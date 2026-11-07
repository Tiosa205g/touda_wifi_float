# 汕大协同办公系统(OA)通知公告查看插件
# 数据来源: http://oa.stu.edu.cn/csweb/list.jsp （公开通知栏，无需登录）
import re
import html
import time
import webbrowser
import requests
import tomlkit
import pluggy
from pathlib import Path

from plugin_sdk import (
    PluginSDK, PluginMenu, get_notifier,
    install_row_hover, install_widget_row_hover,
)

from PySide6.QtCore import Qt, QObject, QTimer
from PySide6.QtGui import QColor, QFont, QBrush
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QPlainTextEdit,
)
from qfluentwidgets import (
    PushButton, PrimaryPushButton, ToolButton, ComboBox,
    BodyLabel, CaptionLabel, StrongBodyLabel, FluentIcon as FIF,
)

from ui.components.frameless_dialog import (
    FramelessDialog, _position_dialog, _theme_colors,
)
from src.touda import start_worker_in_thread, get_vpn_url

PLUGIN_NAME = 'OA通知查看'
PLUGIN_VERSION = '1.0.0'
PLUGIN_AUTHOR = 'tiosa'
PLUGIN_PATH = Path(__file__).parent
PLUGIN_CFG = PLUGIN_PATH / 'config.toml'

# 使用与主程序一致的标识
hook = pluggy.HookimplMarker("toudawifi")  # 不能变动

OA_BASE = 'http://oa.stu.edu.cn'
OA_LIST_URL = OA_BASE + '/csweb/list.jsp'
# 详情页路径（docid 可变），最终展示用直连地址
OA_DETAIL_FMT = (OA_BASE + '/page/maint/template/news/'
                 'newstemplateprotal.jsp?templatetype=1&templateid=3&docid={}')
# 附件下载地址（泛微 e-cology FileDownload）
OA_FILE_DL_FMT = (OA_BASE + '/weaver/weaver.file.FileDownload'
                  '?fileid={}&download=1&requestid=0')

DEFAULT_PAGESIZE = 20
DEFAULT_POLL_MINUTES = 10
NOTIFY_LOG_MAX = 20

# 行解析：标题(完整内容在 title 属性) + 发布单位 + 发布日期
# 兼容 WebVPN 重写后的绝对 URL，只依赖 docid 还原详情链接
_ROW_RE = re.compile(
    r"href\s*=\s*['\"]([^'\"]*newstemplateprotal\.jsp\?[^'\"]*)['\"]"
    r"[^>]*title\s*=\s*['\"](?P<title>[^'\"]*)['\"].*?"
    r'<TD width="20%" align="center">(?P<dept>[^<]*)</TD>\s*'
    r'<TD width="20%" align="center">(?P<date>[^<]*)</TD>',
    re.S,
)
_DOCID_RE = re.compile(r'docid=(\d+)')
_DEPTS_RE = re.compile(r'<select[^>]*name\s*=\s*"fwdw".*?>(.*?)</select>', re.S)
_OPT_RE = re.compile(r'<option\s+value="([^"]*)"[^>]*>([^<]*)</option>')
# 附件行：<img ...>文件名<input type=hidden name=accessoryN value='fileid'>
_ATT_RE = re.compile(
    r"<img[^>]*>\s*(?P<name>[^<>]+?)\s*"
    r"<input[^>]*name\s*=\s*accessory\d+[^>]*value\s*=\s*'(?P<fid>\d+)'",
    re.I | re.S)


# =========================================================================
# 插件配置（config.toml）
# =========================================================================
def _load_cfg() -> dict:
    try:
        with open(PLUGIN_CFG, 'r', encoding='utf-8') as f:
            return tomlkit.load(f)
    except Exception:
        return {}


def _save_cfg(data):
    PLUGIN_CFG.parent.mkdir(parents=True, exist_ok=True)
    with open(PLUGIN_CFG, 'w', encoding='utf-8') as f:
        tomlkit.dump(data, f)


def _get_cfg(section: str, option: str, default=None):
    try:
        return _load_cfg()[section][option]
    except Exception:
        return default


def _set_cfg(section: str, option: str, value):
    cfg = _load_cfg()
    if section not in cfg:
        cfg[section] = {}
    cfg[section][option] = value
    _save_cfg(cfg)


def _get_watermark() -> int:
    try:
        return int(_get_cfg('notice', 'watermark_docid', 0))
    except Exception:
        return 0


def _set_watermark(v: int):
    _set_cfg('notice', 'watermark_docid', int(v))


def _get_pagesize() -> int:
    try:
        v = int(_get_cfg('notice', 'pagesize', DEFAULT_PAGESIZE))
        return v if v > 0 else DEFAULT_PAGESIZE
    except Exception:
        return DEFAULT_PAGESIZE


def _get_poll_minutes() -> int:
    try:
        v = int(_get_cfg('notice', 'poll_minutes', DEFAULT_POLL_MINUTES))
        return v if v >= 0 else DEFAULT_POLL_MINUTES
    except Exception:
        return DEFAULT_POLL_MINUTES


def _get_notified() -> int:
    """已提醒水位（docid）：仅用于定时提醒去重，与“已读水位”独立"""
    try:
        return int(_get_cfg('notice', 'notified_docid', 0))
    except Exception:
        return 0


def _set_notified(v: int):
    _set_cfg('notice', 'notified_docid', int(v))


def _load_notify_log() -> list:
    import json
    try:
        return json.loads(str(_get_cfg('notify', 'log_json', '[]') or '[]'))
    except Exception:
        return []


def _append_notify_log(entries: list):
    import json
    log = _load_notify_log()
    log = list(log) + list(entries)
    log = log[-NOTIFY_LOG_MAX:]
    _set_cfg('notify', 'log_json', json.dumps(log, ensure_ascii=False))


def _html_to_text(html_str: str) -> str:
    """HTML 转纯文本（详情正文展示用）"""
    s = html_str or ''
    s = re.sub(r'(?s)<!--.*?-->', '', s)              # Word 条件注释等
    s = re.sub(r'(?is)<(script|style|xml)[^>]*>.*?</\1>', '', s)
    s = re.sub(r'(?i)<br\s*/?>', '\n', s)
    s = re.sub(r'(?i)</(p|div|tr|li|h[1-6]|table)>', '\n', s)
    s = re.sub(r'(?i)</t[dh]>', '\t', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)
    s = re.sub(r'[ \t]+\n', '\n', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


# =========================================================================
# OA 数据层：列表抓取与解析
# =========================================================================
class OAFetchError(Exception):
    pass


class OAClient:
    """OA 公开通知栏客户端

    访问策略（三级回退）：
      1. 直连（绕过系统代理，校园网直连最快最稳）
      2. 系统代理（部分代理环境下内网走代理可达）
      3. WebVPN 代理（校外访问兜底，需要 webvpn 已登录）
    """

    def __init__(self, webvpn=None):
        self.webvpn = webvpn

    # ---- 请求 ----

    def _post_direct(self, data, trust_env: bool, timeout) -> str:
        s = requests.Session()
        s.trust_env = trust_env
        s.verify = False
        r = s.post(OA_LIST_URL, data=data, timeout=timeout)
        if r.status_code != 200:
            raise OAFetchError(f'HTTP {r.status_code}')
        return r.content.decode('gbk', errors='replace')

    def _post_webvpn(self, data, timeout) -> str:
        if self.webvpn is None:
            raise OAFetchError('未初始化 webvpn')
        self.webvpn.autoLogin()
        if not self.webvpn.twfid:
            raise OAFetchError('WebVPN 未登录')
        s = requests.Session()
        s.trust_env = False
        s.verify = False
        s.cookies.update({'TWFID': self.webvpn.twfid})
        r = s.post(get_vpn_url(OA_LIST_URL), data=data, timeout=timeout)
        if r.status_code != 200:
            raise OAFetchError(f'WebVPN HTTP {r.status_code}')
        return r.content.decode('gbk', errors='replace')

    def _post(self, data) -> str:
        errors = []
        for label, fn in (
            ('直连', lambda: self._post_direct(data, False, (3, 10))),
            ('代理', lambda: self._post_direct(data, True, (3, 10))),
            ('WebVPN', lambda: self._post_webvpn(data, (3, 15))),
        ):
            try:
                return fn()
            except Exception as e:
                errors.append(f'{label}: {e}')
        raise OAFetchError('; '.join(errors))

    def _get_direct(self, url, trust_env: bool, timeout) -> bytes:
        s = requests.Session()
        s.trust_env = trust_env
        s.verify = False
        r = s.get(url, timeout=timeout)
        if r.status_code != 200:
            raise OAFetchError(f'HTTP {r.status_code}')
        return r.content

    def _get_webvpn(self, url, timeout) -> bytes:
        if self.webvpn is None:
            raise OAFetchError('未初始化 webvpn')
        self.webvpn.autoLogin()
        if not self.webvpn.twfid:
            raise OAFetchError('WebVPN 未登录')
        s = requests.Session()
        s.trust_env = False
        s.verify = False
        s.cookies.update({'TWFID': self.webvpn.twfid})
        r = s.get(get_vpn_url(url), timeout=timeout)
        if r.status_code != 200:
            raise OAFetchError(f'WebVPN HTTP {r.status_code}')
        return r.content

    def _get(self, url: str) -> bytes:
        errors = []
        for label, fn in (
            ('直连', lambda: self._get_direct(url, False, (3, 15))),
            ('代理', lambda: self._get_direct(url, True, (3, 15))),
            ('WebVPN', lambda: self._get_webvpn(url, (3, 20))),
        ):
            try:
                return fn()
            except Exception as e:
                errors.append(f'{label}: {e}')
        raise OAFetchError('; '.join(errors))

    # ---- 解析 ----

    @staticmethod
    def _parse_page(text: str) -> dict:
        rows = []
        for m in _ROW_RE.finditer(text):
            path = m.group(1)
            dm = _DOCID_RE.search(path)
            if not dm:
                continue
            rows.append({
                'docid': int(dm.group(1)),
                'title': html.unescape(m.group('title')).strip(),
                'dept': html.unescape(m.group('dept')).strip(),
                'date': html.unescape(m.group('date')).strip(),
            })

        def _hidden(name):
            m = re.search(rf'name\s*=\s*"{name}"[^>]*value\s*=\s*"([^"]*)"', text)
            return m.group(1) if m else ''

        try:
            total_count = int(_hidden('totalcount') or 0)
        except ValueError:
            total_count = 0
        try:
            total_pages = int(_hidden('totalindex') or 0)
        except ValueError:
            total_pages = 0

        depts = []
        dm = _DEPTS_RE.search(text)
        if dm:
            for om in _OPT_RE.finditer(dm.group(1)):
                depts.append((om.group(1), html.unescape(om.group(2)).strip()))

        return {
            'rows': rows,
            'total_count': total_count,
            'total_pages': max(total_pages, 1),
            'depts': depts,
        }

    # ---- 对外接口 ----

    def fetch_page(self, page: int = 1, fwdw: str = '-1',
                   pagesize: int = DEFAULT_PAGESIZE) -> dict:
        data = {
            'pageindex': max(int(page), 1),
            'pagesize': int(pagesize),
            'totalcount': 0,
            'totalindex': 0,
            'keyword': '',
            'fwdw': str(fwdw),
        }
        return self._parse_page(self._post(data))

    @staticmethod
    def _parse_detail(text: str, docid: int) -> dict:
        """解析详情页：标题 / 正文纯文本 / 附件清单"""
        inner = text
        m = re.search(r'id\s*=\s*"spanContent"[^>]*>(.*)', text, re.S | re.I)
        if m:
            inner = m.group(1)

        title = ''
        tm = re.search(r'<title>(.*?)</title>', inner, re.S | re.I)
        if tm:
            title = html.unescape(re.sub(r'\s+', ' ', tm.group(1))).strip()

        body_html = ''
        bm = re.search(r'<body[^>]*>(.*)</body>', inner, re.S | re.I)
        if bm:
            body_html = bm.group(1)
        else:
            body_html = inner

        attachments = []
        seen = set()
        for am in _ATT_RE.finditer(text):
            name = html.unescape(am.group('name')).strip()
            fid = am.group('fid')
            if not name or not fid or fid in seen:
                continue
            seen.add(fid)
            attachments.append({
                'fileid': int(fid),
                'filename': name,
                'url': OA_FILE_DL_FMT.format(fid),
            })

        # 正文里剔除附件表（附件单独列表展示）
        if attachments and '相关附件' in body_html:
            body_html = body_html.split('相关附件')[0]

        return {
            'docid': int(docid),
            'title': title,
            'text': _html_to_text(body_html),
            'attachments': attachments,
        }

    def fetch_detail(self, docid: int) -> dict:
        """抓取并解析通知详情（正文 + 附件清单）"""
        raw = self._get(OA_DETAIL_FMT.format(int(docid)))
        return self._parse_detail(raw.decode('gbk', errors='replace'), int(docid))

    def download_attachment(self, fileid: int) -> bytes:
        """下载附件原始字节"""
        return self._get(OA_FILE_DL_FMT.format(int(fileid)))


# =========================================================================
# 后台任务结果回流（Plugin 不是 QObject，需显式排队回主线程）
# =========================================================================
class _Job(QObject):
    """将后台结果排队回主线程执行回调（QObject 绑定槽 → 自动 QueuedConnection）"""
    def __init__(self, cb):
        super().__init__()
        self._cb = cb

    def on_done(self, result):
        cb, self._cb = self._cb, None
        try:
            if cb is not None:
                cb(result)
        finally:
            self.deleteLater()


# start_worker_in_thread 返回的 QThread/Worker 必须被持有引用，
# 否则函数一返回就被 GC，运行中的 QThread 被销毁会直接崩进程
_BG_REFS = set()


def _keep_bg_ref(*objs):
    key = tuple(objs)
    _BG_REFS.add(key)
    first = objs[0]
    first.finished.connect(lambda _=None, r=key: _BG_REFS.discard(r))


# =========================================================================
# 通知列表对话框
# =========================================================================
class NoticeViewerDialog(FramelessDialog):
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self._closed = False
        self._loading = False
        self._requested_page = 1
        self._pending_goto = None
        self._page = 1
        self._total_pages = 1
        self._total_count = 0
        self._fwdw = '-1'
        self._pagesize = _get_pagesize()
        self._depts = [('-1', '全部')]
        self._watermark = _get_watermark()

        self.setWindowTitle(PLUGIN_NAME)
        self._title_label.setText('汕大OA通知公告')
        self.resize(680, 560)
        _position_dialog(self, parent)

        bg, text, sec, border = _theme_colors()

        # ── 工具行：发布单位筛选 + 刷新 ──
        bar = QWidget(self._outer)
        bar.setStyleSheet('background: transparent;')
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)

        lbl = BodyLabel('发布单位:', bar)
        lbl.setStyleSheet(f'color: {text}; background: transparent;')
        bl.addWidget(lbl)

        self.combo_dept = ComboBox(bar)
        self.combo_dept.setFixedWidth(180)
        self.combo_dept.currentIndexChanged.connect(self._on_dept_changed)
        bl.addWidget(self.combo_dept)

        bl.addStretch(1)

        self.btn_refresh = ToolButton(FIF.SYNC, bar)
        self.btn_refresh.setToolTip('刷新')
        self.btn_refresh.clicked.connect(lambda *_: self.reload())
        bl.addWidget(self.btn_refresh)
        self.add_content(bar, 0)

        # ── 表格 ──
        self.table = QTableWidget(0, 3, self._outer)
        self.table.setHorizontalHeaderLabels(['标题', '发布单位', '发布日期'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setStyleSheet(self._table_style())
        # 整行悬停高亮（替代 QSS 单格 ::item:hover）
        install_row_hover(self.table)
        self.table.itemDoubleClicked.connect(lambda *_: self.open_selected())
        self.add_content(self.table, 1)

        hint = CaptionLabel('💡 双击行打开通知详情；红色为未读新通知', self._outer)
        hint.setStyleSheet(f'color: {sec}; background: transparent;')
        self.add_content(hint, 0)

        # ── 按钮行 ──
        self.btn_prev = PushButton(FIF.UP, '上一页', self._outer)
        self.btn_prev.clicked.connect(lambda *_: self.goto(self._page - 1))
        self.btn_next = PushButton(FIF.DOWN, '下一页', self._outer)
        self.btn_next.clicked.connect(lambda *_: self.goto(self._page + 1))
        self.btn_read = PushButton(FIF.ACCEPT, '全部标为已读', self._outer)
        self.btn_read.clicked.connect(lambda *_: self.mark_read())
        self.btn_open = PrimaryPushButton(FIF.LINK, '打开详情', self._outer)
        self.btn_open.clicked.connect(lambda *_: self.open_selected())
        btn_close = PushButton('关闭', self._outer)
        btn_close.clicked.connect(self.reject)
        self.add_buttons(self.btn_prev, self.btn_next, self.btn_read,
                         self.btn_open, btn_close)

        self.status_label = CaptionLabel('加载中…', self._outer)
        self.status_label.setStyleSheet(f'color: {sec}; background: transparent;')
        self.add_content(self.status_label, 0)

        self.reload()

    # ── 主题 ──

    def _table_style(self) -> str:
        bg, text, sec, border = _theme_colors()
        try:
            from qfluentwidgets import isDarkTheme
            dark = isDarkTheme()
        except Exception:
            dark = False
        if dark:
            return f"""
                QTableWidget {{
                    background: #252525; color: {text};
                    border: 1px solid {border}; border-radius: 6px;
                    gridline-color: #333;
                }}
                QTableWidget::item:selected {{ background: #2B88D8; color: white; }}
                QHeaderView::section {{
                    background: #1e1e1e; color: #90CAF9; border: none;
                    padding: 6px; font-weight: bold;
                }}
            """
        return f"""
            QTableWidget {{
                background: #ffffff; color: {text};
                border: 1px solid {border}; border-radius: 6px;
                gridline-color: #e8f0fe;
            }}
            QTableWidget::item:selected {{ background: #0078D4; color: white; }}
            QHeaderView::section {{
                background: #f0f6ff; color: #0078D4; border: none;
                padding: 6px; font-weight: bold;
            }}
        """

    # ── 关闭保护 ──

    def reject(self):
        self._closed = True
        super().reject()

    def accept(self):
        self._closed = True
        super().accept()

    # ── 数据加载 ─-

    def reload(self):
        self.goto(self._page)

    def goto(self, page: int):
        page = max(int(page), 1)
        if self._total_pages and page > self._total_pages:
            page = self._total_pages
        if self._loading:
            # 加载中：记录为待办请求，当前请求完成后自动继续
            self._pending_goto = (page, self._fwdw)
            return
        self._page = page
        self._loading = True
        self._requested_page = page
        self._set_status(f'加载第 {page} 页…')
        self._set_paging_enabled(False)

        plugin = self.plugin
        fwdw = self._fwdw
        pagesize = self._pagesize

        def job():
            return plugin.client.fetch_page(page, fwdw, pagesize)

        # 只能连接 QObject 绑定槽（跨线程自动排队回主线程），
        # 绝不能传普通闭包——否则回调跑在工作线程里操作 UI 会直接崩
        th, wk = start_worker_in_thread(job, 'oa_notice', self._on_loaded)
        _keep_bg_ref(th, wk)

    def _on_loaded(self, result):
        if self._closed:
            return
        self._loading = False

        if isinstance(result, Exception):
            self._set_paging_enabled(True)
            self._set_status(f'加载失败: {result}')
            return

        rows = result.get('rows', [])
        self._total_pages = max(int(result.get('total_pages') or 1), 1)
        self._total_count = int(result.get('total_count') or 0)

        # 发布单位下拉：保留当前选择
        depts = result.get('depts') or []
        if depts:
            self._depts = [('-1', '全部')] + [d for d in depts if d[0] != '-1']
            self._fill_depts()

        # 首次运行建立基线水位，避免全部标红
        if self._watermark <= 0 and rows:
            self._watermark = max(r['docid'] for r in rows)
            _set_watermark(self._watermark)

        self._fill_table(rows)
        self._page = self._requested_page
        self._set_status(
            f'第 {self._page} / {self._total_pages} 页 · 共 {self._total_count} 条')
        self._set_paging_enabled(True)

        # 处理加载期间积累的翻页/筛选请求
        pending = self._pending_goto
        self._pending_goto = None
        if pending:
            self._fwdw = pending[1]
            self.goto(pending[0])

    def _fill_depts(self):
        current = self._fwdw
        self.combo_dept.blockSignals(True)
        self.combo_dept.clear()
        idx = 0
        for i, (value, label) in enumerate(self._depts):
            self.combo_dept.addItem(label)
            if value == current:
                idx = i
        self.combo_dept.setCurrentIndex(idx)
        self.combo_dept.blockSignals(False)

    def _fill_table(self, rows):
        self.table.setRowCount(0)
        wm = self._watermark
        # 新通知红色随主题（深色用亮红，与邮箱插件一致）
        try:
            from qfluentwidgets import isDarkTheme
            new_color = QColor('#ff7d7d' if isDarkTheme() else '#e05252')
        except Exception:
            new_color = QColor('#e05252')
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            is_new = int(row['docid']) > wm

            title_item = QTableWidgetItem(row['title'])
            title_item.setData(Qt.UserRole, row['docid'])
            if is_new:
                title_item.setForeground(new_color)
                f = QFont()
                f.setBold(True)
                title_item.setFont(f)
            self.table.setItem(r, 0, title_item)
            self.table.setItem(r, 1, QTableWidgetItem(row['dept']))
            self.table.setItem(r, 2, QTableWidgetItem(row['date']))

        if rows:
            self.table.selectRow(0)

    def _set_status(self, msg: str):
        try:
            self.status_label.setText(msg)
        except RuntimeError:
            pass

    def _set_paging_enabled(self, enabled: bool):
        try:
            self.btn_prev.setEnabled(enabled and self._page > 1)
            self.btn_next.setEnabled(enabled and self._page < self._total_pages)
        except RuntimeError:
            pass

    def _on_dept_changed(self, index: int):
        if 0 <= index < len(self._depts):
            self._fwdw = self._depts[index][0]
        self._page = 1
        self.reload()

    # ── 操作 ──

    def _selected_docid(self) -> int | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _mark_item_read(self, docid: int):
        """标记单条通知已读：推进水位 + 取消该行红色加粗"""
        if not docid or int(docid) <= self._watermark:
            return
        self._watermark = int(docid)
        _set_watermark(self._watermark)
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item is None:
                continue
            v = item.data(Qt.UserRole)
            if v and int(v) <= self._watermark:
                item.setForeground(QBrush())
                item.setFont(QFont())

    def mark_read(self):
        docids = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item is not None:
                v = item.data(Qt.UserRole)
                if v:
                    docids.append(int(v))
        if docids:
            self._watermark = max(self._watermark, max(docids))
            _set_watermark(self._watermark)
            self._fill_table([
                {
                    'docid': self.table.item(r, 0).data(Qt.UserRole),
                    'title': self.table.item(r, 0).text(),
                    'dept': self.table.item(r, 1).text(),
                    'date': self.table.item(r, 2).text(),
                }
                for r in range(self.table.rowCount())
            ])
        self._set_status(f'已标记已读（水位 docid={self._watermark}）')

    def open_selected(self):
        docid = self._selected_docid()
        if docid is None:
            self.plugin.sdk.show_message('提示', '请先选中一条通知')
            return
        meta = {'docid': int(docid)}
        rows = (self.table.selectionModel().selectedRows()
                if self.table.selectionModel() else [])
        if rows:
            r = rows[0].row()
            for key, col in (('title', 0), ('dept', 1), ('date', 2)):
                it = self.table.item(r, col)
                if it is not None:
                    meta[key] = it.text()
        # 双击打开即自动标记已读
        self._mark_item_read(int(docid))
        self.plugin.open_notice_detail(docid, parent=self, meta=meta)


# =========================================================================
# 通知详情对话框（正文 + 附件列表下载 + 跳转原页面）
# =========================================================================
class NoticeDetailDialog(FramelessDialog):
    def __init__(self, plugin, item: dict, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.item = dict(item or {})
        self.docid = int(self.item.get('docid') or 0)
        self._closed = False
        self._detail = None
        self._dl_state = {}  # fileid -> {'btn': btn, 'path': path}

        self.setWindowTitle(PLUGIN_NAME)
        self._title_label.setText('通知详情')
        self.resize(680, 580)
        _position_dialog(self, parent)

        bg, text, sec, border = _theme_colors()

        # ── 标题与元信息 ──
        self.head_label = StrongBodyLabel(
            self.item.get('title') or f'通知 #{self.docid}', self._outer)
        self.head_label.setWordWrap(True)
        self.head_label.setStyleSheet(f'color: {text}; background: transparent;')
        self.add_content(self.head_label, 0)

        meta = '  ·  '.join(
            x for x in (self.item.get('dept'), self.item.get('date')) if x)
        self.meta_label = CaptionLabel(meta or '加载中…', self._outer)
        self.meta_label.setStyleSheet(f'color: {sec}; background: transparent;')
        self.add_content(self.meta_label, 0)

        # ── 正文 ──
        self.body_view = QPlainTextEdit(self._outer)
        self.body_view.setReadOnly(True)
        self.body_view.setPlaceholderText('正文加载中…')
        self.body_view.setStyleSheet(
            f'QPlainTextEdit {{ background: {bg}; color: {text};'
            f' border: 1px solid {border}; border-radius: 6px; padding: 8px;'
            f' font-size: 13px; }}')
        self.add_content(self.body_view, 3)

        # ── 附件区 ──
        self.att_label = CaptionLabel('附件加载中…', self._outer)
        self.att_label.setStyleSheet(f'color: {sec}; background: transparent;')
        self.add_content(self.att_label, 0)

        self.att_box = QWidget(self._outer)
        self.att_box.setStyleSheet('background: transparent;')
        self.att_layout = QVBoxLayout(self.att_box)
        self.att_layout.setContentsMargins(0, 0, 0, 0)
        self.att_layout.setSpacing(4)
        self.add_content(self.att_box, 0)

        self.status_label = CaptionLabel('', self._outer)
        self.status_label.setStyleSheet(f'color: {sec}; background: transparent;')
        self.add_content(self.status_label, 0)

        # ── 按钮 ──
        btn_open = PushButton(FIF.GLOBE, '打开原页面', self._outer)
        btn_open.clicked.connect(self.open_original)
        btn_close = PushButton('关闭', self._outer)
        btn_close.clicked.connect(self.reject)
        self.add_buttons(btn_close, btn_open)

        self._load()

    # ── 关闭保护 ──

    def reject(self):
        self._closed = True
        super().reject()

    def accept(self):
        self._closed = True
        super().accept()

    # ── 数据加载 ──

    def _load(self):
        plugin = self.plugin
        docid = self.docid

        def job():
            return plugin.client.fetch_detail(docid)

        # 回调必须是 QObject 绑定槽（跨线程自动排队回主线程）
        th, wk = start_worker_in_thread(job, 'oa_detail', self._on_loaded)
        _keep_bg_ref(th, wk)

    def _on_loaded(self, result):
        if self._closed:
            return
        if isinstance(result, Exception):
            self.body_view.setPlainText(f'加载失败：{result}')
            self.meta_label.setText('加载失败')
            self.att_label.setText('附件不可用')
            return

        self._detail = result
        if result.get('title'):
            self.head_label.setText(result['title'])
        if not self.meta_label.text() or self.meta_label.text() == '加载中…':
            self.meta_label.setText(f'通知 #{self.docid}')

        self.body_view.setPlainText(result.get('text') or '（正文为空）')
        self._fill_attachments(result.get('attachments') or [])

    def _fill_attachments(self, atts: list):
        # 清空旧的行
        while self.att_layout.count():
            item = self.att_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        if not atts:
            self.att_label.setText('无附件')
            return
        self.att_label.setText(f'附件（{len(atts)}）：')

        bg, text, sec, border = _theme_colors()
        for att in atts:
            row = QWidget(self.att_box)
            row.setStyleSheet('background: transparent;')
            hl = QHBoxLayout(row)
            hl.setContentsMargins(8, 2, 8, 2)
            hl.setSpacing(8)

            name = CaptionLabel(f"📎 {att['filename']}", row)
            name.setStyleSheet(f'color: {text}; background: transparent;')
            name.setToolTip(att['filename'])
            hl.addWidget(name, 1)

            btn = PushButton(FIF.SAVE, '下载', row)
            btn.setFixedWidth(90)
            btn.clicked.connect(
                lambda _=False, a=att, b=btn: self.download_att(a, b))
            hl.addWidget(btn)
            self.att_layout.addWidget(row)
            # 整行悬停（悬停行内任意位置含按钮都高亮）
            install_widget_row_hover(row)

    # ── 附件下载 ──

    def download_att(self, att: dict, btn):
        from PySide6.QtWidgets import QFileDialog
        fname = re.sub(r'[\\/:*?"<>|]', '_', str(
            att.get('filename') or f"attachment_{att['fileid']}"))
        path, _ = QFileDialog.getSaveFileName(self, '保存附件', fname)
        if not path:
            return

        fid = int(att['fileid'])
        self._dl_state[fid] = {'btn': btn, 'path': path}
        btn.setEnabled(False)
        self._set_status(f"正在下载 {att.get('filename', '')}…")

        plugin = self.plugin

        def job():
            data = plugin.client.download_attachment(fid)
            with open(path, 'wb') as f:
                f.write(data)
            return {'fileid': fid, 'path': path}

        # 回调必须是 QObject 绑定槽
        th, wk = start_worker_in_thread(job, 'oa_dl', self._on_dl_done)
        _keep_bg_ref(th, wk)

    def _on_dl_done(self, result):
        if self._closed:
            return
        if isinstance(result, Exception):
            self._set_status(f'下载失败: {result}')
        else:
            self._set_status(f"已保存到 {result.get('path', '')}")
        fid = None if isinstance(result, Exception) else result.get('fileid')
        st = self._dl_state.pop(fid, None) if fid is not None else None
        if st and st.get('btn') is not None:
            try:
                st['btn'].setEnabled(True)
            except RuntimeError:
                pass

    def _set_status(self, msg: str):
        try:
            self.status_label.setText(msg)
        except RuntimeError:
            pass

    # ── 跳转原页面 ──

    def open_original(self):
        use_vpn = FramelessDialog.show_confirm(
            '打开原页面',
            '是否使用 WebVPN 打开原页面？\n校内直连选「取消」，校外访问选「确定」',
            self,
        )
        url = OA_DETAIL_FMT.format(self.docid)
        if use_vpn:
            try:
                self.plugin.api.webvpn.autoLogin()
                url = self.plugin.api.webvpn.create_url(url)
            except Exception as e:
                self.plugin.sdk.logger_error(f'WebVPN 打开失败，改用直连: {e}')
        webbrowser.open(url)


# =========================================================================
# 设置对话框
# =========================================================================
class SettingDialog(FramelessDialog):
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle('OA通知查看 设置')
        self._title_label.setText('OA通知查看 设置')
        self.resize(452, 360)
        _position_dialog(self, parent)

        bg, text, sec, border = _theme_colors()

        body = QWidget(self._outer)
        body.setStyleSheet('background: transparent;')
        vl = QVBoxLayout(body)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(12)

        row = QWidget(body)
        row.setStyleSheet('background: transparent;')
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        lbl = BodyLabel('每页条数:', row)
        lbl.setStyleSheet(f'color: {text}; background: transparent;')
        hl.addWidget(lbl)
        self.combo_pagesize = ComboBox(row)
        for n in (10, 20, 50):
            self.combo_pagesize.addItem(str(n))
        cur = str(_get_pagesize())
        idx = self.combo_pagesize.findText(cur)
        self.combo_pagesize.setCurrentIndex(idx if idx >= 0 else 1)
        hl.addWidget(self.combo_pagesize)
        hl.addStretch(1)
        vl.addWidget(row)

        row2 = QWidget(body)
        row2.setStyleSheet('background: transparent;')
        hl2 = QHBoxLayout(row2)
        hl2.setContentsMargins(0, 0, 0, 0)
        lbl2 = BodyLabel('新通知自动检查间隔:', row2)
        lbl2.setStyleSheet(f'color: {text}; background: transparent;')
        hl2.addWidget(lbl2)
        self.combo_poll = ComboBox(row2)
        for label in ('关闭', '5 分钟', '10 分钟', '30 分钟', '60 分钟'):
            self.combo_poll.addItem(label)
        self.combo_poll.setCurrentIndex(self._poll_index(_get_poll_minutes()))
        hl2.addWidget(self.combo_poll)
        hl2.addStretch(1)
        vl.addWidget(row2)

        self.btn_reset = PushButton(FIF.DELETE, '重置“新通知”标记', body)
        self.btn_reset.clicked.connect(self._reset_watermark)
        vl.addWidget(self.btn_reset)

        tip = CaptionLabel('重置后所有通知将重新标记为新', body)
        tip.setStyleSheet(f'color: {sec}; background: transparent;')
        vl.addWidget(tip)
        vl.addStretch(1)

        self.add_content(body, 1)

        btn_save = PrimaryPushButton(FIF.SAVE, '保存', self._outer)
        btn_save.clicked.connect(self._save)
        btn_cancel = PushButton('取消', self._outer)
        btn_cancel.clicked.connect(self.reject)
        self.add_buttons(btn_cancel, btn_save)

    def _reset_watermark(self):
        _set_watermark(0)
        self.plugin.sdk.logger_info('新通知水位已重置')

    @staticmethod
    def _poll_index(minutes: int) -> int:
        mapping = {0: 0, 5: 1, 10: 2, 30: 3, 60: 4}
        return mapping.get(minutes, 2)

    @staticmethod
    def _poll_minutes(index: int) -> int:
        mapping = {0: 0, 1: 5, 2: 10, 3: 30, 4: 60}
        return mapping.get(index, 10)

    def _save(self):
        try:
            _set_cfg('notice', 'pagesize', int(self.combo_pagesize.currentText()))
            _set_cfg('notice', 'poll_minutes',
                     self._poll_minutes(self.combo_poll.currentIndex()))
        except Exception as e:
            self.plugin.sdk.logger_error(f'保存设置失败: {e}')
        self.plugin.apply_settings()
        self.accept()


# =========================================================================
# Plugin
# =========================================================================
class Plugin:  # 类名固定为 Plugin，不能变动，否则无法识别
    @hook
    def start(self, api) -> bool:
        """插件加载时执行,传api包含已实例化的wifi和webvpn类"""
        self.api = api
        self.sdk = PluginSDK(api, PLUGIN_NAME)
        self.client = OAClient(api.webvpn)
        self._polling = False
        self._new_count = 0

        # Windows 通知中枢（点击通知可追溯到内容）
        self.notifier = get_notifier()
        self.notifier.bind(api)

        # 新通知定时检查
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll_tick)
        self.apply_settings()
        # 软件打开时立即检查一次（自动检查开启时），不等首个轮询周期；
        # 延迟 3 秒让界面与校园网登录先起步
        if _get_poll_minutes() > 0:
            QTimer.singleShot(3000, self._poll_tick)

        self.sdk.logger_info('插件已加载')
        return True  # 返回true才会视为有效插件

    @hook
    def on_disable(self):
        try:
            self._timer.stop()
        except Exception:
            pass
        self.sdk.logger_info(f'{PLUGIN_NAME}禁用')

    @hook
    def get_name(self) -> str:
        """获取插件名字"""
        return PLUGIN_NAME

    @hook
    def get_description(self) -> str:
        """获取插件描述,支持markdown"""
        try:
            with open(PLUGIN_PATH / 'readme.md', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.sdk.logger_error(f'出错啦:{e}')

    @hook
    def get_menu(self) -> list[dict]:
        """获取插件的菜单信息"""
        title = '📋 查看OA通知公告'
        if self._new_count > 0:
            title = f'📋 查看OA通知公告（{self._new_count} 新）'
        menu = PluginMenu()
        menu.add_funcs([
            {'function': title, 'object': self.show_viewer},
            {'function': '⚙️ 设置', 'object': self.on_setting},
        ])
        return menu.get_all()

    @hook
    def on_setting(self):
        """当设置按钮被点击"""
        try:
            SettingDialog(self).exec()
        except Exception as e:
            self.sdk.logger_error(f'打开设置失败: {e}')

    # ── 后台任务（Plugin 非 QObject，用 _Job 排队回主线程） ──

    def _run_bg(self, fn, name: str, callback):
        job = _Job(callback)
        th, wk = start_worker_in_thread(fn, name, job.on_done)
        _keep_bg_ref(th, wk, job)

    # ── 定时检查新通知 ──

    def apply_settings(self):
        """应用配置（重启检查定时器）"""
        minutes = _get_poll_minutes()
        self._timer.stop()
        if minutes > 0:
            self._timer.start(minutes * 60 * 1000)

    def _poll_tick(self):
        if self._polling:
            return
        self._polling = True

        def job():
            return self.client.fetch_page(1, '-1', _get_pagesize())

        def done(result):
            self._polling = False
            if isinstance(result, Exception):
                self.sdk.logger_error(f'自动检查新通知失败: {result}')
                return
            rows = result.get('rows', [])
            if not rows:
                return
            latest = max(int(r['docid']) for r in rows)

            notified = _get_notified()
            if notified <= 0:
                # 首次：建立提醒基线，不打扰用户（已读水位同时兜底）
                _set_notified(latest)
                if _get_watermark() <= 0:
                    _set_watermark(latest)
                return

            new_rows = [r for r in rows if int(r['docid']) > notified]
            if not new_rows:
                self._new_count = 0
                return
            _set_notified(latest)
            self._new_count = len(new_rows)
            self._show_notify(new_rows)

        self._run_bg(job, 'oa_poll', done)

    def _show_notify(self, new_rows: list):
        """新通知 → 通知弹窗（点击直达 OA 通知列表，不标记已读）"""
        log_entries = []
        for r in new_rows[:8]:
            label = r.get('title') or '(无标题)'
            sub = f"{r.get('dept', '')}  {r.get('date', '')}"
            log_entries.append({
                'time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'title': label,
                'sub': sub,
                'docid': int(r['docid']),
                'dept': r.get('dept', ''),
                'date': r.get('date', ''),
            })
        _append_notify_log(log_entries)

        if len(new_rows) == 1:
            r = new_rows[0]
            title = '新 OA 通知'
            body = f"{(r.get('title') or '')[:60]}\n{r.get('dept', '')} · {r.get('date', '')}"
        else:
            title = f'{len(new_rows)} 条新 OA 通知'
            lines = [f"· {(r.get('title') or '')[:40]}" for r in new_rows[:3]]
            body = '\n'.join(lines)
            if len(new_rows) > 3:
                body += f'\n… 等共 {len(new_rows)} 条'
        # 点击直达 OA 通知列表（不标记已读，新通知保持红色标记；不再弹中间可点选列表）
        self.notifier.notify(title, body, on_click=self.show_viewer)

    def open_notice_detail(self, docid: int, parent=None, meta: dict = None):
        """应用内打开通知详情（正文 + 附件下载 + 跳转原页面），自动标记已读"""
        try:
            # 自动标记已读：推进水位
            wm = _get_watermark()
            if int(docid) > wm:
                _set_watermark(int(docid))
            item = dict(meta or {})
            item['docid'] = int(docid)
            NoticeDetailDialog(self, item, parent=parent).exec()
        except Exception as e:
            self.sdk.logger_error(f'打开通知详情失败: {e}')

    # ── 菜单动作 ──

    def show_viewer(self, *args):
        try:
            NoticeViewerDialog(self).exec()
        except Exception as e:
            self.sdk.logger_error(f'打开通知列表失败: {e}')
