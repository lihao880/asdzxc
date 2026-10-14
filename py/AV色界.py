# coding: utf-8
# AV色界 - TVBox爬虫
# 站点: https://avsejie8.sbs

import re
import json
import urllib.parse
from urllib.parse import quote, urljoin

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://avsejie8.sbs"
        self.path = ""
        self.site_name = "AV色界"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.classes = [
            {"type_id": "128", "type_name": "视频一区"},
            {"type_id": "129", "type_name": "精品推荐"},
            {"type_id": "130", "type_name": "国产色情"},
            {"type_id": "132", "type_name": "91探花"},
            {"type_id": "133", "type_name": "网红流出"},
            {"type_id": "134", "type_name": "野外露出"},
            {"type_id": "135", "type_name": "传媒出品"},
            {"type_id": "136", "type_name": "国产精品"},
            {"type_id": "172", "type_name": "自拍泄密"},
            {"type_id": "146", "type_name": "视频二区"},
            {"type_id": "147", "type_name": "巨乳美乳"},
            {"type_id": "148", "type_name": "人妻熟女"},
            {"type_id": "149", "type_name": "强奸乱伦"},
            {"type_id": "150", "type_name": "亚洲无码"},
            {"type_id": "151", "type_name": "欺辱凌辱"},
            {"type_id": "152", "type_name": "制服丝袜"},
            {"type_id": "153", "type_name": "剧情介绍"},
            {"type_id": "154", "type_name": "多人多P"},
            {"type_id": "155", "type_name": "视频三区"},
            {"type_id": "156", "type_name": "绿帽换妻"},
            {"type_id": "157", "type_name": "韩国御姐"},
            {"type_id": "158", "type_name": "野外搭讪"},
            {"type_id": "160", "type_name": "精品无码"},
            {"type_id": "161", "type_name": "成人动漫"},
            {"type_id": "162", "type_name": "内射特写"},
            {"type_id": "163", "type_name": "自拍泄密"},
            {"type_id": "179", "type_name": "中文字幕"},
        ]
        self.filters = {}

    def getName(self):
        return self.site_name

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def destroy(self):
        pass

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return self.host + "/" + url.lstrip("/")

    def _fetch_html(self, url):
        try:
            resp = self.fetch(url, headers=self.headers)
            if resp and hasattr(resp, "text"):
                return resp.text
            return None
        except Exception:
            return None

    def _parse_video_list(self, html):
        videos = []
        if not html:
            return videos

        pattern = r'<a[^>]*href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*class="[^"]*group-item[^"]*"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<p>([^<]+)</p>'
        matches = re.findall(pattern, html, re.DOTALL)

        for href, pic, title in matches:
            if not href or not title:
                continue
            vid_match = re.search(r'/vodplay/(\d+)-\d+-\d+\.html', href)
            if vid_match:
                vid = vid_match.group(1)
                videos.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": self._fix_url(pic.strip()),
                    "vod_remarks": ""
                })

        return videos

    def _parse_page_count(self, html):
        if not html:
            return 1
        pattern = r'<a[^>]*class="[^"]*pageitem[^"]*"[^>]*href="[^"]*-(\d+)\.html"[^>]*>'
        matches = re.findall(pattern, html)
        if matches:
            return int(matches[-1]) if matches else 1
        pattern2 = r'共(\d+)条'
        match2 = re.search(pattern2, html)
        if match2:
            total = int(match2.group(1))
            return (total + 19) // 20
        return 1

    def _extract_m3u8_from_html(self, html):
        if not html:
            return None
        pattern = r'var\s+player_aaaa\s*=\s*(\{[^;]+\});'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                url = data.get("url", "")
                if url and url.startswith("http"):
                    return url
            except:
                pass
        pattern2 = r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"'
        match2 = re.search(pattern2, html)
        if match2:
            url = match2.group(1)
            if url and url.startswith("http"):
                return url
        pattern3 = r'https?://[^"\']+\.m3u8[^"\']*'
        match3 = re.search(pattern3, html)
        if match3:
            return match3.group(0)
        return None

    def _extract_title_from_html(self, html):
        if not html:
            return ""
        pattern = r'<p[^>]*class="[^"]*group-title[^"]*"[^>]*>([^<]+)</p>'
        match = re.search(pattern, html)
        if match:
            return match.group(1).strip()
        pattern2 = r'<title>([^<]+)</title>'
        match2 = re.search(pattern2, html)
        if match2:
            title = match2.group(1).strip()
            if "详情介绍" in title:
                title = title.split("详情介绍")[0].strip()
            return title
        return ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self.categoryContent("128", "1", False, {})

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = str(pg) if pg else "1"
        if page == "1":
            url = f"{self.host}/vodtype/{tid}.html"
        else:
            url = f"{self.host}/vodtype/{tid}-{page}.html"

        try:
            res = self.fetch(url, headers=self.headers)
            if not res:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

            html = res.text
            videos = self._parse_video_list(html)
            pagecount = self._parse_page_count(html)

            return {
                "list": videos,
                "page": int(page),
                "pagecount": pagecount or 1,
                "limit": 20,
                "total": (pagecount or 1) * 20
            }
        except Exception as e:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}

        vid = str(ids[0]) if isinstance(ids, list) else str(ids)
        detail_url = f"{self.host}/vodplay/{vid}-1-1.html"
        html = self._fetch_html(detail_url)

        if not html:
            return {"list": []}

        play_url = self._extract_m3u8_from_html(html)
        title = self._extract_title_from_html(html)

        vod = {
            "vod_id": vid,
            "vod_name": title or f"视频{vid}",
            "vod_pic": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "播放" if play_url else "",
            "vod_play_url": f"播放${play_url}" if play_url else "",
        }

        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        if not key:
            return {"list": [], "page": 1, "pagecount": 1, "total": 0}

        pg = int(pg) if pg else 1
        encoded_key = quote(key)
        search_url = f"{self.host}/vodsearch/-------------.html?wd={encoded_key}"

        html = self._fetch_html(search_url)
        videos = self._parse_video_list(html) if html else []

        pagecount = 1
        if html:
            pattern = r'共(\d+)条'
            match = re.search(pattern, html)
            if match:
                total = int(match.group(1))
                pagecount = (total + 19) // 20 if total > 0 else 1

        return {"list": videos, "page": pg, "pagecount": pagecount, "total": pagecount * 20}

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址"""
        if url:
            url = url.replace("\\/", "/")
        # 确保使用正确的代理格式
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")
    def playerContent(self, flag, id, vipFlags=None):
        # 处理转义字符 - 关键修复
        if id and isinstance(id, str):
            id = id.replace("\\/", "/")
        
        # 如果id是m3u8链接，包装成代理URL
        if id and id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id),
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        
        # 如果id是详情页URL，尝试提取m3u8
        if id and id.startswith("http") and "/vodplay/" in id:
            html = self._fetch_html(id)
            play_url = self._extract_m3u8_from_html(html)
            if play_url:
                return self.playerContent(flag, play_url, vipFlags)
            return {"parse": 1, "url": id, "header": self.headers}
        
        # 如果id是vod_id，尝试获取m3u8
        if id and id.isdigit():
            detail_url = f"{self.host}/vodplay/{id}-1-1.html"
            html = self._fetch_html(detail_url)
            play_url = self._extract_m3u8_from_html(html)
            if play_url:
                return self.playerContent(flag, play_url, vipFlags)
            return {"parse": 1, "url": detail_url, "header": self.headers}
        
        return {"parse": 1, "url": id, "header": self.headers}
    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                return 'URI="' + urljoin(source_url, match.group(1)) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            return urljoin(source_url, line)
        return line

    def _clean_m3u8(self, text, source_url):
        """清洗m3u8 - 过滤广告分片（参考王室日报实现）"""
        import posixpath
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
                    child = urllib.parse.urljoin(source_url, line)
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

        # 如果通过KEY没找到，尝试从DISCONTINUITY后的第一个分片推断
        if main_dir == source_dir:
            discontinuity_found = False
            for line in lines:
                if line.startswith("#EXT-X-DISCONTINUITY"):
                    discontinuity_found = True
                    continue
                if discontinuity_found and not line.startswith("#"):
                    media_url = urllib.parse.urljoin(source_url, line)
                    media_parsed = urllib.parse.urlparse(media_url)
                    if media_parsed.path:
                        dir_path = posixpath.dirname(media_parsed.path)
                        if dir_path and dir_path != "/":
                            main_dir = dir_path + "/"
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
                media_url = urllib.parse.urljoin(source_url, line)
                media_parsed = urllib.parse.urlparse(media_url)
                # 过滤逻辑：判断分片路径是否以正片目录开头
                is_ad = not media_parsed.path.startswith(main_dir)
                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urllib.parse.urljoin(source_url, line))
            else:
                segments.append(line)

        # 二次清洗
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
    def localProxy(self, param):
        """
        m3u8本地代理 - 广告分片过滤
        """
        try:
            # 兼容 url 和 source 两种参数名
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            # 剥离前缀 url= 并解码
            if target.startswith("url="):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            # 发起HTTP请求获取m3u8内容 - 设置超时15秒
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
                return [200, "application/vnd.apple.mpegurl", content]

            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            # 超时或异常时，返回原始内容让壳端直接播放
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]
    def recommendContent(self, ids, pg):
        try:
            if not ids:
                return {"list": []}

            vid = str(ids[0]) if isinstance(ids, list) else str(ids)

            detail_url = f"{self.host}/vodplay/{vid}-1-1.html"
            html = self._fetch_html(detail_url)

            if not html:
                return {"list": []}

            pattern = r'<a[^>]*href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*class="[^"]*group-item[^"]*"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<p>([^<]+)</p>'
            matches = re.findall(pattern, html, re.DOTALL)

            videos = []
            for href, pic, title in matches:
                vid_match = re.search(r'/vodplay/(\d+)-\d+-\d+\.html', href)
                if vid_match:
                    v = vid_match.group(1)
                    if v != vid:
                        videos.append({
                            "vod_id": v,
                            "vod_name": title.strip(),
                            "vod_pic": self._fix_url(pic.strip()),
                            "vod_remarks": ""
                        })

            if videos:
                return {"list": videos[:15]}

            return {"list": []}

        except Exception as e:
            return {"list": []}