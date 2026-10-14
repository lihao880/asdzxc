# coding: utf-8
# 站点: AAAA级精品
# 说明: 无广告过滤版本

import re
import json
from urllib.parse import urljoin, quote, urlparse

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://aaawave.aaaajp12.icu"
        self.path = "/aaa"
        self.site_name = "AAAA级精品"

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + self.path + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }

        self.classes = [
            {"type_id": "244", "type_name": "明星淫梦"},
            {"type_id": "269", "type_name": "糖心Vlog"},
            {"type_id": "268", "type_name": "中文调教"},
            {"type_id": "267", "type_name": "中文制服"},
            {"type_id": "266", "type_name": "中文人妻"},
            {"type_id": "265", "type_name": "中文强奸"},
            {"type_id": "264", "type_name": "中文出轨"},
            {"type_id": "263", "type_name": "中文乱伦"},
            {"type_id": "236", "type_name": "传媒视频"},
            {"type_id": "246", "type_name": "精品动漫"},
            {"type_id": "234", "type_name": "国产视频"},
            {"type_id": "238", "type_name": "性感主播"},
            {"type_id": "239", "type_name": "伦理三级"},
            {"type_id": "245", "type_name": "日韩专区"},
            {"type_id": "252", "type_name": "家庭伦伦"},
            {"type_id": "242", "type_name": "VR专区"},
            {"type_id": "241", "type_name": "无码专区"},
            {"type_id": "240", "type_name": "中文字幕"},
            {"type_id": "250", "type_name": "萝莉少女"},
            {"type_id": "249", "type_name": "网曝门事件"},
            {"type_id": "248", "type_name": "欧美专区"},
            {"type_id": "247", "type_name": "AV解说"},
            {"type_id": "259", "type_name": "女同专区"},
            {"type_id": "258", "type_name": "SM专区"},
            {"type_id": "256", "type_name": "侵犯专区"},
            {"type_id": "254", "type_name": "明星换脸"},
            {"type_id": "253", "type_name": "强奸乱伦"},
        ]

        self.filters = {}

    def getName(self):
        return self.site_name

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def destroy(self):
        pass

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return self.host + self.path + "/" + url.lstrip("/")

    def _fetch_html(self, url):
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if resp and hasattr(resp, "text"):
                return resp.text
            return None
        except Exception:
            return None

    def _parse_video_list(self, html):
        videos = []
        if not html:
            return videos

        pattern = r'<li[^>]*>.*?<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*href="([^"]+)"[^>]*title="([^"]*)"[^>]*data-original="([^"]*)"[^>]*>.*?<span[^>]*class="pic-text[^"]*"[^>]*>([^<]*)</span>'
        matches = re.findall(pattern, html, re.DOTALL)

        for href, title, pic, remark in matches:
            if not href or not title:
                continue
            vod_id = self._extract_vod_id_from_url(href)
            if not vod_id:
                continue
            videos.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": self._fix_url(pic.strip()),
                "vod_remarks": remark.strip()
            })

        return videos

    def _extract_vod_id_from_url(self, url):
        if not url:
            return ""
        m = re.search(r'/detail/id/(\d+)\.html', url)
        if m:
            return m.group(1)
        m = re.search(r'/play/id/(\d+)/', url)
        if m:
            return m.group(1)
        return ""

    def _parse_detail(self, html):
        result = {
            "vod_name": "",
            "vod_pic": "",
            "vod_content": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_play_from": "",
            "vod_play_url": ""
        }
        if not html:
            return result

        m = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>', html)
        if m:
            result["vod_name"] = m.group(1).strip()

        m = re.search(r'<img[^>]*class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]+)"', html)
        if m:
            result["vod_pic"] = self._fix_url(m.group(1).strip())

        m = re.search(r'<span[^>]*class="detail-content"[^>]*>([^<]*)</span>', html)
        if m:
            result["vod_content"] = m.group(1).strip()

        m = re.search(r'<p[^>]*class="data"[^>]*>.*?主演：([^<]*)</p>', html, re.DOTALL)
        if m:
            result["vod_actor"] = m.group(1).strip()

        m = re.search(r'<p[^>]*class="data"[^>]*>.*?导演：([^<]*)</p>', html, re.DOTALL)
        if m:
            result["vod_director"] = m.group(1).strip()

        m = re.search(r'var\s+player_aaaa\s*=\s*({[^;]+})', html)
        if m:
            try:
                data = json.loads(m.group(1))
                play_url = data.get("url", "")
                if play_url:
                    result["vod_play_from"] = "默认线路"
                    result["vod_play_url"] = "播放$" + play_url
            except:
                pass

        if not result["vod_play_url"]:
            m = re.search(r'<a[^>]*href="([^"]+)"[^>]*>立即播放</a>', html)
            if m:
                play_url = self._fix_url(m.group(1))
                result["vod_play_from"] = "默认线路"
                result["vod_play_url"] = "播放$" + play_url

        return result

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        url = self.host + self.path + "/"
        html = self._fetch_html(url)
        videos = self._parse_video_list(html) if html else []
        return {"list": videos[:20]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        page_url = f"{self.host}{self.path}/index.php/vod/type/id/{tid}/page/{pg}.html"

        html = self._fetch_html(page_url)
        if not html:
            page_url = f"{self.host}{self.path}/index.php/vod/type/id/{tid}.html"
            html = self._fetch_html(page_url)

        videos = self._parse_video_list(html) if html else []

        pagecount = 1
        if html:
            m = re.search(r'<li[^>]*class="active num"[^>]*><a[^>]*>(\d+)/(\d+)</a></li>', html)
            if m:
                pagecount = int(m.group(2)) or 1
            else:
                m = re.search(r'共(\d+)页', html)
                if m:
                    pagecount = int(m.group(1)) or 1
                else:
                    pages = re.findall(r'<a[^>]*href="[^"]*page=(\d+)"[^>]*>\s*(\d+)\s*</a>', html)
                    if pages:
                        pagecount = max([int(p) for _, p in pages if p.isdigit()]) if pages else 1

        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}

        if isinstance(ids, list) and len(ids) > 0:
            vid = str(ids[0])
        elif isinstance(ids, (str, int)):
            vid = str(ids)
        else:
            return {"list": []}

        detail_url = f"{self.host}{self.path}/index.php/vod/detail/id/{vid}.html"
        html = self._fetch_html(detail_url)

        if not html:
            return {"list": []}

        detail = self._parse_detail(html)
        detail["vod_id"] = vid

        if not detail["vod_name"]:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                title = m.group(1)
                title = re.sub(r'视频-.*$', '', title)
                detail["vod_name"] = title.strip()

        return {"list": [detail]}

    def searchContent(self, key, quick=False, pg="1"):
        if not key:
            return {"list": [], "page": 1, "pagecount": 1, "total": 0}

        pg = int(pg) if pg else 1
        encoded_key = quote(key)

        if pg == 1:
            search_url = f"{self.host}{self.path}/index.php/vod/search.html?wd={encoded_key}"
        else:
            search_url = f"{self.host}{self.path}/index.php/vod/search/page/{pg}/wd/{encoded_key}.html"

        html = self._fetch_html(search_url)
        videos = self._parse_video_list(html) if html else []

        pagecount = 1
        if html:
            m = re.search(r'<li[^>]*class="active num"[^>]*><a[^>]*>(\d+)/(\d+)</a></li>', html)
            if m:
                pagecount = int(m.group(2)) or 1

        return {"list": videos, "page": pg, "pagecount": pagecount, "total": pagecount * 20}

    def playerContent(self, flag, id, vipFlags=None):
        id = str(id) if id is not None else ""
        if not id:
            return {"parse": 1, "url": ""}

        if id.startswith("http") and ".m3u8" in id:
            return {"parse": 0, "url": id, "header": self.headers}

        if id.startswith("/"):
            id = self._fix_url(id)
            if ".m3u8" in id:
                return {"parse": 0, "url": id, "header": self.headers}

        if id.startswith("http") and "/play/" in id:
            html = self._fetch_html(id)
            if html:
                m = re.search(r'var\s+player_aaaa\s*=\s*({[^;]+})', html)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        play_url = data.get("url", "")
                        if play_url and ".m3u8" in play_url:
                            if play_url.startswith("http"):
                                return {"parse": 0, "url": play_url, "header": self.headers}
                            if play_url.startswith("/"):
                                play_url = self._fix_url(play_url)
                                return {"parse": 0, "url": play_url, "header": self.headers}
                    except:
                        pass

        if id.isdigit():
            play_url = f"{self.host}{self.path}/index.php/vod/play/id/{id}/sid/1/nid/1.html"
            html = self._fetch_html(play_url)
            if html:
                m = re.search(r'var\s+player_aaaa\s*=\s*({[^;]+})', html)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        video_url = data.get("url", "")
                        if video_url and ".m3u8" in video_url:
                            if video_url.startswith("http"):
                                return {"parse": 0, "url": video_url, "header": self.headers}
                            if video_url.startswith("/"):
                                video_url = self._fix_url(video_url)
                                return {"parse": 0, "url": video_url, "header": self.headers}
                    except:
                        pass

        return {"parse": 1, "url": id, "header": self.headers}

    def recommendContent(self, ids, pg):
        try:
            if not ids:
                return {"list": []}
            vid = str(ids[0]) if isinstance(ids, list) else str(ids)
            detail_url = f"{self.host}{self.path}/index.php/vod/detail/id/{vid}.html"
            html = self._fetch_html(detail_url)
            if not html:
                return {"list": []}
            tid = None
            m = re.search(r'/vod/type/id/(\d+)\.html', html)
            if m:
                tid = m.group(1)
            if not tid:
                title_match = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>', html)
                if title_match:
                    title = title_match.group(1).strip()
                    keywords = re.sub(r'[^\w\u4e00-\u9fff]', ' ', title)
                    keywords = ' '.join(keywords.split()[:3])
                    if keywords:
                        search_result = self.searchContent(keywords, quick=True, pg="1")
                        result_list = search_result.get("list", [])
                        filtered = [item for item in result_list if str(item.get("vod_id", "")) != vid]
                        return {"list": filtered[:15]}
            if tid:
                category_result = self.categoryContent(tid, 1, False, None)
                result_list = category_result.get("list", [])
                filtered = [item for item in result_list if str(item.get("vod_id", "")) != vid]
                if len(filtered) < 15:
                    page2 = self.categoryContent(tid, 2, False, None)
                    for item in page2.get("list", []):
                        if str(item.get("vod_id", "")) != vid and item not in filtered:
                            filtered.append(item)
                return {"list": filtered[:15]}
            home_result = self.homeVideoContent()
            result_list = home_result.get("list", [])
            filtered = [item for item in result_list if str(item.get("vod_id", "")) != vid]
            return {"list": filtered[:15]}
        except Exception:
            return {"list": []}