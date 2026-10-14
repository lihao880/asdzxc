# coding: utf-8
# 青春水蜜桃 - 成人视频聚合站
# 站点: https://xn--cl0a.qingchunshuimitao.click/

import re
import json
import urllib.parse
import posixpath
from urllib.parse import quote, urljoin

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xn--cl0a.qingchunshuimitao.click"
        self.site_name = "青春水蜜桃"
        
        # 分类列表（数字ID → 显示名称）
        self.classes = [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "最新电影"},
            {"type_id": "3", "type_name": "热播电影"},
            {"type_id": "4", "type_name": "网红主播"},
            {"type_id": "5", "type_name": "SM重味"},
            {"type_id": "6", "type_name": "自拍偷拍"},
            {"type_id": "7", "type_name": "乱伦系列"},
            {"type_id": "8", "type_name": "无码视频"},
            {"type_id": "9", "type_name": "日本Av"},
            {"type_id": "10", "type_name": "会所技师"},
        ]
        
        # ID → URL路径 映射（完整路径，包含videos前缀）
        self.id_to_path = {
            "1": "videos",
            "2": "latest-videos",
            "3": "mostpopular-videos",
            "4": "videos/categories/wangbo",
            "5": "videos/categories/zhongweism",
            "6": "videos/categories/zipai",
            "7": "videos/categories/luanliao",
            "8": "videos/categories/wumaqu",
            "9": "videos/categories/criben",
            "10": "videos/categories/huisuojishi",
        }
        
        self.filters = {c["type_id"]: [] for c in self.classes}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }

    def getName(self):
        return self.site_name

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
        items = self._parse_video_list(html)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg) if pg else "1"
        tid = str(tid)
        
        # 根据数字ID获取URL路径
        path = self.id_to_path.get(tid)
        if not path:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}
        
        # 构建URL
        if pg == "1":
            url = f"{self.host}/{path}/"
        else:
            url = f"{self.host}/{path}/{pg}/"
        
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        page_count = self._parse_page_count(html)
        
        return {
            "list": items,
            "page": int(pg),
            "pagecount": page_count,
            "limit": 20,
            "total": page_count * 20,
        }

    def detailContent(self, ids):
        if not ids:
            self.log({"action": "detailContent", "msg": "ids is empty"})
            return {"list": []}
        
        if isinstance(ids, list):
            vid = str(ids[0]) if ids else ""
        else:
            vid = str(ids)
        
        self.log({"action": "detailContent", "vid": vid, "ids": str(ids)})
        
        if not vid or vid == "None":
            return {"list": []}
        
        id_match = re.search(r'(\d+)', vid)
        if not id_match:
            return {"list": []}
        video_id = id_match.group(1)
        
        url = f"{self.host}/video/{video_id}/"
        self.log({"action": "detailContent", "url": url})
        
        html = self._fetch_html(url)
        
        if not html:
            self.log({"action": "detailContent", "msg": "html is empty", "url": url})
            return {"list": []}
        
        title = self._extract_title(html) or f"视频{video_id}"
        pic = self._extract_poster(html) or ""
        play_url = self._extract_m3u8(html)
        category = self._extract_category(html) or ""
        views = self._extract_views(html) or ""
        
        self.log({"action": "detailContent", "title": title, "play_url": play_url})
        
        # 域名替换：fqm3u8.top -> fqm3u8.cc (备用)
        if play_url and "fqm3u8.top" in play_url:
            play_url = play_url.replace("fqm3u8.top", "fqm3u8.cc")
            self.log({"action": "detailContent", "msg": "domain replaced", "new_url": play_url})
        
        vod = {
            "vod_id": video_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": f"浏览:{views}" if views else "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": f"栏目: {category}" if category else "",
            "vod_play_from": "播放",
        }
        
        if play_url and play_url.startswith("http"):
            vod["vod_play_url"] = f"正片${play_url}"
        else:
            vod["vod_play_url"] = f"播放${url}"
        
        return {"list": [vod]}
    def searchContent(self, key, quick, pg="1"):
        pg = str(pg) if pg else "1"
        key = (key or "").strip()
        if not key:
            return {"list": []}
        
        url = f"{self.host}/search/?q={quote(key)}"
        if pg != "1":
            url = f"{self.host}/search/?q={quote(key)}&page={pg}"
        
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        if id and id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id),
                "header": {
                    "User-Agent": self.headers.get("User-Agent", ""),
                    "Referer": self.host + "/",
                }
            }
        if id and id.startswith("http") and "/video/" in id:
            html = self._fetch_html(id)
            play_url = self._extract_m3u8(html)
            if play_url:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(play_url),
                    "header": {
                        "User-Agent": self.headers.get("User-Agent", ""),
                        "Referer": self.host + "/",
                    }
                }
            return {"parse": 1, "url": id, "header": self.headers}
        if re.match(r'^\d+$', str(id)):
            url = f"{self.host}/video/{id}/"
            html = self._fetch_html(url)
            play_url = self._extract_m3u8(html)
            if play_url:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(play_url),
                    "header": {
                        "User-Agent": self.headers.get("User-Agent", ""),
                        "Referer": self.host + "/",
                    }
                }
            return {"parse": 1, "url": url, "header": self.headers}
        return {"parse": 1, "url": id, "header": self.headers}
    def recommendContent(self, ids, pg):
        """
        相关推荐接口 - 从详情页的"相关视频"中获取
        """
        if not ids:
            return {"list": []}
        
        # 兼容处理 ids 参数
        if isinstance(ids, list):
            vid = str(ids[0]) if ids else ""
        else:
            vid = str(ids)
        
        if not vid or vid == "None":
            return {"list": []}
        
        # 提取纯数字 ID
        id_match = re.search(r'(\d+)', vid)
        if not id_match:
            return {"list": []}
        video_id = id_match.group(1)
        
        # 请求详情页
        url = f"{self.host}/video/{video_id}/"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}
        
        # 定位相关推荐区域
        pattern = r'<div class="item">\s*<a href="([^"]+)"[^>]*>\s*<div class="img">\s*<img[^>]*src="([^"]+)"[^>]*>\s*<span class="ico-play"></span>.*?</div>\s*<strong class="title">([^<]+)</strong>\s*<div class="wrap">\s*<div class="duration">([^<]*)</div>.*?</div>\s*<div class="wrap">\s*<div class="added"><em>([^<]*)</em></div>\s*<div class="views">([^<]*)</div>\s*</div>\s*</a>\s*</div>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        items = []
        for link, pic, title, duration, added, views in matches:
            id_match2 = re.search(r'/video/(\d+)/', link)
            if not id_match2:
                continue
            vid2 = id_match2.group(1)
            # 排除当前视频
            if vid2 == video_id:
                continue
            # 补全图片地址
            if pic and not pic.startswith("http"):
                pic = self.host + pic
            items.append({
                "vod_id": vid2,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": duration.strip() or "0:00",
                "vod_play_from": "",
                "vod_play_url": "",
            })
            if len(items) >= 20:
                break
        
        return {"list": items}
    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
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

            # 域名替换：fqm3u8.top -> fqm3u8.cc (备用)
            if "fqm3u8.top" in target:
                target = target.replace("fqm3u8.top", "fqm3u8.cc")

            resp = self.fetch(target, headers=self.headers, timeout=15)
            if not resp:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")

            if not content:
                return [502, "text/plain", b"empty content"]

            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]
    def _clean_m3u8(self, text, source_url):
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"
        
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"
        
        parsed = urllib.parse.urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"
        
        main_dir = source_dir
        for line in lines:
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                uri_match = re.search(r'URI="([^"]+)"', line)
                if uri_match:
                    key_path = uri_match.group(1)
                    if not key_path.startswith("http"):
                        key_dir = posixpath.dirname(key_path)
                        if key_dir and key_dir != "/":
                            main_dir = key_dir + "/"
                            break
        
        segments = []
        pending = []
        removed = 0
        
        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urllib.parse.urljoin(source_url, line)
                media_parsed = urllib.parse.urlparse(media_url)
                is_ad = not media_parsed.path.startswith(main_dir)
                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                else:
                    removed += 1
                pending = []
                continue
            
            if not line.startswith("#"):
                segments.append(urllib.parse.urljoin(source_url, line))
            else:
                segments.append(line)
        
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)
        
        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()
        
        if removed:
            self.log({"action": "m3u8_ad_filter", "removed": removed})
        
        return "\n".join(out) + "\n"

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

    def _fetch_html(self, url, timeout=15):
        try:
            resp = self.fetch(url, headers=self.headers, timeout=timeout)
            if resp and hasattr(resp, "status_code") and resp.status_code == 200:
                return resp.text
            if resp and hasattr(resp, "text"):
                return resp.text
        except Exception:
            pass
        return ""

    def _parse_video_list(self, html):
        items = []
        if not html:
            return items
        
        pattern = r'<div class="item">\s*<a href="([^"]+)"[^>]*>\s*<div class="img">\s*<img[^>]*src="([^"]+)"[^>]*>\s*<span class="ico-play"></span>.*?</div>\s*<strong class="title">([^<]+)</strong>\s*<div class="wrap">\s*<div class="duration">([^<]*)</div>.*?</div>\s*<div class="wrap">\s*<div class="added"><em>([^<]*)</em></div>\s*<div class="views">([^<]*)</div>\s*</div>\s*</a>\s*</div>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for link, pic, title, duration, added, views in matches:
            id_match = re.search(r'/video/(\d+)/', link)
            if not id_match:
                continue
            vid = id_match.group(1)
            title = title.strip()
            pic = pic.strip()
            if pic and not pic.startswith("http"):
                pic = self.host + pic
            
            items.append({
                "vod_id": vid,
                "vod_name": title or f"视频{vid}",
                "vod_pic": pic,
                "vod_remarks": duration.strip() or "0:00",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "",
                "vod_play_url": "",
            })
        
        return items

    def _parse_page_count(self, html):
        if not html:
            return 1
        pattern = r'<li class="page"><a[^>]*href="[^"]*/(\d+)/"[^>]*>(\d+)</a></li>'
        matches = re.findall(pattern, html)
        if matches:
            pages = [int(m[1]) for m in matches if m[1].isdigit()]
            if pages:
                return max(pages) + 1
        last_match = re.search(r'<li class="last"><a[^>]*href="[^"]*/(\d+)/"', html)
        if last_match:
            return int(last_match.group(1))
        return 1

    def _extract_m3u8(self, html):
        if not html:
            return None
        pattern = r'var\s+videoObject\s*=\s*\{[^}]*video:\s*\{\s*url:\s*[\'"]?([^\'"]+\.m3u8[^\'"]*)[\'"]?'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            url = match.group(1).strip()
            if url.startswith("http"):
                return url
        pattern2 = r'video_url:\s*[\'"]?([^\'"]+\.m3u8[^\'"]*)[\'"]?'
        match2 = re.search(pattern2, html)
        if match2:
            url = match2.group(1).strip()
            if url.startswith("http"):
                return url
        pattern3 = r'https?://[^"\']+\.m3u8[^"\']*'
        match3 = re.search(pattern3, html)
        if match3:
            return match3.group(0)
        return None

    def _extract_title(self, html):
        if not html:
            return None
        match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if match:
            return match.group(1).strip()
        return None

    def _extract_poster(self, html):
        if not html:
            return None
        match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if match:
            return match.group(1)
        match = re.search(r'pic:\s*[\'"]?([^\'"]+)[\'"]?', html)
        if match:
            return match.group(1)
        return None

    def _extract_category(self, html):
        if not html:
            return None
        match = re.search(r'<a[^>]*href="[^"]*/videos/categories/[^"]*/"[^>]*>([^<]+)</a>', html)
        if match:
            return match.group(1).strip()
        return None

    def _extract_views(self, html):
        if not html:
            return None
        match = re.search(r'<div[^>]*class="views"[^>]*>\s*([^<]+)\s*</div>', html)
        if match:
            return match.group(1).strip()
        return None

    def destroy(self):
        pass