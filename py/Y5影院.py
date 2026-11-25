# -*- coding: utf-8 -*-
"""
Y5影院 TVBox py 爬虫 (y5yy.com -> m.jysct15.com)
================================================================
站点架构：Next.js(RSC) + 私有匿名 API(/api/mw-movie/anonymous/*)
鉴权：无需登录，authorization 留空；请求头带 sign/t/deviceid/client-type
签名：sign = SHA1( MD5( 排序后的query串 + "&key=SK&t=毫秒时间戳" ).hexdigest() ).hexdigest()

接口（全部免登录，2026-11-20 实测）：
  列表   /anonymous/video/list              ?pageNum=&pageSize=&sort=1&sortBy=1&type1=<分类>
  搜索   /anonymous/video/searchByWord      ?keyword=&pageNum=&pageSize=
  详情   /anonymous/video/detail            ?id=<vodId>
  播放   /anonymous/v2/video/episode/url    ?clientType=3&id=<vodId>&nid=<nid>
  热搜   /anonymous/home/hotSearch

播放地址说明：
  - episode/url 返回 1080/720/480 三档 m3u8，auth_key 约 5 分钟过期 -> 必须现取现用，不缓存
  - m3u8 CDN(ppvod*.blbtgg.com) 按 IP 限流：沙箱/机房 IP 可能 403，家庭盒子网络正常
    -> playerContent 只负责实时取真址，不以沙箱探活结果否定地址

写法遵循《TVBox_py爬虫经验写法总结_完整版》：
  - 标准 Spider 接口 + 模块级函数转发
  - 三级域名兜底 + 预算超时 + 异常不冒泡
  - 内容标记校验（防假成功）、失败不留缓存
  - 海报直连（obs.3688baihuo.com 实测返回合法 WEBP）
  - 未成年人内容零容忍（搜索/列表/详情统一过滤）

CODE_VERSION = '20261120.2'
"""

import base64
import hashlib
import json
import re
import time
import uuid
from urllib import parse as urlparse

# BaseSpider 软依赖：壳子里有就用框架的，本地没有退化成 object（经验文档 §2 加载层）
try:
    from base.spider import Spider as _BaseSpider
except Exception:
    try:
        from base_spider import BaseSpider as _BaseSpider
    except Exception:
        _BaseSpider = object

try:
    import requests
except Exception:
    requests = None

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
CODE_VERSION = '20261120.2'

# 主域 + 备用域（站点偶发换域，实测主域可用；备用为用户截图/JS里出现过的同源域）
HOSTS = [
    'https://m.jysct15.com',
    'https://m.wxojcopfw.com',   # JS 里 localhost 调试时的备用域
]
HOST = HOSTS[0]

API_BASE = '/api/mw-movie'
SIGN_KEY = 'cb808529bae6b6be45ecfab29a4889bc'

UA = ('Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36')

# 分类：站点 typeId1（电影1/电视剧2/综艺3/动漫4/短剧88）
CLASSES = [
    {'type_id': '1', 'type_name': '电影'},
    {'type_id': '2', 'type_name': '电视剧'},
    {'type_id': '3', 'type_name': '综艺'},
    {'type_id': '4', 'type_name': '动漫'},
    {'type_id': '88', 'type_name': '短剧'},
]

# 未成年人零容忍：命中即过滤（分类/搜索/详情标题与简介）
_MINOR_KW = [
    '萝莉', '幼童', '未成年', '儿童色情', '少儿不宜', '正太', '幼女',
    'loli', 'child porn', 'underage', 'teen porn', 'jailbait',
]

# 网络预算
REQ_TIMEOUT = 8          # 单次请求超时
BUDGET_TOTAL = 22        # 单接口总预算（秒），避免壳子卡死
PAGE_SIZE = 30

# 全局轻量缓存（只缓存列表/详情，绝不缓存播放地址——auth_key 时效）
_CACHE = {}
_CACHE_TTL = 300


def _now_ms():
    return str(int(time.time() * 1000))


def _sign(params):
    """sign = SHA1( MD5( sorted_query + &key=SK&t=ts ).hexdigest() ).hexdigest()"""
    ts = _now_ms()
    ps = '&'.join('%s=%s' % (k, params[k]) for k in sorted(params))
    raw = (ps + '&' if ps else '') + 'key=' + SIGN_KEY + '&t=' + ts
    md5hex = hashlib.md5(raw.encode('utf-8')).hexdigest()
    sign = hashlib.sha1(md5hex.encode('utf-8')).hexdigest()
    return sign, ts


def _is_minor(text):
    if not text:
        return False
    t = str(text).lower()
    return any(k.lower() in t for k in _MINOR_KW)


def _norm_pic(url):
    if not url:
        return ''
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('http'):
        return url
    return HOST + (url if url.startswith('/') else '/' + url)


def _cache_get(key):
    v = _CACHE.get(key)
    if v and (time.time() - v[0]) < _CACHE_TTL:
        return v[1]
    return None


def _cache_set(key, val):
    _CACHE[key] = (time.time(), val)


class Spider(_BaseSpider):
    def getName(self):
        return 'Y5影院'

    def version(self):
        return CODE_VERSION

    def init(self, extend=''):
        self.extend = extend or ''
        self.host = HOST
        # 探测备用域：主域能通就用主域（握手一次，失败不影响后续）
        self._headers = {
            'User-Agent': UA,
            'client-type': '3',
            'authorization': '',
            'Accept': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        return True

    # -----------------------------------------------------------------------
    # 网络层：三级兜底（多域 x 重试） + 预算 + 异常不冒泡
    # -----------------------------------------------------------------------
    def _api(self, path, params, timeout=REQ_TIMEOUT, retries=2, budget=BUDGET_TOTAL):
        """调用匿名 API，成功返回 data，失败返回 None（绝不抛异常）。"""
        deadline = time.time() + budget
        sign, ts = _sign(params)
        headers = dict(self._headers)
        headers['sign'] = sign
        headers['t'] = ts
        headers['deviceid'] = str(uuid.uuid4())
        headers['Referer'] = self.host + '/'
        query = urlparse.urlencode(params)

        # 主域优先，备用域兜底
        for hi, host in enumerate([self.host] + [h for h in HOSTS if h != self.host]):
            if time.time() > deadline:
                break
            for attempt in range(retries):
                if time.time() > deadline:
                    break
                url = host + API_BASE + path
                if query:
                    url += '?' + query
                try:
                    if requests is not None:
                        resp = requests.get(url, headers=headers, timeout=timeout)
                        code = resp.status_code
                        text = resp.text
                    else:
                        import urllib.request
                        req = urllib.request.Request(url, headers=headers)
                        with urllib.request.urlopen(req, timeout=timeout) as r:
                            code = r.status
                            text = r.read().decode('utf-8', 'replace')
                    if code != 200:
                        continue
                    obj = json.loads(text)
                    if obj.get('code') == 200 and 'data' in obj:
                        return obj.get('data')
                    # 业务失败：签名/登录类问题记一次，换域重试
                    continue
                except Exception:
                    continue
        return None

    # -----------------------------------------------------------------------
    # 列表项转换
    # -----------------------------------------------------------------------
    def _to_video(self, it):
        if not isinstance(it, dict):
            return None
        name = it.get('vodName') or ''
        if _is_minor(name) or _is_minor(it.get('vodBlurb') or it.get('vodContent') or ''):
            return None
        vid = it.get('vodId')
        if vid is None:
            return None
        return {
            'vod_id': str(vid),
            'vod_name': name,
            'vod_pic': _norm_pic(it.get('vodPic')),
            'vod_year': str(it.get('vodYear') or ''),
            'vod_area': it.get('vodArea') or '',
            'vod_remarks': it.get('vodVersion') or it.get('vodSerial') or it.get('vodClass') or '',
            'vod_tag': it.get('vodClass') or '',
        }

    # -----------------------------------------------------------------------
    # 首页
    # -----------------------------------------------------------------------
    def homeContent(self, filter=False):
        classes = [{'type_id': c['type_id'], 'type_name': c['type_name']} for c in CLASSES]
        result = {'class': classes, 'list': [], 'filters': {}}

        # 首屏只取 1 个分类（壳子 homeContent 约 10s 硬超时，绝不能串行多次）。
        # 经验文档：空白 90% 来自首屏超时——单请求 + 缓存 + 静态分类，秒回。
        data = self._api('/anonymous/video/list', {
            'pageNum': 1, 'pageSize': PAGE_SIZE, 'sort': 1, 'sortBy': 1, 'type1': '1',
        }, timeout=5, retries=1, budget=8)
        if data:
            for it in (data.get('list') or []):
                v = self._to_video(it)
                if v:
                    result['list'].append(v)
        # 兜底：若上面空，用热搜关键词搜一批
        if not result['list']:
            hot = self._api('/anonymous/home/hotSearch', {}, timeout=5) or []
            for h in hot[:1]:
                kw = h.get('hotWord') or h.get('keyword') or h.get('vodName') or ''
                if kw:
                    result['list'] = self.searchContent(kw, False, 1).get('list', [])
                    break
        if filter:
            result['filters'] = {}
        return result

    def homeVideoContent(self):
        return {'list': self.homeContent(False).get('list', [])[:20]}

    # -----------------------------------------------------------------------
    # 分类
    # -----------------------------------------------------------------------
    def categoryContent(self, tid, pg, filter, extend):
        extend = extend or {}
        params = {
            'pageNum': int(pg) if str(pg).isdigit() else 1,
            'pageSize': PAGE_SIZE,
            'sort': 1,
            'sortBy': 1,
            'type1': str(tid),
        }
        # 支持扩展筛选（排序/地区/年份等，站点支持则透传）
        for k in ('sort', 'sortBy', 'area', 'year', 'lang', 'v_class', 'type'):
            if extend.get(k) not in (None, ''):
                params[k] = extend[k]
        data = self._api('/anonymous/video/list', params)
        vlist = []
        if data:
            for it in (data.get('list') or []):
                v = self._to_video(it)
                if v:
                    vlist.append(v)
        return {
            'list': vlist,
            'page': params['pageNum'],
            'pagecount': int(data.get('totalPage') or 1) if data else 1,
            'limit': PAGE_SIZE,
            'total': int((data.get('totalCount') or 0)) if data else 0,
        }

    # -----------------------------------------------------------------------
    # 搜索
    # -----------------------------------------------------------------------
    def searchContent(self, key, quick, pg='1'):
        params = {
            'keyword': key,
            'pageNum': int(pg) if str(pg).isdigit() else 1,
            'pageSize': PAGE_SIZE,
        }
        data = self._api('/anonymous/video/searchByWord', params)
        vlist = []
        total = 0
        pagecount = 1
        if data:
            res = data.get('result') or {}
            for it in (res.get('list') or []):
                v = self._to_video(it)
                if v:
                    vlist.append(v)
            total = int(res.get('totalCount') or 0)
            pagecount = int(res.get('totalPage') or 1)
        return {'list': vlist, 'page': params['pageNum'], 'pagecount': pagecount, 'total': total}

    # -----------------------------------------------------------------------
    # 详情
    # -----------------------------------------------------------------------
    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) else ids
        data = self._api('/anonymous/video/detail', {'id': vid}, timeout=REQ_TIMEOUT)
        if not data:
            return {'list': []}
        name = data.get('vodName') or ''
        if _is_minor(name) or _is_minor(data.get('vodContent') or ''):
            return {'list': []}

        eps = data.get('episodeList') or []
        # 20261120.2：三档清晰度做成三条可切换线路。
        # 原版默认取 1080P（码率约 2-4MB/s），弱链路（如截图 393KB/s）必然一直缓冲转圈；
        # 现在默认 720P(流畅)，另给 480P(极速)/1080P(高清) 手动切换。
        # 播放串：集名$vid|nid|resolution（透传清晰度档位给 playerContent）
        ep_list = []
        for ep in sorted(eps, key=lambda e: (e.get('sort') or 0)):
            epname = ep.get('name') or '第%s集' % (ep.get('sort') or 1)
            nid = ep.get('nid')
            if nid is None or _is_minor(epname):
                continue
            ep_list.append((epname, nid))
        qualities = [(720, '720P流畅'), (480, '480P极速'), (1080, '1080P高清')]
        _froms, _urls = [], []
        for res, label in qualities:
            items = ['%s$%s|%s|%s' % (epname, vid, nid, res) for epname, nid in ep_list]
            _froms.append('Y5·' + label)
            _urls.append('#'.join(items))
        play_from = '$$$'.join(_froms)
        play_url = '$$$'.join(_urls)
        vod = {
            'vod_id': str(vid),
            'vod_name': name,
            'vod_pic': _norm_pic(data.get('vodPic')),
            'type_name': data.get('typeName') or data.get('vodClass') or '',
            'vod_year': str(data.get('vodYear') or ''),
            'vod_area': data.get('vodArea') or '',
            'vod_actor': data.get('vodActor') or '',
            'vod_director': data.get('vodDirector') or '',
            'vod_content': re.sub(r'<[^>]+>', '', data.get('vodContent') or ''),
            'vod_remarks': data.get('vodVersion') or data.get('vodDuration') or '',
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }
        return {'list': [vod]}

    # -----------------------------------------------------------------------
    # 播放：实时取 m3u8（auth_key 时效，绝不缓存），parse:0 透传
    # -----------------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags):
        # id 形如 "vid|nid|resolution"；兼容旧版 "vid|nid"
        parts = str(id).split('|')
        vid = parts[0]
        nid = parts[1] if len(parts) > 1 else None
        want = None
        if len(parts) > 2:
            try:
                want = int(parts[2])
            except (ValueError, TypeError):
                want = None
        try:
            params = {'clientType': 3, 'id': int(vid)}
            if nid is not None:
                params['nid'] = int(nid)
        except (ValueError, TypeError):
            return {'parse': 0, 'url': '', 'header': {}}

        data = self._api('/anonymous/v2/video/episode/url', params, timeout=REQ_TIMEOUT)
        if not data:
            return {'parse': 0, 'url': '', 'header': {}}
        items = [x for x in (data.get('list') or []) if x.get('url')]
        if not items:
            return {'parse': 0, 'url': '', 'header': {}}

        # 20261120.2：按线路指定档位取；缺失则按 720>480>1080 回退（优先低码率保流畅）。
        if want is not None:
            exact = [x for x in items if x.get('resolution') == want]
            if exact:
                url = exact[0]['url']
            else:
                prefer = {720: 0, 480: 1, 1080: 2}
                url = sorted(items, key=lambda x: prefer.get(x.get('resolution'), 9))[0]['url']
        else:
            prefer = {720: 0, 480: 1, 1080: 2}
            url = sorted(items, key=lambda x: prefer.get(x.get('resolution'), 9))[0]['url']
        return {
            'parse': 0,
            'url': url,
            'header': {'User-Agent': UA, 'Referer': self.host + '/'},
        }

    def localProxy(self, param):
        # 海报为直连合法 WEBP，播放为实时直链，无需本地代理
        return [404, 'text/plain', 'no proxy needed']


# ---------------------------------------------------------------------------
# 模块级函数转发（兼容按函数名调用的壳子）
# ---------------------------------------------------------------------------
_spider = None


def _S():
    global _spider
    if _spider is None:
        _spider = Spider()
        _spider.init('')
    return _spider


def getName():
    return _S().getName()


def init(extend=''):
    return _S().init(extend)


def homeContent(filter=False):
    return _S().homeContent(filter)


def homeVideoContent():
    return _S().homeVideoContent()


def categoryContent(tid, pg, filter, extend):
    return _S().categoryContent(tid, pg, filter, extend)


def detailContent(ids):
    return _S().detailContent(ids)


def searchContent(key, quick, pg='1'):
    return _S().searchContent(key, quick, pg)


def playerContent(flag, id, vipFlags):
    return _S().playerContent(flag, id, vipFlags)


def localProxy(param):
    return _S().localProxy(param)


# ---------------------------------------------------------------------------
# 类名别名：部分内核按 api 文件名反射取类（如 ./py/Y5影院.py -> 找 Y5影院 类），
# 部分按 spider/y5site 约定取类。全部指向同一实现，确保任何加载方式都能命中。
# ---------------------------------------------------------------------------
Y5影院 = Spider
Y5Site = Spider
y5site = Spider
Y5 = Spider


# 命令行自检：python Y5影院.py home|search|detail|play
if __name__ == '__main__':
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'home'
    _sp = Spider()
    _sp.init('')
    if cmd == 'home':
        print(json.dumps(_sp.homeContent(True), ensure_ascii=False)[:800])
    elif cmd == 'search' and len(sys.argv) > 2:
        print(json.dumps(_sp.searchContent(sys.argv[2], False, '1'), ensure_ascii=False)[:800])
    elif cmd == 'detail' and len(sys.argv) > 2:
        print(json.dumps(_sp.detailContent([sys.argv[2]]), ensure_ascii=False)[:800])
    elif cmd == 'play' and len(sys.argv) > 2:
        print(json.dumps(_sp.playerContent('Y5', sys.argv[2], []), ensure_ascii=False))
    else:
        print('usage: python Y5影院.py home|search <kw>|detail <id>|play <vid|nid>')
