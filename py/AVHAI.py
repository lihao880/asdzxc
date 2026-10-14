# coding=utf-8
# !/usr/bin/python
"""
FongMi / TVBox T3 (type=3) 爬虫源
站点：AVHAI (avsea)  当前域 https://du234.sbs/
类型：日本 AV 影片站（成人）—— Nuxt SSR + 纯 JSON API + HLS(m3u8) 直链
说明：
  - 前端为 Nuxt(SPA/SSR)，数据全走 JSON API，基底 apiBase="/api"
  - 站点错误返回 {"code":404/500,...}，正常返回 {"code":200,"data":{...}}
  - 列表:   /api/movies?page_no=<N>&page_size=20  （翻页键为 page_no，不是 page）
              过滤: is_recommend=1 / is_home=1 / is_uncensored=1 / subtitle_type=2 / tag_code=<code> / keyword=<kw>
  - 详情:   /api/movies/<title_code>            title_code 大小写不敏感，如 CJOD-591
              detail.data.videos = [{type:"UrlHls", value:"https://...index.m3u8", label:"中文字幕"}]
  - 标签:   /api/tags                           -> data.list[{name_code,name_zh,name}]  (约20个热门)
  - m3u8：  实测直链 200，Access-Control-Allow-Origin:*，无加密无签名，仅需 UA，parse:0 直接可播
  - 图片 CDN：img.avseacdn.com（cover 字段为完整 URL），直连即可
  - 多备用域名：du234.sbs 若失效自动切换 FALLBACK_HOSTS（init 时 _resolve_host 校验 /api/app/config）
最后验证：2026-09-30
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
    siteName = "AVHAI"
    MAIN = "https://du234.sbs"
    # 主域失效时按序探测（取自站内内嵌域名池，成人站常换域）
    FALLBACK_HOSTS = [
        "https://du234.sbs",
        "https://avdong.sbs", "https://avdong.online", "https://avdong.site",
        "https://avdong.store", "https://avdong.xyz", "https://avdong.live",
        "https://avdong.click", "https://avdong.club", "https://avdong.space",
        "https://avdahai.com", "https://avdahai.online", "https://avdahai.site",
        "https://avdahai.store", "https://avdahai.xyz", "https://avck8.site",
    ]

    UA = ("Mozilla/5.0 (Linux; Android 14; 22127RK46C/Pixel5) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    LIMIT = 20
    _host = ""  # 解析后缓存

    # 首页分类（静态硬编码，零网络；换站只改 type_id 过滤串）
    _CATE = [
        {"type_name": "最近更新", "type_id": "recent"},
        {"type_name": "推荐", "type_id": "is_recommend=1"},
        {"type_name": "精选", "type_id": "is_home=1"},
        {"type_name": "无码", "type_id": "is_uncensored=1"},
        {"type_name": "中文字幕", "type_id": "subtitle_type=2"},
        {"type_name": "类别", "type_id": "genre"},
    ]

    # 「类别」分类的 tag_code 筛选项（取自 /api/tags 常见热门标签，静态硬编码）
    _GENRES = [
        ("jeans", "牛仔裤"), ("yoga-pants", "瑜伽裤"), ("female-boss", "女上司"),
        ("xxx-av", "XXX-AV"), ("gachig", "GACHIG"), ("pacopacomama", "PACOPACOMAMA"),
        ("10musume", "10MUSUME"), ("caribbeancom", "加勒比"), ("tokyo-hot", "东京热"),
        ("heyzo", "HEYZO"), ("1pondo", "一本道"), ("bread-pussy", "馒头逼"),
        ("hentai", "H动画"), ("orgasm", "绝顶高潮"), ("mommy-s-friend", "妈妈的朋友"),
        ("uncensored-crack", "无码破解"), ("vr", "VR"), ("train", "调教"),
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
        pats = ['.m3u8', '.mp4', '.flv', '.mkv', '.ts']
        return any(p in (url or '') for p in pats)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ---------------- 域名解析 ----------------
    def host(self):
        return self._host or self.MAIN

    def _resolve_host(self):
        """按序探测可用域名：校验 /api/app/config 返回 code==200。"""
        cands = [self.MAIN] + [h for h in self.FALLBACK_HOSTS if h != self.MAIN]
        for h in cands:
            try:
                r = self.fetch(h + "/api/app/config", headers=self._headers(h))
                if r and getattr(r, "status_code", 0) == 200:
                    txt = r.text or ""
                    if '"code":200' in txt or '"data"' in txt:
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
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": h + "/",
        }

    def _get_json(self, path):
        """GET host+path 并解析 JSON，失败返回 {}。"""
        url = path if path.startswith("http") else (self.host() + path)
        try:
            r = self.fetch(url, headers=self._headers())
            if not r or getattr(r, "status_code", 0) != 200:
                return {}
            txt = r.text or ""
            if not txt:
                return {}
            data = json.loads(txt)
            if isinstance(data, dict) and data.get("code") == 200:
                return data
            if isinstance(data, dict) and "data" in data:
                return data
            return {}
        except Exception:
            return {}

    # ---------------- 卡片映射 ----------------
    def _title(self, item):
        return (item.get("title_zh") or item.get("title")
                or item.get("title_code") or "")

    def _pic(self, item):
        p = item.get("cover") or ""
        if not p:
            return ""
        if p.startswith("http"):
            return p
        return self.host() + (p if p.startswith("/") else "/" + p)

    def _remark(self, item):
        parts = []
        if item.get("is_hd"):
            parts.append("HD")
        if item.get("is_uncensored"):
            parts.append("无码")
        if item.get("subtitle_type") == 2:
            parts.append("中字")
        code = item.get("title_code")
        if code:
            parts.insert(0, str(code))
        return " ".join(parts)

    def _card(self, item):
        code = item.get("title_code")
        if not code:
            return None
        return {
            "vod_id": str(code),          # 详情用 title_code
            "vod_name": self._title(item),
            "vod_pic": self._pic(item),
            "vod_remarks": self._remark(item),
        }

    def _cards(self, movies):
        out, seen = [], set()
        for it in (movies or []):
            c = self._card(it)
            if not c or c["vod_id"] in seen:
                continue
            seen.add(c["vod_id"])
            out.append(c)
        return out

    def _list_result(self, data, pg):
        movies = data.get("list") or []
        vods = self._cards(movies)
        try:
            total = int(data.get("total") or 0)
        except Exception:
            total = 0
        try:
            psize = int(data.get("page_size") or self.LIMIT) or self.LIMIT
        except Exception:
            psize = self.LIMIT
        pc = (total + psize - 1) // psize if total > 0 else (pg + 1 if vods else pg)
        if pc < 1:
            pc = 1
        return {
            "list": vods,
            "page": pg,
            "pagecount": pc,
            "limit": psize,
            "total": total if total > 0 else len(vods) * pc,
        }

    # ---------------- 首页 ----------------
    def homeContent(self, filter):
        # 零网络：分类静态；「类别」挂 tag_code 筛选
        result = {"class": self._CATE}
        vals = [{"n": name, "v": code} for code, name in self._GENRES]
        result["filters"] = {
            "genre": [{"key": "tag_code", "name": "类别", "value": vals}]
        }
        return result

    def homeVideoContent(self):
        d = self._get_json("/api/movies?page_no=1&page_size=%d" % self.LIMIT)
        data = d.get("data") or {}
        return {"list": self._cards(data.get("list") or [])}

    # ---------------- 分类 ----------------
    def _parse_extend(self, extend):
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
        tid = str(tid or "recent")
        ext = self._parse_extend(extend)

        params = ["page_no=%d" % pg, "page_size=%d" % self.LIMIT]

        if tid == "recent":
            pass
        elif tid == "genre":
            tc = ext.get("tag_code") or ""
            if tc:
                params.append("tag_code=%s" % quote(str(tc)))
        elif "=" in tid:
            k, _, v = tid.partition("=")
            params.append("%s=%s" % (k.strip(), quote(str(v).strip())))

        # extend 里若还带其它筛选键（tag_code 之外的），一并透传
        for k, v in ext.items():
            if k == "tag_code" and tid == "genre":
                continue
            if v not in (None, "", "全部"):
                params.append("%s=%s" % (k, quote(str(v))))

        d = self._get_json("/api/movies?" + "&".join(params))
        data = d.get("data") or {}
        return self._list_result(data, pg)

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

    def _skeleton(self, vid, name="", pic=""):
        return {
            "vod_id": vid,
            "vod_name": name or vid,
            "vod_pic": pic,
            "vod_content": "",
            "vod_play_from": self.siteName,
            "vod_play_url": "正片$%s" % vid,   # 兜底：回详情端点重取
        }

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}
        d = self._get_json("/api/movies/%s" % quote(vid))
        data = d.get("data") or {}
        if not data:
            return {"list": [self._skeleton(vid)]}

        name = self._title(data) or vid
        pic = self._pic(data)
        content = (data.get("desc_zh") or data.get("desc")
                   or data.get("desc_jp") or "")

        tags = []
        for t in (data.get("tags") or []):
            n = t.get("name_zh") or t.get("name")
            if n and n not in tags:
                tags.append(n)
        actors = []
        for a in (data.get("actresses") or []):
            n = a.get("name_zh") or a.get("name")
            if n and n not in actors:
                actors.append(n)

        remark = self._remark(data)

        # ---- 播放线路：videos 数组，每条一个线路，m3u8 直链内联（parse:0）----
        videos = data.get("videos") or []
        froms, urls = [], []
        seen_lab = set()
        for i, v in enumerate(videos):
            url = v.get("value") or v.get("url") or ""
            if not url or "$" in url:   # 直链含 $ 则跳过内联（法則21），交兜底
                continue
            lab = v.get("label") or ("线路%d" % (i + 1))
            base = lab
            k = 2
            while lab in seen_lab:
                lab = "%s%d" % (base, k)
                k += 1
            seen_lab.add(lab)
            froms.append(lab)
            # 单集：剧集名$直链
            epname = "正片"
            urls.append("%s$%s" % (epname, url))

        if froms and urls and len(froms) == len(urls):
            play_from = "$$$".join(froms)
            play_url = "$$$".join(urls)
        else:
            # 兜底骨架：回 title_code，playerContent 重取
            play_from = self.siteName
            play_url = "正片$%s" % vid

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": ", ".join(actors[:15]),
            "vod_director": "",
            "vod_tag": ", ".join(tags[:20]),
            "vod_remarks": remark,
            "vod_play_from": play_from,
            "vod_play_url": play_url,
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
        d = self._get_json(
            "/api/movies?keyword=%s&page_no=%d&page_size=%d"
            % (quote(str(key)), pg, self.LIMIT))
        data = d.get("data") or {}
        return {"list": self._cards(data.get("list") or []), "page": pg}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "")
        header = {"User-Agent": self.UA, "Referer": self.host() + "/"}

        # 情况一：详情已内联 m3u8 直链
        if raw.startswith("http"):
            return {"parse": 0, "url": raw, "header": header}

        # 情况二：兜底—id 为 title_code，回详情端点重取首个 m3u8
        d = self._get_json("/api/movies/%s" % quote(raw))
        videos = (d.get("data") or {}).get("videos") or []
        url = ""
        for v in videos:
            u = v.get("value") or v.get("url") or ""
            if u:
                url = u
                break
        return {"parse": 0, "url": url or "", "header": header}

    def localProxy(self, param):
        return None
