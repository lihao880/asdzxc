"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '极乐禁区',
  lang: 'hipy',
})
"""

import re
import json
import html
from urllib.parse import urljoin, quote

try:
    import requests
except Exception:
    requests = None

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

from base.spider import Spider


class Spider(Spider):
    host = 'https://iegeewiet-4mag.hscwang26y2m.xyz'
    home_url = host + '/jlhs'
    ua = 'Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'

    # 特殊分类（二级目录）
    _special_cats = {
        '百大女优': host + '/label/sortjp/',
        '番号仓库': host + '/label/sortnu/',
        '国产传媒': host + '/label/sortcn/',
        '91探花': host + '/label/sortfl/',
    }

    # 视频分类
    _video_cats = [
        {'type_id': '45', 'type_name': '视频一区'},
        {'type_id': '46', 'type_name': '视频二区'},
        {'type_id': '47', 'type_name': '视频三区'},
    ]

    # 子类型筛选（筛选下拉框内容放到分类）
    _sub_types = {
        '45': [
            {'n': '全部', 'v': ''},
            {'n': '精品日韩', 'v': '51'},
            {'n': '国产精品', 'v': '49'},
            {'n': '日韩无码', 'v': '50'},
            {'n': '中文字幕', 'v': '52'},
            {'n': '欧美极品', 'v': '53'},
            {'n': '动漫精品', 'v': '54'},
            {'n': '淫欲痴女', 'v': '55'},
            {'n': 'SM变态', 'v': '56'},
        ],
        '46': [
            {'n': '全部', 'v': ''},
            {'n': '偷拍偷窥', 'v': '57'},
            {'n': '性感人妻', 'v': '61'},
            {'n': '网红主播', 'v': '64'},
            {'n': '黑丝诱惑', 'v': '63'},
            {'n': '三级伦理', 'v': '62'},
            {'n': '童颜巨乳', 'v': '58'},
            {'n': '明星换脸', 'v': '517'},
            {'n': '女优明星', 'v': '59'},
        ],
        '47': [
            {'n': '全部', 'v': ''},
            {'n': '国产自拍', 'v': '66'},
            {'n': '剧情解说', 'v': '68'},
            {'n': '网曝黑料', 'v': '71'},
            {'n': '萝莉少女', 'v': '73'},
            {'n': '同性世界', 'v': '70'},
            {'n': '制服诱惑', 'v': '69'},
            {'n': '网曝吃瓜', 'v': '67'},
            {'n': '门事件', 'v': '72'},
        ],
    }

    # 传媒类分类
    _media_cats = [
        {'type_id': '202', 'type_name': '麻豆传媒'},
        {'type_id': '205', 'type_name': '天美传媒'},
        {'type_id': '206', 'type_name': '果冻传媒'},
        {'type_id': '207', 'type_name': '91制片厂'},
        {'type_id': '208', 'type_name': '蜜桃传媒'},
        {'type_id': '209', 'type_name': '精东影业'},
        {'type_id': '210', 'type_name': '皇家华人'},
        {'type_id': '223', 'type_name': '星空传媒'},
    ]

    # 女优类分类
    _actress_cats = [
        {'type_id': '401', 'type_name': '梦乃爱华'},
        {'type_id': '402', 'type_name': '波多野结衣'},
        {'type_id': '404', 'type_name': '河北彩花'},
        {'type_id': '409', 'type_name': '桃乃木香奈'},
        {'type_id': '412', 'type_name': '相泽南'},
        {'type_id': '414', 'type_name': 'Miru'},
        {'type_id': '419', 'type_name': '木下日葵'},
        {'type_id': '429', 'type_name': '明里紬'},
    ]

    # 番号类分类
    _code_cats = [
        {'type_id': '301', 'type_name': '200GANA'},
        {'type_id': '302', 'type_name': '300MIUM'},
        {'type_id': '308', 'type_name': '300MAAN'},
        {'type_id': '309', 'type_name': '300NTK'},
        {'type_id': '313', 'type_name': '336KNB'},
        {'type_id': '329', 'type_name': 'AARM'},
        {'type_id': '345', 'type_name': 'DVAJ'},
        {'type_id': '326', 'type_name': 'MUDR'},
    ]

    # 91探花类分类
    _tanflower_cats = [
        {'type_id': '501', 'type_name': '91沈先生'},
        {'type_id': '502', 'type_name': '文轩探花'},
        {'type_id': '503', 'type_name': '千人斩'},
        {'type_id': '509', 'type_name': '李寻欢探花'},
        {'type_id': '513', 'type_name': '酒店'},
        {'type_id': '514', 'type_name': '小宝寻花'},
        {'type_id': '515', 'type_name': '午夜寻花'},
        {'type_id': '516', 'type_name': '91系列'},
    ]

    # ==================== 生命周期 ====================

    def __init__(self, *args, **kwargs):
        self.extend = ''
        self.s = requests.Session() if requests else None
        if self.s:
            self.s.headers.update({'User-Agent': self.ua})
            self.s.verify = False

    def init(self, extend=''):
        self.extend = extend
        return '{}'

    def getName(self):
        return '极乐禁区'

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.s:
            self.s.close()

    # ==================== 内部工具 ====================

    def _headers(self, referer=None):
        return {'User-Agent': self.ua, 'Referer': referer or self.host}

    def _get(self, url, referer=None):
        if self.s:
            r = self.s.get(url, headers=self._headers(referer), timeout=20, verify=False)
            r.encoding = r.apparent_encoding or 'utf-8'
            return r.text
        from urllib.request import Request, urlopen
        return urlopen(Request(url, headers=self._headers(referer)), timeout=20).read().decode('utf-8', 'ignore')

    def _clean(self, s):
        return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', s or ''))).strip()

    def _href(self, h):
        return urljoin(self.host, html.unescape((h or '').replace('\\/', '/')))

    @staticmethod
    def _extract(text, rule):
        """TVBox JSON 规则提取: prefix&&suffix 格式"""
        parts = rule.split('&&')
        if len(parts) != 2:
            return ''
        prefix, suffix = parts
        idx = text.find(prefix)
        if idx == -1:
            return ''
        start = idx + len(prefix)
        end = text.find(suffix, start)
        if end == -1:
            return ''
        return text[start:end]

    def _fix_pic(self, pic):
        """补全图片URL"""
        if not pic:
            return ''
        pic = html.unescape(pic.replace('\\/', '/'))
        if not pic.startswith('http'):
            pic = self._href(pic)
        return pic

    def _get_pagecount(self, text):
        """获取总页数"""
        m = re.search(r'href="[^"]*-(\d+)/?"[^>]*title="尾页"', text, re.I)
        if m:
            return int(m.group(1))
        nums = re.findall(r'class="page_link"\s+href="[^"]*-(\d+)/', text)
        if nums:
            max_page = max(int(n) for n in nums)
            if max_page > 1:
                return max_page
        m = re.search(r'共\s*(\d+)\s*页', text)
        if m:
            return int(m.group(1))
        if '下一页' in text or '尾页' in text:
            return 2
        return 1

    # ==================== 列表解析 ====================

    def _parse_video_list(self, text):
        """解析视频列表（分类页、首页通用）"""
        out = []
        segments = text.split('</li>')
        for seg in segments:
            block = self._extract(seg, '<a class="thumbnail"&&</div>')
            if not block:
                continue
            title = self._clean(self._extract(block, '">&&</a></h5>'))
            if not title:
                continue
            subtitle = self._clean(self._extract(block, '<p>&&</p>'))
            pic = self._fix_pic(self._extract(block, 'data-original="&&"'))
            vod_id = self._extract(seg, '<a href="/voddetail/&&/')
            if not vod_id:
                continue
            play_url = self.host + '/vodplay/' + vod_id + '-1-1/'
            out.append({
                'vod_id': play_url,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': subtitle,
            })
        return out

    def _parse_search_list(self, text):
        """解析搜索结果列表"""
        out = []
        segments = text.split('</li>')
        for seg in segments:
            block = self._extract(seg, '<a class="thumbnail"&&</div>')
            if not block:
                continue
            title = self._clean(self._extract(block, 'title="&&"'))
            if not title:
                title = self._clean(self._extract(block, '">&&</a></h5>'))
            if not title:
                continue
            pic = self._fix_pic(self._extract(block, '<img src="&&"'))
            if not pic:
                pic = self._fix_pic(self._extract(block, 'data-original="&&"'))
            vod_id = self._extract(seg, '<a href="/voddetail/&&/')
            if not vod_id:
                continue
            play_url = self.host + '/vodplay/' + vod_id + '-1-1/'
            out.append({
                'vod_id': play_url,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': '',
            })
        return out

    def _parse_special_list(self, text, cate_pg=1):
        """解析特殊分类列表（百大女优/番号仓库/国产传媒/91探花）"""
        out = []
        for m in re.finditer(r'<li>\s*<a\s+hr', text, re.I):
            end = text.find('</li>', m.start())
            if end == -1:
                continue
            block = text[m.start():end + 5]
            title = self._clean(self._extract(block, '#;">&&</span>'))
            if not title:
                continue
            pic = self._fix_pic(self._extract(block, '<img src="&&"'))
            href_m = re.search(r'href="([^"]+)"', block)
            if not href_m:
                continue
            href = href_m.group(1)
            if not href.startswith('http'):
                href = self._href(href)
            play_url = href.rstrip('/') + '-' + str(cate_pg) + '/'
            out.append({
                'vod_id': play_url,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': '',
                'vod_tag': 'folder',
            })
        return out

    # ==================== TVBox 接口 ====================

    def homeContent(self, filter=False):
        """首页分类（补充完全分类，覆盖导航栏所有分类）"""
        categories = []

        # 特殊分类（二级目录: 百大女优,番号仓库,国产传媒,91探花）
        for name in self._special_cats:
            categories.append({
                'type_id': 'special_' + name,
                'type_name': name,
            })

        # 视频分类及子类型（把筛选下拉框内容放到分类）
        for cat in self._video_cats:
            categories.append({
                'type_id': cat['type_id'],
                'type_name': cat['type_name'],
            })
            tid = cat['type_id']
            if tid in self._sub_types:
                for sub in self._sub_types[tid]:
                    if sub['v']:
                        categories.append({
                            'type_id': sub['v'],
                            'type_name': sub['n'],
                        })

        # 传媒类分类
        for cat in self._media_cats:
            categories.append({
                'type_id': cat['type_id'],
                'type_name': cat['type_name'],
            })

        # 女优类分类
        for cat in self._actress_cats:
            categories.append({
                'type_id': cat['type_id'],
                'type_name': cat['type_name'],
            })

        # 番号类分类
        for cat in self._code_cats:
            categories.append({
                'type_id': cat['type_id'],
                'type_name': cat['type_name'],
            })

        # 91探花类分类
        for cat in self._tanflower_cats:
            categories.append({
                'type_id': cat['type_id'],
                'type_name': cat['type_name'],
            })

        return {'class': categories}

    def homeVideoContent(self):
        """首页视频列表"""
        text = self._get(self.home_url)
        return {'list': self._parse_video_list(text)}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        """分类内容: https://host/vodtype/{cateId}-{catePg}/"""
        page = int(pg) if pg else 1
        tid = str(tid)

        # 特殊分类（二级目录: 百大女优等）
        if tid.startswith('special_'):
            cat_name = tid[8:]
            url = self._special_cats.get(cat_name, '')
            if not url:
                return {'page': page, 'pagecount': 1, 'list': []}
            if page != 1:
                url = url.rstrip('/') + '/' + str(page) + '/'
            text = self._get(url)
            items = self._parse_special_list(text, page)
            pc = self._get_pagecount(text)
            return {
                'page': page,
                'pagecount': pc,
                'limit': len(items),
                'total': pc * len(items) if items else 0,
                'list': items,
            }

        # URL 类型的 tid（来自特殊分类子项点击）
        if tid.startswith('http') or tid.startswith('/'):
            url = tid if tid.startswith('http') else self._href(tid)
            url = re.sub(r'-\d+$', '', url.rstrip('/'))
            url = url + '-' + str(page) + '/'
            text = self._get(url)
            items = self._parse_video_list(text)
            pc = self._get_pagecount(text)
            return {
                'page': page,
                'pagecount': pc,
                'limit': len(items),
                'total': pc * len(items) if items else 0,
                'list': items,
            }

        # 视频分类（vodtype）
        cate_id = tid
        url = self.host + '/vodtype/' + cate_id + '-' + str(page) + '/'

        # 处理筛选（子类型）
        if extend:
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            sub_type = extend.get('type', '')
            if sub_type:
                url = self.host + '/vodtype/' + sub_type + '-' + str(page) + '/'

        text = self._get(url)
        items = self._parse_video_list(text)
        pc = self._get_pagecount(text)
        return {
            'page': page,
            'pagecount': pc,
            'limit': len(items),
            'total': pc * len(items) if items else 0,
            'list': items,
        }

    def searchContent(self, key, quick=False, pg='1'):
        """搜索: https://host/vodsearch/{wd}----------{pg}---/"""
        page = int(pg) if pg else 1
        wd = quote(str(key))
        url = self.host + '/vodsearch/' + wd + '----------' + str(page) + '---/'
        text = self._get(url)
        items = self._parse_search_list(text)
        pc = self._get_pagecount(text)
        if pc <= page and len(items) >= 12:
            pc = page + 1
        return {
            'page': page,
            'pagecount': pc,
            'limit': len(items),
            'total': len(items),
            'list': items,
        }

    def detailContent(self, ids):
        """详情页（取消多集二级播放选集，直接展示播放链接）"""
        u = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        if not str(u).startswith('http'):
            u = self._href(str(u))

        text = self._get(u)

        # 标题
        title = ''
        m = re.search(r'<h5[^>]*>(.*?)</h5>', text, re.I | re.S)
        if m:
            title = self._clean(m.group(1))
        if not title:
            m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.I | re.S)
            if m:
                title = self._clean(m.group(1))
        if not title:
            m = re.search(r'<title>(.*?)</title>', text, re.I | re.S)
            if m:
                raw_title = self._clean(m.group(1))
                for prefix in ['在线观看', '极乐禁区']:
                    if raw_title.startswith(prefix):
                        raw_title = raw_title[len(prefix):]
                title = raw_title.split('-')[0].split('_')[0].strip()

        # 图片
        pic = ''
        m = re.search(r'data-original="([^"]+)"', text)
        if m:
            pic = m.group(1)
        if not pic:
            m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)', text, re.I)
            if m:
                pic = m.group(1)
        if not pic:
            m = re.search(r'<img[^>]+src="([^"]+)"', text)
            if m:
                pic = m.group(1)
        pic = self._fix_pic(pic)

        # 简介
        content = ''
        m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)', text, re.I)
        if m:
            content = self._clean(m.group(1))

        vod = {
            'vod_id': u,
            'vod_name': title,
            'vod_pic': pic,
            'vod_content': content,
            'vod_play_from': '极乐禁区',
            'vod_play_url': '正片$' + u,
        }
        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags=None):
        """播放（嗅探 m3u8/mp4，测试线路，过滤无效选项）"""
        url = str(id)

        if not re.search(r'\.(?:m3u8|mp4|flv)(?:$|[?#])', url, re.I):
            try:
                text = self._get(url)
                # 从 player_aaaa 变量提取视频URL
                m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', text, re.S)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        vurl = data.get('url', '')
                        if vurl:
                            url = vurl
                    except Exception:
                        pass
                # 嗅探 .m3u8 和 .mp4
                if not re.search(r'\.(?:m3u8|mp4)(?:$|[?#])', url, re.I):
                    m = re.search(r'(https?://[^\s"\'<>]+?\.(?:m3u8|mp4)[^\s"\'<>]*)', text, re.I)
                    if m:
                        url = m.group(1)
                # 从 iframe 提取
                if not re.search(r'\.(?:m3u8|mp4)(?:$|[?#])', url, re.I):
                    m = re.search(r'<iframe[^>]+src="([^"]+)"', text, re.I)
                    if m:
                        iframe_url = self._href(m.group(1))
                        try:
                            iframe_text = self._get(iframe_url)
                            m2 = re.search(r'(https?://[^\s"\'<>]+?\.(?:m3u8|mp4)[^\s"\'<>]*)', iframe_text, re.I)
                            if m2:
                                url = m2.group(1)
                        except Exception:
                            pass
            except Exception:
                pass

        return {
            'parse': 0,
            'jx': 0,
            'playUrl': '',
            'url': url,
            'header': 'User-Agent: %s\r\nReferer: %s' % (self.ua, self.host),
        }
