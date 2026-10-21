# -*- coding: utf-8 -*-
"""某音短剧 TVBox 接口（终结者）"""

import base64
import json
import random
import sys
import threading
import time
from collections import OrderedDict
from urllib.parse import urlencode

import requests

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    BaseSpider = object


# 固定 UA，避免随机切换触发风控
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/130.0.0.0 Safari/537.36')


class Config:
    CACHE_TTL_SHORT = 300
    CACHE_TTL_LONG = 900
    CACHE_TTL_PLAY = 600           # 缩短，直链带 expire
    CACHE_MAX_SIZE = 1000
    RETRY_TIMES = 2
    RETRY_DELAY = 1.5
    TIMEOUT_CONNECT = 5
    TIMEOUT_READ = 15
    EPISODE_PAGE_SIZE = 100
    EPISODE_MAX_PAGES = 10


def _log(msg):
    """print 在电视盒子/TVBox 上比 logging 更可靠"""
    try:
        print('[某音短剧] %s' % msg)
    except Exception:
        pass


class Spider(BaseSpider):
    HOST = 'https://www.douyin.com'
    API = HOST + '/aweme/v1/web'
    COMMON = {'device_platform': 'webapp', 'aid': '6383',
              'channel': 'channel_pc_web'}
    # 分类表。已剔除两类：
    #  · 热榜(hot) —— 接口不支持翻页，第 2/3 页与第 1 页完全相同，且固定只有 7 条
    #  · 榜单(1)   —— 去掉 content_type 参数后的默认流，和"推荐"返回同一批数据
    CATEGORIES = (
        ('推荐', 'recommend'),
        ('爱情', '1940'), ('剧情', '1957'), ('逆袭', '1944'),
        ('反转', '2092'), ('亲情', '1941'), ('恩怨', '2091'),
        ('玄幻', '1946'), ('奇幻', '1945'), ('古装', '1958'),
        ('悬疑', '1950'), ('友情', '1942'), ('喜剧', '1956'),
        ('犯罪', '2088'), ('惊悚', '1951'), ('青春', '1943'),
        ('科幻', '1947'), ('仙侠', '1948'), ('其他', '1959'),
    )

    def __init__(self):
        try:
            super(Spider, self).__init__()
        except Exception:
            pass
        self.session = None
        self.cache = OrderedDict()
        self.webid = self._generate_webid()
        self.protected_ready = False
        self._ttwid_lock = threading.Lock()
        self._cache_lock = threading.Lock()

    # ==================== 生命周期 ====================

    def init(self, extend=''):
        self.session = requests.Session()
        # 关键：不设置 Accept-Encoding: br，盒子环境多数没有 brotli 库
        self.session.headers.update({
            'User-Agent': UA,
            'Referer': self.HOST + '/series',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
        ext = self._parse_ext(extend)
        if ext.get('cookie'):
            self.session.headers['Cookie'] = str(ext['cookie'])
            _log('使用自定义 Cookie')
        # ttwid 惰性注册，避免 init 阻塞
        _log('初始化完成')

    def getName(self):
        return '某音短剧'

    def destroy(self):
        try:
            if self.session:
                self.session.close()
        except Exception:
            pass
        self.cache.clear()

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    # ==================== TVBox 接口 ====================

    def homeContent(self, filter):
        return {
            'class': [{'type_name': n, 'type_id': t}
                      for n, t in self.CATEGORIES],
            'filters': {},
        }

    def homeVideoContent(self):
        return {'list': self._category('recommend', 1).get('list', [])}

    def categoryContent(self, tid, pg, filter, extend):
        return self._category(str(tid), self._int(pg, 1))

    def searchContent(self, key, quick, pg='1', sort_type=0, publish_time=0):
        page = self._int(pg, 1)
        if page > 1:
            # 搜索接口只认第 1 页（offset 会被风控），翻页直接回空，别浪费请求
            return {'list': [], 'page': page, 'pagecount': page,
                    'limit': 20, 'total': 0}
        params = {
            'keyword': key,
            'count': 20,
            'offset': (page - 1) * 20,
            'search_channel': 'aweme_series',
            'sort_type': sort_type,
            'publish_time': publish_time,
            'search_source': 'normal_search',
        }
        data = self._get('/search/item/', params, signed=True)
        err = data.get('error') or ''
        if err:
            _log('搜索不可用: %s' % err)
            return {'list': [], 'page': page, 'pagecount': page,
                    'limit': 20, 'total': 0}
        raw = data.get('data') or []
        if not isinstance(raw, list):
            raw = []
        videos = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            series = item.get('series_info') or item.get('aweme_info') or {}
            if series:
                videos.append(self._video(series))
        videos = [x for x in videos if x.get('vod_id')]
        return {
            'list': videos,
            'page': page,
            'pagecount': page + 1 if videos else page,
            'limit': 20,
            'total': page * 20 + (20 if videos else 0),
        }

    def detailContent(self, ids):
        series_id = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        detail = self._get('/series/detail/', {
            'series_id': series_id, 'req_from': 'channel_pc_web'
        })
        info = detail.get('series_info') or {}
        episodes = self._episodes(series_id, info)
        if not info and not episodes:
            _log('未获取到剧集信息: %s' % series_id)
            return {'list': []}

        cover = self._image(info.get('cover_url'))
        name = info.get('series_name') or series_id
        actor_names = [x.get('name', '') for x in (info.get('actors') or [])
                       if isinstance(x, dict)]

        play_items = []
        for index, item in enumerate(episodes, 1):
            ep = self._episode_number(item, index)
            payload = self._play_payload(item)
            if payload:
                play_items.append('%s$%s' % (ep, payload))
            else:
                # 无地址也占位，避免集数错乱
                play_items.append('%s$%s' % (ep, ''))

        _log('详情 %s: 共 %s 集，其中 %s 集有地址'
             % (series_id, len(episodes), len(play_items)))

        vod = {
            'vod_id': series_id,
            'vod_name': name,
            'vod_pic': cover,
            'type_name': self._type_names(info),
            'vod_remarks': self._status_text(info),
            'vod_year': '',
            'vod_area': '中国大陆',
            'vod_actor': ','.join(actor_names),
            'vod_director': '',
            'vod_content': info.get('desc') or '',
            'vod_play_from': '某音短剧',
            'vod_play_url': '#'.join(play_items),
        }
        if not play_items:
            vod['vod_remarks'] = '暂未取得分集播放地址'
            _log('剧集无播放地址: %s' % series_id)
        return {'list': [vod]}

    def playerContent(self, flag, pid, vipFlags):
        urls, uris = [], []
        try:
            raw = base64.urlsafe_b64decode(
                str(pid) + '=' * (-len(str(pid)) % 4))
            data = json.loads(raw.decode('utf-8'))
            urls = data.get('urls') or []
            uris = data.get('uris') or []
        except Exception:
            if str(pid).startswith('http'):
                urls = [str(pid)]

        # 取第一个 http 直链
        url = next((x for x in urls if str(x).startswith('http')), '')

        # 没直链，用 uri 走官方播放接口兜底
        if not url and uris:
            uri = str(uris[0])
            url = ('https://aweme.snssdk.com/aweme/v1/play/'
                   '?video_id=%s&ratio=1080p&line=0' % uri)
            _log('直链缺失，走 uri 兜底: %s' % uri)

        if not url:
            url = str(pid)

        # header 必须是 JSON 字符串。给 dict 时壳解析失败拿不到 Referer/UA，
        # CDN 直接拒流，表现就是"点了没反应/黑屏"——这是本文件最大的坑。
        header = json.dumps({'User-Agent': UA, 'Referer': self.HOST + '/'},
                            ensure_ascii=False)
        return {
            'parse': 0,
            'url': url,
            'playUrl': url,      # 有些壳只读 playUrl，两个都给
            'header': header,
            'jx': 0,
        }

    def localProxy(self, param):
        return [404, 'text/plain', 'not found']

    # ==================== 内部：分类 ====================

    def _category(self, tid, page):
        count = 16
        data = {}

        if tid == 'hot':
            data = self._get('/series/hot/list/', {'count': 100}, signed=True)
            raw_list = (data.get('series_infos')
                        or data.get('series_list')
                        or data.get('aweme_list')
                        or [])
            if not isinstance(raw_list, list):
                raw_list = []
            has_more = False
        else:
            params = {'offset': (page - 1) * count, 'count': count}
            if tid not in ('recommend', ''):
                params['content_type'] = self._int(tid, 0)

            data = self._get('/series/card/feed/', params, signed=True)

            cards = (data.get('card_list')
                     or data.get('cards')
                     or data.get('aweme_list')
                     or [])
            if not isinstance(cards, list):
                cards = []

            raw_list = []
            for x in cards:
                if not isinstance(x, dict):
                    continue
                series = x.get('series') or x.get('series_info') or x
                if isinstance(series, dict) and series.get('series_id'):
                    raw_list.append(series)

            has_more = bool(data.get('has_more') or data.get('hasMore'))

        videos = [self._video(x) for x in raw_list if isinstance(x, dict)]
        videos = [x for x in videos if x.get('vod_id')]

        err = data.get('error')
        _log('分类 %s 第%s页 返回 %s 条%s'
             % (tid, page, len(videos), (' 错误=%s' % err) if err else ''))

        return {
            'list': videos,
            'page': page,
            'pagecount': page + 1 if has_more else page,
            'limit': count,
            'total': page * count + (count if has_more else 0),
        }

    # ==================== 内部：剧集 ====================

    def _episodes(self, series_id, info):
        total = self._int((info.get('stats') or {}).get('total_episode'), 0)
        cache_ttl = Config.CACHE_TTL_SHORT if total < 50 else Config.CACHE_TTL_LONG

        cache_key = 'ep:%s' % series_id
        cached = self._cache_get(cache_key, cache_ttl)
        if cached is not None:
            return cached

        result, cursor = [], 0
        for _ in range(Config.EPISODE_MAX_PAGES):
            data = self._get('/series/aweme/', {
                'series_id': series_id, 'pull_type': 2,
                'cursor': cursor, 'count': Config.EPISODE_PAGE_SIZE,
            }, signed=True)

            chunk = data.get('aweme_list') or []
            if not isinstance(chunk, list) or not chunk:
                break

            result.extend(chunk)
            next_cursor = self._int(data.get('max_cursor'), cursor + len(chunk))
            if not data.get('has_more') or next_cursor <= cursor:
                break
            cursor = next_cursor
            if total and len(result) >= total:
                break

        self._cache_set(cache_key, result)
        _log('剧集 %s 共 %s 集' % (series_id, len(result)))
        return result

    # ==================== 网络 ====================

    def _get(self, path, params, signed=False, retry=None):
        if retry is None:
            retry = Config.RETRY_TIMES

        if self.session is None:
            self.init()

        query_params = dict(self.COMMON)
        query_params.update(params or {})

        if signed:
            self._ensure_protected_session()
            query_params.update({
                'cookie_enabled': 'true',
                'screen_width': 1920, 'screen_height': 1080,
                'browser_language': 'zh-CN',
                'browser_platform': 'Win32',
                'browser_name': 'Chrome', 'browser_version': '130.0.0.0',
                'browser_online': 'true',
                'engine_name': 'Blink', 'engine_version': '130.0.0.0',
                'os_name': 'Windows', 'os_version': '10',
                'cpu_core_num': 8, 'device_memory': 8,
                'platform': 'PC', 'downlink': 10,
                'effective_type': '4g', 'round_trip_time': 50,
                'version_code': '170400', 'version_name': '17.4.0',
                'webid': self.webid, 'update_version_code': '170400',
                'pc_client_type': 1, 'pc_libra_divert': 'Windows',
                'support_h265': 0, 'support_dash': 0,
            })

        url = self.API + path + '?' + urlencode(query_params)
        last_error = None

        for attempt in range(retry + 1):
            try:
                response = self.session.get(
                    url,
                    timeout=(Config.TIMEOUT_CONNECT, Config.TIMEOUT_READ),
                )
                if response.status_code == 200:
                    if response.text.strip() == 'blocked':
                        last_error = '风控拦截'
                        _log('接口被风控: %s (尝试 %s/%s)'
                             % (path, attempt + 1, retry + 1))
                        time.sleep(Config.RETRY_DELAY * (attempt + 1))
                        continue
                    try:
                        payload = response.json()
                        # 抖音用 status_code 表达业务错误：2483=请先登录、8=风控
                        # 这些 HTTP 也是 200，只判状态码会当成"成功但没有数据"
                        code = payload.get('status_code')
                        if code not in (None, 0):
                            last_error = '业务错误 %s: %s' % (
                                code, payload.get('status_msg') or '')
                            _log('接口返回错误: %s (%s)'
                                 % (path, payload.get('status_msg') or code))
                            return {'error': last_error}
                        return payload
                    except Exception as e:
                        last_error = 'JSON解析失败: %s' % e
                        _log(last_error)
                else:
                    last_error = 'HTTP %s' % response.status_code
                    _log('HTTP 错误: %s 状态码 %s' % (path, response.status_code))
            except requests.exceptions.Timeout:
                last_error = '请求超时'
                _log('请求超时: %s' % path)
            except requests.exceptions.ConnectionError:
                last_error = '连接失败'
                _log('连接失败: %s' % path)
            except Exception as e:
                last_error = str(e)
                _log('请求异常: %s -> %s' % (path, e))

            if attempt < retry:
                time.sleep(Config.RETRY_DELAY)

        _log('请求最终失败: %s 错误=%s' % (path, last_error))
        return {'error': last_error}

    def _ensure_protected_session(self):
        if self.protected_ready:
            return
        with self._ttwid_lock:
            if self.protected_ready:
                return
            body = {
                'region': 'cn', 'aid': 6383, 'needFid': False,
                'service': 'www.douyin.com',
                'migrate_info': {'ticket': '', 'source': 'node'},
                'cbUrlProtocol': 'https', 'union': True,
            }
            try:
                response = self.session.post(
                    'https://ttwid.bytedance.com/ttwid/union/register/',
                    json=body,
                    timeout=(Config.TIMEOUT_CONNECT, Config.TIMEOUT_READ),
                )
                callback = (response.json() or {}).get('redirect_url')
                if callback:
                    self.session.get(
                        callback,
                        timeout=(Config.TIMEOUT_CONNECT, Config.TIMEOUT_READ),
                    )
                webid_cookie = self.session.cookies.get('webid')
                if webid_cookie:
                    self.webid = webid_cookie
                # 注册接口会在不同 domain（.bytedance.com / .douyin.com）各下发一个
                # ttwid，jar 里出现重名时 cookies.get() 直接抛 CookieConflictError。
                # 这里逐个域取，只要任意一个存在就算注册成功。
                self.protected_ready = self._has_ttwid()
                _log('ttwid 注册%s'
                     % ('成功' if self.protected_ready else '失败'))
            except Exception as e:
                # 注册失败不致命：接口本身不强制，后面照常请求
                _log('ttwid 注册异常: %s' % e)
                self.protected_ready = self._has_ttwid()

    def _has_ttwid(self):
        try:
            for c in self.session.cookies:
                if c.name == 'ttwid' and c.value:
                    return True
        except Exception:
            pass
        return False

    # ==================== 缓存 ====================

    def _cache_get(self, key, ttl):
        with self._cache_lock:
            item = self.cache.get(key)
            if item:
                ts, value = item
                if time.time() - ts < ttl:
                    self.cache.move_to_end(key)
                    return value
                del self.cache[key]
        return None

    def _cache_set(self, key, value):
        with self._cache_lock:
            if len(self.cache) >= Config.CACHE_MAX_SIZE:
                self.cache.popitem(last=False)
            self.cache[key] = (time.time(), value)

    # ==================== 工具 ====================

    @staticmethod
    def _generate_webid():
        return str(random.SystemRandom().randint(
            7000000000000000000, 7999999999999999999))

    def _video(self, info):
        sid = str(info.get('series_id') or '')
        return {
            'vod_id': sid,
            'vod_name': info.get('series_name') or sid,
            'vod_pic': self._image(info.get('cover_url')),
            'vod_remarks': self._status_text(info),
        }

    def _play_payload(self, item):
        """生成播放 payload：H.264 优先，附 uri 兜底"""
        video = item.get('video') or {}
        h264_urls, h265_urls, uris = [], [], []

        def collect(addr, is_265=False):
            if not isinstance(addr, dict):
                urls = self._urls(addr)
                (h265_urls if is_265 else h264_urls).extend(urls)
                return
            uri = addr.get('uri')
            if uri:
                uris.append(str(uri))
            urls = self._urls(addr)
            (h265_urls if is_265 else h264_urls).extend(urls)

        # bit_rate 里按码率降序
        bit_rates = video.get('bit_rate') or []
        if isinstance(bit_rates, list):
            bit_rates = sorted(
                bit_rates,
                key=lambda x: self._int((x or {}).get('bit_rate'), 0),
                reverse=True,
            )
            for rate in bit_rates:
                if not isinstance(rate, dict):
                    continue
                gear = str(rate.get('gear_name') or '').lower()
                is_265 = ('265' in gear or 'h265' in gear or 'hevc' in gear)
                collect(rate.get('play_addr'), is_265)

        # 主 play_addr 一般是 H.264
        collect(video.get('play_addr'), False)
        collect(video.get('play_addr_h264'), False)
        # 265 放最后
        collect(video.get('play_addr_265'), True)

        h264_unique = list(dict.fromkeys(x for x in h264_urls if x))
        h265_unique = list(dict.fromkeys(x for x in h265_urls if x))
        uri_unique = list(dict.fromkeys(x for x in uris if x))

        # aweme_id 作为最终兜底（付费集常用）
        aweme_id = item.get('aweme_id')
        if aweme_id:
            uri_unique.append(str(aweme_id))

        if not h264_unique and not h265_unique and not uri_unique:
            _log('第%s集无可用地址 aweme_id=%s'
                 % (item.get('episode') or '?', aweme_id or '?'))
            return ''

        payload = {
            'urls': h264_unique + h265_unique,
            'uris': uri_unique,
        }
        raw = json.dumps(payload, ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
        return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')

    @staticmethod
    def _urls(value):
        if isinstance(value, dict):
            value = value.get('url_list') or value.get('urlList') or []
        if isinstance(value, str):
            return [value]
        return [str(x) for x in (value or []) if x]

    @classmethod
    def _image(cls, value):
        urls = cls._urls(value)
        return urls[0] if urls else ''

    @staticmethod
    def _episode_number(item, fallback):
        info = item.get('series_info') or {}
        stats = info.get('stats') or {}
        number = (stats.get('current_episode')
                  or info.get('current_episode')
                  or item.get('episode')
                  or fallback)
        return '第%s集' % number

    @staticmethod
    def _type_names(info):
        values = (info.get('series_content_types_new')
                  or info.get('series_content_types') or [])
        return '/'.join(str(x.get('name')) for x in values
                        if isinstance(x, dict) and x.get('name'))

    @staticmethod
    def _status_text(info):
        status = info.get('status') or {}
        if isinstance(status, dict) and status.get('status_desc'):
            return status['status_desc']
        stats = info.get('stats') or {}
        total = stats.get('total_episode') or info.get('total_episode')
        return ('%s集全' % total) if total else ''

    @staticmethod
    def _int(value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _parse_ext(extend):
        if isinstance(extend, dict):
            return extend
        getter = getattr(extend, 'get', None)
        if callable(getter):
            try:
                cookie = getter('cookie')
                return {'cookie': str(cookie)} if cookie else {}
            except Exception:
                pass
        try:
            text = str(extend or '').strip()
            value = json.loads(text) if text.startswith('{') else {}
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}
