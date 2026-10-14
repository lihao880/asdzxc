# -*- coding: utf-8 -*-
import re
import sys
import json
import requests
from urllib.parse import urljoin, urlencode, quote

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=""):
        """初始化爬蟲"""
        pass

    def getName(self):
        """返回網站名稱"""
        return "AVJOY"

    def isVideoFormat(self, url):
        """判斷是否為視頻格式"""
        return False

    def manualVideoCheck(self):
        """手動視頻檢查"""
        pass

    def destroy(self):
        """銷毀爬蟲"""
        pass

    # ==================== 配置區域 ====================
    host = 'https://avjoy.me'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
        'Connection': 'keep-alive',
    }
    
    # 分類映射
    default_classes = [
        {'type_name': '最新', 'type_id': 'latest'},
        {'type_name': '最受欢迎', 'type_id': 'popular'},
        {'type_name': '日本AV', 'type_id': 'jav'},
        {'type_name': '中国', 'type_id': 'china'},
        {'type_name': '无码', 'type_id': 'uncensored'},
    ]
    
    # ==================== 工具函數 ====================
    
    def _normalize_url(self, url):
        """標準化URL"""
        if not url:
            return ''
        url = str(url).strip()
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        if not url.startswith('http'):
            return 'https://' + url
        return url

    def _fetch_html(self, url):
        """獲取HTML內容"""
        try:
            rsp = requests.get(url, headers=self.headers, timeout=10)
            if rsp.status_code == 200:
                return rsp.text
        except Exception as e:
            print(f'獲取HTML失敗: {e}')
        return ''

    def _extract_videos(self, html):
        """從HTML中提取視頻列表 - 通用方法"""
        videos = []
        try:
            # 匹配視頻卡片的正則表達式
            pattern = r'<div[^>]*class=\"[^\"]*col-6[^\"]*\"[^>]*>.*?<a[^>]*href=\"(/video/(\d+)[^\"]*)\"[^>]*>.*?<img[^>]*src=\"([^\"]+)\"[^>]*>.*?<span[^>]*class=\"content-title\"[^>]*>(.*?)</span>.*?<div[^>]*class=\"duration\"[^>]*>(.*?)</div>'
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                video_url, vid, pic, title, duration = match
                # 清理HTML標籤
                title = re.sub(r'<[^>]+>', '', title).strip()
                duration = re.sub(r'<[^>]+>', '', duration).strip()
                
                videos.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': self._normalize_url(pic),
                    'vod_remarks': duration
                })
        except Exception as e:
            print(f'提取視頻列表失敗: {e}')
        return videos

    def _extract_detail(self, html, vid):
        """從詳情頁提取信息"""
        detail = {}
        try:
            # 提取標題
            title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ''
            
            # 提取封面 - 多種匹配方式
            pic = ''
            # 方式1: 從 thumb-overlay 中提取
            pic_match = re.search(r'<div[^>]*class=\"[^\"]*thumb-overlay[^\"]*\"[^>]*>.*?<img[^>]*src=\"([^\"]+)\"[^>]*>', html, re.DOTALL | re.IGNORECASE)
            if not pic_match:
                # 方式2: 從 og:image meta 標籤提取
                pic_match = re.search(r'<meta[^>]*property=\"og:image\"[^>]*content=\"([^\"]+)\"', html, re.IGNORECASE)
            if not pic_match:
                # 方式3: 從 player div 中提取
                pic_match = re.search(r'<div[^>]*class=\"[^\"]*player[^\"]*\"[^>]*>.*?<img[^>]*src=\"([^\"]+)\"[^>]*>', html, re.DOTALL | re.IGNORECASE)
            
            pic = self._normalize_url(pic_match.group(1)) if pic_match else ''
            
            # 提取描述
            desc_match = re.search(r'<div[^>]*class=\"[^\"]*video-description[^\"]*\"[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
            description = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip() if desc_match else ''
            
            # 提取播放地址 - 優先匹配video標籤
            play_url = ''
            video_match = re.search(r'<video[^>]*>.*?<source[^>]*src=\"([^\"]+)\"[^>]*>', html, re.DOTALL | re.IGNORECASE)
            if video_match:
                play_url = video_match.group(1)
            else:
                # 嘗試匹配iframe
                iframe_match = re.search(r'<iframe[^>]*src=\"([^\"]+)\"[^>]*>', html, re.IGNORECASE)
                if iframe_match:
                    play_url = iframe_match.group(1)
            
            play_url = self._normalize_url(play_url) if play_url else ''
            
            detail = {
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_content': description,
                'vod_play_url': play_url
            }
        except Exception as e:
            print(f'提取詳情信息失敗: {e}')
        return detail

    # ==================== 核心方法 ====================
    
    def homeContent(self, filter):
        """獲取首頁內容"""
        result = {}
        try:
            html = self._fetch_html(self.host)
            if html:
                videos = self._extract_videos(html)
                result['list'] = videos
                result['class'] = self.default_classes
        except Exception as e:
            print(f'homeContent錯誤: {e}')
        return result

    def categoryContent(self, tid, pg, filter, extend):
        """獲取分類內容"""
        result = {}
        page = int(pg) if pg else 1
        try:
            # 構建分類URL
            if tid == 'latest':
                url = f'{self.host}/videos?o=mr&page={page}'
            elif tid == 'popular':
                url = f'{self.host}/videos?o=mv&page={page}'
            else:
                url = f'{self.host}/videos/{tid}?page={page}'
            
            html = self._fetch_html(url)
            if html:
                videos = self._extract_videos(html)
                result['list'] = videos
                result['page'] = str(page)
                result['pagecount'] = '9999'
                result['limit'] = '30'
                result['total'] = '99999'
        except Exception as e:
            print(f'categoryContent錯誤: {e}')
        return result

    def detailContent(self, ids):
        """獲取詳情內容"""
        result = {}
        videos = []
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            url = f'{self.host}/video/{vid}'
            
            html = self._fetch_html(url)
            if html:
                detail = self._extract_detail(html, vid)
                if detail:
                    detail['vod_play_from'] = 'avjoy'
                    detail['vod_play_url'] = f'{detail.get("vod_name", "")}${detail.get("vod_play_url", "")}'
                    videos.append(detail)
                result['list'] = videos
        except Exception as e:
            print(f'detailContent錯誤: {e}')
        return result

    def searchContent(self, keyword, pg):
        """搜索內容 - 基於實際頁面結構優化"""
        result = {}
        videos = []
        try:
            # 使用 quote 進行URL編碼，確保中文正確處理
            encoded_keyword = quote(keyword)
            # 按照實際頁面格式構建URL
            url = f'{self.host}/search/videos/{encoded_keyword}?page={pg}'
            print(f'搜索URL: {url}')
            
            html = self._fetch_html(url)
            if not html:
                print('搜索頁面獲取失敗')
                return result
            
            # 保存HTML用於調試（可選）
            # with open('/sdcard/AiHelper/workspace/spider/search_debug.html', 'w', encoding='utf-8') as f:
            #     f.write(html)
            
            # 從實際頁面結構中提取視頻列表
            # 頁面結構: <div class="col-6 col-sm-6 col-md-4 col-lg-4 col-xl-3"> ... </div>
            pattern = r'<div[^>]*class=\"[^\"]*col-6[^\"]*\"[^>]*>.*?<a[^>]*href=\"(/video/(\d+)[^\"]*)\"[^>]*>.*?<img[^>]*src=\"([^\"]+)\"[^>]*>.*?<span[^>]*class=\"content-title\"[^>]*>(.*?)</span>.*?<div[^>]*class=\"duration\"[^>]*>(.*?)</div>'
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            
            if matches:
                print(f'找到 {len(matches)} 個搜索結果')
                for match in matches:
                    video_url, vid, pic, title, duration = match
                    # 清理HTML標籤
                    title = re.sub(r'<[^>]+>', '', title).strip()
                    duration = re.sub(r'<[^>]+>', '', duration).strip()
                    
                    videos.append({
                        'vod_id': vid,
                        'vod_name': title,
                        'vod_pic': self._normalize_url(pic),
                        'vod_remarks': duration
                    })
            else:
                print('沒有找到搜索結果')
            
            result['list'] = videos
            print(f'搜索完成，共 {len(videos)} 個結果')
            
        except Exception as e:
            print(f'searchContent錯誤: {e}')
            import traceback
            traceback.print_exc()
            
        return result

    def playerContent(self, flag, id, vipFlags):
        """獲取播放地址（修復5秒問題）"""
        result = {}
        try:
            # 如果 id 已經是完整URL，直接返回
            if id.startswith('http'):
                result['parse'] = 0
                result['url'] = id
                # 添加完整的請求頭，防止盜鏈
                result['header'] = {
                    'User-Agent': self.headers['User-Agent'],
                    'Referer': self.host + '/',
                    'Origin': self.host,
                    'Accept': '*/*',
                    'Range': 'bytes=0-',
                    'Connection': 'keep-alive',
                }
            else:
                # 否則從詳情頁獲取播放地址
                detail = self.detailContent([id])
                if detail and detail.get('list'):
                    play_url = detail['list'][0].get('vod_play_url', '')
                    if play_url and '$' in play_url:
                        result['parse'] = 0
                        result['url'] = play_url.split('$')[-1]
                        # 添加完整的請求頭，防止盜鏈
                        result['header'] = {
                            'User-Agent': self.headers['User-Agent'],
                            'Referer': self.host + '/',
                            'Origin': self.host,
                            'Accept': '*/*',
                            'Range': 'bytes=0-',
                            'Connection': 'keep-alive',
                        }
        except Exception as e:
            print(f'playerContent錯誤: {e}')
        return result