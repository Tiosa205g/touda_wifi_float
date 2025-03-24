from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtCore import Qt
from .components import WaterBall

class UI_FloatBall:
    def setupUI(self, FloatBall):
        FloatBall.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        FloatBall.titleBar.hide()
        FloatBall.setAttribute(Qt.WA_TranslucentBackground)
        #self.setFixedSize(1000, 700)
        self.mainLayout = QHBoxLayout(FloatBall)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)

        self.waterball = WaterBall(100)
        self.waterball.setFixedSize(100, 100)
        self.waterball.progress = 50
        self.mainLayout.addWidget(self.waterball)
        FloatBall.setLayout(self.mainLayout)

        FloatBall.show()
