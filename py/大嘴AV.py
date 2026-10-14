# coding: utf-8
"""
大嘴AV - TVBox爬虫源
站点：https://www.dzav3.skin
类型：MacCMS标准站（HTML）
优化：增强 m3u8 广告分片过滤（参考 wangshi_ribao.py）
"""

import re
import json
import urllib.parse
import posixpath
from urllib.parse import urljoin, quote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.dzav3.skin"
        self.base_path = "/cn/home/web"
        self.site_name = "大嘴AV"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.classes = [
            {"type_id": "20", "type_name": "亚洲情色"},
            {"type_id": "21", "type_name": "制服师生"},
            {"type_id": "22", "type_name": "卡通动漫"},
            {"type_id": "23", "type_name": "丝袜美腿"},
            {"type_id": "24", "type_name": "强奸乱伦"},
            {"type_id": "25", "type_name": "偷拍自拍"},
            {"type_id": "29", "type_name": "人妻熟女"},
            {"type_id": "30", "type_name": "无码专区"},
            {"type_id": "32", "type_name": "自淫系列"},
            {"type_id": "36", "type_name": "国产精品"},
            {"type_id": "33", "type_name": "拳交系列"},
            {"type_id": "28", "type_name": "欧美性爱"},
            {"type_id": "31", "type_name": "SM捆绑"},
            {"type_id": "35", "type_name": "男同女同"},
            {"type_id": "26", "type_name": "4K岛国"},
            {"type_id": "27", "type_name": "中文字幕"},
            {"type_id": "37", "type_name": "三级伦理"},
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}
        self._cached_host = None

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
        url = urljoin(self.host, self.base_path + "/")
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}{self.base_path}/index.php/vod/type/id/{tid}/page/{page}.html"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        page_count = self._parse_page_count(html)
        return {
            "list": items,
            "page": int(page),
            "pagecount": page_count,
            "limit": 20,
            "total": page_count * 20,
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        url = f"{self.host}{self.base_path}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        html = self._fetch_html(url)

        title = self._extract_title(html)
        play_url = self._extract_play_url(html)

        vod = {
            "vod_id": vid,
            "vod_name": title or f"视频{vid}",
            "vod_pic": "",
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}" if play_url else f"播放${url}",
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        url = f"{self.host}{self.base_path}/index.php/vod/search.html"
        data = {"wd": key}
        html = self._fetch_html(url, method="POST", data=data)
        items = self._parse_video_list(html)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        """播放 - 走代理过滤广告"""
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        id = str(id).strip()

        # 如果id是m3u8地址，走代理过滤广告
        if '.m3u8' in id and id.startswith('http'):
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id),
                "header": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.dzav3.skin/",
                }
            }

        # 如果id是详情页URL
        if id.startswith('http'):
            vid_match = re.search(r'/id/(\d+)/', id)
            if vid_match:
                vid = vid_match.group(1)
            else:
                num_match = re.search(r'/(\d+)(?:\.html)?$', id)
                vid = num_match.group(1) if num_match else id
            url = id
        else:
            vid = id
            url = f"{self.host}{self.base_path}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"

        html = self._fetch_html(url)
        play_url = self._extract_play_url(html)

        if play_url:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(play_url),
                "header": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.dzav3.skin/",
                }
            }
        else:
            return {"parse": 1, "url": url, "header": self.headers}
    def recommendContent(self, ids, pg):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        url = f"{self.host}{self.base_path}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        html = self._fetch_html(url)

        pattern = r'<div[^>]*class="video-related"[^>]*>.*?<div[^>]*class="video-list"[^>]*>(.*?)</div>\s*</div>'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            items = self._parse_video_list(match.group(1))
            return {"list": items[:12]}
        return {"list": []}

    def destroy(self):
        pass

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def _fetch_html(self, url, method="GET", data=None):
        try:
            if method.upper() == "POST" and data:
                resp = self.post(url, data=data, headers=self.headers, timeout=15)
            else:
                resp = self.fetch(url, headers=self.headers, timeout=15)
            
            if resp is None:
                return ""
            
            if hasattr(resp, "text"):
                return resp.text
            elif hasattr(resp, "content"):
                return resp.content.decode("utf-8", errors="ignore")
            return ""
        except Exception:
            return ""

    def _parse_video_list(self, html):
        items = []
        if not html:
            return items

        pattern = r'<div[^>]*class="video-item"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<div[^>]*class="title"[^>]*>([^<]+)</div>'
        matches = re.findall(pattern, html, re.DOTALL)

        for link, pic, title in matches:
            vid_match = re.search(r'/id/(\d+)/', link)
            if vid_match:
                vid = vid_match.group(1)
                items.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return items

    def _parse_page_count(self, html):
        if not html:
            return 1
        match = re.search(r'(\d+)\s*/\s*(\d+)', html)
        if match:
            return int(match.group(2))
        return 1

    def _extract_title(self, html):
        if not html:
            return ""
        match = re.search(r'<div[^>]*class="playName"[^>]*>.*?<p[^>]*class="name"[^>]*>([^<]+)</p>', html, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r'<title>([^<]+)</title>', html)
        if match:
            title = match.group(1)
            title = re.sub(r'\s*[-|]\s*大嘴AV\s*$', '', title)
            return title.strip()
        return ""

    def _extract_play_url(self, html):
        if not html:
            return None

        match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
        if match:
            url = match.group(1)
            url = url.replace("\\/", "/")
            if url.startswith("http"):
                return url

        match = re.search(r'var\s+player_data\s*=\s*({[^;]+});', html, re.DOTALL)
        if match:
            try:
                js_obj = match.group(1)
                js_obj = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', js_obj)
                data = json.loads(js_obj)
                url = data.get("url", "")
                if url:
                    url = url.replace("\\/", "/")
                if url and url.startswith("http") and ".m3u8" in url:
                    return url
            except Exception:
                pass

        match = re.search(r'https?://[^"\']+\.m3u8[^"\']*', html)
        if match:
            url = match.group(0)
            url = url.replace("\\/", "/")
            return url

        return None

    def localProxy(self, param):
        """
        m3u8本地代理 - 补全相对路径 + 广告分片过滤
        """
        try:
            target = ""
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "") or param.get("do", "")
            elif isinstance(param, str):
                target = param
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            elif target.startswith("do=py&url="):
                target = target[9:]

            target = urllib.parse.unquote(str(target or ""))

            if not target and isinstance(param, dict):
                for key in ["url", "source", "u", "target"]:
                    if key in param and param[key]:
                        target = urllib.parse.unquote(str(param[key]))
                        break

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.dzav3.skin/",
                "Accept": "*/*",
            }

            resp = self.fetch(target, headers=headers, timeout=20)
            if not resp:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")

            if not content:
                return [502, "text/plain", b"empty content"]

            # 检测 m3u8 并调用广告过滤
            if b"#EXTM3U" in content[:256]:
                text = content.decode("utf-8", errors="ignore")
                cleaned = self._clean_m3u8(text, target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

            # 非 m3u8 直接返回
            content_type = "application/octet-stream"
            if target.endswith(".ts"):
                content_type = "video/mp2t"
            elif target.endswith(".m3u8"):
                content_type = "application/vnd.apple.mpegurl"
            elif target.endswith(".png") or target.endswith(".jpg"):
                content_type = "image/jpeg"
            elif target.endswith(".mp4"):
                content_type = "video/mp4"
            elif target.endswith(".key") or target.endswith(".bin"):
                content_type = "application/octet-stream"

            return [200, content_type, content]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]
    def _clean_m3u8(self, text, source_url):
        """
        清洗 m3u8：自动过滤广告分片（参考 wangshi_ribao.py）
        策略：从 #EXT-X-KEY 提取正片目录，分片路径不匹配正片目录则视为广告
        """
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 检测是否为多码率 Master Playlist
        is_multi = any(line.startswith("#EXT-X-STREAM-INF") for line in lines)

        if is_multi:
            return self._clean_m3u8_multi(lines, source_url)
        else:
            return self._clean_m3u8_single(lines, source_url)

    def _clean_m3u8_multi(self, lines, source_url):
        """多码率播放列表 - 完全透传，不做修改（子流会再次进入localProxy过滤）"""
        out = []
        for line in lines:
            if line.startswith("#"):
                out.append(line)
            else:
                # 补全绝对路径，但不过滤
                child_url = urllib.parse.urljoin(source_url, line)
                # 让子流走代理（子流请求会再次进入localProxy）
                out.append(self._m3u8_proxy_url(child_url))
        return "\n".join(out) + "\n"
    def _clean_m3u8_single(self, lines, source_url):
        """单码率播放列表过滤 - 只过滤明确的广告目录"""
        segments = []
        pending = []
        removed = 0

        # 广告目录列表
        ad_dirs = ['UTe7qSJd', 'a3712cbfc6902686', '48a95b6cc2e944fa']
        # 正片目录（从 #EXT-X-KEY 提取）
        main_dir = None

        # 先扫描找正片目录
        for line in lines:
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                uri_match = re.search(r'URI="([^"]+)"', line)
                if uri_match:
                    key_path = uri_match.group(1)
                    # 提取路径中的目录
                    if '/' in key_path:
                        parts = key_path.split('/')
                        for part in parts:
                            if len(part) >= 10 and not any(kw in part for kw in ['key', 'hls', '']):
                                main_dir = part
                                break
                    break

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urllib.parse.urljoin(source_url, line)
                # 检查是否为广告
                is_ad = False
                for ad_dir in ad_dirs:
                    if ad_dir in media_url:
                        is_ad = True
                        break
                # 如果有正片目录，且分片包含正片目录，则不是广告
                if main_dir and main_dir in media_url:
                    is_ad = False

                if is_ad:
                    removed += 1
                    pending = []
                    continue

                segments.extend(pending)
                if media_url.endswith('.jpg'):
                    media_url = media_url[:-4] + '.ts'
                segments.append(media_url)
                pending = []
                continue

            if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
                line = self._rewrite_m3u8_tag(line, source_url)
            segments.append(line)

        if removed:
            self.log(f"大嘴AV m3u8已过滤广告分片: {removed}个")

        # 清理冗余标记
        out = []
        for line in segments:
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        return "\n".join(out) + "\n"
    def _is_ad_stream(self, url):
        """判断子流是否为广告流"""
        if not url:
            return True
        url_lower = url.lower()
        ad_patterns = [
            r'ad[s]?[-_/]',
            r'preroll',
            r'midroll',
            r'postroll',
            r'advertisement',
            r'sponsor',
            r'promotion',
            r'片头',
            r'片尾',
            r'ad_',
            r'-ad',
            r'/ad/',
            r'/ads/',
        ]
        for pattern in ad_patterns:
            if re.search(pattern, url_lower):
                return True
        return False

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写 m3u8 标签中的 URI（补全绝对地址）"""
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