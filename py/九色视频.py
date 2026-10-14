# -*- coding: utf-8 -*-
# 九色视频 TVBox 四壳通用 Python Spider
# 站点: https://www.jiuseav10.top/aa/
# 结构: 苹果CMS abc模板, /aa/子路径, 首页直链播放页, 播放页player_aaaa.url直出m3u8(ytm3u8线路)
# 视频卡片: <li>内含<a><img>封面</a> + <div class="video-detail"><h3 class="video-title">标题</h3></div>
# 播放: /index.php/vod/play/id/{id}/sid/{sid}/nid/{nid}.html, 分类: /index.php/vod/type/id/{id}/page/{page}.html

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

# ==================== 分类配置 (56个, 已排除3个"更多"导航) ====================
CATEGORIES = [
    {"type_id": "2", "type_name": "精品推荐"},
    {"type_id": "3", "type_name": "国产精品"},
    {"type_id": "4", "type_name": "主播秀色"},
    {"type_id": "5", "type_name": "日本无码"},
    {"type_id": "6", "type_name": "欧美情色"},
    {"type_id": "7", "type_name": "自拍偷拍"},
    {"type_id": "8", "type_name": "日本片商"},
    {"type_id": "9", "type_name": "剧情介绍"},
    {"type_id": "10", "type_name": "网曝系列"},
    {"type_id": "11", "type_name": "同性恋"},
    {"type_id": "12", "type_name": "探花嫖娼"},
    {"type_id": "13", "type_name": "国产人妻"},
    {"type_id": "14", "type_name": "国产SM"},
    {"type_id": "15", "type_name": "国产丝袜"},
    {"type_id": "16", "type_name": "麻豆传媒"},
    {"type_id": "17", "type_name": "国产乱伦"},
    {"type_id": "19", "type_name": "精品推荐"},
    {"type_id": "20", "type_name": "国产色情"},
    {"type_id": "21", "type_name": "主播直播"},
    {"type_id": "22", "type_name": "自拍偷拍"},
    {"type_id": "23", "type_name": "Cosplay"},
    {"type_id": "24", "type_name": "素人自拍"},
    {"type_id": "25", "type_name": "台湾辣妹"},
    {"type_id": "26", "type_name": "韩国御姐"},
    {"type_id": "27", "type_name": "唯美港姐"},
    {"type_id": "28", "type_name": "剧情介绍"},
    {"type_id": "29", "type_name": "多人多P"},
    {"type_id": "30", "type_name": "91探花"},
    {"type_id": "31", "type_name": "网红流出"},
    {"type_id": "32", "type_name": "野外露出"},
    {"type_id": "33", "type_name": "古装扮演"},
    {"type_id": "34", "type_name": "女优系列"},
    {"type_id": "35", "type_name": "可爱学生"},
    {"type_id": "36", "type_name": "风情旗袍"},
    {"type_id": "37", "type_name": "兽耳系列"},
    {"type_id": "38", "type_name": "瑜伽裤"},
    {"type_id": "39", "type_name": "闷骚护士"},
    {"type_id": "40", "type_name": "网曝门"},
    {"type_id": "41", "type_name": "传媒出品"},
    {"type_id": "42", "type_name": "女同性恋"},
    {"type_id": "44", "type_name": "偷拍自拍"},
    {"type_id": "45", "type_name": "国产大制作"},
    {"type_id": "46", "type_name": "乱伦毁三观"},
    {"type_id": "47", "type_name": "主播女网红"},
    {"type_id": "48", "type_name": "黑料网曝"},
    {"type_id": "49", "type_name": "淫乱学生妹"},
    {"type_id": "50", "type_name": "FC2"},
    {"type_id": "51", "type_name": "会所技师"},
    {"type_id": "52", "type_name": "国产推荐"},
    {"type_id": "53", "type_name": "探花约炮"},
    {"type_id": "54", "type_name": "韩国直播"},
    {"type_id": "55", "type_name": "国产直播"},
    {"type_id": "56", "type_name": "淫妻绿帽"},
    {"type_id": "57", "type_name": "重口猎奇"},
    {"type_id": "58", "type_name": "东京热"},
    {"type_id": "59", "type_name": "一本道"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://www.jiuseav10.top/aa"
        self.rawSite = "https://www.jiuseav10.top/aa"
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
            return "https://www.jiuseav10.top" + url
        return self.siteUrl + "/" + url

    # ==================== 解析视频列表 ====================
    def _parse_videos(self, html):
        """从HTML中解析视频列表 (abc模板, 封面在<a><img>中, 标题在兄弟<h3 class="video-title">中)"""
        vod_list = []
        # 匹配<li>...</li>中含播放链接的卡片
        li_pattern = r'<li[^>]*>(.*?)</li>'
        for li_content in re.findall(li_pattern, html, re.S):
            # 播放链接
            play_m = re.search(r'/aa/index\.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html', li_content)
            if not play_m:
                continue
            vid = play_m.group(1)
            # 封面 (第一个img的src)
            cover_m = re.search(r'<img[^>]*src="([^"]+\.(?:jpg|png|jpeg|webp))"', li_content)
            cover = cover_m.group(1) if cover_m else ""
            # 标题 (h3.video-title)
            title_m = re.search(r'class="video-title"[^>]*>(.*?)</h3>', li_content, re.S)
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
        html = self._fetch(self.siteUrl + "/?id=yng")
        if not html:
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
        pages = re.findall(r'/aa/index\.php/vod/type/id/' + re.escape(tid) + r'/page/(\d+)\.html', html)
        max_page = max(int(p) for p in pages) if pages else 999
        result["page"] = page
        result["pagecount"] = max_page
        result["limit"] = 40
        result["total"] = max_page * 40
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
            # player_aaaa JSON (raw_decode)
            play_url = ""
            play_from = "ytm3u8"
            pa_m = re.search(r'player_aaaa\s*=\s*', html)
            if pa_m:
                start = pa_m.end()
                if start < len(html) and html[start] == '{':
                    try:
                        decoder = json.JSONDecoder()
                        pa, _ = decoder.raw_decode(html[start:])
                        play_url = pa.get('url', '')
                        play_from = pa.get('from', 'ytm3u8')
                    except Exception:
                        pass
            # 兜底: 直接找m3u8
            if not play_url:
                m3u8_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                if m3u8_m:
                    play_url = m3u8_m.group(1)
            # 标题
            title_m = re.search(r'<title>(.*?)</title>', html, re.S)
            vod_name = ""
            if title_m:
                vod_name = title_m.group(1).split('在线播放')[0].strip()
                vod_name = vod_name.split('-')[0].strip()
            if not vod_name:
                h1_m = re.search(r'<h[1-6][^>]*>(.*?)</h[1-6]>', html, re.S)
                if h1_m:
                    vod_name = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip()
            if is_minor(vod_name):
                continue
            # 封面
            cover_m = re.search(r'<img[^>]*src="([^"]+\.(?:jpg|png|jpeg|webp))"', html)
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
        return "九色视频 Spider loaded"

    def getName(self):
        return "九色视频"

    def destroy(self):
        self._session = None
