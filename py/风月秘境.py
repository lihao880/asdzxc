# -*- coding: utf-8 -*-
# 风月秘境 TVBox 四壳通用 Python Spider
# 站点: https://xn--0921gw9-kk8lp89p.rwxmv0d.sbs/
# 结构: 自定义CMS(nky模板), 分类/vod-type/id-{id}-by-time-pg-{page}.html
# 详情/vod-detail/id-{id}.html, 播放/vod-play/id-{id}.html(线路1) + /vod-play/idb-{id}.html(线路2)
# 反爬: 标题/分类名base64编码在d('...')中, 含display:none诱饵span需清洗
# 播放页m3u8直出JS

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

# ==================== 未成年过滤 ====================
MINOR_KEYWORDS = ['萝莉', '幼女', '少女', '童', 'teen', 'loli', 'schoolgirl', '未成年']

def is_minor(text):
    if not text:
        return False
    t = text.lower()
    return any(kw.lower() in t for kw in MINOR_KEYWORDS)

# ==================== base64标题解码 ====================
def decode_d_text(b64):
    """解码d('base64')中的文本, 移除display:none诱饵span"""
    try:
        decoded = base64.b64decode(b64).decode('utf-8', errors='ignore')
        # 移除display:none的span
        cleaned = re.sub(r'<span[^>]*display:\s*none[^>]*>.*?</span>', '', decoded, flags=re.S)
        # 移除所有HTML标签
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        return cleaned.strip()
    except Exception:
        return ""

# ==================== 分类配置 (42个, 已过滤未成年和"观看更多") ====================
CATEGORIES = [
    {"type_id": "13", "type_name": "日本素人"},
    {"type_id": "3", "type_name": "华语AV"},
    {"type_id": "4", "type_name": "黑料吃瓜"},
    {"type_id": "5", "type_name": "欧美"},
    {"type_id": "6", "type_name": "禁漫"},
    {"type_id": "7", "type_name": "学生"},
    {"type_id": "8", "type_name": "乱伦"},
    {"type_id": "9", "type_name": "探花"},
    {"type_id": "43", "type_name": "VR视角"},
    {"type_id": "21", "type_name": "中文字幕"},
    {"type_id": "22", "type_name": "国产传媒"},
    {"type_id": "23", "type_name": "日本有码"},
    {"type_id": "24", "type_name": "日本无码"},
    {"type_id": "25", "type_name": "欧美无码"},
    {"type_id": "26", "type_name": "强奸乱伦"},
    {"type_id": "27", "type_name": "制服诱惑"},
    {"type_id": "59", "type_name": "人兽性交"},
    {"type_id": "45", "type_name": "国产主播"},
    {"type_id": "46", "type_name": "国产自拍"},
    {"type_id": "47", "type_name": "无码专区"},
    {"type_id": "48", "type_name": "欧美性爱"},
    {"type_id": "49", "type_name": "熟女人妻"},
    {"type_id": "50", "type_name": "强奸乱伦"},
    {"type_id": "51", "type_name": "巨乳美乳"},
    {"type_id": "217", "type_name": "恋腿狂魔"},
    {"type_id": "184", "type_name": "强奸乱伦"},
    {"type_id": "183", "type_name": "人妻熟女"},
    {"type_id": "182", "type_name": "巨乳美乳"},
    {"type_id": "181", "type_name": "中文字幕"},
    {"type_id": "180", "type_name": "亚洲有码"},
    {"type_id": "179", "type_name": "亚洲无码"},
    {"type_id": "178", "type_name": "主播直播"},
    {"type_id": "131", "type_name": "同性恋"},
    {"type_id": "109", "type_name": "亚洲无码"},
    {"type_id": "110", "type_name": "制服诱惑"},
    {"type_id": "111", "type_name": "强奸乱伦"},
    {"type_id": "112", "type_name": "巨乳美乳"},
    {"type_id": "113", "type_name": "AI换脸"},
    {"type_id": "114", "type_name": "中文字幕"},
    {"type_id": "115", "type_name": "角色扮演"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://xn--0921gw9-kk8lp89p.rwxmv0d.sbs"
        self.rawSite = "https://xn--0921gw9-kk8lp89p.rwxmv0d.sbs"
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
        """从HTML中解析视频列表 (封面data-original懒加载, 标题base64编码在d('...')中)"""
        vod_list = []
        # 匹配卡片块
        card_pattern = r'<div class="col-md-3 col-xs-6 portfolio-item[^"]*">(.*?)(?=<div class="col-md-3 col-xs-6 portfolio-item|$)'
        for card in re.findall(card_pattern, html, re.S):
            # ID
            id_m = re.search(r'/vod-detail/id-(\d+)\.html', card)
            if not id_m:
                continue
            vid = id_m.group(1)
            # 封面 (data-original懒加载)
            cover_m = re.search(r'data-original="([^"]+)"', card)
            cover = cover_m.group(1) if cover_m else ""
            # 标题 (base64 in d('...'))
            title = ""
            d_matches = re.findall(r"d\('([^']+)'\)", card)
            for b64 in d_matches:
                t = decode_d_text(b64)
                if t and len(t) > 2 and not t.startswith('上架') and not t.startswith('点击'):
                    title = t
                    break
            if not title:
                # 兜底: alt属性
                alt_m = re.search(r'alt="([^"]+)"', card)
                title = alt_m.group(1) if alt_m else vid
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
        url = f"{self.siteUrl}/vod-type/id-{tid}-by-time-pg-{page}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        result["page"] = page
        result["pagecount"] = 999
        result["limit"] = 12
        result["total"] = 999 * 12
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
            html = self._fetch(f"{self.siteUrl}/vod-detail/id-{vod_id}.html")
            if not html:
                continue
            # 标题 (base64解码, 跳过常见标签, 优先长标题)
            title = ""
            d_matches = re.findall(r"d\('([^']+)'\)", html)
            skip_labels = ['金牌推荐', '热门推荐', '最新发布', '观看更多', '上架时间', '点击数', '播放量', '收藏', '分享', '推荐', '最新', '热门']
            skip_keywords = ['年滿', '法定年齡', '網站內容分級', '未滿18', '18歲', '成人在線']
            candidates = []
            for b64 in d_matches:
                t = decode_d_text(b64)
                if t and len(t) > 3 and len(t) < 100:
                    if not any(t.startswith(s) for s in skip_labels) and not any(kw in t for kw in skip_keywords):
                        candidates.append(t)
            if candidates:
                title = max(candidates, key=len)
            if not title:
                # 兜底: og:title
                og_m = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
                if og_m:
                    title = og_m.group(1)
            if not title:
                title = vod_id
            if is_minor(title):
                continue
            # 封面
            cover_m = re.search(r'data-original="([^"]+)"', html)
            if not cover_m:
                cover_m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
            vod_pic = cover_m.group(1) if cover_m else ""
            # 播放线路: /vod-play/id-{id}.html (线路1) + /vod-play/idb-{id}.html (线路2)
            play_froms = []
            play_urls = []
            # 线路1
            if '/vod-play/id-' + vod_id + '.html' in html:
                play_froms.append("线路1")
                play_urls.append(f"第1集${self.siteUrl}/vod-play/id-{vod_id}.html")
            # 线路2
            if '/vod-play/idb-' + vod_id + '.html' in html:
                play_froms.append("线路2")
                play_urls.append(f"第1集${self.siteUrl}/vod-play/idb-{vod_id}.html")
            # 兜底: 至少有线路1
            if not play_froms:
                play_froms.append("线路1")
                play_urls.append(f"第1集${self.siteUrl}/vod-play/id-{vod_id}.html")
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": self._abs_url(vod_pic),
                "vod_play_from": "$$$".join(play_froms),
                "vod_play_url": "$$$".join(play_urls),
            })
        result["list"] = vod_list
        return result

    # ==================== 4. playerContent ====================
    def playerContent(self, flag, id, vipFlags=None, *args):
        result = {}
        play_url = id if id.startswith("http") else self._abs_url(id)
        m3u8_url = play_url
        # 如果是播放页URL, 抓取获取m3u8
        if '/vod-play/' in play_url:
            html = self._fetch(play_url)
            if html:
                # m3u8直出JS
                m3u8_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                if m3u8_m:
                    m3u8_url = m3u8_m.group(1)
                # JS中的m3u8 (可能带引号)
                if not m3u8_url or '.m3u8' not in m3u8_url:
                    js_m3u8 = re.search(r'["\']([^"\']*\.m3u8[^"\']*)["\']', html)
                    if js_m3u8:
                        m3u8_url = js_m3u8.group(1)
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
        html = self._fetch(f"{self.siteUrl}/vod-search/wd-{key_enc}-by-time-pg-{page}.html")
        vod_list = self._parse_videos(html) if html else []
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
        return "风月秘境 Spider loaded"

    def getName(self):
        return "风月秘境"

    def destroy(self):
        self._session = None
