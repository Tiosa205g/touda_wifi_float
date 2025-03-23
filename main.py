from PySide6 import QtCore
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from ui import FloatBall
from ui import Tray
if __name__ == '__main__':
    app = QApplication()
    tray = Tray(QIcon('res/ico/favicon.ico'))
    win = FloatBall()
    win.show()

    app.exec()