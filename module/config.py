# Desc: 配置文件解析模块
import tomlkit
class CfgParse:
    def __init__(self, path:str):
        self.path = path
        with open(path, 'r', encoding='utf-8') as f:
            self.cfg = tomlkit.load(f)
    def get(self, section:str, option:str, default=None, reloaded=False):
        '''
        Args:
            - section : 配置文件的节名
            - option :  配置文件的项名
            - default : 默认值
            - reloaded : 是否重新加载配置文件(可以再次加载配置文件获取用户更改等等)
        '''
        try:
            if reloaded:
                 with open(self.path, 'r', encoding='utf-8') as f:
                    self.cfg = tomlkit.load(f)
            return self.cfg[section][option]
        except:
            return default
    def write(self, section:str, option:str, value):
        '''
        Args:
            - section : 配置文件的节名
            - option :  配置文件的项名
            - value :  写入的值
        '''
        self.cfg[section][option] = value
        with open(self.path, 'w', encoding='utf-8') as f:
            tomlkit.dump(self.cfg, f)

