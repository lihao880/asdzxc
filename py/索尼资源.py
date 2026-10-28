#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
源名称：索尼资源（suoniapi）
站点：https://suoniapi.com
架构：MacCMS V10 标准 API 采集源
功能：支持 类型/分类/地区/年份/排序 筛选；内置 Netflix 电影/自制剧分类

按 dr_py 规范：一个 Spider 类 + 五方法 + 四占位；filters 二级筛选。
"""
import sys, re, json, html as html_mod
import urllib.parse

sys.path.append('..')
from base.spider import Spider


# 只保留正规影视分类，屏蔽伦理/写真/擦边等（type_id）
HIDE_TYPE_IDS = {"55", "56", "57", "58", "59", "60", "61", "73"}


class Spider(Spider):

    def init(self, extend=""):
        self.host = "https://suoniapi.com"
        self.api = self.host + "/api.php/provide/vod/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": self.host + "/",
        }
        self.play_headers = {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/"}
        self.classes = []
        self._fetch_classes()

        # ====== 二级筛选 filters（MacCMS V10 标准参数）======
        # by: 排序；area: 地区；year: 年份
        area_opts = [
            {"name": "全部", "value": ""},
            {"name": "大陆", "value": "大陆"}, {"name": "香港", "value": "香港"},
            {"name": "台湾", "value": "台湾"}, {"name": "美国", "value": "美国"},
            {"name": "日本", "value": "日本"}, {"name": "韩国", "value": "韩国"},
            {"name": "英国", "value": "英国"}, {"name": "法国", "value": "法国"},
            {"name": "泰国", "value": "泰国"}, {"name": "印度", "value": "印度"},
            {"name": "其他", "value": "其他"},
        ]
        year_opts = [{"name": "全部", "value": ""}] + [
            {"name": str(y), "value": str(y)} for y in range(2026, 2009, -1)
        ]
        by_opts = [
            {"name": "最新", "value": "time"},
            {"name": "最热", "value": "hits"},
            {"name": "评分", "value": "score"},
        ]
        # 每个一级分类都支持这套筛选
        self.filters = {}
        for c in self.classes:
            tid = c["type_id"]
            self.filters[tid] = [
                {"key": "area", "name": "地区", "value": area_opts},
                {"key": "year", "name": "年份", "value": year_opts},
                {"key": "by",   "name": "排序", "value": by_opts},
            ]

    # ============ 工具 ============
    def clean(self, t):
        if not t: return ""
        t = html_mod.unescape(str(t))
        t = re.sub(r'<[^>]+>', '', t)
        t = re.sub(r'[\x00-\x1f\x7f]', '', t)
        return re.sub(r'\s+', ' ', t).strip()

    def normalize_pic(self, src):
        if not src: return ""
        if src.startswith("//"): return "https:" + src
        if src.startswith("http"): return src
        if src.startswith("/"): return self.host + src
        return src

    def _get_json(self, url):
        try:
            r = self.fetch(url, headers=self.headers)
            if r is None or not r.text: return None
            return json.JSONDecoder(strict=False).decode(r.text)
        except Exception:
            return None

    def _fetch_classes(self):
        data = self._get_json(self.api + "?ac=list")
        if data and data.get("class"):
            for c in data["class"]:
                tid = str(c.get("type_id", ""))
                if tid in HIDE_TYPE_IDS:
                    continue
                self.classes.append({"type_id": tid, "type_name": c.get("type_name", "")})

    def _item(self, v):
        return {
            "vod_id": str(v.get("vod_id", "")),
            "vod_name": self.clean(v.get("vod_name", "")),
            "vod_pic": self.normalize_pic(v.get("vod_pic", "")),
            "vod_remarks": self.clean(v.get("vod_remarks", "")),
        }

    @staticmethod
    def _play_from_drpy(s):
        if not s: return ""
        return "$$$".join(p.strip() for p in str(s).split(",") if p.strip())

    # ============ 五方法 ============
    def homeContent(self, filter):
        data = self._get_json(self.api + "?ac=detail&pg=1")
        lst = [self._item(v) for v in data.get("list", [])] if data else []
        return {"class": self.classes, "filters": self.filters, "list": lst[:30]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg or "1")
        qs = f"ac=detail&t={urllib.parse.quote(str(tid))}&pg={pg}"
        # extend 里带筛选参数
        for k in ("area", "year", "by"):
            v = (extend or {}).get(k)
            if v:
                qs += f"&{k}={urllib.parse.quote(str(v))}"
        data = self._get_json(self.api + "?" + qs)
        lst = [self._item(v) for v in data.get("list", [])] if data else []
        pc = int(data.get("pagecount", 1)) if data else 1
        total = int(data.get("total", pc * 20)) if data else pc * 20
        return {"list": lst, "page": int(pg), "pagecount": pc, "limit": 20, "total": total}

    def detailContent(self, ids):
        vid = str(ids[0]) if isinstance(ids, (list, tuple)) else str(ids)
        data = self._get_json(self.api + "?ac=detail&ids=" + urllib.parse.quote(vid))
        if not data or not data.get("list"):
            return {"list": []}
        v = data["list"][0]
        vod = {
            "vod_id": str(v.get("vod_id", vid)),
            "vod_name": self.clean(v.get("vod_name", "")),
            "vod_pic": self.normalize_pic(v.get("vod_pic", "")),
            "vod_year": self.clean(v.get("vod_year", "")),
            "vod_area": self.clean(v.get("vod_area", "")),
            "vod_actor": self.clean(v.get("vod_actor", "")),
            "vod_director": self.clean(v.get("vod_director", "")),
            "vod_content": self.clean(v.get("vod_content", "")),
            "vod_remarks": self.clean(v.get("vod_remarks", "")),
            "vod_play_from": self._play_from_drpy(v.get("vod_play_from", "")),
            "vod_play_url": str(v.get("vod_play_url", "") or "").strip(),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = str(pg or "1")
        url = self.api + "?ac=detail&wd=" + urllib.parse.quote(str(key)) + "&pg=" + pg
        data = self._get_json(url)
        lst = [self._item(v) for v in data.get("list", [])] if data else []
        return {"list": lst, "page": int(pg),
                "pagecount": int(data.get("pagecount", 1)) if data else 1}

    def playerContent(self, flag, id, vipFlags):
        url = str(id or "")
        # 直链直接播
        if re.search(r'\.(m3u8|mp4|flv)(\?|$)', url, re.I):
            return {"parse": 0, "url": url, "header": self.play_headers, "Header": self.play_headers}
        # share 页提 var main
        try:
            r = self.fetch(url, headers=self.headers)
            html = r.text if r else ""
        except Exception:
            html = ""
        m = re.search(r'var\s+main\s*=\s*"([^"]+)"', html)
        if m:
            path = m.group(1).replace('\\/', '/')
            pr = urllib.parse.urlsplit(url)
            real = path if path.startswith("http") else f"{pr.scheme}://{pr.netloc}{path}"
            return {"parse": 0, "url": real, "header": self.play_headers, "Header": self.play_headers}
        return {"parse": 1, "url": url, "header": self.play_headers, "Header": self.play_headers}

    # ============ 占位 ============
    def isVideoFormat(self, url): pass
    def manualVideoCheck(self): pass
    def localProxy(self, param): pass
    def liveContent(self, url): pass
