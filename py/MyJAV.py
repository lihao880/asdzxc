# -*- coding: utf-8 -*-
import sys
import re
import json
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "MyJAV完美版"

    def init(self, extend=""):
        self.host = "https://myjav.tv"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': self.host,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }

    def homeContent(self, filter):
        classes = [
            {"type_id": "/videos?x=updated", "type_name": "最新更新"},
            {"type_id": "/videos?x=uncensored", "type_name": "无码"},
            {"type_id": "/tags", "type_name": "标签"},
            {"type_id": "/actors", "type_name": "演员"},
            {"type_id": "/makers", "type_name": "制作商"}
        ]
        
        try:
            videos = self._fetch_list("/videos?x=updated")
            return {"class": classes, "list": videos[:20]}
        except:
            return {"class": classes, "list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            if '?' in tid:
                page_url = f"{self.host}{tid}&page={pg}"
            else:
                page_url = f"{self.host}{tid}?page={pg}"
            
            videos = self._fetch_list(page_url)
            
            return {
                "list": videos,
                "page": int(pg),
                "pagecount": 50,
                "limit": len(videos)
            }
        except:
            return {"list": [], "page": int(pg), "pagecount": 1}

    def _fetch_list(self, url):
        videos = []
        try:
            rsp = self.fetch(url, headers=self.headers)
            if not rsp or not hasattr(rsp, 'text'):
                return videos
            
            doc = pq(rsp.text)
            items = doc('div.video-grid.regular > div')
            
            for item in items.items():
                try:
                    link = item('a').attr('href')
                    if not link:
                        continue
                    
                    full_link = urljoin(self.host, link)
                    title = item('a').text().strip() or '未知'
                    
                    img = ''
                    cover = item('.video-cover')
                    if cover:
                        style = cover.attr('style')
                        if style:
                            img_match = re.search(r"url\(['\"]?([^'\"]+)['\"]?\)", style)
                            if img_match:
                                img = urljoin(self.host, img_match.group(1))
                    
                    code = item('.video-vol-tag').text().strip()
                    duration = item('.video-duration').text().strip()
                    
                    if code and code not in title:
                        display_title = f"{code} {title}"
                    else:
                        display_title = title
                    
                    videos.append({
                        "vod_id": full_link,
                        "vod_name": display_title[:100],
                        "vod_pic": img,
                        "vod_remarks": duration
                    })
                except:
                    continue
            
            return videos
        except:
            return videos

    def detailContent(self, ids):
        try:
            url = ids[0] if isinstance(ids, list) else ids
            if not url.startswith('http'):
                url = self.host + url
            
            rsp = self.fetch(url, headers=self.headers)
            if not rsp or not hasattr(rsp, 'text'):
                return {"list": []}
            
            doc = pq(rsp.text)
            
            # 标题
            title = doc('h1').text().strip() or doc('.video-title').text().strip()
            
            # 图片
            img = ''
            meta_img = doc('meta[property="og:image"]').attr('content')
            if meta_img:
                img = meta_img
            else:
                cover = doc('.video-cover')
                if cover:
                    style = cover.attr('style')
                    if style:
                        img_match = re.search(r"url\(['\"]?([^'\"]+)['\"]?\)", style)
                        if img_match:
                            img = urljoin(self.host, img_match.group(1))
            
            # 简介
            content = doc('.video-description, .description').text().strip()
            
            # 演员
            actors = []
            for actor in doc('.video-actors a, .actors a').items():
                name = actor.text().strip()
                if name:
                    actors.append(name)
            
            # === 播放地址解析 ===
            play_urls = self._extract_play_urls(doc, url)
            
            if play_urls:
                # 构建播放字符串
                play_from = "MyJAV"
                play_str = '#'.join([f"{name}${link}" for name, link in play_urls])
            else:
                # 如果没有找到，使用当前页面
                play_from = "详情页"
                play_str = f"播放${url}"
            
            vod = {
                "vod_id": url,
                "vod_name": title or '未知',
                "vod_pic": img,
                "vod_actor": ','.join(actors) if actors else '未知',
                "vod_content": content or '暂无简介',
                "vod_play_from": play_from,
                "vod_play_url": play_str
            }
            
            return {"list": [vod]}
        except Exception as e:
            return {"list": []}

    def _extract_play_urls(self, doc, page_url):
        """提取真实播放地址"""
        play_urls = []
        
        # 方法1: 直接查找video标签
        video_src = doc('video').attr('src') or doc('video source').attr('src')
        if video_src:
            full_url = urljoin(self.host, video_src)
            play_urls.append(('高清', full_url))
            return play_urls  # 如果找到直接返回
        
        # 方法2: 查找iframe播放器
        iframes = doc('iframe')
        for iframe in iframes.items():
            src = iframe.attr('src')
            if src:
                full_url = urljoin(self.host, src)
                play_urls.append(('播放器', full_url))
        
        # 方法3: 查找script中的m3u8链接
        scripts = doc('script')
        script_text = ''
        for script in scripts.items():
            script_text += script.text() or ''
        
        # 查找m3u8链接
        m3u8_patterns = [
            r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)',
            r'(/[^\s"\'<>]+\.m3u8[^\s"\'<>]*)',
            r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']',
            r'url[\s]*:[\s]*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'src[\s]*:[\s]*["\']([^"\']+\.m3u8[^"\']*)["\']'
        ]
        
        for pattern in m3u8_patterns:
            matches = re.findall(pattern, script_text, re.I)
            for match in matches:
                url = match if match.startswith('http') else urljoin(self.host, match)
                if url not in [u for _, u in play_urls]:
                    play_urls.append(('m3u8', url))
        
        # 查找mp4链接
        mp4_patterns = [
            r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)',
            r'(/[^\s"\'<>]+\.mp4[^\s"\'<>]*)',
            r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']',
            r'url[\s]*:[\s]*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'file[\s]*:[\s]*["\']([^"\']+\.mp4[^"\']*)["\']'
        ]
        
        for pattern in mp4_patterns:
            matches = re.findall(pattern, script_text, re.I)
            for match in matches:
                url = match if match.startswith('http') else urljoin(self.host, match)
                if url not in [u for _, u in play_urls]:
                    play_urls.append(('mp4', url))
        
        # 方法4: 查找播放按钮
        play_btns = doc('.play-btn, .play-button, .watch-btn, .watch-button, a:contains("Play"), a:contains("播放")')
        for btn in play_btns.items():
            href = btn.attr('href')
            if href and href != '#' and not href.startswith('javascript'):
                full_url = urljoin(self.host, href)
                if full_url not in [u for _, u in play_urls]:
                    play_urls.append(('播放', full_url))
        
        # 方法5: 查找video.js配置
        videojs_data = re.findall(r'videojs\([^,]+,\s*{[^}]*},\s*function\s*\(\)\s*{\s*this\.src\(\[\s*{\s*type:\s*"[^"]+",\s*src:\s*"([^"]+)"', script_text)
        for src in videojs_data:
            full_url = urljoin(self.host, src)
            if full_url not in [u for _, u in play_urls]:
                play_urls.append(('videojs', full_url))
        
        # 去重并返回
        unique_urls = []
        seen = set()
        for name, url in play_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append((name, url))
        
        return unique_urls[:3]  # 最多返回3个

    def playerContent(self, flag, id, vipFlags):
        """播放器内容 - 处理真实播放地址"""
        try:
            print(f"播放请求: flag={flag}, id={id}")
            
            # 如果已经是视频链接
            if self.isVideoFormat(id):
                return {
                    "parse": 0,
                    "url": id,
                    "header": {
                        "User-Agent": self.headers['User-Agent'],
                        "Referer": self.host,
                        "Accept": "*/*",
                        "Range": "bytes=0-"
                    }
                }
            
            # 如果是页面链接，尝试提取真实地址
            rsp = self.fetch(id, headers=self.headers)
            if rsp and hasattr(rsp, 'text'):
                doc = pq(rsp.text)
                play_urls = self._extract_play_urls(doc, id)
                
                if play_urls:
                    # 返回第一个找到的播放地址
                    name, url = play_urls[0]
                    return {
                        "parse": 0,
                        "url": url,
                        "header": {
                            "User-Agent": self.headers['User-Agent'],
                            "Referer": self.host,
                            "Accept": "*/*"
                        }
                    }
            
            # 如果都没找到，返回原链接让TVBox尝试
            return {
                "parse": 0,
                "url": id,
                "header": {
                    "User-Agent": self.headers['User-Agent'],
                    "Referer": self.host
                }
            }
        except Exception as e:
            return {"parse": 0, "url": id}

    def searchContent(self, key, quick, pg="1"):
        try:
            url = f"{self.host}/search?q={key}&page={pg}"
            videos = self._fetch_list(url)
            return {"list": videos, "page": int(pg), "pagecount": 1}
        except:
            return {"list": [], "page": int(pg), "pagecount": 1}

    def isVideoFormat(self, url):
        if not url:
            return False
        url_lower = url.lower()
        video_exts = ['.mp4', '.m3u8', '.flv', '.avi', '.mkv', '.wmv', '.mov', '.ts']
        return any(ext in url_lower for ext in video_exts)

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass