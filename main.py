
import sys
import os
import init
from src.logging_config import logger

VERSION = "v1.2.0"
CONFIG_DIR = os.path.join(os.getcwd(), "config")
MAIN_CFG = os.path.join(CONFIG_DIR, "main.toml")
LINKS_CFG = os.path.join(CONFIG_DIR, "links.toml")



if __name__ == '__main__':
    argv = sys.argv
    logger.info(f"argv: {argv}")
    if len(argv) == 2:
        if argv[1] == "setting":
            # 如果是打包的exe且需要控制台，动态创建控制台
            if getattr(sys, 'frozen', False):  # 检查是否为打包的exe
                import ctypes
                ctypes.windll.kernel32.AllocConsole()
                # 重定向标准输入输出到控制台
                try:
                    sys.stdout = open('CONOUT$', 'w')
                    sys.stderr = open('CONOUT$', 'w')
                    sys.stdin = open('CONIN$', 'r')
                except Exception as e:
                    sys.exit("重定向失败退出")
            while True:
                try:
                    init.main()
                except Exception as e:
                    logger.exception(f'发生错误：{e}')
    
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from src.touda import Worker
    from PySide6.QtCore import QThread
    from src import win_float_ball
    from src.tray import Tray
    from src.config import CfgParse
    from qfluentwidgets import setTheme, Theme
    app = QApplication()
    # 根据配置设置主题（自动/浅色/深色）
    try:
        cfg = CfgParse(MAIN_CFG)
        theme_value = str(cfg.get('ui', 'theme', 'auto') or 'auto').lower()
        t = Theme.AUTO if theme_value == 'auto' else (Theme.LIGHT if theme_value == 'light' else Theme.DARK)
        setTheme(t)
        logger.info(f'应用主题设置: {theme_value}')
    except Exception:
        pass
    win = win_float_ball.FloatBall(app.primaryScreen().size(),app)
    win.setWindowIcon(QIcon('res/ico/favicon.ico'))
    win.tray = Tray(win,VERSION)
    win.bridge.wifi.state_update.connect(win.tray.profile.onUpdateState)
    win.bridge.wifi.flux_update.connect(lambda total,used : win.ui.waterBall.set_progress((((total-used)*100/total) if total != 0 else 100)))

    # 为每个耗时任务创建独立的 QThread，避免把多个任务放到同一个线程导致串行和难以管理
    def start_worker_in_thread(callable_func, name_prefix):
        thread = QThread()
        thread.setObjectName(name_prefix + "_thread")
        worker = Worker(callable_func)
        worker.moveToThread(thread)
        # 当线程启动时运行任务
        thread.started.connect(worker.run_task)
        # 打印/处理完成结果
        worker.finished.connect(lambda x, n=name_prefix: logger.info(f"{n}：{x}"))
        # 任务结束后清理 worker 和退出线程
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        # 线程退出后删除线程对象
        thread.finished.connect(thread.deleteLater)
        thread.start()
        return thread, worker

    wifi_thread, wifi_worker = start_worker_in_thread(win.bridge.wifi.login, "校园网登录")
    webvpn_thread, webvpn_worker = start_worker_in_thread(win.bridge.webvpn.autoLogin, "webvpn登录")

    from PySide6.QtCore import QCoreApplication

    def stop_threads_and_wait():
        for t in (wifi_thread, webvpn_thread):
            try:
                if t is not None and t.isRunning():
                    t.quit()
                    # 等待最多 2 秒，可根据需要调整
                    t.wait(2000)
            except Exception:
                pass

    QCoreApplication.instance().aboutToQuit.connect(stop_threads_and_wait)

    win.show()

    app.exec()