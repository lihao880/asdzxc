# -*- coding: utf-8 -*-
import re
import json
from urllib.parse import urljoin, quote, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://dtu.hdmm3.casa"
        self.base_path = "/cn/home/web/index.php/vod"
        self.classes = [
            {"type_id": "20", "type_name": "自拍偷拍"},
            {"type_id": "21", "type_name": "巨乳波霸"},
            {"type_id": "22", "type_name": "强奸乱伦"},
            {"type_id": "23", "type_name": "人妻熟女"},
            {"type_id": "24", "type_name": "制服丝袜"},
            {"type_id": "25", "type_name": "花季少女"},
            {"type_id": "26", "type_name": "无码露毛"},
            {"type_id": "27", "type_name": "群P多人"},
            {"type_id": "28", "type_name": "人兽人妖"},
            {"type_id": "29", "type_name": "男同女同"},
            {"type_id": "30", "type_name": "韩日专区"},
            {"type_id": "31", "type_name": "欧美色情"},
            {"type_id": "32", "type_name": "成人动漫"},
            {"type_id": "33", "type_name": "三级剧情"},
        ]
        self.filters = {}
        for c in self.classes:
            self.filters[c["type_id"]] = []
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }

    def getName(self):
        return "黑洞秘密"

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
        pattern = r'<div class="video-play[^>]*>.*?<a href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*/>.*?<p class="title-p">.*?<a[^>]*>([^<]*)</a>.*?<p class="time">.*?<span class="fl">.*?<i class="ls">发布</i>([^<]*)</span>.*?<span class="fr">.*?<i class="ls">观看</i>([^<]*)</span>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            link, pic, title, pub_date, views = match
            if not link or not title:
                continue
            vod_id = self._extract_vod_id(link)
            pic = self._fix_url(pic)
            videos.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": pub_date.strip() if pub_date else "",
            })
            if len(videos) >= limit:
                break
        if not videos:
            item_pattern = r'<div class="video-play[^>]*>.*?<a href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*/>.*?<p class="title-p">[^<]*<a[^>]*>([^<]*)</a>'
            item_matches = re.findall(item_pattern, html, re.DOTALL)
            for match in item_matches:
                link, pic, title = match
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
        m = re.search(r'/play/id/(\d+)', url)
        if m:
            return m.group(1)
        m = re.search(r'/detail/id/(\d+)', url)
        if m:
            return m.group(1)
        return url

    def _get_total_pages(self, html):
        if not html:
            return 1
        m = re.search(r'data-total="(\d+)"', html)
        if m:
            return int(m.group(1))
        m = re.search(r'尾页.*?page/(\d+)\.html', html, re.DOTALL)
        if m:
            return int(m.group(1))
        return 1

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/cn/home/web/")
        if not html:
            return {"list": []}
        week_pattern = r'<h2 class="left-title">最近一周热播视频</h2>.*?<div class="video-box clearfix">(.*?)</div>'
        m = re.search(week_pattern, html, re.DOTALL)
        if m:
            section_html = m.group(1)
            items = self._parse_video_items(section_html, 20)
            if items:
                return {"list": items}
        items = self._parse_video_items(html, 20)
        return {"list": items}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        url = f"{self.host}/cn/home/web/index.php/vod/type/id/{tid}/page/{pg}.html"
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
        url = f"{self.host}/cn/home/web/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        title = ""
        t = re.search(r'<div id="player_line"[^>]*>.*?<li>([^<]*)</li>', html, re.DOTALL)
        if t:
            title = t.group(1).strip()
        if not title:
            t = re.search(r'<title>([^<]*)</title>', html)
            if t:
                title = t.group(1).replace(" - 黑洞秘密", "").strip()

        pic = ""
        p = re.search(r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*poster[^"]*"', html, re.DOTALL)
        if p:
            pic = self._fix_url(p.group(1))
        if not pic:
            p = re.search(r'<div class="play-pic"[^>]*>.*?<img[^>]*src="([^"]+)"', html, re.DOTALL)
            if p:
                pic = self._fix_url(p.group(1))

        play_url = ""
        m = re.search(r'player_data\s*=\s*({[^}]+})', html)
        if m:
            try:
                data = json.loads(m.group(1))
                play_url = data.get("url", "")
            except:
                pass
        if not play_url:
            m = re.search(r'url\s*:\s*"([^"]+)"', html)
            if m:
                play_url = m.group(1)
        if not play_url:
            m = re.search(r'videoSrc\s*=\s*["\']([^"\']+)["\']', html)
            if m:
                play_url = m.group(1)
        if play_url and play_url.startswith("/"):
            play_url = self.host + play_url

        content = ""
        c = re.search(r'<div class="video-mes">.*?<p[^>]*>([^<]*)</p>', html, re.DOTALL)
        if c:
            content = c.group(1).strip()

        pub_time = ""
        t = re.search(r'发布时间：([^<]*)</p>', html)
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
            "vod_content": content,
            "vod_play_from": play_from,
            "vod_play_url": play_url_str,
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        if not key:
            return {"list": [], "page": 1, "pagecount": 1, "total": 0}
        pg = int(pg) if pg else 1
        url = f"{self.host}/cn/home/web/index.php/vod/search.html?wd={quote(key)}&page={pg}"
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

            if "/play/id/" in id:
                html = self._fetch_html(id)
                if html:
                    m = re.search(r'player_data\s*=\s*({[^}]+})', html)
                    if m:
                        try:
                            data = json.loads(m.group(1))
                            play_url = data.get("url", "")
                            if play_url and (play_url.endswith(".m3u8") or play_url.endswith(".mp4")):
                                if play_url.startswith("/"):
                                    play_url = self.host + play_url
                                if play_url.endswith(".m3u8") or ".m3u8?" in play_url:
                                    return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": headers}
                                return {"parse": 0, "url": play_url, "header": headers}
                        except:
                            pass
                    m = re.search(r'url\s*:\s*"([^"]+)"', html)
                    if m:
                        play_url = m.group(1)
                        if play_url and (play_url.endswith(".m3u8") or play_url.endswith(".mp4")):
                            if play_url.startswith("/"):
                                play_url = self.host + play_url
                            if play_url.endswith(".m3u8") or ".m3u8?" in play_url:
                                return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": headers}
                            return {"parse": 0, "url": play_url, "header": headers}

        if re.match(r"^\d+$", id):
            play_page_url = f"{self.host}/cn/home/web/index.php/vod/play/id/{id}/sid/1/nid/1.html"
            html = self._fetch_html(play_page_url)
            if html:
                m = re.search(r'player_data\s*=\s*({[^}]+})', html)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        play_url = data.get("url", "")
                        if play_url:
                            if play_url.startswith("/"):
                                play_url = self.host + play_url
                            if play_url.endswith(".m3u8") or ".m3u8?" in play_url:
                                return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": headers}
                            return {"parse": 0, "url": play_url, "header": headers}
                    except:
                        pass
                m = re.search(r'url\s*:\s*"([^"]+)"', html)
                if m:
                    play_url = m.group(1)
                    if play_url:
                        if play_url.startswith("/"):
                            play_url = self.host + play_url
                        if play_url.endswith(".m3u8") or ".m3u8?" in play_url:
                            return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": headers}
                        return {"parse": 0, "url": play_url, "header": headers}

        return {"parse": 1, "url": id, "header": headers}

    def recommendContent(self, ids, pg=1):
        return {"list": []}

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

    def localProxy(self, params):
        print("=== localProxy 被调用 ===")
        print(f"params: {params}")
        import sys
        sys.stdout.flush()
        try:
            target = ""
            if isinstance(params, dict):
                target = params.get("url", "") or params.get("source", "")
            elif isinstance(params, str):
                target = params

            print(f"原始 target: {target}")
            sys.stdout.flush()

            target = unquote(str(target or ""))

            print(f"解码后 target: {target}")
            sys.stdout.flush()

            if not target or not re.match(r"^https?://", target, re.I):
                print("❌ 无效 URL")
                sys.stdout.flush()
                return [400, "text/plain", b"invalid url"]

            headers = {
                "User-Agent": self.headers.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
                "Referer": self.host + "/",
                "Accept": "*/*",
            }

            print(f"开始 fetch: {target}")
            sys.stdout.flush()

            resp = self.fetch(target, headers=headers, timeout=20)
            if not resp or getattr(resp, "status_code", 0) != 200:
                print(f"❌ fetch 失败: {resp}")
                sys.stdout.flush()
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            print(f"响应内容长度: {len(content)}")
            sys.stdout.flush()

            if not content:
                return [502, "text/plain", b"empty content"]

            if b"#EXTM3U" in content[:256]:
                print("✅ 检测到 m3u8，开始过滤")
                sys.stdout.flush()
                try:
                    text = content.decode("utf-8", errors="ignore")
                    cleaned = self._clean_m3u8(text, target)
                    print(f"过滤完成，输出 {len(cleaned)} 字节")
                    sys.stdout.flush()
                    return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
                except Exception as e:
                    print(f"❌ 过滤失败: {e}")
                    sys.stdout.flush()
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

            print(f"返回非 m3u8 内容: {content_type}")
            sys.stdout.flush()
            return [200, content_type, content]

        except Exception as e:
            print(f"❌ localProxy 异常: {e}")
            sys.stdout.flush()
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]

    def _clean_m3u8_single(self, lines, source_url):
        result = []
        pending_extinf = []
        removed = 0
        segment_count = 0
        skip_first = 8  # 跳过前8个分片（片头广告约7-10秒）

        ad_dirs = [
            '8371f2d8ca1f9e25',
        ]

        i = 0
        while i < len(lines):
            line = lines[i]

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
                        is_ad = False

                        for ad_dir in ad_dirs:
                            if ad_dir in media_url:
                                is_ad = True
                                break

                        segment_count += 1
                        if segment_count <= skip_first:
                            is_ad = True
                            print(f"⏭️ 跳过片头分片 #{segment_count}: {media_url}")

                        if is_ad:
                            removed += 1
                        else:
                            if media_url.endswith('.jpg'):
                                media_url = media_url[:-4] + '.ts'
                            result.extend(pending_extinf)
                            result.append(media_url)
                        i += 1
                        break
                continue

            result.append(line)
            i += 1

        if removed:
            print(f"m3u8已过滤广告/片头分片: {removed}个")

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