import math
from PySide6.QtCore import Qt, QRectF, QPropertyAnimation, Property, QSize, Signal
from PySide6.QtGui import QPainter, QPainterPath, QColor, QBrush, QLinearGradient, QRadialGradient
from PySide6.QtWidgets import QWidget

class WaterBall(QWidget):
    clicked = Signal()
    rightClicked = Signal()
    doubleClicked = Signal()
    def __init__(self, x=200, speed=1, border_color=QColor(100, 100, 100), background_color=QColor(128,128,128), parent=None):
        super().__init__(parent)
        scale = x / 200
        self._progress = 0
        self._wave_offset = 0
        self._wave_height = 10*scale
        self._wave_speed = 0.05
        self._border_color = border_color
        self._background_color = background_color
        self.setFixedSize(x, x)

        self.wave_animation = QPropertyAnimation(self, b"wave_offset")
        self.wave_animation.setDuration(int(100000/speed))
        self.wave_animation.setLoopCount(-1)
        self.wave_animation.setStartValue(math.pi*18)
        self.wave_animation.setEndValue(math.pi*1800)
        self.wave_animation.start()
        self.is_pressed = False

    def get_color_by_progress(self, percent):
        start = (76, 175, 80)
        end = (244, 67, 54)
        r = start[0] + (end[0] - start[0]) * (1 - percent)
        g = start[1] + (end[1] - start[1]) * (1 - percent)
        b = start[2] + (end[2] - start[2]) * (1 - percent)
        return QColor(int(r), int(g), int(b))

    def get_progress(self):
        return self._progress

    def set_progress(self, value):
        self._progress = max(0, min(value, 100))
        self.update()

    progress = Property(float, get_progress, set_progress)

    def get_wave_offset(self):
        return self._wave_offset

    def set_wave_offset(self, value):
        self._wave_offset = value
        self.update()

    wave_offset = Property(float, get_wave_offset, set_wave_offset)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        diameter = min(self.width(), self.height()) - 10
        rect = QRectF(5, 5, diameter, diameter)
        painter.setPen(self._border_color)
        painter.drawEllipse(rect)

        painter.setBrush(QBrush(self._background_color))
        painter.drawEllipse(rect)

        water_height = (self._progress / 100) * diameter
        water_level = diameter - water_height + 5

        wave_path = QPainterPath()
        wave_path.moveTo(0, water_level)

        wave_width = diameter / 2
        wave_density = 5
        for x in range(0, self.width()+wave_density, wave_density):
            y = math.sin((x + self._wave_offset) * math.pi / wave_width) * self._wave_height
            wave_path.lineTo(x, water_level + y)

        wave_path.lineTo(self.width(), self.height())
        wave_path.lineTo(0, self.height())
        wave_path.closeSubpath()

        clip_path = QPainterPath()
        clip_path.addEllipse(rect)
        painter.setClipPath(clip_path)

        # 这里根据进度设置水的颜色
        progress_percent = self._progress / 100
        water_color = self.get_color_by_progress(progress_percent)

        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, water_color.lighter(120))
        gradient.setColorAt(0.5, water_color)
        gradient.setColorAt(1, water_color.darker(120))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawPath(wave_path)

        highlight_gradient = QRadialGradient(diameter / 2, diameter / 2, diameter / 2, diameter / 4, diameter / 4)
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, 80))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(highlight_gradient)
        painter.drawEllipse(rect)

        painter.setPen(Qt.white)
        font = painter.font()
        font.setPointSize(int(self.size().width()/10))
        painter.setFont(font)
        text = f"{int(self._progress)}%"
        text_rect = painter.boundingRect(rect, Qt.AlignCenter, text)
        painter.drawText(text_rect, Qt.AlignCenter, text)

    def sizeHint(self):
        return QSize(200, 200)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_pressed = True
            self.clicked.emit()
        elif event.button() == Qt.RightButton:
            self.rightClicked.emit()
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_pressed = False
        return super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()
        return super().mouseDoubleClickEvent(event)