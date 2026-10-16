# -*- coding: utf-8 -*-
"""
芒果TV TVBox Python 爬虫（独立版）v1
====================================
站点：https://www.mgtv.com/
资源：电视剧 / 电影 / 综艺 / 动漫 / 纪录片（5 大分类全量）
筛选：排序（最热 / 最新 / 精选）—— 实测 rider 接口仅 sort 维度真实有效。
      其余维度（area / kind）非 a1 一律返回空，channel/filter 接口需签名不可用，
      故只下发【真实可用】的选项，绝不给假选项。

【接口说明】
  分类列表：pianku.api.mgtv.com/rider/list/pcweb/v3
    - channelId 1=综艺 2=电视剧 3=电影 50=动漫 51=纪录片
    - sort: 空/c2=最新, c1=最热, c3=精选
  搜索：并行拉取各频道前几页 + 本地关键词匹配（官方搜索接口已 403/空）
  详情：pcweb.api.mgtv.com/episode/list

【播放 · 4K 解析引擎】
  芒果官方直链接口已加登录态与签名校验（实测 30001 参数错误），故走外挂解析。
  - 内置一组【实测可用】解析接口池，按可用性自动择优（含高清/4K 线路）
  - 解析请求用移动端 UA，更易命中高码率线路；支持 Cookie 注入
  - 想用自己的 4K 解析：改顶部 PARSERS / COOKIE，或写进 extend：
        {"parser":"https://你的解析/?url=", "cookie":"xxx", "ua":"..."}

接口约定：类名 Spider，playerContent 的 header 必须是 dict。
"""

import re
import json
import threading

# ---------- 壳子兼容层 ----------
try:  # Python 3
    from urllib.parse import quote as _quote
    from urllib.request import Request, urlopen

    def _q(s):
        return _quote(str(s), safe="/")

    _PY2 = False
except Exception:  # Jython 2.7 / Python 2 (TVBox/OK影视)
    from urllib import quote as _quote
    from urllib2 import Request, urlopen

    def _q(s):
        if isinstance(s, unicode):
            s = s.encode("utf-8")
        return _quote(str(s), safe="/")

    _PY2 = True

try:
    import requests as _rq
except Exception:
    _rq = None

try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        pass

UA_PC = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
REF = "https://www.mgtv.com/"
DEBUG = False

# 频道映射
CHANNEL = [("2", "电视剧"), ("3", "电影"), ("1", "综艺"), ("50", "动漫"), ("51", "纪录片")]
# 搜索用频道（含综艺等）
SEARCH_CH = ["1", "2", "3", "50", "51"]

# ================================================================
#  4K 解析引擎（统一配置）
#  说明：
#   1) 解析站的清晰度由【服务端】决定，客户端 py 只能"择优挑选 + 正确传参"，
#      无法强制某个站返回 4K。故这里给一组【实测可用】的接口池，按可用性择优。
#   2) 想用自己的 4K 解析：改下面的 PARSERS，或写进 TVBox 自定义 extend：
#        {"parser": "https://你的解析/?url=", "cookie": "xxx"}
#   3) 芒果TV官方直链需登录态，故走解析通道。
# ================================================================
#   4) 【自动淘汰】探测会识别"停运告别页/域名待售页/劫持跳转页"，失效接口自动跳过。
#   5) 解析站生命周期短（数周~数月），失效是常态——优先替换靠前接口或用 extend 自备。
PARSERS = [
    # ===== 实测可用（2026-10 复测）=====
    # —— 优先：通用云解析，页面带真实解析逻辑，多平台通吃 ——
    "https://yparse.ik9.cc/?url=",
    "https://yemu.xyz/?url=",
    "https://jx.hongshu.net/?url=",
    "https://bd.jx.cn/?url=",
    "https://jx.777jiexi.com/player/?url=",
    # —— 备用：结构正常的通用解析页 ——
    "https://okjx.cc/?url=",
    "https://jx.wannengjiexi.com/?url=",
    "https://jx.h8jx.com/?url=",
    "https://www.playm3u8.cn/jiexi.php?url=",
    # —— 兜底：域内跳转型（自动跟随到活线）——
    "https://jx.yparse.com/?url=",
]
# 是否启用解析通道（False 则只走直链 / 播放页）
USE_PARSER = True
# 解析请求头：部分接口靠 UA/Referer 决定清晰度，这里用移动端 UA 更易命中高码率
PARSER_UA = "Mozilla/5.0 (Linux; Android 12; Pixel 6 Build/SQ3A.220705.004; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/106.0.5249.126 Mobile Safari/537.36"
# 可选 Cookie（部分平台靠登录态解锁 4K）。留空则不发送。
COOKIE = ""

# 排序映射（实测有效值）
SORT = {"最新": "", "最热": "c1", "精选": "c3"}


def _log(*a):
    if DEBUG:
        try:
            print("[芒果]", " ".join([str(x) for x in a]))
        except Exception:
            pass


def _http(method, url, headers=None, body=None, timeout=15):
    hdrs = {"User-Agent": UA_PC, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    data = body.encode("utf-8") if isinstance(body, str) else body
    try:
        if _rq is not None:
            r = _rq.request(method.upper(), url, headers=hdrs, data=data,
                            timeout=timeout, verify=False)
            return r.status_code, r.content.decode("utf-8", "ignore")
        req = Request(url, data=data, headers=hdrs)
        try:
            import ssl
            ctx = ssl.create_unverified_context()
        except Exception:
            ctx = None
        if ctx is not None:
            try:
                with urlopen(req, timeout=timeout, context=ctx) as resp:
                    return resp.getcode(), resp.read().decode("utf-8", "ignore")
            except TypeError:
                pass
        with urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", "ignore")
    except Exception as e:
        _log("HTTP-ERR", method, url[:100], e)
        return 0, ""


def _jload(txt):
    if not txt:
        return {}
    txt = txt.strip()
    i = txt.find("{")
    if i < 0:
        return {}
    try:
        import json
        return json.loads(txt[i:])
    except Exception:
        try:
            import json
            return json.loads(txt[i:].rstrip(";"))
        except Exception:
            return {}


def _clean(s):
    if not s:
        return ""
    return re.sub(r"</?em[^>]*>", "", str(s)).strip()


def _int(v, d=0):
    try:
        return int(v)
    except Exception:
        return d


class Spider(Spider):

    def getName(self):
        return "芒果TV"

    def init(self, extend=""):
        self.host = ""
        self.headers = {"User-Agent": UA_PC}
        self.ext = extend or ""
        self._probe = {}
        # —— 4K 解析配置（extend 可覆盖顶部常量）——
        self.parsers = list(PARSERS)
        self.use_parser = USE_PARSER
        self.parser_ua = PARSER_UA
        self.cookie = COOKIE
        self.force_parser = ""
        try:
            j = json.loads(extend) if extend else {}
            if isinstance(j, dict):
                if j.get("parser"):
                    pp = j.get("parser")
                    self.force_parser = pp
                    self.parsers = [pp] + [x for x in self.parsers if x != pp]
                if j.get("parsers") and isinstance(j.get("parsers"), list):
                    self.parsers = list(j.get("parsers"))
                if j.get("cookie"):
                    self.cookie = j.get("cookie")
                if j.get("use_parser") is not None:
                    self.use_parser = bool(j.get("use_parser"))
                if j.get("ua"):
                    self.parser_ua = j.get("ua")
        except Exception:
            pass

    # ---------------- 工具 ----------------
    def _mk_vod(self, vid, name, pic, remarks="", **kw):
        return {
            "vod_id": vid, "vod_name": name, "vod_pic": pic or "",
            "vod_year": kw.get("year", ""), "vod_area": kw.get("area", ""),
            "vod_remarks": remarks or "", "vod_actor": kw.get("actor", ""),
            "vod_director": kw.get("director", ""), "vod_content": kw.get("content", ""),
            "type_name": kw.get("type_name", ""),
        }

    def _page(self, pg, items, total=None, pcount=None):
        pg = int(pg or 1)
        if pcount:
            pc = _int(pcount, pg)
        elif items:
            pc = pg + 20
        else:
            pc = pg
        return {
            "page": pg, "pagecount": pc, "limit": len(items),
            "total": total if total is not None else len(items), "list": items,
        }

    def _parse_docs(self, hd):
        out = []
        for it in (hd or []):
            if not isinstance(it, dict):
                continue
            vid = it.get("playPartId")
            if not vid:
                continue
            rc = it.get("rightCorner")
            rem = it.get("updateInfo") or ""
            if isinstance(rc, dict) and rc.get("text"):
                rem = (rc.get("text") + " " + rem).strip()
            out.append(self._mk_vod(str(vid), _clean(it.get("title")), it.get("img") or "",
                                    remarks=rem, year=it.get("year") or "",
                                    actor=it.get("subtitle") or "", content=it.get("story") or "",
                                    type_name="芒果TV"))
        return out

    def _rider(self, channel, pg, pc=30, area="a1", sort=""):
        u = ("https://pianku.api.mgtv.com/rider/list/pcweb/v3?platform=pcweb&channelId=%s&pn=%s&pc=%s"
             "&hudong=1&_support=10000000&kind=a1&area=%s" % (channel, pg or 1, pc, area))
        if sort:
            u += "&sort=%s" % sort
        st, txt = _http("GET", u, headers={"Referer": REF})
        j = _jload(txt)
        return (j.get("data") or {}).get("hitDocs") or []

    # ---------------- 搜索（并行 + 本地匹配） ----------------
    def _search(self, key, pg):
        key_n = key.lower().strip()
        if not key_n:
            return []
        frames = []
        lock = threading.Lock()

        def run(ch, p):
            try:
                docs = self._rider(ch, p, 30)
                if docs:
                    with lock:
                        frames.append((ch, docs))
            except Exception:
                pass

        ts = []
        for ch in SEARCH_CH:
            for p in (1, 2, 3):
                t = threading.Thread(target=run, args=(ch, p))
                t.setDaemon(True)
                ts.append(t)
        for t in ts:
            t.start()
        for t in ts:
            t.join(6)
        out, seen = [], set()
        for ch, docs in frames:
            for v in self._parse_docs(docs):
                nm = (v.get("vod_name") or "")
                if key_n not in nm.lower():
                    continue
                if v["vod_id"] in seen:
                    continue
                seen.add(v["vod_id"])
                out.append(v)
        _log("search", key, "->", len(out))
        return out

    # ---------------- 筛选（仅 sort 真实有效） ----------------
    def _gen_filters(self):
        vals = [{"n": "全部", "v": ""}]
        for label in ("最新", "最热", "精选"):
            vals.append({"n": label, "v": "sort\t%s" % SORT.get(label, "")})
        return [{"key": "sort", "name": "排序", "value": vals}]

    def _cate(self, ch, pg, ext=None):
        ext = ext or {}
        so = ""
        for k, v in ext.items():
            v = str(v or "").strip()
            if not v:
                continue
            if "\t" in v:
                kk, vv = v.split("\t", 1)
                if kk == "sort":
                    so = vv
        return self._parse_docs(self._rider(ch, pg, 30, "a1", so))

    # ---------------- 详情 ----------------
    def _detail(self, vid):
        u = "https://pcweb.api.mgtv.com/episode/list?page=1&size=50&video_id=" + str(vid)
        st, txt = _http("GET", u, headers={"Referer": REF})
        d = (_jload(txt).get("data") or {})
        info = d.get("info") if isinstance(d.get("info"), dict) else {}
        lst = d.get("list") or []
        series = d.get("series") or []
        title = _clean(info.get("title")) or _clean(info.get("videoName")) or str(vid)
        eps = []
        for e in lst:
            url = e.get("url") or ""
            if not url:
                continue
            if not url.startswith("http"):
                url = "https://www.mgtv.com" + url
            t = e.get("t4") or e.get("t1") or "正片"
            eps.append("%s$%s" % (t, url))
        if not eps and series:
            url = series[0].get("url") or ""
            if url:
                if not url.startswith("http"):
                    url = "https://www.mgtv.com" + url
                eps.append("正片$" + url)
        vod = self._mk_vod(str(vid), title, info.get("img") or "",
                           remarks=info.get("updateInfo") or "", year=info.get("year") or "",
                           actor=info.get("subtitle") or "", content=info.get("story") or "",
                           type_name="芒果TV")
        vod["vod_play_from"] = "芒果TV"
        vod["vod_play_url"] = "#".join(eps)
        return vod

    # ---------------- TVBox 接口 ----------------
    def homeContent(self, filter):
        classes = [{"type_id": cid, "type_name": name} for cid, name in CHANNEL]
        filters = {}
        if filter:
            f = self._gen_filters()
            for cid, _ in CHANNEL:
                filters[cid] = f
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        out = []
        lock = threading.Lock()

        def run(cid):
            try:
                r = self._cate(cid, 1)
                if r:
                    with lock:
                        out.extend(r[:20])
            except Exception:
                pass

        ts = [threading.Thread(target=run, args=(cid,)) for cid, _ in CHANNEL]
        for t in ts:
            t.setDaemon(True)
            t.start()
        for t in ts:
            t.join(8)
        return {"list": out}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        ext = extend if isinstance(extend, dict) else {}
        try:
            items = self._cate(str(tid), pg, ext)
        except Exception as e:
            _log("category ERR", tid, e)
            items = []
        return self._page(pg, items)

    def detailContent(self, ids):
        vods = []
        for vid in (ids or []):
            try:
                vod = self._detail(str(vid))
            except Exception as e:
                _log("detail ERR", vid, e)
                vod = None
            if vod:
                vods.append(vod)
        return {"list": vods}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        try:
            items = self._search(key, pg)
        except Exception as e:
            _log("search ERR", e)
            items = []
        return {"list": items, "page": pg}

    # ---------------- 播放（4K 解析引擎） ----------------
    # 解析接口失效特征（停运告别页 / 域名待售 / 跳转劫持页）
    _DEAD_WORDS = ("\u540e\u4f1a\u65e0\u671f", "for sale", "domain is for sale",
                   "\u57df\u540d\u51fa\u552e", "\u6c5f\u6e56\u8def\u8fdc",
                   "urldance", "aipages.dev", "under construction", "coming soon",
                   "\u5df2\u505c\u6b62", "\u505c\u6b62\u670d\u52a1")

    def _parser_ok(self, parser):
        """探测解析接口可用性并缓存（避免每次播放都试错）。
        判定： HTTP 200 + 页面够长 + 不含失效特征词 + 未跳转到无关域。"""
        key = "p:" + parser
        if key in self._probe:
            return self._probe[key]
        ok = False
        try:
            hd = {"User-Agent": self.parser_ua, "Referer": REF}
            if self.cookie:
                hd["Cookie"] = self.cookie
            u = parser + _q("https://v.qq.com/x/cover/mzc00200in5doq6.html")
            st, txt = _http("GET", u, headers=hd, timeout=6)
            txt = txt or ""
            low = txt.lower()
            if st and len(txt) > 500:
                ok = True
                # 失效特征词
                for w in self._DEAD_WORDS:
                    if w.lower() in low:
                        ok = False
                        break
                # 播放器骨架（无任何播放器特征则判失效）
                if ok:
                    skel = ("player" in low or "m3u8" in low or
                            "iframe" in low or "<video" in low or
                            "id=\"a1\"" in low or "parse" in low or
                            "dplayer" in low or "tcplayer" in low)
                    if not skel:
                        ok = False
        except Exception:
            ok = False
        self._probe[key] = ok
        _log("parser", parser, ok)
        return ok

    def _pick_parser(self, page_url):
        """按可用性择优挑一个解析接口，返回 解析地址+编码后的播放页。
        用户显式指定的 force_parser 直接信任、不做探测。"""
        if not self.use_parser:
            return ""
        if self.force_parser:
            return self.force_parser + _q(page_url)
        for p in self.parsers:
            if self._parser_ok(p):
                return p + _q(page_url)
        return ""

    def playerContent(self, flag, id, vipFlags):
        page_url = str(id or "")
        # 通道0：mp4/m3u8 直链直接播
        if re.search(r"\.(m3u8|mp4|flv|mkv|webm)(\?|$)", page_url):
            return {"parse": 0, "jx": 0, "url": page_url,
                    "header": {"User-Agent": UA_PC, "Referer": REF}}
        # 通道1：外挂解析（4K 优化：择优 + 高码率 UA + Cookie）
        jx = self._pick_parser(page_url)
        if jx:
            hd = {"User-Agent": self.parser_ua, "Referer": REF}
            if self.cookie:
                hd["Cookie"] = self.cookie
            return {"parse": 1, "jx": 1, "url": jx, "header": hd}
        # 通道2：播放页兜底
        return {"parse": 1, "jx": 1, "url": page_url,
                "header": {"User-Agent": UA_PC, "Referer": REF}}

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4|flv|mkv|webm)(\?|$)", str(url or "")))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        return None
