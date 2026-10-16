# -*- coding: utf-8 -*-
"""
哔哩哔哩 TVBox Python 爬虫（独立版）v1
======================================
站点：https://www.bilibili.com/
资源：番剧 / 国创 / 电影 / 电视剧 / 纪录片 / 综艺（6 大 PGC 分类全量）
      + 搜索支持 UGC 稿件（视频）
筛选：每个分类均带【真实可用】的可选筛选（类型 / 地区 / 年份 / 风格 /
      状态 / 版权 / 付费 / 季度 / 出品 …），定义从 pgc/season/index/condition 动态解析。
      排序维度：播放量 / 更新时间 / 上映时间 / 最高评分。

【接口说明】
  分类列表：api.bilibili.com/pgc/season/index/result
    - season_type: 1=番剧 4=国创 2=电影 5=电视剧 3=纪录片 7=综艺
    - 关键参数（缺一不可）：type / area / year / style / order
    - 筛选定义：api.bilibili.com/pgc/season/index/condition?season_type=N&type=1&...
  搜索：api.bilibili.com/x/web-interface/wbi/search/all/v2（WBI 签名）
  详情：api.bilibili.com/pgc/view/web/season（PGC）/ x/web-interface/view（UGC）
  播放：api.bilibili.com/pgc/player/web/playurl（PGC 直链）
        api.bilibili.com/x/player/wbi/playurl（UGC 直链，需 WBI 签名）

【播放 · 4K 解析引擎】
  B站是【唯一能直链播放】的平台（PGC + UGC），也是唯一能真 4K 的平台。
  - 直链请求【账号可用的最高清晰度】（qn=127 自动降级），并自动挑选分辨率最高的视频流
  - 关键：未登录时 B站只给 480P（尽管接口声明支持 4K）；
    填顶部 COOKIE="SESSDATA=xxx" 或 extend {"cookie":"SESSDATA=xxx"} 即可解锁 4K/1080P+
  - 直链失败时回退外挂解析池 / 播放页
  - 想用自己的 4K 解析：改顶部 PARSERS，或写进 extend {"parser":"https://你的解析/?url="}

接口约定：类名 Spider，playerContent 的 header 必须是 dict。
"""

import re
import json
import time
import hashlib
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
REF = "https://www.bilibili.com/"
DEBUG = False

# PGC 分类（season_type -> 名称）
CLASSES = [("1", "番剧"), ("4", "国创"), ("2", "电影"),
           ("5", "电视剧"), ("3", "纪录片"), ("7", "综艺")]

# 通用请求头（UGC view/playurl 缺 Origin/Accept 会被拦）
BL_H = {"Referer": REF,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.bilibili.com"}

# WBI 签名重排表
WBI_TAB = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9,
           42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1,
           60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52]

# 排序（order 参数）
ORDERS = [("", "综合排序"), ("0", "播放量"), ("2", "更新时间"),
          ("6", "上映时间"), ("4", "最高评分")]

# ================================================================
#  4K 解析引擎（统一配置）
#  说明：
#   B站是唯一能【直链播放】的平台，且是唯一能真 4K 的平台。
#   但实测：未登录时 B站只给 480P（accept 声明支持 120=4K，实际只回 480P），
#         【带登录 Cookie（SESSDATA）才能取到 4K/1080P+】。
#   故这里：
#     - B站直链请求【最高清晰度】（qn=127 即 8K 档，接口自动降级到可用最高）
#     - 支持 Cookie 注入（填 SESSDATA 即可解锁 4K）
#     - 直链失败时回退解析池
#   想用自己的解析：改 PARSERS / SESSDATA，或写进 extend：
#        {"cookie":"SESSDATA=xxx", "parser":"https://你的解析/?url="}
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
USE_PARSER = True
# 解析通道 UA（移动端更易命中高码率）
PARSER_UA = "Mozilla/5.0 (Linux; Android 12; Pixel 6 Build/SQ3A.220705.004; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/106.0.5249.126 Mobile Safari/537.36"
# B站登录 Cookie（填 SESSDATA=xxx 可解锁 4K / 1080P+；留空则最高约 480P）
COOKIE = ""
# 期望清晰度码（B站 qn）：127=8K, 120=4K, 116=1080P60, 112=1080P+, 80=1080P, 64=720P
# 设为 127 时接口会自动降级到当前账号可用的最高清晰度
QN = 127


def _log(*a):
    if DEBUG:
        try:
            print("[B站]", " ".join([str(x) for x in a]))
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
        return json.loads(txt[i:])
    except Exception:
        try:
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
        return "哔哩哔哩"

    def init(self, extend=""):
        self.host = ""
        self.headers = {"User-Agent": UA_PC}
        self.ext = extend or ""
        self._probe = {}
        self._lock = threading.Lock()
        # —— 4K 解析配置（extend 可覆盖顶部常量）——
        self.parsers = list(PARSERS)
        self.use_parser = USE_PARSER
        self.parser_ua = PARSER_UA
        self.cookie = COOKIE
        self.qn = QN
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
                if j.get("qn"):
                    self.qn = _int(j.get("qn"), QN)
        except Exception:
            pass
        # B站接口通用头（带上 Cookie 以解锁高清）
        self.bl_h = dict(BL_H)
        if self.cookie:
            self.bl_h["Cookie"] = self.cookie

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

    # ---------------- WBI 签名 ----------------
    def _mixin(self):
        ck = "mixin"
        if ck in self._probe:
            return self._probe[ck]
        st, txt = _http("GET", "https://api.bilibili.com/x/web-interface/nav", headers=self.bl_h)
        j = _jload(txt)
        wi = (j.get("data") or {}).get("wbi_img") or {}
        img_key = (wi.get("img_url") or "").rsplit("/", 1)[-1].split(".")[0]
        sub_key = (wi.get("sub_url") or "").rsplit("/", 1)[-1].split(".")[0]
        orig = img_key + sub_key
        mx = "".join(orig[WBI_TAB[i]] for i in range(32)) if len(orig) >= 32 else ""
        self._probe[ck] = mx
        return mx

    def _signed(self, base, params):
        mixin = self._mixin()
        if not mixin:
            return ""
        p = dict(params)
        q = "&".join("%s=%s" % (k, _q(str(p[k]).replace("!", "").replace("'", "")
                                      .replace("(", "").replace(")", "")))
                     for k in sorted(p))
        w_rid = hashlib.md5((q + mixin).encode("utf-8")).hexdigest()
        return "%s?%s&w_rid=%s" % (base, q, w_rid)

    # ---------------- 搜索（PGC + UGC） ----------------
    def _search(self, key, pg):
        u = self._signed("https://api.bilibili.com/x/web-interface/wbi/search/all/v2",
                         {"keyword": key, "page": _int(pg, 1), "page_size": 20,
                          "platform": "pc", "wts": int(time.time())})
        if not u:
            return []
        st, txt = _http("GET", u, headers=self.bl_h)
        j = _jload(txt)
        if j.get("code") != 0:
            _log("search code", j.get("code"), j.get("message"))
            return []
        out, seen = [], set()
        for cat in ((j.get("data") or {}).get("result") or []):
            rt = cat.get("result_type")
            if rt in ("media_bangumi", "media_ft"):
                for v in (cat.get("data") or []):
                    sid = v.get("season_id")
                    title = _clean(v.get("title"))
                    if not sid or not title or "预告" in title:
                        continue
                    k = "bl|%s" % sid
                    if k in seen:
                        continue
                    seen.add(k)
                    out.append(self._mk_vod(k, title, v.get("cover") or "",
                                            remarks=_clean(v.get("index_show") or ""),
                                            type_name="哔哩哔哩"))
            elif rt == "video":
                for v in (cat.get("data") or []):
                    bvid = v.get("bvid")
                    title = _clean(v.get("title"))
                    if not bvid or not title:
                        continue
                    k = "blu|%s" % bvid
                    if k in seen:
                        continue
                    seen.add(k)
                    pic = v.get("pic") or ""
                    if pic.startswith("//"):
                        pic = "https:" + pic
                    rem = v.get("duration") or ""
                    au = _clean(v.get("author") or "")
                    if au:
                        rem = (au + "\t" + rem).strip()
                    out.append(self._mk_vod(k, title, pic, remarks=rem,
                                            actor=au, type_name="哔哩哔哩"))
        return out

    # ---------------- 筛选（condition 动态解析） ----------------
    def _filter_defs(self, stype):
        ck = "f:%s" % stype
        if ck in self._probe:
            return self._probe[ck]
        u = ("https://api.bilibili.com/pgc/season/index/condition?season_type=%s&type=1&area=-1&year=-1&style=-1"
             % stype)
        st, txt = _http("GET", u, headers=self.bl_h)
        j = _jload(txt)
        flt = (j.get("data") or {}).get("filter") or []
        out = []
        for g in flt:
            field = g.get("field")
            nm = g.get("name") or field
            if not field:
                continue
            opts = []
            for v in (g.get("values") or []):
                kw = v.get("keyword")
                nmv = v.get("name") or ""
                if kw in (None, "", "-1"):
                    continue                      # 跳过"全部"占位
                opts.append((nmv, str(kw)))
            if opts:
                out.append((field, nm, opts))
        self._probe[ck] = out
        return out

    def _gen_filters(self, stype):
        out = []
        for field, nm, opts in self._filter_defs(stype):
            vals = [{"n": "全部", "v": ""}]
            for label, val in opts:
                vals.append({"n": label, "v": "%s\t%s" % (field, val)})
            if len(vals) > 1:
                out.append({"key": field, "name": nm, "value": vals})
        # 排序维度（order）
        ov = [{"n": "综合排序", "v": ""}]
        for k, label in ORDERS[1:]:
            ov.append({"n": label, "v": "order\t%s" % k})
        out.insert(0, {"key": "order", "name": "排序", "value": ov})
        return out

    # ---------------- 分类 ----------------
    def _cate(self, stype, pg, ext=None):
        ext = ext or {}
        area, year, style, order = "-1", "-1", "-1", ""
        for k, v in ext.items():
            v = str(v or "").strip()
            if not v:
                continue
            if "\t" in v:
                kk, vv = v.split("\t", 1)
            else:
                kk, vv = k, v
            if kk == "area":
                area = vv
            elif kk == "year" or kk == "release_date":
                year = vv
            elif kk == "style" or kk == "style_id":
                style = vv
            elif kk == "order":
                order = vv
        u = ("https://api.bilibili.com/pgc/season/index/result?season_type=%s&page=%s&pagesize=20"
             "&type=1&area=%s&year=%s&style=%s&order=%s"
             % (stype, pg or 1, _q(area), _q(year), _q(style), order))
        st, txt = _http("GET", u, headers=self.bl_h)
        j = _jload(txt)
        lst = (j.get("data") or {}).get("list") or []
        out = []
        for v in lst:
            sid = v.get("season_id")
            title = _clean(v.get("title"))
            if not sid or not title or "预告" in title:
                continue
            rem = v.get("index_show") or ""
            if v.get("order") and len(str(v.get("order"))) == 10:
                rem = v.get("index_show") or rem
            out.append(self._mk_vod("bl|%s" % sid, title, v.get("cover") or "",
                                    remarks=rem, type_name="哔哩哔哩"))
        return out

    # ---------------- 详情 ----------------
    def _detail(self, sid):
        u = "https://api.bilibili.com/pgc/view/web/season?season_id=" + str(sid)
        st, txt = _http("GET", u, headers=self.bl_h)
        r = (_jload(txt).get("result") or {})
        if not r:
            return None
        pub = r.get("publish") or {}
        ne = r.get("new_ep") or {}
        areas = r.get("areas") or []
        rating = r.get("rating") or {}
        stat = r.get("stat") or {}
        status = "弹幕: %s 点赞: %s 追番: %s" % (
            stat.get("danmakus", ""), stat.get("likes", ""), stat.get("favorites", ""))
        score = ("评分: %s %s" % (rating.get("score"), rating.get("subtitle", ""))) if rating else "暂无评分"
        vod = self._mk_vod("bl|%s" % sid, _clean(r.get("title")), r.get("cover") or "",
                           remarks=ne.get("desc") or "", year=(pub.get("pub_time") or "")[:4],
                           area=(areas[0].get("name") if areas and isinstance(areas[0], dict) else ""),
                           actor=status, director=score, content=r.get("evaluate") or "",
                           type_name=r.get("share_sub_title") or "哔哩哔哩")
        direct, pages = [], []
        for ep in (r.get("episodes") or []):
            t = _clean(ep.get("title")) or ""
            badge = ep.get("badge") or ""
            if "预告" in t or "预告" in badge:
                continue
            name = (t + " " + _clean(ep.get("long_title") or "")).strip()
            ep_id, cid, link = ep.get("ep_id"), ep.get("cid"), ep.get("link") or ""
            if ep_id and cid:
                direct.append("%s$blplay|%s|%s|%s" % (name, ep_id, cid, link))
            if link:
                pages.append("%s$%s" % (name, link))
        vod["vod_play_from"] = "$$$".join([x for x in (["B站直链"] if direct else []) + (["B站播放页"] if pages else [])])
        vod["vod_play_url"] = "$$$".join([x for x in (["#".join(direct)] if direct else []) + (["#".join(pages)] if pages else [])])
        return vod

    def _ugc_detail(self, bvid):
        u = "https://api.bilibili.com/x/web-interface/view?bvid=" + str(bvid)
        st, txt = _http("GET", u, headers=self.bl_h)
        d = (_jload(txt).get("data") or {})
        if not d:
            return None
        pages = d.get("pages") or []
        pic = d.get("pic") or ""
        if pic.startswith("//"):
            pic = "https:" + pic
        es = d.get("stat") or {}
        status = "播放: %s 弹幕: %s 点赞: %s" % (es.get("view", ""), es.get("danmaku", ""), es.get("like", ""))
        vod = self._mk_vod("blu|%s" % bvid, _clean(d.get("title")), pic,
                           remarks=("共%sP" % len(pages)) if pages else "",
                           year=time.strftime("%Y", time.localtime(_int(d.get("pubdate"), 0))) if d.get("pubdate") else "",
                           actor=_clean((d.get("owner") or {}).get("name") or ""),
                           director=status, content=_clean(d.get("desc") or ""),
                           type_name=_clean(d.get("tname") or "哔哩哔哩"))
        direct, pages_url = [], []
        for i, p in enumerate(pages):
            cid = p.get("cid")
            if not cid:
                continue
            part = _clean(p.get("part")) or ("P%d" % (i + 1))
            direct.append("%s$blugc|%s|%s" % (part, bvid, cid))
            pages_url.append("%s$https://www.bilibili.com/video/%s?p=%s" % (part, bvid, i + 1))
        fl = []
        if direct:
            fl.append("B站直链")
        if pages_url:
            fl.append("B站播放页")
        vod["vod_play_from"] = "$$$".join(fl)
        vod["vod_play_url"] = "$$$".join([x for x in (["#".join(direct)] if direct else []) +
                                          (["#".join(pages_url)] if pages_url else [])])
        return vod

    # ---------------- 直链播放（4K 优化） ----------------
    def _pick_dash(self, dash):
        """从 dash 里挑【分辨率最高】的视频流地址。"""
        vs = (dash or {}).get("video") or []
        if not vs:
            return ""
        def h(v):
            return _int(v.get("height"), 0) * 100000 + _int(v.get("width"), 0)
        try:
            best = sorted(vs, key=h, reverse=True)[0]
        except Exception:
            best = vs[0]
        # 优先 baseUrl，其次 backupUrl
        u = best.get("baseUrl") or ""
        if not u and best.get("backupUrl"):
            bu = best.get("backupUrl")
            u = bu[0] if isinstance(bu, list) and bu else ""
        return u

    def _play_pgc(self, ep_id, cid):
        """PGC 播放直链：请求账号可用的【最高清晰度】（qn=127 自动降级）。"""
        u = ("https://api.bilibili.com/pgc/player/web/playurl?ep_id=%s&cid=%s&fnval=16&qn=%d"
             "&fnver=0&fourk=1&session=&device=pc&platform=web&otype=json"
             % (ep_id, cid, self.qn))
        st, txt = _http("GET", u, headers=self.bl_h)
        res = (_jload(txt).get("result") or {})
        if res.get("dash"):
            u2 = self._pick_dash(res.get("dash"))
            if u2:
                return u2
        if res.get("durl"):
            return res["durl"][0].get("url") or ""
        return ""

    def _play_ugc(self, bvid, cid):
        """UGC 播放直链：请求账号可用的【最高清晰度】（qn=127 自动降级）。"""
        u = self._signed("https://api.bilibili.com/x/player/wbi/playurl",
                         {"bvid": bvid, "cid": cid, "fnval": 16, "fnver": 0,
                          "fourk": 1, "qn": self.qn, "platform": "pc", "wts": int(time.time())})
        if not u:
            return ""
        st, txt = _http("GET", u, headers=self.bl_h)
        r = (_jload(txt).get("data") or {})
        if r.get("dash"):
            u2 = self._pick_dash(r.get("dash"))
            if u2:
                return u2
        if r.get("durl"):
            return r["durl"][0].get("url") or ""
        return ""

    # ---------------- TVBox 接口 ----------------
    def homeContent(self, filter):
        classes = [{"type_id": cid, "type_name": name} for cid, name in CLASSES]
        filters = {}
        if filter:
            lock = threading.Lock()

            def run(stype):
                try:
                    r = self._gen_filters(stype)
                    if r:
                        with lock:
                            filters[stype] = r
                except Exception as e:
                    _log("flt ERR", stype, e)

            ts = [threading.Thread(target=run, args=(c,)) for c, _ in CLASSES]
            for t in ts:
                t.setDaemon(True)
                t.start()
            for t in ts:
                t.join(12)
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        out = []
        lock = threading.Lock()

        def run(stype):
            try:
                r = self._cate(stype, 1)
                if r:
                    with lock:
                        out.extend(r[:20])
            except Exception:
                pass

        ts = [threading.Thread(target=run, args=(c,)) for c, _ in CLASSES]
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
                s = str(vid)
                if s.startswith("blu|"):
                    vod = self._ugc_detail(s.split("|", 1)[1])
                else:
                    vod = self._detail(s.split("|", 1)[1] if "|" in s else s)
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

    # ---------------- 播放（4K 解析引擎：B站直链优先） ----------------
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
        """按可用性择优挑一个解析接口。用户显式指定的 force_parser 直接信任。"""
        if not self.use_parser:
            return ""
        if self.force_parser:
            return self.force_parser + _q(page_url)
        for p in self.parsers:
            if self._parser_ok(p):
                return p + _q(page_url)
        return ""

    def _bl_direct_hdr(self):
        """B站直链的请求头（带上 Cookie，播放器才能正常拉流）"""
        hd = {"User-Agent": UA_PC, "Referer": REF}
        if self.cookie:
            hd["Cookie"] = self.cookie
        return hd

    def playerContent(self, flag, id, vipFlags):
        id = str(id or "")
        # 通道1：B站 PGC 直链（4K 优先）
        if id.startswith("blplay|"):
            parts = id.split("|")
            ep_id, cid = parts[1], parts[2]
            link = parts[3] if len(parts) > 3 else ""
            url = self._play_pgc(ep_id, cid)
            if url:
                return {"parse": 0, "jx": 0, "url": url, "header": self._bl_direct_hdr()}
            if link:
                return {"parse": 1, "jx": 1, "url": link, "header": self._bl_direct_hdr()}
            return {"parse": 1, "jx": 1, "url": "", "header": self._bl_direct_hdr()}
        # 通道1：B站 UGC 直链（4K 优先）
        if id.startswith("blugc|"):
            parts = id.split("|")
            bvid, cid = parts[1], parts[2]
            url = self._play_ugc(bvid, cid)
            if url:
                return {"parse": 0, "jx": 0, "url": url, "header": self._bl_direct_hdr()}
            return {"parse": 1, "jx": 1, "url": "https://www.bilibili.com/video/%s" % bvid,
                    "header": self._bl_direct_hdr()}
        # 通道0：http 直链
        if re.search(r"\.(m3u8|mp4|flv|mkv|webm)(\?|$)", id):
            return {"parse": 0, "jx": 0, "url": id, "header": self._bl_direct_hdr()}
        # 通道2：外挂解析兜底
        jx = self._pick_parser(id)
        if jx:
            hd = {"User-Agent": self.parser_ua, "Referer": REF}
            if self.cookie:
                hd["Cookie"] = self.cookie
            return {"parse": 1, "jx": 1, "url": jx, "header": hd}
        return {"parse": 1, "jx": 1, "url": id,
                "header": {"User-Agent": UA_PC, "Referer": REF}}

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4|flv|mkv|webm)(\?|$)", str(url or "")))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        return None
