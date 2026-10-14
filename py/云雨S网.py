# coding: utf-8
# ============================================================
# 站点名称: 云雨S网
# 主域名: https://xn------9i9dt24tj6dtp7b.yunyuswang3.click/
# 内容类型: 成人影视站
# 特殊说明: 详情页即播放页，DPlayer配置包含m3u8直链
# 验证时间: 2026-09-06
# 来源: AI生成
# m3u8结构摘要: 多码率主表，锚点使用m3u8_url目录(/20260818/.../1500kb/hls/)，可疑广告目录/20260830/REyBt5pd/3219kb/hls/，需去广告代理
# ============================================================
import json
import re
from urllib.parse import urljoin, quote, unquote, urlparse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xn------9i9dt24tj6dtp7b.yunyuswang3.click"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类定义
        self.classes = [
            {"type_id": "guochan", "type_name": "国产情色"},
            {"type_id": "changtui", "type_name": "长腿丝袜"},
            {"type_id": "lingjiarenqi", "type_name": "邻家人妻"},
            {"type_id": "renbenwuma", "type_name": "无码专区"},
            {"type_id": "zhongwenzimu", "type_name": "中文字幕"},
            {"type_id": "wangbaoxilie", "type_name": "网曝系列"},
            {"type_id": "chuanmei", "type_name": "传媒系列"},
            {"type_id": "tantan", "type_name": "探花专区"},
            {"type_id": "tiaojiao", "type_name": "SM调教"},
            {"type_id": "llishi", "type_name": "伦理视频"},
        ]
        self.filters = {}

    def getName(self):
        return "云雨S网"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐"""
        url = self.host + "/"
        html = self._fetch_text(url)
        items = self._parse_items(html, url)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or 1
        url = f"{self.host}/videos/categories/{tid}/{page}/"
        html = self._fetch_text(url)
        items = self._parse_items(html, url)
        # 总页数从分页器获取
        pagecount = self._parse_total_pages(html)
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount or 847,
            "limit": 20,
            "total": pagecount * 20 if pagecount else 0
        }

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}

        # 如果 ids 已打包直链，直接透传
        if "|$|" in vid:
            parts = vid.split("|$|")
            if len(parts) >= 5 and parts[4]:
                return {"list": [{
                    "vod_id": vid,
                    "vod_name": parts[1] or "未知标题",
                    "vod_pic": parts[2] or "",
                    "vod_remarks": parts[3] or "",
                    "vod_content": parts[3] or "",
                    "vod_play_from": "直链",
                    "vod_play_url": f"播放${parts[4]}"
                }]}

        title = pic = remark = ""
        play_url = ""
        try:
            detail_url = f"{self.host}/video/{vid}/"
            html = self._fetch_text(detail_url)
            if not html:
                return self._skeleton(vid)

            # 提取标题
            title = self._pick(html, [
                r'<h1[^>]*class="videoinfo-title"[^>]*>(.*?)</h1>',
                r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
                r'<title>([^<]+)</title>'
            ])

            # 提取封面
            pic = self._pick(html, [
                r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
                r'<img[^>]+class="[^"]*video-img[^"]*"[^>]+src="([^"]+)"',
                r'pic:\s*["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']'
            ])
            if pic and not pic.startswith("http"):
                pic = urljoin(detail_url, pic)

            # 提取播放地址（DPlayer配置）
            play_url = self._extract_play_url(html)

            if not play_url:
                return self._skeleton(vid, title, pic, "播放地址提取中")

            # 单线路单集
            from_str = "播放"
            url_str = f"播放${play_url}"

            return {"list": [{
                "vod_id": vid,
                "vod_name": title or "未知标题",
                "vod_pic": pic or "",
                "vod_remarks": remark or "",
                "vod_content": remark or "",
                "vod_play_from": from_str,
                "vod_play_url": url_str
            }]}

        except Exception as e:
            self.log({"detail": "exception", "vid": vid, "error": str(e)})
            return self._skeleton(vid, title, pic)

    def searchContent(self, key, quick, pg="1"):
        page = pg or "1"
        # 搜索分页使用 from_videos 参数，从第2页开始为02
        page_str = str(int(page)).zfill(2)
        url = f"{self.host}/search/?q={key}&from_videos={page_str}"
        html = self._fetch_text(url)
        items = self._parse_items(html, url)
        pagecount = self._parse_search_pages(html)
        return {"list": items, "page": int(page), "pagecount": pagecount or 22}

    def playerContent(self, flag, id, vipFlags):
        ua = self.headers.get("User-Agent", "")
        if not id:
            return {"parse": 1, "url": "", "header": {"User-Agent": ua}}

        play_url = str(id).strip()

        # L1: 直链识别
        if self._is_media_url(play_url):
            if ".m3u8" in play_url.lower():
                # 需要去广告代理（m3u8_analyzer 确认有广告分片）
                return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": {"User-Agent": ua}}
            return {"parse": 0, "url": play_url, "header": {"User-Agent": ua}}

        # 不是直链时尝试提取
        page_url = play_url if play_url.startswith("http") else urljoin(self.host, play_url)
        html = self._fetch_text(page_url)
        if html:
            extracted = self._extract_play_url(html)
            if extracted and self._is_media_url(extracted):
                if ".m3u8" in extracted.lower():
                    return {"parse": 0, "url": self._m3u8_proxy_url(extracted), "header": {"User-Agent": ua}}
                return {"parse": 0, "url": extracted, "header": {"User-Agent": ua}}

        # 降级
        return {"parse": 1, "url": page_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}

    def recommendContent(self, ids, pg):
        """相关推荐"""
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}
        try:
            detail_url = f"{self.host}/video/{vid}/"
            html = self._fetch_text(detail_url)
            if not html:
                return {"list": []}
            # 从 guess-list 提取推荐
            items = []
            block = self._grab_block(html, r'<ul[^>]*class="guess-list"[^>]*>(.*?)</ul>', re.S)
            if block:
                for m in re.finditer(
                    r'<a[^>]*class="guess-item-link"[^>]*href="([^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>.*?<h3[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h3>',
                    block, re.S
                ):
                    link = m.group(1)
                    pic = m.group(2)
                    title = re.sub(r"<[^>]+>", "", m.group(3)).strip()
                    if link and title:
                        vod_id = link.split("/")[-2] if link.endswith("/") else link.split("/")[-1]
                        items.append({
                            "vod_id": vod_id,
                            "vod_name": title,
                            "vod_pic": pic or "",
                            "vod_remarks": ""
                        })
            return {"list": items[:10]}
        except Exception:
            return {"list": []}

    def destroy(self):
        pass

    # ==================== 辅助方法 ====================

    def _fetch_text(self, url):
        try:
            r = self.fetch(url, headers=self.headers, timeout=15)
            if r and r.status_code == 200:
                return r.text
            return ""
        except Exception:
            return ""

    @staticmethod
    def _norm_ids(ids):
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

    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
        pid = str(vid).split("|$|")[0].replace("$", "|")
        return {"list": [{
            "vod_id": vid,
            "vod_name": title or "未知标题",
            "vod_pic": pic or "",
            "vod_remarks": remarks,
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": "播放$" + pid
        }]}

    def _pick(self, html, patterns, clean=True):
        for p in patterns:
            try:
                m = re.search(p, html, re.S | re.I)
                if m:
                    v = m.group(1).strip()
                    if clean:
                        v = re.sub(r"<[^>]+>", "", v)
                        v = v.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                    if v:
                        return v
            except Exception:
                continue
        return ""

    def _grab_block(self, html, pattern, flags=re.S):
        m = re.search(pattern, html, flags)
        return m.group(1) if m else ""

    def _parse_items(self, html, base_url):
        items = []
        # 找所有 .item
        for m in re.finditer(r'<div[^>]*class="item"[^>]*>(.*?)</div>\s*(?=<div|$)', html, re.S):
            block = m.group(1)
            # 提取链接和标题
            link_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*title="([^"]*)"', block, re.S)
            if not link_match:
                continue
            link = link_match.group(1)
            title = link_match.group(2) or re.sub(r"<[^>]+>", "", link_match.group(0)).strip()
            if not link or not title:
                continue
            vod_id = link.split("/")[-2] if link.endswith("/") else link.split("/")[-1]
            if not vod_id.isdigit():
                continue
            # 提取封面
            pic = ""
            img_m = re.search(r'<img[^>]+src="([^"]+)"', block)
            if img_m:
                pic = img_m.group(1)
            if pic and not pic.startswith("http"):
                pic = urljoin(base_url, pic)
            items.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": ""
            })
        return items

    def _parse_total_pages(self, html):
        m = re.search(r'总页数[：:]\s*(\d+)', html)
        if m:
            return int(m.group(1))
        m = re.search(r'<li[^>]*class="page"[^>]*>.*?(\d+)</a>', html, re.S)
        if m:
            return int(m.group(1)) + 5
        return 847

    def _parse_search_pages(self, html):
        pages = []
        for m in re.finditer(r'<li[^>]*class="page"[^>]*>.*?(\d+)</a>', html, re.S):
            pages.append(int(m.group(1)))
        if pages:
            return max(pages) + 2
        return 22

    def _is_media_url(self, url):
        if not url or not str(url).startswith("http"):
            return False
        path = str(url).split("?")[0].split("#")[0].lower()
        if path.endswith((".m3u8", ".mp4", ".mkv", ".flv", ".avi", ".m4v")):
            return True
        return "/hls/" in url.lower() and "m3u8" in url.lower()

    def _extract_play_url(self, html):
        """从详情页DPlayer配置提取m3u8地址"""
        # 方法1: videoObject.video.url
        m = re.search(r'videoObject\s*=\s*\{[^}]*video\s*:\s*\{\s*url\s*:\s*["\']([^"\']+)["\']', html, re.S)
        if m:
            return m.group(1)

        # 方法2: flashvars.video_url
        m = re.search(r'video_url\s*:\s*["\']([^"\']+)["\']', html)
        if m:
            return m.group(1)

        # 方法3: 全文正则
        m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
        if m:
            return m.group(1)

        return ""

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def localProxy(self, param):
        """m3u8去广告代理 - 五层管线"""
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                qs = urlparse(target).query
                if "url=" in qs:
                    for part in qs.split("&"):
                        if part.startswith("url="):
                            target = part[4:]
                            break
            target = unquote(str(target or ""))
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp or getattr(resp, "status_code", 0) != 200:
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
            self.log("localProxy error: " + str(e))
            return [500, "text/plain", f"proxy error: {str(e)}".encode("utf-8", errors="ignore")]

    def _clean_m3u8(self, text, source_url):
        """五层m3u8清洗管线"""
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 第1层: 图片流检测（只打标记，不return）
        is_img = self._is_fake_image_stream(text, source_url)
        if is_img:
            self.log({"stage": "clean", "fake_image_stream": True, "action": "keep_suffix_as_is"})

        # 第2层: 多码率主表透传
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            return self._clean_m3u8_multi(lines, source_url)

        # 第3层: 正片目录锚点
        main_dir = self._resolve_main_dir(lines, source_url, is_image_stream=is_img)

        # 第4层: 分片过滤
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        # 第5层: 全滤兜底
        if removed > 0 and (kept == 0 or removed > kept):
            self.log({"stage": "clean", "fallback": "no_filter", "removed": removed, "kept": kept, "anchor": main_dir})
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log({"stage": "clean", "removed": removed, "kept": kept, "anchor": main_dir})

        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def _is_fake_image_stream(self, text, source_url):
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

    def _clean_m3u8_multi(self, lines, source_url):
        out = []
        for line in lines:
            if line.startswith("#"):
                out.append(line)
            else:
                child = urljoin(source_url, line)
                if ".m3u8" in child.lower():
                    out.append(self._m3u8_proxy_url(child))
                else:
                    out.append(child)
        return "\n".join(out) + "\n"

    def _resolve_main_dir(self, lines, source_url, is_image_stream=False):
        import posixpath
        parsed = urlparse(source_url)
        base_dir = posixpath.dirname(parsed.path)
        if not base_dir.endswith("/"):
            base_dir += "/"
        # 修复：去除连续斜杠
        base_dir = re.sub(r"/{2,}", "/", base_dir)

        # 图片流: 改用分片目录众数
        if is_image_stream:
            counter = {}
            for line in lines:
                if not line or line.startswith("#"):
                    continue
                p = urlparse(urljoin(source_url, line)).path
                d = posixpath.dirname(p)
                if d and d != "/":
                    d = re.sub(r"/{2,}", "/", d)
                    counter[d + "/"] = counter.get(d + "/", 0) + 1
            if counter:
                return max(counter.items(), key=lambda kv: kv[1])[0]
            return base_dir

        # 普通流: KEY URI 目录优先
        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            key_path = urlparse(key_uri if key_uri.startswith("http") else urljoin(source_url, key_uri)).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                key_dir = re.sub(r"/{2,}", "/", key_dir)
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
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)
        return line

    def _resolve_main_dir_by_segments(self, lines, source_url):
        """基于分片路径众数确定正片目录（不受m3u8动态路径影响）"""
        import posixpath
        from urllib.parse import urlparse, urljoin
        counter = {}
        for line in lines:
            if not line or line.startswith("#"):
                continue
            media_url = urljoin(source_url, line)
            p = urlparse(media_url).path
            d = posixpath.dirname(p)
            if d and d != "/":
                d = re.sub(r"/{2,}", "/", d)
                if d.count("/") >= 2:
                    counter[d + "/"] = counter.get(d + "/", 0) + 1
        if counter:
            return max(counter.items(), key=lambda kv: kv[1])[0]
        parsed = urlparse(source_url)
        base = posixpath.dirname(parsed.path)
        return re.sub(r"/{2,}", "/", base + "/" if base else "/")

    def _resolve_fallback_dir(self, lines, source_url):
        """宽松兜底锚点：取分片路径的公共前缀（前两级目录）"""
        import posixpath
        from urllib.parse import urlparse, urljoin
        from collections import Counter
        dirs = []
        for line in lines:
            if not line or line.startswith("#"):
                continue
            media_url = urljoin(source_url, line)
            p = urlparse(media_url).path
            d = posixpath.dirname(p)
            if d and d != "/":
                d = re.sub(r"/{2,}", "/", d)
                parts = [part for part in d.split("/") if part]
                if len(parts) >= 2:
                    dirs.append("/" + "/".join(parts[:2]) + "/")
                elif len(parts) == 1:
                    dirs.append("/" + parts[0] + "/")
        if dirs:
            return Counter(dirs).most_common(1)[0][0]
        parsed = urlparse(source_url)
        base = posixpath.dirname(parsed.path)
        return re.sub(r"/{2,}", "/", base + "/" if base else "/")


