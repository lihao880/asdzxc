#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
红颜AI短剧 (ai365.hyaidj.lol) - 全家桶格式版
=================================================
TVBox / TVBoxOSC / FongMi / 影视仓 / PyramidStore 通用 Python 爬虫源
按「全家桶爬虫格式规范」编写（模板基线: 麦田影视 __app_27_ozb7.py）：

  · class Spider 继承 base.spider.Spider（try/except ImportError 兜底），
    实现统一接口清单：init / getName / homeContent / homeVideoContent /
    categoryContent / detailContent / searchContent / searchContentPage /
    playerContent / isVideoFormat / manualVideoCheck / localProxy；
  · 接口返回标准 dict 字段；
  · 零第三方依赖：标准库 urllib。

站点结构（2026-10-13 实勘）：
  · MacCMS 站，无盾
  · 分类：/index.php/vod/type/id/{tid}.html
    翻页：/index.php/vod/type/id/{tid}/page/{pg}.html
  · 卡片直链播放页：<div class="item"><a href="/index.php/vod/play/id/{vid}/sid/1/nid/1.html">
    <div class="img"><img src="{封面}" alt="{标题}">
  · 播放页 JSON "url" 字段含 m3u8（含 \\/ 转义，2609.sysl2026.com 标准 HLS）
  · 搜索：/index.php/vod/search.html?wd={quote(kw)}
  · 92 分类（20-111）
"""

import os
import re
import sys
import json
import time

import ssl
import urllib.request
import urllib.error
from urllib.parse import quote, unquote
import html as _html

try:
    sys.path.append("../../")
except Exception:
    pass
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def init(self, extend=""):
            pass


# ============================================================================
# 0. 图片魔数判定 / 默认筛选器（全家桶模板级组件）
# ============================================================================
def detect_image_mime(data) -> str:
    if not data:
        return "application/octet-stream"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] in (b"GIF8",):
        return "image/gif"
    return "application/octet-stream"


def build_default_filters() -> list:
    return [
        {"key": "sort", "name": "排序",
         "value": [{"n": "最新", "v": "latest"}, {"n": "最热", "v": "hot"}]},
    ]


# ============================================================================
# 1. 站点常量
# ============================================================================
_HOST = "https://ai365.hyaidj.lol"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

_CATS = [
    ("20", "AI短剧"), ("35", "精品推荐"), ("36", "主播秀色"),
    ("37", "中文字幕"), ("38", "童颜巨乳"), ("39", "性感人妻"),
    ("40", "强奸乱伦"), ("41", "欧美情色"), ("42", "三级伦理"),
    ("43", "卡通动漫"), ("44", "丝袜OL"), ("45", "自拍偷拍"),
    ("46", "日本片商"), ("47", "剧情介绍"), ("48", "网曝系列"),
    ("49", "麻豆传媒"), ("50", "明星换脸"), ("51", "国产乱伦"),
    ("52", "国产丝袜"), ("53", "国产SM"), ("54", "国产人妻"),
    ("55", "探花嫖娼"), ("56", "同性恋"), ("57", "国产区"),
    ("58", "AV区"), ("59", "欧美区"), ("60", "动漫区"),
    ("62", "网曝门"), ("63", "OnlyFans"),
]


# ============================================================================
# 2. Spider 主类（全家桶模板）
# ============================================================================
class HongYanAIDuanJuSpider(Spider):
    def init(self, extend=""):
        self._proxy = ""
        try:
            self._proxy = self.getProxyUrl() or ""
        except Exception:
            pass

    def getName(self):
        return "红颜AI短剧"

    # ---- 网络 ----
    def _get(self, url, headers=None, timeout=15):
        hds = {
            "User-Agent": _UA,
            "Referer": _HOST + "/",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if headers:
            hds.update(headers)
        req = urllib.request.Request(url, headers=hds)
        ctx = ssl._create_unverified_context()
        try:
            r = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            raw = r.read()
            try:
                return raw.decode("utf-8")
            except Exception:
                return raw.decode("gbk", "ignore")
        except Exception:
            return ""

    # ---- 解析 ----
    def _parse_cards(self, html):
        videos = []
        seen = set()
        # 卡片直链播放页：
        # <a class="popup-video-link" href="/index.php/vod/play/id/{vid}/sid/1/nid/1.html">
        #   <img src="{封面}"><strong class="title">{标题}</strong>
        pat = re.compile(
            r'<a[^>]*href="/index\.php/vod/play/id/(\d+)/sid/\d+/nid/\d+\.html"[^>]*>'
            r'.*?<img[^>]*src="([^"]+)"[^>]*>.*?<strong[^>]*class="title"[^>]*>([^<]*)</strong>',
            re.S)
        for m in pat.finditer(html):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            cover = m.group(2).strip()
            title = _html.unescape(m.group(3).strip())
            if not title or not vid:
                continue
            if "lazy.svg" in cover or "placeholder" in cover.lower() or len(cover) < 10:
                continue
            # 复合ID透传标题（播放页无标题）
            cid = "%s|%s" % (vid, quote(title))
            videos.append({"vod_id": cid, "vod_name": title,
                           "vod_pic": cover, "vod_remarks": ""})
        return videos

    def _page(self, url, pg=1):
        html = self._get(url)
        videos = self._parse_cards(html)
        total_pg = pg
        for mp in re.findall(r"/page/(\d+)\.html", html):
            try:
                total_pg = max(total_pg, int(mp))
            except Exception:
                pass
        return {"list": videos, "page": pg,
                "pagecount": total_pg, "limit": len(videos) or 30,
                "total": 999999}

    # ---- 标准接口 ----
    def homeContent(self, filter):
        cats = [{"type_id": tid, "type_name": name}
                for tid, name in _CATS]
        filters = {tid: build_default_filters() for tid, _ in _CATS}
        return {"class": cats, "filters": filters}

    def homeVideoContent(self):
        html = self._get(_HOST + "/")
        videos = self._parse_cards(html)[:18]
        return {"list": videos}

    def categoryContent(self, cid, pg, filter, extend):
        pg = int(pg or 1)
        if pg <= 1:
            url = "%s/index.php/vod/type/id/%s.html" % (_HOST, cid)
        else:
            url = "%s/index.php/vod/type/id/%s/page/%d.html" % (_HOST, cid, pg)
        return self._page(url, pg)

    def detailContent(self, ids):
        cid = ids[0] if isinstance(ids, list) else ids
        # 复合ID：vid|quote(title)
        if "|" in cid:
            vid, title = cid.split("|", 1)
            try:
                title = unquote(title)
            except Exception:
                pass
        else:
            vid, title = cid, ""
        # 卡片直链播放页，用播放页做详情
        html = self._get(
            "%s/index.php/vod/play/id/%s/sid/1/nid/1.html" % (_HOST, vid))
        if not title and html:
            m = re.search(r'<img[^>]*alt="([^"]{5,60})"', html)
            if m:
                title = _html.unescape(m.group(1).strip())
        cover = ""
        if html:
            m4 = re.search(
                r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
            if m4:
                cover = m4.group(1).strip()
        vod = {"vod_id": str(vid), "vod_name": title, "vod_pic": cover,
               "vod_play_from": "红颜AI短剧",
               "vod_play_url": "立即播放$%s|1|1" % vid}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        pg = int(pg or 1)
        url = "%s/index.php/vod/search.html?wd=%s" % (_HOST, quote(key))
        if pg > 1:
            # 搜索翻页格式待验证
            url += "&page=%d" % pg
        return self._page(url, pg)

    def playerContent(self, flag, id, vipFlags):
        # id 形如 "vid|quote(title)"（复合ID透传标题）
        parts = str(id).split("|")
        vid = parts[0].split("$")[-1]
        sid = "1"
        nid = "1"
        html = self._get(
            "%s/index.php/vod/play/id/%s/sid/%s/nid/%s.html" % (
                _HOST, vid, sid, nid))
        url = ""
        if html:
            # 优先 JSON "url" 字段（含 \/ 转义）
            m = re.search(
                r'"url"\s*:\s*"((?:https?:)?\\?/\\?/[^"]+?\.m3u8[^"]*)"', html)
            if m:
                url = m.group(1).replace("\\/", "/")
            if not url:
                m2 = re.search(
                    r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
                if m2:
                    url = m2.group(1)
        return {"parse": 0, "url": url,
                "header": {"Referer": _HOST + "/", "User-Agent": _UA}}

    def isVideoFormat(self, url):
        url = (url or "").lower()
        return any(url.endswith(x) for x in
                   (".m3u8", ".mp4", ".flv", ".ts", ".mkv"))

    def manualVideoCheck(self):
        return {"parse": 0}

    def localProxy(self, params):
        try:
            action = params.get("action") or params.get("do") or ""
        except Exception:
            action = ""
        if action != "img":
            return [404, "text/plain", b"unsupported"]
        url = params.get("url") or ""
        try:
            if not url.startswith("http"):
                url = unquote(url)
        except Exception:
            pass
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": _UA, "Referer": _HOST + "/",
                "Accept": "image/*"})
            ctx = ssl._create_unverified_context()
            r = urllib.request.urlopen(req, timeout=15, context=ctx)
            data = r.read()
            return [200, detect_image_mime(data), data]
        except Exception:
            return [404, "text/plain", b"fetch failed"]


# 模块级转发（双兼容）
_spider = None


def _get():
    global _spider
    if _spider is None:
        _spider = HongYanAIDuanJuSpider()
        _spider.init("")
    return _spider


def init(extend=""):
    return _get().init(extend)


def getName():
    return _get().getName()


def homeContent(filter):
    return _get().homeContent(filter)


def homeVideoContent():
    return _get().homeVideoContent()


def categoryContent(cid, pg, filter, extend):
    return _get().categoryContent(cid, pg, filter, extend)


def detailContent(ids):
    return _get().detailContent(ids)


def searchContent(key, quick, pg="1"):
    return _get().searchContent(key, quick, pg)


def searchContentPage(key, quick, pg="1"):
    return _get().searchContentPage(key, quick, pg)


def playerContent(flag, id, vipFlags):
    return _get().playerContent(flag, id, vipFlags)


def isVideoFormat(url):
    return _get().isVideoFormat(url)


def manualVideoCheck():
    return _get().manualVideoCheck()


def localProxy(params):
    return _get().localProxy(params)


Spider = HongYanAIDuanJuSpider


# ============================================================================
# __main__ 自检
# ============================================================================
if __name__ == "__main__":
    import traceback

    sp = HongYanAIDuanJuSpider()
    sp.init("")
    ok = True

    def check(name, fn):
        global ok
        try:
            r = fn()
            print("[OK] %s" % name)
            return r
        except Exception as e:
            ok = False
            print("[FAIL] %s: %s" % (name, str(e)[:100]))
            traceback.print_exc(limit=2)
            return None

    print("== 红颜AI短剧 自检 ==")
    hc = check("homeContent", lambda: sp.homeContent(None))
    if hc:
        print("  分类数:", len(hc.get("class", [])))
    hv = check("homeVideoContent", sp.homeVideoContent)
    if hv:
        print("  推荐数:", len(hv.get("list", [])))
    cc = check("categoryContent",
               lambda: sp.categoryContent("20", "1", None, {}))
    vid = None
    if cc and cc.get("list"):
        print("  分类条数:", len(cc["list"]))
        print("  首条:", cc["list"][0]["vod_name"][:30])
        vid = cc["list"][0]["vod_id"]
    cc2 = check("categoryContent翻页",
                lambda: sp.categoryContent("20", "2", None, {}))
    if cc and cc2 and cc["list"] and cc2["list"]:
        ids1 = {v["vod_id"] for v in cc["list"]}
        ids2 = {v["vod_id"] for v in cc2["list"]}
        print("  翻页重合:", len(ids1 & ids2), "(应为0)")
    if vid:
        dc = check("detailContent", lambda: sp.detailContent([vid]))
        if dc and dc.get("list"):
            v = dc["list"][0]
            print("  详情:", v["vod_name"][:30])
            pu = v.get("vod_play_url", "")
            pid = pu.split("$")[-1] if "$" in pu else ""
            if pid:
                pc = check("playerContent",
                           lambda: sp.playerContent("", pid, []))
                if pc:
                    print("  播放URL:", pc.get("url", "")[:70])
    sc = check("searchContent", lambda: sp.searchContent("美女", False, "1"))
    if sc:
        print("  搜索条数:", len(sc.get("list", [])))
    print("ALL OK" if ok else "HAS FAILURES")
