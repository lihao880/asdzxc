# -*- coding: utf-8 -*-
import re
import json
import urllib.parse
import posixpath
import requests
from bs4 import BeautifulSoup

class Spider:
    def __init__(self):
        self.host = "https://hxooo2.sbs"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/',
        }
        self.classes = [
            {"type_id": "117", "type_name": "深夜撸片"},
            {"type_id": "118", "type_name": "免费视频"},
            {"type_id": "119", "type_name": "每日精选"},
            {"type_id": "120", "type_name": "必射精选"},
            {"type_id": "154", "type_name": "站长推荐"},
        ]
        self.filters = {}

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

    def _extract_vod_id(self, href):
        if not href:
            return ''
        m = re.search(r'/voddetail/(\d+)\.html', href)
        if m:
            return m.group(1)
        m = re.search(r'/vodplay/(\d+)-\d+-\d+\.html', href)
        if m:
            return m.group(1)
        return ''

    def _parse_list_items(self, html, limit=999):
        doc = BeautifulSoup(html, 'html.parser')
        videos = []
        items = doc.select('.thumbnail-group li')
        for li in items:
            a = li.find('a', class_='thumbnail', href=True)
            if not a:
                continue
            href = a.get('href', '')
            vod_id = self._extract_vod_id(href)
            if not vod_id:
                continue
            title = ''
            title_tag = li.find('h5')
            if title_tag:
                title_a = title_tag.find('a')
                if title_a:
                    title = title_a.get('title', '') or title_a.text.strip()
            if not title:
                title = a.get('title', '')
            if not title:
                title = '视频'
            img = a.find('img')
            pic = img.get('src') or img.get('data-src', '') if img else ''
            pic = self.fix_url(pic)
            remark = ''
            p_tag = li.find('p')
            if p_tag:
                remark = p_tag.text.strip()
            if vod_id and title:
                videos.append({
                    'vod_id': vod_id,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })
                if len(videos) >= limit:
                    break
        return videos

    def _extract_play_url(self, html):
        if not html:
            return None
        pattern = r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"'
        m = re.search(pattern, html)
        if m:
            url = m.group(1)
            if url and (url.endswith('.m3u8') or '.m3u8?' in url):
                return url
        m = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html)
        if m:
            return m.group(0)
        m = re.search(r'videoSrc\s*=\s*["\']([^"\']+)["\']', html)
        if m:
            url = m.group(1)
            if url.startswith('/'):
                url = self.host + url
            if url.endswith('.m3u8') or '.m3u8?' in url:
                return url
        return None

    def homeContent(self, filter=False):
        return {'class': self.classes, 'filters': self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            result = self.categoryContent('117', 1, False, None)
            return {'list': result.get('list', [])[:15]}
        except Exception as e:
            print('homeVideoContent error:', e)
            return {'list': []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        if pg == 1:
            url = f"{self.host}/vodtype/{tid}.html"
        else:
            url = f"{self.host}/vodtype/{tid}-{pg}.html"
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        videos = self._parse_list_items(html)
        pagecount = 1
        pagination = re.search(r'共\s*\d+\s*条数据,当前\s*(\d+)\s*/\s*(\d+)\s*页', html)
        if pagination:
            pagecount = int(pagination.group(2))
        else:
            links = re.findall(r'/vodtype/' + str(tid) + r'-(\d+)\.html', html)
            if links:
                max_page = max([int(x) for x in links])
                pagecount = max(max_page, 1)
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
        vod_id = ids[0]
        play_url = f"{self.host}/vodplay/{vod_id}-1-1.html"
        html = self.get_html(play_url)
        title = ''
        pic = ''
        remark = ''
        play_url_raw = ''
        if html:
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                title = title_match.group(1).replace('-在线观看-红杏窝', '').strip()
            play_url_raw = self._extract_play_url(html) or ''
            desc_match = re.search(r'<meta name="description" content="([^"]+)"', html)
            if desc_match:
                remark = desc_match.group(1)
        if not title:
            title = f'视频 {vod_id}'
        if play_url_raw:
            play_from = '播放'
            play_url_str = f'播放${play_url_raw}'
        else:
            play_from = '播放'
            play_url_str = f'播放${play_url}'
        data = {
            'vod_id': vod_id,
            'vod_name': title,
            'vod_pic': pic,
            'vod_remarks': remark,
            'vod_content': remark,
            'vod_play_from': play_from,
            'vod_play_url': play_url_str,
        }
        return {'list': [data]}

    def searchContent(self, key, quick=False, pg='1'):
        if not key:
            return {'list': [], 'page': 1, 'pagecount': 1, 'total': 0}
        pg = int(pg) if pg else 1
        encoded_key = urllib.parse.quote(key)
        url = f"{self.host}/vodsearch/{encoded_key}-------------.html"
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        videos = self._parse_list_items(html)
        return {'list': videos, 'page': pg, 'pagecount': 99, 'total': 999}

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {'parse': 1, 'url': ''}
        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/',
        }
        if id.startswith('http') and (id.endswith('.m3u8') or '.m3u8?' in id or id.endswith('.mp4')):
            return {'parse': 0, 'url': self._m3u8_proxy_url(id), 'header': headers}
        if id.startswith('http') and ('/vodplay/' in id or 'vodplay' in id):
            html = self.get_html(id)
            if html:
                play_url = self._extract_play_url(html)
                if play_url:
                    return {'parse': 0, 'url': self._m3u8_proxy_url(play_url), 'header': headers}
        if id.startswith('http'):
            html = self.get_html(id)
            if html:
                play_url = self._extract_play_url(html)
                if play_url:
                    return {'parse': 0, 'url': self._m3u8_proxy_url(play_url), 'header': headers}
        return {'parse': 1, 'url': id, 'header': headers}

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

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

    def init(self, extend=''):
        pass

    def destroy(self):
        pass

    def getDependence(self):
        return ['requests', 'bs4']

    def getName(self):
        return '红杏窝'