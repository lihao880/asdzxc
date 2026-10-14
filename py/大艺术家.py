# coding: utf-8
"""
站点: 大艺术家
域名: https://xn--cjztj162d.yishusheme.site/
类型: MacCMS 标准影视站 (成人内容)
说明: HTML 解析方式，分类硬编码，m3u8 直链播放，支持 localProxy 广告过滤
"""
import json
import re
import urllib.parse
import posixpath
from urllib.parse import urljoin, quote, unquote, urlencode

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xn--cjztj162d.yishusheme.site"
        self.site_name = "大艺术家"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "35", "type_name": "中文字幕"},
            {"type_id": "43", "type_name": "国产视频"},
            {"type_id": "53", "type_name": "传媒拍摄"},
            {"type_id": "31", "type_name": "捆绑调教"},
            {"type_id": "51", "type_name": "探花约炮"},
            {"type_id": "39", "type_name": "欧美视频"},
            {"type_id": "55", "type_name": "三级视频"},
            {"type_id": "25", "type_name": "重口猎奇"},
            {"type_id": "23", "type_name": "同性视频"},
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}

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
        try:
            html = self._fetch_html(self.host + "/")
            items = self._parse_video_list(html)
            return {"list": items[:30]}
        except Exception as e:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = str(pg) if pg and str(pg).isdigit() and int(pg) > 0 else "1"
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
            html = self._fetch_html(url)
            items = self._parse_video_list(html)
            pagecount = self._parse_page_count(html)
            if pagecount < int(page):
                pagecount = int(page)
            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception as e:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            if not ids:
                return {"list": []}
            vid = str(ids[0]) if isinstance(ids, list) else str(ids)
            detail_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            html = self._fetch_html(detail_url)

            title = self._extract_title(html) or "未知视频"
            pic = self._extract_cover(html) or ""
            remark = self._extract_remark(html) or ""

            play_url = self._extract_m3u8_from_html(html)
            if play_url:
                vod_play_url = f"播放${play_url}"
                vod_play_from = "线路1"
            else:
                vod_play_url = f"播放${detail_url}"
                vod_play_from = "播放"

            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
                "vod_content": remark,
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url
            }
            return {"list": [vod]}
        except Exception as e:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            if not key:
                return {"list": [], "page": 1}
            page = str(pg) if pg and str(pg).isdigit() and int(pg) > 0 else "1"
            url = f"{self.host}/index.php/vod/search/page/{page}/wd/{quote(key)}.html"
            html = self._fetch_html(url)
            items = self._parse_video_list(html)
            return {"list": items, "page": int(page)}
        except Exception as e:
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        try:
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
                play_url = self._extract_m3u8_from_html(html)
                if play_url:
                    return {
                        "parse": 0,
                        "url": self._m3u8_proxy_url(play_url),
                        "header": {"User-Agent": self.headers.get("User-Agent", "")}
                    }
                return {"parse": 1, "url": id, "header": self.headers}
            # 如果id是vod_id，尝试获取m3u8
            if id:
                detail_url = f"{self.host}/index.php/vod/play/id/{id}/sid/1/nid/1.html"
                html = self._fetch_html(detail_url)
                play_url = self._extract_m3u8_from_html(html)
                if play_url:
                    return {
                        "parse": 0,
                        "url": self._m3u8_proxy_url(play_url),
                        "header": {"User-Agent": self.headers.get("User-Agent", "")}
                    }
                return {"parse": 1, "url": detail_url, "header": self.headers}
            return {"parse": 1, "url": id, "header": self.headers}
        except Exception as e:
            return {"parse": 1, "url": id, "header": self.headers}

    def getProxyUrl(self):
        """获取本地代理地址"""
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址"""
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

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

            # 发起HTTP请求获取m3u8内容
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
        """清洗m3u8 - 过滤广告分片"""
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

    def _fetch_html(self, url, params=None):
        full_url = url
        if params:
            if "?" in url:
                full_url = url + "&" + urlencode(params)
            else:
                full_url = url + "?" + urlencode(params)
        try:
            resp = self.fetch(full_url, headers=self.headers, timeout=15)
            if resp and hasattr(resp, "status_code") and resp.status_code == 200:
                return resp.text
            if resp and hasattr(resp, "text"):
                return resp.text
        except:
            pass
        return ""

    def _parse_video_list(self, html):
        """解析视频列表"""
        items = []
        if not html:
            return items
        # 匹配 entry 块
        pattern = r'<div class="entry">(.*?)</div>\s*(?=<div class="entry">|</div>\s*<div class="wp-pagenavi|$)'
        entries = re.findall(pattern, html, re.DOTALL)

        for block in entries:
            href_match = re.search(r'<a class="popimg" href="([^"]+)"', block)
            if not href_match:
                continue
            href = href_match.group(1)

            vid_match = re.search(r'/id/(\d+)/', href)
            if vid_match:
                vod_id = vid_match.group(1)
            else:
                id_match = re.search(r'id=(\d+)', href)
                if id_match:
                    vod_id = id_match.group(1)
                else:
                    continue

            pic_match = re.search(r'<img[^>]*src="([^"]+)"', block)
            pic = pic_match.group(1) if pic_match else ""
            if pic and not pic.startswith("http"):
                pic = urljoin(self.host, pic)

            title_match = re.search(r'<h2[^>]*class="information"[^>]*>.*?<a[^>]*>([^<]+)</a>', block, re.DOTALL)
            if not title_match:
                title_match = re.search(r'<h2[^>]*>.*?<a[^>]*>([^<]+)</a>', block, re.DOTALL)
            if not title_match:
                alt_match = re.search(r'alt="([^"]+)"', block)
                if alt_match:
                    title = alt_match.group(1)
                else:
                    title = "未知视频"
            else:
                title = title_match.group(1).strip()
                if not title:
                    alt_match = re.search(r'alt="([^"]+)"', block)
                    if alt_match:
                        title = alt_match.group(1)
                    else:
                        title = "未知视频"

            items.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": ""
            })

        return items

    def _parse_page_count(self, html):
        """解析总页数"""
        if not html:
            return 1
        # 匹配页码链接
        pattern = r'<a[^>]*class="page[^"]*"[^>]*>(\d+)\s*</a>'
        pages = re.findall(pattern, html)
        if pages:
            page_nums = [int(p) for p in pages if p.isdigit()]
            if page_nums:
                return max(page_nums)
        # 匹配当前页码
        current_match = re.search(r'<span[^>]*class="current"[^>]*>(\d+)</span>', html)
        if current_match:
            current = int(current_match.group(1))
            next_match = re.search(r'<a[^>]*class="nextpostslink"[^>]*>', html)
            if next_match:
                return current + 1
            return current
        # 从 href 中提取
        pattern3 = r'page/(\d+)\.html'
        pages3 = re.findall(pattern3, html)
        if pages3:
            page_nums = [int(p) for p in pages3 if p.isdigit()]
            if page_nums:
                return max(page_nums)
        return 1

    def _extract_title(self, html):
        title_match = re.search(r'<title>([^<]+)</title>', html)
        if title_match:
            title = title_match.group(1)
            title = re.sub(r'\s*在线观看\s*$', '', title)
            return title.strip()
        return None

    def _extract_cover(self, html):
        pattern = r'<img[^>]*class="[^"]*poster[^"]*"[^>]*src="([^"]+)"'
        match = re.search(pattern, html)
        if match:
            pic = match.group(1)
            if not pic.startswith("http"):
                pic = urljoin(self.host, pic)
            return pic
        pattern2 = r'<a class="popimg"[^>]*>.*?<img[^>]*src="([^"]+)"'
        matches = re.findall(pattern2, html, re.DOTALL)
        if matches:
            pic = matches[0]
            if not pic.startswith("http"):
                pic = urljoin(self.host, pic)
            return pic
        return ""

    def _extract_remark(self, html):
        pattern = r'<span class="views">.*?<strong>([^<]+)</strong>'
        match = re.search(pattern, html)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_m3u8_from_html(self, html):
        """从HTML中提取m3u8播放地址"""
        if not html:
            return None
        # 方法1: 从 player_aaaa 中提取
        start_marker = "var player_aaaa="
        start_pos = html.find(start_marker)
        if start_pos != -1:
            json_start = html.find("{", start_pos)
            if json_start != -1:
                brace_count = 0
                json_end = -1
                for i in range(json_start, len(html)):
                    if html[i] == "{":
                        brace_count += 1
                    elif html[i] == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                if json_end != -1:
                    json_str = html[json_start:json_end]
                    try:
                        data = json.loads(json_str)
                        url = data.get("url", "")
                        if url and ".m3u8" in url:
                            return url
                    except:
                        url_match = re.search(r'"url"\s*:\s*"([^"]+)"', json_str)
                        if url_match:
                            url = url_match.group(1)
                            url = url.replace("\\/", "/")
                            if url and ".m3u8" in url:
                                return url
        # 方法2: 从 iframe src 中提取
        pattern2 = r'<iframe[^>]*src="[^"]*url=([^"&]+)'
        match2 = re.search(pattern2, html)
        if match2:
            url = unquote(match2.group(1))
            if url and ".m3u8" in url:
                return url
        # 方法3: 直接找 m3u8 链接
        pattern3 = r'https?://[^\s"\']+\.m3u8[^\s"\']*'
        match3 = re.search(pattern3, html)
        if match3:
            return match3.group(0)
        return None