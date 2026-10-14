# coding: utf-8
# 一心一意 yxyi1.xyz TVBox 爬虫
# 站点: https://yxyi1.xyz/
# 广告过滤: v3.0

import re
import json
import posixpath
import urllib.parse
from urllib.parse import urljoin

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def fetch(self, url, headers=None, **kwargs):
            import requests
            return requests.get(url, headers=headers, timeout=15)
        def post(self, url, data=None, json=None, headers=None, **kwargs):
            import requests
            return requests.post(url, data=data, json=json, headers=headers, timeout=15)
        def log(self, msg):
            print(msg)


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://yxyi1.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "20", "type_name": "国产精品"},
            {"type_id": "21", "type_name": "日韩精品"},
            {"type_id": "22", "type_name": "欧美精品"},
            {"type_id": "23", "type_name": "动漫精品"},
            {"type_id": "24", "type_name": "中文字幕"},
            {"type_id": "25", "type_name": "强奸乱伦"},
        ]
        self.filters = {}

    def getName(self):
        return "一心一意"

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def getClasses(self):
        return self.classes

    def homeVideoContent(self):
        return self.categoryContent("20", "1", None, None)

    def categoryContent(self, tid, pg, filter, extend):
        pg = pg or "1"
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"
        return self._fetch_list(url, pg)

    def _fetch_list(self, url, pg=1):
        try:
            resp = self.fetch(url, headers=self.headers)
            html = resp.text
        except Exception as e:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}

        items = []
        pattern = r'<div class="vod-list">\s*<a href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<p class="vod-name">([^<]+)</p>'
        matches = re.findall(pattern, html, re.DOTALL)

        for match in matches:
            link, pic, name = match
            if not link or '/detail/' not in link:
                continue
            vod_id_match = re.search(r'/detail/id/(\d+)', link)
            if not vod_id_match:
                continue
            vod_id = vod_id_match.group(1)
            play_page = link.replace('/detail/', '/play/').replace('.html', '/sid/1/nid/1.html')
            play_url = play_page if play_page.startswith("http") else urljoin(self.host, play_page)
            items.append({
                "vod_id": f"{vod_id}|$|{name}|$|{pic}|$||$|{play_url}",
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "",
            })

        pagecount = int(pg)
        page_numbers = re.findall(r'<a[^>]*>(\d+)</a>', html)
        for num in page_numbers:
            try:
                if int(num) > pagecount:
                    pagecount = int(num)
            except:
                pass

        total_match = re.search(r'共\s*(\d+)\s*页', html)
        if total_match:
            pagecount = int(total_match.group(1))

        page_info = re.search(r'第\s*\d+\s*/\s*(\d+)\s*页', html)
        if page_info:
            pagecount = int(page_info.group(1))

        if pagecount <= int(pg):
            next_match = re.search(r'<a[^>]*>下一页</a>', html)
            if next_match:
                pagecount = int(pg) + 1

        return {
            "list": items,
            "page": int(pg),
            "pagecount": max(pagecount, int(pg)),
            "limit": 20,
            "total": max(pagecount, int(pg)) * 20
        }

    def detailContent(self, ids):
        raw = str(ids[0])
        parts = raw.split('|$|')
        vod_id = parts[0]
        name = parts[1] if len(parts) > 1 else ""
        pic = parts[2] if len(parts) > 2 else ""
        play_url = parts[4] if len(parts) > 4 else f"{self.host}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"

        detail_url = f"{self.host}/index.php/vod/detail/id/{vod_id}.html"
        vod_name = name
        vod_pic = pic
        vod_content = ""

        try:
            resp = self.fetch(detail_url, headers=self.headers)
            html_text = resp.text
            if html_text:
                title_match = re.search(r'<div[^>]*detail-pos[^>]*><text>([^<]+)</text>', html_text)
                if title_match:
                    vod_name = title_match.group(1).strip()
                pic_match = re.search(r'<img[^>]*detail-vod-pic[^>]*src=["\']([^"\']+)["\']', html_text)
                if pic_match:
                    vod_pic = urljoin(self.host, pic_match.group(1))
                desc_match = re.search(r'<meta name="description" content="([^"]+)"', html_text)
                if desc_match:
                    vod_content = desc_match.group(1).strip()
        except Exception:
            pass

        vod = {
            "vod_id": raw,
            "vod_name": vod_name or name or f"视频{vod_id}",
            "vod_pic": vod_pic,
            "vod_remarks": "",
            "vod_content": vod_content,
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}"
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        return {"list": [], "page": int(pg), "pagecount": 1}

    def playerContent(self, flag, play_url, vipFlags):
        if play_url.endswith((".m3u8", ".mp4")):
            return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": self.headers}

        try:
            resp = self.fetch(play_url, headers=self.headers)
            html = resp.text
        except Exception:
            return {"parse": 1, "url": play_url, "header": self.headers}

        url_match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html, re.I)
        if url_match:
            m3u8_url = url_match.group(1).replace('\\/', '/')
            if not m3u8_url.startswith("http"):
                m3u8_url = urljoin(play_url, m3u8_url)
            return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": self.headers}

        player_match = re.search(r'player_aaaa\s*=\s*({[^;]+})', html, re.DOTALL)
        if player_match:
            try:
                player_data = json.loads(player_match.group(1))
                m3u8_url = player_data.get("url", "").replace('\\/', '/')
                if m3u8_url:
                    if not m3u8_url.startswith("http"):
                        m3u8_url = urljoin(play_url, m3u8_url)
                    if m3u8_url.endswith((".m3u8", ".mp4")) or ".m3u8?" in m3u8_url:
                        return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": self.headers}
            except:
                pass

        m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
        if m3u8_match:
            return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_match.group(1)), "header": self.headers}

        iframe_match = re.search(r'<iframe[^>]*src=["\']([^"\']+)["\']', html)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            if not iframe_url.startswith("http"):
                iframe_url = urljoin(play_url, iframe_url)
            return self.playerContent(flag, iframe_url, vipFlags)

        return {"parse": 1, "url": play_url, "header": self.headers}

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤 (v3.0)"""
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            res = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=15)
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
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片 (基于 #EXT-X-KEY 目录匹配)"""
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
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

        main_dir = source_dir
        for line in lines:
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                uri_match = re.search(r'URI="([^"]+)"', line)
                if uri_match:
                    key_path = uri_match.group(1)
                    if not key_path.startswith("http"):
                        key_dir = posixpath.dirname(key_path)
                        if key_dir and key_dir != "/":
                            main_dir = key_dir + "/"
                            break

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
                media_url = urllib.parse.urljoin(source_url, line)
                media_parsed = urllib.parse.urlparse(media_url)

                is_ad = not media_parsed.path.startswith(main_dir)

                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urllib.parse.urljoin(source_url, line))
            else:
                segments.append(line)

        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urllib.parse.urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)

        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urllib.parse.urljoin(source_url, line)

        return line

    def destroy(self):
        pass