# -*- coding: utf-8 -*-
# 撸状元 TVBox 四壳通用 Python Spider
# 站点: https://xn--7kq.lzytv.art/vod/index.php
# 结构: 自定义CMS, 详情?detail={id}, 分类?class={id}, 搜索?wd=, Aliplayer source直出m3u8

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
    {"type_id": "10082", "type_name": "国产"},
    {"type_id": "10083", "type_name": "传媒"},
    {"type_id": "10084", "type_name": "黑料"},
    {"type_id": "10088", "type_name": "无码"},
    {"type_id": "10087", "type_name": "有码"},
    {"type_id": "10089", "type_name": "字幕"},
    {"type_id": "10085", "type_name": "欧美"},
    {"type_id": "10086", "type_name": "动漫"},
    {"type_id": "10090", "type_name": "巨乳美乳"},
    {"type_id": "10091", "type_name": "人妻熟女"},
    {"type_id": "10092", "type_name": "强奸乱伦"},
    {"type_id": "10093", "type_name": "制服丝袜"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://xn--7kq.lzytv.art"
        self.rawSite = "https://xn--7kq.lzytv.art"
        self.HOST = self.siteUrl
        self._base_path = "/vod/index.php"
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
        vod_list = []
        # thumb-item 结构
        pattern = re.compile(
            r'<div class="thumb-item[^"]*">.*?'
            r'href="\?detail=(\d+)"[^>]*>.*?'
            r'original="([^"]+)".*?'
            r'<h2 class="thumb-item__title[^"]*">([^<]+)</h2>',
            re.S
        )
        for m in pattern.finditer(html):
            vod_id = m.group(1)
            vod_pic = self._abs_url(m.group(2).strip())
            vod_name = m.group(3).strip()
            if is_minor(vod_name):
                continue
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
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
        html = self._fetch(f"{self.siteUrl}{self._base_path}")
        result["list"] = self._parse_videos(html)
        return result

    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, page=1, *args):
        result = {}
        page = int(page)
        if page <= 1:
            url = f"{self.siteUrl}{self._base_path}?class={tid}"
        else:
            url = f"{self.siteUrl}{self._base_path}?class={tid}&page={page}"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        result["page"] = page
        result["pagecount"] = 999
        result["limit"] = 30
        result["total"] = 999 * 30
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
            html = self._fetch(f"{self.siteUrl}{self._base_path}?detail={vod_id}")
            if not html:
                continue
            # 标题: title标签, 去掉"撸状元"后缀
            vod_name = ""
            title_m = re.search(r'<title>(.*?)</title>', html, re.S)
            if title_m:
                vod_name = title_m.group(1).strip()
                # 去掉站点名后缀
                for suffix in ['撸状元', '-撸状元', '撸状元-']:
                    if vod_name.endswith(suffix):
                        vod_name = vod_name[:-len(suffix)].strip()
                        break
            if is_minor(vod_name):
                continue
            # 封面: Aliplayer cover 或 original
            vod_pic = ""
            cover_m = re.search(r'cover\s*:\s*"([^"]+)"', html)
            if cover_m:
                vod_pic = self._abs_url(cover_m.group(1).strip())
            if not vod_pic:
                orig_m = re.search(r'original="([^"]+)"', html)
                if orig_m:
                    vod_pic = self._abs_url(orig_m.group(1).strip())
            # m3u8: Aliplayer source
            play_url = ""
            source_m = re.search(r'source\s*:\s*"([^"]+)"', html)
            if source_m:
                play_url = source_m.group(1).strip()
            # 兜底: 直接正则m3u8
            if not play_url:
                m3u8_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                if m3u8_m:
                    play_url = m3u8_m.group(1)
            vod_play_from = "HD高清"
            vod_play_url = f"第1集${play_url}" if play_url else ""
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_play_from": vod_play_from,
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
        key_enc = urllib.parse.quote(key)
        page = int(page)
        if page <= 1:
            url = f"{self.siteUrl}{self._base_path}?wd={key_enc}"
        else:
            url = f"{self.siteUrl}{self._base_path}?wd={key_enc}&page={page}"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        result["page"] = page
        result["pagecount"] = 99
        result["limit"] = 30
        result["total"] = 99 * 30
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
        return "撸状元 Spider loaded"

    def getName(self):
        return "撸状元"

    def destroy(self):
        self._session = None
