import os
import json
"""
 ============================================================================
  🔧 Plugin 基类 — 插件的"模板"
 ============================================================================
 
  所有插件都需要继承这个基类。
  
  插件的核心方法：
  - __init__(): 注册事件处理函数（最重要！）
  - on_handle_context(): 处理 ON_HANDLE_CONTEXT 事件（最常用）
  - get_help_text(): 返回帮助信息（用户输入 #help 时显示）
  
  插件的配置机制：
  - load_config(): 加载插件配置
  - save_config(): 保存插件配置
  
  注意：load_config() 会优先从 plugins/config.json 加载，
       如果不存在才从插件目录下的 config.json 加载。
 ============================================================================
"""

from config import pconf, plugin_config, conf, write_plugin_config
from common.log import logger


class Plugin:
    """
    【基类】所有插件的基类
    
    写插件的步骤：
    1. 继承 Plugin
    2. 在 __init__ 中注册事件处理函数
    3. 实现事件处理函数
    4. 用 @register 装饰器注册
    
    示例：
    class MyPlugin(Plugin):
        def __init__(self):
            super().__init__()
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        
        def on_handle_context(self, e_context):
            # 处理消息...
            pass
    """
    def __init__(self):
        self.handlers = {}  # 事件类型 → 处理函数的映射

    def load_config(self) -> dict:
        """
        加载当前插件配置
        :return: 插件配置字典
        """
        # 优先获取 plugins/config.json 中的全局配置
        plugin_conf = pconf(self.name)
        if not plugin_conf:
            # 全局配置不存在，则获取插件目录下的配置
            plugin_config_path = os.path.join(self.path, "config.json")
            if os.path.exists(plugin_config_path):
                with open(plugin_config_path, "r", encoding="utf-8") as f:
                    plugin_conf = json.load(f)

                # 写入全局配置内存
                write_plugin_config({self.name: plugin_conf})
        return plugin_conf

    def save_config(self, config: dict):
        try:
            write_plugin_config({self.name: config})
            # 写入全局配置
            global_config_path = "./plugins/config.json"
            if os.path.exists(global_config_path):
                with open(global_config_path, "w", encoding='utf-8') as f:
                    json.dump(plugin_config, f, indent=4, ensure_ascii=False)
            # 写入插件配置
            plugin_config_path = os.path.join(self.path, "config.json")
            if os.path.exists(plugin_config_path):
                with open(plugin_config_path, "w", encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)

        except Exception as e:
            logger.warn("save plugin config failed: {}".format(e))

    def get_help_text(self, **kwargs):
        return "暂无帮助信息"

    def reload(self):
        pass
