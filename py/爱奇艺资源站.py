# coding=utf-8
"""
TVBox / 影视仓 Python 爬虫源 —— 练习版2 (HTML 站)
站点: 爱奇艺资源站 (iqiyizy.com, maccms + shoutu 模板, 4K 资源)
路由: /index.php/vod/type/id/{tid}.html        分类 (分页 /page/N.html)
      /index.php/vod/detail/id/{vid}.html     详情 (内嵌 集名$m3u8)
      /index.php/vod/search.html?wd=...       搜索 (有JS质询, 大概率失败→降级)

学习要点 (对比三个范本):
1. 30剧集网思路: BeautifulSoup + CSS 选择器解析列表; playerContent 直链直接返回
2. 黑米思路: 先在浏览器里摸清真实 DOM 再写选择器, 注释里记录结构依据
3. 本站特点: 详情页 <span class="this-url"> 里直接是 "集名$m3u8" 文本,
   播放链接形如 jx?url=<m3u8>, 剥壳即得直链 —— 无需递归解析, 一层提取链足够
4. 已知缺陷(实测): 搜索页返回 "系统安全验证" JS 质询, 沙盒无法过,
   searchContent 做了双路由尝试 + 失败降级, TVBox 客户端环境或有 Cookie 后可用
"""
import re
import json
import html as html_mod
import urllib.parse
import urllib.request

try:
    import requests
except Exception:
    requests = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        def init(self, extend=""):
            pass


HOST = "https://www.iqiyizy.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 导航用一级分类; 子分类数量太多不铺满, 主分类下用筛选选子分类
MAIN_TYPES = [
    {"type_id": "7", "type_name": "电影"},
    {"type_id": "8", "type_name": "连续剧"},
    {"type_id": "9", "type_name": "综艺"},
]
SUB_FILTERS = {
    "7": [("动作片", 10), ("喜剧片", 11), ("爱情片", 12), ("科幻片", 13), ("恐怖片", 14),
          ("剧情片", 15), ("战争片", 16), ("惊悚片", 17), ("古装片", 19), ("悬疑片", 21),
          ("犯罪片", 22), ("记录片", 24)],
    "8": [("国产剧", 26), ("香港剧", 27), ("台湾剧", 28), ("日本剧", 29), ("欧美剧", 30),
          ("韩国剧", 31), ("海外剧", 32)],
    "9": [],
}


def _log(*args):
    try:
        import sys
        sys.stderr.write("[爱奇艺资源] " + " ".join(str(a) for a in args) + "\n")
    except Exception:
        pass


def _clean(t):
    if not t:
        return ""
    t = re.sub(r"<[^>]+>", "", str(t))
    t = html_mod.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def _is_direct(url):
    return bool(re.search(r"\.(m3u8|mp4|flv|mkv|ts)(\?|$)", url or "", re.I))


class Spider(BaseSpider):

    def getName(self):
        return "爱奇艺资源站"

    def init(self, extend=""):
        self.headers = {"User-Agent": UA, "Referer": HOST + "/",
                        "Accept-Language": "zh-CN,zh;q=0.9"}
        self._timeout = 15
        self.host = HOST

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return _is_direct(url)

    def manualVideoCheck(self):
        return False

    # ---------- HTTP (requests -> urllib 降级, 黑米思路) ----------
    def _http_get(self, url):
        if requests:
            try:
                r = requests.get(url, headers=self.headers, timeout=self._timeout, verify=False)
                if r.status_code == 200:
                    return r.text
                return ""
            except Exception:
                pass
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception as e:
            _log("请求失败", url[:80], repr(e)[:60])
            return ""

    def _fetch(self, url):
        for _ in range(2):
            txt = self._http_get(url)
            if txt:
                return txt
        return ""

    # ---------- 列表解析 (30剧集网思路: 选择器 + 降级) ----------
    def _parse_list(self, html_text):
        """列表页结构 (实测):
        <li><a class="this-link flex" href="/index.php/vod/detail/id/86775.html" title="分床合爱">
          <div class="this-wap-name flex"><h5>分床合爱</h5><i>正片</i></div>
          <div class="shoutu-pc">意大利</div><div class="shoutu-pc">剧情片</div>
          <div class="this-wap-time this-time">2026-10-16 ...</div>
        """
        result, seen = [], set()
        if not html_text:
            return result
        # 本站列表是"表格行"形态, 无封面图, vod_pic 置空
        cards = re.findall(
            r'<a[^>]+class=["\'][^"\']*this-link[^"\']*["\'][^>]+'
            r'href=["\']([^"\']*/vod/detail/id/(\d+)\.html)["\'][^>]*title=["\']([^"\']+)["\']'
            r'(.*?)</a>',
            html_text, re.I | re.S)
        if not cards and BeautifulSoup:
            soup = BeautifulSoup(html_text, "html.parser")
            for a in soup.select("a.this-link[href*='/vod/detail/id/']"):
                vid = re.search(r"/vod/detail/id/(\d+)\.html", a.get("href", ""))
                if not vid:
                    continue
                title = a.get("title", "") or _clean(a.get_text())
                result.append({"vod_id": vid.group(1), "vod_name": title,
                               "vod_pic": "", "vod_remarks": ""})
            return result
        for href, vid, title, inner in cards:
            if vid in seen:
                continue
            seen.add(vid)
            # 备注: <i>正片</i> 或 地区/类型
            remarks = ""
            m = re.search(r"<i>([^<]{1,20})</i>", inner)
            if m:
                remarks = _clean(m.group(1))
            if not remarks:
                divs = re.findall(r'<div[^>]*shoutu-pc[^>]*>([^<]{1,20})</div>', inner)
                remarks = " / ".join(_clean(d) for d in divs[:2] if _clean(d))
            result.append({"vod_id": vid, "vod_name": _clean(title),
                           "vod_pic": "", "vod_remarks": remarks})
        return result

    def _parse_pagecount(self, html_text, pg):
        # 分页形如 /vod/type/id/7/page/2.html, 取最大页码
        nums = [int(n) for n in re.findall(
            r"/(?:vod/type/id/\d+/)?page/(\d+)\.html", html_text or "")]
        return max(nums) if nums else max(int(pg or 1), 1)

    # ---------- 首页 ----------
    def homeContent(self, filter):
        result = {"class": [dict(c) for c in MAIN_TYPES]}
        if filter:
            filters = {}
            for t in MAIN_TYPES:
                subs = SUB_FILTERS.get(t["type_id"], [])
                if subs:
                    filters[t["type_id"]] = [{
                        "key": "sub", "name": "类型",
                        "value": [{"n": "全部", "v": ""}] +
                                 [{"n": n, "v": str(i)} for n, i in subs]}]
            result["filters"] = filters
        return result

    def homeVideoContent(self):
        return {"list": self._parse_list(self._fetch(self.host + "/"))[:40]}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        empty = {"list": [], "page": pg, "pagecount": 1, "limit": 30, "total": 0}
        try:
            sub = ""
            if isinstance(extend, dict) and extend.get("sub"):
                sub = str(extend["sub"])
            tid_use = sub if sub else tid
            url = "%s/index.php/vod/type/id/%s.html" % (self.host, tid_use)
            if pg > 1:
                url = "%s/index.php/vod/type/id/%s/page/%d.html" % (self.host, tid_use, pg)
            html_text = self._fetch(url)
            if not html_text:
                return empty
            items = self._parse_list(html_text)
            empty.update({"list": items, "pagecount": self._parse_pagecount(html_text, pg),
                          "total": len(items)})
            return empty
        except Exception as e:
            _log("categoryContent异常", repr(e)[:80])
            return empty

    # ---------- 详情 ----------
    def detailContent(self, ids):
        result = {"list": []}
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            html_text = self._fetch("%s/index.php/vod/detail/id/%s.html" % (self.host, vid))
            if not html_text:
                return result

            def _field(label):
                # 结构: <span><em>导演：</em>xxx</span>
                m = re.search(r"<em>%s[：:]</em>(.{0,300}?)</span>" % label, html_text, re.S)
                return _clean(m.group(1)) if m else ""

            title = _field("片名") or ""
            if not title:
                m = re.search(r'<h2[^>]*class=["\'][^"\']*this-name[^"\']*["\'][^>]*>([^<]+)</h2>',
                              html_text) or re.search(r"title=\"([^\"]{1,40})\"", html_text)
                title = _clean(m.group(1)) if m else str(vid)
            # 海报: 本站结构 (实测) <img src="https://tu.iqiyizyimg.com/upload/vod/..." alt="片名">
            # 优先取 /upload/vod/ 路径或 alt 与片名一致的 img, 排除 logo 等装饰图
            pic = ""
            for m in re.finditer(r'<img[^>]+>', html_text):
                tag = m.group(0)
                sm = re.search(r'src="([^"]+\.(?:jpg|png|webp)[^"]*)"', tag)
                if not sm:
                    continue
                u = sm.group(1)
                am = re.search(r'alt="([^"]*)"', tag)
                alt = _clean(am.group(1)) if am else ""
                if "/upload/vod/" in u or (alt and alt == title):
                    pic = urllib.parse.urljoin(self.host + "/", u)
                    break
            if not pic:
                # 兜底: 排除 logo/static/二维码 后取第一张
                for m in re.finditer(r'src="([^"]+\.(?:jpg|png|webp)[^"]*)"', html_text):
                    u = m.group(1)
                    if not any(k in u for k in ("logo", "static", "qrcode", "二维码")) \
                            and "/upload/" in u:
                        pic = urllib.parse.urljoin(self.host + "/", u)
                        break
            if not title:
                # 海报 alt 即片名, 作为标题兜底
                m = re.search(r'<img[^>]+src="[^"]*/upload/vod/[^"]*"[^>]+alt="([^"]+)"',
                              html_text)
                if m:
                    title = _clean(m.group(1))

            # 剧集提取: <span class="this-url ...">集名$m3u8</span> (本站直接内嵌TVBox格式)
            play_groups = {}
            for m in re.finditer(
                    r'<span[^>]*class=["\'][^"\']*this-url[^"\']*["\'][^>]*>'
                    r'([^<]{1,40}\$[^<]{1,300})</span>', html_text):
                name_url = _clean(m.group(1))
                if "$" in name_url:
                    nm, u = name_url.split("$", 1)
                    u = urllib.parse.unquote(u).strip()
                    if u.startswith("http"):
                        play_groups.setdefault("默认线路", []).append((nm, u))
            # 降级: 从解析跳转链接 jx?url=m3u8 剥壳
            if not play_groups:
                eps = []
                for m in re.finditer(
                        r'<a[^>]+href=["\'][^"\']*\?url=([^"\']+)["\'][^>]*>\s*([^<]{1,30})',
                        html_text):
                    u = urllib.parse.unquote(m.group(1)).strip()
                    if _is_direct(u):
                        eps.append((_clean(m.group(2)) or "播放", u))
                if eps:
                    play_groups["默认线路"] = eps
            if not play_groups:
                sources, urls = ["默认"], ["播放$%s" % vid]
            else:
                sources = list(play_groups.keys())
                urls = ["#".join("%s$%s" % (n, u) for n, u in play_groups[s])
                        for s in sources]
            result["list"].append({
                "vod_id": str(vid),
                "vod_name": title,
                "vod_pic": pic,
                "vod_actor": _field("演员"),
                "vod_director": _field("导演"),
                "vod_year": _field("年代"),
                "vod_area": _field("地区"),
                "vod_lang": _field("语言"),
                "vod_content": _field("剧情介绍") or _field("简介"),
                "vod_play_from": "$$$".join(sources),
                "vod_play_url": "$$$".join(urls),
            })
            return result
        except Exception as e:
            _log("detailContent异常", repr(e)[:80])
            return result

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        header = {"User-Agent": UA, "Referer": self.host + "/"}
        try:
            play_url = urllib.parse.unquote(id or "").strip()
            # 剥掉解析页外壳 jx?url=xxx
            m = re.search(r"\?url=([^&]+)", play_url)
            if m:
                play_url = urllib.parse.unquote(m.group(1))
            if play_url.startswith("http") and _is_direct(play_url):
                return {"parse": 0, "url": play_url, "header": header}
            return {"parse": 1, "url": play_url, "header": header}
        except Exception:
            return {"parse": 1, "url": id, "header": header}

    # ---------- 搜索 (已知: 站点有 JS 质询, 客户端可能可用, 沙盒降级) ----------
    def searchContent(self, key, quick, pg="1"):
        result = {"list": [], "page": int(pg or 1)}
        if not key:
            return result
        for url in (
            "%s/index.php/vod/search.html?wd=%s&pg=%s" % (
                self.host, urllib.parse.quote(key), pg),
            "%s/index.php/vod/search/wd/%s.html" % (self.host, urllib.parse.quote(key)),
        ):
            html_text = self._fetch(url)
            if html_text and "系统安全验证" not in html_text:
                items = self._parse_list(html_text)
                if items:
                    result["list"] = items
                    return result
        _log("搜索被JS质询拦截, 返回空 (客户端环境可能可用)")
        return result


# 本地自检
if __name__ == "__main__":
    s = Spider()
    s.init()
    print("== 分类:", [c["type_name"] for c in s.homeContent(False)["class"]])
    print("== 首页:", len(s.homeVideoContent()["list"]), "条")
    cat = s.categoryContent("7", "1", False, {})
    print("== 分类(电影):", len(cat["list"]), "条, pagecount =", cat["pagecount"])
    if cat["list"]:
        vid = cat["list"][0]["vod_id"]
        det = s.detailContent([vid])["list"][0]
        print("== 详情:", det["vod_name"], "| 导演:", det["vod_director"][:20],
              "| 年代:", det["vod_year"])
        first = det["vod_play_url"].split("#")[0]
        print("== 播放:", s.playerContent(det["vod_play_from"], first.split("$")[1])["url"][:80])
    print("== 搜索:", len(s.searchContent("分床合爱", False)["list"]), "条 (预期0: JS质询)")
