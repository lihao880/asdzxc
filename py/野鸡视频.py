# -*- coding: utf-8 -*-
import re
import json
import base64
import urllib.parse
import posixpath
from bs4 import BeautifulSoup
import requests


class Spider:
    def __init__(self):
        self.host = "https://yejitv1004.biz"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/',
        }
        self.classes = [
            {"type_id": "6", "type_name": "网红主播"},
            {"type_id": "7", "type_name": "国产传媒"},
            {"type_id": "8", "type_name": "探花系列"},
            {"type_id": "9", "type_name": "人妻熟女"},
            {"type_id": "10", "type_name": "日本无码"},
            {"type_id": "11", "type_name": "美乳巨乳"},
            {"type_id": "12", "type_name": "强制侵犯"},
            {"type_id": "20", "type_name": "制服诱惑"},
            {"type_id": "21", "type_name": "国产自拍"},
            {"type_id": "14", "type_name": "风俗泡泡浴"},
            {"type_id": "15", "type_name": "家庭乱伦"},
            {"type_id": "16", "type_name": "AV解说"},
            {"type_id": "13", "type_name": "绝色佳人"},
            {"type_id": "22", "type_name": "少女萝莉"},
            {"type_id": "23", "type_name": "SM调教"},
            {"type_id": "24", "type_name": "绝顶潮吹"},
        ]
        self.filters = {
            "6": [], "7": [], "8": [], "9": [], "10": [],
            "11": [], "12": [], "20": [], "21": [], "14": [],
            "15": [], "16": [], "13": [], "22": [], "23": [], "24": [],
        }

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

    def _make_proxy_url(self, pic_url):
        if not pic_url:
            return ''
        encoded = base64.b64encode(pic_url.encode()).decode()
        return f'proxy://do=py&site=yeji&type=img&url={encoded}'

    def _m3u8_proxy_url(self, url):
        if not url:
            return ''
        url = url.replace('\\/', '/')
        return 'http://127.0.0.1:9978/proxy?do=py&url=' + urllib.parse.quote(str(url or ''), safe='')
    def _extract_vod_id(self, url):
        if not url:
            return ''
        m = re.search(r'/play/id/(\d+)', url)
        if m:
            return m.group(1)
        m = re.search(r'/vod/play/id/(\d+)', url)
        if m:
            return m.group(1)
        return ''

    def _parse_videos(self, items, limit=999):
        videos = []
        for li in items:
            a = li.find('a', class_='video-pic', href=True)
            if not a:
                continue
            href = a.get('href', '')
            vid = self._extract_vod_id(href)
            if not vid:
                continue

            title_tag = li.find('h5', class_='video-title')
            title = title_tag.text.strip() if title_tag else ''
            if not title:
                title_tag2 = li.find('div', class_='title')
                if title_tag2:
                    a2 = title_tag2.find('a')
                    if a2:
                        title = a2.get('title', '') or a2.text.strip()
            if not title:
                title = a.get('title', '')

            pic = ''
            style = a.get('style', '')
            m = re.search(r'background-image:url\\([^)]+\\)', style)
            if m:
                pic_url = m.group(0).replace('background-image:url(', '').replace(')', '').strip()
                if pic_url.startswith('\\'):
                    pic_url = pic_url[1:]
                pic = self.fix_url(pic_url)
            if not pic:
                img = li.find('img', class_='content-img')
                if img:
                    pic = img.get('src') or img.get('data-original', '')
                    pic = self.fix_url(pic)

            remark = ''
            note = li.find('span', class_='note text-bg-r')
            if note:
                remark = note.text.strip()
            if not remark:
                note2 = li.find('span', class_='note vip-tip')
                if note2:
                    remark = note2.text.strip()

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

    def _parse_player_data(self, html):
        pattern = r'var\s+player_aaaa\s*=\s*(\{[^;]+\});'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                url = data.get("url", "")
                if url and url.startswith("http"):
                    return {"url": url, "from": data.get("from", "")}
            except:
                pass
        pattern2 = r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"'
        match2 = re.search(pattern2, html)
        if match2:
            url = match2.group(1)
            if url.startswith("http"):
                return {"url": url, "from": ""}
            if url.startswith("/"):
                return {"url": self.host + url, "from": ""}
        pattern3 = r'https?://[^"\']+\.m3u8[^"\']*'
        match3 = re.search(pattern3, html)
        if match3:
            return {"url": match3.group(0), "from": ""}
        return {}

    def homeContent(self, filter=False):
        result = {'class': self.classes, 'filters': self.filters if filter else {}}
        html = self.get_html(self.host + '/')
        if html:
            doc = BeautifulSoup(html, 'html.parser')
            items = doc.find_all('div', class_='content-item')
            result['list'] = self._parse_videos(items, 15)
        else:
            result['list'] = []
        return result

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            result = self.categoryContent('6', 1, False, None)
            return {'list': result.get('list', [])[:15]}
        except Exception as e:
            print('homeVideoContent error:', e)
            return {'list': []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        url = f"{self.host}/index.php/vod/type/id/{tid}.html"
        if pg > 1:
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"

        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}

        doc = BeautifulSoup(html, 'html.parser')
        items = doc.find_all('li', class_='content-item')
        videos = self._parse_videos(items)

        pagecount = 1
        total = 0
        pagination = doc.find('ul', class_='pagination')
        if pagination:
            for a in pagination.find_all('a'):
                text = a.text.strip()
                if text.isdigit():
                    num = int(text)
                    if num > pagecount:
                        pagecount = num
                if '总共' in text:
                    m = re.search(r'总共(\d+)部', text)
                    if m:
                        total = int(m.group(1))
            last_a = pagination.find_all('a')[-1] if pagination.find_all('a') else None
            if last_a and '>>' in last_a.text:
                href = last_a.get('href', '')
                m = re.search(r'/page/(\d+)\.html', href)
                if m:
                    pagecount = int(m.group(1))

        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount if pagecount > 1 else 1,
            'limit': 20,
            'total': total if total > 0 else pagecount * 20
        }

    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        if isinstance(ids, list):
            vid = str(ids[0])
        else:
            vid = str(ids)
        url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        html = self.get_html(url)
        if not html:
            return {'list': []}

        doc = BeautifulSoup(html, 'html.parser')

        title = ''
        h3 = doc.find('h3')
        if h3:
            title = h3.text.strip()

        pic = ''
        player_div = doc.find('div', class_='dplayer-body')
        if player_div:
            img = player_div.find('img')
            if img:
                pic = img.get('src', '')
                pic = self.fix_url(pic)

        player_data = self._parse_player_data(html)

        play_from_list = []
        road_list = doc.find('div', class_='play-road-list')
        if road_list:
            for item in road_list.find_all('div', class_='item line'):
                a = item.find('a')
                if a:
                    name = a.text.strip()
                    play_from_list.append(name)

        play_from = '默认线路'
        play_url_str = ''

        if player_data and player_data.get('url'):
            play_url = player_data.get('url', '')
            if play_url:
                play_url_str = f'播放${play_url}'
                from_name = player_data.get('from', '默认线路')
                if from_name and from_name not in play_from_list:
                    play_from_list.append(from_name)
                play_from = from_name if from_name else '默认线路'

        if not play_url_str:
            iframe = doc.find('iframe', src=True)
            if iframe:
                src = iframe.get('src', '')
                if 'm3u8' in src:
                    m = re.search(r'url=([^&]+)', src)
                    if m:
                        play_url = urllib.parse.unquote(m.group(1))
                        play_url_str = f'播放${play_url}'

        if not play_url_str:
            play_url_str = f'播放${vid}'

        actor = ''
        info_row = doc.find('div', class_='info-content')
        if info_row:
            actor_span = info_row.find('span', class_='info-time')
            if actor_span:
                for a in actor_span.find_all('a'):
                    actor = a.text.strip()
                    break

        remark = ''
        info_row = doc.find('div', class_='info-content')
        if info_row:
            time_span = info_row.find('span', class_='info-time')
            if time_span:
                text = time_span.text.strip()
                m = re.search(r'(\d{2}-\d{2}-\d{2})', text)
                if m:
                    remark = m.group(1)

        if play_from_list and len(play_from_list) > 1:
            from_str = '$$$'.join(play_from_list)
            url_str = '$$$'.join([play_url_str] * len(play_from_list))
        else:
            from_str = play_from
            url_str = play_url_str

        data = {
            'vod_id': vid,
            'vod_name': title or '未知视频',
            'vod_pic': pic,
            'vod_actor': actor,
            'vod_remarks': remark,
            'vod_content': '',
            'vod_play_from': from_str,
            'vod_play_url': url_str,
        }
        return {'list': [data]}

    def searchContent(self, key, quick=False, pg='1'):
        if not key:
            return {'list': [], 'page': 1, 'pagecount': 1, 'total': 0}
        pg = int(pg) if pg else 1
        url = f"{self.host}/index.php/vod/search.html?wd={urllib.parse.quote(key)}"
        if pg > 1:
            url = f"{self.host}/index.php/vod/search.html?wd={urllib.parse.quote(key)}&page={pg}"

        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}

        doc = BeautifulSoup(html, 'html.parser')
        videos = []

        # 搜索页面使用 li.content-item
        items = doc.find_all('li', class_='content-item')
        if not items:
            # 尝试 div.content-item
            items = doc.find_all('div', class_='content-item')

        for li in items:
            a = li.find('a', class_='video-pic', href=True)
            if not a:
                continue
            href = a.get('href', '')
            # 搜索页面的链接可能缺少id参数，从href中提取
            vid = self._extract_vod_id(href)
            if not vid:
                # 尝试从链接中提取 sid 和 nid
                sid_match = re.search(r'sid/(\d+)', href)
                nid_match = re.search(r'nid/(\d+)', href)
                if sid_match and nid_match:
                    vid = nid_match.group(1)  # 使用 nid 作为 vid
                else:
                    continue

            title_tag = li.find('h5', class_='video-title')
            title = title_tag.text.strip() if title_tag else ''
            if not title:
                title_tag2 = li.find('div', class_='title')
                if title_tag2:
                    a2 = title_tag2.find('a')
                    if a2:
                        title = a2.get('title', '') or a2.text.strip()
            if not title:
                title = a.get('title', '')

            pic = ''
            style = a.get('style', '')
            m = re.search(r'background-image:url\\([^)]+\\)', style)
            if m:
                pic_url = m.group(0).replace('background-image:url(', '').replace(')', '').strip()
                if pic_url.startswith('\\'):
                    pic_url = pic_url[1:]
                pic = self.fix_url(pic_url)
            if not pic:
                img = li.find('img', class_='content-img')
                if img:
                    pic = img.get('src') or img.get('data-original', '')
                    pic = self.fix_url(pic)

            remark = ''
            note = li.find('span', class_='note text-bg-r')
            if note:
                remark = note.text.strip()

            if vid and title:
                videos.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })

        pagecount = 1
        pagination = doc.find('ul', class_='pagination')
        if pagination:
            for a in pagination.find_all('a'):
                text = a.text.strip()
                if text.isdigit():
                    num = int(text)
                    if num > pagecount:
                        pagecount = num
            last_a = pagination.find_all('a')[-1] if pagination.find_all('a') else None
            if last_a and '>>' in last_a.text:
                href = last_a.get('href', '')
                m = re.search(r'page=(\d+)', href)
                if m:
                    pagecount = int(m.group(1))

        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount if pagecount > 1 else 1,
            'total': pagecount * 20
        }
    def playerContent(self, flag, id, vipFlags=None):
        id = str(id) if id is not None else ''
        if not id:
            return {'parse': 1, 'url': ''}

        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/',
        }

        if id.startswith('http'):
            if id.endswith('.m3u8') or id.endswith('.mp4') or '.m3u8?' in id:
                return {'parse': 0, 'url': self._m3u8_proxy_url(id), 'header': headers}

        if id.isdigit():
            url = f"{self.host}/index.php/vod/play/id/{id}/sid/1/nid/1.html"
            html = self.get_html(url)
            if html:
                player_data = self._parse_player_data(html)
                if player_data and player_data.get('url'):
                    play_url = player_data.get('url', '')
                    if play_url.startswith('http'):
                        return {'parse': 0, 'url': self._m3u8_proxy_url(play_url), 'header': headers}

                doc = BeautifulSoup(html, 'html.parser')
                iframe = doc.find('iframe', src=True)
                if iframe:
                    src = iframe.get('src', '')
                    if 'm3u8' in src:
                        m = re.search(r'url=([^&]+)', src)
                        if m:
                            play_url = urllib.parse.unquote(m.group(1))
                            if play_url.startswith('http'):
                                return {'parse': 0, 'url': self._m3u8_proxy_url(play_url), 'header': headers}

        if id.isdigit():
            return {'parse': 1, 'url': f"{self.host}/index.php/vod/play/id/{id}/sid/1/nid/1.html", 'header': headers}
        return {'parse': 1, 'url': id, 'header': headers}

    def recommendContent(self, ids, pg='1'):
        if not ids:
            return {'list': []}
        if isinstance(ids, list):
            vid = str(ids[0])
        else:
            vid = str(ids)
        try:
            pg = int(pg) if pg else 1
            limit = 12
            url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            html = self.get_html(url)
            if not html:
                return {'list': []}
            tid = None
            m = re.search(r'/index\.php/vod/type/id/(\d+)\.html', html)
            if m:
                tid = m.group(1)
            if not tid:
                m2 = re.search(r'<a[^>]*href="[^"]*/vod/type/id/(\d+)\.html"[^>]*>\s*<span[^>]*>([^<]+)</span>', html)
                if m2:
                    tid = m2.group(1)
            if not tid:
                return {'list': []}
            result = self.categoryContent(tid, pg, False, None)
            items = result.get('list', [])
            items = [item for item in items if item.get('vod_id') != vid]
            if len(items) > limit:
                items = items[:limit]
            return {'list': items}
        except Exception as e:
            return {'list': []}

    def localProxy(self, params):
        try:
            if isinstance(params, dict):
                target = params.get('url', '') or params.get('source', '')
                proxy_type = params.get('type', '')
            else:
                target = str(params or '')
                proxy_type = ''

            if target.startswith('url='):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ''))

            # 图片代理
            if proxy_type == 'img' or (target and target.startswith('http') and not target.endswith('.m3u8') and '.m3u8?' not in target):
                try:
                    pic_url = target
                    resp = requests.get(pic_url, headers=self.headers, timeout=30)
                    if resp.status_code == 200:
                        content = resp.content
                        if content.startswith(b'\xff\xd8\xff'):
                            content_type = 'image/jpeg'
                        elif content.startswith(b'\x89PNG'):
                            content_type = 'image/png'
                        elif content.startswith(b'GIF8'):
                            content_type = 'image/gif'
                        else:
                            content_type = resp.headers.get('Content-Type', 'image/jpeg')
                        return [200, content_type, content]
                    else:
                        return [404, 'text/plain', b'Image not found']
                except Exception as e:
                    return [500, 'text/plain', f'Proxy error: {str(e)}'.encode()]

            # m3u8 代理 - 广告过滤
            if target and re.match(r'^https?://', target, re.I):
                resp = self.fetch(target, headers={'User-Agent': self.headers.get('User-Agent', '')}, timeout=20)
                if not resp:
                    return [502, 'text/plain', b'fetch failed']
                content = getattr(resp, 'content', b'') or b''
                if not content and hasattr(resp, 'text') and resp.text:
                    content = resp.text.encode('utf-8', errors='ignore')
                if not content:
                    return [502, 'text/plain', b'empty content']
                text = content.decode('utf-8', errors='ignore')
                if '#EXTM3U' not in text:
                    return [502, 'text/plain', b'invalid m3u8']
                cleaned = self._clean_m3u8(text, target)
                return [200, 'application/vnd.apple.mpegurl', cleaned.encode('utf-8')]

            return [404, 'text/plain', b'Not Found']

        except Exception as e:
            return [500, 'text/plain', f'localProxy error: {str(e)}'.encode()]

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
        return '野鸡视频'