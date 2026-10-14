#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2400部恐怖电影 (txt 影视库) - 全家桶格式版
=================================================
TVBox / TVBoxOSC / FongMi / 影视仓 / PyramidStore 通用 Python 爬虫源
按「全家桶爬虫格式规范」编写（模板基线: 麦田app.py）：

  · class Spider 继承 base.spider.Spider（try/except ImportError 兜底），
    实现统一接口清单：init / getName / homeContent / homeVideoContent /
    categoryContent / detailContent / searchContent / searchContentPage /
    playerContent / isVideoFormat / manualVideoCheck / localProxy；
  · 接口返回标准 dict 字段；封面走本地代理；
  · 零第三方依赖：HTTP 用标准库 urllib。

站点本质（逆向核对 2026-10-09）：
  · 这是一个纯 txt 影视点播库（非 API、非加密）。
  · ext 形如 2400.js：[{"name":"2400多部恐怖电影[恐怖电影]",
    "url":"<主txt>&&&<封面服务根>"}]
      - 主数据源 txt: http://host407776532.s1169.pppf.com.cn/app/lib/2400部恐怖电影.txt
        （235KB / 2451 行；25 个分组标题「电影01」~「电影26」(缺22) +
         2424 条「片名,直链m3u8」数据行）
      - 封面服务: http://3650000.xyz/api/360.php?cid=6 （返回 JFIF 图片，
        无法按片名映射，故封面字段留空）
  · 每行数据: 片名,https://v.cdnlz*.com/.../index.m3u8 （2421 m3u8 + 2 mp4 + 1 share）
  · 分组标题行（不含逗号、不含 http）即分类；数据行即影片。
  · 播放: m3u8/mp4 直链 parse:0；个别 share 短链无后缀走 parse:1 交播放器。

对接（TVBox sites 配置）：
    {"key":"2400部恐怖电影","name":"☀恐怖🔹电影","type":3,
     "api":"./terrormovies.py","ext":"http://550.3vcn.work/2400.js"}
    · ext 填 2400.js（会自动解析出主 txt 地址）；
    · 或 ext 直接填主 txt 的 http 地址；
    · 或 ext 留空，使用内置默认主 txt 地址。
"""

import os
import re
import sys
import json
import time
import base64
import collections

import ssl
import urllib.request
import urllib.error
from urllib.parse import quote

try:
    sys.path.append("../../")
except Exception:
    pass
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def init(self, extend=""):
            pass


# ============================================================================
# 0. 图片魔数判定 / 默认筛选器（全家桶模板级组件）
# ============================================================================
def detect_image_mime(data) -> str:
    if not data:
        return "application/octet-stream"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] in (b"GIF8",):
        return "image/gif"
    return "application/octet-stream"


def build_default_filters() -> list:
    current_year = int(time.strftime("%Y"))
    years = [{"n": "全部", "v": ""}]
    for y in range(current_year, current_year - 11, -1):
        years.append({"n": str(y), "v": str(y)})
    return [
        {"key": "year", "name": "年份", "value": years},
    ]


# ============================================================================
# 1. 零依赖 HTTP 客户端（仅标准库）
# ============================================================================
_HTTP_INSECURE_CTX = None
try:
    _HTTP_INSECURE_CTX = ssl._create_unverified_context()
except Exception:
    _HTTP_INSECURE_CTX = None


def _encode_url(u):
    """对含非 ascii 字符（如中文路径）的 URL 做 percent-encode；
    纯 ascii 的 URL 原样返回，避免破坏已有的 %xx 编码。"""
    if not u:
        return u
    try:
        u.encode("ascii")
        return u
    except UnicodeEncodeError:
        pass
    from urllib.parse import urlsplit, urlunsplit, quote
    parts = urlsplit(u)
    path = quote(parts.path, safe="/")
    query = quote(parts.query, safe="=&")
    frag = quote(parts.fragment, safe="")
    return urlunsplit((parts.scheme, parts.netloc, path, query, frag))


def _http_request(method, url, headers=None, data=None, timeout=15, verify=True):
    url = _encode_url(url)
    req = urllib.request.Request(url, headers=headers or {}, data=data, method=method)
    ctx = None if verify else _HTTP_INSECURE_CTX
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# ============================================================================
# 2. Spider 主体（全家桶标准接口）
# ============================================================================
_PLAY_UA = ("Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36")

_LOCAL_PROXY_PREFIX = "http://127.0.0.1:9978/proxy?do=py&action=proxy"

# 直链判断(全家桶同款: m3u8/mp4/mkv/flv/ts/avi/webm)
_DIRECT_RE = re.compile(r"(m3u8|mp4|mkv|flv|ts|avi|webm)", re.I)

# 默认主数据源（来自 2400.js；ext 传入时以 ext 为准）
DEFAULT_TXT_URL = "http://host407776532.s1169.pppf.com.cn/app/lib/2400部恐怖电影.txt"
# 封面服务根（360.php 按 cid 返回图片，无法按片名映射，仅作占位说明）
DEFAULT_COVER_BASE = "http://3650000.xyz/api/360.php?cid="

# 单页条数
PAGE_SIZE = 60


class Spider(Spider):
    """2400部恐怖电影（txt 影视库）全家桶格式爬虫源"""

    # 聚合搜索配置(全家桶约定)
    searchable = 1
    quickSearch = 1
    filterable = 0
    changeable = 1

    def __init__(self):
        self.txt_url = ""
        self.cover_base = ""
        self.last_init_error = ""
        self._cache = None  # 分组数据缓存: {"groups": OrderedDict, "error": ""}

    def getName(self):
        return "2400部恐怖电影"

    # -------- ext 解析 --------
    def _parse_ext_json(self, content):
        """解析 2400.js 风格 JSON: [{"name":..,"url":"txt&&&cover"}]"""
        txt_url = ""
        cover = ""
        try:
            arr = json.loads(content)
            if isinstance(arr, list) and arr:
                u = str((arr[0] or {}).get("url", "") or "")
                if "&&&" in u:
                    parts = u.split("&&&")
                    txt_url = parts[0].strip()
                    cover = parts[1].strip() if len(parts) > 1 else ""
                else:
                    txt_url = u
        except Exception:
            pass
        return txt_url, cover

    def init(self, extend=""):
        self.last_init_error = ""
        self._cache = None
        ext = (extend or "").strip()
        txt_url = ""
        cover = ""
        if ext:
            if ext.startswith("["):
                # 情况A: ext 是 2400.js 下载后的 JSON 数组内容
                txt_url, cover = self._parse_ext_json(ext)
            elif ext.startswith("http"):
                # 情况B: ext 是 URL（可能是 2400.js 文件，或直接是 txt）
                try:
                    st, body = _http_request("GET", ext,
                                             headers={"User-Agent": _PLAY_UA},
                                             timeout=20, verify=False)
                    c = body.decode("utf-8", "replace").strip()
                except Exception:
                    c = ""
                if c.startswith("["):
                    t, cov = self._parse_ext_json(c)
                    txt_url = t or ext
                    cover = cov or cover
                else:
                    txt_url = ext
            elif "&&&" in ext:
                # 情况C: 裸 ext 直接是 "txt&&&cover"
                parts = ext.split("&&&")
                txt_url = parts[0].strip()
                cover = parts[1].strip() if len(parts) > 1 else ""
        if not txt_url:
            txt_url = DEFAULT_TXT_URL
            cover = DEFAULT_COVER_BASE
        self.txt_url = txt_url
        self.cover_base = cover

    # -------- 编码工具（tid / vod_id 透传安全） --------
    @staticmethod
    def _enc_tid(name):
        return base64.urlsafe_b64encode(str(name).encode("utf-8")).decode()

    @staticmethod
    def _dec_tid(tid):
        try:
            return base64.urlsafe_b64decode(str(tid).encode("utf-8")).decode("utf-8")
        except Exception:
            return ""

    @staticmethod
    def _enc_vid(name, url):
        raw = json.dumps({"n": name, "u": url}, ensure_ascii=False)
        return base64.urlsafe_b64encode(raw.encode("utf-8")).decode()

    @staticmethod
    def _dec_vid(vid):
        try:
            raw = base64.urlsafe_b64decode(str(vid).encode("utf-8")).decode("utf-8")
            o = json.loads(raw)
            return o.get("n", ""), o.get("u", "")
        except Exception:
            return "", ""

    # -------- 数据加载（带内存缓存） --------
    def _load(self):
        if self._cache is not None:
            return self._cache
        groups = collections.OrderedDict()
        cur = None
        try:
            status, body = _http_request(
                "GET", self.txt_url,
                headers={"User-Agent": _PLAY_UA,
                         "Referer": "http://550.3vcn.work/"},
                timeout=30, verify=False)
            text = body.decode("utf-8", "replace")
        except Exception as e:
            self._cache = {"groups": groups, "error": str(e)}
            return self._cache
        for ln in text.splitlines():
            s = ln.strip()
            if not s:
                continue
            if ("," in s) and ("http" in s):
                if cur is None:
                    cur = "默认"
                    groups.setdefault(cur, [])
                try:
                    title, link = s.split(",", 1)
                    link = link.strip()
                except Exception:
                    continue
                if link:
                    groups[cur].append((title.strip(), link))
            else:
                # 分组标题行
                cur = s
                groups.setdefault(cur, [])
        self._cache = {"groups": groups, "error": ""}
        return self._cache

    # -------- 全家桶标准接口 --------
    def homeContent(self, filter=False):
        try:
            d = self._load()
            groups = d["groups"]
            classes = []
            for gname, items in groups.items():
                if not items:
                    continue
                classes.append({
                    "type_id": self._enc_tid(gname),
                    "type_name": gname,
                })
            return {"class": classes, "filters": {}, "list": []}
        except Exception as e:
            return {"class": [], "list": [], "msg": str(e)}

    def homeVideoContent(self):
        # txt 库无独立首页推荐；取第一个有内容的分组前 20 条作为首页
        try:
            d = self._load()
            groups = d["groups"]
            out = []
            for gname, items in groups.items():
                for title, link in items[:20]:
                    out.append({
                        "vod_id": self._enc_vid(title, link),
                        "vod_name": title,
                        "vod_pic": "",
                        "vod_remarks": "",
                    })
                if out:
                    break
            return {"list": out}
        except Exception as e:
            return {"list": [], "msg": str(e)}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            d = self._load()
            groups = d["groups"]
            gname = self._dec_tid(tid)
            items = groups.get(gname, [])
            pg = int(pg or 1)
            total = len(items)
            pc = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
            start = (pg - 1) * PAGE_SIZE
            chunk = items[start:start + PAGE_SIZE]
            out = []
            for title, link in chunk:
                out.append({
                    "vod_id": self._enc_vid(title, link),
                    "vod_name": title,
                    "vod_pic": "",
                    "vod_remarks": "",
                })
            return {
                "list": out,
                "page": pg,
                "pagecount": pc,
                "limit": PAGE_SIZE,
                "total": total,
            }
        except Exception as e:
            return {"list": [], "page": int(pg or 1), "pagecount": 1,
                    "limit": PAGE_SIZE, "total": 0, "msg": str(e)}

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
            name, url = self._dec_vid(vid)
            if not url:
                return {"list": [], "msg": "vid解码失败"}
            vod = {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": "",
                "vod_remarks": "",
                "vod_play_from": "直连",
                "vod_play_url": "直连$" + url,
            }
            return {"list": [vod]}
        except Exception as e:
            return {"list": [], "msg": str(e)}

    def searchContent(self, key, quick=False, pg=1):
        try:
            d = self._load()
            groups = d["groups"]
            kw = str(key).lower()
            allitems = []
            for gname, items in groups.items():
                for title, link in items:
                    if kw in title.lower():
                        allitems.append((title, link))
            total = len(allitems)
            pg = int(pg or 1)
            pc = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
            start = (pg - 1) * PAGE_SIZE
            out = []
            for title, link in allitems[start:start + PAGE_SIZE]:
                out.append({
                    "vod_id": self._enc_vid(title, link),
                    "vod_name": title,
                    "vod_pic": "",
                    "vod_remarks": "",
                })
            return {
                "list": out,
                "page": pg,
                "pagecount": pc,
                "limit": PAGE_SIZE,
                "total": total,
            }
        except Exception as e:
            return {"list": [], "msg": str(e)}

    def searchContentPage(self, key, quick=False, pg=1):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, pid, vipFlags=None):
        pid = str(pid or "")
        if not pid:
            return {"parse": 0, "playUrl": "", "url": "", "header": ""}
        # ① 直链(m3u8/mp4/...)
        if pid.startswith(("http://", "https://")) and _DIRECT_RE.search(pid):
            return {"parse": 0, "playUrl": "", "url": pid,
                    "header": json.dumps({"User-Agent": _PLAY_UA})}
        # ② 非直链(如 share 短链)交播放器/jx 处理
        return {"parse": 1, "playUrl": "", "url": pid,
                "header": json.dumps({"User-Agent": _PLAY_UA})}

    # -------- 解析辅助 --------
    def _cover_url(self, pic):
        pic = str(pic or "").strip()
        if not pic:
            return ""
        if pic.startswith(_LOCAL_PROXY_PREFIX):
            return pic
        if not pic.startswith(("http://", "https://")):
            pic = "http://" + pic.lstrip("/")
        return _LOCAL_PROXY_PREFIX + "&type=cover&url=" + quote(pic, safe="")

    # -------- 全家桶附加接口 --------
    def isVideoFormat(self, url):
        if not url or not isinstance(url, str):
            return False
        if not url.startswith("http"):
            return False
        return bool(_DIRECT_RE.search(url))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        def _first(v):
            if isinstance(v, list):
                return v[0].strip() if v and v[0] else ""
            return (v or "").strip()

        url = _first(param.get('url'))
        ptype = _first(param.get('type'))
        headers = {"User-Agent": _PLAY_UA}
        try:
            if ptype == 'cover' or (url and re.search(r"\.(jpg|jpeg|png|webp|gif)(\?|$)", url, re.I)):
                status, body = _http_request("GET", url, headers=headers,
                                             timeout=10, verify=False)
                if status == 200 and body:
                    return [200, detect_image_mime(body), body]
                return [404, "text/plain", b"cover not found"]
            if ptype == 'm3u8' or (url and '.m3u8' in url):
                status, body = _http_request("GET", url, headers=headers,
                                             timeout=15, verify=False)
                return [200, "application/vnd.apple.mpegurl", body.decode("utf-8", "replace")]
            if ptype == 'media':
                status, body = _http_request("GET", url, headers=headers,
                                             timeout=15, verify=False)
                return [206, "application/octet-stream", body]
            status, body = _http_request("GET", url, headers=headers,
                                         timeout=15, verify=False)
            return [200, "text/plain", body.decode("utf-8", "replace")]
        except Exception as e:
            return [500, "text/plain", str(e)]


# ============================================================================
# 模块级函数转发层（兼容 webhome / 部分 OK影视 / 影视仓 的模块级加载）
# ============================================================================
_spider_instance = None


def _get_spider():
    global _spider_instance
    if _spider_instance is None:
        _spider_instance = Spider()
        _spider_instance.init()
    return _spider_instance


def getName():
    return _get_spider().getName()


def init(extend=""):
    return _get_spider().init(extend)


def homeContent(filter=False):
    return _get_spider().homeContent(filter)


def homeVideoContent():
    return _get_spider().homeVideoContent()


def categoryContent(tid, pg, filter=False, extend=None):
    return _get_spider().categoryContent(tid, pg, filter, extend)


def detailContent(ids):
    return _get_spider().detailContent(ids)


def playerContent(flag, pid, vip_flags=None):
    return _get_spider().playerContent(flag, pid, vip_flags)


def searchContent(key, quick=False, pg=1):
    return _get_spider().searchContent(key, quick, pg)


def searchContentPage(key, quick=False, pg=1):
    return _get_spider().searchContentPage(key, quick, pg)


def isVideoFormat(url):
    return _get_spider().isVideoFormat(url)


def manualVideoCheck():
    return _get_spider().manualVideoCheck()


def localProxy(param):
    return _get_spider().localProxy(param)


# ============================================================================
# 离线自检（python terrormovies.py）
# ============================================================================
if __name__ == "__main__":
    print("===== 2400部恐怖电影 全家桶格式自检 =====")
    assert detect_image_mime(b'\xff\xd8\xff\xe0') == 'image/jpeg'
    assert detect_image_mime(b'\x89PNG\r\n\x1a\n') == 'image/png'
    print("[mime] ok")
    sp = Spider()
    sp.init("")
    print("[OK] init:", sp.getName(), "| txt_url:", sp.txt_url[:60])

    # 注入假缓存，离线验证分组/分类/详情/播放/搜索逻辑（不联网）
    import collections as _c
    fake = _c.OrderedDict()
    fake["电影01"] = [("蛊1981【粤语】（台湾恐怖片）", "https://v.cdnlz19.com/20240528/35189_a/index.m3u8"),
                     ("笔仙怪谈（大陆恐怖片）", "https://v.cdnlz19.com/x/34940/index.m3u8")]
    fake["电影02"] = [("梅根失踪（美国恐怖片）", "https://v.cdnlz21.com/x/325/index.m3u8"),
                     ("德州电锯杀人狂2003", "https://dow.dowlz2.com//20220410/2751/xxx.mp4")]
    sp._cache = {"groups": fake, "error": ""}

    hc = sp.homeContent(False)
    assert hc["class"][0]["type_name"] == "电影01"
    assert len(hc["class"]) == 2
    tid = hc["class"][0]["type_id"]
    print("[OK] homeContent 分类数:", len(hc["class"]), "| tid 编码:", tid[:12], "...")

    cc = sp.categoryContent(tid, 1)
    assert len(cc["list"]) == 2 and cc["pagecount"] == 1
    assert cc["list"][0]["vod_name"].startswith("蛊")
    print("[OK] categoryContent 列表数:", len(cc["list"]))

    vid = cc["list"][0]["vod_id"]
    dc = sp.detailContent([vid])
    assert dc["list"][0]["vod_play_from"] == "直连"
    assert dc["list"][0]["vod_play_url"].startswith("直连$https")
    print("[OK] detailContent 播放串:", dc["list"][0]["vod_play_url"][:40], "...")

    pc = sp.playerContent("直连", "https://v.cdnlz19.com/x/index.m3u8")
    assert pc["parse"] == 0 and pc["url"].endswith(".m3u8")
    pc2 = sp.playerContent("直连", "https://vip1.lz-cdn10.com/share/abc123")
    assert pc2["parse"] == 1
    print("[OK] playerContent 直链parse:0 / 短链parse:1")

    sc = sp.searchContent("笔仙", False, 1)
    assert sc["list"] and "笔仙" in sc["list"][0]["vod_name"]
    print("[OK] searchContent 命中:", sc["total"], "条")

    assert sp.isVideoFormat("http://x/y/a.m3u8") is True
    assert sp.isVideoFormat("http://x/y/play?id=1") is False
    assert sp.manualVideoCheck() is False
    print("[OK] isVideoFormat/manualVideoCheck")

    assert isinstance(homeContent(False), dict)
    assert isinstance(searchContentPage("梅根"), dict)
    print("[OK] 模块级转发层（含 searchContentPage / homeVideoContent）可用")
    print("===== 自测完成（联网接口请用壳子实测） =====")
