#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小马X母狗（722977.xmamgou103.buzz/xmmg）- 全家桶格式版
=================================================
TVBox / TVBoxOSC / FongMi / 影视仓 / PyramidStore 通用 Python 爬虫源
按「全家桶爬虫格式规范」编写（模板基线: 麦田影视 __app_27_ozb7.py）：

  · class Spider 继承 base.spider.Spider（try/except ImportError 兜底），
    实现统一接口清单：init / getName / homeContent / homeVideoContent /
    categoryContent / detailContent / searchContent / searchContentPage /
    playerContent / isVideoFormat / manualVideoCheck / localProxy；
  · 接口返回标准 dict 字段；封面直链（sbzytpimg11.com 图床直出）；
  · 零第三方依赖：标准库 urllib。

站点结构（2026-10-13 实勘）：
  · MacCMS 模板站，基路径 /xmmg，无盾，直连 200
  · 分类：/xmmg/index.php/vod/type/id/{tid}.html
    翻页：/xmmg/index.php/vod/type/id/{tid}/page/{pg}.html
  · 卡片：<a class="thumbnail" href="/xmmg/index.php/vod/detail/id/{vid}.html">
          <img data-original="{cover}"> + <h5><a>{title}</a></h5>
          （src 是 loading.svg 占位图，必须取 data-original）
  · 详情：<title>{标题}剧情介绍--小马X母狗</title>；
          播放按钮 /xmmg/index.php/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html
  · 播放页 player_aaaa JSON "url" 直含 m3u8（lsbbf11.com，标准 HLS，encrypt=0）
  · 搜索：/xmmg/index.php/vod/search.html?wd={kw}&page={pg}
  · 51 分类（已排除 113 萝莉少女）
"""

import os
import re
import sys
import json
import time

import gzip
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
_HOST = "https://722977.xmamgou103.buzz"
_BASE = "/xmmg"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 113 萝莉少女已排除
_CATS = [
    ("30", "高清精品视频1区"), ("49", "精品推荐"), ("62", "乱伦实录"),
    ("77", "国产精品"), ("63", "换脸明星"), ("54", "偷拍自拍"),
    ("55", "网曝流出"), ("57", "国产探花"), ("56", "同性恋"),
    ("51", "欧美精品"), ("50", "直播做爱"), ("61", "麻豆诱惑"),
    ("60", "制服诱惑"), ("58", "人妻熟女"), ("59", "SM调教"),
    ("92", "高清精品视频2区"), ("94", "网曝黑料"), ("95", "国产视频"),
    ("96", "国产主播"), ("97", "国产传媒"), ("98", "女同性恋"),
    ("99", "网红头条"), ("100", "明星换脸"), ("101", "抖阴视频"),
    ("102", "激情动漫"), ("103", "SM调教"), ("104", "韩国主播"),
    ("105", "VR视角"), ("106", "人妖系列"), ("114", "伦理三级"),
    ("107", "中文字幕"), ("108", "日本有码"), ("116", "AV解说"),
    ("109", "日本无码"), ("110", "欧美无码"), ("115", "制服诱惑"),
    ("111", "女优明星"), ("112", "强奸乱伦"), ("113", "萝莉少女"),("29", "高清精品视频3区"),
    ("65", "传媒出品"), ("67", "自拍短视频"), ("66", "探花约炮"),
    ("64", "主播做爱"), ("73", "黑料网爆"), ("76", "AI换脸"),
    ("75", "调教SM"), ("71", "男同性恋"), ("74", "高清做爱"),
    ("70", "女同性恋"), ("68", "欧美精品"), ("69", "动漫"),
]


# ============================================================================
# 2. Spider 主类（全家桶模板）
# ============================================================================
class XiaoMaMuGouSpider(Spider):
    def init(self, extend=""):
        self._proxy = ""
        try:
            self._proxy = self.getProxyUrl() or ""
        except Exception:
            pass

    def getName(self):
        return "小马X母狗"

    # ---- 网络 ----
    def _get(self, url, timeout=15):
        req = urllib.request.Request(url, headers={
            "User-Agent": _UA,
            "Referer": _HOST + _BASE + "/",
            "Accept": "text/html,application/xhtml+xml",
            # 必须显式要 gzip：不带 Accept-Encoding 时缓存层会回乱码流
            "Accept-Encoding": "gzip",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        ctx = ssl._create_unverified_context()
        try:
            r = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            raw = r.read()
            # 本站部分页面（分类页）直接回 gzip 流，需手动解压
            if raw[:2] == b"\x1f\x8b":
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass
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
        # 卡片：<a class="thumbnail" href=".../detail/id/{vid}.html">
        #   <img data-original="{cover}"> ... <h5><a>{title}</a></h5>
        pat = re.compile(
            r'<a class="thumbnail" href="(/xmmg/index\.php/vod/detail/id/(\d+)\.html)"[^>]*>'
            r'\s*<img[^>]*data-original="([^"]+)"[^>]*>'
            r'.*?<h5><a[^>]*>(.*?)</a></h5>',
            re.S)
        for m in pat.finditer(html):
            vid = m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            cover = m.group(3).strip()
            title = _html.unescape(
                re.sub(r"<[^>]+>", "", m.group(4)).strip())
            if not title:
                continue
            videos.append({"vod_id": vid, "vod_name": title,
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
        html = self._get(_HOST + _BASE + "/")
        videos = self._parse_cards(html)[:20]
        return {"list": videos}

    def categoryContent(self, cid, pg, filter, extend):
        pg = int(pg or 1)
        if pg <= 1:
            url = "%s%s/index.php/vod/type/id/%s.html" % (_HOST, _BASE, cid)
        else:
            url = "%s%s/index.php/vod/type/id/%s/page/%d.html" % (
                _HOST, _BASE, cid, pg)
        return self._page(url, pg)

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        html = self._get(
            "%s%s/index.php/vod/detail/id/%s.html" % (_HOST, _BASE, vid))
        if not html:
            return {"list": []}
        title = ""
        m = re.search(r"<title>([^<]+)</title>", html)
        if m:
            title = _html.unescape(m.group(1).strip())
            title = re.sub(r"剧情介绍--.*$", "", title).strip()
        desc = ""
        m2 = re.search(
            r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
        if m2:
            desc = _html.unescape(m2.group(1).strip())
            desc = re.sub(r"_小马X母狗$", "", desc)
        cover = ""
        m4 = re.search(
            r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if m4:
            cover = m4.group(1).strip()
        if not cover:
            m5 = re.search(r'data-original="(https?://[^"]+upload/vod[^"]+)"',
                            html)
            if m5:
                cover = m5.group(1)
        # 播放列表：/xmmg/index.php/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html
        eps = []
        seen = set()
        for me in re.finditer(
                r'href="(/xmmg/index\.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html)"',
                html):
            key = (me.group(3), me.group(4))
            if key in seen:
                continue
            seen.add(key)
            eps.append("第%s集$%s|%s|%s" % (
                me.group(4), vid, me.group(3), me.group(4)))
        if not eps:
            eps = ["正片$%s|1|1" % vid]
        vod = {"vod_id": str(vid), "vod_name": title, "vod_pic": cover,
               "vod_content": desc, "type_name": "",
               "vod_play_from": "小马X母狗",
               "vod_play_url": "#".join(eps)}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        pg = int(pg or 1)
        url = "%s%s/index.php/vod/search.html?wd=%s" % (
            _HOST, _BASE, quote(key))
        if pg > 1:
            url += "&page=%d" % pg
        return self._page(url, pg)

    def playerContent(self, flag, id, vipFlags):
        # id 形如 "352534|1|1" (vid|sid|nid)
        parts = id.split("|")
        vid = parts[0]
        sid = parts[1] if len(parts) > 1 else "1"
        nid = parts[2] if len(parts) > 2 else "1"
        html = self._get(
            "%s%s/index.php/vod/play/id/%s/sid/%s/nid/%s.html" % (
                _HOST, _BASE, vid, sid, nid))
        url = ""
        if html:
            # 优先 player_aaaa JSON "url" 字段（含 \/ 转义），再找裸 m3u8
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
                "header": {"Referer": _HOST + _BASE + "/",
                           "User-Agent": _UA}}

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
                "User-Agent": _UA, "Referer": _HOST + _BASE + "/",
                "Accept": "image/*", "Accept-Encoding": "gzip"})
            ctx = ssl._create_unverified_context()
            r = urllib.request.urlopen(req, timeout=15, context=ctx)
            data = r.read()
            if data[:2] == b"\x1f\x8b":
                try:
                    data = gzip.decompress(data)
                except Exception:
                    pass
            return [200, detect_image_mime(data), data]
        except Exception:
            return [404, "text/plain", b"fetch failed"]


# 模块级转发（双兼容）
_spider = None


def _get():
    global _spider
    if _spider is None:
        _spider = XiaoMaMuGouSpider()
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


Spider = XiaoMaMuGouSpider


# ============================================================================
# __main__ 自检
# ============================================================================
if __name__ == "__main__":
    import traceback

    sp = XiaoMaMuGouSpider()
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

    print("== 小马X母狗(722977.xmamgou103.buzz/xmmg) 自检 ==")
    hc = check("homeContent", lambda: sp.homeContent(None))
    if hc:
        print("  分类数:", len(hc.get("class", [])))
    hv = check("homeVideoContent", sp.homeVideoContent)
    if hv:
        print("  推荐数:", len(hv.get("list", [])))
    cc = check("categoryContent",
               lambda: sp.categoryContent("30", "1", None, {}))
    vid = None
    if cc and cc.get("list"):
        print("  分类条数:", len(cc["list"]))
        print("  首条:", cc["list"][0]["vod_name"][:30])
        vid = cc["list"][0]["vod_id"]
    cc2 = check("categoryContent翻页",
                lambda: sp.categoryContent("30", "2", None, {}))
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
    sc = check("searchContent", lambda: sp.searchContent("美女", False, "1"))
    if sc:
        print("  搜索条数:", len(sc.get("list", [])))
    print("ALL OK" if ok else "HAS FAILURES")
