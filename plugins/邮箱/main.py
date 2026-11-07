# 汕大邮箱插件：应用内收发邮件 + 新邮件通知
# 邮箱托管于世纪互联 Office 365（partner.outlook.cn）。
# 认证与通路（实测）：
#   · IMAP 密码认证已被服务端禁用（AUTHENTICATE failed / mechanism not supported）
#   · 读信：Microsoft Graph 中国云（microsoftgraph.chinacloudapi.cn），ROPC 密码换令牌
#   · 发信：Outlook REST v2.0（partner.outlook.cn/api/v2.0）sendmail，
#     失败时回退 SMTP 密码登录（587 STARTTLS，实测可用）
import os
import re
import ssl
import time
import json
import tomlkit
import smtplib
import requests
import webbrowser
import pluggy
import base64
from pathlib import Path
from urllib.parse import unquote
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from plugin_sdk import (
    PluginSDK, PluginMenu, get_notifier, install_row_hover,
)

from PySide6.QtCore import Qt, QObject, QTimer, QEvent, QUrl
from PySide6.QtGui import QColor, QFont, QImage, QTextDocument
from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSplitter, QTextBrowser,
    QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QPlainTextEdit, QFileDialog,
)
from qfluentwidgets import (
    PushButton, PrimaryPushButton, ToolButton, ComboBox, LineEdit,
    BodyLabel, CaptionLabel, StrongBodyLabel, FluentIcon as FIF,
)

from ui.components.frameless_dialog import (
    FramelessDialog, _position_dialog, _theme_colors,
)
from src.touda import start_worker_in_thread

PLUGIN_NAME = '汕大邮箱助手'
PLUGIN_VERSION = '2.3.2'
PLUGIN_AUTHOR = 'tiosa'
PLUGIN_PATH = Path(__file__).parent
PLUGIN_CFG = PLUGIN_PATH / 'config.toml'

# 使用与主程序一致的标识
hook = pluggy.HookimplMarker("toudawifi")  # 不能变动

DEFAULT_SUFFIX = 'stu.edu.cn'

# 发信 SMTP（Outlook REST 不可用时的兜底通道）
SMTP_HOST = 'partner.outlook.cn'
SMTP_PORT = 587

# ── OAuth / API 常量（世纪互联云） ──
TENANT = '13f1a05d-6567-489d-99f2-6e4da6095667'          # stu.edu.cn 租户
TOKEN_URL = f'https://login.partner.microsoftonline.cn/{TENANT}/oauth2/v2.0/token'
GRAPH_BASE = 'https://microsoftgraph.chinacloudapi.cn/v1.0'
REST_BASE = 'https://partner.outlook.cn/api/v2.0'
# 微软一方公共客户端（Microsoft Office），无需注册应用即可密码换令牌
CLIENT_ID = 'd3590ed6-52b3-4102-aeff-aad2292ab01c'
SCOPE_GRAPH = 'https://microsoftgraph.chinacloudapi.cn/.default offline_access'
SCOPE_REST = 'https://partner.outlook.cn/.default offline_access'

DEFAULT_PAGESIZE = 20
DEFAULT_POLL_MINUTES = 3
NOTIFY_LOG_MAX = 20

# 令牌缓存：key -> (access_token, expiry_epoch)
_TOKEN_CACHE = {}


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


def _get_poll_minutes() -> int:
    try:
        v = int(_get_cfg('mail', 'poll_minutes', DEFAULT_POLL_MINUTES))
        return v if v >= 0 else DEFAULT_POLL_MINUTES
    except Exception:
        return DEFAULT_POLL_MINUTES


def _get_pagesize() -> int:
    try:
        v = int(_get_cfg('mail', 'pagesize', DEFAULT_PAGESIZE))
        return v if v > 0 else DEFAULT_PAGESIZE
    except Exception:
        return DEFAULT_PAGESIZE


def _get_last_dt() -> str:
    """已提醒过的最新邮件时间（ISO UTC），作为新邮件水位"""
    return str(_get_cfg('mail', 'last_dt', '') or '')


def _set_last_dt(v: str):
    _set_cfg('mail', 'last_dt', v)


# 已提醒（含首次基线）的邮件标识：ge 秒级过滤会重复取到水位同秒的旧邮件，
# 靠这个集合去重；集合里同时存 uid 与 InternetMessageId（见 _item_keys），
# 拦住同一封信跨文件夹/跨轮次的副本（实测曾每分钟重复提醒、一封信弹两封）。
NOTIFIED_UIDS_MAX = 100

# 全部已读单次处理上限：Graph 无「全部已读」接口，需逐封 PATCH，
# 封顶防误触时长时间跑飞（超出部分提示用户可再点一次）
MARK_ALL_READ_MAX = 500

# 收件箱预览缓存的邮件数上限（含内嵌图字节，来回切换秒开）
MSG_CACHE_MAX = 6

# 懒加载下仍取字节的附件阈值：
# - 图片 ≤ IMAGE_FETCH_MAX：内嵌图渲染必需；cid 图常被客户端误标 isInline=False
#   （实测 Outlook 会给普通附件也发 contentId），只能按类型兜底取字节。
#   超过阈值的大图当普通附件对待（预览不取，保存时按需下载）。
# - 小附件 ≤ SMALL_FETCH_MAX：顺手取字节（覆盖 contentType 误标的小图）。
IMAGE_FETCH_MAX = 4 * 1024 * 1024
SMALL_FETCH_MAX = 256 * 1024


def _get_notified_uids() -> list:
    try:
        return [str(x) for x in
                json.loads(str(_get_cfg('mail', 'notified_uids', '[]') or '[]'))]
    except Exception:
        return []


def _register_notified(uids) -> None:
    """登记已提醒/基线 uid，超出上限丢弃最旧的"""
    cur = _get_notified_uids()
    changed = False
    for u in uids:
        u = str(u or '')
        if u and u not in cur:
            cur.append(u)
            changed = True
    if changed:
        _set_cfg('mail', 'notified_uids',
                 json.dumps(cur[-NOTIFIED_UIDS_MAX:], ensure_ascii=False))


def _item_keys(it: dict) -> list:
    """一条消息的去重键：Graph uid + internetMessageId

    同一封信在邮箱里可能有多个副本（自发自收：收件箱/已发送各一份；
    邮件在文件夹间移动后 uid 也会变），副本 uid 不同但 internetMessageId
    相同——两个键都进已提醒集合才能拦住重复提醒。
    """
    keys = [str(it.get('uid') or ''), str(it.get('msgid') or '')]
    return [k for k in keys if k]


def _filter_fresh(items: list) -> list:
    """滤掉已提醒过的邮件，只留真正的新件（同批次内同信副本也去重）"""
    seen = set(_get_notified_uids())
    out = []
    for it in items:
        keys = _item_keys(it)
        if any(k in seen for k in keys):
            continue
        seen.update(keys)  # 同批次内两副本互斥
        out.append(it)
    return out


def _load_notify_log() -> list:
    try:
        return json.loads(str(_get_cfg('notify', 'log_json', '[]') or '[]'))
    except Exception:
        return []


def _append_notify_log(entries: list):
    log = _load_notify_log()
    log = list(log) + list(entries)
    log = log[-NOTIFY_LOG_MAX:]
    _set_cfg('notify', 'log_json', json.dumps(log, ensure_ascii=False))


# =========================================================================
# 后台任务结果回流（Plugin 不是 QObject，用独立 _Job 排队回主线程）
# =========================================================================
class _Job(QObject):
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
# OAuth 令牌获取（ROPC 密码流 + 刷新令牌缓存）
# =========================================================================
class MailError(Exception):
    pass


def _friendly_aad_err(desc: str) -> str:
    if 'AADSTS50126' in desc:
        return '登录失败：账号或密码不正确。\n密码与校园网账号一致；新账号需先修改一次校园网密码激活邮箱。'
    if 'AADSTS50076' in desc or 'AADSTS50079' in desc:
        return '该账号启用了双重验证，无法使用密码直连登录。\n请改用「网页版邮箱」。'
    if 'AADSTS50034' in desc:
        return '账号不存在，请检查邮箱地址。'
    if 'AADSTS50053' in desc:
        return '账号因多次登录失败被暂时锁定，请稍后再试。'
    line = (desc or '').splitlines()
    return f'登录失败：{line[0][:120] if line else "未知错误"}'


def _http_session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False   # 校园网/代理环境下直连身份服务器最稳
    s.verify = False
    return s


def _jwt_exp(token: str) -> float:
    try:
        p = token.split('.')[1]
        p += '=' * (-len(p) % 4)
        return float(json.loads(base64.urlsafe_b64decode(p)).get('exp', 0))
    except Exception:
        return 0.0


def _acquire_token(cache_key: str, scope: str, account: str, password: str) -> str:
    """获取访问令牌：内存缓存 → 刷新令牌 → ROPC 密码流"""
    now = time.time()
    cached = _TOKEN_CACHE.get(cache_key)
    if cached and cached[1] > now + 60:
        return cached[0]

    s = _http_session()
    refresh = str(_get_cfg('mail', f'{cache_key}_refresh', '') or '')
    if refresh:
        try:
            r = s.post(TOKEN_URL, data={
                'grant_type': 'refresh_token', 'client_id': CLIENT_ID,
                'refresh_token': refresh, 'scope': scope,
            }, timeout=20)
            j = r.json()
            if 'access_token' in j:
                _cache_token(cache_key, j)
                return j['access_token']
        except Exception:
            pass

    if not account or not password:
        raise MailError('未配置邮箱账号或密码，请先在「设置」中填写')

    try:
        r = s.post(TOKEN_URL, data={
            'grant_type': 'password', 'client_id': CLIENT_ID,
            'username': account, 'password': password, 'scope': scope,
        }, timeout=20)
    except requests.RequestException as e:
        raise MailError(f'无法连接身份服务器：{e}') from e

    j = r.json()
    if 'access_token' not in j:
        desc = j.get('error_description') or j.get('error') or str(r.status_code)
        raise MailError(_friendly_aad_err(desc))
    _cache_token(cache_key, j)
    return j['access_token']


def _cache_token(cache_key: str, token_resp: dict):
    tok = token_resp['access_token']
    exp = _jwt_exp(tok) or (time.time() + 3000)
    _TOKEN_CACHE[cache_key] = (tok, exp)
    rt = token_resp.get('refresh_token')
    if rt:
        try:
            _set_cfg('mail', f'{cache_key}_refresh', rt)
        except Exception:
            pass


def _fmt_dt(iso: str) -> str:
    """Graph ISO 时间 → 本地可读"""
    try:
        v = (iso or '').replace('Z', '+00:00')
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime('%Y-%m-%d %H:%M')
    except Exception:
        return str(iso or '')[:16]


def _iso_utc(iso: str) -> str:
    """归一化为 UTC ISO 8601（保留亚秒精度，水位比较用）

    必须保留小数秒：Graph 的 receivedDateTime 带亚秒，水位一旦截断到秒，
    同一封邮件永远满足时间条件，会被反复识别为新邮件（实测卡住反复弹窗）。
    统一输出定长 `YYYY-MM-DDTHH:MM:SS.ffffffZ`，保证字符串比较 == 时间比较。
    """
    try:
        v = (iso or '').replace('Z', '+00:00')
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        return f'{dt:%Y-%m-%dT%H:%M:%S}.{dt.microsecond:06d}Z'
    except Exception:
        return str(iso or '')


def _iso_sec(iso: str) -> str:
    """截断到秒（OData 过滤字面量用，配 ge + uid 去重，宁多取不漏掉）"""
    s = _iso_utc(iso)
    return s[:19] + 'Z' if len(s) > 20 else s


# =========================================================================
# 邮件数据层：Graph 读信 / REST+SMTP 发信
# =========================================================================
class MailClient:
    def __init__(self, account: str, password: str):
        self.account = (account or '').strip()
        self.password = password or ''

    # ---- 令牌 ----

    def _graph_token(self) -> str:
        return _acquire_token('graph', SCOPE_GRAPH, self.account, self.password)

    def _rest_token(self) -> str:
        return _acquire_token('rest', SCOPE_REST, self.account, self.password)

    def _graph_get(self, path: str, params: dict | None = None) -> dict:
        s = _http_session()
        r = s.get(f'{GRAPH_BASE}{path}', params=params or {}, timeout=20, headers={
            'Authorization': f'Bearer {self._graph_token()}',
            'Accept': 'application/json',
        })
        if r.status_code == 401:
            raise MailError('登录已过期，请重新打开收件箱')
        if r.status_code >= 400:
            raise MailError(f'接口错误 HTTP {r.status_code}: {r.text[:160]}')
        return r.json()

    def _graph_patch(self, path: str, payload: dict):
        s = _http_session()
        r = s.patch(f'{GRAPH_BASE}{path}', json=payload, timeout=20, headers={
            'Authorization': f'Bearer {self._graph_token()}',
            'Accept': 'application/json',
        })
        if r.status_code >= 400:
            raise MailError(f'操作失败 HTTP {r.status_code}: {r.text[:160]}')

    # ---- 查询 ----

    def count_unseen(self) -> int:
        j = self._graph_get('/me/mailFolders/inbox',
                            {'$select': 'unreadItemCount'})
        return int(j.get('unreadItemCount') or 0)

    def list_messages(self, page: int = 1, pagesize: int = DEFAULT_PAGESIZE) -> dict:
        folder = self._graph_get('/me/mailFolders/inbox',
                                 {'$select': 'totalItemCount,unreadItemCount'})
        total = int(folder.get('totalItemCount') or 0)
        unseen = int(folder.get('unreadItemCount') or 0)
        total_pages = max(1, (total + pagesize - 1) // pagesize)
        page_ = min(max(1, int(page)), total_pages)

        items = []
        if total:
            j = self._graph_get('/me/mailFolders/inbox/messages', {
                '$top': str(pagesize),
                '$skip': str((page_ - 1) * pagesize),
                '$select': 'id,subject,from,receivedDateTime,isRead,hasAttachments,bodyPreview',
                '$orderby': 'receivedDateTime desc',
            })
            for m in j.get('value', []):
                items.append(self._to_item(m))
        return {
            'items': items, 'page': page_,
            'total_pages': total_pages, 'total': total, 'unseen': unseen,
        }

    def fetch_new_headers(self, since_iso: str, limit: int = 8) -> list:
        """取指定时间之后的新邮件（新通知用）

        只查收件箱（`/me/mailFolders/inbox/messages`，与收件箱列表/未读数
        同一范围）：`/me/messages` 是全邮箱，自发自收的信在「已发送」还有
        一个副本，会被当成第二封新邮件（实测一封信弹“2 封新邮件”）。
        外发邮件的「已发送」副本也不该算收进的新件。

        用 `ge` + 秒级字面量（宁多取不漏）：水位带亚秒精度，而 OData 字面量
        只能到秒，`gt` 反而会漏掉同秒内更早的邮件；多取到的重复件由调用方
        的 uid/InternetMessageId 已提醒集合去重。
        """
        wm = _iso_sec(since_iso)
        j = self._graph_get('/me/mailFolders/inbox/messages', {
            '$filter': f'receivedDateTime ge {wm}',
            '$orderby': 'receivedDateTime desc',
            '$top': str(limit),
            '$select': 'id,subject,from,receivedDateTime,isRead,internetMessageId',
        })
        return [self._to_item(m) for m in j.get('value', [])]

    def fetch_message(self, msg_id: str, lazy_atts: bool = True) -> dict:
        """读取整封邮件（正文 + 附件），只读不改已读状态

        浏览 ≠ 已读：这里不 PATCH isRead，避免用户翻阅邮件就被标成已读
        （已读状态只由「标为已读/标为未读/全部已读」显式操作改变）。

        lazy_atts=True（预览默认）：大体积非图片附件只取元数据（名称/大小），
        字节留给「保存附件」按需下载——大附件完整下载会让预览卡几十秒。
        内嵌图 / 小图片 / 小附件仍取字节（cid 渲染必需）。
        """
        j = self._graph_get(f'/me/messages/{msg_id}', {
            '$select': ('id,subject,from,toRecipients,ccRecipients,'
                        'receivedDateTime,body,hasAttachments'),
        })

        body = j.get('body') or {}
        content = str(body.get('content') or '')
        is_html = (body.get('contentType') or '').lower() == 'html'
        text = _html_to_text(content) if is_html else content

        atts, atts_ok = self._fetch_attachments(msg_id, inline_only=lazy_atts)

        return {
            'uid': str(j.get('id') or msg_id),
            'from': self._addr_str(j.get('from')),
            'to': ', '.join(self._addr_str(x) for x in (j.get('toRecipients') or [])),
            'cc': ', '.join(self._addr_str(x) for x in (j.get('ccRecipients') or [])),
            'subject': str(j.get('subject') or '(无主题)'),
            'date': _fmt_dt(j.get('receivedDateTime')),
            'text': text,
            'html': content if is_html else '',
            'attachments': atts,
            # hasAttachments 对「仅内嵌图」邮件经常谎报 false（实测 200 封里 20 封），
            # 不能只信它：列表真拿到附件也算有附件
            'has_attachments': bool(j.get('hasAttachments')) or bool(atts),
            'atts_ok': atts_ok,
        }

    def _fetch_attachments(self, msg_id: str,
                           inline_only: bool = False) -> tuple:
        """收集附件（含内嵌图片，带 content_id 供 cid 映射），返回 (附件列表, 列表请求是否成功)。

        刻意不用 $expand=attachments($select=...)：
        - contentId/contentBytes 是 fileAttachment 派生属性，$select 按基类
          microsoft.graph.attachment 校验直接 400（实测：Parsing OData
          Select and Expand failed: Could not find a property named 'contentId'）
        - 世纪互联网关对 $expand 也不稳
        统一走独立 /attachments 列表（只选基类属性）+ 逐个完整实体下载。

        注意：不要拿消息的 hasAttachments 短路——Exchange 对「只有内嵌图」的
        邮件经常报 hasAttachments=false（实测 200 封里 20 封，全是这类），
        短路会让内嵌图全部丢失且附件区显示「无附件」。这里总是查列表。

        inline_only=True（预览）：只对「内嵌图 / 图片≤IMAGE_FETCH_MAX /
        小附件≤SMALL_FETCH_MAX / 云链接除外」下载字节（cid 渲染必需），
        其余大附件仅返回元数据，字节由 download_attachment 保存时按需拉取。

        逐个下载的取法：
        - 完整实体 GET（不带 $select）→ contentId + contentBytes 一次拿全
        - 拿不到内容再 /$value：fileAttachment=原始字节；itemAttachment=MIME
          （即 .eml 原文）；referenceAttachment=405（仅显示名字）
        """
        raw = []
        try:
            ja = self._graph_get(f'/me/messages/{msg_id}/attachments', {
                '$select': 'id,name,contentType,size,isInline',
            })
            raw = [a for a in (ja.get('value') or []) if isinstance(a, dict)]
        except Exception:
            return [], False

        atts = []
        if not raw:
            return atts, True

        s = _http_session()
        for a in raw:
            name = str(a.get('name') or 'attachment')
            typ = str(a.get('@odata.type') or '')
            ct = str(a.get('contentType') or '').lower()
            try:
                asize = int(a.get('size') or 0)
            except Exception:
                asize = 0
            data = b''
            content_id = ''
            jj = {}
            is_ref = 'referenceAttachment' in typ
            want_data = not is_ref and (
                (not inline_only)
                or bool(a.get('isInline'))                      # 内嵌图：渲染必需
                or (ct.startswith('image/') and asize <= IMAGE_FETCH_MAX)
                or (asize <= SMALL_FETCH_MAX and asize > 0)     # 小附件顺手取
            )
            if want_data:
                try:
                    r = s.get(
                        f'{GRAPH_BASE}/me/messages/{msg_id}/attachments/{a["id"]}',
                        timeout=60,
                        headers={'Authorization': f'Bearer {self._graph_token()}',
                                 'Accept': 'application/json'})
                    if r.status_code == 200:
                        try:
                            jj = r.json() or {}
                        except Exception:
                            jj = {}
                    typ = str(jj.get('@odata.type') or typ)
                    content_id = str(jj.get('contentId') or '').strip().strip('<>')
                    b64 = str(jj.get('contentBytes') or '')
                    if b64:
                        try:
                            # 服务端偶发返回无 padding 的 base64，补齐再解
                            data = base64.b64decode(b64 + '=' * (-len(b64) % 4))
                        except Exception:
                            data = b''
                except Exception:
                    data = b''
                if not data:
                    # contentBytes 缺失/解码失败 → /$value 兜底取原始字节
                    try:
                        r2 = s.get(
                            f'{GRAPH_BASE}/me/messages/{msg_id}/attachments/{a["id"]}/$value',
                            timeout=60,
                            headers={'Authorization': f'Bearer {self._graph_token()}'})
                        if r2.status_code == 200 and r2.content:
                            data = r2.content
                    except Exception:
                        pass
            if 'itemAttachment' in typ and not name.lower().endswith('.eml'):
                name += '.eml'
            atts.append({
                'id': str(a.get('id') or ''),
                'filename': name,
                'data': data,
                'inline': bool(a.get('isInline')),
                # 实体 GET 可能给出更准的 @odata.type，故在此重判（预取 is_ref 只用于懒加载决策）
                'link': 'referenceAttachment' in typ,
                'size': int(a.get('size') or len(data) or 0),
                # cid 图片映射：<img src="cid:xxx"> ↔ contentId（尖括号剥掉）
                'content_id': content_id,
            })
        return atts, True

    def download_attachment(self, msg_id: str, att_id: str) -> bytes:
        """按需下载单个附件字节（预览不带普通附件数据，保存时才拉）"""
        s = _http_session()
        hdr = {'Authorization': f'Bearer {self._graph_token()}'}
        data = b''
        try:
            r = s.get(
                f'{GRAPH_BASE}/me/messages/{msg_id}/attachments/{att_id}',
                timeout=60,
                headers={**hdr, 'Accept': 'application/json'})
            if r.status_code == 200:
                try:
                    jj = r.json() or {}
                except Exception:
                    jj = {}
                b64 = str(jj.get('contentBytes') or '')
                if b64:
                    try:
                        data = base64.b64decode(b64 + '=' * (-len(b64) % 4))
                    except Exception:
                        data = b''
        except Exception:
            data = b''
        if not data:
            try:
                r2 = s.get(
                    f'{GRAPH_BASE}/me/messages/{msg_id}/attachments/{att_id}/$value',
                    timeout=60, headers=hdr)
                if r2.status_code == 200 and r2.content:
                    data = r2.content
            except Exception:
                pass
        return data

    def set_seen(self, msg_id: str, seen: bool = True):
        self._graph_patch(f'/me/messages/{msg_id}', {'isRead': bool(seen)})

    def mark_unseen(self, msg_id: str):
        self._graph_patch(f'/me/messages/{msg_id}', {'isRead': False})

    def mark_all_read(self) -> int:
        """把收件箱未读邮件全部标为已读，返回成功标记的封数。

        Graph 没有「全部已读」接口，只能逐封 PATCH：先收集未读 id
        （只翻页不改动，$skip 分页才安全），再逐封标记；单次封顶
        MARK_ALL_READ_MAX，未处理完的可再次点击继续。
        """
        ids: list = []
        skip = 0
        while len(ids) < MARK_ALL_READ_MAX:
            j = self._graph_get('/me/mailFolders/inbox/messages', {
                '$filter': 'isRead eq false',
                '$select': 'id',
                '$top': '50',
                '$skip': str(skip),
                '$orderby': 'receivedDateTime desc',
            })
            vals = j.get('value') or []
            ids.extend(str(m.get('id')) for m in vals if m.get('id'))
            if len(vals) < 50:
                break
            skip += len(vals)

        n = 0
        for mid in ids[:MARK_ALL_READ_MAX]:
            try:
                self._graph_patch(f'/me/messages/{mid}', {'isRead': True})
                n += 1
            except Exception:
                continue  # 单封失败不中断，其余照常标记
        return n

    def delete(self, msg_id: str):
        s = _http_session()
        r = s.delete(f'{GRAPH_BASE}/me/messages/{msg_id}', timeout=20, headers={
            'Authorization': f'Bearer {self._graph_token()}',
        })
        if r.status_code >= 400:
            raise MailError(f'删除失败 HTTP {r.status_code}: {r.text[:160]}')

    def test_connection(self) -> str:
        j = self._graph_get('/me/mailFolders/inbox',
                            {'$select': 'displayName,totalItemCount,unreadItemCount'})
        return (f"{j.get('displayName', '收件箱')} 共 {j.get('totalItemCount', 0)} 封，"
                f"未读 {j.get('unreadItemCount', 0)} 封")

    # ---- 发送 ----

    def send(self, to: str, subject: str, body: str,
             cc: str = '', attachments: list | None = None):
        to = (to or '').strip()
        if not to:
            raise MailError('请填写收件人')

        def _recipients(s):
            out = []
            for addr in re.split(r'[,;，；\s]+', s or ''):
                addr = addr.strip()
                if addr:
                    out.append({'EmailAddress': {'Address': addr}})
            return out

        att_json = []
        for path in attachments or []:
            p = Path(path)
            if not p.is_file():
                continue
            if p.stat().st_size > 8 * 1024 * 1024:
                raise MailError(f'附件过大（>8MB）：{p.name}')
            att_json.append({
                '@odata.type': '#Microsoft.OutlookServices.FileAttachment',
                'Name': p.name,
                'ContentType': 'application/octet-stream',
                'ContentBytes': base64.b64encode(p.read_bytes()).decode(),
            })

        payload = {
            'Message': {
                'Subject': subject or '(无主题)',
                'Body': {'ContentType': 'Text', 'Content': body or ''},
                'ToRecipients': _recipients(to),
                'Attachments': att_json,
            },
            'SaveToSentItems': True,
        }
        if (cc or '').strip():
            payload['Message']['CcRecipients'] = _recipients(cc)

        # 优先 Outlook REST v2.0 sendmail，失败回退 SMTP 密码发送
        rest_err = None
        try:
            s = _http_session()
            r = s.post(f'{REST_BASE}/me/sendmail', json=payload, timeout=30, headers={
                'Authorization': f'Bearer {self._rest_token()}',
                'Accept': 'application/json',
                'X-AnchorMailbox': self.account,
            })
            if r.status_code in (200, 201, 202):
                return
            rest_err = MailError(f'HTTP {r.status_code}: {r.text[:160]}')
        except Exception as e:
            rest_err = e
        try:
            self._send_smtp(to, subject, body, cc, attachments)
        except Exception as smtp_err:
            raise MailError(f'发送失败。\n接口：{rest_err}\nSMTP：{smtp_err}') from smtp_err

    def _send_smtp(self, to, subject, body, cc, attachments):
        if not self.account or not self.password:
            raise MailError('未配置邮箱账号或密码，无法发送')
        msg = EmailMessage()
        msg['From'] = self.account
        msg['To'] = to
        if (cc or '').strip():
            msg['Cc'] = cc.strip()
        msg['Subject'] = subject or '(无主题)'
        msg.set_content(body or '')
        for path in attachments or []:
            p = Path(path)
            if not p.is_file():
                continue
            import mimetypes
            ctype, _ = mimetypes.guess_type(str(p))
            maintype, subtype = (ctype or 'application/octet-stream').split('/', 1)
            msg.add_attachment(p.read_bytes(), maintype, subtype, filename=p.name)
        try:
            s = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=25)
            try:
                s.starttls(context=ssl.create_default_context())
                s.login(self.account, self.password)
                s.send_message(msg)
            finally:
                try:
                    s.quit()
                except Exception:
                    pass
        except smtplib.SMTPAuthenticationError as e:
            raise MailError(_friendly_aad_err(str(e))) from e
        except smtplib.SMTPException as e:
            raise MailError(f'发送失败：{e}') from e
        except OSError as e:
            raise MailError(f'无法连接发件服务器：{e}') from e

    # ---- 解析辅助 ----

    @staticmethod
    def _addr_str(entry) -> str:
        if not entry:
            return ''
        # Graph 为小写驼峰（emailAddress），REST v2.0 为帕斯卡（EmailAddress）
        ea = entry.get('emailAddress') or entry.get('EmailAddress')
        if not ea or not isinstance(ea, dict):
            return ''
        addr = ea.get('address') or ea.get('Address') or ''
        name = ea.get('name') or ea.get('Name') or ''
        return f'{name} <{addr}>' if name and name != addr else addr

    @classmethod
    def _to_item(cls, m: dict) -> dict:
        return {
            'uid': str(m.get('id') or ''),
            'msgid': str(m.get('internetMessageId') or ''),
            'subject': str(m.get('subject') or '(无主题)'),
            'from': cls._addr_str(m.get('from')),
            'date': _fmt_dt(m.get('receivedDateTime')),
            'iso': _iso_utc(str(m.get('receivedDateTime') or '')),
            'seen': bool(m.get('isRead')),
        }


def _html_to_text(html_str: str) -> str:
    """HTML 简易转文本（阅读兜底）"""
    import html as _html
    s = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', '', html_str or '')
    # 内嵌图片在纯文本正文里不可见，留占位符提示（附件区会列出可保存）
    s = re.sub(r'(?i)<img[^>]*>', ' [图片] ', s)
    s = re.sub(r'(?i)<br\s*/?>', '\n', s)
    s = re.sub(r'(?i)</(p|div|tr|li|h[1-6])>', '\n', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = _html.unescape(s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def _fmt_size(n) -> str:
    """字节数 → 人类可读"""
    try:
        n = int(n)
    except Exception:
        return ''
    if n <= 0:
        return ''
    if n < 1024:
        return f'{n} B'
    if n < 1024 * 1024:
        return f'{n / 1024:.0f} KB'
    return f'{n / 1024 / 1024:.1f} MB'


class _ElidedLabel(QLabel):
    """单行省略标签：超长文本尾部显示 … ，全文放 tooltip（悬停可见）。

    主题/信头再长也只占一行，不换行、不挤压正文区域。
    """

    def __init__(self, text='', parent=None):
        super().__init__(parent)
        self._full_text = ''
        self.setWordWrap(False)
        self.setTextFormat(Qt.PlainText)
        self.setFullText(text)

    def setFullText(self, text: str):
        self._full_text = text or ''
        self._apply_elide()

    def fullText(self) -> str:
        return self._full_text

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply_elide()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.FontChange:
            self._apply_elide()

    def _apply_elide(self):
        if not self._full_text:
            super().setText('')
            self.setToolTip('')
            return
        w = max(self.width() - 2, 12)
        elided = self.fontMetrics().elidedText(self._full_text, Qt.ElideRight, w)
        super().setText(elided)
        # 只在真被截断时给 tooltip，避免短文本也弹提示
        self.setToolTip(self._full_text if elided != self._full_text else '')


def _esc(s: str) -> str:
    import html as _html
    return _html.escape(s or '')


def _prepare_html(html_str: str) -> str:
    """渲染前清洗：去脚本/Word 条件注释/注释，保留排版与 <img> 引用"""
    s = html_str or ''
    s = re.sub(r'(?is)<!--\[if.*?<!\[endif\]-->', '', s)  # Word 条件注释
    s = re.sub(r'(?is)<!--.*?-->', '', s)                 # 普通注释
    s = re.sub(r'(?is)<script[^>]*>.*?</script>', '', s)
    s = re.sub(r'(?is)<base[^>]*>', '', s)
    return s


class _MailBodyView(QTextBrowser):
    """邮件正文渲染区：HTML 按原排版渲染，内嵌图片正常显示。

    - cid:/文件名引用的图片从附件字节解出（loadResource 注入），超宽自动缩到阅读区宽度
    - 外链图片走网络加载；白底阅读区（邮件按浅底设计，深色主题下同样白底最稳）
    - 点击 http/https/mailto 链接交给系统浏览器
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._res = {}
        self._remote_bad = set()     # 外链图下载失败缓存，避免布局时反复重试
        self._remote_pending = set()  # 在下载中的外链图（去重，防同图多请求）
        self._relayout_timer = None   # 回填后的重排合并定时器
        self.setReadOnly(True)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(self._open_link)
        f = self.font()
        f.setPointSize(10)
        self.setFont(f)

    # ── 内容入口 ──

    def show_message(self, msg: str):
        self._res = {}
        self.setHtml(f'<div style="color:#8a8a8a;">{_esc(msg)}</div>')

    def show_content(self, html: str, text: str, attachments: list):
        self._res = {}
        img_datas = []          # 可解码为图片的附件字节（供兜底映射）
        for a in attachments or []:
            data = a.get('data') or b''
            if not data:
                continue
            self._put_res(a.get('content_id'), data)
            self._put_res(a.get('filename'), data)
            if a.get('inline') or a.get('content_id'):
                if not QImage.fromData(data).isNull():
                    img_datas.append(data)
        if html:
            html = _prepare_html(html)
            self._map_orphan_cids(html, img_datas)
            self.setHtml(html)
        else:
            body = _esc(text or '').replace('\n', '<br>')
            self.setHtml(f'<div>{body}</div>')

    @staticmethod
    def _cid_refs(html: str) -> list:
        """提取正文里 <img src="cid:xxx"> 的引用名（按出现顺序）"""
        return re.findall(r'(?is)<img[^>]+?src\s*=\s*["\']?cid:([^"\'>\s]+)',
                          html or '')

    def _map_orphan_cids(self, html: str, img_datas: list):
        """兜底：cid 引用对不上 contentId/文件名时仍让图片显示。

        实测两类真实场景会走到这里：
        - 附件完整实体没回 contentId（只剩文件名，而正文引用 cid:part1.xxx）
        - 正文 cid 引用与 contentId 各写各的（个别客户端）
        规则：未匹配引用 == 1 张内嵌图 → 直接映射；数量相等 → 按顺序映射。
        """
        if not img_datas:
            return
        orphans = []
        seen = set()
        for ref in self._cid_refs(html):
            k = self._norm_key(ref)
            if k and k not in self._res and k not in seen:
                seen.add(k)
                orphans.append(k)
        if not orphans:
            return
        uniq = []
        for d in img_datas:
            if all(d is not u for u in uniq):
                uniq.append(d)
        if len(orphans) == 1 and uniq:
            self._res[orphans[0]] = uniq[0]
        elif len(orphans) == len(uniq):
            for k, d in zip(orphans, uniq):
                self._res[k] = d

    # ── 资源解析（cid:/文件名 → 附件字节） ──

    @staticmethod
    def _norm_key(key) -> str:
        # 先做 URL 解码：HTML 里 cid 的 @ 常被写成 %40（Outlook 系典型），
        # 不解码就和 contentId 的字面 @ 对不上 → 图片显示成空白文件图标
        k = str(key or '').strip()
        for _ in range(2):
            ku = unquote(k)
            if ku == k:
                break
            k = ku
        k = k.strip().strip('<>').lower()
        if ':' in k and not k.startswith('http'):
            k = k.split(':', 1)[1]
        return k.split('?')[0].split('#')[0]

    def _put_res(self, key, data: bytes):
        k = self._norm_key(key)
        if k:
            self._res[k] = data

    def _lookup_res(self, name):
        """按多种 URL 形态查资源字节（编码差异容错）"""
        cands = []
        if isinstance(name, QUrl):
            for get in (lambda: name.toString(),
                        # 全解码形态用 Python unquote 得到：QUrl.toString() 重建
                        # 整条 URL 时禁止传 FullyDecoded（Qt 直接 qWarning
                        # 「FullyDecoded is not permitted when reconstructing
                        # the full URL」并退化成 PrettyDecoded，与上一条重复）
                        lambda: unquote(name.toString()),
                        lambda: bytes(name.toEncoded()).decode('utf-8', 'ignore'),
                        lambda: name.path()):
                try:
                    cands.append(get())
                except Exception:
                    pass
        else:
            cands.append(str(name))
        for c in cands:
            data = self._res.get(self._norm_key(c))
            if data:
                return data
        return None

    def loadResource(self, rtype, name):
        try:
            if rtype == QTextDocument.ImageResource:
                data = self._lookup_res(name)
                if data:
                    return self._to_scaled_image(data)
                # 外链图：Qt 自带网络走系统代理（校园网/代理下常被拦），
                # 用直连会话下载。必须异步——loadResource 在 GUI 线程布局期
                # 被逐图调用，同步下载每张最多阻塞界面数秒（选邮件就卡死）
                url = name.toString() if isinstance(name, QUrl) else str(name)
                if url.startswith(('http://', 'https://')):
                    if url not in self._remote_bad:
                        self._fetch_remote_async(url)
        except Exception:
            pass
        return super().loadResource(rtype, name)

    def _fetch_remote_async(self, url: str):
        """后台下载外链图；完成后回填缓存并合并重排，全程不在 GUI 线程碰网络"""
        if url in self._remote_pending:
            return
        self._remote_pending.add(url)

        def job():
            return url, self._fetch_remote(url)

        def done(result):
            self._remote_pending.discard(url)
            if isinstance(result, Exception):
                self._remote_bad.add(url)
                return
            try:
                _, data = result
            except Exception:
                data = b''
            if not data:
                self._remote_bad.add(url)
                return
            self._put_res(url, data)
            self._schedule_relayout()

        j = _Job(done)
        th, wk = start_worker_in_thread(job, 'mail_img', j.on_done)
        _keep_bg_ref(th, wk, j)

    def _schedule_relayout(self):
        """合并多张图的回填触发（200ms 去抖），避免逐图全量重排抖动"""
        try:
            if self._relayout_timer is None:
                t = QTimer(self)
                t.setSingleShot(True)
                t.setInterval(200)
                t.timeout.connect(self._do_relayout)
                self._relayout_timer = t
            self._relayout_timer.start()
        except RuntimeError:
            pass  # 视图已销毁

    def _do_relayout(self):
        try:
            self.document().markDirty()
            self.viewport().update()
        except RuntimeError:
            pass

    def _to_scaled_image(self, data: bytes):
        img = QImage.fromData(data)
        if img.isNull():
            return None
        # 超宽图片缩放到阅读区宽度，避免横向滚动
        limit = max(self.viewport().width() - 24, 240)
        if img.width() > limit:
            img = img.scaledToWidth(limit, Qt.SmoothTransformation)
        return img

    def _fetch_remote(self, url: str) -> bytes:
        """下载外链图字节（工作线程调用；成败缓存由主线程回调统一记）"""
        try:
            s = _http_session()
            r = s.get(url, timeout=6)
            if r.status_code != 200 or not r.content:
                return b''
            if len(r.content) > 5 * 1024 * 1024:
                return b''
            return r.content
        except Exception:
            return b''

    def _open_link(self, url: QUrl):
        u = url.toString()
        if u.startswith(('http://', 'https://', 'mailto:')):
            webbrowser.open(u)


# =========================================================================
# 收件箱对话框（列表 + 正文 + 附件）
# =========================================================================
class InboxDialog(FramelessDialog):
    def __init__(self, plugin, open_uid=None, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self._closed = False
        self._loading = False
        # 正在拉取详情的邮件 uid 集合：同一封不重复请求；
        # 渲染时以「当前选中行」为准丢弃过期响应，防止快速切换时内容串页
        self._inflight_uids = set()
        # 已看过的邮件缓存（uid → 消息 dict）：来回切换秒开、不闪「加载中」
        self._msg_cache = {}
        self._page = 1
        self._total_pages = 1
        self._total = 0
        self._pagesize = _get_pagesize()
        self._items = []
        self._current_msg = None
        # 通知点击追溯：加载后自动打开指定邮件
        self._open_uid_target = str(open_uid) if open_uid else None

        self.setWindowTitle(PLUGIN_NAME)
        self._title_label.setText('收件箱')
        self.resize(1080, 660)
        _position_dialog(self, parent)

        bg, text, sec, border = _theme_colors()

        # ── 工具行 ──
        bar = QWidget(self._outer)
        bar.setStyleSheet('background: transparent;')
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)

        self.btn_compose = PrimaryPushButton(FIF.SEND, '写邮件', bar)
        self.btn_compose.clicked.connect(lambda *_: self.plugin.show_compose())
        bl.addWidget(self.btn_compose)

        self.btn_refresh = ToolButton(FIF.SYNC, bar)
        self.btn_refresh.setToolTip('刷新')
        self.btn_refresh.clicked.connect(lambda *_: self.reload())
        bl.addWidget(self.btn_refresh)

        self.btn_read = PushButton(FIF.ACCEPT, '标为已读', bar)
        self.btn_read.clicked.connect(lambda *_: self.mark_read())
        bl.addWidget(self.btn_read)

        self.btn_unread = PushButton(FIF.CANCEL, '标为未读', bar)
        self.btn_unread.clicked.connect(lambda *_: self.mark_unread())
        bl.addWidget(self.btn_unread)

        self.btn_read_all = PushButton(FIF.COMPLETED, '全部已读', bar)
        self.btn_read_all.setToolTip('把收件箱所有未读邮件标为已读')
        self.btn_read_all.clicked.connect(lambda *_: self.mark_all_read())
        bl.addWidget(self.btn_read_all)

        self.btn_del = PushButton(FIF.DELETE, '删除', bar)
        self.btn_del.clicked.connect(lambda *_: self.delete_selected())
        bl.addWidget(self.btn_del)

        bl.addStretch(1)
        self.add_content(bar, 0)

        # ── 左右分栏：左侧邮件列表，右侧正文阅读区（可拖动分隔条调整比例） ──
        self.splitter = QSplitter(Qt.Horizontal, self._outer)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(3)
        self.splitter.setStyleSheet(
            f'QSplitter::handle {{ background: {border}; margin: 8px 1px; }}')

        # 左：邮件列表
        left_pane = QWidget(self.splitter)
        left_pane.setStyleSheet('background: transparent;')
        left_pane.setMinimumWidth(320)
        left_l = QVBoxLayout(left_pane)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(0)

        self.table = QTableWidget(0, 3, left_pane)
        self.table.setHorizontalHeaderLabels(['发件人', '主题', '时间'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
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
        self.table.itemSelectionChanged.connect(self._on_select)
        left_l.addWidget(self.table)

        # 右：主题 / 信头 / 正文 / 附件
        right_pane = QWidget(self.splitter)
        right_pane.setStyleSheet('background: transparent;')
        right_pane.setMinimumWidth(360)
        right_l = QVBoxLayout(right_pane)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(10)

        # 主题：单行省略（全文 tooltip），长主题不换行、不挤压正文
        self.subject_label = _ElidedLabel('（选择一封邮件查看正文）', right_pane)
        self.subject_label.setStyleSheet(
            f'color: {text}; background: transparent;'
            f' font-size: 15px; font-weight: bold;')
        right_l.addWidget(self.subject_label, 0)

        # 信头：发件人 + 时间一行；收件人 / 抄送 各一行，单行省略、全文 tooltip
        head_row = QWidget(right_pane)
        head_row.setStyleSheet('background: transparent;')
        hl = QHBoxLayout(head_row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        self.from_label = _ElidedLabel('', head_row)
        self.from_label.setStyleSheet(
            f'color: {sec}; background: transparent; font-size: 12px;')
        hl.addWidget(self.from_label, 1)
        self.date_label = CaptionLabel('', head_row)
        self.date_label.setStyleSheet(f'color: {sec}; background: transparent;')
        hl.addWidget(self.date_label, 0)
        right_l.addWidget(head_row, 0)

        self.to_label = _ElidedLabel('', right_pane)
        self.to_label.setStyleSheet(
            f'color: {sec}; background: transparent; font-size: 12px;')
        right_l.addWidget(self.to_label, 0)

        self.cc_label = _ElidedLabel('', right_pane)
        self.cc_label.setStyleSheet(
            f'color: {sec}; background: transparent; font-size: 12px;')
        right_l.addWidget(self.cc_label, 0)

        # 正文：HTML 原排版渲染 + 内嵌图片正常显示（白底阅读区，图片按邮件原设计呈现）
        self.body_view = _MailBodyView(right_pane)
        self.body_view.setStyleSheet(
            f'QTextBrowser {{ background: #ffffff; color: #1f1f1f;'
            f' border: 1px solid {border}; border-radius: 6px; padding: 8px;'
            f' selection-background-color: #2B88D8; }}')
        right_l.addWidget(self.body_view, 1)
        self.body_view.show_message('邮件正文显示在这里')

        # ── 附件行 ──
        att_bar = QWidget(right_pane)
        att_bar.setStyleSheet('background: transparent;')
        al = QHBoxLayout(att_bar)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(8)
        self.att_label = _ElidedLabel('无附件', att_bar)
        self.att_label.setStyleSheet(
            f'color: {sec}; background: transparent; font-size: 12px;')
        al.addWidget(self.att_label, 1)
        self.btn_save_att = PushButton(FIF.SAVE, '保存附件', att_bar)
        self.btn_save_att.clicked.connect(lambda *_: self.save_attachments())
        self.btn_save_att.setEnabled(False)
        al.addWidget(self.btn_save_att)
        right_l.addWidget(att_bar, 0)

        self.splitter.addWidget(left_pane)
        self.splitter.addWidget(right_pane)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([400, 600])
        self.add_content(self.splitter, 1)

        # ── 翻页 + 状态 ──
        page_bar = QWidget(self._outer)
        page_bar.setStyleSheet('background: transparent;')
        pl = QHBoxLayout(page_bar)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(8)
        self.btn_prev = PushButton(FIF.UP, '上一页', page_bar)
        self.btn_prev.clicked.connect(lambda *_: self.goto(self._page - 1))
        self.btn_next = PushButton(FIF.DOWN, '下一页', page_bar)
        self.btn_next.clicked.connect(lambda *_: self.goto(self._page + 1))
        pl.addWidget(self.btn_prev)
        pl.addWidget(self.btn_next)
        self.status_label = CaptionLabel('加载中…', page_bar)
        self.status_label.setStyleSheet(f'color: {sec}; background: transparent;')
        pl.addWidget(self.status_label, 1)
        btn_close = PushButton('关闭', page_bar)
        btn_close.clicked.connect(self.reject)
        pl.addWidget(btn_close)
        self.add_content(page_bar, 0)

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
                    alternate-background-color: #2d2d2d;
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
                alternate-background-color: #f5f8fd;
                border: 1px solid {border}; border-radius: 6px;
                gridline-color: #e8f0fe;
            }}
            QTableWidget::item:selected {{ background: #0078D4; color: white; }}
            QHeaderView::section {{
                background: #f0f6ff; color: #0078D4; border: none;
                padding: 6px; font-weight: bold;
            }}
        """

    def reject(self):
        self._closed = True
        super().reject()

    def accept(self):
        self._closed = True
        super().accept()

    # ── 数据加载 ──

    def reload(self):
        self.goto(self._page)

    def goto(self, page: int):
        if self._loading:
            return
        self._loading = True
        self._requested_page = max(int(page), 1)
        self._set_status(f'加载第 {self._requested_page} 页…')
        self._set_paging_enabled(False)

        plugin = self.plugin
        pagesize = self._pagesize
        page_ = self._requested_page

        def job():
            return plugin.make_client().list_messages(page_, pagesize)

        # 只能连接 QObject 绑定槽（跨线程自动排队回主线程），
        # 绝不能传普通闭包——否则回调跑在工作线程里操作 UI 会直接崩
        th, wk = start_worker_in_thread(job, 'mail_list', self._on_loaded)
        _keep_bg_ref(th, wk)

    def _on_loaded(self, result):
        if self._closed:
            return
        self._loading = False

        if isinstance(result, Exception):
            self._set_paging_enabled(True)
            self._set_status(f'加载失败: {result}')
            return

        self._items = result.get('items', [])
        # 先更新页码再同步按钮状态——顺序反了会导致按钮按旧页码判断
        # （第 1 页时"下一页"灰、翻到第 2 页时"上一页"灰）
        self._page = int(result.get('page') or 1)
        self._total_pages = max(int(result.get('total_pages') or 1), 1)
        self._total = int(result.get('total') or 0)
        self.plugin.set_unread(int(result.get('unseen') or 0))
        self._set_paging_enabled(True)

        self._fill_table(self._items)
        self._set_status(
            f'第 {self._page} / {self._total_pages} 页 · 共 {self._total} 封'
            f' · 未读 {result.get("unseen", 0)}')

        # 通知点击追溯：自动打开目标邮件
        if self._open_uid_target:
            uid = self._open_uid_target
            self._open_uid_target = None
            self._select_uid_row(uid)
            self._open_uid(uid)

    # 行内未读标记：● 前缀 + 加粗 + 主题红字（三保险，防 QSS/选中态吞色）
    _RAW_SUBJ_ROLE = Qt.UserRole + 1

    @staticmethod
    def _unread_color() -> str:
        try:
            from qfluentwidgets import isDarkTheme
            return '#ff7d7d' if isDarkTheme() else '#e05252'
        except Exception:
            return '#e05252'

    def _set_row_seen_style(self, row: int, seen: bool):
        """应用某行的已读/未读视觉（幂等，可反复调用）"""
        from_it = self.table.item(row, 0)
        subj_it = self.table.item(row, 1)
        date_it = self.table.item(row, 2)
        if not all((from_it, subj_it, date_it)):
            return
        raw = str(subj_it.data(self._RAW_SUBJ_ROLE) or '')
        _, text_color, _, _ = _theme_colors()
        if seen:
            plain = QFont()
            for it in (from_it, subj_it, date_it):
                it.setFont(plain)
                it.setForeground(QColor(text_color))
            subj_it.setText(raw)
        else:
            bold = QFont()
            bold.setBold(True)
            for it in (from_it, subj_it, date_it):
                it.setFont(bold)
            # 主题红字只加在主题列；● 前缀在任何配色/选中态下都可辨认
            subj_it.setText(f'\u25cf {raw}')
            subj_it.setForeground(QColor(self._unread_color()))

    def _fill_table(self, items):
        self.table.setRowCount(0)
        for it in items:
            r = self.table.rowCount()
            self.table.insertRow(r)

            from_item = QTableWidgetItem(self._short_addr(it.get('from', '')))
            subject_raw = str(it.get('subject', ''))
            subj_item = QTableWidgetItem(subject_raw)
            # 左侧窄栏用紧凑时间（MM-DD HH:MM），完整时间在右侧详情信头展示
            date_str = str(it.get('date') or '')
            date_item = QTableWidgetItem(date_str[5:] if len(date_str) >= 16 else date_str)
            for item in (from_item, subj_item, date_item):
                item.setData(Qt.UserRole, it.get('uid'))
            subj_item.setData(self._RAW_SUBJ_ROLE, subject_raw)
            self.table.setItem(r, 0, from_item)
            self.table.setItem(r, 1, subj_item)
            self.table.setItem(r, 2, date_item)
            self._set_row_seen_style(r, bool(it.get('seen', True)))

        if items and not self._open_uid_target:
            self.table.selectRow(0)
        elif not items:
            self._set_header('（收件箱为空）')
            self.body_view.show_message('（收件箱为空）')
            self.att_label.setFullText('无附件')
            self.btn_save_att.setEnabled(False)

    def _select_uid_row(self, uid: str):
        """高亮目标邮件所在行（不触发加载信号）"""
        try:
            self.table.blockSignals(True)
            for r in range(self.table.rowCount()):
                item = self.table.item(r, 0)
                if item and str(item.data(Qt.UserRole)) == str(uid):
                    self.table.selectRow(r)
                    break
        finally:
            self.table.blockSignals(False)

    @staticmethod
    def _short_addr(addr: str) -> str:
        m = re.search(r'<([^>]+)>', addr or '')
        if m:
            return m.group(1)
        return (addr or '').strip()

    def _set_header(self, subject: str, from_: str = '', date: str = '',
                    to: str = '', cc: str = ''):
        """设置右侧信头（各字段单行省略，全文 tooltip）"""
        self.subject_label.setFullText(subject or '')
        self.from_label.setFullText(f'发件人：{from_}' if from_ else '')
        self.date_label.setText(date or '')
        self.to_label.setFullText(f'收件人：{to}' if to else '')
        self.to_label.setVisible(bool(to))
        self.cc_label.setFullText(f'抄送：{cc}' if cc else '')
        self.cc_label.setVisible(bool(cc))

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

    # ── 打开邮件 ──

    def _selected_uid(self):
        rows = (self.table.selectionModel().selectedRows()
                if self.table.selectionModel() else [])
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        return item.data(Qt.UserRole) if item else None

    def _on_select(self):
        uid = self._selected_uid()
        if uid is None:
            return
        self._open_uid(str(uid))

    def _open_uid(self, uid: str):
        uid = str(uid)
        # 缓存命中：直接渲染（不闪「加载中」，来回切换秒开）
        cached = self._msg_cache.get(uid)
        if cached is not None:
            self._on_fetched(uid, cached)
            return
        if uid in self._inflight_uids:
            return  # 同一封已在加载中，不重复请求
        self._inflight_uids.add(uid)
        self._set_header('加载中…')
        self.body_view.show_message('加载中…')
        self.att_label.setFullText('无附件')
        self.btn_save_att.setEnabled(False)

        plugin = self.plugin

        def job():
            return plugin.make_client().fetch_message(uid)

        def done(result):
            self._on_fetched(uid, result)

        # 回调经 _Job 排队回主线程（普通闭包直连工作线程信号会崩）
        j = _Job(done)
        th, wk = start_worker_in_thread(job, 'mail_read', j.on_done)
        _keep_bg_ref(th, wk, j)

    def _on_fetched(self, uid: str, result):
        self._inflight_uids.discard(uid)
        if self._closed:
            return
        if not isinstance(result, Exception):
            # 即使本次因切走而丢弃，也缓存下来（下次切回秒开）
            self._msg_cache[uid] = result
            if len(self._msg_cache) > MSG_CACHE_MAX:
                self._msg_cache.pop(next(iter(self._msg_cache)))
        # 快速切换邮件时以「当前选中行」为准：晚到的过期响应直接丢弃，
        # 保证右侧内容永远与选中行一致（此前互斥锁会丢新请求、留旧内容，导致串页）
        sel = self._selected_uid()
        if sel is not None and str(sel) != str(uid):
            return
        if isinstance(result, Exception):
            self._set_header('加载失败')
            self._set_status(f'读取邮件失败: {result}')
            return

        self._current_msg = result
        self._set_header(
            result.get('subject', ''),
            result.get('from', ''), result.get('date', ''),
            result.get('to', ''), result.get('cc', ''))

        text = result.get('text') or ''
        html = result.get('html') or ''
        if not text and html:
            text = _html_to_text(html)
        # HTML 正文按原排版渲染（内嵌图片正常显示）；纯文本走转义兜底
        self.body_view.show_content(html, text or '（正文为空）',
                                    result.get('attachments') or [])

        atts = result.get('attachments') or []
        if atts:
            parts = []
            for a in atts:
                label = str(a.get('filename') or 'attachment')
                if a.get('inline'):
                    label += '（内嵌）'
                elif a.get('link'):
                    label += '（云链接）'
                sz = _fmt_size(a.get('size') or len(a.get('data') or b''))
                if sz:
                    label += f' {sz}'
                parts.append(label)
            self.att_label.setFullText(f'附件（{len(atts)}）：' + '、'.join(parts))
            self.btn_save_att.setEnabled(True)
        elif not result.get('atts_ok', True) or result.get('has_attachments'):
            # 附件列表请求失败，或 hasAttachments 为真却没解析出内容（如 S/MIME）：
            # 如实告知，而不是显示「无附件」
            self.att_label.setFullText('附件内容获取失败（可到网页版查看）')
            self.btn_save_att.setEnabled(False)
        else:
            self.att_label.setFullText('无附件')
            self.btn_save_att.setEnabled(False)
        # 注意：浏览不改已读状态，行样式（●/加粗）保持原样，
        # 仅「标为已读/标为未读/全部已读」才改变

    # ── 操作 ──

    def mark_read(self):
        uid = self._selected_uid()
        if uid is None:
            self.plugin.sdk.show_message('提示', '请先选中一封邮件')
            return
        self._run_flag_job(lambda c: c.set_seen(str(uid), True), '已标为已读')

    def mark_unread(self):
        uid = self._selected_uid()
        if uid is None:
            self.plugin.sdk.show_message('提示', '请先选中一封邮件')
            return
        self._run_flag_job(lambda c: c.mark_unseen(str(uid)), '已标为未读')

    def mark_all_read(self):
        if not self.btn_read_all.isEnabled():
            return  # 上一批还在处理中
        self.btn_read_all.setEnabled(False)
        self._set_status('正在全部标为已读…')
        plugin = self.plugin

        def job():
            return plugin.make_client().mark_all_read()

        def done(result):
            if self._closed:
                return
            try:
                self.btn_read_all.setEnabled(True)
            except RuntimeError:
                return  # 控件已销毁
            if isinstance(result, Exception):
                self._set_status(f'操作失败: {result}')
                return
            n = int(result or 0)
            # 先刷新再提示：reload 的「加载中」会覆盖前一条状态，
            # 反过来提示能在刷新期间保持可见
            self.reload()
            self._set_status(f'已全部标为已读（{n} 封）')

        j = _Job(done)
        th, wk = start_worker_in_thread(job, 'mail_flag', j.on_done)
        _keep_bg_ref(th, wk, j)

    def delete_selected(self):
        uid = self._selected_uid()
        if uid is None:
            self.plugin.sdk.show_message('提示', '请先选中一封邮件')
            return
        ok = FramelessDialog.show_confirm(
            '删除邮件', '确定删除这封邮件吗？\n删除后可在网页版「已删除邮件」中找回。', self)
        if not ok:
            return
        self._msg_cache.pop(str(uid), None)  # 删除后不能再从缓存翻出旧内容
        self._run_flag_job(lambda c: c.delete(str(uid)), '已删除')

    def _run_flag_job(self, op, done_msg: str):
        plugin = self.plugin

        def job():
            op(plugin.make_client())
            return True

        def done(result):
            if isinstance(result, Exception):
                self._set_status(f'操作失败: {result}')
                return
            self._set_status(done_msg)
            self.reload()

        j = _Job(done)
        th, wk = start_worker_in_thread(job, 'mail_flag', j.on_done)
        _keep_bg_ref(th, wk, j)

    def save_attachments(self):
        msg = self._current_msg
        if not msg or not msg.get('attachments'):
            return
        dir_ = QFileDialog.getExistingDirectory(self, '选择附件保存目录')
        if not dir_:
            return
        plugin = self.plugin
        mid = str(msg.get('uid') or '')
        atts = [dict(a) for a in msg['attachments']]
        base = Path(dir_)

        def job():
            # 预览时普通附件只带元数据，这里按需补下字节（后台线程，不卡界面）
            client = plugin.make_client()
            saved, skipped = [], []
            for a in atts:
                name = Path(str(a.get('filename') or 'attachment')).name
                if a.get('link'):
                    skipped.append(name)
                    continue
                data = a.get('data') or b''
                if not data and a.get('id'):
                    try:
                        data = client.download_attachment(mid, str(a.get('id')))
                    except Exception:
                        data = b''
                if not data:
                    skipped.append(name)
                    continue
                try:
                    (base / name).write_bytes(data)
                    saved.append(name)
                except Exception as e:
                    plugin.sdk.logger_error(f'保存附件失败: {e}')
                    skipped.append(name)
            return saved, skipped

        def done(result):
            if self._closed:
                return
            try:
                self.btn_save_att.setEnabled(True)
            except RuntimeError:
                return
            if isinstance(result, Exception):
                self._set_status(f'保存附件失败: {result}')
                return
            saved, skipped = result
            tip = f'已保存 {len(saved)} 个附件到 {dir_}'
            if skipped:
                tip += f'（{len(skipped)} 个无内容跳过：{"、".join(skipped[:3])}）'
            self._set_status(tip)

        self.btn_save_att.setEnabled(False)
        self._set_status('正在保存附件…')
        j = _Job(done)
        th, wk = start_worker_in_thread(job, 'mail_save_att', j.on_done)
        _keep_bg_ref(th, wk, j)


# =========================================================================
# 写邮件对话框
# =========================================================================
class ComposeDialog(FramelessDialog):
    def __init__(self, plugin, to: str = '', subject: str = '',
                 body: str = '', parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.attachments = []
        self.setWindowTitle('写邮件')
        self._title_label.setText('写邮件')
        self.resize(560, 520)
        _position_dialog(self, parent)

        bg, text, sec, border = _theme_colors()

        def _row(label: str, placeholder: str = ''):
            lbl = BodyLabel(label, self._outer)
            lbl.setStyleSheet(f'color: {text}; background: transparent;')
            self.add_content(lbl, 0)
            edit = LineEdit(self._outer)
            edit.setPlaceholderText(placeholder)
            self.add_content(edit, 0)
            return edit

        # ── 发件账号选择 ──
        self._accounts = plugin.list_accounts()
        acc_row = QWidget(self._outer)
        acc_row.setStyleSheet('background: transparent;')
        acc_lay = QHBoxLayout(acc_row)
        acc_lay.setContentsMargins(0, 0, 0, 0)
        acc_lay.setSpacing(8)
        acc_lbl = BodyLabel('发件账号:', acc_row)
        acc_lbl.setStyleSheet(f'color: {text}; background: transparent;')
        acc_lay.addWidget(acc_lbl)
        self.combo_account = ComboBox(acc_row)
        self.combo_account.setMinimumWidth(260)

        # 默认选中当前使用的账号；不在列表里的补一个「当前」选项
        cur_email = plugin.get_email_address()
        cur_idx_in_list = -1
        for i, a in enumerate(self._accounts):
            self.combo_account.addItem(f"{a['email']}（{a['name']}）")
            if a['email'] == cur_email:
                cur_idx_in_list = i
        if cur_idx_in_list < 0 and cur_email:
            self.combo_account.addItem(f'{cur_email}（当前）')
            self._accounts.append({'idx': None, 'name': cur_email,
                                   'email': cur_email})
            cur_idx_in_list = len(self._accounts) - 1
        if cur_idx_in_list >= 0:
            self.combo_account.setCurrentIndex(cur_idx_in_list)
        acc_lay.addWidget(self.combo_account, 1)
        self.add_content(acc_row, 0)

        self.edit_to = _row('收件人:', 'name@stu.edu.cn，多个地址用逗号分隔')
        self.edit_to.setText(to)
        self.edit_cc = _row('抄送:', '可留空')
        self.edit_subject = _row('主题:', '')
        self.edit_subject.setText(subject)

        lbl = BodyLabel('正文:', self._outer)
        lbl.setStyleSheet(f'color: {text}; background: transparent;')
        self.add_content(lbl, 0)

        self.edit_body = QPlainTextEdit(self._outer)
        self.edit_body.setPlainText(body)
        self.edit_body.setStyleSheet(
            f'QPlainTextEdit {{ background: {bg}; color: {text};'
            f' border: 1px solid {border}; border-radius: 6px; padding: 8px;'
            f' font-size: 13px; }}')
        self.add_content(self.edit_body, 1)

        att_bar = QWidget(self._outer)
        att_bar.setStyleSheet('background: transparent;')
        al = QHBoxLayout(att_bar)
        al.setContentsMargins(0, 0, 0, 0)
        btn_att = PushButton(FIF.ADD, '添加附件', att_bar)
        btn_att.clicked.connect(self._add_attachments)
        al.addWidget(btn_att)
        self.att_label = CaptionLabel('未选择附件', att_bar)
        self.att_label.setStyleSheet(f'color: {sec}; background: transparent;')
        al.addWidget(self.att_label, 1)
        self.add_content(att_bar, 0)

        # 发送状态：置位期间禁止再点（无反馈双击会把同一封发两遍）
        self._sending = False
        self.btn_send = PrimaryPushButton(FIF.SEND, '发送', self._outer)
        self.btn_send.clicked.connect(self._send)
        btn_cancel = PushButton('取消', self._outer)
        btn_cancel.clicked.connect(self.reject)
        self.add_buttons(btn_cancel, self.btn_send)

    def _add_attachments(self):
        paths, _ = QFileDialog.getOpenFileNames(self, '选择附件')
        if not paths:
            return
        self.attachments.extend(paths)
        self.att_label.setText('、'.join(Path(p).name for p in self.attachments))

    def _send(self):
        if self._sending:
            return
        to = self.edit_to.text().strip()
        if not to:
            self.plugin.sdk.show_message('提示', '请填写收件人')
            return
        plugin = self.plugin
        cc = self.edit_cc.text().strip()
        subject = self.edit_subject.text().strip()
        body = self.edit_body.toPlainText()
        atts = list(self.attachments)

        # 读取选中的发件账号凭据
        sel_idx = self.combo_account.currentIndex()
        if 0 <= sel_idx < len(self._accounts):
            acc_idx = self._accounts[sel_idx]['idx']
        else:
            acc_idx = None

        # 立即进入发送状态：按钮禁用 + 文案反馈，杜绝双击重复发送
        self._sending = True
        self.btn_send.setEnabled(False)
        self.btn_send.setText('发送中…')

        def _restore_btn():
            self._sending = False
            self.btn_send.setEnabled(True)
            self.btn_send.setText('发送')

        def job():
            if acc_idx is not None:
                email, password = plugin.get_account_creds(acc_idx)
                if not email:
                    raise MailError('无法读取所选账号的凭据')
                client = plugin.make_client_with(email, password)
            else:
                client = plugin.make_client()
            client.send(to, subject, body, cc=cc, attachments=atts)
            return True

        def done(result):
            if isinstance(result, Exception):
                _restore_btn()
                self.plugin.sdk.show_message('发送失败', str(result))
                return
            self.plugin.sdk.show_message('已发送', '邮件发送成功。')
            self.accept()

        try:
            j = _Job(done)
            th, wk = start_worker_in_thread(job, 'mail_send', j.on_done)
            _keep_bg_ref(th, wk, j)
        except Exception:
            _restore_btn()
            raise


# =========================================================================
# 设置对话框
# =========================================================================
class MailSettingDialog(FramelessDialog):
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle(f'{PLUGIN_NAME} 设置')
        self._title_label.setText(f'{PLUGIN_NAME} 设置')
        self.resize(420, 280)
        _position_dialog(self, parent)

        bg, text, sec, border = _theme_colors()

        lbl_poll = BodyLabel('新邮件自动检查间隔:', self._outer)
        lbl_poll.setStyleSheet(f'color: {text}; background: transparent;')
        self.add_content(lbl_poll, 0)

        self.combo_poll = ComboBox(self._outer)
        for label in ('关闭', '1 分钟', '3 分钟', '5 分钟', '10 分钟'):
            self.combo_poll.addItem(label)
        self.combo_poll.setCurrentIndex(self._poll_index(_get_poll_minutes()))
        self.add_content(self.combo_poll, 0)

        tip = CaptionLabel(
            '· 邮箱账号即「校园网账号@stu.edu.cn」，与当前校园网账号一致\n'
            '· 发件可在「写邮件」里选择账号列表中的任意账号\n'
            '· 密码仅保存在本机 config.toml 中，请勿共享配置目录',
            self._outer)
        tip.setWordWrap(True)
        tip.setStyleSheet(f'color: {sec}; background: transparent;')
        self.add_content(tip, 1)

        btn_test = PushButton(FIF.LINK, '测试连接', self._outer)
        btn_test.clicked.connect(self._test)
        btn_save = PrimaryPushButton(FIF.SAVE, '保存', self._outer)
        btn_save.clicked.connect(self._save)
        btn_cancel = PushButton('取消', self._outer)
        btn_cancel.clicked.connect(self.reject)
        self.add_buttons(btn_test, btn_cancel, btn_save)

    @staticmethod
    def _poll_index(minutes: int) -> int:
        mapping = {0: 0, 1: 1, 3: 2, 5: 3, 10: 4}
        return mapping.get(minutes, 2)

    @staticmethod
    def _poll_minutes(index: int) -> int:
        mapping = {0: 0, 1: 1, 2: 3, 3: 5, 4: 10}
        return mapping.get(index, 3)

    def _save(self):
        _set_cfg('mail', 'poll_minutes', self._poll_minutes(
            self.combo_poll.currentIndex()))
        self.plugin.apply_settings()
        self.accept()

    def _test(self):
        plugin = self.plugin

        def job():
            return plugin.make_client().test_connection()

        def done(result):
            if isinstance(result, Exception):
                self.plugin.sdk.show_message('测试连接', f'连接失败：\n{result}')
            else:
                self.plugin.sdk.show_message(
                    '测试连接', f'连接成功！\n{result}')

        j = _Job(done)
        th, wk = start_worker_in_thread(job, 'mail_test', j.on_done)
        _keep_bg_ref(th, wk, j)


# =========================================================================
# Plugin
# =========================================================================
class Plugin:  # 类名固定为 Plugin，不能变动，否则无法识别
    @hook
    def start(self, api) -> bool:
        """插件加载时执行,传api包含已实例化的wifi和webvpn类"""
        self.api = api
        self.sdk = PluginSDK(api, PLUGIN_NAME)
        self._unread = 0
        self._inbox_dlg = None
        self._polling = False

        # Windows 通知中枢（点击通知可追溯到邮件）
        self.notifier = get_notifier()
        self.notifier.bind(api)

        # 新邮件定时检查
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
        title = '📬 收件箱'
        if self._unread > 0:
            title = f'📬 收件箱（{self._unread} 未读）'
        menu = PluginMenu()
        menu.add_funcs([
            {'function': title, 'object': self.show_inbox},
            {'function': '✉️ 写邮件', 'object': self.show_compose},
            {'function': '⚙️ 设置', 'object': self.on_setting},
        ])
        return menu.get_all()

    @hook
    def on_setting(self):
        """当设置按钮被点击"""
        try:
            MailSettingDialog(self).exec()
        except Exception as e:
            self.sdk.logger_error(f'打开设置失败: {e}')

    # ── 账号与客户端 ──

    def apply_settings(self):
        """应用配置（重启检查定时器）"""
        minutes = _get_poll_minutes()
        self._timer.stop()
        if minutes > 0:
            self._timer.start(minutes * 60 * 1000)

    def get_current_account(self) -> dict:
        """读取主程序当前校园网账号（{'name':xxx,'pwd':xxx}）"""
        try:
            main = self.api.cfg(self.api.MAIN_CFG)
            idx = main.get('main', 'current_account', 0)
            current = self.api.cfg(
                os.path.join(self.api.CFG_DIR, f'account_{idx}.toml')
            )
            name = current.get('setting', 'name', '')
            password = base64.b64decode(
                current.get('setting', 'password', '').encode('utf-8')
            ).decode('utf-8')
            return {'name': name, 'pwd': password}
        except Exception as e:
            self.sdk.logger_error(f'读取当前账号失败: {e}')
            return {'name': '', 'pwd': ''}

    def list_accounts(self) -> list:
        """列出所有校园网账号：[{'idx', 'name', 'email'}]"""
        import re as _re
        accounts = []
        try:
            for fname in sorted(os.listdir(self.api.CFG_DIR)):
                m = _re.match(r'account_(\d+)\.toml$', fname)
                if not m:
                    continue
                idx = int(m.group(1))
                try:
                    cfg = self.api.cfg(os.path.join(self.api.CFG_DIR, fname))
                    name = str(cfg.get('setting', 'name', '') or '').strip()
                    if not name:
                        continue
                    email = name if '@' in name else f'{name}@{DEFAULT_SUFFIX}'
                    accounts.append({'idx': idx, 'name': name, 'email': email})
                except Exception:
                    continue
        except Exception as e:
            self.sdk.logger_error(f'列出账号失败: {e}')
        return accounts

    def get_account_creds(self, idx: int) -> tuple:
        """读取指定账号凭据：(email, password)"""
        try:
            cfg = self.api.cfg(
                os.path.join(self.api.CFG_DIR, f'account_{idx}.toml'))
            name = str(cfg.get('setting', 'name', '') or '').strip()
            password = base64.b64decode(
                str(cfg.get('setting', 'password', '') or '').encode('utf-8')
            ).decode('utf-8')
            email = name if '@' in name else f'{name}@{DEFAULT_SUFFIX}'
            return email, password
        except Exception as e:
            self.sdk.logger_error(f'读取账号 {idx} 凭据失败: {e}')
            return '', ''

    def get_mail_creds(self) -> tuple:
        """返回 (account, password)：校园网账号即邮箱账号，密码相同"""
        acc = self.get_current_account()
        name = (acc.get('name') or self.api.wifi.name or '').strip()
        password = acc.get('pwd') or ''
        if '@' in name:
            account = name
        elif name:
            account = f'{name}@{DEFAULT_SUFFIX}'
        else:
            account = ''
        return account, password

    def get_email_address(self) -> str:
        return self.get_mail_creds()[0]

    def make_client(self) -> MailClient:
        account, password = self.get_mail_creds()
        return MailClient(account, password)

    def make_client_with(self, account: str, password: str) -> MailClient:
        """用指定凭据创建邮件客户端（发信选账号用）"""
        return MailClient(account, password)

    def set_unread(self, n: int):
        self._unread = max(int(n), 0)

    # ── 后台任务（Plugin 非 QObject，用 _Job 排队回主线程） ──

    def _run_bg(self, fn, name: str, callback):
        job = _Job(callback)
        th, wk = start_worker_in_thread(fn, name, job.on_done)
        _keep_bg_ref(th, wk, job)

    # ── 定时检查新邮件 ──

    def _poll_tick(self):
        if self._polling:
            return
        account, password = self.get_mail_creds()
        if not account:
            return
        self._polling = True

        wm = _get_last_dt()

        def job():
            client = MailClient(account, password)
            unseen = client.count_unseen()
            if wm:
                new_items = client.fetch_new_headers(wm, limit=8)
                return {'unseen': unseen, 'new': new_items, 'baseline': None}
            # 首次：取最新几封建立水位并登记 uid（防止 ge 边界被当成新邮件），
            # 不打扰用户
            latest = client.fetch_new_headers('1970-01-01T00:00:00Z', limit=8)
            return {'unseen': unseen, 'new': [],
                    'baseline': (latest[0]['iso'] if latest else ''),
                    'baseline_items': latest}

        def done(result):
            self._polling = False
            if isinstance(result, Exception):
                self.sdk.logger_error(f'自动检查新邮件失败: {result}')
                return
            self.set_unread(result.get('unseen') or 0)
            baseline = result.get('baseline')
            if baseline is not None:
                for it in (result.get('baseline_items') or []):
                    _register_notified(_item_keys(it))
                if baseline:
                    _set_last_dt(self._newest_iso(baseline, result))
                return
            new_items = result.get('new') or []
            if not new_items:
                return
            # ge 秒级过滤会重复取到水位同秒的旧邮件 → uid/msgid 去重，只提醒 fresh
            fresh = _filter_fresh(new_items)
            # 水位推进到全部取到的最新一封（含已提醒的边界件），带亚秒精度
            _set_last_dt(self._newest_iso(None, {'new': new_items}))
            for it in new_items:
                _register_notified(_item_keys(it))
            if fresh:
                self._show_notify(fresh)

        self._run_bg(job, 'mail_poll', done)

    @staticmethod
    def _newest_iso(baseline_iso, result) -> str:
        """从结果里取最新邮件的 ISO 时间作为水位"""
        items = (result or {}).get('new') or []
        if items:
            # fetch_new_headers 已按时间倒序
            return _iso_utc(items[0].get('iso') or '')
        return _iso_utc(baseline_iso or datetime.now(timezone.utc).isoformat())

    def _show_notify(self, new_items: list):
        """新邮件 → 自绘置顶通知（点击直达收件箱，不再弹中间可点选列表）"""
        log_entries = []
        for it in new_items[:8]:
            uid = str(it.get('uid') or '')
            label = it.get('subject') or '(无主题)'
            sub = f"{it.get('from', '')}  {it.get('date', '')}"
            log_entries.append({
                'time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'title': label,
                'sub': sub,
                'uid': uid,
            })
        _append_notify_log(log_entries)

        if len(new_items) == 1:
            it = new_items[0]
            uid = str(it.get('uid') or '')
            title = '新邮件'
            body = (f"{(it.get('subject') or '')[:60]}\n"
                    f"来自 {it.get('from', '')}")
            # 单封：直达该邮件（收件箱内自动展开详情）
            on_click = lambda u=uid: self.show_inbox(open_uid=u)
        else:
            title = f'{len(new_items)} 封新邮件'
            lines = [f"· {(i.get('subject') or '')[:40]}" for i in new_items[:3]]
            body = '\n'.join(lines)
            if len(new_items) > 3:
                body += f'\n… 等共 {len(new_items)} 封'
            # 多封：直达收件箱列表
            on_click = lambda: self.show_inbox()
        try:
            self.notifier.notify(title, body, on_click=on_click)
        except Exception as e:
            self.sdk.logger_error(f'新邮件通知失败: {e}')

    # ── 菜单动作 ──

    def show_inbox(self, *args, open_uid=None):
        try:
            dlg = InboxDialog(self, open_uid=open_uid)
            self._inbox_dlg = dlg
            dlg.exec()
            self._inbox_dlg = None
        except Exception as e:
            self.sdk.logger_error(f'打开收件箱失败: {e}')

    def show_compose(self, *args):
        try:
            ComposeDialog(self).exec()
        except Exception as e:
            self.sdk.logger_error(f'打开写邮件失败: {e}')
