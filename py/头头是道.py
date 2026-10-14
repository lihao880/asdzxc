# coding: utf-8
"""
站点: 头头是道 (ttsd4.cc)
类型: MacCMS 标准影视站 (HTML解析)
内容: 成人视频
备用域名: ttsd1.top
"""
import json
import re
from urllib.parse import quote, urljoin, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://ttsd4.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "1", "type_name": "在线一区"},
            {"type_id": "6", "type_name": "国产视频"},
            {"type_id": "7", "type_name": "中文字幕"},
            {"type_id": "8", "type_name": "日韩精品"},
            {"type_id": "9", "type_name": "自拍偷拍"},
            {"type_id": "10", "type_name": "人妻熟女"},
            {"type_id": "11", "type_name": "动漫卡通"},
            {"type_id": "12", "type_name": "欧美激情"},
            {"type_id": "20", "type_name": "口交颜射"},
            {"type_id": "2", "type_name": "在线二区"},
            {"type_id": "13", "type_name": "制服诱惑"},
            {"type_id": "14", "type_name": "丝袜美腿"},
            {"type_id": "15", "type_name": "无码流出"},
            {"type_id": "16", "type_name": "AV解说"},
            {"type_id": "21", "type_name": "明星换脸"},
            {"type_id": "22", "type_name": "三级伦理"},
            {"type_id": "23", "type_name": "强奸乱伦"},
            {"type_id": "24", "type_name": "SM调教"}
        ]
        self.filters = {}
        for c in self.classes:
            self.filters[c["type_id"]] = []

    def getName(self):
        return "头头是道"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self._fetch_list(f"{self.host}/", 1)

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
        return self._fetch_list(url, page)

    def detailContent(self, ids):
        if isinstance(ids, list) and len(ids) > 0:
            vid = str(ids[0])
        else:
            vid = str(ids)

        url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        title = self._extract_title(html)
        pic = self._extract_poster(html)
        remark = self._extract_remark(html)

        play_links = self._extract_play_links(html)
        if play_links:
            vod_play_from = "$$$".join([name for name, _ in play_links])
            vod_play_url = "$$$".join([f"正片${link}" for _, link in play_links])
        else:
            vod_play_from = "头头是道"
            vod_play_url = f"正片${vid}"

        vod = {
            "vod_id": vid,
            "vod_name": title or "视频",
            "vod_pic": pic or "",
            "vod_remarks": remark or "",
            "vod_content": remark or "",
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        url = f"{self.host}/index.php/vod/search.html?wd={quote(key)}"
        return self._fetch_list(url, pg)

    def playerContent(self, flag, id, vipFlags):
        id = str(id) if id is not None else ""
        if not id:
            return {"parse": 1, "url": "", "header": self.headers}

        if id.startswith("http") and (".m3u8" in id or ".mp4" in id):
            if ".m3u8" in id:
                return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": {}}
            return {"parse": 0, "url": id, "header": self.headers}

        if id.isdigit():
            play_url = f"{self.host}/index.php/vod/play/id/{id}/sid/1/nid/1.html"
        elif id.startswith("/"):
            play_url = self.host + id
        else:
            play_url = id

        html = self._fetch_html(play_url)
        if not html:
            return {"parse": 1, "url": play_url, "header": self.headers}

        m3u8_url = self._extract_m3u8_from_page(html)
        if m3u8_url and m3u8_url.startswith("http"):
            return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": {}}

        iframe_url = self._extract_iframe_url(html)
        if iframe_url:
            return {"parse": 1, "url": iframe_url, "header": self.headers}

        return {"parse": 1, "url": play_url, "header": self.headers}

    def localProxy(self, param):
        target = unquote(str((param or {}).get("url", "") or ""))
        if not target or not target.startswith("http"):
            return [400, "text/plain", b"invalid url"]

        try:
            resp = self.fetch(target, headers=self.headers, timeout=15, verify=False)
            if not resp or getattr(resp, "status_code", 0) != 200:
                return [502, "text/plain", b"fetch failed"]

            raw = getattr(resp, "content", b"") or b""
            text = raw.decode("utf-8", errors="ignore")

            if "#EXTM3U" in text:
                cleaned = self._clean_m3u8(text, target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

            content_type = getattr(resp, "headers", {}).get("Content-Type", "application/octet-stream")
            return [200, content_type, raw]

        except Exception as e:
            return [500, "text/plain", f"proxy error: {str(e)}".encode("utf-8")]

    def _fetch_html(self, url):
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15, verify=False)
            if resp and getattr(resp, "status_code", 0) == 200:
                return getattr(resp, "content", b"").decode("utf-8", errors="ignore")
        except Exception:
            pass
        return ""

    def _fetch_list(self, url, pg=1):
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}

        items = []
        li_blocks = re.findall(r'<li>.*?</li>', html, re.DOTALL)
        for block in li_blocks:
            link_match = re.search(r'<a class="thumbnail"[^>]*href="([^"]+)"', block)
            if not link_match:
                continue
            detail_url = link_match.group(1)
            vod_id = re.search(r'/id/(\d+)\.html', detail_url)
            if not vod_id:
                continue
            vod_id = vod_id.group(1)

            pic_match = re.search(r'<img[^>]*src="([^"]+)"', block)
            pic = pic_match.group(1) if pic_match else ""

            title_match = re.search(r'<h5>\s*<a[^>]*>([^<]*)</a>\s*</h5>', block)
            title = title_match.group(1).strip() if title_match else ""

            remark_match = re.search(r'<span[^>]*>([^<]*)</span>', block)
            remark = remark_match.group(1).strip() if remark_match else ""

            tag_match = re.search(r'<p>([^<]*)</p>', block)
            tag = tag_match.group(1).strip() if tag_match else ""

            if vod_id and title:
                items.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": f"{tag} {remark}".strip()
                })

        pagecount = 1
        total = 0
        page_match = re.search(r'共(\d+)条数据,当前(\d+)/(\d+)页', html)
        if page_match:
            total = int(page_match.group(1))
            pagecount = int(page_match.group(3))

        return {
            "list": items,
            "page": int(pg),
            "pagecount": pagecount,
            "limit": 20,
            "total": total
        }

    def _extract_title(self, html):
        match = re.search(r'片名：([^<]+)', html)
        if match:
            return match.group(1).strip()
        match = re.search(r'<span[^>]*>([^<]*(?:FSDSS|DASS|MIAB|MIDV|KBI|JUFE|JUQ|IPZZ|ABF|ADN)[^<]*)</span>', html)
        if match:
            return match.group(1).strip()
        match = re.search(r'<title>([^<]+)</title>', html)
        if match:
            return match.group(1).replace("剧情介绍", "").replace("--头头是道", "").strip()
        return ""

    def _extract_poster(self, html):
        match = re.search(r'<a href="[^"]*play[^"]*"[^>]*>\s*<img[^>]*src="([^"]+)"', html, re.DOTALL)
        if match:
            return match.group(1)
        return ""

    def _extract_remark(self, html):
        match = re.search(r'<label>更新：</label>([^<]+)', html)
        if match:
            return match.group(1).strip()
        match = re.search(r'<label>类型：</label>\s*([^<]+)', html)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_play_links(self, html):
        links = []
        seen = set()
        # 先尝试从 player_aaaa 提取 m3u8 直链（优先）
        match = re.search(r'player_aaaa\s*=\s*({[^;]+})', html)
        if match:
            try:
                data = json.loads(match.group(1))
                if data.get("url") and ".m3u8" in data["url"]:
                    links.append(("正片", data["url"]))
                    return links
            except:
                pass

        # 如果没有 m3u8 直链，从 detail-play-list 提取播放页链接
        ul_match = re.search(r'<ul[^>]*class="[^"]*detail-play-list[^"]*"[^>]*>(.*?)</ul>', html, re.DOTALL)
        if ul_match:
            ul_content = ul_match.group(1)
            for link in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>([^<]*)</a>', ul_content):
                href = link.group(1)
                name = link.group(2).strip()
                if href and name:
                    if href.startswith("/"):
                        href = self.host + href
                    key = (name, href)
                    if key not in seen:
                        seen.add(key)
                        links.append((name, href))

        return links

    def _extract_m3u8_from_page(self, html):
        match = re.search(r'player_aaaa\s*=\s*({[^;]+})', html)
        if match:
            try:
                data = json.loads(match.group(1))
                url = data.get("url", "")
                if url and ".m3u8" in url:
                    return url
            except:
                pass

        match = re.search(r'<iframe[^>]*src="([^"]*jiexidanaizi[^"]*)"', html)
        if match:
            url = match.group(1)
            url_match = re.search(r'url=([^&]+)', url)
            if url_match:
                decoded = unquote(url_match.group(1))
                if ".m3u8" in decoded:
                    return decoded

        match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
        if match:
            return match.group(1)

        return ""

    def _extract_iframe_url(self, html):
        match = re.search(r'<iframe[^>]*src="([^"]+)"[^>]*>', html)
        if match:
            return match.group(1)
        return ""

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "&url=" + quote(str(url or ""), safe="")

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片，保留正片"""
        lines = [line.strip() for line in text.replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 如果是主播放列表（包含 #EXT-X-STREAM-INF），递归代理子播放列表
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        # 分片列表清洗
        # 正片目录：从源URL提取路径前缀
        source_dir_match = re.search(r'(https?://[^/]+)/(.*/)[^/]+\.m3u8$', source_url)
        source_dir = source_dir_match.group(1) + "/" + source_dir_match.group(2) if source_dir_match else ""

        # 广告域名黑名单
        ad_patterns = [
            r'ad[s]?\d*\.',
            r'advert',
            r'banner',
            r'sponsor',
            r'promo',
            r'googleads',
            r'doubleclick',
            r'union\.',
            r'guanggao',
            r'/gg\d*\.',
            r'/ad[s]?\d*/',
            r'/banner/',
            r'/promo/',
        ]

        segments = []
        pending = []
        removed = 0

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media = urljoin(source_url, line)
                is_ad = False

                # 检查是否为广告分片
                # 1. 检查是否在正片目录下
                if source_dir and not media.startswith(source_dir):
                    is_ad = True

                # 2. 检查广告关键词
                if not is_ad:
                    for pattern in ad_patterns:
                        if re.search(pattern, media, re.I):
                            is_ad = True
                            break

                # 3. 检查文件名是否可疑
                if not is_ad:
                    filename = media.split("/")[-1].lower()
                    if re.search(r'(ad|adv|banner|sponsor|promo|gg|guanggao|advert)', filename):
                        is_ad = True

                if is_ad:
                    removed += 1
                else:
                    segments.extend(pending)
                    segments.append(media)
                pending = []
                continue

            if line.startswith("#"):
                segments.append(line)
            else:
                media = urljoin(source_url, line)
                is_ad = False
                if source_dir and not media.startswith(source_dir):
                    is_ad = True
                if not is_ad:
                    for pattern in ad_patterns:
                        if re.search(pattern, media, re.I):
                            is_ad = True
                            break
                if is_ad:
                    removed += 1
                else:
                    segments.append(media)

        # 合并连续相同标签
        filtered = []
        for seg in segments:
            if filtered and seg == filtered[-1]:
                if seg.startswith("#EXT-X-DISCONTINUITY") or seg == "#EXT-X-KEY:METHOD=NONE":
                    continue
            filtered.append(seg)

        # 日志记录广告过滤数量（调试用）
        # self.log(f"m3u8广告过滤: {removed} 个分片被移除")

        return "\n".join(filtered) + "\n"