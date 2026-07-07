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

## 开发环境要求

| 工具 | 版本 |
|------|------|
| Python | **3.12.3**（在 `.python-version` 中锁定） |
| pip | 最新版 |

> 建议使用 [pyenv](https://github.com/pyenv/pyenv) 管理 Python 版本：
> ```bash
> pyenv install 3.12.3
> pyenv local 3.12.3
> ```

## 快速开始（推荐）

克隆后一条命令搞定全部环境配置：

```bash
git clone <仓库地址> && cd co-thinker
bash setup.sh
```

脚本会自动：
1. ✅ 检查 Python 版本（>= 3.10）
2. ✅ 创建 `.venv` 虚拟环境
3. ✅ 从 `requirements.lock` 安装精确版本的所有依赖
4. ✅ 创建运行时目录（vectorstore、storage）
5. ✅ 验证配置接口正常

## 手动安装

```bash
# 1. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 2. 安装依赖（推荐用 lock 文件确保版本一致）
pip install -r requirements.lock
# 或仅安装版本下限:  pip install -r requirements.txt

# 3. 创建运行时目录
mkdir -p vectorstore storage
```

## 启动应用

```bash
source .venv/bin/activate

# 方式一（推荐）：通过 CLI 启动
python cli.py start

# 或指定端口
python cli.py start --port 8080

# 方式二：直接启动 Streamlit
streamlit run app/streamlit_app.py
```

> 首次使用前需创建 `.env`（从 `.env.example` 复制）并填写 `DEEPSEEK_API_KEY`。

### CLI 命令

```bash
python cli.py start     # 启动 Web 界面
python cli.py version    # 显示版本信息
python cli.py --help     # 查看所有命令
```

## 运行测试

```bash
source .venv/bin/activate
pytest tests/ -v
```

## 确保环境一致

同伴要获得跟你**一模一样的开发环境**，核心是这套文件：

```
co-thinker/
├── .python-version        # 🔒 锁定 Python 3.12.3
├── requirements.txt       # 📝 声明直接依赖（版本下限）
├── requirements.lock      # 🔒 冻结所有依赖的精确版本
├── setup.sh               # 🚀 一键安装脚本
├── .editorconfig          # 📐 跨编辑器代码风格统一
└── data/                  # 📁 知识库源文档（随 git 同步）
```

| 不可提交到 GitHub 的内容 | 解决方案 |
|---|---|
| `.venv/`（虚拟环境，~50MB） | `requirements.lock` + `setup.sh` 自动重建 |
| `.env`（含 API Key） | `.env.example` 模板，同伴自行复制填写 |
| `vectorstore/`、`storage/`（运行时生成） | `setup.sh` 自动创建空目录 |

**要点**：不要在 `.gitignore` 里排除 `data/`——知识库源文档是项目的一部分，应该随版本控制同步。

## 依赖管理

- **`requirements.txt`** — 手动维护，只写**直接依赖**和版本下限
- **`requirements.lock`** — 自动生成，冻结所有包（含传递依赖）的精确版本

当你新增/更新了依赖后：

```bash
source .venv/bin/activate
pip freeze > requirements.lock
git add requirements.lock && git commit -m "chore: update dependency lock"
```

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
