# Desc: 配置文件解析模块
import tomlkit
from tomlkit.exceptions import NonExistentKey


class CfgParse:
    # 类级缓存：path -> TOMLDocument，同路径实例共享缓存，减少磁盘 I/O
    _cache = {}
    _MAX_CACHE = 32  # 最多缓存 32 个文件，防止插件/临时路径无限增长

    def __init__(self, path: str):
        self.path = path
        self._ensure_cache()

    def _ensure_cache(self):
        """缓存未命中时从磁盘加载，超出上限时淘汰最早未使用的缓存"""
        if self.path not in self._cache:
            # 淘汰机制：超出上限时清空缓存（安全简单，config 文件数量通常 < 10）
            if len(self._cache) >= self._MAX_CACHE:
                self._cache.clear()
            with open(self.path, 'r', encoding='utf-8') as f:
                self._cache[self.path] = tomlkit.load(f)

    @classmethod
    def clear_cache(cls):
        """清空所有缓存（在程序退出或测试时调用）"""
        cls._cache.clear()

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

    def write(self, section: str, option: str, value, reload_first: bool = True):
        """写入单个配置项

        Args:
            section: 配置文件的节名
            option: 配置文件的项名
            value: 要写入的值
            reload_first: 写入前是否从磁盘重载（默认 True 以防外部修改冲突）。
                          纯写入高频场景（如保存窗口坐标）可设为 False 以减少 I/O。
        """
        if reload_first:
            self.reload()
        doc = self._cache[self.path]
        if section not in doc:
            doc[section] = {option: value}
        else:
            doc[section][option] = value
        with open(self.path, 'w', encoding='utf-8') as f:
            tomlkit.dump(doc, f)