# coding=utf-8
# !/usr/bin/python
# TVBox/FongMi T3(type=3) 爬虫源  ——  AlohaTube (https://www.alohatube.com/)
# ---------------------------------------------------------------------------
# 站点类型: 成人「元搜索/聚合」引擎（自身不托管视频，卡片经 /ktm/view.cgi?gid=..&u=<源站URL> 302 跳转到外部源站）
# 覆盖源站结构（playerContent 分层提取）：
#   1) KVS(kt_player) 引擎站——flashvars.video_url(+license_code 反混淆)  占比最高: sortporn/3movs/bravotube/xbabe/drtvid...
#   2) jwplayer setup sources / file:                                     videotxxx 等
#   3) 页面裸 .m3u8 / .mp4 正则、og:video、<source src>、contentUrl        兜底
#   播放统一 parse:0 直链 + Referer=源站Origin + UA（KVS acctoken 为时间戳型非IP绑定，盒子可跟随 302 到 CDN 播放）
# 换站说明: 本源为聚合站专用，非通用模板。
# ---------------------------------------------------------------------------
import sys
import re
import json
import base64
from urllib.parse import quote, unquote, urlparse

sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    class Spider:
        def init(self, extend=""): pass


class Spider(Spider):

    # ===== 站点信息（换站只改这里）=====
    SITE_NAME = "AlohaTube"
    HOST = "https://www.alohatube.com"

    UA = ("Mozilla/5.0 (Linux; Android 14; 22127RK46C/Pixel5) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    # 静态分类（法则16/17：homeContent 零网络，分类硬编码）
    CATEGORIES = [
        ("__new__",        "最新"),
        ("__top__",        "最热"),
        ("teen",           "青春"),
        ("milf",           "熟女"),
        ("mature",         "成熟"),
        ("mom",            "妈妈"),
        ("amateur",        "素人"),
        ("asian",          "亚洲"),
        ("japanese",       "日本"),
        ("latina",         "拉丁"),
        ("ebony",          "黑人"),
        ("russian",        "俄罗斯"),
        ("big_tits",       "巨乳"),
        ("anal",           "肛交"),
        ("blowjob",        "口交"),
        ("creampie",       "内射"),
        ("lesbian",        "蕾丝"),
        ("interracial",    "跨种族"),
        ("pov",            "POV"),
        ("handjob",        "手交"),
        ("shemale",        "人妖"),
        ("threesome",      "3P"),
        ("hardcore",       "重口"),
        ("cumshot",        "颜射"),
    ]

    # 付费/试看站黑名单（仅放 10 秒 /trailer/，正片需登录付费）——列表阶段即跳过
    # host 内嵌在卡片 ktm?u= 参数里，无需额外请求即可过滤；子串匹配，可随时追加
    PREMIUM_HOSTS = (
        "fhgte.com",
        "flixcdn",
    )

    def _is_premium_host(self, ext_url):
        low = (ext_url or "").lower()
        return any(h in low for h in self.PREMIUM_HOSTS)

    # ---------- 基础 12 方法 ----------
    def init(self, extend=""):
        self.headers = {
            "User-Agent": self.UA,
            "Accept-Language": "en-US,en;q=0.9",
        }
        return

    def getName(self):
        return self.SITE_NAME

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return (".m3u8" in u) or (".mp4" in u)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ---------- 网络工具 ----------
    def _get(self, url, headers=None, timeout=15):
        h = dict(self.headers)
        if headers:
            h.update(headers)
        try:
            rsp = self.fetch(url, headers=h)
            if rsp is None:
                return ""
            try:
                return rsp.text
            except Exception:
                return rsp.content.decode("utf-8", "ignore")
        except Exception:
            return ""

    # ---------- 首页 ----------
    def homeContent(self, filter):
        classes = []
        for tid, name in self.CATEGORIES:
            classes.append({"type_id": tid, "type_name": name})
        return {"class": classes}

    def homeVideoContent(self):
        # 首屏取「最新」第一页
        try:
            data = self.categoryContent("__new__", "1", False, {})
            return {"list": data.get("list", [])}
        except Exception:
            return {"list": []}

    # ---------- 分类列表 ----------
    def _cat_url(self, tid, pg):
        try:
            p = int(pg)
        except Exception:
            p = 1
        if p < 1:
            p = 1
        if tid == "__new__":
            return self.HOST + "/new/" + ("" if p == 1 else "%d/" % p)
        if tid == "__top__":
            return self.HOST + "/top/" + ("" if p == 1 else "%d/" % p)
        # 具体分类 slug：page1=/top/{slug}  pageN=/top/{N}/{slug}
        if p == 1:
            return self.HOST + "/top/" + tid
        return self.HOST + "/top/%d/%s" % (p, tid)

    def categoryContent(self, tid, pg, filter, extend):
        url = self._cat_url(tid, pg)
        html = self._get(url)
        vlist = self._parse_cards(html)
        try:
            page = int(pg)
        except Exception:
            page = 1
        pagecount = 9999 if vlist else page
        return {
            "list": vlist,
            "page": page,
            "pagecount": pagecount,
            "limit": len(vlist) if vlist else 90,
            "total": 999999,
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        try:
            p = int(pg)
        except Exception:
            p = 1
        if p < 1:
            p = 1
        q = quote(key)
        if p == 1:
            url = self.HOST + "/top/?q=" + q
        else:
            url = self.HOST + "/top/%d/?q=%s" % (p, q)
        html = self._get(url)
        return {"list": self._parse_cards(html)}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        vid = ids[0] if ids else ""
        if isinstance(vid, (list, tuple)):
            vid = vid[0] if vid else ""
        vid = str(vid)
        ext = self._decode_id(vid)  # 源站真实 URL
        # 从 URL 猜个标题
        title = self.SITE_NAME
        try:
            path = urlparse(ext).path.strip("/").split("/")
            for seg in reversed(path):
                seg = seg.replace("-", " ").replace("_", " ").strip()
                if seg and not seg.isdigit():
                    title = seg[:80]
                    break
        except Exception:
            pass
        src_host = self._host_of(ext)
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": "",
            "vod_year": "",
            "vod_area": src_host,
            "vod_remarks": "来源: " + src_host,
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "AlohaTube 聚合 · 源站 " + src_host,
            "vod_play_from": "AlohaTube",
            "vod_play_url": "播放$" + vid,
        }
        return {"list": [vod]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        # id 可能是 "播放$<base64>" 或裸 <base64>/URL —— 先剥名称段（法则21/契约）
        raw = str(id) if id else ""
        if "$" in raw:
            raw = raw.split("$", 1)[1]
        ext = self._decode_id(raw)
        if not ext:
            return {"parse": 0, "url": "", "header": {}}
        origin = self._origin_of(ext)
        # 播放页 URL 本身作 Referer（KVS get_file 校验的是视频页而非站点根）
        play_headers = {
            "User-Agent": self.UA,
            "Referer": ext if ext.startswith("http") else origin + "/",
        }
        page = self._get(ext, headers={"Referer": origin + "/"})
        video = self._extract_video(page, ext)
        if video:
            # 页面直提命中（KVS 经典 flashvars / jw / og 等）——需带 Referer
            return {"parse": 0, "url": video, "header": play_headers}
        # nuvid 系 CMS（nvdvid/h21vid/jepvid/tbnvid/vvtvid/wnvid/drtvid → m.nuvid.com 等）：
        #   页面 <video data-video_hash/data-hash_time/data-video_id>，异步 GET /player_config 拿签名直链
        nv = self._nuvid_resolve(page)
        if nv:
            url, ref_root = nv
            # 直链(gcdn/bkcdn) Referer 须为「站根」(m.<host>/)，非视频页
            return {"parse": 0, "url": url, "header": {"User-Agent": self.UA, "Referer": ref_root}}
        # KVS base164 变体（videomanysex/videotxxx 等 jwplayer 系）：走 /api/videofile.php
        # 注意：其签名 CDN 拒绝任何 Referer（403 Wrong referer），故 header 仅带 UA、不带 Referer
        api_url = self._kvs_api(ext, origin, page)
        if api_url:
            return {"parse": 0, "url": api_url, "header": {"User-Agent": self.UA}}
        # 兜底：提不到直链，降级 parse:1 交嗅探/外部打开（只回 url 单字段）
        return {"parse": 1, "url": ext, "header": play_headers}

    def localProxy(self, param):
        return [404, "text/plain", {}, "not found"]

    # ================= 卡片解析 =================
    def _parse_cards(self, html):
        vlist = []
        if not html:
            return vlist
        # 时长表: gid -> mm:ss
        durs = {}
        for gid, t in re.findall(r"id=a(\d+)>.*?<span class=time>([^<]+)</span>", html, re.S):
            durs[gid] = t.strip()
        # 按 data-video 切块逐卡解析（兼容 inline background-image 与懶載 data-bg）
        blocks = re.split(r'(?=data-video="\d+")', html)
        for blk in blocks:
            mgid = re.match(r'data-video="(\d+)"', blk)
            if not mgid:
                continue
            gid = mgid.group(1)
            mext = re.search(r'/ktm/view\.cgi\?gid=\d+&u=([^"]+)"', blk)
            if not mext:
                continue
            ext = mext.group(1).strip()
            if self._is_premium_host(ext):
                continue  # 付费/试看站直接跳过
            # 封面：优先 data-bg，其次 background-image
            pic = ""
            mp = re.search(r"data-bg=['\"]([^'\"]+)['\"]", blk)
            if not mp:
                mp = re.search(r"background-image:url\(['\"]?([^'\")]+)['\"]?\)", blk)
            if mp:
                pic = mp.group(1)
            if pic.startswith("//"):
                pic = "https:" + pic
            # 标题：aria-label 优先，其次 span id=tr
            title = ""
            mt = re.search(r'aria-label="([^"]*)"', blk)
            if mt:
                title = mt.group(1)
            if not title:
                mt = re.search(r'id=tr\d+>([^<]+)', blk)
                if mt:
                    title = mt.group(1)
            title = self._unescape(title).strip() or self.SITE_NAME
            vlist.append({
                "vod_id": self._encode_id(ext),
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": durs.get(gid, ""),
            })
        # 兜底解析（结构变化时）：直接抓所有 ktm 链接
        if not vlist:
            for gid, ext in re.findall(r'/ktm/view\.cgi\?gid=(\d+)&u=([^"&][^"]*)"', html):
                ext = unquote(ext)
                if self._is_premium_host(ext):
                    continue
                vlist.append({
                    "vod_id": self._encode_id(ext),
                    "vod_name": self.SITE_NAME + " " + gid,
                    "vod_pic": "",
                    "vod_remarks": "",
                })
        return vlist

    # ================= 视频提取（分层）=================
    # 预览/预告/缩图片段特征——命中即视为「试看几秒」的假片，一律跳过
    _PREVIEW_MARKERS = (
        "/tmb/", "/thumb", "/thumbs/", "/preview", "preview.", "/trailer",
        "trailer.", "/screenshots/", "/sample", "sample.", "/promo/", "watermark",
    )

    def _is_preview(self, url):
        low = (url or "").lower()
        return any(k in low for k in self._PREVIEW_MARKERS)

    def _extract_video(self, page, page_url):
        if not page:
            return ""
        # --- 1) KVS flashvars（完整片直链，最可靠）---
        v = self._kvs_extract(page)
        if v and not self._is_preview(v):
            return v
        # --- 2) 优先 m3u8：先 jwplayer file:，再裸 m3u8（HLS 一般为完整片）---
        for pat in (r'["\']?file["\']?\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
                    r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*'):
            for mm in re.finditer(pat, page):
                cand = mm.group(mm.re.groups) if mm.re.groups else mm.group(0)
                cand = self._html_url(cand)
                if cand and not self._is_preview(cand):
                    return cand
        # --- 3) jwplayer file: mp4（跳过预告）---
        for mm in re.finditer(r'["\']?file["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']', page):
            cand = self._html_url(mm.group(1))
            if cand and not self._is_preview(cand):
                return cand
        # --- 4) og:video / contentUrl（跳过预告）---
        for pat in (r'property=["\']og:video(?::url)?["\']\s+content=["\']([^"\']+)["\']',
                    r'"contentUrl"\s*:\s*"([^"]+\.(?:mp4|m3u8)[^"]*)"'):
            for mm in re.finditer(pat, page):
                cand = self._html_url(mm.group(1))
                if cand and (".mp4" in cand or ".m3u8" in cand) and not self._is_preview(cand):
                    return cand
        # --- 5) <source src>（付费站常只放 /trailer/，务必过滤）---
        for mm in re.finditer(r'<source[^>]+src=["\']([^"\']+\.(?:mp4|m3u8)[^"\']*)["\']', page):
            cand = self._html_url(mm.group(1))
            if cand and not self._is_preview(cand):
                return cand
        # --- 6) 裸 .mp4（跳过缩图/预览片段）---
        for mm in re.finditer(r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*', page):
            cand = mm.group(0)
            if self._is_preview(cand):
                continue
            return cand
        return ""

    # ============ KVS base164 变体（/api/videofile.php）============
    # 新版 KVS(kt_player) 不再把 flashvars 内联进页面，而是异步 GET
    #   /api/videofile.php?video_id=<ID>&lifetime=864000  → JSON [{video_url: <base164>, ...}]
    # video_url 为「base164」编码：西里尔同形字替换回拉丁 + '~'→'=' + ',' 分段 base64
    #   段0=get_file 路径，段1+=query。拼 origin 得完整 get_file URL，302→302→签名 CDN。
    # 关键：最终签名 CDN「拒绝 Referer」（403 Wrong referer），播放 header 只可带 UA。
    _B164_HOMO = {
        u'А': 'A', u'В': 'B', u'Е': 'E', u'К': 'K', u'М': 'M', u'Н': 'H',
        u'О': 'O', u'Р': 'P', u'С': 'C', u'Т': 'T', u'Х': 'X', u'а': 'a',
        u'е': 'e', u'о': 'o', u'р': 'p', u'с': 'c', u'у': 'y', u'х': 'x',
        u'І': 'I', u'Ѕ': 'S', u'і': 'i', u'ѕ': 's', u'Ј': 'J', u'ј': 'j', u'Ү': 'Y',
    }

    def _b164_b64(self, seg):
        try:
            seg = seg.rstrip("=")
            pad = "=" * (-len(seg) % 4)
            return base64.b64decode(seg + pad).decode("utf-8", "ignore")
        except Exception:
            return ""

    def _base164_decode(self, v):
        if not v:
            return ""
        # 同形字还原 + '~'→'='
        buf = []
        for ch in v:
            buf.append(self._B164_HOMO.get(ch, ch))
        t = "".join(buf).replace("~", "=")
        parts = t.split(",")
        path = self._b164_b64(parts[0])
        if len(parts) > 1:
            extra = "&".join(self._b164_b64(p) for p in parts[1:] if p)
            if extra:
                path += "?" + extra
        return path

    def _kvs_api(self, ext, origin, page=""):
        # --- 求 video_id：URL /videos?/N、/video-N（vxxx）、页面 canonical/og:url（/v/CODE 短链）、
        #     页面 video_id 变量、末尾裸数字（anysex /371301/）依次尝试 ---
        vid = ""
        m = re.search(r'/videos?/(\d+)', ext) or re.search(r'/video-(\d+)', ext)
        if m:
            vid = m.group(1)
        if not vid and page:
            mc = (re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', page)
                  or re.search(r'property=["\']og:url["\']\s+content=["\']([^"\']+)["\']', page))
            if mc:
                real = self._html_url(mc.group(1))
                mm = re.search(r'/videos?/(\d+)', real) or re.search(r'/video-(\d+)', real)
                if mm:
                    vid = mm.group(1)
                    origin = self._origin_of(real)
                    ext = real
        if not vid and page:
            mv = re.search(r'video_id\s*[:=]\s*["\']?(\d+)', page)
            if mv:
                vid = mv.group(1)
        if not vid:
            m = re.search(r'/(\d+)/?(?:\?|$)', ext)
            if m:
                vid = m.group(1)
        if not vid:
            return ""
        api = origin + "/api/videofile.php?video_id=" + vid + "&lifetime=864000"
        txt = self._get(api, headers={"Referer": ext if ext.startswith("http") else origin + "/",
                                      "X-Requested-With": "XMLHttpRequest"})
        if not txt:
            return ""
        try:
            data = json.loads(txt)
        except Exception:
            return ""
        if not isinstance(data, list) or not data:
            return ""
        item = None
        for it in data:
            if str(it.get("is_default")) == "1" and it.get("video_url"):
                item = it
                break
        if item is None:
            for it in data:
                if it.get("video_url"):
                    item = it
                    break
        if not item:
            return ""
        path = self._base164_decode(item.get("video_url") or "")
        # 解码结果可能是绝对 URL（videohotmovs→txxxporn.tube）或 origin 相对 get_file 路径
        if path.startswith("http"):
            url = path
        elif path.startswith("/"):
            url = origin + path
        else:
            return ""
        # 返回渐进式 mp4（默认清晰度，跨站最稳；HLS 变体部分站点 404，不再强制转 m3u8）
        return url

    # ============ nuvid 系 CMS（/player_config 签名直链）============
    # 结构：视频页 <video data-video_hash="32hex" data-hash_time="10位时间戳" data-video_id="N">
    #   → GET https://m.<host>/player_config?video_hash=..&hash_time=..&video_id=..（Referer=视频页）
    #   → JSON {source:{lq,hq,4k}, files:{lq,hq,4k}}，取 hq>4k>lq
    #   → 直链 gcdn/bkcdn *.mp4?md5=..&expire=.. 206；播放 Referer 须为「站根」m.<host>/
    #   hash/time 每次刷新随时间变化，故须现抓视频页现请求（不可缓存复用）
    def _nuvid_resolve(self, page):
        if not page:
            return None
        vh = re.search(r'data-video_hash=["\']([a-f0-9]{16,})["\']', page)
        ht = re.search(r'data-hash_time=["\'](\d{6,})["\']', page)
        vid = re.search(r'data-video_id=["\'](\d+)["\']', page)
        if not (vh and ht and vid):
            return None
        # 求「移动站主机」：页面内 m.<host>/video/ 链接优先，其次 canonicalUrl 解码
        host = ""
        mm = re.search(r'https?://(m\.[a-z0-9.\-]+)/video/\d+', page)
        if mm:
            host = mm.group(1)
        if not host:
            cu = re.search(r'canonicalUrl=([^&"\'<> ]+)', page)
            if cu:
                dec = unquote(cu.group(1))
                host = urlparse(dec).netloc
        if not host:
            # 兜底：canonical 桌面站转 m. 子域
            mc = re.search(r'rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', page)
            if mc:
                nl = urlparse(self._html_url(mc.group(1))).netloc
                host = ("m." + nl[4:]) if nl.startswith("www.") else ("m." + nl)
        if not host:
            return None
        root = "https://" + host + "/"
        video_page = root + "video/" + vid.group(1) + "/"
        cfg = ("%splayer_config?video_hash=%s&hash_time=%s&video_id=%s"
               % (root, vh.group(1), ht.group(1), vid.group(1)))
        txt = self._get(cfg, headers={"Referer": video_page,
                                      "X-Requested-With": "XMLHttpRequest"})
        if not txt:
            return None
        try:
            j = json.loads(txt)
        except Exception:
            return None
        files = j.get("files") or {}
        src = j.get("source") or {}
        url = ""
        for key in ("hq", "4k", "lq"):
            for d in (files, src):
                v = d.get(key)
                if v and isinstance(v, str) and v.startswith("http"):
                    url = v
                    break
            if url:
                break
        if not url:
            return None
        return self._html_url(url), root

    # ============ KVS 经典 flashvars ============
    def _kvs_extract(self, page):
        # flashvars 内 license_code + video_url / video_alt_url
        lic = ""
        m = re.search(r"license_code\s*:\s*'([^']+)'", page)
        if m:
            lic = m.group(1)
        best = ""
        for key in ("video_url", "video_alt_url"):
            m = re.search(key + r"\s*:\s*'([^']+)'", page)
            if not m:
                continue
            url = m.group(1)
            if url.startswith("function/0/"):
                if lic:
                    url = self._kvs_decode(url[len("function/0/"):], lic)
                else:
                    continue
            if url and best == "":
                best = url
            # 优先选 video_url（第一个）
            if key == "video_url":
                return self._html_url(url)
        return self._html_url(best) if best else ""

    def _kvs_decode(self, url, license_code):
        # 复刻 KVS(kt_player) get_real_url 反混淆
        try:
            parts = url.split("/")
            # 找到需要打乱的段（含 file token 的那段一般在 4~5 之后）
            # KVS 标准：对 url 的 path 中被打乱的字符段做还原
            # 这里采用 yt-dlp 通用实现
            license_token = self._kvs_license_token(license_code)
            # url 形如: <scheme>://host/get_file/N/HASH/... 其中 HASH(32位) 被打乱
            # 取被打乱段（第一个 32 长度的十六进制样式段）
            idx = None
            for i, seg in enumerate(parts):
                if len(seg) >= 32 and re.match(r'^[0-9a-zA-Z_-]{32,}$', seg):
                    idx = i
                    break
            if idx is None:
                return url
            enc = parts[idx]
            n = len(enc)
            shuffled = list(enc)
            for i in range(min(len(license_token), n)):
                j = license_token[i]
                if j < n:
                    shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
            parts[idx] = "".join(shuffled)
            return "/".join(parts)
        except Exception:
            return url

    def _kvs_license_token(self, license_code):
        modlicense = license_code.replace("$", "").replace("0", "1")
        center = len(modlicense) // 2
        try:
            fronthalf = int(modlicense[:center + 1])
            backhalf = int(modlicense[center:])
        except Exception:
            return []
        modlicense = str(4 * abs(fronthalf - backhalf))
        result = []
        mlen = len(modlicense)
        for o in range(len(modlicense) - 1, -1, -1):
            for i in range(mlen):
                result.append(int(modlicense[o]) + int(modlicense[i]))
        return result

    # ================= 小工具 =================
    def _encode_id(self, ext):
        try:
            return base64.urlsafe_b64encode(ext.encode("utf-8")).decode("ascii")
        except Exception:
            return ext

    def _decode_id(self, vid):
        if not vid:
            return ""
        if vid.startswith("http"):
            return vid
        try:
            pad = "=" * (-len(vid) % 4)
            return base64.urlsafe_b64decode(vid + pad).decode("utf-8", "ignore")
        except Exception:
            return vid

    def _host_of(self, url):
        try:
            return urlparse(url).netloc or url
        except Exception:
            return url

    def _origin_of(self, url):
        try:
            p = urlparse(url)
            return "%s://%s" % (p.scheme or "https", p.netloc)
        except Exception:
            return url

    def _html_url(self, u):
        if not u:
            return ""
        u = u.replace("\\/", "/").replace("&amp;", "&")
        if u.startswith("//"):
            u = "https:" + u
        return u

    def _unescape(self, s):
        return (s.replace("&amp;", "&").replace("&quot;", '"')
                 .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
