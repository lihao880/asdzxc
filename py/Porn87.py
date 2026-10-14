#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, json, requests
from urllib.parse import quote

BASE = "https://porn87.com"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": BASE + "/",
}

def _get(url):
    try:
        r = requests.get(url, headers=UA, timeout=10)
        r.encoding = "utf-8"
        return r.text
    except:
        return ""

def _fix(u):
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return BASE + u
    return u

def _parse_list(html):
    results, seen = [], set()
    if not html:
        return results
    for m in re.finditer(r'<a\s[^>]*href="(/main/html\?id=(\d+))"[^>]*>', html):
        vid = m.group(2)
        if vid in seen:
            continue
        seen.add(vid)
        tag_start = m.start()
        tag_end = html.find('/a>', tag_start)
        if tag_end < 0:
            tag_end = tag_start + 500
        chunk = html[tag_start:tag_end]
        pic = ""
        pm = re.search(r'(?:data-original|data-src|src)="([^"]+)"', chunk)
        if pm:
            pic = _fix(pm.group(1))
        title = ""
        tm = re.search(r'alt="([^"]*)"', chunk)
        if tm:
            title = tm.group(1).strip()
        if not title:
            tm = re.search(r'<span[^>]*>([^<]+)</span>', chunk)
            if tm:
                title = tm.group(1).strip()
        if not title:
            title = re.sub(r'<[^>]+>', '', chunk).strip()
        if vid and title:
            results.append({"vod_id": vid, "vod_name": title, "vod_pic": pic})
    return results

def _fetch_tags():
    html = _get(BASE + "/main/all_tags")
    if not html:
        return []
    tags = []
    for m in re.finditer(r'<a[^>]*href="/main/tag\?name=([^"]+)"[^>]*>', html):
        name = m.group(1)
        nm = re.search(r'alt="([^"]*)"', m.group(0))
        display = nm.group(1).strip() if nm else name
        if name and display and name not in [t["type_id"] for t in tags]:
            tags.append({"type_id": name, "type_name": display})
    return tags

class Spider:
    def getDependence(self):
        return []

    def homeVideoContent(self):
        return self.homeContent(False)

    def init(self, extend=""):
        self.site_url = BASE
        self.headers = UA

    def homeContent(self, filter):
        html = _get(BASE + "/main/tag?lineup=create_time")
        cats = _fetch_tags()
        if not cats:
            cats = [
                {"type_id": "create_time", "type_name": "最新影片"},
                {"type_id": "recent_views", "type_name": "最热门"},
            ]
        video_list = _parse_list(html)[:24] if html else []
        return {"class": cats, "list": video_list, "filters": {}}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if page <= 1:
            url = BASE + "/main/tag?name=" + quote(tid)
        else:
            url = BASE + "/main/tag?name=" + quote(tid) + "&page=" + str(page - 1)
        video_list = _parse_list(_get(url))
        return {"page": page, "pagecount": 99, "limit": 12, "total": 9999, "list": video_list}

    def detailContent(self, ids):
        result = {"list": []}
        for vid in ids:
            vid = str(vid)
            embed_html = _get(BASE + "/main/embed?id=" + vid)
            name, pic, m3u8 = "", "", ""
            if embed_html:
                m = re.search(r'<title>([^<]+)', embed_html)
                if m:
                    name = m.group(1).replace(" Porn87 Player", "").strip()
                m = re.search(r'media-poster-image[^>]+src="([^"]+)"', embed_html)
                if m:
                    pic = _fix(m.group(1))
                m = re.search(r'videoSrc\s*=\s*"([^"]+)"', embed_html)
                if m:
                    m3u8 = _fix(m.group(1))
                if not m3u8:
                    m = re.search(r'<video[^>]+src="([^"]+)"', embed_html)
                    if m:
                        m3u8 = _fix(m.group(1))
            if not embed_html:
                html = _get(BASE + "/main/html?id=" + vid)
                if html:
                    m = re.search(r"<title>([^<]+)", html)
                    if m:
                        name = m.group(1).split(" - ")[0].strip()
                    m = re.search(r'og:image[^>]+content="([^"]+)', html)
                    if m:
                        pic = _fix(m.group(1))
            if m3u8:
                play_url = "播放$" + m3u8
            else:
                play_url = "播放$" + BASE + "/main/embed?id=" + vid
            result["list"].append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_play_from": "默认线路",
                "vod_play_url": play_url,
            })
        return result

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = BASE + "/main/search?name=" + quote(key)
        video_list = _parse_list(_get(url))
        return {"list": video_list, "page": page}

    def playerContent(self, flag, id, vipFlags):
        if ".m3u8" in id:
            return {"parse": 0, "url": id, "header": json.dumps(self.headers)}
        if ".mp4" in id:
            return {"parse": 0, "url": id, "header": json.dumps(self.headers)}
        return {"parse": 1, "url": id, "header": json.dumps(self.headers)}