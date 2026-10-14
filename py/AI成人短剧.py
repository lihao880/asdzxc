# coding: utf-8
# 站点: AI成人短剧
# 域名: https://xn--7nrw08b95r.aicrss4.sbs/
# 说明: 无广告过滤版本

import re
import json
import urllib.parse
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xn--7nrw08b95r.aicrss4.sbs"
        self.site_name = "AI成人短剧"
        self.classes = [
            {"type_id": "20", "type_name": "视频资源"},
            {"type_id": "82", "type_name": "AI视频"},
            {"type_id": "23", "type_name": "精品推荐"},
            {"type_id": "24", "type_name": "国产色情"},
            {"type_id": "25", "type_name": "主播直播"},
            {"type_id": "26", "type_name": "亚洲无码"},
            {"type_id": "27", "type_name": "亚洲有码"},
            {"type_id": "28", "type_name": "中文字幕"},
            {"type_id": "29", "type_name": "巨乳美乳"},
            {"type_id": "30", "type_name": "人妻熟女"},
            {"type_id": "31", "type_name": "强奸乱伦"},
            {"type_id": "32", "type_name": "欧美精品"},
            {"type_id": "33", "type_name": "萝莉少女"},
            {"type_id": "34", "type_name": "伦理三级"},
            {"type_id": "35", "type_name": "成人动漫"},
            {"type_id": "36", "type_name": "自拍偷拍"},
            {"type_id": "37", "type_name": "制服丝袜"},
            {"type_id": "38", "type_name": "口交颜射"},
            {"type_id": "39", "type_name": "日本精品"},
            {"type_id": "40", "type_name": "Cosplay"},
            {"type_id": "41", "type_name": "素人自拍"},
            {"type_id": "42", "type_name": "台湾辣妹"},
            {"type_id": "43", "type_name": "韩国御姐"},
            {"type_id": "44", "type_name": "唯美港姐"},
            {"type_id": "45", "type_name": "东南亚AV"},
            {"type_id": "46", "type_name": "欺辱凌辱"},
            {"type_id": "47", "type_name": "剧情介绍"},
            {"type_id": "48", "type_name": "多人多P"},
            {"type_id": "49", "type_name": "91探花"},
            {"type_id": "50", "type_name": "网红流出"},
            {"type_id": "51", "type_name": "野外露出"},
            {"type_id": "52", "type_name": "古装扮演"},
            {"type_id": "53", "type_name": "女优系列"},
            {"type_id": "54", "type_name": "可爱学生"},
            {"type_id": "55", "type_name": "风情旗袍"},
            {"type_id": "56", "type_name": "兽耳系列"},
            {"type_id": "57", "type_name": "瑜伽裤"},
            {"type_id": "58", "type_name": "闷骚护士"},
            {"type_id": "59", "type_name": "网曝门"},
            {"type_id": "60", "type_name": "传媒出品"},
            {"type_id": "61", "type_name": "女同性恋"},
            {"type_id": "62", "type_name": "恋腿狂魔"},
            {"type_id": "77", "type_name": "过膝袜"},
            {"type_id": "78", "type_name": "国产乱伦"},
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
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
        try:
            resp = self.fetch(self.host, headers=self.headers, timeout=10)
            if not resp:
                return {"list": []}
            html = resp.text if hasattr(resp, "text") else ""
            items = self._parse_vod_list(html, self.host)
            return {"list": items[:20] if items else []}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if page == 1:
            url = f"{self.host}/index.php/vod/type/id/{tid}.html"
        else:
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
            html = resp.text if hasattr(resp, "text") else ""
            items = self._parse_vod_list(html, self.host)
            pagecount = self._parse_pagecount(html) or 50
            return {
                "list": items,
                "page": page,
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception:
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid:
            return {"list": []}
        url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp:
                return {"list": []}
            html = resp.text if hasattr(resp, "text") else ""
            vod = self._parse_detail(html, vid)
            return {"list": [vod] if vod else []}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        if not key or not key.strip():
            return {"list": [], "page": 1}
        page = int(pg) if pg else 1
        try:
            data = {"wd": key.strip()}
            url = f"{self.host}/index.php/vod/search.html"
            resp = self.post(url, data=data, headers=self.headers, timeout=10)
            if not resp:
                return {"list": [], "page": page}
            html = resp.text if hasattr(resp, "text") else ""
            items = self._parse_vod_list(html, self.host)
            pagecount = self._parse_pagecount(html) or 5
            return {
                "list": items,
                "page": page,
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception:
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        play_url = str(id).strip()
        if not play_url.startswith("http"):
            parts = play_url.split("|")
            if len(parts) >= 3:
                vid, sid, nid = parts[0], parts[1], parts[2]
                play_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html"
            else:
                play_url = f"{self.host}/index.php/vod/play/id/{play_url}/sid/1/nid/1.html"
        try:
            resp = self.fetch(play_url, headers=self.headers, timeout=10)
            if not resp:
                return {"parse": 1, "url": play_url, "header": self.headers}
            html = resp.text if hasattr(resp, "text") else ""
            m3u8_url = self._extract_m3u8_from_playpage(html)
            if m3u8_url and m3u8_url.startswith("http"):
                return {
                    "parse": 0,
                    "url": m3u8_url,
                    "header": {"User-Agent": self.headers["User-Agent"]}
                }
            return {"parse": 1, "url": play_url, "header": self.headers}
        except Exception:
            return {"parse": 1, "url": play_url, "header": self.headers}

    def recommendContent(self, ids, pg="1"):
        return {"list": []}

    def destroy(self):
        pass

    def _parse_vod_list(self, html, base_url):
        items = []
        pattern = r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*href="([^"]+)"[^>]*title="([^"]*)"[^>]*(?:data-original|src)="([^"]*)"'
        matches = re.findall(pattern, html, re.DOTALL)
        for href, title, pic in matches:
            if not title or not href:
                continue
            vid = self._extract_vid_from_url(href)
            if not vid:
                continue
            remark = ""
            href_pos = html.find(href)
            if href_pos >= 0:
                segment = html[href_pos:href_pos + 800]
                pic_text_match = re.search(r'<span[^>]*class="[^"]*pic-text[^"]*"[^>]*>(.*?)</span>', segment, re.DOTALL)
                if pic_text_match:
                    remark = re.sub(r'<[^>]+>', '', pic_text_match.group(1)).strip()[:30]
            items.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": self._fix_url(pic, base_url),
                "vod_remarks": remark or ""
            })
        seen = set()
        unique = []
        for item in items:
            if item["vod_id"] not in seen:
                seen.add(item["vod_id"])
                unique.append(item)
        return unique[:50]

    def _parse_detail(self, html, vid):
        vod = {
            "vod_id": vid,
            "vod_name": "",
            "vod_pic": "",
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "",
            "vod_play_url": ""
        }
        title_match = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>', html)
        if title_match:
            vod["vod_name"] = title_match.group(1).strip()
        if not vod["vod_name"]:
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                vod["vod_name"] = title_match.group(1).replace("--AI成人短剧", "").strip()
        pic_match = re.search(r'<img[^>]*class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]+)"', html)
        if pic_match:
            vod["vod_pic"] = self._fix_url(pic_match.group(1), self.host)
        content_match = re.search(r'<span[^>]*class="[^"]*detail-content[^"]*"[^>]*>([^<]*)</span>', html)
        if content_match:
            vod["vod_content"] = content_match.group(1).strip()
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
                item_pattern = r'<li[^>]*><a[^>]*href="([^"]+)"[^>]*>([^<]+)</a></li>'
                items = re.findall(item_pattern, playlist_html)
                if items:
                    eps = []
                    for ep_href, ep_name in items:
                        sid_nid = self._extract_sid_nid(ep_href)
                        if sid_nid:
                            eps.append(f"{ep_name.strip()}${vid}|{sid_nid}")
                        else:
                            m2 = re.search(r'/id/(\d+)/', ep_href)
                            if m2:
                                eps.append(f"{ep_name.strip()}${m2.group(1)}|1|1")
                    if eps:
                        play_from_list.append(tab_name.strip())
                        play_url_list.append("#".join(eps))
        if not play_url_list:
            play_btn_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>立即播放</a>', html)
            if play_btn_match:
                btn_href = play_btn_match.group(1)
                sid_nid = self._extract_sid_nid(btn_href)
                if sid_nid:
                    play_from_list.append("播放")
                    play_url_list.append(f"正片${vid}|{sid_nid}")
        vod["vod_play_from"] = "$$$".join(play_from_list)
        vod["vod_play_url"] = "$$$".join(play_url_list)
        return vod

    def _extract_m3u8_from_playpage(self, html):
        match = re.search(r'var\s+player_aaaa\s*=\s*({[^}]+})', html)
        if match:
            try:
                data = json.loads(match.group(1))
                return data.get("url", "")
            except:
                pass
        match = re.search(r'url\s*["\']\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', html)
        if match:
            return match.group(1)
        return ""

    def _extract_vid_from_url(self, url):
        match = re.search(r'/id/(\d+)\.html', url)
        if match:
            return match.group(1)
        match = re.search(r'/id/(\d+)/', url)
        if match:
            return match.group(1)
        return ""

    def _extract_sid_nid(self, url):
        match = re.search(r'/sid/(\d+)/nid/(\d+)\.html', url)
        if match:
            return f"{match.group(1)}|{match.group(2)}"
        return ""

    def _parse_pagecount(self, html):
        match = re.search(r'共(\d+)页', html)
        if match:
            return int(match.group(1))
        page_numbers = re.findall(r'<a[^>]*href="[^"]*page/(\d+)\.html[^"]*"[^>]*>(\d+)</a>', html)
        if page_numbers:
            max_page = max(int(p) for _, p in page_numbers if p.isdigit())
            return max_page
        return 1

    def _fix_url(self, url, base_url):
        if not url:
            return ""
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("//"):
            return "https:" + url
        return urllib.parse.urljoin(base_url, url)