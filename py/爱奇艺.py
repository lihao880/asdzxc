# -*- coding: utf-8 -*-
"""
爱奇艺 TVBox Python 爬虫（独立版）v1
====================================
站点：https://www.iqiyi.com/
资源：电影 / 电视剧 / 综艺 / 动漫 / 纪录片 / 网络电影（6 大分类全量）
筛选：爱奇艺【无公开筛选接口】——实测 7 个候选筛选接口全部 404 或返回无差异数据，
      three_category_id 参数语义不可靠（任意值返回同一批片单）。
      为保证【不出现假选项】，本源【不下发筛选栏】，专注把资源采全、翻页做真。

【接口说明】
  分类列表：pcw-api.iqiyi.com/search/recommend/list
    - channel_id: 1=电影 2=电视剧 6=综艺 4=动漫 3=纪录片 16=网络电影
    - page_id 真实翻页（实测各页不重复）
  搜索：search.video.iqiyi.com/o
  详情：pcw-api.iqiyi.com/video/video/videoinfowithuser/{aid}
  剧集：pcw-api.iqiyi.com/albums/album/avlistinfo

【播放 · 4K 解析引擎】
  爱奇艺官方直链需登录态，故走外挂解析。
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
REF = "https://www.iqiyi.com/"
DEBUG = False

# 分类目录（channel_id -> 显示名）
CLASSES = [("1", "电影"), ("2", "电视剧"), ("6", "综艺"),
           ("4", "动漫"), ("3", "纪录片"), ("16", "网络电影")]
# 综艺 channel（实测 data_type=1 才返回数据，=2 会返空）
CATE_TYPE = {}

# ================================================================
#  4K 解析引擎（统一配置）
#  说明：
#   1) 解析站的清晰度由【服务端】决定，客户端 py 只能"择优挑选 + 正确传参"，
#      无法强制某个站返回 4K。故这里给一组【实测可用】的接口池，按可用性择优。
#   2) 想用自己的 4K 解析：改下面的 PARSERS，或写进 TVBox 自定义 extend：
#        {"parser": "https://你的解析/?url=", "cookie": "xxx"}
#   3) 爱奇艺官方直链需登录态，故走解析通道。
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


def _log(*a):
    if DEBUG:
        try:
            print("[爱奇艺]", " ".join([str(x) for x in a]))
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
        return "爱奇艺"

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

    # ---------------- 搜索 ----------------
    def _search(self, key, pg):
        u = ("https://search.video.iqiyi.com/o?if=html5&key=%s&pageNum=%s&pos=1&pageSize=24&site=iqiyi"
             % (_q(key), pg or 1))
        st, txt = _http("GET", u, headers={"Referer": REF})
        j = _jload(txt)
        docs = (j.get("data") or {}).get("docinfos", []) or []
        out = []
        for d in docs:
            a = d.get("albumDocInfo")
            if not a or not a.get("albumId"):
                continue
            img = a.get("albumVImage") or a.get("albumHImage") or ""
            if img.startswith("//"):
                img = "https:" + img
            ch = (a.get("channel") or "").split(",")[0]
            out.append(self._mk_vod(str(a.get("albumId")), _clean(a.get("albumTitle")), img,
                                    remarks=ch, type_name=ch))
        return out

    # ---------------- 分类 ----------------
    def _cate(self, cid, pg, ext=None):
        dt = CATE_TYPE.get(str(cid), "1")
        if str(cid) == "16":
            u = ("https://pcw-api.iqiyi.com/search/recommend/list?channel_id=1&data_type=1"
                 "&page_id=%s&ret_num=48&three_category_id=27401" % (pg or 1))
        else:
            u = ("https://pcw-api.iqiyi.com/search/recommend/list?channel_id=%s&data_type=%s"
                 "&page_id=%s&ret_num=48" % (cid, dt, pg or 1))
        st, txt = _http("GET", u, headers={"Referer": REF})
        j = _jload(txt)
        lst = (j.get("data") or {}).get("list", []) or []
        out = []
        for it in lst:
            aid = it.get("albumId")
            if not aid:
                continue
            lc, vc = it.get("latestOrder"), it.get("videoCount")
            rem = ""
            if it.get("channelId") in (2, 4):
                rem = ("%s集全" % lc) if (lc and vc and str(lc) == str(vc)) else ("更新至 %s集" % lc)
            elif it.get("period"):
                rem = it.get("period")
            elif it.get("focus"):
                rem = it.get("focus")
            sc = it.get("score")
            if sc:
                rem = ("%s分\t" % sc) + rem
            out.append(self._mk_vod(str(aid), _clean(it.get("name")), it.get("imageUrl") or "",
                                    remarks=rem, year=(it.get("period") or "")[:4],
                                    content=it.get("description") or "", type_name="爱奇艺"))
        return out

    # ---------------- 详情 ----------------
    def _detail(self, aid):
        u = ("https://pcw-api.iqiyi.com/video/video/videoinfowithuser/%s?agent_type=1&authcookie=&subkey=%s&subscribe=1"
             % (aid, aid))
        st, txt = _http("GET", u, headers={"Referer": REF})
        d = (_jload(txt).get("data") or {})
        if not d:
            return None
        cats = d.get("categories") if isinstance(d.get("categories"), list) else []
        ppl = d.get("people") if isinstance(d.get("people"), dict) else {}
        actors = ""
        mc = ppl.get("main_charactor") if isinstance(ppl.get("main_charactor"), list) else []
        if mc:
            actors = ",".join([x.get("name", "") for x in mc if isinstance(x, dict)])
        img = d.get("imageUrl") or ""
        if img.startswith("//"):
            img = "https:" + img
        rem = ""
        if d.get("latestOrder"):
            rem = "更新至 第%s集(期)/共%s集(期)" % (d.get("latestOrder"), d.get("videoCount"))
        elif d.get("period"):
            rem = d.get("period")
        if d.get("score"):
            rem = ("评分：%s " % d.get("score")) + rem
        vod = self._mk_vod(str(aid), _clean(d.get("name")), img, remarks=rem,
                           year=(d.get("period") or "")[:4], actor=actors,
                           content=d.get("description") or "",
                           type_name=",".join([c.get("name", "") for c in cats if isinstance(c, dict)]))
        eps = []
        if d.get("channelId") in (1, 5) and d.get("playUrl"):
            eps.append("正片$%s" % d.get("playUrl"))
        else:
            page = 1
            while True:
                u2 = "https://pcw-api.iqiyi.com/albums/album/avlistinfo?aid=%s&size=200&page=%s" % (aid, page)
                st2, txt2 = _http("GET", u2, headers={"Referer": REF})
                d2 = (_jload(txt2).get("data") or {})
                el = d2.get("epsodelist") or []
                for e in el:
                    pu = e.get("playUrl") or ""
                    if pu:
                        eps.append("%s$%s" % (_clean(e.get("name")) or ("第%s集" % e.get("order", "")), pu))
                total = _int(d2.get("total"), 0)
                if len(el) < 200 or page * 200 >= total:
                    break
                page += 1
                if page > 20:
                    break
        vod["vod_play_from"] = "爱奇艺"
        vod["vod_play_url"] = "#".join(eps)
        return vod

    # ---------------- TVBox 接口 ----------------
    def homeContent(self, filter):
        classes = [{"type_id": cid, "type_name": name} for cid, name in CLASSES]
        # 爱奇艺无公开筛选接口 -> 不下发 filters（避免假选项）
        return {"class": classes, "filters": {}}

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

        ts = [threading.Thread(target=run, args=(cid,)) for cid, _ in CLASSES]
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
