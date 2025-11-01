from qframelesswindow import FramelessWindow
from PySide6.QtCore import QPoint,Qt, QSize
class DragWindow(FramelessWindow):
    __is_dragging:bool = False
    __start_drag_position:QPoint = QPoint()
    __leftScreen = True
    __screen_size = QSize()
    def __init__(self, parent=None):
        super().__init__(parent=parent)
    def setCanLeftScreen(self, leftscreen:bool, screen_size):
        """
            设置是否能够拖离屏幕
        """
        self.__leftScreen = leftscreen
        self.__screen_size = screen_size
    #设置拖拽
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.__is_dragging = True
            self.__start_drag_position = event.globalPos() - self.pos()
            event.accept()
    def mouseMoveEvent(self, event):
        if self.__is_dragging:
            pos = event.globalPos() - self.__start_drag_position
            if not self.__leftScreen:
                width = self.__screen_size.width() # 屏幕宽度
                height = self.__screen_size.height() # 屏幕高度
                geo = self.geometry()
                if pos.x() > width-geo.width():
                    pos.setX(width-geo.width())
                elif pos.x() < 0:
                    pos.setX(0)
                if pos.y() > height-geo.height():
                    pos.setY(height-geo.height())
                elif pos.y() < 0:
                    pos.setY(0)
            self.move(pos)
            event.accept()
    def mouseReleaseEvent(self, event):
        if self.__is_dragging:
            self.__is_dragging = False
            event.accept()