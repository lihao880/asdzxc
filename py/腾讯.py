# -*- coding: utf-8 -*-
"""
腾讯视频 TVBox / 影视仓 Python 爬虫源
================================================
站点: https://v.qq.com
接口: https://pbaccess.video.qq.com  (腾讯视频官方 Web 端公开接口)

覆盖: 全部 7 大分类 × 各分类完整筛选维度 + 多页翻页 + 搜索 + 详情 + 播放

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

# 列表接口用 appid=1000005，详情接口用 appid=3000010
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

# 筛选维度极简兜底（仅当接口完全不可用时使用；值均取自实测的真实 option_value）
# 格式: (参数名, 显示名, [(选项名, 真实值), ...])
_BASE_SORT = ('sort', '排序', [('最热', '75')])
FALLBACK_FILTERS = {
    '100113': [_BASE_SORT,
               ('itype', '类型', [('全部', '-1'), ('爱情', '1'), ('都市', '2'), ('青春', '3'),
                                  ('奇幻', '4'), ('武侠', '5'), ('古装', '6'), ('科幻', '7'),
                                  ('猎奇', '8'), ('竞技', '9'), ('传奇', '10'), ('军旅', '11'),
                                  ('家庭', '12'), ('喜剧', '13'), ('悬疑', '14'), ('权谋', '15'),
                                  ('革命', '16'), ('现实', '17'), ('刑侦', '18'), ('逆袭', '19'),
                                  ('民国', '20'), ('IP改编', '21')]),
               ('ipay', '资费', [('全部', '-1'), ('免费', '1'), ('限免', '2'), ('会员', '3')]),
               ('iarea', '地区', [('全部', '-1'), ('内地', '0'), ('英国', '1'), ('中国台湾', '4'),
                                  ('韩国', '5'), ('美国', '8'), ('泰国', '9'), ('日本', '10'),
                                  ('中国香港', '14'), ('其他', '9999')]),
               ('iyear', '年份', [('全部', '-1'), ('即将上线', '1'), ('2026', '2026'),
                                  ('2025', '2025'), ('2024', '2'), ('2023', '3'), ('2022', '4'),
                                  ('2021', '5'), ('2020-2016', '6'), ('2015-2011', '7'),
                                  ('2010-2000', '8'), ('更早', '9')]),
               ('theater', '剧场', [('全部', '-1'), ('X剧场', '1'), ('板凳单元', '2'),
                                    ('萤火单元', '3'), ('十分剧场', '4')]),
               ('award', '获奖', [('全部', '-1'), ('白玉兰奖', '1'), ('飞天奖', '2'),
                                  ('金鹰奖', '3')])],
    '100173': [_BASE_SORT,
               ('itype', '类型', [('全部', '-1'), ('喜剧', '3'), ('动作', '4'), ('爱情', '5'),
                                  ('犯罪', '6'), ('冒险', '7'), ('战争', '8'), ('悬疑', '10'),
                                  ('恐怖', '11'), ('科幻', '12'), ('动画', '15'), ('灾难', '25'),
                                  ('青春', '26')]),
               ('ipay', '资费', [('全部', '-1'), ('免费', '1'), ('付费', '4'), ('会员', '8')]),
               ('iarea', '地区', [('全部', '-1'), ('英国', '15'), ('法国', '16'), ('德国', '17'),
                                  ('加拿大', '18'), ('西班牙', '19'), ('意大利', '20'),
                                  ('澳大利亚', '21'), ('内地', '100024'), ('中国香港', '100025'),
                                  ('中国台湾', '100026'), ('日本', '100027'), ('韩国', '100028'),
                                  ('美国', '100029'), ('印度', '100030'), ('泰国', '100031'),
                                  ('其他', '100033')]),
               ('iyear', '年份', [('全部', '-1'), ('2017', '1'), ('2016', '2'), ('2015', '3'),
                                  ('2014', '4'), ('2013-2011', '5'), ('2010-2006', '6'),
                                  ('2005-2000', '7'), ('90年代', '8'), ('80年代', '9'),
                                  ('其他', '10'), ('2019', '20'), ('即将上线', '999'),
                                  ('2026', '2026'), ('2025', '2025'), ('2024', '2024'),
                                  ('2023', '2023'), ('2022', '2022'), ('2021', '2021'),
                                  ('2020', '2020'), ('2018', '2018')]),
               ('characteristic', '院线/网络', [('全部', '-1'), ('院线电影', '1'),
                                               ('网络电影', '2'), ('独播', '5'),
                                               ('获奖佳片', '6'), ('原声', '8'), ('粤语', '9')]),
               ('producer', '出品方', [('全部', '-1'), ('腾讯出品', '1'), ('索尼', '2'),
                                      ('派拉蒙', '3'), ('迪士尼', '4'), ('环球', '5'),
                                      ('华谊', '6'), ('华纳', '7'), ('光线', '8'),
                                      ('BBC', '10'), ('20世纪影业', '11'), ('开心麻花', '12')])],
    '100109': [_BASE_SORT, ('itype', '类型', [('全部', '-1')]),
               ('ipay', '资费', [('全部', '-1'), ('免费', '1'), ('会员', '3')]),
               ('iarea', '地区', [('全部', '-1')])],
    '100105': [_BASE_SORT, ('itype', '类型', [('全部', '-1')]),
               ('iregion', '地区', [('全部', '-1')])],
    '100119': [_BASE_SORT, ('itype', '类型', [('全部', '-1')]),
               ('iarea', '地区', [('全部', '-1')]),
               ('anime_status', '状态', [('全部', '-1'), ('即将上线', '1'),
                                          ('更新中', '2'), ('已完结', '3')])],
    '100150': [_BASE_SORT, ('itype', '类型', [('全部', '-1')]),
               ('gender', '性别', [('全部', '-1'), ('女孩', '1'), ('男孩', '2')]),
               ('ipay', '资费', [('全部', '-1')])],
    '110755': [_BASE_SORT, ('prefer', '偏好', [('全部', '-1'), ('男频', '1'), ('女频', '2')])],
}

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

_CACHE = {}
_FILTER_CACHE = {}
_FILTER_LOCK = {}


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


# ============================ 解析工具 ============================
def _iter_params(node):
    """深度遍历 JSON，产出所有 item_params / params 字典"""
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
            rm = _pick(p, 'holly_online_time', 'hotval', 'second_title')
            vods.append(_vod(
                vid,
                _pick(p, 'mz_title', 'title'),
                _pick(p, 'new_pic_hz', 'new_pic_vt', 'image_url'),
                rm if len(str(rm)) <= 24 else '',
                _pick(p, 'year'),
            ))
    _set(key, vods, 300 if vods else 60)
    return vods


def _fetch_filters(cid):
    """取某分类完整筛选维度（不传 page 时接口返回）"""
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
                dims[k]['value'].append({'n': p.get('option_name') or opt, 'v': opt})

    filters = [dims[k] for k in order if dims[k]['value']] if dims else []
    if not filters:
        filters = [{'key': k, 'name': n, 'value': [{'n': a, 'v': b} for a, b in vs]}
                   for k, n, vs in FALLBACK_FILTERS.get(cid, [])]
    _set(key, filters, 3600)
    _FILTER_CACHE[cid] = filters
    return filters


def _valid_keys(cid):
    ks = {d['key'] for d in _fetch_filters(cid)}
    ks.discard('sort')
    return ks


# ============================ 搜索 ============================
def _do_search(key, pg):
    # 说明：腾讯搜索接口一次性返回全部结果（pagesize 调大也不会变），
    # pagenum > 0 会返回空，因此这里始终取第 0 页，pg 仅作透传。
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
            out.append(_vod(vid, vi.get('title'), vi.get('imgUrl'), tagtxt, vi.get('year')))
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
            'name': _pick(p, 'title', 'mz_title'),
            'pic': _pick(p, 'new_pic_hz', 'new_pic_vt', 'image_url'),
            'year': _pick(p, 'year'),
            'area': _pick(p, 'area_name', 'areaName'),
            'type': _pick(p, 'sub_genre'),
            'remark': _pick(p, 'holly_online_time', 'hotval'),
            'content': _pick(p, 'cover_description', 'description'),
        }
        for s in ((first.get('sub_items') or {}).get('star_list', {})
                  .get('item_datas', []) or []):
            nm = (s.get('item_params') or {}).get('name')
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
                _log('筛选取失败', tid, repr(e)[:50])
                filters[tid] = [{'key': k, 'name': n,
                                 'value': [{'n': a, 'v': b} for a, b in vs]}
                                for k, n, vs in FALLBACK_FILTERS.get(tid, [])]
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        try:
            return {'list': _fetch_videos('100113', 'sort=75', 1)[:30]}
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

        parts = []
        sort_v = ext.get('sort') or '75'
        if str(sort_v) in ('', '-1', 'None'):
            sort_v = '75'
        parts.append('sort=' + str(sort_v))

        # 只用该分类下发的合法维度，避免非法参数污染请求
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

        return {
            'parse': 0,
            'playUrl': '',
            'url': page_url,
            'jx': 1,
            'header': header,
            'danmaku': 'http://127.0.0.1:9978/proxy?do=danmu&site=js&url=' + page_url,
        }
