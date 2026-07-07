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
    st.sidebar.caption("API Key 通过终端 `co-thinker init` 或编辑 .env 文件配置")


def render_settings(settings) -> None:
    with st.expander("运行时设置", expanded=False):
        top_k = st.slider("Top K", min_value=1, max_value=10, value=settings.top_k)
        similarity_cutoff = st.slider(
            "相似度阈值",
            min_value=0.0,
            max_value=1.0,
            value=float(settings.similarity_cutoff),
            step=0.05,
        )
        if st.button("应用运行时设置", use_container_width=True):
            st.session_state.runtime_overrides = {
                "top_k": top_k,
                "similarity_cutoff": similarity_cutoff,
            }
            reset_runtime_objects()
            st.success("运行时设置已更新。")


def render_docs_tab() -> None:
    settings = current_settings()
    engine = st.session_state.ingest_engine

    # ── 统计概览区 ──
    stats = engine.get_index_stats()
    overview_cols = st.columns(5)
    overview_cols[0].metric("文档总数", stats["document_count"])
    overview_cols[1].metric("已索引", stats["indexed_document_count"])
    overview_cols[2].metric("失败", stats["failed_document_count"])
    overview_cols[3].metric("分块数", stats["chunk_count"])
    overview_cols[4].metric("最后更新", stats["last_updated_at"][:10] if stats.get("last_updated_at") else "-")

    st.divider()

    # ── 文档导入区 ──
    with st.container(border=True):
        st.markdown("**文档导入**")
        uploaded_files = st.file_uploader(
            "上传知识库文档",
            type=[
                "md", "mdx", "txt", "py", "js", "ts", "tsx",
                "java", "go", "rs", "c", "cpp", "h", "cs", "php", "rb",
                "pdf", "docx", "pptx",
            ],
            accept_multiple_files=True,
        )
        tags_raw = st.text_input("标签（逗号分隔，可选）", placeholder="例如：docs, guide, report")
        tags = [item.strip() for item in tags_raw.split(",") if item.strip()]

        import_cols = st.columns([1, 1, 2])
        if import_cols[0].button("导入上传文件", use_container_width=True, type="primary"):
            if not uploaded_files:
                st.warning("请先选择至少一个文件。")
            else:
                with st.spinner("正在保存并导入文档..."):
                    saved_paths = save_uploaded_files(uploaded_files, settings.data_dir)
                    summary = engine.add_files(saved_paths, tags=tags)
                    st.session_state.last_ingest_summary = summary
                    st.session_state.retriever = build_retriever()
                st.success(f"导入完成：已索引 {summary.indexed_files}，跳过 {summary.skipped_files}，失败 {summary.failed_files}")

        if import_cols[1].button("扫描 data/ 并增量重建", use_container_width=True):
            with st.spinner("正在重建索引..."):
                summary = engine.rebuild_index(force=False)
                st.session_state.last_ingest_summary = summary
                st.session_state.retriever = build_retriever()
            st.success(f"重建完成：已索引 {summary.indexed_files}，跳过 {summary.skipped_files}，失败 {summary.failed_files}")

        summary = st.session_state.get("last_ingest_summary")
        if summary is not None:
            with st.expander("最近一次导入结果", expanded=True):
                res_cols = st.columns(4)
                res_cols[0].metric("文件总数", summary.total_files)
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

    st.divider()

    # ── 文档管理区 ──
    documents = engine.list_documents()
    if not documents:
        st.info("当前知识库为空，请通过上方导入区域添加文档。")
        return

    filter_cols = st.columns([2, 1, 1, 1, 1])
    with filter_cols[0]:
        search_query = st.text_input("搜索文件名", placeholder="关键词...", label_visibility="collapsed")
    with filter_cols[1]:
        status_options = ["全部", "indexed", "failed"]
        status_filter = st.selectbox("状态", status_options, label_visibility="collapsed")
    with filter_cols[2]:
        all_exts = sorted({doc.get("file_ext", "") for doc in documents})
        type_filter = st.selectbox("类型", ["全部"] + all_exts, label_visibility="collapsed")
    with filter_cols[3]:
        all_tags = sorted({tag for doc in documents for tag in doc.get("tags", [])})
        tag_filter = st.selectbox("标签", ["全部"] + all_tags, label_visibility="collapsed")
    with filter_cols[4]:
        show_batch = st.toggle("批量操作", value=st.session_state.get("show_batch_ops", False))
        st.session_state.show_batch_ops = show_batch

    filtered = documents[:]
    if search_query:
        q = search_query.lower()
        filtered = [
            d for d in filtered
            if q in d.get("file_name", "").lower() or q in d.get("source_path", "").lower()
        ]
    if status_filter != "全部":
        filtered = [d for d in filtered if d.get("status") == status_filter]
    if type_filter != "全部":
        filtered = [d for d in filtered if d.get("file_ext") == type_filter]
    if tag_filter != "全部":
        filtered = [d for d in filtered if tag_filter in d.get("tags", [])]

    if st.session_state.get("show_batch_ops") and filtered:
        with st.container(border=True):
            st.markdown(f"已筛选 **{len(filtered)}** 个文档")
            batch_cols = st.columns([1, 1, 4])
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

    header_cols = st.columns([3, 1, 1.5, 1, 1, 1, 2.5])
    header_cols[0].markdown("**文件名**")
    header_cols[1].markdown("**类型**")
    header_cols[2].markdown("**标签**")
    header_cols[3].markdown("**分块数**")
    header_cols[4].markdown("**状态**")
    header_cols[5].markdown("**更新**")
    header_cols[6].markdown("**操作**")

    for doc in filtered:
        cols = st.columns([3, 1, 1.5, 1, 1, 1, 2.5])
        with cols[0]:
            st.markdown(doc.get("file_name", "?"))
        with cols[1]:
            st.write(doc.get("file_ext", ""))
        with cols[2]:
            tags = doc.get("tags", [])
            st.write(", ".join(tags) if tags else "-")
        with cols[3]:
            st.write(str(doc.get("chunk_count", 0)))
        with cols[4]:
            status = doc.get("status", "")
            if status == "indexed":
                st.markdown(":green[已索引]")
            elif status == "failed":
                st.markdown(":red[失败]")
            else:
                st.write(status)
        with cols[5]:
            updated = doc.get("updated_at", "")
            st.caption(updated[:10] if updated else "-")
        with cols[6]:
            act_cols = st.columns(4)
            if act_cols[0].button("分块", key=f"view_{doc['document_id']}", help="查看分块"):
                st.session_state.view_chunks_doc_id = doc["document_id"]
            if act_cols[1].button("标签", key=f"tag_{doc['document_id']}", help="编辑标签"):
                st.session_state.edit_tags_doc_id = doc["document_id"]
            if act_cols[2].button("重建", key=f"reindex_{doc['document_id']}", help="重新索引"):
                try:
                    engine.delete_file(doc["document_id"])
                    summary = engine.add_files([doc["source_path"]], tags=doc.get("tags"))
                    st.session_state.last_ingest_summary = summary
                    st.session_state.retriever = build_retriever()
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            if act_cols[3].button("删除", key=f"del_{doc['document_id']}", help="删除文档"):
                st.session_state.confirm_delete_doc_id = doc["document_id"]
        st.divider()

    # ── 删除确认 ──
    if st.session_state.get("confirm_delete_doc_id"):
        doc_id = st.session_state.confirm_delete_doc_id
        doc_record = next((d for d in documents if d["document_id"] == doc_id), None)
        if doc_record:
            st.warning(f"确定删除文档「{doc_record.get('file_name', '')}」？此操作不可恢复。")
            confirm_cols = st.columns([1, 1, 4])
            if confirm_cols[0].button("确认删除", type="primary"):
                try:
                    engine.delete_file(doc_id)
                    st.session_state.retriever = build_retriever()
                except Exception as e:
                    st.error(str(e))
                st.session_state.confirm_delete_doc_id = None
                st.rerun()
            if confirm_cols[1].button("取消"):
                st.session_state.confirm_delete_doc_id = None
                st.rerun()

    # ── 标签编辑 ──
    if st.session_state.get("edit_tags_doc_id"):
        doc_id = st.session_state.edit_tags_doc_id
        doc_record = next((d for d in documents if d["document_id"] == doc_id), None)
        if doc_record:
            with st.container(border=True):
                st.markdown(f"**编辑标签：{doc_record.get('file_name', '')}**")
                current_tags = list(doc_record.get("tags", []))
                st.markdown(f"当前标签：{', '.join(current_tags) if current_tags else '无'}")
                new_tag = st.text_input("添加标签", key="edit_tag_input")
                tag_act_cols = st.columns([1, 1, 3])
                if tag_act_cols[0].button("添加", type="primary"):
                    if new_tag.strip() and new_tag.strip() not in current_tags:
                        current_tags.append(new_tag.strip())
                        doc_record["tags"] = current_tags
                        engine.manifest.upsert_document(doc_record)
                        st.rerun()
                if tag_act_cols[1].button("关闭"):
                    st.session_state.edit_tags_doc_id = None
                    st.rerun()
                if current_tags:
                    st.markdown("**已有标签（点击删除）：**")
                    tag_chips = st.columns(min(len(current_tags), 6))
                    for i, tag in enumerate(current_tags):
                        col_idx = i % 6
                        with tag_chips[col_idx]:
                            if st.button(f"x {tag}", key=f"del_tag_{tag}_{doc_id}"):
                                doc_record["tags"] = [t for t in current_tags if t != tag]
                                engine.manifest.upsert_document(doc_record)
                                st.rerun()

    # ── 查看分块 ──
    if st.session_state.get("view_chunks_doc_id"):
        doc_id = st.session_state.view_chunks_doc_id
        doc_record = next((d for d in documents if d["document_id"] == doc_id), None)
        if doc_record:
            with st.container(border=True):
                st.markdown(f"**分块列表：{doc_record.get('file_name', '')}**")
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
                if st.button("关闭分块查看"):
                    st.session_state.view_chunks_doc_id = None
                    st.rerun()


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
