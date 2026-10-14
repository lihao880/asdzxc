#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
美妞吧（fgwcw8n4.meiniuba2.cyou）- 全家桶格式版
=================================================
TVBox / TVBoxOSC / FongMi / 影视仓 / PyramidStore 通用 Python 爬虫源
按「全家桶爬虫格式规范」编写（模板基线: 麦田影视 __app_27_ozb7.py）：

  · class Spider 继承 base.spider.Spider（try/except ImportError 兜底），
    实现统一接口清单：init / getName / homeContent / homeVideoContent /
    categoryContent / detailContent / searchContent / searchContentPage /
    playerContent / isVideoFormat / manualVideoCheck / localProxy；
  · 接口返回标准 dict 字段；封面直链（98jpg1.vip 等图床直出 200）；
  · 零第三方依赖：标准库 urllib。

站点结构（2026-10-11 实勘）：
  · MacCMS 模板站，无盾，直连 200
  · 分类：/index.php/vod/type/id/{tid}.html
    翻页：/index.php/vod/type/id/{tid}/page/{pg}.html
  · 卡片：<a class="thumb" href="/index.php/vod/detail/id/{id}.html">
          <img src="{cover}" alt="{title}" loading="lazy">
  · 详情：<h1>标题</h1>；播放按钮
          <a class="primary-play" href="/index.php/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html">
  · 播放页 HTML 直含 m3u8（https://c10.hs100.top/.../index.m3u8，标准 HLS）
  · 搜索：/index.php/vod/search/wd/{quote(kw)}.html
  · 8 分类：6 国产丝袜 / 7 国产自拍 / 8 探花系列 / 9 麻豆传媒 /
    10 网曝系列 / 11 自拍偷拍 / 12 内娱视频 / 20 OnlyFans
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
_HOST = "https://fgwcw8n4.meiniuba2.cyou"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

_CATS = [
    ("1", "视频一区"), ("6", "国产精品"), ("7", "绿帽淫妻"),
    ("8", "国产探花"), ("9", "国产乱伦"), ("10", "中文字幕"),
    ("11", "日本有码"), ("12", "高清无码"), ("13", "精品动漫"),
    ("2", "视频二区"), ("14", "欧美专区"), ("15", "网曝门事件"),
    ("16", "日本无码"), ("20", "国产主播"), ("21", "抖阴视频"),
    ("22", "萝莉少女"),
]


# ============================================================================
# 2. Spider 主类（全家桶模板）
# ============================================================================
class MeiNiuBaSpider(Spider):
    def init(self, extend=""):
        self._proxy = ""
        try:
            self._proxy = self.getProxyUrl() or ""
        except Exception:
            pass

    def getName(self):
        return "美妞吧"

    # ---- 网络 ----
    def _get(self, url, timeout=15):
        req = urllib.request.Request(url, headers={
            "User-Agent": _UA,
            "Referer": _HOST + "/",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
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
        # <a class="thumbnail vod-detail-card" href="/index.php/vod/detail/id/123.html" title="...">
        #   <img src="..." alt="标题">
        pat = re.compile(
            r'<a[^>]*href="(/index\.php/vod/(?:detail|play)/id/(\d+)[^"]*\.html)"[^>]*>'
            r'\s*<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"',
            re.S)
        for m in pat.finditer(html):
            vid = m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            cover = m.group(3).strip()
            title = _html.unescape(m.group(4).strip())
            if not title:
                continue
            videos.append({"vod_id": vid, "vod_name": title,
                           "vod_pic": cover, "vod_remarks": ""})
        return videos

    def _page(self, url, pg=1):
        html = self._get(url)
        videos = self._parse_cards(html)
        # 总页数：找 page/948.html 这类最大页码
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
            url = "%s/index.php/vod/type/id/%s/page/%d.html" % (
                _HOST, cid, pg)
        return self._page(url, pg)

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        html = self._get(
            "%s/index.php/vod/detail/id/%s.html" % (_HOST, vid))
        if not html:
            return {"list": []}
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
        if not m:
            m = re.search(r"<title>([^<]+)</title>", html)
        title = _html.unescape(m.group(1).strip()) if m else ""
        # 简介：detail-info-type 下或 meta description
        desc = ""
        m2 = re.search(
            r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
        if m2:
            desc = _html.unescape(m2.group(1).strip())
        # 分类
        cname = ""
        m3 = re.search(r"分类[：:]\s*([^　\s<]+)", html)
        if m3:
            cname = m3.group(1).strip()
        # 封面：详情页 og:image 或第一张 vod 图
        cover = ""
        m4 = re.search(
            r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if m4:
            cover = m4.group(1).strip()
        # 播放列表：/index.php/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html
        eps = []
        seen = set()
        for me in re.finditer(
                r'href="(/index\.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html)"[^>]*>(.*?)</a>',
                html, re.S):
            nid = me.group(4)
            if nid in seen:
                continue
            seen.add(nid)
            # 去掉内嵌标签（如 <span>▶</span>）
            epname = re.sub(r"<[^>]+>", "", me.group(5))
            epname = _html.unescape(epname.strip()) or ("第%s集" % nid)
            eps.append("%s$%s|%s|%s" % (epname, vid, me.group(3), nid))
        # 线路名
        from_name = "美妞吧"
        vod = {"vod_id": str(vid), "vod_name": title, "vod_pic": cover,
               "vod_content": desc, "type_name": cname,
               "vod_play_from": from_name,
               "vod_play_url": "#".join(eps)}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        pg = int(pg or 1)
        # /index.php/vod/search/wd/{kw}.html
        url = "%s/index.php/vod/search/wd/%s.html" % (_HOST, quote(key))
        if pg > 1:
            # 搜索翻页：/index.php/vod/search/wd/{kw}/page/{pg}.html
            url = "%s/index.php/vod/search/wd/%s/page/%d.html" % (
                _HOST, quote(key), pg)
        return self._page(url, pg)

    def playerContent(self, flag, id, vipFlags):
        # id 形如 "37768|1|1" (vid|sid|nid)
        parts = id.split("|")
        vid = parts[0]
        sid = parts[1] if len(parts) > 1 else "1"
        nid = parts[2] if len(parts) > 2 else "1"
        html = self._get(
            "%s/index.php/vod/play/id/%s/sid/%s/nid/%s.html" % (
                _HOST, vid, sid, nid))
        url = ""
        if html:
            # 优先 JSON "url" 字段（含 \/ 转义），再找裸 m3u8
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
        _spider = MeiNiuBaSpider()
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


Spider = MeiNiuBaSpider


# ============================================================================
# __main__ 自检
# ============================================================================
if __name__ == "__main__":
    import traceback

    sp = MeiNiuBaSpider()
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

    print("== 美妞吧(fgwcw8n4.meiniuba2.cyou) 自检 ==")
    hc = check("homeContent", lambda: sp.homeContent(None))
    if hc:
        print("  分类数:", len(hc.get("class", [])))
    hv = check("homeVideoContent", sp.homeVideoContent)
    if hv:
        print("  推荐数:", len(hv.get("list", [])))
    cc = check("categoryContent",
               lambda: sp.categoryContent("1", "1", None, {}))
    vid = None
    if cc and cc.get("list"):
        print("  分类条数:", len(cc["list"]))
        print("  首条:", cc["list"][0]["vod_name"][:30])
        vid = cc["list"][0]["vod_id"]
    cc2 = check("categoryContent翻页",
                lambda: sp.categoryContent("1", "2", None, {}))
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
            first = pu.split("#")[0] if pu else ""
            pid = first.split("$")[-1] if "$" in first else ""
            if pid:
                pc = check("playerContent",
                           lambda: sp.playerContent("", pid, []))
                if pc:
                    print("  播放URL:", pc.get("url", "")[:70])
    sc = check("searchContent", lambda: sp.searchContent("糖心", False, "1"))
    if sc:
        print("  搜索条数:", len(sc.get("list", [])))
    print("ALL OK" if ok else "HAS FAILURES")
