# coding: utf-8
# ============================================================
# 站点名称 : 葡萄仙子
# 主域名   : https://aolzca.ptxz9.top
# 备用域名 : https://apq.xrbsp1.com/n/ (永久发布页) / https://aje.xrbsp1.com/g/ (友链页)
# 架构     : MacCMS 数据层 + WordPress Koji 主题外壳（纯 HTML，无 API/无加密）
# 分类     : /vodtype/{tid}.html      分页 /vodtype/{tid}-{pg}.html
# 详情=播放: /{vod_id}.html           DPlayer 脚本内 rawUrl 明文 m3u8
# 搜索     : /s/{urlencode(key)}.html 分页 /s/{key}/page/{pg}.html
# 首页推荐 : /label/new.html          日榜 /label/hot_day.html
# 特殊说明 : 封面为 data-src 懒加载；标题尾部带 " new" 需清洗；站点无筛选区块
# 最后验证 : 2026-08-28
# 来源     : 用户提供 https://aolzca.ptxz9.top/ptxz/
# ============================================================

import re
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, unquote, urljoin, urlparse

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    # ------------------------------------------------------------
    # 初始化（零网络）
    # ------------------------------------------------------------
    def __init__(self):
        self.site_name = "葡萄仙子"
        self.host = "https://aolzca.ptxz9.top"
        self.backup_hosts = [
            "https://aolzca.ptxz9.top",
            "https://apq.xrbsp1.com",
            "https://aje.xrbsp1.com",
        ]
        self._cached_host = None
        self.extend = ""

        self.classes = [
            {"type_id": "20", "type_name": "熟母少妇"},
            {"type_id": "21", "type_name": "网红直播"},
            {"type_id": "22", "type_name": "自拍偷拍"},
            {"type_id": "23", "type_name": "强奸乱伦"},
            {"type_id": "24", "type_name": "高清国产"},
            {"type_id": "25", "type_name": "韩国专区"},
            {"type_id": "26", "type_name": "日本有码"},
            {"type_id": "27", "type_name": "日本无码"},
            {"type_id": "28", "type_name": "欧美情色"},
            {"type_id": "29", "type_name": "动漫卡通"},
            {"type_id": "30", "type_name": "三级伦理"},
            {"type_id": "new", "type_name": "最新上传"},
            {"type_id": "hot_day", "type_name": "日排行榜"},
            {"type_id": "hot_week", "type_name": "周排行榜"},
            {"type_id": "hot_month", "type_name": "月排行榜"},
            {"type_id": "hot", "type_name": "总排行榜"},
        ]
        # 站点无筛选入口，全部返回空数组（禁止伪造筛选）
        self.filters = {str(c["type_id"]): [] for c in self.classes}

        self.label_ids = {"new", "hot", "hot_day", "hot_week", "hot_month"}

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def getName(self):
        return self.site_name

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 零网络：仅记录 extend
        self.extend = extend or ""
        return {}

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4|mkv|flv|avi|ts)(\?|$)", str(url or ""), re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        """释放资源：关闭 session、清空缓存"""
        try:
            self._cached_host = None
            sess = getattr(self, "session", None)
            if sess is not None:
                try:
                    sess.close()
                except Exception:
                    pass
        except Exception:
            pass
        return {}

    # ------------------------------------------------------------
    # 域名与请求
    # ------------------------------------------------------------
    def getHost(self):
        """动态域名健康检查（只动态域名，不动态分类）"""
        if self._cached_host:
            return self._cached_host
        for h in self.backup_hosts:
            try:
                r = self.fetch(h + "/", headers=self.headers, timeout=8, verify=False)
                if r and getattr(r, "status_code", 0) == 200 and "vodtype" in (r.text or ""):
                    self._cached_host = h.rstrip("/")
                    return self._cached_host
            except Exception:
                continue
        self._cached_host = self.host
        return self._cached_host

    def _fetch_html(self, url, retry=1):
        """带重试的 HTML 获取"""
        for i in range(retry + 1):
            try:
                r = self.fetch(url, headers=self.headers, timeout=15, verify=False)
                if r is None:
                    continue
                if getattr(r, "status_code", 0) != 200:
                    continue
                try:
                    r.encoding = "utf-8"
                except Exception:
                    pass
                text = r.text or ""
                if text:
                    return text
            except Exception as e:
                self.log("fetch fail(%d): %s %s" % (i, url, str(e)[:120]))
        return ""

    # ------------------------------------------------------------
    # 列表解析（多级选择器兜底）
    # ------------------------------------------------------------
    def _clean_title(self, t):
        t = re.sub(r"<[^>]+>", "", str(t or ""))
        t = t.replace("&amp;", "&").replace("&nbsp;", " ").replace("&quot;", '"')
        t = re.sub(r"\s*\bnew\b\s*$", "", t, flags=re.I)
        return t.strip()

    def _parse_video_list(self, html):
        """解析 article.preview 卡片列表；单条异常不中断"""
        items = []
        seen = set()
        if not html:
            return items

        blocks = re.findall(r'<article[^>]*class="[^"]*preview[^"]*"[\s\S]*?</article>', html)
        if not blocks:
            # 兜底1：直接抓 preview-image 锚点 + 相邻标题
            blocks = re.findall(r'<div class="preview-wrapper"[\s\S]*?</div></div></div>', html)

        for b in blocks:
            try:
                m_id = re.search(r'href="/(\d+)\.html"', b)
                if not m_id:
                    m_id = re.search(r'/(\d+)\.html', b)
                if not m_id:
                    continue
                vid = m_id.group(1)
                if vid in seen:
                    continue

                # 标题：三级兜底
                title = ""
                mt = re.search(r'class="preview-title"[^>]*>\s*<a[^>]*>([\s\S]*?)</a>', b)
                if mt:
                    title = self._clean_title(mt.group(1))
                if not title:
                    mt = re.search(r'<h2[^>]*>([\s\S]*?)</h2>', b)
                    if mt:
                        title = self._clean_title(mt.group(1))
                if not title:
                    mt = re.search(r'alt="([^"]+)"', b)
                    if mt:
                        title = self._clean_title(mt.group(1))
                if not title:
                    continue

                # 封面：data-src 优先（懒加载），再 src / srcset
                pic = ""
                mp = re.search(r'data-src="([^"]+)"', b) or \
                     re.search(r'data-srcset="([^"\s]+)', b) or \
                     re.search(r'<img[^>]+src="([^"]+)"', b)
                if mp:
                    pic = mp.group(1).strip()
                if pic and pic.startswith("//"):
                    pic = "https:" + pic
                elif pic and not pic.startswith("http"):
                    pic = urljoin(self.getHost() + "/", pic)

                # 角标：所属分类名
                remark = ""
                mr = re.search(r'rel="category tag">([^<]+)</a>', b)
                if mr:
                    remark = self._clean_title(mr.group(1))

                seen.add(vid)
                items.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })
            except Exception:
                continue
        return items

    def _parse_page_count(self, html, cur):
        """依据 Next Page 判断是否有下一页"""
        try:
            cur = int(cur)
        except Exception:
            cur = 1
        if html and re.search(r'class="link-pagination[^"]*only-next|Next Page', html):
            return max(cur + 1, cur)
        return cur if cur > 1 else 1

    # ------------------------------------------------------------
    # 首页
    # ------------------------------------------------------------
    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        host = self.getHost()
        html = self._fetch_html(host + "/label/new.html")
        items = self._parse_video_list(html)
        if not items:
            html = self._fetch_html(host + "/ptxz/")
            items = self._parse_video_list(html)
        if not items:
            html = self._fetch_html(host + "/cn/home/web/")
            items = self._parse_video_list(html)
        return {"list": items[:36]}

    # ------------------------------------------------------------
    # 分类列表
    # ------------------------------------------------------------
    def _parse_extend(self, extend):
        """extend 多格式兼容：dict / json / {k=v} / k=v"""
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            s = extend.strip()
            try:
                v = json.loads(s)
                if isinstance(v, dict):
                    return v
            except Exception:
                pass
            s = s.strip("{}")
            out = {}
            for part in re.split(r"[,&]", s):
                if "=" in part:
                    k, v = part.split("=", 1)
                    out[k.strip()] = v.strip()
            return out
        return {}

    def _cat_url(self, tid, pg):
        host = self.getHost()
        tid = str(tid or "20")
        pg = str(pg or "1")
        if tid in self.label_ids:
            if pg == "1":
                return "%s/label/%s.html" % (host, tid)
            return "%s/label/%s/page/%s.html" % (host, tid, pg)
        if pg == "1":
            return "%s/vodtype/%s.html" % (host, tid)
        return "%s/vodtype/%s-%s.html" % (host, tid, pg)

    def categoryContent(self, tid, pg, filter, extend):
        ext = self._parse_extend(extend)
        # 站点无筛选，但仍兼容 extend 传入 class/cateId 覆盖分类
        real_tid = str(ext.get("class") or ext.get("cateId") or ext.get("type_id") or tid or "20")
        page = str(pg or "1")

        url = self._cat_url(real_tid, page)
        html = self._fetch_html(url)
        items = self._parse_video_list(html)

        # 分页兜底：label 类翻页失败时退回 vodtype 形式
        if not items and page != "1" and real_tid in self.label_ids:
            html = self._fetch_html("%s/label/%s.html" % (self.getHost(), real_tid))
            items = self._parse_video_list(html)

        pagecount = self._parse_page_count(html, page)
        limit = len(items) or 36
        return {
            "list": items,
            "page": int(page) if str(page).isdigit() else 1,
            "pagecount": pagecount,
            "limit": limit,
            "total": pagecount * limit,
        }

    # ------------------------------------------------------------
    # 详情（详情页即播放页）
    # ------------------------------------------------------------
    def _extract_play_url(self, html, page_url):
        """从 DPlayer 脚本提取 m3u8/mp4 直链，多级兜底"""
        if not html:
            return ""
        pats = [
            r"rawUrl\s*=\s*['\"]([^'\"]+)['\"]",
            r"vod_play_url\s*=\s*['\"](https?://[^'\"]+)['\"]",
            r"url\s*:\s*['\"](https?://[^'\"]+\.(?:m3u8|mp4)[^'\"]*)['\"]",
            r"\"url\"\s*:\s*\"(https?:[^\"]+?\.(?:m3u8|mp4)[^\"]*)\"",
            r"(https?://[^\s'\"<>\\]+\.m3u8(?:\?[^\s'\"<>]*)?)",
            r"(https?://[^\s'\"<>\\]+\.mp4(?:\?[^\s'\"<>]*)?)",
        ]
        for p in pats:
            m = re.search(p, html, re.I)
            if m:
                u = m.group(1).replace("\\/", "/").strip()
                if u.startswith("//"):
                    u = "https:" + u
                if u.startswith("http"):
                    return u
        # 兜底：iframe 二级播放器
        mi = re.search(r'<iframe[^>]+src="([^"]+)"', html, re.I)
        if mi:
            sub = urljoin(page_url, mi.group(1))
            sub_html = self._fetch_html(sub)
            m = re.search(r"(https?://[^\s'\"<>\\]+\.(?:m3u8|mp4)[^\s'\"<>]*)", sub_html or "", re.I)
            if m:
                return m.group(1).replace("\\/", "/")
        return ""

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        raw = ids[0] if isinstance(ids, (list, tuple)) else ids
        raw = str(raw)
        # 兼容列表阶段附带字段： id|$|name|$|pic|$|remark
        ps = raw.split("|$|")
        vid = re.sub(r"\D", "", ps[0]) or ps[0]
        pre_name = ps[1] if len(ps) > 1 else ""
        pre_pic = ps[2] if len(ps) > 2 else ""
        pre_remark = ps[3] if len(ps) > 3 else ""

        host = self.getHost()
        page_url = "%s/%s.html" % (host, vid)
        html = self._fetch_html(page_url)

        title = pre_name
        mt = re.search(r'class="post-title"[^>]*>([\s\S]*?)</h1>', html or "")
        if mt:
            title = self._clean_title(mt.group(1)) or title
        if not title:
            mt = re.search(r"<title>([\s\S]*?)</title>", html or "")
            if mt:
                title = self._clean_title(mt.group(1))
        if not title:
            title = "视频" + str(vid)

        pic = pre_pic
        if not pic:
            mp = re.search(r'data-src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', html or "", re.I)
            if mp:
                pic = mp.group(1)

        play_url = self._extract_play_url(html, page_url)
        play_id = play_url if play_url else page_url

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": pre_remark,
            "vod_year": "",
            "vod_area": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": title,
            "vod_play_from": "葡萄仙子",
            "vod_play_url": "正片$" + play_id,
        }
        return {"list": [vod]}

    # ------------------------------------------------------------
    # 搜索（多路并发）
    # ------------------------------------------------------------
    def _search_urls(self, key, pg):
        host = self.getHost()
        k = quote(str(key or ""), safe="")
        pg = str(pg or "1")
        urls = []
        if pg == "1":
            urls.append("%s/s/%s.html" % (host, k))
        else:
            urls.append("%s/s/%s/page/%s.html" % (host, k, pg))
            urls.append("%s/s/%s.html" % (host, k))
        # 兼容表单形式
        urls.append("%s/s/index.html?wd=%s&page=%s" % (host, k, pg))
        return urls

    def searchContent(self, key, quick, pg="1"):
        pg = str(pg or "1")
        urls = self._search_urls(key, pg)
        results = []
        try:
            with ThreadPoolExecutor(max_workers=3) as ex:
                htmls = list(ex.map(self._fetch_html, urls))
        except Exception:
            htmls = [self._fetch_html(u) for u in urls]

        seen = set()
        for h in htmls:
            for it in self._parse_video_list(h):
                if it["vod_id"] in seen:
                    continue
                seen.add(it["vod_id"])
                results.append(it)
            if results and pg == "1":
                break  # 第一页命中即够，避免重复合并

        return {"list": results, "page": int(pg) if pg.isdigit() else 1}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ------------------------------------------------------------
    # 相关推荐（站点无推荐区，用日榜兜底）
    # ------------------------------------------------------------
    def recommendContent(self, ids=None, pg=1):
        try:
            cur = ""
            if ids:
                raw = ids[0] if isinstance(ids, (list, tuple)) else ids
                cur = re.sub(r"\D", "", str(raw).split("|$|")[0])
            host = self.getHost()
            html = self._fetch_html(host + "/label/hot_day.html")
            items = self._parse_video_list(html)
            if not items:
                items = self._parse_video_list(self._fetch_html(host + "/label/new.html"))
            out = [it for it in items if it["vod_id"] != cur]
            return {"list": out[:24]}
        except Exception as e:
            self.log("recommend fail: " + str(e)[:120])
            return {"list": []}

    # ------------------------------------------------------------
    # 播放
    # ------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags=None):
        pid = str(id or "")
        ua = self.headers.get("User-Agent", "")
        host = self.getHost()

        # 已是直链
        if pid.startswith("http") and re.search(r"\.m3u8(\?|$)", pid, re.I):
            return {"parse": 0, "url": self._m3u8_proxy_url(pid), "header": {"User-Agent": ua}}
        if pid.startswith("http") and re.search(r"\.(mp4|mkv|flv|ts)(\?|$)", pid, re.I):
            return {"parse": 0, "url": pid, "header": {"User-Agent": ua, "Referer": host + "/"}}

        # 播放页 / 纯数字 id → 抓取提取
        page_url = pid if pid.startswith("http") else "%s/%s.html" % (host, re.sub(r"\D", "", pid) or pid)
        html = self._fetch_html(page_url)
        real = self._extract_play_url(html, page_url)
        if real:
            if re.search(r"\.m3u8(\?|$)", real, re.I):
                return {"parse": 0, "url": self._m3u8_proxy_url(real), "header": {"User-Agent": ua}}
            return {"parse": 0, "url": real, "header": {"User-Agent": ua, "Referer": host + "/"}}

        # 兜底：交给壳端嗅探（补全 header）
        return {
            "parse": 1,
            "url": page_url,
            "header": {
                "User-Agent": ua,
                "Referer": host + "/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        }

    # ------------------------------------------------------------
    # m3u8 本地代理 + 广告分片自动过滤
    # ------------------------------------------------------------
    def _m3u8_proxy_url(self, url):
        try:
            base = self.getProxyUrl()
        except Exception:
            return url
        if not base:
            return url
        sep = "&" if "?" in base else "?"
        return base + sep + "type=m3u8&url=" + quote(str(url or ""), safe="")

    def localProxy(self, param):
        param = param or {}
        target = unquote(str(param.get("url", "") or ""))
        if not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]
        try:
            r = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")},
                           timeout=15, verify=False)
            if not r or getattr(r, "status_code", 0) != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            text = (getattr(r, "content", b"") or b"").decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log("m3u8 proxy error: " + str(e)[:120])
            return [500, "text/plain", b"m3u8 proxy error"]

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 主播放列表：子列表继续走代理
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for l in lines:
                if l.startswith("#"):
                    out.append(self._rewrite_tag(l, source_url))
                else:
                    child = urljoin(source_url, l)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parts = [p for p in urlparse(source_url).path.split("/") if p]
        content_root = "/" + "/".join(parts[:-1]) + "/" if len(parts) >= 2 else ""

        out = []
        pending = []
        removed = 0
        for l in lines:
            if l.startswith("#EXTINF"):
                pending = [l]
                continue
            if pending and l.startswith("#"):
                pending.append(l)
                continue
            if pending:
                media = urljoin(source_url, l)
                # 广告判定：分片不在正片目录，或命中广告关键词
                bad = False
                if content_root and content_root not in urlparse(media).path:
                    bad = True
                if re.search(r"(ad[sv]?[-_/]|advert|guanggao|/ad/)", media, re.I):
                    bad = True
                if bad:
                    removed += 1
                else:
                    out.extend(pending)
                    out.append(media)
                pending = []
                continue
            out.append(self._rewrite_tag(l, source_url))

        # 清理连续的 DISCONTINUITY 冗余标签
        final = []
        for l in out:
            if l == "#EXT-X-DISCONTINUITY" and (not final or final[-1] == "#EXT-X-DISCONTINUITY"):
                continue
            final.append(l)
        if removed:
            self.log("m3u8已过滤广告分片: %d" % removed)
        return "\n".join(final) + "\n"

    def _rewrite_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            return re.sub(r'URI="([^"]+)"',
                          lambda m: 'URI="' + urljoin(source_url, m.group(1)) + '"', line)
        if line and not line.startswith("#"):
            return urljoin(source_url, line)
        return line

    # ------------------------------------------------------------
    def siteInfo(self):
        return {
            "name": self.site_name,
            "host": self.host,
            "backup": self.backup_hosts,
            "publish": "https://apq.xrbsp1.com/n/",
            "type": "video",
            "verified": "2026-08-28",
        }

    def liveContent(self, url):
        return {}

    def action(self, action):
        return ""