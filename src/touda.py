import os
import pyotp
import requests
import re

from PySide6.QtCore import Signal, QObject
from lxml import etree

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from src.logging_config import logger


class Worker(QObject):
    finished = Signal(object)  # 任务完成信号，携带返回值或异常对象
    started = Signal()  # 任务开始信号

    def __init__(self, run, run_on_finish=None, run_on_start=None):
        super().__init__()
        self.run = run
        self.run_on_finish = run_on_finish
        self.run_on_start = run_on_start

    def run_task(self):
        self.started.emit()
        if self.run_on_start is not None:
            self.run_on_start()
        try:
            ret = self.run()
        except Exception as e:
            logger.exception(f"Worker task 异常: {e}")
            ret = e

        try:
            if self.run_on_finish is not None:
                self.run_on_finish()
        except Exception:
            logger.exception("Worker run_on_finish 异常")

        self.finished.emit(ret)


from PySide6.QtCore import QThread


def start_worker_in_thread(callable_func, name_prefix="task", on_finished=None):
    """创建并启动后台线程执行 callable_func，自动管理线程/Worker 生命周期。

    Args:
        callable_func: 在线程中执行的函数
        name_prefix: 线程命名前缀（用于调试）
        on_finished: 可选回调，接收 callable_func 的返回值，在 cleanup 前执行

    Returns:
        (thread, worker): 可供调用方按需连接更多信号
    """
    thread = QThread()
    thread.setObjectName(name_prefix + "_thread")
    worker = Worker(callable_func)
    worker.moveToThread(thread)
    thread.started.connect(worker.run_task)

    if on_finished:
        worker.finished.connect(on_finished)

    worker.finished.connect(lambda x: logger.info(f"{name_prefix}: {x}"))
    worker.finished.connect(worker.deleteLater)
    worker.finished.connect(thread.quit)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread, worker


class encrypt:
    """纯 Python RSA PKCS#1 v1.5 加密（替代原来的 JS MiniRacer 方案）"""

    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    }

    def gettotpkey(self, key) -> str:
        """
        获取totp的6位动态口令
        Args:
            key: 生成totp的秘钥
        Returns:
            6位动态口令，失败返回000000
        """
        try:
            totp = pyotp.TOTP(key)
            return totp.now()
        except Exception:
            logger.exception("gettotpkey 失败")
            return "000000"

    # ------------------------------------------------------------------
    # 纯 Python RSA PKCS#1 v1.5 Type 2 加密
    # 模拟原来 JS 中 getkey 函数的行为：
    #   1. pkcs1pad2: \x00\x02 + 随机非零字节 + \x00 + 数据
    #   2. modPowInt(e, n): 模幂运算 c = m^e mod n
    #   3. FixEncryptLength: hex 结果左补 0 到密钥字节长度
    # ------------------------------------------------------------------

    @staticmethod
    def _pkcs1_pad(data: bytes, key_bytes: int) -> bytes:
        """PKCS#1 v1.5 Type 2 填充"""
        pad_len = key_bytes - len(data) - 3
        random_bytes = os.urandom(pad_len)
        # 确保所有填充字节非零
        random_bytes = bytes(b if b != 0 else 1 for b in random_bytes)
        return b"\x00\x02" + random_bytes + b"\x00" + data

    @staticmethod
    def _fix_hex_length(hex_str: str, key_bytes: int) -> str:
        """将 hex 结果左补零到 2 * key_bytes 长度（FixEncryptLength）"""
        expected = key_bytes * 2
        if len(hex_str) < expected:
            hex_str = hex_str.zfill(expected)
        return hex_str

    def getpwds(self, pwd: str, rand: str, r: str) -> str:
        """
        纯 Python RSA 加密密码，获取登录需要的 svpn_pwd

        Args:
            pwd: 密码明文
            rand: 请求 config 页面返回的随机数
            r: RSA 公钥模数（十六进制字符串）
        Returns:
            加密后的十六进制密文字符串
        """
        id_str = f"{pwd}_{rand}"
        data = id_str.encode("utf-8")

        # 解析 RSA 公钥
        n = int(r, 16)          # 模数
        e = 0x10001              # 固定公钥指数
        key_bytes = (n.bit_length() + 7) // 8

        # PKCS#1 v1.5 Type 2 填充
        padded = self._pkcs1_pad(data, key_bytes)
        m = int.from_bytes(padded, "big")

        # 模幂运算 c = m^e mod n
        c = pow(m, e, n)

        # 转 hex 并修正长度
        result_hex = hex(c)[2:]
        return self._fix_hex_length(result_hex, key_bytes)


class webvpn(QObject):
    twfid_update: Signal = Signal(str)

    # 类级别共享配置——所有实例及引用方共享同一份，设置界面保存后自动生效
    _name = ""
    _password = ""
    _key = ""
    _twfid = ""

    def __init__(self, name: str, password: str, key: str, twfid=""):
        """
        Args:
            name: 用户名
            password: 密码
            key: 动态口令秘钥
            twfid: 如果有twfid则不需要登录，直接使用twfid进行登录
        """
        super().__init__()
        self.session = requests.Session()
        self.session.trust_env = True
        self.session.verify = False
        self.session.cookies.update({"TWFID": twfid})

        # 写入类变量，同类所有实例共享同一份配置
        webvpn._name = name
        webvpn._password = password
        webvpn._key = key
        webvpn._twfid = twfid

        self.encrypt = encrypt()
        self.header = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "content-type": "application/x-www-form-urlencoded",
            "sec-ch-ua": '"Not)A;Brand";v="99", "Microsoft Edge";v="127", "Chromium";v="127"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
            "sec-fetch-site": "same-origin",
        }

    # --- 类变量属性访问器，兼容 self.name / self.key / self.twfid 等写法 ---
    @property
    def name(self) -> str:
        return webvpn._name

    @name.setter
    def name(self, value: str):
        webvpn._name = value

    @property
    def password(self) -> str:
        return webvpn._password

    @password.setter
    def password(self, value: str):
        webvpn._password = value

    @property
    def key(self) -> str:
        return webvpn._key

    @key.setter
    def key(self, value: str):
        webvpn._key = value

    @property
    def twfid(self) -> str:
        return webvpn._twfid

    @twfid.setter
    def twfid(self, value: str):
        webvpn._twfid = value

    @classmethod
    def update_config(cls, name: str, password: str, key: str):
        """供设置界面保存后调用，同步更新运行中的共享配置"""
        cls._name = name
        cls._password = password
        cls._key = key

    def autoLogin(self):
        """
        如果twfid能用则直接使用twfid登录，否则使用用户名和密码登录
        """
        if not self.getState():
            self.login()
            return self.getState()
        return True

    def login(self):
        # 需要使用会话来保持登录状态
        # 第一步：获取 CSRF_RAND_CODE 和 TwfID
        url_auth = "https://webvpn.stu.edu.cn/por/login_auth.csp?apiversion=1"
        response_auth = self.session.get(url_auth, headers=self.header)
        if response_auth.status_code != 200:
            return "访问webvpn失败,请检查是否连接WiFi"
        xml_data = response_auth.content
        root = etree.fromstring(xml_data)
        csrf_rand_code = root.find(".//CSRF_RAND_CODE").text
        twfid = root.find(".//TwfID").text
        r = root.find(".//RSA_ENCRYPT_KEY").text

        # 第二步：登录
        url_login = "https://webvpn.stu.edu.cn/por/login_psw.csp?anti_replay=1&encrypt=1&apiversion=1"
        pwd2 = self.encrypt.getpwds(self.password, csrf_rand_code, r)

        data_login = {
            "mitm_result": "",
            "svpn_req_randcode": csrf_rand_code,
            "svpn_name": self.name,
            "svpn_password": pwd2,
            "svpn_rand_code": "",
        }

        response_login = self.session.post(
            url_login, data=data_login, headers=self.header
        )
        if response_login.status_code != 200:
            return "可能多次输入错密码出现了验证码，请自己手动登录一次webvpn"
        elif response_login.text.find("锁定") != -1:
            return "认证错误次数过多，被系统锁定"
        # 第三步：输入动态口令,需要绑定了数盾otp
        passkey = self.encrypt.gettotpkey(self.key)
        url_token = "https://webvpn.stu.edu.cn/auth/token?apiversion=1"
        data_token = {"twfid": twfid, "svpn_inputtoken": passkey}
        response_token = self.session.post(
            url_token, data=data_token, headers=self.header
        )
        if response_token.status_code != 200:
            return "动态口令错误，请检查key是否正确"
        cookies = self.session.cookies
        cookies_v = ""
        for co in cookies:
            if co.name == "TWFID":
                cookies_v = co.value
        if cookies_v == "":
            return "未成功获取到TWFID，请检查key是否输入正确"
        self.twfid = cookies_v
        self.twfid_update.emit(self.twfid)
        logger.info(f"登录成功，TWFID: {self.twfid}")
        return cookies_v

    def _clear_twfid(self):
        self.session.cookies.clear_session_cookies()
        self.twfid = ""
        self.twfid_update.emit(self.twfid)

    def getState(self):
        r = self.session.get(
            "https://webvpn.stu.edu.cn/por/conf.csp?apiversion=1", headers=self.header
        )
        if r.status_code == 200:
            ret = (
                "unexpected user service" not in r.content.decode()
            )  # 检测是否是在登录页面
            if not ret:
                self._clear_twfid()
            return ret
        else:
            self._clear_twfid()
            return False

    def create_url(self, url: str) -> str:
        """
        创建webvpn访问链接
        """
        if not self.getState():
            self.login()
        return f"https://webvpn.stu.edu.cn/portal/shortcut.html?twfid={self.twfid}&url={get_vpn_url(url)}"

    def create_redirect_url(self, url: str) -> str:
        """
        用webvpn重定向访问链接
        """
        if not self.getState():
            self.login()
        return f"https://webvpn.stu.edu.cn/portal/shortcut.html?twfid={self.twfid}&url={url}"


def GtoM(b):
    b = b.replace("M", "")
    if b.find("G") != -1:
        b = b.replace("G", "")
        b = str(float(b) * 1024)
    return b


def get_data(put) -> tuple[float, float]:
    """
    根据流量请求包，分割流量数据
    :param put:
    :return:
    """
    data = re.findall("<tr> <td>([^<]*)</td> <td>([^<]*)", put)
    limit = 0.0
    now = 0.0
    name = "<UNK>"
    for a, b in data:
        if a.find("用户名") != -1:
            name = b
        elif a.find("流量额") != -1:
            limit = float(GtoM(b))
        elif a.find("当天") != -1:
            now = float(GtoM(b))
    return limit, now, name


def get_vpn_url(site) -> str:
    """
    格式：xxx://xxxx(:xxx)(/xxx)
    """
    if "webvpn.stu.edu.cn:8118" in site:
        return site
    ret = re.match("([a-zA-z]+://)([^/]*)(/.*)", site, re.I)
    if ret is None:
        ret = re.match("([a-zA-z]+://)([^/]*)(/.*)", site + "/", re.I)
        if ret is None:
            return ""

    web = ret.group(2).replace("-", "--").replace(".", "-")
    if ":" in web:
        web = web.replace(":", "-") + "-p"
    web = ret.group(1) + web
    if "https" not in web:
        return web + ".webvpn.stu.edu.cn:8118" + ret.group(3)
    return web.replace("https", "http") + "-s.webvpn.stu.edu.cn:8118" + ret.group(3)


def extract_text(text, start_marker, end_marker):
    pattern = re.compile(
        rf"{re.escape(start_marker)}(.*?){re.escape(end_marker)}", re.DOTALL
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


class wifi(QObject):

    class state:
        """
        wifi的状态类
        """

        def __init__(
            self,
            state: str = "未登录",
            total: float = 0,
            used: float = 0,
            name: str = "未登录",
        ):
            """
            Args:
                state: wifi的状态
                total: 总流量/G
                used: 已使用流量/G
            """
            self.state = state
            self.total = total
            self.used = used
            self.name = name

        def __str__(self):
            return {
                "state": self.state,
                "total": self.total,
                "used": self.used,
                "name": self.name,
            }.__str__()

        __repr__ = __str__

    # 类级别共享配置——所有实例及引用方共享同一份
    _name = ""
    _password = ""

    state_update: Signal = Signal(state)
    flux_update: Signal = Signal(float, float)

    def __init__(self, name: str, password: str):
        """
        Args:
            name: 用户名
            password: 密码
        """
        super().__init__()
        # 写入类变量
        wifi._name = name
        wifi._password = password

        self.session = requests.Session()
        self.session.trust_env = True
        self.session.verify = False
        # self.state = "未登录"

        self.url = "https://a.stu.edu.cn/ac_portal/login.php"
        self.header = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
        }

    # --- 类变量属性访问器，兼容 self.name / self.password 写法 ---
    @property
    def name(self) -> str:
        return wifi._name

    @name.setter
    def name(self, value: str):
        wifi._name = value

    @property
    def password(self) -> str:
        return wifi._password

    @password.setter
    def password(self, value: str):
        wifi._password = value

    @classmethod
    def update_config(cls, name: str, password: str):
        """供设置界面保存后调用，同步更新运行中的共享配置"""
        cls._name = name
        cls._password = password

    def logout(self):
        """
        注销登录
        """
        try:
            r = self.session.post(
                self.url,
                headers=self.header,
                data="opr=logout&ipv4or6=",
                timeout=(1, 2),
            )
        except requests.exceptions.Timeout:
            return "注销请求超时，可能处于临时用户阶段或不在校园网环境"
        if r.status_code == 200:
            return r.content.decode()
        else:
            return "注销失败，请检查网络连接"

    def change_account(self, name, password):
        self.name = name
        self.password = password
        return self.login()

    def login(self) -> bool:
        if self.name == "" or self.password == "":
            logger.warning("账号或密码为空")
            return False
        try:
            logger.info(f"校园网注销:{self.logout()}")
            r = self.session.post(
                self.url,
                headers=self.header,
                data=f"opr=pwdLogin&userName={self.name}&pwd={self.password}&ipv4or6=&rememberPwd=1",
                timeout=(3, 7),
            )
        except requests.exceptions.RequestException as e:
            logger.exception(f"校园网登录请求异常: {e}")
            return False

        try:
            self.getState()
        except Exception:
            pass

        if r.status_code == 200:
            try:
                msg = r.content.decode()
            except Exception:
                return False
            if "logon success" in msg or "已在线" in msg:
                # self.state ="登陆成功"
                return True
            elif "NOAUTH" in msg:
                # self.state = "无限流时间"
                return True
            elif "冻结" in msg:
                # self.state = "登陆失败，登录频繁，账户被冻结一分钟"
                return False
            # else:
            # self.state = "登陆失败，可能是密码错误"
        # else:
        # self.state = "登陆失败，请检查网络连接"
        return False

    def getState(self) -> state:
        """
        获取当前登录状态
        """
        state = self.state()

        try:
            r = self.session.post(
                "https://a.stu.edu.cn/ac_portal/userflux",
                headers=self.header,
                timeout=(3, 7),
            )
        except requests.exceptions.RequestException as e:
            logger.exception(f"获取校园网状态失败: {e}")
            state.state = "未登录"
            state.total = 0
            state.used = 0
            self.state_update.emit(state)
            self.flux_update.emit(state.total, state.used)
            return state

        if r.status_code == 200:
            try:
                ret = r.content.decode()
            except UnicodeDecodeError:
                state.state = "未登录"
                state.total = 0
                state.used = 0
                self.state_update.emit(state)
                self.flux_update.emit(state.total, state.used)
                return state
            if "临时" in ret:
                state.state = "无限流"
                state.total = 999
                state.used = 0
                state.name = "<UNK>"
            elif "请求剩余流量时出错" in ret:
                state.state = "已登录"
                state.total = 0
                state.used = 0
                state.name = self.name
            else:
                state.total, state.used, self.name = get_data(ret)
                state.state = "已登录"
                state.name = self.name
        else:
            state.state = "未登录"
            state.total = 0
            state.used = 0

        self.state_update.emit(state)
        self.flux_update.emit(state.total, state.used)
        return state



