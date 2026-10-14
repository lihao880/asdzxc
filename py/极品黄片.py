# coding=utf-8
# !/usr/bin/python
"""
FongMi / TVBox T3 (type=3) 爬虫源
站点：极品黄片（jphpia）  主域 https://en.jphpia.wiki
类型：成人影视聚合站（SSR 完整 HTML，无需 SPA/API）
说明：
- 反爬：Cloudflare（盒子原生 self.fetch 通常直接通过；本机测试用 requests/curl 亦可）。
- 分类页：/category/{tid}/ 第一页；翻页 /category/{tid}/{page}/（tid 形如 cateN 或 video）。
        列表卡 <article class="seo-media-card">（class 恰为该值），
        广告卡 <article class="seo-media-card seo-ad-card">（class 多出 seo-ad-card）→ 正则天然排除。
        卡内：a.seo-card-cover href="/video/{ID}/" title；img data-cover=真实封面（lazyload）；
              span.seo-duration 时长；h3>a 标题；p><span>作者</span><i></i><span>NN 次播放</span>。
        分页 nav.seo-pagination，pagecount = 页码链接中最大数字。
- 搜索：/search/{urlencode(key)}/{page}/（GET），返回结构同分类页。
- 详情：/video/{ID}/，<div id="article-videos" data-url="/video/日期/夹/hash.m3u8"
        data-cdnline="https://d32bg2g0w9aqg4.cloudfront.net"> → 播放地址 = data-cdnline + data-url。
        单线路单集。h1 标题、og:image 封面。
- 播放：master m3u8 为 AES-128（#EXT-X-KEY URI="/keyhome/video.key" 相对，会对 m3u8 所在 CDN 主机解析），
        CDN 未启用 auth（无 token），TS 分片为绝对 URL。故 parse:0 直链即可播放，
        header 带 UA + Referer=主域 保险。
最后验证：2026-09-30
"""
import sys
import re
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
    siteName = "极品黄片"
    MAIN = "https://en.jphpia.wiki"
    UA = ("Mozilla/5.0 (Linux; Android 14; 22127RK46C/Pixel5) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    # 首页分类（静态硬编码，零网络；tid 直接作为 /category/{tid}/ 路径段）
    _CATE = [
        {"type_name": "短视频", "type_id": "video"},
        {"type_name": "精选Vlog", "type_id": "cate4"},
        {"type_name": "玩偶姐姐", "type_id": "cate17"},
        {"type_name": "桃桃学姐", "type_id": "cate7"},
        {"type_name": "辛尤里", "type_id": "cate13"},
        {"type_name": "糖心淑怡", "type_id": "cate68"},
        {"type_name": "吴梦梦", "type_id": "cate72"},
        {"type_name": "萌白酱", "type_id": "cate127"},
        {"type_name": "探花约炮", "type_id": "cate141"},
        {"type_name": "COS女神", "type_id": "cate145"},
        {"type_name": "台湾SWAG", "type_id": "cate146"},
        {"type_name": "台湾JVID", "type_id": "cate147"},
        {"type_name": "自拍-探花", "type_id": "cate151"},
        {"type_name": "自拍-网红流出", "type_id": "cate159"},
        {"type_name": "自拍-反差婊", "type_id": "cate172"},
        {"type_name": "自拍-明星换脸", "type_id": "cate157"},
        {"type_name": "乱伦-母子", "type_id": "cate174"},
        {"type_name": "乱伦-家庭", "type_id": "cate180"},
        {"type_name": "乱伦-兄妹", "type_id": "cate179"},
        {"type_name": "麻豆传媒", "type_id": "cate183"},
        {"type_name": "皇家华人", "type_id": "cate186"},
        {"type_name": "天美传媒", "type_id": "cate189"},
        {"type_name": "兔子先生", "type_id": "cate190"},
        {"type_name": "果冻传媒", "type_id": "cate191"},
        {"type_name": "星空传媒", "type_id": "cate194"},
        {"type_name": "精东传媒", "type_id": "cate195"},
        {"type_name": "日韩AV", "type_id": "cate198"},
        {"type_name": "AV-中文字幕", "type_id": "cate200"},
        {"type_name": "AV-无码破解", "type_id": "cate205"},
        {"type_name": "三上悠亚", "type_id": "cate209"},
        {"type_name": "波多野结衣", "type_id": "cate201"},
        {"type_name": "欧美超模", "type_id": "cate214"},
        {"type_name": "VIXEN", "type_id": "cate220"},
        {"type_name": "Blacked RAW", "type_id": "cate215"},
        {"type_name": "福利姬", "type_id": "cate222"},
        {"type_name": "经典三级", "type_id": "cate223"},
        {"type_name": "痴汉偷拍", "type_id": "cate229"},
        {"type_name": "精品厕拍", "type_id": "cate228"},
    ]

    # ---------- 生命周期 ----------
    def init(self, extend=""):
        self.extend = extend
        return

    def getName(self):
        return self.siteName

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return (".m3u8" in u) or (".mp4" in u)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ---------- HTTP ----------
    def _headers(self, referer=None):
        h = {
            "User-Agent": self.UA,
            "Referer": referer or (self.MAIN + "/"),
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        return h

    def _get(self, url, referer=None):
        try:
            rsp = self.fetch(url, headers=self._headers(referer))
            if rsp is None:
                return ""
            return rsp.text or ""
        except Exception:
            return ""

    # ---------- 列表解析 ----------
    def _parse_cards(self, html):
        vods = []
        if not html:
            return vods
        # 广告卡 class="seo-media-card seo-ad-card"，正常卡恰为 class="seo-media-card"
        for m in re.finditer(r'<article class="seo-media-card">(.*?)</article>', html, re.S):
            seg = m.group(1)
            hm = re.search(r'href="/video/(\d+)/"', seg)
            if not hm:
                continue
            vid = hm.group(1)
            tm = re.search(r'title="([^"]*)"', seg)
            title = tm.group(1) if tm else ""
            if not title:
                h3 = re.search(r'<h3><a[^>]*>(.*?)</a>', seg, re.S)
                title = re.sub(r'<[^>]+>', '', h3.group(1)).strip() if h3 else vid
            cm = re.search(r'data-cover="([^"]+)"', seg)
            cover = cm.group(1) if cm else ""
            dm = re.search(r'seo-duration">([^<]+)<', seg)
            dur = dm.group(1).strip() if dm else ""
            pm = re.search(r'<p>\s*<span>(.*?)</span>\s*<i></i>\s*<span>(.*?)</span>', seg, re.S)
            if pm:
                author = re.sub(r'<[^>]+>', '', pm.group(1)).strip()
                plays = re.sub(r'<[^>]+>', '', pm.group(2)).strip()
                remark = (author + " · " + plays).strip(" ·") if (author or plays) else dur
            else:
                remark = dur
            vods.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": cover,
                "vod_remarks": remark or dur,
            })
        return vods

    def _parse_pagecount(self, html, cur):
        try:
            nav = re.search(r'seo-pagination.*?</nav>', html or "", re.S)
            if not nav:
                return cur
            nums = [int(x) for x in re.findall(r'/(\d+)/"', nav.group(0))]
            nums += [int(x) for x in re.findall(r'>(\d+)<', nav.group(0))]
            return max(nums) if nums else cur
        except Exception:
            return cur

    # ---------- 首页 ----------
    def homeContent(self, filter):
        return {"class": self._CATE, "filters": {}}

    def getHomeContent(self, filter=True):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._get(self.MAIN + "/category/cate4/")
        return {"list": self._parse_cards(html)}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        if page < 1:
            page = 1
        base = self.MAIN + "/category/" + str(tid) + "/"
        url = base if page == 1 else base + str(page) + "/"
        html = self._get(url)
        vods = self._parse_cards(html)
        pagecount = self._parse_pagecount(html, page)
        if page >= pagecount and vods:
            pagecount = page
        return {
            "list": vods,
            "page": page,
            "pagecount": pagecount,
            "limit": len(vods) if vods else 60,
            "total": pagecount * (len(vods) if vods else 60),
        }

    # ---------- 详情 ----------
    def _norm_id(self, ids):
        if isinstance(ids, (list, tuple)):
            v = ids[0] if ids else ""
        else:
            v = ids
        v = str(v).strip()
        m = re.search(r'/video/(\d+)/', v)
        if m:
            return m.group(1)
        m = re.search(r'(\d+)', v)
        return m.group(1) if m else v

    def detailContent(self, ids):
        vid = self._norm_id(ids)
        durl = self.MAIN + "/video/" + vid + "/"
        html = self._get(durl, referer=self.MAIN + "/")

        title = vid
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        else:
            m = re.search(r'<title>(.*?)</title>', html, re.S)
            if m:
                title = m.group(1).split(' - ')[0].strip()

        pic = ""
        m = re.search(r'og:image"\s+content="([^"]+)"', html)
        if m:
            pic = m.group(1)

        desc = ""
        m = re.search(r'name="description"\s+content="([^"]*)"', html)
        if m:
            desc = m.group(1).strip()

        play_url = ""
        m = re.search(r'id="article-videos"\s+data-url="([^"]+)"\s+data-cdnline="([^"]+)"', html)
        if m:
            raw, cdn = m.group(1), m.group(2).rstrip('/')
            if raw.startswith('http'):
                play_url = raw
            else:
                play_url = cdn + ('' if raw.startswith('/') else '/') + raw

        # 骨架兜底：即使解析不到直链也不返回空 list，交由 playerContent 兜底
        if play_url:
            vod_from = "极品黄片"
            vod_url = "正片$" + play_url
        else:
            vod_from = "极品黄片"
            vod_url = "正片$" + vid  # playerContent 会用 vid 重取详情页

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": vod_from,
            "vod_play_url": vod_url,
        }
        return {"list": [vod]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        url = str(id).strip()
        # id 已是 m3u8 直链
        if not url.lower().startswith("http"):
            # 兜底：id 是视频编号，重取详情页解析直链
            vid = self._norm_id(url)
            html = self._get(self.MAIN + "/video/" + vid + "/", referer=self.MAIN + "/")
            m = re.search(r'id="article-videos"\s+data-url="([^"]+)"\s+data-cdnline="([^"]+)"', html)
            if m:
                raw, cdn = m.group(1), m.group(2).rstrip('/')
                url = raw if raw.startswith('http') else cdn + ('' if raw.startswith('/') else '/') + raw
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": {
                "User-Agent": self.UA,
                "Referer": self.MAIN + "/",
            },
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        if page < 1:
            page = 1
        enc = quote(str(key), safe='')
        base = self.MAIN + "/search/" + enc + "/"
        url = base if page == 1 else base + str(page) + "/"
        html = self._get(url)
        return {"list": self._parse_cards(html), "page": page}

    # ---------- 推荐 ----------
    def recommendContent(self, ids, pg=1):
        return {"list": []}

    def localProxy(self, param):
        return [200, "application/octet-stream", {}, b""]
