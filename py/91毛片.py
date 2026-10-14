# coding: utf-8
import json
import re
import urllib.parse
import posixpath
from urllib.parse import urljoin, quote, unquote, urlparse
import time
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.host = "https://91mp.91mp222.lol"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36",
            "Referer": self.host + "/"
        }
        # 主分类
        self.classes = [
            {"type_id": "137", "type_name": "视频一区"},
            {"type_id": "138", "type_name": "视频二区"},
            {"type_id": "140", "type_name": "视频三区"},
            {"type_id": "148", "type_name": "视频四区"}
        ]
        # 子分类作为筛选选项
        self.filters = {
            "137": [
                {
                    "key": "sub_type",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "国产视频", "v": "124"},
                        {"n": "中文字幕", "v": "125"},
                        {"n": "日本有码", "v": "127"},
                        {"n": "伦理三级", "v": "141"},
                        {"n": "AV解说", "v": "142"},
                        {"n": "人妖系列", "v": "149"}
                    ]
                }
            ],
            "138": [
                {
                    "key": "sub_type",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "日本无码", "v": "128"},
                        {"n": "强奸乱伦", "v": "130"},
                        {"n": "制服诱惑", "v": "131"},
                        {"n": "网曝黑料", "v": "139"},
                        {"n": "SM调教", "v": "143"},
                        {"n": "网红头条", "v": "147"},
                        {"n": "韩国主播", "v": "150"}
                    ]
                }
            ],
            "140": [
                {
                    "key": "sub_type",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "欧美无码", "v": "129"},
                        {"n": "国产主播", "v": "132"},
                        {"n": "明星换脸", "v": "134"},
                        {"n": "女优明星", "v": "136"},
                        {"n": "萝莉少女", "v": "144"},
                        {"n": "女同性恋", "v": "146"}
                    ]
                }
            ],
            "148": [
                {
                    "key": "sub_type",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "国产传媒", "v": "126"},
                        {"n": "激情动漫", "v": "133"},
                        {"n": "抖阴视频", "v": "135"},
                        {"n": "极品媚黑", "v": "145"},
                        {"n": "VR视角", "v": "151"}
                    ]
                }
            ]
        }

    def getName(self):
        return "91毛片"

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

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            res = self.fetch(self.host, headers=self.headers)
            if res and hasattr(res, 'text'):
                items = self._parse_home_list(res.text)
                return {"list": items}
        except Exception as e:
            self.log({"action": "homeVideoContent_error", "error": str(e)})
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        extend_dict = self._parse_extend(extend)
        sub_type = extend_dict.get("sub_type", "")
        target_tid = sub_type if sub_type else tid
        url = f"{self.host}/index.php/vod/type/id/{target_tid}.html"
        if int(page) > 1:
            url += f"?page={page}"
        try:
            res = self.fetch(url, headers=self.headers)
            if res and hasattr(res, 'text'):
                items = self._parse_category_list(res.text)
                total_pages = self._parse_total_pages(res.text)
                return {
                    "list": items,
                    "page": int(page),
                    "pagecount": total_pages if total_pages > 0 else 99,
                    "limit": 20,
                    "total": 999
                }
        except Exception as e:
            self.log({"action": "categoryContent_error", "tid": tid, "target_tid": target_tid, "error": str(e)})
        return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        vod_id = ids[0] if ids else ""
        if not vod_id:
            return {"list": []}
        url = f"{self.host}/index.php/vod/detail/id/{vod_id}.html"
        try:
            res = self.fetch(url, headers=self.headers)
            if res and hasattr(res, 'text'):
                vod_info = self._parse_detail(res.text, vod_id)
                if vod_info:
                    return {"list": [vod_info]}
        except Exception as e:
            self.log({"action": "detailContent_error", "vod_id": vod_id, "error": str(e)})
        return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        url = f"{self.host}/index.php/vod/search.html"
        data = {"wd": key}
        try:
            res = self.post(url, data=data, headers=self.headers)
            if res and hasattr(res, 'text'):
                items = self._parse_search_list(res.text)
                return {"list": items, "page": int(pg)}
        except Exception as e:
            self.log({"action": "searchContent_error", "key": key, "error": str(e)})
        return {"list": [], "page": 1}

    def recommendContent(self, ids, pg):
        """
        相关推荐接口 - 根据当前视频ID获取同类推荐
        ids: 视频ID列表，如 ['video_123'] 或 ['rp_xxx']
        pg: 页码（从1开始）
        返回: {'list': [vod1, vod2, ...]}
        """
        try:
            # 提取视频ID
            vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
            # 移除可能的前缀
            raw_id = vid.replace('rp_', '').replace('video:', '').replace('vod_', '').strip()
            if not raw_id:
                return {'list': []}

            page = max(1, int(pg or 1))

            # 获取当前视频的详情，提取分类信息
            detail_url = f"{self.host}/index.php/vod/detail/id/{raw_id}.html"
            res = self.fetch(detail_url, headers=self.headers)
            if not res or not hasattr(res, 'text'):
                return {'list': []}
            
            html = res.text
            # 提取分类
            category_match = re.search(r'分类\s*</span>\s*<span[^>]*>([^<]+)</span>', html)
            category = category_match.group(1).strip() if category_match else ""

            # 获取推荐列表（从详情页的"相关推荐"区域解析）
            items = self._parse_recommend_list(html)
            
            # 如果没有相关推荐，按分类搜索兜底
            if not items and category:
                # 使用分类关键词搜索
                search_url = f"{self.host}/index.php/vod/search.html"
                data = {"wd": category}
                try:
                    search_res = self.post(search_url, data=data, headers=self.headers)
                    if search_res and hasattr(search_res, 'text'):
                        items = self._parse_search_list(search_res.text)
                except:
                    pass

            # 去重：过滤掉当前视频
            result = []
            seen = set()
            for item in items:
                if item.get('vod_id') and item.get('vod_id') != raw_id and item.get('vod_id') != vid:
                    if item.get('vod_id') not in seen:
                        seen.add(item.get('vod_id'))
                        result.append(item)
                        if len(result) >= 18:
                            break

            return {'list': result}

        except Exception as e:
            self.log({"action": "recommendContent_error", "error": str(e)})
            return {'list': []}
    def playerContent(self, flag, id, vipFlags):
        if id.startswith("http") and (id.endswith(".m3u8") or id.endswith(".mp4")):
            return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": self.headers}
        if id.startswith("http"):
            try:
                res = self.fetch(id, headers=self.headers)
                if res and hasattr(res, 'text'):
                    play_url = self._extract_play_url(res.text)
                    if play_url:
                        return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": self.headers}
            except Exception as e:
                self.log({"action": "playerContent_error", "id": id, "error": str(e)})
        return {"parse": 1, "url": id, "header": self.headers}

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            res = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=15)
            if not res:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(res, "content", b"") or b""
            if not content and hasattr(res, "text") and res.text:
                content = res.text.encode("utf-8", errors="ignore")

            if not content:
                return [502, "text/plain", b"empty content"]

            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]

    def _clean_m3u8(self, text, source_url):
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urllib.parse.urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

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

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urllib.parse.urljoin(source_url, line)
                media_parsed = urllib.parse.urlparse(media_url)
                is_ad = not media_parsed.path.startswith(main_dir)
                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urllib.parse.urljoin(source_url, line))
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

    # ============= 内部解析方法 =============
    
    def _parse_home_list(self, html):
        items = []
        pattern = r'<article class="mp-card">.*?<a class="mp-card-link" href="([^"]+)".*?<img src="([^"]+)" alt="([^"]+)".*?<span class="mp-card-note">([^<]+)</span>.*?</article>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            link, img, title, note = match
            vod_id = self._extract_vod_id(link)
            if vod_id:
                items.append({
                    "vod_id": vod_id,
                    "vod_name": title.strip(),
                    "vod_pic": self._fix_url(img),
                    "vod_remarks": note.strip()
                })
        return items

    def _parse_category_list(self, html):
        items = []
        pattern = r'<article class="mp-card">.*?<a class="mp-card-link" href="([^"]+)".*?<img src="([^"]+)" alt="([^"]+)".*?<span class="mp-card-note">([^<]+)</span>.*?</article>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            link, img, title, note = match
            vod_id = self._extract_vod_id(link)
            if vod_id:
                items.append({
                    "vod_id": vod_id,
                    "vod_name": title.strip(),
                    "vod_pic": self._fix_url(img),
                    "vod_remarks": note.strip()
                })
        return items

    def _parse_recommend_list(self, html):
        """解析相关推荐列表"""
        items = []
        # 查找"相关推荐"区域
        pos = html.find('相关推荐')
        if pos == -1:
            return items
        
        # 查找 mp-grid 容器
        grid_start = html.find('<div class="mp-grid">', pos)
        if grid_start == -1:
            return items
        
        grid_end = html.find('</div>', grid_start + 10)
        if grid_end == -1:
            return items
        
        grid_html = html[grid_start:grid_end]
        
        # 解析卡片
        pattern = r'<article class="mp-card">.*?<a class="mp-card-link" href="([^"]+)".*?<img src="([^"]+)" alt="([^"]+)".*?<span class="mp-card-note">([^<]+)</span>.*?</article>'
        matches = re.findall(pattern, grid_html, re.DOTALL)
        for match in matches:
            link, img, title, note = match
            vod_id = self._extract_vod_id(link)
            if vod_id:
                items.append({
                    "vod_id": vod_id,
                    "vod_name": title.strip(),
                    "vod_pic": self._fix_url(img),
                    "vod_remarks": note.strip()
                })
        return items
    def _parse_detail(self, html, vod_id):
        title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        title = title_match.group(1).strip() if title_match else "视频"
        category_match = re.search(r'分类\s*</span>\s*<span[^>]*>([^<]+)</span>', html)
        category = category_match.group(1).strip() if category_match else ""
        region_match = re.search(r'地区\s*</span>\s*<span[^>]*>([^<]+)</span>', html)
        region = region_match.group(1).strip() if region_match else ""
        year_match = re.search(r'年份\s*</span>\s*<span[^>]*>([^<]+)</span>', html)
        year = year_match.group(1).strip() if year_match else ""
        status_match = re.search(r'状态\s*</span>\s*<span[^>]*>([^<]+)</span>', html)
        status = status_match.group(1).strip() if status_match else ""
        pic_match = re.search(r'<img[^>]+src="([^"]+)"[^>]+alt="[^"]*"[^>]*>', html)
        pic = pic_match.group(1).strip() if pic_match else ""
        play_from, play_url = self._parse_play_info(html)
        content_match = re.search(r'<div[^>]*class="mp-desc"[^>]*>(.*?)</div>', html, re.DOTALL)
        content = content_match.group(1).strip() if content_match else ""
        if content:
            content = re.sub(r'<[^>]+>', '', content).strip()
        vod = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": self._fix_url(pic),
            "vod_remarks": status,
            "vod_actor": "",
            "vod_director": "",
            "vod_content": content,
            "vod_play_from": play_from,
            "vod_play_url": play_url
        }
        return vod

    def _parse_play_info(self, html):
        play_from = ""
        play_url = ""
        from_pattern = r'<div[^>]*class="[^"]*play-source[^"]*"[^>]*>.*?<span[^>]*>([^<]+)</span>'
        from_match = re.search(from_pattern, html, re.DOTALL)
        if from_match:
            play_from = from_match.group(1).strip()
        else:
            if "播放线路" in html:
                line_match = re.search(r'播放线路\s*</span>\s*<span[^>]*>([^<]+)</span>', html)
                if line_match:
                    play_from = line_match.group(1).strip()
                else:
                    play_from = "播放"
            else:
                play_from = "播放"
        episode_pattern = r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
        episodes = re.findall(episode_pattern, html)
        episode_list = []
        for ep_link, ep_name in episodes:
            if not ep_name.strip().isdigit() and "集" not in ep_name and "播放" not in ep_name and not ep_name.strip().startswith("http"):
                continue
            full_link = self._fix_url(ep_link)
            if "vod/play" in full_link or "play" in full_link:
                episode_list.append(f"{ep_name.strip()}${full_link}")
        if episode_list:
            play_url = "#".join(episode_list)
        else:
            play_url = self._extract_play_url(html)
            if play_url:
                play_url = f"播放${play_url}"
        return play_from, play_url

    def _extract_play_url(self, html):
        url_pattern = r'https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*'
        matches = re.findall(url_pattern, html)
        if matches:
            return matches[0]
        iframe_pattern = r'<iframe[^>]+src="([^"]+)"'
        iframe_match = re.search(iframe_pattern, html)
        if iframe_match:
            return iframe_match.group(1).strip()
        video_pattern = r'<video[^>]+src="([^"]+)"'
        video_match = re.search(video_pattern, html)
        if video_match:
            return video_match.group(1).strip()
        js_pattern = r'player\.setUrl\(["\']([^"\']+)["\']\)'
        js_match = re.search(js_pattern, html)
        if js_match:
            return js_match.group(1).strip()
        return ""

    def _parse_search_list(self, html):
        items = []
        pattern = r'<article class="mp-card">.*?<a class="mp-card-link" href="([^"]+)".*?<img src="([^"]+)" alt="([^"]+)".*?<span class="mp-card-note">([^<]+)</span>.*?</article>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            link, img, title, note = match
            vod_id = self._extract_vod_id(link)
            if vod_id:
                items.append({
                    "vod_id": vod_id,
                    "vod_name": title.strip(),
                    "vod_pic": self._fix_url(img),
                    "vod_remarks": note.strip()
                })
        return items

    def _parse_total_pages(self, html):
        pattern = r'<ul class="pagination">.*?</ul>'
        pagination = re.search(pattern, html, re.DOTALL)
        if pagination:
            page_numbers = re.findall(r'<li[^>]*><a[^>]*>(\d+)</a></li>', pagination.group(0))
            if page_numbers:
                return int(max(page_numbers, key=int))
            total_pages_match = re.search(r'共\s*(\d+)\s*页', html)
            if total_pages_match:
                return int(total_pages_match.group(1))
        return 0

    def _extract_vod_id(self, link):
        match = re.search(r'/vod/detail/id/(\d+)\.html', link)
        if match:
            return match.group(1)
        return None

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if not url.startswith("http"):
            return urljoin(self.host, url)
        return url