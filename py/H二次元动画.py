# coding: utf-8
# H二次元动画 影视爬虫 - MacCMS conch 模板站
# ============================================================
# 主域名   : https://cf1.h18ani7.vip
# 备用域名 : https://cf8.h18ani6.vip
# 发布页   : https://www.baidu-xx.xyz/發佈/
# 内容类型 : 视频（成人动画）
# 特殊说明 : MacCMS conch 模板；列表卡片 .vodlist_item / 搜索 .searchlist_item
#            详情页内联 player_aaaa 变量含 m3u8 直链；双线路 /v/{id}-{sid}-{nid}/
#            搜索路由 /s/{关键词}-------------/；分页 /t/{tid}/page/{pg}/
#            m3u8 直链 CDN 有地域调度（开发环境拉取 502/DNS失败），AI 侧形态自查通过
# 提取方式 : 9 层提取管线（法则32），详情页 player_aaaa 优先
# 最后验证 : 2026-09-21
# 来源     : 自主逆向
# ============================================================

import re
import json
import urllib.parse
import posixpath
from urllib.parse import quote, urljoin, urlparse

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://cf1.h18ani7.vip"
        self.site_name = "H二次元动画"
        self.classes = [
            {"type_id": "112", "type_name": "動漫一"},
            {"type_id": "28", "type_name": "動漫二"},
            {"type_id": "21", "type_name": "動漫三"},
            {"type_id": "20", "type_name": "動漫四"},
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
        }
        # 法则30：m3u8_analyzer 取证显示主表含跨目录开头广告分片
        # （广告目录 /20260913/.../9637kb/hls/ 混在正片 /20260919/.../1500kb/hls/ 中）
        # -> 需要走 localProxy 五层清洗
        self.NEED_CLEAN = True
    def getName(self):
        return "H二次元动画"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/")
        items = self._parse_list(html)
        return {"list": items[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg) if pg else "1"
        # MacCMS vodshow 路由才是真分类列表（/t/ 只是首页式聚合，无分页）
        # 分页格式：/show/{tid}--------{pg}---/  （实测 pg=2 内容不同）
        if pg and pg != "1":
            url = f"{self.host}/show/{tid}--------{pg}---/"
        else:
            url = f"{self.host}/show/{tid}-----------/"
        html = self._fetch_html(url)
        items = self._parse_list(html)
        # 总页数：从分页区提取，兜底 999
        return {
            "list": items,
            "page": int(pg),
            "pagecount": self._parse_pagecount(html),
            "limit": 20,
            "total": 999,
        }

    def _parse_pagecount(self, html):
        """从分页区提取总页数，失败返回 999"""
        if not html:
            return 999
        m = re.search(r"共\s*(\d+)\s*页", html)
        if m:
            return int(m.group(1))
        nums = re.findall(r'/show/' + r'[^/]*?(\d+)---/', html)
        if nums:
            try:
                return max(int(n) for n in nums) + 1
            except Exception:
                pass
        return 999
    @staticmethod
    def _norm_ids(ids):
        """法则35：ids 可能是 list / str / int / bytes，禁止直接 ids[0]"""
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
        """法则35：详情兜底骨架，禁止返回空 list"""
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
        try:
            ps = raw.split("|$|")
            vod_id = ps[0]
            old_name = ps[1] if len(ps) > 1 else ""
            old_pic = ps[2] if len(ps) > 2 else ""
            old_remark = ps[3] if len(ps) > 3 else ""
            detail_url = ps[4] if len(ps) > 4 else f"{self.host}/v/{vod_id}-1-1/"

            html = self._fetch_html(detail_url)
            if html:
                name = self._pick_text(html, [r"<h2[^>]*class=\"title[^\"]*\"[^>]*>(.*?)</h2>",
                                              r"<title>(.*?)[_\-\|]"])
                name = self._clean_title(name) or old_name
                pic = self._pick_text(html, [r"<img[^>]*class=\"[^\"]*lazyload[^\"]*\"[^>]*data-original=\"([^\"]+)\"",
                                             r"<img[^>]*data-original=\"([^\"]+)\""])
                if pic and not pic.startswith("http"):
                    pic = urljoin(detail_url, pic)
                desc = self._pick_text(html, [r"<div[^>]*class=\"[^\"]*content[^\"]*\"[^>]*>(.*?)</div>"])

                # 提取所有线路：/v/{id}-{sid}-{nid}/ 链接
                play_from, play_url = self._parse_play_lines(html, vod_id, detail_url)
                if play_from and play_url:
                    vod = {
                        "vod_id": raw,
                        "vod_name": name or old_name or "视频",
                        "vod_pic": pic or old_pic,
                        "vod_remarks": old_remark,
                        "vod_content": self._strip_html(desc) or old_remark,
                        "vod_play_from": play_from,
                        "vod_play_url": play_url,
                    }
                    return {"list": [vod]}
        except Exception as e:
            self.log({"detail": "exception", "ids": raw, "error": str(e)})
        return self._skeleton(raw, old_name, old_pic, old_remark)

    def _parse_play_lines(self, html, vod_id, detail_url):
        """解析所有线路与选集，$$$ 分组严格对齐（法则35 L4）

        站点线路结构：多个 <div class="content play_list_box ...">，
        每块内有 player_infotip（资源名）+ 若干 <li><a href="/v/{id}-{sid}-1/">标签</a></li>。
        """
        froms = []
        urls = []
        seen_sid = set()
        # 按播放列表块切分，每块一条线路
        blocks = re.split(r'(?=<div class="content play_list_box)', html)
        for blk in blocks:
            # 取该块内第一个 sid 链接
            m = re.search(r'href="(/v/' + re.escape(str(vod_id)) + r'-(\d+)-1/)"[^>]*>([^<]+)</a>', blk)
            if not m:
                continue
            href, sid, label = m.group(1), m.group(2), m.group(3).strip()
            if sid in seen_sid:
                continue
            seen_sid.add(sid)
            # 线路名：优先块内 player_infotip 的资源名，否则用 <a> 文本
            name = label
            info_m = re.search(r'player_infotip[^>]*>.*?由(.+?)(?:提供|-|&nbsp;|</)', blk, re.S)
            if info_m:
                cand = re.sub(r"<[^>]+>", "", info_m.group(1)).strip()
                if cand:
                    name = cand
            if not name:
                name = "线路" + sid
            play_page = urljoin(detail_url, href)
            froms.append(name)
            urls.append("高清$" + play_page)
        if not froms:
            return "", ""
        return "$$$".join(froms), "$$$".join(urls)
    def searchContent(self, key, quick, pg="1"):
        pg = str(pg) if pg else "1"
        kw = quote(str(key or ""), safe="")
        if pg and pg != "1":
            url = f"{self.host}/s/{kw}-------------/page/{pg}/"
        else:
            url = f"{self.host}/s/{kw}-------------/"
        html = self._fetch_html(url)
        items = self._parse_list(html, search=True)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        """播放出口（法则32：9层管线穷尽后才降级）"""
        ua = self.headers.get("User-Agent", "")
        raw_id = str(id or "").strip()
        if not raw_id:
            return {"parse": 1, "url": self.host + "/",
                    "header": {"User-Agent": ua, "Referer": self.host + "/"}}

        # id 可能是 "名称$地址" 格式
        if "$" in raw_id:
            parts = raw_id.split("$", 1)
            if len(parts) == 2 and parts[1]:
                raw_id = parts[1].strip()

        # L1 直链识别
        if self._is_media_url(raw_id):
            return self._wrap_play(raw_id, ua)

        # 归一化播放页地址
        page_url = raw_id if raw_id.startswith("http") else f"{self.host}/v/{raw_id}-1-1/"

        html = self._fetch_html(page_url)

        # L2-L6 候选池
        bag = self._extract_play_candidates(html, page_url)

        # L9 打分
        cands = self._pick_playable(bag)
        if cands:
            self.log({"stage": "extract", "result": "hit", "count": len(cands)})
            return self._wrap_play(cands[0], ua)

        self.log({"stage": "extract", "result": "all_layers_miss", "page": page_url})
        return {"parse": 1, "url": page_url,
                "header": {"User-Agent": ua, "Referer": self.host + "/"}}
    def _wrap_play(self, url, ua, referer=""):
        header = {"User-Agent": ua}
        # CDN 防盗链通常只校验域名级 Referer，不接受播放页子路径
        # 实机反馈：带 /v/xxx 子路径 Referer 起播失败 -> 统一用站点根
        header["Referer"] = self.host + "/"
        if getattr(self, "NEED_CLEAN", False) and ".m3u8" in str(url).lower():
            return {"parse": 0, "url": self._m3u8_proxy_url(url), "header": header}
        return {"parse": 0, "url": url, "header": header}
    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤（五层管线）"""
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
            if not resp or getattr(resp, "status_code", 0) != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")
            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            return [500, "text/plain", ("localProxy error: " + str(e)).encode("utf-8", "ignore")]

    def _clean_m3u8(self, text, source_url):
        """m3u8 五层清洗管线（法则30）

        第1层 图片流检测（只打标记，后缀原样透传，不 return）
        第2层 多码率主表透传（子流改代理地址）
        第3层 正片目录锚点（KEY URI 优先 / 图片流分片目录众数）
        第4层 分片过滤（EXTINF 与分片成对丢弃）
        第5层 冗余标签清理 + 全滤兜底
        """
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        is_img = self._is_fake_image_stream(text, source_url)

        # 第2层：多码率主表透传
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child)
                               if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        main_dir = self._resolve_main_dir(lines, source_url, is_image_stream=is_img)
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        if removed > 0 and (kept == 0 or removed > kept):
            self.log({"stage": "clean", "fallback": "no_filter",
                      "removed": removed, "kept": kept, "anchor": main_dir})
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log({"stage": "clean", "removed": removed,
                      "kept": kept, "anchor": main_dir})
        return "\n".join(self._dedup_tags(segments, source_url)) + "\n"

    IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
    VIDEO_EXT = (".ts", ".m4s", ".mp4", ".aac", ".m4a")
    PROTECTED_TAGS = ("#EXT-X-KEY", "#EXT-X-MAP", "#EXT-X-SESSION-KEY")
    NOISE_TAGS = ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE")

    def _is_fake_image_stream(self, text, source_url):
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

    def _resolve_main_dir(self, lines, source_url, is_image_stream=False):
        base_dir = posixpath.dirname(urlparse(source_url).path)
        if not base_dir.endswith("/"):
            base_dir += "/"
        if is_image_stream:
            counter = {}
            for line in lines:
                if not line or line.startswith("#"):
                    continue
                path = urlparse(urljoin(source_url, line)).path
                d = posixpath.dirname(path)
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
            if not key_uri.startswith("http"):
                key_uri = urljoin(source_url, key_uri)
            key_dir = posixpath.dirname(urlparse(key_uri).path)
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
        if pending:
            segments.extend(pending)
        return segments, removed, kept

    def _dedup_tags(self, segments, source_url):
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in self.NOISE_TAGS:
                if not out or out[-1] in self.NOISE_TAGS:
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in self.NOISE_TAGS:
            out.pop()
        return out

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith(self.PROTECTED_TAGS):
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
    # ==================== 列表解析 ====================
    CARD_START = ('<li class="vodlist_item', '<li class="searchlist_item"')

    def _parse_list(self, html, search=False):
        items = []
        if not html:
            return items
        # 无结果页过滤
        if re.search(r"没有找到|暂无数据|没有找到您想要的结果|搜索无结果", html):
            return items
        # 按卡片起始标记切分（class 可能带 num_N 等后缀）
        blocks = re.split(r'(?=<li class="(?:vodlist_item|searchlist_item))', html)
        seen = set()
        for blk in blocks:
            # 1) 详情链接 + 封面（属性顺序不固定，分开取）
            href_m = re.search(r'href="(/v/\d+-1-1/)"', blk)
            if not href_m:
                continue
            href = href_m.group(1)
            vm = re.search(r"/v/(\d+)-", href)
            vid = vm.group(1) if vm else href
            pic_m = re.search(r'data-original="([^"]+)"', blk)
            pic = pic_m.group(1) if pic_m else ""
            if not pic:
                continue
            # 2) 标题：优先 a 标签 title，其次 vodlist_title 内文本
            name = ""
            title_m = re.search(r'<a[^>]*class="[^"]*vodlist_thumb[^"]*"[^>]*title="([^"]*)"', blk)
            if not title_m:
                title_m = re.search(r'<a[^>]*title="([^"]*)"[^>]*class="[^"]*vodlist_thumb', blk)
            if title_m:
                name = title_m.group(1).strip()
            if not name:
                tm = re.search(r'class="[^"]*vodlist_title[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>', blk, re.S)
                if tm:
                    name = re.sub(r"<[^>]+>", "", tm.group(1)).strip()
            if not name:
                tm = re.search(r'<a[^>]*title="([^"]+)"', blk)
                if tm:
                    name = tm.group(1).strip()
            if not name:
                continue
            if not pic.startswith("http"):
                pic = urljoin(self.host + "/", pic)
            if vid in seen:
                continue
            seen.add(vid)
            play_page = urljoin(self.host + "/", href)
            packed = "|$|".join([str(vid), name, pic, "", play_page])
            items.append({
                "vod_id": packed,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return items
    MEDIA_EXT = (".m3u8", ".mp4", ".mkv", ".flv", ".avi", ".m4v", ".mov", ".ts")
    PLAYER_VARS = ("player_aaaa", "player_data", "player_conf", "playerData", "vid_data")
    URL_KEYS = ("url", "play_url", "playUrl", "video_url", "videoUrl", "src",
                "source", "m3u8", "hls", "file", "purl", "vurl")
    FALLBACK_PATTERNS = (
        r'https?://[^\s"\'<>()\\]+?\.m3u8[^\s"\'<>()\\]*',
        r'https?://[^\s"\'<>()\\]+?\.mp4[^\s"\'<>()\\]*',
        r'["\']((?:https?:)?\\?/\\?/[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)["\']',
    )

    def _is_media_url(self, url):
        if not url or not str(url).startswith("http"):
            return False
        path = str(url).split("?")[0].split("#")[0].lower()
        if path.endswith(self.MEDIA_EXT):
            return True
        low = str(url).lower()
        return ("/hls/" in low and "m3u8" in low) or "playlist.m3u8" in low

    def _looks_like_media(self, v):
        if not v or not isinstance(v, str):
            return False
        low = v.lower()
        return any(e in low for e in (".m3u8", ".mp4", ".flv", ".mkv")) or "m3u8" in low

    def _grab_json_object(self, text, start_idx):
        """L2：平衡括号截取完整 JSON"""
        if start_idx < 0 or start_idx >= len(text) or text[start_idx] != "{":
            return ""
        depth = 0
        in_str = False
        esc = False
        quote = ""
        for i in range(start_idx, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == quote:
                    in_str = False
                continue
            if ch in ('"', "'"):
                in_str = True
                quote = ch
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start_idx:i + 1]
        return ""

    def _loose_json(self, raw):
        if not raw:
            return None
        candidates = [raw, raw.replace("\\/", "/")]
        fixed = re.sub(r",\s*([}\]])", r"\1", raw)
        candidates.append(fixed)
        for c in candidates:
            try:
                obj = json.loads(c)
                if isinstance(obj, (dict, list)):
                    return obj
            except Exception:
                continue
        return None

    def _walk_json(self, node, bag, depth=0):
        if depth > 6 or node is None:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str):
                    if str(k).lower() in self.URL_KEYS or self._looks_like_media(v):
                        bag.append(v)
                else:
                    self._walk_json(v, bag, depth + 1)
        elif isinstance(node, list):
            for v in node:
                if isinstance(v, str):
                    if self._looks_like_media(v):
                        bag.append(v)
                else:
                    self._walk_json(v, bag, depth + 1)

    def _normalize_url(self, raw):
        if not raw:
            return ""
        s = str(raw).strip().strip('"').strip("'")
        s = s.replace("\\/", "/").replace("\\u002f", "/").replace("\\u002F", "/")
        s = s.replace('" + "', "").replace("' + '", "")
        try:
            import html as _html
            s = _html.unescape(s)
        except Exception:
            pass
        for _ in range(2):
            if "%3A%2F%2F" in s or "%3a%2f%2f" in s:
                try:
                    s = urllib.parse.unquote(s)
                except Exception:
                    break
            else:
                break
        return s.strip()

    def _has_strong_candidate(self, bag):
        for raw in bag:
            u = self._normalize_url(raw)
            if u.startswith("http") and (".m3u8" in u.lower() or ".mp4" in u.lower()):
                return True
        return False

    def _extract_play_candidates(self, html, page_url, depth=0):
        bag = []
        if not html:
            return bag

        # L2 播放器变量（平衡括号）
        for var in self.PLAYER_VARS:
            for m in re.finditer(re.escape(var) + r'\s*=\s*', html):
                brace = html.find("{", m.end())
                if brace < 0 or brace - m.end() > 8:
                    continue
                raw = self._grab_json_object(html, brace)
                obj = self._loose_json(raw)
                if obj is not None:
                    self._walk_json(obj, bag)
                elif raw:
                    for pat in self.FALLBACK_PATTERNS:
                        for hit in re.findall(pat, raw):
                            bag.append(hit if isinstance(hit, str) else hit[0])

        # L3 内联 JSON
        for m in re.finditer(r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>', html, re.S):
            obj = self._loose_json(m.group(1).strip())
            if obj is not None:
                self._walk_json(obj, bag)

        # L5 全文正则
        for pat in self.FALLBACK_PATTERNS:
            for hit in re.findall(pat, html):
                bag.append(hit if isinstance(hit, str) else hit[0])

        # L6 iframe 递归（限深2）
        if depth < 2 and not self._has_strong_candidate(bag):
            for src in re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html)[:3]:
                sub_url = urljoin(page_url, self._normalize_url(src))
                if not sub_url.startswith("http"):
                    continue
                sub_headers = dict(self.headers)
                sub_headers["Referer"] = page_url
                try:
                    resp = self.fetch(sub_url, headers=sub_headers, timeout=15)
                    sub_html = resp.text if resp and hasattr(resp, "text") else ""
                except Exception:
                    sub_html = ""
                if sub_html:
                    bag.extend(self._extract_play_candidates(sub_html, sub_url, depth + 1))
        return bag

    def _pick_playable(self, bag):
        seen = set()
        cands = []
        for raw in bag:
            u = self._normalize_url(raw)
            if not u or u in seen or not u.startswith("http"):
                continue
            seen.add(u)
            cands.append(u)

        def score(u):
            s = 0
            low = u.lower()
            if ".m3u8" in low:
                s += 10
            elif ".mp4" in low:
                s += 8
            if any(k in low for k in ("auth_key", "token", "sign", "expire")):
                s += 2
            if "/ad" in low or "advert" in low:
                s -= 5
            return -s

        cands.sort(key=score)
        return cands

    # ==================== 通用工具 ====================
    def _fetch_html(self, url, params=None):
        full_url = url
        if params:
            full_url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        try:
            resp = self.fetch(full_url, headers=self.headers, timeout=15)
            if resp and hasattr(resp, "status_code") and resp.status_code == 200:
                return resp.text
            if resp and hasattr(resp, "text"):
                return resp.text
        except Exception:
            pass
        return ""

    def _pick_text(self, html, patterns):
        for pat in patterns:
            m = re.search(pat, html, re.S)
            if m:
                return m.group(1).strip()
        return ""

    def _clean_title(self, title):
        if not title:
            return ""
        title = re.sub(r"<[^>]+>", "", title)
        title = re.sub(r"[_\-\|].{0,30}$", "", title).strip()
        return title.strip()

    def _strip_html(self, text):
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&nbsp;", " ").replace("&amp;", "&")
        return text.strip()

    def destroy(self):
        pass
