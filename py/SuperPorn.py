# coding: utf-8
# ============================================================
# 站点信息（法则24）
# 站点名：SuperPorn
# 主域名：https://cn.superporn.ws
# 备用域名：https://cn.superporn.me
# 发布页：无固定发布页（多语言子域 cn/vi/tr/ru）
# 内容类型：视频（成人影视）
# 特殊说明：
#   - 详情页 <source src> 直接内嵌带 secure 签名的 mp4 直链，无需二次解析
#   - 分类页/搜索页卡片统一 .thumb-video，可复用同一解析函数
#   - 分页：分类页 /{slug}/{page}，首页 ?page={page}
#   - 搜索：GET /search?q={关键词}
# 最后验证：2026-09-20
# 来源：用户提供 URL
# ============================================================
import json
import re
from urllib.parse import quote, urljoin

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    def __init__(self):
        # 零网络依赖：只做本地初始化
        self.host = "https://cn.superporn.ws"
        self.hosts = ["https://cn.superporn.ws", "https://cn.superporn.me"]
        self.api = "https://api.superporn.ws"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        # 静态分类（法则16/17：分类零网络、静态硬编码）
        self.classes = [
            {"type_id": "lesbian", "type_name": "女同"},
            {"type_id": "ebony", "type_name": "黑人"},
            {"type_id": "big-ass", "type_name": "丰臀"},
            {"type_id": "hentai", "type_name": "成人动漫"},
            {"type_id": "milf", "type_name": "MILF"},
            {"type_id": "latina", "type_name": "拉丁裔"},
            {"type_id": "japanese", "type_name": "日本人"},
            {"type_id": "anal", "type_name": "肛交"},
            {"type_id": "threesome", "type_name": "3P"},
            {"type_id": "creampie", "type_name": "内射"},
            {"type_id": "bbw", "type_name": "BBW"},
            {"type_id": "teen", "type_name": "青少年"},
            {"type_id": "big-tits", "type_name": "Big tits"},
            {"type_id": "interracial", "type_name": "异族"},
            {"type_id": "asian", "type_name": "亚洲人"},
            {"type_id": "gangbang", "type_name": "群交"},
            {"type_id": "pov", "type_name": "POV"},
            {"type_id": "squirting", "type_name": "喷射"},
            {"type_id": "redhead", "type_name": "红发"},
            {"type_id": "shemale", "type_name": "变性人"},
            {"type_id": "mature", "type_name": "成熟"},
            {"type_id": "orgasm", "type_name": "性高潮"},
            {"type_id": "brunette", "type_name": "深色头发"},
            {"type_id": "amateur", "type_name": "业余"},
            {"type_id": "maid", "type_name": "女仆"},
            {"type_id": "fetish", "type_name": "恋物癖"},
            {"type_id": "cosplay", "type_name": "角色扮演"},
            {"type_id": "cheating", "type_name": "偷情"},
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}

        # 多级兜底（法则14）
        self.CARD_SEL = [".thumb-video", "li.thumb-video", "[class*='thumb-video']"]
        self.TITLE_SEL = [
            ".thumb-video__description",
            "a.thumb-video__description",
            "[class*='thumb-video__description']",
            ".thumb-video__meta h3 a",
        ]
        self.PIC_SEL = [
            ".thumb-duracion img",
            "img.lazy",
            "[class*='thumb-duracion'] img",
        ]

    # ==================== 基础方法 ====================

    def getName(self):
        return "SuperPorn"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 零网络；动态域名探测放到 _pick_host（非首页方法内调用）
        self.extend = extend or ""

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return bool(url and re.search(r"\.(m3u8|mp4|flv)(\?|$)", url, re.I))

    def manualVideoCheck(self):
        return False

    # ==================== 域名容灾 ====================

    def _pick_host(self):
        """懒加载域名探测（法则16：不在 homeContent 调用）"""
        if getattr(self, "_cached_host", ""):
            return self._cached_host
        for h in self.hosts:
            try:
                r = self.fetch(h + "/", headers=self.headers, timeout=8, verify=False)
                if r and r.status_code == 200:
                    self._cached_host = h
                    self.headers["Referer"] = h + "/"
                    return h
            except Exception:
                continue
        self._cached_host = self.host
        return self.host

    # ==================== 首页（零网络） ====================

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐：抓首页第一页"""
        host = self._pick_host()
        r = self.fetch(host + "/", headers=self.headers, timeout=15, verify=False)
        if not r or r.status_code != 200:
            self.log({"home": "fetch_failed"})
            return {"list": []}
        return {"list": self._parse_list(r.text, host)}

    # ==================== 分类列表 ====================

    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except Exception:
                pass
            result = {}
            for part in extend.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    result[k.strip()] = v.strip()
            return result
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        host = self._pick_host()
        page = int(pg or 1)
        tid = str(tid or "").strip()
        if not tid:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

        if page <= 1:
            url = "%s/%s" % (host, tid)
        else:
            url = "%s/%s/%d" % (host, tid, page)

        r = self.fetch(url, headers=self.headers, timeout=15, verify=False)
        if not r or r.status_code != 200:
            self.log({"category": "fetch_failed", "url": url})
            return {"list": [], "page": page, "pagecount": 9999, "limit": 20, "total": 0}

        vlist = self._parse_list(r.text, host)
        return {
            "list": vlist,
            "page": page,
            "pagecount": 9999,
            "limit": 20,
            "total": 999999,
        }

    # ==================== 列表解析（复用函数） ====================

    def _parse_list(self, html, host):
        """统一列表解析：分类页/搜索页/首页卡片结构一致"""
        if not html:
            return []
        items = []
        seen = set()
        # 按卡片起始切分，避免非贪婪正则过早闭合
        blocks = re.split(r'<div class="thumb-video\s*">', html)
        for block in blocks[1:]:
            # 详情链接（取第一个 /video/ 链接）
            m_link = re.search(r'href="(https?://[^"]*/video/[^"]+)"', block)
            if not m_link:
                m_link = re.search(r'href="(/video/[^"]+)"', block)
            if not m_link:
                continue
            link = m_link.group(1)
            if link.startswith("/"):
                link = host + link
            if link in seen:
                continue
            seen.add(link)

            # 标题（多级兜底，去内联标签）
            title = ""
            for sel in [
                r'class="thumb-video__description"[^>]*>(.*?)</a>',
                r'<h3>\s*<a[^>]*>(.*?)</a>',
            ]:
                m_t = re.search(sel, block, re.S)
                if m_t:
                    title = re.sub(r"<[^>]+>", "", m_t.group(1)).strip()
                    if title:
                        break
            if not title:
                continue
            title = self._unescape(title)

            # 封面（data-src 优先）
            pic = ""
            m_p = re.search(r'data-src="(https?://[^"]+)"', block)
            if not m_p:
                m_p = re.search(r'<img[^>]+src="(https?://[^"]+)"', block)
            if m_p:
                pic = m_p.group(1)

            # 时长角标
            remark = ""
            m_r = re.search(r'class="duracion">\s*([\d:]+)\s*</span>', block)
            if m_r:
                remark = m_r.group(1).strip()

            # 提取视频 ID（用于去重/骨架兜底）
            vid = self._extract_vid(link)
            items.append({
                "vod_id": link,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return items

    @staticmethod
    def _extract_vid(link):
        m = re.search(r"/video/([^/?#]+)", link)
        return m.group(1) if m else link

    @staticmethod
    def _unescape(s):
        if not s:
            return ""
        s = s.replace("&#039;", "'").replace("&quot;", '"')
        s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        s = s.replace("&#39;", "'").replace("&apos;", "'")
        return s.strip()

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

    # ==================== 详情 ====================

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        host = self._pick_host()
        page_url = raw if raw.startswith("http") else urljoin(host + "/", raw.lstrip("/"))

        vod = {
            "vod_id": raw,
            "vod_name": "",
            "vod_pic": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": "",
        }
        try:
            r = self.fetch(page_url, headers=self.headers, timeout=15, verify=False)
            if not r or r.status_code != 200 or len(r.text or "") < 500:
                return self._skeleton(raw, vod)

            html = r.text

            # 标题：h1 > og:title > title
            m = re.search(r"<h1>(.*?)</h1>", html, re.S)
            if m:
                vod["vod_name"] = self._unescape(re.sub(r"<[^>]+>", "", m.group(1)).strip())
            if not vod["vod_name"]:
                m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
                if m:
                    vod["vod_name"] = self._unescape(m.group(1))
            if not vod["vod_name"]:
                m = re.search(r"<title>(.*?)</title>", html, re.S)
                if m:
                    vod["vod_name"] = self._unescape(m.group(1).replace("- SuperPorn", "").strip())

            # 封面：og:image
            m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            if m:
                vod["vod_pic"] = m.group(1)

            # 简介：#resume
            m = re.search(r'id="resume"[^>]*>(.*?)</span>', html, re.S)
            if m:
                vod["vod_content"] = self._unescape(re.sub(r"<[^>]+>", "", m.group(1)).strip())

            # 分类标签
            tags = re.findall(r'class="chip-link"[^>]*>.*?<span>(.*?)</span>', html, re.S)
            if tags:
                vod["vod_remarks"] = ",".join([self._unescape(t.strip()) for t in tags[:6]])

            # 播放直链：<source src="..."> （优先），兜底正则抓 mp4/m3u8
            play_url = ""
            m = re.search(r'<source\s+src="([^"]+)"', html)
            if m:
                play_url = self._unescape(m.group(1))
            if not play_url:
                m = re.search(r'"(https?://[^"]+\.(?:mp4|m3u8)[^"]*)"', html)
                if m:
                    play_url = self._unescape(m.group(1))

            if play_url:
                vod["vod_play_from"] = "播放"
                vod["vod_play_url"] = "播放$" + play_url
            else:
                # 骨架兜底（法则35）
                return self._skeleton(raw, vod)

            return {"list": [vod]}
        except Exception as e:
            self.log({"detail": "exception", "error": str(e)})
            return self._skeleton(raw, vod)

    def _skeleton(self, vid, vod):
        """法则35：骨架兜底，禁止返回空 list"""
        vod = dict(vod or {})
        vod["vod_id"] = vid
        vod["vod_name"] = vod.get("vod_name") or "未知标题"
        vod["vod_play_from"] = "播放"
        vod["vod_play_url"] = "播放$" + str(vid)
        return {"list": [vod]}

    # ==================== 搜索 ====================

    def searchContent(self, key, quick, pg="1"):
        host = self._pick_host()
        page = int(pg or 1)
        url = "%s/search?q=%s" % (host, quote(str(key or ""), safe=""))
        if page > 1:
            url += "&page=%d" % page
        r = self.fetch(url, headers=self.headers, timeout=15, verify=False)
        if not r or r.status_code != 200:
            self.log({"search": "fetch_failed", "url": url})
            return {"list": [], "page": page}
        return {"list": self._parse_list(r.text, host), "page": page}

    # ==================== 播放 ====================

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id) if id else ""
        # id 可能为 "名称$地址" 格式
        if "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2 and parts[1].strip():
                play_url = parts[1]
        # 补全协议
        if play_url and not play_url.startswith("http"):
            play_url = "https://" + play_url.lstrip("/")

        if not play_url:
            return {"parse": 1, "url": "", "header": self.headers}

        # 直链（mp4/m3u8）直接返回，parse:0
        if self.isVideoFormat(play_url) or play_url.startswith("http"):
            return {
                "parse": 0,
                "url": play_url,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/",
                },
            }
        return {"parse": 1, "url": play_url, "header": self.headers}

    # ==================== 推荐 ====================

    def recommendContent(self, ids, pg):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        host = self._pick_host()
        try:
            # related 接口需数字视频 ID；先从详情页取 data-stats-video-id
            vid = ""
            page_url = raw if raw.startswith("http") else urljoin(host + "/", raw.lstrip("/"))
            r0 = self.fetch(page_url, headers=self.headers, timeout=12, verify=False)
            if r0 and r0.status_code == 200:
                m = re.search(r'data-stats-video-id="(\d+)"', r0.text)
                if m:
                    vid = m.group(1)
            if not vid:
                # 兜底：用 related 接口的 slug 版不可用，直接返回空
                return {"list": []}

            url = "%s/video/%s/related" % (self.api, vid)
            r = self.fetch(url, headers=self.headers, timeout=12, verify=False)
            if r and r.status_code == 200:
                data = r.json()
                items = data.get("videos") or []
                out = []
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    link = it.get("url") or ""
                    if link and not str(link).startswith("http"):
                        link = host + "/" + str(link).lstrip("/")
                    title = it.get("title") or ""
                    if not link or not title:
                        continue
                    out.append({
                        "vod_id": link,
                        "vod_name": title,
                        "vod_pic": it.get("thumb") or "",
                        "vod_remarks": it.get("duration") or "",
                    })
                if out:
                    return {"list": out}
        except Exception as e:
            self.log({"recommend": "exception", "error": str(e)})
        return {"list": []}
