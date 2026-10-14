# coding: utf-8
# 站点信息沉淀（法则24）
# 主域名: https://euh.dfswh5.top
# 备用域名: 无
# 发布页: 无
# 内容类型: 成人影视（国产/日韩/欧美/动漫等）
# 特殊说明: 悟空CMS模板，分类列表页直接渲染
# 最后验证时间: 2026-08-31
# 来源: 用户提供 https://euh.dfswh5.top/cn/home/web/

import json
import re
import posixpath
from urllib.parse import quote, urljoin, unquote, urlparse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://euh.dfswh5.top"
        self.base_path = ""
        self.site_name = "东方色文化"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        
        # 分类列表（从首页导航提取）
        self.classes = [
            {"type_id": "1", "type_name": "人妻熟女"},
            {"type_id": "2", "type_name": "强奸乱伦"},
            {"type_id": "3", "type_name": "制服师生"},
            {"type_id": "4", "type_name": "网红主播"},
            {"type_id": "20", "type_name": "偷拍自拍"},
            {"type_id": "21", "type_name": "自慰自淫"},
            {"type_id": "22", "type_name": "国产专区"},
            {"type_id": "23", "type_name": "虐待同性"},
            {"type_id": "24", "type_name": "日韩精品"},
            {"type_id": "25", "type_name": "欧美性爱"},
            {"type_id": "26", "type_name": "卡通动漫"},
            {"type_id": "27", "type_name": "三级伦理"}
        ]
        
        # 无筛选功能
        self.filters = {}

    def getName(self):
        return self.site_name

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        url = self.host + "/cn/home/web/"
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": []}
        
        html = resp.text or ""
        # 从首页最新电影区域提取
        pattern = r'<a class="stui-vodlycms_list__thumb lazyload" href="([^"]+)" title="([^"]*)"[^>]*data-original="([^"]+)"[^>]*>.*?<span class="pic-text text-right">([^<]*)</span>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        result = []
        seen = set()
        for href, title, pic, remark in matches:
            if href in seen:
                continue
            seen.add(href)
            vod_id = self._extract_vod_id_from_url(href)
            if not vod_id:
                continue
            result.append({
                "vod_id": vod_id,
                "vod_name": title.strip() if title else "视频",
                "vod_pic": pic.strip() if pic else "",
                "vod_remarks": remark.strip() if remark else ""
            })
            if len(result) >= 30:
                break
        
        return {"list": result}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg is not None else 1
        except (ValueError, TypeError):
            page = 1
        
        # 分页URL格式: /vodtype/{tid}-{page}.html
        if page <= 1:
            url = f"{self.host}/vodtype/{tid}.html"
        else:
            url = f"{self.host}/vodtype/{tid}-{page}.html"
        
        self.log({"action": "categoryContent", "tid": tid, "page": page, "url": url})
        
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
        
        html = resp.text or ""
        video_items = self._parse_video_items(html)
        
        # 提取分页信息
        pagecount = 1
        # 从分页中提取总页数
        page_match = re.search(r'<a href="[^"]*">\s*(\d+)/(\d+)\s*</a>', html)
        if page_match:
            pagecount = int(page_match.group(2))
        else:
            # 尝试从尾页提取
            tail_match = re.search(r'<a href="/vodtype/.*?-(\d+)\.html">尾页</a>', html)
            if tail_match:
                pagecount = int(tail_match.group(1))
        
        if pagecount < 1:
            pagecount = 1
        
        total = pagecount * 20
        
        return {
            "list": video_items,
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": total
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        
        vid = str(ids[0])
        # 如果是完整URL，提取ID
        if vid.startswith("http"):
            vod_id = self._extract_vod_id_from_url(vid)
            if not vod_id:
                vod_id = vid
        else:
            vod_id = vid
        
        # 详情页就是播放页
        detail_url = f"{self.host}/{vod_id}.html"
        
        resp = self.fetch(detail_url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": []}
        
        html = resp.text or ""
        
        # 提取标题
        title_match = re.search(r'<title>([^<]*)</title>', html)
        title = title_match.group(1).replace(" - 东方色文化", "").strip() if title_match else "视频"
        
        # 提取播放地址（从player_data或直接m3u8）
        play_url = ""
        
        # 尝试 player_data
        player_match = re.search(r'var\s+player_data\s*=\s*(\{[^}]+\})', html, re.DOTALL)
        if player_match:
            try:
                data_str = player_match.group(1)
                data_str = re.sub(r'/\*.*?\*/', '', data_str, flags=re.DOTALL)
                data_str = re.sub(r'//.*?$', '', data_str, flags=re.MULTILINE)
                data = json.loads(data_str)
                play_url = data.get("url", "")
            except:
                pass
        
        # 尝试 MacPlayer
        if not play_url:
            mac_match = re.search(r'MacPlayer\.PlayUrl\s*=\s*"([^"]+)"', html)
            if mac_match:
                play_url = mac_match.group(1)
        
        # 尝试直接提取m3u8
        if not play_url:
            m3u8_match = re.search(r'https?://[^"\']+\.m3u8[^"\']*', html)
            if m3u8_match:
                play_url = m3u8_match.group(0)
        
        # 尝试从 iframe src 提取
        if not play_url:
            iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', html)
            if iframe_match:
                iframe_url = iframe_match.group(1)
                if iframe_url.startswith("http"):
                    # 请求iframe页面提取m3u8
                    iframe_resp = self.fetch(iframe_url, headers=self.headers, timeout=10)
                    if iframe_resp and iframe_resp.status_code == 200:
                        iframe_html = iframe_resp.text or ""
                        m3u8_match = re.search(r'https?://[^"\']+\.m3u8[^"\']*', iframe_html)
                        if m3u8_match:
                            play_url = m3u8_match.group(0)
        
        vod_play_from = "直链"
        vod_play_url = f"第1集${play_url}" if play_url else ""
        
        result = [{
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }]
        
        return {"list": result}

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        
        search_url = f"{self.host}/s/index.html?wd={quote(key)}"
        resp = self.fetch(search_url, headers=self.headers, timeout=10)
        
        if not resp or resp.status_code != 200:
            return {"list": [], "page": 1}
        
        html = resp.text or ""
        
        # 检查是否无结果
        if re.search(r'没有找到|暂无数据|搜索无结果', html):
            return {"list": [], "page": 1}
        
        video_items = self._parse_video_items(html)
        return {"list": video_items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        
        play_url = str(id).strip()
        
        # 如果已经是m3u8直链，走代理过滤广告
        if play_url.startswith("http") and ".m3u8" in play_url:
            proxy_url = self._m3u8_proxy_url(play_url)
            return {
                "parse": 0,
                "url": proxy_url,
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        
        # 如果是详情页URL，提取播放地址
        if play_url.startswith("http") and ".html" in play_url:
            resp = self.fetch(play_url, headers=self.headers, timeout=15)
            if resp and resp.status_code == 200:
                html = resp.text or ""
                
                # 尝试 player_data
                player_match = re.search(r'var\s+player_data\s*=\s*(\{[^}]+\})', html, re.DOTALL)
                if player_match:
                    try:
                        data_str = player_match.group(1)
                        data_str = re.sub(r'/\*.*?\*/', '', data_str, flags=re.DOTALL)
                        data_str = re.sub(r'//.*?$', '', data_str, flags=re.MULTILINE)
                        data = json.loads(data_str)
                        direct_url = data.get("url", "")
                        if direct_url and direct_url.startswith("http") and ".m3u8" in direct_url:
                            proxy_url = self._m3u8_proxy_url(direct_url)
                            return {
                                "parse": 0,
                                "url": proxy_url,
                                "header": {"User-Agent": self.headers.get("User-Agent", "")}
                            }
                    except:
                        pass
                
                # 尝试直接提取m3u8
                m3u8_match = re.search(r'https?://[^"\']+\.m3u8[^"\']*', html)
                if m3u8_match:
                    proxy_url = self._m3u8_proxy_url(m3u8_match.group(0))
                    return {
                        "parse": 0,
                        "url": proxy_url,
                        "header": {"User-Agent": self.headers.get("User-Agent", "")}
                    }
        
        # 降级嗅探
        return {
            "parse": 1,
            "url": play_url,
            "header": {
                "User-Agent": self.headers.get("User-Agent", ""),
                "Referer": self.host + "/"
            }
        }
    def recommendContent(self, ids, pg):
        return {"list": []}

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址"""
        if not url:
            return ""
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url), safe="")

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"
    def destroy(self):
        pass

    def _extract_vod_id_from_url(self, url):
        if not url:
            return ""
        # 匹配 /数字.html
        match = re.search(r'/(\d+)\.html', url)
        if match:
            return match.group(1)
        return ""

    def _parse_video_items(self, html):
        """从HTML中解析视频列表"""
        # 使用更宽松的正则，支持跨行匹配
        pattern = r'<a\s+class="stui-vodlycms_list__thumb\s+lazyload"\s+href="([^"]+)"\s+title="([^"]*)"[^>]*\s+data-original="([^"]+)"[^>]*>.*?<span\s+class="pic-text\s+text-right">([^<]*)</span>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        result = []
        seen = set()
        for href, title, pic, remark in matches:
            if href in seen:
                continue
            seen.add(href)
            vod_id = self._extract_vod_id_from_url(href)
            if not vod_id:
                continue
            result.append({
                "vod_id": vod_id,
                "vod_name": title.strip() if title else "视频",
                "vod_pic": pic.strip() if pic else "",
                "vod_remarks": remark.strip() if remark else ""
            })
        
        # 如果上面的正则为空，尝试更简单的备选
        if not result:
            # 备选：直接从 li 中提取
            li_pattern = r'<li[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*title="([^"]*)"[^>]*data-original="([^"]+)"[^>]*>.*?<span[^>]*>([^<]*)</span>'
            matches2 = re.findall(li_pattern, html, re.DOTALL)
            for href, title, pic, remark in matches2:
                if href in seen:
                    continue
                seen.add(href)
                vod_id = self._extract_vod_id_from_url(href)
                if not vod_id:
                    continue
                result.append({
                    "vod_id": vod_id,
                    "vod_name": title.strip() if title else "视频",
                    "vod_pic": pic.strip() if pic else "",
                    "vod_remarks": remark.strip() if remark else ""
                })
        
        return result
    def localProxy(self, param):
        """m3u8本地代理 + 广告分片过滤"""
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                qs = urlparse(target).query
                parsed_qs = {}
                for part in qs.split("&"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        parsed_qs[k] = v
                if "url" in parsed_qs:
                    target = parsed_qs["url"]
            
            target = unquote(str(target or ""))
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]
            
            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp:
                return [502, "text/plain", b"fetch failed"]
            
            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]
            
            if b"#EXTM3U" in content[:512]:
                cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            
            return [200, "application/octet-stream", content]
            
        except Exception as e:
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]

    def _is_fake_image_stream(self, text, source_url):
        low_url = (source_url or "").lower()
        for sig in ("doyinapi", "svip", "imgcdn", "photo"):
            if sig in low_url:
                return True
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower().split("?")[0]
            if low.endswith((".png", ".jpg", ".jpeg", ".webp")):
                return True
        return False

    def _resolve_main_dir(self, lines, source_url):
        import posixpath
        from collections import Counter
        from urllib.parse import urlparse, urljoin
        
        parsed = urlparse(source_url)
        default_dir = posixpath.dirname(parsed.path)
        if not default_dir.endswith("/"):
            default_dir += "/"
        
        # 优先从 KEY 提取
        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            if key_uri.startswith("http"):
                key_path = urlparse(key_uri).path
            else:
                key_path = urlparse(urljoin(source_url, key_uri)).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        
        # 从 MAP 提取
        for line in lines:
            if not line.startswith("#EXT-X-MAP") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            map_uri = m.group(1)
            if map_uri.startswith("http"):
                map_path = urlparse(map_uri).path
            else:
                map_path = urlparse(urljoin(source_url, map_uri)).path
            map_dir = posixpath.dirname(map_path)
            if map_dir and map_dir != "/":
                return map_dir + "/"
        
        # DISCONTINUITY 之后的分片目录
        after_discontinuity = False
        for line in lines:
            if line == "#EXT-X-DISCONTINUITY":
                after_discontinuity = True
                continue
            if after_discontinuity and line and not line.startswith("#"):
                if line.startswith("http"):
                    seg_path = urlparse(line).path
                else:
                    seg_path = line
                seg_dir = posixpath.dirname(seg_path)
                if seg_dir and seg_dir != "/":
                    if seg_dir.startswith("/"):
                        seg_dir = seg_dir[1:]
                    return seg_dir + "/"
        
        # 统计分片目录
        seg_dirs = []
        for line in lines:
            if line and not line.startswith("#"):
                if line.startswith("http"):
                    seg_path = urlparse(line).path
                else:
                    seg_path = line
                seg_dir = posixpath.dirname(seg_path)
                if seg_dir and seg_dir != "/":
                    if seg_dir.startswith("/"):
                        seg_dir = seg_dir[1:]
                    seg_dirs.append(seg_dir + "/")
        
        if seg_dirs:
            dir_counter = Counter(seg_dirs)
            max_count = 0
            best_dir = default_dir
            for d, count in dir_counter.items():
                if count > max_count:
                    max_count = count
                    best_dir = d
            return best_dir
        
        return default_dir

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(m):
                uri = m.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)
        return line

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"
        
        # 第1层：图片流伪装
        if self._is_fake_image_stream(text, source_url):
            restored = text
            for ext in (".png", ".jpeg", ".jpg", ".webp"):
                restored = restored.replace(ext, ".ts")
            return restored
        
        # 第2层：多码率 - 子流走代理
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    if ".m3u8" in child.lower():
                        out.append(self._m3u8_proxy_url(child))
                    else:
                        out.append(child)
            return "\n".join(out) + "\n"
        
        # 第3层：锚点
        main_dir = self._resolve_main_dir(lines, source_url)
        if main_dir.startswith("/"):
            main_dir = main_dir[1:]
        if not main_dir.endswith("/"):
            main_dir += "/"
        
        # 第4层：过滤
        segments = []
        pending = []
        removed = 0
        kept = 0
        
        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urljoin(source_url, line)
                media_path = urlparse(media_url).path
                if media_path.startswith("/"):
                    media_path = media_path[1:]
                if media_path.startswith(main_dir):
                    segments.extend(pending)
                    segments.append(media_url)
                    kept += 1
                else:
                    removed += 1
                pending = []
                continue
            if line.startswith("#"):
                segments.append(line)
            else:
                segments.append(urljoin(source_url, line))
        
        if pending:
            removed += 1
        
        # 第5层：兜底
        if kept == 0 and removed > 0:
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"
        
        # 冗余标签清理
        NOISE = ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE")
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in NOISE:
                if not out or out[-1] in NOISE:
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in NOISE:
            out.pop()
        
        return "\n".join(out) + "\n"
