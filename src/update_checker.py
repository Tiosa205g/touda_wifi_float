"""版本更新检查模块

从 GitHub Releases API 获取最新版本信息，提供版本比较和用户通知功能。
"""
import re
import requests
from typing import Optional

from src.logging_config import logger

# GitHub 仓库信息
GITHUB_REPO = "Tiosa205g/touda_wifi_float"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# 请求超时（秒）
REQUEST_TIMEOUT = 5


def parse_version(version: str) -> tuple:
    """将版本字符串解析为可比较的数字元组

    支持格式: v1.4.7.1, 1.4.7.1, v2.0, 等
    非数字段会被忽略，缺失位补 0。
    """
    clean = version.lstrip("v").strip()
    parts = re.findall(r"\d+", clean)
    if not parts:
        return (0,)
    return tuple(int(p) for p in parts)


def compare_versions(v_current: str, v_latest: str) -> int:
    """比较两个版本号

    Args:
        v_current: 当前版本号
        v_latest: 最新版本号

    Returns:
        -1: 当前版本更旧（需要更新）
         0: 版本相同
         1: 当前版本更新（理论上不应发生）
    """
    cur = parse_version(v_current)
    lat = parse_version(v_latest)

    # 补齐到相同长度
    max_len = max(len(cur), len(lat))
    cur = cur + (0,) * (max_len - len(cur))
    lat = lat + (0,) * (max_len - len(lat))

    if cur < lat:
        return -1
    elif cur > lat:
        return 1
    return 0


class UpdateInfo:
    """版本更新信息"""

    def __init__(self, tag_name: str, html_url: str, body: str, published_at: str):
        self.tag_name = tag_name          # 如 "v1.5.0.0"
        self.version = tag_name.lstrip("v")  # 纯版本号 "1.5.0.0"
        self.html_url = html_url          # Release 页面链接
        self.body = body                  # Release 说明（markdown）
        self.published_at = published_at  # 发布时间

    def summary(self, max_length: int = 120) -> str:
        """获取更新说明的简短摘要"""
        if not self.body:
            return ""
        # 取第一段非空行
        for line in self.body.split("\n"):
            line = line.strip().strip("#").strip()
            if line:
                if len(line) > max_length:
                    return line[:max_length] + "..."
                return line
        return ""


def check_for_update(current_version: str) -> Optional[UpdateInfo]:
    """查询 GitHub Releases API 获取最新版本信息

    Args:
        current_version: 当前程序版本（如 "v1.4.7.1"）

    Returns:
        有新版本时返回 UpdateInfo，否则返回 None
        网络异常或解析失败也返回 None
    """
    try:
        logger.info(f"检查更新: 当前版本 {current_version}")
        resp = requests.get(RELEASES_API, timeout=REQUEST_TIMEOUT, headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ToudaWiFiFloat/1.0",
        })

        if resp.status_code != 200:
            logger.warning(f"检查更新失败: HTTP {resp.status_code}")
            return None

        data = resp.json()
        tag_name = data.get("tag_name", "")
        if not tag_name:
            logger.warning("检查更新失败: 响应中无 tag_name")
            return None

        # 版本比较
        result = compare_versions(current_version, tag_name)
        if result >= 0:
            logger.info(f"已是最新版本: {current_version}")
            return None

        info = UpdateInfo(
            tag_name=tag_name,
            html_url=data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest"),
            body=data.get("body", ""),
            published_at=data.get("published_at", ""),
        )
        logger.info(f"发现新版本: {tag_name}")
        return info

    except requests.exceptions.Timeout:
        logger.warning("检查更新超时")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"检查更新网络异常: {e}")
        return None
    except Exception as e:
        logger.exception(f"检查更新异常: {e}")
        return None
