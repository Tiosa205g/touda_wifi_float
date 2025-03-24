from PySide6 import QtCore
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from src import win_float_ball
from src import Tray
if __name__ == '__main__':
    app = QApplication()
    tray = Tray(QIcon('res/ico/favicon.ico'))
    win = win_float_ball.FloatBall(app.primaryScreen().size())
    win.show()

    app.exec()