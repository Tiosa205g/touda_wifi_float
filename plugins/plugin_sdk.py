"""Plugin SDK - 为插件提供通用工具类，消除各插件间的重复代码"""

from typing import Optional


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
            from ui.components.frameless_dialog import _center_on_screen, _theme_colors

            dlg = QDialog()
            dlg.setWindowTitle(title)
            dlg.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
            dlg.setAttribute(Qt.WA_TranslucentBackground, True)
            dlg.setFixedSize(380, 400)
            _center_on_screen(dlg, 380, 400)

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
