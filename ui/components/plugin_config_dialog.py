"""插件通用配置编辑器 — 可视化编辑插件目录下的 config.toml

供插件管理页在插件未提供 on_setting 自带设置界面时使用：
按值类型生成编辑控件（bool→开关、int→数字框、float/str→输入框、
密码类字段→密码框），保存走 CfgParse.set_all 保持类级缓存一致，
保存成功后回调 on_saved（如插件的 apply_settings）。
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame,
)
from qfluentwidgets import (
    PrimaryPushButton, PushButton, LineEdit, PasswordLineEdit,
    SpinBox, SwitchButton, StrongBodyLabel, CaptionLabel, InfoBar,
    FluentIcon as FIF,
)

from src.config import CfgParse
from src.logging_config import logger
from ui.components.frameless_dialog import (
    FramelessDialog, _position_dialog, _theme_colors,
)

_SECRET_HINTS = ('password', 'passwd', 'pwd', 'secret', 'token', 'access_key')


class PluginConfigDialog(FramelessDialog):
    """通用插件 config.toml 编辑器"""

    def __init__(self, plugin_name: str, cfg_path: str,
                 on_saved=None, parent=None):
        super().__init__(parent)
        self._cfg_path = cfg_path
        self._on_saved = on_saved
        self._fields = []  # [(section, option, kind, widget)]
        self._updating = False

        self.setWindowTitle(f'{plugin_name} - 参数配置')
        # 尺寸 = 内容区 + 阴影留白（四周约 16px）
        self.setFixedSize(600, 520)
        self._title_label.setText(f'{plugin_name} 参数配置')
        _position_dialog(self, parent)

        bg, text, sec, border = _theme_colors()

        # 加载 TOML（复用 CfgParse 类级缓存，保证与插件读取一致）
        self._doc = CfgParse(cfg_path).get_all()

        # ── 可滚动表单区 ──
        scroll = QScrollArea(self._outer)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
        )
        try:
            scroll.viewport().setStyleSheet("background: transparent;")
        except Exception:
            pass

        form = QWidget(self._outer)
        form.setStyleSheet("background: transparent;")
        vbox = QVBoxLayout(form)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(10)

        has_fields = self._build_form(vbox, text, sec, border)
        vbox.addStretch(1)
        scroll.setWidget(form)
        self.add_content(scroll, 1)

        if not has_fields:
            empty = CaptionLabel('该插件配置为空，无可编辑参数', self._outer)
            empty.setStyleSheet(f"color: {sec}; background: transparent;")
            self.add_content(empty, 0)

        hint = CaptionLabel(
            '复杂类型（数组/表）不支持可视化编辑，可点「打开配置文件」手动修改',
            self._outer,
        )
        hint.setStyleSheet(f"color: {sec}; background: transparent;")
        self.add_content(hint, 0)

        # ── 按钮行 ──
        btn_cancel = PushButton(FIF.CANCEL, "取消", self._outer)
        btn_cancel.setFixedWidth(100)
        btn_cancel.clicked.connect(self.reject)
        btn_open = PushButton(FIF.EDIT, "打开配置文件", self._outer)
        btn_open.setFixedWidth(130)
        btn_open.clicked.connect(self._open_in_editor)
        btn_save = PrimaryPushButton(FIF.SAVE, "保存", self._outer)
        btn_save.setFixedWidth(100)
        btn_save.clicked.connect(self._save)
        self.add_buttons(btn_cancel, btn_open, btn_save)

    # ── 表单构建 ──

    def _build_form(self, vbox: QVBoxLayout, text, sec, border) -> bool:
        """遍历 TOML 文档生成编辑行，返回是否有可编辑字段"""
        has_fields = False
        for section in list(self._doc.keys()):
            table = self._doc[section]
            # 仅处理一维 [section] 表，非表项跳过
            if not hasattr(table, 'items'):
                continue
            header = StrongBodyLabel(f'[{section}]')
            header.setStyleSheet(
                f"color: {text}; font-weight: bold; font-size: 13px;"
                f" background: transparent;"
            )
            vbox.addWidget(header)
            for option in list(table.keys()):
                value = table[option]
                kind = self._kind_of(value)
                editor = self._make_editor(option, value, kind, text, border)
                row = QWidget()
                row.setStyleSheet("background: transparent;")
                hl = QHBoxLayout(row)
                hl.setContentsMargins(12, 2, 4, 2)
                hl.setSpacing(12)
                label = QLabel(str(option))
                label.setFixedWidth(160)
                label.setStyleSheet(f"color: {text}; background: transparent;")
                hl.addWidget(label)
                hl.addWidget(editor, 1)
                vbox.addWidget(row)
                self._fields.append((section, option, kind, editor))
                has_fields = has_fields or kind != 'other'
        return has_fields

    @staticmethod
    def _kind_of(value) -> str:
        # 注意顺序：bool 是 int 子类（tomlkit 同样如此），必须先判断 bool
        if isinstance(value, bool):
            return 'bool'
        if isinstance(value, int):
            return 'int'
        if isinstance(value, float):
            return 'float'
        if isinstance(value, str):
            return 'str'
        return 'other'

    def _make_editor(self, option, value, kind, text, border):
        key = str(option).lower()
        secret = any(h in key for h in _SECRET_HINTS)

        if kind == 'bool':
            w = SwitchButton()
            w.setOnText('开')
            w.setOffText('关')
            w.setChecked(bool(value))
            return w
        if kind == 'int':
            w = SpinBox()
            w.setRange(-2147483648, 2147483647)
            w.setValue(int(value))
            return w
        if kind in ('float', 'str'):
            if secret and kind == 'str':
                w = PasswordLineEdit()
                w.setText(str(value))
                w.setPlaceholderText('（密码/密钥类字段）')
            else:
                w = LineEdit()
                if kind == 'float':
                    w.setText(repr(float(value)))
                else:
                    w.setText(str(value))
                w.setPlaceholderText(str(value) if value != '' else '（空）')
            return w
        # 其他类型（数组/表/时间）只读展示
        w = LineEdit()
        w.setText(str(value))
        w.setReadOnly(True)
        w.setToolTip('复杂类型不支持可视化编辑，请使用「打开配置文件」')
        return w

    # ── 保存 / 打开 ──

    def _collect(self) -> list:
        """把控件值写回 TOML 文档，返回错误列表"""
        errors = []
        for section, option, kind, widget in self._fields:
            if kind == 'other':
                continue
            try:
                if kind == 'bool':
                    val = widget.isChecked()
                elif kind == 'int':
                    val = int(widget.value())
                elif kind == 'float':
                    val = float(widget.text().strip())
                else:
                    val = widget.text()
                self._doc[section][option] = val
            except Exception as e:
                errors.append(f'{section}.{option}: {e}')
        return errors

    def _save(self):
        errors = self._collect()
        if errors:
            InfoBar.error(
                title='保存失败',
                content='；'.join(errors[:3]),
                parent=self, duration=5000,
            )
            return
        try:
            CfgParse(self._cfg_path).set_all(self._doc)
        except Exception as e:
            logger.exception(f'保存插件配置失败: {self._cfg_path}')
            InfoBar.error(
                title='保存失败', content=str(e),
                parent=self, duration=5000,
            )
            return
        # 通知插件应用新配置（如 apply_settings 重启轮询定时器）
        if callable(self._on_saved):
            try:
                self._on_saved()
            except Exception:
                logger.exception('插件应用新配置失败')
        InfoBar.success(
            title='已保存', content='插件配置已更新',
            parent=self, duration=2500,
        )
        self.accept()

    def _open_in_editor(self):
        """用系统默认编辑器打开 config.toml（复杂类型的手动编辑入口）"""
        try:
            os.startfile(self._cfg_path)  # noqa: S606  Windows 本项目专用
        except Exception as e:
            InfoBar.error(
                title='打开失败', content=str(e),
                parent=self, duration=4000,
            )
