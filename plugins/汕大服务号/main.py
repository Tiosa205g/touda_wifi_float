
import base64
import pluggy
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout

from plugin_sdk import PluginSDK, PluginMenu

PLUGIN_NAME = '汕大服务号插件'
PLUGIN_VERSION = '1.0.0'
PLUGIN_AUTHOR = 'tiosa'
PLUGIN_PATH = Path(__file__).parent

# 使用与主程序一致的标识
hook = pluggy.HookimplMarker("toudawifi") # 不能变动

class SDK(PluginSDK):
    """继承公共 PluginSDK，增加插件特有方法"""

    def get_sub(self) -> dict:
        return {'username': self.api.wifi.name, 'pwd': self.api.wifi.password}

    def get_current_account(self) -> dict:
        """返回当前配置的账号（{'name':xxx,'pwd':xxx}），不一定已登录"""
        main = self.api.cfg(self.api.MAIN_CFG)
        current = self.api.cfg(
            f"{self.api.CFG_DIR}\\account_{main.get('main','current_account',0)}.toml"
        )
        name = current.get('setting', 'name', '')
        password = base64.b64decode(
            current.get('setting', 'password', '').encode('utf-8')
        ).decode('utf-8')
        return {'name': name, 'pwd': password}
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
    def get_menu(self)->list[dict]:
        """获取插件的菜单信息"""
        menu = PluginMenu()
        acc = self.sdk.get_current_account()
        name = acc['name']
        pwd = acc['pwd']
        openid = self.get_encode_openid(name)
        if (self.is_login(name)):
            url_card = f'http://wechat.stu.edu.cn/wechat/smartcard/index?openid={openid}'
            url_net = f'http://wechat.stu.edu.cn/wechat/stu_netms_service/stu_netms.aspx?openid={openid}'
            menu.add_funcs([
                {'function':'进入一卡通页面',
                 'object': (lambda *_, url=url_card: QDesktopServices.openUrl(QUrl(url)))},
                {'function':'进入网络服务页面',
                 'object': (lambda *_, url=url_net: QDesktopServices.openUrl(QUrl(url)))},
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
        r = self.session.get(url=f'http://wechat.stu.edu.cn/wechat/login/login?source_type=dorm_information&openid={open_id}',timeout=3)
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
