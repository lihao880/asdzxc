# -*- coding: utf-8 -*-
# 站点：御女阁
# 域名：https://rum.yng6.lol
# 类型：MacCMS HTML影视站

import re
import json
import urllib.parse
import base64
from bs4 import BeautifulSoup

class Spider:
    def __init__(self):
        self.host = "https://rum.yng6.lol"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/',
        }
        self.classes = [
            {"type_id": "20", "type_name": "熟母少妇"},
            {"type_id": "21", "type_name": "网红直播"},
            {"type_id": "22", "type_name": "自拍偷拍"},
            {"type_id": "23", "type_name": "强奸乱伦"},
            {"type_id": "24", "type_name": "高清国产"},
            {"type_id": "25", "type_name": "韩国专区"},
            {"type_id": "26", "type_name": "日本有码"},
            {"type_id": "27", "type_name": "日本无码"},
            {"type_id": "28", "type_name": "欧美情色"},
            {"type_id": "29", "type_name": "动漫卡通"},
            {"type_id": "30", "type_name": "三级伦理"},
        ]
        self.filters = {}

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

    def _extract_vod_id(self, url):
        if not url:
            return ''
        m = re.search(r'/(\d+)\.html', url)
        if m:
            return m.group(1)
        return url

    def _parse_video_items(self, items, limit=999):
        videos = []
        for item in items:
            a = item.find('a', href=True)
            if not a:
                continue
            href = a.get('href', '')
            if not href or '.html' not in href:
                continue
            vid = self._extract_vod_id(href)
            if not vid:
                continue

            title = ''
            title_tag = item.find('h3', class_='heading-3')
            if title_tag:
                title = title_tag.text.strip()
            if not title:
                title = a.get('title', '') or a.text.strip()

            pic = ''
            img = item.find('img')
            if img:
                pic = img.get('data-original') or img.get('src', '')
                pic = self.fix_url(pic)

            remark = ''
            remark_tag = item.find('div', class_='btn-f')
            if remark_tag:
                remark = remark_tag.text.strip()
            if not remark:
                span = item.find('span', class_='btn-l')
                if span:
                    remark = span.text.strip()

            if vid and title:
                videos.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })
                if len(videos) >= limit:
                    break
        return videos

    def _parse_videos(self, html, limit=20):
        doc = BeautifulSoup(html, 'html.parser')
        items = doc.find_all('div', class_='feature-post')
        return self._parse_video_items(items, limit)

    def getName(self):
        return '御女阁'

    def getDependence(self):
        return ['requests', 'bs4']

    def init(self, extend=''):
        pass

    def homeContent(self, filter=False):
        return {
            'class': self.classes,
            'filters': self.filters if filter else {}
        }

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            html = self.get_html(self.host + '/cn/home/web/')
            if html:
                videos = self._parse_videos(html, 15)
                return {'list': videos}
            return {'list': []}
        except Exception as e:
            print('homeVideoContent error:', e)
            return {'list': []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        url = self.host + '/vodtype/' + str(tid) + '.html'
        if pg > 1:
            url += '?page=' + str(pg)
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        videos = self._parse_videos(html, 20)
        pagecount = 999
        doc = BeautifulSoup(html, 'html.parser')
        pagination = doc.find('div', class_='pagination')
        if pagination:
            for a in pagination.find_all('a'):
                if a.text.strip().isdigit():
                    num = int(a.text.strip())
                    if num > pagecount:
                        pagecount = num
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 20,
            'total': pagecount * 20
        }

    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        vid = ids[0]
        if not vid:
            return {'list': []}
        url = self.host + '/' + str(vid) + '.html'
        html = self.get_html(url)
        if not html:
            return {'list': []}
        doc = BeautifulSoup(html, 'html.parser')

        title = ''
        title_tag = doc.find('h1', class_='heading-1')
        if title_tag:
            title = title_tag.text.strip()
        if not title:
            title_tag = doc.find('h1')
            if title_tag:
                title = title_tag.text.strip()

        play_url = ''
        match = re.search(r"const\s+rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html)
        if match:
            play_url = match.group(1)
        if not play_url:
            match = re.search(r"rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html)
            if match:
                play_url = match.group(1)
        if play_url:
            play_url = self.fix_url(play_url)

        pic = ''
        img = doc.find('img', class_='lazy')
        if img:
            pic = img.get('data-original') or img.get('src', '')
            pic = self.fix_url(pic)

        if play_url:
            vod_play_from = '在线播放'
            vod_play_url = '播放$' + play_url
        else:
            vod_play_from = ''
            vod_play_url = ''

        data = {
            'vod_id': vid,
            'vod_name': title or '未知标题',
            'vod_pic': pic,
            'vod_content': '',
            'vod_play_from': vod_play_from,
            'vod_play_url': vod_play_url,
        }
        return {'list': [data]}

    def searchContent(self, key, quick=False, pg='1'):
        if not key:
            return {'list': [], 'page': 1}
        pg = int(pg) if pg else 1
        url = self.host + '/s/index.html?wd=' + urllib.parse.quote(key)
        if pg > 1:
            url += '&page=' + str(pg)
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg}
        videos = self._parse_videos(html, 20)
        return {'list': videos, 'page': pg}

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {'parse': 1, 'url': ''}
        
        if '$' in id:
            parts = id.split('$', 1)
            if len(parts) == 2 and parts[1].startswith('http'):
                id = parts[1]
        
        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/',
        }
        
        if id.startswith('http') and (id.endswith('.m3u8') or '.m3u8?' in id):
            proxy_url = 'http://127.0.0.1:9978/proxy?do=py&url=' + urllib.parse.quote(id, safe='')
            return {'parse': 0, 'url': proxy_url, 'header': headers}
        
        if id.startswith('http') and id.endswith('.mp4'):
            return {'parse': 0, 'url': id, 'header': headers}
        
        if id.startswith('http'):
            html = self.get_html(id, headers)
            if html:
                match = re.search(r"const\s+rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html)
                if match:
                    url = self.fix_url(match.group(1))
                    if url and (url.endswith('.m3u8') or '.m3u8?' in url):
                        proxy_url = 'http://127.0.0.1:9978/proxy?do=py&url=' + urllib.parse.quote(url, safe='')
                        return {'parse': 0, 'url': proxy_url, 'header': headers}
                    if url and url.endswith('.mp4'):
                        return {'parse': 0, 'url': url, 'header': headers}
        
        return {'parse': 1, 'url': id, 'header': headers}

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            resp = self.fetch(target, headers=self.headers, timeout=15)
            if not resp:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")

            if not content:
                return [502, "text/plain", b"empty content"]

            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]

    def _clean_m3u8(self, text, source_url):
        """清洗m3u8 - 过滤广告分片（参考wangshi_ribao实现）"""
        import posixpath
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 处理多码率 Master Playlist
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    if child and (child.endswith('.m3u8') or '.m3u8?' in child):
                        child = 'http://127.0.0.1:9978/proxy?do=py&url=' + urllib.parse.quote(child, safe='')
                    out.append(child)
            return "\n".join(out) + "\n"

        parsed = urllib.parse.urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

        # 从 #EXT-X-KEY 提取正片目录
        main_dir = source_dir
        for line in lines:
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                uri_match = re.search(r'URI="([^"]+)"', line)
                if uri_match:
                    key_path = uri_match.group(1)
                    if not key_path.startswith("http"):
                        key_dir = posixpath.dirname(key_path)
                        if key_dir and key_dir != "/":
                            main_dir = key_dir + "/"
                            break

        segments = []
        pending = []

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
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

            if not line.startswith("#"):
                segments.append(urllib.parse.urljoin(source_url, line))
            else:
                segments.append(line)

        # 二次清洗：移除所有 #EXT-X-DISCONTINUITY 标记
        # 这些标记会导致播放器时间轴重置，造成总时长计算异常
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                continue
            out.append(line)

        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urllib.parse.urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)

        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urllib.parse.urljoin(source_url, line)

        return line

    def _fix_url(self, url, base_url):
        if not url:
            return url
        url = url.strip()
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            import re
            match = re.match(r'(https?://[^/]+)', base_url)
            if match:
                return match.group(1) + url
            return self.host + url
        if base_url.endswith('/'):
            return base_url + url
        else:
            return base_url.rsplit('/', 1)[0] + '/' + url

    def recommendContent(self, ids, pg):
        if not ids:
            return {'list': []}
        vid = ids[0]
        url = self.host + '/' + str(vid) + '.html'
        html = self.get_html(url)
        if not html:
            return {'list': []}
        doc = BeautifulSoup(html, 'html.parser')
        videos = []
        section = doc.find('h2', string=re.compile(r'猜你喜欢'))
        if section:
            parent = section.find_parent('div')
            if parent:
                items = parent.find_all('div', class_='feature-post')
                videos = self._parse_video_items(items, 12)
        return {'list': videos}

    def destroy(self):
        pass