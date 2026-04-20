# my-learn-cli

用 LangChain + 通义千问复刻 CowAgent 的学习项目。

## 项目结构

```
my-learn-cli/
├── app.py               # 阶段1：终端纯聊天（DAY1-DAY2）
├── app_agent.py          # 阶段2+3：终端 Agent + 记忆持久化（DAY3）
├── app_web.py            # 阶段4：Web 界面 + SSE 流式（DAY1+DAY3）
├── tools.py              # 工具定义（bash/read/ls）
├── memory.py             # SQLite 对话历史持久化
├── chat.html             # Web 前端页面
├── config.json           # 配置文件（模型 + API Key）
└── requirements.txt      # 依赖
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

创建 `config.json`：

```json
{
  "model": "qwen-plus",
  "dashscope_api_key": "你的通义千问API Key"
}
```

### 3. 运行

三种模式可选：

```bash
# 阶段1：终端纯聊天（最简单）
python app.py

# 阶段2+3：终端 Agent 模式（带工具 + 记忆持久化）
python app_agent.py

# 阶段4：Web 界面（浏览器访问 http://localhost:8000）
uvicorn app_web:app --reload --port 8000
```

## 与 CowAgent 的对应关系

| my-learn-cli | CowAgent | 说明 |
|---|---|---|
| `app.py` | `app.py` + `channel/` + `bridge/` | 入口 + 通道 + 模型调用 |
| `app_agent.py` | `bridge/agent_bridge.py` + `agent/protocol/` | Agent 模式 |
| `app_web.py` | `channel/web/web_channel.py` | Web 服务 + SSE |
| `tools.py` | `agent/tools/` | 工具系统 |
| `memory.py` | `agent/memory/conversation_store.py` | 对话持久化 |
| `chat.html` | `channel/web/chat.html` | 前端页面 |
| `config.json` | `config.json` + `config.py` | 配置管理 |

## 阶段说明

### 阶段1：终端纯聊天（app.py）
- 对应 DAY1-DAY2 学习内容
- LangChain ChatTongyi 替代 Bridge + BotFactory + DashscopeBot
- 流式输出（打字机效果）
- 内存中的对话历史

### 阶段2：Agent + 工具（app_agent.py + tools.py）
- 对应 DAY3 学习内容
- @tool 装饰器替代 BaseTool 基类
- AgentExecutor 替代 Agent.run_stream() 循环
- 三个工具：bash_run、read_file、list_directory

### 阶段3：记忆持久化（memory.py）
- 对应 CowAgent 的 ConversationStore
- SQLite 存储对话历史
- 启动时可恢复历史会话

### 阶段4：Web 界面（app_web.py + chat.html）
- 对应 CowAgent 的 WebChannel
- FastAPI 替代 web.py
- SSE 流式推送
- 前端聊天界面

## 技术栈

- Python 3.11
- LangChain（模型调用 + Agent + 工具）
- 通义千问 / DashScope（AI 模型）
- FastAPI + Uvicorn（Web 服务）
- SQLite（对话持久化）
