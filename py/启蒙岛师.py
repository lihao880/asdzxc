# coding: utf-8
# 启蒙岛师 - TVBox/FongMi 影视爬虫
# 站点: https://chb.qmds6.beauty/qmds/
# 优化 localProxy 处理 m3u8 多域名 + AES 加密

import re
import json
import urllib.parse
import posixpath
from urllib.parse import quote, urlencode, urljoin

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://chb.qmds6.beauty/cn/home/web"
        self.site_name = "启蒙岛师"
        self.classes = [
            {"type_id": "20", "type_name": "亚洲情色"},
            {"type_id": "21", "type_name": "制服师生"},
            {"type_id": "22", "type_name": "卡通动漫"},
            {"type_id": "24", "type_name": "强奸乱伦"},
            {"type_id": "26", "type_name": "中文字幕"},
            {"type_id": "25", "type_name": "偷拍自拍"},
            {"type_id": "27", "type_name": "欧美性爱"},
            {"type_id": "28", "type_name": "人妻熟女"},
            {"type_id": "29", "type_name": "无码专区"},
            {"type_id": "23", "type_name": "三级伦理"},
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://chb.qmds6.beauty/",
        }

    def getName(self):
        return "启蒙岛师"

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
        return {"list": items[:20] if items else []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg) if pg and str(pg).isdigit() else "1"
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        page_count = self._parse_page_count(html)
        return {
            "list": items,
            "page": int(pg),
            "pagecount": page_count if page_count > 0 else 1,
            "limit": 20,
            "total": page_count * 20 if page_count > 0 else 0,
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        if '|$|' in vid:
            parts = vid.split('|$|')
            vid = parts[0]
            name = parts[1] if len(parts) > 1 else ""
            pic = parts[2] if len(parts) > 2 else ""
            remark = parts[3] if len(parts) > 3 else ""
        else:
            name = "视频"
            pic = ""
            remark = ""

        play_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        vod = {
            "vod_id": vid,
            "vod_name": name or f"视频{vid}",
            "vod_pic": pic or "",
            "vod_remarks": remark or "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}",
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = str(pg) if pg and str(pg).isdigit() else "1"
        url = f"{self.host}/index.php/vod/search.html?wd={quote(key)}"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": self.headers}
        
        if id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id),
                "header": {
                    "User-Agent": self.headers.get("User-Agent", ""),
                    "Referer": self.host + "/",
                }
            }

        if id.startswith("http"):
            html = self._fetch_html(id)
            play_url = self._extract_m3u8_from_html(html)
            if play_url:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(play_url),
                    "header": {
                        "User-Agent": self.headers.get("User-Agent", ""),
                        "Referer": id,
                    }
                }
            return {"parse": 1, "url": id, "header": self.headers}

        detail_url = f"{self.host}/index.php/vod/play/id/{id}/sid/1/nid/1.html"
        html = self._fetch_html(detail_url)
        play_url = self._extract_m3u8_from_html(html)
        if play_url:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(play_url),
                "header": {
                    "User-Agent": self.headers.get("User-Agent", ""),
                    "Referer": detail_url,
                }
            }
        return {"parse": 1, "url": detail_url, "header": self.headers}

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        """
        m3u8本地代理 - 参考王室日报的稳健实现
        """
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

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://chb.qmds6.beauty/",
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Origin": "https://chb.qmds6.beauty",
            }

            resp = self.fetch(target, headers=headers, timeout=15)
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
        """清洗m3u8 - 参考王室日报的稳健实现，过滤广告分片并重写路径"""
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

                # 过滤广告分片
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

        # 清理冗余标记
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
        """重写m3u8标签中的URI"""
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

    def _fetch_html(self, url, params=None):
        full_url = url
        if params:
            if "?" in url:
                full_url = url + "&" + urlencode(params)
            else:
                full_url = url + "?" + urlencode(params)
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": self.host + "/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0",
            }
            resp = self.fetch(full_url, headers=headers, timeout=15)
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
        pattern = r'<div[^>]*class="[^"]*video-card[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-original="([^"]+)"[^>]*>.*?<div[^>]*class="[^"]*time[^"]*"[^>]*>([^<]+)</div>.*?<a[^>]*href="[^"]*"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        if matches:
            for link, pic, remark, title in matches:
                if "play/id/" in link:
                    vid_match = re.search(r'/id/(\d+)/', link)
                    if vid_match:
                        vid = vid_match.group(1)
                        packed_id = f"{vid}|$|{title.strip()}|$|{pic}|$|{remark.strip()}"
                        items.append({
                            "vod_id": packed_id,
                            "vod_name": title.strip(),
                            "vod_pic": pic,
                            "vod_remarks": remark.strip(),
                        })
            return items

        pattern2 = r'<a[^>]*href="([^"]*play/id/(\d+)/[^"]*)"[^>]*>.*?<img[^>]*(?:data-original|src)="([^"]+)"[^>]*>.*?<div[^>]*class="[^"]*time[^"]*"[^>]*>([^<]+)</div>'
        matches2 = re.findall(pattern2, html, re.DOTALL)
        for link, vid, pic, remark in matches2:
            title_match = re.search(r'<div[^>]*class="[^"]*video-title[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>', html, re.DOTALL)
            title = title_match.group(1).strip() if title_match else f"视频{vid}"
            packed_id = f"{vid}|$|{title}|$|{pic}|$|{remark.strip() if remark else ''}"
            items.append({
                "vod_id": packed_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark.strip() if remark else "",
            })
        return items

    def _parse_page_count(self, html):
        if not html:
            return 1
        pattern = r'<li[^>]*class="[^"]*page-item[^"]*"[^>]*><a[^>]*href="[^"]*page/(\d+)\.html"[^>]*>\d+</a></li>'
        matches = re.findall(pattern, html)
        if matches:
            nums = [int(n) for n in matches if n.isdigit()]
            if nums:
                return max(nums)
        pattern2 = r'page/(\d+)\.html.*?下一页'
        match2 = re.search(pattern2, html)
        if match2:
            return int(match2.group(1)) + 1
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
            if url.startswith("http"):
                return url
        pattern3 = r'https?://[^"\']+\.m3u8[^"\']*'
        match3 = re.search(pattern3, html)
        if match3:
            return match3.group(0)
        return None