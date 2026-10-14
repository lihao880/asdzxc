# coding: utf-8
import base64
import json
import re
import time
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from base.spider import Spider


class Spider(Spider):
    def __init__(self):
        self.ext = ''
        self.host = 'https://www.ypu3c.com'
        self.api_hosts = ['https://a64d.vd9h4.com', 'https://a59e.f3de7.com']
        self.api_host = self.api_hosts[0]
        self.ua = 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/124.0.0.0 Mobile Safari/537.36'
        self.headers = {
            'User-Agent': self.ua,
            'Origin': self.host,
            'Referer': self.host + '/',
            'Content-Type': 'application/json;charset=UTF-8;'
        }
        self.aes_key = b'B77A9FF7F323B5404902102257503C2F'
        self.aes_iv = self.aes_key[:16]
        self.image_key = b'46cc793c53dc451b'
        self._clock = 0
        self._clock_at = 0
        self.classes = [
            {'type_id': 'new', 'type_name': '今日上新'},
            {'type_id': 'subject', 'type_name': '专题'},
            {'type_id': 'media', 'type_name': '传媒'},
            {'type_id': 'actress', 'type_name': '女优'},
            {'type_id': 'gather', 'type_name': '合集'},
            {'type_id': 'short', 'type_name': '短视频'},
            {'type_id': 'type:4', 'type_name': '国产'},
            {'type_id': 'type:11', 'type_name': '主播'},
            {'type_id': 'type:17', 'type_name': '日韩'},
            {'type_id': 'type:23', 'type_name': '欧美'},
            {'type_id': 'type:29', 'type_name': '动漫'}
        ]
        order = {'key': 'order', 'name': '排序', 'value': [
            {'n': '最新', 'v': '1'}, {'n': '热播', 'v': '2'}, {'n': '综合', 'v': '7'}
        ]}
        children = {
            'type:4': [(5, '自拍'), (6, '偷拍'), (7, '私拍'), (8, '在校学生'), (9, '迷奸'), (10, '角色扮演')],
            'type:11': [(12, '裸舞诱惑'), (13, '约啪剧情'), (14, '野外露出'), (15, '网红女神'), (16, '潮吹喷水')],
            'type:17': [(18, '高清无码'), (19, '精品素人'), (20, '中文字幕'), (21, '熟女OL'), (22, '剧情综艺'), (32, '制服萝莉')],
            'type:23': [(24, '群P'), (25, '肛交'), (26, '野战'), (27, '黑白配'), (28, '重口剧情')],
            'type:29': [(30, '3D'), (31, '同人'), (33, '萝莉'), (34, '中文字幕')]
        }
        self.filters = {'new': [order]}
        for tid, values in children.items():
            parent = tid.split(':', 1)[1]
            self.filters[tid] = [
                {'key': 'type', 'name': '二级分类', 'value': [{'n': '全部', 'v': parent}] + [
                    {'n': name, 'v': str(cid)} for cid, name in values
                ]}, order
            ]
        for tid in ('subject', 'media', 'actress', 'gather'):
            self.filters[tid] = []
        self.filters['short'] = [order]

    def getName(self):
        return 'ypu3c'

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        self.ext = extend or ''
        return None

    def init(self, extend=''):
        self.ext = getattr(self, 'ext', '') or extend or ''
        try:
            cfg = self.ext if isinstance(self.ext, dict) else json.loads(self.ext or '{}')
            if isinstance(cfg, dict):
                api = str(cfg.get('api') or '').rstrip('/')
                if api:
                    self.api_hosts = [api] + [x for x in self.api_hosts if x != api]
                    self.api_host = api
        except Exception:
            pass

    def homeLayout(self):
        return 0

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(?:m3u8|mp4|flv)(?:$|[?#])', str(url or ''), re.I))

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter=False):
        return {'class': self.classes, 'filters': self.filters}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def _text(self, response):
        if response is None:
            return ''
        value = getattr(response, 'text', '')
        if callable(value):
            value = value()
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='ignore')
        return str(value or '')

    def _bytes(self, response):
        if response is None:
            return b''
        value = getattr(response, 'content', b'')
        if callable(value):
            value = value()
        if isinstance(value, str):
            return value.encode()
        return bytes(value or b'')

    def _request(self, url, method='get', data=None, headers=None, timeout=15):
        req_headers = headers or self.headers
        if str(method).lower() == 'post':
            body = json.dumps(data or {}, ensure_ascii=False, separators=(',', ':'))
            try:
                return self.post(url, data=body, headers=req_headers, timeout=timeout)
            except TypeError:
                return self.post(url, body, headers=req_headers, timeout=timeout)
        return self.fetch(url, headers=req_headers, timeout=timeout)

    def _plain_post(self, host, path, data=None):
        response = self._request(host + path, 'post', data or {})
        text = self._text(response)
        return json.loads(text) if text else {}

    def _server_time(self, host, force=False):
        now = time.time()
        if not force and self._clock and now - self._clock_at < 20:
            return int(self._clock + now - self._clock_at)
        result = self._plain_post(host, '/base/getTimeStamp', {})
        stamp = int((result.get('data') or {}).get('timeStamp') or 0)
        if not stamp:
            raise ValueError('服务端时间为空')
        self._clock, self._clock_at = stamp, now
        return stamp

    def _encrypt(self, value):
        raw = str(value).encode('utf-8')
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv)
        return base64.b64encode(cipher.encrypt(pad(raw, AES.block_size))).decode()

    def _api(self, path, data=None):
        payload = data or {}
        last = None
        hosts = [self.api_host] + [x for x in self.api_hosts if x != self.api_host]
        for host in hosts:
            for retry in range(2):
                try:
                    stamp = self._server_time(host, force=bool(retry))
                    body = {
                        'endata': self._encrypt(json.dumps(payload, ensure_ascii=False, separators=(',', ':'))),
                        'ents': self._encrypt(stamp)
                    }
                    result = self._plain_post(host, path, body)
                    code = int(result.get('code', -1))
                    if code == 0:
                        self.api_host = host
                        return result.get('data') or {}
                    last = RuntimeError('%s: %s' % (code, result.get('msg') or '接口失败'))
                    if code != 607:
                        break
                except Exception as e:
                    last = e
                    self._clock = 0
        self.log('API失败 %s: %s' % (path, last))
        return {}

    def _proxy_pic(self, url):
        url = str(url or '').strip()
        if not url:
            return ''
        if not url.lower().endswith('.aes'):
            return url
        try:
            return self.getProxyUrl() + '&url=' + quote(url, safe='')
        except Exception:
            return url

    def _duration(self, seconds):
        try:
            seconds = int(seconds or 0)
            return '%02d:%02d:%02d' % (seconds // 3600, seconds % 3600 // 60, seconds % 60)
        except Exception:
            return ''

    def _vod(self, item, prefix='video:'):
        if not isinstance(item, dict):
            return None
        vid = item.get('id') or item.get('videoId')
        name = str(item.get('name') or item.get('title') or '').strip()
        if vid is None or not name:
            return None
        pic = item.get('coverImgUrlVertical') or item.get('coverImgUrl') or item.get('cover') or ''
        remarks = self._duration(item.get('length')) or str(item.get('addTime') or item.get('description') or '')[:18]
        return {'vod_id': prefix + str(vid), 'vod_name': name, 'vod_pic': self._proxy_pic(pic), 'vod_remarks': remarks}
    def _folder(self, route, name, pic='', remarks='目录'):
        name = str(name or '').strip()
        if not route or not name:
            return None
        return {
            'vod_id': str(route), 'vod_name': name,
            'vod_pic': self._proxy_pic(pic),
            'vod_remarks': str(remarks or '目录'), 'vod_tag': 'folder'
        }

    def _page_result(self, items, page, count, limit=20):
        page = max(1, int(page or 1))
        count = max(0, int(count or 0))
        pagecount = max(page, (count + limit - 1) // limit) if count else page
        return {'list': items, 'page': page, 'pagecount': pagecount, 'limit': limit, 'total': count}


    def homeVideoContent(self):
        data = self._api('/videos/getList', {'page': 1, 'length': 20, 'orderType': 3})
        items = [v for v in (self._vod(x) for x in data.get('list', [])) if v]
        return {'list': items}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page, limit = max(1, int(pg or 1)), 20
        if isinstance(extend, str):
            try:
                extend = json.loads(extend or '{}')
            except Exception:
                extend = {}
        extend = extend if isinstance(extend, dict) else {}
        tid = str(tid or '')
        order_type = int(extend.get('order') or 1)

        if tid == 'subject':
            data = self._api('/subject/list', {'page': page, 'length': limit})
            folders = []
            for item in data.get('list', []):
                sid = item.get('id') or item.get('subjectId')
                folder = self._folder(
                    'subject:' + str(sid), item.get('name') or item.get('title'),
                    item.get('backgroundImgUrl') or item.get('coverImgUrl'),
                    str(item.get('description') or '专题目录')[:18]
                ) if sid is not None else None
                if folder:
                    folders.append(folder)
            return self._page_result(folders, page, data.get('count'), limit)

        if tid == 'media':
            media = [(1, '兔子先生'), (11, '91制片厂'), (2, '麻豆传媒'),
                     (3, '精东影业'), (4, '天美传媒'), (5, '蜜桃传媒'),
                     (6, '星空传媒'), (7, '水果派'), (8, 'JVID传媒'),
                     (9, '佳丽传媒'), (10, '其他传媒')]
            folders = [self._folder('media:%s' % tag_id, name, '', '传媒目录')
                       for tag_id, name in media]
            return self._page_result([x for x in folders if x], 1, len(media), len(media))

        if tid == 'actress':
            data = self._api('/user/getUpList', {
                'uids': [], 'page': page, 'length': limit,
                'groupIds': [1], 'filterIds': [], 'isManualBack': 1
            })
            folders = []
            for item in data.get('list', []):
                uid = item.get('id') or item.get('uid')
                folder = self._folder(
                    'actress:' + str(uid), item.get('user_nicename') or item.get('name'),
                    item.get('avatar') or item.get('avatar_thumb'),
                    '%s个作品' % int(item.get('videoCount') or 0)
                ) if uid is not None else None
                if folder:
                    folders.append(folder)
            return self._page_result(folders, page, data.get('count'), limit)

        if tid == 'gather':
            data = self._api('/gather/getList', {
                'page': page, 'length': limit, 'gatherType': 1, 'gatherIds': []
            })
            folders = []
            for item in data.get('list', []):
                gid = item.get('gatherId') or item.get('id')
                folder = self._folder(
                    'gather:' + str(gid), item.get('name'), item.get('coverImgUrl'),
                    '%s个视频' % int(item.get('videoCount') or 0)
                ) if gid is not None else None
                if folder:
                    folders.append(folder)
            return self._page_result(folders, page, data.get('count'), limit)

        if tid.startswith('subject:'):
            params = {'page': page, 'length': limit, 'subjectId': int(tid.split(':', 1)[1]),
                      'orderType': order_type}
        elif tid.startswith('media:'):
            params = {'page': page, 'length': limit, 'tagIds': [int(tid.split(':', 1)[1])],
                      'payType': [1, 3, 4], 'orderType': order_type}
        elif tid.startswith('actress:'):
            params = {'page': page, 'length': limit, 'uid': int(tid.split(':', 1)[1]),
                      'offset': (page - 1) * limit, 'payType': [], 'orderType': order_type}
        elif tid.startswith('gather:'):
            data = self._api('/gather/getDetail', {'gatherId': int(tid.split(':', 1)[1])})
            info = data.get('info') or {}
            source = info.get('videos') or []
            start = (page - 1) * limit
            items = [v for v in (self._vod(x) for x in source[start:start + limit]) if v]
            return self._page_result(items, page, info.get('videoCount') or len(source), limit)
        else:
            params = {'page': page, 'length': limit, 'orderType': order_type}
            if tid.startswith('search:'):
                word = unquote(tid[7:]).strip()
                data = self._api('/base/globalSearch', {
                    'page': page, 'length': limit, 'type': 1, 'key': word,
                    'orderType': order_type
                })
                items = [v for v in (self._vod(x) for x in (data.get('infos') or data.get('list') or [])) if v]
                return self._page_result(items, page, data.get('count') or len(items), limit)
            if tid == 'short':
                params['type'] = 2
            elif tid.startswith('type:'):
                params['typeIds'] = [int(extend.get('type') or tid.split(':', 1)[1])]
            elif tid != 'new':
                try:
                    params['typeIds'] = [int(tid)]
                except Exception:
                    return self._page_result([], page, 0, limit)
        data = self._api('/videos/getList', params)
        items = [v for v in (self._vod(x) for x in data.get('list', [])) if v]
        return self._page_result(items, page, data.get('count'), limit)

    def _video_detail(self, video_id):
        data = self._api('/videos/getInfo', {'videoSort': 1, 'videoId': int(video_id)})
        info = data.get('info') or {}
        if not info:
            return None
        tags = str(info.get('tags') or '').strip(',')
        content = str(info.get('description') or '')
        if tags:
            content = ('标签：' + tags + '\n' + content).strip()
        play_name = info.get('name') or ('视频' + str(video_id))
        return {
            'vod_id': 'video:' + str(video_id),
            'vod_name': str(info.get('name') or ''),
            'vod_pic': self._proxy_pic(info.get('coverImgUrlVertical') or info.get('coverImgUrl')),
            'type_name': str(info.get('typeName') or ''),
            'vod_year': str(info.get('addTime') or '')[:4],
            'vod_remarks': self._duration(info.get('length')),
            'vod_content': content,
            'vod_play_from': '站内直链',
            'vod_play_url': '%s$%s' % (str(play_name).replace('$', ' '), video_id)
        }

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, list) and ids else ids
        raw = str(raw or '')
        try:
            if raw.startswith(('subject:', 'media:', 'actress:', 'gather:')):
                return {'list': []}
            vod = self._video_detail(raw.split(':', 1)[-1])
            return {'list': [vod] if vod else []}
        except Exception as e:
            self.log('详情失败: %s' % e)
            return {'list': []}

    def recommendContent(self, ids, pg):
        raw = ids[0] if isinstance(ids, list) and ids else ids
        video_id = str(raw or '').split(':')[-1]
        try:
            data = self._api('/videos/getRecommendListByVideoId', {
                'page': max(0, int(pg or 1) - 1), 'length': 10, 'videoId': int(video_id)
            })
            source = data.get('list') or data.get('info') or []
            items = [v for v in (self._vod(x) for x in source) if v]
            return {'list': items}
        except Exception:
            return {'list': []}

    def searchContent(self, key, quick=False, pg=1):
        word = str(key or '').strip()
        if not word:
            return {'list': []}
        page = max(1, int(pg or 1))
        data = self._api('/base/globalSearch', {
            'page': page, 'length': 12, 'type': 1, 'key': word, 'orderType': 1
        })
        items = [v for v in (self._vod(x) for x in (data.get('infos') or data.get('list') or [])) if v]
        return {'list': items}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def _clean_play_url(self, url):
        """删除试看时间窗口参数，保留服务端签名等其它参数。"""
        url = str(url or '').strip()
        if not url:
            return ''
        try:
            parts = urlsplit(url)
            query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
                     if key.lower() not in ('start', 'end')]
            return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        except Exception:
            return url

    def _resolve_hls_media(self, url):
        url = str(url or '').strip()
        if '.m3u8' not in url.lower():
            return url
        try:
            response = self._request(url, headers={'User-Agent': self.ua}, timeout=10)
            text = self._text(response).lstrip('\ufeff').strip()
            if not text.startswith('#EXTM3U') or '#EXT-X-STREAM-INF' not in text:
                return url
            variants = [line.strip() for line in text.splitlines()
                        if line.strip() and not line.lstrip().startswith('#')]
            if len(variants) != 1:
                return url
            media_url = urljoin(url, variants[0])
            self.log('EXO兼容：单码率主清单展开为子清单')
            return media_url
        except Exception as e:
            self.log('主清单展开失败，保留原地址: %s' % e)
            return url

    def playerContent(self, flag, id, vipFlags=None):
        video_id = str(id or '').split('|', 1)[0].split(':')[-1]
        try:
            preview = self._api('/videos/getPreUrl', {'videoId': int(video_id)})
            url = str(preview.get('url') or preview.get('videoUrl') or preview.get('playUrl') or '')
            if not url:
                return {'parse': 0, 'jx': 0, 'url': '', 'header': {'User-Agent': self.ua}}
            url = self._clean_play_url(url)
            url = self._resolve_hls_media(url)
            return {'parse': 0, 'jx': 0, 'url': url, 'header': {'User-Agent': self.ua}}
        except Exception as e:
            self.log('播放失败: %s' % e)
            return {'parse': 0, 'jx': 0, 'url': '', 'header': {'User-Agent': self.ua}}

    def _image_mime(self, body):
        if body[:3] == b'\xff\xd8\xff':
            return 'image/jpeg'
        if body[:8] == b'\x89PNG\r\n\x1a\n':
            return 'image/png'
        if body[:6] in (b'GIF87a', b'GIF89a'):
            return 'image/gif'
        if body[:4] == b'RIFF' and body[8:12] == b'WEBP':
            return 'image/webp'
        return ''

    def localProxy(self, param):
        url = unquote(str((param or {}).get('url') or ''))
        if not url.startswith(('http://', 'https://')):
            return [404, 'text/plain', b'bad url']
        try:
            response = self._request(url, headers={'User-Agent': self.ua, 'Referer': self.host + '/'})
            body = self._bytes(response).strip()
            mime = self._image_mime(body)
            if mime:
                return [200, mime, body]
            encrypted = base64.b64decode(body)
            plain = unpad(AES.new(self.image_key, AES.MODE_ECB).decrypt(encrypted), AES.block_size)
            if plain.startswith(b'data:image/') and b',' in plain:
                head, encoded = plain.split(b',', 1)
                body = base64.b64decode(encoded)
                match = re.match(br'data:(image/[a-zA-Z0-9.+-]+);base64', head)
                mime = match.group(1).decode() if match else self._image_mime(body)
            else:
                body, mime = plain, self._image_mime(plain)
            if not mime:
                return [404, 'text/plain', b'not image']
            return [200, mime, body]
        except Exception as e:
            self.log('图片代理失败: %s' % e)
            return [404, 'text/plain', b'image error']

    def action(self, action):
        return None

    def destroy(self):
        return None