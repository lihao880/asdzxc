# coding: utf-8
import re
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.host = "https://www.dsys3.help"
        self.base_path = "/cn/home/web/index.php"
        self.classes = [
            {"type_id": "20", "type_name": "熟母少妇"},
            {"type_id": "21", "type_name": "网红直播"},
            {"type_id": "22", "type_name": "自拍偷拍"},
            {"type_id": "23", "type_name": "强奸乱伦"},
            {"type_id": "24", "type_name": "高清国产"},
            {"type_id": "25", "type_name": "韩国专区"},
            {"type_id": "26", "type_name": "日本有码"},
            {"type_id": "27", "type_name": "日本无码"},
            {"type_id": "28", "type_name": "欧美情色"},
            {"type_id": "29", "type_name": "动漫卡通"},
            {"type_id": "30", "type_name": "三级伦理"},
        ]
        self.filters = {str(i): [] for i in range(20, 31)}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    def getName(self):
        return "低俗影视"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 从最近热播和最新上传获取"""
        try:
            resp = self.fetch(self.host + "/cn/home/web/", headers=self.headers, timeout=15)
            if not resp:
                return {"list": []}
            html = resp.text if hasattr(resp, 'text') else ""
            if not html:
                return {"list": []}
            items = []
            # 解析所有视频卡片 (包括最近热播和最新上传)
            # 使用更宽松的模式匹配所有 video__inner
            pattern = r'<a[^>]*href="([^"]+)"[^>]*>.*?<div[^>]*class="video__block"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?</div>.*?<div[^>]*class="video__text"[^>]*>.*?<h3>([^<]+)</h3>'
            matches = re.findall(pattern, html, re.DOTALL)
            seen = set()
            for link, pic, title in matches:
                if not title:
                    continue
                vod_id = ""
                id_match = re.search(r'/play/id/(\d+)/', link)
                if id_match:
                    vod_id = id_match.group(1)
                if vod_id and vod_id not in seen:
                    seen.add(vod_id)
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": "",
                    })
            self.log({"action": "homeVideoContent", "items_count": len(items)})
            return {"list": items}
        except Exception as e:
            self.log({"action": "homeVideoContent_error", "error": str(e)})
            return {"list": []}
    def categoryContent(self, tid, pg, filter, extend):
        """分类列表"""
        try:
            page = pg or "1"
            url = f"{self.host}/cn/home/web/index.php/vod/type/id/{tid}-{page}.html"
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = resp.text if hasattr(resp, 'text') else ""
            if not html:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            items = []
            pattern = r'<a[^>]*href="([^"]+)"[^>]*>.*?<div[^>]*class="video__block"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?</div>.*?<div[^>]*class="video__text"[^>]*>.*?<h3>([^<]+)</h3>'
            matches = re.findall(pattern, html, re.DOTALL)
            for link, pic, title in matches:
                if not title:
                    continue
                vod_id = ""
                id_match = re.search(r'/play/id/(\d+)/', link)
                if id_match:
                    vod_id = id_match.group(1)
                if vod_id:
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": "",
                    })
            pagecount = 10
            pc_match = re.search(r'共(\d+)页', html)
            if pc_match:
                pagecount = int(pc_match.group(1))
            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": len(items) * pagecount if items else 0,
            }
        except Exception as e:
            self.log({"action": "categoryContent_error", "error": str(e)})
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        """详情页 - 提取播放地址"""
        try:
            vod_id = str(ids[0])
            url = f"{self.host}/cn/home/web/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp:
                return {"list": []}
            html = resp.text if hasattr(resp, 'text') else ""
            if not html:
                return {"list": []}
            # 提取标题
            title = "未知标题"
            title_match = re.search(r'<h3>([^<]+)</h3>', html)
            if title_match:
                title = title_match.group(1).strip()
            # 提取播放地址 - 处理转义字符
            play_url = ""
            # 先移除转义反斜杠
            clean_html = html.replace('\\/', '/').replace('\\\\', '')
            # 匹配 m3u8 链接
            m3u8_match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', clean_html)
            if m3u8_match:
                play_url = m3u8_match.group(0)
            if not play_url:
                # 匹配 mp4 链接
                mp4_match = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', clean_html)
                if mp4_match:
                    play_url = mp4_match.group(0)
            if play_url:
                # 清理可能的尾部字符
                play_url = play_url.strip('"\'')
            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": "",
                "vod_remarks": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}" if play_url else "",
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent_error", "error": str(e)})
            return {"list": []}
    def searchContent(self, key, quick, pg="1"):
        """搜索 - POST表单提交"""
        try:
            url = f"{self.host}/cn/home/web/index.php/vod/search.html"
            data = {"wd": key}
            resp = self.post(url, data=data, headers=self.headers, timeout=15)
            if not resp:
                return {"list": [], "page": 1}
            html = resp.text if hasattr(resp, 'text') else ""
            if not html:
                return {"list": [], "page": 1}
            items = []
            pattern = r'<a[^>]*href="([^"]+)"[^>]*>.*?<div[^>]*class="video__block"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?</div>.*?<div[^>]*class="video__text"[^>]*>.*?<h3>([^<]+)</h3>'
            matches = re.findall(pattern, html, re.DOTALL)
            for link, pic, title in matches:
                if not title:
                    continue
                vod_id = ""
                id_match = re.search(r'/play/id/(\d+)/', link)
                if id_match:
                    vod_id = id_match.group(1)
                if vod_id:
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": "",
                    })
            return {"list": items, "page": int(pg)}
        except Exception as e:
            self.log({"action": "searchContent_error", "error": str(e)})
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        """播放地址解析"""
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        play_url = str(id).strip()
        if play_url.startswith("http") and ".m3u8" in play_url:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(play_url),
                "header": self.headers,
            }
        if play_url.startswith("http") and ".mp4" in play_url:
            return {"parse": 0, "url": play_url, "header": self.headers}
        return {"parse": 1, "url": play_url, "header": self.headers}

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        """m3u8本地代理"""
        target = ""
        if isinstance(param, dict):
            target = param.get("url", "") or param.get("source", "")
        elif isinstance(param, str):
            target = param
        if target and target.startswith("url="):
            target = target[4:]
        if target and "url=" in target:
            parsed = urllib.parse.urlparse(target)
            qs = urllib.parse.parse_qs(parsed.query)
            if "url" in qs:
                target = qs["url"][0]
        target = urllib.parse.unquote(str(target or ""))
        if not target or not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]
        try:
            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp:
                return [502, "text/plain", b"fetch failed"]
            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]
            if b"#EXTM3U" in content[:256]:
                text = content.decode("utf-8", errors="ignore")
                cleaned = self._clean_m3u8(text, target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            content_type = "application/octet-stream"
            if target.endswith(".ts"):
                content_type = "video/mp2t"
            elif target.endswith(".m3u8"):
                content_type = "application/vnd.apple.mpegurl"
            elif target.endswith(".jpg") or target.endswith(".png"):
                content_type = "image/jpeg"
            elif target.endswith(".mp4"):
                content_type = "video/mp4"
            return [200, content_type, content]
        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]

    def _clean_m3u8(self, text, source_url):
        """清洗m3u8"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"
        is_multi = any(line.startswith("#EXT-X-STREAM-INF") for line in lines)
        if is_multi:
            return self._clean_m3u8_multi(lines, source_url)
        return self._clean_m3u8_single(lines, source_url)

    def _clean_m3u8_single(self, lines, source_url):
        import posixpath
        parsed = urllib.parse.urlparse(source_url)
        dir_path = posixpath.dirname(parsed.path)
        if not dir_path.endswith('/'):
            dir_path += '/'

        def is_valid_segment(url):
            parsed_url = urllib.parse.urlparse(url)
            return parsed_url.path.startswith(dir_path)

        result = []
        pending_extinf = []
        removed = 0
        kept = 0
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                line = self._rewrite_m3u8_tag(line, source_url)
                result.append(line)
                i += 1
                continue
            if line.startswith("#EXTINF"):
                pending_extinf = [line]
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.startswith("#"):
                        pending_extinf.append(next_line)
                        i += 1
                    else:
                        media_url = urllib.parse.urljoin(source_url, next_line)
                        if is_valid_segment(media_url):
                            if media_url.endswith('.jpg'):
                                media_url = media_url[:-4] + '.ts'
                            result.extend(pending_extinf)
                            result.append(media_url)
                            kept += 1
                        else:
                            removed += 1
                        i += 1
                        break
                continue
            result.append(line)
            i += 1
        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")
        return "\n".join(result) + "\n"

    def _clean_m3u8_multi(self, lines, source_url):
        out = []
        for line in lines:
            if line.startswith("#"):
                out.append(line)
            else:
                child_url = urllib.parse.urljoin(source_url, line)
                out.append(self._m3u8_proxy_url(child_url))
        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urllib.parse.urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urllib.parse.urljoin(source_url, line)
        return line