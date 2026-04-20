# DAY3 学习计划 — Agent 核心循环 + 工具系统

## 学习路径回顾

```
DAY1: 入口层 + 通道层 ✅
  app.py → ChannelManager → WebChannel → post_message → produce/consume → _handle

DAY2: 桥接层 ✅
  _handle → _generate_reply → build_reply_content → Bridge → Bot/AgentBridge

DAY3: Agent 核心 + 工具系统 ← 今天
  AgentBridge.agent_reply() → Agent.run_stream() → 思考/工具调用/生成回复
```

## 今天要学什么

DAY2 学到 `AgentBridge.agent_reply()` 调用 `Agent.run_stream()` 就停了。
今天深入 Agent 内部，搞清楚两个核心问题：
1. Agent 的 think → act → observe 循环是怎么实现的？
2. 工具是怎么定义、注册、被 Agent 调用的？

## 学习模块

### 模块一：Agent 核心循环（agent/protocol/）

```
agent/protocol/
├── agent.py           # Agent 主类 — 管理工具、提示词、入口方法
├── agent_stream.py    # AgentStreamExecutor — 核心循环的实际实现
├── models.py          # LLMModel/LLMRequest — 模型调用的抽象
├── context.py         # AgentContext — Agent 运行时上下文
├── message_utils.py   # 消息格式处理工具函数
├── result.py          # AgentResult — 执行结果
└── task.py            # AgentTask — 任务定义
```

重点文件：
- `agent.py` — Agent 类的入口，`run_stream()` 方法
- `agent_stream.py` — `AgentStreamExecutor.run_stream()` 核心循环

要搞清楚的问题：
- [ ] `run_stream()` 的循环逻辑是什么？什么时候结束？
- [ ] AI 怎么决定"调工具"还是"直接回复"？
- [ ] 工具调用的结果怎么反馈给 AI？
- [ ] `max_steps` 限制怎么生效？
- [ ] 流式输出（SSE）在循环中怎么工作？
- [ ] 消息历史怎么管理？超长对话怎么截断？

### 模块二：工具系统（agent/tools/）

```
agent/tools/
├── base_tool.py       # BaseTool 基类 — 所有工具的模板
├── tool_manager.py    # ToolManager — 工具注册和管理
├── bash/              # 执行 shell 命令
├── edit/              # 编辑文件
├── read/              # 读取文件
├── write/             # 写入文件
├── ls/                # 列出目录
├── browser/           # 浏览器操作
├── web_search/        # 网页搜索
├── web_fetch/         # 抓取网页内容
├── memory/            # 记忆检索（memory_get, memory_search）
├── vision/            # 图片识别
├── send/              # 发送消息
├── scheduler/         # 定时任务
├── env_config/        # 环境配置
└── utils/             # 工具函数（diff, truncate）
```

重点文件：
- `base_tool.py` — 工具基类，理解工具的定义规范
- `tool_manager.py` — 工具怎么被发现和注册
- 挑 2-3 个具体工具看实现（建议 bash、read、web_search）

要搞清楚的问题：
- [ ] 一个工具需要定义哪些东西？（name, description, params, execute）
- [ ] JSON Schema 参数描述是怎么告诉 AI 的？
- [ ] ToolManager 怎么发现和加载工具？
- [ ] PRE_PROCESS 和 POST_PROCESS 工具有什么区别？
- [ ] 工具执行失败怎么处理？

## 建议学习顺序

```
第1步：base_tool.py
  → 理解工具的"骨架"：name/description/params/execute
  → 理解 ToolResult（成功/失败）
  → 理解 PRE_PROCESS vs POST_PROCESS

第2步：看 1-2 个具体工具实现
  → bash/bash.py（最简单，执行命令返回结果）
  → read/read.py（读文件，理解参数定义）

第3步：tool_manager.py
  → 工具怎么被发现、注册、创建实例

第4步：agent.py
  → Agent 类的结构，run_stream() 入口
  → 工具怎么注册到 Agent 上
  → system prompt 怎么包含工具描述

第5步：agent_stream.py（核心重点）
  → run_stream() 的循环逻辑
  → _call_llm_stream() 怎么调 AI
  → _execute_tool() 怎么执行工具
  → 消息历史管理和截断

第6步：对比 LangChain
  → 用 LangChain 实现同样的 Agent + 工具
```

## 核心调用链预览

```
Agent.run_stream(user_message)
    │
    ▼
AgentStreamExecutor.run_stream()
    │
    ▼
while steps < max_steps:          ← 核心循环
    │
    ├─→ _call_llm_stream()        ← 调 AI 模型
    │       │
    │       └─→ model.call_stream(messages)
    │               │
    │               └─→ 通义千问 API（流式返回）
    │
    ├─→ AI 返回内容解析
    │       │
    │       ├─ 有 tool_calls？→ _execute_tool()  ← 执行工具
    │       │                       │
    │       │                       ├─ 找到工具 → tool.execute(params)
    │       │                       └─ 结果加入 messages → 继续循环
    │       │
    │       └─ 没有 tool_calls？→ 最终回复 → 退出循环
    │
    └─→ 返回最终文字回复
```

## 学完后应该能回答的问题

1. AI 怎么知道有哪些工具可以用？
2. AI 返回的 tool_calls 长什么样？
3. 工具执行结果怎么传回给 AI？
4. 如果工具执行失败，Agent 会怎么处理？
5. 一次对话最多能调几次工具？
6. 如果我想新增一个自定义工具，需要做什么？
