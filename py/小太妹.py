# coding: utf-8
# 站点: 小太妹 (https://www.yxcmav.xyz/aa/)
# 类型: MacCMS 成人视频站
# 特性: m3u8 直链播放, 本地分类硬编码, 支持分页, 搜索, 广告过滤

import json
import re
import urllib.parse
import posixpath
from urllib.parse import urlparse, urljoin, quote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.yxcmav.xyz"
        self.base_path = "/aa"

        self.classes = [
            {"type_id": "8", "type_name": "巨乳美乳"},
            {"type_id": "45", "type_name": "人妻熟女"},
            {"type_id": "21", "type_name": "素人自拍"},
            {"type_id": "35", "type_name": "可爱学生"},
            {"type_id": "42", "type_name": "网曝门"},
            {"type_id": "43", "type_name": "传媒出品"},
            {"type_id": "44", "type_name": "女同性恋"},
        ]

        self.filters = {c["type_id"]: [] for c in self.classes}

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.host + "/"
        }
    def getName(self):
        return "小太妹"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        url = self.host + self.base_path + "/index.php/index/index.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        items = []
        pattern = r'<li>\s*<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-original="([^"]+)"[^>]*>.*?<h3[^>]*><a[^>]*>.*?<text>([^<]*)</text>'
        matches = re.findall(pattern, html, re.DOTALL)

        seen = set()
        for href, pic, title in matches:
            if not title or href in seen:
                continue
            seen.add(href)
            if href.startswith("/aa/index.php/vod/play/id/"):
                vid = self._extract_vid_from_url(href)
                if vid:
                    items.append({
                        "vod_id": vid,
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": ""
                    })
        return {"list": items[:40]}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = self.host + self.base_path + f"/index.php/vod/type/id/{tid}.html"
        if str(page) != "1":
            url += f"?page={page}"

        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

        items = []
        pattern = r'<li>\s*<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-original="([^"]+)"[^>]*>.*?<h3[^>]*><a[^>]*>.*?<text>([^<]*)</text>'
        matches = re.findall(pattern, html, re.DOTALL)

        seen = set()
        for href, pic, title in matches:
            if not title or href in seen:
                continue
            seen.add(href)
            if href.startswith("/aa/index.php/vod/play/id/"):
                vid = self._extract_vid_from_url(href)
                if vid:
                    items.append({
                        "vod_id": vid,
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": ""
                    })

        total = 0
        pagecount = 1
        total_match = re.search(r'找到\s*(\d+)\s*条', html)
        if total_match:
            total = int(total_match.group(1))
            pagecount = (total + 19) // 20

        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": total
        }

    def detailContent(self, ids):
        if isinstance(ids, list) and len(ids) > 0:
            vid = str(ids[0])
        else:
            vid = str(ids)

        play_url = self.host + self.base_path + f"/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        html = self._fetch_html(play_url)
        if not html:
            return {"list": []}

        player_data = self._extract_player_data(html)
        if not player_data:
            return {"list": []}

        # 解码 Unicode 转义字符
        vod_name = player_data.get("vod_data", {}).get("vod_name", "视频")
        if vod_name:
            try:
                vod_name = vod_name.encode('utf-8').decode('unicode_escape')
            except:
                pass

        vod_pic = ""
        play_url_raw = player_data.get("url", "")
        play_from = player_data.get("from", "播放")

        # 清理 URL：去除转义的反斜杠
        if play_url_raw:
            play_url_raw = play_url_raw.replace("\\/", "/")

        # 解析主 m3u8，提取子 m3u8 的完整 URL
        if play_url_raw and (play_url_raw.endswith(".m3u8") or ".m3u8" in play_url_raw):
            try:
                resp = self.fetch(play_url_raw, headers=self.headers, timeout=10)
                if resp and resp.status_code == 200:
                    content = resp.text
                    if "#EXT-X-STREAM-INF" in content:
                        lines = content.splitlines()
                        for i, line in enumerate(lines):
                            if line.startswith("#EXT-X-STREAM-INF"):
                                if i + 1 < len(lines):
                                    sub_path = lines[i + 1].strip()
                                    if sub_path.startswith("//"):
                                        parsed = urlparse(play_url_raw)
                                        sub_url = f"{parsed.scheme}:{sub_path}"
                                    elif sub_path.startswith("http://") or sub_path.startswith("https://"):
                                        sub_url = sub_path
                                    else:
                                        parsed = urlparse(play_url_raw)
                                        sub_url = f"{parsed.scheme}://{parsed.netloc}/{sub_path.lstrip('/')}"
                                    play_url_raw = sub_url
                                    break
            except Exception as e:
                self.log(f"解析变体流失败: {str(e)}")

        pic_match = re.search(r'data-original="([^"]+)"', html)
        if pic_match:
            vod_pic = pic_match.group(1)

        vod = {
            "vod_id": vid,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": play_from,
            "vod_play_url": "正片$" + play_url_raw if play_url_raw else ""
        }

        return {"list": [vod]}
    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}

        page = pg or "1"
        url = self.host + self.base_path + f"/index.php/vod/search.html?wd={quote(key)}"
        if str(page) != "1":
            url += f"&page={page}"

        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": int(page)}

        items = []
        pattern = r'<li>\s*<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-original="([^"]+)"[^>]*>.*?<h3[^>]*><a[^>]*>.*?<text>([^<]*)</text>'
        matches = re.findall(pattern, html, re.DOTALL)

        seen = set()
        for href, pic, title in matches:
            if not title or href in seen:
                continue
            seen.add(href)
            if href.startswith("/aa/index.php/vod/play/id/"):
                vid = self._extract_vid_from_url(href)
                if vid:
                    items.append({
                        "vod_id": vid,
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": ""
                    })

        return {"list": items, "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        """播放器 - 返回 parse:0 直链，走代理过滤广告"""
        if id.startswith("http://") or id.startswith("https://"):
            # 返回代理地址，让 localProxy 过滤广告
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id),
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/"
                }
            }

        if str(id).isdigit():
            detail = self.detailContent([id])
            if detail.get("list"):
                vod = detail["list"][0]
                play_url = vod.get("vod_play_url", "")
                if play_url:
                    parts = play_url.split("$")
                    if len(parts) == 2:
                        return {
                            "parse": 0,
                            "url": self._m3u8_proxy_url(parts[1]),
                            "header": {
                                "User-Agent": self.headers["User-Agent"],
                                "Referer": self.host + "/"
                            }
                        }

        return {
            "parse": 1,
            "url": id,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/"
            }
        }

    def localProxy(self, param):
        """m3u8 本地代理 - 广告分片过滤 (基于 m3u8_ad_filter.md v3.0)"""
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
        """清洗 m3u8：过滤广告分片，保留正片"""
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
        """重写 m3u8 标签中的 URI（补全绝对地址）"""
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

    def _fetch_html(self, url):
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if resp and hasattr(resp, 'status_code') and resp.status_code == 200:
                return resp.text
        except Exception as e:
            self.log(f"fetch error: {str(e)}")
        return None

    def _extract_vid_from_url(self, url):
        match = re.search(r'/vod/play/id/(\d+)', url)
        return match.group(1) if match else None

    def _extract_player_data(self, html):
        """从页面源码提取 player_aaaa 数据"""
        pattern = r'var\s+player_aaaa\s*=\s*({[\s\S]+?});'
        match = re.search(pattern, html)
        if not match:
            return None

        try:
            return json.loads(match.group(1))
        except Exception as e:
            self.log(f"json parse error: {str(e)}")
            # 尝试手动提取关键字段
            text = match.group(1)
            result = {}
            
            # 提取 url
            url_match = re.search(r'"url"\s*:\s*"([^"]+)"', text)
            if url_match:
                result["url"] = url_match.group(1)
            
            # 提取 vod_name
            name_match = re.search(r'"vod_name"\s*:\s*"([^"]+)"', text)
            if name_match:
                result["vod_data"] = {"vod_name": name_match.group(1)}
            
            # 提取 from
            from_match = re.search(r'"from"\s*:\s*"([^"]+)"', text)
            if from_match:
                result["from"] = from_match.group(1)
            
            return result if result else None
    def destroy(self):
        pass