# encoding:utf-8
"""
 ============================================================================
  ⚡ Event & EventContext — 插件事件的"合同"和"信封"
 ============================================================================
 
  Event（4 种事件，按消息生命周期排序）：
  
  ① ON_RECEIVE_MESSAGE — 收到消息（最早，还没解析内容）
     可用操作：过滤消息、修改 session_id
  
  ② ON_HANDLE_CONTEXT — 处理消息（最常用！插件在这里拦截和修改消息）
     可用操作：修改消息内容、直接回复、改变消息类型、中断处理链
  
  ③ ON_DECORATE_REPLY — 装饰回复（回复已生成，可以修改格式）
     可用操作：添加前缀后缀、转换回复类型（文字→语音）
  
  ④ ON_SEND_REPLY — 发送回复前（最后的拦截点）
     可用操作：记录日志、修改最终回复内容
 
  EventAction（3 种动作，控制事件传递）：
  
  CONTINUE    → "我处理完了，下一个插件继续"
  BREAK       → "我处理完了，不用下一个插件了，但请调模型"
  BREAK_PASS  → "我已经回复了，不用下一个插件，也不用调模型"
 
  💡 最常用的是 ON_HANDLE_CONTEXT + BREAK_PASS
     （拦截消息并直接回复，不让模型处理）
 ============================================================================
"""


class Event(Enum):
    ON_RECEIVE_MESSAGE = 1  # 收到消息 — 事件 ①
    """
    e_context = {  "channel": 消息channel, "context" : 本次消息的context}
    """

    ON_HANDLE_CONTEXT = 2  # 处理消息前
    """
    e_context = {  "channel": 消息channel, "context" : 本次消息的context, "reply" : 目前的回复，初始为空  }
    """

    ON_DECORATE_REPLY = 3  # 得到回复后准备装饰
    """
    e_context = {  "channel": 消息channel, "context" : 本次消息的context, "reply" : 目前的回复 }
    """

    ON_SEND_REPLY = 4  # 发送回复前
    """
    e_context = {  "channel": 消息channel, "context" : 本次消息的context, "reply" : 目前的回复 }
    """

    # AFTER_SEND_REPLY = 5    # 发送回复后


class EventAction(Enum):
    """
    事件动作 — 插件告诉系统"接下来怎么办"
    
    CONTINUE（默认）：继续传给下一个插件
      → 适用于：只是观察/记录消息，不做拦截
    
    BREAK：停止传递，但继续走默认处理逻辑（调模型）
      → 适用于：修改了消息内容，想让模型处理修改后的内容
    
    BREAK_PASS：停止传递，且跳过默认处理逻辑
      → 适用于：插件已经生成好了回复，不需要模型再处理
    
    💡 类比：
    CONTINUE = "我只是路过，你们继续"
    BREAK = "我来改一下，然后让模型处理"
    BREAK_PASS = "我已经搞定了，模型不用管了"
    """
    CONTINUE = 1  # 事件未结束，继续交给下个插件处理，如果没有下个插件，则交付给默认的事件处理逻辑
    BREAK = 2  # 事件结束，不再给下个插件处理，交付给默认的事件处理逻辑
    BREAK_PASS = 3  # 事件结束，不再给下个插件处理，不交付给默认的事件处理逻辑


class EventContext:
    def __init__(self, event, econtext=dict()):
        self.event = event
        self.econtext = econtext
        self.action = EventAction.CONTINUE

    def __getitem__(self, key):
        return self.econtext[key]

    def __setitem__(self, key, value):
        self.econtext[key] = value

    def __delitem__(self, key):
        del self.econtext[key]

    def is_pass(self):
        return self.action == EventAction.BREAK_PASS

    def is_break(self):
        return self.action == EventAction.BREAK or self.action == EventAction.BREAK_PASS
