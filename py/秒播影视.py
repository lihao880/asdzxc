# -*- coding: utf-8 -*-
"""
秒播影视 - TVBox / FongMi / CatVod 站点源插件（MacCMS v10 模板 mbba6）

站点：https://www.dgsxzn.com

============================== 站点结构（实测 2026-10） ==============================

【和普通 MacCMS 站不一样的地方】
  /api.php/provide/vod/ 是关着的（任何 ac 参数都返回纯文本 closed），所以不能像
  大多数源那样直接挂标准 JSON 接口。真正的数据源是站内给前端用的两个接口：
    /index.php/ajax/data?mid=1&tid=&page=&limit=   列表（MacCMS 原生字段，全都能用）
    /index.php/ajax/suggest?mid=1&wd=             搜索建议（只给 id / name / pic）

  mid 只认 1（2/3 返回空、4/5 返回非 JSON）；limit 上限 30（写 50 会被压回 10）；
  tid 有效范围 1~32，>=33 会退化成全站列表。

【关于 Xcdn 人机验证 —— 重要，别被它骗了】
  站点挂了 Xcdn 的 Proof-of-Work 验证（/__xcdn/captcha/*，页面标题 "Bot detection"）。
  曾经以为所有请求都要先过验证，实际实测结论是：

    >> 业务接口完全不需要过验证。全新 session、零 cookie，把首页 / ajax/data /
    >> ajax/suggest / 分类页 / 筛选页 / 详情页 / 播放页 挨个打一遍，9 个接口
    >> 全部正常返回，cookies 始终为空，没有一个被拦。
    >> 连续 25 次请求也只出现网络超时，从未出现验证页。

  真正会返回验证页的只有 /__xcdn/captcha/api/init 自己——而且一旦开始反复打它，
  它会进入约 60 秒的限速窗口（返回首页 HTML 而不是 JSON），窗口内重试会累积成
  十几分钟的长封禁。也就是说：**验证流程本身才是被封的原因，不碰它就没事。**

  所以本插件不做 PoW，只保留一个「见到验证页就如实报告」的检测，绝不主动去解。
  这段结论是花了很长时间踩坑换来的，改代码前请先读完上面几行。

============================== 数据来源 ==============================

【首页推荐】首页 HTML 里的卡片区块（<div class="a-con-inner">），1 个请求拿 30 条。

【一级分类】电影(1) / 电视剧(2) / 综艺(3) / 动漫(4) / 短剧(5)，
  与站内导航 /mbbatp/{tid}.html 一致。

【分类内容】/index.php/ajax/data?mid=1&tid={tid}&page={pg}&limit=30
  字段齐全（含年份/地区/演员/备注），total 准确，可以直接算总页数。

【二级筛选】站点的筛选是 URL 路径而不是查询参数，所以必须走 HTML 页面：
    /mbbasw/{tid}-{地区}-{排序}-{剧情}--{字母}--{页码}--{年份}.html
  拆开看固定 12 段，位置很反直觉（实测依据是页面里 107 条真实筛选链接）：
      [0]=tid  [1]=地区  [2]=排序  [3]=剧情  [5]=字母  [8]=页码  [11]=年份
  地区/剧情写的是中文名（如 韩国 / 古装），不是数字 id。
  多个维度可以组合，实测「韩国+古装」→ 5 条 1 页、「韩国+2026」→ 60 条 4 页，
  都是真实的交集结果。注意：某一段填了不存在的值，整页会退化成只有 0~1 张卡
  （站点把无法解析的路径当成空结果），而不是报错，所以出问题时先怀疑路径。
  筛选页每页 60 条（和 ajax 的 30 条不是一回事）。

【搜索】/index.php/ajax/suggest?mid=1&wd={kw}&limit=30
  只返回 id / name / pic / en，没有年份、备注、演员，数据比列表少。
  这是站点自己的搜索接口，比扒 HTML 稳。只支持第一页。

【详情】/mbbadt/{id}.html  HTML 页面。
  列表和搜索接口都不给 vod_play_url，播放数据只存在于播放页的
  var player_aaaa = {"from":"ffm3u8","sid":1,"nid":1,"url":"https://.../index.m3u8",...}
  里面。所以要拿全线路，必须逐个 sid 请求播放页。

  详情页结构（h1 全是板块标题，绝不能当片名）：
      <p class="tit">片名</p>
      <p class="type"><span>类型</span><span>年份</span><span>地区</span></p>
      p.daoyan / p.zhuyan / #articleText

【线路】/mbbapy/{id}-{sid}-{nid}.html，sid 从 1 递增。
  线路名和集数写在播放页的「切换线路」区：<a href="/mbbapy/{id}-{sid}-1.html">秒播<small>7</small></a>
  实测 from 有 ffm3u8 / vip / snm3u8 等，encrypt 恒为 0（不需要解密），url 直接可播。
  同一份源常挂在多个 sid 上（vip/vip3、snm3u8/snm3u85），所以要按 url 去重。

============================== 设计取舍 ==============================

1. 【不做 PoW】原因见上，验证流程本身会招来封禁，而业务接口根本不需要它。
2. 【详情要多次请求】要拿全线路就得对每个 sid 打一次播放页。线路清单从第 1 个页面
   里就能读到，不用盲试；其余 sid 并发补齐（3 线程，站点没做严格限流）。
3. 【播放零请求】详情阶段已经把 player_aaaa 里的 m3u8 存下来了，点播放直接命中缓存；
   其余集只存占位符 "EP|vid|sid|nid"，点开才解析——否则一部 100 集的剧要发 100 次请求。
4. 【筛选项按需加载】筛选项不在 homeContent 里全量抓（5 个分类 = 5 次请求），
   而是用户第一次进某个分类时补全，之后走缓存。homeContent 只给维度骨架。
5. 【不碰 /api.php】那个接口是 closed 的，反复试只会增加特征，没有意义。
"""

import re
import json
import time
import html as htmllib
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
import requests
from requests.adapters import HTTPAdapter
from base.spider import Spider


class Spider(Spider):
    # ==================== 基础配置 ====================
    name = "秒播影视"

    # 站点域名（换域名时改这里；也可以下面的 BASE_URL_CANDIDATES 里加候选）
    BASE_URL = "https://www.dgsxzn.com"
    BASE_URL_CANDIDATES = [
        "https://www.dgsxzn.com",
        # 换域名后在这里补一行
    ]

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    PLAY_UA = HEADERS["User-Agent"]

    PAGE_SIZE = 30          # 实测 ajax/data 与 suggest 的 limit 上限都是 30
    FILTER_PAGE_SIZE = 60   # 筛选页每页 60 条（HTML，和 ajax 的 30 条不同）
    # 实测这个站响应很飘：多数 0.1~1s，偶尔 10~19s。15s 会误杀，放宽到 25s
    REQ_TIMEOUT = 25
    DETAIL_WORKERS = 3      # 补线路时的并发，站点没做严格限流，3 足够且不扎眼
    MAX_SID = 8             # 探测线路时最多试到第几个 sid，防止个别页面 sid 无限递增

    # ==================== 一级分类 ====================
    # (tid, 名称)。tid 与站点 /mbbatp/{tid}.html 完全一致
    HOME_CHIPS = [
        ("1", "电影"),
        ("2", "电视剧"),
        ("3", "综艺"),
        ("4", "动漫"),
        ("5", "短剧"),
    ]

    # 站点分类页的筛选维度（显示名）。选项从页面动态抓，不写死
    FILTER_DIMS = ["剧情", "地区", "年份", "查找", "排序"]

    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=0)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        self._session.headers.update(self.HEADERS)
        self._lock = threading.Lock()

        self._base = self.BASE_URL
        # 是否见过验证页。只为「如实报告」而存在，不驱动任何重试逻辑
        self._blocked = False

        self._home_cache = (0.0, None)     # (ts, (items, filters))
        self._filter_cache = {}            # tid -> filters（会被后台预热线程写，用 _lock 护住）
        self._play_cache = {}              # "id-sid" -> {"url":..,"from":..,"eps":..}
        self._list_cache = {}              # (tid, pg) -> (ts, items)
        self._warm_started = False         # 筛选项预热线程是否已在跑
        self._filter_pending = {}          # tid -> Event，正在抓的筛选项（避免重复请求）
        self._filter_page_cache = {}       # path -> (ts, (items, pagecount))，筛选结果页缓存
        self._prefetching = {}             # path -> True，正在预取的页面
        self._detail_cache = {}            # vod_id -> 详情 dict

        self._re_player = re.compile(r"var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>", re.S)
        self._re_card = re.compile(
            r'<a\s+href="/mbbadt/(\d+)\.html"[^>]*?title="([^"]*)"', re.S)
        self._re_pub = re.compile(r"var\s+maccms\s*=\s*(\{.*?\})\s*;", re.S)
        self._re_page = re.compile(r'title="第(\d+)页"')
        # 列表卡片块：从 <div class="a-con-inner"> 到下一个同类块，内部含封面/评分/备注/标题
        self._re_block = re.compile(
            r'<div class="a-con-inner">(.*?)(?=<div class="a-con-inner">|</div>\s*</div>\s*</div>|\Z)',
            re.S)

    # ==================== HTTP ====================
    @staticmethod
    def _is_captcha(text):
        """判断返回的是不是 Xcdn 的验证页（标题 "Bot detection"）。

        实测业务接口不需要过验证，所以这个方法只用来「发现异常并如实报告」，
        不驱动任何重试或求解逻辑。真的见到它，说明站点策略变了，
        此时继续硬刷只会让情况更糟，宁可让用户看到一句人话。
        """
        if not text:
            return False
        return ("Bot detection" in text) or ("__xcdn/captcha" in text[:5000])

    def _get(self, path, referer=None, retry=2):
        """站内 GET。返回响应对象，彻底失败返回 None。

        【重试只针对网络问题】实测这个站响应很飘，偶尔 10~19 秒才回来甚至超时，
        但下一次往往就正常。所以超时/连接错误重试是值得的；
        HTTP 4xx/5xx 不重试（那就是站点明确拒绝，重试只会加深特征）。
        """
        url = path if path.startswith("http") else self._base + path
        headers = {}
        if referer:
            headers["Referer"] = referer
        for attempt in range(retry + 1):
            try:
                r = self._session.get(url, timeout=self.REQ_TIMEOUT,
                                      verify=False, headers=headers or None)
                if self._is_captcha((r.text or "")[:5000]):
                    if not self._blocked:
                        self._blocked = True
                        self._log("站点返回了人机验证页，本次请求放弃（不要重试，重试会加重限速）")
                    return None
                if r.status_code >= 400:
                    self._log("请求失败 %s: HTTP %s" % (path[:60], r.status_code))
                    return None
                self._blocked = False
                return r
            except Exception as e:
                # 网络抖动，退避后重试
                self._log("请求异常 %s: %s%s" % (
                    path[:50], type(e).__name__,
                    "，重试" if attempt < retry else "，放弃"))
                if attempt < retry:
                    time.sleep(1.5 * (attempt + 1))
        return None

    def _get_text(self, path, referer=None):
        r = self._get(path, referer)
        if r is None:
            return ""
        # 站点是 utf-8，但 requests 有时会猜成 ISO-8859-1，这里强制纠正
        if not r.encoding or r.encoding.lower() in ("iso-8859-1", "ascii"):
            r.encoding = "utf-8"
        return self._unwrap(r.text or "")

    @staticmethod
    def _unwrap(text):
        """还原「JSON 转义过的 HTML」。

        【为什么需要这个】站点的模板页（/mbbatp/、/mbbasw/ 这类）有两种返回方式：
        直接吐 HTML，或者把 HTML 塞进 JSON 字符串里下发——后者会把所有 '/' 转义成
        '\\/'，于是 </h2> 变成 <\\/h2>、href="/mbbadt/ 变成 href=\\"/mbbadt\\"，
        所有按路径写的正则全部失配，表现为「页面明明有 60 张卡片却解析出 0 条」。

        实测同一路径 /mbbatp/2.html 会稳定地走其中一种，但没有任何请求头能控制
        走哪条（Referer / X-Requested-With 都试过，无效），所以只能在解析前兜住。
        """
        if not text or "\\/" not in text:
            return text
        # 整包是 JSON 字符串时直接解码，最干净
        s = text.strip()
        if s.startswith('"') and s.endswith('"'):
            try:
                return json.loads(s)
            except Exception:
                pass
        # 否则退化成逐字符还原。只需处理 \/ 和 被转义的引号，
        # 其他 \\uXXXX 交给 htmllib.unescape 在字段级处理
        return text.replace("\\/", "/").replace('\\"', '"')

    def _get_json(self, path, referer=None):
        # 注意：这里【不能】用 _get_text —— 它会把 JSON 里的 "\\/" 还原掉，
        # 而 json.loads 自己就会处理转义，多此一举反而可能破坏字符串
        r = self._get(path, referer)
        if r is None:
            return {}
        if not r.encoding or r.encoding.lower() in ("iso-8859-1", "ascii"):
            r.encoding = "utf-8"
        txt = (r.text or "").strip()
        if not txt:
            return {}
        try:
            return json.loads(txt)
        except Exception:
            return {}

    # ==================== 域名探测 ====================
    def _probe(self, base):
        """判断一个域名是不是活的。

        用一个轻量接口（ajax/data 取 1 条）而不是首页：首页有 8 万多字节，
        探测成本没必要那么高；而且这个接口是 JSON，一眼就能看出是不是真站。
        """
        old = self._base
        try:
            self._base = base
            r = self._session.get(
                base + "/index.php/ajax/data?mid=1&tid=1&page=1&limit=1",
                timeout=self.REQ_TIMEOUT, verify=False)
            txt = (r.text or "").strip()
            if r.status_code != 200 or not txt.startswith("{"):
                return False
            return bool(json.loads(txt).get("list"))
        except Exception:
            return False
        finally:
            self._base = old   # 探测不改状态，由调用方决定是否切换

    def _resolve_base(self, force=False):
        """按候选顺序探测域名，第一个通的就用它。"""
        if not force and self._base:
            return self._base
        for cand in self.BASE_URL_CANDIDATES:
            cand = (cand or "").strip().rstrip("/")
            if not cand:
                continue
            if self._probe(cand):
                self._base = cand
                return cand
        # 全不通就用常量里的默认值，让后续请求自己报错
        self._base = self.BASE_URL
        return self._base

    # ==================== 工具 ====================
    def _log(self, msg):
        print("[%s] %s" % (self.name, msg))

    @staticmethod
    def _clean(text):
        """去标签、还原实体、压空格"""
        if not text:
            return ""
        text = htmllib.unescape(str(text))
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("\xa0", " ")
        return re.sub(r"\s+", " ", text).strip()

    def _abs(self, url):
        url = (url or "").strip()
        if not url or url in ("/", "None", "null"):
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        return self._base + "/" + url.lstrip("/")

    @staticmethod
    def _safe_url(url):
        """播放地址里有中文路径时做百分号编码"""
        if not url or not any(ord(c) > 127 for c in url):
            return url
        return urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")

    def _card(self, vid, name, pic="", remarks="", year="", area="", lang="", typ="", score=0.0):
        return {
            "vod_id": str(vid),
            "vod_name": self._clean(name),
            "vod_pic": self._abs(pic),
            "vod_remarks": self._clean(remarks) or self._clean(year),
            "_year": self._clean(year),
            "_area": self._clean(area),
            "_lang": self._clean(lang),
            "_type": self._clean(typ),
            "_score": score,
        }

    def _api_item_to_card(self, x):
        """ajax/data 的条目 -> 列表卡片（字段和 MacCMS 完全一致）"""
        vid = x.get("vod_id")
        name = x.get("vod_name")
        if not vid or not name:
            return None
        try:
            score = float(x.get("vod_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        # 注意这里的括号：站点两种字段都可能出现，vod_class 是字符串，
        # type 是对象时取 type_name。少了括号会让条件表达式把前半段整个吞掉
        typ = x.get("vod_class") or ""
        if not typ and isinstance(x.get("type"), dict):
            typ = x["type"].get("type_name") or ""
        return self._card(
            vid, name,
            pic=x.get("vod_pic") or "",
            remarks=x.get("vod_remarks") or "",
            year=x.get("vod_year") or "",
            area=x.get("vod_area") or "",
            lang=x.get("vod_lang") or "",
            typ=typ,
            score=score,
        )

    @staticmethod
    def _to_cards(items):
        """下发给壳子时去掉下划线字段"""
        out = []
        for it in items:
            out.append({
                "vod_id": it["vod_id"],
                "vod_name": it["vod_name"],
                "vod_pic": it.get("vod_pic", ""),
                "vod_remarks": it.get("vod_remarks", ""),
            })
        return out

    def _parse_cards(self, html):
        """从首页/分类/筛选页解析卡片列表。

        站点模板每张卡片是一个 <div class="a-con-inner">，里面依次是：
            封面 <img data-src="...">  |  评分 .s3  |  备注 .s4  |  标题 .s1 > a[href]
        按块解析才能把评分/备注/封面正确配对；只看 <a href="/mbbadt/"> 的话
        只能拿到 id 和片名，备注和封面全都丢。
        """
        items, seen = [], set()
        for bm in self._re_block.finditer(html):
            block = bm.group(1)
            lm = re.search(r'<a\s+href="/mbbadt/(\d+)\.html"[^>]*title="([^"]*)"', block)
            if not lm:
                continue
            vid, name = lm.group(1), self._clean(lm.group(2))
            if not vid or not name or vid in seen:
                continue
            seen.add(vid)

            pm = re.search(r'<img[^>]+data-src="([^"]+)"', block) or \
                 re.search(r'<img[^>]+src="([^"]+)"', block)
            pic = self._abs(pm.group(1)) if pm else ""
            if "/load.gif" in pic:  # 占位图，不是真封面
                pic = ""
            sm = re.search(r'class="s3[^"]*"[^>]*>\s*([\d.]+)\s*<', block)
            rm = re.search(r'class="s4[^"]*"[^>]*>\s*([^<]{1,24})\s*<', block)
            items.append(self._card(
                vid, name, pic=pic,
                remarks=self._clean(rm.group(1)) if rm else "",
                score=float(sm.group(1)) if sm and sm.group(1) else 0.0,
            ))
        return items

    # ==================== 首页 ====================
    def _parse_home(self):
        """解析首页：拿「最近更新」区块，一次请求搞定"""
        html = self._get_text("/", referer=self._base + "/")
        if not html:
            return [], []
        return self._parse_cards(html), []

    def homeContent(self, filter=False):
        classes = [{"type_id": tid, "type_name": label} for tid, label in self.HOME_CHIPS]
        result = {"class": classes}
        if filter:
            # 【首屏不阻塞】之前这里只返回空骨架，用户点开筛选栏只能看到一个「全部」，
            # 必须先进分类页才会补全 —— 观感就是「慢 / 没加载出来」。
            # 现在改成：有缓存直接给；没缓存就返回骨架，同时丢一个后台线程去预热，
            # 下一次请求（TVBox 打开筛选面板时常会再拉一次）就拿到完整选项了。
            filters = {}
            missing = False
            for tid, _ in self.HOME_CHIPS:
                cached = self._filter_cache.get(tid)
                if cached:
                    filters[tid] = cached
                else:
                    filters[tid] = self._skeleton_filters()
                    missing = True
            if missing:
                self._warm_filters()
            result["filters"] = filters
            result["filter"] = filters
        return result

    def _skeleton_filters(self):
        """筛选骨架：只有维度和「全部」，选项等用户进分类时再补。

        骨架本身就能让壳子正常显示筛选栏，不点具体选项时行为和无筛选一致。
        """
        return [{"key": d, "name": d, "value": [{"n": "全部", "v": ""}]}
                for d in self.FILTER_DIMS]

    def _busy_msg(self):
        """返回给用户看的「为什么没数据」。空字符串表示当前正常。

        返回空列表时必须和「真的没这部片」区分开，否则用户会以为源坏了或者片子下架了。
        """
        if self._blocked:
            return "站点返回了人机验证页，请稍后再试（不要连续刷新，会加重限制）"
        return ""

    def homeVideoContent(self):
        ts, cached = self._home_cache
        if cached and time.time() - ts < 600:
            return {"list": self._to_cards(cached[: self.PAGE_SIZE])}
        try:
            items, _ = self._parse_home()
            if items:
                self._home_cache = (time.time(), items)
                return {"list": self._to_cards(items[: self.PAGE_SIZE])}
        except Exception as e:
            self._log("homeVideoContent 异常: %s" % e)
        msg = self._busy_msg()
        return {"list": [], "msg": msg} if msg else {"list": []}

    # ==================== 筛选（二级分类） ====================
    def _get_filters(self, tid):
        """从分类页的筛选面板动态抓选项，不写死。

        面板结构：<dl><dt><h2>剧情</h2></dt><dd><a href="/mbbasw/...">古装</a>...</dd></dl>
        路径格式 /mbbasw/{tid}-{area}--{class}--{year}--{by}-{letter}--{pg}.html，
        不同维度落在不同位置，所以直接把整段路径当 value 存下来，避免自己拼错。
        """
        hit = self._filter_cache.get(tid)
        if hit:
            return hit

        # 【原子地检查+登记】这一步必须和预热线程互斥：
        # 否则会出现「我查缓存时预热还没登记，等我发请求时预热也发了」的竞态，
        # 同一个分类页被请求两次（实测会多花一个 RTT）。
        with self._lock:
            hit = self._filter_cache.get(tid)
            if hit:
                return hit
            pend = self._filter_pending.get(tid)
            if pend is None:
                pend = threading.Event()
                self._filter_pending[tid] = pend
                leader = True
            else:
                leader = False

        if not leader:
            # 别人正在抓，等它，共用结果
            try:
                pend.wait(10.0)
            except Exception:
                pass
            got = self._filter_cache.get(tid)
            return got or self._skeleton_filters()

        try:
            filters = self._fetch_filters(tid)
        finally:
            with self._lock:
                if self._filter_pending.get(tid) is pend:
                    del self._filter_pending[tid]
            pend.set()
        return filters or self._skeleton_filters()

    def _fetch_filters(self, tid):
        """真正去抓一个分类的筛选项并写缓存。抓不到返回 []，不写缓存。"""
        html = self._get_text("/mbbatp/%s.html" % tid, referer=self._base + "/")
        filters = self._parse_filters(html)
        if filters:
            with self._lock:
                self._filter_cache[tid] = filters
        return filters

    def _parse_filters(self, html):
        """从分类页 HTML 里抠出筛选面板 -> filters 结构。抓不到返回 []。"""
        filters = []
        if not html:
            return filters
        for dm in re.finditer(r"<dt><h2>([^<]{1,10})</h2></dt>\s*<dd>(.*?)</dd>", html, re.S):
            dim = dm.group(1).strip()
            body = dm.group(2)
            opts = []
            for a, label in re.findall(r'href="(/mbbasw/[^"]+)"[^>]*>([^<]{1,12})<', body):
                a = htmllib.unescape(a)
                label = self._clean(label)
                if not label:
                    continue
                # 全部 -> 空值表示「不限」
                if label == "全部":
                    opts.append({"n": "全部", "v": ""})
                else:
                    opts.append({"n": label, "v": a})
            if opts:
                filters.append({"key": dim, "name": dim, "value": opts})
        return filters

    def _warm_filters(self):
        """后台预热 5 个分类的筛选项。

        单独放一个方法是因为它要在【后台线程】里跑：宁可慢一点后台补，
        也不要把用户卡在首屏。实测 5 个分类页并发抓只要 0.3 秒左右。
        """
        if self._warm_started:
            return
        self._warm_started = True

        def job():
            def one(tid):
                if tid in self._filter_cache:
                    return
                # 先登记「我在抓这个」，让同时进分类的请求等着共用结果，
                # 而不是自己再发一次同样的请求
                ev = threading.Event()
                with self._lock:
                    if tid in self._filter_pending:
                        return          # 别人已经在抓了
                    self._filter_pending[tid] = ev
                try:
                    self._fetch_filters(tid)
                finally:
                    with self._lock:
                        if self._filter_pending.get(tid) is ev:
                            del self._filter_pending[tid]
                    ev.set()

            try:
                with ThreadPoolExecutor(max_workers=len(self.HOME_CHIPS)) as pool:
                    list(pool.map(one, [t for t, _ in self.HOME_CHIPS]))
            except Exception as e:
                self._log("筛选项预热失败: %s" % e)
            finally:
                self._warm_started = False

        threading.Thread(target=job, daemon=True).start()

    # 站点筛选路径 /mbbasw/{tid}-{地区}--{剧情}--{年份}--{排序}-{字母}--{页码}.html
    # 拆开看固定是 12 段（实测全部样本都是 12 段，缺省段为空字符串）：
    #   [0]=tid  [1]=地区  [2]=排序  [3]=剧情  [5]=字母  [8]=页码  [11]=年份
    # 注意顺序很反直觉（年份在最后、排序在第 2 段），必须按位置放，不能按视觉顺序拼。
    FILTER_DIM_POS = {
        "地区": 1,
        "排序": 2,
        "剧情": 3,
        "查找": 5,
        "年份": 11,
    }
    FILTER_PATH_SEGS = 12

    def _pick_filter(self, content, dim):
        """从用户提交的筛选里取出某个维度的值（value 是整段 /mbbasw 路径）"""
        if not isinstance(content, dict):
            return ""
        v = content.get(dim)
        if not v:
            return ""
        if isinstance(v, list):
            v = v[0] if v else ""
        return str(v)

    def _build_filter_path(self, tid, content, pg):
        """把用户选的多个维度拼成站点能识别的筛选路径。

        站点每个选项自己的路径只带它自己那一维，我们要把多选合成一条，
        所以先按位置把各维度的值从原路径里抠出来，再一次性重排。

        【踩过的坑】站点给的 href 是【已百分号编码】的（2-%E9%9F%A9%E5%9B%BD---...），
        如果直接拿这段去冒号拼接再 quote() 一次，就会变成 %25E9（双重编码），
        站点认不出来，整页退化成 0 条。所以这里先 unquote 还原成中文再统一编码。
        """
        segs = [""] * self.FILTER_PATH_SEGS
        segs[0] = str(tid)

        for dim, pos in self.FILTER_DIM_POS.items():
            raw = self._pick_filter(content, dim)
            if not raw:
                continue
            # 先解码，去掉可能存在的重复编码
            raw = urllib.parse.unquote(raw)
            name = raw.rstrip("/").split("/")[-1]
            if not name.endswith(".html"):
                continue
            parts = name[:-5].split("-")
            if pos < len(parts) and parts[pos]:
                segs[pos] = parts[pos]

        if pg and int(pg) > 1:
            segs[8] = str(int(pg))

        path = "-".join(segs) + ".html"
        return "/mbbasw/" + urllib.parse.quote(path, safe="-_~.")

    def _parse_list_page(self, html):
        """解析分类/筛选页的条目列表 + 总页数"""
        items = self._parse_cards(html)
        pages = [int(x) for x in self._re_page.findall(html)] or [1]
        return items, max(pages)

    def _prefetch_next(self, path, tid):
        """后台预取下一页筛选结果。失败无所谓，用户翻页时再正常请求一次。"""
        if path in self._filter_page_cache or path in self._prefetching:
            return
        self._prefetching[path] = True

        def job():
            try:
                html = self._get_text(path, referer=self._base + "/mbbatp/%s.html" % tid)
                items, pagecount = self._parse_list_page(html)
                if items:
                    self._filter_page_cache[path] = (time.time(), (items, pagecount))
                    # 缓存别无限长：只留最近 40 个页面
                    if len(self._filter_page_cache) > 40:
                        for k in sorted(self._filter_page_cache,
                                        key=lambda x: self._filter_page_cache[x][0])[:10]:
                            self._filter_page_cache.pop(k, None)
            except Exception:
                pass
            finally:
                self._prefetching.pop(path, None)

        threading.Thread(target=job, daemon=True).start()

    def categoryContent(self, tid, pg, filter=False, content=None):
        try:
            pg = max(1, int(pg or 1))
        except (TypeError, ValueError):
            pg = 1

        # 用户第一次进这个分类时补全筛选项（1 次请求，之后走缓存）。
        # 放在这里而不是 homeContent，是为了把请求摊到用户真正要看的分类上。
        # 如果后台预热已经在跑，这里就直接去等它的结果（_get_filters 内部会读缓存），
        # 不额外开一次请求 —— 预热线程本来就只抓一次。
        if filter and tid not in self._filter_cache:
            self._get_filters(tid)

        flt = {}
        if content:
            flt = content if isinstance(content, dict) else {}
            if not isinstance(flt, dict):
                try:
                    flt = json.loads(content)
                except Exception:
                    flt = {}

        # 有筛选条件就走 HTML 筛选页；纯分类走 ajax 接口（更快、字段更全）
        has_filter = any(flt.get(d) for d in self.FILTER_DIMS) if isinstance(flt, dict) else False

        if has_filter:
            path = self._build_filter_path(tid, flt, pg)
            hit = self._filter_page_cache.get(path)
            if hit and time.time() - hit[0] < 300:
                items, pagecount = hit[1]
            else:
                html = self._get_text(path, referer=self._base + "/mbbatp/%s.html" % tid)
                items, pagecount = self._parse_list_page(html)
                if items:
                    self._filter_page_cache[path] = (time.time(), (items, pagecount))
            # 用户还在看这一页时就把下一页抓回来，翻页时大概率直接命中缓存。
            # 实测这个站的延迟波动很大（多数 0.02s，偶尔 1~2s），预取能把这种波动
            # 挪到用户还没点击的时候，体感差别很明显。
            if items and pg < (pagecount or 1):
                self._prefetch_next(self._build_filter_path(tid, flt, pg + 1), tid)
            # 筛选页每页固定 60 条（实测），和 ajax 接口的 30 条不是一回事，
            # 所以 total 要按 60 算，别拿 PAGE_SIZE 套
            result = {
                "list": self._to_cards(items),
                "page": pg,
                "pagecount": pagecount or 1,
                "limit": len(items) or 60,
                "total": (pagecount - 1) * 60 + len(items) if pagecount > 1 else len(items),
            }
            if not items:
                msg = self._busy_msg()
                if msg:
                    result["msg"] = msg
            return result

        key = (tid, pg)
        hit = self._list_cache.get(key)
        if hit and time.time() - hit[0] < 600:
            items, pagecount, total = hit[1]
        else:
            d = self._get_json("/index.php/ajax/data?mid=1&tid=%s&page=%d&limit=%d"
                               % (tid, pg, self.PAGE_SIZE))
            raw = d.get("list") or []
            items = [c for c in (self._api_item_to_card(x) for x in raw) if c]
            total = int(d.get("total") or 0)
            pagecount = int(d.get("pagecount") or 0) or max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            if items:
                self._list_cache[key] = (time.time(), (items, pagecount, total))
                # 顺手把下一页抓回来（只在还有下一页时）。
                # 列表页接口本身很快（中位数 0.6s），但这站偶尔抽到十几秒，
                # 预取能让这种抖动落在用户还没滑到的时候。
                if pg < pagecount:
                    self._prefetch_list(tid, pg + 1)

        result = {
            "list": self._to_cards(items),
            "page": pg,
            "pagecount": pagecount,
            "limit": self.PAGE_SIZE,
            "total": total,
        }
        if not items:
            msg = self._busy_msg()
            if msg:
                result["msg"] = msg
        return result

    def _prefetch_list(self, tid, pg):
        """后台预取 ajax 列表的下一页。"""
        key = (tid, pg)
        if key in self._list_cache or key in self._prefetching:
            return
        self._prefetching[key] = True

        def job():
            try:
                d = self._get_json("/index.php/ajax/data?mid=1&tid=%s&page=%d&limit=%d"
                                   % (tid, pg, self.PAGE_SIZE))
                raw = d.get("list") or []
                items = [c for c in (self._api_item_to_card(x) for x in raw) if c]
                if not items:
                    return
                total = int(d.get("total") or 0)
                pagecount = int(d.get("pagecount") or 0) or max(
                    1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
                self._list_cache[key] = (time.time(), (items, pagecount, total))
                if len(self._list_cache) > 60:
                    for k in sorted(self._list_cache, key=lambda x: self._list_cache[x][0])[:15]:
                        self._list_cache.pop(k, None)
            except Exception:
                pass
            finally:
                self._prefetching.pop(key, None)

        threading.Thread(target=job, daemon=True).start()

    # ==================== 搜索 ====================
    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = max(1, int(pg or 1))
        except (TypeError, ValueError):
            pg = 1
        kw = self._clean(key)
        if not kw:
            return {"list": [], "page": pg, "pagecount": 1, "limit": self.PAGE_SIZE, "total": 0}

        # 站点搜索接口只支持第一页，翻页时客户端会传 pg>1，这里直接复用第一页结果
        d = self._get_json("/index.php/ajax/suggest?mid=1&wd=%s&limit=%d"
                           % (urllib.parse.quote(kw), self.PAGE_SIZE))
        raw = d.get("list") or []
        items = []
        for x in raw:
            vid, name = x.get("id"), x.get("name")
            if not vid or not name:
                continue
            items.append(self._card(vid, name, pic=x.get("pic") or ""))
        total = int(d.get("total") or len(items))

        # 精确匹配排前面，壳子默认取第一条进详情，排序直接影响体验
        low = kw.lower()
        def rank(it):
            n = (it.get("vod_name") or "").lower()
            if n == low:
                return 0
            if n.startswith(low):
                return 1
            if low in n:
                return 2
            return 3
        items.sort(key=rank)

        result = {
            "list": self._to_cards(items),
            "page": pg,
            "pagecount": 1,
            "limit": self.PAGE_SIZE,
            "total": total,
        }
        # 搜不到时要区分「真没有这部片」和「被限速了没请求出去」，
        # 后者静默返回空列表会让人误判
        if not items:
            msg = self._busy_msg()
            if msg:
                result["msg"] = msg
        return result

    # ==================== 详情：解析播放页拿全线路 ====================
    def _fetch_play_page(self, vid, sid):
        """取播放页的 player_aaaa，返回 (url, from, 同线路集数, 线路总数信息)"""
        path = "/mbbapy/%s-%d-1.html" % (vid, sid)
        html = self._get_text(path, referer="%s/mbbadt/%s.html" % (self._base, vid))
        if not html:
            return None
        m = self._re_player.search(html)
        if not m:
            return None
        try:
            pj = json.loads(m.group(1))
        except Exception:
            return None
        url = self._safe_url(str(pj.get("url") or "").strip())
        if not url:
            return None

        # 线路名和集数在「切换线路」区（实测结构，注意【链接是 javascript:;，不是 /mbbapy/】）：
        #   <span class="mxianlu ...">
        #       <a href="javascript:;" class="active">秒播<small>46</small></a>
        #       <a href="javascript:;" class="">非凡<small>46</small></a>
        #   </span>
        # 之前按 href="/mbbapy/{vid}-{sid}-1.html" 找，结果永远只匹配到 1 条线路，
        # 因为站点把换线路做成了 JS 点击。这里改成在 mxianlu 容器里按顺序取，
        # 序号 i 就是 sid（站点的 sid 是 1 起连续的，第 i 个 <a> 对应 sid=i）。
        lines = []  # [(sid, 名称, 集数)]
        box = re.search(r'class="mxianlu[^"]*">(.*?)</span>\s*</span>', html, re.S)
        if box:
            for i, lm in enumerate(
                    re.finditer(r'<a\s[^>]*>\s*([^<>]{1,16}?)\s*<small>\s*(\d+)\s*</small>',
                                box.group(1)), 1):
                lines.append((i, self._clean(lm.group(1)), int(lm.group(2))))

        # 兜底：万一模板改回带 href 的写法，也认
        if not lines:
            for lm in re.finditer(
                    r'href="/mbbapy/%s-(\d+)-1\.html"[^>]*>\s*([^<]{0,14}?)\s*<small>(\d+)</small>'
                    % re.escape(str(vid)), html):
                lines.append((int(lm.group(1)), self._clean(lm.group(2)), int(lm.group(3))))

        # 选集链接：/mbbapy/{vid}-{sid}-{nid}.html
        # 注意第 1 集的链接和上方「切换线路」按钮是同一个地址
        # （{vid}-{sid}-1.html），标签会被解析成线路名，所以第 1 集的名字不能靠这个，
        # 统一用「第01集」补齐，页面上拿到的标签只覆盖 nid>1 的部分。
        eps = {}
        for em in re.finditer(r'href="/mbbapy/%s-(\d+)-(\d+)\.html"[^>]*>\s*([^<]{1,14}?)\s*<'
                              % re.escape(str(vid)), html):
            s_, n_, label = int(em.group(1)), int(em.group(2)), self._clean(em.group(3))
            if s_ == sid and label and n_ > 1:
                eps[n_] = label

        # 集数取三种来源里最可靠的那个：
        #   [1] 选集链接实际有几个 nid —— 这是用户真正能点的集，最可信
        #   [2] 「切换线路」里该 sid 的 <small>N</small> 标注
        #   [3] 都没有就至少保证当前这一集有标签
        # 实测这三者会互相打架（例如 sid=1 有 8 个选集链接但 <small> 标 7），
        # 所以取【最大值】：宁可多给一集（点开是空的），也不要少给（用户点不到）。
        total_links = max(eps) if eps else 0
        total_label = 0
        for s_id, _nm, cnt in lines:
            if s_id == sid and cnt:
                total_label = cnt
                break
        total = max(total_links, total_label)
        if total:
            for n in range(1, total + 1):
                eps.setdefault(n, "第%02d集" % n)
        else:
            # 页面没写集数时，至少保证当前这一集有标签
            eps.setdefault(int(pj.get("nid") or 1), "第01集")

        return {
            "url": url,
            "from": str(pj.get("from") or "").strip(),
            "vid": str(vid),
            "sid": sid,
            "nid": int(pj.get("nid") or 1),
            "lines": lines,
            "eps": eps,
            "total": total,
        }

    def _fetch_ep_url(self, vid, sid, nid):
        """取某一集某一线路的真实播放地址（详情阶段用不到每一集，播放时按需取）"""
        path = "/mbbapy/%s-%d-%d.html" % (vid, sid, nid)
        html = self._get_text(path, referer="%s/mbbadt/%s.html" % (self._base, vid))
        m = self._re_player.search(html or "")
        if not m:
            return ""
        try:
            pj = json.loads(m.group(1))
        except Exception:
            return ""
        return self._safe_url(str(pj.get("url") or "").strip())

    def _fetch_detail_html(self, vid):
        """解析详情页的基本信息。

        详情页结构（实测）：
            <p class="tit">片名</p>
            <p class="type"><span><a>类型</a></span><span><a>2026</a></span><span><a>大陆</a></span></p>
            <p class="daoyan"><span class="name">导演：</span><a>刘新</a></p>
            <p class="zhuyan"><span class="name">主演：</span><a>蒋欣</a>...</p>
            <div id="articleText">剧情…</div>
        注意 h1 全是「关联推荐/猜你喜欢」这类板块标题，绝不能拿 h1 当片名。
        """
        html = self._get_text("/mbbadt/%s.html" % vid, referer=self._base + "/")
        if not html:
            return {}
        info = {"vod_id": str(vid)}

        def pick(pat, idx=1, default=""):
            m = re.search(pat, html, re.S)
            if not m:
                return default
            return self._clean(m.group(idx))

        # 片名：p.tit 最准；兜底用 <title>《...》里的书名号内容
        name = pick(r'<p class="tit">\s*(.*?)\s*</p>')
        if not name:
            tm = re.search(r"<title>\s*《(.*?)》", html, re.S)
            name = self._clean(tm.group(1)) if tm else pick(r"<title>(.*?)</title>").split("_")[0]
        info["vod_name"] = name.strip("《》 ")

        info["vod_pic"] = self._abs(
            pick(r'class="cover"[^>]+background-image:\s*url\(([^)]+)\)')
            or pick(r'<img[^>]+class="lazyload"[^>]+data-src="([^"]+)"')
        )

        # 类型区三个 <span>：类型 / 年份 / 地区。按位置取，比正则匹配文字稳
        info["vod_type"] = ""
        tm = re.search(r'<p class="type">(.*?)</p>', html, re.S)
        if tm:
            spans = [self._clean(x) for x in re.findall(r"<span>(.*?)</span>", tm.group(1), re.S)]
            spans = [s for s in spans if s]
            if spans:
                info["vod_type"] = spans[0]
            if len(spans) > 1 and re.fullmatch(r"[12]\d{3}", spans[1]):
                info["vod_year"] = spans[1]
            if len(spans) > 2:
                info["vod_area"] = spans[2]

        info.setdefault("vod_year", "")
        info.setdefault("vod_area", "")
        if not info.get("vod_year"):
            info["vod_year"] = pick(r"([12]\d{3})\s*</a>")
        if not info.get("vod_area"):
            info["vod_area"] = ""

        info["vod_director"] = pick(r'class="daoyan".*?name">\s*导演[：:]\s*</span>\s*(.*?)</p>')
        info["vod_actor"] = pick(r'class="zhuyan[^"]*".*?name">\s*主演[：:]\s*</span>\s*(.*?)</p>')
        info["vod_remarks"] = pick(r'集数[：:]\s*([^<]{1,20})') or pick(r'<span class="s4[^"]*">\s*([^<]{1,20})\s*<')
        info["vod_content"] = pick(r'id="articleText"[^>]*>(.*?)</div>')
        return info

    def _collect_lines(self, vid):
        """把这部片的全部线路都取回来。

        先打 sid=1 拿线路清单（页面里直接写着有哪些线路、各多少集），
        再按清单并发补齐其余 sid —— 不盲试，省掉一堆 404。
        返回前按播放地址去重：站点同一份源会挂好几个 sid（vip/vip3、snm3u8/snm3u85），
        内容完全一样，不去重用户会看到两条一模一样的线路。
        """
        first = self._fetch_play_page(vid, 1)
        if not first:
            return []
        self._play_cache["%s-1" % vid] = first

        lines = first.get("lines") or []
        sids = [s for s, _, _ in lines if s != 1]
        # 页面没给线路清单时，保守地往后试几个 sid
        if not sids:
            sids = list(range(2, min(self.MAX_SID, 4) + 1))

        rest = []
        if sids:
            def job(sid):
                return self._fetch_play_page(vid, sid)
            with ThreadPoolExecutor(max_workers=self.DETAIL_WORKERS) as pool:
                for r in pool.map(job, sids[: self.MAX_SID]):
                    if r:
                        rest.append(r)
                        self._play_cache["%s-%d" % (vid, r["sid"])] = r

        # 按 sid 排序，保证线路顺序稳定（和站点一致）
        allp = sorted([first] + rest, key=lambda x: x["sid"])

        # 按播放地址去重，保留 sid 最小的那条（和站点默认选中一致）
        out, seen_url = [], set()
        for p in allp:
            url = p.get("url") or ""
            if not url or url in seen_url:
                continue
            seen_url.add(url)
            out.append(p)
        return out

    @staticmethod
    def _line_name(p, idx):
        """线路显示名：优先用站点给的名字，其次用 from 字段"""
        for sid, name, _ in p.get("lines") or []:
            if sid == p.get("sid") and name:
                return name
        frm = (p.get("from") or "").strip()
        return frm or ("线路%d" % idx)

    def detailContent(self, ids):
        try:
            vid = str(ids[0] if isinstance(ids, list) else ids).strip()
            vid = re.sub(r"[^\d]", "", vid)
            if not vid:
                return {"list": []}

            # 【详情页解析和线路抓取并发】这两件事互不依赖：详情页给片名/简介/封面，
            # 播放页给线路和选集。串行做就是两个 RTT 相加，实测能省掉 0.5 秒左右。
            with ThreadPoolExecutor(max_workers=2) as pool:
                f_info = pool.submit(self._fetch_detail_html, vid)
                f_lines = pool.submit(self._collect_lines, vid)
                info = f_info.result()
                lines = f_lines.result()
            if not lines:
                self._log("详情无可用线路: %s" % vid)
                msg = self._busy_msg()
                return {"list": [], "msg": msg} if msg else {"list": []}

            from_list, url_list, seen = [], [], set()
            for i, p in enumerate(lines, 1):
                name = self._line_name(p, i)
                if name in seen:
                    name = "%s%d" % (name, i)
                seen.add(name)
                from_list.append(name)

                # 这一线路的全部集：优先用页面里的选集列表，兜底只给第 1 集
                eps = p.get("eps") or {}
                # 集数以「切换线路」里的 <small>N</small> 为准（p['total']）。
                # 页面上的选集区块常常只渲染前若干集（实测有只给 20 个链接、但标注 46 集的），
                # 只按 eps 的键补齐会让剧集「看起来只有 20 集」，用户点不到后面的
                total_eps = int(p.get("total") or 0)
                top = max(total_eps, max(eps) if eps else 0)
                if top:
                    seq = [eps.get(k) or "第%02d集" % k for k in range(1, top + 1)]
                else:
                    seq = ["第01集"]
                # 详情阶段只把「刚刚真实取到地址的那一集」写成真地址（它的 nid 是 p['nid']），
                # 其余集写占位符，播放时再按需解析——否则一部 100 集的剧要发 100 次请求
                cur_nid = int(p.get("nid") or 1)
                cells = []
                for j in range(1, len(seq) + 1):
                    label = seq[j - 1]
                    # 第 cur_nid 集已经真实取到地址了，直接给；其余给占位符
                    if j == cur_nid:
                        cells.append("%s$%s" % (label, p["url"]))
                    else:
                        cells.append("%s$%s|%s|%d|%d" % (label, "EP", vid, p["sid"], j))
                url_list.append("#".join(cells))

            name = info.get("vod_name") or ""
            video = {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": info.get("vod_pic") or "",
                "vod_year": info.get("vod_year") or "",
                "vod_area": info.get("vod_area") or "",
                "vod_actor": info.get("vod_actor") or "",
                "vod_director": info.get("vod_director") or "",
                "vod_content": info.get("vod_content") or "",
                "vod_remarks": info.get("vod_remarks") or "",
                "vod_play_from": "$$$".join(from_list),
                "vod_play_url": "$$$".join(url_list),
            }
            self._log("详情成功: %s 线路(%d): %s" % (name, len(from_list), "/".join(from_list)))
            return {"list": [video]}
        except Exception as e:
            self._log("detailContent 异常: %s" % e)
            msg = self._busy_msg()
            return {"list": [], "msg": msg} if msg else {"list": []}

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags=None):
        try:
            raw = str(id or "").strip()
            if not raw:
                return {"parse": 0, "url": "", "header": ""}

            # 第 1 集在详情阶段已经带了真实地址
            if raw.startswith("http"):
                return {"parse": 0, "url": raw, "header": self._play_headers()}

            # 其余集：占位符 "EP|vid|sid|nid"，按需解析
            if raw.startswith("EP|"):
                parts = raw.split("|")
                if len(parts) >= 4:
                    vid, sid, nid = parts[1], int(parts[2]), int(parts[3])
                    url = self._fetch_ep_url(vid, sid, nid)
                    if url:
                        return {"parse": 0, "url": url, "header": self._play_headers()}
                return {"parse": 0, "url": "", "header": ""}

            # 兼容壳子传 "集名$地址" 的情况
            if "$" in raw:
                raw = raw.split("$")[-1].strip()
                if raw.startswith("http"):
                    return {"parse": 0, "url": raw, "header": self._play_headers()}

            return {"parse": 1, "url": raw, "header": self._play_headers()}
        except Exception as e:
            self._log("playerContent 异常: %s" % e)
            return {"parse": 0, "url": "", "header": ""}

    def _play_headers(self):
        return {
            "User-Agent": self.PLAY_UA,
            "Referer": self._base + "/",
            "Accept": "*/*",
        }

    # ==================== 初始化 ====================
    def init(self, extend=""):
        # extend 里可以指定域名：{"base": "https://xxx.com"}
        try:
            ext = {}
            if isinstance(extend, dict):
                ext = extend
            elif isinstance(extend, str) and extend.strip():
                try:
                    ext = json.loads(extend)
                except Exception:
                    ext = {}
            manual = ""
            if isinstance(ext, dict):
                manual = str(ext.get("base") or ext.get("baseUrl") or ext.get("url") or "").strip()
            if manual:
                manual = manual.rstrip("/")
                if not manual.startswith("http"):
                    manual = "https://" + manual
                self._base = manual
        except Exception as e:
            self._log("解析 extend 失败: %s" % e)

        # 【init 里不发任何请求】
        # 业务接口不需要过验证（见文件头），所以初始化没有「必须先做的事」。
        # 而 TVBox 打开源时是同步调 init，一旦这里发起网络请求（这个站偶尔要 10~19 秒
        # 才响应），整个 App 会卡在启动页。让它秒返回，真正的请求交给用户触发。
        self._log("初始化完成 (%s)" % self._base)

    # ==================== 壳子可选接口 ====================
    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4|flv|mkv|ts)(?:[?#]|$)", str(url or ""), re.I))

    def manualVideoCheck(self):
        return False
