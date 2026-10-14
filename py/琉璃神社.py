# -*- coding: utf-8 -*-
# 琉璃神社 TVBox 四壳通用 Python Spider
# 站点: https://wap.llss14.cc/llss/
# 结构: 苹果CMS llss移动端模板, /llss/子路径, 播放页player_aaaa.url直出m3u8(ytm3u8线路)
# 视频: /index.php/vod/detail/id/{id}.html -> /index.php/vod/play/id/{id}/sid/1/nid/1.html
# 分类: /index.php/vod/type/id/{id}.html?page={page}, 搜索: /index.php/vod/search/wd/{kw}.html

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

# ==================== 分类配置 (75个, 已过滤3个未成年) ====================
CATEGORIES = [
    {"type_id": "119", "type_name": "不卡资源"},
    {"type_id": "120", "type_name": "国产视频"},
    {"type_id": "121", "type_name": "中文字幕"},
    {"type_id": "122", "type_name": "国产传媒"},
    {"type_id": "123", "type_name": "日本有码"},
    {"type_id": "124", "type_name": "日本无码"},
    {"type_id": "125", "type_name": "欧美无码"},
    {"type_id": "126", "type_name": "强干乱伦"},
    {"type_id": "127", "type_name": "制服诱惑"},
    {"type_id": "128", "type_name": "国产主播"},
    {"type_id": "129", "type_name": "激情动漫"},
    {"type_id": "130", "type_name": "明星换脸"},
    {"type_id": "131", "type_name": "抖阴视频"},
    {"type_id": "244", "type_name": "51资源"},
    {"type_id": "254", "type_name": "国产自拍"},
    {"type_id": "255", "type_name": "熟女人妻"},
    {"type_id": "257", "type_name": "百合剧情"},
    {"type_id": "258", "type_name": "美乳巨乳"},
    {"type_id": "259", "type_name": "强歼乱伦"},
    {"type_id": "260", "type_name": "抖音视频"},
    {"type_id": "261", "type_name": "韩国主播"},
    {"type_id": "262", "type_name": "网红头条"},
    {"type_id": "263", "type_name": "网曝黑料"},
    {"type_id": "264", "type_name": "欧美无码"},
    {"type_id": "266", "type_name": "AV解说"},
    {"type_id": "286", "type_name": "兔儿资源"},
    {"type_id": "304", "type_name": "精品推荐"},
    {"type_id": "305", "type_name": "主播秀色"},
    {"type_id": "306", "type_name": "日本有码"},
    {"type_id": "307", "type_name": "日本无码"},
    {"type_id": "308", "type_name": "中文字幕"},
    {"type_id": "310", "type_name": "性感人妻"},
    {"type_id": "311", "type_name": "强歼乱伦"},
    {"type_id": "312", "type_name": "欧美情色"},
    {"type_id": "313", "type_name": "三级伦理"},
    {"type_id": "314", "type_name": "卡通动漫"},
    {"type_id": "315", "type_name": "丝袜OL"},
    {"type_id": "329", "type_name": "库库资源"},
    {"type_id": "330", "type_name": "日本有码"},
    {"type_id": "331", "type_name": "无码中文"},
    {"type_id": "332", "type_name": "有码中文"},
    {"type_id": "333", "type_name": "日本无码"},
    {"type_id": "334", "type_name": "国产视频"},
    {"type_id": "335", "type_name": "欧美高清"},
    {"type_id": "336", "type_name": "动漫剧情"},
    {"type_id": "358", "type_name": "琉璃资源"},
    {"type_id": "359", "type_name": "欧美精品"},
    {"type_id": "360", "type_name": "偷拍自拍"},
    {"type_id": "361", "type_name": "国产精品"},
    {"type_id": "362", "type_name": "乱伦系列"},
    {"type_id": "363", "type_name": "主播网红"},
    {"type_id": "364", "type_name": "黑料网曝"},
    {"type_id": "365", "type_name": "高清无码"},
    {"type_id": "366", "type_name": "中文字幕"},
    {"type_id": "367", "type_name": "学生妹"},
    {"type_id": "368", "type_name": "动漫精选"},
    {"type_id": "369", "type_name": "高清有码"},
    {"type_id": "370", "type_name": "森林资源"},
    {"type_id": "371", "type_name": "精品推荐"},
    {"type_id": "372", "type_name": "国产情色"},
    {"type_id": "373", "type_name": "亚洲无码"},
    {"type_id": "374", "type_name": "亚洲有码"},
    {"type_id": "375", "type_name": "中文字幕"},
    {"type_id": "376", "type_name": "强*乱伦"},
    {"type_id": "377", "type_name": "欧美精品"},
    {"type_id": "379", "type_name": "日本精品"},
    {"type_id": "380", "type_name": "Cosplay"},
    {"type_id": "381", "type_name": "野外露出"},
    {"type_id": "382", "type_name": "网红流出"},
    {"type_id": "386", "type_name": "黄瓜资源"},
    {"type_id": "387", "type_name": "国产自拍"},
    {"type_id": "388", "type_name": "日本无码"},
    {"type_id": "389", "type_name": "主播系列"},
    {"type_id": "390", "type_name": "欧美精品"},
    {"type_id": "391", "type_name": "AI短剧"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://wap.llss14.cc/llss"
        self.rawSite = "https://wap.llss14.cc/llss"
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
            return "https://wap.llss14.cc" + url
        return self.siteUrl + "/" + url

    # ==================== 解析视频列表 ====================
    def _parse_videos(self, html):
        """从HTML中解析视频列表 (llss模板, 封面data-original, 标题alt)"""
        vod_list = []
        pattern = r'<a[^>]*href="/llss/index\.php/vod/detail/id/(\d+)\.html"[^>]*>(.*?)</a>'
        for vid, content in re.findall(pattern, html, re.S):
            # 封面
            cover_m = re.search(r'data-original="([^"]+)"', content)
            if not cover_m:
                cover_m = re.search(r'data-src="([^"]+)"', content)
            cover = cover_m.group(1) if cover_m else ""
            # 标题 (alt属性)
            title_m = re.search(r'alt="([^"]+)"', content)
            title = title_m.group(1) if title_m else ""
            if not title:
                # 兜底: vod-name div
                name_m = re.search(r'class="vod-name"[^>]*>(.*?)</div>', content, re.S)
                if name_m:
                    title = re.sub(r'<[^>]+>', '', name_m.group(1)).strip()
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
            url += f"?page={page}"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        # 分页 (站点分页链接可能由JS加载, 默认999页)
        pages = re.findall(r'/llss/index\.php/vod/type/id/' + re.escape(tid) + r'\.html\?page=(\d+)', html)
        max_page = max(int(p) for p in pages) if pages else 999
        result["page"] = page
        result["pagecount"] = max_page
        result["limit"] = 12
        result["total"] = max_page * 12
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
            dhtml = self._fetch(f"{self.siteUrl}/index.php/vod/detail/id/{vod_id}.html")
            if not dhtml:
                continue
            # 标题
            title_m = re.search(r'<title>(.*?)</title>', dhtml, re.S)
            vod_name = ""
            if title_m:
                vod_name = title_m.group(1).split('在线观看')[0].strip()
                vod_name = vod_name.strip('《》')
            if not vod_name:
                name_m = re.search(r'class="vod-name"[^>]*>(.*?)</div>', dhtml, re.S)
                if name_m:
                    vod_name = re.sub(r'<[^>]+>', '', name_m.group(1)).strip()
            if is_minor(vod_name):
                continue
            # 封面
            cover_m = re.search(r'data-original="([^"]+)"', dhtml)
            if not cover_m:
                cover_m = re.search(r'data-src="([^"]+)"', dhtml)
            vod_pic = cover_m.group(1) if cover_m else ""
            # 播放页
            play_url = ""
            play_from = "ytm3u8"
            phtml = self._fetch(f"{self.siteUrl}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html")
            if phtml:
                # player_aaaa JSON (raw_decode)
                pa_m = re.search(r'player_aaaa\s*=\s*', phtml)
                if pa_m:
                    start = pa_m.end()
                    if start < len(phtml) and phtml[start] == '{':
                        try:
                            decoder = json.JSONDecoder()
                            pa, _ = decoder.raw_decode(phtml[start:])
                            play_url = pa.get('url', '')
                            play_from = pa.get('from', 'ytm3u8')
                        except Exception:
                            pass
                # 兜底: 直接找m3u8
                if not play_url:
                    m3u8_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', phtml)
                    if m3u8_m:
                        play_url = m3u8_m.group(1)
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
        url = f"{self.siteUrl}/index.php/vod/search/wd/{key_enc}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        result["page"] = page
        result["pagecount"] = 1
        result["limit"] = 12
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
        return "琉璃神社 Spider loaded"

    def getName(self):
        return "琉璃神社"

    def destroy(self):
        self._session = None
