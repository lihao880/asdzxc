import sys, re, json
import urllib.request
import urllib.parse

class Spider():
    def __init__(self):
        self.host = "https://xojav.tv"

    def getName(self): return "XOJAV"
    def init(self, extend=""): pass
    def getDependence(self): return ['re', 'json']

    def fetch(self, url):
        import urllib.request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': self.host
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as res:
                return res.read().decode('utf-8', errors='ignore')
        except:
            return ""

    def homeContent(self, filter):
        # 根據你提供的 HTML 精確補全分類
        res = {
            'class': [
                {"type_name": "最新影片", "type_id": "latest-updates"},
                {"type_name": "中文字幕", "type_id": "categories/chinese-subtitle"},
                {"type_name": "直接開啪", "type_id": "categories/sex-only"},
                {"type_name": "無碼解放", "type_id": "categories/uncensored"},
                {"type_name": "制服誘惑", "type_id": "categories/uniform"},
                {"type_name": "角色劇情", "type_id": "categories/roleplay"},
                {"type_name": "男友視角", "type_id": "categories/pov"},
                {"type_name": "主奴調教", "type_id": "categories/bdsm"},
                {"type_name": "進犯", "type_id": "categories/intrusion"},
                {"type_name": "流出", "type_id": "categories/hixxen-cam"}
            ],
            'list': []
        }
        try:
            html = self.fetch(self.host)
            res['list'] = self.parseList(html)
        except:
            pass
        return res

    def homeVideoContent(self):
        return {"list": self.parseList(self.fetch(self.host))}

    def categoryContent(self, tid, pg, filter, extend):
        # 判斷 tid 是否已經包含 categories/ 前綴
        path = tid if "categories/" in tid or tid == "latest-updates" else f"categories/{tid}"
        url = f"{self.host}/{path}?page={pg}"
        return {"list": self.parseList(self.fetch(url))}

    def detailContent(self, ids):
        vid = ids[0]
        html = self.fetch(f"{self.host}/videos/{vid}")
        title = re.search(r'property="og:title"\s+content="([^"]+)"', html)
        pic = re.search(r'property="og:image"\s+content="([^"]+)"', html)
        return {"list": [{
            "vod_id": vid,
            "vod_name": title.group(1).replace(' - XOJAV', '').strip() if title else vid,
            "vod_pic": pic.group(1) if pic else "",
            "vod_play_from": "XO-Stream",
            "vod_play_url": f"播放正片${vid}"
        }]}

    def playerContent(self, flag, id, vipFlags):
        video_page = f"{self.host}/videos/{id}"
        html = self.fetch(video_page)
        raw_url = re.search(r"var\s+stream\s*=\s*'([^']+)'", html)
        url = raw_url.group(1).replace('\\/', '/') if raw_url else ""
        return {
            "parse": 0,
            "play": 0,
            "url": url,
            "header": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": video_page
            }
        }

    def parseList(self, html):
        videos = []
        if not html: return videos
        # 使用更穩健的正則匹配影片 ID 和標題
        pattern = r'href="[^"]*/videos/([^"/]+)"[^>]*>.*?alt="([^"]+)"'
        for vid, title in re.findall(pattern, html, re.S):
            if vid not in [v['vod_id'] for v in videos]:
                videos.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": f"https://cdn.18jav.tv/storage/{vid}/320_180.jpg"
                })
        return videos

    def searchContent(self, key, quick):
        import urllib.parse
        url = f"{self.host}/search?q={urllib.parse.quote(key)}"
        return {"list": self.parseList(self.fetch(url))}
