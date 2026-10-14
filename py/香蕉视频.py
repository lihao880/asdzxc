# coding: utf-8
import base64
import hashlib
import html
import json
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, unquote, urljoin, urlparse

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.ext = ''
        self.host = 'https://xj001l5qv9.xjff7064bw.cc'
        self.api_hosts = [self.host]
        self.publish_hosts = ['https://xjtv04.vip', 'https://xjtv02.vip', 'https://xjtv03.vip']
        self.cdn = 'https://fcatmmzmno27.ncqey.com/'
        self.key = b'gFzviOY0zOxVq1cu'
        self.iv = b'ZmA0Osl677UdSrl0'
        self.play_salt = 'wB760Vqpk76oRSVA1TNz'
        self.ua = 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36'
        self.headers = {'User-Agent': self.ua, 'Accept': 'application/json, text/plain, */*',
                        'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
                        'Authorization': 'Bearer null',
                        'X-AUTH-UUID': hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()}
        self.long_channels = [
            ('9', '吃瓜', []), ('14', '探花', []),
            ('5', '传媒', [('40', '麻豆'), ('42', '91'), ('41', '天美'), ('43', '星空'), ('90', '台湾ED'), ('44', '精东'), ('45', '蜜桃'), ('77', '爱豆'), ('46', 'SWAG'), ('47', '果冻'), ('48', '糖心'), ('49', '萝莉社'), ('50', '扣扣'), ('52', '杏吧'), ('53', '大象'), ('54', '皇家'), ('59', '玩偶姐姐')]),
            ('15', '主播', []), ('16', '自拍', []),
            ('3', '日韩', [('18', '有码'), ('19', '无码'), ('20', '中字'), ('21', '乱伦'), ('22', '角色'), ('23', '制服'), ('24', '调教'), ('25', '人妻'), ('26', '素人'), ('27', '女同'), ('28', '群P')]),
            ('4', '欧美', [('29', '黑白配'), ('30', '自拍'), ('31', '媚黑'), ('32', '少女'), ('33', '剧情'), ('34', '派对'), ('35', '女同'), ('36', '男同'), ('37', '肛交'), ('38', '口交'), ('39', 'SM')]),
            ('8', '三级', [('66', '日本'), ('67', '台湾'), ('68', '香港'), ('69', '大陆'), ('70', '韩国'), ('71', '欧美'), ('72', '其他')]),
            ('7', '换脸', []), ('6', '动漫', [('60', '3D'), ('61', '无码'), ('62', '剧情'), ('63', '中字'), ('64', '同人'), ('65', '次元')]),
            ('10', '猎奇', []), ('20', '成人综艺', [('korea', '韩国')]), ('25', '解说', [('89', '水果派')]), ('26', '性爱空客', [])]
        self.novel_categories = [('6', '文学'), ('34', '变身系列'), ('5', '武侠'), ('35', '名人明星'), ('195', '校园'), ('194', '乱伦'), ('181', '人妻文学'), ('180', '强暴虐待'), ('179', '动漫改编'), ('171', '制服')]
        self.audio_categories = [('189', '都市生活'), ('186', '人妻'), ('193', '强暴'), ('192', '露出'), ('190', '校园'), ('188', '群交'), ('187', '乱伦'), ('178', '经典')]
        self.comic_categories = [('172', '日漫'), ('8', '韩漫'), ('209', '原神'), ('208', '国漫'), ('207', '萝莉'), ('206', 'Cosplay'), ('205', '诱惑'), ('204', '口交'), ('203', '内射'), ('202', '乳交'), ('201', '中出'), ('200', '3P'), ('199', '母女'), ('198', '青春'), ('197', '同居'), ('196', '后宫'), ('185', '不伦'), ('184', '调教'), ('183', '有夫之妇'), ('182', '正妹'), ('177', 'BL漫画'), ('176', '真人漫画'), ('173', '3D')]
        self.drama_channels = [('4', '逆袭'), ('9', '玄幻'), ('7', '都市'), ('6', '古风'), ('5', '穿越'), ('1', '霸总'), ('8', '民国'), ('3', '复仇'), ('10', '其他')]
        self.bbs_groups = [
            ('1', '黑料', [('1', '明星黑料'), ('2', '热门大瓜'), ('3', '网红泄密'), ('4', '反差婊'), ('5', '学生校园')]),
            ('2', '微密', [('6', '微密圈'), ('7', '秀人网'), ('8', '网红系列'), ('9', '模特写真')]),
            ('3', '圈子', [('10', '自拍分享'), ('11', '母狗调教'), ('12', '偷拍抄底'), ('13', '裸聊约炮'), ('14', '乱伦佳作'), ('15', 'TS美妖'), ('16', '户外露出'), ('18', '真人漫画'), ('20', '福利姬')])]
        self.classes = [{'type_id': x, 'type_name': n} for x, n in [
            ('discover', '发现'), ('actress', '女优榜'), ('long', '长视频'), ('short', '抖阴'), ('pic', '美图'), ('drama', '短剧'),
            ('novel', '小说'), ('audio', '有声书'), ('comic', '漫画'), ('bbs', '社区')]]
        self.filters = self._build_filters()
        self._hosts_checked = False
        self._config_time = 0
        self.audio_cache_dir = '/storage/emulated/0/tvbox/cache/banana_audio'
        self.audio_cache_limit = 256 * 1024 * 1024
        self.audio_chunk_size = 64 * 1024
        self.audio_segment_size = 512 * 1024
        self._audio_lock = threading.Lock()
        self._audio_meta_cache = {}

    def _values(self, rows, all_name='全部'):
        return [{'n': all_name, 'v': ''}] + [{'n': n, 'v': str(v)} for v, n in rows]

    def _group_filters(self, groups, merged_name='其他分类'):
        result, merged = [], []
        for parent_id, parent_name, children in groups:
            if not children:
                merged.append({'n': parent_name, 'v': '%s|' % parent_id})
                continue
            values = [{'n': '全部', 'v': '%s|' % parent_id}]
            values += [{'n': name, 'v': '%s|%s' % (parent_id, child_id)} for child_id, name in children]
            result.append({'key': 'cate_id', 'name': parent_name, 'value': values})
        if merged:
            result.insert(0, {'key': 'cate_id', 'name': merged_name, 'value': merged})
        return result

    def _build_filters(self):
        sort_video = [{'n': n, 'v': v} for n, v in [('热门', '2'), ('推荐', '0'), ('最新', '1'), ('周热', '5'), ('热搜', '6'), ('点赞', '3'), ('收藏', '4'), ('随机', '7')]]
        book_sort = [{'n': '默认', 'v': ''}, {'n': '上架时间', 'v': 'CreateTime'}, {'n': '最多阅读', 'v': 'ReadingCount'}, {'n': '最多收藏', 'v': 'FavoriteCount'}]
        status = [{'n': '全部', 'v': '-1'}, {'n': '完结', 'v': '0'}, {'n': '连载', 'v': '1'}]
        long_filters = self._group_filters(self.long_channels, '其他频道')
        long_filters.append({'key': 'sort', 'name': '排序', 'value': sort_video})
        bbs_filters = self._group_filters(self.bbs_groups)
        bbs_filters.append({'key': 'sort', 'name': '排序', 'value': [{'n': '热门', 'v': '0'}, {'n': '最新', 'v': '1'}]})
        return {
            'discover': [
                {'key': 'cate_id', 'name': '发现', 'value': [
                    {'n': '推荐', 'v': 'recommend'}, {'n': '吃瓜', 'v': 'chigua'},
                    {'n': '专题合集', 'v': 'collection'}, {'n': '热门榜', 'v': 'rank'},
                    {'n': '主题榜', 'v': 'theme'}]},
                {'key': 'rank', 'name': '榜单', 'value': [
                    {'n': '日榜', 'v': '2'}, {'n': '周榜', 'v': '1'},
                    {'n': '月榜', 'v': '0'}, {'n': '总榜', 'v': 'total'}]}],
            'actress': [
                {'key': 'category', 'name': '分类', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '知名', 'v': '1'}, {'n': '无码', 'v': '2'},
                    {'n': '日本', 'v': '3'}, {'n': '国产', 'v': '4'}, {'n': '素人', 'v': '5'}]},
                {'key': 'sort', 'name': '排序', 'value': [
                    {'n': '全部', 'v': ''}, {'n': '影片数量', 'v': '1'}, {'n': '最多人看', 'v': '2'},
                    {'n': '最多收藏', 'v': '3'}, {'n': '知名度', 'v': '4'}]}],
            'long': long_filters,
            'short': [{'key': 'sort', 'name': '排序', 'value': sort_video}],
            'pic': [{'key': 'sort', 'name': '排序', 'value': [{'n': '最新', 'v': '1'}, {'n': '热门', 'v': '0'}]}],
            'drama': [{'key': 'channel', 'name': '题材', 'value': self._values(self.drama_channels)}],
            'novel': [{'key': 'category', 'name': '分类', 'value': self._values(self.novel_categories)}, {'key': 'status', 'name': '状态', 'value': status}, {'key': 'booksort', 'name': '排序', 'value': book_sort}],
            'audio': [{'key': 'category', 'name': '分类', 'value': self._values(self.audio_categories)}, {'key': 'status', 'name': '状态', 'value': status}, {'key': 'booksort', 'name': '排序', 'value': book_sort}],
            'comic': [{'key': 'category', 'name': '分类', 'value': self._values(self.comic_categories)}, {'key': 'status', 'name': '状态', 'value': status}, {'key': 'booksort', 'name': '排序', 'value': book_sort}],
            'bbs': bbs_filters
        }

    def getName(self): return '香蕉集合'
    def getDependence(self): return []
    def setExtendInfo(self, extend): self.ext = extend or ''
    def init(self, extend=''): self.ext = getattr(self, 'ext', '') or extend or ''
    def homeLayout(self): return 0
    def manualVideoCheck(self): return False
    def isVideoFormat(self, url): return bool(re.search(r'\.(?:m3u8|mp4|flv)(?:$|[?#])', str(url or ''), re.I))

    def _text(self, response):
        value = getattr(response, 'text', None) if response is not None else None
        if value is not None: return str(value)
        raw = getattr(response, 'content', b'') if response is not None else b''
        return raw if isinstance(raw, str) else bytes(raw or b'').decode('utf-8', 'ignore')

    def _content(self, response):
        raw = getattr(response, 'content', None) if response is not None else None
        return raw.encode() if isinstance(raw, str) else bytes(raw or self._text(response).encode())

    def _decrypt(self, value):
        return unpad(AES.new(self.key, AES.MODE_CBC, self.iv).decrypt(base64.b64decode(value.strip() if isinstance(value, str) else value)), 16)

    def _encrypt(self, value):
        if not isinstance(value, (str, bytes)): value = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        raw = value.encode() if isinstance(value, str) else value
        return base64.b64encode(AES.new(self.key, AES.MODE_CBC, self.iv).encrypt(pad(raw, 16))).decode()

    def _discover_hosts(self):
        if self._hosts_checked: return
        self._hosts_checked = True

        def probe(entry):
            try:
                text = self._text(self.fetch(entry, headers={'User-Agent': self.ua}, timeout=6, verify=False))
                return [x.rstrip('/') for x in re.findall(r'https?://[A-Za-z0-9.-]+', text)]
            except Exception:
                return []

        found = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            for rows in pool.map(probe, self.publish_hosts): found.extend(rows)
        self.api_hosts = list(dict.fromkeys(found + self.api_hosts))

    def _api_host(self, host, path, payload):
        try:
            r = self.post(host + '/' + path.lstrip('/'), data=payload, headers=self.headers, timeout=18, verify=False)
            text = self._text(r).strip()
            if not text or text.startswith('<'): return {}
            result = json.loads(self._decrypt(text).decode('utf-8', 'ignore'))
            if str(result.get('code')) == '200':
                self.host = host
                return result
        except Exception as exc:
            self.log('接口失败 %s: %s' % (path, exc))
        return {}

    def _api(self, path, data=None, encrypted=False):
        payload = self._encrypt(data or {}) if encrypted else data
        tried = set()
        for host in list(self.api_hosts):
            tried.add(host)
            result = self._api_host(host, path, payload)
            if result: return result
        self._discover_hosts()
        for host in self.api_hosts:
            if host in tried: continue
            result = self._api_host(host, path, payload)
            if result: return result
        return {}

    def _refresh_config(self):
        if time.time() - self._config_time < 600: return
        rows = self._api('Web/Config2').get('data') or []
        values = {str(x.get('a')): x for x in rows if isinstance(x, dict)}
        domain = ((values.get('PlayDomain') or {}).get('b') or (values.get('ImageDomain') or {}).get('b'))
        if domain: self.cdn = str(domain).rstrip('/') + '/'
        self._config_time = time.time()

    def _full_media(self, path):
        return str(path) if str(path or '').startswith('http') else urljoin(self.cdn, str(path or '').lstrip('/'))

    def _proxy_pic(self, path):
        return self.getProxyUrl() + '&url=' + quote(self._full_media(path), safe='') if path else ''

    def _duration(self, value):
        try:
            n = int(float(value or 0)); return '%d:%02d' % (n // 60, n % 60)
        except Exception: return ''

    def _page(self, data, page, items):
        return {'list': items, 'page': int(page), 'pagecount': int((data or {}).get('pageCount') or page or 1), 'limit': int((data or {}).get('pageSize') or 20), 'total': int((data or {}).get('recordCount') or len(items))}

    def _video_item(self, x, prefix='video'):
        if not isinstance(x, dict): return None
        vid, name = str(x.get('a') or x.get('id') or ''), html.unescape(str(x.get('b') or x.get('title') or '')).strip()
        if not vid or not name: return None
        pic = x.get('j') or x.get('imgUrl') or x.get('coverImage')
        remark = str(x.get('e') or x.get('channelName') or '')
        dur = self._duration(x.get('h') or x.get('duration'))
        if dur: remark = (remark + ' · ' if remark else '') + dur
        return {'vod_id': prefix + '@@' + vid, 'vod_name': name, 'vod_pic': self._proxy_pic(pic), 'vod_remarks': remark}

    def _directory_item(self, x, prefix):
        if not isinstance(x, dict): return None
        rid, name = str(x.get('id') or ''), html.unescape(str(x.get('title') or '')).strip()
        if not rid or not name: return None
        count = x.get('videosCount') if x.get('videosCount') is not None else x.get('videoCount')
        remark = ('%s部' % count) if str(count or '') else str(x.get('channelName') or '二级目录')
        route = prefix + '_dir@@' + rid
        item = {'vod_id': route, 'vod_name': name,
                'vod_pic': self._proxy_pic(x.get('imgUrl')), 'vod_remarks': remark,
                'vod_tag': 'folder'}
        return item

    def _book_item(self, x, prefix):
        if not isinstance(x, dict) or not x.get('id'): return None
        return {'vod_id': prefix + '@@' + str(x['id']), 'vod_name': html.unescape(str(x.get('title') or prefix)), 'vod_pic': self._proxy_pic(x.get('coverUrl')), 'vod_remarks': str(x.get('categoryName') or '') + (' · 连载' if str(x.get('status')) == '1' else ' · 完结')}

    def _is_media_url(self, value):
        value = str(value or '').strip()
        if not value or value.startswith(('blob:', '#')):
            return False
        if value.startswith(('http://', 'https://')):
            return True
        return bool(re.search(r'\.(?:m3u8|mp4|flv)(?:$|[?#])', value, re.I))

    def _post_item(self, x, prefix='bbs'):
        if not isinstance(x, dict) or not x.get('id'): return None
        imgs = [i for i in str(x.get('imgs') or '').split(',') if i]
        channel = x.get('subChannel') or x.get('channel') or {}
        video = str(x.get('videos') or '').strip()
        has_video = self._is_media_url(video)
        media = []
        if has_video: media.append('视频')
        if imgs: media.append('%s图' % (x.get('imageCount') or len(imgs)))
        remark = ' + '.join(media) or '帖子'
        if channel.get('title'): remark = str(channel.get('title')) + ' · ' + remark
        return {'vod_id': prefix + '@@' + str(x['id']), 'vod_name': html.unescape(str(x.get('title') or '社区内容')), 'vod_pic': self._proxy_pic(imgs[0]) if imgs else '', 'vod_remarks': remark}

    def homeContent(self, filter=False): return {'class': self.classes, 'filters': self.filters}
    def getHomeContent(self, filter=False): return self.homeContent(filter)

    def homeVideoContent(self):
        data = self._api('Web/IndexVideo2', {'Filter': '1'}).get('data') or {}
        rows = [self._video_item(x) for x in data.get('Recommended') or []]
        return {'list': [x for x in rows if x]}

    def _extend(self, extend):
        if isinstance(extend, dict): return extend
        try: return json.loads(extend or '{}')
        except Exception: return {}

    def _selected_route(self, extend, default_parent='', legacy_parent='', legacy_child=''):
        selected = str((extend or {}).get('cate_id') or '')
        if selected:
            parent, child = (selected.split('|', 1) + [''])[:2]
            return parent or default_parent, child
        parent = str((extend or {}).get(legacy_parent) or default_parent)
        child = str((extend or {}).get(legacy_child) or '')
        return parent, child

    def categoryContent(self, tid, pg, filter, extend):
        try: page = max(1, int(pg or 1))
        except Exception: page = 1
        ex = self._extend(extend)
        try:
            tid = str(tid or '')
            if tid.startswith('collection_dir@@'):
                collection_id = tid.split('@@', 1)[1]
                payload = {'PageIndex': page, 'PageSize': 30, 'SortType': 1, 'CollectionId': collection_id}
                data = self._api('Web/VideoList2', payload).get('data') or {}
                rows = [self._video_item(x, 'video') for x in (data.get('items') or data.get('newVideos') or [])]
            elif tid.startswith('theme_dir@@'):
                keyword = unquote(tid.split('@@', 1)[1])
                payload = {'SearchType': 1, 'KeyWord': keyword, 'PageIndex': page, 'PageSize': 30}
                data = self._api('WEB/SearchByKeyword', payload, True).get('data') or {}
                rows = [self._video_item(x, 'video') for x in data.get('items') or []]
            elif tid.startswith('actress_dir@@'):
                actress_id = tid.split('@@', 1)[1]
                payload = {'PageIndex': page, 'PageSize': 30, 'SortType': 1, 'ActressId': actress_id}
                data = self._api('Web/VideoList2', payload).get('data') or {}
                rows = [self._video_item(x, 'video') for x in (data.get('items') or data.get('newVideos') or [])]
            elif tid == 'actress':
                payload = {'PageIndex': page, 'PageSize': 20,
                           'CategoryId': str(ex.get('category') or ''),
                           'SortType': str(ex.get('sort') or '')}
                data = self._api('Web/ActressList', payload).get('data') or {}
                rows = [self._directory_item(x, 'actress') for x in data.get('items') or []]
            elif tid == 'discover':
                route = str(ex.get('cate_id') or 'recommend')
                if route == 'collection':
                    data = self._api('Collection/CollectionList', {'PageIndex': page, 'PageSize': 20, 'SortType': 1}, True).get('data') or {}
                    rows = [self._directory_item(x, 'collection') for x in data.get('items') or []]
                elif route == 'theme':
                    groups = self._api('Web/ThemeList').get('data') or []
                    flat = [x for group in groups if isinstance(group, dict) for x in (group.get('items') or [])]
                    start, end = (page - 1) * 40, page * 40
                    data = {'pageCount': max(1, (len(flat) + 39) // 40), 'pageSize': 40, 'recordCount': len(flat)}
                    rows = [self._directory_item(dict(x, id=quote(str(x.get('title') or ''), safe='')), 'theme') for x in flat[start:end]]
                elif route == 'rank':
                    rank = str(ex.get('rank') or '2')
                    payload = {'PageIndex': page, 'PageSize': 20, 'SortType': 2}
                    if rank == 'total':
                        data = self._api('Web/VideoList2', payload).get('data') or {}
                    else:
                        payload['RankType'] = rank
                        data = self._api('Web/VideoRankList', payload).get('data') or {}
                    rows = [self._video_item(x, 'video') for x in data.get('items') or []]
                else:
                    payload = {'ChannelId': '9' if route == 'chigua' else '', 'SubChannelId': '',
                               'SortType': 2 if route == 'chigua' else 7, 'IsFirst': page == 1,
                               'PageIndex': page, 'PageSize': 20}
                    data = self._api('Web/VideoList2', payload).get('data') or {}
                    rows = [self._video_item(x, 'video') for x in (data.get('items') or data.get('newVideos') or [])]
            elif tid in ('long', 'short'):
                if tid == 'long':
                    channel, sub_channel = self._selected_route(ex, '9', 'channel', 'sub')
                else:
                    channel, sub_channel = '', ''
                if tid == 'long' and channel == '20' and sub_channel == 'korea':
                    data = self._api('WEB/SearchByKeyword', {'SearchType': 1, 'KeyWord': '韩国综艺', 'PageIndex': page, 'PageSize': 30}, True).get('data') or {}
                    matched = []
                    for x in data.get('items') or []:
                        if str(x.get('channelId') or '') == '20' or str(x.get('channelName') or '') == '成人综艺':
                            matched.append({'id': x.get('id'), 'title': x.get('title'), 'coverImage': str(x.get('coverImage') or '').split(',')[0], 'channelName': x.get('channelName')})
                    rows = [self._video_item(x, 'long') for x in matched]
                else:
                    payload = {'ChannelId': channel, 'SubChannelId': sub_channel, 'SortType': int(ex.get('sort') or (2 if tid == 'long' else 7)), 'IsFirst': page == 1, 'PageIndex': page, 'PageSize': 20}
                    if tid == 'short': payload['VideoType'] = 1
                    data = self._api('Web/VideoList2', payload).get('data') or {}
                    rows = [self._video_item(x, tid) for x in (data.get('items') or data.get('newVideos') or [])]
            elif tid == 'drama':
                data = self._api('ShortMovie/ShortMovieList', {'PageIndex': page, 'PageSize': 20, 'ChannelId': str(ex.get('channel') or '')}, True).get('data') or {}
                rows = [self._video_item(x, 'drama') for x in data.get('items') or []]
            elif tid in ('novel', 'comic', 'audio'):
                payload = {'Type': 0, 'BookStatus': int(ex.get('status') or -1), 'PageIndex': page, 'PageSize': 20}
                if ex.get('category'): payload['CategoryId'] = int(ex['category'])
                if ex.get('booksort'): payload[str(ex['booksort'])] = 1
                path = {'novel': 'Web/NovelList', 'comic': 'Web/ComicsList', 'audio': 'Web/AudioNovelList'}[tid]
                data = self._api(path, payload, True).get('data') or {}
                rows = [self._book_item(x, tid) for x in data.get('items') or []]
            else:
                payload = {'PageIndex': page, 'PageSize': 20, 'SortType': int(ex.get('sort') or (1 if tid == 'pic' else 0))}
                if tid == 'bbs':
                    group, sub_group = self._selected_route(ex, '1', 'group', 'sub')
                    payload.update({'ChannelId': group, 'SubChannelId': sub_group})
                data = self._api('BBS/PostList', payload, False).get('data') or {}
                rows = [self._post_item(x, tid) for x in data.get('items') or []]
            return self._page(data, page, [x for x in rows if x])
        except Exception as exc:
            self.log('分类失败: %s' % exc)
            return self._page({}, page, [])

    def _split_id(self, value):
        raw = str(value[0] if isinstance(value, (list, tuple)) else value)
        return raw.split('@@', 1) if '@@' in raw else ('video', raw)

    def detailContent(self, ids):
        typ, rid = self._split_id(ids)
        try:
            if typ in ('actress', 'actress_dir', 'collection', 'collection_dir', 'theme', 'theme_dir'):
                return {'list': []}
            if typ in ('video', 'long', 'short'):
                d = self._api('Web/VideoDetail', {'id': rid}).get('data') or {}
                if not d.get('id'): return {'list': []}
                tags = ' / '.join(str(x.get('title')) for x in d.get('tags') or [] if x.get('title'))
                # 获取推荐视频列表
                recommend_data = self._api('Web/RecommendList', {'VideoId': rid, 'PageIndex': 1, 'PageSize': 6}).get('data') or {}
                recommend_items = recommend_data.get('items') or recommend_data.get('list') or []
                recommend_html = ''
                if recommend_items:
                    rec_lines = ['【相关推荐】']
                    for idx, item in enumerate(recommend_items[:6], 1):
                        title = str(item.get('b') or item.get('title') or '')
                        vid = str(item.get('a') or item.get('id') or '')
                        if title and vid:
                            rec_lines.append('  %s. %s' % (idx, title))
                    recommend_html = '\n'.join(rec_lines)
                content_parts = []
                if tags:
                    content_parts.append('标签：' + tags)
                channel_name = str(d.get('channelName') or '')
                if channel_name:
                    content_parts.append('频道：' + channel_name)
                if recommend_html:
                    content_parts.append('')
                    content_parts.append(recommend_html)
                vod_content = '\n'.join(content_parts) if content_parts else (tags or channel_name or '')
                vod = {'vod_id': typ + '@@' + rid, 'vod_name': str(d.get('title') or '视频'), 'vod_pic': self._proxy_pic(d.get('imgUrl')), 'type_name': str(d.get('channelName') or ''), 'vod_remarks': self._duration(d.get('duration')), 'vod_content': vod_content, 'vod_play_from': '香蕉直链', 'vod_play_url': '播放$play@@' + str(d.get('playUrl') or rid)}
            elif typ == 'drama':
                d = self._api('ShortMovie/ShortMovieDetail', {'id': rid}, True).get('data') or {}
                plays = ['第%s集$play@@%s' % (x.get('collectionIndex') or i + 1, x.get('playUrl')) for i, x in enumerate(d.get('items') or []) if x.get('playUrl')]
                vod = {'vod_id': typ + '@@' + rid, 'vod_name': str(d.get('title') or '短剧'), 'vod_pic': self._proxy_pic(d.get('imgUrl')), 'type_name': str(d.get('channelName') or '短剧'), 'vod_remarks': '更新至%s集' % (d.get('currentEpisodes') or len(plays)), 'vod_content': str(d.get('introduction') or ''), 'vod_play_from': '短剧直链', 'vod_play_url': '#'.join(plays)}
            elif typ in ('novel', 'comic', 'audio'):
                path = {'novel': 'Web/NovelInfo', 'comic': 'Web/ComicsInfo', 'audio': 'Web/AudioNovelInfo'}[typ]
                d = self._api(path, {'id': rid, 'PageSize': 999, 'pageSize': 999}, True).get('data') or {}
                book = (d.get('newVideos') or {}).get('book') or {}
                mark = {'novel': 'novelch', 'comic': 'comicch', 'audio': 'audioch'}[typ]
                if typ == 'audio':
                    meta = base64.urlsafe_b64encode(json.dumps({
                        'book': str(book.get('title') or '有声书'),
                        'pic': str(book.get('coverUrl') or '')
                    }, ensure_ascii=False, separators=(',', ':')).encode()).decode().rstrip('=')
                    plays = ['%s$%s@@%s@@%s@@%s' % (x.get('title') or '正文', mark, rid, x.get('id'), meta) for x in d.get('items') or [] if x.get('id')]
                else:
                    plays = ['%s$%s@@%s@@%s' % (x.get('title') or '正文', mark, rid, x.get('id')) for x in d.get('items') or [] if x.get('id')]
                source = {'novel': '小说阅读', 'comic': '漫画阅读', 'audio': '有声书播放'}[typ]
                vod = {'vod_id': typ + '@@' + rid, 'vod_name': str(book.get('title') or typ), 'vod_pic': self._proxy_pic(book.get('coverUrl')), 'type_name': str(book.get('categoryName') or ''), 'vod_remarks': '%s章' % len(plays), 'vod_content': str(book.get('description') or ''), 'vod_play_from': source, 'vod_play_url': '#'.join(plays)}
            else:
                d = self._api('BBS/PostDetail', {'id': rid}, False).get('data') or {}
                imgs = [x for x in str(d.get('imgs') or d.get('coverImgs') or '').split(',') if x]
                video = str(d.get('videos') or '').strip()
                has_video = self._is_media_url(video)
                sources, groups = [], []
                if has_video:
                    sources.append('帖子视频')
                    groups.append('播放$play@@' + video)
                if imgs:
                    sources.append('帖子图集')
                    groups.append('点击浏览$pics@@' + '||'.join(imgs))
                user = d.get('user') or {}
                media = []
                if has_video: media.append('视频')
                if imgs: media.append('%s图' % len(imgs))
                vod = {'vod_id': typ + '@@' + rid, 'vod_name': html.unescape(str(d.get('title') or '社区内容')), 'vod_pic': self._proxy_pic(imgs[0]) if imgs else '', 'type_name': str((d.get('subChannel') or d.get('channel') or {}).get('title') or '社区'), 'vod_remarks': ' + '.join(media) or '帖子', 'vod_content': '发布者：' + str(user.get('nickName') or ''), 'vod_play_from': '$$$'.join(sources), 'vod_play_url': '$$$'.join(groups)}
            return {'list': [vod]}
        except Exception as exc:
            self.log('详情失败: %s' % exc)
            return {'list': []}
    def recommendContent(self, ids, pg):
        """推荐视频 - 壳端播放时自动调用，传入当前视频ID"""
        try:
            typ, rid = self._split_id(ids)
            if typ not in ('video', 'long', 'short'):
                return {'list': []}
            page = max(1, int(pg or 1))
            # 调用推荐API，获取基于当前视频的推荐列表
            payload = {'PageIndex': page, 'PageSize': 10, 'VideoId': rid}
            data = self._api('Web/RecommendList', payload).get('data') or {}
            items = data.get('items') or data.get('list') or []
            rows = [self._video_item(x, 'video') for x in items if x]
            return {'list': [x for x in rows if x]}
        except Exception as exc:
            self.log('推荐失败: %s' % exc)
            return {'list': []}
    def searchContent(self, key, quick, pg='1'):
        try: page = max(1, int(pg or 1))
        except Exception: page = 1
        keyword = str(key or '').strip()
        if not keyword: return {'list': [], 'page': page, 'pagecount': page, 'limit': 70, 'total': 0}
        sources = [
            (1, 'video', '长视频'), (2, 'short', '抖阴'), (3, 'drama', '短剧'),
            (4, 'bbs', '社区'), (5, 'novel', '小说'), (6, 'comic', '漫画'), (8, 'audio', '有声书')]

        def search_one(search_type):
            try:
                data = self._api('WEB/SearchByKeyword', {'SearchType': search_type, 'KeyWord': keyword,
                    'PageIndex': page, 'PageSize': 10}, True).get('data') or {}
                return list(data.get('items') or []), int(data.get('pageCount') or page)
            except Exception as exc:
                self.log('搜索类型%s失败: %s' % (search_type, exc))
                return [], page

        fetched = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = {pool.submit(search_one, search_type): search_type for search_type, _, _ in sources}
            for job in as_completed(jobs):
                search_type = jobs[job]
                try: fetched[search_type] = job.result()
                except Exception as exc:
                    self.log('搜索并发任务%s失败: %s' % (search_type, exc))
                    fetched[search_type] = ([], page)

        rows, seen, pagecount = [], set(), page
        for search_type, prefix, source in sources:
            items, count = fetched.get(search_type, ([], page))
            pagecount = max(pagecount, count)
            for raw in items:
                try:
                    cover = str(raw.get('coverImage') or raw.get('coverUrl') or '').split(',')[0]
                    if prefix in ('novel', 'comic', 'audio'):
                        item = self._book_item({'id': raw.get('id'), 'title': raw.get('title'),
                            'coverUrl': cover, 'categoryName': raw.get('channelName'), 'status': 0}, prefix)
                    elif prefix == 'bbs':
                        item = {'vod_id': 'bbs@@' + str(raw.get('id')), 'vod_name': html.unescape(str(raw.get('title') or '社区内容')),
                            'vod_pic': self._proxy_pic(cover), 'vod_remarks': str(raw.get('subChannelName') or raw.get('channelName') or '')}
                    else:
                        item = self._video_item({'id': raw.get('id'), 'title': raw.get('title'),
                            'coverImage': cover, 'channelName': raw.get('channelName')}, prefix)
                    if not item or item['vod_id'] in seen: continue
                    seen.add(item['vod_id'])
                    remark = str(item.get('vod_remarks') or '').strip()
                    item['vod_remarks'] = '[%s]%s' % (source, (' ' + remark) if remark else '')
                    rows.append(item)
                except Exception as exc:
                    self.log('搜索结果转换失败: %s' % exc)
        return {'list': rows, 'page': page, 'pagecount': pagecount, 'limit': 70, 'total': len(rows)}

    def _signed_play_url(self, relative):
        if not relative: return ''
        self._refresh_config()
        parsed = urlparse(str(relative))
        rel = parsed.path.lstrip('/') if parsed.scheme else str(relative).split('?', 1)[0].lstrip('/')
        stamp = str(int(time.time()))
        sign = hashlib.md5(('%s/%s%s' % (self.play_salt, rel, stamp)).encode()).hexdigest()
        base = str(relative) if parsed.scheme else urljoin(self.cdn, rel)
        return base + ('&' if '?' in base else '?') + 'sign=' + sign + '&t=' + stamp

    def playerContent(self, flag, id, vipFlags):
        raw = str(id or '')
        try:
            if raw.startswith('play@@'):
                value = raw.split('@@', 1)[1]
                if not value.startswith(('http://', 'https://')) and not self.isVideoFormat(value):
                    value = (self._api('Web/VideoDetail', {'id': value}).get('data') or {}).get('playUrl')
                return {'parse': 0, 'jx': 0, 'url': self._signed_play_url(value), 'header': {'User-Agent': self.ua}}
            if raw.startswith('pics@@'):
                paths = [x for x in raw.split('@@', 1)[1].split('||') if x]
                urls = [self._proxy_pic(x) for x in paths]
                return {'parse': 0, 'playUrl': '', 'url': 'pics://' + '&&'.join(urls), 'header': ''}
            if raw.startswith(('novelch@@', 'comicch@@', 'audioch@@')):
                parts = raw.split('@@')
                typ, book, chapter = parts[:3]
                meta = {}
                if typ == 'audioch' and len(parts) > 3:
                    try:
                        token = parts[3] + '=' * (-len(parts[3]) % 4)
                        meta = json.loads(base64.urlsafe_b64decode(token).decode('utf-8'))
                    except Exception: meta = {}
                path = {'novelch': 'Web/ChapterDetails', 'comicch': 'Web/ComicsChapterDetails', 'audioch': 'Web/AudioChapterDetails'}[typ]
                d = self._api(path, {'bookId': book, 'id': chapter}, True).get('data') or {}
                title, content = str(d.get('title') or '正文'), str(d.get('contents') or '')
                if typ == 'novelch':
                    return {'parse': 0, 'url': 'novel://' + json.dumps({'title': title, 'content': content}, ensure_ascii=False), 'header': ''}
                if typ == 'audioch':
                    audio = self._full_media(d.get('audioUrl'))
                    proxy = self.getProxyUrl() + '&audio_hls=' + quote(audio, safe='') + '&media=.m3u8'
                    pic = self._proxy_pic(meta.get('pic')) if meta.get('pic') else ''
                    return {'parse': 0, 'jx': 0, 'playUrl': '', 'url': proxy, 'header': {},
                            'type': 'hls', 'format': 'm3u8',
                            'title': title or str(meta.get('book') or '有声书'),
                            'pic': pic, 'poster': pic}
                urls = [self._proxy_pic(x) for x in content.split(',') if x]
                return {'parse': 0, 'playUrl': '', 'url': 'pics://' + '&&'.join(urls), 'header': ''}
            typ, rid = self._split_id(raw)
            if typ in ('video', 'long', 'short'):
                d = self._api('Web/VideoDetail', {'id': rid}).get('data') or {}
                return {'parse': 0, 'jx': 0, 'url': self._signed_play_url(d.get('playUrl')), 'header': {'User-Agent': self.ua}}
        except Exception as exc:
            self.log('播放失败: %s' % exc)
        return {'parse': 0, 'jx': 0, 'url': '', 'header': {}}

    def _image_mime(self, data):
        if data.startswith(b'\xff\xd8\xff'): return 'image/jpeg'
        if data.startswith(b'\x89PNG\r\n\x1a\n'): return 'image/png'
        if data.startswith((b'GIF87a', b'GIF89a')): return 'image/gif'
        if data.startswith(b'RIFF') and data[8:12] == b'WEBP': return 'image/webp'
        return ''

    def _webp_first_frame(self, data):
        if not (data.startswith(b'RIFF') and data[8:12] == b'WEBP' and b'ANIM' in data[:64]): return data
        pos = 12
        while pos + 8 <= len(data):
            kind, size = data[pos:pos + 4], int.from_bytes(data[pos + 4:pos + 8], 'little')
            body = data[pos + 8:pos + 8 + size]
            if kind == b'ANMF' and len(body) > 16:
                chunks, kept, offset = body[16:], b'', 0
                while offset + 8 <= len(chunks):
                    ctype = chunks[offset:offset + 4]
                    length = int.from_bytes(chunks[offset + 4:offset + 8], 'little')
                    end = offset + 8 + length + (length & 1)
                    if ctype in (b'ALPH', b'VP8 ', b'VP8L'): kept += chunks[offset:end]
                    offset = end
                if kept: return b'RIFF' + (len(kept) + 4).to_bytes(4, 'little') + b'WEBP' + kept
            pos += 8 + size + (size & 1)
        return data

    def _decrypt_asset(self, raw):
        candidates = [raw]
        try:
            decoded = base64.b64decode(raw, validate=True)
            if decoded: candidates.insert(0, decoded)
        except Exception: pass
        for encrypted in candidates:
            if len(encrypted) % 16: continue
            try:
                value = unpad(AES.new(self.key, AES.MODE_CBC, self.iv).decrypt(encrypted), 16)
                try:
                    decoded = base64.b64decode(value, validate=True)
                    if decoded: value = decoded
                except Exception: pass
                if value: return value
            except Exception: continue
        return b''

    def _audio_valid(self, data):
        return bool(data) and (data.startswith(b'ID3') or data[:2].hex() in ('fffb', 'fff3', 'fff2'))

    def _trim_audio_cache(self, keep=''):
        try:
            files, total = [], 0
            for name in os.listdir(self.audio_cache_dir):
                path = os.path.join(self.audio_cache_dir, name)
                if not os.path.isfile(path): continue
                size = os.path.getsize(path)
                total += size
                files.append((os.path.getmtime(path), size, path))
            for _, size, path in sorted(files):
                if total <= self.audio_cache_limit: break
                if path == keep: continue
                try:
                    os.remove(path)
                    total -= size
                except Exception: pass
        except Exception: pass

    def _audio_range_bounds(self, header, total):
        if total <= 0: return 0, -1
        match = re.match(r'bytes=(\d*)-(\d*)', str(header or '').strip())
        if not match: return 0, min(total - 1, self.audio_chunk_size - 1)
        first, last = match.groups()
        if first:
            start = int(first)
            end = int(last) if last else start + self.audio_chunk_size - 1
        elif last:
            length = min(int(last), self.audio_chunk_size)
            start, end = total - length, total - 1
        else:
            return 0, -1
        return start, min(end, total - 1)

    def _audio_segment_file(self, target, start, end):
        key = hashlib.md5(('%s|%s|%s' % (target, start, end)).encode()).hexdigest()
        return os.path.join(self.audio_cache_dir, key + '.seg')

    def _read_audio_segment(self, target, start, end):
        path = self._audio_segment_file(target, start, end)
        expected = end - start + 1
        try:
            if os.path.getsize(path) == expected:
                os.utime(path, None)
                with open(path, 'rb') as f: return f.read()
        except Exception: pass
        return b''

    def _save_audio_segment(self, target, start, end, body):
        if not body or len(body) != end - start + 1: return
        path = self._audio_segment_file(target, start, end)
        temp = path + '.tmp'
        try:
            os.makedirs(self.audio_cache_dir, exist_ok=True)
            with open(temp, 'wb') as f: f.write(body)
            os.replace(temp, path)
            self._trim_audio_cache(path)
        except Exception: pass
        finally:
            try:
                if os.path.exists(temp): os.remove(temp)
            except Exception: pass

    def _audio_file(self, target):
        key = hashlib.md5(target.encode()).hexdigest()
        cache = os.path.join(self.audio_cache_dir, key + '.mp3')
        try:
            if os.path.getsize(cache) > 1024:
                os.utime(cache, None)
                return cache
        except Exception: pass
        with self._audio_lock:
            try:
                if os.path.getsize(cache) > 1024:
                    os.utime(cache, None)
                    return cache
            except Exception: pass
            os.makedirs(self.audio_cache_dir, exist_ok=True)
            plain = b''
            for attempt in range(2):
                try:
                    response = self.fetch(target, headers={'User-Agent': self.ua}, timeout=120, verify=False)
                    plain = self._decrypt_asset(self._content(response))
                    if self._audio_valid(plain): break
                except Exception as exc:
                    self.log('音频下载失败(%s/2): %s' % (attempt + 1, exc))
                    plain = b''
            if not self._audio_valid(plain): return ''
            temp = cache + '.tmp'
            try:
                with open(temp, 'wb') as f: f.write(plain)
                os.replace(temp, cache)
                self._trim_audio_cache(cache)
                return cache
            finally:
                try:
                    if os.path.exists(temp): os.remove(temp)
                except Exception: pass

    def _fetch_audio_range(self, target, start, end):
        expected = end - start + 1
        headers = {'User-Agent': self.ua, 'Accept-Encoding': 'identity', 'Connection': 'close',
                   'Range': 'bytes=%s-%s' % (start, end)}
        for attempt in range(2):
            try:
                response = self.fetch(target, headers=headers, timeout=(9 if attempt == 0 else 4), verify=False)
                body = self._content(response)
                status = int(getattr(response, 'status_code', 0) or getattr(response, 'status', 0) or 0)
                response_headers = getattr(response, 'headers', {}) or {}
                content_range = str(response_headers.get('Content-Range') or response_headers.get('content-range') or '')
                if status == 206 and len(body) == expected and content_range:
                    return body, content_range
            except Exception as exc:
                self.log('音频分块失败(%s/2): %s' % (attempt + 1, exc))
        return b'', ''

    def _audio_remote_meta(self, target):
        key = hashlib.md5(target.encode()).hexdigest()
        cached = self._audio_meta_cache.get(key)
        if cached: return cached
        meta_file = os.path.join(self.audio_cache_dir, key + '.meta')
        first_file = os.path.join(self.audio_cache_dir, key + '.first')
        try:
            with open(meta_file, 'r', encoding='utf-8') as f: cached = json.load(f)
            with open(first_file, 'rb') as f: cached['first_chunk'] = f.read()
            if self._audio_valid(cached['first_chunk']) and int(cached.get('mp3_total') or 0) > 0:
                self._audio_meta_cache[key] = cached
                return cached
        except Exception: pass

        first_mp3_end = self.audio_chunk_size - 1
        b64_end = ((first_mp3_end // 3) + 1) * 4 - 1
        cipher_end = ((b64_end // 16) + 1) * 16 - 1
        first_encrypted, content_range = self._fetch_audio_range(target, 0, cipher_end)
        match = re.search(r'/(\d+)$', content_range)
        if not first_encrypted or not match: return {}
        cipher_total = int(match.group(1))

        # 冷启动快路径：不再等待尾部 Range。AES-CBC padding 最多只影响末尾几个字节，
        # 采用常见的4字节 padding 估算总长，首块可以立即交给 EXO；后续 Range 仍会校验边界。
        padding = 4
        b64_length = cipher_total - padding
        if b64_length <= 0 or b64_length % 4: return {}
        mp3_total = (b64_length // 4) * 3
        try:
            decrypted = AES.new(self.key, AES.MODE_CBC, self.iv).decrypt(first_encrypted)
            first_encoded = decrypted[:b64_end + 1]
            first_chunk = base64.b64decode(first_encoded, validate=True)[:self.audio_chunk_size]
        except Exception:
            first_chunk = b''
        if not self._audio_valid(first_chunk): return {}
        meta = {'cipher_total': cipher_total, 'b64_length': b64_length, 'mp3_total': mp3_total,
                'first_chunk': first_chunk, 'approx_total': True}
        self._audio_meta_cache[key] = meta
        try:
            os.makedirs(self.audio_cache_dir, exist_ok=True)
            temp_meta, temp_first = meta_file + '.tmp', first_file + '.tmp'
            saved = dict(meta); saved.pop('first_chunk', None)
            with open(temp_meta, 'w', encoding='utf-8') as f: json.dump(saved, f, separators=(',', ':'))
            with open(temp_first, 'wb') as f: f.write(first_chunk)
            os.replace(temp_meta, meta_file); os.replace(temp_first, first_file)
        except Exception: pass
        return meta

    def _audio_remote_chunk(self, target, start, end, meta):
        b64_length = int(meta.get('b64_length') or 0)
        if b64_length <= 0: return b''
        group_start, group_end = start // 3, end // 3
        b64_start = group_start * 4
        b64_end = min(b64_length - 1, (group_end + 1) * 4 - 1)
        cipher_start = (b64_start // 16) * 16
        cipher_end = min(int(meta['cipher_total']) - 1, ((b64_end // 16) + 1) * 16 - 1)
        fetch_start = 0 if cipher_start == 0 else cipher_start - 16
        encrypted, _ = self._fetch_audio_range(target, fetch_start, cipher_end)
        if not encrypted: return b''
        if cipher_start == 0:
            decrypted = AES.new(self.key, AES.MODE_CBC, self.iv).decrypt(encrypted)
        else:
            if len(encrypted) < 32: return b''
            decrypted = AES.new(self.key, AES.MODE_CBC, encrypted[:16]).decrypt(encrypted[16:])
        offset = b64_start - cipher_start
        encoded = decrypted[offset:offset + b64_end - b64_start + 1]
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except Exception:
            return b''
        crop = start - group_start * 3
        return decoded[crop:crop + end - start + 1]

    def _mp3_stream_info(self, data):
        offset = 0
        if data.startswith(b'ID3') and len(data) >= 10:
            size = ((data[6] & 127) << 21) | ((data[7] & 127) << 14) | ((data[8] & 127) << 7) | (data[9] & 127)
            offset = min(len(data), 10 + size)
        bitrate_tables = {
            (3, 1): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
            (2, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
            (0, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}
        sample_tables = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}
        for pos in range(offset, max(offset, len(data) - 4)):
            h = int.from_bytes(data[pos:pos + 4], 'big')
            if (h & 0xFFE00000) != 0xFFE00000: continue
            version = (h >> 19) & 3
            layer_bits = (h >> 17) & 3
            bitrate_index = (h >> 12) & 15
            sample_index = (h >> 10) & 3
            padding = (h >> 9) & 1
            if version == 1 or layer_bits != 1 or bitrate_index in (0, 15) or sample_index == 3: continue
            rates = bitrate_tables.get((version, layer_bits))
            samples = sample_tables.get(version)
            if not rates or not samples: continue
            bitrate, sample_rate = rates[bitrate_index] * 1000, samples[sample_index]
            frame_samples = 1152 if version == 3 else 576
            frame_length = ((144 if version == 3 else 72) * bitrate // sample_rate) + padding
            if frame_length < 24: continue
            return {'offset': pos, 'bitrate': bitrate, 'sample_rate': sample_rate,
                    'frame_samples': frame_samples, 'frame_length': frame_length}
        return {}

    def _audio_hls_playlist(self, target):
        meta = self._audio_remote_meta(target)
        first = meta.get('first_chunk') or b''
        info = self._mp3_stream_info(first)
        total = int(meta.get('mp3_total') or 0)
        if not info or total <= info.get('offset', 0): return b''
        frame_length = int(info['frame_length'])
        frame_duration = float(info['frame_samples']) / float(info['sample_rate'])
        audio_start = int(info.get('offset') or 0)
        total = audio_start + ((total - audio_start) // frame_length) * frame_length
        if total <= audio_start: return b''
        cached_audio_bytes = max(0, len(first) - audio_start)
        first_frames = max(1, cached_audio_bytes // frame_length)
        segment_frames = max(first_frames, self.audio_segment_size // frame_length)
        first_bytes = first_frames * frame_length
        segment_bytes = segment_frames * frame_length
        target_duration = segment_frames * frame_duration
        starts = []
        first_end = min(total - 1, info['offset'] + first_bytes - 1)
        starts.append((0, first_end, (first_end - info['offset'] + 1) / frame_length * frame_duration))
        start = first_end + 1
        while start < total:
            end = min(total - 1, start + segment_bytes - 1)
            duration = (end - start + 1) / frame_length * frame_duration
            starts.append((start, end, duration))
            start = end + 1
        base = self.getProxyUrl()
        lines = ['#EXTM3U', '#EXT-X-VERSION:3', '#EXT-X-PLAYLIST-TYPE:VOD',
                 '#EXT-X-TARGETDURATION:%s' % max(1, int(target_duration + 0.999)), '#EXT-X-MEDIA-SEQUENCE:0']
        encoded = quote(target, safe='')
        for start, end, duration in starts:
            lines.append('#EXTINF:%.3f,' % max(frame_duration, duration))
            lines.append(base + '&audio_seg=' + encoded + '&start=%s&end=%s' % (start, end))
        lines.append('#EXT-X-ENDLIST')
        return ('\n'.join(lines) + '\n').encode('utf-8')

    def localProxy(self, param):
        audio = unquote(str((param or {}).get('audio') or ''))
        audio_hls = unquote(str((param or {}).get('audio_hls') or ''))
        audio_seg = unquote(str((param or {}).get('audio_seg') or ''))
        target = audio or audio_hls or audio_seg or unquote(str((param or {}).get('url') or ''))
        if not target.startswith(('http://', 'https://')): return [404, 'text/plain', b'', {}]
        try:
            if audio_hls:
                playlist = self._audio_hls_playlist(target)
                return [200, 'application/vnd.apple.mpegurl', playlist, {'Cache-Control': 'no-cache'}] if playlist else [404, 'text/plain', b'', {}]
            if audio_seg:
                try:
                    start = max(0, int((param or {}).get('start') or 0))
                    end = max(start, int((param or {}).get('end') or start))
                except Exception: return [400, 'text/plain', b'', {}]
                meta = self._audio_remote_meta(target)
                body = self._read_audio_segment(target, start, end)
                if not body:
                    body = (meta.get('first_chunk') or b'')[start:end + 1] if start == 0 else b''
                if len(body) != end - start + 1:
                    body = self._audio_remote_chunk(target, start, end, meta)
                    self._save_audio_segment(target, start, end, body)
                return [200, 'audio/mpeg', body, {'Content-Length': str(len(body)), 'Cache-Control': 'public, max-age=86400'}] if body else [503, 'text/plain', b'', {'Retry-After': '1'}]
            if audio:
                key = hashlib.md5(target.encode()).hexdigest()
                cache = os.path.join(self.audio_cache_dir, key + '.mp3')
                try: cached_total = os.path.getsize(cache)
                except Exception: cached_total = 0
                range_header = (param or {}).get('range') or (param or {}).get('Range') or ''

                if cached_total > 1024:
                    total = cached_total
                    start, end = self._audio_range_bounds(range_header, total)
                    if start < 0 or start >= total or end < start:
                        return [416, 'text/plain', b'', {'Content-Range': 'bytes */%s' % total}]
                    with open(cache, 'rb') as f:
                        f.seek(start); body = f.read(end - start + 1)
                else:
                    meta = self._audio_remote_meta(target)
                    total = int(meta.get('mp3_total') or 0)
                    if total:
                        start, end = self._audio_range_bounds(range_header, total)
                        if start < total and end >= start:
                            if start == 0 and end < len(meta.get('first_chunk') or b''):
                                body = meta['first_chunk'][:end + 1]
                            else:
                                body = self._audio_remote_chunk(target, start, end, meta)
                        else: body = b''
                    else: body = b''
                    if not body:
                        cache = self._audio_file(target)
                        if not cache: return [404, 'text/plain', b'', {}]
                        total = os.path.getsize(cache)
                        start, end = self._audio_range_bounds(range_header, total)
                        if start < 0 or start >= total or end < start:
                            return [416, 'text/plain', b'', {'Content-Range': 'bytes */%s' % total}]
                        with open(cache, 'rb') as f:
                            f.seek(start); body = f.read(end - start + 1)

                headers = {'Accept-Ranges': 'bytes', 'Cache-Control': 'public, max-age=86400',
                           'Content-Length': str(len(body)), 'Content-Range': 'bytes %s-%s/%s' % (start, end, total)}
                return [206, 'audio/mpeg', body, headers]

            raw = self._content(self.fetch(target, headers={'User-Agent': self.ua}, timeout=18, verify=False))
            mime = self._image_mime(raw)
            if not mime:
                candidates = [raw]
                try:
                    decoded = base64.b64decode(raw, validate=True)
                    if decoded: candidates.insert(0, decoded)
                except Exception: pass
                plain = b''
                for encrypted in candidates:
                    if len(encrypted) % 16: continue
                    try:
                        value = unpad(AES.new(self.key, AES.MODE_CBC, self.iv).decrypt(encrypted), 16)
                        mime = self._image_mime(value)
                        if not mime:
                            value = base64.b64decode(value, validate=True)
                            mime = self._image_mime(value)
                        if mime:
                            plain = value
                            break
                    except Exception: continue
                raw = plain
            if mime == 'image/webp': raw = self._webp_first_frame(raw)
            return [200, mime, raw, {'Cache-Control': 'public, max-age=86400'}] if mime else [404, 'text/plain', b'', {}]
        except Exception as exc:
            self.log('图片解密失败: %s' % exc)
            return [404, 'text/plain', b'', {}]