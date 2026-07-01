import os
import re
import webbrowser
import base64
from functools import partial
from PySide6.QtCore import QPoint, QTimer, QPropertyAnimation
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import TeachingTip, RoundMenu, Action, Dialog
from qfluentwidgets import FluentIcon as FIF
from ui.float_ball import UI_FloatBall
from ui.windows.drag_window import DragWindow
from src import touda, config
from src.logging_config import logger


def _cfg_dir() -> str:
    """获取配置目录路径（延迟求值，避免模块导入时锁定 os.getcwd()）"""
    return os.path.join(os.getcwd(), "config")


class MyRoundMenu(RoundMenu):
    # 重写方法：点击有子菜单的项时在右侧展开子菜单
    def _onItemClicked(self, item):
        super()._onItemClicked(item)
        action = item.data(Qt.UserRole)
        if action in self._subMenus and action.isEnabled():
            pos = self.mapToGlobal(QPoint(self.width() - 25, 30))
            action.exec(pos)

    def mousePressEvent(self, e):
        rect = self.geometry()
        rect.setX(rect.x() - self.width())
        w = self.childAt(e.pos())
        if (
            (w is not self.view)
            and (not self.view.isAncestorOf(w))
            and (not rect.contains(e.globalPos()))
        ):
            self._hideMenu(True)


class FloatBall(DragWindow):
    def __init__(self, screen_size, app: QApplication):
        super().__init__()
        self.app = app
        self.ui = UI_FloatBall()
        self.ui.setupUI(self)
        self.setFixedSize(self.ui.waterBall.size())
        self.setResizeEnabled(False)

        self.setCanLeftScreen(False, screen_size=screen_size)
        self.ui.waterBall.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.waterBall.customContextMenuRequested.connect(self.waterBall_menu)

        # 初始化配置和核心对象
        self.main_cfg = config.CfgParse(os.path.join(os.getcwd(), "config", "main.toml"))
        current_cfg = config.CfgParse(
            os.path.join(os.getcwd(), "config", f"account_{self.main_cfg.get('main','current_account',0)}.toml")
        )
        webvpn_name = self.main_cfg.get("webvpn", "name", "")
        webvpn_password = base64.b64decode(
            self.main_cfg.get("webvpn", "password", "").encode("utf-8")
        ).decode("utf-8")
        webvpn_key = self.main_cfg.get("webvpn", "key", "")
        webvpn_twfid = self.main_cfg.get("webvpn", "twfid", "")
        name = current_cfg.get("setting", "name", "")
        password = base64.b64decode(
            current_cfg.get("setting", "password", "").encode("utf-8")
        ).decode("utf-8")

        self.wifi = touda.wifi(name, password)
        self.webvpn = touda.webvpn(
            webvpn_name, webvpn_password, webvpn_key, webvpn_twfid
        )
        self.webvpn.twfid_update.connect(
            lambda twfid: self.main_cfg.write("webvpn", "twfid", twfid)
        )
        self._used_twfid = None  # 记录已使用过的 twfid，用于判断是否首次使用

        self.update_timer = Update_timer(self.wifi, parent=self)
        self._cached_menu = None  # 右键菜单缓存（首次打开时构建，后续复用）
        self._switch_thread = None  # 账号切换后台线程引用
        self._switch_worker = None  # 账号切换 Worker 引用
        x, y = self.main_cfg.get("main", "x", 0), self.main_cfg.get(
            "main", "y", 0
        )  # 设置初始位置为上一次关闭位置
        self.move(x, y)

    def hideEvent(self, event):
        """窗口隐藏时暂停波浪动画，减少 GPU/CPU 占用（定时器保持运行，保证网络认证状态）"""
        if self.ui.waterBall.wave_animation.state() == QPropertyAnimation.Running:
            self.ui.waterBall.wave_animation.pause()
        super().hideEvent(event)

    def showEvent(self, event):
        """窗口显示时恢复波浪动画"""
        if self.ui.waterBall.wave_animation.state() == QPropertyAnimation.Paused:
            self.ui.waterBall.wave_animation.resume()
        super().showEvent(event)

    def waterBall_menu(self, pos):
        """右键菜单：菜单对象缓存复用，每次打开不再新建，彻底解决内存增长"""
        if self._cached_menu is None:
            self._cached_menu = self._build_menu()
        self._cached_menu.exec(self.mapToGlobal(pos))

    def _build_menu(self):
        """一次性构建右键菜单（仅在首次右键时调用）"""
        menu = MyRoundMenu()
        accountMenu = MyRoundMenu("账号", parent=menu)
        linkMenu = MyRoundMenu("链接", parent=menu)
        webvpnMenu = MyRoundMenu("webvpn相关", parent=menu)
        pluginMenu = MyRoundMenu("插件", parent=menu)

        try:
            for file in sorted(os.listdir("config")):
                match = re.match(r"account_(\d+)\.toml", file)
                if match:
                    now = config.CfgParse("config/" + file)
                    name = now.get("setting", "name")
                    password = base64.b64decode(
                        now.get("setting", "password", "").encode("utf-8")
                    ).decode("utf-8")
                    if name and password:
                        index = int(match.group(1))
                        accountMenu.addAction(
                            Action(
                                text="切换为" + name,
                                icon=FIF.CHAT,
                                triggered=partial(self.change_account, name, password, index),
                            )
                        )
            logger.info("账号菜单加载完成")
        except Exception:
            logger.exception("加载账号菜单失败")

        try:
            linkMenu.addAction(
                Action(text="剪切板链接", icon=FIF.LINK, triggered=self.open_custom_link)
            )
            self.create_links_menu(linkMenu)
        except Exception:
            logger.exception("加载链接菜单失败")

        webvpnMenu.addActions(
            [
                Action(
                    text="一键登录链接",
                    icon=FIF.ACCEPT,
                    triggered=self.copy_login_link,
                ),
                Action(
                    text="转换剪贴板链接",
                    icon=FIF.LABEL,
                    triggered=self.clipboard_convert_webvpn,
                ),
                Action(text="复制6位口令", icon=FIF.VPN, triggered=self.copy_totp),
                Action(text="复制twfid", icon=FIF.CODE, triggered=self.copy_twfid),
            ]
        )

        menu.addMenu(linkMenu)
        menu.addMenu(webvpnMenu)
        menu.addMenu(accountMenu)

        try:
            if len(self.pm.plugins) > 0:
                for plg in self.pm.plugins:
                    p = plg["object"]
                    if self.pm.is_valid_func(p, "get_menu"):
                        plg_actions = [
                            Action(text=a["function"], triggered=a["object"])
                            for a in p.get_menu()
                        ]
                        sub_menu = MyRoundMenu(plg["name"], parent=pluginMenu)
                        sub_menu.addActions(plg_actions)
                        pluginMenu.addMenu(sub_menu)
                menu.addMenu(pluginMenu)
        except Exception:
            logger.exception("加载插件菜单失败")

        menu.addSeparator()
        menu.addAction(
            Action(
                text="立即更新状态",
                icon=FIF.SYNC,
                triggered=self.update_timer.update,
            )
        )
        menu.addAction(
            Action(text="隐藏", icon=FIF.HIDE, triggered=lambda: self.setHidden(True))
        )
        return menu

    def clipboard_convert_webvpn(self):
        count = 0
        convert_count = 0

        cb = self.app.clipboard()
        site = cb.text()

        it = re.finditer("(https?://)([^/]*)(/.*)", site, re.I)

        for match in it:
            all_url = match.group()
            count += 1

            if "webvpn.stu.edu.cn:8118" in all_url:
                continue

            vpn_url = touda.get_vpn_url(all_url)
            if vpn_url:
                site = site.replace(all_url, vpn_url, 1)
                convert_count += 1

        cb.setText(site)
        logger.info(f"转换结果: 共识别到{count}个链接,成功修改{convert_count}个链接")

    def open_custom_link(self):
        """
        剪辑板链接
        """
        link = self.app.clipboard().text()
        self.open_link_window(link, link)

    def copy_login_link(self):
        """
        一键登录webvpn：询问是否在浏览器打开，否则复制链接
        """
        try:
            link = self.webvpn.create_redirect_url("https://webvpn.stu.edu.cn/")
            w = Dialog(
                "一键登录链接",
                "是否在浏览器中打开一键登录链接？",
                self,
            )
            w.yesButton.setText("打开浏览器")
            w.cancelButton.setText("复制到剪贴板")
            if w.exec():
                webbrowser.open(link)
            else:
                self.app.clipboard().setText(link)
        except Exception:
            logger.exception("获取登录链接失败")

    def copy_totp(self):
        """
        复制6位totp口令
        """
        try:
            key = self.webvpn.key
            totp = self.webvpn.encrypt.gettotpkey(key)
            self.app.clipboard().setText(totp)
        except Exception:
            logger.exception("获取totp失败")

    def copy_twfid(self):
        """
        复制用于登录的twfid
        """
        try:
            self.webvpn.autoLogin()
        except Exception:
            logger.exception("自动登录webvpn失败，无法获取twfid")
            return
        twfid = self.webvpn.twfid
        self.app.clipboard().setText(twfid)

    def open_link_window(self, name: str, link: str, *args):
        w = Dialog(
            "选择:",
            f"是否使用webvpn打开{name[:70] + ('...' if len(name) > 70 else '')}",
            self,
        )
        w.yesButton.setText("是")
        w.cancelButton.setText("否")
        if w.exec():
            try:
                self.webvpn.autoLogin()
                url = touda.get_vpn_url(link)
                # 仅在首次使用该 twfid 时带上 twfid 参数，避免重复传递
                if self.webvpn.twfid and self.webvpn.twfid != self._used_twfid:
                    url = f"https://webvpn.stu.edu.cn/portal/shortcut.html?twfid={self.webvpn.twfid}&url={url}"
                    self._used_twfid = self.webvpn.twfid
                webbrowser.open(url)
            except Exception:
                logger.exception("webvpn打开链接失败")
                webbrowser.open(link)
        else:
            webbrowser.open(link)

    def create_links_menu(self, menu: MyRoundMenu):
        """
        添加链接菜单到菜单上
        """
        link_all = config.CfgParse(os.path.join(os.getcwd(), "config", "links.toml")).get_all()

        for link_type in link_all:
            linkType = MyRoundMenu(link_type, parent=menu)
            for name in link_all[link_type]:
                link = link_all[link_type][name]
                linkType.addAction(
                    Action(
                        text=name,
                        icon=FIF.LINK,
                        triggered=partial(self.open_link_window, name, link),
                    )
                )
            menu.addMenu(linkType)

    def change_account(self, name, password, index, *args):
        """
        切换账号：放入后台线程执行，避免阻塞 UI
        """
        try:
            thread_busy = (
                self._switch_thread is not None
                and self._switch_thread.isRunning()
            )
        except RuntimeError:
            thread_busy = False
            self._switch_thread = None
            self._switch_worker = None

        if thread_busy:
            logger.warning("账号切换正在进行中，忽略重复请求")
            return

        try:
            main = config.CfgParse(os.path.join(os.getcwd(), "config", "main.toml"))
            from PySide6.QtCore import Qt as QtNS

            # 先保存当前账号索引，确保重启后使用新账号（无论登录是否成功）
            try:
                main.write("main", "current_account", index)
            except Exception:
                pass

            def do_switch():
                return self.wifi.change_account(name, password)

            def on_finished(result):
                self._switch_thread = None
                self._switch_worker = None
                ok = isinstance(result, bool) and result
                if ok:
                    logger.info("切换账号成功")
                else:
                    logger.info("切换账号失败，但账号配置已保存，重启后将使用新账号")

            # 创建后台线程，on_finished 使用 QueuedConnection 确保在主线程执行
            thread, worker = touda.start_worker_in_thread(do_switch, "切换账号")
            worker.finished.connect(on_finished, QtNS.QueuedConnection)

            self._switch_thread = thread
            self._switch_worker = worker
        except Exception as e:
            self._switch_thread = None
            self._switch_worker = None
            logger.exception(f"切换账号出错: {e}")


class Update_timer(QTimer):
    def __init__(self, wifi, parent=None):
        super().__init__(parent=parent)
        try:
            self.wifi = wifi
            main = config.CfgParse(os.path.join(os.getcwd(), "config", "main.toml"))
            interval = int(main.get("main", "timer_interval", 60000))
        except Exception:
            interval = 60000
        self.setInterval(interval)
        self.timeout.connect(self.update)
        self.start()

    def update(self):
        state = self.wifi.getState()
        if state.state == "未登录":
            self.wifi.login()
