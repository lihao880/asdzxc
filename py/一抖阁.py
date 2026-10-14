# -*- coding: utf-8 -*-
import re
import json
import base64
import urllib.parse
from bs4 import BeautifulSoup
import requests


class Spider:
    def __init__(self):
        self.host = "https://yidouge.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/',
            'Cookie': '_ga=GA1.1.1532488156.1787153147; gv_age_verified=1;',
        }
        self.classes = [
            {"type_id": "v2/ai短剧", "type_name": "AI短剧"},
            {"type_id": "v2/伦理绿帽ntr", "type_name": "伦理绿帽NTR"},
            {"type_id": "v2/动漫短剧", "type_name": "动漫短剧"},
            {"type_id": "v2/古装", "type_name": "古装"},
            {"type_id": "v2/奇幻", "type_name": "奇幻"},
            {"type_id": "v2/小说同人", "type_name": "小说影视剧同人"},
            {"type_id": "v2/微恐", "type_name": "微恐"},
            {"type_id": "v2/都市", "type_name": "现代"},
            {"type_id": "v2/短篇", "type_name": "短篇"},
            {"type_id": "v2/穿越", "type_name": "穿越"},
            {"type_id": "v2/重生", "type_name": "重生"},
            {"type_id": "v2/pmv", "type_name": "PMV"},
            {"type_id": "v2/ai风格pmv", "type_name": "AI风格PMV"},
            {"type_id": "v2/avjuqing", "type_name": "AV剧情剪辑"},
            {"type_id": "v2/b站舞蹈", "type_name": "B站舞蹈"},
            {"type_id": "v2/dfpmv", "type_name": "KPOP深度换脸"},
            {"type_id": "v2/mmd动画", "type_name": "MMD动画"},
            {"type_id": "v2/cunzhi", "type_name": "寸止挑战"},
            {"type_id": "v2/dyhunjian", "type_name": "抖音混剪"},
            {"type_id": "v2/拼接跳转", "type_name": "拼接跳转"},
            {"type_id": "v2/oumeipmv", "type_name": "欧美PMV"},
            {"type_id": "v2/wudaopmv", "type_name": "舞蹈"},
            {"type_id": "v2/魔改影视剧", "type_name": "魔改影视剧"},
            {"type_id": "v2/魔改电影电视剧", "type_name": "魔改电影电视剧"},
            {"type_id": "v2/魔改综艺", "type_name": "魔改综艺"},
            {"type_id": "v2/明星二创", "type_name": "名人二创"},
            {"type_id": "v2/明星换脸", "type_name": "明星换脸"},
            {"type_id": "v2/明星去衣", "type_name": "明星短剧去衣"},
            {"type_id": "v2/网红去衣", "type_name": "网红去衣"},
            {"type_id": "v2/vam动画-漫画", "type_name": "VAM动画"},
            {"type_id": "v1/国产", "type_name": "国产"},
            {"type_id": "v1/91大神", "type_name": "91大神"},
            {"type_id": "v1/国产订阅博主", "type_name": "国产订阅博主"},
            {"type_id": "v1/泄露门事件", "type_name": "泄露门事件"},
            {"type_id": "v1/绿帽ntr", "type_name": "绿帽NTR"},
            {"type_id": "v1/萝莉福利姬-国产", "type_name": "萝莉福利姬"},
            {"type_id": "v1/调教sm", "type_name": "调教SM"},
            {"type_id": "v1/里番", "type_name": "里番"},
        ]
        self.filters = {}

    def _pic(self, url):
        """图片处理：将 webp 转为 jpg，通过 weserv.nl 代理"""
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            url = "https:" + url
        if "images.weserv.nl" in url:
            return url
        if url.endswith(".webp") or "webp" in url.lower():
            # 使用 weserv.nl 将 webp 转换为 jpg
            return "https://images.weserv.nl/?url=" + url + "&output=jpg"
        return url

    def fetch(self, url, headers=None, timeout=15):
        try:
            headers = headers or self.headers
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            resp = requests.get(url, headers=headers, timeout=timeout, verify=False)
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
        return self._pic(pic_url)

    def _extract_vod_id(self, url):
        if not url:
            return ''
        m = re.search(r'/video/([^/?#]+)', url)
        if m:
            return m.group(1)
        m = re.search(r'/creator/([^/?#]+)', url)
        if m:
            return 'creator_' + m.group(1)
        return url

    def _is_creator(self, vid):
        return vid.startswith('creator_')

    def _get_creator_slug(self, vid):
        return vid[8:] if vid.startswith('creator_') else vid

    def _parse_video_card(self, card):
        a = card.find('a', class_='video-card__link', href=True)
        if not a:
            return None
        href = a.get('href', '')
        vid = self._extract_vod_id(href)
        if not vid:
            return None
        title_tag = card.find('h2', class_='video-card__title')
        title = title_tag.text.strip() if title_tag else ''
        if not title:
            title_el = card.find('a', class_='video-card__body-link')
            if title_el:
                title = title_el.text.strip()
        img = card.find('img')
        if img:
            # 优先使用 data-static-src 或 data-hover-src
            pic = img.get('data-static-src') or img.get('data-hover-src') or img.get('src') or img.get('data-src', '')
        else:
            pic = ''
        pic = self.fix_url(pic)
        if pic:
            pic = self._make_proxy_url(pic)
        remark = ''
        label = card.find('span', class_='video-card__label')
        if label:
            remark = label.text.strip()
        duration = card.find('span', class_='video-card__duration')
        if duration:
            if remark:
                remark += ' ' + duration.text.strip()
            else:
                remark = duration.text.strip()
        views_tag = card.find('span', class_='video-card__meta-views')
        if views_tag:
            views = views_tag.text.strip()
            if remark:
                remark += ' ' + views
            else:
                remark = views
        if vid and title:
            return {
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remark
            }
        return None

    def _parse_creator_card(self, card):
        a = card.find('a', href=True)
        if not a:
            return None
        href = a.get('href', '')
        vid = self._extract_vod_id(href)
        if not vid or not vid.startswith('creator_'):
            return None
        title_el = card.find('strong', class_='ydg-author-collection-title')
        title = title_el.text.strip() if title_el else ''
        if not title:
            title_a = card.find('a', class_='ydg-author-collection-body')
            if title_a:
                title = title_a.text.strip()
        covers = card.find_all('img', class_='ydg-author-collection-cover')
        pic = ''
        if covers:
            pic = covers[0].get('src') or covers[0].get('data-src', '')
            pic = self.fix_url(pic)
            if pic:
                pic = self._make_proxy_url(pic)
        remark = ''
        subcat = card.find('a', class_='video-card__subcategory')
        if subcat:
            remark = subcat.text.strip()
        meta = card.find('span', class_='ydg-author-collection-meta')
        if meta:
            meta_text = meta.text.strip()
            if remark:
                remark += ' ' + meta_text
            else:
                remark = meta_text
        if vid and title:
            return {
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remark
            }
        return None

    def _parse_videos_from_html(self, html, limit=100):
        doc = BeautifulSoup(html, 'html.parser')
        videos = []
        cards = doc.find_all('article', class_='video-card')
        for card in cards:
            if card.find('div', class_='ydg-author-collection-link'):
                item = self._parse_creator_card(card)
            else:
                item = self._parse_video_card(card)
            if item:
                videos.append(item)
                if len(videos) >= limit:
                    break
        return videos

    def homeContent(self, filter=False):
        result = {'class': self.classes, 'filters': self.filters if filter else {}}
        html = self.get_html(self.host + '/')
        if html:
            result['list'] = self._parse_videos_from_html(html, 30)
        else:
            result['list'] = []
        return result

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self.get_html(self.host + '/')
        if html:
            videos = self._parse_videos_from_html(html, 20)
            return {'list': videos}
        return {'list': []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        page_param = '' if pg <= 1 else f'/page/{pg}/'
        url = self.host + '/' + tid + page_param
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        videos = self._parse_videos_from_html(html, 50)
        pagecount = 1
        doc = BeautifulSoup(html, 'html.parser')
        pagination = doc.find('div', class_=re.compile(r'pagination|page-numbers'))
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
        if self._is_creator(vid):
            return self._creator_detail(vid)
        url = self.host + '/video/' + vid + '/'
        html = self.get_html(url)
        if not html:
            return {'list': []}
        doc = BeautifulSoup(html, 'html.parser')
        title = ''
        title_el = doc.find('h1', class_=re.compile(r'entry-title|video-title'))
        if title_el:
            title = title_el.text.strip()
        if not title:
            title_el = doc.find('h1')
            if title_el:
                title = title_el.text.strip()
        pic = ''
        img = doc.find('img', class_=re.compile(r'wp-post-image|featured-image'))
        if img:
            pic = img.get('src') or img.get('data-src', '')
            pic = self.fix_url(pic)
            if pic:
                pic = self._make_proxy_url(pic)
        if not pic:
            article = doc.find('article')
            if article:
                img = article.find('img')
                if img:
                    pic = img.get('src') or img.get('data-src', '')
                    pic = self.fix_url(pic)
                    if pic:
                        pic = self._make_proxy_url(pic)
        desc = ''
        desc_el = doc.find('div', class_=re.compile(r'entry-content|video-description|content'))
        if desc_el:
            desc = desc_el.text.strip()[:500]
        play_url = ''
        # 从 JSON-LD 提取 contentUrl
        script_match = re.search(r'"contentUrl"\s*:\s*"([^"]+)"', html)
        if script_match:
            play_url = self.fix_url(script_match.group(1))
        if not play_url:
            video_tag = doc.find('video')
            if video_tag:
                src = video_tag.get('src', '')
                if src:
                    play_url = self.fix_url(src)
        if not play_url:
            iframe = doc.find('iframe')
            if iframe:
                src = iframe.get('src', '')
                if src:
                    play_url = self.fix_url(src)
        if not play_url:
            script_match = re.search(r'videoSrc\s*[:=]\s*["\']([^"\']+)["\']', html)
            if script_match:
                play_url = self.fix_url(script_match.group(1))
        if not play_url:
            m3u8_match = re.search(r'["\']([^"\']+\.m3u8[^"\']*)["\']', html)
            if m3u8_match:
                play_url = self.fix_url(m3u8_match.group(1))
        if not play_url:
            mp4_match = re.search(r'["\']([^"\']+\.mp4[^"\']*)["\']', html)
            if mp4_match:
                play_url = self.fix_url(mp4_match.group(1))
        if play_url:
            play_from = '默认线路'
            play_url_str = '播放$' + play_url
        else:
            play_from = '默认线路'
            play_url_str = '播放$' + vid
        data = {
            'vod_id': vid,
            'vod_name': title or '未知视频',
            'vod_pic': pic,
            'vod_content': desc,
            'vod_play_from': play_from,
            'vod_play_url': play_url_str,
        }
        return {'list': [data]}

    def _creator_detail(self, vid):
        slug = self._get_creator_slug(vid)
        url = self.host + '/creator/' + slug + '/'
        html = self.get_html(url)
        if not html:
            return {'list': []}
        doc = BeautifulSoup(html, 'html.parser')
        title = ''
        title_el = doc.find('h1')
        if title_el:
            title = title_el.text.strip()
        pic = ''
        img = doc.find('img', class_=re.compile(r'cover|featured'))
        if img:
            pic = img.get('src') or img.get('data-src', '')
            pic = self.fix_url(pic)
            if pic:
                pic = self._make_proxy_url(pic)
        videos = self._parse_videos_from_html(html, 100)
        if videos:
            play_from = '合集播放'
            play_url_parts = []
            for v in videos:
                play_url_parts.append(f"{v['vod_name']}${v['vod_id']}")
            play_url_str = '#'.join(play_url_parts)
        else:
            play_from = '合集播放'
            play_url_str = ''
        data = {
            'vod_id': vid,
            'vod_name': title or '未知合集',
            'vod_pic': pic,
            'vod_content': f'共 {len(videos)} 个视频',
            'vod_play_from': play_from,
            'vod_play_url': play_url_str,
        }
        return {'list': [data]}

    def searchContent(self, key, quick=False, pg='1'):
        if not key:
            return {'list': [], 'page': 1, 'pagecount': 1, 'total': 0}
        pg = int(pg) if pg else 1
        url = self.host + '/?s=' + urllib.parse.quote(key) + '&post_type=video'
        if pg > 1:
            url += '&paged=' + str(pg)
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        videos = self._parse_videos_from_html(html, 50)
        return {
            'list': videos,
            'page': pg,
            'pagecount': 99,
            'total': 999
        }

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {'parse': 1, 'url': ''}
        if id.startswith('pics://'):
            return {'parse': 1, 'url': id}
        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/',
            'Cookie': self.headers.get('Cookie', ''),
        }
        if id.startswith('http') and ('video/' in id or '/video?' in id):
            html = self.get_html(id)
            if html:
                m = re.search(r'"contentUrl"\s*:\s*"([^"]+)"', html)
                if m:
                    url = self.fix_url(m.group(1))
                    if url.endswith('.mp4') or url.endswith('.m3u8'):
                        return {'parse': 0, 'url': url, 'header': headers}
                m = re.search(r'videoSrc\s*[:=]\s*["\']([^"\']+)["\']', html)
                if m:
                    url = self.fix_url(m.group(1))
                    if url.endswith('.mp4') or url.endswith('.m3u8'):
                        return {'parse': 0, 'url': url, 'header': headers}
                m = re.search(r'<video[^>]*src=["\']([^"\']+)["\']', html)
                if m:
                    url = self.fix_url(m.group(1))
                    if url.endswith('.mp4') or url.endswith('.m3u8'):
                        return {'parse': 0, 'url': url, 'header': headers}
        if id.startswith('http') and (id.endswith('.mp4') or id.endswith('.m3u8')):
            return {'parse': 0, 'url': id, 'header': headers}
        if not id.startswith('http'):
            url = self.host + '/video/' + id + '/'
            html = self.get_html(url)
            if html:
                m = re.search(r'"contentUrl"\s*:\s*"([^"]+)"', html)
                if m:
                    play_url = self.fix_url(m.group(1))
                    if play_url.endswith('.mp4') or play_url.endswith('.m3u8'):
                        return {'parse': 0, 'url': play_url, 'header': headers}
                m = re.search(r'videoSrc\s*[:=]\s*["\']([^"\']+)["\']', html)
                if m:
                    play_url = self.fix_url(m.group(1))
                    if play_url.endswith('.mp4') or play_url.endswith('.m3u8'):
                        return {'parse': 0, 'url': play_url, 'header': headers}
        return {'parse': 1, 'url': id, 'header': headers}

    def localProxy(self, params):
        type_ = params.get('type', '')
        url = params.get('url', '')
        if type_ == 'img' and url:
            try:
                pic_url = base64.b64decode(url).decode()
                resp = requests.get(pic_url, headers=self.headers, timeout=30)
                if resp.status_code == 200:
                    content = resp.content
                    if content.startswith(b'\xff\xd8\xff') or content.startswith(b'\x89PNG') or content.startswith(b'GIF8'):
                        content_type = 'image/jpeg' if content.startswith(b'\xff\xd8\xff') else ('image/png' if content.startswith(b'\x89PNG') else 'image/gif')
                        return [200, content_type, content]
                    content_type = resp.headers.get('Content-Type', 'image/jpeg')
                    return [200, content_type, content]
                return [404, 'text/plain', b'Image not found']
            except Exception as e:
                print('localProxy error:', e)
                return [500, 'text/plain', b'Proxy error']
        return [404, 'text/plain', b'Not Found']

    def init(self, extend=''):
        pass

    def destroy(self):
        pass

    def getDependence(self):
        return ['requests', 'bs4']

    def getName(self):
        return '一抖阁'