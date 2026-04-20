"""
my-learn-cli 阶段2+3 — Agent 模式 + 记忆持久化

对应 CowAgent 的模块：
- tools.py             → CowAgent 的 agent/tools/（工具系统）
- memory.py            → CowAgent 的 agent/memory/conversation_store.py（持久化）
- create_agent_executor → CowAgent 的 AgentBridge + AgentInitializer（Agent 初始化）
- AgentExecutor        → CowAgent 的 Agent.run_stream()（核心循环）

学习阶段：DAY3 + 记忆持久化
"""

import json
import sys
import uuid
from pathlib import Path

from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor

from tools import ALL_TOOLS
from memory import ChatMemory


# ============================================================
# 第1层：配置管理（同阶段1）
# ============================================================

def load_config() -> dict:
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        print("错误：找不到 config.json")
        sys.exit(1)
    with open(config_path, "r") as f:
        return json.load(f)


# ============================================================
# 第2层：创建 Agent（对应 CowAgent 的 AgentBridge + AgentInitializer）
# ============================================================

def create_agent_executor(config: dict) -> AgentExecutor:
    """
    创建 Agent 执行器。
    
    CowAgent 的流程：
      AgentInitializer.initialize_agent()
        → 加载工具 → 构建 system prompt → 创建 Agent 实例
    
    LangChain 简化为：
      创建 LLM → 定义 prompt → create_tool_calling_agent → AgentExecutor
    """
    # 1. 创建 LLM（对应 Bridge + BotFactory）
    llm = ChatTongyi(
        model=config.get("model", "qwen-plus"),
        dashscope_api_key=config["dashscope_api_key"],
    )

    # 2. 定义提示词模板（对应 agent/prompt/builder.py）
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "你是一个有用的AI助手，可以使用工具帮助用户完成任务。\n"
         "当用户需要执行命令、查看文件或目录时，请使用对应的工具。\n"
         "使用工具后，根据工具返回的结果回答用户。"),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # 3. 创建 Agent（对应 AgentBridge.create_agent）
    agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt)

    # 4. 创建执行器（对应 Agent.run_stream 的循环逻辑）
    executor = AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True,       # 打印思考过程（方便学习）
        max_iterations=10,  # 最多调 10 次工具（对应 agent_max_steps）
        handle_parsing_errors=True,
    )

    return executor


# ============================================================
# 第3层：终端交互（对应 CowAgent 的 Channel 层）
# ============================================================

def run():
    """
    入口函数。
    
    与阶段1的区别：
    - 阶段1用 llm.stream() 直接调模型
    - 阶段2用 executor.invoke() 走 Agent 循环（think → act → observe）
    - 阶段3加入 SQLite 持久化，关掉程序再打开还能记住之前的对话
    """
    config = load_config()
    executor = create_agent_executor(config)
    memory = ChatMemory()  # SQLite 持久化（对应 CowAgent 的 ConversationStore）

    # 选择或创建会话
    sessions = memory.list_sessions()
    session_id = None

    if sessions:
        print("\n历史会话：")
        for i, s in enumerate(sessions[:5]):
            print(f"  {i + 1}. {s['title']}")
        print(f"  0. 新建对话")
        choice = input("\n选择会话编号（直接回车新建）: ").strip()
        if choice.isdigit() and 0 < int(choice) <= len(sessions[:5]):
            session_id = sessions[int(choice) - 1]["session_id"]
            print(f"已恢复会话: {sessions[int(choice) - 1]['title']}")

    if not session_id:
        session_id = str(uuid.uuid4())[:8]
        print(f"新建会话: {session_id}")

    # 从数据库加载历史消息
    chat_history = memory.load_messages(session_id)
    if chat_history:
        print(f"（已加载 {len(chat_history)} 条历史消息）")

    print()
    print("=" * 50)
    print("  my-learn-cli Agent 模式 + 记忆持久化")
    print("  可用工具: bash_run, read_file, list_directory")
    print("  输入 'quit' 退出，'#清除记忆' 清除历史")
    print("=" * 50)
    print()

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("再见！")
            break
        if user_input == "#清除记忆":
            chat_history.clear()
            memory.clear_session(session_id)
            print("助手: 记忆已清除（数据库也已清空）\n")
            continue

        try:
            result = executor.invoke({
                "input": user_input,
                "chat_history": chat_history,
            })

            response = result["output"]
            print(f"\n助手: {response}\n")

            # 保存到内存
            new_messages = [
                HumanMessage(content=user_input),
                AIMessage(content=response),
            ]
            chat_history.extend(new_messages)

            # 持久化到 SQLite（对应 CowAgent 的 AgentBridge._persist_messages）
            memory.save_messages(session_id, new_messages)

        except Exception as e:
            print(f"\n调用失败: {e}\n")


if __name__ == "__main__":
    run()
