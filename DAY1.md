# DAY1 学习笔记 — CowAgent 入口与消息链路

## 一、config.py — 配置脱敏函数

`drag_sensitive(config)` 函数用于对配置中的敏感字段（键名包含 "key" 或 "secret"）做脱敏处理：
- 保留前 3 位和后 3 位，中间用 `*****` 替代
- 支持传入 JSON 字符串或字典两种格式
- 函数名可能想表达 `mask_sensitive`（遮蔽敏感信息）

## 二、app.py — 启动入口与整体架构

### 启动流程

```
run()
  → load_config()                 # 读取配置
  → sigterm_handler_wrap()        # 注册 Ctrl+C / kill 优雅退出
  → _parse_channel_type()         # 解析通道列表
  → ChannelManager().start()      # 创建并启动所有通道
  → while True: time.sleep(1)     # 主线程挂起
```

### 核心类 ChannelManager

多通道管理器，职责：
- 管理多个消息通道的生命周期（创建/启动/停止/重启）
- 每个通道在独立守护线程中运行，互不干扰
- 用工厂模式创建通道，线程锁保护共享状态

### 关键函数一览

| 函数 | 作用 |
|------|------|
| `get_channel_manager()` | 获取全局通道管理器实例 |
| `_parse_channel_type()` | 将配置值解析为通道名称列表 |
| `ChannelManager.start()` | 创建通道实例，每个通道开独立线程运行 |
| `ChannelManager.stop()` | 优雅停止通道，超时则强制中断 |
| `ChannelManager.restart()` | 停止 → 清缓存 → 重启 |
| `ChannelManager.add_channel()` | 运行时动态添加通道 |
| `ChannelManager.remove_channel()` | 运行时动态移除通道 |
| `_clear_singleton_cache()` | 清除通道类的单例缓存（通过反射清闭包中的 dict） |
| `sigterm_handler_wrap()` | 注册信号处理器，退出前保存用户数据 |
| `run()` | 程序入口，加载配置 → 启动通道 → 挂起等待 |

### 当前配置

`config.json` 中 `channel_type` 为空，所以只启动了 Web 通道（默认 `http://localhost:9899`）。

## 三、Python 语法点 — `with self._lock:`

这是上下文管理器语法，用于自动管理线程锁：

```python
# 等价于
self._lock.acquire()
try:
    do_something()
finally:
    self._lock.release()
```

类似 Java 的 `synchronized`，用来**防止**并发问题，不是死锁。
`with` 的好处是即使代码抛异常，锁也会自动释放，避免"忘记解锁"导致死锁。

## 四、消息完整链路（核心）

### 全景图

```
浏览器输入 "你好"
    │
    ▼
POST /message
    │
    ▼
WebChannel.post_message()     ← 解析请求，构建 Context
    │
    ▼
produce()                     ← 消息入队（生产者）
    │
    ▼
consume()                     ← 后台循环取消息（消费者）
    │
    ▼
_handle()                     ← 总调度
    │
    ├─→ _generate_reply()     ← 生成回复
    │       │
    │       ├─→ 插件链处理（可拦截）
    │       │
    │       └─→ build_reply_content()
    │               │
    │               └─→ Bridge().fetch_agent_reply()
    │                       │
    │                       └─→ 通义千问 API（当前配置的模型）
    │
    ├─→ _decorate_reply()     ← 加前缀后缀
    │
    └─→ _send_reply()         ← 发送回复
            │
            └─→ WebChannel.send() → SSE 推送给浏览器
```

### 逐步详解

**第 1 步：浏览器发送请求**
前端 JS 发 `POST /message`，携带 `{ message, session_id, stream: true }`

**第 2 步：路由到 Handler**
`MessageHandler.POST()` → 调用 `WebChannel().post_message()`

**第 3 步：post_message() — 接收请求**
- 解析参数（message、session_id、attachments）
- 调用 `_compose_context()` 构建 Context（消息安检、过滤黑名单）
- 开新线程调用 `produce(context)` 入队
- 立即返回 `request_id` 给前端（异步处理）

**第 4 步：produce() — 消息入队**
- 每个 session 有独立的双端队列（Dequeue）
- `#` 开头的消息插队到队首（管理命令优先）
- 其他消息追加到队尾

**第 5 步：consume() — 后台消费**
- 无限循环，每 0.2 秒扫描所有会话
- 信号量控制每个会话同时只处理 1 条消息（串行，避免乱序）
- 取出消息后提交到线程池执行 `_handle()`

**第 6 步：_handle() — 三步流水线**
```python
reply = self._generate_reply(context)    # 1. 厨房做菜
reply = self._decorate_reply(context, reply)  # 2. 摆盘装饰
self._send_reply(context, reply)         # 3. 服务员上菜
```

**第 7 步：_generate_reply() — 调用 AI**
- 先过插件链（ON_HANDLE_CONTEXT），插件可拦截
- 未被拦截则调用 `build_reply_content()`

**第 8 步：build_reply_content() → Bridge**
- `agent=true` 时走 `Bridge().fetch_agent_reply()`（Agent 模式）
- `agent=false` 时走 `Bridge().fetch_reply_content()`（直接调模型）
- Bridge 根据模型名路由到对应的 bot（如 qwen → QWEN_DASHSCOPE）

**第 9 步：回复返回**
AI 返回 Reply → 装饰 → `WebChannel.send()` 推到 SSE 队列 → 浏览器接收渲染

### 核心 5 个函数

| 函数 | 文件 | 职责 |
|------|------|------|
| `post_message()` | web_channel.py | 接收 HTTP 请求，构建 Context |
| `produce()` | chat_channel.py | 消息入队（生产者） |
| `consume()` | chat_channel.py | 消息出队（消费者） |
| `_handle()` | chat_channel.py | 总调度：生成 → 装饰 → 发送 |
| `build_reply_content()` | channel.py | 调用 Bridge 路由到 AI 模型 |

## 五、实战排错

### 问题：发送消息返回"发送失败，请稍后再试"

**根因**：`chat_channel.py` 在之前加注释的 git 提交中，import 块被误删，导致 `conf`、`PluginManager`、`handler_pool`、`Dequeue`、`Future` 等全部未定义。

**修复**：从 git 历史恢复完整的 import：

```python
import os
import re
import threading
import time
from asyncio import CancelledError
from concurrent.futures import Future, ThreadPoolExecutor

from bridge.context import *
from bridge.reply import *
from channel.channel import Channel
from common.dequeue import Dequeue
from common import memory
from common.log import logger
from config import conf
from plugins import *

try:
    from voice.audio_convert import any_to_wav
except Exception as e:
    pass

handler_pool = ThreadPoolExecutor(max_workers=8)
```

**教训**：修改文件时注意不要误删 import，Python 不像 Java 有编译期检查，缺少 import 只有运行时才会报错。

## 六、下一步学习方向

- `bridge/` — Bridge 如何路由到不同 AI 模型
- `agent/` — Agent 模式的思考和工具调用流程
- `plugins/` — 插件系统如何拦截和处理消息
