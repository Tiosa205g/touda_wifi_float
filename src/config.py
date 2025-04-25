# Desc: 配置文件解析模块
import tomlkit
from tomlkit.exceptions import NonExistentKey

class CfgParse:
    def __init__(self, path: str):
        """
        Args:
            - path : 配置文件路径
        :param path: str
        """
        self.path = path
        with open(path, 'r', encoding='utf-8') as f:
            self.cfg = tomlkit.load(f)
    def get_all(self):
        """
        获取所有配置项
        """
        return self.cfg
    def set_all(self,cfg):
        """
        设置所有配置项
        """
        with open(self.path, 'w', encoding='utf-8') as f:
            tomlkit.dump(cfg, f)
    def get(self, section: str, option: str, default=None, reloaded=False):
        """
        Args:
            - section : 配置文件的节名
            - option :  配置文件的项名
            - default : 默认值
            - reloaded : 是否重新加载配置文件(可以再次加载配置文件获取用户更改等等)
        :param reloaded:
        :param default:
        :param option:
        :param section:
        """
        try:
            if reloaded:
                with open(self.path, 'r', encoding='utf-8') as f:
                    self.cfg = tomlkit.load(f)
            return self.cfg[section][option]
        except NonExistentKey:
            return default

    def write(self, section: str, option: str, value):
        """
        Args:
            - section : 配置文件的节名
            - option :  配置文件的项名
            - value :  写入的值
        :param value:
        :param option:
        :param section:
        """
        if section not in self.cfg:
            self.cfg.update({section: {option: value}})
        elif option not in self.cfg[section]:
            self.cfg[section].update({option: value})
        self.set_all(self.cfg)