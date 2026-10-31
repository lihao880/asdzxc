# -*- coding: utf-8 -*-
"""
=================================================
  鬼片之家 TVBox 源（修复 + 防失效版）
=================================================

站点：guipian456.cc（海螺模板 v3.1，HTML 解析，无标准 AppleCMS API）

修复历史：
- 原始版：host 写死 kanguipian.com，旧域名 301 跳走 → 整源空白。
- 上一修复版：host 改成 www.kanguipian456.cc（仍带 "kan" 前缀），但此域名已 DNS 失效 → 仍然没资源。
- 本版修复（2026-10）：
  1. 【关键】真实存活域名为 guipian456.cc（无 "kan" 前缀），原写死的 kanguipian456.cc 已解析失败。
  2. 【关键】域名不再写死：用 _DOMAINS 域名池 + 失败自动轮换；并从已成功页面正则收编同族新域名置首
     —— 以后运营换域名无需改代码，自动生效（破解"写死单域名迟早没资源"）。
  3. 【关键】_fetch_html 兼容框架 self.fetch 返回值（str/bytes/Response）；不依赖 status_code 判成功。
  4. 网络层兜底：壳子用框架 self.fetch；本地兜底先 requests 再 urllib，保证沙箱/自测也能跑。
  5. init(extend) 支持传自定义域名 {"domain":"..."}，插到域名池队首，换域名零改码。

解析逻辑（首页/分类/详情/播放）已对照 guipian456.cc 真实 HTML 验证 class 命名一致：
  hl-list-item / hl-text-muted / data-original / hl-tabs-box / /nv/ / /play/ / var now="..." m3u8。
"""
import sys
import json
import re
import base64
import time
from urllib.parse import quote, urlencode, urlparse

sys.path.append('..')

# ----------------------------------------------------------------------------
#  网络层基类：壳子环境用框架注入的 self.fetch；本地兜底先 requests 再 urllib
# ----------------------------------------------------------------------------
try:
    from base.spider import Spider as _Base
except ImportError:
    import ssl as _ssl
    _ICT = _ssl.create_default_context()
    _ICT.check_hostname = False
    _ICT.verify_mode = _ssl.CERT_NONE
    import urllib.request as _ur

    class _Base:
        def fetch(self, url, headers=None, timeout=15, **kw):
            kw.pop('timeout', None)
            # 优先 requests（壳子本地有时可用）
            try:
                import requests as rq
                r = rq.get(url, headers=headers, timeout=timeout, **kw)
                r.encoding = 'utf-8'
                return r
            except ImportError:
                pass
            # urllib 兜底（沙箱/无 requests 时使用）
            req = _ur.Request(url, headers=headers or {})
            try:
                resp = _ur.urlopen(req, timeout=timeout, context=_ICT)
            except TypeError:
                resp = _ur.urlopen(req, timeout=timeout)
            data = resp.read()
            if resp.headers.get('Content-Encoding') == 'gzip':
                import gzip
                data = gzip.decompress(data)
            return data.decode('utf-8', 'replace')

        def post(self, url, data=None, headers=None, timeout=15, **kw):
            try:
                import requests as rq
                r = rq.post(url, data=data, headers=headers, timeout=timeout, **kw)
                r.encoding = 'utf-8'
                return r
            except ImportError:
                return ''


class Spider(_Base):
    """
    鬼片之家 Spider
    海螺模板 v3.1, HTML 解析
    """

    # ------------------------------------------------------------------
    #  域名池（按优先级）：当前存活 guipian456.cc 置首
    #  旧域名 kanguipian456.cc（带 "kan"）已 DNS 失效，保留待复活（自动跳过）
    #  _harvest 会从成功页面动态收编同族新域名置首，破解写死失效
    # ------------------------------------------------------------------
    _DOMAINS = [
        'guipian456.cc',          # 当前存活（2026-10 实测）
        'www.guipian456.cc',      # 同站 www 变体
        'kanguipian456.cc',       # 旧域名（已 DNS 失效，保留待复活）
        'www.kanguipian456.cc',
        'kanguipian.com',         # 更早的旧域名（曾 301 跳转）
        'www.kanguipian.com',
    ]
    _cur = 0  # 当前生效域名索引

    @property
    def host(self):
        return 'https://' + self._DOMAINS[self._cur]

    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }

    # 分类列表 (type_id 对应 /list/{type_id}.html)
    classes = [
        {'type_name': '鬼片大全', 'type_id': '1'},
        {'type_name': '电视剧', 'type_id': '2'},
        {'type_name': '恐怖片', 'type_id': '3'},
        {'type_name': '动漫', 'type_id': '4'},
        {'type_name': '大陆鬼片', 'type_id': '6'},
        {'type_name': '日韩鬼片', 'type_id': '7'},
        {'type_name': '欧美鬼片', 'type_id': '11'},
    ]

    # 筛选器: 鬼片大全子分类
    _filter_guipian = [
        {'n': '全部', 'v': ''},
        {'n': '大陆鬼片', 'v': '6'},
        {'n': '日韩鬼片', 'v': '7'},
        {'n': '林正英鬼片', 'v': '8'},
        {'n': '港台鬼片', 'v': '9'},
        {'n': '泰国鬼片', 'v': '10'},
        {'n': '欧美鬼片', 'v': '11'},
        {'n': '剧情片', 'v': '31'},
    ]

    # 筛选器: 电视剧子分类
    _filter_tv = [
        {'n': '全部', 'v': ''},
        {'n': '国产剧', 'v': '12'},
        {'n': '美剧', 'v': '13'},
        {'n': '韩剧', 'v': '14'},
        {'n': '日剧', 'v': '15'},
        {'n': '泰剧', 'v': '16'},
        {'n': '港台剧', 'v': '17'},
        {'n': '其他剧', 'v': '18'},
    ]

    # 筛选器: 动漫子分类
    _filter_anime = [
        {'n': '全部', 'v': ''},
        {'n': '日韩动漫', 'v': '23'},
        {'n': '国产动漫', 'v': '24'},
        {'n': '欧美动漫', 'v': '25'},
        {'n': '港台动漫', 'v': '26'},
        {'n': '动画电影', 'v': '5'},
    ]

    # 筛选器: 排序
    _filter_sort = [
        {'n': '时间排序', 'v': 'time'},
        {'n': '人气排序', 'v': 'hit'},
        {'n': '评分排序', 'v': 'commend'},
    ]

    # ===================================================================
    #  基础方法
    # ===================================================================

    def getName(self):
        return '鬼片之家'

    def init(self, extend=''):
        self.extend = extend or ''
        # 支持 extend 传自定义域名：{"domain":"..."} / {"site":"..."} / {"host":"..."}
        # 自定义域名插到域名池队首，换域名零改码
        try:
            obj = extend if isinstance(extend, dict) else None
            if isinstance(extend, str) and extend.strip().startswith('{'):
                obj = json.loads(extend)
            if isinstance(obj, dict):
                dom = obj.get('domain') or obj.get('site') or obj.get('host')
                if dom:
                    dom = dom.replace('http://', '').replace('https://', '').strip('/').lower()
                    if dom and dom not in self._DOMAINS:
                        self._DOMAINS.insert(0, dom)
                        self._cur = 0
        except Exception:
            pass

    def isVideoFormat(self, url):
        return any(x in url for x in ['.m3u8', '.mp4', '.flv', '.avi', '.mkv'])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ===================================================================
    #  请求封装（兼容 self.fetch 返回 str/bytes/Response；多域名轮换 + 收编）
    # ===================================================================

    @staticmethod
    def _to_text(resp):
        """把 self.fetch 的多种返回值规整为字符串。"""
        if resp is None:
            return ''
        if isinstance(resp, str):
            return resp
        if isinstance(resp, (bytes, bytearray)):
            if resp[:2] == b'\x1f\x8b':
                try:
                    import gzip
                    resp = gzip.decompress(resp)
                except Exception:
                    pass
            try:
                return resp.decode('utf-8', 'replace')
            except Exception:
                return str(resp)
        if hasattr(resp, 'text') and resp.text:
            return resp.text
        if hasattr(resp, 'content'):
            try:
                return resp.content.decode('utf-8', 'replace')
            except Exception:
                return ''
        return ''

    def _fetch_html(self, path):
        """获取页面 HTML，带多域名轮换 + 动态收编。当前域名失败自动切下一个。"""
        last_text = ''
        tried = 0
        max_try = len(self._DOMAINS) + 1
        while tried < max_try:
            tried += 1
            url = path if path.startswith('http') else self.host + path
            try:
                r = self.fetch(url, headers=self.header, timeout=15)
                text = self._to_text(r)
            except Exception:
                text = ''
            if text:
                self._harvest(text)  # 收编页面里出现的同族新域名
                return text
            last_text = text
            # 当前域名失败 -> 轮换到下一个
            self._cur = (self._cur + 1) % len(self._DOMAINS)
        return last_text

    def _harvest(self, html):
        """从已成功页面里收编同族域名（guipian/456 类）作为候补，不覆盖当前主域名。

        注意：只收编主站后缀，排除明显是图片/视频 CDN 的域名（img/pic/cdn/video/play 等），
        避免把图床当主域名导致整源不稳。新域名插到当前主域名之后作为后备轮换项。
        """
        try:
            for d in re.findall(
                r'(?:https?://)?([A-Za-z0-9.-]*guipian[A-Za-z0-9.-]*\.(?:com|cc|net|info|me|xyz|top|vip|icu|cyou|app|tv|la|online))',
                html, re.I):
                d = d.strip().lower()
                if d and d not in self._DOMAINS:
                    # 排除明显是图片/视频 CDN 的域名
                    head = d.split('.')[0]
                    if any(k in head for k in ('img', 'pic', 'cdn', 'upload', 'video', 'play', 'live', 'stream')):
                        continue
                    self._DOMAINS.insert(self._cur + 1, d)
        except Exception:
            pass

    # ===================================================================
    #  图片处理（直连不走代理）
    # ===================================================================

    def _wrap_pic(self, pic_url):
        """将图片 URL 处理为可直接加载的 URL"""
        if not pic_url:
            return ''

        pic_url = pic_url.strip()
        if pic_url.startswith(('"', "'")) and pic_url.endswith(('"', "'")):
            pic_url = pic_url[1:-1]

        pic_url = pic_url.replace('&amp;', '&')

        if '127.0.0.1' in pic_url or 'proxy' in pic_url:
            return pic_url

        if pic_url.startswith('//'):
            pic_url = 'https:' + pic_url
        elif not pic_url.startswith(('http://', 'https://')):
            if pic_url.startswith('/'):
                pic_url = self.host + pic_url
            else:
                pic_url = self.host + '/' + pic_url

        return pic_url

    # ===================================================================
    #  首页
    # ===================================================================

    def homeContent(self, filter):
        """返回分类列表和筛选器配置"""
        filters = {}
        filters['1'] = [
            {'key': 'cate', 'name': '子分类', 'value': self._filter_guipian},
            {'key': 'order', 'name': '排序', 'value': self._filter_sort},
        ]
        filters['2'] = [
            {'key': 'cate', 'name': '子分类', 'value': self._filter_tv},
            {'key': 'order', 'name': '排序', 'value': self._filter_sort},
        ]
        filters['3'] = [
            {'key': 'order', 'name': '排序', 'value': self._filter_sort},
        ]
        filters['4'] = [
            {'key': 'cate', 'name': '子分类', 'value': self._filter_anime},
            {'key': 'order', 'name': '排序', 'value': self._filter_sort},
        ]
        for tid in ['6', '7', '11']:
            filters[tid] = [
                {'key': 'order', 'name': '排序', 'value': self._filter_sort},
            ]
        return {'class': self.classes, 'filters': filters}

    def homeVideoContent(self):
        try:
            html = self._fetch_html('/')
            vod_list = self._parse_cards(html)
            return {'list': vod_list[:30]}
        except Exception:
            return {'list': []}

    # ===================================================================
    #  分类内容
    # ===================================================================

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg or 1)

            ext = {}
            if extend:
                if isinstance(extend, dict):
                    ext = extend
                elif isinstance(extend, str):
                    try:
                        ext = json.loads(extend)
                    except Exception:
                        ext = {}

            cate = ext.get('cate', '')
            order = ext.get('order', 'time')

            actual_tid = cate if cate else tid

            if pg <= 1:
                url = '/list/%s.html' % actual_tid
            else:
                url = '/list/%s_%d.html' % (actual_tid, pg)

            if order and order != 'time':
                url = '/search.php?page=%d&searchtype=5&order=%s&tid=%s' % (pg, order, actual_tid)

            html = self._fetch_html(url)
            vod_list = self._parse_cards(html)
            pagecount = self._parse_pagecount(html)

            return {
                'page': pg,
                'pagecount': pagecount,
                'limit': len(vod_list),
                'total': pagecount * 24 if pagecount < 999 else 99999,
                'list': vod_list,
            }
        except Exception:
            return {'page': pg, 'pagecount': 1, 'limit': 24, 'total': 0, 'list': []}

    def _parse_pagecount(self, html):
        """从分页 HTML 中解析总页数"""
        try:
            m = re.search(r'(\d+)\s*(?:&nbsp;)?\s*/\s*(?:&nbsp;)?\s*(\d+)', html)
            if m:
                return int(m.group(2))
            nums = re.findall(r'/list/\d+_(\d+)\.html', html)
            if nums:
                return max(int(n) for n in nums)
            if '下一页' in html:
                return 999
        except Exception:
            pass
        return 1

    # ===================================================================
    #  详情页
    # ===================================================================

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else str(ids)

            vid_match = re.search(r'(\d+)', vod_id)
            if vid_match:
                vod_id = vid_match.group(1)

            html = self._fetch_html('/nv/%s.html' % vod_id)

            vod_name = ''
            title_match = re.search(r'<title>(.*?)</title>', html, re.S)
            if title_match:
                vod_name = title_match.group(1).strip()
                vod_name = re.sub(r'《|》', '', vod_name)
                vod_name = re.sub(r'鬼片大全高清完整版在线观看.*$', '', vod_name)
                vod_name = re.sub(r'-鬼片之家.*$', '', vod_name)

            dc_title = re.search(r'<h2[^>]*class="hl-dc-title[^"]*"[^>]*>(.*?)</h2>', html, re.S)
            if dc_title:
                name = re.sub(r'<[^>]+>', '', dc_title.group(1)).strip()
                if name:
                    vod_name = name

            vod_content = ''
            desc_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
            if desc_m:
                vod_content = desc_m.group(1)
                vod_content = re.sub(r'^[^：]*剧情介绍：', '', vod_content)

            vod_pic = ''
            pic_m = re.search(r'hl-item-pic[^>]*>.*?data-original="([^"]+)"', html, re.S)
            if pic_m:
                vod_pic = pic_m.group(1)
            if not vod_pic:
                og = re.search(r'<meta\s+property="og:image"\s+content="([^"]*)"', html)
                if og:
                    vod_pic = og.group(1)
            vod_pic = self._wrap_pic(vod_pic)

            vod_year = ''
            vod_class = ''
            vod_area = ''
            vod_director = ''
            vod_actor = ''
            vod_remarks = ''
            vod_lang = ''

            info_items = re.findall(
                r'<em class="hl-text-muted">(.*?)</em>(.*?)(?:</li>|<li)',
                html, re.S
            )
            for label, raw_val in info_items:
                label = re.sub(r'<[^>]+>', '', label).strip().rstrip('：:')
                value = re.sub(r'<[^>]+>', '', raw_val).strip()
                value = value.replace('&nbsp;', ' ').strip()
                value = re.sub(r'\s{2,}', ' ', value)

                if label == '片名':
                    if not vod_name:
                        vod_name = value
                elif label == '状态':
                    vod_remarks = value
                elif label == '主演':
                    vod_actor = value
                elif label == '导演':
                    vod_director = value
                elif label == '年份':
                    vod_year = value
                elif label == '地区':
                    vod_area = value
                elif label == '类型':
                    vod_class = value
                elif label == '语言':
                    vod_lang = value
                elif label == '简介':
                    if not vod_content:
                        vod_content = value

            play_from_list = []
            play_url_list = []

            source_names = re.findall(
                r'<a[^>]*class="hl-tabs-btn[^"]*"[^>]*alt="([^"]+)"',
                html
            )

            play_boxes = re.findall(
                r'<div class="hl-tabs-box[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
                html, re.S
            )

            if not play_boxes:
                play_boxes = re.split(r'<div class="hl-tabs-box', html)[1:]

            source_idx = 0
            for box_html in play_boxes:
                eps = re.findall(
                    r"<a\s+title='([^']*)'\s+href='(/play/[^']+)'",
                    box_html
                )
                if not eps:
                    eps = re.findall(
                        r'<a\s+title="([^"]*)"\s+href="(/play/[^"]+)"',
                        box_html
                    )
                if eps:
                    source_name = source_names[source_idx] if source_idx < len(source_names) else '播放源%d' % (source_idx + 1)
                    play_from_list.append(source_name)

                    ep_list = []
                    for ep_name, ep_url in eps:
                        ep_list.append('%s$%s' % (ep_name, ep_url))
                    play_url_list.append('#'.join(ep_list))
                    source_idx += 1

            if not play_from_list:
                play_from_list.append('鬼片之家')
                play_url_list.append('播放$/nv/%s.html' % vod_id)

            vod = {
                'vod_id': vod_id,
                'vod_name': vod_name,
                'vod_pic': vod_pic,
                'type_name': vod_class or '鬼片之家',
                'vod_year': vod_year,
                'vod_area': vod_area,
                'vod_actor': vod_actor,
                'vod_director': vod_director,
                'vod_content': vod_content,
                'vod_remarks': vod_remarks,
                'vod_play_from': '$$$'.join(play_from_list),
                'vod_play_url': '$$$'.join(play_url_list),
            }
            return {'list': [vod]}
        except Exception:
            return {'list': []}

    # ===================================================================
    #  搜索
    # ===================================================================

    def searchContent(self, key, quick, pg=1):
        try:
            pg = int(pg or 1)
            encoded_key = quote(key)

            search_path = '/search.php?searchword=%s' % encoded_key
            if pg > 1:
                search_path += '&page=%d' % pg

            html = self._fetch_html(search_path)

            if '系统安全验证' in html or '验证码' in html:
                return {'list': [], 'page': pg}

            vod_list = self._parse_cards(html)

            return {
                'list': vod_list[:30],
                'page': pg,
            }
        except Exception:
            return {'list': [], 'page': 1}

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key, quick, pg)

    # ===================================================================
    #  播放
    # ===================================================================

    def playerContent(self, flag, id, vipFlags=''):
        """
        播放解析。直接从播放页提取 m3u8 直链（parse:0）。
        """
        try:
            play_url = str(id or '')

            if play_url.startswith('/play/'):
                full_url = self.host + play_url
            elif play_url.startswith('http'):
                full_url = play_url
            else:
                return {}

            play_headers = dict(self.header)
            play_headers['Referer'] = self.host + '/'
            r = self.fetch(full_url, headers=play_headers, timeout=15)
            html = self._to_text(r)

            m3u8 = ''
            now_m = re.search(r'var\s+now\s*=\s*"([^"]+)"', html)
            if now_m:
                m3u8 = now_m.group(1)

            if m3u8 and '.m3u8' in m3u8:
                return {
                    'parse': 0,
                    'url': m3u8,
                    'header': {
                        'User-Agent': self.header['User-Agent'],
                        'Referer': self.host + '/',
                    },
                }

            iframe_m = re.search(r'<iframe[^>]*src="([^"]+)"', html)
            if iframe_m:
                iframe_url = iframe_m.group(1)
                if not iframe_url.startswith('http'):
                    iframe_url = self.host + iframe_url

                r2 = self.fetch(iframe_url, headers=play_headers, timeout=15)
                html2 = self._to_text(r2)

                now_m2 = re.search(r'var\s+now\s*=\s*"([^"]+)"', html2)
                if now_m2:
                    m3u8 = now_m2.group(1)

                if m3u8 and '.m3u8' in m3u8:
                    return {
                        'parse': 0,
                        'url': m3u8,
                        'header': {
                            'User-Agent': self.header['User-Agent'],
                            'Referer': self.host + '/',
                        },
                    }

            return {
                'parse': 1,
                'url': full_url,
                'header': {
                    'User-Agent': self.header['User-Agent'],
                    'Referer': self.host + '/',
                },
            }
        except Exception:
            return {}

    # ===================================================================
    #  本地代理 (图片代理) - 保留备用
    # ===================================================================

    def localProxy(self, param):
        """本地代理: 处理图片加载（备用，正常不走代理）"""
        try:
            if isinstance(param, str):
                from urllib.parse import parse_qs
                param_dict = parse_qs(param)
            else:
                param_dict = param

            do = param_dict.get('do', '')
            if isinstance(do, list):
                do = do[0] if do else ''

            if do == 'img':
                url = param_dict.get('url', '')
                if isinstance(url, list):
                    url = url[0] if url else ''

                if url:
                    try:
                        url = base64.urlsafe_b64decode(url).decode('utf-8')
                    except Exception:
                        pass

                    if url:
                        headers = {
                            'User-Agent': self.header['User-Agent'],
                            'Referer': self.host + '/',
                            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                        }
                        r = self.fetch(url, headers=headers, timeout=15)
                        content_type = ''
                        if hasattr(r, 'headers'):
                            ct = r.headers.get('Content-Type', '')
                            if ct and 'image' in ct:
                                content_type = ct
                        if not content_type:
                            if '.png' in url:
                                content_type = 'image/png'
                            elif '.webp' in url:
                                content_type = 'image/webp'
                            elif '.gif' in url:
                                content_type = 'image/gif'
                            else:
                                content_type = 'image/jpeg'
                        content = r.content if hasattr(r, 'content') else r.text.encode('utf-8')
                        return [200, content_type, content, {}]
        except Exception:
            pass
        return [404, 'text/plain', '', {}]

    # ===================================================================
    #  卡片解析（多层级回退，data-original 懒加载支持）
    # ===================================================================

    def _parse_cards(self, html):
        """解析视频卡片列表 - 针对 guipian456 海螺模板结构"""
        vod_list = []
        seen = set()

        card_pattern = re.compile(
            r'<li\s+class="hl-list-item[^"]*"[^>]*>(.*?)</li>',
            re.S
        )
        cards = card_pattern.findall(html)

        for card in cards:
            href_m = re.search(r'href="/nv/(\d+)\.html"', card)
            if not href_m:
                continue
            vid = href_m.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            name = ''
            title_m = re.search(r'title="([^"]+)"', card)
            if title_m:
                name = title_m.group(1).strip()

            pic_url = ''
            pic_m = re.search(r'data-original="([^"]+)"', card)
            if pic_m:
                pic_url = pic_m.group(1)

            remark = ''
            remark_m = re.search(r'class="hl-lc-1\s+remarks">([^<]+)', card)
            if remark_m:
                remark = remark_m.group(1).strip()

            score = ''
            score_m = re.search(r'class="hl-text-conch\s+score">([^<]+)', card)
            if score_m:
                score = score_m.group(1).strip()

            if score and not remark:
                remark = score

            pic_url = self._wrap_pic(pic_url)

            vod_list.append({
                'vod_id': vid,
                'vod_name': name or vid,
                'vod_pic': pic_url,
                'vod_remarks': remark,
            })

        if not vod_list:
            nv_pattern = re.compile(r'href="/nv/(\d+)\.html"[^>]*title="([^"]*)"', re.S)
            matches = nv_pattern.findall(html)

            for vid, name in matches:
                if vid in seen:
                    continue
                seen.add(vid)

                pic_url = ''
                pos = html.find('/nv/%s.html' % vid)
                if pos >= 0:
                    context = html[max(0, pos - 200):pos + 500]
                    pic_m = re.search(r'data-original="([^"]+)"', context)
                    if pic_m:
                        pic_url = pic_m.group(1)

                pic_url = self._wrap_pic(pic_url)

                vod_list.append({
                    'vod_id': vid,
                    'vod_name': name or vid,
                    'vod_pic': pic_url,
                    'vod_remarks': '',
                })

        return vod_list


# ===================================================================
#  模块级转发（兼容 hipy / CatVod-T4 / FongMi 按函数名调用）
# ===================================================================
_spider = Spider()


def getName():
    return _spider.getName()


def init(extend=''):
    return _spider.init(extend)


def homeContent(filter):
    return _spider.homeContent(filter)


def homeVideoContent():
    return _spider.homeVideoContent()


def categoryContent(tid, pg, filter, extend):
    return _spider.categoryContent(tid, pg, filter, extend)


def detailContent(ids):
    return _spider.detailContent(ids)


def searchContent(key, quick, pg=1):
    return _spider.searchContent(key, quick, pg)


def searchContentPage(key, quick, pg=1):
    return _spider.searchContentPage(key, quick, pg)


def playerContent(flag, id, vipFlags):
    return _spider.playerContent(flag, id, vipFlags)


def localProxy(param):
    return _spider.localProxy(param)


def manualVideoCheck():
    return _spider.manualVideoCheck()


def destroy():
    return _spider.destroy()


if __name__ == '__main__':
    s = Spider()
    s.init('')
    print('=== homeContent ===')
    h = s.homeContent(False)
    print('class 数量:', len(h['class']))
    print('=== homeVideoContent ===')
    hv = s.homeVideoContent()
    print('首页卡片:', len(hv['list']))
    if hv['list']:
        print('  首条:', hv['list'][0]['vod_name'], '| pic:', hv['list'][0]['vod_pic'][:50])
    print('=== categoryContent t=1 pg=1 ===')
    c = s.categoryContent('1', 1, False, None)
    print('列表:', len(c['list']), '| pagecount:', c['pagecount'])
    if c['list']:
        vid = c['list'][0]['vod_id']
        print('  首条:', c['list'][0]['vod_name'], '| id:', vid)
        print('=== detailContent ===')
        d = s.detailContent([vid])
        if d['list']:
            v = d['list'][0]
            print('  名称:', v['vod_name'], '| pic:', v['vod_pic'][:50])
            print('  play_from:', v['vod_play_from'])
            print('  play_url :', v['vod_play_url'][:80])
            print('=== playerContent ===')
            p = s.playerContent(v['vod_play_from'].split('$$$')[0], v['vod_play_url'].split('$$$')[0].split('#')[0].split('$')[-1])
            print('  parse:', p.get('parse'), '| url:', p.get('url', '')[:70])
    print('=== 当前生效域名:', s.host, '===')
