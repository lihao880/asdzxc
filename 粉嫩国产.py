# -*- coding: utf-8 -*-
# TVBox / 影视仓 / OK影视 / FongMi Python 标准爬虫
# 站点: 粉嫩国产 (pingguodiannao.shop)
# 站型: 苹果CMS V10 + m1938pc 模板 (路由 /index.php/vod/...)
# v1.0 首版, 依据站点实测结构编写:
#   1. 分类 /index.php/vod/type/id/{cid}.html, 分页 /page/{pg}.html,
#      页面自带「共N条数据,当前x/y页」可直接算 total/pagecount
#   2. 搜索 /index.php/vod/search.html?wd=xx (分页 /search/page/{pg}/wd/{q}.html)
#   3. 详情页字段: h2.c_pink=标题 / background-image:url()=封面 /
#      <p>類型：X</p> / <p>更新：YYYY-MM-DD</p>
#   4. 播放页 var player_aaaa={... "url":"https://.../index.m3u8"} 取直链
#   5. m3u8 母清单 -> 根相对子清单(指向另一目录) -> 根相对 .ts (METHOD=NONE)
#      => 默认直连(壳按标准 HLS 自行解析) + 「代理」线路兜底
#   6. 封面 data-aes="true" 但实测为明文 PNG(CT image/jpeg), 无需解密
#   7. 蜘蛛契约: 独立 class / dict header / 三别名会话 / __init__ 自初始化
#      (OK影视 不调 init) / 三级网络降级 / localProxy 4 元组 bytes 正文
import re
import json
import time

try:
    import requests as _requests
except Exception:
    _requests = None

from urllib.parse import quote, urljoin, parse_qs
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler, HTTPSHandler

try:
    import ssl as _ssl
    _SSL_CTX = _ssl._create_unverified_context()
except Exception:
    _SSL_CTX = None


class _Redirect308(HTTPRedirectHandler):
    """兼容 308 永久重定向"""

    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return Request(newurl, headers=dict(req.header_items()),
                       method=req.get_method())


def _opener():
    if _SSL_CTX is not None:
        return build_opener(HTTPSHandler(context=_SSL_CTX), _Redirect308())
    return build_opener(_Redirect308())


class Spider(object):
    """独立 Spider, 不继承 base.spider (壳内加载即白屏的坑)"""

    host = 'https://www.pingguodiannao.shop'
    HOSTS = ('https://www.pingguodiannao.shop', 'https://pingguodiannao.shop')
    UA = ('Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36')
    header = {
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }

    # 站点实测有数据的分类 (3/4/5/12/13 为空壳分类, 不收录)
    classes = [
        {'type_name': '三级电影', 'type_id': '1'},
        {'type_name': '传媒剧情', 'type_id': '2'},
        {'type_name': '欧美无码', 'type_id': '6'},
        {'type_name': '主播自慰', 'type_id': '7'},
        {'type_name': '制服诱惑', 'type_id': '8'},
        {'type_name': '中文字幕', 'type_id': '10'},
        {'type_name': 'AI明星', 'type_id': '11'},
    ]

    # 站点无筛选 UI
    filters = {}

    # 类级兜底默认值: 部分壳(如 OK影视)只做 Spider() 而不调 init(extend)
    m3u8_mode = 'direct'
    s = None
    session = None
    sess = None
    _home_cache = None
    _home_cache_time = 0
    _play_cache = None
    _play_cache_time = 0
    _cat_cache = None

    def __init__(self, *args, **kwargs):
        # 模板契约: __init__ 负责全部实例属性初始化, init(extend) 只解析扩展参数
        self._setup()
        try:
            if args and isinstance(args[0], (str, dict)):
                self.init(args[0])
            elif kwargs:
                self.init(kwargs)
        except Exception:
            pass

    def _setup(self):
        self.host = Spider.host
        self.header = dict(Spider.header)
        self.m3u8_mode = 'direct'
        self.s = self.session = self.sess = _requests.Session() if _requests else None
        self._home_cache = []
        self._home_cache_time = 0
        self._play_cache = {}
        self._play_cache_time = 0
        self._cat_cache = {}

    def getName(self):
        return '粉嫩国产'

    def getDependence(self):
        return []

    def init(self, extend=''):
        self._setup()
        ext = {}
        try:
            if isinstance(extend, str) and extend.strip():
                ext = json.loads(extend)
            elif isinstance(extend, dict):
                ext = extend
        except Exception:
            ext = {}
        # m3u8 模式: 'direct'(默认) / 'proxy'(本地代理重写)
        mode = str(ext.get('m3u8') or ext.get('mode') or '').lower()
        if not mode and ext.get('direct') is True:
            mode = 'direct'
        self.m3u8_mode = 'proxy' if mode in ('proxy', 'local', '1') else 'direct'

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ============================================================
    # TVBox 标准接口
    # ============================================================

    def homeContent(self, filter=None):
        return {'class': self.classes, 'filters': self.filters}

    def homeVideoContent(self):
        now = time.time()
        if self._home_cache and now - self._home_cache_time < 300:
            return {'list': self._home_cache[:60]}
        vods = []
        try:
            for host in self._hosts():
                html = self._fetch_text(host + '/', timeout=12)
                if html and 'vod/detail' in html:
                    vods = self._parse_cards(html)
                    if vods:
                        self._home_cache = vods
                        self._home_cache_time = now
                        break
        except Exception:
            pass
        return {'list': vods[:60]}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        tid = str(tid)
        # 站点分页有缺陷: 第2页会确定性重复第1页尾部(且顺序反转),
        # 直接翻页用户会看到大量重复。改为「合并去重流」:
        # 按需继续抓站点页, 只把没出现过的条目追加进流, 永远从流里切片。
        st = self._cat_state(tid)
        if pg <= 1:
            st['items'] = []
            st['seen'] = set()
            st['fetched'] = 0
            st['total'] = 0
            st['site_pc'] = 1
        need = pg * 30
        guard = 0
        while len(st['items']) < need and guard < 40:
            guard += 1
            nxt = st['fetched'] + 1
            url = '%s/index.php/vod/type/id/%s.html' % (self.host, tid)
            if nxt > 1:
                url = '%s/index.php/vod/type/id/%s/page/%d.html' % (self.host, tid, nxt)
            html = self._fetch_text(url, timeout=15)
            if not html:
                break
            st['fetched'] = nxt
            m = re.search(r'共(\d+)条数据\s*,\s*当前(\d+)/(\d+)页', html)
            if m:
                st['total'] = int(m.group(1))
                st['site_pc'] = int(m.group(3))
            for v in self._parse_cards(html):
                if v['vod_id'] not in st['seen']:
                    st['seen'].add(v['vod_id'])
                    st['items'].append(v)
            if nxt >= st['site_pc']:
                break
        items = st['items'][(pg - 1) * 30:pg * 30]
        total = st['total'] or len(st['items'])
        pagecount = max(1, (total + 29) // 30)
        return {'page': pg, 'pagecount': pagecount, 'limit': 30,
                'total': total, 'list': items}

    def _cat_state(self, tid):
        cache = getattr(self, '_cat_cache', None)
        if cache is None:
            cache = {}
            self._cat_cache = cache
        if tid not in cache:
            cache[tid] = {'items': [], 'seen': set(), 'fetched': 0,
                          'total': 0, 'site_pc': 1}
        return cache[tid]

    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        vod_id = str(ids[0]) if ids else ''
        vod = {
            'vod_id': vod_id, 'vod_name': vod_id, 'vod_pic': '',
            'type_name': '', 'vod_year': '', 'vod_area': '',
            'vod_remarks': '', 'vod_actor': '', 'vod_director': '',
            'vod_content': '', 'vod_play_from': '', 'vod_play_url': '',
        }
        try:
            html = self._fetch_text(
                '%s/index.php/vod/detail/id/%s.html' % (self.host, vod_id),
                timeout=15)
            if not html or 'vod/detail/id/%s' % vod_id not in html:
                return {'list': [vod]}

            vod['vod_name'] = self._detail_title(html) or vod_id
            vod['vod_pic'] = self._detail_pic(html)
            vod['type_name'] = self._detail_type(html)
            vod['vod_remarks'] = self._detail_note(html)

            # 线路: 详情页给 play 页链接, 播放页给真实 m3u8
            play_links = []
            for u in re.findall(
                    r'href="(/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"', html):
                if u not in play_links:
                    play_links.append(u)
            eps = []
            for i, pl in enumerate(play_links):
                real = self._play_url(pl)
                if real:
                    eps.append(('线路%d' % (i + 1), real))
            if not eps:
                # 兜底: 详情页直接出现过 m3u8
                for u in re.findall(r'"(https?://[^"]+\.m3u8)"', html):
                    eps.append(('线路1', u))
                    break

            if eps:
                froms = []
                urls = []
                # ① 直连 (默认)
                froms.append('直连')
                urls.append('#'.join('%s$%s' % (n, u) for n, u in eps))
                # ② 代理 (直连黑屏时的手动退路)
                froms.append('代理')
                urls.append('#'.join('%s$%s' % (n, self._proxy_ep(u))
                                    for n, u in eps))
                vod['vod_play_from'] = '$$$'.join(froms)
                vod['vod_play_url'] = '$$$'.join(urls)
        except Exception:
            pass
        return {'list': [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        key = str(key or '').strip()
        vods = []
        total = 0
        pagecount = 1
        try:
            if key:
                q = quote(key)
                if pg <= 1:
                    url = '%s/index.php/vod/search.html?wd=%s' % (self.host, q)
                else:
                    url = '%s/index.php/vod/search/page/%d/wd/%s.html' % (
                        self.host, pg, q)
                html = self._fetch_text(url, timeout=15)
                if html:
                    vods = self._parse_cards(html)
                    m = re.search(r'共(\d+)条数据\s*,\s*当前(\d+)/(\d+)页', html)
                    if m:
                        total = int(m.group(1))
                        pagecount = int(m.group(3))
                    else:
                        total = len(vods)
                        pagecount = max(1, pg)
        except Exception:
            pass
        return {'page': pg, 'pagecount': pagecount, 'limit': 30,
                'total': total, 'list': vods}

    def playerContent(self, flag, ids, vipFlags=None):
        url = str(ids or '')
        if '$' in url:
            url = url.split('$')[-1].strip()
        hdr = {'User-Agent': self.UA}
        if not url:
            return {'parse': 0, 'url': '', 'header': hdr}
        # 已是本地代理地址 (来自「代理」线路) -> 原样交壳
        if url.startswith('proxy://') or url.startswith('clan://'):
            return {'parse': 0, 'url': url, 'header': hdr,
                    'format': 'application/vnd.apple.mpegurl'}
        low = url.lower()
        if '.m3u8' in low:
            if getattr(self, 'm3u8_mode', 'direct') == 'proxy':
                return {'parse': 0,
                        'url': 'proxy://do=m3u8&url=%s' % quote(url, safe=''),
                        'header': hdr,
                        'format': 'application/vnd.apple.mpegurl'}
            # 默认直连: 壳按标准 HLS 以母清单 URL 解析根相对子清单/分片
            return {'parse': 0, 'url': url, 'header': hdr,
                    'format': 'application/vnd.apple.mpegurl'}
        if '.mp4' in low or '.flv' in low or '.mkv' in low or '.ts' in low:
            return {'parse': 0, 'url': url, 'header': hdr}
        return {'parse': 1, 'url': url, 'header': hdr}

    def localProxy(self, params):
        try:
            if isinstance(params, dict):
                q = (params.get('type') or params.get('param')
                     or params.get('what') or params.get('params') or '')
                if not q and params.get('url'):
                    q = 'url=%s&do=%s' % (quote(str(params.get('url')), safe=''),
                                          str(params.get('do') or ''))
            else:
                q = str(params or '')
            if 'url=' not in q:
                return [404, 'text/plain', b'', None]
            qs = parse_qs(q)
            u = (qs.get('url') or [''])[0]
            do = (qs.get('do') or [''])[0].lower()
            if not u:
                return [404, 'text/plain', b'', None]
            blob = self._fetch_bytes(u, timeout=15)
            if not blob:
                return [404, 'text/plain', b'', None]
            head = blob[:512]
            if do == 'm3u8' or blob[:8].startswith(b'#EXTM3U') or b'#EXT-X-' in head:
                txt = blob.decode('utf-8', 'ignore')
                # 正文必须 bytes: 部分壳直接把第三元素写入 socket
                return [200, 'application/vnd.apple.mpegurl',
                        self._rewrite_m3u8(u, txt).encode('utf-8'), None]
            if head[:1] == b'<':
                # 站点对未知路径返回 200+HTML 兜底页 -> 按正文判失败
                return [404, 'text/plain', b'', None]
            if head[:1] == b'\x47':
                mime = 'video/MP2T'
            elif head[:4] == b'\x89PNG':
                mime = 'image/png'
            elif head[:3] == b'\xff\xd8\xff':
                mime = 'image/jpeg'
            elif head[:6] in (b'GIF87a', b'GIF89a'):
                mime = 'image/gif'
            elif head[:4] == b'RIFF' and blob[8:12] == b'WEBP':
                mime = 'image/webp'
            else:
                mime = 'application/octet-stream'
            return [200, mime, blob, None]
        except Exception:
            return [404, 'text/plain', b'', None]

    # ============================================================
    # 网络层 (壳 -> requests -> urllib 三级降级)
    # ============================================================

    def _hosts(self):
        hs = [self.host]
        for h in Spider.HOSTS:
            if h not in hs:
                hs.append(h)
        return hs

    def _sess(self):
        s = getattr(self, 's', None)
        if s is None and _requests is not None:
            try:
                s = _requests.Session()
            except Exception:
                s = None
            self.s = self.session = self.sess = s
        return s

    def _fetch_bytes(self, url, timeout=20):
        """取原始字节 (站点发完 chunked 不关连接, 用总时长上限防挂起)"""
        hdr = {'User-Agent': self.UA, 'Accept': '*/*',
               'Accept-Language': 'zh-CN,zh;q=0.9'}
        # requests 会自动解 gzip, 不能手工设 Accept-Encoding
        hdr_u = dict(hdr)
        hdr_u['Accept-Encoding'] = 'gzip'
        s = self._sess()
        if s is not None:
            try:
                r = s.get(url, headers=hdr, timeout=(6, timeout), stream=True)
                if getattr(r, 'status_code', 200) >= 400:
                    try:
                        r.close()
                    except Exception:
                        pass
                    return b''
                buf = []
                t0 = time.time()
                for ch in r.iter_content(16384):
                    if not ch:
                        break
                    buf.append(ch)
                    if time.time() - t0 > timeout + 20:
                        break
                try:
                    r.close()
                except Exception:
                    pass
                b = b''.join(buf)
                if b:
                    return b
            except Exception:
                pass
        try:
            req = Request(url, headers=hdr_u)
            r = _opener().open(req, timeout=timeout)
            buf = []
            t0 = time.time()
            while True:
                ch = r.read(16384)
                if not ch:
                    break
                buf.append(ch)
                if time.time() - t0 > timeout + 20:
                    break
            try:
                r.close()
            except Exception:
                pass
            return self._maybe_gunzip(b''.join(buf))
        except Exception:
            return b''

    @staticmethod
    def _maybe_gunzip(b):
        if not b or b[:2] != b'\x1f\x8b':
            return b
        try:
            import gzip as _gz
            return _gz.decompress(b)
        except Exception:
            try:
                import zlib as _zl
                return _zl.decompress(b, 16 + _zl.MAX_WBITS)
            except Exception:
                return b

    def _fetch_text(self, url, timeout=20):
        return self._fetch_bytes(url, timeout=timeout).decode('utf-8', 'ignore')

    # ============================================================
    # 列表解析 (首页 / 分类 / 搜索 同一卡片结构)
    # ============================================================

    def _parse_cards(self, html):
        """按 <li> 块解析卡片 (一卡两锚: 图锚+题锚, 整页正则会互相吞并)"""
        vods = []
        seg = self._main_list(html)
        for block in re.findall(r'<li[^>]*>([\s\S]*?)</li>', seg):
            m = re.search(r'href="(/index\.php/vod/detail/id/(\d+)\.html)"', block)
            if not m:
                continue
            vid = m.group(2)
            t = re.search(r'title="([^"]*)"', block)
            title = (t.group(1) if t else '').strip()
            if not title:
                h3 = re.search(r'<h3[^>]*>([^<]+)</h3>', block)
                title = (h3.group(1) if h3 else '').strip()
            if not title:
                continue
            pic = ''
            p = re.search(r'<img[^>]+(?:data-original|src)="([^"]+)"', block)
            if p:
                pic = p.group(1)
            note = ''
            n = re.search(r'date-text-bg[^"]*">\s*([^<]*?)\s*</p>', block)
            if n:
                note = n.group(1).strip()
            vods.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': self._abs(pic),
                'vod_remarks': note,
            })
        return vods

    @staticmethod
    def _main_list(html):
        """只取主列表区 (排除底部「视频推荐」content-item 块, 避免混入相关视频)"""
        i = html.find('img-list-data')
        if i < 0:
            return ''
        end = len(html)
        for mark in ('pagination', 'center-content-list'):
            j = html.find(mark, i)
            if j > i:
                end = min(end, j)
        return html[i:end]

    @staticmethod
    def _abs(u):
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('http'):
            return u
        return 'https://www.pingguodiannao.shop' + u

    # ============================================================
    # 详情页字段解析
    # ============================================================

    @staticmethod
    def _detail_title(html):
        m = re.search(r'<h2 class="c_pink[^"]*">([^<]+)</h2>', html)
        if m and m.group(1).strip():
            return m.group(1).strip()
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if m and m.group(1).strip():
            return m.group(1).strip()
        m = re.search(r'<title>([^<]+?)(?:详情介绍|在线观看|-)', html)
        if m and m.group(1).strip():
            return m.group(1).strip()
        return ''

    @staticmethod
    def _detail_pic(html):
        # 详情封面: film_info 里的 img, 取 background-image:url() 或 data-original
        m = re.search(r'film_info[\s\S]{0,2000}?background-image:\s*url\(([^)]+)\)', html)
        if m and m.group(1).strip():
            u = m.group(1).strip().strip('\'"')
            if u.startswith('//'):
                return 'https:' + u
            if u.startswith('http'):
                return u
        m = re.search(r'film_info[\s\S]{0,2000}?data-original="([^"]+)"', html)
        if m:
            u = m.group(1).strip()
            if u.startswith('//'):
                return 'https:' + u
            if u.startswith('http'):
                return u
        m = re.search(r'og:image["\']\s+content=["\']([^"\']+)', html)
        if m:
            return m.group(1).strip()
        return ''

    @staticmethod
    def _detail_type(html):
        m = re.search(r'<p>類型[：:]\s*([^<]+)</p>', html)
        if m and m.group(1).strip():
            return m.group(1).strip()
        m = re.search(r'cat_pos[\s\S]{0,400}?vod/type/id/\d+\.html"[^>]*>([^<]+)</a>', html)
        if m:
            return m.group(1).strip()
        return ''

    @staticmethod
    def _detail_note(html):
        m = re.search(r'<p>更新[：:]\s*([^<]+)</p>', html)
        if m and m.group(1).strip():
            return m.group(1).strip()
        return ''

    # ============================================================
    # 播放页解析: var player_aaaa={... "url":"https://.../index.m3u8"}
    # ============================================================

    def _play_url(self, play_path):
        """播放页相对路径 -> 真实 m3u8 地址 (带缓存)"""
        try:
            cache = getattr(self, '_play_cache', None) or {}
            now = time.time()
            if play_path in cache and now - self._play_cache_time < 600:
                return cache[play_path]
            html = self._fetch_text(self._abs(play_path), timeout=15)
            url = ''
            if html:
                m = re.search(r'var\s+player_\w+\s*=\s*\{(.{0,4000}?)\}\s*</script>',
                              html, re.S)
                if m:
                    mm = re.search(r'"url"\s*:\s*"((?:[^"\\]|\\.)*)"', m.group(1))
                    if mm:
                        url = mm.group(1).replace('\\/', '/')
                if not url:
                    mm = re.search(r'"(https?://[^"]+\.m3u8[^"]*)"', html)
                    if mm:
                        url = mm.group(1)
            if url:
                cache[play_path] = url
                self._play_cache = cache
                self._play_cache_time = now
            return url
        except Exception:
            return ''

    @staticmethod
    def _proxy_ep(u):
        """裸 m3u8 -> proxy://do=m3u8&url=<quoted> (代理线路用)"""
        u = str(u or '').strip()
        if not u:
            return u
        return 'proxy://do=m3u8&url=%s' % quote(u, safe='')

    # ============================================================
    # m3u8 重写: 母清单 -> 根相对子清单 -> 根相对 .ts
    # 子清单走本地代理, 分片绝对化直连 (不压垮壳)
    # ============================================================

    def _rewrite_m3u8(self, url, text):
        out = []
        for line in text.splitlines():
            s = line.strip()
            if not s:
                out.append(line)
                continue
            if s.startswith('#'):
                m = re.search(r'URI="([^"]+)"', s)
                if m and not m.group(1).startswith('http'):
                    s = s.replace('URI="%s"' % m.group(1),
                                  'URI="%s"' % urljoin(url, m.group(1)))
                out.append(s)
                continue
            if s.startswith('http'):
                out.append(s)
                continue
            absu = urljoin(url, s)
            if '.m3u8' in absu.lower():
                out.append('proxy://do=m3u8&url=%s' % quote(absu, safe=''))
            else:
                out.append(absu)
        return '\n'.join(out)
