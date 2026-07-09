# Co-Thinker

基于 RAG 的大模型智能问答系统 — 面向特定领域的知识问答。

## 项目简介

实现一个基于文本查询的智能问答系统，支持多格式文档批量导入构建知识库，利用语义理解与 RAG 技术精准检索并生成自然流畅的答案，支持多轮对话上下文管理。

## 功能模块

- **知识库构建** — 支持 md、txt、代码、PDF、DOCX、PPTX 等多格式文档批量导入
- **混合检索** — 向量检索 + BM25 混合排序（RRF 融合），精准定位相关信息
- **RAG 答案生成** — 大模型 + 检索上下文，支持多轮对话连贯性
- **多轮对话管理** — 会话持久化、历史上下文维护
- **可视化交互界面** — FastAPI 后端 + Next.js 前端双栏/三栏布局
- **模型选择** — 聊天输入框和设置页支持切换模型（自动拉取 API 可用模型列表）
- **配置管理** — Web 设置页可视化修改模型、API Key、Base URL 等配置
- **CLI 工具链** — 一键初始化、启动、扫描、问答


## 安装

### Linux / macOS

一条命令安装 Co-Thinker：

**方式一（推荐 — jsDelivr CDN，全球加速）**

```bash
curl -fsSL 'https://cdn.jsdelivr.net/gh/player-Muteki/co-thinker@main/install.sh' | bash
```

**方式二（GitHub Raw，备选）**

```bash
curl -fsSL 'https://raw.githubusercontent.com/player-Muteki/co-thinker/refs/heads/main/install.sh' | bash
```

> macOS 默认的 bash 3.2 部分功能有限，推荐先升级 bash（`brew install bash`）或使用 zsh 执行。
>
> 注意：`curl` 命令中的 `-f`（`--fail`）确保在下载失败时不会将错误页面传给 bash。

### Windows

以管理员身份打开 PowerShell，执行以下任一命令：

**方式一（推荐 — jsDelivr CDN）：**

```powershell
powershell -ExecutionPolicy Bypass -c "curl.exe -fsSL -o $env:TEMP\install.ps1 'https://cdn.jsdelivr.net/gh/player-Muteki/co-thinker@main/install.ps1'; iex (Get-Content $env:TEMP\install.ps1 -Raw)"
```

**方式二（GitHub Raw 备选）：**

```powershell
powershell -ExecutionPolicy Bypass -c "curl.exe -fsSL -o $env:TEMP\install.ps1 'https://raw.githubusercontent.com/player-Muteki/co-thinker/refs/heads/main/install.ps1'; iex (Get-Content $env:TEMP\install.ps1 -Raw)"
```

### 启动

安装完成后，在新目录中初始化项目并启动：

```bash
mkdir my-kb && cd my-kb           # Linux / macOS
co-thinker init                    # 创建 .co-thinker/ 配置目录
co-thinker start                   # 启动 Web 界面
```

Windows PowerShell 请用 `;` 代替 `&&`：

```powershell
mkdir my-kb; cd my-kb
co-thinker init
co-thinker start
```

> 首次运行 `co-thinker init` 时会提示填写 DeepSeek API Key，自动保存到 `~/.co-thinkerc`。

## 项目结构

```
co-thinker/
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

> 运行时数据（`.co-thinker/`）由程序自动生成，不纳入版本控制。
