# -*- coding: utf-8 -*-
"""
TVBox / CatVod 通用爬虫 —— 茶杯狐 chabeihu12.com
=================================================

适配站点: https://www.chabeihu12.com/  (茶杯狐 cupfox 官网镜像站)
站点内核: 苹果CMS(MacCMS) V10 衍生魔改皮肤 (mould=library)

数据结构要点
------------
1) 列表页   /frim/index{tid}.html        分类 1=电影 2=电视剧 3=综艺 4=动漫
              /frim/index{tid}-{pg}.html   分页
   条目块   <div class="module-item"> ... </div>
2) 搜索     POST /search.php  body: searchword=xxx
   条目块   <div class="module-search-item">
3) 详情页   /movie/index{vod_id}.html
   元信息   <h1 class="page-title">, .video-info-aux, .video-info-content
   播放列表 每个 <div class="module-blocklist"> 是一路, <li><a href="/play/{id}-{from}-{idx}.html">
             线路名从「播放节点列表」的 data-dropdown-value 按序取得
4) 播放页   /play/{vod_id}-{from}-{idx}.html
   直链     <script>var now="https://xxx/index.m3u8";</script>  (需带 Referer)

用法
----
TVBox 配置 (多仓单条 / 单仓):
    {
      "key": "chabeihu",
      "name": "茶杯狐",
      "type": 3,
      "api": "./spider/chabeihu.py",
      "searchable": 1,
      "quickSearch": 1,
      "filterable": 1,
      "ext": ""
    }

    说明: type=3 表示 Python 爬虫; 把本文件放进 TVBox 的 spider 目录
          /storage/emulated/0/Download/tvbox/spider/chabeihu.py
    ext 可选: 直接填新域名 "https://新域名.com" 即可换站, 无需改代码。

本地自测:
    python3 chabeihu.py          # 跑内置全链路自检

依赖: 只需要 requests (TVBox 内置)。若缺失自动降级 urllib, 不装也能跑。

免责: 站点为第三方影视聚合站, 域名可能随时变更; 本脚本仅做页面结构解析。
"""

import sys
import json
import re

try:
    import requests
    requests.packages.urllib3.disable_warnings()
except Exception:
    requests = None

try:
    from base.spider import Spider as BaseSpider  # TVBox 运行时注入
except ImportError:                                # 本地自检兜底
    class BaseSpider(object):
        pass

try:
    from urllib.parse import quote, unquote, urlencode
    from urllib.request import Request, urlopen
    from urllib.error import URLError
except ImportError:
    from urllib import quote, unquote, urlencode
    from urllib2 import Request, urlopen, URLError


# ============================================================================
# 站点常量
# ============================================================================
HOST = "https://www.chabeihu12.com"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

TIMEOUT = 15

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": HOST + "/",
}

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
]

FILTERS = [
    {"key": "tid", "name": "分类", "value": [
        {"n": "全部", "v": ""},
        {"n": "电影", "v": "1"},
        {"n": "电视剧", "v": "2"},
        {"n": "综艺", "v": "3"},
        {"n": "动漫", "v": "4"},
    ]},
    {"key": "area", "name": "地区", "value": [
        {"n": "全部", "v": ""},
        {"n": "大陆", "v": "大陆"},
        {"n": "香港", "v": "香港"},
        {"n": "台湾", "v": "台湾"},
        {"n": "美国", "v": "美国"},
        {"n": "韩国", "v": "韩国"},
        {"n": "日本", "v": "日本"},
        {"n": "英国", "v": "英国"},
        {"n": "法国", "v": "法国"},
        {"n": "泰国", "v": "泰国"},
        {"n": "印度", "v": "印度"},
        {"n": "其它", "v": "其它"},
    ]},
    {"key": "year", "name": "年份", "value": [
        {"n": "全部", "v": ""},
        {"n": "2026", "v": "2026"},
        {"n": "2025", "v": "2025"},
        {"n": "2024", "v": "2024"},
        {"n": "2023", "v": "2023"},
        {"n": "2022", "v": "2022"},
        {"n": "2021", "v": "2021"},
        {"n": "2020", "v": "2020"},
        {"n": "2019", "v": "2019"},
        {"n": "2018", "v": "2018"},
        {"n": "2017", "v": "2017"},
        {"n": "2016", "v": "2016"},
        {"n": "2015", "v": "2015"},
        {"n": "更早", "v": "2014"},
    ]},
    {"key": "by", "name": "排序", "value": [
        {"n": "按时间", "v": "time"},
        {"n": "按人气", "v": "hits"},
        {"n": "按评分", "v": "score"},
    ]},
]


# ============================================================================
# 工具函数
# ============================================================================
def _unescape(s):
    """HTML 实体反转义 (不引入额外依赖)。"""
    if not s:
        return s
    return (s.replace("&nbsp;", " ")
             .replace("&amp;", "&")
             .replace("&quot;", '"')
             .replace("&#39;", "'")
             .replace("&apos;", "'")
             .replace("&lt;", "<")
             .replace("&gt;", ">"))


def _text(s):
    """去标签 + 反转义 + 去空白。"""
    if not s:
        return ""
    return _unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _abs(url):
    """补全相对地址。"""
    if not url:
        return ""
    url = _html_unescape_url(url.strip())
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return HOST + url
    return HOST + "/" + url


def _html_unescape_url(u):
    return u.replace("&amp;", "&")


def _first(html, pattern, flags=re.S):
    m = re.search(pattern, html, flags)
    return m.group(1).strip() if m and m.groups() else ""


# ============================================================================
# Spider
# ============================================================================
class Spider(BaseSpider):
    """茶杯狐 (chabeihu12.com) TVBox Python 爬虫。"""

    def __init__(self):
        self.host = HOST
        self.name = "茶杯狐"
        self.session = None
        self._init_session()

    # ------------------------------------------------------------ TVBox 生命周期
    def getName(self):
        return self.name

    def init(self, extend=""):
        """TVBox 拉起时调用。extend 可传新域名或 {"host": "..."} 实现换站。"""
        try:
            ext = (extend or "").strip()
            if ext:
                if ext.startswith("{"):
                    cfg = json.loads(ext)
                    new = cfg.get("host") or cfg.get("site") or ""
                    if new:
                        self.host = new.rstrip("/")
                elif ext.startswith("http"):
                    self.host = ext.rstrip("/")
                HEADERS["Referer"] = self.host + "/"
                if self.session is not None:
                    self.session.headers.update({"Referer": self.host + "/"})
        except Exception:
            pass
        return self

    def _init_session(self):
        if requests is None:
            return
        try:
            self.session = requests.Session()
            self.session.headers.update(HEADERS)
            self.session.verify = False
        except Exception:
            self.session = None

    def isVideoFormat(self, url):
        return bool(url) and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    # ------------------------------------------------------------------- http
    def _fetch(self, url, data=None, referer=None):
        """GET/POST 拉取页面, 返回 utf-8 文本, 失败返回 ''。"""
        headers = dict(HEADERS)
        if referer:
            headers["Referer"] = referer
        if self.session is not None:
            try:
                if data is not None:
                    r = self.session.post(url, data=data, headers=headers,
                                          timeout=TIMEOUT, verify=False)
                else:
                    r = self.session.get(url, headers=headers,
                                         timeout=TIMEOUT, verify=False)
                r.encoding = "utf-8"
                return r.text or ""
            except Exception:
                return ""
        # urllib 兜底
        try:
            body = None
            if data is not None:
                body = urlencode(data).encode("utf-8")
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            resp = urlopen(Request(url, data=body, headers=headers), timeout=TIMEOUT)
            raw = resp.read()
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("gbk", "ignore")
        except Exception:
            return ""

    # ------------------------------------------------------------------ 首页
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS if filter else {}}

    def homeVideoContent(self):
        """首页推荐位: 「正在热播」区块。"""
        html = self._fetch(self.host + "/")
        return {"list": self._dedup(self._parse_module_items(html))}

    # ------------------------------------------------------------------ 分类
    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg or 1)
        extend = extend or {}
        tid = str(tid)

        # 走筛选通道 (searchtype=5)
        has_filter = any(extend.get(k) for k in ("area", "year", "by")) \
            or (extend.get("tid") and str(extend["tid"]) != tid)

        if has_filter:
            ftid = extend.get("tid") or tid
            qs = ["searchtype=5", "tid=" + quote(str(ftid))]
            if extend.get("area"):
                qs.append("area=" + quote(str(extend["area"])))
            if extend.get("year"):
                qs.append("year=" + quote(str(extend["year"])))
            if extend.get("by"):
                qs.append("by=" + quote(str(extend["by"])))
            if pg > 1:
                qs.append("page=%d" % pg)
            url = self.host + "/search.php?" + "&".join(qs)
        else:
            url = ("%s/frim/index%s.html" % (self.host, tid)) if pg <= 1 \
                else ("%s/frim/index%s-%d.html" % (self.host, tid, pg))

        html = self._fetch(url, referer=self.host + "/")
        videos = self._dedup(self._parse_module_items(html))

        pagecount = pg
        tail = re.findall(r'index%s-(\d+)\.html' % re.escape(tid), html)
        if tail:
            try:
                pagecount = max(int(x) for x in tail)
            except ValueError:
                pagecount = pg

        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": len(videos),
            "total": pagecount * max(len(videos), 1),
        }

    # ------------------------------------------------------------------ 详情
    def detailContent(self, ids):
        vid_or_url = ids[0] if isinstance(ids, (list, tuple)) else ids
        vid_or_url = str(vid_or_url).strip()

        if vid_or_url.startswith("http"):
            detail_url = vid_or_url
            vid = _first(detail_url, r"index(\d+)\.html") or vid_or_url
        else:
            vid = _first(vid_or_url, r"(\d+)") or vid_or_url
            detail_url = "%s/movie/index%s.html" % (self.host, vid)

        html = self._fetch(detail_url, referer=self.host + "/")
        if not html:
            return {"list": []}

        name = _text(_first(html, r'<h1 class="page-title">(.*?)</h1>'))
        if not name:
            name = _text(_first(html, r'<h1[^>]*>(.*?)</h1>'))

        pic = _first(html, r'<img class="lazyload"[^>]*data-src="([^"]+)"')
        if not pic:
            pic = _first(html, r'<img[^>]*data-src="([^"]+)"')

        # 分类 / 年份 / 地区  (走 .video-info-aux)
        aux = _first(html, r'(<div class="video-info-aux">.*?)</div>\s*</div>')
        if not aux:
            aux = _first(html, r'(<div class="video-info-aux">.*?)<a href="/play/')
        cate = _text(_first(aux, r'class="tag-link"[^>]*>(?:<[^>]+>)*([^<]+)</a>'))
        year = _first(aux, r'year=(\d{4})')
        area = _first(aux, r'area=([^"&\']*)')
        if not area:
            area = _first(html, r'&amp;area=([^"&\']*)')
        area = unquote(area) if area else ""

        director, actor = self._parse_staff(html)
        content = self._parse_content(html)

        remark = _text(_first(html, r'class="video-serial"[^>]*>([^<]*)<'))
        if not remark:
            remark = _text(_first(html, r'class="module-item-text"[^>]*>(.*?)</div>'))
        if not remark:
            remark = _text(_first(html, r'<span class="video-info-itemtitle">状态：'
                                        r'</span>\s*<div[^>]*>(.*?)</div>'))

        play_from, play_url = self._parse_playlist(html)

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": _abs(pic),
            "type_name": cate or "",
            "vod_year": year or "",
            "vod_area": area or "",
            "vod_remarks": remark,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    # ------------------------------------------------------------------ 搜索
    def searchContent(self, key, quick=False, pg="1"):
        key = (key or "").strip()
        if not key:
            return {"list": []}
        html = self._fetch(self.host + "/search.php",
                           data={"searchword": key},
                           referer=self.host + "/")
        if not html:
            html = self._fetch(
                self.host + "/search.php?searchword=" + quote(key),
                referer=self.host + "/")
        return {"list": self._dedup(self._parse_search_items(html))}

    # ------------------------------------------------------------------ 播放
    def playerContent(self, flag, id, vipFlags=None):
        play_page = _abs(id)
        html = self._fetch(play_page, referer=play_page)
        video_url = self._extract_play_url(html)

        if video_url:
            return {
                "parse": 0,
                "playUrl": "",
                "url": video_url,
                "header": json.dumps({
                    "User-Agent": UA,
                    "Referer": play_page,
                }, ensure_ascii=False),
            }
        # 未取到直链: 交回 TVBox 嗅探播放页
        return {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": json.dumps({
                "User-Agent": UA,
                "Referer": self.host + "/",
            }, ensure_ascii=False),
        }

    # =====================================================================
    # 内部解析
    # =====================================================================
    @staticmethod
    def _dedup(videos):
        seen, out = set(), []
        for v in videos:
            if v.get("vod_id") in seen:
                continue
            seen.add(v.get("vod_id"))
            out.append(v)
        return out

    def _parse_module_items(self, html):
        """解析列表页/首页的 <div class="module-item"> 条目。"""
        if not html:
            return []
        videos = []
        for m in re.finditer(r'<div class="module-item">', html):
            b = m.start()
            nxt = html.find('<div class="module-item">', b + 5)
            block = html[b: nxt if nxt > 0 else b + 3000]
            item = self._parse_module_item(block)
            if item:
                videos.append(item)
        return videos

    def _parse_module_item(self, block):
        m = re.search(r'href="(/movie/index(\d+)\.html)"[^>]*title="([^"]*)"', block)
        if not m:
            m2 = re.search(r'<a[^>]*href="(/movie/index(\d+)\.html)"[^>]*>(.*?)</a>',
                           block, re.S)
            if not m2:
                return None
            link, vid, name = m2.group(1), m2.group(2), _text(m2.group(3))
        else:
            link, vid, name = m.group(1), m.group(2), _unescape(m.group(3))

        pic = _first(block, r'data-src="([^"]+)"')
        if not pic:
            pic = _first(block, r'<img[^>]*src="([^"]+)"')
        remark = _text(_first(block, r'class="module-item-text"[^>]*>(.*?)</div>'))
        if not remark:
            remark = _text(_first(block, r'class="module-item-note"[^>]*>(.*?)</div>'))
        return {
            "vod_id": vid,
            "vod_name": name.strip(),
            "vod_pic": _abs(pic),
            "vod_remarks": remark,
        }

    def _parse_search_items(self, html):
        """解析搜索结果 <div class="module-search-item">。"""
        if not html:
            return []
        videos = []
        for m in re.finditer(r'<div class="module-search-item">', html):
            b = m.start()
            nxt = html.find('<div class="module-search-item">', b + 5)
            block = html[b: nxt if nxt > 0 else b + 4000]
            mm = re.search(r'href="(/movie/index(\d+)\.html)"', block)
            if not mm:
                continue
            vid = mm.group(2)
            name = _text(_first(block, r'<h3>\s*<a[^>]*>(.*?)</a>'))
            if not name:
                name = _unescape(_first(block, r'title="([^"]+)"'))
            pic = _first(block, r'data-src="([^"]+)"') or _first(block, r'<img[^>]*src="([^"]+)"')
            remark = _text(_first(block, r'class="video-serial"[^>]*>([^<]*)<'))
            videos.append({
                "vod_id": vid,
                "vod_name": name.strip(),
                "vod_pic": _abs(pic),
                "vod_remarks": remark,
            })
        return videos

    def _parse_staff(self, html):
        """解析导演 / 主演。"""
        director, actor = "", ""
        seg = _first(html, r'(<div class="video-info-main">.*?)'
                           r'<div class="video-info-footer')
        if not seg:
            seg = html

        m = re.search(r'导演：</span>(.*?)(?=<span class="video-info-itemtitle"|'
                      r'<div class="video-info-itemtitle"|</div>\s*</div>)', seg, re.S)
        if m:
            director = "、".join(_unescape(x) for x in re.findall(r'>([^<>]+)</a>', m.group(1)))

        m = re.search(r'(?:主演|演员)：</span>(.*?)(?=<span class="video-info-itemtitle"|'
                      r'<div class="video-info-itemtitle"|</div>\s*</div>)', seg, re.S)
        if m:
            actor = "、".join(_unescape(x) for x in re.findall(r'>([^<>]+)</a>', m.group(1)))
        return director, actor

    @staticmethod
    def _parse_content(html):
        """解析剧情简介 (容器 class 是 video-info-item video-info-content)。"""
        seg = _first(html, r'<div class="video-info-content">(.*?)</div>')
        if not seg:
            seg = _first(html, r'<div class="[^"]*video-info-content[^"]*">(.*?)</div>')
        if not seg:
            seg = _first(html, r'<div class="vod-content">(.*?)</div>')
        if not seg:
            seg = _first(html, r'<span class="detail-content">(.*?)</span>')
        if not seg:
            return ""
        seg = re.sub(r'<br\s*/?>', '\n', seg, flags=re.I)
        seg = re.sub(r'</p>\s*<p[^>]*>', '\n', seg, flags=re.I)
        seg = _unescape(re.sub(r'<[^>]+>', '', seg))
        lines = [ln.strip().replace("\u3000", "").strip() for ln in seg.split("\n")]
        return "\n".join([ln for ln in lines if ln])

    def _parse_playlist(self, html):
        """
        解析播放线路。

        站点每路播放列表会输出两个 <div class="module-blocklist"> (一个给桌面、
        一个给移动端), 内容完全相同; 因此按 vfrom 去重, 只保留每条线路一次。
        """
        if not html:
            return [], []

        # 线路名 (按「播放节点列表」下拉顺序)
        names = re.findall(r'data-dropdown-value="([^"]+)"', html)
        if not names:
            names = re.findall(
                r'class="module-tab-item tab-item"[^>]*>\s*<span[^>]*>([^<]+)</span>', html)

        seg_start = html.find('module-player-list')
        seg = html[seg_start:] if seg_start > 0 else html

        starts = [m.start() for m in re.finditer(r'<div class="module-blocklist[^"]*">', seg)]
        starts.append(len(seg))

        ordered_from = []      # 出现顺序的 vfrom
        grouped = {}           # vfrom -> [ "第01集$/play/xxx.html", ... ]
        for i in range(len(starts) - 1):
            block = seg[starts[i]:starts[i + 1]]
            eps = self._parse_episodes(block)   # [(title, vfrom, href), ...]
            if not eps:
                continue
            vfrom = eps[0][1]
            if vfrom in grouped:
                continue       # 移动端重复块, 跳过
            grouped[vfrom] = ["%s$%s" % (t, h) for t, _v, h in eps]
            ordered_from.append(vfrom)

        play_from, play_url = [], []
        for idx, vfrom in enumerate(ordered_from):
            name = names[idx] if idx < len(names) else ("线路%d" % (idx + 1))
            play_from.append(name)
            play_url.append("#".join(grouped[vfrom]))
        return play_from, play_url

    @staticmethod
    def _parse_episodes(block):
        """从单个 module-blocklist 提取 [(剧集名, vfrom, href), ...]。"""
        eps = []
        # 常见写法: href 在前, title 在后
        for a in re.finditer(
                r'<a[^>]*href="(/play/(\d+)-(\d+)-(\d+)\.html)"[^>]*>(.*?)</a>',
                block, re.S):
            href, _vid, vfrom, idx, inner = a.groups()
            title = _text(inner)
            if not title:
                title = _unescape(_first(a.group(0), r'title="([^"]*)"'))
            if not title:
                title = "第%d集" % (int(idx) + 1)
            eps.append((title, vfrom, href))
        # 兼容 title 在前 href 在后 的写法
        if not eps:
            for a in re.finditer(
                    r'<a[^>]*title="([^"]*)"[^>]*href="(/play/(\d+)-(\d+)-(\d+)\.html)"',
                    block, re.S):
                title, href, _vid, vfrom, idx = a.groups()
                title = _unescape(title) or ("第%d集" % (int(idx) + 1))
                eps.append((title, vfrom, href))
        return eps

    @staticmethod
    def _extract_play_url(html):
        """从播放页提取真实 m3u8 / mp4 地址。"""
        if not html:
            return ""
        patterns = [
            r'var\s+now\s*=\s*[\'"]([^\'"]+)[\'"]',
            r'var\s+url\s*=\s*[\'"]([^\'"]+\.(?:m3u8|mp4)[^\'"]*)[\'"]',
            r'url\s*:\s*[\'"](https?://[^\'"]+\.(?:m3u8|mp4)[^\'"]*)',
            r'["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
        ]
        for p in patterns:
            m = re.search(p, html)
            if m:
                url = m.group(1).strip().replace("\\/", "/")
                if url.startswith("//"):
                    url = "https:" + url
                if url.startswith("http"):
                    return url
        return ""


# ============================================================================
# 本地自检
# ============================================================================
def _demo():
    s = Spider()
    line = "=" * 72
    print(line)
    print("茶杯狐 chabeihu12.com  TVBox 爬虫自检")
    print(line)

    print("\n[1] homeContent")
    print("    分类:", [c["type_name"] for c in s.homeContent(True)["class"]])

    print("\n[2] categoryContent(tid=2, pg=1)  电视剧")
    cc = s.categoryContent("2", "1", False, {})
    print("    数量: %d   总页数: %d" % (len(cc["list"]), cc["pagecount"]))
    for v in cc["list"][:3]:
        print("     -", v["vod_id"], v["vod_name"], "|", v["vod_remarks"])

    print("\n[3] 筛选 categoryContent(tid=1, 大陆/2024/人气)")
    cf = s.categoryContent("1", "1", True, {"tid": "1", "area": "大陆",
                                            "year": "2024", "by": "hits"})
    print("    数量: %d" % len(cf["list"]))
    for v in cf["list"][:3]:
        print("     -", v["vod_id"], v["vod_name"], "|", v["vod_remarks"])

    print("\n[4] searchContent('斗破苍穹')")
    sr = s.searchContent("斗破苍穹", False, "1")
    print("    命中: %d" % len(sr["list"]))
    for v in sr["list"][:3]:
        print("     -", v["vod_id"], v["vod_name"], "|", v["vod_remarks"])

    if not sr["list"]:
        print("\n搜索无结果, 自检提前结束")
        return

    vid = sr["list"][0]["vod_id"]
    print("\n[5] detailContent(['%s'])" % vid)
    d = s.detailContent([vid])
    if not d["list"]:
        print("    详情为空!")
        return
    vod = d["list"][0]
    print("    名称 :", vod["vod_name"])
    print("    封面 :", vod["vod_pic"])
    print("    分类 : %s | 年份: %s | 地区: %s" % (
        vod["type_name"], vod["vod_year"], vod["vod_area"]))
    print("    备注 :", vod["vod_remarks"])
    print("    导演 :", vod["vod_director"][:50])
    print("    演员 :", vod["vod_actor"][:70])
    print("    简介 :", vod["vod_content"][:70].replace("\n", " "), "...")

    froms = vod["vod_play_from"].split("$$$")
    urls = vod["vod_play_url"].split("$$$")
    print("    线路 :", froms)
    for i, f in enumerate(froms):
        eps = urls[i].split("#") if i < len(urls) else []
        print("      %-8s %d 集   首集: %s" % (f, len(eps), eps[0] if eps else "-"))

    if urls and urls[0]:
        first = urls[0].split("#")[0]
        ep_id = first.split("$")[-1]
        print("\n[6] playerContent(flag='%s', id='%s')" % (froms[0], ep_id))
        pc = s.playerContent(froms[0], ep_id, None)
        print("    parse:", pc["parse"])
        print("    url  :", pc["url"])
        print("    header:", pc["header"])

    print("\n" + line)
    print("自检完成")


if __name__ == "__main__":
    if requests is None:
        print("[提示] 未安装 requests, 已切到 urllib 兜底模式")
    _demo()
