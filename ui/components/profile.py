from PySide6.QtCore import Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout
from qfluentwidgets import AvatarWidget, BodyLabel, CaptionLabel
from src.touda import wifi

class ProfileCard(QWidget):
    """ Profile card """

    def __init__(self, avatarPath: str, name: str, email: str, parent=None):
        """

        :param avatarPath: 头像图片路径
        :param name: 名字
        :param email: 邮箱
        :param parent:
        """
        super().__init__(parent=parent)
        self.mainLayout = QHBoxLayout(self)
        self.rightLayout = QVBoxLayout()

        self.avatar = AvatarWidget(image=avatarPath)
        self.avatar.setRadius(19)
        self.avatar.setText("汕大")
        self.mainLayout.addWidget(self.avatar)
        self.mainLayout.addLayout(self.rightLayout)

        self.nameLabel = BodyLabel(text=name)
        self.emailLabel = CaptionLabel(text=email)
        self.fluxLable = CaptionLabel(text="0.00Mb/0.00Mb")
        self.rightLayout.addWidget(self.nameLabel)
        self.rightLayout.addWidget(self.emailLabel)
        self.rightLayout.addWidget(self.fluxLable)

        self.emailLabel.setTextColor(QColor(96, 96, 96), QColor(206, 206, 206))

        self.setFixedSize(230, 80)
        self.setLayout(self.mainLayout)

    @Slot(wifi.state)
    def onUpdateState(self, state:wifi.state):
        """
        切换账号
        :param state: wifi.state
        :return:
        """
        self.nameLabel.setText(state.name)
        if state.state == "无限流":
            self.nameLabel.setText("无限流账号")
        if state.state == "无限流" or state.state == "未登录":
            self.emailLabel.setText("<UNK>@stu.edu.cn")
        else:
            self.emailLabel.setText(state.name+"@stu.edu.cn")
        self.fluxLable.setText(f"{state.used:.2f}Mb/{state.total:.2f}Mb")
