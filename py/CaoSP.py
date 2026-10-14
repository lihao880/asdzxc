# coding=utf-8
# Caosp影视 Spider - 广告过滤 v3.0
# 站点: https://web.caosp3.cc

import re
import json
import posixpath
import urllib.parse
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.base_url = "https://web.caosp3.cc"
        self.site_url = "/a/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.base_url + "/a/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive"
        }

        self.classes = [
            {"type_id": "244", "type_name": "163资源"},
            {"type_id": "358", "type_name": "Cao资源"},
            {"type_id": "329", "type_name": "裤子资源"},
            {"type_id": "119", "type_name": "不卡资源"},
            {"type_id": "286", "type_name": "兔儿资源"},
            {"type_id": "370", "type_name": "森林资源"}
        ]

        self.filters = {
            "244": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "AV解说", "v": "266"},
                    {"n": "国产自拍", "v": "254"},
                    {"n": "熟女人妻", "v": "255"},
                    {"n": "萝莉少女", "v": "256"},
                    {"n": "百合剧情", "v": "257"},
                    {"n": "美乳巨乳", "v": "258"},
                    {"n": "强歼乱伦", "v": "259"},
                    {"n": "抖音视频", "v": "260"},
                    {"n": "韩国主播", "v": "89"},
                    {"n": "网红头条", "v": "90"}
                ]}
            ],
            "358": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "高清有码", "v": "369"},
                    {"n": "动漫精选", "v": "368"},
                    {"n": "学生妹", "v": "367"},
                    {"n": "中文字幕", "v": "366"},
                    {"n": "高清无码", "v": "365"},
                    {"n": "黑料网曝", "v": "364"},
                    {"n": "主播网红", "v": "363"},
                    {"n": "乱伦系列", "v": "362"},
                    {"n": "国产精品", "v": "7"},
                    {"n": "偷拍自拍", "v": "28"}
                ]}
            ],
            "329": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "日本有码", "v": "330"},
                    {"n": "无码中文", "v": "331"},
                    {"n": "有码中文", "v": "332"},
                    {"n": "日本无码", "v": "333"},
                    {"n": "国产视频", "v": "334"},
                    {"n": "欧美高清", "v": "335"},
                    {"n": "动漫剧情", "v": "336"}
                ]}
            ],
            "119": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "国产视频", "v": "120"},
                    {"n": "中文字幕", "v": "121"},
                    {"n": "国产传媒", "v": "122"},
                    {"n": "日本有码", "v": "123"},
                    {"n": "日本无码", "v": "124"},
                    {"n": "欧美无码", "v": "125"},
                    {"n": "强干乱伦", "v": "126"},
                    {"n": "制服诱惑", "v": "127"},
                    {"n": "国产主播", "v": "3"},
                    {"n": "激情动漫", "v": "4"}
                ]}
            ],
            "286": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "精品推荐", "v": "304"},
                    {"n": "主播秀色", "v": "305"},
                    {"n": "日本有码", "v": "306"},
                    {"n": "日本无码", "v": "307"},
                    {"n": "中文字幕", "v": "308"},
                    {"n": "童颜巨乳", "v": "309"},
                    {"n": "性感人妻", "v": "310"},
                    {"n": "强歼乱伦", "v": "311"},
                    {"n": "欧美情色", "v": "24"},
                    {"n": "三级伦理", "v": "25"}
                ]}
            ],
            "370": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "精品推荐", "v": "371"},
                    {"n": "国产情色", "v": "372"},
                    {"n": "亚洲无码", "v": "373"},
                    {"n": "亚洲有码", "v": "374"},
                    {"n": "中文字幕", "v": "375"},
                    {"n": "强*乱伦", "v": "376"},
                    {"n": "欧美精品", "v": "377"},
                    {"n": "萝莉少女", "v": "378"},
                    {"n": "日本精品", "v": "45"},
                    {"n": "Cosplay", "v": "54"}
                ]}
            ]
        }

    def init(self, cfg=None):
        pass

    def getDependence(self):
        return []

    def getName(self):
        return "CaoSP"

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def _fetch_html(self, url):
        try:
            res = self.fetch(url, headers=self.headers, timeout=15)
            if res is None:
                return ""
            if hasattr(res, "text") and res.text:
                return res.text
            if hasattr(res, "content") and res.content:
                try:
                    return res.content.decode('utf-8', errors='ignore')
                except Exception:
                    pass
            return ""
        except Exception:
            return ""

    def fix_url(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.base_url + url
        return urllib.parse.urljoin(self.base_url, url)

    def extract_id_from_url(self, url):
        match = re.search(r'/detail/id/(\d+)\.html', url)
        if match:
            return match.group(1)
        match = re.search(r'/play/id/(\d+)/', url)
        if match:
            return match.group(1)
        match = re.search(r'[?&]id=(\d+)', url)
        if match:
            return match.group(1)
        return url

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.base_url + self.site_url)
        items = self._parse_list(html)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        actual_tid = tid
        if extend:
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except:
                    extend = {}
            if isinstance(extend, dict) and extend.get("sub"):
                actual_tid = extend["sub"]
        url = f"{self.base_url}/a/index.php/vod/type/id/{actual_tid}/page/{page}.html"
        html = self._fetch_html(url)
        items = self._parse_list(html)
        pagecount = self._get_pagecount(html)
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        if "detail/id/" in vid or "play/id/" in vid:
            vid = self.extract_id_from_url(vid)
        url = f"{self.base_url}/a/index.php/vod/detail/id/{vid}.html"
        html = self._fetch_html(url)
        return self._parse_detail(html, vid)

    def searchContent(self, key, quick, pg="1"):
        if not key or key.strip() == "":
            return {"list": [], "page": 1}
        page = pg or "1"
        encoded_key = urllib.parse.quote(key)
        url = f"{self.base_url}/a/index.php/vod/search/wd/{encoded_key}/page/{page}.html"
        html = self._fetch_html(url)
        items = self._parse_list(html)
        return {"list": items, "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        if id.startswith("http"):
            play_url = id
        else:
            parts = id.split('/')
            if len(parts) >= 3:
                video_id, sid, nid = parts[0], parts[1], parts[2]
                play_url = f"{self.base_url}/a/index.php/vod/play/id/{video_id}/sid/{sid}/nid/{nid}.html"
            else:
                vid = self.extract_id_from_url(id)
                play_url = f"{self.base_url}/a/index.php/vod/play/id/{vid}/sid/1/nid/1.html"

        html = self._fetch_html(play_url)
        if not html:
            return {"parse": 1, "url": play_url}

        real_url = ""
        match = re.search(r'"url"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
        if match:
            real_url = match.group(1).replace('\\/', '/').replace('\\\\', '\\')

        if not real_url:
            match = re.search(r'(https?://[^\s"]+\.m3u8[^\s"]*)', html)
            if match:
                real_url = match.group(1)

        if real_url:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(real_url),
                "header": self.headers
            }

        iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"', html)
        if iframe_match:
            iframe_url = self.fix_url(iframe_match.group(1))
            return {"parse": 1, "url": iframe_url}

        return {"parse": 1, "url": play_url}

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤 (v3.0)"""
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
        """清洗 m3u8：过滤广告分片 (基于 #EXT-X-KEY 目录匹配)"""
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

    def _parse_list(self, html):
        items = []
        if not html:
            return items

        pattern = r'<a[^>]*class="[^"]*vod-item[^"]*"[^>]*href="([^"]+)"[^>]*>.*?<div[^>]*class="[^"]*vod-thumb[^"]*"[^>]*>.*?<img[^>]*(?:data-original|src)="([^"]+)"[^>]*alt="([^"]*)"[^>]*>.*?</div>.*?<div[^>]*class="[^"]*vod-name[^"]*"[^>]*>([^<]*)</div>'
        matches = re.findall(pattern, html, re.DOTALL)

        for match in matches:
            href, img, alt, name = match
            title = alt if alt and alt.strip() else name
            if not title or not title.strip():
                continue
            vid = self.extract_id_from_url(href)
            items.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": self.fix_url(img),
                "vod_remarks": ""
            })

        if not items:
            pattern2 = r'<a[^>]*href="([^"]*(?:detail|play)[^"]+)"[^>]*>.*?<img[^>]*(?:data-original|src)="([^"]+)"[^>]*(?:alt="([^"]*)")?.*?<div[^>]*class="[^"]*vod-name[^"]*"[^>]*>([^<]*)</div>'
            matches2 = re.findall(pattern2, html, re.DOTALL)
            for match in matches2:
                href, img, alt, name = match
                title = alt if alt and alt.strip() else name
                if not title or not title.strip():
                    continue
                vid = self.extract_id_from_url(href)
                items.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": self.fix_url(img),
                    "vod_remarks": ""
                })

        return items

    def _parse_detail(self, html, vid):
        if not html:
            return {"list": []}

        title = ""
        title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if title_match:
            title = title_match.group(1).strip()
        if not title:
            title_match = re.search(r'<div[^>]*class="[^"]*video-title[^"]*"[^>]*>([^<]+)</div>', html)
            if title_match:
                title = title_match.group(1).strip()
        if not title:
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                title = re.sub(r'\s*[-–]\s*Caosp.*$', '', title_match.group(1).strip())

        pic = ""
        pic_match = re.search(r'<div[^>]*class="[^"]*detail-pic[^"]*"[^>]*>.*?<img[^>]*src="([^"]+)"', html, re.DOTALL)
        if pic_match:
            pic = self.fix_url(pic_match.group(1))
        if not pic:
            pic_match = re.search(r'<img[^>]*class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]+)"', html)
            if pic_match:
                pic = self.fix_url(pic_match.group(1))

        tags = []
        tag_matches = re.findall(r'<span[^>]*>[^<]*(?:精品推荐|高清|无码|有码|字幕|精品|推荐|国产|日本|欧美|亚洲|动漫|萝莉|人妻|乱伦|自拍|主播|网红|偷拍|制服|剧情|巨乳|少女|学生|中文|Cosplay)[^<]*</span>', html)
        for tag in tag_matches:
            clean = re.sub(r'<[^>]+>', '', tag).strip()
            if clean and clean not in tags and len(clean) < 20:
                tags.append(clean)

        play_from = []
        play_url_parts = []

        pos = 0
        while True:
            start = html.find('<div class="play-section"', pos)
            if start == -1:
                start = html.find('<div class="play-section ', pos)
            if start == -1:
                break

            depth = 0
            end = start
            i = start
            while i < len(html):
                if html[i:i+4] == '<div':
                    depth += 1
                    i += 4
                elif html[i:i+6] == '</div>':
                    depth -= 1
                    i += 6
                    if depth == 0:
                        end = i
                        break
                else:
                    i += 1

            if depth != 0:
                break

            section = html[start:end]

            title_match2 = re.search(r'<div[^>]*class="[^"]*section-title[^"]*"[^>]*>(.*?)</div>', section, re.DOTALL)
            if title_match2:
                source_name = title_match2.group(1).strip()
                source_name = re.sub(r'[🍓🥩🎬]', '', source_name).strip()
                if source_name and source_name not in ["", "播放源", "线路"]:
                    play_list_match = re.search(r'<div[^>]*class="[^"]*play-list[^"]*"[^>]*>(.*?)</div>', section, re.DOTALL)
                    if play_list_match:
                        play_links = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', play_list_match.group(1))
                        if play_links:
                            eps = []
                            for link, name in play_links:
                                full_url = self.fix_url(link)
                                eps.append(name.strip() + "$" + full_url)
                            if eps:
                                play_from.append(source_name)
                                play_url_parts.append("#".join(eps))

            pos = end

        if not play_from:
            play_links = re.findall(r'<a[^>]*class="[^"]*play-item[^"]*"[^>]*href="([^"]*play[^"]+)"[^>]*>([^<]+)</a>', html)
            if play_links:
                play_from.append("默认来源")
                eps = []
                for link, name in play_links:
                    full_url = self.fix_url(link)
                    eps.append(name.strip() + "$" + full_url)
                if eps:
                    play_url_parts.append("#".join(eps))
            else:
                play_from = ["默认来源"]
                play_link_match = re.search(r'<a[^>]*href="([^"]*play[^"]*id/' + vid + r'[^"]*)"[^>]*>', html)
                if play_link_match:
                    full_url = self.fix_url(play_link_match.group(1))
                    play_url_parts = ["正片$" + full_url]
                else:
                    play_url_parts = [""]

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title or "未知标题",
                "vod_pic": pic,
                "vod_content": " | ".join(tags) if tags else "",
                "vod_play_from": "$$$".join(play_from) if play_from else "默认来源",
                "vod_play_url": "$$$".join(play_url_parts) if play_url_parts else ""
            }]
        }

    def _get_pagecount(self, html):
        if not html:
            return 1
        page_match = re.search(r'共(\d+)頁', html)
        if not page_match:
            page_match = re.search(r'共(\d+)页', html)
        if page_match:
            return int(page_match.group(1))
        return 1

    def destroy(self):
        pass