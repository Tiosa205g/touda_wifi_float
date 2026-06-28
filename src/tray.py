import os
import weakref
from PySide6.QtWidgets import QSystemTrayIcon
from qfluentwidgets import SystemTrayMenu, Action
from src import config
from ui.windows.settings_window import SettingsWindow
from src.logging_config import logger
from ui.components import ProfileCard
path = os.getcwd()
class Tray(QSystemTrayIcon):
    def __init__(self, parent=None,version:str="v1.0.0"):
        super().__init__(parent=parent)
        self.setIcon(parent.windowIcon())
        self.setToolTip('Touda WiFi')

        # 必须先创建 menu，因为 ProfileCard 需要以 menu 为 parent
        self.menu = SystemTrayMenu("touda_wifi", parent=parent)
        self.profile = ProfileCard("res/ico/favicon.ico", "<UNK>", "<UNK>@stu.edu.cn",version, parent=self.menu)
        self.menu.addWidget(self.profile,selectable=False)
        self.menu.aboutToShow.connect(self.onMenuShow)
        self.menu.addAction(Action(text='设置', triggered=self.open_settings))
        self.menu.addActions([Action(text='退出', triggered=self.quit)])
        self.activated.connect(self.toggle)


        self.setContextMenu(self.menu)

        self.show()
        logger.info('托盘创建完毕')
        self._settings_win = None
    def onMenuShow(self):
        self.menu.setFocus()
    def toggle(self, reason):
        
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.parent().setHidden(not self.parent().isHidden())
    def open_settings(self):
        # 安全地打开设置窗口：处理已删除的 Qt 对象引用
        win = self._settings_win
        if win is not None:
            try:
                if win.isVisible():
                    win.raise_()
                    win.activateWindow()
                    return
            except RuntimeError:
                # C++ 对象已被删除，清空引用以便重新创建
                self._settings_win = None

        # 创建新的设置窗口，并在销毁时自动清理引用
        try:
            self._settings_win = SettingsWindow()
            # 窗口关闭并删除后，自动将引用置空，避免悬空对象
            # 使用弱引用避免 lambda 强捕获 self 导致引用循环
            weak_self = weakref.ref(self)
            try:
                self._settings_win.destroyed.connect(
                    lambda win=weak_self: win() is not None and setattr(win(), '_settings_win', None)
                )
            except Exception:
                pass
            self._settings_win.show()
        except Exception as e:
            logger.exception(f"打开设置窗口失败: {e}")

    def quit(self):
        x,y=self.parent().geometry().x(),self.parent().geometry().y()
        mainc = config.CfgParse(os.getcwd()+"/config/main.toml")
        mainc.write('main','x',x)
        mainc.write('main','y',y)
        # 通知所有插件释放资源
        if hasattr(self.parent(), 'pm') and self.parent().pm is not None:
            self.parent().pm.shutdown()
        # 清理配置文件缓存
        config.CfgParse.clear_cache()
        # 关闭网络会话连接池，释放 socket/内存资源
        try:
            parent = self.parent()
            if hasattr(parent, 'wifi') and parent.wifi is not None:
                parent.wifi.session.close()
            if hasattr(parent, 'webvpn') and parent.webvpn is not None:
                parent.webvpn.session.close()
        except Exception:
            pass
        logger.info('quit')
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.instance().quit()


