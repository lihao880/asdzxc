# -*- coding: utf-8 -*-
import re
import json
import base64
from urllib.parse import urljoin, quote, unquote, urlparse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.zysp8.boats"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
        }
        self.classes = [
            {"type_id": "21", "type_name": "女神学生"},
            {"type_id": "22", "type_name": "美女直播"},
            {"type_id": "23", "type_name": "人妻系列"},
            {"type_id": "24", "type_name": "强奸乱伦"},
            {"type_id": "25", "type_name": "自拍偷拍"},
            {"type_id": "26", "type_name": "制服诱惑"},
            {"type_id": "27", "type_name": "巨乳系列"},
            {"type_id": "28", "type_name": "自慰系列"},
            {"type_id": "29", "type_name": "国产视频"},
            {"type_id": "30", "type_name": "无码视频"},
            {"type_id": "31", "type_name": "有码视频"},
            {"type_id": "32", "type_name": "中文字幕"},
            {"type_id": "33", "type_name": "日韩精品"},
            {"type_id": "34", "type_name": "欧美精品"},
            {"type_id": "35", "type_name": "动漫精品"},
            {"type_id": "36", "type_name": "三级伦理"},
        ]
        self.filters = {}

    def getName(self):
        return "状元视频"

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def destroy(self):
        pass

    def getProxyUrl(self):
        """获取本地代理地址"""
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址"""
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def _fetch_html(self, url, timeout=30):
        try:
            resp = self.fetch(url, headers=self.headers, timeout=timeout)
            if resp and hasattr(resp, "status_code") and resp.status_code == 200:
                return resp.text
            return None
        except Exception as e:
            print(f"fetch error: {e}")
            return None

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        return urljoin(self.host, url)

    def _extract_vod_id(self, url):
        if not url:
            return ""
        m = re.search(r"/(\d+)\.html", url)
        if m:
            return m.group(1)
        return url

    def _parse_video_items(self, html, limit=999):
        videos = []
        if not html:
            return videos

        pattern = r'<li class="col-md-2 col-sm-3 col-xs-4">(.*?)</li>'
        items = re.findall(pattern, html, re.DOTALL)

        for item in items:
            link_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*>', item)
            if not link_match:
                continue
            href = link_match.group(1)
            vid = self._extract_vod_id(href)
            if not vid:
                continue

            title_match = re.search(r'<h5[^>]*>.*?<a[^>]*>(.*?)</a>.*?</h5>', item, re.DOTALL)
            title = title_match.group(1).strip() if title_match else ""

            pic_match = re.search(r'background-image:\s*url\(([^)]+)\)', item)
            pic = pic_match.group(1).strip().strip('"\'') if pic_match else ""

            remark_match = re.search(r'<div class="subtitle[^"]*">人气:(\d+)</div>', item)
            remark = remark_match.group(1) if remark_match else ""

            if vid and title:
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": self._fix_url(pic),
                    "vod_remarks": remark
                })
                if len(videos) >= limit:
                    break

        return videos

    def _get_category_url(self, tid, pg):
        pg = int(pg) if pg else 1
        if pg == 1:
            return f"{self.host}/vodtype/{tid}.html"
        return f"{self.host}/vodtype/{tid}-{pg}.html"

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/zysp/")
        if not html:
            return {"list": []}

        pattern = r'<div class="box-title">.*?最近更新.*?</div>(.*?)<div class="box-title">'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            section_html = match.group(1)
            videos = self._parse_video_items(section_html, 20)
        else:
            videos = self._parse_video_items(html, 20)

        return {"list": videos}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        url = self._get_category_url(tid, pg)

        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

        videos = self._parse_video_items(html, 100)

        pagecount = 1
        page_match = re.search(r'<a[^>]*>(\d+)/(\d+)</a>', html)
        if page_match:
            pagecount = int(page_match.group(2)) or 1
        else:
            page_links = re.findall(r'<a[^>]*>(\d+)</a>', html)
            if page_links:
                nums = [int(x) for x in page_links if x.isdigit()]
                if nums:
                    pagecount = max(nums)

        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = ids[0]
        url = f"{self.host}/{vid}.html"

        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        title_match = re.search(r'<title>(.*?)\s*-\s*状元视频</title>', html)
        title = title_match.group(1).strip() if title_match else ""

        pic_match = re.search(r'background-image:\s*url\(([^)]+)\)', html)
        pic = pic_match.group(1).strip().strip('"\'') if pic_match else ""

        play_url = ""
        raw_url_match = re.search(r"const\s+rawUrl\s*=\s*['\"]((?:https?:)?//[^'\"]+)['\"]", html)
        if raw_url_match:
            play_url = raw_url_match.group(1)
            if not play_url.startswith("http"):
                play_url = "https:" + play_url

        if not play_url:
            m3u8_match = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html)
            if m3u8_match:
                play_url = m3u8_match.group(0)

        if play_url:
            play_from = "默认线路"
            play_url_str = "播放$" + play_url
        else:
            play_from = "默认线路"
            play_url_str = "播放$" + vid

        data = {
            "vod_id": vid,
            "vod_name": title or "未知视频",
            "vod_pic": self._fix_url(pic),
            "vod_content": "",
            "vod_play_from": play_from,
            "vod_play_url": play_url_str,
        }

        return {"list": [data]}

    def searchContent(self, key, quick=False, pg="1"):
        if not key:
            return {"list": [], "page": 1, "pagecount": 1, "total": 0}

        pg = int(pg) if pg else 1
        if pg == 1:
            url = f"{self.host}/s/index.html?wd={quote(key)}"
        else:
            url = f"{self.host}/s/{quote(key)}/page/{pg}.html"

        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "total": 0}

        videos = self._parse_video_items(html, 100)

        pagecount = 1
        page_match = re.search(r'<a[^>]*>(\d+)/(\d+)</a>', html)
        if page_match:
            pagecount = int(page_match.group(2)) or 1

        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "total": pagecount * 20
        }

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {"parse": 1, "url": ""}

        if id.startswith("http") and (".m3u8" in id or ".mp4" in id):
            if ".m3u8" in id:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(id),
                    "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": self.host + "/"
                    }
                }
            return {
                "parse": 0,
                "url": id,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/"
                }
            }

        if id.startswith("http"):
            html = self._fetch_html(id)
            if html:
                raw_url_match = re.search(r"const\s+rawUrl\s*=\s*['\"]((?:https?:)?//[^'\"]+)['\"]", html)
                if raw_url_match:
                    url = raw_url_match.group(1)
                    if not url.startswith("http"):
                        url = "https:" + url
                    if ".m3u8" in url:
                        return {
                            "parse": 0,
                            "url": self._m3u8_proxy_url(url),
                            "header": {
                                "User-Agent": self.headers["User-Agent"],
                                "Referer": self.host + "/"
                            }
                        }
                    if ".mp4" in url:
                        return {
                            "parse": 0,
                            "url": url,
                            "header": {
                                "User-Agent": self.headers["User-Agent"],
                                "Referer": self.host + "/"
                            }
                        }

        return {
            "parse": 1,
            "url": id,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/"
            }
        }

    def localProxy(self, params):
        """m3u8 本地代理 - 过滤广告分片"""
        try:
            if isinstance(params, dict):
                target = params.get("url", "") or params.get("source", "")
            else:
                target = str(params or "")

            if target.startswith("url="):
                target = target[4:]
            target = unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            fetch_headers = {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
                "Accept": "*/*",
            }

            resp = self.fetch(target, headers=fetch_headers, timeout=15)
            if not resp:
                return [502, "text/plain", b"fetch failed: no response"]

            if getattr(resp, "status_code", 0) != 200:
                return [502, "text/plain", f"fetch failed: status {resp.status_code}".encode()]

            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")

            if not content:
                return [502, "text/plain", b"empty content"]

            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            # 调用广告过滤
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]
    def _is_ad_url(self, url):
        """判断URL是否为广告"""
        if not url:
            return False
        url_lower = url.lower()
        ad_keywords = ['ad.', 'ads', 'preroll', 'midroll', 'postroll', 'advertisement', '广告', 'sponsor', 'promotion', '片头', '片尾', 'banner', 'adv', 'ad_', '-ad-']
        for kw in ad_keywords:
            if kw in url_lower:
                return True
        # 检查路径是否包含 /ad/ 或 /adv/
        if '/ad/' in url_lower or '/adv/' in url_lower:
            return True
        return False

    def _clean_m3u8(self, text, source_url):
        """清洗m3u8 - 过滤广告分片（基于域名白名单）"""
        import posixpath
        import re
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
                    if child and (child.endswith('.m3u8') or '.m3u8?' in child):
                        child = self._m3u8_proxy_url(child)
                    out.append(child)
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
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urljoin(source_url, line))
            else:
                segments.append(line)

        # 二次清洗：移除所有 #EXT-X-DISCONTINUITY 和 KEY:METHOD=NONE
        out = []
        for line in segments:
            line = self._rewrite_uri(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                continue
            out.append(line)

        return "\n".join(out) + "\n"
    def _rewrite_uri(self, line, source_url):
        """重写m3u8标签中的URI（补全绝对地址）"""
        def repl(match):
            uri = match.group(1)
            if uri.startswith(("http://", "https://")):
                return 'URI="' + uri + '"'
            return 'URI="' + urljoin(source_url, uri) + '"'
        return re.sub(r'URI="([^"]+)"', repl, line)

    def recommendContent(self, ids, pg=1):
        if not ids:
            return {"list": []}
        vid = ids[0]
        url = f"{self.host}/{vid}.html"

        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        pattern = r'<div class="box-title">.*?同类推荐.*?</div>(.*?)</ul>'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            section_html = match.group(1)
            videos = self._parse_video_items(section_html, 20)
        else:
            videos = []

        return {"list": videos}