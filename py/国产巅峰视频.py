# -*- coding: utf-8 -*-
import re
import json
import urllib.parse
import posixpath
from urllib.parse import quote
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://gcdwave.gcdff12.sbs/kav"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }
        self.classes = [
            {"type_id": "34", "type_name": "强奸轮奸"},
            {"type_id": "95", "type_name": "明星淫梦"},
            {"type_id": "94", "type_name": "美女主播"},
            {"type_id": "57", "type_name": "其他片商"},
            {"type_id": "56", "type_name": "AV解说"},
            {"type_id": "45", "type_name": "VR专区"},
            {"type_id": "42", "type_name": "网曝泄密"},
            {"type_id": "40", "type_name": "猎奇重口"},
            {"type_id": "36", "type_name": "岛国大片"},
            {"type_id": "35", "type_name": "乱伦性爱"},
            {"type_id": "30", "type_name": "口爆颜射"},
            {"type_id": "23", "type_name": "无码专区"},
            {"type_id": "22", "type_name": "制服丝袜"},
            {"type_id": "21", "type_name": "欧美性爱"},
            {"type_id": "20", "type_name": "中文字幕"},
            {"type_id": "25", "type_name": "卡通动漫"},
            {"type_id": "26", "type_name": "少女萝莉"},
            {"type_id": "27", "type_name": "女同性恋"},
            {"type_id": "28", "type_name": "伦理三级"},
            {"type_id": "29", "type_name": "国产自拍"}
        ]
        self.filters = {}

    def getName(self):
        return "国产巅峰视频"

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
            html = self._fetch_html(self.host + "/")
            if not html:
                return {"list": []}
            items = self._parse_video_items(html)
            return {"list": items}
        except Exception as e:
            self.log({"action": "homeVideoContent", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        items = self._parse_video_items(html)
        pagecount = self._extract_pagecount(html)
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        url = f"{self.host}/index.php/vod/detail/id/{vod_id}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}
        vod = self._parse_detail(html, vod_id)
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        page = pg or "1"
        url = f"{self.host}/index.php/vod/search.html?wd={quote(key)}&page={page}"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": int(page)}
        items = self._parse_video_items(html)
        pagecount = self._extract_pagecount(html)
        return {"list": items, "page": int(page), "pagecount": pagecount, "total": pagecount * 20}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 1, "url": ""}
        if id.endswith(".m3u8") or ".m3u8?" in id:
            return {"parse": 0, "url": id, "header": self.headers}
        if id.endswith(".mp4"):
            return {"parse": 0, "url": id, "header": self.headers}
        try:
            resp = self.fetch(id, headers=self.headers, timeout=15)
            if resp and resp.text:
                html = resp.text
                pattern = r'var\s+player_aaaa\s*=\s*(\{[^;]+\});'
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        play_url = data.get("url", "")
                        if play_url and play_url.startswith("http") and ".m3u8" in play_url:
                            return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": self.headers}
                    except:
                        pass
                match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
                if match:
                    play_url = match.group(1)
                    if play_url.startswith("http"):
                        return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": self.headers}
                match = re.search(r'https?://[^"\']+\.m3u8[^"\']*', html)
                if match:
                    play_url = match.group(0)
                    return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": self.headers}
        except Exception as e:
            self.log({"action": "playerContent", "error": str(e)})
        return {"parse": 1, "url": id, "header": self.headers}

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
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

            resp = self.fetch(target, headers=self.headers, timeout=15)
            if not resp:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")

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

    def _fetch_html(self, url, params=None):
        full_url = url
        if params:
            if "?" in url:
                full_url = url + "&" + urllib.parse.urlencode(params)
            else:
                full_url = url + "?" + urllib.parse.urlencode(params)
        try:
            resp = self.fetch(full_url, headers=self.headers, timeout=15)
            if resp and hasattr(resp, "status_code") and resp.status_code == 200:
                return resp.text
            if resp and hasattr(resp, "text"):
                return resp.text
        except:
            pass
        return ""

    def _parse_video_items(self, html, limit=999):
        items = []
        pattern = r'<div[^>]*class="[^"]*item[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-src="([^"]+)"[^>]*>.*?<h4[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        for play_link, pic, detail_link, title in matches:
            vod_id = self._extract_vod_id(detail_link)
            if not vod_id:
                vod_id = self._extract_vod_id(play_link)
            if vod_id and title:
                items.append({
                    "vod_id": vod_id,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
                if len(items) >= limit:
                    break
        return items

    def _extract_vod_id(self, url):
        match = re.search(r'/detail/id/(\d+)\.html', url)
        if match:
            return match.group(1)
        match = re.search(r'/play/id/(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'id[/=](\d+)', url)
        if match:
            return match.group(1)
        return None

    def _parse_detail(self, html, vod_id):
        vod = {
            "vod_id": vod_id,
            "vod_name": "",
            "vod_pic": "",
            "vod_content": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_remarks": "",
            "vod_play_from": "",
            "vod_play_url": ""
        }
        title_match = re.search(r'<h1\s+class="title"[^>]*>([^<]+)</h1>', html)
        if title_match:
            vod["vod_name"] = title_match.group(1).strip()
        pic_match = re.search(r'<img[^>]*class="[^"]*thumb_img[^"]*"[^>]*data-src="([^"]+)"', html)
        if not pic_match:
            pic_match = re.search(r'<img[^>]*class="[^"]*thumb_img[^"]*"[^>]*src="([^"]+)"', html)
        if pic_match:
            vod["vod_pic"] = pic_match.group(1)
        play_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>立即播放</a>', html)
        if play_match:
            play_url = play_match.group(1)
            if play_url.startswith("/kav/"):
                play_url = "https://gcdwave.gcdff12.sbs" + play_url
            elif not play_url.startswith("http"):
                play_url = self.host + play_url
            vod["vod_play_from"] = "默认线路"
            vod["vod_play_url"] = f"播放${play_url}"
        else:
            play_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*title="([^"]*)"', html)
            if play_match:
                play_url = play_match.group(1)
                if play_url.startswith("/kav/"):
                    play_url = "https://gcdwave.gcdff12.sbs" + play_url
                elif not play_url.startswith("http"):
                    play_url = self.host + play_url
                vod["vod_play_from"] = "默认线路"
                vod["vod_play_url"] = f"播放${play_url}"
        content_match = re.search(r'<div\s+class="block-tags"[^>]*>.*?<span\s+class="label">剧情:</span>.*?<div\s+class="tags">(.*?)</div>', html, re.DOTALL)
        if content_match:
            content = re.sub(r'<[^>]+>', '', content_match.group(1)).strip()
            vod["vod_content"] = content
        return vod

    def _extract_pagecount(self, html):
        pages = re.findall(r'<a[^>]*href="[^"]*page/(\d+)\.html"[^>]*>(\d+)</a>', html)
        if pages:
            max_page = 1
            for _, num in pages:
                try:
                    p = int(num)
                    if p > max_page:
                        max_page = p
                except:
                    pass
            return max_page
        return 99

    def _safe_json_parse(self, text):
        try:
            text = text.replace("'", '"')
            text = re.sub(r'(\w+):', r'"\1":', text)
            return json.loads(text)
        except:
            return {}