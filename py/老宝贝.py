# -*- coding: utf-8 -*-
import re
import json
import base64
import urllib.parse
import posixpath
from bs4 import BeautifulSoup
import requests
import time


class Spider:
    def __init__(self):
        self.host = "https://aadd.lbb888.sbs"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/'
        }
        self.classes = [
            {"type_id": "b97362", "type_name": "无码专区"},
            {"type_id": "f515b6", "type_name": "抖音视频"},
            {"type_id": "d9a334", "type_name": "欧美无码"},
            {"type_id": "089884", "type_name": "美女主播"},
            {"type_id": "43db0a", "type_name": "麻豆传媒"},
            {"type_id": "794919", "type_name": "美乳巨乳"},
            {"type_id": "d91d92", "type_name": "韩国主播"},
            {"type_id": "5530e4", "type_name": "中文字幕"},
            {"type_id": "541e22", "type_name": "萝莉少女"},
            {"type_id": "1e09c1", "type_name": "女优明星"},
            {"type_id": "d03896", "type_name": "女同性爱"},
        ]
        self.filters = {}

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if not url:
            return ''
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def fetch(self, url, headers=None, timeout=15):
        try:
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

    def _extract_real_pic_url(self, url):
        if not url:
            return ''
        m = re.search(r'url=([^&]+)', url)
        if m:
            return urllib.parse.unquote(m.group(1))
        return url

    def _make_proxy_url(self, pic_url):
        if not pic_url:
            return ''
        real_url = self._extract_real_pic_url(pic_url)
        return real_url

    def _extract_vod_id(self, url):
        if not url:
            return ''
        m = re.search(r'/666/(\d+)\.html', url)
        if m:
            return m.group(1)
        return url

    def _parse_items(self, items, limit=999):
        videos = []
        seen_ids = set()
        for item in items:
            if item in seen_ids:
                continue
            seen_ids.add(item)
            a = item.find('a', class_=re.compile(r'gridmini-grid-post-thumbnail-link'))
            if not a:
                a = item.find('a', href=True)
            if not a:
                continue
            href = a.get('href', '')
            if '/666/' not in href:
                continue
            vid = self._extract_vod_id(href)
            if not vid:
                continue
            title_elem = item.find('h3', class_=re.compile(r'gridmini-grid-post-title'))
            if title_elem:
                title_a = title_elem.find('a')
                title = title_a.text.strip() if title_a else title_elem.text.strip()
            else:
                title = a.get('title', '') or a.text.strip()
            if not title:
                continue
            img = item.find('img', class_=re.compile(r'gridmini-grid-post-thumbnail-img'))
            pic = img.get('src') or img.get('data-src', '') if img else ''
            if pic:
                pic = self._make_proxy_url(pic)
                if not pic.startswith('http'):
                    pic = self.fix_url(pic)
            remark = ''
            cat_elem = item.find('div', class_=re.compile(r'gridmini-grid-post-categories'))
            if cat_elem:
                cat_a = cat_elem.find('a')
                if cat_a:
                    remark = cat_a.text.strip()
            if not remark:
                overlay = item.find('div', class_=re.compile(r'gridmini-thumbnail-overlay'))
                if overlay:
                    cat_div = overlay.find('div', class_=re.compile(r'gridmini-grid-post-categories'))
                    if cat_div:
                        cat_a = cat_div.find('a')
                        if cat_a:
                            remark = cat_a.text.strip()
            videos.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remark
            })
            if len(videos) >= limit:
                break
        unique_videos = []
        seen_vids = set()
        for v in videos:
            if v['vod_id'] not in seen_vids:
                seen_vids.add(v['vod_id'])
                unique_videos.append(v)
        return unique_videos

    def homeContent(self, filter=False):
        return {'class': self.classes, 'filters': self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            html = self.get_html(self.host + '/')
            if not html:
                return {'list': []}
            doc = BeautifulSoup(html, 'html.parser')
            items = doc.find_all('div', class_=re.compile(r'gridmini-grid-post'))
            videos = self._parse_items(items, 15)
            return {'list': videos}
        except Exception as e:
            print('homeVideoContent error:', e)
            return {'list': []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        url = self.host + '/' + tid
        if pg > 1:
            url += '/page/' + str(pg)
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        doc = BeautifulSoup(html, 'html.parser')
        items = doc.find_all('div', class_=re.compile(r'gridmini-grid-post'))
        videos = self._parse_items(items)
        pagecount = 1
        pagination = doc.find('nav', class_=re.compile(r'pagination'))
        if pagination:
            for a in pagination.find_all('a', class_=re.compile(r'page-numbers')):
                if a.text.strip().isdigit():
                    num = int(a.text.strip())
                    if num > pagecount:
                        pagecount = num
        return {'list': videos, 'page': pg, 'pagecount': pagecount, 'limit': 20, 'total': pagecount * 20}

    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        vid = ids[0]
        url = self.host + '/666/' + vid + '.html'
        html = self.get_html(url)
        if not html:
            return {'list': []}
        doc = BeautifulSoup(html, 'html.parser')

        title = ''
        article = doc.find('article', id=re.compile(r'post-\d+'))
        if article:
            h1 = article.find('h1', class_=re.compile(r'entry-title|post-title'))
            if h1:
                a = h1.find('a')
                title = a.text.strip() if a else h1.text.strip()
        if not title:
            h1 = doc.find('h1', class_=re.compile(r'entry-title|post-title'))
            if h1:
                a = h1.find('a')
                title = a.text.strip() if a else h1.text.strip()

        pic = ''
        img = doc.find('img', class_=re.compile(r'gridmini-grid-post-thumbnail-img'))
        if img:
            pic = img.get('src') or img.get('data-src', '')
            if pic:
                pic = self._make_proxy_url(pic)
                if not pic.startswith('http'):
                    pic = self.fix_url(pic)

        content = ''
        if article:
            content_div = article.find('div', class_=re.compile(r'entry-content'))
        else:
            content_div = doc.find('div', class_=re.compile(r'entry-content'))
        if content_div:
            content = content_div.get_text(separator=' ', strip=True)

        play_url = ''
        iframe = doc.find('iframe')
        if iframe:
            src = iframe.get('src', '')
            if src:
                m = re.search(r'url=([^&]+)', src)
                if m:
                    play_url = urllib.parse.unquote(m.group(1))
                else:
                    play_url = self.fix_url(src)
        if not play_url:
            m = re.search(r'videoSrc\s*=\s*["\']([^"\']+)["\']', html)
            if m:
                play_url = m.group(1)
            if not play_url:
                m = re.search(r'["\']([^"\']+\.m3u8)["\']', html)
                if m:
                    play_url = m.group(1)

        if play_url:
            if play_url.startswith('/'):
                play_url = self.host + play_url
            play_from = '播放'
            play_url_str = '播放$' + play_url
        else:
            play_from = '播放'
            play_url_str = ''

        tags = []
        if article:
            tag_links = article.find_all('a', rel='tag')
        else:
            tag_links = doc.find_all('a', rel='tag')
        for a in tag_links:
            tags.append(a.text.strip())

        data = {
            'vod_id': vid,
            'vod_name': title or '未知标题',
            'vod_pic': pic,
            'vod_content': content[:500] if content else '',
            'vod_tag': '、'.join(tags) if tags else '',
            'vod_play_from': play_from,
            'vod_play_url': play_url_str,
        }
        return {'list': [data]}

    def searchContent(self, key, quick=False, pg='1'):
        if not key:
            return {'list': [], 'page': 1, 'pagecount': 1, 'total': 0}
        pg = int(pg) if pg else 1
        encoded_key = urllib.parse.quote(key)
        url = self.host + '/?s=' + encoded_key
        if pg > 1:
            url = self.host + '/page/' + str(pg) + '/?s=' + encoded_key
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        doc = BeautifulSoup(html, 'html.parser')
        if '没有找到' in html or '无结果' in html or '暂无数据' in html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        items = doc.find_all('div', class_=re.compile(r'gridmini-grid-post'))
        videos = self._parse_items(items)
        pagecount = 1
        pagination = doc.find('nav', class_=re.compile(r'pagination'))
        if pagination:
            for a in pagination.find_all('a', class_=re.compile(r'page-numbers')):
                if a.text.strip().isdigit():
                    num = int(a.text.strip())
                    if num > pagecount:
                        pagecount = num
        return {'list': videos, 'page': pg, 'pagecount': pagecount, 'total': pagecount * 20}

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {'parse': 1, 'url': ''}

        # 替换转义符
        id = id.replace("\\/", "/")

        # 如果已经是m3u8/mp4直链，走代理清洗广告
        if id.startswith('http'):
            if id.endswith('.m3u8') or id.endswith('.mp4') or '.m3u8?' in id:
                headers = {
                    'User-Agent': self.headers['User-Agent'],
                    'Referer': self.host + '/',
                }
                # m3u8 走代理清洗广告
                if '.m3u8' in id:
                    return {'parse': 0, 'url': self._m3u8_proxy_url(id), 'header': headers}
                return {'parse': 0, 'url': id, 'header': headers}

        # 尝试从播放页解析
        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/',
        }
        if id.startswith('http'):
            html = self.get_html(id, headers)
            if html:
                m = re.search(r'url=([^&"\']+)', html)
                if m:
                    url = urllib.parse.unquote(m.group(1))
                    if url.endswith('.m3u8') or url.endswith('.mp4'):
                        if '.m3u8' in url:
                            return {'parse': 0, 'url': self._m3u8_proxy_url(url), 'header': headers}
                        return {'parse': 0, 'url': url, 'header': headers}
                m = re.search(r'videoSrc\s*=\s*["\']([^"\']+)["\']', html)
                if m:
                    url = m.group(1)
                    if url.startswith('/'):
                        url = self.host + url
                    if url.endswith('.m3u8') or url.endswith('.mp4'):
                        if '.m3u8' in url:
                            return {'parse': 0, 'url': self._m3u8_proxy_url(url), 'header': headers}
                        return {'parse': 0, 'url': url, 'header': headers}
                m = re.search(r'["\']([^"\']+\.m3u8)["\']', html)
                if m:
                    url = m.group(1)
                    if url.startswith('/'):
                        url = self.host + url
                    return {'parse': 0, 'url': self._m3u8_proxy_url(url), 'header': headers}

        return {'parse': 1, 'url': id, 'header': headers}

    def localProxy(self, params):
        # 兼容 url 和 source 两种参数名
        if isinstance(params, dict):
            target = params.get('url', '') or params.get('source', '')
            req_type = params.get('type', '') or params.get('source_type', '')
        else:
            target = str(params or '')
            req_type = ''

        # 处理图片代理
        if req_type == 'img' and target:
            try:
                pic_url = base64.b64decode(target).decode('utf-8', errors='ignore')
                resp = requests.get(pic_url, headers=self.headers, timeout=30)
                if resp.status_code == 200:
                    content = resp.content
                    if len(content) > 4:
                        if content.startswith(b'\xff\xd8\xff'):
                            return [200, 'image/jpeg', content]
                        elif content.startswith(b'\x89PNG'):
                            return [200, 'image/png', content]
                        elif content.startswith(b'GIF8'):
                            return [200, 'image/gif', content]
                        elif content.startswith(b'RIFF') and content[8:12] == b'WEBP':
                            return [200, 'image/webp', content]
                    content_type = resp.headers.get('Content-Type', 'image/jpeg')
                    if 'text/html' in content_type:
                        return [404, 'text/plain', b'Invalid image response']
                    return [200, content_type, content]
                else:
                    return [404, 'text/plain', f'Image not found: {resp.status_code}'.encode()]
            except Exception as e:
                print('localProxy image error:', e)
                return [500, 'text/plain', f'Proxy error: {str(e)}'.encode()]

        # 处理 m3u8 代理（广告过滤）
        if target:
            # 剥离前缀 url=
            if target.startswith('url='):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ''))

            if not target or not re.match(r'^https?://', target, re.I):
                return [400, 'text/plain', b'invalid url']

            try:
                # 获取 m3u8 内容
                resp = self.fetch(target, headers={'User-Agent': self.headers.get('User-Agent', '')}, timeout=20)
                if not resp or resp.status_code != 200:
                    return [502, 'text/plain', b'fetch m3u8 failed']

                content = getattr(resp, 'content', b'') or b''
                if not content and hasattr(resp, 'text') and resp.text:
                    content = resp.text.encode('utf-8', errors='ignore')

                if not content:
                    return [502, 'text/plain', b'empty content']

                text = content.decode('utf-8', errors='ignore')
                if '#EXTM3U' not in text:
                    # 不是 m3u8，直接返回原内容
                    return [200, 'application/vnd.apple.mpegurl', content]

                # 清洗广告
                cleaned = self._clean_m3u8(text, target)
                return [200, 'application/vnd.apple.mpegurl', cleaned.encode('utf-8')]

            except Exception as e:
                error_msg = f'localProxy m3u8 error: {str(e)}'.encode('utf-8', errors='ignore')
                return [500, 'text/plain', error_msg]

        return [404, 'text/plain', b'Not Found']

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片，保留正片"""
        lines = [line.strip() for line in str(text or '').replace('\r', '').split('\n') if line.strip()]
        if not lines:
            return '#EXTM3U\n'

        # 处理多码率 Master Playlist
        if any(line.startswith('#EXT-X-STREAM-INF') for line in lines):
            out = []
            for line in lines:
                if line.startswith('#'):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if '.m3u8' in child.lower() else child)
            return '\n'.join(out) + '\n'

        parsed = urllib.parse.urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith('/'):
            source_dir += '/'

        # 从 #EXT-X-KEY 提取正片目录（更准确）
        main_dir = source_dir
        for line in lines:
            if line.startswith('#EXT-X-KEY') and 'URI=' in line:
                uri_match = re.search(r'URI="([^"]+)"', line)
                if uri_match:
                    key_path = uri_match.group(1)
                    if not key_path.startswith('http'):
                        key_dir = posixpath.dirname(key_path)
                        if key_dir and key_dir != '/':
                            main_dir = key_dir + '/'
                            break

        segments = []
        pending = []

        for line in lines:
            if line.startswith('#EXTINF'):
                pending = [line]
                continue
            if pending and line.startswith('#'):
                pending.append(line)
                continue
            if pending:
                media_url = urllib.parse.urljoin(source_url, line)
                media_parsed = urllib.parse.urlparse(media_url)

                # 过滤逻辑：判断分片路径是否以正片目录开头
                is_ad = not media_parsed.path.startswith(main_dir)

                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue

            if not line.startswith('#'):
                segments.append(urllib.parse.urljoin(source_url, line))
            else:
                segments.append(line)

        # 二次清洗：去除孤立/连续的 #EXT-X-DISCONTINUITY 和 KEY:METHOD=NONE
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ('#EXT-X-KEY:METHOD=NONE', '#EXT-X-DISCONTINUITY'):
                if not out or out[-1] in ('#EXT-X-DISCONTINUITY', '#EXT-X-KEY:METHOD=NONE'):
                    continue
            out.append(line)

        # 清理尾部多余的标记
        while len(out) > 1 and out[-1] in ('#EXT-X-DISCONTINUITY', '#EXT-X-KEY:METHOD=NONE'):
            out.pop()

        return '\n'.join(out) + '\n'

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写 m3u8 标签中的 URI（补全绝对地址）"""
        if line.startswith('#EXT-X-KEY') or line.startswith('#EXT-X-MAP'):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(('http://', 'https://')):
                    return 'URI="' + uri + '"'
                return 'URI="' + urllib.parse.urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)

        if line and not line.startswith('#'):
            if line.startswith(('http://', 'https://')):
                return line
            return urllib.parse.urljoin(source_url, line)

        return line

    def init(self, extend=''):
        pass

    def destroy(self):
        pass

    def getDependence(self):
        return ['requests', 'bs4']

    def getName(self):
        return '老宝贝'