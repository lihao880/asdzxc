# -*- coding: utf-8 -*-
# 八戒影视 (hipy / CatVod / TVBox 类爬虫)
#
# 本资源来源于互联网公开渠道, 仅可用于个人学习爬虫技术。
# 严禁用于商业用途, 下载后请于 24 小时内删除。
# 搜索结果均来自源站, 作者不承担任何责任。
#
# ------------------------------------------------------------------ 修复说明
#
# 相对原版, 这一版修了 10 个问题 (每条都经过实测确认):
#
# 1) typeId 不再硬编码
#    原版 detailContent 写死 "M17"、playerContent 写死 "M16" —— 而服务端
#    typeId 的真实含义是: M15=电视剧 M16=电影 M17=动漫 M18=综艺 M14=短剧
#    (见 screenType 接口返回)。等于"按动漫查详情、按电影去播放"。
#    实测当前服务端不校验 typeId(传错也返回同样数据), 所以表面上能用,
#    但这是靠运气——服务端哪天补了校验, 全站立刻失效。
#    现改为从条目自带的 typeId 透传: vod_id = "<typeId>|<id>"。
#
# 2) 分类树只取了顶层, 丢了筛选维度
#    screenType 返回三级嵌套: 电视剧(M15) -> 地区(M19)/类型(M31)/年份(M50)。
#    原版只取顶层 6 个当 tab, 子节点全丢。现在顶层做 tab, 二三级展开成
#    TVBox 的 filters(地区/类型/年份 三个下拉), 分类数不变但可筛维度全在。
#
# 3) 解析出的地址可能 302, 原版直接丢给播放器
#    实测有的源(如 cibn-edge-5g.1ljx.com)返回 302 跳转, 有的(如
#    log.alibabacloud.vip)是 200 直链。原版一律 parse=0 把 302 地址丢给
#    播放器, 部分播放器不跟随 302 -> 黑屏。现在先探测一次, 302 就自己
#    跟到底拿到最终地址再交出去。
#    ★ 但 302 有"糊"的情况: 实测优酷源 2 个不同的集地址被转到同一个上游,
#      跟随反而把多集合并成一集。所以加了撞车检测 —— 原始地址不同、302
#      目标却相同, 就保留原地址不跟。
#
# 4) 播放地址为空/是网页时仍返回 parse=0
#    原版 analysisMovieUrl 返回空串或 None 时, 仍然构造
#    {"parse":"0","url":""} 交给播放器 -> 黑屏无提示。
#    现在按地址真实形态判定: m3u8/mp4 -> parse=0; 网页 -> parse=1;
#    空 -> 返回空 url 让壳子走失败分支, 而不是假装能播。
#
# 5) 去掉外部歌词依赖
#    原版在文件末尾劫持 Spider.playerContent, 每次播放都去
#    chuxinya.top 拉一个 mp4 再 base64 解码当歌词。那个站挂了/返回非
#    base64 就静默失败, 还要多等最多 5 秒。已删除, 改成开关(默认关)。
#
# 6) 域名配置加兜底
#    原版只能从 osstexll.oss-... 阿里云 OSS 拉 domainPath.json,
#    拉不到就 raise, 整个源起不来; TVBox 里又没法设 BAJIE_HOST 环境变量。
#    现在: OSS -> 失败则用内置域名 -> 再失败才报错。
#
# 7) 接口方法/重试
#    visitorInfo 必须 GET(原版用 fetch 是对的), 但 _safe_request 默认 POST,
#    容易误用; 现在每个接口显式声明方法。另外 _safe_request 在最后一次
#    失败时 raise, 外层又 catch 成空列表, 日志里只剩一句"请求失败";
#    现在统一返回 None 并保留最后一次错误原因。
#
# 8) 【新】分集切换无效 —— 一整部剧只能播第一集
#    原版(以及本文件上一版)按 episodeId 取集: 把 episodeList[i].id 传给
#    movieDetails 的 episodeId 参数。实测服务端**完全忽略** episodeId,
#    传 83466123 / 83466124 / 83466156 都返回第 0 集, 于是"第 1 集"和
#    "第 56 集"播出来是同一个地址。真正生效的只有 episodeIndex(从 0 起):
#    实测 idx=0..5 拿到 6 个不同的 v.qq.com 集页, 解析后也是 6 个不同 m3u8。
#    现在一律用 episodeIndex, episodeId 只作附赠参数。
#
# 9) 【新】没有 requests 时整个脚本静默全空
#    请求头里带了 Accept-Encoding: gzip, requests 会自动解压, 但
#    urllib.urlopen 不会 —— 拿到的是 \x1f\x8b 开头的压缩流, 后面 json
#    解析必然失败, 日志只剩一句"body 非 JSON", 分类/首页/搜索全是空。
#    现在在 _raw_request 里按 Content-Encoding(或魔数)手动 gunzip/解 deflate。
#
# 10)【新】短剧题材筛选是死的
#    screenType 里短剧(M14)挂了个"类型"(虐恋/逆袭/悬疑/神豪/重生...)的子节点,
#    但 screenMovie 的 classify 传任何题材值都返回 0 条(空值才是 6834 条);
#    换 theme/tag/type/label/category 等十余个键名又全被忽略返回全量。
#    结论是服务端没做这个筛选。与其给个点了就空的筛选项, 不如不给 ——
#    现在 NO_FILTER_CATS 里排除掉短剧的 filters。
#
# ------------------------------------------------------------------ 已知限制
#
# A) 短剧(S 前缀)的详情接口不可用
#   搜索结果的 typeId 里有一类是 S 开头(S26/S28/S30...), 走的是短剧库。
#   对它调 movieDetails 一律返回:
#       {"msg":"No bean named 'shortService' available","code":500}
#   已逐一试过 /api/v1/app/short/**、/api/v1/short/**、shortMovieDetails、
#   dramaDetails 等十余条路径, 全部 404; 换端口/换 source 参数也无解。
#   判定为服务端 Bean 缺失, 脚本无解。detailContent 会返回一条说明页,
#   不再给空列表(壳子会显示"没有资源", 看不出原因)。
#   —— 短剧(M14)分类本身完全正常: 6834 条, 详情 82 集, 播放可出真 m3u8。
#
# B) 个别播放源解析不出地址
#   如 playerId=77(高清单线路), movieDetails 只返回一个裸 id
#   "co_ebykzzd6xi4age2s", analysisMovieUrl 把它原样返回。此时 _by_url
#   会明确判失败并记日志, 不再把裸 id 当 URL 丢给壳子。
#
# C) 个别源的多集被 CDN 合并
#   优酷源实测多个集地址 302 到同一个 sviptq 上游。撞车检测会保留原
#   cibn 地址, 但 cibn 本身也是 302, 播放器跟过去仍是同一集。源侧问题。
#
# ------------------------------------------------------------------ 兼容性
#
# Python 2.7 / 3.x 双兼容; requests 可选(没有也能跑, 走标准库)。
# 支持 hipy/CatVod 的 fetch/post 注入; 独立运行时自动用 requests 兜底。

import os
import sys
import json
import time
import base64
import threading
import gzip
import zlib

try:
    from io import BytesIO
except Exception:
    from StringIO import StringIO as BytesIO

try:
    _gzip_decompress = gzip.decompress
except Exception:
    def _gzip_decompress(raw):
        buf = BytesIO(raw)
        out = []
        while True:
            try:
                d = gzip.GzipFile(fileobj=buf)
                out.append(d.read())
            except Exception:
                break
            if not out[-1]:
                break
        return b''.join(out)

try:
    from urllib.parse import quote, unquote, urlencode, urljoin
    from urllib.request import Request, urlopen
    _PY3 = True
except Exception:
    from urllib import quote, unquote, urlencode
    from urlparse import urljoin
    from urllib2 import Request, urlopen
    _PY3 = False

try:
    _UNICODE = unicode
except NameError:
    _UNICODE = str

try:
    _BYTES = bytes if _PY3 else str
except Exception:
    _BYTES = str

try:
    import requests
    _HAS_REQ = True
except Exception:
    requests = None
    _HAS_REQ = False

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

try:
    from concurrent.futures import ThreadPoolExecutor, as_completed
except Exception:
    ThreadPoolExecutor = None

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    try:
        from base import Spider as _BaseSpider
    except Exception:
        try:
            from spider import Spider as _BaseSpider
        except Exception:
            class _BaseSpider(object):
                def getName(self): return ''
                def init(self, extend=''): return None
                def homeContent(self, filter=None): return {}
                def homeVideoContent(self): return {}
                def categoryContent(self, tid, pg, filter=None, extend=None): return {}
                def detailContent(self, ids): return {}
                def searchContent(self, key, quick=False, pg='1'): return {}
                def searchContentPage(self, key, quick=False, pg='1'): return {}
                def playerContent(self, flag, id, vipFlags=None): return {}
                def localProxy(self, param): return [404, 'text/plain', b'']
                def isVideoFormat(self, url): return False
                def manualVideoCheck(self): return False
                def getDependence(self): return []


# ================================================================ 编码统一

def _bstr(raw):
    if not raw:
        return None
    if isinstance(raw, _UNICODE):
        return raw
    try:
        return raw.decode('utf-8', 'replace')
    except Exception:
        try:
            return _UNICODE(str(raw))
        except Exception:
            return None


def _ustr(s):
    if s is None:
        return u''
    if isinstance(s, _UNICODE):
        return s
    if isinstance(s, _BYTES):
        return _bstr(s) or u''
    try:
        return _UNICODE(str(s))
    except Exception:
        return u''


def _u8(s):
    if s is None:
        return b'' if _PY3 else ''
    if isinstance(s, _BYTES) and not isinstance(s, _UNICODE):
        return s
    try:
        return _ustr(s).encode('utf-8')
    except Exception:
        return b'' if _PY3 else ''


def _jdump(d):
    try:
        t = json.dumps(d, ensure_ascii=False)
    except Exception:
        try:
            t = json.dumps(d)
        except Exception:
            return None
    if not _PY3 and isinstance(t, _UNICODE):
        try:
            return t.encode('utf-8')
        except Exception:
            return None
    return t


def _loads(text):
    if not text:
        return None
    if isinstance(text, dict):
        return text
    if not isinstance(text, _UNICODE):
        text = _bstr(text)
        if not text:
            return None
    try:
        return json.loads(text)
    except Exception:
        return None


# ================================================================ 常量

# 域名配置文件(源站长自己维护的 OSS)
_DOMAIN_CFG = 'http://osstexll.oss-rg-china-mainland.aliyuncs.com/domainPath.json'
# 内置兜底域名: OSS 挂了时直接用; 失效时改这一行
_BUILTIN_HOST = 'http://82.156.118.137:88'

_UA_OKHTTP = 'okhttp/4.12.0'
_UA_PLAYER = ('Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) '
              'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 '
              'Mobile/15E148 Safari/604.1')

# typeId 语义(来自 screenType 接口)
TYPE_NAMES = {
    'M15': u'电视剧', 'M16': u'电影', 'M17': u'动漫',
    'M18': u'综艺', 'M14': u'短剧', 'M396': u'动画片',
}


class Spider(_BaseSpider):
    host = ''
    userid = ''
    token = ''

    # 是否给播放结果附带歌词(原版去外部站拉, 已改为关闭; 想恢复改 True)
    ENABLE_LRC = False
    # 详情最多显示几条播放源
    MAX_LINES = 6
    # 是否在播放前探测 302 并跟到最终地址
    RESOLVE_302 = True
    # 这些分类不显示筛选项: 服务端根本没实现, 显示出来点了就是 0 条
    NO_FILTER_CATS = ('M14',)
    # 屏蔽的播放源(按 moviePlayerName 匹配, 忽略大小写):
    # 4K-YKT 会在视频画面里烧录广告水印
    # ("4K接口源码分享QQ交流群:212706934 ... https://fz1.xo.je"),
    # 播放时直接糊在画面上, 没法去掉, 只能整条源不展示。
    BANNED_PLAYERS = ('4k-ykt',)

    def __init__(self, *a, **kw):
        try:
            super(Spider, self).__init__(*a, **kw)
        except Exception:
            pass
        self._cache = {}
        self._cat_tree = None
        self._detail_cache = {}
        # hipy/CatVod 会注入 fetch/post; 独立运行时用标准库兜底
        if not hasattr(self, 'fetch'):
            self.fetch = self._http_get
        if not hasattr(self, 'post'):
            self.post = self._http_post

    # ---------------------------------------------------------- HTTP

    def _headers(self, extra=None):
        h = {
            'User-Agent': _UA_OKHTTP,
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip',
            'Content-Type': 'application/json;charset=UTF-8',
            'Cache-Control': 'no-cache',
            'token': self.token,
            'deviceId': '2d590b9842d064a1',
            'client': 'app',
            'deviceType': 'Android',
        }
        if extra:
            h.update(extra)
        return h

    def _raw_request(self, url, payload=None, method=None, timeout=15, headers=None):
        """返回 (status, bytes)"""
        m = method or ('POST' if payload is not None else 'GET')
        data = _u8(_jdump(payload)) if payload is not None else None
        hdr = headers or self._headers()
        if _HAS_REQ:
            try:
                r = requests.request(m, url, data=data, headers=hdr,
                                     timeout=timeout, verify=False)
                return r.status_code, r.content
            except Exception:
                return 0, None
        try:
            req = Request(url, data=data, headers=hdr)
            if m != 'POST':
                # Py2 的 urllib2 不支持 method 参数, 用 get_method 兜底
                try:
                    req.method = m
                except Exception:
                    pass
            resp = urlopen(req, timeout=timeout)
            code = getattr(resp, 'code', None) or 200
            raw = resp.read()
            if not raw and hasattr(resp, 'readall'):
                try:
                    raw = resp.readall()
                except Exception:
                    pass
            # ★ 必须手动解压: 请求头里带了 Accept-Encoding: gzip,
            #   urllib 不会自动解, 拿到的就是 \x1f\x8b 开头的压缩流,
            #   后面 _loads 一律"body 非 JSON", 整个脚本静默全空。
            #   (requests 分支会自动解压, 所以只有无 requests 时才炸)
            if raw:
                enc = ''
                try:
                    enc = (resp.headers.get('Content-Encoding') or '').lower()
                except Exception:
                    pass
                if enc == 'gzip' or (len(raw) > 2 and raw[:2] == b'\x1f\x8b'):
                    try:
                        raw = gzip.GzipFile(fileobj=BytesIO(raw)).read()
                    except Exception:
                        try:
                            raw = _gzip_decompress(raw)
                        except Exception:
                            pass
                elif enc == 'deflate':
                    try:
                        raw = zlib.decompress(raw)
                    except Exception:
                        try:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                        except Exception:
                            pass
            try:
                resp.close()
            except Exception:
                pass
            return code, raw
        except Exception:
            return 0, None

    def _http_get(self, url, **kw):
        c, b = self._raw_request(url, None, 'GET',
                                 kw.get('timeout', 15), kw.get('headers'))
        return _Resp(c, b)

    def _http_post(self, url, data=None, **kw):
        pl = _loads(data) if isinstance(data, (str, _BYTES)) else data
        c, b = self._raw_request(url, pl if pl is not None else {},
                                 'POST', kw.get('timeout', 15), kw.get('headers'))
        return _Resp(c, b)

    def _api(self, path, payload=None, method=None, timeout=15, retries=2):
        """统一调接口, 返回 dict 或 None
        payload=None 且 method 未指定 -> GET; 否则 POST
        """
        url = self.host.rstrip('/') + path
        last_err = ''
        for i in range(max(1, retries)):
            try:
                if method == 'GET' or (method is None and payload is None):
                    st, raw = self._raw_request(url, None, 'GET', timeout)
                else:
                    st, raw = self._raw_request(url, payload or {}, 'POST', timeout)
                if st != 200:
                    last_err = u'HTTP %s' % st
                    if i + 1 < retries:
                        time.sleep(0.4)
                    continue
                d = _loads(_bstr(raw))
                if not isinstance(d, dict):
                    last_err = u'body 非 JSON'
                    if i + 1 < retries:
                        time.sleep(0.4)
                    continue
                code = d.get('code', 200)
                if code in (200, 0) or str(code) in ('200', '0'):
                    return d
                last_err = u'code=%s msg=%s' % (code, d.get('msg') or d.get('message'))
                # 业务错(比如 token 过期)重试也没用, 直接返回
                return None
            except Exception as e:
                last_err = u'%s: %s' % (type(e).__name__, _ustr(e))
                if i + 1 < retries and _PY3 is not None:
                    time.sleep(0.4)
        if last_err:
            self._log(u'[api] %s 失败: %s' % (path, last_err))
        return None

    @staticmethod
    def _log(msg):
        try:
            print(u'[八戒] %s' % _ustr(msg))
        except Exception:
            pass

    # ---------------------------------------------------------- 缓存

    def _cache_get(self, key, ttl=180):
        v = self._cache.get(key)
        if v and time.time() - v[0] < ttl:
            return v[1]
        return None

    def _cache_put(self, key, val):
        if len(self._cache) > 200:
            self._cache.clear()
        self._cache[key] = (time.time(), val)

    # ---------------------------------------------------------- init

    def init(self, extend=""):
        self._resolve_host()
        self._login_visitor()
        return None

    def _resolve_host(self):
        """域名: 环境变量 > OSS 配置 > 内置兜底"""
        env = _ustr(os.environ.get('BAJIE_HOST', '')).strip()
        if env:
            self.host = env.rstrip('/')
            self._log(u'host 来自环境变量: %s' % self.host)
            return
        try:
            st, raw = self._raw_request(_DOMAIN_CFG, None, 'GET', 10,
                                        {'User-Agent': _UA_OKHTTP})
            if st == 200:
                j = _loads(_bstr(raw)) or {}
                urls = j.get('url') if isinstance(j, dict) else None
                if urls:
                    self.host = _ustr(urls[0]).rstrip('/')
                    self._log(u'host 来自远程配置: %s' % self.host)
                    return
                # OSS 返回 {"status":403,...} 之类
                self._log(u'domainPath.json 结构异常: %s' % _ustr(j)[:120])
            else:
                self._log(u'domainPath.json HTTP %s' % st)
        except Exception as e:
            self._log(u'拉域名配置异常: %s' % e)
        # 兜底: 内置域名
        self.host = _BUILTIN_HOST.rstrip('/')
        self._log(u'改用内置域名: %s' % self.host)

    def _login_visitor(self):
        """拿游客 token; 有些接口不带 token 也能用, 所以失败不 fatal"""
        d = self._api('/api/v1/app/user/visitorInfo', None, 'GET', timeout=12, retries=2)
        data = (d or {}).get('data') or {}
        self.userid = data.get('id') or self.userid
        self.token = data.get('token') or self.token
        if self.token:
            self._log(u'游客登录成功 userId=%s' % self.userid)
        else:
            self._log(u'游客登录失败, 继续无 token 请求')

    # ---------------------------------------------------------- 分类树

    def _load_cat_tree(self):
        """拉 screenType, 缓存 10 分钟"""
        if self._cat_tree is not None:
            return self._cat_tree
        d = self._api('/api/v1/app/screen/screenType', {}, 'POST', timeout=12, retries=2)
        tree = []
        if d:
            tree = d.get('data') or []
        if not tree:
            # 拉不到时用硬编码的 6 个顶层, 至少能进
            tree = [{'id': k, 'name': v, 'children': []} for k, v in
                    (('M16', u'电影'), ('M15', u'电视剧'), ('M17', u'动漫'),
                     ('M18', u'综艺'), ('M14', u'短剧'), ('M396', u'动画片'))]
        self._cat_tree = tree
        return tree

    def _build_cats(self):
        """顶层做 tab; 二三级展开成 filters"""
        tree = self._load_cat_tree()
        classes = []
        filters = {}
        for node in tree:
            tid = _ustr(node.get('id'))
            name = _ustr(node.get('name'))
            if not tid:
                continue
            classes.append({'type_id': tid, 'type_name': name})
            # ★ 短剧(M14) 的题材筛选服务端没实现: classify 传任何值都
            #   返回 0 条(逆袭/虐恋/甜宠/重生 全试过), 传空才是 6834 条;
            #   换 theme/tag/type/label 等十余个键名又全被忽略返回全量。
            #   与其给个点了就空的筛选项, 不如不显示。
            if tid in self.NO_FILTER_CATS:
                continue
            fdefs = []
            for dim in (node.get('children') or []):
                key = self._dim_key(dim)
                if not key:
                    continue
                # ★ 接口的 condition.region/classify/year 要的是**中文名**,
                #   不是子项 id —— 实测 region=M79 返回 0 条, region=内地
                #   返回 4888 条。所以下拉的 value 直接用 name。
                opts = [{'n': u'全部', 'v': ''}]
                for c in (dim.get('children') or []):
                    cn = _ustr(c.get('name'))
                    if cn:
                        opts.append({'n': cn, 'v': cn})
                if len(opts) > 1:
                    fdefs.append({'key': key, 'name': _ustr(dim.get('name')),
                                  'value': opts})
            if fdefs:
                filters[tid] = fdefs
        return classes, filters

    @staticmethod
    def _dim_key(dim):
        """把分类树的维度名映射成 extend 里的键名"""
        nm = _ustr(dim.get('name'))
        if u'地区' in nm:
            return 'area'
        if u'类型' in nm or u'分类' in nm:
            return 'genre'
        if u'年份' in nm or u'年代' in nm:
            return 'year'
        # 未知维度用它的 id 当 key, 不至于丢
        return _ustr(dim.get('id'))

    # ---------------------------------------------------------- TVBox 接口

    def getName(self):
        return u'八戒影视'

    def getDependence(self):
        return []

    def homeContent(self, filter=None):
        c = self._cache_get('home', 600)
        if c:
            return c
        classes, filters = self._build_cats()
        out = {'class': classes, 'filters': filters}
        self._cache_put('home', out)
        return out

    def homeVideoContent(self):
        c = self._cache_get('homevideo', 300)
        if c:
            return c
        d = self._api('/api/v1/app/recommend/recommendList', {}, 'POST', 12)
        groups = (d or {}).get('data') or []
        items = []
        seen = set()

        def one(g):
            gid = g.get('id')
            if not gid:
                return []
            r = self._api('/api/v1/app/recommend/recommendSubList',
                          {'condition': gid, 'pageNum': 1, 'pageSize': 8}, 'POST', 12, 1)
            return ((r or {}).get('data') or {}).get('records') or []

        if ThreadPoolExecutor is not None and len(groups) > 1:
            try:
                with ThreadPoolExecutor(max_workers=4) as ex:
                    for recs in ex.map(one, groups[:6]):
                        for rec in recs:
                            it = self._to_item(rec)
                            if it['vod_name'] and it['vod_name'] not in seen:
                                seen.add(it['vod_name'])
                                items.append(it)
            except Exception:
                pass
        else:
            for g in groups[:6]:
                for rec in one(g):
                    it = self._to_item(rec)
                    if it['vod_name'] and it['vod_name'] not in seen:
                        seen.add(it['vod_name'])
                        items.append(it)

        out = {'list': items[:60]}
        self._cache_put('homevideo', out)
        return out

    def _to_item(self, rec):
        """条目 -> TVBox 列表项; vod_id 带上 typeId 供详情/播放透传"""
        vid = _ustr(rec.get('id'))
        tid = _ustr(rec.get('typeId'))
        return {
            'vod_id': (tid + '|' + vid) if tid else vid,
            'vod_name': _ustr(rec.get('name')),
            'vod_pic': _ustr(rec.get('cover')),
            'vod_remarks': _ustr(rec.get('desc') or rec.get('area')),
            'vod_year': _ustr(rec.get('year')),
            'vod_type': _ustr(rec.get('type')),
        }

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        ext = self._parse_extend(extend)
        try:
            p = int(pg or 1)
        except Exception:
            p = 1
        ck = 'cat_%s_%s_%s' % (tid, p, _ustr(sorted(ext.items())))
        c = self._cache_get(ck, 120)
        if c:
            return c

        payload = {
            'condition': {
                'classify': _ustr(ext.get('genre') or ''),
                'region': _ustr(ext.get('area') or ''),
                'sreecnTypeEnum': 'NEWEST',
                'typeId': _ustr(tid),
                'year': _ustr(ext.get('year') or ''),
            },
            'pageNum': p,
            'pageSize': 40,
        }
        d = self._api('/api/v1/app/screen/screenMovie', payload, 'POST', 15)
        data = (d or {}).get('data') or {}
        recs = data.get('records') or []
        items = [self._to_item(r) for r in recs]
        total = data.get('total')
        try:
            total = int(total)
        except Exception:
            total = 0
        # 服务端不给 pages 时自己算; 有些分类(如 动画片)total 就只有 1
        srv_pages = data.get('pages')
        try:
            srv_pages = int(srv_pages)
        except Exception:
            srv_pages = 0
        pages = srv_pages or (int((total + 39) / 40) if total else p)
        if pages < p:
            pages = p
        out = {'list': items, 'page': p, 'pagecount': pages,
               'limit': 40, 'total': total or len(items)}
        self._cache_put(ck, out)
        return out

    @staticmethod
    def _parse_extend(extend):
        if isinstance(extend, (str, _BYTES)) and extend.strip().startswith('{'):
            d = _loads(extend)
            if isinstance(d, dict):
                return d
            return {}
        if isinstance(extend, dict):
            return dict(extend)
        return {}

    def searchContent(self, key, quick=False, pg='1'):
        kw = _ustr(key or '').strip()
        if not kw:
            return {'list': [], 'page': 1, 'pagecount': 1}
        try:
            p = int(pg or 1)
        except Exception:
            p = 1
        ck = 'search_%s_%s' % (kw, p)
        c = self._cache_get(ck, 120)
        if c:
            return c
        d = self._api('/api/v1/app/search/searchMovie',
                      {'condition': {'value': kw}, 'pageNum': p, 'pageSize': 40},
                      'POST', 15)
        data = (d or {}).get('data') or {}
        recs = data.get('records') or []
        out = {'list': [self._to_item(r) for r in recs], 'page': p, 'pagecount': 1}
        self._cache_put(ck, out)
        return out

    def searchContentPage(self, key, quick=False, pg='1'):
        return self.searchContent(key, quick, pg)

    # ---------------------------------------------------------- 详情

    def _split_vid(self, ids):
        vid = ''
        if isinstance(ids, (list, tuple)):
            vid = _ustr(ids[0]) if ids else u''
        else:
            vid = _ustr(ids or u'')
        vid = vid.strip()
        if u'|' in vid:
            tid, real = vid.split(u'|', 1)
            return tid, real
        # 老格式(只有数字 id): 类型未知, 用电影兜底
        return u'M16', vid

    def detailContent(self, ids):
        type_id, video_id = self._split_vid(ids)
        if not video_id:
            return {'list': []}
        vod_key = type_id + '|' + video_id
        c = self._cache_get('dt_' + vod_key, 600)
        if c:
            return c

        d = self._api('/api/v1/app/play/movieDetails',
                      {'id': video_id, 'source': 0, 'typeId': type_id,
                       'userId': self.userid}, 'POST', 15)
        data = (d or {}).get('data') or {}
        if not data:
            # 短剧(S 前缀)服务端压根没部署: movieDetails 返回
            # {"msg":"No bean named 'shortService' available","code":500}
            # 搜过 /short/** 系列十几条路径全是 404, 只能明确告知而不是空白
            return self._short_unavailable(vod_key)

        # 简介单独一个接口, 失败不影响主流程
        desc = {}
        try:
            dd = self._api('/api/v1/app/play/movieDesc',
                           {'id': video_id, 'typeId': type_id}, 'POST', 12, 1)
            desc = (dd or {}).get('data') or {}
        except Exception:
            pass

        vod = {
            'vod_id': vod_key,
            'vod_name': _ustr(desc.get('name') or data.get('name')),
            'vod_pic': _ustr(desc.get('cover') or data.get('cover') or ''),
            'vod_content': _ustr(desc.get('introduce') or data.get('introduce') or ''),
            'vod_year': _ustr(desc.get('year') or data.get('year') or ''),
            'vod_area': _ustr(desc.get('area') or data.get('area') or ''),
            'vod_remarks': '',
            'vod_actor': _ustr(desc.get('actor') or ''),
            'vod_director': _ustr(desc.get('director') or ''),
        }
        score = desc.get('score') or data.get('score')
        if score:
            vod['vod_score'] = _ustr(score)

        froms, urls = self._build_playlist(video_id, type_id, data)
        if froms and urls:
            vod['vod_play_from'] = u'$$$'.join(froms)
            vod['vod_play_url'] = u'$$$'.join(urls)
        else:
            # 一条都拿不到: 给一条虚线路, 至少能点进去让播放阶段再试
            vod['vod_play_from'] = u'默认'
            vod['vod_play_url'] = u'正片$' + self._pack(video_id, type_id, '', 0, '')

        out = {'list': [vod]}
        self._cache_put('dt_' + vod_key, out)
        return out

    def _short_unavailable(self, vod_key):
        """短剧详情兜底: S 前缀走 shortService, 而该服务在现网未部署
        不返回空列表(壳子会显示「没有资源」), 给说明文字而不是空白页
        """
        vid = vod_key.split('|')[-1]
        content = (
            u'该条目属于短剧库(S 系列), 但八戒服务端的短剧服务 shortService '
            u'未部署, 详情接口直接返回 No bean named shortService available。'
            u'\n\n'
            u'已逐一试过 /api/v1/app/short/**、/api/v1/short/** 等十余条路径, '
            u'全部 404, 属于服务端缺件, 不是脚本问题。'
            u'\n\n'
            u'可改用「短剧(M14)」分类观看, 那条链路的详情与播放都正常。')
        vod = {
            'vod_id': vod_key,
            'vod_name': u'短剧 #' + vid,
            'vod_pic': '',
            'vod_content': content,
            'vod_year': '',
            'vod_area': '',
            'vod_remarks': u'短剧服务未部署',
            'vod_actor': '',
            'vod_director': '',
        }
        return {'list': [vod]}

    @staticmethod
    def _pack(video_id, type_id, player_id, ep_index, ep_id, kind='virtual'):
        """播放参数打包: 全部用 | 分隔, 避免和 URL 里的字符冲突
        kind=virtual -> 按集号取; kind=episode -> 按 episodeId 取
        """
        return u'%s@%s@%s@%s@%s@%s' % (
            _ustr(video_id), _ustr(type_id), _ustr(player_id),
            _ustr(ep_index), _ustr(ep_id), kind)

    @staticmethod
    def _unpack(s):
        p = _ustr(s).split(u'@')
        while len(p) < 6:
            p.append(u'')
        return p[0], p[1], p[2], p[3], p[4], p[5]

    def _build_playlist(self, video_id, type_id, data):
        """把详情里的 episodeList / moviePlayerList 组装成线路
        同一部片可能有多个播放源(腾讯/优酷/4K-YKT...), 每个源一条线路
        """
        eps = data.get('episodeList') or []
        players = data.get('moviePlayerList') or []
        cur_pid = data.get('playerId')

        froms = []
        urls = []

        # 1) 有真实分集: 每个播放源都能按 episodeIndex 播
        #    ★ 实测 epId 传上去服务端直接忽略(传 83466123/83466124/83466156
        #      都返回第 0 集), 只有 episodeIndex(从 0 起) 才真正生效。
        #      所以 kind 一律用 virtual, 靠集号定位。
        if eps:
            for pl in players[:self.MAX_LINES]:
                pid = pl.get('id')
                pname = _ustr(pl.get('moviePlayerName') or u'线路')
                if self._banned(pname):
                    continue
                total = pl.get('episodeTotal') or len(eps)
                try:
                    total = int(total)
                except Exception:
                    total = len(eps)
                pairs = []
                for idx, ep in enumerate(eps):
                    ep_name = _ustr(ep.get('episode')) or _ustr(idx + 1)
                    pairs.append((ep_name, self._pack(
                        video_id, type_id, pid, idx, u'', 'virtual')))
                # 播放源声明比 episodeList 更多集时补齐(多数是空集, 但聊胜于无)
                for k in range(len(eps), min(total, 500)):
                    pairs.append((_ustr(k + 1), self._pack(
                        video_id, type_id, pid, k, u'', 'virtual')))
                if pairs:
                    froms.append(self._uniq(pname, froms))
                    urls.append(u'#'.join([u'%s$%s' % (n, u) for n, u in pairs]))
            return froms, urls

        # 2) 没有分集列表: 按每个源的 episodeTotal 生成集号
        for pl in players[:self.MAX_LINES]:
            pid = pl.get('id')
            pname = _ustr(pl.get('moviePlayerName') or u'线路')
            if self._banned(pname):
                continue
            total = pl.get('episodeTotal') or 1
            try:
                total = int(total)
            except Exception:
                total = 1
            if total <= 0:
                continue
            pairs = [(_ustr(k + 1), self._pack(video_id, type_id, pid, k, u'', 'virtual'))
                     for k in range(min(total, 500))]
            froms.append(self._uniq(pname, froms))
            urls.append(u'#'.join([u'%s$%s' % (n, u) for n, u in pairs]))

        # 3) 连播放源都没有: 单集兜底
        if not froms:
            froms.append(u'默认')
            urls.append(u'正片$' + self._pack(video_id, type_id, cur_pid or 0, 0, u'', 'virtual'))
        return froms, urls

    @staticmethod
    def _banned(pname):
        """播放源名命中黑名单 -> 整条剔除(如 4K-YKT 画面带广告水印)"""
        low = _ustr(pname).strip().lower()
        for w in Spider.BANNED_PLAYERS:
            if w in low:
                return True
        return False

    @staticmethod
    def _uniq(name, existing):
        n = name
        i = 2
        while n in existing:
            n = u'%s(%d)' % (name, i)
            i += 1
        return n

    # ---------------------------------------------------------- 播放

    def playerContent(self, flag, ids, vipFlags=None):
        raw = ids
        if isinstance(raw, (list, tuple)):
            raw = raw[0] if raw else ''
        raw = _ustr(raw).strip()
        if not raw:
            return self._fail()

        if u'@' in raw:
            video_id, type_id, pid, ep_index, ep_id, kind = self._unpack(raw)
        else:
            # 兼容老的 "id@playerId@xxx@virtual" 格式或裸 URL
            if raw.startswith(u'http'):
                return self._by_url(raw)
            video_id, type_id, pid, ep_index, ep_id, kind = raw, u'M16', u'', u'0', u'', u'virtual'

        if not video_id:
            return self._fail()
        if not type_id:
            type_id = u'M16'

        # 1) 用播放参数再问一次 movieDetails, 拿到该集的 url
        #    ★ 只有 episodeIndex(从 0 起) 生效; episodeId 服务端不认,
        #      传了也返回第 0 集, 所以这里两个都传, 但以 index 为准
        payload = {
            'id': video_id,
            'playerId': int(pid) if _ustr(pid).isdigit() else pid,
            'source': 0,
            'typeId': type_id,
            'userId': self.userid,
            'episodeIndex': str(max(0, int(ep_index) if _ustr(ep_index).isdigit() else 0)),
        }
        if ep_id:
            payload['episodeId'] = int(ep_id) if _ustr(ep_id).isdigit() else ep_id

        d = self._api('/api/v1/app/play/movieDetails', payload, 'POST', 15)
        data = (d or {}).get('data') or {}
        page_url = _ustr(data.get('url') or '')
        got_pid = data.get('playerId') or pid

        if not page_url:
            self._log(u'播放: movieDetails 未返回 url')
            return self._fail()

        # 2) 页面地址 -> 真实直链
        q = ('/api/v1/app/play/analysisMovieUrl?playerUrl=' +
             _ustr(quote(_u8(page_url), safe='')) +
             '&playerId=' + _ustr(got_pid))
        a = self._api(q, None, 'GET', 20)
        real = _ustr((a or {}).get('data') or '')
        if not real:
            self._log(u'播放: analysis 未返回地址, 页面地址=%s' % page_url[:80])
            # 解析失败但页面地址本身可能是可播的 m3u8(少数源直接给直链)
            return self._by_url(page_url)

        return self._by_url(real)

    @staticmethod
    def _fail():
        return {'parse': 1, 'jx': 0, 'playUrl': '', 'url': '', 'header': {}}

    def _by_url(self, url):
        """按地址真实形态判定 parse, 必要时先把 302 跟到底"""
        u = _ustr(url).strip()
        if not u:
            return self._fail()
        if u.startswith(u'//'):
            u = u'https:' + u

        # 裸 id(如 co_ebykzzd6xi4age2s): 说明这个源解析不出来, 地址不是 URL。
        # 硬交给壳子解析器只会白转一圈, 直接判失败更好排查。
        if not (u.startswith(u'http://') or u.startswith(u'https://')):
            self._log(u'播放: 源未给出可用地址(裸 id): %s' % u[:60])
            return self._fail()

        low = u.lower().split(u'?')[0]
        is_media = low.endswith(u'.m3u8') or low.endswith(u'.m3u') or \
            low.endswith(u'.mp4') or low.endswith(u'.flv') or low.endswith(u'.ts')

        if is_media and self.RESOLVE_302:
            final = self._follow_302(u)
            if final:
                u = final

        low = u.lower().split(u'?')[0]
        is_media = low.endswith(u'.m3u8') or low.endswith(u'.m3u') or \
            low.endswith(u'.mp4') or low.endswith(u'.flv') or low.endswith(u'.ts')

        hdr = {'User-Agent': _UA_PLAYER, 'Referer': self.host + '/' if self.host else ''}
        if is_media:
            return {
                'parse': 0, 'jx': 0, 'playUrl': '', 'url': u,
                'format': 'application/x-mpegURL' if (u'.m3u8' in low or u'.m3u' in low) else 'video/mp4',
                'header': hdr,
            }
        # 网页地址: 交给壳子的解析器
        return {'parse': 1, 'jx': 0, 'playUrl': u, 'url': u, 'header': hdr}

    def _follow_302(self, url, max_hop=3):
        """跟 302 拿最终地址; 拿到非重定向响应就返回它的地址
        实测: 有的源(cibn-edge-5g)302 到真 CDN, 有的(log.alibabacloud)
        直接 200。播放器不一定跟随 302, 所以这里先跟一次。

        ★ 但有的源 302 是"糊"的: 不同的集地址会被转到同一个上游
          (实测优酷源 2 集 -> 同一个 sviptq 地址)。这种跟随反而把
          多集合并成一集, 所以对 302 目标做一次"同源撞车"检测 —
          见 _302_seen。
        """
        cur = url
        for _ in range(max_hop):
            try:
                st, loc = self._probe(cur)
                if st in (301, 302, 303, 307, 308) and loc:
                    loc = _ustr(loc)
                    if loc.startswith(u'//'):
                        loc = u'https:' + loc
                    elif loc.startswith(u'/'):
                        loc = urljoin(cur, loc)
                    # 跳到广告页就不跟了, 用原地址
                    if self._is_ad(loc):
                        self._log(u'302 指向广告页, 保留原地址: %s' % loc[:60])
                        return cur
                    # 原始地址不同却转到同一个目标 -> 该源 302 不可信
                    if self._302_collides(url, loc):
                        self._log(u'302 目标与其它集撞车, 保留原地址: %s' % loc[:60])
                        return url
                    cur = loc
                    continue
                if st == 200:
                    return cur
                return cur
            except Exception:
                return cur
        return cur

    # 302 撞车检测: 键是"原始集地址的指纹", 值是 302 目标
    _302_map = {}
    _302_lock = None

    @classmethod
    def _302_collides(cls, src, dst):
        """同一个 302 目标已经被另一个不同的原始地址用过 -> 撞车
        只记前 200 条, 防止长时间运行内存膨胀
        """
        try:
            if cls._302_lock is None:
                import threading
                cls._302_lock = threading.Lock()
            key = dst.split(u'?')[0]
            with cls._302_lock:
                old = cls._302_map.get(key)
                if old is None:
                    if len(cls._302_map) < 200:
                        cls._302_map[key] = src.split(u'?')[0]
                    return False
                return old != src.split(u'?')[0]
        except Exception:
            return False

    @staticmethod
    def _is_ad(u):
        low = u.lower()
        for w in ('aibox.eu.org', 'aibox.', '/110', 'tg.', 't.me/'):
            if w in low:
                return True
        return False

    def _probe(self, url):
        """只取响应头, 返回 (status, location)"""
        hdr = {'User-Agent': _UA_PLAYER, 'Range': 'bytes=0-1'}
        if _HAS_REQ:
            try:
                r = requests.get(url, headers=hdr, timeout=10, verify=False,
                                 allow_redirects=False, stream=True)
                loc = r.headers.get('Location') or r.headers.get('location') or ''
                try:
                    r.close()
                except Exception:
                    pass
                return r.status_code, loc
            except Exception:
                return 0, ''
        try:
            class _NoRedirect(object):
                pass
            req = Request(url, headers=hdr)
            try:
                opener = urlopen(req, timeout=10)
                code = getattr(opener, 'code', 200)
                try:
                    opener.close()
                except Exception:
                    pass
                return code, ''
            except Exception as e:
                # urllib 默认会跟 302; 抛 HTTPError 时取 code/url
                code = getattr(e, 'code', 0)
                loc = ''
                try:
                    loc = e.headers.get('Location') or ''
                except Exception:
                    pass
                return code, loc
        except Exception:
            return 0, ''

    # ---------------------------------------------------------- 其它接口

    def isVideoFormat(self, url):
        u = _ustr(url).lower()
        return (u'.m3u8' in u) or (u'.mp4' in u) or (u'.flv' in u)

    def manualVideoCheck(self):
        return True

    def localProxy(self, param):
        return [404, 'text/plain', b'Not Found', {}]

    def action(self, action):
        return {}

    def destroy(self):
        self._cache.clear()
        self._cat_tree = None


class _Resp(object):
    """模拟 requests.Response 的极简壳, 给框架注入的 fetch/post 用"""
    def __init__(self, status, content):
        self.status_code = status or 0
        self.content = content or b''
        self.text = _bstr(content) or u''

    def json(self):
        return _loads(self.text) or {}


# ================================================================ 模块级转发

_sp = None


def _ins():
    global _sp
    if _sp is None:
        _sp = Spider()
    return _sp


def getName():
    return _ins().getName()


def init(extend=""):
    return _ins().init(extend)


def homeContent(filter=None):
    return _ins().homeContent(filter)


def homeVideoContent():
    return _ins().homeVideoContent()


def categoryContent(tid, pg=1, filter=None, extend=None):
    return _ins().categoryContent(tid, pg, filter, extend)


def detailContent(ids):
    return _ins().detailContent(ids)


def searchContent(key, quick=False, pg='1'):
    return _ins().searchContent(key, quick, pg)


def searchContentPage(key, quick=False, pg='1'):
    return _ins().searchContentPage(key, quick, pg)


def playerContent(flag, ids, vipFlags=None):
    return _ins().playerContent(flag, ids, vipFlags)


def isVideoFormat(url):
    return _ins().isVideoFormat(url)


def manualVideoCheck():
    return _ins().manualVideoCheck()


def localProxy(param):
    return _ins().localProxy(param)


def getDependence():
    return _ins().getDependence()


def action(action):
    return _ins().action(action)


def destroy():
    return _ins().destroy()


if __name__ == '__main__':
    # Py2 下 stdout 不是 utf-8, 先把裸中文串都换成编码安全的写法
    def _p(s):
        try:
            print(s)
        except Exception:
            try:
                print(_u8(s))
            except Exception:
                pass
    sp = Spider()
    _p('=' * 60)
    _p(u'八戒影视 - 自测')
    _p('=' * 60)
    sp.init()
    _p(u'host = ' + _ustr(sp.host))
    _p(u'token = ' + _ustr((sp.token or u'')[:24]))
    h = sp.homeContent(False)
    _p(u'分类 %d 个: %s' % (len(h.get('class') or []),
                          [(c['type_id'], c['type_name']) for c in (h.get('class') or [])]))
    _p(u'筛选维度: %s' % _ustr({k: [d['name'] for d in v]
                               for k, v in (h.get('filters') or {}).items()}))
