import sys
from PySide6.QtWidgets import QSystemTrayIcon, QWidget
from qfluentwidgets import SystemTrayMenu, Action


from ui.components import ProfileCard
class Tray(QSystemTrayIcon):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setIcon(parent.windowIcon())
        self.setToolTip('Touda WiFi')

        self.profile = ProfileCard("res/ico/favicon.ico", "xxx", "xxx@stu.edu.cn")

        # TODO : 把菜单复刻一下
        self.menu = SystemTrayMenu("touda_wifi", parent=parent)
        self.menu.addWidget(self.profile,selectable=False)
        self.menu.addActions([Action(text='退出', triggered=self.quit)])
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
        sys.exit()
    