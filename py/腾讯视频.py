# -*- coding: utf-8 -*-
"""
腾讯视频 TVBox / 影视仓 Python 爬虫源  v2.0
============================================================
站点: https://v.qq.com/channel/tv   (电视剧频道，其余频道同理)
接口: https://pbaccess.video.qq.com  (腾讯视频 Web 端公开接口)

覆盖: 7 大分类 · 全维度筛选(592 个选项) · 翻页 · 搜索 · 详情 · 剧集 · 播放

【本版重点：分类/类型可选】
  homeContent() 会为每个分类下发完整筛选维度，播放器里点开「筛选」即可
  逐级选择「类型 / 地区 / 年份 / 资费 / 排序 ...」，且**多维度可叠加**。
  例：电视剧 → 类型=悬疑 + 地区=内地 + 年份=2024 → 精准出片。

【接口清单】
  分类列表  POST /trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData
              ?video_appid=1000005&vplatform=2&vversion_name=8.9.10&new_mark_label_enabled=1
              page_params.page_id = channel_list_second_page
              ├─ 不传 page  → 返回该分类的全部筛选维度（sort/itype/iarea/iyear...）
              └─ 传   page  → 返回该分类第 N 页影片列表（每页 21 条）
              筛选靠 filter_params 拼接，形如 "sort=75&itype=6&iarea=8"
              ⚠ 筛选值必须用接口下发的原始值(option_value)，各分类之间不通用
  搜索      POST /trpc.videosearch.mobile_search.MultiTerminalSearch/MbSearch?vplatform=2
  详情介绍  POST .../GetPageData?video_appid=3000010&vplatform=2&vversion_name=8.2.96
              page_id = detail_page_introduction
  剧集列表  POST .../GetPageData?video_appid=3000010&vplatform=2&vversion_name=8.2.96
              page_id = vsite_episode_list   (携带 module_params.tabs 处理多分段)
  播放      https://v.qq.com/x/cover/{cid}/{vid}.html  → 交给框架内置解析(jx=1)

────────────────────────────────────────────────────────────
【实测记录 2026-10-16】接口全部验证通过：
  · 电视剧 8 维 / 电影 9 维 / 综艺 7 维 / 纪录片 7 维 / 动漫 7 维 / 少儿 8 维 / 短剧 5 维
  · 分页稳定 21 条/页，多条件叠加筛选结果正确
  · 参数顺序对结果无影响（已实测 3 种顺序结果一致），本版仍按接口下发顺序拼接
────────────────────────────────────────────────────────────

仅供学习交流，请勿用于商业用途。
"""

import json
import time
import uuid
import gzip
import re
import urllib.parse
import urllib.request
import ssl

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider(object):
        pass

# ============================ 常量 ============================
API = 'https://pbaccess.video.qq.com'
HOST = 'https://v.qq.com'

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/109.0.5410.0 Safari/537.36')

HEADERS = {
    'User-Agent': UA,
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Content-Type': 'application/json',
    'Origin': HOST,
    'Referer': HOST + '/',
}

LIST_API = (API + '/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData'
            '?video_appid=1000005&vplatform=2&vversion_name=8.9.10&new_mark_label_enabled=1')
DETAIL_API = (API + '/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData'
              '?video_appid=3000010&vplatform=2&vversion_name=8.2.96')
SEARCH_API = API + '/trpc.videosearch.mobile_search.MultiTerminalSearch/MbSearch?vplatform=2'

# 全部分类（腾讯视频频道 ID）
CLASSES = [
    ('电视剧', '100113'),
    ('电影', '100173'),
    ('综艺', '100109'),
    ('纪录片', '100105'),
    ('动漫', '100119'),
    ('少儿', '100150'),
    ('短剧', '110755'),
]

# 排序维度固定排在最前面
_SORT_KEY = 'sort'
_DEFAULT_SORT = '75'   # 最热

# 「全部」选项：接口在末尾下发的重置项（option_name 常等于维度名，值为 -1）
# 这里统一归一化成显示「全部」，并挪到每个维度的第一位
_ALL_NAMES = ('全部', '类型', '地区', '年份', '资费', '排序', '奖项', '剧场', '出品',
              '状态', '画风', '影人', '明星', '明星', '语言', '性别', '年龄', '偏好',
              '主要看点', '身份人设', '故事背景', '为你推荐', '院线', '网络', '全部')

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

_CACHE = {}
_FILTER_CACHE = {}


def _log(*a):
    try:
        print('[腾讯视频]', *[str(x) for x in a])
    except Exception:
        pass


# ============================ HTTP ============================
def _http(url, data=None, method='GET', timeout=15, tries=3):
    body = data.encode('utf-8') if isinstance(data, str) else data
    h = dict(HEADERS)
    h['Accept-Encoding'] = 'gzip'
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=h, method=method)
            resp = urllib.request.urlopen(req, timeout=timeout, context=_CTX)
            raw = resp.read()
            if raw[:2] == b'\x1f\x8b':
                raw = gzip.decompress(raw)
            return raw.decode('utf-8', 'ignore')
        except Exception as e:
            _log('%s 失败(%d/%d)' % (method, i + 1, tries), url[:60], repr(e)[:50])
            time.sleep(0.3 * (i + 1))
    return ''


def _post_json(url, obj, timeout=15, tries=3):
    txt = _http(url, json.dumps(obj, ensure_ascii=False), 'POST', timeout, tries)
    if not txt:
        return None
    try:
        return json.loads(txt)
    except Exception:
        return None


def _ck(key):
    v = _CACHE.get(key)
    if v and v[0] > time.time():
        return v[1]
    if v:
        _CACHE.pop(key, None)
    return None


def _set(key, val, ttl=300):
    if len(_CACHE) > 240:
        # 只清理已过期项，避免整体清空造成的缓存雪崩
        now = time.time()
        for k in [k for k, v in list(_CACHE.items()) if v[0] <= now]:
            _CACHE.pop(k, None)
        if len(_CACHE) > 320:
            _CACHE.clear()
    _CACHE[key] = (time.time() + ttl, val)


# ============================ 解析工具 ============================
def _iter_params(node):
    """深度遍历 JSON，产出所有 item_params / params 字典（对接口改版免疫）"""
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for key in ('item_params', 'params'):
                v = cur.get(key)
                if isinstance(v, dict):
                    yield v
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                if isinstance(v, (dict, list)):
                    stack.append(v)


def _fix_pic(url):
    if not url:
        return ''
    url = str(url)
    if url.startswith('//'):
        url = 'https:' + url
    return url.replace('http://', 'https://')


def _pick(d, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, '', 'None'):
            return v
    return ''


def _year_of(p):
    """年份兜底：year 缺失时从上线时间/描述里正则提取"""
    y = p.get('year')
    if y not in (None, '', 'None'):
        try:
            y = str(int(y))
            if 1900 <= int(y) <= 2100:
                return y
        except Exception:
            pass
    for k in ('holly_online_time', 'publish_date', 'online_time'):
        s = str(p.get(k) or '')
        m = re.search(r'(19|20)\d{2}', s)
        if m:
            return m.group(0)
    return '0'


def _vod(cid, name, pic, remark='', year=''):
    return {
        'vod_id': str(cid),
        'vod_name': str(name or ''),
        'vod_pic': _fix_pic(pic),
        'vod_remarks': str(remark or ''),
        'vod_year': str(year or '0'),
    }


# ============================ 分类列表 ============================
def _list_body(cid, filter_params, page=None):
    pp = {
        'channel_id': str(cid),
        'filter_params': filter_params or ('sort=' + _DEFAULT_SORT),
        'page_type': 'channel_operation',
        'page_id': 'channel_list_second_page',
        'page_context': '',
    }
    # 关键：传 page 才返回影片列表；不传则返回筛选维度
    if page is not None:
        pp['page'] = str(int(page))
    return {'page_params': pp, 'has_cache': 1}


def _fetch_videos(cid, filter_params, page):
    key = 'L|%s|%s|%s' % (cid, filter_params, page)
    hit = _ck(key)
    if hit is not None:
        return hit
    j = _post_json(LIST_API, _list_body(cid, filter_params, page), timeout=20)
    vods, seen = [], set()
    if j and 'data' in j:
        for p in _iter_params(j):
            vid = p.get('cid')
            if not vid or vid in seen:
                continue
            # 列表条目特征：带封面图或标题
            if not (p.get('new_pic_hz') or p.get('new_pic_vt') or p.get('title')):
                continue
            seen.add(vid)
            rm = _pick(p, 'holly_online_time', 'hotval', 'second_title', 'remark')
            vods.append(_vod(
                vid,
                _pick(p, 'mz_title', 'title'),
                _pick(p, 'new_pic_hz', 'new_pic_vt', 'image_url'),
                rm if len(str(rm)) <= 24 else '',
                _year_of(p),
            ))
    _set(key, vods, 300 if vods else 60)
    return vods


def _norm_options(raw):
    """清洗某一维度的选项列表：
    1) 把接口末尾下发的重置项(name==维度名 且 value==-1)统一成「全部」
    2) 去重  3) 把「全部」挪到第一位
    """
    seen = set()
    opts, all_opt = [], None
    for name, val in raw:
        name = str(name or '').strip()
        val = str(val)
        if not name or val in seen:
            continue
        seen.add(val)
        is_all = (val == '-1' and name in _ALL_NAMES)
        if is_all:
            if all_opt is None:
                all_opt = {'n': '全部', 'v': val}
            continue
        opts.append({'n': name, 'v': val})
    # 年份/地区等维度如果接口没下发 -1，也补一个「全部」打头
    if all_opt is None:
        all_opt = {'n': '全部', 'v': '-1'}
    return [all_opt] + opts


def _fetch_filters(cid):
    """取某分类完整筛选维度（不传 page 时接口返回），带 1 小时缓存"""
    cid = str(cid)
    if cid in _FILTER_CACHE:
        return _FILTER_CACHE[cid]
    key = 'F|' + cid
    hit = _ck(key)
    if hit is not None:
        _FILTER_CACHE[cid] = hit
        return hit

    dims, order = {}, []
    j = _post_json(LIST_API, _list_body(cid, 'sort=' + _DEFAULT_SORT, None), timeout=20)
    if j and 'data' in j:
        for p in _iter_params(j):
            k = p.get('index_item_key')
            opt = p.get('option_value')
            if not k or opt in (None, ''):
                continue
            if k not in dims:
                dims[k] = {'key': k, 'name': _fix_dim_name(cid, k, p.get('index_name') or k),
                           'raw': []}
                order.append(k)
            dims[k]['raw'].append((p.get('option_name'), str(opt)))

    filters = []
    for k in order:
        if not dims[k]['raw']:
            continue
        opts = _norm_options(dims[k]['raw'])
        if len(opts) <= 1:
            # 只有「全部」的维度没有意义，丢弃
            continue
        filters.append({'key': k, 'name': dims[k]['name'], 'value': opts})

    if not filters:
        filters = _fallback_filters(cid)

    # 排序维度置顶，其余保持接口下发顺序
    filters.sort(key=lambda f: 0 if f['key'] == _SORT_KEY else 1)
    _set(key, filters, 3600)
    _FILTER_CACHE[cid] = filters
    return filters


# 少数维度接口下发的 index_name 与实际含义不符，这里做显示名纠正
_NAME_FIX = {
    ('100150', 'all'): '主题',      # 少儿下发的「全部」实为内容主题集合
    ('100119', 'item'): '画风',
}


def _fix_dim_name(cid, key, name):
    return _NAME_FIX.get((str(cid), key), name)


def _fallback_filters(cid):
    fb = FALLBACK.get(str(cid))
    if not fb:
        return [{'key': _SORT_KEY, 'name': '排序',
                 'value': [{'n': '最热', 'v': _DEFAULT_SORT}]}]
    _, dim_list = fb
    out = []
    for k, n, vs in dim_list:
        opts = [{'n': a, 'v': b} for a, b in vs if a != n or b != '-1']
        if not opts:
            continue
        out.append({'key': k, 'name': n,
                    'value': [{'n': '全部', 'v': '-1'}] + opts})
    return out


def _valid_keys(cid):
    """当前分类下真正合法的维度名（不含 sort）"""
    try:
        ks = {d['key'] for d in _fetch_filters(cid)}
    except Exception:
        ks = set()
    ks.discard(_SORT_KEY)
    return ks


def _order_keys(cid):
    """按接口下发顺序返回维度名，用于拼接 filter_params"""
    try:
        return [d['key'] for d in _fetch_filters(cid) if d.get('key') != _SORT_KEY]
    except Exception:
        return []


# ============================ 搜索 ============================
def _do_search(key, pg):
    # 说明：腾讯搜索接口一次性返回全部结果，pagenum > 0 会返回空，
    # 因此这里始终取第 0 页，pg 仅作透传（搜索不支持翻页）。
    body = {
        'version': '24072901', 'clientType': 1, 'filterValue': '',
        'uuid': str(uuid.uuid4()), 'retry': 0, 'query': key,
        'pagenum': 0, 'pagesize': 30, 'queryFrom': 0,
        'searchDatakey': '', 'transInfo': '', 'isneedQc': True,
        'preQid': '', 'adClientInfo': '',
        'extraInfo': {'isNewMarkLabel': '1', 'multi_terminal_pc': '1'},
    }
    j = _post_json(SEARCH_API, body, timeout=20)
    out, seen = [], set()
    if not j:
        return out
    for box in (j.get('data', {}) or {}).get('areaBoxList', []) or []:
        for it in box.get('itemList', []) or []:
            doc = it.get('doc') or {}
            vi = it.get('videoInfo') or {}
            vid = doc.get('id') or vi.get('cid')
            if not vid or vid in seen:
                continue
            seen.add(vid)
            tagtxt = ''
            try:
                tag = vi.get('imgTag')
                if isinstance(tag, str) and tag.strip().startswith('{'):
                    t = json.loads(tag)
                    tagtxt = ((t.get('tag_4') or {}).get('text')
                              or (t.get('tag_2') or {}).get('text') or '')
            except Exception:
                pass
            out.append(_vod(vid, vi.get('title'), vi.get('imgUrl'),
                            tagtxt, vi.get('year') or '0'))
    return out


# ============================ 详情 ============================
def _first_item_params(data):
    """从详情响应里找第一个带标题的 item_params"""
    for p in _iter_params(data):
        if p.get('title') or p.get('mz_title'):
            return p
    return {}


def _fetch_intro(cid):
    body = {
        'page_params': {
            'req_from': 'web', 'cid': str(cid), 'vid': '', 'lid': '',
            'page_type': 'detail_operation', 'page_id': 'detail_page_introduction',
        },
        'has_cache': 1,
    }
    j = _post_json(DETAIL_API, body, timeout=20)
    info, actors = {}, []
    if not j or 'data' not in j:
        return info, actors
    try:
        p = _first_item_params(j['data'])
        info = {
            'name': _pick(p, 'title', 'mz_title'),
            'pic': _pick(p, 'new_pic_hz', 'new_pic_vt', 'image_url'),
            'year': _year_of(p),
            'area': _pick(p, 'area_name', 'areaName'),
            'type': _pick(p, 'sub_genre', 'genre'),
            'remark': _pick(p, 'holly_online_time', 'hotval'),
            'content': _pick(p, 'cover_description', 'description', 'content'),
        }
    except Exception as e:
        _log('详情介绍解析失败', repr(e)[:60])

    # 演员：从响应里任意位置找 star_list
    try:
        def _walk(n):
            if isinstance(n, dict):
                sl = n.get('star_list')
                if isinstance(sl, dict):
                    for s in sl.get('item_datas') or []:
                        nm = (s.get('item_params') or {}).get('name')
                        if nm and nm not in actors:
                            actors.append(nm)
                for v in n.values():
                    if isinstance(v, (dict, list)):
                        _walk(v)
            elif isinstance(n, list):
                for v in n:
                    if isinstance(v, (dict, list)):
                        _walk(v)
        _walk(j['data'])
    except Exception:
        pass
    return info, actors


def _collect_eps(data):
    """从一个 GetPageData 响应里抽出剧集项"""
    out = []
    try:
        md = data['module_list_datas'][-1]['module_datas'][-1]
        for it in md['item_data_lists']['item_datas']:
            iid = it.get('item_id')
            if not iid:
                continue
            p = it.get('item_params') or {}
            out.append({
                'id': str(iid),
                'title': _pick(p, 'union_title', 'play_title', 'title'),
                'trailer': str(p.get('is_trailer', '0')) in ('1', 'True', 'true'),
            })
    except Exception:
        pass
    return out


def _fetch_episodes(cid):
    key = 'E|' + str(cid)
    hit = _ck(key)
    if hit is not None:
        return hit

    base_pp = {
        'req_from': 'web_vsite', 'page_id': 'vsite_episode_list',
        'page_type': 'detail_operation', 'id_type': '1', 'page_size': '',
        'cid': str(cid), 'vid': '', 'lid': '', 'page_num': '',
        'page_context': '', 'detail_page_type': '1',
    }
    j = _post_json(DETAIL_API, {'page_params': dict(base_pp), 'has_cache': 1}, timeout=20)
    if not j or 'data' not in j:
        _set(key, [], 60)
        return []

    eps = _collect_eps(j['data'])

    # 多分段（长剧/综艺）：module_params.tabs 里带各段 page_context
    tabs = None
    try:
        tabs = (j['data']['module_list_datas'][-1]['module_datas'][-1]
                ['module_params'].get('tabs'))
        if isinstance(tabs, str):
            tabs = json.loads(tabs) if tabs.strip() else None
    except Exception:
        tabs = None

    if isinstance(tabs, list) and len(tabs) > 1:
        for t in tabs[1:]:
            pctx = t.get('page_context') if isinstance(t, dict) else None
            if not pctx:
                continue
            pp = dict(base_pp)
            pp['page_context'] = pctx
            jj = _post_json(DETAIL_API, {'page_params': pp, 'has_cache': 1}, timeout=20)
            if jj and 'data' in jj:
                eps.extend(_collect_eps(jj['data']))

    out, seen = [], set()
    for e in eps:
        if e['id'] in seen:
            continue
        seen.add(e['id'])
        out.append(e)
    _set(key, out, 600)
    return out


# ============================ Spider ============================
class Spider(_BaseSpider):

    def getName(self):
        return '腾讯视频'

    def init(self, extend=''):
        self.extend = extend or ''

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    # ---------- 首页：7 大分类 + 全部筛选维度 ----------
    def homeContent(self, filter):
        classes = [{'type_id': t, 'type_name': n} for n, t in CLASSES]
        filters = {}
        for _, tid in CLASSES:
            try:
                filters[tid] = _fetch_filters(tid)
            except Exception as e:
                _log('筛选获取失败', tid, repr(e)[:50])
                filters[tid] = _fallback_filters(tid)
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        try:
            return {'list': _fetch_videos('100113', 'sort=' + _DEFAULT_SORT, 1)[:30]}
        except Exception:
            return {'list': []}

    # ---------- 分类：全维度筛选 + 翻页 ----------
    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        tid = str(tid)
        ext = extend if isinstance(extend, dict) else {}

        # ---- 拼接筛选条件 ----
        parts = []
        sort_v = ext.get(_SORT_KEY) or _DEFAULT_SORT
        if str(sort_v) in ('', '-1', 'None'):
            sort_v = _DEFAULT_SORT
        parts.append('%s=%s' % (_SORT_KEY, sort_v))

        # 按接口下发顺序拼接其余维度；只放行本分类合法的维度
        valid = _valid_keys(tid)
        keys = [k for k in _order_keys(tid) if k in valid]
        # 兜底：接口不可用时按传入参数拼接
        if not keys:
            keys = [k for k in ext.keys()
                    if k != _SORT_KEY and str(ext.get(k)) not in ('', '-1', 'None')]
        for k in keys:
            v = ext.get(k)
            if v in (None, '', '-1', 'None'):
                continue
            parts.append('%s=%s' % (k, v))

        fp = '&'.join(parts)
        vods = _fetch_videos(tid, fp, pg)
        return {
            'list': vods,
            'page': pg,
            'pagecount': 9999 if len(vods) >= 15 else pg,
            'limit': 21,
            'total': 999999,
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg='1'):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if not key:
            return {'list': [], 'page': pg}
        return {'list': _do_search(key.strip(), pg), 'page': pg}

    # ---------- 详情 ----------
    def detailContent(self, array):
        if not array:
            return {'list': []}
        raw = str(array[0] if isinstance(array, list) else array)
        cid = raw.split('@')[0].strip()
        if not cid:
            return {'list': []}

        info, actors = _fetch_intro(cid)
        eps = _fetch_episodes(cid)

        main, trailer = [], []
        for idx, e in enumerate(eps):
            title = e['title'] or ''
            num = None
            m = re.search(r'第\s*(\d+)\s*集', title)
            if m:
                num = m.group(1)
            else:
                m2 = re.search(r'(\d+)\s*$', title)
                if m2:
                    num = m2.group(1)
            if num:
                label = '第%s集' % (num.zfill(2) if len(num) < 3 else num)
            else:
                label = title or ('第%d集' % (idx + 1))
            item = '%s$%s@%s' % (label, cid, e['id'])
            (trailer if e['trailer'] else main).append(item)

        names, urls = [], []
        if main:
            names.append('腾讯视频')
            urls.append('#'.join(main))
        if trailer:
            names.append('预告片')
            urls.append('#'.join(trailer))
        if not names:
            names.append('腾讯视频')
            urls.append('正片$%s@%s' % (cid, cid))

        vod = {
            'vod_id': cid,
            'vod_name': info.get('name') or '',
            'vod_pic': _fix_pic(info.get('pic') or ''),
            'vod_year': str(info.get('year') or '0'),
            'vod_area': info.get('area') or '',
            'vod_type': info.get('type') or '',
            'vod_actor': ','.join(actors),
            'vod_content': info.get('content') or '',
            'vod_remarks': info.get('remark') or '',
            'vod_play_from': '$$$'.join(names),
            'vod_play_url': '$$$'.join(urls),
        }
        return {'list': [vod]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        header = {'User-Agent': UA, 'Referer': HOST + '/'}
        pid = str(id or '')
        if '@' in pid:
            cid, vid = pid.split('@', 1)
        else:
            cid, vid = pid, pid
        if not cid:
            return {'parse': 0, 'playUrl': '', 'url': '', 'header': header}

        if vid and vid != cid:
            page_url = '%s/x/cover/%s/%s.html' % (HOST, cid, vid)
        else:
            page_url = '%s/x/cover/%s.html' % (HOST, cid)

        # parse=1 表示该地址需要解析（非直链），交由框架内置解析器处理
        return {
            'parse': 1,
            'playUrl': '',
            'url': page_url,
            'jx': 1,
            'header': header,
            'danmaku': 'http://127.0.0.1:9978/proxy?do=danmu&site=js&url=' + page_url,
        }


# ============================ 离线兜底数据 ============================
# 仅当接口完全不可用时启用；选项值均为实测的真实 option_value
# 结构: {分类ID: (分类名, [(参数名, 显示名, [(选项名, 真实值), ...]), ...])}
FALLBACK = {
    '100113': ('电视剧', [
        ('recommend', '推荐', [('美食题材','poi_00003510'), ('失忆','poi_00004435'), ('都市生活','poi_00003639'), ('闪婚','poi_00004451'), ('偶像爱情','poi_00003363'), ('职场剧','poi_00003312'), ('末日题材','poi_00003472'), ('仙侠','poi_00003348'), ('跨物种对决','poi_00004568'), ('契约恋爱','poi_00004507'), ('侦查追踪','poi_00004228'), ('身份顶替','poi_00004375'), ('系统流','poi_00004278'), ('商界风云','poi_00004381'), ('创业','poi_00004882'), ('东方玄幻','poi_00003596'), ('都市爱情','poi_00003641'), ('轻喜剧','poi_00003455'), ('探寻真相','poi_00004416'), ('古装爱情','poi_00003563'), ('家长里短','poi_00003540'), ('乡村爱情','poi_00004313'), ('末世生存','poi_00004529'), ('逆袭','poi_00004496'), ('乡村生活','poi_00004312'), ('超能力','poi_00004921'), ('婚姻生活','poi_00003610'), ('重来人生','poi_00004120'), ('战争传奇','poi_00003493'), ('都市奇幻','poi_00003588'), ('乡村题材','poi_00003410'), ('宅门风云','poi_00003292'), ('奇幻爱情','poi_00003396'), ('反转','poi_00004844'), ('亲情','poi_00004482,poi_00004198,poi_00004602'), ('甜虐爱情','poi_00003431'), ('女性题材','poi_00004517'), ('全部','-1')]),
        ('award', '获奖', [('金鹰奖','3'), ('飞天奖','2'), ('白玉兰奖','1'), ('奖项','-1')]),
        ('theater', '剧场', [('十分剧场','4'), ('萤火单元','3'), ('板凳单元','2'), ('X剧场','1')]),
        ('iyear', '年份', [('更早','9'), ('2010-2000','8'), ('2015-2011','7'), ('2020-2016','6'), ('2021','5'), ('2022','4'), ('2023','3'), ('2024','2'), ('2025','2025'), ('2026','2026'), ('即将上线','1')]),
        ('iarea', '地区', [('其他','9999'), ('日本','10'), ('韩国','5'), ('英国','1'), ('泰国','9'), ('美国','8'), ('中国台湾','4'), ('中国香港','14'), ('内地','0')]),
        ('ipay', '资费', [('会员','3'), ('限免','2'), ('免费','1')]),
        ('itype', '类型', [('IP改编','21'), ('民国','20'), ('刑侦','18'), ('现实','17'), ('革命','16'), ('权谋','15'), ('悬疑','14'), ('喜剧','13'), ('家庭','12'), ('军旅','11'), ('逆袭','19'), ('传奇','10'), ('竞技','9'), ('猎奇','8'), ('科幻','7'), ('古装','6'), ('武侠','5'), ('奇幻','4'), ('青春','3'), ('都市','2'), ('爱情','1')]),
        ('sort', '排序', [('高分好评','85'), ('最新上架','79'), ('最热','75')]),
    ]),
    '100173': ('电影', [
        ('characteristic', '院线/网络', [('获奖佳片','6'), ('粤语','9'), ('原声','8'), ('独播','5'), ('网络电影','2'), ('院线电影','1'), ('其他','-1')]),
        ('recommend_1', '细分类型', [('动作喜剧','poi_00003642'), ('青春片','poi_00003457'), ('中国香港','poi_00309009'), ('日本电影','poi_00309103'), ('亲情','poi_00004482'), ('奇幻喜剧','poi_00003458'), ('奇幻冒险','poi_00003395'), ('文艺片','poi_00003418'), ('合家欢','poi_00003555'), ('正邪对抗','poi_00004141'), ('科幻动作','poi_00003525'), ('友情','poi_00004242'), ('科幻冒险','poi_00003524'), ('黑色喜剧','poi_00004731'), ('动画电影','poi_00003595'), ('口碑佳作','poi_00004984,poi_00005054,poi_00004993'), ('高能推理','poi_00003627'), ('爱情喜剧','poi_00003660'), ('超能力','poi_00004921'), ('中国台湾','poi_00309106'), ('甜虐爱情','poi_00003464'), ('真实事件改编','poi_00003317'), ('视效炸裂','poi_00005034'), ('奇幻爱情','poi_00003396'), ('武侠江湖','poi_00004285,poi_00003355'), ('东方玄幻','poi_00003596'), ('全部','-1')]),
        ('producer', '出品方', [('开心麻花','12'), ('20世纪影业','11'), ('BBC','10'), ('光线','8'), ('华纳','7'), ('华谊','6'), ('环球','5'), ('迪士尼','4'), ('派拉蒙','3'), ('索尼','2'), ('腾讯出品','1'), ('出品','-1')]),
        ('recommend_2', '影人推荐', [('黄晓明','poi_00218065'), ('张译','poi_00262342'), ('王迅','poi_00262452'), ('李连杰','poi_00066707'), ('樊少皇','poi_00098511'), ('王宝强','poi_00082363'), ('惠英红','poi_00066580'), ('郭富城','poi_00053945'), ('刘青云','poi_00114655'), ('吴京','poi_00304777'), ('吴孟达','poi_00082366'), ('任达华','poi_00114686'), ('梁家辉','poi_00099216'), ('葛优','poi_00115025'), ('吴君如','poi_00053651'), ('周星驰','poi_00098650'), ('王晶','poi_00300945'), ('贾冰','poi_00304923'), ('洪金宝','poi_00114866'), ('马丽','poi_00240297'), ('吴镇宇','poi_00114400'), ('古天乐','poi_00053652'), ('马特·达蒙','poi_00099113'), ('刘德华','poi_00114921'), ('林家栋','poi_00088628'), ('成龙','poi_00098553'), ('张家辉','poi_00066654'), ('甄子丹','poi_00066646'), ('周润发','poi_00066710'), ('黄渤','poi_00066936'), ('周冬雨','poi_00066713'), ('舒淇','poi_00066697'), ('沈腾','poi_00218057'), ('吴彦祖','poi_00082511'), ('梁朝伟','poi_00054039'), ('方中信','poi_00066978'), ('陈小春','poi_00053579'), ('张曼玉','poi_00098903'), ('张学友','poi_00262813'), ('布拉德·皮特','poi_00098486'), ('影人','-1')]),
        ('iyear', '年份', [('其他','10'), ('80年代','9'), ('90年代','8'), ('2005-2000','7'), ('2010-2006','6'), ('2013-2011','5'), ('2014','4'), ('2015','3'), ('2016','2'), ('2017','1'), ('2018','2018'), ('2019','20'), ('2020','2020'), ('2021','2021'), ('2022','2022'), ('2023','2023'), ('2024','2024'), ('2025','2025'), ('2026','2026'), ('即将上线','999')]),
        ('iarea', '地区', [('其他','100033'), ('澳大利亚','21'), ('意大利','20'), ('西班牙','19'), ('加拿大','18'), ('德国','17'), ('法国','16'), ('英国','15'), ('印度','100030'), ('泰国','100031'), ('韩国','100028'), ('日本','100027'), ('美国','100029'), ('中国台湾','100026'), ('中国香港','100025'), ('内地','100024')]),
        ('ipay', '免费/VIP', [('付费','4'), ('会员','8'), ('免费','1'), ('资费','-1')]),
        ('itype', '类型', [('青春','26'), ('灾难','25'), ('悬疑','10'), ('战争','8'), ('动画','15'), ('恐怖','11'), ('冒险','7'), ('犯罪','6'), ('科幻','12'), ('爱情','5'), ('喜剧','3'), ('动作','4')]),
        ('sort', '排序', [('高分好评','81'), ('最新','83'), ('最热','75')]),
    ]),
    '100109': ('综艺', [
        ('recommend_3', '明星推荐', [('胡夏','poi_00283886'), ('郑恺','poi_00283687'), ('杨幂','poi_00082402'), ('刘宇','poi_00207343'), ('沈腾','poi_00218057'), ('张大大','poi_00283944'), ('柳岩','poi_00218377'), ('岳云鹏','poi_00283787'), ('李雪琴','poi_00262797'), ('蔡明','poi_00304848'), ('李宇春','poi_00240221'), ('杜海涛','poi_00283905'), ('王祖蓝','poi_00240333'), ('毛不易','poi_00217967'), ('希林娜依·高','poi_00283400'), ('张远','poi_00262491'), ('张杰','poi_00304944'), ('魏大勋','poi_00082371'), ('范丞丞','poi_00304895'), ('杨迪','poi_00066715'), ('陈赫','poi_00240431'), ('徐志胜','poi_00325852'), ('沙溢','poi_00217999'), ('孟子义','poi_00066942'), ('周深','poi_00262812'), ('宋小宝','poi_00262456'), ('关晓彤','poi_00114918'), ('汪苏泷','poi_00218332'), ('杨超越','poi_00262429'), ('贾玲','poi_00283684'), ('大张伟','poi_00283791'), ('欧阳娜娜','poi_00262821'), ('刘宇宁','poi_00240161'), ('李晨','poi_00053566'), ('邓超','poi_00098551'), ('鹿晗','poi_00240432'), ('李诞','poi_00240354'), ('周震南','poi_00240344'), ('金靖','poi_00284425'), ('明星','-1')]),
        ('iyear', '年份', [('更早','99'), ('2010','2010'), ('2011','2011'), ('2012','2012'), ('2013','6'), ('2014','5'), ('2015','4'), ('2016','3'), ('2017','2'), ('2018','1'), ('2019','7'), ('2020','50'), ('2021','2021'), ('2022','2022'), ('2023','2023'), ('2024','2024'), ('2025','2025'), ('2026','2026')]),
        ('iarea', '地区', [('海外','2'), ('国内','1')]),
        ('exclusive', '自制/独播', [('独播','2'), ('腾讯自制','1'), ('出品','-1')]),
        ('ipay', '资费', [('会员','6'), ('免费','1')]),
        ('itype', '类型', [('资讯','7'), ('晚会','6'), ('互动','23'), ('文化','26'), ('亲子','17'), ('访谈','3'), ('推理','25'), ('电竞','15'), ('影视','16'), ('竞技','24'), ('潮流运动','21'), ('美食','19'), ('喜剧','14'), ('职场','20'), ('生活','22'), ('情感','12'), ('音乐舞台','11'), ('脱口秀','2'), ('游戏','10')]),
        ('sort', '排序', [('高分好评','85'), ('最近更新','23'), ('最热','75')]),
    ]),
    '100105': ('纪录片', [
        ('recommend', '推荐', [('野外生存','poi_00004256'), ('社会话题','poi_00003444'), ('人生百态','poi_00004467'), ('历史研究','poi_00004559'), ('动物家族','poi_00004788'), ('自然环境','poi_00004114'), ('战争史','poi_00381870'), ('访谈节目','poi_00003575'), ('考古发掘','poi_00002949'), ('名人访谈','poi_00003505'), ('世界史','poi_00004427'), ('天文学','poi_00004351'), ('地域文化','poi_00004795'), ('未解之谜','poi_00004331'), ('宇宙探秘','poi_00004171'), ('中国史','poi_00004211'), ('人物故事','poi_00003387'), ('动物研究','poi_00004856'), ('动物世界','poi_00004857'), ('历史科普','poi_00004561'), ('动物行为','poi_00004789'), ('科技发展','poi_00004648'), ('动物科普','poi_00004787'), ('冷知识','poi_00343602'), ('口碑佳作','poi_00004984'), ('美食制作','poi_00004548'), ('人文风貌','poi_00004462'), ('传统文化','poi_00004910'), ('风土人情','poi_00004765'), ('文学品读','poi_00004327'), ('文物','poi_00004328'), ('地方美食','poi_00004868'), ('饮食文化','poi_00004182'), ('袒露心声','poi_00343449'), ('风景欣赏','poi_00004767'), ('人物传记','poi_00003388'), ('动物生存','poi_00004858'), ('中国文化','poi_00004127'), ('行业揭秘','poi_00004807'), ('生活纪实','poi_00003376'), ('为你推荐','-1')]),
        ('iyear', '年份', [('更早','9'), ('2009-2005','8'), ('2014-2010','7'), ('2019-2015','6'), ('2020','5'), ('2021','4'), ('2022','3'), ('2023','2'), ('2024','1'), ('2025','2025'), ('2026','2026')]),
        ('pay', '资费', [('限免','3'), ('会员','2'), ('免费','1')]),
        ('iregion', '地区', [('国外','2'), ('国内','1'), ('地区','0')]),
        ('itype', '分类', [('旅游','11'), ('竞技','12'), ('罪案','7'), ('探险','15'), ('财经','14'), ('科技','8'), ('军事','2'), ('历史','1'), ('人文','6'), ('社会','3'), ('美食','10'), ('自然','4'), ('类型','-1')]),
        ('itrailer', '出品机构', [('历史频道','7'), ('ITV','3530'), ('NHK','2'), ('HBO','3175'), ('探索频道','3174'), ('国家地理','4'), ('BBC','1'), ('央视','8'), ('腾讯出品','15'), ('出品','-1')]),
        ('sort', '排序', [('高分好评','85'), ('最新','74'), ('最热','75')]),
    ]),
    '100119': ('动漫', [
        ('item', '3D/2D', [('其他','5'), ('特摄','4'), ('2D动画','3'), ('3D动画','2'), ('画风','1')]),
        ('anime_status', '连载/完结', [('已完结','45'), ('更新中','44'), ('即将上线','46'), ('状态','-1')]),
        ('iyear', '年份', [('更早','10'), ('80年代','9'), ('90年代','8'), ('00年代','7'), ('2011','6'), ('2012','5'), ('2013','4'), ('2014','3'), ('2015','2'), ('2016','1'), ('2017','2017'), ('2018','2018'), ('2019','11'), ('2020','50'), ('2021','2021'), ('2022','2022'), ('2023','2023'), ('2024','2024'), ('2025','2025'), ('2026','2026')]),
        ('itype', '类型', [('其他','12'), ('音乐','32'), ('美食','31'), ('恐怖','30'), ('智斗','29'), ('古风','28'), ('历史','19'), ('异能','27'), ('游戏','26'), ('治愈','25'), ('真人','18'), ('日常','15'), ('竞技','20'), ('悬疑','17'), ('冒险','2'), ('搞笑','1'), ('恋爱','7'), ('都市','24'), ('仙侠','23'), ('武侠','13'), ('奇幻','21'), ('科幻','4'), ('玄幻','9')]),
        ('ipay', '免费/VIP', [('会员','6'), ('免费','867'), ('资费','-1')]),
        ('iarea', '地区', [('其他','4'), ('欧美','3'), ('日本','2'), ('内地','1')]),
        ('sort', '排序', [('高分好评','85'), ('最近更新','23'), ('最热','75')]),
    ]),
    '100150': ('少儿', [
        ('child_ip', '动画明星', [('小马宝莉','13'), ('开心超人','12'), ('叶罗丽','11'), ('芭比','10'), ('海绵宝宝','9'), ('猫和老鼠','8'), ('舒克贝塔','7'), ('米奇','14'), ('米小圈','6'), ('乐迪','5'), ('喜羊羊','4'), ('猪猪侠','3'), ('汪汪队','2'), ('小猪佩奇','1')]),
        ('language', '语言', [('英文版','1'), ('普通话版','3')]),
        ('gender', '性别', [('男孩','2'), ('女孩','1')]),
        ('itype', '类型', [('动画电影','20'), ('家长甄选','17'), ('真人·特摄','14'), ('动物','13'), ('魔幻·科幻','12'), ('玩具','4'), ('益智早教','2'), ('交通工具','11'), ('儿歌','1'), ('冒险','10'), ('涨知识','23'), ('磨耳朵','22')]),
        ('ipay', '免费/VIP', [('会员','2'), ('免费','1'), ('资费','-1')]),
        ('all', '全部', [('学科内容','24'), ('优质佳作','26'), ('搞笑','25'), ('国学','11'), ('创意玩耍','8'), ('英语','15'), ('科普','23'), ('童年记忆','22'), ('真人剧','21'), ('动画','20'), ('德智体','19'), ('早教','7'), ('百科','13'), ('汽车','5'), ('颜色','4'), ('绘本·故事','3'), ('儿歌·童谣','2'), ('情商教育','17'), ('行为习惯','14'), ('安全','12'), ('玩具节目','10'), ('恐龙','6'), ('出行工具','16'), ('幼小衔接','18'), ('入园','9'), ('叫早·哄睡','1')]),
        ('iyear', '年龄', [('全年龄','7'), ('10岁以上','4'), ('7-9岁','3'), ('4-6岁','2'), ('0-3岁','1')]),
        ('sort', '排序', [('最新','76'), ('最热','75')]),
    ]),
    '110755': ('短剧', [
        ('attraction', '主要看点', [('脑洞','89'), ('娱乐圈','88'), ('恐怖','49'), ('权力争夺','47'), ('虐渣复仇','29'), ('追妻','25'), ('身份之谜','23'), ('家族恩怨','22'), ('宅门风云','21'), ('亲情','20'), ('传承觉醒','19'), ('系统流','16'), ('闪婚','15'), ('奇幻爱情','13'), ('甜宠爱情','12'), ('异能','11'), ('马甲','10'), ('破镜重圆','9'), ('曲折爱情','8'), ('虐心','7'), ('家庭伦理','6'), ('逆袭','5'), ('重生','4'), ('穿越','3')]),
        ('identity', '身份人设', [('团宠','29'), ('小人物','28'), ('大叔','24'), ('欢喜冤家','16'), ('青梅竹马','13'), ('皇后王妃','11'), ('女帝','10'), ('大男主','9'), ('神豪','8'), ('赘婿','7'), ('落难千金','6'), ('神医','5'), ('萌娃','4'), ('战神','3'), ('大女主','2'), ('总裁','1')]),
        ('story', '故事背景', [('喜剧','21'), ('玄幻','19'), ('悬疑推理','18'), ('乡村','15'), ('末日','12'), ('民国','11'), ('职场','10'), ('青春','8'), ('年代','6'), ('古装权谋','5'), ('都市奇幻','3'), ('都市爱情','2'), ('古装爱情','1')]),
        ('prefer', '偏好', [('女频','1'), ('男频','2')]),
        ('sort', '排序', [('限免中','90'), ('最新上架','76'), ('最热','75')]),
    ]),
}
