# coding=utf-8
# !/usr/bin/python
"""
FongMi / TVBox T3 (type=3) 爬虫源
站点：蝴蝶情色（hyhongli）  主域 https://hyhongli.com  多语言，中文用 /zh/ 前缀
类型：日本 AV 影片站（成人）
说明：
  - 反爬：Cloudflare 盾（盒子原生 self.fetch 通常直接通过；本机测试需 curl_cffi impersonate）。
          首页/列表/详情 HTML 被 JS 混淆为 document.write(FUNC(unescape("hex..."))) ——
          抓出 200+ 位的 hex blob 后 binascii.unhexlify 解码即得真实 HTML。见 _decode_html。
  - 列表卡片：<a href="/zh/{ID}.html" ... class="img" title="标题">
                <img data-original="https://cache-xxxx.sgvafw.com/base/{b64}.cache" ...>
             封面为 CDN cache 直链（base64 解码得原图 fourhoi.com/...），实测无防盗链可直接用。
  - 分类入口：
      最新   /zh/new/index.html      翻页 /zh/new/index-{N}.html
      热门   /zh/hot/index.html      翻页 /zh/hot/index-{N}.html
      list   /zh/list/{catid}.html   翻页 /zh/list/{catid}-{N}.html
             44002=中文字幕 44247=无码破解 44251=英文字幕 80001~80018=片商
      标签   /zh/tags?key={名称}&page={N}
  - 搜索：/zh/search?key={关键词}&page={N}  （参数为 key，非 wd）
  - 详情：/zh/{ID}.html ，页内 window.videoConfig = { fanhao,url,vtthas,img,vtt,title }
          其中 url 即 m3u8 master（带 verify 签名 token，每次开页新发）。
  - 播放：master playlist 必须带 Origin/Referer=hyhongli.com 才返回真清单（否则退化为假清单）；
          子清单与分片为绝对 URL 且无需特殊 header。故 playerContent 每次重取详情页拿新鲜 token，
          经 localProxy 代理 master（补 Origin/Referer 头）交播放器 parse:0，子清单/分片播放器直连。
          实测 master 含 360p/480p/720p/1080p 四档，分片为伪装 .jpeg 实为 video/mp2t，无广告注入。
最后验证：2026-09-30
"""
import sys
import re
import binascii
from urllib.parse import quote

sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        def init(self, extend=""):
            pass


class Spider(Spider):

    # ============ 站点信息（换站只改这里） ============
    siteName = "蝴蝶情色"
    MAIN = "https://hyhongli.com"

    UA = ("Mozilla/5.0 (Linux; Android 14; 22127RK46C/Pixel5) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    # 首页分类（静态硬编码，零网络）
    _CATE = [
        {"type_name": "最新", "type_id": "new"},
        {"type_name": "热门", "type_id": "hot"},
        {"type_name": "中文字幕", "type_id": "list/44002"},
        {"type_name": "无码破解", "type_id": "list/44247"},
        {"type_name": "英文字幕", "type_id": "list/44251"},
        {"type_name": "片商", "type_id": "studio"},
        {"type_name": "标签", "type_id": "tags"},
    ]

    # 片商（list/8000x）
    _STUDIO = [
        ("FC2", "80001"), ("HEYZO", "80002"), ("Tokyo-Hot", "80003"),
        ("1pondo", "80004"), ("Caribbeancom", "80005"), ("10musume", "80006"),
        ("pacopacomama", "80007"), ("Gachinco", "80008"), ("XXX-AV", "80009"),
        ("C0930", "80010"), ("H0930", "80011"), ("H4610", "80012"),
        ("SIRO", "80013"), ("LUXU", "80014"), ("GANA", "80015"),
        ("MIUM", "80016"), ("SCUTE", "80017"), ("ARA", "80018"),
    ]

    # 热门标签（显示名 = 请求 key，请求时 URL 编码）
    _TAGS = [
        "中文字幕", "无码", "破解", "巨乳", "熟女", "人妻", "少女", "美腿",
        "丝袜", "制服", "护士", "老师", "学生", "偷拍", "露出", "中出",
        "口交", "颜射", "潮吹", "调教", "凌辱", "多P", "痴女", "痴汉",
        "出轨", "诱惑", "泡姬", "按摩", "母乳", "空姐", "OL", "偶像",
        "主播", "家政妇", "情侣", "医生", "电车", "学校", "泳池", "监狱",
    ]

    _host = ""

    def getName(self):
        return self.siteName

    def init(self, extend=""):
        self.extend = extend
        self._host = self.MAIN
        return

    def isVideoFormat(self, url):
        pats = ['.m3u8', '.mp4', '.flv', '.mkv', '.ts', 'playlist']
        return any(p in (url or '') for p in pats)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ---------------- 域名 ----------------
    def host(self):
        return self._host or self.MAIN

    # ---------------- 公共请求 ----------------
    def _headers(self):
        return {
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host() + "/",
        }

    def _decode_html(self, text):
        """首页/列表/详情 HTML 被混淆为 document.write(...unescape("hex...")...)。
        若检测到长 hex blob 则 unhexlify 解码，否则原样返回。"""
        if not text:
            return ""
        # 已是正常 HTML（含站内链接卡片）则直接用
        if "/zh/" in text and 'href="/zh/' in text:
            # 有可能同时含 hex（脚本），但正常内容已在则直接返回
            if 'class="img"' in text or 'itemprop="name headline"' in text or "videoConfig" in text:
                return text
        hx = re.findall(r'"([0-9a-fA-F]{200,})"', text)
        if hx:
            try:
                return binascii.unhexlify(hx[0]).decode("utf-8", "ignore")
            except Exception:
                pass
        return text

    def _get_html(self, path):
        url = path if path.startswith("http") else (self.host() + path)
        try:
            r = self.fetch(url, headers=self._headers())
            if not r or getattr(r, "status_code", 0) != 200:
                return ""
            return self._decode_html(r.text or "")
        except Exception:
            return ""

    # ---------------- 文本清理 ----------------
    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<[^>]+>", "", s)
        s = s.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
        s = s.replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
        return s.strip()

    # ---------------- 卡片解析 ----------------
    def _card_list(self, html):
        """解析列表卡片：a.img[href=/zh/{id}.html][title] + img[data-original]。"""
        out, seen = [], set()
        if not html:
            return out
        pat = re.compile(
            r'href="/zh/(\d+)\.html"[^>]*class="img"[^>]*title="([^"]*)"'
            r'[^>]*>\s*<img[^>]*data-original="([^"]+)"',
            re.S)
        for m in pat.finditer(html):
            vid, title, pic = m.group(1), m.group(2), m.group(3)
            if vid in seen:
                continue
            seen.add(vid)
            out.append({
                "vod_id": vid,
                "vod_name": self._clean(title) or vid,
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return out

    def _pagecount(self, html, pg):
        nums = []
        nums += re.findall(r'index-(\d+)\.html', html or "")
        nums += re.findall(r'/zh/list/\d+-(\d+)\.html', html or "")
        nums += re.findall(r'[?&]page=(\d+)', html or "")
        if nums:
            try:
                mx = max(int(x) for x in nums)
                return max(mx, pg)
            except Exception:
                pass
        # 无翻页信息但当前页有满卡 → 假定还有下一页
        cards = len(re.findall(r'href="/zh/\d+\.html"[^>]*class="img"', html or ""))
        return (pg + 1) if cards >= 16 else pg

    # ---------------- 首页 ----------------
    def homeContent(self, filter):
        result = {"class": self._CATE}
        result["filters"] = {
            "studio": [{"key": "studio", "name": "片商",
                        "value": [{"n": nm, "v": cid} for (nm, cid) in self._STUDIO]}],
            "tags": [{"key": "tag", "name": "标签",
                      "value": [{"n": t, "v": t} for t in self._TAGS]}],
        }
        return result

    def homeVideoContent(self):
        html = self._get_html("/zh/new/index.html")
        return {"list": self._card_list(html)}

    # ---------------- 分类 ----------------
    def _parse_extend(self, extend):
        if isinstance(extend, dict):
            return extend
        if not extend:
            return {}
        s = str(extend).strip()
        if s.startswith("{"):
            try:
                import json
                return json.loads(s)
            except Exception:
                s = s.strip("{}")
        out = {}
        for pair in re.split(r'[&,;]', s):
            if "=" in pair:
                k, _, v = pair.partition("=")
                k = k.strip().strip('"').strip("'")
                v = v.strip().strip('"').strip("'")
                if k:
                    out[k] = v
        return out

    def _cat_path(self, tid, pg, ext):
        """依 tid 与页码组出请求路径。"""
        tid = str(tid or "new")
        # 标签：/zh/tags?key=名称&page=N
        if tid == "tags":
            key = ext.get("tag") or (self._TAGS[0] if self._TAGS else "")
            key = quote(str(key))
            if pg <= 1:
                return "/zh/tags?key=%s" % key
            return "/zh/tags?key=%s&page=%d" % (key, pg)
        # 片商：filter 选择的 catid（80001~80018），默认第一个
        if tid == "studio":
            cid = ext.get("studio") or (self._STUDIO[0][1] if self._STUDIO else "80001")
            base = "/zh/list/%s" % str(cid)
            return (base + ".html") if pg <= 1 else ("%s-%d.html" % (base, pg))
        # list/{catid}
        if tid.startswith("list/"):
            base = "/zh/" + tid
            return (base + ".html") if pg <= 1 else ("%s-%d.html" % (base, pg))
        # new / hot
        if tid in ("new", "hot"):
            base = "/zh/%s/index" % tid
            return (base + ".html") if pg <= 1 else ("%s-%d.html" % (base, pg))
        # 兜底：当作 list catid 数字
        base = "/zh/list/%s" % tid.strip("/")
        return (base + ".html") if pg <= 1 else ("%s-%d.html" % (base, pg))

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        ext = self._parse_extend(extend)
        path = self._cat_path(tid, pg, ext)
        html = self._get_html(path)
        vods = self._card_list(html)
        pc = self._pagecount(html, pg)
        return {
            "list": vods,
            "page": pg,
            "pagecount": pc,
            "limit": len(vods) or 16,
            "total": (len(vods) or 16) * pc,
        }

    # ---------------- 详情 ----------------
    def _norm_ids(self, ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            return str(ids[0]) if ids else ""
        if isinstance(ids, bytes):
            try:
                return ids.decode("utf-8", "ignore")
            except Exception:
                return ""
        return str(ids)

    def _detail_id(self, vid):
        """归一化为纯数字 ID。"""
        vid = str(vid).strip()
        m = re.search(r"/zh/(\d+)\.html", vid)
        if m:
            return m.group(1)
        m = re.search(r"(\d{5,})", vid)
        return m.group(1) if m else vid.strip("/")

    def _skeleton(self, vid, name="", pic=""):
        return {
            "vod_id": vid,
            "vod_name": name or vid,
            "vod_pic": pic,
            "vod_content": "",
            "vod_play_from": self.siteName,
            "vod_play_url": "正片$%s" % vid,
        }

    def _extract_config(self, html):
        """抓 window.videoConfig 字段字典。"""
        if not html:
            return {}
        m = re.search(r'window\.videoConfig\s*=\s*\{(.*?)\};', html, re.S)
        blob = m.group(1) if m else html
        out = {}
        for k in ("url", "img", "title", "fanhao", "vtthas", "vtt"):
            mm = re.search(r'\b%s\s*:\s*"([^"]*)"' % k, blob)
            if mm:
                out[k] = mm.group(1)
        return out

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        vid = self._detail_id(raw)
        html = self._get_html("/zh/%s.html" % vid)
        if not html:
            return {"list": [self._skeleton(vid)]}

        cfg = self._extract_config(html)
        name = self._clean(cfg.get("title") or "")
        if not name:
            mt = re.search(r'<meta property="og:title" content="([^"]*)"', html)
            name = self._clean(mt.group(1)) if mt else vid
        pic = cfg.get("img") or ""
        if not pic:
            mi = re.search(r'<meta property="og:image" content="([^"]*)"', html)
            pic = mi.group(1) if mi else ""
        fanhao = cfg.get("fanhao") or ""

        # 简介：og:description
        md = re.search(r'<meta property="og:description" content="([^"]*)"', html)
        content = self._clean(md.group(1)) if md else ""

        vod = {
            "vod_id": vid,
            "vod_name": name or vid,
            "vod_pic": pic,
            "vod_remarks": fanhao,
            "vod_content": content,
            "vod_play_from": self.siteName,
            "vod_play_url": "正片$%s" % vid,   # 播放交 playerContent 懒解析取新鲜 token
        }
        return {"list": [vod]}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        k = quote(str(key))
        if pg <= 1:
            path = "/zh/search?key=%s" % k
        else:
            path = "/zh/search?key=%s&page=%d" % (k, pg)
        html = self._get_html(path)
        return {"list": self._card_list(html), "page": pg}

    # ---------------- 播放 ----------------
    def _proxy(self, url, typ):
        try:
            base = self.getProxyUrl() or ""
        except Exception:
            base = ""
        if not base:
            return url
        sep = "" if base.endswith(("?", "&")) else ("&" if "?" in base else "?")
        return base + sep + "url=" + quote(url, safe="") + "&type=" + typ

    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "")
        header = {"User-Agent": self.UA,
                  "Origin": self.host(),
                  "Referer": self.host() + "/"}

        # 直链（已是 m3u8）→ 经代理补头
        if raw.startswith("http") and ("playlist.m3u8" in raw or ".m3u8" in raw):
            return {"parse": 0, "url": self._proxy(raw, "m3u8"), "header": header}

        vid = self._detail_id(raw)
        html = self._get_html("/zh/%s.html" % vid)
        cfg = self._extract_config(html)
        murl = cfg.get("url") or ""

        if murl and murl.startswith("http"):
            # master 需带 Origin/Referer 才返回真清单 → 走 localProxy 代理
            return {"parse": 0, "url": self._proxy(murl, "m3u8"), "header": header}

        # 兜底：页内任意 m3u8
        mm = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or "")
        if mm:
            return {"parse": 0, "url": self._proxy(mm.group(0), "m3u8"), "header": header}
        return {"parse": 0, "url": "", "header": header}

    # ---------------- 本地代理（master m3u8 补头 / 图片） ----------------
    def localProxy(self, param):
        try:
            param = param or {}
            url = param.get("url") or ""
            typ = param.get("type") or ""
            if not url:
                return None
            h = {"User-Agent": self.UA,
                 "Origin": self.MAIN,
                 "Referer": self.MAIN + "/",
                 "Accept": "*/*"}
            r = self.fetch(url, headers=h)
            if not r or getattr(r, "status_code", 0) != 200:
                return None
            if typ == "m3u8":
                text = r.text or ""
                # 子清单为绝对 URL，播放器直连；此处仅返回真 master
                return [200, "application/vnd.apple.mpegurl", text]
            data = r.content
            return [200, self._mime(data), data]
        except Exception:
            return None

    def _mime(self, data):
        if data[:3] == b"\xff\xd8\xff":
            return "image/jpeg"
        if data[:4] == b"\x89PNG":
            return "image/png"
        if data[:4] == b"GIF8":
            return "image/gif"
        if data[:4] == b"RIFF":
            return "image/webp"
        return "image/jpeg"
