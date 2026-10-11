import os
import re
import webbrowser
import base64
from functools import partial
from PySide6.QtCore import QPoint, QSize, QTimer, QPropertyAnimation
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import TeachingTip, RoundMenu, Action, InfoBar
from qfluentwidgets import FluentIcon as FIF
from ui.float_ball import UI_FloatBall
from src import touda, config, update_checker
from src.logging_config import logger
from ui.components.frameless_dialog import FramelessDialog


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


class FloatBall(QWidget):
    __is_dragging: bool = False
    __start_drag_position: QPoint = QPoint()
    __leftScreen = True
    __screen_size = QSize()

    def __init__(self, screen_size, app: QApplication, version: str = "v0.0.0"):
        super().__init__()
        self.setObjectName("FloatBall")
        self.app = app
        self._version = version
        self._pending_update = None  # 待显示的更新信息（需在 setupUI → showEvent 前初始化）

        # 窗口标志和透明背景必须在 show() 之前设置
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 设置为纯透明 widget，避免任何 DWM 框架残留
        self.setStyleSheet("#FloatBall { background: transparent; }")

        self.ui = UI_FloatBall()
        self.ui.setupUI(self)
        self.setFixedSize(self.ui.waterBall.size())
        self.__screen_size = screen_size
        self.__leftScreen = False

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
        self._cached_menu = None  # 右键菜单缓存（框架构建一次复用，动态区每次打开刷新）
        self._link_menu = None
        self._webvpn_menu = None
        self._account_menu = None
        self._plugin_menu = None
        self._dynamic_spec = None  # 动态菜单区内容指纹（未变化时跳过重建，避免无谓的内存churn）
        self._switch_thread = None  # 账号切换后台线程引用
        self._switch_worker = None  # 账号切换 Worker 引用
        self._update_thread = None  # 检查更新后台线程引用
        self._update_worker = None  # 检查更新 Worker 引用
        # 已在上方 setupUI 前初始化
        x, y = self.main_cfg.get("main", "x", 0), self.main_cfg.get(
            "main", "y", 0
        )  # 设置初始位置为上一次关闭位置

        # 验证坐标在任意可用屏幕范围内，防止副屏移除后窗口显示到不可见区域
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QGuiApplication

        win_rect = QRect(x, y, self.width(), self.height())
        if not any(screen.geometry().intersects(win_rect) for screen in QGuiApplication.screens()):
            primary_geo = QGuiApplication.primaryScreen().availableGeometry()
            x = primary_geo.x() + (primary_geo.width() - self.width()) // 2
            y = primary_geo.y() + (primary_geo.height() - self.height()) // 2
            logger.info(
                "上次关闭位置(%d, %d)不在当前屏幕范围内，已自动居中到主屏(%d, %d)",
                win_rect.x(), win_rect.y(), x, y
            )

        self.move(x, y)

        # 所有初始化完成后再显示窗口（确保窗口标志和透明背景已设置）
        self.show()

    # ── 拖拽支持（替代 DragWindow） ──
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.__is_dragging = True
            self.__start_drag_position = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.__is_dragging:
            pos = event.globalPos() - self.__start_drag_position
            if not self.__leftScreen:
                width = self.__screen_size.width()
                height = self.__screen_size.height()
                geo = self.geometry()
                if pos.x() > width - geo.width():
                    pos.setX(width - geo.width())
                elif pos.x() < 0:
                    pos.setX(0)
                if pos.y() > height - geo.height():
                    pos.setY(height - geo.height())
                elif pos.y() < 0:
                    pos.setY(0)
            self.move(pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self.__is_dragging:
            self.__is_dragging = False
            event.accept()

    def hideEvent(self, event):
        """窗口隐藏时暂停波浪动画，减少 GPU/CPU 占用（定时器保持运行，保证网络认证状态）"""
        if self.ui.waterBall.wave_animation.state() == QPropertyAnimation.Running:
            self.ui.waterBall.wave_animation.pause()
        super().hideEvent(event)

    def on_flux_update(self, total: float, used: float):
        """流量更新槽：水球显示剩余百分比。

        以 FloatBall（主线程 QObject）为接收者连接 wifi.flux_update，
        后台线程发射时 Qt 自动走队列连接，保证在主线程操作 UI。
        """
        self.ui.waterBall.set_progress(
            ((total - used) * 100 / total) if total != 0 else 100
        )

    def showEvent(self, event):
        """窗口显示时恢复波浪动画，并弹出缓存的更新提示（静默启动场景）"""
        if self.ui.waterBall.wave_animation.state() == QPropertyAnimation.Paused:
            self.ui.waterBall.wave_animation.resume()

        # 如果有待显示的更新信息，此时弹出
        if self._pending_update is not None:
            raw = self._pending_update
            self._pending_update = None
            from ui.components.frameless_dialog import UpdateDialog
            dlg = UpdateDialog(
                current_version=self._version,
                latest_tag=raw.tag_name,
                release_body=raw.body,
                download_url=raw.html_url,
                parent=self,
            )
            dlg.exec()

        super().showEvent(event)

    def waterBall_menu(self, pos):
        """右键菜单：菜单框架缓存复用（防内存增长），账号/链接/插件区每次打开时刷新"""
        if self._cached_menu is None:
            self._cached_menu = self._build_menu()
        else:
            self._refresh_dynamic_menus()
        self._cached_menu.exec(self.mapToGlobal(pos))

    def _build_menu(self):
        """一次性构建右键菜单框架（静态部分 + 动态区容器，内容刷新见 _refresh_dynamic_menus）"""
        menu = MyRoundMenu()
        self._link_menu = MyRoundMenu("链接", parent=menu)
        self._webvpn_menu = MyRoundMenu("webvpn相关", parent=menu)
        self._account_menu = MyRoundMenu("账号", parent=menu)
        self._plugin_menu = MyRoundMenu("插件", parent=menu)

        self._webvpn_menu.addActions(
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

        # 动态区内容先填充再挂载（addMenu 后 adjustSize 已就绪）
        self._refresh_dynamic_menus()

        menu.addMenu(self._link_menu)
        menu.addMenu(self._webvpn_menu)
        menu.addMenu(self._account_menu)
        if len(self.pm.plugins) > 0:
            menu.addMenu(self._plugin_menu)

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

    def _refresh_dynamic_menus(self, force: bool = False):
        """刷新动态菜单区（账号/链接/插件）。

        先计算内容指纹，与上次一致时直接跳过重建——既保证菜单反映最新
        状态，又让"内容未变的日常打开"不产生任何 Qt 对象分配（每次重建
        即使正确释放，也会带来堆内存缓存的持续增长）。
        """
        spec = self._dynamic_menus_spec()
        if not force and spec is not None and spec == self._dynamic_spec:
            return
        self._dynamic_spec = spec
        self._repopulate_account_menu()
        self._repopulate_link_menu()
        self._repopulate_plugin_menu()

    def _dynamic_menus_spec(self):
        """计算动态菜单区内容指纹（纯 Python 计算，不创建 Qt 对象）。

        任何一项失败返回 None，调用方将强制重建（安全兜底）。
        """
        try:
            # 账号区：索引 + 名称 + 密码哈希（密码变化也需重建菜单闭包）
            accounts = []
            for file in sorted(os.listdir("config")):
                match = re.match(r"account_(\d+)\.toml", file)
                if match:
                    now = config.CfgParse("config/" + file)
                    name = now.get("setting", "name")
                    password = now.get("setting", "password", "")
                    if name and password:
                        accounts.append((int(match.group(1)), name, hash(password)))

            # 链接区：links.toml 全文
            links = str(
                config.CfgParse(
                    os.path.join(os.getcwd(), "config", "links.toml")
                ).get_all()
            )

            # 插件区：各插件菜单项的功能名列表（内容变化即重建；
            # 调用 get_menu() 产生的临时对象由引用计数立即回收）
            plugins = []
            for plg in self.pm.plugins:
                p = plg["object"]
                try:
                    if self.pm.is_valid_func(p, "get_menu"):
                        names = tuple(
                            a.get("function") for a in (p.get_menu() or [])
                            if isinstance(a, dict)
                        )
                    else:
                        names = None
                    plugins.append((plg["name"], names))
                except Exception:
                    plugins.append((plg.get("name", "?"), "ERROR"))

            return (tuple(accounts), links, tuple(plugins))
        except Exception:
            return None

    def _clear_menu_for_rebuild(self, menu):
        """清空菜单并显式销毁旧子菜单。

        qfluentwidgets 的 RoundMenu.clear()/removeMenu() 只把子菜单移出
        _subMenus 列表并移除列表项，QObject 父子关系（parent=menu）仍然
        保留，旧子菜单永远不会被释放——每次刷新会按子菜单数量线性泄漏。
        因此先收集旧子菜单引用，clear 后逐个 deleteLater 显式释放。
        """
        old_submenus = list(menu._subMenus)
        menu.clear()
        for sub in old_submenus:
            try:
                sub.hide()
            except RuntimeError:
                pass  # C++ 对象已销毁，无需处理
            sub.deleteLater()

    def _repopulate_account_menu(self):
        """重建账号子菜单（读取全部 account_*.toml）"""
        menu = self._account_menu
        self._clear_menu_for_rebuild(menu)
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
                        menu.addAction(
                            Action(
                                text="切换为" + name,
                                icon=FIF.CHAT,
                                triggered=partial(self.change_account, name, password, index),
                            )
                        )
            logger.info("账号菜单加载完成")
        except Exception:
            logger.exception("加载账号菜单失败")

    def _repopulate_link_menu(self):
        """重建链接子菜单（剪切板链接 + links.toml 全部类别）"""
        menu = self._link_menu
        self._clear_menu_for_rebuild(menu)
        try:
            menu.addAction(
                Action(text="剪切板链接", icon=FIF.LINK, triggered=self.open_custom_link)
            )
            self.create_links_menu(menu)
        except Exception:
            logger.exception("加载链接菜单失败")

    def _repopulate_plugin_menu(self):
        """重建插件子菜单：逐个调用插件 get_menu()，单项失败不影响其他插件"""
        menu = self._plugin_menu
        self._clear_menu_for_rebuild(menu)
        for plg in self.pm.plugins:
            try:
                p = plg["object"]
                if not self.pm.is_valid_func(p, "get_menu"):
                    continue
                plg_actions = []
                plg_menu_items = p.get_menu() or []
                for a in plg_menu_items:
                    try:
                        if not callable(a.get("object")):
                            # 非可调用对象视为分隔线或暂不可用项，跳过
                            continue
                        plg_actions.append(
                            Action(text=a["function"], triggered=a["object"])
                        )
                    except Exception:
                        logger.exception(
                            f"插件 [{plg.get('name', '?')}] 菜单项 [{a.get('function', '?')}] 创建失败"
                        )
                if not plg_actions:
                    logger.warning(
                        f"插件 [{plg.get('name', '?')}] 没有可用的菜单项"
                    )
                else:
                    sub_menu = MyRoundMenu(plg["name"], parent=menu)
                    sub_menu.addActions(plg_actions)
                    menu.addMenu(sub_menu)
            except Exception:
                logger.exception(
                    f"加载插件 [{plg.get('name', '?')}] 菜单失败"
                )

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
            if FramelessDialog.show_confirm("一键登录链接", "是否在浏览器中打开一键登录链接？", self):
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
        if FramelessDialog.show_confirm(
            "选择:",
            f"是否使用webvpn打开{name[:70] + ('...' if len(name) > 70 else '')}",
            self,
        ):
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

    def check_update(self, silent: bool = True):
        """检查版本更新

        Args:
            silent: 如果为 True，没有新版本时静默（不弹提示）；
                     如果为 False，无论有没有新版本都会弹提示
        """
        try:
            # 如果已有检查线程在运行，跳过（捕获 RuntimeError 防止 C++ 对象已删除）
            try:
                thread_busy = (
                    self._update_thread is not None
                    and self._update_thread.isRunning()
                )
            except RuntimeError:
                thread_busy = False
                self._update_thread = None
                self._update_worker = None
            if thread_busy:
                return

            from src.touda import start_worker_in_thread
            from PySide6.QtCore import Qt as QtNS

            # 用 list 做闭包容器存储线程结果，避免通过 Signal(object) 传递自定义对象（QueuedConnection 会序列化失败）
            _result = []

            def do_check():
                try:
                    _result.append(update_checker.check_for_update(self._version))
                except Exception as e:
                    _result.append(e)

            def on_finished():
                # 线程结束后读取闭包中的结果
                raw = _result[0] if _result else None
                # 清理线程引用
                if self._update_thread is thread and self._update_worker is worker:
                    self._update_thread = None
                    self._update_worker = None

                if isinstance(raw, Exception):
                    if not silent:
                        InfoBar.error(
                            title="检查更新失败",
                            content="网络异常，请稍后重试",
                            duration=3000,
                            parent=self,
                        )
                    return

                if raw is None:
                    if not silent:
                        InfoBar.info(
                            title="已是最新版",
                            content="当前没有可用更新",
                            duration=3000,
                            parent=self,
                        )
                    return

                # 有新版本：窗口可见直接弹，隐藏时缓存等 showEvent
                if self.isVisible():
                    from ui.components.frameless_dialog import UpdateDialog
                    dlg = UpdateDialog(
                        current_version=self._version,
                        latest_tag=raw.tag_name,
                        release_body=raw.body,
                        download_url=raw.html_url,
                        parent=self,
                    )
                    dlg.exec()
                else:
                    self._pending_update = raw

            thread, worker = start_worker_in_thread(do_check, "检查更新")
            thread.finished.connect(on_finished, QtNS.QueuedConnection)
            self._update_thread = thread
            self._update_worker = worker

        except Exception:
            logger.exception("检查更新失败")


class Update_timer(QTimer):
    def __init__(self, wifi, parent=None):
        super().__init__(parent=parent)
        self.wifi = wifi
        self._thread = None  # 当前轮询线程引用（防重入）
        self._worker = None
        try:
            main = config.CfgParse(os.path.join(os.getcwd(), "config", "main.toml"))
            interval = int(main.get("main", "timer_interval", 60000))
        except Exception:
            interval = 60000
        self.setInterval(max(interval, 10000))
        self.timeout.connect(self.update)
        self.start()

    def update(self):
        """轮询入口：网络请求放入后台线程执行，避免阻塞 UI 主线程"""
        try:
            busy = self._thread is not None and self._thread.isRunning()
        except RuntimeError:
            # C++ 对象已销毁，视为空闲
            busy = False
            self._thread = None
            self._worker = None
        if busy:
            logger.info("上一轮状态检查尚未完成，跳过本次轮询")
            return

        def do_update():
            state = self.wifi.getState()
            if state.state == "未登录":
                self.wifi.login()

        thread, worker = touda.start_worker_in_thread(do_update, "状态轮询")
        self._thread = thread
        self._worker = worker
