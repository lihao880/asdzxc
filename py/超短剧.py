# coding: utf-8
# 超短剧 (tvriyv.shanekids.com) —— AI 生成成人短剧聚合站 T3(type=3) 爬虫源
# 型态：SSR 静态 HTML 站；串流域 stream.megafile.media；m3u8 为 AES-128(相对 KEY/分片)直链
# 播放：详情页 <script id="player-data"> 内含全集 m3u8，KEY/分片相对同 CDN，直接 parse:0 即可
import sys, re, json
from urllib.parse import quote, unquote

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def log(self, *a, **k): pass

# ============ 换站只改这两行 ============
SITE_NAME = "超短剧"
HOST = "https://tvriyv.shanekids.com"
# =======================================

UA = "Mozilla/5.0 (Linux; Android 14; 22127RK46C/Pixel5) Chrome/120 Mobile"

# 静态分类：/explore 为全部(分页)，其余为 /tag/{标签}(单页 ~24 部)
TAGS = ["科幻", "都市", "高颜值", "乡村", "乱伦", "仙侠", "剧情", "古风", "同学",
        "同性", "后宫", "大女主", "大男主", "奇幻", "女神", "校园", "熟女", "玄幻",
        "现代", "甜宠", "禁忌", "穿越", "系统", "绿帽", "职场", "脑洞", "虐恋",
        "超能力", "逆袭"]


class Spider(BaseSpider):
    def __init__(self):
        self.host = HOST
        self.headers = {
            "User-Agent": UA,
            "Referer": HOST + "/",
        }
        self.classes = [{"type_id": "explore", "type_name": "最新"}]
        for t in TAGS:
            self.classes.append({"type_id": "tag:" + t, "type_name": t})

    # ---------- 基础 ----------
    def getName(self):
        return SITE_NAME

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return u.endswith(".m3u8") or u.endswith(".mp4") or ".m3u8" in u

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ---------- 网络 ----------
    def _get(self, url):
        try:
            r = self.fetch(url, headers=self.headers)
            if r is None:
                return ""
            return getattr(r, "text", "") or ""
        except Exception as e:
            self.log("get fail %s: %s" % (url, e))
            return ""

    # ---------- 解析卡片 ----------
    def _parse_cards(self, html):
        vods = []
        if not html:
            return vods
        # 以 <a class="card" 分块
        blocks = re.split(r'<a\s+class="card"', html)
        for b in blocks[1:]:
            b = b[:1200]  # 单卡范围足够
            m_href = re.search(r'href="/drama/([^"]+)"', b)
            if not m_href:
                continue
            slug = m_href.group(1)
            m_title = re.search(r'title="([^"]*)"', b)
            title = (m_title.group(1) if m_title else "").strip()
            if not title:
                m_ct = re.search(r'class="card-title">([^<]+)<', b)
                title = (m_ct.group(1).strip() if m_ct else slug)
            m_pic = re.search(r'<img[^>]+src="([^"]+)"', b)
            pic = m_pic.group(1) if m_pic else ""
            m_eps = re.search(r'class="card-eps">\s*([^<]+?)\s*<', b)
            eps = m_eps.group(1).strip() if m_eps else ""
            vods.append({
                "vod_id": slug,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": eps,
            })
        return vods

    # ---------- 首页 ----------
    def homeContent(self, filter):
        # 零网络，仅返回本地分类
        return {"class": self.classes, "filters": {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._get(self.host + "/explore?page=1")
        return {"list": self._parse_cards(html)}

    def getHomeVideoContent(self):
        return self.homeVideoContent()

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        tid = str(tid or "explore")

        if tid.startswith("tag:"):
            tag = tid[4:]
            url = "%s/tag/%s" % (self.host, quote(tag))
            html = self._get(url)
            vods = self._parse_cards(html)
            # tag 页为单页，无分页
            return {"list": vods, "page": page, "pagecount": 1,
                    "limit": len(vods) or 24, "total": len(vods)}

        # explore 全部（分页）
        url = "%s/explore?page=%d" % (self.host, page)
        html = self._get(url)
        vods = self._parse_cards(html)
        # 探测是否有下一页：页面内含 page=N 链接，取最大值判断
        nums = [int(n) for n in re.findall(r'[?&]page=(\d+)', html)]
        has_next = any(n > page for n in nums) if nums else False
        pagecount = page + 1 if has_next else page
        return {"list": vods, "page": page, "pagecount": pagecount,
                "limit": len(vods) or 30, "total": pagecount * (len(vods) or 30)}

    def getCategoryContent(self, tid, pg, filter, extend):
        return self.categoryContent(tid, pg, filter, extend)

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

    def detailContent(self, ids):
        slug = self._norm_ids(ids)
        if not slug:
            return {"list": []}
        # slug 可能带前缀 /drama/
        slug = slug.replace("/drama/", "").strip("/")
        url = "%s/drama/%s" % (self.host, slug)
        html = self._get(url)

        title = ""
        m = re.search(r'<h1[^>]*class="watch-title"[^>]*>([^<]+)</h1>', html)
        if m:
            title = m.group(1).strip()
        if not title:
            m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
            if m:
                title = m.group(1).split("-")[0].strip()

        desc = ""
        m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html)
        if m:
            desc = m.group(1).strip()

        # 标签
        tags = re.findall(r'href="/tag/([^"]+)"', html)
        tag_names = []
        for t in tags:
            t = unquote(t)
            if t and t not in tag_names:
                tag_names.append(t)

        # 播放数据：<script id="player-data" ...>[...]</script>
        eps = []
        m = re.search(r'<script[^>]+id="player-data"[^>]*>(\[.*?\])</script>',
                      html, re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                for it in data:
                    seq = str(it.get("seq") or "").strip()
                    src = str(it.get("src") or "").strip()
                    if src and "$" not in src and "#" not in src:
                        eps.append("第%s集$%s" % (seq or (len(eps) + 1), src))
            except Exception as e:
                self.log("player-data parse fail: %s" % e)

        # 兜底：直接从 ep-btn data-src 提取
        if not eps:
            srcs = re.findall(r'class="ep-btn"[^>]+data-src="([^"]+playlist\.m3u8)"', html)
            for i, src in enumerate(srcs, 1):
                if "$" not in src and "#" not in src:
                    eps.append("第%d集$%s" % (i, src))

        vod = {
            "vod_id": slug,
            "vod_name": title or slug,
            "vod_pic": "",
            "vod_remarks": ("%d 集" % len(eps)) if eps else "",
            "vod_content": desc,
            "vod_tag": ",".join(tag_names),
            "vod_play_from": SITE_NAME,
            "vod_play_url": "#".join(eps) if eps else "",
        }
        if not vod["vod_play_url"]:
            # 骨架兜底：禁止 play_from 有值而 play_url 为空
            vod["vod_play_url"] = "第1集$" + url
        return {"list": [vod]}

    def getDetailContent(self, ids):
        return self.detailContent(ids)

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        url = "%s/search?q=%s" % (self.host, quote(str(key or "")))
        html = self._get(url)
        return {"list": self._parse_cards(html), "page": 1,
                "pagecount": 1, "limit": 30, "total": 30}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def getSearchContent(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        u = str(id or "").strip()
        # m3u8 为 AES-128(相对 KEY/分片)，KEY/分片均在同 CDN 相对路径，
        # 直接把 CDN 原始 m3u8 交给播放器，其以 CDN 为 base 解析相对 KEY/分片，无需代理
        if u.startswith("http"):
            return {"parse": 0, "url": u,
                    "header": {"User-Agent": UA}}
        # 兜底：id 为详情页 URL，则重新解析取第一集
        if "/drama/" in u:
            d = self.detailContent(u.split("/drama/")[-1])
            lst = d.get("list") or []
            if lst:
                first = (lst[0].get("vod_play_url") or "").split("#")[0]
                real = first.split("$")[-1]
                if real.startswith("http"):
                    return {"parse": 0, "url": real, "header": {"User-Agent": UA}}
        return {"parse": 1, "url": u, "header": {"User-Agent": UA}}

    def getPlayerContent(self, flag, id, vipFlags):
        return self.playerContent(flag, id, vipFlags)

    def localProxy(self, param):
        return None
