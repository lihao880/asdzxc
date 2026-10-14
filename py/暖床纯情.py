# coding: utf-8
"""
站点: 暖床纯情
域名: https://qcvh.nccq48.cfd/
类型: HTML影视站 (自定义模板)
版本: 1.0
特点: 多分区分类、HLS播放代理、分页列表、搜索
"""
import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://qcvh.nccq48.cfd"
        self.play_proxy = "https://m.892539.xyz/play.php"
        self.site_id = "13"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        self._init_classes()

    def _init_classes(self):
        self.classes = [
            {"type_id": "79491059", "type_name": "国产精品"},
            {"type_id": "79721059", "type_name": "自拍偷拍"},
            {"type_id": "79461059", "type_name": "日韩无码"},
            {"type_id": "79481059", "type_name": "欧美精品"},
            {"type_id": "79681059", "type_name": "日韩精品"},
            {"type_id": "79871059", "type_name": "大秀视频"},
            {"type_id": "79631059", "type_name": "中文字幕"},
            {"type_id": "79651059", "type_name": "动漫精品"},
            {"type_id": "79691079", "type_name": "国模私拍"},
            {"type_id": "79681079", "type_name": "欧美情色"},
            {"type_id": "79651079", "type_name": "中文字幕"},
            {"type_id": "79471079", "type_name": "日本无码"},
            {"type_id": "79721079", "type_name": "韩国伦理"},
            {"type_id": "79461079", "type_name": "国产情色"},
            {"type_id": "79661079", "type_name": "网红主播"},
            {"type_id": "79671079", "type_name": "成人动漫"},
            {"type_id": "79671129", "type_name": "国产色情"},
            {"type_id": "79681129", "type_name": "主播直播"},
            {"type_id": "79651129", "type_name": "精品推荐"},
            {"type_id": "79751129", "type_name": "欧美精品"},
            {"type_id": "79821129", "type_name": "日本精品"},
            {"type_id": "79921129", "type_name": "91探花"},
            {"type_id": "79791129", "type_name": "自拍偷拍"},
            {"type_id": "80041129", "type_name": "传媒出品"},
            {"type_id": "79661049", "type_name": "动漫精品"},
            {"type_id": "79701049", "type_name": "三级自慰"},
            {"type_id": "79461049", "type_name": "国产自拍"},
            {"type_id": "79471049", "type_name": "欧美极品"},
            {"type_id": "79711049", "type_name": "强奸乱伦"},
            {"type_id": "79481049", "type_name": "日韩无码"},
            {"type_id": "79651049", "type_name": "中文字幕"},
            {"type_id": "79671049", "type_name": "极骚萝莉"},
            {"type_id": "79461039", "type_name": "亚洲情色"},
            {"type_id": "79491039", "type_name": "无码专区"},
            {"type_id": "79541039", "type_name": "中文字幕"},
            {"type_id": "79511039", "type_name": "熟女人妻"},
            {"type_id": "79501039", "type_name": "欧美性爱"},
            {"type_id": "79471039", "type_name": "国产主播"},
            {"type_id": "79521039", "type_name": "强奸乱伦"},
            {"type_id": "79481039", "type_name": "国产自拍"},
            {"type_id": "79460940", "type_name": "国产专区"},
            {"type_id": "79470940", "type_name": "日本有码"},
            {"type_id": "79480940", "type_name": "日本无码"},
            {"type_id": "79490940", "type_name": "欧美色情"},
            {"type_id": "79500940", "type_name": "传媒作品"},
            {"type_id": "79510940", "type_name": "探花直播"},
            {"type_id": "79520940", "type_name": "网黄女神"},
            {"type_id": "79530940", "type_name": "绿帽淫妻"},
        ]
        self.filters = {}

    def getName(self):
        return "暖床纯情"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self.categoryContent("79461059", "1", False, {})

    def _fetch_html(self, url):
        try:
            resp = self.fetch(url, headers=self.headers)
            if resp and resp.status_code == 200:
                return resp.text
            return ""
        except Exception as e:
            self.log({"action": "fetch_fail", "url": url, "error": str(e)})
            return ""

    def _parse_list_items(self, html):
        items = []
        if not html:
            return items

        list_pattern = r'<ul[^>]*class="[^"]*tile-list[^"]*"[^>]*>(.*?)</ul>'
        ul_match = re.search(list_pattern, html, re.DOTALL | re.IGNORECASE)
        if not ul_match:
            return items

        ul_content = ul_match.group(1)
        li_pattern = r'<li>(.*?)</li>'
        for li_match in re.finditer(li_pattern, ul_content, re.DOTALL | re.IGNORECASE):
            li = li_match.group(1)
            try:
                a_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', li)
                if not a_match:
                    continue
                href = a_match.group(1)
                title = a_match.group(2).strip()
                if not title:
                    continue

                vid_match = re.search(r'video\.php\?id=(\d+)', href)
                if not vid_match:
                    continue
                vod_id = vid_match.group(1)

                pic = ""
                img_match = re.search(r'<img[^>]*data-original="([^"]*)"', li)
                if img_match:
                    pic = img_match.group(1)
                else:
                    img_match = re.search(r'<img[^>]*src="([^"]*)"', li)
                    if img_match and "loading" not in img_match.group(1).lower():
                        pic = img_match.group(1)

                remark = ""
                remark_match = re.search(r'<span[^>]*class="[^"]*remark[^"]*"[^>]*>(.*?)</span>', li)
                if remark_match:
                    remark = remark_match.group(1).strip()

                items.append({
                    "vod_id": str(vod_id),
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
            except Exception as e:
                self.log({"action": "parse_item_fail", "error": str(e)})
                continue

        return items

    def _parse_pagination(self, html):
        page = 1
        pagecount = 1
        total = 0

        pg_pattern = r'<div[^>]*class="[^"]*pg-strip[^"]*"[^>]*>(.*?)</div>'
        pg_match = re.search(pg_pattern, html, re.DOTALL | re.IGNORECASE)
        if not pg_match:
            return page, pagecount, total

        pg_html = pg_match.group(1)

        current_match = re.search(r'<a[^>]*class="[^"]*pg-on[^"]*"[^>]*>(\d+)</a>', pg_html)
        if current_match:
            page = int(current_match.group(1))

        max_page = 1
        for num_match in re.finditer(r'<a[^>]*href="[^"]*page=(\d+)"[^>]*>', pg_html):
            p = int(num_match.group(1))
            if p > max_page:
                max_page = p
        pagecount = max_page

        total_match = re.search(r'共(\d+)部', html)
        if total_match:
            total = int(total_match.group(1))
        else:
            total = pagecount * 20

        return page, pagecount, total

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/list.php?id={tid}&page={page}"

        html = self._fetch_html(url)
        items = self._parse_list_items(html)

        if not items:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

        page_num, pagecount, total = self._parse_pagination(html)
        if total == 0 and len(items) > 0:
            total = len(items) * 50

        return {
            "list": items,
            "page": page_num,
            "pagecount": pagecount,
            "limit": 20,
            "total": total
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}

        if isinstance(ids, list):
            vod_id = str(ids[0]) if ids else ""
        else:
            vod_id = str(ids)
        if not vod_id:
            return {"list": []}

        url = f"{self.host}/video.php?id={vod_id}"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        title = ""
        title_match = re.search(r'<div[^>]*class="[^"]*item-banner[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
        if title_match:
            banner = title_match.group(1)
            text_match = re.search(r'>(.*?)</b>', banner)
            if text_match:
                title = text_match.group(1).strip()
            else:
                title = re.sub(r'<[^>]+>', '', banner).strip()
                title = re.sub(r'\[.*?\]', '', title).strip()

        pic = ""
        img_match = re.search(r'<img[^>]*data-original="([^"]*)"', html)
        if img_match:
            pic = img_match.group(1)
        else:
            img_match = re.search(r'<video[^>]*poster="([^"]*)"', html)
            if img_match:
                pic = img_match.group(1)

        play_url = ""
        hls_match = re.search(r"hls\.loadSource\('([^']+)'\)", html)
        if hls_match:
            play_url = hls_match.group(1)

        if not play_url:
            src_match = re.search(r'<video[^>]*src="([^"]*)"', html)
            if src_match:
                play_url = src_match.group(1)

        if play_url:
            vod_play_from = "播放"
            vod_play_url = f"正片${play_url}"
        else:
            vod_play_from = "播放"
            vod_play_url = f"正片${self.play_proxy}?site_id={self.site_id}&source_id={vod_id}"

        content = ""
        content_match = re.search(r'<div[^>]*class="[^"]*vod-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
        if content_match:
            content = re.sub(r'<[^>]+>', '', content_match.group(1)).strip()

        vod = {
            "vod_id": vod_id,
            "vod_name": title or f"视频 {vod_id}",
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": content,
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }

        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}

        page = pg or "1"
        search_type = "1"
        encoded_key = urllib.parse.quote(key)
        url = f"{self.host}/search.php?content={encoded_key}&type={search_type}"

        html = self._fetch_html(url)
        items = self._parse_list_items(html)

        if not items or "没有找到" in html or "搜索无结果" in html or "暂无数据" in html:
            return {"list": [], "page": int(page)}

        page_num, pagecount, total = self._parse_pagination(html)

        return {
            "list": items,
            "page": page_num
        }

    def playerContent(self, flag, id, vipFlags):
        # 确保 id 为字符串
        id = str(id) if id is not None else ""
        if not id:
            return {"parse": 1, "url": ""}

        # 如果是 play.php 代理地址或纯数字 ID，请求获取 m3u8
        if "play.php" in id or id.isdigit():
            if id.isdigit():
                play_url = f"{self.play_proxy}?site_id={self.site_id}&source_id={id}"
            else:
                play_url = id

            # 请求 play.php 获取 m3u8 内容
            try:
                resp = self.fetch(play_url, headers=self.headers)
                if resp and resp.status_code == 200:
                    content = resp.text
                    if "#EXTM3U" in content:
                        # play_url 本身就是 m3u8 地址，直接返回
                        return {
                            "parse": 0,
                            "url": play_url,
                            "header": {
                                "User-Agent": self.headers["User-Agent"],
                                "Referer": self.host + "/"
                            }
                        }
            except Exception as e:
                self.log({"action": "player_fetch_fail", "url": play_url, "error": str(e)})

            # 即使请求失败，也尝试返回 play_url 让壳端处理
            return {
                "parse": 0,
                "url": play_url,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/"
                }
            }

        # 如果已经是完整的 m3u8/mp4 地址
        if id.startswith("http"):
            if ".m3u8" in id.lower() or ".mp4" in id.lower():
                return {
                    "parse": 0,
                    "url": id,
                    "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": self.host + "/"
                    }
                }

        # 降级嗅探
        return {
            "parse": 1,
            "url": id,
            "header": self.headers
        }

    def localProxy(self, param):
        url = param.get("url", "")
        if not url:
            return [400, "text/plain", b"missing url"]

        if ".m3u8" in url.lower() or "play.php" in url:
            try:
                resp = self.fetch(url, headers=self.headers)
                if resp and resp.status_code == 200:
                    content = resp.content
                    text = content.decode("utf-8", errors="ignore")
                    if "#EXTM3U" in text:
                        cleaned = self._clean_m3u8(text, url)
                        return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
                    return [200, "text/plain", content]
            except Exception as e:
                self.log({"action": "proxy_fail", "url": url, "error": str(e)})
                return [500, "text/plain", b"proxy error"]

        try:
            resp = self.fetch(url, headers=self.headers)
            if resp and resp.status_code == 200:
                content = resp.content
                if content[:4] == b'\xff\xd8\xff\xe0' or content[:4] == b'\xff\xd8\xff\xe1':
                    return [200, "image/jpeg", content]
                if content[:8] == b'\x89PNG\r\n\x1a\n':
                    return [200, "image/png", content]
                if content[:6] == b'GIF89a':
                    return [200, "image/gif", content]
                if content[:4] == b'RIFF' and content[8:12] == b'WEBP':
                    return [200, "image/webp", content]
                return [200, "application/octet-stream", content]
        except Exception as e:
            self.log({"action": "proxy_fail", "url": url, "error": str(e)})
            return [500, "text/plain", b"proxy error"]

        return [404, "text/plain", b"not found"]

    def _clean_m3u8(self, text, base_url):
        lines = text.replace("\r", "").split("\n")
        out = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
                    def repl(m):
                        return f'URI="{urllib.parse.urljoin(base_url, m.group(1))}"'
                    line = re.sub(r'URI="([^"]+)"', repl, line)
                out.append(line)
            else:
                full_url = urllib.parse.urljoin(base_url, line)
                out.append(full_url)
        return "\n".join(out) + "\n"