"""
 ============================================================================
  🏭 ChannelFactory — 通道工厂
 ============================================================================
 
  核心职责：根据 channel_type 字符串，创建对应的 Channel 实例。
  
  设计模式：简单工厂模式
  
  支持的通道：
  - "terminal" → 终端对话
  - "web" → Web 控制台
  - "wechatmp" → 微信公众号（被动回复）
  - "wechatmp_service" → 微信公众号（主动回复）
  - "wechatcom_app" → 企业微信应用
  - "feishu" → 飞书
  - "dingtalk" → 钉钉
  - "wecom_bot" → 企业微信机器人
  - "qq" → QQ
  - "weixin" / "wx" → 个人微信
  
  💡 类比：就像餐厅的"点餐台"，你说"我要飞书"，它就给你一个 FeiShuChannel 实例
 ============================================================================
"""

from common import const
from .channel import Channel


def create_channel(channel_type) -> Channel:
    """
    create a channel instance
    :param channel_type: channel type code
    :return: channel instance
    """
    ch = Channel()
    if channel_type == "terminal":
        from channel.terminal.terminal_channel import TerminalChannel
        ch = TerminalChannel()
    elif channel_type == 'web':
        from channel.web.web_channel import WebChannel
        ch = WebChannel()
    elif channel_type == "wechatmp":
        from channel.wechatmp.wechatmp_channel import WechatMPChannel
        ch = WechatMPChannel(passive_reply=True)
    elif channel_type == "wechatmp_service":
        from channel.wechatmp.wechatmp_channel import WechatMPChannel
        ch = WechatMPChannel(passive_reply=False)
    elif channel_type == "wechatcom_app":
        from channel.wechatcom.wechatcomapp_channel import WechatComAppChannel
        ch = WechatComAppChannel()
    elif channel_type == const.FEISHU:
        from channel.feishu.feishu_channel import FeiShuChanel
        ch = FeiShuChanel()
    elif channel_type == const.DINGTALK:
        from channel.dingtalk.dingtalk_channel import DingTalkChanel
        ch = DingTalkChanel()
    elif channel_type == const.WECOM_BOT:
        from channel.wecom_bot.wecom_bot_channel import WecomBotChannel
        ch = WecomBotChannel()
    elif channel_type == const.QQ:
        from channel.qq.qq_channel import QQChannel
        ch = QQChannel()
    elif channel_type in (const.WEIXIN, "wx"):
        from channel.weixin.weixin_channel import WeixinChannel
        ch = WeixinChannel()
        channel_type = const.WEIXIN
    else:
        raise RuntimeError
    ch.channel_type = channel_type
    return ch
