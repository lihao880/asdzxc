# coding: utf-8
# ============================================================
# 站点: VJAV (vjav1.sbs)
# 域名: https://vjav1.sbs
# 入口: https://vjav1.sbs/enter (需 Cookie: x-index-auth=authed)
# 类型: 视频站 (kvs 架构 SPA, JSON API + mp4 直链)
# 架构: Vue SPA, 数据全部走 /api/json/ 与 /api/*.php
# 列表: /api/json/videos2/14400/str/latest-updates/25/{section}.{oid}.{page}.{type}...json
# 搜索: /api/videos2.php?params=86400/str/relevance/60/search..{kw}.all..&
# 播放: /api/videofile.php?video_id={id}&lifetime=8640000 -> base64(西里尔同形混淆)
# 详情页: /videos/{id}/{dir}/
# 关键: 全站需 Cookie x-index-auth=authed, 否则 500 挑战页
# 最后验证: 2026-09-20
# 来源: 用户提供 URL 全自动开发
# ============================================================
import json
import base64
import re
from urllib.parse import quote, urljoin

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://vjav1.sbs"
        self.cookie = "x-index-auth=authed"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Cookie": self.cookie,
        }
        # 静态分类 (kvs dir 已知, 零网络)
        self.classes = [
            {"type_id": "latest-updates.top-country.hk", "type_name": "最新"},
            {"type_id": "top-rated.top-country.hk", "type_name": "最佳"},
            {"type_id": "most-popular.top-country.hk", "type_name": "热门"},
            {"type_id": "latest-updates.categories.asian", "type_name": "亚洲"},
            {"type_id": "latest-updates.categories.japanese", "type_name": "日本"},
            {"type_id": "latest-updates.categories.hd", "type_name": "HD"},
            {"type_id": "latest-updates.categories.jav-censored", "type_name": "有码"},
            {"type_id": "latest-updates.categories.jav-uncensored", "type_name": "无码"},
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}
        # 西里尔同形字母 -> 拉丁
        self._cyr = {
            "\u041c": "M", "\u0410": "A", "\u0415": "E",
            "\u0412": "B", "\u0421": "C",
            "\u041e": "O", "\u0420": "P", "\u0422": "T",
            "\u0425": "X", "\u041d": "H", "\u041a": "K",
        }

    # ---------- 基础 ----------
    def getName(self):
        return "VJAV"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 零网络
        pass

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return bool(url and re.search(r"\.(m3u8|mp4|flv|m4s)(/|$|\?)", url, re.I))

    def manualVideoCheck(self):
        return False

    # ---------- 首页 (零网络) ----------
    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        data = self._api_list("latest-updates", "top-country", "hk", 1)
        return {"list": self._parse_videos(data)}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        # tid 形如 "latest-updates.categories.asian" 或 "latest-updates.top-country.hk"
        parts = str(tid).split(".")
        sort = parts[0] if parts else "latest-updates"
        if len(parts) >= 3:
            section = parts[1]
            oid = parts[2]
        elif len(parts) == 2:
            section, oid = parts[0], parts[1]
        else:
            section, oid = "top-country", "hk"
        data = self._api_list(sort, section, oid, page)
        items = self._parse_videos(data)
        pages = self._safe_int(data.get("pages"), 1)
        return {
            "list": items,
            "page": int(page),
            "pagecount": pages,
            "limit": 25,
            "total": self._safe_int(data.get("total_count"), pages * 25),
        }

    def _api_list(self, sort, section, oid, page):
        url = "%s/api/json/videos2/14400/str/%s/25/%s.%s.%s.all...json" % (
            self.host, sort, section, oid, page
        )
        # WAF 为概率性拦截, 失败重试一次
        for _ in range(2):
            try:
                r = self.fetch(url, headers=self.headers, timeout=15)
                if r and r.status_code == 200:
                    txt = r.text or ""
                    if txt.strip().startswith("{"):
                        return json.loads(txt)
            except Exception:
                pass
        return {}
    def _parse_videos(self, data):
        result = []
        for v in (data.get("videos") or []):
            vid = str(v.get("video_id") or "")
            if not vid:
                continue
            title = v.get("title") or v.get("title_jp") or ("视频 " + vid)
            pic = v.get("scr") or ""
            remark = v.get("duration") or ""
            result.append({
                "vod_id": vid + "|$|" + title + "|$|" + pic + "|$|" + str(v.get("dir") or ""),
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return result

    def _safe_int(self, v, d=0):
        try:
            return int(v)
        except Exception:
            return d

    # ---------- 详情 ----------
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

    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
        pid = str(vid).split("|$|")[0].replace("$", "|")
        return {"list": [{
            "vod_id": vid, "vod_name": title or "未知标题", "vod_pic": pic or "",
            "vod_remarks": remarks, "vod_content": "",
            "vod_play_from": "播放", "vod_play_url": "播放$" + pid,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        parts = raw.split("|$|")
        vid = parts[0]
        title = parts[1] if len(parts) > 1 else ""
        pic = parts[2] if len(parts) > 2 else ""
        dr = parts[3] if len(parts) > 3 else ""

        # 详情页抓补充信息
        content = ""
        if dr:
            page_url = "%s/videos/%s/%s/" % (self.host, vid, dr)
            try:
                r = self.fetch(page_url, headers=self.headers, timeout=15)
                if r and r.status_code == 200 and len(r.text or "") > 500:
                    content = self._pick_content(r.text or "")
            except Exception:
                pass

        play_url = self._get_play_url(vid)
        if not play_url:
            return self._skeleton(raw, title, pic, "解析中")

        vod = {
            "vod_id": raw,
            "vod_name": title or "视频",
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": content,
            "vod_play_from": "播放",
            "vod_play_url": "播放$" + play_url,
        }
        return {"list": [vod]}

    def _pick_content(self, html):
        m = re.search(r'<meta name="description" content="([^"]*)"', html)
        if m:
            return m.group(1)
        return ""

    # ---------- 播放地址 (base64 + 西里尔同形破解) ----------
    def _get_play_url(self, vid):
        url = "%s/api/videofile.php?video_id=%s&lifetime=8640000" % (self.host, vid)
        try:
            r = self.fetch(url, headers=self.headers, timeout=15)
            if not r or r.status_code != 200:
                return ""
            arr = json.loads(r.text or "[]")
            if not isinstance(arr, list) or not arr:
                return ""
            # 优先 is_default 或第一个
            item = arr[0]
            for it in arr:
                if str(it.get("is_default")) == "1":
                    item = it
                    break
            enc = item.get("video_url") or ""
            return self._decode_video_url(enc)
        except Exception as e:
            self.log({"play": "exception", "error": str(e)})
            return ""

    def _decode_video_url(self, enc):
        if not enc:
            return ""
        # 去掉签名占位符, 还原西里尔同形字母
        s = "".join(self._cyr.get(c, c) for c in enc)
        s = s.replace("~~", "").strip()
        part1, _, part2 = s.partition(",")
        p1 = self._b64d(part1)
        p2 = self._b64d(part2)
        if not p1:
            return ""
        if p2:
            return self.host + p1 + "?" + p2
        return self.host + p1
    def _b64d(self, x):
        if not x:
            return ""
        try:
            x = x + "=" * ((4 - len(x) % 4) % 4)
            return base64.b64decode(x).decode("utf-8", errors="ignore")
        except Exception:
            return ""

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        kw = quote(str(key or ""), safe="")
        # kvs 搜索入口 (浏览器实测: /api/videos2.php?params=.../search..{kw}.all..&)
        # 尾部 & 用 %26 编码, 避免被 HTTP 客户端截断
        url = "%s/api/videos2.php?params=86400/str/relevance/60/search..%s.all..%%26" % (self.host, kw)
        try:
            r = self.fetch(url, headers=self.headers, timeout=15)
            if r and r.status_code == 200 and (r.text or "").strip().startswith("{"):
                data = json.loads(r.text)
                items = self._parse_videos(data)
                if items:
                    return {"list": items, "page": int(pg or 1)}
        except Exception as e:
            self.log({"search": "exception", "error": str(e)})
        # 备用: 不带尾 & 再试一次
        try:
            url2 = "%s/api/videos2.php?params=86400/str/relevance/60/search..%s.all.." % (self.host, kw)
            r2 = self.fetch(url2, headers=self.headers, timeout=15)
            if r2 and r2.status_code == 200 and (r2.text or "").strip().startswith("{"):
                data2 = json.loads(r2.text)
                items2 = self._parse_videos(data2)
                if items2:
                    return {"list": items2, "page": int(pg or 1)}
        except Exception:
            pass
        return {"list": [], "page": int(pg or 1)}
    def recommendContent(self, ids, pg=1):
        try:
            data = self._api_list("latest-updates", "top-country", "hk", 1)
            cur = self._norm_ids(ids).split("|$|")[0]
            items = [i for i in self._parse_videos(data) if not str(i.get("vod_id", "")).startswith(cur + "|$|")]
            return {"list": items}
        except Exception:
            return {"list": []}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_url = str(id) if id else ""
        if "$" in play_url:
            play_url = play_url.split("$", 1)[1]
        play_url = play_url.strip()

        if self.isVideoFormat(play_url) and play_url.startswith("http"):
            return {
                "parse": 0,
                "url": play_url,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/",
                },
            }
        # 否则当作视频 id 再解一次
        vid = play_url
        if "/videos/" in vid:
            m = re.search(r"/videos/(\d+)", vid)
            if m:
                vid = m.group(1)
        real = self._get_play_url(vid)
        if real:
            return {
                "parse": 0,
                "url": real,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/",
                },
            }
        page_url = "%s/videos/%s/" % (self.host, vid)
        return {
            "parse": 1,
            "url": page_url,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
                "Cookie": self.cookie,
            },
        }
