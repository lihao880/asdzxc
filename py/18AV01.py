# -*- coding: utf-8 -*-
"""18AV 在線影片（18av01.cc 系列）— TVBox / 影視倉 type=3 Python 爬蟲。

只依賴 Python 標準庫，Chaquopy 環境可直接載入。

配置範例（訂閱 JSON）：

{
  "key": "18av01",
  "name": "18AV",
  "type": 3,
  "api": "./py/18av01.py",
  "searchable": 1,
  "quickSearch": 1,
  "filterable": 0,
  "ext": { "site": "https://18av01.cc" }
}

ext.site 可留空，預設 https://18av01.cc；主域失效時改成鏡像域即可，不用動代碼。

播放鏈路（實測）：
  列表頁 → 詳情頁 → 頁內 mvarr 混淆串
  → 自訂進位切分 → 逐字 XOR → Base64 → AES-128-CBC → 播放令牌
  → play.php?numresolution=N&id=令牌 → videoSources 內的 m3u8
  → m3u8 必須帶 Referer，否則伺服器回 143 bytes 的假清單（tip.ts）。

頁面上的 hcdeedg252 / hadeedg252 / argdeqweqweqwe / hdddedg252 每個詳情頁
都可能不同，且旁邊塞了一堆名稱相近的誘餌變數（hdddedd252、argdeqweqweqww…），
因此每次都由當前頁面即時讀取，並帶候選窮舉兜底。
"""

import base64
import gzip
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from io import BytesIO

try:
    from base.spider import Spider as BaseSpider
except Exception:  # 本地除錯時沒有 Chaquopy 橋接層
    class BaseSpider(object):
        def __init__(self):
            pass

        def getCache(self, key):
            return None

        def setCache(self, key, value):
            pass

        def delCache(self, key):
            pass


DEFAULT_SITE = "https://18av01.cc"
LANG_SEG = "zh"
TIMEOUT = 20
RETRY = 2
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# (slug, 顯示名稱)  —— slug 同時是列表頁與搜尋頁的路徑段
CATEGORIES = (
    ("chinese", "中文字幕AV"),
    ("censored", "有碼AV"),
    ("uncensored", "無碼AV"),
    ("reducing-mosaic", "無碼破解"),
    ("amateurjav", "素人AV"),
    ("animation", "H動畫"),
    ("CensoredAnimation", "H有碼動畫"),
    ("UncensoredAnimation", "H無碼動畫"),
    ("tdAnimation", "H_3D動畫"),
    ("dt", "國產自拍"),
)

# 搜尋路徑用的類型段（站方搜尋框的下拉選項）
SEARCH_TYPES = (
    ("fc", "全部影片"),
    ("chineseonly", "中文字幕"),
    ("censoredonly", "有碼AV"),
    ("uncensoredonly", "無碼AV"),
    ("amateurjavonly", "素人AV"),
    ("animationonly", "H動畫"),
    ("dt", "國產自拍"),
)

PAGE_SIZE = 24


# --------------------------------------------------------------------------
# 純 Python AES-128 / 192 / 256（CBC 解密，無第三方依賴）
# --------------------------------------------------------------------------

SBOX = bytes.fromhex(
    "637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0"
    "b7fd9326363ff7cc34a5e5f171d8311504c723c31896059a071280e2eb27b275"
    "09832c1a1b6e5aa0523bd6b329e32f8453d100ed20fcb15b6acbbe394a4c58cf"
    "d0efaafb434d338545f9027f503c9fa851a3408f929d38f5bcb6da2110fff3d2"
    "cd0c13ec5f974417c4a77e3d645d197360814fdc222a908846eeb814de5e0bdb"
    "e0323a0a4906245cc2d3ac629195e479e7c8376d8dd54ea96c56f4ea657aae08"
    "ba78252e1ca6b4c6e8dd741f4bbd8b8a703eb5664803f60e613557b986c11d9e"
    "e1f8981169d98e949b1e87e9ce5528df8ca1890dbfe6426841992d0fb054bb16")

INV_SBOX = bytearray(256)
for _i, _v in enumerate(SBOX):
    INV_SBOX[_v] = _i

RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80,
        0x1B, 0x36, 0x6C, 0xD8, 0xAB, 0x4D)


def _xtime(a):
    return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else (a << 1) & 0xFF


def _gmul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a = _xtime(a)
        b >>= 1
    return r & 0xFF


def _expand_key(key):
    nk = len(key) // 4
    nr = nk + 6
    w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        t = list(w[i - 1])
        if i % nk == 0:
            t = t[1:] + t[:1]
            t = [SBOX[b] for b in t]
            t[0] ^= RCON[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            t = [SBOX[b] for b in t]
        w.append([w[i - nk][j] ^ t[j] for j in range(4)])
    return w, nr


def _add_round_key(state, w, rnd):
    for c in range(4):
        for r in range(4):
            state[r][c] ^= w[rnd * 4 + c][r]


def _decrypt_block(block, key):
    w, nr = _expand_key(key)
    s = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
    _add_round_key(s, w, nr)
    for rnd in range(nr - 1, 0, -1):
        for r in range(1, 4):
            s[r] = s[r][-r:] + s[r][:-r]
        for r in range(4):
            for c in range(4):
                s[r][c] = INV_SBOX[s[r][c]]
        _add_round_key(s, w, rnd)
        for c in range(4):
            a = [s[r][c] for r in range(4)]
            s[0][c] = _gmul(a[0], 14) ^ _gmul(a[1], 11) ^ _gmul(a[2], 13) ^ _gmul(a[3], 9)
            s[1][c] = _gmul(a[0], 9) ^ _gmul(a[1], 14) ^ _gmul(a[2], 11) ^ _gmul(a[3], 13)
            s[2][c] = _gmul(a[0], 13) ^ _gmul(a[1], 9) ^ _gmul(a[2], 14) ^ _gmul(a[3], 11)
            s[3][c] = _gmul(a[0], 11) ^ _gmul(a[1], 13) ^ _gmul(a[2], 9) ^ _gmul(a[3], 14)
    for r in range(1, 4):
        s[r] = s[r][-r:] + s[r][:-r]
    for r in range(4):
        for c in range(4):
            s[r][c] = INV_SBOX[s[r][c]]
    _add_round_key(s, w, 0)
    return bytes(s[r][c] for c in range(4) for r in range(4))


def aes_cbc_decrypt(data, key, iv, unpad=True):
    if not data or len(data) % 16:
        return b""
    out = bytearray()
    prev = iv[:16]
    for i in range(0, len(data), 16):
        blk = data[i:i + 16]
        out += bytes(a ^ b for a, b in zip(_decrypt_block(blk, key), prev))
        prev = blk
    if unpad and out:
        n = out[-1]
        if 1 <= n <= 16 and bytes(out[-n:]) == bytes([n]) * n:
            del out[-n:]
    return bytes(out)


# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------

_B36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def _js_parse_int(text, base):
    """模擬 JS parseInt(text, base)：遇到非法字元即停，無效回 None（NaN）。"""
    value = 0
    started = False
    for ch in text.strip().lower():
        d = _B36.find(ch)
        if d < 0 or d >= base:
            break
        value = value * base + d
        started = True
    return value if started else None


def _unescape(text):
    text = text.replace("\\'", "'").replace('\\"', '"').replace("\\/", "/")
    text = text.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")
    return text.replace("\\\\", "\\")


def _clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&quot;", '"').replace("&#39;", "'")
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", text).strip()


def _abs_url(site, url):
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return site + url
    if url.startswith("http"):
        return url
    return site + "/" + url.lstrip("./")


def _to_int(value, fallback=1):
    try:
        n = int(str(value).strip())
        return n if n > 0 else fallback
    except Exception:
        return fallback


# --------------------------------------------------------------------------
# 主體
# --------------------------------------------------------------------------

class Spider(BaseSpider):

    # ---------------- 生命週期 ----------------

    def init(self, extend=""):
        if isinstance(extend, dict):
            options = extend
        elif extend:
            try:
                options = json.loads(extend)
            except Exception:
                options = {}
        else:
            options = {}
        if not isinstance(options, dict):
            options = {}

        self.options = options
        raw = str(options.get("site") or options.get("host") or "").strip()
        if raw:
            if "://" not in raw:
                raw = "https://" + raw
            parts = urllib.parse.urlsplit(raw)
            self.site = "%s://%s" % (parts.scheme or "https", parts.netloc or parts.path)
        else:
            self.site = DEFAULT_SITE
        self.site = self.site.rstrip("/")
        self.lang = str(options.get("lang") or LANG_SEG).strip("/") or LANG_SEG
        self.cache_key = "18av01_makers:" + str(getattr(self, "siteKey", "") or "default")
        self._http_cache = {}

    def getName(self):
        return "18AV"

    def destroy(self):
        self._http_cache = {}

    def isVideoFormat(self, url):
        url = (url or "").lower()
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    # ---------------- HTTP ----------------

    def _headers(self, referer=None):
        return {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Referer": referer or (self.site + "/%s/" % self.lang),
            "Connection": "close",
        }

    def _fetch(self, url, referer=None, binary=False):
        """取頁面。帶重試與 gzip 解壓；失敗回空字串。"""
        last = None
        for attempt in range(RETRY + 1):
            try:
                req = urllib.request.Request(url, headers=self._headers(referer))
                resp = urllib.request.urlopen(req, timeout=TIMEOUT)
                raw = resp.read()
                enc = (resp.headers.get("Content-Encoding") or "").lower()
                if "gzip" in enc:
                    try:
                        raw = gzip.GzipFile(fileobj=BytesIO(raw)).read()
                    except Exception:
                        pass
                elif "deflate" in enc:
                    try:
                        raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                    except Exception:
                        pass
                resp.close()
                if binary:
                    return raw
                # 站方 UTF-8，但保留容錯
                for codec in ("utf-8", "gb18030", "big5"):
                    try:
                        return raw.decode(codec)
                    except Exception:
                        continue
                return raw.decode("utf-8", "ignore")
            except urllib.error.HTTPError as exc:
                last = exc
            except Exception as exc:
                last = exc
            if attempt < RETRY:
                time.sleep(0.6 * (attempt + 1))
        return b"" if binary else ""

    # ---------------- 列表解析 ----------------

    _CARD_RE = re.compile(r"<div class='post[^']*'>(.*?)(?=<div class='post[^']*'>|</div>\s*</div>\s*</div>|$)", re.S)

    def _parse_cards(self, html):
        """列表頁 → [vod dict]。站方兩種版型（帶 video / 純 post）都吃。"""
        items = []
        seen = set()
        blocks = re.split(r"<div class='post[^']*'>|<div class=\"post[^\"]*\">", html)[1:]
        if not blocks:
            blocks = [html]
        for block in blocks:
            m = re.search(r"<a[^>]+href=['\"]([^'\"]+_content/[^'\"]+)['\"]", block)
            if not m:
                continue
            link = _unescape(m.group(1)).strip()
            vid = self._vid_from_url(link)
            if not vid or vid in seen:
                continue
            seen.add(vid)

            name = ""
            h = re.search(r"<h3[^>]*>\s*<a[^>]*>(.*?)</a>", block, re.S)
            if h:
                name = _clean(h.group(1))
            if not name:
                t = re.search(r"title=['\"]([^'\"]+)['\"]", block)
                name = _clean(t.group(1)) if t else vid

            pic = ""
            p = re.search(r"<img[^>]+src=['\"]([^'\"]+)['\"]", block)
            if p:
                pic = _abs_url(self.site, _unescape(p.group(1)))
            if not pic:
                p = re.search(r"data-src=['\"]([^'\"]+\.(?:jpg|png|webp))['\"]", block)
                if p:
                    pic = _abs_url(self.site, _unescape(p.group(1)))

            remark = ""
            r = re.search(r"<div class='meta'>\s*(.*?)\s*</div>", block, re.S)
            if r:
                remark = _clean(r.group(1))

            items.append({
                "vod_id": link,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark,
                "style": {"type": "rect", "ratio": 1.33},
            })
        return items

    @staticmethod
    def _vid_from_url(url):
        m = re.search(r"/([a-zA-Z_-]*content)/(\d+)", url or "")
        return m.group(2) if m else ""

    def _pagecount(self, html, pg):
        pages = []
        for num in re.findall(r"/(?:[a-zA-Z_-]+)/(?:all|\d+)/(\d+)\.html", html):
            n = _to_int(num, 0)
            if n:
                pages.append(n)
        total = max(pages) if pages else 0
        if total:
            return total
        return pg if self._parse_cards(html) else 1

    def _page(self, items, pg, pagecount):
        return {
            "list": items,
            "page": pg,
            "pagecount": max(1, pagecount),
            "limit": PAGE_SIZE,
            "total": PAGE_SIZE * max(1, pagecount),
        }

    # ---------------- 分類 ----------------

    def homeContent(self, filter):
        classes = [{"type_id": slug, "type_name": name} for slug, name in CATEGORIES]
        classes.append({"type_id": "makers", "type_name": "無碼片商專區",
                        "type_flag": "1"})
        result = {"class": classes}
        if filter:
            result["filters"] = {
                "makers": [],
            }
        return result

    def homeVideoContent(self):
        html = self._fetch("%s/%s/chinese_list/all/1.html" % (self.site, self.lang))
        return {"list": self._parse_cards(html)}

    def _makers(self):
        """片商清單：優先即時抓首頁解析，失敗用內建清單兜底。"""
        cached = None
        try:
            cached = self.getCache(self.cache_key)
        except Exception:
            cached = None
        if cached:
            try:
                data = json.loads(cached)
                if isinstance(data, list) and data:
                    return data
            except Exception:
                pass

        result = []
        try:
            html = self._fetch("%s/%s/" % (self.site, self.lang))
            for m in re.finditer(
                    r"href=['\"]https?://[^'\"]*/%s/uncensored_makersr/(\d+)/([^/'\"]+)/\d+\.html['\"]"
                    % re.escape(self.lang), html):
                mid, name = m.group(1), urllib.parse.unquote(m.group(2))
                result.append({"mid": mid, "name": _clean(name)})
        except Exception:
            result = []

        # 去重保序
        seen = set()
        uniq = []
        for row in result:
            if row["mid"] in seen:
                continue
            seen.add(row["mid"])
            uniq.append(row)

        if not uniq:
            uniq = [
                {"mid": "32", "name": "一本道(1pondo)"},
                {"mid": "30", "name": "カリビアンコム(Caribbeancom)"},
                {"mid": "40", "name": "カリビアンコムPPV(Caribbeancompr)"},
                {"mid": "17", "name": "HEYZO"},
                {"mid": "29", "name": "東京熱(Tokyo Hot)"},
                {"mid": "31", "name": "天然むすめ(10musume)"},
                {"mid": "36", "name": "パコパコママ(pacopacomama)"},
                {"mid": "35", "name": "ガチん娘！(Gachinco)"},
                {"mid": "34", "name": "エッチな4610"},
                {"mid": "39", "name": "エッチな0930"},
                {"mid": "38", "name": "人妻斬り0930"},
                {"mid": "126", "name": "トリプルエックス (XXX-AV)"},
            ]
        else:
            try:
                self.setCache(self.cache_key, json.dumps(uniq, ensure_ascii=False))
            except Exception:
                pass
        return uniq

    def categoryContent(self, tid, pg, filter, extend):
        pg = _to_int(pg, 1)
        tid = str(tid or "")

        if tid == "makers":
            data = [{
                "vod_id": "folder/maker/%s/%s" % (m["mid"], urllib.parse.quote(m["name"])),
                "vod_name": m["name"],
                "vod_tag": "folder",
                "vod_pic": "",
                "vod_remarks": "片商",
                "style": {"type": "list"},
            } for m in self._makers()]
            return self._page(data, pg, 1)

        if tid.startswith("folder/maker/"):
            rest = tid[len("folder/maker/"):]
            mid, _, name = rest.partition("/")
            name = urllib.parse.unquote(name or "")
            url = "%s/%s/uncensored_makersr/%s/%s/%d.html" % (
                self.site, self.lang, mid, urllib.parse.quote(name), pg)
            html = self._fetch(url)
            items = self._parse_cards(html)
            return self._page(items, pg, self._pagecount(html, pg))

        if tid not in [slug for slug, _ in CATEGORIES]:
            return self._page([], pg, 1)

        url = "%s/%s/%s_list/all/%d.html" % (self.site, self.lang, tid, pg)
        html = self._fetch(url)
        items = self._parse_cards(html)
        return self._page(items, pg, self._pagecount(html, pg))

    # ---------------- 搜尋 ----------------

    def searchContent(self, key, quick, pg="1"):
        key = (key or "").strip()
        if not key:
            return self._page([], 1, 1)
        pg = _to_int(pg, 1)
        keyword = urllib.parse.quote(key, safe="")
        last_html = ""
        for stype, _label in SEARCH_TYPES:
            url = "%s/%s/%s_search/all/%s/%d.html" % (self.site, self.lang, stype, keyword, pg)
            html = self._fetch(url)
            items = self._parse_cards(html)
            if items:
                return self._page(items, pg, self._pagecount(html, pg))
            last_html = html
        return self._page([], pg, 1)

    # ---------------- 詳情 ----------------

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        url = _abs_url(self.site, str(vid or ""))
        if "_content/" not in url:
            return {"list": [], "msg": "無效的影片 ID"}

        html = self._fetch(url)
        if not html:
            return {"list": [], "msg": "頁面讀取失敗，請稍後再試"}

        name = ""
        m = re.search(r"<h1>\s*(?:<b>)?(.*?)(?:</b>)?\s*</h1>", html, re.S)
        if m:
            name = _clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            name = _clean(m.group(1)) if m else ""
        name = re.sub(r"\s*-\s*18AV.*$", "", name).strip() or "18AV 影片"

        pic = ""
        m = re.search(r"id=['\"]player-wrap['\"][^>]*>\s*<img[^>]+src=['\"]([^'\"]+)['\"]", html)
        if not m:
            m = re.search(r"<img[^>]+src=['\"]([^'\"]*(?:stimg|18avmmcg)[^'\"]*\.(?:jpg|png|webp))['\"]", html)
        if m:
            pic = _abs_url(self.site, m.group(1))

        meta = self._parse_meta(html)
        actors = self._parse_actors(html)
        intro = self._parse_intro(html)

        play_from, play_url = self._parse_play(html, url)

        item = {
            "vod_id": url,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": meta.get("影片時長", "") or meta.get("影片时长", ""),
            "type_name": (meta.get("影片類別") or meta.get("影片类别")
                          or meta.get("類別") or meta.get("类别") or "18AV"),
            "vod_year": (meta.get("網站發佈", "") or meta.get("网站发布", "") or "")[:4],
            "vod_area": "日本",
            "vod_director": self._meta_pick(meta, "導演", "导演"),
            "vod_actor": "、".join(actors),
            "vod_content": intro or name,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
            "style": {"type": "rect", "ratio": 1.33},
        }

        # 番號 / 發行商 / 製作商 併入備註，TVBox 端顯示更完整
        extra = []
        for label in ("番號", "番号", "發行商", "制作商", "製作商"):
            value = self._meta_pick(meta, label)
            if value:
                extra.append("%s %s" % (label, value))
        if extra:
            item["vod_remarks"] = (item["vod_remarks"] + " · " if item["vod_remarks"] else "") \
                + " · ".join(extra)

        return {"list": [item]}

    @staticmethod
    def _meta_pick(meta, *labels):
        """取第一個有效值，"N/A" / "-" 之類的佔位不算。"""
        for label in labels:
            value = (meta.get(label) or "").strip()
            if value and value.upper() not in ("N/A", "NA", "NULL", "NONE", "-", "--",
                                               "未知", "無", "无", "不詳", "不详"):
                return value
        return ""

    @staticmethod
    def _parse_meta(html):
        """詳情頁 posts-headline / posts-message 成對的欄位。"""
        meta = {}
        pairs = re.findall(
            r"<li class='posts-headline'>\s*(.*?)\s*[:：]?\s*</li>\s*"
            r"<li class='posts-message'>\s*(.*?)\s*</li>", html, re.S)
        for label, value in pairs:
            label = _clean(label).rstrip(":：").strip()
            if not label or label in meta:
                continue
            meta[label] = _clean(value)
        return meta

    def _parse_actors(self, html):
        actors = []
        seg = re.search(r"actor-heading-left['\"]\s*>\s*<p>\s*(女優|女优|演員|演员)\s*</p>(.*?)</div>\s*</div>\s*<div",
                        html, re.S)
        if not seg:
            seg = re.search(r"actor-right-part['\"]\s*>(.*?)</ul>", html, re.S)
            body = seg.group(1) if seg else ""
        else:
            body = seg.group(2)
        if body:
            for m in re.finditer(r"<p>\s*(.*?)\s*</p>", body, re.S):
                nm = _clean(m.group(1))
                if nm and nm not in actors and len(nm) < 60:
                    actors.append(nm)
        return actors

    @staticmethod
    def _parse_intro(html):
        m = re.search(r"<div class='posts-inner-details-text-top'>\s*"
                      r"<span class='posts-inner-details-text-left'>\s*<ul>\s*"
                      r"<li[^>]*>\s*(?:簡介|简介|內容|内容)[:：]?\s*</li>\s*"
                      r"<li[^>]*>\s*(.*?)\s*</li>", html, re.S)
        if m:
            return _clean(m.group(1))
        m = re.search(r"<meta[^>]+name=['\"]description['\"][^>]+content=['\"]([^'\"]+)['\"]", html)
        return _clean(m.group(1)) if m else ""

    # ---------------- 播放令牌解密 ----------------

    _ENTRY_RE = re.compile(
        r"mvarr\['([^']+)'\]\s*=\s*\[\[\s*'([^']*)'\s*,\s*'([0-9a-z]+(?:%s[0-9a-z]+)+)'\s*,"
        r"\s*'((?:[^'\\]|\\.)*)'\s*,\s*'((?:[^'\\]|\\.)*)'\s*,\s*'((?:[^'\\]|\\.)*)'"
        % r"[a-z]", re.S)

    def _page_params(self, html):
        """從當前詳情頁讀出 4 個參數（自訂進位 / XOR / AES key / IV）。

        頁面上有一串名字相近的誘餌（hdddedd252、argdeqweqweqww、hadeedd252…），
        因此只認精確名稱，並回傳多組候選供窮舉。
        """
        def nums(name):
            out = []
            for m in re.finditer(r"(?:var\s+)?" + re.escape(name) + r"\s*=\s*(\d+)", html):
                v = _to_int(m.group(1), 0)
                if v:
                    out.append(v)
            return out

        def strings(name):
            out = []
            for m in re.finditer(r"(?:var\s+)?" + re.escape(name) + r"\s*=\s*'([0-9a-zA-Z]{16,64})'", html):
                out.append(m.group(1))
            return out

        radix = nums("hcdeedg252") or [11]
        xors = nums("hadeedg252") or [16]
        keys = strings("argdeqweqweqwe")
        ivs = strings("hdddedg252")
        if not keys:
            keys = strings("argdeqweqweqw")
        if not ivs:
            ivs = strings("hdddedg252")
        return radix, xors, keys, ivs

    @staticmethod
    def _decrypto(raw, radix, xor):
        """自訂進位切分 → 逐字 XOR → 字串。"""
        if not 2 <= radix <= 35:
            return ""
        sep = chr(radix + 97)
        out = []
        for part in raw.split(sep):
            n = _js_parse_int(part, radix)
            if n is None:
                continue
            out.append(chr(n ^ xor))
        return "".join(out)

    def _decrypt_token(self, raw, params):
        radixs, xors, keys, ivs = params
        for radix in radixs:
            for xor in xors:
                stage = self._decrypto(raw, radix, xor)
                if not stage:
                    continue
                # 補齊 base64 padding
                pad = "=" * (-len(stage) % 4)
                try:
                    data = base64.b64decode(stage + pad)
                except Exception:
                    continue
                for key in keys:
                    for iv in ivs:
                        try:
                            kb, ib = key.encode(), iv.encode()
                        except Exception:
                            continue
                        if len(kb) not in (16, 24, 32) or len(ib) < 16:
                            continue
                        try:
                            plain = aes_cbc_decrypt(data, kb, ib)
                        except Exception:
                            continue
                        if plain:
                            try:
                                text = plain.decode("utf-8").strip()
                            except Exception:
                                continue
                            if text and re.fullmatch(r"[0-9A-Za-z_\-\.~%/+=]{8,}", text):
                                return text
        return ""

    def _parse_play(self, html, page_url):
        """回傳 (play_from, play_url)：每條線路一組。"""
        entries = self._ENTRY_RE.findall(html)
        if not entries:
            return [], []

        referer = page_url
        play_from, play_url = [], []
        tokens = {}
        params = None
        for idx, entry in enumerate(entries):
            tag, iframe_id, raw = entry[0], entry[1], entry[2]
            prefix = entry[4] if len(entry) > 4 else ""
            if raw in tokens:
                token = tokens[raw]
            else:
                if params is None:
                    params = self._page_params(html)
                token = self._decrypt_token(raw, params)
                tokens[raw] = token
            if not token:
                continue

            res = "1080"
            m = re.search(r"numresolution=(\d+)", prefix or "")
            if m:
                res = m.group(1)

            label = "線路%d" % (idx + 1)
            if res in ("1080", "720", "480"):
                label = "%sP 線路%d" % (res, idx + 1)

            play_from.append(label)
            play_url.append("正片$%s@@%s@@%s" % (token, res, referer))

        return play_from, play_url

    # ---------------- 播放 ----------------

    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "")
        parts = raw.split("@@")
        token = parts[0].strip()
        res = parts[1].strip() if len(parts) > 1 else "1080"
        referer = parts[2].strip() if len(parts) > 2 else (self.site + "/")

        if not token:
            return {"parse": 0, "msg": "播放令牌為空，請回上一頁重試"}

        for num in (res, "1080", "720"):
            url = "%s/js/player/play.php?numresolution=%s&id=%s" % (
                self.site, num, urllib.parse.quote(token, safe=""))
            html = self._fetch(url, referer=referer)
            if not html:
                continue
            best = self._pick_source(html)
            if best:
                return {
                    "parse": 0,
                    "jx": 0,
                    "url": best,
                    "header": {
                        "User-Agent": UA,
                        "Referer": self.site + "/",
                    },
                    "format": "application/x-mpegURL",
                }
        return {"parse": 0, "msg": "未取得播放地址，可能該片源已下架"}

    @staticmethod
    def _pick_source(html):
        """播放頁 videoSources 裡挑最高畫質的 m3u8/wmv 直鏈。"""
        sources = re.findall(
            r"src:\s*['\"]([^'\"]+)['\"]\s*,\s*type:\s*['\"]([^'\"]+)['\"]\s*,\s*size:\s*(\d+)",
            html)
        if not sources:
            sources = [(m, "application/x-mpegURL", "0")
                       for m in re.findall(r"['\"]([^'\"]+\.(?:m3u8|mp4))['\"]", html)]
        if not sources:
            return ""

        def score(row):
            url, kind, size = row[0], row[1], row[2]
            try:
                s = int(size)
            except Exception:
                s = 0
            bonus = 100000 if "mpegurl" in (kind or "") or ".m3u8" in url else 0
            return (bonus + s, url)

        rows = [r for r in sources if r[0]]
        if not rows:
            return ""
        url = max(rows, key=score)[0]
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return DEFAULT_SITE + url
        return url
