# coding: utf-8
# TVBox FongMi 爬虫 - 福利宝宝 (fulibao1.cyou)
# 站点聚合站，所有分类内容相同，只保留一个分类
# 翻页格式: /index.php/vod/type/id/1001.html?page={pg}

import re
import json
from urllib.parse import urljoin

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def fetch(self, url, headers=None, **kwargs):
            import requests
            return requests.get(url, headers=headers, timeout=15)
        def post(self, url, data=None, json=None, headers=None, **kwargs):
            import requests
            return requests.post(url, data=data, json=json, headers=headers, timeout=15)
        def log(self, msg):
            print(msg)


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://fulibao1.cyou"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "1001", "type_name": "福利宝宝"},
        ]
        self.filters = {}

    def getName(self):
        return "福利宝宝"

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self.categoryContent("1001", "1", None, None)

    def categoryContent(self, tid, pg, filter, extend):
        pg = pg or "1"
        url = f"{self.host}/index.php/vod/type/id/1001.html?page={pg}"
        return self._fetch_list(url, pg)

    def _fetch_list(self, url, pg=1):
        try:
            resp = self.fetch(url, headers=self.headers)
            html = resp.text
        except Exception as e:
            self.log({"action": "fetch_list_fail", "url": url, "error": str(e)})
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}

        items = []
        pattern = r'<td id="gametd">\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)<br><img[^>]+(?:data-original|src)="([^"]+)"'
        matches = re.findall(pattern, html, re.DOTALL)

        for match in matches:
            link = match[0].strip()
            name = match[1].strip()
            pic = match[2].strip()
            vod_id_match = re.search(r'/play/id/(\d+)', link)
            if not vod_id_match:
                continue
            vod_id = vod_id_match.group(1)
            detail_url = link if link.startswith("http") else urljoin(self.host, link)
            items.append({
                "vod_id": f"{vod_id}|$|{name}|$|{pic}|$||$|{detail_url}",
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "",
            })

        # 提取最大页码
        pages = re.findall(r'<a href="[^"]*\?page=(\d+)"', html)
        pagecount = max([int(p) for p in pages]) if pages else 1

        if pagecount <= 1:
            page_area = re.search(r'第\s*\d+\s*页.*?共\s*(\d+)\s*页', html)
            if page_area:
                pagecount = int(page_area.group(1))

        return {
            "list": items,
            "page": int(pg),
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20
        }

    def detailContent(self, ids):
        raw = str(ids[0])
        parts = raw.split('|$|')
        vod_id = parts[0]
        name = parts[1] if len(parts) > 1 else ""
        pic = parts[2] if len(parts) > 2 else ""
        remark = parts[3] if len(parts) > 3 else ""
        play_url = parts[4] if len(parts) > 4 else f"{self.host}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"

        vod = {
            "vod_id": raw,
            "vod_name": name or f"视频{vod_id}",
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_content": remark,
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}"
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        try:
            resp = self.post(
                f"{self.host}/index.php/vod/search.html",
                data={"wd": key},
                headers=self.headers
            )
            html = resp.text
        except Exception:
            return {"list": [], "page": int(pg), "pagecount": 1}

        items = []
        pattern = r'<td id="gametd">\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)<br><img[^>]+(?:data-original|src)="([^"]+)"'
        matches = re.findall(pattern, html, re.DOTALL)

        for match in matches:
            link = match[0].strip()
            name = match[1].strip()
            pic = match[2].strip()
            vod_id_match = re.search(r'/play/id/(\d+)', link)
            if not vod_id_match:
                continue
            vod_id = vod_id_match.group(1)
            detail_url = link if link.startswith("http") else urljoin(self.host, link)
            items.append({
                "vod_id": f"{vod_id}|$|{name}|$|{pic}|$||$|{detail_url}",
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "",
            })

        return {"list": items, "page": int(pg), "pagecount": 1}

    def playerContent(self, flag, play_url, vipFlags):
        if play_url.endswith((".m3u8", ".mp4")):
            return {"parse": 0, "url": play_url, "header": self.headers}

        try:
            resp = self.fetch(play_url, headers=self.headers)
            html = resp.text
        except Exception:
            return {"parse": 1, "url": play_url, "header": self.headers}

        player_match = re.search(r'var\s+player_aaaa\s*=\s*({.*?});', html, re.DOTALL)
        if not player_match:
            mac_match = re.search(r'MacPlayer\.PlayUrl\s*=\s*"([^"]+)"', html)
            if mac_match:
                m3u8_url = mac_match.group(1).replace('\\/', '/')
                return {"parse": 0, "url": m3u8_url, "header": self.headers}
            m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
            if m3u8_match:
                return {"parse": 0, "url": m3u8_match.group(1), "header": self.headers}
            return {"parse": 1, "url": play_url, "header": self.headers}

        try:
            player_data = json.loads(player_match.group(1))
            m3u8_url = player_data.get("url", "").replace('\\/', '/')
            if m3u8_url and m3u8_url.endswith((".m3u8", ".mp4")):
                return {"parse": 0, "url": m3u8_url, "header": self.headers}
            elif m3u8_url:
                if not m3u8_url.startswith("http"):
                    m3u8_url = urljoin(play_url, m3u8_url)
                return self.playerContent(flag, m3u8_url, vipFlags)
            else:
                return {"parse": 1, "url": play_url, "header": self.headers}
        except json.JSONDecodeError:
            url_match = re.search(r'"url"\s*:\s*"([^"]+)"', player_match.group(1))
            if url_match:
                m3u8_url = url_match.group(1).replace('\\/', '/')
                if m3u8_url.endswith((".m3u8", ".mp4")):
                    return {"parse": 0, "url": m3u8_url, "header": self.headers}
            return {"parse": 1, "url": play_url, "header": self.headers}

    def localProxy(self, params):
        return [404, "text/plain", "Not Found", {}]

    def destroy(self):
        pass