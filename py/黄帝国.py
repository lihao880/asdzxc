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
        self.host = "https://hdg.91tk.lat"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/'
        }
        self.classes = [
            {"type_id": "国产精品", "type_name": "国产精品"},
            {"type_id": "日本女优", "type_name": "日本女优"},
            {"type_id": "制服诱惑", "type_name": "制服诱惑"},
            {"type_id": "巨乳美乳", "type_name": "巨乳美乳"},
            {"type_id": "国产传媒", "type_name": "国产传媒"},
            {"type_id": "国产乱伦", "type_name": "国产乱伦"},
            {"type_id": "自拍偷拍", "type_name": "自拍偷拍"},
            {"type_id": "主播直播", "type_name": "主播直播"},
            {"type_id": "亚洲无码", "type_name": "亚洲无码"},
            {"type_id": "日本商", "type_name": "日本商"},
            {"type_id": "国产SM", "type_name": "国产SM"},
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

    def _make_pic_url(self, pic_url):
        if not pic_url:
            return ''
        real_url = self._extract_real_pic_url(pic_url)
        return real_url

    def _extract_vod_id(self, url):
        if not url:
            return ''
        m = re.search(r'/p/(\d+)\.htm', url)
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
            # 优先从 h5 中找链接
            a = None
            h5 = item.find('h5')
            if h5:
                a = h5.find('a', href=True)
            if not a:
                # 从 read-more 找链接
                read_more = item.find('div', class_='read-more')
                if read_more:
                    a = read_more.find('a', href=True)
            if not a:
                # 兜底：找任意 a 标签
                a = item.find('a', href=True)
            if not a:
                continue
            href = a.get('href', '')
            if '/p/' not in href:
                continue
            vid = self._extract_vod_id(href)
            if not vid:
                continue
            # 标题
            title = ''
            if h5:
                title_a = h5.find('a')
                if title_a:
                    title = title_a.text.strip()
                else:
                    title = h5.text.strip()
            if not title:
                title = a.get('title', '') or a.text.strip()
            if not title:
                continue
            # 封面
            img = item.find('img')
            pic = img.get('src') or img.get('data-src', '') if img else ''
            if pic:
                pic = self._make_pic_url(pic)
                if not pic.startswith('http'):
                    pic = self.fix_url(pic)
            # 备注（分类）
            remark = ''
            cat_links = item.find_all('a', rel='category tag')
            if cat_links:
                remark = '、'.join([c.text.strip() for c in cat_links])
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
            items = doc.find_all('article', class_=re.compile(r'blog-item'))
            videos = self._parse_items(items, 15)
            return {'list': videos}
        except Exception as e:
            print('homeVideoContent error:', e)
            return {'list': []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        # 分类名需要URL编码（中文）
        encoded_tid = urllib.parse.quote(tid)
        url = self.host + '/' + encoded_tid
        if pg > 1:
            url = self.host + '/page/' + str(pg)
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        doc = BeautifulSoup(html, 'html.parser')
        items = doc.find_all('article', class_=re.compile(r'blog-item'))
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
        url = self.host + '/p/' + vid + '.htm'
        html = self.get_html(url)
        if not html:
            return {'list': []}
        doc = BeautifulSoup(html, 'html.parser')

        # 标题 - 多种方式提取
        title = ''
        # 1. 从 blog-detail 中的 h4 提取（该站实际结构）
        blog_detail = doc.find('div', class_='blog-detail')
        if blog_detail:
            h4 = blog_detail.find('h4', class_='text-capitalize')
            if h4:
                title = h4.text.strip()
        if not title:
            # 2. 从 entry-title 提取
            title_elem = doc.find('h1', class_=re.compile(r'entry-title'))
            if title_elem:
                title = title_elem.text.strip()
        if not title:
            # 3. 从 article 内的 h1
            article = doc.find('article')
            if article:
                h1 = article.find('h1')
                if h1:
                    title = h1.text.strip()
        if not title:
            # 4. 从 post-title 提取
            title_elem = doc.find('h1', class_=re.compile(r'post-title'))
            if title_elem:
                title = title_elem.text.strip()
        if not title:
            # 5. 从 og:title 提取
            meta_title = doc.find('meta', property='og:title')
            if meta_title:
                title = meta_title.get('content', '').strip()
        if not title or title == '黄帝国':
            # 6. 从任意 h1 提取（排除站点标题）
            for h1 in doc.find_all('h1'):
                h1_text = h1.text.strip()
                if h1_text and h1_text != '黄帝国' and not h1.find('a'):
                    title = h1_text
                    break

        # 封面
        pic = ''
        img = doc.find('img', class_=re.compile(r'wp-post-image'))
        if img:
            pic = img.get('src') or img.get('data-src', '')
            if pic:
                pic = self._make_pic_url(pic)
                if not pic.startswith('http'):
                    pic = self.fix_url(pic)

        # 内容
        content = ''
        if blog_detail:
            # 提取内容（排除iframe和标题）
            for iframe in blog_detail.find_all('iframe'):
                iframe.decompose()
            for h4_tag in blog_detail.find_all('h4'):
                h4_tag.decompose()
            content = blog_detail.get_text(separator=' ', strip=True)

        if not content:
            content_div = doc.find('div', class_=re.compile(r'entry-content'))
            if content_div:
                content = content_div.get_text(separator=' ', strip=True)

        # 播放地址
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
            video = doc.find('video')
            if video:
                src = video.get('src', '')
                if src:
                    play_url = self.fix_url(src)
        if not play_url:
            m = re.search(r'videoSrc\s*=\s*["\']([^"\']+)["\']', html)
            if m:
                play_url = m.group(1)
        if not play_url:
            m = re.search(r'["\']([^"\']+\.m3u8)["\']', html)
            if m:
                play_url = m.group(1)
        if not play_url:
            m = re.search(r'url\s*:\s*["\']([^"\']+\.m3u8)["\']', html)
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

        # 分类标签
        tags = []
        cat_links = doc.find_all('a', rel='category tag')
        for a in cat_links:
            tags.append(a.text.strip())
        # 也尝试从 post-tags 提取
        post_tags = doc.find('div', class_='post-tags')
        if post_tags:
            for a in post_tags.find_all('a', rel='tag'):
                tag_text = a.text.strip()
                if tag_text and tag_text not in tags:
                    tags.append(tag_text)

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
        items = doc.find_all('article', class_=re.compile(r'blog-item'))
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
        id = id.replace("\\/", "/")

        # 如果是 /tt/t.php 跳转链接，直接解析真实m3u8
        if '/tt/t.php' in id:
            headers = {
                'User-Agent': self.headers['User-Agent'],
                'Referer': self.host + '/',
            }
            # 提取url参数
            m = re.search(r'url=([^&]+)', id)
            if m:
                real_url = urllib.parse.unquote(m.group(1))
                if real_url.endswith('.m3u8') or '.m3u8?' in real_url:
                    return {'parse': 0, 'url': self._m3u8_proxy_url(real_url), 'header': headers}
                # 如果还不是m3u8，尝试请求页面
                html = self.get_html(id, headers)
                if html:
                    # 尝试从iframe或script中提取
                    m2 = re.search(r'url=([^&"\']+)', html)
                    if m2:
                        final_url = urllib.parse.unquote(m2.group(1))
                        if final_url.endswith('.m3u8') or '.m3u8?' in final_url:
                            return {'parse': 0, 'url': self._m3u8_proxy_url(final_url), 'header': headers}
                    m2 = re.search(r'videoSrc\s*=\s*["\']([^"\']+)["\']', html)
                    if m2:
                        final_url = m2.group(1)
                        if final_url.endswith('.m3u8') or '.m3u8?' in final_url:
                            return {'parse': 0, 'url': self._m3u8_proxy_url(final_url), 'header': headers}
                    m2 = re.search(r'["\']([^"\']+\.m3u8)["\']', html)
                    if m2:
                        final_url = m2.group(1)
                        return {'parse': 0, 'url': self._m3u8_proxy_url(final_url), 'header': headers}

        # 如果已经是m3u8/mp4直链
        if id.startswith('http'):
            if id.endswith('.m3u8') or id.endswith('.mp4') or '.m3u8?' in id:
                headers = {
                    'User-Agent': self.headers['User-Agent'],
                    'Referer': self.host + '/',
                }
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
        if isinstance(params, dict):
            target = params.get('url', '') or params.get('source', '')
            req_type = params.get('type', '') or params.get('source_type', '')
        else:
            target = str(params or '')
            req_type = ''

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

        if target:
            if target.startswith('url='):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ''))
            if not target or not re.match(r'^https?://', target, re.I):
                return [400, 'text/plain', b'invalid url']
            try:
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
                    return [200, 'application/vnd.apple.mpegurl', content]
                cleaned = self._clean_m3u8(text, target)
                return [200, 'application/vnd.apple.mpegurl', cleaned.encode('utf-8')]
            except Exception as e:
                error_msg = f'localProxy m3u8 error: {str(e)}'.encode('utf-8', errors='ignore')
                return [500, 'text/plain', error_msg]
        return [404, 'text/plain', b'Not Found']

    def _clean_m3u8(self, text, source_url):
        lines = [line.strip() for line in str(text or '').replace('\r', '').split('\n') if line.strip()]
        if not lines:
            return '#EXTM3U\n'
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
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ('#EXT-X-KEY:METHOD=NONE', '#EXT-X-DISCONTINUITY'):
                if not out or out[-1] in ('#EXT-X-DISCONTINUITY', '#EXT-X-KEY:METHOD=NONE'):
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in ('#EXT-X-DISCONTINUITY', '#EXT-X-KEY:METHOD=NONE'):
            out.pop()
        return '\n'.join(out) + '\n'

    def _rewrite_m3u8_tag(self, line, source_url):
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
        return '黄帝国'