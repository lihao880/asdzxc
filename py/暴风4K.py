# coding=utf-8
"""
TVBox / 影视仓 Python 爬虫源 —— 练习版
站点: 暴风资源 (4K 资源站, 苹果CMS v10 标准 JSON API)
API : https://bfzyapi.com/api.php/provide/vod

学习要点 (来自 30剧集网 / 趣谷 / 黑米影视 三个范本):
1. 趣谷思路: 不解析 HTML, 直接走 App/CMS 的 JSON 接口, 数据干净、抗模板改版
2. 多层降级: requests -> urllib; 主域名失败不重试死磕, 全接口 try-except 返回空结构
3. 去重贯穿始终 (seen 集合)
4. homeContent 下发 filters (类型/年份/地区), categoryContent 拼 API 参数实现筛选
5. playerContent 直链检测 (.m3u8/.mp4) 直接返回 parse=0
6. 分页语义: pagecount 用于客户端翻页判断, 满页则假定还有下一页
"""
import re
import json
import urllib.parse
import urllib.request

try:
    import requests
except Exception:
    requests = None

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        def init(self, extend=""):
            pass


HOST = "https://bfzyapi.com"
API = HOST + "/api.php/provide/vod"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 一级分类 (type_pid=0); 子分类用筛选里选, 不铺满导航栏
CLASSES = [
    {"type_id": "21", "type_name": "动作片"},
    {"type_id": "22", "type_name": "喜剧片"},
    {"type_id": "23", "type_name": "恐怖片"},
    {"type_id": "24", "type_name": "科幻片"},
    {"type_id": "25", "type_name": "爱情片"},
    {"type_id": "26", "type_name": "剧情片"},
    {"type_id": "27", "type_name": "战争片"},
    {"type_id": "28", "type_name": "纪录片"},
    {"type_id": "31", "type_name": "国产剧"},
    {"type_id": "32", "type_name": "欧美剧"},
    {"type_id": "33", "type_name": "香港剧"},
    {"type_id": "34", "type_name": "韩国剧"},
    {"type_id": "35", "type_name": "台湾剧"},
    {"type_id": "36", "type_name": "日本剧"},
    {"type_id": "37", "type_name": "海外剧"},
    {"type_id": "40", "type_name": "国产动漫"},
    {"type_id": "41", "type_name": "日韩动漫"},
    {"type_id": "42", "type_name": "欧美动漫"},
    {"type_id": "46", "type_name": "大陆综艺"},
    {"type_id": "47", "type_name": "港台综艺"},
    {"type_id": "49", "type_name": "欧美综艺"},
    {"type_id": "65", "type_name": "短剧"},
]

# 筛选维度: 年份 (子分类已直挂导航, 不再重复"类型"维度)
_YEAR_VALUES = [{"n": "全部", "v": ""}] + [
    {"n": str(y), "v": str(y)} for y in range(2026, 2019, -1)]
FILTERS = {str(tid): [{"key": "year", "name": "年份", "value": _YEAR_VALUES}]
           for tid in [21, 22, 23, 24, 25, 26, 27, 28, 31, 32, 33, 34, 35, 36, 37, 40, 41, 42, 46, 47, 49, 65]}


def _log(*args):
    try:
        import sys
        sys.stderr.write("[暴风] " + " ".join(str(a) for a in args) + "\n")
    except Exception:
        pass


def _http(url, timeout=10):
    """requests -> urllib 两级降级 (黑米思路), 失败返回空串不抛错"""
    headers = {"User-Agent": UA, "Referer": HOST + "/"}
    if requests:
        try:
            r = requests.get(url, headers=headers, timeout=timeout, verify=False)
            if r.status_code == 200:
                return r.text
            return ""
        except Exception:
            pass
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "ignore")
    except Exception as e:
        _log("请求失败", url[:80], repr(e)[:60])
        return ""


def _json(url):
    txt = _http(url)
    if not txt:
        return {}
    try:
        return json.loads(txt)
    except Exception:
        return {}


def _vod_from(it):
    """JSON 条目 -> TVBox 条目 (趣谷 _vod_from 思路)"""
    return {
        "vod_id": str(it.get("vod_id") or ""),
        "vod_name": it.get("vod_name") or "",
        "vod_pic": it.get("vod_pic") or "",
        "vod_remarks": it.get("vod_remarks") or "",
        "vod_year": str(it.get("vod_year") or ""),
        "vod_area": it.get("vod_area") or "",
        "type_name": it.get("type_name") or "",
    }


def _parse_list(data, seen=None):
    vods = []
    seen = seen if seen is not None else set()
    for it in (data or {}).get("list") or []:
        v = _vod_from(it)
        if not v["vod_id"] or v["vod_id"] in seen:
            continue
        seen.add(v["vod_id"])
        vods.append(v)
    return vods


def _is_direct(url):
    return bool(re.search(r"\.(m3u8|mp4|flv|mkv|ts)(\?|$)", url or "", re.I))


class Spider(BaseSpider):

    def getName(self):
        return "暴风资源"

    def init(self, extend=""):
        self.headers = {"User-Agent": UA, "Referer": HOST + "/"}

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return _is_direct(url)

    def manualVideoCheck(self):
        return False

    # ---------- 首页 ----------
    def homeContent(self, filter):
        result = {"class": [dict(c) for c in CLASSES]}
        if filter:
            result["filters"] = {k: [dict(d) for d in v] for k, v in FILTERS.items() if v}
        return result

    def homeVideoContent(self):
        # 首页推荐: 取最新一页列表
        data = _json(API + "?ac=list")
        return {"list": _parse_list(data)[:30]}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        result = {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}
        try:
            ex = extend if isinstance(extend, dict) else {}
            try:
                ex = json.loads(ex) if isinstance(ex, str) else ex
            except Exception:
                ex = {}
            year = ex.get("year") or ""
            # CMS API: ac=videolist / t=子分类id / year
            url = "%s?ac=videolist&t=%s&pg=%d" % (API, tid, pg)
            if year:
                url += "&year=" + urllib.parse.quote(year)
            data = _json(url)
            result["list"] = _parse_list(data)
            result["pagecount"] = int(data.get("pagecount") or pg)
            result["total"] = int(data.get("total") or len(result["list"]))
            return result
        except Exception as e:
            _log("categoryContent异常", repr(e)[:80])
            return result

    # ---------- 详情 ----------
    def detailContent(self, ids):
        result = {"list": []}
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            data = _json("%s?ac=detail&ids=%s" % (API, vid))
            items = data.get("list") or []
            if not items:
                return result
            it = items[0]
            # play_from 可能多线路 ( $$$ 分隔), play_url 与之对应
            play_from = (it.get("vod_play_from") or "").split("$$$")
            play_url = (it.get("vod_play_url") or "").split("$$$")
            sources, urls = [], []
            for name, eps in zip(play_from, play_url):
                eps = [e for e in eps.split("#") if "$" in e]
                if not eps:
                    continue
                sources.append(name or "默认")
                urls.append("#".join(eps))
            if not sources:
                sources, urls = ["默认"], ["播放$%s" % vid]
            result["list"].append({
                "vod_id": str(it.get("vod_id") or vid),
                "vod_name": it.get("vod_name") or "",
                "vod_pic": it.get("vod_pic") or "",
                "type_name": it.get("type_name") or "",
                "vod_year": str(it.get("vod_year") or ""),
                "vod_area": it.get("vod_area") or "",
                "vod_actor": it.get("vod_actor") or "",
                "vod_director": it.get("vod_director") or "",
                "vod_content": it.get("vod_content") or "",
                "vod_remarks": it.get("vod_remarks") or "",
                "vod_play_from": "$$$".join(sources),
                "vod_play_url": "$$$".join(urls),
            })
            return result
        except Exception as e:
            _log("detailContent异常", repr(e)[:80])
            return result

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        header = {"User-Agent": UA, "Referer": HOST + "/"}
        try:
            play_url = id if id.startswith("http") else urllib.parse.urljoin(HOST + "/", id)
            if _is_direct(play_url):
                # 直链直接返回 parse=0 (30剧集网思路)
                return {"parse": 0, "url": play_url, "header": header}
            return {"parse": 1, "url": play_url, "header": header}
        except Exception:
            return {"parse": 1, "url": id, "header": header}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        result = {"list": [], "page": int(pg or 1)}
        try:
            if not key:
                return result
            data = _json("%s?ac=videolist&wd=%s&pg=%s" % (
                API, urllib.parse.quote(key), pg))
            result["list"] = _parse_list(data)
            return result
        except Exception as e:
            _log("searchContent异常", repr(e)[:80])
            return result


# 本地自检
if __name__ == "__main__":
    s = Spider()
    s.init()
    print("== 首页分类:", [c["type_name"] for c in s.homeContent(False)["class"]])
    print("== 首页推荐:", len(s.homeVideoContent()["list"]), "条")
    cat = s.categoryContent("21", "1", False, {})
    print("== 分类(动作片):", len(cat["list"]), "条, pagecount =", cat["pagecount"])
    if cat["list"]:
        vid = cat["list"][0]["vod_id"]
        det = s.detailContent([vid])["list"][0]
        print("== 详情:", det["vod_name"], "| 线路:", det["vod_play_from"])
        first_ep = det["vod_play_url"].split("#")[0]
        play_id = first_ep.split("$")[1]
        print("== 播放:", s.playerContent(det["vod_play_from"], play_id))
    print("== 搜索:", len(s.searchContent("三体", False)["list"]), "条")
