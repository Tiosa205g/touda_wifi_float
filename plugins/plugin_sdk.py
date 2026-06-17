"""Plugin SDK - 为插件提供通用工具类，消除各插件间的重复代码"""


class PluginMenu:
    """插件菜单构建器"""

    def __init__(self):
        self.menu = []

    def add_func(self, func_name: str, func):
        """添加单个菜单项"""
        self.menu.append({'function': func_name, 'object': func})

    def add_funcs(self, funcs: list[dict]):
        """批量添加菜单项"""
        self.menu.extend(funcs)

    def del_func(self, func_name: str) -> bool:
        """删除指定名称的菜单项"""
        count = len(self.menu)
        self.menu = [x for x in self.menu if x['function'] != func_name]
        return len(self.menu) != count

    def get_all(self) -> list[dict]:
        return self.menu


class PluginSDK:
    """插件 SDK 基类，提供日志等通用功能"""

    def __init__(self, api, plugin_name=""):
        self.api = api
        self._plugin_name = plugin_name

    def logger_info(self, msg: str):
        self.api.logger.info(f'[{self._plugin_name}] {msg}')

    def logger_error(self, msg: str):
        self.api.logger.error(f'[{self._plugin_name}] {msg}')
