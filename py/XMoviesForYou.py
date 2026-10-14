# coding: utf-8
# ============================================================
# 站点名称: XMoviesForYou
# 前端域名: https://xmoviesforyou.com   （Tailwind 静态 HTML，走 Cloudflare CDN）
# 图片 CDN: https://xmoviescdn.online   （封面 .webp，无防盗链，可直连）
# 站点类型: 成人影片站（长片，HLS .ts 分片，需 Origin 头破防盗链）
# ------------------------------------------------------------
# 结构（已实测 2026-09-29）：
#   分类清单: /categories                       （a[href="/category/{slug}"] + h3）
#   分类列表: /category/{slug}?page=N            （"Page X of Y" 提供总页数）
#   详情页:   /{slug}                            （根路径 slug）
#   搜索:     /search?q={kw}
#   列表卡片: <a href="/{slug}" class="group flex flex-col gap-2"> 内含
#             img.src(xmoviescdn .webp) / h3[title] / span.text-primary(片商) / span(日期)
# ------------------------------------------------------------
# 播放机制（核心，已完整破解）：
#   详情页 JS 内硬编码 const videoId = "179050195804120";
#   GET /api/stream/{videoId}?target=dedi_1
#     -> {"node":"...","url":"https://nodeX.eternalslumber.online/hls/vid_{id}/index.m3u8"}
#   m3u8 + segment_XXX.ts 均需 header  Origin: https://xmoviesforyou.com
#     （缺 Origin 回 403；带 Origin m3u8=200、分片=206 video/mp2t）
#   → parse:0 直连 + header{UA,Origin,Referer}，ExoPlayer 会把 header 套到
#     master/变体/分片全链路；.ts 副檔名可被正确识别，无需代理（避 OOM 法则26）。
# 封面: xmoviescdn.online 无防盗链，直连返回，不走代理。
# 最后验证: 2026-09-29
# 来源: 用户提供 xmoviesforyou.com
# ============================================================
import json
import re
import sys

try:
    import html as _html
    _unescape = _html.unescape
except Exception:
    def _unescape(s):
        return s

from urllib.parse import quote

from base.spider import Spider as BaseSpider

# 静态分类（法则16：零网络、硬编码；数字为站点标注影片数，仅供参考排序）
_CATS = [
    ("brunette", "Brunette"), ("blonde", "Blonde"), ("teen", "Teen"),
    ("milf", "MILF"), ("threesome", "Threesome"), ("interracial", "Interracial"),
    ("redhead", "Redhead"), ("anal", "Anal"), ("lesbian", "Lesbian"),
    ("asian", "Asian"), ("latina", "Latina"), ("tattoo", "Tattoo"),
    ("orgy", "Orgy"),
]

# 列表卡片：锚点 + 块内容（非贪婪吃到第一个 </a>）
_CARD_RE = re.compile(
    r'<a href="(/[^"]+)" class="group flex flex-col gap-2">(.*?)</a>', re.S)
_IMG_RE = re.compile(
    r'src="(https://xmoviescdn\.online/[^"]+\.(?:webp|jpg|jpeg|png))"', re.I)
_TITLE_RE = re.compile(r'title="([^"]*)"')
_STUDIO_RE = re.compile(r'text-primary font-medium truncate[^>]*>([^<]*)<')
_DATE_RE = re.compile(r'<span>([^<]*)</span>')
_PAGE_RE = re.compile(r'Page\s+(\d+)\s+of\s+(\d+)', re.I)
_VIDEOID_RE = re.compile(r'const\s+videoId\s*=\s*"(\d+)"')
_OGTITLE_RE = re.compile(r'<meta property="og:title" content="([^"]*)"')
_OGIMG_RE = re.compile(r'<meta property="og:image" content="([^"]*)"')
_OGDESC_RE = re.compile(r'<meta property="og:description" content="([^"]*)"')
_DETAIL_CAT_RE = re.compile(r'href="/category/([a-z0-9-]+)"')


class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.web = "https://xmoviesforyou.com"
        self.cdn = "https://xmoviescdn.online"
        self.ua = ("Mozilla/5.0 (Linux; Android 14; 22127RK46C/Pixel5) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 "
                   "Mobile Safari/537.36")
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.web + "/",
            "Origin": self.web,
            "Accept": ("text/html,application/xhtml+xml,application/xml;"
                       "q=0.9,image/webp,*/*;q=0.8"),
        }
        # 播放防盗链头（m3u8 + 分片必须带 Origin）
        self.play_hdr = {
            "User-Agent": self.ua,
            "Origin": self.web,
            "Referer": self.web + "/",
        }
        self.classes = [{"type_id": s, "type_name": n} for s, n in _CATS]
        self.filters = {}

    # ---------------- 基础信息 ----------------
    def getName(self):
        return "XMoviesForYou"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        if not url:
            return False
        return bool(re.search(r"\.(m3u8|mp4|flv|ts|mkv|mov|m4v)(\?|$)", url, re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        # 封面无防盗链、播放直连，无需本地代理
        return [404, "text/plain", b""]

    # ---------------- 网络 ----------------
    def _get(self, url, timeout=15):
        """GET 返回 HTML 文本，失败回空串。"""
        u = url if url.startswith("http") else self.web + "/" + url.lstrip("/")
        try:
            r = self.fetch(u, headers=self.headers, timeout=timeout)
            if r and getattr(r, "status_code", 0) == 200:
                return r.text or ""
        except Exception as e:
            self.log({"get_fail": u, "err": str(e)})
        return ""

    def _api_stream(self, video_id):
        """调 /api/stream/{id} 取 m3u8 直链，失败回空串。"""
        vid = str(video_id).strip()
        if not vid:
            return ""
        url = "%s/api/stream/%s?target=dedi_1" % (self.web, quote(vid))
        try:
            r = self.fetch(url, headers=self.headers, timeout=15)
            if r and getattr(r, "status_code", 0) == 200 and r.text:
                data = json.loads(r.text)
                if isinstance(data, dict):
                    return (data.get("url") or "").strip()
        except Exception as e:
            self.log({"stream_fail": url, "err": str(e)})
        return ""

    # ---------------- 卡片解析 ----------------
    def _parse_cards(self, htmltext):
        out = []
        if not htmltext:
            return out
        for m in _CARD_RE.finditer(htmltext):
            href = m.group(1)
            block = m.group(2)
            slug = href.strip("/").split("?", 1)[0]
            # 排除非影片锚点（分类/标签/影星等一般不带此卡片类，双保险）
            if not slug or slug.split("/", 1)[0] in (
                    "category", "categories", "tags", "pornstars", "studios",
                    "search"):
                continue
            tm = _TITLE_RE.search(block)
            name = _unescape(tm.group(1).strip()) if tm else slug
            im = _IMG_RE.search(block)
            pic = im.group(1) if im else ""
            sm = _STUDIO_RE.search(block)
            studio = _unescape(sm.group(1).strip()) if sm else ""
            dm = _DATE_RE.findall(block)
            date = _unescape(dm[-1].strip()) if dm else ""
            remarks = " · ".join([x for x in (studio, date) if x])
            out.append({
                "vod_id": slug,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return out

    @staticmethod
    def _pagecount(htmltext, page):
        m = _PAGE_RE.search(htmltext or "")
        if m:
            try:
                return max(int(m.group(2)), 1)
            except Exception:
                pass
        return page

    # ---------------- 首页 ----------------
    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return {"list": self._parse_cards(self._get(self.web + "/"))}

    # ---------------- 分类/分页 ----------------
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg or 1)
        tid = (tid or "teen").strip().strip("/")
        url = "%s/category/%s" % (self.web, quote(tid))
        if page > 1:
            url += "?page=%d" % page
        htmltext = self._get(url)
        lst = self._parse_cards(htmltext)
        pagecount = self._pagecount(htmltext, page)
        if not lst and page < pagecount:
            pagecount = page
        return {
            "list": lst,
            "page": page,
            "pagecount": pagecount,
            "limit": len(lst) or 24,
            "total": (pagecount * (len(lst) or 24)),
        }

    # ---------------- 详情 ----------------
    @staticmethod
    def _norm_ids(ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        slug = raw.split("$", 1)[0].strip() if "$" in raw else raw
        slug = slug.strip("/").split("?", 1)[0]

        htmltext = self._get(self.web + "/" + quote(slug))

        vm = _VIDEOID_RE.search(htmltext)
        video_id = vm.group(1) if vm else ""

        tm = _OGTITLE_RE.search(htmltext)
        name = _unescape(tm.group(1)) if tm else slug
        name = re.sub(r"\s*-\s*XMoviesForYou\s*$", "", name).strip() or slug
        im = _OGIMG_RE.search(htmltext)
        pic = im.group(1) if im else ""
        dm = _OGDESC_RE.search(htmltext)
        desc = _unescape(dm.group(1)).strip() if dm else ""

        # 分类标签（详情页 /category/{slug} 链接去重）
        cats = []
        for c in _DETAIL_CAT_RE.findall(htmltext):
            if c not in cats:
                cats.append(c)
        tags = ", ".join(cats[:12])
        content = desc or (("标签: " + tags) if tags else "")

        # play id：优先 videoId（纯数字直接调 api），无则回退 slug 让 playerContent 现抓
        play_id = video_id if video_id else slug

        vod = {
            "vod_id": slug,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": content,
            "vod_tag": tags,
            "vod_play_from": "XMoviesForYou",
            "vod_play_url": "正片$" + play_id,
        }
        return {"list": [vod]}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg or 1)
        if page > 1:
            return {"list": [], "page": page}
        htmltext = self._get("%s/search?q=%s" % (self.web, quote(key)))
        return {"list": self._parse_cards(htmltext), "page": page}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "")
        if "$" in raw:
            raw = raw.split("$", 1)[1]
        raw = raw.strip()
        if not raw:
            return {"parse": 1, "url": self.web, "header": self.play_hdr}

        # 纯数字 = videoId，直接调 api；否则当 slug，现抓详情页取 videoId
        if re.fullmatch(r"\d{6,}", raw):
            video_id = raw
        else:
            slug = raw.strip("/").split("?", 1)[0]
            htmltext = self._get(self.web + "/" + quote(slug))
            vm = _VIDEOID_RE.search(htmltext)
            video_id = vm.group(1) if vm else ""

        m3u8 = self._api_stream(video_id) if video_id else ""
        if m3u8:
            # parse:0 直连；header 带 Origin 破防盗链，ExoPlayer 套到全链路含 .ts 分片
            return {"parse": 0, "url": m3u8, "header": self.play_hdr}
        # 兜底交盒子
        return {"parse": 1, "url": self.web, "header": self.play_hdr}

    # ---------------- 推荐 ----------------
    def recommendContent(self, ids, pg):
        return {"list": self._parse_cards(self._get(self.web + "/"))}
