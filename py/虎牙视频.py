# -*- coding: utf-8 -*-
import re
import json
import base64
import urllib.parse
from bs4 import BeautifulSoup
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.huyasp.cc"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/',
            'Cookie': 'ageVerified=true'
        }
        # 主分类
        self.classes = [
            {"type_id": "3-极速传媒", "type_name": "极速传媒"},
            {"type_id": "19-极速视频", "type_name": "极速视频"},
            {"type_id": "27-极速影视", "type_name": "极速影视"},
            {"type_id": "2-备用专区", "type_name": "备用专区"},
        ]
        # 子分类筛选（从页面sub-nav提取）
        self.sub_classes = {
            "3-极速传媒": ["91传媒", "精东传媒", "麻豆传媒", "蜜桃传媒", "天美传媒", "星空传媒"],
            "19-极速视频": ["偷拍自拍", "日韩视频", "欧美性爱", "经典三级", "网红主播", "台湾辣妹", "onlyfans"],
            "27-极速影视": ["中文字幕", "经典素人", "高清无码", "美颜巨乳", "丝袜制服", "欧美系列", "卡通动画"],
            "2-备用专区": ["精选国产", "无码中字", "有码中字", "日本无码", "日本有码"],
        }
        self.filters = {}

    def getName(self):
        return "虎牙视频"

    def getDependence(self):
        return ['requests', 'bs4']

    def init(self, extend=""):
        pass

    def destroy(self):
        pass

    def fetch(self, url, headers=None, timeout=15):
        try:
            import requests
            headers = headers or self.headers
            resp = requests.get(url, headers=headers, timeout=timeout)
            return resp
        except Exception as e:
            print('fetch error:', e)
            return None

    def get_html(self, url, headers=None):
        resp = self.fetch(url, headers)
        if resp and resp.status_code == 200:
            return resp.text
        return None

    def fix_url(self, url):
        if not url:
            return ''
        url = url.strip()
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host.rstrip('/') + url
        return self.host.rstrip('/') + '/' + url.lstrip('/')

    def _parse_video_card(self, article):
        """解析单个 video-card 元素"""
        a = article.find('a', class_='video-card-link', href=True)
        if not a:
            return None

        href = a.get('href', '')
        vid = self._extract_vod_id(href)
        if not vid:
            return None

        title = ''
        h3 = article.find('h3', class_='video-title')
        if h3:
            title = h3.text.strip()

        pic = ''
        img = article.find('img')
        if img:
            pic = img.get('src') or img.get('data-src', '')
            pic = self.fix_url(pic)

        badge = ''
        span_badge = article.find('span', class_='video-badge')
        if span_badge:
            badge = span_badge.text.strip()

        date = ''
        meta_line = article.find('div', class_='video-meta-line')
        if meta_line:
            spans = meta_line.find_all('span')
            if spans:
                date = spans[0].text.strip()

        remark = badge
        if date:
            remark = f"{badge} {date}" if badge else date

        return {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'vod_remarks': remark
        }

    def _parse_videos(self, html, limit=999):
        doc = BeautifulSoup(html, 'html.parser')
        videos = []
        for article in doc.find_all('article', class_='video-card'):
            item = self._parse_video_card(article)
            if item:
                videos.append(item)
            if len(videos) >= limit:
                break
        return videos

    def _extract_vod_id(self, url):
        if not url:
            return ''
        # /play/slug-id -> 返回完整 slug-id
        # 匹配 /play/xxx-数字 格式
        m = re.search(r'/play/([^/?]+)', url)
        if m:
            return m.group(1)
        return url
    def _get_pagination_total(self, html):
        doc = BeautifulSoup(html, 'html.parser')
        # 查找包含分页信息的元素
        pagination = doc.find('nav', class_='pagination-container')
        if pagination:
            # 方法1：从 section-header 的 span 中提取 "共 X 页"
            header = doc.find('div', class_='section-header')
            if header:
                span = header.find('span')
                if span:
                    text = span.text.strip()
                    m = re.search(r'共\s*(\d+)\s*页', text)
                    if m:
                        return int(m.group(1))
            # 方法2：从分页跳转 input 的 max 属性提取
            jump_input = pagination.find('input', class_='jump-input')
            if jump_input:
                max_val = jump_input.get('max')
                if max_val and max_val.isdigit():
                    return int(max_val)
            # 方法3：从分页链接中提取最大页码
            page_links = pagination.find_all('a', class_='page-link')
            max_page = 1
            for link in page_links:
                href = link.get('href', '')
                m = re.search(r'[?&]page=(\d+)', href)
                if m:
                    page_num = int(m.group(1))
                    if page_num > max_page:
                        max_page = page_num
            if max_page > 1:
                return max_page
        return 1
    def homeContent(self, filter=False):
        result = {'class': self.classes, 'filters': self.filters if filter else {}}
        html = self.get_html(self.host + '/')
        if html:
            result['list'] = self._parse_videos(html, 20)
        else:
            result['list'] = []
        return result

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐"""
        html = self.get_html(self.host + '/')
        if html:
            videos = self._parse_videos(html, 20)
            return {'list': videos}
        return {'list': []}
    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        # 子分类处理：如果tid是子分类名（如"91传媒"），直接使用
        # 否则tid是主分类ID（如"3-极速传媒"）
        # 检查是否是子分类
        is_sub = False
        for main_id, subs in self.sub_classes.items():
            if tid in subs:
                # tid是子分类名
                is_sub = True
                break

        if is_sub:
            # 子分类URL: /type/{子分类名}
            url = f"{self.host}/type/{urllib.parse.quote(tid)}"
        else:
            # 主分类URL: /type/{主分类ID}
            url = f"{self.host}/type/{tid}"

        if pg > 1:
            url += f"?page={pg}"

        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}

        videos = self._parse_videos(html)
        total_pages = self._get_pagination_total(html)
        if total_pages < 1:
            total_pages = 1

        return {
            'list': videos,
            'page': pg,
            'pagecount': total_pages,
            'total': total_pages * 20
        }

    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        vid = ids[0]
        url = f"{self.host}/play/{vid}"
        html = self.get_html(url)
        if not html:
            return {'list': []}

        doc = BeautifulSoup(html, 'html.parser')

        # 标题
        title = ''
        h1 = doc.find('h1', class_='page-title')
        if h1:
            title = h1.text.strip()

        # 分类
        category = ''
        meta_tiles = doc.find_all('span', class_='meta-tile')
        if len(meta_tiles) >= 1:
            strong = meta_tiles[0].find('strong')
            if strong:
                category = strong.text.strip()

        # 日期
        pub_date = ''
        if len(meta_tiles) >= 2:
            strong = meta_tiles[1].find('strong')
            if strong:
                pub_date = strong.text.strip()

        # 简介
        desc = ''
        summary = doc.find('p', class_='page-summary')
        if summary:
            desc = summary.text.strip()

        # 封面图
        pic = ''
        img = doc.find('meta', property='og:image')
        if img:
            pic = img.get('content', '')
        if not pic:
            # 从播放页找封面
            container = doc.find('div', id='player-container')
            if container:
                iframe = container.find('iframe')
                if iframe:
                    src = iframe.get('src', '')
                    m = re.search(r'poster=([^&]+)', src)
                    if m:
                        pic = urllib.parse.unquote(m.group(1))

        # 提取播放地址
        play_url = ''
        container = doc.find('div', id='player-container')
        if container:
            iframe = container.find('iframe')
            if iframe:
                src = iframe.get('src', '')
                # 解析 src 参数
                m = re.search(r'src=([^&]+)', src)
                if m:
                    play_url = urllib.parse.unquote(m.group(1))
                    if not play_url.startswith('http'):
                        play_url = self.fix_url(play_url)

        if not play_url:
            # 尝试从script中提取
            for script in doc.find_all('script'):
                text = script.text
                if 'playUrl' in text:
                    m = re.search(r"playUrl\s*=\s*['\"]([^'\"]+)['\"]", text)
                    if m:
                        play_url = m.group(1)
                        if not play_url.startswith('http'):
                            play_url = self.fix_url(play_url)
                        break

        # 构建播放数据
        if play_url:
            play_from = category or '默认线路'
            play_url_str = f"播放${play_url}"
        else:
            play_from = '默认线路'
            play_url_str = f"播放${vid}"

        data = {
            'vod_id': vid,
            'vod_name': title or '未知标题',
            'vod_pic': pic,
            'vod_remarks': pub_date,
            'vod_content': desc,
            'vod_actor': '',
            'vod_director': '',
            'vod_play_from': play_from,
            'vod_play_url': play_url_str,
        }
        return {'list': [data]}

    def searchContent(self, key, quick=False, pg='1'):
        if not key:
            return {'list': [], 'page': 1, 'pagecount': 1, 'total': 0}
        pg = int(pg) if pg else 1
        url = f"{self.host}/search?keyword={urllib.parse.quote(key)}"
        if pg > 1:
            url += f"&page={pg}"
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        videos = self._parse_videos(html)
        total_pages = self._get_pagination_total(html)
        if total_pages < 1:
            total_pages = 1
        return {
            'list': videos,
            'page': pg,
            'pagecount': total_pages,
            'total': total_pages * 20
        }

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {'parse': 1, 'url': ''}

        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/',
            'Cookie': 'ageVerified=true'
        }

        if id.startswith('http'):
            if id.endswith('.m3u8') or id.endswith('.mp4') or '.m3u8?' in id:
                return {'parse': 0, 'url': id, 'header': headers}
            # 尝试从页面提取
            html = self.get_html(id, headers)
            if html:
                # 寻找 videoSrc 或 m3u8
                m = re.search(r'videoSrc\s*=\s*["\']([^"\']+)["\']', html)
                if not m:
                    m = re.search(r'["\']([^"\']+\.m3u8[^"\']*)["\']', html)
                if m:
                    url = m.group(1)
                    if url.startswith('/'):
                        url = self.host + url
                    if url.endswith('.m3u8') or '.m3u8?' in url:
                        return {'parse': 0, 'url': url, 'header': headers}

        return {'parse': 1, 'url': id, 'header': headers}

    def localProxy(self, params):
        return [404, 'text/plain', b'Not Found']

    def recommendContent(self, ids=None, pg=1):
        """相关推荐 - 从详情页提取猜你喜欢区域"""
        if not ids:
            return {'list': []}
        if isinstance(ids, list):
            vid = ids[0] if ids else None
        else:
            vid = ids
        if not vid:
            return {'list': []}
        
        pg = int(pg) if pg else 1
        url = f"{self.host}/play/{vid}"
        html = self.get_html(url)
        if not html:
            return {'list': []}
        
        doc = BeautifulSoup(html, 'html.parser')
        videos = []
        
        # 查找猜你喜欢区域
        for section in doc.find_all('section', class_='page-shell'):
            header = section.find('div', class_='section-header')
            if header:
                h2 = header.find('h2')
                if h2 and '猜你喜欢' in h2.text:
                    for article in section.find_all('article', class_='video-card'):
                        item = self._parse_video_card(article)
                        if item:
                            videos.append(item)
                    break
        
        # 兜底：取页面中所有video-card前10个
        if not videos:
            for article in doc.find_all('article', class_='video-card')[:10]:
                item = self._parse_video_card(article)
                if item:
                    videos.append(item)
        
        return {'list': videos}
