from qframelesswindow import FramelessWindow
from PySide6.QtWidgets import QApplication,QHBoxLayout
from PySide6 import QtCore
from components import WaterBall
class FloatBall(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.setFixedSize(500, 200)
        self.initUI()

        self.show()
    def initUI(self):
        mainLayout = QHBoxLayout(self)
        mainLayout.setContentsMargins(0, 0, 0, 0)

        self.waterball = WaterBall()
        mainLayout.addWidget(self.waterball)
        self.setLayout(mainLayout)

        
if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    win = FloatBall()
    sys.exit(app.exec_())