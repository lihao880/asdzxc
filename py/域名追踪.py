# -*- coding: utf-8 -*-
# TVBox 域名追踪器 / 域名池存活监测
# 2026-10-15
#
# 用途: 维护一组站点域名, 自动探测存活、识别主域名(canonical)、跟踪域名轮换。
#      适用于频繁更换域名的资源站 —— 把最新可用域名喂给 TVBox 源使用。
#
# 【机制说明】(逆向自常见联盟推广型站点, 通用做法)
#   1. canonical: <link rel="canonical" href="..."> 通常指向当前正式域名,
#      是多域名部署时的"主域名标识"。探测它可判断某个域名是否已被替换。
#   2. 来源追踪: 部分站点在链接后追加 ?ck=<来源域名>, 用于联盟分成统计。
#      仅影响点击统计, 不影响页面内容, 属于常规做法。
#   3. 域名池: 导航页(如 /active, /daohang, /nav 等)通常列出当前可用的
#      全部备用域名, 是发现新域名的主要来源。
#
# 【重要】请只对本工具填写你自己有权访问/管理的域名。
# 本工具不内置任何域名, 需要你自行配置 DOMAINS / POOL_URLS。
#
# 学习用途, 请遵守当地法律法规
import os
import re
import sys
import json
import time
import ssl
import socket
import urllib.parse
import urllib.request
import concurrent.futures

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider(object):
        pass

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
_CTX.timeout = 8

# ============ 配置区: 填你自己的域名 ============
# 待监测的域名(不带协议)
DOMAINS = [
    # 'your-domain-1.com',
    # 'your-domain-2.net',
]
# 域名池页面(导航页), 从页面里自动提取当前可用域名
POOL_URLS = [
    # 'https://example.com/active',
]
# 构建请求时要把域名拼到哪个路径上做存活判断
PROBE_PATH = '/'
# 存活判定关键词(页面里出现任一即认为有效, 留空则不校验内容)
PROBE_MARKERS = []
# 缓存/持久化文件 (跨进程复用, 免每次冷启动重测)
STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '.domain_tracker.json')
# ==============================================

TIMEOUT = 8
MAX_WORKERS = 16


def _log(*a):
    try:
        sys.stderr.write('[域名追踪] ' + ' '.join(str(x) for x in a) + '\n')
    except Exception:
        pass


def _norm(host):
    """归一化: 去协议、去路径、去端口、转小写"""
    if not host:
        return ''
    h = host.strip().lower()
    h = re.sub(r'^[a-z]+://', '', h)
    h = h.split('/')[0].split('?')[0].split('#')[0]
    h = h.split('@')[-1]
    h = re.sub(r':\d+$', '', h)
    return h


def _http(url, timeout=TIMEOUT, allow_redirect=True):
    """返回 (status_code, final_url, text); 失败返回 (0, url, '')"""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': UA, 'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9'})
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_CTX))
        if not allow_redirect:
            class _NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **k):
                    return None
            opener = urllib.request.build_opener(
                _NoRedirect(), urllib.request.HTTPSHandler(context=_CTX))
        resp = opener.open(req, timeout=timeout)
        raw = resp.read()
        if raw[:2] == b'\x1f\x8b':
            import gzip
            raw = gzip.decompress(raw)
        txt = ''
        for enc in ('utf-8', 'gbk'):
            try:
                txt = raw.decode(enc)
                break
            except Exception:
                continue
        if not txt:
            txt = raw.decode('utf-8', 'ignore')
        return resp.getcode() or 200, resp.geturl(), txt
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode('utf-8', 'ignore')
        except Exception:
            pass
        return e.code, url, body
    except Exception as e:
        _log('请求失败', url[:60], repr(e)[:50])
        return 0, url, ''


def _dns_ok(host):
    """DNS 解析检测(比 HTTP 更轻, 但站点可能靠 CDN 泛解析)"""
    try:
        socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        return True
    except Exception:
        return False


def extract_domains(text, base_host=''):
    """从 HTML 里提取域名:
    - <a href="http..."> 外链
    - 纯文本里出现的域名
    过滤掉统计/图床/第三方 CDN 等无关域名"""
    if not text:
        return []
    found = set()
    # 1) 显式链接
    for m in re.finditer(r'https?://([a-zA-Z0-9][a-zA-Z0-9._-]*\.[a-zA-Z]{2,})',
                         text):
        found.add(_norm(m.group(1)))
    # 2) 裸域名 (可能出现在 JS 数组或文本里)
    for m in re.finditer(
            r'(?<![\w.-])((?:[a-zA-Z0-9][a-zA-Z0-9-]{0,62}\.)+'
            r'(?:com|net|org|xyz|top|cc|vip|link|buzz|mom|cn|io|me|tv|info|site)'
            r'(?::\d+)?)', text):
        found.add(_norm(m.group(1)))
    # 3) 过滤噪音域
    noise = ('google', 'gstatic', 'googletagmanager', 'googleapis', 'yandex',
             'cloudflare', 'cdn.jsdelivr', 'jsdelivr', 'unpkg', 'bootstrapcdn',
             'baidu.com', 'schema.org', 'w3.org', 'miit.gov.cn', 'beian',
             'facebook', 'twitter', 'doubleclick', 'google-analytics',
             'umami', 'plausible', 'sentry', 'wixstatic')
    # 常见图床/静态资源 / 统计子域前缀 (可通过 PROBE_MARKERS 之外的场景自行调整)
    noise_prefix = ('pic.', 'img.', 'img1.', 'img2.', 'cdn.', 'static.',
                    'static1.', 'assets.', 'm.stat', 'nplausible.', 'stat.',
                    'tj.', 'tongji.', 'hm.', 'collect.')
    out = []
    for d in found:
        if not d or d == base_host:
            continue
        if any(n in d for n in noise):
            continue
        if d.startswith(noise_prefix):
            continue
        if len(d.split('.')) < 2:
            continue
        out.append(d)
    return sorted(set(out))


def canonical_of(text):
    """提取 <link rel=canonical> 指向的域名 —— 主域名标识"""
    if not text:
        return ''
    m = re.search(r'<link[^>]*rel=["\']?canonical["\']?[^>]*href=["\']([^"\']+)',
                  text, re.I)
    if not m:
        m = re.search(r'href=["\']([^"\']+)["\'][^>]*rel=["\']?canonical',
                      text, re.I)
    return _norm(m.group(1)) if m else ''


def probe_domain(host):
    """探测单个域名存活, 返回结构化结果"""
    host = _norm(host)
    if not host:
        return None
    res = {'host': host, 'dns': False, 'status': 0, 'alive': False,
           'final': '', 'canonical': '', 'marker_hit': None, 'elapsed': 0}
    t0 = time.time()
    res['dns'] = _dns_ok(host)
    if not res['dns']:
        return res
    url = 'https://%s%s' % (host, PROBE_PATH)
    code, final, txt = _http(url)
    res['status'] = code
    res['final'] = _norm(final)
    res['canonical'] = canonical_of(txt)
    if PROBE_MARKERS and txt:
        for mk in PROBE_MARKERS:
            if mk in txt:
                res['marker_hit'] = mk
                break
    # 存活判定: 2xx/3xx 且 (无marker要求 或 marker命中)
    ok_code = 200 <= code < 400
    ok_marker = (not PROBE_MARKERS) or bool(res['marker_hit'])
    res['alive'] = bool(ok_code and ok_marker)
    res['elapsed'] = round(time.time() - t0, 2)
    return res


def probe_all(domains, workers=MAX_WORKERS):
    """并发探测一组域名"""
    domains = sorted(set(_norm(d) for d in domains if _norm(d)))
    out = {}
    if not domains:
        return out
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(probe_domain, d): d for d in domains}
        for f in concurrent.futures.as_completed(futs):
            try:
                r = f.result()
                if r:
                    out[r['host']] = r
            except Exception as e:
                _log('探测异常', repr(e)[:50])
    return out


def harvest_pool(urls=None):
    """从域名池页面提取当前可用域名"""
    urls = urls if urls else POOL_URLS
    pool = set()
    for u in urls:
        if not u:
            continue
        code, final, txt = _http(u)
        base = _norm(final)
        if code and txt:
            for d in extract_domains(txt, base):
                pool.add(d)
        _log('池页', u[:50], 'HTTP', code, '提取', len(pool))
    return sorted(pool)


# ---------- 状态持久化 ----------
def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(st):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(st, f, ensure_ascii=False, indent=1)
    except Exception as e:
        _log('保存状态失败', repr(e)[:50])


def track(domains=None, pool_urls=None, save=True):
    """主流程: 池页收割 → 全量探测 → 汇总 → 持久化
    返回 {'alive': [...], 'dead': [...], 'canonical_map': {...}, 'best': str}"""
    domains = list(domains if domains else DOMAINS)
    pool = harvest_pool(pool_urls) if (pool_urls or POOL_URLS) else []
    all_d = sorted(set([_norm(d) for d in domains if d] + pool))
    res = probe_all(all_d)

    alive = [h for h, r in res.items() if r['alive']]
    dead = [h for h, r in res.items() if not r['alive']]
    # canonical 归属: 若某域名 page 的 canonical 指向另一域名, 则该另一域名是主域
    canon = {}
    for h, r in res.items():
        c = r.get('canonical')
        if c and c != h:
            canon[h] = c
    main_set = sorted(set(canon.values()))
    # 选优: 优先 canonical 主域, 其次响应最快
    pool_alive = [h for h in alive if h in main_set] or alive
    best = ''
    if pool_alive:
        pool_alive.sort(key=lambda h: res[h].get('elapsed', 99))
        best = pool_alive[0]

    st = load_state()
    st['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    st['alive'] = alive
    st['dead'] = dead
    st['canonical_map'] = canon
    st['main_domains'] = main_set
    st['best'] = best
    st['detail'] = {h: {k: v for k, v in r.items() if k != 'host'}
                    for h, r in res.items()}
    if save:
        save_state(st)
    return {'alive': alive, 'dead': dead, 'canonical_map': canon,
            'main_domains': main_set, 'best': best, 'detail': res}


# ---------- TVBox 接口 (仅暴露域名状态, 不含任何影视内容) ----------
class Spider(_BaseSpider):
    """把域名追踪结果包装成 TVBox 可读的"分类", 便于在客户端查看域名状态"""

    def getName(self):
        return "域名追踪"

    def init(self, extend=""):
        # extend 可传 JSON: {"domains":[...], "pool_urls":[...]}
        self._cfg = {}
        if extend:
            try:
                self._cfg = json.loads(extend)
            except Exception:
                self._cfg = {}
        self._domains = self._cfg.get('domains') or DOMAINS
        self._pool = self._cfg.get('pool_urls') or POOL_URLS

    def destroy(self):
        pass

    def homeContent(self, filter):
        return {
            "class": [
                {"type_id": "alive", "type_name": "存活域名"},
                {"type_id": "dead", "type_name": "失效域名"},
                {"type_id": "main", "type_name": "主域名"},
            ],
            "filters": {},
        }

    def homeVideoContent(self):
        return {"list": self._status_vods()}

    def _status_vods(self):
        st = load_state()
        if not st:
            r = track(self._domains, self._pool)
            st = load_state()
        vods = []
        for h in st.get('alive', []):
            d = (st.get('detail') or {}).get(h, {})
            vods.append({
                "vod_id": 'alive|' + h,
                "vod_name": h,
                "vod_pic": '',
                "vod_remarks": '存活 %ss' % d.get('elapsed', '?'),
            })
        return vods

    def categoryContent(self, tid, pg, filter, extend):
        st = load_state()
        if not st:
            track(self._domains, self._pool)
            st = load_state()
        if tid == 'dead':
            hosts = st.get('dead', [])
        elif tid == 'main':
            hosts = st.get('main_domains', [])
        else:
            hosts = st.get('alive', [])
        vods = [{"vod_id": '%s|%s' % (tid, h), "vod_name": h, "vod_pic": '',
                 "vod_remarks": ''} for h in hosts]
        return {"list": vods, "page": 1, "pagecount": 1,
                "limit": len(vods) or 1, "total": len(vods)}

    def searchContent(self, key, quick, pg="1"):
        """搜索: 输入域名则实时探测; 输入关键词则在已知池里模糊匹配"""
        out = []
        k = (key or '').strip()
        if not k:
            return {"list": []}
        st = load_state()
        known = set(st.get('alive', []) + st.get('dead', []))
        if re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', k):
            r = probe_domain(k)
            if r:
                out.append({"vod_id": 'probe|' + r['host'],
                            "vod_name": r['host'],
                            "vod_pic": '',
                            "vod_remarks": '存活' if r['alive'] else
                                           ('HTTP %s' % r['status'])})
        else:
            for h in sorted(known):
                if k.lower() in h.lower():
                    out.append({"vod_id": 'hit|' + h, "vod_name": h,
                                "vod_pic": "", "vod_remarks": ""})
        return {"list": out, "page": 1}

    def detailContent(self, array):
        vid = str(array[0] if isinstance(array, list) else array)
        host = vid.split('|')[-1]
        r = probe_domain(host)
        if not r:
            return {"list": []}
        content = json.dumps(r, ensure_ascii=False, indent=2)
        vod = {
            "vod_id": vid, "vod_name": host, "vod_pic": "",
            "vod_year": "", "vod_area": "",
            "vod_remarks": '存活' if r['alive'] else '失效',
            "vod_actor": 'DNS=%s HTTP=%s' % (r['dns'], r['status']),
            "vod_content": content,
            "vod_play_from": '域名信息',
            "vod_play_url": '状态$%s' % host,
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        """不走播放, 只回探测详情页(避免误用)"""
        return {"parse": 0, "playUrl": "", "url": "", "header": {"User-Agent": UA}}


# ---------- 命令行自测 ----------
if __name__ == '__main__':
    args = sys.argv[1:]
    if args and args[0] == 'track':
        ds = args[1:] or None
        r = track(ds, POOL_URLS)
        print('存活 %d | 失效 %d' % (len(r['alive']), len(r['dead'])))
        if r['best']:
            print('推荐主域:', r['best'])
        for h in r['alive']:
            d = r['detail'][h]
            print('  [OK] %-40s %sms  canonical=%s'
                  % (h, int(d['elapsed'] * 1000), d['canonical'] or '-'))
        for h in r['dead']:
            d = r['detail'][h]
            print('  [--] %-40s dns=%s http=%s' % (h, d['dns'], d['status']))
    elif args and args[0] == 'harvest':
        pool = harvest_pool(args[1:] or None)
        print('池内域名 %d 个:' % len(pool))
        for d in pool:
            print('  ', d)
    else:
        print('用法:')
        print('  python3 domain_tracker.py track [域名...]   # 探测存活')
        print('  python3 domain_tracker.py harvest [池页URL...]  # 收割域名池')
        print('  先在本文件 DOMAINS / POOL_URLS 配置你的域名')

# 学习用途
