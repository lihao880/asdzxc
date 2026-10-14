# coding: utf-8
# 站点: 人人射 (rrs.renrenshe9.life)
# 类型: MacCMS HTML影视站
# 支持: m3u8 广告过滤 (localProxy)

import re
import json
import posixpath
import urllib.parse
from urllib.parse import quote, unquote, urljoin

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://rrs.renrenshe9.life"
        self.path = "/rrs"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.host + "/rrs/"
        }
        self.classes = [
            {"type_id": "2", "type_name": "国产精选"},
            {"type_id": "3", "type_name": "日本无码"},
            {"type_id": "4", "type_name": "日韩精品"},
            {"type_id": "5", "type_name": "乱伦合集"},
            {"type_id": "6", "type_name": "网曝吃瓜"},
            {"type_id": "7", "type_name": "探花寻花"},
            {"type_id": "8", "type_name": "网红主播"},
            {"type_id": "9", "type_name": "传媒片商"}
        ]
        self.filters = {}

    def getName(self):
        return "人人射"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址"""
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            url = f"{self.host}{self.path}/"
            res = self.fetch(url, headers=self.headers)
            if not res or res.status_code != 200:
                return {"list": []}
            html = res.text
            items = self._parse_list_from_html(html)
            return {"list": items[:20]}
        except Exception as e:
            self.log("homeVideoContent error: " + str(e))
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = pg or "1"
            url = f"{self.host}{self.path}/index.php/vod/type/id/{tid}/page/{page}.html"
            res = self.fetch(url, headers=self.headers)
            if not res or res.status_code != 200:
                return {"list": [], "page": int(page), "pagecount": 0, "limit": 20, "total": 0}
            html = res.text
            items = self._parse_list_from_html(html)
            pagecount = self._parse_pagecount_from_html(html)
            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount or 100,
                "limit": 20,
                "total": 0
            }
        except Exception as e:
            self.log("categoryContent error: " + str(e))
            return {"list": [], "page": int(pg or "1"), "pagecount": 0, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            if not ids:
                return {"list": []}
            if isinstance(ids, list):
                vid = ids[0] if ids else ""
            else:
                vid = ids
            if not vid:
                return {"list": []}

            parts = vid.split('|$|')
            vod_id = parts[0] if len(parts) > 0 else vid
            vod_name = parts[1] if len(parts) > 1 else "视频"
            vod_pic = parts[2] if len(parts) > 2 else ""
            vod_remark = parts[3] if len(parts) > 3 else ""

            detail_url = f"{self.host}{self.path}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
            res = self.fetch(detail_url, headers=self.headers)
            if not res or res.status_code != 200:
                return {"list": [{
                    "vod_id": vid,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remark,
                    "vod_content": "",
                    "vod_play_from": "播放",
                    "vod_play_url": f"播放${detail_url}"
                }]}

            html = res.text
            play_url = self._extract_play_url_from_html(html)
            if play_url:
                play_url = play_url.replace('\\/', '/')
                vod_play_from = "线路1"
                vod_play_url = f"播放${play_url}"
            else:
                vod_play_from = "播放"
                vod_play_url = f"播放${detail_url}"

            return {"list": [{
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remark,
                "vod_content": "",
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url
            }]}
        except Exception as e:
            self.log("detailContent error: " + str(e))
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            page = pg or "1"
            keyword = quote(key)
            url = f"{self.host}{self.path}/index.php/vod/search/page/{page}/wd/{keyword}.html"
            res = self.fetch(url, headers=self.headers)
            if not res or res.status_code != 200:
                return {"list": [], "page": int(page)}
            html = res.text
            items = self._parse_list_from_html(html)
            return {"list": items, "page": int(page)}
        except Exception as e:
            self.log("searchContent error: " + str(e))
            return {"list": [], "page": int(pg or "1")}

    def playerContent(self, flag, id, vipFlags):
        try:
            if id and (id.endswith(".m3u8") or ".m3u8" in id):
                # 通过本地代理过滤广告
                proxy_url = self._m3u8_proxy_url(id)
                self.log(f"playerContent 返回代理: {proxy_url}")
                return {"parse": 0, "url": proxy_url, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.headers["Referer"]}}
            if id and (id.endswith(".mp4") or ".mp4" in id):
                return {"parse": 0, "url": id, "header": {"User-Agent": self.headers["User-Agent"]}}

            if id and "vod/play" in id:
                res = self.fetch(id, headers=self.headers)
                if res and res.status_code == 200:
                    play_url = self._extract_play_url_from_html(res.text)
                    if play_url:
                        if play_url.endswith(".m3u8") or ".m3u8" in play_url:
                            proxy_url = self._m3u8_proxy_url(play_url)
                            self.log(f"playerContent 从详情页提取代理: {proxy_url}")
                            return {"parse": 0, "url": proxy_url, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.headers["Referer"]}}
                        if play_url.endswith(".mp4") or ".mp4" in play_url:
                            return {"parse": 0, "url": play_url, "header": {"User-Agent": self.headers["User-Agent"]}}

            return {"parse": 1, "url": id, "header": self.headers}
        except Exception as e:
            self.log("playerContent error: " + str(e))
            return {"parse": 1, "url": id, "header": self.headers}

    def localProxy(self, param):
        """m3u8 本地代理 - 广告过滤 + 路径重写"""
        try:
            # 兼容 url 和 source 两种参数名
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            # 获取 m3u8 内容
            res = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=15)
            if not res:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(res, "content", b"") or b""
            if not content and hasattr(res, "text") and res.text:
                content = res.text.encode("utf-8", errors="ignore")

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
        """清洗 m3u8：过滤广告分片，保留正片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 处理多码率 Master Playlist
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urllib.parse.urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

        # 从 #EXT-X-KEY 提取正片目录
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

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urljoin(source_url, line)
                media_parsed = urllib.parse.urlparse(media_url)
                # 过滤逻辑：判断分片路径是否以正片目录开头
                is_ad = not media_parsed.path.startswith(main_dir)
                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urljoin(source_url, line))
            else:
                segments.append(line)

        # 二次清洗：去除孤立/连续的标记
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写 m3u8 标签中的 URI"""
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

    def _parse_list_from_html(self, html):
        """从 HTML 中解析视频列表"""
        items = []
        pattern = r'<dl>\s*<dt>\s*<a\s+href="([^"]+)"[^>]*>\s*<img[^>]+data-src="([^"]+)"[^>]*>\s*<i>([^<]*)</i>\s*</a>\s*</dt>\s*<dd>\s*<a\s+href="[^"]+"[^>]*>\s*<h3>([^<]*)</h3>\s*</a>\s*</dd>\s*</dl>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            href, pic, remark, title = match
            vod_id = "0"
            id_match = re.search(r'/vod/play/id/(\d+)', href)
            if id_match:
                vod_id = id_match.group(1)
            packed_id = f"{vod_id}|$|{title}|$|{pic}|$|{remark}"
            items.append({
                "vod_id": packed_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark
            })
        return items

    def _parse_pagecount_from_html(self, html):
        match = re.search(r'尾页</a>\s*<a[^>]*href="[^"]*/page/(\d+)\.html"', html)
        return int(match.group(1)) if match else 0

    def _extract_play_url_from_html(self, html):
        """从详情页 HTML 中提取播放地址"""
        match = re.search(r'var\s+player_aaaa\s*=\s*{[^}]*"url"\s*:\s*"([^"]+)"', html)
        if match:
            return match.group(1)
        match = re.search(r'MacPlayer\.PlayUrl\s*=\s*"([^"]+)"', html)
        if match:
            return match.group(1)
        match = re.search(r'player_data\.url\s*=\s*"([^"]+)"', html)
        if match:
            return match.group(1)
        match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
        if match:
            return match.group(1)
        return None