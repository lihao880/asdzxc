#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# TVBox / FongMi Python 爬虫 · 影桥 (qiaoying)
# ------------------------------------------------------------
# 站点  : 影桥 —— 私有影库面板（TMDB 元数据 + 网盘直链）
#         面板本体是 Web 应用，资源在个人网盘（UC/百度/移动云盘…）里
# 接口  : POST /api/fwrex/{home/run,search,item,play}?token=XXX
#         home/run  {pluginId,rowId,startIndex,limit} → items[]
#         search    {wd,limit}                        → items[]
#         item      {itemId}                          → versions[]
#         play      {ref}                             → {urls,header,playVia,container}
# 注意  : 条目坐标格式 tmdb_<id>_<movie|tv>[_s<季>_e<集>]
#         剧集 item 必须带季集，否则 versions 为空 —— 所以要探测集数
# 集数  : 面板没有"列分集"接口, /search 的 itemId 里带集号可用来定上限,
#         但服务端限流(约 4 请求/秒), 200 集以上的剧靠 BUDGET 兜底截断
# 注意  : 无 f-string / 兼容 py2+py3 / FongMi(base.spider) 与旧 TVBox 双体系
# 播放  : 面板按 ref 逐条签发, 网盘 Cookie 会整批过期 -> 必须实测再给
# 版本  : build 20261019-3
# ============================================================
import sys
import re
import json
import time
import hashlib

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

try:
    from concurrent.futures import ThreadPoolExecutor as _Pool
    from concurrent.futures import wait as _wait
    from concurrent.futures import FIRST_COMPLETED as _FIRST
except ImportError:
    _Pool = None
    _wait = None
    _FIRST = None


# ============ 常量自保护层 ============
# 面板地址与令牌不存明文, 运行时解出。
# 算法: hex -> 逐字节 ^ keystream ^ MASK; keystream = sha256(口令|计数)
_KP_ = "yq-20261019"
_KMASK_ = 0x3C


def _ks_(n):
    out = bytearray()
    pw = _KP_.encode("utf-8")
    i = 0
    while len(out) < n:
        h = hashlib.sha256(pw + b"|" + str(i).encode("ascii")).digest()
        out.extend(bytearray(h))
        i += 1
    return out


def _E(s):
    """密文 -> 明文 (只依赖 hashlib)"""
    if isinstance(s, (bytes, bytearray)):
        s = bytes(s).decode("ascii", "ignore")
    try:
        raw = bytearray.fromhex(s)
    except Exception:
        return ""
    k = _ks_(len(raw))
    buf = bytearray()
    for i in range(len(raw)):
        buf.append((raw[i] ^ k[i] ^ _KMASK_) & 0xFF)
    try:
        return bytes(buf).decode("utf-8", "ignore")
    except Exception:
        return str(buf)


# ============ 面板常量 (已混淆, 填自己的值见下方说明) ============
# 换面板/换令牌: 用「密钥混淆工具.py」重新生成后替换这两行
PANEL = _E("ce7d6e89680cc8c164cd673f3e9a2b1d4d3dcb9c84ca577265dc4f")
TOKEN = _E("943c2c9b7e5781da20c2306576c2741b027e9b8a8ad90b3e318617134c76ef8d725fa1ebd3e6e77aa75fab344023b789")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
PLAY_UA = ("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36")

IS_PY3 = sys.version_info[0] >= 3
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
        return bytes(x).decode("utf-8", "ignore") if IS_PY3 else str(x)
    return _unicode(x)


def _num(v, d=0):
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return d


def _with_hint(iid, title):
    """把片名挂到 vod_id 后面, 供详情页跨进程取用

    只在「剧集坐标」(tmdb_x_tv) 上加; 裸坐标和已是单集坐标的不动。
    片名里若含 "||" 会破坏解析, 这种极少见, 直接放弃附加。
    """
    t = _ustr(title).strip()
    if not t or "||" in t:
        return iid
    if re.match(r"^tmdb_\d+_(tv|movie)$", iid):
        return iid + "||" + t
    return iid


# ============ 首页行 (与面板 widget.js 对齐) ============
ROWS = [
    ("now_playing", u"正在热映"),
    ("trending", u"趋势"),
    ("popular", u"备受欢迎"),
    ("top_rated", u"高分内容"),
    ("categories", u"分类"),
    ("networks", u"播出平台"),
    ("companies", u"出品公司"),
    ("list", u"片单"),
    ("regional_series", u"近一月地区剧集"),
    ("regional_variety", u"近一月地区综艺"),
    ("random_picks", u"随机推荐"),
]

# 分类 -> 用哪个首页行当数据源 (面板没有真正的分类接口, 用行代替)
CLASSES = [
    ["now_playing", u"正在热映"],
    ["trending", u"趋势"],
    ["popular", u"备受欢迎"],
    ["top_rated", u"高分内容"],
    ["regional_series", u"地区剧集"],
    ["regional_variety", u"地区综艺"],
    ["list", u"片单"],
    ["random_picks", u"随机推荐"],
]


# ============ 爬虫 ============
class Spider(_BaseSpider):

    # 详情页探测集数的时间预算(秒)。面板服务端限流, 大剧天生探不完,
    # 宁可早点交出已探到的集, 也别让客户端等到超时。
    BUDGET = 55

    def getName(self):
        return u"影桥"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = _ustr(extend)
        self.panel, self.token = self._read_cfg()
        self._cache = {}      # itemId -> versions
        self.destroy()

    def destroy(self):
        pass

    # ---------- 配置 ----------
    def _read_cfg(self):
        """优先级: init(extend) JSON > 内置密文"""
        panel, token = PANEL, TOKEN
        ext = self.extend
        if ext:
            try:
                o = json.loads(ext) if ext.strip().startswith("{") else {}
            except Exception:
                o = {}
            p = _ustr(o.get("panel"))
            t = _ustr(o.get("token"))
            if p:
                panel = p
            if t:
                token = t
        return panel.rstrip("/"), token

    def _ok(self):
        return bool(self.panel and self.token)

    # ---------- HTTP ----------
    def _api(self, route, body=None, timeout=40):
        if not self._ok():
            return {}
        q = "?token=" + _urlpar.quote(self.token) if IS_PY3 \
            else "?token=" + _urlpar.quote(self.token.encode("utf-8"))
        url = self.panel + "/api/fwrex" + route + q
        h = {"User-Agent": UA, "Accept": "application/json",
             "Content-Type": "application/json",
             "Referer": self.panel + "/", "Origin": self.panel}
        data = json.dumps(body or {}).encode("utf-8")
        for attempt in range(2):
            try:
                if _rq is not None:
                    r = _rq.post(url, headers=h, data=data,
                                 timeout=timeout, verify=False)
                    raw = r.content
                else:
                    req = _urlreq.Request(url, data=data, headers=h)
                    resp = _urlreq.urlopen(req, timeout=timeout)
                    try:
                        raw = resp.read()
                    finally:
                        try:
                            resp.close()
                        except Exception:
                            pass
                if isinstance(raw, (bytes, bytearray)):
                    raw = bytes(raw).decode("utf-8", "ignore")
                if not raw:
                    time.sleep(0.4)
                    continue
                # 面板被限流/网关出错时会回 HTML 而不是 JSON, 直接 loads 会抛
                raw = raw.strip()
                if not raw.startswith("{") and not raw.startswith("["):
                    if attempt == 0:
                        time.sleep(1.2)
                    continue
                return json.loads(raw)
            except Exception:
                if attempt == 0:
                    time.sleep(0.5)
        return {}

    # ---------- 卡片 -> vod ----------
    def _to_vod(self, it):
        if not isinstance(it, dict):
            return None
        iid = _ustr(it.get("id"))
        if not iid:
            return None
        title = _ustr(it.get("title"))
        if not title:
            return None
        pic = _ustr(it.get("poster"))
        # 顺手记住 片名/封面, 供详情页复用 (剧集搜索的 title 是「第N集」, 不算)
        try:
            mb = re.match(r"^(tmdb_\d+)_(tv|movie)", iid)
            if mb:
                self._remember(mb.group(1) + "_" + mb.group(2), title, pic)
        except Exception:
            pass
        is_tv = _ustr(it.get("type")).lower() == "tv"
        yr = _ustr(it.get("year"))
        rating = it.get("rating")
        remarks = []
        if yr:
            remarks.append(yr)
        remarks.append(u"剧集" if is_tv else u"电影")
        try:
            if rating:
                remarks.append(u"★%.1f" % float(rating))
        except (ValueError, TypeError):
            pass
        return {
            # 片名塞进 vod_id 后缀: TVBox 从列表点进详情常是另一个进程,
            # 内存缓存带不过去, 但 vod_id 是原样透传的, 这是最可靠的通道。
            "vod_id": _with_hint(iid, title),
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": u"·".join(remarks),
            "vod_year": yr,
        }

    # ---------- 首页 ----------
    def homeContent(self, filter=1):
        classes = [{"type_id": c[0], "type_name": c[1]} for c in CLASSES]
        return {"class": classes}

    def homeVideoContent(self):
        """首页取前几行拼一起"""
        items, seen = [], set()
        for rid, _n in ROWS[:5]:
            o = self._api("/home/run", {"pluginId": "tmdb", "rowId": rid,
                                        "startIndex": 0, "limit": 18})
            for it in (o.get("items") or []):
                v = self._to_vod(it)
                if v and v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    items.append(v)
        return {"list": items}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg=1, filter=1, extend=None):
        page = max(1, _num(pg, 1))
        rid = _ustr(tid) or "now_playing"
        limit = 30
        o = self._api("/home/run", {"pluginId": "tmdb", "rowId": rid,
                                    "startIndex": (page - 1) * limit,
                                    "limit": limit})
        items = []
        for it in (o.get("items") or []):
            v = self._to_vod(it)
            if v:
                items.append(v)
        total = _num(o.get("total"), 0)
        has_more = bool(items) and (len(items) >= limit or
                                    (total and page * limit < total))
        return {"list": items, "page": page,
                "pagecount": page + 1 if has_more else page,
                "limit": limit, "total": total or len(items)}

    # ---------- 集数探测 ----------
    def _versions_of(self, item_id):
        """取某坐标的版本清单 (带内存缓存)"""
        if item_id in self._cache:
            return self._cache[item_id]
        o = self._api("/item", {"itemId": item_id}, timeout=30)
        vs = o.get("versions") or []
        self._cache[item_id] = vs
        return vs

    def _index_of(self, base, title=""):
        """给某部剧建「集号索引 + 元数据」, 一次 /search 全解决

        面板没有"列分集"接口, 但 /search 返回的每条 itemId 里**带集号**。
        实测: 搜「嫁金钗」8 条就是 8 集, 搜「炼气十万年」50 条集号最高 214。
        所以 /search 的价值不是"拿全集"(它每部最多给 50 条, 是抽样的),
        而是**快速定上限**:
          没有它, 216 集的剧要发 216 次 /item (约 50s)
          有它,   知道上限是 214 后, 补探量能压到 30 次以内

        同时按 TMDB id 精确过滤 —— 搜「炼气十万年」会带回纪录片和花絮,
        只有 itemId 里 id 段与 base 一致的才算同一部。

        返回 (上限集号, 已知命中的集集合, 片名, 封面)
        """
        cache = self.__dict__.setdefault("_idx", {})
        if base in cache:
            return cache[base]
        res = (0, set(), u"", u"")
        mm = re.match(r"^(tmdb_\d+)_(tv|movie)$", base or "")
        if not mm:
            return res
        want_id = mm.group(1)                 # tmdb_220850
        want_kind = mm.group(2)
        wd = _ustr(title)
        if not wd:
            # 没有片名时无从搜索, 只能靠盲探
            cache[base] = res
            return res
        o = self._api("/search", {"wd": wd, "limit": 50}, timeout=30)
        hit = set()
        top = 0
        best_name = u""
        best_pic = u""
        for it in (o.get("items") or []):
            iid = _ustr(it.get("itemId") or it.get("id"))
            if not iid.startswith(want_id + "_" + want_kind):
                continue                      # 别的片子, 同名也不行
            nm = _ustr(it.get("title"))
            pic = _ustr(it.get("poster"))
            if nm and not re.match(r"^第\s*\d+\s*集$", nm):
                if not best_name or len(nm) > len(best_name):
                    best_name = nm
            if pic and not best_pic:
                best_pic = pic
            em = re.search(r"_s(\d+)_e(\d+)$", iid)
            if not em:
                continue
            if _num(em.group(1), 0) != 1:     # 只按第一季的集号定上限
                continue
            e = _num(em.group(2), 0)
            if e > 0:
                hit.add(e)
                top = max(top, e)
        res = (top, hit, best_name or wd, best_pic)
        cache[base] = res
        return res

    def _probe(self, base, title="", max_season=8, batch=24, max_ep=500,
               top=-1, known=None, budget=0):
        """探测一部剧到底有哪些季、哪些集

        面板的 item 接口**必须给到季集坐标**才返回版本, 没有"列分集"的接口,
        所以集数只能一集一集探。为使探测量可控, 分三段:

          ① 用 /search 定上限 (这是关键: 216 集的剧不用发 216 次请求)
          ② 在上限范围内逐批补探, 命中即止
          ③ 没有片名 / search 也查不到时, 退回纯粗扫跳点

        实测坑:
          - 集与集之间**会有洞** (E163 空但 E164 有), 所以不能"一遇空就停"
          - 面板服务端限流, 并发加上去单请求延迟跟着涨, 天花板约 4 请求/秒
            所以 200 集以上的剧天生就要 50s+, budget 用来兜底别让客户端干等

        返回 {season: [ep, ...]}
        """
        if top < 0:
            top = self._index_of(base, title)[0]
        deadline = time.time() + budget if budget else 0
        found = {}
        season = 1
        while season <= max_season:
            if not self._versions_of("%s_s%d_e1" % (base, season)):
                break                      # 连 E1 都没有 -> 这季不存在, 停
            eps = self._scan_season(base, season, batch, max_ep,
                                    top if season == 1 else 0, deadline)
            if eps:
                found[season] = eps
            season += 1
        return found

    def _scan_season(self, base, season, batch, max_ep, top=0, deadline=0):
        """单季扫描

        top > 0 时 (search 给出了上限): 在 [1, top] 里逐批补探, 扫完即止。
        top = 0 时 (纯盲探): 先跳点定上限, 再补齐到 上限+2批。
        deadline 到了就立刻收手, 把已有结果交出去。
        """
        have = set([1])
        if top:
            end = min(top, max_ep)
            cur = 2
            while cur <= end:
                if deadline and time.time() > deadline:
                    break
                # 批大小跟着剩余预算走: 剩得多就大批快跑, 快没时间就小批收尾,
                # 这样总耗时能贴着预算, 不会因为最后一大批拖出一倍时间。
                bs = batch
                if deadline:
                    left = deadline - time.time()
                    if left <= 0:
                        break
                    bs = min(batch, max(6, int(left * 3)))
                rng = [e for e in range(cur, min(cur + bs, end + 1))
                       if e not in have]
                if rng:
                    got = [e for e, n in self._probe_many(base, season, rng,
                                                         deadline) if n]
                    have.update(got)
                cur += bs
            return sorted(have)
        # ---- 盲探: ① 跳点定上限 ----
        probe = list(range(1, max_ep + 1, batch))
        last_hit = 1
        for e, n in self._probe_many(base, season, probe, deadline):
            if n:
                have.add(e)
                last_hit = e
        # ---- ② 逐批补齐 (超出跳点上限 2 批, 防上限卡在跳点之间) ----
        end = min(last_hit + batch * 2, max_ep)
        cur = 2
        miss = 0
        while cur <= end:
            if deadline and time.time() > deadline:
                break
            rng = [e for e in range(cur, min(cur + batch, end + 1))
                   if e not in have]
            if rng:
                got = [e for e, n in self._probe_many(base, season, rng,
                                                         deadline) if n]
                if got:
                    have.update(got)
                    miss = 0
                else:
                    miss += len(rng)
            cur += batch
            if miss >= batch * 2 and cur > last_hit:
                break
        return sorted(have)

    def _probe_many(self, base, season, eps, deadline=0):
        """批量试探一集是否有版本

        并发实测: 面板单请求约 1.0s, 但 12 路并上跑久了一两个会拖尾,
        一批 24 个要等最慢的那个。改成**窗口式**: 同时最多 12 个在飞,
        谁回谁补, 这样没有"批次尾延迟"。

        (不用 ThreadPoolExecutor.map —— 它按输入顺序返回, 一个慢请求会
         堵住后面所有已完成的; 同理也不能用 submit 后按序 join)

        deadline 到了就不再补新请求, 已有的拿完就走。
        """
        if not eps:
            return []
        todo = list(eps)
        out = {}
        if _Pool is None or len(todo) <= 1:
            for e in todo:
                out[e] = 1 if self._versions_of(
                    "%s_s%d_e%d" % (base, season, e)) else 0
            return [(e, out[e]) for e in todo]
        pool = None
        try:
            pool = _Pool(max_workers=12)
            futs = {}
            it = iter(todo)
            # 先灌满窗口
            for e in it:
                futs[pool.submit(self._versions_of,
                                 "%s_s%d_e%d" % (base, season, e))] = e
                if len(futs) >= 12:
                    break
            while futs:
                if deadline and time.time() > deadline:
                    break                     # 硬超时: 不等在飞的请求了
                done, _pending = _wait(list(futs.keys()),
                                       return_when=_FIRST)
                for f in done:
                    e = futs.pop(f, None)
                    if e is None:
                        continue
                    try:
                        out[e] = 1 if f.result() else 0
                    except Exception:
                        out[e] = 0
                    ne = next(it, None)           # 补位
                    if ne is not None:
                        futs[pool.submit(
                            self._versions_of,
                            "%s_s%d_e%d" % (base, season, ne))] = ne
            return [(e, out.get(e, 0)) for e in todo]
        except Exception:
            return [(e, out.get(e, 0)) for e in todo]
        finally:
            # 关键: 不能用 with 或 shutdown(wait=True) —— 那样必须等在飞请求
            # 全部结束, 预算就等于白设了
            if pool is not None:
                try:
                    pool.shutdown(wait=False)
                except Exception:
                    pass

    # ---------- 详情 ----------
    def detailContent(self, ids=None):
        if not ids:
            return {"list": []}
        vid = _ustr(ids[0]).strip()
        if not vid:
            return {"list": []}
        try:
            return {"list": [self._build_detail(vid)]}
        except Exception:
            return {"list": []}

    def _build_detail(self, vid):
        vod = {
            "vod_id": vid,
            "vod_name": vid,
            "vod_pic": "",
            "vod_remarks": "",
            "vod_content": u"影桥私有影库。",
            "vod_play_from": u"影桥",
            "vod_play_url": "",
        }
        # vod_id 可能带 "||片名" 后缀 (见 _with_hint), 用于跨进程传递片名
        hint = u""
        if "||" in vid:
            vid, hint = vid.split("||", 1)
            hint = _ustr(hint).strip()
        m = re.match(r"^(tmdb_\d+)_(tv|movie)(?:_s(\d+)_e(\d+))?$", vid)
        if not m:
            return vod
        base = m.group(1) + "_" + m.group(2)   # tmdb_xxx_tv / tmdb_xxx_movie
        kind = m.group(2)
        cur_s = _num(m.group(3), 0)
        cur_e = _num(m.group(4), 0)
        # 一次 /search: 片名 + 封面 + 集数上限, 三个都从这儿来
        top, known, name, pic = self._index_of(base, hint)
        title = name or hint or self._meta_of(base, kind)[0]
        if title:
            vod["vod_name"] = title
        if pic:
            vod["vod_pic"] = pic
        tid = m.group(1).replace("tmdb_", "")
        # ---- 电影: 一条正片 ----
        if kind == "movie":
            vod["vod_play_url"] = u"正片$" + base
            vod["vod_remarks"] = u"电影"
            vod["vod_content"] = u"影桥私有影库 · 电影 · TMDB %s。" % tid
            return vod
        # ---- 剧集: 探季集 ----
        # 预算 55s: 面板单请求约 1s 且**服务端限流** (并发加上去延迟跟着涨,
        # 实测天花板约 4/s), 所以 200 集以上的大剧老实讲探不完。
        # 超预算就先把已探到的集交出去, 不能让客户端干等到超时。
        seasons = self._probe(base, title, top=top, known=known,
                              budget=self.BUDGET)
        if not seasons:
            # 探不到就退化成「当前这一集」, 至少能播
            if cur_s and cur_e:
                vod["vod_play_url"] = u"第%d集$%s_s%d_e%d" % (cur_e, base,
                                                              cur_s, cur_e)
                vod["vod_remarks"] = u"仅此集入库"
            else:
                vod["vod_play_url"] = u"第1集$%s_s1_e1" % base
                vod["vod_remarks"] = u"探测不到分集"
            return vod
        groups, names = [], []
        for sn in sorted(seasons.keys()):
            eps = seasons[sn]
            cells = []
            for e in eps:
                cells.append(u"第%d集$%s_s%d_e%d" % (e, base, sn, e))
            if cells:
                groups.append(u"#".join(cells))
                names.append(u"影桥S%d" % sn if len(seasons) > 1 else u"影桥")
        vod["vod_play_url"] = u"$$$".join(groups)
        vod["vod_play_from"] = u"$$$".join(names)
        total = sum(len(v) for v in seasons.values())
        # 探到的可能少于 search 给的上限 -> 说明超预算截断了, 备注里讲清楚
        capped = bool(top) and len(seasons.get(1) or []) < top
        if capped:
            vod["vod_remarks"] = u"已入库%d集(共%d集)" % (total, top)
        else:
            vod["vod_remarks"] = u"共%d集" % total if total else u""
        vod["vod_content"] = (u"影桥私有影库 · 剧集 · TMDB %s · 已入库 %d 集。"
                              % (tid, total))
        return vod

    # ---------- 元数据 (片名/封面) ----------
    def _meta_of(self, base, kind=""):
        """按 base 坐标取片名与封面

        TVBox 里从"搜索结果点进详情"是**两次独立调用**, 常常不在同一进程,
        内存里 _titles 缓存基本指望不上。所以真正可靠的路子是 /search 反查
        (_index_of 干的活), 这里只是:
          ① 先吃本进程里攒下的缓存 (首页/搜索同进程时能省一次请求)
          ② 没有再走 /search 反查
        """
        cache = self.__dict__.get("_meta")
        if cache is None:
            cache = {}
            self.__dict__["_meta"] = cache
        key = base + "|" + kind
        if key in cache:
            return cache[key]
        tmap = self.__dict__.get("_titles") or {}
        if base in tmap:
            cache[key] = tmap[base]
            return tmap[base]
        idx = self._index_of(base)          # (top, hit, name, pic)
        res = (_ustr(idx[2]), _ustr(idx[3]))
        cache[key] = res
        return res

    def _remember(self, base, title, pic):
        """把首页/搜索里见到的 片名+封面 记下来, 供同进程内的详情页复用"""
        tmap = self.__dict__.get("_titles")
        if tmap is None:
            tmap = {}
            self.__dict__["_titles"] = tmap
        if not base:
            return
        cur = tmap.get(base)
        title = _ustr(title)
        # 「第 N 集」这类不是作品名, 不要覆盖已有的好标题
        bad = bool(re.match(r"^第\s*\d+\s*集$", title))
        if cur:
            ct, cp = cur
            if bad:
                return
            if ct and not _ustr(pic):
                return
        tmap[base] = (title, _ustr(pic))

    # ---------- 播放 ----------
    # 各网盘/通道的可用性信誉 (实测得出, 见笔记 27.11)
    # 面板是按 **ref**(即单个文件) 签发直链的, 而网盘那边的 Cookie 会整批过期,
    # 所以"哪个能播"是成片成片地失效, 不是单条随机。实测成功率:
    #   百度无限 72% | UC无限 57% | UC原画 0% | 夸克转码 0% | 百度原画 0%
    # 而它们的体积恰恰是 UC原画/夸克最大 —— 所以按体积排序必然踩雷。
    SITE_RANK = [
        (u"百度无限", 100),
        (u"UC無限", 80),
        (u"UC无限", 80),
        (u"百度", 60),
        (u"UC", 40),
        (u"夸克", 10),
    ]

    # 探测播放地址时, 只读这么多字节来判断真伪就够了
    PROBE_BYTES = 1024
    # 单次播放最多实测几个版本。每个版本一次请求, 太多会把播放拖慢;
    # 按网盘分组轮转后, 通常前 1~2 个就能命中, 6 是给极端情况留的余量。
    PROBE_MAX = 6
    # 两次实测之间的间隔(秒)。不留间隔会被面板限流, 见 _probe_all 注释。
    PROBE_GAP = 0.8
    # 一次播放里"验证片源"总共最多花多久。全部失效的条目否则会一路试到底,
    # 实测能拖 30s+, 播放器早报超时了。到点就放弃并如实报片源失效。
    PROBE_BUDGET = 15

    def _site_rank(self, v):
        """给版本打一个"该先试谁"的分

        打分 = 网盘信誉 * 10 + 画质(体积)归一化
        信誉是主导项: 宁可要一个能播的 6G mp4, 也不要一个放不出来的 10G mkv
        """
        site = _ustr(v.get("site"))
        base = 20
        for name, sc in self.SITE_RANK:
            if name and name in site:
                base = sc
                break
        # 体积只做同档内的微调, 不能翻盘
        try:
            size = _num(v.get("size"), 0)
        except Exception:
            size = 0
        return base * 1000 + min(size // (100 * 1024 * 1024), 99)

    def _probe_url(self, url, header):
        """实测这个播放地址是不是真的能出流

        失败形态都见过:
          - 面板转发失败 -> Cloudflare 的 502 HTML 页
          - 网盘 Cookie 过期 -> 412 / 403 JSON
          - 地址能通但内容是错误页
        判据: 状态 200 且首字节像媒体(EBML/MP4/m3u8/TS/FLV)。
        """
        if not url:
            return False
        # 超时给 (3, 6): 网盘正常时建连 1~2s 就出头了。
        # 实测建连能拖到 6s+, 说明那条链路在排队或者本地出口慢 ——
        # 探测的目的是"快速排除坏源", 等太久不如直接判负, 交给并发去补。
        try:
            if _rq is not None:
                r = _rq.get(url, headers=header, timeout=(3, 6), verify=False,
                            stream=True, allow_redirects=True)
                try:
                    code = _num(r.status_code, 0)
                    if code != 200:
                        return False
                    head = b""
                    for chunk in r.iter_content(256):
                        head += chunk
                        if len(head) >= 12:
                            break
                finally:
                    try:
                        r.close()
                    except Exception:
                        pass
            else:
                req = _urlreq.Request(url, headers=header)
                resp = _urlreq.urlopen(req, timeout=6)
                try:
                    if _num(getattr(resp, "code", 200), 200) != 200:
                        return False
                    head = resp.read(12)
                finally:
                    try:
                        resp.close()
                    except Exception:
                        pass
            return self._looks_media(head)
        except Exception:
            return False

    def _looks_media(self, head):
        """首字节判媒体 (不用依赖 Content-Type, 网盘经常给 octet-stream)"""
        if not head:
            return False
        h = bytes(head) if not isinstance(head, bytes) else head
        if h[:4] == b"\x1aE\xdf\xa3":          # EBML: mkv / webm
            return True
        if len(h) >= 8 and h[4:8] == b"ftyp":  # MP4 / MOV
            return True
        if h[:4] == b"#EXT":                   # m3u8
            return True
        if h[:1] == b"\x47":                   # MPEG-TS
            return True
        if h[:3] == b"FLV":                    # FLV
            return True
        if h[:4] == b"\x00\x00\x00\x01" or h[:4] == b"\x00\x00\x00\x0c":
            return True                        # 裸 H.264/H.265
        return False

    def playerContent(self, flag, id, vipFlags=None):
        tok = _ustr(id).strip()
        if not tok:
            return {"parse": 0, "url": "", "header": {}}
        # 解析顺序有讲究: "||" 必须先剥, 否则会被 "|" 切坏
        if "||" in tok:
            tok = tok.split("||", 1)[0].strip()
        for sep in ("~~", "|", "$"):
            if sep in tok:
                tok = tok.rsplit(sep, 1)[-1].strip()
        # 只保留坐标本体 (tmdb_xxx_tv_s1_e1), 后面可能还挂了别的
        mc = re.search(r"(tmdb_\d+_(?:tv|movie)(?:_s\d+_e\d+)?)", tok)
        if mc:
            tok = mc.group(1)
        header = {"User-Agent": PLAY_UA, "Referer": self.panel + "/"}
        try:
            if tok.endswith("_none"):
                return {"parse": 0, "url": "", "header": {}}
            vs = self._versions_of(tok)
            if not vs:
                return {"parse": 0, "url": "", "header": {},
                        "format": u"该集无片源"}
            good = self._probe_all(vs, header, self.PROBE_MAX)
            if not good:
                # 实测全部失败。这里做个取舍:
                # 返回失效地址 -> App 显示"加载失败", 用户以为脚本坏了
                # 返回空      -> App 知道是片源问题, 提示更准
                # 选后者, 并用 format 说明是哪个网盘挂了
                sites = []
                for v in vs:
                    s = _ustr(v.get("site"))
                    if s and s not in sites:
                        sites.append(s)
                note = u"片源失效(%s)" % (u"/".join(sites[:3]) or u"未知")
                return {"parse": 0, "url": "", "header": {},
                        "format": note}
            # 注意: playerContent 的 url 只能是**一条**。
            # "$$$" 多线路是 vod_play_url 的语法, 放到这里播放器会把整串
            # 当成一个地址去请求, 直接失败。所以这里只给最优的那一条。
            return {"parse": 0, "url": good[0][1], "header": good[0][2]}
        except Exception:
            pass
        return {"parse": 0, "url": "", "header": {}}

    def _probe_all(self, vs, header, limit=0):
        """实测版本, 返回能播的那些 (按信誉排序)

        试过三种策略, 最后落在这个:

          ① 串行逐个试  -> 太慢, 6 个版本要 20~40s (建连本身 2.5~6.4s)
          ② 6 路全并发  -> 快, 但会**把面板打限流**: 同一网盘 6 个并发,
                          百度无限会返回 502, 明明单试是 200
          ③ 小批串行    -> 每批 2 个并发, 批内先到先得, 命中就停

        实测 ③ 最好: 大多数条目第一批就中 (约 3~5s), 也不会触发限流。
        """
        cache = self.__dict__.setdefault("_good", {})
        plan = self._plan_tries(vs)
        cap = min(limit or len(plan), len(plan), 6)
        picked = plan[:cap]
        if not picked:
            return []
        # 缓存直通: 上次验过能播的直接给, 不再发请求
        hit, todo = [], []
        for v in picked:
            ref = _ustr(v.get("ref"))
            r = cache.get(ref) if ref else None
            if r:
                hit.append((v, r[0], r[1]))
            elif ref:
                todo.append(v)
        if hit:
            return hit
        if not todo:
            return []

        good = []
        i = 0
        deadline = time.time() + self.PROBE_BUDGET
        while i < len(todo):
            v = todo[i]
            i += 1
            # 必须留间隔。实测面板对短时间内的密集请求会限流:
            # 不带间隔连发 4 个 -> 百度无限明明能放也回 502;
            # 插 0.8s -> 同一条目立刻恢复正常。
            # 所以宁可慢半秒, 也别把好好的片源误判成失效。
            if i > 1:
                time.sleep(self.PROBE_GAP)
            # 总时长兜底: 全部失效的条目会一路试到底, 实测能拖到 30s+。
            # 超过预算就别试了, 直接告诉用户片源失效, 比干等强。
            if time.time() > deadline:
                break
            r = self._one_ready(v, header, cache)
            if r:
                good = [(v, r[0], r[1])]
                break
        if not good:
            return []
        return good

    def _one_ready(self, v, header, cache):
        """单个版本: 取地址 + 实测, 通了返回 (url, header), 否则 None"""
        ref = _ustr(v.get("ref"))
        if not ref:
            return None
        if ref in cache:
            return cache[ref]
        vh = v.get("header")
        hh = dict(header)
        u = ""
        try:
            if isinstance(vh, dict) and vh:
                hh.update({_ustr(k): _ustr(x) for k, x in vh.items()})
                u = self._stream_url(ref)
            else:
                o = self._api("/play", {"ref": ref}, timeout=25)
                urls = o.get("urls") or []
                if not urls:
                    cache[ref] = None
                    return None
                ph = o.get("header")
                if isinstance(ph, dict):
                    hh.update({_ustr(k): _ustr(x) for k, x in ph.items()})
                u = _ustr(urls[0])
                if o.get("playVia") == "proxy":
                    u = self._stream_url(ref)
        except Exception:
            return None
        if not u:
            cache[ref] = None
            return None
        ok = self._probe_url(u, hh)
        res = (u, hh) if ok else None
        # 只缓存"成功"和"明确的失败"; 超时那种别写死, 下次可能就好了
        if ok:
            cache[ref] = res
        return res

    def _plan_tries(self, vs):
        """排一个"先试谁"的顺序, 关键是别让高信誉网盘排不上号

        踩过的坑: 「希望」有 17 个版本, UC 占 6 个且体积最大。
        单纯按信誉排序时, 前 4 个还是 UC(信誉 80) —— 只要 UC 那批挂了,
        珍贵的 4 次实测机会就全浪费在同一个网盘上, 永远轮不到百度。

        所以改成: **按网盘分组, 轮流各出代表** ——
        先每家的头名各试一次, 再第二轮。这样 2~3 次就能横向覆盖所有网盘。
        """
        buckets = {}
        order = []
        for v in vs:
            site = _ustr(v.get("site"))
            key = u"其他"
            for name, _sc in self.SITE_RANK:
                if name and name in site:
                    key = name
                    break
            if key not in buckets:
                buckets[key] = []
                order.append(key)
            buckets[key].append(v)
        # 组内按体积降序 (同网盘内挑画质好的)
        for k in buckets:
            buckets[k].sort(key=lambda v: -_num(v.get("size"), 0))
        # 组间按信誉降序
        order.sort(key=lambda k: -max([self._site_rank(v) // 1000
                                       for v in buckets[k]] or [0]))
        out = []
        i = 0
        while True:
            added = False
            for k in order:
                if i < len(buckets[k]):
                    out.append(buckets[k][i])
                    added = True
            if not added:
                break
            i += 1
        return out

    def _stream_url(self, ref):
        t = self.token
        if IS_PY3:
            return (self.panel + "/api/fwrex/stream?token="
                    + _urlpar.quote(t) + "&ref=" + _urlpar.quote(ref))
        return (self.panel + "/api/fwrex/stream?token="
                + _urlpar.quote(t.encode("utf-8")) + "&ref="
                + _urlpar.quote(ref.encode("utf-8")))

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=None, pg=None):
        """面板搜索是**按集登记**的: 一部 40 集的剧会返回 40 条,
        itemId 形如 tmdb_xxx_tv_s1_e7, title 是「第 7 集」。
        所以这里必须**按 base 坐标聚合**, 否则搜索结果会被同一部剧刷屏。
        """
        wd = _ustr(key).strip()
        if not wd:
            return {"list": []}
        page = max(1, _num(pg, 1))
        o = self._api("/search", {"wd": wd, "limit": 40}, timeout=30)
        order, agg = [], {}
        for it in (o.get("items") or []):
            iid = _ustr(it.get("itemId") or it.get("id"))
            if not iid:
                continue
            mb = re.match(r"^(tmdb_\d+)_(tv|movie)", iid)
            if mb:
                base, kind = mb.group(1) + "_" + mb.group(2), mb.group(2)
                gid = base
            else:
                base, kind, gid = iid, "", iid
            if gid not in agg:
                agg[gid] = {
                    "id": gid, "base": base, "kind": kind,
                    "title": "", "year": it.get("year"),
                    "poster": it.get("poster"),
                    "eps": 0, "versions": 0, "sites": [],
                }
                order.append(gid)
            a = agg[gid]
            t = _ustr(it.get("title"))
            # 「第 N 集」不是作品名, 跳过
            if t and not re.match(r"^第\s*\d+\s*集$", t):
                if not a["title"] or len(t) > len(a["title"]):
                    a["title"] = t
            a["eps"] += 1
            a["versions"] += _num(it.get("versions"), 0)
            for s in (it.get("sites") or []):
                s = _ustr(s)
                if s and s not in a["sites"]:
                    a["sites"].append(s)
            if not a["poster"] and it.get("poster"):
                a["poster"] = it.get("poster")
        items = []
        for gid in order:
            a = agg[gid]
            title = a["title"] or wd
            self._remember(a["base"], title, a["poster"])
            yr = _ustr(a["year"])
            rem = [yr] if yr else []
            rem.append(u"剧集" if a["kind"] == "tv" else u"电影")
            if a["eps"] > 1:
                # 这里只能反映"搜索命中的集数", 不是真实入库量 —— 面板搜索
                # 每部最多回 50 条且是抽样的, 所以别写"入库", 免得误导。
                rem.append(u"命中%d集" % a["eps"])
            if a["sites"]:
                rem.append(u"/".join(a["sites"][:2]))
            items.append({
                "vod_id": _with_hint(gid, title),
                "vod_name": title,
                "vod_pic": _ustr(a["poster"]),
                "vod_remarks": u"·".join([x for x in rem if x]),
                "vod_year": yr,
            })
        return {"list": items, "page": page,
                "pagecount": page, "limit": len(items), "total": len(items)}

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
        try:
            _sp.init("")
        except Exception:
            pass
    return _sp


def getName():
    return _ins().getName()


def getDependence():
    return []


def init(extend=""):
    global _sp
    _sp = None
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


def searchContentPage(key, quick=False, pg="1"):
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
# 只在本机 python3 影桥.py 时跑, 客户端不会执行到这里。
# 默认走内置密文配置; 想临时换面板/令牌就设环境变量:
#   YQ_PANEL=https://xxx  YQ_TOKEN=yyy  python3 影桥.py
if __name__ == "__main__":
    import os
    _ext = ""
    if os.environ.get("YQ_PANEL") or os.environ.get("YQ_TOKEN"):
        _ext = json.dumps({"panel": os.environ.get("YQ_PANEL", ""),
                           "token": os.environ.get("YQ_TOKEN", "")})
    sp = Spider()
    sp.init(_ext)
    print(u"面板:", sp.panel, u"| 配置完整:", sp._ok())

    print(u"\n=== homeContent ===")
    hc = sp.homeContent(1)
    print(u"分类:", [(c["type_id"], c["type_name"]) for c in hc["class"]])

    print(u"\n=== homeVideoContent ===")
    hv = sp.homeVideoContent()
    print(u"首页:", len(hv["list"]))
    for v in hv["list"][:4]:
        print("  ", v["vod_name"], "|", v["vod_remarks"], "|", v["vod_id"])

    print(u"\n=== 搜索 嫁金钗 ===")
    sc = sp.searchContent(u"嫁金钗", False, "1")
    print(u"结果:", len(sc["list"]))
    for v in sc["list"][:3]:
        print("  ", v["vod_name"], "|", v["vod_remarks"], "|", v["vod_id"])

    print(u"\n=== 搜索 炼气十万年 ===")
    sc2 = sp.searchContent(u"炼气十万年", False, "1")
    for v in sc2["list"][:3]:
        print("  ", v["vod_name"], "|", v["vod_remarks"], "|", v["vod_id"])

    if sc["list"]:
        vid = sc["list"][0]["vod_id"]
        print(u"\n=== 详情 %s ===" % vid)
        t0 = time.time()
        d = sp.detailContent([vid])["list"][0]
        print(u"耗时: %.1fs" % (time.time() - t0))
        print(u"片名:", d["vod_name"], u"| 封面:", d["vod_pic"][:60])
        print(u"备注:", d["vod_remarks"])
        print(u"线路:", d["vod_play_from"])
        first = d["vod_play_url"].split("$$$")[0].split("#")
        print(u"集数:", [x.split("$")[0] for x in first[:6]], u"...",
              u"共", len(first), u"集")
        if first:
            print(u"\n=== 播放 %s ===" % first[0].split("$")[-1])
            p = sp.playerContent(u"影桥", first[0].split("$")[-1], [])
            print(u"parse:", p["parse"])
            # 不打印完整 url —— 里面带 token, 自测输出别留痕
            print(u"url 可播:", bool(p["url"]),
                  u"| 长度:", len(p["url"]))
            print(u"header:", list(p["header"].keys()))