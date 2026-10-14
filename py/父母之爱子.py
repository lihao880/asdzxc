# -*- coding: utf-8 -*-
# 父母之爱子 TVBox 四壳通用 Python Spider
# 站点: https://981246.fmzazf01.top/fmaizi/
# 结构: 苹果CMSv10, 详情/vod/detail/id/{id}, 播放/vod/play/id/{id}/sid/{sid}/nid/{nid}
# 播放页player_aaaa encrypt=0直出m3u8, 详情页多线路

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

# ==================== 分类配置 (去重, 萝莉少女已剔除) ====================
CATEGORIES = [
    {"type_id": "92", "type_name": "每日更新3区"},
    {"type_id": "94", "type_name": "网曝黑料"},
    {"type_id": "96", "type_name": "国产主播"},
    {"type_id": "95", "type_name": "国产视频"},
    {"type_id": "99", "type_name": "网红头条"},
    {"type_id": "97", "type_name": "国产传媒"},
    {"type_id": "100", "type_name": "明星换脸"},
    {"type_id": "98", "type_name": "女同性恋"},
    {"type_id": "101", "type_name": "抖阴视频"},
    {"type_id": "114", "type_name": "伦理三级"},
    {"type_id": "110", "type_name": "欧美无码"},
    {"type_id": "112", "type_name": "强奸乱伦"},
    {"type_id": "111", "type_name": "女优明星"},
    {"type_id": "115", "type_name": "制服诱惑"},
    {"type_id": "108", "type_name": "日本有码"},
    {"type_id": "116", "type_name": "AV解说"},
    {"type_id": "109", "type_name": "日本无码"},
    {"type_id": "107", "type_name": "中文字幕"},
    {"type_id": "102", "type_name": "激情动漫"},
    {"type_id": "103", "type_name": "SM调教"},
    {"type_id": "106", "type_name": "人妖系列"},
    {"type_id": "105", "type_name": "VR视角"},
    {"type_id": "104", "type_name": "韩国主播"},
    {"type_id": "29", "type_name": "每日更新1区"},
    {"type_id": "66", "type_name": "探花约炮"},
    {"type_id": "64", "type_name": "主播做爱"},
    {"type_id": "65", "type_name": "传媒出品"},
    {"type_id": "73", "type_name": "黑料网爆"},
    {"type_id": "67", "type_name": "自拍短视频"},
    {"type_id": "74", "type_name": "高清做爱"},
    {"type_id": "69", "type_name": "动漫"},
    {"type_id": "68", "type_name": "欧美精品"},
    {"type_id": "71", "type_name": "男同性恋"},
    {"type_id": "75", "type_name": "调教SM"},
    {"type_id": "76", "type_name": "AI换脸"},
    {"type_id": "30", "type_name": "每日更新2区"},
    {"type_id": "57", "type_name": "国产探花"},
    {"type_id": "54", "type_name": "偷拍自拍"},
    {"type_id": "77", "type_name": "国产精品"},
    {"type_id": "50", "type_name": "直播做爱"},
    {"type_id": "49", "type_name": "精品推荐"},
    {"type_id": "55", "type_name": "网曝流出"},
    {"type_id": "62", "type_name": "乱伦实录"},
    {"type_id": "63", "type_name": "换脸明星"},
    {"type_id": "56", "type_name": "同性恋"},
    {"type_id": "58", "type_name": "人妻熟女"},
    {"type_id": "61", "type_name": "麻豆诱惑"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://981246.fmzazf01.top"
        self.rawSite = "https://981246.fmzazf01.top"
        self.HOST = self.siteUrl
        self._base_path = "/fmaizi/index.php/vod"
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
        pattern = re.compile(
            r'<li>\s*<a[^>]*class="thumbnail"[^>]*href="/fmaizi/index\.php/vod/detail/id/(\d+)\.html"[^>]*>.*?'
            r'data-original="([^"]+)".*?'
            r'<h5><a[^>]*>([^<]+)</a></h5>',
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
        html = self._fetch(f"{self.siteUrl}/fmaizi/")
        result["list"] = self._parse_videos(html)
        return result

    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, page=1, *args):
        result = {}
        page = int(page)
        if page <= 1:
            url = f"{self.siteUrl}{self._base_path}/type/id/{tid}.html"
        else:
            url = f"{self.siteUrl}{self._base_path}/type/id/{tid}/page/{page}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        result["page"] = page
        result["pagecount"] = 999
        result["limit"] = 20
        result["total"] = 999 * 20
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
            html = self._fetch(f"{self.siteUrl}{self._base_path}/detail/id/{vod_id}.html")
            if not html:
                continue
            # 标题: title标签, 去掉"剧情介绍--父母之爱子"后缀
            vod_name = ""
            title_m = re.search(r'<title>(.*?)</title>', html, re.S)
            if title_m:
                vod_name = title_m.group(1).strip()
                for suffix in ['剧情介绍--父母之爱子', '--父母之爱子', '父母之爱子']:
                    if vod_name.endswith(suffix):
                        vod_name = vod_name[:-len(suffix)].strip()
                        break
            if is_minor(vod_name):
                continue
            # 封面
            vod_pic = ""
            cover_m = re.search(r'data-original="([^"]+)"', html)
            if cover_m:
                vod_pic = self._abs_url(cover_m.group(1).strip())
            # 播放链接: 按sid分组构造多线路
            play_links = re.findall(
                r'href="(/fmaizi/index\.php/vod/play/id/\d+/sid/(\d+)/nid/(\d+)\.html)"[^>]*>(.*?)</a>',
                html, re.S
            )
            lines = {}  # sid -> {name, url}
            for href, sid, nid, content in play_links:
                ep_name = re.sub(r'<[^>]+>', '', content).strip()
                if not ep_name:
                    ep_name = f"第{nid}集"
                full_url = self.siteUrl + href
                if sid not in lines:
                    lines[sid] = {"name": ep_name, "eps": []}
                lines[sid]["eps"].append(f"{ep_name}${full_url}")
            # 构造vod_play_from和vod_play_url
            vod_play_from = ""
            vod_play_url = ""
            if lines:
                from_list = []
                url_list = []
                for sid, info in lines.items():
                    from_list.append(info["name"])
                    url_list.append("#".join(info["eps"]))
                vod_play_from = "$$$".join(from_list)
                vod_play_url = "$$$".join(url_list)
            else:
                # 兜底: 单线路默认播放页
                vod_play_from = "HD高清"
                vod_play_url = f"第1集${self.siteUrl}{self._base_path}/play/id/{vod_id}/sid/1/nid/1.html"
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
        # id是播放页完整URL, 需要fetch后从player_aaaa提取m3u8
        play_url = id if id.startswith("http") else self._abs_url(id)
        m3u8_url = ""
        if play_url:
            html = self._fetch(play_url)
            if html:
                m = re.search(r'(?:var\s+)?player_aaaa\s*=\s*', html)
                if m:
                    start = m.end()
                    depth = 0
                    end = start
                    for i in range(start, min(start + 5000, len(html))):
                        if html[i] == '{': depth += 1
                        elif html[i] == '}':
                            depth -= 1
                            if depth == 0:
                                end = i + 1
                                break
                    if end > start:
                        try:
                            data = json.loads(html[start:end])
                            raw_url = data.get("url", "")
                            if data.get("encrypt") == 1 and raw_url:
                                raw_url = urllib.parse.unquote(raw_url)
                            m3u8_url = raw_url
                        except Exception:
                            pass
                # 兜底: 直接正则m3u8
                if not m3u8_url:
                    m3u8_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                    if m3u8_m:
                        m3u8_url = m3u8_m.group(1)
        result["parse"] = 0
        result["jx"] = 0
        result["url"] = m3u8_url if m3u8_url else play_url
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
            url = f"{self.siteUrl}{self._base_path}/search.html?wd={key_enc}"
        else:
            url = f"{self.siteUrl}{self._base_path}/search/page/{page}/wd/{key_enc}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        result["page"] = page
        result["pagecount"] = 99
        result["limit"] = 20
        result["total"] = 99 * 20
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
        return "父母之爱子 Spider loaded"

    def getName(self):
        return "父母之爱子"

    def destroy(self):
        self._session = None
