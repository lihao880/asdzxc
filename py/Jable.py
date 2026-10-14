# coding: utf-8
# ============================================================
# 站点信息（法则24）
# 名称：Jable（jable1.nl 系列）
# 主域名：https://jable1.nl
# 备用域名：https://jable888.net（发布页观察）
# 发布页/入口：https://jable1.nl/enter
# 内容类型：视频（成人影视，非视频闭环不适用）
# 特殊说明：
#   - 列表容器 .video-img-box，标题 .detail h6.title a，封面 img[data-src]，
#     角标 .absolute-bottom-right .label（时长）
#   - 分页统一为 {base}/{page}/（new-release / categories/{slug} / search/{kw}）
#   - 播放直链在详情页 var hlsUrl = '...m3u8'（inline script，非外链）
#   - m3u8_analyzer 取证工具卡住未完成，按「原始直链不代理」策略返回 parse:0
# 最后验证时间：2026-09-14
# 来源：AI 自主分析（fetch_html / pagination_parser / selector_fallback_generator）
# ============================================================
import re
import json
from urllib.parse import quote, urljoin, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        # __init__ 零网络，保证首页秒出 class
        self.extend = ""
        self.host = "https://jable1.nl"
        self.classes = [
            {"type_id": "new-release", "type_name": "最新上市"},
            {"type_id": "latest-updates", "type_name": "最近更新"},
            {"type_id": "hot", "type_name": "热门影片"},
            {"type_id": "categories/bdsm", "type_name": "主奴调教"},
            {"type_id": "categories/sex-only", "type_name": "直接开啪"},
            {"type_id": "categories/chinese-subtitle", "type_name": "中文字幕"},
            {"type_id": "categories/rape", "type_name": "凌辱快感"},
            {"type_id": "categories/uniform", "type_name": "制服诱惑"},
            {"type_id": "categories/roleplay", "type_name": "角色剧情"},
            {"type_id": "categories/private-cam", "type_name": "盗摄偷拍"},
            {"type_id": "categories/uncensored", "type_name": "无码解放"},
            {"type_id": "categories/pov", "type_name": "男友视角"},
            {"type_id": "categories/groupsex", "type_name": "多P群交"},
            {"type_id": "categories/pantyhose", "type_name": "丝袜美腿"},
            {"type_id": "categories/lesbian", "type_name": "女同欢愉"},
        ]
        self.filters = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
        }

    # ---------- 基础 ----------
    def getName(self):
        return "Jable"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 零网络
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

    def _fetch_html(self, url):
        try:
            r = self.fetch(url, headers=self.headers, timeout=15)
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
        """解析视频卡片列表，多级兜底（法则14）"""
        items = []
        if not html:
            return items
        # 按卡片起始切分，避免正则跨卡片
        blocks = re.split(r'<div class="video-img-box', html)[1:]
        for b in blocks:
            # 播放页链接
            m = re.search(r'<a\s+href="(https?://[^"]*/videos/[^"]+)"', b)
            if not m:
                continue
            link = m.group(1)
            vid = link.rstrip("/").split("/videos/")[-1]
            if not vid:
                continue
            # 标题：h6.title 内 a（去内联标签）
            name = ""
            mt = re.search(r'<h6[^>]*class="[^"]*title[^"]*"[^>]*>\s*<a[^>]*>(.*?)</a>', b, re.S)
            if mt:
                name = self._clean(mt.group(1))
            if not name:
                mt = re.search(r'<h6[^>]*>(.*?)</h6>', b, re.S)
                name = self._clean(mt.group(1)) if mt else ""
            # 封面：优先 data-src，其次 style background-image，再次 src
            pic = ""
            mp = re.search(r'data-src="([^"]+)"', b)
            if mp:
                pic = mp.group(1)
            if not pic:
                mp = re.search(r"background-image:url\('([^']+)'\)", b)
                pic = mp.group(1) if mp else ""
            if not pic:
                mp = re.search(r'<img[^>]+src="(https?://[^"]+)"', b)
                pic = mp.group(1) if mp else ""
            # 角标：时长 label
            remark = ""
            mr = re.search(r'class="label">([^<]+)</span>', b)
            if mr:
                remark = self._clean(mr.group(1))
            # 播放 ID 打包：vid|$|名称|$|封面|$|角标
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
        html = self._fetch_html(self.host + "/new-release/")
        return {"list": self._parse_list(html)}

    # ---------- 分类 ----------
    def _build_list_url(self, tid, pg):
        tid = (tid or "new-release").strip("/")
        if tid.startswith("categories/"):
            base = "{}/{}".format(self.host, tid)
        else:
            base = "{}/{}".format(self.host, tid)
        return "{}/{}/".format(base.rstrip("/"), pg or "1")

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
        """从分页区精确提取总页数，避免误抓正文数字（法则19）"""
        if not html:
            return 1
        cur = int(page) if str(page).isdigit() else 1
        candidates = []
        # 形如 "1 / 226" 或 "1/226"
        for m in re.finditer(r"(\d{1,6})\s*/\s*(\d{1,6})", html):
            a, b = int(m.group(1)), int(m.group(2))
            if a == cur and b >= cur:
                candidates.append(b)
        # 形如 "共 226 页"
        for m in re.finditer(r"共\s*(\d{1,6})\s*页", html):
            candidates.append(int(m.group(1)))
        # 分页区最大页码
        for m in re.finditer(r'class="[^"]*(?:page|pagination|fenye)[^"]*"[^>]*>(.*?)</', html, re.S):
            nums = [int(x) for x in re.findall(r"\d{1,6}", m.group(1))]
            if nums:
                candidates.append(max(nums))
        if candidates:
            return max(candidates)
        return 1
    def searchContent(self, key, quick, pg="1"):
        page = str(pg or "1")
        kw = quote(str(key or ""), safe="")
        url = "{}/search/{}/{}/".format(self.host, kw, page)
        html = self._fetch_html(url)
        return {"list": self._parse_list(html), "page": int(page) if page.isdigit() else 1}

    # ---------- 详情 ----------
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
            old_name = ps[1] if len(ps) > 1 else ""
            old_pic = ps[2] if len(ps) > 2 else ""
            old_remark = ps[3] if len(ps) > 3 else ""

            detail_url = "{}/videos/{}/".format(self.host, vid)
            html = self._fetch_html(detail_url)
            if not html or len(html) < 500:
                return self._skeleton(raw, old_name, old_pic, old_remark)

            # 标题：og:title 或 h4/h6 标题
            name = old_name
            mt = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
            if mt:
                name = self._clean(mt.group(1))
            if not name:
                mt = re.search(r"<title>(.*?)</title>", html, re.S)
                if mt:
                    name = self._clean(mt.group(1)).split(" - ")[0]

            # 封面：og:image 或 preview.jpg
            pic = old_pic
            mp = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
            if mp:
                pic = mp.group(1)
            if not pic:
                mp = re.search(r'poster="([^"]+)"', html)
                pic = mp.group(1) if mp else ""

            # 简介/备注
            content = old_remark
            mc = re.search(r'上市于\s*([0-9\-]+)', html)
            if mc:
                content = "上市于 " + mc.group(1)

            # 播放地址提取（9层管线，站点为 L2 播放器变量直取）
            play_url = self._extract_play_url(html, detail_url)

            vod = {
                "vod_id": raw,
                "vod_name": name or vid,
                "vod_pic": pic,
                "vod_remarks": old_remark,
                "vod_content": content,
                "vod_play_from": "播放",
                "vod_play_url": "播放$" + (play_url if play_url else vid),
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"detail": "exception", "ids": raw, "error": type(e).__name__})
            return self._skeleton(raw)

    # ---------- 播放地址提取（法则32：多层级） ----------
    def _extract_play_url(self, html, page_url):
        if not html:
            return ""
        candidates = []
        # L1/L2：var hlsUrl = '...'
        for pat in [
            r"var\s+hlsUrl\s*=\s*'([^']+)'",
            r'var\s+hlsUrl\s*=\s*"([^"]+)"',
            r"hlsUrl['\"]?\s*[:=]\s*['\"]([^'\"]+\.m3u8[^'\"]*)",
            r"source\s*[:=]\s*['\"]([^'\"]+\.m3u8[^'\"]*)",
        ]:
            for m in re.finditer(pat, html):
                candidates.append(m.group(1))
        # L5：全文正则兜底（mp4/m3u8）
        for m in re.finditer(r"https?://[^\s'\"<>]+\.(?:m3u8|mp4)(?:\?[^\s'\"<>]*)?", html):
            candidates.append(m.group(0))
        # 归一化
        out = []
        for c in candidates:
            c = c.replace("\\/", "/").replace("\\u002f", "/")
            c = unquote(c) if "%2F" in c or "%3A" in c else c
            if c.startswith("//"):
                c = "https:" + c
            if not c.startswith("http"):
                c = urljoin(page_url, c)
            if c not in out:
                out.append(c)
        # 优先 m3u8
        for c in out:
            if ".m3u8" in c.lower():
                return c
        return out[0] if out else ""

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_url = str(id or "")
        # 处理 "名称$地址" 形态
        if "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2 and (parts[1].startswith("http") or "/" in parts[1] or "." in parts[1]):
                play_url = parts[1]
        # 若 id 只是 slug（无 http），尝试抓详情页取直链
        if not play_url.startswith("http"):
            slug = play_url.strip("/").split("/")[-1]
            if slug:
                detail_url = "{}/videos/{}/".format(self.host, slug)
                html = self._fetch_html(detail_url)
                real = self._extract_play_url(html, detail_url)
                if real:
                    # 取证未完成（m3u8_analyzer 卡住），按原始直链返回，不代理
                    return {"parse": 0, "url": real, "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": detail_url,
                    }}
            return {"parse": 1, "url": id, "header": self.headers}
        return {"parse": 0, "url": play_url, "header": {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.host + "/",
        }}

    # ---------- 推荐 ----------
    def recommendContent(self, ids, pg):
        return {"list": []}
