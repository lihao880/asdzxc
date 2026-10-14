# -*- coding: utf-8 -*-
import re
import json
import base64
import urllib.parse
import requests
from bs4 import BeautifulSoup


class Spider:
    def __init__(self):
        self.host = "https://xn--62w985dzpl.llbdyy.buzz"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/',
        }
        self.classes = [
            {"type_id": "2101", "type_name": "国产自拍"},
            {"type_id": "2102", "type_name": "中文字幕"},
            {"type_id": "2103", "type_name": "亚洲无码"},
            {"type_id": "2104", "type_name": "亚洲有码"},
            {"type_id": "2105", "type_name": "美女主播"},
            {"type_id": "2106", "type_name": "激情欧美"},
            {"type_id": "2107", "type_name": "成人动漫"},
            {"type_id": "2108", "type_name": "人妻熟女"},
            {"type_id": "2111", "type_name": "重口味"},
            {"type_id": "2112", "type_name": "强奸乱伦"},
            {"type_id": "2113", "type_name": "巨乳爆乳"},
            {"type_id": "2114", "type_name": "制服丝袜"},
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
        m = re.search(r'[?&]vid=([^&]+)', url)
        if m:
            return m.group(1)
        return url

    def _parse_videos(self, doc, limit=20):
        videos = []
        for fig in doc.find_all('div', class_='video'):
            a = fig.find('a', href=True)
            if not a:
                continue
            href = a.get('href', '')
            vid = self._extract_vod_id(href)
            if not vid:
                continue

            title = ''
            t = fig.find('span', class_='video-titulo')
            if t:
                title = t.text.strip()
            if not title:
                title = a.get('title', '') or a.text.strip()

            img = fig.find('img')
            pic = img.get('data-src') or img.get('src', '') if img else ''
            pic = self.fix_url(pic)

            remark = ''
            s = fig.find('span', class_='selo-tempo')
            if s:
                remark = s.text.strip()

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

    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except:
                pass
            result = {}
            for part in extend.split(','):
                if '=' in part:
                    k, v = part.split('=', 1)
                    result[k.strip()] = v.strip()
            return result
        return {}

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
            videos = self._parse_videos(doc, 20)
            return {'list': videos}
        except Exception as e:
            print('homeVideoContent error:', e)
            return {'list': []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        url = self.host + '/?tid=' + str(tid)
        if pg > 1:
            url += '&page=' + str(pg)
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}

        doc = BeautifulSoup(html, 'html.parser')
        videos = self._parse_videos(doc, 20)

        pagecount = 999
        pagination = doc.find('ul', class_='paginacao')
        if pagination:
            for a in pagination.find_all('a'):
                if a.text.strip().isdigit():
                    num = int(a.text.strip())
                    if num > pagecount:
                        pagecount = num

        return {'list': videos, 'page': pg, 'pagecount': pagecount, 'limit': 20, 'total': pagecount * 20}

    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        vid = str(ids[0])
        url = self.host + '/?vid=' + vid
        html = self.get_html(url)
        if not html:
            return {'list': []}

        doc = BeautifulSoup(html, 'html.parser')

        title = ''
        t = doc.find('h1', class_='post-titulo')
        if t:
            title = t.text.strip()

        pic = ''
        img = doc.find('img', class_='thumb')
        if img:
            pic = img.get('data-src') or img.get('src', '')
            pic = self.fix_url(pic)

        desc = ''

        # 提取播放地址
        play_url = ''
        m = re.search(r'var\s+playUrl\s*=\s*["\']([^"\']+)["\']', html)
        if m:
            play_url = m.group(1)
        if not play_url:
            m = re.search(r'["\']([^"\']+\.m3u8)["\']', html)
            if m:
                play_url = m.group(1)

        if play_url:
            play_from = '默认线路'
            play_url_str = '播放$' + play_url
        else:
            play_from = '默认线路'
            play_url_str = '播放$' + vid

        data = {
            'vod_id': vid,
            'vod_name': title or '未知标题',
            'vod_pic': pic,
            'vod_content': desc,
            'vod_play_from': play_from,
            'vod_play_url': play_url_str,
        }
        return {'list': [data]}

    def searchContent(self, key, quick=False, pg='1'):
        if not key:
            return {'list': [], 'page': 1}
        pg = int(pg) if pg else 1
        url = self.host + '/?kw=' + urllib.parse.quote(key)
        if pg > 1:
            url += '&page=' + str(pg)
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg}

        doc = BeautifulSoup(html, 'html.parser')
        videos = self._parse_videos(doc, 20)

        return {'list': videos, 'page': pg}

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {'parse': 1, 'url': ''}

        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/',
        }

        # 如果是直链 m3u8 或 mp4，直接返回 parse:0
        if id.startswith('http'):
            if id.endswith('.m3u8') or id.endswith('.mp4') or '.m3u8?' in id:
                return {'parse': 0, 'url': id, 'header': headers}

            # 尝试从页面中提取播放地址
            html = self.get_html(id)
            if html:
                m = re.search(r'var\s+playUrl\s*=\s*["\']([^"\']+)["\']', html)
                if m:
                    url = m.group(1)
                    if url.endswith('.m3u8') or url.endswith('.mp4'):
                        return {'parse': 0, 'url': url, 'header': headers}

        # 降级：交给壳端嗅探
        return {'parse': 1, 'url': id, 'header': headers}

    def recommendContent(self, ids, pg):
        """相关推荐"""
        if not ids:
            return {'list': []}
        vid = str(ids[0])
        url = self.host + '/?vid=' + vid
        html = self.get_html(url)
        if not html:
            return {'list': []}

        doc = BeautifulSoup(html, 'html.parser')
        videos = []

        for fig in doc.find_all('div', class_='video'):
            a = fig.find('a', href=True)
            if not a:
                continue
            href = a.get('href', '')
            vid_rec = self._extract_vod_id(href)
            if not vid_rec or vid_rec == vid:
                continue

            title = ''
            t = fig.find('span', class_='video-titulo')
            if t:
                title = t.text.strip()
            if not title:
                title = a.get('title', '') or a.text.strip()

            img = fig.find('img')
            pic = img.get('data-src') or img.get('src', '') if img else ''
            pic = self.fix_url(pic)

            remark = ''
            s = fig.find('span', class_='selo-tempo')
            if s:
                remark = s.text.strip()

            if vid_rec and title:
                videos.append({
                    'vod_id': vid_rec,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })

        return {'list': videos}

    def init(self, extend=''):
        pass

    def destroy(self):
        pass

    def getDependence(self):
        return ['requests', 'bs4']

    def getName(self):
        return '撸撸宝典'