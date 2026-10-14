# coding: utf-8
import re
import json
import posixpath
import urllib.parse
from urllib.parse import quote, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.host = "https://m3n4o5p6.avgqsp70.sbs"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36",
            "Referer": self.host + "/"
        }
        # 视频分类
        self.video_classes = [
            {"type_id": "37", "type_name": "抖阴视频"},
            {"type_id": "39", "type_name": "网曝黑料"},
            {"type_id": "34", "type_name": "国产主播"},
            {"type_id": "36", "type_name": "明星换脸"},
            {"type_id": "28", "type_name": "国产传媒"},
            {"type_id": "26", "type_name": "国产视频"},
            {"type_id": "80", "type_name": "网红主播"},
            {"type_id": "121", "type_name": "OnlyFans"},
            {"type_id": "81", "type_name": "国产剧情"},
            {"type_id": "82", "type_name": "国产自拍"},
            {"type_id": "83", "type_name": "国产探花"},
            {"type_id": "84", "type_name": "网曝吃瓜"},
            {"type_id": "111", "type_name": "AV解说"},
            {"type_id": "112", "type_name": "三级伦理"},
            {"type_id": "117", "type_name": "AI换脸"},
            {"type_id": "120", "type_name": "泰国风情"},
            {"type_id": "41", "type_name": "AV解说"},
            {"type_id": "42", "type_name": "SM调教"},
            {"type_id": "43", "type_name": "萝莉少女"},
            {"type_id": "38", "type_name": "女优明星"},
            {"type_id": "33", "type_name": "制服诱惑"},
            {"type_id": "30", "type_name": "日本无码"},
            {"type_id": "29", "type_name": "日本有码"},
            {"type_id": "27", "type_name": "中文字幕"},
            {"type_id": "103", "type_name": "人妻熟女"},
            {"type_id": "104", "type_name": "日本无码"},
            {"type_id": "105", "type_name": "美乳巨乳"},
            {"type_id": "106", "type_name": "强制侵犯"},
            {"type_id": "107", "type_name": "制服诱惑"},
            {"type_id": "109", "type_name": "风俗泡泡浴"},
            {"type_id": "110", "type_name": "家庭乱伦"},
            {"type_id": "113", "type_name": "少女萝莉"},
            {"type_id": "114", "type_name": "SM调教"},
            {"type_id": "115", "type_name": "绝顶潮吹"},
            {"type_id": "116", "type_name": "淫欲痴女"},
            {"type_id": "118", "type_name": "欧美精品"},
            {"type_id": "119", "type_name": "日本动漫"},
            {"type_id": "48", "type_name": "韩国主播"},
            {"type_id": "49", "type_name": "VR视角"},
            {"type_id": "44", "type_name": "极品媚黑"},
            {"type_id": "45", "type_name": "女同性恋"},
            {"type_id": "47", "type_name": "人妖系列"},
            {"type_id": "40", "type_name": "伦理三级"},
            {"type_id": "31", "type_name": "欧美无码"},
            {"type_id": "32", "type_name": "强奸乱伦"},
            {"type_id": "35", "type_name": "激情动漫"},
        ]
        # 图区分类
        self.art_classes = [
            {"type_id": "art_86", "type_name": "📷 街拍偷拍"},
            {"type_id": "art_87", "type_name": "📷 丝袜美腿(失效)"},
            {"type_id": "art_89", "type_name": "📷 网友自拍(失效)"},
            {"type_id": "art_90", "type_name": "📷 卡通漫画(失效)"},
            {"type_id": "art_92", "type_name": "📷 唯美写真(失效)"},
            {"type_id": "art_95", "type_name": "📖 生活都市"},
            {"type_id": "art_96", "type_name": "📖 不偷恋情"},
            {"type_id": "art_97", "type_name": "📖 学生校园"},
            {"type_id": "art_99", "type_name": "📖 暴力虐待"},
            {"type_id": "art_100", "type_name": "📖 明星偶像"},
            {"type_id": "art_102", "type_name": "📖 科学幻想"},
        ]
        self.classes = self.video_classes + self.art_classes
        self.filters = {tid: [] for tid in [x["type_id"] for x in self.classes]}

    def getName(self):
        return "九色淫院"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self.categoryContent("82", "1", False, {})

    def _is_art_category(self, tid):
        return str(tid).startswith("art_")

    def _parse_video_list(self, html):
        items = []
        dl_pattern = re.compile(
            r'<dl>.*?<a[^>]+href="([^"]+)".*?<img[^>]+(?:src|data-original)="([^"]+)".*?<h3>([^<]+)</h3>.*?</dl>',
            re.DOTALL
        )
        for match in dl_pattern.findall(html):
            url, pic, title = match
            vid = re.search(r'/vod/detail/id/(\d+)\.html', url)
            if vid:
                items.append({
                    "vod_id": "video_" + vid.group(1),
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return items

    def _parse_art_list(self, html):
        items = []
        li_pattern = re.compile(
            r'<li>.*?<a[^>]+href="([^"]+)"[^>]*>.*?<span>\[([^\]]+)\]</span>.*?<h3>([^<]+)</h3>.*?</a>',
            re.DOTALL
        )
        for match in li_pattern.findall(html):
            url, date, title = match
            aid = re.search(r'/art/detail/id/(\d+)\.html', url)
            if aid:
                items.append({
                    "vod_id": "art_" + aid.group(1),
                    "vod_name": title.strip(),
                    "vod_pic": "",
                    "vod_remarks": date.strip()
                })
        return items

    def _parse_pagecount(self, html):
        match = re.search(r'<a[^>]+href="[^"]*/page/(\d+)\.html"[^>]*>尾页</a>', html)
        if match:
            return int(match.group(1))
        pages = re.findall(r'<a[^>]+href="[^"]*/page/(\d+)\.html"', html)
        if pages:
            return max(int(p) for p in pages)
        return 1

    def _extract(self, html, pattern, multiline=False):
        flags = re.DOTALL if multiline else 0
        match = re.search(pattern, html, flags)
        if match:
            if match.groups():
                return match.group(1).strip()
            return match.group(0).strip()
        return ""

    def _get_proxy_url(self):
        return "http://127.0.0.1:9978/proxy?do=py"

    def _m3u8_proxy_url(self, url):
        return self._get_proxy_url() + "&url=" + urllib.parse.quote(str(url or ""), safe="")

    def _clean_m3u8(self, text, source_url):
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
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urllib.parse.urlparse(source_url)
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

        # 二次清洗
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

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            page = int(pg or 1)
        except:
            page = 1
        extend = extend or {}
        tid = str(tid)

        if self._is_art_category(tid):
            art_id = tid.replace("art_", "")
            url = f"{self.host}/av/index.php/art/type/id/{art_id}/page/{page}.html"
            res = self.fetch(url, headers=self.headers)
            html = res.text if res else ""
            items = self._parse_art_list(html)
            pagecount = self._parse_pagecount(html)
            return {
                "list": items,
                "page": page,
                "pagecount": pagecount or page,
                "limit": 20,
                "total": pagecount * 20 if pagecount else len(items)
            }

        url = f"{self.host}/av/index.php/vod/type/id/{tid}/page/{page}.html"
        res = self.fetch(url, headers=self.headers)
        html = res.text if res else ""
        items = self._parse_video_list(html)
        pagecount = self._parse_pagecount(html)
        return {
            "list": items,
            "page": page,
            "pagecount": pagecount or page,
            "limit": 20,
            "total": pagecount * 20 if pagecount else len(items)
        }

    def detailContent(self, ids):
        if isinstance(ids, int):
            vid = str(ids)
        elif isinstance(ids, list) and ids:
            vid = str(ids[0])
        else:
            vid = str(ids) if ids else ""
        if not vid:
            return {"list": []}

        if vid.startswith("video_"):
            vid = vid.replace("video_", "")

        # 图区/小说/漫画详情
        if vid.startswith("art_"):
            art_id = vid.replace("art_", "")
            url = f"{self.host}/av/index.php/art/detail/id/{art_id}.html"
            res = self.fetch(url, headers=self.headers)
            html = res.text if res else ""

            title = self._extract(html, r'<h1>([^<]+)</h1>')
            remark = self._extract(html, r'<h2>[^<]*\s+([\d-]+)\s*</h2>')

            pics = re.findall(r'<img[^>]+src="([^"]+)"[^>]*>', html)
            pics = [p for p in pics if not p.startswith("/") and "gif" not in p.lower() and "logo" not in p.lower() and "banner" not in p.lower()]
            pics = [p for p in pics if "picpic.com" in p or "meitu" in p]

            content_html = ""
            content_match = re.search(r'<div[^>]*class="f14"[^>]*>(.*?)</div>', html, re.DOTALL)
            if content_match:
                content_html = content_match.group(1)
            else:
                content_match = re.search(r'<div[^>]*id="read_tpc"[^>]*>(.*?)</div>', html, re.DOTALL)
                if content_match:
                    content_html = content_match.group(1)
                else:
                    content_match = re.search(r'<div[^>]*class="m1938ing"[^>]*>(.*?)</div>', html, re.DOTALL)
                    if content_match:
                        content_html = content_match.group(1)

            text_content = ""
            if content_html:
                text_content = re.sub(r'<img[^>]*>', '', content_html)
                text_content = re.sub(r'<[^>]+>', '', text_content)
                text_content = re.sub(r'\n\s*\n', '\n', text_content)
                text_content = text_content.strip()

            if not text_content:
                body_text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
                body_text = re.sub(r'<style[^>]*>.*?</style>', '', body_text, flags=re.DOTALL)
                body_text = re.sub(r'<[^>]+>', ' ', body_text)
                paragraphs = re.findall(r'[^\n]{30,}', body_text)
                if len(paragraphs) > 5:
                    text_content = '\n'.join(p.strip() for p in paragraphs if len(p.strip()) > 20)
                    text_content = text_content[:5000]

            vod = {
                "vod_id": vid,
                "vod_name": title or "内容详情",
                "vod_pic": pics[0] if pics else "",
                "vod_remarks": remark or "",
                "vod_content": text_content[:500] + "..." if len(text_content) > 500 else text_content,
            }

            if pics:
                pics_str = "&&".join(pics)
                vod["vod_play_from"] = "图片浏览"
                vod["vod_play_url"] = "pics://" + pics_str
            elif text_content and len(text_content) > 50:
                vod["vod_play_from"] = "小说阅读"
                vod["vod_play_url"] = "novel://" + json.dumps({"title": title or "小说", "content": text_content}, ensure_ascii=False)
            else:
                vod["vod_play_from"] = ""
                vod["vod_play_url"] = ""

            return {"list": [vod]}

        # 视频详情
        url = f"{self.host}/av/index.php/vod/detail/id/{vid}.html"
        res = self.fetch(url, headers=self.headers)
        html = res.text if res else ""

        title = self._extract(html, r'<h1>([^<]+)</h1>')
        pic = self._extract(html, r'<img[^>]+src="([^"]+)"[^>]*alt="[^"]*"')
        if not pic:
            pic = self._extract(html, r'<img[^>]+data-original="([^"]+)"')
        remark = self._extract(html, r'<span[^>]*id="addtime"[^>]*>([^<]+)</span>')
        content = self._extract(html, r'<div[^>]*class="textlink"[^>]*>.*?</div>', multiline=True)

        play_match = re.search(r'<a[^>]+data-val="([^"]+)"[^>]*>.*?播放.*?</a>', html)
        play_url = play_match.group(1) if play_match else ""
        if not play_url:
            play_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*>.*?播放.*?</a>', html)
            play_url = play_match.group(1) if play_match else ""

        # 如果 play_url 是 m3u8，包装代理
        if play_url and ".m3u8" in play_url.lower():
            play_url = self._m3u8_proxy_url(play_url)

        vod = {
            "vod_id": vid,
            "vod_name": title or "视频详情",
            "vod_pic": pic or "",
            "vod_remarks": remark or "",
            "vod_content": content or "",
            "vod_play_from": "播放" if play_url else "",
            "vod_play_url": f"播放${play_url}" if play_url else ""
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            page = int(pg or 1)
        except:
            page = 1
        word = str(key or "").strip()
        if not word:
            return {"list": [], "page": page}

        url = f"{self.host}/av/index.php/vod/search.html?wd={quote(word)}"
        res = self.fetch(url, headers=self.headers)
        html = res.text if res else ""
        items = self._parse_video_list(html)

        art_url = f"{self.host}/av/index.php/art/search.html?wd={quote(word)}"
        art_res = self.fetch(art_url, headers=self.headers)
        art_html = art_res.text if art_res else ""
        art_items = self._parse_art_list(art_html)

        seen = set()
        result = []
        for item in items + art_items:
            if item["vod_id"] not in seen:
                seen.add(item["vod_id"])
                result.append(item)

        return {"list": result, "page": page}

    def playerContent(self, flag, id, vipFlags):
        import json
        # 图片浏览
        if id.startswith("pics://"):
            return {"parse": 0, "playUrl": "", "url": id, "header": {}}
        # 小说协议
        if id.startswith("novel://"):
            return {"parse": 0, "playUrl": "", "url": id, "header": {}}
        # 播放页链接 - 解析获取直链
        if id.startswith("/av/"):
            play_url = self.host + id
            try:
                import re
                res = self.fetch(play_url, headers=self.headers)
                html = res.text if res else ""
                match = re.search(r'var player_aaaa\s*=\s*({[^;]+});', html, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        m3u8_url = data.get("url", "")
                        if m3u8_url and (".m3u8" in m3u8_url or ".mp4" in m3u8_url):
                            self.log({"action": "player_parse_json", "m3u8": m3u8_url})
                            if ".m3u8" in m3u8_url:
                                m3u8_url = self._m3u8_proxy_url(m3u8_url)
                            return {"parse": 0, "playUrl": "", "url": m3u8_url, "header": {"User-Agent": "Mozilla/5.0"}}
                    except:
                        pass
                url_match = re.search(r'"url":"([^"]+\.m3u8[^"]*)"', html)
                if url_match:
                    m3u8_url = url_match.group(1)
                    self.log({"action": "player_parse_regex", "m3u8": m3u8_url})
                    m3u8_url = self._m3u8_proxy_url(m3u8_url)
                    return {"parse": 0, "playUrl": "", "url": m3u8_url, "header": {"User-Agent": "Mozilla/5.0"}}
                iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"[^>]*>', html)
                if iframe_match:
                    iframe_src = iframe_match.group(1)
                    if "askvodbf.com" in iframe_src:
                        url_param = re.search(r'\?url=([^&"\']+)', iframe_src)
                        if url_param:
                            return {"parse": 0, "playUrl": "", "url": url_param.group(1), "header": {"User-Agent": "Mozilla/5.0"}}
                    return {"parse": 1, "playUrl": "", "url": iframe_src, "header": {"User-Agent": "Mozilla/5.0", "Referer": self.host + "/"}}
                m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
                if m3u8_match:
                    m3u8_url = m3u8_match.group(1)
                    self.log({"action": "player_parse_m3u8_direct", "m3u8": m3u8_url})
                    m3u8_url = self._m3u8_proxy_url(m3u8_url)
                    return {"parse": 0, "playUrl": "", "url": m3u8_url, "header": {"User-Agent": "Mozilla/5.0"}}
                self.log({"action": "player_parse_failed", "html_len": len(html)})
            except Exception as e:
                self.log({"action": "player_error", "error": str(e)})
            return {"parse": 1, "playUrl": "", "url": play_url, "header": self.headers}
        if id.startswith("http"):
            if ".m3u8" in id.lower():
                return {"parse": 0, "playUrl": "", "url": self._m3u8_proxy_url(id), "header": {}}
            return {"parse": 0, "playUrl": "", "url": id, "header": self.headers}
        return {"parse": 0, "playUrl": "", "url": id, "header": self.headers}

    def localProxy(self, param):
        try:
            # 解析目标 URL
            target = ""
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "") or param.get("do", "")
            elif isinstance(param, str):
                target = param
            else:
                target = str(param or "")

            if not target and hasattr(param, "get"):
                target = param.get("url", "") or param.get("source", "") or param.get("do", "")

            if target.startswith("url="):
                target = target[4:]
            if target.startswith("source="):
                target = target[7:]

            # URL 解码
            target = urllib.parse.unquote(str(target or ""))

            # 替换转义反斜杠 \/ 为 /
            target = target.replace("\\/", "/")

            # 如果 target 包含完整代理地址，提取真实 URL
            if "proxy?do=py" in target or "proxy?do=py&url=" in target:
                url_match = re.search(r'[&?]url=([^&]+)', target)
                if url_match:
                    target = urllib.parse.unquote(url_match.group(1))
                    target = target.replace("\\/", "/")

            # 验证 URL
            if not target or not re.match(r"^https?://", target, re.I):
                if isinstance(param, dict):
                    for key in ["url", "source", "do", "u", "link", "play_url"]:
                        if param.get(key):
                            val = str(param[key])
                            val = val.replace("\\/", "/")
                            if val.startswith("http"):
                                target = val
                                break
                if not target or not re.match(r"^https?://", target, re.I):
                    return [400, "text/plain", f"invalid url: {target}".encode("utf-8")]

            # 图片代理
            if any(ext in target.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
                res = self.fetch(target, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                content = res.content if res else b""
                if not content:
                    return [404, "text/plain", b""]
                if content.startswith(bytes.fromhex("ffd8ff")):
                    mime = "image/jpeg"
                elif content.startswith(bytes.fromhex("89504e47")):
                    mime = "image/png"
                elif content.startswith(b"GIF8"):
                    mime = "image/gif"
                elif b"WEBP" in content[:20]:
                    mime = "image/webp"
                else:
                    mime = "application/octet-stream"
                return [200, mime, content]

            # m3u8 代理
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
    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return None

    def action(self, action):
        return None

    def destroy(self):
        return None