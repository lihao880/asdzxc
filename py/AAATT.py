# -*- coding: utf-8 -*-
# AAATT TVBox 四壳通用 Python Spider
# 站点: https://qtuip.aaatt60.sbs/
# 结构: 自定义CMS(aatt模板), 分类名d()编码(atob+escape+decodeURIComponent), 视频页Hls.js直出m3u8
# 多域名: 支持*.aaatt60.sbs子域名镜像
# 视频: /video.php?id={id}, 分类: /list.php?id={cid}&page={page}, 搜索: /search.php?content={kw}

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

# ==================== d()解码工具 ====================
def d_decode(encoded):
    """对应站点d()函数: atob → escape → decodeURIComponent
    实际效果 = base64 decode → UTF-8 decode"""
    try:
        return base64.b64decode(encoded).decode('utf-8', errors='replace')
    except Exception:
        return ""

def extract_visible_text(text):
    """从HTML中提取可见文本, 去掉display:none的隐藏内容和标签"""
    if not text:
        return ""
    # 如果包含document.write(d()), 先解码
    dw_m = re.search(r"document\.write\s*\(\s*d\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\)", text)
    if dw_m:
        text = d_decode(dw_m.group(1))
    # 去掉display:none的span
    text = re.sub(r'<span[^>]*display:\s*none[^>]*>.*?</span>', '', text, flags=re.S|re.I)
    # 去掉所有标签
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

# ==================== 未成年过滤 ====================
MINOR_KEYWORDS = ['萝莉', '幼女', '少女', '童', 'teen', 'loli', 'schoolgirl', '未成年']

def is_minor(text):
    if not text:
        return False
    t = text.lower()
    return any(kw.lower() in t for kw in MINOR_KEYWORDS)

# ==================== 分类配置 (16个) ====================
CATEGORIES = [
    {"type_id": "8787634", "type_name": "精品推荐"},
    {"type_id": "8797634", "type_name": "国产传媒"},
    {"type_id": "8807634", "type_name": "探花系列"},
    {"type_id": "8817634", "type_name": "偷拍自拍"},
    {"type_id": "8827634", "type_name": "熟女少妇"},
    {"type_id": "8837634", "type_name": "无码专区"},
    {"type_id": "8847634", "type_name": "欧美激情"},
    {"type_id": "8857634", "type_name": "颜值正义"},
    {"type_id": "8887644", "type_name": "美乳巨乳"},
    {"type_id": "8897644", "type_name": "网曝事件"},
    {"type_id": "8907644", "type_name": "国产主播"},
    {"type_id": "8917644", "type_name": "中文字幕"},
    {"type_id": "8927644", "type_name": "制服丝袜"},
    {"type_id": "8937644", "type_name": "口交自慰"},
    {"type_id": "8947644", "type_name": "国产精品"},
    {"type_id": "8957644", "type_name": "大秀视频"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://qtuip.aaatt60.sbs"
        self.rawSite = "https://qtuip.aaatt60.sbs"
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
        """从HTML中解析视频列表 (vod-card结构)"""
        vod_list = []
        # 匹配 <li class="vod-card"> ... </li>
        cards = re.findall(r'<li class="vod-card">(.*?)</li>', html, re.S)
        for card in cards:
            # 视频ID
            vid_m = re.search(r'/video\.php\?id=(\d+)', card)
            if not vid_m:
                continue
            vid = vid_m.group(1)
            # 封面
            cover_m = re.search(r'data-original="([^"]+)"', card)
            if not cover_m:
                cover_m = re.search(r'data-src="([^"]+)"', card)
            cover = cover_m.group(1) if cover_m else ""
            # 标题 (card-title中的a标签文本, 可能含document.write编码)
            title_m = re.search(r'<h5 class="card-title">(.*?)</h5>', card, re.S)
            title = ""
            if title_m:
                title = extract_visible_text(title_m.group(1))
            if not title:
                alt_m = re.search(r'alt="([^"]+)"', card)
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
        html = self._fetch(self.siteUrl + "/")
        result["list"] = self._parse_videos(html) if html else []
        return result

    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, page=1, *args):
        result = {}
        page = int(page)
        url = f"{self.siteUrl}/list.php?id={tid}&page={page}"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        # 分页
        pages = re.findall(r'page=(\d+)', html)
        max_page = max(int(p) for p in pages) if pages else 1
        result["page"] = page
        result["pagecount"] = max_page
        result["limit"] = 19
        result["total"] = max_page * 19
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
            html = self._fetch(f"{self.siteUrl}/video.php?id={vod_id}")
            if not html:
                continue
            # 标题 (可能含document.write编码)
            title_m = re.search(r'<h5 class="card-title">(.*?)</h5>', html, re.S)
            vod_name = ""
            if title_m:
                vod_name = extract_visible_text(title_m.group(1))
            if not vod_name:
                t_m = re.search(r'<title>(.*?)</title>', html, re.S)
                vod_name = t_m.group(1).strip() if t_m else ""
            if is_minor(vod_name):
                continue
            # 封面
            cover_m = re.search(r'data-original="([^"]+)"', html)
            if not cover_m:
                cover_m = re.search(r'poster="([^"]+)"', html)
            vod_pic = cover_m.group(1) if cover_m else ""
            # m3u8: Hls.js loadSource 或 video.src
            m3u8 = ""
            hls_m = re.search(r"loadSource\s*\(\s*['\"]([^'\"]+\.m3u8[^'\"]*)['\"]", html)
            if hls_m:
                m3u8 = hls_m.group(1)
            if not m3u8:
                src_m = re.search(r"video\.src\s*=\s*['\"]([^'\"]+\.m3u8[^'\"]*)['\"]", html)
                if src_m:
                    m3u8 = src_m.group(1)
            if not m3u8:
                direct_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                if direct_m:
                    m3u8 = direct_m.group(1)
            if m3u8 and '$' not in m3u8:
                m3u8 = f"第1集${m3u8}"
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": self._abs_url(vod_pic),
                "vod_play_from": "HD高清",
                "vod_play_url": m3u8,
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
        url = f"{self.siteUrl}/search.php?content={key_enc}"
        if page > 1:
            url += f"&page={page}"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        result["page"] = page
        result["pagecount"] = 1
        result["limit"] = 19
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
        return "AAATT Spider loaded"

    def getName(self):
        return "AAATT"

    def destroy(self):
        self._session = None
