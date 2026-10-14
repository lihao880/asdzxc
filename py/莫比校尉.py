# -*- coding: utf-8 -*-
# 站点: 莫比校尉 (https://ccc.mb888.sbs)
# 类型: WordPress 影视站
# 特性: 纯 HTML 解析，无加密，直接提取 m3u8 直链
# 作者: AI Assistant

import re
import urllib.parse
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def getName(self):
        return "莫比校尉"

    def __init__(self):
        self.site_url = "https://ccc.mb888.sbs"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": self.site_url + "/"
        }
        self.classes = [
            {"type_id": "904c54", "type_name": "91探花"},
            {"type_id": "1353a5", "type_name": "萝莉少女"},
            {"type_id": "55cff4", "type_name": "亚洲无码"},
            {"type_id": "474799", "type_name": "欧美精品"},
            {"type_id": "ae3fd9", "type_name": "主播直播"},
            {"type_id": "0710c7", "type_name": "闷骚护士"},
            {"type_id": "2e0b56", "type_name": "女优系列"},
            {"type_id": "17c210", "type_name": "Cosplay"},
            {"type_id": "ea847e", "type_name": "素人自拍"},
            {"type_id": "8151d5", "type_name": "多人多P"},
            {"type_id": "bca889", "type_name": "精品推荐"},
            {"type_id": "96fe0c", "type_name": "韩国御姐"},
            {"type_id": "f73275", "type_name": "风情旗袍"},
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            res = self.fetch(self.site_url + "/", headers=self.headers)
            html = res.text
            return {"list": self._parse_home_list(html)}
        except Exception as e:
            self.log({"action": "homeVideoContent_error", "error": str(e)})
            return {"list": []}

    def _parse_home_list(self, html):
        items = []
        pattern = r'<div id="gridbit-grid-post-\d+"[^>]*>.*?<a href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h3[^>]*>.*?<a[^>]*>([^<]+)</a>.*?</h3>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            url, pic, title = match
            if url and title:
                post_id = re.search(r'/a/(\d+)\.htm', url)
                vid = post_id.group(1) if post_id else url
                items.append({
                    "vod_id": str(vid),
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return items

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if page == 1:
            url = f"{self.site_url}/{tid}"
        else:
            url = f"{self.site_url}/{tid}/page/{page}"
        try:
            res = self.fetch(url, headers=self.headers)
            html = res.text
            items = self._parse_category_list(html)
            pagecount = self._parse_total_pages(html)
            return {
                "list": items,
                "page": page,
                "pagecount": pagecount if pagecount > 0 else 1,
                "limit": 20,
                "total": 0
            }
        except Exception as e:
            self.log({"action": "categoryContent_error", "tid": tid, "pg": pg, "error": str(e)})
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

    def _parse_category_list(self, html):
        items = []
        pattern = r'<div id="gridbit-grid-post-(\d+)"[^>]*>.*?<a href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h3[^>]*>.*?<a[^>]*>([^<]+)</a>.*?</h3>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            post_id, url, pic, title = match
            if url and title:
                items.append({
                    "vod_id": str(post_id),
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return items

    def _parse_total_pages(self, html):
        pattern = r'<a class="page-numbers"[^>]*href="[^"]*/page/(\d+)"[^>]*>(\d+)</a>'
        matches = re.findall(pattern, html)
        if matches:
            max_page = 0
            for _, num in matches:
                try:
                    p = int(num)
                    if p > max_page:
                        max_page = p
                except:
                    pass
            return max_page
        pattern2 = r'<a class="page-numbers"[^>]*>(\d+)</a>\s*<a class="next page-numbers"'
        match2 = re.search(pattern2, html)
        if match2:
            try:
                return int(match2.group(1))
            except:
                pass
        return 1

    def detailContent(self, ids):
        raw = str(ids[0])
        parts = raw.split('|$|')
        post_id = parts[0]
        vod_name = parts[1] if len(parts) > 1 else ""
        vod_pic = parts[2] if len(parts) > 2 else ""
        vod_remark = parts[3] if len(parts) > 3 else ""
        play_url = parts[4] if len(parts) > 4 else f"{self.site_url}/a/{post_id}.htm"
        if not play_url or play_url == post_id:
            play_url = f"{self.site_url}/a/{post_id}.htm"
        if not vod_name or vod_name == "视频":
            try:
                res = self.fetch(play_url, headers=self.headers)
                html = res.text
                title_match = re.search(r'<title>([^<]+)</title>', html)
                if title_match:
                    full_title = title_match.group(1).strip()
                    vod_name = re.sub(r'\s*[-|—]\s*莫比校尉\s*$', '', full_title).strip()
                if not vod_name:
                    h1_match = re.search(r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>([^<]+)</h1>', html)
                    if h1_match:
                        vod_name = h1_match.group(1).strip()
            except:
                pass
        vod = {
            "vod_id": post_id,
            "vod_name": vod_name or "视频",
            "vod_pic": vod_pic,
            "vod_remarks": vod_remark or "",
            "vod_content": vod_remark or "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}"
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        if id.endswith((".m3u8", ".mp4")):
            return {"parse": 0, "url": id, "header": self.headers}
        try:
            res = self.fetch(id, headers=self.headers)
            html = res.text
            iframe_pattern = r'<iframe[^>]*src="([^"]+)"[^>]*>'
            iframe_matches = re.findall(iframe_pattern, html)
            for src in iframe_matches:
                if "t.php" in src and "url=" in src:
                    parsed = urllib.parse.urlparse(src)
                    params = urllib.parse.parse_qs(parsed.query)
                    if "url" in params:
                        real_url = params["url"][0]
                        if real_url.endswith((".m3u8", ".mp4")):
                            return {"parse": 0, "url": real_url, "header": self.headers}
                if src.endswith((".m3u8", ".mp4")):
                    return {"parse": 0, "url": src, "header": self.headers}
            media_pattern = r'https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*'
            media_matches = re.findall(media_pattern, html)
            if media_matches:
                return {"parse": 0, "url": media_matches[0], "header": self.headers}
            now_pattern = r'now\s*[=:]\s*["\']([^"\']+)["\']'
            now_match = re.search(now_pattern, html)
            if now_match:
                url = now_match.group(1)
                if url.endswith((".m3u8", ".mp4")):
                    return {"parse": 0, "url": url, "header": self.headers}
            player_pattern = r'player_aaaa\s*=\s*({[^;]+});'
            player_match = re.search(player_pattern, html, re.DOTALL)
            if player_match:
                try:
                    import json
                    js_obj = player_match.group(1)
                    js_obj = js_obj.replace("'", '"')
                    js_obj = re.sub(r'//.*?\n', '', js_obj)
                    data = json.loads(js_obj)
                    if "url" in data:
                        raw_url = data["url"]
                        if "encrypt" in data and data["encrypt"] == 1:
                            raw_url = urllib.parse.unquote(raw_url)
                        if raw_url.endswith((".m3u8", ".mp4")):
                            return {"parse": 0, "url": raw_url, "header": self.headers}
                except:
                    pass
            return {"parse": 1, "url": id, "header": self.headers}
        except Exception as e:
            self.log({"action": "playerContent_error", "url": id, "error": str(e)})
            return {"parse": 1, "url": id, "header": self.headers}

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
            url = f"{self.site_url}/?s={urllib.parse.quote(key)}"
            if page > 1:
                url += f"&paged={page}"
            res = self.fetch(url, headers=self.headers)
            html = res.text
            items = []
            pattern = r'<div id="gridbit-grid-post-(\d+)"[^>]*>.*?<a href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h3[^>]*>.*?<a[^>]*>([^<]+)</a>.*?</h3>'
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                post_id, url, pic, title = match
                if url and title:
                    items.append({
                        "vod_id": str(post_id),
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": ""
                    })
            return {"list": items, "page": page}
        except Exception as e:
            self.log({"action": "searchContent_error", "key": key, "error": str(e)})
            return {"list": [], "page": int(pg) if pg else 1}