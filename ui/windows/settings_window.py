import ast
import os
import sys
import subprocess
import winreg
import base64
from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets import (
    FluentWindow,
    NavigationItemPosition,
    ScrollArea,
    LineEdit,
    SpinBox,
    PasswordLineEdit,
    ComboBox,
    EditableComboBox,
    PushButton,
    StrongBodyLabel,
    InfoBar,
    FluentIcon as FIF,
    Dialog,
    setTheme,
    Theme,
    isDarkTheme,
    FluentTitleBar,
    SwitchButton,
)

from src.config import CfgParse
from src.logging_config import logger


def _get_config_dir() -> str:
    return os.path.join(os.getcwd(), "config")

def _get_main_cfg() -> str:
    return os.path.join(_get_config_dir(), "main.toml")

def _get_links_cfg() -> str:
    return os.path.join(_get_config_dir(), "links.toml")


def ensure_cfg():
    cfg_dir = _get_config_dir()
    if not os.path.isdir(cfg_dir):
        os.makedirs(cfg_dir, exist_ok=True)
    for p in (_get_main_cfg(), _get_links_cfg()):
        if not os.path.exists(p):
            try:
                with open(p, 'a', encoding='utf-8'):
                    pass
            except Exception:
                pass


def list_account_files() -> List[str]:
    ensure_cfg()
    files = []
    cfg_dir = _get_config_dir()
    for f in os.listdir(cfg_dir):
        if f.startswith("account_") and f.endswith(".toml"):
            files.append(os.path.join(cfg_dir, f))
    # sort by index number
    def _idx(name: str) -> int:
        try:
            base = os.path.basename(name)
            return int(base.replace("account_", "").replace(".toml", ""))
        except Exception:
            return 0
    files.sort(key=_idx)
    return files


def read_b64(s: str) -> str:
    try:
        return base64.b64decode(s.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def write_b64(s: str) -> str:
    try:
        return base64.b64encode(s.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


class _BaseInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scrollWidget = QWidget()
        # 使用透明背景以适配浅/深主题，由外层窗口样式负责上色
        self.scrollWidget.setStyleSheet("background: transparent;")
        self.vLayout = QVBoxLayout(self.scrollWidget)
        self.vLayout.setContentsMargins(36, 20, 36, 20)
        self.vLayout.setSpacing(20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        # 让滚动区域视口也透明，避免在深色主题下显示浅色底
        try:
            self.viewport().setStyleSheet("background: transparent;")
        except Exception:
            pass
        # 关键：避免中间层成为原生窗口，防止下拉框弹出时将其视为父级导致
        # “QWidgetWindow(... ) must be a top level window” 的报错
        try:
            self.setAttribute(Qt.WA_NativeWindow, False)
            self.setAttribute(Qt.WA_DontCreateNativeAncestors, True)
            self.scrollWidget.setAttribute(Qt.WA_NativeWindow, False)
            self.viewport().setAttribute(Qt.WA_NativeWindow, False)
        except Exception:
            pass

    def addGroup(self, title: str):
        """创建一个简单分组容器，返回其 QVBoxLayout，可直接 addWidget(row)"""
        groupWidget = QWidget(self.scrollWidget)
        groupLayout = QVBoxLayout(groupWidget)
        groupLayout.setContentsMargins(12, 4, 12, 4)
        groupLayout.setSpacing(8)
        titleLabel = StrongBodyLabel(title, groupWidget)
        # 不在此处固定颜色，交由外层 QSS 根据主题决定
        titleLabel.setStyleSheet("font-weight: bold;")
        groupLayout.addWidget(titleLabel)
        self.vLayout.addWidget(groupWidget)
        return groupLayout

    def addFooterSpacer(self):
        self.vLayout.addStretch(1)


class GeneralInterface(_BaseInterface):
    """常规设置：打开配置文件夹"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mainCfg = CfgParse(_get_main_cfg())
        self._update_thread = None
        self._update_worker = None

        # 常规：WiFi 状态检查间隔（秒）
        g_account = self.addGroup("常规")

        rowInterval = QWidget(self.scrollWidget)
        h1 = QHBoxLayout(rowInterval)
        h1.setContentsMargins(12, 8, 12, 8)
        h1.setSpacing(12)
        self.spinInterval = SpinBox(rowInterval)
        self.spinInterval.setRange(10, 3600)  # 秒
        self.spinInterval.setSingleStep(10)
        # 读取配置（毫秒），转换为秒
        interval_ms = self.mainCfg.get('main', 'timer_interval', 60000)
        try:
            interval_s = max(10, int(int(interval_ms) / 1000))
        except Exception:
            interval_s = 60
        self.spinInterval.setValue(interval_s)
        self.btnSaveInterval = PushButton("保存")
        self.btnOpenDir = PushButton("打开配置文件夹")
        self.btnOpenDir.clicked.connect(lambda: os.startfile(_get_config_dir()))
        self.btnSaveInterval.clicked.connect(self.saveInterval)
        h1.addWidget(StrongBodyLabel("WiFi 状态检查间隔(秒):"))
        h1.addWidget(self.spinInterval)
        h1.addWidget(self.btnSaveInterval)
        h1.addWidget(self.btnOpenDir)
        h1.addStretch(1)
        g_account.addWidget(rowInterval)

        # 主题选择（自动/浅色/深色）
        rowTheme = QWidget(self.scrollWidget)
        h2 = QHBoxLayout(rowTheme)
        h2.setContentsMargins(12, 8, 12, 8)
        h2.setSpacing(12)
        self.cmbTheme = ComboBox(rowTheme)
        self.cmbTheme.addItems(["自动", "浅色", "深色"])
        # 避免 ComboBox 弹出层找错父级
        try:
            self.cmbTheme.setAttribute(Qt.WA_DontCreateNativeAncestors, True)
        except Exception:
            pass
        # 从配置读取默认主题
        theme_value = str(self.mainCfg.get('ui', 'theme', 'auto') or 'auto').lower()
        idx_map = { 'auto': 0, 'light': 1, 'dark': 2 }
        self.cmbTheme.setCurrentIndex(idx_map.get(theme_value, 0))
        # 选择变化即刻应用并保存
        self.cmbTheme.currentIndexChanged.connect(self.applyTheme)
        h2.addWidget(StrongBodyLabel("主题: "))
        h2.addWidget(self.cmbTheme)
        h2.addStretch(1)
        g_account.addWidget(rowTheme)

        # ── 启动管理 ──
        g_startup = self.addGroup("启动")

        # 开机自启（注册表 HKCU\Run）
        rowAutoStart = QWidget(self.scrollWidget)
        h3 = QHBoxLayout(rowAutoStart)
        h3.setContentsMargins(12, 8, 12, 8)
        h3.setSpacing(12)
        self.switchAutoStart = SwitchButton(rowAutoStart)
        self.switchAutoStart.setOnText("开")
        self.switchAutoStart.setOffText("关")
        self.switchAutoStart.checkedChanged.connect(self.toggleAutoStart)
        h3.addWidget(StrongBodyLabel("开机自启:"))
        h3.addWidget(self.switchAutoStart)
        h3.addStretch(1)
        g_startup.addWidget(rowAutoStart)

        # 管理员启动
        rowAdmin = QWidget(self.scrollWidget)
        h4 = QHBoxLayout(rowAdmin)
        h4.setContentsMargins(12, 8, 12, 8)
        h4.setSpacing(12)
        self.switchAdmin = SwitchButton(rowAdmin)
        self.switchAdmin.setOnText("开")
        self.switchAdmin.setOffText("关")
        self.switchAdmin.checkedChanged.connect(self.toggleAdmin)
        h4.addWidget(StrongBodyLabel("管理员启动:"))
        h4.addWidget(self.switchAdmin)
        h4.addStretch(1)
        g_startup.addWidget(rowAdmin)

        # 静默启动
        rowSilent = QWidget(self.scrollWidget)
        h5 = QHBoxLayout(rowSilent)
        h5.setContentsMargins(12, 8, 12, 8)
        h5.setSpacing(12)
        self.switchSilent = SwitchButton(rowSilent)
        self.switchSilent.setOnText("开")
        self.switchSilent.setOffText("关")
        self.switchSilent.checkedChanged.connect(self.toggleSilent)
        h5.addWidget(StrongBodyLabel("静默启动:"))
        h5.addWidget(self.switchSilent)
        h5.addStretch(1)
        g_startup.addWidget(rowSilent)

        # 加载启动配置状态
        self._load_startup_config()

        # ── 更新管理 ──
        g_update = self.addGroup("更新")

        # 自动检查更新
        rowAutoUpdate = QWidget(self.scrollWidget)
        h6 = QHBoxLayout(rowAutoUpdate)
        h6.setContentsMargins(12, 8, 12, 8)
        h6.setSpacing(12)
        self.switchAutoUpdate = SwitchButton(rowAutoUpdate)
        self.switchAutoUpdate.setOnText("开")
        self.switchAutoUpdate.setOffText("关")
        self.switchAutoUpdate.checkedChanged.connect(self.toggleAutoUpdate)
        h6.addWidget(StrongBodyLabel("自动检查更新:"))
        h6.addWidget(self.switchAutoUpdate)
        h6.addStretch(1)
        g_update.addWidget(rowAutoUpdate)

        # 检查更新按钮
        rowCheckNow = QWidget(self.scrollWidget)
        h7 = QHBoxLayout(rowCheckNow)
        h7.setContentsMargins(12, 8, 12, 8)
        h7.setSpacing(12)
        self.btnCheckNow = PushButton("立即检查更新")
        self.btnCheckNow.setFixedWidth(130)
        self.btnCheckNow.clicked.connect(self.checkUpdateNow)
        h7.addWidget(self.btnCheckNow)
        h7.addStretch(1)
        g_update.addWidget(rowCheckNow)

        # 加载更新配置状态
        self._load_update_config()

        self.addFooterSpacer()

    def _load_startup_config(self):
        """从配置和注册表加载启动相关的开关状态（阻止信号触发通知）"""
        # 阻断信号，避免 setChecked 触发 checkedChanged → InfoBar 弹窗
        self.switchAutoStart.blockSignals(True)
        self.switchAdmin.blockSignals(True)
        self.switchSilent.blockSignals(True)
        try:
            # 开机自启：检查注册表
            self.switchAutoStart.setChecked(self._is_auto_start_enabled())
            # 管理员启动 & 静默启动：从配置读取
            admin = self.mainCfg.get('startup', 'run_as_admin', False)
            self.switchAdmin.setChecked(str(admin).lower() == 'true' or admin is True)
            silent = self.mainCfg.get('startup', 'silent', False)
            self.switchSilent.setChecked(str(silent).lower() == 'true' or silent is True)
        finally:
            self.switchAutoStart.blockSignals(False)
            self.switchAdmin.blockSignals(False)
            self.switchSilent.blockSignals(False)

    @staticmethod
    def _is_auto_start_enabled() -> bool:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ
            )
            val, _ = winreg.QueryValueEx(key, "ToudaWiFi")
            winreg.CloseKey(key)
            # 注册表值可能带参数：C:\path\main.exe --auto-start
            # 或带引号："python.exe" "main.py" --auto-start
            # 需要提取出真正的可执行文件路径
            if val.startswith('"'):
                exe_path = val.split('"')[1]
            else:
                exe_path = val.split(maxsplit=1)[0]
            return os.path.exists(exe_path)
        except FileNotFoundError:
            return False
        except Exception:
            return False

    @staticmethod
    def _is_source() -> bool:
        """检测是否为源码运行（而非打包 exe）"""
        return sys.argv[0].endswith('.py')

    @staticmethod
    def _get_app_exe_path() -> str:
        """获取可执行文件路径（兼容 exe 和 .py 运行模式）"""
        if GeneralInterface._is_source():
            # 源码运行：python.exe + main.py 全路径
            main_py = os.path.join(os.getcwd(), 'main.py')
            if os.path.exists(main_py):
                return f'"{sys.executable}" "{main_py}"'
            # fallback
            return sys.executable
        # Nuitka 打包的 exe
        return sys.executable

    def toggleAutoStart(self, checked: bool):
        """开关开机自启注册表项"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            if checked:
                exe_path = self._get_app_exe_path() + " --auto-start"
                winreg.SetValueEx(key, "ToudaWiFi", 0, winreg.REG_SZ, exe_path)
                InfoBar.success(title='已开启', content='开机自启已启用', duration=1500, parent=self)
            else:
                try:
                    winreg.DeleteValue(key, "ToudaWiFi")
                except FileNotFoundError:
                    pass
                InfoBar.info(title='已关闭', content='开机自启已禁用', duration=1500, parent=self)
            winreg.CloseKey(key)
        except Exception as e:
            InfoBar.error(title='操作失败', content=str(e), duration=2000, parent=self)
            # 回退开关状态
            self.switchAutoStart.setChecked(not checked)

    def toggleAdmin(self, checked: bool):
        """开关管理员启动（写入配置，启动时自动提权）"""
        if self._is_source() and checked:
            # 源码运行：提示不支持，回退开关
            InfoBar.warning(title='提示', content='源码运行无需管理员权限，打包为 exe 后生效', duration=3000, parent=self)
            self.switchAdmin.blockSignals(True)
            self.switchAdmin.setChecked(False)
            self.switchAdmin.blockSignals(False)
            return
        self.mainCfg.write('startup', 'run_as_admin', checked)
        if checked:
            InfoBar.success(title='已开启', content='下次启动时将自动请求管理员权限', duration=2000, parent=self)
        else:
            InfoBar.info(title='已关闭', content='管理员启动已禁用', duration=1500, parent=self)

    def toggleSilent(self, checked: bool):
        """开关静默启动（写入配置，启动时自动隐藏窗口）"""
        self.mainCfg.write('startup', 'silent', checked)
        if checked:
            InfoBar.success(title='已开启', content='下次启动时窗口将自动隐藏到托盘', duration=2000, parent=self)
        else:
            InfoBar.info(title='已关闭', content='静默启动已禁用', duration=1500, parent=self)

    def saveInterval(self):
        seconds = int(self.spinInterval.value())
        ms = max(10000, seconds * 1000)
        self.mainCfg.write('main', 'timer_interval', ms)
        InfoBar.success(title='已保存', content=f'已设置间隔为 {seconds} 秒，重启软件后生效', duration=1500, parent=self)

    def applyTheme(self, *_):
        idx = self.cmbTheme.currentIndex()
        val = 'auto' if idx == 0 else ('light' if idx == 1 else 'dark')
        self.mainCfg.write('ui', 'theme', val)
        t = Theme.AUTO if val == 'auto' else (Theme.LIGHT if val == 'light' else Theme.DARK)
        try:
            setTheme(t)
        except Exception:
            pass
        # 通知父窗口更新样式
        try:
            sw = self.window()
            if hasattr(sw, 'applyCustomStyleForTheme'):
                is_dark = t == Theme.DARK or (t == Theme.AUTO and isDarkTheme())
                sw.applyCustomStyleForTheme(Theme.DARK if is_dark else Theme.LIGHT)
        except Exception:
            pass
        InfoBar.success(title='已应用', content=f'主题已切换为 {self.cmbTheme.currentText()}', duration=1200, parent=self)

    def _load_update_config(self):
        """加载更新相关的配置状态"""
        self.switchAutoUpdate.blockSignals(True)
        try:
            auto_check = self.mainCfg.get('update', 'auto_check', True)
            self.switchAutoUpdate.setChecked(str(auto_check).lower() == 'true' or auto_check is True)
        finally:
            self.switchAutoUpdate.blockSignals(False)

    def toggleAutoUpdate(self, checked: bool):
        """开关自动检查更新"""
        self.mainCfg.write('update', 'auto_check', checked)
        if checked:
            InfoBar.success(title='已开启', content='下次启动时将自动检查更新', duration=2000, parent=self)
        else:
            InfoBar.info(title='已关闭', content='启动时将不再自动检查更新', duration=1500, parent=self)

    def checkUpdateNow(self):
        """立即检查更新"""
        # 防止重复点击和线程泄漏
        try:
            thread_busy = (
                self._update_thread is not None
                and self._update_thread.isRunning()
            )
        except RuntimeError:
            thread_busy = False
            self._update_thread = None
            self._update_worker = None
        if thread_busy:
            return

        self.btnCheckNow.setEnabled(False)
        self.btnCheckNow.setText("检查中...")

        from src.update_checker import check_for_update
        from src.config import CfgParse
        from PySide6.QtCore import QTimer

        # 从 main.py 读取 VERSION（避免动态导入执行模块级副作用）
        import re as _re
        _version_file = os.path.join(os.getcwd(), 'main.py')
        current_version = 'v0.0.0'
        try:
            with open(_version_file, 'r', encoding='utf-8') as _f:
                _m = _re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', _f.read(), _re.MULTILINE)
                if _m:
                    current_version = _m.group(1)
        except Exception:
            pass

        # 用 list 做闭包容器存储线程结果，避免通过 Signal(object) 传递自定义对象（QueuedConnection 会序列化失败）
        _result = []

        def do_check():
            _result.append(check_for_update(current_version))

        def on_finished():
            self.btnCheckNow.setEnabled(True)
            self.btnCheckNow.setText("立即检查更新")
            if self._update_thread is thread and self._update_worker is worker:
                self._update_thread = None
                self._update_worker = None

            raw = _result[0] if _result else None
            if isinstance(raw, Exception) or raw is None:
                if raw is None:
                    InfoBar.info(title='已是最新版', content=f'当前 {current_version} 已是最新版本', duration=3000, parent=self)
                else:
                    InfoBar.error(title='检查失败', content='网络异常，请稍后重试', duration=3000, parent=self)
                return

            # 有新版本
            desc = raw.summary()
            from ui.components.update_dialog import UpdateDialog
            dlg = UpdateDialog(
                current_version=current_version,
                latest_tag=raw.tag_name,
                release_body=raw.body,
                download_url=raw.html_url,
                parent=self.window(),
            )
            dlg.exec()

        from src.touda import start_worker_in_thread
        thread, worker = start_worker_in_thread(do_check, "检查更新")
        from PySide6.QtCore import Qt as QtNS
        thread.finished.connect(on_finished, QtNS.QueuedConnection)
        self._update_thread = thread
        self._update_worker = worker


class WebVpnInterface(_BaseInterface):
    """WebVPN 设置：账号/密码/密钥，TWFID 操作"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mainCfg = CfgParse(_get_main_cfg())

        g_webvpn = self.addGroup("WebVPN")

        # name
        row_name = QWidget(self.scrollWidget)
        l = QHBoxLayout(row_name)
        l.setContentsMargins(12, 8, 12, 8)
        self.editName = LineEdit(row_name)
        self.editName.setPlaceholderText("webvpn 用户名")
        self.editName.setClearButtonEnabled(True)
        l.addWidget(StrongBodyLabel("用户名:"))
        l.addWidget(self.editName)
        g_webvpn.addWidget(row_name)

        # password
        row_pwd = QWidget(self.scrollWidget)
        l2 = QHBoxLayout(row_pwd)
        l2.setContentsMargins(12, 8, 12, 8)
        self.editPwd = PasswordLineEdit(row_pwd)
        self.editPwd.setPlaceholderText("webvpn 密码")
        l2.addWidget(StrongBodyLabel("密码:"))
        l2.addWidget(self.editPwd)
        g_webvpn.addWidget(row_pwd)

        # key
        row_key = QWidget(self.scrollWidget)
        l3 = QHBoxLayout(row_key)
        l3.setContentsMargins(12, 8, 12, 8)
        self.editKey = LineEdit(row_key)
        self.editKey.setPlaceholderText("生成动态口令(TOTP)密钥")
        self.editKey.setClearButtonEnabled(True)
        l3.addWidget(StrongBodyLabel("密钥:"))
        l3.addWidget(self.editKey)
        g_webvpn.addWidget(row_key)

        # buttons
        row_btn = QWidget(self.scrollWidget)
        l4 = QHBoxLayout(row_btn)
        l4.setContentsMargins(12, 8, 12, 8)
        self.btnSave = PushButton("保存")
        self.btnCopyTwfid = PushButton("复制 TWFID")
        self.btnClearTwfid = PushButton("清空 TWFID")
        # self.btnSave.setIcon(FIF.SAVE.icon())  # 移除图标，仅保留文字
        # self.btnCopyTwfid.setIcon(FIF.COPY.icon())  # 移除图标，仅保留文字
        # self.btnClearTwfid.setIcon(FIF.DELETE.icon())  # 移除图标，仅保留文字
        self.btnSave.clicked.connect(self.save)
        self.btnCopyTwfid.clicked.connect(self.copyTwfid)
        self.btnClearTwfid.clicked.connect(self.clearTwfid)
        l4.addWidget(self.btnSave)
        l4.addWidget(self.btnCopyTwfid)
        l4.addWidget(self.btnClearTwfid)
        l4.addStretch(1)
        g_webvpn.addWidget(row_btn)

        self.load()
        self.addFooterSpacer()

    def load(self):
        name = self.mainCfg.get('webvpn', 'name', '')
        pwd_b64 = self.mainCfg.get('webvpn', 'password', '')
        key = self.mainCfg.get('webvpn', 'key', '')
        self.editName.setText(name or "")
        self.editPwd.setText(read_b64(pwd_b64) if pwd_b64 else "")
        self.editKey.setText(key or "")

    def save(self):
        name = self.editName.text().strip()
        pwd = self.editPwd.text()
        key = self.editKey.text().strip()
        if not name or not pwd or not key:
            InfoBar.warning(title='缺少信息', content='请填写完整 用户名/密码/密钥', duration=2000, parent=self)
            return
        self.mainCfg.write('webvpn', 'name', name)
        self.mainCfg.write('webvpn', 'password', write_b64(pwd))
        self.mainCfg.write('webvpn', 'key', key)
        # 同步更新运行中的 webvpn 对象（类变量共享），无需重启立即生效
        from src.touda import webvpn as WebVpnCls
        WebVpnCls.update_config(name, pwd, key)
        InfoBar.success(title='已保存', content='WebVPN 设置已保存', duration=1500, parent=self)

    def copyTwfid(self):
        twfid = self.mainCfg.get('webvpn', 'twfid', '')
        if not twfid:
            InfoBar.info(title='空 TWFID', content='当前未保存 TWFID', duration=1500, parent=self)
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(str(twfid))
        InfoBar.success(title='已复制', content='TWFID 已复制到剪贴板', duration=1200, parent=self)

    def clearTwfid(self):
        # 清空登录态
        self.mainCfg.write('webvpn', 'twfid', '')
        InfoBar.success(title='已清空', content='已清空 TWFID,下次登录时将不再使用', duration=1200, parent=self)


class AccountsInterface(_BaseInterface):
    """账户管理：新增/修改/删除 WiFi 账户"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mainCfg = CfgParse(_get_main_cfg())

        g = self.addGroup("WiFi账户管理")

        # selector row
        row = QWidget(self.scrollWidget)
        hl = QHBoxLayout(row)
        hl.setContentsMargins(12, 8, 12, 8)
        self.combo = ComboBox(row)
        self.combo.setMinimumWidth(260)
        try:
            self.combo.setAttribute(Qt.WA_DontCreateNativeAncestors, True)
        except Exception:
            pass
        self.btnRefresh = PushButton("刷新")
        self.btnAdd = PushButton("添加")
        self.btnEdit = PushButton("修改")
        self.btnDel = PushButton("删除")
        self.btnMakeCurrent = PushButton("设为当前")
        # for b in (self.btnRefresh, self.btnAdd, self.btnEdit, self.btnDel, self.btnMakeCurrent):
        #     b.setIcon(FIF.ADD_TO.icon() if b is self.btnAdd else b.icon())  # 移除所有图标，仅保留文字
        self.combo.currentIndexChanged.connect(self.load_current_to_editor)
        self.btnRefresh.clicked.connect(self.reload)
        self.btnAdd.clicked.connect(self.addAccount)
        self.btnEdit.clicked.connect(self.saveEdit)
        self.btnDel.clicked.connect(self.deleteAccount)
        self.btnMakeCurrent.clicked.connect(self.makeCurrent)
        hl.addWidget(StrongBodyLabel("选择账号:"))
        hl.addWidget(self.combo, 1)
        hl.addWidget(self.btnRefresh)
        hl.addWidget(self.btnAdd)
        hl.addWidget(self.btnEdit)
        hl.addWidget(self.btnDel)
        hl.addWidget(self.btnMakeCurrent)
        g.addWidget(row)

        # editor row
        row2 = QWidget(self.scrollWidget)
        hl2 = QHBoxLayout(row2)
        hl2.setContentsMargins(12, 8, 12, 8)
        self.editName = LineEdit(row2)
        self.editName.setPlaceholderText("WiFi 账号")
        self.editPwd = PasswordLineEdit(row2)
        self.editPwd.setPlaceholderText("WiFi 密码")
        #self.btnSave = PushButton("保存修改")
        #self.btnSave.setIcon(FIF.SAVE.icon())
        #self.btnSave.clicked.connect(self.save)
        hl2.addWidget(StrongBodyLabel("名称:"))
        hl2.addWidget(self.editName)
        hl2.addWidget(StrongBodyLabel("密码:"))
        hl2.addWidget(self.editPwd)
        #hl2.addWidget(self.btnSave)
        g.addWidget(row2)

        self.reload()
        self.addFooterSpacer()

    def reload(self):
        self.combo.clear()
        self.accounts = list_account_files()
        for i, p in enumerate(self.accounts):
            cfg = CfgParse(p)
            name = cfg.get('setting', 'name', f"account_{i}")
            self.combo.addItem(f"{i} - {name}", userData=i)
        if self.combo.count() > 0:
            self.combo.setCurrentIndex(0)
            self.load_current_to_editor()

    def load_current_to_editor(self):
        if self.combo.count() == 0:
            self.editName.setText("")
            self.editPwd.setText("")
            return
        idx = self.combo.currentData()
        path = self.accounts[idx]
        cfg = CfgParse(path)
        name = cfg.get('setting', 'name', '')
        pwd_b64 = cfg.get('setting', 'password', '')
        self.editName.setText(name or "")
        self.editPwd.setText(read_b64(pwd_b64) if pwd_b64 else "")

    def addAccount(self):
        # 创建一个新的连续 index 文件
        files = list_account_files()
        # 找到最小可用索引
        used = set()
        for p in files:
            base = os.path.basename(p)
            try:
                used.add(int(base.replace('account_', '').replace('.toml', '')))
            except Exception:
                pass
        idx = 0
        while idx in used:
            idx += 1
        new_path = os.path.join(_get_config_dir(), f"account_{idx}.toml")
        open(new_path, 'w', encoding='utf-8').close()
        name = self.editName.text().strip() or "new_user"
        pwd = self.editPwd.text()
        cfg = CfgParse(new_path)
        cfg.write('setting', 'name', name)
        cfg.write('setting', 'password', write_b64(pwd))
        InfoBar.success(title='已添加', content=f'创建 account_{idx}.toml', duration=1500, parent=self)
        self.reload()

    def saveEdit(self):
        if self.combo.count() == 0:
            InfoBar.error(title='无账号', content='请先添加账号', duration=1500, parent=self)
            return
        idx = self.combo.currentData()
        path = self.accounts[idx]
        cfg = CfgParse(path)
        cfg.write('setting', 'name', self.editName.text().strip())
        cfg.write('setting', 'password', write_b64(self.editPwd.text()))
        InfoBar.success(title='已保存', content='账号信息已保存', duration=1200, parent=self)
        self.reload()

    def deleteAccount(self):
        if self.combo.count() == 0:
            return
        idx = self.combo.currentData()
        # 0 号不允许删除（保持和命令行工具一致的约束）
        if idx == 0:
            InfoBar.warning(title='不允许删除', content='0 号账户不能删除，只能修改', duration=2000, parent=self)
            return
        base = os.path.basename(self.accounts[idx])
        if Dialog("确认删除", f"确定删除 {base} ?").exec():
            try:
                os.remove(self.accounts[idx])
                InfoBar.success(title='已删除', content=base, duration=1200, parent=self)
            except Exception as e:
                InfoBar.error(title='删除失败', content=str(e), duration=2000, parent=self)
            self.reload()

    def makeCurrent(self):
        if self.combo.count() == 0:
            return
        idx = self.combo.currentData()
        self.mainCfg.write('main', 'current_account', int(idx))
        InfoBar.success(title='已更新', content=f'当前账号: {idx}', duration=1200, parent=self)


class LinksInterface(_BaseInterface):
    """链接管理：简单的按类别管理、导入/导出"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.linksCfg = CfgParse(_get_links_cfg())

        g = self.addGroup("链接管理")

        row1 = QWidget(self.scrollWidget)
        h1 = QHBoxLayout(row1)
        h1.setContentsMargins(12, 8, 12, 8)
        h1.setSpacing(12)
        self.btnAddOrUpdate = PushButton("新增/更新")
        self.btnDelete = PushButton("删除")
        self.btnExport = PushButton("导出当前类别")
        self.btnImport = PushButton("导入到当前类别")
        self.btnAddOrUpdate.clicked.connect(self.add_or_update)
        self.btnDelete.clicked.connect(self.delete)
        self.btnExport.clicked.connect(self.export_type)
        self.btnImport.clicked.connect(self.import_to_type)
        h1.addWidget(self.btnAddOrUpdate)
        h1.addWidget(self.btnDelete)
        h1.addWidget(self.btnExport)
        h1.addWidget(self.btnImport)
        h1.addStretch(1)
        g.addWidget(row1)

        # 操作区：类别、名称、链接 + 按钮
        row2 = QWidget(self.scrollWidget)
        h2 = QHBoxLayout(row2)
        h2.setContentsMargins(12, 8, 12, 8)
        h2.setSpacing(12)
        self.cmbType = EditableComboBox(row2)
        self.cmbType.setMinimumWidth(180)
        try:
            self.cmbType.setAttribute(Qt.WA_DontCreateNativeAncestors, True)
        except Exception:
            pass
        # 设置占位符文本提示用户可输入
        try:
            self.cmbType.setPlaceholderText("输入或选择类别")
        except Exception:
            pass
        # 启用清除按钮
        try:
            self.cmbType.setClearButtonEnabled(True)
        except Exception:
            pass
        try:
            self.cmbType.currentIndexChanged.connect(self.reload_names)
            self.cmbType.editTextChanged.connect(self.reload_names)
        except Exception:
            pass
        h2.addWidget(StrongBodyLabel("类别:"))
        h2.addWidget(self.cmbType, 1)
        g.addWidget(row2)

        # 名称行
        self.cmbName = EditableComboBox(self.scrollWidget)
        self.cmbName.setMinimumWidth(280)
        try:
            self.cmbName.setAttribute(Qt.WA_DontCreateNativeAncestors, True)
        except Exception:
            pass
        try:
            self.cmbName.setPlaceholderText("输入或选择名称")
            self.cmbName.setClearButtonEnabled(True)
        except Exception:
            pass
        rowName = QWidget(self.scrollWidget)
        hlName = QHBoxLayout(rowName)
        hlName.setContentsMargins(12, 4, 12, 4)
        hlName.setSpacing(12)
        hlName.addWidget(StrongBodyLabel("名称:"))
        hlName.addWidget(self.cmbName, 1)
        g.addWidget(rowName)

        # 链接行（更长、更易点）
        self.editLink = LineEdit(self.scrollWidget)
        self.editLink.setPlaceholderText("输入完整链接，如：https://example.com")
        try:
            self.editLink.setClearButtonEnabled(True)
        except Exception:
            pass
        self.editLink.setMinimumWidth(700)
        rowLink = QWidget(self.scrollWidget)
        hlLink = QHBoxLayout(rowLink)
        hlLink.setContentsMargins(12, 4, 12, 4)
        hlLink.setSpacing(12)
        hlLink.addWidget(StrongBodyLabel("链接:"))
        hlLink.addWidget(self.editLink, 1)
        g.addWidget(rowLink)

        self.reload_types()
        try:
            self.cmbName.currentIndexChanged.connect(self.on_name_selected)
            self.cmbName.editTextChanged.connect(self.on_name_selected)
        except Exception:
            pass
        self.addFooterSpacer()

        self.on_name_selected()

    def _load_all(self) -> Dict:
        try:
            return dict(self.linksCfg.get_all())
        except Exception:
            return {}

    def reload_types(self):
        self.cmbType.clear()
        data = self._load_all()
        for t in data.keys():
            self.cmbType.addItem(str(t))
        # 如果没有类别，先放一个默认
        if self.cmbType.count() == 0:
            self.cmbType.addItem("常用")
        self.reload_names()

    def reload_names(self):
        self.cmbName.clear()
        data = self._load_all()
        t = self.cmbType.currentText()
        names = []
        if t in data and isinstance(data[t], dict):
            names = list(data[t].keys())
        for n in names:
            self.cmbName.addItem(n)

    def on_name_selected(self):
        data = self._load_all()
        t = self.cmbType.currentText()
        n = self.cmbName.currentText()
        if t in data and isinstance(data[t], dict) and n in data[t]:
            self.cmbName.setCurrentText(n)
            self.editLink.setText(str(data[t][n]))

    def add_or_update(self):
        t = self.cmbType.currentText().strip() or "常用"
        n = self.cmbName.currentText().strip()
        link = self.editLink.text().strip()
        if not n or not link:
            InfoBar.warning(title='缺少信息', content='请填写 名称 与 链接', duration=1500, parent=self)
            return
        data = self._load_all()
        data.setdefault(t, {})
        data[t][n] = link
        self.linksCfg.set_all(data)
        InfoBar.success(title='已保存', content=f'[{t}] {n}', duration=1200, parent=self)
        self.reload_types()

    def delete(self):
        t = self.cmbType.currentText().strip()
        n = self.cmbName.currentText().strip()
        data = self._load_all()
        if not t or t not in data or n not in data[t]:
            return
        if Dialog("确认删除", f"删除 [{t}]/{n} ?").exec():
            del data[t][n]
            if not data[t]:
                del data[t]
            self.linksCfg.set_all(data)
            InfoBar.success(title='已删除', content=f'[{t}] {n}', duration=1200, parent=self)
            self.reload_types()

    def export_type(self):
        # 将当前类别导出为 base64 以兼容 init.py 的逻辑
        t = self.cmbType.currentText().strip()
        data = self._load_all()
        if t not in data:
            InfoBar.info(title='无数据', content='该类别下没有链接', duration=1200, parent=self)
            return
        from PySide6.QtWidgets import QApplication
        s = str(data[t])
        b64 = base64.b64encode(s.encode('utf-8')).decode('utf-8')
        QApplication.clipboard().setText(b64)
        InfoBar.success(title='已复制', content='导出内容已复制到剪贴板', duration=1500, parent=self)

    def import_to_type(self):
        # 从 base64 文本导入到指定类别（覆盖/合并）
        from PySide6.QtWidgets import QApplication
        b64 = QApplication.clipboard().text().strip()
        try:
            text = base64.b64decode(b64.encode('utf-8')).decode('utf-8')
            # 使用 ast.literal_eval 替代 eval，避免执行任意代码的安全风险
            obj = ast.literal_eval(text)
            if not isinstance(obj, dict):
                raise ValueError('内容不是 dict 类型')
        except Exception as e:
            InfoBar.error(title='导入失败', content=str(e), duration=2000, parent=self)
            return
        t = self.cmbType.currentText().strip() or "常用"
        data = self._load_all()
        data.setdefault(t, {})
        # 合并（覆盖已存在同名）
        data[t].update(obj)
        self.linksCfg.set_all(data)
        InfoBar.success(title='导入成功', content=f'已导入到 [{t}]', duration=1500, parent=self)
        self.reload_types()


class SettingsWindow(FluentWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        ensure_cfg()  # 确保配置目录和文件存在（一次即可）
        self.setWindowTitle('设置 - Touda WiFi')
        self.setFixedSize(1000, 600)  # 固定宽度 1000，高度 600
        self.setResizeEnabled(False)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        # 独立窗口
        self.setWindowFlags(Qt.Window)
        try:
            self.setWindowIcon(QIcon('res/ico/favicon.ico'))
        except Exception:
            pass
        # 使用 qfluent-widgets 的 FluentTitleBar 作为标题栏
        titleBar = FluentTitleBar(self)
        self.setTitleBar(titleBar)
        # 隐藏最小化和最大化按钮
        titleBar.minBtn.hide()
        titleBar.maxBtn.hide()
        self.titleBar.setDoubleClickEnabled(False) # 禁止双击最大化/还原
        
        # 优先启用云母/亚克力效果（Win11/Win10支持）
        for api in ('setMicaEffectEnabled', 'setAcrylicEffectEnabled'):
            try:
                getattr(self, api)(True)
                break
            except Exception:
                continue
        # 根据主题应用定制样式（浅/深）
        try:
            current_theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
            self.applyCustomStyleForTheme(current_theme)
        except Exception:
            # 如果无法检测就按浅色样式
            self.applyCustomStyleForTheme(Theme.LIGHT)

        # pages
        self.generalInterface = GeneralInterface(self)
        self.generalInterface.setObjectName('generalInterface')
        self.webvpnInterface = WebVpnInterface(self)
        self.webvpnInterface.setObjectName('webvpnInterface')
        self.accountsInterface = AccountsInterface(self)
        self.accountsInterface.setObjectName('accountsInterface')
        self.linksInterface = LinksInterface(self)
        self.linksInterface.setObjectName('linksInterface')

        # 避免子页面成为原生子窗口，破坏弹出层父级判断
        for w in (self.generalInterface, self.webvpnInterface, self.accountsInterface, self.linksInterface):
            try:
                w.setAttribute(Qt.WA_NativeWindow, False)
                w.setAttribute(Qt.WA_DontCreateNativeAncestors, True)
                w.viewport().setAttribute(Qt.WA_NativeWindow, False)
            except Exception:
                pass

        self.addSubInterface(self.generalInterface, FIF.SETTING, '常规', NavigationItemPosition.TOP)
        self.addSubInterface(self.webvpnInterface, FIF.VPN, 'WebVPN', NavigationItemPosition.TOP)
        self.addSubInterface(self.accountsInterface, FIF.PEOPLE, 'WiFi账户', NavigationItemPosition.TOP)
        self.addSubInterface(self.linksInterface, FIF.LINK, '链接', NavigationItemPosition.TOP)

        self.navigationInterface.setExpandWidth(240)
        self.stackedWidget.setCurrentWidget(self.generalInterface)

        self.move(self.geometry().center() - self.rect().center())# 居中

        logger.info('设置窗口初始化完毕')

    def applyCustomStyleForTheme(self, theme: Theme):
        """根据主题切换浅/深自定义样式，避免深色下文字/背景不匹配"""
        if theme == Theme.DARK:
            custom_style = """
SettingsWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1f1f1f, stop:1 #242424);
    background-color: rgba(20,20,20,0.85);
    border-radius: 18px;
}
QWidget#generalInterface, QWidget#webvpnInterface, QWidget#accountsInterface, QWidget#linksInterface {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #2a2a2a, stop:1 #1f1f1f);
    border-radius: 12px;
    border: 1px solid #3b3b3b;
}
StrongBodyLabel {
    color: #90CAF9;
    font-weight: bold;
    font-size: 17px;
}
PushButton {
    background: #2B88D8;
    color: #fff;
    border-radius: 8px;
    padding: 6px 18px;
    font-weight: 500;
    border: 1px solid transparent;
}
PushButton:hover {
    background: #1f6fb5;
    color: #fff;
    border: 1px solid #1f6fb5;
}
LineEdit, PasswordLineEdit, ComboBox {
    background: rgba(30,30,30,0.95);
    color: #e6e6e6;
    border: 2px solid #3b3b3b;
    border-radius: 6px;
    padding: 4px 8px;
}
QAbstractSpinBox, QSpinBox {
    background: rgba(30,30,30,0.95);
    color: #e6e6e6;
    border: 2px solid #3b3b3b;
    border-radius: 6px;
    padding: 4px 8px;
}
LineEdit:focus, PasswordLineEdit:focus, ComboBox:focus {
    border: 2px solid #2B88D8;
}
"""
        else:
            custom_style = """
SettingsWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #e3f0ff, stop:1 #f7f7fa);
    background-color: rgba(255,255,255,0.85);
    border-radius: 18px;
}
QWidget#generalInterface, QWidget#webvpnInterface, QWidget#accountsInterface, QWidget#linksInterface {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #f0f6ff, stop:1 #e6f0fa);
    border-radius: 12px;
    border: 1px solid #cce4f7;
}
StrongBodyLabel {
    color: #0078D4;
    font-weight: bold;
    font-size: 17px;
}
PushButton {
    background: #0078D4;
    color: #fff;
    border-radius: 8px;
    padding: 6px 18px;
    font-weight: 500;
    border: 1px solid transparent;
}
PushButton:hover {
    background: #005a9e;
    color: #fff;
    border: 1px solid #005a9e;
}
LineEdit, PasswordLineEdit, ComboBox {
    background: rgba(255,255,255,0.95);
    border: 2px solid #cce4f7;
    border-radius: 6px;
    padding: 4px 8px;
}
QAbstractSpinBox, QSpinBox {
    background: rgba(255,255,255,0.95);
    color: #1f1f1f;
    border: 2px solid #cce4f7;
    border-radius: 6px;
    padding: 4px 8px;
}
LineEdit:focus, PasswordLineEdit:focus, ComboBox:focus {
    border: 2px solid #0078D4;
}
"""
        # 直接替换样式，避免多次叠加导致性能与视觉问题
        self.setStyleSheet(custom_style)
