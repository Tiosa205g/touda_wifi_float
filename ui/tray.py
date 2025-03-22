from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QAction

class Tray(QSystemTrayIcon):
    def __init__(self, icon, parent=None):
        super().__init__(icon=icon, parent=parent)
        self.setToolTip('Tray')

        self.menu = QMenu()
        self.showAction = QAction('Show', self)
        self.quitAction = QAction('Quit', self)

        self.showAction.triggered.connect(self.show)
        self.quitAction.triggered.connect(self.quit)

        self.menu.addAction(self.showAction)
        self.menu.addAction(self.quitAction)

        self.setContextMenu(self.menu)
        print('Tray created')
        self.show()

    def show(self):
        print('show')

    def quit(self):
        print('quit')
