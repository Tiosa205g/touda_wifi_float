from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtCore import Qt
from .components import WaterBall

class UI_FloatBall:
    def setupUI(self, FloatBall):
        FloatBall.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool) # 窗口置顶, 无边框, 隐藏任务栏
        FloatBall.titleBar.hide() # 隐藏标题栏(最小化, 最大化, 关闭)
        FloatBall.setAttribute(Qt.WA_TranslucentBackground) # 设置窗口透明
        
        #self.setFixedSize(1000, 700)
        self.mainLayout = QHBoxLayout(FloatBall)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)

        self.waterball = WaterBall(100)
        self.waterball.setFixedSize(100, 100)
        self.waterball.progress = 50
        self.mainLayout.addWidget(self.waterball)
        FloatBall.setLayout(self.mainLayout)

        FloatBall.show()
