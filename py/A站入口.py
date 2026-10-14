#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, json, urllib.request, urllib.parse, ssl
from base.spider import Spider

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

class Spider(Spider):
    def getName(self): return "A站入口"
    def init(self, extend=""):
        self.host = "https://wocenjwi.cyou"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": self.host + "/"}
        self.categories = [{"type_id": "1", "type_name": "中文字幕"}, {"type_id": "2", "type_name": "成人动漫"}, {"type_id": "7", "type_name": "欧美专区"}, {"type_id": "6", "type_name": "国产情色"}, {"type_id": "3", "type_name": "人妻熟女"}, {"type_id": "8", "type_name": "日本无码"}, {"type_id": "4", "type_name": "网红主播"}, {"type_id": "5", "type_name": "香港三级"}]

    def _get(self, url):
        try:
            req = urllib.request.Request(url, headers=self.headers)
            resp = urllib.request.urlopen(req, timeout=15, context=ctx)
            return resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="ignore")
        except: return None

    def _fix(self, u):
        if not u: return ""
        if u.startswith("//"): return "https:" + u
        if u.startswith("/"): return self.host + u
        return u

    def _parse_list(self, html):
        if not html: return []
        results, seen = [], set()
        blocks = re.findall(r'<li[^>]*class="[^"]*content-item[^"]*"[^>]*>(.*?)</li>', html, re.DOTALL)
        if not blocks:
            tpl = re.search(r'id="tpl-img-content"[^>]*>(.*?)</div>', html, re.DOTALL)
            if tpl: blocks = re.findall(r'<li[^>]*>(.*?)</li>', tpl.group(1), re.DOTALL)
        if not blocks:
            tpl2 = re.search(r'class="[^"]*img-list-data[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            if tpl2: blocks = re.findall(r'<li[^>]*>(.*?)</li>', tpl2.group(1), re.DOTALL)
        for b in blocks:
            try:
                href_m = re.search(r'href="(/index\.php/vod/detail/id/(\d+)\.html)"', b)
                if not href_m: continue
                vid = href_m.group(2)
                if vid in seen: continue
                seen.add(vid)
                title_m = re.search(r'title="([^"]+)"', b)
                title = title_m.group(1) if title_m else ""
                if not title:
                    t2 = re.search(r'<a[^>]*>([^<]+)</a>', b)
                    title = t2.group(1).strip() if t2 else ""
                img_m = re.search(r'data-original="([^"]+)"', b)
                if not img_m: img_m = re.search(r'<img[^>]+src="([^"]+)"', b)
                pic = self._fix(img_m.group(1)) if img_m else ""
                date_m = re.search(r'<p[^>]*class="[^"]*date-text-bg[^"]*"[^>]*>([^<]+)</p>', b)
                if not date_m: date_m = re.search(r'<span[^>]*class="[^"]*note[^"]*text-bg-r[^"]*"[^>]*>([^<]+)</span>', b)
                remarks = date_m.group(1).strip() if date_m else ""
                results.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": remarks})
            except: continue
        return results

    def _parse_player_json(self, html):
        if not html: return {}
        idx = html.find("player_aaaa")
        if idx < 0: return {}
        snippet = html[idx:idx+1500]
        m = re.search(r'player_aaaa\s*=\s*(\{.*)', snippet)
        if not m: return {}
        raw = m.group(1).replace("\\/", "/")
        depth, end = 0, 0
        for i, ch in enumerate(raw):
            if ch == '{': depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end > 0:
            try: return json.loads(raw[:end])
            except: pass
        return {}

    def homeContent(self, filter):
        html = self._get(self.host + "/")
        return {"class": self.categories, "list": self._parse_list(html) if html else [], "filters": {}}

    def categoryContent(self, tid, pg, filter, extend):
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"
        html = self._get(url)
        if not html: return {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}
        total_m = re.search(r'共\s*(\d+)\s*页', html)
        pagecount = int(total_m.group(1)) if total_m else 99
        lst = self._parse_list(html)
        return {"list": lst, "page": int(pg), "pagecount": pagecount, "limit": 20, "total": len(lst) * pagecount}

    def detailContent(self, ids):
        result = {"list": []}
        for vid in ids:
            try:
                html = self._get(f"{self.host}/index.php/vod/detail/id/{vid}.html")
                if not html: continue
                name_m = re.search(r'<h2[^>]*class="[^"]*text-ellipsis[^"]*"[^>]*>([^<]+)', html)
                name = name_m.group(1).strip() if name_m else ""
                if not name:
                    ttl_m = re.search(r'<title>([^<]+)', html)
                    name = ttl_m.group(1).replace("详情介绍","").replace("在线观看","").replace("迅雷下载","").replace(" - A站入口","").strip() if ttl_m else ""
                bg_m = re.search(r'background-image:\s*url\(([^)]+)\)', html)
                pic = self._fix(bg_m.group(1)) if bg_m else ""
                if not pic:
                    img_m = re.search(r'<img[^>]+src="([^"]+)"[^>]*alt=', html)
                    pic = self._fix(img_m.group(1)) if img_m else ""
                lines = re.findall(r'<a[^>]*href="(/index\.php/vod/play/[^"]+)"[^>]*>([^<]+)</a>', html)
                if not lines:
                    raw = re.findall(r'<div[^>]*class="[^"]*item line[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', html, re.DOTALL)
                    lines = raw
                src_map = {}
                for href, text in lines:
                    src_name = text.strip() or f"线路{len(src_map)+1}"
                    if src_name in src_map: src_name = f"{src_name}{len(src_map)}"
                    src_map[src_name] = self._fix(href)
                if not src_map:
                    pjs = self._parse_player_json(html)
                    if pjs.get("url"): src_map["默认"] = self._fix(pjs["url"])
                sources = list(src_map.keys())
                episodes = ["1$" + src_map[k] for k in sources]
                result["list"].append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_play_from": "$$$".join(sources), "vod_play_url": "$$$".join(episodes)})
            except: continue
        return result

    def searchContent(self, key, quick, pg="1"):
        return {"list": [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        url = self._fix(id)
        if ".m3u8" in url or ".mp4" in url:
            return {"parse": 0, "url": url, "header": json.dumps(self.headers)}
        html = self._get(url)
        if not html: return {"parse": 1, "playUrl": "", "url": ""}
        cfg = self._parse_player_json(html)
        pu = cfg.get("url", "")
        if pu:
            if ".m3u8" in pu or ".mp4" in pu:
                return {"parse": 0, "url": pu, "header": json.dumps(self.headers)}
            return {"parse": 1, "playUrl": "", "url": pu}
        ifm = re.search(r'<iframe[^>]+src="([^"]+)"', html)
        if ifm:
            isrc = self._fix(ifm.group(1))
            if ".m3u8" in isrc or ".mp4" in isrc:
                return {"parse": 0, "url": isrc, "header": json.dumps(self.headers)}
        dm = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
        if dm: return {"parse": 0, "url": dm.group(1), "header": json.dumps(self.headers)}
        mp4 = re.search(r'(https?://[^\s"\']+\.mp4[^\s"\']*)', html)
        if mp4: return {"parse": 0, "url": mp4.group(1), "header": json.dumps(self.headers)}
        return {"parse": 1, "playUrl": "", "url": ""}