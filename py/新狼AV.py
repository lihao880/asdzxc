# coding: utf-8
"""
新狼AV - TVBox爬虫源
站点：https://cugauy.xlav8.bond
类型：成人影视站（HTML标准站）
特点：首页聚合各分类内容，详情页JS嵌入m3u8播放地址
"""

import re
import json
import urllib.parse
from urllib.parse import urljoin, quote, unquote
import json
from urllib.parse import urljoin, quote, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://cugauy.xlav8.bond"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        # 分类列表
        self.classes = [
            {"type_id": "20", "type_name": "亚洲情色"},
            {"type_id": "21", "type_name": "制服师生"},
            {"type_id": "22", "type_name": "卡通动漫"},
            {"type_id": "24", "type_name": "强奸乱伦"},
            {"type_id": "26", "type_name": "中文字幕"},
            {"type_id": "25", "type_name": "偷拍自拍"},
            {"type_id": "27", "type_name": "欧美性爱"},
            {"type_id": "28", "type_name": "人妻熟女"},
            {"type_id": "29", "type_name": "无码专区"},
            {"type_id": "23", "type_name": "三级伦理"},
        ]
        # 筛选（该站点无筛选功能）
        self.filters = {c["type_id"]: [] for c in self.classes}

    def getName(self):
        return "新狼AV"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """从首页提取推荐视频列表"""
        url = urljoin(self.host, "/cn/home/web/")
        try:
            html = self.fetch(url, headers=self.headers).text
            videos = self._parse_video_list(html)
            return {"list": videos[:20]}
        except Exception as e:
            self.log("homeVideoContent error: " + str(e))
            return {"list": []}
    def categoryContent(self, tid, pg, filter, extend):
        """分类列表（支持分页）"""
        page = pg or "1"
        # 分页URL格式：/vodtype/{tid}-{pg}.html，第一页为 /vodtype/{tid}.html
        if page == "1":
            url = urljoin(self.host, f"/vodtype/{tid}.html")
        else:
            url = urljoin(self.host, f"/vodtype/{tid}-{page}.html")

        try:
            html = self.fetch(url, headers=self.headers).text
            videos = self._parse_video_list(html)

            # 提取总页数
            pagecount = self._parse_pagecount(html)

            return {
                "list": videos,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception as e:
            self.log("categoryContent error: " + str(e))
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        """详情页 - 提取播放地址"""
        vid = ids[0] if ids else ""
        if not vid:
            return {"list": []}

        url = urljoin(self.host, f"/{vid}.html")
        try:
            html = self.fetch(url, headers=self.headers).text

            # 提取标题
            title_match = re.search(r'<h3>([^<]+)</h3>', html)
            title = title_match.group(1).strip() if title_match else ""

            # 提取播放地址（rawUrl）
            play_url = self._extract_play_url(html)

            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": "",
                "vod_remarks": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}" if play_url else ""
            }
            return {"list": [vod]}
        except Exception as e:
            self.log("detailContent error: " + str(e))
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        if not key:
            return {"list": [], "page": 1}

        url = urljoin(self.host, f"/s/index.html?wd={quote(key)}")
        try:
            html = self.fetch(url, headers=self.headers).text
            videos = self._parse_video_list(html)
            return {"list": videos, "page": int(pg)}
        except Exception as e:
            self.log("searchContent error: " + str(e))
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        """播放 - 带m3u8广告过滤"""
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        # 如果id本身是m3u8地址，走代理过滤广告
        if re.match(r'^https?://.*\.m3u8', id):
            return {
                "parse": 0, 
                "url": self._m3u8_proxy_url(id), 
                "header": self.headers
            }

        # 否则尝试从详情页提取
        try:
            if re.match(r'^https?://', id):
                url = id
                vid = id.split('/')[-1].replace('.html', '')
            else:
                vid = id
                url = urljoin(self.host, f"/{vid}.html")

            html = self.fetch(url, headers=self.headers).text
            play_url = self._extract_play_url(html)

            if play_url:
                return {
                    "parse": 0, 
                    "url": self._m3u8_proxy_url(play_url), 
                    "header": self.headers
                }
            else:
                return {"parse": 1, "url": url, "header": self.headers}
        except Exception as e:
            self.log("playerContent error: " + str(e))
            return {"parse": 1, "url": id, "header": self.headers}

    def recommendContent(self, ids, pg):
        """猜你喜欢（从详情页提取）"""
        vid = ids[0] if ids else ""
        if not vid:
            return {"list": []}

        url = urljoin(self.host, f"/{vid}.html")
        try:
            html = self.fetch(url, headers=self.headers).text
            # 查找"猜你喜欢"区域
            pattern = r'<h2>猜你喜欢</h2>(.*?)(?:</ul>|</div>)'
            match = re.search(pattern, html, re.DOTALL)
            if match:
                section = match.group(1)
                videos = self._parse_video_list(section)
                return {"list": videos[:12]}
            return {"list": []}
        except Exception as e:
            self.log("recommendContent error: " + str(e))
            return {"list": []}

    def getProxyUrl(self):
        """获取本地代理地址"""
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址"""
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        """
        m3u8本地代理 - 广告分片过滤
        """
        try:
            # 兼容多种参数格式
            target = ""
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "") or param.get("do", "")
                # 如果 param 是完整的请求参数，可能包含 url 字段
                if "url" in param:
                    target = param.get("url", "")
            elif isinstance(param, str):
                target = param
            else:
                target = str(param or "")

            # 处理各种前缀
            if target.startswith("url="):
                target = target[4:]
            elif target.startswith("do=py&url="):
                target = target[9:]

            # URL解码
            target = urllib.parse.unquote(str(target or ""))

            # 如果 target 仍然是空的，尝试从原始 param 中提取
            if not target and isinstance(param, dict):
                for key in ["url", "source", "u", "target"]:
                    if key in param and param[key]:
                        target = urllib.parse.unquote(str(param[key]))
                        break

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url: " + str(target).encode("utf-8")]

            # 添加完整的请求头
            headers = {
                "User-Agent": self.headers.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
                "Referer": target,
                "Origin": self.host,
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
            }

            resp = self.fetch(target, headers=headers, timeout=15, stream=True)
            if not resp:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")

            if not content:
                return [502, "text/plain", b"empty content"]

            # 检查是否为 m3u8
            if b"#EXTM3U" in content[:256]:
                text = content.decode("utf-8", errors="ignore")
                cleaned = self._clean_m3u8(text, target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

            # 非 m3u8 内容直接透传（可能是 ts/png 分片）
            # 根据文件扩展名设置 Content-Type
            content_type = "application/octet-stream"
            if target.endswith(".png"):
                content_type = "image/png"
            elif target.endswith(".ts"):
                content_type = "video/mp2t"
            elif target.endswith(".m4s"):
                content_type = "video/mp4"

            return [200, content_type, content]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]

    def _clean_m3u8(self, text, source_url):
        """清洗m3u8 - 过滤广告目录 + 补全 KEY URI"""
        import posixpath
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 检测是否为多码率 Master Playlist
        has_multi = any(line.startswith("#EXT-X-STREAM-INF") for line in lines)

        if has_multi:
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child))
            return "\n".join(out) + "\n"

        # 单码率：过滤广告目录
        ad_dirs = [
            '5215af9565c8b6ce',
            'a3712cbfc6902686',
            '48a95b6cc2e944fa',
            'UTe7qSJd',
        ]

        result = []
        pending_extinf = []
        removed = 0

        i = 0
        while i < len(lines):
            line = lines[i]

            # 补全 #EXT-X-KEY 的 URI
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                # 使用 _rewrite_m3u8_tag 补全 URI
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
                        is_ad = False
                        for ad_dir in ad_dirs:
                            if ad_dir in media_url:
                                is_ad = True
                                break
                        if is_ad:
                            removed += 1
                        else:
                            # 替换 .jpg -> .ts
                            if media_url.endswith('.jpg'):
                                media_url = media_url[:-4] + '.ts'
                            result.extend(pending_extinf)
                            result.append(media_url)
                        i += 1
                        break
                continue

            result.append(line)
            i += 1

        if removed:
            self.log(f"新狼AV m3u8已过滤广告分片: {removed}个")

        output = "\n".join(result)
        self.log(f"新狼AV 过滤后m3u8预览: {output[:500]}")
        return output + "\n"
    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI（补全绝对地址）"""
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
    def destroy(self):
        pass

    # ========== 辅助方法 ==========

    def _parse_video_list(self, html):
        """从HTML中解析视频列表 - 使用 content-list 作为锚点"""
        videos = []
        
        # 先找到 content-list 区域
        list_match = re.search(r'<ul[^>]*class="content-list"[^>]*>(.*?)</ul>', html, re.DOTALL)
        if not list_match:
            return videos
        
        list_html = list_match.group(1)
        
        # 方法1：分类页结构 - <a class="v" href="/{id}.html">
        # 先找到所有卡片
        cards = re.findall(r'<a[^>]*class="v"[^>]*href="/(\d+\.html)"[^>]*>(.*?)</a>', list_html, re.DOTALL)
        
        for href, card_html in cards:
            vid = href.replace('.html', '')
            # 提取封面
            pic_match = re.search(r'background-image:url\(([^)]+)\)', card_html)
            pic = pic_match.group(1).strip().strip("'\"") if pic_match else ""
            # 提取标题
            title_match = re.search(r'<div[^>]*class="v-title">([^<]+)</div>', card_html)
            title = title_match.group(1).strip() if title_match else ""
            if vid and title:
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        
        if videos:
            return videos
        
        # 方法2：首页结构 - <div class="v"> 包含 <a class="v-link">
        parts = re.split(r'<div[^>]*class="v"[^>]*>', list_html)
        for part in parts[1:]:
            href_match = re.search(r'<a[^>]*class="v-link"[^>]*href="/(\d+\.html)"', part)
            if not href_match:
                continue
            vid = href_match.group(1).replace('.html', '')
            pic_match = re.search(r'background-image:url\(([^)]+)\)', part)
            pic = pic_match.group(1).strip().strip("'\"") if pic_match else ""
            title_match = re.search(r'<div[^>]*class="v-title">([^<]+)</div>', part)
            title = title_match.group(1).strip() if title_match else ""
            if vid and title:
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return videos
    def _parse_pagecount(self, html):
        """从分页控件提取总页数"""
        # 匹配 "1/238" 格式
        match = re.search(r'(\d+)\s*/\s*(\d+)', html)
        if match:
            return int(match.group(2))
        return 99

    def _extract_play_url(self, html):
        """从详情页JS中提取m3u8播放地址"""
        # 匹配 rawUrl = '...'
        match = re.search(r"rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html)
        if match:
            raw = match.group(1)
            # 提取.m3u8地址
            m3u8_match = re.search(r'(https?://[^\s$#]+\.m3u8(?:\?[^\s#]*)?)', raw)
            if m3u8_match:
                return m3u8_match.group(1)
        return ""