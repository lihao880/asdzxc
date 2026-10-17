# coding=utf-8
"""
TVBox / 影视仓 Python 爬虫源 —— 练习版3 (短剧站, stui 模板)
站点: 低端影视 (iqingtun.com, 苹果CMS + stui 模板, 短剧/电影/剧集全都有)
路由: /type/{tid}.html        分类 (分页 /type/{tid}-{pg}.html)
      /voddetail/{id}.html    详情 (两条线路 playlist1/2, 集 /vplay/{id}/{sid}-{nid}.html)
      /vplay/{id}/{sid}-{nid}.html  播放页 (player_aaaa JSON, url 为转义 m3u8)
      /search/{kw}-------------.html 搜索 (Cloudflare 质询, 沙盒不可用→降级)
分类: 1电影 2电视剧 3综艺 4动漫 33短剧(最新网红短剧)

学习要点 (30短剧集网同族模板的对照练习):
1. 30剧集网用 BeautifulSoup; 本版换纯正则+BS4双轨, 对照两者写法差异
2. player_aaaa 提取要点: JSON 里 url 是 "https:\\/\\/x\\/y.m3u8" 转义形态,
   必须做 \\/ -> / 反转义 (黑米 _unescape_url 的坑, 实战验证)
3. 站点 Cloudflare 只挡 /show/ 与 /search/, /type//voddetail//vplay/ 均放行 ——
   用 /type/{id} 替代 /show/{id} 做分类即可绕开质询
4. 播放页多线路: #playlist1 / #playlist2 两个 ul, 按 id 提取分组 (黑米 data-target 思路的变体)
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


HOST = "https://www.iqingtun.com"
# 反爬发现 (实测): 该站按 UA 指纹拦截 —— 完整 Chrome UA 反而 404,
# 简版 UA "Mozilla/5.0" 放行。TVBox 内置 Python 环境默认 UA 简短, 反而更稳。
UA = "Mozilla/5.0"

CLASSES = [
    {"type_id": "33", "type_name": "短剧"},
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
]


def _log(*args):
    try:
        import sys
        sys.stderr.write("[低端影视] " + " ".join(str(a) for a in args) + "\n")
    except Exception:
        pass


def _clean(t):
    if not t:
        return ""
    t = re.sub(r"<[^>]+>", "", str(t))
    t = html_mod.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def _unescape_url(u):
    """player_aaaa 里 url 是 https:\\/\\/x.m3u8 形态, 还原之 (黑米思路)"""
    if not u:
        return ""
    return u.replace("\\/", "/").replace("\\u0026", "&").replace("\\", "")


def _is_direct(url):
    return bool(re.search(r"\.(m3u8|mp4|flv|mkv|ts)(\?|$)", url or "", re.I))


class Spider(BaseSpider):

    def getName(self):
        return "低端影视"

    def init(self, extend=""):
        self.headers = {"User-Agent": UA, "Referer": HOST + "/",
                        "Accept-Language": "zh-CN,zh;q=0.9"}
        self._timeout = 15

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return _is_direct(url)

    def manualVideoCheck(self):
        return False

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
            if txt and "Just a moment" not in txt:
                return txt
        return ""

    # ---------- 列表解析 (stui 模板, 与 myui 同族) ----------
    def _parse_list(self, html_text):
        result, seen = [], set()
        if not html_text:
            return result
        # 结构: <a href="/voddetail/119603.html" class="stui-vodlist__thumb lazyload"
        #        title="从赘婿到宠臣" data-original="https://img.../xxx.jpg">
        #        <span class="pic-text text-center">从赘婿到宠臣</span></a>
        cards = re.findall(
            r'<a[^>]+href=["\']([^"\']*/voddetail/(\d+)\.html)["\']'
            r'[^>]*class=["\'][^"\']*stui-vodlist__thumb[^"\']*["\'][^>]*>'
            r'(.*?)</a>',
            html_text, re.I | re.S)
        for href, vid, inner in cards:
            if vid in seen:
                continue
            seen.add(vid)
            tm = re.search(r'title=["\']([^"\']+)["\']', "href=%s %s" % (href, inner))
            title = _clean(tm.group(1)) if tm else ""
            if not title:
                tm = re.search(r'title=["\']([^"\']+)["\']', inner)
                title = _clean(tm.group(1)) if tm else ""
            if not title:
                continue
            pm = re.search(r'(?:data-original|data-src|src)=["\']([^"\']+)["\']', inner)
            pic = pm.group(1) if pm else ""
            if pic and not pic.startswith("http"):
                pic = urllib.parse.urljoin(HOST + "/", pic)
            rm = re.search(r'class=["\'][^"\']*pic-text[^"\']*["\'][^>]*>([^<]+)<', inner)
            remark = _clean(rm.group(1)) if rm else ""
            result.append({"vod_id": vid, "vod_name": title,
                           "vod_pic": pic, "vod_remarks": remark})
        # BS4 降级 (30剧集网思路)
        if not result and BeautifulSoup:
            soup = BeautifulSoup(html_text, "html.parser")
            for a in soup.select("a.stui-vodlist__thumb[href*='/voddetail/']"):
                vid = re.search(r"/voddetail/(\d+)\.html", a.get("href", ""))
                if not vid or vid.group(1) in seen:
                    continue
                seen.add(vid.group(1))
                pt = a.select_one(".pic-text")
                result.append({
                    "vod_id": vid.group(1),
                    "vod_name": _clean(a.get("title", "") or a.get_text()),
                    "vod_pic": a.get("data-original") or a.get("data-src") or "",
                    "vod_remarks": _clean(pt.get_text()) if pt else ""})
        return result

    def _parse_pagecount(self, html_text, pg):
        # stui 分页: /type/33-2.html; 取最大页码
        nums = [int(n) for n in re.findall(
            r"/type/\d+-(\d+)\.html", html_text or "")]
        return max(nums) if nums else max(int(pg or 1), 1)

    # ---------- 首页 ----------
    def homeContent(self, filter):
        return {"class": [dict(c) for c in CLASSES]}

    def homeVideoContent(self):
        return {"list": self._parse_list(self._fetch(HOST + "/"))[:40]}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        empty = {"list": [], "page": pg, "pagecount": 1, "limit": 46, "total": 0}
        try:
            url = "%s/type/%s.html" % (HOST, tid) if pg <= 1 else \
                  "%s/type/%s-%d.html" % (HOST, tid, pg)
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
            html_text = self._fetch("%s/voddetail/%s.html" % (HOST, vid))
            if not html_text:
                return result
            soup = BeautifulSoup(html_text, "html.parser") if BeautifulSoup else None

            # 标题: <h1> 内文本 / <title> 前段
            title = str(vid)
            if soup:
                h1 = soup.select_one(".stui-content__detail h1, h1")
                if h1:
                    title = _clean(h1.get_text())
            if title == str(vid):
                m = re.search(r"《([^《》]+)》", html_text)
                if m:
                    title = _clean(m.group(1))
            # 封面: stui-content__thumb 内 lazyload img
            pic = ""
            m = re.search(r'<(?:div|a)[^>]*class=["\'][^"\']*stui-content__thumb[^"\']*["\'][^>]*>.*?'
                          r'(?:data-original|data-src|src)=["\']([^"\']+)["\']',
                          html_text, re.I | re.S)
            if not m:
                m = re.search(r'(?:data-original|data-src)=["\'](https?://[^"\']+)["\']',
                              html_text, re.I)
            if m:
                pic = urllib.parse.urljoin(HOST + "/", m.group(1))

            # 字段: <p><span>主演：</span>xxx</p> 形态
            def _field(label):
                m = re.search(r"<span[^>]*>%s[：:]</span>(.{0,300}?)</p>" % label,
                              html_text, re.S)
                return _clean(m.group(1)) if m else ""

            # 剧集: 多线路 <ul id="playlist1"> / #playlist2, 按面板 id 精确配对
            # (黑米教训: 不能按线路名和面板的下标 zip, 会错位)
            sources, urls = [], []
            panels = re.findall(
                r'<(?:ul|div)[^>]*id=["\']playlist(\d+)["\'][^>]*>(.*?)</(?:ul|div)>',
                html_text, re.I | re.S)
            tabs = re.findall(
                r'<(?:a|li)[^>]*href=["\']#playlist(\d+)["\'][^>]*>([^<]{1,20})<',
                html_text, re.I)
            tab_map = {pid: _clean(name) for pid, name in tabs
                       if _clean(name) and _clean(name) not in ("选集", "全部")}
            for pid, body in panels:
                sname = tab_map.get(pid) or ("线路%s" % pid)
                eps = re.findall(
                    r'<a[^>]+href=["\']([^"\']*/vplay/\d+/\d+-\d+\.html)["\'][^>]*>'
                    r'\s*([^<]{1,40})\s*</a>', body, re.I)
                if not eps:
                    continue
                sources.append(sname)
                urls.append("#".join(
                    "%s$%s" % (_clean(t), urllib.parse.urljoin(HOST + "/", u))
                    for u, t in eps))
            if not sources:
                sources, urls = ["默认"], ["播放$%s/vplay/%s/1-1.html" % (HOST, vid)]
            result["list"].append({
                "vod_id": str(vid),
                "vod_name": title,
                "vod_pic": pic,
                "vod_actor": _field("主演"),
                "vod_director": _field("导演"),
                "vod_year": _field("年份"),
                "vod_area": _field("地区"),
                "vod_type": _field("类型"),
                "vod_remarks": _field("状态") or _field("更新"),
                "vod_content": _field("简介") or _field("剧情"),
                "vod_play_from": "$$$".join(sources),
                "vod_play_url": "$$$".join(urls),
            })
            return result
        except Exception as e:
            _log("detailContent异常", repr(e)[:80])
            return result

    # ---------- 播放 (递归一次: 播放页 -> player_aaaa -> 直链) ----------
    def playerContent(self, flag, id, vipFlags=None):
        header = {"User-Agent": UA, "Referer": HOST + "/"}
        try:
            play_url = urllib.parse.urljoin(HOST + "/", id)
            if _is_direct(play_url):
                return {"parse": 0, "url": play_url, "header": header}
            html_text = self._fetch(play_url)
            if html_text:
                # 1) player_aaaa (苹果CMS权威来源)
                m = re.search(r'player_aaaa\s*=\s*(\{[^<]+\})', html_text)
                if m:
                    try:
                        d = json.loads(m.group(1))
                        u = _unescape_url(d.get("url") or d.get("url_next") or "")
                        if _is_direct(u):
                            return {"parse": 0, "url": u, "header": header}
                    except Exception:
                        pass
                # 2) 转义/普通 m3u8/mp4 直链
                m = re.search(r'(https?:\\?/\\?/[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html_text, re.I)
                if not m:
                    m = re.search(r'(https?:[^\s"\'<>]+\.(?:mp4|flv)[^\s"\'<>]*)', html_text, re.I)
                if m:
                    return {"parse": 0, "url": _unescape_url(m.group(1)).rstrip('\\'),
                            "header": header}
            return {"parse": 1, "url": play_url, "header": header}
        except Exception as e:
            _log("playerContent异常", repr(e)[:80])
            return {"parse": 1, "url": id, "header": header}

    # ---------- 搜索 (Cloudflare 质询, 客户端环境可能可用) ----------
    def searchContent(self, key, quick, pg="1"):
        result = {"list": [], "page": int(pg or 1)}
        if not key:
            return result
        # stui 搜索槽位格式: /search/{kw}-------------{pg}.html (pg>1 时末段为页码)
        if int(pg or 1) > 1:
            url = "%s/search/%s-------------%s.html" % (HOST, urllib.parse.quote(key), pg)
        else:
            url = "%s/search/%s-------------.html" % (HOST, urllib.parse.quote(key))
        html_text = self._fetch(url)
        if html_text:
            items = self._parse_list(html_text)
            if items:
                result["list"] = items
                return result
        _log("搜索被Cloudflare质询拦截, 返回空 (客户端环境可能可用)")
        return result


# 本地自检
if __name__ == "__main__":
    s = Spider()
    s.init()
    print("== 分类:", [c["type_name"] for c in s.homeContent(False)["class"]])
    print("== 首页:", len(s.homeVideoContent()["list"]), "条")
    cat = s.categoryContent("33", "1", False, {})
    print("== 分类(短剧):", len(cat["list"]), "条, pagecount =", cat["pagecount"])
    if cat["list"]:
        item = cat["list"][0]
        print("   首条:", item["vod_name"], "| 图:", item["vod_pic"][:50], "| 备注:", item["vod_remarks"])
        det = s.detailContent([item["vod_id"]])["list"][0]
        first_ep = det["vod_play_url"].split("#")[0]
        print("== 详情:", det["vod_name"], "| 线路:", det["vod_play_from"],
              "| 集数:", len(det["vod_play_url"].split("#")))
        pc = s.playerContent(det["vod_play_from"], first_ep.split("$")[1])
        print("== 播放 parse =", pc["parse"], "| url:", pc["url"][:80])
    print("== 搜索:", len(s.searchContent("赘婿", False)["list"]), "条 (预期0: CF质询)")
