"""Plugin SDK - 为插件提供通用工具类，消除各插件间的重复代码"""

import time
from typing import Optional, Callable

from PySide6.QtCore import QObject, QEvent, Qt, QTimer
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QApplication, QWidget, QStyle, QStyledItemDelegate,
    QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGraphicsDropShadowEffect,
)


class PluginMenu:
    """插件菜单构建器"""

    def __init__(self):
        self.menu = []

    def add_func(self, func_name: str, func):
        """添加单个菜单项"""
        self.menu.append({'function': func_name, 'object': func})

    def add_funcs(self, funcs: list[dict]):
        """批量添加菜单项"""
        self.menu.extend(funcs)

    def del_func(self, func_name: str) -> bool:
        """删除指定名称的菜单项"""
        count = len(self.menu)
        self.menu = [x for x in self.menu if x['function'] != func_name]
        return len(self.menu) != count

    def get_all(self) -> list[dict]:
        return self.menu


class PluginSDK:
    """插件 SDK 基类，提供日志、弹窗等通用功能"""

    def __init__(self, api, plugin_name=""):
        self.api = api
        self._plugin_name = plugin_name

    def logger_info(self, msg: str):
        self.api.logger.info(f'[{self._plugin_name}] {msg}')

    def logger_error(self, msg: str):
        self.api.logger.error(f'[{self._plugin_name}] {msg}')

    # ── 弹窗接口 ──

    def show_message(self, title: str, content: str):
        """显示信息弹窗"""
        try:
            from ui.components.frameless_dialog import FramelessDialog
            FramelessDialog.show_message(title, content)
        except Exception as e:
            self.logger_error(f"show_message 失败: {e}")

    def show_confirm(self, title: str, content: str) -> bool:
        """显示确认弹窗，返回 True=确认 / False=取消"""
        try:
            from ui.components.frameless_dialog import FramelessDialog
            return FramelessDialog.show_confirm(title, content)
        except Exception as e:
            self.logger_error(f"show_confirm 失败: {e}")
            return False

    def show_input_list(self, title: str, prompt: str, items: list[str]) -> Optional[str]:
        """显示列表选择弹窗，返回选中项或 None"""
        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel
            from PySide6.QtCore import Qt
            from qfluentwidgets import (
                PrimaryPushButton, PushButton,
                ListWidget, FluentIcon as FIF,
            )
            from ui.components.frameless_dialog import _position_dialog, _theme_colors

            dlg = QDialog()
            dlg.setWindowTitle(title)
            dlg.setWindowFlags(
                Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
            dlg.setAttribute(Qt.WA_TranslucentBackground, True)
            dlg.setFixedSize(380, 400)
            _position_dialog(dlg, None)

            bg, text, sec, border = _theme_colors()
            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(0, 0, 0, 0)

            from PySide6.QtWidgets import QWidget
            outer = QWidget(dlg)
            outer.setObjectName("ilOuter")
            outer.setStyleSheet(f"#ilOuter {{ background: {bg}; border: 1px solid {border}; border-radius: 12px; }}")
            ol = QVBoxLayout(outer)
            ol.setContentsMargins(24, 16, 24, 20)
            ol.setSpacing(12)

            lbl = QLabel(prompt, outer)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color: {text}; font-size: 13px; background: transparent;")
            ol.addWidget(lbl)

            list_widget = ListWidget(outer)
            list_widget.addItems(items)
            list_widget.setStyleSheet(f"background: {bg}; color: {text}; border: 1px solid {border}; border-radius: 6px;")
            ol.addWidget(list_widget, 1)

            br = QHBoxLayout()
            cancel_btn = PushButton(FIF.CANCEL, "取消", outer)
            cancel_btn.setFixedWidth(100)
            cancel_btn.clicked.connect(dlg.reject)
            ok_btn = PrimaryPushButton(FIF.ACCEPT, "确定", outer)
            ok_btn.setFixedWidth(100)
            ok_btn.clicked.connect(dlg.accept)
            br.addStretch()
            br.addWidget(cancel_btn)
            br.addWidget(ok_btn)
            ol.addLayout(br)
            layout.addWidget(outer)

            if dlg.exec() == QDialog.Accepted and list_widget.currentItem():
                return list_widget.currentItem().text()
            return None
        except Exception as e:
            self.logger_error(f"show_input_list 失败: {e}")
            return None


# =========================================================================
# 列表整行悬停高亮（全插件共享）
# =========================================================================

def _hover_bg_color() -> QColor:
    """按主题返回悬停行背景色"""
    try:
        from qfluentwidgets import isDarkTheme
        return QColor('#3a3a3a' if isDarkTheme() else '#e3f0ff')
    except Exception:
        return QColor('#e3f0ff')


class _StripCellHoverDelegate(QStyledItemDelegate):
    """去掉原生样式对鼠标下单个单元格的 hover 绘制

    windows11 等原生样式会给 State_MouseOver 的单元格单独铺一层
    hover 颜色，叠在整行高亮上就出现了"单元格效果"。
    这里绘制前清掉该状态，悬停只表现为整行背景；选中态不受影响。
    """

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.state &= ~QStyle.State_MouseOver


class RowHoverTracker(QObject):
    """跟踪鼠标所在行，整行铺悬停背景色

    QSS 的 ::item:hover 只高亮鼠标下单个单元格；这里在悬停行变化时
    给行内所有单元格设置 BackgroundRole，整行一起高亮。
    同时挂 _StripCellHoverDelegate 压掉原生单格 hover 绘制。
    不与样式表/选中色冲突。
    """

    def __init__(self, view, hover_color: Optional[QColor] = None):
        super().__init__(view)
        self._view = view
        self.hover_color = hover_color or _hover_bg_color()
        self.hover_row = -1
        # 压掉原生样式对鼠标下单格的 hover 绘制（悬停只保留整行效果）
        self._delegate = _StripCellHoverDelegate(view)
        view.setItemDelegate(self._delegate)
        view.setMouseTracking(True)
        view.viewport().setMouseTracking(True)
        view.viewport().installEventFilter(self)

    # ── 鼠标跟踪 ──

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseMove:
            idx = self._view.indexAt(event.position().toPoint())
            self.set_hover_row(idx.row() if idx.isValid() else -1)
        elif event.type() == QEvent.Leave:
            self.set_hover_row(-1)
        return False

    def set_hover_row(self, row: int):
        if row == self.hover_row:
            return
        self._paint_row(self.hover_row, False)
        self.hover_row = row
        self._paint_row(row, True)

    # ── 背景铺设 ──

    def _paint_row(self, row: int, hover: bool):
        if row is None or row < 0:
            return
        brush = QBrush(self.hover_color) if hover else QBrush()
        for item in self._row_items(row):
            item.setBackground(brush)

    def _row_items(self, row: int) -> list:
        v = self._view
        try:
            if hasattr(v, 'columnCount'):  # QTableWidget
                return [v.item(row, c) for c in range(v.columnCount())
                        if v.item(row, c) is not None]
            item = v.item(row)  # QListWidget
            return [item] if item is not None else []
        except Exception:
            return []


def install_row_hover(view, hover_color: Optional[QColor] = None) -> RowHoverTracker:
    """给表格/列表装上整行悬停高亮（QTableWidget / QListWidget 通用）

    直接操作单元格背景（BackgroundRole），与 QSS 样式表共存稳定；
    同时压掉原生样式对鼠标下单格的 hover 绘制，悬停只有整行效果。
    """
    return RowHoverTracker(view, hover_color)


class RowHoverStyler(QObject):
    """普通 QWidget 行的整行悬停（附件行这类非 item 视图用）

    挂在行容器上监听 Enter/Leave（含子控件冒泡），悬停时铺行背景色。
    """

    def __init__(self, row: QWidget, hover_color: Optional[QColor] = None,
                 radius: int = 6):
        super().__init__(row)
        self._row = row
        self._color = hover_color or _hover_bg_color()
        self._radius = radius
        self._depth = 0
        row.installEventFilter(self)
        for child in row.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.Enter:
            self._depth += 1
            self._apply(True)
        elif t == QEvent.Leave:
            self._depth = max(0, self._depth - 1)
            if self._depth == 0:
                self._apply(False)
        return False

    def _apply(self, hover: bool):
        rgba = self._color.name()
        if hover:
            self._row.setStyleSheet(
                f'background: {rgba}; border-radius: {self._radius}px;')
        else:
            self._row.setStyleSheet('background: transparent;')


def install_widget_row_hover(row: QWidget, hover_color: Optional[QColor] = None,
                             radius: int = 6) -> RowHoverStyler:
    """给普通 QWidget 行装整行悬停效果（悬停子控件同样触发）"""
    return RowHoverStyler(row, hover_color, radius)


# =========================================================================
# 通知中枢（自绘置顶弹窗，全插件共享单例）
# =========================================================================

class _NotifyPopup(QWidget):
    """自绘置顶通知弹窗 — 不依赖 Windows 系统通知设置，确保可见

    · 无边框 + 置顶 + 不抢焦点，出现在屏幕右下角
    · 自动关闭（默认 10 s）；点击主体执行 on_click；✕ 关闭
    · 多条通知从下往上堆叠
    · 弹出时播放系统提示音
    """

    _stack: list = []          # 当前存活的弹窗（保持引用防 GC）
    _W = 340
    _MARGIN = 16
    _GAP = 10

    def __init__(self, title: str, body: str,
                 on_click: Optional[Callable] = None,
                 msecs: int = 10000):
        super().__init__(None)
        self._on_click = on_click if callable(on_click) else None

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedWidth(self._W)

        # ── 主题色（与主程序弹窗一致） ──
        from ui.components.frameless_dialog import _theme_colors
        bg, text, sec, border = _theme_colors()
        try:
            from qfluentwidgets import isDarkTheme
            dark = isDarkTheme()
        except Exception:
            dark = False
        hint_color = '#6a9fff' if dark else '#0078D4'
        close_hover = '#3a3a3a' if dark else '#e0e0e0'

        # ── 圆角背景卡片 ──
        card = QWidget(self)
        card.setObjectName('npCard')
        card.setStyleSheet(
            f'#npCard {{ background: {bg}; border: 1px solid {border};'
            f' border-radius: 10px; }}')
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)

        # 标题行：图标 + 标题 + 关闭
        trow = QWidget(card)
        trow.setStyleSheet('background: transparent;')
        tl = QHBoxLayout(trow)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(8)

        icon = QLabel('\U0001F514', trow)
        icon.setStyleSheet('background: transparent; font-size: 14px;')
        icon.setFixedWidth(24)
        tl.addWidget(icon)

        title_lbl = QLabel(str(title)[:80], trow)
        title_lbl.setStyleSheet(
            f'color: {text}; font-size: 13px; font-weight: 600;'
            f' background: transparent;')
        tl.addWidget(title_lbl, 1)

        self._btn_close = QPushButton('\u2715', trow)
        self._btn_close.setFixedSize(22, 22)
        self._btn_close.setStyleSheet(
            f'QPushButton {{ color: {sec}; background: transparent;'
            f' border: none; font-size: 13px; border-radius: 11px; }}'
            f'QPushButton:hover {{ background: {close_hover};'
            f' color: {text}; }}')
        self._btn_close.clicked.connect(self._dismiss)
        tl.addWidget(self._btn_close)
        lay.addWidget(trow)

        # 正文
        body_lbl = QLabel(str(body)[:300], card)
        body_lbl.setWordWrap(True)
        body_lbl.setStyleSheet(
            f'color: {text}; font-size: 12px; background: transparent;')
        lay.addWidget(body_lbl)

        # 点击提示
        if self._on_click:
            hint = QLabel('\u70b9\u51fb\u67e5\u770b', card)
            hint.setStyleSheet(
                f'color: {hint_color}; font-size: 11px;'
                f' background: transparent;')
            lay.addWidget(hint)

        outer = QVBoxLayout(self)
        # 四周留白给柔和投影（与主程序弹窗一致）
        outer.setContentsMargins(12, 10, 12, 16)
        outer.addWidget(card)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 90))
        card.setGraphicsEffect(shadow)

        # 子控件鼠标事件透传到弹窗（关闭按钮除外）
        for w in self.findChildren(QWidget):
            if w is not self._btn_close:
                w.installEventFilter(self)

        # 自动关闭
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dismiss)
        self._timer.start(max(int(msecs), 2000))

        # 堆叠定位
        self.adjustSize()
        _NotifyPopup._stack.append(self)
        _NotifyPopup._reposition_all()

        self._beep()
        self.show()

    # ── 堆叠定位 ──

    @classmethod
    def _reposition_all(cls):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.right() - cls._W - cls._MARGIN
        y = geo.bottom() - cls._MARGIN
        for p in reversed(cls._stack):
            y -= p.height()
            p.move(x, y)
            y -= cls._GAP

    # ── 关闭与点击 ──

    def _dismiss(self):
        self._timer.stop()
        if self in _NotifyPopup._stack:
            _NotifyPopup._stack.remove(self)
        _NotifyPopup._reposition_all()
        self.close()
        self.deleteLater()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            self._activate()
            return True
        return False

    def mousePressEvent(self, event):
        self._activate()

    def _activate(self):
        on_click = self._on_click
        self._dismiss()
        if on_click:
            try:
                on_click()
            except Exception:
                pass

    # ── 提示音 ──

    @staticmethod
    def _beep():
        try:
            import winsound
            winsound.PlaySound('SystemNotification',
                               winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            try:
                QApplication.beep()
            except Exception:
                pass


class _NotifyHub:
    """通知中枢

    - notify(): 弹出自绘置顶弹窗（不依赖 Windows 通知设置）
    - 点击弹窗执行 on_click（如直达列表 / 页面）
    - 全插件共享单例
    """

    MAX_PENDING = 20

    def __init__(self):
        self._tray = None
        self._connected = False

    def bind(self, api) -> bool:
        """绑定主程序托盘（幂等，保留兼容）。返回是否绑定成功。"""
        if self._connected:
            return True
        tray = getattr(getattr(api, 'parent', None), 'tray', None)
        if tray is None:
            return False
        self._tray = tray
        self._connected = True
        return True

    def notify(self, title: str, body: str,
               on_click: Optional[Callable] = None,
               msecs: int = 10000):
        """弹出通知（自绘置顶弹窗）。

        on_click: 点击弹窗主体时执行的动作（如打开列表/页面）。
        """
        try:
            _NotifyPopup(title, body,
                         on_click=on_click if callable(on_click) else None,
                         msecs=msecs)
        except Exception:
            # 极端兜底：弹窗创建失败时退回系统通知
            tray = self._tray
            if tray is not None:
                try:
                    from PySide6.QtWidgets import QSystemTrayIcon
                    tray.showMessage(str(title), str(body),
                                     QSystemTrayIcon.Information, 8000)
                    return
                except Exception:
                    pass
            try:
                from ui.components.frameless_dialog import FramelessDialog
                FramelessDialog.show_message(title, body)
            except Exception:
                pass


_hub = _NotifyHub()


def get_notifier() -> _NotifyHub:
    """获取共享通知中枢（各插件共用同一个实例）"""
    return _hub
