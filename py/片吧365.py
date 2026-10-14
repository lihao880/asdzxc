# coding: utf-8
# ============================================================
# 站点信息（法则24）
# 名称：片吧365（pb365.nl）
# 主域名：https://pb365.nl
# 备用域名：https://hsex1.sbs（导航页观察）
# 发布页/入口：https://pb365.nl/enter
# 内容类型：视频（成人短视频/自拍）
# 特殊说明：
#   - 列表卡片 .thumbnail；链接 a[href="video-{id}.htm"]；
#     标题 .image[title]；封面 .image 的 style background-image:url(...)
#   - 分页统一 list-{pg}.htm（各分类前缀不同：top7_/top_/5min_/long_/hot_）
#   - 详情页必须带 Referer（否则 503 维护页）；搜索页同理
#   - 播放地址在 iframe: player.centercdn.top/player.html?video_url=<urlencoded m3u8>
#   - 播放器对 m3u8 做域名重写 replaceResUrl：
#       https://pb365.nl/xxx -> https://rjmp1.centercdn.top/pb365.nl/xxx
#     本脚本在 playerContent 中实现该重写，直链返回
# 最后验证时间：2026-09-14
# 来源：AI 自主分析（fetch_html / pagination_parser）
# ============================================================
import re
import json
from urllib.parse import quote, urljoin, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        # __init__ 零网络
        self.extend = ""
        self.host = "https://pb365.nl"
        self.classes = [
            {"type_id": "list", "type_name": "最新"},
            {"type_id": "hot_list", "type_name": "最热"},
            {"type_id": "top7_list", "type_name": "周榜"},
            {"type_id": "top_list", "type_name": "月榜"},
            {"type_id": "5min_list", "type_name": "5分钟+"},
            {"type_id": "long_list", "type_name": "10分钟+"},
        ]
        self.filters = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/list-1.htm",
        }

    # ---------- 基础 ----------
    def getName(self):
        return "片吧365"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def destroy(self):
        pass

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    # ---------- 工具 ----------
    @staticmethod
    def _norm_ids(ids):
        """法则35：ids 兼容 list/str/int/bytes"""
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def _fetch_html(self, url, referer=None):
        h = dict(self.headers)
        if referer:
            h["Referer"] = referer
        try:
            r = self.fetch(url, headers=h, timeout=20)
        except Exception as e:
            self.log({"fetch": "exception", "url": url, "error": type(e).__name__})
            return ""
        if not r or r.status_code != 200:
            self.log({"fetch": "failed", "url": url, "status": getattr(r, "status_code", None)})
            return ""
        return r.text or ""

    @staticmethod
    def _clean(text):
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&amp;", "&").replace("&nbsp;", " ").replace("&#39;", "'").replace("&quot;", '"')
        return re.sub(r"\s+", " ", text).strip()

    def _parse_list(self, html):
        """解析视频卡片列表（.thumbnail），多级兜底"""
        items = []
        if not html:
            return items
        blocks = re.split(r'<div class="thumbnail"', html)[1:]
        for b in blocks:
            # 播放页链接 video-{id}.htm
            m = re.search(r'href="(video-(\d+)\.htm)"', b)
            if not m:
                continue
            vid = m.group(2)
            link = m.group(1)
            # 标题：.image[title]
            name = ""
            mt = re.search(r'class="image"[^>]*title="([^"]*)"', b)
            if mt:
                name = self._clean(mt.group(1))
            if not name:
                mt = re.search(r'title="([^"]+)"', b)
                name = self._clean(mt.group(1)) if mt else ""
            # 封面：style background-image url
            pic = ""
            mp = re.search(r"background-image:\s*url\('([^']+)'\)", b)
            if mp:
                pic = mp.group(1)
            if not pic:
                mp = re.search(r'data-original="([^"]+)"', b)
                pic = mp.group(1) if mp else ""
            # 时长角标
            remark = ""
            mr = re.search(r'<var[^>]*class="duration"[^>]*>([^<]+)</var>', b)
            if mr:
                remark = self._clean(mr.group(1))
            packed = "{}|$|{}|$|{}|$|{}".format(vid, name, pic, remark)
            items.append({
                "vod_id": packed,
                "vod_name": name or vid,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return items

    # ---------- 首页推荐 ----------
    def homeVideoContent(self):
        # 与 categoryContent("list", 1) 同源；失败时重试一次
        url = self.host + "/list-1.htm"
        html = self._fetch_html(url)
        items = self._parse_list(html)
        if not items:
            html = self._fetch_html(url, referer=self.host + "/")
            items = self._parse_list(html)
        return {"list": items}
    def _build_list_url(self, tid, pg):
        tid = (tid or "list").strip("/")
        base = tid if tid.endswith("_list") else tid
        return "{}/{}-{}.htm".format(self.host, base, pg or "1")

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        url = self._build_list_url(tid, page)
        html = self._fetch_html(url)
        items = self._parse_list(html)
        pagecount = self._parse_pagecount(html, page)
        return {
            "list": items,
            "page": int(page) if page.isdigit() else 1,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20,
        }

    def _parse_pagecount(self, html, page):
        """从分页区精确提取总页数（法则19）"""
        if not html:
            return 1
        cur = int(page) if str(page).isdigit() else 1
        nums = [int(x) for x in re.findall(r'class="page-link"[^>]*>(\d+)<', html)]
        if not nums:
            nums = [int(x) for x in re.findall(r'(\d+)\.htm"[^>]*class="page-link"', html)]
        if nums:
            # 分页区通常展示当前页附近页码，取最大合理值
            mx = max(nums)
            return mx if mx >= cur else 1
        return 1

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        page = str(pg or "1")
        kw = quote(str(key or ""), safe="")
        # 预热列表页拿会话 Cookie（该站搜索/详情需预热 + Referer）
        self._fetch_html(self.host + "/list-1.htm")
        url = "{}/search.htm?search={}".format(self.host, kw)
        html = self._fetch_html(url, referer=self.host + "/list-1.htm")
        return {"list": self._parse_list(html), "page": int(page) if page.isdigit() else 1}
    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
        """法则35：骨架兜底，禁止返回空 list"""
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
        try:
            ps = raw.split("|$|")
            vid = ps[0]
            name = ps[1] if len(ps) > 1 else ""
            pic = ps[2] if len(ps) > 2 else ""
            remark = ps[3] if len(ps) > 3 else ""

            # 优先尝试抓详情页拿 og 元数据 + 直链（带重试）
            detail_url = "{}/video-{}.htm".format(self.host, vid)
            html = self._fetch_html(detail_url, referer=self.host + "/list-1.htm")
            if not html or len(html) < 500:
                html = self._fetch_html(detail_url, referer=self.host + "/")

            play_url = ""
            if html and len(html) >= 500:
                mt = re.search(r'property="og:title"[^>]*content="([^"]+)"', html)
                if mt:
                    name = self._clean(mt.group(1)) or name
                mp = re.search(r'property="og:image"[^>]*content="([^"]+)"', html)
                if mp:
                    pic = mp.group(1) or pic
                play_url = self._extract_play_url(html, detail_url)

            # 详情页失败也不返回空：用列表字段兜底，play_url 交 playerContent 再抢救
            vod = {
                "vod_id": raw,
                "vod_name": name or vid,
                "vod_pic": pic,
                "vod_remarks": remark,
                "vod_content": remark,
                "vod_play_from": "播放",
                "vod_play_url": "播放$" + (play_url if play_url else vid),
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"detail": "exception", "ids": raw, "error": type(e).__name__})
            return self._skeleton(raw)
    @staticmethod
    def _replace_res_url(url):
        """实现播放器 replaceResUrl：https://host/path -> https://rjmp1.centercdn.top/host/path"""
        try:
            m = re.match(r"^(https?)://([\w\.\-]+?)(/.*)$", url)
            if m:
                return "{}://rjmp1.centercdn.top/{}{}".format(m.group(1), m.group(2), m.group(3))
        except Exception:
            pass
        return url

    def _extract_play_url(self, html, page_url):
        if not html:
            return ""
        candidates = []
        # L6：iframe 内嵌 player.html?video_url=<urlencoded>
        for m in re.finditer(r'player\.html\?video_url=([^"&\s]+)', html):
            raw = unquote(m.group(1))
            if raw.startswith("http"):
                candidates.append(raw)
        # L5：全文正则兜底
        for m in re.finditer(r"https?://[^\s'\"<>]+\.m3u8(?:\?[^\s'\"<>]*)?", html):
            candidates.append(m.group(0))
        # 归一化 + 重写
        out = []
        for c in candidates:
            c = c.replace("\\/", "/").replace("\\u002f", "/")
            if c.startswith("//"):
                c = "https:" + c
            if not c.startswith("http"):
                c = urljoin(page_url, c)
            if c not in out:
                out.append(c)
        for c in out:
            if ".m3u8" in c.lower():
                return self._replace_res_url(c)
        return out[0] if out else ""

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_url = str(id or "")
        if "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2 and ("/" in parts[1] or "." in parts[1]):
                play_url = parts[1]
        # 只有 vid，抓详情页取直链
        if not play_url.startswith("http"):
            vid = re.sub(r"\D", "", play_url) or str(play_url).strip("/")
            if vid:
                detail_url = "{}/video-{}.htm".format(self.host, vid)
                html = self._fetch_html(detail_url, referer=self.host + "/list-1.htm")
                real = self._extract_play_url(html, detail_url)
                if real:
                    return {"parse": 0, "url": real, "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": "https://player.centercdn.top/",
                    }}
            return {"parse": 1, "url": id, "header": self.headers}
        return {"parse": 0, "url": play_url, "header": {
            "User-Agent": self.headers["User-Agent"],
            "Referer": "https://player.centercdn.top/",
        }}

    def recommendContent(self, ids, pg):
        return {"list": []}
