"""通用无边框弹窗基类 — 支持深浅主题、拖拽、按钮自定义"""

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont, QMouseEvent
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QWidget, QTextBrowser, QSizePolicy,
)
from qfluentwidgets import (
    PrimaryPushButton, PushButton,
    FluentIcon as FIF, isDarkTheme, InfoBar,
)
from typing import Optional


def _theme_colors():
    """根据当前主题返回 (bg, text, sec, border)"""
    dark = isDarkTheme()
    return (
        "#2a2a2a" if dark else "#ffffff",
        "#e0e0e0" if dark else "#1f1f1f",
        "#a0a0a0" if dark else "#666666",
        "#3b3b3b" if dark else "#d0d0d0",
    )


def _center_on_screen(widget, width: int, height: int):
    """将 widget 居中于屏幕"""
    from PySide6.QtGui import QGuiApplication
    screen = QGuiApplication.primaryScreen()
    if screen:
        sg = screen.availableGeometry()
        widget.move(sg.center().x() - width // 2, sg.center().y() - height // 2)


class FramelessDialog(QDialog):
    """通用无边框弹窗

    快速创建风格统一的确认/信息/输入弹窗。

    show_message(title, content)  → 信息弹窗
    show_confirm(title, content)  → 确认弹窗，返回 bool
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dragging = False
        self._drag_pos = QPoint()
        self._result_value = False

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("framelessDialog")

        # 主布局
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # ── outer 容器：真正 clip 圆角 ──
        self._outer = QWidget(self)
        self._outer.setObjectName("fdOuter")
        self._outerLayout = QVBoxLayout(self._outer)
        self._outerLayout.setContentsMargins(0, 0, 0, 0)
        self._outerLayout.setSpacing(0)
        self._layout.addWidget(self._outer)

        self._content_layout: Optional[QVBoxLayout] = None

        self._setup_theme()
        self._build_title_bar()

    def _setup_theme(self):
        bg, text, sec, border = _theme_colors()
        self._outer.setStyleSheet(f"""
            #fdOuter {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)

    def _build_title_bar(self):
        bg, text, sec, border = _theme_colors()
        dark = isDarkTheme()

        bar = QWidget(self._outer)
        bar.setObjectName("fdTitleBar")
        bar.setFixedHeight(44)
        bar.setStyleSheet("background: transparent;")
        tb = QHBoxLayout(bar)
        tb.setContentsMargins(16, 0, 8, 0)

        self._title_label = QLabel("提示", bar)
        self._title_label.setStyleSheet(
            f"color: {text}; font-size: 14px; font-weight: bold; background: transparent;"
        )
        tb.addWidget(self._title_label)
        tb.addStretch(1)

        close_btn = QLabel("✕", bar)
        close_btn.setFixedSize(28, 28)
        close_btn.setAlignment(Qt.AlignCenter)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QLabel {{
                color: {sec}; background: transparent;
                border-radius: 14px; font-size: 14px;
            }}
            QLabel:hover {{
                background: {"#3a3a3a" if dark else "#e0e0e0"};
                color: {text};
            }}
        """)
        close_btn.mousePressEvent = lambda e: self.reject()
        tb.addWidget(close_btn)
        self._outerLayout.addWidget(bar)

    def add_content(self, widget: QWidget, stretch: int = 1):
        """向内容区添加控件"""
        if self._content_layout is None:
            content = QWidget(self._outer)
            content.setObjectName("fdContent")
            content.setStyleSheet("background: transparent;")
            self._content_layout = QVBoxLayout(content)
            self._content_layout.setContentsMargins(24, 12, 24, 20)
            self._content_layout.setSpacing(16)
            self._outerLayout.addWidget(content, stretch)

        self._content_layout.addWidget(widget, stretch)

    def add_buttons(self, *buttons: QWidget):
        """添加按钮行（右对齐）"""
        row = QWidget(self._outer)
        row.setObjectName("fdBtnRow")
        row.setStyleSheet("background: transparent;")
        br = QHBoxLayout(row)
        br.setContentsMargins(24, 0, 24, 20)
        br.setSpacing(12)
        br.addStretch(1)
        for b in buttons:
            br.addWidget(b)
        self.add_content(row, 0)

    # ── 拖拽 ──
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and event.position().y() <= 44:
            self._is_dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._is_dragging:
            self._is_dragging = False
            event.accept()

    # ── 快捷静态方法 ──
    @staticmethod
    def show_message(title: str, content: str, parent=None):
        """显示信息弹窗"""
        dlg = FramelessDialog(parent)
        dlg.setWindowTitle(title)
        dlg.setFixedSize(400, 220)
        dlg._title_label.setText(title)
        _center_on_screen(dlg, 400, 220)

        label = QLabel(content, dlg._outer)
        label.setWordWrap(True)
        bg, text, sec, border = _theme_colors()
        label.setStyleSheet(f"color: {text}; font-size: 13px; background: transparent;")
        dlg.add_content(label)

        btn = PrimaryPushButton(FIF.ACCEPT, "确定", dlg._outer)
        btn.setFixedWidth(100)
        btn.clicked.connect(dlg.accept)
        dlg.add_buttons(btn)
        return dlg.exec()

    @staticmethod
    def show_confirm(title: str, content: str, parent=None) -> bool:
        """显示确认弹窗，返回 True=确认 / False=取消"""
        dlg = FramelessDialog(parent)
        dlg.setWindowTitle(title)
        dlg.setFixedSize(420, 200)
        dlg._title_label.setText(title)
        _center_on_screen(dlg, 420, 200)

        label = QLabel(content, dlg._outer)
        label.setWordWrap(True)
        bg, text, sec, border = _theme_colors()
        label.setStyleSheet(f"color: {text}; font-size: 13px; background: transparent;")
        dlg.add_content(label)

        cancel_btn = PushButton(FIF.CANCEL, "取消", dlg._outer)
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(dlg.reject)
        ok_btn = PrimaryPushButton(FIF.ACCEPT, "确定", dlg._outer)
        ok_btn.setFixedWidth(100)
        ok_btn.clicked.connect(dlg.accept)
        dlg.add_buttons(cancel_btn, ok_btn)
        return dlg.exec()


class UpdateDialog(FramelessDialog):
    """版本更新弹窗 — 基于 FramelessDialog"""

    def __init__(
        self,
        current_version: str,
        latest_tag: str,
        release_body: str,
        download_url: str,
        parent=None,
    ):
        super().__init__(parent)
        self._download_url = download_url

        self.setWindowTitle("发现新版本")
        self.setFixedSize(540, 480)
        self._title_label.setText("发现新版本")
        _center_on_screen(self, 540, 480)

        bg, text, sec, border = _theme_colors()
        dark = isDarkTheme()

        # 版本对比头
        headerRow = QWidget(self._outer)
        hr = QHBoxLayout(headerRow)
        hr.setContentsMargins(0, 0, 0, 0)
        hr.setSpacing(12)

        iconLabel = QLabel("📦", headerRow)
        iconFont = QFont("Segoe UI Emoji", 36)
        iconLabel.setFont(iconFont)
        hr.addWidget(iconLabel)

        vInfo = QVBoxLayout()
        vInfo.setSpacing(4)
        mainTitle = QLabel("有新版本可用", headerRow)
        mtFont = QFont()
        mtFont.setPointSize(18)
        mtFont.setBold(True)
        mainTitle.setFont(mtFont)
        mainTitle.setStyleSheet(f"color: {text}; background: transparent;")
        vInfo.addWidget(mainTitle)

        verLabel = QLabel(f"{current_version}  →  {latest_tag}", headerRow)
        vf = QFont()
        vf.setPointSize(13)
        verLabel.setFont(vf)
        verLabel.setStyleSheet(f"color: {sec}; background: transparent;")
        vInfo.addWidget(verLabel)
        hr.addLayout(vInfo, 1)
        self.add_content(headerRow, 0)

        # 更新说明
        bodyArea = QTextBrowser(self._outer)
        bodyArea.setOpenExternalLinks(True)
        bodyArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        bodyArea.setMinimumHeight(180)
        bodyArea.setStyleSheet(f"""
            QTextBrowser {{
                border: 1px solid {border};
                border-radius: 8px;
                background: transparent;
                color: {text};
                padding: 12px 16px;
                font-size: 13px;
            }}
        """)
        bodyArea.setHtml(self._format_release_body(release_body, text))
        self.add_content(bodyArea, 1)

        # 按钮
        btnLater = PushButton(FIF.CANCEL, "稍后再说", self._outer)
        btnLater.setFixedWidth(110)
        btnLater.clicked.connect(self.reject)
        btnDownload = PrimaryPushButton(FIF.DOWNLOAD, "去下载", self._outer)
        btnDownload.setFixedWidth(110)
        btnDownload.clicked.connect(self._on_download)
        self.add_buttons(btnLater, btnDownload)

    def _format_release_body(self, body: str, text_color: str) -> str:
        if not body or not body.strip():
            return "<p style='color:#888;'>暂无更新说明</p>"
        import re
        body = body.lstrip('\n\r ')
        html = body
        html = re.sub(r'^#{1,3}\s+(.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'^\* (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'```(\w*)\n(.*?)```', r'<pre><code>\2</code></pre>', html, flags=re.DOTALL)
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
        html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html)
        html = html.replace('\n', '<br>')
        return (
            f'<html><body style="font-family: -apple-system, Microsoft YaHei, sans-serif; '
            f'line-height: 1.6; color: {text_color};">'
            f'{html}'
            '</body></html>'
        )

    def _on_download(self):
        import webbrowser
        webbrowser.open(self._download_url)
        self.accept()
