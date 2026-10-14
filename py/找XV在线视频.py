# coding: utf-8
# 站点: 找XV在线视频 (https://findqv.com)
# CMS: MacCMS
# 类型: 成人影视

import re
import json
import urllib.parse
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://findqv.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "21", "type_name": "新品日番"},
            {"type_id": "20", "type_name": "本土精选"},
            {"type_id": "25", "type_name": "汉译字幕"},
            {"type_id": "23", "type_name": "动漫专区"},
            {"type_id": "24", "type_name": "欧美猛货"},
            {"type_id": "22", "type_name": "经典电影"},
            {"type_id": "26", "type_name": "山寨解说"},
            {"type_id": "27", "type_name": "素人码无"}
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}

    def getName(self):
        return "找XV在线视频"

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def _fetch_html(self, url):
        try:
            res = self.fetch(url, headers=self.headers, timeout=15)
            if res is None:
                return ""
            if hasattr(res, "text") and res.text:
                return res.text
            if hasattr(res, "content") and res.content:
                try:
                    return res.content.decode('utf-8', errors='ignore')
                except Exception:
                    pass
            return ""
        except Exception:
            return ""

    def _parse_video_list(self, html):
        items = []
        blocks = re.findall(r'<div class="pic"><ul>(.*?)</ul></div>', html, re.S)
        for block in blocks:
            lis = re.findall(r'<li><a href="([^"]+)" title="([^"]*)"[^>]*>.*?<img src="([^"]+)".*?<span>([^<]*)</span>\s*([^<]*)</a></li>', block, re.S)
            for href, title, pic, span, name in lis:
                full_title = (span + " " + name).strip()
                if not full_title and title:
                    full_title = title
                if full_title:
                    items.append({
                        "vod_id": href.split("/")[-1].replace(".html", ""),
                        "vod_name": full_title,
                        "vod_pic": pic,
                        "vod_remarks": ""
                    })
        return items

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/")
        if not html:
            return {"list": []}
        return {"list": self._parse_video_list(html)[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        url = f"{self.host}/vdtype/{tid}-{page}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

        items = self._parse_video_list(html)
        page_info = re.search(r'共(\d+)条数据,当前(\d+)/(\d+)页', html)
        if page_info:
            total = int(page_info.group(1))
            current = int(page_info.group(2))
            total_pages = int(page_info.group(3))
        else:
            total = 0
            current = page
            total_pages = 1

        return {
            "list": items,
            "page": current,
            "pagecount": total_pages,
            "limit": 20,
            "total": total
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        if isinstance(ids, list):
            vid = str(ids[0])
        else:
            vid = str(ids)
        url = f"{self.host}/vddetail/{vid}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        title_match = re.search(r'<dt>片名：([^<]+)</dt>', html)
        title = title_match.group(1).strip() if title_match else ""

        pic_match = re.search(r'<div class="media"><ul><li><a href="[^"]+"><img src="([^"]+)"', html)
        pic = pic_match.group(1) if pic_match else ""

        play_link = ""
        play_match = re.search(r'<dt class="playurl2"><a href="([^"]+)">点击播放</a>', html)
        if play_match:
            play_link = play_match.group(1)

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": "播放$" + play_link if play_link else ""
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        url = f"{self.host}/vdsearch/-.html?wd={urllib.parse.quote(key)}"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": 1}

        items = self._parse_video_list(html)
        return {"list": items[:20], "page": 1}

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "&url=" + urllib.parse.quote(str(url or ""), safe="")

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": ""}

        if id.startswith("/vdplay/") or id.startswith(self.host + "/vdplay/"):
            play_url = urllib.parse.urljoin(self.host, id)
            html = self._fetch_html(play_url)
            if not html:
                return {"parse": 1, "url": play_url, "header": self.headers}

            m3u8_match = re.search(r'"url":"([^"]+\.m3u8)"', html)
            if m3u8_match:
                m3u8_url = m3u8_match.group(1).replace("\\/", "/")
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(m3u8_url),
                    "header": {"User-Agent": self.headers["User-Agent"]}
                }
            return {"parse": 1, "url": play_url, "header": self.headers}

        if id.endswith(".m3u8"):
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id.replace("\\/", "/")),
                "header": {"User-Agent": self.headers["User-Agent"]}
            }

        return {"parse": 1, "url": id, "header": self.headers}

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤"""
        try:
            # 兼容不同壳端传入的 param (dict / string / query string)
            if isinstance(param, dict):
                target = param.get("url", "")
            else:
                target = str(param or "")
            
            if target.startswith("url="):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ""))
            
            if not target:
                return [400, "text/plain", b"invalid url"]

            res = self.fetch(target, headers={"User-Agent": self.headers["User-Agent"]}, timeout=15)
            if not res:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(res, "content", b"") or b""
            if not content and hasattr(res, "text") and res.text:
                content = res.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]

            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode('utf-8')
            return [500, "text/plain", error_msg]

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urllib.parse.urlparse(source_url)
        source_path = parsed.path
        source_parts = [p for p in source_path.split("/") if p]
        content_root = "/" + "/".join(source_parts[:2]) + "/" if len(source_parts) >= 2 else ""

        segments = []
        pending = []

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media = urllib.parse.urljoin(source_url, line)
                if content_root and content_root not in urllib.parse.urlparse(media).path:
                    pass
                else:
                    segments.extend(pending)
                    segments.append(media)
                pending = []
                continue
            segments.append(self._rewrite_m3u8_tag(line, source_url))

        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line == "#EXT-X-KEY:METHOD=NONE" or line == "#EXT-X-DISCONTINUITY":
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)
        while len(out) > 1 and out[-2] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop(-2)
        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith("http://") or uri.startswith("https://"):
                    return 'URI="' + uri + '"'
                return 'URI="' + urllib.parse.urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith("http://") or line.startswith("https://"):
                return line
            return urllib.parse.urljoin(source_url, line)
        return line

    def destroy(self):
        pass