# -*- coding: utf-8 -*-
import re
import sys
import json
from pyquery import PyQuery as pq
from urllib.parse import urljoin, urlparse
import random

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    
    def init(self, extend=""):
        pass
    
    def getName(self):
        return "DXLive直播"
    
    def isVideoFormat(self, url):
        pass
    
    def manualVideoCheck(self):
        pass
    
    def destroy(self):
        pass
    
    # ------------------------- 网站配置 -------------------------
    host = 'https://mobile.dxlive.com'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
        'Referer': 'https://mobile.dxlive.com/',
    }
    
    # 流媒体服务器域名列表
    STREAM_DOMAINS = [
        'stream1224.dxlive.com',
        'stream.dxlive.com',
        'live.dxlive.com',
        'video.dxlive.com',
        'edge.dxlive.com'
    ]
    
    # ------------------------- 通用工具方法 -------------------------
    def _normalize_url(self, url):
        """标准化URL：处理相对路径、协议缺失等"""
        if not url:
            return url
        if url.startswith('//'):
            return f"https:{url}"
        elif url.startswith('/'):
            return urljoin(self.host, url)
        return url
    
    def _extract_performer_id(self, url):
        """从URL提取主播ID"""
        if not url:
            return ''
        match = re.search(r'mobilePreview/([^/]+)', url)
        return match.group(1) if match else url.split('/')[-1]
    
    def _extract_channel_id(self, html):
        """从HTML中提取channel_id"""
        # 方法1: 查找data属性中的channel_id
        patterns = [
            r'channel_id["\']?\s*[:=]\s*["\']?(\d+)["\']?',
            r'channelId["\']?\s*[:=]\s*["\']?(\d+)["\']?',
            r'data-channel-id=["\'](\d+)["\']',
            r'data-channel=["\'](\d+)["\']',
            r'"channel_id":\s*(\d+)',
            r'"channelId":\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # 方法2: 从已有的播放地址中提取（如果是详情页）
        match = re.search(r'/free-preview/(\d+)/', html)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_video_basic(self, item):
        """从列表项提取主播基本信息"""
        try:
            # 获取链接和主播ID
            link_elem = item('a')
            link = self._normalize_url(link_elem.attr('href'))
            if not link:
                return None
            
            performer_id = self._extract_performer_id(link)
            
            # 提取主播名
            name_elem = item('.pf-name')
            title = name_elem.text().strip() or performer_id or '未知主播'
            
            # 提取图片
            img_elem = item('img')
            img = self._normalize_url(img_elem.attr('src') or img_elem.attr('data-src'))
            
            # 提取状态
            status_elem = item('.pf-status-sec')
            status = status_elem.text().strip() if status_elem else ''
            
            # 提取留言
            msg_elem = item('.thumbnail-message')
            message = msg_elem.text().strip() if msg_elem else ''
            
            # 提取观看人数
            viewers_elem = item('.icon-vw')
            viewers = viewers_elem.text().strip() if viewers_elem else '0'
            
            # 提取channel_id (可能存储在data属性中)
            channel_id = item.attr('data-channel-id') or item.attr('data-channel')
            
            # 组合备注信息
            remarks = f"{status}"
            if message:
                remarks += f" | {message}"
            if viewers != '0':
                remarks += f" | 👥{viewers}"
            
            vod_data = {
                'vod_id': link,  # 详情页URL
                'vod_name': title,
                'vod_pic': img or '',
                'vod_remarks': remarks,
                'vod_year': '',
                'vod_content': message
            }
            
            # 如果有channel_id，保存到vod_custom
            if channel_id:
                vod_data['vod_custom'] = json.dumps({'channel_id': channel_id})
            
            return vod_data
        except Exception as e:
            return None
    
    def getpq(self, text):
        """创建PyQuery对象，处理编码问题"""
        try:
            return pq(text)
        except:
            try:
                return pq(text.encode('utf-8'))
            except:
                return pq('')
    
    def _build_stream_url(self, channel_id):
        """构建流媒体播放地址"""
        if not channel_id:
            return None
        
        # 随机选择一个流媒体服务器
        stream_domain = random.choice(self.STREAM_DOMAINS)
        
        # 生成随机数（模拟原URL中的w1525455231）
        random_num = random.randint(100000000, 999999999)
        
        # 构建标准格式的URL
        stream_url = f"https://{stream_domain}/free-preview/{channel_id}/chunklist_w{random_num}.m3u8"
        
        return stream_url
    
    # ------------------------- 主要功能方法 -------------------------
    def homeContent(self, filter):
        """首页：分类 + 推荐列表"""
        try:
            response = self.fetch(self.host + '/zh-Hant/home', headers=self.headers)
            data = self.getpq(response.text)
            
            # 提取分类（从筛选按钮）
            classes = []
            filter_buttons = data('.thumbnail-filters-sec button')
            for item in filter_buttons.items():
                value = item.attr('value')
                name = item.text().strip()
                if value and name and value not in ['newPerformer', 'starPerformer']:
                    # 构建分类URL（假设分类通过URL参数实现）
                    class_url = f"{self.host}/zh-Hant/home?filter={value}"
                    classes.append({'type_name': name, 'type_id': class_url})
            
            # 如果没提取到分类，添加默认分类
            if not classes:
                default_classes = [
                    {'type_name': '新人', 'type_id': f"{self.host}/zh-Hant/home?filter=newPerformer"},
                    {'type_name': '人氣', 'type_id': f"{self.host}/zh-Hant/home?filter=starPerformer"},
                    {'type_name': '有玩具', 'type_id': f"{self.host}/zh-Hant/home?filter=hasToy"},
                    {'type_name': '熟女', 'type_id': f"{self.host}/zh-Hant/home?filter=milf"},
                    {'type_name': '待機中', 'type_id': f"{self.host}/zh-Hant/home?filter=standby"},
                ]
                classes.extend(default_classes)
            
            # 首页推荐列表
            videos = self._get_online_list(data)
            
            return {'class': classes, 'list': videos}
        except Exception as e:
            return {'class': [], 'list': []}
    
    def _get_online_list(self, data):
        """提取在线主播列表"""
        videos = []
        # 主播列表容器
        items = data('#online-thumbnail-sec li')
        for item in items.items():
            video_info = self._extract_video_basic(item)
            if video_info:
                videos.append(video_info)
        return videos
    
    def categoryContent(self, tid, pg, filter, extend):
        """分类页内容"""
        try:
            # 处理分页
            url = tid
            if pg != '1':
                if '?' in url:
                    url = f"{url}&page={pg}"
                else:
                    url = f"{url}/page/{pg}"
            
            response = self.fetch(url, headers=self.headers)
            data = self.getpq(response.text)
            
            videos = self._get_online_list(data)
            
            return {
                'list': videos,
                'page': int(pg),
                'pagecount': 9999,  # 假设无限滚动/多页
                'limit': 30,
                'total': 999999
            }
        except Exception as e:
            return {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': 30, 'total': 0}
    
    def detailContent(self, ids):
        """详情页：提取主播详情"""
        try:
            first_id = next(iter(ids)) if hasattr(ids, '__iter__') and not isinstance(ids, str) else ids
            
            response = self.fetch(first_id, headers=self.headers)
            html_text = response.text
            data = self.getpq(html_text)
            
            # 提取主播名
            name = data('.pf-name').text().strip() or data('h1').text().strip()
            
            # 提取图片
            img = data('.thumb-content img').attr('src') or data('img').attr('src')
            
            # 提取状态和消息
            status = data('.pf-status-sec').text().strip()
            message = data('.thumbnail-message').text().strip()
            
            # 提取观看人数
            viewers = data('.icon-vw').text().strip()
            
            # 提取channel_id
            channel_id = self._extract_channel_id(html_text)
            
            # 如果页面中没有channel_id，尝试从列表数据中获取
            if not channel_id:
                # 尝试从data属性中获取
                channel_elem = data('[data-channel-id], [data-channel]')
                if channel_elem:
                    channel_id = channel_elem.attr('data-channel-id') or channel_elem.attr('data-channel')
            
            # 组合简介
            content_parts = []
            if message:
                content_parts.append(f"留言：{message}")
            if viewers:
                content_parts.append(f"觀看人數：{viewers}")
            if status:
                content_parts.append(f"狀態：{status}")
            if channel_id:
                content_parts.append(f"頻道ID：{channel_id}")
            
            vod = {
                'vod_id': first_id,
                'vod_name': name,
                'vod_pic': self._normalize_url(img) if img else '',
                'vod_content': '\n'.join(content_parts) if content_parts else '暂无简介',
                'vod_year': '',
                'vod_area': '日本',
                'vod_remarks': status,
                'vod_actor': name,
                'vod_director': ''
            }
            
            # 构建播放地址
            stream_url = None
            if channel_id:
                stream_url = self._build_stream_url(channel_id)
            
            if stream_url:
                vod['vod_play_from'] = 'DXLive'
                vod['vod_play_url'] = f"直播${stream_url}"
            else:
                # 如果没有channel_id，使用详情页URL（让playerContent处理）
                vod['vod_play_from'] = 'DXLive'
                vod['vod_play_url'] = f"直播${first_id}"
            
            return {'list': [vod]}
        except Exception as e:
            return {'list': []}
    
    def searchContent(self, key, quick, pg="1"):
        """搜索功能"""
        try:
            # 假设搜索URL
            search_url = f"{self.host}/zh-Hant/search?q={key}"
            if pg != "1":
                search_url += f"&page={pg}"
            
            response = self.fetch(search_url, headers=self.headers)
            data = self.getpq(response.text)
            
            results = self._get_online_list(data)
            
            # 过滤结果
            filtered = self._filter_search_results(results, key)
            
            return {'list': filtered, 'page': int(pg)}
        except Exception as e:
            return {'list': [], 'page': int(pg)}
    
    def _filter_search_results(self, results, key):
        """过滤搜索结果"""
        if not results or not key:
            return results
        key_lower = key.lower()
        filtered = []
        for result in results:
            title = result.get('vod_name', '').lower()
            if key_lower in title:
                filtered.append(result)
        return filtered
    
    def playerContent(self, flag, id, vipFlags):
        """解析播放地址"""
        try:
            # 如果id已经是.m3u8地址，直接播放
            if '.m3u8' in id or '.flv' in id or '.mp4' in id:
                return {'parse': 0, 'url': id, 'header': self.headers}
            
            # 如果是详情页URL，尝试重新提取channel_id
            response = self.fetch(id, headers=self.headers)
            html_text = response.text
            
            # 提取channel_id
            channel_id = self._extract_channel_id(html_text)
            
            if channel_id:
                stream_url = self._build_stream_url(channel_id)
                return {'parse': 0, 'url': stream_url, 'header': self.headers}
            
            # 如果都失败，返回原始URL让播放器尝试
            return {'parse': 1, 'url': id, 'header': self.headers}
        except Exception as e:
            return {'parse': 1, 'url': id, 'header': self.headers}
    
    def localProxy(self, param):
        pass
    
    def liveContent(self, url):
        pass