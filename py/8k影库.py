# coding: utf-8
# ============================================================
# 站点: 8k影库 (8kyingku)
# 主域名: https://8kyingku6296079.buzz
# 备用域名: https://8kyingku.buzz
# 发布页: 无（域名带随机数字，属轮换域名站）
# 内容类型: 视频（成人向 MacCMS 风格 HTML 站）
# 特殊说明:
#   - Cloudflare 前置，需完整浏览器 UA，并做 429 退避
#   - 列表页 /video/type/{tid}/{pg}.html
#   - 详情页 /video/info/{id}.html -> 播放页 /video/play/{id}.html
#   - 播放页内嵌 iframe /static/html/player09.html?id=https://{aa_id}&rs=60
#   - 真实 m3u8 通过 /aa/{aa_id} 获取，需 Referer=player09.html + JSESSIONID
#   - m3u8 经取证无广告、无KEY、非图片流 -> 直链不代理
# 最后验证时间: 2026-09-13
# 来源: 用户提供
# ============================================================
import re
import time
from urllib.parse import quote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        # 零网络：只做本地初始化
        self.host = "https://8kyingku6296079.buzz"
        self.backup_hosts = ["https://8kyingku.buzz"]
        self._cached_host = ""

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
        }

        # 分类：来自首页实测真实分类
        self.classes = [
            {"type_id": "868", "type_name": "最近加精"},
            {"type_id": "869", "type_name": "收藏最多"},
            {"type_id": "870", "type_name": "本月最热"},
            {"type_id": "871", "type_name": "最近更新"},
            {"type_id": "872", "type_name": "91原创"},
            {"type_id": "952", "type_name": "日韩系列"},
            {"type_id": "953", "type_name": "欧美巨屌"},
            {"type_id": "954", "type_name": "步兵无码"},
            {"type_id": "938", "type_name": "国产精品"},
            {"type_id": "939", "type_name": "华语AV"},
            {"type_id": "940", "type_name": "黑料吃瓜"},
            {"type_id": "941", "type_name": "欧美"},
            {"type_id": "944", "type_name": "学生"},
            {"type_id": "946", "type_name": "探花"},
            {"type_id": "947", "type_name": "日本无码"},
            {"type_id": "948", "type_name": "日本有码"},
            {"type_id": "949", "type_name": "主播网红"},
            {"type_id": "950", "type_name": "日本素人"},
            {"type_id": "426", "type_name": "国产视频"},
            {"type_id": "427", "type_name": "中文字幕"},
            {"type_id": "428", "type_name": "国产传媒"},
            {"type_id": "431", "type_name": "欧美无码"},
            {"type_id": "433", "type_name": "制服诱惑"},
            {"type_id": "434", "type_name": "国产主播"},
            {"type_id": "435", "type_name": "激情动漫"},
            {"type_id": "436", "type_name": "明星换脸"},
            {"type_id": "437", "type_name": "抖阴视频"},
            {"type_id": "438", "type_name": "女优明星"},
            {"type_id": "441", "type_name": "网曝黑料"},
            {"type_id": "443", "type_name": "伦理三级"},
            {"type_id": "444", "type_name": "AV解说"},
            {"type_id": "445", "type_name": "SM调教"},
            {"type_id": "446", "type_name": "萝莉少女"},
            {"type_id": "448", "type_name": "女同性恋"},
            {"type_id": "449", "type_name": "网红头条"},
            {"type_id": "451", "type_name": "人妖系列"},
            {"type_id": "452", "type_name": "韩国主播"},
            {"type_id": "453", "type_name": "VR视角"},
        ]

        # 首页无真实筛选 DOM/API，不伪造假筛选
        self.filters = {}

    # ---------- 基础 ----------
    def getName(self):
        return "8k影库"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 零网络
        self.extend = extend or ""

    def destroy(self):
        self._cached_host = ""

    # ---------- 内部工具 ----------
    def _base(self):
        return self._cached_host or self.host

    def _hosts(self):
        hosts = []
        if self._cached_host:
            hosts.append(self._cached_host)
        hosts.append(self.host)
        for h in self.backup_hosts:
            if h not in hosts:
                hosts.append(h)
        return hosts

    def _fetch_resp(self, path, headers=None, retry=1):
        """返回 (text, resp, host)，带多域名容灾 + 429 退避"""
        h = dict(self.headers)
        if headers:
            h.update(headers)
        for host in self._hosts():
            url = path if path.startswith("http") else host + path
            for attempt in range(retry + 1):
                try:
                    r = self.fetch(url, headers=h, timeout=15)
                except Exception:
                    r = None
                if r and getattr(r, "status_code", 0) == 200:
                    if not self._cached_host:
                        self._cached_host = host
                    return (r.text or ""), r, host
                status = getattr(r, "status_code", 0) if r else 0
                if status in (429, 503) and attempt < retry:
                    time.sleep(1.2)
                    continue
                break
        return "", None, ""

    def _fetch_text(self, path, headers=None, retry=1):
        """返回文本或空串，带多域名容灾 + 429 退避"""
        text, _, _ = self._fetch_resp(path, headers=headers, retry=retry)
        return text

    @staticmethod
    def _norm_ids(ids):
        """法则35：ids 可能是 list/str/int/bytes"""
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    @staticmethod
    def _clean_text(s):
        if not s:
            return ""
        s = re.sub(r"<[^>]+>", "", s)
        s = s.replace("&nbsp;", " ").replace("&amp;", "&")
        return s.strip()

    def _parse_list_html(self, html):
        """解析列表卡片：div.list > a[href=/video/info/{id}.html]"""
        items = []
        if not html:
            return items
        blocks = re.findall(r'<div class="list"\s*>(.*?)</a>\s*</div>', html, re.S)
        if blocks:
            for blk in blocks:
                href_m = re.search(r'href=[\'"](/video/info/(\d+)\.html)[\'"]', blk)
                if not href_m:
                    continue
                vid = href_m.group(2)
                name = ""
                nm = re.search(r'title=[\'"]([^\'"]*)[\'"]', blk)
                if nm:
                    name = nm.group(1)
                if not name:
                    pm = re.search(r"<p>(.*?)</p>", blk, re.S)
                    if pm:
                        name = self._clean_text(pm.group(1))
                pic = ""
                pim = re.search(r'<img[^>]+src=[\'"]([^\'"]+)[\'"]', blk)
                if pim:
                    pic = pim.group(1)
                remark = ""
                tm = re.search(r'<span class="time">([^<]*)</span>', blk)
                if tm:
                    remark = tm.group(1).strip()
                items.append({
                    "vod_id": vid,
                    "vod_name": self._clean_text(name),
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })
            return items
        # 正则兜底：直接抓 a[href=/video/info/]
        for m in re.finditer(
            r'<a[^>]+href=[\'"](/video/info/\d+\.html)[\'"][^>]*title=[\'"]([^\'"]*)[\'"][^>]*>(.*?)</a>',
            html, re.S):
            href, title, inner = m.group(1), m.group(2), m.group(3)
            vid = re.search(r"/video/info/(\d+)\.html", href)
            pic = ""
            pm = re.search(r'<img[^>]+src=[\'"]([^\'"]+)[\'"]', inner)
            if pm:
                pic = pm.group(1)
            tm = re.search(r'<span class="time">([^<]*)</span>', inner)
            remark = tm.group(1).strip() if tm else ""
            if vid:
                items.append({
                    "vod_id": vid.group(1),
                    "vod_name": self._clean_text(title),
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })
        return items

    # ---------- 首页 ----------
    def homeContent(self, filter):
        # 零网络
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_text("/video/type/868.html")
        return {"list": self._parse_list_html(html)}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        if page == "1":
            path = "/video/type/%s.html" % tid
        else:
            path = "/video/type/%s/%s.html" % (tid, page)
        html = self._fetch_text(path)
        items = self._parse_list_html(html)
        pagecount = self._parse_pagecount(html)
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20,
        }

    def _parse_pagecount(self, html):
        if not html:
            return 1
        m = re.search(r"当前\d+/(\d+)页", html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return 1

    # ---------- 详情 ----------
    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        vid = raw.split("|$|")[0].split("$")[0]
        path = "/video/info/%s.html" % vid
        html = self._fetch_text(path)
        if not html or len(html) < 500:
            return self._skeleton(vid)
        name = self._pick_detail_field(html, [
            r"<h1[^>]*>(.*?)</h1>",
            r'<meta property="og:title" content="([^"]*)"',
            r"<title>(.*?)</title>",
        ])
        name = self._clean_text(name)
        name = re.sub(r"｜.*$", "", name).strip()
        pic = self._pick_detail_field(html, [
            r'<meta property="og:image" content="([^"]*)"',
            r'<img[^>]+class="[^"]*lazy[^"]*"[^>]+src="([^"]*)"',
            r'<img[^>]+src="([^"]*)"',
        ])
        content = self._pick_detail_field(html, [r'<meta name="description" content="([^"]*)"'])
        content = self._clean_text(content)

        if not name:
            return self._skeleton(vid)

        play_page = "/video/play/%s.html" % vid
        vod = {
            "vod_id": raw,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": content,
            "vod_play_from": "播放",
            "vod_play_url": "播放$" + play_page,
        }
        return {"list": [vod]}

    def _pick_detail_field(self, html, patterns):
        for p in patterns:
            m = re.search(p, html, re.S)
            if m:
                v = m.group(1).strip()
                if v:
                    return v
        return ""

    def _skeleton(self, vid):
        return {"list": [{
            "vod_id": vid,
            "vod_name": "未知标题",
            "vod_pic": "",
            "vod_remarks": "解析中",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": "播放$/video/play/%s.html" % vid,
        }]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        page = str(pg or "1")
        kw = quote(str(key or ""), safe="")
        if page == "1":
            path = "/search/%s.html" % kw
        else:
            path = "/search/%s/n/%s.html" % (kw, page)
        html = self._fetch_text(path)
        items = self._parse_list_html(html)
        return {"list": items, "page": int(page)}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        pid = str(id or "")
        if "$" in pid:
            pid = pid.split("$", 1)[1]
        pid = pid.strip()
        if not pid:
            return {"parse": 0, "url": "", "header": {}}
        base = self._base()
        if pid.startswith("//"):
            pid = "https:" + pid
        elif pid.startswith("/"):
            pid = base + pid
        elif not pid.startswith("http"):
            pid = base + "/" + pid.lstrip("/")

        play_html, resp, host = self._fetch_resp(pid)
        if not play_html:
            return {"parse": 1, "url": pid, "header": self.headers}

        # 提取 iframe 中的 aa_id（多种格式兜底）
        aa_id = ""
        for pat in (
            r"player09\.html\?id=https?://([0-9a-zA-Z]+)",
            r"[?&]id=https?://([0-9a-zA-Z]+)",
            r"/aa/([0-9a-zA-Z]+)",
        ):
            m = re.search(pat, play_html)
            if m:
                aa_id = m.group(1)
                break
        if not aa_id:
            return {"parse": 1, "url": pid, "header": self.headers}

        # 预热 player09.html 建立会话，让沙盒持有 JSESSIONID
        try:
            self.fetch(host + "/static/html/player09.html",
                       headers=self.headers, timeout=10)
        except Exception:
            pass

        # 取播放页响应里的 JSESSIONID（可选，作为显式 Cookie 兜底）
        cookie = ""
        try:
            setc = resp.headers.get("Set-Cookie", "") if resp is not None else ""
            cm = re.search(r"JSESSIONID=([^;]+)", setc or "")
            if cm:
                cookie = "JSESSIONID=" + cm.group(1)
        except Exception:
            cookie = ""

        # 多组尝试：优先复用会话（不显式带 Cookie），失败再带 Cookie
        attempt_headers = [
            {"Referer": host + "/static/html/player09.html", "X-Requested-With": "XMLHttpRequest"},
        ]
        if cookie:
            attempt_headers.append({
                "Referer": host + "/static/html/player09.html",
                "X-Requested-With": "XMLHttpRequest",
                "Cookie": cookie,
            })
        # 最后兜底：直接以播放页为 Referer
        attempt_headers.append({"Referer": pid})

        real = ""
        for hd in attempt_headers:
            aa_text = self._fetch_text("/aa/" + aa_id, headers=hd)
            cand = (aa_text or "").strip().replace("&amp;", "&").replace("\\/", "/").strip()
            if cand.startswith("http"):
                real = cand
                break

        if not real:
            return {"parse": 1, "url": pid, "header": self.headers}

        # m3u8 经取证无广告、非图片流 -> 直链，不代理
        return {"parse": 0, "url": real, "header": {"User-Agent": self.headers["User-Agent"]}}

    # ---------- 推荐 ----------
    def recommendContent(self, ids, pg):
        try:
            vid = self._norm_ids(ids)
            html = self._fetch_text("/video/info/%s.html" % vid)
            items = self._parse_list_html(html)
            items = [x for x in items if str(x.get("vod_id")) != str(vid)]
            return {"list": items[:12]}
        except Exception:
            return {"list": []}

    def localProxy(self, param):
        return [404, "text/plain; charset=utf-8", "not implemented"]