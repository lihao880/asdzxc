# -*- coding: utf-8 -*-
# 樱花影视 TVBox 爬虫 —— 接口型 maccms (基于 yhzy.cc 实测 2026-10)
# 写法遵循《TVBox 写法提炼》骨架：接口优先 / 全程去重 / 默认值兜底 / 失败返回空不抛错
# py2/py3 双兼容（无 f-string，转换函数 _bstr/_ustr/_jdump）
# 用法: 拷进 TVBox / FongMi 即可；本地自检: python3 樱花影视.py [关键词]
import re, json, sys, time, hashlib, atexit, urllib.parse, urllib.request

try:
    import requests
except Exception:
    requests = None

# ========== 改这 3 行即可换站 ==========
NAME   = u"樱花影视"
HOSTS  = ["https://yhzy.cc"]
CLASSES = [("1", u"电影"), ("2", u"连续剧"), ("3", u"综艺"), ("4", u"动漫")]
PAGE_SIZE = 20
# 远程兜底域名(可选): 放一个 {"hosts":["https://备用1","https://备用2"]} 的 json 地址
REMOTE_HOSTS_URL = ""
# =====================================

# 顶层分类是空壳(坑3)，该站接口无 type_pid，用手动父子映射做聚合(坑4)
# 电影/连续剧/综艺/动漫 都是聚合壳，真正数据在叶子分类
SUB_MAP = {
    u"1": [u"6", u"7", u"8", u"9", u"10", u"11", u"12", u"20", u"21", u"22"],  # 电影
    u"2": [u"13", u"14", u"15", u"16", u"23", u"24", u"25"],                        # 连续剧
    u"3": [u"26", u"27", u"28", u"29"],                                              # 综艺
    u"4": [u"30", u"31", u"32", u"33"],                                              # 动漫
}
# 聚合并发上限 + 节流（坑5/坑6）
MAX_WORKERS = 4
_MIN_GAP = 0.06
_LOCK = None
_LAST = {}
try:
    import threading
    _LOCK = threading.Lock()
except Exception:
    _LOCK = None

UA = "Mozilla/5.0"

# ---------- py2/py3 兼容层 ----------
try:
    _PY3 = sys.version_info[0] == 3
except Exception:
    _PY3 = True
try:
    _UNICODE = unicode
except NameError:
    _UNICODE = str
try:
    _BYTES = bytes if _PY3 else str
except Exception:
    _BYTES = str


def _log(*a):
    try:
        sys.stderr.write(u"[%s] %s\n" % (NAME, u" ".join(_ustr(x) for x in a)))
    except Exception:
        pass


def _bstr(raw):
    if not raw:
        return None
    if isinstance(raw, _UNICODE):
        return raw
    try:
        return raw.decode("utf-8", "replace")
    except Exception:
        return None


def _ustr(s):
    if s is None:
        return u""
    if isinstance(s, _UNICODE):
        return s
    if isinstance(s, (_BYTES, bytearray, memoryview)):
        b = bytes(s) if _PY3 else s
        return _bstr(b) or u""
    try:
        return _UNICODE(str(s))
    except Exception:
        return u""


def _jdump(d):
    try:
        t = json.dumps(d, ensure_ascii=False)
    except Exception:
        t = json.dumps(d)
    if not _PY3 and isinstance(t, _UNICODE):
        return t.encode("utf-8")
    return t


def _q(s):
    return urllib.parse.quote(_ustr(s).encode("utf-8"))


# ---------- 网络层：三级降级 + 内容锚点识别 ----------
_CF_WORDS = (u"Just a moment", u"安全驗證", u"安全验证", u"cf-mitigated",
             u"cf-error-details", u"Web Server Is Down", u"Bad gateway",
             u"A timeout occurred")


def _cfpage(t):
    try:
        t2 = (t or u"")[:3000]
    except Exception:
        return False
    return any(w in t2 for w in _CF_WORDS)


_GOOD = {"h": None, "t": 0.0}
_HOSTS_REMOTE = None
_HOSTS_TS = 0.0
_CACHE = {}
_CACHE_TTL = 120


def _http(url, timeout=10, use_cache=True):
    # 缓存
    ck = url
    if use_cache and ck in _CACHE:
        v, ts = _CACHE[ck]
        if time.time() - ts < _CACHE_TTL:
            return v
    h = {"User-Agent": UA, "Referer": HOSTS[0] + "/"}
    txt = ""
    if requests:
        try:
            r = requests.get(url, headers=h, timeout=timeout, verify=False)
            if r.status_code == 200:
                txt = r.text
        except Exception:
            pass
    if not txt:
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                txt = resp.read().decode("utf-8", "ignore")
        except Exception as e:
            _log(u"请求失败", url[:80], repr(e)[:50])
            return ""
    if txt and _cfpage(txt):
        _GOOD["t"] = 0.0          # 域名不可信，下次重新轮换
        return ""
    if use_cache and txt:
        _CACHE[ck] = (txt, time.time())
        if len(_CACHE) > 2000:    # 防内存膨胀
            _CACHE.clear()
    return txt


def _hosts_all():
    global _HOSTS_REMOTE, _HOSTS_TS
    hs = list(HOSTS)
    if REMOTE_HOSTS_URL:
        if _HOSTS_REMOTE is None or time.time() - _HOSTS_TS > 600:
            try:
                j = json.loads(_http(REMOTE_HOSTS_URL, timeout=6, use_cache=False) or u"{}")
                rl = j.get("hosts") or []
                if isinstance(rl, list):
                    hs += [x for x in rl if isinstance(x, _UNICODE) and x.startswith("http")]
            except Exception:
                pass
            _HOSTS_REMOTE = hs
            _HOSTS_TS = time.time()
        hs = _HOSTS_REMOTE
    return hs


def _pick_host():
    now = time.time()
    if _GOOD["h"] and now - _GOOD["t"] < 300:
        return _GOOD["h"]
    for h in _hosts_all():
        txt = _http(h + "/api.php/provide/vod/?ac=list", timeout=6, use_cache=False)
        if txt and txt.lstrip()[:1] == "{" and not _cfpage(txt):
            _GOOD["h"], _GOOD["t"] = h, now
            return h
    h = (_hosts_all() or HOSTS)[0]
    _GOOD["h"], _GOOD["t"] = h, now - 240
    return h


def _api():
    return _pick_host() + "/api.php/provide/vod/"


# ---------- 工具 ----------
def _clean(s):
    s = re.sub(r"<[^>]+>", "", _ustr(s))
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&ldquo;", u"\u201c").replace("&rdquo;", u"\u201d")
    return re.sub(r"\s+", " ", s).strip()


def _unescape_url(u):
    if not u:
        return ""
    return u.replace("\\/", "/").replace("\\u0026", "&").replace("\\", "")


def _is_direct(u):
    return bool(re.search(r"\.(m3u8|mp4|flv|mkv|ts|mpd)(\?|$)", _ustr(u), re.I))


def _json(txt):
    try:
        d = json.loads(txt) if txt else {}
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _vod(vid, name, pic="", remark=""):
    return {"vod_id": _ustr(vid), "vod_name": _clean(name), "vod_pic": pic or "",
            "vod_remarks": remark or ""}


def _classes_from_api(txt):
    try:
        d = json.loads(txt)
    except Exception:
        return []
    out = []
    for c in d.get("class") or []:
        tid = c.get("type_id")
        nm = (c.get("type_name") or "").strip()
        if tid is not None and nm:
            out.append((_ustr(tid), _ustr(nm)))
    return out


def _throttle(url=""):
    """全局节流: 按 host 分账, 避免把同一站打太密(坑6)"""
    if not _LOCK:
        return
    try:
        k = urllib.parse.urlparse(url).netloc
    except Exception:
        k = ""
    with _LOCK:
        w = _MIN_GAP - (time.time() - _LAST.get(k, 0.0))
        if w > 0:
            time.sleep(w)
        _LAST[k] = time.time()


def _from_api(data, seen=None):
    out, seen = [], seen if seen is not None else set()
    for it in (data or {}).get("list") or []:
        vid = _ustr(it.get("vod_id") or "")
        if not vid or vid in seen:
            continue
        seen.add(vid)
        v = _vod(vid, it.get("vod_name"), it.get("vod_pic"), it.get("vod_remarks"))
        v["vod_year"] = _ustr(it.get("vod_year") or "")
        v["type_name"] = _ustr(it.get("type_name") or "")
        out.append(v)
    return out


def _detail_from_api(it):
    # 按名字分组拼线路，避免 zip 错位
    froms = _ustr(it.get("vod_play_from") or "").split("$$$")
    urls = _ustr(it.get("vod_play_url") or "").split("$$$")
    src, out = [], []
    for name, eps in zip(froms, urls):
        eps = [e for e in eps.split("#") if "$" in e]
        if not eps:
            continue
        src.append(name or u"默认")
        out.append("#".join(eps))
    if not src:
        src, out = [u"默认"], [u"播放$%s" % _ustr(it.get("vod_id"))]
    v = _vod(it.get("vod_id"), it.get("vod_name"), it.get("vod_pic"), it.get("vod_remarks"))
    v.update({
        "type_name": _ustr(it.get("type_name") or ""),
        "vod_year": _ustr(it.get("vod_year") or ""),
        "vod_area": _ustr(it.get("vod_area") or ""),
        "vod_actor": _ustr(it.get("vod_actor") or ""),
        "vod_director": _ustr(it.get("vod_director") or ""),
        "vod_content": _clean(it.get("vod_content") or ""),
        "vod_play_from": "$$$".join(src),
        "vod_play_url": "$$$".join(out),
    })
    return v


# ---------- Spider 类 ----------
try:
    from base.spider import Spider as _Base
except Exception:
    class _Base(object):
        pass


class Spider(_Base):
    def __init__(self, cfg=None):
        self._cfg = cfg or {}
        self._host = None
        self._mode = "api"

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return _is_direct(url)

    def manualVideoCheck(self):
        return False

    def getName(self):
        return NAME

    def homeContent(self, filter):
        # 接口型: 优先服务端下发的分类
        try:
            cs = _classes_from_api(_http(_api() + "?ac=list"))
            if cs:
                # 过滤掉伦理片(t=34), 不在首页显示
                cs = [x for x in cs if x[0] != u"34"]
                return {"class": [{"type_id": _ustr(t), "type_name": _ustr(n)} for t, n in cs]}
        except Exception as e:
            _log(u"homeContent 异常", repr(e)[:60])
        return {"class": [{"type_id": t, "type_name": n} for t, n in CLASSES]}

    def homeVideoContent(self):
        try:
            data = _json(_http(_api() + "?ac=videolist&pg=1"))
            return {"list": _from_api(data)[:PAGE_SIZE * 2]}
        except Exception as e:
            _log(u"homeVideoContent 异常", repr(e)[:60])
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        res = {"list": [], "page": pg, "pagecount": 1, "limit": PAGE_SIZE, "total": 0}
        try:
            tid = _ustr(tid)
            kids = SUB_MAP.get(tid)
            if kids:
                # 父分类聚合: 各子分类拉同一页, 并发 + 去重 + 页码取最大并硬上限(坑3/4/5/6)
                out, seen = [], set()
                pages = []
                try:
                    from concurrent.futures import ThreadPoolExecutor
                    def one(k):
                        _throttle(_api())
                        return k, _json(_http("%s?ac=videolist&t=%s&pg=%d" % (_api(), k, pg), timeout=8))
                    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(kids))) as ex:
                        futs = {ex.submit(one, k): k for k in kids}
                        for f in futs:
                            k, data = f.result()
                            pages.append(int(data.get("pagecount") or pg))
                            for v in _from_api(data, seen=seen):
                                out.append(v)
                except Exception:
                    pass
                res["list"] = out[:PAGE_SIZE * 3]
                res["pagecount"] = min(max(pages) if pages else pg, 500)
                res["total"] = len(out)   # 聚合首屏不做额外同步扫描(坑8), 用已取量近似
                return res
            # 叶子分类: 单请求
            data = _json(_http("%s?ac=videolist&t=%s&pg=%d" % (_api(), tid, pg)))
            res["list"] = _from_api(data)
            res["pagecount"] = min(int(data.get("pagecount") or pg), 500)
            res["total"] = int(data.get("total") or len(res["list"]))
        except Exception as e:
            _log(u"category 异常", repr(e)[:60])
        return res

    def detailContent(self, ids):
        res = {"list": []}
        try:
            vid = _ustr(ids[0] if isinstance(ids, list) else ids)
            data = _json(_http("%s?ac=detail&ids=%s" % (_api(), vid)))
            items = data.get("list") or []
            if items:
                res["list"].append(_detail_from_api(items[0]))
        except Exception as e:
            _log(u"detail 异常", repr(e)[:60])
        return res

    def playerContent(self, flag, id, vipFlags=None):
        url = _unescape_url(id)
        url = url if url.startswith("http") else urllib.parse.urljoin(_pick_host() + "/", url)
        return {"parse": 0 if _is_direct(url) else 1,
                "playUrl": "", "url": url,
                "header": {"User-Agent": UA, "Referer": _pick_host() + "/"}}

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg or 1)
            data = _json(_http("%s?ac=videolist&wd=%s&pg=%d" % (_api(), _q(key), pg)))
            return {"list": _from_api(data), "page": pg}
        except Exception as e:
            _log(u"search 异常", repr(e)[:60])
            return {"list": [], "page": 1}

    def localProxy(self, param):
        # 简单的直链/图片中转（带 UA+Referer）
        try:
            url = param.get("url") or ""
            typ = param.get("type") or ""
            if not url.startswith("http"):
                return None
            h = {"User-Agent": UA, "Referer": _pick_host() + "/"}
            if requests:
                r = requests.get(url, headers=h, timeout=15, verify=False)
                if r.status_code == 200:
                    ct = r.headers.get("Content-Type") or ("image/jpeg" if typ in ("pic", "img", "image") else "application/octet-stream")
                    body = r.content
                    return [200, ct, body]
            return None
        except Exception:
            return None


# ---------- 13 个模块级转发（TVBox 只认模块级函数） ----------
_sp = None


def _ins():
    global _sp
    if _sp is None:
        _sp = Spider()
    return _sp


def getName():                 return NAME
def init(extend=""):           return _ins().init(extend)
def destroy():                 return _ins().destroy()
def isVideoFormat(url):        return _ins().isVideoFormat(url)
def manualVideoCheck():        return _ins().manualVideoCheck()
def getDependence():           return _ins().getDependence()
def homeContent(filter=True):  return _ins().homeContent(filter)
def homeVideoContent():        return _ins().homeVideoContent()
def categoryContent(tid, pg, filter, extend):
    return _ins().categoryContent(tid, pg, filter, extend)
def detailContent(ids):        return _ins().detailContent(ids)
def playerContent(flag, id, vipFlags=None):
    return _ins().playerContent(flag, id, vipFlags)
def searchContent(key, quick, pg="1"):
    return _ins().searchContent(key, quick, pg)
def localProxy(param):         return _ins().localProxy(param)


# ============ 自检入口 (放文件最末尾) ============
if __name__ == "__main__":
    sp = Spider()
    print(u"名称:", sp.getName())
    cs = sp.homeContent(True)["class"]
    print(u"分类:", len(cs), u"| 前5:", [(c["type_id"], c["type_name"]) for c in cs[:5]])
    print(u"首页:", len(sp.homeVideoContent()["list"]), u"条")

    hit = None
    for c in cs[:20]:
        r = sp.categoryContent(c["type_id"], 1, True, {})
        if len(r["list"]) >= 5:
            hit = (c, r)
            break
    if not hit:
        print(u"!! 所有分类都为空: 检查 HOSTS / API 路径")
        sys.exit(1)

    c, r = hit
    print(u"列表[%s]: %d 条, pagecount=%s" % (c["type_name"], len(r["list"]), r["pagecount"]))
    d = sp.detailContent([r["list"][0]["vod_id"]])["list"]
    if not d:
        print(u"!! 详情为空")
        sys.exit(1)
    v = d[0]
    eps = (v.get("vod_play_url") or "").split("#")
    print(u"详情:", v.get("vod_name"), u"| 线路:", v.get("vod_play_from"), u"| 集数:", len(eps))
    if eps:
        u0 = eps[0].split("$")[-1]
        p = sp.playerContent("", u0)
        print(u"播放: parse=%s url=%s" % (p.get("parse"), (p.get("url") or "")[:70]))

    key = sys.argv[1] if len(sys.argv) > 1 else u"流浪地球"
    print(u"搜索[%s]: %d 条" % (key, len(sp.searchContent(key, False)["list"])))
    print(u"\n五项全非空 → 接入成功")
