# coding=utf-8
# !/usr/bin/python
"""
FongMi / TVBox T3 (type=3) 爬虫源
站点：375AV  https://375av.com/zh/
类型：MissAV 风格 日本/亚洲/国产 AV 影片站（成人）—— 服务器渲染 HTML + HLS(m3u8) 直链

逆向要点（换站需重做 hex 解码正则与卡片选择器）：
- Cloudflare 前置（server: cloudflare / x-powered-by: Express），盒子原生 self.fetch 通常直接过。
- 反爬核心：真实 HTML body 被 hex 编码后包在每次请求随机命名的 JS 解码函数内，
  形如 document.write(UglURa(unescape(JuiAPZ("<长 hex 串>"))))。
  破解：抓取后用正则取最长 hex 区块 -> bytes.fromhex().decode("utf-8","ignore") 即得真实 HTML。
- 多语言路径前缀 /zh/（en/ja/ko/cn/ms/th... 同构）。
- 列表卡片：div.mgn-item 内 <a href="/zh/movie/detail/{uuid}.html | /zh/guochan/play/{id}"
  title="标题" data-missav-preview="..."> <img class="mgn-cover" src="{.cache}" alt="{番号}">。单页 40 张。
- 封面：https://cache-XXXX.sgvafw.com/base/{base64}.cache（.cache 本身 403 防盗链）；
  base64 解出原图直链（fourhoi.com/{code}/cover-t.jpg 或 video.dage.top/...png），仅需 UA 即 200 -> 直接用。
- 播放：详情/播放页 inline <script> 内 window.videoConfig={...,"url":"...playlist.m3u8?verify=<ts>-<sign>",...}
  两种写法：movie 用 `url: "..."`，guochan 用 `"url":"..."`，同一正则可覆盖。
  m3u8 为标准 master/media 播放列表，无 AES 加密、无广告切片。
  ★防盗链关键：m3cdn.playergo.top 校验 Origin header——缺 Origin 时 playlist.m3u8
  只返回一段 8 秒「域名已更换 55x.cc」公告 TS（video20000.jpeg 伪装）占位；
  带 Origin=站点主域才返回真正 master（360p/480p/720p，各约千余切片正片）。
  故 playerContent header 必带 Origin，parse:0 直接交播放器（ExoPlayer 会透传 header）。
  签名有效期有限故在 playerContent 现取（不缓存到详情）。
- 搜索：GET /zh/keywords/movie/{关键字}（/{page} 翻页），返回同构卡片。
- 分页：路径式 /zh/{path}/{page}（page1=基址，page>1 追加 /{page}）；
  排序 /zh/{path}/sort/{monthly_views|released_at}（/{page} 翻页）。
最后验证：2026-09-30
"""
import sys
import re
import base64
from urllib.parse import quote

sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        def init(self, extend=""):
            pass


class Spider(Spider):
    # ============ 站点信息（换站主要改这里）============
    siteName = "375AV"
    HOST = "https://375av.com"
    LANG = "zh"
    UA = ("Mozilla/5.0 (Linux; Android 14; 22127RK46C/Pixel5) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    # 首页静态分类（法则16：零网络硬编码）
    # tid = /zh/ 之后的相对路径；kind: path=路径式(支持排序) / guochan=国产分类式
    CATS = [
        ("movie/new",              "最近更新", "path"),
        ("menu/uncensored",        "无码A片",  "path"),
        ("menu/chinese-subtitle",  "中文字幕", "path"),
        ("guochan/category/44044", "国产精选", "guochan"),
        ("guochan/category/44001", "制服诱惑", "guochan"),
        ("guochan/category/44002", "国产字幕", "guochan"),
        ("guochan/category/44004", "强奸乱伦", "guochan"),
        ("guochan/category/44005", "熟女人妻", "guochan"),
        ("guochan/category/44010", "AV解说",  "guochan"),
        ("guochan/category/44041", "日本无码", "guochan"),
        ("guochan/category/44048", "女同性恋", "guochan"),
    ]
    # 路径式分类的排序筛选（extend key = "sort"）
    SORTS = [
        {"n": "最新更新", "v": ""},
        {"n": "本月热门", "v": "monthly_views"},
        {"n": "最新发行", "v": "released_at"},
    ]

    # ---------- 生命周期 ----------
    def init(self, extend=""):
        self.extend = extend or ""
        return

    def getName(self):
        return self.siteName

    def isVideoFormat(self, url):
        u = url or ""
        return any(x in u for x in (".m3u8", ".mp4", ".ts", ".flv", ".mkv"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    def getDependence(self):
        return []

    # ---------- HTTP + hex 解码 ----------
    def _headers(self):
        return {
            "User-Agent": self.UA,
            "Referer": self.HOST + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def _get(self, url):
        """抓取并解 hex，返回真实 HTML。"""
        try:
            r = self.fetch(url, headers=self._headers())
            html = r.text or ""
        except Exception:
            return ""
        return self._unhex(html)

    @staticmethod
    def _unhex(html):
        if not html:
            return ""
        try:
            blobs = re.findall(r'"([0-9a-fA-F]{200,})"', html)
            if blobs:
                blob = max(blobs, key=len)
                if len(blob) % 2 == 0:
                    real = bytes.fromhex(blob).decode("utf-8", "ignore")
                    if "<" in real:
                        return real
        except Exception:
            pass
        return html

    # ---------- 解析工具 ----------
    def _pic(self, src):
        """从 .cache 封面链接还原原图直链（仅需 UA 即可达）。"""
        if not src:
            return ""
        m = re.search(r'/base/([A-Za-z0-9_\-]+)\.cache', src)
        if m:
            try:
                s = m.group(1)
                s += "=" * (-len(s) % 4)
                dec = base64.b64decode(s).decode("utf-8", "ignore")
                if dec.startswith("http"):
                    return dec
            except Exception:
                pass
        return src

    def _abs(self, path):
        if not path:
            return ""
        if path.startswith("http"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return self.HOST + path

    def _cards(self, html):
        """解析列表卡片 -> [{vod_id, vod_name, vod_pic, vod_remarks}]。"""
        out, seen = [], set()
        for block in re.split(r'<div class="mgn-item', html)[1:]:
            m_href = re.search(
                r'href="(/[a-z]{2}(?:-[a-z]{2})?/(?:movie/detail/[^"]+?\.html|guochan/play/\d+))"',
                block)
            if not m_href:
                continue
            vid = m_href.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            m_title = re.search(r'title="([^"]*)"', block)
            title = self._clean(m_title.group(1)) if m_title else ""
            m_img = re.search(r'<img[^>]*?src="([^"]*)"', block)
            pic = self._pic(m_img.group(1)) if m_img else ""
            m_alt = re.search(r'alt="([^"]*)"', block)
            remark = (m_alt.group(1) or "").upper().strip() if m_alt else ""
            if not title:
                continue
            out.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return out

    @staticmethod
    def _clean(s):
        s = re.sub(r'<[^>]*>', ' ', s or "")
        for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
                     ("&#39;", "'"), ("&apos;", "'"), ("&nbsp;", " "), ("&amp;", "&")):
            s = s.replace(a, b)
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def _pagecount(html, page, cards):
        m = re.search(r'共\s*(\d+)\s*[頁页]', html)
        if m:
            try:
                return max(int(m.group(1)), page)
            except Exception:
                pass
        # 兜底：满页则推断还有下一页
        return page + 1 if len(cards) >= 20 else page

    # ---------- 首页 ----------
    def homeContent(self, filter):
        classes = [{"type_id": tid, "type_name": name} for (tid, name, _k) in self.CATS]
        filters = {}
        sort_filter = {
            "key": "sort",
            "name": "排序",
            "value": self.SORTS,
        }
        for (tid, _name, kind) in self.CATS:
            if kind == "path":
                filters[tid] = [sort_filter]
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        html = self._get("%s/%s/movie/new" % (self.HOST, self.LANG))
        return {"list": self._cards(html)}

    # ---------- 分类 ----------
    def _kind_of(self, tid):
        for (t, _n, k) in self.CATS:
            if t == tid:
                return k
        return "path"

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        extend = extend or {}
        kind = self._kind_of(tid)
        base = "%s/%s/%s" % (self.HOST, self.LANG, tid)

        if kind == "guochan":
            url = base if page == 1 else "%s/%d" % (base, page)
        else:
            sort = ""
            if isinstance(extend, dict):
                sort = (extend.get("sort") or "").strip()
            if sort:
                base = "%s/sort/%s" % (base, sort)
            url = base if page == 1 else "%s/%d" % (base, page)

        html = self._get(url)
        cards = self._cards(html)
        return {
            "list": cards,
            "page": page,
            "pagecount": self._pagecount(html, page, cards),
            "limit": 40,
            "total": 999999,
        }

    # ---------- 详情 ----------
    def _norm_ids(self, ids):
        if isinstance(ids, (list, tuple)):
            return ids[0] if ids else ""
        return ids or ""

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        html = self._get(self._abs(vid))

        # 标题：优先 h1，退回 videoConfig.title
        title = ""
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            title = self._clean(m.group(1))
        if not title:
            m = re.search(r'["\']?title["\']?\s*:\s*"([^"]+)"', html)
            if m:
                title = self._clean(m.group(1))
        if not title:
            title = self.siteName

        # 封面：videoConfig.img -> 还原直链
        pic = ""
        m = re.search(r'["\']?img["\']?\s*:\s*"([^"]+\.cache)"', html)
        if m:
            pic = self._pic(m.group(1))

        # 番号
        fanhao = ""
        m = re.search(r'["\']?fanhao["\']?\s*:\s*"([^"]+)"', html)
        if m:
            fanhao = m.group(1).upper()

        # 标签（关键字）与分类
        tags = re.findall(r'href="/[a-z]{2}/keywords[^"]*"[^>]*>\s*([^<]+?)\s*<', html)
        tags = [t.strip() for t in tags if t.strip()][:12]
        genres = re.findall(
            r'href="/[a-z]{2}/(?:menu|guochan/category)[^"]*"[^>]*>\s*#?\s*([^<]+?)\s*<', html)
        genres = [g.strip() for g in genres if g.strip() and len(g.strip()) < 12]

        # 简介
        desc = ""
        m = re.search(r'<meta name="description" content="([^"]*)"', html)
        if m:
            desc = self._clean(m.group(1))

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": fanhao,
            "vod_year": "",
            "vod_area": "",
            "vod_actor": "",
            "vod_director": "",
            "type_name": "、".join(dict.fromkeys(genres)),
            "vod_content": desc or "、".join(tags),
            "vod_play_from": self.siteName,
            "vod_play_url": "正片$" + vid,   # 现取直链，故传相对路径给 playerContent
        }
        return {"list": [vod]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        base = "%s/%s/keywords/movie/%s" % (self.HOST, self.LANG, quote(key or ""))
        url = base if page == 1 else "%s/%d" % (base, page)
        html = self._get(url)
        return {"list": self._cards(html), "page": page}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        html = self._get(self._abs(id))
        url = ""
        m = re.search(r'["\']?url["\']?\s*:\s*"(https?://[^"]+?\.m3u8[^"]*)"', html)
        if m:
            url = m.group(1)
        if not url:
            # 兜底：页面任意 m3u8 直链
            m = re.search(r'(https?://[^"\'\s]+?\.m3u8[^"\'\s]*)', html)
            if m:
                url = m.group(1)
        # 关键：m3cdn.playergo.top 防盗链校验 Origin —— 缺 Origin 会返回一段
        # 8 秒「域名已更换」公告 TS 占位；带 Origin=站点主域才返回完整正片 master。
        header = {
            "User-Agent": self.UA,
            "Referer": self.HOST + "/",
            "Origin": self.HOST,
        }
        if not url:
            return {"parse": 1, "url": self._abs(id), "header": header}
        return {"parse": 0, "url": url, "header": header}

    def localProxy(self, param):
        return [200, "text/plain", {}, b""]
