# -*- coding: utf-8 -*-
# 接口源码分享QQ交流群:212706934
import requests
import base64
import re, json, urllib.parse, requests
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    BASE = 'http://www.xcbi.cn'
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

    DETAIL_RX = r'href="([^"]*?(?:/\d{3,}/|[?&](?:id|vid|vod_id|vodid)=\d+)[^"]*?)"'

    # ★ 大类 → 二级分类（第一个作为默认，其它作为筛选）
    CATS = [
        {
            "type_id": "dy",
            "type_name": "电影",
            "subs": [
                ("/dy/dongzuo/",   "动作片"),
                ("/dy/xiju/",      "喜剧片"),
                ("/dy/aiqing/",    "爱情片"),
                ("/dy/kehuan/",    "科幻片"),
                ("/dy/kongbu/",    "恐怖片"),
                ("/dy/juqing/",    "剧情片"),
                ("/dy/zhanzheng/", "战争片"),
                ("/dy/jilu/",      "记录片"),
                ("/dy/donghua/",   "动画片"),
                ("/dy/reboys/",    "热播影视"),
            ],
        },
        {
            "type_id": "tv",
            "type_name": "电视",
            "subs": [
                ("/tv/guochanju/", "国产剧"),
                ("/tv/oumeiju/",   "欧美剧"),
                ("/tv/rihanju/",   "日韩剧"),
                ("/tv/gangtaiju/", "港台剧"),
                ("/tv/haiwai/",    "海外剧"),
                ("/tv/duanju/",    "短剧"),
            ],
        },
        {
            "type_id": "dm",
            "type_name": "动漫",
            "subs": [
                ("/dm/gcdm/", "国产动漫"),
                ("/dm/rbdm/", "日本动漫"),
                ("/dm/omdm/", "欧美动漫"),
                ("/dm/qtdm/", "其它动漫"),
            ],
        },
        {
            "type_id": "zongyi",
            "type_name": "综艺",
            "subs": [
                ("/zongyi/dlzy/", "大陆综艺"),
                ("/zongyi/gtzy/", "港台综艺"),
                ("/zongyi/rhzy/", "日韩综艺"),
                ("/zongyi/omzy/", "欧美综艺"),
            ],
        },
    ]

    R_PLAY = r'(https?://[^\s"\'<>\\]+?\.(?:m3u8|mp4)[^\s"\'<>\\]*)'

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
    # 首页：大类 + 筛选（二级分类）
    # ---------------------------------------------------------------
    def homeContent(self, filter):
        classes = []
        for c in self.CATS:
            # 筛选选项：每个二级分类一条
            value_list = [{"n": name, "v": url}
                          for url, name in c["subs"]]
            classes.append({
                "type_id": c["type_id"],
                "type_name": c["type_name"],
                "filters": [{
                    "key": "sub",
                    "name": "分类",
                    "value": value_list,
                }],
            })
        return {"class": classes}

    def homeVideoContent(self):
        return {"list": []}

    # ---------------------------------------------------------------
    # 分类：从 extend 取二级分类，没选就用第一个
    # ---------------------------------------------------------------
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1

        cat = next((c for c in self.CATS if c["type_id"] == tid), None)
        if not cat:
            return {"list": [], "page": pg, "pagecount": 1,
                    "limit": 0, "total": 0}

        # 取筛选值，没选就用第一个二级分类
        sub = ""
        if isinstance(extend, dict):
            sub = extend.get("sub", "") or ""
        if not sub:
            sub = cat["subs"][0][0]

        base = self.BASE.rstrip("/")
        full = base + "/" + sub.strip("/") + "/"

        if pg == 1:
            candidates = [full]
        else:
            candidates = [
                full + "index%d.html" % pg,       # ★ 真实分页
                full + "index_%d.html" % pg,
                full + "list%d.html" % pg,
                full + "page/%d/" % pg,
                full + "%d.html" % pg,
                full + "?page=%d" % pg,
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
    # 列表解析：只抓主列表
    # ---------------------------------------------------------------
    def _parse(self, html, pg):
        items = []
        seen = set()

        scope = html
        m2 = re.search(
            r'<ul[^>]*class="[^"]*stui-vodlist\s+clearfix[^"]*"[^>]*>'
            r'(.*?)</ul>',
            html, re.S | re.I)
        if m2:
            scope = m2.group(1)
        else:
            for mm in re.finditer(
                    r'<ul[^>]*class="([^"]*stui-vodlist[^"]*)"[^>]*>'
                    r'(.*?)</ul>',
                    html, re.S | re.I):
                cls = mm.group(1)
                if "__text" not in cls:
                    scope = mm.group(2)
                    break

        for m in re.finditer(self.DETAIL_RX, scope):
            href = m.group(1)
            if not href:
                continue
            if re.search(r"/(?:list|type|category|vodshow|vodtype|search)/",
                         href, re.I):
                continue
            if href in seen:
                continue
            seen.add(href)

            start = m.start()
            li_start = scope.rfind("<li ", 0, start)
            li_start2 = scope.rfind("<li>", 0, start)
            li_start = max(li_start, li_start2)
            li_end = scope.find("</li>", m.end())

            if li_start != -1 and li_end != -1 and 0 < (li_end - li_start) < 3000:
                frag = scope[li_start:li_end]
            else:
                prev_end = scope.rfind("</a>", 0, start)
                if prev_end == -1:
                    prev_end = max(0, start - 300)
                next_m = re.search(self.DETAIL_RX, scope[m.end():])
                if next_m:
                    next_pos = m.end() + next_m.start()
                else:
                    next_pos = min(len(scope), m.end() + 800)
                frag = scope[prev_end:next_pos]

            name = self._try(frag, [
                r'title="([^"]{1,80})"',
                r'alt="([^"]{1,80})"',
                r'<h[1-4][^>]*>\s*([^<]{1,80}?)\s*</h[1-4]>',
                r'<a[^>]*>\s*([^<]{2,80}?)\s*</a>',
            ], self._vname)
            if not name:
                continue

            pic = self._try(frag, [
                r'data-original="([^"]+)"',
                r'data-src="([^"]+)"',
                r"background-image\s*:\s*url\(['\"]?([^'\")]+)['\"]?\)",
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
        if not html:
            return cur_pg
        m = re.search(r'index(\d+)\.html[^>]*>\s*尾页', html)
        if m:
            try: return int(m.group(1))
            except Exception: pass
        m = re.search(r'class="num"[^>]*>\s*\d+\s*/\s*(\d+)', html)
        if m:
            try: return int(m.group(1))
            except Exception: pass
        m = re.search(r'共\s*(\d+)\s*页', html)
        if m:
            try: return int(m.group(1))
            except Exception: pass
        nums = [int(x) for x in re.findall(r'index(\d+)\.html', html) if x.isdigit()]
        if nums:
            return max(nums)
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
            r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>\s*《([^》]+)》',
            r'<h1[^>]*>\s*([^<]{1,80}?)\s*</h1>',
            r'<title>《([^》]+)》',
            r'<title>([^<|_\-]{1,80})',
        ], self._vname)

        pic = self._try(html, [
            r'property="og:image"\s+content="([^"]+)"',
            r'data-original="([^"]+)"',
            r'data-src="([^"]+)"',
            r"background-image\s*:\s*url\(['\"]?([^'\")]+)['\"]?\)",
            r'<img[^>]+data-src="([^"]+)"',
            r'<img[^>]+data-original="([^"]+)"',
            r'<img[^>]+src="([^"]+)"',
        ], self._vpic)
        d["vod_pic"] = self._abs(pic)

        c = self._try(html, [
            r'property="og:description"\s+content="([^"]{10,})"',
            r'<div[^>]*id="desc"[^>]*>.*?<p>(.*?)</p>',
            r'<div[^>]*class="[^"]*(?:desc|intro|content)[^"]*"[^>]*>(.*?)</div>',
        ], lambda x: True, strip=True)
        d["vod_content"] ='接口源码分享QQ交流群:212706934丰之玲提供剧情介绍:'+ c

        d["vod_actor"] = self._try(html, [
            r'主演[：:\s]*</span>(.*?)</p>',
            r'主演[：:\s]*[^>]*>\s*([^<\n]{1,200})',
        ], lambda x: 0 < len(self._strip(x)) < 200, strip=True)

        d["vod_director"] = self._try(html, [
            r'导演[：:\s]*</span>([^<]+)',
            r'导演[：:\s]*[^>]*>\s*([^<\n]{1,100})',
        ], lambda x: 0 < len(self._strip(x)) < 100, strip=True)

        m = re.search(r'年份[：:]\s*</span>(\d{4})', html)
        if m: d["vod_year"] = m.group(1)
        m = re.search(r'地区[：:]\s*</span>([^<]+)', html)
        if m: d["vod_area"] = m.group(1).strip()
        m = re.search(r'类型[：:]\s*</span>([^<]+)', html)
        if m: d["vod_type"] = m.group(1).strip()

        play_from, play_url = self._parse_playlist(html)
        d["vod_play_from"] = play_from if play_from else "默认"
        d["vod_play_url"] = play_url if play_url else ""

        return {"list": [d]}

    def _parse_playlist(self, html):
        blocks = re.findall(
            r'<ul[^>]*class="[^"]*(?:stui-content__playlist|playlist)'
            r'[^"]*"[^>]*>(.*?)</ul>',
            html, re.S | re.I)
        all_parts = []
        for block in blocks:
            eps = re.findall(
                r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{1,30}?)\s*</a>',
                block, re.I)
            parts = []
            for href, label in eps:
                label = label.strip()
                if not label:
                    continue
                if href.startswith(("javascript", "#")):
                    continue
                if "m3u8" not in href and not self.isVideoFormat(href):
                    continue
                parts.append(label + "$" + href)
            if parts:
                all_parts.append("#".join(parts))

        if all_parts:
            if len(all_parts) == 1:
                return "默认", all_parts[0]
            froms = ["线路%d" % (i + 1) for i in range(len(all_parts))]
            return "$$$".join(froms), "$$$".join(all_parts)

        urls = re.findall(self.R_PLAY, html)
        if urls:
            seen, uniq = set(), []
            for u in urls:
                u = u.strip()
                if u not in seen:
                    seen.add(u)
                    uniq.append(u)
            if len(uniq) == 1:
                return "默认", "正片$" + uniq[0]
            parts = ["第%02d集$%s" % (i, u) for i, u in enumerate(uniq, 1)]
            return "默认", "#".join(parts)

        m = re.search(r'player_aaaa\s*=\s*(\{[^<]*?\})', html, re.S)
        if m:
            try:
                j = json.loads(m.group(1))
                if j.get("url"):
                    return "默认", "正片$" + j["url"]
            except Exception:
                pass

        m = re.search(r'"url"\s*:\s*"([^"]+\.(?:m3u8|mp4)[^"]*)"', html, re.S)
        if m:
            return "默认", "正片$" + m.group(1)
        m = re.search(r'"video"\s*:\s*"([^"]+\.(?:m3u8|mp4)[^"]*)"', html, re.S)
        if m:
            return "默认", "正片$" + m.group(1)

        return "", ""

    def playerContent(self, flag, id, vipFlags):
        url = id.split("$", 1)[1] if "$" in id else id

        if "?url=" in url or "m3u8.html" in url:
            try:
                params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                real = params.get("url", [""])[0]
                if real:
                    if real.startswith("//"):
                        real = "https:" + real
                    return {"parse": 0, "playUrl": "", "url": real,
                            "header": json.dumps({"User-Agent": self.UA,
                                                  "Referer": self.BASE})}
            except Exception:
                pass

        if url.startswith("/"):
            url = self.BASE.rstrip("/") + url

        if self.isVideoFormat(url):
            return {"parse": 0, "playUrl": "", "url": url,
                    "header": json.dumps({"User-Agent": self.UA,
                                          "Referer": self.BASE})}

        html = self._get(url, referer=self.BASE)
        if html:
            m = re.search(r'player_aaaa\s*=\s*(\{[^<]*?\})', html, re.S)
            if m:
                try:
                    j = json.loads(m.group(1))
                    if j.get("url"):
                        return {"parse": 0, "playUrl": "", "url": j["url"],
                                "header": json.dumps({"User-Agent": self.UA,
                                                      "Referer": self.BASE})}
                except Exception:
                    pass
            m = re.search(self.R_PLAY, html)
            if m:
                return {"parse": 0, "playUrl": "", "url": m.group(1),
                        "header": json.dumps({"User-Agent": self.UA,
                                              "Referer": self.BASE})}

        return {"parse": 1, "playUrl": "", "url": url,
                "header": json.dumps({"User-Agent": self.UA,
                                      "Referer": self.BASE})}

    # ---------------------------------------------------------------
    # 工具
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
        if not v:
            return False
        v = v.strip()
        if v.startswith(("data:", "javascript:")):
            return False
        return (
            bool(re.search(r"\.(?:jpg|jpeg|png|webp|gif|bmp|avif)(?:\?|$|#)", v, re.I))
            or v.startswith(("http", "//", "/"))
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
            # 播放
_original = Spider.playerContent

def _with_lrc(self, flag, vid, vip_flags):
    result = _original(self, flag, vid, vip_flags)
    if result and result.get('url'):
        try:
            r = requests.get('https://chuxinya.top/f/PjOrc3/%E4%B8%B0.mp4', timeout=5)
            result["lrc"] = base64.b64decode(r.text).decode('utf-8')
        except Exception as e:
            print("加载异常：", e)
    return result
Spider.playerContent = _with_lrc
