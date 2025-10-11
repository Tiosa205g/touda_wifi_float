import base64
import os
import sys
from functools import partial

from PySide6.QtWidgets import QSystemTrayIcon, QWidget
from qfluentwidgets import SystemTrayMenu, Action
from qfluentwidgets import FluentIcon as FIF
from src import config
from src.win_float_ball import MyRoundMenu
from src.logging_config import logger
from ui.components import ProfileCard
path = os.getcwd()
class Tray(QSystemTrayIcon):
    def __init__(self, parent=None,version:str="v1.0.0"):
        super().__init__(parent=parent)
        self.setIcon(parent.windowIcon())
        self.setToolTip('Touda WiFi')

        self.profile = ProfileCard("res/ico/favicon.ico", "xxx", "xxx@stu.edu.cn",version)

        self.menu = SystemTrayMenu("touda_wifi", parent=parent)
        self.menu.addWidget(self.profile,selectable=False)
        self.menu.aboutToShow.connect(self.onMenuShow)
        self.menu.addActions([Action(text='退出', triggered=self.quit)])
        self.activated.connect(self.toggle)


        self.setContextMenu(self.menu)

        self.show()
        logger.info('托盘创建完毕')
    def onMenuShow(self):
        self.menu.setFocus()
        logger.info("托盘菜单已打开")
    def toggle(self, reason):
        
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            logger.info('toggle')
            self.parent().setHidden(not self.parent().isHidden())

    def quit(self):
        x,y=self.parent().geometry().x(),self.parent().geometry().y()
        mainc = config.CfgParse(os.getcwd()+"/config/main.toml")
        mainc.write('main','x',x)
        mainc.write('main','y',y)
        logger.info('quit')
        sys.exit()


