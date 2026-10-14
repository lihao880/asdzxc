# coding: utf-8
# 站点：婶儿 (https://fusyzr.sher24.vip/)
# 类型：成人影视站 (MacCMS 风格)
# 最后验证：2026-09-08

import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://fusyzr.sher24.vip"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "1", "type_name": "视频一区"},
            {"type_id": "2", "type_name": "视频二区"},
            {"type_id": "3", "type_name": "视频三区"},
            {"type_id": "4", "type_name": "视频四区"},
        ]
        self.filters = {
            "1": [{"key": "sub_id", "name": "子分类", "value": [{"n": "全部", "v": ""}, {"n": "国产情色", "v": "22"}, {"n": "传媒精选", "v": "23"}, {"n": "中文字幕", "v": "24"}, {"n": "国产乱伦", "v": "25"}, {"n": "欧美情色", "v": "26"}, {"n": "日本无码", "v": "27"}, {"n": "AV解说", "v": "28"}, {"n": "明星换脸", "v": "29"}]}],
            "2": [{"key": "sub_id", "name": "子分类", "value": [{"n": "全部", "v": ""}, {"n": "野战车震", "v": "30"}, {"n": "群P换妻", "v": "31"}, {"n": "颜射系列", "v": "32"}, {"n": "成人动漫", "v": "33"}, {"n": "伦理影片", "v": "34"}, {"n": "酒店探花", "v": "35"}, {"n": "熟女少妇", "v": "36"}, {"n": "人兽乱交", "v": "37"}]}],
            "3": [{"key": "sub_id", "name": "子分类", "value": [{"n": "全部", "v": ""}, {"n": "偷情少妇", "v": "38"}, {"n": "学生空姐", "v": "39"}, {"n": "百合女同", "v": "40"}, {"n": "反差母狗", "v": "41"}, {"n": "巨乳尤物", "v": "42"}, {"n": "SM重味", "v": "43"}, {"n": "强奸乱伦", "v": "44"}, {"n": "自拍偷拍", "v": "45"}]}],
            "4": [{"key": "sub_id", "name": "子分类", "value": [{"n": "全部", "v": ""}, {"n": "人妻系列", "v": "46"}, {"n": "国产主播", "v": "47"}, {"n": "制服诱惑", "v": "48"}, {"n": "口交视频", "v": "49"}, {"n": "自慰系列", "v": "50"}, {"n": "教师学生", "v": "51"}, {"n": "颜值正义", "v": "52"}, {"n": "SM调教", "v": "53"}]}]
        }
        self.NEED_CLEAN = True

    def getName(self):
        return "婶儿"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self.categoryContent("1", "1", False, {})

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

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        ext = self._parse_extend(extend)
        sub_id = ext.get("sub_id", "")
        cat_id = sub_id if sub_id else tid
        url = f"{self.host}/index.php/vod/type/id/{cat_id}/page/{page}.html"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        html = r.text
        items = self._parse_list(html)
        pagecount = self._get_pagecount(html)
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount or 999,
            "limit": 20,
            "total": len(items) * pagecount if pagecount else 999
        }

    def _parse_list(self, html):
        items = []
        pattern = r'<div class="vod-list"><a href="([^"]+)"[^>]*>.*?<div class="vod-item">.*?<img src="([^"]+)"[^>]*>.*?<span class="vod-date">([^<]*)</span>.*?<p class="vod-name">([^<]*)</p>'
        for m in re.finditer(pattern, html, re.S):
            link = m.group(1).strip()
            pic = m.group(2).strip()
            date = m.group(3).strip()
            name = re.sub(r'<[^>]+>', '', m.group(4)).strip()
            if not link or not name:
                continue
            vid_match = re.search(r'/vod/detail/id/(\d+)\.html', link)
            if not vid_match:
                continue
            vid = vid_match.group(1)
            items.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": date
            })
        return items

    def _get_pagecount(self, html):
        m = re.search(r'/(\d+)页', html)
        if m:
            return int(m.group(1))
        m = re.search(r'max="(\d+)"', html)
        if m:
            return int(m.group(1))
        return None

    @staticmethod
    def _norm_ids(ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            try:
                ids = ids.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        return str(ids).strip()

    def _skeleton(self, vid, title="", pic=""):
        pid = str(vid).split("|$|")[0].replace("$", "|")
        return {"list": [{
            "vod_id": vid,
            "vod_name": title or "未知标题",
            "vod_pic": pic or "",
            "vod_remarks": "解析中",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${pid}",
        }]}

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}
        url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return self._skeleton(vid)
        html = r.text
        title = ""
        m = re.search(r'<div class="detail-pos"><text>([^<]*)</text></div>', html)
        if m:
            title = m.group(1).strip()
        pic = ""
        m = re.search(r'<img src="([^"]+)"[^>]*class="detail-vod-pic"', html)
        if m:
            pic = m.group(1).strip()
        play_url = ""
        m = re.search(r'<a class="play-btn-text" href="([^"]+)"', html)
        if m:
            play_url = m.group(1).strip()
            if not play_url.startswith("http"):
                play_url = self.host + play_url
        if not play_url:
            return self._skeleton(vid, title, pic)
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title or "未知标题",
                "vod_pic": pic or "",
                "vod_remarks": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}",
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        enc_key = urllib.parse.quote(key, encoding="utf-8")
        url = f"{self.host}/index.php/vod/search.html?wd={enc_key}"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": [], "page": int(pg)}
        html = r.text
        items = self._parse_list(html)
        return {"list": items, "page": int(pg)}

    def _grab_json_object(self, html, var):
        """平衡括号提取 player_aaaa JSON 对象"""
        m = re.search(r'(?:var|let|const)?\s*' + re.escape(var) + r'\s*=\s*\{', html)
        if not m:
            return None
        start = html.index("{", m.start())
        depth = 0
        in_str = False
        esc = False
        quote = ""
        for i in range(start, len(html)):
            c = html[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == quote:
                    in_str = False
                continue
            if c in ('"', "'"):
                in_str = True
                quote = c
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    raw = html[start:i+1]
                    # 转义还原
                    raw = raw.replace("\\/", "/")
                    raw = raw.replace("\\\"", '"')
                    try:
                        return json.loads(raw)
                    except Exception:
                        # 尝试修复尾逗号
                        raw_fixed = re.sub(r',\s*([}\]])', r'\1', raw)
                        try:
                            return json.loads(raw_fixed)
                        except Exception:
                            return None
        return None

    def _extract_play_url(self, html):
        """从播放页提取 m3u8 地址"""
        obj = self._grab_json_object(html, "player_aaaa")
        if obj and isinstance(obj, dict):
            url = obj.get("url", "")
            if url and url.startswith("http"):
                return url
        # 备用：直接正则匹配 url 字段
        m = re.search(r'"url"\s*:\s*"([^"]+)"', html)
        if m:
            url = m.group(1).replace("\\/", "/")
            if url.startswith("http"):
                return url
        return None

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id or "").strip()
        if not play_url:
            return {"parse": 0, "url": "", "header": {}}

        ua = self.headers.get("User-Agent", "")

        if play_url and "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]

        if play_url and not play_url.startswith("http"):
            if not play_url.startswith("//"):
                play_url = "https://" + play_url

        # 如果是 m3u8 直链
        if play_url and ".m3u8" in play_url.lower():
            if self.NEED_CLEAN:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(play_url),
                    "header": {"User-Agent": ua}
                }
            return {"parse": 0, "url": play_url, "header": {"User-Agent": ua}}

        # 请求播放页提取 m3u8
        if not play_url.startswith("http"):
            play_url = self.host + play_url

        r = self.fetch(play_url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"parse": 1, "url": play_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}

        html = r.text
        m3u8_url = self._extract_play_url(html)

        if m3u8_url:
            if self.NEED_CLEAN:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(m3u8_url),
                    "header": {"User-Agent": ua}
                }
            return {"parse": 0, "url": m3u8_url, "header": {"User-Agent": ua}}

        return {"parse": 1, "url": play_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}

    def _m3u8_proxy_url(self, url):
        return "http://127.0.0.1:9978/proxy?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

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

    def _is_fake_image_stream(self, text):
        IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
        VIDEO_EXT = (".ts", ".m4s", ".mp4", ".aac", ".m4a")
        has_video = False
        has_image = False
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            path = line.split("?")[0].split("#")[0].lower()
            if path.endswith(VIDEO_EXT):
                has_video = True
            elif path.endswith(IMAGE_EXT):
                has_image = True
        return has_image and not has_video

    def _resolve_main_dir(self, lines, source_url, is_image_stream=False):
        import posixpath
        base_dir = posixpath.dirname(urllib.parse.urlparse(source_url).path)
        if not base_dir.endswith("/"):
            base_dir += "/"

        if is_image_stream:
            counter = {}
            for line in lines:
                if not line or line.startswith("#"):
                    continue
                p = urllib.parse.urlparse(urllib.parse.urljoin(source_url, line)).path
                d = posixpath.dirname(p)
                if d and d != "/":
                    counter[d + "/"] = counter.get(d + "/", 0) + 1
            if counter:
                return max(counter.items(), key=lambda kv: kv[1])[0]
            return base_dir

        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            key_path = urllib.parse.urlparse(
                key_uri if key_uri.startswith("http")
                else urllib.parse.urljoin(source_url, key_uri)
            ).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return base_dir

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
                media_url = urllib.parse.urljoin(source_url, line)
                media_path = urllib.parse.urlparse(media_url).path
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
                segments.append(urllib.parse.urljoin(source_url, line))
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

        is_img = self._is_fake_image_stream(text)

        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    if ".m3u8" in child.lower():
                        out.append(self._m3u8_proxy_url(child))
                    else:
                        out.append(child)
            return "\n".join(out) + "\n"

        main_dir = self._resolve_main_dir(lines, source_url, is_image_stream=is_img)
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        if removed > 0 and (kept == 0 or removed > kept):
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

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
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(target).query)
                if "url" in qs:
                    target = qs["url"][0]
            target = urllib.parse.unquote(str(target or ""))
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

    def recommendContent(self, ids, pg):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}
        url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": []}
        html = r.text
        items = self._parse_list(html)
        items = [it for it in items if it.get("vod_id") != vid]
        return {"list": items[:12]}

    def destroy(self):
        pass