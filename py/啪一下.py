# coding=utf-8
# TVBox 爬虫源 - 啪一下
# 站点: https://pyapexspeedgreat.xyz

import re
import json
import gzip
import zlib
import urllib.request
import urllib.parse
from urllib.parse import urljoin

try:
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass


class Spider:

    def __init__(self):
        self.extend = ""
        self.base_url = "https://pyapexspeedgreat.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.timeout = 15
        self.cookies = {}
        self._classes = None

    def init(self, extend: str = "") -> None:
        self.extend = str(extend)
        if self.extend and self.extend.startswith("{"):
            try:
                config = json.loads(self.extend)
                if "base_url" in config:
                    self.base_url = config["base_url"]
            except:
                pass

    def getDependence(self) -> list:
        return []

    def getName(self) -> str:
        return "啪一下"

    def homeContent(self, filter: bool = False) -> dict:
        result = {"class": [], "filters": {}}
        try:
            result["class"] = self._get_classes()
            if filter:
                result["filters"] = {}
            return result
        except Exception:
            return {"class": [], "filters": {}}

    def homeVideoContent(self) -> dict:
        try:
            html = self._fetch(self.base_url + "/")
            if not html:
                return {"list": []}
            items = self._parse_video_list(html, self.base_url)
            return {"list": items[:40]}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid: str, pg: str = "1", filter: bool = False, extend: dict = None) -> dict:
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        try:
            page = int(pg) if pg else 1
            if page == 1:
                url = f"{self.base_url}/index.php/vod/type/id/{tid}.html"
            else:
                url = f"{self.base_url}/index.php/vod/type/id/{tid}/page/{page}.html"
            html = self._fetch(url)
            if not html:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
            result["list"] = self._parse_video_list(html, url)
            result["page"] = page
            result["pagecount"] = self._parse_pagecount(html, page)
            result["total"] = len(result["list"]) * result["pagecount"]
            return result
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids: list) -> dict:
        result = {"list": []}
        try:
            if not ids:
                return {"list": []}
            vid = str(ids[0]).strip()
            url = f"{self.base_url}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            html = self._fetch(url)
            if not html:
                return {"list": []}
            detail = self._parse_detail(html, vid)
            if detail:
                result["list"] = [detail]
            return result
        except Exception:
            return {"list": []}

    def searchContent(self, key: str, quick: bool = False, pg: str = None) -> dict:
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        try:
            if not key:
                return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
            page = int(pg) if pg else 1
            encoded_key = urllib.parse.quote(key)
            if page == 1:
                url = f"{self.base_url}/index.php/vod/search.html?wd={encoded_key}"
            else:
                url = f"{self.base_url}/index.php/vod/search/page/{page}.html?wd={encoded_key}"
            html = self._fetch(url)
            if not html:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
            result["list"] = self._parse_video_list(html, url)
            result["page"] = page
            result["pagecount"] = self._parse_pagecount(html, page)
            result["total"] = len(result["list"]) * result["pagecount"]
            return result
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def playerContent(self, flag: str, id: str, vipFlags: dict = None) -> dict:
        result = {"parse": 0, "url": "", "header": {}}
        try:
            if not id:
                return {"parse": 0, "url": "", "header": {}}

            if id.startswith("http") and (".m3u8" in id or ".mp4" in id):
                result["url"] = id
                result["header"] = self.headers
                return result

            if not id.startswith("http"):
                full_url = self.base_url + id if id.startswith("/") else self.base_url + "/" + id
            else:
                full_url = id

            html = self._fetch(full_url)
            if not html:
                return {"parse": 0, "url": "", "header": {}}

            m3u8_url = self._extract_m3u8(html)
            if m3u8_url:
                result["url"] = m3u8_url
                result["header"] = self.headers
                return result

            result["url"] = full_url
            result["parse"] = 1
            result["header"] = self.headers
            return result
        except Exception:
            return {"parse": 0, "url": "", "header": {}}

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
            if "pyapexspeedgreat.xyz" in url:
                headers["Referer"] = "https://pyapexspeedgreat.xyz"
                headers["Host"] = "pyapexspeedgreat.xyz"
            req = urllib.request.Request(url, headers=headers)
            if self.cookies:
                cookie_str = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
                req.add_header('Cookie', cookie_str)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
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
        except Exception:
            return ""

    def _get_classes(self) -> list:
        if self._classes is not None:
            return self._classes
        self._classes = [
            {"type_id": "43", "type_name": "国产视频"},
            {"type_id": "35", "type_name": "日本视频"},
            {"type_id": "39", "type_name": "欧美视频"},
            {"type_id": "31", "type_name": "SM调教"},
            {"type_id": "53", "type_name": "剧情"},
            {"type_id": "29", "type_name": "人妖"},
            {"type_id": "49", "type_name": "女主播"},
            {"type_id": "47", "type_name": "少女"},
            {"type_id": "55", "type_name": "三级片"},
            {"type_id": "23", "type_name": "同性"}
        ]
        return self._classes

    def _parse_video_list(self, html: str, base_url: str) -> list:
        videos = []
        if not html:
            return videos

        pattern = r'<div\s+itemscope[^>]*>.*?<div\s+class="info">.*?<h2>.*?<a\s+href="([^"]+)"[^>]*>.*?<font[^>]*>.*?<font[^>]*>(.*?)</font>.*?</a>.*?</h2>.*?</div>.*?<div\s+class="image[^"]*">.*?<a[^>]*href="[^"]*">.*?<img[^>]*src="([^"]+)"'
        matches = re.findall(pattern, html, re.DOTALL)

        for match in matches:
            try:
                link = match[0].strip()
                title = match[1].strip() if match[1] else ""
                pic = match[2].strip() if match[2] else ""

                if not link:
                    continue
                if not link.startswith("http"):
                    link = urljoin(base_url, link)
                if pic and not pic.startswith("http") and not pic.startswith("data:"):
                    pic = urljoin(base_url, pic)

                vod_id = "0"
                id_match = re.search(r'/play/id/(\d+)', link)
                if id_match:
                    vod_id = id_match.group(1)

                videos.append({
                    "vod_id": vod_id,
                    "vod_name": self._clean_text(title),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
            except Exception:
                continue
        return videos

    def _parse_pagecount(self, html: str, current_page: int) -> int:
        if not html:
            return 1
        m = re.search(r'共(\d+)页', html)
        if m:
            return int(m.group(1))
        page_links = re.findall(r'/page/(\d+)\.html"', html)
        if page_links:
            nums = [int(p) for p in page_links if p.isdigit()]
            if nums:
                return max(nums) + 1
        return current_page + 1

    def _parse_detail(self, html: str, vid: str) -> dict:
        detail = {
            "vod_id": vid,
            "vod_name": "",
            "vod_pic": "",
            "vod_content": "",
            "vod_play_from": "线路1",
            "vod_play_url": ""
        }

        if not html:
            return detail

        # 从 h1.block_header 提取标题
        name_match = re.search(r'<h1[^>]*class="[^"]*block_header[^"]*"[^>]*>.*?正在播放[^<]*([^<]+)</font>', html, re.DOTALL)
        if name_match:
            title = name_match.group(1).strip()
            title = re.sub(r'^\-', '', title)
            detail["vod_name"] = self._clean_text(title)

        if not detail["vod_name"]:
            name_match2 = re.search(r'正在播放[^<]*([^<]+)', html)
            if name_match2:
                detail["vod_name"] = self._clean_text(name_match2.group(1).strip())

        pic_match = re.search(r'<img[^>]*src="([^"]+)"[^>]*width="180"[^>]*height="135"', html)
        if pic_match:
            detail["vod_pic"] = self._fix_url(pic_match.group(1))

        m3u8_url = self._extract_m3u8(html)
        if m3u8_url:
            detail["vod_play_url"] = m3u8_url
        else:
            detail["vod_play_url"] = f"{self.base_url}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"

        return detail

    def _extract_m3u8(self, html: str) -> str:
        if not html:
            return None

        iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"', html)
        if iframe_match:
            iframe_src = iframe_match.group(1)
            url_param_match = re.search(r'[?&]url=([^&]+)', iframe_src)
            if url_param_match:
                real_url = urllib.parse.unquote(url_param_match.group(1))
                if ".m3u8" in real_url or ".mp4" in real_url:
                    return real_url
            if ".m3u8" in iframe_src:
                return self._fix_url(iframe_src)

        player_pattern = r'var\s+player_[a-z]+\s*=\s*({[^}]+})'
        for m in re.findall(player_pattern, html, re.DOTALL):
            try:
                data = json.loads(m)
                if data.get("url"):
                    url = data["url"]
                    if ".m3u8" in url or ".mp4" in url:
                        return url
            except:
                pass

        return None

    def _fix_url(self, url: str) -> str:
        if not url:
            return ""
        url = str(url).strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.base_url + url
        if not url.startswith("http"):
            return self.base_url + "/" + url
        return url

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", str(text)).strip()