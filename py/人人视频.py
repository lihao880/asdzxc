# coding=utf-8
# 文件名: rersp_enhanced.py
# 站点: https://rersp.cfd/
# 参考: avmars.py 多层降级 + WebView 嗅探

import re
import json
import urllib.request
import urllib.parse
from urllib.parse import urljoin

class Spider:
    def __init__(self):
        self.extend = ""
        self.domains = [
            "https://rersp.cfd",
            "https://91991cyp.cfd"
        ]
        self.base_url = self.domains[0]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://rersp.cfd/"
        }
        self.timeout = 15

    def init(self, extend=""):
        self.extend = str(extend) if extend else ""
        if self.extend and self.extend.startswith("{"):
            try:
                config = json.loads(self.extend)
                if "base_url" in config:
                    self.base_url = config["base_url"]
            except:
                pass

    def getDependence(self):
        return ""

    def _fetch(self, url):
        for domain in self.domains:
            full_url = url if url.startswith("http") else domain + url
            try:
                req = urllib.request.Request(full_url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    content = resp.read().decode('utf-8', errors='ignore')
                    if content and len(content) > 500:
                        self.base_url = domain
                        return content
            except Exception:
                continue
        return ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = str(url).replace("\\/", "/").replace("&amp;", "&").strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return urljoin(self.base_url, url)
        if not url.startswith("http"):
            return urljoin(self.base_url + "/", url)
        return url

    def _clean_text(self, text):
        if not text:
            return ""
        return re.sub(r"\s+", " ", str(text)).strip()

    def _extract_vod_id(self, url):
        m = re.search(r'/id/(\d+)\.html', url)
        return m.group(1) if m else url

    def homeContent(self, filter):
        categories = [
            {"type_id": "1", "type_name": "视频一区"},
            {"type_id": "6", "type_name": "国产视频"},
            {"type_id": "7", "type_name": "中文字幕"},
            {"type_id": "8", "type_name": "国产传媒"},
            {"type_id": "9", "type_name": "日本有码"},
            {"type_id": "10", "type_name": "日本无码"},
            {"type_id": "11", "type_name": "欧美无码"},
            {"type_id": "12", "type_name": "强奸乱轮"},
            {"type_id": "2", "type_name": "视频二区"},
            {"type_id": "13", "type_name": "制服诱惑"},
            {"type_id": "14", "type_name": "国产主播"},
            {"type_id": "15", "type_name": "激情动漫"},
            {"type_id": "16", "type_name": "明星换脸"},
            {"type_id": "17", "type_name": "抖阴视频"},
            {"type_id": "18", "type_name": "女优明星"},
            {"type_id": "20", "type_name": "网爆黑料"},
            {"type_id": "3", "type_name": "视频三区"},
            {"type_id": "21", "type_name": "VR视角"},
            {"type_id": "22", "type_name": "AV解说"},
            {"type_id": "23", "type_name": "极品媚黑"},
            {"type_id": "24", "type_name": "萝莉少女"},
            {"type_id": "25", "type_name": "女同性恋"},
            {"type_id": "26", "type_name": "人妖系列"},
            {"type_id": "27", "type_name": "网红头条"},
        ]
        filters = {}
        for cat in categories:
            filters[cat["type_id"]] = [
                {
                    "key": "order",
                    "name": "排序",
                    "value": [
                        {"n": "最新", "v": "time"},
                        {"n": "最热", "v": "hits"},
                        {"n": "随机", "v": "rand"}
                    ]
                }
            ]
        return {"class": categories, "filters": filters}

    def homeVideoContent(self):
        return self.categoryContent("1", "1", False, {})

    def categoryContent(self, tid, pg, filter=False, extend=None):
        url = f"{self.base_url}/index.php/vod/type/id/{tid}/page/{pg}.html"
        html = self._fetch(url)
        if not html:
            return {"list": [], "page": int(pg), "pagecount": 1}

        videos = []
        items = re.findall(
            r'<li>\s*<a[^>]+class="thumbnail"[^>]+href="([^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"[^>]*>.*?</a>.*?<h5[^>]*>.*?<a[^>]+href="[^"]+"[^>]*>([^<]+)</a>.*?</h5>.*?<p[^>]*>([^<]+)</p>',
            html,
            re.S
        )
        if not items:
            items = re.findall(
                r'href="(/index\.php/vod/detail/id/\d+\.html)".*?src="([^"]+)".*?alt="([^"]*)".*?<a[^>]+>([^<]+)</a>.*?<p>([^<]+)</p>',
                html,
                re.S
            )
        for item in items:
            if len(item) >= 5:
                detail_url, img, alt, title, info = item[0], item[1], item[2], item[3], item[4]
                vod_id = self._extract_vod_id(detail_url)
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": self._clean_text(title or alt),
                    "vod_pic": self._fix_url(img),
                    "vod_remarks": self._clean_text(info.split('-')[0] if info else "")
                })
            elif len(item) >= 4:
                detail_url, img, title, info = item[0], item[1], item[2], item[3]
                vod_id = self._extract_vod_id(detail_url)
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": self._clean_text(title),
                    "vod_pic": self._fix_url(img),
                    "vod_remarks": self._clean_text(info.split('-')[0] if info else "")
                })

        # 分页解析
        pagecount = int(pg)
        page_match = re.search(r'共(\d+)页', html)
        if page_match:
            pagecount = int(page_match.group(1))
        else:
            pages = re.findall(r'/page/(\d+)/', html)
            if pages:
                pagecount = max([int(p) for p in pages])
            last_match = re.search(r'尾页</a>\s*</li>.*?/page/(\d+)/', html)
            if last_match:
                pagecount = int(last_match.group(1))
            total_match = re.search(r'共(\d+)条', html)
            if total_match:
                total = int(total_match.group(1))
                limit = 20
                pagecount = (total + limit - 1) // limit

        if pagecount < int(pg):
            pagecount = int(pg)

        return {
            "list": videos,
            "page": int(pg),
            "pagecount": pagecount,
            "limit": 20,
            "total": len(videos)
        }

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        if vid.isdigit():
            url = f"{self.base_url}/index.php/vod/detail/id/{vid}.html"
        else:
            url = self._fix_url(vid)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        title = re.search(r'<h2[^>]*>([^<]+)</h2>', html)
        title = self._clean_text(title.group(1)) if title else ""
        if not title:
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                title = self._clean_text(title_match.group(1).split("剧情介绍")[0].split("在线播放")[0])

        pic = re.search(r'<img[^>]+src="([^"]+)"[^>]*alt="[^"]*"', html)
        pic = self._fix_url(pic.group(1)) if pic else ""

        desc = re.search(r'<div[^>]*class="[^"]*detail-content[^"]*"[^>]*>([\s\S]*?)</div>', html)
        desc = self._clean_text(re.sub(r'<[^>]+>', '', desc.group(1) if desc else "")) if desc else ""

        play_url = ""
        play_from = "默认"

        play_items = re.findall(
            r'<li><a[^>]*href="(/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"[^>]*>([^<]+)</a></li>',
            html,
            re.S
        )
        if play_items:
            for p_url, p_name in play_items:
                if "立即播放" in p_name or "第" in p_name:
                    play_url = self._fix_url(p_url)
                    break

        if not play_url:
            iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', html)
            if iframe_match:
                play_url = self._fix_url(iframe_match.group(1))

        if play_url:
            play_url = f"{vid}${play_url}"

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": play_from,
            "vod_play_url": play_url
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg):
        if not key:
            return {"list": [], "page": int(pg or "1"), "pagecount": 1}
        q = urllib.parse.quote(self._clean_text(key))
        url = f"{self.base_url}/index.php/vod/search/page/{pg}/wd/{q}.html"
        html = self._fetch(url)
        videos = []
        if html:
            items = re.findall(
                r'href="(/index\.php/vod/detail/id/\d+\.html)".*?src="([^"]+)".*?alt="([^"]*)".*?<a[^>]+>([^<]+)</a>.*?<p>([^<]+)</p>',
                html,
                re.S
            )
            for item in items:
                detail_url, img, alt, title, info = item
                vod_id = self._extract_vod_id(detail_url)
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": self._clean_text(title or alt),
                    "vod_pic": self._fix_url(img),
                    "vod_remarks": self._clean_text(info.split('-')[0] if info else "")
                })
        return {"list": videos, "page": int(pg or "1"), "pagecount": 1}

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "url": ""}

        if not id:
            return {"parse": 1, "url": ""}

        if id.startswith("http") and (".m3u8" in id or ".mp4" in id):
            return {"parse": 0, "url": id}

        play_url = id
        vod_id = None

        if "$" in id:
            parts = id.split("$")
            if len(parts) == 2:
                vod_id = parts[0]
                play_url = parts[1]
            else:
                for part in parts:
                    if part.startswith("http"):
                        play_url = part
                    elif part.isdigit():
                        vod_id = part

        if not play_url.startswith("http"):
            play_url = self._fix_url(play_url)

        if play_url and (play_url.endswith(".m3u8") or ".mp4" in play_url):
            return {"parse": 0, "url": play_url}

        html = self._fetch(play_url)
        if html:
            m3u8_url = self._extract_m3u8(html)
            if m3u8_url:
                return {"parse": 0, "url": m3u8_url}

            iframe_url = self._extract_iframe(html)
            if iframe_url:
                return {"parse": 1, "url": iframe_url}

        return {"parse": 1, "url": play_url}

    def _extract_m3u8(self, html):
        if not html:
            return None

        patterns = [
            r'var\s+player_aaaa\s*=\s*({[^;]+})',
            r'var\s+uul\s*=\s*[\'"]([^\'"]+\.m3u8[^\'"]*)[\'"]',
            r'(https?://[^\s\'"]+\.m3u8[^\s\'"]*)',
            r'<iframe[^>]*src="([^"]*\.m3u8[^"]*)"[^>]*>',
            r'[?&]url=([^&]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                url = match.group(1)
                if url:
                    if url.startswith("{") and "url" in url:
                        try:
                            data = json.loads(url)
                            if data.get("url"):
                                return data["url"]
                        except:
                            pass
                        continue
                    try:
                        url = urllib.parse.unquote(url)
                    except:
                        pass
                    url = re.sub(r'[\'";]+$', '', url).strip()
                    if url.startswith("http") and ".m3u8" in url:
                        return url
        return None

    def _extract_iframe(self, html):
        if not html:
            return None
        match = re.search(r'<iframe[^>]+src="([^"]+)"[^>]*>', html)
        return match.group(1) if match else None

    def localProxy(self, param):
        return None

    def isVideoFormat(self, url):
        return url and (".m3u8" in url or ".mp4" in url)

    def destroy(self):
        pass