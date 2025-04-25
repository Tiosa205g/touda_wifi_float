import os
import webbrowser
from functools import partial
from PySide6.QtCore import QTimer, Signal
from qfluentwidgets import TeachingTip, TeachingTipTailPosition, RoundMenu, Action, Dialog
from qfluentwidgets import FluentIcon as FIF
from ui.float_ball import UI_FloatBall
from ui.windows.drag_window import DragWindow
from src import touda, config

path = os.getcwd()
class handle:
    def __init__(self):
        main = config.CfgParse(path+"/config/main.toml")
        current = config.CfgParse(path+f"/config/account_{main.get('main','current_account')}.toml")
        webvpn_name = main.get('webvpn','name')
        webvpn_password = main.get('webvpn','password')
        webvpn_key = main.get('webvpn','key')
        webvpn_twfid = main.get('webvpn','twfid')
        name = current.get('setting','name')
        password = current.get('setting','password')

        self.wifi = touda.wifi(name,password)
        self.webvpn = touda.webvpn(webvpn_name,webvpn_password,webvpn_key,webvpn_twfid)

awa = handle()
class FloatBall(DragWindow):
    def __init__(self,screen_size):
        super().__init__()
        self.ui = UI_FloatBall()
        self.ui.setupUI(self)
        self.setFixedSize(self.ui.waterBall.size())

        self.setCanLeftScreen(False, screen_size=screen_size)
        self.ui.waterBall.contextMenuEvent = self.waterBall_menu
        self.ui.waterBall.doubleClicked.connect(self.waterBall_double_click)

        #self.ui.waterBall.rightClicked.connect(self.waterBall_right_clicked)

        self.timer = timer()
        self.timer.wifi_state.connect(lambda total,used : self.ui.waterBall.set_progress(((total-used)*100/total)))
        print(awa.wifi.login())
    def waterBall_double_click(self):
        
        TeachingTip.create(self.ui.waterBall,
                            'This is a ball','This is a ball that you can click on',
                            FIF.BASKETBALL,
                            isClosable=True,
                            duration=3000,
                            parent=self.ui.waterBall)
    def waterBall_menu(self,e):
        mainMenu = RoundMenu()
        accountMenu = RoundMenu("账号")
        linkMenu = RoundMenu("链接")

        accountMenu.addActions([Action(text="切换到账号1", icon=FIF.CHAT, triggered=lambda: print("切换账号1")),
                                Action(text="切换到账号2", icon=FIF.CHAT, triggered=lambda: print("切换账号2")),
                                Action(text="切换到账号3", icon=FIF.CHAT, triggered=lambda: print("切换账号3"))])

        self.create_links_menu(linkMenu)
        # 链接内还应加入子菜单选择类别，以及是否使用webvpn打开
        
        mainMenu.addMenu(accountMenu)
        mainMenu.addMenu(linkMenu)
        mainMenu.addSeparator()
        mainMenu.addActions([Action(text="隐藏", icon=FIF.HIDE, triggered=lambda: self.setHidden(True)),
                             Action(text="退出", icon=FIF.CLOSE, triggered=lambda: exit())])

        mainMenu.exec(e.globalPos())
    def open_link_window(self,name,link,*args):
        w = Dialog("选择:",f"是否使用webvpn打开{name}",self)
        if w.exec():
            url = awa.webvpn.create_url(link)
            webbrowser.open(url)
        else:
            webbrowser.open(link)

    def create_links_menu(self,menu:RoundMenu):
        """
        添加链接菜单到菜单上
        """
        link_all = config.CfgParse(path+"/config/links.toml").get_all()

        for link_type in link_all:
            linkType = RoundMenu(link_type)
            for name in link_all[link_type]:
                link = link_all[link_type][name]
                linkType.addAction(Action(text=name, icon=FIF.LINK, triggered=partial(self.open_link_window,name,link)))
            menu.addMenu(linkType)

class timer(QTimer):
    wifi_state = Signal(float,float)
    def __init__(self):
        super().__init__()
        self.timeout.connect(self.update)
        self.start(10000)

    def update(self):
        state = awa.wifi.getState()
        if state.state == "未登录":
            if not awa.wifi.login():
                return
            else:
                state = awa.wifi.getState()
        print(state)
        self.wifi_state.emit(state.total,state.used)


