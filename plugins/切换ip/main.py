# 切换静态IP插件 - 支持同网段IP扫描、手动设置、阿里云DDNS（内网IP）
import pluggy
import subprocess
import re
import ipaddress
import socket
import concurrent.futures
import ctypes
import sys
import tomlkit
import json
import time
import urllib.parse
import hmac
import hashlib
import base64
from pathlib import Path
from datetime import datetime

from src.logging_config import logger

from plugin_sdk import PluginSDK, PluginMenu

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QWidget, QFrame, QSizePolicy,
    QScrollArea,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer, QPoint
from PySide6.QtGui import QFont, QColor, QMouseEvent

from qfluentwidgets import (
    PushButton, PrimaryPushButton, ComboBox, LineEdit,
    PasswordLineEdit, StrongBodyLabel, BodyLabel, FluentIcon as FIF,
    InfoBar, CardWidget, InfoBarPosition, SpinBox, SwitchButton,
    CaptionLabel, ToolButton, ProgressBar, isDarkTheme,
)

PLUGIN_NAME = '切换静态IP'
PLUGIN_VERSION = '1.1.0'
PLUGIN_AUTHOR = 'tiosa'
PLUGIN_PATH = Path(__file__).parent
PLUGIN_CFG = PLUGIN_PATH / 'config.toml'

ALIYUN_DNS_ENDPOINT = 'https://dns.aliyuncs.com/'

hook = pluggy.HookimplMarker("toudawifi")


# =========================================================================
# 网络工具函数
# =========================================================================
def _run_cmd(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=False,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        raw = (r.stdout or b'') + (r.stderr or b'')
        for enc in ('utf-8', 'gbk', 'cp936'):
            try:
                return raw.decode(enc).strip()
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode('utf-8', errors='replace').strip()
    except FileNotFoundError:
        return ''


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def mask_to_cidr(mask: str) -> int:
    return sum(bin(int(x)).count('1') for x in mask.split('.'))


def get_adapters() -> list[dict]:
    out = _run_cmd(['netsh', 'interface', 'ip', 'show', 'config'])
    if not out or '没有启用' in out or '命令失败' in out:
        return []

    adapters = []
    blocks = re.split(r'\n(?=接口 \")', out)
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        m = re.search(r'接口 \"(.+?)\"', block)
        name = m.group(1) if m else ''

        dhcp_m = re.search(r'DHCP 已启用[:\s]+(\S)', block)
        dhcp = bool(dhcp_m and dhcp_m.group(1) == '是')

        ip_m = re.search(r'IP 地址[:\s]+([\d.]+)', block)
        ip_addr = ip_m.group(1) if ip_m else ''

        mask_m = re.search(r'子网前缀[:\s]+[\d.]+/(\d+)', block)
        if not mask_m:
            mask_m = re.search(r'子网掩码[:\s]+([\d.]+)', block)
        if mask_m and mask_m.lastindex == 1:
            if '/' in block and mask_m.group(0).startswith('子网前缀'):
                cidr = int(mask_m.group(1))
                mask_str = str(ipaddress.IPv4Network(f'0.0.0.0/{cidr}').netmask)
            else:
                mask_str = mask_m.group(1)
        else:
            mask_str = ''

        gw_m = re.search(r'默认网关[:\s]+([\d.]+)', block)
        gateway = gw_m.group(1) if gw_m else ''

        adapters.append({
            'name': name,
            'ip': ip_addr,
            'mask': mask_str,
            'gateway': gateway,
            'dhcp': dhcp,
        })

    return adapters


def _ping_ip(ip: str, timeout: int = 200) -> tuple[str, bool]:
    try:
        r = subprocess.run(
            ['ping', '-n', '1', '-w', str(timeout), ip],
            capture_output=True, text=True, encoding='gbk',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return ip, r.returncode == 0
    except Exception:
        return ip, False


def set_static_ip(adapter_name: str, ip: str, subnet_mask: str, gateway: str = '') -> tuple[bool, str]:
    if not is_admin():
        return False, '需要管理员权限才能修改IP设置，请以管理员身份运行程序。'
    try:
        socket.inet_aton(ip)
        socket.inet_aton(subnet_mask)
        if gateway:
            socket.inet_aton(gateway)
    except OSError:
        return False, 'IP 地址格式不合法'
    if gateway:
        cmd = ['netsh', 'interface', 'ip', 'set', 'address',
               f'name={adapter_name}', 'source=static', ip, subnet_mask, gateway, '1']
    else:
        cmd = ['netsh', 'interface', 'ip', 'set', 'address',
               f'name={adapter_name}', 'source=static', ip, subnet_mask]
    out = _run_cmd(cmd)
    if '确定' in out or 'OK' in out or not out:
        return True, f'静态 IP 已设置为 {ip}'
    if '需要提升' in out or 'elevation' in out.lower():
        return False, '需要管理员权限才能修改IP设置。'
    return False, f'设置失败:\n{out[:200]}'


def _get_static_dns(adapter_name: str) -> list[str]:
    out = _run_cmd(['netsh', 'interface', 'ip', 'show', 'dnsserver', f'name={adapter_name}'])
    lines = out.split('\n')
    servers = []
    in_static = False
    for line in lines:
        if '静态配置的 DNS 服务器' in line:
            in_static = True
            m = re.search(r'[\d.]+', line)
            if m:
                servers.append(m.group())
        elif in_static:
            m = re.search(r'^\s+([\d.]+)', line)
            if m:
                servers.append(m.group(1))
            else:
                break
    return servers


def _set_static_dns(adapter_name: str, servers: list[str]):
    _run_cmd(['netsh', 'interface', 'ip', 'set', 'dnsserver', f'name={adapter_name}', 'source=dhcp'])
    for i, srv in enumerate(servers):
        if i == 0:
            _run_cmd(['netsh', 'interface', 'ip', 'set', 'dnsserver',
                      f'name={adapter_name}', 'source=static', f'addr={srv}', 'register=primary'])
        else:
            _run_cmd(['netsh', 'interface', 'ip', 'add', 'dnsserver',
                      f'name={adapter_name}', f'addr={srv}', f'index={i+1}'])


def set_dhcp(adapter_name: str) -> tuple[bool, str]:
    if not is_admin():
        return False, '需要管理员权限才能修改IP设置，请以管理员身份运行程序。'
    saved_dns = _get_static_dns(adapter_name)
    out = _run_cmd(['netsh', 'interface', 'ip', 'set', 'address', f'name={adapter_name}', 'source=dhcp'])
    if '确定' in out or 'OK' in out or not out:
        if saved_dns:
            _set_static_dns(adapter_name, saved_dns)
        return True, f'{adapter_name} 已切换为 DHCP 自动获取 IP（DNS 已保留）'
    if '需要提升' in out or 'elevation' in out.lower():
        return False, '需要管理员权限才能修改IP设置。'
    return False, f'设置失败:\n{out[:200]}'


def calc_network(ip_str: str, mask_str: str) -> ipaddress.IPv4Network | None:
    try:
        cidr = mask_to_cidr(mask_str)
        return ipaddress.IPv4Network(f'{ip_str}/{cidr}', strict=False)
    except Exception:
        return None


def get_current_ip(adapter_name: str = '') -> str | None:
    """获取指定适配器的当前内网 IP，未指定时取第一个有 IP 的适配器"""
    adapters = get_adapters()
    if adapter_name:
        for a in adapters:
            if a['name'] == adapter_name and a['ip']:
                return a['ip']
    for a in adapters:
        if a['ip']:
            return a['ip']
    return None


# =========================================================================
# 阿里云 DDNS
# =========================================================================
def _aliyun_sign(access_key_secret: str, params: dict) -> str:
    sorted_params = sorted(params.items())
    canonicalized = '&'.join(
        f'{urllib.parse.quote(k, safe="")}={urllib.parse.quote(str(v), safe="")}'
        for k, v in sorted_params
    )
    string_to_sign = f'GET&{urllib.parse.quote("/", safe="")}&{urllib.parse.quote(canonicalized, safe="")}'
    key = (access_key_secret + '&').encode('utf-8')
    h = hmac.new(key, string_to_sign.encode('utf-8'), hashlib.sha1)
    return base64.b64encode(h.digest()).decode('utf-8')


def _aliyun_request(access_key_id: str, access_key_secret: str, action: str, params: dict) -> dict:
    public_params = {
        'Format': 'JSON',
        'Version': '2015-01-09',
        'AccessKeyId': access_key_id,
        'SignatureMethod': 'HMAC-SHA1',
        'Timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'SignatureVersion': '1.0',
        'SignatureNonce': str(int(time.time() * 1000)),
        'Action': action,
    }
    public_params.update(params)
    public_params['Signature'] = _aliyun_sign(access_key_secret, public_params)

    import requests
    try:
        r = requests.get(ALIYUN_DNS_ENDPOINT, params=public_params, timeout=10)
        return r.json()
    except Exception as e:
        return {'Error': {'Code': 'RequestError', 'Message': str(e)}}


def _is_aliyun_error(result: dict) -> bool:
    """检查阿里云 API 响应是否包含错误（API 在 HTTP 200 中返回 error JSON）"""
    if 'Code' in result and 'Message' in result and result['Code'] != '200':
        return True
    if 'Error' in result and 'Code' in result.get('Error', {}):
        return True
    return False


def ddns_get_records(ak_id: str, ak_secret: str, domain: str, rr: str = '', type_: str = 'A') -> list[dict]:
    params = {'DomainName': domain, 'Type': type_, 'PageSize': 500}
    if rr:
        params['RRKeyWord'] = rr
    result = _aliyun_request(ak_id, ak_secret, 'DescribeDomainRecords', params)
    if _is_aliyun_error(result):
        err_msg = (result.get('Error', {}) or {}).get('Message', result.get('Message', '未知错误'))
        raise ValueError(f'阿里云 API 错误: {err_msg}')
    if 'DomainRecords' in result and 'Record' in result['DomainRecords']:
        return result['DomainRecords']['Record']
    return []


def ddns_update_record(ak_id: str, ak_secret: str,
                       record_id: str, rr: str, type_: str, value: str, ttl: int = 600) -> tuple[bool, str]:
    params = {'RecordId': record_id, 'RR': rr, 'Type': type_, 'Value': value, 'TTL': ttl}
    result = _aliyun_request(ak_id, ak_secret, 'UpdateDomainRecord', params)
    if 'RecordId' in result:
        return True, f'DNS 记录已更新: {rr} → {value}'
    err_msg = result.get('Error', {}).get('Message', '未知错误')
    return False, f'更新失败: {err_msg}'


def ddns_add_record(ak_id: str, ak_secret: str,
                    domain: str, rr: str, type_: str, value: str, ttl: int = 600) -> tuple[bool, str]:
    params = {'DomainName': domain, 'RR': rr, 'Type': type_, 'Value': value, 'TTL': ttl}
    result = _aliyun_request(ak_id, ak_secret, 'AddDomainRecord', params)
    if 'RecordId' in result:
        return True, f'DNS 记录已添加: {rr}.{domain} → {value}'
    err_msg = result.get('Error', {}).get('Message', '未知错误')
    return False, f'添加失败: {err_msg}'


# =========================================================================
# 插件配置（带进程内缓存）
# =========================================================================
_cfg_cache: dict | None = None


def _load_cfg() -> dict:
    global _cfg_cache
    if _cfg_cache is not None:
        return _cfg_cache
    return _reload_cfg()


def _reload_cfg() -> dict:
    global _cfg_cache
    try:
        with open(PLUGIN_CFG, 'r', encoding='utf-8') as f:
            _cfg_cache = tomlkit.load(f)
            return _cfg_cache
    except Exception:
        _cfg_cache = {}
        return _cfg_cache


def _save_cfg(data: dict):
    global _cfg_cache
    _cfg_cache = data
    PLUGIN_CFG.parent.mkdir(parents=True, exist_ok=True)
    with open(PLUGIN_CFG, 'w', encoding='utf-8') as f:
        tomlkit.dump(data, f)


def _get_preferred_adapter_name() -> str:
    return _load_cfg().get('preferred_adapter', '')


def _set_preferred_adapter_name(name: str):
    cfg = _load_cfg()
    cfg['preferred_adapter'] = name
    _save_cfg(cfg)


def _get_ddns_config() -> dict:
    cfg = _load_cfg()
    return cfg.get('ddns', {})


def _set_ddns_config(ddns: dict):
    cfg = _load_cfg()
    cfg['ddns'] = ddns
    _save_cfg(cfg)


# =========================================================================
# 主题工具
# =========================================================================
def _is_dark() -> bool:
    try:
        return isDarkTheme()
    except Exception:
        return False


def _get_theme_colors():
    """返回 (bg, text, sec, border)"""
    dark = _is_dark()
    if dark:
        return '#1e1e1e', '#e0e0e0', '#888888', '#3b3b3b'
    return '#f5f9ff', '#1f1f1f', '#666666', '#cce4f7'


def _bg_card() -> str:
    return '#2a2a2a' if _is_dark() else '#ffffff'


def _border_color() -> str:
    return '#3b3b3b' if _is_dark() else '#cce4f7'


def _text_primary() -> str:
    return '#e0e0e0' if _is_dark() else '#1f1f1f'


def _text_secondary() -> str:
    return '#888888' if _is_dark() else '#666666'


def _accent_color() -> str:
    return '#2B88D8' if _is_dark() else '#0078D4'


def _table_style() -> str:
    if _is_dark():
        return f"""
            QTableWidget {{
                background: #252525; color: {_text_primary()};
                border: 1px solid {_border_color()}; border-radius: 6px;
                gridline-color: #333;
            }}
            QTableWidget::item:selected {{ background: {_accent_color()}; color: white; }}
            QTableWidget::item:hover {{
                background: #3a3a3a; color: {_text_primary()};
            }}
            QTableWidget::indicator {{ width: 0; height: 0; }}
            QHeaderView::section {{
                background: #1e1e1e; color: #90CAF9; border: none;
                padding: 6px; font-weight: bold;
            }}
        """
    else:
        return f"""
            QTableWidget {{
                background: #ffffff; color: {_text_primary()};
                border: 1px solid {_border_color()}; border-radius: 6px;
                gridline-color: #e8f0fe;
            }}
            QTableWidget::item:selected {{ background: {_accent_color()}; color: white; }}
            QTableWidget::item:hover {{
                background: #e3f0ff; color: {_text_primary()};
            }}
            QTableWidget::indicator {{ width: 0; height: 0; }}
            QHeaderView::section {{
                background: #f0f6ff; color: #0078D4; border: none;
                padding: 6px; font-weight: bold;
            }}
        """


def _card_style() -> str:
    return f'background: {_bg_card()}; border: 1px solid {_border_color()}; border-radius: 8px;'


# =========================================================================
# 无边框对话框基类
# =========================================================================
class _FramelessDialog(QDialog):
    """插件内无边框对话框基类 — 圆角背景、标题栏、拖拽"""

    def __init__(self, parent=None, title=''):
        super().__init__(parent)
        self._is_dragging = False
        self._drag_start = QPoint()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # ── 根布局 ──
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 外层容器（圆角 + 背景） ──
        self._outer = QWidget(self)
        self._outer.setObjectName("plgFdOuter")
        self._outerLayout = QVBoxLayout(self._outer)
        self._outerLayout.setContentsMargins(0, 0, 0, 0)
        self._outerLayout.setSpacing(0)
        root.addWidget(self._outer)

        # ── 标题栏 ──
        self._build_title_bar(title)

        # ── 内容区 ──
        self._content_area = QWidget(self._outer)
        self._content_area.setObjectName("plgFdContent")
        self._content_area.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content_area)
        self._content_layout.setContentsMargins(20, 8, 20, 20)
        self._content_layout.setSpacing(12)
        self._outerLayout.addWidget(self._content_area, 1)

        # ── 主题 ──
        self._refresh_theme()

    def _build_title_bar(self, title):
        bg, text, sec, border = _get_theme_colors()
        dark = _is_dark()

        bar = QWidget(self._outer)
        bar.setObjectName("plgFdBar")
        bar.setFixedHeight(44)
        bar.setStyleSheet("background: transparent;")

        tb = QHBoxLayout(bar)
        tb.setContentsMargins(16, 0, 8, 0)
        tb.setSpacing(0)

        self._title_label = QLabel(title, bar)
        self._title_label.setStyleSheet(
            f"color: {text}; font-size: 14px; font-weight: bold; background: transparent;"
        )
        tb.addWidget(self._title_label)
        tb.addStretch()

        close_btn = QLabel("✕", bar)
        close_btn.setFixedSize(28, 28)
        close_btn.setAlignment(Qt.AlignCenter)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QLabel {{
                color: {sec}; background: transparent;
                border-radius: 14px; font-size: 14px;
            }}
            QLabel:hover {{
                background: {"#3a3a3a" if dark else "#e0e0e0"};
                color: {text};
            }}
        """)
        close_btn.mousePressEvent = lambda e: self.reject()
        tb.addWidget(close_btn)

        self._outerLayout.addWidget(bar)

    def _refresh_theme(self):
        bg, text, sec, border = _get_theme_colors()
        self._outer.setStyleSheet(f"""
            #plgFdOuter {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)
        try:
            self._title_label.setStyleSheet(
                f"color: {text}; font-size: 14px; font-weight: bold; background: transparent;"
            )
        except Exception:
            pass

    def setCentralWidget(self, widget, stretch=1):
        """设置（或替换）内容区唯一控件"""
        # 清除现有内容
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._content_layout.addWidget(widget, stretch)

    # ── 拖拽支持 ──
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and event.position().y() <= 44:
            self._is_dragging = True
            self._drag_start = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging:
            self.move(event.globalPosition().toPoint() - self._drag_start)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._is_dragging = False
        event.accept()


# =========================================================================
# 适配器信息卡片
# =========================================================================
class _AdapterCard(CardWidget):
    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self.setBorderRadius(8)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = StrongBodyLabel(info['name'])
        title.setStyleSheet(f'font-size: 14px; color: {_text_primary()};')
        header.addWidget(title)
        header.addStretch()

        dhcp_badge = BodyLabel('DHCP' if info['dhcp'] else '静态')
        dhcp_badge.setStyleSheet(f'''
            background-color: {"#d0d0d0" if info['dhcp'] else "#e3dac9"};
            border-radius: 4px; padding: 1px 8px; font-size: 11px;
            color: {"#333" if not info['dhcp'] else "#555"};
        ''')
        header.addWidget(dhcp_badge)
        layout.addLayout(header)

        rows_data = [
            ('IP', info['ip'] or '—'),
            ('子网掩码', info['mask'] or '—'),
            ('网关', info['gateway'] or '—'),
        ]
        for label, value in rows_data:
            row = QHBoxLayout()
            lbl = BodyLabel(f'{label}:')
            lbl.setStyleSheet(f'color: {_text_secondary()}; font-size: 12px; min-width: 50px;')
            val = BodyLabel(value)
            val.setStyleSheet(f'color: {_text_primary()}; font-size: 12px;')
            row.addWidget(lbl)
            row.addWidget(val)
            row.addStretch()
            layout.addLayout(row)


# =========================================================================
# 网络信息对话框
# =========================================================================
class NetworkInfoDialog(_FramelessDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent, title='所有网络适配器')
        self.resize(540, 420)

        adapters = get_adapters()

        # 副标题
        subtitle = BodyLabel(f'共 {len(adapters)} 个适配器')
        subtitle.setStyleSheet(f'color: {_text_secondary()}; margin-bottom: 4px;')
        self._content_layout.addWidget(subtitle)

        # 卡片列表
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet('background: transparent;')
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(8)

        if not adapters:
            empty = BodyLabel('未检测到网络适配器')
            empty.setStyleSheet(f'color: {_text_secondary()}; padding: 20px;')
            empty.setAlignment(Qt.AlignCenter)
            scroll_layout.addWidget(empty)
        else:
            for a in adapters:
                scroll_layout.addWidget(_AdapterCard(a))
        scroll_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet('background: transparent; border: none;')
        try:
            scroll.viewport().setStyleSheet('background: transparent;')
        except Exception:
            pass
        self._content_layout.addWidget(scroll, stretch=1)

        # 按钮
        btn_ok = PrimaryPushButton(FIF.ACCEPT, '确定')
        btn_ok.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        self._content_layout.addLayout(btn_row)


# =========================================================================
# 适配器选择对话框
# =========================================================================
class AdapterSelectDialog(_FramelessDialog):
    def __init__(self, title: str = '选择适配器', parent=None):
        super().__init__(parent=parent, title=title)
        self.resize(420, 200)

        self.combo = ComboBox()
        self._adapters = [a for a in get_adapters() if a['ip']]
        if not self._adapters:
            self._adapters = get_adapters()

        for a in self._adapters:
            text = a['name']
            if a['ip']:
                text += f'  ({a["ip"]})'
            self.combo.addItem(text)

        preferred = _get_preferred_adapter_name()
        if preferred:
            for i, a in enumerate(self._adapters):
                if a['name'] == preferred:
                    self.combo.setCurrentIndex(i)
                    break

        self._content_layout.addWidget(self.combo)

        tip = BodyLabel('将扫描该适配器所在网段的可用 IP')
        tip.setStyleSheet(f'color: {_text_secondary()};')
        self._content_layout.addWidget(tip)

        self._content_layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_cancel = PushButton('取消')
        btn_cancel.clicked.connect(self.reject)
        btn_ok = PrimaryPushButton(FIF.SEARCH, '开始扫描')
        btn_ok.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        self._content_layout.addLayout(btn_layout)

    def selected_adapter(self) -> dict | None:
        idx = self.combo.currentIndex()
        if 0 <= idx < len(self._adapters):
            return self._adapters[idx]
        return None


# =========================================================================
# 扫描 Worker（无 QThread，用 QTimer 轮询 ThreadPoolExecutor 避免跨线程信号）
# =========================================================================
class _ScanPoller(QObject):
    finished = Signal(dict)
    progress = Signal(int, int)

    def __init__(self, ips: list[str], parent=None):
        super().__init__(parent)
        self.ips = ips
        self._cancel = False
        self._pool: concurrent.futures.ThreadPoolExecutor | None = None
        self._fut_map: dict[concurrent.futures.Future, str] = {}
        self._results: dict[str, bool] = {}
        self._done_count = 0
        self._total = len(ips)
        self._timer: QTimer | None = None

    def start(self):
        self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=30)
        self._fut_map = {}
        for ip in self.ips:
            if self._cancel:
                break
            fut = self._pool.submit(_ping_ip, ip, 150)
            self._fut_map[fut] = ip

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(50)

    def cancel(self):
        self._cancel = True

    def _poll(self):
        if self._cancel:
            self._cleanup()
            return

        done = {f for f in self._fut_map if f.done()}
        for fut in done:
            ip, alive = fut.result()
            self._results[ip] = alive
            self._done_count += 1
            del self._fut_map[fut]

        self.progress.emit(self._done_count, self._total)

        if not self._fut_map:
            self._cleanup()
            self.finished.emit(self._results)

    def _cleanup(self):
        if self._timer:
            self._timer.stop()
            self._timer = None
        if self._pool:
            self._pool.shutdown(wait=False)
            self._pool = None
        self._fut_map.clear()


# =========================================================================
# 扫描结果对话框
# =========================================================================
class ScanResultDialog(_FramelessDialog):
    def __init__(self, adapter: dict, ips: list[str], direction_label: str,
                 parent=None, on_ip_set=None):
        super().__init__(parent=parent, title=f'扫描结果 - {direction_label}')
        self.resize(580, 540)
        self.adapter = adapter
        self.available_ips: list[str] = []
        self.selected_ip: str | None = None
        self._on_ip_set = on_ip_set  # IP 设置成功后的回调

        # 适配器信息卡片
        info_card = CardWidget()
        info_card.setBorderRadius(8)
        info_card.setStyleSheet(_card_style())
        info_layout = QHBoxLayout(info_card)
        info_layout.setContentsMargins(12, 8, 12, 8)

        icon_label = BodyLabel('📡')
        icon_label.setStyleSheet('font-size: 20px; margin-right: 8px;')
        info_layout.addWidget(icon_label)

        info_text = StrongBodyLabel(
            f'{adapter["name"]}  |  {adapter["ip"]} / {adapter["mask"]}'
        )
        info_layout.addWidget(info_text)
        info_layout.addStretch()
        self._content_layout.addWidget(info_card)

        # 进度条
        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, len(ips))
        self.progress_bar.setFixedHeight(6)
        self.progress_label = CaptionLabel('准备扫描…')
        self.progress_label.setStyleSheet(f'color: {_text_secondary()};')

        progress_row = QHBoxLayout()
        progress_row.addWidget(self.progress_bar, stretch=1)
        progress_row.addWidget(self.progress_label)
        self._content_layout.addLayout(progress_row)

        # 表格
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['IP 地址', '状态'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.verticalHeader().hide()
        self.table.setStyleSheet(_table_style())
        self.table.itemDoubleClicked.connect(self._on_row_double_click)
        self._content_layout.addWidget(self.table, stretch=1)

        hint = CaptionLabel('💡 双击空闲 IP 可直接填入并应用')
        hint.setStyleSheet(f'color: {_text_secondary()};')
        self._content_layout.addWidget(hint)

        btn_layout = QHBoxLayout()
        self.btn_apply = PushButton(FIF.CHECKBOX, '应用选中')
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply_selected)
        self.btn_manual = PushButton(FIF.SETTING, '手动设置')
        self.btn_manual.clicked.connect(self._open_manual)
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_manual)
        btn_layout.addStretch()
        self.btn_close = PushButton('关闭')
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)
        self._content_layout.addLayout(btn_layout)

        # 启动扫描（QTimer 轮询 ThreadPoolExecutor，无 QThread 避免跨线程信号问题）
        self._scan_finished = False
        self._poller = _ScanPoller(ips)
        self._poller.progress.connect(self._on_progress)
        self._poller.finished.connect(self._on_finished)
        self._poller.start()

    def reject(self):
        """关闭对话框时确保扫描停止"""
        if hasattr(self, '_poller') and self._poller is not None:
            self._poller.cancel()
        super().reject()

    def _on_progress(self, current: int, total: int):
        self.progress_bar.setValue(current)
        self.progress_label.setText(f'{current}/{total}')

    def _on_finished(self, results: dict[str, bool]):
        if self._scan_finished:
            return
        self._scan_finished = True
        self.progress_bar.setValue(self.progress_bar.maximum())
        online_count = sum(1 for v in results.values() if v)
        self.progress_label.setText(f'完成  ({online_count} 个在线)')

        self.table.setRowCount(0)
        available = []

        # 按 IP 升序排序
        try:
            sorted_ips = sorted(results.keys(), key=lambda ip: tuple(int(x) for x in ip.split('.')))
        except Exception:
            sorted_ips = list(results.keys())

        for ip in sorted_ips:
            alive = results[ip]
            row = self.table.rowCount()
            self.table.insertRow(row)

            item_ip = QTableWidgetItem(ip)
            item_ip.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, item_ip)

            status_text = '🟢 在线' if alive else '⚪ 空闲'
            item_status = QTableWidgetItem(status_text)
            item_status.setTextAlignment(Qt.AlignCenter)
            if alive:
                item_status.setForeground(QColor('#888888'))
            else:
                item_status.setForeground(QColor('#2e7d32'))
                available.append(ip)
            self.table.setItem(row, 1, item_status)

        self.available_ips = available
        if available:
            self.btn_apply.setEnabled(True)
        self._scan_finished = True
        self._poller = None

    def _on_row_double_click(self, item: QTableWidgetItem):
        row = item.row()
        ip = self.table.item(row, 0).text()
        status = self.table.item(row, 1).text()
        if '空闲' in status:
            self.selected_ip = ip
            self._open_manual_with_ip(ip)

    def _apply_selected(self):
        rows = self.table.selectedItems()
        if not rows:
            InfoBar.info(title='提示', content='请先选中一个可用 IP', parent=self)
            return
        row = rows[0].row()
        ip = self.table.item(row, 0).text()
        status = self.table.item(row, 1).text()
        if '在线' in status:
            InfoBar.warning(title='警告', content=f'{ip} 当前在线，请选择空闲 IP', parent=self)
            return
        self.selected_ip = ip
        self._open_manual_with_ip(ip)

    def _open_manual_with_ip(self, ip: str):
        dlg = ManualIpDialog(self.adapter, preset_ip=ip, parent=self)
        if dlg.exec() == QDialog.Accepted:
            InfoBar.success(title='IP 设置成功',
                            content=f'{self.adapter["name"]} 已设置为 {ip}',
                            parent=self, duration=3000)
            if self._on_ip_set:
                self._on_ip_set()

    def _open_manual(self):
        dlg = ManualIpDialog(self.adapter, parent=self)
        if dlg.exec() == QDialog.Accepted:
            InfoBar.success(title='IP 设置成功',
                            content=f'{self.adapter["name"]} 已设置',
                            parent=self, duration=3000)
            if self._on_ip_set:
                self._on_ip_set()


# =========================================================================
# 手动设置 IP 对话框
# =========================================================================
class ManualIpDialog(_FramelessDialog):
    def __init__(self, adapter: dict, preset_ip: str = '', parent=None):
        super().__init__(parent=parent, title=f'手动设置 IP - {adapter["name"]}')
        self.resize(440, 340)
        self.adapter = adapter

        card = CardWidget()
        card.setBorderRadius(8)
        card.setStyleSheet(_card_style())
        form_layout = QVBoxLayout(card)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setSpacing(12)

        # 适配器选择
        row1 = QHBoxLayout()
        lbl1 = BodyLabel('网络适配器:')
        lbl1.setFixedWidth(80)
        self.combo_adapter = ComboBox()
        self._all_adapters = get_adapters()
        for a in self._all_adapters:
            self.combo_adapter.addItem(a['name'])
        idx = self.combo_adapter.findText(adapter['name'])
        if idx >= 0:
            self.combo_adapter.setCurrentIndex(idx)
        self.combo_adapter.currentIndexChanged.connect(self._on_adapter_changed)
        row1.addWidget(lbl1)
        row1.addWidget(self.combo_adapter, stretch=1)
        form_layout.addLayout(row1)

        # IP 地址
        row2 = QHBoxLayout()
        lbl2 = BodyLabel('IP 地址:')
        lbl2.setFixedWidth(80)
        self.edit_ip = LineEdit()
        self.edit_ip.setText(preset_ip or adapter['ip'])
        self.edit_ip.setPlaceholderText('例如: 192.168.1.100')
        row2.addWidget(lbl2)
        row2.addWidget(self.edit_ip, stretch=1)
        form_layout.addLayout(row2)

        # 子网掩码
        row3 = QHBoxLayout()
        lbl3 = BodyLabel('子网掩码:')
        lbl3.setFixedWidth(80)
        self.edit_mask = LineEdit()
        self.edit_mask.setText(adapter['mask'] or '255.255.255.0')
        self.edit_mask.setPlaceholderText('例如: 255.255.255.0')
        row3.addWidget(lbl3)
        row3.addWidget(self.edit_mask, stretch=1)
        form_layout.addLayout(row3)

        # 默认网关
        row4 = QHBoxLayout()
        lbl4 = BodyLabel('默认网关:')
        lbl4.setFixedWidth(80)
        self.edit_gateway = LineEdit()
        self.edit_gateway.setText(adapter['gateway'] or '')
        self.edit_gateway.setPlaceholderText('留空则不设置网关')
        row4.addWidget(lbl4)
        row4.addWidget(self.edit_gateway, stretch=1)
        form_layout.addLayout(row4)

        self._content_layout.addWidget(card)

        # 管理员提示
        if not is_admin():
            hint = CardWidget()
            hint.setBorderRadius(8)
            hint.setStyleSheet(_card_style())
            hint_layout = QHBoxLayout(hint)
            hint_layout.setContentsMargins(12, 8, 12, 8)
            hint_icon = BodyLabel('⚠')
            hint_icon.setStyleSheet('font-size: 16px; color: #d0870a;')
            hint_text = BodyLabel('需要管理员权限才能修改 IP，请以管理员身份运行程序')
            hint_text.setStyleSheet('color: #d0870a;')
            hint_layout.addWidget(hint_icon)
            hint_layout.addWidget(hint_text)
            self._content_layout.addWidget(hint)

        self._content_layout.addStretch()

        btn_layout = QHBoxLayout()
        self.btn_apply = PrimaryPushButton(FIF.ACCEPT, '应用')
        self.btn_apply.clicked.connect(self._apply)
        self.btn_cancel = PushButton('取消')
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_apply)
        self._content_layout.addLayout(btn_layout)

    def _on_adapter_changed(self, index: int):
        if 0 <= index < len(self._all_adapters):
            a = self._all_adapters[index]
            self.edit_ip.setText(a['ip'] or '')
            self.edit_mask.setText(a['mask'] or '')
            self.edit_gateway.setText(a['gateway'] or '')

    def _apply(self):
        adapter_name = self.combo_adapter.currentText()
        ip = self.edit_ip.text().strip()
        mask = self.edit_mask.text().strip()
        gateway = self.edit_gateway.text().strip()

        if not ip or not mask:
            InfoBar.warning(title='输入错误', content='IP 地址和子网掩码不能为空', parent=self)
            return

        ok, msg = set_static_ip(adapter_name, ip, mask, gateway)
        if ok:
            _set_preferred_adapter_name(adapter_name)
            self.accept()
        else:
            InfoBar.error(title='设置失败', content=msg, parent=self, duration=4000)


# =========================================================================
# DDNS 配置对话框
# =========================================================================
class DdnsConfigDialog(_FramelessDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent, title='阿里云 DDNS 配置')
        self.resize(520, 480)

        sub = CaptionLabel('将当前适配器的内网 IP 自动同步到阿里云 DNS 解析记录')
        sub.setStyleSheet(f'color: {_text_secondary()}; margin-bottom: 4px;')
        self._content_layout.addWidget(sub)

        # 配置卡片
        card = CardWidget()
        card.setBorderRadius(8)
        card.setStyleSheet(_card_style())
        form = QVBoxLayout(card)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)

        r1 = QHBoxLayout()
        r1_lbl = BodyLabel('AccessKey ID:')
        r1_lbl.setFixedWidth(110)
        self.edit_ak_id = LineEdit()
        self.edit_ak_id.setPlaceholderText('阿里云 RAM 用户的 AccessKey ID')
        r1.addWidget(r1_lbl)
        r1.addWidget(self.edit_ak_id, stretch=1)
        form.addLayout(r1)

        r2 = QHBoxLayout()
        r2_lbl = BodyLabel('AccessKey Secret:')
        r2_lbl.setFixedWidth(110)
        self.edit_ak_secret = PasswordLineEdit()
        self.edit_ak_secret.setPlaceholderText('阿里云 RAM 用户的 AccessKey Secret')
        r2.addWidget(r2_lbl)
        r2.addWidget(self.edit_ak_secret, stretch=1)
        form.addLayout(r2)

        form.addWidget(CaptionLabel(''))

        r3 = QHBoxLayout()
        r3_lbl = BodyLabel('域名:')
        r3_lbl.setFixedWidth(110)
        self.edit_domain = LineEdit()
        self.edit_domain.setPlaceholderText('例如: example.com')
        r3.addWidget(r3_lbl)
        r3.addWidget(self.edit_domain, stretch=1)
        form.addLayout(r3)

        r4 = QHBoxLayout()
        r4_lbl = BodyLabel('主机记录:')
        r4_lbl.setFixedWidth(110)
        self.edit_rr = LineEdit()
        self.edit_rr.setPlaceholderText('例如: www, @, *')
        r4.addWidget(r4_lbl)
        r4.addWidget(self.edit_rr, stretch=1)
        form.addLayout(r4)

        r5 = QHBoxLayout()
        r5_lbl = BodyLabel('记录类型:')
        r5_lbl.setFixedWidth(110)
        self.combo_type = ComboBox()
        self.combo_type.addItems(['A', 'AAAA'])
        r5.addWidget(r5_lbl)
        r5.addWidget(self.combo_type, stretch=1)
        form.addLayout(r5)

        r6 = QHBoxLayout()
        r6_lbl = BodyLabel('关联适配器:')
        r6_lbl.setFixedWidth(110)
        self.combo_adapter = ComboBox()
        adapters = get_adapters()
        self._ddns_adapters = [a for a in adapters if a['ip']] or adapters
        for a in self._ddns_adapters:
            self.combo_adapter.addItem(a['name'])
        preferred = _get_preferred_adapter_name()
        if preferred:
            for i, a in enumerate(self._ddns_adapters):
                if a['name'] == preferred:
                    self.combo_adapter.setCurrentIndex(i)
                    break
        r6.addWidget(r6_lbl)
        r6.addWidget(self.combo_adapter, stretch=1)
        form.addLayout(r6)

        self._content_layout.addWidget(card)

        # 状态显示
        self.status_card = CardWidget()
        self.status_card.setBorderRadius(8)
        self.status_card.setStyleSheet(_card_style())
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(12, 8, 12, 8)

        status_header = QHBoxLayout()
        self.status_label = StrongBodyLabel('状态: 未配置')
        status_header.addWidget(self.status_label)
        status_header.addStretch()

        self.btn_test = PushButton(FIF.SEARCH, '测试连接')
        self.btn_test.clicked.connect(self._test_connection)
        status_header.addWidget(self.btn_test)
        status_layout.addLayout(status_header)

        self.status_detail = CaptionLabel('')
        self.status_detail.setStyleSheet(f'color: {_text_secondary()};')
        self.status_detail.setWordWrap(True)
        status_layout.addWidget(self.status_detail)

        self._content_layout.addWidget(self.status_card)

        self._load_config()

        self._content_layout.addStretch()

        btn_layout = QHBoxLayout()
        self.btn_save = PrimaryPushButton(FIF.SAVE, '保存配置')
        self.btn_save.clicked.connect(self._save)
        self.btn_cancel = PushButton('取消')
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        self._content_layout.addLayout(btn_layout)

    def _load_config(self):
        ddns = _get_ddns_config()
        self.edit_ak_id.setText(ddns.get('access_key_id', ''))
        self.edit_ak_secret.setText(ddns.get('access_key_secret', ''))
        self.edit_domain.setText(ddns.get('domain', ''))
        self.edit_rr.setText(ddns.get('rr', ''))
        type_idx = 0 if ddns.get('type', 'A') == 'A' else 1
        self.combo_type.setCurrentIndex(type_idx)

        adapter_name = ddns.get('adapter_name', '')
        if adapter_name:
            for i in range(self.combo_adapter.count()):
                if self.combo_adapter.itemText(i) == adapter_name:
                    self.combo_adapter.setCurrentIndex(i)
                    break

        if ddns.get('access_key_id') and ddns.get('domain'):
            self.status_label.setText('状态: 已配置')
            self.status_detail.setText(
                f"域名: {ddns.get('rr', '@')}.{ddns.get('domain', '')}  |  类型: {ddns.get('type', 'A')}"
            )

    def _test_connection(self):
        ak_id = self.edit_ak_id.text().strip()
        ak_secret = self.edit_ak_secret.text().strip()
        domain = self.edit_domain.text().strip()
        if not ak_id or not ak_secret or not domain:
            InfoBar.warning(title='信息不完整',
                            content='请填写 AccessKey ID/Secret 和域名', parent=self)
            return
        self.btn_test.setEnabled(False)
        self.btn_test.setText('测试中…')
        self.status_label.setText('状态: 正在测试…')
        self.status_detail.setText('正在连接阿里云 DNS API…')
        QTimer.singleShot(100, lambda: self._do_test(ak_id, ak_secret, domain))

    def _do_test(self, ak_id, ak_secret, domain):
        try:
            records = ddns_get_records(ak_id, ak_secret, domain)
            if records:
                self.status_label.setText('✅ 连接成功')
                self.status_detail.setText(f'找到 {len(records)} 条 DNS 记录')
            else:
                self.status_label.setText('✅ 连接成功（无记录）')
                self.status_detail.setText('域名验证通过，但没有找到当前类型的记录')
        except Exception as e:
            self.status_label.setText('❌ 连接失败')
            self.status_detail.setText(str(e)[:100])
        finally:
            self.btn_test.setEnabled(True)
            self.btn_test.setText('测试连接')

    def _save(self):
        ak_id = self.edit_ak_id.text().strip()
        ak_secret = self.edit_ak_secret.text().strip()
        domain = self.edit_domain.text().strip()
        rr = self.edit_rr.text().strip()
        type_ = self.combo_type.currentText()
        adapter_name = self.combo_adapter.currentText()
        if not ak_id or not ak_secret or not domain:
            InfoBar.warning(title='信息不完整',
                            content='AccessKey ID/Secret 和域名不能为空', parent=self)
            return
        ddns = {
            'access_key_id': ak_id, 'access_key_secret': ak_secret,
            'domain': domain, 'rr': rr, 'type': type_, 'ttl': 600,
            'adapter_name': adapter_name,
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        _set_ddns_config(ddns)
        InfoBar.success(title='已保存', content='DDNS 配置已保存', parent=self, duration=1500)
        self.accept()


# =========================================================================
# DDNS 状态与更新对话框
# =========================================================================
class DdnsStatusDialog(_FramelessDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent, title='DDNS 状态')
        self.resize(500, 420)

        # 配置信息卡片
        self.cfg_card = CardWidget()
        self.cfg_card.setBorderRadius(8)
        self.cfg_card.setStyleSheet(_card_style())
        cfg_layout = QVBoxLayout(self.cfg_card)
        cfg_layout.setContentsMargins(16, 12, 16, 12)
        self.cfg_text = BodyLabel('')
        self.cfg_text.setWordWrap(True)
        cfg_layout.addWidget(self.cfg_text)
        self._content_layout.addWidget(self.cfg_card)

        # 内网 IP 卡片
        ip_card = CardWidget()
        ip_card.setBorderRadius(8)
        ip_card.setStyleSheet(_card_style())
        ip_layout = QVBoxLayout(ip_card)
        ip_layout.setContentsMargins(16, 12, 16, 12)

        ip_header = QHBoxLayout()
        self.ip_label = StrongBodyLabel('内网 IP: 查询中…')
        ip_header.addWidget(self.ip_label)
        ip_header.addStretch()
        self.btn_refresh_ip = ToolButton(FIF.SYNC)
        self.btn_refresh_ip.clicked.connect(self._refresh_ip)
        ip_header.addWidget(self.btn_refresh_ip)
        ip_layout.addLayout(ip_header)

        self.ip_detail = CaptionLabel('')
        self.ip_detail.setStyleSheet(f'color: {_text_secondary()};')
        ip_layout.addWidget(self.ip_detail)
        self._content_layout.addWidget(ip_card)

        # DNS 记录卡片
        self.status_card = CardWidget()
        self.status_card.setBorderRadius(8)
        self.status_card.setStyleSheet(_card_style())
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(16, 12, 16, 12)
        status_layout.addWidget(StrongBodyLabel('DNS 记录'))
        self.record_text = BodyLabel('未检查')
        self.record_text.setWordWrap(True)
        status_layout.addWidget(self.record_text)
        self._content_layout.addWidget(self.status_card)

        self._content_layout.addStretch()

        btn_layout = QHBoxLayout()
        self.btn_update = PrimaryPushButton(FIF.SYNC, '立即同步')
        self.btn_update.clicked.connect(self._do_update)
        btn_layout.addWidget(self.btn_update)
        btn_layout.addStretch()
        self.btn_close = PushButton('关闭')
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        self._content_layout.addLayout(btn_layout)

        self._refresh_status()

    def _refresh_status(self):
        ddns = _get_ddns_config()
        if not ddns.get('access_key_id') or not ddns.get('domain'):
            self.cfg_text.setText('⚠ DDNS 未配置，请先在配置中设置阿里云信息')
            self.btn_update.setEnabled(False)
            return

        rr = ddns.get('rr', '@')
        domain = ddns.get('domain', '')
        type_ = ddns.get('type', 'A')
        updated = ddns.get('updated_at', '从未更新')
        adapter_name = ddns.get('adapter_name', '')

        self.cfg_text.setText(
            f'域名: {rr}.{domain}\n记录类型: {type_}\n适配器: {adapter_name or "自动"}\n最后更新: {updated}'
        )
        self.btn_update.setEnabled(True)
        self._refresh_ip()
        self._refresh_dns_records()

    def _refresh_ip(self):
        ddns = _get_ddns_config()
        adapter_name = ddns.get('adapter_name', '')
        self.ip_label.setText('内网 IP: 查询中…')
        QTimer.singleShot(100, lambda: self._do_refresh_ip(adapter_name))

    def _do_refresh_ip(self, adapter_name):
        ip = get_current_ip(adapter_name)
        if ip:
            self.ip_label.setText(f'内网 IP: {ip}')
            self._current_ip = ip
            self.ip_detail.setText(
                f'适配器: {adapter_name or "自动选择"}  |  {datetime.now().strftime("%H:%M:%S")}'
            )
        else:
            self.ip_label.setText('内网 IP: 获取失败')
            self._current_ip = None
            self.ip_detail.setText('无法获取适配器 IP，请检查网络连接')

    def _refresh_dns_records(self):
        ddns = _get_ddns_config()
        if not ddns.get('access_key_id'):
            self.record_text.setText('未配置认证信息')
            return
        QTimer.singleShot(100, lambda: self._do_fetch_records(ddns))

    def _do_fetch_records(self, ddns):
        try:
            records = ddns_get_records(
                ddns['access_key_id'], ddns['access_key_secret'],
                ddns['domain'], ddns.get('rr', ''), ddns.get('type', 'A'),
            )
            if records:
                lines = []
                for r in records[:5]:
                    val = r.get('Value', '?')
                    rr = r.get('RR', '?')
                    lines.append(f'  {rr}.{ddns["domain"]}  →  {val}')
                text = f'找到 {len(records)} 条记录:\n' + '\n'.join(lines)
                if len(records) > 5:
                    text += '\n  …更多'
                self.record_text.setText(text)
                self._records = records
            else:
                self.record_text.setText('没有找到匹配的记录')
                self.record_text.setStyleSheet(f'color: {_text_secondary()};')
                self._records = []
        except Exception as e:
            self.record_text.setText(f'查询失败: {str(e)[:100]}')
            self._records = []

    def _do_update(self):
        ddns = _get_ddns_config()
        if not getattr(self, '_current_ip', None):
            InfoBar.warning(title='无内网 IP', content='无法获取适配器 IP，请稍后再试', parent=self)
            return

        ip = self._current_ip
        ak_id = ddns.get('access_key_id', '')
        ak_secret = ddns.get('access_key_secret', '')
        domain = ddns.get('domain', '')
        rr = ddns.get('rr', '@')
        type_ = ddns.get('type', 'A')
        ttl = int(ddns.get('ttl', 600))

        self.btn_update.setEnabled(False)
        self.btn_update.setText('同步中…')
        self.record_text.setText('正在同步…')

        # 优先使用缓存的记录，避免重复 API 请求
        cached_records = getattr(self, '_records', None)
        if cached_records and isinstance(cached_records, list):
            QTimer.singleShot(100, lambda: self._do_sync(
                ak_id, ak_secret, domain, rr, type_, ip, ttl, ddns, cached_records
            ))
        else:
            QTimer.singleShot(100, lambda: self._do_sync(
                ak_id, ak_secret, domain, rr, type_, ip, ttl, ddns
            ))

    def _do_sync(self, ak_id, ak_secret, domain, rr, type_, ip, ttl, ddns, existing_records=None):
        try:
            records = existing_records or ddns_get_records(ak_id, ak_secret, domain, rr, type_)
            target_rr = rr or '@'
            matched = [r for r in records if r.get('RR', '') == target_rr]

            if matched:
                record = matched[0]
                current_value = record.get('Value', '')
                if current_value == ip:
                    status_msg = ('no_change', f'IP 未变更 ({ip})')
                else:
                    ok, msg = ddns_update_record(ak_id, ak_secret, record['RecordId'],
                                                 target_rr, type_, ip, ttl)
                    status_msg = ('updated' if ok else 'error', msg)
            else:
                ok, msg = ddns_add_record(ak_id, ak_secret, domain, target_rr, type_, ip, ttl)
                status_msg = ('created' if ok else 'error', msg)
        except Exception as e:
            status_msg = ('error', str(e))

        self.btn_update.setEnabled(True)
        self.btn_update.setText('立即同步')

        status, msg = status_msg
        if status == 'no_change':
            InfoBar.info(title='无需更新', content=msg, parent=self, duration=3000)
        elif status in ('updated', 'created'):
            ddns['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            _set_ddns_config(ddns)
            InfoBar.success(title='同步成功', content=msg, parent=self, duration=3000)
            self._refresh_status()
        else:
            InfoBar.error(title='同步失败', content=msg, parent=self, duration=4000)


# =========================================================================
# Plugin
# =========================================================================

class Plugin:
    @hook
    def start(self, api) -> bool:
        self.api = api
        self.sdk = PluginSDK(api, PLUGIN_NAME)
        self.sdk.logger_info('插件已加载')
        return True

    @hook
    def on_disable(self):
        self.sdk.logger_info(f'{PLUGIN_NAME} 禁用')

    @hook
    def get_name(self) -> str:
        return PLUGIN_NAME

    @hook
    def get_description(self) -> str:
        try:
            with open(PLUGIN_PATH / 'readme.md', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.sdk.logger_error(f'读取描述出错: {e}')
            return '切换静态IP插件 - 支持同网段IP扫描、手动配置、阿里云DDNS（内网IP）'

    @hook
    def get_menu(self) -> list[dict]:
        menu = PluginMenu()
        menu.add_funcs([
            {'function': '📋 查看网络信息', 'object': self.show_network_info},
            {'function': '📡 扫描当前网段', 'object': self.scan_subnet},
            {'function': '🔧 手动设置IP', 'object': self.manual_set_ip},
            {'function': '🔄 恢复DHCP', 'object': self.revert_dhcp},
            {'function': '🌐 DDNS 配置', 'object': self.ddns_config},
            {'function': '🌐 DDNS 状态与同步', 'object': self.ddns_status},
        ])
        return menu.get_all()

    @staticmethod
    def _is_virtual_adapter(name: str) -> bool:
        keywords = ['tailscale', 'loopback', 'virtual', 'bluetooth',
                    'pseudo', 'tunnel', 'vmware', 'vbox', 'hyper-v', 'localhost']
        lower = name.lower()
        return any(k in lower for k in keywords)

    def _get_usable_adapter(self) -> dict | None:
        preferred = _get_preferred_adapter_name()
        all_adapters = get_adapters()

        def has_ip(a):
            return bool(a['ip'])

        if preferred:
            for a in all_adapters:
                if a['name'] == preferred and has_ip(a):
                    return a
        for a in all_adapters:
            if a['ip'] and a['gateway'] and not self._is_virtual_adapter(a['name']):
                return a
        for a in all_adapters:
            if a['ip'] and a['gateway']:
                return a
        for a in all_adapters:
            if has_ip(a):
                return a
        return all_adapters[0] if all_adapters else None

    def show_network_info(self):
        dlg = NetworkInfoDialog()
        dlg.exec()

    def _adapter_picker(self, title: str) -> dict | None:
        sel = AdapterSelectDialog(title)
        if sel.exec() != QDialog.Accepted:
            return None
        return sel.selected_adapter()

    def scan_subnet(self):
        """扫描当前网段所有 IP"""
        adapter = self._adapter_picker('选择适配器')
        if not adapter or not adapter['ip'] or not adapter['mask']:
            return
        net = calc_network(adapter['ip'], adapter['mask'])
        if not net:
            InfoBar.warning(title='计算失败', content='无法计算子网范围', parent=None)
            return
        # 获取子网内所有可用 IP
        from plugin_sdk import PluginSDK
        PluginSDK(self.api, PLUGIN_NAME).logger_info(f'扫描网段: {net}')
        all_hosts = list(net.hosts())
        # 限制最大扫描数量，避免 C 类大子网扫描太久
        max_scan = 254
        if len(all_hosts) > max_scan:
            # 取当前 IP 附近 max_scan 个
            try:
                cur = ipaddress.IPv4Address(adapter['ip'])
                idx = all_hosts.index(cur)
                half = max_scan // 2
                start = max(0, idx - half)
                end = min(len(all_hosts), idx + half)
                ips = [str(h) for h in all_hosts[start:end]]
            except ValueError:
                ips = [str(h) for h in all_hosts[:max_scan]]
        else:
            ips = [str(h) for h in all_hosts]

        if not ips:
            InfoBar.info(title='提示', content='子网内没有可用 IP', parent=None)
            return

        dlg = ScanResultDialog(adapter, ips, f'全子网扫描 (共 {len(ips)} 个)',
                                on_ip_set=lambda: self._do_after_ip_set(adapter['name']))
        dlg.exec()

    def _do_after_ip_set(self, adapter_name: str):
        """IP 设置完成后后台重试 DDNS 同步（网络变更后需等待连通）"""
        _set_preferred_adapter_name(adapter_name)
        self.sdk.logger_info(f'IP 已变更到 {adapter_name}，DDNS 将在后台重试同步')

        ddns_cfg = _get_ddns_config()
        if not ddns_cfg.get('access_key_id') or not ddns_cfg.get('domain'):
            return

        import threading

        def do_ddns_with_retry():
            for attempt in range(3):
                try:
                    cur_ip = get_current_ip(adapter_name)
                    if not cur_ip:
                        time.sleep(5)
                        continue

                    cfg = dict(ddns_cfg)
                    ak_id = cfg['access_key_id']
                    ak_secret = cfg['access_key_secret']
                    domain = cfg['domain']
                    rr = cfg.get('rr', '@')
                    type_ = cfg.get('type', 'A')
                    ttl = int(cfg.get('ttl', 600))
                    records = ddns_get_records(ak_id, ak_secret, domain, rr, type_)
                    matched = [r for r in records if r.get('RR', '') == rr]
                    if matched:
                        record = matched[0]
                        if record.get('Value') != cur_ip:
                            ok, msg = ddns_update_record(ak_id, ak_secret, record['RecordId'],
                                                         rr, type_, cur_ip, ttl)
                            if ok:
                                d = _get_ddns_config()
                                d['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                _set_ddns_config(d)
                                logger.info(f'[{PLUGIN_NAME}] DDNS 同步成功: {rr}.{domain} → {cur_ip}')
                                return
                    else:
                        ok, msg = ddns_add_record(ak_id, ak_secret, domain, rr, type_, cur_ip, ttl)
                        if ok:
                            d = _get_ddns_config()
                            d['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            _set_ddns_config(d)
                            logger.info(f'[{PLUGIN_NAME}] DDNS 记录已添加: {rr}.{domain} → {cur_ip}')
                            return
                except Exception as e:
                    logger.error(f'[{PLUGIN_NAME}] DDNS 尝试 {attempt+1}/3 失败: {e}')
                    time.sleep(10)
                else:
                    return
            logger.error(f'[{PLUGIN_NAME}] DDNS 同步失败（3 次重试后放弃）')

        threading.Thread(target=do_ddns_with_retry, daemon=True).start()

    def manual_set_ip(self):
        adapter = self._get_usable_adapter()
        if not adapter:
            InfoBar.warning(title='无可用适配器', content='未检测到任何网络适配器', parent=None)
            return
        dlg = ManualIpDialog(adapter)
        if dlg.exec() == QDialog.Accepted:
            preferred = dlg.combo_adapter.currentText()
            InfoBar.success(title='IP 设置成功',
                            content=f'{preferred} 已设置为 {dlg.edit_ip.text()}',
                            parent=None, duration=3000)
            self.sdk.logger_info(f'静态IP设置成功: {preferred} -> {dlg.edit_ip.text()}')
            self._do_after_ip_set(preferred)

    def revert_dhcp(self):
        adapter = self._adapter_picker('恢复 DHCP')
        if not adapter:
            return
        if not self.sdk.show_confirm(
            '恢复 DHCP',
            f'确定要将「{adapter["name"]}」恢复为 DHCP 自动获取 IP 吗？\n当前 IP: {adapter["ip"] or "未设置"}'
        ):
            return
        ok, msg = set_dhcp(adapter['name'])
        if ok:
            InfoBar.success(title='DHCP 恢复成功', content=msg, parent=None, duration=3000)
            self.sdk.logger_info(f'DHCP 恢复成功: {adapter["name"]}')
            self._do_after_ip_set(adapter['name'])
        else:
            InfoBar.error(title='失败', content=msg, parent=None, duration=3000)

    # ── DDNS ──

    def ddns_config(self):
        dlg = DdnsConfigDialog()
        dlg.exec()

    def ddns_status(self):
        dlg = DdnsStatusDialog()
        dlg.exec()
