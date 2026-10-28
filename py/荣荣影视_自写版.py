# -*- coding: utf-8 -*-
# 荣荣影视 TVBox py 源 —— 独立重写版
# 站点特性：需登录（Cookie: auth 鉴权，非 Bearer）；自己不存片源，
# 是聚合器——榜单走豆瓣(/api/douban)、内容发现走 TMDB(/api/tmdb)、
# 播放靠 /api/search/resources 聚合外部 AppleCMS 站用片名解析。
# 代码结构为本实现独立设计（登录、榜单、搜索、详情、外部解析均自实现）。

import json
import re
import time
import threading
import urllib.parse
import urllib.request

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass

# ---------- 常量 ----------
HOST = 'https://rrys.dpdns.org'
API = HOST + '/api'            # 所有接口都在 /api 前缀下
UA = 'Mozilla/5.0 (Linux; Android 13; V2049A Build/TP1A.220624.014; wv) ' \
     'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 ' \
     'Mobile Safari/537.36'
ACCOUNT = {'username': 'kill', 'password': '123456'}
PAGE_SIZE = 16          # 豆瓣榜单每页条数
DEADLINE = 35           # 外部解析总时限（秒）
WORKERS = 8             # 外部解析并发


def _norm(s):
    """归一化片名：小写 + 去非字母数字，用于比对。"""
    return ''.join(ch for ch in (str(s or '').lower()) if ch.isalnum())


def _strip_year(name):
    return re.sub(r'\s*[（(]?\s*(?:19|20)\d{2}\s*[)）]?\s*$', '', str(name or '')).strip()


def _name_ok(site_name, want, year=''):
    """外部站返回片名与目标片名校验（含年份冲突检测）。"""
    a, b = _norm(site_name), _norm(want)
    if not a or not b:
        return False
    if not (a == b or b in a or a in b):
        return False
    if year:
        m = re.search(r'(?:19|20)\d{2}', a)
        if m and m.group(0) != year and year not in b:
            return False
    return True


def _pick_ep(play_url, episode):
    """从 AppleCMS vod_play_url 按集号取地址；第一集/整片兜底取第一段。"""
    for line in (play_url or '').split('$$$'):
        for seg in line.split('#'):
            if '$' not in seg:
                continue
            ep_no, u = seg.split('$', 1)
            m = re.search(r'\d+', ep_no)
            if m and int(m.group(0)) == episode:
                return u
    if episode == 1:
        for line in (play_url or '').split('$$$'):
            for seg in line.split('#'):
                if '$' in seg:
                    ep_no, u = seg.split('$', 1)
                    if not re.search(r'\d+', ep_no):
                        return u
    return ''


class Spider(BaseSpider):
    def getName(self):
        return '荣荣影视'

    # ---------- 网络 ----------
    def _open(self, url, data=None, headers=None, timeout=15):
        h = {'User-Agent': UA, 'Accept': 'application/json',
             'Referer': HOST + '/'}
        if headers:
            h.update(headers)
        if self.auth:
            h['Cookie'] = self.auth
        req = urllib.request.Request(url, data=data, headers=h, method='POST' if data else 'GET')
        return urllib.request.urlopen(req, timeout=timeout)

    def _post(self, path, payload):
        body = json.dumps(payload).encode()
        try:
            with self._open(API + path, body) as r:
                return json.loads(r.read().decode('utf-8', 'ignore')), r.headers.get('Set-Cookie')
        except Exception:
            return {}, None

    def _get_json(self, path, params=None, retry=5, timeout=15):
        url = API + path
        if params:
            url += '?' + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        for _ in range(retry):
            try:
                with self._open(url, timeout=timeout) as r:
                    return json.loads(r.read().decode('utf-8', 'ignore'))
            except Exception:
                time.sleep(0.8)
        return {}

    # ---------- 鉴权 ----------
    def init(self, extend=''):
        self.auth = ''
        self._login()
        return ''

    def _login(self):
        for _ in range(8):
            _, cookie = self._post('/login', dict(ACCOUNT))
            if cookie:
                for part in cookie.split(','):
                    if 'auth=' in part:
                        self.auth = 'auth=' + part.split('auth=')[1].split(';')[0]
                        return
            time.sleep(0.6)

    # ---------- 列表项 ----------
    def _douban_row(self, v, kind):
        v = v or {}
        year = str(v.get('year') or '').strip()
        rate = str(v.get('rate') or '').strip()
        return {
            'vod_id': 'd%s@%s' % (v.get('id'), kind),
            'vod_name': v.get('title') or '',
            'vod_pic': v.get('poster') or '',
            'vod_remarks': ' '.join(x for x in (year, rate) if x),
        }

    def _tmdb_row(self, v):
        v = v or {}
        tid = str(v.get('id') or v.get('tmdbId') or '')
        mt = v.get('media_type') or ('tv' if v.get('first_air_date') else 'movie')
        date = v.get('release_date') or v.get('first_air_date') or ''
        pic = 'https://image.tmdb.org/t/p/w500' + (v.get('poster_path') or v.get('backdrop_path') or '')
        score = str(v.get('vote_average') or '')
        return {
            'vod_id': '%s@%s' % (tid, mt),
            'vod_name': v.get('title') or v.get('name') or '',
            'vod_pic': pic,
            'vod_remarks': (date[:4] + ' ' + score).strip(),
        }

    # ---------- 首页 / 分类 ----------
    def homeContent(self, filter):
        classes = [
            {'type_id': 'movie', 'type_name': '电影'},
            {'type_id': 'tv', 'type_name': '电视剧'},
            {'type_id': 'movie|热门', 'type_name': '电影·热门'},
            {'type_id': 'tv|热门', 'type_name': '剧集·热门'},
        ]
        return {'class': classes}

    def homeVideoContent(self):
        return {'list': self._douban_paged('movie', '热门', 1)}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        kind, _, tag = tid.partition('|')
        kind = kind or 'movie'
        tag = tag or '热门'
        return {'list': self._douban_paged(kind, tag, pg),
                'page': pg, 'pagecount': 999, 'limit': PAGE_SIZE, 'total': 99999}

    def _douban_paged(self, kind, tag, pg):
        start = (pg - 1) * PAGE_SIZE
        d = self._get_json('/douban', {'type': kind, 'tag': tag,
                                       'pageLimit': PAGE_SIZE, 'pageStart': start}) or {}
        out, seen = [], set()
        for v in d.get('list') or []:
            vid = str(v.get('id') or '')
            if not vid or vid in seen:
                continue
            seen.add(vid)
            out.append(self._douban_row(v, kind))
        return out

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg='1'):
        pg = int(pg) if str(pg).isdigit() else 1
        d = self._get_json('/tmdb/search', {'query': key or '', 'page': pg})
        rows = d.get('results') or d.get('data') or []
        return {'list': [self._tmdb_row(v) for v in rows if str(v.get('id') or '')], 'page': pg}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        raw = ids[0]
        tid, sep, typ = raw.partition('@')
        if not sep:
            return {'list': []}
        if tid.startswith('d'):
            return {'list': [self._douban_detail(tid[1:], typ)]}
        info = self._get_json('/tmdb/detail', {'id': tid, 'type': typ}) or {}
        if not info:
            info = self._get_json('/douban/detail', {'id': tid}) or {}
            if info:
                return {'list': [self._douban_detail(tid, typ)]}
            return {'list': []}
        name = info.get('name') or info.get('title') or ''
        year = (info.get('release_date') or info.get('first_air_date') or '')[:4]
        pic = info.get('poster_path') or ''
        if pic:
            pic = 'https://image.tmdb.org/t/p/w500' + pic
        seasons = info.get('seasons') or []
        play_from, play_url = [], []
        if not seasons:
            # 电影/单集：兜底一集
            key = '%s@%s@1@1@%s@%s' % (tid, typ, urllib.parse.quote(name), year)
            play_from.append('正片')
            play_url.append('正片$%s' % key)
        dl = time.time() + 30   # 详情总时限：服务器不稳，慢的季快速跳过
        for s in seasons:
            if time.time() > dl:
                break
            sn = s.get('season_number')
            ed = self._get_json('/tmdb/episodes', {'id': tid, 'season': sn,
                                                   'type': typ}, retry=1, timeout=10) or {}
            eps = ed.get('episodes') or []
            segs = []
            for e in eps:
                en = e.get('episode_number')
                et = e.get('name') or '第%s集' % en
                key = '%s@%s@%s@%s@%s@%s' % (tid, typ, sn, en,
                                             urllib.parse.quote(name), year)
                segs.append('%s$%s' % (et, key))
            if segs:
                play_from.append('第%s季' % sn)
                play_url.append('#'.join(segs))
        return {'list': [{
            'vod_id': raw,
            'vod_name': name,
            'vod_pic': pic,
            'vod_year': year,
            'vod_content': info.get('overview') or '',
            'vod_play_from': '$$$'.join(play_from) or '正片',
            'vod_play_url': '$$$'.join(play_url),
        }]}

    def _douban_detail(self, did, typ):
        d = self._get_json('/douban/detail', {'id': did}) or {}
        name = d.get('title') or ''
        year = str(d.get('year') or '')[:4]
        pic = d.get('poster') or ''
        n = int(d.get('episodes_count') or d.get('last_episode_number') or 0)
        segs = []
        for i in range(1, n + 1):
            key = '%s@%s@1@%d@%s@%s' % (did, typ, i, urllib.parse.quote(name), year)
            segs.append('第%s集$%s' % (i, key))
        if not segs:
            key = '%s@%s@1@1@%s@%s' % (did, typ, urllib.parse.quote(name), year)
            segs.append('正片$%s' % key)
        return {
            'vod_id': 'd%s@%s' % (did, typ),
            'vod_name': name,
            'vod_pic': pic,
            'vod_year': year,
            'vod_content': d.get('intro') or '',
            'vod_play_from': '正片',
            'vod_play_url': '#'.join(segs),
        }

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        parts = id.split('@')
        if len(parts) < 5:
            return {'parse': 0, 'url': id}
        tid, typ, season, episode = parts[0], parts[1], parts[2], parts[3]
        name = urllib.parse.unquote(parts[4])
        year = urllib.parse.unquote(parts[5]) if len(parts) > 5 else ''
        url = self._resolve(tid, name, int(season), int(episode), year)
        if not url:
            return {'parse': 0, 'url': ''}
        return {
            'parse': 0 if '.m3u8' in url else 1,
            'playUrl': '',
            'url': url,
            'header': {'User-Agent': UA, 'Referer': HOST + '/'},
        }

    def _resolve(self, tid, name, season, episode, year=''):
        """并发查外部资源站，解析指定季/集地址。"""
        apis = []
        for _ in range(6):   # resources 偶发返回空 dict，重试到拿到 list
            res = self._get_json('/search/resources', {'id': tid}, retry=2, timeout=12)
            if isinstance(res, list) and res:
                apis = res
                break
            time.sleep(0.5)
        sources = [a for a in apis if a.get('api')]   # 所有源都参与解析（含🔞成人源）
        if not sources:
            return ''
        deadline = time.time() + DEADLINE
        found, lock, idx = [], threading.Lock(), [0]

        def work():
            while time.time() < deadline:
                with lock:
                    if idx[0] >= len(sources):
                        return
                    api = sources[idx[0]]
                    idx[0] += 1
                url = self._site_search(api, name, season, episode, year)
                if url:
                    with lock:
                        if not found:
                            found.append(url)
                    return

        ts = [threading.Thread(target=work, daemon=True) for _ in range(WORKERS)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(max(1.0, deadline - time.time()))
        return found[0] if found else ''

    def _site_search(self, api, name, season, episode, year=''):
        base = api.get('api') or ''
        base = base.rstrip('/')
        headers = {'User-Agent': UA, 'Referer': base}
        queries = [name]
        bare = _strip_year(name)
        if bare and bare != name:
            queries.append(bare)
        for q in queries:
            try:
                u = base + '?ac=videolist&wd=' + urllib.parse.quote(q)
                with urllib.request.urlopen(
                        urllib.request.Request(u, headers=headers), timeout=10) as r:
                    j = json.loads(r.read().decode('utf-8', 'ignore'))
                for v in j.get('list') or []:
                    if not _name_ok(v.get('vod_name') or '', name, year):
                        continue
                    url = _pick_ep(v.get('vod_play_url') or '', episode)
                    if url:
                        return url
            except Exception:
                continue
        return ''

    def isVideoFormat(self, url):
        return True

    def isTextFormat(self, url):
        return False

    def localProxy(self, param):
        return [404, 'text/plain', b'']

    def destroy(self):
        pass


# ---------- 模块级转发 ----------
_inst = None


def _sp():
    global _inst
    if _inst is None:
        _inst = Spider()
    return _inst


def getName():
    return _sp().getName()


def init(extend=''):
    return _sp().init(extend)


def homeContent(filter=None):
    return _sp().homeContent(filter)


def homeVideoContent():
    return _sp().homeVideoContent()


def categoryContent(tid, pg=1, filter=None, extend=None):
    return _sp().categoryContent(tid, pg, filter, extend)


def detailContent(ids):
    return _sp().detailContent(ids)


def searchContent(key, quick=False, pg=1):
    return _sp().searchContent(key, quick, pg)


def searchContentPage(key, quick=False, pg=1):
    return _sp().searchContent(key, quick, pg)


def playerContent(flag, id, vipFlags=None):
    return _sp().playerContent(flag, id, vipFlags)


def isVideoFormat(url):
    return _sp().isVideoFormat(url)


def isTextFormat(url):
    return _sp().isTextFormat(url)


def manualVideoCheck():
    return False


def getDependence():
    return []


def localProxy(param):
    return _sp().localProxy(param)


def destroy():
    return _sp().destroy()
