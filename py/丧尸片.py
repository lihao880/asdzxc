# -*- coding: utf-8 -*-
"""
丧尸片大全 (sangshipian.com) - 纯 Python TVBox 源
适配 FongMi / TVBox / 影视仓系壳。

站点结构 (已真抓验证 2026-11-03):
- 不是标准 AppleCMS API: /api.php/provide/vod 真实 404 (站点用自定义 URL 重写 + 苹果CMS fed- 模板)。
- 分类 (首页导航, 路径固定):
    * 丧尸电影  : /sangshidianying/1-page{N}.html   (type_id=1)
    * 丧尸电视剧: /sangshidianshiju/2-page{N}.html   (type_id=2)
    * 丧尸动漫  : /sangshidongman/3-page{N}.html      (type_id=3)
- 列表卡片:
    * 海报 : <a class="fed-list-pics ..." href="/{section}/vod{ID}.html" data-original="http://pic.sangshipian.com/Uploads/...">
    * 标题 : 兄弟 <a class="fed-list-title ..." href="/{section}/vod{ID}.html">标题</a> (按 href 合并)
- 详情页: /{section}/vod{ID}.html (og:title=标题; 海报走 pic.sangshipian.com)
           选集: /{section}/play{ID}-{源S}-{集E}.html (如 /sangshidianying/play150-4-1.html)
- 播放页: /{section}/play{ID}-{S}-{E}.html 内含 var url = "https://...m3u8" (真实播放地址)
   站点自身用 iframe 把该 m3u8 喂给解析接口 api.taiju.bid 播放, 但 m3u8 经 DPlayer 以 no-referrer 直连,
   无防盗链, 故 spider 直接取 var url 直出 parse:0 即可, 无需走解析接口。

域名收口 (2026-11-03 真抓):
- DOMAINS : 仅 www.sangshipian.com 实测可用 (非 www 返回 520 Cloudflare 错误, 已排除)
- IMG_HOSTS: pic.sangshipian.com (海报图床, 实测 200)
- MEDIA   : m3u8 由播放页 var url 动态给出 (多落在 lz-cdn*.com6.com 等 VIP CDN), 已验证直连; 列已知项备查
"""
import re
import json
import urllib.parse
import requests

from base.spider import Spider


class Spider(Spider):
    # ---- 域名收口常量 (写/改源时搜到的域名一律进这里) ----
    DOMAINS = [
        "https://www.sangshipian.com",   # 主站 (实测唯一可用, 非 www 返回 520)
    ]
    # 图片域名: 海报图床 (独立于前端主域)
    IMG_HOSTS = [
        "https://pic.sangshipian.com",   # 海报 CDN (实测 200)
    ]
    # 媒体 CDN: m3u8 由播放页 var url 动态给出, 这里列已知项备查/容灾
    MEDIA_HOSTS = [
        "https://vip1.lz-cdn1.com6.com",  # 已见播放地址落点
    ]

    # 分类: (type_id, section路径, 显示名)
    CATEGORIES = [
        ("1", "sangshidianying", "丧尸电影"),
        ("2", "sangshidianshiju", "丧尸电视剧"),
        ("3", "sangshidongman", "丧尸动漫"),
    ]
    _SEC = {tid: sec for tid, sec, _ in CATEGORIES}

    def init(self, ext=None):
        self.host = self.DOMAINS[0]
        self.uagent = ("Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36")
        self.headers = {
            "User-Agent": self.uagent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.play_header = {
            "User-Agent": self.uagent,
            "Referer": self.host + "/",
        }

    # ---------- 工具 ----------
    def _request(self, path, timeout=20, referer=None):
        """带域名容灾的请求: 从当前 self.host 起按 DOMAINS 顺序 failover; 单次失败自动重试一次。
        path 可为相对路径(按 DOMAINS 拼 host)或绝对 URL(直接用)。"""
        if self.host not in self.DOMAINS:
            self.DOMAINS.insert(0, self.host)
        if path.startswith("http://") or path.startswith("https://"):
            urls = [path]
        else:
            start = self.DOMAINS.index(self.host)
            urls = [self.DOMAINS[(start + i) % len(self.DOMAINS)].rstrip("/") + path
                    for i in range(len(self.DOMAINS))]
        for url in urls:
            hd = dict(self.headers)
            hd["Referer"] = referer or (self.host + "/")
            for _ in range(2):  # 偶发空返回/抖动, 重试一次
                try:
                    r = requests.get(url, headers=hd, timeout=timeout, allow_redirects=True)
                    if r.status_code == 200:
                        # 站点部分页面 Content-Type 不带 charset, requests 会按 Latin-1 解码导致中文乱码,
                        # 强制以 UTF-8 解码 (页面均声明 charset=utf-8)。
                        r.encoding = "utf-8"
                        text = r.text
                        if text:
                            if url.startswith("http"):
                                self.host = "%s://%s" % (url.split("://")[0],
                                                         url.split("://")[1].split("/")[0])
                            return text
                    break  # 非 200 直接换 host/退出, 不重试
                except Exception:
                    continue
        return ""

    def _parse_list(self, html):
        """解析视频卡片列表。

        卡片: 海报 <a class="fed-list-pics" href="/{sec}/vod{ID}.html" data-original="...">
              + 标题 <a class="fed-list-title" href="/{sec}/vod{ID}.html">标题</a> (兄弟节点)
        海报与标题同 href, 分两次抓再按 href 合并, 绝不串位。
        海报为 pic.sangshipian.com 绝对地址, 统一收口到 IMG_HOSTS 协议(https)。
        """
        if not html:
            return []
        out = []
        seen = set()
        # 1) 海报 + id (用完整相对路径做 key, 跨区不重号)
        for m in re.finditer(
                r'<a class="fed-list-pics[^"]*" href="(/([a-z]+)/vod(\d+)\.html)"[^>]*data-original="([^"]+)"',
                html):
            href, pic = m.group(1), m.group(4)
            if href in seen:
                continue
            seen.add(href)
            p = pic.strip()
            if p.startswith("http://"):
                p = "https://" + p[7:]
            out.append({"vod_id": href, "vod_pic": p, "vod_name": "", "vod_remarks": ""})
        # 2) 标题 (仅匹配 class=fed-list-title 的锚点; 兼容搜索页标题含 <font> 高亮,
        #    抓出整段后剥标签; 跳过 "0.0正片" 类备注; 同 href 取最长避免被 pic 锚点干扰)
        title_map = {}
        for m in re.finditer(
                r'<a[^>]*fed-list-title[^>]*href="(/[a-z]+/vod\d+\.html)">(.*?)</a>', html):
            href, txt = m.group(1), re.sub(r'<[^>]+>', '', m.group(2)).strip()
            if not txt or re.match(r'^\d+\.\d', txt):  # 跳过 "0.0正片/HD高清/全集" 等备注
                continue
            if href not in title_map or len(txt) > len(title_map[href]):
                title_map[href] = txt
        for it in out:
            if it["vod_id"] in title_map:
                it["vod_name"] = title_map[it["vod_id"]]
        return out

    def _pagecount(self, html, sec, sub):
        nums = re.findall(r'/%s/%s-page(\d+)\.html' % (re.escape(sec), re.escape(sub)), html or "")
        nums = [int(x) for x in nums if x.isdigit()]
        return max(nums) if nums else 999

    # ---------- 契约方法 ----------
    def homeContent(self, filter_):
        html = self._request("/")
        classes = [{"type_id": tid, "type_name": name}
                   for tid, _sec, name in self.CATEGORIES]
        return {"class": classes, "list": self._parse_list(html), "filters": {}}

    def categoryContent(self, tid, pg, filter_, ext):
        tid = str(tid or "1")
        sec = self._SEC.get(tid, "sangshidianying")
        try:
            pg = int(str(pg))
        except Exception:
            pg = 1
        pg = max(pg, 1)
        path = "/%s/%s-page%d.html" % (sec, tid, pg)
        html = self._request(path)
        items = self._parse_list(html) if html else []
        return {
            "list": items,
            "page": pg,
            "pagecount": self._pagecount(html, sec, tid),
            "limit": 20,
            "total": 0,
        }

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) else ids
        vid = str(vid or "").strip()
        # 兼容传完整链接的情况
        if vid.startswith("http"):
            m = re.search(r'(/[a-z]+/vod\d+\.html)', vid)
            vid = m.group(1) if m else vid

        html = self._request(vid)
        if not html:
            return {"list": [{"vod_id": vid, "vod_play_url": ""}]}

        # 标题
        name = ""
        m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        if m:
            name = m.group(1).strip()
        if not name:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                name = m.group(1).split("-")[0].strip()

        # 海报
        pic = ""
        m = re.search(r'property="og:image" content="([^"]+)"', html)
        if not m:
            m = re.search(r'data-original="(https?://[^\s"]+)"', html)
        if m:
            p = m.group(1).strip()
            pic = self.host + p if p.startswith("/") else p
            if pic.startswith("http://"):
                pic = "https://" + pic[7:]

        # 选集: /{section}/play{VID}-{源S}-{集E}.html
        # 只取本片 vid 的播放链接, 必须排除页面里"相关推荐"等其它影片的 play 链接。
        mvid = re.search(r'/([a-z]+)/vod(\d+)\.html', vid)
        sec = mvid.group(1) if mvid else ""
        cur_id = mvid.group(2) if mvid else ""
        plays = (re.findall(
            r'/' + re.escape(sec) + r'/play' + re.escape(cur_id) + r'-(\d+)-(\d+)\.html', html)
            if (sec and cur_id) else [])
        sources = {}   # 源S -> [(集E, href)]
        order = []
        for s, e in plays:
            if s not in sources:
                sources[s] = []
                order.append(s)
            sources[s].append((int(e), "/%s/play%s-%s-%s.html" % (sec, cur_id, s, e)))
        if not sources:
            return {"list": [{
                "vod_id": vid, "vod_name": name, "vod_pic": pic,
                "vod_play_from": "提示", "vod_play_url": "未找到播放地址$%s" % vid,
            }]}

        froms, urls = [], []
        for idx, s in enumerate(order, 1):
            eps = sorted(sources[s], key=lambda x: x[0])
            line = "#".join("%d$%s" % (e, h) for e, h in eps)
            froms.append("线路%d" % idx)
            urls.append(line)
        return {"list": [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": "",
            "vod_play_from": "$$$".join(froms),
            "vod_play_url": "$$$".join(urls),
            "type_name": "", "vod_year": "", "vod_area": "",
            "vod_remarks": "", "vod_actor": "", "vod_director": "",
        }]}

    def searchContent(self, key, quick, pg):
        try:
            pg = int(str(pg))
        except Exception:
            pg = 1
        pg = max(pg, 1)
        wd = urllib.parse.quote(str(key or ""))
        path = "/vod-search-wd-%s-page%d.html" % (wd, pg)
        html = self._request(path)
        return {"list": self._parse_list(html) if html else [], "pagecount": 999}

    def playerContent(self, flag, id, vipFlags=None):
        # id 可能: 播放页相对路径 / 完整 m3u8 直链
        pid = str(id or "").strip()
        if "$" in pid:  # 兼容部分壳把 "线路名$地址" 整体当作 id
            pid = pid.rsplit("$", 1)[-1].strip()
        if not pid:
            return {"parse": 0, "url": "", "header": {}}
        # 已经是 m3u8/mp4 直链
        if pid.startswith("http") and re.search(r"\.(m3u8|mp4|mkv|flv|m4s)(\?|$)", pid, re.IGNORECASE):
            return {"parse": 0, "url": pid, "header": self.play_header}
        # 否则视作播放页路径(相对或绝对均可), 取 var url (真实 m3u8)
        # 播放页 Referer 用对应详情页 (浏览器从详情页点播放, Referer 即详情页), 避免被空返回
        ref = None
        mref = re.search(r'/([a-z]+)/play(\d+)-', pid)
        if mref:
            ref = self.host.rstrip("/") + "/%s/vod%s.html" % (mref.group(1), mref.group(2))
        html = self._request(pid, referer=ref)
        if html:
            m = re.search(r'var\s+url\s*=\s*"([^"]+)"', html)
            if m:
                u = m.group(1).replace(r"\/", "/")
                return {"parse": 0, "url": u, "header": self.play_header}
        return {"parse": 0, "url": "", "header": self.play_header,
                "msg": "未找到播放地址"}
