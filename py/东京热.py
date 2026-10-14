# -*- coding: utf-8 -*-
# 东京热 TVBox 四壳通用 Python Spider
# 站点: https://www.tokyo-hot.com/index?lang=zh-TW
# 结构: 自定义电商CMS, 产品列表/product/?page={page}, 产品页/product/{code}/
# 每个产品有免费sample MP4: https://my.cdn.tokyo-hot.com/media/samples/{code}.mp4
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

# ==================== 分类配置 ====================
CATEGORIES = [
    {"type_id": "all", "type_name": "全部作品"},
    {"type_id": "shorts", "type_name": "短影片"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://www.tokyo-hot.com"
        self.rawSite = "https://www.tokyo-hot.com"
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
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"
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

    # ==================== 解析产品列表 ====================
    def _parse_products(self, html):
        """从产品列表页解析产品 (封面img src, 标题在div.title, code在href)"""
        vod_list = []
        # 匹配 <li class="detail">...<a href="/product/{code}/">...<img src=COVER>...<div class="title">TITLE</div>
        pattern = r'<li[^>]*>\s*<a[^>]*href="/product/([^/"]+)/"[^>]*>(.*?)</a>'
        for code, content in re.findall(pattern, html, re.S):
            # 封面
            cover_m = re.search(r'<img[^>]*src="([^"]+)"', content)
            cover = cover_m.group(1) if cover_m else ""
            # 标题 (div.title)
            title_m = re.search(r'class="title"[^>]*>(.*?)</div>', content, re.S)
            title = ""
            if title_m:
                title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            if not title:
                # 兜底: alt/title属性
                alt_m = re.search(r'alt="([^"]+)"', content)
                title = alt_m.group(1) if alt_m else code
            if not title or is_minor(title):
                continue
            vod_list.append({
                "vod_id": code,
                "vod_name": title,
                "vod_pic": self._abs_url(cover),
                "vod_remarks": code,
            })
        return vod_list

    # ==================== 解析首页短影片 ====================
    def _parse_shorts(self, html):
        """从首页解析短影片卡片"""
        vod_list = []
        pattern = r'<a[^>]*class="tile"[^>]*href="/shorts/(\d+)/"[^>]*>(.*?)</a>'
        for sid, content in re.findall(pattern, html, re.S):
            cover_m = re.search(r'<img[^>]*src="([^"]+)"', content)
            cover = cover_m.group(1) if cover_m else ""
            title_m = re.search(r'<span[^>]*class="caption"[^>]*>(.*?)</span>', content, re.S)
            title = ""
            if title_m:
                title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            if not title:
                alt_m = re.search(r'alt="([^"]+)"', content)
                title = alt_m.group(1) if alt_m else sid
            if not title or is_minor(title):
                continue
            vod_list.append({
                "vod_id": "shorts_" + sid,
                "vod_name": title,
                "vod_pic": self._abs_url(cover),
                "vod_remarks": "短影片",
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
        html = self._fetch(self.siteUrl + "/index?lang=zh-TW")
        if not html:
            html = self._fetch(self.siteUrl + "/")
        # 首页推荐: 产品 + 短影片
        vod_list = self._parse_products(html)
        vod_list.extend(self._parse_shorts(html))
        result["list"] = vod_list
        return result

    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, page=1, *args):
        result = {}
        page = int(page)
        vod_list = []
        max_page = 999
        if tid == "all":
            # 全部作品
            url = f"{self.siteUrl}/product/?lang=zh-TW&page={page}"
            html = self._fetch(url)
            vod_list = self._parse_products(html)
            pages = re.findall(r'[?&]page=(\d+)', html)
            if pages:
                max_page = max(int(p) for p in pages)
        elif tid == "shorts":
            # 短影片 (首页短影片carousel)
            html = self._fetch(self.siteUrl + "/index?lang=zh-TW")
            vod_list = self._parse_shorts(html)
            max_page = 1
        result["page"] = page
        result["pagecount"] = max_page
        result["limit"] = 51
        result["total"] = max_page * 51
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
            # 短影片特殊处理
            if vod_id.startswith("shorts_"):
                sid = vod_id.replace("shorts_", "")
                html = self._fetch(f"{self.siteUrl}/shorts/{sid}/?lang=zh-TW")
                # 从shorts页提取所有mp4
                mp4s = re.findall(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html)
                if mp4s:
                    # 去重
                    unique_mp4s = list(dict.fromkeys(mp4s))
                    episodes = []
                    for i, mp4 in enumerate(unique_mp4s[:10]):
                        episodes.append(f"片段{i+1}${mp4}")
                    vod_list.append({
                        "vod_id": vod_id,
                        "vod_name": f"短影片 {sid}",
                        "vod_pic": "",
                        "vod_play_from": "短影片",
                        "vod_play_url": "#".join(episodes),
                    })
                continue
            # 普通产品
            code = vod_id
            # 产品页
            html = self._fetch(f"{self.siteUrl}/product/{code}/?lang=zh-TW")
            vod_name = code
            vod_pic = ""
            play_url = ""
            if html:
                # 标题
                title_m = re.search(r'<title>(.*?)</title>', html, re.S)
                if title_m:
                    vod_name = title_m.group(1).split('|')[0].strip()
                    vod_name = vod_name.split(' - ')[0].strip()
                # 封面
                cover_m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
                if cover_m:
                    vod_pic = cover_m.group(1)
                if not vod_pic:
                    img_m = re.search(r'<img[^>]*src="([^"]+\.(?:jpg|png|jpeg|webp))"', html)
                    if img_m:
                        vod_pic = img_m.group(1)
                # sample MP4
                mp4_m = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html)
                if mp4_m:
                    play_url = mp4_m.group(1)
            # 兜底: 构造sample URL
            if not play_url:
                play_url = f"https://my.cdn.tokyo-hot.com/media/samples/{code}.mp4"
            if is_minor(vod_name):
                continue
            if play_url and '$' not in play_url:
                play_url = f"试看${play_url}"
            vod_list.append({
                "vod_id": code,
                "vod_name": vod_name,
                "vod_pic": self._abs_url(vod_pic),
                "vod_play_from": "sample",
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
        # 东京热搜索格式
        html = ""
        for url in [
            f"{self.siteUrl}/product/?lang=zh-TW&q={key_enc}",
            f"{self.siteUrl}/search/?q={key_enc}",
            f"{self.siteUrl}/product/?keyword={key_enc}",
        ]:
            html = self._fetch(url)
            if html and '/product/' in html:
                break
        vod_list = self._parse_products(html) if html else []
        result["page"] = page
        result["pagecount"] = 1
        result["limit"] = 51
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
            return [200, "video/mp4", html]
        except Exception:
            return [404, "text/plain", ""]

    # ==================== 7. 其他接口 ====================
    def isVideoFormat(self, url):
        return any(url.endswith(ext) for ext in [".m3u8", ".mp4", ".mkv", ".avi", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return "东京热 Spider loaded"

    def getName(self):
        return "东京热"

    def destroy(self):
        self._session = None
