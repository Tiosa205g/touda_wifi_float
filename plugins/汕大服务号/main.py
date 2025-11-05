
import base64
import pluggy
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget,QVBoxLayout

PLUGIN_NAME = '汕大服务号插件'
PLUGIN_VERSION = '1.0.0'
PLUGIN_AUTHOR = 'tiosa'
PLUGIN_PATH = Path(__file__).parent

# 使用与主程序一致的标识
hook = pluggy.HookimplMarker("toudawifi") # 不能变动

class SDK:
    def __init__(self,api):
        self.api = api
    def logger_info(self,msg:str):
        self.api.logger.info(f'[{PLUGIN_NAME}] {msg}')
    def logger_error(self,msg:str):
        self.api.logger.error(f'[{PLUGIN_NAME}] {msg}')
    def get_sub(self)->dict: #{'username':xxx,'pwd':xxx}
        return {'username':self.api.wifi.username,'pwd':self.api.wifi.password}
    def get_current_account(self)->dict:
        """{'name':xxx,'pwd':xxx} 不一定已经登录，比如到了临时用户时间"""
        main = self.api.cfg(self.api.MAIN_CFG)
        current = self.api.cfg(f"{self.api.CFG_DIR}\\account_{main.get('main','current_account',0)}.toml")
        name = current.get('setting','name','')
        password = base64.b64decode(current.get('setting','password','').encode('utf-8')).decode('utf-8')
        return {'name':name,'pwd':password}
    class Menu: # 插件名 功能名 函数
        def __init__(self):
            self.menu = []
        def add_func(self,func_name:str,func):
            """功能名，可调用的函数对象"""
            self.menu.append({'function':func_name,
                              'object':func})
            
        def add_funcs(self,funcs:list[dict]):
            """list内应为{'function':功能名,'object':可调用函数对象}"""
            self.menu.extend(funcs)

        def del_func(self,func_name:str)->bool:
            """删除指定功能名的功能"""
            num = len(self.menu)
            self.menu = [x for x in self.menu if x['function'] != func_name]
            return len(self.menu) != num
        
        def get_all(self)->list[dict]:
            return self.menu
class Plugin:  # 类名固定为 Plugin，不能变动，否则无法识别
    @hook
    def start(self,api) -> bool:
        """插件加载时执行，传api包含已实例化的wifi和webvpn类"""
        self.api = api
        self.sdk = SDK(self.api)
        self.session = requests.session()
        self.session.trust_env = True
        self.session.verify = False
        self.session.headers.update({'User-Agent':'Mozilla/5.0 (Linux; Android 14; ALP-AN00 Build/HONORALP-AN00T; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/138.0.7204.180 Mobile Safari/537.36 XWEB/1380267 MMWEBSDK/20250804 MMWEBID/6729 MicroMessenger/8.0.63.2920(0x28003F3C) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64',
                                     'Content-Type':'application/x-www-form-urlencoded'})
        return True # 返回true才会视为有效插件
    @hook
    def on_disable(self):
        self.sdk.logger_info(f'{PLUGIN_NAME}禁用')
    @hook
    def get_name(self)->str:
        """获取插件名字"""
        return PLUGIN_NAME
    @hook
    def get_description(self)->str:
        """获取插件描述,支持markdown"""
        try:
            with open(PLUGIN_PATH/'readme.md',encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.sdk.logger_error(f'出错啦:{e}')
    @hook
    def get_menu(self)->list[dict]: # list[功能 - function]
        """获取插件的菜单信息,需要返回list[{'function':'功能名','object':callable函数}]"""
        menu = self.sdk.Menu()
        acc = self.sdk.get_current_account()
        name = acc['name']
        pwd = acc['pwd']
        openid = self.get_encode_openid(name)
        if (self.is_login(name)):
            url_card = f'http://wechat.stu.edu.cn/wechat/smartcard/index?openid={openid}'
            url_net = f'http://wechat.stu.edu.cn/wechat/stu_netms_service/stu_netms.aspx?openid={openid}'
            menu.add_funcs([
                {'function':'进入一卡通页面',
                 'object': (lambda *_, url=url_card: self.open_browser(url,'一卡通'))},
                {'function':'进入网络服务页面',
                 'object': (lambda *_, url=url_net: self.open_browser(url,'网络服务'))},
                {'function':'解绑',
                 'object': (lambda *_, name=name: self.unbind_wechat(name))}
            ])

        else:
            menu.add_func('绑定账号', lambda *_, name=name, pwd=pwd: self.auth_wechat(name,pwd))
        return menu.get_all()
    
    def get_encode_openid(self,name:str)->str:
        """获取base64编码后的用户名，并去除等号，用于伪造一个openid并确保安全问题"""
        if not name:
            self.sdk.logger_error('非法用户名')
            return ''
        return base64.urlsafe_b64encode(name.encode()).decode('utf-8').rstrip('=')
    def is_login(self,name:str)->bool:
        """判断是否登录"""
        open_id = self.get_encode_openid(name)
        r = self.session.get(url=f'http://wechat.stu.edu.cn/wechat/login/login?source_type=dorm_information&openid={open_id}')
        if r.status_code == 200:
            return r.text.find('登录') == -1 # 寻找是否有 登录 字样，如果未绑定就会有登录提示
        return False               
    def auth_wechat(self,name:str,pwd:str)->bool:
        """使用伪造openid进行登录并绑定"""
        open_id = self.get_encode_openid(name)
        r = self.session.post(url='http://wechat.stu.edu.cn/wechat/login/login_verify',data=f'ldap_account={name}&ldap_password={pwd}&btn_ok=登录&source_type=dorm_information&openid={open_id}')
        if r.status_code == 200:
            return r.text.find('成功') != -1
        return False 
    def unbind_wechat(self,name:str)->bool:
        """将伪造openid取消绑定"""
        open_id = self.get_encode_openid(name)
        r = self.session.get(url=f'http://wechat.stu.edu.cn/wechat/ldap_openid_ok.aspx?openid={open_id}')
        if r.status_code != 200:
            return False
        
        soup = BeautifulSoup(r.text,'lxml')

        __VIEWSTATE = soup.find('input',attrs={'type':'hidden','name':'__VIEWSTATE'}).get('value')
        __EVENTVALIDATION = soup.find('input',attrs={'type':'hidden','name':'__EVENTVALIDATION'}).get('value')

        r = self.session.post(url=f'http://wechat.stu.edu.cn/wechat/ldap_openid_ok.aspx?openid={open_id}',data=f'__VIEWSTATE={__VIEWSTATE}&__EVENTVALIDATION={__EVENTVALIDATION}&Btn_cancel_bind=')
        if r.status_code == 200:
            return r.text.find('取消绑定成功') != -1
        return False
    def open_browser(self,url:str,title:str):
        self.browser = SimpleBrowser(url,title)
        self.browser.show()
class SimpleBrowser(QWidget):
    def __init__(self,url:str,title:str):
        super().__init__()
        self.title = title
        self.url = url
        self.init_ui()
        
    def init_ui(self):
        # 设置窗口基本属性
        self.setWindowTitle(self.title)
        self.setGeometry(100, 100, 500,500)  # x, y, 宽, 高
        
        # 创建布局管理器
        layout = QVBoxLayout()
        self.setLayout(layout)  # 直接给当前QWidget设置布局
        
        # 创建浏览器组件
        self.web_view = QWebEngineView()
        
        # 添加浏览器到布局
        layout.addWidget(self.web_view)
        
        # 加载网页
        self.web_view.load(QUrl(self.url))
        
        # 显示加载进度
        self.web_view.loadProgress.connect(self.update_progress)
        
    def update_progress(self, progress):
        if progress < 100:
            self.setWindowTitle(f"{self.title} - 加载中: {progress}%")
        else:
            self.setWindowTitle(f"{self.title} - 加载完成")

    