# coding: utf-8
# 站点: A片.com
# 域名: https://xn--a-pt1c.com/
# 说明: 无广告过滤版本

import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xn--a-pt1c.com"
        self.classes = [
            {"type_id": "1", "type_name": "日韓有碼"},
            {"type_id": "2", "type_name": "國產AV"},
            {"type_id": "5", "type_name": "日韓無碼"},
            {"type_id": "6", "type_name": "強姦亂倫"},
            {"type_id": "7", "type_name": "巨乳美乳"},
            {"type_id": "9", "type_name": "制服誘惑"},
            {"type_id": "10", "type_name": "人妻熟女"},
            {"type_id": "11", "type_name": "調教"},
            {"type_id": "13", "type_name": "中文字幕"},
            {"type_id": "17", "type_name": "國產精品"},
            {"type_id": "30", "type_name": "歐美"},
            {"type_id": "35", "type_name": "FC2系列"},
            {"type_id": "36", "type_name": "探花"},
            {"type_id": "38", "type_name": "麻豆傳媒"},
            {"type_id": "44", "type_name": "童顏巨乳"},
            {"type_id": "45", "type_name": "明星淫夢"},
            {"type_id": "48", "type_name": "國產自拍"},
            {"type_id": "51", "type_name": "有碼精品"},
            {"type_id": "53", "type_name": "絕美少女"},
        ]
        self.filters = {
            "1": [], "2": [], "5": [], "6": [], "7": [], "9": [], "10": [],
            "11": [], "13": [], "17": [], "30": [], "35": [], "36": [], "38": [],
            "44": [], "45": [], "48": [], "51": [], "53": [],
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }

    def getName(self):
        return "A片.com"

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
            resp = self.fetch(self.host, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            items = []
            pattern = r'<div class="col-6 col-sm-4 col-lg-3">.*?<a href="/([^"]+)".*?data-src="([^"]+)".*?alt="([^"]+)".*?<h4 class="title"><a[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches[:20]:
                url_part, pic, alt, title = match
                if url_part:
                    items.append({
                        "vod_id": url_part.replace(".html", ""),
                        "vod_name": title or alt,
                        "vod_pic": urllib.parse.urljoin(self.host, pic) if pic and not pic.startswith("http") else pic,
                        "vod_remarks": "",
                    })
            return {"list": items}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = pg or "1"
            url = f"{self.host}/vodtype/{tid}-{page}.html"
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = resp.text
            items = []
            card_pattern = r'<div class="video-img-box mb-e-20">.*?<a href="/([^"]+\.html)"[^>]*>.*?<img[^>]*(?:data-src|src)="([^"]+)"[^>]*>.*?<h4 class="title">.*?<a[^>]*>([^<]+)</a>'
            matches = re.findall(card_pattern, html, re.DOTALL)
            for url_part, pic, title in matches:
                if url_part:
                    vid = url_part.replace(".html", "").replace("/v/", "")
                    if vid:
                        items.append({
                            "vod_id": vid,
                            "vod_name": title.strip(),
                            "vod_pic": urllib.parse.urljoin(self.host, pic) if pic and not pic.startswith("http") else pic,
                            "vod_remarks": "",
                        })
            if not items:
                backup_pattern = r'<a href="/([^"]+\.html)"[^>]*>.*?<img[^>]*(?:data-src|src)="([^"]+)"[^>]*alt="([^"]*)"'
                matches = re.findall(backup_pattern, html, re.DOTALL)
                for url_part, pic, alt in matches:
                    if url_part and "/v/" in url_part:
                        vid = url_part.replace(".html", "").replace("/v/", "")
                        if vid:
                            items.append({
                                "vod_id": vid,
                                "vod_name": alt.strip() or "未知",
                                "vod_pic": urllib.parse.urljoin(self.host, pic) if pic and not pic.startswith("http") else pic,
                                "vod_remarks": "",
                            })
            pagecount = 1
            last_marker = '最後一頁 »'
            last_pos = html.find(last_marker)
            if last_pos != -1:
                href_pos = html.rfind('href="', 0, last_pos)
                if href_pos != -1:
                    href_end = html.find('"', href_pos + 6)
                    if href_end != -1:
                        href = html[href_pos + 6:href_end]
                        match = re.search(r'/vodtype/' + tid + r'-(\d+)\.html', href)
                        if match:
                            pagecount = int(match.group(1))
            if pagecount <= 1:
                page_nums = re.findall(r'<a[^>]*href="[^"]*page-(\d+)\.html[^"]*"[^>]*>(\d+)</a>', html)
                if page_nums:
                    max_p = max(int(p) for _, p in page_nums if p.isdigit())
                    pagecount = max_p if max_p > 1 else 1
            return {
                "list": items[:20],
                "page": int(page),
                "pagecount": pagecount if pagecount > 1 else 1,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception:
            return {"list": [], "page": int(page or 1), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if ids else ""
            if not vod_id:
                return {"list": []}
            if vod_id.startswith("v/"):
                vod_id = vod_id[2:]
            url = f"{self.host}/v/{vod_id}.html"
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            title_match = re.search(r'<h1>([^<]+)</h1>', html)
            title = title_match.group(1) if title_match else ""
            if not title:
                title_match = re.search(r'<title>([^<]+)</title>', html)
                if title_match:
                    title = title_match.group(1).replace("-A片.com", "").strip()
            pic_match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            pic = pic_match.group(1) if pic_match else ""
            if not pic:
                pic_match = re.search(r'<img[^>]*class="[^"]*vodpic[^"]*"[^>]*src="([^"]+)"', html)
                if pic_match:
                    pic = pic_match.group(1)
            play_url = ""
            play_from = "播放"
            play_match = re.search(r'var\s+player_aaaa\s*=\s*\{[^}]*"url"\s*:\s*"([^"]+)"[^}]*\}', html, re.DOTALL)
            if play_match:
                play_url = play_match.group(1).replace("\\/", "/")
                from_match = re.search(r'"from"\s*:\s*"([^"]+)"', html)
                if from_match:
                    play_from = from_match.group(1)
            if not play_url:
                play_match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
                if play_match:
                    play_url = play_match.group(1).replace("\\/", "/")
            if not play_url:
                play_match = re.search(r'<video[^>]*src="([^"]+)"', html)
                if play_match:
                    play_url = play_match.group(1)
            if not play_url:
                play_match = re.search(r'<iframe[^>]*src="([^"]+)"', html)
                if play_match:
                    play_url = play_match.group(1)
            if not play_url:
                return {"list": []}
            if play_url and not play_url.startswith("http"):
                play_url = urllib.parse.urljoin(self.host, play_url)
            vod = {
                "vod_id": vod_id,
                "vod_name": title or "未知标题",
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_content": "",
                "vod_play_from": play_from,
                "vod_play_url": f"正片${play_url}",
            }
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            page = pg or "1"
            url = f"{self.host}/s.html?wd={urllib.parse.quote(key)}"
            if int(page) > 1:
                url = f"{self.host}/s.html?wd={urllib.parse.quote(key)}&page={page}"
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": int(page)}
            html = resp.text
            if "請不要頻繁操作" in html or "搜索時間間隔為5秒" in html:
                return {"list": [], "page": int(page)}
            items = []
            card_pattern = r'<div class="video-img-box mb-e-20">.*?<a href="/([^"]+\.html)"[^>]*>.*?<img[^>]*(?:data-src|src)="([^"]+)"[^>]*>.*?<h4 class="title">.*?<a[^>]*>([^<]+)</a>'
            matches = re.findall(card_pattern, html, re.DOTALL)
            for url_part, pic, title in matches:
                if url_part and "/v/" in url_part:
                    vid = url_part.replace(".html", "").replace("/v/", "")
                    if vid:
                        items.append({
                            "vod_id": vid,
                            "vod_name": title.strip(),
                            "vod_pic": urllib.parse.urljoin(self.host, pic) if pic and not pic.startswith("http") else pic,
                            "vod_remarks": "",
                        })
            if not items:
                backup_pattern = r'<a href="/([^"]+\.html)"[^>]*>.*?<img[^>]*(?:data-src|src)="([^"]+)"[^>]*alt="([^"]*)"'
                matches = re.findall(backup_pattern, html, re.DOTALL)
                for url_part, pic, alt in matches:
                    if url_part and "/v/" in url_part:
                        vid = url_part.replace(".html", "").replace("/v/", "")
                        if vid:
                            items.append({
                                "vod_id": vid,
                                "vod_name": alt.strip() or "未知",
                                "vod_pic": urllib.parse.urljoin(self.host, pic) if pic and not pic.startswith("http") else pic,
                                "vod_remarks": "",
                            })
            return {"list": items, "page": int(page)}
        except Exception:
            return {"list": [], "page": int(pg or 1)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        play_url = str(id).strip()
        if play_url.startswith("http") and ".m3u8" in play_url:
            return {
                "parse": 0,
                "url": play_url,
                "header": {"User-Agent": self.headers.get("User-Agent", "")},
            }
        return {"parse": 1, "url": play_url, "header": self.headers}

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass