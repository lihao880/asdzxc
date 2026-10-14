# coding: utf-8
# 色狗网 - TVBox爬虫源
# 站点: https://ccc.sg888.sbs/
# 类型: WordPress成人聚合站
# 作者: AI Assistant
# 日期: 2026-07-21

import re
import json
import urllib.parse
from base.spider import Spider


class Spider(Spider):
    def __init__(self):
        self.site_url = 'https://ccc.sg888.sbs'
        
        # 分类列表（从顶部菜单提取）
        self.classes = [
            {'type_id': '742ae3', 'type_name': '中文'},
            {'type_id': 'f33dc0', 'type_name': '母狗'},
            {'type_id': '661aa4', 'type_name': '绿帽'},
            {'type_id': 'e31934', 'type_name': '淫荡'},
            {'type_id': 'e44a7a', 'type_name': '妹子'},
            {'type_id': 'cf89cb', 'type_name': '探花'},
            {'type_id': 'b63bf8', 'type_name': '奶子'},
            {'type_id': '332eb8', 'type_name': '美少女'},
            {'type_id': 'ec53aa', 'type_name': '中出'},
            {'type_id': '1a8358', 'type_name': '女神'}
        ]
        
        # 筛选器
        self.filters = {}
        for cls in self.classes:
            self.filters[cls['type_id']] = []

    def getName(self):
        return '色狗网'

    def init(self, extend=""):
        pass

    def destroy(self):
        pass

    def _fetch(self, url):
        """请求页面"""
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'zh-CN,zh;q=0.9'
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            return ''

    def _fix_url(self, url):
        if not url:
            return ''
        url = url.strip()
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.site_url + url
        if not url.startswith('http'):
            return self.site_url + '/' + url
        return url

    def _clean_text(self, text):
        if not text:
            return ''
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _parse_video_list(self, html):
        """解析视频列表"""
        videos = []
        # 匹配文章条目
        pattern = r'<article[^>]*class="[^"]*post[^"]*"[^>]*>.*?<h2[^>]*class="[^"]*post-title[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>.*?<img[^>]*src="([^"]+)"[^>]*>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for match in matches:
            url = self._fix_url(match[0])
            title = self._clean_text(match[1])
            img = match[2] if match[2].startswith('http') else self._fix_url(match[2])
            
            videos.append({
                'vod_id': url,
                'vod_name': title,
                'vod_pic': img,
                'vod_remarks': ''
            })
        
        return videos

    def homeContent(self, filter=False):
        """首页返回分类和筛选"""
        return {
            'class': self.classes,
            'filters': self.filters if filter else {}
        }

    def homeVideoContent(self):
        """首页推荐列表 - APP加载必须实现"""
        html = self._fetch(self.site_url)
        videos = self._parse_video_list(html)
        return {'list': videos[:20]}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        """分类列表"""
        try:
            pg = int(pg)
        except:
            pg = 1
        if pg < 1:
            pg = 1
        
        if pg == 1:
            url = f'{self.site_url}/s/tag/{tid}'
        else:
            url = f'{self.site_url}/s/tag/{tid}/page/{pg}'
        
        html = self._fetch(url)
        videos = self._parse_video_list(html)
        
        return {
            'list': videos,
            'page': pg,
            'pagecount': 99,
            'total': len(videos)
        }

    def detailContent(self, ids):
        """详情页"""
        if not ids:
            return {'list': []}
        
        url = ids[0] if isinstance(ids, list) else ids
        if not url.startswith('http'):
            url = self._fix_url(url)
        
        html = self._fetch(url)
        
        # 提取标题
        title_match = re.search(r'<h1[^>]*class="[^"]*post-title[^"]*"[^>]*>([^<]+)</h1>', html)
        title = self._clean_text(title_match.group(1)) if title_match else ''
        
        # 提取正文内容
        content_match = re.search(r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        content = content_match.group(1) if content_match else ''
        
        # 提取播放地址 (iframe src)
        play_url = ''
        iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"[^>]*>', content)
        if iframe_match:
            src = iframe_match.group(1)
            if '/tt/t.php?url=' in src:
                url_param = src.split('/tt/t.php?url=')[1]
                if '&' in url_param:
                    url_param = url_param.split('&')[0]
                play_url = urllib.parse.unquote(url_param)
            elif src.startswith('http'):
                play_url = src
        
        # 提取图片
        pic_match = re.search(r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*easywp-post-thumbnail[^"]*"', html)
        pic = pic_match.group(1) if pic_match else ''
        
        # 构建vod_play_url
        if play_url:
            vod_play_from = '直链'
            vod_play_url = f'直链${play_url}'
        else:
            vod_play_from = ''
            vod_play_url = ''
        
        vod = {
            'vod_id': url,
            'vod_name': title,
            'vod_pic': pic,
            'vod_play_from': vod_play_from,
            'vod_play_url': vod_play_url,
            'vod_content': self._clean_text(content)
        }
        
        return {'list': [vod]}

    def searchContent(self, key, quick=False, pg=1):
        """搜索"""
        try:
            pg = int(pg)
        except:
            pg = 1
        if pg < 1:
            pg = 1
        
        encoded_key = urllib.parse.quote(key)
        url = f'{self.site_url}/?s={encoded_key}'
        if pg > 1:
            url += f'&page={pg}'
        
        html = self._fetch(url)
        videos = self._parse_video_list(html)
        
        return {'list': videos}

    def playerContent(self, flag, id, vipFlags=None):
        """播放地址"""
        if id.startswith('http'):
            return {'parse': 0, 'playUrl': '', 'url': id}
        else:
            url = self._fix_url(id)
            return {'parse': 0, 'playUrl': '', 'url': url}