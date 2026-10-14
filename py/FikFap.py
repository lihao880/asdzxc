# coding: utf-8
# ============================================================
# 站点名称: FikFap
# 前端域名: https://fikfap.com   （React SPA）
# API 域名: https://api.fikfap.com   （公开 REST API，路径不带前导斜线）
# 站点类型: 成人短视频平台（BunnyCDN 承载，m3u8 签名直链可 parse:0 直接播放）
# 内容类型: 视频（成人向短视频 / hashtag 频道 / 推荐流）
# ------------------------------------------------------------
# API 认证机制（关键，无需登入，只需 client 端自产 header）：
#   User-Agent / Origin=https://fikfap.com / Referer=https://fikfap.com/
#   X-Client-Type: browser
#   X-Client-App-Version / X-Client-App-Commit-Sha （固定值）
#   Authorization-Anonymous: <随机 uuid4>
#   X-Client-Logged-In: false
#   Accept: */*
# ------------------------------------------------------------
# 已实测确认的端点：
#   推荐流:   posts/recommender/control?amount=40          （&afterId= 分页，overlap=0）
#   贴文详情: posts/{postId}                               （含最新签名 videoStreamUrl）
#   搜索:     search?q={kw}                                （回 dict: posts/users/hashtags/...）
#   hashtag列表: hashtags/label/{label}/posts?amount=15    （&afterId= 分页）
#   全部hashtag: hashtags                                  （287 个）
# ------------------------------------------------------------
# Post 关键字段: postId(int) / label(标题) / videoStreamUrl(BunnyCDN 签名 m3u8，
#   有 expires 时效) / thumbnailStreamUrl(封面) / duration / likesCount /
#   viewsCount / author{username} / hashtags
# 播放: videoStreamUrl 有时效 -> playerContent 即时抓 posts/{postId} 拿最新直链，
#   BunnyCDN 仅需 UA，无需 Referer，直接 parse:0。
# 最后验证: 2026-09-29
# 来源: 用户提供 fikfap.com
# ============================================================
import json
import re
import uuid
import base64
from urllib.parse import quote

from base.spider import Spider as BaseSpider

# 依 countPosts 排序的 TOP hashtags（实测 hashtags 端点抓取）
_TOP_TAGS = [
    "ass", "bigboobs", "masturbation", "godpussy", "boobs", "legalteen",
    "blowjob", "blonde", "anal", "cutesexy", "brunette", "bodyperfection",
    "latina", "pussyjob", "petite", "milf", "tinytits", "sextoys", "feet",
    "asshole", "shorts", "alternative", "tattoo", "curvy", "couplesex",
    "ahegao", "thickass", "natural", "rearpussy", "cosplay", "doggystyle",
    "fingering", "analstretching", "lingerie", "cumshot", "asianhottie",
    "hotwife", "chubby", "skinny", "ebony", "college",
]

# 推荐引擎变体（前端实测存在）
_ENGINES = ["control", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "lowquality", "default"]


class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.host = "https://api.fikfap.com"
        self.web = "https://fikfap.com"
        self.ua = ("Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36")
        self.headers = {
            "User-Agent": self.ua,
            "Origin": self.web,
            "Referer": self.web + "/",
            "X-Client-Type": "browser",
            "X-Client-App-Version": "9647",
            "X-Client-App-Commit-Sha": "d71ce4b4a35f4312e7f181640887e239f93b0820",
            "Authorization-Anonymous": str(uuid.uuid4()),
            "X-Client-Logged-In": "false",
            "Accept": "*/*",
        }
        # 静态分类（法则16：零网络、硬编码）
        self.classes = [{"type_id": "rec:control", "type_name": "推薦"}]
        for t in _TOP_TAGS:
            self.classes.append({"type_id": "tag:" + t, "type_name": "#" + t})
        # 筛选：仅「推薦」分类可切换推荐引擎；其余分类给空数组（法则16 要求每个 type_id 都有对应）
        self.filters = {
            "rec:control": [{
                "key": "engine",
                "name": "推薦引擎",
                "value": [{"n": e, "v": e} for e in _ENGINES],
            }]
        }
        # afterId 游标缓存：{tid: {page: afterId}}，供序列翻页（TVBox 无限滚动会顺序 +1）
        self._cursors = {}

    # ---------------- 基础信息 ----------------
    def getName(self):
        return "FikFap"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        if not url:
            return False
        return bool(re.search(r"\.(m3u8|mp4|flv|ts|mkv|mov|m4v)(\?|$)", url, re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        """代理 BunnyCDN 资源，统一注入 Referer 破防盗链（图片/縮圖 + m3u8 + 分片都要）。"""
        param = param or {}
        t = param.get("type")
        u = param.get("url") or ""
        if isinstance(u, list):
            u = u[0] if u else ""
        try:
            real = self._d64(u) if u and not str(u).startswith("http") else u
        except Exception:
            real = u
        hdr = {"User-Agent": self.ua, "Referer": self.web + "/", "Origin": self.web}
        if not real:
            return [404, "text/plain", b""]
        if t == "img":
            try:
                r = self.fetch(real, headers=hdr, timeout=15)
                ct = "image/jpeg"
                try:
                    ct = (r.headers.get("Content-Type") or ct)
                except Exception:
                    pass
                return [200, ct, r.content]
            except Exception:
                return [404, "text/plain", b""]
        return [404, "text/plain", b""]

    # ---------------- 代理辅助 ----------------
    @staticmethod
    def _e64(s):
        return base64.b64encode(str(s).encode("utf-8")).decode("ascii")

    @staticmethod
    def _d64(s):
        return base64.b64decode(str(s).encode("ascii")).decode("utf-8")

    def _proxy(self, url, typ):
        """把真实 URL 包成本地代理 URL（由 localProxy 带 Referer 取回）。
        目前仅封面/縮圖走代理（BunnyCDN 图片防盗链）；m3u8/分片一律直连。"""
        base = "%s&url=%s&type=%s" % (self.getProxyUrl(), self._e64(url), typ)
        try:
            path = str(url).split("?", 1)[0]
            mext = re.search(r"(\.[A-Za-z0-9]{1,5})$", path)
            if mext:
                base += "&ext=" + mext.group(1)
        except Exception:
            pass
        return base

    def _proxy_img(self, url):
        """封面/縮圖走代理（BunnyCDN 圖片同樣有 Referer 防盜鏈，盒子圖片載入器不帶 Referer 會 403）。"""
        if not url or not str(url).startswith("http"):
            return url or ""
        return self._proxy(url, "img")

    # ---------------- 网络 ----------------
    def _api(self, path, timeout=15):
        """GET api.fikfap.com/{path}，回解析后的 JSON（dict/list），失败回 None。"""
        url = path if path.startswith("http") else self.host + "/" + path.lstrip("/")
        try:
            r = self.fetch(url, headers=self.headers, timeout=timeout)
            if r and getattr(r, "status_code", 0) == 200 and r.text:
                return json.loads(r.text)
        except Exception as e:
            self.log({"api_fail": url, "err": str(e)})
        return None

    # ---------------- Post -> Vod ----------------
    @staticmethod
    def _fmt_dur(sec):
        try:
            s = int(float(sec))
        except Exception:
            return ""
        if s <= 0:
            return ""
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h:
            return "%d:%02d:%02d" % (h, m, s)
        return "%d:%02d" % (m, s)

    def _post_to_vod(self, p):
        if not isinstance(p, dict):
            return None
        pid = p.get("postId") or p.get("id")
        if pid is None:
            return None
        pid = str(pid)
        name = (p.get("label") or p.get("title") or "").strip() or ("#" + pid)
        pic = p.get("thumbnailStreamUrl") or p.get("thumbnail") or ""
        pic = self._proxy_img(pic)
        # 备注：时长 · 点赞
        bits = []
        d = self._fmt_dur(p.get("duration"))
        if d:
            bits.append(d)
        likes = p.get("likesCount")
        if likes:
            bits.append("♥%s" % likes)
        author = p.get("author")
        if isinstance(author, dict) and author.get("username"):
            bits.append("@" + str(author.get("username")))
        return {
            "vod_id": pid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": " · ".join(bits),
        }

    @staticmethod
    def _extract_posts(data):
        """从各端点回应中抽出 post 列表。"""
        if data is None:
            return []
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            for k in ("posts", "data", "items", "results"):
                v = data.get(k)
                if isinstance(v, list):
                    return [x for x in v if isinstance(x, dict)]
        return []

    def _to_list(self, posts):
        out = []
        for p in posts:
            v = self._post_to_vod(p)
            if v:
                out.append(v)
        return out

    # ---------------- 首页 ----------------
    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        data = self._api("posts/recommender/control?amount=40")
        return {"list": self._to_list(self._extract_posts(data))}

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

    def _after_id(self, tid, page):
        """取该 tid 第 page 页所需 afterId（page<=1 回 None）。"""
        if page <= 1:
            return None
        return self._cursors.get(tid, {}).get(page)

    def _store_cursor(self, tid, page, posts):
        """记录下一页游标：第 page 页最后一个 postId -> 供第 page+1 页当 afterId。"""
        if not posts:
            return
        last = posts[-1].get("postId") or posts[-1].get("id")
        if last is None:
            return
        self._cursors.setdefault(tid, {})[page + 1] = str(last)

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg or 1)
        tid = (tid or "rec:control").strip()
        ext = self._parse_extend(extend)
        amount = 30
        after = self._after_id(tid, page)

        if tid.startswith("tag:"):
            label = tid[4:]
            path = "hashtags/label/%s/posts?amount=%d" % (quote(label), amount)
            if after:
                path += "&afterId=" + str(after)
            data = self._api(path)
        else:
            # 推荐引擎流；extend.engine 可覆盖 tid 携带的引擎
            engine = ext.get("engine") or (tid[4:] if tid.startswith("rec:") else "control")
            engine = engine or "control"
            path = "posts/recommender/%s?amount=%d" % (quote(engine), amount)
            if after:
                path += "&afterId=" + str(after)
            data = self._api(path)

        posts = self._extract_posts(data)
        self._store_cursor(tid, page, posts)
        lst = self._to_list(posts)
        # 游标翻页无总数：只要本页有卡，就假定还有下一页
        pagecount = page + 1 if lst else page
        return {
            "list": lst,
            "page": page,
            "pagecount": pagecount,
            "limit": amount,
            "total": pagecount * amount,
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
        pid = raw.split("$", 1)[0].strip() if "$" in raw else raw
        pid = pid.strip("/").split("/")[-1]  # 容错

        data = self._api("posts/" + quote(pid))
        p = data if isinstance(data, dict) else None
        if isinstance(p, dict) and "posts" in p and isinstance(p["posts"], list) and p["posts"]:
            p = p["posts"][0]

        # 提取失败 -> 骨架兜底（法则35：不回空 list）
        if not isinstance(p, dict) or (p.get("postId") is None and p.get("id") is None):
            return {"list": [{
                "vod_id": raw,
                "vod_name": "#" + pid,
                "vod_pic": "",
                "vod_remarks": "",
                "vod_content": "",
                "vod_play_from": "FikFap",
                "vod_play_url": "播放$" + pid,
            }]}

        name = (p.get("label") or p.get("title") or "").strip() or ("#" + pid)
        pic = self._proxy_img(p.get("thumbnailStreamUrl") or "")
        # 简介：hashtags + 统计
        tags = p.get("hashtags") or []
        tag_names = []
        for t in tags:
            if isinstance(t, dict):
                nm = t.get("label") or t.get("name")
                if nm:
                    tag_names.append("#" + str(nm))
            elif isinstance(t, str):
                tag_names.append("#" + t)
        content_bits = []
        if p.get("viewsCount"):
            content_bits.append("观看 %s" % p.get("viewsCount"))
        if p.get("likesCount"):
            content_bits.append("点赞 %s" % p.get("likesCount"))
        if tag_names:
            content_bits.append(" ".join(tag_names))
        content = "  ".join(content_bits)

        bits = []
        d = self._fmt_dur(p.get("duration"))
        if d:
            bits.append(d)
        author = p.get("author")
        if isinstance(author, dict) and author.get("username"):
            bits.append("@" + str(author.get("username")))

        vod = {
            "vod_id": pid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": " · ".join(bits),
            "vod_content": content,
            "vod_play_from": "FikFap",
            "vod_play_url": "播放$" + pid,
        }
        return {"list": [vod]}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg or 1)
        if page > 1:
            return {"list": [], "page": page}
        data = self._api("search?q=" + quote(key))
        posts = []
        if isinstance(data, dict):
            posts = [x for x in (data.get("posts") or []) if isinstance(x, dict)]
        elif isinstance(data, list):
            posts = [x for x in data if isinstance(x, dict)]
        # 去重
        seen, uniq = set(), []
        for p in posts:
            pid = p.get("postId") or p.get("id")
            if pid is None or pid in seen:
                continue
            seen.add(pid)
            uniq.append(p)
        return {"list": self._to_list(uniq), "page": page}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "")
        if "$" in raw:
            raw = raw.split("$", 1)[1]
        raw = raw.strip()
        # BunnyCDN 有 Referer 防盗链：直链必须带 UA + Referer=fikfap.com（实测缺 Referer 回 403）
        play_hdr = {"User-Agent": self.ua, "Referer": self.web + "/", "Origin": self.web}
        if not raw:
            return {"parse": 1, "url": "", "header": play_hdr}

        # 已是直链：直连 CDN，靠 header 的 Referer 过防盗链。
        # 不代理 m3u8——本站为 fMP4（.m4s + EXT-X-MAP），代理会让 FongMi M3u8Helper
        # 看不到分片 .m4s 副檔名（代理 path 是 /proxy），触发『无扩展名切片探测』失败；
        # 直连时分片 path 以 .m4s 结尾可被正确识别，ExoPlayer 的 header map 也会
        # 把 Referer 套到全部 HLS 请求（master/变体/分片）。
        if raw.startswith("http") and re.search(r"\.(m3u8|mp4|ts|flv)(\?|$)", raw, re.I):
            return {"parse": 0, "url": raw, "header": play_hdr}

        pid = raw.strip("/").split("/")[-1]
        # 即时抓最新签名 URL（videoStreamUrl 有 expires 时效）
        data = self._api("posts/" + quote(pid))
        p = data if isinstance(data, dict) else None
        if isinstance(p, dict) and "posts" in p and isinstance(p["posts"], list) and p["posts"]:
            p = p["posts"][0]
        url = ""
        if isinstance(p, dict):
            url = (p.get("videoStreamUrl") or p.get("videoUrl") or "").strip()

        if url:
            return {"parse": 0, "url": url, "header": play_hdr}
        # 兜底：交盒子处理
        return {"parse": 1, "url": self.web, "header": play_hdr}

    # ---------------- 推荐 ----------------
    def recommendContent(self, ids, pg):
        data = self._api("posts/recommender/control?amount=20")
        return {"list": self._to_list(self._extract_posts(data))}
