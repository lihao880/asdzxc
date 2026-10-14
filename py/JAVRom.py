# coding=utf-8
# TVBox 爬虫源 - javrom.com
# 版本: 1.4 - 修复筛选器格式 + 播放返回

import re
import json
import urllib.request
import urllib.parse
from typing import Dict, List, Optional
from urllib.parse import urljoin

class Spider:
    
    def __init__(self):
        self.extend = ""
        self.base_url = "https://javrom.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://javrom.com"
        }
        self.timeout = 20
        
        # 主分类
        self.categories = {
            "1": "视频一区",
            "2": "视频二区",
            "3": "视频三区",
            "4": "视频四区"
        }
        
        # 筛选器 - 参考03yy.py格式: [{"key": "xxx", "name": "xxx", "value": [{"n": "显示名", "v": "参数值"}]}]
        self.filters = {
            "1": [
                {
                    "key": "class",
                    "name": "分类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "亚洲情色", "v": "亚洲情色"},
                        {"n": "国产主播", "v": "国产主播"},
                        {"n": "国产自拍", "v": "国产自拍"},
                        {"n": "无码专区", "v": "无码专区"},
                        {"n": "欧美性爱", "v": "欧美性爱"},
                        {"n": "熟女人妻", "v": "熟女人妻"},
                        {"n": "强奸乱伦", "v": "强奸乱伦"},
                        {"n": "巨乳美乳", "v": "巨乳美乳"},
                        {"n": "中文字幕", "v": "中文字幕"},
                        {"n": "制服诱惑", "v": "制服诱惑"},
                        {"n": "女同性恋", "v": "女同性恋"},
                        {"n": "卡通动画", "v": "卡通动画"},
                        {"n": "视频伦理", "v": "视频伦理"},
                        {"n": "少女萝莉", "v": "少女萝莉"}
                    ]
                }
            ],
            "2": [
                {
                    "key": "class",
                    "name": "分类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "亚洲情色", "v": "亚洲情色"},
                        {"n": "国产主播", "v": "国产主播"},
                        {"n": "国产自拍", "v": "国产自拍"},
                        {"n": "无码专区", "v": "无码专区"},
                        {"n": "欧美性爱", "v": "欧美性爱"},
                        {"n": "熟女人妻", "v": "熟女人妻"}
                    ]
                }
            ],
            "3": [
                {
                    "key": "class",
                    "name": "分类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "亚洲情色", "v": "亚洲情色"},
                        {"n": "欧美性爱", "v": "欧美性爱"},
                        {"n": "中文字幕", "v": "中文字幕"},
                        {"n": "无码专区", "v": "无码专区"}
                    ]
                }
            ],
            "4": [
                {
                    "key": "class",
                    "name": "分类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "亚洲情色", "v": "亚洲情色"},
                        {"n": "欧美性爱", "v": "欧美性爱"},
                        {"n": "中文字幕", "v": "中文字幕"}
                    ]
                }
            ]
        }

    def init(self, extend: str = "") -> None:
        self.extend = str(extend)
        if self.extend and self.extend.startswith("{"):
            try:
                config = json.loads(self.extend)
                if "base_url" in config:
                    self.base_url = config["base_url"]
                if "headers" in config:
                    self.headers.update(config["headers"])
            except Exception as e:
                print(f"[ERROR] init: {e}")

    def getDependence(self) -> str:
        return ""

    def homeContent(self, filter: bool = False) -> Dict:
        result = {"code": 0, "msg": "", "class": [], "filters": {}, "list": []}
        try:
            for tid, name in self.categories.items():
                result["class"].append({"type_id": tid, "type_name": name})
            if filter:
                result["filters"] = self.filters
            result["list"] = self._get_home_recommend()
            return result
        except Exception as e:
            print(f"[ERROR] homeContent: {e}")
            return {"code": -1, "msg": str(e), "class": [], "filters": {}, "list": []}

    def homeVideoContent(self) -> Dict:
        return self.homeContent(False)

    def categoryContent(self, tid: str, pg: str = "1", filter: bool = False, extend: Dict = None) -> Dict:
        result = {"code": 0, "msg": "", "list": [], "page": 1, "pagecount": 1, "limit": 12, "total": 0}
        try:
            extend = extend or {}
            sub_class = extend.get("class", "")
            
            if sub_class:
                url = f"{self.base_url}/vod/show/class/{urllib.parse.quote(sub_class)}/id/{tid}/page/{pg}/"
            else:
                url = f"{self.base_url}/vod/show/id/{tid}/page/{pg}/"
            
            html = self._fetch(url)
            if not html:
                return {"code": -1, "msg": "获取列表失败", "list": []}
            
            pattern = r'<div class="col-6 col-sm-4 col-lg-3">.*?<a href="([^"]+)".*?title="([^"]+)".*?data-src="([^"]+)"'
            items = re.findall(pattern, html, re.DOTALL)
            
            for link, title, img in items:
                vod_id_match = re.search(r"/vod/play/id/(\d+)/", link)
                vod_id = vod_id_match.group(1) if vod_id_match else ""
                pic = img if img.startswith("http") else urljoin(self.base_url, img)
                result["list"].append({
                    "vod_id": vod_id,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
            
            page_match = re.search(r'<a class="page-link">(\d+)/(\d+)</a>', html)
            if page_match:
                result["page"] = int(page_match.group(1))
                result["pagecount"] = int(page_match.group(2))
            else:
                last_match = re.search(r'/page/(\d+)/[^>]*>尾页</a>', html)
                if last_match:
                    result["page"] = int(pg) if pg else 1
                    result["pagecount"] = int(last_match.group(1))
                else:
                    pages = re.findall(r'/page/(\d+)/', html)
                    if pages:
                        result["page"] = int(pg) if pg else 1
                        result["pagecount"] = int(pages[-1]) if pages else 100
            
            result["total"] = result["pagecount"] * result["limit"]
            return result
        except Exception as e:
            print(f"[ERROR] categoryContent: {e}")
            return {"code": -1, "msg": str(e), "list": []}

    def detailContent(self, ids: List[str]) -> Dict:
        result = {"code": 0, "msg": "", "list": []}
        try:
            if not ids:
                return {"code": -1, "msg": "缺少影片ID", "list": []}
            
            vod_id = ids[0]
            url = f"{self.base_url}/vod/play/id/{vod_id}/sid/1/nid/1/"
            html = self._fetch(url)
            if not html:
                return {"code": -1, "msg": "获取详情失败", "list": []}
            
            # 标题
            title = ""
            title_match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
            if title_match:
                title = title_match.group(1).strip()
                title = re.sub(r'\s*[-—]\s*(?:第\d+集\s*)?HD?$', '', title).strip()
            if not title:
                title_match = re.search(r'<h4[^>]*>([^<]+)</h4>', html)
                if title_match:
                    title = title_match.group(1).strip()
            if not title:
                title_match = re.search(r'<title>([^<]+)</title>', html)
                if title_match:
                    title = title_match.group(1).strip()
                    title = re.sub(r'\s*[-—]\s*(?:在线播放|高清在线播放|javrom\.com.*)$', '', title).strip()
            
            # 封面
            pic = ""
            img_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
            if img_match:
                pic = img_match.group(1).strip()
            if not pic:
                img_match = re.search(r'<img[^>]+data-src="([^"]+)"', html)
                if img_match:
                    pic = img_match.group(1).strip()
            
            # 简介
            desc = ""
            desc_match = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html)
            if desc_match:
                desc = desc_match.group(1).strip()
            
            # 播放地址
            play_url = ""
            og_match = re.search(r'<meta\s+property="og:video"\s+content="([^"]+)"', html)
            if og_match:
                play_url = og_match.group(1).strip()
            if not play_url:
                twitter_match = re.search(r'<meta\s+name="twitter:player:stream"\s+content="([^"]+)"', html)
                if twitter_match:
                    play_url = twitter_match.group(1).strip()
            if not play_url:
                js_match = re.search(r"var\s+uul\s*=\s*'([^']+)'", html)
                if js_match:
                    raw = js_match.group(1)
                    play_url = re.sub(r"\+'[^']*'$", "", raw).strip()
                    if not play_url.startswith("http"):
                        play_url = ""
            
            if play_url:
                play_url_str = f"1${play_url}"
            else:
                play_url_str = f"1${url}"
            
            vod = {
                "vod_id": vod_id,
                "vod_name": title if title else f"视频_{vod_id}",
                "vod_pic": pic,
                "vod_content": desc,
                "vod_play_from": "默认",
                "vod_play_url": play_url_str
            }
            result["list"] = [vod]
            return result
        except Exception as e:
            print(f"[ERROR] detailContent: {e}")
            return {"code": -1, "msg": str(e), "list": []}

    def searchContent(self, key: str, quick: bool = False, pg: Optional[str] = None) -> Dict:
        result = {"code": 0, "msg": "", "list": [], "page": 1, "pagecount": 1}
        try:
            if not key:
                return {"code": -1, "msg": "请输入搜索关键词", "list": []}
            page = pg or "1"
            url = f"{self.base_url}/vod/search.html?wd={urllib.parse.quote(key)}&page={page}"
            html = self._fetch(url)
            if not html:
                return {"code": -1, "msg": "搜索失败", "list": []}
            
            pattern = r'<div class="col-6 col-sm-4 col-lg-3">.*?<a href="([^"]+)".*?title="([^"]+)".*?data-src="([^"]+)"'
            items = re.findall(pattern, html, re.DOTALL)
            for link, title, img in items:
                vod_id_match = re.search(r"/vod/play/id/(\d+)/", link)
                vod_id = vod_id_match.group(1) if vod_id_match else ""
                pic = img if img.startswith("http") else urljoin(self.base_url, img)
                result["list"].append({
                    "vod_id": vod_id,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
            
            page_match = re.search(r'<a class="page-link">(\d+)/(\d+)</a>', html)
            if page_match:
                result["page"] = int(page_match.group(1))
                result["pagecount"] = int(page_match.group(2))
            return result
        except Exception as e:
            return {"code": -1, "msg": str(e), "list": []}

    def playerContent(self, flag: str, id: str, vipFlags: Optional[Dict] = None) -> Dict:
        """获取播放地址 - 只返回url"""
        result = {"code": 0, "msg": "", "parse": 0, "playUrl": "", "url": ""}
        try:
            if not id:
                return {"code": -1, "msg": "缺少播放地址", "parse": 0, "playUrl": "", "url": ""}
            
            # 如果已经是完整URL
            if id.startswith("http"):
                result["url"] = id
                return result
            
            # 构建播放页URL
            if id.startswith("/"):
                play_url = urljoin(self.base_url, id)
            else:
                play_url = urljoin(self.base_url, f"/vod/play/id/{id}/sid/1/nid/1/")
            
            html = self._fetch(play_url)
            if not html:
                return {"code": -1, "msg": "获取播放页失败", "parse": 0, "playUrl": "", "url": ""}
            
            # 1. og:video
            og_match = re.search(r'<meta\s+property="og:video"\s+content="([^"]+)"', html)
            if og_match:
                m3u8 = og_match.group(1).strip()
                if m3u8.startswith("http"):
                    result["url"] = m3u8
                    return result
            
            # 2. twitter:player:stream
            twitter_match = re.search(r'<meta\s+name="twitter:player:stream"\s+content="([^"]+)"', html)
            if twitter_match:
                m3u8 = twitter_match.group(1).strip()
                if m3u8.startswith("http"):
                    result["url"] = m3u8
                    return result
            
            # 3. JS变量uul
            js_match = re.search(r"var\s+uul\s*=\s*'([^']+)'", html)
            if js_match:
                raw = js_match.group(1)
                m3u8 = re.sub(r"\+'[^']*'$", "", raw).strip()
                http_match = re.search(r'(https?://[^\s"\']+\.m3u8)', m3u8)
                if http_match:
                    result["url"] = http_match.group(1)
                    return result
                elif m3u8.startswith("http"):
                    result["url"] = m3u8
                    return result
            
            # 4. video标签
            video_match = re.search(r'<video[^>]+src="([^"]+)"', html)
            if video_match:
                m3u8 = video_match.group(1)
                if m3u8.startswith("http"):
                    result["url"] = m3u8
                    return result
            
            # 5. iframe (解析模式)
            iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', html)
            if iframe_match:
                iframe_src = iframe_match.group(1)
                if not iframe_src.startswith("http"):
                    iframe_src = urljoin(self.base_url, iframe_src)
                result["url"] = iframe_src
                result["parse"] = 1
                return result
            
            # 6. 返回播放页URL
            result["url"] = play_url
            result["parse"] = 1
            return result
        except Exception as e:
            print(f"[ERROR] playerContent: {e}")
            return {"code": -1, "msg": str(e), "parse": 0, "playUrl": "", "url": ""}

    def localProxy(self, param: Optional[Dict] = None) -> Optional[List]:
        return None

    def isVideoFormat(self, url: str) -> bool:
        if not url:
            return False
        exts = ['.m3u8', '.mp4', '.ts', '.flv', '.mkv', '.avi', '.mov']
        return any(ext in url.lower() for ext in exts)

    def manualVideoCheck(self) -> bool:
        return False

    def destroy(self) -> None:
        pass

    def _fetch(self, url: str) -> str:
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"[ERROR] fetch: {e}")
            return ""

    def _get_home_recommend(self) -> List[Dict]:
        try:
            html = self._fetch(self.base_url)
            if not html:
                return []
            items = []
            pattern = r'<div class="item">.*?<a href="([^"]+)".*?title="([^"]+)".*?data-src="([^"]+)"'
            carousel = re.findall(pattern, html, re.DOTALL)
            for link, title, img in carousel:
                vod_id_match = re.search(r"/vod/play/id/(\d+)/", link)
                vod_id = vod_id_match.group(1) if vod_id_match else ""
                pic = img if img.startswith("http") else urljoin(self.base_url, img)
                items.append({
                    "vod_id": vod_id,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
            return items[:20]
        except Exception as e:
            print(f"[ERROR] home推荐: {e}")
            return []