import time

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from src.touda import Worker
from PySide6.QtCore import QThread
from src import win_float_ball
from src import Tray
import sys
import init

if __name__ == '__main__':
    argv = sys.argv
    if len(argv) == 2:
        if argv[1] == "setting":
            while True:
                try:
                    init.main()
                except Exception as e:
                    print('发生错误：', e)
    app = QApplication()

    win = win_float_ball.FloatBall(app.primaryScreen().size(),app)
    win.setWindowIcon(QIcon('res/ico/favicon.ico'))
    win.tray = Tray(win)
    win.bridge.wifi.state_update.connect(win.tray.profile.onUpdateState)
    win.bridge.wifi.flux_update.connect(lambda total,used : win.ui.waterBall.set_progress((((total-used)*100/total) if total != 0 else 100)))

    handle_thread = QThread()
    wifi_worker = Worker(win.bridge.wifi.login)
    webvpn_worker = Worker(win.bridge.webvpn.autoLogin)
    wifi_worker.finished.connect(lambda x: print(f"校园网登录：{x}"))
    webvpn_worker.finished.connect(lambda x: print(f"webvpn登录：{x}"))
    wifi_worker.moveToThread(handle_thread)
    webvpn_worker.moveToThread(handle_thread)
    handle_thread.started.connect(wifi_worker.run_task)
    handle_thread.started.connect(webvpn_worker.run_task)
    handle_thread.start()

    win.show()

    app.exec()