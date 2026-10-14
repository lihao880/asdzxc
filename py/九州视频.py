# coding: utf-8
import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider

# 尝试导入广告过滤器
try:
    from ad_filter import M3u8AdFilter
except ImportError:
    M3u8AdFilter = None

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.jzsp4.beauty"
        self.base_url = f"{self.host}/cn/home/web"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        # 从播放页导航栏提取的分类
        self.classes = [
            {"type_id": "20", "type_name": "日韩"},
            {"type_id": "21", "type_name": "偷拍"},
            {"type_id": "22", "type_name": "无码"},
            {"type_id": "23", "type_name": "自拍"},
            {"type_id": "24", "type_name": "巨乳"},
            {"type_id": "25", "type_name": "华人"},
            {"type_id": "26", "type_name": "嫩模"},
            {"type_id": "27", "type_name": "剧情"},
            {"type_id": "28", "type_name": "动漫"},
            {"type_id": "29", "type_name": "熟女"},
            {"type_id": "30", "type_name": "丝袜"},
            {"type_id": "32", "type_name": "欧美"},
            {"type_id": "33", "type_name": "有码"},
            {"type_id": "34", "type_name": "制服"},
            {"type_id": "35", "type_name": "口交"},
            {"type_id": "31", "type_name": "三级"},
        ]
        self.filters = {}
        self.ad_filter = M3u8AdFilter() if M3u8AdFilter else None

    def getName(self):
        return "九州视频"

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self.categoryContent("20", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.base_url}/index.php/vod/type/id/{tid}/page/{page}.html"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

        html = r.text
        items = []
        pattern = r'<a[^>]+href="([^"]+vod/play/id/(\d+)[^"]+)"[^>]*class="[^"]*videoListStyle[^"]*"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html, re.S)
        for link, vid, title in matches:
            # 清理标题：去标签、去换行、去多余空白
            title = re.sub(r'<[^>]+>', '', title)
            title = re.sub(r'\s+', ' ', title).strip()
            # 去掉开头的日期（如 09-08）
            title = re.sub(r'^\d{2}-\d{2}\s*', '', title)
            # 去掉末尾的 "数字 人气" 或 "人气" 及前后空白
            title = re.sub(r'\s*\d+\s*人气\s*$', '', title)
            title = re.sub(r'\s*人气\s*$', '', title)
            title = title.strip()
            if not vid or not title:
                continue
            img_pattern = r'<img[^>]+src="([^"]+)"[^>]*>'
            card_start = html.find(f'href="{link}"')
            if card_start == -1:
                continue
            card_end = html.find('</a>', card_start)
            card_html = html[card_start:card_end]
            img_match = re.search(img_pattern, card_html)
            pic = img_match.group(1) if img_match else ""
            if pic and not pic.startswith("http"):
                pic = urllib.parse.urljoin(self.host, pic)
            # 将标题、图片打包进 vod_id，供 detailContent 解析
            packed_id = f"{vid}|$|{title}|$|{pic}"
            items.append({
                "vod_id": packed_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": ""
            })

        pagecount = 1
        page_pattern = r'<a[^>]+href="[^"]*page/(\d+)[^"]*"[^>]*>(\d+)</a>'
        page_matches = re.findall(page_pattern, html)
        if page_matches:
            try:
                pagecount = max(int(p) for _, p in page_matches)
            except:
                pass

        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": len(items)
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        raw_id = str(ids[0]) if isinstance(ids, list) else str(ids)
        # 尝试解析打包的 ID: vid|$|title|$|pic
        parts = raw_id.split("|$|")
        if len(parts) >= 3:
            vid = parts[0]
            title = re.sub(r'\s+', ' ', parts[1]).strip()
            pic = parts[2]
        elif len(parts) == 2:
            vid = parts[0]
            title = re.sub(r'\s+', ' ', parts[1]).strip()
            pic = ""
        else:
            vid = raw_id
            title = "视频"
            pic = ""
        play_url = f"{self.base_url}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}"
        }]}

    def searchContent(self, key, quick, pg="1"):
        return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        # 如果 id 是播放页链接，提取 m3u8
        if "vod/play" in id:
            r = self.fetch(id, headers=self.headers, timeout=15)
            if not r or r.status_code != 200:
                return {"parse": 1, "url": id, "header": self.headers}

            html = r.text
            match = re.search(r'var player_data=({.*?})</script>', html, re.S)
            if match:
                try:
                    data = json.loads(match.group(1))
                    m3u8_url = data.get("url", "")
                    if m3u8_url and m3u8_url.startswith("http"):
                        # 根据 m3u8_analyzer 取证结论：存在广告目录，走 localProxy 去广告
                        proxy_url = self._m3u8_proxy_url(m3u8_url)
                        return {"parse": 0, "url": proxy_url, "header": {"User-Agent": self.headers["User-Agent"]}}
                except:
                    pass

            return {"parse": 1, "url": id, "header": self.headers}

        # 如果 id 本身就是 m3u8 地址，也走代理
        if id.startswith("http") and ".m3u8" in id:
            proxy_url = self._m3u8_proxy_url(id)
            return {"parse": 0, "url": proxy_url, "header": {"User-Agent": self.headers["User-Agent"]}}

        return {"parse": 0, "url": "", "header": {}}

    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址"""
        if not url:
            return ""
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url), safe="")

    def getProxyUrl(self):
        """TVBox 代理地址"""
        return "http://127.0.0.1:9978/proxy"

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤（五层管线）"""
        try:
            # 解析参数
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

            # 获取 m3u8 内容
            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp or resp.status_code != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]

            # 检查是否为 m3u8
            if b"#EXTM3U" in content[:256]:
                text = content.decode("utf-8", errors="ignore")
                # 优先使用 ad_filter 模块
                if self.ad_filter:
                    cleaned = self.ad_filter.clean(text, target)
                else:
                    cleaned = self._clean_m3u8_fallback(text, target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

            # 非 m3u8 直接透传
            return [200, "application/octet-stream", content]

        except Exception as e:
            self.log({"localProxy": "error", "error": str(e)})
            return [500, "text/plain", f"proxy error: {str(e)}".encode("utf-8", errors="ignore")]

    def _clean_m3u8_fallback(self, text, source_url):
        """降级清洗：ad_filter 不可用时使用（五层管线）"""
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # ---- 第1层：图片流检测（只打标记） ----
        is_img = self._is_fake_image_stream(lines)
        if is_img:
            self.log({"stage": "clean", "fake_image_stream": True, "action": "keep_suffix_as_is"})

        # ---- 第2层：多码率主表 ----
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            return self._clean_m3u8_multi(lines, source_url)

        # ---- 第3层：正片目录锚点 ----
        main_dir = self._resolve_main_dir(lines, source_url, is_image_stream=is_img)

        # ---- 第4层：分片过滤 ----
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        # ---- 第5层：全滤兜底 ----
        if removed > 0 and (kept == 0 or removed > kept):
            self.log({"stage": "clean", "fallback": "no_filter", "removed": removed, "kept": kept, "anchor": main_dir})
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log({"stage": "clean", "removed": removed, "kept": kept, "anchor": main_dir})

        # 冗余标签清理
        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def _is_fake_image_stream(self, lines):
        """检测是否为图片流伪装（分片扩展名为强证据）"""
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
        """确定正片目录锚点"""
        import posixpath
        base_dir = posixpath.dirname(urllib.parse.urlparse(source_url).path)
        if not base_dir.endswith("/"):
            base_dir += "/"

        if is_image_stream:
            # 图片流：分片目录众数
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

        # 普通流：KEY URI 目录优先
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
        """分片过滤：只保留锚点目录下的分片"""
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
        """冗余标签清理"""
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
        """重写 m3u8 标签 URI"""
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
        """多码率主表透传：子流改代理地址"""
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

    def destroy(self):
        pass