# -*- coding: utf-8 -*-
"""
@header({
  searchable: 1,
  filterable: 0,
  quickSearch: 1,
  title: 'Ksou快搜',
  lang: 'hipy'
})
"""
# ============================================================
# Ksou快搜 (www.ksou4.com) — TVBox / 影视仓 / FongMi 爬虫源
# 单文件纯 py（py-drpy / hipy），六接口 + 本地代理 + 自测
# ------------------------------------------------------------
# 站点特征(2026-10-15 全量验证):
#   · Next.js App Router，数据内嵌在 HTML 的 RSC 流 self.__next_f 里
#   · 无鉴权、无加密、m3u8 为明文直链，仅需极少防盗链（实测带/不带 Referer 均 200）
#   · 列表页(/videos) 用内嵌 JSON 对象结构 {"id":"hex","title","code","cover"}
#   · 搜索/首页用卡片组件结构 ["$","div","hex",{... $L2e src/alt ...}]
#   · 播放直链 https://www.ksou.tv/video-source/library/{id}.m3u8
# 调试: python3 ksou4.py --selftest [--debug]
# ============================================================
import sys
import re
import json
import time
import gzip
import urllib.parse
import urllib.request
import urllib.error

# -------------------------- 常量 --------------------------
SITE = "https://www.ksou4.com"
MEDIA = "https://www.ksou.tv"
PLAY_REFERER = SITE + "/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
TIMEOUT = 15
RETRY = 2
CACHE_TTL = 600          # 列表/详情缓存 10 分钟
_DEBUG = "--debug" in sys.argv

# 分类: TVBox type_id -> 站点路由
CATEGORIES = [
    {"type_id": "videos",       "type_name": "最新上架"},
    {"type_id": "rankings",     "type_name": "热播排行"},
    {"type_id": "short-videos", "type_name": "国产原创"},
    {"type_id": "fanhao",       "type_name": "番号检索"},
]

# 列表内嵌对象正则（宽松匹配，容忍字段顺序/空缺）
OBJ_RE = re.compile(
    r'"id":"([0-9a-f]{16})"[^}]{0,300}?"title":"([^"]*)"[^}]{0,300}?"cover":"([^"]+)"')
# 卡片组件：div 带 16 位 hex key，内部 $L2e 组件含 src/alt
CARD_DIV_RE = re.compile(r'\["\$","div","([0-9a-f]{16})"')
CARD_SRC_RE = re.compile(r'"src":"([^"]+)"')
CARD_ALT_RE = re.compile(r'"alt":"([^"]*)"')

_CACHE = {}


def _log(*a):
    if _DEBUG:
        sys.stderr.write("[ksou] " + " ".join(str(x) for x in a) + "\n")


# ---------------------- 缓存工具 ----------------------
def _cache_get(key):
    item = _CACHE.get(key)
    if not item:
        return None
    exp, val = item
    if exp < time.time():
        _CACHE.pop(key, None)
        return None
    return val


def _cache_set(key, val, ttl=CACHE_TTL):
    _CACHE[key] = (time.time() + ttl, val)


# ---------------------- HTTP 工具（标准库） ----------------------
def _request(url, referer=None, headers=None, timeout=None, tag=""):
    t0 = time.time()
    h = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }
    if referer:
        h["Referer"] = referer
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout or TIMEOUT) as resp:
        raw = resp.read()
        enc = (resp.headers.get("Content-Encoding") or "").lower()
        if "gzip" in enc:
            raw = gzip.decompress(raw)
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].lower()
        _log("%s OK %s %dB %.0fms" % (tag or "GET", ctype, len(raw), (time.time() - t0) * 1000))
        return resp.status, ctype, raw


def _http_get(url, referer=None, ttl=None, timeout=None, tag=""):
    """带重试 + 缓存 的文本 GET；失败返回空串"""
    if not url:
        return ""
    if ttl is None:
        ttl = CACHE_TTL
    ck = "T:" + url
    hit = _cache_get(ck)
    if hit is not None:
        _log("CACHE %s" % url[:90])
        return hit
    last = None
    for i in range(RETRY + 1):
        try:
            code, ctype, raw = _request(url, referer=referer, timeout=timeout, tag=tag)
            if code == 200 and raw:
                text = _decode(raw)
                _cache_set(ck, text, ttl)
                return text
            last = "HTTP %s" % code
        except Exception as e:
            last = e
            _log("retry %d: %s" % (i, e))
        if i < RETRY:
            time.sleep(0.4 * (i + 1))
    _log("FAIL", url[:100], last)
    return ""


def _http_get_bytes(url, referer=None, timeout=None):
    try:
        code, ctype, raw = _request(url, referer=referer, timeout=timeout, tag="PROXY")
        if code == 200 and raw:
            return ctype, raw
        return "", b""
    except Exception as e:
        _log("PROXY FAIL:", e)
        return "", b""


def _decode(raw):
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


# ---------------------- RSC 提取 ----------------------
def _rsc(html):
    """从 Next.js RSC 流中提取并拼接完整数据文本"""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', html)
    try:
        return "".join(json.loads(c) for c in chunks)
    except Exception as e:
        _log("rsc json err:", e)
        return html


# ---------------------- 列表解析 ----------------------
def _clean_title(alt):
    """卡片 alt 形如《...》封面 -> 纯标题"""
    t = alt.strip()
    if t.startswith("《"):
        t = t[1:]
    if t.endswith("》"):
        t = t[:-1]
    if t.endswith("封面"):
        t = t[:-2]
    return t.strip()


def _parse_cards(rsc):
    out = []
    it = list(CARD_DIV_RE.finditer(rsc))
    for i, m in enumerate(it):
        vid = m.group(1)
        seg = rsc[m.start(): it[i + 1].start() if i + 1 < len(it) else len(rsc)]
        sm = CARD_SRC_RE.search(seg)
        am = CARD_ALT_RE.search(seg)
        if sm and am:
            out.append((vid, sm.group(1), am.group(1)))
    return out


def _parse_list(rsc):
    """自适应两种结构：对象结构优先，卡片结构兜底，合并去重"""
    out, seen = [], set()
    # 1) 内嵌对象结构 {"id":"hex","title","cover"}
    for vid, title, cover in OBJ_RE.findall(rsc):
        if vid in seen:
            continue
        seen.add(vid)
        name = (title or "").strip()
        if not name:
            continue
        out.append({"vod_id": vid, "vod_name": name, "vod_pic": cover})
    # 2) 卡片组件结构
    for vid, src, alt in _parse_cards(rsc):
        if vid in seen:
            continue
        seen.add(vid)
        name = _clean_title(alt)
        if not name:
            continue
        out.append({"vod_id": vid, "vod_name": name, "vod_pic": src})
    _log("parse_list -> %d 条" % len(out))
    return out


# ---------------------- 业务层 ----------------------
def _route_for(tid):
    for c in CATEGORIES:
        if c["type_id"] == tid:
            return "/" + c["type_id"]
    return None


def _category_videos(route, pg):
    url = SITE + route
    if pg and int(pg or 1) > 1:
        sep = "&" if "?" in url else "?"
        url = "%s%spage=%s" % (url, sep, int(pg))
    html = _http_get(url, tag="CAT")
    if not html:
        return []
    return _parse_list(_rsc(html))


def _home_videos():
    html = _http_get(SITE, tag="HOME")
    if not html:
        return []
    return _parse_list(_rsc(html))


def _search_videos(kw, pg):
    url = "%s/search?q=%s" % (SITE, urllib.parse.quote(kw))
    if pg and int(pg or 1) > 1:
        url += "&page=%s" % int(pg)
    html = _http_get(url, tag="SEARCH")
    if not html:
        return []
    # 搜索结果用卡片结构，兜底对象结构
    return _parse_list(_rsc(html))


def _extract_actors(rsc):
    m = re.search(r'"creators":\[(.*?)\]', rsc)
    if not m:
        return []
    # 过滤掉技术字段
    tech = {"qseek-build-id", "ksou-ga-measurement-id", "viewport",
            "theme-color", "description", "application-name"}
    names = re.findall(r'"name":"([^"]+)"', m.group(1))
    return [n.strip() for n in names if n not in tech]


def _detail_vod(vid):
    html = _http_get("%s/library/%s" % (SITE, vid), tag="DETAIL")
    if not html:
        return None
    vod = {"vod_id": vid}

    # 标题：从 <title> 取（去掉站点后缀）
    mt = re.search(r"<title>([^<]*)</title>", html)
    if mt:
        vod["vod_name"] = re.split(r"\s*\|\s*Ksou快搜", mt.group(1))[0].strip()

    # 封面：og:image
    mo = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]*)"', html)
    if mo:
        vod["vod_pic"] = mo.group(1).strip()

    rsc = _rsc(html)

    # 简介
    md = re.search(r'"description":"((?:[^"\\]|\\.)*)"', rsc)
    desc = _unescape(md.group(1)) if md else ""

    # 时长（ISO 8601 PT 格式，尽量转换）
    mp = re.search(r'PT(\d+H)?(\d+M)?(\d+S)?', rsc)
    dur = _pt_to_min(mp.group(0)) if mp else ""

    # 演员
    actors = _extract_actors(rsc)
    parts = []
    if desc:
        parts.append(desc)
    if actors:
        parts.append("演员: " + " / ".join(actors))
    if dur:
        parts.append("时长: " + dur)
    vod["vod_content"] = "\n".join(parts)[:800]

    # 播放：单线路直链 m3u8
    vod["vod_play_from"] = "ksou4"
    vod["vod_play_url"] = "正片$%s" % vid
    return vod


def _unescape(s):
    """仅还原 JSON 风格的反斜杠转义，绝不调用 unicode_escape（会把正常 UTF-8 中文破坏成乱码）。"""
    if not s:
        return ""
    s = (s.replace('\\"', '"')
         .replace('\\\\', '\\')
         .replace('\\n', '\n')
         .replace('\\t', '\t')
         .replace('\\/', '/'))
    # 若仍有残留 \uXXXX，单独按码点解码（不影响已正确的中文）
    s = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)
    return s


def _pt_to_min(pt):
    """PT1H2M3S / PT120M -> '62分' 之类"""
    h = m = s = 0
    mt = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", pt or "")
    if not mt:
        return ""
    h = int(mt.group(1) or 0)
    m = int(mt.group(2) or 0)
    s = int(mt.group(3) or 0)
    total = h * 60 + m + (1 if s else 0)
    return "%d分钟" % total if total else ""


def _play_url(vid):
    return "%s/video-source/library/%s.m3u8" % (MEDIA, vid)


# ---------------------- TVBox 六接口 ----------------------
def home_content(filter_=False):
    try:
        return {
            "class": [{"type_id": c["type_id"], "type_name": c["type_name"]}
                      for c in CATEGORIES],
            "list": _home_videos(),
        }
    except Exception as e:
        _log("home err:", e)
        return {"class": [{"type_id": c["type_id"], "type_name": c["type_name"]}
                          for c in CATEGORIES], "list": []}


def category_content(tid, pg="1", filter_=False):
    try:
        route = _route_for(tid)
        if not route:
            _log("未知分类 tid=%s" % tid)
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "total": 0}
        videos = _category_videos(route, pg)
        pgi = int(pg or 1)
        return {
            "list": videos,
            "page": pgi,
            "pagecount": pgi + 1,      # 允许继续翻页
            "total": len(videos) if videos else 0,
        }
    except Exception as e:
        _log("cate err:", e)
        return {"list": [], "page": int(pg or 1), "pagecount": 1, "total": 0}


def detail_content(ids):
    try:
        if isinstance(ids, str):
            ids = [x.strip() for x in ids.split(",") if x.strip()]
        vods = []
        for vid in ids or []:
            vod = _detail_vod(re.sub(r"\.html$", "", str(vid)))
            if vod:
                vods.append(vod)
        return {"list": vods}
    except Exception as e:
        _log("detail err:", e)
        return {"list": []}


def play_parse(flag, id_, flags=None):
    """id 形如 '正片$<16hex>' 或直接 16hex"""
    try:
        sid = str(id_ or "")
        if "$" in sid:
            sid = sid.split("$")[-1]
        sid = sid.strip()
        if not re.match(r"^[0-9a-f]{16}$", sid):
            return {"parse": 1, "url": "", "header": {"User-Agent": UA, "Referer": PLAY_REFERER}}
        url = _play_url(sid)
        _log("play %s -> %s" % (sid, url))
        return {
            "parse": 0,
            "url": url,
            "header": {"User-Agent": UA, "Referer": PLAY_REFERER},
        }
    except Exception as e:
        _log("play err:", e)
        return {"parse": 1, "url": "", "header": {"User-Agent": UA, "Referer": PLAY_REFERER}}


def search_content(key, quick=False, pg="1"):
    try:
        key = (key or "").strip()
        if not key:
            return {"list": []}
        out = _search_videos(key, pg)
        pgi = int(pg or 1)
        return {"list": out, "page": pgi, "pagecount": pgi + 1}
    except Exception as e:
        _log("search err:", e)
        return {"list": []}


# ---------------------- localProxy（防盗链/兜底转发） ----------------------
def _proxy_param_url(param):
    if isinstance(param, dict):
        for k in ("url", "imageUrl", "path", "src", "u"):
            if param.get(k):
                return str(param[k]).strip()
        return ""
    s = str(param or "").strip()
    if s.startswith("?"):
        s = s[1:]
    if s.startswith("url="):
        try:
            return urllib.parse.parse_qs(s).get("url", [""])[0]
        except Exception:
            return s[4:]
    return s


def local_proxy(param):
    try:
        url = _proxy_param_url(param)
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith("http"):
            return [404, "text/plain", b"", None]
        ctype, raw = _http_get_bytes(url, referer=PLAY_REFERER, timeout=15)
        if not raw:
            return [404, "text/plain", b"", None]
        return [200, ctype or "application/octet-stream", raw, None]
    except Exception as e:
        _log("localProxy err:", e)
        return [404, "text/plain", b"", None]


# ---------------------- 自测入口 ----------------------
def _selftest():
    ok = fail = 0

    def check(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print("  [PASS] %s %s" % (name, extra))
        else:
            fail += 1
            print("  [FAIL] %s %s" % (name, extra))

    print("=" * 70)
    print("Ksou快搜 ksou4.py 自测 (%s)" % SITE)
    print("=" * 70)

    home = home_content()
    check("首页分类", len(home.get("class", [])) == len(CATEGORIES),
          "-> %s" % [c["type_name"] for c in home["class"]])
    check("首页精选", len(home.get("list", [])) > 0,
          "-> %d 条" % len(home.get("list", [])))

    cate = category_content("videos", "1")
    check("分类(最新上架)", len(cate.get("list", [])) > 0,
          "-> %d 条" % len(cate.get("list", [])))
    if cate.get("list"):
        print("    示例: %s" % cate["list"][0].get("vod_name", "")[:40])

    vid = cate["list"][0]["vod_id"] if cate.get("list") else ""
    det = detail_content([vid])
    vod = det["list"][0] if det.get("list") else {}
    check("详情", bool(vod.get("vod_name") and vod.get("vod_play_url")),
          "-> %s | 封面:%s | 简介:%d字" % (
              vod.get("vod_name", "")[:30],
              "有" if vod.get("vod_pic") else "无",
              len(vod.get("vod_content", ""))))

    if vod.get("vod_play_url"):
        pid = vod["vod_play_url"].split("$")[-1]
        play = play_parse("ksou4", pid)
        check("播放解析", bool(play.get("url")),
              "-> parse=%s url=%s..." % (play.get("parse"), str(play.get("url"))[:70]))

    s = search_content("SSNI")
    check("搜索(SSNI)", len(s.get("list", [])) > 0,
          "-> %d 条" % len(s.get("list", [])))
    if s.get("list"):
        print("    示例: %s" % s["list"][0].get("vod_name", "")[:40])

    print("\n自测结果: %d 通过 / %d 失败" % (ok, fail))
    return 0 if fail == 0 else 1


def home_vod_content():
    try:
        return {"list": home_content().get("list", [])}
    except Exception:
        return {"list": []}


# ---------------------- 双导出 --------------------------
exports = {
    "homeContent": home_content,
    "homeVideoContent": home_vod_content,
    "categoryContent": category_content,
    "detailContent": detail_content,
    "searchContent": search_content,
    "playerContent": play_parse,
    "playContent": play_parse,
    "localProxy": local_proxy,
}

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider(object):
        pass


class Spider(_BaseSpider):
    def getName(self):
        return "Ksou快搜"

    def init(self, extend=""):
        return ""

    def destroy(self):
        return ""

    def isVideoFormat(self, url):
        try:
            u = str(url or "").lower()
            return u.startswith("http://") or u.startswith("https://")
        except Exception:
            return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return local_proxy(param)

    def homeContent(self, filter=False):
        try:
            return home_content(filter)
        except Exception:
            return {"class": [], "list": []}

    def homeVideoContent(self):
        try:
            return {"list": home_content().get("list", [])}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg="1", filter=False, extend={}):
        try:
            return category_content(tid, pg, filter)
        except Exception:
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "total": 0}

    def detailContent(self, ids):
        try:
            return detail_content(ids)
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            return search_content(key, quick, pg)
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id_=None, vipFlags=None):
        try:
            return play_parse(flag, id_, vipFlags)
        except Exception:
            return {"parse": 1, "url": "", "header": {"User-Agent": UA, "Referer": PLAY_REFERER}}


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    if "--debug" not in sys.argv:
        _DEBUG = False
    if len(sys.argv) > 1:
        cmd, args = sys.argv[1], sys.argv[2:]
        if cmd == "home":
            print(json.dumps(home_content(), ensure_ascii=False)[:4000])
        elif cmd == "cat":
            print(json.dumps(category_content(args[0] if args else "videos",
                                             args[1] if len(args) > 1 else "1"),
                             ensure_ascii=False)[:4000])
        elif cmd == "detail":
            print(json.dumps(detail_content(args), ensure_ascii=False)[:3000])
        elif cmd == "search":
            print(json.dumps(search_content(args[0] if args else ""), ensure_ascii=False)[:3000])
        elif cmd == "play":
            print(json.dumps(play_parse("", args[0] if args else ""), ensure_ascii=False)[:2000])
        else:
            print("unknown cmd:", cmd)
    else:
        print("用法: python3 ksou4.py --selftest [--debug] | home | cat <tid> | detail <id> | search <kw> | play <id>")
