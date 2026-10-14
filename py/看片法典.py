# coding: utf-8
import re
import json
import urllib.parse
import posixpath
from urllib.parse import urljoin, urlparse, quote, unquote

from base.spider import Spider as BaseSpider

"""
站点信息沉淀（法则24）
主域名: https://www.kpfd9.lat
备用域名: 暂无（发布页: https://udz.avztc1.com/c/）
内容类型: 成人视频
特殊说明: MacCMS标准影视站，HTML解析，m3u8广告过滤
最后验证时间: 2026-09-01
"""

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.kpfd9.lat"
        self.base_url = self.host + "/cn/home/web/index.php"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "20", "type_name": "自拍偷拍"},
            {"type_id": "21", "type_name": "巨乳波霸"},
            {"type_id": "22", "type_name": "强奸乱伦"},
            {"type_id": "23", "type_name": "人妻熟女"},
            {"type_id": "24", "type_name": "制服丝袜"},
            {"type_id": "25", "type_name": "花季少女"},
            {"type_id": "26", "type_name": "无码露毛"},
            {"type_id": "27", "type_name": "群P多人"},
            {"type_id": "28", "type_name": "人兽人妖"},
            {"type_id": "29", "type_name": "男同女同"},
            {"type_id": "30", "type_name": "韩日专区"},
            {"type_id": "31", "type_name": "欧美色情"},
            {"type_id": "32", "type_name": "成人动漫"},
            {"type_id": "33", "type_name": "三级剧情"},
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}

    def getName(self):
        return "看片法典"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        url = self.base_url + "/vod/type/id/20/page/1.html"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            return self._parse_video_list(html, url)
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.base_url}/vod/type/id/{tid}/page/{page}.html"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = resp.text
            result = self._parse_video_list(html, url)
            pagecount = self._parse_total_pages(html)
            return {
                "list": result.get("list", []),
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": 0,
            }
        except Exception:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def _parse_video_list(self, html, url):
        videos = []
        pattern = r'<div class="video-play[^"]*">.*?<a href="([^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*/>.*?<p class="title-p"><a[^>]+>(.*?)</a></p>.*?<p class="time">.*?发布</i>([^<]+).*?观看</i>(\d+)'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            try:
                link, pic, title, date, views = match
                vid_match = re.search(r'/vod/play/id/(\d+)/', link)
                if not vid_match:
                    continue
                vod_id = link
                title = self._clean_html(title)
                remark = f"{date.strip()} 观看{views}"
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": urljoin(url, pic) if pic else "",
                    "vod_remarks": remark,
                })
            except Exception:
                continue
        return {"list": videos}

    def _clean_html(self, text):
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _parse_total_pages(self, html):
        tail_match = re.search(r'<a[^>]+href="[^"]*/page/(\d+)\.html"[^>]*>尾页</a>', html)
        if tail_match:
            return int(tail_match.group(1))
        page_matches = re.findall(r'<a[^>]+href="[^"]*/page/(\d+)\.html"', html)
        max_page = 1
        for p in page_matches:
            try:
                if int(p) > max_page:
                    max_page = int(p)
            except:
                pass
        return max_page

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        raw = str(ids[0])
        if raw.startswith("/") or raw.startswith("http"):
            play_url = raw if raw.startswith("http") else urljoin(self.host, raw)
            vid_match = re.search(r'/vod/play/id/(\d+)/', raw)
            vod_id = vid_match.group(1) if vid_match else raw
        else:
            vod_id = raw
            play_url = f"{self.base_url}/vod/play/id/{vod_id}/sid/1/nid/1.html"
        
        title = "视频"
        pic = ""
        try:
            resp = self.fetch(play_url, headers=self.headers, timeout=10)
            if resp and resp.status_code == 200:
                html = resp.text
                title_match = re.search(r'<title>(.*?)</title>', html)
                if title_match:
                    title = title_match.group(1).replace(" - 看片法典", "").strip()
                pic_match = re.search(r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*play-btn[^"]*"', html)
                if pic_match:
                    pic = urljoin(play_url, pic_match.group(1))
        except Exception:
            pass

        vod = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}",
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        url = f"{self.base_url}/vod/search.html"
        data = {"wd": key}
        try:
            resp = self.post(url, data=data, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": 1}
            html = resp.text
            result = self._parse_video_list(html, url)
            return {"list": result.get("list", []), "page": int(pg)}
        except Exception:
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        if id.startswith("http") and ".m3u8" in id.lower():
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id),
                "header": {"User-Agent": self.headers.get("User-Agent", "")},
            }
        try:
            resp = self.fetch(id, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"parse": 1, "url": id, "header": self.headers}
            html = resp.text
            match = re.search(r'var player_data=({.*?})</script>', html, re.DOTALL)
            if not match:
                return {"parse": 1, "url": id, "header": self.headers}
            data = json.loads(match.group(1))
            m3u8_url = data.get("url", "")
            if m3u8_url and ".m3u8" in m3u8_url.lower():
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(m3u8_url),
                    "header": {"User-Agent": self.headers.get("User-Agent", "")},
                }
            if m3u8_url:
                return {"parse": 0, "url": m3u8_url, "header": {"User-Agent": self.headers.get("User-Agent", "")}}
            return {"parse": 1, "url": id, "header": self.headers}
        except Exception:
            return {"parse": 1, "url": id, "header": self.headers}

    def _m3u8_proxy_url(self, url):
        if not url:
            return ""
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url), safe="")

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target and "do=py" in target:
                qs = self._parse_qs(target)
                if "url" in qs:
                    target = qs["url"][0]
            target = unquote(str(target or ""))
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp or resp.status_code != 200:
                return [502, "text/plain", b"fetch failed"]
            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]

            if b"#EXTM3U" not in content[:256]:
                return [200, "application/octet-stream", content]

            text = content.decode("utf-8", errors="ignore")
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]

    def _parse_qs(self, url):
        result = {}
        if "?" in url:
            qs = url.split("?", 1)[1]
            for item in qs.split("&"):
                if "=" in item:
                    k, v = item.split("=", 1)
                    result[k] = [unquote(v)]
        return result

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 第1层：图片流伪装检测（命中后只还原扩展名并立即返回，禁止进入后续过滤）
        is_png_stream = False
        if source_url:
            low_source = source_url.lower()
            if 'doyinapi' in low_source or 'svip' in low_source or 'imgcdn' in low_source:
                is_png_stream = True
        if not is_png_stream:
            for line in lines:
                if '.png' in line.lower() or '.jpg' in line.lower() or '.jpeg' in line.lower() or '.webp' in line.lower():
                    is_png_stream = True
                    break

        if is_png_stream:
            # 图片流站点的分片天生不在 m3u8/KEY 目录下，一旦走目录前缀法会把正片全部误杀。
            # 因此这里只做两件事：还原扩展名 + 补全绝对地址，然后立即 return。
            # 严禁在此之后执行第3层锚点判定与第4层目录过滤。
            text = text.replace(".jpeg", ".ts").replace(".jpg", ".ts").replace(".png", ".ts").replace(".webp", ".ts")
            lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
            if not lines:
                return "#EXTM3U\n"
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            seg_count = sum(1 for l in out if l and not l.startswith("#"))
            self.log(f"检测到图片流伪装，已还原扩展名 -> .ts，跳过广告过滤，分片: {seg_count}个")
            return "\n".join(out) + "\n"

        # 第2层：多码率主表透传
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

        # 第3层：正片目录锚点（使用最后一个KEY URI目录）
        parsed = urllib.parse.urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

        main_dir = source_dir
        for line in lines:
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                m = re.search(r'URI="([^"]+)"', line)
                if m:
                    key_uri = m.group(1)
                    key_path = urllib.parse.urlparse(
                        key_uri if key_uri.startswith("http") else urllib.parse.urljoin(source_url, key_uri)
                    ).path
                    key_dir = posixpath.dirname(key_path)
                    if key_dir and key_dir != "/":
                        main_dir = key_dir + "/"

        self.log(f"正片锚点目录: {main_dir}")

        # 第4层：分片过滤
        segments = []
        pending = []
        removed = 0
        kept = 0

        for line in lines:
            if line.startswith("#EXT-X-KEY"):
                segments.append(self._rewrite_m3u8_tag(line, source_url))
                continue
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urllib.parse.urljoin(source_url, line)
                media_parsed = urllib.parse.urlparse(media_url)
                if media_parsed.path.startswith(main_dir):
                    for p in pending:
                        if p.startswith("#EXTINF"):
                            segments.append(p)
                        else:
                            segments.append(self._rewrite_m3u8_tag(p, source_url))
                    segments.append(media_url)
                    kept += 1
                else:
                    removed += 1
                pending = []
                continue
            if not line.startswith("#"):
                segments.append(urllib.parse.urljoin(source_url, line))
            else:
                segments.append(line)

        # 第5层：全滤兜底 + 高误杀率保护
        if removed > 0 and (kept == 0 or removed > kept):
            self.log(f"广告过滤命中过多分片(滤{removed}/留{kept})，判定锚点失效，回退为不过滤模式")
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")

        # 冗余标签清理
        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"
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
            def repl(m):
                uri = m.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urllib.parse.urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urllib.parse.urljoin(source_url, line)
        return line

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass