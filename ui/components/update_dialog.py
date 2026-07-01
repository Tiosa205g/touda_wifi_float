"""版本更新弹窗 — QDialog 无边框，支持深浅主题"""

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont, QMouseEvent
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QWidget, QTextBrowser,
)
from qfluentwidgets import (
    PrimaryPushButton, PushButton,
    FluentIcon as FIF, isDarkTheme,
)


class UpdateDialog(QDialog):
    """无边框版本更新弹窗，用 QDialog.exec() 实现模态"""

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
        self._is_dragging = False
        self._drag_pos = QPoint()

        self.setWindowTitle("发现新版本")
        self.setFixedSize(540, 480)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Dialog
        )
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("updateDialog")

        # 居中于屏幕
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self.move(sg.center().x() - 270, sg.center().y() - 240)

        self._setup_ui(current_version, latest_tag, release_body)

    def _setup_ui(self, cur_ver: str, latest_tag: str, body: str):
        dark = isDarkTheme()
        bg = "#2a2a2a" if dark else "#ffffff"
        text_color = "#e0e0e0" if dark else "#1f1f1f"
        sec_color = "#a0a0a0" if dark else "#666666"
        border_color = "#3b3b3b" if dark else "#d0d0d0"

        self.setStyleSheet(f"""
            #updateDialog {{
                background: {bg};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 整个弹窗放一个容器实现真正圆角 ──
        outer = QWidget(self)
        outer.setObjectName("updateOuter")
        outer.setStyleSheet(f"""
            #updateOuter {{
                background: {bg};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
        """)
        outerLayout = QVBoxLayout(outer)
        outerLayout.setContentsMargins(0, 0, 0, 0)
        outerLayout.setSpacing(0)

        # ── 自定义标题栏（可拖拽） ──
        titleBar = QWidget(self)
        titleBar.setObjectName("updateTitleBar")
        titleBar.setFixedHeight(48)
        titleBar.setStyleSheet("background: transparent;")
        tbLayout = QHBoxLayout(titleBar)
        tbLayout.setContentsMargins(16, 0, 8, 0)

        tbTitle = QLabel("发现新版本", titleBar)
        tbTitle.setStyleSheet(
            f"color: {text_color}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        tbLayout.addWidget(tbTitle)
        tbLayout.addStretch(1)

        closeBtn = QLabel("✕", titleBar)
        closeBtn.setFixedSize(32, 32)
        closeBtn.setAlignment(Qt.AlignCenter)
        closeBtn.setCursor(Qt.PointingHandCursor)
        closeBtn.setStyleSheet(f"""
            QLabel {{
                color: {sec_color}; background: transparent;
                border-radius: 16px; font-size: 16px;
            }}
            QLabel:hover {{
                background: {"#3a3a3a" if dark else "#e0e0e0"};
                color: {text_color};
            }}
        """)
        closeBtn.mousePressEvent = lambda e: self.reject()
        tbLayout.addWidget(closeBtn)
        outerLayout.addWidget(titleBar)

        # ── 内容区 ──
        content = QWidget(self)
        content.setObjectName("updateContent")
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 16, 24, 20)
        cl.setSpacing(16)

        # 版本对比头
        headerRow = QWidget(content)
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
        mainTitle.setStyleSheet(f"color: {text_color}; background: transparent;")
        vInfo.addWidget(mainTitle)

        verLabel = QLabel(f"{cur_ver}  →  {latest_tag}", headerRow)
        vf = QFont()
        vf.setPointSize(13)
        verLabel.setFont(vf)
        verLabel.setStyleSheet(f"color: {sec_color}; background: transparent;")
        vInfo.addWidget(verLabel)
        hr.addLayout(vInfo, 1)
        cl.addWidget(headerRow)

        # 更新说明
        bodyArea = QTextBrowser(content)
        bodyArea.setOpenExternalLinks(True)
        bodyArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        bodyArea.setMinimumHeight(200)
        bodyArea.setStyleSheet(f"""
            QTextBrowser {{
                border: 1px solid {border_color};
                border-radius: 8px;
                background: {bg};
                color: {text_color};
                padding: 12px 16px;
                font-size: 13px;
            }}
        """)
        bodyArea.setHtml(self._format_release_body(body, text_color))
        cl.addWidget(bodyArea, 1)

        # 按钮行
        btnRow = QWidget(content)
        br = QHBoxLayout(btnRow)
        br.setContentsMargins(0, 4, 0, 0)
        br.setSpacing(12)

        self.btnLater = PushButton(FIF.CANCEL, "稍后再说", btnRow)
        self.btnLater.clicked.connect(self.reject)

        self.btnDownload = PrimaryPushButton(FIF.DOWNLOAD, "去下载", btnRow)
        self.btnDownload.clicked.connect(self._on_download)

        br.addStretch(1)
        br.addWidget(self.btnLater)
        br.addWidget(self.btnDownload)
        cl.addWidget(btnRow)
        outerLayout.addWidget(content, 1)

        layout.addWidget(outer)

    def _format_release_body(self, body: str, text_color: str) -> str:
        if not body or not body.strip():
            return f"<p style='color:#888;'>暂无更新说明</p>"

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

    # ── 窗口拖拽 ──
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and event.position().y() <= 48:
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

    def _on_download(self):
        import webbrowser
        webbrowser.open(self._download_url)
        self.accept()
