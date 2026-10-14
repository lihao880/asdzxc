# coding=utf-8
# !/usr/bin/python
"""
FongMi / TVBox T3 (type=3) 爬虫源
站点：KISSAV   canonical 主域 kissavs.com  当前访问域 https://www.nxlvzlo.cc/ (CloudFront 前置)
类型：日本 AV 影片站（成人）—— 纯静态 HTML，可直接解析 DOM + 站内 m3u8 代理 (parse:0)
说明：
  - 列表卡片：div.video-img-box  > a[href="/video/{id}/"] + img.zximg[z-image-loader-url=封面][alt=标题]
             时长在 div.absolute-bottom-right > span.label
  - 封面真实 URL 在 z-image-loader-url 属性(非 src)，域 xi.dzuxta.cn 带 auth_key 签名，实测明文可直连
  - 分类入口：/av/new/(新作)  /av/tag/{标签}/update/(主题)  /hotmovies/alwayshot/(东京热)
             翻页 /av/new/page/{N}/ ；<link rel="next"> 提供下一页判定
  - 详情：/video/{id}/  (id 为 hash 或番号)，标题取 og:title / h1，简介 og:description，海报走 packed poster
  - 搜索：/search/{keyword}/  (GET)
  - 播放：详情页第 ~3046 行 Dean-Edwards packed script(eval(function(p,a,c,k,e,d)...))
          Python unpacker 解出 create_player 参数 'url' = /media/m3u8/?url=...&exp=...&token=...
          站内代理端点回标准 AES-128 m3u8(绝对 KEY/TS)，parse:0 直接播；外部 xv.dzuxta.cn 直连 403 必走代理
  - 加密图片密钥(兼容加密目录)：AES-128-CBC NoPadding key=f5d965df75336270 iv=97b60394abc2fbe1
          isPlainImageData 预检：前 16B 解出 JPEG/PNG/GIF/WEBP/ICO 档头则直接返回明文(实测封面均明文)
最后验证：2026-09-30
"""
import sys
import re
import base64
from urllib.parse import quote, unquote

sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        def init(self, extend=""):
            pass


class Spider(Spider):

    # ============ 站点信息（换站只改这里） ============
    siteName = "KISSAV"
    MAIN = "https://www.nxlvzlo.cc"
    FALLBACK_HOSTS = [
        "https://www.nxlvzlo.cc",
        "https://kissavs.com",
        "https://www.kissavs.com",
    ]

    UA = ("Mozilla/5.0 (Linux; Android 14; 22127RK46C/Pixel5) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    # 加密图片密钥（兼容加密目录，实测封面均明文）
    _IMG_KEY = b"f5d965df75336270"
    _IMG_IV = b"97b60394abc2fbe1"

    _host = ""

    # 首页分类（静态硬编码，零网络）
    _CATE = [
        {"type_name": "新作", "type_id": "/av/new"},
        {"type_name": "主题", "type_id": "themes"},
        {"type_name": "东京热", "type_id": "/hotmovies/alwayshot"},
        {"type_name": "中文字幕", "type_id": "/av/theme/chinese-subtitle"},
        {"type_name": "制服诱惑", "type_id": "/av/theme/uniform"},
        {"type_name": "直接开啪", "type_id": "/av/theme/sex-only"},
        {"type_name": "丝袜美腿", "type_id": "/av/theme/pantyhose"},
        {"type_name": "主奴调教", "type_id": "/av/theme/bdsm"},
        {"type_name": "多P群交", "type_id": "/av/theme/group-sex"},
        {"type_name": "男友视角", "type_id": "/av/theme/pov"},
        {"type_name": "凌辱强暴", "type_id": "/av/theme/rape"},
        {"type_name": "无码解放", "type_id": "/av/theme/uncensored"},
        {"type_name": "偷拍视角", "type_id": "/av/theme/hidden-cam"},
        {"type_name": "女同欢愉", "type_id": "/av/theme/lesbian"},
    ]

    # 「主题」分类的标签筛选（取自 /av/themes/ 全部 102 个标签，静态硬编码）
    # (显示名, 已URL编码的 slug)；请求 /av/tag/{slug}/update/ ，slug 直接用避免大小写/斜杠问题
    _TAGS = [
        ("黑丝", "%E9%BB%91%E4%B8%9D"), ("过膝袜", "%E8%BF%87%E8%86%9D%E8%A2%9C"), ("运动装", "%E8%BF%90%E5%8A%A8%E8%A3%85"),
        ("肉丝", "%E8%82%89%E4%B8%9D"), ("丝袜", "%E4%B8%9D%E8%A2%9C"), ("眼镜娘", "%E7%9C%BC%E9%95%9C%E5%A8%98"),
        ("兽耳", "%E5%85%BD%E8%80%B3"), ("渔网", "%E6%B8%94%E7%BD%91"), ("水着", "%E6%B0%B4%E7%9D%80"),
        ("校服", "%E6%A0%A1%E6%9C%8D"), ("旗袍", "%E6%97%97%E8%A2%8D"), ("婚纱", "%E5%A9%9A%E7%BA%B1"),
        ("女仆", "%E5%A5%B3%E4%BB%86"), ("和服", "%E5%92%8C%E6%9C%8D"), ("吊带袜", "%E5%90%8A%E5%B8%A6%E8%A2%9C"),
        ("兔女郎", "%E5%85%94%E5%A5%B3%E9%83%8E"), ("Cosplay", "cosplay"), ("黑肉", "%E9%BB%91%E8%82%89"),
        ("长身", "%E9%95%BF%E8%BA%AB"), ("软体", "%E8%BD%AF%E4%BD%93"), ("贫乳", "%E8%B4%AB%E4%B9%B3"),
        ("萝莉", "%E8%90%9D%E8%8E%89"), ("美腿", "%E7%BE%8E%E8%85%BF"), ("美尻", "%E7%BE%8E%E5%B0%BB"),
        ("纹身", "%E7%BA%B9%E8%BA%AB"), ("短发", "%E7%9F%AD%E5%8F%91"), ("白虎", "%E7%99%BD%E8%99%8E"),
        ("熟女", "%E7%86%9F%E5%A5%B3"), ("巨乳", "%E5%B7%A8%E4%B9%B3"), ("少女", "%E5%B0%91%E5%A5%B3"),
        ("颜射", "%E9%A2%9C%E5%B0%84"), ("脚交", "%E8%84%9A%E4%BA%A4"), ("肛交", "%E8%82%9B%E4%BA%A4"),
        ("痉挛", "%E7%97%89%E6%8C%9B"), ("潮吹", "%E6%BD%AE%E5%90%B9"), ("深喉", "%E6%B7%B1%E5%96%89"),
        ("接吻", "%E6%8E%A5%E5%90%BB"), ("口爆", "%E5%8F%A3%E7%88%86"), ("口交", "%E5%8F%A3%E4%BA%A4"),
        ("乳交", "%E4%B9%B3%E4%BA%A4"), ("中出", "%E4%B8%AD%E5%87%BA"), ("露出", "%E9%9C%B2%E5%87%BA"),
        ("轮奸", "%E8%BD%AE%E5%A5%B8"), ("调教", "%E8%B0%83%E6%95%99"), ("捆绑", "%E6%8D%86%E7%BB%91"),
        ("瞬间插入", "%E7%9E%AC%E9%97%B4%E6%8F%92%E5%85%A5"), ("痴汉", "%E7%97%B4%E6%B1%89"), ("痴女", "%E7%97%B4%E5%A5%B3"),
        ("男M", "%E7%94%B7m"), ("泥醉", "%E6%B3%A5%E9%86%89"), ("泡姬", "%E6%B3%A1%E5%A7%AC"),
        ("母乳", "%E6%AF%8D%E4%B9%B3"), ("放尿", "%E6%94%BE%E5%B0%BF"), ("按摩", "%E6%8C%89%E6%91%A9"),
        ("强奸", "%E5%BC%BA%E5%A5%B8"), ("多P", "%E5%A4%9Ap"), ("刑具", "%E5%88%91%E5%85%B7"),
        ("凌辱", "%E5%87%8C%E8%BE%B1"), ("一日十回", "%E4%B8%80%E6%97%A5%E5%8D%81%E5%9B%9E"), ("3P", "3p"),
        ("黑人", "%E9%BB%91%E4%BA%BA"), ("丑男", "%E4%B8%91%E7%94%B7"), ("诱惑", "%E8%AF%B1%E6%83%91"),
        ("童贞", "%E7%AB%A5%E8%B4%9E"), ("时间停止", "%E6%97%B6%E9%97%B4%E5%81%9C%E6%AD%A2"), ("复仇", "%E5%A4%8D%E4%BB%87"),
        ("年龄差", "%E5%B9%B4%E9%BE%84%E5%B7%AE"), ("巨汉", "%E5%B7%A8%E6%B1%89"), ("媚药", "%E5%AA%9A%E8%8D%AF"),
        ("夫目前犯", "%E5%A4%AB%E7%9B%AE%E5%89%8D%E7%8A%AF"), ("出轨", "%E5%87%BA%E8%BD%A8"), ("催眠", "%E5%82%AC%E7%9C%A0"),
        ("偷拍", "%E5%81%B7%E6%8B%8D"), ("不伦", "%E4%B8%8D%E4%BC%A6"), ("下雨天", "%E4%B8%8B%E9%9B%A8%E5%A4%A9"),
        ("NTR", "ntr"), ("错过末班车", "%E9%94%99%E8%BF%87%E6%9C%AB%E7%8F%AD%E8%BD%A6"), ("青梅竹马", "%E9%9D%92%E6%A2%85%E7%AB%B9%E9%A9%AC"),
        ("女性观众", "%E5%A5%B3%E6%80%A7%E8%A7%82%E4%BC%97"), ("店铺盗窃", "%E5%BA%97%E9%93%BA%E7%9B%97%E7%AA%83"), ("风俗娘", "%E9%A3%8E%E4%BF%97%E5%A8%98"),
        ("医生", "%E5%8C%BB%E7%94%9F"), ("逃犯", "%E9%80%83%E7%8A%AF"), ("护士", "%E6%8A%A4%E5%A3%AB"),
        ("老师", "%E8%80%81%E5%B8%88"), ("空姐", "%E7%A9%BA%E5%A7%90"), ("球队经理", "%E7%90%83%E9%98%9F%E7%BB%8F%E7%90%86"),
        ("未亡人", "%E6%9C%AA%E4%BA%A1%E4%BA%BA"), ("搜查官", "%E6%90%9C%E6%9F%A5%E5%AE%98"), ("情侣", "%E6%83%85%E4%BE%A3"),
        ("家政妇", "%E5%AE%B6%E6%94%BF%E5%A6%87"), ("家庭教师", "%E5%AE%B6%E5%BA%AD%E6%95%99%E5%B8%88"), ("偶像", "%E5%81%B6%E5%83%8F"),
        ("人妻", "%E4%BA%BA%E5%A6%BB"), ("主播", "%E4%B8%BB%E6%92%AD"), ("OL", "ol"),
        ("录像", "%E5%BD%95%E5%83%8F"), ("处女作/引退作", "%E5%A4%84%E5%A5%B3%E4%BD%9C%2F%E5%BC%95%E9%80%80%E4%BD%9C"), ("综艺", "%E7%BB%BC%E8%89%BA"),
        ("节日主题", "%E8%8A%82%E6%97%A5%E4%B8%BB%E9%A2%98"), ("感谢祭", "%E6%84%9F%E8%B0%A2%E7%A5%AD"), ("4小时以上", "4%E5%B0%8F%E6%97%B6%E4%BB%A5%E4%B8%8A"),
    ]

    def getName(self):
        return self.siteName

    def init(self, extend=""):
        self.extend = extend
        try:
            self._resolve_host()
        except Exception:
            self._host = self.MAIN
        return

    def isVideoFormat(self, url):
        pats = ['.m3u8', '.mp4', '.flv', '.mkv', '.ts', '/media/m3u8/']
        return any(p in (url or '') for p in pats)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ---------------- 域名解析 ----------------
    def host(self):
        return self._host or self.MAIN

    def _resolve_host(self):
        """按序探测可用域名：校验 /av/new/ 列表页含 video-img-box。"""
        cands = [self.MAIN] + [h for h in self.FALLBACK_HOSTS if h != self.MAIN]
        for h in cands:
            try:
                r = self.fetch(h + "/av/new/", headers=self._headers(h))
                if r and getattr(r, "status_code", 0) == 200 and "video-img-box" in (r.text or ""):
                    self._host = h
                    return
            except Exception:
                continue
        self._host = self.MAIN

    # ---------------- 公共请求 ----------------
    def _headers(self, host=None):
        h = host or self.host()
        return {
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": h + "/",
        }

    def _get_html(self, path):
        url = path if path.startswith("http") else (self.host() + path)
        try:
            r = self.fetch(url, headers=self._headers())
            if not r or getattr(r, "status_code", 0) != 200:
                return ""
            return r.text or ""
        except Exception:
            return ""

    def _img_proxy(self, url):
        """把封面真实 URL 包装成本地代理地址，交爬虫端代取(带 UA+Referer，明文直返/加密自动解密)；
        取不到 getProxyUrl 时回退直链。"""
        if not url:
            return url
        base = ""
        try:
            base = self.getProxyUrl() or ""
        except Exception:
            base = ""
        if not base:
            return url
        if base.endswith("?") or base.endswith("&"):
            sep = ""
        elif "?" in base:
            sep = "&"
        else:
            sep = "?"
        return base + sep + "url=" + quote(url, safe="") + "&type=img"

    # ---------------- 卡片解析 ----------------
    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<[^>]+>", "", s)
        s = s.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
        s = s.replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
        return s.strip()

    def _card_list(self, html):
        """解析 div.video-img-box 卡片；过滤广告(无 /video/ 内链的块)。"""
        out, seen = [], set()
        if not html:
            return out
        # 以 video-img-box 分块
        blocks = re.split(r'<div class="video-img-box[^"]*">', html)
        for blk in blocks[1:]:
            # 广告卡：带 data-ad_type / report-item / 无站内 /video/ 链接 → 跳过
            if "data-ad_type" in blk or "report-item" in blk:
                continue
            mid = re.search(r'href="/video/([^"/]+)/"', blk)
            if not mid:
                continue
            vid = mid.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            mpic = re.search(r'z-image-loader-url="([^"]+)"', blk)
            pic = mpic.group(1) if mpic else ""
            mtitle = re.search(r'alt="([^"]*)"', blk)
            title = self._clean(mtitle.group(1)) if mtitle else vid
            mlabel = re.search(r'<span class="label[^"]*">([^<]+)</span>', blk)
            remark = self._clean(mlabel.group(1)) if mlabel else ""
            out.append({
                "vod_id": "/video/%s/" % vid,   # 详情/播放统一用相对路径
                "vod_name": title or vid,
                "vod_pic": self._img_proxy(pic),
                "vod_remarks": remark,
            })
        return out

    def _pagecount(self, html, pg):
        """有 <link rel="next"> 则至少还有下一页。"""
        if html and re.search(r'<link\s+rel="next"', html):
            return pg + 1
        return pg

    # ---------------- 首页 ----------------
    def homeContent(self, filter):
        result = {"class": self._CATE}
        vals = [{"n": name, "v": slug} for (name, slug) in self._TAGS]
        result["filters"] = {
            "themes": [{"key": "tag", "name": "主题", "value": vals}]
        }
        return result

    def homeVideoContent(self):
        html = self._get_html("/av/new/")
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

    def _cat_base(self, tid, ext):
        tid = str(tid or "/av/new")
        if tid == "themes":
            # ext['tag'] 为已 URL 编码的 slug（来自 homeContent filters），直接拼接
            slug = ext.get("tag") or (self._TAGS[0][1] if self._TAGS else "")
            slug = str(slug).strip("/")
            # 兼容旧值/中文：若含未编码非 ASCII 则再 quote
            try:
                slug.encode("ascii")
            except Exception:
                slug = quote(slug)
            return "/av/tag/%s/update" % slug
        if tid.startswith("/"):
            return tid.rstrip("/")
        # 兜底：当作标签名
        return "/av/tag/%s/update" % quote(tid)

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        ext = self._parse_extend(extend)
        base = self._cat_base(tid, ext)
        if pg <= 1:
            path = base + "/"
        else:
            path = "%s/page/%d/" % (base, pg)
        html = self._get_html(path)
        vods = self._card_list(html)
        pc = self._pagecount(html, pg)
        return {
            "list": vods,
            "page": pg,
            "pagecount": pc,
            "limit": len(vods) or 24,
            "total": (len(vods) or 24) * pc,
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

    def _detail_path(self, vid):
        """vid 归一化为 /video/{id}/ 相对路径。"""
        vid = vid.strip()
        if vid.startswith("http"):
            m = re.search(r"/video/([^/?#]+)", vid)
            vid = "/video/%s/" % m.group(1) if m else vid
        elif not vid.startswith("/video/"):
            vid = "/video/%s/" % vid.strip("/")
        if not vid.endswith("/"):
            vid += "/"
        return vid

    def _skeleton(self, vid, name="", pic=""):
        return {
            "vod_id": vid,
            "vod_name": name or vid,
            "vod_pic": pic,
            "vod_content": "",
            "vod_play_from": self.siteName,
            "vod_play_url": "正片$%s" % vid,
        }

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        vid = self._detail_path(raw)
        html = self._get_html(vid)
        if not html:
            return {"list": [self._skeleton(vid)]}

        mtitle = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        name = self._clean(mtitle.group(1)) if mtitle else ""
        if not name:
            mh1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
            name = self._clean(mh1.group(1)) if mh1 else vid

        mdesc = re.search(r'<meta property="og:description" content="([^"]*)"', html)
        content = self._clean(mdesc.group(1)) if mdesc else ""

        # 海报：优先 packed poster，退回 og:image
        pic = ""
        params = self._unpack_player(html)
        if params:
            pic = params.get("poster") or ""
        if not pic:
            mimg = re.search(r'<meta property="og:image" content="([^"]*)"', html)
            pic = mimg.group(1) if mimg else ""

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_play_from": self.siteName,
            "vod_play_url": "正片$%s" % vid,   # 播放交 playerContent 懒解析
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
        path = "/search/%s/" % quote(str(key))
        if pg > 1:
            path = "/search/%s/page/%d/" % (quote(str(key)), pg)
        html = self._get_html(path)
        return {"list": self._card_list(html), "page": pg}

    # ---------------- Dean-Edwards packed 解包 ----------------
    def _b36(self, n):
        if n == 0:
            return "0"
        d = "0123456789abcdefghijklmnopqrstuvwxyz"
        s = ""
        while n > 0:
            s = d[n % 36] + s
            n //= 36
        return s

    def _enc(self, n, a):
        first = "" if n < a else self._enc(n // a, a)
        r = n % a
        ch = chr(r + 29) if r > 35 else self._b36(r)
        return first + ch

    def _unpack(self, p, a, c, k):
        d = {}
        for i in range(c):
            tok = self._enc(i, a)
            d[tok] = k[i] if (i < len(k) and k[i] != "") else tok
        return re.sub(r"\b\w+\b", lambda m: d.get(m.group(0), m.group(0)), p)

    def _unpack_player(self, html):
        """定位 create_player 的 packed 脚本并解出 {'url':..,'poster':..}。"""
        if not html:
            return {}
        for line in html.splitlines():
            if "eval(function(p,a,c,k,e,d)" not in line:
                continue
            m = re.search(r"\}\((.*)\)\)\s*$", line.strip(), re.S)
            if not m:
                continue
            args = m.group(1)
            mm = re.search(
                r"^'(?P<p>.*?)',\s*(?P<a>\d+),\s*(?P<c>\d+),\s*'(?P<k>.*?)'\.split\('\|'\)",
                args, re.S)
            if not mm:
                continue
            P = mm.group("p").replace("\\\\", "\\").replace("\\'", "'")
            A = int(mm.group("a"))
            C = int(mm.group("c"))
            K = mm.group("k").split("|")
            try:
                out = self._unpack(P, A, C, K)
            except Exception:
                continue
            if "create_player" not in out and "'url'" not in out:
                continue
            res = {}
            mu = re.search(r"'url'\s*:\s*'([^']*)'", out)
            if mu:
                res["url"] = mu.group(1)
            mp = re.search(r"'poster'\s*:\s*'([^']*)'", out)
            if mp:
                res["poster"] = mp.group(1)
            if res.get("url"):
                return res
        return {}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "")
        header = {"User-Agent": self.UA, "Referer": self.host() + "/"}

        # 直链直接返回
        if raw.startswith("http") and (".m3u8" in raw or "/media/m3u8/" in raw):
            return {"parse": 0, "url": raw, "header": header}

        vid = self._detail_path(raw)
        html = self._get_html(vid)
        params = self._unpack_player(html)
        url = (params or {}).get("url") or ""

        if url:
            if url.startswith("http"):
                play = url
            else:
                play = self.host() + (url if url.startswith("/") else "/" + url)
            return {"parse": 0, "url": play, "header": header}

        # 兜底：webm 预览
        mwebm = re.search(r'<source[^>]+src="([^"]+\.webm)"', html or "")
        if mwebm:
            return {"parse": 0, "url": mwebm.group(1), "header": header}

        return {"parse": 0, "url": "", "header": header}

    # ---------------- 图片解密代理（兼容加密目录，实测封面明文） ----------------
    def _is_plain_image(self, data):
        if not data or len(data) < 4:
            return False
        sigs = [b"\xff\xd8\xff", b"\x89PNG", b"GIF8", b"RIFF", b"\x00\x00\x01\x00"]
        head = data[:4]
        return any(head.startswith(s) or data[:3] == b"\xff\xd8\xff" for s in sigs)

    def localProxy(self, param):
        # 封面实测明文，vod_pic 直接用原始 URL；此处保留 AES 解密以兼容加密图目录
        try:
            url = (param or {}).get("url") or ""
            if not url:
                return None
            r = self.fetch(url, headers=self._headers())
            if not r or getattr(r, "status_code", 0) != 200:
                return None
            data = r.content
            # 预检：明文直接返回
            if self._is_plain_image(data):
                return [200, self._mime(data), data]
            # 尝试 AES-128-CBC NoPadding 解密
            try:
                from Crypto.Cipher import AES
                cipher = AES.new(self._IMG_KEY, AES.MODE_CBC, self._IMG_IV)
                n = len(data) - (len(data) % 16)
                dec = cipher.decrypt(data[:n])
                if self._is_plain_image(dec):
                    return [200, self._mime(dec), dec]
            except Exception:
                pass
            return [200, "image/jpeg", data]
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
