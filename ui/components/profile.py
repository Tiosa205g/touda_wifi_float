from PySide6.QtCore import Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget
from qfluentwidgets import AvatarWidget, BodyLabel, CaptionLabel


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
        self.avatar = AvatarWidget(avatarPath, self)
        self.avatar.setText("汕大")
        self.nameLabel = BodyLabel(name, self)
        self.emailLabel = CaptionLabel(email, self)

        self.emailLabel.setTextColor(QColor(96, 96, 96), QColor(206, 206, 206))

        self.setFixedSize(246, 66)
        self.avatar.setRadius(19)
        self.avatar.move(2, 5)
        self.nameLabel.move(51, 10)
        self.emailLabel.move(51, 26)
    @Slot(str,str)
    def onUpdateState(self, name: str, email: str):
        """
        切换账号
        :param name: 名字
        :param email: 邮箱
        :return:
        """
        self.nameLabel.setText(name)
        self.emailLabel.setText(email)
