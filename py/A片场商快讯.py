# coding: utf-8
# TVBox/FongMi 爬虫 - A片场商快讯
# 站点: https://214841.apiankx011.top/kuaixun/
# 说明: 无广告过滤版本

import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://214841.apiankx011.top/kuaixun"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }
        self.classes = [
            {"type_id": "27", "type_name": "国产乱伦"},
            {"type_id": "28", "type_name": "网曝黑料"},
            {"type_id": "29", "type_name": "自拍偷拍"},
            {"type_id": "30", "type_name": "国产传媒"},
            {"type_id": "31", "type_name": "国产精品"},
            {"type_id": "32", "type_name": "探花精品"},
            {"type_id": "33", "type_name": "网红主播"},
            {"type_id": "34", "type_name": "AI换脸"},
            {"type_id": "35", "type_name": "同性恋"},
            {"type_id": "36", "type_name": "3D动漫"},
            {"type_id": "37", "type_name": "欧美精品"},
            {"type_id": "38", "type_name": "韩国主播"},
            {"type_id": "39", "type_name": "高美传媒"},
            {"type_id": "40", "type_name": "国产人妻"},
            {"type_id": "41", "type_name": "麻豆传媒"},
            {"type_id": "42", "type_name": "国产SM"},
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}

    def getName(self):
        return "A片场商快讯"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        url = f"{self.host}/"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            items = re.findall(
                r'<a[^>]*class="thumbnail"[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-original="([^"]+)"[^>]*>.*?<h5><a[^>]*href="[^"]*"[^>]*>([^<]+)</a></h5>.*?<p[^>]*class="vodtitle">(.*?)</p>',
                html, re.S
            )
            videos = []
            for href, pic, title, info_html in items:
                if not href:
                    continue
                vid = re.search(r'/id/(\d+)/', href)
                vid = vid.group(1) if vid else ""
                if not vid:
                    continue
                info = re.sub(r'<[^>]+>', '', info_html).strip()
                parts = info.split(" - ")
                remarks = parts[0].strip() if parts else info
                videos.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": pic.strip(),
                    "vod_remarks": remarks
                })
            return {"list": videos[:30]}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or 1
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = resp.text
            items = re.findall(
                r'<a[^>]*class="thumbnail"[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-original="([^"]+)"[^>]*>.*?<h5><a[^>]*href="[^"]*"[^>]*>([^<]+)</a></h5>.*?<p[^>]*class="vodtitle">(.*?)</p>',
                html, re.S
            )
            videos = []
            for href, pic, title, info_html in items:
                if not href:
                    continue
                vid = re.search(r'/id/(\d+)/', href)
                vid = vid.group(1) if vid else ""
                if not vid:
                    continue
                info = re.sub(r'<[^>]+>', '', info_html).strip()
                parts = info.split(" - ")
                remarks = parts[0].strip() if parts else info
                videos.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": pic.strip(),
                    "vod_remarks": remarks
                })
            pagecount = 1
            m = re.search(r'共(\d+)页', html)
            if m:
                pagecount = int(m.group(1))
            else:
                page_numbers = re.findall(r'<a[^>]*href="[^"]*page/(\d+)\.html[^"]*"[^>]*>(\d+)</a>', html)
                if page_numbers:
                    max_page = max(int(p) for _, p in page_numbers if p.isdigit())
                    pagecount = max_page if max_page > 1 else 1
            return {
                "list": videos,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0]) if isinstance(ids, list) else str(ids)
        detail_url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        try:
            resp = self.fetch(detail_url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return self._detail_from_play_page(vid)
            html = resp.text
            title = ""
            m = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>', html)
            if m:
                title = m.group(1).strip()
            if not title:
                m = re.search(r'<title>([^<]+)</title>', html)
                if m:
                    title = m.group(1).replace("在线播放--A片场商快讯", "").replace("-A片场商快讯", "").strip()
            pic = ""
            m = re.search(r'<img[^>]*class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]+)"', html)
            if m:
                pic = m.group(1)
            if not pic:
                m = re.search(r'data-original="([^"]+)"', html)
                if m:
                    pic = m.group(1)
            content = ""
            m = re.search(r'<span[^>]*class="[^"]*detail-content[^"]*"[^>]*>([^<]*)</span>', html)
            if m:
                content = m.group(1).strip()
            play_from_list = []
            play_url_list = []
            tab_pattern = r'<li><a[^>]*href="#playlist(\d+)"[^>]*>([^<]+)</a></li>'
            tabs = re.findall(tab_pattern, html)
            if not tabs:
                tabs = [("1", "默认")]
            for tab_id, tab_name in tabs:
                playlist_pattern = rf'<div[^>]*id="playlist{tab_id}"[^>]*>.*?<ul[^>]*class="[^"]*stui-content__playlist[^"]*"[^>]*>(.*?)</ul>'
                playlist_match = re.search(playlist_pattern, html, re.DOTALL)
                if playlist_match:
                    playlist_html = playlist_match.group(1)
                    ep_pattern = r'<li[^>]*><a[^>]*href="([^"]+)"[^>]*>([^<]+)</a></li>'
                    eps = re.findall(ep_pattern, playlist_html)
                    if eps:
                        play_from_list.append(tab_name.strip())
                        ep_urls = []
                        for ep_href, ep_name in eps:
                            sid_nid = re.search(r'/sid/(\d+)/nid/(\d+)\.html', ep_href)
                            if sid_nid:
                                ep_urls.append(f"{ep_name.strip()}${vid}|{sid_nid.group(1)}|{sid_nid.group(2)}")
                            else:
                                m2 = re.search(r'/id/(\d+)/', ep_href)
                                if m2:
                                    ep_urls.append(f"{ep_name.strip()}${m2.group(1)}|1|1")
                        if ep_urls:
                            play_url_list.append("#".join(ep_urls))
            if not play_url_list:
                return self._detail_from_play_page(vid)
            vod = {
                "vod_id": vid,
                "vod_name": title or "未知标题",
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_content": content,
                "vod_play_from": "$$$".join(play_from_list),
                "vod_play_url": "$$$".join(play_url_list)
            }
            return {"list": [vod]}
        except Exception:
            return self._detail_from_play_page(vid)

    def _detail_from_play_page(self, vid):
        url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            title = ""
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                title = m.group(1).replace("在线播放--A片场商快讯", "").strip()
            pic = ""
            m = re.search(r'data-original="([^"]+)"', html)
            if m:
                pic = m.group(1)
            play_url = ""
            m = re.search(r'"url":"([^"]+)"', html)
            if m:
                play_url = m.group(1).replace("\\/", "/")
            if not play_url:
                m = re.search(r'"url"\s*:\s*"([^"]+)"', html)
                if m:
                    play_url = m.group(1).replace("\\/", "/")
            if play_url:
                return {
                    "list": [{
                        "vod_id": vid,
                        "vod_name": title or "未知标题",
                        "vod_pic": pic,
                        "vod_remarks": "",
                        "vod_content": "",
                        "vod_play_from": "播放",
                        "vod_play_url": f"正片${play_url}"
                    }]
                }
            return {"list": []}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        page = pg or 1
        url = f"{self.host}/index.php/vod/search.html"
        try:
            resp = self.post(url, data={"wd": key}, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": int(page)}
            html = resp.text
            items = re.findall(
                r'<a[^>]*class="thumbnail"[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-original="([^"]+)"[^>]*>.*?<h5><a[^>]*href="[^"]*"[^>]*>([^<]+)</a></h5>.*?<p[^>]*class="vodtitle">(.*?)</p>',
                html, re.S
            )
            videos = []
            for href, pic, title, info_html in items:
                if not href:
                    continue
                vid = re.search(r'/id/(\d+)/', href)
                vid = vid.group(1) if vid else ""
                if not vid:
                    continue
                info = re.sub(r'<[^>]+>', '', info_html).strip()
                parts = info.split(" - ")
                remarks = parts[0].strip() if parts else info
                videos.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": pic.strip(),
                    "vod_remarks": remarks
                })
            return {"list": videos, "page": int(page)}
        except Exception:
            return {"list": [], "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        play_url = str(id).strip()
        if play_url.startswith("http"):
            if ".m3u8" in play_url:
                return {
                    "parse": 0,
                    "url": play_url,
                    "header": {"User-Agent": self.headers["User-Agent"]}
                }
            return {"parse": 0, "url": play_url, "header": {"User-Agent": self.headers["User-Agent"]}}
        return {"parse": 1, "url": play_url, "header": self.headers}

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass