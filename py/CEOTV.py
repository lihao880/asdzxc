# coding: utf-8
# CEOTV 爬虫
# 站点: https://ceotv1324.lol/
# 类型: MacCMS 标准影视站 (成人)
# 分类: 国产视频(1), 中文字幕(2), 国产传媒(3), 日本有码(4), 日本无码(5), 欧美无码(6), 强奸乱伦(7), 制服诱惑(8), 国产主播(9), 激情动漫(10), 明星换脸(11), 抖音视频(12), 女优明星(13), 网曝黑料(14), 伦理三级(15), AV解说(16), SM调教(17), 人妖系列(18)
# 分页: /index.php/vod/type/id/{tid}/page/{pg}.html
# 搜索: POST /index.php/vod/search.html
# 播放地址: 从 player_aaaa.url 提取
# 最后更新: 2026-09-09

import json
import re
from urllib.parse import urljoin, quote, unquote, urlparse

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://ceotv1324.lol"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "1", "type_name": "国产视频"},
            {"type_id": "2", "type_name": "中文字幕"},
            {"type_id": "3", "type_name": "国产传媒"},
            {"type_id": "4", "type_name": "日本有码"},
            {"type_id": "5", "type_name": "日本无码"},
            {"type_id": "6", "type_name": "欧美无码"},
            {"type_id": "7", "type_name": "强奸乱伦"},
            {"type_id": "8", "type_name": "制服诱惑"},
            {"type_id": "9", "type_name": "国产主播"},
            {"type_id": "10", "type_name": "激情动漫"},
            {"type_id": "11", "type_name": "明星换脸"},
            {"type_id": "12", "type_name": "抖音视频"},
            {"type_id": "13", "type_name": "女优明星"},
            {"type_id": "14", "type_name": "网曝黑料"},
            {"type_id": "15", "type_name": "伦理三级"},
            {"type_id": "16", "type_name": "AV解说"},
            {"type_id": "17", "type_name": "SM调教"},
            {"type_id": "18", "type_name": "人妖系列"},
        ]
        self.filters = {cid: [] for cid in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18"]}
        self.NEED_CLEAN = True
        self.ANCHOR = "/20260907/ugvkr4gd/2000kb/hls/"
        self.AD_DIRS = ["/20260830/i2vAQKIt/1000kb/hls/"]

    def getName(self):
        return "CEOTV"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self.categoryContent("1", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        html = r.text
        items = []
        pattern = r'<li class="col-25[^"]*"[^>]*>.*?<section class="item-box">.*?<a href="([^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>.*?<h2 class="f-15[^"]*"[^>]*>.*?<a[^>]+title="([^"]+)"[^>]*>([^<]+)</a>.*?</section>'
        for m in re.finditer(pattern, html, re.S):
            link = m.group(1).strip()
            pic = m.group(2).strip()
            title = m.group(4).strip()
            if not link or not title:
                continue
            vid_match = re.search(r'/id/(\d+)/', link)
            vod_id = vid_match.group(1) if vid_match else link
            items.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic if pic.startswith("http") else urljoin(self.host, pic),
                "vod_remarks": "",
            })
        pagecount = 1
        total = len(items)
        pager_match = re.search(r'共(\d+)页', html)
        if pager_match:
            pagecount = int(pager_match.group(1))
        else:
            page_links = re.findall(r'<a[^>]+href="[^"]*page/(\d+)\.html"[^>]*>', html)
            if page_links:
                pagecount = max([int(p) for p in page_links] + [int(page)])
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": total
        }

    def _norm_ids(self, ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}
        url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": [{"vod_id": vid, "vod_name": "未知标题", "vod_pic": "", "vod_remarks": "", "vod_content": "", "vod_play_from": "播放", "vod_play_url": f"播放${vid}"}]}
        html = r.text
        play_url = ""
        vod_name = ""
        # 提取 player_aaaa
        player_match = re.search(r'var player_aaaa\s*=\s*({.*?});', html, re.S)
        if player_match:
            try:
                # 完整JSON解析（自动处理Unicode转义）
                json_str = player_match.group(1).replace("\\/", "/")
                data = json.loads(json_str)
                play_url = data.get("url", "")
                # 从 vod_data 中提取标题
                vod_data = data.get("vod_data", {})
                if isinstance(vod_data, dict):
                    vod_name = vod_data.get("vod_name", "")
                if not vod_name:
                    vod_name = data.get("vod_name", "")
                if not vod_name:
                    vod_name = data.get("name", "") or data.get("title", "")
            except Exception:
                # 正则提取并手动解码
                name_match = re.search(r'"vod_name":"((?:[^"\\]|\\.)*)"', player_match.group(1))
                if name_match:
                    raw = name_match.group(1)
                    try:
                        vod_name = json.loads(f'"{raw}"')
                    except Exception:
                        vod_name = raw
                url_match = re.search(r'"url":"((?:[^"\\]|\\.)*)"', player_match.group(1))
                if url_match:
                    raw_url = url_match.group(1)
                    try:
                        play_url = json.loads(f'"{raw_url}"')
                    except Exception:
                        play_url = raw_url.replace("\\/", "/")
        # 从页面标题提取
        if not vod_name:
            title_match = re.search(r'<title>(.*?)</title>', html)
            if title_match:
                title = title_match.group(1).strip()
                title = re.sub(r'\s*[—\-|]\s*CEOTV.*$', '', title)
                title = re.sub(r'\s*详情介绍.*$', '', title)
                title = re.sub(r'\s*在线观看.*$', '', title)
                if title:
                    vod_name = title
        # 从h1提取
        if not vod_name:
            h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html)
            if h1_match:
                vod_name = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
                vod_name = re.sub(r'[~\-—]$', '', vod_name).strip()
        if play_url:
            proxy_url = self.getProxyUrl() + "?do=py&url=" + quote(play_url, safe="")
            return {
                "list": [{
                    "vod_id": vid,
                    "vod_name": vod_name or "视频",
                    "vod_pic": "",
                    "vod_remarks": "",
                    "vod_content": "",
                    "vod_play_from": "播放",
                    "vod_play_url": f"播放${proxy_url}",
                }]
            }
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": vod_name or "视频",
                "vod_pic": "",
                "vod_remarks": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${vid}",
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        page = pg or "1"
        url = f"{self.host}/index.php/vod/search.html"
        data = {"wd": key}
        r = self.post(url, data=data, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": [], "page": int(page)}
        html = r.text
        items = []
        pattern = r'<li class="col-25[^"]*"[^>]*>.*?<section class="item-box">.*?<a href="([^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>.*?<h2 class="f-15[^"]*"[^>]*>.*?<a[^>]+title="([^"]+)"[^>]*>([^<]+)</a>.*?</section>'
        for m in re.finditer(pattern, html, re.S):
            link = m.group(1).strip()
            pic = m.group(2).strip()
            title = m.group(4).strip()
            if not link or not title:
                continue
            vid_match = re.search(r'/id/(\d+)/', link)
            vod_id = vid_match.group(1) if vid_match else link
            items.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic if pic.startswith("http") else urljoin(self.host, pic),
                "vod_remarks": "",
            })
        return {"list": items, "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id or "").strip()
        if not play_url:
            return {"parse": 0, "url": "", "header": {}}
        if play_url.startswith("http://127.0.0.1:9978/proxy") or "do=py" in play_url:
            return {"parse": 0, "url": play_url, "header": {"User-Agent": self.headers["User-Agent"]}}
        if play_url.startswith("http") and ".m3u8" in play_url:
            proxy_url = self.getProxyUrl() + "?do=py&url=" + quote(play_url, safe="")
            return {"parse": 0, "url": proxy_url, "header": {"User-Agent": self.headers["User-Agent"]}}
        if re.match(r"^\d+$", play_url):
            detail_url = f"{self.host}/index.php/vod/play/id/{play_url}/sid/1/nid/1.html"
            r = self.fetch(detail_url, headers=self.headers, timeout=15)
            if r and r.status_code == 200:
                html = r.text
                player_match = re.search(r'var player_aaaa\s*=\s*({.*?});', html, re.S)
                if player_match:
                    try:
                        data = json.loads(player_match.group(1).replace("\\/", "/"))
                        real_url = data.get("url", "")
                        if real_url:
                            proxy_url = self.getProxyUrl() + "?do=py&url=" + quote(real_url, safe="")
                            return {"parse": 0, "url": proxy_url, "header": {"User-Agent": self.headers["User-Agent"]}}
                    except Exception:
                        pass
            return {"parse": 1, "url": detail_url, "header": self.headers}
        return {"parse": 1, "url": play_url, "header": self.headers}

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
            elif "url=" in target:
                qs = urlparse(target).query
                if "url" in qs:
                    target = qs.split("url=")[1].split("&")[0]
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

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"
        is_img = self._is_fake_image_stream(text, source_url)
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    if ".m3u8" in child.lower():
                        out.append(self.getProxyUrl() + "?do=py&url=" + quote(child, safe=""))
                    else:
                        out.append(child)
            return "\n".join(out) + "\n"
        main_dir = self._resolve_anchor(lines, source_url, is_image_stream=is_img)
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)
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

    def _resolve_anchor(self, lines, source_url, is_image_stream=False):
        import posixpath
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

    def recommendContent(self, ids, pg):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}
        url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": []}
        html = r.text
        items = []
        pattern = r'<a href="(/index.php/vod/play/id/(\d+)/sid/1/nid/1\.html)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>.*?<h2 class="f-15[^"]*"[^>]*>.*?<a[^>]+title="([^"]+)"[^>]*>'
        tab_match = re.search(r'<div class="home-tab mb10">.*?<div class="tab-bd">(.*?)</div>', html, re.S)
        if tab_match:
            tab_html = tab_match.group(1)
            for m in re.finditer(pattern, tab_html, re.S):
                link = m.group(1).strip()
                vod_id = m.group(2).strip()
                pic = m.group(3).strip()
                title = m.group(4).strip()
                if not link or not title:
                    continue
                items.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic if pic.startswith("http") else urljoin(self.host, pic),
                    "vod_remarks": "",
                })
                if len(items) >= 20:
                    break
        if not items:
            for m in re.finditer(pattern, html, re.S):
                link = m.group(1).strip()
                vod_id = m.group(2).strip()
                pic = m.group(3).strip()
                title = m.group(4).strip()
                if not link or not title:
                    continue
                if vod_id == vid:
                    continue
                items.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic if pic.startswith("http") else urljoin(self.host, pic),
                    "vod_remarks": "",
                })
                if len(items) >= 20:
                    break
        return {"list": items}

    def destroy(self):
        pass