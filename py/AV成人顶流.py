# -*- coding: utf-8 -*-
# AV成人顶流 影视爬虫 - MacCMS 标准站
# 站点: https://avcwave.avcrdl11.icu/golink/

import re
import json
import urllib.parse
import posixpath
from urllib.parse import quote, urlencode

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://avcwave.avcrdl11.icu"
        self.base_path = "/golink"
        self.site_name = "AV成人顶流"
        self.classes = [
            {"type_id": "245", "type_name": "日韩专区"},
            {"type_id": "276", "type_name": "巨乳中文"},
            {"type_id": "274", "type_name": "出轨中文"},
            {"type_id": "273", "type_name": "强奸中文"},
            {"type_id": "265", "type_name": "抖阴视频"},
            {"type_id": "264", "type_name": "网红头条"},
            {"type_id": "263", "type_name": "极品媚黑"},
            {"type_id": "262", "type_name": "萝莉少女"},
            {"type_id": "261", "type_name": "制服诱惑"},
            {"type_id": "268", "type_name": "乱伦精品"},
            {"type_id": "236", "type_name": "传媒视频"},
            {"type_id": "246", "type_name": "精品动漫"},
            {"type_id": "234", "type_name": "国产视频"},
            {"type_id": "238", "type_name": "性感主播"},
            {"type_id": "239", "type_name": "伦理三级"},
            {"type_id": "272", "type_name": "人妻中文"},
            {"type_id": "244", "type_name": "明星淫梦"},
            {"type_id": "242", "type_name": "VR专区"},
            {"type_id": "241", "type_name": "无码专区"},
            {"type_id": "240", "type_name": "中文字幕"},
            {"type_id": "271", "type_name": "制服中文"},
            {"type_id": "249", "type_name": "网曝门事件"},
            {"type_id": "248", "type_name": "欧美专区"},
            {"type_id": "247", "type_name": "AV解说"},
            {"type_id": "259", "type_name": "女同专区"},
            {"type_id": "258", "type_name": "SM专区"},
            {"type_id": "269", "type_name": "极品学妹"},
            {"type_id": "270", "type_name": "调教中文"},
            {"type_id": "254", "type_name": "明星换脸"},
            {"type_id": "253", "type_name": "强奸乱伦"},
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}
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
        """首页推荐 - 从默认分类（日韩专区）获取数据"""
        try:
            result = self.categoryContent('245', '1', False, None)
            return {"list": result.get("list", [])[:20]}
        except Exception as e:
            return {"list": []}
    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg) if pg else "1"
        url = f"{self.host}{self.base_path}/index.php/vod/type/id/{tid}/page/{pg}.html"
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
            return {"list": []}
        # 处理各种 ID 格式
        if isinstance(ids, list):
            vid = str(ids[0]).strip()
        else:
            vid = str(ids).strip()
        # 如果 ID 包含路径，提取数字部分
        if '/' in vid:
            match = re.search(r'/detail/id/(\d+)\.html', vid)
            if match:
                vid = match.group(1)
            else:
                match = re.search(r'/play/id/(\d+)/', vid)
                if match:
                    vid = match.group(1)

        detail_url = f"{self.host}{self.base_path}/index.php/vod/detail/id/{vid}.html"
        html = self._fetch_html(detail_url)

        title = self._extract_title(html) or f"视频{vid}"
        pic = self._extract_pic(html) or ""
        play_url = self._extract_m3u8_from_html(html)

        if play_url:
            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}",
            }
        else:
            play_page_url = f"{self.host}{self.base_path}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_page_url}",
            }
        return {"list": [vod]}
    def searchContent(self, key, quick, pg="1"):
        pg = str(pg) if pg else "1"
        url = f"{self.host}{self.base_path}/index.php/vod/search/page/{pg}/wd/{quote(key)}.html"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        return {"list": items, "page": int(pg)}

    def recommendContent(self, ids, pg):
        """
        相关推荐接口 - 从详情页的"猜你喜欢"中获取
        """
        try:
            if not ids:
                return {"list": []}
            vid = str(ids[0]) if isinstance(ids, list) else str(ids)

            detail_url = f"{self.host}{self.base_path}/index.php/vod/detail/id/{vid}.html"
            html = self._fetch_html(detail_url)
            if not html:
                print("recommendContent: 获取详情页HTML失败")
                return {"list": []}

            # 使用 _parse_video_list 解析
            items = self._parse_video_list(html)
            print(f"recommendContent: 解析到 {len(items)} 个视频")

            # 过滤掉当前视频
            filtered = [item for item in items if item.get("vod_id") != vid]

            print(f"recommendContent: 过滤后剩余 {len(filtered)} 个")
            return {"list": filtered[:20]}
        except Exception as e:
            print(f"recommendContent error: {e}")
            return {"list": []}
    def playerContent(self, flag, id, vipFlags):
        if id and id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id),
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        if id and id.startswith("http") and "/play/" in id:
            html = self._fetch_html(id)
            play_url = self._extract_m3u8_from_html(html)
            if play_url:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(play_url),
                    "header": {"User-Agent": self.headers.get("User-Agent", "")}
                }
            return {"parse": 1, "url": id, "header": self.headers}
        if id and re.match(r'^\d+$', str(id)):
            play_page_url = f"{self.host}{self.base_path}/index.php/vod/play/id/{id}/sid/1/nid/1.html"
            html = self._fetch_html(play_page_url)
            play_url = self._extract_m3u8_from_html(html)
            if play_url:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(play_url),
                    "header": {"User-Agent": self.headers.get("User-Agent", "")}
                }
            return {"parse": 1, "url": play_page_url, "header": self.headers}
        return {"parse": 1, "url": id, "header": self.headers}

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
        except Exception:
            pass
        return ""

    def _parse_video_list(self, html):
        items = []
        if not html:
            return items

        # 匹配详情页链接中的数字ID
        link_pattern = r'<a[^>]*href="[^"]*/detail/id/(\d+)\.html[^"]*"[^>]*title="([^"]*)"'
        matches = re.findall(link_pattern, html)

        if not matches:
            link_pattern2 = r'<a[^>]*href="[^"]*/play/id/(\d+)/[^"]*"[^>]*title="([^"]*)"'
            matches = re.findall(link_pattern2, html)

        if not matches:
            return items

        box_parts = []
        start = 0
        while True:
            pos = html.find('<div class="stui-vodlist__box', start)
            if pos == -1:
                break
            end = html.find('</div>', pos + 30)
            end2 = html.find('</div>', end + 1)
            if end2 == -1:
                end2 = end
            box_html = html[pos:end2]
            box_parts.append(box_html)
            start = end2 + 1

        for i, (vid, title) in enumerate(matches):
            pic = ""
            remark = ""
            if i < len(box_parts):
                box = box_parts[i]
                pic_match = re.search(r'data-original="([^"]+)"', box)
                if pic_match:
                    pic = pic_match.group(1)
                remark_match = re.search(r'pic-text[^>]*>([^<]*)', box)
                if remark_match:
                    remark = remark_match.group(1).strip()

            # 确保 vid 是纯数字
            vid = vid.strip()
            items.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": remark
            })
            if len(items) >= 20:
                break
        return items
    def _parse_page_count(self, html):
        if not html:
            return 1
        pattern = r'<a[^>]*href="[^"]*page/(\d+)\.html"[^>]*>.*?尾页'
        match = re.search(pattern, html)
        if match:
            return int(match.group(1))
        pattern2 = r'<a[^>]*>(\d+)</a>'
        matches = re.findall(pattern2, html)
        if matches:
            nums = [int(x) for x in matches if x.isdigit()]
            if nums:
                return max(nums)
        return 1

    def _extract_title(self, html):
        if not html:
            return None
        pattern = r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>'
        match = re.search(pattern, html)
        if match:
            return match.group(1).strip()
        pattern2 = r'<h1[^>]*>([^<]+)</h1>'
        match2 = re.search(pattern2, html)
        if match2:
            return match2.group(1).strip()
        return None

    def _extract_pic(self, html):
        if not html:
            return None
        pattern = r'<img[^>]*class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]+)"'
        match = re.search(pattern, html)
        if match:
            return match.group(1)
        return None

    def _extract_m3u8_from_html(self, html):
        if not html:
            return None
        pattern = r'var\s+player_aaaa\s*=\s*(\{[^;]+\});'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                url = data.get("url", "")
                if url and url.startswith("http") and ".m3u8" in url:
                    return url
            except Exception:
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

    def destroy(self):
        pass