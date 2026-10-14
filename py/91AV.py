# coding: utf-8
"""
站点信息：
- 主域名：https://91avsp9.cc
- 备用域名：https://xxvv1.tw (国内), https://91avsp9.cc (海外)
- 内容类型：成人影视
- 说明：标准HTML影视站，无API，播放地址从页面 __ARCHIVE_PLAYER__ 提取
- 最后验证时间：2026-08-31
"""

import re
import json
from urllib.parse import urljoin, urlparse, quote, unquote
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://91avsp9.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "cate5", "type_name": "爱豆"},
            {"type_id": "cate6", "type_name": "天美"},
            {"type_id": "cate7", "type_name": "起点"},
            {"type_id": "cate8", "type_name": "星空"},
            {"type_id": "cate9", "type_name": "蜜桃"},
            {"type_id": "cate10", "type_name": "萝莉社"},
            {"type_id": "cate11", "type_name": "精东"},
            {"type_id": "cate12", "type_name": "皇家"},
            {"type_id": "cate13", "type_name": "扣扣"},
            {"type_id": "cate14", "type_name": "果冻"},
            {"type_id": "cate15", "type_name": "黑料六点半"},
            {"type_id": "cate16", "type_name": "三级片"},
            {"type_id": "cate17", "type_name": "每日大赛"},
            {"type_id": "cate21", "type_name": "精品推荐"},
            {"type_id": "cate37", "type_name": "日韩AV"},
            {"type_id": "cate43", "type_name": "欧美色情"},
        ]
        self.filters = {}
        for c in self.classes:
            self.filters[c["type_id"]] = []

    def getName(self):
        return "91av视频"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 直接请求首页解析推荐列表
        res = self.fetch(self.host + "/", headers=self.headers, timeout=10)
        if not res:
            return {"list": []}
        html = res.text
        items = self._parse_video_list(html)
        return {"list": items}

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg) if pg and pg != "1" else ""
        if page:
            url = f"{self.host}/category/{tid}/{page}/"
        else:
            url = f"{self.host}/category/{tid}/"
        res = self.fetch(url, headers=self.headers, timeout=10)
        if not res:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        html = res.text
        items = self._parse_video_list(html)
        pagecount = self._parse_pagecount(html)
        return {
            "list": items,
            "page": int(page) if page else 1,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20
        }

    def detailContent(self, ids):
        vod_id = str(ids[0])
        url = f"{self.host}/video/{vod_id}/"
        res = self.fetch(url, headers=self.headers, timeout=10)
        if not res:
            return {"list": []}
        html = res.text
        title = self._parse_title(html)
        pic = self._parse_poster(html)
        play_url = self._parse_play_url(html)
        if play_url:
            play_url = self._m3u8_proxy_url(play_url)
        vod = {
            "vod_id": vod_id,
            "vod_name": title or "视频",
            "vod_pic": pic or "",
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}" if play_url else ""
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = str(pg) if pg and pg != "1" else ""
        if page:
            url = f"{self.host}/search/{key}/{page}/"
        else:
            url = f"{self.host}/search/{key}/"
        res = self.fetch(url, headers=self.headers, timeout=10)
        if not res:
            return {"list": [], "page": 1}
        html = res.text
        items = self._parse_video_list(html)
        return {"list": items, "page": int(page) if page else 1}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        # 如果是完整URL直接返回
        if id.startswith("http"):
            if ".m3u8" in id:
                return {
                    "parse": 0,
                    "url": id,
                    "header": {"User-Agent": self.headers["User-Agent"]}
                }
            # mp4直链
            return {
                "parse": 0,
                "url": id,
                "header": {"User-Agent": self.headers["User-Agent"]}
            }
        # 否则按ID处理
        if id.startswith("proxy://"):
            return {
                "parse": 0,
                "url": self.getProxyUrl() + "?target=" + quote(id),
                "header": self.headers
            }
        # 尝试直接作为播放地址
        return {"parse": 1, "url": id, "header": self.headers}

    def recommendContent(self, ids, pg):
        # 直接从详情页解析相关推荐
        vod_id = str(ids[0]) if ids else ""
        if not vod_id:
            return {"list": []}
        url = f"{self.host}/video/{vod_id}/"
        res = self.fetch(url, headers=self.headers, timeout=10)
        if not res:
            return {"list": []}
        html = res.text
        items = self._parse_recommend(html)
        return {"list": items}

    def destroy(self):
        pass

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy?do=py"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "&url=" + quote(str(url or ""), safe="")

    def _parse_video_list(self, html):
        items = []
        # 匹配视频卡片
        pattern = r'<a\s+[^>]*href="/video/(\d+)/"[^>]*>.*?<img[^>]*data-src="([^"]+)"[^>]*>.*?<h3[^>]*>([^<]*)</h3>.*?<span[^>]*>([^<]*)</span>.*?</a>'
        # 更健壮的方式：按li解析
        li_pattern = r'<li[^>]*class="[^"]*tp4-section-content__item[^"]*"[^>]*>.*?</li>'
        li_matches = re.findall(li_pattern, html, re.DOTALL)
        for li in li_matches:
            # 提取视频ID
            id_match = re.search(r'href="/video/(\d+)/"', li)
            if not id_match:
                continue
            vod_id = id_match.group(1)
            # 提取封面
            pic_match = re.search(r'data-src="([^"]+)"', li)
            pic = pic_match.group(1) if pic_match else ""
            # 提取标题
            title_match = re.search(r'<h3[^>]*>([^<]*)</h3>', li)
            title = title_match.group(1).strip() if title_match else ""
            # 提取时长/角标
            remark_match = re.search(r'<span[^>]*class="[^"]*tp4-duration[^"]*"[^>]*>([^<]*)</span>', li)
            remark = remark_match.group(1).strip() if remark_match else ""
            if not vod_id or not title:
                continue
            items.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark
            })
        return items

    def _parse_pagecount(self, html):
        # 解析分页总数
        # 匹配 "共 X 页" 或分页链接
        match = re.search(r'共\s*(\d+)\s*页', html)
        if match:
            return int(match.group(1))
        # 从分页链接中找最大页码
        page_links = re.findall(r'href="[^"]*/category/[^/"]+/(\d+)/"', html)
        if page_links:
            return max(int(p) for p in page_links)
        return 1

    def _parse_title(self, html):
        match = re.search(r'<h1[^>]*>([^<]*)</h1>', html)
        if match:
            return match.group(1).strip()
        # 从og:title
        match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
        if match:
            return match.group(1).strip()
        return ""

    def _parse_poster(self, html):
        match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if match:
            return match.group(1).strip()
        return ""

    def _parse_play_url(self, html):
        # 从 __ARCHIVE_PLAYER__ 提取播放地址
        match = re.search(r'window\.__ARCHIVE_PLAYER__\s*=\s*({[^}]+})', html)
        if match:
            try:
                data = json.loads(match.group(1))
                cdn = data.get("cdnLine", "")
                raw = data.get("rawPath", "")
                if cdn and raw:
                    return urljoin(cdn, raw)
                if raw:
                    return urljoin(self.host, raw)
            except:
                pass
        # 尝试直接匹配m3u8链接
        match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
        if match:
            return match.group(0)
        return ""

    def _parse_recommend(self, html):
        items = []
        # 从右侧推荐区域提取
        right_pattern = r'<article[^>]*class="[^"]*tp4-detail-right-content[^"]*"[^>]*>(.*?)</article>'
        right_match = re.search(right_pattern, html, re.DOTALL)
        if right_match:
            content = right_match.group(1)
            # 提取推荐项
            item_pattern = r'<a[^>]*href="/video/(\d+)/"[^>]*>.*?<img[^>]*data-src="([^"]+)"[^>]*>.*?<h4[^>]*>([^<]*)</h4>'
            for m in re.finditer(item_pattern, content, re.DOTALL):
                vod_id = m.group(1)
                pic = m.group(2)
                title = m.group(3).strip()
                if vod_id and title:
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": ""
                    })
        return items

    def localProxy(self, param):
        """m3u8代理 - 清洗广告分片"""
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                qs = urlparse(target).query
                params = {}
                for p in qs.split("&"):
                    if "=" in p:
                        k, v = p.split("=", 1)
                        params[k] = v
                if "url" in params:
                    target = params["url"]
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
            self.log(f"localProxy error: {e}")
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]

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

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        if self._is_fake_image_stream(text, source_url):
            restored = text
            for ext in (".png", ".jpeg", ".jpg", ".webp"):
                restored = restored.replace(ext, ".ts")
            self.log("检测到图片流伪装，已还原扩展名 -> .ts，跳过广告过滤")
            return restored

        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
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

        main_dir = self._resolve_main_dir(lines, source_url)
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        if kept == 0 and removed > 0:
            self.log("广告过滤命中全部分片，判定锚点失效，回退为不过滤模式")
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")

        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"