#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
翘臀mm（xn--mm-k33fj1e.qtmm2.top）- 全家桶格式版
=================================================
TVBox / TVBoxOSC / FongMi / 影视仓 / PyramidStore 通用 Python 爬虫源
按「全家桶爬虫格式规范」编写（模板基线: 麦田影视 __app_27_ozb7.py）：

  · class Spider 继承 base.spider.Spider（try/except ImportError 兜底），
    实现统一接口清单：init / getName / homeContent / homeVideoContent /
    categoryContent / detailContent / searchContent / searchContentPage /
    playerContent / isVideoFormat / manualVideoCheck / localProxy；
  · 接口返回标准 dict 字段；封面直链；
  · 零第三方依赖：标准库 urllib + http.cookiejar。

站点结构（2026-10-14 实勘，与机车美女/屁眼训练师/无毛小猫同 verify_slide 家族，同后者卡片结构）：
  · 入口先过滑块验证页（纯前端滑块，JS 回调即后端接口）：
    GET / 取 token → POST /（token，须带 last_page Cookie +
    X-Requested-With）→ 响应 {"ok":1} 并 Set-Cookie anti_block_verified，
    之后列表直接用该 Cookie 访问，不用跟 sig 落地页。
    关键：只 POST token 会 403 非法请求；必须同会话 + last_page +
    X-Requested-With 三者齐全。验证 Cookie 有效期 86400 秒。
    _get 检出验证页（SlideVerifyPlug / verify-wrap）即自动重验并重试一次。
  · 分类：/?m=video_list*{tid}*{pg}（40 条/页，翻页零重合）
  · 卡片：<a class="thumbnail" href="/?m=video_detail*{vid}*{suf}">
          <img data-original="{cover}" src="{cover}">
          + <h5><a href="/?m=video_detail*{vid}*{suf}">{title}</a></h5>
          （与机车美女不同：本 img 无 alt、无 h3，标题只在 h5 里）
          【后缀 suf 必须透传】卡片链接的 suf（分类页里就是分类 tid，
          搜索页里是 1，首页混合）决定播放：conter 必须用同一 suf，
          用错 suf 返回无 m3u8。因此 vod_id 用 vid|suf 复合，
          detail/conter 一律带原 suf。
  · 详情：/?m=video_detail*{vid}*{suf}，
          标题在 <h3 class="appel-title">（<h1> 是站名 logo，无标题），
          封面 detail-poster 下 img，播放入口 /?m=video_conter*{vid}*{suf}
  · 播放页：iframe src="/Static/Home/VideoJS/index.php?Play={m3u8}&Cover=..."
          Play 参数即 m3u8 直链（lsbbf11.com，标准 HLS）
  · 搜索：/?m=video_search*{kw}，翻页 /?m=video_search*{kw}*{pg}
  · 32 分类：见 _CATS（与机车美女同套分类 ID 与名称）
"""

import gzip
import html as _html
import re
import ssl
import sys
import urllib.request
import urllib.error
from urllib.parse import quote, unquote

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
_HOST = "https://xn--mm-k33fj1e.qtmm2.top"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

_CATS = [
    ("1", "精品推荐"), ("2", "主播秀色"), ("3", "日本有码"), ("4", "日本无码"),
    ("5", "中文字幕"), ("6", "童颜巨乳"), ("7", "性感人妻"), ("8", "强奸乱伦"),
    ("9", "欧美情色"), ("10", "三级伦理"), ("11", "卡通动漫"), ("12", "丝袜OL"),
    ("13", "自拍偷拍"), ("14", "日本片商"), ("15", "剧情介绍"), ("16", "网曝系列"),
    ("17", "同性恋"), ("18", "探花嫖娼"), ("19", "国产人妻"), ("20", "国产SM"),
    ("21", "国产丝袜"), ("22", "麻豆传媒"), ("23", "国产乱伦"), ("24", "明星换脸"),
    ("25", "主奴调教"), ("26", "凌辱快感"), ("27", "多人群交"), ("28", "角色剧情"),
    ("29", "港台辣妹"), ("30", "重口性癖"), ("31", "变性伪娘"), ("32", "VR视角"),
]


# ============================================================================
# 2. Spider 主类（全家桶模板）
# ============================================================================
class QiaoTunMMSpider(Spider):
    def init(self, extend=""):
        self._proxy = ""
        try:
            self._proxy = self.getProxyUrl() or ""
        except Exception:
            pass
        # 手动 Cookie 管理（不用 CookieJar/opener：与之前在设备端跑通的
        # 那些源同一写法，避免 opener 在壳子 Python 里的兼容差异）。
        # 有分类无内容的那版用的就是 opener，沙箱通、设备端空，
        # 现改回 urlopen + 手动 Cookie 头。
        self._cookies = {}
        self._verified = False
        self._verifying = False

    def getName(self):
        return "翘臀mm"

    # ---- 网络 ----
    def _store_cookies(self, headers):
        try:
            for h in (headers.get_all("Set-Cookie") or []):
                m = re.match(r"\s*([^=;]+)=([^;]*)", h)
                if m:
                    self._cookies[m.group(1).strip()] = m.group(2).strip()
        except Exception:
            pass

    def _cookie_header(self, extra=None):
        parts = ["%s=%s" % (k, v) for k, v in self._cookies.items()]
        if extra:
            parts.append(extra)
        return "; ".join(parts)

    def _decode(self, raw, headers):
        try:
            if (headers.get("Content-Encoding") or "") == "gzip":
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass
            return raw.decode("utf-8")
        except Exception:
            try:
                return raw.decode("gbk", "ignore")
            except Exception:
                return ""

    def _raw(self, url, data=None, headers=None, timeout=20):
        h = dict(headers or {})
        h.setdefault("User-Agent", _UA)
        h.setdefault("Accept-Encoding", "identity")
        ck = self._cookie_header()
        if ck and "Cookie" not in h:
            h["Cookie"] = ck
        req = urllib.request.Request(url, data=data, headers=h,
                                     method="POST" if data is not None else "GET")
        ctx = ssl._create_unverified_context()
        try:
            r = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            self._store_cookies(r.headers)
            return self._decode(r.read(), r.headers)
        except urllib.error.HTTPError as e:
            try:
                self._store_cookies(e.headers)
                return self._decode(e.read(), e.headers)
            except Exception:
                return ""
        except Exception:
            return ""

    def _has_verified_cookie(self):
        return bool(self._cookies.get("anti_block_verified"))

    def _verify_once(self, entry_url):
        """单次验证：GET entry 取 token → POST 同 entry 验证。
        返回 True 表示拿到 anti_block_verified。"""
        html = self._raw(entry_url, headers={
            "User-Agent": _UA, "Referer": _HOST + "/"})
        m_tok = re.search(
            r'encodeURIComponent\("([a-f0-9]{32})"\)', html)
        if not m_tok:
            return False
        token = m_tok.group(1)
        last_page = quote(entry_url, safe="")
        ck = self._cookie_header("last_page=" + last_page)
        data = ("token=" + quote(token, safe="")).encode()
        resp = self._raw(entry_url, data=data, headers={
            "User-Agent": _UA,
            "Referer": entry_url,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": _HOST,
            "Cookie": ck,
            "X-Requested-With": "XMLHttpRequest"})
        return '"ok":1' in resp.replace(" ", "") \
            and self._has_verified_cookie()

    def _verify(self):
        """滑块验证：取 token → POST 验证 → 拿验证 Cookie。
        成功返回 True。token 一次性，失败即换新 token 重来。
        注意：POST 必须带 last_page Cookie + X-Requested-With，
        只带 token 会 403 非法请求。验证通过后列表可直接用 Cookie 访问，
        不需要再跟那个 sig 落地页。
        双入口：先走 GET /（沙箱通），失败再走带 sig 的验证 URL
        （首版在沙箱走通的入口；不同网络下服务器可能只认其中一个入口）。"""
        if self._verifying:
            return False
        self._verifying = True
        try:
            entries = [
                _HOST + "/",
                _HOST + "/?verify_slide=1&sig=19434ebdba1facfd48490a4c2658562c",
            ]
            for entry in entries:
                for _ in range(2):
                    try:
                        if self._verify_once(entry):
                            self._verified = True
                            return True
                    except Exception:
                        pass
                    self._cookies.pop("anti_block_verified", None)
            return False
        except Exception:
            return False
        finally:
            self._verifying = False

    def _get(self, url, timeout=20):
        # 先直取再验证：部分网络下无需验证即可访问，直取成功就不用走
        # 验证 POST（设备端验证失败反而可能把会话搞坏，导致全空）。
        # 直取拿到验证页时，再走 _verify() 验证后重试一次。
        # 空响应（瞬时网络失败）重试一次，避免一次抖动就返回空列表。
        def _fetch():
            html = ""
            for _ in range(2):
                html = self._raw(url, headers={
                    "User-Agent": _UA, "Referer": _HOST + "/",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "zh-CN,zh;q=0.9"}, timeout=timeout)
                if html:
                    break
            return html
        html = _fetch()
        if "SlideVerifyPlug" in html or 'id="verify-wrap"' in html:
            if self._verify():
                html = _fetch()
        return html

    # ---- 解析 ----
    def _parse_cards(self, html):
        # 卡片：<a class="thumbnail" href="/?m=video_detail*{vid}*{suf}">
        #   <img data-original="{cover}" src="{cover}">
        #   + <h5><a href="/?m=video_detail*{vid}*{suf}">{title}</a></h5>
        # 标题只在 h5 里（img 无 alt、无 h3），先建 (vid,suf)->封面表再合标题。
        # suf 必须随 vod_id 透传（见文件头说明）。
        covers = {}
        for m in re.finditer(
                r'<a class="thumbnail" href="/\?m=video_detail\*(\d+)\*(\d+)"[^>]*>'
                r'\s*<img[^>]*?(?:data-original="([^"]+)"|src="([^"]+)")',
                html, re.S):
            key = (m.group(1), m.group(2))
            if key not in covers:
                covers[key] = (m.group(3) or m.group(4) or "").strip()
        videos = []
        seen = set()
        for m in re.finditer(
                r'<h5><a href="/\?m=video_detail\*(\d+)\*(\d+)"[^>]*>(.*?)</a></h5>',
                html, re.S):
            vid, suf = m.group(1), m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            title = _html.unescape(
                re.sub(r"<[^>]+>", "", m.group(3)).strip())
            if not title:
                continue
            videos.append({"vod_id": "%s|%s" % (vid, suf),
                           "vod_name": title,
                           "vod_pic": covers.get((vid, suf), ""),
                           "vod_remarks": ""})
        return videos

    def _page(self, url, pg=1):
        html = self._get(url)
        videos = self._parse_cards(html)
        return {"list": videos, "page": pg,
                "pagecount": 9999, "limit": len(videos) or 40,
                "total": 999999}

    # ---- 标准接口 ----
    def homeContent(self, filter):
        cats = [{"type_id": tid, "type_name": name}
                for tid, name in _CATS]
        filters = {tid: build_default_filters() for tid, _ in _CATS}
        return {"class": cats, "filters": filters}

    def homeVideoContent(self):
        html = self._get(_HOST + "/")
        videos = self._parse_cards(html)[:20]
        return {"list": videos}

    def categoryContent(self, cid, pg, filter, extend):
        pg = int(pg or 1)
        url = "%s/?m=video_list*%s*%d" % (_HOST, cid, pg)
        return self._page(url, pg)

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, list) else ids
        parts = str(raw).split("|")
        vid = parts[0]
        suf = parts[1] if len(parts) > 1 and parts[1] else "1"
        html = self._get("%s/?m=video_detail*%s*%s" % (_HOST, vid, suf))
        if not html:
            return {"list": []}
        # 标题：<h3 class="appel-title">（<h1> 是站名 logo，无标题）
        # 兜底：<title>翘臀mm-{分类}-{标题}</title> 去前两段；再兜底 片名：
        title = ""
        m = re.search(r'<h3 class="appel-title">(.*?)</h3>', html, re.S)
        if m:
            title = _html.unescape(
                re.sub(r"<[^>]+>", "", m.group(1)).strip())
        if not title:
            m = re.search(r"<title>([^<]+)</title>", html)
            if m:
                t = _html.unescape(m.group(1).strip())
                title = t.split("-", 2)[-1].strip() if t.count("-") >= 2 else t
        if not title:
            m = re.search(r"片名[：:]\s*([^<]+)</li>", html)
            if m:
                title = _html.unescape(m.group(1).strip())
        cover = ""
        m2 = re.search(
            r'<div class="detail-poster">.*?<img[^>]*src="([^"]+)"',
            html, re.S)
        if m2:
            cover = m2.group(1).strip()
        if not cover:
            m3 = re.search(
                r'href="/\?m=video_conter\*%s\*\d+"[^>]*>\s*<img[^>]*src="([^"]+)"'
                % re.escape(vid), html, re.S)
            if m3:
                cover = m3.group(1).strip()
        eps = []
        if re.search(r'video_conter\*%s\*\d+' % re.escape(vid), html):
            eps.append("播放$%s|%s" % (vid, suf))
        vod = {"vod_id": str(vid), "vod_name": title, "vod_pic": cover,
               "vod_play_from": "翘臀mm",
               "vod_play_url": "#".join(eps)}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        pg = int(pg or 1)
        if pg <= 1:
            url = "%s/?m=video_search*%s" % (_HOST, quote(key))
        else:
            url = "%s/?m=video_search*%s*%d" % (_HOST, quote(key), pg)
        return self._page(url, pg)

    def playerContent(self, flag, id, vipFlags):
        # id 形如 "vid|suf"，suf 必须与卡片链接一致，用错则无 m3u8
        parts = str(id).split("|")
        vid = parts[0]
        suf = parts[1] if len(parts) > 1 and parts[1] else "1"
        html = self._get("%s/?m=video_conter*%s*%s" % (_HOST, vid, suf))
        url = ""
        if html:
            m = re.search(r'[?&]Play=([^&"\']+)', html)
            if m:
                url = unquote(m.group(1))
            if not url:
                m2 = re.search(
                    r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
                if m2:
                    url = m2.group(1).split("&Cover=")[0]
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
        _spider = QiaoTunMMSpider()
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


Spider = QiaoTunMMSpider


# ============================================================================
# __main__ 自检（只打印条数与 id，不打印标题）
# ============================================================================
if __name__ == "__main__":
    import traceback

    sp = QiaoTunMMSpider()
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

    print("== 翘臀mm(xn--mm-k33fj1e.qtmm2.top) 自检 ==")
    hc = check("homeContent", lambda: sp.homeContent(None))
    if hc:
        print("  分类数:", len(hc.get("class", [])))
    hv = check("homeVideoContent", sp.homeVideoContent)
    if hv:
        print("  推荐数:", len(hv.get("list", [])))
    cc = check("categoryContent",
               lambda: sp.categoryContent("2", "1", None, {}))
    vid = None
    if cc and cc.get("list"):
        print("  分类条数:", len(cc["list"]))
        vid = cc["list"][0]["vod_id"]
        print("  首条 id:", vid)
    cc2 = check("categoryContent翻页",
                lambda: sp.categoryContent("2", "2", None, {}))
    if cc and cc2 and cc["list"] and cc2["list"]:
        ids1 = {v["vod_id"] for v in cc["list"]}
        ids2 = {v["vod_id"] for v in cc2["list"]}
        print("  翻页重合:", len(ids1 & ids2), "(应为0)")
    if vid:
        dc = check("detailContent", lambda: sp.detailContent([vid]))
        if dc and dc.get("list"):
            v = dc["list"][0]
            print("  详情 id:", v["vod_id"], "有播放线路:",
                  bool(v.get("vod_play_url")))
            pu = v.get("vod_play_url", "")
            first = pu.split("#")[0] if pu else ""
            pid = first.split("$")[-1] if "$" in first else ""
            if pid:
                pc = check("playerContent",
                           lambda: sp.playerContent("", pid, []))
                if pc:
                    u = pc.get("url", "")
                    print("  播放URL含 m3u8:", ".m3u8" in u,
                          "域名:", u.split("/")[2] if "://" in u else "")
    sc = check("searchContent", lambda: sp.searchContent("主播", False, "1"))
    if sc:
        print("  搜索条数:", len(sc.get("list", [])))
    print("ALL OK" if ok else "HAS FAILURES")
