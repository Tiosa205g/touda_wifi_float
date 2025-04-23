import math
from PySide6.QtCore import Qt, QRectF, QPropertyAnimation, Property, QSize, Signal
from PySide6.QtGui import QPainter, QPainterPath, QColor, QBrush, QLinearGradient
from PySide6.QtWidgets import  QWidget
class WaterBall(QWidget):
    clicked = Signal()
    rightClicked = Signal()
    doubleClicked = Signal()
    def __init__(self, x=200, speed=1, water_color=QColor(33, 150, 243), border_color = QColor(100, 100, 100), background_color = QColor(128,128,128), parent=None):
        super().__init__(parent)
        scale = x / 200
        self._progress = 0
        self._wave_offset = 0
        self._wave_height = 10*scale
        self._wave_speed = 0.05
        self._water_color = water_color
        self._border_color = border_color
        self._background_color = background_color
        self.setFixedSize(x, x)

        # 波浪动画
        self.wave_animation = QPropertyAnimation(self, b"wave_offset")
        self.wave_animation.setDuration(int(100000/speed))
        self.wave_animation.setLoopCount(-1)
        self.wave_animation.setStartValue(math.pi*18)
        self.wave_animation.setEndValue(math.pi*1800)
        self.wave_animation.start()
        
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
        
        # 绘制外框
        diameter = min(self.width(), self.height()) - 10
        rect = QRectF(5, 5, diameter, diameter)
        painter.setPen(self._border_color)
        painter.drawEllipse(rect)

        # 填充背景色
        painter.setBrush(QBrush(self._background_color))
        painter.drawEllipse(rect)
        
        # 计算水位高度（Y坐标从下往上增长）
        water_height = (1 - self._progress / 100) * diameter
        water_level = diameter - water_height + 5
        
        # 创建波浪路径
        wave_path = QPainterPath()
        wave_path.moveTo(0, water_level)
        
        wave_width = diameter / 2  # 波浪宽度
        for x in range(0, self.width()+2, 2):
            y = math.sin((x + self._wave_offset) * math.pi / wave_width) * self._wave_height
            wave_path.lineTo(x, water_level + y)
        
        wave_path.lineTo(self.width(), self.height())
        wave_path.lineTo(0, self.height())
        wave_path.closeSubpath()
        
        # 设置裁剪路径（圆形内部）
        clip_path = QPainterPath()
        clip_path.addEllipse(rect)
        painter.setClipPath(clip_path)
        
        # 绘制波浪渐变
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, self._water_color.lighter(120))
        gradient.setColorAt(0.5, self._water_color)
        gradient.setColorAt(1, self._water_color.darker(120))
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawPath(wave_path)
        
        # 绘制中间的数字
        painter.setPen(Qt.white)
        font = painter.font()
        font.setPointSize(int(self.size().width()/10))
        painter.setFont(font)
        text = f"{self._progress}%"
        text_rect = painter.boundingRect(rect, Qt.AlignCenter, text)
        painter.drawText(text_rect, Qt.AlignCenter, text)
        
    def sizeHint(self):
        return QSize(200, 200)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        elif event.button() == Qt.RightButton:
            self.rightClicked.emit()
        return super().mousePressEvent(event)
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()
        return super().mouseDoubleClickEvent(event)