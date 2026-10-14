#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TVBox 爬虫 - bstube.site
目标站点: https://www.bstube.site
内容类型: 影视
"""

import re
import json
import base64
import requests
from urllib.parse import urljoin, quote

# 站点配置
SITE_URL = "https://www.bstube.site"

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": SITE_URL,
}

class Spider:
    """TVBox 爬虫主类"""
    
    def getName(self):
        return "bstube.site"

    def init(self, extend=""):
        """初始化"""
        try:
            requests.get(SITE_URL, headers=HEADERS, timeout=5)
        except:
            pass

    def getDependence(self):
        """返回依赖声明"""
        return []

    def homeContent(self, filter_param):
        """获取首页内容"""
        url = f"{SITE_URL}/index.php"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = 'utf-8'
            html = resp.text
        except Exception as e:
            print(f"homeContent error: {e}")
            return {"class": [], "list": []}
        
        class_list = []
        type_pattern = r'<a\s+href="[^"]*?/vod/type/id/(\d+)\.html"[^>]*?class="([^"]*)"[^>]*>([^<]+)</a>'
        types = re.findall(type_pattern, html)
        
        seen_ids = set()
        for type_id, cls, type_name in types:
            type_name = type_name.strip()
            if type_name in ("视频一区", "视频二区"):
                continue
            if type_id in seen_ids:
                continue
            seen_ids.add(type_id)
            class_list.append({
                "type_id": type_id,
                "type_name": type_name
            })
        
        video_list = self._parse_video_list(html)
        
        return {
            "class": class_list,
            "filters": {},
            "list": video_list
        }

    def homeVideoContent(self):
        """获取主页推荐视频"""
        return self.homeContent(False)

    def categoryContent(self, tid, pg, filter_param, extend):
        """获取分类列表页"""
        url = f"{SITE_URL}/index.php/vod/type/id/{tid}/page/{pg}.html"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = 'utf-8'
            html = resp.text
        except Exception as e:
            print(f"categoryContent error: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}
        
        video_list = self._parse_video_list(html)
        
        pagecount = 1
        page_pattern = r'<li\s+class="fenyeyema\s+weiyeyema">\s*<a[^>]*?href="[^"]*?/page/(\d+)\.html"[^>]*?>(\d+)</a>'
        page_match = re.search(page_pattern, html)
        if page_match:
            pagecount = int(page_match.group(1))
        
        return {
            "list": video_list,
            "page": int(pg),
            "pagecount": int(pagecount),
            "limit": 20,
            "total": int(pagecount) * 20
        }

    def detailContent(self, ids):
        """获取视频详情"""
        vid = ids[0] if isinstance(ids, list) else str(ids).strip()
        url = f"{SITE_URL}/index.php/vod/detail/id/{vid}.html"
        
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = 'utf-8'
            html = resp.text
        except Exception as e:
            print(f"detailContent error: {e}")
            return {"list": []}
        
        vod_name = ""
        vod_pic = ""
        vod_remarks = ""
        vod_content = ""
        type_name = ""
        vod_play_from = "默认线路"
        vod_play_url = ""
        
        # 提取标题
        title_match = re.search(r'<h1>([^<]+)</h1>', html)
        if title_match:
            vod_name = title_match.group(1).strip()
        
        # 提取播放地址
        m3u8_match = re.search(r'\"url\":\s*\"(https?://[^\"]+?\.m3u8[^\"]*)\"', html)
        if not m3u8_match:
            m3u8_match = re.search(r'(https?://[^\s\"\'<>]+?\.m3u8[^\s\"\'<>]*)', html)
        
        if m3u8_match:
            play_url = m3u8_match.group(1)
            vod_play_url = f"第1集${play_url}"
        
        # 提取封面
        poster_match = re.search(r'\"poster\":\s*\"(https?://[^\"]+?)\"', html)
        if poster_match:
            vod_pic = poster_match.group(1)
        
        # 提取标签
        tags_match = re.findall(r'<li><a\s+href="[^"]*?vod/search/wd/[^"]*?"[^>]*?>([^<]+)</a></li>', html)
        if tags_match:
            vod_remarks = ",".join(tags_match[:5])
            if tags_match:
                type_name = tags_match[0]
        
        # 提取简介
        desc_match = re.search(r'<div\s+class="video-info"[^>]*?>(.*?)</div>\s*</div>', html, re.DOTALL)
        if desc_match:
            vod_content = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
        
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "type_name": type_name,
                "vod_year": "",
                "vod_area": "",
                "vod_remarks": vod_remarks,
                "vod_actor": "",
                "vod_director": "",
                "vod_content": vod_content,
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url
            }]
        }

    def searchContent(self, key, quick, pg=1):
        """搜索"""
        url = f"{SITE_URL}/index.php/vod/search/wd/{quote(key)}/page/{pg}.html"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = 'utf-8'
            html = resp.text
        except Exception as e:
            print(f"searchContent error: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}
        
        video_list = self._parse_video_list(html)
        
        pagecount = 1
        page_pattern = r'<li\s+class="fenyeyema\s+weiyeyema">\s*<a[^>]*?href="[^"]*?/page/(\d+)\.html"[^>]*?>(\d+)</a>'
        page_match = re.search(page_pattern, html)
        if page_match:
            pagecount = int(page_match.group(1))
        
        return {
            "list": video_list,
            "page": int(pg),
            "pagecount": int(pagecount),
            "limit": 20,
            "total": int(pagecount) * 20
        }

    def playerContent(self, flag, vid, vip_flags=""):
        """获取播放地址"""
        if vid and ".m3u8" in str(vid):
            return {
                "parse": 0,
                "playUrl": "",
                "url": str(vid)
            }
        return {
            "parse": 0,
            "playUrl": "",
            "url": str(vid) if vid else ""
        }

    def _parse_video_list(self, html):
        """解析视频列表"""
        video_list = []
        
        pattern = r'<div\s+class="thumb">\s*<a\s+href="([^"]*?)"[^>]*?>\s*<span\s+class="title">([^<]+)</span>.*?data-original="([^"]+?)".*?<span\s+class="duration">(.*?)</span>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for link, title, pic, duration in matches:
            vid_match = re.search(r'/vod/detail/id/(\d+)\.html', link)
            if not vid_match:
                continue
            vod_id = vid_match.group(1)
            vod_name = title.strip()
            vod_pic = pic.strip()
            vod_remarks = duration.strip() if duration else ""
            
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic
            elif vod_pic.startswith("/"):
                vod_pic = SITE_URL + vod_pic
            
            video_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks
            })
        
        return video_list