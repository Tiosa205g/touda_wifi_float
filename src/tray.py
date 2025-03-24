from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QAction

class Tray(QSystemTrayIcon):
    def __init__(self, icon, parent=None):
        super().__init__(icon=icon, parent=parent)
        self.setToolTip('Tray')

        self.menu = QMenu()
        self.displayAction = QAction('Display', self)
        self.quitAction = QAction('Quit', self)

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
