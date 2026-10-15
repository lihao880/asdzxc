# -*- coding: utf-8 -*-
# TVBox/影视仓 Python 爬虫 - 懂片帝AI dongpian5.com
# 2026-10-15 全链路实测通过 (列表/搜索/详情/播放)
#
# 【站点性质】Vite+React SPA, 数据全部走后端 JSON API, 页面 HTML 无内容
#   页面 HTML 只是 4KB 骨架 → 必须直接调 API, 不能解析 HTML
#
# 【逆向要点】(对照普通 MacCMS 站的难点)
#   1. 所有 /v1/ 接口需要 HMAC-SHA256 签名头, 否则 401 invalid_request_signature
#      密钥: 8b9a908a05eac640e1ee06f52acaa741bfe4ba9e004eeffdbeb635e532e06666
#      待签串(4行, \n 分隔): METHOD\n{pathname}{search}\ntimestamp_ms\nnonce
#      nonce = 16 随机字节 → 32 位 hex; 签名 = HMAC-SHA256 结果 hex (64位)
#   2. 4 个客户端信息头必带: x-ai-movie-client-name/version/build-version/protocol-version
#   3. 公开数据无需登录 (feed/catalog/suggest 匿名可读)
#   4. 播放 line_options 里 m3u8 直链 (url_kind=m3u8, resolve_required=False) 可直接播;
#      resolve:// 开头的需二次解析 (本实现自动跳过, 优先选直链)
#
# 【接口清单】(实测)
#   GET  /v1/feed/home?scope=public&mode=preview&sections=N&cards=M   首页
#   GET  /v1/browse/catalog?sort=trending&window=week&kind={kind}&page=&limit=  分类
#   GET  /v1/browse/catalog?q={kw}&sort=relevance&page=&limit=        搜索
#   GET  /v1/catalog/{variant_id}                                     详情
#   GET  /v1/catalog/{variant_id}/episodes                            剧集列表
#   GET  /v1/playback/episodes/{episode_token}                        播放线路
#   GET  /v1/suggest?q=&limit=&mode=home&scope=public                 联想
# 学习用途, 请遵守当地法律法规
import os
import re
import sys
import json
import time
import hmac
import hashlib
import urllib.parse
import urllib.request
import ssl

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider(object):
        pass

HOST = 'https://dongpian5.com'
SIGN_KEY = '8b9a908a05eac640e1ee06f52acaa741bfe4ba9e004eeffdbeb635e532e06666'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
CLIENT_HEADERS = {
    'x-ai-movie-client-name': 'movie-search-frontend',
    'x-ai-movie-client-version': '1.0.0',
    'x-ai-movie-build-version':
        'dongpiandi-v2026.10.15.2-danmaku-suggestions-02f82e7bd711-web',
    'x-ai-movie-protocol-version': '2026-07-05.library-v2.playback-v1',
}
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
_CACHE = {}

# 分类: (kind, 名称) —— kind 即 API 的 content_kind 参数
TYPES = [
    ('movie', '电影'), ('series', '剧集'), ('short_drama', '短剧'),
    ('anime', '动漫'), ('variety', '综艺'), ('documentary', '纪录片'),
    ('sports', '体育'),
]
SORTS = [('trending', '热播'), ('latest', '最新'), ('rating', '高分')]
WINDOWS = [('week', '本周'), ('month', '本月'), ('all', '全部')]

# 播放线路优先级: 优先挑直链 m3u8
DIRECT_KINDS = ('m3u8', 'mp4')
DIRECT_PROVIDERS = (
    'hongniu', 'hhzy', 'jinying', 'yyzy1080', 'mdzy', 'xinlang',
    'dbzy', 'iqiyi', 'jszy', 'bfzy', 'ikun', 'wujin', 'uku', 'dytt',
    'maotai', 'maoyan', 'ffzy', 'subo', 'liangzi', 'niuniu', 'zuida',
    'zy360', 'wsyzy', 'xigua',
)


def _log(*a):
    try:
        sys.stderr.write('[懂片帝] ' + ' '.join(str(x) for x in a) + '\n')
    except Exception:
        pass


# ---------- 签名 ----------
def _nonce():
    return os.urandom(16).hex()


def _sign(method, path_qs, ts, nc):
    """HMAC-SHA256(KEY, 'METHOD\\npath?query\\nts\\nnonce') → hex"""
    msg = '%s\n%s\n%s\n%s' % (method.upper(), path_qs, ts, nc)
    return hmac.new(SIGN_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()


# ---------- HTTP ----------
def _api(path_qs, method='GET', body=None, timeout=15, tries=2):
    """带签名请求 /v1/ 接口, 返回解析后的 dict 或 None"""
    for attempt in range(tries):
        try:
            ts = str(int(time.time() * 1000))
            nc = _nonce()
            h = {
                'User-Agent': UA,
                'Accept': 'application/json',
                'Origin': HOST,
                'Referer': HOST + '/',
                'x-ai-movie-timestamp': ts,
                'x-ai-movie-nonce': nc,
                'x-ai-movie-signature': _sign(method, path_qs, ts, nc),
            }
            h.update(CLIENT_HEADERS)
            data = None
            if body is not None:
                data = json.dumps(body).encode('utf-8')
                h['Content-Type'] = 'application/json'
            req = urllib.request.Request(HOST + path_qs, data=data,
                                         headers=h, method=method)
            resp = urllib.request.urlopen(req, timeout=timeout, context=_CTX)
            raw = resp.read()
            if raw[:2] == b'\x1f\x8b':
                import gzip
                raw = gzip.decompress(raw)
            return json.loads(raw.decode('utf-8', 'ignore'))
        except Exception as e:
            _log('%s失败(%d/%d)' % (method, attempt + 1, tries),
                 path_qs[:70], repr(e)[:70])
            time.sleep(0.3)
    return None


def _cache_get(k):
    v = _CACHE.get(k)
    if v and v[0] > time.time():
        return v[1]
    if v:
        _CACHE.pop(k, None)
    return None


def _cache_set(k, val, ttl=300):
    if len(_CACHE) > 200:
        _CACHE.clear()
    _CACHE[k] = (time.time() + ttl, val)


def _api_cached(path_qs, ttl=300):
    ck = 'A|' + path_qs
    hit = _cache_get(ck)
    if hit is not None:
        return hit
    j = _api(path_qs)
    _cache_set(ck, j, ttl if j else 60)
    return j


# ---------- 数据装配 ----------
def _pic(u):
    """封面: 站内走百度图床代理, 已是 http 则原样"""
    if not u:
        return ''
    if u.startswith('http'):
        return u
    return u


def _kind_cn(k):
    for kk, cn in TYPES:
        if kk == k:
            return cn
    return {'movie': '电影', 'series': '剧集', 'short_drama': '短剧',
            'anime': '动漫', 'variety': '综艺', 'documentary': '纪录片',
            'sports': '体育'}.get(k, k or '')


def _vod_from_card(c):
    """card / variant 结构 → TVBox vod"""
    vid = c.get('variant_id') or c.get('id') or ''
    title = c.get('title') or c.get('normalized_title') or ''
    remarks = c.get('remarks') or ''
    if not remarks:
        us = c.get('update_status')
        ec = c.get('episode_count') or 0
        aec = c.get('available_episode_count') or 0
        if us == 'completed' or c.get('is_completed'):
            remarks = '已完结' if not ec else '全%s集' % ec
        elif aec:
            remarks = '更新至%s集' % aec
        elif ec:
            remarks = '共%s集' % ec
    return {
        'vod_id': vid,
        'vod_name': title,
        'vod_pic': _pic(c.get('poster_url') or ''),
        'vod_remarks': remarks,
        'vod_year': str(c.get('year') or ''),
        'vod_area': c.get('area') or '',
        'vod_actor': ','.join(c.get('actors') or [])[:200],
        'vod_content': c.get('description') or '',
        '_kind': c.get('content_kind') or '',
    }


def _vods_from_cards(j):
    vods, seen = [], set()
    if not isinstance(j, dict):
        return vods
    cards = j.get('cards') or j.get('variants') or []
    if not isinstance(cards, list):
        return vods
    for c in cards:
        if not isinstance(c, dict):
            continue
        v = _vod_from_card(c)
        if not v['vod_id'] or v['vod_id'] in seen:
            continue
        seen.add(v['vod_id'])
        vods.append(v)
    return vods


def _best_line(lines):
    """从 line_options 里挑最佳直链: 优先 m3u8 直链, 按 preference_weight 降序"""
    direct, resolve = [], []
    for lo in lines or []:
        if not isinstance(lo, dict):
            continue
        url = lo.get('url') or ''
        if not url.startswith('http'):
            continue
        if lo.get('url_kind') in DIRECT_KINDS or not lo.get('resolve_required'):
            direct.append(lo)
        else:
            resolve.append(lo)
    pool = direct or resolve
    if not pool:
        return None
    pool.sort(key=lambda x: -(x.get('preference_weight') or 0))
    return pool[0]


class Spider(_BaseSpider):

    def getName(self):
        return "懂片帝AI"

    def init(self, extend=""):
        self.site = HOST
        self._ep = {}   # 缓存: variant_id -> [episode dict]

    def destroy(self):
        pass

    def homeContent(self, filter):
        classes = [{"type_id": k, "type_name": n} for k, n in TYPES]
        filters = {}
        for k, _ in TYPES:
            filters[k] = [
                {"key": "sort", "name": "排序",
                 "value": [{"n": n, "v": v} for v, n in SORTS]},
                {"key": "window", "name": "周期",
                 "value": [{"n": n, "v": v} for v, n in WINDOWS]},
            ]
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        j = _api_cached(
            '/v1/feed/home?scope=public&mode=preview&sections=4&cards=12', ttl=600)
        vods, seen = [], set()
        if isinstance(j, dict):
            for sec in (j.get('sections') or []):
                for v in _vods_from_cards(sec):
                    if v['vod_id'] in seen:
                        continue
                    seen.add(v['vod_id'])
                    vods.append(v)
                    if len(vods) >= 36:
                        break
                if len(vods) >= 36:
                    break
        return {"list": vods[:36]}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = max(1, int(pg))
        except Exception:
            pg = 1
        sort, window = 'trending', 'week'
        if isinstance(extend, dict):
            sort = extend.get('sort') or sort
            window = extend.get('window') or window
        if sort not in ('trending', 'latest', 'rating', 'relevance'):
            sort = 'trending'
        if window not in ('week', 'month', 'all'):
            window = 'week'
        kind = tid if tid in [k for k, _ in TYPES] else 'movie'
        q = ('/v1/browse/catalog?sort=%s&window=%s&kind=%s&page=%d&limit=20'
             % (sort, window, kind, pg))
        j = _api_cached(q)
        vods = _vods_from_cards(j)
        has_more = False
        if isinstance(j, dict):
            pg_info = j.get('pagination') or {}
            has_more = bool(pg_info.get('has_more'))
        return {
            "list": vods, "page": pg,
            "pagecount": pg + 1 if (has_more or len(vods) >= 20) else pg,
            "limit": 20, "total": 999999 if vods else 0,
        }

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = max(1, int(pg))
        except Exception:
            pg = 1
        if not key:
            return {"list": [], "page": pg}
        q = '/v1/browse/catalog?q=%s&sort=relevance&page=%d&limit=20' % (
            urllib.parse.quote(key), pg)
        vods = _vods_from_cards(_api_cached(q, ttl=180))
        return {"list": vods, "page": pg}

    def _episodes(self, variant_id):
        """取剧集列表并缓存"""
        if variant_id in self._ep:
            return self._ep[variant_id]
        j = _api_cached('/v1/catalog/%s/episodes' % variant_id, ttl=600)
        eps = []
        if isinstance(j, dict):
            eps = j.get('episodes') or []
        self._ep[variant_id] = eps
        return eps

    def detailContent(self, array):
        vid = str(array[0] if isinstance(array, list) else array)
        vid = vid.strip()
        if not vid:
            return {"list": []}
        j = _api_cached('/v1/catalog/%s' % urllib.parse.quote(vid), ttl=600)
        vod = {"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_content": "",
               "vod_year": "", "vod_area": "", "vod_actor": "", "vod_remarks": ""}
        if not isinstance(j, dict):
            return {"list": [vod]}

        vod.update({
            "vod_name": j.get('title') or j.get('normalized_title') or '',
            "vod_pic": _pic(j.get('poster_url') or ''),
            "vod_year": str(j.get('year') or ''),
            "vod_area": j.get('area') or '',
            "vod_actor": ','.join(j.get('actors') or [])[:300],
            "vod_content": j.get('description') or '',
            "vod_remarks": j.get('remarks') or '',
        })

        # 剧集: 优先详情自带 episodes, 否则单独请求
        eps = j.get('episodes') or []
        if not eps:
            eps = self._episodes(vid)
        if eps:
            self._ep[vid] = eps

        items = []
        for i, e in enumerate(eps):
            if not isinstance(e, dict):
                continue
            token = e.get('token') or e.get('id') or ''
            if not token:
                continue
            nm = e.get('title') or ('第%d集' % (e.get('number') or (i + 1)))
            items.append('%s$%s' % (nm, token))

        vod["vod_play_from"] = '懂片帝'
        vod["vod_play_url"] = '#'.join(items) if items else ''
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        header = {"User-Agent": UA}
        token = str(id or '').strip()
        if not token or '$' in token:
            token = token.split('$')[-1]
        if not token:
            return {"parse": 0, "playUrl": "", "url": "", "header": header}

        j = _api_cached('/v1/playback/episodes/%s' % urllib.parse.quote(token),
                        ttl=180)
        url = ''
        if isinstance(j, dict):
            lines = j.get('line_options') or []
            best = _best_line(lines)
            if best:
                cand = best.get('url') or ''
                if cand.startswith('http') and not cand.startswith('resolve://'):
                    url = cand
                else:
                    _log('最优线路需二次解析, 尝试其他直链',
                         best.get('provider_name'))
                    # 换一条纯直链
                    for lo in lines:
                        u2 = lo.get('url') or ''
                        if u2.startswith('http') and lo.get('url_kind') in DIRECT_KINDS:
                            url = u2
                            break
            if not url:
                # 兜底: 任意 http m3u8
                for lo in lines or []:
                    u2 = (lo or {}).get('url') or ''
                    if u2.startswith('http') and '.m3u8' in u2:
                        url = u2
                        break
        if not url:
            _log('未取得播放地址', token[:30])
        return {"parse": 0, "playUrl": "", "url": url, "header": header}


# 学习用途
