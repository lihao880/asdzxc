# coding: utf-8
import json
import re
from urllib.parse import quote, unquote, urljoin
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = 'https://bbav110.com'
        self.ua = 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36'
        self.cookie = ''
        self.headers = {'User-Agent': self.ua, 'Referer': self.host + '/'}
        self.classes = [
            {'type_id': 'video_all', 'type_name': '🎬 视频大区'},
            {'type_id': 'premium', 'type_name': '💎 VIP专区'},
            {'type_id': 'free', 'type_name': '🆓 免费专区'},
            {'type_id': 'new', 'type_name': '🆕 最近更新'},
            {'type_id': 'short', 'type_name': '📱 短视频'},
            {'type_id': 'album_all', 'type_name': '📸 相册大区'}
        ]
        self._home_cache = None
        self.filters = {
            'video_all': [{'key': 'cat', 'name': '视频分类', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '国产自拍', 'v': '21c031e02ee6ad29acda82b9625b28ef'},
                {'n': '高清无码', 'v': 'cd80c93db2d41150d80f5668f6e20b7f'},
                {'n': '女主播', 'v': '49f3b2bc1aec44b8a0fc03926ffe7499'},
                {'n': '主播福利', 'v': '90884db3ccf63485ae6bd49c0110269f'},
                {'n': '传媒映画', 'v': 'f770c0df1435be8aea4e2e2f4ad5d7f2'},
                {'n': '中文字幕', 'v': '6eec9fd0dad785e04651354b8ddab749'},
                {'n': '欧美风情', 'v': 'a0b14da040498ca8c3882059087b722c'},
                {'n': 'FC2', 'v': 'fc2'},
                {'n': '東南亚', 'v': 'cba2b3bf1b2d7959c9defe5bf2ebd542'},
                {'n': '无码', 'v': 'e93b363376180bd0b49b90d343aa5cbc'},
                {'n': '动漫', 'v': 'b83d6021cfa5cc3a3feff746a6f72b12'},
                {'n': '三级电影', 'v': 'fa7224cfdf3ebea8b4da1083c0c407b8'},
                {'n': '自拍视频', 'v': 'amateur'},
                {'n': 'School Girls', 'v': 'school-girls'},
                {'n': '自慰玩法', 'v': '106d2424c60ca7d4cbe8f303ae25f753'},
                {'n': '射精高潮', 'v': 'c216c7f1783dca2b878bd00bd68acec1'},
                {'n': '体位玩法', 'v': '426d7277ef8a7a3941917b97a66dd5c5'},
                {'n': '多人互动', 'v': '7b43c401900fda19fd81d224ca4b50e2'},
                {'n': '口腔玩法', 'v': '34956d4102137d53d264404c4ab126fd'}
            ]}],
            'album_all': [{'key': 'cat', 'name': '相册分类', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '国产自拍', 'v': '21c031e02ee6ad29acda82b9625b28ef'},
                {'n': '高清无码', 'v': 'cd80c93db2d41150d80f5668f6e20b7f'},
                {'n': '女主播', 'v': '49f3b2bc1aec44b8a0fc03926ffe7499'},
                {'n': '主播福利', 'v': '90884db3ccf63485ae6bd49c0110269f'},
                {'n': '传媒映画', 'v': 'f770c0df1435be8aea4e2e2f4ad5d7f2'},
                {'n': 'FC2', 'v': 'fc2'},
                {'n': '网红黑料', 'v': '5c977f3f8c18750a85d37f8d301f4f51'}
            ]}]
        }

    def getName(self):
        return '爱微社区'

    def getDependence(self):
        return []

    def init(self, extend=''):
        self.cookie = ''
        try:
            cfg = extend if isinstance(extend, dict) else json.loads(extend or '{}')
            self.cookie = str(cfg.get('cookie') or cfg.get('Cookie') or '').strip()
            custom = str(cfg.get('host') or '').strip().rstrip('/')
            if custom.startswith('http'):
                self.host = custom
        except Exception:
            if isinstance(extend, str) and '=' in extend:
                self.cookie = extend.strip()
        self.headers = {'User-Agent': self.ua, 'Referer': self.host + '/'}
        if self.cookie:
            self.headers['Cookie'] = self.cookie

    def homeContent(self, filter=False):
        # 首页只放大区，避免把全部细分类铺平造成分类混乱；二级目录在 categoryContent 内展开。
        return {'class': self.classes, 'filters': self.filters}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            html = self._get(self.host + '/')
            return {'list': self._parse_cards(html, 40)}
        except Exception as e:
            self.log({'action': '首页解析失败', 'error': str(e)})
            return {'list': []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = self._int(pg, 1)
        tid = str(tid or '')
        ext = self._extend(extend)
        if tid.startswith('search:'):
            return self._search_page(unquote(tid[7:]), page)
        if tid == 'short':
            return self._short_page(page)
        if tid == 'premium':
            base = self.host + '/premium/'
        elif tid == 'free':
            base = self.host + '/free/'
        elif tid == 'new':
            base = self.host + '/new/'
        elif tid == 'video_all':
            cat = str(ext.get('cat') or '').strip()
            base = self.host + ('/categories/' + cat + '/' if cat else '/')
        elif tid == 'album_all':
            cat = str(ext.get('cat') or '').strip()
            base = self.host + ('/albums/categories/' + cat + '/' if cat else '/albums/')
        else:
            # 兼容旧配置中直接传分类 id，但首页不再铺平这些细分类
            base = self.host + '/categories/' + tid.strip('/') + '/'
        url = base if page == 1 else base.rstrip('/') + '/' + str(page) + '/'
        try:
            html = self._get(url)
            items = self._parse_album_cards(html, 60) if '/albums/' in base else self._parse_cards(html, 60)
            return self._page(items, page)
        except Exception as e:
            self.log({'action': '分类解析失败', 'tid': tid, 'url': url, 'extend': ext, 'error': str(e)})
            return self._page([], page, 1)
    def detailContent(self, ids):
        raw = str(ids[0] if ids else '')
        if raw.startswith('album@@'):
            return self._album_detail(raw)
        if raw.startswith('short@@'):
            p = raw.split('@@')
            name = p[2] if len(p) > 2 else '短视频'
            pic = p[3] if len(p) > 3 else ''
            remark = p[4] if len(p) > 4 else ''
            url = p[1] if len(p) > 1 else ''
            return {'list': [{'vod_id': raw, 'vod_name': name, 'vod_pic': pic, 'vod_remarks': remark, 'vod_content': remark, 'vod_play_from': '短视频', 'vod_play_url': '播放$' + url}]}
        raw = str(ids[0] if ids else '')
        page_url, old_name, old_pic, old_remark = self._unpack(raw)
        page_url = urljoin(self.host + '/', page_url)
        name, pic, remark, content = old_name or '视频', old_pic, old_remark, old_remark
        vip_url = ''
        try:
            html = self._get(page_url)
            name = self._match(html, r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)') or \
                   self._match(html, r'<h1[^>]*>(.*?)</h1>') or name
            name = re.sub(r'<[^>]+>', '', name).strip() or old_name or '视频'
            pic = self._match(html, r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)') or \
                  self._match(html, r'poster\s*:\s*["\']([^"\']+)') or pic
            duration = self._match(html, r'<meta\s+property=["\']video:duration["\']\s+content=["\'](\d+)')
            if duration:
                remark = self._duration(duration)
            vid = self._video_id(page_url, html)
            # 只保留站点实际下发的 VIP/newembed 线路，不展示试看 MP4 和完整版入口
            embed = self._match(html, r'<meta\s+property=["\']og:video["\']\s+content=["\']([^"\']+)') or \
                    self._match(html, r'<meta\s+name=["\']twitter:player["\']\s+content=["\']([^"\']+)')
            if not embed and vid:
                embed = self.host + '/newembed/' + vid
            if embed:
                embed = urljoin(self.host + '/', embed)
                vip_url = self._resolve_embed(embed, page_url) or embed
        except Exception as e:
            self.log({'action': '详情解析失败，降级VIP入口', 'url': page_url, 'error': str(e)})
        if not vip_url:
            vid = self._video_id(page_url, '')
            vip_url = self.host + '/newembed/' + vid if vid else page_url
        vod = {
            'vod_id': raw,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': remark,
            'vod_content': content or remark,
            'vod_play_from': 'VIP线路',
            'vod_play_url': '播放$' + vip_url
        }
        return {'list': [vod]}


    def searchContent(self, key, quick=False, pg='1'):
        return self._search_page(str(key or ''), self._int(pg, 1))

    def playerContent(self, flag, id, vipFlags=None):
        raw_id = str(id or '').replace('\\/', '/')
        if raw_id.startswith('pics@@'):
            return {'parse': 0, 'url': 'pics://' + raw_id[6:], 'header': ''}
        page_url = urljoin(self.host + '/', raw_id)
        media_header = {'User-Agent': self.ua, 'Referer': self.host + '/'}
        if re.search(r'\.(?:m3u8|mp4)(?:\?|$)', page_url, re.I):
            return {'parse': 0, 'url': page_url, 'header': json.dumps(media_header)}
        try:
            # newembed 是真实下发 m3u8 的入口，不能直接 parse=1 嗅探
            if '/newembed/' in page_url:
                u = self._resolve_embed(page_url, self.host + '/')
                if u:
                    media_header['Referer'] = page_url
                    return {'parse': 0, 'url': u, 'header': json.dumps(media_header)}
            html = self._get(page_url)
            csrf = self._match(html, r'PLAYER_CSRF\s*=\s*["\']([^"\']+)')
            direct = self._match(html, r'currentVideoURL\s*=\s*["\']([^"\']+)')
            sources = []
            default_key = ''
            if csrf:
                api = self.host + '/player/spped.php?csrf=' + quote(csrf, safe='')
                data = self._json(self._get(api, page_url))
                sources = data.get('sources') if isinstance(data.get('sources'), list) else []
                default_key = str(data.get('defaultKey') or '')
                if data.get('direct') and direct:
                    sources.insert(0, {'key': 'direct', 'name': '直连', 'url': direct})
            candidates = []
            for item in sources:
                try:
                    if not isinstance(item, dict):
                        continue
                    u = str(item.get('url') or '').replace('\\/', '/')
                    if re.search(r'\.(?:m3u8|mp4)(?:\?|$)', u, re.I):
                        candidates.append((str(item.get('key') or ''), u))
                except Exception as e:
                    self.log({'action': '跳过异常线路', 'error': str(e)})
                    continue
            if candidates:
                final = next((u for k, u in candidates if k == default_key), candidates[0][1])
                media_header['Referer'] = page_url
                return {'parse': 0, 'url': final, 'header': json.dumps(media_header)}
            # 详情页 og:video/twitter:player 指向 newembed，VIP/private/free 都可追到 m3u8
            embed = self._match(html, r'<meta\s+property=["\']og:video["\']\s+content=["\']([^"\']+)') or \
                    self._match(html, r'<meta\s+name=["\']twitter:player["\']\s+content=["\']([^"\']+)')
            if embed:
                eu = self._resolve_embed(urljoin(self.host + '/', embed), page_url)
                if eu:
                    media_header['Referer'] = urljoin(self.host + '/', embed)
                    return {'parse': 0, 'url': eu, 'header': json.dumps(media_header)}
            direct = direct.replace('\\/', '/') if direct else ''
            if re.search(r'\.(?:m3u8|mp4)(?:/|\?|$)', direct, re.I):
                media_header['Referer'] = page_url
                return {'parse': 0, 'url': direct, 'header': json.dumps(media_header)}
            media = self._extract_media(html)
            if media:
                media_header['Referer'] = page_url
                return {'parse': 0, 'url': media[0], 'header': json.dumps(media_header)}
            vid = self._video_id(page_url, html)
            if vid:
                eu = self._resolve_embed(self.host + '/newembed/' + vid, page_url)
                if eu:
                    media_header['Referer'] = self.host + '/newembed/' + vid
                    return {'parse': 0, 'url': eu, 'header': json.dumps(media_header)}
                return {'parse': 1, 'url': self.host + '/newembed/' + vid, 'header': self.headers}
        except Exception as e:
            self.log({'action': '播放解析失败', 'url': page_url, 'error': str(e)})
        return {'parse': 1, 'url': page_url, 'header': self.headers}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    def action(self, action):
        return {}

    def destroy(self):
        pass

    def _search_page(self, key, page):
        word = quote(str(key or '').strip(), safe='')
        base = self.host + '/search/' + word + '/videos/'
        url = base if page == 1 else base + str(page) + '/'
        try:
            html = self._get(url)
            if re.search(r'没有找到|搜索无结果|暂无数据', html, re.I):
                return self._page([], page, 1)
            return self._page(self._parse_cards(html, 60), page)
        except Exception as e:
            self.log({'action': '搜索失败', 'url': url, 'error': str(e)})
            return self._page([], page, 1)

    def _build_home_classes(self):
        out, seen = [], set()
        def add(tid, name):
            if tid and tid not in seen:
                seen.add(tid); out.append({'type_id': tid, 'type_name': name})
        add('premium', 'VIP专区')
        add('short', '短视频')
        add('albums', '相册')
        add('cat_root', '视频分类')
        add('album_cat_root', '相册分类')
        add('free', '免费专区')
        add('new', '最近更新')
        try:
            html = self._get(self.host + '/categories/')
            for href, title in self._extract_category_links(html, False):
                add(self._cat_tid(href), title)
        except Exception as e:
            self.log({'action': '视频分类动态提取失败', 'error': str(e)})
        try:
            html = self._get(self.host + '/albums/categories/')
            for href, title in self._extract_category_links(html, True):
                add('album_cat@@' + href, '相册·' + title)
        except Exception as e:
            self.log({'action': '相册分类动态提取失败', 'error': str(e)})
        for c in self.classes:
            add(c.get('type_id'), c.get('type_name'))
        return out

    def _cat_tid(self, href):
        return self._match(href, r'/categories/([^/]+)/') or href.rstrip('/').split('/')[-1]

    def _extract_category_links(self, html, album=False):
        base_pat = r'/albums/categories/' if album else r'/categories/'
        out, seen = [], set()
        pat = r'<a[^>]+(?:class=["\'][^"\']*(?:cat-card|feature-card|item)[^"\']*["\'][^>]+)?href=["\']([^"\']*' + base_pat + r'[^"\']+)["\'][^>]*>(.*?)</a>'
        for href, body in re.findall(pat, html or '', re.I | re.S):
            if any(x in href for x in ['/zh/', '/en/', '/tw/', '/ja/', '/kr/', '/vi/', '/th/', '/ms/', '/fil/']):
                continue
            href = urljoin(self.host + '/', href)
            if href in seen:
                continue
            title = self._match(body, r'<div[^>]+class=["\']t["\'][^>]*>(.*?)</div>') or self._match(body, r'title=["\']([^"\']+)')
            title = re.sub(r'<[^>]+>', '', title or '').replace('-爱微社区', '').replace('-艾薇社区', '').strip()
            if title:
                seen.add(href); out.append((href, title))
        return out

    def _category_index(self, page, album=False):
        if page > 1:
            return self._page([], page, 1)
        try:
            html = self._get(self.host + ('/albums/categories/' if album else '/categories/'))
            links = self._extract_category_links(html, album)
            items = []
            prefix = 'album_cat@@' if album else 'url@@'
            for href, title in links:
                items.append({'vod_id': prefix + href, 'vod_name': title, 'vod_pic': '', 'vod_remarks': '二级目录'})
            return self._page(items, 1, 1)
        except Exception as e:
            self.log({'action': '二级分类目录失败', 'album': album, 'error': str(e)})
            return self._page([], 1, 1)

    def _short_page(self, page):
        try:
            per = 24
            exclude = ''
            if page > 1:
                exclude = ','.join(str(i) for i in range(1, min(page * per, 500)))
            data = self._json(self._get(self.host + '/mod/video_ids.php?action=list&per_page=' + str(per) + '&max_duration=60&exclude=' + quote(exclude, safe=','), self.host + '/mod/short.html'))
            videos = ((data.get('data') or {}).get('videos') or []) if isinstance(data, dict) else []
            out = []
            for v in videos:
                try:
                    url = str(v.get('video_url') or '').replace('\\/', '/')
                    name = str(v.get('title') or '短视频')
                    pic = str(v.get('cover_url') or '').replace('\\/', '/')
                    remark = str(v.get('duration_text') or v.get('post_date') or '')
                    if url:
                        out.append({'vod_id': 'short@@' + url + '@@' + name + '@@' + pic + '@@' + remark, 'vod_name': name, 'vod_pic': pic, 'vod_remarks': remark})
                except Exception as e:
                    self.log({'action': '跳过短视频异常项', 'error': str(e)})
            return self._page(out, page)
        except Exception as e:
            self.log({'action': '短视频接口失败', 'error': str(e)})
            return self._page([], page, 1)

    def _parse_album_cards(self, html, limit=60):
        doc = self.html(html)
        nodes = doc.xpath('//a[contains(@href,"/albums/")][.//strong[contains(@class,"title")] or .//img[contains(@class,"thumb")]]')
        out, seen = [], set()
        for node in nodes:
            try:
                href = self._first(node.xpath('./@href'))
                name = self._first(node.xpath('./@title')) or self._text(node.xpath('.//strong[contains(@class,"title")]'))
                if not href or not name or '/albums/categories/' in href or '/albums/tags/' in href:
                    continue
                href = urljoin(self.host + '/', href)
                if href in seen:
                    continue
                seen.add(href)
                pic = self._first(node.xpath('.//img[contains(@class,"thumb")]/@data-original')) or self._first(node.xpath('.//img[contains(@class,"thumb")]/@src'))
                pic = urljoin(self.host + '/', pic) if pic and not pic.startswith('data:') else ''
                photos = self._text(node.xpath('.//*[contains(@class,"photos")]'))
                out.append({'vod_id': 'album@@' + href + '@@' + name.replace('@@','') + '@@' + pic + '@@' + photos, 'vod_name': name.strip(), 'vod_pic': pic, 'vod_remarks': photos})
                if len(out) >= limit:
                    break
            except Exception as e:
                self.log({'action': '跳过相册卡片', 'error': str(e)})
        return out

    def _album_detail(self, raw):
        p = raw.split('@@')
        url = p[1] if len(p) > 1 else ''
        name = p[2] if len(p) > 2 else '相册'
        pic = p[3] if len(p) > 3 else ''
        remark = p[4] if len(p) > 4 else ''
        imgs = []
        try:
            html = self._get(url)
            name = self._match(html, r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)') or name
            pic = self._match(html, r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)') or pic
            for u in re.findall(r'<a[^>]+href=["\']([^"\']+/get_image/[^"\']+)["\']', html, re.I):
                u = urljoin(self.host + '/', u).replace('\\/', '/')
                if u not in imgs:
                    imgs.append(u)
            if not imgs:
                for u in re.findall(r'data-original=["\']([^"\']+/contents/albums/main/[^"\']+)["\']', html, re.I):
                    u = urljoin(self.host + '/', u).replace('/main/200x150/', '/sources/')
                    if u not in imgs:
                        imgs.append(u)
        except Exception as e:
            self.log({'action': '相册详情失败', 'url': url, 'error': str(e)})
        play = '图片$pics@@' + '&&'.join(imgs) if imgs else '图片$pics@@' + pic
        return {'list': [{'vod_id': raw, 'vod_name': name, 'vod_pic': pic, 'vod_remarks': remark, 'vod_content': remark, 'vod_play_from': '相册', 'vod_play_url': play}]}


    def _parse_cards(self, html, limit=60):
        doc = self.html(html)
        nodes = doc.xpath('//a[contains(@href,"/video/")][.//strong[contains(@class,"title")] or .//img[contains(@class,"thumb")]]')
        out, seen = [], set()
        for node in nodes:
            try:
                href = self._first(node.xpath('./@href'))
                name = self._first(node.xpath('./@title')) or self._text(node.xpath('.//strong[contains(@class,"title")]'))
                if not href or not name:
                    continue
                href = urljoin(self.host + '/', href)
                if href in seen:
                    continue
                seen.add(href)
                pic = self._first(node.xpath('.//img[contains(@class,"thumb")]/@data-original'))
                if not pic:
                    pic = self._first(node.xpath('.//img[contains(@class,"thumb")]/@data-webp'))
                if not pic:
                    pic = self._first(node.xpath('.//img[contains(@class,"thumb")]/@src'))
                pic = urljoin(self.host + '/', pic) if pic and not pic.startswith('data:') else ''
                duration = self._text(node.xpath('.//*[contains(@class,"duration")]'))
                access = self._first(node.xpath('.//*[contains(@class,"line-premium")]//*[local-name()="svg"]/@aria-label'))
                remark = ' · '.join(x for x in [access, duration] if x)
                packed = self._pack(href, name, pic, remark)
                out.append({'vod_id': packed, 'vod_name': name.strip(), 'vod_pic': pic, 'vod_remarks': remark})
                if len(out) >= limit:
                    break
            except Exception as e:
                self.log({'action': '跳过异常卡片', 'error': str(e)})
        return out
    def _get(self, url, referer=''):
        h = dict(self.headers)
        h['Referer'] = referer or self.host + '/'
        r = self.fetch(url, headers=h, timeout=15)
        return r.text

    def _video_id(self, url, html=''):
        return self._match(url, r'/(?:video|newembed|videos)/(\d+)(?:/|$)') or \
               self._match(html, r'newembed/(\d+)') or \
               self._match(html, r'videoId\s*[:=]\s*["\']?(\d+)') or \
               self._match(html, r'data-fav-video-id=["\'](\d+)')

    def _extract_media(self, html):
        out, seen = [], set()
        patterns = [
            r'file\s*:\s*["\']([^"\']+\.(?:m3u8|mp4)(?:\?[^"\']*)?)',
            r'var\s+url\s*=\s*["\']([^"\']+\.(?:m3u8|mp4)(?:\?[^"\']*)?)',
            r'["\']url["\']\s*:\s*["\']([^"\']+\.(?:m3u8|mp4)(?:\?[^"\']*)?)',
            r'(https?://[^"\'<>\s]+\.(?:m3u8|mp4)(?:\?[^"\'<>\s]*)?)'
        ]
        for pat in patterns:
            for m in re.findall(pat, html or '', re.I | re.S):
                u = str(m).replace('\\/', '/').strip()
                if u and u not in seen:
                    seen.add(u)
                    out.append(u)
        return out

    def _resolve_embed(self, embed_url, referer=''):
        try:
            html = self._get(embed_url, referer or self.host + '/')
            media = self._extract_media(html)
            if media:
                return media[0]
            # 个别页面把地址拆在 JS 字符串里，宽松兜底
            u = self._match(html, r'(https?://[^"\'<>\s]+/videos/\d+/\d+/index\.m3u8[^"\'<>\s]*)')
            return u.replace('\\/', '/') if u else ''
        except Exception as e:
            self.log({'action': 'embed解析失败', 'url': embed_url, 'error': str(e)})
            return ''

    def _add_play(self, groups, urls, group, play):
        if not play or '$' not in play:
            return
        if group in groups:
            idx = groups.index(group)
            old = urls[idx].split('#') if urls[idx] else []
            if play not in old:
                urls[idx] = urls[idx] + '#' + play if urls[idx] else play
        else:
            groups.append(group)
            urls.append(play)


    def _extend(self, extend):
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str) and extend.strip():
            try:
                return json.loads(extend)
            except Exception:
                return {}
        return {}

    def _json(self, text):
        try:
            return json.loads(text)
        except Exception:
            return {}

    def _page(self, items, page, pagecount=999):
        return {'list': items, 'page': int(page), 'pagecount': int(pagecount), 'limit': len(items) or 20, 'total': 999999 if items else 0}

    def _pack(self, url, name, pic, remark):
        return '|$|'.join([url, name.replace('|$|', ''), pic, remark.replace('|$|', '')])

    def _unpack(self, raw):
        p = raw.split('|$|')
        return p[0], p[1] if len(p) > 1 else '', p[2] if len(p) > 2 else '', p[3] if len(p) > 3 else ''

    def _first(self, values):
        return str(values[0]).strip() if values else ''

    def _text(self, values):
        if not values:
            return ''
        node = values[0]
        try:
            return ' '.join(x.strip() for x in node.xpath('.//text()') if x.strip()).strip()
        except Exception:
            return str(node).strip()

    def _match(self, text, pattern):
        m = re.search(pattern, text or '', re.I | re.S)
        return m.group(1).strip() if m else ''

    def _duration(self, seconds):
        s = self._int(seconds, 0)
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        return ('%d:%02d:%02d' % (h, m, sec)) if h else ('%d:%02d' % (m, sec))

    def _int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default