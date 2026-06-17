# Desc: 配置文件解析模块
import tomlkit
from tomlkit.exceptions import NonExistentKey


class CfgParse:
    # 类级缓存：path -> TOMLDocument，同路径实例共享缓存，减少磁盘 I/O
    _cache = {}

    def __init__(self, path: str):
        self.path = path
        self._ensure_cache()

    def _ensure_cache(self):
        """缓存未命中时从磁盘加载"""
        if self.path not in self._cache:
            with open(self.path, 'r', encoding='utf-8') as f:
                self._cache[self.path] = tomlkit.load(f)

    def reload(self):
        """强制从磁盘重载并更新缓存"""
        with open(self.path, 'r', encoding='utf-8') as f:
            self._cache[self.path] = tomlkit.load(f)

    def get_all(self):
        """获取所有配置项（直接从缓存读取）"""
        self._ensure_cache()
        return self._cache[self.path]

    def set_all(self, cfg):
        """写入全部配置项，同步更新缓存"""
        self._cache[self.path] = cfg
        with open(self.path, 'w', encoding='utf-8') as f:
            tomlkit.dump(cfg, f)

    def get(self, section: str, option: str, default=None):
        """
        Args:
            section : 配置文件的节名
            option  : 配置文件的项名
            default : 默认值
        """
        self._ensure_cache()
        try:
            return self._cache[self.path][section][option]
        except (NonExistentKey, KeyError):
            return default

    def write(self, section: str, option: str, value):
        """写入单个配置项，写前从磁盘重载以防冲突"""
        self.reload()
        doc = self._cache[self.path]
        if section not in doc:
            doc[section] = {option: value}
        else:
            doc[section][option] = value
        with open(self.path, 'w', encoding='utf-8') as f:
            tomlkit.dump(doc, f)