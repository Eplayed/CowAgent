# DAY2 学习笔记 — Bridge 桥接层深入

## 学完后应该能回答的问题

- [x] Bridge 的核心职责是什么？（根据模型名路由到对应 Bot）
- [x] Bridge 怎么知道用哪个 Bot？（读 config.json 的 model 字段，前缀匹配）
- [x] get_bot() 的懒加载是什么意思？（第一次调用才创建，之后复用）
- [x] BotFactory 为什么用延迟导入？（不用的模型不加载，节省资源）
- [x] DashscopeBot.reply() 做了哪几步？（管理历史 → 调 API → 保存回复）
- [x] AI 怎么"记住"之前的对话？（session.messages 完整对话历史每次都发给 API）
- [x] API 调用失败怎么处理？（自动重试最多 2 次）
- [x] Context 和 Reply 的数据结构是什么？（type + content + kwargs）
- [x] 普通模式和 Agent 模式有什么区别？（一问一答 vs 可思考+用工具）
- [x] AgentBridge.agent_reply() 做了哪些事？（获取 Agent → 事件处理 → run_stream → 持久化）
- [x] Agent 初始化时做了什么？（加载工具/技能/记忆 → 构建 prompt → 创建实例）
- [x] 提示词是运行时构建还是初始化时构建？（初始化时构建好，运行时复用）
- [x] 记忆系统和技能系统是怎么接入 Agent 的？（记忆=注册为工具，技能=注入 prompt）

### 全景图（学习进度标记）

```
浏览器输入 "你好"
    │
    ▼
POST /message                                          ✅ DAY1 已学
    │
    ▼
WebChannel.post_message()     ← 解析请求，构建 Context   ✅ DAY1 已学
    │
    ▼
produce()                     ← 消息入队（生产者）        ✅ DAY1 已学
    │
    ▼
consume()                     ← 后台循环取消息（消费者）   ✅ DAY1 已学
    │
    ▼
_handle()                     ← 总调度                   ✅ DAY1 已学
    │
    ├─→ _generate_reply()     ← 生成回复                 ✅ DAY1 已学（流程）
    │       │
    │       ├─→ 插件链处理（可拦截）                       ❌ 未学（plugins/）
    │       │     ├─ ON_RECEIVE_MESSAGE                   ❌ 未学
    │       │     ├─ ON_HANDLE_CONTEXT                    ❌ 未学
    │       │     ├─ ON_DECORATE_REPLY                    ❌ 未学
    │       │     └─ ON_SEND_REPLY                        ❌ 未学
    │       │
    │       └─→ build_reply_content()                     ✅ DAY2 已学
    │               │
    │               ├─→ Bridge 路由                       ✅ DAY2 已学
    │               │     ├─ 模型前缀匹配                  ✅ DAY2 已学
    │               │     ├─ BotFactory 工厂创建           ✅ DAY2 已学
    │               │     └─ get_bot() 懒加载              ✅ DAY2 已学
    │               │
    │               ├─→ 普通模式: DashscopeBot.reply()    ✅ DAY2 已学
    │               │     ├─ session.messages 对话历史     ✅ DAY2 已学
    │               │     ├─ reply_text() 调 API          ✅ DAY2 已学
    │               │     └─ 失败重试机制                   ✅ DAY2 已学
    │               │
    │               └─→ Agent 模式: AgentBridge           ✅ DAY2 已学（入口流程）
    │                     ├─ AgentInitializer 初始化       ✅ DAY2 已学（流程概览）
    │                     ├─ Agent.run_stream() 核心循环   ❌ 未学（agent/protocol/）
    │                     │     ├─ think（思考）            ❌ 未学
    │                     │     ├─ act（调用工具）           ❌ 未学
    │                     │     └─ observe（观察结果）       ❌ 未学
    │                     ├─ 工具系统                       ❌ 未学（agent/tools/）
    │                     │     ├─ bash/edit/read/write    ❌ 未学
    │                     │     ├─ browser/web_search      ❌ 未学
    │                     │     ├─ memory/vision           ❌ 未学
    │                     │     └─ scheduler               ❌ 未学
    │                     ├─ 记忆系统                       ❌ 未学（agent/memory/）
    │                     │     ├─ 对话历史存储              ❌ 未学
    │                     │     ├─ 向量嵌入/检索            ❌ 未学
    │                     │     └─ 摘要生成                 ❌ 未学
    │                     ├─ 技能系统                       ❌ 未学（agent/skills/）
    │                     └─ 提示词构建                     ❌ 未学（agent/prompt/）
    │
    ├─→ _decorate_reply()     ← 加前缀后缀               ✅ DAY1 已学（知道作用）
    │
    └─→ _send_reply()         ← 发送回复                 ✅ DAY1 已学（知道作用）
            │
            └─→ WebChannel.send() → SSE 推送给浏览器      ✅ DAY1 已学
```

### 学习进度统计

- ✅ 已学：通道层（收发/排队）、Bridge 路由、Bot 调用、数据结构
- ❌ 未学：插件系统、Agent 核心循环、工具系统、记忆系统、技能系统、提示词构建
## 学习路径回顾

```
DAY1: 入口层 + 通道层（消息怎么收发和排队）
  app.py → ChannelManager → WebChannel → post_message → produce/consume → _handle

DAY2: 桥接层（消息怎么到达 AI 模型）
  _handle → _generate_reply → build_reply_content → Bridge → Bot/Agent → AI API
```

DAY1 学到 `build_reply_content()` 就停了，今天从这里继续往下挖。

## 一、Bridge 层整体架构

### 文件结构

```
bridge/
├── bridge.py              # Bridge 主类 — 模型路由器
├── agent_bridge.py        # AgentBridge — Agent 模式的入口
├── agent_event_handler.py # Agent 事件处理（日志、SSE 推送）
├── agent_initializer.py   # Agent 初始化（工具、记忆、提示词）
├── context.py             # Context — 消息上下文数据结构
└── reply.py               # Reply — 回复数据结构
```

### 调用关系

```
Channel.build_reply_content()
    │
    ├─ agent=false → Bridge.fetch_reply_content()
    │                    │
    │                    └─→ get_bot("chat").reply()
    │                           │
    │                           └─→ DashscopeBot.reply() → 通义千问 API
    │
    └─ agent=true  → Bridge.fetch_agent_reply()
                         │
                         └─→ AgentBridge.agent_reply()
                                │
                                └─→ Agent.run_stream() → 思考/工具调用/生成回复
```

## 二、Bridge 主类 — 模型路由器

### 核心职责

Bridge 做的事就一件：根据配置中的模型名，决定用哪个 Bot 类来调 API。

### 路由逻辑（__init__）

Bridge 初始化时读取 `config.json` 中的 `model` 字段，通过前缀匹配确定 bot 类型：

| 模型名前缀 | bot 类型 | 对应 Bot 类 |
|---|---|---|
| `qwen` / `qwq` / `qvq` | QWEN_DASHSCOPE | DashscopeBot |
| `gpt` | OPENAI | ChatGPTBot |
| `claude` | CLAUDEAPI | ClaudeAPIBot |
| `gemini` | GEMINI | GoogleGeminiBot |
| `glm` | ZHIPU_AI | ZHIPUAIBot |
| `deepseek` | DEEPSEEK | DeepSeekBot |
| `moonshot` / `kimi` | MOONSHOT | MoonshotBot |
| `doubao` | DOUBAO | DoubaoBot |
| `minimax` | MiniMax | MinimaxBot |

当前配置 `model: "qwen3.6-plus"` 以 `qwen` 开头，所以路由到 `QWEN_DASHSCOPE` → `DashscopeBot`。

### 四个 fetch 方法

```python
fetch_reply_content(query, context)   # 调 AI 模型生成文字回复
fetch_agent_reply(query, context)     # Agent 模式（思考+工具调用）
fetch_voice_to_text(voiceFile)        # 语音转文字
fetch_text_to_voice(text)             # 文字转语音
```

### get_bot() — 懒加载

Bot 实例不是初始化时创建的，而是第一次调用时才创建（懒加载）：

```python
def get_bot(self, typename):
    if self.bots.get(typename) is None:
        # 第一次调用才创建，之后复用
        self.bots[typename] = create_bot(self.btype[typename])
    return self.bots[typename]
```

## 三、BotFactory — 工厂模式创建 Bot

`models/bot_factory.py` 的 `create_bot()` 是一个大的 if-elif 链，根据 bot_type 创建对应的 Bot 实例：

```python
def create_bot(bot_type):
    if bot_type == const.QWEN_DASHSCOPE:
        from models.dashscope.dashscope_bot import DashscopeBot
        return DashscopeBot()
    elif bot_type == const.OPENAI:
        from models.chatgpt.chat_gpt_bot import ChatGPTBot
        return ChatGPTBot()
    elif bot_type == const.CLAUDEAPI:
        from models.claudeapi.claude_api_bot import ClaudeAPIBot
        return ClaudeAPIBot()
    # ... 十几个模型
```

注意：每个 Bot 的 import 都在 if 分支内部（延迟导入），这样不用的模型不会被加载，节省启动时间和内存。

## 四、DashscopeBot — 通义千问的实际调用

这是当前配置使用的 Bot，看看它怎么调 API。

### reply() — 入口方法

```python
def reply(self, query, context=None):
    # 1. 检查特殊命令
    if query in ["#清除记忆"]:
        self.sessions.clear_session(session_id)
        return Reply(ReplyType.INFO, "记忆已清除")

    # 2. 把用户消息加入会话历史
    session = self.sessions.session_query(query, session_id)

    # 3. 调用 API 获取回复
    reply_content = self.reply_text(session)

    # 4. 把 AI 回复也加入会话历史（维护上下文）
    self.sessions.session_reply(reply_content["content"], session_id)

    # 5. 返回 Reply 对象
    return Reply(ReplyType.TEXT, reply_content["content"])
```

### reply_text() — 实际调 API

```python
def reply_text(self, session, retry_count=0):
    dashscope.api_key = self.api_key
    model = "qwen3.6-plus"

    # 调用通义千问 API
    response = self.client.call(
        model,
        messages=session.messages,  # 完整的对话历史
        result_format="message"
    )

    if response.status_code == 200:
        content = response.output.choices[0].message.content
        return {"content": content, "completion_tokens": ..., "total_tokens": ...}
    else:
        # 失败重试（最多 2 次）
        if retry_count < 2:
            return self.reply_text(session, retry_count + 1)
        return {"content": "我现在有点累了，等会再来吧", "completion_tokens": 0}
```

关键点：
- `session.messages` 是完整的对话历史（包含之前的问答），这就是 AI 能"记住"上下文的原因
- 失败会自动重试 2 次
- API 调用用的是 dashscope SDK（阿里云的通义千问 SDK）

## 五、Context 和 Reply — 数据结构

### Context（消息上下文）

```python
class Context:
    type: ContextType    # 消息类型（TEXT/VOICE/IMAGE/...）
    content: str         # 消息内容
    kwargs: dict         # 附加信息（session_id, receiver, request_id, on_event...）
```

Context 像一个字典，可以用 `context["session_id"]` 读写。它贯穿整个消息链路，从 `post_message()` 创建，一直传到 `_send_reply()`。

### ContextType（消息类型枚举）

```python
TEXT = 1           # 文本消息
VOICE = 2          # 语音消息
IMAGE = 3          # 图片消息
FILE = 4           # 文件
VIDEO = 5          # 视频
IMAGE_CREATE = 10  # 画图命令（如"画一只猫"）
FUNCTION = 22      # 函数调用
```

### Reply（回复）

```python
class Reply:
    type: ReplyType   # 回复类型
    content: str      # 回复内容
```

### ReplyType（回复类型枚举）

```python
TEXT = 1        # 文本回复
VOICE = 2       # 语音文件
IMAGE = 3       # 图片文件
IMAGE_URL = 4   # 图片链接
ERROR = 10      # 错误信息
INFO = 9        # 提示信息（如"记忆已清除"）
```

## 六、Agent 模式 — 两条路径的区别

### 普通模式（agent=false）

```
用户: "今天天气怎么样"
  → DashscopeBot.reply() → 直接调通义千问 API → 返回文字回复
```

简单直接，一问一答，AI 只能回复文字。

### Agent 模式（agent=true，当前配置）

```
用户: "帮我查一下北京天气"
  → AgentBridge.agent_reply()
    → Agent.run_stream()
      → 思考: "用户想查天气，我需要用搜索工具"
      → 调用工具: web_search("北京天气")
      → 观察结果: "北京今天晴，25°C"
      → 思考: "我已经拿到信息了，可以回复了"
      → 生成回复: "北京今天天气晴朗，气温25°C..."
```

Agent 模式下 AI 可以"思考"和"使用工具"，不只是回复文字。

### AgentBridge.agent_reply() 做了什么

1. 根据 session_id 获取/创建 Agent 实例
2. 创建事件处理器（用于 SSE 流式推送）
3. 调用 `agent.run_stream()` 执行 Agent 循环
4. 持久化对话历史到数据库
5. 返回 Reply

### Agent 初始化流程（AgentInitializer）

```
initialize_agent()
  → 设置工作目录（~/cow）
  → 迁移 API Key 到环境变量
  → 初始化记忆系统（向量存储 + 对话历史）
  → 加载工具（bash/edit/read/write/browser/memory/scheduler...）
  → 初始化定时任务调度器
  → 加载技能（Skills）
  → 构建系统提示词（system prompt）
  → 创建 Agent 实例
  → 恢复历史对话记录
```

## 七、完整调用链（从浏览器到 AI API）

把 DAY1 和 DAY2 串起来，完整链路：

```
浏览器输入 "你好"
    │
    ▼
POST /message → MessageHandler
    │
    ▼
WebChannel.post_message()
    ├─ 解析请求参数
    ├─ _compose_context() 构建 Context（安检过滤）
    ├─ produce(context) 消息入队
    └─ 返回 request_id
    │
    ▼
consume() 后台取消息
    │
    ▼
_handle(context) 总调度
    │
    ▼
_generate_reply(context)
    ├─ PluginManager 插件链（可拦截）
    └─ build_reply_content()
        │
        ▼
    Bridge（路由器）
        │
        ├─ agent=false → fetch_reply_content()
        │                   │
        │                   ▼
        │               get_bot("chat") → DashscopeBot
        │                   │
        │                   ▼
        │               reply() → reply_text()
        │                   │
        │                   ▼
        │               dashscope SDK → 通义千问 API
        │                   │
        │                   ▼
        │               返回 Reply(TEXT, "你好！...")
        │
        └─ agent=true  → fetch_agent_reply()
                            │
                            ▼
                        AgentBridge.agent_reply()
                            │
                            ▼
                        Agent.run_stream()
                            ├─ 思考（调 AI）
                            ├─ 使用工具（可选）
                            └─ 生成回复
                            │
                            ▼
                        返回 Reply(TEXT, "你好！...")
    │
    ▼
_decorate_reply() 加前缀后缀
    │
    ▼
_send_reply() → WebChannel.send() → SSE 推送给浏览器
```

## 八、关键设计总结

| 设计点 | 怎么做的 | 为什么 |
|---|---|---|
| 模型路由 | Bridge 根据模型名前缀匹配 bot 类型 | 支持十几种模型，切换只改配置 |
| 懒加载 | Bot 第一次调用时才创建 | 不用的模型不占资源 |
| 延迟导入 | import 写在 if 分支内 | 启动快，不加载无关模块 |
| 会话管理 | session.messages 维护对话历史 | AI 能记住上下文 |
| 失败重试 | reply_text 最多重试 2 次 | 网络抖动不影响用户体验 |
| 双模式 | 普通模式直接调 API，Agent 模式可用工具 | 简单场景快速响应，复杂场景智能处理 |
| 单例 | Bridge 用 @singleton 装饰器 | 全局只有一个路由器，避免重复初始化 |

## 九、如果用 LangChain 实现 Agent 模式

CowAgent 的 Agent 模式手写了初始化、循环、工具调用、记忆、技能等全部逻辑。用 LangChain 的话，可以大幅简化。

### 完整对比：CowAgent vs LangChain 实现

**CowAgent 手写方式（简化版）：**

```python
# 1. 初始化（agent_initializer.py）
tools = [BashTool(), EditTool(), ReadTool(), WebSearchTool(), MemorySearchTool()]
system_prompt = PromptBuilder().build(tools=tools, skills=skills, memory=memory)
agent = Agent(model=DashscopeBot(), tools=tools, system_prompt=system_prompt)

# 2. 运行（agent.run_stream）
def run_stream(self, user_message):
    self.messages.append({"role": "user", "content": user_message})
    while steps < max_steps:
        response = self.model.call(self.messages)       # 调 AI
        if response.has_tool_call:                       # AI 想用工具？
            result = self.execute_tool(response.tool_call)  # 执行工具
            self.messages.append(tool_result)             # 结果加入历史
        else:
            return response.content                       # 最终回复
```

**LangChain 方式：**

```python
from langchain_community.chat_models import ChatTongyi
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory

# 1. 模型（替代 Bridge + BotFactory + DashscopeBot）
llm = ChatTongyi(model="qwen-plus", dashscope_api_key="sk-xxx")

# 2. 工具（替代 agent/tools/ 下的所有工具类）
@tool
def web_search(query: str) -> str:
    """搜索互联网获取实时信息"""
    # 调用搜索 API
    return search_api(query)

@tool
def bash(command: str) -> str:
    """执行 shell 命令"""
    return subprocess.run(command, capture_output=True, text=True).stdout

@tool
def read_file(path: str) -> str:
    """读取文件内容"""
    return open(path).read()

tools = [web_search, bash, read_file]

# 3. 提示词（替代 agent/prompt/builder.py）
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个AI助手，可以使用工具帮助用户完成任务。"),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# 4. 记忆（替代 agent/memory/）
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True
)

# 5. 创建 Agent（替代 AgentBridge + AgentInitializer + Agent 类）
agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    max_iterations=20,   # 对应 agent_max_steps
    verbose=True
)

# 6. 运行（替代 agent.run_stream）
result = executor.invoke({"input": "帮我查一下北京天气"})
print(result["output"])
```

### 逐模块对应关系

| CowAgent 模块 | 代码位置 | LangChain 替代 | 说明 |
|---|---|---|---|
| Bridge 路由 | `bridge/bridge.py` | `ChatTongyi()` / `ChatOpenAI()` | 一行代码切换模型 |
| BotFactory | `models/bot_factory.py` | 不需要 | LangChain 内置模型适配 |
| DashscopeBot | `models/dashscope/` | `ChatTongyi` | 通义千问直接支持 |
| Agent 循环 | `agent/protocol/agent.py` | `AgentExecutor` | 自动处理 think→act→observe |
| 工具注册 | `agent/tools/base_tool.py` | `@tool` 装饰器 | 几行代码定义一个工具 |
| 工具管理 | `agent/tools/tool_manager.py` | `tools=[]` 列表传入 | 不需要管理器 |
| 记忆系统 | `agent/memory/` | `ConversationBufferMemory` | 自动管理对话历史 |
| 对话历史存储 | `agent/memory/conversation_store.py` | `RedisChatMessageHistory` 等 | 可选持久化后端 |
| 向量检索记忆 | `agent/memory/embedding.py` | `VectorStoreRetrieverMemory` | 语义搜索历史 |
| 摘要记忆 | `agent/memory/summarizer.py` | `ConversationSummaryMemory` | 自动压缩长对话 |
| 技能系统 | `agent/skills/` | 动态拼接 `SystemMessage` | 没有直接对应，最接近的做法见下方 |
| 提示词构建 | `agent/prompt/builder.py` | `ChatPromptTemplate` | 模板化提示词 |
| 知识库/RAG | `agent/knowledge/` | `VectorStore` + `Retriever` | 文档检索增强生成 |

### 技能系统用 LangChain 怎么做？

CowAgent 的技能是 markdown 文件，初始化时加载并注入 system prompt。LangChain 没有直接对应的概念，但可以这样实现：

```python
# 方式1：动态拼接 system prompt（最接近 CowAgent 的做法）
skills = load_skill_files("~/cow/skills/")  # 读取技能文件
system_message = f"""你是一个AI助手。

你具备以下技能：
{skills}
"""
prompt = ChatPromptTemplate.from_messages([
    ("system", system_message),
    ...
])

# 方式2：把技能做成工具（更 LangChain 风格）
@tool
def code_review(code: str) -> str:
    """审查代码质量，给出改进建议"""
    return llm.invoke(f"请审查以下代码：\n{code}")
```

### 加入 RAG 的完整 Agent

```python
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import DashScopeEmbeddings
from langchain.tools.retriever import create_retriever_tool

# 向量化知识库
embeddings = DashScopeEmbeddings()
vectorstore = FAISS.load_local("knowledge_base", embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# 把检索器包装成工具，Agent 需要时自动调用
knowledge_tool = create_retriever_tool(
    retriever,
    name="knowledge_search",
    description="搜索知识库获取相关信息，当用户问到专业问题时使用"
)

# 加入工具列表
tools = [web_search, bash, read_file, knowledge_tool]

# Agent 会自动判断什么时候该搜知识库
executor = AgentExecutor(agent=agent, tools=tools, memory=memory)
result = executor.invoke({"input": "我们公司的请假流程是什么？"})
# Agent 思考 → 调用 knowledge_search → 检索到相关文档 → 生成回复
```

### 流式输出对比

```python
# CowAgent: 手写 SSE 队列 + 回调
context["on_event"] = self._make_sse_callback(request_id)
agent.run_stream(query, on_event=event_handler.handle_event)

# LangChain: 内置流式支持
async for event in executor.astream_events({"input": query}, version="v2"):
    if event["event"] == "on_chat_model_stream":
        chunk = event["data"]["chunk"]
        await send_sse(chunk.content)  # 推送给前端
```

## 九、下一步学习方向（建议顺序）

| 优先级 | 模块 | 内容 | 建议天数 |
|---|---|---|---|
| 1 | `agent/protocol/` | Agent 核心循环（think → act → observe） | DAY3 |
| 2 | `agent/tools/` | 工具系统（怎么注册、调用、返回结果） | DAY3 |
| 3 | `plugins/` | 插件系统（事件链、拦截机制） | DAY4 |
| 4 | `agent/memory/` | 记忆系统（对话存储、向量检索、摘要） | DAY4 |
| 5 | `agent/prompt/` | 提示词构建（system prompt 怎么拼的） | DAY5 |
| 6 | `agent/skills/` | 技能系统（动态加载的能力扩展） | DAY5 |
