from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)

if __package__ in {None, ''}:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from app.chat_engine import ChatEngine
from app.generator import RAGGenerator
from app.ingest import IngestionEngine
from app.retriever import HybridRetriever
from config import (
    ensure_directories,
    get_embedding_model,
    get_llm,
    load_settings,
    validate_for_chat,
    validate_settings,
)


def init_session_state() -> None:
    if st.session_state.get("initialized"):
        return

    settings = load_settings()
    validate_settings(settings)
    ensure_directories(settings)

    st.session_state.settings = settings
    st.session_state.runtime_overrides = {}
    st.session_state.retrieval_mode = "hybrid"
    st.session_state.last_ingest_summary = None
    st.session_state.initialized = True
    reset_runtime_objects()


def reset_runtime_objects() -> None:
    settings = current_settings()
    embedding_model = get_embedding_model(settings)
    st.session_state.ingest_engine = IngestionEngine(settings, embedding_model=embedding_model)
    st.session_state.chat_engine = ChatEngine(settings.storage_dir / "chat_history.json", max_history_turns=settings.max_history_turns)
    st.session_state.retriever = HybridRetriever(settings, st.session_state.ingest_engine.vector_store, embedding_model=embedding_model)
    # Generator is lazily initialized by build_generator() with LLM
    st.session_state.pop("generator", None)
    if not embedding_model and settings.embedding_model_name:
        st.warning(f"⚠️ 嵌入模型 {settings.embedding_model_name} 初始化失败，向量检索将使用词元重叠（token overlap）降级方案。")


def current_settings():
    base = st.session_state.settings
    overrides = st.session_state.get("runtime_overrides", {})
    if not overrides:
        return base
    # Merge overrides on top of the existing (possibly previously merged) base,
    # so that omitting a field in overrides preserves the current value.
    from config import Settings
    merged = {**base.__dict__, **overrides}
    return Settings(**merged)


def build_retriever() -> HybridRetriever:
    settings = current_settings()
    embedding_model = get_embedding_model(settings)
    retriever = HybridRetriever(settings, st.session_state.ingest_engine.vector_store, embedding_model=embedding_model)
    st.session_state.retriever = retriever
    return retriever


def build_generator() -> RAGGenerator:
    settings = current_settings()
    llm = None
    try:
        validate_for_chat(settings)
        llm = get_llm(settings)
    except Exception as exc:
        logger.warning("LLM not available: %s", exc)
        st.warning(f"⚠️ DeepSeek LLM 未配置或初始化失败（{exc}），问答将使用 fallback 模式。请设置 DEEPSEEK_API_KEY。")
    generator = RAGGenerator(settings, llm=llm)
    st.session_state.generator = generator
    return generator


def save_uploaded_files(uploaded_files: list[Any], target_dir: Path) -> list[Path]:
    saved_paths: list[Path] = []
    for uploaded in uploaded_files:
        destination = unique_target_path(target_dir / uploaded.name)
        destination.write_bytes(uploaded.getbuffer())
        saved_paths.append(destination)
    return saved_paths


def unique_target_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem} ({counter}){suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def render_sidebar(stats: dict[str, Any]) -> None:
    chat_engine = st.session_state.chat_engine
    st.sidebar.title("Co-Thinker")
    st.sidebar.caption("本地 RAG MVP")
    st.sidebar.metric("文档数", stats["indexed_document_count"])
    st.sidebar.metric("Chunks", stats["chunk_count"])
    st.sidebar.metric("失败文档", stats["failed_document_count"])
    st.sidebar.selectbox(
        "检索模式",
        options=["hybrid", "vector", "bm25"],
        key="retrieval_mode",
    )
    st.sidebar.markdown("---")
    st.sidebar.caption("会话")
    if st.sidebar.button("新建会话", use_container_width=True):
        chat_engine.create_conversation()
        st.rerun()

    conversations = chat_engine.list_conversations()
    if conversations:
        labels = [item["title"] for item in conversations]
        current_index = next((i for i, item in enumerate(conversations) if item["is_current"]), 0)
        selected = st.sidebar.selectbox("当前会话", options=range(len(conversations)), index=current_index, format_func=lambda i: labels[i])
        selected_id = conversations[selected]["id"]
        if selected_id != chat_engine.current_id:
            chat_engine.switch_conversation(selected_id)
            st.rerun()

    sidebar_cols = st.sidebar.columns(2)
    if sidebar_cols[0].button("清空当前", use_container_width=True, type="secondary"):
        st.session_state.confirm_clear = True
    if st.session_state.get("confirm_clear"):
        st.sidebar.warning("确定清空当前会话消息？")
        confirm_cols = st.sidebar.columns(2)
        if confirm_cols[0].button("确认清空", use_container_width=True, type="primary"):
            chat_engine.clear_history()
            st.session_state.confirm_clear = False
            st.rerun()
        if confirm_cols[1].button("取消", use_container_width=True):
            st.session_state.confirm_clear = False
            st.rerun()

    if sidebar_cols[1].button("删除当前", use_container_width=True, type="secondary"):
        st.session_state.confirm_delete = True
    if st.session_state.get("confirm_delete"):
        st.sidebar.warning("确定删除当前会话？此操作不可恢复。")
        confirm_cols = st.sidebar.columns(2)
        if confirm_cols[0].button("确认删除", use_container_width=True, type="primary"):
            chat_engine.delete_conversation(chat_engine.current_id)
            st.session_state.confirm_delete = False
            st.rerun()
        if confirm_cols[1].button("取消", use_container_width=True):
            st.session_state.confirm_delete = False
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.caption("API Key 配置后会保存到 .env 文件，重启后仍有效")


def _save_env_api_key(api_key: str) -> None:
    """Persist the API key to .env so it survives restart."""
    if not api_key:
        return
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    else:
        lines = []
    # Update or append DEEPSEEK_API_KEY
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith("DEEPSEEK_API_KEY="):
            lines[i] = f"DEEPSEEK_API_KEY={api_key}\n"
            found = True
            break
    if not found:
        lines.append(f"DEEPSEEK_API_KEY={api_key}\n")
    env_path.write_text("".join(lines), encoding="utf-8")


def render_settings(settings) -> None:
    with st.expander("运行时设置", expanded=False):
        deepseek_key = st.text_input(
            "DeepSeek API Key",
            value=settings.deepseek_api_key,
            type="password",
            help="输入后点击「应用」自动保存到 .env，重启不丢失",
        )
        top_k = st.slider("Top K", min_value=1, max_value=10, value=settings.top_k)
        similarity_cutoff = st.slider(
            "相似度阈值",
            min_value=0.0,
            max_value=1.0,
            value=float(settings.similarity_cutoff),
            step=0.05,
        )
        if st.button("应用运行时设置", use_container_width=True):
            if deepseek_key:
                _save_env_api_key(deepseek_key)
            st.session_state.runtime_overrides = {
                "deepseek_api_key": deepseek_key,
                "top_k": top_k,
                "similarity_cutoff": similarity_cutoff,
            }
            reset_runtime_objects()
            st.success("运行时设置已更新。API Key 已保存到 .env 文件，重启后自动加载。")


def render_docs_tab() -> None:
    st.subheader("文档管理")
    settings = current_settings()
    engine = st.session_state.ingest_engine

    uploaded_files = st.file_uploader(
        "上传知识库文档",
        type=["md", "mdx", "txt", "py", "js", "ts", "tsx", "java", "go", "rs", "c", "cpp", "h", "cs", "php", "rb"],
        accept_multiple_files=True,
    )
    tags_raw = st.text_input("标签（逗号分隔，可选）")
    tags = [item.strip() for item in tags_raw.split(",") if item.strip()]

    action_cols = st.columns([1, 1, 1])
    if action_cols[0].button("导入上传文件", use_container_width=True):
        if not uploaded_files:
            st.warning("请先选择至少一个文件。")
        else:
            with st.spinner("正在保存并导入文档..."):
                saved_paths = save_uploaded_files(uploaded_files, settings.data_dir)
                summary = engine.add_files(saved_paths, tags=tags)
                st.session_state.last_ingest_summary = summary
                st.session_state.retriever = build_retriever()
            st.success(f"导入完成：indexed={summary.indexed_files}, skipped={summary.skipped_files}, failed={summary.failed_files}")

    if action_cols[1].button("扫描 data/ 并增量重建", use_container_width=True):
        with st.spinner("正在重建索引..."):
            summary = engine.rebuild_index(force=False)
            st.session_state.last_ingest_summary = summary
            st.session_state.retriever = build_retriever()
        st.success(f"重建完成：indexed={summary.indexed_files}, skipped={summary.skipped_files}, failed={summary.failed_files}")

    if action_cols[2].button("清空索引", use_container_width=True, type="secondary"):
        st.session_state.confirm_clear_index = True
    if st.session_state.get("confirm_clear_index"):
        st.warning("⚠️ 确定清空所有索引和文档清单？此操作不可恢复。")
        confirm_cols = st.columns([1, 1])
        if confirm_cols[0].button("确认清空", use_container_width=True, type="primary"):
            engine.clear_index(clear_manifest=True)
            st.session_state.last_ingest_summary = None
            st.session_state.retriever = build_retriever()
            st.session_state.confirm_clear_index = False
            st.success("索引已清空。")
            st.rerun()
        if confirm_cols[1].button("取消", use_container_width=True):
            st.session_state.confirm_clear_index = False
            st.rerun()

    summary = st.session_state.get("last_ingest_summary")
    if summary is not None:
        with st.expander("最近一次导入结果", expanded=True):
            st.write(
                {
                    "total_files": summary.total_files,
                    "indexed_files": summary.indexed_files,
                    "skipped_files": summary.skipped_files,
                    "failed_files": summary.failed_files,
                    "total_chunks": summary.total_chunks,
                }
            )
            st.dataframe(
                [
                    {
                        "path": item.path,
                        "status": item.status,
                        "document_id": item.document_id,
                        "chunk_count": item.chunk_count,
                        "error": item.error or "",
                    }
                    for item in summary.results
                ],
                use_container_width=True,
            )

    documents = engine.list_documents()
    st.markdown("### 当前文档")
    if not documents:
        st.info("当前知识库为空。")
    else:
        st.dataframe(documents, use_container_width=True)


def render_chat_tab() -> None:
    st.subheader("问答")
    engine = st.session_state.ingest_engine
    chat_engine = st.session_state.chat_engine
    stats = engine.get_index_stats()
    if stats["chunk_count"] == 0:
        st.warning("知识库为空，请先在文档管理中导入文档。")
        return

    for message in chat_engine.current_conversation.messages:
        with st.chat_message(message.role):
            st.markdown(message.content)
            references = message.metadata.get("references", [])
            if references:
                with st.expander("引用来源", expanded=False):
                    for ref in references:
                        st.markdown(f"- `{ref['chunk_id']}` · `{ref['source_path']}`")
            debug = message.metadata.get("debug")
            if debug:
                with st.expander("调试信息", expanded=False):
                    st.json(debug)

    query = st.chat_input("请输入你的问题")
    if not query:
        return

    # Get history before adding the current message to avoid
    # the retriever treating the current query as conversation context
    history = chat_engine.get_history()

    chat_engine.add_user_message(query)
    with st.chat_message("user"):
        st.markdown(query)

    retriever = build_retriever()
    generator = build_generator()

    with st.chat_message("assistant"):
        with st.status("正在检索...", expanded=False) as retrieval_status:
            retrieval_results = retriever.retrieve(
                query,
                chat_history=history,
                mode=st.session_state.retrieval_mode,
            )
            retrieval_status.write(f"检索模式: {retrieval_results.mode}")
            retrieval_status.write(f"有效查询: {retrieval_results.effective_query}")
            retrieval_status.write(f"检索到 {len(retrieval_results.results)} 个片段，耗时 {retrieval_results.elapsed_ms:.0f}ms")

        # Build references from retrieval results before generating
        references = [
            {
                "chunk_id": item.chunk_id,
                "source_path": item.source_path,
                "file_name": item.file_name,
                "score": item.final_score,
                "snippet": item.text[:200],
            }
            for item in retrieval_results.results
        ]
        confidence = retrieval_results.confidence

        # Try streaming first, fall back to sync generate
        stream_start = time.perf_counter()
        if retrieval_results.results and generator.llm is not None:
            answer_placeholder = st.empty()
            streamed_chunks: list[str] = []
            try:
                for chunk in generator.stream_generate(query, retrieval_results, chat_history=history):
                    streamed_chunks.append(chunk)
                    answer_placeholder.markdown("".join(streamed_chunks) + "▌")
                full_answer = "".join(streamed_chunks)
                generation_elapsed_ms = (time.perf_counter() - stream_start) * 1000
                answer_placeholder.markdown(full_answer)
            except Exception as exc:
                logger.error("Stream generation failed: %s", exc)
                full_answer = generator.friendly_error_message(exc)
                generation_elapsed_ms = (time.perf_counter() - stream_start) * 1000
                st.markdown(full_answer)
        else:
            generation = generator.generate(query, retrieval_results, chat_history=history)
            full_answer = generation.answer
            generation_elapsed_ms = generation.elapsed_ms
            st.markdown(full_answer)

        if references:
            with st.expander("引用来源", expanded=True):
                for ref in references:
                    st.markdown(f"- `{ref['chunk_id']}` · `{ref['source_path']}`")
                    if ref.get("snippet"):
                        st.caption(ref["snippet"])
        debug_payload = {
            "effective_query": retrieval_results.effective_query,
            "mode": retrieval_results.mode,
            "retrieval_elapsed_ms": retrieval_results.elapsed_ms,
            "generation_elapsed_ms": generation_elapsed_ms,
            "confidence": confidence,
            "sources": retrieval_results.to_sources(),
        }
        with st.expander("调试信息", expanded=False):
            st.json(debug_payload)

    chat_engine.add_assistant_message(
        full_answer,
        references=references,
        debug=debug_payload,
        confidence=confidence,
        retrieval_mode=retrieval_results.mode,
        retrieval_elapsed_ms=retrieval_results.elapsed_ms,
        generation_elapsed_ms=generation_elapsed_ms,
    )


def main() -> None:
    st.set_page_config(page_title="Co-Thinker", layout="wide")
    init_session_state()

    settings = current_settings()
    stats = st.session_state.ingest_engine.get_index_stats()

    st.title("Co-Thinker")
    st.caption("本地知识库问答 MVP")
    render_sidebar(stats)
    render_settings(settings)

    overview_cols = st.columns(4)
    overview_cols[0].metric("已索引文档", stats["indexed_document_count"])
    overview_cols[1].metric("Chunks", stats["chunk_count"])
    overview_cols[2].metric("失败文档", stats["failed_document_count"])
    overview_cols[3].metric("最后更新", stats["last_updated_at"] or "-")

    docs_tab, chat_tab = st.tabs(["文档管理", "问答"])
    with docs_tab:
        render_docs_tab()
    with chat_tab:
        render_chat_tab()


if __name__ == "__main__":
    main()
