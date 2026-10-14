# -*- coding: utf-8 -*-
"""
站点名称: 今日热门AV
站点域名: rmav86.jrrmav.buzz
内容类型: 影视
最后验证: 2026-09-10
"""
import re
import json
import urllib.parse
from base.spider import Spider

# 尝试导入广告过滤器
try:
    from ad_filter import M3u8AdFilter
except ImportError:
    M3u8AdFilter = None

class Spider(Spider):
    def __init__(self):
        self.host = "https://rmav86.jrrmav.buzz"
        self.site_url = "/bb"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "29", "type_name": "国产自拍"},
            {"type_id": "30", "type_name": "国产偷拍"},
            {"type_id": "33", "type_name": "短视频"},
            {"type_id": "35", "type_name": "国产主播"},
            {"type_id": "80", "type_name": "国产女王"},
            {"type_id": "81", "type_name": "国产女奴"},
            {"type_id": "83", "type_name": "福利姬"},
            {"type_id": "84", "type_name": "抖阴视频"},
            {"type_id": "85", "type_name": "国模私拍"},
            {"type_id": "88", "type_name": "国产乱伦"},
            {"type_id": "91", "type_name": "网曝系列"},
            {"type_id": "107", "type_name": "台湾辣妹"},
            {"type_id": "108", "type_name": "唯美港姐"},
            {"type_id": "109", "type_name": "国产探花"},
            {"type_id": "110", "type_name": "野外露出"},
            {"type_id": "26", "type_name": "国产精品"},
            {"type_id": "27", "type_name": "国产传媒"},
            {"type_id": "101", "type_name": "有码精品"},
            {"type_id": "116", "type_name": "欺辱凌辱"},
            {"type_id": "117", "type_name": "AV解说"},
            {"type_id": "118", "type_name": "有码VR"},
            {"type_id": "48", "type_name": "美乳巨乳"},
            {"type_id": "59", "type_name": "丝袜美腿"},
            {"type_id": "46", "type_name": "口爆颜射"},
            {"type_id": "50", "type_name": "强奸乱伦"},
            {"type_id": "93", "type_name": "多人运动"},
            {"type_id": "52", "type_name": "制服诱惑"},
            {"type_id": "43", "type_name": "女仆"},
            {"type_id": "31", "type_name": "人妻熟女"},
            {"type_id": "58", "type_name": "cosplay"},
            {"type_id": "34", "type_name": "潮吹喷射"},
            {"type_id": "47", "type_name": "萝莉少女"},
            {"type_id": "44", "type_name": "素人"},
            {"type_id": "53", "type_name": "女同性恋"},
            {"type_id": "32", "type_name": "SM重口味"},
            {"type_id": "45", "type_name": "熟女"},
            {"type_id": "55", "type_name": "教师"},
            {"type_id": "62", "type_name": "无码VR"},
            {"type_id": "71", "type_name": "无码流出"},
            {"type_id": "72", "type_name": "乱伦无码"},
            {"type_id": "73", "type_name": "巨乳无码"},
            {"type_id": "74", "type_name": "强姦无码"},
            {"type_id": "75", "type_name": "人妻无码"},
            {"type_id": "76", "type_name": "制服无码"},
            {"type_id": "86", "type_name": "女优明星"},
            {"type_id": "97", "type_name": "HEYZO"},
            {"type_id": "98", "type_name": "HEY诱惑"},
            {"type_id": "102", "type_name": "无码精品"},
            {"type_id": "111", "type_name": "无码破解"},
            {"type_id": "51", "type_name": "日本中字"},
            {"type_id": "99", "type_name": "欧美中字"},
            {"type_id": "100", "type_name": "韩国中字"},
            {"type_id": "38", "type_name": "欧美主播"},
            {"type_id": "63", "type_name": "人妖"},
            {"type_id": "64", "type_name": "男同性恋"},
            {"type_id": "65", "type_name": "女同性恋"},
            {"type_id": "104", "type_name": "欧美精品"},
            {"type_id": "103", "type_name": "动漫精品"},
            {"type_id": "39", "type_name": "综合三级"},
            {"type_id": "40", "type_name": "香港三级"},
            {"type_id": "67", "type_name": "韩国伦理"},
            {"type_id": "77", "type_name": "国产伦理"},
            {"type_id": "78", "type_name": "欧美伦理"},
            {"type_id": "79", "type_name": "日本伦理"},
            {"type_id": "37", "type_name": "韩国主播"},
            {"type_id": "68", "type_name": "韩国综艺"},
            {"type_id": "82", "type_name": "韩国精品"},
            {"type_id": "42", "type_name": "恐怖色情"},
            {"type_id": "54", "type_name": "人兽性交"},
            {"type_id": "60", "type_name": "拳交"},
            {"type_id": "61", "type_name": "AI换脸"}
        ]
        self.filters = {}
        self.ad_filter = M3u8AdFilter() if M3u8AdFilter else None
        self._ad_config = {
            "anchor_dir": "/20260908/ihgGSZFJ/1500kb/hls/",
            "ad_dirs": ["/20260731/UTxI1Mxv/9567kb/hls/"]
        }

    def init(self, extend=""):
        self.host = "https://rmav86.jrrmav.buzz"
        self.headers["Referer"] = self.host + "/"

    def getName(self):
        return "今日热门AV"

    def getDependence(self):
        return []

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """提取首页「国产」分类下的视频作为推荐"""
        url = f"{self.host}{self.site_url}/"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        items = []
        # 定位「国产」分类区块 - 它的标题是 <h3>国产</h3>
        # 然后提取该区块内的 .vod 条目
        pattern = r'<h3>国产</h3>\s*<a[^>]*href="[^"]*"[^>]*>更多</a>\s*</div>\s*<div class="vods">(.*?)</div>\s*<div class="box">'
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            return {"list": []}

        vods_html = match.group(1)
        # 提取 .vod 条目
        vod_pattern = r'<div class="vod">\s*<div class="vod-img">\s*<a[^>]*href="([^"]+)"[^>]*>\s*<img[^>]*data-original="([^"]+)"[^>]*>\s*</a>\s*</div>\s*<div class="vod-txt">\s*<a[^>]*href="[^"]+"[^>]*>([^<]+)</a>'
        matches = re.findall(vod_pattern, vods_html, re.DOTALL)
        for link, pic, name in matches:
            vod_id = re.search(r'/detail/id/(\d+)\.html', link)
            if vod_id:
                items.append({
                    "vod_id": vod_id.group(1),
                    "vod_name": name.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
                if len(items) >= 20:
                    break

        return {"list": items}
    def _fetch_html(self, url):
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return None
        return r.text

    def _parse_list(self, html):
        items = []
        pattern = r'<div class="vod">\s*<div class="vod-img">\s*<a[^>]*href="([^"]+)"[^>]*>\s*<img[^>]*data-original="([^"]+)"[^>]*>\s*</a>\s*</div>\s*<div class="vod-txt">\s*<a[^>]*href="[^"]+"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            link, pic, name = match
            vod_id = re.search(r'/detail/id/(\d+)\.html', link)
            if vod_id:
                items.append({
                    "vod_id": vod_id.group(1),
                    "vod_name": name.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return items

    def categoryContent(self, tid, pg, filter=False, extend=""):
        if not pg:
            pg = "1"
        url = f"{self.host}{self.site_url}/index.php/vod/type/id/{tid}/page/{pg}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}

        items = self._parse_list(html)
        pagecount = 1
        page_match = re.search(r'共(\d+)页', html)
        if page_match:
            pagecount = int(page_match.group(1))
        elif re.search(r'<a[^>]*href="[^"]*page/(\d+)\.html"', html):
            pages = re.findall(r'<a[^>]*href="[^"]*page/(\d+)\.html"', html)
            if pages:
                pagecount = max([int(p) for p in pages if p.isdigit()])

        return {
            "list": items,
            "page": int(pg),
            "pagecount": pagecount,
            "limit": 20,
            "total": len(items)
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0]) if isinstance(ids, list) else str(ids)
        url = f"{self.host}{self.site_url}/index.php/vod/detail/id/{vod_id}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        title_match = re.search(r'<h3 class="title">([^<]+)</h3>', html)
        title = title_match.group(1).strip() if title_match else "未知标题"

        pic_match = re.search(r'<img[^>]*data-original="([^"]+)"[^>]*>', html)
        pic = pic_match.group(1) if pic_match else ""

        play_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>立即播放</a>', html)
        play_url = ""
        if play_match:
            play_url = self.host + play_match.group(1)

        backup_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>备用线路</a>', html)
        backup_url = ""
        if backup_match:
            backup_url = self.host + backup_match.group(1)

        play_from = ""
        play_urls = ""
        if play_url:
            play_from = "播放"
            play_urls = f"播放${play_url}"
        if backup_url:
            if play_from:
                play_from += "$$$备用"
                play_urls += f"$$$播放${backup_url}"
            else:
                play_from = "备用"
                play_urls = f"播放${backup_url}"

        return {
            "list": [{
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": play_from,
                "vod_play_url": play_urls
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        encoded_key = urllib.parse.quote(key.encode('utf-8'))
        url = f"{self.host}{self.site_url}/index.php/vod/search/wd/{encoded_key}.html"
        if pg and pg != "1":
            url = f"{self.host}{self.site_url}/index.php/vod/search/wd/{encoded_key}/page/{pg}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": 1}
        items = self._parse_list(html)
        return {"list": items, "page": int(pg) if pg else 1}

    def _m3u8_proxy_url(self, url):
        if not url:
            return ""
        return "http://127.0.0.1:9978/proxy?do=py&url=" + urllib.parse.quote(str(url), safe="")

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id) if id else ""

        if play_url and "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]

        if play_url and not play_url.startswith("http"):
            if not play_url.startswith("//"):
                play_url = "https://" + play_url

        if not play_url:
            return {"parse": 0, "url": "", "header": {}}

        if "/vod/play/" in play_url:
            r = self.fetch(play_url, headers=self.headers, timeout=15)
            if r and r.status_code == 200:
                html = r.text
                match = re.search(r'player_aaaa\s*=\s*({[^;]+});', html, re.DOTALL)
                if match:
                    try:
                        js_obj = match.group(1)
                        js_obj = re.sub(r'(\w+):', r'"\1":', js_obj)
                        js_obj = js_obj.replace("'", '"')
                        data = json.loads(js_obj)
                        if data.get('url'):
                            m3u8_url = data['url'].replace('\\/', '/')
                            if m3u8_url.startswith('http'):
                                if self._ad_config.get("ad_dirs"):
                                    proxy_url = self._m3u8_proxy_url(m3u8_url)
                                    return {"parse": 0, "url": proxy_url, "header": {"User-Agent": self.headers["User-Agent"]}}
                                return {"parse": 0, "url": m3u8_url, "header": self.headers}
                    except:
                        pass

                match2 = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
                if match2:
                    m3u8_url = match2.group(1)
                    if self._ad_config.get("ad_dirs"):
                        proxy_url = self._m3u8_proxy_url(m3u8_url)
                        return {"parse": 0, "url": proxy_url, "header": {"User-Agent": self.headers["User-Agent"]}}
                    return {"parse": 0, "url": m3u8_url, "header": self.headers}

                match3 = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
                if match3:
                    m3u8_url = match3.group(1).replace('\\/', '/')
                    if m3u8_url.startswith('http'):
                        if self._ad_config.get("ad_dirs"):
                            proxy_url = self._m3u8_proxy_url(m3u8_url)
                            return {"parse": 0, "url": proxy_url, "header": {"User-Agent": self.headers["User-Agent"]}}
                        return {"parse": 0, "url": m3u8_url, "header": self.headers}

        if '.m3u8' in play_url:
            if self._ad_config.get("ad_dirs"):
                proxy_url = self._m3u8_proxy_url(play_url)
                return {"parse": 0, "url": proxy_url, "header": {"User-Agent": self.headers["User-Agent"]}}
            return {"parse": 0, "url": play_url, "header": self.headers}

        return {"parse": 1, "url": play_url, "header": self.headers}

    def localProxy(self, param):
        """m3u8 本地代理 - 使用九州视频同款 ad_filter"""
        try:
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
            if not target or not target.startswith("http"):
                return [400, "text/plain", b"invalid url"]

            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp or resp.status_code != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]

            if b"#EXTM3U" in content[:256]:
                text = content.decode("utf-8", errors="ignore")
                if self.ad_filter:
                    cleaned = self.ad_filter.clean(text, target)
                else:
                    cleaned = self._clean_m3u8_fallback(text, target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

            return [200, "application/octet-stream", content]

        except Exception as e:
            return [500, "text/plain", f"proxy error: {str(e)}".encode("utf-8", errors="ignore")]

    def _clean_m3u8_fallback(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        is_img = self._is_fake_image_stream(lines)
        if is_img:
            pass

        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            return self._clean_m3u8_multi(lines, source_url)

        main_dir = self._resolve_main_dir(lines, source_url, is_image_stream=is_img)
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        if removed > 0 and (kept == 0 or removed > kept):
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def _is_fake_image_stream(self, lines):
        IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
        VIDEO_EXT = (".ts", ".m4s", ".mp4", ".aac", ".m4a")
        has_video = False
        has_image = False
        for line in lines:
            if not line or line.startswith("#"):
                continue
            path = line.split("?")[0].split("#")[0].lower()
            if path.endswith(VIDEO_EXT):
                has_video = True
            elif path.endswith(IMAGE_EXT):
                has_image = True
        return has_image and not has_video

    def _resolve_main_dir(self, lines, source_url, is_image_stream=False):
        import posixpath
        base_dir = posixpath.dirname(urllib.parse.urlparse(source_url).path)
        if not base_dir.endswith("/"):
            base_dir += "/"

        if is_image_stream:
            counter = {}
            for line in lines:
                if not line or line.startswith("#"):
                    continue
                p = urllib.parse.urlparse(urllib.parse.urljoin(source_url, line)).path
                d = posixpath.dirname(p)
                if d and d != "/":
                    counter[d + "/"] = counter.get(d + "/", 0) + 1
            if counter:
                return max(counter.items(), key=lambda kv: kv[1])[0]
            return base_dir

        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            key_path = urllib.parse.urlparse(
                key_uri if key_uri.startswith("http") else urllib.parse.urljoin(source_url, key_uri)
            ).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return base_dir

    def _filter_segments(self, lines, source_url, main_dir):
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
                if media_path.startswith(main_dir):
                    segments.extend(pending)
                    segments.append(media_url)
                    kept += 1
                else:
                    removed += 1
                pending = []
                continue
            if line.startswith("#"):
                segments.append(line)
            else:
                segments.append(urllib.parse.urljoin(source_url, line))
        return segments, removed, kept

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

    def _clean_m3u8_multi(self, lines, source_url):
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

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass