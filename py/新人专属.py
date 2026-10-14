# coding: utf-8
# 站点: https://hee727.xinrzs1.pw/ren/
# CMS: 苹果CMS (MacCMS v10)
# 类型: 成人影视聚合站

import re
import json
import urllib.parse
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://hee727.xinrzs1.pw"
        self.base_path = "/ren"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + self.base_path + "/"
        }
        self.classes = [
            {"type_id": "6", "type_name": "精品推荐"},
            {"type_id": "7", "type_name": "国产精品"},
            {"type_id": "8", "type_name": "主播秀色"},
            {"type_id": "9", "type_name": "日本有码"},
            {"type_id": "10", "type_name": "日本无码"},
            {"type_id": "11", "type_name": "中文字幕"},
            {"type_id": "21", "type_name": "童颜巨乳"},
            {"type_id": "22", "type_name": "性感人妻"},
            {"type_id": "23", "type_name": "强奸乱伦"},
            {"type_id": "24", "type_name": "欧美情色"},
            {"type_id": "25", "type_name": "三级伦理"},
            {"type_id": "26", "type_name": "卡通动漫"},
            {"type_id": "27", "type_name": "丝袜OL"},
            {"type_id": "28", "type_name": "自拍偷拍"},
            {"type_id": "29", "type_name": "日本片商"},
            {"type_id": "31", "type_name": "网曝系列"},
            {"type_id": "32", "type_name": "麻豆传媒"},
            {"type_id": "34", "type_name": "国产乱伦"},
            {"type_id": "36", "type_name": "国产SM"},
            {"type_id": "37", "type_name": "国产人妻"},
            {"type_id": "41", "type_name": "网红主播"},
            {"type_id": "42", "type_name": "国产传媒"},
            {"type_id": "43", "type_name": "探花系列"},
            {"type_id": "44", "type_name": "人妻熟女"},
            {"type_id": "45", "type_name": "日本无码"},
            {"type_id": "46", "type_name": "美乳巨乳"},
            {"type_id": "47", "type_name": "强制侵犯"},
            {"type_id": "48", "type_name": "制服诱惑"},
            {"type_id": "49", "type_name": "绝色佳人"},
            {"type_id": "50", "type_name": "风俗泡泡浴"},
            {"type_id": "51", "type_name": "家庭乱伦"},
            {"type_id": "52", "type_name": "AV解说"},
            {"type_id": "53", "type_name": "三级电影"},
            {"type_id": "54", "type_name": "少女萝莉"},
            {"type_id": "55", "type_name": "SM调教"},
            {"type_id": "56", "type_name": "绝顶潮吹"},
            {"type_id": "57", "type_name": "魔镜系列"},
            {"type_id": "58", "type_name": "时间停止"},
            {"type_id": "59", "type_name": "漫改系列"},
            {"type_id": "60", "type_name": "电车痴汉"},
            {"type_id": "73", "type_name": "无码专区"},
            {"type_id": "74", "type_name": "麻豆传媒"},
            {"type_id": "75", "type_name": "制服诱惑"},
            {"type_id": "76", "type_name": "三级伦理"},
            {"type_id": "77", "type_name": "AI换脸"},
            {"type_id": "78", "type_name": "中文字幕"},
            {"type_id": "79", "type_name": "卡通动漫"},
            {"type_id": "80", "type_name": "欧美系列"},
            {"type_id": "81", "type_name": "美女主播"},
            {"type_id": "82", "type_name": "国产自拍"},
            {"type_id": "83", "type_name": "熟女人妻"},
            {"type_id": "84", "type_name": "萝莉少女"},
            {"type_id": "85", "type_name": "多人群交"},
            {"type_id": "86", "type_name": "美乳巨乳"},
            {"type_id": "87", "type_name": "强奸乱伦"},
            {"type_id": "88", "type_name": "抖音视频"},
            {"type_id": "89", "type_name": "韩国主播"},
            {"type_id": "90", "type_name": "网红头条"},
            {"type_id": "91", "type_name": "网爆黑料"},
            {"type_id": "92", "type_name": "欧美无码"},
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}

    def getName(self):
        return "新人专属"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        if not url.startswith("http"):
            return self.host + self.base_path + "/" + url.lstrip("/")
        return url

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
            if hasattr(res, "body") and res.body:
                if isinstance(res.body, bytes):
                    return res.body.decode('utf-8', errors='ignore')
                return str(res.body)
            if isinstance(res, str):
                return res
            return ""
        except Exception:
            return ""

    def _parse_video_list(self, html):
        if not html:
            return []
        items = []
        li_pattern = r'<li[^>]*>.*?<a[^>]*class=["\']thumbnail["\'][^>]*href=["\']([^"\']+)["\'][^>]*>.*?<img[^>]*src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\'][^>]*>.*?</a>.*?<div[^>]*class=["\']video-info["\'][^>]*>.*?<h5[^>]*>.*?<a[^>]*href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']*)["\'][^>]*>(.*?)</a>.*?</h5>.*?<p[^>]*>(.*?)</p>'
        matches = re.findall(li_pattern, html, re.DOTALL)
        for match in matches:
            link = match[0].strip()
            pic = match[1].strip()
            alt = match[2].strip()
            title1 = match[4].strip()
            title2 = match[5].strip()
            remark = match[6].strip()
            title = title1 or title2 or alt
            if not title:
                continue
            vid_match = re.search(r'/voddetail/(\d+)\.html', link)
            if not vid_match:
                continue
            vod_id = vid_match.group(1)
            items.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": self._fix_url(pic),
                "vod_remarks": remark.strip() if remark else "",
                "vod_url": self._fix_url(link)
            })
        return items

    def _get_page_count(self, html):
        if not html:
            return 1
        page_match = re.search(r'共\d+条数据,当前(\d+)/(\d+)页', html)
        if page_match:
            return int(page_match.group(2))
        match = re.search(r'<a[^>]*href=["\']/ren/vodtype/\d+-(\d+)\.html["\'][^>]*>尾页</a>', html)
        if match:
            return int(match.group(1))
        return 1

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + self.base_path + "/vodtype/6.html")
        if not html:
            return {"list": []}
        return {"list": self._parse_video_list(html)[:20]}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        pg = int(pg) if pg else 1
        if pg == 1:
            url = f"{self.host}{self.base_path}/vodtype/{tid}.html"
        else:
            url = f"{self.host}{self.base_path}/vodtype/{tid}-{pg}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}
        videos = self._parse_video_list(html)
        return {"list": videos, "page": pg, "pagecount": self._get_page_count(html), "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            if not ids:
                return {"list": []}
            vod_id = str(ids[0])
            if vod_id.startswith("http"):
                vid_match = re.search(r'/voddetail/(\d+)\.html', vod_id)
                if vid_match:
                    vod_id = vid_match.group(1)
            url = f"{self.host}{self.base_path}/voddetail/{vod_id}.html"
            html = self._fetch_html(url)
            if not html:
                return {"list": []}
            title = ""
            title_match = re.search(r'<span[^>]*class=["\']text-muted["\'][^>]*>(.*?)</span>', html)
            if title_match:
                title = title_match.group(1).strip()
            if not title:
                title_match = re.search(r'<div[^>]*class=["\']breadcrumbs["\'][^>]*>.*?<span[^>]*>(.*?)</span>', html, re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
            if not title:
                title_match = re.search(r'<div[^>]*class=["\']detail-poster["\'][^>]*>.*?<img[^>]*alt=["\']([^"\']+)["\'][^>]*>', html, re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
            if not title:
                title = f"视频{vod_id}"
            pic = ""
            pic_match = re.search(r'<div[^>]*class=["\']detail-poster["\'][^>]*>.*?<img[^>]*src=["\']([^"\']+)["\'][^>]*>', html, re.DOTALL)
            if pic_match:
                pic = self._fix_url(pic_match.group(1))
            update_time = ""
            info_pattern = r'<li[^>]*>.*?<label>(.*?)</label>(.*?)</li>'
            for match in re.findall(info_pattern, html, re.DOTALL):
                label = match[0].strip()
                value = match[1].strip()
                if "更新" in label:
                    update_time = value
            play_url = f"{vod_id}-1-1"
            play_match = re.search(r'<ul[^>]*class=["\']detail-play-list[^"\']*["\'][^>]*>.*?<a[^>]*href=["\'](/ren/vodplay/\d+-\d+-\d+\.html)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
            if play_match:
                play_link = play_match.group(1)
                p_match = re.search(r'/vodplay/(\d+)-(\d+)-(\d+)\.html', play_link)
                if p_match:
                    play_url = f"{p_match.group(1)}-{p_match.group(2)}-{p_match.group(3)}"
            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": update_time or "",
                "vod_content": "",
                "vod_play_from": "默认播放",
                "vod_play_url": f"正片${play_url}"
            }
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if pg else 1
        encoded_key = urllib.parse.quote(key.encode('utf-8'))
        if pg == 1:
            url = f"{self.host}{self.base_path}/vodsearch/-------------.html?wd={encoded_key}"
        else:
            url = f"{self.host}{self.base_path}/vodsearch/{encoded_key}----------{pg}---.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": pg}
        return {"list": self._parse_video_list(html), "page": pg}

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "&url=" + urllib.parse.quote(str(url or ""), safe="")

    def playerContent(self, flag, id, vipFlags=None):
        try:
            if not id:
                return {"parse": 1, "url": ""}

            play_url = id
            if not id.startswith("http"):
                if "/" in id:
                    play_url = self._fix_url(id)
                elif "-" in id:
                    play_url = f"{self.host}{self.base_path}/vodplay/{id}.html"
                else:
                    play_url = f"{self.host}{self.base_path}/vodplay/{id}-1-1.html"

            html = self._fetch_html(play_url)
            if not html:
                return {"parse": 1, "url": play_url}

            m3u8_url = ""

            # 方案1: 匹配 player_aaaa JSON
            p_match = re.search(r'player_aaaa\s*=\s*(\{.*?\})(?:;|\n|</script>)', html, re.DOTALL)
            if p_match:
                try:
                    data = json.loads(p_match.group(1))
                    raw_url = data.get("url", "")
                    if raw_url:
                        raw_url = urllib.parse.unquote(raw_url).replace('\\/', '/')
                        if '.m3u8' in raw_url or '.mp4' in raw_url:
                            m3u8_url = raw_url
                except Exception:
                    pass

            # 方案2: 直接全局抓取 URL
            if not m3u8_url:
                urls = re.findall(r'(https?://[^\s"\'<>]+?\.(?:m3u8|mp4)[^\s"\'<>]*)', html, re.IGNORECASE)
                if urls:
                    m3u8_url = urls[0].replace('\\/', '/')

            if m3u8_url:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(m3u8_url),
                    "header": {"User-Agent": self.headers["User-Agent"]}
                }

            return {"parse": 1, "url": play_url}

        except Exception:
            return {"parse": 1, "url": id}

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤"""
        target = urllib.parse.unquote(str((param or {}).get("url", "") or ""))
        if not target:
            return [400, "text/plain", b"invalid url"]
        try:
            res = self.fetch(target, headers={"User-Agent": self.headers["User-Agent"]}, timeout=15)
            if not res:
                return [502, "text/plain", b"fetch failed"]
            content = getattr(res, "content", b"") or b""
            if not content:
                return [502, "text/plain", b"empty content"]
            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            return [500, "text/plain", str(e).encode()]

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片"""
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
        source_path = parsed.path
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
                media = urllib.parse.urljoin(source_url, line)
                if content_root and content_root not in urllib.parse.urlparse(media).path:
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
        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                return 'URI="' + urllib.parse.urljoin(source_url, match.group(1)) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            return urllib.parse.urljoin(source_url, line)
        return line

    def destroy(self):
        pass