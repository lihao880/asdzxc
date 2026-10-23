import base64
import binascii
import html as _html
import json
import re
import ssl
import time
import urllib.parse
import urllib.request

_PROXY_B64 = (
    "aHR0cHM6Ly84OTc0NTYyMTIzLjg4ODg4ODg4"
    "ODg4ODg4ODg4ODg4ODg4ODg4ODg4ODg4ODg4"
    "LmNjd3UuY2MvP3VybD0="
)


def _cfg(b64_str):
    try:
        return base64.b64decode(b64_str.encode("ascii")).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return ""


try:
    _CTX = ssl.create_default_context()
    _CTX.check_hostname = False
    _CTX.verify_mode = ssl.CERT_NONE
    try:
        _CTX.set_ciphers("DEFAULT:@SECLEVEL=0")
    except Exception:
        pass
except Exception:
    _CTX = None

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def fetch(self, url, headers=None, timeout=20):
            req = urllib.request.Request(url, headers=headers or {})
            return urllib.request.urlopen(req, timeout=timeout, context=_CTX)

        def html(self, content):
            return None


class Spider(BaseSpider):
    def __init__(self):
        self.name = "人妖影视"
        self.host = "https://www.shemaletubevideos.com"
        self.proxy = _cfg(_PROXY_B64)
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.page_size = 40
        self.sorts = [
            {"n": "最热", "v": "popular"},
            {"n": "最新", "v": "recent"},
            {"n": "最多播放", "v": "view"},
            {"n": "最高评分", "v": "rate"},
            {"n": "最长", "v": "length"},
        ]
        self.cats = []
        self.counts = {}
        self.pic_cache = {}
        self.extend = ""
        self._last = 0.0
        self._headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
        }

    def init(self, extend=""):
        self.extend = extend
        ext = str(extend or "").strip()
        if ext.startswith("{"):
            try:
                cfg = json.loads(ext)
            except Exception:
                cfg = {}
            if isinstance(cfg, dict):
                host = str(cfg.get("host") or "").strip().rstrip("/")
                if host:
                    if not host.startswith("http"):
                        host = "https://" + host
                    self.host = host
                    self._headers["Referer"] = host + "/"
                px = str(cfg.get("proxy") or "").strip()
                if px:
                    if "?url=" not in px:
                        px = px.rstrip("/") + "/?url="
                    self.proxy = px
        return {}

    def getName(self):
        return self.name

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        if not url:
            return False
        u = str(url).lower()
        return (".mp4" in u or ".m3u8" in u or ".flv" in u
                or ".ts" in u or "ccwu.cc" in u)

    def manualVideoCheck(self):
        return False

    def liveContent(self, url=""):
        return ""

    def action(self, action):
        return None

    def destroy(self):
        self.cats = []
        self.counts = {}
        self.pic_cache = {}
        return "已销毁"

    def _throttle(self):
        now = time.time()
        gap = now - self._last
        if gap < 0.3:
            time.sleep(0.3 - gap)
        self._last = time.time()

    def _open(self, url, referer=None, timeout=15, post=None):
        headers = dict(self._headers)
        if referer:
            headers["Referer"] = referer
        data = None
        if post:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            data = urllib.parse.urlencode(post).encode()
        req = urllib.request.Request(url, headers=headers, data=data)
        resp = urllib.request.urlopen(req, timeout=timeout, context=_CTX)
        return resp.read()

    def _fetch(self, path, referer=None, retry=3):
        target = path if str(path).startswith("http") else (self.host + path)
        plans = []
        if self.proxy:
            plans.append((self.proxy + urllib.parse.quote(target, safe=""), retry, 20))
        plans.append((target, 1, 8))
        for url, tries, timeout in plans:
            for _ in range(tries):
                self._throttle()
                try:
                    raw = self._open(url, referer, timeout)
                    if raw and len(raw) > 2500:
                        return raw.decode("utf-8", errors="ignore")
                except Exception:
                    time.sleep(0.4)
        return ""

    def _unwrap(self, url):
        raw = str(url or "").strip()
        if not raw:
            return ""
        if "?url=" in raw:
            tail = raw.split("?url=", 1)[1]
            try:
                tail = urllib.parse.unquote(tail)
            except Exception:
                pass
            if tail.startswith("http"):
                return tail
        if self.proxy and raw.startswith(self.proxy):
            tail = raw[len(self.proxy):]
            try:
                tail = urllib.parse.unquote(tail)
            except Exception:
                pass
            if tail.startswith("http"):
                return tail
        if raw.startswith("https%3A") or raw.startswith("http%3A"):
            try:
                tail = urllib.parse.unquote(raw)
            except Exception:
                return raw
            if tail.startswith("http"):
                return tail
        return raw

    def _wrap(self, url):
        raw = self._unwrap(url)
        if not raw:
            return ""
        if raw.startswith("//"):
            raw = "https:" + raw
        elif raw.startswith("/"):
            raw = self.host + raw
        if not raw.startswith("http"):
            return raw
        if not self.proxy:
            return raw
        if "shemaletubevideos.com" not in raw:
            return raw
        return self.proxy + urllib.parse.quote(raw, safe="")

    def _link(self, href):
        raw = self._unwrap(href)
        return raw.split("?")[0] if "?x=" in raw or "?view=" in raw else raw

    @staticmethod
    def _clean(text):
        value = re.sub(r"<script.*?</script>", " ", str(text or ""), flags=re.S)
        value = re.sub(r"<[^>]+>", " ", value)
        value = _html.unescape(value.replace("&nbsp;", " "))
        return re.sub(r"\s+", " ", value).strip()

    def _scan_categories(self):
        if self.cats:
            return self.cats
        html = self._fetch("/categories/")
        cats = []
        seen = set()
        for m in re.finditer(
                r'<div class="thumb"><h3><a href="([^"]+?)"[^>]*>([^<]+)</a></h3>',
                html):
            path = urllib.parse.unquote(m.group(1))
            name = self._clean(m.group(2))
            mm = re.search(r"/videos/(?:shemale|all)/([a-z0-9]+)-popular\.html", path)
            if not mm or not name:
                continue
            slug = mm.group(1)
            if slug in seen:
                continue
            seen.add(slug)
            cm = re.search(r"Videos \((\d+)\)", html[m.end():m.end() + 1600])
            cats.append({"type_id": slug, "type_name": name})
            self.counts[slug] = int(cm.group(1)) if cm else 0
        self.cats = cats
        return cats

    def _classes(self):
        cls = [{"type_id": "home", "type_name": "首页最新"},
               {"type_id": "all", "type_name": "全部视频"}]
        cls.extend(self._scan_categories())
        return cls

    def _filters(self):
        val = [{"n": "全部", "v": "all"}]
        for c in self._scan_categories():
            val.append({"n": c["type_name"], "v": c["type_id"]})
        out = {}
        for c in self._classes():
            out[c["type_id"]] = [
                {"key": "cat", "name": "分类筛选", "value": val},
                {"key": "sort", "name": "排序", "value": self.sorts},
            ]
        return out

    def homeContent(self, filter=False):
        return {"class": self._classes(), "filters": self._filters()}

    def homeVideoContent(self):
        html = self._fetch("/")
        return {"list": self._cards(html)[:60]}

    @staticmethod
    def _scope(html):
        if not html:
            return ""
        i = html.find('<div class="thumbs-wrap">')
        if i < 0:
            return ""
        j = html.find("pages2-wrap", i)
        return html[i:j if j > 0 else len(html)]

    def _cards(self, html):
        items = []
        seg = self._scope(html)
        if not seg:
            return items
        for blk in re.split(r'<div class="th">', seg)[1:]:
            hm = re.search(r'href="([^"]+?)"', blk)
            if not hm:
                continue
            vid = self._vid_of(self._link(hm.group(1)))
            if not vid:
                continue
            title = ""
            tm = re.search(r'class="ha">([^<]*)</a>', blk)
            if tm:
                title = self._clean(tm.group(1))
            pic = ""
            pm = re.search(r'<img[^>]*src="([^"]+)"', blk)
            if not pm:
                pm = re.search(r'<img[^>]*data-src="([^"]+)"', blk)
            if pm:
                pic = pm.group(1).strip()
            if not title:
                am = re.search(r'alt="([^"]*)"', blk)
                if am:
                    title = self._clean(am.group(1))
            dur = ""
            dm = re.search(r'class="lenght">([^<]*)<', blk)
            if dm:
                dur = dm.group(1).strip()
            views = ""
            vm = re.search(r'class="views">\s*([^<]*?)\s*<', blk)
            if vm:
                views = self._clean(vm.group(1))
            ago = ""
            gm = re.search(r'class="ago">([^<]*)<', blk)
            if gm:
                ago = self._clean(gm.group(1))
            rate = ""
            rm = re.search(r'flag-rating">([^<]*)<', blk)
            if rm:
                rate = rm.group(1).strip()
            bits = []
            for bit in (rate, views, ago):
                if bit:
                    bits.append(bit)
            remarks = (dur + " · " if dur else "") + " · ".join(bits)
            if pic:
                self.pic_cache[vid] = pic
            items.append({
                "vod_id": vid,
                "vod_name": title or vid,
                "vod_pic": self._wrap(pic),
                "vod_remarks": remarks,
            })
        if len(self.pic_cache) > 1200:
            self.pic_cache = dict(list(self.pic_cache.items())[-600:])
        return items

    @staticmethod
    def _vid_of(href):
        if not href:
            return ""
        path = href.split("?")[0]
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[-2] == "video":
            token = parts[-1]
            return token[:-5] if token.endswith(".html") else token
        if len(parts) >= 4 and parts[-4] == "click" and parts[-3] == "video":
            return "%s-%s" % (parts[-1], parts[-2])
        return ""

    def _pagecount(self, html, pg, slug):
        cnt = self.counts.get(slug or "")
        if cnt:
            return max((cnt + self.page_size - 1) // self.page_size, pg)
        if html:
            i = html.find("pages2-wrap")
            if i > 0:
                seg = html[i:i + 3000]
                nums = [int(n) for n in re.findall(r">(\d+)</a>", seg)]
                if nums:
                    top = max(nums)
                    return max(top + 1 if "pagern" in seg else top, pg)
        return pg + 1 if html else pg

    def _list_path(self, slug, sort, pg):
        pool = "all" if slug == "all" else "shemale"
        name = "%s-%s" % (slug if slug == "all" else slug, sort)
        if pg > 1:
            name += "-%d" % pg
        return "/videos/%s/%s.html" % (pool, name)

    def categoryContent(self, tid, pg, filter=False, extend=""):
        tid = str(tid or "").strip() or "home"
        try:
            pg = int(pg) if pg else 1
        except Exception:
            pg = 1
        pg = max(1, pg)
        ext = extend
        if isinstance(ext, str) and ext.strip().startswith("{"):
            try:
                ext = json.loads(ext)
            except Exception:
                ext = {}
        if not isinstance(ext, dict):
            ext = {}
        sub = str(ext.get("cat") or "").strip()
        sort = str(ext.get("sort") or "").strip()
        if sort not in ("popular", "recent", "view", "rate", "length"):
            sort = "popular"
        if tid == "home":
            items = self._cards(self._fetch("/"))
            return {"list": items[:60], "page": 1, "pagecount": 1,
                    "limit": len(items[:60]), "total": len(items[:60]),
                    "parse": 0, "jx": 0}
        slug = sub if (sub and sub != "all") else tid
        if slug not in ("all", "home") and slug not in self.counts:
            slug = tid if tid in self.counts else "all"
        html = self._fetch(self._list_path(slug, sort, pg))
        items = self._cards(html)
        pc = self._pagecount(html, pg, slug) if items else pg
        return {"list": items, "page": pg, "pagecount": pc,
                "limit": self.page_size, "total": pc * self.page_size,
                "parse": 0, "jx": 0}

    def _detail_html(self, vid):
        html = self._fetch("/video/%s.html" % vid, referer=self.host + "/")
        if html and "<source" in html:
            return html
        token = vid.rsplit("-", 1)[-1]
        if token and token != vid:
            for alt_path in ("/click/video/%s/x" % token,
                             "/click/video/%s/_/" % token):
                alt = self._fetch(alt_path, referer=self.host + "/")
                if alt and "<source" in alt:
                    return alt
        return html

    def _sources(self, html):
        out = []
        for m in re.finditer(
                r'<source[^>]*data-res="([^"]+)"[^>]*src="([^"]+)"', html):
            out.append((m.group(1).strip(), m.group(2).strip()))
        for m in re.finditer(
                r'<source[^>]*src="([^"]+)"[^>]*data-res="([^"]+)"', html):
            out.append((m.group(2).strip(), m.group(1).strip()))
        for m in re.finditer(r"<li>Download: </li>([\s\S]*?)</ul>", html):
            for a in re.finditer(r'<a href="([^"]+\.mp4)">([^<]+)</a>', m.group(1)):
                out.append((a.group(2).strip(), a.group(1).strip()))
        seen = set()
        res = []
        for label, url in out:
            url = url.replace("\\/", "/")
            if not url.startswith("http"):
                continue
            key = url.split("/")[-1]
            if key in seen:
                continue
            seen.add(key)
            res.append((label or "正片", url))
        return res

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        vid = self._vid_of(str(raw)) or str(raw or "").strip()
        vid = vid.replace(".html", "")
        if not vid:
            return {"list": [], "parse": 0, "jx": 0}
        html = self._detail_html(vid)
        if not html:
            return {"list": [], "parse": 0, "jx": 0}
        title = ""
        tm = re.search(r"<h1><span>(.*?)</span></h1>", html, re.S)
        if tm:
            title = self._clean(tm.group(1))
        if not title:
            tm = re.search(r"<title>(.*?)</title>", html, re.S)
            if tm:
                title = self._clean(tm.group(1)).split(" - ")[0]
        pic = ""
        pm = re.search(r'<video[^>]*poster="([^"]+)"', html)
        if pm:
            pic = pm.group(1).strip()
        if not pic:
            vm = re.search(r"var videodir\s*=\s*'([^']+)'", html)
            if vm:
                pic = vm.group(1).strip() + "main.jpg"
        if not pic:
            pic = self.pic_cache.get(vid, "")
        desc = ""
        dm = re.search(r"<strong>Description:</strong><br />([\s\S]*?)<BR><BR>", html)
        if dm:
            desc = self._clean(dm.group(1))
        dur = ""
        dm2 = re.search(r"<td>Time: </td>\s*<td><span>([^<]+)</span>", html)
        if dm2:
            dur = dm2.group(1).strip()
        views = ""
        vw = re.search(r"<td>Views: </td>\s*<td><span>([^<]+)</span>", html)
        if vw:
            views = self._clean(vw.group(1))
        actor = ""
        am = re.search(r'class="aupa">([^<]+)</a>', html)
        if am:
            actor = self._clean(am.group(1))
        added = ""
        ad = re.search(r"Added: <strong>([^<]+)</strong>", html)
        if ad:
            added = self._clean(ad.group(1))
        year = ""
        ym = re.search(r"(\d{4})", added)
        if ym:
            year = ym.group(1)
        cats = []
        cm = re.search(r"<li>Categories: </li>([\s\S]*?)</ul>", html)
        if cm:
            for n in re.findall(r">([^<]+)</a>", cm.group(1)):
                n = self._clean(n)
                if n and n not in cats:
                    cats.append(n)
        tags = []
        tg = re.search(r"<li>Tags: </li>([\s\S]*?)</ul>", html)
        if tg:
            for n in re.findall(r">([^<]+)</a>", tg.group(1)):
                n = self._clean(n)
                if n and n not in tags:
                    tags.append(n)
        lines = []
        seen = set()
        for label, url in self._sources(html):
            ln = "%s$%s" % (label, self._wrap(url))
            if ln not in seen:
                seen.add(ln)
                lines.append(ln)
        bits = []
        for bit in (dur, (views + " Views") if views else "", added):
            if bit:
                bits.append(bit)
        vod = {
            "vod_id": vid,
            "vod_name": title or vid,
            "vod_pic": self._wrap(pic),
            "type_name": " · ".join((cats + tags)[:8]),
            "vod_year": year,
            "vod_area": "",
            "vod_lang": "",
            "vod_actor": actor,
            "vod_director": actor,
            "vod_content": desc or " ".join(tags),
            "vod_remarks": " · ".join(bits),
            "vod_play_from": "人妖直链",
            "vod_play_url": "#".join(lines),
        }
        return {"list": [vod], "parse": 0, "jx": 0}

    def playerContent(self, flag, id, vipFlags=None):
        header = {"User-Agent": self.ua, "Referer": self.host + "/"}
        raw = str(id or "").strip()
        if not raw:
            return {"parse": 0, "playUrl": "", "url": "", "header": header, "jx": 0}
        if self.proxy and raw.startswith(self.proxy):
            return {"parse": 0, "playUrl": "", "url": raw, "header": header, "jx": 0}
        inner = self._unwrap(raw)
        low = inner.lower().split("?")[0]
        if low.endswith((".mp4", ".m3u8", ".flv", ".ts")):
            return {"parse": 0, "playUrl": "", "url": self._wrap(inner),
                    "header": header, "jx": 0}
        vid = self._vid_of(inner) or inner.replace(".html", "")
        src = self._sources(self._detail_html(vid))
        best = ""
        if flag:
            for label, url in src:
                if label == flag:
                    best = url
                    break
        if not best:
            for want in ("1080p", "720p", "480p", "360p"):
                for label, url in src:
                    if label == want:
                        best = url
                        break
                if best:
                    break
        if not best and src:
            best = src[0][1]
        if best:
            return {"parse": 0, "playUrl": "", "url": self._wrap(best),
                    "header": header, "jx": 0}
        return {"parse": 1, "playUrl": "", "url": self.host + "/",
                "header": header, "jx": 0}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg) if pg else 1
        except Exception:
            pg = 1
        pg = max(1, pg)
        kw = str(key or "").strip()
        if not kw:
            return {"list": [], "page": pg, "pagecount": pg,
                    "limit": 0, "total": 0, "parse": 0, "jx": 0}
        seg = urllib.parse.quote(kw, safe="").replace("%20", "+")
        path = "/search/video/%s/" % seg
        if pg > 1:
            path += "%d/" % pg
        html = self._fetch(path, referer=self.host + "/search/")
        items = self._cards(html)
        pc = pg + 1 if items else pg
        nums = [int(n) for n in re.findall(r"/search/video/[^\"']*?/(\d+)/", html)]
        if nums:
            pc = max(max(nums), pg)
        return {"list": items, "page": pg, "pagecount": pc,
                "limit": self.page_size, "total": pc * self.page_size,
                "parse": 0, "jx": 0}

    def searchContentPage(self, key, quick=False, pg="1"):
        return self.searchContent(key, quick, pg)

    def localProxy(self, param):
        if not param:
            return None
        url = param.get("url") if isinstance(param, dict) else param
        url = str(url or "").strip()
        if not url.startswith("http"):
            return None
        try:
            raw = self._open(url, self.host + "/", 20)
            if not raw:
                return None
            mime = "image/jpeg"
            if raw[:8] == b"\x89PNG\r\n\x1a\n":
                mime = "image/png"
            elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
                mime = "image/webp"
            elif raw[:3] == b"GIF":
                mime = "image/gif"
            elif raw[4:8] == b"ftyp":
                mime = "video/mp4"
            elif raw[:7] == b"#EXTM3U":
                mime = "application/vnd.apple.mpegurl"
            return [200, mime, raw]
        except Exception:
            return None


if __name__ == "__main__":
    sp = Spider()
    sp.init("")
    ok = True

    def check(name, cond, extra=""):
        global ok
        print(("PASS " if cond else "FAIL ") + name +
              (("  -> " + str(extra)[:100]) if extra else ""))
        if not cond:
            ok = False

    print("host  =", sp.host)
    print("proxy =", sp.proxy)
    cats = sp._scan_categories()
    check("分类抓取 >= 40 项", len(cats) >= 40, "n=%d" % len(cats))
    check("分类 slug/名 完整",
          all(c["type_id"] and c["type_name"] for c in cats),
          cats[0] if cats else "-")
    hc = sp.homeContent(True)
    check("homeContent class", len(hc["class"]) >= 42,
          "class=%d" % len(hc["class"]))
    check("每个分类都挂筛选器",
          len(hc["filters"]) == len(hc["class"]),
          "filters=%d" % len(hc["filters"]))
    fv = hc["filters"].get(cats[0]["type_id"]) if cats else None
    check("筛选器 = 分类 + 排序", bool(fv) and len(fv) == 2,
          [b["name"] for b in (fv or [])])

    hv = sp.homeVideoContent()
    check("首页最新列表", len(hv["list"]) > 0, "n=%d" % len(hv["list"]))

    slug = cats[0]["type_id"] if cats else "anal"
    cc = sp.categoryContent(slug, "1", False, "")
    lst = cc["list"]
    check("父分类第 1 页", len(lst) > 0,
          "n=%d pagecount=%s" % (len(lst), cc["pagecount"]))
    check("卡片 id/标题/封面",
          all(v["vod_id"] and v["vod_name"] for v in lst) and
          any(v["vod_pic"] for v in lst),
          lst[0]["vod_name"][:32] if lst else "-")
    pics = [v["vod_pic"] for v in lst[:5] if v["vod_pic"]]
    check("封面地址已套全局代理",
          bool(pics) and all(p.startswith(sp.proxy) for p in pics),
          pics[0][:70] if pics else "-")
    check("pagecount > 1", cc["pagecount"] > 1, str(cc["pagecount"]))
    cc2 = sp.categoryContent(slug, "2", False, "")
    i1 = set(v["vod_id"] for v in lst)
    i2 = set(v["vod_id"] for v in cc2["list"])
    check("分页不重复", len(i1 & i2) == 0, "p1=%d p2=%d" % (len(i1), len(i2)))
    cc3 = sp.categoryContent(slug, "1", False, json.dumps({"sort": "recent"}))
    check("排序筛选生效",
          len(cc3["list"]) > 0 and set(v["vod_id"] for v in cc3["list"]) != i1,
          "n=%d" % len(cc3["list"]))
    cc4 = sp.categoryContent("all", "1", False, json.dumps({"sort": "view"}))
    check("全部视频池可遍历", len(cc4["list"]) > 0, "n=%d" % len(cc4["list"]))
    if len(cats) > 1:
        cc5 = sp.categoryContent(slug, "1", False,
                                 json.dumps({"cat": cats[1]["type_id"]}))
        check("父分类内切子分类", len(cc5["list"]) > 0,
              "n=%d -> %s" % (len(cc5["list"]), cats[1]["type_name"]))
    for c in cats[:6]:
        r = sp.categoryContent(c["type_id"], "1", False, "")
        check("遍历子分类 %s" % c["type_name"], len(r["list"]) > 0,
              "n=%d" % len(r["list"]))

    vid = lst[0]["vod_id"] if lst else ""
    dc = sp.detailContent([vid])
    vod = (dc["list"] or [{}])[0]
    check("详情：标题", bool(vod.get("vod_name")), vod.get("vod_name", "")[:36])
    check("详情：简介/分类",
          bool(vod.get("vod_content") or vod.get("type_name")),
          (vod.get("type_name") or vod.get("vod_content") or "-")[:44])
    check("详情：年份/演员",
          bool(vod.get("vod_year") or vod.get("vod_actor")),
          "year=%s actor=%s" % (vod.get("vod_year"), vod.get("vod_actor")))
    check("详情：封面补齐", bool(vod.get("vod_pic")), (vod.get("vod_pic") or "")[:70])
    check("详情：播放链", "$" in (vod.get("vod_play_url") or ""),
          (vod.get("vod_play_url") or "")[:70])

    first = (vod.get("vod_play_url") or "").split("#")[0]
    line = first.split("$")[-1] if "$" in first else first
    pc = sp.playerContent((vod.get("vod_play_from") or ""), line, [])
    check("播放：parse=0 直连", pc.get("parse") == 0 and bool(pc.get("url")),
          (pc.get("url") or "")[:80])
    pc2 = sp.playerContent("720p", vid, [])
    check("播放：传 vid 取直连",
          pc2.get("parse") == 0 and ".mp4" in (pc2.get("url") or ""),
          (pc2.get("url") or "")[:80])

    sc = sp.searchContent("ladyboy", False, "1")
    check("搜索：有结果", len(sc["list"]) > 0, "n=%d" % len(sc["list"]))
    sc2 = sp.searchContent("ladyboy", False, "2")
    s1 = set(v["vod_id"] for v in sc["list"])
    s2 = set(v["vod_id"] for v in sc2["list"])
    check("搜索分页不重复", len(s1 & s2) == 0, "p1=%d p2=%d" % (len(s1), len(s2)))
    sc3 = sp.searchContent("big tits", False, "1")
    check("搜索：多词关键词", len(sc3["list"]) > 0, "n=%d" % len(sc3["list"]))

    pic = vod.get("vod_pic") or ""
    if pic:
        r = sp.localProxy({"type": "pic", "url": pic})
        check("封面代理可取", bool(r) and r[0] == 200 and len(r[2]) > 800,
              r[1] if r else "-")

    print("\n==== %s ====" % ("ALL PASS" if ok else "HAS FAILURES"))
