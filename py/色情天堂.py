# coding: utf-8
"""
站点信息
主域名: https://azl.sqtt4.beauty
备用域名: 无
发布页: https://eoi.szwaa.com/3/
内容类型: 成人影视
特殊说明: 标准HTML站，m3u8含广告分片需过滤
最后验证时间: 2026-08-30
来源: 用户提供
"""
import json
import re
import base64
from urllib.parse import urljoin, urlparse, quote, unquote
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://azl.sqtt4.beauty"
        self.classes = [
            {"type_id": "20", "type_name": "自拍视频"},
            {"type_id": "21", "type_name": "强奸乱伦"},
            {"type_id": "22", "type_name": "无码视频"},
            {"type_id": "23", "type_name": "有码视频"},
            {"type_id": "24", "type_name": "人妻熟女"},
            {"type_id": "25", "type_name": "制服诱惑"},
            {"type_id": "26", "type_name": "口交颜射"},
            {"type_id": "27", "type_name": "SM重味"},
            {"type_id": "28", "type_name": "日韩视频"},
            {"type_id": "29", "type_name": "欧美视频"},
            {"type_id": "30", "type_name": "动漫视频"},
            {"type_id": "31", "type_name": "伦理影片"}
        ]
        self.filters = {
            "20": [],
            "21": [],
            "22": [],
            "23": [],
            "24": [],
            "25": [],
            "26": [],
            "27": [],
            "28": [],
            "29": [],
            "30": [],
            "31": []
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        self._cached_host = self.host

    def getName(self):
        return "色情天堂"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        url = self.host + "/cn/home/web/"
        html = self.fetch(url, headers=self.headers).text
        items = self._parse_video_list(html)
        return {"list": items[:12] if items else []}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/vodtype/{tid}-{page}.html"
        html = self.fetch(url, headers=self.headers).text
        items = self._parse_video_list(html)
        # 提取总页数
        total_pages = self._extract_total_pages(html)
        return {
            "list": items,
            "page": int(page),
            "pagecount": total_pages or 99,
            "limit": 20,
            "total": total_pages * 20 if total_pages else 999
        }

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid:
            return {"list": []}
        url = f"{self.host}/{vid}.html"
        html = self.fetch(url, headers=self.headers).text
        # 提取标题
        title_match = re.search(r'<h1>([^<]+)</h1>', html)
        title = title_match.group(1).strip() if title_match else "视频"
        # 提取播放地址 rawUrl
        m3u8_match = re.search(r"rawUrl\s*=\s*'([^']+)'", html)
        play_url = ""
        if m3u8_match:
            play_url = m3u8_match.group(1).strip()
        # 提取封面图（从相关推荐或页面中）
        pic_match = re.search(r'<img\s+src="([^"]+)"', html)
        pic = pic_match.group(1) if pic_match else ""
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": title,
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}" if play_url else ""
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/s/index.html?wd={quote(str(key))}"
        html = self.fetch(url, headers=self.headers).text
        items = self._parse_video_list(html)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        play_url = str(id).strip()
        if play_url.startswith(("http://", "https://")):
            if ".m3u8" in play_url:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(play_url),
                    "header": {"User-Agent": self.headers.get("User-Agent", "")}
                }
            return {"parse": 0, "url": play_url, "header": {"User-Agent": self.headers.get("User-Agent", "")}}
        # 降级嗅探
        return {
            "parse": 1,
            "url": play_url,
            "header": {
                "User-Agent": self.headers.get("User-Agent", ""),
                "Referer": self.host + "/"
            }
        }

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass

    def _parse_video_list(self, html):
        items = []
        # 匹配 <li class="item"><a href="/123.html" title="标题">...<img src="封面">...<span class="hint">观看数</span>
        pattern = r'<li\s+class="item">\s*<a\s+href="([^"]+)"\s+title="([^"]*)"[^>]*>.*?<img\s+src="([^"]+)"[^>]*>.*?<span\s+class="hint">([^<]*)</span>'
        matches = re.findall(pattern, html, re.DOTALL)
        for href, title, pic, hint in matches:
            if not href or not title:
                continue
            vod_id = href.lstrip('/').split('.')[0]
            if not vod_id or not vod_id.isdigit():
                continue
            items.append({
                "vod_id": str(vod_id),
                "vod_name": title.strip(),
                "vod_pic": urljoin(self.host, pic) if pic and not pic.startswith("http") else pic,
                "vod_remarks": hint.strip() if hint else ""
            })
        return items

    def _extract_total_pages(self, html):
        # 从分页脚本中提取总页数
        match = re.search(r'for\s*\(\s*var\s+i\s*=\s*0\s*;\s*i\s*<\s*(\d+)\s*;\s*i\+\+\)', html)
        if match:
            return int(match.group(1))
        # 备选：从尾页链接提取
        match = re.search(r'<a[^>]*href="[^"]*-(\d+)\.html"[^>]*>尾页</a>', html)
        if match:
            return int(match.group(1))
        return None

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                qs = self._parse_qs(target)
                if "url" in qs:
                    target = qs["url"][0]
            target = unquote(str(target or ""))
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp:
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

    def _parse_qs(self, query):
        result = {}
        for part in query.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                result.setdefault(k, []).append(v)
        return result

    def _is_fake_image_stream(self, text, source_url):
        low_url = (source_url or "").lower()
        for sig in ("doyinapi", "svip", "imgcdn", "photo"):
            if sig in low_url:
                return True
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower().split("?")[0]
            if low.endswith((".png", ".jpg", ".jpeg", ".webp")):
                return True
        return False

    def _resolve_main_dir(self, lines, source_url):
        import posixpath
        parsed = urlparse(source_url)
        main_dir = posixpath.dirname(parsed.path)
        if not main_dir.endswith("/"):
            main_dir += "/"
        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            key_path = urlparse(
                key_uri if key_uri.startswith("http") else urljoin(source_url, key_uri)
            ).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return main_dir

    def _rewrite_m3u8_tag(self, line, source_url):
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

    def _clean_m3u8_multi(self, lines, source_url):
        out = []
        for line in lines:
            if line.startswith("#"):
                out.append(line)
                continue
            child = urljoin(source_url, line)
            if ".m3u8" in child.lower():
                out.append(self._m3u8_proxy_url(child))
            else:
                out.append(child)
        return "\n".join(out) + "\n"

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 第1层：图片流伪装
        if self._is_fake_image_stream(text, source_url):
            restored = text
            for ext in (".png", ".jpeg", ".jpg", ".webp"):
                restored = restored.replace(ext, ".ts")
            return restored

        # 第2层：多码率主表
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            return self._clean_m3u8_multi(lines, source_url)

        # 第3层：正片目录锚点
        main_dir = self._resolve_main_dir(lines, source_url)

        # 第4层：分片过滤
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
                media_url = urljoin(source_url, line)
                media_path = urlparse(media_url).path
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
                segments.append(urljoin(source_url, line))

        # 第5层：全滤兜底
        if kept == 0 and removed > 0:
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")

        # 第5层：冗余标签清理
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

        return "\n".join(out) + "\n"