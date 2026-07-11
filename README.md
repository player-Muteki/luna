# Lore

基于 RAG 的个人知识问答系统 — 本地部署，围绕工作目录下的文档进行知识问答。

## 项目简介

实现一个基于文本查询的智能问答系统，支持多格式文档批量导入构建知识库，利用语义理解与 RAG 技术精准检索并生成自然流畅的答案，支持多轮对话上下文管理。

与部署在本地的编码代理类似，Lore 也采取**本地部署模式**，围绕本地工作目录下的知识库源文件进行问答。采取 **CLI 启动 + WebUI 问答**的架构设计，兼顾终端用户的效率偏好与图形界面的交互体验。

## 功能模块

- **知识库构建** — 支持 md、txt、代码、PDF、DOCX、PPTX 等多格式文档批量导入
- **混合检索** — 向量检索 + BM25 混合排序（RRF 融合），精准定位相关信息
- **RAG 答案生成** — 大模型 + 检索上下文，支持多轮对话连贯性
- **多轮对话管理** — 会话持久化、历史上下文维护
- **可视化交互界面** — FastAPI 后端 + Next.js 前端双栏/三栏布局
- **模型选择** — 聊天输入框和设置页支持切换模型（自动拉取 API 可用模型列表）
- **配置管理** — Web 设置页可视化修改模型、API Key、Base URL 等配置
- **CLI 工具链** — 一键初始化、启动、扫描、问答

## 快速开始

### 安装

**Linux / macOS**

```bash
curl -fsSL 'https://cdn.jsdelivr.net/gh/player-Muteki/lore@main/install.sh' | bash
```

**Windows（PowerShell 管理员）**

```powershell
powershell -ExecutionPolicy Bypass -c "curl.exe -fsSL -o $env:TEMP\install.ps1 'https://cdn.jsdelivr.net/gh/player-Muteki/lore@main/install.ps1'; & $env:TEMP\install.ps1"
```

### 启动

```bash
mkdir my-kb && cd my-kb
lore init                    # 创建 .lore/ 配置目录
lore start                   # 启动 Web 界面
```

首次运行 `lore init` 时会提示填写 DeepSeek API Key，自动保存到 `~/.lorerc`。

## 项目结构

```
lore/
├── api/                    # FastAPI 后端服务
│   ├── server.py           # 应用入口与路由注册
│   ├── deps.py             # 依赖注入
│   └── routes/             # API 路由（chat / config / files / ingest / sessions）
├── core/                   # 核心业务逻辑
│   ├── chat_workflow.py    # 聊天工作流引擎
│   ├── generator.py        # 答案生成（LLM 调用）
│   ├── retriever.py        # 混合检索（向量 + BM25）
│   ├── ingest.py           # 文档导入与索引
│   ├── parser.py           # 文档解析（PDF/DOCX/PPTX/文本）
│   ├── file_catalog.py     # 文件目录索引管理
│   ├── runtime.py          # 运行时统一入口（WorkspaceRuntime）
│   └── project.py          # 项目上下文与配置管理
├── web/                    # Next.js 前端
│   ├── app/                # 页面路由
│   ├── components/         # UI 组件
│   └── lib/                # API 与 WebSocket 客户端
├── cli.py                  # CLI 入口（init / start / run / scan）
├── __version__.py          # 版本号
├── pyproject.toml          # 项目元数据与依赖声明
├── install.sh              # 一键安装脚本（Linux / macOS）
├── install.ps1             # 一键安装脚本（Windows）
└── README.md
```

> 运行时数据（`.lore/`）由程序自动生成，不纳入版本控制。

## 设计亮点

### 本地部署 · 知识主权

受当下编码代理（Coding Agent）本地部署模式的启发，Lore 采用**纯本地运行架构**。所有文档解析、向量索引、检索与推理均在用户自己的机器上完成，无需上传任何文件至云端。用户围绕**本地工作目录**下的源文件构建知识库，做到数据不出域、知识归自己。

### CLI 启航 · Web 远航

采取 **「CLI 启动 + WebUI 问答」** 的分层设计：

- **CLI 层**（`lore init / start / scan / run`）—— 一条命令完成初始化、启动服务、扫描文档、单轮问答
- **WebUI 层**（Next.js + FastAPI + WebSocket）—— 启动后浏览器接管交互：文件树管理、标签标注、检索详情可视化、多轮对话流式问答

二者共用同一套后端引擎，CLI 是入口，WebUI 是主场。

### 混合检索

向量检索（语义理解）+ BM25（关键词精确匹配）+ RRF（Reciprocal Rank Fusion）加权融合，兼顾语义泛化能力与精确命中能力。

### 指代消解与查询重写

内置查询预处理管道，自动检测短查询/指代词，结合对话历史进行上下文增强，确保多轮问答连贯性。

## 开发

```bash
git clone https://github.com/player-Muteki/lore.git
cd lore
bash setup.sh        # 创建虚拟环境 + 安装依赖
```

## License

MIT
