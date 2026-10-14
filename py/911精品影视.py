# coding: utf-8
"""
911精品影视 - hhzx1.xyz
苹果CMS repiannew 模板
"""
import re
import json
import urllib.request
import urllib.parse
from urllib.parse import urljoin, quote, unquote

try:
    from bs4 import BeautifulSoup
except ImportError:
    pass

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def fetch(self, url, headers=None):
            req = urllib.request.Request(url, headers=headers or {})
            resp = urllib.request.urlopen(req)
            return type('Response', (), {'text': resp.read().decode('utf-8', errors='ignore')})()
        def post(self, url, data=None, headers=None):
            data_bytes = urllib.parse.urlencode(data).encode('utf-8') if data else None
            req = urllib.request.Request(url, data=data_bytes, headers=headers or {})
            resp = urllib.request.urlopen(req)
            return type('Response', (), {'text': resp.read().decode('utf-8', errors='ignore')})()
        def log(self, msg):
            print(msg)


class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.host = "https://hhzx1.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "16", "type_name": "国产精品"},
            {"type_id": "17", "type_name": "中文字幕"},
            {"type_id": "18", "type_name": "强奸乱伦"},
            {"type_id": "19", "type_name": "动漫精品"},
            {"type_id": "20", "type_name": "欧美激情"},
            {"type_id": "21", "type_name": "三级伦理"},
            {"type_id": "22", "type_name": "变态调教"},
            {"type_id": "23", "type_name": "亚洲精品"},
        ]
        area_filters = [{"key": "area", "name": "地区", "value": [
            {"n": "全部", "v": ""},
            {"n": "大陆", "v": "大陆"},
            {"n": "香港", "v": "香港"},
            {"n": "台湾", "v": "台湾"},
            {"n": "美国", "v": "美国"},
            {"n": "韩国", "v": "韩国"},
            {"n": "日本", "v": "日本"},
            {"n": "泰国", "v": "泰国"},
            {"n": "新加坡", "v": "新加坡"},
            {"n": "马来西亚", "v": "马来西亚"},
            {"n": "印度", "v": "印度"},
            {"n": "英国", "v": "英国"},
            {"n": "法国", "v": "法国"},
            {"n": "加拿大", "v": "加拿大"},
            {"n": "西班牙", "v": "西班牙"},
            {"n": "俄罗斯", "v": "俄罗斯"},
            {"n": "其它", "v": "其它"},
        ]}]
        self.filters = {}
        for cid in ["16", "17", "18", "19", "20", "21", "22", "23"]:
            self.filters[cid] = area_filters

    def getName(self):
        return "911精品影视"

    def getDependence(self):
        return ["bs4"]

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            html = self.fetch(self.host + "/", headers=self.headers).text
            soup = BeautifulSoup(html, "html.parser")
            items = []
            for li in soup.select(".commend li, .ccommend li, .tab .box li"):
                a = li.find("a")
                if not a:
                    continue
                href = a.get("href", "").strip()
                match = re.search(r"vod-detail-id-(\d+)\.html", href)
                if not match:
                    continue
                vid = match.group(1)
                title = a.get("title", "")
                if not title:
                    img = li.find("img")
                    if img:
                        title = img.get("alt", "")
                if not title:
                    strong = li.find("strong")
                    if strong:
                        title = strong.text.strip()
                if not title:
                    title = a.text.strip()
                if not title:
                    continue
                img = li.find("img")
                pic = ""
                if img:
                    pic = img.get("original", "") or img.get("src", "")
                    if pic and not pic.startswith("http"):
                        pic = urljoin(self.host, pic)
                span = li.find("span")
                remark = span.text.strip() if span else ""
                items.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
                if len(items) >= 20:
                    break
            return {"list": items}
        except Exception as e:
            self.log("homeVideoContent error: " + str(e))
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg) if pg else 1
            area = ""
            if isinstance(extend, dict):
                area = extend.get("area", "")
            elif isinstance(extend, str):
                try:
                    ex = json.loads(extend)
                    area = ex.get("area", "")
                except:
                    if "area=" in extend:
                        m = re.search(r"area=([^}\"]+)", extend)
                        if m:
                            area = m.group(1).strip()

            if area:
                url = f"{self.host}/index.php?m=vod-list-id-{tid}-pg-{pg}-order--by--class--year--letter--area-{quote(area)}-lang-.html"
            else:
                url = f"{self.host}/index.php?m=vod-list-id-{tid}-pg-{pg}-order--by-time-class--year--letter--area--lang-.html"

            html = self.fetch(url, headers=self.headers).text
            soup = BeautifulSoup(html, "html.parser")

            items = []
            for li in soup.select(".shannel ul li"):
                a = li.find("a")
                if not a:
                    continue
                href = a.get("href", "").strip()
                match = re.search(r"vod-detail-id-(\d+)\.html", href)
                if not match:
                    continue
                vid = match.group(1)
                title = a.get("title", "")
                if not title:
                    h2 = li.find("h2")
                    if h2:
                        a2 = h2.find("a")
                        if a2:
                            title = a2.text.strip()
                if not title:
                    continue
                img = li.find("img")
                pic = ""
                if img:
                    pic = img.get("original", "") or img.get("src", "")
                    if pic and not pic.startswith("http"):
                        pic = urljoin(self.host, pic)
                remark = ""
                status_span = li.find("p", string=re.compile(r"状态"))
                if status_span:
                    blue = status_span.find("font", class_="blue")
                    if blue:
                        remark = blue.text.strip()
                if not remark:
                    for span in li.find_all("span"):
                        if span.text.strip():
                            remark = span.text.strip()
                            break
                items.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })

            pagecount = 1
            page_links = soup.select(".page a")
            for a in page_links:
                if "最后一页" in a.text or "末页" in a.text:
                    href = a.get("href", "")
                    m = re.search(r"pg-(\d+)", href)
                    if m:
                        pagecount = int(m.group(1))
                    break
            if pagecount == 1:
                for a in page_links:
                    m = re.search(r"pg-(\d+)", a.get("href", ""))
                    if m:
                        pc = int(m.group(1))
                        if pc > pagecount:
                            pagecount = pc

            return {
                "list": items,
                "page": pg,
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception as e:
            self.log("categoryContent error: " + str(e))
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            vid = str(ids[0])
            url = f"{self.host}/?m=vod-detail-id-{vid}.html"
            html = self.fetch(url, headers=self.headers).text
            soup = BeautifulSoup(html, "html.parser")

            title = ""
            pic = ""
            content = ""
            play_from = ""
            play_url = ""

            h1 = soup.find("h1")
            if h1:
                title = h1.text.strip()

            img = soup.select_one(".info .pic")
            if img:
                pic = img.get("src", "")
                if pic and not pic.startswith("http"):
                    pic = urljoin(self.host, pic)

            desc = soup.select_one(".description2")
            if desc:
                content = desc.text.strip().replace("剧情:", "").strip()

            play_from_elem = soup.select_one(".playfrom strong span")
            if play_from_elem:
                play_from = play_from_elem.text.strip()
            else:
                play_from = "播放"

            ep_list = []
            for a in soup.select("#vlink_1 li a, #vlink_1 a"):
                href = a.get("href", "").strip()
                name = a.text.strip()
                if href and name:
                    match = re.search(r"vod-play-id-(\d+)-src-(\d+)-num-(\d+)\.html", href)
                    if match:
                        play_id = f"{match.group(1)}|{match.group(2)}|{match.group(3)}"
                        ep_list.append(f"{name}${play_id}")
                    else:
                        ep_list.append(f"{name}${vid}")

            if ep_list:
                play_url = "$$$".join(ep_list)
            else:
                play_url = f"正片${vid}"

            vod = {
                "vod_id": vid,
                "vod_name": title or "未知影片",
                "vod_pic": pic,
                "vod_content": content,
                "vod_play_from": play_from,
                "vod_play_url": play_url
            }
            return {"list": [vod]}
        except Exception as e:
            self.log("detailContent error: " + str(e))
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg) if pg else 1
            # 使用 GET 请求，关键词放在 URL 中
            url = f"{self.host}/index.php?m=vod-search&wd={quote(key)}"
            html = self.fetch(url, headers=self.headers).text
            soup = BeautifulSoup(html, "html.parser")

            items = []
            for li in soup.select("li"):
                a = li.find("a")
                if not a:
                    continue
                href = a.get("href", "").strip()
                match = re.search(r"vod-detail-id-(\d+)\.html", href)
                if not match:
                    continue
                vid = match.group(1)
                title = a.get("title", "")
                if not title:
                    title = a.text.strip()
                if not title:
                    continue
                img = li.find("img")
                pic = ""
                if img:
                    pic = img.get("original", "") or img.get("src", "")
                    if pic and not pic.startswith("http"):
                        pic = urljoin(self.host, pic)
                span = li.find("span")
                remark = span.text.strip() if span else ""
                items.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })

            return {"list": items, "page": pg, "pagecount": 1}
        except Exception as e:
            self.log("searchContent error: " + str(e))
            return {"list": [], "page": 1, "pagecount": 1}

    def playerContent(self, flag, id, vipFlags):
        try:
            parts = id.split("|")
            if len(parts) == 3:
                vid, src, num = parts
                play_url = f"{self.host}/?m=vod-play-id-{vid}-src-{src}-num-{num}.html"
            else:
                play_url = f"{self.host}/?m=vod-play-id-{id}-src-1-num-1.html"

            html = self.fetch(play_url, headers=self.headers).text

            match = re.search(r"mac_url\s*=\s*unescape\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", html)
            if match:
                encoded = match.group(1)
                decoded = self._unescape(encoded)
                if "$" in decoded:
                    _, m3u8_url = decoded.split("$", 1)
                    m3u8_url = unquote(m3u8_url)
                    if m3u8_url.startswith("http") and (".m3u8" in m3u8_url or ".mp4" in m3u8_url):
                        return {"parse": 0, "url": m3u8_url, "header": self.headers}

            m3u8_match = re.search(r"(https?://[^\s'\"]+\.m3u8[^\s'\"]*)", html)
            if m3u8_match:
                return {"parse": 0, "url": m3u8_match.group(1), "header": self.headers}

            return {"parse": 1, "url": id}
        except Exception as e:
            self.log("playerContent error: " + str(e))
            return {"parse": 1, "url": id}

    def _unescape(self, s):
        result = re.sub(r'%u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)
        result = re.sub(r'%([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), result)
        return result

    def localProxy(self, param):
        return [200, "application/octet-stream", "", {"Cache-Control": "no-store"}]