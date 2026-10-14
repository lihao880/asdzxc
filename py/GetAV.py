# coding=utf-8
# !/usr/bin/python
"""
FongMi / TVBox T3 (type=3) 爬虫源
站点：GetAV  https://getav.me/zh
类型：日本 AV 影片站（成人）—— 纯 JSON API + HLS(m3u8) 直链
说明：
  - 站点是 SPA，数据全走 JSON API（基底 https://getav.me/api），统一 locale=zh
  - Cloudflare 盾：请求须带  Referer: https://getav.me/ + Chrome UA 才通过（无需 cf cookie）
  - 列表:   /api/movies?locale=zh&page=&limit=&sortBy=latest|popular|rating
  - 分类:   /api/search?q=&category=<gid>&sortBy=&page=&limit=
  - 搜索:   /api/search?q=<kw>&page=&limit=
  - 详情:   /api/movies/<id>?locale=zh                     -> data{...}
  - 文件夹大全（一级 folder@@ + 二级下钻，均已实测）：
      类型 /api/genres  ->cat@@<id>  ->/api/genres/<id>
      演员 /api/stars   ->star@@<id> ->/api/stars/<id>
      片商 /api/studios ->studio@@<id>->/api/studios/<id>
      系列 /api/series  ->series@@<id>->/api/series/<id>
      番号 /api/codes   ->code@@<id> ->/api/codes/<id>
    以上实体端点返回 {..., movies[], pagination{totalPages}}；列表项 vod_tag=folder 供 TVBox 下钻。
  - 播放地址取自「详情 data.videoSources[]」：每档 {type: raw_1080p/720p/480p/240p,
    url: https://static.worldstatic.com/cdn/.../index.txt?t=<sig>&e=<expire>}
    该 url 为完整签名 HLS，m3u8 内 KEY(glyph.woff)/分片(seg-N.woff2) 均相对 /cdn/ 路径，
    对 static.worldstatic.com 解析；实测 m3u8=200 / key=200(16B) / seg=206(font/woff2) 可达。
  - 图片 CDN static.worldstatic.com：localImg 相对 /images/cover/xxx.jpg，只需 UA 即 200。
  - playerContent 用 movieId@type 回详情端点重取签名直链，避免签名过期；parse:0 直接交播放器。
最后验证：2026-09-24
"""
import sys
import json
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
    siteName = "GetAV"
    HOST = "https://getav.me"
    CDN = "https://static.worldstatic.com"

    UA = ("Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    LIMIT = 30

    def getName(self):
        return self.siteName

    def init(self, extend=""):
        self.extend = extend
        return

    def isVideoFormat(self, url):
        pats = ['.m3u8', '.mp4', '.flv', '.mkv', 'index.txt', '/cdn/']
        return any(p in (url or '') for p in pats)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ---------------- 公共请求 ----------------
    def _headers(self, referer=None, json_accept=True):
        h = {
            "User-Agent": self.UA,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": referer or (self.HOST + "/"),
        }
        if json_accept:
            h["Accept"] = "application/json, text/plain, */*"
        return h

    def _get_json(self, path):
        """GET HOST+path 并解析 JSON，失败返回 {}（法則：每次 fetch 后判空）。"""
        url = path if path.startswith("http") else (self.HOST + path)
        try:
            r = self.fetch(url, headers=self._headers())
            if not r or getattr(r, "status_code", 0) != 200:
                return {}
            txt = r.text or ""
            if not txt:
                return {}
            data = json.loads(txt)
            if isinstance(data, dict):
                return data
            return {}
        except Exception:
            return {}

    def _pic(self, item):
        """封面：localImg / img 相对路径补 CDN 域名（图片只需 UA 即可达）。"""
        p = item.get("localImg") or item.get("img") or item.get("posterUrl") or ""
        if not p:
            return ""
        if p.startswith("http"):
            return p
        if not p.startswith("/"):
            p = "/" + p
        return self.CDN + p

    def _remark(self, item):
        r = item.get("durationFormatted") or item.get("videoLength") or ""
        if r:
            r = str(r).split(".")[0]
        d = item.get("date") or ""
        if d:
            d = str(d)[:10]
        if r and d:
            return "%s | %s" % (r, d)
        return r or d or ""

    def _card(self, item):
        vid = item.get("id")
        if not vid:
            return None
        return {
            "vod_id": str(vid),
            "vod_name": item.get("title") or str(vid),
            "vod_pic": self._pic(item),
            "vod_remarks": self._remark(item),
        }

    def _cards(self, movies):
        out = []
        seen = set()
        for it in (movies or []):
            c = self._card(it)
            if not c or c["vod_id"] in seen:
                continue
            seen.add(c["vod_id"])
            out.append(c)
        return out

    # ---------------- 首页分类（静态，零网路）----------------
    #  设计：4 个「影片区块」(api@@*) + 5 个「文件夹大全」(folder@@*)。
    #  api@@*    直接回影片列表（latest/popular/rating 为 /api/movies 排序；4k=category=6）
    #  folder@@* 回「文件夹卡片」(vod_tag=folder)，点进去二级 tid=cat@@/star@@/studio@@/series@@/code@@
    #            再由 categoryContent 拉对应实体的影片。全部端点已实测可用。
    def homeContent(self, filter):
        cate = [
            {"type_name": "最近更新", "type_id": "api@@latest"},
            {"type_name": "热门影片", "type_id": "api@@popular"},
            {"type_name": "高分影片", "type_id": "api@@rating"},
            {"type_name": "4K 超清", "type_id": "api@@4k"},
            {"type_name": "类型大全", "type_id": "folder@@genres"},
            {"type_name": "演员大全", "type_id": "folder@@stars"},
            {"type_name": "片商大全", "type_id": "folder@@studios"},
            {"type_name": "系列大全", "type_id": "folder@@series"},
            {"type_name": "番号系列", "type_id": "folder@@codes"},
        ]
        # 三个影片区块（latest/popular/rating）本身即三种排序，无需再挂 sort 筛选。
        return {"class": cate}

    def homeVideoContent(self):
        # 首页推荐：最新影片列表
        d = self._get_json("/api/movies?locale=zh&page=1&limit=%d" % self.LIMIT)
        movies = (d.get("data") or {}).get("movies") or []
        return {"list": self._cards(movies)}

    # ---------------- 分类 ----------------
    def _parse_extend(self, extend):
        """兼容 dict / '{k=v,...}' / 'k=v&k2=v2' 三种 extend 格式，返回 dict。"""
        if isinstance(extend, dict):
            return extend
        if not extend:
            return {}
        s = str(extend).strip()
        if s.startswith("{"):
            try:
                return json.loads(s)
            except Exception:
                s = s.strip("{}")
        out = {}
        import re
        for pair in re.split(r'[&,;]', s):
            if "=" in pair:
                k, _, v = pair.partition("=")
                k = k.strip().strip('"').strip("'")
                v = v.strip().strip('"').strip("'")
                if k:
                    out[k] = v
        return out

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        tid = str(tid or "")
        ext = self._parse_extend(extend)  # 保留：兼容 TVBox 传入的 extend

        # ---- 一级：文件夹大全（返回 vod_tag=folder 卡片，点进去二级 tid）----
        if tid.startswith("folder@@"):
            return self._folder_list(tid.split("@@", 1)[1], pg)

        # ---- 影片区块：/api/movies 排序 + 4K(category=6) ----
        if tid.startswith("api@@"):
            key = tid.split("@@", 1)[1]
            if key == "4k":
                # 4K = genre id 6，走实体端点 /api/genres/6（search?category=6 仅回 74 部，实体端点约 6428 部）
                path = ("/api/genres/6?locale=zh&page=%d&limit=%d" % (pg, self.LIMIT))
            else:
                sb = key if key in ("latest", "popular", "rating") else "latest"
                path = ("/api/movies?locale=zh&page=%d&limit=%d&sortBy=%s"
                        % (pg, self.LIMIT, sb))
            return self._movie_page(path, pg)

        # ---- 二级：具体实体 -> 影片列表 ----
        if tid.startswith("cat@@"):
            gid = tid.split("@@", 1)[1]
            # 类型走实体端点 /api/genres/<id>（search?category 对多数 genre 返回空）
            return self._movie_page(
                "/api/genres/%s?locale=zh&page=%d&limit=%d" % (quote(gid), pg, self.LIMIT), pg)
        if tid.startswith("star@@"):
            sid = tid.split("@@", 1)[1]
            return self._movie_page(
                "/api/stars/%s?locale=zh&page=%d&limit=%d" % (quote(sid), pg, self.LIMIT), pg)
        if tid.startswith("studio@@"):
            sid = tid.split("@@", 1)[1]
            return self._movie_page(
                "/api/studios/%s?locale=zh&page=%d&limit=%d" % (quote(sid), pg, self.LIMIT), pg)
        if tid.startswith("series@@"):
            sid = tid.split("@@", 1)[1]
            return self._movie_page(
                "/api/series/%s?locale=zh&page=%d&limit=%d" % (quote(sid), pg, self.LIMIT), pg)
        if tid.startswith("code@@"):
            sid = tid.split("@@", 1)[1]
            return self._movie_page(
                "/api/codes/%s?locale=zh&page=%d&limit=%d" % (quote(sid), pg, self.LIMIT), pg)

        # ---- 向后兼容：纯 genre id ----
        return self._movie_page(
            "/api/genres/%s?locale=zh&page=%d&limit=%d" % (quote(tid), pg, self.LIMIT), pg)

    def _movie_page(self, path, pg):
        """通用「影片列表页」解析：兼容 /api/movies、/api/search、/api/<实体>/<id> 三类响应。
        影片数组取 data.movies；翻页数取 data.totalPages 或 data.pagination.totalPages。"""
        d = self._get_json(path)
        data = d.get("data") or {}
        movies = data.get("movies") or data.get("results") or []
        vods = self._cards(movies)
        pag = data.get("pagination") or {}
        try:
            pc = int(data.get("totalPages") or pag.get("totalPages") or 1)
        except Exception:
            pc = 1
        if pc < 1:
            pc = 1
        try:
            total = int(data.get("total") or pag.get("total") or (self.LIMIT * pc))
        except Exception:
            total = self.LIMIT * pc
        return {
            "list": vods,
            "page": pg,
            "pagecount": pc,
            "limit": self.LIMIT,
            "total": total,
        }

    # 文件夹大全配置： kind -> (api 路径模板, 数据键, 二级 tid 前缀)
    _FOLDER = {
        "genres":  ("/api/genres?locale=zh&page=%d&limit=%d&sortBy=popular",  "genres",  "cat"),
        "stars":   ("/api/stars?locale=zh&page=%d&limit=%d&sortBy=popular",   "stars",   "star"),
        "studios": ("/api/studios?locale=zh&page=%d&limit=%d&sortBy=popular", "studios", "studio"),
        "series":  ("/api/series?locale=zh&page=%d&limit=%d&sortBy=popular",  "series",  "series"),
        "codes":   ("/api/codes?locale=zh&page=%d&limit=%d&sortBy=popular",   "codes",   "code"),
    }

    def _folder_pic(self, item):
        """文件夹封面：演员用头像 localAvatar；片商/系列用 recentMovies 首图；其余留空。"""
        av = item.get("localAvatar") or item.get("avatar")
        if av:
            if av.startswith("http"):
                return av
            return self.CDN + (av if av.startswith("/") else "/" + av)
        rm = item.get("recentMovies") or []
        if rm:
            p = rm[0].get("localImg") or rm[0].get("img") or ""
            if p:
                if p.startswith("http"):
                    return p
                return self.CDN + (p if p.startswith("/") else "/" + p)
        return ""

    def _folder_list(self, kind, pg):
        cfg = self._FOLDER.get(kind)
        if not cfg:
            return {"list": [], "page": pg, "pagecount": 1, "limit": self.LIMIT, "total": 0}
        tmpl, key, prefix = cfg
        d = self._get_json(tmpl % (pg, self.LIMIT))
        data = d.get("data") or {}
        arr = data.get(key) or []
        vods = []
        seen = set()
        for it in arr:
            fid = it.get("id")
            if fid is None or str(fid) in seen:
                continue
            seen.add(str(fid))
            name = it.get("name") or it.get("originalName") or str(fid)
            mc = it.get("movieCount")
            vods.append({
                "vod_id": "%s@@%s" % (prefix, fid),
                "vod_name": name,
                "vod_pic": self._folder_pic(it),
                "vod_tag": "folder",          # 关键：告诉 TVBox 这是可下钻的文件夹
                "vod_remarks": ("%s 部" % mc) if mc else "",
            })
        pag = data.get("pagination") or {}
        try:
            pc = int(data.get("totalPages") or pag.get("totalPages") or 1)
        except Exception:
            pc = 1
        if pc < 1:
            pc = 1
        try:
            total = int(data.get("total") or pag.get("total") or (self.LIMIT * pc))
        except Exception:
            total = self.LIMIT * pc
        return {
            "list": vods,
            "page": pg,
            "pagecount": pc,
            "limit": self.LIMIT,
            "total": total,
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

    _QMAP = [
        ("raw_4k", "4K", 400),
        ("raw_2160p", "2160P", 390),
        ("raw_1440p", "1440P", 300),
        ("raw_1080p", "1080P", 280),
        ("raw_720p", "720P", 260),
        ("raw_540p", "540P", 240),
        ("raw_480p", "480P", 220),
        ("raw_360p", "360P", 200),
        ("raw_240p", "240P", 180),
    ]

    def _quality_label(self, t):
        t = (t or "").lower()
        for key, lab, _ in self._QMAP:
            if t == key:
                return lab
        # 兜底：从字符串抽数字
        import re
        m = re.search(r'(\d+)\s*[kp]?', t)
        if m:
            return m.group(1).upper() + ("K" if "k" in t else "P")
        return t.upper() or "播放"

    def _quality_rank(self, t):
        t = (t or "").lower()
        for key, _, rank in self._QMAP:
            if t == key:
                return rank
        return 100

    def _skeleton(self, vid, name="", pic=""):
        return {
            "vod_id": vid,
            "vod_name": name or vid,
            "vod_pic": pic,
            "vod_content": "",
            "vod_play_from": self.siteName,
            "vod_play_url": "播放$%s@auto" % vid,
        }

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}
        d = self._get_json("/api/movies/%s?locale=zh" % quote(vid))
        data = d.get("data") or {}
        if not data:
            return {"list": [self._skeleton(vid)]}

        name = data.get("title") or vid
        pic = self._pic(data)
        content = data.get("plot") or data.get("plotEn") or data.get("description") or ""
        remark = self._remark(data)
        rating = data.get("rating")
        if rating:
            remark = ("%s | ★%s" % (remark, rating)) if remark else ("★%s" % rating)

        actors = []
        for s in (data.get("stars") or []):
            n = s.get("name") or s.get("originalName")
            if n and n not in actors:
                actors.append(n)

        tags = []
        for g in (data.get("genres") or []):
            n = g.get("name") or g.get("originalName")
            if n and n not in tags:
                tags.append(n)

        director = ""
        prod = data.get("producer") or data.get("director")
        if isinstance(prod, dict):
            director = prod.get("name") or ""

        # ---- 播放线路：videoSources 多清晰度（movieId@type，回 player 重取签名链）----
        srcs = data.get("videoSources") or []
        eps = []
        seen_lab = set()
        for s in sorted(srcs, key=lambda x: self._quality_rank(x.get("type")), reverse=True):
            t = s.get("type") or ""
            if not s.get("url"):
                continue
            lab = self._quality_label(t)
            base = lab
            i = 2
            while lab in seen_lab:
                lab = "%s(%d)" % (base, i)
                i += 1
            seen_lab.add(lab)
            eps.append("%s$%s@%s" % (lab, vid, t))
        if not eps:
            eps = ["播放$%s@auto" % vid]
        play_url = "#".join(eps)

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": ", ".join(actors[:15]),
            "vod_director": director,
            "vod_tag": ", ".join(tags[:20]),
            "vod_remarks": remark,
            "vod_year": (str(data.get("date"))[:4] if data.get("date") else ""),
            "vod_play_from": self.siteName,
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        path = ("/api/search?q=%s&locale=zh&page=%d&limit=%d"
                % (quote(str(key)), pg, self.LIMIT))
        d = self._get_json(path)
        data = d.get("data") or {}
        movies = data.get("movies") or data.get("results") or []
        return {"list": self._cards(movies), "page": pg}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        # id 形如 "RKI-489@raw_1080p"（或 "@auto"）。回详情端点重取签名 HLS 直链。
        raw = str(id or "")
        mid, _, qtype = raw.partition("@")
        mid = mid or raw
        url = ""
        d = self._get_json("/api/movies/%s?locale=zh" % quote(mid))
        srcs = (d.get("data") or {}).get("videoSources") or []
        if srcs:
            if qtype and qtype != "auto":
                for s in srcs:
                    if (s.get("type") or "") == qtype and s.get("url"):
                        url = s.get("url")
                        break
            if not url:
                # 兜底：按 priority 取最高，其次按清晰度
                best = sorted(
                    srcs,
                    key=lambda x: (x.get("priority") or 0,
                                   self._quality_rank(x.get("type"))),
                    reverse=True)
                for s in best:
                    if s.get("url"):
                        url = s.get("url")
                        break
        header = {
            "User-Agent": self.UA,
            "Referer": self.HOST + "/",
        }
        if not url:
            # 极端兜底：预览片（避免完全无播放地址）
            prev = (d.get("data") or {}).get("previewVideoUrl") or ""
            if prev:
                url = prev if prev.startswith("http") else (self.CDN + (prev if prev.startswith("/") else "/" + prev))
        return {"parse": 0, "url": url or "", "header": header}

    def localProxy(self, param):
        return None
