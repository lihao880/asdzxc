#!/usr/bin/python
# -*- coding: utf-8 -*-
# 秘密视频 - TVBox爬虫
# 网站: https://59c8-e.coorr.xyz/

import re
import json
import urllib.parse
from bs4 import BeautifulSoup

class Spider:
    def getName(self):
        return "秘密视频"

    def getDependence(self):
        return ["bs4"]

    def init(self, extend=""):
        self.base_url = "https://59c8-e.coorr.xyz"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.base_url,
        }
        self.categories = [
            {"type_id": "人妻熟女", "type_name": "人妻熟女"},
            {"type_id": "国产区", "type_name": "国产区"},
            {"type_id": "AV区", "type_name": "AV区"},
            {"type_id": "欧美区", "type_name": "欧美区"},
            {"type_id": "动漫区", "type_name": "动漫区"},
            {"type_id": "网红主播", "type_name": "网红主播"},
            {"type_id": "国产传媒", "type_name": "国产传媒"},
            {"type_id": "探花系列", "type_name": "探花系列"},
            {"type_id": "日本无码", "type_name": "日本无码"},
            {"type_id": "美乳巨乳", "type_name": "美乳巨乳"},
            {"type_id": "制服诱惑", "type_name": "制服诱惑"},
            {"type_id": "家庭乱伦", "type_name": "家庭乱伦"},
            {"type_id": "AI换脸", "type_name": "AI换脸"},
            {"type_id": "OnlyFans", "type_name": "OnlyFans"},
            {"type_id": "三级电影", "type_name": "三级电影"},
            {"type_id": "少女萝莉", "type_name": "少女萝莉"},
        ]

    def _fetch(self, url, headers=None):
        try:
            import requests
            if headers is None:
                headers = self.headers
            r = requests.get(url, headers=headers, timeout=15)
            r.encoding = 'utf-8'
            return r.text
        except Exception as e:
            print(f"fetch error: {e}")
            return ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.base_url + url
        return self.base_url + "/" + url

    def _parse_list(self, html):
        if not html:
            return []
        
        videos = []
        soup = BeautifulSoup(html, 'html.parser')
        
        for item in soup.select('.thumb'):
            try:
                a = item.find('a', class_='th-in')
                if not a:
                    continue
                href = a.get('href', '')
                if not href:
                    continue
                
                title_elem = a.find('div', class_='th-title')
                name = title_elem.text.strip() if title_elem else ''
                
                img = item.find('img')
                pic = ''
                if img:
                    pic = img.get('src') or img.get('data-src') or ''
                    pic = self._fix_url(pic)
                
                remark = ''
                meta_items = item.select('.th-meta .th-meta-item')
                if meta_items:
                    parts = []
                    for m in meta_items:
                        text = m.text.strip()
                        if text:
                            parts.append(text)
                    remark = ' '.join(parts)
                
                vod_id = self._fix_url(href)
                if name and vod_id:
                    videos.append({
                        "vod_id": vod_id,
                        "vod_name": name,
                        "vod_pic": pic,
                        "vod_remarks": remark
                    })
            except Exception as e:
                print(f"parse item error: {e}")
                continue
        
        return videos

    def homeContent(self, filter):
        html = self._fetch(self.base_url)
        return {"class": self.categories, "list": self._parse_list(html)}

    def homeVideoContent(self):
        return self.homeContent(False)

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        url = f"{self.base_url}/?fenlei={urllib.parse.quote(tid)}"
        if page > 1:
            # 修复: 网站使用 p 参数而不是 page
            url = f"{self.base_url}/?fenlei={urllib.parse.quote(tid)}&p={page}"
        
        print(f"分类URL: {url}")
        html = self._fetch(url)
        video_list = self._parse_list(html)
        
        # 提取总页数
        pagecount = page
        if html:
            # 从 "1 / 90" 格式提取
            match = re.search(r'(\d+)\s*/\s*(\d+)', html)
            if match:
                pagecount = int(match.group(2))
            else:
                # 从分页控件提取最大页码
                page_links = re.findall(r'[?&]p=(\d+)', html)
                if page_links:
                    max_p = max(int(p) for p in page_links)
                    if max_p > pagecount:
                        pagecount = max_p
        
        return {"list": video_list, "page": page, "pagecount": pagecount, "limit": len(video_list)}

    def detailContent(self, ids):
        result = {"list": []}
        for vid in ids:
            try:
                url = self._fix_url(vid)
                html = self._fetch(url)
                if not html:
                    continue
                
                soup = BeautifulSoup(html, 'html.parser')
                
                title = soup.find('h1')
                name = title.text.strip() if title else ''
                
                pic = ''
                img = soup.select_one('.fplayer img, .video-box img, .thumb img')
                if img:
                    pic = img.get('src') or ''
                    pic = self._fix_url(pic)
                
                remark = ''
                cat = soup.select_one('.ftags a')
                if cat:
                    remark = cat.text.strip()
                
                did = ''
                did_match = re.search(r'play-(\d+)-', vid)
                if did_match:
                    did = did_match.group(1)
                else:
                    did_match = re.search(r'did=(\d+)', vid)
                    if did_match:
                        did = did_match.group(1)
                
                play_url = vid
                if did:
                    js_url = f"{self.base_url}/js/js.php?did={did}&src=1"
                    js_html = self._fetch(js_url)
                    if js_html:
                        m3u8_match = re.search(r'm3u8=([^&\"]+)', js_html)
                        if m3u8_match:
                            play_url = m3u8_match.group(1)
                        else:
                            m3u8_match2 = re.search(r'(https?://[^\s\"\']+\.m3u8[^\s\"\']*)', js_html)
                            if m3u8_match2:
                                play_url = m3u8_match2.group(1)
                
                result["list"].append({
                    "vod_id": did if did else vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                    "vod_play_from": "秘密视频",
                    "vod_play_url": f"秘密视频${play_url}"
                })
            except Exception as e:
                print(f"detailContent error: {e}")
                continue
        return result

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = f"{self.base_url}/?search={urllib.parse.quote(key)}"
        if page > 1:
            url = f"{self.base_url}/?search={urllib.parse.quote(key)}&page={page}"
        
        html = self._fetch(url)
        video_list = self._parse_list(html)
        
        filtered = []
        for v in video_list:
            if key.lower() in v.get("vod_name", "").lower():
                filtered.append(v)
        
        return {"list": filtered, "page": page, "pagecount": 1}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": ""}
        
        if '.m3u8' in id and id.startswith('http'):
            return {"parse": 0, "url": id, "header": json.dumps(self.headers)}
        
        did_match = re.search(r'play-(\d+)-', id)
        if did_match:
            did = did_match.group(1)
            js_url = f"{self.base_url}/js/js.php?did={did}&src=1"
            js_html = self._fetch(js_url)
            if js_html:
                m3u8_match = re.search(r'm3u8=([^&\"]+)', js_html)
                if m3u8_match:
                    m3u8_url = m3u8_match.group(1)
                    if m3u8_url.startswith('/'):
                        m3u8_url = self.base_url + m3u8_url
                    return {"parse": 0, "url": m3u8_url, "header": json.dumps(self.headers)}
        
        return {"parse": 1, "url": id, "header": json.dumps(self.headers)}

    def isVideoFormat(self, url):
        if not url:
            return False
        video_exts = ['.mp4', '.m3u8', '.flv', '.avi', '.mkv']
        return any(ext in url.lower() for ext in video_exts)

    def destroy(self):
        pass