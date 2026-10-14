# -*- coding: utf-8 -*-
# 淫窝市 TVBox 四壳通用 Python Spider
# 站点: https://xn---0921-cfavg-pd0t.yinwoshi.sbs/
# 结构: 自定义CMS(avnvtuan模板), 分类/vod-type/id-{id}-by-time-pg-{page}.html
# 播放页/vod-play/id-{id}.html, m3u8在iframe的ckplayer player.php?url=参数中
# 视频卡片: <a><img data-original=封面><span class="vodname">标题</span></a>
# 注意: 本站可能需要代理/VPN才能访问

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

# ==================== 分类配置 (21个, 已过滤id=125少女萝莉) ====================
CATEGORIES = [
    {"type_id": "122", "type_name": "乐播平台"},
    {"type_id": "123", "type_name": "亚洲情色"},
    {"type_id": "124", "type_name": "重口色情"},
    {"type_id": "126", "type_name": "丝袜长腿"},
    {"type_id": "127", "type_name": "卡通动画"},
    {"type_id": "128", "type_name": "女同性恋"},
    {"type_id": "129", "type_name": "制服诱惑"},
    {"type_id": "130", "type_name": "中文字幕"},
    {"type_id": "131", "type_name": "巨乳美乳"},
    {"type_id": "132", "type_name": "强奸乱伦"},
    {"type_id": "133", "type_name": "熟女人妻"},
    {"type_id": "134", "type_name": "欧美性爱"},
    {"type_id": "135", "type_name": "无码专区"},
    {"type_id": "136", "type_name": "国产自拍"},
    {"type_id": "137", "type_name": "国产主播"},
    {"type_id": "138", "type_name": "人兽性交"},
    {"type_id": "272", "type_name": "桃花资源"},
    {"type_id": "285", "type_name": "奥斯卡资源"},
    {"type_id": "376", "type_name": "色猫资源"},
    {"type_id": "404", "type_name": "老色逼资源"},
    {"type_id": "451", "type_name": "杏吧"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://xn---0921-cfavg-pd0t.yinwoshi.sbs"
        self.rawSite = "https://xn---0921-cfavg-pd0t.yinwoshi.sbs"
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
        """从HTML中解析视频列表 (avnvtuan模板, 封面data-original, 标题span.vodname)"""
        vod_list = []
        # 匹配 <li>...</li> 中含vod-play的卡片
        li_pattern = r'<li[^>]*>(.*?)</li>'
        for li_content in re.findall(li_pattern, html, re.S):
            # 播放链接
            play_m = re.search(r'/vod-play/id-(\d+)\.html', li_content)
            if not play_m:
                continue
            vid = play_m.group(1)
            # 封面 (data-original懒加载)
            cover_m = re.search(r'data-original="([^"]+\.(?:jpg|png|jpeg|webp))"', li_content)
            if not cover_m:
                cover_m = re.search(r'<img[^>]*src="([^"]+\.(?:jpg|png|jpeg|webp))"', li_content)
            cover = cover_m.group(1) if cover_m else ""
            # 标题 (span.vodname)
            title_m = re.search(r'class="vodname"[^>]*>(.*?)</span>', li_content, re.S)
            title = ""
            if title_m:
                title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            if not title:
                # 兜底: alt属性
                alt_m = re.search(r'alt="([^"]+)"', li_content)
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
        # 首页为导航页, 抓取首个分类页兜底
        html = self._fetch(self.siteUrl + "/vod-type/id-122-by-time-pg-1.html")
        result["list"] = self._parse_videos(html) if html else []
        return result

    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, page=1, *args):
        result = {}
        page = int(page)
        url = f"{self.siteUrl}/vod-type/id-{tid}-by-time-pg-{page}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        # 分页
        pages = re.findall(r'/vod-type/id/' + re.escape(tid) + r'-by-time-pg-(\d+)\.html', html)
        max_page = max(int(p) for p in pages) if pages else 999
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
            html = self._fetch(f"{self.siteUrl}/vod-play/id-{vod_id}.html")
            if not html:
                continue
            # 标题
            title_m = re.search(r'<title>(.*?)</title>', html, re.S)
            vod_name = ""
            if title_m:
                vod_name = title_m.group(1).split(' - ')[0].strip()
                vod_name = vod_name.split(',')[0].strip()
            if not vod_name:
                h1_m = re.search(r'<h[1-6][^>]*>(.*?)</h[1-6]>', html, re.S)
                if h1_m:
                    vod_name = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip()
            if is_minor(vod_name):
                continue
            # 封面
            cover_m = re.search(r'data-original="([^"]+\.(?:jpg|png|jpeg|webp))"', html)
            if not cover_m:
                cover_m = re.search(r'<img[^>]*src="([^"]+\.(?:jpg|png|jpeg|webp))"', html)
            vod_pic = cover_m.group(1) if cover_m else ""
            # m3u8: 从iframe的ckplayer player.php?url=参数中提取
            play_url = ""
            iframe_m = re.search(r'<iframe[^>]*src="([^"]+)"', html)
            if iframe_m:
                iframe_src = iframe_m.group(1)
                # 从URL参数中提取url
                parsed = urllib.parse.urlparse(iframe_src)
                params = urllib.parse.parse_qs(parsed.query)
                if 'url' in params:
                    play_url = params['url'][0]
            # 兜底: 直接找m3u8
            if not play_url:
                m3u8_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                if m3u8_m:
                    play_url = m3u8_m.group(1)
            # 兜底: player.php?url= 在其他位置
            if not play_url:
                pp_m = re.search(r'player\.php\?url=([^"\'&\s]+)', html)
                if pp_m:
                    play_url = urllib.parse.unquote(pp_m.group(1))
            if play_url and '$' not in play_url:
                play_url = f"第1集${play_url}"
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": self._abs_url(vod_pic),
                "vod_play_from": "ckplayer",
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
            f"{self.siteUrl}/vod-search/wd-{key_enc}-by-time-pg-{page}.html",
            f"{self.siteUrl}/vod-search/wd-{key_enc}.html",
            f"{self.siteUrl}/?wd={key_enc}",
        ]:
            html = self._fetch(url)
            if html and '/vod-play/' in html:
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
        return "淫窝市 Spider loaded"

    def getName(self):
        return "淫窝市"

    def destroy(self):
        self._session = None
