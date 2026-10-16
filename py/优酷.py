# -*- coding: utf-8 -*-
# ================================================================
#  优酷 TVBox / 影视仓 Spider 源（独立版 · 全分类 + 可选筛选 + 4K 解析池）
# ================================================================
#  接口来源（2026-10 实测）：
#    · 分类列表  https://www.youku.com/category/data          （动态筛选定义 + 列表）
#    · 详情      https://openapi.youku.com/v2/shows/show.json  （开放 API，稳定）
#    · 剧集      https://openapi.youku.com/v2/shows/videos.json
#    · 搜索      https://search.youku.com/api/search
# ================================================================
#  【播放 · 4K 解析引擎】
#   1) 优酷 PC 直链接口已加密（__ottreqid / 签名），必须走解析通道。
#   2) 解析池内置一组【实测可用】接口；探测时自动识别
#      「停运告别页 / 域名待售页 / 劫持跳转页」等失效特征，失效接口自动跳过。
#   3) 想用自己的 4K 解析：改下面 PARSERS，或在 TVBox extend 里传：
#        {"parser":"https://你的解析/?url=", "cookie":"xxx", "use_parser":true}
#   4) 解析站生命周期普遍很短（数周~数月），失效属常态；
#      失效时优先替换 PARSERS 里靠前的接口，或改用 extend 自备解析。
# ================================================================
#  已知限制（如实说明）：
#   · 未登录状态下分类【只服务第 1 页】（page>=2 返回空），已做正确收敛。
#   · 搜索接口返回的 UGC 片段较多，已过滤为结构化影视条目。
# ================================================================

import sys
import json
import re
import time
import random

try:
    from urllib.parse import quote, quote_plus, urlencode
except Exception:
    from urllib import quote, quote_plus, urlencode

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except Exception:
    from urllib2 import Request, urlopen, HTTPError, URLError

try:
    import requests
except Exception:
    requests = None

DEBUG = False

# ================================================================
#  基础常量
# ================================================================
UA_PC = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
UA_M = ("Mozilla/5.0 (Linux; Android 12; Pixel 6 Build/SQ3A.220705.004; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/106.0.5249.126 "
        "Mobile Safari/537.36")
REF = "https://www.youku.com/"

# 优酷开放 API 的公开 client_id（网页端公开值）
CLIENT_ID = "53e6cc67237fc59a"

# 分类目录（type_id -> 显示名；type_id 同时作为接口 category / type 参数）
CLASSES = [
    ("电视剧", "电视剧"),
    ("电影", "电影"),
    ("综艺", "综艺"),
    ("动漫", "动漫"),
    ("纪录片", "纪录片"),
    ("少儿", "少儿"),
    ("文化", "文化"),
    ("亲子", "亲子"),
    ("教育", "教育"),
    ("搞笑", "搞笑"),
    ("生活", "生活"),
    ("体育", "体育"),
]

# ================================================================
#  4K 解析引擎（统一配置）
# ================================================================
#   说明：
#    1) 解析站的清晰度由【服务端】决定，客户端 py 只能"择优挑选 + 正确传参"，
#       无法强制某个站返回 4K。故这里给一组【实测可用】的接口池，按可用性择优。
#    2) 想用自己的 4K 解析：改下面的 PARSERS，或写进 TVBox 自定义 extend：
#         {"parser": "https://你的解析/?url=", "cookie": "xxx"}
#    3) 优酷 PC 直连接口已签名，故必须走解析通道。
#    4) 【自动淘汰】探测会识别"停运告别页/域名待售页/劫持跳转页"，失效接口自动跳过。
#    5) 解析站生命周期短（数周~数月），失效是常态——优先替换靠前接口或用 extend 自备。
# ================================================================
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
# 是否启用解析通道（False 则只走播放页）
USE_PARSER = True
# 解析请求头：部分接口靠 UA/Referer 决定清晰度，这里用移动端 UA 更易命中高码率
PARSER_UA = UA_M
# 可选 Cookie（部分解析站/平台靠登录态解锁 4K）。留空则不发送。
COOKIE = ""


def _log(*a):
    if DEBUG:
        try:
            print("[优酷]", " ".join([str(x) for x in a]))
        except Exception:
            pass


def _q(s):
    """URL 编码（保留 :// 与常见安全字符，兼容 Jython2）"""
    try:
        return quote(str(s or ""), safe="")
    except Exception:
        return quote(str(s or ""))


def _http(method, url, headers=None, body=None, timeout=15):
    """统一 HTTP 请求：优先 requests，退化 urllib（兼容 Jython/Py2/Py3）"""
    hdrs = {"User-Agent": UA_PC, "Accept": "*/*", "Referer": REF}
    if headers:
        hdrs.update(headers)

    if requests is not None:
        try:
            if method.upper() == "POST":
                r = requests.post(url, headers=hdrs, data=body, timeout=timeout, verify=False)
            else:
                r = requests.get(url, headers=hdrs, timeout=timeout, verify=False)
            return r.status_code, r.text
        except Exception:
            pass

    # urllib 兜底
    try:
        req = Request(url, data=body, headers=hdrs)
        resp = urlopen(req, timeout=timeout)
        code = resp.getcode() if hasattr(resp, "getcode") else 200
        raw = resp.read()
        try:
            txt = raw.decode("utf-8", "ignore")
        except Exception:
            txt = raw
        return code, txt
    except HTTPError as e:
        try:
            return e.code, e.read().decode("utf-8", "ignore")
        except Exception:
            return e.code, ""
    except Exception as e:
        _log("http err", e)
        return 0, ""


def _jload(txt):
    try:
        return json.loads(txt)
    except Exception:
        # 容错：_INITIAL_DATA__ 里存在 undefined 等非法 JSON 片段
        try:
            fixed = (txt or "").replace(":undefined", ":null").replace("undefined", "null")
            return json.loads(fixed)
        except Exception:
            return {}


def _s(v, d=""):
    if v is None:
        return d
    try:
        return str(v)
    except Exception:
        return d


def _pick(d, *keys):
    """从 dict 里按顺序取第一个非空值"""
    if not isinstance(d, dict):
        return None
    for k in keys:
        if d.get(k) not in (None, "", [], {}):
            return d.get(k)
    return None


def _img(u):
    """补全封面 URL"""
    u = _s(u)
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    return u


class Spider(object):
    """优酷 Spider"""

    def __init__(self):
        self.extend = ""
        # 解析引擎配置
        self.parsers = list(PARSERS)
        self.use_parser = USE_PARSER
        self.parser_ua = PARSER_UA
        self.cookie = COOKIE
        self.force_parser = ""
        self._probe = {}
        # 通用配置
        self.hdr = {"User-Agent": UA_PC, "Referer": REF}

    # ---------------- 生命周期 ----------------
    def init(self, extend=""):
        self.extend = extend or ""
        if self.extend:
            try:
                cfg = _jload(self.extend) if isinstance(self.extend, str) else self.extend
                if isinstance(cfg, dict):
                    # 解析池自定义
                    pp = cfg.get("parser") or cfg.get("jx")
                    if pp:
                        self.force_parser = _s(pp)
                    ps = cfg.get("parsers")
                    if isinstance(ps, list) and ps:
                        self.parsers = [_s(x) for x in ps if x]
                    if cfg.get("cookie") is not None and _s(cfg.get("cookie")):
                        self.cookie = _s(cfg.get("cookie"))
                        self.hdr["Cookie"] = self.cookie
                    if cfg.get("use_parser") is not None:
                        self.use_parser = bool(cfg.get("use_parser"))
                    if cfg.get("ua"):
                        self.parser_ua = _s(cfg.get("ua"))
            except Exception as e:
                _log("init err", e)

    def getName(self):
        return "优酷"

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4|flv|mkv|webm)(\?|$)", _s(url)))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        return None

    # ---------------- 分类接口 ----------------
    def _cat_url(self, cate, page, extra):
        """构造分类列表请求 URL。"""
        params = {"category": cate, "type": cate}
        if extra:
            for k, v in extra.items():
                if v not in (None, "", []):
                    params[k] = v
        u = ("https://www.youku.com/category/data?optionRefresh=1&pageNo=%d&params=%s"
             % (int(page or 1), _q(json.dumps(params, ensure_ascii=False))))
        return u

    def _fetch_cat(self, cate, page, extra):
        """返回 (listData, filterDims, hasMore)"""
        u = self._cat_url(cate, page, extra)
        st, txt = _http("GET", u, headers=self.hdr, timeout=15)
        if not st or not txt:
            return [], [], False
        d = _jload(txt)
        fd = ((d.get("data") or {}).get("filterData") or {})
        return (fd.get("listData") or [],
                ((fd.get("filter") or {}).get("filterData") or []),
                bool(fd.get("hasMore")))

    def _parse_filter(self, dims):
        """把接口返回的筛选定义转成 TVBox filters 结构。"""
        filters = []
        for dim in dims or []:
            subs = dim.get("subFilter") or []
            if not subs:
                continue
            ftype = None
            values = []
            for s in subs:
                ft = _s(s.get("filterType"))
                if ft and not ftype:
                    ftype = ft
                title = _s(s.get("title"))
                val = s.get("value")
                val = "" if val in (None, "NON") else _s(val)
                if title == "" or title.startswith("全部") or title == "综合排序":
                    val = ""
                values.append({"n": title, "v": val})
            if not ftype or not values:
                continue
            # 首项保证是「全部」
            if values[0].get("v") != "":
                values.insert(0, {"n": "全部", "v": ""})
            filters.append({"key": ftype, "name": ftype, "value": values})
        # 中文显示名映射（key -> 友好名）
        NAME_MAP = {
            "type": "类型", "main_area": "地区", "tags": "剧情", "year": "年份",
            "status": "规格", "pay_type": "付费", "sort": "排序", "theatre": "剧场",
            "tag_label_name": "标签",
        }
        for f in filters:
            f["name"] = NAME_MAP.get(f["key"], f["key"])
        return filters

    # ---------------- 内容接口 ----------------
    def homeContent(self, filter=False):
        classes = [{"type_id": tid, "type_name": name} for tid, name in CLASSES]
        out = {"class": classes}
        # 筛选按分类首次请求时的返回动态生成
        if filter:
            # 用第一个分类的筛选做示例；各分类 lebel 结构不同，逐个补充
            filters = {}
            for tid, _ in CLASSES:
                _, dims, _ = self._fetch_cat(tid, 1, None)
                filters[tid] = self._parse_filter(dims)
            out["filters"] = filters
        return out

    def homeVideoContent(self):
        items, _, _ = self._fetch_cat("电视剧", 1, None)
        return {"list": [self._vod(it) for it in items]}

    def _vod(self, it):
        """列表条目 -> TVBox vod 结构"""
        link = _s(_pick(it, "videoLink", "link", "url"))
        vid = self._extract_sid(link) or _s(_pick(it, "showId", "id"))
        title = _s(_pick(it, "title", "name"))
        return {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": _img(_pick(it, "img", "poster", "thumbnail")),
            "vod_remarks": _s(_pick(it, "summary", "rightTagText", "subTitle")),
        }

    def _extract_sid(self, link):
        """从各种链接里抽出 show id（优酷 id 是 20 位十六进制）"""
        link = _s(link)
        m = re.search(r"id_([0-9a-fA-F]{16,})\.html", link)
        if m:
            return m.group(1)
        m = re.search(r"/(?:show|nextstage)[/_]([0-9a-fA-F]{16,})", link)
        if m:
            return m.group(1)
        m = re.search(r"showId=([0-9a-fA-F]{16,})", link)
        if m:
            return m.group(1)
        return ""

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        # 未登录时接口仅服务第 1 页
        if pg > 1:
            return {"list": [], "page": pg, "pagecount": pg, "limit": 24, "total": 0}
        extra = {}
        if isinstance(extend, dict):
            for k, v in extend.items():
                if v not in (None, "", []):
                    extra[k] = v
        items, _, has_more = self._fetch_cat(tid, 1, extra)
        lst = [self._vod(it) for it in items]
        pagecount = 1
        if has_more:
            pagecount = 9999  # 理论可翻页，但未登录实际拿不到第 2 页
        return {"list": lst, "page": pg, "pagecount": pagecount,
                "limit": 24, "total": 24 if has_more else len(lst)}

    def detailContent(self, ids):
        sid = ""
        if ids:
            sid = _s(ids[0])
        sid = self._extract_sid(sid) or sid
        if not sid:
            return {"list": []}

        # 详情（开放 API）
        du = ("https://openapi.youku.com/v2/shows/show.json?client_id=%s&show_id=%s"
              % (CLIENT_ID, sid))
        st, txt = _http("GET", du, headers=self.hdr, timeout=15)
        info = _jload(txt) if st else {}

        # 剧集列表（开放 API）
        eu = ("https://openapi.youku.com/v2/shows/videos.json?client_id=%s&show_id=%s&count=100"
              % (CLIENT_ID, sid))
        st2, txt2 = _http("GET", eu, headers=self.hdr, timeout=15)
        eps = (_jload(txt2).get("videos") or []) if st2 else []

        name = _s(_pick(info, "name", "title")) or sid
        # 演员 / 导演
        actors = []
        attr = info.get("attr") or {}
        for a in (attr.get("director") or []):
            nm = _s(a.get("name"))
            if nm:
                actors.append("导演:" + nm)
        for a in (attr.get("performer") or attr.get("actor") or []):
            nm = _s(a.get("name"))
            if nm:
                actors.append(nm)
        if not actors:
            actors = []
        # 更多信息
        extra_bits = []
        area = _s(info.get("area"))
        genre = _s(info.get("genre"))
        year = _s(info.get("published"))[:4]
        if year:
            extra_bits.append(year)
        if area:
            extra_bits.append(area)
        if genre:
            extra_bits.append(genre)
        ep_cnt = _s(info.get("episode_count"))
        if ep_cnt:
            extra_bits.append(ep_cnt + "集")

        # 播放列表：一集一集
        play_urls = []
        for e in eps:
            t = _s(_pick(e, "title", "name")) or ("第%s集" % _s(e.get("seq")))
            lk = _s(_pick(e, "link", "url"))
            # 取出 video id 作为播放标识
            m = re.search(r"id_([A-Za-z0-9=+/]+)\.html", lk)
            vid = m.group(1) if m else lk
            if vid:
                play_urls.append("%s$%s" % (t, vid))
        if not play_urls:
            # 兜底：用详情里的 play_link
            pl = _s(_pick(info, "play_link"))
            m = re.search(r"id_([A-Za-z0-9=+/]+)\.html", pl)
            if m:
                play_urls.append("%s$%s" % (name, m.group(1)))

        vod = {
            "vod_id": sid,
            "vod_name": name,
            "vod_pic": _img(_pick(info, "poster_large", "poster", "thumbnail_large")),
            "vod_year": year,
            "vod_area": area,
            "vod_actor": " / ".join(actors[:12]),
            "vod_director": " / ".join([_s(a.get("name")) for a in (attr.get("director") or [])]),
            "vod_content": _s(_pick(info, "description", "subtitle")),
            "vod_remarks": _s(_pick(info, "update_notice")) or (" · ".join(extra_bits)),
            "vod_play_from": "优酷",
            "vod_play_url": "#".join(play_urls),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        kw = _s(key)
        u = ("https://search.youku.com/api/search?keyword=%s&page=%d"
             % (_q(kw), int(pg or 1)))
        st, txt = _http("GET", u, headers=self.hdr, timeout=15)
        lst = []
        seen = {}
        if st and txt:
            d = _jload(txt)
            for c in (d.get("pageComponentList") or []):
                cd = c.get("commonData") or {}
                sid = _s(cd.get("showId") or cd.get("realShowId"))
                if not sid:
                    continue
                # 标题在 titleDTO.displayName；无则退化到 displayName / title
                title = ""
                td = cd.get("titleDTO")
                if isinstance(td, dict):
                    title = _s(_pick(td, "displayName", "title", "name"))
                if not title:
                    title = _s(_pick(cd, "displayName", "title", "showName", "name"))
                if not title:
                    continue
                # 去重（同一 showId 在多个组件里重复出现）
                if sid in seen:
                    continue
                # 封面：commonData.sourceImg / posterDTO
                pic = _s(_pick(cd, "sourceImg", "posterImg", "img", "thumbnail"))
                if not pic:
                    pd = cd.get("posterDTO")
                    if isinstance(pd, dict):
                        pic = _s(_pick(pd, "sourceImg", "img", "pic"))
                seen[sid] = 1
                lst.append({
                    "vod_id": sid,
                    "vod_name": title,
                    "vod_pic": _img(pic),
                    "vod_remarks": _s(_pick(cd, "feature", "stripeBottom")),
                })
        return {"list": lst, "page": int(pg or 1)}

    # ---------------- 播放（4K 解析引擎） ----------------
    # 解析接口失效特征（停运告别页 / 域名待售 / 跳转劫持页）
    _DEAD_WORDS = ("\u540e\u4f1a\u65e0\u671f", "for sale", "domain is for sale",
                   "\u57df\u540d\u51fa\u552e", "\u6c5f\u6e56\u8def\u8fdc",
                   "urldance", "aipages.dev", "under construction", "coming soon",
                   "\u5df2\u505c\u6b62", "\u505c\u6b62\u670d\u52a1")

    def _parser_ok(self, parser):
        """探测解析接口可用性并缓存（避免每次播放都试错）。
        判定： HTTP 200 + 页面够长 + 不含失效特征词 + 有播放器骨架。"""
        key = "p:" + parser
        if key in self._probe:
            return self._probe[key]
        ok = False
        try:
            hd = {"User-Agent": self.parser_ua, "Referer": REF}
            if self.cookie:
                hd["Cookie"] = self.cookie
            u = parser + _q("https://v.youku.com/v_show/id_XNTk0NjA0MzYw.html")
            st, txt = _http("GET", u, headers=hd, timeout=6)
            txt = txt or ""
            low = txt.lower()
            if st and len(txt) > 500:
                ok = True
                for w in self._DEAD_WORDS:
                    if w.lower() in low:
                        ok = False
                        break
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

    def playerContent(self, flag, id, vipFlags):
        vid = _s(id or "")
        # 已是直链，直接播
        if re.search(r"\.(m3u8|mp4|flv|mkv|webm)(\?|$)", vid):
            return {"parse": 0, "jx": 0, "url": vid,
                    "header": {"User-Agent": UA_PC, "Referer": REF,
                               "Origin": "https://www.youku.com"}}
        # 拼优酷播放页
        if vid.startswith("http"):
            page_url = vid
        else:
            page_url = "https://v.youku.com/v_show/id_%s.html" % vid
        # 解析通道（4K 优化：择优 + 移动端 UA + Cookie）
        jx = self._pick_parser(page_url)
        if jx:
            hd = {"User-Agent": self.parser_ua, "Referer": REF}
            if self.cookie:
                hd["Cookie"] = self.cookie
            return {"parse": 1, "jx": 1, "url": jx, "header": hd}
        # 兜底：交给壳子解析播放页
        return {"parse": 1, "jx": 1, "url": page_url,
                "header": {"User-Agent": UA_PC, "Referer": REF}}
