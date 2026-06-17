# 这是一个示例插件
import pluggy
from pathlib import Path

from plugin_sdk import PluginSDK, PluginMenu

PLUGIN_NAME = 'example插件'
PLUGIN_VERSION = '1.0.0'
PLUGIN_AUTHOR = 'tiosa'
PLUGIN_PATH = Path(__file__).parent

# 使用与主程序一致的标识
hook = pluggy.HookimplMarker("toudawifi") # 不能变动

class Plugin:  # 类名固定为 Plugin，不能变动，否则无法识别
    @hook
    def start(self,api) -> bool:
        """插件加载时执行，传api包含已实例化的wifi和webvpn类"""
        self.api = api
        self.sdk = PluginSDK(api, PLUGIN_NAME)
        self.sdk.logger_info(f'当前wifi用户名：{self.api.wifi.name}')
        return True # 返回true才会视为有效插件
    @hook
    def on_disable(self):
        self.sdk.logger_info(f'{PLUGIN_NAME}禁用')
    @hook
    def get_name(self)->str:
        """获取插件名字"""
        return PLUGIN_NAME
    @hook
    def get_description(self)->str:
        """获取插件描述,支持markdown"""
        try:
            with open(PLUGIN_PATH/'readme.md',encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.sdk.logger_error(f'出错啦:{e}')
    @hook
    def get_menu(self)->list[dict]: # list[功能 - function]
        """获取插件的菜单信息,需要返回list[{'function':'功能名','object':callable函数}]"""
        menu = PluginMenu()
        menu.add_func('测试功能',self.hello_world)
        return menu.get_all()
    
    def hello_world(self):
        self.sdk.logger_info('hello world')
