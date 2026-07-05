from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtCore import Qt
from .components import WaterBall

class UI_FloatBall:
    def __init__(self):
        self.waterBall = None
        self.mainLayout = None

    def setupUI(self, FloatBall):
        # 无 titleBar 需要隐藏
        FloatBall.setAttribute(Qt.WA_TranslucentBackground) # 设置窗口透明

        self.mainLayout = QHBoxLayout(FloatBall)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)

        self.waterBall = WaterBall(100)
        self.waterBall.setFixedSize(100, 100)
        self.waterBall.progress = 100
        self.mainLayout.addWidget(self.waterBall)
        FloatBall.setLayout(self.mainLayout)
