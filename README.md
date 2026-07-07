# Co-Thinker

基于 RAG 的大模型智能问答系统 — 面向特定领域的知识问答。

## 项目简介

实现一个基于文本查询的智能问答系统，支持多格式文档批量导入构建知识库，利用语义理解与 RAG 技术精准检索并生成自然流畅的答案，支持多轮对话上下文管理。

## 功能模块

- 知识库构建与管理（支持 md、txt、代码文件等格式批量导入、分类标注更新）
- 精准语义检索（意图解析 + 关键信息提取）
- RAG 答案生成（大模型 + 检索上下文，支持多轮对话连贯性）
- 多轮对话上下文记录
- 可视化交互界面


## 安装

一条命令安装 Co-Thinker：

```bash
curl -sSL https://raw.githubusercontent.com/player-Muteki/co-thinker/main/install.sh | bash
```

安装完成后，在新目录中初始化项目并启动：

```bash
mkdir my-kb && cd my-kb
co-thinker init       # 创建 .env 和运行时目录
co-thinker start      # 启动 Web 界面
```

> 首次使用前需编辑 `.env` 并填写 `DEEPSEEK_API_KEY`。

## 项目结构

```
co-thinker/
├── app/                    # 核心应用代码
│   ├── streamlit_app.py    # Web 界面
│   ├── chat_engine.py      # 对话引擎
│   ├── generator.py        # 答案生成
│   ├── retriever.py        # 文档检索
│   └── ingest.py           # 文档导入与索引
├── cli.py                  # CLI 入口（启动 Web / 版本信息）
├── __version__.py          # 版本号
├── data/                   # 知识库源文档（markdown/txt）
├── tests/                  # 测试
├── config.py               # 配置管理
├── requirements.txt        # 直接依赖声明
├── requirements.lock       # 精确版本锁
├── .python-version         # Python 版本锁定
├── .env.example            # 环境变量模板
├── setup.sh                # 一键环境设置
└── README.md
```

> `vectorstore/`（向量索引）和 `storage/`（运行时数据）由程序自动生成，不纳入版本控制。
