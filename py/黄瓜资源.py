# coding: utf-8
# ============================================================
# 站点名称: 黄瓜资源（仓井阁）
# 主域名  : https://cangjingge153.click
# 备用域名: https://www.cangjingge153.click / http://cangjingge153.click
# 站点类型: MacCMS 标准影视站（成人向）
# 内容类型: 视频（成人向 AV / 国产 / 无码 / 有码 等）
# 结构说明（全部 URL 由真实页面 a 标签验证，法则19）:
#   - 分类页  : /type/id/{tid}.html
#   - 分类分页: /type/id/{tid}/{pg}.html   （第1页为 /type/id/{tid}.html）
#   - 详情页  : /info/id/{id}.html         （H1 标题、封面 img、两条播放线路同指 /play/id/{id}.html）
#   - 播放页  : /play/id/{id}.html
#   - 标签搜索: /hunt/{关键字}.html  分页 /hunt/{kw}/h/{pg}.html
#   - 列表卡片: <article class="vod"> 内 .vod-img a[href=/info/id/{id}.html] img.lazy[src=封面 alt=标题]
#               + .vod-txt a[title=标题]
# 播放地址（关键 —— 走 parse:0 + localProxy 去广告）:
#   播放页含 ①JSON-LD "contentUrl":"...index.m3u8"  ②JS  var playUrl = '...index.m3u8'
#   实测为 master(单一 2000kb 子流) → media 清单混插广告分片(不同目录/码率)。
#   正片分片为 AES-128 加密：媒体清单含 #EXT-X-KEY:METHOD=AES-128,URI="/.../key.key"
#   （广告段落用 METHOD=NONE）。key URI 为相对路径，localProxy 必须改绝对地址，
#   否则播放器按代理 base(127.0.0.1) 解析 → 取金钥 404 → 无法解密黑屏（历史根因）。
# 搜索: 无公开 JSON API（api.php/provide、ajax/suggest 皆空）→ 走 /hunt/ 标签匹配 HTML 解析。
# 最后验证: 2026-09-25
# 来源: 用户提供 URL https://cangjingge153.click/
# ============================================================
import re
import sys
import time
from urllib.parse import quote, unquote, urljoin

from base.spider import Spider as BaseSpider

# ============================================================
# 换站只改下面三行（法则18）
# ============================================================
MAIN = "cangjingge153.click"
HOST = "https://cangjingge153.click"
FALLBACK_HOSTS = [
    "https://cangjingge153.click",
    "https://www.cangjingge153.click",
    "http://cangjingge153.click",
]

UA = ("Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36")


class Spider(BaseSpider):
    # ---------------- 生命周期 ----------------
    def __init__(self):
        # __init__ 零网络（法则16）
        self.extend = ""
        self._host = HOST
        self.hosts = list(FALLBACK_HOSTS)
        self.headers = {
            "User-Agent": UA,
            "Referer": HOST + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        # 静态视频分类（法则16/17：分类硬编码、零网络）
        # 仅收录“有视频内容”的分区：
        #   - 剔除纯图 CG/漫画（575/576/579）与 AI 漫剧（872）；
        #   - 剔除“精品视频区”里已废弃且实测 0 卡片的旧劇情分区（672/674/678/679 等 67x 段，
        #     真实页面仅剩标题、无 /info/id/ 卡片，2026-09-25 实测确认）；
        #   - “小说区”694-700（含 693）实测为纯文字小说、播放页无 m3u8/mp4，非视频，故不收录。
        self.classes = [
            {"type_id": "239", "type_name": "精品推荐"},
            {"type_id": "240", "type_name": "国产色情"},
            {"type_id": "241", "type_name": "主播直播"},
            {"type_id": "242", "type_name": "亚洲无码"},
            {"type_id": "243", "type_name": "亚洲有码"},
            {"type_id": "244", "type_name": "中文字幕"},
            {"type_id": "245", "type_name": "巨乳美乳"},
            {"type_id": "246", "type_name": "人妻熟女"},
            {"type_id": "247", "type_name": "强奸乱伦"},
            {"type_id": "248", "type_name": "欧美精品"},
            {"type_id": "249", "type_name": "萝莉少女"},
            {"type_id": "250", "type_name": "伦理三级"},
            {"type_id": "251", "type_name": "成人动漫"},
            {"type_id": "252", "type_name": "自拍偷拍"},
            {"type_id": "253", "type_name": "制服丝袜"},
            {"type_id": "254", "type_name": "口交颜射"},
            {"type_id": "255", "type_name": "日本精品"},
            {"type_id": "256", "type_name": "Cosplay"},
            {"type_id": "257", "type_name": "素人自拍"},
            {"type_id": "258", "type_name": "台湾辣妹"},
            {"type_id": "259", "type_name": "韩国御姐"},
            {"type_id": "265", "type_name": "91探花"},
            {"type_id": "266", "type_name": "网红流出"},
            {"type_id": "269", "type_name": "女优系列"},
            {"type_id": "277", "type_name": "传媒出品"},
            {"type_id": "282", "type_name": "麻豆传媒"},
            {"type_id": "285", "type_name": "AI换脸"},
            {"type_id": "297", "type_name": "标清电影"},
            {"type_id": "298", "type_name": "高清电影"},
            {"type_id": "302", "type_name": "欧美无码"},
            {"type_id": "341", "type_name": "SM调教"},
            {"type_id": "351", "type_name": "AV解说"},
            {"type_id": "871", "type_name": "AI成人短剧"},
            {"type_id": "873", "type_name": "AI成人视频"},
        ]
        self.filters = {}

    def getName(self):
        return "黄瓜资源"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # init 可联网：探测可用主域（跟随 301 到 canonical），失败则保留默认 HOST（法则18）
        self.extend = extend or ""
        try:
            self._resolve_host()
        except Exception:
            pass

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        if not url:
            return False
        return bool(re.search(r"\.(m3u8|mp4|flv|ts|mkv|avi|mov|m4v)(\?|$)", url, re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        """代理并清洗 m3u8：过滤前贴片/中插广告分片，只保留正片目录分片。
        规则（法则26）：仅代理 m3u8 文本本身；分片一律改绝对地址，交由播放器
        直连 CDN，禁止把 ts 分片塞进 localProxy（避免盒子 OOM）。
        """
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url") or param.get("u") or ""
            else:
                url = str(param or "")
            if not url:
                return [404, "text/plain", b""]
            if "%" in url:
                try:
                    url = unquote(url)
                except Exception:
                    pass
            text = self._fetch(url)
            if not text or "#EXTM3U" not in text:
                return [404, "text/plain", b""]
            cleaned = self._filter_m3u8(text, url)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception:
            return [404, "text/plain", b""]

    # ---------------- m3u8 去广告管线（内联自实作，不依赖外部模組） ----------------
    def _proxy_url(self, target):
        """把真实 m3u8 地址包装成本地代理地址；取不到 getProxyUrl 时回退直链。"""
        if not target:
            return target
        base = ""
        try:
            base = self.getProxyUrl() or ""
        except Exception:
            base = ""
        if not base:
            return target
        if base.endswith("?") or base.endswith("&"):
            sep = ""
        elif "?" in base:
            sep = "&"
        else:
            sep = "?"
        return base + sep + "url=" + quote(target, safe="") + "&type=m3u8"

    @staticmethod
    def _resolve_url(uri, base_url):
        if not uri:
            return ""
        if uri.startswith("http"):
            return uri
        if uri.startswith("//"):
            return "https:" + uri
        try:
            return urljoin(base_url, uri)
        except Exception:
            return uri

    def _abs_tag_uri(self, line, base_url):
        """把 #EXT-X-KEY / #EXT-X-MAP 里的 URI="..." 改成绝对 CDN 地址。
        相对 key URI 若不改绝对，播放器会按代理 base(127.0.0.1) 解析 → 取金钥 404。"""
        m = re.search(r'URI="([^"]*)"', line)
        if not m or not m.group(1):
            return line
        absu = self._resolve_url(m.group(1), base_url)
        return line[:m.start(1)] + absu + line[m.end(1):]

    def _filter_m3u8(self, text, base_url, depth=0):
        """第2层：主表（多码率）拉平为单跳代理——直接抓子流媒体清单过滤后回传；
        媒体清单走分片过滤。禁止把子流再包成嵌套 127.0.0.1 代理 URL（Bug1）。
        """
        if "#EXT-X-STREAM-INF" in text:
            return self._flatten_master(text, base_url, depth)
        return self._filter_media(text, base_url)

    def _flatten_master(self, text, base_url, depth=0):
        """主表拉平（single proxy hop）：取首个/唯一子流绝对地址，直接抓该 media 清单
        并过滤后回传，而非回一个包含 127.0.0.1 嵌套代理的 master（盒子请求嵌套 URL 会 404）。
        depth 防护最多 2 层，避免罕见的 master→master 嵌套死循环。
        """
        if depth >= 2:
            return text if text.endswith("\n") else text + "\n"
        sub = ""
        expect_uri = False
        for raw in text.split("\n"):
            s = raw.strip()
            if not s:
                continue
            if s.startswith("#EXT-X-STREAM-INF"):
                expect_uri = True
                continue
            if s.startswith("#"):
                continue
            # 首个子流 URI 行（无论是否紧跟 STREAM-INF 均取第一条）
            sub = self._resolve_url(s, base_url)
            break
        if not sub:
            # 无法定位子流：回退原文（分片交播放器直连，虽可能含广告但可播）
            return text if text.endswith("\n") else text + "\n"
        media = self._fetch(sub)
        if not media or "#EXTM3U" not in media:
            # 抓不到子流清单：回退原主表原文
            return text if text.endswith("\n") else text + "\n"
        # 子流可能仍是 master（罕见嵌套）→ 递归再拉平一层
        return self._filter_m3u8(media, sub, depth + 1)

    def _filter_media(self, text, base_url):
        """媒体清单去广告：
        第3层 正片目录锚点：KEY URI 目录优先，无 KEY 回退 m3u8 URL 目录；
        第4层 分片过滤：只留锚点目录前缀分片，EXTINF/DISCONTINUITY/BYTERANGE 与分片成对丢弃，
               分片改绝对地址；leading 的孤立 DISCONTINUITY 抑制；
        第5层 全滤兜底：仅当 kept==0（全被判为广告、正片一段不剩）时才整体回退不过滤，
               避免“重广告短片（广告段数 > 正片段数）”误触发回退导致广告漏网（Bug2）。
        """
        lines = text.split("\n")
        base_dir = base_url.rsplit("/", 1)[0]
        # 锚点目录：优先 KEY URI 所在目录
        anchor = ""
        for ln in lines:
            m = re.search(r'#EXT-X-KEY:[^\n]*URI="([^"]+)"', ln)
            if m:
                key_abs = self._resolve_url(m.group(1), base_url)
                anchor = key_abs.rsplit("/", 1)[0]
                break
        if not anchor:
            anchor = base_dir

        out = []
        buf = []          # 缓冲 EXTINF/DISCONTINUITY/BYTERANGE，等待与分片成对处理
        removed = 0
        kept = 0
        kept_any = False
        for raw in lines:
            s = raw.strip()
            if not s:
                continue
            if s.startswith("#EXTINF") or s.startswith("#EXT-X-DISCONTINUITY") \
                    or s.startswith("#EXT-X-BYTERANGE") or s.startswith("#EXT-X-PROGRAM-DATE-TIME"):
                buf.append(s)
                continue
            if s.startswith("#"):
                # 头部/结尾标签透传；但 #EXT-X-KEY / #EXT-X-MAP 的 URI 必须改绝对地址，
                # 否则播放器会把相对 key URI 依代理 base(127.0.0.1:9978) 解析 → 取金钥 404 → 无法解密（根因）。
                if s.startswith("#EXT-X-KEY") or s.startswith("#EXT-X-MAP"):
                    s = self._abs_tag_uri(s, base_url)
                out.append(s)
                continue
            # 分片 URI 行
            seg_abs = self._resolve_url(s, base_url)
            if seg_abs.startswith(anchor):
                # 保留：先冲刷缓冲标签（抑制开头孤立的 DISCONTINUITY），再放绝对分片
                for t in buf:
                    if (not kept_any) and t.startswith("#EXT-X-DISCONTINUITY"):
                        continue
                    out.append(t)
                out.append(seg_abs)
                kept += 1
                kept_any = True
            else:
                # 丢弃广告分片及其成对标签（含前置 DISCONTINUITY）
                removed += 1
            buf = []

        # 第5层 全滤兜底：仅当正片一段不剩（kept==0）时才回退原文，避免整片黑屏；
        # 不再用 removed>kept 判据（重广告短片会误触发，Bug2）。
        if kept == 0 and removed > 0:
            try:
                self.log({"ad_filter": "fallback_no_filter", "removed": removed, "kept": kept})
            except Exception:
                pass
            return text if text.endswith("\n") else text + "\n"
        try:
            self.log({"ad_filter": "ok", "removed": removed, "kept": kept, "anchor": anchor})
        except Exception:
            pass
        return "\n".join(out) + "\n"

    # ---------------- 域名/网络 ----------------
    def host(self):
        return self._host

    def _resolve_host(self):
        """探测首个能返回含卡片列表页的主域并缓存到 self._host。"""
        for h in self.hosts:
            try:
                r = self.fetch(h + "/", headers=self.headers, timeout=12)
                if r and getattr(r, "status_code", 0) == 200 and r.text and 'class="vod"' in r.text:
                    self._host = h.rstrip("/")
                    self.headers["Referer"] = self._host + "/"
                    return
            except Exception:
                continue

    def _fetch(self, url):
        """多域容错抓取，返回 HTML 文本。对站点 429 限流做一次短暂退避重试。"""
        cand = [url] if url.startswith("http") else [self._host + url]
        # 主域失败时轮询其它备用域
        if not url.startswith("http"):
            cand += [h.rstrip("/") + url for h in self.hosts if h.rstrip("/") != self._host]
        for u in cand:
            for attempt in range(2):  # 首次 + 429 退避重试一次
                try:
                    r = self.fetch(u, headers=self.headers, timeout=15)
                    code = getattr(r, "status_code", 0) if r else 0
                    if r and code == 200 and r.text:
                        return r.text
                    # 站点限流：429 或返回 429 提示页，短暂退避后重试一次
                    if code == 429 or (r and r.text and "<title>429</title>" in r.text):
                        if attempt == 0:
                            try:
                                time.sleep(1.2)
                            except Exception:
                                pass
                            continue
                    break
                except Exception as e:
                    try:
                        self.log({"fetch_fail": u, "err": str(e)})
                    except Exception:
                        pass
                    break
        return ""

    # ---------------- 工具 ----------------
    @staticmethod
    def _clean(s):
        if not s:
            return ""
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&amp;", "&").replace("&nbsp;", " ").replace("\u00a0", " ")
             .replace("&quot;", '"').replace("&#039;", "'").replace("&lt;", "<")
             .replace("&gt;", ">"))
        return s.strip()

    def _abs(self, u):
        if not u:
            return ""
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        return self._host + (u if u.startswith("/") else "/" + u)

    def _card_list(self, html):
        """解析 <article class="vod"> 卡片；把 name/pic 打包进 vod_id 供 detailContent 零网络拆包（|$| 分隔，法则21 不用裸 $）。"""
        out = []
        if not html:
            return out
        for block in re.findall(r'<article class="vod">(.*?)</article>', html, re.S):
            m = re.search(r'/info/id/(\d+)\.html', block)
            if not m:
                continue
            vid = m.group(1)
            # 标题：优先 .vod-txt a[title]，兜底 img alt
            name = ""
            mt = re.search(r'<div class="vod-txt">\s*<a[^>]+title="([^"]*)"', block, re.S)
            if mt:
                name = self._clean(mt.group(1))
            if not name:
                ma = re.search(r'<img[^>]+alt="([^"]*)"', block)
                if ma:
                    name = self._clean(ma.group(1))
            # 封面：img.lazy 的 src / data-src / data-original
            pic = ""
            mp = re.search(r'<img[^>]+class="lazy"[^>]+(?:data-src|data-original|src)="([^"]+)"', block)
            if not mp:
                mp = re.search(r'<img[^>]+(?:data-src|data-original|src)="([^"]+)"', block)
            if mp:
                pic = self._abs(mp.group(1))
            if not name:
                continue
            out.append({
                "vod_id": vid + "|$|" + name + "|$|" + pic,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return out

    def _max_page(self, html, tid):
        """从分页链接 /type/id/{tid}/{pg}.html 取最大页码，兜底 1。"""
        if not html:
            return 1
        nums = re.findall(r'/type/id/' + re.escape(str(tid)) + r'/(\d+)\.html', html)
        pgs = [int(n) for n in nums if n.isdigit()]
        return max(pgs) if pgs else 1

    # ---------------- 首页 ----------------
    def homeContent(self, filter):
        # 零网络，秒出（法则16）
        return {"class": self.classes, "filters": self.filters}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch("/")
        return {"list": self._card_list(html)[:40]}

    # ---------------- 分类 ----------------
    def categoryContent(self, tid, pg, filter, extend):
        page = 1
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        tid = str(tid or "").strip().strip("/")
        if page <= 1:
            url = "/type/id/" + tid + ".html"
        else:
            url = "/type/id/" + tid + "/" + str(page) + ".html"
        html = self._fetch(url)
        lst = self._card_list(html)
        pc = self._max_page(html, tid)
        if pc < page:
            pc = page
        return {
            "list": lst,
            "page": page,
            "pagecount": pc,
            "limit": len(lst) if lst else 16,
            "total": pc * (len(lst) if lst else 16),
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
        # 拆包：vid|$|name|$|pic（列表阶段打包，法则35：先归一化）
        parts = raw.split("|$|")
        vid = parts[0].strip()
        name = parts[1].strip() if len(parts) > 1 else ""
        pic = parts[2].strip() if len(parts) > 2 else ""
        # 提取纯数字 id（兜底：raw 本身即 /info/id 或纯数字）
        mid = re.search(r"(\d+)", vid)
        vid = mid.group(1) if mid else vid

        # 若缺标题/封面则回详情页补全（列表已打包时零网络）
        if not name or not pic:
            html = self._fetch("/info/id/" + vid + ".html")
            if html:
                if not name:
                    mt = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
                    if mt:
                        name = self._clean(mt.group(1))
                if not pic:
                    mp = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
                    if not mp:
                        mp = re.search(r'<img[^>]+(?:data-src|src)="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', html)
                    if mp:
                        pic = self._abs(mp.group(1))

        # 单一播放页；播放 id 用纯数字（法则21：无裸 $）
        vod = {
            "vod_id": raw,
            "vod_name": name or ("视频 " + vid),
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_year": "",
            "vod_area": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": name or "",
            "vod_play_from": "黄瓜线路",
            "vod_play_url": "正片$" + vid,
        }
        return {"list": [vod]}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        page = 1
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        kw = quote(str(key or ""))
        if page <= 1:
            url = "/hunt/" + kw + ".html"
        else:
            url = "/hunt/" + kw + "/h/" + str(page) + ".html"
        html = self._fetch(url)
        return {"list": self._card_list(html), "page": page}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "")
        if "$" in raw:
            raw = raw.split("$", 1)[1]
        raw = raw.strip()

        # 已是直链
        if raw.startswith("http") and re.search(r"\.(m3u8|mp4|flv|ts)(\?|$)", raw, re.I):
            return {"parse": 0, "url": raw,
                    "header": {"User-Agent": UA, "Referer": self._host + "/"}}

        mid = re.search(r"(\d+)", raw)
        vid = mid.group(1) if mid else raw
        m3u8 = self._extract_m3u8(vid)
        if m3u8:
            # 走 localProxy 去广告（前贴片/中插）；取不到代理时 _proxy_url 回退直链
            return {"parse": 0, "url": self._proxy_url(m3u8),
                    "header": {"User-Agent": UA, "Referer": self._host + "/"}}
        # 兜底：交盒子嗅探播放页（法则7 降级）
        return {"parse": 1, "url": self._host + "/play/id/" + vid + ".html",
                "header": {"User-Agent": UA, "Referer": self._host + "/"}}

    def _extract_m3u8(self, vid):
        """从 /play/id/{id}.html 提取 m3u8 直链：JSON-LD contentUrl 或 JS playUrl。"""
        html = self._fetch("/play/id/" + str(vid) + ".html")
        if not html:
            return ""
        # ① Aliplayer: var playUrl = '...m3u8'
        m = re.search(r'var\s+playUrl\s*=\s*[\'"]([^\'"]+\.m3u8[^\'"]*)[\'"]', html)
        if m:
            return self._abs(m.group(1))
        # ② JSON-LD contentUrl
        m = re.search(r'"contentUrl"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
        if m:
            return self._abs(m.group(1).replace("\\/", "/"))
        # ③ 兜底：任意 m3u8
        m = re.search(r'https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*', html)
        if m:
            return self._abs(m.group(0))
        return ""


# ============================================================
# 本地冒烟（仅在直接运行时；FongMi/TVBox 运行时不会走到这里）
# ============================================================
if __name__ == "__main__":
    print("huanggua spider module OK", file=sys.stderr)
