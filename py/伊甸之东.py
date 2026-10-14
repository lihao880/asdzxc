# coding: utf-8
"""
站点: 伊甸之东
域名: https://xn--u0qp95j6dm.ydmagiccrownx.site/
类型: MacCMS 影视站 (HTML解析)
内容: 成人影片
特点: 播放页直接返回 m3u8 直链，无加密
"""
import json
import re
from urllib.parse import quote, urljoin, unquote, urlparse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.host = "https://xn--u0qp95j6dm.ydmagiccrownx.site"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36",
            "Referer": self.host + "/"
        }
        # 分类硬编码
        self.classes = [
            {"type_id": "time", "type_name": "最新影片"},
            {"type_id": "score", "type_name": "评分最高"}
        ]
        # 筛选（无额外筛选参数）
        self.filters = {
            "time": [],
            "score": []
        }

    def getName(self):
        return "伊甸之东"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """获取首页推荐列表"""
        url = f"{self.host}/index.php/index/index/by/time.html?sort_code=time"
        try:
            html = self.fetch(url, headers=self.headers).text
            items = self._parse_list(html)
            return {"list": items[:20]}
        except Exception as e:
            self.log({"action": "homeVideoContent_error", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        """分类列表"""
        page = pg or "1"
        if tid == "time":
            url = f"{self.host}/index.php/index/index/page/{page}.html?sort_code=time"
        elif tid == "score":
            url = f"{self.host}/index.php/index/index/page/{page}.html?sort_code=score"
        else:
            # 默认走最新
            url = f"{self.host}/index.php/index/index/page/{page}.html?sort_code=time"

        try:
            html = self.fetch(url, headers=self.headers).text
            items = self._parse_list(html)
            # 提取总页数
            pagecount = self._get_pagecount(html)
            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception as e:
            self.log({"action": "categoryContent_error", "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        """详情页 - 直接解析播放地址"""
        # 兼容处理：ids 可能是 int、str 或 list
        if isinstance(ids, list):
            vod_id = ids[0] if ids else ""
        else:
            vod_id = str(ids)
        if not vod_id:
            return {"list": []}

        url = f"{self.host}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
        try:
            html = self.fetch(url, headers=self.headers).text
            
            # 手动提取 player_aaaa JSON
            start = html.find('var player_aaaa=')
            if start == -1:
                return {"list": []}
            
            # 从 var player_aaaa= 后面开始提取 JSON
            json_start = start + len('var player_aaaa=')
            # 找到 JSON 结束位置：匹配平衡的 {}
            brace_count = 0
            json_end = json_start
            in_string = False
            escape_next = False
            
            for i in range(json_start, len(html)):
                ch = html[i]
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\':
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
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
            
            if brace_count != 0 or json_end <= json_start:
                return {"list": []}
            
            json_str = html[json_start:json_end]
            # 处理转义字符
            json_str = json_str.replace('\\/', '/')
            
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                try:
                    import ast
                    data = ast.literal_eval(json_str)
                except:
                    return {"list": []}
            
            vod_data = data.get("vod_data", {})
            play_url = data.get("url", "")
            
            if not play_url:
                return {"list": []}
            
            vod = {
                "vod_id": str(data.get("id", vod_id)),
                "vod_name": vod_data.get("vod_name", "未知视频"),
                "vod_pic": "",
                "vod_remarks": "",
                "vod_actor": vod_data.get("vod_actor", ""),
                "vod_director": vod_data.get("vod_director", ""),
                "vod_content": vod_data.get("vod_class", ""),
                "vod_play_from": "直链",
                "vod_play_url": f"播放${play_url}"
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent_error", "error": str(e), "url": url})
            return {"list": []}
    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        url = f"{self.host}/index.php/vod/search.html"
        try:
            resp = self.post(url, data={"wd": key}, headers=self.headers)
            html = resp.text
            items = self._parse_list(html)
            return {"list": items, "page": int(pg)}
        except Exception as e:
            self.log({"action": "searchContent_error", "error": str(e)})
            return {"list": [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        """播放 - 直链模式"""
        if not id:
            return {"parse": 1, "url": "", "header": self.headers}

        # 如果是 m3u8 或 mp4 直链
        if id.endswith((".m3u8", ".mp4")):
            if id.endswith(".m3u8"):
                return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": {}}
            return {"parse": 0, "url": id, "header": {"User-Agent": self.headers["User-Agent"]}}

        # 其他情况降级嗅探
        return {"parse": 1, "url": id, "header": self.headers}

    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址"""
        return self.getProxyUrl() + "&url=" + quote(str(url or ""), safe="")

    def localProxy(self, param):
        """m3u8 本地代理（暂不过滤广告，如用户反馈广告再启用）"""
        target = unquote(str((param or {}).get("url", "") or ""))
        if not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]
        try:
            res = self.fetch(target, headers={"User-Agent": self.headers["User-Agent"]}, timeout=15, verify=False)
            if not res or getattr(res, "status_code", 0) != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            raw = getattr(res, "content", b"") or b""
            text = raw.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            # 重写相对路径为绝对路径
            cleaned = self._rewrite_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log("m3u8代理失败: " + str(e))
            return [500, "text/plain", b"m3u8 proxy error"]

    def _rewrite_m3u8(self, text, source_url):
        """重写 m3u8 中的相对路径为绝对路径，并过滤广告分片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 如果是主播放列表（包含 #EXT-X-STREAM-INF），需要代理子播放列表
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        # 普通分片列表 - 过滤广告分片
        source_path = urlparse(source_url).path
        source_parts = [p for p in source_path.split("/") if p]
        # 提取内容根路径（前两级目录）
        content_root = "/" + "/".join(source_parts[:2]) + "/" if len(source_parts) >= 2 else ""
        # 如果内容根路径为空，使用 source_url 的目录
        if not content_root:
            content_root = "/" + "/".join(source_parts[:-1]) + "/" if source_parts else "/"

        out = []
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
                # 分片 URL
                media = line
                # 如果是相对路径，转为绝对路径
                if not media.startswith(("http://", "https://")):
                    media = urljoin(source_url, media)
                # 检查是否为广告分片（通常不在内容根路径下）
                media_path = urlparse(media).path
                if content_root and content_root not in media_path:
                    removed += 1
                    pending = []
                    continue
                # 检查常见的广告关键词
                ad_keywords = ['ad', 'advert', 'banner', 'promo', 'sponsor', 'tracking', 'analytics', 'preload', 'pre-roll']
                media_lower = media.lower()
                is_ad = any(kw in media_lower for kw in ad_keywords)
                if is_ad:
                    removed += 1
                    pending = []
                    continue
                # 保留非广告分片
                segments = []
                for p in pending:
                    if p.startswith("#") and (p.startswith("#EXT-X-KEY") or p.startswith("#EXT-X-MAP")):
                        # 重写 KEY/MAP 的 URI
                        def repl(m):
                            return 'URI="' + urljoin(source_url, m.group(1)) + '"'
                        p = re.sub(r'URI="([^"]+)"', repl, p)
                    segments.append(p)
                segments.append(media)
                out.extend(segments)
                pending = []
                continue
            # 处理非分片行
            if line.startswith("#") and not line.startswith("#EXTINF"):
                if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
                    def repl2(m):
                        return 'URI="' + urljoin(source_url, m.group(1)) + '"'
                    line = re.sub(r'URI="([^"]+)"', repl2, line)
                out.append(line)

        # 过滤连续的重复标签
        filtered = []
        for line in out:
            if line in ["#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"]:
                if filtered and filtered[-1] == line:
                    continue
            filtered.append(line)

        if removed:
            self.log(f"m3u8已过滤广告分片: {removed} 个")

        return "\n".join(filtered) + "\n"
    def _parse_list(self, html):
        """解析列表页 / 首页 / 搜索页"""
        items = []
        # 匹配 .thumb 块
        pattern = r'<div class="thumb">.*?<a href="([^"]+)".*?<img src="([^"]+)".*?<span class="duration">([^<]*)</span>.*?<strong>([^<]*)</strong>.*?</div>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            href, pic, duration, title = match
            vod_id = re.search(r'/id/(\d+)/', href)
            if vod_id:
                items.append({
                    "vod_id": vod_id.group(1),
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": duration
                })
        return items

    def _get_pagecount(self, html):
        """提取总页数"""
        # 匹配分页中的最大数字
        page_nums = re.findall(r'<a href="[^"]*page/(\d+)\.html[^"]*">(\d+)</a>', html)
        if page_nums:
            nums = [int(n[1]) for n in page_nums]
            return max(nums) if nums else 1
        return 1