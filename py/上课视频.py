# -*- coding: utf-8 -*-
import re
import json
import base64
import urllib.parse
from bs4 import BeautifulSoup
import requests
import time
import posixpath

class Spider:
    def __init__(self):
        self.host = "https://www.shangke9.shop"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/',
        }
        self.classes = [
            {"type_id": "20", "type_name": "视频一区"},
            {"type_id": "21", "type_name": "国产自拍"},
            {"type_id": "22", "type_name": "日韩无码"},
            {"type_id": "23", "type_name": "中文字幕"},
            {"type_id": "24", "type_name": "欧美极品"},
            {"type_id": "25", "type_name": "极骚萝莉"},
            {"type_id": "26", "type_name": "童颜巨乳"},
            {"type_id": "27", "type_name": "绝美少女"},
            {"type_id": "28", "type_name": "强奸乱伦"},
            {"type_id": "29", "type_name": "激情口交"},
            {"type_id": "30", "type_name": "精品视频"},
            {"type_id": "33", "type_name": "视频二区"},
            {"type_id": "34", "type_name": "国产精品"},
            {"type_id": "35", "type_name": "绿帽淫妻"},
            {"type_id": "36", "type_name": "国产探花"},
            {"type_id": "37", "type_name": "国产乱伦"},
            {"type_id": "38", "type_name": "美女主播"},
            {"type_id": "39", "type_name": "明星淫梦"},
            {"type_id": "40", "type_name": "高清无码"},
            {"type_id": "41", "type_name": "麻豆传媒"},
            {"type_id": "42", "type_name": "网曝事件"},
        ]
        self.filters = {}

    def getName(self):
        return "上课视频"

    def getDependence(self):
        return ['requests', 'bs4']

    def init(self, extend=""):
        pass

    def destroy(self):
        pass

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
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

    def _extract_vod_id(self, url):
        if not url:
            return ''
        m = re.search(r'/detail/id/(\d+)\.html', url)
        if m:
            return m.group(1)
        m = re.search(r'/play/id/(\d+)', url)
        if m:
            return m.group(1)
        return url

    def _extract_video_items(self, items, limit=999):
        videos = []
        for li in items:
            a = li.find('a', href=True)
            if not a:
                continue
            href = a.get('href', '')
            if '/detail/id/' not in href:
                continue
            vid = self._extract_vod_id(href)
            title = a.get('title', '') or a.text.strip()
            if not title:
                title = a.text.strip()
            if '更多>>' in title or '首页' in title:
                continue
            img = li.find('img')
            pic = img.get('src') or img.get('data-src', '') if img else ''
            pic = self.fix_url(pic)
            remark = ''
            span = li.find('span')
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

    def homeContent(self, filter=False):
        result = {'class': self.classes, 'filters': self.filters if filter else {}}
        html = self.get_html(self.host + '/')
        if html:
            doc = BeautifulSoup(html, 'html.parser')
            items = doc.select('div.pic ul li')
            videos = self._extract_video_items(items, 24)
            result['list'] = videos
        else:
            result['list'] = []
        return result

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            result = self.homeContent(False)
            return {'list': result.get('list', [])[:15]}
        except Exception as e:
            print('homeVideoContent error:', e)
            return {'list': []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        if pg == 1:
            url = f"{self.host}/index.php/vod/type/id/{tid}.html"
        else:
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        doc = BeautifulSoup(html, 'html.parser')
        items = doc.select('div.pic ul li')
        videos = self._extract_video_items(items)
        pagecount = 1
        total = 0
        pagination = doc.find('div', class_=re.compile(r'page|pagination'))
        if pagination:
            for a in pagination.find_all('a'):
                if a.text.strip().isdigit():
                    num = int(a.text.strip())
                    if num > pagecount:
                        pagecount = num
        text = doc.get_text()
        m = re.search(r'共(\d+)条数据', text)
        if m:
            total = int(m.group(1))
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 20,
            'total': total
        }

    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        vid = ids[0]
        url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        html = self.get_html(url)
        if not html:
            return {'list': []}
        doc = BeautifulSoup(html, 'html.parser')

        title = ''
        t = doc.find('title')
        if t:
            title = t.text.split('-')[0].strip()
        if not title:
            title = f"视频_{vid}"

        pic = ''
        img = doc.select_one('div.media ul li a img')
        if img:
            pic = img.get('src') or img.get('data-src', '')
            pic = self.fix_url(pic)

        play_link = ''
        play_a = doc.select_one('div.media ul li a')
        if play_a:
            play_link = play_a.get('href', '')
            if play_link:
                play_link = self.fix_url(play_link)

        desc = ''
        dt = doc.select_one('div.media ul li dt')
        if dt:
            desc = dt.text.strip()
        if not desc:
            desc = title

        if play_link:
            play_from = '默认线路'
            play_url_str = '播放$' + play_link
        else:
            play_from = '默认线路'
            play_url_str = '播放$' + vid

        data = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'vod_content': desc,
            'vod_actor': '',
            'vod_tag': '',
            'vod_play_from': play_from,
            'vod_play_url': play_url_str,
        }
        return {'list': [data]}

    def searchContent(self, key, quick=False, pg='1'):
        if not key:
            return {'list': [], 'page': 1, 'pagecount': 1, 'total': 0}
        pg = int(pg) if pg else 1
        if pg == 1:
            url = f"{self.host}/index.php/vod/search.html?wd={urllib.parse.quote(key)}"
        else:
            url = f"{self.host}/index.php/vod/search.html?wd={urllib.parse.quote(key)}&page={pg}"
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        doc = BeautifulSoup(html, 'html.parser')
        items = doc.select('div.pic ul li')
        videos = self._extract_video_items(items)
        pagecount = 1
        text = doc.get_text()
        m = re.search(r'共(\d+)条数据,当前(\d+)/(\d+)页', text)
        if m:
            total = int(m.group(1))
            pagecount = int(m.group(3))
        else:
            total = len(videos)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'total': total
        }

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {'parse': 1, 'url': ''}

        # 如果已经是直链，包装为代理地址
        if id.startswith('http') and (id.endswith('.m3u8') or id.endswith('.mp4') or '.m3u8?' in id):
            headers = {
                'User-Agent': self.headers['User-Agent'],
                'Referer': self.host + '/',
            }
            # 如果是 m3u8，走代理过滤广告
            if '.m3u8' in id:
                return {'parse': 0, 'url': self._m3u8_proxy_url(id), 'header': headers}
            return {'parse': 0, 'url': id, 'header': headers}

        # 从播放页提取直链
        html = self.get_html(id)
        if html:
            m = re.search(r'player_aaaa\s*=\s*\{.*?"url"\s*:\s*"([^"]+)"', html, re.DOTALL)
            if m:
                url = m.group(1)
                if url and (url.endswith('.m3u8') or url.endswith('.mp4')):
                    headers = {
                        'User-Agent': self.headers['User-Agent'],
                        'Referer': self.host + '/',
                    }
                    if '.m3u8' in url:
                        return {'parse': 0, 'url': self._m3u8_proxy_url(url), 'header': headers}
                    return {'parse': 0, 'url': url, 'header': headers}

            m = re.search(r'videoSrc\s*=\s*["\']([^"\']+)["\']', html)
            if m:
                url = m.group(1)
                if url.startswith('/'):
                    url = self.host + url
                if url.endswith('.m3u8') or url.endswith('.mp4'):
                    headers = {
                        'User-Agent': self.headers['User-Agent'],
                        'Referer': self.host + '/',
                    }
                    if '.m3u8' in url:
                        return {'parse': 0, 'url': self._m3u8_proxy_url(url), 'header': headers}
                    return {'parse': 0, 'url': url, 'header': headers}

        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/',
        }
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
            # 清洗反斜杠转义：将 \/ 替换为 /
            target = target.replace("\\/", "/")

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            res = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=15)
            if not res:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(res, "content", b"") or b""
            if not content and hasattr(res, "text") and res.text:
                content = res.text.encode("utf-8", errors="ignore")

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
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urllib.parse.urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

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

        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

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

    def recommendContent(self, ids, pg):
        if not ids:
            return {'list': []}
        vid = ids[0]
        url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        html = self.get_html(url)
        if not html:
            return {'list': []}
        doc = BeautifulSoup(html, 'html.parser')
        videos = []
        for container in doc.select('div.pic2 ul li, div.pic ul li'):
            a = container.find('a', href=True)
            if not a:
                continue
            href = a.get('href', '')
            if '/detail/id/' not in href:
                continue
            if a.get('title') and ('更多>>' in a.get('title') or '首页' in a.get('title')):
                continue
            vid2 = self._extract_vod_id(href)
            title = a.get('title', '') or a.text.strip()
            if not title:
                title = a.text.strip()
            pic = ''
            img = container.find('img')
            if img:
                pic = img.get('src') or img.get('data-src', '')
                pic = self.fix_url(pic)
            if vid2 and title and vid2 != vid:
                videos.append({
                    'vod_id': vid2,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': ''
                })
                if len(videos) >= 12:
                    break
        return {'list': videos}