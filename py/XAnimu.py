# coding: utf-8
# ============================================================
# 站点: xanimu.one (XAnimu) 成人动漫/Hentai 视频站
# 主域名: https://xanimu.one
# 备用:   https://xanimu.art
# 发布页: 无（主域直接可用）
# 内容类型: 视频（mp4 直链，非 m3u8）
# 架构: WordPress + kolortube 主题，纯服务端渲染，非 SPA
# 播放: 详情页内联 JS 明文变量 videoHigh/videoLow（带 verify 签名 mp4 直链）
# 特殊说明: 列表卡片链接为完整详情页 URL；分页为 /{分类slug}/有关详细信息.../{page}/
# 最后验证: 2026-09-20
# 来源: 自主逆向
# ============================================================
import json
import re
from urllib.parse import quote, urljoin, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        # __init__ 零网络，只做本地初始化
        self.extend = ""
        self.host = "https://xanimu.one"
        self.lang = "/zh-CN"
        self.classes = [
            {"type_id": "/zh-CN/36900-2d/", "type_name": "2D"},
            {"type_id": "/zh-CN/5-3d-%E6%97%A0%E5%B0%BD/", "type_name": "3D"},
            {"type_id": "/zh-CN/16884%E4%B8%AA%E7%81%B5%E9%AD%82/", "type_name": "日本动画"},
            {"type_id": "/zh-CN/22%E6%B8%B8%E6%88%8F/", "type_name": "游戏"},
            {"type_id": "/zh-CN/24-%E9%83%A8%E7%94%B5%E8%A7%86%E8%8A%82%E7%9B%AE/", "type_name": "电视节目"},
            {"type_id": "/zh-CN/23%E7%94%B5%E5%BD%B1/", "type_name": "电影"},
            {"type_id": "/zh-CN/15410%E6%BC%AB%E7%94%BB/", "type_name": "漫画"},
            {"type_id": "/zh-CN/40241%E5%8D%A1%E9%80%9A/", "type_name": "卡通"},
            {"type_id": "/zh-CN/47441-hmv/", "type_name": "HMV"},
            {"type_id": "/zh-CN/47420%E6%AF%AB%E7%B1%B3/", "type_name": "MMD"},
            {"type_id": "/zh-CN/4-%E6%AF%9B%E8%8C%B8%E8%8C%B8%E7%9A%84%E6%97%A0%E5%B0%BD/", "type_name": "毛茸茸"},
            {"type_id": "/zh-CN/6-%E4%B9%B1%E4%BC%A6%E6%97%A0%E5%B0%BD/", "type_name": "乱伦"},
            {"type_id": "/zh-CN/7-%E8%A7%A6%E6%89%8B%E6%97%A0%E5%B0%BD/", "type_name": "触手"},
            {"type_id": "/zh-CN/8-futanari-%E6%97%A0%E5%B0%BD/", "type_name": "扶他"},
            {"type_id": "/zh-CN/9476-yaoi-%E6%97%A0%E5%B0%BD/", "type_name": "Yaoi"},
            {"type_id": "/zh-CN/9475-femdom-%E6%97%A0%E5%B0%BD/", "type_name": "Femdom"},
            {"type_id": "/zh-CN/9480-bdsm-%E6%97%A0%E5%B0%BD/", "type_name": "BDSM"},
            {"type_id": "/zh-CN/9404-%E6%B7%B1%E8%89%B2%E7%9A%AE%E8%82%A4%E6%97%A0%E5%B0%BD/", "type_name": "深色皮肤"},
            {"type_id": "/zh-CN/9478-%E9%A9%AC-hentai/", "type_name": "马"},
            {"type_id": "/zh-CN/9479-disney-%E6%97%A0%E5%B0%BD/", "type_name": "Disney"},
            {"type_id": "/zh-CN/5519%E6%97%A0%E5%B0%BD%E7%9A%84/", "type_name": "无尽"},
            {"type_id": "/zh-CN/13-%E6%80%AA%E7%89%A9%E6%97%A0%E5%B0%BD/", "type_name": "怪物"},
            {"type_id": "/zh-CN/10-%E5%A5%B3%E5%B7%A8%E4%BA%BA%E6%97%A0%E5%B0%BD/", "type_name": "女巨人"},
            {"type_id": "/zh-CN/11-%E4%B9%B3%E6%88%BF%E6%89%A9%E5%BC%A0%E6%97%A0%E5%B0%BD/", "type_name": "乳房扩张"},
            {"type_id": "/zh-CN/19-%E4%B8%AD%E5%87%BA%E6%97%A0%E5%B0%BD/", "type_name": "中出"},
            {"type_id": "/zh-CN/61626%E6%94%BB%E5%87%BB%E6%B3%B0%E5%9D%A6/", "type_name": "进击的巨人"},
            {"type_id": "/zh-CN/614-naruto-2/", "type_name": "Naruto"},
            {"type_id": "/zh-CN/24-%E9%83%A8%E7%94%B5%E8%A7%86%E8%8A%82%E7%9B%AE/26-pokemon/", "type_name": "Pokemon"},
            {"type_id": "/zh-CN/22%E6%B8%B8%E6%88%8F/9489-minecraft/", "type_name": "Minecraft"},
            {"type_id": "/zh-CN/16884%E4%B8%AA%E7%81%B5%E9%AD%82/16597%E4%B8%80%E4%BB%B6/", "type_name": "One Piece"},
        ]
        self.filters = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
        }

    # ---------------- 基础方法 ----------------

    def getName(self):
        return "XAnimu"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # init 零网络
        self.extend = extend or ""

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return bool(url and re.search(r"\.(mp4|m3u8|flv|ts)(\?|$)", str(url), re.I))

    def manualVideoCheck(self):
        return False

    # ---------------- 首页 ----------------

    def homeContent(self, filter):
        # 零网络，分类静态返回
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 首页推荐 = 首页列表
        try:
            html = self._fetch_html(self.host + self.lang + "/")
            vlist = self._parse_list(html)
            return {"list": vlist}
        except Exception as e:
            self.log({"home": "exception", "error": str(e)})
            return {"list": []}

    # ---------------- 分类 ----------------

    def _parse_extend(self, extend):
        """法则20：extend 支持 dict / json串 / k=v,k=v 三种格式"""
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            s = extend.strip()
            if not s:
                return {}
            try:
                obj = json.loads(s)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
            result = {}
            for part in s.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    result[k.strip()] = v.strip()
            return result
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        try:
            base = str(tid or "").strip()
            if not base.startswith("http"):
                base = self.host + (base if base.startswith("/") else "/" + base)
            if not base.endswith("/"):
                base += "/"

            # 分页模板： {base}有关详细信息，请查看此页面。/{page}/
            # 第1页用 base 自身，其余用 slug 模板
            slug = quote("有关详细信息，请查看此页面。", safe="")
            if page == "1":
                url = base
            else:
                url = base + slug + "/" + page + "/"

            html = self._fetch_html(url)
            vlist = self._parse_list(html)
            if not vlist and page != "1":
                # 回退：尝试 /{page}/ 直拼
                alt = base + page + "/"
                if alt != url:
                    html = self._fetch_html(alt)
                    vlist = self._parse_list(html)

            return {
                "list": vlist,
                "page": int(page),
                "pagecount": 9999,
                "limit": 48,
                "total": 999999,
            }
        except Exception as e:
            self.log({"category": "exception", "tid": tid, "pg": pg, "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 48, "total": 0}

    # ---------------- 列表解析 ----------------

    CARD_SPLIT = re.compile(r'<div class="video-block[^"]*"')

    def _parse_list(self, html):
        """解析视频卡片列表。结构： div.video-block > a.thumb[href] + a.infos[href] > span.title"""
        if not html:
            return []
        out = []
        seen = set()
        # 按卡片起始标记切分，保留到下一张卡片
        parts = self.CARD_SPLIT.split(html)
        for chunk in parts[1:]:
            try:
                # 详情链接：a.thumb 或 a.infos 的 href
                href = ""
                m = re.search(r'<a class="thumb"[^>]*href="([^"]+)"', chunk)
                if not m:
                    m = re.search(r'<a class="infos"[^>]*href="([^"]+)"', chunk)
                if m:
                    href = m.group(1)
                if not href:
                    m = re.search(r'href="(https?://[^"]+)"', chunk)
                    href = m.group(1) if m else ""
                if not href:
                    continue
                href = urljoin(self.host, href)

                # 标题
                title = ""
                mt = re.search(r'<span class="title">(.*?)</span>', chunk, re.S)
                if mt:
                    title = re.sub(r"<[^>]+>", "", mt.group(1)).strip()
                if not title:
                    mt = re.search(r'aria-label="([^"]+)"', chunk)
                    title = mt.group(1).strip() if mt else ""
                if not title:
                    continue

                # 缩略图： data-src 优先，其次 src
                pic = ""
                mp = re.search(r'class="video-img[^"]*"[^>]*?data-src="([^"]+)"', chunk)
                if not mp:
                    mp = re.search(r'class="video-img[^"]*"[^>]*?src="([^"]+)"', chunk)
                if not mp:
                    mp = re.search(r'data-src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', chunk, re.I)
                if not mp:
                    mp = re.search(r'src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', chunk, re.I)
                if mp:
                    pic = mp.group(1)
                if pic.startswith("//"):
                    pic = "https:" + pic
                pic = urljoin(self.host, pic) if pic else ""

                # 角标： views / duration
                remark = ""
                mv = re.search(r'class="views-number[^"]*">.*?</i>\s*([\d\.]+[KMB]?)', chunk, re.S)
                md = re.search(r'class="notranslate duration[^"]*">([^<]+)<', chunk)
                parts_r = []
                if mv:
                    parts_r.append(mv.group(1).strip())
                if md:
                    parts_r.append(md.group(1).strip())
                if parts_r:
                    remark = " | ".join(parts_r)

                vid = href
                if vid in seen:
                    continue
                seen.add(vid)
                out.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })
            except Exception:
                continue
        return out

    # ---------------- 详情 ----------------

    @staticmethod
    def _norm_ids(ids):
        """法则35：ids 可能是 list / str / int / bytes"""
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
        page_url = raw
        if not page_url.startswith("http"):
            page_url = urljoin(self.host, page_url)
        try:
            html = self._fetch_html(page_url)
            if not html or len(html) < 500:
                return self._skeleton(raw)

            # 标题
            title = ""
            mt = re.search(r'<meta property="og:title" content="([^"]+)"', html)
            if mt:
                title = mt.group(1).strip()
            if not title:
                mt = re.search(r"<title>(.*?)</title>", html, re.S)
                if mt:
                    title = re.sub(r"\s*-\s*xanimu\.one\s*$", "", mt.group(1)).strip()
            if not title:
                mt = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
                if mt:
                    title = re.sub(r"<[^>]+>", "", mt.group(1)).strip()

            # 封面 poster
            pic = ""
            mp = re.search(r'var poster="([^"]+)"', html)
            if mp:
                pic = mp.group(1)
            if not pic:
                mp = re.search(r'<meta property="og:image" content="([^"]+)"', html)
                if mp:
                    pic = mp.group(1)

            # 简介
            content = ""
            mc = re.search(r'<meta name="description" content="([^"]*)"', html)
            if mc:
                content = mc.group(1).strip()

            # 播放地址： 明文 JS 变量 videoHigh / videoLow
            play_urls = []
            for var in ("videoHigh", "videoLow"):
                # var videoHigh="..."  或  var videoHigh;videoHigh="..."
                for pat in (
                    r'var\s+%s\s*=\s*"([^"]+)"' % var,
                    r'%s\s*=\s*"([^"]+)"' % var,
                ):
                    mm = re.search(pat, html)
                    if mm and mm.group(1).startswith("http"):
                        play_urls.append(mm.group(1))
                        break

            if not play_urls:
                # 兜底：抓页面里任意带 verify 的 mp4 直链
                play_urls = re.findall(r'https?://[^"\']+?\.mp4\?verify=[^"\']+', html)

            # 去重保序（法则34：禁用 set 打乱顺序）
            uniq = []
            seen = set()
            for u in play_urls:
                if u not in seen:
                    seen.add(u)
                    uniq.append(u)

            if not uniq:
                self.log({"detail": "no_play_url", "url": page_url})
                return self._skeleton(raw, title, pic)

            # 线路：高清 / 标清；单集格式 名称$地址，ID 内禁止裸 $（此处地址含 %2B 等，安全）
            eps = []
            names = ["高清", "标清"]
            for i, u in enumerate(uniq):
                nm = names[i] if i < len(names) else ("线路%d" % (i + 1))
                eps.append(nm + "$" + u)
            play_from = "XAnimu"
            play_url = "#".join(eps)

            vod = {
                "vod_id": raw,
                "vod_name": title or "未知标题",
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_content": content,
                "vod_play_from": play_from,
                "vod_play_url": play_url,
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"detail": "exception", "ids": raw, "error": str(e)})
            return self._skeleton(raw)

    # ---------------- 搜索 ----------------

    def searchContent(self, key, quick, pg="1"):
        page = str(pg or "1")
        try:
            kw = quote(str(key or "").strip(), safe="")
            if not kw:
                return {"list": [], "page": int(page)}
            if page == "1":
                url = self.host + self.lang + "/?s=" + kw
            else:
                slug = quote("有关详细信息，请查看此页面。", safe="")
                url = self.host + self.lang + "/" + slug + "/page/" + page + "/?s=" + kw
            html = self._fetch_html(url)
            vlist = self._parse_list(html)
            return {"list": vlist, "page": int(page)}
        except Exception as e:
            self.log({"search": "exception", "key": key, "error": str(e)})
            return {"list": [], "page": int(page)}

    # ---------------- 播放 ----------------

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id) if id else ""
        if "$" in play_url:
            p = play_url.split("$", 1)
            if len(p) == 2:
                play_url = p[1]
        if play_url and not play_url.startswith("http"):
            if play_url.startswith("//"):
                play_url = "https:" + play_url
            else:
                play_url = "https://" + play_url

        if not play_url:
            return {"parse": 0, "url": "", "header": self.headers}

        # mp4 直链（带 verify 签名），直接返回
        if re.search(r"\.mp4(\?|$)", play_url, re.I) or ".m3u8" in play_url.lower():
            return {
                "parse": 0,
                "url": play_url,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/",
                },
            }

        # 否则把 id 当作详情页URL，回抓一次拿直链
        try:
            if not play_url.startswith("http"):
                play_url = urljoin(self.host, play_url)
            html = self._fetch_html(play_url)
            for var in ("videoHigh", "videoLow"):
                mm = re.search(r'var\s+%s\s*=\s*"([^"]+)"' % var, html)
                if mm and mm.group(1).startswith("http"):
                    return {
                        "parse": 0, "url": mm.group(1),
                        "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/"},
                    }
        except Exception as e:
            self.log({"play": "exception", "id": id, "error": str(e)})

        return {
            "parse": 1,
            "url": play_url,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
            },
        }

    # ---------------- 推荐 ----------------

    def recommendContent(self, ids, pg):
        try:
            vid = self._norm_ids(ids)
            if not vid:
                return {"list": []}
            html = self._fetch_html(vid if vid.startswith("http") else urljoin(self.host, vid))
            if not html:
                return {"list": []}
            vlist = self._parse_list(html)
            norm = vid.rstrip("/")
            out = []
            for v in vlist:
                if v.get("vod_id", "").rstrip("/") == norm:
                    continue
                out.append(v)
            return {"list": out[:24]}
        except Exception as e:
            self.log({"recommend": "exception", "error": str(e)})
            return {"list": []}

    # ---------------- 工具 ----------------

    def _fetch_html(self, url):
        """统一抓取，判空 + 编码容错（法则：fetch 失败返回 None）"""
        try:
            r = self.fetch(url, headers=self.headers, timeout=15)
            if not r or getattr(r, "status_code", 0) != 200:
                self.log({"fetch": "failed", "url": url, "status": getattr(r, "status_code", None)})
                return ""
            return getattr(r, "text", "") or ""
        except Exception as e:
            self.log({"fetch": "exception", "url": url, "error": str(e)})
            return ""