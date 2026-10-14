# coding: utf-8
import re
import time
from urllib.parse import urljoin, quote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.xasiat.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.classes = [
            {"type_id": "gravure-idols", "type_name": "Gravure Idols"},
            {"type_id": "amateur3", "type_name": "Amateur"},
            {"type_id": "southeast-asia", "type_name": "Southeast Asia"},
            {"type_id": "western-girls", "type_name": "Western Girls"},
            {"type_id": "china-taiwan", "type_name": "China & Taiwan"},
            {"type_id": "korea", "type_name": "South Korea"},
            {"type_id": "jav-uncensored", "type_name": "JAV Uncensored"},
            {"type_id": "jav-amateur", "type_name": "JAV Amateur"},
            {"type_id": "jav", "type_name": "JAV & AV Models"},
            {"type_id": "cosplay", "type_name": "Cosplay"},
        ]
        self.filters = {}
        self._cookies = {}

    def getName(self):
        return "xasiat"

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            html = self._fetch_html(self.host + "/")
            videos = self._parse_video_list(html)
            return {"list": videos[:20]}
        except Exception as e:
            self.log({"action": "home_fail", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        if pg is None or pg == "":
            pg = 1
        pg = int(pg)
        if pg == 1:
            url = f"{self.host}/categories/{tid}/"
        else:
            url = f"{self.host}/categories/{tid}/{pg}/"
        try:
            html = self._fetch_html(url)
            videos = self._parse_video_list(html)
            return {"list": videos, "total": len(videos), "page": pg, "pagecount": 99, "limit": 20}
        except Exception as e:
            self.log({"action": "category_fail", "url": url, "error": str(e)})
            return {"list": [], "total": 0, "page": pg, "pagecount": 99, "limit": 20}

    def _fetch_html(self, url, retry=2):
        for attempt in range(retry + 1):
            try:
                resp = self.fetch(url, headers=self.headers)
                if resp is None:
                    continue
                if hasattr(resp, 'cookies') and resp.cookies:
                    self._cookies = resp.cookies
                if hasattr(resp, 'text'):
                    return resp.text
                if hasattr(resp, 'content'):
                    try:
                        return resp.content.decode('utf-8')
                    except:
                        return str(resp.content)
                return str(resp)
            except Exception as e:
                if attempt < retry:
                    time.sleep(1)
                    continue
                raise
        return ""

    def _parse_video_list(self, html):
        videos = []
        if not html:
            return videos
        
        pattern = r'href\s*=\s*["\']?(https?://[^"\']*?/videos/(\d+)/[^>"\s]+/)["\']?'
        links = re.findall(pattern, html, re.IGNORECASE)
        
        if not links:
            pattern2 = r'href\s*=\s*["\']?(/videos/(\d+)/[^>"\s]+/)["\']?'
            links = re.findall(pattern2, html, re.IGNORECASE)
        
        seen = set()
        for match in links:
            if len(match) == 2:
                href, vid = match
            else:
                continue
            if vid in seen:
                continue
            seen.add(vid)
            if not vid:
                continue
            
            vid_pattern = f'href="[^"]*?/videos/{vid}/'
            vid_pos = re.search(vid_pattern, html, re.IGNORECASE)
            if not vid_pos:
                continue
            start_pos = vid_pos.start()
            chunk = html[start_pos:start_pos + 1500]
            
            title_match = re.search(r'<strong\s+class="title">(.*?)</strong>', chunk, re.DOTALL)
            if not title_match:
                continue
            title = title_match.group(1).strip()
            title = re.sub(r'&nbsp;', ' ', title)
            if not title:
                continue
            
            pic = ""
            pic_match = re.search(r'data-original="([^"]+)"', chunk)
            if not pic_match:
                pic_match = re.search(r'data-src="([^"]+)"', chunk)
            if not pic_match:
                pic_match = re.search(r'src="([^"]+)"', chunk)
            if pic_match:
                pic = pic_match.group(1)
            if pic and ('data:image' in pic or 'base64' in pic or 'gif' in pic):
                pic = ""
            if pic and not pic.startswith("http"):
                pic = urljoin(self.host, pic)
            
            if href.startswith("/"):
                full_url = urljoin(self.host, href)
            else:
                full_url = href
            
            videos.append({
                "vod_id": full_url,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_url": full_url
            })
        
        return videos

    def detailContent(self, ids):
        if not ids or not ids[0]:
            return {"list": []}
        url = str(ids[0]).strip()
        if not url.startswith("http"):
            url = urljoin(self.host, url)
        try:
            html = self._fetch_html(url)
            return self._parse_detail(html, url)
        except Exception as e:
            self.log({"action": "detail_fail", "url": url, "error": str(e)})
            return {"list": []}

    def _parse_detail(self, html, url):
        vid_match = re.search(r'/videos/(\d+)/', url)
        vid = vid_match.group(1) if vid_match else ""
        
        vod = {
            "vod_id": vid,
            "vod_name": "",
            "vod_pic": "",
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "",
            "vod_play_url": ""
        }
        
        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        if title_match:
            vod["vod_name"] = title_match.group(1).strip()
        
        pic_match = re.search(r'"thumbnailUrl"\s*:\s*"([^"]+)"', html)
        if pic_match:
            vod["vod_pic"] = pic_match.group(1)
        if not vod["vod_pic"]:
            pic_match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            if pic_match:
                vod["vod_pic"] = pic_match.group(1)
        
        play_url = None
        v_match = re.search(r'video_url:\s*[\'"]([^\'"]+)[\'"]', html)
        if v_match:
            play_url = v_match.group(1)
        if not play_url:
            alt_match = re.search(r'video_alt_url:\s*[\'"]([^\'"]+)[\'"]', html)
            if alt_match:
                play_url = alt_match.group(1)
        if not play_url:
            content_match = re.search(r'"contentUrl"\s*:\s*"([^"]+)"', html)
            if content_match:
                play_url = content_match.group(1)
        if not play_url:
            mp4_match = re.search(r'(https?://[^"\']+\.(?:mp4|m3u8)[^"\']*)', html)
            if mp4_match:
                play_url = mp4_match.group(1)
        
        if play_url:
            play_url = play_url.rstrip('/')
            vod["vod_play_url"] = f"播放${play_url}"
            vod["vod_play_from"] = "直链"
        else:
            vod["vod_play_url"] = f"播放$"
            vod["vod_play_from"] = ""
        
        desc_match = re.search(r'<meta name="description" content="([^"]+)"', html)
        if desc_match:
            vod["vod_content"] = desc_match.group(1)
        
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        if not key or not key.strip():
            return {"list": [], "page": 1}
        keyword = key.strip()
        search_url = f"{self.host}/search/?q={quote(keyword)}"
        try:
            html = self._fetch_html(search_url)
            videos = self._parse_video_list(html)
            return {"list": videos, "page": int(pg or 1)}
        except Exception as e:
            self.log({"action": "search_fail", "key": keyword, "error": str(e)})
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        if id:
            headers = self.headers.copy()
            if self._cookies:
                cookie_str = "; ".join([f"{k}={v}" for k, v in self._cookies.items()])
                headers["Cookie"] = cookie_str
            if id.startswith("http://") or id.startswith("https://"):
                return {"parse": 0, "url": id, "header": headers}
            if id.startswith("/"):
                id = urljoin(self.host, id)
            else:
                id = self.host + "/" + id
            return {"parse": 0, "url": id, "header": headers}
        return {"parse": 1, "url": "", "header": self.headers}

    def localProxy(self, param):
        return [200, "application/octet-stream", "", {"Cache-Control": "no-store"}]

    def isVideoFormat(self, url):
        return url and url.endswith((".mp4", ".m3u8", ".mkv", ".avi", ".ts"))