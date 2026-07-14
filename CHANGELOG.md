# Changelog

## [v0.0.3] - 2026-07-14

### ✨ Features
- 改进 CLI banner 的 ASCII 月亮渲染（更高分辨率、灰度过渡）
- 修复 CLI banner 色彩主题（金色月亮 + 灰色副标题）

### 🐛 Bug Fixes
- 修复 `agent_workflow.py` 中 `_get_llm_model_name` 引用不存在的 `load_settings` 函数的问题

### 🧹 Chores
- 版本号更新至 v0.0.3

---

## [v0.0.1] - 2026-07-11

### ✨ Features
- 基于 RAG 的本地知识问答系统初始版本
- `app/chat_engine.py`：聊天引擎（会话管理、持久化）
- `app/generator.py`：LLM 调用封装（DeepSeek API）
- `app/ingest.py`：文档摄入（分块、向量化）
- `app/retriever.py`：检索模块（向量检索 + BM25 混合）
- `app/streamlit_app.py`：Streamlit WebUI
- `config.py`：配置管理（YAML + `.env` 双源加载）
- `cli.py`：CLI 命令入口

### 🧪 Testing
- `tests/test_config.py`：配置加载测试
- `tests/test_chat_engine.py`：聊天引擎测试
- `tests/test_generator.py`：生成器测试
- `tests/test_ingest.py`：摄入模块测试
- `tests/test_retriever.py`：检索模块测试
- 测试夹具：`docs/code_sample.py`、`docs/rag_intro.md`

### 📦 Dependencies
- `openai>=1.0.0`
- `streamlit>=1.30.0`
- `typer>=0.9.0`
- `python-dotenv>=1.0.0`
- `pyyaml>=6.0`

---

[v0.0.1]: https://github.com/player-Muteki/luna/releases/tag/v0.0.1
