from qframelesswindow import FramelessWindow
from PySide6.QtCore import QPoint,Qt
class DragWindow(FramelessWindow):
    __is_dragging:bool = False
    __start_drag_position:QPoint = QPoint()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.__is_dragging = True
            self.__start_drag_position = event.globalPos() - self.pos()
            event.accept()
    def mouseMoveEvent(self, event):
        if self.__is_dragging:
            self.move(event.globalPos() - self.__start_drag_position)
            event.accept()
    def mouseReleaseEvent(self, event):
        if self.__is_dragging:
            self.__is_dragging = False
            event.accept()