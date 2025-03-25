from PySide6.QtWidgets import QSystemTrayIcon
from qfluentwidgets import SystemTrayMenu, Action

class Tray(QSystemTrayIcon):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setIcon(parent.windowIcon())
        self.setToolTip('Tray')

        self.menu = SystemTrayMenu("touda_wifi", parent=parent)
        self.menu.addActions([Action('Display',triggered=self.display),
                              Action('Quit', triggered=self.quit)])

        self.setContextMenu(self.menu)
        self.show()

        print('Tray created')

    def display(self):
        print('show')

    def quit(self):
        print('quit')
        exit()
