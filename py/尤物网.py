# coding: utf-8
"""
站点: 尤物网 (iae6.com)
类型: 成人影视站
特点: 静态HTML生成，m3u8直链播放，本地代理过滤广告
域名: https://iae6.com/
分类: 国产主播(fpojt), 自拍偷拍(ffqtu), 美女主播(gglci), 韩国主播(rhinn), 国产直播(gpooi), 男同gay友(lulfe), AV明星1(rraem)
"""

import json
import re
import posixpath
from urllib.parse import urljoin, quote, unquote, urlparse

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://iae6.com/"
        self.classes = [
            {"type_id": "fpojt", "type_name": "国产主播"},
            {"type_id": "ffqtu", "type_name": "自拍偷拍"},
            {"type_id": "gglci", "type_name": "美女主播"},
            {"type_id": "rhinn", "type_name": "韩国主播"},
            {"type_id": "gpooi", "type_name": "国产直播"},
            {"type_id": "lulfe", "type_name": "男同gay友"},
            {"type_id": "rraem", "type_name": "AV明星1"},
        ]
        self.filters = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host,
        }

    def getName(self):
        return "尤物网"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐视频"""
        try:
            html = self.fetch(self.host, headers=self.headers).text
            return {"list": self._parse_video_list(html)}
        except Exception as e:
            self.log("homeVideoContent error: " + str(e))
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        """分类列表页"""
        page = pg or "1"
        if page == "1" or page == 1:
            url = f"{self.host}{tid}/"
        else:
            url = f"{self.host}{tid}/page/{page}/"

        try:
            html = self.fetch(url, headers=self.headers).text
            videos = self._parse_video_list(html)
            pagecount = self._parse_page_count(html)
            return {
                "list": videos,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception as e:
            self.log("categoryContent error: " + str(e))
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        """详情页"""
        url = ids[0]
        if not url.startswith("http"):
            url = urljoin(self.host, url)

        try:
            html = self.fetch(url, headers=self.headers).text
            vod = self._parse_detail(html, url)
            return {"list": [vod]}
        except Exception as e:
            self.log("detailContent error: " + str(e))
            return {"list": []}

    def searchContent(self, key, quick=False, pg="1"):
        """搜索 - 站点搜索API不可用，返回空"""
        return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags=""):
        """播放地址解析 - 走本地代理过滤广告"""
        if id.startswith("http") and (".m3u8" in id or ".mp4" in id):
            if ".m3u8" in id:
                return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": self.headers}
            return {"parse": 0, "url": id, "header": self.headers}

        if id.startswith("http"):
            try:
                html = self.fetch(id, headers=self.headers).text
                m3u8_url = self._extract_m3u8(html)
                if m3u8_url:
                    return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": self.headers}
            except:
                pass

        return {"parse": 1, "url": id, "header": self.headers}

    def _parse_video_list(self, html):
        """解析视频列表"""
        videos = []
        pattern = r'<div class="video-item">.*?<a class="video-thumbnail" href="([^"]+)".*?<img src="([^"]+)" alt="([^"]+)".*?<span class="category-badge">([^<]+)</span>.*?</a>.*?<div class="video-caption">.*?<a href="[^"]+">([^<]+)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            href, img, alt, cat, title = match
            video_id = href if href.startswith("/") else "/" + href
            videos.append({
                "vod_id": video_id,
                "vod_name": title or alt,
                "vod_pic": img,
                "vod_remarks": cat,
            })
        if not videos:
            pattern2 = r'<div class="video-item">.*?<a href="([^"]+)".*?<img src="([^"]+)".*?alt="([^"]+)".*?<div class="video-caption">.*?<a href="[^"]+">([^<]+)</a>'
            matches2 = re.findall(pattern2, html, re.DOTALL)
            for match in matches2:
                href, img, alt, title = match
                video_id = href if href.startswith("/") else "/" + href
                videos.append({
                    "vod_id": video_id,
                    "vod_name": title or alt,
                    "vod_pic": img,
                    "vod_remarks": "",
                })
        return videos

    def _parse_page_count(self, html):
        """解析总页数"""
        page_nums = re.findall(r'/page/(\d+)/', html)
        if page_nums:
            return max(int(p) for p in page_nums)
        if 'class="next page-link"' in html:
            return 50
        return 1

    def _parse_detail(self, html, base_url):
        """解析详情页"""
        title_match = re.search(r'<h1[^>]*class="content-title"[^>]*>(.*?)</h1>', html, re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

        pic_match = re.search(r'<meta property="og:image"\s+content="([^"]+)"', html)
        pic = pic_match.group(1) if pic_match else ""

        desc_match = re.search(r'<meta name="description"\s+content="([^"]+)"', html)
        desc = desc_match.group(1) if desc_match else ""

        m3u8_url = self._extract_m3u8(html)

        vod = {
            "vod_id": base_url,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": desc,
            "vod_play_from": "直链",
            "vod_play_url": f"播放${m3u8_url}" if m3u8_url else "",
        }
        return vod

    def _extract_m3u8(self, html):
        """从HTML中提取m3u8地址"""
        pattern1 = r'sources:\s*\[\s*\{\s*src:\s*["\']([^"\']+\.m3u8)["\']'
        match = re.search(pattern1, html)
        if match:
            return match.group(1)

        pattern2 = r'https?://[^\s"\']+\.m3u8'
        matches = re.findall(pattern2, html)
        if matches:
            for m in matches:
                if "index.m3u8" in m or "playlist" in m:
                    return m
            return matches[0]

        pattern3 = r'"contentUrl"\s*:\s*"([^"]+\.m3u8)"'
        match = re.search(pattern3, html)
        if match:
            return match.group(1)

        return None

    def _m3u8_proxy_url(self, url):
        """m3u8代理地址（标准格式: ?do=py&url=）"""
        proxy_base = self.getProxyUrl()
        # 如果 proxy_base 已经包含 ?do=py，直接拼接 &url=
        if "?do=py" in proxy_base:
            return proxy_base + "&url=" + quote(str(url or ""), safe="")
        # 否则添加 ?do=py&url=
        return proxy_base + "?do=py&url=" + quote(str(url or ""), safe="")
    def localProxy(self, param):
        """m3u8本地代理 - 过滤广告分片"""
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            self.log("localProxy target: " + target[:200])

            res = self.fetch(target, headers={"User-Agent": self.headers["User-Agent"]}, timeout=15)
            self.log("fetch status: " + str(getattr(res, "status_code", 0)))

            if not res or getattr(res, "status_code", 0) != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]

            raw = getattr(res, "content", b"") or b""
            text = raw.decode("utf-8", errors="ignore")

            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log("localProxy error: " + str(e))
            return [500, "text/plain", str(e).encode("utf-8", errors="ignore")]
    def _clean_m3u8(self, text, source_url):
        """清洗m3u8：过滤广告分片，保留正片"""
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

        parsed = urlparse(source_url)
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
        removed = 0

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urljoin(source_url, line)
                media_parsed = urlparse(media_url)

                # 过滤逻辑：判断分片路径是否以正片目录开头
                is_ad = not media_parsed.path.startswith(main_dir)

                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                else:
                    removed += 1
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urljoin(source_url, line))
            else:
                segments.append(line)

        # 二次清洗：去除孤立的 #EXT-X-DISCONTINUITY 和 KEY:METHOD=NONE
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
            self.log("m3u8已过滤广告分片: %d" % removed)
        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI（补全绝对地址）"""
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

    def siteInfo(self):
        """站点信息"""
        return {
            "name": "尤物网",
            "domain": "iae6.com",
            "type": "成人影视站",
            "description": "m3u8直链播放，本地代理过滤广告"
        }