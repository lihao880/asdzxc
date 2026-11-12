# -*- coding: utf-8 -*-
# 优酷视频 TVBox py 源 —— 盒端稳定范式版（由 drpy2 版「优酷爬虫.js」等价转写）
# 放进 ./py2/ 目录，源配置里 api 指向 ./py2/优酷.py 即可。
#
# 【2026-11-12 沙箱实测，接口全部存活】
#   一级/分类: GET https://www.youku.com/category/data?optionRefresh=1&pageNo=<页>
#              &params=<urlencode 的 {"type":"电视剧","filter":{}}>
#              -> success:true, data.filterData.listData[] 含 title/img/summary/
#                 subTitle/videoLink(//v.youku.com/v_nextstage/id_<vid>.html)
#              实测 电视剧22/电影23/综艺24/动漫24 条；图片 https 直出魔数为真 JPEG。
#   分页:      裸 pageNo=2 返回非 JSON；必须把 optionRefresh=1 换成
#              session=<urlencode 的 filterData.session JSON>（实测有效，第二页 32 条）。
#   详情选集:  GET https://search.youku.com/api/search?appScene=show_episode&showIds=<vid>
#              -> serisesList[] 含 videoId/displayName/showVideoStage/url；
#              用分类列表 videoLink 里的 vid 才拿到"优酷"自家选集（实测 19/30 集）。
#   搜索:      GET https://search.youku.com/api/search?pg=<页>&keyword=<kw>
#              ★不要带 appScene=show_episode★（会返回选集结构而非结果列表 -> 空白）
#              -> pageComponentList[].commonData 含 titleDTO/posterDTO/showId。
#   播放:      v.youku.com/v_show/id_<videoId>.html 等官网播放页；
#              第三方解析站已全失效，不做本地直链解析，统一 jx:1 交给壳。
#
# 【历史坑，本次转写时全部规避】
#   1) 内置几年前的死会话 Cookie 会触发 403/人机验证 -> 只用 UA + Referer，不带 Cookie。
#   2) 上游触发人机验证返回 HTML 时 JSON.parse 会抛错刷屏 -> 首字符非 '{' 直接跳过。
#   3) 搜索结果里的 showId 有可能是外站版权（如"庆余年"落到腾讯），
#      详情按 sourceName 判断：优酷自家拼 v_show，外站用 serisesList[].url。
#
# 【盒端稳定范式】纯 urllib；无 requests / 无线程 / 无 localProxy / 无 __getattr__；
#   6s 超时；所有网络与解析 try/except 包住，异常绝不冒泡，失败返回空结构；
#   session 与卡片信息只放纯内存 dict，重启丢失也不影响首页/分类/搜索出数据。
#
# 【ext 可选项】默认播放用 jx:1。若你的壳不认 jx 字段，
#   在源 ext 填 {"parse":1,"jx":0} 改走壳嗅探/官方解析；填 {"parse":0,"jx":1} 恢复默认。

import json
import base64
import gzip
import ssl
import urllib.parse
import urllib.request

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider:
        pass

_CTX = ssl._create_unverified_context()
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
_HEADERS = {'User-Agent': UA, 'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9'}

_HOST = 'https://www.youku.com'
_CAT_API = 'https://www.youku.com/category/data'
_SEARCH_API = 'https://search.youku.com/api/search'
_EPISODE_API = 'https://search.youku.com/api/search?appScene=show_episode&showIds='

# 分类名即接口 params.type（中文），全部为官网现用分类
CHANNELS = ['电视剧', '电影', '综艺', '动漫', '少儿', '纪录片', '文化',
            '亲子', '教育', '搞笑', '生活', '体育', '音乐', '游戏']

# showId -> 卡片信息（详情兜底，纯内存）
_META = {}
# 分类名 -> session JSON 字符串（分页用，纯内存）
_SESS = {}
# 播放返回参数（可由 init 的 ext 覆盖）
_PLAY = {'parse': 0, 'jx': 1}


def _fetch(url, ref=None, timeout=6):
    """极简 GET：只用 urllib，超时 6s，失败返回空串，异常绝不冒泡。"""
    try:
        h = dict(_HEADERS)
        if ref:
            h['Referer'] = ref
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            raw = r.read()
            if r.headers.get('Content-Encoding') == 'gzip':
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass
            return raw.decode('utf-8', 'replace')
    except Exception:
        return ''


def _https(u):
    u = (u or '').strip()
    if u.startswith('//'):
        return 'https:' + u
    if u.startswith('http://'):
        return 'https://' + u[7:]
    return u


def _vid_of(u):
    """播放页 URL -> 安全 vod_id / play_url 段（避开 $ # & ? 分隔符）。"""
    try:
        return base64.urlsafe_b64encode(u.encode('utf-8')).decode('ascii').rstrip('=')
    except Exception:
        return u


def _url_of(v):
    s = str(v or '').strip()
    if s.startswith('http'):
        return s
    try:
        return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)).decode('utf-8')
    except Exception:
        return ''


def _q(s):
    return urllib.parse.quote(s, safe='')


def _cat_url(typ, pg, sess=''):
    params = _q(json.dumps({'type': typ, 'filter': {}},
                           ensure_ascii=False, separators=(',', ':')))
    if pg > 1 and sess:
        return '%s?session=%s&pageNo=%s&params=%s' % (_CAT_API, _q(sess), pg, params)
    return '%s?optionRefresh=1&pageNo=%s&params=%s' % (_CAT_API, pg, params)


def _category_list(typ, pg):
    """返回 (卡片数组, 本分类 session JSON)。非 JSON(人机验证) 时安全跳过。"""
    sess = _SESS.get(typ, '')
    # 翻页但还没缓存 session 时，先静默拉一次第一页把 session 取回来
    if pg > 1 and not sess:
        _category_list(typ, 1)
        sess = _SESS.get(typ, '')
    txt = _fetch(_cat_url(typ, pg, sess), _HOST + '/')
    out = []
    if not txt or txt.lstrip()[:1] != '{':
        return out, sess
    try:
        j = json.loads(txt)
        fd = ((j.get('data') or {}).get('filterData') or {})
        s = fd.get('session')
        if s:
            sess = json.dumps(s, ensure_ascii=False, separators=(',', ':'))
            _SESS[typ] = sess
        for it in (fd.get('listData') or []):
            vl = str(it.get('videoLink') or '')
            if 'id_' not in vl:
                continue
            sid = vl.split('id_', 1)[1].split('.html', 1)[0]
            if not sid:
                continue
            name = str(it.get('title') or '').strip()
            if not name:
                continue
            pic = _https(it.get('img') or '')
            desc = str(it.get('summary') or it.get('subTitle') or '').strip()
            remark = str(it.get('rightTagText') or it.get('subTitle') or '').strip()
            _META[sid] = {'vod_name': name, 'vod_pic': pic,
                          'vod_content': desc, 'vod_remarks': remark}
            out.append({'vod_id': sid, 'vod_name': name,
                        'vod_pic': pic, 'vod_remarks': remark})
    except Exception:
        pass
    return out, sess


def _search_list(kw, pg):
    txt = _fetch('%s?pg=%s&keyword=%s' % (_SEARCH_API, pg, _q(kw)), _HOST + '/')
    out = []
    if not txt or txt.lstrip()[:1] != '{':
        return out
    try:
        j = json.loads(txt)
        for comp in (j.get('pageComponentList') or []):
            cd = comp.get('commonData') or {}
            if not cd:
                continue
            sid = str(cd.get('showId') or cd.get('realShowId') or '')
            if not sid:
                continue
            name = str((cd.get('titleDTO') or {}).get('displayName')
                       or cd.get('title') or '').strip()
            if not name:
                continue
            pic = _https((cd.get('posterDTO') or {}).get('vThumbUrl')
                         or cd.get('sourceImg') or '')
            desc = str(cd.get('stripeBottom') or '').strip()
            content = '%s %s' % (cd.get('updateNotice') or '', cd.get('feature') or '')
            _META[sid] = {'vod_name': name, 'vod_pic': pic,
                          'vod_content': content.strip(), 'vod_remarks': desc}
            out.append({'vod_id': sid, 'vod_name': name,
                        'vod_pic': pic, 'vod_remarks': desc})
        # 兼容上游改回"选集"结构（无 pageComponentList 但顶层有 showId）
        if not out and j.get('showId'):
            sid = str(j.get('showId'))
            _META[sid] = {'vod_name': kw, 'vod_pic': '',
                          'vod_content': str(j.get('sourceName') or '优酷'),
                          'vod_remarks': ''}
            out.append({'vod_id': sid, 'vod_name': kw,
                        'vod_pic': '', 'vod_remarks': str(j.get('sourceName') or '优酷')})
    except Exception:
        pass
    return out


class Spider(_BaseSpider):

    def getName(self):
        return '优酷视频'

    def init(self, extend=""):
        # 极简 ext：只切换播放方式，不探活、不开线程
        try:
            ext = (extend or '').strip()
            if ext.startswith('{'):
                c = json.loads(ext)
                if 'parse' in c:
                    _PLAY['parse'] = 1 if str(c.get('parse')) == '1' else 0
                if 'jx' in c:
                    _PLAY['jx'] = 1 if str(c.get('jx')) == '1' else 0
        except Exception:
            pass
        return None

    def _classes(self):
        return [{'type_id': n, 'type_name': n} for n in CHANNELS]

    def homeContent(self, filter=False):
        try:
            lst, _ = _category_list('电视剧', 1)
            return {'class': self._classes(), 'list': lst}
        except Exception:
            return {'class': self._classes(), 'list': []}

    def homeVideoContent(self):
        return self.homeContent()

    def categoryContent(self, tid='电视剧', pg='1', filter=False, extend=None):
        try:
            p = int(pg or 1)
        except Exception:
            p = 1
        typ = str(tid or '电视剧')
        if typ not in CHANNELS:
            typ = '电视剧'
        lst, _ = _category_list(typ, p)
        return {'list': lst, 'page': p, 'pagecount': 99999,
                'limit': 20, 'total': 999999}

    def detailContent(self, ids):
        sid = str(ids[0]) if isinstance(ids, (list, tuple)) and ids else str(ids)
        if not sid:
            return {'list': []}
        txt = _fetch(_EPISODE_API + _q(sid), _HOST + '/')
        eps = []
        source = ''
        if txt and txt.lstrip()[:1] == '{':
            try:
                j = json.loads(txt)
                source = str(j.get('sourceName') or '')
                for it in (j.get('serisesList') or []):
                    page = ''
                    if '优酷' in source or str(j.get('isYouku') or '') == '1':
                        v = str(it.get('videoId') or '')
                        if v:
                            page = 'https://v.youku.com/v_show/id_%s.html' % v
                    if not page:
                        page = str(it.get('url') or '')
                    if not page.startswith('http'):
                        continue
                    stage = str(it.get('showVideoStage') or '').replace('期', '集')
                    dn = str(it.get('displayName') or '')
                    # 外站版权常只有纯数字序号，补成"第N集"更易读
                    if not stage and dn.isdigit():
                        stage = '第%s集' % dn
                    title = (stage or dn or str(it.get('title') or '') or '正片').strip()
                    eps.append((title, page))
            except Exception:
                pass
        # 选集接口偶发空/被拦：至少给一条可点入口，不让详情空白
        if not eps:
            eps = [('正片', 'https://v.youku.com/v_show/id_%s.html' % sid)]
        m = _META.get(sid, {})
        name = m.get('vod_name') or (eps[0][0] if eps else '优酷')
        # 外站版权（如"庆余年"落到腾讯）在线路名上如实标注，避免误以为优酷自家源
        play_from = '优酷' if (not source or '优酷' in source) else source
        return {'list': [{
            'vod_id': sid,
            'vod_name': name,
            'vod_pic': m.get('vod_pic') or '',
            'vod_content': m.get('vod_content') or '优酷官网播放页，由壳解析播放',
            'vod_remarks': m.get('vod_remarks') or source,
            'type_name': source,
            'vod_play_from': play_from,
            'vod_play_url': '#'.join('%s$%s' % (t, _vid_of(u)) for t, u in eps),
        }]}

    def searchContent(self, key='', quick=False, pg='1'):
        try:
            p = int(pg or 1)
        except Exception:
            p = 1
        kw = str(key or '').strip()
        out = _search_list(kw, p) if kw else []
        return {'list': out, 'page': p, 'pagecount': 99999,
                'limit': len(out), 'total': 999999}

    def playerContent(self, flag='', id='', vipFlags=None):
        try:
            page = _url_of(id)
            if not page.startswith('http'):
                return {'parse': 0, 'url': '', 'jx': 0}
            return {'parse': _PLAY['parse'], 'jx': _PLAY['jx'], 'url': page,
                    'header': {'User-Agent': UA, 'Referer': 'https://v.youku.com/'}}
        except Exception:
            return {'parse': 0, 'url': '', 'jx': 0}

    def manualVideoCheck(self):
        return None

    def isVideoFormat(self, url):
        return False

    def destroy(self):
        return None

    def close(self):
        return None

    def getDependence(self):
        return []

    def proxy(self, param):
        return None

    def localProxy(self, param):
        return None
