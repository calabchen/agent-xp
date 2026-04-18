# Agent XP

本项目是对以下 Agent 设计模式的手写实践：

- **ReAct**：推理 + 行动，通过思考和工具调用完成复杂任务
- **Plan&Execute**：先制定计划，再逐步执行
- **Reflection**：通过自我反思改进决策和执行

## 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (快速 Python 包管理工具)

## 安装

### 1. 克隆仓库

```bash
git clone <仓库地址>
cd agent-xp
```

### 2. 安装依赖

使用 `uv`：

```bash
uv sync
```

将根据 `pyproject.toml` 安装所有依赖到虚拟环境。

### 3. 配置环境变量

在项目根目录创建 `.env` 文件并配置 API 凭证：

```
DEEPSEEK_API_KEY=你的_deepseek_api_key
MODEL_NAME=deepseek-chat
```

**必需的环境变量：**
- `DEEPSEEK_API_KEY`：DeepSeek API 密钥（从 [DeepSeek 平台](https://platform.deepseek.com/) 获取）
- `MODEL_NAME`：LLM 模型名称（默认为 `deepseek-chat`）

## 运行方法

使用以下命令启动 ReAct Agent：

```bash
uv run python -m patterns.react.agent
```

然后与 Agent 交互：

```
USER: <你的问题或任务>
```

输入 `ctrl+c` 退出。

## 项目结构

```
agent-xp/
├── patterns/               # Agent 设计模式实现
│   ├── react/              # ReAct 模式
│   │   ├── agent.py        # ReAct Agent 实现
│   │   ├── system_prompt.md
│   │   └── summary_prompt.md
│   ├── plan_execute/       # Plan&Execute 模式
│   └── reflection/         # Reflection 模式
├── tools/                  # 工具实现
│   ├── base_tool.py        # 工具基类
│   └── xxx.py              # 自定义工具
├── utils/                  # 工具函数
│   └── message.py          # 消息处理
├── pyproject.toml          # 项目配置
├── .env                    # 环境变量（本地创建）
├── .gitignore              # Git 忽略文件
└── README.md               # 介绍文档
```

## 添加自定义工具

1. 在 `tools/` 目录创建新文件
2. 继承 `tools/base_tool.py` 中的 `BaseTool`
3. 实现 `run()` 方法
4. 工具将在 Agent 启动时自动注册

示例：

```python
from tools.base_tool import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "工具的描述"
    
    def run(self, query):
        # 实现工具逻辑
        return result
```