# coding: utf-8
"""
站点名称: XX日鲍社
主域名: https://187.xxrbs.cfd
备用域名: 无
发布页: 无
内容类型: 成人影视/资源站
特殊说明: 论坛式站点，fid 分类，详情页 video 标签直链 m3u8
最后验证时间: 2026-09-01
来源: 用户提供

m3u8 结构摘要:
- 主 m3u8 为多码率索引，含 1 个子流
- 子 m3u8 分片为 .ts 格式，无加密 (#EXT-X-KEY:METHOD=NONE)
- 正片目录: /20200623/TfEybspr/500kb/hls/
- 过滤策略: m3u8 目录锚点，无广告目录，仅做绝对地址补全
"""

import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://187.xxrbs.cfd"
        self.classes = [
            {"type_id": "10065", "type_name": "国产自拍"},
            {"type_id": "10066", "type_name": "欧美极品"},
            {"type_id": "10067", "type_name": "日韩无码"},
            {"type_id": "10068", "type_name": "日韩有码"},
            {"type_id": "10069", "type_name": "中文字幕"},
            {"type_id": "10070", "type_name": "动漫精品"},
            {"type_id": "10071", "type_name": "极骚萝莉"},
            {"type_id": "10072", "type_name": "强奸乱伦"},
            {"type_id": "10073", "type_name": "童颜巨乳"},
            {"type_id": "10074", "type_name": "人妖视频"},
            {"type_id": "10075", "type_name": "三级自慰"},
        ]
        self.filters = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/new/index.php",
        }
        self._cached_host = self.host

    def getName(self):
        return "XX日鲍社"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐从列表页取"""
        url = f"{self.host}/new/index.php"
        html = self.fetch_html(url)
        if not html:
            return {"list": []}
        items = self._parse_video_list(html)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/new/index.php?mod=forumdisplay&fid={tid}&page={page}"
        html = self.fetch_html(url)
        if not html:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

        items = self._parse_video_list(html)
        total = self._parse_total_pages(html)

        return {
            "list": items,
            "page": int(page),
            "pagecount": total or 1,
            "limit": 20,
            "total": total * 20 if total else 0,
        }

    def detailContent(self, ids):
        tid = ids[0] if ids else ""
        url = f"{self.host}/new/index.php?mod=viewthread&tid={tid}"
        html = self.fetch_html(url)
        if not html:
            return {"list": []}

        title = self._extract_title(html)
        play_url = self._extract_play_url(html)
        tags = self._extract_tags(html)

        vod = {
            "vod_id": tid,
            "vod_name": title or "未知标题",
            "vod_pic": "",
            "vod_remarks": tags,
            "vod_content": tags,
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}" if play_url else "",
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/new/index.php?mod=search&kw={urllib.parse.quote(key)}"
        html = self.fetch_html(url)
        if not html:
            return {"list": [], "page": 1}
        items = self._parse_video_list(html)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        # 如果已经是 m3u8 直链，走代理清洗
        if id.startswith("http") and ".m3u8" in id.lower():
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id),
                "header": {"User-Agent": self.headers["User-Agent"]},
            }

        # 如果是播放页 url，尝试提取直链
        if id.startswith(self.host):
            html = self.fetch_html(id)
            if html:
                play_url = self._extract_play_url(html)
                if play_url and play_url.startswith("http") and ".m3u8" in play_url.lower():
                    return {
                        "parse": 0,
                        "url": self._m3u8_proxy_url(play_url),
                        "header": {"User-Agent": self.headers["User-Agent"]},
                    }

        # 降级嗅探
        return {
            "parse": 1,
            "url": id,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
            },
        }

    def recommendContent(self, ids, pg):
        """相关推荐"""
        return {"list": []}

    def destroy(self):
        pass

    # ====== 辅助方法 ======

    def fetch_html(self, url):
        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if getattr(resp, "status_code", 0) != 200:
                return ""
            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")
            return content.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def _parse_video_list(self, html):
        """从 HTML 中解析视频列表项"""
        items = []
        # 匹配 .list-videos .item 块，兼容标题中的高亮标签
        pattern = r'<div class="item\s*">.*?<a href="([^"]+)".*?<img.*?data-src="([^"]+)".*?<strong class="title">(.*?)</strong>.*?<em>([^<]+)</em>.*?<div class="views">(\d+)</div>'
        matches = re.findall(pattern, html, re.DOTALL)

        for match in matches:
            link, pic, title, date, views = match
            # 清理标题中的 HTML 标签（如 <span style="color:red;">）
            title = re.sub(r'<[^>]+>', '', title).strip()
            tid = self._extract_tid(link)
            if not tid:
                continue
            items.append({
                "vod_id": tid,
                "vod_name": title,
                "vod_pic": pic if pic.startswith("http") else self.host + pic,
                "vod_remarks": f"{date} {views}",
            })

        return items

    def _parse_total_pages(self, html):
        """解析总页数"""
        # 从分页中取最后一页（weiyeyema 类）
        pattern = r'<li class="fenyeyema weiyeyema"><a[^>]*>(\d+)</a></li>'
        match = re.search(pattern, html)
        if match:
            return int(match.group(1))
        # 备用：取所有分页数字的最大值
        pattern = r'<li class="fenyeyema"><a[^>]*>(\d+)</a></li>'
        matches = re.findall(pattern, html)
        if matches:
            return max(int(x) for x in matches)
        return 1

    def _extract_tid(self, link):
        """从链接中提取 tid"""
        match = re.search(r'tid=(\d+)', link)
        return match.group(1) if match else ""

    def _extract_title(self, html):
        """提取标题"""
        match = re.search(r'<h1>([^<]+)</h1>', html)
        if match:
            return match.group(1).strip()
        match = re.search(r'<title>([^<]+)_XX日鲍社</title>', html)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_play_url(self, html):
        """提取播放地址"""
        # 方式1: video 标签 src
        match = re.search(r'<video[^>]*src="([^"]+)"[^>]*>', html)
        if match:
            return match.group(1)

        # 方式2: xgplayer 配置中的 url
        match = re.search(r'"url":\s*"([^"]+)"', html)
        if match:
            return match.group(1)

        # 方式3: 通用 .m3u8 链接
        match = re.search(r'(https?://[^\s"\']+\.m3u8)', html)
        if match:
            return match.group(1)

        return ""

    def _extract_tags(self, html):
        """提取标签"""
        tags = []
        pattern = r'<a href="/new/index\.php\?mod=search&amp;kw=[^"]*">([^<]+)</a>'
        matches = re.findall(pattern, html)
        for m in matches[:5]:
            tags.append(m.strip())
        return ", ".join(tags) if tags else ""

    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址"""
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤"""
        target = ""
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(target).query)
                if "url" in qs:
                    target = qs["url"][0]
            target = urllib.parse.unquote(str(target or ""))
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

            # 非 m3u8 直接透传
            return [200, "application/octet-stream", content]
        except Exception as e:
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片，保留正片"""
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 检测图片流伪装
        if self._is_fake_image_stream(text, source_url):
            restored = text
            for ext in (".png", ".jpeg", ".jpg", ".webp"):
                restored = restored.replace(ext, ".ts")
            self.log("检测到图片流伪装，已还原扩展名 -> .ts，跳过广告过滤")
            return restored

        # 多码率主表透传
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    if ".m3u8" in child.lower():
                        out.append(self._m3u8_proxy_url(child))
                    else:
                        out.append(child)
            return "\n".join(out) + "\n"

        # 正片目录锚点
        main_dir = self._resolve_main_dir(lines, source_url)

        # 分片过滤
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        # 全滤兜底
        if kept == 0 and removed > 0:
            self.log("广告过滤命中全部分片，判定锚点失效，回退为不过滤模式")
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")

        # 冗余标签清理
        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def _is_fake_image_stream(self, text, source_url):
        """检测是否为图片流伪装"""
        low_url = (source_url or "").lower()
        for sig in ("doyinapi", "svip", "imgcdn", "photo", "pic"):
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
        """确定正片目录锚点，优先使用 KEY URI 目录"""
        import posixpath
        parsed = urllib.parse.urlparse(source_url)
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
            if not key_uri.startswith("http"):
                key_uri = urllib.parse.urljoin(source_url, key_uri)
            key_path = urllib.parse.urlparse(key_uri).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return main_dir

    def _filter_segments(self, lines, source_url, main_dir):
        """过滤分片"""
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
                media_url = urllib.parse.urljoin(source_url, line)
                media_path = urllib.parse.urlparse(media_url).path
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
                segments.append(urllib.parse.urljoin(source_url, line))

        return segments, removed, kept

    def _dedup_tags(self, segments, source_url):
        """清理冗余标签"""
        noise = ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE")
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in noise:
                if not out or out[-1] in noise:
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in noise:
            out.pop()
        return out

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写 m3u8 标签中的 URI"""
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