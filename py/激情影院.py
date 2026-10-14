# coding: utf-8
"""
站点名称: 激情影院
域名: https://fangjiu.cfd/
架构: MacCMS
内容类型: 成人影视 (视频)
分类数: 16
播放地址: 从播放页 player_aaaa.url 提取 m3u8 直链
"""
import json
import re
import urllib.parse
import posixpath
from urllib.parse import urljoin, quote, unquote
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://fangjiu.cfd"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }

        self.classes = [
            {"type_id": "1", "type_name": "国产乱伦"},
            {"type_id": "2", "type_name": "制服诱惑"},
            {"type_id": "3", "type_name": "中文字幕"},
            {"type_id": "4", "type_name": "蜜桃传媒"},
            {"type_id": "5", "type_name": "精东影业"},
            {"type_id": "6", "type_name": "日韩专区"},
            {"type_id": "7", "type_name": "国产高清"},
            {"type_id": "8", "type_name": "欧美极品"},
            {"type_id": "9", "type_name": "无码专区"},
            {"type_id": "10", "type_name": "熟女素人"},
            {"type_id": "11", "type_name": "精品动漫"},
            {"type_id": "12", "type_name": "麻豆传媒"},
            {"type_id": "13", "type_name": "AV解说"},
            {"type_id": "14", "type_name": "91视频"},
            {"type_id": "15", "type_name": "三级伦理"},
            {"type_id": "16", "type_name": "绿帽淫妻"},
        ]

        self.filters = {str(i): [] for i in range(1, 17)}

    def getName(self):
        return "激情影院"

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
        url = self.host + "/"
        try:
            resp = self.fetch(url, headers=self.headers)
            if resp.status_code != 200:
                return {"list": []}
            html = resp.text
            return self._parse_home_list(html)
        except Exception as e:
            self.log("homeVideoContent error: " + str(e))
            return {"list": []}

    def _parse_home_list(self, html):
        videos = []
        pattern = r'<a[^>]*class="[^"]*video-pic[^"]*"[^>]*data-original="([^"]+)"[^>]*href="([^"]+)"[^>]*title="([^"]*)"'
        matches = re.findall(pattern, html)
        for pic, href, title in matches[:20]:
            if href:
                vid = self._extract_vod_id(href)
                videos.append({
                    "vod_id": vid,
                    "vod_name": title.strip() or "未知视频",
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return {"list": videos}

    def _extract_vod_id(self, url):
        match = re.search(r'/id/(\d+)\.html', url)
        if match:
            return match.group(1)
        return url

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
        try:
            resp = self.fetch(url, headers=self.headers)
            if resp.status_code != 200:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = resp.text

            videos = []
            seen = set()

            pattern = r'<a[^>]*class="[^"]*video-pic[^"]*"[^>]*data-original="([^"]+)"[^>]*href="([^"]+)"[^>]*title="([^"]*)"'
            matches = re.findall(pattern, html)
            for pic, href, title in matches:
                vid = self._extract_vod_id(href)
                if vid not in seen:
                    seen.add(vid)
                    videos.append({
                        "vod_id": vid,
                        "vod_name": title.strip() or "未知视频",
                        "vod_pic": pic,
                        "vod_remarks": ""
                    })

            if len(videos) < 5:
                pattern2 = r'<a[^>]*class="[^"]*video-pic[^"]*"[^>]*src="([^"]+)"[^>]*href="([^"]+)"[^>]*title="([^"]*)"'
                matches2 = re.findall(pattern2, html)
                for pic, href, title in matches2:
                    vid = self._extract_vod_id(href)
                    if vid not in seen:
                        seen.add(vid)
                        videos.append({
                            "vod_id": vid,
                            "vod_name": title.strip() or "未知视频",
                            "vod_pic": pic,
                            "vod_remarks": ""
                        })

            if len(videos) < 5:
                detail_links = re.findall(r'href="(/index\.php/vod/detail/id/(\d+)\.html)"[^>]*>([^<]+)</a>', html)
                for href, vid, title in detail_links:
                    if vid not in seen and len(title.strip()) > 2:
                        seen.add(vid)
                        videos.append({
                            "vod_id": vid,
                            "vod_name": title.strip(),
                            "vod_pic": "",
                            "vod_remarks": ""
                        })

            pagecount = 1
            total = 0
            page_match = re.search(r'共(\d+)条数据,当前(\d+)/(\d+)页', html)
            if page_match:
                total = int(page_match.group(1))
                pagecount = int(page_match.group(3))
            else:
                page_links = re.findall(r'<a[^>]*href="[^"]*/page/(\d+)\.html"', html)
                if page_links:
                    pagecount = max([int(p) for p in page_links])

            return {
                "list": videos[:30],
                "page": int(page),
                "pagecount": pagecount if pagecount > 0 else 1,
                "limit": 20,
                "total": total
            }
        except Exception as e:
            self.log("categoryContent error: " + str(e))
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        vid = ids[0] if ids else ""
        if not vid:
            return {"list": []}

        url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        try:
            resp = self.fetch(url, headers=self.headers)
            if resp.status_code != 200:
                return {"list": []}
            html = resp.text

            vod = {
                "vod_id": vid,
                "vod_name": "",
                "vod_pic": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "",
                "vod_play_url": ""
            }

            title_match = re.search(r'<title>(.+?)</title>', html)
            if title_match:
                title = title_match.group(1)
                title = re.sub(r'详情介绍.*$', '', title)
                title = re.sub(r'在线观看.*$', '', title)
                title = re.sub(r'迅雷下载.*$', '', title)
                title = re.sub(r' - 激情影院$', '', title)
                vod["vod_name"] = title.strip()

            pic_match = re.search(r'data-original="([^"]+)"', html)
            if not pic_match:
                pic_match = re.search(r'src="([^"]+)"[^>]*class="video-pic"', html)
            if pic_match:
                vod["vod_pic"] = pic_match.group(1)

            desc_match = re.search(r'<div[^>]*class="[^"]*desc[^"]*"[^>]*>([^<]+)</div>', html, re.DOTALL)
            if desc_match:
                vod["vod_content"] = desc_match.group(1).strip()

            play_link_match = re.search(r'href="(/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"', html)
            if play_link_match:
                play_url = self.host + play_link_match.group(1)
                vod["vod_play_from"] = "线路1"
                vod["vod_play_url"] = f"播放${play_url}"
            else:
                play_link_match2 = re.search(r'href="([^"]*play/id/[^"]+\.html)"', html)
                if play_link_match2:
                    play_url = self.host + play_link_match2.group(1)
                    vod["vod_play_from"] = "线路1"
                    vod["vod_play_url"] = f"播放${play_url}"
                else:
                    fallback_play_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
                    vod["vod_play_from"] = "线路1"
                    vod["vod_play_url"] = f"播放${fallback_play_url}"

            return {"list": [vod]}
        except Exception as e:
            self.log("detailContent error: " + str(e))
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        # 站点搜索功能已关闭，返回空列表
        return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        if id and (id.endswith(".m3u8") or id.endswith(".mp4")):
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id) if id.endswith(".m3u8") else id,
                "header": self.headers
            }

        if id and id.startswith("http") and "/vod/play/" in id:
            try:
                resp = self.fetch(id, headers=self.headers)
                if resp.status_code != 200:
                    return {"parse": 1, "url": id, "header": self.headers}
                html = resp.text

                player_match = re.search(r'var player_aaaa\s*=\s*({[^}]+})', html)
                if player_match:
                    try:
                        player_data = json.loads(player_match.group(1))
                        if player_data.get("url"):
                            m3u8_url = player_data["url"]
                            return {
                                "parse": 0,
                                "url": self._m3u8_proxy_url(m3u8_url),
                                "header": {
                                    "User-Agent": self.headers["User-Agent"],
                                    "Referer": self.host + "/"
                                }
                            }
                    except:
                        pass

                m3u8_match = re.search(r'https?://[^\s<>"\']+\.m3u8[^\s<>"\']*', html)
                if m3u8_match:
                    return {
                        "parse": 0,
                        "url": self._m3u8_proxy_url(m3u8_match.group(0)),
                        "header": self.headers
                    }

                return {"parse": 1, "url": id, "header": self.headers}
            except Exception as e:
                self.log("playerContent error: " + str(e))
                return {"parse": 1, "url": id, "header": self.headers}

        return {"parse": 1, "url": id, "header": self.headers}

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片，保留正片"""
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

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤"""
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

    def siteInfo(self):
        return {
            "name": "激情影院",
            "host": self.host,
            "description": "成人影视站，MacCMS架构"
        }