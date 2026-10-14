# coding: utf-8
import re
import json
import base64
from urllib.parse import quote, urljoin

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = 'https://kzzn.wandanba63.cc'
        self.classes = [
            {'type_id': '5228', 'type_name': '国产精品'},
            {'type_id': '5229', 'type_name': '主播秀色'},
            {'type_id': '5230', 'type_name': '网曝系列'},
            {'type_id': '5231', 'type_name': '麻豆传媒'},
            {'type_id': '5232', 'type_name': '日本有码'},
            {'type_id': '5233', 'type_name': '日本无码'},
            {'type_id': '5234', 'type_name': '中文字幕'},
            {'type_id': '5235', 'type_name': '童颜巨乳'},
            {'type_id': '5236', 'type_name': '性感人妻'},
            {'type_id': '5237', 'type_name': '强奸乱伦'},
            {'type_id': '5238', 'type_name': '丝袜OL'},
            {'type_id': '5239', 'type_name': '欧美情色'},
            {'type_id': '5240', 'type_name': '三级伦理'},
            {'type_id': '5241', 'type_name': '卡通动漫'},
        ]
        self.filters = {}
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0',
            'Referer': self.host + '/'
        }
        self.timeout = 15

    def getName(self):
        return '玩蛋吧'

    def getDependence(self):
        return []

    def init(self, extend=''):
        self.extend = extend or ''

    def homeContent(self, filter):
        return {'class': self.classes, 'filters': self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            resp = self.fetch(f'{self.host}/index.php', headers=self.headers, timeout=self.timeout)
            html = resp.text
            return {'list': self._parse_list(html)}
        except Exception:
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
            if page < 1:
                page = 1
            url = f'{self.host}/index.php/vod/type/id/{tid}.html'
            if page > 1:
                url = f'{self.host}/index.php/vod/type/id/{tid}/page/{page}.html'
            resp = self.fetch(url, headers=self.headers, timeout=self.timeout)
            html = resp.text
            items = self._parse_list(html)
            total_page = self._parse_total_page(html)
            return {
                'list': items,
                'page': page,
                'pagecount': total_page or 99,
                'limit': 20,
                'total': 999
            }
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 20, 'total': 0}

    def detailContent(self, ids):
        try:
            vid = str(ids[0])
            parts = vid.split('|$|')
            vod_id = parts[0]
            name = parts[1] if len(parts) > 1 else ''
            raw_pic = parts[2] if len(parts) > 2 else ''
            remark = parts[3] if len(parts) > 3 else ''

            detail_url = f'{self.host}/index.php/vod/detail/id/{vod_id}.html'
            resp = self.fetch(detail_url, headers=self.headers, timeout=self.timeout)
            html = resp.text

            m3u8 = self._extract_m3u8(html)
            title = self._extract_title(html) or name
            pic_url = self._extract_pic(html) or raw_pic
            remark_text = self._extract_remark(html) or remark

            if m3u8:
                play_url = f'第1集${m3u8}'
            else:
                play_url = f'第1集${detail_url}'

            vod = {
                'vod_id': vod_id,
                'vod_name': title,
                'vod_pic': pic_url,
                'vod_remarks': remark_text,
                'vod_content': remark_text,
                'vod_play_from': '播放',
                'vod_play_url': play_url
            }
            return {'list': [vod]}
        except Exception:
            return {'list': []}

    def searchContent(self, key, quick, pg='1'):
        try:
            page = int(pg) if pg else 1
            if page < 1:
                page = 1
            encoded = quote(key)
            url = f'{self.host}/index.php/vod/search/wd/{encoded}.html'
            if page > 1:
                url = f'{url}?page={page}'
            resp = self.fetch(url, headers=self.headers, timeout=self.timeout)
            html = resp.text
            items = self._parse_list(html)
            return {'list': items, 'page': page}
        except Exception:
            return {'list': [], 'page': 1}

    def playerContent(self, flag, id, vipFlags):
        if id.endswith('.m3u8') or id.endswith('.mp4'):
            return {'parse': 0, 'url': id, 'header': self.headers}

        if '/vod/detail/' in id:
            try:
                resp = self.fetch(id, headers=self.headers, timeout=self.timeout)
                html = resp.text
                m3u8 = self._extract_m3u8(html)
                if m3u8:
                    return {'parse': 0, 'url': m3u8, 'header': self.headers}
            except Exception:
                pass

        return {'parse': 1, 'url': id, 'header': self.headers}

    def _parse_list(self, html):
        items = []
        # 优先匹配 data-src 真实图片
        pattern = r'<a\s+href="[^"]*?/vod/detail/id/(\d+)\.html"[^>]*>[\s\S]*?<img[^>]*?data-src="([^"]+)"[^>]*>[\s\S]*?<span[^>]*?class="[^"]*title[^"]*"[^>]*>([^<]+)</span>[\s\S]*?<span[^>]*?class="[^"]*remarks[^"]*"[^>]*>([^<]*)</span>'
        matches = re.findall(pattern, html)

        if not matches:
            # 备用：匹配 src
            pattern2 = r'<a\s+href="[^"]*?/vod/detail/id/(\d+)\.html"[^>]*>[\s\S]*?<img[^>]*?src="([^"]+)"[^>]*>[\s\S]*?<span[^>]*?class="[^"]*title[^"]*"[^>]*>([^<]+)</span>[\s\S]*?<span[^>]*?class="[^"]*remarks[^"]*"[^>]*>([^<]*)</span>'
            matches = re.findall(pattern2, html)

        if not matches:
            # 更宽松备用
            block_pattern = r'<a\s+href="[^"]*?/vod/detail/id/(\d+)\.html"[^>]*>[\s\S]*?<img[^>]*?data-src="([^"]+)"[^>]*>[\s\S]*?<span[^>]*>([^<]+)</span>'
            matches = re.findall(block_pattern, html)
            if not matches:
                block_pattern2 = r'<a\s+href="[^"]*?/vod/detail/id/(\d+)\.html"[^>]*>[\s\S]*?<img[^>]*?src="([^"]+)"[^>]*>[\s\S]*?<span[^>]*>([^<]+)</span>'
                matches = re.findall(block_pattern2, html)

        for match in matches:
            if len(match) >= 3:
                vid = match[0]
                raw_pic = self._fix_url(match[1])
                # 过滤占位图
                if 'lazy.svg' in raw_pic or raw_pic.endswith('/style/lazy.svg'):
                    continue
                name = match[2].strip()
                remark = match[3].strip() if len(match) > 3 else ''
                vod_id = f'{vid}|$|{name}|$|{raw_pic}|$|{remark}'
                # 添加 Referer 让壳层正确加载图片
                pic_with_ref = raw_pic + '@Referer=' + self.host + '/'
                items.append({
                    'vod_id': vod_id,
                    'vod_name': name,
                    'vod_pic': pic_with_ref,
                    'vod_remarks': remark
                })
        return items

    def _parse_total_page(self, html):
        pattern = r'<a[^>]*href="[^"]*/page/(\d+)\.html"[^>]*>(\d+)</a>'
        matches = re.findall(pattern, html)
        if matches:
            try:
                last_page = int(matches[-1][1])
                if last_page > 1:
                    return last_page
            except:
                pass

        total_pattern = r'共(\d+)页'
        total_match = re.search(total_pattern, html)
        if total_match:
            try:
                return int(total_match.group(1))
            except:
                pass
        return 1

    def _extract_m3u8(self, html):
        player_pattern = r'player_aaaa\s*=\s*({[\s\S]*?});'
        player_match = re.search(player_pattern, html)
        if player_match:
            try:
                import json
                text = player_match.group(1)
                text = re.sub(r'//.*?$', '', text, flags=re.M)
                text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
                data = json.loads(text)
                url = data.get('url', '')
                if url and ('.m3u8' in url or '.mp4' in url):
                    return self._fix_url(url)
            except:
                pass

        hls_pattern = r'url"\s*:\s*"([^"]+\.m3u8)"'
        hls_match = re.search(hls_pattern, html)
        if hls_match:
            return self._fix_url(hls_match.group(1))

        video_pattern = r'<video[^>]*src="([^"]+\.m3u8)"'
        video_match = re.search(video_pattern, html)
        if video_match:
            return self._fix_url(video_match.group(1))

        mac_pattern = r'MacPlayer\.PlayUrl\s*=\s*"([^"]+\.m3u8)"'
        mac_match = re.search(mac_pattern, html)
        if mac_match:
            return self._fix_url(mac_match.group(1))

        return None

    def _extract_title(self, html):
        title_match = re.search(r'<title>([^<]+)</title>', html)
        if title_match:
            title = title_match.group(1).strip()
            title = re.sub(r'\s*[-|]\s*玩蛋吧\s*$', '', title)
            return title
        return None

    def _extract_pic(self, html):
        pic_match = re.search(r'<img[^>]*?class="[^"]*vod_pic[^"]*"[^>]*data-src="([^"]+)"', html)
        if pic_match:
            return self._fix_url(pic_match.group(1))
        pic_match = re.search(r'<img[^>]*?class="[^"]*vod_pic[^"]*"[^>]*src="([^"]+)"', html)
        if pic_match:
            return self._fix_url(pic_match.group(1))
        pic_match = re.search(r'<img[^>]*?data-src="([^"]+)"[^>]*?class="[^"]*vod_pic[^"]*"', html)
        if pic_match:
            return self._fix_url(pic_match.group(1))
        pic_match = re.search(r'<img[^>]*?src="([^"]+)"[^>]*?class="[^"]*vod_pic[^"]*"', html)
        if pic_match:
            return self._fix_url(pic_match.group(1))
        return None

    def _extract_remark(self, html):
        remark_match = re.search(r'<span[^>]*?class="[^"]*remarks[^"]*"[^>]*>([^<]+)</span>', html)
        if remark_match:
            return remark_match.group(1).strip()
        return None

    def _fix_url(self, url):
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if not url.startswith('http'):
            if url.startswith('/'):
                return self.host + url
            return urljoin(self.host, url)
        return url