import pluggy
import os
import importlib.util
from .config import CfgParse
class Api:
    """通过start返回给插件的类，可以调用已实例化的类"""
    def __init__(self,wifi,webvpn,version,cfg_dir,main_cfg,links_cfg):
        self.wifi = wifi
        self.webvpn = webvpn
        self.cfg = CfgParse
        self.VERSION = version
        self.CFG_DIR = cfg_dir
        self.MAIN_CFG = main_cfg
        self.LINKS_CFG = links_cfg
# 1. 定义钩子规范（插件需实现的接口）
hook = pluggy.HookspecMarker("toudawifi")

class PluginSpec:
    @hook
    def start(self,api)->bool:
        """插件加载时执行,插件返回true才能被认为正确加载"""
    @hook
    def get_name(self)->str:
        """获取插件名字"""
    @hook
    def get_description(self)->str:
        """获取插件描述,支持markdown"""
    @hook
    def on_setting(self):
        """当设置按钮被点击"""
    @hook
    def on_disable(self):
        """当插件被禁用时"""
    @hook 
    def on_exit(self):
        """程序退出时调用"""
# 2. 遍历插件目录下所有子目录中的 main.py 并加载插件
def load_all_plugins(plugin_root: str, pm: pluggy.PluginManager):
    """
    递归遍历插件根目录下的所有子目录，加载其中的 main.py 作为插件
    :param plugin_root: 插件根目录（如 ./plugins）
    :param pm: Pluggy 插件管理器
    """
    # 递归遍历所有子目录
    for root, dirs, files in os.walk(plugin_root):
        # 只处理包含 main.py 的子目录
        if "main.py" in files:
            main_py_path = os.path.join(root, "main.py")
            module_name = f"plugin_{root.replace(os.sep, '_')}"  # 替换路径分隔符为下划线
            
            try:
                # 动态导入 main.py 模块
                spec = importlib.util.spec_from_file_location(module_name, main_py_path)
                if not spec or not spec.loader:
                    print(f"跳过无效文件：{main_py_path}")
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # 查找并注册插件类（约定：插件类名为 Plugin）
                if hasattr(module, "Plugin"):
                    plugin_class = module.Plugin
                    if isinstance(plugin_class, type):  # 确保是类
                        pm.register(plugin_class())
                        print(f"已加载插件：{root}（来自 {main_py_path}）")
                else:
                    print(f"警告：{main_py_path} 中未找到 Plugin 类")
            
            except Exception as e:
                print(f"加载插件失败 {main_py_path}：{str(e)}")


class Manager:
    def __init__(self,wifi,webvpn,version,cfg_dir,main_cfg,links_cfg):
        self.api = Api(wifi,webvpn,version,cfg_dir,main_cfg,links_cfg)
        # 创建插件管理器并注册钩子规范
        self.pm = pluggy.PluginManager("toudawifi")
        self.pm.add_hookspecs(PluginSpec)
        
        # 加载 plugins 目录下所有子目录中的 main.py 插件
        load_all_plugins(plugin_root="./plugins", pm=self.pm)

        # 套娃获取可用插件列表，无效自动卸载
        self.plugins = [x for x in [{'name':plg.get_name(),'description':plg.get_description(),'object':plg} if plg.start(self.api) else plg.on_disable() and self.pm.unregister(plg) for plg in self.pm.get_plugins()] if x is not None] # 插件字典列表
        print(f'已加载的有效插件列表:{self.plugins}') 
    def open_plg_setting(plg):
        plg.on_setting()


# 3. 初始化插件管理器并加载所有插件
if __name__ == "__main__":
    m = Manager(None,None) # 测试
