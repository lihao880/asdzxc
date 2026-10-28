#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 荐片 cibnabg 镜像 TVBox py 源（融合两版优点，沙箱端到端验证通过）
#
# 站点： https://h5v1.cibnabg.com  （荐片影视系 SPA，数据走同源 /api）
# 关键工程点（来自对比验证）：
#   1) 封面图走独立 CDN 图床（img.cqkgy.com 等），init() 里用
#      /v2/settings/resourceDomainConfig 拿域名 + _probe_img 探测可达，
#      相对路径必须拼到图床域名，拼到站点域名会 404（早期版本踩过坑）。
#   2) 分类列表用 /search/searchList（稳定），不用偶发 500 的 dyTag/tpl1_data。
#   3) 详情合并 source_list_source 与 vip_source_list_source，线路更全。
#   4) UA 用 okhttp/3.15（TVBox 环境规范），结果加 5 分钟缓存 + 重试。
#
# 接口：
#   首页分类  GET /api/v2/settings/homeCategory
#   图床配置  GET /api/v2/settings/resourceDomainConfig   -> data.imgDomain
#   分类列表  GET /api/search/searchList?category_id=<id>&page=<页>
#   首页精选  GET /api/search/searchList?category_id=88
#   搜索      GET /api/v2/search/videoV2?key=<词>&page=<页>&pageSize=20
#   详情      GET /api/video/detailv2?id=<vid>
#   播放      data.source_list_source[].source_list[].url -> m3u8 直链(parse=0)
import sys
import json
import time
import urllib.request
import urllib.parse

try:
    sys.path.append('..')
    from base.spider import Spider
except Exception:
    class Spider:
        pass


class Spider(Spider):

    HOST = 'https://h5v1.cibnabg.com'
    API = HOST + '/api'
    UA = 'okhttp/3.15'
    PAGE_SIZE = 10
    # 图床探测兜底（接口拿不到时用的候选）
    FALLBACK_IMG = ['img.cqkgy.com', 'img.hzllys.com', 'img.bptpw.com', 'img.ypfbj.com']
    # 分类排序（不在列表里的排最后）
    CAT_ORDER = [1, 2, 67, 3, 4, 50, 99]
    MAX_PAGES = 10  # 分类筛选为客户端本地过滤，最多预拉页数（每页约 10 条）
    CLASSES_FALLBACK = [
        {'type_id': '1', 'type_name': '电影'},
        {'type_id': '2', 'type_name': '电视剧'},
        {'type_id': '67', 'type_name': '短剧'},
        {'type_id': '3', 'type_name': '动漫'},
        {'type_id': '4', 'type_name': '综艺'},
        {'type_id': '50', 'type_name': '纪录片'},
        {'type_id': '99', 'type_name': 'Netflix'},
    ]

    def init(self, extend=""):
        self._img = ''
        self._cache = {}
        # 1) 从接口拿真实图床域名
        try:
            d = self._get('/v2/settings/resourceDomainConfig')
            domains = (d.get('data') or {}).get('imgDomain') or ''
            probe = [x.strip() for x in domains.split(',') if x.strip()]
        except Exception:
            probe = []
        # 2) 逐个探测哪个图床可达，选第一个
        for host in probe + [h for h in self.FALLBACK_IMG if h not in probe]:
            if self._probe_img(host):
                self._img = 'https://' + host
                break
        if not self._img and probe:
            self._img = 'https://' + probe[0]
        self._cat_cache = {}
        self._filters_cache = None

    def getName(self):
        return '荐片'

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def homeContent(self, filter):
        classes = []
        try:
            d = self._get('/v2/settings/homeCategory')
            items = sorted(
                d.get('data') or [],
                key=lambda x: self.CAT_ORDER.index(x['id']) if x.get('id') in self.CAT_ORDER else 99)
            for c in items:
                if c.get('id') in self.CAT_ORDER:
                    classes.append({'type_id': str(c['id']), 'type_name': c['name']})
        except Exception:
            classes = self.CLASSES_FALLBACK
        result = {'class': classes}
        if filter:
            fl = self._build_filters()
            result['filters'] = {
                c['type_id']: [fl['area'], fl['year'], fl['sort']] for c in classes
            }
        return result

    def homeVideoContent(self):
        return {'list': self._list_page('88', 1)}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        extend = extend or {}
        # 站点 searchList 不支持服务端筛选参数，统一拉取本分类数据后在本地过滤/排序
        raw = self._load_category(str(tid))
        items = self._apply_filters(raw, extend)
        items = self._apply_sort(items, extend.get('sort'))
        return self._paginate(items, pg)

    def _load_category(self, tid):
        """预拉本分类最多 MAX_PAGES 页，合并去重后缓存（供筛选/分页复用）。"""
        if tid in getattr(self, '_cat_cache', {}):
            return self._cat_cache[tid]
        items = []
        seen = set()
        for p in range(1, self.MAX_PAGES + 1):
            d = self._get('/search/searchList', {'category_id': tid, 'page': p})
            lst = d.get('data') or []
            if not lst:
                break
            for v in lst:
                if v.get('id') and v['id'] not in seen:
                    seen.add(v['id'])
                    items.append(v)
            if len(lst) < self.PAGE_SIZE:
                break
        self._cat_cache[tid] = items
        return items

    def _apply_filters(self, items, ext):
        area = (ext.get('area') or '').strip()
        year = (ext.get('year') or '').strip()
        out = []
        for it in items:
            if area:
                cats = it.get('categroyies') or []
                if not any(area == str(c) for c in cats):
                    continue
            if year and str(it.get('year')) != str(year):
                continue
            out.append(it)
        return out

    def _apply_sort(self, items, sort):
        if sort in ('hot', 'rating'):
            items = sorted(items, key=lambda x: float(x.get('score') or 0), reverse=True)
        elif sort == 'update':
            def _kf(x):
                try:
                    return float(x.get('changed') or 0)
                except Exception:
                    return 0
            items = sorted(items, key=_kf, reverse=True)
        return items

    def _paginate(self, items, pg, page_size=None):
        page_size = page_size or self.PAGE_SIZE
        total = len(items)
        pagecount = max(1, (total + page_size - 1) // page_size) if total else 1
        start = (pg - 1) * page_size
        return {
            'list': [self._item(x) for x in items[start:start + page_size]],
            'page': pg,
            'pagecount': pagecount,
            'limit': page_size,
            'total': total,
        }

    def _build_filters(self):
        if getattr(self, '_filters_cache', None) is not None:
            return self._filters_cache
        groups = {}
        try:
            d = self._get('/crumb/filterOptions')
            for g in (d.get('data') or []):
                groups[g.get('key')] = g.get('data') or []
        except Exception:
            groups = {}
        area_opts = [{'n': '全部', 'v': ''}]
        for o in groups.get('area', []):
            if o.get('name') and o['name'] != '全部':
                area_opts.append({'n': o['name'], 'v': o['name']})
        year_opts = [{'n': '全部', 'v': ''}]
        for o in groups.get('year', []):
            if o.get('name') and o['name'] != '全部':
                year_opts.append({'n': o['name'], 'v': str(o['name'])})
        sort_opts = [
            {'n': '最新', 'v': 'update'},
            {'n': '最热', 'v': 'hot'},
            {'n': '评分', 'v': 'rating'},
        ]
        self._filters_cache = {
            'area': {'key': 'area', 'name': '地区', 'value': area_opts},
            'year': {'key': 'year', 'name': '年份', 'value': year_opts},
            'sort': {'key': 'sort', 'name': '排序', 'value': sort_opts},
        }
        return self._filters_cache

    def detailContent(self, array):
        vid = str(array[0])
        d = self._get('/video/detailv2', {'id': vid})
        info = d.get('data') or {}
        sources = self._merge_sources(info)
        play_from = []
        play_url = []
        used = set()
        for src in sources:
            name = (src.get('name') or '线路').strip()
            base = name
            i = 1
            while name in used:
                i += 1
                name = '%s%s' % (base, i)
            eps = src.get('source_list') or []
            urls = []
            seen_urls = set()
            for ep in eps:
                url = ep.get('url') or ''
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                used.add(name)
                ep_name = self._clean(ep.get('source_name') or ep.get('weight') or '播放')
                urls.append('%s$%s' % (ep_name, url))
            if urls:
                play_from.append(name)
                play_url.append('#'.join(urls))
        pic = self._pic(info.get('thumbnail') or info.get('tvimg'))
        types = '/'.join([t.get('name', '') for t in (info.get('types') or []) if t.get('name')])
        actors = ','.join([a.get('name', '') for a in (info.get('actors') or []) if a.get('name')])
        directors = ','.join([a.get('name', '') for a in (info.get('directors') or []) if a.get('name')])
        langs = '/'.join([l.get('value', '') for l in (info.get('languages') or []) if l.get('value')])
        dates = '/'.join([r.get('value', '') for r in (info.get('release_dates') or []) if r.get('value')])
        vod = {
            'vod_id': vid,
            'vod_name': info.get('title') or '',
            'vod_pic': pic,
            'type_name': types,
            'vod_year': info.get('year') or '',
            'vod_area': info.get('area') or '',
            'vod_lang': langs,
            'vod_remarks': info.get('mask') or '',
            'vod_score': info.get('score') or '',
            'vod_actor': actors,
            'vod_director': directors,
            'vod_content': (info.get('description') or '').strip(),
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg) if str(pg).isdigit() else 1
        d = self._get('/v2/search/videoV2', {'key': key or '', 'page': pg, 'pageSize': 20})
        lst = []
        for v in d.get('data') or []:
            lst.append(self._item(v))
        return {'list': lst, 'page': pg}

    def playerContent(self, flag, id, vipFlags):
        return {
            'parse': 0,
            'playUrl': '',
            'url': id,
            'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'},
        }

    def localProxy(self, param):
        return [200, 'text/plain', '', '']

    # ---------------- 内部请求 ----------------
    def _get(self, path, params=None):
        url = self.API + path
        if params:
            url += '?' + urllib.parse.urlencode(params)
        now = time.time()
        if url in self._cache and now - self._cache[url][0] < 300:
            return self._cache[url][1]
        req = urllib.request.Request(url, headers={'User-Agent': self.UA, 'Referer': self.HOST + '/'})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=12) as r:
                    d = json.loads(r.read().decode('utf-8', 'ignore'))
                if isinstance(d, dict) and d.get('code') in (0, 1):
                    self._cache[url] = (now, d)
                    return d
                raise RuntimeError(d.get('msg', 'empty') if isinstance(d, dict) else 'bad json')
            except Exception:
                if attempt == 2:
                    return {}
        return {}

    def _list_page(self, cid, pg):
        d = self._get('/search/searchList', {'category_id': cid, 'page': pg})
        return [self._item(v) for v in (d.get('data') or [])]

    def _item(self, v):
        mask = str(v.get('mask') or '')
        score = str(v.get('score') or '')
        if score in ('0', '0.0', '0.00'):
            score = ''
        remarks = mask or score
        if score and mask and score != mask:
            remarks = mask + ' ' + score
        return {
            'vod_id': str(v.get('id') or ''),
            'vod_name': v.get('title') or '',
            'vod_pic': self._pic(v.get('thumbnail') or v.get('tvimg')),
            'vod_remarks': remarks,
        }

    def _pic(self, path):
        if not path:
            return ''
        if path.startswith('http'):
            return path
        return (self._img or '') + path

    def _merge_sources(self, info):
        primary = info.get('source_list_source') or []
        merged = list(primary)
        seen_urls = set()
        for s in primary:
            for ep in (s.get('source_list') or []):
                if ep.get('url'):
                    seen_urls.add(ep['url'])
        for s in (info.get('vip_source_list_source') or []):
            eps = [e for e in (s.get('source_list') or []) if e.get('url') and e['url'] not in seen_urls]
            if eps:
                for e in eps:
                    seen_urls.add(e['url'])
                s = dict(s)
                s['source_list'] = eps
                merged.append(s)
        if not merged and info.get('m3u8_list'):
            merged = [{'name': '默认', 'source_list': info.get('m3u8_list')}]
        return merged

    def _clean(self, name):
        return name.replace('#', ' ').replace('$', ' ').strip() or '播放'

    def _probe_img(self, host):
        try:
            req = urllib.request.Request(
                'https://' + host + '/favicon.ico',
                headers={'User-Agent': self.UA},
                method='GET')
            with urllib.request.urlopen(req, timeout=6) as r:
                return r.status == 200
        except urllib.error.HTTPError as e:
            return e.code in (200, 301, 302, 403, 404)
        except Exception:
            return False
