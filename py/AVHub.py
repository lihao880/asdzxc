# coding: utf-8
"""
AVHub 爬虫源 - 直链播放版
站点: https://avhub360.com/
"""

import json
import re
import base64
import urllib.parse
from base.spider import Spider as BaseSpider

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except ImportError:
    AES = None
    unpad = None


class Spider(BaseSpider):
    def getName(self):
        return "AVHub"

    def init(self, extend=""):
        self.host = "https://avhub360.com"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host + "/",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }

        key_str = "102_53_100_57_54_53_100_102_55_53_51_51_54_50_55_48"
        key_chars = "".join(chr(int(c)) for c in key_str.split("_"))
        self.img_key = key_chars.encode("utf-8")

        iv_str = "57_55_98_54_48_51_57_52_97_98_99_50_102_98_101_49"
        iv_chars = "".join(chr(int(c)) for c in iv_str.split("_"))
        self.img_iv = iv_chars.encode("utf-8")

        self.classes = [
            {"type_id": "new", "type_name": "新作"},
            {"type_id": "theme_3", "type_name": "中文字幕"},
            {"type_id": "theme_11", "type_name": "高清无码"},
            {"type_id": "theme", "type_name": "主题"},
            {"type_id": "actress", "type_name": "女优"},
            {"type_id": "popular", "type_name": "东京热"},
            {"type_id": "tags_206", "type_name": "时间停止"},
            {"type_id": "movie", "type_name": "AV精选"},
        ]
        self.filters = {}

    def getDependence(self):
        return []

    def destroy(self):
        pass

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        if not url.startswith("http"):
            return self.host + "/" + url.lstrip("/")
        return url

    def _build_proxy_pic(self, pic_url):
        if not pic_url:
            return ""
        clean_url = pic_url.replace("pics://", "https://")
        img_b64 = base64.b64encode(clean_url.encode()).decode('utf-8')
        return f"proxy://do=py&site={self.getName()}&type=img&url={img_b64}"

    def _extract_videos(self, html):
        videos = []
        seen = set()

        pattern = r'<div[^>]*class="[^"]*video-img-box[^"]*"[^>]*>(.*?)</div>\s*</div>'
        cards = re.findall(pattern, html, re.DOTALL)

        for card in cards:
            try:
                a_match = re.search(r'<a href="([^"]+)"', card)
                if not a_match:
                    continue
                href = a_match.group(1)

                if any(x in href for x in ["taokju", "ggrzw", "xyxcpa1", "http://", "https://"]):
                    continue

                vid = href.strip("/").split("/")[-1]
                if not vid or vid in seen:
                    continue
                seen.add(vid)

                img_match = re.search(r'<img[^>]+z-image-loader-url="([^"]+)"', card)
                if not img_match:
                    img_match = re.search(r'<img[^>]+data-src="([^"]+)"', card)
                if not img_match:
                    img_match = re.search(r'<img[^>]+src="([^"]+)"', card)
                if not img_match:
                    continue

                pic = self._fix_url(img_match.group(1))
                if not pic or "assets/images" in pic or "notice_close" in pic:
                    continue
                pic = self._build_proxy_pic(pic)

                title = ""
                title_match = re.search(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>\s*<a[^>]*>\s*(.*?)\s*</a>', card, re.DOTALL)
                if title_match:
                    title = re.sub(r'\s+', ' ', title_match.group(1).strip())
                if not title:
                    alt_match = re.search(r'alt="([^"]*)"', card)
                    if alt_match:
                        title = alt_match.group(1).strip()
                if not title:
                    title = vid

                if "广告" in title or "PG" in title or "开元" in title:
                    continue
                if len(title) < 2:
                    continue

                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "",
                })
            except:
                continue

        return videos

    def _get_play_url_from_player_aaaa(self, html):
        """从 player_aaaa 提取播放地址"""
        match = re.search(r'var\s+player_aaaa\s*=\s*({.*?});', html, re.DOTALL)
        if not match:
            return None
        try:
            s = match.group(1)
            depth, start = 0, 0
            for i, ch in enumerate(s):
                if ch == "{":
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        s = s[start:i+1]
                        break
            data = json.loads(s)
            url = data.get("url", "")
            if url:
                enc = data.get("encrypt", 0)
                if enc == 1:
                    url = urllib.parse.unquote(url)
                elif enc == 2:
                    try:
                        url = base64.b64decode(url).decode("utf-8", errors="ignore")
                    except:
                        pass
                elif enc == 3:
                    try:
                        url = bytes.fromhex(url).decode("utf-8", errors="ignore")
                    except:
                        pass
                return url
        except:
            pass
        return None

    def _extract_m3u8_from_html(self, html):
        """从HTML中提取m3u8地址"""
        # 多种模式匹配 m3u8
        patterns = [
            r'(https?://[^"\'\s<>]+\.m3u8[^"\'\s<>]*)',
            r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"',
            r'"src"\s*:\s*"([^"]+\.m3u8[^"]*)"',
            r'<source[^>]+src="([^"]+\.m3u8[^"]*)"',
            r'video[^>]+src="([^"]+\.m3u8[^"]*)"',
            r'now\s*=\s*"([^"]+\.m3u8[^"]*)"',
            r'playUrl\s*[:=]\s*"([^"]+\.m3u8[^"]*)"',
            r'MacPlayer\.PlayUrl\s*=\s*"([^"]+)"',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for url in matches:
                if url and ".m3u8" in url:
                    # 清理可能的转义字符
                    url = url.replace("\\/", "/")
                    return url
        return None

    def _get_play_url(self, html, page_url):
        """多级提取播放地址"""
        # 1. 从 player_aaaa 提取
        url = self._get_play_url_from_player_aaaa(html)
        if url and (".m3u8" in url or ".mp4" in url):
            return url

        # 2. 从 HTML 中提取 m3u8
        url = self._extract_m3u8_from_html(html)
        if url:
            return url

        # 3. 如果有 iframe，递归解析
        iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', html)
        if iframe_match:
            iframe_url = self._fix_url(iframe_match.group(1))
            try:
                resp = self.fetch(iframe_url, headers=self.headers, timeout=10)
                html2 = resp.content.decode("utf-8", errors="ignore")
                url = self._extract_m3u8_from_html(html2)
                if url:
                    return url
            except:
                pass

        return None

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            resp = self.fetch(self.host + "/", headers=self.headers, timeout=10)
            html = resp.content.decode("utf-8", errors="ignore")
            videos = self._extract_videos(html)
            return {"list": videos[:20]}
        except Exception as e:
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = int(pg) if pg else 1

        if tid == "new":
            base_url = self.host + "/new"
        elif tid == "theme":
            base_url = self.host + "/theme"
        elif tid == "actress":
            base_url = self.host + "/actress"
        elif tid == "popular":
            base_url = self.host + "/popular"
        elif tid == "movie":
            base_url = self.host + "/movie"
        elif tid.startswith("theme_"):
            base_url = self.host + "/theme/detail/" + tid.replace("theme_", "")
        elif tid.startswith("tags_"):
            base_url = self.host + "/tags/" + tid.replace("tags_", "")
        else:
            base_url = self.host + "/"

        if page > 1:
            url = base_url.rstrip("/") + "/" + str(page)
        else:
            url = base_url

        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            html = resp.content.decode("utf-8", errors="ignore")
            videos = self._extract_videos(html)

            page_count = 10
            pages = re.findall(r'<a[^>]*href="[^"]*/(\d+)"[^>]*>', html)
            if pages:
                page_count = max(int(p) for p in pages)

            return {
                "list": videos,
                "page": page,
                "pagecount": page_count,
                "limit": 20,
                "total": len(videos) * page_count
            }
        except Exception as e:
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        vid = str(ids[0])
        url = self.host + "/videos/" + vid
        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            html = resp.content.decode("utf-8", errors="ignore")

            title = vid
            og_title = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
            if og_title:
                title = og_title.group(1).strip()
                title = re.sub(r'\s*[-|]\s*AVHub$', '', title).strip()
            else:
                h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
                if h1_match:
                    title = re.sub(r'\s+', ' ', h1_match.group(1).strip())
                else:
                    tm = re.search(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>\s*<a[^>]*>\s*(.*?)\s*</a>', html, re.DOTALL)
                    if tm:
                        title = re.sub(r'\s+', ' ', tm.group(1).strip())

            pic = ""
            pm = re.search(r'<img[^>]+class="[^"]*zximg[^"]*"[^>]+z-image-loader-url="([^"]+)"', html)
            if pm:
                pic = self._fix_url(pm.group(1))
            if pic and ("assets/images" in pic or "notice_close" in pic):
                pic = ""
            pic = self._build_proxy_pic(pic)

            content = ""
            cm = re.search(r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>(.*?)</p>', html, re.DOTALL)
            if cm:
                content = re.sub(r'<[^>]+>', '', cm.group(1)).strip()
            if not content:
                desc_match = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html)
                if desc_match:
                    content = desc_match.group(1).strip()

            # 尝试提取播放地址（直链）
            play_url = self._get_play_url(html, url)

            if play_url and (".m3u8" in play_url or ".mp4" in play_url):
                play_url_str = "第1集$" + play_url
            else:
                # 没有直链，传详情页URL让playerContent处理
                play_url_str = "第1集$" + url

            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": content,
                "vod_remarks": "",
                "vod_play_from": "播放",
                "vod_play_url": play_url_str
            }
            return {"list": [vod]}
        except Exception as e:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key.encode("utf-8"))
        url = self.host + "/search/" + keyword
        if page > 1:
            url = url + "/" + str(page)
        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            html = resp.content.decode("utf-8", errors="ignore")
            videos = self._extract_videos(html)
            return {"list": videos, "pagecount": 5}
        except:
            return {"list": [], "pagecount": 1}

    def playerContent(self, flag, id, vipFlags):
        """播放 - 优先返回直链"""
        # 如果已经是 m3u8/mp4 直链
        if id and (".m3u8" in id or ".mp4" in id):
            if id.startswith("http"):
                return {"parse": 0, "url": id, "header": self.headers}
            if id.startswith("/"):
                return {"parse": 0, "url": self.host + id, "header": self.headers}

        # 尝试从播放页提取直链
        if id.startswith("http"):
            try:
                resp = self.fetch(id, headers=self.headers, timeout=10)
                html = resp.content.decode("utf-8", errors="ignore")

                play_url = self._get_play_url(html, id)

                if play_url and (".m3u8" in play_url or ".mp4" in play_url):
                    # 补全URL
                    if play_url.startswith("/"):
                        play_url = self.host + play_url
                    return {"parse": 0, "url": play_url, "header": self.headers}
            except Exception as e:
                self.log({"action": "playerContent_error", "error": str(e)})

        # 没有提取到直链，降级嗅探
        return {"parse": 1, "url": id, "header": self.headers}

    def localProxy(self, params):
        if params.get('type') != 'img':
            return [404, "text/plain", b""]

        try:
            img_url = base64.b64decode(params.get('url')).decode('utf-8')
            img_headers = self.headers.copy()
            img_headers['Accept'] = 'image/avif,image/webp,image/*,*/*;q=0.8'

            resp = self.fetch(img_url, headers=img_headers, timeout=10)
            raw_data = resp.content

            if raw_data.startswith(b'\xff\xd8') or raw_data.startswith(b'\x89PNG') or raw_data.startswith(b'GIF8'):
                mime = "image/jpeg" if raw_data.startswith(b'\xff\xd8') else ("image/png" if raw_data.startswith(b'\x89PNG') else "image/gif")
                return [200, mime, raw_data]
            if raw_data[:20] and b'WEBP' in raw_data[:20]:
                return [200, "image/webp", raw_data]

            if AES is not None:
                try:
                    cipher = AES.new(self.img_key, AES.MODE_CBC, self.img_iv)
                    decrypted = cipher.decrypt(raw_data)
                    try:
                        decrypted = unpad(decrypted, AES.block_size)
                    except:
                        pass

                    mime = "image/jpeg"
                    if decrypted.startswith(b'\x89PNG'):
                        mime = "image/png"
                    elif decrypted.startswith(b'GIF8'):
                        mime = "image/gif"
                    elif decrypted.startswith(b'RIFF') and b'WEBP' in decrypted[8:12]:
                        mime = "image/webp"

                    return [200, mime, decrypted]
                except:
                    pass

            return [200, "image/jpeg", raw_data]
        except Exception as e:
            return [404, "text/plain", b""]