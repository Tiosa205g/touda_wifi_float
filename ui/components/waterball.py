import sys
import math
from PySide6.QtCore import Qt, QRectF, QPointF, QPropertyAnimation, QTimer, Property,QSize
from PySide6.QtGui import QPainter, QPainterPath, QColor, QBrush, QLinearGradient
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton
from qfluentwidgets import PushButton
class WaterBall(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0
        self._wave_offset = 0
        self._wave_height = 10
        self._wave_speed = 0.05
        self._water_color = QColor(33, 150, 243)
        self._border_color = QColor(100, 100, 100)
        
        # 波浪动画
        self.wave_animation = QPropertyAnimation(self, b"wave_offset")
        self.wave_animation.setDuration(2500)
        self.wave_animation.setLoopCount(-1)
        self.wave_animation.setStartValue(0)
        self.wave_animation.setEndValue(math.pi*180)
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
        
    def sizeHint(self):
        return QSize(200, 200)

class DemoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("水球进度效果")
        self.resize(300, 350)
        
        layout = QVBoxLayout()
        self.water_ball = WaterBall()
        layout.addWidget(self.water_ball, alignment=Qt.AlignCenter)
        
        self.btn_start = QPushButton("开始动画")
        self.btn_start.clicked.connect(self.start_animation)
        layout.addWidget(self.btn_start)
        
        self.setLayout(layout)
        
    def start_animation(self):
        self.water_ball.progress = 50


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DemoWindow()
    window.show()
    sys.exit(app.exec())