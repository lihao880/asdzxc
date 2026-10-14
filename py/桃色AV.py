# -*- coding: utf-8 -*-
# 桃色AV TVBox 四壳通用 Python Spider
# 站点: https://www.taoseav1.cc/aa/?id=yng
# 结构: 苹果CMSv10变体, 无详情页(播放页兼详情), player_aaaa encrypt=0直出m3u8
# 分类: /aa/index.php/vod/type/id/{id}.html, 播放: /aa/index.php/vod/play/id/{id}/sid/{s}/nid/{n}.html
# 搜索: /aa/index.php/vod/search.html?wd=, 列表: ul.video-list, 标题在<text>标签, 封面data-original

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

# ==================== 未成年过滤关键词 ====================
MINOR_KEYWORDS = ['萝莉', '幼女', '少女', '童', 'teen', 'loli', 'schoolgirl', '未成年']

def is_minor(text):
    if not text:
        return False
    t = text.lower()
    return any(kw.lower() in t for kw in MINOR_KEYWORDS)

# ==================== 分类配置 (39个, 已剔除萝莉) ====================
CATEGORIES = [
    {"type_id": "2", "type_name": "精品推荐"},
    {"type_id": "3", "type_name": "国产色情"},
    {"type_id": "4", "type_name": "主播直播"},
    {"type_id": "5", "type_name": "亚洲无码"},
    {"type_id": "6", "type_name": "亚洲有码"},
    {"type_id": "7", "type_name": "中文字幕"},
    {"type_id": "8", "type_name": "巨乳美乳"},
    {"type_id": "45", "type_name": "人妻熟女"},
    {"type_id": "10", "type_name": "强奸乱伦"},
    {"type_id": "11", "type_name": "欧美精品"},
    {"type_id": "13", "type_name": "伦理三级"},
    {"type_id": "14", "type_name": "自拍偷拍"},
    {"type_id": "15", "type_name": "制服丝袜"},
    {"type_id": "16", "type_name": "口交颜射"},
    {"type_id": "17", "type_name": "恋腿狂魔"},
    {"type_id": "19", "type_name": "日本精品"},
    {"type_id": "20", "type_name": "Cosplay"},
    {"type_id": "21", "type_name": "素人自拍"},
    {"type_id": "22", "type_name": "台湾辣妹"},
    {"type_id": "23", "type_name": "韩国御姐"},
    {"type_id": "24", "type_name": "唯美港姐"},
    {"type_id": "25", "type_name": "东南亚AV"},
    {"type_id": "26", "type_name": "欺辱凌辱"},
    {"type_id": "28", "type_name": "剧情介绍"},
    {"type_id": "29", "type_name": "多人多P"},
    {"type_id": "30", "type_name": "91探花"},
    {"type_id": "31", "type_name": "网红流出"},
    {"type_id": "32", "type_name": "野外露出"},
    {"type_id": "33", "type_name": "古装扮演"},
    {"type_id": "34", "type_name": "女优系列"},
    {"type_id": "35", "type_name": "可爱学生"},
    {"type_id": "38", "type_name": "风情旗袍"},
    {"type_id": "39", "type_name": "兽耳系列"},
    {"type_id": "40", "type_name": "瑜伽裤"},
    {"type_id": "41", "type_name": "闷骚护士"},
    {"type_id": "42", "type_name": "网曝门"},
    {"type_id": "43", "type_name": "传媒出品"},
    {"type_id": "44", "type_name": "女同性恋"},
]


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://www.taoseav1.cc"
        self.rawSite = "https://www.taoseav1.cc"
        self.HOST = self.siteUrl
        self._session = None
        self._base_path = "/aa/index.php"

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
        # 匹配 video-list 中的 li
        li_pattern = re.compile(
            r'<li>\s*<a[^>]*href="(/aa/index\.php/vod/play/id/(\d+)/sid/\d+/nid/\d+\.html)"[^>]*>.*?'
            r'data-original="([^"]+)".*?'
            r'<h3 class="video-title">.*?<text>([^<]+)</text>',
            re.S
        )
        for m in li_pattern.finditer(html):
            vod_id = m.group(2)
            vod_name = m.group(4).strip()
            vod_pic = self._abs_url(m.group(3).strip())
            # 铁律13: 未成年跳过
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
        html = self._fetch(self.siteUrl + "/aa/?id=yng")
        result["list"] = self._parse_videos(html)
        return result

    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, page=1, *args):
        result = {}
        page = int(page)
        if page <= 1:
            url = f"{self.siteUrl}{self._base_path}/vod/type/id/{tid}.html"
        else:
            url = f"{self.siteUrl}{self._base_path}/vod/type/id/{tid}/page/{page}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        result["page"] = page
        result["pagecount"] = 999
        result["limit"] = 40
        result["total"] = 999 * 40
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
            # 无详情页, 直接用播放页兼详情
            play_url = f"{self.siteUrl}{self._base_path}/vod/play/id/{vod_id}/sid/1/nid/1.html"
            html = self._fetch(play_url)
            if not html:
                continue
            # 从 player_aaaa 的 vod_data 取标题
            vod_name = ""
            vod_pic = ""
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
                        vd = data.get("vod_data", {})
                        vod_name = vd.get("vod_name", "").strip()
                        vod_pic = self._abs_url(vd.get("vod_pic", ""))
                    except Exception:
                        pass
            # 兜底: 从页面title取
            if not vod_name:
                title_m = re.search(r'<title>(.*?)</title>', html, re.S)
                if title_m:
                    vod_name = title_m.group(1).strip().split('-')[0].strip()
            # 铁律13: 未成年跳过
            if is_minor(vod_name):
                continue
            # 提取播放线路列表
            play_links = re.findall(
                r'href="(/aa/index\.php/vod/play/id/\d+/sid/(\d+)/nid/(\d+)\.html)"[^>]*>([^<]*)</a>',
                html
            )
            if not play_links:
                play_links = [(play_url, "1", "1", "HD")]
            # 按线路分组
            lines = {}
            for href, sid, nid, name in play_links:
                name = name.strip() or f"线路{sid}"
                if sid not in lines:
                    lines[sid] = {"name": name, "eps": []}
                lines[sid]["eps"].append((nid, href))
            # 构造播放列表
            play_from_list = []
            play_url_list = []
            for sid, line_data in lines.items():
                play_from_list.append(line_data["name"])
                eps_str = "#".join([f"第{nid}集${href}" for nid, href in line_data["eps"]])
                play_url_list.append(eps_str)
            vod_play_from = "$$$".join(play_from_list)
            vod_play_url = "$$$".join(play_url_list)
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
        if not id.startswith("http"):
            play_url = self._abs_url(id)
        else:
            play_url = id
        html = self._fetch(play_url)
        play_url_final = ""
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
                        play_url_final = raw_url
                    except Exception:
                        pass
            if not play_url_final:
                m3u8_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                if m3u8_m:
                    play_url_final = m3u8_m.group(1)
        result["parse"] = 0
        result["jx"] = 0
        result["url"] = play_url_final
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
            url = f"{self.siteUrl}{self._base_path}/vod/search.html?wd={key_enc}"
        else:
            url = f"{self.siteUrl}{self._base_path}/vod/search/page/{page}/wd/{key_enc}.html"
        html = self._fetch(url)
        vod_list = self._parse_videos(html)
        result["page"] = page
        result["pagecount"] = 99
        result["limit"] = 40
        result["total"] = 99 * 40
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
        return "桃色AV Spider loaded"

    def getName(self):
        return "桃色AV"

    def destroy(self):
        self._session = None
