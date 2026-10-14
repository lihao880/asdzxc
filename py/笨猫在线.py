# coding: utf-8
import re
import json
from urllib.parse import quote, urljoin, unquote, urlparse

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self):
            pass
        def fetch(self, url, headers=None, timeout=15):
            import requests
            resp = requests.get(url, headers=headers or {}, timeout=timeout)
            return resp
        def post(self, url, data=None, json=None, headers=None):
            import requests
            if json:
                resp = requests.post(url, json=json, headers=headers or {})
            else:
                resp = requests.post(url, data=data, headers=headers or {})
            return resp
        def log(self, msg):
            print(msg)
        def getProxyUrl(self):
            return "http://127.0.0.1:9978/proxy?do=py"


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://ccc.bm888.sbs"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host
        }
        self.classes = [
            {"type_id": "m1hl5vzzcl", "type_name": "国产精品"},
            {"type_id": "o02scu0mzl", "type_name": "欧美专区"},
            {"type_id": "94h1iuj6g2", "type_name": "高清无码"},
            {"type_id": "kmgmzxjuhu", "type_name": "中文字幕"},
            {"type_id": "6kjejplcr0", "type_name": "国产探花"},
            {"type_id": "cnamgir43s", "type_name": "国产乱伦"},
            {"type_id": "elfmzylnyx", "type_name": "美女主播"},
            {"type_id": "fbksleo4xk", "type_name": "网曝门事件"},
            {"type_id": "24x4bvr621", "type_name": "天美传媒"},
            {"type_id": "jshi4b4bin", "type_name": "兔子先生"},
            {"type_id": "nnhbwdxdqx", "type_name": "精东影业"},
            {"type_id": "xrjghzkiun", "type_name": "星空无限"},
            {"type_id": "bv3bqvwpni", "type_name": "性世界"},
            {"type_id": "ye8yzlzhut", "type_name": "蜜桃传媒"},
            {"type_id": "lxf89ivd9m", "type_name": "果冻传媒"},
            {"type_id": "1ex3mimwkt", "type_name": "杏吧传媒"},
            {"type_id": "fqmohdxz7e", "type_name": "香港三级"},
            {"type_id": "sutrhjhods", "type_name": "扣扣传媒"},
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}
        self.extend = ""
        self.img_proxy = "https://img.886345.xyz/i.php?url="
        self.img_domains = [
            "bo.bobo998.com:1999",
            "img.imgimg998.com:1999",
            "pic6.sex8sex866.com",
            "pic7.sex8sex866.com",
            "img.886345.xyz"
        ]
        self.play_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://pic6.sex8sex866.com/"
        }

    def getName(self):
        return "笨猫在线"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            html = self._fetch_text(f"{self.host}/")
            items = self._parse_video_list(html)
            return {"list": items}
        except Exception as e:
            self.log(f"homeVideoContent error: {e}")
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = pg or "1"
        if pg == "1":
            url = f"{self.host}/{tid}/"
        else:
            url = f"{self.host}/{tid}/page/{pg}/"
        try:
            html = self._fetch_text(url)
            items = self._parse_video_list(html)
            pagecount = self._parse_page_count(html)
            return {
                "list": items,
                "page": int(pg),
                "pagecount": pagecount,
                "limit": 24,
                "total": 999
            }
        except Exception as e:
            self.log(f"categoryContent error: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        post_id = ids[0]
        detail_url = f"{self.host}/b/{post_id}.html"
        try:
            html = self._fetch_text(detail_url)
            title_match = re.search(r'<h1[^>]*class="post-title[^"]*"[^>]*>(.*?)</h1>', html, re.S)
            title = self._clean_text(title_match.group(1)) if title_match else "视频"
            pic = self._extract_cover_image(html)
            play_url = self._extract_play_url(html)
            content_match = re.search(r'<div[^>]*class="entry-content[^"]*"[^>]*>(.*?)</div>', html, re.S)
            content = self._clean_text(content_match.group(1)) if content_match else ""
            tags_match = re.search(r'<span[^>]*class="writemag-tags-links[^"]*"[^>]*>.*?Tagged\s*(.*?)</span>', html, re.S)
            tags = self._clean_text(tags_match.group(1)) if tags_match else ""
            vod = {
                "vod_id": post_id,
                "vod_name": title,
                "vod_pic": self._fix_image_url(pic),
                "vod_content": f"{content} {tags}".strip(),
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}" if play_url else ""
            }
            return {"list": [vod]}
        except Exception as e:
            self.log(f"detailContent error: {e}")
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        pg = pg or "1"
        if pg == "1":
            url = f"{self.host}/?s={quote(key)}"
        else:
            url = f"{self.host}/page/{pg}/?s={quote(key)}"
        try:
            html = self._fetch_text(url)
            items = self._parse_video_list(html)
            return {"list": items, "page": int(pg)}
        except Exception as e:
            self.log(f"searchContent error: {e}")
            return {"list": [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 1, "url": "", "header": self.headers}
        if not id.startswith("http"):
            id = urljoin(self.host, id)
        if ".m3u8" in id.lower():
            proxy_url = self.getProxyUrl() + "&url=" + quote(str(id), safe="")
            return {"parse": 0, "url": proxy_url, "header": self.play_headers}
        try:
            html = self._fetch_text(id)
            extracted = self._extract_play_url(html)
            if extracted and ".m3u8" in extracted.lower():
                proxy_url = self.getProxyUrl() + "&url=" + quote(str(extracted), safe="")
                return {"parse": 0, "url": proxy_url, "header": self.play_headers}
            if "#EXTM3U" in html:
                proxy_url = self.getProxyUrl() + "&url=" + quote(str(id), safe="")
                return {"parse": 0, "url": proxy_url, "header": self.play_headers}
            return {"parse": 1, "url": id, "header": self.headers}
        except Exception as e:
            self.log(f"playerContent error: {e}")
            return {"parse": 1, "url": id, "header": self.headers}

    def localProxy(self, param):
        target = unquote(str((param or {}).get("url", "") or ""))
        if not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]
        try:
            resp = self.fetch(target, headers=self.play_headers, timeout=20)
            if resp is None:
                return [502, "text/plain", b"fetch None"]
            if resp.status_code != 200:
                return [502, "text/plain", f"status {resp.status_code}".encode()]
            raw = resp.content or b""
            if not raw:
                return [502, "text/plain", b"empty"]
            text = raw.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"not m3u8"]
            cleaned = self._clean_m3u8(text, target)
            if not cleaned:
                cleaned = "#EXTM3U\n"
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log(f"localProxy error: {e}")
            return [500, "text/plain", b"proxy error"]

    def _clean_m3u8(self, text, source_url):
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
                    if ".m3u8" in child.lower():
                        out.append(self.getProxyUrl() + "&url=" + quote(child, safe=""))
                    else:
                        out.append(child)
            return "\n".join(out) + "\n"
        source_path = urlparse(source_url).path
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
                media = urljoin(source_url, line)
                if content_root and content_root not in urlparse(media).path:
                    pending = []
                    continue
                segments.extend(pending)
                segments.append(media)
                pending = []
                continue
            if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
                def repl(m):
                    uri = m.group(1)
                    if not uri.startswith("http"):
                        uri = urljoin(source_url, uri)
                    return f'URI="{uri}"'
                line = re.sub(r'URI="([^"]+)"', repl, line)
            segments.append(line)
        if not segments:
            return "#EXTM3U\n"
        return "\n".join(segments) + "\n"

    def _fix_image_url(self, url):
        """修复图片地址 - 替换域名为可访问的域名"""
        if not url:
            return ""
        # 如果已经是代理格式，直接返回
        if url.startswith(self.img_proxy):
            return url
        # 替换不可访问的域名为可访问的域名（不经过代理）
        if "bo.bobo998.com:1999" in url:
            url = url.replace("bo.bobo998.com:1999", "pic6.sex8sex866.com")
        if "img.imgimg998.com:1999" in url:
            url = url.replace("img.imgimg998.com:1999", "pic6.sex8sex866.com")
        # 如果是 pic6.sex8sex866.com 或 pic7.sex8sex866.com，直接返回
        if "pic6.sex8sex866.com" in url or "pic7.sex8sex866.com" in url:
            return url
        return url

    def _extract_cover_image(self, html):
        match = re.search(r'<img[^>]*class="[^"]*writemag-compact-post-thumbnail-img[^"]*"[^>]*src="([^"]+)"', html)
        if match:
            return match.group(1)
        match = re.search(r'<div[^>]*class="entry-content[^"]*"[^>]*>.*?<img[^>]*src="([^"]+)"', html, re.S)
        if match:
            return match.group(1)
        match = re.search(r'<img[^>]*src="([^"]+)"[^>]*>', html)
        if match:
            return match.group(1)
        return ""

    def _fetch_text(self, url):
        resp = self.fetch(url, headers=self.headers, timeout=15)
        return resp.text

    def _parse_video_list(self, html):
        items = []
        pattern = r'<div[^>]*class="[^"]*writemag-compact-post-wrapper[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h2[^>]*class="[^"]*writemag-compact-post-title[^"]*"[^>]*><a[^>]*href="[^"]*"[^>]*>(.*?)</a></h2>'
        matches = re.findall(pattern, html, re.S)
        for match in matches:
            href = match[0]
            pic = match[1]
            title = self._clean_text(match[2])
            id_match = re.search(r'/b/(\d+)\.html', href)
            vod_id = id_match.group(1) if id_match else href
            items.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": self._fix_image_url(pic),
                "vod_remarks": ""
            })
        seen = set()
        unique = []
        for item in items:
            if item["vod_id"] not in seen:
                seen.add(item["vod_id"])
                unique.append(item)
        return unique

    def _parse_page_count(self, html):
        page_links = re.findall(r'<a[^>]*class="page-numbers"[^>]*href="[^"]*/page/(\d+)/?"[^>]*>([\d,]+)</a>', html)
        if page_links:
            max_page = max(int(p[1].replace(",", "")) for p in page_links if p[1].replace(",", "").isdigit())
            return max_page
        if re.search(r'class="next page-numbers"', html):
            return 2
        return 1

    def _extract_play_url(self, html):
        match = re.search(r'<iframe[^>]*src="([^"]+)"[^>]*>', html)
        if match:
            src = match.group(1)
            if "/tt/t.php" in src:
                url_match = re.search(r'url=([^&]+)', src)
                if url_match:
                    return unquote(url_match.group(1))
            return urljoin(self.host, src)
        match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
        if match:
            return match.group(0)
        match = re.search(r'url\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']', html, re.I)
        if match:
            return match.group(1)
        return ""

    def _clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def destroy(self):
        pass