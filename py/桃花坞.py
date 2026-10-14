# -*- coding: utf-8 -*-
# 桃花坞 TVBox 四壳通用 Python Spider
# 站点: https://thw1034.lol/
# 结构: 苹果CMS taohua模板, 无独立详情页(播放页兼详情), player_aaaa.url直出m3u8
# 播放: /index.php/vod/play/id/{id}/sid/{sid}/nid/{nid}.html

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

# ==================== 分类配置 (12个) ====================
CATEGORIES = [
    {"type_id": "1", "type_name": "国产精品"},
    {"type_id": "2", "type_name": "华语AV"},
    {"type_id": "3", "type_name": "黑料吃瓜"},
    {"type_id": "4", "type_name": "欧美"},
    {"type_id": "5", "type_name": "禁漫"},
    {"type_id": "6", "type_name": "学生"},
    {"type_id": "7", "type_name": "乱伦"},
    {"type_id": "8", "type_name": "探花"},
    {"type_id": "9", "type_name": "日本无码"},
    {"type_id": "10", "type_name": "日本有码"},
    {"type_id": "11", "type_name": "主播网红"},
    {"type_id": "12", "type_name": "日本素人"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://thw1034.lol"
        self.rawSite = "https://thw1034.lol"
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
        """从HTML中解析视频列表 (卡片直接链播放页)"""
        vod_list = []
        # 匹配 <a href="/index.php/vod/play/id/{id}/sid/{sid}/nid/{nid}.html"> ... <img data-src="COVER" alt="TITLE">
        pattern = r'<a[^>]*href="/index\.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html"[^>]*>(.*?)</a>'
        for vid, sid, nid, content in re.findall(pattern, html, re.S):
            # 封面
            cover_m = re.search(r'data-(?:original|src|lazy)="([^"]+)"', content)
            if not cover_m:
                cover_m = re.search(r'src="([^"]+)"', content)
            cover = cover_m.group(1) if cover_m else ""
            if cover and ('placeholder' in cover or 'logo' in cover):
                cover = ""
            # 标题
            title_m = re.search(r'alt="([^"]+)"', content)
            title = title_m.group(1) if title_m else ""
            if not title:
                # 从cite/title标签提取
                cite_m = re.search(r'<cite[^>]*>(.*?)</cite>', content, re.S)
                if cite_m:
                    title = re.sub(r'<[^>]+>', '', cite_m.group(1)).strip()
            if not title or is_minor(title):
                continue
            vod_list.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._abs_url(cover),
                "vod_remarks": "",
            })
        return vod_list

    # ==================== 解析player_aaaa ====================
    def _parse_player_aaaa(self, html):
        """从播放页HTML中解析player_aaaa JSON (用raw_decode处理大JSON)"""
        m = re.search(r'player_aaaa\s*=\s*', html)
        if not m:
            return None
        start = m.end()
        # 从{开始用raw_decode精确解析
        if start < len(html) and html[start] == '{':
            try:
                decoder = json.JSONDecoder()
                obj, end = decoder.raw_decode(html[start:])
                return obj
            except Exception:
                pass
        # 回退: 正则匹配
        m2 = re.search(r'player_aaaa\s*=\s*({.*?})\s*;', html, re.S)
        if m2:
            try:
                return json.loads(m2.group(1))
            except Exception:
                return None
        return None

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
        url = f"{self.siteUrl}/index.php/vod/type/id/{tid}.html"
        if page > 1:
            url = f"{self.siteUrl}/index.php/vod/type/id/{tid}-page-{page}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        # 分页
        pages = re.findall(r'/index\.php/vod/type/id/' + re.escape(tid) + r'[/-]page[/-](\d+)', html)
        max_page = max(int(p) for p in pages) if pages else 1
        result["page"] = page
        result["pagecount"] = max_page
        result["limit"] = 16
        result["total"] = max_page * 16
        result["list"] = vod_list
        return result

    # ==================== 3. detailContent (播放页兼详情) ====================
    def detailContent(self, ids, *args):
        result = {}
        vod_list = []
        if isinstance(ids, str):
            ids = [ids]
        for vod_id in ids:
            if not vod_id:
                continue
            # 播放页兼详情页
            html = self._fetch(f"{self.siteUrl}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html")
            if not html:
                continue
            pa = self._parse_player_aaaa(html)
            if not pa:
                continue
            vod_data = pa.get('vod_data', {})
            vod_name = vod_data.get('vod_name', '')
            if not vod_name:
                title_m = re.search(r'<title>(.*?)</title>', html, re.S)
                vod_name = title_m.group(1).strip() if title_m else ""
            if is_minor(vod_name):
                continue
            # 播放地址
            play_url = pa.get('url', '')
            play_from = pa.get('from', 'HD高清')
            if play_url and '$' not in play_url:
                play_url = f"第1集${play_url}"
            # 封面 (从页面中找)
            cover_m = re.search(r'data-(?:original|src|lazy)="([^"]+)"', html)
            vod_pic = cover_m.group(1) if cover_m else ""
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": self._abs_url(vod_pic),
                "vod_play_from": play_from,
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
        url = f"{self.siteUrl}/index.php/vod/search.html?wd={key_enc}"
        if page > 1:
            url += f"&page={page}"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
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
        return "桃花坞 Spider loaded"

    def getName(self):
        return "桃花坞"

    def destroy(self):
        self._session = None
