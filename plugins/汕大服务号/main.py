# 这是一个示例插件
import pluggy
import requests
from pathlib import Path

PLUGIN_NAME = '汕大服务号插件'
PLUGIN_VERSION = '1.0.0'
PLUGIN_AUTHOR = 'tiosa'
PLUGIN_PATH = Path(__file__).parent

# 使用与主程序一致的标识
hook = pluggy.HookimplMarker("toudawifi") # 不能变动

class SDK:
    def __init__(self,api):
        self.api = api
    def logger_info(self,msg:str):
        self.api.logger.info(f'[{PLUGIN_NAME}] {msg}')
    def logger_error(self,msg:str):
        self.api.logger.error(f'[{PLUGIN_NAME}] {msg}')
    
    class Menu: # 插件名 功能名 函数
        def __init__(self):
            self.menu = []
        def add_func(self,func_name:str,func):
            """功能名，可调用的函数对象"""
            self.menu.append({'function':func_name,
                              'object':func})
            
        def add_funcs(self,funcs:list[dict]):
            """list内应为{'function':功能名,'object':可调用函数对象}"""
            self.menu.extend(funcs)

        def del_func(self,func_name:str)->bool:
            """删除指定功能名的功能"""
            num = len(num)
            self.menu = [x for x in self.menu if x['function'] != func_name] 
            return len(self.menu) != num
        
        def get_all(self)->list[dict]:
            return self.menu
class Plugin:  # 类名固定为 Plugin，不能变动，否则无法识别
    @hook
    def start(self,api) -> bool:
        """插件加载时执行，传api包含已实例化的wifi和webvpn类"""
        self.api = api
        self.sdk = SDK(self.api)
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
        menu = self.sdk.Menu()
        menu.add_func('获取一卡通余额',self.hello_world)
        return menu.get_all()
    
    def query_card_remain(self):
        self.sdk.logger_info('hello world')

    def query_card_records(self):
        pass
    
    def apply_webvpn(self):
        pass

    def unbind_totp(self):
        pass
    
    def bind_mac(self):
        pass