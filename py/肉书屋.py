# coding: utf-8
"""
站点信息：
  主域名: https://m.roushuwu.com
  备用域名: https://www.roushuwu.com
  发布页: https://m.roushuwu.com
  内容类型: 小说 (novel://)
  特殊说明: GBK编码；17mb移动模板。分类/完本页用 newbook_list 结构，
            排行榜页用 articlegeneral 结构；详情页有"最新章节(倒序)"和
            "章节列表(正序)"两个区块，必须定位"章节列表"；完整目录走
            /book/{id}_{page}/ 分页(pageselect)，并发抓取。
  最后验证时间: 2026-09-05
  来源: 用户附件脚本(肉书屋.py) 按真实站点结构修正重写
"""
import json
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def fetch(self, *a, **k):
            return None
        def post(self, *a, **k):
            return None


class Spider(BaseSpider):

    def __init__(self):
        self.hosts = ["https://m.roushuwu.com", "https://www.roushuwu.com"]
        self.host = self.hosts[0]
        self._host_ok = False
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        self.post_headers = dict(self.headers)
        self.post_headers["Content-Type"] = "application/x-www-form-urlencoded"
        # 章节目录最多抓取的分页数（每页约20章）
        self.max_chapter_pages = 200
        # 分类（sort=作品分类，top=排行榜，full=完本）
        self.classes = [
            {"type_id": "sort_1", "type_name": "玄幻奇幻"},
            {"type_id": "sort_2", "type_name": "武侠仙侠"},
            {"type_id": "sort_3", "type_name": "都市言情"},
            {"type_id": "sort_4", "type_name": "历史穿越"},
            {"type_id": "sort_5", "type_name": "网游竞技"},
            {"type_id": "sort_6", "type_name": "科幻灵异"},
            {"type_id": "sort_7", "type_name": "恐怖惊悚"},
            {"type_id": "sort_8", "type_name": "其他类型"},
            {"type_id": "full", "type_name": "完本小说"},
            {"type_id": "top_allvisit", "type_name": "总点击榜"},
            {"type_id": "top_monthvisit", "type_name": "月点击榜"},
            {"type_id": "top_weekvisit", "type_name": "周点击榜"},
            {"type_id": "top_dayvisit", "type_name": "日点击榜"},
            {"type_id": "top_allvote", "type_name": "总推荐榜"},
            {"type_id": "top_monthvote", "type_name": "月推荐榜"},
            {"type_id": "top_goodnum", "type_name": "总收藏榜"},
            {"type_id": "top_size", "type_name": "字数排行"},
            {"type_id": "top_postdate", "type_name": "最新入库"},
            {"type_id": "top_lastupdate", "type_name": "最近更新"},
        ]
        self.filters = {}

    # ---------- 基础方法 ----------
    def getName(self):
        return "肉书屋"

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        self.extend = extend or ""
        return None

    def init(self, extend=""):
        self.setExtendInfo(extend)
        return None

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def destroy(self):
        try:
            self._host_ok = False
        except Exception:
            pass
        return None

    # ---------- 网络封装 ----------
    def _pick_host(self):
        """懒加载确定可用域名（非首页方法调用，homeContent 不触发，保证首页零网络）"""
        if self._host_ok:
            return
        for h in self.hosts:
            try:
                rsp = self.fetch(h + "/", headers={"User-Agent": self.headers["User-Agent"]}, timeout=8)
                if rsp is not None:
                    data = getattr(rsp, "content", None)
                    if data:
                        self.host = h
                        self.headers["Referer"] = h + "/"
                        self.post_headers["Referer"] = h + "/"
                        self._host_ok = True
                        return
            except Exception:
                continue
        self._host_ok = True  # 全失败也标记，继续用默认主域名

    def _decode(self, rsp):
        if rsp is None:
            return ""
        try:
            data = getattr(rsp, "content", None)
            if data is None:
                data = getattr(rsp, "text", "")
            if isinstance(data, bytes):
                return data.decode("gbk", errors="ignore")
            return data or ""
        except Exception:
            return ""

    def _get(self, url):
        """GET 并按 GBK 解码；相对路径自动补全主域名"""
        if url.startswith("/"):
            url = self.host + url
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=15)
            return self._decode(rsp)
        except Exception:
            return ""

    # ---------- 列表解析 ----------
    def _parse_list(self, html):
        """兼容 newbook_list(有封面) 与 articlegeneral(榜单) 两种结构"""
        items = self._parse_newbook_list(html)
        if items:
            return items
        return self._parse_articlegeneral(html)

    def _parse_newbook_list(self, html):
        items = []
        if not html:
            return items
        blocks = html.split('<div class="newbook_list">')[1:]
        for b in blocks:
            m = re.search(r'<div class="newbook_title"><a href="/book/(\d+)/?"[^>]*>([^<]+)</a>', b)
            if not m:
                m = re.search(r'/book/(\d+)/?"[^>]*>([^<]+)</a>', b)
            if not m:
                continue
            vid, name = m.group(1), m.group(2).strip()
            pic = ""
            pm = re.search(r'<img[^>]+src="([^"]+)"', b)
            if pm:
                pic = pm.group(1).strip()
            author = ""
            am = re.search(r'newbook_author"><a[^>]*>([^<]*)</a>', b)
            if am:
                author = am.group(1).strip()
            intro = ""
            im = re.search(r'newbook_intor">(.*?)</div>', b, re.S)
            if im:
                intro = self._clean_text(im.group(1))
            # wanben_serial_novelsort: s1=状态, s2=分类
            remark = "小说"
            sm = re.search(r'wanben_serial_novelsort"><span class="s1">([^<]*)</span><span class="s2">([^<]*)</span>', b)
            if sm:
                remark = (sm.group(1).strip() + " " + sm.group(2).strip()).strip()
            items.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark or "小说",
                "vod_actor": author,
                "vod_content": intro,
            })
        return items

    def _cover(self, bid):
        """按站点规律生成封面 URL: image/{id去尾3位或0}/{id}/{id}s.jpg"""
        bid = str(bid)
        prefix = bid[:-3] if len(bid) > 3 else "0"
        return "https://img.roushuwu.com/image/%s/%s/%ss.jpg" % (prefix, bid, bid)

    def _parse_articlegeneral(self, html):
        items = []
        if not html:
            return items
        area = html
        am = re.search(r'articlegeneral">(.*?)</ul>', html, re.S)
        if am:
            area = am.group(1)
        lis = re.findall(r'<li>(.*?)</li>', area, re.S)
        for li in lis:
            m = re.search(r'<a href="/book/(\d+)/?"[^>]*>([^<]+)</a>', li)
            if not m:
                continue
            vid, name = m.group(1), m.group(2).strip()
            cat = ""
            cm = re.search(r'<p class="p2">([^<]*)</p>', li)
            if cm:
                cat = cm.group(1).strip()
            author = ""
            aa = re.search(r'<p class="p3">.*?<a[^>]*>([^<]*)</a>', li, re.S)
            if aa:
                author = aa.group(1).strip()
            items.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": self._cover(vid),
                "vod_remarks": cat or "小说",
                "vod_actor": author,
            })
        return items

    def _clean_text(self, raw):
        if not raw:
            return ""
        raw = re.sub(r'<[^>]+>', '', raw)
        raw = raw.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
        raw = re.sub(r'[ \t]+', ' ', raw)
        raw = re.sub(r'\s+', ' ', raw)
        return raw.strip()

    def _parse_pagecount(self, html):
        m = re.search(r'(\d+)\s*/\s*(\d+)\s*页', html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        last = re.findall(r'/(?:sort|top|full)[^"]*?_(\d+)\.html', html)
        if last:
            nums = [int(x) for x in last if x.isdigit()]
            if nums:
                return max(nums)
        return 1

    # ---------- 首页推荐 ----------
    def homeVideoContent(self):
        self._pick_host()
        html = self._get("/")
        items = []
        # 本站推荐区
        rm = re.search(r'newbook_recommend">(.*?)wap_rankinglist', html, re.S)
        if rm:
            items = self._parse_newbook_list(rm.group(1))
        if not items:
            items = self._parse_newbook_list(html)
        return {"list": items[:30]}

    # ---------- 分类列表 ----------
    def _build_cat_url(self, tid, page):
        if tid == "full":
            return "/full/%s.html" % page
        if tid.startswith("sort_"):
            sid = tid.split("_", 1)[1]
            return "/sort/%s_%s.html" % (sid, page)
        if tid.startswith("top_"):
            key = tid.split("_", 1)[1]
            return "/top/%s_%s.html" % (key, page)
        # 兼容纯数字旧格式
        if tid.isdigit():
            return "/sort/%s_%s.html" % (tid, page)
        return "/sort/%s_%s.html" % (tid, page)

    def categoryContent(self, tid, pg, filter, extend):
        self._pick_host()
        page = str(pg or "1")
        url = self._build_cat_url(str(tid), page)
        html = self._get(url)
        if not html:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        items = self._parse_list(html)
        pagecount = self._parse_pagecount(html)
        try:
            ipage = int(page)
        except Exception:
            ipage = 1
        if pagecount < ipage:
            pagecount = ipage
        return {
            "list": items,
            "page": ipage,
            "pagecount": pagecount,
            "limit": len(items) if items else 20,
            "total": pagecount * (len(items) if items else 20),
        }

    # ---------- 详情 + 章节 ----------
    def detailContent(self, ids):
        self._pick_host()
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        html = self._get("/book/%s/" % vid)
        if not html:
            return {"list": []}

        name = self._first(html, [
            r'catalog_info_right">\s*<h3>([^<]+)</h3>',
            r'<h3>([^<]+)</h3>',
        ], "未知")
        pic = self._first(html, [
            r'catalog_pic_left"><a[^>]*><img src="([^"]+)"',
            r'<img[^>]*src="([^"]+)"[^>]*width="100"',
        ], "")
        author = self._first(html, [
            r'catalog_author">作者：<a[^>]*>([^<]+)</a>',
            r'作者：<a[^>]*>([^<]+)</a>',
        ], "")
        # sort_finish_serial: s1=分类, s2=状态
        cat, status = "", "连载中"
        sm = re.search(r'sort_finish_serial"><span class="s1">([^<]*)</span><span class="s2">([^<]*)</span>', html)
        if sm:
            cat = sm.group(1).strip()
            status = sm.group(2).strip() or "连载中"
        intro = ""
        im = re.search(r'catalog_intor">(.*?)</div>', html, re.S)
        if im:
            intro = self._clean_text(im.group(1))
            intro = re.sub(r'^本书简介[：:]\s*', '', intro)
        update = self._first(html, [r'catalog_updatetime">更新：<span>([^<]+)</span>'], "")

        chapters = self._get_all_chapters(vid, html)

        plays = []
        for cname, cid in chapters:
            cname = cname.replace('$', ' ').replace('#', ' ').strip()
            if not cname:
                cname = "正文"
            plays.append("%s$nv_%s_%s" % (cname, vid, cid))
        play_url = "#".join(plays)

        remarks = status
        if cat:
            remarks = "%s | %s" % (cat, status)
        if chapters:
            remarks += " | 共%d章" % len(chapters)

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks,
            "vod_actor": author,
            "vod_director": "",
            "vod_content": (("[%s] " % update) if update else "") + intro,
            "vod_play_from": "肉书屋",
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    def _first(self, html, patterns, default=""):
        for p in patterns:
            m = re.search(p, html, re.S)
            if m:
                return m.group(1).strip()
        return default

    def _get_all_chapters(self, vid, first_html):
        """返回 [(章节名, cid), ...]，正序。走 pageselect 分页并发抓取"""
        page_urls = self._extract_page_urls(first_html)
        if not page_urls:
            return self._parse_chapter_list(first_html)

        if len(page_urls) > self.max_chapter_pages:
            page_urls = page_urls[:self.max_chapter_pages]

        results = {0: self._parse_chapter_list(first_html)}
        remaining = [(i, u) for i, u in enumerate(page_urls)][1:]

        if remaining:
            def work(idx, u):
                return idx, self._parse_chapter_list(self._get(u))
            with ThreadPoolExecutor(max_workers=16) as ex:
                futs = [ex.submit(work, i, u) for i, u in remaining]
                for fut in as_completed(futs):
                    try:
                        idx, chs = fut.result()
                        results[idx] = chs
                    except Exception:
                        pass

        merged = []
        seen = set()
        for i in range(len(page_urls)):
            for name, cid in results.get(i, []):
                if cid in seen:
                    continue
                seen.add(cid)
                merged.append((name, cid))
        return merged

    def _extract_page_urls(self, html):
        sel = re.search(r'name="pageselect".*?</select>', html, re.S)
        if not sel:
            return []
        opts = re.findall(r'<option[^>]+value="([^"]+)"', sel.group(0))
        urls = []
        seen = set()
        for v in opts:
            v = v.split('#')[0].strip()
            if not v:
                continue
            if v.startswith('/'):
                full = self.host + v
            elif v.startswith('http'):
                full = v
            else:
                continue
            if full not in seen:
                seen.add(full)
                urls.append(full)
        return urls

    def _parse_chapter_list(self, html):
        """定位"章节列表"区块（跳过"最新章节"倒序区），返回 [(name, cid)]"""
        if not html:
            return []
        idx = html.find('章节列表')
        scope = html[idx:] if idx != -1 else html
        m = re.search(r'<ul>(.*?)</ul>', scope, re.S)
        if not m:
            return []
        block = m.group(1)
        result = []
        for href, name in re.findall(r"<li><a\s+href=['\"]([^'\"]+)['\"][^>]*>([^<]+)</a></li>", block, re.S):
            name = name.strip()
            if not name:
                continue
            cm = re.search(r'/book/\d+/(\d+)\.html', href)
            if not cm:
                continue
            result.append((name, cm.group(1)))
        return result

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        self._pick_host()
        if not key:
            return {"list": [], "page": 1}
        url = self.host + "/search.php"
        try:
            kb = key.encode("gbk")
        except Exception:
            kb = key.encode("utf-8", errors="ignore")
        data = "searchkey=" + urllib.parse.quote(kb) + "&submit=" + urllib.parse.quote("搜索".encode("gbk"))
        html = ""
        try:
            rsp = self.post(url, data=data, headers=self.post_headers, timeout=15)
            html = self._decode(rsp)
        except Exception:
            html = ""
        items = self._parse_list(html)
        # 搜索唯一命中时站点可能直接 302 到详情页
        if not items:
            dm = re.search(r'catalog_info_right">\s*<h3>([^<]+)</h3>', html)
            if dm:
                bid = re.search(r'/book/(\d+)/', html)
                if bid:
                    items = [{"vod_id": bid.group(1), "vod_name": dm.group(1).strip(), "vod_pic": "", "vod_remarks": "小说"}]
        return {"list": items, "page": 1}

    # ---------- 播放（小说正文） ----------
    def playerContent(self, flag, id, vipFlags):
        self._pick_host()
        if not id:
            return {"parse": 0, "url": "", "header": self.headers}
        if id.startswith("nv_"):
            parts = id.split("_")
            if len(parts) >= 3:
                vid, cid = parts[1], parts[2]
                url = "%s/book/%s/%s.html" % (self.host, vid, cid)
                chapter = self._fetch_chapter(url)
                payload = json.dumps(chapter, ensure_ascii=False)
                return {"parse": 0, "url": "novel://" + payload, "header": self.headers}
        if id.startswith("novel://"):
            return {"parse": 0, "url": id, "header": self.headers}
        if id.startswith("http"):
            chapter = self._fetch_chapter(id)
            payload = json.dumps(chapter, ensure_ascii=False)
            return {"parse": 0, "url": "novel://" + payload, "header": self.headers}
        return {"parse": 0, "url": id, "header": self.headers}

    def _fetch_chapter(self, url):
        html = self._get(url)
        if not html:
            return {"title": "", "content": "无法获取章节内容"}
        title = self._first(html, [
            r'<div class="chapter_name">([^<]+)</div>',
            r'chapter_noveltitle">\s*<h3>[^<]*</h3>\s*<div[^>]*>([^<]+)</div>',
        ], "")
        content = ""
        cm = re.search(r'<div class="chapter_content">(.*?)</div>', html, re.S)
        if cm:
            raw = cm.group(1)
            raw = re.sub(r'<br\s*/?>', '\n', raw)
            raw = re.sub(r'<[^>]+>', '', raw)
            raw = raw.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
            raw = re.sub(r'[ \t]+', ' ', raw)
            raw = re.sub(r'\n{3,}', '\n\n', raw)
            content = raw.strip()
        if not content:
            content = "本章内容为空或格式不支持"
        return {"title": title, "content": content}

    # ---------- 推荐 ----------
    def recommendContent(self, ids, pg):
        return {"list": []}


if __name__ == "__main__":
    sp = Spider()
    sp.init()
    print(sp.getName())