# coding: utf-8
"""
站点名称: 片场大师
主域名: https://fjgjxf.pcds5.ink
备用域名: 无 (发布页: https://lry.xxkk7.com/263/)
内容类型: 成人影视
m3u8结构: KEY URI目录锚点优先，广告分片在前6个，按五层管线过滤
最后验证: 2026-08-31
来源: AI自动分析
"""
import re
import json
import base64
from urllib.parse import urljoin, urlparse, quote, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.host = "https://fjgjxf.pcds5.ink"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "20", "type_name": "美女写真"},
            {"type_id": "21", "type_name": "国产精品"},
            {"type_id": "22", "type_name": "无码专区"},
            {"type_id": "23", "type_name": "中文字幕"},
            {"type_id": "24", "type_name": "强奸乱伦"},
            {"type_id": "25", "type_name": "人妻熟女"},
            {"type_id": "26", "type_name": "亚洲情色"},
            {"type_id": "27", "type_name": "制服丝袜"},
            {"type_id": "28", "type_name": "SM捆绑"},
            {"type_id": "29", "type_name": "自淫系列"},
            {"type_id": "30", "type_name": "三级伦理"}
        ]
        self.filters = {}
        for cls in self.classes:
            self.filters[cls["type_id"]] = []

    def getName(self):
        return "片场大师"

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
        html = self.fetch(url, headers=self.headers, timeout=10).text
        items = self._parse_video_list(html, is_home=True)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        if page == "1":
            url = f"{self.host}/vodtype/{tid}.html"
        else:
            url = f"{self.host}/vodtype/{tid}-{page}.html"
        html = self.fetch(url, headers=self.headers, timeout=10).text
        items = self._parse_video_list(html, is_home=False)
        pagecount = self._parse_pagecount(html)
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount or 99,
            "limit": 20,
            "total": pagecount * 20 if pagecount else 999
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        if vod_id.startswith("/"):
            vod_id = vod_id.lstrip("/").split(".")[0]
        
        detail_url = f"{self.host}/{vod_id}.html"
        html = self.fetch(detail_url, headers=self.headers, timeout=10).text
        
        if not html or len(html) < 100:
            detail_url = f"{self.host}/vod/detail/id/{vod_id}.html"
            html = self.fetch(detail_url, headers=self.headers, timeout=10).text
        
        return self._parse_detail(html, vod_id)

    def _parse_detail(self, html, vod_id):
        """解析详情页"""
        if not html or len(html) < 100:
            return {"list": [{
                "vod_id": vod_id,
                "vod_name": f"视频{vod_id}",
                "vod_pic": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放$play://{vod_id}"
            }]}

        # 提取标题
        title = ""
        title_match = re.search(r'<div class="head">.*?<h3>([^<]+)</h3>', html, re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
        if not title:
            title_match = re.search(r'<title>正在播放:([^<]+)-片场大师</title>', html)
            if title_match:
                title = title_match.group(1).strip()
        if not title:
            title = f"视频{vod_id}"

        # 提取类型
        type_name = ""
        type_match = re.search(r'类型：</span><a href="[^"]+">([^<]+)</a>', html)
        if type_match:
            type_name = type_match.group(1).strip()

        # 提取时间
        time_str = ""
        time_match = re.search(r'时间：</span>([^<]+)', html)
        if time_match:
            time_str = time_match.group(1).strip()

        # 提取封面
        pic = ""
        pic_match = re.search(r'<img[^>]*class="[^"]*imgPlay[^"]*"[^>]*src="([^"]+)"', html)
        if pic_match:
            pic = pic_match.group(1)
        if not pic:
            pic_match = re.search(r'data-original="([^"]+)"', html)
            if pic_match:
                pic = pic_match.group(1)
        if pic and not pic.startswith("http"):
            pic = urljoin(self.host, pic)

        # 提取播放地址
        play_url = self._extract_m3u8(html)

        if play_url:
            if ".m3u8" in play_url.lower():
                play_url = self._m3u8_proxy_url(play_url)
            return {
                "list": [{
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": time_str,
                    "vod_actor": type_name,
                    "vod_content": type_name,
                    "vod_play_from": "播放",
                    "vod_play_url": f"播放${play_url}"
                }]
            }

        return {
            "list": [{
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": time_str,
                "vod_actor": type_name,
                "vod_content": type_name,
                "vod_play_from": "播放",
                "vod_play_url": f"播放$play://{vod_id}"
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        encoded_key = quote(key)
        if pg == "1":
            url = f"{self.host}/s/index.html?wd={encoded_key}"
        else:
            url = f"{self.host}/s/{encoded_key}/page/{pg}.html"
        html = self.fetch(url, headers=self.headers, timeout=10).text
        items = self._parse_video_list(html, is_home=False)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        
        # 处理 play:// 协议
        if id.startswith("play://"):
            vod_id = id.replace("play://", "")
            detail_url = f"{self.host}/{vod_id}.html"
            html = self.fetch(detail_url, headers=self.headers, timeout=10).text
            play_url = self._extract_m3u8(html)
            if play_url and ".m3u8" in play_url:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(play_url),
                    "header": {"User-Agent": self.headers.get("User-Agent", "")}
                }
            return {"parse": 1, "url": detail_url, "header": self.headers}
        
        play_url = str(id).strip()
        if play_url.startswith("http") and ".m3u8" in play_url:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(play_url),
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        
        html = self.fetch(play_url, headers=self.headers, timeout=10).text
        real_url = self._extract_m3u8(html)
        if real_url:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(real_url),
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        return {"parse": 1, "url": play_url, "header": self.headers}

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass

    def _parse_video_list(self, html, is_home=False):
        items = []
        if is_home:
            pattern = r'<div class="col-md-3 col-sm-12 col-xs-12">.*?<a href="([^"]+)" title="([^"]+)">.*?<img src="([^"]+)"'
        else:
            pattern = r'<li class="col-md-3 col-sm-12 col-xs-12">.*?<a href="([^"]+)" title="([^"]+)">.*?<img src="([^"]+)"'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            link, title, pic = match
            if not link or not title:
                continue
            if is_home and not link.startswith("/1"):
                continue
            if "title" in title.lower() and len(title) < 20:
                continue
            vod_id = link.lstrip("/").split(".")[0] if link.startswith("/") else link
            items.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": ""
            })
        return items

    def _parse_pagecount(self, html):
        match = re.search(r'for\s*\(\s*var\s+i\s*=\s*0\s*;\s*i\s*<\s*(\d+)\s*;', html)
        if match:
            return int(match.group(1))
        match = re.search(r'尾页</a>.*?/(\d+)\.html', html)
        if match:
            return int(match.group(1))
        return None

    def _extract_m3u8(self, html):
        if not html:
            return None
        
        # 方法1: 从 rawUrl 变量提取
        match = re.search(r'(?:const|var|let)\s+rawUrl\s*=\s*[\'"]([^\'"]+)[\'"]', html)
        if match:
            raw = match.group(1)
            m3u8_match = re.search(r'https?://[^\s$#]+\.m3u8(?:\?[^\s#]*)?', raw)
            if m3u8_match:
                return m3u8_match.group(0)
        
        # 方法2: 从 player_data 提取 (参考七度妹妹)
        match = re.search(r'player_data\s*=\s*({[^}]+})', html)
        if match:
            try:
                import json
                data = json.loads(match.group(1))
                url = data.get("url", "")
                if url and url.startswith("http") and ".m3u8" in url:
                    return url
            except:
                pass
        
        # 方法3: 从 MacPlayer 提取
        match = re.search(r'MacPlayer\.PlayUrl\s*=\s*["\']([^"\']+)["\']', html)
        if match:
            return match.group(1)
        
        # 方法4: 直接搜索 m3u8
        match = re.search(r'https?://[^\s$#"\']+\.m3u8(?:\?[^\s#]*)?', html)
        if match:
            return match.group(0)
        
        # 方法5: 从 DPlayer video.url 提取
        match = re.search(r'video:\s*{\s*url:\s*[\'"]([^\'"]+)[\'"]', html, re.DOTALL)
        if match:
            url = match.group(1)
            if '.m3u8' in url:
                return url
        
        return None

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

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
        parsed = urlparse(source_url)
        default_dir = parsed.path[:parsed.path.rfind("/") + 1] if "/" in parsed.path else "/"
        if not default_dir.endswith("/"):
            default_dir += "/"
        
        # 从最后一个 #EXT-X-KEY 提取（正片 KEY 通常在广告段之后）
        last_key_uri = None
        for line in lines:
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                m = re.search(r'URI="([^"]+)"', line)
                if m:
                    last_key_uri = m.group(1)
        
        if last_key_uri:
            if not last_key_uri.startswith(("http://", "https://")):
                last_key_uri = urljoin(source_url, last_key_uri)
            key_path = urlparse(last_key_uri).path
            key_dir = key_path[:key_path.rfind("/") + 1] if "/" in key_path else "/"
            if key_dir and key_dir != "/":
                return key_dir
        
        return default_dir
    def _rewrite_m3u8_tag(self, line, source_url):
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

    def _clean_m3u8_multi(self, lines, source_url):
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

    def _filter_segments(self, lines, source_url, main_dir):
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
        return segments, removed, kept

    def _dedup_tags(self, segments, source_url):
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
        return out

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        if self._is_fake_image_stream(text, source_url):
            restored = text
            for ext in (".png", ".jpeg", ".jpg", ".webp"):
                restored = restored.replace(ext, ".ts")
            self.log("检测到图片流伪装，已还原扩展名 -> .ts，跳过广告过滤")
            return restored

        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            return self._clean_m3u8_multi(lines, source_url)

        main_dir = self._resolve_main_dir(lines, source_url)
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        # 全滤兜底：正片太少说明锚点可能选反
        if kept <= 3 and removed > 0:
            self.log(f"正片分片过少({kept}个)，判定锚点失效，回退为不过滤模式")
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")

        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"
    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                qs = {}
                for part in target.split("&"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        qs[k] = v
                if "url" in qs:
                    target = qs["url"]
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

            if b"#EXTM3U" in content[:256]:
                cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

            return [200, "application/octet-stream", content]
        except Exception as e:
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]