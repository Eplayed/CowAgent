"""
my-learn-cli — 用 LangChain 复刻 CowAgent 的最小 MVP

对应 CowAgent 的模块：
- config.json          → CowAgent 的 config.py（配置管理）
- ChatTongyi           → CowAgent 的 Bridge + DashscopeBot（模型路由+调用）
- ConversationBufferMemory 的效果 → CowAgent 的 session.messages（对话历史）
- 终端输入输出         → CowAgent 的 Channel 层（WebChannel）

学习阶段：DAY1-DAY2 的内容用 LangChain 实现
"""

import json
import sys
from pathlib import Path

from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


# ============================================================
# 第1层：配置管理（对应 CowAgent 的 config.py）
# ============================================================

def load_config() -> dict:
    """加载配置文件，对应 CowAgent 的 load_config()"""
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        print("错误：找不到 config.json")
        sys.exit(1)
    with open(config_path, "r") as f:
        return json.load(f)


# ============================================================
# 第2层：模型创建（对应 CowAgent 的 Bridge + BotFactory）
# ============================================================

def create_llm(config: dict) -> ChatTongyi:
    """
    创建 LLM 实例。
    
    CowAgent 需要 Bridge 路由 + BotFactory 工厂 + DashscopeBot 适配，
    LangChain 一行搞定。
    """
    return ChatTongyi(
        model=config.get("model", "qwen-plus"),
        dashscope_api_key=config["dashscope_api_key"],
        streaming=True,  # 启用流式输出
    )


# ============================================================
# 第3层：对话管理（对应 CowAgent 的 session.messages）
# ============================================================

class ChatSession:
    """
    对话会话管理。
    
    对应 CowAgent 的 DashscopeBot 中的 session.messages，
    维护完整的对话历史，每次调 API 都带上。
    """

    def __init__(self, system_prompt: str = "你是一个有用的AI助手。"):
        self.messages = [SystemMessage(content=system_prompt)]

    def add_user_message(self, content: str):
        self.messages.append(HumanMessage(content=content))

    def add_ai_message(self, content: str):
        self.messages.append(AIMessage(content=content))

    def clear(self):
        """清除对话历史，只保留 system prompt"""
        system = self.messages[0]
        self.messages = [system]


# ============================================================
# 第4层：终端交互（对应 CowAgent 的 Channel 层）
# ============================================================

def run():
    """
    入口函数，对应 CowAgent 的 app.py run()。
    
    CowAgent 的流程：
      load_config → ChannelManager → WebChannel → post_message → produce/consume → _handle
    
    我们简化为：
      load_config → create_llm → 终端循环（输入 → 调 AI → 流式输出）
    """
    config = load_config()
    llm = create_llm(config)
    session = ChatSession()

    print("=" * 50)
    print("  my-learn-cli — LangChain + 通义千问")
    print("  输入消息开始对话，输入 'quit' 退出")
    print("  输入 '#清除记忆' 清除对话历史")
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
            session.clear()
            print("助手: 记忆已清除\n")
            continue

        # 用户消息加入历史
        session.add_user_message(user_input)

        # 流式调用 AI（对应 CowAgent 的 Bridge.fetch_reply_content → DashscopeBot.reply_text）
        print("助手: ", end="", flush=True)
        full_response = ""
        try:
            for chunk in llm.stream(session.messages):
                text = chunk.content
                print(text, end="", flush=True)
                full_response += text
            print("\n")
        except Exception as e:
            print(f"\n调用失败: {e}\n")
            # 移除刚加的用户消息（调用失败不应该留在历史里）
            session.messages.pop()
            continue

        # AI 回复加入历史（对应 CowAgent 的 session_reply）
        session.add_ai_message(full_response)


if __name__ == "__main__":
    run()
