"""
 ============================================================================
  📡 Channel 基类 — 所有消息通道的"抽象接口"
 ============================================================================
 
  继承关系：
  Channel（抽象基类）
      ↓
  ChatChannel（通用聊天逻辑）
      ↓
  WeixinChannel / FeiShuChannel / WebChannel / ...（具体实现）
  
  Channel 只定义接口，具体通道需要实现：
  - startup(): 启动通道，开始监听消息
  - handle_text(msg): 处理收到的消息
  - send(reply, context): 发送回复
  
  ChatChannel 已经实现了 handle_text 的通用逻辑，
  具体通道只需要实现 startup() 和 send()。
  
  💡 为什么要这样设计？
  因为不同通道的"收消息"和"发消息"方式完全不同：
  - 微信：扫码登录 → WebSocket 接收消息
  - 飞书：Webhook 回调
  - Web：SSE 流式推送
  但中间的"怎么处理消息"是一样的，所以抽到 ChatChannel。
 ============================================================================
"""

from bridge.bridge import Bridge
from bridge.context import Context
from bridge.reply import *
from common.log import logger
from config import conf


class Channel(object):
    """
    【抽象基类】消息通道
    
    所有具体通道（微信/飞书/Web...）的基类。
    定义了三个必须实现的方法：
    - startup(): 启动通道
    - handle_text(msg): 处理消息
    - send(reply, context): 发送回复
    """
    channel_type = ""  # 通道类型标识（如 "weixin", "feishu"）
    NOT_SUPPORT_REPLYTYPE = [ReplyType.VOICE, ReplyType.IMAGE]  # 不支持的回复类型

    def __init__(self):
        import threading
        self._startup_event = threading.Event()
        self._startup_error = None
        self.cloud_mode = False  # set to True by ChannelManager when running with cloud client

    def startup(self):
        """
        init channel
        """
        raise NotImplementedError

    def report_startup_success(self):
        self._startup_error = None
        self._startup_event.set()

    def report_startup_error(self, error: str):
        self._startup_error = error
        self._startup_event.set()

    def wait_startup(self, timeout: float = 3) -> (bool, str):
        """
        Wait for channel startup result.
        Returns (success: bool, error_msg: str).
        """
        ready = self._startup_event.wait(timeout=timeout)
        if not ready:
            return True, ""
        if self._startup_error:
            return False, self._startup_error
        return True, ""

    def stop(self):
        """
        stop channel gracefully, called before restart
        """
        pass

    def handle_text(self, msg):
        """
        process received msg
        :param msg: message object
        """
        raise NotImplementedError

    # 统一的发送函数，每个Channel自行实现，根据reply的type字段发送不同类型的消息
    def send(self, reply: Reply, context: Context):
        """
        send message to user
        :param msg: message content
        :param receiver: receiver channel account
        :return:
        """
        raise NotImplementedError

    def build_reply_content(self, query, context: Context = None) -> Reply:
        """
        Build reply content, using agent if enabled in config
        """
        # Check if agent mode is enabled
        use_agent = conf().get("agent", False)

        if use_agent:
            try:
                logger.info("[Channel] Using agent mode")

                # Add channel_type to context if not present
                if context and "channel_type" not in context:
                    context["channel_type"] = self.channel_type

                # Read on_event callback injected by the channel (e.g. web SSE)
                on_event = context.get("on_event") if context else None

                # Use agent bridge to handle the query
                return Bridge().fetch_agent_reply(
                    query=query,
                    context=context,
                    on_event=on_event,
                    clear_history=False
                )
            except Exception as e:
                logger.error(f"[Channel] Agent mode failed, fallback to normal mode: {e}")
                # Fallback to normal mode if agent fails
                return Bridge().fetch_reply_content(query, context)
        else:
            # Normal mode
            return Bridge().fetch_reply_content(query, context)

    def build_voice_to_text(self, voice_file) -> Reply:
        return Bridge().fetch_voice_to_text(voice_file)

    def build_text_to_voice(self, text) -> Reply:
        return Bridge().fetch_text_to_voice(text)
