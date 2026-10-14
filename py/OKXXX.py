# coding: utf-8
# ============================================================
# 站点: OKXXX (okxxx.life)
# 域名: https://okxxx.life  (备用: https://okxxx1.com)
# 发布页: https://okxxx.life/enter
# 类型: 视频站 (mp4 直链, 无 m3u8, 无加密)
# 分页: https://okxxx.life/{page}/   (?page 形), 列表页 /1/
# 搜索: https://okxxx.life/search/?q=关键词
# 详情: https://okxxx.life/video/{id}/
# 封面: img.thumb.lazy-load[data-original]
# 播放: <source src=".../xxx_720p.mp4/"> 多清晰度, 也见 var url= 与 videoUrl =
# 特殊: 详情页内嵌 mp4 直链, 直接 parse:0 返回; 无广告特征不套代理
# 最后验证: 2026-09-20
# 来源: 用户提供 URL 全自动开发
# ============================================================
import json
import re
from urllib.parse import quote, urljoin, urlparse, parse_qs

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        # 零网络: 只做本地初始化
        self.host = "https://okxxx.life"
        self.backups = ["https://okxxx.life", "https://okxxx1.com"]
        self.classes = [
            {"type_id": "1", "type_name": "最新"},
            {"type_id": "2", "type_name": "热门"},
        ]
        # 站点为"最新视频"分页站, 无多维筛选 DOM, 不伪造假筛选
        self.filters = {"1": [], "2": []}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
        }
        self._host_checked = False

    # ---------- 基础 ----------
    def getName(self):
        return "OKXXX"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 零网络, 动态域名探测延后到 _pick_host()
        pass

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return bool(url and re.search(r"\.(m3u8|mp4|flv|m4s)(/|$|\?)", url, re.I))

    def manualVideoCheck(self):
        return False

    # ---------- 多域名懒加载探测 (法则16/18) ----------
    def _pick_host(self):
        if self._host_checked:
            return self.host
        for h in self.backups:
            try:
                r = self.fetch(h + "/enter", headers=self.headers, timeout=12)
                if r and r.status_code == 200 and len(r.text or "") > 5000:
                    self.host = h
                    self.headers["Referer"] = h + "/"
                    break
            except Exception:
                continue
        self._host_checked = True
        return self.host

    # ---------- 首页 (零网络) ----------
    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        self._pick_host()
        r = self.fetch(self.host + "/enter", headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": []}
        return {"list": self._parse_list(r.text or "")}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        self._pick_host()
        page = str(pg or "1")
        url = "%s/%s/" % (self.host, page)
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        html = r.text or ""
        items = self._parse_list(html)
        pc = self._parse_pagecount(html)
        # 窗口式分页器给不出确切总页数时给足余量, 靠末页空列表自然停止
        pagecount = pc if pc else (int(page) + 20)
        return {
            "list": items,
            "page": int(page),
            "pagecount": int(pagecount),
            "limit": 20,
            "total": pagecount * 60,
        }
    def _parse_pagecount(self, html):
        # 分页器为 1..9 + "..." + 10 + Next 的窗口式, 总页数不直出。
        # 取 "..." 后的最大页码作为下限; 无 Next 时该页即末页。
        if not html:
            return 0
        if 'pagination-next' not in html:
            m = re.search(r'href="/%s/(\d+)/"' % re.escape(self.host), html)
            return int(m.group(1)) if m else 1
        pages = [int(x) for x in re.findall(r'href="%s/(\d+)/"' % re.escape(self.host), html)]
        return max(pages) if pages else 0
    def _parse_list(self, html):
        result = []
        seen = set()
        # 卡片: <a href="/video/ID/" title="TITLE" ...> ... <img ... data-original="PIC" ...>
        blocks = re.split(r'<div class="\s*item thumb-bl thumb-bl-video', html)
        for b in blocks[1:]:
            m = re.search(r'<a href="(/video/(\d+)/)"\s+title="([^"]*)"', b)
            if not m:
                continue
            vid = m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            title = self._unescape(m.group(3))
            pm = re.search(r'data-original="([^"]+)"', b)
            pic = pm.group(1) if pm else ""
            tm = re.search(r'<li><i class="fa fa-clock-o"></i>\s*<span>([^<]+)</span>', b)
            remark = tm.group(1).strip() if tm else ""
            result.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return result

    def _unescape(self, s):
        if not s:
            return ""
        return (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                 .replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")).strip()

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
        self._pick_host()
        # 兼容列表阶段打包串 或 纯 id
        parts = raw.split("|$|")
        vid = parts[0]
        old_name = parts[1] if len(parts) > 1 else ""
        old_pic = parts[2] if len(parts) > 2 else ""
        old_remark = parts[3] if len(parts) > 3 else ""

        url = "%s/video/%s/" % (self.host, vid)
        r = self.fetch(url, headers=self.headers, timeout=15)
        html = (r.text or "") if (r and r.status_code == 200) else ""

        title = self._pick_title(html) or old_name or "视频"
        pic = self._pick_pic(html) or old_pic
        content = self._pick_content(html) or old_remark

        play_url = self._pick_play(html, vid, url)
        if not play_url:
            # 骨架兜底 (法则35)
            return self._skeleton(raw, title, pic, old_remark or "解析中")

        vod = {
            "vod_id": raw,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": old_remark,
            "vod_content": content,
            "vod_play_from": "播放",
            "vod_play_url": "播放$" + play_url,
        }
        return {"list": [vod]}

    def _pick_title(self, html):
        if not html:
            return ""
        m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        if m:
            t = self._unescape(m.group(1))
            return re.sub(r'\s*[-|]\s*OKXXX.*$', '', t).strip()
        m = re.search(r"<title>([^<]+)</title>", html)
        if m:
            t = self._unescape(m.group(1))
            t = re.sub(r'^\s*Video\s*', '', t)
            return re.sub(r'\s*[-|]\s*OKXXX.*$', '', t).strip()
        return ""

    def _pick_pic(self, html):
        if not html:
            return ""
        m = re.search(r'poster="([^"]+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'data-original="(https?://[^"]+\.jpg)"', html)
        return m.group(1) if m else ""

    def _pick_content(self, html):
        if not html:
            return ""
        m = re.search(r'<meta name="description" content="([^"]*)"', html)
        if m:
            return self._unescape(m.group(1))
        return ""

    def _pick_play(self, html, vid, page_url):
        """从详情页内嵌的多个 mp4 source / var url 中提取最佳清晰度直链"""
        if not html:
            return ""
        urls = []
        # 1) <source src=".../xxx_720p.mp4/">
        for m in re.finditer(r'<source src="([^"]+\.mp4[^"]*)"', html):
            urls.append(m.group(1))
        # 2) var url = '...' / var videoUrl = '...'
        for m in re.finditer(r"var\s+(?:videoUrl|url)\s*=\s*'([^']+\.mp4[^']*)'", html):
            urls.append(m.group(1))
        # 归一化并去重
        norm = []
        seen = set()
        for u in urls:
            u = self._normalize_url(u)
            if u and u not in seen:
                seen.add(u)
                norm.append(u)
        if not norm:
            return ""
        # 优先 720p -> 480p -> 其它 (排除 preview)
        norm = [u for u in norm if "preview" not in u.lower()]
        if not norm:
            return ""
        def rank(u):
            if "_720p" in u or "/720" in u:
                return 0
            if "_480p" in u or "/480" in u:
                return 1
            if "_360p" in u or "/360" in u:
                return 2
            return 3
        norm.sort(key=rank)
        return norm[0]

    def _normalize_url(self, u):
        if not u:
            return ""
        u = u.strip().replace("\\/", "/").replace("\\u002f", "/")
        u = u.replace("&amp;", "&")
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = self.host + u
        if not u.startswith("http"):
            u = "https://" + u.lstrip("/")
        return u

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        self._pick_host()
        kw = quote(str(key or ""), safe="")
        url = "%s/search/?q=%s" % (self.host, kw)
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": [], "page": 1}
        return {"list": self._parse_list(r.text or ""), "page": int(pg or 1)}

    # ---------- 推荐 ----------
    def recommendContent(self, ids, pg=1):
        # 详情页已含相关推荐卡片, 这里直接复用最新列表, 避免额外网络
        try:
            self._pick_host()
            r = self.fetch(self.host + "/enter", headers=self.headers, timeout=15)
            if not r or r.status_code != 200:
                return {"list": []}
            cur = str(ids).split("|$|")[0] if ids else ""
            items = [i for i in self._parse_list(r.text or "") if str(i.get("vod_id")) != cur]
            return {"list": items}
        except Exception:
            return {"list": []}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_url = str(id) if id else ""
        # id 可能是 "名称$地址" 或纯地址
        if "$" in play_url:
            play_url = play_url.split("$", 1)[1]
        play_url = play_url.strip()

        # 内嵌完整直链
        if self.isVideoFormat(play_url) and play_url.startswith("http"):
            return {
                "parse": 0,
                "url": play_url,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/",
                },
            }

        # 否则当作视频 id / 页面路径, 抓详情页提取直链
        vid = play_url
        if "/video/" in vid:
            m = re.search(r'/video/(\d+)', vid)
            if m:
                vid = m.group(1)
        self._pick_host()
        page_url = "%s/video/%s/" % (self.host, vid)
        try:
            r = self.fetch(page_url, headers=self.headers, timeout=15)
            html = (r.text or "") if (r and r.status_code == 200) else ""
            real = self._pick_play(html, vid, page_url)
            if real:
                return {
                    "parse": 0,
                    "url": real,
                    "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": self.host + "/",
                    },
                }
        except Exception as e:
            self.log({"player": "exception", "error": str(e)})

        # 最后兜底: 交壳嗅探 (带完整 header)
        return {
            "parse": 1,
            "url": page_url,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
            },
        }