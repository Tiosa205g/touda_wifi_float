from PySide6 import QtCore
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from src import win_float_ball
from src import Tray
if __name__ == '__main__':
    app = QApplication()
    
    win = win_float_ball.FloatBall(app.primaryScreen().size())
    win.setWindowIcon(QIcon('res/ico/favicon.ico'))
    win.tray = Tray(win)
    win.bridge.wifi.state_update.connect(win.tray.profile.onUpdateState)
    print(win.bridge.wifi.login())
    print(win.bridge.webvpn.login())
    win.show()

    app.exec()