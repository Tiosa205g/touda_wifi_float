# 这是一个示例插件
import pluggy
from pathlib import Path


# 使用与主程序一致的标识
hook = pluggy.HookimplMarker("toudawifi")

class Plugin:  # 类名固定为 Plugin，不能变动，否则无法识别
    @hook
    def start(self, name:str) -> bool:
        """插件加载时执行，传用户名称"""
        print(f'插件收到name数据:{name}')
    @hook
    def get_name(self)->str:
        """获取插件名字"""
        return "example插件"
    @hook
    def get_description(self)->str:
        """获取插件描述,支持markdown"""
        try:
            with open(Path(__file__).parent/'readme.md',encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f'出错啦:{e}')
