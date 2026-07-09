# Changelog

## [v0.0.11] - 2026-07-09

### ♻️ Refactor
- 应用 Clean Code 改进：`cli.py`、`core/file_catalog.py`、`core/generator.py`、`core/ingest.py`、`core/retriever.py` 代码精简与质量提升

### ✨ Features
- 新增设置页面（`/settings`），支持可视化修改模型、API Key、Base URL 等配置
- 聊天输入框新增模型选择器下拉菜单
- 侧边栏导航增加设置入口
- 文件管理页面增加全部索引/取消索引操作
- `DELETE /api/ingest` 新增清空所有索引端点
- WebSocket 聊天支持 `model` 参数，前端可指定模型覆盖默认配置

### 🐛 Bug Fixes
- 修复 `get_api_key()` 因 `WorkspaceRuntime` vs `ProjectContext` 类型不匹配导致的 AttributeError
  - `/api/config` 和 `/api/models` 接口恢复正常，模型列表可正确加载
- 修复 `POST /api/config` 500 错误：`WorkspaceRuntime` 缺少 `save_config()` 方法
- 修复 CORS 预检请求 400 错误：`allow_origins` 未包含 Web 前端端口 3001
- 修复 Vercel 部署时的 `nextConfig` 序列化错误

### 🎨 UI
- `ChatComposer.tsx` 重构：模型选择器、本地存储持久化、发送逻辑优化
- `ProjectSidebar.tsx` 新增设置导航项
- `globals.css`：暗色主题、自定义滚动条、设置页面样式统一
- `page.tsx`（文件管理）：批量操作按钮、状态管理优化

### 🔧 Maintenance
- `cli.py`：API 子进程自动检测开发环境并注入 `PYTHONPATH`
- 重构 `WorkspaceRuntime`：向后兼容委托属性体系补全

---

## [v0.0.10] - 2026-07-08

### ♻️ Refactor
- 移除 Streamlit 旧版前端（`app/streamlit_app.py`），统一为 FastAPI + Next.js 架构
- 业务逻辑从 `app/` 迁移至 `core/`（chat_engine, generator, parser 等）
- 重构 `api/deps.py` 使用 `ProjectContext` 统一管理资源
- 新增 `.co-thinker/` 项目配置系统（toml 格式），支持全局配置 `~/.co-thinkerc`

### 🐛 Bug Fixes
- 修复 `stream_generate` 返回 dict 但被当 tuple 解包，导致答案显示为重复 'content' 字符串的问题
- 修复 `install.sh` 安装后未自动刷新 PATH 的问题（改为 exec /bin/zsh）

### 🎨 UI
- 文件管理：新增文件勾选/全选，支持按目录筛选
- 会话管理：侧边栏显示消息数量、日期，支持删除
- 删除旧的 SourcePanel 和 ws.ts（旧版 WebSocket 实现）
- CSS 全局样式优化

---

## [v0.0.7] - 2026-07-08

### ♻️ Maintenance
- `.gitignore` 优化：添加 `.venv/`、`.deepseek/` 忽略规则，修正 `*.egg-info/` 通配
- `web/package-lock.json` 依赖锁文件更新

---

## [v0.0.6] - 2026-07-08

### 🐛 Bug Fixes
- 修复 Windows 终端 GBK 编码不支持 emoji 导致 `co-thinker start` 崩溃的问题
  - cli.py 中所有 emoji（🔌📂📄⚠️❌✅🎉⏳👋）替换为 ASCII 文本（`[PORT]` `[DIR]` `[OK]` `[WARN]` `[ERROR]` 等）
- 修复 Streamlit 首次启动弹出交互式邮箱提示导致 Windows 下卡住的问题
  - 添加 `--server.headless true` 命令行参数

### ✨ Features
- 新增 `install.ps1`：Windows PowerShell 一键安装脚本
- README 添加 Windows 安装说明

---

## [v0.0.5] - 2026-07-07

### 🐛 Bug Fixes
- 修复 `pyproject.toml` 缺少文档解析器依赖，导致 `install.sh` 安装后无法解析 .docx/.pdf/.pptx (python-docx / pymupdf / python-pptx)

---

## [v0.0.4] - 2026-07-07

### 🧪 Testing
- 新增 4 个损坏二进制文件解析测试
- `tests/test_parser.py`：PDF/DOCX/PPTX 解析测试

### 📦 Other
- **Parser**: PDF/DOCX/PPTX 添加 200MiB 大文件限制
- **Retriever**: CJK 字符范围扩展到 Extension A
- **Retriever**: `_iter_records` 改用 `hasattr()` 替代 `try/except`
- **Retriever**: BM25 预分词改用 `id()` 缓存避免突变 records 字典
- **Generator**: 系统提示改为中英双语
- **Deps**: 更新 lock 文件（parser 新依赖）

---

## [v0.0.3] - 2026-07-07

### 🐛 Bug Fixes
- 修复终端配置 DeepSeek API Key 后未生效的问题
  - `cli.py`：`start()` 启动 Streamlit 前调用 `load_dotenv()` 加载 `.env`
  - `config.py`：`_load_env_file()` 支持传入 `dotenv_path` 参数
  - `streamlit_app.py`：`init_session_state()` 双重保障加载 `.env`
- 修复 LLM 重试逻辑字符串匹配过于宽泛的问题
  - `generator.py`：`'model' + 'not found'` 改为组合条件检查
- 修复 `_split_text` 重叠窗口边界计算 bug
  - `ingest.py`：重叠窗口下界改为 `end - overlap_chars`

### 🔒 Security
- 修复 API Key 泄漏风险：新增 `EMBEDDING_API_KEY` 独立配置项
  - embedding 模块不再默认透传 `deepseek_api_key`

### ♻️ Refactor
- 移除 WebUI 中填写 API Key 的模块
  - 删除 `_save_env_api_key()` 函数
  - 删除 `render_settings()` 中的 API Key 输入框
  - 配置方式统一为终端 `co-thinker init` 或编辑 `.env`

### 🚀 Performance
- `chat_engine.save()` 添加 `_dirty` 脏标记，减少写盘频率

### 🧪 Testing
- 新增 4 个损坏二进制文件解析测试
- `tests/test_parser.py`：PDF/DOCX/PPTX 解析测试

### 📦 Other
- **Features**: `install.sh` 自动下载 GitHub Releases 最新 `.whl`
- **Config**: `_get_int` / `_get_float` 友好错误提示
- **Parser**: PDF/DOCX/PPTX 添加 200MiB 大文件限制
- **Retriever**: CJK 字符范围扩展到 Extension A
- **Retriever**: `_iter_records` 改用 `hasattr()` 替代 `try/except`
- **Retriever**: BM25 预分词改用 `id()` 缓存避免突变 records 字典
- **Generator**: 系统提示改为中英双语
- **Deps**: 更新 lock 文件（parser 新依赖）

---

## [v0.0.2] - 2026-07-07

### ✨ Features
- 新增 `co-thinker init` CLI 交互初始化命令
- 新增 `co-thinker start` CLI 启动入口
- GitHub Actions release workflow（`.github/workflows/release.yml`）
- `pyproject.toml` 构建配置，支持 `pip install` 安装

### 🧪 Testing
- 新增 `tests/conftest.py` 共享测试夹具
- 新增 `tests/test_ingest.py`、`tests/test_retriever.py` 测试用例
- 强化 `tests/test_generator.py` 测试覆盖

### 📝 Documentation
- `plans/` 目录：架构概述、模块设计、实现路线图等 10 份文档
- README 内容扩充

### 🔧 Maintenance
- 代码审查问题修复
- 调整 `.gitignore`，移除 `plans/` 排除规则

---

## [v0.0.1] - 2026-07-07

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

[v0.0.11]: https://github.com/player-Muteki/co-thinker/releases/tag/v0.0.11
[v0.0.10]: https://github.com/player-Muteki/co-thinker/releases/tag/v0.0.10
[v0.0.6]: https://github.com/player-Muteki/co-thinker/releases/tag/v0.0.6
[v0.0.5]: https://github.com/player-Muteki/co-thinker/releases/tag/v0.0.5
[v0.0.4]: https://github.com/player-Muteki/co-thinker/releases/tag/v0.0.4
[v0.0.3]: https://github.com/player-Muteki/co-thinker/releases/tag/v0.0.3
[v0.0.2]: https://github.com/player-Muteki/co-thinker/releases/tag/v0.0.2
[v0.0.1]: https://github.com/player-Muteki/co-thinker/releases/tag/v0.0.1
