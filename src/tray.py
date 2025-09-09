import base64
import os
import sys
from functools import partial

from PySide6.QtWidgets import QSystemTrayIcon, QWidget
from qfluentwidgets import SystemTrayMenu, Action
from qfluentwidgets import FluentIcon as FIF
from src import config
from src.win_float_ball import MyRoundMenu
from ui.components import ProfileCard
path = os.getcwd()
class Tray(QSystemTrayIcon):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setIcon(parent.windowIcon())
        self.setToolTip('Touda WiFi')

        self.profile = ProfileCard("res/ico/favicon.ico", "xxx", "xxx@stu.edu.cn")

        self.menu = SystemTrayMenu("touda_wifi", parent=parent)
        self.menu.addWidget(self.profile,selectable=False)

        self.menu.addActions([Action(text='退出', triggered=self.quit)])
        self.activated.connect(self.toggle)


        self.setContextMenu(self.menu)

        self.show()

        print('托盘创建完毕')

    def toggle(self, reason):
        
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            print('toggle')
            self.parent().setHidden(not self.parent().isHidden())

    def quit(self):
        #TODO： 记录位置
        x,y=self.parent().geometry().x(),self.parent().geometry().y()
        mainc = config.CfgParse(os.getcwd()+"/config/main.toml")
        mainc.write('main','x',x)
        mainc.write('main','y',y)
        print('quit')
        sys.exit()


