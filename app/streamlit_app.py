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
    _load_env_file,
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

    # 从工作目录的 .env 文件加载环境变量（双重保障）
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        _load_env_file(env_path)

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
        st.warning(f"⚠️ DeepSeek LLM 未配置或初始化失败（{exc}），问答将使用 fallback 模式。请在终端运行 `co-thinker init` 或编辑 .env 文件设置 DEEPSEEK_API_KEY。")
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


def render_right_column() -> None:
    """Right column: retrieval mode → session management."""
    chat_engine = st.session_state.chat_engine

    # ── 检索模式（精简一行） ──
    st.markdown("### 🔍 检索模式")

    st.selectbox(
        "检索方式",
        options=["hybrid", "vector", "bm25"],
        key="retrieval_mode",
        label_visibility="collapsed",
        help="hybrid：混合检索（推荐）；vector：仅向量检索；bm25：仅关键词检索",
    )
    st.caption("hybrid（推荐）· vector · bm25")

    st.divider()

    # ── 会话 ──
    st.markdown("### 💬 会话")

    if st.button("➕ 新建会话", use_container_width=True, type="primary"):
        chat_engine.create_conversation()
        st.rerun()

    conversations = chat_engine.list_conversations()
    if conversations:
        labels = [item["title"] for item in conversations]
        current_index = next(
            (i for i, item in enumerate(conversations) if item["is_current"]), 0
        )
        selected = st.selectbox(
            "切换会话",
            options=range(len(conversations)),
            index=current_index,
            format_func=lambda i: labels[i],
            label_visibility="collapsed",
        )
        selected_id = conversations[selected]["id"]
        if selected_id != chat_engine.current_id:
            chat_engine.switch_conversation(selected_id)
            st.rerun()

    col1, col2 = st.columns(2)
    if col1.button("🗑️ 清空", use_container_width=True, help="清空当前会话消息"):
        st.session_state.confirm_clear = True
    if col2.button("❌ 删除", use_container_width=True, help="删除当前会话"):
        st.session_state.confirm_delete = True

    if st.session_state.get("confirm_clear"):
        st.warning("确定清空当前会话消息？")
        c1, c2 = st.columns(2)
        if c1.button("确认清空", use_container_width=True, type="primary"):
            chat_engine.clear_history()
            st.session_state.confirm_clear = False
            st.rerun()
        if c2.button("取消", use_container_width=True):
            st.session_state.confirm_clear = False
            st.rerun()

    if st.session_state.get("confirm_delete"):
        st.warning("确定删除当前会话？此操作不可恢复。")
        c1, c2 = st.columns(2)
        if c1.button("确认删除", use_container_width=True, type="primary"):
            chat_engine.delete_conversation(chat_engine.current_id)
            st.session_state.confirm_delete = False
            st.rerun()
        if c2.button("取消", use_container_width=True):
            st.session_state.confirm_delete = False
            st.rerun()


def render_left_column() -> None:
    """Render the left column: settings → document import → file list."""
    settings = current_settings()
    engine = st.session_state.ingest_engine

    # ── 参数设置（紧凑版） ──
    st.markdown("### ⚙️ 检索设置")
    ref_col, match_col, btn_col = st.columns([1, 1, 1])
    with ref_col:
        ref_count = st.number_input(
            "参考片段数", min_value=1, max_value=10, value=settings.top_k,
            help="每次问答取多少个片段作参考",
        )
    with match_col:
        match_level = st.number_input(
            "匹配相关度",
            min_value=0.0, max_value=1.0,
            value=float(settings.similarity_cutoff), step=0.05, format="%.2f",
            help="越高越精准，越低结果越多但可能不相关",
        )
    with btn_col:
        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
        if st.button("应用", use_container_width=True):
            st.session_state.runtime_overrides = {
                "top_k": ref_count,
                "similarity_cutoff": match_level,
            }
            reset_runtime_objects()
            st.success("已更新。")

    st.divider()

    # ── 文档导入 ──
    st.markdown("### 📄 文档导入")
    uploaded_files = st.file_uploader(
        "选择文件上传",
        type=[
            "md", "mdx", "txt", "py", "js", "jsx", "ts", "tsx",
            "java", "go", "rs", "c", "cpp", "h", "cs", "php", "rb",
            "json", "yaml", "yml", "toml", "xml", "csv", "sql", "log",
            "pdf", "docx", "pptx",
        ],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    tags_raw = st.text_input("标签（逗号分隔，可选）", placeholder="例如：docs, guide, report")
    tags = [item.strip() for item in tags_raw.split(",") if item.strip()]

    import_cols = st.columns(2)
    if import_cols[0].button("📥 导入", use_container_width=True, type="primary"):
        if not uploaded_files:
            st.warning("请先选择至少一个文件。")
        else:
            with st.spinner("正在保存并导入文档..."):
                saved_paths = save_uploaded_files(uploaded_files, settings.data_dir)
                summary = engine.add_files(saved_paths, tags=tags)
                st.session_state.last_ingest_summary = summary
                st.session_state.retriever = build_retriever()
            st.success(f"导入完成：已索引 {summary.indexed_files}，跳过 {summary.skipped_files}，失败 {summary.failed_files}")

    if import_cols[1].button("🔄 增量重建", use_container_width=True):
        with st.spinner("正在重建索引..."):
            summary = engine.rebuild_index(force=False)
            st.session_state.last_ingest_summary = summary
            st.session_state.retriever = build_retriever()
        st.success(f"重建完成：已索引 {summary.indexed_files}，跳过 {summary.skipped_files}，失败 {summary.failed_files}")

    summary = st.session_state.get("last_ingest_summary")
    if summary is not None:
        with st.expander("最近一次导入结果", expanded=False):
            res_cols = st.columns(4)
            res_cols[0].metric("总数", summary.total_files)
            res_cols[1].metric("已索引", summary.indexed_files)
            res_cols[2].metric("跳过", summary.skipped_files)
            res_cols[3].metric("失败", summary.failed_files)
            if summary.results:
                st.dataframe(
                    [
                        {
                            "文件": item.path,
                            "状态": item.status,
                            "分块数": item.chunk_count,
                            "错误": item.error or "",
                        }
                        for item in summary.results
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

    # ── 文档管理区 ──
    st.markdown("### 📂 文件列表")
    documents = engine.list_documents()
    if not documents:
        st.info("知识库为空，请通过上方导入区添加文档。")
        return

    search_q = st.text_input("搜索文件名", placeholder="关键词...", label_visibility="collapsed")
    status_filter = st.selectbox(
        "状态过滤", ["全部", "indexed", "failed"], label_visibility="collapsed"
    )
    all_tags = sorted({tag for doc in documents for tag in doc.get("tags", [])})
    tag_filter = st.selectbox("标签过滤", ["全部"] + all_tags, label_visibility="collapsed")

    filtered = documents[:]
    if search_q:
        q = search_q.lower()
        filtered = [
            d for d in filtered
            if q in d.get("file_name", "").lower() or q in d.get("source_path", "").lower()
        ]
    if status_filter != "全部":
        filtered = [d for d in filtered if d.get("status") == status_filter]
    if tag_filter != "全部":
        filtered = [d for d in filtered if tag_filter in d.get("tags", [])]

    # Batch ops toggle
    show_batch = st.toggle("批量操作", value=st.session_state.get("show_batch_ops", False))
    st.session_state.show_batch_ops = show_batch

    if st.session_state.get("show_batch_ops") and filtered:
        with st.container(border=True):
            st.markdown(f"已筛选 **{len(filtered)}** 个文档")
            batch_cols = st.columns(2)
            if batch_cols[0].button("批量删除", type="secondary", use_container_width=True):
                for doc in filtered:
                    try:
                        engine.delete_file(doc["document_id"])
                    except Exception:
                        pass
                st.session_state.retriever = build_retriever()
                st.rerun()
            if batch_cols[1].button("批量重建", use_container_width=True):
                paths = [doc["source_path"] for doc in filtered]
                summary = engine.add_files(paths, tags=None)
                st.session_state.last_ingest_summary = summary
                st.session_state.retriever = build_retriever()
                st.rerun()

    if not filtered:
        st.info("没有匹配的文档。")
        return

    for doc in filtered:
        doc_id = doc["document_id"]
        with st.container(border=True):
            doc_cols = st.columns([3, 1])
            doc_cols[0].markdown(f"**{doc.get('file_name', '?')}**")
            status = doc.get("status", "")
            if status == "indexed":
                doc_cols[1].markdown(":green[已索引]")
            elif status == "failed":
                doc_cols[1].markdown(":red[失败]")
            else:
                doc_cols[1].write(status)
            st.caption(
                f"{doc.get('file_ext', '')} · {doc.get('chunk_count', 0)} 分块"
                + (f" · {', '.join(doc.get('tags', []))}" if doc.get("tags") else "")
            )
            act_cols = st.columns(4)
            if act_cols[0].button("🔍 分块", key=f"view_{doc_id}", help="查看分块"):
                st.session_state.view_chunks_doc_id = doc_id
            if act_cols[1].button("🏷️ 标签", key=f"tag_{doc_id}", help="编辑标签"):
                st.session_state.edit_tags_doc_id = doc_id
            if act_cols[2].button("🔄 重建", key=f"reindex_{doc_id}", help="重新索引"):
                try:
                    engine.delete_file(doc_id)
                    summary = engine.add_files([doc["source_path"]], tags=doc.get("tags"))
                    st.session_state.last_ingest_summary = summary
                    st.session_state.retriever = build_retriever()
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            if act_cols[3].button("🗑️", key=f"del_{doc_id}", help="删除文档"):
                st.session_state.confirm_delete_doc_id = doc_id
        # ── 删除确认 ──
        if st.session_state.get("confirm_delete_doc_id") == doc_id:
            st.warning(f"确定删除「{doc.get('file_name', '')}」？此操作不可恢复。")
            c1, c2 = st.columns(2)
            if c1.button("确认删除", key=f"cf_del_{doc_id}", type="primary"):
                try:
                    engine.delete_file(doc_id)
                    st.session_state.retriever = build_retriever()
                except Exception as e:
                    st.error(str(e))
                st.session_state.confirm_delete_doc_id = None
                st.rerun()
            if c2.button("取消", key=f"cancel_del_{doc_id}"):
                st.session_state.confirm_delete_doc_id = None
                st.rerun()
        # ── 标签编辑 ──
        if st.session_state.get("edit_tags_doc_id") == doc_id:
            with st.container(border=True):
                st.markdown(f"**编辑标签：{doc.get('file_name', '')}**")
                current_tags = list(doc.get("tags", []))
                st.markdown(f"当前标签：{', '.join(current_tags) if current_tags else '无'}")
                new_tag = st.text_input("添加标签", key=f"edit_tag_{doc_id}")
                tag_act_cols = st.columns([1, 1, 3])
                if tag_act_cols[0].button("添加", type="primary"):
                    if new_tag.strip() and new_tag.strip() not in current_tags:
                        current_tags.append(new_tag.strip())
                        doc["tags"] = current_tags
                        engine.manifest.upsert_document(doc)
                        st.rerun()
                if tag_act_cols[1].button("关闭"):
                    st.session_state.edit_tags_doc_id = None
                    st.rerun()
        # ── 查看分块 ──
        if st.session_state.get("view_chunks_doc_id") == doc_id:
            with st.container(border=True):
                st.markdown(f"**分块列表：{doc.get('file_name', '')}**")
                all_records = engine.vector_store.iter_records()
                doc_chunks = [r for r in all_records if r.get("document_id") == doc_id]
                if doc_chunks:
                    st.dataframe(
                        [
                            {
                                "分块ID": r.get("chunk_id", ""),
                                "内容预览": r.get("text", "")[:150],
                                "长度": len(r.get("text", "")),
                            }
                            for r in doc_chunks
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("该文档暂无分块记录。")
                if st.button("关闭", key=f"close_chunks_{doc_id}"):
                    st.session_state.view_chunks_doc_id = None
                    st.rerun()


def render_chat_tab() -> None:
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

    # Inject CSS: each column is fixed at viewport height and scrolls independently.
    # The column container (data-testid="column") sits in a flex row inside
    # data-testid="stHorizontalBlock". We force that row to fill the remaining
    # viewport, then each column becomes a scrollable pane.
    st.markdown(
        """
        <style>
        /* Full-height horizontal block (the columns row) */
        div[data-testid="stHorizontalBlock"] {
            height: calc(100vh - 6rem) !important;
            gap: 0.75rem;
            align-items: stretch;
        }
        /* Each column is a scrollable pane */
        div[data-testid="column"] {
            height: 100% !important;
            min-height: 0 !important;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        /* The inner wrapper scrolls */
        div[data-testid="column"] > div:first-child {
            height: 100% !important;
            overflow-y: auto !important;
            padding-right: 0.5rem;
            scrollbar-width: thin;
            scrollbar-color: #ddd transparent;
        }
        div[data-testid="column"] > div:first-child::-webkit-scrollbar {
            width: 4px;
        }
        div[data-testid="column"] > div:first-child::-webkit-scrollbar-thumb {
            background: #ddd;
            border-radius: 2px;
        }
        /* Hide Streamlit header/decorations for max space */
        header { display: none !important; }
        #MainMenu, footer { display: none; }
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 0 !important;
            max-width: 100% !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("Co-Thinker")

    left_col, mid_col, right_col = st.columns([1.3, 2, 1])

    with left_col:
        render_left_column()

    with mid_col:
        stats = st.session_state.ingest_engine.get_index_stats()
        st.markdown("## 💡 问答")
        if stats["chunk_count"] == 0:
            st.info("知识库为空，请在左侧文档导入中添加文档。")
        else:
            render_chat_tab()

    with right_col:
        render_right_column()


if __name__ == "__main__":
    main()
