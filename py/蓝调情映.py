# -*- coding: utf-8 -*-
"""
蓝调情映 - TVBox爬虫源
站点: https://ldapexfast.xyz/
"""

import re
import json
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://ldapexfast.xyz"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host
        }
        self.classes = [
            {"type_id": "23", "type_name": "女同性爱"},
            {"type_id": "29", "type_name": "人妖视频"},
            {"type_id": "31", "type_name": "捆绑调教"},
            {"type_id": "33", "type_name": "日本女优"},
            {"type_id": "35", "type_name": "中文字幕"},
            {"type_id": "39", "type_name": "欧美视频"},
            {"type_id": "43", "type_name": "国产精品"},
            {"type_id": "45", "type_name": "明星换脸"},
            {"type_id": "47", "type_name": "萝莉少女"},
            {"type_id": "49", "type_name": "网红主播"},
            {"type_id": "53", "type_name": "传媒拍摄"},
            {"type_id": "55", "type_name": "三级伦理"},
            {"type_id": "57", "type_name": "网暴黑料"},
            {"type_id": "59", "type_name": "激情动漫"},
            {"type_id": "61", "type_name": "全景视角"},
            {"type_id": "63", "type_name": "解说类"}
        ]
        self.filters = {}

    def getName(self):
        return "蓝调情映"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            res = self.fetch(self.host, headers=self.headers)
            if res:
                html = self._get_text(res)
                if html:
                    items = self._parse_list(html)
                    if items:
                        return {"list": items[:20]}
            return {"list": []}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend={}):
        try:
            page = pg or "1"
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
            res = self.fetch(url, headers=self.headers)
            if not res:
                return {"list": [], "page": int(page), "pagecount": 0, "limit": 20}
            html = self._get_text(res)
            if not html:
                return {"list": [], "page": int(page), "pagecount": 0, "limit": 20}
            items = self._parse_list(html)
            total_pages = self._parse_total_pages(html)
            return {
                "list": items,
                "page": int(page),
                "pagecount": total_pages or 99,
                "limit": 20,
                "total": 0
            }
        except Exception:
            return {"list": [], "page": int(pg or "1"), "pagecount": 0, "limit": 20}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        try:
            vod_id = str(ids[0])
            url = f"{self.host}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
            res = self.fetch(url, headers=self.headers)
            if not res:
                return {"list": []}
            html = self._get_text(res)
            if not html:
                return {"list": []}

            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            vod_name = title_match.group(1).strip() if title_match else "视频"

            cover_match = re.search(r'<img[^>]+class="[^"]*item-img[^"]*"[^>]+src="([^"]+)"', html)
            vod_pic = cover_match.group(1) if cover_match else ""

            # 先定位 player_aaaa，再从里面提取 url
            start = html.find('var player_aaaa=')
            if start == -1:
                start = html.find('var player_aaaa =')
            if start != -1:
                segment = html[start:start+2000]
                url_match = re.search(r'"url"\s*:\s*"([^"]+)"', segment)
                if url_match:
                    play_url = url_match.group(1).replace('\\/', '/')
                    # 过滤掉 maccms 配置中的 test.cn
                    if 'test.cn' not in play_url and play_url.startswith('http'):
                        vod = {
                            "vod_id": vod_id,
                            "vod_name": vod_name,
                            "vod_pic": vod_pic,
                            "vod_remarks": "",
                            "vod_content": "",
                            "vod_play_from": "直链",
                            "vod_play_url": f"直链${play_url}"
                        }
                        return {"list": [vod]}

            return {"list": []}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            url = f"{self.host}/index.php/vod/search.html"
            res = self.post(url, data={"wd": key}, headers=self.headers)
            if not res:
                return {"list": [], "page": int(pg)}
            html = self._get_text(res)
            if not html:
                return {"list": [], "page": int(pg)}
            items = self._parse_list(html)
            return {"list": items, "page": int(pg)}
        except Exception:
            return {"list": [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags=""):
        if not id:
            return {"parse": 1, "url": ""}
        if id.endswith((".m3u8", ".mp4", ".m3u")) or "m3u8" in id:
            return {"parse": 0, "url": id, "header": self.headers}
        return {"parse": 1, "url": id, "header": self.headers}

    def _get_text(self, res):
        if hasattr(res, 'text'):
            return res.text
        if hasattr(res, 'content'):
            try:
                return res.content.decode('utf-8')
            except:
                return str(res.content)
        if isinstance(res, str):
            return res
        return str(res)

    def _parse_list(self, html):
        items = []
        pattern = r'<div class="item">.*?<a href="([^"]+)".*?<img alt="([^"]*)" src="([^"]+)".*?<div class="item-meta meta-time"><span[^>]*>.*?</span>([^<]*)</div>.*?<div class="item-meta meta-rate[^>]*>([^<]*)</div>'
        matches = re.findall(pattern, html, re.DOTALL)

        if not matches:
            pattern2 = r'<div class="item">.*?<a href="([^"]+)".*?<img[^>]+src="([^"]+)".*?<div class="item-title">([^<]+)</div>'
            matches2 = re.findall(pattern2, html, re.DOTALL)
            for match in matches2:
                link, pic, title = match
                vod_id_match = re.search(r'/id/(\d+)', link)
                if vod_id_match:
                    vod_id = vod_id_match.group(1)
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": ""
                    })
            return items

        for match in matches:
            link, title, pic, duration, rate = match
            if not link or not title:
                continue
            vod_id_match = re.search(r'/id/(\d+)', link)
            if not vod_id_match:
                continue
            vod_id = vod_id_match.group(1)
            items.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": f"{duration.strip()} | {rate.strip()}分"
            })
        return items

    def _parse_total_pages(self, html):
        match = re.search(r'<a[^>]*href="[^"]*page/(\d+)\.html"[^>]*>(\d+)</a>', html)
        if match:
            return int(match.group(2))
        match = re.search(r'<span[^>]*>.*?</span>\s*<a[^>]*href="[^"]*page/(\d+)\.html"', html)
        if match:
            return int(match.group(1))
        return 99