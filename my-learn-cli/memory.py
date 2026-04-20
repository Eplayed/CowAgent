"""
记忆持久化 — 对应 CowAgent 的 agent/memory/conversation_store.py

CowAgent 手写了 ConversationStore（SQLite 两张表：sessions + messages），
我们用 LangChain 的 SQLChatMessageHistory 实现同样的功能。

对应关系：
- ChatMessageHistory    → CowAgent 的 ConversationStore
- SQLite 文件           → CowAgent 的 ~/cow/data/conversations.db
- get_session_history() → CowAgent 的 load_messages() + append_messages()
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import List, Dict, Optional

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage


class ChatMemory:
    """
    基于 SQLite 的对话历史持久化。
    
    对应 CowAgent 的 ConversationStore，简化版只保留核心功能：
    - 保存对话消息到数据库
    - 加载历史消息
    - 清除会话
    - 列出所有会话
    """

    def __init__(self, db_path: str = "chat_history.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """初始化数据库，对应 CowAgent 的 ConversationStore._init_db"""
        conn = self._connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                title        TEXT NOT NULL DEFAULT '',
                created_at   INTEGER NOT NULL,
                last_active  INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   TEXT NOT NULL,
                seq          INTEGER NOT NULL,
                role         TEXT NOT NULL,
                content      TEXT NOT NULL,
                created_at   INTEGER NOT NULL,
                UNIQUE(session_id, seq)
            );

            CREATE INDEX IF NOT EXISTS idx_msg_session
                ON messages(session_id, seq);
        """)
        conn.commit()
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def save_messages(self, session_id: str, messages: List[BaseMessage]):
        """
        保存消息到数据库。
        对应 CowAgent 的 ConversationStore.append_messages()
        """
        now = int(time.time())
        conn = self._connect()
        try:
            # 创建或更新 session
            conn.execute(
                "INSERT OR IGNORE INTO sessions (session_id, created_at, last_active) VALUES (?, ?, ?)",
                (session_id, now, now),
            )
            conn.execute(
                "UPDATE sessions SET last_active = ? WHERE session_id = ?",
                (now, session_id),
            )

            # 获取当前最大 seq
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), -1) FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            next_seq = row[0] + 1

            for msg in messages:
                role = msg.type  # "human", "ai", "system"
                content = msg.content
                conn.execute(
                    "INSERT OR IGNORE INTO messages (session_id, seq, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                    (session_id, next_seq, role, content, now),
                )
                next_seq += 1

            # 自动生成标题（取第一条用户消息的前30字）
            title_row = conn.execute(
                "SELECT title FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if title_row and not title_row[0]:
                for msg in messages:
                    if msg.type == "human":
                        title = msg.content[:30].split("\n")[0]
                        conn.execute(
                            "UPDATE sessions SET title = ? WHERE session_id = ?",
                            (title, session_id),
                        )
                        break

            conn.commit()
        finally:
            conn.close()

    def load_messages(self, session_id: str, max_turns: int = 20) -> List[BaseMessage]:
        """
        从数据库加载历史消息。
        对应 CowAgent 的 ConversationStore.load_messages()
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY seq",
                (session_id,),
            ).fetchall()
        finally:
            conn.close()

        messages = []
        for role, content in rows:
            if role == "human":
                messages.append(HumanMessage(content=content))
            elif role == "ai":
                messages.append(AIMessage(content=content))
            elif role == "system":
                messages.append(SystemMessage(content=content))

        # 只保留最近 max_turns 轮（一轮 = 一问一答 = 2条消息）
        if len(messages) > max_turns * 2:
            messages = messages[-(max_turns * 2):]

        return messages

    def clear_session(self, session_id: str):
        """清除指定会话，对应 CowAgent 的 ConversationStore.clear_session"""
        conn = self._connect()
        try:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
        finally:
            conn.close()

    def list_sessions(self) -> List[Dict]:
        """列出所有会话，对应 CowAgent 的 ConversationStore.list_sessions"""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT session_id, title, last_active FROM sessions ORDER BY last_active DESC"
            ).fetchall()
        finally:
            conn.close()
        return [
            {"session_id": r[0], "title": r[1] or "未命名", "last_active": r[2]}
            for r in rows
        ]
