# -*- coding: utf-8 -*-
import base64
import json
import re
import time
from html import unescape
from urllib.parse import quote, unquote, urljoin
import requests
import urllib3
from base.spider import Spider
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Spider(Spider):
    UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
    IMAGE_ALPHABET = 'ABCD*EFGHIJKLMNOPQRSTUVWX#YZabcdefghijklmnopqrstuvwxyz1234567890'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ext, self.cookie, self.user_token, self.user_id = '', '', '', ''
        self.username, self.password = '', ''
        self.host = 'https://j818754ac1fdc8.xyz'
        self.fallback_host = self.host
        self.bootstrap_hosts = (
            'https://j818754ac1fdc8.xyz',
            'https://j8789198fa66b8.xyz',
            'https://j741f6c110b3cf.xyz',
            'https://www.haijiao.com',
        )
        self._host_resolved = False
        self._host_resolved_at = 0
        self._host_retry_at = 0
        self._host_manual = False
        self._init_signature = None
        self._detail_cache = {}
        self.session = requests.Session()
        self.headers = {}
        self.classes = [
            {'type_id': 'hot', 'type_name': '热门'},
            {'type_id': '888', 'type_name': '热门专区'},
            {'type_id': '1001', 'type_name': '收费视频'},
            {'type_id': '972', 'type_name': '销魂视频'},
            {'type_id': '971', 'type_name': '耳目盛宴'},
            {'type_id': '973', 'type_name': '激情时刻'},
            {'type_id': '962', 'type_name': '图情画意'},
            {'type_id': '961', 'type_name': '美伦精品'},
        ]
        self.filters = {}
        self._apply_headers()

    def getName(self): return '海角社区'
    def getDependence(self): return []
    def homeLayout(self): return 0
    def manualVideoCheck(self): return False

    def setExtendInfo(self, extend):
        self.ext = extend or ''
        return None

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(?:m3u8|mp4|flv)(?:$|[?#])', str(url or ''), re.I))

    def _parse_extend(self, extend):
        if isinstance(extend, dict): return extend
        text = str(extend or '').strip()
        if not text: return {}
        try: return json.loads(text)
        except Exception: pass
        try:
            return json.loads(base64.b64decode(text + '=' * (-len(text) % 4)).decode())
        except Exception: pass
        return {'cookie': text} if '=' in text else {}

    def _apply_headers(self):
        self.headers = {'User-Agent': self.UA, 'Accept': 'application/json, text/plain, */*',
                        'Referer': self.host + '/home', 'Origin': self.host, 'pcVer': '2'}
        if self.cookie: self.headers['Cookie'] = self.cookie
        if self.user_token: self.headers['X-User-Token'] = self.user_token
        if self.user_id: self.headers['X-User-Id'] = self.user_id
        self.session.headers.clear()
        self.session.headers.update(self.headers)

    def init(self, extend=''):
        incoming = extend if extend not in (None, '') else getattr(self, 'ext', '')
        self.ext = incoming or ''
        cfg = self._parse_extend(self.ext)
        configured_host = str(cfg.get('site') or cfg.get('host') or '').strip().rstrip('/')
        cookie = str(cfg.get('cookie') or '')
        user_token = str(cfg.get('token') or cfg.get('user_token') or cfg.get('X-User-Token') or '')
        user_id = str(cfg.get('id') or cfg.get('user_id') or cfg.get('X-User-Id') or '')
        username = str(cfg.get('username') or cfg.get('user') or '')
        password = str(cfg.get('password') or cfg.get('pass') or '')
        signature = (configured_host, cookie, user_token, user_id, username, password)
        if signature == self._init_signature and self._host_resolved:
            return None

        self._init_signature = signature
        self._host_manual = bool(configured_host)
        if configured_host:
            self.host = configured_host
            self.fallback_host = configured_host
            self._host_resolved = True
            self._host_resolved_at = time.time()
        else:
            self.host = self.fallback_host
            self._host_resolved = False
            self._host_resolved_at = 0
        self._host_retry_at = 0
        self.cookie, self.user_token, self.user_id = cookie, user_token, user_id
        self.username, self.password = username, password
        self._detail_cache.clear()
        self._apply_headers()
        if not (self.user_token and self.user_id) and self.username and self.password:
            self._login()
        return None

    def _login(self):
        payload = {'Username': self.username, 'Password': self.password,
                   'CaptchaCode': '', 'CaptchaId': '', 'Ref': '', 'Sign': ''}
        obj = self._json('POST', '/api/login/signin', data=payload,
                         referer=self.host + '/login')
        data = self._data(obj)
        if not isinstance(data, dict):
            return False
        user = data.get('user') if isinstance(data.get('user'), dict) else {}
        token = str(data.get('token') or '')
        user_id = str(user.get('id') or data.get('userId') or data.get('user_id') or '')
        if not token or not user_id:
            try: self.log('海角登录失败: ' + str(obj.get('message') or '未返回 token/id'))
            except Exception: pass
            return False
        domain = str(data.get('domain') or '').strip()
        if domain.startswith(('http://', 'https://')):
            self.host = domain.rstrip('/')
        self.user_token, self.user_id = token, user_id
        self._apply_headers()
        return True

    def destroy(self):
        try: self.session.close()
        except Exception: pass

    def _valid_host(self, value):
        value = str(value or '').strip().rstrip('/')
        return value if re.match(r'^https?://[A-Za-z0-9.-]+(?::\d+)?$', value, re.I) else ''

    def _host_has_api(self, host):
        try:
            resp = self.session.get(host + '/api/topic/hot/topics', params={'page': 1}, headers={
                'User-Agent': self.UA, 'Accept': 'application/json, text/plain, */*',
                'Referer': host + '/home', 'Origin': host, 'pcVer': '2'
            }, timeout=12, verify=False)
            if resp.status_code != 200 or 'json' not in str(resp.headers.get('Content-Type', '')).lower():
                return False
            obj = resp.json()
            return isinstance(obj, dict) and obj.get('success') is True and bool(obj.get('data'))
        except Exception:
            return False

    def _resolve_host(self, force=False):
        now = time.time()
        if self._host_manual:
            return self.host
        if self._host_resolved and not force and now - self._host_resolved_at < 1800:
            return self.host
        if not force and now < self._host_retry_at:
            return self.host

        sources = []
        for value in (self.host, self.fallback_host) + tuple(self.bootstrap_hosts):
            value = self._valid_host(value)
            if value and value not in sources:
                sources.append(value)
        candidates = []
        for source in sources:
            try:
                resp = self.session.get(source + '/api/login/conf', headers={
                    'User-Agent': self.UA, 'Accept': 'application/json, text/plain, */*',
                    'Referer': source + '/home', 'Origin': source, 'pcVer': '2'
                }, timeout=8, verify=False)
                obj = resp.json() if resp.status_code == 200 else {}
                data = self._decode_payload(obj.get('data')) if isinstance(obj, dict) else {}
                if isinstance(data, dict):
                    # 国内业务域优先；跳转和备用域次之，海外域最后。
                    candidates.extend((data.get('domain'), data.get('redirectTo'),
                                       data.get('backupDomain'), data.get('domainAbroad')))
                    if any(candidates):
                        break
            except Exception:
                continue
        candidates.extend(sources)
        seen = set()
        for value in candidates:
            candidate = self._valid_host(value)
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            if self._host_has_api(candidate):
                old_host = self.host
                self.host = candidate
                self._host_resolved = True
                self._host_resolved_at = now
                self._host_retry_at = 0
                self._apply_headers()
                try:
                    self.log('海角国内域名已刷新: %s%s' % (
                        self.host, '' if old_host == self.host else '（原 %s）' % old_host))
                except Exception:
                    pass
                return self.host
        self.host = self._valid_host(self.fallback_host) or (sources[0] if sources else self.host)
        self._host_resolved = False
        self._host_resolved_at = 0
        self._host_retry_at = now + 30
        self._apply_headers()
        return self.host

    def _request(self, method, path, params=None, data=None, referer=None):
        absolute = str(path).startswith(('http://', 'https://'))
        if not absolute:
            self._resolve_host()
        for attempt in range(2):
            url = path if absolute else self.host + path
            headers = dict(self.headers)
            if referer:
                headers['Referer'] = referer
            try:
                response = self.session.request(method, url, params=params, json=data,
                                                headers=headers, timeout=15, verify=False)
                if absolute or response.status_code not in (403, 404, 502, 503, 504) or attempt:
                    return response
            except Exception as e:
                if absolute or attempt:
                    try: self.log('海角请求失败: %s | %s' % (url, e))
                    except Exception: pass
                    return None
            self._host_resolved = False
            self._host_resolved_at = 0
            old_host = self.host
            self._resolve_host(force=True)
            if self.host == old_host:
                return response if 'response' in locals() else None
        return None

    def _decode_payload(self, value):
        current = value
        for _ in range(3):
            if not isinstance(current, str): break
            try:
                text = current.strip()
                current = base64.b64decode(text + '=' * (-len(text) % 4)).decode('utf-8')
            except Exception: return value
        if isinstance(current, str):
            try: return json.loads(current)
            except Exception: return current
        return current

    def _json(self, method, path, params=None, data=None, referer=None):
        resp = self._request(method, path, params, data, referer)
        if resp is None or resp.status_code != 200: return {}
        try: obj = resp.json()
        except Exception: return {}
        if isinstance(obj, dict) and obj.get('isEncrypted') and obj.get('data'):
            obj['data'] = self._decode_payload(obj['data'])
        return obj

    def _data(self, obj):
        return obj.get('data') if isinstance(obj, dict) and 'data' in obj else obj

    def _fix_url(self, url):
        url = str(url or '').strip()
        return urljoin(self.host + '/', url) if url else ''
    def _preview_url(self, topic_id, attachment):
        attachment_id = attachment.get('id') if isinstance(attachment, dict) else attachment
        try:
            payload = {
                'id': int(attachment_id),
                'resource_id': int(topic_id),
                'resource_type': 'topic',
                'line': '',
            }
        except Exception:
            return ''
        obj = self._json(
            'POST', '/api/attachment', data=payload,
            referer=self.host + '/post/details?pid=' + str(topic_id)
        )
        data = self._data(obj)
        if isinstance(data, dict):
            value = self._fix_url(data.get('remoteUrl') or data.get('url'))
            if value:
                return value

        # 匿名详情会隐藏 remoteUrl，但 coverUrl 保留真实视频目录与媒体编号。
        cover = str(attachment.get('coverUrl') or '') if isinstance(attachment, dict) else ''
        match = re.match(
            r'https?://[^/]+(/hjstore/video/\d{8}/[0-9a-f]+/)(\d+)\.jpeg(?:\.txt)?(?:[?#].*)?$',
            cover, re.I
        )
        if not match:
            return ''
        preview = 'https://ts10.hj260302818.top%s%s_i_preview.m3u8' % match.groups()
        try:
            response = self.session.get(preview, headers={'User-Agent': self.UA},
                                        timeout=12, verify=False)
            text = response.text if response.status_code == 200 else ''
            if '#EXTM3U' not in text[:256]:
                return ''
            key_match = re.search(r'URI=["\']([^"\']+\.key[^"\']*)', text, re.I)
            resources = [line.strip() for line in text.splitlines()
                         if line.strip() and not line.lstrip().startswith('#')]
            if not key_match or not resources:
                return ''
            # KEY 名含当前附件 ID，可避免把同目录无关资源误当成该视频预览。
            if str(attachment_id) not in key_match.group(1):
                return ''
            return preview
        except Exception:
            return ''


    def _image_proxy(self, url):
        url = self._fix_url(url)
        if not url: return ''
        try: return self.getProxyUrl() + '&url=' + quote(url, safe='')
        except Exception: return url

    def _image_mime(self, content):
        if content.startswith(b'\xff\xd8\xff'): return 'image/jpeg'
        if content.startswith(b'\x89PNG\r\n\x1a\n'): return 'image/png'
        if content.startswith((b'GIF87a', b'GIF89a')): return 'image/gif'
        if len(content) >= 12 and content[:4] == b'RIFF' and content[8:12] == b'WEBP': return 'image/webp'
        return ''

    def _decode_image_text(self, text):
        chars = [c for c in str(text or '') if c in self.IMAGE_ALPHABET]
        output = bytearray()
        for pos in range(0, len(chars), 4):
            block = chars[pos:pos + 4]
            if len(block) < 2: break
            values = [self.IMAGE_ALPHABET.find(c) for c in block]
            a, b = values[0], values[1]
            output.append(((a << 2) | (b >> 4)) & 255)
            if len(values) > 2:
                c = values[2]
                output.append((((b & 15) << 4) | (c >> 2)) & 255)
                if len(values) > 3:
                    output.append((((c & 3) << 6) | values[3]) & 255)
        raw = bytes(output)
        if b'base64,' not in raw: return raw
        payload = raw.split(b'base64,', 1)[1].strip()
        try: return base64.b64decode(payload + b'=' * (-len(payload) % 4))
        except Exception: return b''
    def _proxy_image(self, raw_url):
        if not raw_url:
            return [404, 'text/plain', b'Empty URL']
        try:
            resp = self.session.get(raw_url, headers={
                'User-Agent': self.UA, 'Referer': self.host + '/home'
            }, timeout=15, verify=False)
            if resp.status_code != 200:
                return [resp.status_code, 'text/plain', b'Image request failed']
            content, mime = resp.content, self._image_mime(resp.content)
            if not mime:
                content = self._decode_image_text(resp.text)
                mime = self._image_mime(content)
            if not mime:
                return [422, 'text/plain', b'Invalid image payload']
            return [200, mime, content]
        except Exception:
            return [500, 'text/plain', b'Image proxy failed']

    def proxy(self, params):
        return self.localProxy(params)
    def _image_urls(self, item):
        result, seen = [], set()
        for att in item.get('attachments') or []:
            if not isinstance(att, dict) or att.get('category') != 'images':
                continue
            url = self._fix_url(att.get('remoteUrl') or att.get('url'))
            if not url or url in seen:
                continue
            seen.add(url)
            result.append(url)
        return result

    def _first_image(self, item):
        for att in item.get('attachments') or []:
            if not isinstance(att, dict): continue
            if att.get('category') == 'images' and att.get('remoteUrl'):
                return self._image_proxy(att['remoteUrl'])
            if att.get('coverUrl'): return self._image_proxy(att['coverUrl'])
        for key in ('cover', 'coverUrl', 'pic', 'thumb'):
            if item.get(key): return self._image_proxy(item[key])
        return ''

    def _items(self, items):
        result, seen = [], set()
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict): continue
            topic_id = str(item.get('topicId') or item.get('id') or '')
            if not topic_id or topic_id in seen: continue
            seen.add(topic_id)
            node = item.get('node') if isinstance(item.get('node'), dict) else {}
            video = item.get('hasVideo') or any(isinstance(a, dict) and a.get('category') == 'video'
                                                for a in item.get('attachments') or [])
            pictures = item.get('hasPic') or any(isinstance(a, dict) and a.get('category') == 'images'
                                                 for a in item.get('attachments') or [])
            media = '图文视频' if video and pictures else ('视频' if video else ('图片' if pictures else ''))
            remark = str(node.get('name') or '')
            if media:
                remark = (media + ' · ' + remark).strip(' ·')
            result.append({'vod_id': topic_id, 'vod_name': str(item.get('title') or '海角帖子'),
                           'vod_pic': self._first_image(item), 'vod_remarks': remark})
        return result

    def _page_result(self, data, page):
        if isinstance(data, list): items, info = data, {}
        elif isinstance(data, dict):
            items = data.get('results') or data.get('topics') or data.get('list') or []
            info = data.get('page') if isinstance(data.get('page'), dict) else {}
        else: items, info = [], {}
        limit, total = int(info.get('limit') or 20), int(info.get('total') or len(items))
        pagecount = max(1, (total + limit - 1) // limit) if total else page
        return {'list': self._items(items), 'page': page, 'pagecount': pagecount,
                'limit': limit, 'total': total}

    def homeContent(self, filter=False): return {'class': self.classes, 'filters': self.filters}
    def getHomeContent(self, filter=False): return self.homeContent(filter)

    def homeVideoContent(self):
        obj = self._json('GET', '/api/topic/hot/topics', params={'page': 1})
        return {'list': self._page_result(self._data(obj), 1)['list']}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = int(pg) if str(pg).isdigit() else 1
        if str(tid).startswith('search:'):
            obj = self._json('GET', '/api/topic/searchV2', params={
                'key': str(tid)[7:], 'node_id': 0, 'page': page})
        elif str(tid) == 'hot':
            obj = self._json('GET', '/api/topic/hot/topics', params={'page': page})
        else:
            obj = self._json('GET', '/api/topic/node/topics', params={'nodeId': str(tid), 'page': page})
        return self._page_result(self._data(obj), page)

    def _plain_text(self, html):
        text = re.sub(r'<(?:img|video)\b[^>]*>', '', str(html or ''), flags=re.I)
        text = re.sub(r'<br\s*/?>|</p\s*>', '\n', text, flags=re.I)
        text = re.sub(r'<[^>]+>', '', text)
        return re.sub(r'\n{3,}', '\n\n', unescape(text)).strip()

    def _detail(self, topic_id):
        key = str(topic_id)
        cached = self._detail_cache.get(key)
        if isinstance(cached, tuple) and time.time() - cached[0] < 120:
            return cached[1]
        obj = self._json('GET', '/api/topic/' + quote(key),
                         referer=self.host + '/post/details?pid=' + key)
        data = self._data(obj)
        if isinstance(data, dict):
            self._detail_cache[key] = (time.time(), data)
            if len(self._detail_cache) > 12:
                oldest = min(self._detail_cache, key=lambda x: self._detail_cache[x][0])
                self._detail_cache.pop(oldest, None)
            return data
        return {}

    def detailContent(self, ids):
        if not ids: return {'list': []}
        topic_id, data = str(ids[0]), self._detail(ids[0])
        if not data: return {'list': []}
        videos = [a for a in data.get('attachments') or [] if isinstance(a, dict)
                  and a.get('category') == 'video' and a.get('id')]
        play_from, play_urls = [], []
        images = self._image_urls(data)
        has_preview = False
        for video in videos:
            aid = str(video['id'])
            preview = str(video.get('remoteUrl') or '').strip()
            if not preview:
                preview = self._preview_url(topic_id, video)
            if preview:
                # 详情字段为空时，按网页播放器真实 POST 接口恢复匿名试看。
                has_preview = True
                play_from.append('匿名预览')
                play_urls.append('预览$' + '|'.join((topic_id, aid, 'preview', preview)))
            if self.user_token and self.user_id:
                lines = self._data(self._json('GET', '/api/topic/att/' + aid))
                if isinstance(lines, list):
                    for index, line in enumerate(lines):
                        if not isinstance(line, dict):
                            continue
                        code = 'normal1' if index == 0 else ('normal2' if index == 1 else 'vip')
                        name = str(line.get('name') or '线路%d' % (index + 1))
                        if name in play_from:
                            name += str(len(play_from) + 1)
                        play_from.append(name)
                        play_urls.append('正片$' + '|'.join((topic_id, aid, code)))
            elif not preview:
                # 收费视频未购买时会保留 video 附件 ID，但隐藏 remoteUrl。
                # 保留受限线路用于表达真实媒体类型，点击时由 playerContent 明确提示授权。
                play_from.append('视频需授权')
                play_urls.append('正片$' + '|'.join((topic_id, aid, 'normal1')))

        if images:
            play_from.append('图片')
            play_urls.append('浏览%d张$images|%s' % (len(images), topic_id))

        node = data.get('node') if isinstance(data.get('node'), dict) else {}
        user = data.get('user') if isinstance(data.get('user'), dict) else {}
        tags = [str(x.get('tagName')) for x in data.get('tags') or [] if isinstance(x, dict) and x.get('tagName')]
        remark = ' / '.join(tags) or str(node.get('name') or '')
        if videos and not self.user_token:
            access = '匿名可预览 · 正片需账号授权' if has_preview else '视频需购买或账号授权'
            remark = (access + ' · ' + remark).strip(' ·')
        vod = {'vod_id': topic_id, 'vod_name': str(data.get('title') or '海角帖子'),
               'vod_pic': self._first_image(data), 'type_name': str(node.get('name') or '海角社区'),
               'vod_remarks': remark, 'vod_actor': str(user.get('nickname') or ''), 'vod_director': '',
               'vod_content': self._plain_text(data.get('content') or data.get('liteContent')),
               'vod_play_from': '$$$'.join(play_from), 'vod_play_url': '$$$'.join(play_urls)}
        return {'list': [vod]}

    def searchContent(self, key, quick=False, pg='1'):
        page = int(pg) if str(pg).isdigit() else 1
        obj = self._json('GET', '/api/topic/searchV2', params={
            'key': str(key), 'node_id': 0, 'page': page})
        return {'list': self._page_result(self._data(obj), page)['list']}

    def playerContent(self, flag, play_id, vipFlags=None):
        value = str(play_id or '').strip()
        if value.startswith('images|'):
            topic_id = value.split('|', 1)[1].strip()
            images = self._image_urls(self._detail(topic_id)) if topic_id else []
            if not images:
                return {'parse': 0, 'jx': 0, 'url': '', 'msg': '该帖子没有可浏览图片'}
            pictures = [self._image_proxy(url) for url in images]
            pictures = [url for url in pictures if url]
            return {'parse': 0, 'jx': 0, 'playUrl': '',
                    'url': 'pics://' + '&&'.join(pictures), 'header': {}}
        parts = value.split('|', 3)
        if value.startswith(('http://', 'https://')):
            # 壳端可能把预览直链当普通地址传入；站内视频 CDN 一律不裸出，
            # 否则 EXO 直连 CDN 会拿到不可解析内容（3001/3002）。
            if '/hjstore/' not in value:
                return {'parse': 0, 'jx': 0, 'url': value, 'header': {'User-Agent': self.UA}}
            preview = value
        elif len(parts) == 4 and parts[2] == 'preview':
            preview = self._fix_url(parts[3])
        else:
            preview = ''
        if preview:
            if not preview:
                return {'parse': 0, 'jx': 0, 'url': '', 'msg': '匿名预览地址为空'}
            # 先构造 ts5 候选并探测 ts5 本身；握手失败时回退原始 ts10 地址。
            candidate = re.sub(r'://ts(?:\d+)?\.', '://ts5.', preview, count=1, flags=re.I)
            try:
                host = re.match(r'https?://[^/]+', candidate, re.I).group(0)
                probe = self.session.get(host + '/favicon.ico', headers={'User-Agent': self.UA},
                                         timeout=(4, 6), verify=False, allow_redirects=False)
                reachable = probe.status_code < 500
            except Exception:
                reachable = False
            preview = candidate if reachable else preview
            proxy = self.getProxyUrl()
            if proxy:
                preview = proxy + '&type=preview_m3u8&url=' + quote(preview, safe='')
            return {'parse': 0, 'jx': 0, 'url': preview,
                    'header': {'User-Agent': self.UA}}
        if len(parts) != 3 or not all(parts[:2]):
            return {'parse': 0, 'jx': 0, 'url': '', 'msg': '播放参数无效'}
        topic_id, attachment_id, line = parts
        if not self.user_token or not self.user_id:
            message = ('该视频未公开匿名预览，需购买或登录已获授权账号'
                       if str(flag or '') == '视频需授权'
                       else '该线路是授权正片；未登录时请选择“匿名预览”')
            return {'parse': 0, 'jx': 0, 'url': '', 'msg': message}
        payload = {'id': int(attachment_id), 'resource_id': int(topic_id),
                   'resource_type': 'topic', 'line': line}
        obj = self._json('POST', '/api/attachment', data=payload,
                         referer=self.host + '/post/details?pid=' + topic_id)
        data = self._data(obj)
        media = str(data.get('remoteUrl') or '') if isinstance(data, dict) else ''
        if not media:
            message = str(obj.get('message') or '当前账号未获该视频播放授权') if isinstance(obj, dict) else '播放接口失败'
            return {'parse': 0, 'jx': 0, 'url': '', 'msg': message}
        return {'parse': 0, 'jx': 0, 'url': self._fix_url(media),
                'header': {'User-Agent': self.UA}}

    def _proxy_url(self, raw_url):
        try:
            return self.getProxyUrl() + '&type=media&url=' + quote(str(raw_url), safe='')
        except Exception:
            return raw_url

    def localProxy(self, params):
        params = params or {}
        proxy_type = str(params.get('type') or '').strip()
        source = unquote(str(params.get('url') or '')).strip()
        if proxy_type == 'media':
            # KEY/TS 分片由壳端 EXO 经本地代理转发，绕开壳端直连 CDN 失败的问题。
            try:
                response = self.session.get(source, headers={'User-Agent': self.UA},
                                            timeout=25, verify=False)
                # CDN 对 TS 返回 text/vnd.trolltech.linguist 等错误 MIME，会触发 EXO 3001；
                # 按资源类型强制返回正确 MIME。
                lower = source.lower()
                filename = lower.rsplit('/', 1)[-1].split('?')[0]
                content = response.content
                mime = response.headers.get('Content-Type', 'application/octet-stream')
                if filename.endswith('.ts'):
                    mime = 'video/mp2t'
                elif filename.endswith('.key'):
                    # .key 是 XOR 混淆的：真实KEY = enc ^ 种子前16字节；
                    # 种子 = 同目录 .jpg（base64 文本），由清单重写时附在 &seed= 上。
                    mime = 'application/octet-stream'
                    seed = unquote(str(params.get('seed') or '')).strip()
                    if seed:
                        try:
                            sresp = self.session.get(seed, headers={'User-Agent': self.UA},
                                                     timeout=15, verify=False)
                            blob = base64.b64decode(sresp.text.strip())
                            content = bytes(a ^ b for a, b in zip(content, blob[:16]))
                        except Exception as e:
                            try: self.log('海角KEY解密失败: %s' % e)
                            except Exception: pass
                return [response.status_code, mime, content]
            except Exception as e:
                try: self.log('海角媒体转发失败: %s | %s' % (source[:150], e))
                except Exception: pass
                return [502, 'text/plain', b'Media fetch failed']
        if proxy_type != 'preview_m3u8':
            return self._proxy_image(source)
        if not source.startswith(('http://', 'https://')):
            return [400, 'text/plain', b'Invalid URL']
        try:
            response = self.session.get(source, headers={'User-Agent': self.UA},
                                        timeout=15, verify=False)
            response.raise_for_status()
            text = response.text
            if '#EXTM3U' not in text[:256]:
                return [502, 'text/plain', b'Invalid m3u8']
            base = source.rsplit('/', 1)[0] + '/'

            # 预览清单名不能直接删除 _preview；完整清单名来自首个媒体分片前缀。
            # 例如 13813945TFJI9xdG_i0.ts -> 13813945TFJI9xdG_i.m3u8。
            if re.search(r'_preview\.m3u8(?:$|[?#])', source, re.I):
                first_media = next((x.strip() for x in text.splitlines()
                                    if x.strip() and not x.lstrip().startswith('#')), '')
                media_name = first_media.split('?', 1)[0].rsplit('/', 1)[-1]
                match = re.match(r'(.+?)(\d+)(\.[^.]+)$', media_name)
                if match:
                    full_url = urljoin(base, match.group(1) + '.m3u8')
                    full_resp = self.session.get(full_url, headers={'User-Agent': self.UA},
                                                 timeout=15, verify=False)
                    if full_resp.status_code == 200 and '#EXTM3U' in full_resp.text[:256]:
                        source, text = full_url, full_resp.text
                        base = full_url.rsplit('/', 1)[0] + '/'

            # 种子文件：与最终清单同目录，清单名去掉 _preview 后换 .jpg。
            # 例如 531642_i_preview.m3u8 -> 531642_i_preview.jpg（与网页端一致）。
            manifest_name = source.rsplit('/', 1)[-1].split('?')[0]
            seed_name = re.sub(r'\.m3u8$', '.jpg', manifest_name, flags=re.I)
            seed_url = base + seed_name

            def rewrite_uri(match):
                target = urljoin(base, match.group(1))
                proxied = self._proxy_url(target)
                if '.key' in target.lower().rsplit('/', 1)[-1]:
                    proxied += '&seed=' + quote(seed_url, safe='')
                return 'URI="' + proxied + '"'

            text = re.sub(r'URI="([^"]+)"', rewrite_uri, text, flags=re.I)
            lines = []
            for line in text.splitlines():
                value = line.strip()
                if value and not value.startswith('#'):
                    lines.append(self._proxy_url(urljoin(base, value)))
                else:
                    lines.append(line)
            body = ('\n'.join(lines) + '\n').encode('utf-8')
            return [200, 'application/vnd.apple.mpegurl', body]
        except Exception as e:
            try:
                self.log('海角预览清单重写失败: %s' % e)
            except Exception:
                pass
            return [502, 'text/plain', b'Preview m3u8 rewrite failed']