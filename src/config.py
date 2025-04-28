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
        self.cfg = None
        self.reload()
    def reload(self):
        with open(self.path, 'r', encoding='utf-8') as f:
            self.cfg = tomlkit.load(f)
    def get_all(self):
        """
        获取所有配置项
        """
        self.reload()
        return self.cfg
    def set_all(self,cfg):
        """
        设置所有配置项
        """
        self.reload()
        with open(self.path, 'w', encoding='utf-8') as f:
            tomlkit.dump(cfg, f)
    def get(self, section: str, option: str, default=None):
        """
        Args:
            - section : 配置文件的节名
            - option :  配置文件的项名
            - default : 默认值
        :param default:
        :param option:
        :param section:
        """
        try:
            self.reload()
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
        self.reload()
        if section not in self.cfg:
            self.cfg.update({section: {option: value}})
        elif option not in self.cfg[section]:
            self.cfg[section].update({option: value})
        else:
            self.cfg[section][option] = value
        self.set_all(self.cfg)