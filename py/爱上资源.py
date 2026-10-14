#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, json
from urllib.parse import quote
try: import requests; from lxml import etree
except: pass

BASE = "https://aszyz.xyz"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": BASE + "/"}

def _get(url):
    try:
        r = requests.get(url, headers=UA, timeout=15)
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except:
        return None

def _fix(u):
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return BASE + u
    return u

class Spider:
    def getDependence(self): return []
    def getName(self): return "ASZYZ"
    def homeVideoContent(self): return self.homeContent({})
    def init(self, extend=""):
        self.site_url = BASE
        self.categories = [
            {"type_id": "1", "type_name": "视频一区"},
            {"type_id": "2", "type_name": "视频二区"},
            {"type_id": "3", "type_name": "视频三区"},
        ]

    def _parse_list(self, html):
        if not html:
            return []
        tree = etree.HTML(html)
        results, seen = [], set()
        items = tree.xpath('//div[contains(@class,"item")]')
        for item in items:
            try:
                a = item.xpath('.//a[contains(@href,"/vod/play/")]')
                if not a:
                    continue
                href = a[0].get("href", "")
                m = re.search(r"/vod/play/id/(\d+)/", href)
                if not m or m.group(1) in seen:
                    continue
                seen.add(m.group(1))
                img = item.xpath('.//img[contains(@class,"data-cover")]')
                pic = ""
                if img:
                    pic = img[0].get("src") or img[0].get("data-src") or ""
                    pic = _fix(pic)
                title = item.xpath('.//strong[contains(@class,"title")]')
                name = title[0].text.strip() if title and title[0].text else ""
                results.append({"vod_id": m.group(1), "vod_name": name, "vod_pic": pic})
            except:
                continue
        return results

    def homeContent(self, filter):
        html = _get(BASE + "/")
        return {"class": self.categories, "list": self._parse_list(html) if html else [], "filters": {}}

    def categoryContent(self, tid, pg, filter, extend):
        url = f"{BASE}/vod/show/id/{tid}/page/{pg}"
        html = _get(url)
        return {"page": int(pg), "pagecount": 99, "limit": 30, "count": 0, "list": self._parse_list(html) if html else []}

    def detailContent(self, ids):
        result = {"list": []}
        for vid in ids:
            try:
                html = _get(f"{BASE}/vod/play/id/{vid}/sid/1/nid/1/")
                if not html:
                    continue
                tree = etree.HTML(html)
                name = "".join(tree.xpath('//h1/text()')).strip()
                img = tree.xpath('//div[contains(@class,"video-holder")]//img[contains(@class,"data-cover")]')
                pic = ""
                if img:
                    pic = _fix(img[0].get("src", ""))
                m = re.search(r"var\s+uul\s*=\s*'([^']+)'\+'m3u8", html)
                play_url = ""
                if m:
                    play_url = "http" + m.group(1) if m.group(1).startswith("s") else m.group(1)
                sources = ["默认"]
                episodes = [f"播放${play_url}" if play_url else "加载中$"]
                result["list"].append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_play_from": "$$$".join(sources),
                    "vod_play_url": "$$$".join(episodes),
                })
            except:
                continue
        return result

    def searchContent(self, key, quick, pg="1"):
        url = f"{BASE}/vod/search.html?wd={quote(key)}&page={pg}"
        html = _get(url)
        return {"list": self._parse_list(html) if html else [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        url = id
        if not re.search(r"\.m3u8", url):
            html = _get(url)
            if html:
                m = re.search(r"var\s+uul\s*=\s*'([^']+)'\+'m3u8", html)
                if m:
                    url = "http" + m.group(1) if m.group(1).startswith("s") else m.group(1)
        return {"parse": 0, "url": _fix(url), "header": json.dumps(UA)}