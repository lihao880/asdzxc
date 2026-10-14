# coding: utf-8
import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.host = "https://daolys.yzqt4.makeup"
        self.classes = [
            {"type_id": "20", "type_name": "偷拍自拍"},
            {"type_id": "21", "type_name": "强奸乱伦"},
            {"type_id": "22", "type_name": "人妻熟女"},
            {"type_id": "23", "type_name": "制服情景"},
            {"type_id": "24", "type_name": "国产情色"},
            {"type_id": "25", "type_name": "亚洲精品"},
            {"type_id": "26", "type_name": "卡通动漫"},
            {"type_id": "27", "type_name": "欧美性爱"},
            {"type_id": "28", "type_name": "精品三级"},
        ]
        self.filters = {
            "20": [], "21": [], "22": [], "23": [], "24": [],
            "25": [], "26": [], "27": [], "28": [],
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    def getName(self):
        return "一柱擎天"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """
        首页推荐：从偷拍自拍分类页获取数据（因首页被拦截）
        """
        try:
            # 从分类页获取数据
            result = self.categoryContent("20", "1", False, {})
            items = result.get('list', [])
            # 添加分类名作为备注
            for item in items:
                item['vod_remarks'] = "偷拍自拍"
            self.log({"action": "homeVideoContent", "items_count": len(items)})
            return {"list": items}
        except Exception as e:
            self.log({"action": "homeVideoContent_error", "error": str(e)})
            return {"list": []}
    def categoryContent(self, tid, pg, filter, extend):
        """
        分类列表页 - 使用正确的分页格式 /vodtype/{tid}-{pg}.html
        """
        try:
            page = pg or "1"
            # 构造正确的分页URL
            url = f"{self.host}/vodtype/{tid}-{page}.html"
            
            resp = self.fetch(url, headers=self.headers, timeout=20)
            if not resp:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            
            html = resp.text if hasattr(resp, 'text') else ""
            if not html:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            
            items = []
            # 解析视频卡片
            card_pattern = r'<a[^>]*href=[\'"]/(\d+\.html)[\'"][^>]*>.*?<div[^>]*class=[\'"]item-cove[\'"][^>]*><img[^>]*src=[\'"]([^\'"]+)[\'"][^>]*>.*?<div[^>]*class=[\'"]title[\'"][^>]*>([^<]+)</div>'
            cards = re.findall(card_pattern, html, re.DOTALL)
            
            for detail_link, pic, title in cards:
                title = title.strip()
                if title:
                    items.append({
                        "vod_id": detail_link.replace(".html", ""),
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": "",
                    })
            
            # 提取总页数
            pagecount = 10
            page_match = re.search(r'共(\d+)页', html)
            if page_match:
                pagecount = int(page_match.group(1))
            
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
        """
        详情页解析
        """
        try:
            vod_id = str(ids[0])
            url = f"{self.host}/{vod_id}.html"
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp:
                return {"list": []}
            html = resp.text if hasattr(resp, 'text') else ""
            if not html:
                return {"list": []}
            # 提取标题
            title_pattern = r'<div class=[\'"]title[\'"]>([^<]+)</div>'
            title_match = re.search(title_pattern, html)
            title = title_match.group(1).strip() if title_match else "未知标题"
            # 提取封面图
            pic_pattern = r'<div class=[\'"]item-cove[\'"]><img src=[\'"]([^\'"]+)[\'"]>'
            pic_match = re.search(pic_pattern, html)
            pic = pic_match.group(1) if pic_match else ""
            # 提取播放地址（m3u8或mp4）
            play_url = ""
            # 尝试从iframe中提取
            iframe_pattern = r'<iframe[^>]*src=[\'"]([^\'"]+)[\'"][^>]*>'
            iframe_match = re.search(iframe_pattern, html)
            if iframe_match:
                play_url = iframe_match.group(1)
            # 尝试从video标签提取
            video_pattern = r'<video[^>]*src=[\'"]([^\'"]+)[\'"][^>]*>'
            video_match = re.search(video_pattern, html)
            if video_match:
                play_url = video_match.group(1)
            # 尝试从script中提取m3u8
            m3u8_pattern = r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']'
            m3u8_match = re.search(m3u8_pattern, html)
            if m3u8_match:
                play_url = m3u8_match.group(1)
            if play_url:
                play_url = urllib.parse.urljoin(self.host, play_url)
            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
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
        """
        搜索功能
        """
        try:
            # 使用正确的搜索URL，关键词需要URL编码
            encoded_key = urllib.parse.quote(key)
            url = f"{self.host}/s/index.html?wd={encoded_key}"
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp:
                return {"list": [], "page": 1}
            html = resp.text if hasattr(resp, 'text') else ""
            if not html:
                return {"list": [], "page": 1}
            items = []
            # 搜索页使用 col-md-4
            card_pattern = r'<a[^>]*class=[\'"]col-md-4 item-video-container[\'"][^>]*href=[\'"]/(\d+\.html)[\'"][^>]*>.*?<div[^>]*class=[\'"]item-video[\'"][^>]*>.*?<img[^>]*src=[\'"]([^\'"]+)[\'"][^>]*>.*?<div[^>]*class=[\'"]title[\'"][^>]*>([^<]+)</div>'
            cards = re.findall(card_pattern, html, re.DOTALL)
            for detail_link, pic, title in cards:
                title = title.strip()
                if title:
                    items.append({
                        "vod_id": detail_link.replace(".html", ""),
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": "",
                    })
            return {"list": items, "page": int(pg)}
        except Exception as e:
            self.log({"action": "searchContent_error", "error": str(e)})
            return {"list": [], "page": 1}
    def playerContent(self, flag, id, vipFlags):
        """
        播放地址解析
        """
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        play_url = str(id).strip()
        # 如果是m3u8链接，直接返回
        if play_url.startswith("http") and ".m3u8" in play_url:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(play_url),
                "header": self.headers,
            }
        # 如果是mp4链接，直接返回
        if play_url.startswith("http") and ".mp4" in play_url:
            return {"parse": 0, "url": play_url, "header": self.headers}
        # 如果是相对路径，补全
        if play_url and not play_url.startswith("http"):
            play_url = urllib.parse.urljoin(self.host, play_url)
            if ".m3u8" in play_url:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(play_url),
                    "header": self.headers,
                }
            if ".mp4" in play_url:
                return {"parse": 0, "url": play_url, "header": self.headers}
        # 降级嗅探
        return {"parse": 1, "url": play_url, "header": self.headers}

    def recommendContent(self, ids, pg):
        """
        相关推荐 - 从详情页解析视频推荐
        """
        try:
            if not ids or not ids[0]:
                return {"list": []}
            vod_id = str(ids[0])
            url = f"{self.host}/{vod_id}.html"
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp:
                return {"list": []}
            html = resp.text if hasattr(resp, 'text') else ""
            if not html:
                return {"list": []}
            items = []
            # 查找视频推荐区域
            # 先找 "视频推荐" 标题的位置
            title_idx = html.find('视频推荐')
            if title_idx == -1:
                return {"list": []}
            # 从标题开始，找到下一个 page-header 或结束
            start_idx = html.find('<div class="row"', title_idx)
            if start_idx == -1:
                start_idx = html.find("<div class='row'", title_idx)
            if start_idx == -1:
                return {"list": []}
            # 找到匹配的结束 </div>
            # 从start_idx开始找配对结束
            end_idx = start_idx
            depth = 0
            # 简单策略：找下一个 </div> 但需要跳过嵌套
            # 从 start_idx 开始，找到 row 的结束（下一个 page-header 或视频推荐后的第二个 row 结束）
            # 直接取到下一个 page-header 之前
            next_header = html.find('<h1', start_idx + 1)
            if next_header == -1:
                end_idx = len(html)
            else:
                end_idx = next_header
            block = html[start_idx:end_idx]
            # 解析推荐卡片
            card_pattern = r'<a[^>]*href=[\'"]/(\d+\.html)[\'"][^>]*>.*?<img[^>]*src=[\'"]([^\'"]+)[\'"][^>]*>.*?<div[^>]*class=[\'"]title[\'"][^>]*>([^<]+)</div>'
            cards = re.findall(card_pattern, block, re.DOTALL)
            for detail_link, pic, title in cards:
                title = title.strip()
                if title:
                    items.append({
                        "vod_id": detail_link.replace(".html", ""),
                        "vod_name": title,
                        "vod_pic": pic,
                    })
            return {"list": items}
        except Exception as e:
            self.log({"action": "recommendContent_error", "error": str(e)})
            return {"list": []}
    def destroy(self):
        pass

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址"""
        return self.getProxyUrl() + "&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        """
        m3u8本地代理 + 广告分片过滤
        """
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
            elif target.endswith(".key") or target.endswith(".bin"):
                content_type = "application/octet-stream"
            return [200, content_type, content]
        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]

    def _clean_m3u8(self, text, source_url):
        """清洗m3u8：过滤广告分片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"
        # 检测是否为多码率
        is_multi = any(line.startswith("#EXT-X-STREAM-INF") for line in lines)
        if is_multi:
            return self._clean_m3u8_multi(lines, source_url)
        return self._clean_m3u8_single(lines, source_url)

    def _clean_m3u8_single(self, lines, source_url):
        """单码率m3u8过滤"""
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
        """多码率m3u8处理"""
        out = []
        for line in lines:
            if line.startswith("#"):
                out.append(line)
            else:
                child_url = urllib.parse.urljoin(source_url, line)
                out.append(self._m3u8_proxy_url(child_url))
        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI"""
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