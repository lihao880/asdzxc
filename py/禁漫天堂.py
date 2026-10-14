# coding=utf-8
# !/usr/bin/python
# JMComic (禁漫天堂) — TVBox / FongMi T3 爬蟲來源
# 架構：漫畫看圖（pics://），圖片經 localProxy 還原打亂
import sys
sys.path.append('..')
from base.spider import Spider
import re
import time
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, unquote


class Spider(Spider):

    # ==== 站點資訊（換站只改這裡）====
    siteName = "禁漫天堂"
    MAIN = "https://18comic.my"
    HOST = ""                       # 留空自動探測
    FALLBACK_HOSTS = [
        "https://18comic.my",
        "https://18comic.vip",
        "https://jmcomic.me",
        "https://jmcomic1.me",
    ]

    UA = ("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    # ==== 分類（靜態硬編碼，homeContent 零網路）====
    CATE = [
        {"type_id": "albums",         "type_name": "全部"},
        {"type_id": "albums/doujin",  "type_name": "同人"},
        {"type_id": "albums/single",  "type_name": "單本"},
        {"type_id": "albums/short",   "type_name": "短篇"},
        {"type_id": "albums/another", "type_name": "其他類"},
        {"type_id": "albums/hanman",  "type_name": "韓漫"},
        {"type_id": "albums/meiman",  "type_name": "美漫"},
        {"type_id": "albums/doujin_cosplay", "type_name": "Cosplay"},
        {"type_id": "albums/3D",      "type_name": "3D"},
    ]

    def getName(self):
        return self.siteName

    def init(self, extend=""):
        self._host = ""
        self._host_lock = threading.Lock()
        return

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ==================== 網路基礎 ====================
    def _headers(self, referer=None):
        h = {
            "User-Agent": self.UA,
            "Accept-Encoding": "gzip",
            "Accept-Language": "zh-TW,zh;q=0.9,zh-CN;q=0.8,en;q=0.7",
        }
        h["Referer"] = referer if referer else (self.host() + "/")
        return h

    def _get(self, url, referer=None):
        try:
            rsp = self.fetch(url, headers=self._headers(referer))
            if rsp is None:
                return None
            if getattr(rsp, "status_code", 200) != 200:
                return None
            rsp.encoding = "utf-8"
            return rsp.text
        except Exception:
            return None

    # ==================== 多域名探測 ====================
    def host(self):
        if self._host:
            return self._host
        return self.HOST or self.MAIN

    def _pick_host(self):
        if self._host:
            return self._host
        with self._host_lock:
            if self._host:
                return self._host
            cands = []
            if self.HOST:
                cands.append(self.HOST)
            if self.MAIN and self.MAIN not in cands:
                cands.append(self.MAIN)
            for u in self.FALLBACK_HOSTS:
                if u not in cands:
                    cands.append(u)
            for base in cands:
                try:
                    rsp = self.fetch(base + "/albums?o=mv",
                                     headers=self._headers(base + "/"))
                    if rsp is None:
                        continue
                    if getattr(rsp, "status_code", 200) != 200:
                        continue
                    rsp.encoding = "utf-8"
                    if "/album/" in rsp.text:
                        self._host = base
                        return base
                except Exception:
                    continue
            self._host = self.MAIN
            return self._host

    # ==================== 首頁（零網路）====================
    def homeContent(self, filter):
        classes = [{"type_id": c["type_id"], "type_name": c["type_name"]}
                   for c in self.CATE]
        filters = {}
        vod = {"list": []}
        result = {"class": classes, "filters": filters}
        result.update(vod)
        return result

    def homeVideoContent(self):
        host = self._pick_host()
        html = self._get(host + "/albums?o=mv")
        if not html:
            return {"list": []}
        return {"list": self._parse_list(html)}

    # ==================== 分類 ====================
    def categoryContent(self, tid, pg, filter, extend):
        host = self._pick_host()
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1

        # 排序參數
        o = "mv"
        if extend and isinstance(extend, dict):
            o = extend.get("o", "mv") or "mv"

        sep = "&" if "?" in tid else "?"
        url = "%s/%s%so=%s&page=%d" % (host, tid, sep, o, page)
        html = self._get(url)
        vlist = self._parse_list(html) if html else []

        result = {}
        result["list"] = vlist
        result["page"] = page
        result["pagecount"] = 9999 if vlist else page
        result["limit"] = len(vlist)
        result["total"] = 999999
        return result

    # ==================== 詳情 ====================
    def detailContent(self, ids):
        host = self._pick_host()
        aid = ids[0]
        url = "%s/album/%s/" % (host, aid)
        html = self._get(url)
        if not html:
            return {"list": []}

        # 標題
        title = self._first(html, [
            r'<h1[^>]*>(.*?)</h1>',
        ], aid)
        title = self._clean_text(title)

        # 封面
        pic = ""
        mp = re.search(r'(https?:)?//[^"\']+/media/albums/%s[^"\']*\.(?:jpg|png|webp)' % aid, html)
        if mp:
            pic = mp.group(0)
            if pic.startswith("//"):
                pic = "https:" + pic

        # 標籤（作者/分類關鍵字）
        tags = re.findall(r'/search/photos\?search_query=[^"&]+"[^>]*>([^<]+)</a>', html)
        tags = [self._clean_text(t) for t in tags if t.strip()]
        seen = set()
        utags = []
        for t in tags:
            if t and t not in seen:
                seen.add(t)
                utags.append(t)
        remark = " ".join(utags[:12])

        # 敘述
        desc = ""
        md = re.search(r'<h2 class="p-t-5 p-b-5">(.*?)</h2>', html, re.S)
        if md:
            desc = self._clean_text(md.group(1))
        if not desc:
            desc = remark

        # 章節列表
        mblk = re.search(r'id="episode-block"(.*?</ul>)', html, re.S)
        blk = mblk.group(1) if mblk else html
        anchors = re.findall(r'<a\s+href="/photo/(\d+)[^"]*"[^>]*>(.*?)</a>', blk, re.S)

        eps = []
        seen_pid = set()
        idx = 0
        for pid, inner in anchors:
            if pid in seen_pid:
                continue
            seen_pid.add(pid)
            idx += 1
            name = self._clean_text(inner)
            if not name:
                name = "第%d話" % idx
            # 話名中的 $ / # 清理
            name = name.replace("$", " ").replace("#", " ").strip()
            purl = "%s/photo/%s/" % (host, pid)
            eps.append("%s$%s" % (name, purl))

        # 單話本兜底
        if not eps:
            purl = "%s/photo/%s/" % (host, aid)
            eps.append("第1話$%s" % purl)

        play_url = "#".join(eps)

        vod = {
            "vod_id": aid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "type_name": remark,
            "vod_remarks": "共%d話" % len(eps),
            "vod_play_from": "禁漫天堂",
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    # ==================== 搜尋 ====================
    def searchContent(self, key, quick, pg="1"):
        host = self._pick_host()
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        url = "%s/search/photos?search_query=%s&page=%d" % (
            host, quote(key), page)
        html = self._get(url)
        vlist = self._parse_list(html) if html else []
        return {"list": vlist, "page": page}

    # ==================== 播放（聚合整話圖片）====================
    def playerContent(self, flag, id, vipFlags):
        host = self._pick_host()
        # id 為該話 photo 頁 URL
        purl = id
        if not purl.startswith("http"):
            purl = host + "/photo/" + str(id) + "/"

        imgs = self._extract_photo_images(purl)

        # 每張圖走 localProxy 還原
        # getProxyUrl() 已含 ?do=py，依是否有 ? 決定連接符，避免重複
        proxy = self.getProxyUrl()
        sep = "&" if "?" in proxy else "?"
        parts = []
        for u in imgs:
            p = proxy + sep + "type=img&src=" + quote(u)
            parts.append(p)
        content = "&&".join(parts)

        return {
            "parse": 0,
            "url": "pics://" + content,
            "header": {"User-Agent": self.UA, "Referer": host + "/"},
        }

    # ==================== localProxy 圖片還原 ====================
    def localProxy(self, param):
        t = param.get("type", "")
        if t == "img":
            return self._proxy_image(param)
        return [404, "text/plain", ""]

    def _proxy_image(self, param):
        src = param.get("src", "")
        if src:
            src = unquote(src)
        if not src:
            return [404, "text/plain", b""]

        host = self.host()
        # 抓原圖
        try:
            rsp = self.fetch(src, headers={
                "User-Agent": self.UA,
                "Referer": host + "/",
                "Accept-Encoding": "identity",
            })
            if rsp is None or getattr(rsp, "status_code", 200) != 200:
                return [404, "image/webp", b""]
            data = rsp.content
        except Exception:
            return [404, "image/webp", b""]

        # 解析 aid + filename 決定切塊數
        aid, fname = self._parse_img_meta(src)
        num = self._get_num(aid, fname)
        if num <= 1:
            return [200, self._img_mime(src), data]

        try:
            out = self._descramble(data, num)
            return [200, "image/jpeg", out]
        except Exception:
            # 還原失敗回退原圖
            return [200, self._img_mime(src), data]

    def _parse_img_meta(self, url):
        # .../media/photos/{aid}/{fname}.webp
        aid = 0
        fname = ""
        m = re.search(r'/media/photos/(\d+)/([^/?]+)', url)
        if m:
            try:
                aid = int(m.group(1))
            except Exception:
                aid = 0
            fname = m.group(2)
            fname = re.sub(r'\.(webp|jpg|jpeg|png|gif)$', '', fname, flags=re.I)
        return aid, fname

    def _get_num(self, aid, fname):
        scramble_id = 220980
        if aid < scramble_id:
            return 0
        elif aid < 268850:
            return 10
        else:
            x = 10 if aid < 421926 else 8
            s = hashlib.md5((str(aid) + fname).encode("utf-8")).hexdigest()
            return (ord(s[-1]) % x) * 2 + 2

    def _descramble(self, data, num):
        from PIL import Image
        import io
        src = Image.open(io.BytesIO(data))
        src = src.convert("RGB")
        w, h = src.size
        dst = Image.new("RGB", (w, h))
        ch = h // num
        rem = h % num
        for i in range(num):
            # 這一塊在目標的高度
            cur = ch
            y_src = h - ch * (i + 1) - rem
            y_dst = ch * i
            if i == 0:
                cur = ch + rem
                y_src = h - ch * (i + 1) - rem
                y_dst = 0
            else:
                y_dst = ch * i + rem
                y_src = h - ch * (i + 1) - rem
            box = (0, y_src, w, y_src + cur)
            region = src.crop(box)
            dst.paste(region, (0, y_dst))
        buf = io.BytesIO()
        dst.save(buf, format="JPEG", quality=90)
        return buf.getvalue()

    def _img_mime(self, url):
        u = url.lower()
        if ".png" in u:
            return "image/png"
        if ".gif" in u:
            return "image/gif"
        if ".jpg" in u or ".jpeg" in u:
            return "image/jpeg"
        return "image/webp"

    # ==================== 圖片抽取 ====================
    def _extract_photo_images(self, purl):
        host = self._pick_host()
        html = self._get(purl, referer=host + "/")
        if not html:
            return []
        imgs = self._extract_images(html)
        # >200 頁截斷
        if len(imgs) > 200:
            imgs = imgs[:200]
        return imgs

    def _extract_images(self, html):
        # 漫畫頁圖片固定路徑：.../media/photos/{aid}/{page}.{ext}
        # 以此精準鎖定，避開選單/分類等裝飾圖
        imgs = []

        # 模式1：屬性中含 /media/photos/ 的懶載入圖
        for m in re.findall(
                r'(?:data-original|data-src|src)="([^"]*/media/photos/\d+/[^"]+\.(?:webp|jpg|jpeg|png))"',
                html):
            imgs.append(m)

        # 模式2（備援）：整頁裸 URL 掃描
        if not imgs:
            for m in re.finditer(
                    r'(?:https?:)?//[^"\'\s]+/media/photos/\d+/[^"\'\s]+\.(?:webp|jpg|jpeg|png)',
                    html):
                imgs.append(m.group(0))

        # 補協議
        out = []
        for u in imgs:
            if u.startswith("//"):
                u = "https:" + u
            elif u.startswith("/"):
                u = self.host() + u
            out.append(u)

        # 去重保序
        seen = set()
        res = []
        for u in out:
            if u not in seen:
                seen.add(u)
                res.append(u)
        return res

    NOISE_KEYWORDS = ["logo", "loading", "blank", "avatar", "banner",
                      "adv", "ad_", "line_", "icon", "cover"]
    NOISE_EXT = [".gif"]

    def _is_noise(self, url):
        name = url.split("/")[-1].split("?")[0].lower()
        for k in self.NOISE_KEYWORDS:
            if k in name:
                return True
        for e in self.NOISE_EXT:
            if name.endswith(e):
                return True
        return False

    # ==================== 列表解析 ====================
    def _parse_list(self, html):
        vlist = []
        if not html:
            return vlist
        seen = set()

        # 每張卡片：<a href="/album/{id}/..."> ... <img ... title="..." src/data-src=...>
        blocks = re.findall(
            r'<a[^>]+href="/album/(\d+)/[^"]*"[^>]*>(.*?)</a>',
            html, re.S)
        for aid, inner in blocks:
            if aid in seen:
                continue
            # 標題
            title = ""
            mt = re.search(r'title="([^"]+)"', inner)
            if mt:
                title = self._clean_text(mt.group(1))
            if not title:
                ma = re.search(r'alt="([^"]+)"', inner)
                if ma:
                    title = self._clean_text(ma.group(1))
            # 封面：優先 data-original / data-src（真圖），跳過 blank/loading 佔位圖
            pic = ""
            cands = re.findall(
                r'(?:data-original|data-src|data-echo|src)="([^"]+)"', inner)
            for c in cands:
                cl = c.lower()
                if "blank" in cl or "loading" in cl or "placeholder" in cl:
                    continue
                if not re.search(r'\.(?:jpg|jpeg|png|webp)', cl):
                    continue
                pic = c
                break
            if pic:
                pic = pic.strip()
                if pic.startswith("//"):
                    pic = "https:" + pic
                elif pic.startswith("/"):
                    pic = self.host() + pic
            if not title:
                continue
            seen.add(aid)
            vlist.append({
                "vod_id": aid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return vlist

    # ==================== 工具 ====================
    def _clean_text(self, s):
        if not s:
            return ""
        s = re.sub(r'<[^>]+>', ' ', s)
        s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        s = s.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    def _first(self, html, patterns, default=""):
        for p in patterns:
            m = re.search(p, html, re.S)
            if m:
                return m.group(1)
        return default
