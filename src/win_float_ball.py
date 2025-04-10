from qfluentwidgets import TeachingTip, TeachingTipTailPosition, RoundMenu, Action
from qfluentwidgets import FluentIcon as FIF
from ui.float_ball import UI_FloatBall
from ui.windows.drag_window import DragWindow
class FloatBall(DragWindow):
    def __init__(self,screen_size):
        super().__init__()
        self.ui = UI_FloatBall()
        self.ui.setupUI(self)
        self.setFixedSize(self.ui.waterball.size())

        self.setCanLeftScreen(False, screen_size=screen_size)
        self.ui.waterball.contextMenuEvent = self.waterball_menu
        self.ui.waterball.doubleClicked.connect(self.waterball_double_click)
        #self.ui.waterball.rightClicked.connect(self.waterball_right_clicked)
    def waterball_double_click(self):
        
        TeachingTip.create(self.ui.waterball,
                            'This is a ball','This is a ball that you can click on',
                            FIF.BASKETBALL,
                            isClosable=True,
                            duration=3000,
                            parent=self.ui.waterball)
    def waterball_menu(self,e):
        mainMenu = RoundMenu()
        accountMenu = RoundMenu("账号")
        linkMenu = RoundMenu("链接")

        accountMenu.addActions([Action("切换到账号1", icon=FIF.CHAT, triggered=lambda: print("切换账号1")),
                                Action("切换到账号2", icon=FIF.CHAT, triggered=lambda: print("切换账号2")),
                                Action("切换到账号3", icon=FIF.CHAT, triggered=lambda: print("切换账号3"))])
        
        linkMenu.addActions([Action("打开剪贴板链接", icon=FIF.LINK, triggered=lambda: print("打开剪贴板链接")),
                             Action("链接1", icon=FIF.LINK, triggered=lambda: print("链接1")),
                             Action("链接2", icon=FIF.LINK, triggered=lambda: print("链接2")),
                             Action("链接3", icon=FIF.LINK, triggered=lambda: print("链接3"))])
        # 链接内还应加入子菜单选择类别，以及是否使用webvpn打开
        
        mainMenu.addMenu(accountMenu)
        mainMenu.addMenu(linkMenu)
        mainMenu.addSeparator()
        mainMenu.addActions([Action("隐藏", icon=FIF.HIDE, triggered=lambda: self.setHidden(True)),
                             Action("退出", icon=FIF.CLOSE, triggered=lambda: exit())])

        mainMenu.exec(e.globalPos())