# -*- coding: utf-8 -*-
# 黄网视频 TVBox 四壳通用 Python Spider
# 站点: https://www.xxoosp8.buzz/
# 结构: 苹果CMS 69tang黑色模板, 首页直链播放页, player_aaaa.url直出m3u8(s8m3u8线路)
# 多域名镜像: xxoosp1-8.buzz
# 视频: /index.php/vod/play/id/{id}/sid/{sid}/nid/{nid}.html, 分类: /index.php/vod/type/id/{id}.html

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

# ==================== 分类配置 (5个) ====================
CATEGORIES = [
    {"type_id": "1", "type_name": "国产视频"},
    {"type_id": "2", "type_name": "番号视频"},
    {"type_id": "3", "type_name": "黄网视频"},
    {"type_id": "4", "type_name": "原创视频"},
    {"type_id": "5", "type_name": "独家视频"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://www.xxoosp8.buzz"
        self.rawSite = "https://www.xxoosp8.buzz"
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
        """从HTML中解析视频列表 (69tang模板, 首页直链播放页)"""
        vod_list = []
        # 匹配 <a href="/index.php/vod/play/id/{id}/sid/{sid}/nid/{nid}.html"> ... <img data-original="COVER" alt="TITLE">
        pattern = r'<a[^>]*href="/index\.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html"[^>]*>(.*?)</a>'
        for vid, sid, nid, content in re.findall(pattern, html, re.S):
            # 封面
            cover_m = re.search(r'data-original="([^"]+)"', content)
            if not cover_m:
                cover_m = re.search(r'data-src="([^"]+)"', content)
            cover = cover_m.group(1) if cover_m else ""
            # 标题 (alt属性)
            title_m = re.search(r'alt="([^"]+)"', content)
            title = title_m.group(1) if title_m else ""
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
        url = f"{self.siteUrl}/index.php/vod/type/id/{tid}.html"
        if page > 1:
            url = f"{self.siteUrl}/index.php/vod/type/id/{tid}/page/{page}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        # 分页
        pages = re.findall(r'/index\.php/vod/type/id/' + re.escape(tid) + r'/page/(\d+)\.html', html)
        max_page = max(int(p) for p in pages) if pages else 1
        result["page"] = page
        result["pagecount"] = max_page
        result["limit"] = 20
        result["total"] = max_page * 20
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
            # player_data JSON (用raw_decode处理大JSON)
            pd_m = re.search(r'player_aaaa\s*=\s*', html)
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
                        vod_data = pd.get('vod_data', {})
                        vod_name = vod_data.get('vod_name', '')
                    except Exception:
                        pass
            # 标题兜底
            if not vod_name:
                title_m = re.search(r'<title>(.*?)</title>', html, re.S)
                if title_m:
                    vod_name = title_m.group(1).split('详情介绍')[0].strip()
            if is_minor(vod_name):
                continue
            # 封面
            cover_m = re.search(r'data-original="([^"]+)"', html)
            if not cover_m:
                cover_m = re.search(r'poster="([^"]+)"', html)
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
        return "黄网视频 Spider loaded"

    def getName(self):
        return "黄网视频"

    def destroy(self):
        self._session = None
