# coding=utf-8
# 古装AI (ai.guzhuangai.cc) — 标准 MacCMS 成人资源聚合站  T3(type=3)
# 入口: https://ai.guzhuangai.cc/rukou/
#   分类:  /rukou/index.php/vod/type/id/{tid}/page/{pg}.html
#   详情:  /rukou/index.php/vod/detail/id/{id}.html
#   播放页:/rukou/index.php/vod/play/id/{id}/sid/{sid}/nid/{nid}.html  -> player_aaaa.url = 直链 m3u8
#   搜索:  /rukou/index.php/vod/search/wd/{kw}.html  (GET)
import sys, re, json
sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        pass

# ===== 站点信息（换站只改这两行）=====
SITE_NAME = "古装AI"
MAIN = "https://ai.guzhuangai.cc"          # 主域（协议+域名，不含 /rukou/）
# ====================================
PREFIX = "/rukou"                           # 子目录前缀
HOST = ""                                   # 留空自动探测
FALLBACK_HOSTS = ["https://ai.guzhuangai.cc"]

UA = "Mozilla/5.0 (Linux; Android 14; 22127RK46C/Pixel5) Chrome/120 Mobile"


class Spider(Spider):

    def init(self, extend=""):
        self._host = ""
        try:
            self._resolve_host()
        except Exception:
            self._host = MAIN
        return

    def getName(self):
        return SITE_NAME

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return (".m3u8" in u) or (".mp4" in u)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ---------------- 内部工具 ----------------
    def _headers(self, referer=None):
        h = {"User-Agent": UA}
        if referer:
            h["Referer"] = referer
        return h

    def _get(self, url, referer=None):
        try:
            r = self.fetch(url, headers=self._headers(referer))
            if r is None:
                return ""
            t = getattr(r, "text", None)
            if t is None:
                c = getattr(r, "content", None)
                t = c.decode("utf-8", "ignore") if c else ""
            return t or ""
        except Exception:
            return ""

    def host(self):
        if self._host:
            return self._host
        try:
            self._resolve_host()
        except Exception:
            self._host = MAIN
        return self._host or MAIN

    def _candidates(self):
        seen, out = set(), []
        for h in ([MAIN] + FALLBACK_HOSTS):
            h = (h or "").rstrip("/")
            if h and h not in seen:
                seen.add(h)
                out.append(h)
        return out

    def _resolve_host(self):
        # 跟随 301 + 校验分类列表页含卡片
        for base in self._candidates():
            url = base + PREFIX + "/index.php/vod/type/id/119.html"
            html = self._get(url)
            if html and ("group-item" in html or "vod/detail/id/" in html):
                self._host = base
                return
        self._host = MAIN

    def _base(self):
        return self.host() + PREFIX

    def _abs(self, u):
        if not u:
            return ""
        if u.startswith("http"):
            return u
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host() + u
        return self.host() + "/" + u

    # 解析卡片列表  <a href=".../vod/detail/id/{id}.html" class="group-item..."><img data-original="pic"><p>title</p>
    _CARD_RE = re.compile(
        r'<a[^>]+href=["\']([^"\']*?/vod/detail/id/(\d+)\.html)["\'][^>]*class=["\'][^"\']*group-item[^"\']*["\'][^>]*>'
        r'.*?data-original=["\']([^"\']*)["\'].*?<p[^>]*>(.*?)</p>',
        re.S
    )

    def _parse_list(self, html):
        vods = []
        for m in self._CARD_RE.finditer(html or ""):
            vid = m.group(2)
            pic = m.group(3).strip()
            title = re.sub(r"<[^>]+>", "", m.group(4)).strip()
            if not vid:
                continue
            vods.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._abs(pic),
                "vod_remarks": "",
            })
        return vods

    # ---------------- 首页/分类（静态硬编码，零网络）----------------
    def homeContent(self, filter):
        cats = [
            ("119", "斯卡资源"), ("244", "51资源"), ("386", "黄瓜资源"),
            ("358", "番茄资源"), ("286", "兔兔资源"), ("370", "森林资源"),
            ("329", "库库资源"), ("127", "制服诱惑"), ("390", "AI短剧"),
        ]
        classes = [{"type_id": c[0], "type_name": c[1]} for c in cats]
        return {"class": classes, "list": []}

    def homeVideoContent(self):
        # 首页推荐取第一个分类首页
        html = self._get(self._base() + "/index.php/vod/type/id/119.html")
        return {"list": self._parse_list(html)}

    # ---------------- 分类列表 ----------------
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        if page < 1:
            page = 1
        if page == 1:
            url = "%s/index.php/vod/type/id/%s.html" % (self._base(), tid)
        else:
            url = "%s/index.php/vod/type/id/%s/page/%d.html" % (self._base(), tid, page)
        html = self._get(url)
        vods = self._parse_list(html)

        pagecount = page
        m = re.search(r'/vod/type/id/%s/page/(\d+)\.html["\'][^>]*>\s*尾页' % re.escape(str(tid)), html)
        if not m:
            m = re.search(r'/page/(\d+)\.html["\'][^>]*class=["\'][^"\']*pagenum[^"\']*["\'][^>]*>\s*尾页', html)
        if m:
            try:
                pagecount = int(m.group(1))
            except Exception:
                pagecount = page + 1
        elif vods:
            pagecount = page + 1

        return {
            "list": vods,
            "page": page,
            "pagecount": pagecount,
            "limit": len(vods) if vods else 24,
            "total": pagecount * (len(vods) if vods else 24),
        }

    # ---------------- 详情 ----------------
    def _norm_ids(self, ids):
        if isinstance(ids, (list, tuple)):
            arr = list(ids)
        else:
            arr = [ids]
        out = []
        for x in arr:
            if x is None:
                continue
            s = str(x).strip()
            if not s:
                continue
            m = re.search(r'/vod/detail/id/(\d+)\.html', s)
            if m:
                s = m.group(1)
            out.append(s)
        return out

    def detailContent(self, ids):
        arr = self._norm_ids(ids)
        if not arr:
            return {"list": []}
        vid = arr[0]
        url = "%s/index.php/vod/detail/id/%s.html" % (self._base(), vid)
        html = self._get(url)

        title = ""
        m = re.search(r'<p class=["\']group-title["\']>(.*?)</p>', html, re.S)
        if m:
            title = re.sub(r"<[^>]+>", "", m.group(1)).strip()

        pic = ""
        m = re.search(r'class=["\']detail-img["\'][^>]*data-img=["\']([^"\']+)["\']', html, re.S)
        if not m:
            m = re.search(r'data-img=["\']([^"\']+)["\']', html)
        if m:
            pic = self._abs(m.group(1).strip())

        vclass = ""
        m = re.search(r'资源分类：\s*<span>(.*?)</span>', html, re.S)
        if m:
            vclass = re.sub(r"<[^>]+>", "", m.group(1)).strip()

        content = ""
        m = re.search(r'内容简介：\s*<span>(.*?)</span>', html, re.S)
        if m:
            content = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if not content:
            content = title

        # 播放线路：抓取 "资源线路" 区块内的 play 链接
        flags = []      # 线路名列表
        urls = []       # 对应线路的 "集名$播放页路径" 串
        for sec in re.finditer(
            r'<strong>(.*?)资源线路</strong>.*?<ul class=["\']dslist-group[^"\']*["\']>(.*?)</ul>',
            html, re.S
        ):
            fname = re.sub(r"<[^>]+>", "", sec.group(1)).strip() or "线路"
            body = sec.group(2)
            eps = []
            for i, a in enumerate(re.finditer(
                r'<a[^>]+href=["\']([^"\']*?/vod/play/id/[^"\']+\.html)["\'][^>]*>(.*?)</a>',
                body, re.S
            )):
                path = a.group(1)
                name = re.sub(r"<[^>]+>", "", a.group(2)).strip() or ("第%d集" % (i + 1))
                # play id 内禁裸 $，路径本身无 $，直接使用
                eps.append("%s$%s" % (name, path))
            if eps:
                flags.append(fname)
                urls.append("#".join(eps))

        # 兜底：详情页海报也带一个 play 链接
        if not urls:
            m = re.search(r'href=["\']([^"\']*?/vod/play/id/[^"\']+\.html)["\']', html)
            if m:
                flags.append("slm3u8")
                urls.append("在线播放$" + m.group(1))
        if not urls:
            flags.append("slm3u8")
            urls.append("在线播放$" + "/index.php/vod/play/id/%s/sid/1/nid/1.html" % vid)

        # $$$ 分组：flags 与 urls 组数严格相等
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": vclass,
            "vod_actor": "",
            "vod_director": "",
            "vod_content": content,
            "type_name": vclass,
            "vod_play_from": "$$$".join(flags),
            "vod_play_url": "$$$".join(urls),
        }
        return {"list": [vod]}

    # ---------------- 搜索（GET）----------------
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        try:
            from urllib.parse import quote
            kw = quote(key)
        except Exception:
            kw = key
        if page <= 1:
            url = "%s/index.php/vod/search/wd/%s.html" % (self._base(), kw)
        else:
            url = "%s/index.php/vod/search/wd/%s/page/%d.html" % (self._base(), kw, page)
        html = self._get(url)
        return {"list": self._parse_list(html), "page": page}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        # id 为详情里存的播放页路径（或已是直链）
        pid = id or ""
        if "$" in pid:
            pid = pid.split("$", 1)[-1]
        # 已是直链
        if pid.startswith("http") and (".m3u8" in pid.lower() or ".mp4" in pid.lower()):
            return {"parse": 0, "url": pid, "header": {"User-Agent": UA}}

        play_url = self._abs(pid) if pid else ""
        real = ""
        if play_url:
            html = self._get(play_url, referer=self._base() + "/")
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.S)
            if not m:
                m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', html, re.S)
            if m:
                raw = m.group(1)
                try:
                    data = json.loads(raw)
                    real = data.get("url", "") or ""
                except Exception:
                    mm = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                    if mm:
                        real = mm.group(1).encode("utf-8").decode("unicode_escape")
            if not real:
                mm = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
                if mm:
                    real = mm.group(1).encode("utf-8").decode("unicode_escape")

        real = (real or "").replace("\\/", "/")
        if not real:
            # 兜底：交给盒子嗅探播放页
            return {"parse": 1, "url": play_url,
                    "header": {"User-Agent": UA, "Referer": self._base() + "/"}}

        real = self._abs(real)
        # 该站 m3u8 为前贴片广告注入型（master→media 混插广告分片，正片分片跨 host），
        # 走 localProxy 去广告；取不到代理时 _proxy_url 回退直链（法则7/26）。
        # 只回 url 键（禁同时给 playUrl，避免盒子把两者拼接→网址重复拼接）；
        # _proxy_url 只算一次（getProxyUrl 每次可能返回不同代理地址）。
        proxied = self._proxy_url(real)
        return {"parse": 0, "url": proxied, "header": {"User-Agent": UA}}

    # ---------------- localProxy 去广告管线（视频 hash-token 锚点）----------------
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
        from urllib.parse import quote
        if base.endswith("?") or base.endswith("&"):
            sep = ""
        elif "?" in base:
            sep = "&"
        else:
            sep = "?"
        return base + sep + "url=" + quote(target, safe="") + "&type=m3u8"

    @staticmethod
    def _resolve_seg(uri, base_url):
        if not uri:
            return ""
        if uri.startswith("http"):
            return uri
        if uri.startswith("//"):
            return "https:" + uri
        try:
            from urllib.parse import urljoin
            return urljoin(base_url, uri)
        except Exception:
            return uri

    def _abs_tag_uri(self, line, base_url):
        """把 #EXT-X-KEY / #EXT-X-MAP 的 URI="..." 改成绝对地址（否则播放器按 127.0.0.1 解析 key→404）。"""
        m = re.search(r'URI="([^"]*)"', line)
        if not m or not m.group(1):
            return line
        absu = self._resolve_seg(m.group(1), base_url)
        return line[:m.start(1)] + absu + line[m.end(1):]

    @staticmethod
    def _video_token(base_url):
        """从 m3u8 URL 提取视频唯一 hash 段（如 /20231109/Y2wDCtNO/ 的 Y2wDCtNO）。
        正片分片路径都含此 token，广告分片为不同 date/hash 目录。"""
        m = re.search(r'/\d{6,}/([A-Za-z0-9_-]{4,})/', base_url)
        return m.group(1) if m else ""

    def _filter_m3u8(self, text, base_url, depth=0):
        if "#EXT-X-STREAM-INF" in text:
            return self._flatten_master(text, base_url, depth)
        return self._filter_media(text, base_url)

    def _flatten_master(self, text, base_url, depth=0):
        """master 拉平为单跳：取首个子流绝对地址，抓 media 清单去广告后回传（禁嵌套代理 URL）。"""
        if depth >= 2:
            return text if text.endswith("\n") else text + "\n"
        sub = ""
        for raw in text.split("\n"):
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            sub = self._resolve_seg(s, base_url)
            break
        if not sub:
            return text if text.endswith("\n") else text + "\n"
        media = self._get(sub)
        if not media or "#EXTM3U" not in media:
            return text if text.endswith("\n") else text + "\n"
        return self._filter_m3u8(media, sub, depth + 1)

    def _filter_media(self, text, base_url):
        """媒体清单去广告：以视频 hash-token 为锚点（正片分片跨 host，不能用目录前缀）。
        保留 URL 含 /{token}/ 的分片，剔除其它（广告）；分片绝对化、KEY/MAP URI 绝对化；
        开头孤立 DISCONTINUITY 抑制；token 缺失或全滤时回退原文（分片交播放器直连）。"""
        lines = text.split("\n")
        token = self._video_token(base_url)
        base_dir = base_url.rsplit("/", 1)[0]

        out, buf = [], []
        removed = kept = 0
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
                if s.startswith("#EXT-X-KEY") or s.startswith("#EXT-X-MAP"):
                    s = self._abs_tag_uri(s, base_url)
                out.append(s)
                continue
            seg_abs = self._resolve_seg(s, base_url)
            # 正片判定：优先 token，其次目录前缀兜底
            if token:
                is_main = ("/" + token + "/") in seg_abs
            else:
                is_main = seg_abs.startswith(base_dir)
            if is_main:
                for t in buf:
                    if (not kept_any) and t.startswith("#EXT-X-DISCONTINUITY"):
                        continue
                    out.append(t)
                out.append(seg_abs)
                kept += 1
                kept_any = True
            else:
                removed += 1
            buf = []

        if kept == 0 and removed > 0:
            try:
                self.log({"ad_filter": "fallback_no_filter", "removed": removed, "kept": kept})
            except Exception:
                pass
            return text if text.endswith("\n") else text + "\n"
        try:
            self.log({"ad_filter": "ok", "removed": removed, "kept": kept, "token": token})
        except Exception:
            pass
        return "\n".join(out) + "\n"

    def localProxy(self, param):
        """代理并清洗 m3u8：去广告、分片绝对化直连 CDN（法则26：不代理 ts 避 OOM）。"""
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
                    from urllib.parse import unquote
                    url = unquote(url)
                except Exception:
                    pass
            text = self._get(url)
            if not text or "#EXTM3U" not in text:
                return [404, "text/plain", b""]
            cleaned = self._filter_m3u8(text, url)
            if isinstance(cleaned, str):
                cleaned = cleaned.encode("utf-8")
            # FongMi chaquo 契约：localProxy 回三元组 [code, content_type, content_bytes]
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception:
            return [404, "text/plain", b""]
