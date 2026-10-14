# -*- coding: utf-8 -*-
# 前妻の丝袜 TVBox 四壳通用 Python Spider
# 站点: https://kbtuelec.qqdsw32.top/
# 结构: 自定义模板, 首页var Words双层编码(URL+%uXXXX), 详情页mark#bfz直出m3u8
# 详情: /index.php/vod/detail/id/{id}.html, m3u8在 <mark id="bfz" data-user-name="第1集$m3u8">

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

# ==================== 解码工具 ====================
def decode_words(html):
    """解码 var Words 双层编码: URL decode + %uXXXX JS unicode decode"""
    m = re.search(r'var Words\s*=\s*"([^"]+)"', html)
    if not m:
        return html
    encoded = m.group(1)
    # 第一层: URL decode
    decoded = urllib.parse.unquote(encoded)
    # 第二层: %uXXXX JS unicode decode
    def replacer(mm):
        return chr(int(mm.group(1), 16))
    full = re.sub(r'%u([0-9a-fA-F]{4})', replacer, decoded)
    return full

# ==================== 分类配置 (18个) ====================
CATEGORIES = [
    {"type_id": "1", "type_name": "精品推荐"},
    {"type_id": "2", "type_name": "国产主播"},
    {"type_id": "3", "type_name": "强奸乱伦"},
    {"type_id": "4", "type_name": "自拍偷拍"},
    {"type_id": "5", "type_name": "制服诱惑"},
    {"type_id": "6", "type_name": "网曝事件"},
    {"type_id": "7", "type_name": "传媒探花"},
    {"type_id": "8", "type_name": "清纯学生"},
    {"type_id": "9", "type_name": "淫妻作乐"},
    {"type_id": "10", "type_name": "足浴撩妹"},
    {"type_id": "11", "type_name": "反差母狗"},
    {"type_id": "12", "type_name": "丝袜美腿"},
    {"type_id": "13", "type_name": "中文字幕"},
    {"type_id": "14", "type_name": "无码流出"},
    {"type_id": "15", "type_name": "多人群交"},
    {"type_id": "16", "type_name": "欧美激情"},
    {"type_id": "17", "type_name": "人妻熟女"},
    {"type_id": "18", "type_name": "主奴调教"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://kbtuelec.qqdsw32.top"
        self.rawSite = "https://kbtuelec.qqdsw32.top"
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
        """从HTML中解析视频列表"""
        vod_list = []
        # 匹配 <a class="ss/sw" href="/index.php/vod/detail/id/{id}.html">
        pattern = r'<a[^>]*class="s[sw]"[^>]*href="/index\.php/vod/detail/id/(\d+)\.html"[^>]*>(.*?)</a>'
        for vid, content in re.findall(pattern, html, re.S):
            # 封面
            cover_m = re.search(r'data-src="([^"]+)"', content)
            if not cover_m:
                cover_m = re.search(r'data-original="([^"]+)"', content)
            cover = cover_m.group(1) if cover_m else ""
            # 标题
            title_m = re.search(r'<cite[^>]*>(.*?)</cite>', content, re.S)
            if title_m:
                title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            else:
                alt_m = re.search(r'alt="([^"]+)"', content)
                title = alt_m.group(1) if alt_m else ""
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
        # 首页需要解码var Words
        html = self._fetch(self.siteUrl + "/")
        if html:
            full_html = decode_words(html)
            result["list"] = self._parse_videos(full_html)
        else:
            result["list"] = []
        return result

    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, page=1, *args):
        result = {}
        page = int(page)
        url = f"{self.siteUrl}/index.php/vod/type/id/{tid}.html"
        if page > 1:
            url = f"{self.siteUrl}/index.php/vod/type/id/{tid}/page/{page}.html"
        html = self._fetch(url)
        # 分类页可能也有Words编码
        if 'var Words' in html:
            html = decode_words(html)
        vod_list = self._parse_videos(html)
        # 分页
        pages = re.findall(r'/index\.php/vod/type/id/' + re.escape(tid) + r'/page/(\d+)', html)
        max_page = max(int(p) for p in pages) if pages else 1
        result["page"] = page
        result["pagecount"] = max_page
        result["limit"] = 16
        result["total"] = max_page * 16
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
            html = self._fetch(f"{self.siteUrl}/index.php/vod/detail/id/{vod_id}.html")
            if not html:
                continue
            # 详情页可能也有Words编码
            if 'var Words' in html:
                html = decode_words(html)
            # 标题
            title_m = re.search(r'<title>(.*?)</title>', html, re.S)
            vod_name = title_m.group(1).strip() if title_m else ""
            # 从片名cite提取
            cite_m = re.search(r'片名[：:]\s*(.*?)</cite>', html, re.S)
            if cite_m:
                vod_name = re.sub(r'<[^>]+>', '', cite_m.group(1)).strip()
            if is_minor(vod_name):
                continue
            # 封面 (过滤广告图, 取首个非广告图)
            all_covers = re.findall(r'data-src="([^"]+)"', html)
            vod_pic = ""
            for c in all_covers:
                if 'alicdn' not in c and 'fleamarket' not in c and 'taobao' not in c:
                    vod_pic = c
                    break
            if not vod_pic:
                cover_m = re.search(r'data-original="([^"]+)"', html)
                vod_pic = cover_m.group(1) if cover_m else ""
            # m3u8: <mark id="bfz" data-user-name="第1集$m3u8">
            bfz_m = re.search(r'<mark[^>]*id="bfz"[^>]*data-user-name="([^"]+)"', html)
            vod_play_url = bfz_m.group(1) if bfz_m else ""
            if vod_play_url and '$' not in vod_play_url:
                vod_play_url = f"第1集${vod_play_url}"
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": self._abs_url(vod_pic),
                "vod_play_from": "HD高清",
                "vod_play_url": vod_play_url,
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
            url = f"{self.siteUrl}/index.php/vod/search.html?wd={key_enc}&page={page}"
        html = self._fetch(url)
        if 'var Words' in html:
            html = decode_words(html)
        vod_list = self._parse_videos(html)
        result["page"] = page
        result["pagecount"] = 1
        result["limit"] = 16
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
        return "前妻の丝袜 Spider loaded"

    def getName(self):
        return "前妻の丝袜"

    def destroy(self):
        self._session = None
