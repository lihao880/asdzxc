# coding: utf-8
# 极致视觉 - MacCMS 影视站爬虫
# 站点: https://xn--6kqp3o1xtjuu.jzaccetexscale.site/
# 特性: 分类列表、搜索、播放、m3u8本地代理 + 广告分片过滤

import re
import json
import urllib.parse
import posixpath
from urllib.parse import urljoin, quote, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xn--6kqp3o1xtjuu.jzaccetexscale.site"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类硬编码
        self.classes = [
            {"type_id": "57", "type_name": "网暴黑料"},
            {"type_id": "51", "type_name": "探花约泡"},
            {"type_id": "53", "type_name": "传媒剧情"},
            {"type_id": "49", "type_name": "女主播"},
            {"type_id": "31", "type_name": "捆绑调教"},
            {"type_id": "35", "type_name": "中文字幕"},
            {"type_id": "43", "type_name": "国产视频"},
            {"type_id": "29", "type_name": "人妖"},
            {"type_id": "47", "type_name": "萝莉女"},
            {"type_id": "23", "type_name": "女同性"},
            {"type_id": "33", "type_name": "日本无码"},
            {"type_id": "55", "type_name": "三级片"},
            {"type_id": "25", "type_name": "重口味"},
            {"type_id": "39", "type_name": "欧美视频"},
            {"type_id": "37", "type_name": "黑人无码"}
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}

    def getName(self):
        return "极致视觉"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            res = self.fetch(self.host + "/", headers=self.headers)
            html = res.text if hasattr(res, "text") else res.content.decode("utf-8", errors="ignore")
            items = self._parse_list_items(html)
            return {"list": items[:24]}
        except Exception as e:
            self.log({"action": "homeVideoContent_error", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        try:
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
            res = self.fetch(url, headers=self.headers)
            html = res.text if hasattr(res, "text") else res.content.decode("utf-8", errors="ignore")
            items = self._parse_list_items(html)
            pagecount = self._parse_pagecount(html)
            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount or 99,
                "limit": 20,
                "total": (pagecount or 99) * 20
            }
        except Exception as e:
            self.log({"action": "categoryContent_error", "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            if not ids:
                return {"list": []}
            vid = str(ids[0])
            parts = vid.split('|$|')
            if len(parts) >= 5:
                vod_id = parts[0]
                title = parts[1]
                pic = parts[2]
                remark = parts[3]
                play_url = parts[4]
            else:
                vod_id = vid
                title = ""
                pic = ""
                remark = ""
                play_url = ""
                detail_url = f"{self.host}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
                detail_data = self._fetch_detail(detail_url)
                if detail_data:
                    title = detail_data.get("title", "")
                    pic = detail_data.get("pic", "")
                    remark = detail_data.get("remark", "")
                    play_url = detail_data.get("play_url", "")

            vod = {
                "vod_id": f"{vod_id}|$|{title}|$|{pic}|$|{remark}|$|{play_url}",
                "vod_name": title or "视频",
                "vod_pic": pic,
                "vod_remarks": remark,
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}" if play_url else ""
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent_error", "error": str(e)})
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            url = f"{self.host}/index.php/vod/search.html"
            data = {"wd": key}
            res = self.post(url, data=data, headers=self.headers)
            html = res.text if hasattr(res, "text") else res.content.decode("utf-8", errors="ignore")
            items = self._parse_list_items(html)
            return {"list": items, "page": int(pg)}
        except Exception as e:
            self.log({"action": "searchContent_error", "error": str(e)})
            return {"list": [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        try:
            if id.startswith("http"):
                if id.endswith(".m3u8") or id.endswith(".mp4"):
                    return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": self.headers}
                play_data = self._fetch_play_page(id)
                if play_data and play_data.get("url"):
                    return {"parse": 0, "url": self._m3u8_proxy_url(play_data["url"]), "header": self.headers}
                return {"parse": 1, "url": id, "header": self.headers}
            if id.startswith("/"):
                full_url = self.host + id
                play_data = self._fetch_play_page(full_url)
                if play_data and play_data.get("url"):
                    return {"parse": 0, "url": self._m3u8_proxy_url(play_data["url"]), "header": self.headers}
                return {"parse": 1, "url": full_url, "header": self.headers}
            if id.isdigit():
                play_url = f"{self.host}/index.php/vod/play/id/{id}/sid/1/nid/1.html"
                play_data = self._fetch_play_page(play_url)
                if play_data and play_data.get("url"):
                    return {"parse": 0, "url": self._m3u8_proxy_url(play_data["url"]), "header": self.headers}
                return {"parse": 1, "url": play_url, "header": self.headers}
            play_data = self._fetch_play_page(id)
            if play_data and play_data.get("url"):
                return {"parse": 0, "url": self._m3u8_proxy_url(play_data["url"]), "header": self.headers}
            return {"parse": 1, "url": id, "header": self.headers}
        except Exception as e:
            self.log({"action": "playerContent_error", "error": str(e)})
            return {"parse": 1, "url": id, "header": self.headers}
    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy?do=py"

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "&url=" + quote(str(url or ""), safe="")

    def localProxy(self, param):
        """m3u8本地代理 - 广告分片过滤"""
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = unquote(str(target or ""))

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
        """清洗m3u8 - 过滤广告分片"""
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
                    child = urljoin(source_url, line)
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
        ad_filtered_count = 0

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urljoin(source_url, line)
                media_parsed = urllib.parse.urlparse(media_url)

                # 过滤：分片路径以正片目录开头
                is_ad = not media_parsed.path.startswith(main_dir)

                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                else:
                    ad_filtered_count += 1
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urljoin(source_url, line))
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

        if ad_filtered_count > 0:
            self.log(f"m3u8已过滤广告分片: {ad_filtered_count}个")

        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI"""
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

    def _parse_list_items(self, html):
        items = []
        pattern = r'<div><a href="([^"]+)"[^>]*><span class="title">([^<]*)</span>\s*<img[^>]*src="([^"]*)"[^>]*></a><span[^>]*></span>\s*<span class="duration">([^<]*)</span>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            href, title, pic, duration = match
            vid_match = re.search(r'/id/(\d+)/', href)
            if not vid_match:
                continue
            vid = vid_match.group(1)
            if pic and not pic.startswith("http"):
                pic = urljoin(self.host, pic)
            play_url = href if href.startswith("http") else urljoin(self.host, href)
            items.append({
                "vod_id": f"{vid}|$|{title}|$|{pic}|$|{duration}|$|{play_url}",
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": duration.strip()
            })
        return items

    def _parse_pagecount(self, html):
        pattern = r'<a href="[^"]*/page/(\d+)\.html"[^>]*>(\d+)</a>'
        matches = re.findall(pattern, html)
        if matches:
            nums = [int(m[1]) for m in matches]
            return max(nums) if nums else 1
        return 1

    def _fetch_detail(self, url):
        try:
            res = self.fetch(url, headers=self.headers)
            html = res.text if hasattr(res, "text") else res.content.decode("utf-8", errors="ignore")
            player_match = re.search(r'var player_aaaa=({[^;]+});', html)
            if player_match:
                try:
                    data = json.loads(player_match.group(1))
                    title = data.get("vod_data", {}).get("vod_name", "")
                    play_url = data.get("url", "").replace("\\/", "/")
                    return {"title": title, "play_url": play_url}
                except:
                    pass
            title_match = re.search(r'<h3>\s*正在播放-([^<]+)</h3>', html)
            title = title_match.group(1).strip() if title_match else ""
            return {"title": title, "play_url": ""}
        except:
            return {}

    def _fetch_play_page(self, url):
        try:
            res = self.fetch(url, headers=self.headers)
            if hasattr(res, "text"):
                html = res.text
            elif hasattr(res, "content"):
                html = res.content.decode("utf-8", errors="ignore")
            else:
                html = str(res)

            player_match = re.search(r'var\s+player_aaaa\s*=\s*({[^;]+});', html, re.DOTALL)
            if player_match:
                try:
                    data = json.loads(player_match.group(1))
                    play_url = data.get("url", "").replace("\\/", "/")
                    if play_url and (play_url.endswith(".m3u8") or play_url.endswith(".mp4")):
                        return {"url": play_url}
                except:
                    url_match = re.search(r'"url"\s*:\s*"([^"]+)"', player_match.group(1))
                    if url_match:
                        play_url = url_match.group(1).replace("\\/", "/")
                        if play_url and (play_url.endswith(".m3u8") or play_url.endswith(".mp4")):
                            return {"url": play_url}

            url_match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
            if url_match:
                play_url = url_match.group(1).replace("\\/", "/")
                if play_url:
                    return {"url": play_url}

            iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"[^>]*>', html)
            if iframe_match:
                src = iframe_match.group(1)
                url_param = re.search(r'[?&]url=([^&]+)', src)
                if url_param:
                    play_url = unquote(url_param.group(1)).replace("\\/", "/")
                    if play_url and (play_url.endswith(".m3u8") or play_url.endswith(".mp4")):
                        return {"url": play_url}

            return {}
        except Exception as e:
            self.log({"action": "_fetch_play_page_error", "error": str(e), "url": url})
            return {}