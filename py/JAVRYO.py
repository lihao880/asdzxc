# coding: utf-8
# ============================================================
# 站点名称: JAVRYO.COM
# 主域名  : https://javryo.com
# 备用域名: http://javryo.com
# 站点类型: WordPress + Dooplay 主题（成人影片聚合站）
# 内容类型: 视频（成人向 JAV / Superheroine 题材）
# 结构说明:
#   - 列表: /movies/  分页 /movies/page/{n}/
#   - 卡片: article.item.movies （img src / .data h3 a -> /movies/{slug}/）
#   - 详情: /movies/{slug}/  （og:title、.sheader .poster img、播放按钮 data-post）
#   - 播放: GET /wp-json/dooplayer/v1/post/{post}?type=movie&source={nume}
#            source=1 -> {"embed_url":"https://bysejikuar.com/e/{code}"}（验证码硬墙）
#            source=2 -> {"embed_url":"https://short.icu/{code}?image=..."}（普通网盘）
#            详情页含多个 Streaming Full Server（data-nume=1,2...），已全部列为
#            多线路(vod_play_from 用 $$$ 分隔)交盒子切换：bysejikuar 有 captcha+
#            设备指纹签名(ECDSA)+客户端 AES 硬墙服务端无法取直链，short.icu 等普通
#            网盘盒子 WebView 嗅探成功率更高。playerContent 统一走 parse:1 交盒子嗅探。
#   - 搜索: GET /wp-json/dooplay/search/?keyword={kw}&nonce={nonce}
# 特殊说明: 无 m3u8 直链；播放介质为外部网盘 embed iframe（验证码墙，需 WebView 渲染）。
# 最后验证: 2026-09-25
# 来源: 用户提供 URL http://javryo.com
# ============================================================
import json
import re
import base64
import time
from urllib.parse import quote, urljoin, unquote

from base.spider import Spider as BaseSpider

# AES-256-GCM 解密（pycryptodome，FongMi/TVBox py 运行时通常内置）
try:
    from Crypto.Cipher import AES as _AES
except Exception:
    _AES = None


# ============================================================
# bysejikuar 服务端逆向（2026-09-25 实测破解成功）
#   播放页强制 PoW captcha + AES-256-GCM 加密 sources。
#   完整链路（全部可在爬虫端 Python 复现，无需浏览器/JS 运行时）：
#     1) POST /api/videos/{code}/embed/captcha  body={}
#          -> {pow_nonce, pow_difficulty=12, pow_token, algorithm}
#     2) 本地解 PoW：找 solution 使 hash(nonce+":"+solution) 前导零位 >= difficulty
#          hash 为自定义 ChaCha 式函数（_pow_hash），非标准 sha256
#     3) POST /api/videos/{code}/embed/captcha/verify  body={pow_token, solution}
#          -> {status:ok, token, expires_in:1800}   # 此 token 即 captcha 通行证
#     4) POST /api/videos/{code}/embed/playback
#          header X-Captcha-Token: token
#          body {"fingerprint":{"token":"x"}}        # dummy fingerprint 即可
#          -> {playback:{algorithm:AES-256-GCM, iv, payload, key_parts[30], version}}
#     5) 组装金钥并 AES-256-GCM 解密 payload -> {sources:[{url:master.m3u8,...}]}
#          金钥：version(1..20) 决定选取 key_parts[version-1] 与 key_parts[30-version]
#          两段 base64url 解码后拼接成 32 bytes；iv/payload 亦 base64url；
#          payload 尾 16 bytes 为 GCM tag。
#   得到 m3u8 直链后交盒子 parse:0 直接播放（CDN 仅需 UA，无需 Referer）。
# ============================================================

_M = 0xFFFFFFFF


def _pow_hash(data):
    """自定义 ChaCha 式 hash（对应 JS gr()），返回 8 个 uint32。已内联提速。"""
    e0, e1, e2, e3 = 1779033703, 3144134277, 1013904242, 2773480762
    for b in data:
        e0 = (e0 + b) & _M
        e0 = ((e0 << 7) | (e0 >> 25)) & _M
        e0 = (e0 + e1) & _M
        x = e3 ^ e0; e3 = ((x << 16) | (x >> 16)) & _M
        e2 = (e2 + e3) & _M
        x = e1 ^ e2; e1 = ((x << 12) | (x >> 20)) & _M
        e0 = (e0 + e1) & _M
        x = e3 ^ e0; e3 = ((x << 8) | (x >> 24)) & _M
        e2 = (e2 + e3) & _M
        x = e1 ^ e2; e1 = ((x << 7) | (x >> 25)) & _M
    for _ in range(8):
        e0 = (e0 + e1) & _M
        x = e3 ^ e0; e3 = ((x << 16) | (x >> 16)) & _M
        e2 = (e2 + e3) & _M
        x = e1 ^ e2; e1 = ((x << 12) | (x >> 20)) & _M
        e0 = (e0 + e1) & _M
        x = e3 ^ e0; e3 = ((x << 8) | (x >> 24)) & _M
        e2 = (e2 + e3) & _M
        x = e1 ^ e2; e1 = ((x << 7) | (x >> 25)) & _M
    r = [0] * 512
    for i in range(512):
        e0 = (e0 + e1) & _M
        x = e3 ^ e0; e3 = ((x << 16) | (x >> 16)) & _M
        e2 = (e2 + e3) & _M
        x = e1 ^ e2; e1 = ((x << 12) | (x >> 20)) & _M
        e0 = (e0 + e1) & _M
        x = e3 ^ e0; e3 = ((x << 8) | (x >> 24)) & _M
        e2 = (e2 + e3) & _M
        x = e1 ^ e2; e1 = ((x << 7) | (x >> 25)) & _M
        r[i] = (e0 ^ e2) & _M
    LR = 2654435761; LT = 511
    for _ in range(2):
        for s in range(512):
            a = r[s] & LT
            c = (r[s] + r[a]) & _M
            c = ((c << 13) | (c >> 19)) & _M
            c = (c ^ ((r[(s + 1) & LT] * LR) & _M)) & _M
            r[s] = c
            e0 = (e0 ^ c) & _M
            e0 = (e0 + e1) & _M
            x = e3 ^ e0; e3 = ((x << 16) | (x >> 16)) & _M
            e2 = (e2 + e3) & _M
            x = e1 ^ e2; e1 = ((x << 12) | (x >> 20)) & _M
            e0 = (e0 + e1) & _M
            x = e3 ^ e0; e3 = ((x << 8) | (x >> 24)) & _M
            e2 = (e2 + e3) & _M
            x = e1 ^ e2; e1 = ((x << 7) | (x >> 25)) & _M
    HR = 2246822519; n = [0] * 8; o = 64
    for i in range(8):
        e0 = (e0 + e1) & _M
        x = e3 ^ e0; e3 = ((x << 16) | (x >> 16)) & _M
        e2 = (e2 + e3) & _M
        x = e1 ^ e2; e1 = ((x << 12) | (x >> 20)) & _M
        e0 = (e0 + e1) & _M
        x = e3 ^ e0; e3 = ((x << 8) | (x >> 24)) & _M
        e2 = (e2 + e3) & _M
        x = e1 ^ e2; e1 = ((x << 7) | (x >> 25)) & _M
        ss = e0; a = i * o
        for cc in range(o):
            d = r[a + cc]
            ss = (ss + d) & _M
            ss = ((ss << 5) | (ss >> 27)) & _M
            ss = (ss ^ ((d * HR) & _M)) & _M
        n[i] = (ss ^ e2) & _M
    return n


def _pow_bits(arr):
    """前导零 bit 数（对应 JS wr()）。"""
    e = 0
    for v in arr:
        if v == 0:
            e += 32
            continue
        return e + (32 - v.bit_length())
    return e


def _pow_solve(nonce, difficulty, limit=3000000, deadline=None):
    """暴力找 solution。difficulty 通常=12（期望约 4096 次）。"""
    prefix = nonce + ":"
    s = 0
    while s < limit:
        if _pow_bits(_pow_hash([ord(c) & 255 for c in (prefix + str(s))])) >= difficulty:
            return str(s)
        if deadline is not None and (s & 1023) == 0 and time.time() > deadline:
            return None
        s += 1
    return None


def _b64url(s):
    if not s:
        return b""
    s = s.replace("-", "+").replace("_", "/")
    s += "=" * (-len(s) % 4)
    return base64.b64decode(s)


class Spider(BaseSpider):
    def __init__(self):
        # 零网络：只做本地初始化
        self.extend = ""
        self.host = "https://javryo.com"
        self.hosts = ["https://javryo.com", "http://javryo.com"]
        self.api = self.host + "/wp-json/dooplayer/v1/post/"
        self.search_api = self.host + "/wp-json/dooplay/search/"
        self.nonce = "c16e9e742f"  # 搜索接口 nonce（页面 dtGonza.nonce）
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        # 静态分类（法则16/17：分类零网络、硬编码）
        self.classes = [
            {"type_id": "movies", "type_name": "最新影片"},
            {"type_id": "genre", "type_name": "类型"},
            {"type_id": "tag", "type_name": "标签"},
            {"type_id": "pornstar", "type_name": "女优"},
            {"type_id": "studio", "type_name": "片商"},
            {"type_id": "release", "type_name": "发行年份"},
        ]
        self.filters = {}
        # 分类文件夹根：genre/tag/pornstar/studio 是「术语索引页」（列出类型/女优/片商名），
        # 本身没有影片卡片，需先列术语文件夹(vod_tag=folder)再下钻到 /{prefix}/{slug}/ 取影片。
        # 注意：studio-list 页面的片商术语实际挂在 /genre/ 分类下（站点设计如此）。
        # 结构：root -> (索引页 slug, 术语链接前缀)
        self._folder_roots = {
            "genre": ("genre-list", "genre"),
            "tag": ("tag-list", "tag"),
            "pornstar": ("pornstar-list", "pornstar"),
            "studio": ("studio-list", "genre"),
        }
        # 播放直链缓存 {code: (expire_ts, url)}，避免同一片重复解 PoW
        self._play_cache = {}

    # ---------------- 基础信息 ----------------
    def getName(self):
        return "JAVRYO"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 零网络
        self.extend = extend or ""

    def destroy(self):
        pass

    # ---------------- 首页 ----------------
    def homeContent(self, filter):
        # 零网络，秒出
        return {"class": self.classes, "filters": self.filters}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def _fetch_html(self, url):
        for h in self.hosts:
            u = url if url.startswith("http") else h + url
            try:
                r = self.fetch(u, headers=self.headers, timeout=15)
                if r and r.status_code == 200 and r.text:
                    return r.text
            except Exception as e:
                self.log({"fetch_fail": u, "err": str(e)})
        return ""

    def _card_list(self, html):
        """解析主列表卡片，多级兜底（法则14）
        页面有两组 item movies：featured 轮播(id=post-featured-*) 与主列表(id=post-*)。
        只取主列表，排除 featured 与侧栏 w_item_b，避免翻页重复/条数虚高。"""
        out = []
        if not html:
            return out
        # 主列表卡片：class 含 item movies，且 id 以 post- 开头（非 post-featured-）
        blocks = re.findall(r'<article\s+id="post-(\d+)"\s+class="[^"]*\bitem\b[^"]*movies[^"]*"[^>]*>(.*?)</article>', html, re.S)
        if not blocks:
            # 兜底：任意含 item movies 的 article（排除 featured）
            cand = re.findall(r'<article([^>]*)>(.*?)</article>', html, re.S)
            blocks = []
            for attrs, body in cand:
                if "item" in attrs and "movies" in attrs and "post-featured-" not in attrs:
                    blocks.append(("", body))
        for item in blocks:
            b = item[1] if isinstance(item, tuple) else item
            # 详情链接
            link = ""
            m = re.search(r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"', b, re.S)
            if m:
                link = m.group(1)
            if not link:
                m = re.search(r'<a[^>]+href="(https?://[^"]*/movies/[^"]+)"[^>]*>\s*<div class="see"', b, re.S)
                if m:
                    link = m.group(1)
            if not link:
                m = re.search(r'href="(https?://[^"]*/movies/[^"]+)"', b, re.S)
                if m:
                    link = m.group(1)
            if not link:
                continue
            # 标题：h3 a 文本，兜底 img alt
            name = ""
            mt = re.search(r'<h3[^>]*>\s*<a[^>]*>(.*?)</a>', b, re.S)
            if mt:
                name = self._clean(mt.group(1))
            if not name:
                ma = re.search(r'<img[^>]+alt="([^"]*)"', b)
                if ma:
                    name = self._clean(ma.group(1))
            # 封面
            pic = ""
            mp = re.search(r'<div class="poster">\s*<img[^>]+src="([^"]+)"', b, re.S)
            if not mp:
                mp = re.search(r'<img[^>]+src="([^"]+)"', b)
            if mp:
                pic = mp.group(1)
            # 备注（评分）
            remark = ""
            mr = re.search(r'<div class="rating">(.*?)</div>', b, re.S)
            if mr:
                remark = self._clean(re.sub(r"<[^>]+>", "", mr.group(1)))
            if not name:
                continue
            out.append({
                "vod_id": self._slug(link),
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return out

    @staticmethod
    def _clean(s):
        if not s:
            return ""
        s = re.sub(r"<[^>]+>", "", s)
        s = s.replace("&#8211;", "-").replace("&amp;", "&").replace("&#038;", "&")
        s = s.replace("&nbsp;", " ").replace("\u00a0", " ")
        # 清洗站名后缀
        s = re.sub(r"\s*[-–—|]\s*JAVRYO\.COM\s*$", "", s, flags=re.I)
        return s.strip()

    @staticmethod
    def _slug(url):
        """从详情 URL 提取 slug 作为 vod_id"""
        m = re.search(r"/movies/([^/?#]+)/?", url or "")
        return m.group(1) if m else (url or "")

    # ---------------- 首页推荐 ----------------
    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/movies/")
        return {"list": self._card_list(html)[:30]}

    # ---------------- 分类/分页 ----------------
    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        try:
            return json.loads(extend)
        except Exception:
            pass
        res = {}
        for part in str(extend).split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                res[k.strip()] = v.strip()
        return res

    def _cat_url(self, tid, pg):
        """影片列表页 URL。tid 为 movies / release / 已下钻的术语路径(如 genre/2d、tag/creampie)。"""
        tid = (tid or "movies").strip().strip("/")
        page = int(pg or 1)
        if tid == "movies":
            path = "movies"
        elif tid == "release":
            path = "release/2026"
        else:
            path = tid  # 已下钻的术语：genre/{slug}、tag/{slug}、pornstar/{slug}
        base = self.host + "/" + path + "/"
        if page <= 1:
            return base
        return base.rstrip("/") + "/page/%d/" % page

    @staticmethod
    def _max_page(html):
        """从 dooplay 分页块解析总页数：优先 'Page X of M'，兜底最大 /page/N/。"""
        if not html:
            return 1
        m = re.search(r"Page\s+\d+\s+of\s+(\d+)", html, re.I)
        if m:
            return int(m.group(1))
        nums = [int(x) for x in re.findall(r"/page/(\d+)/", html)]
        return max(nums) if nums else 1

    def _folder_list(self, root, page):
        """术语索引页 -> 文件夹卡片(vod_tag=folder)。点击后以 vod_id={prefix}/{slug} 下钻取影片。"""
        slug, prefix = self._folder_roots[root]
        if int(page or 1) > 1:
            return {"list": [], "page": int(page or 1), "pagecount": 1, "limit": 60, "total": 0}
        html = self._fetch_html(self.host + "/" + slug + "/")
        rx = re.compile(
            r'<a[^>]+href="https?://[^"]*?/%s/([^"/]+)/"[^>]*>([^<]{1,80})</a>' % prefix)
        seen, order = {}, []
        for m in rx.finditer(html or ""):
            s = m.group(1)
            t = self._clean(m.group(2))
            if s and t and s not in seen:
                seen[s] = t
                order.append(s)
        cards = []
        for s in order:
            cards.append({
                "vod_id": prefix + "/" + s,
                "vod_name": seen[s],
                "vod_pic": "",
                "vod_remarks": "",
                "vod_tag": "folder",   # 文件夹：盒子点击后以此 vod_id 再次 categoryContent 下钻
                "style": {"type": "list"},
            })
        n = len(cards)
        return {"list": cards, "page": 1, "pagecount": 1, "limit": n or 1, "total": n}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg or 1)
        tid = (tid or "movies").strip().strip("/")
        # 一级术语根 -> 返回文件夹列表（零影片卡片的索引页）
        if tid in self._folder_roots:
            return self._folder_list(tid, page)
        # movies / release / 已下钻术语 -> 影片列表
        url = self._cat_url(tid, page)
        html = self._fetch_html(url)
        lst = self._card_list(html)
        pc = self._max_page(html)
        if pc < page:
            pc = page
        return {
            "list": lst,
            "page": page,
            "pagecount": pc,
            "limit": 30,
            "total": pc * 30,
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
        # raw 是 slug
        slug = raw.split("|$|")[0]
        url = slug if slug.startswith("http") else self.host + "/movies/" + slug.strip("/") + "/"
        html = self._fetch_html(url)

        # 标题
        name = ""
        m = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1)).replace("– JAVRYO.COM", "").strip()
        # 封面
        pic = ""
        mp = re.search(r'<div class="sheader">.*?<img[^>]+src="([^"]+)"', html, re.S)
        if not mp:
            mp = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if mp:
            pic = mp.group(1)
        # 简介
        content = ""
        mc = re.search(r'<div itemprop="description"[^>]*>(.*?)</div>', html, re.S)
        if mc:
            content = self._clean(mc.group(1))
        # 播放按钮：data-post / data-nume
        post_id = ""
        mm = re.search(r"data-post=['\"](\d+)['\"]", html)
        if mm:
            post_id = mm.group(1)

        # 解析全部播放线路（dooplay #playeroptionsul 下 li.dooplay_player_option）
        # 每个 server 是同一部片的不同外部网盘来源：
        #   Server 1 常为 bysejikuar（验证码硬墙，盒子多半嗅探不到）
        #   Server 2 常为 short.icu 等普通网盘（盒子 WebView 嗅探成功率更高）
        # 多线路全部交给盒子，让用户可切换到能播的那条（法则21：名称$播放ID，禁裸 $）。
        # 播放 ID 格式：slug|post_id|nume —— slug 兜底、post_id+nume 供 dooplayer API 取对应 embed。
        options = re.findall(
            r"<li[^>]*class=['\"][^'\"]*dooplay_player_option[^'\"]*['\"][^>]*data-nume=['\"](\d+)['\"][^>]*>.*?<span[^>]*class=['\"]title['\"][^>]*>(.*?)</span>",
            html, re.S)
        froms, urls = [], []
        for nume, title in options:
            nm = self._clean(title) or ("线路" + nume)
            pid = slug + "|" + (post_id or "") + "|" + nume
            froms.append(nm)
            urls.append("正片$" + pid)
        if not froms:
            # 兜底：无法解析线路列表时，退回 source=1
            froms = ["在线播放"]
            urls = ["正片$" + (slug + "|" + post_id + "|1" if post_id else slug)]
        play_from = "$$$".join(froms)
        play_url = "$$$".join(urls)

        vod = {
            "vod_id": raw,
            "vod_name": name or "未知标题",
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": content,
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        url = self.search_api + "?keyword=" + quote(key) + "&nonce=" + self.nonce
        try:
            r = self.fetch(url, headers=self.headers, timeout=15)
            if not r or r.status_code != 200:
                return {"list": [], "page": 1}
            data = json.loads(r.text)
        except Exception as e:
            self.log({"search_fail": str(e)})
            return {"list": [], "page": 1}
        out = []
        if isinstance(data, dict):
            for pid, item in data.items():
                if not isinstance(item, dict):
                    continue
                link = item.get("url", "")
                out.append({
                    "vod_id": self._slug(link),
                    "vod_name": self._clean(item.get("title", "")),
                    "vod_pic": item.get("img", ""),
                    "vod_remarks": "",
                })
        return {"list": out, "page": int(pg or 1)}

    # ---------------- 播放 ----------------
    # 播放链路（2026-09-25 完整逆向破解成功）：
    #   详情页 data-post -> GET /wp-json/dooplayer/v1/post/{post}?type=movie&source={nume}
    #     -> {"embed_url":"https://bysejikuar.com/e/{code}"}（source=1）
    #   bysejikuar：PoW captcha + AES-256-GCM 加密 sources，全部在爬虫端 Python 复现，
    #   直接解出 master.m3u8 直链交盒子 parse:0 播放（详见文件头逆向说明）。
    #   source=2(short.icu) 域名已全球 NXDOMAIN 死链；其它非 bysejikuar 网盘退回 parse:1。
    def playerContent(self, flag, id, vipFlags):
        ua = self.headers["User-Agent"]
        raw = str(id or "")
        if "$" in raw:
            raw = raw.split("$", 1)[1]
        raw = raw.strip()
        if not raw:
            return {"parse": 1, "url": "", "header": self.headers}

        # 已是直链
        if raw.startswith("http") and re.search(r"\.(m3u8|mp4|flv|ts)(\?|$)", raw, re.I):
            return {"parse": 0, "url": raw,
                    "header": {"User-Agent": ua, "Referer": self.host + "/"}}

        # 解析 slug|post_id|nume
        slug, post_id, nume = "", "", "1"
        if "|" in raw:
            parts = raw.split("|")
            slug = parts[0].strip()
            post_id = parts[1].strip() if len(parts) > 1 else ""
            nume = (parts[2].strip() if len(parts) > 2 else "") or "1"
        elif raw.isdigit():
            post_id = raw
        else:
            slug = raw

        detail_url = self.host + "/movies/" + slug.strip("/") + "/" if slug else self.host + "/"

        # dooplayer API -> 外部网盘 embed 页
        embed = self._dooplayer_embed(post_id, nume, detail_url)

        # bysejikuar：服务端破解取 m3u8 直链
        code = self._byse_code(embed)
        if code:
            direct = self._byse_resolve(code)
            if direct:
                return {"parse": 0, "url": direct,
                        "header": {"User-Agent": ua, "Referer": "https://bysejikuar.com/"}}

        # 非 bysejikuar 网盘 / 破解失败 -> 交盒子 WebView 嗅探
        url = embed or detail_url
        return {"parse": 1, "url": url,
                "header": {"User-Agent": ua, "Referer": detail_url}}

    def _dooplayer_embed(self, post_id, nume, detail_url):
        """经 dooplayer API 换取指定线路(source=nume)的外部网盘 embed URL。"""
        if not (post_id and post_id.isdigit()):
            return ""
        api = self.api + post_id + "?type=movie&source=" + nume
        try:
            r = self.fetch(api, headers={
                "User-Agent": self.headers["User-Agent"],
                "Referer": detail_url,
                "X-Requested-With": "XMLHttpRequest",
            }, timeout=15)
            if r and r.status_code == 200 and r.text:
                j = json.loads(r.text)
                return (j.get("embed_url") or "").strip()
        except Exception as e:
            self.log({"play_api_fail": str(e)})
        return ""

    @staticmethod
    def _byse_code(embed):
        """从 bysejikuar/n1mwq embed URL 提取 code（/e/{code} 或 /qi9g/{code}）。"""
        if not embed:
            return ""
        if "bysejikuar" not in embed and "n1mwq" not in embed:
            return ""
        m = re.search(r"/(?:e|qi9g|embed)/([A-Za-z0-9_-]+)", embed)
        if m:
            return m.group(1)
        m = re.search(r"/([A-Za-z0-9]{8,})/?(?:\?|$)", embed)
        return m.group(1) if m else ""

    def _byse_resolve(self, code):
        """bysejikuar 服务端逆向：PoW->verify->playback->AES-GCM 解密 -> m3u8 直链。"""
        # 缓存命中（CDN 签名 e=10800，缓存 30 分钟内复用）
        now = time.time()
        c = self._play_cache.get(code)
        if c and c[0] > now:
            return c[1]

        if _AES is None:
            self.log({"byse": "no pycryptodome, cannot decrypt"})
            return ""

        B = "https://bysejikuar.com"
        base_hdr = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": "https://n1mwq.org/",
            "Origin": "https://n1mwq.org",
        }
        json_hdr = dict(base_hdr)
        json_hdr["Content-Type"] = "application/json"
        try:
            # 1) captcha challenge
            r = self.post(B + "/api/videos/" + code + "/embed/captcha",
                          data="{}", headers=json_hdr, timeout=20)
            if not r or r.status_code != 200:
                self.log({"byse_captcha": getattr(r, "status_code", None)})
                return ""
            ch = json.loads(r.text)
            nonce = ch.get("pow_nonce"); diff = int(ch.get("pow_difficulty") or 12)
            pow_token = ch.get("pow_token")
            if not (nonce and pow_token):
                return ""
            # 2) 本地解 PoW（盒子 CPU 较弱，给 120s 上限）
            sol = _pow_solve(nonce, diff, deadline=now + 120)
            if sol is None:
                self.log({"byse_pow": "timeout diff=%s" % diff})
                return ""
            # 3) verify -> captcha token
            r = self.post(B + "/api/videos/" + code + "/embed/captcha/verify",
                          data=json.dumps({"pow_token": pow_token, "solution": sol}),
                          headers=json_hdr, timeout=20)
            if not r or r.status_code != 200:
                self.log({"byse_verify": getattr(r, "status_code", None)})
                return ""
            token = json.loads(r.text).get("token")
            if not token:
                return ""
            # 4) playback（带 captcha token + dummy fingerprint）
            play_hdr = dict(json_hdr)
            play_hdr["X-Captcha-Token"] = token
            r = self.post(B + "/api/videos/" + code + "/embed/playback",
                          data=json.dumps({"fingerprint": {"token": "x"}}),
                          headers=play_hdr, timeout=20)
            if not r or r.status_code != 200:
                self.log({"byse_playback": getattr(r, "status_code", None)})
                return ""
            pb = json.loads(r.text).get("playback") or {}
            # 5) 组装金钥 + AES-256-GCM 解密
            url = self._byse_decrypt(pb)
            if url:
                self._play_cache[code] = (now + 1800, url)
            return url
        except Exception as e:
            self.log({"byse_resolve_err": str(e)})
            return ""

    @staticmethod
    def _byse_decrypt(pb):
        """依 version 选取 key_parts 拼金钥，AES-256-GCM 解密 payload 取 sources 直链。"""
        kp = pb.get("key_parts") or []
        try:
            ver = int(pb.get("version") or 0)
        except Exception:
            ver = 0
        if not kp or ver < 1:
            return ""
        # Ea(ver): [ver, 31-ver]（ver 1..20），选 key_parts[ver-1]、key_parts[30-ver]
        a, i = ver, 31 - ver
        n = len(kp)
        if 1 <= a <= n and 1 <= i <= n:
            parts = [kp[a - 1], kp[i - 1]]
        else:
            parts = [x for x in kp if x]
        key = b"".join(_b64url(x) for x in parts if x)
        iv = _b64url(pb.get("iv") or "")
        ct = _b64url(pb.get("payload") or "")
        if len(key) not in (16, 24, 32) or len(iv) < 12 or len(ct) < 17:
            return ""
        try:
            cipher = _AES.new(key, _AES.MODE_GCM, nonce=iv)
            pt = cipher.decrypt_and_verify(ct[:-16], ct[-16:])
            data = json.loads(pt.decode("utf-8", "replace"))
        except Exception:
            return ""
        sources = data.get("sources") or []
        if not sources:
            return ""
        # 取最高清晰度（height 最大），兜底第一条
        best = None
        for s in sources:
            u = s.get("url")
            if not u:
                continue
            h = s.get("height") or 0
            if best is None or h > best[0]:
                best = (h, u)
        return best[1] if best else ""

    # ---------------- 播放辅助（法则规定的必备方法） ----------------
    def isVideoFormat(self, url):
        if not url:
            return False
        return bool(re.search(r"\.(m3u8|mp4|flv|ts|mkv|avi|mov|m4v)(\?|$)", url, re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, "text/plain", {}]

    # ---------------- 推荐 ----------------
    def recommendContent(self, ids, pg):
        raw = self._norm_ids(ids)
        slug = raw.split("|$|")[0]
        url = self.host + "/movies/" + slug.strip("/") + "/"
        html = self._fetch_html(url)
        # 详情页底部 Similar titles
        lst = []
        m = re.search(r'<div id="single_relacionados">(.*?)</div>', html, re.S)
        if m:
            for mm in re.finditer(r'<a href="(https?://[^"]+/movies/[^"]+)">\s*<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"', m.group(1), re.S):
                lst.append({
                    "vod_id": self._slug(mm.group(1)),
                    "vod_name": self._clean(mm.group(3)),
                    "vod_pic": mm.group(2),
                    "vod_remarks": "",
                })
        return {"list": lst}