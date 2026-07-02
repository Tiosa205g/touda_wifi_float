import json
import pluggy
import re
import requests
from pathlib import Path

from plugin_sdk import PluginSDK, PluginMenu

PLUGIN_NAME = 'B站直播解析'
PLUGIN_VERSION = '1.0.0'
PLUGIN_AUTHOR = 'tiosa'
PLUGIN_PATH = Path(__file__).parent

hook = pluggy.HookimplMarker("toudawifi")


def _extract_text(text, start_marker, end_marker):
    pattern = re.compile(
        rf"{re.escape(start_marker)}(.*?){re.escape(end_marker)}", re.DOTALL
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


class Plugin:
    @hook
    def start(self, api) -> bool:
        self.api = api
        self.sdk = PluginSDK(api, PLUGIN_NAME)
        self.session = requests.Session()
        self.session.trust_env = True
        self.session.verify = False
        return True

    @hook
    def get_name(self) -> str:
        return PLUGIN_NAME

    @hook
    def get_description(self) -> str:
        return "从剪贴板解析B站直播链接，选择清晰度后通过WebVPN在浏览器播放"

    @hook
    def get_menu(self) -> list[dict]:
        menu = PluginMenu()
        menu.add_func('解析B站直播', self.parse_bilibili)
        return menu.get_all()

    def _get_live_urls(self, bili_url: str) -> list:
        urls = []
        try:
            res = self.session.get(
                bili_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
                },
                cookies={"TWFID": self.api.webvpn.twfid} if self.api.webvpn.twfid else {},
                timeout=3,
            )
        except Exception as e:
            self.sdk.logger_error(f"请求B站失败: {e}")
            return urls

        if res.status_code != 200:
            self.sdk.logger_error(f"B站请求返回 {res.status_code}")
            return urls

        try:
            data = res.content.decode()
            j = json.loads(
                _extract_text(data, "window.__NEPTUNE_IS_MY_WAIFU__=", "</script>")
            )
            streams = j["roomInitRes"]["data"]["playurl_info"]["playurl"]["stream"]

            for stream in streams:
                for fmt in stream["format"]:
                    for codec in fmt["codec"]:
                        for url_info in codec["url_info"]:
                            urls.append(
                                url_info["host"] + codec["base_url"] + url_info["extra"]
                            )
        except Exception as e:
            self.sdk.logger_error(f"解析B站直播流失败: {e}")

        return urls

    def parse_bilibili(self):
        if not self.api.webvpn.twfid:
            self.sdk.logger_error("未登录WebVPN，无法使用B站直播解析")
            return

        # 从剪贴板获取链接
        if self.api.app is None:
            self.sdk.logger_error("无法访问剪贴板")
            return
        cb = self.api.app.clipboard()
        link = cb.text().strip()
        if not link or ("live" not in link and "bilibili" not in link):
            self.sdk.logger_error("剪贴板内容不是有效的B站直播链接")
            return

        self.sdk.logger_info(f"正在解析: {link}")

        # 确保WebVPN已登录
        try:
            self.api.webvpn.autoLogin()
        except Exception as e:
            self.sdk.logger_error(f"WebVPN自动登录失败: {e}")
            return

        urls = self._get_live_urls(link)
        if not urls:
            self.sdk.logger_error("未获取到直播流地址")
            return

        # 构建简短选择列表
        short_urls = []
        hash_map = {}
        for i, x in enumerate(urls):
            label = x[:30] + f"...{i}"
            short_urls.append(label)
            hash_map[label] = x

        item = self.sdk.show_input_list("选择视频地址", "请选择直播源", short_urls)
        if item:
            raw_url = hash_map[item]
            final_url = (
                "http://hlsplayer-net-s.webvpn.stu.edu.cn:8118/embed?type=m3u8&src="
                + raw_url
            )
            import webbrowser
            webbrowser.open(final_url)
            self.sdk.logger_info(f"已打开直播: {item}")

