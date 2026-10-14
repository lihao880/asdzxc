# coding: utf-8
# ============================================================
# 站点: 大屌v巨乳 (MacCMS)
# 主域名: https://pfgzyhx2z.817020.xyz
# 发布页: 817010.xyz
# 内容类型: 成人影视（视频）
# 特殊说明: 全站页面为 base64(atob) + 数字数组双重编码，须在脚本内解码
# 来源: 手动逆向 + m3u8_analyzer 取证
# 最后验证: 2026-09-12
# ============================================================
import json
import base64
import ast
import re
from urllib.parse import quote, urljoin, unquote, urlparse
import posixpath

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        # __init__ 只做本地初始化，零网络
        self.extend = ""
        self.host = "https://pfgzyhx2z.817020.xyz"
        self.classes = [
            {"type_id": "3", "type_name": "国产视频"},
            {"type_id": "7", "type_name": "日本有码"},
            {"type_id": "8", "type_name": "其他口味"},
            {"type_id": "1", "type_name": "日本无码"},
            {"type_id": "2", "type_name": "欧美视频"},
            {"type_id": "4", "type_name": "动漫肉番"},
            {"type_id": "5", "type_name": "伦理三级"},
        ]
        # 站点无真实筛选 DOM/API，不伪造筛选
        self.filters = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
        }
        # m3u8_analyzer 取证结论：存在广告目录 /20260830/... ，需清洗
        self.NEED_CLEAN = True
        self.ANCHOR = "/20260910/uVXsfAuw/2000kb/hls/"
        self.AD_DIRS = ["/20260830/i2vAQKIt/1000kb/hls/"]

    def getName(self):
        return "大屌v巨乳"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    # ---------------- 编码解码 ----------------
    def _decode_page(self, raw):
        """全站双重编码: base64(atob) -> 数字数组 -> bytes -> html"""
        if not raw:
            return ""
        try:
            m = re.search(r'atob\("([^"]+)"\)', raw)
            if not m:
                return raw
            stage1 = base64.b64decode(m.group(1)).decode("utf-8", errors="ignore")
            try:
                arr = ast.literal_eval(stage1.strip())
                return bytes(arr).decode("utf-8", errors="ignore")
            except Exception:
                return stage1
        except Exception as e:
            self.log({"action": "decode_fail", "error": str(e)})
            return raw

    def _fetch_html(self, url, post_data=None):
        try:
            if post_data is not None:
                r = self.post(url, data=post_data, headers=self.headers, timeout=20)
            else:
                r = self.fetch(url, headers=self.headers, timeout=20)
            if not r or r.status_code != 200:
                return ""
            raw = r.text if hasattr(r, "text") else ""
            return self._decode_page(raw)
        except Exception as e:
            self.log({"action": "fetch_fail", "url": url, "error": str(e)})
            return ""

    # ---------------- 首页 ----------------
    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/")
        return {"list": self._parse_list(html)}

    # ---------------- 分类 ----------------
    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        if page == "1":
            url = f"{self.host}/vodtype/{tid}.html"
        else:
            url = f"{self.host}/vodtype/{tid}-{page}.html"
        html = self._fetch_html(url)
        vlist = self._parse_list(html)
        # 尾页实测 18160 页，取一个保守的较大值
        return {
            "list": vlist,
            "page": int(page) if page.isdigit() else 1,
            "pagecount": 18160,
            "limit": 20,
            "total": 999999,
        }

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        # POST /vod/search.html  wd=关键词
        data = "wd=" + quote(key or "")
        html = self._fetch_html(self.host + "/vod/search.html", post_data=data)
        # 无结果页过滤
        if html and re.search(r"没有找到|暂无数据|没有找到您想要的结果", html):
            return {"list": [], "page": int(pg) if str(pg).isdigit() else 1}
        return {"list": self._parse_list(html), "page": int(pg) if str(pg).isdigit() else 1}

    # ---------------- 详情 ----------------
    @staticmethod
    def _norm_ids(ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
        pid = str(vid).split("|$|")[0].replace("$", "|")
        return {"list": [{
            "vod_id": vid, "vod_name": title or "未知标题", "vod_pic": pic or "",
            "vod_remarks": remarks, "vod_content": "",
            "vod_play_from": "播放", "vod_play_url": "播放$" + pid,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        vid = raw.split("|$|")[0]
        try:
            html = self._fetch_html(f"{self.host}/voddetail/{vid}.html")
            if not html or len(html) < 500:
                return self._skeleton(vid, remarks="详情加载失败")

            title = ""
            m = re.search(r'<h1[^>]*class="movie-title"[^>]*>(.*?)</h1>', html, re.S)
            if m:
                title = self._clean_text(m.group(1))
            if not title:
                m = re.search(r"<title>(.*?)</title>", html, re.S)
                if m:
                    title = self._clean_text(m.group(1)).split("--")[-1]
            if not title:
                m = re.search(r'property="og:title"[^>]*content="([^"]*)"', html)
                if m:
                    title = self._clean_text(m.group(1))

            pic = ""
            m = re.search(r'<img[^>]+src="([^"]+)"[^>]*class="vod-cover"', html)
            if not m:
                m = re.search(r'class="vod-cover"[^>]*src="([^"]+)"', html)
            if not m:
                m = re.search(r'property="og:image"[^>]*content="([^"]*)"', html)
            if m:
                pic = m.group(1)

            # 播放页入口: /vodplay/{vid}-1-1.html
            play_page = ""
            m = re.search(r'href="(/vodplay/%s[^"]*)"' % re.escape(vid), html)
            if m:
                play_page = m.group(1)
            if not play_page:
                m = re.search(r'href="(/vodplay/[^"]+)"', html)
                if m:
                    play_page = m.group(1)

            vod = {
                "vod_id": raw,
                "vod_name": title or "视频",
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_content": title or "",
                "vod_play_from": "播放",
                "vod_play_url": "播放$" + (play_page or f"/vodplay/{vid}-1-1.html"),
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"detail": "exception", "error": str(e)})
            return self._skeleton(vid)

    @staticmethod
    def _clean_text(s):
        s = re.sub(r"<[^>]+>", "", s or "")
        s = s.replace("&nbsp;", " ").replace("&amp;", "&").strip()
        return s

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_url = str(id or "").strip()
        if play_url and "$" in play_url:
            play_url = play_url.split("$", 1)[-1]
        if play_url.startswith("http") and ".m3u8" in play_url.lower():
            if self.NEED_CLEAN:
                return {"parse": 0, "url": self._m3u8_proxy_url(play_url),
                        "header": {"User-Agent": self.headers["User-Agent"]}}
            return {"parse": 0, "url": play_url,
                    "header": {"User-Agent": self.headers["User-Agent"]}}

        # 站内播放页：解析 mark#bfz data-user-name="第1集$http.../index.m3u8"
        page_url = play_url
        if page_url and not page_url.startswith("http"):
            page_url = urljoin(self.host + "/", page_url.lstrip("/"))
        m3u8 = ""
        if page_url:
            html = self._fetch_html(page_url)
            if html:
                m = re.search(r'data-user-name="[^"$]*\$(https?://[^"]+\.m3u8[^"]*)"', html)
                if not m:
                    m = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', html)
                if m:
                    m3u8 = m.group(1)

        if m3u8:
            if self.NEED_CLEAN:
                return {"parse": 0, "url": self._m3u8_proxy_url(m3u8),
                        "header": {"User-Agent": self.headers["User-Agent"]}}
            return {"parse": 0, "url": m3u8,
                    "header": {"User-Agent": self.headers["User-Agent"]}}

        # 降级：url 禁止为空
        return {"parse": 1, "url": page_url or self.host,
                "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/"}}

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        base = self.getProxyUrl()
        # getProxyUrl() 通常已含 "?do=py"，只需追加 url 参数
        sep = "&" if "?" in base else "?do=py&"
        if base.rstrip().endswith("do=py"):
            return base + "&url=" + quote(str(url or ""), safe="")
        if "?" in base:
            return base + "&url=" + quote(str(url or ""), safe="")
        return base + "?do=py&url=" + quote(str(url or ""), safe="")
    IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
    VIDEO_EXT = (".ts", ".m4s", ".mp4", ".aac", ".m4a")

    def _is_fake_image_stream(self, text):
        has_video = False
        has_image = False
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            path = line.split("?")[0].split("#")[0].lower()
            if path.endswith(self.VIDEO_EXT):
                has_video = True
            elif path.endswith(self.IMAGE_EXT):
                has_image = True
        return has_image and not has_video

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

    def _resolve_main_dir(self, lines, source_url, is_image_stream=False):
        base_dir = posixpath.dirname(urlparse(source_url).path)
        if not base_dir.endswith("/"):
            base_dir += "/"
        if is_image_stream:
            counter = {}
            for line in lines:
                if not line or line.startswith("#"):
                    continue
                p = urlparse(urljoin(source_url, line)).path
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
            key_path = urlparse(key_uri if key_uri.startswith("http")
                                else urljoin(source_url, key_uri)).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return base_dir

    def _filter_segments(self, lines, source_url, main_dir):
        segments, pending = [], []
        removed = kept = 0
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
        is_img = self._is_fake_image_stream(text)
        if is_img:
            self.log({"stage": "clean", "fake_image_stream": True})
        # 第2层：多码率
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            return self._clean_m3u8_multi(lines, source_url)
        # 第3层：锚点
        main_dir = self._resolve_main_dir(lines, source_url, is_image_stream=is_img)
        # 第4层：过滤
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)
        # 第5层：全滤兜底
        if removed > 0 and (kept == 0 or removed > kept):
            self.log({"stage": "clean", "fallback": "no_filter",
                      "removed": removed, "kept": kept, "anchor": main_dir})
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"
        if removed:
            self.log({"stage": "clean", "removed": removed,
                      "kept": kept, "anchor": main_dir})
        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                qs = urlparse(target).query
                import urllib.parse as _up
                q = _up.parse_qs(qs)
                if "url" in q:
                    target = q["url"][0]
            target = unquote(str(target or ""))
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            resp = self.fetch(target, headers={"User-Agent": self.headers["User-Agent"]}, timeout=20)
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
            return [500, "text/plain", ("localProxy error: " + str(e)).encode("utf-8", errors="ignore")]

    # ---------------- 解析列表 ----------------
    def _parse_list(self, html):
        items = []
        if not html:
            return items
        # 以 box-item 为块切分
        blocks = re.findall(r'<div class="box-item">(.*?)</div>\s*</div>', html, re.S)
        if not blocks:
            blocks = re.split(r'<div class="box-item">', html)[1:]
        seen = set()
        for b in blocks:
            m = re.search(r'href="(/voddetail/(\d+)\.html)"', b)
            if not m:
                continue
            vid = m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            nm = re.search(r'title="([^"]*)"', b)
            name = nm.group(1) if nm else ""
            if not name:
                nm = re.search(r'class="movie-name"[^>]*>([^<]*)<', b)
                name = nm.group(1) if nm else ""
            pic = ""
            pm = re.search(r'<img[^>]+src="([^"]+)"', b)
            if pm:
                pic = pm.group(1)
            remark = ""
            rm = re.search(r'<span>([^<]*)</span>', b)
            if rm:
                remark = rm.group(1)
            items.append({
                "vod_id": vid,
                "vod_name": self._clean_text(name),
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return items

    # ---------------- 推荐 ----------------
    def recommendContent(self, ids, pg):
        """相关推荐（官方模式3：分类/关键词搜索 + 热门兜底）"""
        try:
            raw = self._norm_ids(ids)
            m0 = re.search(r"(\d{3,})", raw)
            vid = m0.group(1) if m0 else ""
            self.log({"recommend": "input", "raw": raw, "vid": vid})
            if not vid:
                return {"list": []}
            page = str(max(1, int(pg or 1)))
            # 1. 详情页取标题
            html = self._fetch_html(f"{self.host}/voddetail/{vid}.html")
            title = ""
            if html:
                m = re.search(r'<h1[^>]*class="movie-title"[^>]*>(.*?)</h1>', html, re.S)
                if m:
                    title = self._clean_text(m.group(1))
            self.log({"recommend": "title", "title": title})
            videos = []
            seen = set()
            # 2. 关键词：番号优先，否则前4字
            kw = ""
            if title:
                m = re.search(r"([A-Za-z]+-\d+)", title)
                if m:
                    kw = m.group(1)
                if not kw:
                    kw = re.sub(r"[^\w\u4e00-\u9fff]", "", title)[:4]
            # 3. 关键字搜索
            if kw:
                data = "wd=" + quote(kw)
                shtml = self._fetch_html(self.host + "/vod/search.html", post_data=data)
                for x in self._parse_list(shtml):
                    if x["vod_id"] != vid and x["vod_id"] not in seen:
                        seen.add(x["vod_id"]); videos.append(x)
            # 4. 兜底：最新列表（首页）补位
            if len(videos) < 12:
                hhtml = self._fetch_html(self.host + "/")
                for x in self._parse_list(hhtml):
                    if x["vod_id"] != vid and x["vod_id"] not in seen:
                        seen.add(x["vod_id"]); videos.append(x)
                        if len(videos) >= 12:
                            break
            self.log({"recommend": "result", "count": len(videos), "kw": kw})
            return {"list": videos[:12]}
        except Exception as e:
            self.log({"recommend": "exception", "error": str(e)})
            return {"list": []}
    def destroy(self):
        pass