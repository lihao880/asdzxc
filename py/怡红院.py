# coding: utf-8
# 站点: 怡红院 (guozichan.cyou)
# CMS: MacCMS
# 类型: 成人影视
# 特性: m3u8 本地代理 + 广告分片过滤

import re
import json
import base64
from urllib.parse import urljoin, quote, unquote, urlparse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://guozichan.cyou"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        # 只保留有视频数据的分类（经测试验证）
        self.classes = [
            {"type_id": "1", "type_name": "国产乱伦"},
            {"type_id": "2", "type_name": "制服诱惑"},
            {"type_id": "3", "type_name": "中文字幕"},
            {"type_id": "4", "type_name": "蜜桃传媒"},
            {"type_id": "5", "type_name": "精东影业"},
            {"type_id": "13", "type_name": "AV解说"},
            {"type_id": "14", "type_name": "91视频"},
            {"type_id": "16", "type_name": "绿帽淫妻"}
        ]
        # 无筛选功能
        self.filters = {}

    def getName(self):
        return "怡红院"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            html = self._get("/")
            items = self._parse_video_list(html)
            return {"list": items[:30]}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg or "1")
        real_tid = str(tid or "")
        if not real_tid or real_tid == "0":
            if isinstance(extend, dict):
                real_tid = str(extend.get("type_id") or extend.get("tid") or "")
        if not real_tid or real_tid == "0":
            real_tid = "2"
        
        if pg == "1":
            path = f"/index.php/vod/show/id/{real_tid}.html"
        else:
            path = f"/index.php/vod/show/id/{real_tid}.html?page={pg}"
        
        html = self._get(path)
        items = self._parse_video_list(html)
        pagecount = self._parse_page_count(html)
        return {
            "list": items,
            "page": int(pg),
            "pagecount": pagecount or 50,
            "limit": 20,
            "total": 0
        }

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        detail_url = f"/index.php/vod/detail/id/{vid}.html"
        html = self._get(detail_url)
        
        title_match = re.search(r'<title>(.*?)</title>', html)
        if title_match:
            raw = title_match.group(1).strip()
            if "详情介绍" in raw:
                title = raw.split("详情介绍")[0].strip()
            else:
                parts = raw.split("-")
                title = parts[0].strip() if parts else raw
            if not title:
                title = raw
        else:
            title = "视频"
        
        pic = self._regex(html, r'<a[^>]*class="video-pic[^"]*"[^>]*data-original="([^"]+)"')
        
        play_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic or "",
            "vod_remarks": "HD",
            "vod_content": title,
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}"
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        try:
            data = {"wd": key}
            headers = self.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            res = self.post(f"{self.host}/index.php/vod/search.html", data=data, headers=headers)
            if res.status_code != 200:
                return {"list": []}
            html = res.text
            items = self._parse_video_list(html)
            return {"list": items, "page": int(pg)}
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        try:
            play_id = str(id or "").strip()
            
            if play_id.startswith("http") and re.search(r"\.(m3u8|mp4)(\?|$)", play_id, re.I):
                if re.search(r"\.m3u8(?:\?|$)", play_id, re.I):
                    return {"parse": 0, "url": self._m3u8_proxy_url(play_id), "header": {}}
                return {"parse": 0, "url": play_id, "header": {"User-Agent": self.headers["User-Agent"]}}
            
            m = re.search(r'/id/(\d+)', play_id)
            if m:
                vid = m.group(1)
                nid = self._regex(play_id, r'/nid/(\d+)') or '1'
                sid = self._regex(play_id, r'/sid/(\d+)') or '1'
                player_path = f"/index.php/vod/player/id/{vid}/nid/{nid}/sid/{sid}.html"
            else:
                player_path = play_id.replace("/vod/play/", "/vod/player/")
                if not player_path.startswith("/"):
                    player_path = "/" + player_path.lstrip("/")
            
            html = self._get(player_path)
            play_url = self._extract_player_url(html)
            
            if not play_url:
                iframe_src = self._regex(html, r'<iframe[^>]*src="([^"]+)"')
                if iframe_src:
                    if not iframe_src.startswith("http"):
                        iframe_src = self.host + iframe_src
                    iframe_html = self._get(iframe_src)
                    play_url = self._extract_player_url(iframe_html)
            
            if not play_url:
                return {"parse": 1, "url": self.host + player_path, "header": self.headers}
            
            if re.search(r"\.m3u8(?:\?|$)", play_url, re.I):
                return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": {}}
            return {"parse": 0, "url": play_url, "header": {"User-Agent": self.headers["User-Agent"]}}
        except Exception:
            return {"parse": 1, "url": id, "header": self.headers}

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "&url=" + quote(str(url or ""), safe="")

    def localProxy(self, param):
        target = unquote(str((param or {}).get("url", "") or ""))
        if not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]
        try:
            res = self.fetch(
                target,
                headers={"User-Agent": self.headers["User-Agent"]},
                timeout=15,
                verify=False
            )
            if not res or getattr(res, "status_code", 0) != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            raw = getattr(res, "content", b"") or b""
            text = raw.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log("m3u8广告过滤失败: " + str(e))
            return [500, "text/plain", b"m3u8 proxy error"]

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
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        source_path = urlparse(source_url).path
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
        if removed:
            self.log("m3u8已过滤广告分片: %d" % removed)
        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                return 'URI="' + urljoin(source_url, match.group(1)) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            return urljoin(source_url, line)
        return line

    def _extract_player_url(self, html):
        if not html:
            return ""
        
        js = self._regex(html, r'var\s+player_[a-zA-Z0-9_]+\s*=\s*(\{.*?\})(?:;|</script>)')
        if not js:
            js = self._regex(html, r'var\s+player_[a-zA-Z0-9_]+\s*=\s*(\{.*?\})')
        
        if js:
            try:
                data = json.loads(js)
                url = data.get("url", "")
                encrypt = int(data.get("encrypt", 0))
                if encrypt == 1:
                    url = unquote(url)
                elif encrypt == 2:
                    url = unquote(base64.b64decode(url).decode("utf-8", errors="ignore"))
                return str(url).replace("\\/", "/")
            except Exception:
                url = self._regex(js, r'"url"\s*:\s*"([^"]+)"')
                if url:
                    return str(url).replace("\\/", "/")
        
        url = self._regex(html, r'(https?:\\?/\\?/[^"\']+?\.(?:m3u8|mp4)[^"\']*)')
        if url:
            return str(url).replace("\\/", "/")
        
        return ""

    def _parse_video_list(self, html):
        items = []
        if not html:
            return items
        block_pattern = r'<li[^>]*class="col-md-2 col-sm-3 col-xs-4[^"]*"[^>]*>(.*?)</li>'
        blocks = re.findall(block_pattern, html, re.S)
        for block in blocks:
            try:
                link_match = re.search(r'<a[^>]*href="([^"]+)"', block)
                if not link_match:
                    continue
                link = link_match.group(1)
                vid_match = re.search(r'/vod/detail/id/(\d+)\.html', link)
                if not vid_match:
                    continue
                vid = vid_match.group(1)
                pic_match = re.search(r'data-original="([^"]+)"', block)
                pic = pic_match.group(1) if pic_match else ""
                title_match = re.search(r'<h5[^>]*class="text-overflow"[^>]*><a[^>]*>([^<]+)</a></h5>', block, re.S)
                title = title_match.group(1).strip() if title_match else "视频"
                time_match = re.search(r'<div[^>]*class="subtitle text-time text-overflow"[^>]*>([^<]+)</div>', block)
                time_str = time_match.group(1).strip() if time_match else ""
                items.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": time_str
                })
            except:
                continue
        return items

    def _parse_page_count(self, html):
        match = re.search(r'共(\d+)页', html)
        if match:
            return int(match.group(1))
        match = re.search(r'class="page"[^>]*>.*?(\d+)</a>\s*</li>\s*<li[^>]*class="active"', html, re.S)
        if match:
            return int(match.group(1))
        return None

    def _get(self, path):
        try:
            import requests
            url = path if path.startswith("http") else self.host + path
            r = requests.get(url, headers=self.headers, timeout=15, verify=False)
            r.encoding = "utf-8"
            return r.text or ""
        except Exception:
            return ""

    def _regex(self, text, pattern):
        if not text:
            return ""
        m = re.search(pattern, text, re.S)
        return m.group(1).strip() if m else ""

    def destroy(self):
        pass