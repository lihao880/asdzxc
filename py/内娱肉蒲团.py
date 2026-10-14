# coding: utf-8
# 站点: 内娱肉蒲团
# 域名: https://xn--u5z.neiyurouputuan4.click/
# 类型: 成人视频站
# 特点: 详情页直接包含m3u8直链，多码率，有广告分片
# 最后验证: 2026-09-08
# m3u8取证: anchor=/20260720/GQmPz7dv/1500kb/hls/, ad_dirs=[/20260830/REyBt5pd/3219kb/hls/]

import re
import json
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xn--u5z.neiyurouputuan4.click"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类列表 - 使用slug作为type_id
        self.classes = [
            {"type_id": "latest", "type_name": "最新电影"},
            {"type_id": "mostpopular", "type_name": "热播电影"},
            {"type_id": "jingxuan", "type_name": "精品推荐"},
            {"type_id": "wangbo", "type_name": "网红主播"},
            {"type_id": "changtui", "type_name": "长腿丝袜"},
            {"type_id": "lingjiarenqi", "type_name": "邻家人妻"},
            {"type_id": "renqishunv", "type_name": "人妻熟女"},
            {"type_id": "chuanmei", "type_name": "传媒系列"},
            {"type_id": "wangbaoxilie", "type_name": "网曝系列"},
            {"type_id": "tantanpiao", "type_name": "探花嫖娼"},
            {"type_id": "tiaojiao", "type_name": "SM调教"},
            {"type_id": "zipai", "type_name": "自拍偷拍"},
            {"type_id": "renbenwuma", "type_name": "日本无码"},
            {"type_id": "qiangluan", "type_name": "强奸乱伦"},
            {"type_id": "luanliao", "type_name": "乱伦系列"},
            {"type_id": "juqing", "type_name": "有剧有情"},
            {"type_id": "zhongwenzimu", "type_name": "中文字幕"},
            {"type_id": "criben", "type_name": "日本Av"},
            {"type_id": "huanshen", "type_name": "换脸女神"},
            {"type_id": "sanli", "type_name": "三级伦理"},
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}
        self.NEED_CLEAN = True

    def getName(self):
        return "内娱肉蒲团"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        url = self.host + "/"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": []}
        html = r.text
        items = self._parse_list(html, url)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        if tid == "latest":
            url = f"{self.host}/latest-videos/{page}/"
        elif tid == "mostpopular":
            url = f"{self.host}/mostpopular-videos/{page}/"
        else:
            url = f"{self.host}/videos/categories/{tid}/{page}/"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        html = r.text
        items = self._parse_list(html, url)
        pagecount = self._get_page_count(html)
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount if pagecount > 0 else 1,
            "limit": 20,
            "total": pagecount * 20 if pagecount > 0 else 0
        }

    def _parse_list(self, html, base_url):
        items = []
        pattern = r'<div class="item">\s*<a href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<strong class="title">(.*?)</strong>'
        for m in re.finditer(pattern, html, re.S):
            link = m.group(1).strip()
            pic = m.group(2).strip()
            title = re.sub(r'<[^>]+>', '', m.group(3)).strip()
            if not link or not title:
                continue
            if not link.startswith("http"):
                link = urllib.parse.urljoin(base_url, link)
            vid = link.rstrip('/').split('/')[-1]
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": ""
            })
        return items

    def _get_page_count(self, html):
        m = re.search(r'<a[^>]*>(\d+)</a>\s*<a[^>]*>下一页</a>', html)
        if m:
            return int(m.group(1))
        m = re.search(r'(?:共|总)(\d+)\s*页', html)
        if m:
            return int(m.group(1))
        matches = re.findall(r'<a[^>]*>(\d+)</a>', html)
        if matches:
            nums = [int(x) for x in matches if x.isdigit()]
            if nums:
                return max(nums)
        return 1

    def _norm_ids(self, ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            try:
                ids = ids.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        return str(ids).strip()

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}

        url = f"{self.host}/video/{vid}/"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return self._skeleton(vid)

        html = r.text

        title_match = re.search(r'<h1>(.*?)</h1>', html)
        title = title_match.group(1).strip() if title_match else ""

        pic_match = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
        pic = pic_match.group(1) if pic_match else ""

        m3u8_url = self._extract_m3u8(html)

        if m3u8_url:
            play_url = self._m3u8_proxy_url(m3u8_url)
            return {"list": [{
                "vod_id": vid,
                "vod_name": title or "未知标题",
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}"
            }]}

        return self._skeleton(vid, title, pic)

    def _extract_m3u8(self, html):
        m = re.search(r'video_url\s*:\s*["\']([^"\']+)["\']', html)
        if m:
            url = m.group(1).strip()
            if url and '.m3u8' in url:
                return url
        m = re.search(r'url\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', html)
        if m:
            url = m.group(1).strip()
            if url:
                return url
        m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html)
        if m:
            embed_url = m.group(1).strip()
            if embed_url:
                r = self.fetch(embed_url, headers=self.headers, timeout=10)
                if r and r.status_code == 200:
                    return self._extract_m3u8(r.text)
        return ""

    def _skeleton(self, vid, title="", pic=""):
        return {"list": [{
            "vod_id": vid,
            "vod_name": title or "未知标题",
            "vod_pic": pic or "",
            "vod_remarks": "解析中",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${vid}"
        }]}

    def searchContent(self, key, quick, pg="1"):
        page = pg or "1"
        encoded_key = urllib.parse.quote(key.encode('utf-8'), safe='')
        url = f"{self.host}/search/?q={encoded_key}&page={page}"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": [], "page": int(page)}
        html = r.text
        items = self._parse_list(html, url)
        return {"list": items, "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        play_url = str(id).strip()
        ua = self.headers.get("User-Agent", "")

        if play_url.startswith("http") and ".m3u8" in play_url:
            if self.NEED_CLEAN:
                return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": {"User-Agent": ua}}
            return {"parse": 0, "url": play_url, "header": {"User-Agent": ua}}

        if play_url.isdigit():
            detail = self.detailContent([play_url])
            if detail.get("list"):
                vod = detail["list"][0]
                play_url_str = vod.get("vod_play_url", "")
                if play_url_str and "$" in play_url_str:
                    parts = play_url_str.split("$", 1)
                    if len(parts) == 2:
                        return {"parse": 0, "url": parts[1], "header": {"User-Agent": ua}}

        return {"parse": 1, "url": play_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}

    def _m3u8_proxy_url(self, url):
        if not url:
            return ""
        return "http://127.0.0.1:9978/proxy?do=py&url=" + urllib.parse.quote(str(url), safe="")

    def localProxy(self, param):
        target = ""
        if isinstance(param, dict):
            target = param.get("url", "") or param.get("source", "")
        else:
            target = str(param or "")
        if target.startswith("url="):
            target = target[4:]
        elif "url=" in target:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(target).query)
            if "url" in qs:
                target = qs["url"][0]
        target = urllib.parse.unquote(str(target or ""))
        if not target or not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]

        try:
            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp or resp.status_code != 200:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]

            if b"#EXTM3U" in content[:256]:
                cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

            return [200, "application/octet-stream", content]
        except Exception as e:
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        ANCHOR = "/20260720/GQmPz7dv/1500kb/hls/"
        AD_DIRS = ["/20260830/REyBt5pd/3219kb/hls/"]

        is_img = self._is_fake_image_stream(text)
        if is_img:
            self.log({"stage": "clean", "fake_image_stream": True})

        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    if ".m3u8" in child.lower():
                        out.append(self._m3u8_proxy_url(child))
                    else:
                        out.append(child)
            return "\n".join(out) + "\n"

        main_dir = ANCHOR
        ad_dirs = AD_DIRS

        segments = []
        pending = []
        removed = 0
        kept = 0

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urllib.parse.urljoin(source_url, line)
                media_path = urllib.parse.urlparse(media_url).path
                is_ad = any(media_path.startswith(ad_dir) for ad_dir in ad_dirs)
                if is_ad:
                    removed += 1
                else:
                    segments.extend(pending)
                    segments.append(media_url)
                    kept += 1
                pending = []
                continue
            if line.startswith("#"):
                segments.append(line)
            else:
                segments.append(urllib.parse.urljoin(source_url, line))

        if removed > 0 and (kept == 0 or removed > kept):
            self.log({"stage": "clean", "fallback": "no_filter", "removed": removed, "kept": kept})
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log({"stage": "clean", "removed": removed, "kept": kept, "anchor": main_dir})

        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def _is_fake_image_stream(self, text):
        IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
        VIDEO_EXT = (".ts", ".m4s", ".mp4", ".aac", ".m4a")
        has_video = False
        has_image = False
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            path = line.split("?")[0].split("#")[0].lower()
            if path.endswith(VIDEO_EXT):
                has_video = True
            elif path.endswith(IMAGE_EXT):
                has_image = True
        return has_image and not has_video

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

    def _dedup_tags(self, segments, source_url):
        NOISE = ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE")
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in NOISE:
                if not out or out[-1] in NOISE:
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in NOISE:
            out.pop()
        return out

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass