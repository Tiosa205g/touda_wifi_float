import sys
import os
from pathlib import Path

# import init
from src.logging_config import logger
from src.config import CfgParse

VERSION = "v1.4.6"
CONFIG_DIR = os.path.join(os.getcwd(), "config")
MAIN_CFG = os.path.join(CONFIG_DIR, "main.toml")
LINKS_CFG = os.path.join(CONFIG_DIR, "links.toml")


def init_config():
    new_files = ["main", "account_0", "links"]
    logger.info("检查配置目录...")
    if not os.path.exists("config"):
        logger.info("正在初始化配置...")
        os.mkdir("config")

        for file in new_files:
            Path(f"config/{file}.toml").touch()

        cfg = [CfgParse(f"config/{file}.toml") for file in new_files]
        cfg[0].write("main", "current_account", "0")

        # 写入默认链接
        cfg[2].write("汕大", "汕大官网", "https://www.stu.edu.cn/")
        cfg[2].write("汕大", "教务系统", "https://jw.stu.edu.cn/")
        cfg[2].write("汕大", "mystu", "https://my.stu.edu.cn/")
    else:
        for file in new_files:
            if not os.path.exists(f"config/{file}.toml"):
                Path(f"config/{file}.toml").touch()


if __name__ == "__main__":
    argv = sys.argv
    logger.info(f"argv: {argv}")

    init_config()

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from src.touda import start_worker_in_thread
    from src import win_float_ball
    from src.plugin_manager import Manager
    from src.tray import Tray
    from qfluentwidgets import setTheme, Theme

    app = QApplication()
    app.setQuitOnLastWindowClosed(False)
    # 根据配置设置主题（自动/浅色/深色）
    try:
        cfg = CfgParse(MAIN_CFG)
        theme_value = str(cfg.get("ui", "theme", "auto") or "auto").lower()
        t = (
            Theme.AUTO
            if theme_value == "auto"
            else (Theme.LIGHT if theme_value == "light" else Theme.DARK)
        )
        setTheme(t)
        logger.info(f"应用主题设置: {theme_value}")
    except Exception:
        pass
    win = win_float_ball.FloatBall(app.primaryScreen().size(), app)
    win.setWindowIcon(QIcon("res/ico/favicon.ico"))
    win.tray = Tray(win, VERSION)
    win.pm = Manager(
        win.wifi, win.webvpn, VERSION, CONFIG_DIR, MAIN_CFG, LINKS_CFG,
        app=app, parent=win
    )

    win.wifi.state_update.connect(win.tray.profile.onUpdateState)
    win.wifi.state_update.connect(
        lambda state: logger.info(f"校园网状态更新：{state}")
    )
    win.wifi.flux_update.connect(
        lambda total, used: win.ui.waterBall.set_progress(
            (((total - used) * 100 / total) if total != 0 else 100)
        )
    )

    # 后台执行校园网登录和 WebVPN 登录，不阻塞 UI
    wifi_thread, wifi_worker = start_worker_in_thread(
        win.wifi.login, "校园网登录"
    )
    webvpn_thread, webvpn_worker = start_worker_in_thread(
        win.webvpn.autoLogin, "webvpn登录"
    )

    win.show()

    app.exec()
