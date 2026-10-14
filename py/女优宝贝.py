import sys
import re
import json
import requests as req
from base.spider import Spider

# 禁用 SSL 警告
from requests.packages.urllib3.exceptions import InsecureRequestWarning
req.packages.urllib3.disable_warnings(InsecureRequestWarning)

class Spider(Spider):
    site_url = "https://nvyou.baby"
    common_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"

    def getName(self):
        return "日本女优精选"

    def init(self, extend=""):
        super().init(extend)

    def homeContent(self, filter):
        cate_list = [
            {"type_name": "艺术精选", "type_id": "23"},
            {"type_name": "女优精选", "type_id": "22"},
            {"type_name": "无码步兵", "type_id": "21"},
            {"type_name": "无码素人", "type_id": "20"},
            {"type_name": "欧美精品", "type_id": "24"}
        ]
        return {"class": cate_list}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        url = f"{self.site_url}/index.php/vod/type/id/{tid}/page/{pg}.html"
        res = req.get(url, headers={"User-Agent": self.common_ua}, verify=False, timeout=15)
        video_list = []
        if res.status_code == 200:
            blocks = res.text.split('ewave-vodlist__item')
            for block in blocks[1:]:
                link = re.search(r'href=["\'](/index.php/vod/detail/id/\d+\.html)["\']', block)
                name = re.search(r'title=["\']([^"\']+)["\']', block)
                pic = re.search(r'data-original=["\']([^"\']+)["\']', block)
                if link and name and pic:
                    video_list.append({
                        "vod_id": link.group(1),
                        "vod_name": name.group(1),
                        "vod_pic": pic.group(1) if pic.group(1).startswith("http") else self.site_url + pic.group(1),
                        "vod_remarks": "高清"
                    })
        return {"list": video_list, "page": pg, "pagecount": pg + 1}

    def detailContent(self, ids):
        url = self.site_url + ids[0]
        res = req.get(url, headers={"User-Agent": self.common_ua}, verify=False, timeout=15)
        if res.status_code != 200: return {"list": []}
        
        html = res.text
        name = re.search(r'title">([^<]+)</h1>', html) or re.search(r'<title>([^<]+)</title>', html)
        pic = re.search(r'data-original=["\']([^"\']+)["\']', html)
        
        # 提取播放链接
        play_matches = re.findall(r'href=["\'](/index.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)["\'][^>]*>([^<]+)</a>', html)
        play_urls = [f"{m[1]}${m[0]}" for m in play_matches]
        
        # 如果没找到列表，尝试拼凑一个
        if not play_urls:
            play_urls = ["立即播放$" + ids[0].replace("detail", "play")]

        video = {
            "vod_id": ids[0],
            "vod_name": name.group(1).split("-")[0].strip() if name else "视频详情",
            "vod_pic": pic.group(1) if pic else "",
            "vod_play_from": "站内播放器",
            "vod_play_url": "#".join(play_urls)
        }
        return {"list": [video]}

    def playerContent(self, flag, id, vipFlags):
        url = self.site_url + id
        res = req.get(url, headers={"User-Agent": self.common_ua}, verify=False, timeout=15)
        if res.status_code != 200: return {"parse": 0, "url": ""}

        # 核心解析逻辑：提取 player_aaaa 变量中的 url 字段
        match = re.search(r'player_aaaa\s*=\s*({.*?})', res.text)
        if match:
            try:
                config = json.loads(match.group(1))
                play_url = config.get("url", "").replace("\/", "/")
                if play_url:
                    return {"parse": 0, "url": play_url, "header": {"User-Agent": self.common_ua, "Referer": self.site_url}}
            except: pass
        
        # 兜底：全局匹配 m3u8
        m3u8 = re.search(r'["\'](http[^"\']+\.m3u8[^"\']*)["\']', res.text)
        if m3u8:
            return {"parse": 0, "url": m3u8.group(1).replace("\/", "/")}

        return {"parse": 1, "url": url}

    def searchContent(self, key, quick, pg=1):
        url = f"{self.site_url}/index.php/vod/search/wd/{key}/page/{pg}.html"
        res = req.get(url, headers={"User-Agent": self.common_ua}, verify=False, timeout=15)
        video_list = []
        if res.status_code == 200:
            blocks = res.text.split('ewave-vodlist__item')
            for block in blocks[1:]:
                link = re.search(r'href=["\'](/index.php/vod/detail/id/\d+\.html)["\']', block)
                name = re.search(r'title=["\']([^"\']+)["\']', block)
                pic = re.search(r'data-original=["\']([^"\']+)["\']', block)
                if link and name and pic:
                    video_list.append({
                        "vod_id": link.group(1),
                        "vod_name": name.group(1),
                        "vod_pic": pic.group(1) if pic.group(1).startswith("http") else self.site_url + pic.group(1)
                    })
        return {"list": video_list}