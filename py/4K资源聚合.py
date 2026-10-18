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
_last = [0.0]
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


def _throttle():
    global _lock
    if _lock is None:
        try:
            import threading
            _lock = threading.Lock()
        except Exception:
            return
    with _lock:
        w = _MIN_GAP - (time.time() - _last[0])
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()


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
    _throttle()
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

    # ---------- 四件套 ----------
    def getName(self):
        return NAME

    def init(self, extend=""):
        self._probe()

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return _is_direct(url)

    def manualVideoCheck(self):
        return False

    # ---------- 探测活源 ----------
    def _probe(self):
        if self._probed:
            return self._alive
        self._probed = True
        remote = _remote_hosts()
        for st in SITES:
            cands = [st["host"]] + list(remote.get(st["key"]) or [])
            for h in cands:
                api = h + "/api.php/provide/vod/"
                d = _json(_http(api + "?ac=list", timeout=8))
                if d.get("class") or d.get("list"):
                    if h != st["host"]:
                        _log("主域名失效, 切换备用", st["name"], h)
                        st["host"] = h          # 写回, 后续请求直接用活域名
                    self._alive.append(st)
                    _log("活源", st["name"], st["host"], "total=%s" % st["total"])
                    break
            else:
                _log("失效", st["name"], st["host"])
        return self._alive

    def _api(self, st):
        return st["host"] + "/api.php/provide/vod/"

    # ---------- 首页 ----------
    def homeContent(self, filter):
        self._probe()
        classes = []
        for st in self._alive:
            # 每个站单独拉分类, 用 "站key:分类id" 路由
            d = _json(_http(self._api(st) + "?ac=list", timeout=8))
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
        self._probe()
        out, seen = [], set()
        for st in self._alive[:3]:
            d = _json(_http(self._api(st) + "?ac=videolist&pg=1", timeout=8))
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
        self._probe()
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
        self._probe()
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
        return {"parse": 0 if _is_direct(url) else 1,
                "playUrl": "", "url": url, "header": header}

    # ---------- 搜索 (并发多站合并) ----------
    def searchContent(self, key, quick, pg="1"):
        self._probe()
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


# ============ 自检 ============
if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    sp = Spider()
    print("名称:", sp.getName())
    sp.init()
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


def _bye():
    _SHUTDOWN[0] = True


try:
    import atexit as _atexit
    _atexit.register(_bye)
except Exception:
    pass
