# -*- coding: utf-8 -*-
"""
腾讯视频 TVBox / 影视仓 Python 爬虫源
==================================================
站点: https://v.qq.com
接口: https://pbaccess.video.qq.com  (腾讯视频官方 Web 端公开接口)

覆盖: 8 大分类 × 各分类完整筛选维度 + 多页翻页 + 搜索 + 详情 + 播放

【接口清单】
  分类列表  POST /trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData
              ?video_appid=1000005&vplatform=2&vversion_name=8.9.10&new_mark_label_enabled=1
              page_params.page_id = channel_list_second_page
              ├─ 不传 page  → 返回该分类的全部筛选维度(sort/itype/iarea/iyear...)
              └─ 传   page  → 返回该分类第 N 页影片列表(每页 21 条)
              筛选靠 filter_params 拼接, 形如 "sort=75&itype=6&iarea=8"
              ⚠ 筛选值必须用接口下发的原始值(option_value), 各分类之间不通用
  搜索      POST /trpc.videosearch.mobile_search.MultiTerminalSearch/MbSearch?vplatform=2
  详情介绍  POST .../GetPageData?video_appid=3000010&vplatform=2&vversion_name=8.2.96
              page_id = detail_page_introduction
  剧集列表  POST .../GetPageData?video_appid=3000010&vplatform=2&vversion_name=8.2.96
              page_id = vsite_episode_list   (携带 module_params.tabs 处理多分段)
  播放      https://v.qq.com/x/cover/{cid}/{vid}.html  → 交给框架内置解析(jx=1)

【播放说明(实测)】
  腾讯正版片源受 DRM 保护, 无明文直链, 只能由 App 打开播放页播放。
  播放页前贴广告与正片复用同一个 <video> 元素(实测: 先播 15s/25s/51s 广告,
  约 1-2 分钟后正片在同一元素续播 2575s)。若 App 把广告的 ended 事件误判为
  本集播完, 会提示"已经是最后一集"。应对:
    1) 关闭 App 的"播放完自动下一集", 让 WebView 留在页面等正片续播;
    2) 播放方式选"网页/网页播放", 不要用会抓第一个 video 的嗅探模式;
    3) 在 ext 里配置腾讯视频登录 Cookie( {"cookie":"..."} ) —— 免前贴广告
       并解锁会员正片, 从根源避免误判(最稳, 见 _set_cookie)。

仅供学习交流, 请勿用于商业用途。
"""

import json
import time
import uuid
import gzip
import re
import ssl
import urllib.request

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider(object):
        pass

try:
    import requests as _requests
except Exception:
    _requests = None

# ============================ 常量 ============================
API = 'https://pbaccess.video.qq.com'
HOST = 'https://v.qq.com'

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')

HEADERS = {
    'User-Agent': UA,
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Content-Type': 'application/json',
    'Origin': HOST,
    'Referer': HOST + '/',
}

# 列表接口用 appid=1000005, 详情接口用 appid=3000010
LIST_API = (API + '/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData'
            '?video_appid=1000005&vplatform=2&vversion_name=8.9.10&new_mark_label_enabled=1')
DETAIL_API = (API + '/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData'
              '?video_appid=3000010&vplatform=2&vversion_name=8.2.96')
SEARCH_API = API + '/trpc.videosearch.mobile_search.MultiTerminalSearch/MbSearch?vplatform=2'

# 全部分类(腾讯视频频道 ID, 2026-10 实测)
CLASSES = [
    ('电影', '100173'),
    ('电视剧', '100113'),
    ('综艺', '100109'),
    ('动漫', '100119'),
    ('纪录片', '100105'),
    ('少儿', '100150'),
    ('短剧', '110755'),
    ('短番', '120178'),
]

# 每页条数(接口固定返回 21 条)
PAGE_SIZE = 21
# 首页推荐默认分类
HOME_CHANNEL = '100173'

# 筛选维度极简兜底(仅当接口完全不可用时使用; 值均取自实测的真实 option_value)
# 格式: (参数名, 显示名, [(选项名, 真实值), ...])
_BASE_SORT = ('sort', '排序', [('最热', '75'), ('最新', '83'), ('高分好评', '81')])

# 电影 + 电视剧的「类型」合并选项池(去重)
_ALL_ITYPE = [
    ('全部', '-1'),
    # —— 电视剧类型 ——
    ('爱情', '1'), ('都市', '2'), ('青春', '3'), ('奇幻', '4'), ('武侠', '5'),
    ('古装', '6'), ('科幻', '7'), ('猎奇', '8'), ('竞技', '9'), ('传奇', '10'),
    ('军旅', '11'), ('家庭', '12'), ('喜剧', '13'), ('悬疑', '14'), ('权谋', '15'),
    ('革命', '16'), ('现实', '17'), ('刑侦', '18'), ('逆袭', '19'), ('民国', '20'),
    ('IP改编', '21'),
    # —— 电影类型 ——
    ('动作', '4'), ('犯罪', '6'), ('冒险', '7'), ('战争', '8'), ('恐怖', '11'),
    ('动画', '15'), ('灾难', '25'),
]

# 电影年份兜底
_FILM_YEAR = [('全部', '-1'), ('即将上线', '999'), ('2026', '2026'), ('2025', '2025'),
              ('2024', '2024'), ('2023', '2023'), ('2022', '2022'), ('2021', '2021'),
              ('2020', '2020'), ('2019', '20'), ('2018', '2018'), ('2017', '1'),
              ('2016', '2'), ('2015', '3'), ('2014', '4'), ('2013-2011', '5'),
              ('2010-2006', '6'), ('2005-2000', '7'), ('90年代', '8'), ('80年代', '9'),
              ('其他', '10')]

FALLBACK_FILTERS = {
    '100113': [_BASE_SORT,
               ('itype', '类型', _ALL_ITYPE),
               ('ipay', '资费', [('全部', '-1'), ('免费', '1'), ('限免', '2'), ('会员', '3')]),
               ('iarea', '地区', [('全部', '-1'), ('内地', '0'), ('英国', '1'), ('中国台湾', '4'),
                                  ('韩国', '5'), ('美国', '8'), ('泰国', '9'), ('日本', '10'),
                                  ('中国香港', '14'), ('其他', '9999')]),
               ('iyear', '上映时间', [('全部', '-1'), ('即将上线', '1'), ('2026', '2026'),
                                      ('2025', '2025'), ('2024', '2'), ('2023', '3'),
                                      ('2022', '4'), ('2021', '5'), ('2020-2016', '6'),
                                      ('2015-2011', '7'), ('2010-2000', '8'), ('更早', '9')])],
    '100173': [_BASE_SORT,
               ('itype', '类型', _ALL_ITYPE),
               ('ipay', '资费', [('全部', '-1'), ('免费', '1'), ('付费', '4'), ('会员', '8')]),
               ('iarea', '地区', [('全部', '-1'), ('内地', '100024'), ('中国香港', '100025'),
                                  ('中国台湾', '100026'), ('日本', '100027'), ('韩国', '100028'),
                                  ('美国', '100029'), ('英国', '15'), ('法国', '16'),
                                  ('印度', '100030'), ('泰国', '100031')]),
               ('iyear', '上映时间', _FILM_YEAR)],
    '100109': [_BASE_SORT, ('itype', '类型', [('全部', '-1')]),
               ('ipay', '资费', [('全部', '-1'), ('免费', '1'), ('会员', '3')]),
               ('iarea', '地区', [('全部', '-1')])],
    '100119': [_BASE_SORT, ('itype', '类型', [('全部', '-1')]),
               ('iarea', '地区', [('全部', '-1')]),
               ('anime_status', '状态', [('全部', '-1'), ('即将上线', '1'),
                                          ('更新中', '2'), ('已完结', '3')])],
    '100105': [_BASE_SORT, ('itype', '类型', [('全部', '-1')]),
               ('iregion', '地区', [('全部', '-1')])],
    '100150': [_BASE_SORT, ('itype', '类型', [('全部', '-1')]),
               ('gender', '性别', [('全部', '-1'), ('女孩', '1'), ('男孩', '2')])],
    '110755': [_BASE_SORT, ('prefer', '偏好', [('全部', '-1'), ('男频', '1'), ('女频', '2')])],
    '120178': [_BASE_SORT, ('itype', '题材', [('全部', '-1')])],
}

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

_CACHE = {}
_FILTER_CACHE = {}
_FILTER_LOCK = {}

# 腾讯视频登录 Cookie(可选): 配置后免前贴广告 + 解锁会员正片
_COOKIE = ''


def _log(*a):
    try:
        print('[腾讯视频]', *[str(x) for x in a])
    except Exception:
        pass


# ============================ HTTP ============================
def _http(url, data=None, method='GET', timeout=15, tries=2):
    body = data.encode('utf-8') if isinstance(data, str) else data
    h = dict(HEADERS)
    h['Accept-Encoding'] = 'gzip'
    # requests 优先(连接复用更快), 失败时回退 urllib
    if _requests is not None:
        for i in range(tries):
            try:
                if method == 'POST':
                    r = _requests.post(url, data=body, headers=h, timeout=timeout)
                else:
                    r = _requests.get(url, headers=h, timeout=timeout)
                if r.status_code == 200:
                    return r.text
                _log('%s HTTP %s(%d/%d)' % (method, r.status_code, i + 1, tries), url[:70])
            except Exception as e:
                _log('%s 失败(%d/%d)' % (method, i + 1, tries), url[:70], repr(e)[:60])
            time.sleep(0.3)
        return ''
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=h, method=method)
            resp = urllib.request.urlopen(req, timeout=timeout, context=_CTX)
            raw = resp.read()
            if raw[:2] == b'\x1f\x8b':
                raw = gzip.decompress(raw)
            return raw.decode('utf-8', 'ignore')
        except Exception as e:
            _log('%s 失败(%d/%d)' % (method, i + 1, tries), url[:70], repr(e)[:60])
            time.sleep(0.3)
    return ''


def _post_json(url, obj, timeout=15, tries=2):
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
        _CACHE.clear()
    _CACHE[key] = (time.time() + ttl, val)


# ============================ Cookie(可选) ============================
def _set_cookie(extend):
    """从 init(extend) 解析腾讯视频登录 Cookie

    支持三种写法(空值表示清除):
      {"cookie":"vqq_vusession=xxx; ..."}    JSON 对象
      vqq_vusession=xxx; ...                 裸 Cookie 字符串
      dict                                   Python 字典
    配置后可免前贴广告并解锁会员正片。抓取方法: 浏览器登录 v.qq.com 后,
    F12 → Network → 任一请求 → Request Headers → 复制 Cookie 整串。
    """
    global _COOKIE
    ck = ''
    if extend:
        if isinstance(extend, dict):
            ck = extend.get('cookie') or extend.get('Cookie') or ''
        else:
            s = str(extend).strip()
            if s.startswith('{'):
                try:
                    d = json.loads(s)
                    if isinstance(d, dict):
                        ck = d.get('cookie') or d.get('Cookie') or ''
                except Exception:
                    ck = ''
            elif '=' in s:
                ck = s
    _COOKIE = _clean(ck)
    if _COOKIE:
        HEADERS['Cookie'] = _COOKIE
    elif 'Cookie' in HEADERS:
        del HEADERS['Cookie']


# ============================ 解析工具 ============================
def _clean(s):
    if s is None:
        return ''
    s = str(s)
    return re.sub(r'<[^>]+>', '', s).replace('&nbsp;', ' ').strip()


def _iter_params(node):
    """深度遍历 JSON, 产出所有 item_params / params 字典"""
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
    return url


def _pick(d, *keys):
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return ''


def _vod(cid, name, pic, remark='', year=''):
    return {
        'vod_id': str(cid),
        'vod_name': name or '',
        'vod_pic': _fix_pic(pic),
        'vod_remarks': str(remark or ''),
        'vod_year': str(year or ''),
    }


# ============================ 分类列表 ============================
def _list_body(cid, filter_params, page=None):
    pp = {
        'channel_id': str(cid),
        'filter_params': filter_params or 'sort=75',
        'page_type': 'channel_operation',
        'page_id': 'channel_list_second_page',
        'page_context': '',
    }
    # 关键: 传 page 才返回影片列表; 不传则返回筛选维度
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
            # 列表条目特征: 带封面图或标题
            if not (p.get('new_pic_hz') or p.get('new_pic_vt') or p.get('title')):
                continue
            seen.add(vid)
            rm = _pick(p, 'holly_online_time', 'hotval', 'second_title')
            vods.append(_vod(
                vid,
                _clean(_pick(p, 'mz_title', 'title')),
                _pick(p, 'new_pic_hz', 'new_pic_vt', 'image_url'),
                _clean(rm) if len(str(rm)) <= 24 else '',
                _pick(p, 'year'),
            ))
    _set(key, vods, 300 if vods else 60)
    return vods


def _fetch_filters(cid):
    """取某分类完整筛选维度(不传 page 时接口返回)"""
    cid = str(cid)
    if cid in _FILTER_CACHE:
        return _FILTER_CACHE[cid]
    key = 'F|' + cid
    hit = _ck(key)
    if hit is not None:
        _FILTER_CACHE[cid] = hit
        return hit

    dims, order = {}, []
    j = _post_json(LIST_API, _list_body(cid, 'sort=75', None), timeout=20)
    if j and 'data' in j:
        for p in _iter_params(j):
            k = p.get('index_item_key')
            opt = p.get('option_value')
            if not k or opt in (None, ''):
                continue
            opt = str(opt)
            if k not in dims:
                dims[k] = {'key': k, 'name': p.get('index_name') or k, 'value': []}
                order.append(k)
            if not any(x['v'] == opt for x in dims[k]['value']):
                dims[k]['value'].append({'n': _clean(p.get('option_name')) or opt, 'v': opt})

    filters = [dims[k] for k in order if dims[k]['value']] if dims else []
    if not filters:
        filters = [{'key': k, 'name': n, 'value': [{'n': a, 'v': b} for a, b in vs]}
                   for k, n, vs in FALLBACK_FILTERS.get(cid, [])]
    filters = _expand_itype(cid, filters)
    filters = _rename_year(filters)
    _set(key, filters, 3600)
    _FILTER_CACHE[cid] = filters
    return filters


def _rename_year(filters):
    """把「年份」显示名改为「上映时间」(便于按上映年份筛电影)"""
    out = []
    for f in filters:
        if f.get('key') == 'iyear' or f.get('name') == '年份':
            f = dict(f)
            f['name'] = '上映时间'
        out.append(f)
    return out


def _expand_itype(cid, filters):
    """为电影/电视剧的「类型」维度补充分类未下发、但同参数可用的类型选项"""
    if str(cid) not in ('100113', '100173'):
        return filters
    out = []
    for f in filters:
        if f.get('key') == 'itype':
            have = {x['n'] for x in f['value']}
            merged = list(f['value'])
            for n, v in _ALL_ITYPE:
                if n in have:
                    continue
                if any(x['v'] == v and x['n'] != n for x in merged):
                    continue
                merged.append({'n': n, 'v': v})
            out.append({'key': 'itype', 'name': f.get('name') or '类型', 'value': merged})
        else:
            out.append(f)
    return out


def _valid_keys(cid):
    ks = {d['key'] for d in _fetch_filters(cid)}
    ks.discard('sort')
    return ks


def _pick_filter_json(filter, extend):
    """兼容各框架: 筛选 JSON 可能在 filter(DRPy2/HiPy 部分分支) 或 extend(FongMi 官方)"""
    for v in (filter, extend):
        if isinstance(v, str) and v.strip().startswith('{'):
            return v
        if isinstance(v, dict):
            return v
    return ''


def _norm_extend(filter, extend, cid):
    """把框架回传的筛选整理成 {原始key: option_value}

    - extend 为 dict(标准) -> 直接用
    - extend/filter 为 JSON 字符串 -> 解析
    - 键可能是显示名(如"上映时间"/"地区") -> 换算回原始 key
    - 值可能是选项名(如"中国大陆") -> 换算回 option_value
    """
    v = extend if isinstance(extend, dict) else None
    if v is None:
        s = _pick_filter_json(filter, extend)
        if isinstance(s, str) and s.strip().startswith('{'):
            try:
                v = json.loads(s)
            except Exception:
                v = None
        elif isinstance(s, dict):
            v = s
    if not isinstance(v, dict) or not v:
        return {}

    raw = dict(v)

    # 显示名 -> 原始 key, 同时建立 key -> 选项表
    name2key, key_opts = {}, {}
    try:
        for f in _fetch_filters(cid):
            k = f.get('key')
            name2key.setdefault(f.get('name') or k, k)
            name2key.setdefault(k, k)
            key_opts[k] = f.get('value') or []
            if k == 'iyear':
                name2key.setdefault('年份', 'iyear')
                name2key.setdefault('上映时间', 'iyear')
    except Exception:
        pass

    out = {}
    for k, val in raw.items():
        val = '' if val is None else str(val).strip()
        if val in ('', '-1', 'None', '全部'):
            continue
        key = name2key.get(k, k)
        opts = key_opts.get(key)
        if opts:                       # 有该维度选项表: 校验并按需换算
            vals = {o['v'] for o in opts}
            if val not in vals:
                for o in opts:
                    if o['n'] == val:
                        val = o['v']
                        break
                else:
                    continue           # 无效选项, 丢弃(避免非法参数污染请求)
        if val in ('', '-1'):
            continue
        out[key] = val
    return out


# ============================ 搜索 ============================
def _do_search(key, pg):
    # 说明: 腾讯搜索接口一次性返回全部结果(pagesize 调大也不会变),
    # pagenum > 0 会返回空, 因此这里始终取第 0 页, pg 仅作透传。
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
            vid = doc.get('id')
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
            out.append(_vod(vid, _clean(vi.get('title')), vi.get('imgUrl'), tagtxt, vi.get('year')))
    return out


# ============================ 详情 ============================
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
        first = (j['data']['module_list_datas'][0]['module_datas'][0]
                 ['item_data_lists']['item_datas'][0])
        p = first.get('item_params') or {}
        info = {
            'name': _clean(_pick(p, 'title', 'mz_title')),
            'pic': _pick(p, 'new_pic_hz', 'new_pic_vt', 'image_url'),
            'year': _pick(p, 'year', 'cover_year'),
            'area': _clean(_pick(p, 'area_name', 'areaName')),
            'type': _clean(_pick(p, 'sub_genre', 'main_genres')),
            'remark': _clean(_pick(p, 'holly_online_time', 'hotval')),
            'content': _clean(_pick(p, 'cover_description', 'description')),
        }
        for s in ((first.get('sub_items') or {}).get('star_list', {})
                  .get('item_datas', []) or []):
            nm = _clean((s.get('item_params') or {}).get('name'))
            if nm and nm not in actors:
                actors.append(nm)
    except Exception as e:
        _log('详情介绍解析失败', repr(e)[:60])
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
                'title': _clean(_pick(p, 'union_title', 'play_title', 'title')),
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

    # 多分段(长剧/综艺): module_params.tabs 里带各段 page_context
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
        _set_cookie(extend)

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    # ---------- 首页: 8 大分类 + 全部筛选维度 ----------
    def homeContent(self, filter):
        classes = [{'type_id': t, 'type_name': n} for n, t in CLASSES]
        filters = {}
        for _, tid in CLASSES:
            try:
                filters[tid] = _fetch_filters(tid)
            except Exception as e:
                _log('筛选取失败', tid, repr(e)[:50])
                filters[tid] = [{'key': k, 'name': n,
                                 'value': [{'n': a, 'v': b} for a, b in vs]}
                                for k, n, vs in FALLBACK_FILTERS.get(tid, [])]
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        # 首页推荐: 电影频道"最新"(按上映时间), 方便找新片
        try:
            v = _fetch_videos(HOME_CHANNEL, 'sort=83', 1)
            if not v:
                v = _fetch_videos(HOME_CHANNEL, 'sort=75', 1)
            return {'list': v[:30]}
        except Exception:
            return {'list': []}

    # ---------- 分类: 全维度筛选 + 翻页 ----------
    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        tid = str(tid)

        ext = _norm_extend(filter, extend, tid)

        parts = []
        sort_v = ext.pop('sort', None) or '75'
        if str(sort_v) in ('', '-1', 'None'):
            sort_v = '75'
        parts.append('sort=' + str(sort_v))

        # 只用该分类下发的合法维度, 避免非法参数污染请求
        try:
            keys = _valid_keys(tid)
        except Exception:
            keys = set()
        for k in sorted(keys):
            v = ext.get(k)
            if v in (None, '', '-1', 'None'):
                continue
            parts.append('%s=%s' % (k, v))

        vods = _fetch_videos(tid, '&'.join(parts), pg)
        return {
            'list': vods,
            'page': pg,
            'pagecount': 9999 if len(vods) >= 5 else pg,
            'limit': PAGE_SIZE,
            'total': 999999,
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg='1'):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if not key:
            return {'list': [], 'page': pg, 'pagecount': 1}
        # 搜索接口只返回一页(pagenum>0 恒为空), 固定 pagecount=1
        return {'list': _do_search(_clean(key), pg), 'page': pg, 'pagecount': 1}

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
        for e in eps:
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
                label = title or ('第%d集' % (len(main) + len(trailer) + 1))
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
            'vod_year': str(info.get('year') or ''),
            'vod_area': info.get('area') or '',
            'vod_type': info.get('type') or '',
            'type_name': info.get('type') or '',
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
        if _COOKIE:
            header['Cookie'] = _COOKIE      # VIP 登录态: 免贴片广告 + 会员正片
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

        # jx=1: 交给框架内置解析器打开播放页(与主流腾讯源一致),
        # 比 parse=1 更适配各 App 的播放流程; 播放页广告与正片复用同一
        # video 元素, 配置 Cookie 可免广告(见文件头部说明)。
        return {
            'parse': 0,
            'playUrl': '',
            'url': page_url,
            'jx': 1,
            'header': header,
        }


# 单例 + 模块级函数(兼容旧式函数加载的框架)
_spider = Spider()


def init(extend=''):
    return _spider.init(extend)


def homeContent(filter=False):
    return _spider.homeContent(filter)


def homeVideoContent():
    return _spider.homeVideoContent()


def categoryContent(tid, pg, filter, extend):
    return _spider.categoryContent(tid, pg, filter, extend)


def detailContent(ids):
    return _spider.detailContent(ids)


def playerContent(flag, id, vipFlags):
    return _spider.playerContent(flag, id, vipFlags)


def searchContent(key, quick, pg='1'):
    return _spider.searchContent(key, quick, pg)


# ---------------------------------------------------------------------------
# 本地测试入口: python3 tx_spider.py
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    s = Spider()

    print('===== 1. 分类 + 筛选维度 =====')
    h = s.homeContent(True)
    print('分类:', ' / '.join(c['type_name'] for c in h['class']))
    for cid in ['100173', '100113']:
        fs = h['filters'].get(cid) or []
        print('[%s] 筛选维度:' % cid, ', '.join('%s(%d项)' % (f['name'], len(f['value'])) for f in fs))
        for f in fs:
            if f['name'] == '上映时间':
                print('   上映时间:', ' '.join(o['n'] for o in f['value'][:14]), '...')

    print()
    print('===== 2. 电影 + 2025年上映 + 最新排序 =====')
    r = s.categoryContent('100173', '1', False, {'sort': '83', 'iyear': '2025'})
    print('第1页: %s 条 (pagecount=%s)' % (len(r['list']), r['pagecount']))
    for v in r['list'][:5]:
        print('   -', v['vod_name'], '|', v['vod_year'], '|', v['vod_id'])

    print()
    print('===== 3. 翻页(第3页) =====')
    r3 = s.categoryContent('100173', '3', False, {'sort': '83', 'iyear': '2025'})
    print('第3页: %d 条, 首条: %s' % (len(r3['list']), r3['list'][0]['vod_name'] if r3['list'] else '无'))

    print()
    print('===== 4. 详情 + 选集(三体) =====')
    d = s.detailContent(['mzc002007knmh3g'])
    v = d['list'][0]
    print('%s | %s | %s | %s' % (v['vod_name'], v['vod_year'], v['vod_area'], v['vod_type']))
    print('演员:', v['vod_actor'][:60])
    print('播放源:', v['vod_play_from'])
    print('选集前3:', v['vod_play_url'].split('$$$')[0].split('#')[:3])

    print()
    print('===== 5. 搜索"三体" =====')
    sr = s.searchContent('三体', False, '1')
    print('结果 %d 条:' % len(sr['list']))
    for x in sr['list'][:5]:
        print('   -', x['vod_name'], '|', x['vod_year'], '|', x['vod_id'])

    print()
    print('===== 6. 播放地址 =====')
    if sr['list']:
        d2 = s.detailContent([sr['list'][0]['vod_id']])
        if d2['list'] and d2['list'][0]['vod_play_url']:
            first = d2['list'][0]['vod_play_url'].split('$$$')[0].split('#')[0].split('$')[-1]
            print(s.playerContent('', first, []))
    print()
    print('全部测试完成')
