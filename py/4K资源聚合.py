# -*- coding: utf-8 -*-
# 4K资源聚合 · TVBox Python 爬虫 (多站聚合版)
# ==================================================================
# 实测背景 (2026-10 实测):
#   免费 maccms 采集站里"真正的 4K"极少 —— 拉 m3u8 主列表验证,
#   主流站分辨率全是 1080P 级别,"4K"多为站名营销话术。
#   号称最大的 apiyutu.com(22万条) 实测是成人内容站, 已排除。
#
# 本脚本的价值:
#   1. 聚合 5 个实测可用、内容最多的正常影视站, 单站挂了自动切换
#   2. 详情页把"疑似 4K/蓝光"的线路自动排到最前 (含 4K/2160/UHD/蓝光
#      关键词的线路优先, 一旦某站放出真 4K 线路会立即生效)
#   3. 搜索并发打所有活源, 合并去重, 一次搜到最多结果
#   4. 直链 m3u8 parse=0 秒开, 不依赖嗅探
#
# 用法: 直接拷进 TVBox, 或 python3 4K资源聚合.py [关键词] 自检
# ==================================================================
import re, json, sys, time, urllib.parse, urllib.request

try:
    import requests
except Exception:
    requests = None
try:
    from concurrent.futures import ThreadPoolExecutor, as_completed
except Exception:
    ThreadPoolExecutor = None
try:
    from base.spider import Spider as _Base
except Exception:
    class _Base(object):
        pass

# ========== 配置: 5 个实测可用站点 ==========
NAME = "4K资源聚合"
SITES = [
    {"key": "bfzy",    "name": "暴风", "host": "https://bfzyapi.com",    "total": 165442},
    {"key": "lzi",     "name": "量子", "host": "https://cj.lziapi.com",  "total": 159601},
    {"key": "jinying", "name": "金鹰", "host": "https://jinyingzy.com",  "total": 115673},
    {"key": "hongniu", "name": "红牛", "host": "https://www.hongniuzy3.com", "total": 115070},
    {"key": "ffzy",    "name": "非凡", "host": "https://api.ffzyapi.com", "total": 98616},
]
PAGE_SIZE = 21
# 分类黑名单: 站点接口返回的分类名含这些词的直接不显示
CAT_BLOCK = ["伦理", "福利", "理论", "写真", "换脸", "自拍", "国产传媒", "流蜜"]
# 可选: 远程备用域名兜底。填一个json地址, 格式 {"bfzy": ["https://备用域名"], "lzi": [...]}
# 站点主域名被封后, 改线上 json 即可让所有用户自动切到备用域名, 无需更新脚本。
REMOTE_SITE_URL = ""
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
# ============================================

# 4K/蓝光 线路关键词: 详情页里线路名含这些词的会被排到最前
HD_KEYWORDS = ["4k", "2160", "uhd", "蓝光", "bluray", "bd", "原盘", "hdr", "杜比", "dolby"]

# ========== 切片广告过滤 (实测 2026-10) ==========
# 实测 5 个源里只有【暴风】带插播广告, 走的 CDN 是 fengbao14.com:
#   正片第 5 分钟 / 第 40 分钟处插入 /video/adjump/time/<时间戳>.ts
#   共 9~18 个分片, 每个 3 秒, 合计 27~54 秒; 两侧夹 #EXT-X-DISCONTINUITY
#   adjump = ad jump, 分片是真的 TS 视频(1.1MB), 不是图片
# 其余 4 个源(量子/金鹰/红牛/非凡)实测 adjump=0、图片分片=0, 干净。
# 处理方式: 播放时把 m3u8 包一层 localProxy, 剔除广告分片后再吐给播放器。
AD_FILTER = True
# 广告分片地址特征(小写子串匹配)。遇到新的广告路径往后加即可, 不用改逻辑
AD_PAT = ("adjump", "/ad/", "/ads/", "advert", "/gg/", "/guanggao")
# 图片扩展名: 广告方有时把 png/webp 伪装成分片混在 ts 里
IMG_EXT = ("png", "jpg", "jpeg", "gif", "webp", "bmp", "ico", "svg", "avif")
# 过滤后至少留这么多秒, 否则不采用过滤结果(防止把整集删成残片)
MIN_KEEP_SEC = 900
# ================================================


def _log(*a):
    try:
        sys.stderr.write("[%s] %s\n" % (NAME, " ".join(str(x) for x in a)))
    except Exception:
        pass


# ---------- 网络层: Session 复用 + 缓存 + 节流 ----------
_SESS = None
_CACHE = {}
_CACHE_TTL = 120
_lock = None
# ★ 节流按 host 分账, 不能用一个全局时间戳:
#   本脚本每次都是「同时打 5 个不同的站」, 全局节流会把这 5 个请求排成队列,
#   每个白等 0.05 秒, 5 个就是 0.25 秒; 实测并发(全局节流)1.08s
#   vs 并发(按 host 节流)0.47s, 差 2.3 倍。
#   节流本来是为了「别把同一个站打太密」, 所以粒度就该是 host。
_last = {}
_MIN_GAP = 0.05
_SHUTDOWN = [False]


def _session():
    global _SESS
    if _SESS is not None or not requests:
        return _SESS
    try:
        from requests.adapters import HTTPAdapter
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Connection": "keep-alive",
                          "Accept": "application/json, text/plain, */*"})
        ad = HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=1)
        s.mount("https://", ad)
        s.mount("http://", ad)
        _SESS = s
    except Exception:
        _SESS = None
    return _SESS


def _host_of(url):
    """取 url 的 netloc 当节流键; 解析不出来就整条当键(退化成串行, 不会错)"""
    try:
        p = url.split("://", 1)
        rest = p[1] if len(p) > 1 else p[0]
        return rest.split("/", 1)[0].lower()
    except Exception:
        return url


def _throttle(url=""):
    """按 host 节流: 只有「同一个站」的连续请求才需要拉开间隔"""
    global _lock
    if _lock is None:
        try:
            import threading
            _lock = threading.Lock()
        except Exception:
            return
    k = _host_of(url)
    with _lock:
        w = _MIN_GAP - (time.time() - _last.get(k, 0.0))
        if w > 0:
            time.sleep(w)
        _last[k] = time.time()


# ---------- Cloudflare 拦截页检测 + 远程备用域名兜底 (借鉴 55影院/八戒影视) ----------
_CF_WORDS = ("Just a moment", "安全驗證", "安全验证", "cf-mitigated",
             "cf-error-details", "Web Server Is Down", "Bad gateway",
             "A timeout occurred")


def _cfpage(t):
    """识别 CF 拦截/错误页: HTTP 状态可能是 200, 必须看内容"""
    try:
        t2 = (t or "")[:3000]
    except Exception:
        return False
    return any(w in t2 for w in _CF_WORDS)


_REMOTE = None
_REMOTE_TS = 0.0


def _remote_hosts():
    """远程备用域名表 {站key: [域名,...]}, 缓存 10 分钟, 失败返回空"""
    global _REMOTE, _REMOTE_TS
    if not REMOTE_SITE_URL:
        return {}
    if _REMOTE is None or time.time() - _REMOTE_TS > 600:
        try:
            j = json.loads(_http(REMOTE_SITE_URL, timeout=6, use_cache=False) or "")
            _REMOTE = j if isinstance(j, dict) else {}
        except Exception:
            _REMOTE = {}
        _REMOTE_TS = time.time()
    return _REMOTE or {}


def _http(url, timeout=10, use_cache=True):
    if use_cache:
        c = _CACHE.get(url)
        if c and time.time() - c[0] < _CACHE_TTL:
            return c[1]
    _throttle(url)
    txt = ""
    s = _session()
    if s is not None:
        try:
            r = s.get(url, timeout=timeout, verify=False)
            if r.status_code == 200:
                txt = r.text
        except Exception:
            pass
    if not txt:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                txt = resp.read().decode("utf-8", "ignore")
        except Exception as e:
            _log("请求失败", url[:60], repr(e)[:40])
            return ""
    if txt and _cfpage(txt):
        # CF 拦截页: 视为失败, 不缓存
        _log("CF拦截", url[:60])
        return ""
    if txt and use_cache:
        if len(_CACHE) > 300:
            _CACHE.clear()
        _CACHE[url] = (time.time(), txt)
    return txt


def _json(txt):
    try:
        d = json.loads(txt) if txt else {}
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _clean(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    return re.sub(r"\s+", " ", s).strip()


def _is_direct(u):
    return bool(re.search(r"\.(m3u8|mp4|flv|mkv|ts)(\?|$)", u or "", re.I))


def _vod(vid, name, pic="", remark="", year="", tname=""):
    return {"vod_id": str(vid), "vod_name": _clean(name), "vod_pic": pic or "",
            "vod_remarks": remark or "", "vod_year": str(year or ""),
            "type_name": tname or ""}


class Spider(_Base):
    def __init__(self):
        self._alive = []      # 探测成功的源 [{key,name,host}]
        self._probed = False
        self._probe_lock = None   # 探测状态锁(懒建, 兼容 py2 无 threading 的极端环境)
        self._probe_done = None   # Event: 探测是否已结束
        self._probe_thread = None

    # ---------- 四件套 ----------
    def getName(self):
        return NAME

    def init(self, extend=""):
        """【init 不发同步请求】
        TVBox 打开源时会同步调 init, 串行探测 5 个站实测要 2.8~6.7 秒,
        这段时间整个 App 卡在启动页。这里只把探测扔到后台, 立刻返回;
        真正要用数据的地方(首页/分类/搜索)各自等探测完成。
        """
        self._start_probe()

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return _is_direct(url)

    def manualVideoCheck(self):
        return False

    # ---------- 探测活源 ----------
    _state_lock = None

    def _ensure_probe_state(self):
        """懒建探测用的锁和 Event。

        ★ 这里必须用「双重检查」: 本方法会被主线程和探测线程同时调用,
          如果直接 `if x is None: x = Lock()`, 两边可能各建一把锁,
          谁拿到哪把不确定 -> 互斥失效。
          用一把类级别的模块锁来保护「建锁」这个动作本身。
        """
        if self._probe_lock is not None and self._probe_done is not None:
            return
        if Spider._state_lock is None:
            import threading
            Spider._state_lock = threading.Lock()
        with Spider._state_lock:
            if self._probe_lock is None:
                import threading
                self._probe_lock = threading.Lock()
            if self._probe_done is None:
                import threading
                self._probe_done = threading.Event()

    def _start_probe(self):
        """起后台探测线程(只起一次)"""
        self._ensure_probe_state()
        if self._probed:
            return
        with self._probe_lock:
            if self._probed:
                return
            if self._probe_thread is None:
                import threading
                t = threading.Thread(target=self._probe_job, daemon=True)
                t.start()
                self._probe_thread = t

    def _probe_job(self):
        try:
            self._probe()
        except Exception as e:
            _log("探测异常", repr(e)[:60])
        finally:
            self._ensure_probe_state()
            self._probed = True
            self._probe_done.set()      # ★ 必须 set, 否则等在 _wait_alive 里的线程会卡满超时

    def _probe(self):
        """【并发探测 5 个站】
        串行实测 2.8s(好的时候)~6.7s(金鹰/红牛慢的时候), 并发后 0.47~1.08s。
        每个站内部仍按「主域名 -> 备用域名」顺序试, 这个顺序不能并发
        (备用域名只在主域名挂了才有意义)。
        """
        if self._probed and self._alive:
            return self._alive
        remote = _remote_hosts()

        def one(st):
            cands = [st["host"]] + list(remote.get(st["key"]) or [])
            for h in cands:
                api = h + "/api.php/provide/vod/"
                d = _json(_http(api + "?ac=list", timeout=8))
                if d.get("class") or d.get("list"):
                    if h != st["host"]:
                        _log("主域名失效, 切换备用", st["name"], h)
                        st["host"] = h          # 写回, 后续请求直接用活域名
                    _log("活源", st["name"], st["host"], "total=%s" % st["total"])
                    return st
            _log("失效", st["name"], st["host"])
            return None

        # 保持 SITES 原顺序(首页推荐按这个顺序取样), 并发只影响耗时不影响顺序
        got = [None] * len(SITES)
        if ThreadPoolExecutor and len(SITES) > 1:
            try:
                with ThreadPoolExecutor(max_workers=len(SITES)) as ex:
                    futs = [ex.submit(one, st) for st in SITES]
                    for i, f in enumerate(futs):
                        try:
                            got[i] = f.result()
                        except Exception:
                            got[i] = None
            except Exception:
                got = [one(st) for st in SITES]
        else:
            got = [one(st) for st in SITES]
        self._alive = [st for st in got if st is not None]
        return self._alive

    def _wait_alive(self, timeout=12.0):
        """用到 _alive 的地方调它: 已经探测好就立即返回, 否则等后台那次探测。

        ★ 这个「等」不能省: init 里已经不再同步探测了, 如果这里不等,
          直接读 self._alive 会拿到空列表 -> 首页空白。
        ★ 超时也要返回: 宁可返回已探测到的那部分源(甚至空), 也不能把
          TVBox 卡死 —— 用户看到"没有分类"比看到"App 假死"好得多。
        """
        if self._probed and self._alive:
            return self._alive
        self._start_probe()
        self._ensure_probe_state()
        try:
            self._probe_done.wait(timeout)
        except Exception:
            pass
        return self._alive

    def _api(self, st):
        return st["host"] + "/api.php/provide/vod/"

    # ---------- 首页 ----------
    def homeContent(self, filter):
        self._wait_alive()
        # 【并发拉 5 个站的分类】这 5 个请求打的是 5 个不同的站, 互不依赖。
        # 串行实测 1.5~2.6 秒; 并发后只等最慢的那一个。
        # 必须按 SITES 顺序合并, 否则分类列表的顺序每次刷新都在变。
        pool = list(self._alive)

        def one(st):
            return st, _json(_http(self._api(st) + "?ac=list", timeout=8))

        rows = []
        if ThreadPoolExecutor and len(pool) > 1:
            try:
                with ThreadPoolExecutor(max_workers=len(pool)) as ex:
                    for r in ex.map(one, pool):
                        rows.append(r)
            except Exception:
                rows = [one(st) for st in pool]
        else:
            rows = [one(st) for st in pool]
        classes = []
        for st, d in rows:
            for c in d.get("class") or []:
                tid, nm = c.get("type_id"), (c.get("type_name") or "")
                if tid is None or not nm:
                    continue
                if any(b in nm for b in CAT_BLOCK):
                    continue
                classes.append({"type_id": "%s:%s" % (st["key"], tid),
                                "type_name": "%s·%s" % (st["name"], nm)})
        return {"class": classes}

    def homeVideoContent(self):
        self._wait_alive()
        out, seen = [], set()
        # 【并发拉前 3 个站】串行实测 1.8~3.1 秒, 并发 0.6~0.8 秒。
        # 必须保持 SITES 顺序合并, 否则首页推荐顺序每次都在变(用户会觉得"乱跳")。
        pool = self._alive[:3]

        def one(st):
            return st, _json(_http(self._api(st) + "?ac=videolist&pg=1", timeout=8))

        rows = []
        if ThreadPoolExecutor and len(pool) > 1:
            try:
                with ThreadPoolExecutor(max_workers=len(pool)) as ex:
                    for r in ex.map(one, pool):
                        rows.append(r)
            except Exception:
                rows = [one(st) for st in pool]
        else:
            rows = [one(st) for st in pool]
        for st, d in rows:
            for it in d.get("list") or []:
                vid = "%s:%s" % (st["key"], it.get("vod_id"))
                if vid in seen:
                    continue
                seen.add(vid)
                out.append(_vod(vid, it.get("vod_name"), it.get("vod_pic"),
                                it.get("vod_remarks"), it.get("vod_year"),
                                "%s·%s" % (st["name"], it.get("type_name") or "")))
            if len(out) >= PAGE_SIZE * 2:
                break
        return {"list": out[:PAGE_SIZE * 2]}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        res = {"list": [], "page": pg, "pagecount": 1, "limit": PAGE_SIZE, "total": 0}
        self._wait_alive()
        try:
            if ":" not in str(tid):
                return res
            key, real_tid = str(tid).split(":", 1)
            st = self._find(key)
            if not st:
                return res
            d = _json(_http("%s?ac=videolist&t=%s&pg=%d" % (self._api(st), real_tid, pg)))
            for it in d.get("list") or []:
                res["list"].append(_vod(
                    "%s:%s" % (key, it.get("vod_id")), it.get("vod_name"),
                    it.get("vod_pic"), it.get("vod_remarks"), it.get("vod_year"),
                    it.get("type_name") or ""))
            res["pagecount"] = min(int(d.get("pagecount") or pg), 500)
            res["total"] = int(d.get("total") or len(res["list"]))
        except Exception as e:
            _log("分类异常", repr(e)[:80])
        return res

    def _find(self, key):
        for st in self._alive:
            if st["key"] == key:
                return st
        return None

    # ---------- 详情 (4K 线路自动置顶) ----------
    def detailContent(self, ids):
        res = {"list": []}
        self._wait_alive()
        try:
            raw = str(ids[0] if isinstance(ids, list) else ids)
            key, vod_id = raw.split(":", 1)
            st = self._find(key)
            if not st:
                return res
            d = _json(_http("%s?ac=detail&ids=%s" % (self._api(st), vod_id)))
            it = (d.get("list") or [None])[0]
            if not it:
                return res
            froms = (it.get("vod_play_from") or "").split("$$$")
            urls = (it.get("vod_play_url") or "").split("$$$")
            src, out = [], []
            for name, eps in zip(froms, urls):
                eps = [e for e in eps.split("#") if "$" in e]
                if not eps:
                    continue
                src.append(name or "默认")
                out.append("#".join(eps))
            # 核心: 疑似 4K/蓝光 的线路排最前, 真 4K 出现时自动生效
            def _rank(i):
                ln = src[i].lower()
                return 0 if any(k in ln for k in HD_KEYWORDS) else 1
            order = sorted(range(len(src)), key=_rank)
            src = [src[i] for i in order]
            out = [out[i] for i in order]
            if not src:
                src, out = ["默认"], ["播放$%s" % vod_id]
            v = _vod(it.get("vod_id"), it.get("vod_name"), it.get("vod_pic"),
                     it.get("vod_remarks"), it.get("vod_year"), it.get("type_name"))
            v.update({
                "vod_area": it.get("vod_area") or "",
                "vod_actor": it.get("vod_actor") or "",
                "vod_director": it.get("vod_director") or "",
                "vod_content": _clean(it.get("vod_content") or ""),
                "vod_play_from": "$$$".join(src),
                "vod_play_url": "$$$".join(out),
            })
            res["list"].append(v)
        except Exception as e:
            _log("详情异常", repr(e)[:80])
        return res

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        url = id if (id or "").startswith("http") else id or ""
        header = {"User-Agent": UA, "Referer": SITES[0]["host"] + "/"}
        # m3u8 里可能夹着伪装成 ts 的图片广告 / adjump 插播段 -> 走本地代理过滤
        if AD_FILTER and ".m3u8" in url.lower():
            # url 必须整段编码, 否则里面的 & 会把代理参数切断
            url = "proxy://do=py&type=m3u8&url=" + urllib.parse.quote(url, safe="")
            return {"parse": 0, "playUrl": "", "url": url, "header": header}
        return {"parse": 0 if _is_direct(url) else 1,
                "playUrl": "", "url": url, "header": header}

    # ---------- 切片广告过滤 ----------
    @staticmethod
    def _seg_ext(u):
        """分片地址的扩展名, 取不到返回空串"""
        p = (u or "").split("?")[0]
        name = p.rsplit("/", 1)[-1]
        return name.rsplit(".", 1)[-1].lower() if "." in name else ""

    def _is_ad_seg(self, u):
        """分片地址像广告吗(adjump 这类插播段)"""
        low = (u or "").lower()
        return any(w in low for w in AD_PAT)

    def _master_sub(self, text, base_url):
        """如果是 master 清单, 返回第一路子清单的绝对地址; 不是则返回 ''
        master 的特征: 有 #EXT-X-STREAM-INF, 分片全是 .m3u8 且没有 #EXTINF
        """
        if "#EXT-X-STREAM-INF" not in text:
            return ""
        for line in text.split("\n"):
            t = line.strip()
            if t and not t.startswith("#"):
                return urllib.parse.urljoin(base_url, t)
        return ""

    def _filter_m3u8(self, text, base_url):
        """剔掉图片假分片和插播广告段, 相对地址补绝对
        返回 (新内容, 删掉几个, 留下几个, 留下总秒数)
        """
        out = []
        pending = []
        pending_sec = 0.0
        dropped = kept = 0
        kept_sec = 0.0
        just_dropped = False
        for raw in text.split("\n"):
            t = raw.strip()
            if not t:
                continue
            if t.startswith("#"):
                # ★ #EXTM3U / #EXT-X-VERSION / #EXT-X-TARGETDURATION 这些头部标签
                #   不属于任何分片, 必须无条件先输出。攒进 pending 的话, 一旦
                #   首个分片就是广告, 整批被丢, 清单没有 #EXTM3U 播放器不认。
                if not t.startswith("#EXTINF"):
                    # 广告删掉后, 紧跟的 DISCONTINUITY 两边都是正片, 留着没意义,
                    # 有的播放器见到会重置解码器(画面闪一下)
                    if just_dropped and t.startswith("#EXT-X-DISCONTINUITY"):
                        just_dropped = False
                        continue
                    just_dropped = False
                    out.append(t)
                    continue
                pending.append(t)
                try:
                    pending_sec = float(t.split(":", 1)[1].split(",")[0])
                except Exception:
                    pending_sec = 0.0
                continue
            # 分片行
            if self._seg_ext(t) in IMG_EXT or self._is_ad_seg(t):
                dropped += 1
                pending = []
                pending_sec = 0.0
                just_dropped = True
                continue
            just_dropped = False
            if not t.startswith("http"):
                t = urllib.parse.urljoin(base_url, t)
            out.extend(pending)
            pending = []
            out.append(t)
            kept += 1
            kept_sec += pending_sec
            pending_sec = 0.0
        return "\n".join(out) + "\n", dropped, kept, kept_sec

    def localProxy(self, param):
        """播放器请求 proxy:// 时走这里: 拉 m3u8 -> 过滤 -> 吐新清单"""
        p = self._param(param)
        if str(p.get("type") or "") not in ("", "m3u8"):
            return [404, "text/plain", b""]
        url = p.get("url") or ""
        if not url:
            return [404, "text/plain", b""]
        body = b""
        for _ in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=15) as r:
                    body = r.read()
                if body:
                    break
            except Exception:
                # fengbao 这类站会间歇性 404, 隔 0.25 秒重试基本就命中
                time.sleep(0.25)
        if not body:
            return [404, "text/plain", b""]
        text = body.decode("utf-8", "replace")
        if "#EXTM3U" not in text:
            return [200, "application/vnd.apple.mpegurl", body]
        # ★ master 清单(只列出子清单地址, 如 1000k/hls/mixed.m3u8):
        #   不能直接吐给播放器 —— 子清单里是相对路径, 播放器会按 master 的
        #   目录去拼, 拼出来全是 404。这里钻进第一路子清单, 继续过滤后返回。
        #   代价是丢了多码率切换, 但 TVBox 播放器本来也不会手动切码率。
        sub = self._master_sub(text, url)
        if sub:
            try:
                req = urllib.request.Request(sub, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=15) as r:
                    body2 = r.read()
                text2 = body2.decode("utf-8", "replace")
                if "#EXTM3U" in text2:
                    text, body, url = text2, body2, sub
            except Exception:
                return [200, "application/vnd.apple.mpegurl", body]
        new_text, dropped, kept, kept_sec = self._filter_m3u8(text, url)
        ctype = "application/vnd.apple.mpegurl"
        if dropped == 0:
            # 没广告; 但相对地址(0000000.ts 这种)补全后的清单得吐出去
            if new_text and new_text != text:
                return [200, ctype, new_text.encode("utf-8")]
            return [200, ctype, body]
        if kept == 0 or kept_sec < MIN_KEEP_SEC:
            # 全删光了 / 只剩残片 -> 原样回, 别让用户看到黑屏
            return [200, ctype, body]
        return [200, ctype, new_text.encode("utf-8")]

    @staticmethod
    def _param(param):
        """localProxy 的 param 形态很多: dict / 查询串 / 整条代理URL"""
        s = param
        if isinstance(s, dict):
            return s
        if not isinstance(s, str):
            try:
                s = str(s)
            except Exception:
                return {}
        if s.startswith("proxy://"):
            s = s[len("proxy://"):]
        out = {}
        for part in s.split("&"):
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k in ("url", "u"):
                v = urllib.parse.unquote(v)
            out[k] = v
        return out

    # ---------- 搜索 (并发多站合并) ----------
    def searchContent(self, key, quick, pg="1"):
        self._wait_alive()
        pg = int(pg or 1)
        out, seen = [], set()

        def _one(st):
            d = _json(_http("%s?ac=videolist&wd=%s&pg=%d" % (
                self._api(st), urllib.parse.quote(key), pg)))
            rows = []
            for it in d.get("list") or []:
                vid = "%s:%s" % (st["key"], it.get("vod_id"))
                if vid in seen:
                    continue
                seen.add(vid)
                rows.append(_vod(vid, it.get("vod_name"), it.get("vod_pic"),
                                 it.get("vod_remarks"), it.get("vod_year"),
                                 "%s·%s" % (st["name"], it.get("type_name") or "")))
            return rows

        if ThreadPoolExecutor and len(self._alive) > 1:
            with ThreadPoolExecutor(max_workers=min(5, len(self._alive))) as ex:
                futs = [ex.submit(_one, st) for st in self._alive]
                for f in as_completed(futs):
                    try:
                        out.extend(f.result())
                    except Exception:
                        pass
        else:
            for st in self._alive:
                out.extend(_one(st))
        return {"list": out, "page": pg}


def _bye():
    _SHUTDOWN[0] = True


try:
    import atexit as _atexit
    _atexit.register(_bye)
except Exception:
    pass


# ============ 模块级转发 (TVBox 只认模块级函数, 缺了就整站空白) ============
_sp = None


def _ins():
    global _sp
    if _sp is None:
        _sp = Spider()
    return _sp


def getName():
    return NAME


def init(extend=""):
    return _ins().init(extend)


def homeContent(filter=True):
    return _ins().homeContent(filter)


def homeVideoContent():
    return _ins().homeVideoContent()


def categoryContent(tid, pg, filter=True, extend=None):
    return _ins().categoryContent(tid, pg, filter, extend or {})


def detailContent(ids):
    return _ins().detailContent(ids)


def searchContent(key, quick=False, pg="1"):
    return _ins().searchContent(key, quick, pg)


def playerContent(flag, id, vipFlags=None):
    return _ins().playerContent(flag, id, vipFlags)


def localProxy(param):
    return _ins().localProxy(param)


def isVideoFormat(url):
    return _is_direct(url)


def manualVideoCheck():
    return False


def getDependence():
    return []


def destroy():
    try:
        _ins().destroy()
    except Exception:
        pass


# ============ 自检 ============
if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    sp = Spider()
    print("名称:", sp.getName())
    # init 现在是「起后台探测后立刻返回」, 所以这里必须用 _wait_alive 等它,
    # 否则会打印出一个空的活源列表(功能没问题, 只是自检信息会误导人)
    t0 = time.time()
    sp.init()
    print("init 耗时: %.3fs (不阻塞启动)" % (time.time() - t0))
    sp._wait_alive()
    print("活源:", [(s["name"], s["total"]) for s in sp._alive])
    cs = sp.homeContent(True)["class"]
    print("分类总数:", len(cs), "| 前5:", [(c["type_id"], c["type_name"]) for c in cs[:5]])
    hv = sp.homeVideoContent()["list"]
    print("首页:", len(hv), "条")

    # 找第一个真有数据的分类
    hit = None
    for c in cs[:30]:
        r = sp.categoryContent(c["type_id"], 1, True, {})
        if len(r["list"]) >= 5:
            hit = (c, r)
            break
    if hit:
        c, r = hit
        print("列表[%s]: %d 条, pagecount=%s" % (c["type_name"], len(r["list"]), r["pagecount"]))
        d = sp.detailContent([r["list"][0]["vod_id"]])["list"]
        if d:
            v = d[0]
            eps = (v.get("vod_play_url") or "").split("#")
            print("详情:", v["vod_name"], "| 线路:", v.get("vod_play_from"), "| 集数:", len(eps))
            if eps:
                u = eps[0].split("$")[-1]
                p = sp.playerContent("", u)
                print("播放: parse=%s url=%s" % (p["parse"], (p["url"] or "")[:70]))

    key = sys.argv[1] if len(sys.argv) > 1 else "流浪地球"
    print("搜索[%s]: %d 条" % (key, len(sp.searchContent(key, False)["list"])))
    print("\n自检完成")
