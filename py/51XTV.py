# coding: utf-8
import json
import re
from urllib.parse import urljoin, urlencode

try:
    from base import Spider as BaseSpider
except ImportError:
    import requests

    class BaseSpider:
        def fetch(self, url, headers=None, timeout=30):
            try:
                resp = requests.get(url, headers=headers or {}, timeout=timeout)
                return resp
            except Exception:
                return None

        def post(self, url, json=None, headers=None, timeout=30):
            try:
                resp = requests.post(url, json=json, headers=headers or {}, timeout=timeout)
                return resp
            except Exception:
                return None

        def log(self, data):
            print("[LOG]", json.dumps(data, ensure_ascii=False))


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://5lxtv.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.58 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = []
        self.video_cache = {}
        self.filters = {}
        self._classes_fetched = False

    def _fetch_classes(self):
        """从 /channels 页面获取分类列表"""
        try:
            url = f"{self.host}/channels"
            resp = self.fetch(url, headers=self.headers)
            if not resp or resp.status_code != 200:
                return False

            html = resp.text if hasattr(resp, 'text') else resp.content.decode('utf-8', errors='ignore')
            card_pattern = r'<a href="/([^"]+)"[^>]*class="[^"]*group relative[^"]*"[^>]*>.*?<div[^>]*>([^<]+)</div>.*?<div[^>]*>([^<]+)</div>'
            card_matches = re.findall(card_pattern, html, re.DOTALL)

            new_classes = []
            for path, en_name, zh_name in card_matches:
                path = path.strip()
                zh_name = zh_name.strip()
                if path and zh_name:
                    new_classes.append({"type_id": path, "type_name": zh_name})

            if new_classes:
                self.classes = new_classes
                self._classes_fetched = True
                return True
            return False
        except Exception as e:
            self.log({"action": "fetch_classes_fail", "error": str(e)})
            return False

    def _ensure_classes(self):
        if not self.classes and not self._classes_fetched:
            self._fetch_classes()
        if not self.classes:
            self.classes = [
                {"type_id": "chinese", "type_name": "中文字幕"},
                {"type_id": "selfie", "type_name": "偷拍盜攝"},
                {"type_id": "scandal", "type_name": "黑料吃瓜"},
                {"type_id": "exclusive", "type_name": "獨家AV"},
                {"type_id": "cuckold", "type_name": "綠帽NTR"},
                {"type_id": "fc2", "type_name": "FC2外流"},
                {"type_id": "upzhu", "type_name": "網紅UP主"},
            ]

    def getName(self):
        return "51xtv"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        self._ensure_classes()
        return {
            "class": self.classes,
            "filters": self.filters if filter else {}
        }

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self.categoryContent(tid="latest", pg="1", filter=False, extend={})

    def categoryContent(self, tid, pg, filter=False, extend={}):
        page = int(pg) if pg else 1
        if tid == "latest" or not tid:
            url = f"{self.host}/latest"
        else:
            url = f"{self.host}/{tid}"
        if page > 1:
            url = f"{url}?page={page}"

        try:
            resp = self.fetch(url, headers=self.headers)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": page, "pagecount": 1, "limit": 0, "total": 0}

            html = resp.text if hasattr(resp, 'text') else resp.content.decode('utf-8', errors='ignore')
            video_pattern = r'<a href="/videos/([^"]+)"[^>]*>.*?<img src="([^"]+)"[^>]*>.*?<span[^>]*>([^<]+)</span>.*?<div[^>]*>([^<]+)</div>.*?<div[^>]*>([^<]+)</div>'
            matches = re.findall(video_pattern, html, re.DOTALL)

            video_list = []
            for match in matches:
                vid = match[0]
                pic = match[1] if match[1].startswith('http') else f"{self.host}{match[1]}"
                duration = match[2].strip()
                title = match[3].strip()
                date = match[4].strip()

                if vid and title:
                    self.video_cache[vid] = {
                        "id": vid,
                        "title": title,
                        "duration": duration,
                        "pic": pic,
                        "date": date
                    }
                    video_list.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": duration
                    })

            page_pattern = r'<a href="\?page=(\d+)"[^>]*>'
            page_matches = re.findall(page_pattern, html)
            total_pages = 1
            for p in page_matches:
                if int(p) > total_pages:
                    total_pages = int(p)

            return {
                "list": video_list,
                "page": page,
                "pagecount": total_pages,
                "limit": len(video_list),
                "total": len(video_list) * total_pages
            }
        except Exception as e:
            self.log({"action": "category_fail", "tid": tid, "error": str(e)})

        return {"list": [], "page": page, "pagecount": 1, "limit": 0, "total": 0}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}

        vid = str(ids[0])
        item = self.video_cache.get(vid)

        if not item or not item.get('play_url'):
            try:
                url = f"{self.host}/videos/{vid}"
                resp = self.fetch(url, headers=self.headers)
                if resp and resp.status_code == 200:
                    html = resp.text if hasattr(resp, 'text') else resp.content.decode('utf-8', errors='ignore')

                    title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
                    title = title_match.group(1).strip() if title_match else ""

                    play_url = ""
                    # 提取播放API参数
                    slug_match = re.search(r'slug\s*=\s*"([^"]+)"', html)
                    t_match = re.search(r'var\s+t\s*=\s*(\d+)', html)
                    n_match = re.search(r'var\s+n\s*=\s*"([^"]+)"', html)
                    
                    if slug_match and t_match and n_match:
                        slug = slug_match.group(1)
                        t_val = t_match.group(1)
                        n_val = n_match.group(1)
                        play_url = f"{self.host}/api/play/{slug}?t={t_val}&n={n_val}"
                    else:
                        # 兜底：直接匹配 m3u8
                        src_match = re.search(r'var\s+src\s*=\s*"([^"]+\.m3u8[^"]*)"', html)
                        if src_match:
                            play_url = src_match.group(1)
                        else:
                            m3u8_match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
                            if m3u8_match:
                                play_url = m3u8_match.group(0)
                            else:
                                iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', html)
                                if iframe_match:
                                    iframe_url = iframe_match.group(1)
                                    if not iframe_url.startswith('http'):
                                        iframe_url = self.host + iframe_url
                                    iframe_resp = self.fetch(iframe_url, headers=self.headers)
                                    if iframe_resp and iframe_resp.status_code == 200:
                                        iframe_text = iframe_resp.text if hasattr(iframe_resp, 'text') else iframe_resp.content.decode('utf-8', errors='ignore')
                                        m3u8_match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', iframe_text)
                                        if m3u8_match:
                                            play_url = m3u8_match.group(0)

                    if item:
                        item['title'] = title
                        item['play_url'] = play_url
                    else:
                        item = {
                            "id": vid,
                            "title": title,
                            "pic": "",
                            "duration": "",
                            "play_url": play_url
                        }
                        self.video_cache[vid] = item
            except Exception as e:
                self.log({"action": "detail_fail", "vid": vid, "error": str(e)})
                return {"list": []}

        if not item:
            return {"list": []}

        vod = {
            "vod_id": vid,
            "vod_name": item.get("title", ""),
            "vod_pic": item.get("pic", ""),
            "vod_remarks": item.get("duration", ""),
            "vod_content": "",
            "vod_play_from": "直链",
            "vod_play_url": f"播放${item.get('play_url', '')}" if item.get('play_url') else ""
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        page = int(pg) if pg else 1
        url = f"{self.host}/search?q={key}&page={page}"

        try:
            resp = self.fetch(url, headers=self.headers)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": page, "pagecount": 1, "limit": 0, "total": 0}

            html = resp.text if hasattr(resp, 'text') else resp.content.decode('utf-8', errors='ignore')
            video_pattern = r'<a href="/videos/([^"]+)"[^>]*>.*?<img src="([^"]+)"[^>]*>.*?<div[^>]*>([^<]+)</div>'
            matches = re.findall(video_pattern, html, re.DOTALL)

            video_list = []
            for match in matches:
                vid = match[0]
                pic = match[1] if match[1].startswith('http') else f"{self.host}{match[1]}"
                title = match[2].strip()

                if vid and title:
                    video_list.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": ""
                    })

            return {
                "list": video_list,
                "page": page,
                "pagecount": 1,
                "limit": len(video_list),
                "total": len(video_list)
            }
        except Exception as e:
            self.log({"action": "search_fail", "error": str(e)})

        return {"list": [], "page": page, "pagecount": 1, "limit": 0, "total": 0}

    def playerContent(self, flag, id, vipFlags=""):
        if not id:
            return {"parse": 1, "url": ""}

        if id.startswith("http://") or id.startswith("https://"):
            if ".m3u8" in id or ".mp4" in id:
                return {"parse": 0, "url": id, "header": {"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]}}
            # 播放API URL
            if "/api/play/" in id:
                return {"parse": 0, "url": id, "header": {"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]}}
            return {"parse": 1, "url": id, "header": {"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]}}

        item = self.video_cache.get(str(id))
        if item and item.get("play_url"):
            play_url = item["play_url"]
            if "/api/play/" in play_url:
                return {"parse": 0, "url": play_url, "header": {"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]}}
            return {"parse": 1, "url": play_url, "header": {"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]}}

        return {"parse": 1, "url": id, "header": {"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]}}

    def localProxy(self, param):
        url = param.get("url", "")
        if not url:
            return [404, "text/plain", "Not Found"]

        if "key.bin" in url:
            try:
                resp = self.fetch(url, headers={"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                if resp and resp.status_code == 200:
                    return [200, "application/octet-stream", resp.content]
            except Exception as e:
                self.log({"action": "localProxy_key_fail", "error": str(e)})

        if ".m3u8" in url:
            try:
                resp = self.fetch(url, headers={"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                if resp and resp.status_code == 200:
                    content = resp.text if hasattr(resp, 'text') else resp.content.decode('utf-8', errors='ignore')
                    lines = content.split('\n')
                    new_lines = []
                    base_url = url.rsplit('/', 1)[0]
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        if not line.startswith('#'):
                            if not line.startswith('http'):
                                line = base_url + '/' + line
                        new_lines.append(line)
                    return [200, "application/vnd.apple.mpegurl", '\n'.join(new_lines)]
            except Exception as e:
                self.log({"action": "localProxy_m3u8_fail", "error": str(e)})

        return [404, "text/plain", "Not Found"]

    def destroy(self):
        self.video_cache.clear()