import sys
import os
from pathlib import Path


def _is_source():
    """检测是否为源码运行（而非打包 exe）"""
    return sys.argv[0].endswith('.py')


def _fix_working_dir():
    """将工作目录切换到程序所在目录，确保 os.getcwd() 始终指向正确位置"""
    if _is_source():
        # 源码运行：main.py 所在目录
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        # Nuitka 打包的 exe
        exe_dir = os.path.dirname(sys.executable)
    os.chdir(exe_dir)


# 在导入业务模块前切换工作目录，否则所有 os.getcwd() 都会跑偏
_fix_working_dir()

# import init
from src.logging_config import logger
from src.config import CfgParse

VERSION = "v1.4.7.1"
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


def _parse_theme(theme_value: str):
    """将主题字符串(auto/light/dark)转为 Theme 枚举"""
    from qfluentwidgets import Theme
    v = str(theme_value or "auto").lower()
    if v == "auto":
        return Theme.AUTO
    return Theme.LIGHT if v == "light" else Theme.DARK


def _is_admin() -> bool:
    """检查当前进程是否以管理员权限运行"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _request_admin_restart():
    """以管理员权限重新启动当前程序（不阻塞等待）"""
    import ctypes
    args = ' '.join(f'"{a}"' for a in sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, args, None, 1  # SW_SHOWNORMAL
    )
    sys.exit(0)


if __name__ == "__main__":
    argv = sys.argv
    logger.info(f"argv: {argv}")

    init_config()

    # ── 管理员启动检查 ──
    # 从注册表启动时带 --auto-start 标记，跳过提权，否则开机弹 UAC 没人点
    is_auto_start = '--auto-start' in argv
    if is_auto_start:
        logger.info("开机自启模式：跳过管理员提权检查")

    cfg = CfgParse(MAIN_CFG)
    need_admin = str(cfg.get('startup', 'run_as_admin', False)).lower() == 'true'
    if need_admin and not _is_admin() and not is_auto_start and not _is_source():
        logger.info("检测到管理员启动配置，正在请求提权…")
        _request_admin_restart()

    # ── 静默启动标志 ──
    silent_start = str(cfg.get('startup', 'silent', False)).lower() == 'true'
    if silent_start:
        logger.info("静默启动模式：窗口启动后自动隐藏到托盘")

    from PySide6.QtGui import QIcon, QPixmapCache
    from PySide6.QtWidgets import QApplication
    from src.touda import start_worker_in_thread
    from src import win_float_ball
    from src.plugin_manager import Manager
    from src.tray import Tray
    from qfluentwidgets import setTheme

    app = QApplication()
    app.setQuitOnLastWindowClosed(False)
    # 根据配置设置主题（自动/浅色/深色）
    try:
        cfg = CfgParse(MAIN_CFG)
        theme_value = cfg.get("ui", "theme", "auto")
        t = _parse_theme(theme_value)
        setTheme(t)
        logger.info(f"应用主题设置: {theme_value}")
    except Exception:
        pass
    win = win_float_ball.FloatBall(app.primaryScreen().size(), app)
    win.setWindowIcon(QIcon("res/ico/favicon.ico"))
    # 限制 QPixmapCache 大小（默认 10MB → 5MB），减少 bitmap 缓存占用
    QPixmapCache.setCacheLimit(5120)

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

    if silent_start:
        # 静默启动：窗口显示后立即隐藏到系统托盘
        win.setHidden(True)

    app.exec()
