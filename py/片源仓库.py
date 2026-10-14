# -*- coding: utf-8 -*-
"""
片源仓库 - TVBox爬虫源
站点: https://xn--dxtu96arxc.kc3000eiy.sbs
CMS: MacCMS v10
"""

import re
import json
import gzip
import zlib
import urllib.parse
import urllib.request
import urllib.error
import ssl
import html as html_lib

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass


class Spider:
    def __init__(self):
        self.host = "https://xn--dxtu96arxc.kc3000eiy.sbs"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
        }
        self._classes = None
        self.cookies = {}

    def _get_classes(self):
        if self._classes is not None:
            return self._classes
        self._classes = [
            {"type_id": "124", "type_name": "国产视频"},
            {"type_id": "125", "type_name": "中文字幕"},
            {"type_id": "126", "type_name": "国产传媒"},
            {"type_id": "127", "type_name": "日本有码"},
            {"type_id": "128", "type_name": "日本无码"},
            {"type_id": "130", "type_name": "強姦亂倫"},
            {"type_id": "131", "type_name": "制服誘惑"},
            {"type_id": "132", "type_name": "國產主播"},
            {"type_id": "133", "type_name": "激情動漫"},
        ]
        return self._classes

    def _fix_url(self, url):
        if not url:
            return ""
        url = str(url).strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        if not url.startswith("http"):
            return self.host + "/" + url
        return url

    def _clean_text(self, text):
        if not text:
            return ""
        return re.sub(r"\s+", " ", html_lib.unescape(str(text))).strip()

    def _fetch(self, url):
        if not url.startswith("http"):
            url = self.host + url if url.startswith("/") else self.host + "/" + url
        
        try:
            req = urllib.request.Request(url, headers=self.headers)
            if self.cookies:
                cookie_str = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
                req.add_header('Cookie', cookie_str)
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read()
                encoding = resp.info().get('Content-Encoding', '').lower()
                if encoding == 'gzip':
                    try:
                        content = gzip.decompress(content)
                    except:
                        pass
                elif encoding == 'deflate':
                    try:
                        content = zlib.decompress(content, -zlib.MAX_WBITS)
                    except:
                        pass
                cookie_header = resp.info().get('Set-Cookie', '')
                if cookie_header:
                    for cookie in cookie_header.split(','):
                        if '=' in cookie:
                            parts = cookie.strip().split(';')[0].split('=', 1)
                            if len(parts) == 2:
                                self.cookies[parts[0]] = parts[1]
                return content.decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"Fetch error: {e}")
            return ""

    def _parse_videos(self, html):
        videos = []
        if not html:
            return videos
        
        pattern = r'<article\s+class="video-card">(.*?)</article>'
        articles = re.findall(pattern, html, re.DOTALL)

        for art in articles:
            try:
                link_match = re.search(r'<a\s+class="video-link"\s+href="([^"]+)"', art)
                if not link_match:
                    continue
                link = link_match.group(1)

                title_match = re.search(r'title="([^"]*)"', art)
                title = self._clean_text(title_match.group(1)) if title_match else ""

                pic_match = re.search(r'<img\s+src="([^"]+)"', art)
                pic = pic_match.group(1) if pic_match else ""

                dur_match = re.search(r'<em\s+class="duration">([^<]*)</em>', art)
                dur = dur_match.group(1) if dur_match else ""

                name_match = re.search(r'<h3>([^<]*)</h3>', art)
                name = self._clean_text(name_match.group(1)) if name_match else ""
                if not name:
                    name = title

                vod_id = re.search(r'/play/id/(\d+)', link)
                if not vod_id:
                    vod_id = re.search(r'/play/(\d+)/', link)
                if not vod_id:
                    vod_id = re.search(r'id=(\d+)', link)
                
                if vod_id:
                    videos.append({
                        "vod_id": vod_id.group(1),
                        "vod_name": name,
                        "vod_pic": self._fix_url(pic),
                        "vod_remarks": dur
                    })
            except:
                continue
        
        return videos

    def homeContent(self, filter):
        result = {"class": [], "list": []}
        for cls in self._get_classes():
            result["class"].append({
                "type_id": cls["type_id"],
                "type_name": cls["type_name"]
            })
        html = self._fetch("/index.php/label/home.html")
        if html:
            videos = self._parse_videos(html)
            result["list"] = videos[:20]
        return result

    def homeVideoContent(self):
        html = self._fetch("/index.php/label/home.html")
        if html:
            videos = self._parse_videos(html)
            return {"list": videos[:20]}
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
        except:
            page = 1
        
        result = {
            "list": [],
            "page": page,
            "pagecount": 1,
            "limit": 20,
            "total": 0
        }
        
        if page == 1:
            url = f"/index.php/vod/type/id/{tid}.html"
        else:
            url = f"/index.php/vod/type/id/{tid}/page/{page}.html"
        
        html = self._fetch(url)
        if html:
            videos = self._parse_videos(html)
            result["list"] = videos
            
            pagecount = 1
            m = re.search(r'共(\d+)页', html)
            if m:
                pagecount = int(m.group(1))
            else:
                page_links = re.findall(r'href="[^"]*/page/(\d+)\.html"', html)
                if page_links:
                    nums = [int(p) for p in page_links if p.isdigit()]
                    if nums:
                        pagecount = max(nums)
                else:
                    nums = re.findall(r'<a[^>]*>(\d+)</a>', html)
                    if nums:
                        nums = [int(n) for n in nums if n.isdigit()]
                        if nums:
                            pagecount = max(nums)
            
            result["pagecount"] = pagecount
            result["total"] = len(videos) * pagecount
        
        return result

    def searchContent(self, key, quick=False, pg=1):
        """
        搜索功能 - 兼容 TVBox/FongMi 搜索调用
        key: 搜索关键词
        quick: 快速搜索 (可能为字符串或布尔值)
        pg: 页码
        """
        # 处理 key 可能为 None 或空字符串
        if not key:
            return {"list": []}
        
        # 确保 key 是字符串
        key = str(key).strip()
        if not key:
            return {"list": []}
        
        try:
            page = int(pg) if pg else 1
        except:
            page = 1
        
        encoded_key = urllib.parse.quote(key)
        
        if page == 1:
            url = f"/index.php/vod/search.html?wd={encoded_key}"
        else:
            url = f"/index.php/vod/search/page/{page}.html?wd={encoded_key}"
        
        html = self._fetch(url)
        
        result = {"list": []}
        if html:
            videos = self._parse_videos(html)
            result["list"] = videos
            
            # 提取总页数
            pagecount = 1
            m = re.search(r'共(\d+)页', html)
            if m:
                pagecount = int(m.group(1))
            result["pagecount"] = pagecount
        else:
            # 如果搜索URL返回空，尝试备用搜索格式
            # 有些 MacCMS 站点使用不同的搜索URL格式
            if page == 1:
                alt_url = f"/index.php/vod/search.html?searchword={encoded_key}"
            else:
                alt_url = f"/index.php/vod/search/page/{page}.html?searchword={encoded_key}"
            
            html2 = self._fetch(alt_url)
            if html2:
                videos = self._parse_videos(html2)
                result["list"] = videos
                m = re.search(r'共(\d+)页', html2)
                if m:
                    result["pagecount"] = int(m.group(1))
                else:
                    result["pagecount"] = 1
        
        return result

    def detailContent(self, ids):
        result = {"list": []}
        if not ids or len(ids) == 0:
            return result
        
        vid = ids[0]
        url = f"/index.php/vod/detail/id/{vid}.html"
        html = self._fetch(url)
        if not html:
            return result
        
        video_data = {
            "vod_id": vid,
            "vod_name": "",
            "vod_pic": "",
            "vod_content": "",
            "vod_play_from": "",
            "vod_play_url": ""
        }
        
        title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if title_match:
            video_data["vod_name"] = self._clean_text(title_match.group(1))
        
        pic_match = re.search(r'<div[^>]*class="[^"]*detail-cover[^"]*"[^>]*>.*?<img[^>]*src="([^"]+)"', html, re.DOTALL)
        if pic_match:
            video_data["vod_pic"] = self._fix_url(pic_match.group(1))
        
        desc_match = re.search(r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>([^<]+)</p>', html)
        if desc_match:
            video_data["vod_content"] = self._clean_text(desc_match.group(1))
        
        play_urls = []
        play_names = []
        player_pattern = r'var\s+player_([a-z]+)\s*=\s*({[^}]+})'
        for m in re.findall(player_pattern, html, re.DOTALL):
            try:
                name = m.group(1)
                data = json.loads(m.group(2))
                if data.get("url"):
                    play_names.append(name)
                    play_urls.append(data["url"])
            except:
                pass
        
        if play_urls:
            video_data["vod_play_from"] = "$$$".join(play_names)
            video_data["vod_play_url"] = "$$$".join(play_urls)
        else:
            video_data["vod_play_from"] = "默认线路"
            video_data["vod_play_url"] = f"/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        
        result["list"].append(video_data)
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 1, "url": ""}
        
        if not id:
            return result
        
        if ".m3u8" in id or ".mp4" in id:
            result["parse"] = 0
            result["url"] = id
            result["header"] = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": self.host + "/"
            }
            return result
        
        if not id.startswith("http"):
            full_url = self.host + id if id.startswith("/") else self.host + "/" + id
        else:
            full_url = id
        
        html = self._fetch(full_url)
        if html:
            player_pattern = r'var\s+player_[a-z]+\s*=\s*({[^}]+})'
            for m in re.findall(player_pattern, html, re.DOTALL):
                try:
                    data = json.loads(m)
                    if data.get("url"):
                        url = data["url"]
                        if ".m3u8" in url or ".mp4" in url:
                            result["parse"] = 0
                            result["url"] = url
                            result["header"] = {
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                "Referer": full_url
                            }
                            return result
                except:
                    pass
            
            iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"', html)
            if iframe_match:
                iframe_url = iframe_match.group(1)
                if ".m3u8" in iframe_url:
                    result["parse"] = 0
                    result["url"] = self._fix_url(iframe_url)
                    return result
                return self.playerContent(flag, self._fix_url(iframe_url), vipFlags)
        
        result["parse"] = 1
        result["url"] = id
        return result

    def init(self, extend=""):
        pass

    def getDependence(self):
        return []

    def destroy(self):
        pass

    def localProxy(self, params):
        return None