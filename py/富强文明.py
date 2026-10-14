# -*- coding: utf-8 -*-
# 富强文明 TVBox 四壳通用 Python Spider
# 站点: https://tl2ruixing.361030.xyz/富强文明/
# 结构: 自定义CMS, AES-128-CBC加密+双层Base64, API驱动
# API: index_api.php(分类列表), v_api.php(详情), s_api.php(搜索), rand_api.php(推荐), type_api.php(分类)

import re
import json
import base64
import urllib.parse

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    HAS_PYCRYPTODOME = True
except ImportError:
    HAS_PYCRYPTODOME = False

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

# ==================== AES配置 ====================
AES_KEY = b'0123456789abcdef'
AES_IV = b'abcdef0123456789'

def _decrypt_utf8(encrypted):
    """AES decrypt + 双层Base64 → UTF-8 (对应 decryptData_Utf8)"""
    if not encrypted:
        return ""
    try:
        first = base64.b64decode(encrypted).decode('utf-8', errors='replace')
        ct = base64.b64decode(first)
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        pt = unpad(cipher.decrypt(ct), 16)
        return pt.decode('utf-8', errors='replace')
    except Exception:
        return ""

def _decrypt_base64(encrypted):
    """AES decrypt + 双层Base64 → Base64 → UTF-8 (对应 decryptData_Base64)"""
    if not encrypted:
        return ""
    try:
        first = base64.b64decode(encrypted).decode('utf-8', errors='replace')
        ct = base64.b64decode(first)
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        pt = unpad(cipher.decrypt(ct), 16)
        b64_result = pt.decode('utf-8', errors='replace')
        try:
            return base64.b64decode(b64_result).decode('utf-8', errors='replace')
        except Exception:
            return b64_result
    except Exception:
        return ""

# ==================== 未成年过滤 ====================
MINOR_KEYWORDS = ['萝莉', '幼女', '少女', '童', 'teen', 'loli', 'schoolgirl', '未成年']

def is_minor(text):
    if not text:
        return False
    t = text.lower()
    return any(kw.lower() in t for kw in MINOR_KEYWORDS)

# ==================== 分类配置 (6个) ====================
CATEGORIES = [
    {"type_id": "20", "type_name": "日本有码"},
    {"type_id": "21", "type_name": "日本无码"},
    {"type_id": "22", "type_name": "国产精品"},
    {"type_id": "23", "type_name": "欧美视频"},
    {"type_id": "130", "type_name": "精品传媒"},
    {"type_id": "131", "type_name": "3D动漫"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://tl2ruixing.361030.xyz"
        self.rawSite = "https://tl2ruixing.361030.xyz"
        self.HOST = self.siteUrl
        self._base_path = "/富强文明"
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

    def _fetch_json(self, url, timeout=15):
        text = self._fetch(url, timeout)
        if text:
            try:
                return json.loads(text)
            except Exception:
                pass
        return {}

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

    # ==================== 解析API视频列表 ====================
    def _parse_api_videos(self, data_list):
        vod_list = []
        for item in data_list:
            vod_id = _decrypt_utf8(item.get('id', ''))
            vod_name = _decrypt_base64(item.get('title', ''))
            vod_pic = _decrypt_utf8(item.get('img', ''))
            if not vod_id or not vod_name:
                continue
            if is_minor(vod_name):
                continue
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": self._abs_url(vod_pic),
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
        # 推荐视频用rand_api
        data = self._fetch_json(f"{self.siteUrl}{self._base_path}/rand_api.php")
        result["list"] = self._parse_api_videos(data.get('data', []))
        return result

    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, page=1, *args):
        result = {}
        page = int(page)
        data = self._fetch_json(
            f"{self.siteUrl}{self._base_path}/index_api.php?tid={tid}&page={page}&sort=0"
        )
        vod_list = self._parse_api_videos(data.get('data', []))
        pagination = data.get('pagination', {})
        total = int(pagination.get('total', 0))
        per_page = int(pagination.get('per_page', 20))
        pagecount = (total + per_page - 1) // per_page if total > 0 else 999
        result["page"] = page
        result["pagecount"] = pagecount
        result["limit"] = per_page
        result["total"] = total
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
            data = self._fetch_json(f"{self.siteUrl}{self._base_path}/v_api.php?i={vod_id}")
            if not data or 'data' not in data or not data['data']:
                continue
            item = data['data'][0]
            vod_name = _decrypt_base64(item.get('title', ''))
            vod_pic = _decrypt_utf8(item.get('img', ''))
            v_url = _decrypt_utf8(item.get('v_url', ''))
            if is_minor(vod_name):
                continue
            # v_url格式: "第1集$https://...m3u8"
            vod_play_from = "HD高清"
            vod_play_url = v_url if v_url else ""
            # 如果v_url不含$，手动加前缀
            if vod_play_url and '$' not in vod_play_url:
                vod_play_url = f"第1集${vod_play_url}"
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
        # id是m3u8直链 (从v_url解析)
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
        data = self._fetch_json(
            f"{self.siteUrl}{self._base_path}/s_api.php?q={key_enc}&page={page}&sort=0"
        )
        vod_list = self._parse_api_videos(data.get('data', []))
        pagination = data.get('pagination', {})
        total = int(pagination.get('total', 0))
        per_page = int(pagination.get('per_page', 20))
        pagecount = (total + per_page - 1) // per_page if total > 0 else 99
        result["page"] = page
        result["pagecount"] = pagecount
        result["limit"] = per_page
        result["total"] = total
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
        return "富强文明 Spider loaded"

    def getName(self):
        return "富强文明"

    def destroy(self):
        self._session = None
