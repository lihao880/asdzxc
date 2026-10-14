# coding: utf-8
"""
站点: 尤物会所
域名: https://youhuisuo8.life
CMS: MacCMS (苹果CMS)
类型: 成人影视聚合站
广告过滤: v3.0
"""

import sys
sys.path.append('..')
import re
import json
import posixpath
import urllib.parse
from urllib.parse import quote, urljoin, unquote, urlparse

try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def log(self, msg):
            print(msg)
        def fetch(self, url, headers=None, timeout=10, verify=False):
            import requests
            return requests.get(url, headers=headers or {}, timeout=timeout, verify=verify)


class Spider(Spider):
    def __init__(self):
        self.host = "https://youhuisuo8.life"
        self.classes = [
            {"type_id": "1001", "type_name": "视频一区"},
            {"type_id": "1002", "type_name": "视频二区"},
            {"type_id": "1003", "type_name": "视频三区"},
            {"type_id": "1004", "type_name": "视频四区"},
            {"type_id": "1005", "type_name": "视频五区"},
        ]
        self.filters = {}
        for c in self.classes:
            self.filters[c["type_id"]] = []
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.host + "/"
        }
        self._cache_html = None
        self._play_cookies = {}

    def getName(self):
        return "youwu"

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._get_html()
        return {"list": self._parse_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg or 1)
        html = self._get_html()
        items = self._parse_videos(html)
        return {
            "list": items,
            "page": page,
            "pagecount": 999,
            "limit": len(items) if items else 20,
            "total": 999
        }

    def detailContent(self, ids):
        if ids and isinstance(ids, list):
            vid = str(ids[0])
        elif ids:
            vid = str(ids)
        else:
            return {"list": []}

        url = urljoin(self.host, f"/index.php/vod/detail/id/{vid}.html")
        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        vod = {
            "vod_id": vid,
            "vod_name": "",
            "vod_pic": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "",
            "vod_play_url": ""
        }

        title_match = re.search(r'<title>([^<]+)</title>', html)
        if title_match:
            title = title_match.group(1).strip()
            title = re.sub(r'详情介绍.*$', '', title).strip()
            vod["vod_name"] = title

        pic_match = re.search(r'<div[^>]*class="[^"]*detail-cover[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.S)
        if pic_match:
            pic = pic_match.group(1)
            if pic.startswith("/"):
                pic = self.host + pic
            vod["vod_pic"] = pic

        actor_match = re.search(r'演员[：:]\s*<[^>]*>([^<]+)</[^>]*>', html)
        if not actor_match:
            actor_match = re.search(r'演员[：:]\s*([^<]+)', html)
        if actor_match:
            vod["vod_actor"] = actor_match.group(1).strip()

        director_match = re.search(r'导演[：:]\s*<[^>]*>([^<]+)</[^>]*>', html)
        if not director_match:
            director_match = re.search(r'导演[：:]\s*([^<]+)', html)
        if director_match:
            vod["vod_director"] = director_match.group(1).strip()

        desc_match = re.search(r'简介[：:]\s*<[^>]*>([^<]+)</[^>]*>', html)
        if not desc_match:
            desc_match = re.search(r'简介[：:]\s*([^<]+)', html)
        if desc_match:
            vod["vod_content"] = desc_match.group(1).strip()

        vod["vod_play_from"] = "播放"
        vod["vod_play_url"] = f"正片${vid}"

        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": []}
        url = urljoin(self.host, f"/index.php/vod/search/wd/{quote(key)}.html")
        html = self._fetch_html(url)
        items = self._parse_videos(html)
        for item in items:
            if item.get("vod_pic") and item["vod_pic"].startswith("/"):
                item["vod_pic"] = self.host + item["vod_pic"]
        return {"list": items, "page": int(pg or 1)}

    def playerContent(self, flag, id, vipFlags):
        id = str(id) if id is not None else ""

        if id.endswith((".m3u8", ".mp4")):
            return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": self._get_headers()}

        if id.isdigit():
            play_url = urljoin(self.host, f"/index.php/vod/play/id/{id}/sid/1/nid/1.html")
            html, cookies = self._fetch_html_with_cookies(play_url)
            if html:
                if cookies:
                    self._play_cookies = cookies
                player_match = re.search(r'player_aaaa\s*=\s*(\{[^}]*\})', html, re.S)
                if player_match:
                    try:
                        json_str = player_match.group(1)
                        player_data = json.loads(json_str)
                        if player_data.get("url"):
                            m3u8_url = player_data["url"].replace("\\/", "/")
                            return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": self._get_headers()}
                    except:
                        pass
                m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
                if m3u8_match:
                    m3u8_url = m3u8_match.group(1).replace("\\/", "/")
                    return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": self._get_headers()}
                iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', html)
                if iframe_match:
                    return {"parse": 1, "url": iframe_match.group(1), "header": self.headers}
            return {"parse": 1, "url": play_url, "header": self.headers}

        return {"parse": 1, "url": id, "header": self.headers}

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

    def _get_headers(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://youhuisuo8.life/",
        }
        if self._play_cookies:
            cookie_str = "; ".join([f"{k}={v}" for k, v in self._play_cookies.items()])
            headers["Cookie"] = cookie_str
        return headers

    def _get_html(self):
        if self._cache_html is None:
            self._cache_html, _ = self._fetch_html_with_cookies(self.host + "/")
        return self._cache_html

    def _fetch_html(self, url):
        html, _ = self._fetch_html_with_cookies(url)
        return html

    def _fetch_html_with_cookies(self, url):
        try:
            res = self.fetch(url, headers=self.headers)
            if res and hasattr(res, "content"):
                content = res.content.decode("utf-8", errors="ignore")
                cookies = {}
                if hasattr(res, "headers") and res.headers:
                    cookie_str = res.headers.get("Set-Cookie", "")
                    if cookie_str:
                        for item in cookie_str.split(","):
                            parts = item.strip().split(";")
                            if parts:
                                kv = parts[0].split("=", 1)
                                if len(kv) == 2:
                                    cookies[kv[0].strip()] = kv[1].strip()
                return content, cookies
            return "", {}
        except Exception as e:
            self.log({"action": "fetch_fail", "url": url, "error": str(e)})
            return "", {}

    def _parse_videos(self, html):
        items = []
        pattern = r'<a\s+href="([^"]+)"[^>]*class="[^"]*video-item[^"]*"[^>]*>.*?<h3[^>]*>([^<]+)</h3>'
        pic_pattern = r'<img[^>]+data-original="([^"]+)"'
        for match in re.finditer(pattern, html, re.S):
            href = match.group(1)
            title = match.group(2).strip()
            vid = href.split("/id/")[-1].replace(".html", "") if "/id/" in href else ""
            pic_match = re.search(pic_pattern, match.group(0))
            pic = pic_match.group(1) if pic_match else ""
            if pic and pic.startswith("/"):
                pic = self.host + pic
            if vid:
                items.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "",
                    "vod_actor": "",
                })
        return items