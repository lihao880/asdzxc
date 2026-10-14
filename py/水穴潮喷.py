# coding: utf-8
import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://lis.sxcp8.autos"
        self.base_path = "/sxcp"
        self.classes = [
            {"type_id": "20", "type_name": "国产自拍"},
            {"type_id": "21", "type_name": "制服丝袜"},
            {"type_id": "22", "type_name": "强奸乱伦"},
            {"type_id": "23", "type_name": "教师学生"},
            {"type_id": "24", "type_name": "素人系列"},
            {"type_id": "25", "type_name": "人妻熟女"},
            {"type_id": "26", "type_name": "日韩无码"},
            {"type_id": "27", "type_name": "日韩有码"},
            {"type_id": "28", "type_name": "中文字幕"},
            {"type_id": "29", "type_name": "欧美风情"},
            {"type_id": "30", "type_name": "经典伦理"},
            {"type_id": "31", "type_name": "卡通动漫"},
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        # 广告目录列表 - 只保留明确是广告的目录，正片目录不要放进来
        self.ad_dirs = [
            # 通用广告目录（只保留明确是广告的）
            '5215af9565c8b6ce', 'UTe7qSJd', 'UTxI1Mxv',
            'VmnacVi8', 'a3712cbfc6902686', '48a95b6cc2e944fa',
            # 注意：DbPXley4 和 H2rvyIMK 可能是正片目录，已移除
        ]
    def getName(self):
        return "水穴潮喷"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except:
                pass
            result = {}
            for part in extend.split(','):
                if '=' in part:
                    k, v = part.split('=', 1)
                    result[k.strip()] = v.strip()
            return result
        return {}

    def _parse_list_items(self, html, base_url):
        """从HTML解析视频列表 - 优先取 data-original"""
        items = []
        li_pattern = r'<li>(.*?)</li>'
        li_matches = re.findall(li_pattern, html, re.DOTALL)
        
        for li_html in li_matches:
            url_match = re.search(r'href="([^"]+)"', li_html)
            if not url_match:
                continue
            url = url_match.group(1)
            vod_id_match = re.search(r'/(\d+)\.html', url)
            if not vod_id_match:
                continue
            vod_id = vod_id_match.group(1)
            
            # 标题
            title = ""
            h2_match = re.search(r'<h2><a[^>]*>([^<]+)</a></h2>', li_html)
            if h2_match:
                title = h2_match.group(1).strip()
            else:
                title_match = re.search(r'title="([^"]+)"', li_html)
                if title_match:
                    title = title_match.group(1).strip()
            if not title:
                continue
            
            # 图片 - 只取 data-original，忽略 src 占位图
            pic = ""
            pic_match = re.search(r'data-original="([^"]+)"', li_html)
            if pic_match:
                pic = pic_match.group(1)
            # 如果 data-original 没有，才取 src（但排除占位图）
            if not pic or '220x307.jpg' in pic:
                src_match = re.search(r'src="([^"]+)"', li_html)
                if src_match and '220x307.jpg' not in src_match.group(1):
                    pic = src_match.group(1)
            
            # 观看次数
            remark = ""
            remark_match = re.search(r'<label[^>]*class="title"[^>]*>([^<]+)</label>', li_html)
            if remark_match:
                remark = remark_match.group(1).strip()
            
            items.append({
                "vod_id": str(vod_id),
                "vod_name": title,
                "vod_pic": urllib.parse.urljoin(base_url, pic) if pic else "",
                "vod_remarks": remark,
            })
        
        return items
    def _parse_play_url(self, html):
        """从播放页解析播放地址 - 支持多种格式"""
        # 方式1: player_data 对象
        match = re.search(r'player_data\s*=\s*\{[^}]*"url"\s*:\s*"([^"]+)"', html)
        if match:
            url = match.group(1).replace('\\/', '/')
            if url.startswith('http'):
                return url
        
        # 方式2: DPlayer 脚本中的 rawUrl
        match = re.search(r'const\s+rawUrl\s*=\s*[\'"]?([^\'";]+)[\'"]?', html)
        if match:
            url = match.group(1).strip()
            if url.startswith('http'):
                return url
        
        # 方式3: 直接搜索 m3u8 链接
        match = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html)
        if match:
            return match.group(0)
        
        # 方式4: 其他 JS 变量中的 URL
        match = re.search(r'"url"\s*:\s*"([^"]+)"', html)
        if match:
            url = match.group(1).replace('\\/', '/')
            if url.startswith('http'):
                return url
        
        return None
    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        url = self.host + self.base_path + "/"
        resp = self.fetch(url, headers=self.headers, timeout=15)
        if not resp or resp.status_code != 200:
            return {"list": []}
        html = resp.text
        items = []
        # 从最近更新区块提取
        pattern = r'<div class="modo_title top">.*?<h2><a href="#" target="#">最近更新</a></h2>.*?<ul class="lycms_list_tab_img" id="resize_list">(.*?)</ul>'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            items = self._parse_list_items(match.group(1), url)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        
        if page == "1":
            list_url = f"{self.host}/vodtype/{tid}.html"
        else:
            list_url = f"{self.host}/vodtype/{tid}-{page}.html"
        
        try:
            import requests
            # 使用 session 并禁用 SSL 验证警告
            session = requests.Session()
            session.verify = False
            resp = session.get(list_url, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                html = resp.text
                items = []
                li_pattern = r'<li>(.*?)</li>'
                li_matches = re.findall(li_pattern, html, re.DOTALL)
                for li_html in li_matches:
                    url_match = re.search(r'href="([^"]+)"', li_html)
                    if not url_match:
                        continue
                    url = url_match.group(1)
                    vod_id_match = re.search(r'/(\d+)\.html', url)
                    if not vod_id_match:
                        continue
                    vod_id = vod_id_match.group(1)
                    
                    # 标题
                    title = ""
                    h2_match = re.search(r'<h2><a[^>]*>([^<]+)</a></h2>', li_html)
                    if h2_match:
                        title = h2_match.group(1).strip()
                    if not title:
                        title_match = re.search(r'title="([^"]+)"', li_html)
                        if title_match:
                            title = title_match.group(1).strip()
                    if not title:
                        continue
                    
                    # 图片 - 优先 data-original，排除占位图
                    pic = ""
                    pic_match = re.search(r'data-original="([^"]+)"', li_html)
                    if pic_match:
                        pic = pic_match.group(1)
                    # 如果 data-original 是占位图或者没有，尝试 src
                    if not pic or '220x307.jpg' in pic:
                        src_match = re.search(r'src="([^"]+)"', li_html)
                        if src_match and '220x307.jpg' not in src_match.group(1):
                            pic = src_match.group(1)
                    
                    # 如果还是占位图，从整个 li 中找 data-original
                    if not pic or '220x307.jpg' in pic:
                        alt_match = re.search(r'data-original="([^"]+)"', li_html)
                        if alt_match and '220x307.jpg' not in alt_match.group(1):
                            pic = alt_match.group(1)
                    
                    items.append({
                        "vod_id": str(vod_id),
                        "vod_name": title,
                        "vod_pic": urllib.parse.urljoin(list_url, pic) if pic else "",
                        "vod_remarks": "",
                    })
                
                # 提取分页信息
                pagecount = 1
                page_match = re.search(r'(\d+)/(\d+)</a>', html)
                if page_match:
                    pagecount = int(page_match.group(2))
                page_links = re.findall(r'/vodtype/' + str(tid) + r'-(\d+)\.html', html)
                if page_links:
                    max_page = max([int(p) for p in page_links])
                    if max_page > pagecount:
                        pagecount = max_page
                
                return {
                    "list": items,
                    "page": int(page),
                    "pagecount": pagecount,
                    "limit": 20,
                    "total": 0,
                }
        except Exception as e:
            pass
        
        # 降级方案（同上，但保持一致性）
        if page != "1":
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        
        home_url = f"{self.host}{self.base_path}/"
        try:
            import requests
            session = requests.Session()
            session.verify = False
            resp = session.get(home_url, headers=self.headers, timeout=15)
            if resp.status_code != 200:
                return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
            html = resp.text
        except:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        
        items = []
        tid_to_name = {
            "20": "国产自拍", "21": "制服丝袜", "22": "强奸乱伦",
            "23": "教师学生", "24": "素人系列", "25": "人妻熟女",
            "26": "日韩无码", "27": "日韩有码", "28": "中文字幕",
            "29": "欧美风情", "30": "经典伦理", "31": "卡通动漫"
        }
        type_name = tid_to_name.get(str(tid), "")
        if not type_name:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        
        block_pattern = rf'<div class="modo_title top">.*?<h2><a href="[^"]*" target="#">{type_name}</a></h2>.*?<ul class="lycms_list_tab_img" id="resize_list">(.*?)</ul>'
        block_match = re.search(block_pattern, html, re.DOTALL)
        if block_match:
            ul_html = block_match.group(1)
            li_pattern = r'<li>(.*?)</li>'
            li_matches = re.findall(li_pattern, ul_html, re.DOTALL)
            for li_html in li_matches:
                url_match = re.search(r'href="([^"]+)"', li_html)
                if not url_match:
                    continue
                url = url_match.group(1)
                vod_id_match = re.search(r'/(\d+)\.html', url)
                if not vod_id_match:
                    continue
                vod_id = vod_id_match.group(1)
                
                title_match = re.search(r'<h2><a[^>]*>([^<]+)</a></h2>', li_html)
                if not title_match:
                    continue
                title = title_match.group(1).strip()
                
                # 图片 - 优先 data-original
                pic = ""
                pic_match = re.search(r'data-original="([^"]+)"', li_html)
                if pic_match:
                    pic = pic_match.group(1)
                if not pic or '220x307.jpg' in pic:
                    src_match = re.search(r'src="([^"]+)"', li_html)
                    if src_match and '220x307.jpg' not in src_match.group(1):
                        pic = src_match.group(1)
                
                items.append({
                    "vod_id": str(vod_id),
                    "vod_name": title,
                    "vod_pic": urllib.parse.urljoin(home_url, pic) if pic else "",
                    "vod_remarks": "",
                })
        
        return {
            "list": items,
            "page": 1,
            "pagecount": 1,
            "limit": 20,
            "total": len(items),
        }
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        try:
            url = f"{self.host}/{vod_id}.html"
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text

            title = ""
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                title = title_match.group(1)
                title = re.sub(r'\s*-\s*水穴潮喷.*', '', title)
                title = re.sub(r'\s*-\s*在线播放.*', '', title)
                title = re.sub(r'\s*-\s*视频播放.*', '', title)

            play_url = self._parse_play_url(html)
            if not play_url:
                alt_match = re.search(r'"url"\s*:\s*"([^"]+)"', html)
                if alt_match:
                    play_url = alt_match.group(1).replace('\\/', '/')
            if not play_url:
                return {"list": []}

            play_from = "ckplayer"
            from_match = re.search(r'"from"\s*:\s*"([^"]+)"', html)
            if from_match:
                play_from = from_match.group(1)

            vod = {
                "vod_id": str(vod_id),
                "vod_name": title or "视频",
                "vod_pic": "",
                "vod_remarks": "",
                "vod_content": "",
                "vod_play_from": play_from,
                "vod_play_url": f"第1集${play_url}",
            }
            return {"list": [vod]}
        except Exception as e:
            return {"list": []}
    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        page = str(pg or "1")
        search_url = f"{self.host}/s/index.html?wd={urllib.parse.quote(key)}"
        if page != "1":
            search_url += f"&page={page}"

        resp = self.fetch(search_url, headers=self.headers, timeout=15)
        if not resp or resp.status_code != 200:
            return {"list": [], "page": int(page)}

        html = resp.text
        items = []
        pattern = r'<ul class="lycms_list_tab_img" id="resize_list">(.*?)</ul>'
        ul_match = re.search(pattern, html, re.DOTALL)
        if ul_match:
            items = self._parse_list_items(ul_match.group(1), search_url)

        return {"list": items, "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        play_url = str(id).strip()
        if play_url.startswith("http") and (".m3u8" in play_url or ".mp4" in play_url):
            if ".m3u8" in play_url:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(play_url),
                    "header": self.headers,
                }
            return {
                "parse": 0,
                "url": play_url,
                "header": {"User-Agent": self.headers["User-Agent"]},
            }

        return {
            "parse": 1,
            "url": play_url,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
            },
        }

    def _m3u8_proxy_url(self, url):
        if not url:
            return ""
        if url.startswith("http://127.0.0.1:9978/proxy"):
            return url
        encoded = urllib.parse.quote(str(url), safe=":/?&=#%")
        # TVBox/FongMi 代理格式
        proxy_base = self.getProxyUrl()
        if "?" in proxy_base:
            return proxy_base + "&url=" + encoded
        else:
            return proxy_base + "?url=" + encoded
    def _clean_m3u8_single(self, lines, source_url):
        result = []
        pending_extinf = []
        removed = 0
        kept = 0

        # 从 source_url 提取正片目录前缀
        # 例如：https://2609.sysl2026.com/20260826/DbPXley4/index.m3u8
        # 提取：/20260826/DbPXley4/
        import posixpath
        parsed = urllib.parse.urlparse(source_url)
        path = parsed.path
        # 去掉文件名，保留目录
        dir_path = posixpath.dirname(path)
        if not dir_path.endswith('/'):
            dir_path += '/'

        def is_valid_segment(url):
            # 只保留路径以正片目录开头的分片
            parsed_url = urllib.parse.urlparse(url)
            return parsed_url.path.startswith(dir_path)

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
                        is_valid = is_valid_segment(media_url)
                        
                        if is_valid:
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
                out.append(self._m3u8_proxy_url(child_url) if ".m3u8" in child_url.lower() else child_url)
        return "\n".join(out) + "\n"

    def _clean_m3u8(self, text, source_url):
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        is_multi = any(line.startswith("#EXT-X-STREAM-INF") for line in lines)
        if is_multi:
            return self._clean_m3u8_multi(lines, source_url)
        else:
            return self._clean_m3u8_single(lines, source_url)

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

    def localProxy(self, param):
        """
        m3u8本地代理 - 广告分片过滤
        """
        try:
            target = ""
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            elif isinstance(param, str):
                target = param
            
            # 如果参数是 URL 编码的字符串，先解码
            if target and target.startswith("url="):
                target = target[4:]
            if target and "url=" in target:
                # 从 query string 中提取 url 参数
                import urllib.parse as up
                parsed = up.urlparse(target)
                qs = up.parse_qs(parsed.query)
                if "url" in qs:
                    target = qs["url"][0]
                elif "do" in qs and "url" in qs:
                    target = qs["url"][0]
            
            target = urllib.parse.unquote(str(target or ""))
            
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": self.host + "/",
                "Accept": "*/*",
            }
            
            resp = self.fetch(target, headers=headers, timeout=20)
            if not resp:
                return [502, "text/plain", b"fetch failed"]
            
            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")
            
            if not content:
                return [502, "text/plain", b"empty content"]
            
            # 检测是否为 m3u8
            if b"#EXTM3U" in content[:256]:
                text = content.decode("utf-8", errors="ignore")
                cleaned = self._clean_m3u8(text, target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            
            # 非 m3u8 直接返回
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
    def recommendContent(self, ids, pg):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = f"{self.host}/{vod_id}.html"
        resp = self.fetch(url, headers=self.headers, timeout=15)
        if not resp or resp.status_code != 200:
            return {"list": []}
        html = resp.text

        items = []
        # 从 "猜你喜欢" 区块提取
        # 查找包含 "猜你喜欢" 的区块
        pattern = r'<div[^>]*class="main"[^>]*id="resize_list"[^>]*>.*?<ul[^>]*class="lycms_list_tab_img"[^>]*>(.*?)</ul>'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            items = self._parse_list_items(match.group(1), url)

        # 如果没找到，尝试其他模式
        if not items:
            pattern2 = r'猜你喜欢.*?<ul[^>]*class="lycms_list_tab_img"[^>]*>(.*?)</ul>'
            match2 = re.search(pattern2, html, re.DOTALL)
            if match2:
                items = self._parse_list_items(match2.group(1), url)

        # 去重，避免与当前视频重复
        if items:
            unique_items = []
            seen = set()
            for item in items:
                if item["vod_id"] != vod_id and item["vod_id"] not in seen:
                    seen.add(item["vod_id"])
                    unique_items.append(item)
            items = unique_items

        return {"list": items[:12]}
    def destroy(self):
        pass