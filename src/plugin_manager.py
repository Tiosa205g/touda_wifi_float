import pluggy
import os
import sys
import importlib.util
from .config import CfgParse
from .logging_config import logger


class Api:
    """通过start返回给插件的类，可以调用已实例化的类"""
    def __init__(self,wifi,webvpn,version,cfg_dir,main_cfg,links_cfg,app=None,parent=None):
        self.wifi = wifi
        self.webvpn = webvpn
        self.cfg = CfgParse
        self.VERSION = version
        self.CFG_DIR = cfg_dir
        self.MAIN_CFG = main_cfg
        self.LINKS_CFG = links_cfg
        self.logger = logger
        self.app = app
        self.parent = parent
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
    def get_menu(self)->list[dict]: # list[功能 - function]
        """获取插件的菜单信息,需要返回list[{'function':'功能名','object':callable函数}]"""
    @hook
    def on_setting(self):
        """当设置按钮被点击"""
    @hook
    def on_disable(self):
        """当插件被禁用时"""
    @hook
    def on_exit(self):
        """程序退出时调用"""


# ── 插件发现 ──

def _plugin_id(plugin_root: str, dir_path: str) -> str:
    """插件唯一标识 = 相对插件根目录的路径（正斜杠分隔）"""
    rel = os.path.relpath(dir_path, plugin_root)
    return rel.replace(os.sep, "/")


def discover_plugins(plugin_root: str) -> list[dict]:
    """
    递归遍历插件根目录下的所有子目录，导入其中的 main.py。

    返回记录列表，每条记录：
      {'id', 'dir', 'main_py', 'module', 'cls', 'error'}
    导入失败的插件也会返回（module/cls 为 None，error 说明原因），
    供管理界面展示。不注册、不启动。
    """
    abs_root = os.path.abspath(plugin_root)
    if abs_root not in sys.path:
        sys.path.insert(0, abs_root)

    records = []
    for root, dirs, files in os.walk(plugin_root):
        if "main.py" not in files:
            continue
        main_py_path = os.path.join(root, "main.py")
        rec = {
            'id': _plugin_id(plugin_root, root),
            'dir': root,
            'main_py': main_py_path,
            'module': None,
            'cls': None,
            'error': None,
        }
        module_name = f"plugin_{root.replace(os.sep, '_')}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, main_py_path)
            if not spec or not spec.loader:
                rec['error'] = '无效的插件文件'
                records.append(rec)
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if not hasattr(module, "Plugin"):
                rec['error'] = '未找到 Plugin 类'
            elif not isinstance(module.Plugin, type):
                rec['error'] = 'Plugin 不是类'
            else:
                rec['module'] = module
                rec['cls'] = module.Plugin
                logger.info(f"已发现插件：{rec['id']}（来自 {main_py_path}）")
        except Exception as e:
            rec['error'] = f'导入失败: {e}'
            logger.info(f"加载插件失败 {main_py_path}：{str(e)}")
        records.append(rec)
    return records


# 3. 初始化插件管理器并加载所有插件
class Manager:
    def __init__(self,wifi,webvpn,version,cfg_dir,main_cfg,links_cfg,app=None,parent=None):
        self.api = Api(wifi,webvpn,version,cfg_dir,main_cfg,links_cfg,app,parent)
        # 创建插件管理器并注册钩子规范
        self.pm = pluggy.PluginManager("toudawifi")
        self.pm.add_hookspecs(PluginSpec)

        self._main_cfg = main_cfg
        # id -> 发现记录（含未启动/禁用/失败的插件）
        self._registry: dict[str, dict] = {}
        # 运行中的插件（保持旧字段兼容：name/description/object）
        self.plugins: list[dict] = []
        # 用户禁用的插件元数据（未 start，仅用于界面展示）
        self._disabled_meta: dict[str, dict] = {}
        # 加载/启动失败的插件及原因
        self._errors: dict[str, str] = {}

        disabled_ids = self._load_disabled_ids()
        # 加载 plugins 目录下所有子目录中的 main.py 插件
        for rec in discover_plugins("./plugins"):
            pid = rec['id']
            self._registry[pid] = rec
            if rec['cls'] is None:
                # 导入失败：记录错误，界面可显示
                self._errors[pid] = rec['error'] or '未知错误'
                continue
            if pid in disabled_ids:
                # 用户禁用：不 start，仅探测展示名称
                name, desc = self._probe_meta(rec)
                self._disabled_meta[pid] = {'name': name, 'description': desc}
                logger.info(f'插件已被禁用，跳过启动：{pid}')
                continue
            ok, err = self._start_plugin(pid)
            if not ok:
                self._errors[pid] = err

        logger.info(f'已加载的有效插件列表:{self.plugins}')

    # ── 内部：启动/探测 ──

    def _probe_meta(self, rec: dict) -> tuple:
        """未启动的插件探测 get_name/get_description（失败回退目录名）"""
        name, desc = rec['id'], ''
        try:
            inst = rec['cls']()
            try:
                name = inst.get_name() or rec['id']
            except Exception:
                pass
            try:
                desc = inst.get_description() or ''
            except Exception:
                pass
        except Exception:
            pass
        return name, desc

    def _start_plugin(self, pid: str) -> tuple:
        """实例化并启动插件，成功后注册进 pluggy。返回 (ok, error_msg)"""
        rec = self._registry.get(pid)
        if not rec or rec['cls'] is None:
            return False, '插件不存在或导入失败'
        try:
            instance = rec['cls']()
        except Exception as e:
            logger.exception(f'插件 {pid} 实例化失败')
            return False, f'实例化失败: {e}'
        try:
            ok = instance.start(self.api)
        except Exception as e:
            logger.exception(f'插件 {pid} 的 start 方法异常')
            return False, f'启动异常: {e}'
        if not ok:
            # start 返回 False → 释放插件自身资源（保持与旧逻辑一致）
            try:
                if callable(getattr(instance, 'on_disable', None)):
                    instance.on_disable()
            except Exception:
                logger.exception(f'插件 {pid} 的 on_disable 异常')
            return False, '插件启动失败（start 返回 False）'
        try:
            name = instance.get_name()
            description = instance.get_description()
        except Exception:
            logger.exception(f'插件 {instance} 的 get_name/get_description 异常，使用兜底名称')
            name, description = pid, ''
        try:
            self.pm.register(instance)
        except Exception:
            logger.exception(f'插件 {pid} 注册到 pluggy 失败')
            try:
                if callable(getattr(instance, 'on_disable', None)):
                    instance.on_disable()
            except Exception:
                pass
            return False, '插件注册失败'
        self.plugins.append({
            'id': pid,
            'name': name,
            'description': description,
            'object': instance,
        })
        return True, ''

    # ── 禁用状态持久化（config/main.toml [plugins] disabled） ──

    def _load_disabled_ids(self) -> set:
        try:
            cfg = CfgParse(self._main_cfg)
            raw = cfg.get('plugins', 'disabled', [])
            return {str(x) for x in (raw or [])}
        except Exception:
            logger.exception('读取插件禁用列表失败')
            return set()

    def _persist_disabled_ids(self):
        try:
            cfg = CfgParse(self._main_cfg)
            cfg.write('plugins', 'disabled', sorted(self._disabled_meta.keys()))
        except Exception:
            logger.exception('保存插件禁用列表失败')

    # ── 供设置界面使用 ──

    def get_plugin_entries(self) -> list[dict]:
        """返回管理界面用的插件清单（按发现顺序）。

        每条：{id, name, description, dir, state, error, object,
              has_setting, has_config}
        state: 'enabled' | 'disabled' | 'error'
        """
        running = {p['id']: p for p in self.plugins}
        entries = []
        for pid, rec in self._registry.items():
            if pid in running:
                p = running[pid]
                state, obj = 'enabled', p['object']
                name, desc = p['name'], p['description']
            elif pid in self._disabled_meta:
                state, obj = 'disabled', None
                name, desc = self._disabled_meta[pid]['name'], self._disabled_meta[pid]['description']
            else:
                state, obj = 'error', None
                if rec['cls'] is not None:
                    name, desc = self._probe_meta(rec)
                else:
                    name, desc = pid, ''
            entries.append({
                'id': pid,
                'name': name or pid,
                'description': desc or '',
                'dir': rec['dir'],
                'state': state,
                'error': self._errors.get(pid, ''),
                'object': obj,
                'has_setting': obj is not None and self.is_valid_func(obj, 'on_setting'),
                'has_config': os.path.exists(os.path.join(rec['dir'], 'config.toml')),
            })
        return entries

    def get_config_path(self, pid: str):
        """返回插件 config.toml 路径（不存在返回 None）"""
        rec = self._registry.get(pid)
        if not rec:
            return None
        path = os.path.join(rec['dir'], 'config.toml')
        return path if os.path.exists(path) else None

    def set_plugin_enabled(self, pid: str, enabled: bool) -> tuple:
        """运行时启用/禁用插件（立即生效）。返回 (ok, message)"""
        running = next((p for p in self.plugins if p['id'] == pid), None)
        if enabled:
            if running is not None:
                return True, '插件已处于启用状态'
            ok, err = self._start_plugin(pid)
            if not ok:
                self._errors[pid] = err
                return False, err
            # 启动成功：移出禁用集合/错误集合
            self._disabled_meta.pop(pid, None)
            self._errors.pop(pid, None)
            self._persist_disabled_ids()
            self._notify_menus_changed()
            return True, ''
        # 禁用
        if running is None:
            # 未在运行（禁用/失败态）：仅记录禁用，跳过下次启动
            rec = self._registry.get(pid)
            name, desc = (pid, '')
            if rec and rec['cls'] is not None:
                name, desc = self._probe_meta(rec)
            self._disabled_meta[pid] = {'name': name, 'description': desc}
            self._errors.pop(pid, None)
            self._persist_disabled_ids()
            return True, ''
        obj = running['object']
        try:
            if callable(getattr(obj, 'on_disable', None)):
                obj.on_disable()
        except Exception:
            logger.exception(f'插件 {pid} 的 on_disable 异常')
        try:
            self.pm.unregister(obj)
        except Exception:
            logger.exception(f'插件 {pid} 从 pluggy 注销失败')
        self.plugins.remove(running)
        self._disabled_meta[pid] = {
            'name': running['name'],
            'description': running['description'],
        }
        self._persist_disabled_ids()
        self._notify_menus_changed()
        return True, ''

    def open_plg_setting_by_id(self, pid: str) -> tuple:
        """打开指定插件的设置界面（on_setting）。返回 (ok, message)"""
        running = next((p for p in self.plugins if p['id'] == pid), None)
        if running is None:
            return False, '插件未启用，无法打开其设置界面'
        return self._call_on_setting(running['object'])

    def _call_on_setting(self, plg) -> tuple:
        try:
            plg.on_setting()
            return True, ''
        except Exception as e:
            logger.exception(f'插件 {plg} 的 on_setting 异常')
            return False, f'打开设置失败: {e}'

    def _notify_menus_changed(self):
        """启用/禁用后通知悬浮球刷新右键菜单"""
        parent = getattr(self.api, 'parent', None)
        fn = getattr(parent, '_refresh_dynamic_menus', None)
        if callable(fn):
            try:
                fn(force=True)
            except Exception:
                logger.exception('刷新右键菜单失败')

    def shutdown(self):
        """程序退出时调用所有插件的 on_exit 钩子，释放插件持有的资源"""
        for plg in self.plugins:
            obj = plg["object"]
            if callable(getattr(obj, "on_exit", None)):
                try:
                    obj.on_exit()
                except Exception:
                    logger.exception(f"插件 {plg.get('name', '?')} on_exit 异常")

    def open_plg_setting(self, plg):
        self._call_on_setting(plg)

    def is_valid_func(self,plg,func_name:str)->bool:
        return callable(getattr(plg,func_name,None))


# if __name__ == "__main__":
#     pm = Manager(None,None) # 测试
#     first_plg = pm.plugins[0]
