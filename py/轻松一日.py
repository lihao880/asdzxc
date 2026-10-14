# coding: utf-8
import re
import json
import urllib.parse
import posixpath
from urllib.parse import quote, urljoin

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

class Spider:
    """轻松一日 - TVBox爬虫"""
    
    def __init__(self):
        self.host = "https://qswebdrive.xyz"
        self.site_name = "轻松一日"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 23113RKC6G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "43", "type_name": "国产视频"},
            {"type_id": "35", "type_name": "字幕剧情"},
            {"type_id": "39", "type_name": "欧美视频"},
            {"type_id": "33", "type_name": "日本无码"},
            {"type_id": "37", "type_name": "黑人视频"},
            {"type_id": "53", "type_name": "传媒拍摄"},
            {"type_id": "29", "type_name": "人妖大战"},
            {"type_id": "47", "type_name": "萝莉少女"},
            {"type_id": "23", "type_name": "女同性爱"},
            {"type_id": "31", "type_name": "捆绑调教"},
            {"type_id": "55", "type_name": "三级伦理"},
            {"type_id": "25", "type_name": "重口猎奇"},
            {"type_id": "59", "type_name": "卡通视频"},
        ]
        self.filters = {
            "43": [], "35": [], "39": [], "33": [], "37": [],
            "53": [], "29": [], "47": [], "23": [], "31": [],
            "55": [], "25": [], "59": [],
        }

    def getName(self):
        return self.site_name

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, timeout=20):
        if HAS_REQUESTS:
            h = headers or self.headers
            resp = requests.get(url, headers=h, timeout=timeout)
            return resp
        import urllib.request
        req = urllib.request.Request(url, headers=headers or self.headers)
        return urllib.request.urlopen(req, timeout=timeout)

    def post(self, url, data=None, headers=None, timeout=20):
        if HAS_REQUESTS:
            h = headers or self.headers
            resp = requests.post(url, data=data, headers=h, timeout=timeout)
            return resp
        import urllib.request
        import urllib.parse
        h = headers or self.headers
        encoded_data = urllib.parse.urlencode(data).encode('utf-8')
        req = urllib.request.Request(url, data=encoded_data, headers=h)
        return urllib.request.urlopen(req, timeout=timeout)

    def log(self, info):
        print(json.dumps(info, ensure_ascii=False))

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            url = self.host + "/"
            resp = self.fetch(url, headers=self.headers)
            html = resp.text if HAS_REQUESTS else resp.read().decode('utf-8')
            
            pattern = r'<article[^>]*class="[^"]*persona-card[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<span[^>]*class="[^"]*label[^"]*ol[^"]*"[^>]*>([^<]+)</span>'
            matches = re.findall(pattern, html, re.DOTALL)
            
            video_list = []
            for match in matches[:24]:
                href, pic, name = match
                if not href.startswith("http"):
                    href = self.host + href
                if not pic.startswith("http"):
                    pic = self.host + pic
                video_list.append({
                    "vod_id": href,
                    "vod_name": name.strip(),
                    "vod_pic": pic,
                    "vod_remarks": "首页推荐"
                })
            return {"list": video_list}
        except Exception as e:
            self.log({"action": "homeVideoContent_error", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        try:
            page = pg or 1
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
            resp = self.fetch(url, headers=self.headers)
            html = resp.text if HAS_REQUESTS else resp.read().decode('utf-8')
            
            pattern = r'<article[^>]*class="[^"]*persona-card[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<span[^>]*class="[^"]*label[^"]*ol[^"]*"[^>]*>([^<]+)</span>'
            matches = re.findall(pattern, html, re.DOTALL)
            
            video_list = []
            for match in matches:
                href, pic, name = match
                if not href.startswith("http"):
                    href = self.host + href
                if not pic.startswith("http"):
                    pic = self.host + pic
                video_list.append({
                    "vod_id": href,
                    "vod_name": name.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
            
            page_pattern = r'<a[^>]*href="[^"]*/page/(\d+)\.html"[^>]*>.*?</a>'
            page_matches = re.findall(page_pattern, html)
            pagecount = 10
            if page_matches:
                pagecount = max([int(p) for p in page_matches]) + 1
            
            return {
                "list": video_list,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 24,
                "total": pagecount * 24
            }
        except Exception as e:
            self.log({"action": "categoryContent_error", "error": str(e)})
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if ids else ""
            if not vod_id:
                return {"list": []}
            
            if vod_id.startswith("http"):
                url = vod_id
            else:
                url = f"{self.host}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
            
            resp = self.fetch(url, headers=self.headers)
            html = resp.text if HAS_REQUESTS else resp.read().decode('utf-8')
            
            # 提取标题 - 简单直接的方式
            title = "未知标题"
            
            # 查找"正在播放"的位置
            idx = html.find("正在播放")
            if idx != -1:
                # 提取"正在播放"后面的内容
                sub = html[idx:idx + 600]
                # 查找p标签
                p_start = sub.find("<p")
                if p_start != -1:
                    p_end = sub.find("</p>", p_start)
                    if p_end != -1:
                        content_start = sub.find(">", p_start) + 1
                        if content_start < p_end:
                            title = sub[content_start:p_end].strip()
                            # 去除可能的HTML标签
                            title = re.sub(r'<[^>]+>', '', title).strip()
            
            # 如果没找到，用class匹配
            if title == "未知标题":
                m = re.search(r'<p[^>]*class="[^"]*text-fv-neutral-500[^"]*"[^>]*>([^<]+)</p>', html)
                if m:
                    title = m.group(1).strip()
            
            # 如果还没找到，用通用p标签匹配
            if title == "未知标题":
                ps = re.findall(r'<p[^>]*>([^<]+)</p>', html)
                for p in ps:
                    p = p.strip()
                    if p and len(p) > 5 and p not in ["", "共0个结果", "视频分类"]:
                        if not p.startswith("共") and not p.startswith("分类"):
                            title = p
                            break
            
            title = re.sub(r'\s+', ' ', title).strip()
            
            # 提取封面图
            pic = ""
            m = re.search(r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*w-full[^"]*object-cover[^"]*"[^>]*>', html)
            if not m:
                m = re.search(r'<article[^>]*class="[^"]*persona-card[^"]*"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>', html, re.DOTALL)
            if not m:
                m = re.search(r'<img[^>]*src="([^"]+)"[^>]*>', html)
            if m:
                pic = m.group(1)
                if pic.startswith("/"):
                    pic = self.host + pic
            
            # 提取播放地址
            play_url = ""
            m = re.search(r'<iframe[^>]*src="([^"]+)"[^>]*>', html)
            if m:
                play_url = m.group(1)
            
            # 构建结果
            vod = {
                "vod_id": url,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_content": title,
                "vod_play_from": "播放",
                "vod_play_url": f"播放${url}" if play_url else ""
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent_error", "error": str(e)})
            return {"list": []}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            page = int(pg) if pg else 1
            url = self.host + "/index.php/vod/search.html"
            data = {"wd": key, "page": page}
            resp = self.post(url, data=data, headers=self.headers)
            html = resp.text if HAS_REQUESTS else resp.read().decode('utf-8')
            
            pattern = r'<article[^>]*class="[^"]*persona-card[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<span[^>]*class="[^"]*label[^"]*ol[^"]*"[^>]*>([^<]+)</span>'
            matches = re.findall(pattern, html, re.DOTALL)
            
            video_list = []
            for match in matches:
                href, pic, name = match
                if not href.startswith("http"):
                    href = self.host + href
                if not pic.startswith("http"):
                    pic = self.host + pic
                video_list.append({
                    "vod_id": href,
                    "vod_name": name.strip(),
                    "vod_pic": pic,
                    "vod_remarks": f"搜索: {key}"
                })
            
            return {"list": video_list, "page": page}
        except Exception as e:
            self.log({"action": "searchContent_error", "error": str(e)})
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        try:
            if id.startswith("http") and (".m3u8" in id or ".mp4" in id):
                if "aojiexi.com" in id:
                    try:
                        resp = self.fetch(id, headers=self.headers, timeout=15)
                        html = resp.text if HAS_REQUESTS else resp.read().decode('utf-8')
                        real_matches = re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html, re.IGNORECASE)
                        if real_matches:
                            for m in real_matches:
                                if "aojiexi.com" not in m:
                                    return {"parse": 0, "url": self._m3u8_proxy_url(m), "header": self.headers}
                        js_matches = re.findall(r'["\'](https?://[^\s"\']+\.m3u8[^\s"\']*)["\']', html, re.IGNORECASE)
                        if js_matches:
                            for m in js_matches:
                                if "aojiexi.com" not in m:
                                    return {"parse": 0, "url": self._m3u8_proxy_url(m), "header": self.headers}
                    except Exception as e:
                        self.log({"action": "playerContent_aojiexi_fetch_error", "error": str(e)})
                return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": self.headers}
            
            full_url = id
            if not id.startswith("http"):
                if id.startswith("/"):
                    full_url = self.host + id
                else:
                    full_url = self.host + "/" + id
            
            real_m3u8 = None
            
            try:
                resp = self.fetch(full_url, headers=self.headers, timeout=15)
                html = resp.text if HAS_REQUESTS else resp.read().decode('utf-8')
                
                video_pattern = r'https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*'
                matches = re.findall(video_pattern, html, re.IGNORECASE)
                for m in matches:
                    if ".m3u8" in m and "aojiexi.com" not in m:
                        real_m3u8 = m
                        break
                    if not real_m3u8 and ".mp4" in m and "aojiexi.com" not in m:
                        real_m3u8 = m
                
                if not real_m3u8:
                    iframe_pattern = r'<iframe[^>]*src="([^"]+)"[^>]*>'
                    iframe_matches = re.findall(iframe_pattern, html, re.IGNORECASE)
                    for iframe_src in iframe_matches:
                        url_param_match = re.search(r'[?&]url=([^&\'"]+)', iframe_src)
                        if url_param_match:
                            inner_url = urllib.parse.unquote(url_param_match.group(1))
                            if ".m3u8" in inner_url or ".mp4" in inner_url:
                                real_m3u8 = inner_url
                                break
                            if "aojiexi.com" in iframe_src or "parse" in iframe_src:
                                try:
                                    mid_resp = self.fetch(iframe_src, headers=self.headers, timeout=15)
                                    mid_html = mid_resp.text if HAS_REQUESTS else mid_resp.read().decode('utf-8')
                                    mid_matches = re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', mid_html, re.IGNORECASE)
                                    for mm in mid_matches:
                                        if "aojiexi.com" not in mm:
                                            real_m3u8 = mm
                                            break
                                    if not real_m3u8:
                                        js_matches = re.findall(r'["\'](https?://[^\s"\']+\.m3u8[^\s"\']*)["\']', mid_html, re.IGNORECASE)
                                        for jm in js_matches:
                                            if "aojiexi.com" not in jm:
                                                real_m3u8 = jm
                                                break
                                except Exception:
                                    pass
                        
                        if not real_m3u8 and (".m3u8" in iframe_src or ".mp4" in iframe_src):
                            real_m3u8 = iframe_src
                            break
                
                if not real_m3u8:
                    js_pattern = r'(?:url|src|video|play(?:er)?_?url)\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']'
                    js_matches = re.findall(js_pattern, html, re.IGNORECASE)
                    for jm in js_matches:
                        if "aojiexi.com" not in jm:
                            real_m3u8 = jm
                            break
                
            except Exception as e:
                self.log({"action": "playerContent_fetch_error", "error": str(e)})
            
            if real_m3u8:
                return {"parse": 0, "url": self._m3u8_proxy_url(real_m3u8), "header": self.headers}
            
            return {"parse": 1, "url": full_url, "header": self.headers}
        except Exception as e:
            self.log({"action": "playerContent_error", "error": str(e)})
            return {"parse": 1, "url": id, "header": self.headers}

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

    def localProxy(self, params):
        try:
            if isinstance(params, dict):
                target = params.get("url", "") or params.get("source", "")
            else:
                target = str(params or "")

            if target.startswith("url="):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url", {}]

            try:
                resp = self.fetch(target, headers=self.headers, timeout=20)
                if resp is None:
                    return [502, "text/plain", b"fetch returned None", {}]
                content = resp.content if HAS_REQUESTS else resp.read()
            except Exception as e:
                self.log({"action": "localProxy_fetch_error", "error": str(e)})
                return [502, "text/plain", ("fetch failed: " + str(e)).encode(), {}]

            if not content:
                return [502, "text/plain", b"empty content", {}]

            text = content.decode('utf-8', errors='ignore')
            
            if "#EXTM3U" not in text:
                return [200, "application/vnd.apple.mpegurl", content, {"Cache-Control": "no-store"}]

            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode('utf-8'), {"Cache-Control": "no-store"}]

        except Exception as e:
            error_msg = ("localProxy error: " + str(e)).encode('utf-8', errors='ignore')
            return [500, "text/plain", error_msg, {}]