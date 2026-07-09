from __future__ import annotations

import logging
from core.project import ProjectConfig
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

logger = logging.getLogger(__name__)

from core.retriever import RetrievalResults
from core.project import ProjectConfig

DEFAULT_RAG_SYSTEM_PROMPT = """你是 Co-Thinker，一个基于领域知识库的问答助手。
You are Co-Thinker, a Q&A assistant grounded in a domain-specific knowledge base.

必须遵守以下规则：
1.  仅基于 <context> 中提供的知识库片段来回答。
2.  如果 <context> 中没有足够信息，请明确说"知识库中未找到相关信息"，不要编造事实。
3.  陈述事实、结论、步骤或代码说明时，请标注来源编号如 [1]、[2]。
4.  如果多个片段互相矛盾，指出矛盾点并分别列出来源。
5.  保留代码、配置名和文件路径原样——不要翻译或改写。
6.  用用户提问的语言回答。用户用中文则用中文回答，用英文则用英文回答。
7.  保持结构化回复：先直接回答，再提供支撑证据或步骤。
8.  如果知识库片段中包含 Markdown 格式（标题、列表、粗体等），请用自然语言转述，不要直接输出原始 Markdown 标记。用自然流畅的口吻表达内容，不要保留 #、*、- 等标记符号。

(English version of rules above — answer in the user's language.)
"""

USER_PROMPT_TEMPLATE = """{instructions}<context>
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
    # Character-level estimates (not token counts) — see _estimate_chars
    input_chars: int = 0
    output_chars: int = 0
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
            # Don't retry on auth errors or invalid model errors.
            # "model not found" / "model does not exist" — pair check to avoid
            # false positives on legitimate error messages containing "model".
            if any(word in msg for word in ("api key", "authentication", "401")):
                raise
            if ("model" in msg) and ("not" in msg) and ("found" in msg or "exist" in msg or "support" in msg):
                raise
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # exponential backoff
                logger.warning("LLM call failed (attempt %d/%d): %s. Retrying in %.1fs...",
                               attempt + 1, max_retries, exc, delay)
                time.sleep(delay)
    raise LLMRetryError(f"LLM call failed after {max_retries} retries: {last_exc}") from last_exc


class RAGGenerator:
    def __init__(self, config: ProjectConfig, llm: Any | None = None, prompt_template: str | None = None):
        self.config = config
        self.llm = llm
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
            messages = self.build_messages(query, retrieval_results, chat_history)
            answer = self._generate_with_llm(messages)
            if not answer.strip():
                raise ValueError("LLM returned empty content")
            return GenerationResult(
                answer=answer,
                references=references,
                finish_reason="stop",
                elapsed_ms=(time.perf_counter() - started) * 1000,
                input_chars=sum(len(message["content"]) for message in messages),
                output_chars=len(answer),
                confidence=confidence,
            )
        except Exception as exc:
            logger.exception("Generation failed: %s", exc)
            return GenerationResult(
                answer=self.friendly_error_message(exc),
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
        model: str | None = None,
    ) -> Iterable[tuple[str, str]]:
        """流式生成回答，每个事件为 (event_type, content) 元组。

        event_type:
          - "content" — 答案文本片段
          - "reasoning" — 推理过程文本片段
        """
        if not retrieval_results.results:
            yield ("content", NO_RESULT_MESSAGE)
            return

        if self.llm is None:
            result = self.generate(query, retrieval_results, chat_history)
            yield ("content", result.answer)
            return

        try:
            messages = self.build_messages(query, retrieval_results, chat_history)
            effective_model = model or self.config.model
            response = _llm_call_with_retry(
                self.llm,
                model=effective_model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                stream=True,
            )
            for chunk in response:
                choices = chunk.choices
                if not choices:
                    continue
                delta = choices[0].delta
                if not delta:
                    continue
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    yield ("reasoning", reasoning)
                if delta.content:
                    yield ("content", delta.content)
        except Exception as exc:
            logger.exception("Stream generation failed: %s", exc)
            yield ("content", self.friendly_error_message(exc))

    def build_messages(
        self,
        query: str,
        retrieval_results: RetrievalResults,
        chat_history: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, str]]:
        context = retrieval_results.to_context_text(token_budget=self.config.context_token_budget)
        history = self.format_history(chat_history, self.config.max_history_turns)
        instructions = ""
        if retrieval_results.confidence == "low":
            instructions = f"<instructions>\n{LOW_CONFIDENCE_NOTICE}\n</instructions>\n\n"
        user_prompt = USER_PROMPT_TEMPLATE.format(
            instructions=instructions,
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

    def format_history(
        self,
        chat_history: list[dict[str, Any]] | None,
        max_turns: int,
        per_msg_max_chars: int = 500,
    ) -> str:
        """Format chat history for the LLM prompt.

        Each message is truncated to *per_msg_max_chars* to prevent large
        code blocks or long references from consuming the context budget.
        """
        if not chat_history:
            return ""
        recent = chat_history[-max_turns * 2 :]
        lines: list[str] = []
        for message in recent:
            role = "用户" if message.get("role") == "user" else "助手"
            content = str(message.get("content", "")).strip()
            if not content:
                continue
            if len(content) > per_msg_max_chars:
                content = content[:per_msg_max_chars] + f"\n… [截断至 {per_msg_max_chars} 字符]"
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _generate_with_llm(self, messages: list[dict[str, str]]) -> str:
        if self.llm is None:
            return self._fallback_answer(messages)

        response = _llm_call_with_retry(
            self.llm,
            model=self.config.model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        content = response.choices[0].message.content
        return content or ""

    def _fallback_answer(self, messages: list[dict[str, str]]) -> str:
        """Produce a simple fallback when no LLM is configured.

        Extracts source paths from the rendered user prompt (generated by
        USER_PROMPT_TEMPLATE) to provide source attribution.
        """
        user_message = messages[-1]["content"] if messages else ""
        source_paths: list[str] = []
        for line in user_message.splitlines():
            if line.startswith("source:"):
                source_paths.append(line.split(":", 1)[1].strip())
        return (
            "基于检索到的知识片段，我已经整理出相关内容。"
            + (f"\n\n引用来源：\n" + "\n".join(
                f"[{i}] {p}" for i, p in enumerate(source_paths[:5], start=1)
            ) if source_paths else "")
        )

    def friendly_error_message(self, error: Exception) -> str:
        message = str(error)
        msg_lower = message.lower()

        if "DEEPSEEK_API_KEY" in message:
            return "缺少 DEEPSEEK_API_KEY，请在 .env 或设置页中配置后重试。"
        if "api key" in msg_lower or "authentication" in msg_lower or "401" in message:
            return "DeepSeek API Key 认证失败，请检查密钥是否正确。"
        if "insufficient_quota" in msg_lower or "余额" in message or "quota" in msg_lower:
            return "DeepSeek API 额度不足，请检查账户余额。"
        if "model" in msg_lower and "not" in msg_lower and ("found" in msg_lower or "exist" in msg_lower or "support" in msg_lower):
            return f"模型不可用（{self.config.model}），请检查 模型 配置。"
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
