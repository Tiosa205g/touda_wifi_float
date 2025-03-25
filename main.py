from PySide6 import QtCore
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from src import win_float_ball
from src import Tray
if __name__ == '__main__':
    app = QApplication()
    
    win = win_float_ball.FloatBall(app.primaryScreen().size())
    win.setWindowIcon(QIcon('res/ico/favicon.ico'))
    tray = Tray(win)
    win.show()

    app.exec()