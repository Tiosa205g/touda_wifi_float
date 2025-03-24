from qfluentwidgets import TeachingTip, TeachingTipTailPosition
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

        self.ui.waterball.clicked.connect(self.waterball_clicked)
    def waterball_clicked(self):
        TeachingTip.create(self.ui.waterball,
                            'This is a ball','This is a ball that you can click on',
                            FIF.BASKETBALL,
                            isClosable=True,
                            duration=3000,
                            parent=self.ui.waterball)