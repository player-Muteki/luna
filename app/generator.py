from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

logger = logging.getLogger(__name__)

from app.retriever import RetrievalResults
from config import Settings, validate_for_chat

DEFAULT_RAG_SYSTEM_PROMPT = """你是 Co-Thinker，一个面向特定领域知识库的问答助手。

你必须遵守以下规则：
1. 只能基于 <context> 中提供的知识库片段回答。
2. 如果 <context> 没有足够信息，明确说"知识库中未找到足够信息"，不要编造。
3. 回答中涉及事实、结论、步骤或代码说明时，应引用来源编号，例如 [1]、[2]。
4. 如果多个片段互相矛盾，指出矛盾并分别列出来源。
5. 对代码、配置名、文件路径保持原样，不要翻译或改写。
6. 默认使用中文回答，除非用户明确要求其他语言。
7. 保持结构清晰：先直接回答，再列出依据或步骤。
"""

USER_PROMPT_TEMPLATE = """<context>
{context}
</context>

<chat_history>
{chat_history}
</chat_history>

<question>
{question}
</question>"""

NO_RESULT_MESSAGE = """知识库中未找到与该问题相关的足够信息。

你可以尝试：
1. 换用更具体的关键词。
2. 检查相关文档是否已导入。
3. 在文档管理页重新构建索引。"""

LOW_CONFIDENCE_NOTICE = "注意：以下检索结果相关性较低。请谨慎回答；如果依据不足，请明确说明。"


@dataclass
class SourceReference:
    source_path: str
    file_name: str
    chunk_id: str
    score: float
    snippet: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    answer: str
    references: list[SourceReference]
    finish_reason: str
    elapsed_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    confidence: str = "unknown"
    error: str | None = None


class LLMRetryError(Exception):
    """Raised when all LLM retry attempts are exhausted."""


def _llm_call_with_retry(
    llm: Any,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    stream: bool = False,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> Any:
    """Call the LLM with exponential backoff retry logic.

    Pattern inspired by DeepTutor's LLM retry configuration.
    """
    import time as _time

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            if stream:
                return llm.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
            return llm.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            last_exc = exc
            msg = str(exc).lower()
            # Don't retry on auth errors or invalid model errors
            if any(word in msg for word in ("api key", "authentication", "401", "model", "not found")):
                raise
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # exponential backoff
                logger.warning("LLM call failed (attempt %d/%d): %s. Retrying in %.1fs...",
                               attempt + 1, max_retries, exc, delay)
                _time.sleep(delay)
    raise LLMRetryError(f"LLM call failed after {max_retries} retries: {last_exc}") from last_exc


class RAGGenerator:
    def __init__(self, settings: Settings, llm: Any | None = None, prompt_template: str | None = None):
        self.settings = settings
        self.llm = llm  # openai.OpenAI client instance
        self.prompt_template = prompt_template or DEFAULT_RAG_SYSTEM_PROMPT

    def generate(
        self,
        query: str,
        retrieval_results: RetrievalResults,
        chat_history: list[dict[str, Any]] | None = None,
    ) -> GenerationResult:
        started = time.perf_counter()
        references = self.extract_references(retrieval_results)
        confidence = retrieval_results.confidence

        if not retrieval_results.results:
            return GenerationResult(
                answer=NO_RESULT_MESSAGE,
                references=[],
                finish_reason="no_context",
                elapsed_ms=(time.perf_counter() - started) * 1000,
                confidence="none",
            )

        try:
            validate_for_chat(self.settings)
            messages = self.build_messages(query, retrieval_results, chat_history)
            answer = self._invoke_llm(messages)
            if not answer.strip():
                raise ValueError("LLM returned empty content")
            return GenerationResult(
                answer=answer,
                references=references,
                finish_reason="stop",
                elapsed_ms=(time.perf_counter() - started) * 1000,
                input_tokens=sum(len(message["content"]) for message in messages),
                output_tokens=len(answer),
                confidence=confidence,
            )
        except Exception as exc:
            return GenerationResult(
                answer=self._friendly_error_message(exc),
                references=references,
                finish_reason="error",
                elapsed_ms=(time.perf_counter() - started) * 1000,
                confidence=confidence,
                error=str(exc),
            )

    def stream_generate(
        self,
        query: str,
        retrieval_results: RetrievalResults,
        chat_history: list[dict[str, Any]] | None = None,
    ) -> Iterable[str]:
        if not retrieval_results.results:
            yield NO_RESULT_MESSAGE
            return

        if self.llm is None:
            result = self.generate(query, retrieval_results, chat_history)
            yield result.answer
            return

        try:
            validate_for_chat(self.settings)
            messages = self.build_messages(query, retrieval_results, chat_history)
            response = _llm_call_with_retry(
                self.llm,
                model=self.settings.deepseek_model,
                messages=messages,
                temperature=self.settings.temperature,
                max_tokens=self.settings.max_tokens,
                stream=True,
            )
            for chunk in response:
                choices = chunk.choices
                if not choices:
                    continue
                delta = choices[0].delta
                if delta and delta.content:
                    yield delta.content
        except Exception as exc:
            yield self._friendly_error_message(exc)

    def build_messages(
        self,
        query: str,
        retrieval_results: RetrievalResults,
        chat_history: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, str]]:
        context = retrieval_results.to_context_text(token_budget=self.settings.context_token_budget)
        history = self.format_history(chat_history, self.settings.max_history_turns)
        if retrieval_results.confidence == "low":
            context = f"{LOW_CONFIDENCE_NOTICE}\n\n{context}"
        user_prompt = USER_PROMPT_TEMPLATE.format(
            context=context,
            chat_history=history,
            question=query,
        )
        return [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user_prompt},
        ]

    def extract_references(self, retrieval_results: RetrievalResults) -> list[SourceReference]:
        seen: set[str] = set()
        references: list[SourceReference] = []
        for result in retrieval_results.results:
            if result.chunk_id in seen:
                continue
            seen.add(result.chunk_id)
            references.append(
                SourceReference(
                    source_path=result.source_path,
                    file_name=result.file_name,
                    chunk_id=result.chunk_id,
                    score=result.final_score,
                    snippet=result.text[:200],
                    metadata=result.metadata,
                )
            )
        return references

    def format_history(self, chat_history: list[dict[str, Any]] | None, max_turns: int) -> str:
        if not chat_history:
            return ""
        recent = chat_history[-max_turns * 2 :]
        lines: list[str] = []
        for message in recent:
            role = "用户" if message.get("role") == "user" else "助手"
            content = str(message.get("content", "")).strip()
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _invoke_llm(self, messages: list[dict[str, str]]) -> str:
        if self.llm is None:
            return self._fallback_answer(messages)

        response = _llm_call_with_retry(
            self.llm,
            model=self.settings.deepseek_model,
            messages=messages,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )
        content = response.choices[0].message.content
        return content or ""

    def _fallback_answer(self, messages: list[dict[str, str]]) -> str:
        user_message = messages[-1]["content"] if messages else ""
        cited_sources: list[str] = []
        for line in user_message.splitlines():
            if line.startswith("source:"):
                cited_sources.append(line.split(":", 1)[1].strip())
        source_suffix = "" if not cited_sources else f"\n\n引用来源：\n[1] {cited_sources[0]}"
        return f"基于检索到的知识片段，我已经整理出相关内容。{source_suffix}"

    def _friendly_error_message(self, error: Exception) -> str:
        message = str(error)
        msg_lower = message.lower()

        if "DEEPSEEK_API_KEY" in message:
            return "缺少 DEEPSEEK_API_KEY，请在 .env 或设置页中配置后重试。"
        if "api key" in msg_lower or "authentication" in msg_lower or "401" in message:
            return "DeepSeek API Key 认证失败，请检查密钥是否正确。"
        if "insufficient_quota" in msg_lower or "余额" in message or "quota" in msg_lower:
            return "DeepSeek API 额度不足，请检查账户余额。"
        if "model" in msg_lower and "not" in msg_lower and ("found" in msg_lower or "exist" in msg_lower or "support" in msg_lower):
            return f"模型不可用（{self.settings.deepseek_model}），请检查 DEEPSEEK_MODEL 配置。"
        if "server" in msg_lower and "error" in msg_lower:
            return "DeepSeek 服务暂时不可用，请稍后重试。"
        if "timeout" in msg_lower or "timed out" in msg_lower:
            return "模型服务超时，请稍后重试。"
        if "rate" in msg_lower or "too many" in msg_lower:
            return "请求过于频繁，请稍后重试。"
        if "context" in msg_lower and "length" in msg_lower:
            return "输入内容过长，超过了模型上下文限制。"
        if "empty content" in msg_lower:
            return "模型没有返回有效内容，请稍后重试。"
        logger.warning("Unhandled generation error: %s", message)
        return f"生成答案时发生错误：{message}"
