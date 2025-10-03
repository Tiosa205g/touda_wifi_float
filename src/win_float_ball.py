import os
import threading
import webbrowser
import base64
from functools import partial
from PySide6.QtCore import QTimer, QPoint
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QApplication, QInputDialog
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
        self.main = config.CfgParse(path+"/config/main.toml")
        self.current = config.CfgParse(path+f"/config/account_{self.main.get('main','current_account')}.toml")
        webvpn_name = self.main.get('webvpn','name')
        webvpn_password = base64.b64decode(self.main.get('webvpn','password').encode('utf-8')).decode('utf-8')
        webvpn_key = self.main.get('webvpn','key')
        webvpn_twfid = self.main.get('webvpn','twfid')
        name = self.current.get('setting','name')
        password = base64.b64decode(self.current.get('setting','password').encode('utf-8')).decode('utf-8')

        self.wifi = touda.wifi(name,password)
        self.webvpn = touda.webvpn(webvpn_name,webvpn_password,webvpn_key,webvpn_twfid)
        self.webvpn.twfid_update.connect(lambda twfid:self.main.write('webvpn','twfid',twfid))

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
        self.timer.win = self
        self.bridge = awa
        
        x,y=self.bridge.main.get('main','x',0),self.bridge.main.get('main','y',0) #设置初始位置为上一次关闭位置
        self.move(x,y)
    def waterBall_double_click(self):
        # 账号具体信息状态显示
        TeachingTip.create(self.ui.waterBall,
                            'This is a ball','这都给你发现了',
                            FIF.BASKETBALL,
                            isClosable=True,
                            duration=1500,
                            parent=self.ui.waterBall)
    def waterBall_menu(self,pos,ret:bool=False):
        self.mainMenu = MyRoundMenu()
        accountMenu = MyRoundMenu("账号")
        linkMenu = MyRoundMenu("链接")
        webvpnMenu = MyRoundMenu("webvpn相关")
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
        # 移入webvpn相关
        self.create_links_menu(linkMenu)
        # 链接内还应加入子菜单选择类别，以及是否使用webvpn打开

        webvpnMenu.addActions([#Action(text="剪切板链接", icon=FIF.LINK, triggered=self.open_custom_link),
                               Action(text="复制一键登录链接", icon=FIF.ACCEPT,triggered=self.copy_login_link),
                               Action(text="转换剪贴板链接",icon=FIF.LABEL,triggered=self.clipboard_convert_webvpn),
                               Action(text="复制6位口令",icon=FIF.VPN,triggered=self.copy_totp),
                               Action(text="复制twfid",icon=FIF.CODE,triggered=self.copy_twfid)])

        self.mainMenu.addMenu(linkMenu)
        self.mainMenu.addMenu(webvpnMenu)
        self.mainMenu.addMenu(accountMenu)
        
        self.mainMenu.addSeparator() #分割线

        self.mainMenu.addAction(Action(text="隐藏", icon=FIF.HIDE, triggered=lambda: self.setHidden(True)))

        self.mainMenu.exec(self.mapToGlobal(pos))
    def clipboard_convert_webvpn(self):
        import re
        count = 0
        convert_count = 0

        cb = self.app.clipboard()
        site = cb.text()
        
        # ([a-zA-z]+://)([^/]*)(/.*)
        it = re.finditer('(https?://)(.*)(/.*)', site,re.I)

        for match in it:
            all = match.group()
            protocol = match.group(1)
            domain = match.group(2)
            args = match.group(3)

            count += 1

            if "webvpn.stu.edu.cn:8118" in all:
                continue

            web = domain.replace('-','--').replace(".","-")
            if ":" in web:
                web = web.replace(":","-")+"-p"
            web = protocol + web
            if "https" not in web:
                site = site.replace(all, web + ".webvpn.stu.edu.cn:8118" + args, 1) # http
            else:
                site = site.replace(all, web.replace("https","http") + "-s.webvpn.stu.edu.cn:8118" + args, 1) # https
            convert_count += 1
        cb.setText(site)
        print(f"转换结果: 共识别到{count}个链接,成功修改{convert_count}个链接")
    def open_custom_link(self):
        """
            剪辑板链接
        """
        link = self.app.clipboard().text()
        self.open_link_window(link,link)
    def copy_login_link(self):
        """
            复制一键登录webvpn的链接，不限设备
        """
        link = self.bridge.webvpn.create_redirect_url("https://webvpn.stu.edu.cn/")
        self.app.clipboard().setText(link)
    def copy_totp(self):
        """
            复制6位totp口令
        """
        key = self.bridge.webvpn.key
        totp = self.bridge.webvpn.encrypt.gettotpkey(key)
        self.app.clipboard().setText(totp)
    def copy_twfid(self):
        """
            复制用于登录的twfid
        """
        self.bridge.webvpn.autoLogin()
        twfid = self.bridge.webvpn.twfid
        self.app.clipboard().setText(twfid)
    def open_link_window(self,name,link,*args):
        if "live" in link and "bilibili" in link:
            a = Dialog("匹配到bilibili直播链接",f"是否使用使用解析打开{name}",self)
            a.yesButton.setText("是")
            a.cancelButton.setText("否")
            if a.exec():
                awa.webvpn.autoLogin()
                bilibili = touda.live_bilibili(awa.webvpn.twfid)
                url = bilibili.get_live_url(link)
                if len(url) > 0:
                    short_url = []
                    hash_put = {}
                    for i,x in enumerate(url) :
                        short_url.append(x[:30]+str(i))
                        hash_put.update({short_url[-1]:x})

                    item,ok = QInputDialog.getItem(self,
                                                   "选择视频地址",
                                                      "请选择",
                                                   short_url,
                                                   0,
                                                   editable=False)
                    if ok:
                        url = "http://hlsplayer-net-s.webvpn.stu.edu.cn:8118/embed?type=m3u8&src=" + hash_put[item]
                        webbrowser.open(url)

                return
        w = Dialog("选择:",f"是否使用webvpn打开{name}",self)
        w.yesButton.setText("是")
        w.cancelButton.setText("否")
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
        print(f"校园网状态：{state}")


