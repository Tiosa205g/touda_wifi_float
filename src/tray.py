from PySide6.QtWidgets import QSystemTrayIcon
from qfluentwidgets import SystemTrayMenu, Action

class Tray(QSystemTrayIcon):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setIcon(parent.windowIcon())
        self.setToolTip('Tray')

        self.menu = SystemTrayMenu("touda_wifi", parent=parent)
        self.displayAction = Action('Display', self)
        self.quitAction = Action('Quit', self)

        self.displayAction.triggered.connect(self.display)
        self.quitAction.triggered.connect(self.quit)

        self.menu.addAction(self.displayAction)
        self.menu.addAction(self.quitAction)

        self.setContextMenu(self.menu)
        print('Tray created')
        self.show()

    def display(self):
        print('show')

    def quit(self):
        print('quit')
        exit()
