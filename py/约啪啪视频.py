# -*- coding: utf-8 -*-
import re
import json
from urllib.parse import urljoin, quote, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://bqqeoc.yppsp2.skin"
        self.classes = [
            {"type_id": "20", "type_name": "日韩"},
            {"type_id": "21", "type_name": "偷拍"},
            {"type_id": "22", "type_name": "无码"},
            {"type_id": "23", "type_name": "自拍"},
            {"type_id": "24", "type_name": "巨乳"},
            {"type_id": "25", "type_name": "华人"},
            {"type_id": "26", "type_name": "嫩模"},
            {"type_id": "27", "type_name": "剧情"},
            {"type_id": "28", "type_name": "动漫"},
            {"type_id": "29", "type_name": "熟女"},
            {"type_id": "30", "type_name": "丝袜"},
            {"type_id": "32", "type_name": "欧美"},
            {"type_id": "33", "type_name": "有码"},
            {"type_id": "34", "type_name": "制服"},
            {"type_id": "35", "type_name": "口交"},
            {"type_id": "31", "type_name": "三级"},
        ]
        self.filters = {}
        for c in self.classes:
            self.filters[c["type_id"]] = []
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }

    def getName(self):
        return "约啪啪视频"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def destroy(self):
        pass

    def _fetch_html(self, url):
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if resp and resp.status_code == 200:
                return resp.text
            return None
        except Exception:
            return None

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return self.host + "/" + url.lstrip("/")

    def _parse_video_items(self, html, limit=999):
        if not html:
            return []
        videos = []
        # 解析分类列表页的视频项
        pattern = r'<div class="post-list-item">.*?<img[^>]*src="([^"]+)"[^>]*class="[^"]*post-image[^"]*"[^>]*>.*?<h3 class="post-title">.*?<a href="([^"]+)"[^>]*>(?:<span>)?([^<]*)(?:</span>)?</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            pic, link, title = match
            if not link or not title:
                continue
            vod_id = self._extract_vod_id(link)
            pic = self._fix_url(pic)
            videos.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": "",
            })
            if len(videos) >= limit:
                break
        # 如果上面的没匹配到，尝试另一种格式
        if not videos:
            pattern2 = r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*post-image[^"]*"[^>]*>\s*<h3 class="post-title">\s*<a href="([^"]+)"[^>]*>([^<]*)</a>'
            matches2 = re.findall(pattern2, html, re.DOTALL)
            for match in matches2:
                pic, link, title = match
                if not link or not title:
                    continue
                vod_id = self._extract_vod_id(link)
                pic = self._fix_url(pic)
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": "",
                })
                if len(videos) >= limit:
                    break
        # 再尝试一种更宽松的匹配
        if not videos:
            pattern3 = r'<div class="post-top">.*?<img[^>]*src="([^"]+)"[^>]*/>.*?<a href="([^"]+)"[^>]*>([^<]*)</a>'
            matches3 = re.findall(pattern3, html, re.DOTALL)
            for match in matches3:
                pic, link, title = match
                if not link or not title:
                    continue
                vod_id = self._extract_vod_id(link)
                pic = self._fix_url(pic)
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": "",
                })
                if len(videos) >= limit:
                    break
        return videos

    def _extract_vod_id(self, url):
        if not url:
            return ""
        # /1135948.html
        m = re.search(r'/(\d+)\.html', url)
        if m:
            return m.group(1)
        return url

    def _get_total_pages(self, html):
        if not html:
            return 1
        
        # 方法1：从尾页链接获取
        m = re.search(r'尾页[^>]*>.*?/(\d+)\.html', html, re.DOTALL)
        if m:
            total = int(m.group(1))
            print(f"从尾页获取总页数: {total}")
            return total
        
        # 方法2：匹配 /vodtype/20-18.html 这种格式（不依赖"尾页"文字）
        m = re.search(r'/(\d+-\d+)\.html["\']?[^>]*>尾页', html)
        if m:
            parts = m.group(1).split('-')
            if len(parts) == 2:
                total = int(parts[1])
                print(f"从尾页链接获取总页数: {total}")
                return total
        
        # 方法3：从 select 中提取最大页码
        m = re.search(r'<select[^>]*>.*?</select>', html, re.DOTALL)
        if m:
            options = re.findall(r'<option[^>]*>第(\d+)页', m.group(0))
            if options:
                total = int(options[-1])
                print(f"从select option获取总页数: {total}")
                return total
        
        # 方法4：匹配 "尾页" 附近的数字
        m = re.search(r'尾页[^<]*</a>', html)
        if m:
            nums = re.findall(r'\d+', m.group(0))
            if nums:
                total = int(nums[-1])
                print(f"从尾页附近数字获取总页数: {total}")
                return total
        
        print("⚠️ 无法获取总页数，默认返回1")
        return 1

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/cn/home/web/")
        if not html:
            return {"list": []}
        # 从首页提取"最近更新"区域或所有视频列表
        videos = []
        # 尝试提取 content-timeline 中的视频
        timeline_pattern = r'<div class="content-timeline">.*?<div class="post-lists">(.*?)</div>'
        timelines = re.findall(timeline_pattern, html, re.DOTALL)
        for tl_html in timelines:
            items = self._parse_video_items(tl_html, 20)
            for item in items:
                if item["vod_id"] and item["vod_name"]:
                    # 去重
                    exist = False
                    for v in videos:
                        if v["vod_id"] == item["vod_id"]:
                            exist = True
                            break
                    if not exist:
                        videos.append(item)
            if len(videos) >= 20:
                break
        if not videos:
            videos = self._parse_video_items(html, 20)
        return {"list": videos[:20]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        if pg == 1:
            url = f"{self.host}/vodtype/{tid}.html"
        else:
            url = f"{self.host}/vodtype/{tid}-{pg}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}
        videos = self._parse_video_items(html)
        total_pages = self._get_total_pages(html)
        return {
            "list": videos,
            "page": pg,
            "pagecount": total_pages,
            "limit": 20,
            "total": total_pages * 20,
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = f"{self.host}/{vod_id}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        # 提取标题
        title = ""
        t = re.search(r'<h1 class="article-title">([^<]*)</h1>', html)
        if t:
            title = t.group(1).strip()
        if not title:
            t = re.search(r'<title>([^<]*)</title>', html)
            if t:
                title = t.group(1).replace(" - 约啪啪视频", "").strip()

        # 提取封面
        pic = ""
        p = re.search(r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*imgPlay[^"]*"', html)
        if p:
            pic = self._fix_url(p.group(1))

        # 提取播放地址
        play_url = ""
        m = re.search(r"rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html)
        if m:
            play_url = m.group(1)
        if not play_url:
            m = re.search(r"url\s*:\s*['\"]([^'\"]+)['\"]", html)
            if m:
                play_url = m.group(1)

        # 提取发布日期
        pub_time = ""
        t = re.search(r'<span class="article-post-date">([^<]*)</span>', html)
        if t:
            pub_time = t.group(1).strip()

        if play_url:
            play_from = "播放"
            play_url_str = f"第1集${play_url}"
        else:
            play_from = "播放"
            play_url_str = f"第1集${vod_id}"

        vod = {
            "vod_id": vod_id,
            "vod_name": title or "未知视频",
            "vod_pic": pic,
            "vod_remarks": pub_time,
            "vod_content": "",
            "vod_play_from": play_from,
            "vod_play_url": play_url_str,
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        if not key:
            return {"list": [], "page": 1, "pagecount": 1, "total": 0}
        pg = int(pg) if pg else 1
        url = f"{self.host}/s/index.html?wd={quote(key)}"
        if pg > 1:
            url += f"&page={pg}"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "total": 0}
        videos = self._parse_video_items(html)
        total_pages = self._get_total_pages(html)
        return {
            "list": videos,
            "page": pg,
            "pagecount": total_pages,
            "limit": 20,
            "total": total_pages * 20,
        }

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {"parse": 1, "url": ""}

        id = id.strip()
        headers = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.host + "/",
        }

        if id.startswith("http"):
            if id.endswith(".m3u8") or id.endswith(".mp4") or ".m3u8?" in id or ".mp4?" in id:
                if id.endswith(".m3u8") or ".m3u8?" in id:
                    return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": headers}
                return {"parse": 0, "url": id, "header": headers}

            # 如果是详情页链接，尝试提取m3u8
            if id.endswith(".html"):
                html = self._fetch_html(id)
                if html:
                    m = re.search(r"rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html)
                    if m:
                        play_url = m.group(1)
                        if play_url:
                            if play_url.endswith(".m3u8") or ".m3u8?" in play_url:
                                return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": headers}
                            return {"parse": 0, "url": play_url, "header": headers}
                    m = re.search(r"url\s*:\s*['\"]([^'\"]+)['\"]", html)
                    if m:
                        play_url = m.group(1)
                        if play_url:
                            if play_url.endswith(".m3u8") or ".m3u8?" in play_url:
                                return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": headers}
                            return {"parse": 0, "url": play_url, "header": headers}

        # 如果id是数字，构造详情页URL再提取
        if re.match(r"^\d+$", id):
            detail_url = f"{self.host}/{id}.html"
            html = self._fetch_html(detail_url)
            if html:
                m = re.search(r"rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html)
                if m:
                    play_url = m.group(1)
                    if play_url:
                        if play_url.endswith(".m3u8") or ".m3u8?" in play_url:
                            return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": headers}
                        return {"parse": 0, "url": play_url, "header": headers}
                m = re.search(r"url\s*:\s*['\"]([^'\"]+)['\"]", html)
                if m:
                    play_url = m.group(1)
                    if play_url:
                        if play_url.endswith(".m3u8") or ".m3u8?" in play_url:
                            return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": headers}
                        return {"parse": 0, "url": play_url, "header": headers}

        return {"parse": 1, "url": id, "header": headers}

    def recommendContent(self, ids, pg=1):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = f"{self.host}/{vod_id}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        videos = []
        # 直接查找 all columns 中的推荐项
        pattern = r'<div class="columns column-2">.*?<article class="post-box">.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h3 class="post-title">([^<]*)</h3>.*?<a href="([^"]+)"[^>]*>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            pic, title, link = match
            if not link or not title:
                continue
            vid = self._extract_vod_id(link)
            pic = self._fix_url(pic)
            if vid and vid != vod_id:  # 排除当前视频
                videos.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": "",
                })
                if len(videos) >= 12:
                    break

        return {"list": videos}

    def localProxy(self, params):
        try:
            target = ""
            if isinstance(params, dict):
                target = params.get("url", "") or params.get("source", "")
            elif isinstance(params, str):
                target = params

            target = unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            headers = {
                "User-Agent": self.headers.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
                "Referer": self.host + "/",
                "Accept": "*/*",
            }

            resp = self.fetch(target, headers=headers, timeout=20)
            if not resp or getattr(resp, "status_code", 0) != 200:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content:
                return [502, "text/plain", b"empty content"]

            if b"#EXTM3U" in content[:256]:
                try:
                    text = content.decode("utf-8", errors="ignore")
                    cleaned = self._clean_m3u8(text, target)
                    return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
                except Exception as e:
                    return [200, "application/vnd.apple.mpegurl", content]

            content_type = "application/octet-stream"
            if target.endswith(".ts"):
                content_type = "video/mp2t"
            elif target.endswith(".m3u8"):
                content_type = "application/vnd.apple.mpegurl"
            elif target.endswith((".jpg", ".jpeg")):
                content_type = "image/jpeg"
            elif target.endswith(".png"):
                content_type = "image/png"
            elif target.endswith(".mp4"):
                content_type = "video/mp4"
            elif target.endswith(".key") or target.endswith(".bin"):
                content_type = "application/octet-stream"

            return [200, content_type, content]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]

    def _m3u8_proxy_url(self, url):
        if not url:
            return ""
        encoded = quote(str(url), safe="")
        proxy_base = self.getProxyUrl()
        if '?' in proxy_base:
            if proxy_base.endswith('&') or proxy_base.endswith('?'):
                proxy_url = proxy_base + "url=" + encoded
            else:
                proxy_url = proxy_base + "&url=" + encoded
        else:
            proxy_url = proxy_base + "?url=" + encoded
        return proxy_url

    def _clean_m3u8_single(self, lines, source_url):
        result = []
        pending_extinf = []
        removed = 0
        total = 0
        skip_until_discontinuity = False
        in_ad_segment = False

        print("=== _clean_m3u8_single 开始 ===")
        print(f"总行数: {len(lines)}")

        i = 0
        while i < len(lines):
            line = lines[i]

            # 检测到 METHOD=NONE 且没有 URI 的 KEY，标记为广告段
            if line.startswith("#EXT-X-KEY:METHOD=NONE"):
                in_ad_segment = True
                print("🔴 检测到无加密段 (广告)")
                result.append(line)
                i += 1
                continue

            # 检测到 DISCONTINUITY，结束广告段
            if line.startswith("#EXT-X-DISCONTINUITY"):
                if in_ad_segment:
                    print("🔴 广告段结束 (DISCONTINUITY)")
                    in_ad_segment = False
                result.append(line)
                i += 1
                continue

            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                line = self._rewrite_m3u8_tag(line, source_url)
                result.append(line)
                i += 1
                continue

            if line.startswith("#EXTINF"):
                pending_extinf = [line]
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.startswith("#"):
                        pending_extinf.append(next_line)
                        i += 1
                    else:
                        media_url = urljoin(source_url, next_line)
                        total += 1

                        # 如果在广告段内，过滤该分片
                        if in_ad_segment:
                            removed += 1
                            print(f"❌ 过滤广告分片 #{total}: {media_url}")
                        else:
                            result.extend(pending_extinf)
                            result.append(media_url)
                        i += 1
                        break
                continue

            result.append(line)
            i += 1

        print(f"📊 总分片: {total}, 过滤: {removed}")
        if removed:
            print(f"✅ m3u8已过滤广告分片: {removed}个")

        return "\n".join(result) + "\n"

    def _clean_m3u8_multi(self, lines, source_url):
        out = []
        for line in lines:
            if line.startswith("#"):
                out.append(line)
            else:
                child_url = urljoin(source_url, line)
                out.append(self._m3u8_proxy_url(child_url))
        return "\n".join(out) + "\n"

    def _clean_m3u8(self, text, source_url):
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        is_multi = any(line.startswith("#EXT-X-STREAM-INF") for line in lines)

        if is_multi:
            return self._clean_m3u8_multi(lines, source_url)
        else:
            return self._clean_m3u8_single(lines, source_url)

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
