# coding: utf-8
# 初恋之夜 - WordPress影视站
# 站点: https://mis.clzy7.fit/

import re
import json
import urllib.parse
import posixpath
from urllib.parse import quote, urlencode

class Spider:
    def __init__(self):
        self.host = "https://mis.clzy7.fit"
        self.site_name = "初恋之夜"
        self.classes = [
            {"type_id": "20", "type_name": "熟母少妇"},
            {"type_id": "21", "type_name": "网红直播"},
            {"type_id": "22", "type_name": "自拍偷拍"},
            {"type_id": "23", "type_name": "强奸乱伦"},
            {"type_id": "24", "type_name": "高清国产"},
            {"type_id": "25", "type_name": "韩国专区"},
            {"type_id": "26", "type_name": "日本有码"},
            {"type_id": "27", "type_name": "日本无码"},
            {"type_id": "28", "type_name": "欧美情色"},
            {"type_id": "29", "type_name": "动漫卡通"},
            {"type_id": "30", "type_name": "三级伦理"},
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }

    def getName(self):
        return "初恋之夜"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def destroy(self):
        pass

    def fetch(self, url, headers=None, timeout=15):
        try:
            import requests
            headers = headers or self.headers
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                return resp
        except Exception as e:
            print('fetch error:', e)
        return None

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/cn/home/web/")
        items = self._parse_video_list(html)
        return {"list": items[:18]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = str(pg) if pg else "1"
        url = self.host + '/vodtype/' + str(tid) + '.html'
        if int(pg) > 1:
            url = self.host + '/vodtype/' + str(tid) + '-' + str(pg) + '.html'
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        page_count = self._parse_page_count(html)
        return {
            "list": items,
            "page": int(pg),
            "pagecount": page_count,
            "limit": 18,
            "total": page_count * 18,
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        detail_url = self.host + '/' + vid + '.html'
        html = self._fetch_html(detail_url)
        
        # 提取标题
        title = ''
        m = re.search(r'<h1[^>]*class="[^"]*post-title[^"]*"[^>]*>([^<]+)</h1>', html)
        if m:
            title = m.group(1).strip()
        if not title:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                title = m.group(1).replace('在线观看', '').replace(' - 电影区 - 初恋之夜', '').strip()
        
        # 提取封面
        pic = ''
        m = re.search(r'<img[^>]*class="[^"]*wp-post-image[^"]*"[^>]*data-src="([^"]+)"', html)
        if m:
            pic = m.group(1)
            if pic.startswith('/'):
                pic = self.host + pic
        
        # 提取播放地址
        play_url = ''
        m = re.search(r"const\s+rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html)
        if m:
            raw = m.group(1)
            m3u8 = re.search(r'(https?://[^\s$#]+\.m3u8(?:\?[^\s#]*)?)', raw)
            if m3u8:
                play_url = m3u8.group(1)
        
        if not play_url:
            m = re.search(r'videoSrc\s*=\s*["\']([^"\']+)["\']', html)
            if m:
                play_url = m.group(1)
                if play_url.startswith('/'):
                    play_url = self.host + play_url
        
        if play_url:
            vod_play_url = f"播放${play_url}"
        else:
            vod_play_url = f"播放${vid}"
        
        vod = {
            "vod_id": vid,
            "vod_name": title or f"视频{vid}",
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": vod_play_url,
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        pg = str(pg) if pg else "1"
        url = self.host + '/s/index.html?wd=' + urllib.parse.quote(key)
        if int(pg) > 1:
            url = self.host + '/s/index.html?wd=' + urllib.parse.quote(key) + '&page=' + pg
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        return {"list": items, "page": int(pg)}

    def getProxyUrl(self):
        """获取本地代理地址"""
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址"""
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def playerContent(self, flag, id, vipFlags):
        # 如果id是m3u8链接，包装成代理URL
        if id and id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0, 
                "url": self._m3u8_proxy_url(id), 
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        # 如果id是详情页URL，尝试提取m3u8
        if id and id.startswith("http"):
            html = self._fetch_html(id)
            m = re.search(r"const\s+rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html)
            if m:
                m3u8 = re.search(r'(https?://[^\s$#]+\.m3u8(?:\?[^\s#]*)?)', m.group(1))
                if m3u8:
                    return {
                        "parse": 0, 
                        "url": self._m3u8_proxy_url(m3u8.group(1)), 
                        "header": {"User-Agent": self.headers.get("User-Agent", "")}
                    }
            m = re.search(r'videoSrc\s*=\s*["\']([^"\']+)["\']', html)
            if m:
                url = m.group(1)
                if url.startswith('/'):
                    url = self.host + url
                if '.m3u8' in url:
                    return {
                        "parse": 0, 
                        "url": self._m3u8_proxy_url(url), 
                        "header": {"User-Agent": self.headers.get("User-Agent", "")}
                    }
            return {"parse": 1, "url": id, "header": self.headers}
        return {"parse": 1, "url": id, "header": self.headers}

    def localProxy(self, param):
        """
        m3u8本地代理 - 广告分片过滤
        参考wangshi_ribao.py的实现方式
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
        """清洗m3u8 - 过滤广告分片（完全参考wangshi_ribao.py）"""
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

        # 从 #EXT-X-KEY 提取正片目录（更准确）
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

        # 二次清洗：去除孤立/连续的 #EXT-X-DISCONTINUITY 和 KEY:METHOD=NONE
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        # 清理尾部多余的标记
        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI（补全绝对地址）"""
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

    def _fetch_html(self, url):
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if resp and hasattr(resp, "status_code") and resp.status_code == 200:
                return resp.text
            if resp and hasattr(resp, "text"):
                return resp.text
        except:
            pass
        return ""

    def _parse_video_list(self, html):
        items = []
        if not html:
            return items
        # WordPress 文章列表解析
        pattern = r'<article[^>]*>.*?<a\s+href="/(\d+)\.html"[^>]*>.*?<h2[^>]*>.*?<a[^>]*>([^<]+)</a>.*?</h2>.*?<img[^>]*data-src="([^"]+)"'
        matches = re.findall(pattern, html, re.DOTALL)
        for vid, title, pic in matches:
            if vid and title:
                items.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": pic if pic.startswith('http') else self.host + pic,
                    "vod_remarks": ""
                })
        if not items:
            # 备用模式
            pattern2 = r'<a\s+href="/(\d+)\.html"[^>]*>\s*<img[^>]*data-src="([^"]+)"[^>]*>\s*</a>\s*<h2[^>]*>.*?<a[^>]*>([^<]+)</a>'
            matches2 = re.findall(pattern2, html, re.DOTALL)
            for vid, pic, title in matches2:
                if vid and title:
                    items.append({
                        "vod_id": vid,
                        "vod_name": title.strip(),
                        "vod_pic": pic if pic.startswith('http') else self.host + pic,
                        "vod_remarks": ""
                    })
        return items

    def _parse_page_count(self, html):
        if not html:
            return 1
        # 从 max_num_pages 提取
        m = re.search(r'"max_num_pages":(\d+)', html)
        if m:
            return int(m.group(1))
        # 从分页链接提取
        page_links = re.findall(r'/\d+-(\d+)\.html', html)
        if page_links:
            max_page = max([int(p) for p in page_links])
            if max_page > 1:
                return max_page
        return 1

    def recommendContent(self, ids, pg):
        return {"list": []}