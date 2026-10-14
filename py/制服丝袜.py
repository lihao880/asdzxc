# -*- coding: utf-8 -*-
"""
站点名称: 制服丝袜
主域名: https://zhifsiwi.cc/
备用域名: https://xxvv1.tw (页面标注)
内容类型: 成人影视聚合站（制服/丝袜向）
最后验证: 2026-08-31
"""
import re
import json
from urllib.parse import urljoin, quote, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://zhifsiwi.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }
        self.classes = [
            {"type_id": "cate18", "type_name": "会员定制"},
            {"type_id": "cate19", "type_name": "Stripchat"},
            {"type_id": "cate20", "type_name": "SWAG订阅"},
            {"type_id": "cate22", "type_name": "推荐"},
            {"type_id": "cate23", "type_name": "黑料吃瓜"},
            {"type_id": "cate24", "type_name": "乱伦"},
            {"type_id": "cate25", "type_name": "福利姬"},
            {"type_id": "cate26", "type_name": "网黄"},
            {"type_id": "cate27", "type_name": "探花"},
            {"type_id": "cate28", "type_name": "主播"},
            {"type_id": "cate29", "type_name": "SM调教"},
            {"type_id": "cate30", "type_name": "偷拍"},
            {"type_id": "cate31", "type_name": "明星换脸"},
            {"type_id": "cate32", "type_name": "迷奸强奸"},
            {"type_id": "cate33", "type_name": "重口猎奇"},
            {"type_id": "cate34", "type_name": "绿帽"},
            {"type_id": "cate35", "type_name": "TS人妖"},
            {"type_id": "cate36", "type_name": "同性恋"},
            {"type_id": "cate38", "type_name": "日韩精选"},
            {"type_id": "cate39", "type_name": "中文字幕"},
            {"type_id": "cate40", "type_name": "AV解说"},
            {"type_id": "cate41", "type_name": "FC2无码"},
            {"type_id": "cate42", "type_name": "素人AV"},
            {"type_id": "cate43", "type_name": "欧美色情"},
        ]
        self.filters = {}
        self.backup_hosts = [
            "https://xxvv1.tw",
            "https://zhifsiwi.cc",
        ]

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy?do=py"

    def getName(self):
        return "制服丝袜"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def _get_host(self):
        for host in self.backup_hosts:
            try:
                resp = self.fetch(host + "/", headers=self.headers, timeout=5)
                if resp and resp.status_code == 200:
                    return host
            except Exception:
                continue
        return self.host

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

    def _fix_url(self, url):
        if not url:
            return ''
        url = url.strip()
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host.rstrip('/') + url
        return self.host.rstrip('/') + '/' + url.lstrip('/')

    def _extract_video_id(self, href):
        if not href:
            return ''
        m = re.search(r'/video/(\d+)/', href)
        if m:
            return m.group(1)
        return ''

    def _parse_video_list(self, html):
        videos = []
        cdn_domain = "https://d32bg2g0w9aqg4.cloudfront.net"
        cdn_match = re.search(r'https://([^/]+\.cloudfront\.net)', html)
        if cdn_match:
            cdn_domain = "https://" + cdn_match.group(1)
        
        # 使用更宽松的匹配方式：先找到所有 li 卡片，再逐个解析
        li_pattern = r'<li[^>]*class="[^"]*tp4-section-content__item[^"]*"[^>]*>(.*?)</li>'
        li_matches = re.findall(li_pattern, html, re.DOTALL)
        
        for li_html in li_matches:
            # 跳过广告卡片（包含 tp4-module-ad）
            if 'tp4-module-ad' in li_html:
                continue
            # 提取 href
            href_match = re.search(r'<a[^>]*href="([^"]+)"', li_html)
            if not href_match:
                continue
            href = href_match.group(1)
            vid = self._extract_video_id(href)
            if not vid:
                continue
            # 提取标题
            title_match = re.search(r'<h3[^>]*class="[^"]*text-truncate[^"]*"[^>]*>([^<]+)</h3>', li_html)
            if not title_match:
                continue
            title = title_match.group(1).strip()
            if not title:
                continue
            # 提取图片
            pic_match = re.search(r'<img[^>]*data-src="([^"]+)"', li_html)
            pic = pic_match.group(1).strip() if pic_match else ""
            if pic and not pic.startswith('http'):
                pic = cdn_domain + pic if pic.startswith('/') else cdn_domain + '/' + pic
            elif pic and pic.startswith('//'):
                pic = 'https:' + pic
            # 提取观看量
            views_match = re.search(r'<span[^>]*class="[^"]*tp4-eye[^"]*"[^>]*>([^<]*)</span>', li_html)
            views = views_match.group(1).strip() if views_match else ""
            # 提取 data-plink
            plink_match = re.search(r'<div[^>]*class="[^"]*tp4-item-preview[^"]*"[^>]*data-plink="([^"]+)"', li_html)
            plink_full = ""
            if plink_match:
                plink = plink_match.group(1)
                if plink.startswith('/'):
                    plink_full = cdn_domain + plink
                elif plink.startswith('//'):
                    plink_full = 'https:' + plink
                else:
                    plink_full = plink
            encoded_vid = f"{vid}|$|{plink_full}" if plink_full else vid
            videos.append({
                'vod_id': encoded_vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': views,
            })
        return videos
    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            url = self.host + "/"
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            videos = self._parse_video_list(html)
            return {"list": videos[:20]}
        except Exception as e:
            self.log({"action": "homeVideoContent_error", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        """分类列表 - 单页模式"""
        try:
            pg = int(pg) if pg else 1
            
            if pg == 1:
                url = f"{self.host}/category/{tid}/"
            else:
                url = f"{self.host}/category/{tid}/{pg}/"

            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

            html = resp.text
            videos = self._parse_video_list(html)

            # 提取分页信息
            pagecount = 1
            total = 999
            page_links = re.findall(r'/category/[^/]+/(\d+)/', html)
            if page_links:
                page_nums = [int(p) for p in page_links if p.isdigit()]
                if page_nums:
                    pagecount = max(page_nums) + 1

            return {
                "list": videos,
                "page": pg,
                "pagecount": pagecount,
                "limit": 20,
                "total": total,
            }
        except Exception as e:
            self.log({"action": "categoryContent_error", "tid": tid, "pg": pg, "error": str(e)})
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        raw = ids[0]
        vid = raw
        play_url = ""
        if '|$|' in raw:
            parts = raw.split('|$|', 1)
            vid = parts[0]
            play_url = parts[1] if len(parts) > 1 else ""
        try:
            url = f"{self.host}/video/{vid}/"
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text

            # 提取 __ARCHIVE_PLAYER__
            player_match = re.search(r'window\.__ARCHIVE_PLAYER__\s*=\s*({[^;]+});', html)
            if player_match:
                try:
                    player_data = json.loads(player_match.group(1))
                    cdn_line = player_data.get('cdnLine', 'https://d32bg2g0w9aqg4.cloudfront.net')
                    raw_path = player_data.get('rawPath', '')
                    if raw_path:
                        play_url = cdn_line.rstrip('/') + raw_path
                except:
                    pass

            title = ""
            og_title = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
            if og_title:
                title = og_title.group(1).strip()
            if not title:
                title_match = re.search(r'<title>([^<]+)</title>', html)
                if title_match:
                    title = title_match.group(1).strip()
                    title = title.replace(' - 制服丝袜', '').replace('制服丝袜｜', '')

            pic = ""
            pic_match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
            if pic_match:
                pic = pic_match.group(1).strip()

            desc = ""
            desc_match = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', html)
            if desc_match:
                desc = desc_match.group(1).strip()

            if play_url:
                play_url_str = f"播放${play_url}"
            elif raw and '|$|' in raw:
                parts = raw.split('|$|', 1)
                if len(parts) > 1 and parts[1]:
                    play_url_str = f"播放${parts[1]}"
                else:
                    play_url_str = f"播放${vid}"
            else:
                play_url_str = f"播放${vid}"

            data = {
                "vod_id": vid,
                "vod_name": title or "未知视频",
                "vod_pic": pic,
                "vod_content": desc,
                "vod_play_from": "播放",
                "vod_play_url": play_url_str,
            }
            return {"list": [data]}

        except Exception as e:
            self.log({"action": "detailContent_error", "vid": vid, "error": str(e)})

        if raw and '|$|' in raw:
            parts = raw.split('|$|', 1)
            if len(parts) > 1 and parts[1]:
                play_url = parts[1]
                data = {
                    "vod_id": vid,
                    "vod_name": "视频详情",
                    "vod_pic": "",
                    "vod_content": "",
                    "vod_play_from": "播放",
                    "vod_play_url": f"播放${play_url}",
                }
                return {"list": [data]}

        return {"list": [{"vod_id": vid, "vod_name": "未知视频", "vod_pic": "", "vod_content": "", "vod_play_from": "播放", "vod_play_url": f"播放${vid}"}]}

    def searchContent(self, key, quick=False, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        try:
            pg = int(pg) if pg else 1
            if pg == 1:
                url = f"{self.host}/search/{quote(key)}/"
            else:
                url = f"{self.host}/search/{quote(key)}/{pg}/"

            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": pg}

            html = resp.text
            videos = self._parse_video_list(html)

            return {"list": videos, "page": pg}
        except Exception as e:
            self.log({"action": "searchContent_error", "key": key, "error": str(e)})
            return {"list": [], "page": 1}

    def _m3u8_proxy_url(self, url):
        if not url:
            return ""
        proxy_base = self.getProxyUrl()
        if "?" in proxy_base:
            return proxy_base + "&url=" + quote(str(url), safe="")
        else:
            return proxy_base + "?url=" + quote(str(url), safe="")

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {"parse": 1, "url": ""}

        if id.startswith("http") and (".m3u8" in id.lower() or ".mp4" in id.lower()):
            return {
                "parse": 0,
                "url": id,
                "header": {"User-Agent": self.headers["User-Agent"]},
            }

        if not id.startswith("http"):
            return {"parse": 1, "url": f"{self.host}/video/{id}/", "header": self.headers}

        return {"parse": 1, "url": id, "header": self.headers}

    def _is_fake_image_stream(self, text, source_url):
        low_url = (source_url or "").lower()
        for sig in ("doyinapi", "svip", "imgcdn", "photo"):
            if sig in low_url:
                return True
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower().split("?")[0]
            if low.endswith((".png", ".jpg", ".jpeg", ".webp")):
                return True
        return False

    def _resolve_main_dir(self, lines, source_url):
        import posixpath
        from urllib.parse import urlparse, urljoin

        parsed = urlparse(source_url)
        main_dir = posixpath.dirname(parsed.path)
        if not main_dir.endswith("/"):
            main_dir += "/"

        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            key_path = urlparse(
                key_uri if key_uri.startswith("http") else urljoin(source_url, key_uri)
            ).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return main_dir

    def _rewrite_m3u8_tag(self, line, source_url):
        from urllib.parse import urljoin
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

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        if self._is_fake_image_stream(text, source_url):
            restored = text
            for ext in (".png", ".jpeg", ".jpg", ".webp"):
                restored = restored.replace(ext, ".ts")
            self.log("检测到图片流伪装，已还原扩展名 -> .ts，跳过广告过滤")
            return restored

        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = self._fix_url(line) if line.startswith("http") else self._m3u8_proxy_url(line)
                    out.append(child)
            return "\n".join(out) + "\n"

        main_dir = self._resolve_main_dir(lines, source_url)

        from urllib.parse import urlparse, urljoin
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
                media_url = urljoin(source_url, line)
                media_path = urlparse(media_url).path
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
                segments.append(urljoin(source_url, line))

        if kept == 0 and removed > 0:
            self.log("广告过滤命中全部分片，判定锚点失效，回退为不过滤模式")
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")

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
                from urllib.parse import parse_qs, urlparse
                qs = parse_qs(urlparse(target).query)
                if "url" in qs:
                    target = qs["url"][0]
            target = unquote(str(target or ""))

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
            self.log({"action": "localProxy_error", "error": str(e)})
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]

    def recommendContent(self, ids, pg=None):
        if not ids:
            return {"list": []}
        vid = ids[0] if isinstance(ids, list) else ids
        if '|$|' in vid:
            vid = vid.split('|$|', 1)[0]
        try:
            url = f"{self.host}/video/{vid}/"
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            videos = []
            card_pattern = r'<li[^>]*class="[^"]*tp4-section-content__item[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-src="([^"]+)"[^>]*>.*?<h3[^>]*class="[^"]*text-truncate[^"]*"[^>]*>([^<]+)</h3>.*?<span[^>]*class="[^"]*tp4-eye[^"]*"[^>]*>([^<]*)</span>'
            matches = re.findall(card_pattern, html, re.DOTALL)
            for href, pic, title, views in matches:
                vid_new = self._extract_video_id(href)
                if not vid_new or vid_new == vid:
                    continue
                title = title.strip()
                if not title:
                    continue
                pic = self._fix_url(pic.strip())
                videos.append({
                    "vod_id": vid_new,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": views.strip() if views else "",
                })
                if len(videos) >= 10:
                    break
            return {"list": videos}
        except Exception as e:
            self.log({"action": "recommendContent_error", "error": str(e)})
            return {"list": []}

    def destroy(self):
        pass