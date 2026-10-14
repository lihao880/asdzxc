# coding: utf-8
import re
import json
from bs4 import BeautifulSoup
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://bad.news"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Cookie": "agree=true"
        }
        # 排序分類（首頁的4種排序方式）
        self.classes = [
            {"type_id": "hot", "type_name": "按熱度"},
            {"type_id": "new", "type_name": "按時間"},
            {"type_id": "score", "type_name": "按得分"},
            {"type_id": "better", "type_name": "精選"}
        ]
        self.filters = {}

    def getName(self):
        return "Bad.News"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return {"list": []}

    def _fetch_html(self, url):
        resp = self.fetch(url, headers=self.headers)
        if not resp:
            return ""
        if hasattr(resp, 'text'):
            return resp.text
        if hasattr(resp, 'content'):
            return resp.content.decode('utf-8', errors='ignore')
        return str(resp)

    def _get_title_and_link(self, card):
        h3 = card.select_one("h3")
        if not h3:
            return "Watch video", ""
        
        for a in h3.select("a"):
            href = a.get("href")
            if href and ("/t/" in href):
                link = href
                if not link.startswith("http"):
                    link = self.host + link
                title = a.get_text(strip=True)
                if title:
                    return title, link
        
        full_text = h3.get_text(strip=True)
        if full_text:
            return full_text, ""
        
        return "Watch video", ""

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = pg or 1
        
        if tid == "hot":
            url = f"{self.host}/sort-hot/page-{page}"
        elif tid == "new":
            url = f"{self.host}/sort-new/page-{page}"
        elif tid == "score":
            url = f"{self.host}/sort-score/page-{page}"
        elif tid == "better":
            url = f"{self.host}/sort-better/page-{page}"
        else:
            url = f"{self.host}/page-{page}"
        
        try:
            html = self._fetch_html(url)
            if not html:
                return {"list": [], "page": page, "pagecount": 1}
            
            soup = BeautifulSoup(html, "html.parser")
            items = []
            
            cards = soup.select(".twi.hasMedia.link")
            for card in cards:
                try:
                    title, link = self._get_title_and_link(card)
                    if not link:
                        continue
                    
                    video = card.select_one("video.my-videos")
                    if video:
                        video_url = video.get("data-source") or video.get("src") or ""
                        poster = video.get("poster") or video.get("data-poster") or ""
                    else:
                        continue
                    
                    if title and video_url:
                        items.append({
                            "vod_id": link,
                            "vod_name": title,
                            "vod_pic": poster,
                            "vod_remarks": ""
                        })
                except:
                    continue
            
            pagecount = 1
            pagination = soup.select(".pagination ul li a")
            for a in pagination:
                text = a.get_text(strip=True)
                if text.isdigit() and int(text) > pagecount:
                    pagecount = int(text)
            
            return {"list": items, "page": page, "pagecount": pagecount}
            
        except Exception as e:
            return {"list": [], "page": page, "pagecount": 1}

    def getCategoryContent(self, tid, pg, filter=False, extend=None):
        return self.categoryContent(tid, pg, filter, extend)

    def getCategory(self, tid, pg, filter=False, extend=None):
        return self.categoryContent(tid, pg, filter, extend)

    def getCategoryList(self, tid, pg, filter=False, extend=None):
        return self.categoryContent(tid, pg, filter, extend)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        
        vid = ids[0] if isinstance(ids, list) else ids
        if vid.startswith("http"):
            url = vid
        else:
            url = self.host + vid
        
        try:
            html = self._fetch_html(url)
            if not html:
                return {"list": []}
            
            if "请确认您的年龄18+" in html or "agree-over18" in html:
                old_headers = self.headers.copy()
                self.headers["Cookie"] = "agree=true"
                html = self._fetch_html(url)
                self.headers = old_headers
                if not html:
                    return {"list": []}
            
            soup = BeautifulSoup(html, "html.parser")
            video = soup.select_one("video.my-videos")
            if not video:
                return {"list": []}
            
            video_url = video.get("data-source") or video.get("src") or ""
            poster = video.get("poster") or video.get("data-poster") or ""
            
            title = "未知标题"
            h3 = soup.select_one("h3")
            if h3:
                a_tag = h3.select_one("a")
                if a_tag:
                    title = a_tag.get_text(strip=True)
                if not title or title == "未知标题":
                    title = h3.get_text(strip=True)
                    for tag in h3.select("a, h4, .label, .info2, .time"):
                        if tag:
                            title = title.replace(tag.get_text(strip=True), "").strip()
            
            if not title or title == "未知标题":
                meta_title = soup.select_one("meta[property='og:title']")
                if meta_title:
                    title = meta_title.get("content", "")
            
            user_elem = soup.select_one(".info2 .time")
            username = user_elem.get_text(strip=True) if user_elem else ""
            
            time_elem = soup.select_one(".intotime label")
            pub_time = time_elem.get_text(strip=True) if time_elem else ""
            
            desc_elem = soup.select_one(".md p")
            desc = desc_elem.get_text(strip=True) if desc_elem else ""
            
            vod = {
                "vod_id": url,
                "vod_name": title or "未知标题",
                "vod_pic": poster,
                "vod_actor": username,
                "vod_remarks": pub_time,
                "vod_content": desc,
                "vod_play_from": "直链",
                "vod_play_url": f"播放${video_url}" if video_url else ""
            }
            
            return {"list": [vod]}
            
        except Exception as e:
            return {"list": []}

    def searchContent(self, key, quick=False, pg=1):
        if not key:
            return {"list": []}
        
        url = f"{self.host}/search/q-{key}/type-porn"
        if pg > 1:
            url = f"{self.host}/search/q-{key}/type-porn/page-{pg}"
        
        try:
            html = self._fetch_html(url)
            if not html:
                return {"list": []}
            
            soup = BeautifulSoup(html, "html.parser")
            items = []
            
            cards = soup.select(".twi.hasMedia.link")
            for card in cards:
                try:
                    title, link = self._get_title_and_link(card)
                    if not link:
                        continue
                    
                    video = card.select_one("video.my-videos")
                    if video:
                        video_url = video.get("data-source") or video.get("src") or ""
                        poster = video.get("poster") or video.get("data-poster") or ""
                    else:
                        continue
                    
                    if title and video_url:
                        items.append({
                            "vod_id": link,
                            "vod_name": title,
                            "vod_pic": poster,
                            "vod_remarks": ""
                        })
                except:
                    continue
            
            return {"list": items}
            
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        if id and id.startswith("http"):
            return {"parse": 0, "url": id}
        return {"parse": 1, "url": id}

    def localProxy(self, param):
        return [200, "application/octet-stream", "", {}]