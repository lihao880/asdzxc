# coding: utf-8
"""
站点: 贵妇X学堂
域名: https://xn--u5z.guifuxxuetang5.click/
类型: 成人影视站 (HTML解析)
特点: 播放地址直接出现在video标签src中，m3u8直链
"""
import re
import json
import urllib.parse
import posixpath
from urllib.parse import urljoin, quote, unquote, urlparse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xn--u5z.guifuxxuetang5.click"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "latest", "type_name": "最新电影"},
            {"type_id": "hot", "type_name": "热播电影"},
        ]
        self.filters = {}
        self.ad_keywords = ["ad", "advertisement", "banner", "promo", "pre-roll", "post-roll", "sponsor", "advert"]

    def getName(self):
        return "贵妇X学堂"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def _parse_video_list(self, html):
        items = []
        pattern = r'<div class="item">.*?<a href="([^"]+)" title="([^"]*)".*?<img[^>]*src="([^"]+)".*?<span class="play-number">([^<]*)</span>.*?<div class="wrap">([^<]*)</div>'
        matches = re.findall(pattern, html, re.DOTALL)
        if not matches:
            pattern2 = r'<div class="item">.*?<a href="([^"]+)" title="([^"]*)".*?<img[^>]*src="([^"]+)".*?<span class="play-number">([^<]*)</span>'
            matches2 = re.findall(pattern2, html, re.DOTALL)
            for m in matches2:
                url, title, pic, plays = m
                date_match = re.search(r'<div class="wrap">([^<]*)</div>', html[html.find(url):html.find(url)+500] if url in html else "")
                date = date_match.group(1) if date_match else ""
                items.append({
                    "vod_id": url.split("/")[-2] if "/video/" in url else url,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": plays.strip() + (" · " + date if date else "")
                })
            return items

        for m in matches:
            url, title, pic, plays, date = m
            vod_id = url.split("/")[-2] if "/video/" in url else url
            if not vod_id or not title:
                continue
            items.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": plays.strip() + (" · " + date if date else "")
            })
        return items

    def homeVideoContent(self):
        html = self.fetch(self.host + "/", headers=self.headers).text
        items = self._parse_video_list(html)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg="1", filter=False, extend=""):
        page = pg or "1"
        if tid == "latest":
            url = f"{self.host}/latest-videos/"
        elif tid == "hot":
            url = f"{self.host}/mostpopular-videos/"
        else:
            url = f"{self.host}/latest-videos/"

        if int(page) > 1:
            url = f"{url}{page}/"

        html = self.fetch(url, headers=self.headers).text
        items = self._parse_video_list(html)

        pagecount = 100
        page_match = re.search(r'<li class="last"><a[^>]*>.*?(\d+)</a></li>', html)
        if page_match:
            pagecount = int(page_match.group(1))

        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20
        }

    def detailContent(self, ids):
        if isinstance(ids, int):
            vid = str(ids)
        elif isinstance(ids, list) and ids:
            vid = str(ids[0])
        elif isinstance(ids, str):
            vid = ids
        else:
            return {"list": []}

        if vid.isdigit():
            url = f"{self.host}/video/{vid}/"
        else:
            url = vid if vid.startswith("http") else f"{self.host}/video/{vid}/"

        try:
            resp = self.fetch(url, headers=self.headers)
            html = resp.text
        except Exception:
            return {"list": []}

        title_match = re.search(r'<h1 class="videoinfo-title">([^<]+)</h1>', html)
        if not title_match:
            title_match = re.search(r'<title>([^<]+)-贵妇X学堂</title>', html)
        title = title_match.group(1).strip() if title_match else ""

        play_url = ""
        play_match = re.search(r'<video[^>]*src="([^"]+)"', html, re.DOTALL | re.IGNORECASE)
        if not play_match:
            play_match = re.search(r'src\s*=\s*"([^"]+\.m3u8[^"]*)"', html, re.IGNORECASE)
        if not play_match:
            play_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
        if play_match:
            play_url = play_match.group(1)

        poster = ""
        poster_match = re.search(r'<video[^>]*poster="([^"]+)"', html, re.DOTALL | re.IGNORECASE)
        if not poster_match:
            poster_match = re.search(r'poster\s*=\s*"([^"]+)"', html, re.IGNORECASE)
        if not poster_match:
            poster_match = re.search(r'poster:\s*"([^"]+)"', html, re.IGNORECASE)
        if poster_match:
            poster = poster_match.group(1)

        date_match = re.search(r'<div class="extrainfo-added"><span[^>]*>加入日期：</span>([^<]+)</div>', html)
        if not date_match:
            date_match = re.search(r'加入日期：([^<]+)', html)
        date = date_match.group(1).strip() if date_match else ""

        plays_match = re.search(r'<div class="extrainfo-playnums"><span[^>]*>浏览：</span>([^<]+)</div>', html)
        if not plays_match:
            plays_match = re.search(r'浏览：([^<]+)', html)
        plays = plays_match.group(1).strip() if plays_match else ""

        # 直接返回代理地址，让壳端触发 localProxy
        if play_url:
            vod_play_url = f"播放${self._m3u8_proxy_url(play_url)}"
            vod_play_from = "直链"
        else:
            vod_play_url = ""
            vod_play_from = ""

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": poster,
            "vod_remarks": f"{plays} · {date}" if plays and date else (plays or date or ""),
            "vod_content": "",
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }
        return {"list": [vod]}
    def searchContent(self, key, quick=False, pg="1"):
        if not key:
            return {"list": [], "page": 1}

        page = pg or "1"
        if int(page) > 1:
            url = f"{self.host}/search/{key}/{page}/"
        else:
            url = f"{self.host}/search/{key}/"

        html = self.fetch(url, headers=self.headers).text
        items = self._parse_video_list(html)

        pagecount = 10
        page_match = re.search(r'<li class="last"><a[^>]*>.*?(\d+)</a></li>', html)
        if page_match:
            pagecount = int(page_match.group(1))

        return {"list": items, "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        # 如果 id 已经是代理地址
        if id.startswith("http://127.0.0.1:9978/proxy"):
            return {
                "parse": 0,
                "url": id,
                "header": {"User-Agent": self.headers.get("User-Agent", ""), "Referer": self.host + "/"}
            }

        # 如果 id 是 m3u8 链接，包装成代理地址
        if id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id),
                "header": {"User-Agent": self.headers.get("User-Agent", ""), "Referer": self.host + "/"}
            }

        # 如果 id 是数字，尝试获取详情
        if id.isdigit():
            detail = self.detailContent([id])
            if detail and detail.get("list"):
                vod = detail["list"][0]
                play_url = vod.get("vod_play_url", "")
                if play_url and "$" in play_url:
                    _, url = play_url.split("$", 1)
                    if url.startswith("http"):
                        # 如果已经是代理地址，直接返回
                        if "127.0.0.1:9978/proxy" in url:
                            return {
                                "parse": 0,
                                "url": url,
                                "header": {"User-Agent": self.headers.get("User-Agent", ""), "Referer": self.host + "/"}
                            }
                        # 否则包装成代理地址
                        return {
                            "parse": 0,
                            "url": self._m3u8_proxy_url(url),
                            "header": {"User-Agent": self.headers.get("User-Agent", ""), "Referer": self.host + "/"}
                        }

        return {"parse": 0, "url": id, "header": {"User-Agent": self.headers.get("User-Agent", ""), "Referer": self.host + "/"}}

    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址 - 标准格式"""
        if not url:
            return ""
        url = url.replace("\\/", "/")
        return "http://127.0.0.1:9978/proxy?do=py&url=" + quote(str(url), safe="")

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写 m3u8 标签中的 URI（补全绝对地址）"""
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)

        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)

        return line

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8 - 过滤广告分片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 处理多码率 Master Playlist
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
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

        # 从 #EXT-X-KEY 提取正片目录
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
                media_url = urljoin(source_url, line)
                media_parsed = urlparse(media_url)

                is_ad = not media_parsed.path.startswith(main_dir)

                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urljoin(source_url, line))
            else:
                segments.append(line)

        # 二次清洗
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

    def localProxy(self, param):
        """
        TVBox/FongMi 本地代理接口
        参数: param 可以是字符串或字典
        返回: [status_code, content_type, data_bytes]
        """
        try:
            # 解析目标 URL
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            elif isinstance(param, str):
                target = param
            else:
                target = str(param or "")

            # 如果 target 包含完整代理地址，提取 url 参数
            if "url=" in target:
                parsed = urlparse(target)
                query = urllib.parse.parse_qs(parsed.query)
                if "url" in query:
                    target = query["url"][0]
                elif "source" in query:
                    target = query["source"][0]

            # URL 解码
            target = unquote(target)

            if not target or not target.startswith("http"):
                return [400, "text/plain", b"invalid url"]

            # 如果目标不是 m3u8，直接返回原始内容
            if not target.endswith(".m3u8") and "m3u8" not in target.lower():
                resp = self.fetch(target, headers=self.headers, timeout=10)
                if resp and resp.status_code == 200:
                    return [200, resp.headers.get("Content-Type", "application/octet-stream"), resp.content]
                return [404, "text/plain", b"not found"]

            # 请求 m3u8
            resp = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=15)
            if not resp or resp.status_code != 200:
                return [502, "text/plain", b"fetch failed"]

            content = resp.text if hasattr(resp, "text") else resp.content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in content:
                return [502, "text/plain", b"invalid m3u8"]

            cleaned = self._clean_m3u8(content, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            return [500, "text/plain", f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")]

    def destroy(self):
        pass