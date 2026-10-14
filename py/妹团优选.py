# coding: utf-8
import re
import json
import base64
from urllib.parse import quote, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = 'https://heping704.mtyxl2.top/mt'
        self.classes = [
            {'type_id': '6', 'type_name': '精品推荐'},
            {'type_id': '7', 'type_name': '国产精品'},
            {'type_id': '8', 'type_name': '主播秀色'},
            {'type_id': '9', 'type_name': '日本有码'},
            {'type_id': '10', 'type_name': '日本无码'},
            {'type_id': '11', 'type_name': '中文字幕'},
            {'type_id': '21', 'type_name': '童颜巨乳'},
            {'type_id': '22', 'type_name': '性感人妻'},
            {'type_id': '41', 'type_name': '网红主播'},
            {'type_id': '42', 'type_name': '国产传媒'},
            {'type_id': '43', 'type_name': '探花系列'},
            {'type_id': '44', 'type_name': '人妻熟女'},
            {'type_id': '45', 'type_name': '日本无码'},
            {'type_id': '46', 'type_name': '美乳巨乳'},
            {'type_id': '47', 'type_name': '强制侵犯'},
            {'type_id': '48', 'type_name': '制服诱惑'},
            {'type_id': '73', 'type_name': '无码专区'},
            {'type_id': '74', 'type_name': '麻豆传媒'},
            {'type_id': '75', 'type_name': '制服诱惑'},
            {'type_id': '76', 'type_name': '三级伦理'},
            {'type_id': '77', 'type_name': 'AI换脸'},
            {'type_id': '78', 'type_name': '中文字幕'},
            {'type_id': '79', 'type_name': '卡通动漫'},
            {'type_id': '80', 'type_name': '欧美系列'},
        ]
        self.filters = {}
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0',
            'Referer': self.host + '/'
        }
        self.timeout = 15

    def getName(self):
        return '妹团优选'

    def getDependence(self):
        return []

    def init(self, extend=''):
        self.extend = extend or ''

    def homeContent(self, filter=False):
        return {'class': self.classes, 'filters': self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            url = f'{self.host}/vodtype/6.html'
            resp = self.fetch(url, headers=self.headers, timeout=self.timeout)
            html = resp.text
            return {'list': self._parse_list(html)}
        except Exception:
            return {'list': []}

    def categoryContent(self, tid, pg='1', filter=False, extend={}):
        try:
            page = int(pg) if pg else 1
            if page < 1:
                page = 1
            # 翻页URL格式: /mt/vodtype/{tid}-{page}.html
            if page > 1:
                url = f'{self.host}/vodtype/{tid}-{page}.html'
            else:
                url = f'{self.host}/vodtype/{tid}.html'
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

            detail_url = f'{self.host}/voddetail/{vod_id}.html'
            resp = self.fetch(detail_url, headers=self.headers, timeout=self.timeout)
            html = resp.text

            title = self._extract_title(html) or name
            pic_url = self._extract_pic(html) or raw_pic
            play_from, play_url = self._parse_playlist(html, vod_id)

            vod = {
                'vod_id': vod_id,
                'vod_name': title,
                'vod_pic': pic_url,
                'vod_remarks': remark,
                'vod_content': remark,
                'vod_play_from': play_from or '播放',
                'vod_play_url': play_url or f'第1集${vod_id}-1-1'
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
            url = f'{self.host}/vodsearch/-------------.html?wd={encoded}'
            if page > 1:
                url += f'&page={page}'
            resp = self.fetch(url, headers=self.headers, timeout=self.timeout)
            html = resp.text
            items = self._parse_list(html)
            return {'list': items, 'page': page}
        except Exception:
            return {'list': [], 'page': 1}

    def playerContent(self, flag, id, vipFlags):
        # 如果已经是直链
        if id and (id.endswith('.m3u8') or id.endswith('.mp4') or id.startswith('http')):
            return {'parse': 0, 'url': id, 'header': self.headers}

        # 构建播放页URL: /mt/vodplay/{vod_id}-{nid}-{sid}.html
        if id and '-' in id:
            play_url = f'{self.host}/vodplay/{id}.html'
        else:
            play_url = f'{self.host}/vodplay/{id}-1-1.html'

        try:
            resp = self.fetch(play_url, headers=self.headers, timeout=self.timeout)
            if not resp or not hasattr(resp, 'text'):
                return {'parse': 1, 'url': play_url}
            html = resp.text

            # 1. 匹配 player_aaaa
            player_match = re.search(r'var\s+player_aaaa\s*=\s*({.*?});', html, re.DOTALL)
            if player_match:
                try:
                    data_str = player_match.group(1)
                    # 清理注释
                    data_str = re.sub(r'//.*?$', '', data_str, flags=re.M)
                    data_str = re.sub(r'/\*.*?\*/', '', data_str, flags=re.S)
                    player_data = json.loads(data_str)
                    url = player_data.get('url', '')
                    encrypt = player_data.get('encrypt', 0)
                    if url:
                        if encrypt == 1:
                            url = unquote(url)
                        elif encrypt == 2:
                            try:
                                url = base64.b64decode(url).decode('utf-8', errors='ignore')
                            except:
                                pass
                        if url.startswith('http'):
                            return {'parse': 0, 'url': url, 'header': self.headers}
                except Exception as e:
                    pass

            # 2. MacPlayer.PlayUrl
            mac_match = re.search(r'MacPlayer\.PlayUrl\s*=\s*["\']([^"\']+)["\']', html)
            if mac_match:
                url = mac_match.group(1)
                if url.startswith('http'):
                    return {'parse': 0, 'url': url, 'header': self.headers}

            # 3. iframe src
            iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html)
            if iframe_match:
                url = iframe_match.group(1)
                if not url.startswith('http'):
                    url = self._fix_url(url)
                if url.startswith('http'):
                    return {'parse': 0, 'url': url, 'header': self.headers}

            # 4. .m3u8 直链
            m3u8_match = re.search(r'["\']([^"\']+\.m3u8[^"\']*)["\']', html)
            if m3u8_match:
                url = m3u8_match.group(1)
                if url.startswith('http'):
                    return {'parse': 0, 'url': url, 'header': self.headers}

            # 5. now 变量
            now_match = re.search(r'now\s*=\s*["\']([^"\']+)["\']', html)
            if now_match:
                url = now_match.group(1)
                if url.startswith('http'):
                    return {'parse': 0, 'url': url, 'header': self.headers}

        except Exception as e:
            pass

        return {'parse': 1, 'url': play_url}

    # ========== 辅助方法 ==========
    def _parse_list(self, html):
        items = []
        # 匹配视频列表
        pattern = r'<a\s+href="[^"]*?/voddetail/(\d+)\.html"[^>]*>[\s\S]*?<img[^>]*?src="([^"]+)"[^>]*>[\s\S]*?<h5[^>]*>[\s\S]*?<a[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html)

        if not matches:
            # 备选模式
            pattern2 = r'<li>\s*<a[^>]+href="[^"]*?/voddetail/(\d+)\.html"[^>]*>[\s\S]*?<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"'
            matches = re.findall(pattern2, html)

        for match in matches:
            vid = match[0]
            raw_pic = self._fix_url(match[1])
            name = match[2].strip() if len(match) > 2 else '未知'
            vod_id = f'{vid}|$|{name}|$|{raw_pic}|$|'
            items.append({
                'vod_id': vod_id,
                'vod_name': name,
                'vod_pic': raw_pic,
                'vod_remarks': ''
            })
        return items

    def _parse_total_page(self, html):
        # 匹配分页链接: /mt/vodtype/6-2.html
        pattern = r'<a[^>]*href="[^"]*/vodtype/\d+-(\d+)\.html"[^>]*>'
        matches = re.findall(pattern, html)
        if matches:
            try:
                last_page = max([int(p) for p in matches if p.isdigit()])
                if last_page > 1:
                    return last_page
            except:
                pass
        # 匹配 "共X页"
        total_pattern = r'共(\d+)页'
        total_match = re.search(total_pattern, html)
        if total_match:
            try:
                return int(total_match.group(1))
            except:
                pass
        # 匹配 "当前X/Y页"
        page_pattern = r'当前(\d+)/(\d+)页'
        page_match = re.search(page_pattern, html)
        if page_match:
            try:
                return int(page_match.group(2))
            except:
                pass
        return 1

    def _parse_playlist(self, html, vod_id):
        play_from = '播放'
        play_url = ''

        # 提取线路名称
        tab_match = re.search(r'<ul[^>]*class="[^"]*nav-tabs[^"]*"[^>]*>.*?<li[^>]*class="[^"]*active[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>', html, re.DOTALL)
        if tab_match:
            play_from = tab_match.group(1).strip()
        else:
            # 从播放器区域提取线路名
            tab_match2 = re.search(r'<li[^>]*class="[^"]*active[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>', html)
            if tab_match2:
                play_from = tab_match2.group(1).strip()

        # 提取播放列表
        playlist_match = re.search(r'<ul[^>]*class="[^"]*playlist[^"]*"[^>]*id="[^"]*"[^>]*>(.*?)</ul>', html, re.DOTALL)
        if not playlist_match:
            playlist_match = re.search(r'<ul[^>]*id="playlist_\d+"[^>]*>(.*?)</ul>', html, re.DOTALL)

        if playlist_match:
            content = playlist_match.group(1)
            link_pattern = r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
            links = re.findall(link_pattern, content)
            if links:
                parts = []
                for href, name in links:
                    name = name.strip()
                    # 提取播放ID: /mt/vodplay/478253-1-1.html -> 478253-1-1
                    vid_match = re.search(r'/vodplay/([^/"]+)\.html', href)
                    if vid_match:
                        vid = vid_match.group(1)
                        parts.append(f"{name}${vid}")
                    else:
                        # 从href提取id
                        id_match = re.search(r'/(\d+-\d+-\d+)\.html', href)
                        if id_match:
                            parts.append(f"{name}${id_match.group(1)}")
                if parts:
                    play_url = '$$$'.join(parts)

        # 如果没有播放列表，生成默认
        if not play_url:
            play_url = f'第1集${vod_id}-1-1'

        return play_from, play_url

    def _extract_title(self, html):
        title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if title_match:
            return title_match.group(1).strip()
        # 从title标签提取
        title_match2 = re.search(r'<title>([^<]+)</title>', html)
        if title_match2:
            title = title_match2.group(1).strip()
            title = re.sub(r'\s*[-|]\s*妹团优选\s*$', '', title)
            title = re.sub(r'\s*视频介绍\s*$', '', title)
            return title
        return None

    def _extract_pic(self, html):
        pic_match = re.search(r'<img[^>]*?class="[^"]*vodimg[^"]*"[^>]*src="([^"]+)"', html)
        if pic_match:
            return self._fix_url(pic_match.group(1))
        pic_match = re.search(r'<div[^>]*class="[^"]*detail-poster[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.DOTALL)
        if pic_match:
            return self._fix_url(pic_match.group(1))
        pic_match = re.search(r'<img[^>]*?src="([^"]+)"[^>]*?alt="[^"]*"', html)
        if pic_match:
            return self._fix_url(pic_match.group(1))
        return None

    def _fix_url(self, url):
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if not url.startswith('http'):
            if url.startswith('/'):
                return self.host + url
            return self.host.rstrip('/') + '/' + url.lstrip('/')
        return url