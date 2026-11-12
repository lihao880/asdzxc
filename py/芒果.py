# -*- coding: utf-8 -*-
# 芒果TV TVBox py 源 —— 盒端稳定范式版（与 爱奇艺.py / 优酷.py 同一套骨架）
# 放进 ./py2/ 目录，源配置里 api 指向 ./py2/芒果TV.py 即可。
#
# 【2026-11-12 沙箱实测，接口全部存活】
#   一级/分类: GET https://pianku.api.mgtv.com/rider/list/pcweb/v3
#              ?pn=<页>&pc=20&channelId=<频道>&sort=c2
#              -> code 200, data.hitDocs[] 含 clipId(专辑ID)/playPartId(当前集ID)/
#                 title/img/imgUrlH/story/subtitle/updateInfo/year
#              实测频道 2电视剧/3电影/1综艺/50动漫/10少儿/51纪实 各 20 条，
#              pn 翻页有效（无需 session）。图片 https 直出且魔数为真 JPEG。
#   详情选集:  GET https://pcweb.api.mgtv.com/episode/list
#              ?collection_id=<clipId>&page=1&size=50
#              -> data.list[] 含 video_id/t1(集号)/t2/t3/t4(第N集)/url(/b/cid/vid.html)
#              注意：接口会返回 73 条，其中「彩N」是花絮、3~7 集各有一份
#              「看点」重复条目。本源按集号去重 + 剔除花絮，还原正片 40 集。
#   播放页:    https://www.mgtv.com/b/<clipId>/<videoId>.html （实测 200）
#
# 【播放：源内直出真实 m3u8，不再依赖壳解析】
#     1) tk2 = reverse(base64('did=<did>|pno=1030|ver=5.5.1|clit=<固定值>'))
#     2) GET https://pcweb.api.mgtv.com/player/video?video_id=<vid>&tk2=<tk2>
#        （带 Cookie: PM_CHKID=1）-> data.atc.pm2
#     3) GET https://pcweb.api.mgtv.com/player/getSource
#        ?video_id=<vid>&tk2=<tk2b>&pm2=<pm2>
#        &did=<did>&suuid=&cxid=&type=pch5&_support=10000000
#        &auth_mode=1&allowedRC=1&abroad=0
#        -> data.stream_domain[] + data.stream[].url(/atcl?pm2=...)
#        ★ 这套设备参数必须带全，否则 atcl 一律返回 code:617 busy。
#     4) GET <stream_domain[0]><stream.url> -> {"info": "https://....m3u8?..."}
#     5) playerContent 返回 parse:0 / jx:0 / url=真实m3u8
#        header 必须带 User-Agent(PC) + Referer(www.mgtv.com)，裸请求 403。
#   实测 m3u8 返回 200 + #EXTM3U，标清/高清/超清三档均可用，默认取最高档。
#   任一步失败 -> 自动降级回 jx:1，异常绝不冒泡。
#
# 【2026-11-12 三次加固：解决盒端「还是空白」】
#   - 去掉 import time，改用实测有效的固定 clit（减少盒端加载依赖）。
#   - playerContent 同时返回 header / headers 双键；不同壳对请求头的契约
#     不一致（dict / JSON字符串 / 只认 URL 后缀），用 ext 一键切换：
#       {"atref":1}   把 Referer 用 TVBox 通用 @Referer= 后缀拼到 m3u8 上
#       {"hdr":"str"} header 改为 JSON 字符串
#     壳不认 header 时 m3u8 会被 403 -> 播放器纯黑（空白）。
#   - 首页/分类接口不通时返回一张可点的兜底卡，保证任何情况下都不全白。
#   - 降级 URL 用 m 站播放页（SSR 200，含标题），比 PC 页更易被壳解析。
#
# 【2026-11-12 四次修复：解决「有视频、不能播放」】
#   根因实测：拿到的 m3u8 里 283 个 ts 分片全是「相对路径」，且每个分片都
#   要求 User-Agent + Referer 同时存在，缺一即 403（只带 UA 或只带 Referer
#   都 403）。而 playerContent 返回的 header 字典在很多壳里只作用于主 m3u8
#   请求、不会传给分片 -> 主文件能下、分片全 403 -> 有画面列表但播不了。
#   修复：
#   1) 默认改用 TVBox 通用 @ 后缀契约：
#        m3u8@Referer=https://www.mgtv.com/@User-Agent=okhttp/3.14.9
#      壳会把这两个头应用到该流的全部请求（含所有相对分片）。
#      UA 用短串（不含空格/括号/分号），避免被壳按空格截断 URL。
#   2) 详情页给三条线路，盒端可手动切换：
#        直连        = @ 后缀（默认，覆盖分片，首选）
#        直连·请求头 = 纯 m3u8 + header/headers 字典（壳认请求头时用）
#        壳解析      = jx:1 交壳自带解析（兜底）
#   3) getSource 返回的 3 个 stream_domain 落到 3 个不同 CDN，原先只取 [0]，
#      盒端若到该 CDN 不通就整体降级；现在档位 × CDN 交叉轮询，任一成功即返回。
#
# 【搜索：三层兜底，任何环境都不空白】
#   1) 官方搜索 GET https://mobileso.bz.mgtv.com/msite/search/v2
#      ?q=<kw>&pc=30&pn=1&sort=-99&ty=0&du=0&pt=0&corr=1&abroad=0
#      &_support=10000000000000000
#      -> data.contents[].data[] 含 title/url/img/desc/source；
#         仅取 source=='imgo' 的芒果自有结果，专辑 id 从 url 的 /b/<id>/ 提取。
#      注：该域在部分机房 IP 会 403（沙箱实测被拦，盒端家宽通常可通）。
#   2) 官方不可用时：拉片库 6 个频道各 2 页（纯内存）按标题做本地关键词过滤。
#   3) 仍无结果：给一条官网搜索页入口卡（so.mgtv.com/so?k=）。
#
# 【盒端稳定范式】纯 urllib；无 requests / 无线程 / 无 localProxy / 无 __getattr__；
#   6s 超时；所有网络与解析 try/except 包住，异常绝不冒泡，失败返回空结构；
#   卡片信息用纯内存 _META 缓存供详情使用。
#
# 【ext 可选项】
#   默认：播放直连真实 m3u8 + @Referer/@User-Agent 后缀（parse:0 / jx:0），
#         不依赖壳解析接口，且 @ 头对全部 ts 分片生效。
#   {"direct":0}        关闭直连，退回 jx:1 交壳解析。
#   {"atref":0}         关闭 @ 后缀，改回纯 m3u8 + header 字典（少数壳用）。
#   {"hdr":"str"}       header 改成 JSON 字符串（部分壳要求）。
#   {"parse":1,"jx":0}  降级时改走壳嗅探/官方解析。
#   {"quality":1|2|3}   指定清晰度（1标清/2高清/3超清），默认自动取最高。
#   {"search":"local"}   强制走片库本地过滤（官方搜索被墙时用）。
#   注：播放页也可直接切「直连 / 直连·请求头 / 壳解析」三条线路，无需改 ext。

import json
import re
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

_HOST = 'https://www.mgtv.com'
_LIST_API = 'https://pianku.api.mgtv.com/rider/list/pcweb/v3'
_EPISODE_API = 'https://pcweb.api.mgtv.com/episode/list'
_SEARCH_API = 'https://mobileso.bz.mgtv.com/msite/search/v2'
_PLAYER_VIDEO = 'https://pcweb.api.mgtv.com/player/video'
_PLAYER_SOURCE = 'https://pcweb.api.mgtv.com/player/getSource'

# 固定设备指纹（tk2 与 getSource 的 did 必须一致，实测有效）
_DID = 'f11dee65-4e0d-4d25-bfce-719ad9dc991d'
# clit 不校验时效，固定值即可（实测 0 / 1700000 / 1794480 均返回 pm2）
# 用固定值可省掉 import time，减少盒端加载依赖
_CLIT = 1794480
_CK = {'Cookie': 'PM_CHKID=1'}
_REF = {'User-Agent': UA, 'Referer': 'https://www.mgtv.com/'}
# TVBox @ 后缀契约里用的短 UA：不含空格/括号/分号，不会被壳按空格截断。
# 实测该 UA + Referer 对 m3u8 主请求和全部 ts 分片均返回 200。
_SUF_UA = 'okhttp/3.14.9'

# 频道号 -> 分类名（六个频道实测均 code 200 + 20 条）
CHANNELS = [
    ('2', '电视剧'), ('3', '电影'), ('1', '综艺'),
    ('50', '动漫'), ('10', '少儿'), ('51', '纪实'),
]

# clipId -> 卡片信息（详情兜底，纯内存）
_META = {}
# 播放参数 / 搜索模式（可由 init 的 ext 覆盖）
# atref 默认 1：播放默认走 TVBox @Referer/@User-Agent 后缀契约，
# 保证 m3u8 的相对 ts 分片也能带齐 UA + Referer（否则分片 403 导致播不了）。
_PLAY = {'parse': 0, 'jx': 1, 'direct': 1, 'quality': 0,
         'atref': 1, 'hdrstr': 0}
_SEARCH_MODE = 'auto'


def _fetch(url, ref=None, timeout=6, extra=None):
    """极简 GET：只用 urllib，超时 6s，失败返回空串，异常绝不冒泡。"""
    try:
        h = dict(_HEADERS)
        if ref:
            h['Referer'] = ref
        if extra:
            h.update(extra)
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


def _q(s):
    return urllib.parse.quote(str(s), safe='')


def _tk2(s):
    """芒果 tk2：urlsafe base64 后整体反转。"""
    return base64.urlsafe_b64encode(s.encode('utf-8')).decode('ascii').rstrip('=')[::-1]


def _url_of(v):
    s = str(v or '').strip()
    if s.startswith('http'):
        return s
    try:
        return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)).decode('utf-8')
    except Exception:
        return ''


def _vid_of(u):
    """播放页 URL -> 安全 vod_id / play_url 段（避开 $ # & ? 分隔符）。"""
    try:
        return base64.urlsafe_b64encode(u.encode('utf-8')).decode('ascii').rstrip('=')
    except Exception:
        return u


def _fallback_card():
    """接口不通时的兜底卡：保证首页/分类永不全白，点进去是官网。"""
    return {'vod_id': 'web' + _vid_of('https://so.mgtv.com/so?k='),
            'vod_name': '芒果TV接口暂不可达·点此打开官网',
            'vod_pic': '', 'vod_remarks': '检查网络后下拉刷新'}


def _resolve_m3u8(page):
    """官网播放页 -> 真实 m3u8 直连地址；任一步失败返回空串（上层降级）。"""
    try:
        m = re.search(r'/(\d+)\.html', page)
        if not m:
            return ''
        vid = m.group(1)
        clit = _CLIT
        tk2 = _tk2('did=%s|pno=1030|ver=5.5.1|clit=%d' % (_DID, clit))

        # 1) player/video -> pm2
        txt = _fetch('%s?video_id=%s&tk2=%s' % (_PLAYER_VIDEO, vid, _q(tk2)),
                     page, extra=_CK)
        if not txt or txt.lstrip()[:1] != '{':
            return ''
        pm2 = (((json.loads(txt).get('data') or {}).get('atc') or {})
               .get('pm2') or '')
        if not pm2:
            return ''

        # 2) getSource（设备参数必须带全，否则 atcl 返回 617 busy）
        tk2b = _tk2('clit=%d' % clit)
        su = ('%s?video_id=%s&tk2=%s&pm2=%s'
              '&did=%s&suuid=&cxid=&type=pch5&_support=10000000'
              '&auth_mode=1&allowedRC=1&abroad=0'
              % (_PLAYER_SOURCE, vid, _q(tk2b), _q(pm2), _DID))
        stxt = _fetch(su, page, extra=_CK)
        if not stxt or stxt.lstrip()[:1] != '{':
            return ''
        d = json.loads(stxt).get('data') or {}
        # 实测返回 3 个 stream_domain，分别落到 pcvideocmobile-v6 /
        # pcvideohwyunott / pcvideoaliyun 三个不同 CDN。盒端常只通其中一个，
        # 所以全部轮询，任一成功即返回（原先只取 [0]，不通就直接降级）。
        doms = [x for x in (d.get('stream_domain') or []) if x][:3]
        streams = [s for s in (d.get('stream') or []) if s.get('url')]
        if not doms or not streams:
            return ''
        doms = [('https://' + x[7:] if x.startswith('http://') else x)
                for x in doms]

        want = str(_PLAY.get('quality') or '')
        if want:
            first = [s for s in streams if str(s.get('def') or '') == want]
            rest = [s for s in streams if str(s.get('def') or '') != want]
            # 指定档位放最前，其余档位作后备，避免单档 busy 就整体降级
            pick = first + sorted(rest, key=lambda s: int(s.get('def') or 0),
                                  reverse=True)
        else:
            pick = sorted(streams, key=lambda s: int(s.get('def') or 0), reverse=True)

        # 3) atcl -> info(真实 m3u8)：档位 × CDN 交叉重试
        for s in pick[:3]:
            for dom in doms:
                z = _fetch(dom + str(s['url']), page, extra=_CK, timeout=5)
                if not z or z.lstrip()[:1] != '{':
                    continue
                try:
                    info = str(json.loads(z).get('info') or '')
                except Exception:
                    continue
                if info.startswith('http') and '.m3u8' in info:
                    return info
        return ''
    except Exception:
        return ''


def _put_meta(cid, name, pic, remark, content, part_id=''):
    _META[str(cid)] = {'vod_name': name, 'vod_pic': pic,
                       'vod_remarks': remark, 'vod_content': content,
                       'part_id': str(part_id or '')}


def _card(cid, name, pic, remark, content, part_id=''):
    _put_meta(cid, name, pic, remark, content, part_id)
    return {'vod_id': str(cid), 'vod_name': name,
            'vod_pic': pic, 'vod_remarks': remark}


def _list_docs(cid, pg):
    """片库列表：返回 hitDocs 原始数组。"""
    u = '%s?pn=%s&pc=20&channelId=%s&sort=c2' % (_LIST_API, pg, _q(cid))
    txt = _fetch(u, _HOST + '/')
    if not txt or txt.lstrip()[:1] != '{':
        return []
    try:
        j = json.loads(txt)
        if str(j.get('code')) != '200':
            return []
        return ((j.get('data') or {}).get('hitDocs') or [])
    except Exception:
        return []


def _category_list(cid, pg):
    out = []
    for it in _list_docs(cid, pg):
        c = str(it.get('clipId') or '')
        name = re.sub(r'<[^>]+>', '', str(it.get('title') or '')).strip()
        if not c or not name:
            continue
        pic = _https(it.get('img') or it.get('imgUrlH') or '')
        remark = str(it.get('updateInfo') or it.get('subtitle') or '').strip()
        content = str(it.get('story') or '').strip()
        out.append(_card(c, name, pic, remark, content, it.get('playPartId') or ''))
    return out


def _official_search(kw):
    """官方搜索接口（部分机房 IP 会 403，失败返回空列表由上层降级）。"""
    u = ('%s?q=%s&pc=30&pn=1&sort=-99&ty=0&du=0&pt=0&corr=1'
         '&abroad=0&_support=10000000000000000') % (_SEARCH_API, _q(kw))
    txt = _fetch(u, 'https://m.mgtv.com/', timeout=6)
    if not txt or txt.lstrip()[:1] != '{':
        return []
    out = []
    try:
        j = json.loads(txt)
        for block in (((j.get('data') or {}).get('contents')) or []):
            if block.get('type') != 'media':
                continue
            for it in (block.get('data') or []):
                if not isinstance(it, dict):
                    continue
                # 只收芒果自有内容，外站聚合结果不进（避免详情取不到选集）
                if str(it.get('source') or 'imgo') != 'imgo':
                    continue
                url = str(it.get('url') or '')
                m = re.search(r'/b/(\d+)', url)
                if not m:
                    continue
                cid = m.group(1)
                name = re.sub(r'<[^>]+>', '', str(it.get('title') or '')).strip()
                if not name:
                    continue
                pic = _https(it.get('img') or '')
                desc = it.get('desc') or []
                remark = ''
                if isinstance(desc, list) and desc:
                    remark = str(desc[0]).replace('类型:', '').split('/')[0].strip()
                out.append(_card(cid, name, pic, remark, remark))
    except Exception:
        pass
    return out


def _local_search(kw):
    """降级：片库 6 频道各 2 页，按标题本地过滤（接口已坐实，绝不空白）。"""
    pool, seen = [], set()
    for cid, _ in CHANNELS:
        for pg in (1, 2):
            for it in _list_docs(cid, pg):
                c = str(it.get('clipId') or '')
                if not c or c in seen:
                    continue
                seen.add(c)
                pool.append(it)
    out = []
    for it in pool:
        name = re.sub(r'<[^>]+>', '', str(it.get('title') or '')).strip()
        if not name or kw not in name:
            continue
        c = str(it.get('clipId') or '')
        pic = _https(it.get('img') or it.get('imgUrlH') or '')
        remark = str(it.get('updateInfo') or it.get('subtitle') or '').strip()
        out.append(_card(c, name, pic, remark, str(it.get('story') or '').strip(),
                         it.get('playPartId') or ''))
    return out


class Spider(_BaseSpider):

    def getName(self):
        return '芒果TV'

    def init(self, extend=""):
        global _SEARCH_MODE
        try:
            # 每次 init 先恢复默认，避免上一次 ext（如 {"direct":0}）残留
            # 导致改回默认配置后仍一直走降级、播放出不来。
            _PLAY.update({'parse': 0, 'jx': 1, 'direct': 1, 'quality': 0,
                          'atref': 1, 'hdrstr': 0})
            _SEARCH_MODE = 'auto'
            ext = (extend or '').strip()
            if ext.startswith('{'):
                c = json.loads(ext)
                if 'parse' in c:
                    _PLAY['parse'] = 1 if str(c.get('parse')) == '1' else 0
                if 'jx' in c:
                    _PLAY['jx'] = 1 if str(c.get('jx')) == '1' else 0
                if 'direct' in c:
                    _PLAY['direct'] = 0 if str(c.get('direct')) == '0' else 1
                if 'atref' in c:
                    _PLAY['atref'] = 1 if str(c.get('atref')) == '1' else 0
                if 'hdr' in c:
                    _PLAY['hdrstr'] = 1 if str(c.get('hdr')) == 'str' else 0
                if c.get('quality'):
                    try:
                        _PLAY['quality'] = int(c.get('quality'))
                    except Exception:
                        pass
                if c.get('search'):
                    _SEARCH_MODE = str(c.get('search'))
        except Exception:
            pass
        return None

    def _classes(self):
        return [{'type_id': cid, 'type_name': cname} for cid, cname in CHANNELS]

    def homeContent(self, filter=False):
        try:
            lst = _category_list('2', 1)
        except Exception:
            lst = []
        # 接口不通/被拦时给兜底卡，绝不让首页全白
        if not lst:
            lst = [_fallback_card()]
        return {'class': self._classes(), 'list': lst}

    def homeVideoContent(self):
        return self.homeContent()

    def categoryContent(self, tid='2', pg='1', filter=False, extend=None):
        try:
            p = int(pg or 1)
        except Exception:
            p = 1
        cid = str(tid or '2')
        if cid not in [x[0] for x in CHANNELS]:
            cid = '2'
        try:
            lst = _category_list(cid, p)
        except Exception:
            lst = []
        if not lst:
            lst = [_fallback_card()]
        return {'list': lst, 'page': p, 'pagecount': 99999,
                'limit': 20, 'total': 999999}

    def detailContent(self, ids):
        cid = str(ids[0]) if isinstance(ids, (list, tuple)) and ids else str(ids)
        # 'web' 前缀 = 官网搜索页入口卡（无专辑ID），直接把网页交给壳解析
        if cid.startswith('web'):
            page = _url_of(cid[3:])
            if not page.startswith('http'):
                page = 'https://www.mgtv.com/'
            return {'list': [{
                'vod_id': cid, 'vod_name': '芒果TV搜索', 'vod_pic': '',
                'vod_content': '芒果TV官网搜索页，由壳解析播放',
                'vod_remarks': '', 'type_name': '',
                'vod_play_from': '壳解析',
                'vod_play_url': '打开搜索页$' + _vid_of(page),
            }]}
        cid = re.sub(r'[^0-9A-Za-z]', '', cid)
        if not cid:
            return {'list': []}
        txt = _fetch('%s?collection_id=%s&page=1&size=50' % (_EPISODE_API, _q(cid)),
                     _HOST + '/')
        eps = []
        info = {}
        if txt and txt.lstrip()[:1] == '{':
            try:
                j = json.loads(txt)
                d = j.get('data') or {}
                info = d.get('info') or {}
                # 芒果接口会混入「彩N」花絮 + 重复集（如 3~7 集各有一份
                # 「看点」版）。按集号去重，同集优先取正片而非「看点」。
                bucket, order = {}, []
                for it in (d.get('list') or []):
                    t1 = str(it.get('t1') or '').strip()
                    if t1 and not t1.isdigit():
                        continue
                    u = str(it.get('url') or '')
                    if u.startswith('/'):
                        u = _HOST + u
                    if not u.startswith('http'):
                        v = str(it.get('video_id') or '')
                        if not v:
                            continue
                        u = '%s/b/%s/%s.html' % (_HOST, cid, v)
                    title = (str(it.get('t4') or '') or str(it.get('t3') or '')
                             or ('第%s集' % t1 if t1 else '')
                             or str(it.get('t2') or '') or '正片').strip() or '正片'
                    key = t1 or str(it.get('video_id') or '') or title
                    clean = 0 if re.search(r'看点|花絮|预告|竖屏|彩蛋|特辑',
                                           str(it.get('t3') or '')) else 1
                    if key not in bucket:
                        order.append(key)
                        bucket[key] = (title, u, clean)
                    elif clean and not bucket[key][2]:
                        bucket[key] = (title, u, clean)
                eps = [bucket[k][:2] for k in order]
            except Exception:
                pass
        # 选集接口偶发空/被拦：用卡片缓存的真实 playPartId 拼当前集播放页
        if not eps:
            pid = (_META.get(cid, {}) or {}).get('part_id') or cid
            eps = [('正片', '%s/b/%s/%s.html' % (_HOST, cid, pid))]
        m = _META.get(cid, {})
        name = m.get('vod_name') or (info.get('title') if isinstance(info, dict) else '') or '芒果TV'
        pic = m.get('vod_pic') or ''
        content = (m.get('vod_content')
                   or (info.get('desc') if isinstance(info, dict) else '')
                   or '芒果TV官网播放页，由壳解析播放')
        # 三条线路（$$$ 分隔），盒端可在播放器里手动切换：
        #   直连        —— m3u8 + TVBox @Referer/@User-Agent 后缀（对全部
        #                  相对分片生效，解决「有视频、播不了」的默认首选）
        #   直连·请求头 —— 纯 m3u8 + header/headers 字典（壳认请求头时用）
        #   壳解析      —— jx:1 把 m 站播放页交给壳自带解析（兜底）
        seg = '#'.join('%s$%s' % (t, _vid_of(u)) for t, u in eps)
        return {'list': [{
            'vod_id': cid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_content': content,
            'vod_remarks': m.get('vod_remarks') or '',
            'type_name': '',
            'vod_play_from': '直连$$$直连·请求头$$$壳解析',
            'vod_play_url': seg + '$$$' + seg + '$$$' + seg,
        }]}

    def searchContent(self, key='', quick=False, pg='1'):
        try:
            p = int(pg or 1)
        except Exception:
            p = 1
        kw = str(key or '').strip()
        out = []
        if kw:
            if _SEARCH_MODE != 'local':
                out = _official_search(kw)
            if not out:
                out = _local_search(kw)
        # 最后兜底：官网搜索页入口，保证搜索页永远不空白
        if not out and kw:
            u = 'https://so.mgtv.com/so?k=' + _q(kw)
            out = [_card(kw, kw + ' (芒果TV搜索)', '', '芒果TV', '在芒果TV搜索「%s」' % kw)]
            out[0]['vod_id'] = 'web' + _vid_of(u)
        return {'list': out, 'page': p, 'pagecount': 1,
                'limit': len(out), 'total': len(out)}

    def playerContent(self, flag='', id='', vipFlags=None):
        try:
            page = _url_of(id)
            if not page.startswith('http'):
                return {'parse': 0, 'url': '', 'jx': 0}
            f = str(flag or '')

            def jx():
                # 降级：m 站播放页（SSR 200）交给壳的解析接口
                mp = page.replace('https://www.mgtv.com/b/',
                                  'https://m.mgtv.com/b/')
                return {'parse': _PLAY['parse'], 'jx': _PLAY['jx'], 'url': mp,
                        'header': {'User-Agent': UA,
                                   'Referer': 'https://m.mgtv.com/'}}

            # 线路「壳解析」或 ext direct:0 -> 直接降级
            if ('壳解析' in f) or not _PLAY.get('direct'):
                return jx()

            m3 = _resolve_m3u8(page)
            if not m3:
                return jx()

            hdr = dict(_REF)
            hv = json.dumps(hdr) if _PLAY.get('hdrstr') else hdr
            # 默认「直连」线路：把头拼成 TVBox @ 后缀。
            # ★ 关键：m3u8 里 283 个 ts 分片是相对路径，分片也要求
            #   UA + Referer 同时存在（缺一即 403）。header 字典在很多壳里
            #   只作用于主 m3u8 请求、不传给分片，所以必须用 @ 后缀契约，
            #   让壳把这两个头应用到该流的全部请求（含所有分片）。
            #   短 UA 不含空格/括号/分号，避免被壳按空格截断 URL。
            if ('请求头' not in f) and _PLAY.get('atref', 1):
                url = (m3 + '@Referer=' + _HOST + '/'
                       + '@User-Agent=' + _SUF_UA)
            else:
                # 线路「直连·请求头」/ ext atref:0：纯净 m3u8 + header 字典
                url = m3
            return {'parse': 0, 'jx': 0, 'url': url,
                    'header': hv, 'headers': hdr}
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
