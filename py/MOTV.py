# coding: utf-8
# ============================================================================
# 站点信息（换站只改这里）
#   名称   : motv (MOTV / motv.app 香港版)
#   主域   : https://motv.app  路径前缀 /hk/
#   类型   : 成人 AV 影视站 · zh-Hant 海螺(conch)版 MacCMS 系 · 纯 HTML 解析
#   图片CDN: https://imagecdn3.wbwyz.com
#   播放域 : 由 player_aaaa.url 动态给出(实测 https://ytexcphckc2.wbwyz.com)
#   备注   : MacCMS API 已关闭，走完整 HTML 解析(纯 re + html，无 lxml/bs4/Crypto)
#            取链两段式: play 页 player_aaaa.url -> watch 页 var src -> 补全 m3u8
#            拉流须带 Referer=播放域根，token 为 JWT 约 14 小时有效
#   验证时 : 2026-09-23
# ============================================================================
import re
import json
from urllib.parse import quote, urljoin, urlparse

import sys
sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    # ---- 站点常量 ----------------------------------------------------------
    MAIN = "https://motv.app"
    PREFIX = "/hk"

    UA = ("Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    # 首页 9 张分类卡片(法则16/17 静态硬编码)。
    #   type_id 直接用站点 vc_class 取值(可含逗号，如 "日本,有码"/"男同,女同")，
    #   分类列表走 query 格式 /hk/label/vodclass.html?vc_class=<type_id>
    #   ⚠️ 旧版用 path 格式 /vc_tid/N/... 站点忽略参数 → 所有分类返回同一默认清单(此为 bug 根因)
    CLASSES = [
        {"type_id": "日本HD",   "type_name": "日本HD"},
        {"type_id": "欧美HD",   "type_name": "欧美HD"},
        {"type_id": "日本,有码", "type_name": "日本有码"},
        {"type_id": "日本",     "type_name": "日本无码"},
        {"type_id": "中国",     "type_name": "国产原创"},
        {"type_id": "欧美",     "type_name": "欧美风情"},
        {"type_id": "动漫",     "type_name": "动画"},
        {"type_id": "Onlyfan",  "type_name": "Only Fans"},
        {"type_id": "男同,女同", "type_name": "同性影集"},
    ]

    # 排序维度(所有分类通用)
    _SORT = {"key": "by", "name": "排序", "value": [
        {"n": "时间", "v": "time"},
        {"n": "人气", "v": "hits"},
        {"n": "评分", "v": "score"},
    ]}

    def __init__(self):
        # 只做本地初始化，禁网络(法则16)
        self.extend = ""
        self.host = self.MAIN
        self.classes = self.CLASSES
        self.headers = {
            "User-Agent": self.UA,
            "Referer": self.MAIN + self.PREFIX + "/",
            "Cookie": "user_lang=hk",
            "Accept-Language": "zh-HK,zh;q=0.9",
        }
        self.filters = self._build_filters()

    def _build_filters(self):
        # 每个分类通用一个排序维度(分类本身即 vc_class，无需地区子维度)
        f = {}
        for c in self.CLASSES:
            f[c["type_id"]] = [self._SORT]
        return f

    def getName(self):
        return "motv"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 零网络，禁自动切域名(testing §7.0)
        self.extend = extend or ""

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return any(x in u for x in (".m3u8", ".mp4", ".flv", ".mkv", ".ts"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ========================================================================
    # 通用工具
    # ========================================================================
    def _full(self, path):
        if not path:
            return ""
        if path.startswith("http"):
            return path
        return urljoin(self.host + "/", path.lstrip("/"))

    @staticmethod
    def _parse_extend(extend):
        """支持 dict / '{by=time}' / 'by=time&class=日本' 三种格式(法则20)"""
        if not extend:
            return {}
        if isinstance(extend, dict):
            return {str(k): str(v) for k, v in extend.items()}
        s = str(extend).strip().strip("{}")
        out = {}
        for seg in re.split(r"[&,]", s):
            seg = seg.strip()
            if not seg:
                continue
            if "=" in seg:
                k, v = seg.split("=", 1)
                out[k.strip()] = v.strip()
        return out

    @staticmethod
    def _norm_ids(ids):
        """法则35：ids 可能是 list/str/int/bytes，禁止直接 ids[0]"""
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
    def _grab_balanced(s, start):
        """平衡括号匹配抽 JSON 对象(法则32)"""
        i = s.find("{", start)
        if i < 0:
            return None
        depth = 0
        for j in range(i, len(s)):
            c = s[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return s[i:j + 1]
        return None

    @staticmethod
    def _loose_json(raw):
        if not raw:
            return None
        for cand in (raw,
                     raw.replace("\\/", "/"),
                     raw.replace("\\/", "/").replace("'", '"')):
            try:
                return json.loads(cand)
            except Exception:
                continue
        return None

    def _parse_cards(self, html):
        """列表卡片解析：先切块再逐栏抽(法则14)。返回 vod list。"""
        if not html:
            return []
        blocks = [b for b in re.split(r'(?=<a\s+class="hl-item-thumb)', html)
                  if b.startswith("<a")]
        out = []
        for b in blocks:
            m_href = re.search(r'href="(/hk/vod/play/id/\d+[^"]*)"', b)
            m_vid = re.search(r'data-popedom-id="(\d+)"', b)
            if not m_href and not m_vid:
                continue
            # vod_id 取 data-popedom-id；缺失时从 href 的 id/N 兜底
            vid = m_vid.group(1) if m_vid else ""
            if not vid and m_href:
                mm = re.search(r'/id/(\d+)', m_href.group(1))
                vid = mm.group(1) if mm else ""
            if not vid:
                continue
            m_title = re.search(r'title="([^"]*)"', b)
            m_pic = (re.search(r'data-original="([^"]*)"', b)
                     or re.search(r'data-src="([^"]*)"', b)
                     or re.search(r'<img[^>]+src="([^"]*)"', b))
            m_rem = (re.search(r'remarks[^>]*>\s*([^<]+?)\s*<', b)
                     or re.search(r'hl-lc-remarks[^>]*>\s*([^<]+?)\s*<', b))
            title = (m_title.group(1) if m_title else "").strip()
            pic = (m_pic.group(1) if m_pic else "").strip()
            rem = (m_rem.group(1) if m_rem else "").strip()
            # 打包：vid|$|title|$|pic|$|remark (detailContent 拆包，含 $ 用 | 规避 法则21)
            packed = "|$|".join([vid, title, pic, rem])
            out.append({
                "vod_id": packed,
                "vod_name": title or "视频",
                "vod_pic": self._full(pic),
                "vod_remarks": rem,
            })
        return out

    # ========================================================================
    # 首页
    # ========================================================================
    def homeContent(self, filter):
        # 零网络，秒出(法则16)
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        url = self.host + self.PREFIX + "/"
        r = self.fetch(url, headers=self.headers)
        if not r or getattr(r, "status_code", 0) != 200:
            self.log({"home": "fetch_fail", "url": url})
            return {"list": []}
        vods = self._parse_cards(r.text)
        self.log({"home": "ok", "items": len(vods)})
        return {"list": vods}

    # ========================================================================
    # 分类列表
    # ========================================================================
    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg or "1")
        ext = self._parse_extend(extend)
        by = ext.get("by") or "time"
        vc = str(tid or "")

        # ⚠️ 必须走 query 格式(?vc_class=)，path 格式(/vc_tid/N/)站点会忽略参数，
        #    导致所有分类返回同一默认清单(此前 bug 根因)。
        #    vc_class 可含逗号(如 "日本,有码")，quote(safe="") 编码成 %2C 与站点一致。
        url = (self.host + "/hk/label/vodclass.html?vc_class=" + quote(vc, safe="")
               + "&by=" + quote(by, safe="") + "&order=desc&page=" + pg)

        r = self.fetch(url, headers=self.headers)
        status = getattr(r, "status_code", 0) if r else 0
        html = r.text if (r and status == 200) else ""
        vods = self._parse_cards(html)
        self.log({"category": tid, "request_url": url, "fetch_status": status,
                  "html_len": len(html), "items_count": len(vods)})

        try:
            ipg = int(pg)
        except Exception:
            ipg = 1
        # 满页(实测每页 12 卡)则认为还有下一页，否则到底
        pagecount = ipg + 1 if len(vods) >= 12 else ipg
        return {
            "list": vods,
            "page": ipg,
            "pagecount": pagecount,
            "limit": 12,
            "total": pagecount * 12,
        }

    # ========================================================================
    # 详情
    # ========================================================================
    def _skeleton(self, packed, name="", pic="", rem="解析中"):
        vid = str(packed).split("|$|")[0]
        return {"list": [{
            "vod_id": packed,
            "vod_name": name or "未知标题",
            "vod_pic": self._full(pic),
            "vod_remarks": rem,
            "vod_content": "",
            "vod_play_from": "自家线路",
            "vod_play_url": "正片$/hk/vod/play/id/%s/sid/1/nid/1.html" % vid,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:                       # 唯一允许返回空 list 的分支(法则35 L0)
            return {"list": []}
        ps = raw.split("|$|")
        vid = ps[0]
        old_name = ps[1] if len(ps) > 1 else ""
        old_pic = ps[2] if len(ps) > 2 else ""
        old_rem = ps[3] if len(ps) > 3 else ""

        if not vid.isdigit():
            # 兜底：从任意数字段抽 id
            m = re.search(r"\d+", vid)
            vid = m.group(0) if m else vid

        url = self.host + "/hk/vod/detail/id/" + vid + ".html"
        r = self.fetch(url, headers=self.headers)
        status = getattr(r, "status_code", 0) if r else 0
        html = r.text if (r and status == 200) else ""
        self.log({"detail": vid, "request_url": url, "fetch_status": status,
                  "html_len": len(html)})
        if not html or len(html) < 500:   # 站点对不存在 ID 常返回 200+空模板
            return self._skeleton(raw, old_name, old_pic, old_rem)

        # ---- 标题(多级兜底 法则35) ----
        #   站点真实片名来源(hk 版实测 2026-09-23)：
        #     ld+json Movie.name / <h1> / og:title 三处均为「纯片名」
        #   禁再用 re.split("[-_|]")——会把片名内的英文连字符和数字一起切掉
        name = old_name
        cand = []
        # L1 ld+json Movie.name
        for mm in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            try:
                o = json.loads(mm.group(1))
            except Exception:
                continue
            if isinstance(o, dict) and o.get("@type") == "Movie" and o.get("name"):
                cand.append(str(o["name"]).strip())
        # L2 h1(页面可能有多个，取首个非空且长度合理的)
        for mm in re.finditer(r"<h1[^>]*>(.*?)</h1>", html, re.S):
            t = re.sub(r"<[^>]+>", "", mm.group(1)).strip()
            if t:
                cand.append(t)
        # L3 og:title
        mm = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"', html)
        if mm and mm.group(1).strip():
            cand.append(mm.group(1).strip())
        # L4 <title> 兜底：只剥离《》与站名后缀，不做字符切分
        mm = re.search(r"<title>\s*(.*?)\s*</title>", html, re.S)
        if mm:
            t = re.sub(r"<[^>]+>", "", mm.group(1)).strip()
            t = re.sub(r"^《|》.*$", "", t).strip()
            if t:
                cand.append(t)
        for t in cand:
            t = re.sub(r"\s+", " ", t).strip()
            # 去掉包裹的《》与尾部站名
            t = t.strip("《》").strip()
            t = re.sub(r"[-_|]\s*MOTV.*$", "", t).strip()
            t = re.sub(r"MOTV最強全中文字幕AV網站$", "", t).strip()
            t = re.sub(r"\s*[-_|]\s*$", "", t).strip()
            if t and len(t) >= 1:
                name = t
                break
        # ---- 封面(og:image 优先) ----
        pic = old_pic
        for pat in (r'<meta[^>]+property="og:image"[^>]+content="([^"]*)"',
                    r'class="hl-item-thumb[^"]*"[^>]*data-original="([^"]*)"'):
            m = re.search(pat, html)
            if m and m.group(1).strip():
                pic = m.group(1).strip()
                break

        # ---- EM 资讯栏(注意 </em > 后有空格) ----
        info = {}
        for k, v in re.findall(r'<em class="hl-text-muted">([^<]+)</em\s*>\s*([^<]*)', html):
            key = k.strip().rstrip("：:").strip()
            val = v.strip()
            if key:
                info[key] = val
        def pick(*keys):
            for kk in keys:
                vv = info.get(kk, "").strip()
                if vv and vv not in ("未知", "未詳", "内详", "內詳"):
                    return vv
            return ""
        year = pick("年份")
        area = pick("地區", "地区")
        lang = pick("語言", "语言")
        director = pick("導演", "导演")
        actor = pick("主演", "演員", "演员")
        genre = pick("類型", "类型")
        remarks = info.get("更新", "").strip() or info.get("狀態", "").strip() or old_rem
        intro = pick("簡介", "简介", "劇情", "剧情")
        if not intro or intro in ("暂无简介", "暫無簡介"):
            parts = ["%s：%s" % (k.rstrip("：:"), v) for k, v in info.items()
                     if v and v not in ("未知", "未詳") and not k.startswith("簡介")]
            intro = "；".join(parts) if parts else (old_rem or "")
        elif genre:
            intro = "類型：%s；%s" % (genre, intro)

        # ---- 多线路(遍历所有，空组丢弃，同序对齐 法则9/35) ----
        routes = re.findall(
            r'<li[^>]*data-href="(/hk/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"'
            r'[^>]*>.*?hl-lc-1[^>]*>\s*([^<]+?)\s*</span>', html, re.S)
        froms, urls = [], []
        seen = set()
        for href, rname in routes:
            href = href.strip()
            rname = re.sub(r"<[^>]+>", "", rname).strip() or "线路"
            if href in seen:              # 两线路 url 相同也各留一条名(站方给不同 from)
                pass
            seen.add(href)
            froms.append(rname)
            urls.append("正片$" + href)   # 单集
        # 严格对齐
        if not froms:
            return self._skeleton(raw, name, pic, remarks or "暂无线路")
        if len(froms) != len(urls):
            n = min(len(froms), len(urls))
            froms, urls = froms[:n], urls[:n]

        vod = {
            "vod_id": raw,
            "vod_name": name or old_name or "视频",
            "vod_pic": self._full(pic),
            "vod_remarks": remarks,
            "vod_year": year,
            "vod_area": area,
            "vod_lang": lang,
            "vod_director": director,
            "vod_actor": actor,
            "vod_content": intro,
            "vod_play_from": "$$$".join(froms),
            "vod_play_url": "$$$".join(urls),
        }
        return {"list": [vod]}

    # ========================================================================
    # 搜索
    # ========================================================================
    def searchContent(self, key, quick, pg="1"):
        pg = str(pg or "1")
        q = quote(str(key), safe="")
        if pg == "1":
            url = self.host + "/hk/vod/search/wd/" + q + ".html"
        else:
            url = self.host + "/hk/vod/search/page/" + pg + "/wd/" + q + ".html"
        r = self.fetch(url, headers=self.headers)
        status = getattr(r, "status_code", 0) if r else 0
        html = r.text if (r and status == 200) else ""
        vods = self._parse_cards(html)
        self.log({"search": key, "request_url": url, "fetch_status": status,
                  "html_len": len(html), "items_count": len(vods)})
        return {"list": vods, "page": int(pg) if pg.isdigit() else 1}

    # ========================================================================
    # 播放：两段式取直链(法则7/32)
    #   play 页 player_aaaa.url(watch 页) -> watch 页 var src -> 补全 m3u8
    # ========================================================================
    def playerContent(self, flag, id, vipFlags):
        pid = self._norm_ids(id)
        low = pid.lower()

        # 已是直链
        if low.endswith(".m3u8") or ".m3u8?" in low or low.endswith(".mp4"):
            return {"parse": 0, "url": pid,
                    "header": {"User-Agent": self.UA, "Referer": self.host + "/"}}

        play_url = self._full(pid)
        r = self.fetch(play_url, headers=self.headers)
        if not r or getattr(r, "status_code", 0) != 200:
            self.log({"player": "play_fetch_fail", "url": play_url})
            return {"parse": 1, "url": play_url, "header": self.headers}
        ptxt = r.text

        # L2 播放器变量：平衡括号抽 player_aaaa
        k = ptxt.find("player_aaaa")
        obj = self._loose_json(self._grab_balanced(ptxt, k)) if k >= 0 else None
        watch_url = ""
        if obj and isinstance(obj, dict):
            watch_url = str(obj.get("url") or "")
        # L5 全文正则兜底
        if not watch_url:
            m = re.search(r'"url"\s*:\s*"([^"]+)"', ptxt)
            if m:
                watch_url = m.group(1).replace("\\/", "/")
        if not watch_url:
            self.log({"player": "no_player_url", "url": play_url})
            return {"parse": 1, "url": play_url, "header": self.headers}

        watch_url = watch_url.replace("\\/", "/")
        wl = watch_url.lower()
        # watch_url 本身即直链
        if wl.endswith(".m3u8") or ".m3u8?" in wl or wl.endswith(".mp4"):
            pu = urlparse(watch_url)
            ref = "%s://%s/" % (pu.scheme, pu.netloc)
            return {"parse": 0, "url": watch_url,
                    "header": {"User-Agent": self.UA, "Referer": ref}}

        # 取 watch 页解析 var src
        # ⚠️ watch 域对 Referer 校验：Referer 必须是站点页(motv.app)，
        #    用 watch 域自身或空 Referer 会 401(实测)
        pu = urlparse(watch_url)
        watch_host = "%s://%s" % (pu.scheme, pu.netloc)
        wheaders = {
            "User-Agent": self.UA,
            "Referer": play_url,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-HK,zh;q=0.9",
        }
        r2 = self.fetch(watch_url, headers=wheaders)
        if not r2 or getattr(r2, "status_code", 0) != 200:
            self.log({"player": "watch_fetch_fail", "url": watch_url})
            return {"parse": 1, "url": watch_url, "header": wheaders}
        wtxt = r2.text
        m = (re.search(r"var\s+src\s*=\s*'([^']+)'", wtxt)
             or re.search(r'var\s+src\s*=\s*"([^"]+)"', wtxt)
             or re.search(r'["\']?src["\']?\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']', wtxt))
        if not m:
            self.log({"player": "no_src", "watch": watch_url})
            return {"parse": 1, "url": watch_url, "header": wheaders}
        src = m.group(1).replace("\\/", "/")
        m3u8 = src if src.startswith("http") else urljoin(watch_host + "/", src.lstrip("/"))
        self.log({"player": "ok", "m3u8": m3u8[:80]})
        # 取证显示无广告特征，直接返回原始直链(法则30)
        return {"parse": 0, "url": m3u8,
                "header": {"User-Agent": self.UA, "Referer": watch_host + "/"}}

    def localProxy(self, param):
        # 直链可播、无广告特征，无需代理(法则30)
        return [404, "text/plain", b""]
