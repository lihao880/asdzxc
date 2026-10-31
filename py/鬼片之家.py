# -*- coding: utf-8 -*-
"""
=================================================
  修复版：鬼片之家 TVBox 源
=================================================

修复点（相较原版）：
1. 【关键】host 已从 kanguipian.com 更新为最终域名 kanguipian456.cc
   —— 原域名已 301 跳转到新域名，写死旧域名会导致所有请求落到错误站点/拿不到正文。
2. 【关键】_fetch_html 兼容 TVBox 的 self.fetch 返回值：
   TVBox(FongMi T3) 的 fetch 往往直接返回「字符串」或「bytes」，
   而原代码的 `r.content.decode(...)` 在返回 str 时会 AttributeError 崩溃。
   新增 _to_text() 统一把 str / bytes / Response 对象规整为文本。
3. 不再依赖 r.status_code == 200 做判断（str 没有该属性），直接以「拿到文本」为准。
4. 其余解析逻辑（海螺模板 v3.1 的 hl-list-item / hl-text-muted / data-original /
   hl-tabs-box / /nv/ / /play/）保持，已对照真实首页 HTML 验证 class 命名一致。
"""
import sys
import json
import re
import base64
import time
from urllib.parse import quote, urlencode, urlparse

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as rq

    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

        def post(self, url, data=None, headers=None, **kw):
            r = rq.post(url, data=data, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r


class Spider(Spider):
    """
    鬼片之家 Spider
    MacCMS + 海螺模板 v3.1, HTML 解析
    """

    # 修复点1：旧域名 kanguipian.com 已 301 跳转到 kanguipian456.cc
    host = 'https://www.kanguipian456.cc'

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
        if isinstance(extend, list):
            self.extend = ''
        else:
            self.extend = extend or ''

    def isVideoFormat(self, url):
        return any(x in url for x in ['.m3u8', '.mp4', '.flv', '.avi', '.mkv'])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ===================================================================
    #  请求封装（修复点2/3：兼容 fetch 返回 str/bytes/Response）
    # ===================================================================

    @staticmethod
    def _to_text(resp):
        """把 self.fetch 的多种返回值规整为字符串。

        TVBox(FongMi T3) 的 fetch 可能返回：
          - str（最常见）
          - bytes（含 gzip）
          - 带 .text / .content 的 Response 对象
        """
        if resp is None:
            return ''
        if isinstance(resp, str):
            return resp
        if isinstance(resp, (bytes, bytearray)):
            # 可能是 gzip，简单探测魔数
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
        # 兜底：当作 Response 对象处理
        if hasattr(resp, 'text') and resp.text:
            return resp.text
        if hasattr(resp, 'content'):
            try:
                return resp.content.decode('utf-8', 'replace')
            except Exception:
                return ''
        return ''

    def _fetch_html(self, path):
        """获取页面 HTML，最多重试一次。"""
        url = path if path.startswith('http') else self.host + path
        last_text = ''
        for _ in range(2):  # 首次 + 重试一次
            try:
                r = self.fetch(url, headers=self.header, timeout=15)
                text = self._to_text(r)
                if text:
                    return text
                last_text = text
            except Exception:
                continue
        return last_text

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
        # 鬼片大全分类
        filters['1'] = [
            {'key': 'cate', 'name': '子分类', 'value': self._filter_guipian},
            {'key': 'order', 'name': '排序', 'value': self._filter_sort},
        ]
        # 电视剧分类
        filters['2'] = [
            {'key': 'cate', 'name': '子分类', 'value': self._filter_tv},
            {'key': 'order', 'name': '排序', 'value': self._filter_sort},
        ]
        # 恐怖片分类（无子分类）
        filters['3'] = [
            {'key': 'order', 'name': '排序', 'value': self._filter_sort},
        ]
        # 动漫分类
        filters['4'] = [
            {'key': 'cate', 'name': '子分类', 'value': self._filter_anime},
            {'key': 'order', 'name': '排序', 'value': self._filter_sort},
        ]
        # 其他分类
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

            # 解析筛选器参数
            ext = {}
            if extend:
                if isinstance(extend, dict):
                    ext = extend
                elif isinstance(extend, str):
                    try:
                        ext = json.loads(extend)
                    except Exception:
                        ext = {}

            # 子分类覆盖 tid
            cate = ext.get('cate', '')
            order = ext.get('order', 'time')

            # 如果有子分类，使用子分类的 tid
            actual_tid = cate if cate else tid

            # 构建分页 URL: /list/{tid}.html 或 /list/{tid}_{page}.html
            if pg <= 1:
                url = '/list/%s.html' % actual_tid
            else:
                url = '/list/%s_%d.html' % (actual_tid, pg)

            # 排序参数通过 URL 参数传递
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
            # 匹配 "X / Y" 格式 (含 &nbsp; 如 "1&nbsp;/&nbsp;848")
            m = re.search(r'(\d+)\s*(?:&nbsp;)?\s*/\s*(?:&nbsp;)?\s*(\d+)', html)
            if m:
                return int(m.group(2))
            # 找分页链接中的页码数字
            nums = re.findall(r'/list/\d+_(\d+)\.html', html)
            if nums:
                return max(int(n) for n in nums)
            # 如果有 "下一页" 链接
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

            # 提取数字 ID (从 /nv/XXXXX.html 格式)
            vid_match = re.search(r'(\d+)', vod_id)
            if vid_match:
                vod_id = vid_match.group(1)

            html = self._fetch_html('/nv/%s.html' % vod_id)

            # 标题
            vod_name = ''
            title_match = re.search(r'<title>(.*?)</title>', html, re.S)
            if title_match:
                vod_name = title_match.group(1).strip()
                vod_name = re.sub(r'《|》', '', vod_name)
                vod_name = re.sub(r'鬼片大全高清完整版在线观看.*$', '', vod_name)
                vod_name = re.sub(r'-鬼片之家.*$', '', vod_name)

            # 从 hl-dc-title 提取更准确的标题
            dc_title = re.search(r'<h2[^>]*class="hl-dc-title[^"]*"[^>]*>(.*?)</h2>', html, re.S)
            if dc_title:
                name = re.sub(r'<[^>]+>', '', dc_title.group(1)).strip()
                if name:
                    vod_name = name

            # 描述
            vod_content = ''
            desc_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
            if desc_m:
                vod_content = desc_m.group(1)
                # 清理 "剧情介绍：" 前缀
                vod_content = re.sub(r'^[^：]*剧情介绍：', '', vod_content)

            # 封面图
            vod_pic = ''
            # 从详情页 data-original 提取
            pic_m = re.search(r'hl-item-pic[^>]*>.*?data-original="([^"]+)"', html, re.S)
            if pic_m:
                vod_pic = pic_m.group(1)
            if not vod_pic:
                og = re.search(r'<meta\s+property="og:image"\s+content="([^"]*)"', html)
                if og:
                    vod_pic = og.group(1)
            vod_pic = self._wrap_pic(vod_pic)

            # 从详情信息字段提取
            vod_year = ''
            vod_class = ''
            vod_area = ''
            vod_director = ''
            vod_actor = ''
            vod_remarks = ''
            vod_lang = ''

            # 解析信息列表
            info_items = re.findall(
                r'<em class="hl-text-muted">(.*?)</em>(.*?)(?:</li>|<li)',
                html, re.S
            )
            for label, raw_val in info_items:
                label = re.sub(r'<[^>]+>', '', label).strip().rstrip('：:')
                # 清理 HTML 标签和 &nbsp;
                value = re.sub(r'<[^>]+>', '', raw_val).strip()
                value = value.replace('&nbsp;', ' ').strip()
                # 合并多余空格
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

            # 提取选集
            play_from_list = []
            play_url_list = []

            # 播放源名称
            source_names = re.findall(
                r'<a[^>]*class="hl-tabs-btn[^"]*"[^>]*alt="([^"]+)"',
                html
            )

            # 播放列表 - 每个 hl-tabs-box 对应一个播放源
            play_boxes = re.findall(
                r'<div class="hl-tabs-box[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
                html, re.S
            )

            if not play_boxes:
                # 尝试另一种匹配方式
                play_boxes = re.split(r'<div class="hl-tabs-box', html)[1:]

            # 按播放源分组提取选集
            source_idx = 0
            for box_html in play_boxes:
                # 提取该源下的所有选集
                eps = re.findall(
                    r"<a\s+title='([^']*)'\s+href='(/play/[^']+)'",
                    box_html
                )
                if not eps:
                    # 兼容双引号写法
                    eps = re.findall(
                        r'<a\s+title="([^"]*)"\s+href="(/play/[^"]+)"',
                        box_html
                    )
                if eps:
                    source_name = source_names[source_idx] if source_idx < len(source_names) else '播放源%d' % (source_idx + 1)
                    play_from_list.append(source_name)

                    ep_list = []
                    for ep_name, ep_url in eps:
                        # 格式: 选集名$播放URL
                        ep_list.append('%s$%s' % (ep_name, ep_url))
                    play_url_list.append('#'.join(ep_list))
                    source_idx += 1

            # 如果没有找到选集，至少返回当前播放链接
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

            # 搜索 URL: /search.php?searchword=关键词
            # 注意: 该站搜索有验证码保护，可能无法直接搜索
            search_path = '/search.php?searchword=%s' % encoded_key
            if pg > 1:
                search_path += '&page=%d' % pg

            html = self._fetch_html(search_path)

            # 检查是否触发验证码
            if '系统安全验证' in html or '验证码' in html:
                # 搜索被验证码拦截，返回空结果
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

    def playerContent(self, flag, id, vipFlags):
        """
        播放解析。
        直接从播放页提取 m3u8 直链（parse:0）。
        """
        try:
            play_url = str(id or '')

            # 构建完整播放页 URL
            if play_url.startswith('/play/'):
                full_url = self.host + play_url
            elif play_url.startswith('http'):
                full_url = play_url
            else:
                return {}

            # 获取播放页 HTML
            play_headers = dict(self.header)
            play_headers['Referer'] = self.host + '/'
            r = self.fetch(full_url, headers=play_headers, timeout=15)
            html = self._to_text(r)

            # 提取 m3u8 直链
            # 格式: var now="https://xxx/video/index.m3u8"
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

            # 如果没有找到 m3u8，尝试提取 iframe 源
            iframe_m = re.search(r'<iframe[^>]*src="([^"]+)"', html)
            if iframe_m:
                iframe_url = iframe_m.group(1)
                if not iframe_url.startswith('http'):
                    iframe_url = self.host + iframe_url

                # 请求 iframe 页面提取真实播放地址
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

            # 回退: parse:1 网页解析
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
        """解析视频卡片列表 - 针对 kanguipian 海螺模板结构"""
        vod_list = []
        seen = set()

        # 方法1: 匹配 hl-list-item 结构 (首页/分类页/搜索页通用)
        card_pattern = re.compile(
            r'<li\s+class="hl-list-item[^"]*"[^>]*>(.*?)</li>',
            re.S
        )
        cards = card_pattern.findall(html)

        for card in cards:
            # 提取视频 ID 和链接
            href_m = re.search(r'href="/nv/(\d+)\.html"', card)
            if not href_m:
                continue
            vid = href_m.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            # 提取标题
            name = ''
            title_m = re.search(r'title="([^"]+)"', card)
            if title_m:
                name = title_m.group(1).strip()

            # 提取海报图片 - data-original 属性
            pic_url = ''
            pic_m = re.search(r'data-original="([^"]+)"', card)
            if pic_m:
                pic_url = pic_m.group(1)

            # 提取备注 (更新状态)
            remark = ''
            remark_m = re.search(r'class="hl-lc-1\s+remarks">([^<]+)', card)
            if remark_m:
                remark = remark_m.group(1).strip()

            # 提取评分
            score = ''
            score_m = re.search(r'class="hl-text-conch\s+score">([^<]+)', card)
            if score_m:
                score = score_m.group(1).strip()

            # 优先使用评分作为备注
            if score and not remark:
                remark = score

            pic_url = self._wrap_pic(pic_url)

            vod_list.append({
                'vod_id': vid,
                'vod_name': name or vid,
                'vod_pic': pic_url,
                'vod_remarks': remark,
            })

        # 方法2: 如果方法1没有结果，尝试更宽松的匹配
        if not vod_list:
            nv_pattern = re.compile(r'href="/nv/(\d+)\.html"[^>]*title="([^"]*)"', re.S)
            matches = nv_pattern.findall(html)

            for vid, name in matches:
                if vid in seen:
                    continue
                seen.add(vid)

                # 在附近找图片
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
