# -*- coding: utf-8 -*-
"""
B站 TVBox/WebHomeTV 通用爬虫 (py 源)
- 搜索覆盖 UGC 视频(up主上传的电影/短片) + 番剧 + 影视
- 播放: UGC 用 WBI 签名拿 mp4 直链(parse=0); PGC 走正版直链
- 兼容 Python2/3 + base.spider 基类(照 哔哩哔哩.py 原稿的壳子兼容层写法)
- 用法: api 填本文件的 http 直链(不要填相对路径)
"""
import re
import json
import time
import hashlib

# ---------- Python 2/3 兼容 ----------
try:
    from urllib.parse import quote as _quote
    from urllib.parse import urlencode as _urlencode
    _PY3 = True
except Exception:
    from urllib import quote as _quote
    from urllib import urlencode as _urlencode
    _PY3 = False

# ---------- base.spider 基类兼容层(关键, 照原稿) ----------
try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        pass

# ---------- requests (壳的 Chaquopy 自带) ----------
try:
    import requests as _rq
except Exception:
    _rq = None

# ---------- 可配置 ----------
COOKIE = "b_nut=1754358399; buvid3=0F2F49F9-DB89-BB64-8C82-0FC19C89700C99838infoc; bsource=search_baidu; _uuid=D75882107-8DA4-5CEB-610BF-1C947B575F6F00241infoc; buvid4=708DFED9-5C46-1145-2E55-C666A6DCD00D00431-125080509-2JaJVUbLMmiKSv6f1hrFWOzvO5HPB0qiGQ88G7/gWinLq9zArOyfN4Sxbea0Elu2; bmg_af_switch=1; bmg_src_def_domain=i0.hdslb.com; buvid_fp=a648a8f1a55caf7d8a9f1cf0a7012532; rpdid=0zbfvUmrTi|gvd1C9k3|4EB|3w1UJ6Qk; b_lsid=3F6610F34_19B627D262F; home_feed_column=4; browser_resolution=1100-2444; theme-tip-show=SHOWED; theme-avatar-tip-show=SHOWED; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NjcxNDM0NjAsImlhdCI6MTc2Njg4NDIwMCwicGx0IjotMX0.Mq61VKWaA2PwrfGmjz5wdxxTq4gAEl8OCW1aC1vcyAg; bili_ticket_expires=1767143400; CURRENT_FNVAL=16; CURRENT_QUALITY=0; sid=pp8jodon"
UA_PC = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
MIXIN_KEY_ENC_TAB = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52]
HOST = "https://api.bilibili.com"


class Spider(Spider):

    def getName(self):
        return "哔哩哔哩"

    def init(self, extend=""):
        self.extend = extend or ""
        self.cookie = COOKIE
        self._headers = {
            "User-Agent": UA_PC,
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
            "Cookie": self.cookie,
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "identity",
        }

    # ---------- 请求 ----------
    def _req(self, url):
        if _rq is None:
            return {}
        try:
            r = _rq.get(url, headers=self._headers, timeout=10)
            try:
                return r.json()
            except Exception:
                return {}
        except Exception:
            return {}

    # ---------- WBI 签名 ----------
    def _wbi_keys(self):
        try:
            r = self._req(HOST + "/x/web-interface/nav")
            wbi = r["data"]["wbi_img"]
            ik = wbi["img_url"].split("/")[-1].split(".")[0]
            sk = wbi["sub_url"].split("/")[-1].split(".")[0]
            return ik, sk
        except Exception:
            return "", ""

    def _wbi(self, params):
        ik, sk = self._wbi_keys()
        mixin = "".join((ik + sk)[i] for i in MIXIN_KEY_ENC_TAB[:32])
        params["wts"] = int(time.time())
        keys = sorted(params.keys())
        query = "&".join("%s=%s" % (k, _quote(str(params[k]), safe="")) for k in keys)
        w_rid = hashlib.md5((query + mixin).encode("utf-8")).hexdigest()
        return query, w_rid

    def _clean(self, t):
        if not t:
            return ""
        return re.sub(r"<[^>]+>", "", t).replace("&quot;", '"').replace("&amp;", "&").strip()

    def _pic(self, p):
        p = p or ""
        if p.startswith("//"):
            p = "https:" + p
        return p

    # ---------- 首页 ----------
    def homeContent(self, filter):
        return {
            "class": [
                {"type_id": "all", "type_name": "综合"},
                {"type_id": "1", "type_name": "番剧"},
                {"type_id": "4", "type_name": "国创"},
                {"type_id": "2", "type_name": "电影"},
                {"type_id": "5", "type_name": "电视剧"},
                {"type_id": "3", "type_name": "纪录片"},
                {"type_id": "7", "type_name": "综艺"},
            ]
        }

    # ---------- 分类内容(PGC 分类对应真实内容 / 综合走热门) ----------
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if pg else 1
        vods = []
        if tid and str(tid) != "all":
            # PGC 分类: season_type 1番剧 4国创 2电影 5电视剧 3纪录片 7综艺
            u = (HOST + "/pgc/season/index/result?season_type=%s&page=%d&pagesize=20"
                      "&type=1&area=-1&year=-1&style_id=-1&order=") % (str(tid), pg)
            r = self._req(u)
            for it in (r.get("data") or {}).get("list") or []:
                vods.append(self._mk_pgc(it))
        else:
            r = self._req(HOST + "/x/web-interface/popular?pn=%d&ps=20" % pg)
            for it in (r.get("data") or {}).get("list") or []:
                vods.append(self._mk_vod(it))
            if not vods:
                r = self._req(HOST + "/x/web-interface/ranking/v2?rid=0&type=all")
                for it in (r.get("data") or {}).get("list") or []:
                    vods.append(self._mk_vod(it))
        return {"list": vods, "page": pg, "pagecount": 999, "limit": 20, "total": 9999}

    def _mk_pgc(self, item):
        return {
            "vod_id": str(item.get("season_id", "")),
            "vod_name": self._clean(item.get("title", "")),
            "vod_pic": self._pic(item.get("cover", "")),
            "vod_remarks": str(item.get("index_show", "")),
            "type_name": "哔哩·PGC",
            "vod_actor": item.get("actors", ""),
        }

    def _mk_vod(self, item):
        bvid = item.get("bvid", "")
        return {
            "vod_id": bvid,
            "vod_name": self._clean(item.get("title", "")),
            "vod_pic": self._pic(item.get("pic", "")),
            "vod_remarks": (item.get("owner") or {}).get("name", ""),
            "vod_actor": (item.get("owner") or {}).get("name", ""),
            "vod_content": item.get("desc", ""),
        }

    # ---------- 搜索(覆盖 UGC + 番剧 + 影视) ----------
    def searchContent(self, key, quick, pg="1"):
        k = _quote(str(key))
        vods = []
        # 1) UGC 视频 —— 核心(up主上传的电影)
        r = self._req(HOST + "/x/web-interface/search/type?search_type=video&keyword=%s&page=%s" % (k, pg))
        if r.get("code") == 0:
            for it in (r.get("data") or {}).get("result") or []:
                bvid = it.get("bvid", "")
                title = self._clean(it.get("title", ""))
                if bvid and title:
                    vods.append({"vod_id": bvid, "vod_name": title,
                                 "vod_pic": self._pic(it.get("pic", "")),
                                 "vod_remarks": "%s %s" % (it.get("duration", ""), it.get("author", "")),
                                 "vod_actor": it.get("author", "")})
        # 2) 番剧
        r = self._req(HOST + "/x/web-interface/search/type?search_type=media_bangumi&keyword=%s&page=%s" % (k, pg))
        if r.get("code") == 0:
            for it in (r.get("data") or {}).get("result") or []:
                sid = it.get("season_id")
                title = self._clean(it.get("title", ""))
                if sid and title:
                    vods.append({"vod_id": str(sid), "vod_name": title,
                                 "vod_pic": self._pic(it.get("cover", "")), "vod_remarks": "番剧"})
        # 3) 影视
        r = self._req(HOST + "/x/web-interface/search/type?search_type=media_ft&keyword=%s&page=%s" % (k, pg))
        if r.get("code") == 0:
            for it in (r.get("data") or {}).get("result") or []:
                sid = it.get("season_id")
                title = self._clean(it.get("title", ""))
                if sid and title:
                    vods.append({"vod_id": str(sid), "vod_name": title,
                                 "vod_pic": self._pic(it.get("cover", "")), "vod_remarks": "影视"})
        return {"list": vods}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        vid = str(ids[0])
        m = re.search(r"BV[0-9A-Za-z]{8,}", vid)
        if m:
            return self._detail_ugc(m.group(0))
        if vid.isdigit():
            return self._detail_pgc(vid)
        m2 = re.search(r"/video/(BV[0-9A-Za-z]{8,})", vid)
        if m2:
            return self._detail_ugc(m2.group(1))
        return {"list": []}

    def _detail_ugc(self, bvid):
        r = self._req(HOST + "/x/web-interface/view?bvid=%s" % bvid)
        if r.get("code") != 0:
            return {"list": []}
        jo = r["data"]
        eps = []
        for pp in jo.get("pages") or []:
            tag = ("P%d " % pp["page"]) if pp.get("page", 1) > 1 else ""
            tag += pp.get("part") or ""
            eps.append("%s$%s_%s" % (tag, bvid, pp["cid"]))
        return {"list": [{
            "vod_id": bvid, "vod_name": jo.get("title", bvid),
            "vod_pic": self._pic(jo.get("pic", "")), "vod_content": jo.get("desc", ""),
            "type_name": "哔哩·UGC",
            "vod_play_from": "B站", "vod_play_url": "#".join(eps),
            "vod_actor": (jo.get("owner") or {}).get("name", ""),
        }]}

    def _detail_pgc(self, sid):
        r = self._req(HOST + "/pgc/view/web/season?season_id=%s" % sid)
        if r.get("code") != 0:
            return {"list": []}
        jo = r.get("result") or {}
        eps = []
        for ep in jo.get("episodes") or []:
            t = ep.get("title", "")
            if "预告" in str(t):
                continue
            eps.append("%s$%s_%s" % (t, ep.get("id"), ep.get("cid")))
        return {"list": [{
            "vod_id": sid, "vod_name": jo.get("title", sid),
            "vod_pic": self._pic(jo.get("cover", "")), "vod_content": jo.get("evaluate", ""),
            "type_name": jo.get("share_sub_title", ""),
            "vod_play_from": "B站", "vod_play_url": "#".join(eps),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        id = str(id)
        m = re.search(r"(BV[0-9A-Za-z]{8,})_?(\d*)", id)
        if m:
            bvid = m.group(1)
            cid = m.group(2) if m.group(2) else self._ugc_cid(bvid)
            if cid:
                params = {"bvid": bvid, "cid": cid, "fnval": "0", "fourk": "1", "qn": "127"}
                query, wrid = self._wbi(params)
                r = self._req(HOST + "/x/player/wbi/playurl?%s&w_rid=%s" % (query, wrid))
                if r.get("code") == 0 and r.get("data", {}).get("durl"):
                    return {"parse": 0, "url": r["data"]["durl"][0]["url"], "jx": 0,
                            "header": {"User-Agent": UA_PC, "Referer": "https://www.bilibili.com/",
                                       "Cookie": self.cookie, "Origin": "https://www.bilibili.com"}}
                return {"parse": 0, "url": "https://www.bilibili.com/video/" + bvid, "jx": 1}
            return {}
        m2 = re.search(r"(\d+)_(\d+)", id)
        if m2:
            eid, cid = m2.group(1), m2.group(2)
            try:
                params = {"cid": cid, "ep_id": eid, "fnval": "0", "fourk": "1", "qn": "127"}
                query, wrid = self._wbi(params)
                r = self._req(HOST + "/x/player/wbi/playurl?%s&w_rid=%s" % (query, wrid))
                if r.get("code") == 0 and r.get("data", {}).get("durl"):
                    return {"parse": 0, "url": r["data"]["durl"][0]["url"], "jx": 0,
                            "header": {"User-Agent": UA_PC, "Referer": "https://www.bilibili.com/",
                                       "Cookie": self.cookie, "Origin": "https://www.bilibili.com"}}
            except Exception:
                pass
            return {"parse": 0, "url": "https://www.bilibili.com/bangumi/play/ep" + eid, "jx": 1}
        return {}

    def _ugc_cid(self, bvid):
        r = self._req(HOST + "/x/web-interface/view?bvid=%s" % bvid)
        if r.get("code") == 0 and r.get("data", {}).get("pages"):
            return r["data"]["pages"][0]["cid"]
        return None

    def localProxy(self, param):
        return None
