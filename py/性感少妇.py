# -*- coding: utf-8 -*-
# 性感少妇 TVBox 四壳通用 Python Spider
# 站点: https://kxepzh.xg377.vip/
# 结构: 自定义CMS(xxgyy模板), 详情页<mark id="bfz" data-user-name="第1集$m3u8">直出播放地址
# 视频: /voddetail/{id}.html, 分类: /vodtype/{id}.html, 搜索: /search/?wd={kw}

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

# ==================== 分类配置 (8个) ====================
CATEGORIES = [
    {"type_id": "82", "type_name": "国产黑料"},
    {"type_id": "83", "type_name": "传媒精选"},
    {"type_id": "84", "type_name": "中文字幕"},
    {"type_id": "85", "type_name": "明星换脸"},
    {"type_id": "86", "type_name": "欧美情色"},
    {"type_id": "87", "type_name": "日本无码"},
    {"type_id": "88", "type_name": "国产乱伦"},
    {"type_id": "89", "type_name": "卡通动漫"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://kxepzh.xg377.vip"
        self.rawSite = "https://kxepzh.xg377.vip"
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
        """从HTML中解析视频列表 (xxgyy模板, 封面data-src, 标题<cite>标签)"""
        vod_list = []
        # 匹配 <a href="/voddetail/{id}.html"> ... <img data-src="COVER"> ... <cite>TITLE</cite>
        pattern = r'<a[^>]*href="/voddetail/(\d+)\.html"[^>]*>(.*?)</a>'
        for vid, content in re.findall(pattern, html, re.S):
            # 封面
            cover_m = re.search(r'data-src="([^"]+)"', content)
            if not cover_m:
                cover_m = re.search(r'src="([^"]+\.(?:jpg|png|jpeg|webp))"', content)
            cover = cover_m.group(1) if cover_m else ""
            # 标题 (<cite>标签)
            title_m = re.search(r'<cite[^>]*>(.*?)</cite>', content, re.S)
            title = ""
            if title_m:
                title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            if not title:
                # 兜底: title属性或alt
                title_attr = re.search(r'title="([^"]+)"', content)
                alt_attr = re.search(r'alt="([^"]+)"', content)
                title = (title_attr.group(1) if title_attr else (alt_attr.group(1) if alt_attr else ""))
            if not title or is_minor(title):
                continue
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
        url = f"{self.siteUrl}/vodtype/{tid}.html"
        if page > 1:
            url = f"{self.siteUrl}/vodtype/{tid}-{page}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        # 分页
        pages = re.findall(r'/vodtype/' + re.escape(tid) + r'-(\d+)\.html', html)
        max_page = max(int(p) for p in pages) if pages else 1
        result["page"] = page
        result["pagecount"] = max_page
        result["limit"] = 36
        result["total"] = max_page * 36
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
            # 播放地址: <mark id="bfz" data-user-name="第1集$m3u8_url">
            play_url = ""
            play_from = "xxgyy"
            bfz_m = re.search(r'<mark[^>]*id="bfz"[^>]*data-user-name="([^"]*)"', html)
            if bfz_m:
                data = bfz_m.group(1)
                # 格式: 第1集$https://.../index.m3u8
                if '$' in data:
                    parts = data.split('$', 1)
                    play_url = parts[1].strip()
                else:
                    play_url = data.strip()
            # 兜底: 直接找m3u8
            if not play_url:
                m3u8_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                if m3u8_m:
                    play_url = m3u8_m.group(1)
            # 标题
            title_m = re.search(r'<title>(.*?)</title>', html, re.S)
            vod_name = ""
            if title_m:
                vod_name = title_m.group(1).split('-')[0].strip()
            if not vod_name:
                cite_m = re.search(r'<cite[^>]*>(.*?)</cite>', html, re.S)
                if cite_m:
                    vod_name = re.sub(r'<[^>]+>', '', cite_m.group(1)).strip()
            if is_minor(vod_name):
                continue
            # 封面
            cover_m = re.search(r'data-src="([^"]+)"', html)
            if not cover_m:
                cover_m = re.search(r'src="([^"]+\.(?:jpg|png|jpeg|webp))"', html)
            vod_pic = cover_m.group(1) if cover_m else ""
            if play_url and '$' not in play_url:
                play_url = f"第1集${play_url}"
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
        url = f"{self.siteUrl}/search/?wd={key_enc}"
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
        return "性感少妇 Spider loaded"

    def getName(self):
        return "性感少妇"

    def destroy(self):
        self._session = None
