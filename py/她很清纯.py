# -*- coding: utf-8 -*-
# 站点: 她很清纯
# 域名: https://xn--chqx48jrui00b.thrapidrealmnet.site/
# 类型: MacCMS标准影视站

import re
import json
import urllib.parse
import posixpath
from urllib.parse import quote, urlencode
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xn--chqx48jrui00b.thrapidrealmnet.site"
        self.site_name = "她很清纯"
        self.classes = [
            {"type_id": "43", "type_name": "国产"},
            {"type_id": "35", "type_name": "中文字幕"},
            {"type_id": "31", "type_name": "捆绑调教"},
            {"type_id": "47", "type_name": "萝莉"},
            {"type_id": "33", "type_name": "日韩"},
            {"type_id": "39", "type_name": "欧美"},
            {"type_id": "55", "type_name": "三级剧情"}
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }

    def getName(self):
        return "她很清纯"

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
        return {"list": items[:12]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg) if pg else "1"
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        page_count = self._parse_page_count(html)
        return {
            "list": items,
            "page": int(pg),
            "pagecount": page_count or 50,
            "limit": 20,
            "total": (page_count or 50) * 20,
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        if isinstance(ids, list):
            vid = str(ids[0])
        else:
            vid = str(ids)
        
        detail_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        html = self._fetch_html(detail_url)
        
        vod_name = ""
        title_match = re.search(r'<title>([^<]+)', html)
        if title_match:
            vod_name = title_match.group(1).replace(" 在线观看", "").strip()
        
        vod_pic = ""
        pic_match = re.search(r'<div class="thumb"[^>]*>.*?<img[^>]*src="([^"]+)"', html, re.DOTALL)
        if pic_match:
            vod_pic = pic_match.group(1)
        
        play_url = self._extract_m3u8_from_html(html)
        
        if play_url:
            vod = {
                "vod_id": vid,
                "vod_name": vod_name or f"视频{vid}",
                "vod_pic": vod_pic,
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "在线播放",
                "vod_play_url": f"正片${play_url}",
            }
        else:
            vod = {
                "vod_id": vid,
                "vod_name": vod_name or f"视频{vid}",
                "vod_pic": vod_pic,
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "在线播放",
                "vod_play_url": f"正片${detail_url}",
            }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = str(pg) if pg else "1"
        url = f"{self.host}/index.php/vod/search/wd/{quote(key)}.html"
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
        if id and id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0, 
                "url": self._m3u8_proxy_url(id), 
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
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

    def localProxy(self, param):
        """m3u8本地代理 - 广告分片过滤"""
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
            if resp:
                if hasattr(resp, "text"):
                    return resp.text
                if hasattr(resp, "content"):
                    return resp.content.decode("utf-8", errors="ignore")
                if isinstance(resp, str):
                    return resp
            return ""
        except Exception as e:
            return ""

    def _parse_video_list(self, html):
        items = []
        if not html:
            return items
        
        thumb_blocks = re.findall(r'<div class="thumb">(.*?)</div>', html, re.DOTALL)
        for block in thumb_blocks:
            link_match = re.search(r'<a href="([^"]+)"[^>]*title="([^"]*)"', block)
            if not link_match:
                continue
            link = link_match.group(1)
            title = link_match.group(2).strip()
            
            img_match = re.search(r'<img[^>]*src="([^"]+)"', block)
            pic = img_match.group(1) if img_match else ""
            
            date_match = re.search(r'<div class="date">([^<]+)</div>', block)
            duration = date_match.group(1).strip() if date_match else ""
            
            if "play/id/" in link:
                vid_match = re.search(r'/id/(\d+)/', link)
                if vid_match:
                    vid = vid_match.group(1)
                    items.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": duration
                    })
        return items

    def _parse_page_count(self, html):
        if not html:
            return 1
        
        # 方法1: 直接提取所有 page/n.html 中的数字
        page_links = re.findall(r'/page/(\d+)\.html', html)
        if page_links:
            max_page = max(int(p) for p in page_links)
            return max_page
        
        # 方法2: 匹配分页链接中的数字
        pattern = r'<a[^>]+href="[^"]*page/(\d+)\.html"[^>]*>'
        matches = re.findall(pattern, html)
        if matches:
            max_page = max(int(m) for m in matches)
            return max_page
        
        # 方法3: 匹配 "Page X of Y"
        page_match = re.search(r'Page\s+\d+\s+of\s+(\d+)', html)
        if page_match:
            return int(page_match.group(1))
        
        # 方法4: 匹配页码显示区域
        nav_match = re.search(r'<div class="navbar">.*?</div>', html, re.DOTALL)
        if nav_match:
            nav_html = nav_match.group(0)
            num_matches = re.findall(r'>\s*(\d+)\s*<', nav_html)
            if num_matches:
                return max(int(n) for n in num_matches)
        
        return 1
    def _extract_m3u8_from_html(self, html):
        if not html:
            return None
        
        # 方法1: 使用括号计数提取 player_aaaa JSON 对象
        start = html.find('var player_aaaa=')
        if start != -1:
            start = html.find('{', start)
            if start != -1:
                brace_count = 0
                end = start
                for i in range(start, len(html)):
                    if html[i] == '{':
                        brace_count += 1
                    elif html[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break
                if end > start:
                    json_str = html[start:end]
                    try:
                        data = json.loads(json_str)
                        url = data.get("url", "")
                        if url and url.startswith("http"):
                            return url
                    except:
                        pass
        
        # 方法2: 直接查找m3u8链接
        pattern = r'https?://[^"\']+\.m3u8[^"\']*'
        match = re.search(pattern, html)
        if match:
            return match.group(0)
        return None