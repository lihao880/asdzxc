# coding: utf-8
"""
站点: CartoonPorno (卡通动漫色情站)
主域名: https://www.cartoonporno.cc
内容类型: 成人动漫/3D卡通短视频 (mp4直链)
备用域名: 无
发布页: 无
特殊说明:
  - 列表卡片 URL = data-s + data-i + data-u + data-q (JS 拼装)
  - 分页参数 p (非 page/pg)
  - 播放源在 embed 页: 详情页 JSON-LD embedUrl -> /embed/{vid}/?hl=zh -> <source src="mp4">
  - mp4 直链带时效签名 (utc/e)，需每次实时抓 embed 页
最后验证时间: 2026-09-20
来源: 自主分析
"""
import json
import re
from urllib.parse import quote, urljoin, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.host = "https://www.cartoonporno.cc"
        self.hl = "zh"
        self.classes = [
            {"type_id": "217/3d", "type_name": "3D性感"},
            {"type_id": "231/anime", "type_name": "动漫诱惑"},
            {"type_id": "447/hentai", "type_name": "动漫色情"},
            {"type_id": "218/3d-cartoon", "type_name": "3D卡通诱惑"},
            {"type_id": "445/hardcore", "type_name": "激烈硬核"},
            {"type_id": "494/lesbian", "type_name": "女同性恋"},
            {"type_id": "276/blowjob", "type_name": "口交快感"},
            {"type_id": "338/creampie", "type_name": "体内射精"},
            {"type_id": "180/demons", "type_name": "Demons"},
            {"type_id": "376/erotic", "type_name": "色情诱惑"},
            {"type_id": "725/uncensored", "type_name": "无码直击"},
            {"type_id": "234/ass", "type_name": "翘臀诱惑"},
            {"type_id": "184/big-tits", "type_name": "巨乳诱惑"},
            {"type_id": "327/comic", "type_name": "漫画风"},
        ]
        self.filters = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
    def getName(self):
        return "CartoonPorno"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 零网络
        self.extend = extend or ""

    def homeContent(self, filter):
        # 零网络
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def _fetch(self, url, headers=None):
        h = dict(self.headers)
        if headers:
            h.update(headers)
        try:
            r = self.fetch(url, headers=h, timeout=15)
            if not r or r.status_code != 200:
                self.log({"fetch_fail": url, "status": r.status_code if r else None})
                return ""
            return r.text or ""
        except Exception as e:
            self.log({"fetch_exc": url, "error": str(e)})
            return ""

    # ---------- 列表解析 ----------
    def _build_url(self, ds, di, du, dq):
        """按站点 JS: data-s + data-i + data-u + data-q 拼详情 URL"""
        return (ds or "") + str(di or "") + (du or "") + (dq or "")

    def _parse_cards(self, html):
        out = []
        if not html:
            return out
        # 每张卡片以 <div class="item"> 开头，内含 <a class='...lnk' data-s=.. data-i=.. data-u=.. data-q=..>
        blocks = re.split(r'<div class="item">', html)
        for blk in blocks[1:]:
            am = re.search(
                r"<a[^>]*class=['\"][^'\"]*lnk[^'\"]*['\"][^>]*data-s=['\"]([^'\"]*)['\"][^>]*data-i=['\"]([^'\"]*)['\"][^>]*data-u=['\"]([^'\"]*)['\"][^>]*data-q=['\"]([^'\"]*)['\"][^>]*title=['\"]([^'\"]*)['\"]",
                blk, re.S)
            if not am:
                continue
            ds, di, du, dq, title = am.group(1), am.group(2), am.group(3), am.group(4), am.group(5)
            link = self._build_url(ds, di, du, dq)
            # 封面: data-src
            pm = re.search(r'data-src=["\']([^"\']+)["\']', blk)
            pic = pm.group(1) if pm else ""
            if pic.startswith("//"):
                pic = "https:" + pic
            # 时长
            tm = re.search(r'<span class="item-time">([^<]+)</span>', blk)
            remark = tm.group(1).strip() if tm else ""
            out.append({
                "vod_id": di,
                "vod_name": self._unescape(title),
                "vod_pic": pic,
                "vod_remarks": remark,
                "vod_link": link,
            })
        return out

    @staticmethod
    def _unescape(s):
        if not s:
            return ""
        return (s.replace("&amp;", "&").replace("&quot;", '"')
                 .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))

    def _to_list(self, cards):
        res = []
        for c in cards:
            vid = str(c.get("vod_id") or "")
            name = str(c.get("vod_name") or "").replace("|$|", " ").replace("$", " ")
            pic = str(c.get("vod_pic") or "")
            remark = str(c.get("vod_remarks") or "").replace("|$|", " ").replace("$", " ")
            packed = "|$|".join([vid, name, pic, remark])
            res.append({
                "vod_id": packed,
                "vod_name": c.get("vod_name") or "",
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return res
    def homeVideoContent(self):
        html = self._fetch(f"{self.host}/?hl={self.hl}")
        cards = self._parse_cards(html)
        return {"list": self._to_list(cards)}

    # ---------- 分类列表 ----------
    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        tid = str(tid or "")
        if tid == "videos_hot":
            url = f"{self.host}/videos?hl={self.hl}&p={page}"
        elif tid == "videos_new":
            url = f"{self.host}/videos?hl={self.hl}&s=n&p={page}"
        else:
            # tid 形如 217/3d
            url = f"{self.host}/categories/{tid}?hl={self.hl}&p={page}"
        html = self._fetch(url)
        cards = self._parse_cards(html)
        return {
            "list": self._to_list(cards),
            "page": int(page),
            "pagecount": 9999,
            "limit": 20,
            "total": 9999,
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        page = str(pg or "1")
        kw = quote(str(key or ""))
        url = f"{self.host}/toon?q={kw}&hl={self.hl}&p={page}"
        html = self._fetch(url)
        cards = self._parse_cards(html)
        return {"list": self._to_list(cards), "page": int(page)}

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

    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
        pid = str(vid).split("|$|")[0].replace("$", "|")
        return {"list": [{
            "vod_id": vid, "vod_name": title or "未知标题", "vod_pic": pic or "",
            "vod_remarks": remarks, "vod_content": "",
            "vod_play_from": "播放", "vod_play_url": "播放$" + pid,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        try:
            ps = raw.split("|$|")
            vid = ps[0]
            old_name = ps[1] if len(ps) > 1 else ""
            old_pic = ps[2] if len(ps) > 2 else ""
            old_remark = ps[3] if len(ps) > 3 else ""
            # 拼详情页 URL（用于取 embedUrl）
            detail_url = self._detail_url(vid)
            html = self._fetch(detail_url) if detail_url else ""
            name, pic, content = old_name, old_pic, old_remark
            if html:
                # JSON-LD
                jm = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
                if jm:
                    try:
                        jd = json.loads(jm.group(1))
                        name = jd.get("name") or name
                        pic = jd.get("thumbnailUrl") or pic
                        content = jd.get("description") or content
                        if pic.startswith("//"):
                            pic = "https:" + pic
                    except Exception:
                        pass
                if not name:
                    tm = re.search(r'<meta property="og:title" content="([^"]*)"', html)
                    if tm:
                        name = tm.group(1)
            if not vid:
                return self._skeleton(raw, name, pic)
            vod = {
                "vod_id": raw,
                "vod_name": name or "视频",
                "vod_pic": pic,
                "vod_remarks": old_remark,
                "vod_content": content or old_remark,
                "vod_play_from": "播放",
                "vod_play_url": "播放$" + vid,
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"detail_exc": raw, "error": str(e)})
            return self._skeleton(raw)

    def _detail_url(self, vid):
        """vid 形如 131319，但详情 URL 需要 slug。
        我们从搜索/列表阶段只存了 id，详情页可尝试 /v-niche/{id}/ 直接跳 embed。
        真正取播放地址只依赖 /embed/{id}/，故详情 URL 可省略 slug。"""
        return f"{self.host}/v-niche/{vid}/?hl={self.hl}"

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        pid = str(id or "")
        if "$" in pid:
            pid = pid.split("$", 1)[1]
        pid = pid.strip()
        # 纯数字 id
        m = re.search(r"(\d+)", pid)
        if not m:
            return {"parse": 1, "url": pid, "header": self.headers}
        vid = m.group(1)
        # 抓 embed 页取 mp4 直链
        embed_url = f"{self.host}/embed/{vid}/?hl={self.hl}"
        html = self._fetch(embed_url, headers={"Referer": f"{self.host}/v-niche/{vid}/?hl={self.hl}"})
        real = ""
        if html:
            sm = re.search(r'<source[^>]+src=["\']([^"\']+)["\']', html)
            if sm:
                real = sm.group(1)
            if not real:
                vm = re.search(r'(https?://[^"\'\s]+\.mp4[^"\'\s]*)', html)
                if vm:
                    real = vm.group(1)
        if real:
            if real.startswith("//"):
                real = "https:" + real
            return {
                "parse": 0,
                "url": real,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": f"{self.host}/",
                },
            }
        # 兜底：降级到详情页嗅探
        return {
            "parse": 1,
            "url": f"{self.host}/v-niche/{vid}/?hl={self.hl}",
            "header": self.headers,
        }

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass