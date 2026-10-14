# -*- coding: utf-8 -*-
# 91成人 TVBox 四壳通用 Python Spider
# 站点: https://yjuyg-91207-zmo5ae.miupiupiupiav131b72.top/light/
# 结构: 苹果CMS自定义模板, 首页在/light/子路径, 详情页/voddetail/{id}/跳转播放页/v/{id}/
# 播放页player_aaaa.url直出m3u8(naixx线路), 分类/t/{id}/, 搜索/s/wd/{kw}.html

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

# ==================== 分类配置 (63个, 已过滤2个未成年) ====================
CATEGORIES = [
    {"type_id": "1", "type_name": "日本有码"},
    {"type_id": "2", "type_name": "国产传媒"},
    {"type_id": "5", "type_name": "日本无码"},
    {"type_id": "7", "type_name": "日本巨乳"},
    {"type_id": "9", "type_name": "制服诱惑"},
    {"type_id": "13", "type_name": "中文字幕"},
    {"type_id": "17", "type_name": "国产精品"},
    {"type_id": "30", "type_name": "欧美"},
    {"type_id": "32", "type_name": "巨乳无码"},
    {"type_id": "34", "type_name": "人妻无码"},
    {"type_id": "35", "type_name": "制服无码"},
    {"type_id": "38", "type_name": "麻豆合集"},
    {"type_id": "51", "type_name": "日本有码"},
    {"type_id": "58", "type_name": "日本口爆"},
    {"type_id": "84", "type_name": "VR"},
    {"type_id": "86", "type_name": "女优"},
    {"type_id": "87", "type_name": "三上悠亚"},
    {"type_id": "88", "type_name": "高桥圣子"},
    {"type_id": "89", "type_name": "波多野结衣"},
    {"type_id": "90", "type_name": "葵司"},
    {"type_id": "91", "type_name": "水卜櫻"},
    {"type_id": "92", "type_name": "紗倉真菜"},
    {"type_id": "93", "type_name": "桃乃木香奈"},
    {"type_id": "95", "type_name": "天使萌"},
    {"type_id": "96", "type_name": "相澤南"},
    {"type_id": "97", "type_name": "櫻空桃"},
    {"type_id": "100", "type_name": "山岸逢花"},
    {"type_id": "103", "type_name": "松本一香"},
    {"type_id": "104", "type_name": "木下日葵"},
    {"type_id": "109", "type_name": "葫芦影业"},
    {"type_id": "111", "type_name": "天美传媒"},
    {"type_id": "112", "type_name": "果冻传媒"},
    {"type_id": "113", "type_name": "蜜桃传媒"},
    {"type_id": "114", "type_name": "精东影业"},
    {"type_id": "115", "type_name": "皇家华人"},
    {"type_id": "120", "type_name": "兔子先生"},
    {"type_id": "131", "type_name": "91制片厂"},
    {"type_id": "136", "type_name": "久留木玲"},
    {"type_id": "141", "type_name": "日本番號"},
    {"type_id": "142", "type_name": "200GANA"},
    {"type_id": "143", "type_name": "300MIUM"},
    {"type_id": "146", "type_name": "259LUXU"},
    {"type_id": "149", "type_name": "300MAAN"},
    {"type_id": "163", "type_name": "国产视频"},
    {"type_id": "186", "type_name": "STARS"},
    {"type_id": "190", "type_name": "MIAA"},
    {"type_id": "191", "type_name": "SSIS"},
    {"type_id": "207", "type_name": "夢乃愛華"},
    {"type_id": "221", "type_name": "日本无码"},
    {"type_id": "223", "type_name": "乱伦无码"},
    {"type_id": "224", "type_name": "强奸无码"},
    {"type_id": "225", "type_name": "综合番号"},
    {"type_id": "226", "type_name": "猫爪影像"},
    {"type_id": "227", "type_name": "综合传媒"},
    {"type_id": "231", "type_name": "扣扣传媒"},
    {"type_id": "232", "type_name": "网曝黑料"},
    {"type_id": "233", "type_name": "主播大秀"},
    {"type_id": "234", "type_name": "自拍/偷拍"},
    {"type_id": "235", "type_name": "国产自拍"},
    {"type_id": "237", "type_name": "抖阴视频"},
    {"type_id": "238", "type_name": "AV解说"},
    {"type_id": "239", "type_name": "探花系列"},
    {"type_id": "241", "type_name": "网红头条"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://yjuyg-91207-zmo5ae.miupiupiupiav131b72.top"
        self.rawSite = "https://yjuyg-91207-zmo5ae.miupiupiupiav131b72.top"
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
        """从HTML中解析视频列表 (封面src属性, 标题alt属性)"""
        vod_list = []
        pattern = r'<a[^>]*href="/voddetail/(\d+)/"[^>]*>(.*?)</a>'
        for vid, content in re.findall(pattern, html, re.S):
            # 封面
            cover_m = re.search(r'src="([^"]+\.(?:jpg|png|jpeg|webp))"', content)
            if not cover_m:
                cover_m = re.search(r'data-(?:original|src|lazy)="([^"]+)"', content)
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
        # 首页在/light/子路径
        html = self._fetch(self.siteUrl + "/light/")
        result["list"] = self._parse_videos(html) if html else []
        return result

    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, page=1, *args):
        result = {}
        page = int(page)
        url = f"{self.siteUrl}/t/{tid}/"
        if page > 1:
            url += f"page/{page}/"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        # 分页 (站点分页链接可能由JS加载, 默认999页)
        pages = re.findall(r'/t/' + re.escape(tid) + r'/page/(\d+)/', html)
        max_page = max(int(p) for p in pages) if pages else 999
        result["page"] = page
        result["pagecount"] = max_page
        result["limit"] = 54
        result["total"] = max_page * 54
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
            # 详情页 (获取标题和封面)
            dhtml = self._fetch(f"{self.siteUrl}/voddetail/{vod_id}/")
            vod_name = ""
            vod_pic = ""
            if dhtml:
                title_m = re.search(r'<title>(.*?)</title>', dhtml, re.S)
                if title_m:
                    vod_name = title_m.group(1).split(' - ')[0].strip()
                cover_m = re.search(r'src="([^"]+\.(?:jpg|png|jpeg|webp))"', dhtml)
                if cover_m:
                    vod_pic = cover_m.group(1)
            # 播放页 (获取m3u8)
            play_url = ""
            play_from = "naixx"
            phtml = self._fetch(f"{self.siteUrl}/v/{vod_id}/")
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
                            play_from = pa.get('from', 'naixx')
                        except Exception:
                            pass
                # 兜底: 直接找m3u8
                if not play_url:
                    m3u8_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', phtml)
                    if m3u8_m:
                        play_url = m3u8_m.group(1)
            if not vod_name:
                vod_name = vod_id
            if is_minor(vod_name):
                continue
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
        url = f"{self.siteUrl}/s/wd/{key_enc}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        result["page"] = page
        result["pagecount"] = 1
        result["limit"] = 25
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
        return "91成人 Spider loaded"

    def getName(self):
        return "91成人"

    def destroy(self):
        self._session = None
