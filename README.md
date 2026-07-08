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
- **CLI 工具链** — 一键初始化、启动、扫描、问答


## 安装

### Linux

一条命令安装 Co-Thinker：

```bash
curl -sSL https://api.github.com/repos/player-Muteki/co-thinker/contents/install.sh | python3 -c "import json,sys; print(json.load(sys.stdin)['content'])" | base64 -d > /tmp/co-thinker-install.sh && bash /tmp/co-thinker-install.sh
```

> 通过 GitHub API 获取脚本，避免 raw.githubusercontent.com CDN 限流问题。

### macOS

> macOS 默认的 bash 3.2 对 Unicode 支持有限，请使用以下命令（通过 `refs/heads/main` 路径绕过 CDN 缓存）：

```bash
bash <(curl -sSL 'https://raw.githubusercontent.com/player-Muteki/co-thinker/refs/heads/main/install.sh')
```

### Windows

以管理员身份打开 PowerShell，执行以下任一命令：

**方式一（推荐 - 使用 curl.exe）：**

```powershell
powershell -ExecutionPolicy Bypass -c "curl.exe -sSL -o $env:TEMP\install.ps1 https://raw.githubusercontent.com/player-Muteki/co-thinker/main/install.ps1; iex (Get-Content $env:TEMP\install.ps1 -Raw)"
```

**方式二（使用 irm - 先下载再执行）：**

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/player-Muteki/co-thinker/main/install.ps1 -OutFile $env:TEMP\co-thinker-install.ps1; iex (Get-Content $env:TEMP\co-thinker-install.ps1 -Raw)"
```

或手动下载后执行：

```powershell
curl.exe -sSL -o install.ps1 https://raw.githubusercontent.com/player-Muteki/co-thinker/main/install.ps1
powershell -ExecutionPolicy Bypass -File install.ps1
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

> 首次使用前需编辑 `.env` 并填写 `DEEPSEEK_API_KEY`。

## 项目结构

```
co-thinker/
├── api/                    # FastAPI 后端服务
│   ├── server.py           # 应用入口与路由注册
│   ├── deps.py             # 依赖注入
│   └── routes/             # API 路由（chat / files / ingest / sessions）
├── core/                   # 核心业务逻辑
│   ├── chat_engine.py      # 对话引擎
│   ├── generator.py        # 答案生成（LLM 调用）
│   ├── retriever.py        # 混合检索（向量 + BM25）
│   ├── ingest.py           # 文档导入与索引
│   ├── parser.py           # 文档解析（PDF/DOCX/PPTX/文本）
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
