# 切换静态IP插件 - 支持同网段IP扫描和手动设置
import pluggy
import subprocess
import re
import ipaddress
import socket
import concurrent.futures
import ctypes
import sys
import tomlkit
from pathlib import Path

from plugin_sdk import PluginSDK, PluginMenu

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QMessageBox, QFormLayout,
    QDialogButtonBox, QProgressBar, QHeaderView,
    QAbstractItemView, QTableWidget, QTableWidgetItem,
    QWidget, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont

from qfluentwidgets import (
    PushButton, PrimaryPushButton, ComboBox, LineEdit,
    StrongBodyLabel, BodyLabel, FluentIcon as FIF,
    InfoBar, CardWidget, InfoBarIcon, InfoBarPosition,
)

PLUGIN_NAME = '切换静态IP'
PLUGIN_VERSION = '1.0.0'
PLUGIN_AUTHOR = 'tiosa'
PLUGIN_PATH = Path(__file__).parent
PLUGIN_CFG = PLUGIN_PATH / 'config.toml'

hook = pluggy.HookimplMarker("toudawifi")


# ---------------------------------------------------------------------------
# 网络工具函数
# ---------------------------------------------------------------------------
def _run_cmd(cmd: list[str]) -> str:
    """运行外部命令并返回 stdout（含 stderr 合并）"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=False,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        raw = (r.stdout or b'') + (r.stderr or b'')
        # Windows 新版 netsh 输出 UTF-8，旧版输出 GBK
        for enc in ('utf-8', 'gbk', 'cp936'):
            try:
                return raw.decode(enc).strip()
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode('utf-8', errors='replace').strip()
    except FileNotFoundError:
        return ''


def is_admin() -> bool:
    """检查当前进程是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def mask_to_cidr(mask: str) -> int:
    """将点分十进制子网掩码转 CIDR 前缀长度"""
    return sum(bin(int(x)).count('1') for x in mask.split('.'))


def get_adapters() -> list[dict]:
    """获取所有网络适配器的 IP 配置信息

    返回格式:
    [{'name': '以太网', 'ip': '192.168.1.100',
      'mask': '255.255.255.0', 'gateway': '192.168.1.1',
      'dhcp': True}, ...]
    """
    out = _run_cmd(['netsh', 'interface', 'ip', 'show', 'config'])
    if not out or '没有启用' in out or '命令失败' in out:
        return []

    adapters = []
    blocks = re.split(r'\n(?=接口 ")', out)
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        m = re.search(r'接口 "(.+?)"', block)
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


def get_active_adapter() -> dict | None:
    """获取有默认网关的活动适配器（通常是正在上网的）"""
    adapters = get_adapters()
    # 优先选有 IP 且有网关的
    for a in adapters:
        if a['ip'] and a['gateway']:
            return a
    # 其次选有 IP 的
    for a in adapters:
        if a['ip']:
            return a
    return adapters[0] if adapters else None


def get_adapter_names() -> list[str]:
    """返回所有适配器名称列表"""
    return [a['name'] for a in get_adapters()]


def _ping_ip(ip: str, timeout: int = 200) -> tuple[str, bool]:
    """ping 单个 IP，返回 (ip, is_alive)"""
    try:
        r = subprocess.run(
            ['ping', '-n', '1', '-w', str(timeout), ip],
            capture_output=True, text=True, encoding='gbk',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return ip, r.returncode == 0
    except Exception:
        return ip, False


def scan_ips(ip_list: list[str], max_workers: int = 20, timeout: int = 200) -> dict[str, bool]:
    """并发扫描一批 IP 的在线状态

    返回 {ip: alive}
    """
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        fut_map = {pool.submit(_ping_ip, ip, timeout): ip for ip in ip_list}
        for fut in concurrent.futures.as_completed(fut_map):
            ip, alive = fut.result()
            results[ip] = alive
    return results


def set_static_ip(adapter_name: str, ip: str, subnet_mask: str, gateway: str = '') -> tuple[bool, str]:
    """设置静态 IP，返回 (成功, 消息)"""
    if not is_admin():
        return False, '需要管理员权限才能修改IP设置，请以管理员身份运行程序。'

    # 验证参数合法性
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
    """获取适配器上的静态 DNS 服务器列表，DHCP 获取的返回空"""
    out = _run_cmd(['netsh', 'interface', 'ip', 'show', 'dnsserver',
                    f'name={adapter_name}'])
    # 如果包含"静态配置的 DNS 服务器"说明是静态 DNS
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
    """恢复适配器的静态 DNS（先清空再逐个添加）"""
    # 先切到 DHCP DNS 清掉所有静态 DNS
    _run_cmd(['netsh', 'interface', 'ip', 'set', 'dnsserver',
              f'name={adapter_name}', 'source=dhcp'])
    # 再设回静态
    for i, srv in enumerate(servers):
        if i == 0:
            _run_cmd(['netsh', 'interface', 'ip', 'set', 'dnsserver',
                      f'name={adapter_name}', 'source=static', f'addr={srv}', 'register=primary'])
        else:
            _run_cmd(['netsh', 'interface', 'ip', 'add', 'dnsserver',
                      f'name={adapter_name}', f'addr={srv}', f'index={i+1}'])


def set_dhcp(adapter_name: str) -> tuple[bool, str]:
    """恢复适配器为 DHCP 自动获取 IP（保留静态 DNS 不变）"""
    if not is_admin():
        return False, '需要管理员权限才能修改IP设置，请以管理员身份运行程序。'

    # 保存现有的静态 DNS，恢复 DHCP 后重新写入
    saved_dns = _get_static_dns(adapter_name)

    out = _run_cmd(['netsh', 'interface', 'ip', 'set', 'address',
                    f'name={adapter_name}', 'source=dhcp'])
    if '确定' in out or 'OK' in out or not out:
        if saved_dns:
            _set_static_dns(adapter_name, saved_dns)
        return True, f'{adapter_name} 已切换为 DHCP 自动获取 IP（DNS 已保留）'
    if '需要提升' in out or 'elevation' in out.lower():
        return False, '需要管理员权限才能修改IP设置。'
    return False, f'设置失败:\n{out[:200]}'


def calc_network(ip_str: str, mask_str: str) -> ipaddress.IPv4Network | None:
    """计算 IP 所在的子网"""
    try:
        cidr = mask_to_cidr(mask_str)
        return ipaddress.IPv4Network(f'{ip_str}/{cidr}', strict=False)
    except Exception:
        return None


def get_subnet_hosts(net: ipaddress.IPv4Network) -> list[str]:
    """获取子网内所有可用主机 IP（字符串形式），排除网络地址和广播地址"""
    hosts = list(net.hosts())
    return [str(h) for h in hosts]


def get_ips_above(ip_str: str, net: ipaddress.IPv4Network, count: int = 50) -> list[str]:
    """获取当前 IP 向上 count 个 IP（同网段内）"""
    try:
        cur = ipaddress.IPv4Address(ip_str)
    except Exception:
        return []
    hosts = list(net.hosts())
    try:
        idx = hosts.index(cur)
    except ValueError:
        return [str(h) for h in hosts[-count:] if h > cur] or [str(h) for h in hosts[:count]]
    above = [str(h) for h in hosts[idx + 1:idx + 1 + count]]
    return above


def get_ips_below(ip_str: str, net: ipaddress.IPv4Network, count: int = 50) -> list[str]:
    """获取当前 IP 向下 count 个 IP（同网段内）"""
    try:
        cur = ipaddress.IPv4Address(ip_str)
    except Exception:
        return []
    hosts = list(net.hosts())
    try:
        idx = hosts.index(cur)
    except ValueError:
        return [str(h) for h in hosts[:count]]
    below = [str(h) for h in hosts[max(0, idx - count):idx]]
    below.reverse()
    return below


# ---------------------------------------------------------------------------
# 插件配置
# ---------------------------------------------------------------------------
def _load_cfg() -> dict:
    """加载插件配置文件"""
    try:
        with open(PLUGIN_CFG, 'r', encoding='utf-8') as f:
            return tomlkit.load(f)
    except Exception:
        return {}


def _save_cfg(data: dict):
    """保存插件配置文件"""
    PLUGIN_CFG.parent.mkdir(parents=True, exist_ok=True)
    with open(PLUGIN_CFG, 'w', encoding='utf-8') as f:
        tomlkit.dump(data, f)


def _get_preferred_adapter_name() -> str:
    """获取上次使用的适配器名称"""
    cfg = _load_cfg()
    return cfg.get('preferred_adapter', '')


def _set_preferred_adapter_name(name: str):
    """保存本次使用的适配器名称"""
    cfg = _load_cfg()
    cfg['preferred_adapter'] = name
    _save_cfg(cfg)


# ---------------------------------------------------------------------------
# SDK  — 使用公共 PluginSDK（src.plugin_sdk）
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 对话框
# ---------------------------------------------------------------------------
class _AdapterCard(CardWidget):
    """单个适配器的信息卡片"""

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self.setBorderRadius(8)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # 标题行：适配器名称 + DHCP 标签
        header = QHBoxLayout()
        title = StrongBodyLabel(info['name'])
        title.setStyleSheet('font-size: 14px;')
        header.addWidget(title)
        header.addStretch()

        dhcp_badge = BodyLabel('DHCP' if info['dhcp'] else '静态')
        dhcp_badge.setStyleSheet(
            'background-color: #d0d0d0; border-radius: 4px; padding: 1px 8px; font-size: 11px;'
            if info['dhcp'] else
            'background-color: #e3dac9; border-radius: 4px; padding: 1px 8px; font-size: 11px;'
        )
        header.addWidget(dhcp_badge)
        layout.addLayout(header)

        # 信息行
        rows = [
            ('IP', info['ip'] or '—'),
            ('子网掩码', info['mask'] or '—'),
            ('网关', info['gateway'] or '—'),
        ]
        for label, value in rows:
            row = QHBoxLayout()
            lbl = BodyLabel(f'{label}:')
            lbl.setStyleSheet('color: #888888; font-size: 12px; min-width: 50px;')
            val = BodyLabel(value)
            val.setStyleSheet('font-size: 12px;')
            row.addWidget(lbl)
            row.addWidget(val)
            row.addStretch()
            layout.addLayout(row)


class NetworkInfoDialog(QDialog):
    """显示所有网络适配器信息"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('所有网络适配器')
        self.resize(540, 420)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        # 标题
        title = StrongBodyLabel('网络适配器')
        title.setStyleSheet('font-size: 18px;')
        layout.addWidget(title)

        subtitle = BodyLabel(f'共 {len(get_adapters())} 个适配器')
        subtitle.setStyleSheet('color: #888888; margin-bottom: 8px;')
        layout.addWidget(subtitle)

        # 滚动区
        scroll = QWidget()
        scroll_layout = QVBoxLayout(scroll)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(8)
        for a in get_adapters():
            scroll_layout.addWidget(_AdapterCard(a))

        # 把滚动区塞进 QTextEdit 充当 scroll（简单兼容）
        text = QTextEdit(self)
        text.setReadOnly(True)
        text.setFrameShape(QFrame.Shape.NoFrame)
        text.setStyleSheet('background: transparent; border: none;')
        text.document().setDocumentMargin(0)

        html_parts = []
        for i, a in enumerate(get_adapters()):
            if i > 0:
                html_parts.append('<hr style="border: none; border-top: 1px solid #e0e0e0; margin: 8px 0;">')
            dhcp_label = 'DHCP' if a['dhcp'] else '静态'
            html_parts.append(f'''
<div style="padding: 8px 0;">
  <div style="font-size: 14px; font-weight: 600; margin-bottom: 4px;">
    {a["name"]}
    <span style="font-size: 11px; font-weight: 400; color: #666; background: #eee; border-radius: 4px; padding: 1px 8px; margin-left: 8px;">{dhcp_label}</span>
  </div>
  <table style="font-size: 12px; color: #555; line-height: 1.8;">
    <tr><td style="padding-right: 16px;">IP</td><td>{a["ip"] or "—"}</td></tr>
    <tr><td style="padding-right: 16px;">子网掩码</td><td>{a["mask"] or "—"}</td></tr>
    <tr><td style="padding-right: 16px;">网关</td><td>{a["gateway"] or "—"}</td></tr>
  </table>
</div>''')
        text.setHtml(''.join(html_parts))
        layout.addWidget(text, stretch=1)

        # 关闭按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self.accept)
        btn_box.setCenterButtons(True)
        layout.addWidget(btn_box)


class AdapterSelectDialog(QDialog):
    """选择适配器后再执行扫描"""

    def __init__(self, title: str = '选择适配器', parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(400, 200)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title_lbl = StrongBodyLabel('请选择要扫描的网络适配器')
        title_lbl.setStyleSheet('font-size: 15px;')
        layout.addWidget(title_lbl)

        self.combo = ComboBox()
        self._adapters = [a for a in get_adapters() if a['ip']]
        if not self._adapters:
            self._adapters = get_adapters()

        for a in self._adapters:
            text = a['name']
            if a['ip']:
                text += f'  ({a["ip"]})'
            self.combo.addItem(text)

        # 自动选中首选
        preferred = _get_preferred_adapter_name()
        if preferred:
            for i, a in enumerate(self._adapters):
                if a['name'] == preferred:
                    self.combo.setCurrentIndex(i)
                    break
        layout.addWidget(self.combo)

        # 提示
        tip = BodyLabel('将扫描该适配器所在网段的可用 IP')
        tip.setStyleSheet('color: #888;')
        layout.addWidget(tip)

        layout.addStretch()

        # 按钮
        btn_layout = QHBoxLayout()
        btn_cancel = PushButton('取消')
        btn_cancel.clicked.connect(self.reject)
        btn_ok = PrimaryPushButton(FIF.SEARCH, '开始扫描')
        btn_ok.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

    def selected_adapter(self) -> dict | None:
        idx = self.combo.currentIndex()
        if 0 <= idx < len(self._adapters):
            return self._adapters[idx]
        return None


class ScanWorker(QObject):
    """后台扫描 IP 的 Worker"""
    finished = Signal(dict)  # {ip: alive}
    progress = Signal(int, int)  # current, total
    error = Signal(str)

    def __init__(self, ips: list[str], parent=None):
        super().__init__(parent)
        self.ips = ips
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        results = {}
        total = len(self.ips)
        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as pool:
            fut_map = {}
            for ip in self.ips:
                if self._cancel:
                    break
                fut = pool.submit(_ping_ip, ip, 150)
                fut_map[fut] = ip

            done_count = 0
            for fut in concurrent.futures.as_completed(fut_map):
                if self._cancel:
                    break
                ip, alive = fut.result()
                results[ip] = alive
                done_count += 1
                self.progress.emit(done_count, total)

        self.finished.emit(results)


class ScanResultDialog(QDialog):
    """显示扫描结果，允许选择 IP 应用"""

    def __init__(self, adapter: dict, ips: list[str], direction_label: str, parent=None):
        super().__init__(parent)
        self.adapter = adapter
        self.available_ips: list[str] = []
        self.selected_ip: str | None = None

        self.setWindowTitle(f'扫描结果 - {direction_label}')
        self.resize(540, 520)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        # 标题
        title = StrongBodyLabel(f'扫描 {direction_label}')
        title.setStyleSheet('font-size: 16px;')
        layout.addWidget(title)

        # 适配器信息
        info = BodyLabel(f'{adapter["name"]}  ({adapter["ip"]} / {adapter["mask"]})')
        info.setStyleSheet('color: #888; margin-bottom: 4px;')
        layout.addWidget(info)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(ips))
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # 表格: IP | 状态
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['IP 地址', '状态'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.itemDoubleClicked.connect(self._on_row_double_click)
        layout.addWidget(self.table, stretch=1)

        # 说明
        hint = BodyLabel('双击空闲 IP 可直接填入手动设置窗口')
        hint.setStyleSheet('color: #999; font-size: 12px;')
        layout.addWidget(hint)

        # 底部按钮
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
        layout.addLayout(btn_layout)

        # 启动扫描线程
        self.worker = ScanWorker(ips)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _on_progress(self, current: int, total: int):
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f'正在扫描… {current}/{total}')

    def _on_finished(self, results: dict[str, bool]):
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.progress_bar.setFormat(f'扫描完成  ({sum(1 for v in results.values() if v)} 个在线)')
        self.table.setRowCount(0)

        available = []
        for ip, alive in results.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(ip))
            item_status = QTableWidgetItem('🟢 在线' if alive else '⚪ 空闲')
            if alive:
                item_status.setForeground(Qt.GlobalColor.gray)
            else:
                item_status.setForeground(Qt.GlobalColor.darkGreen)
                available.append(ip)
            self.table.setItem(row, 1, item_status)

        self.available_ips = available
        if available:
            self.btn_apply.setEnabled(True)
        self.thread.quit()
        self.worker.deleteLater()

    def _on_error(self, msg: str):
        self.thread.quit()

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
        if dlg.exec() == QDialog.DialogCode.Accepted:
            InfoBar.success(title='IP 设置成功',
                            content=f'{self.adapter["name"]} 已设置为 {ip}',
                            parent=self, duration=3000)

    def _open_manual(self):
        dlg = ManualIpDialog(self.adapter, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            InfoBar.success(title='IP 设置成功',
                            content=f'{self.adapter["name"]} 已设置',
                            parent=self, duration=3000)


class ManualIpDialog(QDialog):
    """手动设置 IP 的对话框，切换适配器时自动填入当前值"""

    def __init__(self, adapter: dict, preset_ip: str = '', parent=None):
        super().__init__(parent)
        self.adapter = adapter
        self.setWindowTitle(f'手动设置 IP - {adapter["name"]}')
        self.resize(420, 340)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title = StrongBodyLabel('IP 配置')
        title.setStyleSheet('font-size: 16px;')
        layout.addWidget(title)

        # 表单卡片
        card = CardWidget(self)
        card.setBorderRadius(8)
        form_layout = QFormLayout(card)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 适配器选择
        self.combo_adapter = ComboBox()
        self._all_adapters = get_adapters()
        for a in self._all_adapters:
            self.combo_adapter.addItem(a['name'])
        idx = self.combo_adapter.findText(adapter['name'])
        if idx >= 0:
            self.combo_adapter.setCurrentIndex(idx)
        self.combo_adapter.currentIndexChanged.connect(self._on_adapter_changed)
        form_layout.addRow('网络适配器:', self.combo_adapter)

        self.edit_ip = LineEdit(self)
        self.edit_ip.setText(preset_ip or adapter['ip'])
        self.edit_ip.setPlaceholderText('例如: 192.168.1.100')
        form_layout.addRow('IP 地址:', self.edit_ip)

        self.edit_mask = LineEdit(self)
        self.edit_mask.setText(adapter['mask'] or '255.255.255.0')
        self.edit_mask.setPlaceholderText('例如: 255.255.255.0')
        form_layout.addRow('子网掩码:', self.edit_mask)

        self.edit_gateway = LineEdit(self)
        self.edit_gateway.setText(adapter['gateway'] or '')
        self.edit_gateway.setPlaceholderText('留空则不设置网关')
        form_layout.addRow('默认网关:', self.edit_gateway)

        layout.addWidget(card)

        # 管理员提示
        if not is_admin():
            hint = BodyLabel('⚠ 需要管理员权限才能修改 IP，请以管理员身份运行程序')
            hint.setStyleSheet('color: #d0870a; padding: 4px 0;')
            layout.addWidget(hint)

        layout.addStretch()

        # 按钮
        btn_layout = QHBoxLayout()
        self.btn_apply = PrimaryPushButton(FIF.ACCEPT, '应用')
        self.btn_apply.clicked.connect(self._apply)
        self.btn_cancel = PushButton('取消')
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_apply)
        layout.addLayout(btn_layout)

    def _on_adapter_changed(self, index: int):
        """切换适配器时自动填入当前 IP/掩码/网关"""
        if 0 <= index < len(self._all_adapters):
            a = self._all_adapters[index]
            self.edit_ip.setText(a['ip'] or '')
            self.edit_mask.setText(a['mask'] or '')
            self.edit_gateway.setText(a['gateway'] or '')
            self.setWindowTitle(f'手动设置 IP - {a["name"]}')

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


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------
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
            return '切换静态IP插件 - 支持同网段可用IP扫描与手动配置'

    @hook
    def get_menu(self) -> list[dict]:
        menu = PluginMenu()
        menu.add_funcs([
            {'function': '📋 查看网络信息', 'object': self.show_network_info},
            {'function': '⬆ 向前扫描可用IP', 'object': self.scan_down},
            {'function': '⬇ 向后扫描可用IP', 'object': self.scan_up},
            {'function': '🔧 手动设置IP', 'object': self.manual_set_ip},
            {'function': '🔄 恢复DHCP', 'object': self.revert_dhcp},
        ])
        return menu.get_all()

    # ------------------------------------------------------------------
    # 菜单回调
    # ------------------------------------------------------------------
    @staticmethod
    def _is_virtual_adapter(name: str) -> bool:
        """判断是否为虚拟/隧道适配器"""
        keywords = ['tailscale', 'loopback', 'virtual', 'bluetooth',
                    'pseudo', 'tunnel', 'vmware', 'vbox', 'hyper-v',
                    'localhost']
        lower = name.lower()
        return any(k in lower for k in keywords)

    def _get_usable_adapter(self) -> dict | None:
        """获取可用适配器：
        1) 上次保存的首选（存在且有 IP）
        2) 物理适配器（有 IP+网关，非虚拟）
        3) 任意有 IP+网关 的适配器
        4) 任意有 IP 的适配器
        """
        preferred = _get_preferred_adapter_name()
        all_adapters = get_adapters()

        def has_ip(a):
            return bool(a['ip'])

        # 1) 首选项存在且可用
        if preferred:
            for a in all_adapters:
                if a['name'] == preferred and has_ip(a):
                    return a

        # 2) 物理适配器（有 IP+网关，非虚拟）
        for a in all_adapters:
            if a['ip'] and a['gateway'] and not self._is_virtual_adapter(a['name']):
                return a

        # 3) 任意有 IP+网关
        for a in all_adapters:
            if a['ip'] and a['gateway']:
                return a

        # 4) 任意有 IP
        for a in all_adapters:
            if has_ip(a):
                return a

        return all_adapters[0] if all_adapters else None

    def _get_adapter_safe(self) -> dict | None:
        adapter = self._get_usable_adapter()
        if not adapter:
            QMessageBox.warning(None, '未检测到网络',
                                '未检测到任何网络适配器，请确认网络连接正常。')
            self.sdk.logger_error('未检测到网络适配器')
        return adapter

    def show_network_info(self):
        dlg = NetworkInfoDialog()
        dlg.exec()

    def _adapter_picker(self, title: str) -> dict | None:
        """弹窗选适配器，返回 adapter dict 或 None"""
        sel = AdapterSelectDialog(title)
        if sel.exec() != QDialog.DialogCode.Accepted:
            return None
        return sel.selected_adapter()

    def _scan_with_adapter(self, direction: str):
        """先选适配器，再执行扫描"""
        adapter = self._adapter_picker(f'选择适配器 - {direction}')
        if not adapter or not adapter['ip'] or not adapter['mask']:
            return
        net = calc_network(adapter['ip'], adapter['mask'])
        if not net:
            InfoBar.warning(title='计算失败', content='无法计算子网范围', parent=None)
            return

        if '向后' in direction:
            ips = get_ips_above(adapter['ip'], net, count=50)
        else:
            ips = get_ips_below(adapter['ip'], net, count=50)

        if not ips:
            InfoBar.info(title='提示', content='已到达子网边界，没有更多 IP', parent=None)
            return

        dlg = ScanResultDialog(adapter, ips, f'{direction} (从 {adapter["ip"]})')
        dlg.exec()

    def scan_up(self):
        self._scan_with_adapter('向后扫描')

    def scan_down(self):
        self._scan_with_adapter('向前扫描')

    def manual_set_ip(self):
        adapter = self._get_usable_adapter()
        if not adapter:
            InfoBar.warning(title='无可用适配器', content='未检测到任何网络适配器', parent=None)
            return
        dlg = ManualIpDialog(adapter)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            preferred = dlg.combo_adapter.currentText()
            _set_preferred_adapter_name(preferred)
            InfoBar.success(title='IP 设置成功',
                            content=f'{preferred} 已设置为 {dlg.edit_ip.text()}',
                            parent=None, duration=3000)
            self.sdk.logger_info(f'静态IP设置成功: {preferred} -> {dlg.edit_ip.text()}')

    def revert_dhcp(self):
        adapter = self._adapter_picker('恢复 DHCP')
        if not adapter:
            return

        from qfluentwidgets import Dialog as FluentDialog
        confirm = FluentDialog(
            f'确定要将「{adapter["name"]}」恢复为 DHCP 自动获取 IP 吗？',
            f'当前 IP: {adapter["ip"] or "未设置"}',
            parent=None
        )
        if not confirm.exec():
            return

        ok, msg = set_dhcp(adapter['name'])
        if ok:
            _set_preferred_adapter_name(adapter['name'])
            InfoBar.success(title='DHCP 恢复成功', content=msg, parent=None, duration=3000)
            self.sdk.logger_info(f'DHCP 恢复成功: {adapter["name"]}')
        else:
            InfoBar.error(title='失败', content=msg, parent=None, duration=3000)
