# Luna

基于 RAG 的个人知识问答系统 — 本地部署，围绕工作目录下的文档进行知识问答。

## 项目简介

实现一个基于文本查询的智能问答系统，支持多格式文档批量导入构建知识库，利用语义理解与 RAG 技术精准检索并生成自然流畅的答案，支持多轮对话上下文管理。

与部署在本地的编码代理类似，Luna 也采取**本地部署模式**，围绕本地工作目录下的知识库源文件进行问答。采取 **CLI 启动 + WebUI 问答**的架构设计，兼顾终端用户的效率偏好与图形界面的交互体验。

## 功能模块

- **知识库构建** — 支持 md、txt、代码、PDF、DOCX、PPTX 等多格式文档批量导入
- **混合检索** — 向量检索 + BM25 混合排序（RRF 融合），精准定位相关信息
- **RAG 答案生成** — 大模型 + 检索上下文，支持多轮对话连贯性
- **多轮对话管理** — 会话持久化、历史上下文维护
- **可视化交互界面** — FastAPI 后端 + Next.js 前端双栏/三栏布局
- **模型选择** — 聊天输入框和设置页支持切换模型（自动拉取 API 可用模型列表）
- **配置管理** — Web 设置页可视化修改模型、API Key、Base URL 等配置
- **CLI 工具链** — 一键初始化、启动、扫描、问答（`luna` / `Luna`）
- **Agent 智能体** — 知识库自动化管理：计划、审批、执行闭环（CLI + API + WebUI）
- **Rust 工具运行时** — Rust JSON-RPC 策略引擎，Python KnowledgeToolset 执行层

## 快速开始

### 安装

**Linux / macOS**

```bash
curl -fsSL 'https://cdn.jsdelivr.net/gh/player-Muteki/luna@main/install.sh' | bash
```

**Windows（PowerShell 管理员）**

```powershell
powershell -ExecutionPolicy Bypass -c "curl.exe -fsSL -o $env:TEMP\install.ps1 'https://cdn.jsdelivr.net/gh/player-Muteki/luna@main/install.ps1'; & $env:TEMP\install.ps1"
```

### 启动

```bash
mkdir my-kb && cd my-kb
luna init                    # 创建 .luna/ 配置目录
luna start                   # 启动 Web 界面
```

> 命令不区分大小写：`luna` 和 `Luna` 均可使用。

首次运行 `luna init` 时会提示填写 DeepSeek API Key，自动保存到 `~/.lunarc`。

## Agent 智能体

Luna 内置知识库 Agent，可自动化执行知识库管理任务。

### CLI 使用

```bash
# 只读查询（获取知识库统计）
luna agent run "检查知识库状态"

# 自动执行低风险变更
luna agent run "索引新文件" --yes

# 计划模式（只读预览，不执行变更）
luna agent run "重建索引" --plan

# 执行后生成 LLM 总结
luna agent run "检查知识库状态" --respond

# JSONL 格式输出（适合管道处理）
luna agent run "检查知识库状态" --json

# 审批管理
luna agent approvals            # 列出待审批
luna agent approve appr_xxx     # 批准并执行
luna agent reject appr_xxx      # 拒绝

# 会话历史
luna agent sessions             # 列出会话
luna agent show ags_xxx         # 查看会话事件
```

### 工具集

| 工具 | 类别 | 说明 |
|------|------|------|
| `kb_get_stats` | 只读 | 知识库索引统计 |
| `kb_list_files` | 只读 | 工作区文件列表 |
| `kb_list_documents` | 只读 | 已索引文档列表 |
| `kb_search` | 只读 | 知识库内容搜索 |
| `kb_index_files` | 变更 | 索引指定文件 |
| `kb_rebuild_index` | 变更 | 全量重建索引 |
| `kb_delete_document` | 变更 | 删除文档 |
| `kb_update_tags` | 变更 | 更新文档标签 |
| `kb_clear_index` | 危险 | 清空索引（默认禁止） |

### 三种模式

- **默认模式** — 执行工具 → 变更需审批
- **计划模式** (`--plan`) — 只读预览计划，不变更
- **目标模式** (`--goal`) — 预留扩展

### 审批策略

| 策略 | 说明 |
|------|------|
| `ask`（默认） | 变更工具等待人工审批 |
| `auto_safe_mutation` (`--yes`) | 自动执行 `kb_index_files` / `kb_update_tags` |

危险工具（`kb_clear_index`、`shell_exec`）始终拒绝，不可审批。

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agent/run` | 运行 Agent（SSE 流式事件） |
| GET | `/api/agent/approvals` | 审批列表 |
| POST | `/api/agent/approve/{id}` | 批准并执行 |
| POST | `/api/agent/reject/{id}` | 拒绝 |
| GET | `/api/agent/sessions` | 会话列表 |
| GET | `/api/agent/sessions/{id}` | 会话事件详情 |

## 项目结构

```
luna/
├── api/                    # FastAPI 后端
│   ├── server.py           # 应用入口与路由注册
│   ├── deps.py             # 依赖注入
│   └── routes/             # API 路由
│       ├── agent.py        # Agent SSE/REST 端点
│       ├── chat.py         # WebSocket 流式问答
│       ├── config.py       # 配置管理
│       ├── files.py        # 文件列表
│       ├── ingest.py       # 索引管理
│       └── sessions.py     # 聊天会话
├── core/                   # 核心业务逻辑
│   ├── agent_approval.py   # 审批持久化存储
│   ├── agent_contracts.py  # 工具合约定义
│   ├── agent_events.py     # 事件协议模型
│   ├── agent_executor.py   # 策略门控执行器
│   ├── agent_modes.py      # Agent 模式与审批策略
│   ├── agent_plan_store.py # 计划持久化
│   ├── agent_planner.py    # 规则匹配规划器
│   ├── agent_runtime.py    # Rust runtime Python 适配器
│   ├── agent_session.py    # 会话事件日志
│   ├── agent_tools.py      # 知识库工具集
│   ├── agent_workflow.py   # Agent 工作流编排
│   ├── chat_engine.py      # 对话引擎
│   ├── chat_workflow.py    # 聊天工作流
│   ├── generator.py        # LLM 答案生成
│   ├── retriever.py        # 混合检索（向量 + BM25）
│   ├── ingest.py           # 文档导入与索引
│   ├── parser.py           # 文档解析
│   ├── file_catalog.py     # 文件目录管理
│   ├── runtime.py          # WorkspaceRuntime 统一入口
│   └── project.py          # 项目配置管理
├── crates/                 # Rust 工作区
│   └── luna-agent-runtime/ # Agent 工具策略引擎
│       ├── src/
│       │   ├── main.rs     # stdio JSON-RPC 循环
│       │   ├── protocol.rs # 请求/响应类型
│       │   ├── policy.rs   # 工具策略评估
│       │   ├── tools.rs    # 工具注册表与 schema
│       │   └── jsonrpc.rs  # JSON-RPC 2.0 协议
│       └── Cargo.toml
├── web/                    # Next.js 前端
│   ├── app/                # 页面路由
│   │   ├── (workspace)/
│   │   │   ├── agent/      # Agent 面板
│   │   │   ├── chat/       # 对话页
│   │   │   ├── files/      # 文件管理
│   │   │   └── settings/   # 设置
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/         # UI 组件
│   │   └── workspace/
│   │       └── ProjectSidebar.tsx
│   └── lib/
│       └── api.ts          # API 客户端
├── cli.py                  # CLI 入口
├── __version__.py          # 版本号
├── pyproject.toml           # 项目元数据
├── Cargo.toml              # Rust 工作区
├── install.sh              # Linux/macOS 安装脚本
├── install.ps1             # Windows 安装脚本
├── LICENSE                 # MIT 许可证
└── README.md
```

> 运行时数据（`.luna/`）由程序自动生成，不纳入版本控制。

## 开发

```bash
git clone https://github.com/player-Muteki/luna.git
cd luna
bash setup.sh                # 创建虚拟环境 + 安装 Python 依赖
cargo build --workspace      # 编译 Rust agent runtime
```

## License

[MIT](LICENSE)
