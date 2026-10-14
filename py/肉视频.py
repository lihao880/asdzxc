# -*- coding: utf-8 -*-
import sys
import re
import json
import time
import zlib
import struct
import base64
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from lxml import etree

sys.path.append('..')
from base.spider import Spider

PNG_MAGIC = bytes([137, 80, 78, 71, 13, 10, 26, 10])


def unwrap_png(data):
    """提取 PNG 中自定义 roUd 块的真实载荷：首字节为标志位，奇数表示 zlib 压缩。"""
    if not data or data[:8] != PNG_MAGIC:
        return None
    pos = 8
    try:
        while pos + 8 <= len(data):
            length = struct.unpack('>I', data[pos:pos + 4])[0]
            ctype = data[pos + 4:pos + 8]
            payload = data[pos + 8:pos + 8 + length]
            if ctype == b'roUd':
                body = payload[1:]
                return zlib.decompress(body) if (payload[0] & 1) else body
            pos += 8 + length + 4
    except Exception:
        return None
    return None


LOG_FILE = '/storage/emulated/0/tvbox/cache/rou_proxy.log'


def log(msg):
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(time.strftime('%H:%M:%S ') + str(msg) + '\n')
    except Exception:
        pass


class Spider(Spider):
    DIZHI_URLS = ['https://rdz3.xyz/dizhi', 'https://rou.pub/dizhi']
    BACKUP_HOSTS = ['https://rouva8.xyz', 'https://rou.video', 'https://rouva5.xyz', 'https://roum28.xyz']
    CLASSES = ['自拍流出', '國產AV', '探花', '日本', '麻豆傳媒', 'OnlyFans']

    def __init__(self):
        self.home_url = None
        self.real_home = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; PLA-AL10 Build/HUAWEIPLA-AL10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.200 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cookie": "over18=1; age_verified=1",
        }
        self._session = requests.Session()
        self._filters = None
        self._filters_ts = 0
        self._manifest = {}
        self._seg_cache = {}
        self._next_seg = {}
        self._lock = threading.Lock()

    def getName(self):
        return "Rou"

    # ---------- 初始化与域名 ----------
    def init(self, extend=""):
        user_host = ''
        if extend:
            try:
                ext = json.loads(extend) if isinstance(extend, str) else extend
                user_host = (ext.get('host') or '').rstrip('/')
            except Exception:
                pass
        self.home_url = None
        self._filters = None
        if user_host and self._check_host_valid(user_host):
            self.home_url = user_host
        if not self.home_url:
            self.home_url = self._fetch_host_from_dizhi()
        if not self.home_url:
            self.home_url = self._quick_check_host(self.BACKUP_HOSTS)
        if not self.home_url:
            self.home_url = self.BACKUP_HOSTS[0]
        self.real_home = self.home_url + '/home'

    def _check_host_valid(self, host):
        try:
            r = self._session.get(host.rstrip('/') + '/home', headers=self.headers, timeout=6)
            return r.status_code == 200 and '/v/' in r.text
        except Exception:
            return False

    def _quick_check_host(self, hosts):
        hosts = [h.rstrip('/') for h in hosts if h]
        if not hosts:
            return None
        with ThreadPoolExecutor(max_workers=min(len(hosts), 6)) as ex:
            fmap = {ex.submit(self._check_host_valid, h): h for h in hosts}
            for f in as_completed(fmap):
                if f.result():
                    return fmap[f]
        return None

    def _fetch_host_from_dizhi(self):
        for dizhi in self.DIZHI_URLS:
            try:
                r = self._session.get(dizhi, headers=self.headers, timeout=8)
                if r.status_code != 200:
                    continue
                m = re.search(r'<h2>肉視頻</h2>(.*?)</section>', r.text, re.S)
                if not m:
                    continue
                for label in ['科學地址', '永久地址']:
                    mm = re.search(label + r'</a><span class="url">(https?://[^<]+)</span>', m.group(1))
                    if mm and self._check_host_valid(mm.group(1).rstrip('/')):
                        return mm.group(1).rstrip('/')
            except Exception:
                continue
        return None

    # ---------- 基础请求 ----------
    def _get(self, url, extra=None, timeout=8):
        headers = self.headers.copy()
        if extra:
            headers.update(extra)
        try:
            return self._session.get(url, headers=headers, timeout=timeout)
        except Exception:
            return None

    def _tsr_data(self, text):
        """TanStack Router $_TSR 序列化岛：按页面特征提取为类 pageProps 结构。"""
        if not text or '$_TSR' not in text:
            return {}
        out = {}
        # /series 列表
        m = re.search(r'\{list:\$R\[\d+\]=\[(.*?)\],total:(\d+),totalPage:(\d+)', text, re.S)
        if m:
            items = [{'id': b.group(1), 'name': b.group(2),
                      'episodeCount': int(b.group(3)), 'coverImageUrl': b.group(4)}
                     for b in re.finditer(r'\{id:"([^"]+)",name:"([^"]*)"(?:,status:"[^"]*")?,episodeCount:(\d+),totalEpisodes:\d+[^}]*?coverImageUrl:"([^"]*)"', m.group(1))]
            out = {'list': items, 'total': int(m.group(2)), 'totalPage': int(m.group(3))}
        # /s/ 详情：series + episodes
        sm = re.search(r'series:\$R\[\d+\]=\{id:"([^"]+)",name:"([^"]*)"(?:,status:"[^"]*")?,episodeCount:(\d+),totalEpisodes:\d+.*?tags:\$R\[\d+\]=\[(.*?)\],createdAt:"([^"]*)"', text)
        if sm:
            ser = {'id': sm.group(1), 'name': sm.group(2), 'episodeCount': int(sm.group(3)),
                   'tags': re.findall(r'"([^"]+)"', sm.group(4)), 'createdAt': sm.group(5)}
            ci = re.search(r'series:\$R\[\d+\]=\{.*?coverImageUrl:"([^"]*)"', text)
            ser['coverImageUrl'] = ci.group(1) if ci else ''
            eps = [{'id': b.group(1), 'episode': int(b.group(2))}
                   for b in re.finditer(r'\{id:"([^"]+)",name:"[^"]*",episode:(\d+),duration:[\d.]+', text)]
            out = {'series': ser, 'episodes': eps}
        # /cat 页 taxonomy（genre 全局类型 + byParent 各分类子项）
        if 'byParent:' in text:
            tax = {'genre': [], 'byParent': {}}
            gm = re.search(r'genre:\$R\[\d+\]=\[(.*?)\]\s*,', text, re.S)
            if gm:
                tax['genre'] = [{'id': x.group(1), 'count': int(x.group(2))}
                                for x in re.finditer(r'\{id:"([^"]+)",count:(\d+)\}', gm.group(1))][:80]
            bm = re.search(r'byParent:\$R\[\d+\]=\{(.*)\}', text, re.S)
            if bm:
                # 内层元素被 $R[n]= 包裹，按下一个父分类边界切段
                inner = bm.group(1)
                bounds = [(mm.start(1), mm.group(1)) for mm in re.finditer(r'"([^"]+)":\$R\[\d+\]=\[', inner)]
                bounds.append((len(inner), ''))
                for i in range(len(bounds) - 1):
                    seg = inner[bounds[i][0]:bounds[i + 1][0]]
                    subs = [{'id': x.group(1), 'count': int(x.group(2))}
                            for x in re.finditer(r'\{id:"([^"]+)",count:(\d+)\}', seg)]
                    tax['byParent'][bounds[i][1]] = subs
            out = {'taxonomy': tax}
        # tagOptions（/series 页类型筛选）
        tm = re.search(r'tagOptions:\$R\[\d+\]=\[(.*?)\],ads:', text, re.S)
        if tm:
            out['tagOptions'] = [{'id': x.group(1), 'count': int(x.group(2))}
                                 for x in re.finditer(r'\{id:"([^"]+)",count:(\d+)\}', tm.group(1))]
        if out:
            return {'props': {'pageProps': out}}
        return {}

    def _page_props(self, vid):
        """视频详情：App Router 页面用 ld+json 提取核心元数据。"""
        r = self._get(f'{self.home_url}/v/{vid}')
        text = r.text if r and r.status_code == 200 else ''
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', text or '', re.S)
        if not m:
            return {}
        try:
            ld = json.loads(m.group(1))
        except Exception:
            return {}
        secs = 0
        md = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', ld.get('duration') or '')
        if md:
            hh, mm, ss = (int(x or 0) for x in md.groups())
            secs = hh * 3600 + mm * 60 + ss
        tags = [urllib.parse.unquote(t) for t in sorted(set(re.findall(r'href="/t/([^"]+)"', text)))]
        return {'video': {
            'id': vid,
            'name': ld.get('name', '') or '',
            'coverImageUrl': (ld.get('thumbnailUrl') or [''])[0],
            'tags': tags,
            'createdAt': (ld.get('uploadDate') or '')[:4],
            'duration': secs,
        }}

    # ---------- 列表 ----------
    def homeContent(self, filter):
        classes = [{'type_name': t, 'type_id': '/t/' + t} for t in self.CLASSES]
        classes.append({'type_name': 'AI短劇', 'type_id': '/series'})
        return {'class': classes, 'filters': self._load_filters()}

    def _load_filters(self):
        now = time.time()
        if self._filters is not None and now - self._filters_ts < 600:
            return self._filters
        filters = {}
        try:
            r = self._get(self.home_url + '/cat')
            if r and r.status_code == 200:
                tax = self._tsr_data(r.text).get('props', {}).get('pageProps', {}).get('taxonomy') or {}
                genres = [{'n': '全部', 'v': ''}]
                for g in tax.get('genre') or []:
                    gid, cnt = g.get('id', ''), g.get('count', 0)
                    if gid:
                        genres.append({'n': f'{gid}({cnt})' if cnt else gid, 'v': gid})
                by_parent = tax.get('byParent') or {}
                for name in self.CLASSES:
                    values = [{'n': '全部', 'v': ''}]
                    for sub in by_parent.get(name) or []:
                        sid, cnt = sub.get('id', ''), sub.get('count', 0)
                        if sid:
                            values.append({'n': f'{sid}({cnt})' if cnt else sid, 'v': sid})
                    fl = []
                    if len(values) > 1:
                        fl.append({'key': 'tag', 'name': '出品', 'value': values})
                    if len(genres) > 1:
                        fl.append({'key': 'genre', 'name': '类型', 'value': genres})
                    if fl:
                        filters['/t/' + name] = fl
        except Exception:
            pass
        try:
            r = self._get(self.home_url + '/series')
            if r and r.status_code == 200:
                pp = self._tsr_data(r.text).get('props', {}).get('pageProps') or {}
                values = [{'n': '全部', 'v': ''}]
                for t in pp.get('tagOptions') or []:
                    tid, cnt = t.get('id', ''), t.get('count', 0)
                    if tid:
                        values.append({'n': f'{tid}({cnt})' if cnt else tid, 'v': tid})
                if len(values) > 1:
                    filters['/series'] = [{'key': 'tag', 'name': '类型', 'value': values}]
        except Exception:
            pass
        self._filters, self._filters_ts = filters, now
        return filters

    def homeVideoContent(self):
        return self._get_video_list(self.real_home)

    def categoryContent(self, tid, pg, filter, extend):
        ext = extend or {}
        page = int(pg) if str(pg).isdigit() else 1
        if str(tid).startswith('/series'):
            tag = (ext.get('tag') or '').strip()
            params = []
            if tag:
                params.append('tag=' + urllib.parse.quote(tag))
            if page > 1:
                params.append('page=' + str(page))
            url = self.home_url + '/series' + (('?' + '&'.join(params)) if params else '')
            return self._get_series_list(url, page)
        tag = (ext.get('tag') or ext.get('genre') or '').strip()
        if not tag:
            tag = urllib.parse.unquote(str(tid)).split('/t/')[-1] or self.CLASSES[0]
        url = f'{self.home_url}/t/{urllib.parse.quote(tag)}'
        if page > 1:
            url += f'?page={page}'
        result = self._get_video_list(url)
        result.update({'page': page, 'pagecount': page + 1 if result.get('list') else page, 'limit': 30, 'total': 0})
        return result

    def searchContent(self, key, quick, pg="1"):
        url = f'{self.home_url}/search?q={urllib.parse.quote(key)}'
        if pg and str(pg) != '1':
            url += f'&page={pg}'
        return self._get_video_list(url)

    def _get_series_list(self, url, page=1):
        try:
            r = self._get(url)
            if not r or r.status_code != 200:
                return {'list': [], 'msg': '请求失败'}
            pp = self._tsr_data(r.text).get('props', {}).get('pageProps') or {}
            videos, seen = [], set()
            for it in pp.get('list') or []:
                try:
                    sid = it.get('id', '')
                    if not sid or sid in seen:
                        continue
                    seen.add(sid)
                    cnt = it.get('episodeCount') or 0
                    videos.append({
                        'vod_id': 's:' + sid,
                        'vod_name': it.get('name', '') or '未知',
                        'vod_pic': it.get('coverImageUrl', ''),
                        'vod_remarks': f'{cnt}集' if cnt else '',
                        'style': {"type": "rect", "ratio": 1.5},
                    })
                except Exception:
                    continue
            total = int(pp.get('total') or 0)
            tp = int(pp.get('totalPage') or 0)
            return {'list': videos, 'page': page, 'pagecount': tp or page, 'limit': 26, 'total': total}
        except Exception:
            return {'list': [], 'msg': '解析失败'}

    def _get_video_list(self, url):
        try:
            resp = self._get(url)
            if not resp or resp.status_code != 200:
                return {'list': [], 'msg': '请求失败'}
            root = etree.HTML(resp.text)
            items = root.xpath('//a[contains(@href, "/v/")]') or []
            videos, seen = [], set()
            for item in items:
                try:
                    info = self._parse_video_item(item)
                    if info and info['vod_id'] not in seen:
                        seen.add(info['vod_id'])
                        videos.append(info)
                except Exception:
                    continue
            return {'list': videos}
        except Exception:
            return {'list': [], 'msg': '解析失败'}

    def _parse_video_item(self, item):
        hrefs = item.xpath('./@href')
        if not hrefs or '/v/' not in hrefs[0]:
            return None
        href = hrefs[0]
        imgs = item.xpath('.//img/@src')
        pic = imgs[0] if imgs else ''
        # 过滤站点"開始觀看"继续观看占位卡（无封面无实义）
        if not pic or '開始觀看' in ''.join(item.xpath('.//text()')):
            return None
        title = ''
        for alt in reversed(item.xpath('.//img/@alt')):
            if alt and alt.strip() and alt.strip() != 'cover':
                title = alt.strip()
                break
        if not title:
            texts = [t.strip() for t in item.xpath('.//text()') if t.strip() and len(t.strip()) > 2]
            title = ' '.join(texts)[:100] if texts else '未知'
        all_text = ' '.join(item.xpath('.//text()')).strip()
        remark = ''
        q = re.search(r'(\d{3,4}P|4K|HD)', all_text, re.IGNORECASE)
        if q:
            remark = q.group(1)
        t = re.search(r'(\d+分\d+秒|\d+:\d+:\d+|\d+:\d+)', all_text)
        if t:
            remark = f'{remark} {t.group(1)}'.strip()
        return {
            'vod_id': href,
            'vod_name': title,
            'vod_pic': pic,
            'vod_remarks': remark,
            'style': {"type": "rect", "ratio": 1.5},
        }

    # ---------- 详情与播放 ----------
    def detailContent(self, ids):
        raw = str(ids[0] if isinstance(ids, list) else ids)
        if raw.startswith('s:'):
            return self._series_detail(raw[2:])
        vid = raw.split('/')[-1].split('?')[0]
        if not vid:
            return {'list': [], 'msg': '视频ID为空'}
        vd = self._page_props(vid).get('video') or {}
        if not vd:
            return {'list': [], 'msg': '未找到视频信息'}
        tags = vd.get('tags') or []
        content = ' '.join(
            f'[a=cr:{{"id":"/t/{urllib.parse.quote(t)}","name":"{t}"}}/]{t}[/a]' for t in tags
        ) if tags else ''
        return {'list': [{
            'vod_id': vid,
            'vod_name': vd.get('name', ''),
            'vod_pic': vd.get('coverImageUrl', ''),
            'type_name': tags[0] if tags else 'Rou',
            'vod_year': vd.get('createdAt', ''),
            'vod_content': content,
            'vod_play_from': '肉視頻',
            'vod_play_url': f'正片${self._meta_proxy(vid)}',
        }]}

    def _series_detail(self, sid):
        if not sid:
            return {'list': [], 'msg': '短剧ID为空'}
        r = self._get(f'{self.home_url}/s/{sid}')
        pp = self._tsr_data(r.text if r else '').get('props', {}).get('pageProps') or {}
        ser = pp.get('series') or {}
        eps = pp.get('episodes') or []
        if not eps:
            return {'list': [], 'msg': '未找到剧集信息'}
        items = []
        for i, ep in enumerate(eps):
            if not isinstance(ep, dict):
                continue
            epid = ep.get('id', '')
            if not epid:
                continue
            ep_no = ep.get('episode') or (i + 1)
            items.append(f'第{ep_no}集${epid}')
        tags = ser.get('tags') or []
        return {'list': [{
            'vod_id': 's:' + sid,
            'vod_name': ser.get('name', '') or '未知短剧',
            'vod_pic': ser.get('coverImageUrl', ''),
            'type_name': tags[0] if tags else 'AI短劇',
            'vod_year': (ser.get('createdAt') or '')[:4],
            'vod_content': f'共{len(items)}集',
            'vod_play_from': '肉視頻短劇',
            'vod_play_url': '#'.join(items),
        }]}

    def playerContent(self, flag, id, vipFlags):
        id = str(id or '')
        if id.startswith('http'):
            # 详情阶段已返回本地代理 URL，直接交给播放器
            return {'parse': 0, 'url': id}
        vid = id.rstrip('/').split('/')[-1]
        if vid:
            return {'parse': 0, 'url': self._meta_proxy(vid)}
        return {'parse': 1, 'url': '', 'msg': '获取播放地址失败'}

    # ---------- 本地代理：PNG/roUd 解包 ----------
    def localProxy(self, params):
        log('localProxy CALLED, params type=' + type(params).__name__ + ' raw=' + repr(params)[:200])
        # 本壳 drpy-node 传查询字符串；也兼容 dict 与 parse_qs 形态
        if isinstance(params, str):
            try:
                qs = params.split('?', 1)[1] if '?' in params else params
                params = {k: v[0] for k, v in urllib.parse.parse_qs(qs).items()}
            except Exception:
                params = {}
        params = params or {}

        def gv(k, d=''):
            v = params.get(k, d)
            return v[0] if isinstance(v, list) and v else v

        action = str(gv('action', ''))
        try:
            if action == 'meta':
                vid = str(gv('vid', ''))
                if vid.endswith('.m3u8'):
                    vid = vid[:-5]
                return self._proxy_meta(vid)
            if action == 'ts':
                return self._proxy_ts(str(gv('u', '')))
        except Exception as e:
            log('localProxy error: ' + repr(e))
            return [500, 'text/plain', ('proxy error: ' + str(e)).encode('utf-8', 'ignore')]
        return [404, 'text/plain', b'proxy error']

    def _meta_proxy(self, vid):
        # 尾部 .m3u8 让壳端/EXO 按 HLS 初始化（localProxy 内会剥掉）
        return self.getProxyUrl() + f'&action=meta&vid={vid}.m3u8'

    def _proxy_meta(self, vid):
        if not vid:
            return [404, 'text/plain', b'no vid']
        now = time.time()
        with self._lock:
            hit = self._manifest.get(vid)
            if hit and now - hit[0] < 600:
                return [200, 'application/vnd.apple.mpegurl', hit[1]]
        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': f'{self.home_url}/v/{vid}',
            'Origin': self.home_url,
            'Cookie': self.headers['Cookie'],
        }
        # CDN 偶发缓存占位 PNG：缺 roUd 时带时间戳参数重试绕过边缘缓存
        text, base = '', ''
        last_diag = ''
        for attempt in range(3):
            url = f'{self.home_url}/api/hls/{vid}'
            if attempt:
                url += f'?_={int(time.time() * 1000)}'
            try:
                r = self._session.get(url, headers=headers, timeout=(5, 20))
            except Exception as e:
                last_diag = f'attempt{attempt} request exception: {e}'
                print('[Rou] ' + last_diag)
                continue
            body = unwrap_png(r.content)
            text = (body if body is not None else r.content).decode('utf-8', 'ignore')
            if '#EXTM3U' in text[:32]:
                base = r.url
                break
            last_diag = (f'attempt{attempt} status={r.status_code} len={len(r.content)} '
                         f'ct={r.headers.get("content-type")} redirected={r.url[:80]} '
                         f'head={r.content[:24]!r}')
            print('[Rou] meta fail ' + last_diag)
        if not base:
            log('meta FAIL ' + last_diag)
            return [500, 'text/plain',
                    f'Rou manifest fail vid={vid} | {last_diag}'.encode('utf-8', 'ignore')]
        segs = [urllib.parse.urljoin(base, s.strip())
                for s in text.splitlines() if s.strip() and not s.strip().startswith('#')]
        log('meta OK vid=' + vid + ' segs=' + str(len(segs)))
        with self._lock:
            for i, real in enumerate(segs):
                self._next_seg[real] = segs[i + 1] if i + 1 < len(segs) else None
        out = ['#EXTM3U', '#EXT-X-VERSION:3', '#EXT-X-TARGETDURATION:10']
        idx = 0
        for line in text.splitlines():
            ls = line.strip()
            if ls.startswith('#EXTINF'):
                out.append(ls)
            elif ls and not ls.startswith('#'):
                real = segs[idx] if idx < len(segs) else ''
                idx += 1
                out.append(f'{self.getProxyUrl()}&action=ts&u='
                           + urllib.parse.quote(base64.b64encode(real.encode()).decode()))
        data = '\n'.join(out) + '\n'
        with self._lock:
            self._manifest[vid] = (now, data)
            if len(self._manifest) > 20:
                for k in sorted(self._manifest, key=lambda x: self._manifest[x][0])[:-10]:
                    self._manifest.pop(k, None)
        # 壳端对 bytes 兼容性差，清单以文本返回
        return [200, 'application/vnd.apple.mpegurl', data]

    def _proxy_ts(self, u):
        if not u:
            return [404, 'text/plain', b'no url']
        real = base64.b64decode(urllib.parse.unquote(u)).decode()
        with self._lock:
            data = self._seg_cache.get(real)
        if data:
            return [200, 'video/mp2t', data]
        try:
            r = self._session.get(real, headers={'User-Agent': self.headers['User-Agent']}, timeout=(5, 30))
            body = unwrap_png(r.content)
            data = body if body is not None else r.content
        except Exception:
            return [404, 'text/plain', b'segment error']
        with self._lock:
            self._seg_cache[real] = data
            while len(self._seg_cache) > 4:
                self._seg_cache.pop(next(iter(self._seg_cache)))
        nxt = self._next_seg.get(real)
        if nxt:
            threading.Thread(target=self._prefetch, args=(nxt,), daemon=True).start()
        return [200, 'video/mp2t', data]

    def _prefetch(self, real):
        try:
            with self._lock:
                if real in self._seg_cache:
                    return
            r = self._session.get(real, headers={'User-Agent': self.headers['User-Agent']}, timeout=(5, 30))
            body = unwrap_png(r.content)
            data = body if body is not None else r.content
            with self._lock:
                self._seg_cache[real] = data
                while len(self._seg_cache) > 4:
                    self._seg_cache.pop(next(iter(self._seg_cache)))
        except Exception:
            pass

    def destroy(self):
        self._manifest.clear()
        self._seg_cache.clear()
        self._next_seg.clear()