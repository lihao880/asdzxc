# coding: utf-8
import re
import json
import base64
import urllib.parse
import posixpath
from bs4 import BeautifulSoup
import requests


class Spider:
    def __init__(self):
        self.host = "https://a.qingyiduz.xyz"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/',
        }
        self.classes = [
            {"type_id": "1", "type_name": "日韩电影"},
            {"type_id": "2", "type_name": "欧美视频"},
            {"type_id": "3", "type_name": "国产高清"},
            {"type_id": "4", "type_name": "动漫精品"},
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

    def _extract_vod_id(self, url):
        if not url:
            return ''
        m = re.search(r'/vod/play/id/(\d+)', url)
        if m:
            return m.group(1)
        m = re.search(r'id=(\d+)', url)
        if m:
            return m.group(1)
        return url

    def _parse_videos(self, html, limit=999):
        doc = BeautifulSoup(html, 'html.parser')
        videos = []
        for li in doc.find_all('li'):
            a = li.find('a', class_='uzimg', href=True)
            if not a:
                continue
            href = a.get('href', '')
            vid = self._extract_vod_id(href)
            if not vid:
                continue
            title = a.get('title', '')
            if not title:
                h4 = li.find('h4')
                if h4:
                    title = h4.text.strip()
            img = a.find('img')
            pic = img.get('data-original') or img.get('src', '') if img else ''
            pic = self.fix_url(pic)
            remark = ''
            p = li.find('p', class_='vodtitle')
            if p:
                span = p.find('span', class_='title')
                if span:
                    remark = span.text.strip()
                else:
                    parts = p.text.split('-')
                    if len(parts) > 1:
                        remark = parts[-1].strip()
            if vid and title:
                videos.append({
                    'vod_id': str(vid),
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })
                if len(videos) >= limit:
                    break
        return videos

    def homeContent(self, filter=False):
        return {'class': self.classes, 'filters': self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self.get_html(self.host + '/')
        if not html:
            return {'list': []}
        doc = BeautifulSoup(html, 'html.parser')
        div = doc.find('div', class_='myvod')
        if not div:
            return {'list': []}
        videos = self._parse_videos(str(div), 15)
        return {'list': videos}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        if pg == 1:
            url = self.host + '/index.php/vod/type/id/' + str(tid) + '.html'
        else:
            url = self.host + '/index.php/vod/type/id/' + str(tid) + '/page/' + str(pg) + '.html'
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        doc = BeautifulSoup(html, 'html.parser')
        div = doc.find('div', class_='myvod')
        if not div:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        videos = self._parse_videos(str(div))
        total = 0
        total_span = doc.find('span', class_='mac_total')
        if total_span:
            try:
                total = int(total_span.text.strip())
            except:
                pass
        pagecount = 1
        mypage = doc.find('div', class_='mypage')
        if mypage:
            for a in mypage.find_all('a'):
                href = a.get('href', '')
                if '尾页' in a.text and href:
                    m = re.search(r'/page/(\d+)\.html', href)
                    if m:
                        pagecount = int(m.group(1))
                        break
                if href and '/page/' in href:
                    m = re.search(r'/page/(\d+)\.html', href)
                    if m:
                        num = int(m.group(1))
                        if num > pagecount:
                            pagecount = num
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
        if isinstance(ids, list):
            vid = str(ids[0])
        else:
            vid = str(ids)
        if not vid or vid == 'None':
            return {'list': []}
        url = self.host + '/index.php/vod/play/id/' + vid + '/sid/1/nid/1.html'
        html = self.get_html(url)
        if not html:
            return {'list': []}
        doc = BeautifulSoup(html, 'html.parser')
        title = ''
        t = doc.find('title')
        if t:
            title = t.text.strip()
            title = re.sub(r'\s*-\s*在线播放.*$', '', title)
            title = re.sub(r'\s*-\s*高清资源.*$', '', title)
            title = re.sub(r'\s*-\s*不夜城.*$', '', title)
        pic = ''
        img = doc.find('img', class_='lazy')
        if img:
            pic = img.get('data-original') or img.get('src', '')
            pic = self.fix_url(pic)
        play_url = ''
        player_match = re.search(r'var\s+player_aaaa\s*=\s*({[^}]+})', html)
        if player_match:
            try:
                player_data = json.loads(player_match.group(1))
                play_url = player_data.get('url', '')
                play_from = player_data.get('from', '默认线路')
            except:
                play_from = '默认线路'
        else:
            play_from = '默认线路'
            m = re.search(r'["\']([^"\']+\.m3u8)["\']', html)
            if m:
                play_url = m.group(1)
        if play_url:
            play_url = play_url.replace("\\/", "/")
            play_url_str = '播放$' + play_url
        else:
            play_url_str = '播放$' + vid
        data = {
            'vod_id': vid,
            'vod_name': title or '未知标题',
            'vod_pic': pic,
            'vod_content': '',
            'vod_play_from': play_from,
            'vod_play_url': play_url_str,
        }
        return {'list': [data]}

    def searchContent(self, key, quick=False, pg='1'):
        return {'list': [], 'page': 1, 'pagecount': 1, 'total': 0}

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {'parse': 1, 'url': ''}
        # 转义处理
        id = id.replace("\\/", "/")
        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/',
        }
        if id.startswith('http'):
            if id.endswith('.m3u8') or id.endswith('.mp4') or '.m3u8?' in id:
                # m3u8 走代理过滤广告
                if id.endswith('.m3u8') or '.m3u8?' in id:
                    return {'parse': 0, 'url': self._m3u8_proxy_url(id), 'header': headers}
                return {'parse': 0, 'url': id, 'header': headers}
            html = self.get_html(id)
            if html:
                player_match = re.search(r'var\s+player_aaaa\s*=\s*({[^}]+})', html)
                if player_match:
                    try:
                        player_data = json.loads(player_match.group(1))
                        url = player_data.get('url', '')
                        if url:
                            url = url.replace("\\/", "/")
                        if url and (url.endswith('.m3u8') or url.endswith('.mp4')):
                            if url.endswith('.m3u8') or '.m3u8?' in url:
                                return {'parse': 0, 'url': self._m3u8_proxy_url(url), 'header': headers}
                            return {'parse': 0, 'url': url, 'header': headers}
                    except:
                        pass
                m = re.search(r'["\']([^"\']+\.m3u8)["\']', html)
                if m:
                    url = m.group(1).replace("\\/", "/")
                    return {'parse': 0, 'url': self._m3u8_proxy_url(url), 'header': headers}
        return {'parse': 1, 'url': id, 'header': headers}

    def getProxyUrl(self):
        """获取本地代理地址（FongMi/TVBox 标准）"""
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址（标准格式：?do=py&url=）"""
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, params):
        """
        m3u8本地代理 - 广告分片过滤
        兼容 url 和 source 两种参数名
        """
        try:
            # 兼容 url 和 source 两种参数名
            if isinstance(params, dict):
                target = params.get("url", "") or params.get("source", "")
            else:
                target = str(params or "")

            # 剥离前缀 url= 并解码
            if target.startswith("url="):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            # 发起HTTP请求获取m3u8内容
            resp = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=15)
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
        """清洗m3u8 - 过滤广告分片"""
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
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urllib.parse.urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

        # 从 #EXT-X-KEY 提取正片目录（更准确）
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

        # 二次清洗：去除孤立/连续的 #EXT-X-DISCONTINUITY 和 KEY:METHOD=NONE
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        # 清理尾部多余的标记
        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI（补全绝对地址）"""
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
        return {'list': []}

    def init(self, extend=''):
        pass

    def destroy(self):
        pass

    def getDependence(self):
        return ['requests', 'bs4']

    def getName(self):
        return '不夜城'