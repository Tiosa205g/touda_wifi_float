from PySide6.QtWidgets import QApplication, QHBoxLayout
from PySide6 import QtCore, QtGui
from PySide6.QtGui import QIcon
from components import WaterBall
from windows import DragWindow
from tray import Tray

class FloatBall(DragWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFixedSize(1000, 700)
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

if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    tray = Tray(QIcon('D:\\Source\\Python\\touda_wifi_float\\res\\favicon.ico'))
    win = FloatBall()
    win.show()

    app.exec()