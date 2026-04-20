"""
my-learn-cli 阶段4 — Web 界面 + SSE 流式输出

对应 CowAgent 的模块：
- FastAPI               → CowAgent 的 web.py HTTP 服务器（WebChannel.startup）
- /message POST         → CowAgent 的 MessageHandler → post_message()
- /stream SSE           → CowAgent 的 StreamHandler → SSE 推送
- /sessions GET         → CowAgent 的 SessionsHandler
- chat.html             → CowAgent 的 channel/web/chat.html

学习阶段：DAY1 的 Web 通道 + SSE 用 FastAPI 实现
"""

import json
import uuid
import threading
from pathlib import Path
from queue import Queue, Empty

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.callbacks import BaseCallbackHandler

from tools import ALL_TOOLS
from memory import ChatMemory


# ============================================================
# 配置 + 初始化
# ============================================================

def load_config() -> dict:
    config_path = Path(__file__).parent / "config.json"
    with open(config_path, "r") as f:
        return json.load(f)

config = load_config()
memory = ChatMemory()

# 每个 request_id 对应一个 SSE 队列（对应 CowAgent 的 sse_queues）
sse_queues: dict[str, Queue] = {}
# 每个 session_id 的对话历史缓存
session_histories: dict[str, list] = {}


def create_agent_executor() -> AgentExecutor:
    llm = ChatTongyi(
        model=config.get("model", "qwen-plus"),
        dashscope_api_key=config["dashscope_api_key"],
        streaming=True,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "你是一个有用的AI助手，可以使用工具帮助用户完成任务。\n"
         "当用户需要执行命令、查看文件或目录时，请使用对应的工具。"),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt)
    return AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=False,
        max_iterations=10,
        handle_parsing_errors=True,
    )

executor = create_agent_executor()


# ============================================================
# SSE 回调（对应 CowAgent 的 _make_sse_callback）
# ============================================================

class SSECallbackHandler(BaseCallbackHandler):
    """把 LLM 的流式输出推到 SSE 队列"""

    def __init__(self, queue: Queue):
        self.queue = queue

    def on_llm_new_token(self, token: str, **kwargs):
        self.queue.put({"type": "token", "data": token})


# ============================================================
# FastAPI 应用（对应 CowAgent 的 WebChannel）
# ============================================================

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
async def root():
    """首页，对应 CowAgent 的 RootHandler → /chat"""
    html_path = Path(__file__).parent / "chat.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/sessions")
async def list_sessions():
    """会话列表，对应 CowAgent 的 SessionsHandler"""
    sessions = memory.list_sessions()
    return JSONResponse(sessions)


@app.post("/message")
async def post_message(request: Request):
    """
    接收消息，对应 CowAgent 的 MessageHandler → post_message()。
    
    CowAgent 的流程：解析请求 → 构建 Context → produce() 入队 → 返回 request_id
    我们简化为：解析请求 → 开线程处理 → 返回 request_id
    """
    data = await request.json()
    message = data.get("message", "")
    session_id = data.get("session_id", str(uuid.uuid4())[:8])

    request_id = str(uuid.uuid4())[:8]
    sse_queues[request_id] = Queue()

    # 加载历史
    if session_id not in session_histories:
        session_histories[session_id] = memory.load_messages(session_id)

    # 开线程处理（对应 CowAgent 的 produce → consume → _handle）
    threading.Thread(
        target=_process_message,
        args=(request_id, session_id, message),
        daemon=True,
    ).start()

    return JSONResponse({
        "status": "success",
        "request_id": request_id,
        "session_id": session_id,
    })


def _process_message(request_id: str, session_id: str, message: str):
    """
    后台处理消息，对应 CowAgent 的 _handle → _generate_reply → _send_reply。
    """
    queue = sse_queues.get(request_id)
    if not queue:
        return

    chat_history = session_histories.get(session_id, [])

    try:
        callback = SSECallbackHandler(queue)
        result = executor.invoke(
            {"input": message, "chat_history": chat_history},
            config={"callbacks": [callback]},
        )
        response = result["output"]

        # 持久化
        new_msgs = [HumanMessage(content=message), AIMessage(content=response)]
        chat_history.extend(new_msgs)
        session_histories[session_id] = chat_history
        memory.save_messages(session_id, new_msgs)

    except Exception as e:
        queue.put({"type": "error", "data": str(e)})
    finally:
        queue.put({"type": "done"})


@app.get("/stream")
async def stream(request_id: str):
    """
    SSE 流式推送，对应 CowAgent 的 StreamHandler。
    
    CowAgent 用 web.py 手写 SSE，我们用 FastAPI 的 StreamingResponse。
    """
    def event_generator():
        queue = sse_queues.get(request_id)
        if not queue:
            yield f"data: {json.dumps({'type': 'error', 'data': 'invalid request_id'})}\n\n"
            return

        while True:
            try:
                event = queue.get(timeout=60)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") in ("done", "error"):
                    break
            except Empty:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

        # 清理
        sse_queues.pop(request_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.post("/api/sessions/{session_id}/clear")
async def clear_session(session_id: str):
    """清除会话"""
    memory.clear_session(session_id)
    session_histories.pop(session_id, None)
    return JSONResponse({"status": "success"})
