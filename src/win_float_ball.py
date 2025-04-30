import os
import webbrowser
import base64
from functools import partial
from PySide6.QtCore import QTimer, QPoint
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import TeachingTip, RoundMenu, Action, Dialog
from qfluentwidgets import FluentIcon as FIF
from ui.float_ball import UI_FloatBall
from ui.windows.drag_window import DragWindow
from src import touda, config
from src.touda import Worker
path = os.getcwd()
class MyRoundMenu(RoundMenu):
    # 重写方法加入点击打开子菜单
    def _onItemClicked(self, item):
        super()._onItemClicked(item)
        action = item.data(Qt.UserRole)
        if action in self._subMenus and action.isEnabled():
            pos = self.mapToGlobal(QPoint(self.width() - 25, +30))
            action.exec(pos)
    def mousePressEvent(self, e):
        rect = self.geometry()
        rect.setX(rect.x() - self.width())
        w = self.childAt(e.pos())
        if (w is not self.view) and (not self.view.isAncestorOf(w)) and (not rect.contains(e.globalPos())):
            self._hideMenu(True)
class handle:
    def __init__(self):
        main = config.CfgParse(path+"/config/main.toml")
        current = config.CfgParse(path+f"/config/account_{main.get('main','current_account')}.toml")
        webvpn_name = main.get('webvpn','name')
        webvpn_password = base64.b64decode(main.get('webvpn','password').encode('utf-8')).decode('utf-8')
        webvpn_key = main.get('webvpn','key')
        webvpn_twfid = main.get('webvpn','twfid')
        name = current.get('setting','name')
        password = base64.b64decode(current.get('setting','password').encode('utf-8')).decode('utf-8')

        self.wifi = touda.wifi(name,password)
        self.webvpn = touda.webvpn(webvpn_name,webvpn_password,webvpn_key,webvpn_twfid)

awa = handle()
class FloatBall(DragWindow):
    def __init__(self,screen_size,app:QApplication):
        super().__init__()
        self.app = app
        self.ui = UI_FloatBall()
        self.ui.setupUI(self)
        self.setFixedSize(self.ui.waterBall.size())

        self.setCanLeftScreen(False, screen_size=screen_size)
        self.ui.waterBall.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.waterBall.customContextMenuRequested.connect(self.waterBall_menu)
        self.ui.waterBall.doubleClicked.connect(self.waterBall_double_click)

        #self.ui.waterBall.rightClicked.connect(self.waterBall_right_clicked)

        self.timer = timer()
        self.bridge = awa
    def waterBall_double_click(self):
        
        TeachingTip.create(self.ui.waterBall,
                            'This is a ball','这都给你发现了',
                            FIF.BASKETBALL,
                            isClosable=True,
                            duration=1500,
                            parent=self.ui.waterBall)
    def waterBall_menu(self,pos):
        mainMenu = MyRoundMenu()
        accountMenu = MyRoundMenu("账号")
        linkMenu = MyRoundMenu("链接")
        acc = []
        curr = config.CfgParse(path+"/config/main.toml").get('main','current_account')
        i = 0
        for file in os.listdir('config'):
            if 'account_' in file and '.toml' in file:
                acc.append("config/"+file)
                now = config.CfgParse("config/"+file)
                name = now.get('setting','name')
                password = base64.b64decode(now.get('setting','password').encode('utf-8')).decode('utf-8')
                accountMenu.addAction(Action(text="切换为"+name, icon=FIF.CHAT, triggered=partial(self.change_account,name,password,i)))
                i+=1

        linkMenu.addAction(Action(text="剪切板链接", icon=FIF.LINK, triggered=self.open_custom_link))
        self.create_links_menu(linkMenu)
        # 链接内还应加入子菜单选择类别，以及是否使用webvpn打开
        

        mainMenu.addMenu(linkMenu)
        mainMenu.addMenu(accountMenu)
        mainMenu.addSeparator()
        mainMenu.addAction(Action(text="隐藏", icon=FIF.HIDE, triggered=lambda: self.setHidden(True)))

        mainMenu.exec(self.mapToGlobal(pos))
    def open_custom_link(self):
        """
        剪辑板链接
        """
        link = self.app.clipboard().text()
        self.open_link_window(link,link)
    def open_link_window(self,name,link,*args):
        w = Dialog("选择:",f"是否使用webvpn打开{name}",self)
        if w.exec():
            url = awa.webvpn.create_url(link)
            webbrowser.open(url)
        else:
            webbrowser.open(link)

    def create_links_menu(self,menu:MyRoundMenu):
        """
        添加链接菜单到菜单上
        """
        link_all = config.CfgParse(path+"/config/links.toml").get_all()

        for link_type in link_all:
            linkType = MyRoundMenu(link_type)
            for name in link_all[link_type]:
                link = link_all[link_type][name]
                linkType.addAction(Action(text=name, icon=FIF.LINK, triggered=partial(self.open_link_window,name,link)))
            menu.addMenu(linkType)
    def change_account(self,name,password,index,*args):
        """
        切换账号
        """
        try:
            main = config.CfgParse(path+"/config/main.toml")
            self.bridge.wifi.change_account(name,password)
            main.write('main', 'current_account', index)
            print("切换账号成功")
        except Exception as e:
            print(f"切换账号出错{e}")


class timer(QTimer):
    """
    检查wifi登录状态
    """
    def __init__(self):
        super().__init__()
        self.timeout.connect(self.update)
        self.start(60000)

    def update(self):
        state = awa.wifi.getState()
        if state.state == "未登录":
            if not awa.wifi.login():
                return
            else:
                state = awa.wifi.getState()
        print(state)


