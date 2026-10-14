# coding: utf-8
"""
站点: 黄色宝库-Hsbk.CC (bk678.cc)
类型: 成人影视站 (MacCMS)
特点: 标准MacCMS架构，m3u8直链播放
域名: https://www.bk678.cc/
备用: www.hsbk.cc, www.bk567.cc
分类: 日韩AV(1), 国产系列(2), 欧美(3), 无码中文字幕(5), 有码中文字幕(6), 日本无码(7), 日本有码(8), 国产视频(9), 欧美高清(10), 动漫剧情(11)
"""

import re
import json
from urllib.parse import urljoin, quote, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.bk678.cc/"
        self.classes = [
            {"type_id": "1", "type_name": "日韩AV"},
            {"type_id": "2", "type_name": "国产系列"},
            {"type_id": "3", "type_name": "欧美"},
            {"type_id": "5", "type_name": "无码中文字幕"},
            {"type_id": "6", "type_name": "有码中文字幕"},
            {"type_id": "7", "type_name": "日本无码"},
            {"type_id": "8", "type_name": "日本有码"},
            {"type_id": "9", "type_name": "国产视频"},
            {"type_id": "10", "type_name": "欧美高清"},
            {"type_id": "11", "type_name": "动漫剧情"},
        ]
        self.filters = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host,
        }

    def getName(self):
        return "黄色宝库"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐视频"""
        try:
            html = self.fetch(self.host, headers=self.headers).text
            return {"list": self._parse_video_list(html)}
        except Exception as e:
            self.log("homeVideoContent error: " + str(e))
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        """分类列表页"""
        page = pg or "1"
        url = f"{self.host}vodtype/{tid}-{page}/"

        try:
            html = self.fetch(url, headers=self.headers).text
            videos = self._parse_video_list(html)
            pagecount = self._parse_page_count(html)
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
        """详情页 - 从播放页提取m3u8"""
        url = ids[0]
        if not url.startswith("http"):
            url = urljoin(self.host, url)

        try:
            res = self.fetch(url, headers=self.headers)
            raw_content = getattr(res, "content", b"") or b""
            html = raw_content.decode("utf-8", errors="ignore")
            
            # 提取 m3u8
            m3u8 = ""
            m3u8_match = re.search(r'var player_aaaa\s*=\s*\{[\s\S]*?"url"\s*:\s*"([^"]+)"', html)
            if m3u8_match:
                m3u8 = m3u8_match.group(1).replace("\\/", "/")
            
            # 提取标题
            title_match = re.search(r'<h3 class="title">([^<]+)</h3>', html)
            title = title_match.group(1).strip() if title_match else ""
            
            vod = {
                "vod_id": url,
                "vod_name": title or "视频",
                "vod_pic": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "直链",
                "vod_play_url": f"播放${m3u8}" if m3u8 else "",
            }
            return {"list": [vod]}
        except Exception as e:
            self.log("detailContent error: " + str(e))
            return {"list": []}
    def searchContent(self, key, quick=False, pg="1"):
        """搜索"""
        page = pg or "1"
        # MacCMS 搜索URL格式
        url = f"{self.host}vodsearch/-------------.html?wd={quote(key)}&page={page}"

        try:
            html = self.fetch(url, headers=self.headers).text
            videos = self._parse_search_list(html)
            pagecount = self._parse_page_count(html)
            return {
                "list": videos,
                "page": int(page),
                "pagecount": pagecount
            }
        except Exception as e:
            self.log("searchContent error: " + str(e))
            return {"list": [], "page": int(page)}

    def playerContent(self, flag, id, vipFlags=""):
        """播放地址解析"""
        # id 可能是m3u8直链或播放页URL
        if id.startswith("http") and (".m3u8" in id or ".mp4" in id):
            if ".m3u8" in id:
                return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": self.headers}
            return {"parse": 0, "url": id, "header": self.headers}

        # 如果是播放页URL，提取m3u8
        if id.startswith("http"):
            try:
                html = self.fetch(id, headers=self.headers).text
                m3u8_url = self._extract_m3u8(html)
                if m3u8_url:
                    return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": self.headers}
            except:
                pass

        return {"parse": 1, "url": id, "header": self.headers}

    def _parse_video_list(self, html):
        """解析视频列表 - 优化版"""
        videos = []
        # 分割视频项，使用更简单的匹配
        items = re.findall(r'<div class="stui-vodlist__box">(.*?)</div>\s*</div>', html, re.DOTALL)
        for item in items:
            # 提取链接
            href_match = re.search(r'<a[^>]*href="([^"]+)"', item)
            if not href_match:
                continue
            href = href_match.group(1)
            
            # 提取封面
            img_match = re.search(r'data-original="([^"]+)"', item)
            img = img_match.group(1) if img_match else ""
            
            # 提取时长
            duration_match = re.search(r'<span class="pic-text[^"]*">([^<]*)</span>', item)
            duration = duration_match.group(1).strip() if duration_match else ""
            
            # 提取标题
            title_match = re.search(r'<h4 class="title">.*?<a[^>]*>([^<]+)</a>', item, re.DOTALL)
            title = title_match.group(1).strip() if title_match else ""
            
            if href and title:
                video_id = href if href.startswith("/") else "/" + href
                videos.append({
                    "vod_id": video_id,
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": duration,
                })
                if len(videos) >= 20:  # 限制返回数量，提高速度
                    break
        return videos
    def _parse_search_list(self, html):
        """解析搜索列表"""
        videos = []
        # 搜索页面的视频项结构
        items = re.findall(r'<div class="stui-vodlist__box">(.*?)</div>\s*</div>', html, re.DOTALL)
        for item in items:
            # 提取链接
            href_match = re.search(r'<a[^>]*href="([^"]+)"', item)
            if not href_match:
                continue
            href = href_match.group(1)
            
            # 提取封面
            img_match = re.search(r'data-original="([^"]+)"', item)
            img = img_match.group(1) if img_match else ""
            
            # 提取标题
            title_match = re.search(r'<h4 class="title">.*?<a[^>]*>([^<]+)</a>', item, re.DOTALL)
            title = title_match.group(1).strip() if title_match else ""
            
            # 提取时长
            duration_match = re.search(r'<span class="pic-text[^"]*">([^<]*)</span>', item)
            duration = duration_match.group(1).strip() if duration_match else ""
            
            if href and title and title != "首页":
                video_id = href if href.startswith("/") else "/" + href
                videos.append({
                    "vod_id": video_id,
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": duration,
                })
        
        # 如果上面没匹配到，尝试直接匹配搜索结果中的链接
        if not videos:
            pattern = r'<a class="stui-vodlist__thumb[^"]*" href="([^"]+)"[^>]*data-original="([^"]+)"[^>]*>.*?<h4 class="title">.*?<a[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html, re.DOTALL)
            for href, img, title in matches:
                if title and title != "首页":
                    video_id = href if href.startswith("/") else "/" + href
                    videos.append({
                        "vod_id": video_id,
                        "vod_name": title.strip(),
                        "vod_pic": img,
                        "vod_remarks": "",
                    })
        return videos
    def _parse_page_count(self, html):
        """解析总页数"""
        # 匹配分页链接，如 /vodtype/1-2/ 或 尾页链接
        page_nums = re.findall(r'/vodtype/\d+-(\d+)/', html)
        if page_nums:
            return max(int(p) for p in page_nums)
        # 检查是否有 "尾页" 链接
        tail_match = re.search(r'/vodtype/\d+-(\d+)/"[^>]*>尾页', html)
        if tail_match:
            return int(tail_match.group(1))
        # 检查是否有 "下一页" 链接
        if 'class="next page-link"' in html or '下一页' in html:
            return 50
        return 1

    def _parse_detail(self, html, base_url):
        """解析详情页 - 提取m3u8"""
        # 标题 - 从多种可能位置提取
        title = ""
        title_match = re.search(r'<h3 class="title">([^<]+)</h3>', html)
        if title_match:
            title = title_match.group(1).strip()
        else:
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                title = title_match.group(1).strip()
                title = re.sub(r'\s*[-|]\s*.*$', '', title)

        # 从 player_aaaa 提取播放地址
        m3u8_url = self._extract_m3u8(html)
        
        # 调试日志
        self.log("m3u8_url: " + str(m3u8_url))
        self.log("title: " + str(title))

        # 构建vod
        vod = {
            "vod_id": base_url,
            "vod_name": title or "视频",
            "vod_pic": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "直链",
            "vod_play_url": f"播放${m3u8_url}" if m3u8_url else "",
        }
        return vod
    def _extract_m3u8(self, html):
        """从HTML中提取m3u8地址"""
        # 方法1: player_aaaa 变量 (最可靠)
        # 使用更宽松的匹配，提取url字段
        pattern1 = r'var player_aaaa\s*=\s*\{[^}]*"url"\s*:\s*"([^"]+)"'
        match = re.search(pattern1, html)
        if match:
            url = match.group(1).replace("\\/", "/")
            if ".m3u8" in url:
                return url

        # 方法2: 在script中查找包含m3u8的变量
        pattern2 = r'url\s*:\s*["\']([^"\']+\.m3u8)["\']'
        matches = re.findall(pattern2, html)
        if matches:
            return matches[0].replace("\\/", "/")

        # 方法3: videojs sources
        pattern3 = r'sources:\s*\[\s*\{\s*src:\s*["\']([^"\']+\.m3u8)["\']'
        match = re.search(pattern3, html)
        if match:
            return match.group(1).replace("\\/", "/")

        # 方法4: 直接在html中查找m3u8
        pattern4 = r'https?://[^\s"\']+\.m3u8'
        matches = re.findall(pattern4, html)
        if matches:
            for m in matches:
                if "index.m3u8" in m or "playlist" in m:
                    return m
            return matches[0]

        return None
    def _m3u8_proxy_url(self, url):
        """m3u8代理地址"""
        proxy_base = self.getProxyUrl()
        if "?do=py" in proxy_base:
            return proxy_base + "&url=" + quote(str(url or ""), safe="")
        return proxy_base + "?do=py&url=" + quote(str(url or ""), safe="")

    def localProxy(self, param):
        """m3u8本地代理 - 简化版"""
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            # 直接请求m3u8
            res = self.fetch(target, headers=self.headers, timeout=15)
            if not res or getattr(res, "status_code", 0) != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]

            raw = getattr(res, "content", b"") or b""
            text = raw.decode("utf-8", errors="ignore")

            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            # 只做路径补全，不做广告过滤
            cleaned = self._rewrite_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log("localProxy error: " + str(e))
            return [500, "text/plain", str(e).encode("utf-8", errors="ignore")]

    def _rewrite_m3u8(self, text, source_url):
        """重写m3u8：补全相对路径"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        out = []
        for line in lines:
            if line.startswith("#"):
                if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
                    def repl(match):
                        return 'URI="' + urljoin(source_url, match.group(1)) + '"'
                    line = re.sub(r'URI="([^"]+)"', repl, line)
                out.append(line)
            else:
                if not line.startswith(("http://", "https://")):
                    line = urljoin(source_url, line)
                out.append(line)
        return "\n".join(out) + "\n"
    def _clean_m3u8(self, text, source_url):
        """清洗m3u8：过滤广告分片，保留正片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 处理多码率 Master Playlist
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

        # 从 #EXT-X-KEY 提取正片目录
        main_dir = source_dir
        for line in lines:
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                uri_match = re.search(r'URI="([^"]+)"', line)
                if uri_match:
                    key_path = uri_match.group(1)
                    if not key_path.startswith("http"):
                        key_dir = posixpath.dirname(key_path)
                        if key_dir and key_dir != "/":
                            main_dir = key_dir + "/"
                            break

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
                media_url = urljoin(source_url, line)
                media_parsed = urlparse(media_url)

                is_ad = not media_parsed.path.startswith(main_dir)

                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                else:
                    removed += 1
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urljoin(source_url, line))
            else:
                segments.append(line)

        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        if removed:
            self.log("m3u8已过滤广告分片: %d" % removed)
        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI（补全绝对地址）"""
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)

        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)

        return line

    def siteInfo(self):
        """站点信息"""
        return {
            "name": "黄色宝库",
            "domain": "bk678.cc",
            "type": "成人影视站",
            "description": "MacCMS标准架构，m3u8直链播放"
        }