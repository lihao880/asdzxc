# -*- coding: utf-8 -*-
# 星空福利视频 TVBox 四壳通用 Python Spider
# 站点: https://xkfldh1103.shop/
# 结构: 标准苹果CMS xkfl模板, 详情/index.php/vod/detail/id/{id}.html
# 播放/index.php/vod/play/id/{id}/sid/{sid}/nid/{nid}.html, player_aaaa.url直出m3u8(xjplayer)
# 视频卡片: 封面data-src懒加载, 标题在a的title属性

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
    {"type_id": "75", "type_name": "国产视频"},
    {"type_id": "88", "type_name": "日韩AV"},
    {"type_id": "94", "type_name": "蓝光超清"},
    {"type_id": "99", "type_name": "欧美视频"},
    {"type_id": "103", "type_name": "动漫精选"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://xkfldh1103.shop"
        self.rawSite = "https://xkfldh1103.shop"
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
        """从HTML中解析视频列表 (xkfl模板, 封面data-src, 标题在a的title属性)"""
        vod_list = []
        # 匹配 <a href="/index.php/vod/detail/id/{id}.html" title="TITLE">
        pattern = r'<a[^>]*href="/index\.php/vod/detail/id/(\d+)\.html"[^>]*title="([^"]*)"[^>]*>'
        for vid, title in re.findall(pattern, html):
            if not title or is_minor(title):
                continue
            vod_list.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": "",
                "vod_remarks": "",
            })
        # 提取封面 (data-src) - 按视频ID附近的img
        for vod in vod_list:
            vid = vod["vod_id"]
            # 找该视频ID附近的data-src
            idx = html.find('/index.php/vod/detail/id/' + vid + '.html')
            if idx > 0:
                nearby = html[max(0, idx-200):idx+500]
                cover_m = re.search(r'data-src="([^"]+\.(?:jpg|png|jpeg|webp))"', nearby)
                if not cover_m:
                    cover_m = re.search(r'<img[^>]*src="([^"]+\.(?:jpg|png|jpeg|webp))"', nearby)
                if cover_m:
                    vod["vod_pic"] = self._abs_url(cover_m.group(1))
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
            url = f"{self.siteUrl}/index.php/vod/type/id/{tid}.html"
        else:
            url = f"{self.siteUrl}/index.php/vod/type/id/{tid}/page/{page}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        # 分页
        pages = re.findall(r'/index\.php/vod/type/id/' + re.escape(tid) + r'/page/(\d+)\.html', html)
        max_page = max(int(p) for p in pages) if pages else 999
        result["page"] = page
        result["pagecount"] = max_page
        result["limit"] = 40
        result["total"] = max_page * 40
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
            # 详情页
            html = self._fetch(f"{self.siteUrl}/index.php/vod/detail/id/{vod_id}.html")
            if not html:
                continue
            # 标题
            title_m = re.search(r'<title>(.*?)</title>', html, re.S)
            vod_name = ""
            if title_m:
                vod_name = title_m.group(1).split('-星空福利')[0].strip()
                vod_name = vod_name.split('在线播放')[0].strip()
            if not vod_name:
                h1_m = re.search(r'<h[1-6][^>]*>(.*?)</h[1-6]>', html, re.S)
                if h1_m:
                    vod_name = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip()
            if is_minor(vod_name):
                continue
            # 封面
            cover_m = re.search(r'data-src="([^"]+\.(?:jpg|png|jpeg|webp))"', html)
            if not cover_m:
                cover_m = re.search(r'<img[^>]*src="([^"]+\.(?:jpg|png|jpeg|webp))"', html)
            vod_pic = cover_m.group(1) if cover_m else ""
            # 播放链接 (多线路/多集)
            play_links = re.findall(r'/index\.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html', html)
            vod_play_from = ""
            vod_play_url = ""
            if play_links:
                # 按sid分组 (不同线路)
                sources = {}
                for pid, sid, nid in play_links:
                    if sid not in sources:
                        sources[sid] = []
                    play_url = f"{self.siteUrl}/index.php/vod/play/id/{pid}/sid/{sid}/nid/{nid}.html"
                    sources[sid].append(f"第{nid}集${play_url}")
                from_list = []
                url_list = []
                for idx, (sid, episodes) in enumerate(sources.items()):
                    from_list.append(f"线路{idx+1}")
                    url_list.append("#".join(episodes))
                vod_play_from = "$$$".join(from_list)
                vod_play_url = "$$$".join(url_list)
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": self._abs_url(vod_pic),
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url,
            })
        result["list"] = vod_list
        return result

    # ==================== 4. playerContent ====================
    def playerContent(self, flag, id, vipFlags=None, *args):
        result = {}
        # id是播放页URL, 需要抓取播放页获取m3u8
        play_url = id
        if not play_url.startswith("http"):
            play_url = self._abs_url(play_url)
        m3u8_url = play_url
        # 如果是播放页URL, 抓取获取m3u8
        if '/vod/play/' in play_url:
            html = self._fetch(play_url)
            if html:
                # player_aaaa JSON (raw_decode)
                pa_m = re.search(r'player_aaaa\s*=\s*', html)
                if pa_m:
                    start = pa_m.end()
                    if start < len(html) and html[start] == '{':
                        try:
                            decoder = json.JSONDecoder()
                            pa, _ = decoder.raw_decode(html[start:])
                            m3u8_url = pa.get('url', play_url)
                        except Exception:
                            pass
                # 兜底: 直接找m3u8
                if m3u8_url == play_url:
                    m3u8_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                    if m3u8_m:
                        m3u8_url = m3u8_m.group(1)
        result["parse"] = 0
        result["jx"] = 0
        result["url"] = m3u8_url
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
        url = f"{self.siteUrl}/index.php/vod/search/wd/{key_enc}.html"
        html = self._fetch(url)
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
        return "星空福利视频 Spider loaded"

    def getName(self):
        return "星空福利视频"

    def destroy(self):
        self._session = None
