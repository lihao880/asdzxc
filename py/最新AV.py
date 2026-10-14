# coding: utf-8
# 站点: 最新AV (https://www.changwen.shop/)
# 类型: MacCMS 架构影视站 (成人内容)
# 最后验证: 2026-09-07

import json
import re
from urllib.parse import urljoin, quote, unquote, urlparse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.host = "https://www.changwen.shop"
        self.classes = [
            {"type_id": "1", "type_name": "国产"},
            {"type_id": "2", "type_name": "欧美日本"},
            {"type_id": "3", "type_name": "主播"},
            {"type_id": "4", "type_name": "动漫"},
        ]
        self.filters = {
            "1": [],
            "2": [],
            "3": [],
            "4": [],
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host + "/",
        }
        self.timeout = 15
        self._ad_filter = None

    def getName(self):
        return "最新AV"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def _fetch(self, url, **kwargs):
        """带判空的请求，支持 SSL 容错"""
        # 如果 kwargs 中没有 timeout，使用默认值
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
        try:
            r = self.fetch(url, headers=self.headers, verify=False, **kwargs)
            if r is None:
                self.log({"fetch": "returned None", "url": url})
                return None
            if r.status_code != 200:
                self.log({"fetch": "non-200", "url": url, "status": r.status_code})
                return None
            return r
        except Exception as e:
            self.log({"fetch": "exception", "url": url, "error": str(e)})
            return None

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 直接取分类页第1页"""
        url = f"{self.host}/index.php/vod/type/page/1.html"
        r = self._fetch(url)
        if not r:
            return {"list": []}
        items = self._parse_list(r.text, url)
        return {"list": items[:20]}

    def _parse_list(self, html, page_url):
        """解析视频列表（分类页/搜索页共用）"""
        items = []
        # 提取所有视频链接和标题
        link_pattern = r'<a href="(/index.php/vod/play/id/\d+/sid/1/nid/1\.html)"\s+title="([^"]+)"'
        link_matches = re.findall(link_pattern, html)
        # 提取封面图
        pic_pattern = r'<a href="(/index.php/vod/play/id/\d+/sid/1/nid/1\.html)".*?<img[^>]+data-original="([^"]+)"'
        pic_matches = re.findall(pic_pattern, html, re.DOTALL)
        pic_map = {link: pic for link, pic in pic_matches}
        # 提取时长
        dur_pattern = r'<a href="(/index.php/vod/play/id/\d+/sid/1/nid/1\.html)".*?<span class="duration">([^<]*)</span>'
        dur_matches = re.findall(dur_pattern, html, re.DOTALL)
        dur_map = {link: dur for link, dur in dur_matches}
        # 合并
        for link, title in link_matches:
            if not title:
                continue
            id_match = re.search(r'/id/(\d+)/', link)
            if not id_match:
                continue
            vod_id = id_match.group(1)
            pic = pic_map.get(link, "")
            pic = pic.strip() if pic and not pic.startswith("data:") else ""
            duration = dur_map.get(link, "").strip()
            items.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": duration if duration else "HD",
            })
        # 如果上述方法没有匹配到，尝试备用方法
        if not items:
            # 备用：匹配所有 /vod/play/id/ 链接
            alt_pattern = r'<a href="(/index.php/vod/play/id/\d+/sid/1/nid/1\.html)"[^>]*>(.*?)</a>'
            alt_matches = re.findall(alt_pattern, html, re.DOTALL)
            for link, text in alt_matches:
                id_match = re.search(r'/id/(\d+)/', link)
                if not id_match:
                    continue
                # 从文本中提取标题（去除时长、日期等信息）
                title = re.sub(r'\d+:\d+.*$', '', text).strip()
                if not title:
                    continue
                items.append({
                    "vod_id": id_match.group(1),
                    "vod_name": title,
                    "vod_pic": "",
                    "vod_remarks": "HD",
                })
        return items

    @staticmethod
    def _norm_ids(ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
        pid = str(vid).split("|$|")[0].replace("$", "|")
        return {"list": [{
            "vod_id": vid,
            "vod_name": title or "未知标题",
            "vod_pic": pic or "",
            "vod_remarks": remarks,
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": "播放$" + pid,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        # 构造播放页URL
        play_url = f"{self.host}/index.php/vod/play/id/{raw}/sid/1/nid/1.html"
        r = self._fetch(play_url)
        title = f"视频{raw}"
        pic = ""
        if r:
            html = r.text
            # 提取标题
            title_match = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
                # 清洗站名后缀
                title = re.sub(r'\s*-\s*在线播放.*$', '', title)
                title = re.sub(r'\s*第\d+集\s*-\s*.*$', '', title)
                title = re.sub(r'\s*-\s*最新AV.*$', '', title)
            # 提取封面
            pic_match = re.search(r'<img[^>]+class="thumb"[^>]+data-original="([^"]+)"', html, re.DOTALL)
            if pic_match:
                pic = pic_match.group(1)
            # 如果上面没找到，尝试其他模式
            if not pic:
                pic_match2 = re.search(r'data-original="([^"]+)"', html, re.DOTALL)
                if pic_match2:
                    pic = pic_match2.group(1)
        if not title or title == "未知标题":
            title = f"视频{raw}"
        # 返回详情数据，播放地址由 playerContent 处理
        return {
            "list": [{
                "vod_id": raw,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "高清",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${raw}",
            }]
        }

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/index.php/vod/type/page/{page}.html"
        # 如果有分类筛选，尝试加上分类参数
        if tid and tid != "1":
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
        self.log({"category": "fetching", "url": url})
        r = self._fetch(url)
        if not r:
            self.log({"category": "fetch_failed", "url": url})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        self.log({"category": "fetch_success", "status": r.status_code, "html_len": len(r.text)})
        items = self._parse_list(r.text, url)
        self.log({"category": "parsed_items", "count": len(items)})
        # 从页面提取总页数
        pagecount = 495
        total_match = re.search(r'共(\d+)页', r.text)
        if total_match:
            pagecount = int(total_match.group(1))
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": len(items) * pagecount,
        }

    def searchContent(self, key, quick, pg="1"):
        if not key or len(key.strip()) < 2:
            return {"list": [], "page": 1}
        # 搜索词可能包含中文，需要 URL 编码
        encoded_key = quote(key.strip().encode('utf-8'))
        url = f"{self.host}/index.php/vod/search.html?wd={encoded_key}"
        r = self._fetch(url)
        if not r:
            return {"list": [], "page": 1}
        items = self._parse_list(r.text, url)
        return {"list": items, "page": int(pg)}

    def _extract_play_url(self, html):
        """从播放页提取 m3u8 地址"""
        # 匹配 var player_aaaa 中的 url
        pattern = r'var player_aaaa=.*?"url":"([^"]+)"'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            url = match.group(1)
            # 反转义 \/
            url = url.replace('\\/', '/')
            if url.startswith("//"):
                url = "https:" + url
            if not url.startswith("http"):
                url = "https://" + url
            return url
        return None

    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址"""
        proxy_base = self.getProxyUrl()
        # 移除已有的查询参数
        if '?' in proxy_base:
            proxy_base = proxy_base.split('?')[0]
        return proxy_base + "?do=py&url=" + quote(str(url or ""), safe="")

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id) if id else ""

        # 如果 id 是 "名称$地址" 格式，提取地址部分
        if play_url and "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]

        # 如果 play_url 是纯数字ID，请求播放页提取m3u8
        if play_url and re.match(r'^\d+$', play_url):
            page_url = f"{self.host}/index.php/vod/play/id/{play_url}/sid/1/nid/1.html"
            r = self._fetch(page_url)
            if r:
                m3u8_url = self._extract_play_url(r.text)
                if m3u8_url:
                    # 返回代理地址（因为m3u8有广告需要清洗）
                    return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": {"User-Agent": self.headers["User-Agent"]}}
            # 降级到播放页嗅探
            return {"parse": 1, "url": page_url, "header": self.headers}

        # 补全协议
        if play_url and not play_url.startswith("http"):
            if not play_url.startswith("//"):
                play_url = "https://" + play_url

        if not play_url:
            return {"parse": 0, "url": "", "header": {}}

        if play_url.endswith((".m3u8", ".mp4")):
            if ".m3u8" in play_url:
                return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": {"User-Agent": self.headers["User-Agent"]}}
            return {"parse": 0, "url": play_url, "header": {"User-Agent": self.headers["User-Agent"]}}

        # 如果已经是播放页URL
        if "/vod/play/" in play_url:
            r = self._fetch(play_url)
            if r:
                m3u8_url = self._extract_play_url(r.text)
                if m3u8_url:
                    return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": {"User-Agent": self.headers["User-Agent"]}}
            return {"parse": 1, "url": play_url, "header": self.headers}

        return {"parse": 0, "url": play_url, "header": {"User-Agent": self.headers["User-Agent"]}}

    def _get_ad_filter(self):
        """延迟加载 ad_filter 模块"""
        if self._ad_filter is not None:
            return self._ad_filter
        try:
            from ad_filter import M3u8AdFilter
            self._ad_filter = M3u8AdFilter()
            return self._ad_filter
        except ImportError:
            self._ad_filter = False
            return None

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤"""
        target = unquote(str((param or {}).get("url", "") or ""))
        if not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]

        # 先尝试使用 ad_filter 模块
        ad_filter = self._get_ad_filter()
        try:
            r = self._fetch(target, stream=True, timeout=15)
            if not r or getattr(r, "status_code", 0) != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            raw = getattr(r, "content", b"") or b""
            if not raw:
                return [502, "text/plain", b"empty response"]
            text = raw.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            # 使用 ad_filter 模块清洗
            if ad_filter:
                try:
                    cleaned = ad_filter.clean(text, target)
                    if cleaned and "#EXTM3U" in cleaned:
                        return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
                except Exception as e:
                    self.log({"localProxy": "ad_filter_error", "error": str(e)})

            # 降级清洗
            cleaned = self._clean_m3u8_fallback(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log({"localProxy": "error", "error": str(e)})
            return [500, "text/plain", b"m3u8 proxy error"]

    def _clean_m3u8_fallback(self, text, source_url):
        """降级清洗：ad_filter 不可用时使用"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 多码率主表处理
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        # 单码率：按锚点过滤
        source_path = urlparse(source_url).path
        source_parts = [p for p in source_path.split("/") if p]
        # 锚点：取 m3u8_url 目录
        content_root = ""
        if len(source_parts) >= 3:
            content_root = "/" + "/".join(source_parts[:3]) + "/"
        elif len(source_parts) >= 2:
            content_root = "/" + "/".join(source_parts[:2]) + "/"

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
                media = urljoin(source_url, line)
                # 检查是否在锚点目录下
                if content_root and content_root not in urlparse(media).path:
                    removed += 1
                else:
                    segments.extend(pending)
                    segments.append(media)
                    kept += 1
                pending = []
                continue
            segments.append(line)

        # 过滤后如果 kept == 0 或 removed > kept，全量返回（全滤兜底）
        if kept == 0 or removed > kept:
            self.log({"m3u8": "fallback_triggered", "removed": removed, "kept": kept})
            # 返回原始内容（不做过滤）
            return "\n".join(lines) + "\n"

        # 重写分片为绝对地址
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line == "#EXT-X-KEY:METHOD=NONE" or line == "#EXT-X-DISCONTINUITY":
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        # 清理尾部孤立标签
        while len(out) > 1 and out[-2] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop(-2)

        self.log({"m3u8": "cleaned", "removed": removed, "kept": kept})
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

    def recommendContent(self, ids, *args):
        return {"list": []}

    def destroy(self):
        pass