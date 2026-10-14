# -*- coding: utf-8 -*-
# 疯狂乱撸 TVBox 四壳通用 Python Spider
# 站点: https://5uxzglz7x.luanlu32.vip/
# 结构: 自定义CMS, 全站atob+charcode混淆, 详情/voddetail/{id}, m3u8在mark data-user-name
# 分类: /vodtype/{id}.html, 搜索: /vod/search.html?wd=, 列表: article.video_link

import re
import json
import base64
import urllib.parse

try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def __init__(self):
            self.extend = {}

# ==================== 未成年过滤 ====================
MINOR_KEYWORDS = ['萝莉', '幼女', '少女', '童', 'teen', 'loli', 'schoolgirl', '未成年']

def is_minor(text):
    if not text:
        return False
    t = text.lower()
    return any(kw.lower() in t for kw in MINOR_KEYWORDS)

# ==================== 分类配置 (20个) ====================
CATEGORIES = [
    {"type_id": "21", "type_name": "视频②区"},
    {"type_id": "40", "type_name": "国产视频"},
    {"type_id": "41", "type_name": "中文字幕"},
    {"type_id": "42", "type_name": "国产传媒"},
    {"type_id": "43", "type_name": "日本有码"},
    {"type_id": "44", "type_name": "日本无码"},
    {"type_id": "45", "type_name": "欧美无码"},
    {"type_id": "46", "type_name": "美女主播"},
    {"type_id": "47", "type_name": "激情动漫"},
    {"type_id": "48", "type_name": "明星换脸"},
    {"type_id": "50", "type_name": "女优明星"},
    {"type_id": "51", "type_name": "SM调教"},
    {"type_id": "52", "type_name": "网红头条"},
    {"type_id": "53", "type_name": "极品媚黑"},
    {"type_id": "54", "type_name": "人妖系列"},
    {"type_id": "55", "type_name": "VR视角"},
    {"type_id": "56", "type_name": "伦理三级"},
    {"type_id": "57", "type_name": "女同性恋"},
    {"type_id": "58", "type_name": "AV解说"},
    {"type_id": "59", "type_name": "清纯素女"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://5uxzglz7x.luanlu32.vip"
        self.rawSite = "https://5uxzglz7x.luanlu32.vip"
        self.HOST = self.siteUrl
        self._session = None

    def init(self, extend=""):
        if extend and isinstance(extend, str):
            try:
                self.extend = json.loads(extend)
            except Exception:
                self.extend = {}
        elif isinstance(extend, dict):
            self.extend = extend
        else:
            self.extend = {}
        if self.extend.get("siteUrl"):
            self.siteUrl = self.extend["siteUrl"]
            self.HOST = self.siteUrl
        if self.extend.get("proxy"):
            self.siteUrl = self.extend["proxy"]
            self.HOST = self.siteUrl

    # ==================== HTTP + 混淆解码 ====================
    def _get_session(self):
        if self._session is None:
            if HAS_CURL_CFFI:
                self._session = curl_requests.Session(impersonate="chrome131")
            else:
                import requests as req_lib
                self._session = req_lib.Session()
                self._session.headers.update({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                })
        return self._session

    def _decode_page(self, html):
        """解码atob+charcode混淆的页面"""
        if not html:
            return html
        m = re.search(r'atob\("([^"]+)"\)', html)
        if m:
            try:
                decoded = base64.b64decode(m.group(1)).decode('utf-8')
                char_codes = json.loads(decoded)
                if isinstance(char_codes, list) and len(char_codes) > 10:
                    return bytes(char_codes).decode('utf-8', errors='ignore')
            except Exception:
                pass
        return html

    def _fetch(self, url, timeout=15):
        session = self._get_session()
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200:
                return self._decode_page(resp.text)
        except Exception:
            pass
        return ""

    def _abs_url(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.siteUrl + url
        return self.siteUrl + "/" + url

    # ==================== 解析视频列表 ====================
    def _parse_videos(self, html):
        vod_list = []
        # article.video_link 结构
        pattern = re.compile(
            r'<a[^>]*href="/vodplay/(\d+)-\d+-\d+\.html"[^>]*class="video_link"[^>]*>.*?'
            r'data-src="([^"]+)".*?'
            r'<cite>([^<]+)</cite>',
            re.S
        )
        for m in pattern.finditer(html):
            vod_id = m.group(1)
            vod_pic = self._abs_url(m.group(2).strip())
            vod_name = m.group(3).strip()
            if is_minor(vod_name):
                continue
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": "",
            })
        return vod_list

    # ==================== 1. homeContent ====================
    def homeContent(self, *args):
        result = {}
        classes = [{"type_id": c["type_id"], "type_name": c["type_name"]} for c in CATEGORIES]
        result["class"] = classes
        filters = {}
        for c in CATEGORIES:
            filters[c["type_id"]] = []
        result["filters"] = filters
        html = self._fetch(self.siteUrl + "/")
        result["list"] = self._parse_videos(html)
        return result

    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, page=1, *args):
        result = {}
        page = int(page)
        if page <= 1:
            url = f"{self.siteUrl}/vodtype/{tid}.html"
        else:
            url = f"{self.siteUrl}/vodtype/{tid}-{page}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        result["page"] = page
        result["pagecount"] = 999
        result["limit"] = 20
        result["total"] = 999 * 20
        result["list"] = vod_list
        return result

    # ==================== 3. detailContent ====================
    def detailContent(self, ids, *args):
        result = {}
        vod_list = []
        if isinstance(ids, str):
            ids = [ids]
        for vod_id in ids:
            if not vod_id:
                continue
            html = self._fetch(f"{self.siteUrl}/voddetail/{vod_id}.html")
            if not html:
                continue
            # 标题: title格式 "站点名-视频标题-描述后缀", 取中间部分
            vod_name = ""
            title_m = re.search(r'<title>(.*?)</title>', html, re.S)
            if title_m:
                raw = title_m.group(1).strip()
                parts = raw.split('-')
                if len(parts) >= 3:
                    # 去掉首段(站点名)和末段(描述后缀), 中间用-连接
                    vod_name = '-'.join(parts[1:-1]).strip()
                elif len(parts) == 2:
                    vod_name = parts[1].strip()
                else:
                    vod_name = raw
            if is_minor(vod_name):
                continue
            # 封面: 第一个data-src
            cover_m = re.search(r'data-src="([^"]+)"', html)
            vod_pic = self._abs_url(cover_m.group(1).strip()) if cover_m else ""
            # m3u8: mark#bfz data-user-name="第N集$URL"
            play_url = ""
            bfz_m = re.search(r'id="bfz"[^>]*data-user-name="([^"]+)"', html)
            if bfz_m:
                data = bfz_m.group(1)
                if '$' in data:
                    play_url = data.split('$', 1)[1].strip()
            # 构造播放列表
            vod_play_from = "HD高清"
            vod_play_url = f"第1集${play_url}" if play_url else ""
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url,
            })
        result["list"] = vod_list
        return result

    # ==================== 4. playerContent ====================
    def playerContent(self, flag, id, vipFlags=None, *args):
        result = {}
        # id 是直接的m3u8 URL
        play_url = id if id.startswith("http") else self._abs_url(id)
        result["parse"] = 0
        result["jx"] = 0
        result["url"] = play_url
        result["header"] = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": self.rawSite + "/",
            "Origin": self.rawSite,
        }
        return result

    # ==================== 5. searchContent ====================
    def searchContent(self, key, page=1, *args):
        result = {}
        key_enc = urllib.parse.quote(key)
        page = int(page)
        if page <= 1:
            url = f"{self.siteUrl}/vod/search.html?wd={key_enc}"
        else:
            url = f"{self.siteUrl}/vod/search.html?wd={key_enc}&page={page}"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        result["page"] = page
        result["pagecount"] = 99
        result["limit"] = 20
        result["total"] = 99 * 20
        result["list"] = vod_list
        return result

    # ==================== 6. localProxy ====================
    def localProxy(self, param):
        try:
            if isinstance(param, str):
                params = urllib.parse.parse_qs(param)
            else:
                params = param or {}
            url = params.get("url", [""])[0] if isinstance(params, dict) else ""
            if not url:
                return [404, "text/plain", ""]
            html = self._fetch(url, timeout=10)
            if not html:
                return [404, "text/plain", "fetch failed"]
            cleaned = self._clean_m3u8(html, url)
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception:
            return [404, "text/plain", ""]

    def _clean_m3u8(self, content, base_url=""):
        lines = content.split("\n")
        cleaned = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if self._is_ad_segment(line):
                continue
            if line.startswith("#EXT-X-MEDIA-SEQUENCE"):
                cleaned.append("#EXT-X-MEDIA-SEQUENCE:0")
                continue
            cleaned.append(line)
        return "\n".join(cleaned)

    def _is_ad_segment(self, line):
        if not line or line.startswith("#"):
            return False
        ad_keywords = ["ad", "gg", "adv", "preroll", "片头", "广告"]
        return any(kw in line.lower() for kw in ad_keywords)

    # ==================== 7. 其他接口 ====================
    def isVideoFormat(self, url):
        return any(url.endswith(ext) for ext in [".m3u8", ".mp4", ".mkv", ".avi", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return "疯狂乱撸 Spider loaded"

    def getName(self):
        return "疯狂乱撸"

    def destroy(self):
        self._session = None
