# -*- coding: utf-8 -*-
# 极乐AV天堂 TVBox 四壳通用 Python Spider
# 站点: https://n68w8w.kppsolid.buzz/
# 结构: 自定义CMS(kopapa模板), Cloudflare防护, 视频卡片封面在style=background:url(), 播放页player_data.url直出m3u8
# 视频: /voddetail/{id}/, 播放: /vodplay/{id}-{sid}-{nid}/, 分类: /vodtype/{id}/, 搜索: /vodsearch/{wd}-------------/

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
    {"type_id": "18", "type_name": "大地资源"},
    {"type_id": "48", "type_name": "桃花资源"},
    {"type_id": "61", "type_name": "森林资源"},
    {"type_id": "132", "type_name": "杏吧资源"},
    {"type_id": "154", "type_name": "色猫资源"},
    {"type_id": "268", "type_name": "奶香香资源"},
    {"type_id": "296", "type_name": "奥斯卡资源"},
    {"type_id": "347", "type_name": "乐播资源"},
    {"type_id": "365", "type_name": "番号资源"},
    {"type_id": "382", "type_name": "黄色仓库"},
    {"type_id": "423", "type_name": "麻豆资源"},
    {"type_id": "600", "type_name": "极品资源"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://n68w8w.kppsolid.buzz"
        self.rawSite = "https://n68w8w.kppsolid.buzz"
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
        """从HTML中解析视频列表 (kopapa模板, 封面在style=background:url())"""
        vod_list = []
        # 匹配 <a href="/voddetail/{id}/" title="TITLE" ... style="background:...url(COVER)...">
        pattern = r'<a[^>]*href="/voddetail/(\d+)/"[^>]*title="([^"]*)"[^>]*>'
        for vid, title in re.findall(pattern, html):
            if not title or is_minor(title):
                continue
            # 封面: 从style属性提取url()
            cover = ""
            # 找这个a标签的完整内容
            a_start = html.find(f'/voddetail/{vid}/"')
            if a_start > 0:
                tag_start = html.rfind('<a', 0, a_start)
                tag_end = html.find('>', a_start)
                if tag_start > 0 and tag_end > 0:
                    tag = html[tag_start:tag_end+1]
                    style_m = re.search(r'style="[^"]*url\(([^)]+)\)', tag)
                    if style_m:
                        cover = style_m.group(1).strip().strip("'\"")
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
        html = self._fetch(self.siteUrl + "/gao/")
        result["list"] = self._parse_videos(html) if html else []
        return result

    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, page=1, *args):
        result = {}
        page = int(page)
        url = f"{self.siteUrl}/vodtype/{tid}/"
        if page > 1:
            url = f"{self.siteUrl}/vodtype/{tid}-{page}/"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        # 分页
        pages = re.findall(r'/vodtype/' + re.escape(tid) + r'-(\d+)/', html)
        max_page = max(int(p) for p in pages) if pages else 1
        result["page"] = page
        result["pagecount"] = max_page
        result["limit"] = 24
        result["total"] = max_page * 24
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
            html = self._fetch(f"{self.siteUrl}/vodplay/{vod_id}-1-1/")
            if not html:
                continue
            # player_data JSON (用raw_decode处理大JSON)
            pd_m = re.search(r'var\s+player_data\s*=\s*', html)
            play_url = ""
            play_from = "HD高清"
            vod_name = ""
            if pd_m:
                start = pd_m.end()
                if start < len(html) and html[start] == '{':
                    try:
                        decoder = json.JSONDecoder()
                        pd, _ = decoder.raw_decode(html[start:])
                        play_url = pd.get('url', '')
                        play_from = pd.get('from', 'HD高清')
                    except Exception:
                        pass
            # 标题 (按"详情介绍"分割)
            title_m = re.search(r'<title>(.*?)</title>', html, re.S)
            if title_m:
                full_title = title_m.group(1)
                vod_name = full_title.split('详情介绍')[0].strip()
            if not vod_name:
                h1_m = re.search(r'<h[1-6][^>]*>(.*?)</h[1-6]>', html, re.S)
                if h1_m:
                    vod_name = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip()
            if is_minor(vod_name):
                continue
            # 封面
            cover_m = re.search(r'poster="([^"]+)"', html)
            if not cover_m:
                cover_m = re.search(r'style="[^"]*url\(([^)]+)\)', html)
            vod_pic = cover_m.group(1).strip().strip("'\"") if cover_m else ""
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
        url = f"{self.siteUrl}/vodsearch/{key_enc}-------------/"
        if page > 1:
            url += f"{page}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        result["page"] = page
        result["pagecount"] = 1
        result["limit"] = 36
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
        return "极乐AV天堂 Spider loaded"

    def getName(self):
        return "极乐AV天堂"

    def destroy(self):
        self._session = None
