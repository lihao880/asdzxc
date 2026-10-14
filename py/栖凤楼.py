# coding: utf-8
"""
站点名称: 栖凤楼
站点类型: 标准HTML影视站（成人内容）
主域名: https://aho.qfl4.top
备用域名: https://ilb.xxxxff.com/341/ (发布页)
内容类型: 视频
特殊说明: 播放地址在详情页 script 的 rawUrl 变量中；m3u8 有广告分片需过滤
最后验证: 2026-09-01
来源: 用户提供
"""

import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://aho.qfl4.top"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类硬编码
        self.classes = [
            {"type_id": "20", "type_name": "绝美少女"},
            {"type_id": "21", "type_name": "激情口交"},
            {"type_id": "22", "type_name": "亚洲日韩"},
            {"type_id": "23", "type_name": "人妖激情"},
            {"type_id": "24", "type_name": "重咸口味"},
            {"type_id": "25", "type_name": "国产专区"},
            {"type_id": "26", "type_name": "日韩专区"},
            {"type_id": "27", "type_name": "欧美专区"},
            {"type_id": "28", "type_name": "卡通动漫"},
            {"type_id": "29", "type_name": "三级伦理"}
        ]
        # 筛选（无筛选功能）
        self.filters = {tid: [] for tid in ["20", "21", "22", "23", "24", "25", "26", "27", "28", "29"]}
        self._cached_host = self.host

    def getName(self):
        return "栖凤楼"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 从首页抓取"""
        try:
            res = self.fetch(self.host + "/cn/home/web/", headers=self.headers, timeout=15)
            if not res or res.status_code != 200:
                return {"list": []}
            html = res.text
            items = self._parse_list(html, self.host + "/cn/home/web/")
            return {"list": items[:30] if items else []}
        except Exception as e:
            self.log({"action": "homeVideoContent_error", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        """分类列表"""
        page = pg or "1"
        url = f"{self.host}/vodtype/{tid}-{page}.html"
        try:
            res = self.fetch(url, headers=self.headers, timeout=15)
            if not res or res.status_code != 200:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = res.text
            items = self._parse_list(html, url)
            # 解析总页数
            pagecount = self._parse_total_pages(html)
            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception as e:
            self.log({"action": "categoryContent_error", "tid": tid, "pg": page, "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        """详情页"""
        try:
            vod_id = str(ids[0]) if ids else ""
            if not vod_id:
                return {"list": []}
            url = f"{self.host}/{vod_id}.html"
            res = self.fetch(url, headers=self.headers, timeout=15)
            if not res or res.status_code != 200:
                return {"list": []}
            html = res.text
            # 提取标题
            title = self._extract_title(html)
            # 提取播放地址
            play_url = self._extract_play_url(html)
            # 提取发布时间
            pub_date = self._extract_pub_date(html)
            # 提取封面图
            pic = self._extract_pic(html)
            vod = {
                "vod_id": vod_id,
                "vod_name": title or "视频",
                "vod_pic": pic or "",
                "vod_remarks": pub_date or "",
                "vod_content": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}" if play_url else ""
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent_error", "ids": ids, "error": str(e)})
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        try:
            if not key:
                return {"list": [], "page": 1}
            keyword = urllib.parse.quote(key)
            url = f"{self.host}/s/index.html?wd={keyword}" if pg == "1" else f"{self.host}/s/{keyword}/page/{pg}.html"
            res = self.fetch(url, headers=self.headers, timeout=15)
            if not res or res.status_code != 200:
                return {"list": [], "page": int(pg)}
            html = res.text
            items = self._parse_list(html, url)
            pagecount = self._parse_search_total_pages(html)
            return {"list": items, "page": int(pg), "pagecount": pagecount}
        except Exception as e:
            self.log({"action": "searchContent_error", "key": key, "error": str(e)})
            return {"list": [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        """播放地址"""
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        # 如果是 m3u8 地址，走代理过滤
        if ".m3u8" in id:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id),
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        # 如果是 mp4 直链，直接返回
        if ".mp4" in id:
            return {"parse": 0, "url": id, "header": {"User-Agent": self.headers.get("User-Agent", "")}}
        # 其他情况降级嗅探
        return {"parse": 1, "url": id, "header": self.headers}

    def recommendContent(self, ids, pg):
        """相关推荐 - 从详情页提取"""
        try:
            vod_id = str(ids[0]) if ids else ""
            if not vod_id:
                return {"list": []}
            url = f"{self.host}/{vod_id}.html"
            res = self.fetch(url, headers=self.headers, timeout=15)
            if not res or res.status_code != 200:
                return {"list": []}
            html = res.text
            # 提取推荐列表
            items = self._parse_recommend(html, url)
            return {"list": items[:20] if items else []}
        except Exception as e:
            self.log({"action": "recommendContent_error", "error": str(e)})
            return {"list": []}

    def destroy(self):
        """释放资源"""
        pass

    # ---------- 辅助方法 ----------

    def _parse_list(self, html, base_url):
        """解析视频列表"""
        items = []
        # 匹配 .f-movie 容器
        pattern = r'<div class="f-movie">.*?<a href="([^"]+)">.*?<img src="([^"]+)"[^>]*alt="([^"]*)"[^>]*>.*?<a href="[^"]+"[^>]*>([^<]*)</a>.*?<p>([^<]*)</p>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            link, pic, alt, name, remark = match
            if not link or not name:
                continue
            vod_id = self._extract_vod_id(link)
            if not vod_id:
                continue
            items.append({
                "vod_id": vod_id,
                "vod_name": name.strip(),
                "vod_pic": pic,
                "vod_remarks": remark.strip()
            })
        return items

    def _parse_recommend(self, html, base_url):
        """解析推荐列表"""
        # 查找 "猜你喜欢" 区域
        start = html.find('猜你喜欢')
        if start == -1:
            return []
        end = html.find('<div class="clearfix"></div>', start)
        if end == -1:
            return []
        section = html[start:end]
        return self._parse_list(section, base_url)

    def _extract_vod_id(self, link):
        """从链接提取视频ID"""
        match = re.search(r'/(\d+)\.html', link)
        return match.group(1) if match else ""

    def _extract_title(self, html):
        """提取标题（精确匹配视频标题区域）"""
        # 精确匹配 .m-single-article .article-left h3
        match = re.search(r'<div class="m-single-article[^"]*">.*?<div class="article-left[^"]*">.*?<h3[^>]*>([^<]+)</h3>', html, re.DOTALL)
        if match:
            return match.group(1).strip()
        # 备用：匹配 article-img 前面的 h3
        match = re.search(r'<h3[^>]*>([^<]+)</h3>\s*<div class="clearfix"></div>\s*<div class="article-time-strip"', html, re.DOTALL)
        if match:
            return match.group(1).strip()
        # 最后备用：匹配第一个 h3 但排除 "热播排行榜"
        matches = re.findall(r'<h3[^>]*>([^<]+)</h3>', html)
        for title in matches:
            title = title.strip()
            if title and "热播排行榜" not in title and "热门关键词" not in title:
                return title
        return ""
    def _extract_play_url(self, html):
        """提取播放地址（rawUrl 变量）"""
        # 匹配 const rawUrl = '...';
        match = re.search(r"const rawUrl\s*=\s*'([^']+)';", html)
        if match:
            url = match.group(1)
            # 从 URL 中提取 m3u8 地址（可能有多个）
            m3u8_match = re.search(r'(https?://[^\s$#]+\.m3u8(?:\?[^\s#]*)?)', url, re.I)
            if m3u8_match:
                return m3u8_match.group(1)
            return url
        # 备用：匹配 var rawUrl
        match = re.search(r"var rawUrl\s*=\s*'([^']+)';", html)
        if match:
            url = match.group(1)
            m3u8_match = re.search(r'(https?://[^\s$#]+\.m3u8(?:\?[^\s#]*)?)', url, re.I)
            if m3u8_match:
                return m3u8_match.group(1)
            return url
        return ""

    def _extract_pub_date(self, html):
        """提取发布时间"""
        match = re.search(r'<p><i[^>]*></i>更新时间：([^<]+)</p>', html)
        return match.group(1).strip() if match else ""

    def _extract_pic(self, html):
        """提取封面图"""
        # 从 video 标签前找封面
        match = re.search(r'<img[^>]+class="img-box"[^>]+src="([^"]+)"', html)
        return match.group(1) if match else ""

    def _parse_total_pages(self, html):
        """解析分类总页数"""
        # 匹配尾页链接: /vodtype/25-326.html
        match = re.search(r'/vodtype/\d+-(\d+)\.html"[^>]*>尾页</a>', html)
        if match:
            return int(match.group(1))
        # 匹配 select 中最大 option
        matches = re.findall(r'<option value="(\d+)"', html)
        if matches:
            return max(int(v) for v in matches)
        return 1

    def _parse_search_total_pages(self, html):
        """解析搜索总页数"""
        match = re.search(r'/s/[^/]+/page/(\d+)\.html"[^>]*>尾页</a>', html)
        if match:
            return int(match.group(1))
        matches = re.findall(r'<option value="(\d+)"', html)
        if matches:
            return max(int(v) for v in matches)
        return 1

    def getProxyUrl(self):
        """获取代理地址"""
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址"""
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤（五层管线）"""
        try:
            # 解析参数
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

            resp = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=20)
            if not resp or resp.status_code != 200:
                return [502, "text/plain", f"fetch failed: {resp.status_code if resp else 'no response'}".encode()]
            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]

            # 检查是否为 m3u8
            if b"#EXTM3U" not in content[:512]:
                return [200, "application/octet-stream", content]

            text = content.decode("utf-8", errors="ignore")
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log({"action": "localProxy_error", "error": str(e)})
            return [500, "text/plain", f"localProxy error: {e}".encode()]

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：五层管线"""
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # ---- 第1层：图片流伪装检测 ----
        # 先检测，还原扩展名后继续执行后续过滤（不 return）
        is_fake = self._is_fake_image_stream(text, source_url)
        if is_fake:
            self.log("检测到图片流伪装，还原扩展名 .jpg/.png -> .ts")
            # 还原扩展名（.jpeg 必须先于 .jpg）
            for ext in (".png", ".jpeg", ".jpg", ".webp"):
                text = text.replace(ext, ".ts")
            lines = [l.strip() for l in text.replace("\r", "").split("\n") if l.strip()]
            # 继续执行后续过滤，不 return

        # ---- 第2层：多码率主表处理 ----
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            return self._clean_m3u8_multi(lines, source_url)

        # ---- 第3层：正片目录锚点 ----
        # 优先使用 KEY URI 目录，无 KEY 则用 m3u8 URL 目录
        main_dir = self._resolve_main_dir(lines, source_url)

        # ---- 第4层：分片过滤 ----
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        # ---- 第5层：全滤兜底 ----
        if removed > 0 and (kept == 0 or removed > kept):
            self.log(f"广告过滤命中过多分片(滤{removed}/留{kept})，判定锚点失效，回退为不过滤模式")
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")

        # ---- 第5层：冗余标签清理 ----
        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"
    def _is_fake_image_stream(self, text, source_url):
        """检测图片流伪装"""
        low_url = (source_url or "").lower()
        # 已知图片流服务商特征（包含 thm3u8、jpg、png）
        for sig in ("doyinapi", "svip", "imgcdn", "photo", "thm3u8", "jpg", "png"):
            if sig in low_url:
                return True
        # 分片扩展名为图片格式
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower().split("?")[0]
            if low.endswith((".png", ".jpg", ".jpeg", ".webp")):
                return True
        return False
    def _clean_m3u8_multi(self, lines, source_url):
        """多码率主表透传"""
        out = []
        for line in lines:
            if line.startswith("#"):
                out.append(line)
                continue
            child = urllib.parse.urljoin(source_url, line)
            if ".m3u8" in child.lower():
                out.append(self._m3u8_proxy_url(child))
            else:
                out.append(child)
        return "\n".join(out) + "\n"

    def _resolve_main_dir(self, lines, source_url):
        """解析正片目录锚点（KEY URI 目录优先）"""
        import posixpath
        parsed = urllib.parse.urlparse(source_url)
        main_dir = posixpath.dirname(parsed.path)
        if not main_dir.endswith("/"):
            main_dir += "/"
        # 优先以 KEY URI 目录为锚点
        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            key_path = urllib.parse.urlparse(
                key_uri if key_uri.startswith("http") else urllib.parse.urljoin(source_url, key_uri)
            ).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return main_dir

    def _filter_segments(self, lines, source_url, main_dir):
        """分片过滤"""
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

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写 m3u8 标签中的 URI（补全绝对地址）"""
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

    def _dedup_tags(self, segments, source_url):
        """冗余标签清理（去重 + 清尾）"""
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
        return out