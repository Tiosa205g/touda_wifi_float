from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtCore import Qt
from .components import WaterBall

class UI_FloatBall:
    def __init__(self):
        self.waterBall = None
        self.mainLayout = None

    def setupUI(self, FloatBall):
        FloatBall.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool) # 窗口置顶, 无边框, 隐藏任务栏
        FloatBall.titleBar.hide() # 隐藏标题栏(最小化, 最大化, 关闭)
        FloatBall.setAttribute(Qt.WA_TranslucentBackground) # 设置窗口透明
        
        #self.setFixedSize(1000, 700)
        self.mainLayout = QHBoxLayout(FloatBall)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)

        self.waterBall = WaterBall(100)
        self.waterBall.setFixedSize(100, 100)
        self.waterBall.progress = 100
        self.mainLayout.addWidget(self.waterBall)
        FloatBall.setLayout(self.mainLayout)

        FloatBall.show()
