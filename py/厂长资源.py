# -*- coding: utf-8 -*-
# TVBox/影视仓 Python 爬虫 - 厂长资源 cddxfz.com
# 站点类型: MacCMS V10 (苹果CMS) 模板站, 播放页 player_aaaa 明文 m3u8 (encrypt=0)
# 2026-10-15 实测: 列表/详情/播放/搜索 四链路全通
#
# 【设计要点】
#   1. 明文直取: 播放页 JSON encrypt=0, 直接正则提 player_aaaa.url, 无需解密
#   2. 搜索走 ajax/suggest JSON 接口, 比解析 HTML 稳
#   3. 三级容错: 主域名失效自动切备用; 解析失败返回空列表不抛异常
#   4. 云播优先: 详情页多线路, 优先选含 m3u8 直链的线路聚合
# 学习用途, 请遵守当地法律法规
import re
import sys
import time
import json
import html
import urllib.parse
import urllib.request
import ssl

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider(object):
        pass

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
HOSTS = ['https://cddxfz.com', 'https://www.cddxfz.com']
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
_CACHE = {}

# 分类: (type_id, 名称) —— type_id 即 MacCMS 的 vodshow 分类号
TYPES = [
    (6, '动作片'), (7, '喜剧片'), (8, '爱情片'), (9, '科幻片'), (10, '恐怖片'),
    (11, '剧情片'), (12, '战争片'), (20, '纪录片'), (29, '犯罪片'), (39, '动漫片'),
    (13, '国产剧'), (14, '港台剧'), (15, '日韩剧'), (16, '欧美剧'), (21, '泰剧'), (35, '海外剧'),
    (22, '内地综艺'), (23, '港台综艺'), (24, '日韩综艺'), (25, '欧美综艺'),
    (26, '国漫'), (27, '日漫'), (28, '欧美动漫'), (34, '海外动漫'),
]

SORT = [('time', '按时间'), ('hits', '按人气'), ('score', '按评分')]


def _log(*a):
    try:
        sys.stderr.write('[厂长] ' + ' '.join(str(x) for x in a) + '\n')
    except Exception:
        pass


# ---------- HTTP ----------
def _http(url, headers=None, timeout=15, tries=2):
    h = {'User-Agent': UA, 'Accept': '*/*',
         'Accept-Language': 'zh-CN,zh;q=0.9', 'Referer': HOSTS[0] + '/'}
    if headers:
        h.update(headers)
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=h)
            resp = urllib.request.urlopen(req, timeout=timeout, context=_CTX)
            raw = resp.read()
            if raw[:2] == b'\x1f\x8b':           # 手动解 gzip, 避免依赖
                import gzip
                raw = gzip.decompress(raw)
            for enc in ('utf-8', 'gbk'):
                try:
                    return raw.decode(enc)
                except Exception:
                    continue
            return raw.decode('utf-8', 'ignore')
        except Exception as e:
            _log('请求失败(%d/%d)' % (i + 1, tries), url[:80], repr(e)[:60])
            time.sleep(0.3)
    return ''


def _cache_get(k):
    v = _CACHE.get(k)
    if v and v[0] > time.time():
        return v[1]
    if v:
        _CACHE.pop(k, None)
    return None


def _cache_set(k, val, ttl=300):
    if len(_CACHE) > 256:
        _CACHE.clear()
    _CACHE[k] = (time.time() + ttl, val)


def _get(url, ttl=300):
    ck = 'G|' + url
    hit = _cache_get(ck)
    if hit is not None:
        return hit
    txt = _http(url)
    _cache_set(ck, txt, ttl if txt else 60)   # 失败短 TTL, 不固化抖动
    return txt


def _base():
    hit = _cache_get('BASE')
    if hit:
        return hit
    for hh in HOSTS:
        if _http(hh + '/', timeout=8, tries=1):
            _cache_set('BASE', hh, 3600)
            return hh
    _cache_set('BASE', HOSTS[0], 600)
    return HOSTS[0]


# ---------- 解析 ----------
def _clean(s):
    if not s:
        return ''
    s = re.sub(r'<[^>]+>', '', s)
    return html.unescape(s).strip()


def _abs(href):
    """相对链接补全为绝对链接"""
    if not href:
        return ''
    if href.startswith('//'):
        return 'https:' + href
    if href.startswith('/'):
        return _base() + href
    if href.startswith('http'):
        return href
    return _base() + '/' + href.lstrip('/')


def _parse_list(page_html):
    """解析 stui-vodlist 卡片流 → TVBox vod 列表
    卡片形如:
      <a class="stui-vodlist__thumb lazyload" href="/cdvoddetail/ID.html"
         title="名称" data-original="封面图">
         <span class="pic-text text-right">备注</span></a>"""
    vods, seen = [], set()
    if not page_html:
        return vods
    for m in re.finditer(r'<a[^>]*stui-vodlist__thumb[^>]*>(.*?)</a>',
                         page_html, re.S):
        tag, inner = m.group(0), m.group(1)
        href = re.search(r'href="([^"]+)"', tag)
        if not href:
            continue
        vid = re.search(r'/(\d+)\.html', href.group(1))
        if not vid or vid.group(1) in seen:
            continue
        title = re.search(r'title="([^"]*)"', tag)
        pic = re.search(r'data-original="([^"]+)"', tag)
        rem = re.search(r'<span class="pic-text[^"]*">([^<]*)</span>', inner)
        seen.add(vid.group(1))
        vods.append({
            "vod_id": vid.group(1),
            "vod_name": html.unescape(title.group(1)) if title else '',
            "vod_pic": _abs(pic.group(1)) if pic else '',
            "vod_remarks": _clean(rem.group(1)) if rem else '',
        })
    return vods


def _list_url(tid, pg, sort='time'):
    """MacCMS 筛选 URL: cdvodshow/{分类}--{排序}--------{页码}---.html
    实测锚点(勿改):
      第1页 6--time---------   (分类/排序各占段, 尾部 9 个 '-', 页码位留空)
      第2页 6--------2---      (分类后 8 个 '-', 页码段, 再 3 个 '-')
    空页码时尾部固定 9 个 '-'。"""
    p = int(pg)
    if p <= 1:
        return '%s/cdvodshow/%s--%s---------.html' % (_base(), tid, sort)
    return '%s/cdvodshow/%s--------%d---.html' % (_base(), tid, p)


# ---------- Spider ----------
class Spider(_BaseSpider):

    def getName(self):
        return "厂长资源"

    def init(self, extend=""):
        self.base = _base()

    def destroy(self):
        pass

    def homeContent(self, filter):
        classes = [{"type_id": str(t), "type_name": n} for t, n in TYPES]
        filters = {}
        for t, _ in TYPES:
            filters[str(t)] = [{
                "key": "sort", "name": "排序",
                "value": [{"n": n, "v": v} for v, n in SORT]}]
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        vods = _parse_list(_get(_list_url(6, 1, 'time'), ttl=600))
        return {"list": vods[:36]}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = max(1, int(pg))
        except Exception:
            pg = 1
        sort = 'time'
        if isinstance(extend, dict):
            sort = extend.get('sort') or sort
        if sort not in ('time', 'hits', 'score'):
            sort = 'time'
        vods = _parse_list(_get(_list_url(tid, pg, sort)))
        return {
            "list": vods, "page": pg,
            "pagecount": pg + 1 if len(vods) >= 20 else pg,
            "limit": 20, "total": 999999 if vods else 0,
        }

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = max(1, int(pg))
        except Exception:
            pg = 1
        if not key:
            return {"list": [], "page": pg}
        # 优先走 ajax/suggest JSON 接口 (稳)
        url = '%s/index.php/ajax/suggest?mid=1&wd=%s' % (
            _base(), urllib.parse.quote(key))
        try:
            j = json.loads(_get(url, ttl=180) or '{}')
            arr = j.get('list') or []
            vods = []
            for it in arr:
                vods.append({
                    "vod_id": str(it.get('id')),
                    "vod_name": it.get('name') or '',
                    "vod_pic": it.get('pic') or '',
                    "vod_remarks": '',
                })
            if vods:
                return {"list": vods, "page": pg}
        except Exception as e:
            _log('suggest 异常', repr(e)[:60])
        # 兜底: 搜索 HTML 页
        surl = '%s/index.php/vod/search/page/%d/wd/%s.html' % (
            _base(), pg, urllib.parse.quote(key))
        return {"list": _parse_list(_get(surl, ttl=180)), "page": pg}

    def detailContent(self, array):
        vid = str(array[0] if isinstance(array, list) else array)
        m = re.search(r'\d+', vid)
        if not m:
            return {"list": []}
        vid = m.group(0)
        url = '%s/cdvoddetail/%s.html' % (_base(), vid)
        h = _get(url, ttl=600)

        vod = {"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_content": "",
               "vod_year": "", "vod_area": "", "vod_actor": "", "vod_remarks": ""}
        if not h:
            return {"list": [vod]}

        # 基础信息
        t = re.search(r'<h1[^>]*>(.*?)</h1>', h, re.S)
        if t:
            vod["vod_name"] = _clean(t.group(1))
        p = re.search(r'<img[^>]+(?:data-original|src)="([^"]+)"[^>]*class="[^"]*lazyload', h)
        if not p:
            p = re.search(r'class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]+)"', h)
        if p:
            vod["vod_pic"] = _abs(p.group(1))

        def _meta(label):
            """字段形如: <span class="text-muted">地区：</span>
                          <a href="...">中国大陆</a>&nbsp;<span class="split-line"></span>
                          <span>年份：</span>...
            用 split-line 切断, 只取本字段段落内所有 <a> 文本"""
            mm = re.search(r'<span[^>]*>\s*' + label + r'[：:]\s*</span>(.*?)'
                           r'(?:<span class="split-line"|</p>)', h, re.S)
            if not mm:
                mm = re.search(label + r'[：:]\s*([^<]*)', h)
                return _clean(mm.group(1)) if mm else ''
            seg = mm.group(1)
            vals = [_clean(v) for v in re.findall(r'<a[^>]*>([^<]+)</a>', seg)]
            vals = [v for v in vals if v]
            return '/'.join(vals) if vals else _clean(seg)

        vod["vod_area"] = _meta('地区')
        yr = re.search(r'(\d{4})', _meta('年份'))
        vod["vod_year"] = yr.group(1) if yr else ''
        vod["vod_actor"] = _meta('主演')
        blurb = re.search(r'(?:简\s*介|剧情介绍)[：:]?\s*</strong>?\s*(.*?)</p>', h, re.S)
        if not blurb:
            blurb = re.search(r'简介[：:]\s*(.*?)</(?:p|div)>', h, re.S)
        if blurb:
            vod["vod_content"] = _clean(blurb.group(1))

        # 备注: 从页面 remark 或从播放列表推
        rk = re.search(r'<span class="pic-text[^"]*">([^<]*)</span>', h)
        if rk:
            vod["vod_remarks"] = _clean(rk.group(1))

        # 播放线路: 逐源解析 —— 用 (源序号, 集数) 二元组精确配对集名, 不跨源错位
        # 捕获 <a href=".../cdvodplay/{vid}-{sid}-{nid}.html" ...>集名</a>
        srcs = {}
        for mm in re.finditer(
                r'<a[^>]+href="[^"]*cdvodplay/%s-(\d+)-(\d+)\.html"[^>]*>\s*([^<]*?)\s*</a>'
                % vid, h):
            sid, nid, nm = int(mm.group(1)), int(mm.group(2)), _clean(mm.group(3))
            srcs.setdefault(sid, {})[nid] = nm or ('第%d集' % nid)

        # 线路名: 播放区块标题 (线路W / 高清线路 / 线路G ...)
        names = re.findall(r'<h[34][^>]*>\s*([^<>]{1,14}?)\s*</h[34]>', h)
        names = [n for n in names if re.search(r'线路|高清|播放', n)]

        play_from, play_url = [], []
        for i, sid in enumerate(sorted(srcs.keys())):
            eps = srcs[sid]
            fname = names[i] if i < len(names) else ('线路%s' % sid)
            items = ['%s$%s-%s-%s' % (eps[nid], vid, sid, nid)
                     for nid in sorted(eps.keys())]
            play_from.append(_clean(fname) or ('线路%s' % sid))
            play_url.append('#'.join(items))

        if not play_from:  # 兜底
            play_from = ['厂长资源']
            play_url = ['第01集$%s-1-1' % vid]

        vod["vod_play_from"] = '$$$'.join(play_from)
        vod["vod_play_url"] = '$$$'.join(play_url)
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        """id 形如 {vid}-{sid}-{nid}; 请求播放页正则提 player_aaaa.url"""
        pid = str(id or '')
        header = {"User-Agent": UA, "Referer": _base() + '/'}
        m = re.fullmatch(r'(\d+)-(\d+)-(\d+)', pid)
        if not m:
            return {"parse": 0, "playUrl": "", "url": "", "header": header}
        vid, sid, nid = m.group(1), m.group(2), m.group(3)
        purl = '%s/cdvodplay/%s-%s-%s.html' % (_base(), vid, sid, nid)
        h = _get(purl, ttl=300)
        if not h:
            return {"parse": 0, "playUrl": "", "url": "", "header": header}

        url = ''
        # 主路径: player_aaaa JSON 里的 url
        mm = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', h, re.S)
        if mm:
            try:
                j = json.loads(mm.group(1))
                url = j.get('url') or ''
            except Exception as e:
                _log('player_aaaa 解析异常', repr(e)[:60])
        # 兜底: 任意 m3u8 直链
        if not url:
            m2 = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', h)
            if m2:
                url = m2.group(1)
        try:
            url = url.encode('utf-8').decode('unicode_escape')
        except Exception:
            pass
        url = url.replace('\\/', '/')
        return {"parse": 0, "playUrl": "", "url": url, "header": header}


# 学习用途
