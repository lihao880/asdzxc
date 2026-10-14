# coding=utf-8
# TVBox 爬虫源 - avmars.com (播放) + yese.co (数据)
# 火星AV在线

import re
import json
import urllib.request
import urllib.parse
from urllib.parse import urljoin

class Spider:
    
    def __init__(self):
        self.extend = ""
        self.base_url = "https://avmars.com"
        self.data_url = "https://yese.co"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.timeout = 15

    def init(self, extend: str = "") -> None:
        self.extend = str(extend)
        if self.extend and self.extend.startswith("{"):
            try:
                config = json.loads(self.extend)
                if "base_url" in config:
                    self.base_url = config["base_url"]
                if "data_url" in config:
                    self.data_url = config["data_url"]
            except:
                pass

    def getDependence(self) -> str:
        return ""

    def homeContent(self, filter: bool = False) -> dict:
        result = {"code": 0, "msg": "", "class": [], "filters": {}, "list": []}
        try:
            result["class"] = [
                {"type_id": "亚洲情色", "type_name": "🔥 亚洲情色"},
                {"type_id": "中文字幕", "type_name": "📺 中文字幕"},
                {"type_id": "国产主播", "type_name": "🎙️ 国产主播"},
                {"type_id": "国产自拍", "type_name": "📱 国产自拍"},
                {"type_id": "无码专区", "type_name": "🔞 无码专区"},
                {"type_id": "欧美性爱", "type_name": "🌍 欧美性爱"},
                {"type_id": "熟女人妻", "type_name": "💃 熟女人妻"},
                {"type_id": "巨乳美乳", "type_name": "🍒 巨乳美乳"},
                {"type_id": "强奸乱伦", "type_name": "⛓️ 强奸乱伦"},
                {"type_id": "制服诱惑", "type_name": "👔 制服诱惑"},
                {"type_id": "少女萝莉", "type_name": "🌸 少女萝莉"},
                {"type_id": "丝袜长腿", "type_name": "🦵 丝袜长腿"}
            ]
            if filter:
                result["filters"] = {}
            result["list"] = self._get_home_recommend()
            return result
        except Exception as e:
            return {"code": -1, "msg": str(e), "class": [], "filters": {}, "list": []}

    def homeVideoContent(self) -> dict:
        return self.homeContent(False)

    def categoryContent(self, tid: str, pg: str = "1", filter: bool = False, extend: dict = None) -> dict:
        result = {"code": 0, "msg": "", "list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        try:
            url = f"{self.data_url}/vod/show/class/{urllib.parse.quote(tid)}/id/1/page/{pg}/"
            html = self._fetch(url)
            if not html:
                return {"code": -1, "msg": "获取列表失败", "list": []}
            result["list"] = self._parse_video_list(html, url)
            page_info = self._parse_pagination(html)
            if page_info:
                result["page"] = int(pg) if pg else 1
                result["pagecount"] = page_info.get("pagecount", 100)
                result["total"] = page_info.get("total", 2000)
            return result
        except Exception as e:
            return {"code": -1, "msg": str(e), "list": []}

    def detailContent(self, ids: list) -> dict:
        result = {"code": 0, "msg": "", "list": []}
        try:
            if not ids:
                return {"code": -1, "msg": "缺少影片ID", "list": []}
            vod_id = str(ids[0]).strip()
            url = f"{self.base_url}/vod/play/id/{vod_id}/sid/1/nid/1/"
            html = self._fetch(url)
            if not html:
                return {"code": -1, "msg": "获取详情失败", "list": []}
            detail = self._parse_detail(html, vod_id, url)
            if detail:
                result["list"] = [detail]
            return result
        except Exception as e:
            return {"code": -1, "msg": str(e), "list": []}

    def searchContent(self, key: str, quick: bool = False, pg: str = None) -> dict:
        result = {"code": 0, "msg": "", "list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        try:
            if not key:
                return {"code": -1, "msg": "请输入搜索关键词", "list": []}
            page = pg or "1"
            search_url = f"{self.data_url}/vod/search.html?wd={urllib.parse.quote(key)}&page={page}"
            html = self._fetch(search_url)
            if not html:
                return {"code": -1, "msg": "搜索失败", "list": []}
            result["list"] = self._parse_video_list(html, search_url)
            page_info = self._parse_pagination(html)
            if page_info:
                result["page"] = int(page)
                result["pagecount"] = page_info.get("pagecount", 10)
                result["total"] = page_info.get("total", 200)
            return result
        except Exception as e:
            return {"code": -1, "msg": str(e), "list": []}

    def playerContent(self, flag: str, id: str, vipFlags: dict = None) -> dict:
        result = {"code": 0, "msg": "", "parse": 0, "playUrl": "", "url": ""}
        try:
            if not id:
                return {"code": -1, "msg": "缺少播放地址", "parse": 0, "playUrl": "", "url": ""}
            
            # 如果已经是m3u8直链
            if id.startswith("http") and ".m3u8" in id:
                result["url"] = id
                return result
            
            # 提取video_id
            if "_" in str(id):
                video_id = str(id).split("_")[0]
            else:
                video_id = str(id)
            
            # 构建播放页URL
            play_url = f"{self.base_url}/vod/play/id/{video_id}/sid/1/nid/1/"
            
            # 获取播放页HTML (带超时)
            html = self._fetch(play_url)
            if not html:
                return {"code": -1, "msg": "获取播放页失败", "parse": 0, "playUrl": "", "url": ""}
            
            # 提取m3u8 - 多种模式
            m3u8_url = self._extract_m3u8(html)
            if m3u8_url:
                result["url"] = m3u8_url
                return result
            
            # 尝试从iframe提取
            iframe_url = self._extract_iframe(html)
            if iframe_url:
                if not iframe_url.startswith("http"):
                    iframe_url = urljoin(self.base_url, iframe_url)
                # 如果iframe是播放器，返回parse=1让TVBox解析
                result["url"] = iframe_url
                result["parse"] = 1
                return result
            
            # 降级
            result["url"] = play_url
            result["parse"] = 1
            return result
        except Exception as e:
            return {"code": -1, "msg": str(e), "parse": 0, "playUrl": "", "url": ""}

    def localProxy(self, param: dict = None):
        return None

    def isVideoFormat(self, url: str) -> bool:
        if not url:
            return False
        exts = ['.m3u8', '.mp4', '.ts', '.flv']
        return any(ext in url.lower() for ext in exts)

    def destroy(self) -> None:
        pass

    # ============ 内部方法 ============

    def _fetch(self, url: str) -> str:
        try:
            headers = self.headers.copy()
            if "yese.co" in url:
                headers["Referer"] = "https://yese.co"
                headers["Host"] = "yese.co"
            elif "avmars.com" in url:
                headers["Referer"] = "https://avmars.com"
                headers["Host"] = "avmars.com"
            else:
                headers["Referer"] = "https://avmars.com"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            return ""

    def _get_home_recommend(self) -> list:
        try:
            html = self._fetch(self.base_url)
            if not html:
                return []
            return self._parse_video_list(html, self.base_url)[:20]
        except Exception:
            return []

    def _parse_video_list(self, html: str, base_url: str) -> list:
        videos = []
        if not html:
            return videos

        pattern = r'<div[^>]*class="[^"]*(?:video-img-box|col-6)[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*(?:src|data-src)="([^"]+)"[^>]*(?:title|alt)="([^"]*)"[^>]*>.*?</a>.*?<h6[^>]*class="[^"]*title[^"]*"[^>]*><a[^>]*href="[^"]*"[^>]*>([^<]*)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        if not matches:
            pattern2 = r'<div[^>]*class="item"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*(?:src|data-src)="([^"]+)"[^>]*(?:title|alt)="([^"]*)"[^>]*>'
            matches = re.findall(pattern2, html, re.DOTALL)

        for match in matches:
            try:
                url = match[0].strip()
                img = match[1].strip() if match[1] else ""
                title = match[2].strip() if match[2] else ""
                if len(match) > 3 and match[3]:
                    title = match[3].strip()

                if not url:
                    continue
                if not url.startswith("http"):
                    url = urljoin(base_url, url)
                if img and not img.startswith("http") and not img.startswith("data:"):
                    img = urljoin(base_url, img)

                vod_id = "0"
                id_match = re.search(r'/vod/play/id/(\d+)/', url)
                if id_match:
                    vod_id = id_match.group(1)

                videos.append({
                    "vod_id": vod_id,
                    "vod_name": title if title else "未知标题",
                    "vod_pic": img if img else "",
                    "vod_remarks": ""
                })
            except Exception:
                continue
        return videos

    def _parse_pagination(self, html: str) -> dict:
        result = {"pagecount": 100, "total": 2000}
        if not html:
            return result

        page_links = re.findall(r'/vod/show/id/\d+/page/(\d+)/', html)
        if page_links:
            pages = [int(p) for p in page_links]
            max_page = max(pages) if pages else 1
            result["pagecount"] = max_page + 1

        total_match = re.search(r'共(\d+)条', html)
        if total_match:
            result["total"] = int(total_match.group(1))
        elif result["pagecount"] > 1:
            result["total"] = result["pagecount"] * 20
        return result

    def _parse_detail(self, html: str, video_id: str, base_url: str) -> dict:
        detail = {
            "vod_id": video_id,
            "vod_name": "",
            "vod_pic": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "线路1",
            "vod_play_url": ""
        }

        if not html:
            return detail

        title_match = re.search(r'<title>([^<]*)</title>', html)
        if title_match:
            title = title_match.group(1).strip()
            title = re.sub(r'^Playing\s+', '', title)
            title = re.sub(r'\s*-\s*avmars\.com.*$', '', title)
            detail["vod_name"] = title

        img_match = re.search(r'<h7[^>]*style="[^"]*display:none[^"]*"[^>]*>([^<]+)</h7>', html)
        if img_match:
            detail["vod_pic"] = img_match.group(1).strip()

        m3u8_url = self._extract_m3u8(html)
        if m3u8_url:
            detail["vod_play_url"] = f"{video_id}_1_1${m3u8_url}"
        else:
            detail["vod_play_url"] = f"{video_id}_1_1${base_url}"

        return detail

    def _extract_m3u8(self, html: str) -> str:
        if not html:
            return None

        # 模式1: var uul = '...' + '文件' (avmars.com 特有)
        match = re.search(r'var\s+uul\s*=\s*[\'"]([^\'"]+)[\'"]\s*\+\s*[\'"][^\'"]*[\'"]', html)
        if match:
            base = match.group(1)
            # 尝试从整个html中提取完整m3u8链接
            full = re.search(r'https?://[^\s\'"]+\.m3u8', html)
            if full:
                return full.group(0)
            if base.startswith("http") and ".m3u8" in base:
                return base

        # 模式2: 标准匹配
        patterns = [
            r'var\s+uul\s*=\s*[\'"]([^\'"]+\.m3u8[^\'"]*)[\'"]',
            r'<iframe[^>]*src="([^"]*\.m3u8[^"]*)"[^>]*>',
            r'(https?://[^\s\'"]+\.m3u8[^\s\'"]*)',
            r'[?&]url=([^&]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                url = match.group(1)
                if url:
                    try:
                        url = urllib.parse.unquote(url)
                    except:
                        pass
                    url = re.sub(r'[\'";]+$', '', url)
                    url = re.sub(r'^\s*[\'"]+', '', url)
                    if url.startswith("http") and ".m3u8" in url:
                        return url

        # 模式3: 在iframe中查找m3u8
        iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"[^>]*>', html)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            if ".m3u8" in iframe_url:
                if not iframe_url.startswith("http"):
                    iframe_url = urljoin(self.base_url, iframe_url)
                return iframe_url

        return None

    def _extract_iframe(self, html: str) -> str:
        if not html:
            return None
        iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"[^>]*>', html)
        if iframe_match:
            return iframe_match.group(1)
        return None