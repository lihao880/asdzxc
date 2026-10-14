# coding: utf-8
"""
站点: 外围精品
主域名: https://o8cjc.wwjpp.shop/
备用域名: wwjpp.buzz
CMS: MacCMS
类型: 成人视频
维护信息: 2026-08-06
"""
import json
import re
from urllib.parse import quote, urljoin, unquote, urlparse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://o8cjc.wwjpp.shop"
        self.backup_host = "https://wwjpp.buzz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "20", "type_name": "国产大制作"},
            {"type_id": "21", "type_name": "偷拍自拍"},
            {"type_id": "22", "type_name": "乱伦毁三观"},
            {"type_id": "23", "type_name": "主播女网红"},
            {"type_id": "24", "type_name": "黑料网曝"},
            {"type_id": "25", "type_name": "高清无码"},
            {"type_id": "26", "type_name": "中文字幕"},
            {"type_id": "27", "type_name": "欧美精品"},
            {"type_id": "28", "type_name": "淫乱学生妹"},
            {"type_id": "29", "type_name": "动漫精选"},
            {"type_id": "30", "type_name": "高清有码"},
            {"type_id": "31", "type_name": "日本素人"},
            {"type_id": "32", "type_name": "无码流出"},
            {"type_id": "33", "type_name": "FC2"},
            {"type_id": "34", "type_name": "会所技师"},
            {"type_id": "35", "type_name": "国产推荐"},
            {"type_id": "36", "type_name": "探花约炮"},
            {"type_id": "37", "type_name": "韩国直播"},
            {"type_id": "38", "type_name": "国产直播"},
            {"type_id": "39", "type_name": "淫妻绿帽"},
            {"type_id": "40", "type_name": "制服诱惑"},
            {"type_id": "41", "type_name": "重口猎奇"},
            {"type_id": "42", "type_name": "东京热"},
            {"type_id": "43", "type_name": "一本道"},
            {"type_id": "44", "type_name": "欧美精品"}
        ]
        self.filters = {}
        for c in self.classes:
            self.filters[c["type_id"]] = []

    def getName(self):
        return "外围精品"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend

    def _get_host(self):
        return self.host

    def _fetch_html(self, url):
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if resp and hasattr(resp, "content"):
                return resp.content.decode("utf-8", errors="ignore")
        except Exception as e:
            self.log({"action": "fetch_error", "url": url, "error": str(e)})
        return None

    def _parse_video_list(self, html):
        if not html:
            return []
        items = []
        article_pattern = r'<article>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-src="([^"]+)"[^>]*>.*?<cite>([^<]+)</cite>.*?</article>'
        matches = re.findall(article_pattern, html, re.DOTALL)
        for match in matches:
            link, pic, title = match
            vod_id = re.search(r'/id/(\d+)\.html', link)
            if vod_id:
                items.append({
                    "vod_id": vod_id.group(1),
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return items

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        url = f"{self._get_host()}/index.php/vod/type/id/20.html"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        if page == "1":
            url = f"{self._get_host()}/index.php/vod/type/id/{tid}.html"
        else:
            url = f"{self._get_host()}/index.php/vod/type/id/{tid}/page/{page}.html"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        total = 0
        pagecount = 1
        if html:
            total_match = re.search(r'<em[^>]*class="mac_total"[^>]*>(\d+)</em>', html)
            if total_match:
                total = int(total_match.group(1))
            page_matches = re.findall(r'<a[^>]*href="[^"]*page/(\d+)\.html"[^>]*>(\d+)</a>', html)
            if page_matches:
                max_page = max([int(p[0]) for p in page_matches])
                pagecount = max_page
            last_match = re.search(r'<a[^>]*href="[^"]*page/(\d+)\.html"[^>]*>尾页</a>', html)
            if last_match:
                pagecount = int(last_match.group(1))
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": total
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        if isinstance(ids, (int, str)):
            vod_id = str(ids)
        elif isinstance(ids, list) and len(ids) > 0:
            vod_id = str(ids[0])
        else:
            return {"list": []}
        url = f"{self._get_host()}/index.php/vod/detail/id/{vod_id}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}
        title_match = re.search(r'<h2[^>]*>片名[：:]\s*([^<]+)</h2>', html)
        title = title_match.group(1).strip() if title_match else ""
        pic_match = re.search(r'<div[^>]*class="video-poster"[^>]*>.*?<img[^>]*src="([^"]+)"', html, re.DOTALL)
        pic = pic_match.group(1) if pic_match else ""
        play_btn_pattern = r'<button[^>]*class="play-btn"[^>]*onclick="window\.location\.href=\'([^\']+)\'"[^>]*>([^<]+)</button>'
        play_matches = re.findall(play_btn_pattern, html)
        play_froms = []
        play_urls = []
        for idx, (play_link, play_name) in enumerate(play_matches):
            play_froms.append(play_name.strip())
            sid_match = re.search(r'/sid/(\d+)/nid/(\d+)', play_link)
            if sid_match:
                sid, nid = sid_match.group(1), sid_match.group(2)
                play_urls.append(f"第1集${vod_id}|{sid}|{nid}")
            else:
                play_urls.append(f"第1集${vod_id}|1|1")
        if not play_matches:
            play_link_match = re.search(r'<a[^>]*href="([^"]*play[^"]*)"[^>]*>点此立即观看', html)
            if play_link_match:
                play_link = play_link_match.group(1)
                play_froms.append("播放")
                sid_match = re.search(r'/sid/(\d+)/nid/(\d+)', play_link)
                if sid_match:
                    sid, nid = sid_match.group(1), sid_match.group(2)
                    play_urls.append(f"第1集${vod_id}|{sid}|{nid}")
                else:
                    play_urls.append(f"第1集${vod_id}|1|1")
        vod = {
            "vod_id": vod_id,
            "vod_name": title or "视频",
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "$$$".join(play_froms) if play_froms else "",
            "vod_play_url": "$$$".join(play_urls) if play_urls else ""
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        url = f"{self._get_host()}/index.php/vod/search.html?wd={quote(key)}"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        parts = id.split("|")
        if len(parts) >= 3:
            vod_id, sid, nid = parts[0], parts[1], parts[2]
        else:
            vod_id = id
            sid, nid = "1", "1"
        url = f"{self._get_host()}/index.php/vod/play/id/{vod_id}/sid/{sid}/nid/{nid}.html"
        html = self._fetch_html(url)
        if not html:
            return {"parse": 1, "url": url, "header": self.headers}
        player_match = re.search(r'var\s+player_aaaa\s*=\s*({[^}]+})', html)
        if player_match:
            try:
                player_data = json.loads(player_match.group(1))
                play_url = player_data.get("url", "")
                encrypt = player_data.get("encrypt", 0)
                if play_url and encrypt == 0:
                    if play_url.endswith(".m3u8"):
                        return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": self.headers}
                    return {"parse": 0, "url": play_url, "header": self.headers}
            except Exception as e:
                self.log({"action": "parse_player_fail", "error": str(e)})
        iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"[^>]*>', html)
        if iframe_match:
            iframe_src = iframe_match.group(1)
            if iframe_src.startswith("http"):
                return {"parse": 1, "url": iframe_src, "header": self.headers}
        return {"parse": 1, "url": url, "header": self.headers}

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "&url=" + quote(str(url or ""), safe="")

    def localProxy(self, param):
        target = unquote(str((param or {}).get("url", "") or ""))
        if not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]
        try:
            res = self.fetch(target, headers=self.headers, timeout=15, verify=False)
            if not res or getattr(res, "status_code", 0) != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            raw = getattr(res, "content", b"") or b""
            text = raw.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log("m3u8代理失败: " + str(e))
            return [500, "text/plain", b"m3u8 proxy error"]

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片，保留正片"""
        if not text:
            return "#EXTM3U\n"
        lines = [line.strip() for line in text.replace("\r", "").split("\n")]
        if not lines:
            return "#EXTM3U\n"

        # 如果是多码率 m3u8（有 #EXT-X-STREAM-INF），递归处理子 m3u8
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                elif line and not line.startswith("#"):
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        # 单码率 m3u8：过滤广告分片
        # 广告分片特征：路径包含 ad/、短时长、特定域名
        ad_patterns = [
            r'/ad[s]?/',
            r'/advert/',
            r'/banner/',
            r'/promo/',
            r'/sponsor/',
            r'[/_]ad[/_]',
            r'\.ad\.',
            r'advertisement',
            r'guanggao',
            r'gg[0-9]+',
            r'pre[-_]?roll',
            r'post[-_]?roll',
            r'mid[-_]?roll',
            r'seg_00000\.',  # 第一个分片通常是广告
            r'seg_00001\.',
            r'seg_00002\.',
            r'[0-9a-f]{8}\.jpg$',  # 短哈希名的 jpg 可能是广告
        ]

        source_path = urlparse(source_url).path
        source_parts = [p for p in source_path.split("/") if p]
        # 取前三级作为内容根路径
        content_root = "/" + "/".join(source_parts[:3]) + "/" if len(source_parts) >= 3 else ""
        if not content_root and len(source_parts) >= 2:
            content_root = "/" + "/".join(source_parts[:2]) + "/"

        segments = []
        pending = []
        removed = 0

        # 检测是否有 KEY 标签，标记为加密视频
        has_key = any(line.startswith("#EXT-X-KEY") and "URI" in line for line in lines)

        i = 0
        while i < len(lines):
            line = lines[i]
            if not line:
                i += 1
                continue

            # 收集 EXTINF 块
            if line.startswith("#EXTINF"):
                pending = [line]
                i += 1
                # 收集后续的注释行
                while i < len(lines) and lines[i].startswith("#") and not lines[i].startswith("#EXTINF"):
                    pending.append(lines[i])
                    i += 1
                # 收集媒体 URL
                if i < len(lines) and lines[i] and not lines[i].startswith("#"):
                    media = lines[i]
                    media_url = media if media.startswith("http") else urljoin(source_url, media)
                    should_remove = False

                    # 1. 检查广告特征
                    media_lower = media_url.lower()
                    for pattern in ad_patterns:
                        if re.search(pattern, media_lower, re.I):
                            should_remove = True
                            break

                    # 2. 检查时长：短于 2 秒的广告
                    if not should_remove:
                        for p in pending:
                            if p.startswith("#EXTINF"):
                                dur_match = re.search(r'#EXTINF:([\d.]+)', p)
                                if dur_match:
                                    try:
                                        dur = float(dur_match.group(1))
                                        if dur < 2.0 and dur > 0:
                                            should_remove = True
                                            break
                                    except:
                                        pass

                    # 3. 对于加密视频，检查分片序号
                    if not should_remove and has_key:
                        # 检查分片路径是否包含日期和视频ID
                        # 正片路径格式: /20260805/7251a1c7cef11f7f/xxx.jpg
                        # 广告路径不同
                        if content_root and content_root not in media_url:
                            # 但如果是同域名的其他路径，保留
                            if urlparse(media_url).netloc != urlparse(source_url).netloc:
                                should_remove = True

                    # 4. 额外：检查是否包含 "seg_00000" 或 "seg_00001" 开头（广告）
                    if not should_remove:
                        seg_match = re.search(r'seg_(\d+)\.', media_url)
                        if seg_match:
                            seg_num = int(seg_match.group(1))
                            if seg_num <= 3:
                                should_remove = True

                    if should_remove:
                        removed += 1
                    else:
                        # 对于加密视频，需要补全 KEY 的绝对路径
                        if has_key:
                            for j, p in enumerate(pending):
                                if p.startswith("#EXT-X-KEY") and "URI=" in p:
                                    key_match = re.search(r'URI="([^"]+)"', p)
                                    if key_match:
                                        key_url = key_match.group(1)
                                        if not key_url.startswith("http"):
                                            key_url = urljoin(source_url, key_url)
                                        pending[j] = p.replace(key_match.group(0), f'URI="{key_url}"')
                        segments.extend(pending)
                        segments.append(media_url)
                    i += 1
                else:
                    # 没有媒体 URL，保留 pending
                    segments.extend(pending)
                    i += 1
                continue

            # 处理单独的标签行
            if line.startswith("#"):
                # 处理 KEY 标签，补全 URI
                if line.startswith("#EXT-X-KEY") and "URI=" in line:
                    key_match = re.search(r'URI="([^"]+)"', line)
                    if key_match:
                        key_url = key_match.group(1)
                        if not key_url.startswith("http"):
                            key_url = urljoin(source_url, key_url)
                        line = line.replace(key_match.group(0), f'URI="{key_url}"')
                segments.append(line)
            else:
                # 直接的媒体 URL
                media_url = line if line.startswith("http") else urljoin(source_url, line)
                should_remove = False
                media_lower = media_url.lower()
                for pattern in ad_patterns:
                    if re.search(pattern, media_lower, re.I):
                        should_remove = True
                        break
                if should_remove:
                    removed += 1
                else:
                    segments.append(media_url)
            i += 1

        # 清理尾部无效标签
        while len(segments) > 1 and segments[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            segments.pop(-1)

        if removed:
            self.log({"action": "m3u8_ad_filtered", "removed": removed})

        if segments and not segments[0].startswith("#EXTM3U"):
            segments.insert(0, "#EXTM3U")

        return "\n".join(segments) + "\n"
