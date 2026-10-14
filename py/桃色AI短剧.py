# -*- coding: utf-8 -*-
# 桃色AI短剧 TVBox 四壳通用 Python Spider
# 站点: https://taosenura.buzz/
# 结构: 自定义CMS(taose模板), 分类/type/id/{id}/{page}.html, 详情/info/id/{id}.html
# 播放页/play/id/{id}.html, m3u8直接在JS中, 视频卡片<a title=标题><img src=封面>

import re
import json
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

# ==================== 分类配置 (44个, 已过滤id=306萝莉群交) ====================
CATEGORIES = [
    {"type_id": "295", "type_name": "无码热门"},
    {"type_id": "297", "type_name": "制服乱伦"},
    {"type_id": "298", "type_name": "三级性交"},
    {"type_id": "299", "type_name": "换脸淫梦"},
    {"type_id": "300", "type_name": "中文精选"},
    {"type_id": "301", "type_name": "卡通动漫"},
    {"type_id": "302", "type_name": "欧美系列"},
    {"type_id": "303", "type_name": "美女主播"},
    {"type_id": "304", "type_name": "国产自拍"},
    {"type_id": "305", "type_name": "熟女有码"},
    {"type_id": "307", "type_name": "女同性爱"},
    {"type_id": "308", "type_name": "多人群交"},
    {"type_id": "309", "type_name": "美乳巨乳"},
    {"type_id": "310", "type_name": "强奸调教"},
    {"type_id": "311", "type_name": "抖阴视频"},
    {"type_id": "312", "type_name": "韩国主播"},
    {"type_id": "313", "type_name": "网红头条"},
    {"type_id": "314", "type_name": "网爆黑料"},
    {"type_id": "315", "type_name": "欧美无码"},
    {"type_id": "316", "type_name": "女优明星"},
    {"type_id": "317", "type_name": "SM调教"},
    {"type_id": "326", "type_name": "AV在线"},
    {"type_id": "702", "type_name": "国产自拍"},
    {"type_id": "703", "type_name": "主播诱惑"},
    {"type_id": "704", "type_name": "探花约炮"},
    {"type_id": "705", "type_name": "偷拍偷窥"},
    {"type_id": "706", "type_name": "网曝吃瓜"},
    {"type_id": "707", "type_name": "抖阴短片"},
    {"type_id": "708", "type_name": "传媒剧情"},
    {"type_id": "709", "type_name": "日韩主播"},
    {"type_id": "710", "type_name": "日韩无码"},
    {"type_id": "711", "type_name": "中文字幕"},
    {"type_id": "712", "type_name": "AV解说"},
    {"type_id": "713", "type_name": "换脸明星"},
    {"type_id": "714", "type_name": "强奸乱伦"},
    {"type_id": "715", "type_name": "女优明星"},
    {"type_id": "716", "type_name": "欧美激情"},
    {"type_id": "717", "type_name": "重口激情"},
    {"type_id": "718", "type_name": "三级伦理"},
    {"type_id": "719", "type_name": "剧情动漫"},
    {"type_id": "720", "type_name": "SM调教"},
    {"type_id": "721", "type_name": "女同性恋"},
    {"type_id": "722", "type_name": "VR视角"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://taosenura.buzz"
        self.rawSite = "https://taosenura.buzz"
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

    # ==================== HTTP ====================
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

    def _fetch(self, url, timeout=15):
        session = self._get_session()
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text
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
        """从HTML中解析视频列表 (taose模板, 标题在a的title属性, 封面在img src)"""
        vod_list = []
        # 匹配 <a href="/info/id/{id}.html" ... title="TITLE"> ... <img src="COVER">
        pattern = r'<a[^>]*href="/info/id/(\d+)\.html"[^>]*title="([^"]*)"[^>]*>(.*?)</a>'
        for vid, title, content in re.findall(pattern, html, re.S):
            if not title or is_minor(title):
                continue
            # 封面
            cover_m = re.search(r'<img[^>]*src="([^"]+\.(?:jpg|png|jpeg|webp))"', content)
            if not cover_m:
                cover_m = re.search(r'data-(?:original|src|lazy)="([^"]+)"', content)
            cover = cover_m.group(1) if cover_m else ""
            vod_list.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._abs_url(cover),
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
        result["list"] = self._parse_videos(html) if html else []
        return result

    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, page=1, *args):
        result = {}
        page = int(page)
        if page <= 1:
            url = f"{self.siteUrl}/type/id/{tid}.html"
        else:
            url = f"{self.siteUrl}/type/id/{tid}/{page}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        # 分页
        pages = re.findall(r'/type/id/' + re.escape(tid) + r'/(\d+)\.html', html)
        max_page = max(int(p) for p in pages) if pages else 999
        result["page"] = page
        result["pagecount"] = max_page
        result["limit"] = 20
        result["total"] = max_page * 20
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
            # 播放页 (兼详情, m3u8直接在JS中)
            html = self._fetch(f"{self.siteUrl}/play/id/{vod_id}.html")
            if not html:
                continue
            # 标题
            title_m = re.search(r'<title>(.*?)</title>', html, re.S)
            vod_name = ""
            if title_m:
                vod_name = title_m.group(1).split('正在火热播放')[0].strip()
                vod_name = vod_name.split('-AI成人短剧')[0].strip()
                vod_name = vod_name.split('-详情页')[0].strip()
            if not vod_name:
                vod_name = vod_id
            if is_minor(vod_name):
                continue
            # 封面
            cover_m = re.search(r'<img[^>]*src="([^"]+\.(?:jpg|png|jpeg|webp))"', html)
            vod_pic = cover_m.group(1) if cover_m else ""
            # m3u8 (直接在JS中)
            play_url = ""
            m3u8_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
            if m3u8_m:
                play_url = m3u8_m.group(1).rstrip("';")
            # 兜底: JS变量中的m3u8
            if not play_url:
                js_m3u8 = re.findall(r'["\']([^"\']*\.m3u8[^"\']*)["\']', html)
                if js_m3u8:
                    play_url = js_m3u8[0]
            if play_url and '$' not in play_url:
                play_url = f"第1集${play_url}"
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": self._abs_url(vod_pic),
                "vod_play_from": "default",
                "vod_play_url": play_url,
            })
        result["list"] = vod_list
        return result

    # ==================== 4. playerContent ====================
    def playerContent(self, flag, id, vipFlags=None, *args):
        result = {}
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
        page = int(page)
        key_enc = urllib.parse.quote(key)
        # 尝试多种搜索格式
        html = ""
        for url in [
            f"{self.siteUrl}/search/wd/{key_enc}.html",
            f"{self.siteUrl}/search.html?wd={key_enc}",
            f"{self.siteUrl}/?wd={key_enc}",
            f"{self.siteUrl}/index.php?wd={key_enc}",
        ]:
            html = self._fetch(url)
            if html and '/info/id/' in html:
                break
        vod_list = self._parse_videos(html) if html else []
        result["page"] = page
        result["pagecount"] = 1
        result["limit"] = 20
        result["total"] = len(vod_list)
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
        return "桃色AI短剧 Spider loaded"

    def getName(self):
        return "桃色AI短剧"

    def destroy(self):
        self._session = None
