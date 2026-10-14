# coding: utf-8
# 伯爵视界 - TVBox/FongMi 爬虫
# 站点：https://xn--jgu84yxzx.bjstackxreach.site/
# CMS: MacCMS v10
# 特性: m3u8 本地代理 + 广告分片过滤

import re
import json
from urllib.parse import urljoin, quote, unquote, urlparse

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.site_url = "https://xn--jgu84yxzx.bjstackxreach.site"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.site_url + "/"
        }
        self.classes = [
            {"type_id": "22", "type_name": "女同性爱"},
            {"type_id": "28", "type_name": "人妖视频"},
            {"type_id": "30", "type_name": "捆绑调教"},
            {"type_id": "32", "type_name": "日本女优"},
            {"type_id": "34", "type_name": "中文字幕"},
            {"type_id": "38", "type_name": "欧美视频"},
            {"type_id": "42", "type_name": "国产精品"},
            {"type_id": "44", "type_name": "明星换脸"},
            {"type_id": "46", "type_name": "萝莉少女"},
            {"type_id": "48", "type_name": "网红主播"},
            {"type_id": "52", "type_name": "传媒拍摄"},
            {"type_id": "54", "type_name": "三级伦理"},
            {"type_id": "56", "type_name": "网暴黑料"},
            {"type_id": "58", "type_name": "激情动漫"},
            {"type_id": "60", "type_name": "全景视角"}
        ]
        self.filters = {cls["type_id"]: [] for cls in self.classes}

    def getName(self):
        return "伯爵视界"

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def destroy(self):
        pass

    def _decode(self, text):
        if not text:
            return text
        try:
            return json.loads('"' + text + '"')
        except:
            return text

    def _fetch_html(self, url, data=None):
        try:
            if data:
                res = self.fetch(url, data=data, headers=self.headers, timeout=15)
            else:
                res = self.fetch(url, headers=self.headers, timeout=15)
            if res is None:
                return ""
            if hasattr(res, "text") and res.text:
                return res.text
            if hasattr(res, "content") and res.content:
                try:
                    return res.content.decode('utf-8', errors='ignore')
                except:
                    pass
            if hasattr(res, "body") and res.body:
                if isinstance(res.body, bytes):
                    return res.body.decode('utf-8', errors='ignore')
                return str(res.body)
            if isinstance(res, str):
                return res
            return ""
        except Exception:
            return ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.site_url.rstrip("/") + url
        return self.site_url.rstrip("/") + "/" + url.lstrip("/")

    def _parse_video_list(self, html):
        videos = []
        if not html:
            return videos
        pattern = r'<div class="item[^"]*">.*?<a href="([^"]+)".*?<span class="duration">([^<]*)</span>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<strong class="thumb-title">([^<]*)</strong>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            href, duration, pic, title = match
            id_match = re.search(r'/id/(\d+)', href)
            vod_id = id_match.group(1) if id_match else href.strip()
            videos.append({
                "vod_id": vod_id,
                "vod_name": self._decode(title.strip()),
                "vod_pic": self._fix_url(pic.strip()),
                "vod_remarks": duration.strip()
            })
        return videos

    def _parse_page_info(self, html):
        page, total = 1, 1
        if not html:
            return {"page": 1, "pagecount": 1}
        cur_match = re.search(r'<li><a href="javascript:void\(0\);">\s*<div[^>]*>(\d+)</div>\s*</a>', html)
        if cur_match:
            page = int(cur_match.group(1))
        total_match = re.search(r'data-total="(\d+)"', html)
        if total_match:
            total = int(total_match.group(1))
        return {"page": page, "pagecount": total}

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.site_url)
        return {"list": self._parse_video_list(html)[:20]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        if pg <= 1:
            url = f"{self.site_url}/index.php/vod/type/id/{tid}.html"
        else:
            url = f"{self.site_url}/index.php/index/index/page/{pg}.html"
        html = self._fetch_html(url)
        info = self._parse_page_info(html)
        return {
            "list": self._parse_video_list(html),
            "page": pg,
            "pagecount": info.get("pagecount", 1)
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        if isinstance(ids, list):
            vid = ids[0] if ids else ""
        else:
            vid = ids
        if not vid:
            return {"list": []}
        vid = str(vid)
        if re.match(r'^\d+$', vid):
            url = f"{self.site_url}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        else:
            url = self._fix_url(vid)
        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        id_match = re.search(r'"id":"(\d+)"', html)
        real_vid = id_match.group(1) if id_match else vid

        title = ""
        m = re.search(r'正在播放：([^<]+)</h2>', html)
        if m:
            title = self._decode(m.group(1).strip())
        if not title:
            m = re.search(r'"vod_name":"([^"]+)"', html)
            if m:
                title = self._decode(m.group(1).strip())
        if not title:
            title = "未知影片"

        pic = ""
        m = re.search(r'<img[^>]+class="theimg"[^>]+src="([^"]+)"', html)
        if m:
            pic = self._fix_url(m.group(1))

        desc = ""
        m = re.search(r'"vod_content":"([^"]*)"', html)
        if m:
            desc = self._decode(m.group(1).strip())
        if not desc:
            desc = title

        play_from = "播放"
        play_url = ""
        m = re.search(r'"url":"([^"]+\.m3u8[^"]*)"', html)
        if m:
            m3u8_url = m.group(1).replace('\\/', '/')
            play_url = f"播放${m3u8_url}"
        if not play_url:
            m = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
            if m:
                m3u8_url = m.group(0).replace('\\/', '/')
                play_url = f"播放${m3u8_url}"
        if not play_url:
            m = re.search(r'"id":"(\d+)"', html)
            if m:
                play_url = f"播放${m.group(1)}"
            else:
                play_url = f"播放${vid}"
        m = re.search(r'"from":"([^"]+)"', html)
        if m:
            play_from = m.group(1)

        return {"list": [{
            "vod_id": real_vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": desc,
            "vod_play_from": play_from,
            "vod_play_url": play_url
        }]}

    def searchContent(self, key, quick, pg="1"):
        if not key or not key.strip():
            return {"list": [], "page": 1}
        pg = int(pg) if pg else 1
        encoded_key = quote(key.strip(), safe="")
        url = f"{self.site_url}/index.php/vod/search/wd/{encoded_key}.html"
        html = self._fetch_html(url)
        if not html:
            html = self._fetch_html(f"{self.site_url}/index.php/vod/search.html", data={"wd": key.strip()})
        info = self._parse_page_info(html)
        return {
            "list": self._parse_video_list(html),
            "page": pg,
            "pagecount": info.get("pagecount", 1)
        }

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "&url=" + quote(str(url or ""), safe="")

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {"parse": 1, "url": ""}
        id = str(id).replace('\\/', '/')
        if id.startswith("http") and (".m3u8" in id or ".mp4" in id):
            if ".m3u8" in id:
                return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": self.headers}
            return {"parse": 0, "url": id, "header": self.headers}
        if re.match(r'^\d+$', id):
            url = f"{self.site_url}/index.php/vod/play/id/{id}/sid/1/nid/1.html"
            html = self._fetch_html(url)
            m = re.search(r'"url":"([^"]+\.m3u8[^"]*)"', html)
            if m:
                m3u8_url = m.group(1).replace('\\/', '/')
                return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": self.headers}
            return {"parse": 1, "url": url, "header": self.headers}
        return {"parse": 1, "url": id, "header": self.headers}

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤"""
        target = unquote(str((param or {}).get("url", "") or ""))
        if not target:
            return [400, "text/plain", b"invalid url"]
        try:
            res = self.fetch(target, headers={"User-Agent": self.headers["User-Agent"]}, timeout=15)
            if not res:
                return [502, "text/plain", b"fetch failed"]
            content = getattr(res, "content", b"") or b""
            if not content:
                return [502, "text/plain", b"empty content"]
            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            return [500, "text/plain", str(e).encode()]

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
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urlparse(source_url)
        source_path = parsed.path
        source_parts = [p for p in source_path.split("/") if p]
        content_root = "/" + "/".join(source_parts[:2]) + "/" if len(source_parts) >= 2 else ""
        segments = []
        pending = []
        removed = 0

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media = urljoin(source_url, line)
                if content_root and content_root not in urlparse(media).path:
                    removed += 1
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
                return 'URI="' + urljoin(source_url, match.group(1)) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            return urljoin(source_url, line)
        return line

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|ts)(\?|$)', url, re.I))