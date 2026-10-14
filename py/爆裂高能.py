# coding: utf-8
import json
import re
from urllib.parse import quote, urljoin, unquote, urlparse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://l0rbzt.blgn99.quest"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.200 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类数据（从首页导航提取）
        self.classes = [
            {"type_id": "83258220", "type_name": "强奸乱伦"},
            {"type_id": "83208220", "type_name": "动漫精品"},
            {"type_id": "83198220", "type_name": "中文字幕"},
            {"type_id": "83248220", "type_name": "三级自慰"},
            {"type_id": "83218220", "type_name": "极骚萝莉"},
            {"type_id": "83008220", "type_name": "国产自拍"},
            {"type_id": "83018220", "type_name": "欧美极品"},
            {"type_id": "83028220", "type_name": "日韩无码"},
            # 视频二区
            {"type_id": "83008230", "type_name": "日韩无码"},
            {"type_id": "83268230", "type_name": "自拍偷拍"},
            {"type_id": "83418230", "type_name": "大秀视频"},
            {"type_id": "83228230", "type_name": "日韩精品"},
            {"type_id": "83028230", "type_name": "欧美精品"},
            {"type_id": "83178230", "type_name": "中文字幕"},
            {"type_id": "83038230", "type_name": "国产精品"},
            {"type_id": "83198230", "type_name": "动漫精品"},
            # 视频三区
            {"type_id": "83338300", "type_name": "自拍偷拍"},
            {"type_id": "83468300", "type_name": "91探花"},
            {"type_id": "83298300", "type_name": "欧美精品"},
            {"type_id": "83218300", "type_name": "国产色情"},
            {"type_id": "83368300", "type_name": "日本精品"},
            {"type_id": "83228300", "type_name": "主播直播"},
            {"type_id": "83588300", "type_name": "传媒出品"},
            {"type_id": "83198300", "type_name": "精品推荐"},
            # 视频四区
            {"type_id": "83268250", "type_name": "韩国伦理"},
            {"type_id": "83218250", "type_name": "成人动漫"},
            {"type_id": "83008250", "type_name": "国产情色"},
            {"type_id": "83228250", "type_name": "欧美情色"},
            {"type_id": "83238250", "type_name": "国模私拍"},
            {"type_id": "83198250", "type_name": "中文字幕"},
            {"type_id": "83018250", "type_name": "日本无码"},
            {"type_id": "83208250", "type_name": "网红主播"},
            # 视频五区
            {"type_id": "83058210", "type_name": "熟女人妻"},
            {"type_id": "83048210", "type_name": "欧美性爱"},
            {"type_id": "83038210", "type_name": "无码专区"},
            {"type_id": "83018210", "type_name": "国产主播"},
            {"type_id": "83068210", "type_name": "强奸乱伦"},
            {"type_id": "83028210", "type_name": "国产自拍"},
            {"type_id": "83008210", "type_name": "亚洲情色"},
            {"type_id": "83088210", "type_name": "中文字幕"},
            # 磁力一区
            {"type_id": "83008111", "type_name": "国产专区"},
            {"type_id": "83018111", "type_name": "日本有码"},
            {"type_id": "83028111", "type_name": "日本无码"},
            {"type_id": "83038111", "type_name": "欧美色情"},
            {"type_id": "83048111", "type_name": "传媒作品"},
            {"type_id": "83058111", "type_name": "探花直播"},
            {"type_id": "83068111", "type_name": "网黄女神"},
            {"type_id": "83078111", "type_name": "绿帽淫妻"},
        ]
        self.filters = {}

    def getName(self):
        return "爆裂高能"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 首页推荐 - 从首页解析
        url = self.host + "/"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}
        return {"list": self._parse_video_list(html, url)}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/list.php?id={tid}&page={page}"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

        # 解析列表
        items = self._parse_video_list(html, url)

        # 解析分页信息
        pagecount = 1
        total = 0
        # 提取 "共X部" 信息
        total_match = re.search(r'共(\d+)部', html)
        if total_match:
            total = int(total_match.group(1))

        # 提取尾页页码
        page_match = re.search(r'<a[^>]*class="pagebtn"[^>]*href="[^"]*page=(\d+)"[^>]*>尾页</a>', html)
        if page_match:
            pagecount = int(page_match.group(1))
        else:
            # 尝试从分页链接中提取最大页码
            page_links = re.findall(r'<a[^>]*href="[^"]*page=(\d+)"[^>]*>', html)
            if page_links:
                pagecount = max([int(p) for p in page_links])

        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": total
        }

    def detailContent(self, ids):
        # ids 可能是列表或整数
        if isinstance(ids, list):
            vod_id = str(ids[0])
        else:
            vod_id = str(ids)
        url = f"{self.host}/video.php?id={vod_id}"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        # 提取标题
        title_match = re.search(r'<div class="itemtitle">.*?<b>([^<]+)</b>', html, re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

        # 提取封面图（从播放器区域或页面中）
        pic = ""
        pic_match = re.search(r'<img[^>]*data-original="([^"]+)"[^>]*>', html)
        if pic_match:
            pic = pic_match.group(1)

        # 提取播放地址 (hls.loadSource)
        play_url = ""
        play_match = re.search(r"hls\.loadSource\s*\(\s*['\"]\s*([^'\"]+)['\"]\s*\)", html)
        if play_match:
            play_url = play_match.group(1)

        # 如果没有hls.loadSource，尝试其他方式
        if not play_url:
            # 尝试提取 video src
            src_match = re.search(r'<video[^>]*src="([^"]+)"', html)
            if src_match:
                play_url = src_match.group(1)

        # 构建vod数据
        vod = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"正片${play_url}" if play_url else ""
        }

        return {"list": [vod]}
    def searchContent(self, key, quick, pg="1"):
        page = pg or "1"
        # 搜索视频
        url = f"{self.host}/search.php?content={quote(key)}&type=1"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": 1}

        items = self._parse_video_list(html, url)

        return {"list": items, "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        # id 就是播放地址
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        # 如果是m3u8地址，走代理过滤广告
        if id.endswith(".m3u8") or ".m3u8" in id:
            return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": {}}

        # 如果是播放接口地址
        if "play.php" in id:
            return {"parse": 0, "url": id, "header": self.headers}

        # 直链
        return {"parse": 0, "url": id, "header": {"User-Agent": self.headers["User-Agent"]}}

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "&url=" + quote(str(url or ""), safe="")

    def _fetch_html(self, url):
        try:
            res = self.fetch(url, headers=self.headers, timeout=10, verify=False)
            if not res or getattr(res, "status_code", 0) != 200:
                return ""
            return getattr(res, "text", "") or ""
        except Exception as e:
            self.log({"action": "fetch_fail", "url": url, "error": str(e)})
            return ""

    def _parse_video_list(self, html, base_url):
        items = []
        # 匹配 <li> 中的视频项
        # <a class="filmthumb" href="/video.php?id=xxx" target="_blank">
        # <img class="loadi" data-original="xxx" src="...">
        # <h5><a href="/video.php?id=xxx">标题</a></h5>
        pattern = r'<li>.*?<a[^>]*class="filmthumb"[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-original="([^"]*)"[^>]*>.*?<h5><a[^>]*href="[^"]*"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.DOTALL)

        for match in matches:
            link, pic, title = match
            # 提取视频ID
            vid_match = re.search(r'id=(\d+)', link)
            if not vid_match:
                continue
            vod_id = vid_match.group(1)
            if not vod_id or not title:
                continue

            # 补全图片URL
            if pic and not pic.startswith("http"):
                pic = urljoin(base_url, pic)

            items.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": ""
            })

        return items

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤"""
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
            self.log("m3u8代理错误: " + str(e))
            return [500, "text/plain", b"m3u8 proxy error"]

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片，保留正片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 如果是主播放列表（有 #EXT-X-STREAM-INF），重写子列表路径
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        source_path = urlparse(source_url).path
        source_parts = [p for p in source_path.split("/") if p]
        content_root = "/" + "/".join(source_parts[:2]) + "/" if len(source_parts) >= 2 else ""
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
                if content_root and content_root not in urlparse(media).path:
                    removed += 1
                else:
                    segments.extend(pending)
                    segments.append(media)
                pending = []
                continue
            segments.append(self._rewrite_m3u8_tag(line, source_url))

        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line == "#EXT-X-KEY:METHOD=NONE" or line == "#EXT-X-DISCONTINUITY":
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)
        while len(out) > 1 and out[-2] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop(-2)
        if removed:
            self.log("m3u8已过滤广告分片: %d" % removed)
        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写 m3u8 标签中的 URI（补全绝对地址）"""
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                return 'URI="' + urljoin(source_url, match.group(1)) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            return urljoin(source_url, line)
        return line