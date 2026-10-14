# coding: utf-8
"""
站点名称: 私人定制
主域名: https://xn--rp0a6b.srquantlabpure.site/
站点类型: MacCMS 影视站 (成人向)
内容类型: 视频 (m3u8)
解析方式: HTML 解析
"""
import json
import re
import urllib.parse
import posixpath
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xn--rp0a6b.srquantlabpure.site"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类 - 只保留已验证有内容的分类
        self.classes = [
            {"type_id": "29", "type_name": "人妖视频"},
            {"type_id": "31", "type_name": "捆绑调教"},
            {"type_id": "33", "type_name": "日本女优"},
            {"type_id": "35", "type_name": "中文字幕"},
            {"type_id": "39", "type_name": "欧美视频"},
            {"type_id": "43", "type_name": "国产视频"},
            {"type_id": "45", "type_name": "明星换脸"},
            {"type_id": "47", "type_name": "萝莉少女"},
            {"type_id": "49", "type_name": "网红主播"},
            {"type_id": "53", "type_name": "传媒拍摄"},
            {"type_id": "55", "type_name": "三级伦理"},
            {"type_id": "57", "type_name": "网暴黑料"},
            {"type_id": "59", "type_name": "激情动漫"},
            {"type_id": "61", "type_name": "全景视角"}
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}

    def getName(self):
        return "私人定制"

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
            html = self._fetch_html(self.host + "/")
            items = self._parse_list(html)
            return {"list": items[:20]}
        except Exception as e:
            self.log({"action": "homeVideoContent", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = pg or "1"
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
            html = self._fetch_html(url)
            items = self._parse_list(html)
            pagecount = self._parse_pagecount(html)
            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception as e:
            self.log({"action": "categoryContent", "tid": tid, "pg": pg, "error": str(e)})
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            vid = ids[0]
            url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
            try:
                resp = self.fetch(url, headers=self.headers, timeout=10)
                html = resp.text if hasattr(resp, "text") else ""
            except:
                html = ""

            vod = {
                "vod_id": vid,
                "vod_name": f"视频_{vid}",
                "vod_pic": "",
                "vod_remarks": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放$https://xn--rp0a6b.srquantlabpure.site/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            }

            if html:
                title_match = re.search(r'<p class="t-t"><a[^>]*>([^<]*)</a></p>', html)
                if title_match:
                    vod["vod_name"] = title_match.group(1).strip()
                pic_match = re.search(r'<img[^>]*src="([^"]+)"[^>]*alt="[^"]*"[^>]*>', html)
                if pic_match:
                    pic = pic_match.group(1)
                    if not pic.startswith("http"):
                        pic = urllib.parse.urljoin(self.host, pic)
                    vod["vod_pic"] = pic
                play_match = re.search(r'href="https://bf\.bofdingzabc\.xyz\?url=([^"]+)"', html)
                if play_match:
                    try:
                        decoded = urllib.parse.unquote(play_match.group(1))
                        if "$" in decoded:
                            parts = decoded.split("$", 1)
                            if len(parts) == 2 and parts[1].startswith("http"):
                                vod["vod_play_from"] = "直链"
                                vod["vod_play_url"] = parts[0] + "$" + parts[1]
                    except:
                        pass

            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent", "ids": ids, "error": str(e)})
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            data = {"wd": key}
            headers = self.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            resp = self.post(f"{self.host}/index.php/vod/search.html", data=data, headers=headers)
            html = resp.text if hasattr(resp, "text") else ""
            items = self._parse_list(html)
            return {"list": items, "page": int(pg)}
        except Exception as e:
            self.log({"action": "searchContent", "key": key, "error": str(e)})
            return {"list": [], "page": 1}

    def getProxyUrl(self):
        """获取本地代理地址"""
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址"""
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def playerContent(self, flag, id, vipFlags):
        try:
            # 如果已经是m3u8直链，包装成代理URL以过滤广告
            if isinstance(id, str) and id.startswith("http") and ".m3u8" in id:
                return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": self.headers}
            # 如果是bf.bofdingzabc.xyz链接，提取m3u8
            if isinstance(id, str) and "bf.bofdingzabc.xyz" in id and "url=" in id:
                match = re.search(r'url=([^&"]+)', id)
                if match:
                    try:
                        decoded = urllib.parse.unquote(match.group(1))
                        if "$" in decoded:
                            parts = decoded.split("$", 1)
                            if len(parts) == 2 and parts[1].startswith("http"):
                                real_url = parts[1]
                                if ".m3u8" in real_url:
                                    return {"parse": 0, "url": self._m3u8_proxy_url(real_url), "header": self.headers}
                    except:
                        pass
            # 如果是播放页URL或数字ID，交给WebView嗅探
            if isinstance(id, str) and ("/vod/play/id/" in id or id.isdigit()):
                if id.isdigit():
                    play_url = f"{self.host}/index.php/vod/play/id/{id}/sid/1/nid/1.html"
                else:
                    play_url = id
                return {"parse": 1, "url": play_url, "header": self.headers}
            return {"parse": 1, "url": id, "header": self.headers}
        except Exception as e:
            self.log({"action": "playerContent", "flag": flag, "id": id, "error": str(e)})
            return {"parse": 1, "url": id, "header": self.headers}

    def localProxy(self, param):
        """m3u8本地代理 - 广告分片过滤"""
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

            resp = self.fetch(target, headers=self.headers, timeout=15)
            if not resp:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")

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
        """重写m3u8标签中的URI（补全绝对地址）"""
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
            import urllib.request
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read()
                try:
                    return content.decode("utf-8")
                except:
                    try:
                        return content.decode("gb2312")
                    except:
                        return content.decode("gbk", errors="ignore")
        except Exception as e:
            self.log({"action": "_fetch_html", "url": url, "error": str(e)})
            return ""

    def _parse_list(self, html):
        items = []
        if not html:
            return items
        mainbar_pattern = r'<div class="mainbar">.*?<a[^>]*href="([^"]+)"[^>]*title="([^"]*)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<p class="t-t">([^<]*)</p>.*?<p class="date">([^<]*)</p>'
        matches = re.findall(mainbar_pattern, html, re.DOTALL)
        for match in matches:
            link, title_from_attr, pic, title_from_tag, remark = match
            title = title_from_attr or title_from_tag
            title = title.strip()
            if not title or not link:
                continue
            vid_match = re.search(r'/vod/detail/id/(\d+)\.html', link)
            if not vid_match:
                continue
            vid = vid_match.group(1)
            if not pic.startswith("http"):
                pic = urllib.parse.urljoin(self.host, pic)
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark.strip()
            })
        return items

    def _parse_pagecount(self, html):
        try:
            page_match = re.search(r'Page\s+\d+\s+of\s+(\d+)', html)
            if page_match:
                return int(page_match.group(1))
            page_links = re.findall(r'/page/(\d+)\.html', html)
            if page_links:
                return max([int(p) for p in page_links])
        except:
            pass
        return 99