# coding: utf-8
import json
import re
from urllib.parse import urljoin, quote, unquote, urlparse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xn--ybu43o.ypsparklabridge.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [{"type_id": "0", "type_name": "全部"}]
        self.filters = {"0": []}
        # 广告分片过滤关键词
        self.ad_keywords = ["ad", "ads", "advert", "banner", "promo", "union", "stat", "count", "track", "analytics"]

    def getName(self):
        return "一品脱"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self._fetch_list("/index.php/index/index/page/1.html", "1")

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        return self._fetch_list(f"/index.php/index/index/page/{page}.html", page)

    def _fetch_list(self, path, page):
        url = urljoin(self.host, path)
        try:
            res = self.fetch(url, headers=self.headers, timeout=10)
            if res.status_code != 200:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = res.text
            items = []
            pattern = r'<div class="item-thumb thumb-video">.*?<a href="([^"]+)".*?<img[^>]*src="([^"]+)".*?<h3 class="title">.*?<font.*?>(.*?)</font>.*?</h3>.*?<div class="details">.*?<span class="text">.*?<font.*?>(.*?)</font>.*?</span>.*?<span class="text">.*?<font.*?>(.*?)</font>.*?</span>'
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                link, pic, title, duration, time = match
                vod_id = self._extract_id(link)
                if vod_id:
                    title_clean = re.sub(r'<[^>]+>', '', title).strip()
                    remark_clean = re.sub(r'<[^>]+>', '', duration).strip()
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": title_clean,
                        "vod_pic": pic,
                        "vod_remarks": remark_clean
                    })
            pagecount = 1
            count_match = re.search(r'共(\d+)页', html)
            if count_match:
                pagecount = int(count_match.group(1))
            else:
                page_numbers = re.findall(r'/page/(\d+)\.html', html)
                if page_numbers:
                    pagecount = max(int(p) for p in page_numbers)
            if pagecount < 1:
                pagecount = 1
            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": len(items) if int(page) == 1 else 0
            }
        except Exception as e:
            self.log({"action": "fetch_list_fail", "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def _extract_id(self, link):
        match = re.search(r'/id/(\d+)/', link)
        return match.group(1) if match else None

    def detailContent(self, ids):
        if isinstance(ids, list):
            vod_id = ids[0] if ids else ""
        else:
            vod_id = str(ids) if ids else ""
        if not vod_id:
            return {"list": []}
        path = f"/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
        url = urljoin(self.host, path)
        try:
            res = self.fetch(url, headers=self.headers, timeout=10)
            if res.status_code != 200:
                return {"list": []}
            html = res.text
            start = html.find('var player_aaaa=')
            if start == -1:
                return {"list": []}
            json_start = start + len('var player_aaaa=')
            brace_count = 0
            json_end = json_start
            in_string = False
            escape = False
            for i, ch in enumerate(html[json_start:], json_start):
                if escape:
                    escape = False
                    continue
                if ch == '\\':
                    escape = True
                    continue
                if ch == '"' and not escape:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '{':
                    brace_count += 1
                elif ch == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break
            if json_end == json_start:
                return {"list": []}
            json_str = html[json_start:json_end]
            data = json.loads(json_str)
            vod_data = data.get("vod_data", {})
            play_url = data.get("url", "")
            vod_name = vod_data.get("vod_name", "视频")
            vod_name = re.sub(r'<[^>]+>', '', vod_name).strip()
            vod_pic = ""
            pic_match = re.search(r'<img[^>]*class="lazyloaded"[^>]*src="([^"]+)"', html)
            if pic_match:
                vod_pic = pic_match.group(1)
            # 如果播放地址是m3u8，走代理过滤广告
            if play_url and play_url.endswith(".m3u8"):
                play_url = self._m3u8_proxy_url(play_url)
            vod = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "线路1",
                "vod_play_url": f"播放${play_url}"
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detail_fail", "error": str(e)})
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        if not key or len(key.strip()) < 2:
            return {"list": [], "page": 1}
        url = urljoin(self.host, "/index.php/vod/search.html")
        try:
            res = self.post(url, data={"wd": key.strip()}, headers=self.headers, timeout=10)
            if res.status_code != 200:
                return {"list": [], "page": 1}
            html = res.text
            items = []
            pattern = r'<div class="item-thumb thumb-video">.*?<a href="([^"]+)".*?<img[^>]*src="([^"]+)".*?<h3 class="title">.*?<font.*?>(.*?)</font>.*?</h3>'
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                link, pic, title = match
                vod_id = self._extract_id(link)
                if vod_id:
                    title_clean = re.sub(r'<[^>]+>', '', title).strip()
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": title_clean,
                        "vod_pic": pic,
                        "vod_remarks": ""
                    })
            return {"list": items, "page": int(pg)}
        except Exception as e:
            self.log({"action": "search_fail", "error": str(e)})
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": self.headers}
        # 如果是 m3u8 直链，走代理过滤广告
        if id.endswith(".m3u8"):
            return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": {}}
        if id.endswith(".mp4"):
            return {"parse": 0, "url": id, "header": self.headers}
        # 尝试从详情页提取
        try:
            vod_id = self._extract_id(id)
            if not vod_id:
                return {"parse": 1, "url": id, "header": self.headers}
            path = f"/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
            url = urljoin(self.host, path)
            res = self.fetch(url, headers=self.headers, timeout=10)
            if res.status_code != 200:
                return {"parse": 1, "url": id, "header": self.headers}
            html = res.text
            start = html.find('var player_aaaa=')
            if start != -1:
                json_start = start + len('var player_aaaa=')
                brace_count = 0
                json_end = json_start
                in_string = False
                escape = False
                for i, ch in enumerate(html[json_start:], json_start):
                    if escape:
                        escape = False
                        continue
                    if ch == '\\':
                        escape = True
                        continue
                    if ch == '"' and not escape:
                        in_string = not in_string
                        continue
                    if in_string:
                        continue
                    if ch == '{':
                        brace_count += 1
                    elif ch == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                if json_end != json_start:
                    data = json.loads(html[json_start:json_end])
                    play_url = data.get("url", "")
                    if play_url:
                        if play_url.endswith(".m3u8"):
                            return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": {}}
                        return {"parse": 0, "url": play_url, "header": self.headers}
            return {"parse": 1, "url": id, "header": self.headers}
        except Exception as e:
            self.log({"action": "player_fail", "error": str(e)})
            return {"parse": 1, "url": id, "header": self.headers}

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "&url=" + quote(str(url or ""), safe="")
    def localProxy(self, param):
        """本地代理 - 过滤m3u8广告分片"""
        target = unquote(str((param or {}).get("url", "") or ""))
        if not target:
            return [400, "text/plain", b"missing url"]
        if not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]
        try:
            res = self.fetch(target, headers={"User-Agent": self.headers["User-Agent"]}, timeout=15, verify=False)
            if res.status_code != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            raw = getattr(res, "content", b"") or b""
            text = raw.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log({"action": "proxy_fail", "error": str(e)})
            return [500, "text/plain", b"proxy error"]
    def _clean_m3u8(self, text, source_url):
        """清洗m3u8：过滤广告分片，保留正片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"
        
        # 如果是多码率m3u8，递归处理
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"
        
        # 单码率m3u8：使用 content_root 方法过滤广告
        source_path = urlparse(source_url).path
        source_parts = [p for p in source_path.split("/") if p]
        # 取前两级目录作为正片根路径
        content_root = "/" + "/".join(source_parts[:2]) + "/" if len(source_parts) >= 2 else ""
        
        segments = []
        pending = []
        removed = 0
        
        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media = urljoin(source_url, line)
                # 广告过滤：检查路径是否在 content_root 下
                is_ad = False
                media_path = urlparse(media).path
                
                # 规则1：检查是否在正片根路径下
                if content_root and content_root not in media_path:
                    is_ad = True
                
                # 规则2：检查广告关键词
                if not is_ad:
                    media_lower = media.lower()
                    for kw in self.ad_keywords:
                        if kw in media_lower:
                            is_ad = True
                            break
                
                # 规则3：检查文件大小（广告分片通常较小）
                if not is_ad:
                    size_match = re.search(r'/(\d+)\.(ts|m4s)', media)
                    if size_match:
                        file_name = size_match.group(1)
                        if len(file_name) < 3:  # 极短文件名可能是广告
                            is_ad = True
                
                if is_ad:
                    removed += 1
                    pending = []
                    continue
                
                segments.extend(pending)
                segments.append(media)
                pending = []
                continue
            
            # 处理标签行
            segments.append(self._rewrite_m3u8_tag(line, source_url))
        
        # 后处理：清理重复的 DISCONTINUITY 和 KEY
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            # 补全非标签行的绝对路径
            if line and not line.startswith("#"):
                line = urljoin(source_url, line)
            # 清理无意义的标签
            if line == "#EXT-X-KEY:METHOD=NONE" or line == "#EXT-X-DISCONTINUITY":
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)
        
        # 移除末尾的垃圾标签
        while len(out) > 1 and out[-2] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop(-2)
        
        if removed:
            self.log({"action": "m3u8_filter", "filtered": removed})
        
        return "\n".join(out) + "\n"
    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI"""
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                return 'URI="' + urljoin(source_url, match.group(1)) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        return line

    def recommendContent(self, ids, pg="1"):
        """相关推荐 - 返回首页推荐（去重）"""
        try:
            if not ids:
                return {"list": []}
            vod_id = ids[0] if isinstance(ids, list) else str(ids)
            # 直接返回首页推荐
            home_result = self.homeVideoContent()
            items = home_result.get("list", [])
            # 过滤掉当前视频
            result = [item for item in items if item.get("vod_id") != vod_id]
            return {"list": result[:12]}
        except Exception as e:
            self.log({"action": "recommend_fail", "error": str(e)})
            return {"list": []}
    def destroy(self):
        pass