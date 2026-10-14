# -*- coding: utf-8 -*-
import re
import json
import base64
import posixpath
from urllib.parse import urljoin, quote, unquote, urlparse
from bs4 import BeautifulSoup
import requests

class Spider:
    def __init__(self):
        self.host = "https://rrr623.chao2.my/crrrr"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/'
        }
        # 分类列表 - 从首页提取
        self.classes = [
            {"type_id": "6", "type_name": "精品推荐"},
            {"type_id": "7", "type_name": "国产精品"},
            {"type_id": "8", "type_name": "主播秀色"},
            {"type_id": "9", "type_name": "日本有码"},
            {"type_id": "10", "type_name": "日本无码"},
            {"type_id": "11", "type_name": "中文字幕"},
            {"type_id": "21", "type_name": "童颜巨乳"},
            {"type_id": "22", "type_name": "性感人妻"},
            {"type_id": "23", "type_name": "强奸乱伦"},
            {"type_id": "24", "type_name": "欧美情色"},
            {"type_id": "25", "type_name": "三级伦理"},
            {"type_id": "26", "type_name": "卡通动漫"},
            {"type_id": "27", "type_name": "丝袜OL"},
            {"type_id": "28", "type_name": "自拍偷拍"},
            {"type_id": "29", "type_name": "日本片商"},
            {"type_id": "31", "type_name": "网曝系列"},
            {"type_id": "32", "type_name": "麻豆传媒"},
            {"type_id": "34", "type_name": "国产乱伦"},
            {"type_id": "36", "type_name": "国产SM"},
            {"type_id": "37", "type_name": "国产人妻"},
            {"type_id": "73", "type_name": "无码专区"},
            {"type_id": "74", "type_name": "麻豆传媒"},
            {"type_id": "75", "type_name": "制服诱惑"},
            {"type_id": "76", "type_name": "三级伦理"},
            {"type_id": "77", "type_name": "AI换脸"},
            {"type_id": "78", "type_name": "中文字幕"},
            {"type_id": "79", "type_name": "卡通动漫"},
            {"type_id": "80", "type_name": "欧美系列"},
            {"type_id": "81", "type_name": "美女主播"},
            {"type_id": "82", "type_name": "国产自拍"},
            {"type_id": "83", "type_name": "熟女人妻"},
            {"type_id": "84", "type_name": "萝莉少女"},
            {"type_id": "85", "type_name": "多人群交"},
            {"type_id": "86", "type_name": "美乳巨乳"},
            {"type_id": "87", "type_name": "强奸乱伦"},
            {"type_id": "88", "type_name": "抖音视频"},
            {"type_id": "89", "type_name": "韩国主播"},
            {"type_id": "90", "type_name": "网红头条"},
            {"type_id": "91", "type_name": "网爆黑料"},
            {"type_id": "92", "type_name": "欧美无码"},
            {"type_id": "41", "type_name": "网红主播"},
            {"type_id": "42", "type_name": "国产传媒"},
            {"type_id": "43", "type_name": "探花系列"},
            {"type_id": "44", "type_name": "人妻熟女"},
            {"type_id": "45", "type_name": "日本无码"},
            {"type_id": "46", "type_name": "美乳巨乳"},
            {"type_id": "47", "type_name": "强制侵犯"},
            {"type_id": "48", "type_name": "制服诱惑"},
            {"type_id": "49", "type_name": "绝色佳人"},
            {"type_id": "50", "type_name": "风俗泡泡浴"},
            {"type_id": "51", "type_name": "家庭乱伦"},
            {"type_id": "52", "type_name": "AV解说"},
            {"type_id": "53", "type_name": "三级电影"},
            {"type_id": "54", "type_name": "少女萝莉"},
            {"type_id": "55", "type_name": "SM调教"},
            {"type_id": "56", "type_name": "绝顶潮吹"},
            {"type_id": "57", "type_name": "魔镜系列"},
            {"type_id": "58", "type_name": "时间停止"},
            {"type_id": "59", "type_name": "漫改系列"},
            {"type_id": "60", "type_name": "电车痴汉"},
        ]
        self.filters = {}
        for cls in self.classes:
            self.filters[cls["type_id"]] = []

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def fetch(self, url, headers=None, timeout=20):
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
        m = re.search(r'/vodplay/(\d+)-\d+-\d+\.html', url)
        if m:
            return m.group(1)
        m = re.search(r'/voddetail/(\d+)\.html', url)
        if m:
            return m.group(1)
        return url

    def _parse_video_items(self, items, limit=999):
        """解析视频列表，自动去重（使用 vod_name 去重）"""
        videos = []
        seen_names = set()
        for dl in items:
            a = dl.find('a', href=True)
            if not a:
                continue
            href = a.get('href', '')
            vid = self._extract_vod_id(href)
            if not vid:
                continue
            title = a.get('title', '') or a.text.strip()
            if not title:
                continue

            # 使用标题去重（去除可能的空格差异）
            title_key = title.strip()
            if title_key in seen_names:
                continue
            seen_names.add(title_key)

            dt = dl.find('dt')
            pic = ''
            date = ''
            if dt:
                img = dt.find('img')
                if img:
                    pic = img.get('data-src') or img.get('src', '')
                    pic = self.fix_url(pic)
                date_span = dt.find('i')
                if date_span:
                    date = date_span.text.strip()

            remark = date or ''
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
            mod = doc.find('div', class_='mod index-list')
            if mod:
                items = mod.find_all('dl')
                result['list'] = self._parse_video_items(items, 30)
            else:
                result['list'] = []
        else:
            result['list'] = []
        return result

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            result = self.categoryContent('6', 1, False, None)
            return {'list': result.get('list', [])[:20]}
        except Exception as e:
            print('homeVideoContent error:', e)
            return {'list': []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        url = f"{self.host}/vodtype/{tid}-{pg}.html"
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}

        doc = BeautifulSoup(html, 'html.parser')
        # 合并多个可能包含视频列表的区域，统一去重
        all_items = []
        mod = doc.find('div', class_='mod index-list')
        if mod:
            all_items.extend(mod.find_all('dl'))
        mod2 = doc.find('div', class_='channel-list')
        if mod2:
            all_items.extend(mod2.find_all('dl'))

        videos = self._parse_video_items(all_items)

        pagecount = 1
        pagination = doc.find('div', class_='pagination')
        if pagination:
            for a in pagination.find_all('a'):
                if a.text.strip().isdigit():
                    num = int(a.text.strip())
                    if num > pagecount:
                        pagecount = num
            for a in pagination.find_all('a'):
                if '尾页' in a.text:
                    m = re.search(r'-(\d+)---\.html', a.get('href', ''))
                    if m:
                        pagecount = int(m.group(1))
                        break

        total = pagecount * 20
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
        url = f"{self.host}/vodplay/{vid}-1-1.html"
        html = self.get_html(url)
        if not html:
            return {'list': []}

        doc = BeautifulSoup(html, 'html.parser')

        title = ''
        h1 = doc.find('h1')
        if h1:
            title = h1.text.strip()
        if not title:
            t = doc.find('div', class_='content')
            if t:
                h1 = t.find('h1')
                if h1:
                    title = h1.text.strip()

        pic = ''
        img = doc.find('img', class_='lazyloaded')
        if img:
            pic = img.get('data-src') or img.get('src', '')
            pic = self.fix_url(pic)

        play_url = ''
        play_from = '默认线路'
        script = doc.find('script', string=re.compile(r'player_aaaa'))
        if script:
            script_text = script.string
            if script_text:
                m = re.search(r'"url":"([^"]+)"', script_text)
                if m:
                    play_url = m.group(1).replace('\\/', '/')
                if not play_url:
                    m = re.search(r"'url':'([^']+)'", script_text)
                    if m:
                        play_url = m.group(1).replace('\\/', '/')
                m = re.search(r'"from":"([^"]+)"', script_text)
                if m:
                    play_from = m.group(1)

        if not play_url:
            iframe = doc.find('iframe', src=True)
            if iframe:
                src = iframe.get('src', '')
                if 'url=' in src:
                    m = re.search(r'url=([^&]+)', src)
                    if m:
                        play_url = unquote(m.group(1))
                elif src.startswith('http'):
                    play_url = src

        if play_url:
            if play_url.startswith('/'):
                play_url = self.host + play_url
            # 使用代理地址，支持广告过滤
            play_url_str = f'播放${self._m3u8_proxy_url(play_url)}'
        else:
            play_url_str = f'播放${vid}'

        tag = ''
        if title:
            m = re.search(r'\[([^\]]+)\]', title)
            if m:
                tag = m.group(1)

        data = {
            'vod_id': vid,
            'vod_name': title or '未知视频',
            'vod_pic': pic,
            'vod_content': '',
            'vod_tag': tag,
            'vod_play_from': play_from,
            'vod_play_url': play_url_str,
        }
        return {'list': [data]}

    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址"""
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def searchContent(self, key, quick=False, pg='1'):
        if not key:
            return {'list': [], 'page': 1, 'pagecount': 1, 'total': 0}

        pg = int(pg) if pg else 1
        if pg == 1:
            url = f"{self.host}/vodsearch/-------------.html?wd={quote(key)}"
        else:
            url = f"{self.host}/vodsearch/{quote(key)}----------{pg}---.html"

        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}

        doc = BeautifulSoup(html, 'html.parser')
        all_items = []
        mod = doc.find('div', class_='channel-list')
        if mod:
            all_items.extend(mod.find_all('dl'))
        mod2 = doc.find('div', class_='mod index-list')
        if mod2:
            all_items.extend(mod2.find_all('dl'))

        videos = self._parse_video_items(all_items)

        total = 0
        total_span = doc.find('span', class_='mac_total')
        if total_span:
            try:
                total = int(total_span.text.strip())
            except:
                pass

        pagecount = (total + 19) // 20 if total > 0 else 1
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 20,
            'total': total
        }

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {'parse': 1, 'url': ''}

        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/',
        }

        if id.startswith('http'):
            if id.endswith('.m3u8') or id.endswith('.mp4') or '.m3u8' in id:
                return {'parse': 0, 'url': id, 'header': headers}
            html = self.get_html(id)
            if html:
                m = re.search(r'"url":"([^"]+)"', html)
                if m:
                    url = m.group(1).replace('\\/', '/')
                    if url.startswith('/'):
                        url = self.host + url
                    if url.endswith('.m3u8') or url.endswith('.mp4') or '.m3u8' in url:
                        return {'parse': 0, 'url': url, 'header': headers}
                m = re.search(r'url=([^&]+)', html)
                if m:
                    url = unquote(m.group(1))
                    if url.startswith('/'):
                        url = self.host + url
                    if url.endswith('.m3u8') or url.endswith('.mp4') or '.m3u8' in url:
                        return {'parse': 0, 'url': url, 'header': headers}

        return {'parse': 1, 'url': id, 'header': headers}

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤"""
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            res = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=20)
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
        """清洗 m3u8：过滤广告分片，保留正片"""
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
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urlparse(source_url)
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
                media_url = urljoin(source_url, line)
                media_parsed = urlparse(media_url)

                # 过滤逻辑：判断分片路径是否以正片目录开头
                is_ad = not media_parsed.path.startswith(main_dir)

                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urljoin(source_url, line))
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

        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写 m3u8 标签中的 URI（补全绝对地址）"""
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)

        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)

        return line

    def recommendContent(self, ids, pg=1):
        if not ids:
            return {'list': []}
        vid = ids[0]
        url = f"{self.host}/vodplay/{vid}-1-1.html"
        html = self.get_html(url)
        if not html:
            return {'list': []}

        doc = BeautifulSoup(html, 'html.parser')
        mod = doc.find('div', class_='mod index-list')
        if mod:
            items = mod.find_all('dl')
            videos = self._parse_video_items(items, 20)
            return {'list': videos}
        return {'list': []}

    def init(self, extend=''):
        pass

    def destroy(self):
        pass

    def getDependence(self):
        return ['requests', 'bs4']

    def getName(self):
        return '超乳天团'