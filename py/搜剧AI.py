#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# TVBox / FongMi Python 爬虫 · 搜剧AI (baipiaozhe.ai)
# ------------------------------------------------------------
# 站点  : 搜剧AI (React SPA + REST /v1 接口, 全站 HMAC 签名校验)
# 签名  : HMAC-SHA256(KEY, "METHOD\npath?query\ntimestamp\nnonce")
#         6 个 x-ai-movie-* 头; KEY 写在前端 chunk 里
# 播放  : episodes[].token → resolve → line_options[].url(resolve://)
#         → POST resolve-line {ticket} → line.url (mp4 直链)
# 注意  : 无 f-string / 兼容 py2+py3 / FongMi(base.spider) 与旧 TVBox 双体系
# 版本  : build 20261019-1
# ============================================================
import sys
import re
import json
import time
import random
import string
import hashlib
import hmac
import base64

try:
    import urllib.request as _urlreq
    import urllib.parse as _urlpar
except ImportError:
    import urllib as _urlpar
    import urllib2 as _urlreq

try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    _BaseSpider = object

try:
    import requests as _rq
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass
except ImportError:
    _rq = None

# ============ 站点常量 (来自前端 chunk: movie-card-runtime) ============
API = "https://baipiaozhe.ai"
SIGN_KEY = ("f39d73aa7a6426203cdee1ef17b31d3b7ea8c23f4c59c62a3a8aa0f39ee5e79d")
CLIENT_NAME = "movie-search-frontend"
CLIENT_VER = "1.0.0"
BUILD_VER = "aimovie-v2026.10.18.1-library-download-f05b45a438ff-web"
PROTO_VER = "2026-07-05.library-v2.playback-v1"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
PLAY_UA = ("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36")

# 分类 (kind 见前端枚举 D)
CLASSES = [
    ["series", u"电视剧"],
    ["movie", u"电影"],
    ["short_drama", u"短剧"],
    ["anime", u"动漫"],
    ["variety", u"综艺"],
    ["documentary", u"纪录片"],
]

GENRES = [u"动作", u"喜剧", u"爱情", u"科幻", u"悬疑", u"恐怖", u"剧情",
          u"战争", u"犯罪", u"动画", u"奇幻", u"冒险", u"武侠", u"古装",
          u"惊悚", u"灾难", u"历史", u"家庭"]
AREAS = [u"中国大陆", u"香港", u"台湾", u"美国", u"韩国", u"日本",
         u"英国", u"法国", u"泰国", u"印度"]
YEARS = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
         "2018", "2017", "2016", "2015"]

_ALNUM = string.ascii_letters + string.digits
_HEX = "0123456789abcdef"
_IS_PY3 = sys.version_info[0] >= 3

try:
    _unicode = unicode
except NameError:
    _unicode = str


def _ustr(x):
    if x is None:
        return ""
    if isinstance(x, _unicode):
        return x
    if isinstance(x, (bytes, bytearray)):
        return bytes(x).decode("utf-8", "ignore") if _IS_PY3 else str(x)
    return _unicode(x)


def _q(s):
    s = _ustr(s)
    if _IS_PY3:
        if not isinstance(s, bytes):
            s = s.encode("utf-8")
        return _urlpar.quote(s)
    if isinstance(s, _unicode):
        s = s.encode("utf-8")
    return _urlpar.quote(s)


def _b2s(b):
    if isinstance(b, (bytes, bytearray, memoryview)):
        return bytes(bytearray(b)).decode("utf-8", "ignore")
    return b


def _rand_hex(n):
    rnd = random.SystemRandom()
    return "".join(rnd.choice(_HEX) for _ in range(n))


def _hmac_hex(key, msg):
    kb = key.encode("utf-8") if isinstance(key, _unicode) else key
    mb = msg.encode("utf-8") if isinstance(msg, _unicode) else msg
    try:
        return hmac.new(kb, mb, hashlib.sha256).hexdigest()
    except AttributeError:
        return hmac.new(kb, mb, hashlib.sha256).hexdigest()


# ============ 爬虫 ============
class Spider(_BaseSpider):

    def getName(self):
        return u"搜剧AI"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.session_id = ""
        self.destroy()

    def destroy(self):
        pass

    # ---------- 签名请求 ----------
    def _headers(self, method, path_q):
        ts = str(int(time.time() * 1000))
        nonce = _rand_hex(32)
        msg = "%s\n%s\n%s\n%s" % (method, path_q, ts, nonce)
        return {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Referer": API + "/",
            "Origin": API,
            "x-ai-movie-client-name": CLIENT_NAME,
            "x-ai-movie-client-version": CLIENT_VER,
            "x-ai-movie-build-version": BUILD_VER,
            "x-ai-movie-protocol-version": PROTO_VER,
            "x-ai-movie-timestamp": ts,
            "x-ai-movie-nonce": nonce,
            "x-ai-movie-signature": _hmac_hex(SIGN_KEY, msg),
        }

    def _api(self, path_q, method="GET", body=None):
        """签名请求 -> dict (失败返回 {})"""
        h = self._headers(method, path_q)
        url = path_q if path_q.startswith("http") else API + path_q
        last = None
        for _ in range(2):
            try:
                if _rq is not None:
                    if method == "GET":
                        r = _rq.get(url, headers=h, timeout=15, verify=False)
                    else:
                        hh = dict(h)
                        hh["Content-Type"] = "application/json"
                        r = _rq.post(url, headers=hh, timeout=20,
                                     data=json.dumps(body or {}), verify=False)
                    raw = _b2s(r.content)
                else:
                    data = None
                    if method != "GET":
                        data = json.dumps(body or {}).encode("utf-8")
                        h = dict(h)
                        h["Content-Type"] = "application/json"
                    req = _urlreq.Request(url, data=data, headers=h)
                    resp = _urlreq.urlopen(req, timeout=20)
                    try:
                        raw = _b2s(resp.read())
                    finally:
                        try:
                            resp.close()
                        except Exception:
                            pass
                if not raw:
                    continue
                return json.loads(raw)
            except Exception as e:
                last = e
                time.sleep(0.8)
        return {}

    # ---------- 卡片 -> vod ----------
    @staticmethod
    def _kind_name(k):
        d = {"movie": u"电影", "series": u"剧集", "short_drama": u"短剧",
             "anime": u"动漫", "variety": u"综艺",
             "documentary": u"纪录片", "sports": u"体育", "adult": u"18+"}
        return d.get(k, _ustr(k))

    def _to_vod(self, c):
        if not isinstance(c, dict):
            return None
        cid = _ustr(c.get("id") or c.get("variant_id"))
        if not cid:
            return None
        pic = _ustr(c.get("poster_url") or c.get("backdrop_url"))
        remarks = _ustr(c.get("remarks"))
        if not remarks:
            yr = _ustr(c.get("year"))
            remarks = self._kind_name(c.get("content_kind")) + (
                ("·" + yr) if yr else "")
        return {
            "vod_id": cid,
            "vod_name": _ustr(c.get("title") or c.get("normalized_title")),
            "vod_pic": pic,
            "vod_remarks": remarks,
        }

    # ---------- 首页 ----------
    def homeContent(self, filter=1):
        classes = [{"type_id": c[0], "type_name": c[1]} for c in CLASSES]
        filters = {}
        if filter:
            years = [{"n": u"全部", "v": ""}]
            for y in YEARS:
                years.append({"n": y, "v": y})
            genres = [{"n": u"全部", "v": ""}]
            for g in GENRES:
                genres.append({"n": g, "v": g})
            areas = [{"n": u"全部", "v": ""}]
            for a in AREAS:
                areas.append({"n": a, "v": a})
            sorts = [{"n": u"最新", "v": "latest_catalog"},
                     {"n": u"最热", "v": "hot"}]
            for tid, _n in CLASSES:
                filters[tid] = [
                    {"key": "genre", "name": u"类型", "value": genres},
                    {"key": "area", "name": u"地区", "value": areas},
                    {"key": "year", "name": u"年份", "value": years},
                    {"key": "sort", "name": u"排序", "value": sorts},
                ]
        return {"class": classes, "filters": filters} if filter \
            else {"class": classes}

    def homeVideoContent(self):
        items, seen = [], set()
        for qs in ("/v1/feed/home?scope=public&mode=preview&sections=3&cards=10",
                   "/v1/browse/catalog?kind=movie&page=1&limit=20&intent=latest_catalog",
                   "/v1/browse/catalog?kind=series&page=1&limit=20&intent=latest_catalog"):
            try:
                o = self._api(qs)
                cards = []
                for sec in (o.get("sections") or []):
                    cards.extend(sec.get("cards") or [])
                cards.extend(o.get("cards") or [])
                for c in cards:
                    v = self._to_vod(c)
                    if v and v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        items.append(v)
            except Exception:
                pass
        return {"list": items}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg=1, filter=1, extend=None):
        try:
            page = max(1, int(pg) if pg else 1)
        except (ValueError, TypeError):
            page = 1
        ext = {}
        if isinstance(extend, str) and extend:
            try:
                ext = json.loads(extend)
            except Exception:
                ext = {}
        elif isinstance(extend, dict):
            ext = extend
        kind = _ustr(tid) or "movie"
        parts = ["kind=" + _q(kind), "page=%d" % page, "limit=20"]
        genre = _ustr(ext.get("genre", ""))
        area = _ustr(ext.get("area", ""))
        year = _ustr(ext.get("year", ""))
        if genre:
            parts.append("genre=" + _q(genre))
        if area:
            parts.append("area=" + _q(area))
        if year:
            parts.append("year=" + _q(year))
        parts.append("intent=latest_catalog")
        items = []
        has_more = 0
        try:
            o = self._api("/v1/browse/catalog?" + "&".join(parts))
            for c in (o.get("cards") or []):
                v = self._to_vod(c)
                if v:
                    items.append(v)
            pg_info = o.get("pagination") or {}
            has_more = 1 if pg_info.get("has_more") else 0
        except Exception:
            pass
        return {"list": items, "page": page,
                "pagecount": page + 1 if has_more else page,
                "limit": max(len(items), 20), "total": len(items)}

    # ---------- 详情 ----------
    def detailContent(self, ids=None):
        if not ids:
            return {"list": []}
        try:
            vid = _ustr(ids[0]).strip()
        except (IndexError, TypeError):
            return {"list": []}
        if not vid:
            return {"list": []}
        try:
            d = self._api("/v1/catalog/" + _q(vid) + "/detail")
            if not d or d.get("error"):
                return {"list": []}
            vod = {
                "vod_id": vid,
                "vod_name": _ustr(d.get("title")),
                "vod_pic": _ustr(d.get("poster_url")),
                "vod_year": _ustr(d.get("year")),
                "vod_area": _ustr(d.get("area")),
                "vod_remarks": _ustr(d.get("remarks")
                                     or d.get("episode_progress_text")),
                "vod_content": _ustr(d.get("description")),
                "vod_actor": u"、".join([_ustr(x) for x in
                                         (d.get("actors") or [])]),
                "vod_director": u"、".join([_ustr(x) for x in
                                            (d.get("directors") or [])]),
            }
            kinds = d.get("genres") or []
            if kinds:
                vod["vod_class"] = _ustr(kinds[0])
            # 剧集列表
            eo = self._api("/v1/catalog/" + _q(vid)
                           + "/episodes?limit=200&offset=0")
            eps = eo.get("episodes") or []
            urls = []
            for i, e in enumerate(eps):
                tok = _ustr(e.get("token") or e.get("id"))
                if not tok:
                    continue
                name = _ustr(e.get("title") or e.get("display_name"))
                if not name:
                    try:
                        name = u"第%d集" % int(e.get("number") or i + 1)
                    except Exception:
                        name = u"第%d集" % (i + 1)
                urls.append(name + "$" + tok)
            if not urls:
                # 电影等无剧集列表: 直接用 vod_id 播放
                urls = [u"正片$" + vid]
            vod["vod_play_from"] = u"搜剧AI"
            vod["vod_play_url"] = "#".join(urls)
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        try:
            tok = _ustr(id).strip()
        except Exception:
            tok = ""
        if not tok:
            return {"parse": 0, "url": "", "header": {}}
        for sep in ("~~", "|", "$"):
            if sep in tok:
                tok = tok.rsplit(sep, 1)[-1].strip()
        header = {"User-Agent": PLAY_UA, "Referer": API + "/"}
        try:
            # 1) resolve: 拿线路候选
            o = self._api("/v1/playback/resolve/" + _q(tok) + "?view=compact")
            lines = o.get("line_options") or []
            # 已经 resolved 且是 http 的优先
            for ln in lines:
                u = _ustr(ln.get("url"))
                if u.startswith("http") and ln.get("resolved"):
                    kind = _ustr(ln.get("url_kind"))
                    if kind in ("mp4", "m3u8", "hls", ""):
                        return {"parse": 0, "url": u, "header": header}
            # 2) resolve://ticket -> POST resolve-line
            for ln in lines[:6]:
                u = _ustr(ln.get("url"))
                if not u.startswith("resolve://"):
                    continue
                ticket = u[len("resolve://"):]
                r = self._api("/v1/playback/resolve-line?view=compact",
                              "POST", {"ticket": ticket})
                line = r.get("line") or {}
                pu = _ustr(line.get("url"))
                if pu.startswith("http"):
                    return {"parse": 0, "url": pu, "header": header}
        except Exception:
            pass
        return {"parse": 0, "url": "", "header": {}}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=None, pg=None):
        if not key or not _ustr(key).strip():
            return {"list": []}
        try:
            page = int(pg) if pg else 1
        except (ValueError, TypeError):
            page = 1
        items = []
        has_more = 0
        try:
            o = self._api("/v1/browse/catalog?q=" + _q(key)
                          + "&page=%d&limit=20&intent=catalog_search" % page)
            for c in (o.get("cards") or []):
                v = self._to_vod(c)
                if v:
                    items.append(v)
            has_more = 1 if (o.get("pagination") or {}).get("has_more") else 0
        except Exception:
            pass
        return {"list": items, "page": page,
                "pagecount": page + 1 if has_more else page,
                "limit": max(len(items), 20), "total": len(items)}

    def searchContentPage(self, key, quick=None, pg=None):
        return self.searchContent(key, quick, pg)

    # ---------- 兼容 ----------
    def isVideoFormat(self, url):
        return bool(re.search(r"(?i)\.(mp4|m3u8|flv|mkv|ts|mov|mpd)(\?|$)",
                              _ustr(url)))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, "text/plain", ""]

    def liveContent(self, url):
        return {"list": []}

    def action(self, a):
        return {}


# ============================================================
# 模块级转发 (旧 TVBox 体系)
# ============================================================
_M = Spider
_sp = None


def _ins():
    global _sp
    if _sp is None:
        _sp = _M()
    return _sp


def getName():
    return _ins().getName()


def getDependence():
    return []


def init(extend=""):
    return _ins().init(extend)


def destroy():
    try:
        _ins().destroy()
    except Exception:
        pass


def homeContent(filter=True):
    return _ins().homeContent(filter)


def homeVideoContent():
    return _ins().homeVideoContent()


def categoryContent(tid, pg, filter=True, extend=None):
    try:
        return _ins().categoryContent(tid, pg, filter,
                                      extend if extend is not None else {})
    except Exception:
        return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}


def detailContent(ids):
    return _ins().detailContent(ids)


def searchContent(key, quick=False, pg="1"):
    return _ins().searchContent(key, quick, pg)


def playerContent(flag, id, vipFlags=None):
    return _ins().playerContent(flag, id, vipFlags)


def isVideoFormat(url):
    return _ins().isVideoFormat(url)


def manualVideoCheck():
    return False


def localProxy(param):
    return [404, "text/plain", ""]


def liveContent(url):
    return {"list": []}


def action(a):
    return {}


# ============ 自测 ============
if __name__ == "__main__":
    sp = Spider()
    sp.init("")
    print(u"=== homeContent ===")
    hc = sp.homeContent(1)
    print(u"分类:", [(c["type_id"], c["type_name"]) for c in hc["class"]])
    print(u"筛选:", [(f["key"], len(f["value"])) for f in hc["filters"]["movie"]])

    print(u"\n=== homeVideoContent ===")
    hv = sp.homeVideoContent()
    print(u"首页:", len(hv["list"]))
    for v in hv["list"][:3]:
        print("  ", v["vod_name"], "|", v["vod_remarks"])

    for tid, name in (("movie", u"电影"), ("series", u"电视剧"),
                      ("anime", u"动漫")):
        print(u"\n=== categoryContent %s ===" % name)
        cc = sp.categoryContent(tid, 1, 1, {})
        print(u"数量:", len(cc["list"]), u"| 还有下一页:",
              cc["pagecount"] > 1)
        for v in cc["list"][:3]:
            print("  ", v["vod_name"], "|", v["vod_remarks"])

    print(u"\n=== 筛选 电影/动作/2024 ===")
    cf = sp.categoryContent("movie", 1, 1,
                            {"genre": u"动作", "year": "2024"})
    print(u"数量:", len(cf["list"]))
    for v in cf["list"][:3]:
        print("  ", v["vod_name"])

    cc = sp.categoryContent("movie", 1, 1, {})
    if cc["list"]:
        vid = cc["list"][0]["vod_id"]
        print(u"\n=== detailContent", cc["list"][0]["vod_name"], "===")
        dc = sp.detailContent([vid])
        vod = dc["list"][0]
        print(u"名称:", vod["vod_name"], u"| 年份:", vod.get("vod_year"),
              u"| 演员:", vod.get("vod_actor", "")[:40])
        purl = vod["vod_play_url"]
        print(u"线路条目:", len(purl.split("#")))
        pid = purl.split("#")[0].split("$")[-1]
        print(u"\n=== playerContent ===")
        pc = sp.playerContent("", pid, {})
        print(u"  url:", (pc.get("url") or "")[:110])
        print(u"  header:", pc.get("header"))

    print(u"\n=== searchContent 美人余 ===")
    sc = sp.searchContent(u"美人余", "1", "1")
    print(u"结果:", len(sc["list"]))
    for v in sc["list"][:3]:
        print("  ", v["vod_name"], "|", v["vod_remarks"])
