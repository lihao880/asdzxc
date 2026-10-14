# -*- coding: utf-8 -*-
# 接口源码分享QQ交流群:212706934
import re, json, urllib.parse, requests
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    BASE = 'http://www.xcbi.cn'
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

    DETAIL_RX = r'href="([^"]*?(?:/\d{3,}/|[?&](?:id|vid|vod_id|vodid)=\d+)[^"]*?)"'

    CATS = [
        {"type_id": "dy",     "type_name": "电影"},
        {"type_id": "tv",     "type_name": "电视"},
        {"type_id": "dm",     "type_name": "动漫"},
        {"type_id": "zongyi", "type_name": "综艺"},
    ]

    R_PLAY = r'(https?://[^\s"\'<>\\]+?\.(?:m3u8|mp4)[^\s"\'<>\\]*)'

    # ---------------------------------------------------------------
    # 基础方法
    # ---------------------------------------------------------------
    def init(self, extend=""):
        self.extend = extend or ""

    def getName(self):
        return "XCBI"

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def _clean(self, t):
        if not t:
            return ""
        t = t.replace("\ufeff", "")
        return re.sub(r"<\?xml[^>]*?\?>", "", t, count=1)

    def _get(self, url, referer=None):
        h = {"User-Agent": self.UA}
        if referer:
            h["Referer"] = referer
        try:
            r = requests.get(url, headers=h, timeout=15)
            enc = r.encoding
            if not enc or enc.lower() in ("iso-8859-1", "ascii", "latin-1"):
                enc = r.apparent_encoding or "utf-8"
            r.encoding = enc
            text = r.text
            if text.count("\ufffd") > 20:
                best = text
                for try_enc in ("gbk", "gb2312", "utf-8", "big5"):
                    try:
                        r.encoding = try_enc
                        t2 = r.text
                        if t2.count("\ufffd") < best.count("\ufffd"):
                            best = t2
                    except Exception:
                        continue
                text = best
            return self._clean(text)
        except Exception:
            return ""

    # ---------------------------------------------------------------
    # 首页分类
    # ---------------------------------------------------------------
    def homeContent(self, filter):
        return {"class": self.CATS}

    def homeVideoContent(self):
        return {"list": []}

    # ---------------------------------------------------------------
    # 分类内容
    # ---------------------------------------------------------------
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        tid_path = str(tid).replace("_", "/")

        candidates = []
        if pg == 1:
            candidates += [
                self.BASE + "/" + tid_path + "/",
                self.BASE + "/" + tid_path,
                self.BASE + "/list/" + tid_path + "/",
                self.BASE + "/vodshow/" + tid_path + "/",
            ]
        candidates += [
            self.BASE + "/" + tid_path + "/page/" + str(pg) + "/",
            self.BASE + "/" + tid_path + "/index_" + str(pg) + ".html",
            self.BASE + "/" + tid_path + "/" + str(pg) + ".html",
            self.BASE + "/" + tid_path + "/list_" + str(pg) + ".html",
            self.BASE + "/" + tid_path + "/page_" + str(pg) + ".html",
            self.BASE + "/" + tid_path + "/?page=" + str(pg),
            self.BASE + "/" + tid_path + "?page=" + str(pg),
        ]

        for url in candidates:
            try:
                html = self._get(url, referer=self.BASE)
                if not html:
                    continue
                r = self._parse(html, pg)
                if r["list"]:
                    return r
            except Exception:
                continue

        return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

    # ---------------------------------------------------------------
    # 搜索
    # ---------------------------------------------------------------
    def searchContent(self, key, quick, pg=1):
        pg = int(pg) if str(pg).isdigit() else 1
        url = self.BASE + '/?wd=' + urllib.parse.quote(key)
        if pg > 1:
            url += '&page=' + str(pg)
        html = self._get(url, referer=self.BASE)
        return self._parse(html, pg)

    # ---------------------------------------------------------------
    # 列表解析
    # ---------------------------------------------------------------
    def _parse(self, html, pg):
        items = []
        seen = set()

        for m in re.finditer(self.DETAIL_RX, html):
            href = m.group(1)
            if not href:
                continue
            # 排除明显的分类/列表链接
            if re.search(r"/(?:list|type|category|vodshow|vodtype|search)/", href, re.I):
                continue
            if href in seen:
                continue
            seen.add(href)

            pos = m.start()
            frag = html[max(0, pos - 300): min(len(html), m.end() + 600)]

            name = self._try(frag, [
                r'title="([^"]{1,80})"',
                r'alt="([^"]{1,80})"',
                r'<h[1-4][^>]*>\s*([^<]{1,80}?)\s*</h[1-4]>',
                r'<a[^>]*>\s*([^<]{2,80}?)\s*</a>',
            ], self._vname)
            if not name:
                continue

            pic = self._try(frag, [
                r'<img[^>]+data-src="([^"]+)"',
                r'<img[^>]+data-original="([^"]+)"',
                r'<img[^>]+src="([^"]+)"',
            ], self._vpic)

            rem = self._try(frag, [
                r'<span[^>]*class="[^"]*(?:module-item-text|note|pic-text|tag|status|play-text|score)[^"]*"[^>]*>\s*([^<]{1,30}?)\s*</span>',
                r'<em[^>]*>\s*([^<]{1,30}?)\s*</em>',
                r'<span[^>]*>\s*([^<]{1,30}?(?:集|话|更新|完结|HD|BD|超清|高清|抢先|预告|全集))\s*</span>',
            ], lambda v: 1 <= len(v.strip()) <= 30)

            items.append({
                "vod_id": href.lstrip("/").rstrip("/"),
                "vod_name": name,
                "vod_pic": self._abs(pic),
                "vod_remarks": rem or "",
            })

        pagecount = self._detect_pagecount(html, pg)
        return {"list": items, "page": pg, "pagecount": pagecount,
                "limit": len(items), "total": pagecount * max(len(items), 1)}

    def _detect_pagecount(self, html, cur_pg):
        for pat in [
            r'共\s*(\d+)\s*页',
            r'/(?:page|index_|list_)(\d+)\.html[^>]*>\s*尾页',
            r'第\s*\d+\s*/\s*(\d+)\s*页',
        ]:
            m = re.search(pat, html)
            if m and m.groups():
                try:
                    n = int(m.group(1))
                    if n > 0:
                        return n
                except Exception:
                    pass
        return cur_pg + 5

    # ---------------------------------------------------------------
    # 详情页
    # ---------------------------------------------------------------
    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        url = self.BASE + "/" + str(vid).strip("/") + "/"
        html = self._get(url, referer=self.BASE)

        d = {"vod_id": vid}

        d["vod_name"] = self._try(html, [
            r'property="og:title"\s+content="([^"]{1,80})"',
            r'<h1[^>]*>\s*([^<]{1,80}?)\s*</h1>',
            r'<title>([^<|_\-]{1,80})',
        ], self._vname)

        pic = self._try(html, [
            r'property="og:image"\s+content="([^"]+)"',
            r'<img[^>]+data-src="([^"]+)"',
            r'<img[^>]+src="([^"]+)"',
        ], self._vpic)
        d["vod_pic"] = self._abs(pic)

        c = self._try(html, [
            r'property="og:description"\s+content="([^"]{10,})"',
            r'<div[^>]*class="[^"]*(?:desc|intro|content)[^"]*"[^>]*>(.*?)</div>',
        ], lambda x: True, strip=True)
        d["vod_content"] = c

        d["vod_actor"] = self._try(html, [
            r'主演[：:\s]*[^>]*>\s*([^<\n]{1,200})'
        ], lambda x: 0 < len(self._strip(x)) < 200, strip=True)

        d["vod_director"] = self._try(html, [
            r'导演[：:\s]*[^>]*>\s*([^<\n]{1,100})'
        ], lambda x: 0 < len(self._strip(x)) < 100, strip=True)

        # ---------- 播放地址解析（完整提取所有集数）----------
        play_from, play_url = self._parse_playlist(html)

        d["vod_play_from"] = play_from if play_from else "默认"
        d["vod_play_url"] = play_url if play_url else ""

        return {"list": [d]}

    def _parse_playlist(self, html):
        """
        提取所有剧集播放地址，返回 (play_from, play_url) 字符串。
        play_url 格式: 第01集$http://xxx.m3u8#第02集$http://xxx.m3u8
        """
        # 方式1：直接提取 m3u8/mp4 链接列表
        urls = re.findall(self.R_PLAY, html)
        if urls:
            # 去重保序
            seen = set()
            uniq = []
            for u in urls:
                u = u.strip()
                if u not in seen:
                    seen.add(u)
                    uniq.append(u)

            if len(uniq) == 1:
                # 单集：电影或单片
                return "默认", "正片$" + uniq[0]

            # 多集：生成 第01集$url 格式
            parts = []
            for idx, u in enumerate(uniq, 1):
                ep_name = "第%02d集" % idx
                parts.append(ep_name + "$" + u)
            return "默认", "#".join(parts)

        # 方式2：从JSON配置中提取（常见于某些CMS）
        m = re.search(r'"url"\s*:\s*"([^"]+\.(?:m3u8|mp4)[^"]*)"', html, re.S)
        if m:
            return "默认", "正片$" + m.group(1)

        m = re.search(r'"video"\s*:\s*"([^"]+\.(?:m3u8|mp4)[^"]*)"', html, re.S)
        if m:
            return "默认", "正片$" + m.group(1)

        return "", ""

    # ---------------------------------------------------------------
    # 播放解析
    # ---------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags):
        # id 可能是 "第01集$http://xxx.m3u8" 或直接是 URL
        url = id
        if "$" in id:
            url = id.split("$", 1)[1]

        # 如果 url 本身是 m3u8/mp4，直接返回
        if self.isVideoFormat(url):
            return {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": json.dumps({"User-Agent": self.UA}),
            }

        # 否则尝试作为页面地址解析
        html = self._get(url, referer=self.BASE)
        m = re.search(self.R_PLAY, html)
        if m:
            return {
                "parse": 0,
                "playUrl": "",
                "url": m.group(1),
                "header": json.dumps({"User-Agent": self.UA}),
            }

        # 兜底：返回空，交给TVBox嗅探
        return {
            "parse": 1,
            "playUrl": "",
            "url": url,
            "header": json.dumps({"User-Agent": self.UA}),
        }

    # ---------------------------------------------------------------
    # 工具方法
    # ---------------------------------------------------------------
    def _try(self, text, pats, validator, strip=False):
        for p in pats:
            if not p:
                continue
            try:
                for m in re.finditer(p, text, re.S):
                    try:
                        v = m.group(1).strip()
                    except IndexError:
                        v = m.group(0).strip()
                    if strip:
                        v = re.sub(r"<[^>]+>", "", v).strip()
                    if validator(v):
                        return v
            except Exception:
                continue
        return ""

    def _vname(self, v):
        if not v:
            return False
        v = v.strip()
        return (1 <= len(v) <= 80
                and not v.startswith(("http", "//"))
                and not re.fullmatch(r"[\s\W_]+", v)
                and not re.fullmatch(r"\d+", v)
                and "\ufffd" not in v)

    def _vpic(self, v):
        return bool(v) and (
            bool(re.search(r"\.(?:jpg|jpeg|png|webp|gif)", v, re.I))
            or v.startswith(("http", "//"))
        )

    def _abs(self, u):
        if not u:
            return ""
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.BASE + u
        if u.startswith("http"):
            return u
        return urllib.parse.urljoin(self.BASE, u)

    def _strip(self, t):
        return re.sub(r"<[^>]+>", "", t or "").strip()