import os
import base64
from typing import Dict, List

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFileDialog, QMessageBox, QSpinBox

from qfluentwidgets import (
    FluentWindow,
    NavigationItemPosition,
    ScrollArea,
    LineEdit,
    PasswordLineEdit,
    ComboBox,
    PushButton,
    StrongBodyLabel,
    InfoBar,
    InfoBarIcon,
    FluentIcon as FIF,
    Dialog,
    setTheme,
    Theme,
    isDarkTheme,
    FluentTitleBar,
)

from src.config import CfgParse
from src.logging_config import logger


CONFIG_DIR = os.path.join(os.getcwd(), "config")
MAIN_CFG = os.path.join(CONFIG_DIR, "main.toml")
LINKS_CFG = os.path.join(CONFIG_DIR, "links.toml")


def ensure_cfg():
    if not os.path.isdir(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)
    for p in (MAIN_CFG, LINKS_CFG):
        if not os.path.exists(p):
            try:
                open(p, 'a', encoding='utf-8').close()
            except Exception:
                pass


def list_account_files() -> List[str]:
    ensure_cfg()
    files = []
    for f in os.listdir(CONFIG_DIR):
        if f.startswith("account_") and f.endswith(".toml"):
            files.append(os.path.join(CONFIG_DIR, f))
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
        ensure_cfg()
        self.mainCfg = CfgParse(MAIN_CFG)

        # 常规：WiFi 状态检查间隔（秒）
        g_account = self.addGroup("常规")

        rowInterval = QWidget(self)
        h1 = QHBoxLayout(rowInterval)
        h1.setContentsMargins(12, 8, 12, 8)
        h1.setSpacing(12)
        self.spinInterval = QSpinBox(rowInterval)
        self.spinInterval.setRange(10, 3600)  # 秒
        self.spinInterval.setSingleStep(10)
        # 颜色交由主题样式控制
        
        # 读取配置（毫秒），转换为秒
        interval_ms = self.mainCfg.get('main', 'timer_interval', 60000)
        try:
            interval_s = max(10, int(int(interval_ms) / 1000))
        except Exception:
            interval_s = 60
        self.spinInterval.setValue(interval_s)
        self.btnSaveInterval = PushButton("保存")
        self.btnOpenDir = PushButton("打开配置文件夹")
    # self.btnOpenDir.setIcon(FIF.FOLDER.icon())  # 移除图标，仅保留文字
        self.btnOpenDir.clicked.connect(lambda: os.startfile(CONFIG_DIR))
    # self.btnSaveInterval.setIcon(FIF.SAVE.icon())  # 移除图标，仅保留文字
        self.btnSaveInterval.clicked.connect(self.saveInterval)
        h1.addWidget(StrongBodyLabel("WiFi 状态检查间隔(秒):"))
        h1.addWidget(self.spinInterval)
        h1.addWidget(self.btnSaveInterval)
        h1.addWidget(self.btnOpenDir)
        h1.addStretch(1)
        g_account.addWidget(rowInterval)

        # 主题选择（自动/浅色/深色）
        rowTheme = QWidget(self)
        h2 = QHBoxLayout(rowTheme)
        h2.setContentsMargins(12, 8, 12, 8)
        h2.setSpacing(12)
        self.cmbTheme = ComboBox(rowTheme)
        self.cmbTheme.addItems(["自动", "浅色", "深色"])
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

        self.addFooterSpacer()

    def saveInterval(self):
        seconds = int(self.spinInterval.value())
        ms = max(10000, seconds * 1000)
        self.mainCfg.write('main', 'timer_interval', ms)
        # 若父窗口是 FloatBall，让定时器即时生效
        try:
            win = self.window().parent()  # SettingsWindow 的 parent 是 FloatBall
            if hasattr(win, 'timer') and win.timer is not None:
                win.timer.setInterval(ms)
                win.timer.start(ms)
        except Exception:
            pass
        InfoBar.success(title='已保存', content=f'已设置间隔为 {seconds} 秒', duration=1500, parent=self)

    def applyTheme(self, *_):
        idx = self.cmbTheme.currentIndex()
        val = 'auto' if idx == 0 else ('light' if idx == 1 else 'dark')
        # 写入配置
        self.mainCfg.write('ui', 'theme', val)
        # 应用主题
        t = Theme.AUTO if val == 'auto' else (Theme.LIGHT if val == 'light' else Theme.DARK)
        try:
            setTheme(t)
        except Exception:
            pass
        # 通知父窗口更新样式（浅/深不同配色）
        try:
            sw = self.window()
            if hasattr(sw, 'applyCustomStyleForTheme'):
                # AUTO 时根据系统当前深浅选择样式
                theme_for_style = Theme.DARK if (t == Theme.DARK or (t == Theme.AUTO and isDarkTheme())) else Theme.LIGHT
                sw.applyCustomStyleForTheme(theme_for_style)
        except Exception:
            pass
        InfoBar.success(title='已应用', content=f'主题已切换为 {self.cmbTheme.currentText()}', duration=1200, parent=self)


class WebVpnInterface(_BaseInterface):
    """WebVPN 设置：账号/密码/密钥，TWFID 操作"""
    def __init__(self, parent=None):
        super().__init__(parent)
        ensure_cfg()
        self.mainCfg = CfgParse(MAIN_CFG)

        g_webvpn = self.addGroup("WebVPN")

        # name
        row_name = QWidget(self)
        l = QHBoxLayout(row_name)
        l.setContentsMargins(12, 8, 12, 8)
        self.editName = LineEdit(row_name)
        self.editName.setPlaceholderText("webvpn 用户名")
        self.editName.setClearButtonEnabled(True)
        l.addWidget(StrongBodyLabel("用户名:"))
        l.addWidget(self.editName)
        g_webvpn.addWidget(row_name)

        # password
        row_pwd = QWidget(self)
        l2 = QHBoxLayout(row_pwd)
        l2.setContentsMargins(12, 8, 12, 8)
        self.editPwd = PasswordLineEdit(row_pwd)
        self.editPwd.setPlaceholderText("webvpn 密码")
        l2.addWidget(StrongBodyLabel("密码:"))
        l2.addWidget(self.editPwd)
        g_webvpn.addWidget(row_pwd)

        # key
        row_key = QWidget(self)
        l3 = QHBoxLayout(row_key)
        l3.setContentsMargins(12, 8, 12, 8)
        self.editKey = LineEdit(row_key)
        self.editKey.setPlaceholderText("动态口令密钥 (TOTP)")
        self.editKey.setClearButtonEnabled(True)
        l3.addWidget(StrongBodyLabel("密钥:"))
        l3.addWidget(self.editKey)
        g_webvpn.addWidget(row_key)

        # buttons
        row_btn = QWidget(self)
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
        InfoBar.success(title='已清空', content='已清空 TWFID', duration=1200, parent=self)


class AccountsInterface(_BaseInterface):
    """账户管理：新增/修改/删除 WiFi 账户"""
    def __init__(self, parent=None):
        super().__init__(parent)
        ensure_cfg()
        self.mainCfg = CfgParse(MAIN_CFG)

        g = self.addGroup("账户管理")

        # selector row
        row = QWidget(self)
        hl = QHBoxLayout(row)
        hl.setContentsMargins(12, 8, 12, 8)
        self.combo = ComboBox(row)
        self.combo.setMinimumWidth(260)
        self.btnRefresh = PushButton("刷新")
        self.btnAdd = PushButton("添加")
        self.btnEdit = PushButton("修改")
        self.btnDel = PushButton("删除")
        self.btnMakeCurrent = PushButton("设为当前")
        # for b in (self.btnRefresh, self.btnAdd, self.btnEdit, self.btnDel, self.btnMakeCurrent):
        #     b.setIcon(FIF.ADD_TO.icon() if b is self.btnAdd else b.icon())  # 移除所有图标，仅保留文字
        self.btnRefresh.clicked.connect(self.reload)
        self.btnAdd.clicked.connect(self.addAccount)
        self.btnEdit.clicked.connect(self.editAccount)
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
        row2 = QWidget(self)
        hl2 = QHBoxLayout(row2)
        hl2.setContentsMargins(12, 8, 12, 8)
        self.editName = LineEdit(row2)
        self.editName.setPlaceholderText("WiFi 账号")
        self.editPwd = PasswordLineEdit(row2)
        self.editPwd.setPlaceholderText("WiFi 密码")
        self.btnSave = PushButton("保存修改")
        #self.btnSave.setIcon(FIF.SAVE.icon())
        self.btnSave.clicked.connect(self.save)
        hl2.addWidget(StrongBodyLabel("名称:"))
        hl2.addWidget(self.editName)
        hl2.addWidget(StrongBodyLabel("密码:"))
        hl2.addWidget(self.editPwd)
        hl2.addWidget(self.btnSave)
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
        new_path = os.path.join(CONFIG_DIR, f"account_{idx}.toml")
        open(new_path, 'w', encoding='utf-8').close()
        cfg = CfgParse(new_path)
        cfg.write('setting', 'name', 'new_user')
        cfg.write('setting', 'password', write_b64('password'))
        InfoBar.success(title='已添加', content=f'创建 account_{idx}.toml', duration=1500, parent=self)
        self.reload()

    def editAccount(self):
        if self.combo.count() == 0:
            return
        self.load_current_to_editor()

    def save(self):
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
        if Dialog("确认删除", f"确定删除 {base} ?", self).exec():
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
        ensure_cfg()
        self.linksCfg = CfgParse(LINKS_CFG)

        g = self.addGroup("链接管理")

        # 操作区：类别、名称、链接 + 按钮
        row = QWidget(self)
        hl = QHBoxLayout(row)
        hl.setContentsMargins(12, 8, 12, 8)
        self.cmbType = ComboBox(row)
        self.cmbType.setMinimumWidth(140)
        self.editName = LineEdit(row)
        self.editName.setPlaceholderText("名称")
        self.editLink = LineEdit(row)
        self.editLink.setPlaceholderText("https://...")
        self.btnAddOrUpdate = PushButton("新增/更新")
        self.btnDelete = PushButton("删除")
        self.btnExport = PushButton("导出当前类别")
        self.btnImport = PushButton("导入到类别…")
        self.btnAddOrUpdate.clicked.connect(self.add_or_update)
        self.btnDelete.clicked.connect(self.delete)
        self.btnExport.clicked.connect(self.export_type)
        self.btnImport.clicked.connect(self.import_to_type)
        hl.addWidget(StrongBodyLabel("类别:"))
        hl.addWidget(self.cmbType)
        hl.addWidget(StrongBodyLabel("名称:"))
        hl.addWidget(self.editName)
        hl.addWidget(StrongBodyLabel("链接:"))
        hl.addWidget(self.editLink, 1)
        hl.addWidget(self.btnAddOrUpdate)
        hl.addWidget(self.btnDelete)
        hl.addWidget(self.btnExport)
        hl.addWidget(self.btnImport)
        g.addWidget(row)

        # 二行：快速选择已有条目
        row2 = QWidget(self)
        hl2 = QHBoxLayout(row2)
        hl2.setContentsMargins(12, 8, 12, 8)
        self.cmbExistName = ComboBox(row2)
        self.cmbExistName.setMinimumWidth(220)
        self.cmbExistName.currentIndexChanged.connect(self.on_exist_selected)
        hl2.addWidget(StrongBodyLabel("已存在:"))
        hl2.addWidget(self.cmbExistName, 1)
        g.addWidget(row2)

        self.reload_types()
        self.addFooterSpacer()

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
        self.reload_exist_names()

    def reload_exist_names(self):
        self.cmbExistName.clear()
        data = self._load_all()
        t = self.cmbType.currentText()
        names = []
        if t in data and isinstance(data[t], dict):
            names = list(data[t].keys())
        for n in names:
            self.cmbExistName.addItem(n)
        if names:
            self.on_exist_selected(0)

    def on_exist_selected(self, _):
        data = self._load_all()
        t = self.cmbType.currentText()
        n = self.cmbExistName.currentText()
        if t in data and isinstance(data[t], dict) and n in data[t]:
            self.editName.setText(n)
            self.editLink.setText(str(data[t][n]))

    def add_or_update(self):
        t = self.cmbType.currentText().strip() or "常用"
        n = self.editName.text().strip()
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
        n = self.editName.text().strip() or self.cmbExistName.currentText()
        data = self._load_all()
        if not t or t not in data or n not in data[t]:
            return
        if Dialog("确认删除", f"删除 [{t}]/{n} ?", self).exec():
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
            obj = eval(text)
            if not isinstance(obj, dict):
                raise ValueError('内容不是字典')
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
        self.setWindowTitle('设置 - Touda WiFi')
        self.setFixedSize(1000, 600)  # 固定宽度 1000，高度 600
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
        mica_enabled = False
        for api in ('setMicaEffectEnabled', 'setAcrylicEffectEnabled'):
            try:
                getattr(self, api)(True)
                mica_enabled = True
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

        self.addSubInterface(self.generalInterface, FIF.SETTING, '常规', NavigationItemPosition.TOP)
        self.addSubInterface(self.webvpnInterface, FIF.VPN, 'WebVPN', NavigationItemPosition.TOP)
        self.addSubInterface(self.accountsInterface, FIF.PEOPLE, '账户', NavigationItemPosition.TOP)
        self.addSubInterface(self.linksInterface, FIF.LINK, '链接', NavigationItemPosition.TOP)

        self.navigationInterface.setExpandWidth(240)
        self.stackedWidget.setCurrentWidget(self.generalInterface)

        self.move(self.geometry().center() - self.rect().center())# 居中

        logger.info('设置窗口初始化完毕 mica=%s', mica_enabled)

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
