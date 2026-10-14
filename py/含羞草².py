# -*- coding: utf-8 -*-
import re
import json
import base64
from urllib.parse import urljoin, quote, unquote

try:
    import requests
except Exception:
    requests = None

try:
    from lxml import etree
except Exception:
    etree = None


class Spider:
    def __init__(self):
        self.extend = ""
        self.cookie = ""
        self.host = "https://www.mtv77.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "25", "type_name": "一区"}, {"type_id": "26", "type_name": "二区"},
            {"type_id": "27", "type_name": "三区"}, {"type_id": "51", "type_name": "四区"},
            {"type_id": "62", "type_name": "五区"}, {"type_id": "108", "type_name": "六区"},
            {"type_id": "118", "type_name": "七区"}, {"type_id": "128", "type_name": "八区"},
            {"type_id": "141", "type_name": "九区"}
        ]
        self.filters = {
            "25": [{"key": "type_id", "name": "分类", "value": [{"n": "全部", "v": "25"}, {"n": "传媒-星空无限传媒", "v": "71"}, {"n": "传媒-果冻传媒", "v": "70"}, {"n": "传媒-蜜桃传媒", "v": "69"}, {"n": "传媒-精东影业", "v": "68"}, {"n": "传媒-麻豆传媒", "v": "67"}]}],
            "26": [{"key": "type_id", "name": "分类", "value": [{"n": "全部", "v": "26"}, {"n": "欧美-高清有码", "v": "80"}, {"n": "欧美-高清无码", "v": "79"}, {"n": "传媒-天美传媒", "v": "78"}, {"n": "国产-主播", "v": "77"}, {"n": "国产-探花", "v": "76"}, {"n": "国产-偷拍", "v": "75"}, {"n": "国产-自拍", "v": "74"}, {"n": "传媒-性视界传媒", "v": "73"}, {"n": "传媒-SA国际传媒", "v": "72"}]}],
            "27": [{"key": "type_id", "name": "分类", "value": [{"n": "全部", "v": "27"}, {"n": "动漫", "v": "89"}, {"n": "玩偶姐姐", "v": "88"}, {"n": "刘玥", "v": "87"}, {"n": "欧美-中文字幕", "v": "85"}, {"n": "传媒-皇家华人", "v": "84"}, {"n": "日本-高清有码", "v": "83"}, {"n": "日本-无码流出", "v": "82"}, {"n": "日本-中文字幕", "v": "81"}]}],
            "51": [{"key": "type_id", "name": "分类", "value": [{"n": "全部", "v": "51"}, {"n": "台湾粉红兔", "v": "90"}, {"n": "吃瓜黑料", "v": "91"}, {"n": "小众女同", "v": "95"}, {"n": "TS人妖", "v": "96"}, {"n": "传媒-扣扣传媒", "v": "97"}, {"n": "恐怖色情", "v": "98"}]}],
            "62": [{"key": "type_id", "name": "分类", "value": [{"n": "全部", "v": "62"}, {"n": "迷奸强奸", "v": "100"}, {"n": "重口味", "v": "101"}, {"n": "传媒-91传媒", "v": "102"}, {"n": "传媒-杏吧传媒", "v": "103"}, {"n": "传媒-起点传媒", "v": "104"}, {"n": "传媒-CCAV成人头条", "v": "105"}, {"n": "传媒-渡边传媒", "v": "106"}]}],
            "108": [{"key": "type_id", "name": "分类", "value": [{"n": "全部", "v": "108"}, {"n": "传媒-糖心传媒", "v": "111"}, {"n": "传媒-乐播传媒", "v": "112"}, {"n": "传媒-葫芦影业", "v": "113"}, {"n": "传媒-其他传媒", "v": "114"}, {"n": "热门大瓜", "v": "116"}, {"n": "学生校园", "v": "117"}]}],
            "118": [{"key": "type_id", "name": "分类", "value": [{"n": "全部", "v": "118"}, {"n": "动漫-黄漫", "v": "123"}, {"n": "动漫-里番中字", "v": "124"}, {"n": "水果派", "v": "126"}, {"n": "短视频", "v": "127"}]}],
            "128": [{"key": "type_id", "name": "分类", "value": [{"n": "全部", "v": "128"}, {"n": "SM虐待", "v": "129"}, {"n": "NTR 绿帽", "v": "130"}, {"n": "国产-网红", "v": "131"}, {"n": "国产-户外", "v": "132"}, {"n": "国产-吃瓜", "v": "133"}, {"n": "AI换脸", "v": "134"}, {"n": "日本-东京热", "v": "136"}, {"n": "日本-一本道", "v": "137"}]}],
            "141": [{"key": "type_id", "name": "分类", "value": [{"n": "全部", "v": "141"}, {"n": "国产-台湾JVID", "v": "138"}, {"n": "韩国-主播", "v": "140"}, {"n": "日本-素人", "v": "152"}]}]
        }

    # =========================
    # APP 接口 (禁止乱删, 需返回特定格式)
    # =========================
    def getName(self): return "MT777"
    def getDependence(self): return []
    def setExtendInfo(self, extend): 
        self.extend = extend or ""
        return {}
    def init(self, extend=""): 
        self.extend = extend or ""
        return {}
    def getCookie(self): return self.cookie
    def setCookie(self, cookie): 
        self.cookie = cookie or ""
        return {}
    def getHeaders(self): return self.headers
    def destroy(self): pass
    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def localProxy(self, param): return None

    # =========================
    # TVBox / FongMi 核心逻辑
    # =========================
    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters} if filter else {"class": self.classes}

    def homeVideoContent(self):
        return {"list": self._parse_vod_list(self._get("/"))[:30]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg or "1")
        real_tid = str(extend.get("type_id") or extend.get("tid") or extend.get("cateId") or tid or "25") if isinstance(extend, dict) else str(tid or "25")
        path = f"/index.php/vod/type/id/{real_tid}.html" if pg == "1" else f"/index.php/vod/type/id/{real_tid}/page/{pg}.html"
        vods = self._parse_vod_list(self._get(path))
        return {"list": vods, "page": int(pg), "pagecount": 999 if vods else int(pg), "limit": len(vods) if vods else 24, "total": 9999 if vods else 0}

    def detailContent(self, ids):
        play_path = self._to_path(ids[0] if ids else "")
        html = self._get(play_path)

        title = self._clean_title(self._regex(html, r"var\s+vod_name\s*=\s*['\"]([^'\"]+)") or self._xpath_text(html, '//h1[contains(@class,"page-title")]//a[1]/@title | //h1[contains(@class,"page-title")]//a[1]/text()') or "视频")
        pic = self._abs_url(self._xpath_attr(html, '//div[contains(@class,"player-info")]//img/@data-src | //div[contains(@class,"player-info")]//img/@data-original | //div[contains(@class,"player-info")]//img/@src | //div[contains(@class,"video-cover")]//img/@data-src | //div[contains(@class,"module-item-pic")]//img/@data-src | //meta[@property="og:image"]/@content'))
        type_name = self._clean(self._xpath_text(html, '//div[contains(@class,"video-info-aux")]//a[contains(@href,"/index.php/vod/type/id/")][1]//text()'))
        remark = self._clean(self._regex(html, r"vod_part\s*=\s*['\"]([^'\"]+)")) or "HD"
        desc = self._clean(self._xpath_text(html, '//meta[@name="description"]/@content').replace(title + "HD免费在线观看,", "").replace(title + "剧情介绍", "").replace("[展开全部]", "").replace("[收起部分]", ""))

        return {"list": [{
            "vod_id": play_path, "vod_name": title, "vod_pic": pic, "type_name": type_name,
            "vod_year": "", "vod_area": "", "vod_remarks": remark, "vod_actor": "",
            "vod_director": "", "vod_content": desc or title, "vod_play_from": "MT777直连",
            "vod_play_url": "播放$" + play_path
        }]}

    def searchContent(self, key, quick, pg="1"):
        pg, wd = str(pg or "1"), quote(key or "")
        path = f"/index.php/vod/search/wd/{wd}.html" if pg == "1" else f"/index.php/vod/search/page/{pg}/wd/{wd}.html"
        vods = self._parse_vod_list(self._get(path))
        return {"list": vods, "page": int(pg), "pagecount": 999 if vods else int(pg), "limit": len(vods) if vods else 10, "total": 9999 if vods else 0}

    def playerContent(self, flag, id, vipFlags):
        play_id = str(id or "").strip()

        if play_id.startswith("http") and re.search(r"\.(m3u8|mp4)(\?|$)", play_id, re.I):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": play_id, "header": self.headers}

        m = re.search(r'/id/(\d+)', play_id)
        if m:
            vid = m.group(1)
            nid = self._regex(play_id, r'/nid/(\d+)') or '1'
            sid = self._regex(play_id, r'/sid/(\d+)') or '1'
            player_path = f"/index.php/vod/player/id/{vid}/nid/{nid}/sid/{sid}.html"
        else:
            player_path = play_id.replace("/vod/play/", "/vod/player/")

        play_url = self._extract_player_url(self._get(player_path))

        if not play_url:
            html = self._get(play_id)
            iframe_src = self._xpath_attr(html, '//iframe[contains(@src, "/vod/player/")]/@src | //iframe[@id="player_if"]/@src')
            play_url = self._extract_player_url(self._get(iframe_src)) if iframe_src else self._extract_player_url(html)

        if not play_url:
            return {"parse": 1, "jx": 1, "playUrl": "", "url": self._abs_url(play_id), "header": self.headers}

        return {"parse": 0, "jx": 0, "playUrl": "", "url": play_url, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/", "Origin": self.host}}

    # =========================
    # 解析工具
    # =========================
    def _extract_player_url(self, html):
        if not html: return ""
        js = self._regex(html, r'var\s+player_[a-zA-Z0-9_]+\s*=\s*(\{.*?\})(?:;|</script>)') or self._regex(html, r'var\s+player_[a-zA-Z0-9_]+\s*=\s*(\{.*?\})')
        if js:
            try:
                data = json.loads(js)
                url = data.get("url", "")
                encrypt = int(data.get("encrypt", 0))
                if encrypt == 1: url = unquote(url)
                elif encrypt == 2: url = unquote(base64.b64decode(url).decode("utf-8", errors="ignore"))
                return str(url).replace("\\/", "/")
            except Exception:
                url = self._regex(js, r'"url"\s*:\s*"([^"]+)"')
                if url: return str(url).replace("\\/", "/")
        url = self._regex(html, r'(https?:\\?/\\?/[^"\']+?\.(?:m3u8|mp4)[^"\']*)')
        return str(url).replace("\\/", "/") if url else ""

    def _parse_vod_list(self, html):
        vods, seen = [], set()
        if not html: return vods
        doc = self._doc(html)

        if doc is not None:
            for a in doc.xpath('//a[contains(@href,"/index.php/vod/play/id/")]'):
                try:
                    href = self._first(a.xpath("./@href"))
                    if not href: continue
                    play_path = self._to_path(href)
                    if not play_path or play_path in seen: continue

                    title = self._first(a.xpath('./@title | .//img/@alt | ./text()'))
                    if not title:
                        parent = a.xpath('./ancestor::div[contains(@class,"module-item") or contains(@class,"module-search-item")][1]')
                        if parent:
                            title = self._first(parent[0].xpath('.//a[contains(@class,"module-item-title")]/@title | .//img/@alt'))

                    title = self._clean_title(title)
                    if not title: continue

                    parent = a.xpath('./ancestor::div[contains(@class,"module-item") or contains(@class,"module-search-item")][1]')
                    pic = self._first(parent[0].xpath('.//img/@data-src | .//img/@data-original | .//img/@src')) if parent else ""
                    remark = self._first(parent[0].xpath('.//div[contains(@class,"module-item-text")]/text() | .//span[contains(@class,"video-class")]/text()')) if parent else "HD"

                    seen.add(play_path)
                    vods.append({"vod_id": play_path, "vod_name": title, "vod_pic": self._abs_url(pic), "vod_remarks": self._clean(remark) or "HD"})
                except Exception: pass

        if not vods:
            for href, title in re.findall(r'<a[^>]+href="([^"]*?/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"[^>]*title="([^"]*)"', html, re.S):
                play_path = self._to_path(href)
                title = self._clean_title(title)
                if play_path and title and play_path not in seen:
                    seen.add(play_path)
                    vods.append({"vod_id": play_path, "vod_name": title, "vod_pic": "", "vod_remarks": "HD"})
        return vods

    # =========================
    # 基础请求与字符串处理
    # =========================
    def _get(self, path):
        if requests is None: return ""
        try:
            r = requests.get(self._abs_url(path), headers=self.headers, timeout=15, verify=False)
            r.encoding = "utf-8"
            return r.text or ""
        except Exception: return ""

    def _doc(self, html):
        try: return etree.HTML(html.encode("utf-8", errors="ignore"), parser=etree.HTMLParser(encoding="utf-8")) if etree and html else None
        except Exception: return None

    def _xpath_text(self, html, xp):
        doc = self._doc(html)
        return self._clean(" ".join([str(x) for x in doc.xpath(xp) if x is not None])) if doc is not None else ""

    def _xpath_attr(self, html, xp):
        doc = self._doc(html)
        return self._first(doc.xpath(xp)) if doc is not None else ""

    def _first(self, arr):
        return next((self._clean(str(x)) for x in (arr or []) if x is not None and self._clean(str(x))), "")

    def _regex(self, text, pattern):
        m = re.search(pattern, text or "", re.S)
        return m.group(1).strip() if m else ""

    def _to_path(self, url):
        url = str(url or "").replace("\\/", "/").strip()
        m = re.search(r"https?://[^/]+(.+)", url)
        return m.group(1) if m else ("/" + url if not url.startswith("/") else url)

    def _abs_url(self, url):
        url = str(url or "").replace("\\/", "/").strip()
        return "https:" + url if url.startswith("//") else (url if url.startswith("http") else urljoin(self.host, url))

    def _clean_title(self, s):
        s = self._clean(s)
        return re.sub(r"\s*免费在线观看.*$|\s*-\s*含羞草\s*$|\s*HD\s*-\s*含羞草.*$|^(立刻播放|在线播放)", "", s).strip() if s else ""

    def _clean(self, s):
        if not s: return ""
        s = re.sub(r"<[^>]+>|<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", str(s), flags=re.I)
        for k, v in {"\u3000": " ", "&nbsp;": " ", "&amp;": "&", "&quot;": '"', "&#39;": "'", "&lt;": "<", "&gt;": ">"}.items(): s = s.replace(k, v)
        return re.sub(r"\s+", " ", s).strip()
