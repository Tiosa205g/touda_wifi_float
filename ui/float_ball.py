from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtCore import Qt
from .components import WaterBall
from .windows import DragWindow
from .tray import Tray

class FloatBall(DragWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.titleBar.hide()
        self.setAttribute(Qt.WA_TranslucentBackground)
        #self.setFixedSize(1000, 700)
        self.initUI()
        self.show()

    def initUI(self):
        mainLayout = QHBoxLayout(self)
        mainLayout.setContentsMargins(0, 0, 0, 0)

        self.waterball = WaterBall(100)
        self.waterball.setFixedSize(100, 100)
        self.waterball.progress = 50
        mainLayout.addWidget(self.waterball)
        self.setLayout(mainLayout)

