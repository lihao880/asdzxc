# -*- coding: utf-8 -*-
"""
秘书AI短剧 - https://mishu.mishuzw.sbs (MacCMS MediaVault_Wine 模板)
按用户「全家桶模板」(_____4_107x 歪比巴卜结构) 编写:
  requests.Session 复用连接 + 全套浏览器请求头 + Cookie 维护 + 请求重试;
  searchable/quickSearch/filterable/changeable 全开; 分类跨页去重; 搜索缓存 60 秒。



实勘 (2026-10-23, 沙箱全链实测):
  分类页: /index.php/vod/type/id/{tid}/page/{pg}.html, 30 条/页;
  卡片: article.media-card > a.thumb[href=/index.php/vod/detail/id/{id}.html][title]
        > img[src=封面] + span 备注;
  详情: /index.php/vod/detail/id/{vid}.html, h1 为片名,
        封面 div.detail-image-wrapper > img;
        线路块 div.play-list: <strong> 为线路名 (如 jpm3u8),
        剧集 a.play-link /index.php/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html;
  播放页: 原生 <video><source src="{m3u8}"> 直链 parse=0;
  搜索: /index.php/vod/search/page/{pg}/wd/{quote(kw)}.html。
"""
import json
import re
import time
from urllib.parse import quote
import requests
from base.spider import Spider


class Spider(Spider):
    name = "秘书AI短剧"
    base_url = "https://mishu.mishuzw.sbs"
    HOME_URL = "https://mishu.mishuzw.sbs/"

    searchable = 1
    quickSearch = 1
    filterable = 1
    changeable = 1

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://mishu.mishuzw.sbs/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
    }

    play_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://mishu.mishuzw.sbs/",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    CATEGORY_NAMES = {
        "41": "短剧推荐",
        "1": "视频一区", "2": "视频二区", "3": "视频三区", "4": "视频四区",
        "6": "人妻熟女", "7": "日本无码", "8": "美乳巨乳", "9": "强奸乱伦",
        "10": "制服诱惑", "11": "绝色佳人", "12": "少女萝莉", "13": "AV解说", "14": "TS专区",
        "15": "女同性恋", "16": "AI换脸", "20": "SM调教", "21": "韩国主播",
        "22": "泰国风情", "23": "3D动漫", "24": "中文字幕", "25": "国产精品",
        "26": "主播秀色", "27": "网曝系列", "28": "自拍偷拍", "29": "国产乱伦",
        "30": "国产丝袜", "31": "国产SM", "32": "国产人妻", "33": "探花嫖娼",
        "34": "国产自拍", "35": "国产AI短剧", "36": "网红主播", "37": "国产传媒",
        "38": "三级电影", "39": "抖音视频", "40": "丝袜OL",
    }
    FILTERS = {}

    _CAT_PAGEMARK = {}
    _SEARCH_CACHE = {}
    _SEARCH_CACHE_TTL = 60

    _CARD_RE = re.compile(
        r'<a class="thumb" href="/index\.php/vod/detail/id/(\d+)\.html"(?: title="([^"]*)")?><img src="([^"]+)" alt="([^"]*)"[^>]*>(?:<span>([\s\S]*?)</span>)?')
    _BLOCK_RE = re.compile(r'<div class="play-list">([\s\S]*?)(?=<div class="play-list">|</main>)')
    _FROM_RE = re.compile(r'<strong>([\s\S]*?)</strong>')
    _EP_RE = re.compile(r'<a class="play-link" href="(/index\.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html)"[^>]*>([\s\S]*?)</a>')
    _SRC_RE = re.compile(r'<source src="(https?://[^"]+)"')

    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self._cookies = ""
        self._last_req_time = 0
        self._min_req_interval = 0.12

    def _log(self, msg):
        print(f"[{self.name}] {msg}")

    def _clean(self, x):
        x = re.sub(r"<[^>]+>", "", x or "")
        return x.replace("▶", "").strip()

    def _apply_req_delay(self):
        now = time.time()
        elapsed = now - self._last_req_time
        if 0 < elapsed < self._min_req_interval:
            time.sleep(self._min_req_interval - elapsed)
        self._last_req_time = time.time()

    def fetch(self, url, headers=None, timeout=15):
        self._apply_req_delay()
        return self._session.get(url, headers=headers or {}, timeout=timeout)

    def _extract_cookies(self, resp):
        try:
            items = []
            if getattr(resp, "cookies", None):
                for c in resp.cookies:
                    items.append(f"{c.name}={c.value}")
            if items:
                existing = {}
                for part in self._cookies.split("; "):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        existing[k.strip()] = v
                for c in items:
                    k, v = c.split("=", 1)
                    existing[k.strip()] = v
                self._cookies = "; ".join(f"{k}={v}" for k, v in existing.items())
        except Exception:
            pass

    def _fetch_cookies(self):
        try:
            resp = self.fetch(self.HOME_URL, timeout=10)
            self._extract_cookies(resp)
        except Exception as e:
            self._log(f"Cookie获取失败: {e}")

    def _get(self, url, max_retry=3, timeout=15):
        h = self.headers.copy()
        for attempt in range(max_retry):
            try:
                resp = self.fetch(url, headers=h, timeout=timeout)
                self._extract_cookies(resp)
                if resp.status_code == 200 and resp.text:
                    return resp.text
                self._log(f"请求异常状态 {resp.status_code}: {url}")
            except Exception as e:
                self._log(f"请求失败({attempt + 1}/{max_retry}): {url}, {e}")
            if attempt < max_retry - 1:
                time.sleep(0.6 * (attempt + 1))
        return ""

    def _parse_cards(self, page):
        out, seen = [], set()
        for vid, title, pic, alt, rk in self._CARD_RE.findall(page or ""):
            if vid in seen:
                continue
            seen.add(vid)
            out.append({
                "vod_id": vid,
                "vod_name": self._clean(title or alt),
                "vod_pic": pic,
                "vod_remarks": self._clean(rk or ""),
            })
        return out

    def init(self, extend=""):
        try:
            if extend:
                ext = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(ext, dict) and ext.get("host"):
                    self.base_url = str(ext["host"]).rstrip("/")
                    self.HOME_URL = self.base_url + "/"
                    self.headers["Referer"] = self.base_url + "/"
                    self._session.headers.update(self.headers)
        except Exception:
            pass
        self._fetch_cookies()
        self._log("初始化完成")

    def getName(self):
        return self.name

    def homeContent(self, filter=False):
        result = {
            "class": [
                {"type_id": tid, "type_name": name}
                for tid, name in self.CATEGORY_NAMES.items()
            ]
        }
        if filter:
            result["filters"] = self.FILTERS
            result["filter"] = self.FILTERS
        return result

    def homeVideoContent(self):
        try:
            page = self._get(self.HOME_URL)
            return {"list": self._parse_cards(page)[:36]}
        except Exception as e:
            self._log(f"homeVideoContent异常: {e}")
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, content=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        url = f"{self.base_url}/index.php/vod/type/id/{tid}/page/{pg}.html"
        videos = self._parse_cards(self._get(url))
        key = str(tid)
        if pg > 1 and key in self._CAT_PAGEMARK:
            prev = set(self._CAT_PAGEMARK[key])
            videos = [v for v in videos if v["vod_id"] not in prev] or videos
        self._CAT_PAGEMARK[key] = [v["vod_id"] for v in videos]
        return {"list": videos, "page": pg, "pagecount": 999, "limit": 36, "total": 99999}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) else ids
        page = self._get(f"{self.base_url}/index.php/vod/detail/id/{vid}.html")
        tit = re.search(r"<h1[^>]*>([\s\S]{0,200}?)</h1>", page)
        pic = re.search(r'<div class="detail-image-wrapper"><img src="([^"]+)"', page)
        froms, urls = [], []
        for block in self._BLOCK_RE.findall(page):
            fm = self._FROM_RE.search(block)
            eps = []
            for href, _v, sid, nid, label in self._EP_RE.findall(block):
                eps.append(f"{self._clean(label) or ('第' + nid + '集')}${href}")
            if eps:
                froms.append(self._clean(fm.group(1)) if fm else "默认线路")
                urls.append("#".join(eps))
        vod = {
            "vod_id": str(vid),
            "vod_name": self._clean(tit.group(1)) if tit else "",
            "vod_pic": pic.group(1) if pic else "",
            "vod_play_from": "$$$".join(froms),
            "vod_play_url": "$$$".join(urls),
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags=None):
        url = id if str(id).startswith("http") else self.base_url + str(id)
        page = self._get(url)
        m = self._SRC_RE.search(page)
        if m:
            return {"parse": 0, "playUrl": "", "url": m.group(1), "header": self.play_headers}
        return {"parse": 1, "playUrl": "", "url": url, "header": self.play_headers}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        ckey = (str(key), pg)
        now = time.time()
        hit = self._SEARCH_CACHE.get(ckey)
        if hit and now - hit[0] < self._SEARCH_CACHE_TTL:
            return hit[1]
        url = f"{self.base_url}/index.php/vod/search/page/{pg}/wd/{quote(str(key))}.html"
        result = {"list": self._parse_cards(self._get(url)),
                  "page": pg, "pagecount": 999, "limit": 36, "total": 99999}
        self._SEARCH_CACHE[ckey] = (now, result)
        return result

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self._session.close()
        except Exception:
            pass

    def localProxy(self, param):
        return None


_spider = None


def _get_spider():
    global _spider
    if _spider is None:
        _spider = Spider()
    return _spider


def init(extend=""):
    return _get_spider().init(extend)


def homeContent(filter=False):
    return _get_spider().homeContent(filter)


def homeVideoContent():
    return _get_spider().homeVideoContent()


def categoryContent(tid, pg, filter=False, extend=None):
    return _get_spider().categoryContent(tid, pg, filter, extend)


def detailContent(ids):
    return _get_spider().detailContent(ids)


def playerContent(flag, id, vipFlags=None):
    return _get_spider().playerContent(flag, id, vipFlags)


def searchContent(key, quick=False, pg="1"):
    return _get_spider().searchContent(key, quick, pg)


def isVideoFormat(url):
    return _get_spider().isVideoFormat(url)


def manualVideoCheck():
    return _get_spider().manualVideoCheck()


def localProxy(param):
    return _get_spider().localProxy(param)
