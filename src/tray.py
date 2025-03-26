from PySide6.QtWidgets import QSystemTrayIcon
from qfluentwidgets import SystemTrayMenu, Action

class Tray(QSystemTrayIcon):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setIcon(parent.windowIcon())
        self.setToolTip('Touda WiFi')

        self.menu = SystemTrayMenu("touda_wifi", parent=parent)
        self.menu.addActions([Action('退出', triggered=self.quit)])
        self.activated.connect(self.toggle)

        self.setContextMenu(self.menu)
        self.show()

        print('Tray created')

    def toggle(self, reason):
        
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            print('toggle')
            self.parent().setHidden(not self.parent().isHidden())

    def quit(self):
        print('quit')
        exit()
    