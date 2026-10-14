# coding: utf-8
"""
站点信息：
  主域名: https://123.aiding.cc/888/
  备用域名: www.setu8.com
  站点名称: 刚满18岁
  内容类型: 成人视频聚合
  特殊说明: 标准HTML站，m3u8嵌入播放页，多码率+AES-128加密，无广告分片
  最后验证时间: 2026-09-04
  来源: https://123.aiding.cc/888/
  m3u8结构摘要: 多码率主表 -> 单码率子流，KEY URI外部服务器，无广告目录特征
"""

import re
import json
import base64
from urllib.parse import urljoin, urlparse, quote, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://123.aiding.cc/888"
        self.site_name = "刚满18岁"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类列表（硬编码，来自首页）
        self.classes = [
            {"type_id": "31", "type_name": "网曝门"},
            {"type_id": "42", "type_name": "OnlyFans"},
            {"type_id": "6", "type_name": "网红主播"},
            {"type_id": "7", "type_name": "国产传媒"},
            {"type_id": "8", "type_name": "探花系列"},
            {"type_id": "37", "type_name": "国产自拍"},
            {"type_id": "9", "type_name": "人妻熟女"},
            {"type_id": "10", "type_name": "日本无码"},
            {"type_id": "11", "type_name": "美乳巨乳"},
            {"type_id": "12", "type_name": "强制侵犯"},
            {"type_id": "13", "type_name": "制服诱惑"},
            {"type_id": "14", "type_name": "绝色佳人"},
            {"type_id": "15", "type_name": "风俗泡泡浴"},
            {"type_id": "16", "type_name": "家庭乱伦"},
            {"type_id": "20", "type_name": "少女萝莉"},
            {"type_id": "21", "type_name": "SM调教"},
            {"type_id": "22", "type_name": "绝顶潮吹"},
            {"type_id": "23", "type_name": "魔镜系列"},
            {"type_id": "24", "type_name": "时间停止"},
            {"type_id": "25", "type_name": "催眠洗脑"},
            {"type_id": "26", "type_name": "漫改系列"},
            {"type_id": "27", "type_name": "电车痴汉"},
            {"type_id": "28", "type_name": "淫欲痴女"},
            {"type_id": "36", "type_name": "欧美精品"},
            {"type_id": "38", "type_name": "日本动漫"},
            {"type_id": "39", "type_name": "3D动漫"},
            {"type_id": "17", "type_name": "AV解说"},
            {"type_id": "18", "type_name": "三级电影"},
            {"type_id": "29", "type_name": "AI换脸"},
            {"type_id": "32", "type_name": "TS专区"},
            {"type_id": "33", "type_name": "女性向系列"},
            {"type_id": "34", "type_name": "女同性恋"},
            {"type_id": "35", "type_name": "男同性恋"},
            {"type_id": "40", "type_name": "韩国主播"},
            {"type_id": "41", "type_name": "泰国风情"},
        ]
        # 无筛选器
        self.filters = {c["type_id"]: [] for c in self.classes}

    def getName(self):
        return self.site_name

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 从首页解析"""
        url = self.host + "/"
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": []}
        html = resp.text
        return self._parse_video_list(html, url)

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/?type={tid}&page={page}"
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        html = resp.text
        result = self._parse_video_list(html, url)
        # 简单分页判断：检查是否有"下一页"链接
        has_next = '下一页' in html
        pagecount = int(page) + 1 if has_next else int(page)
        return {
            "list": result.get("list", []),
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20
        }

    def detailContent(self, ids):
        if not ids or not ids[0]:
            return {"list": []}
        vod_id = str(ids[0])
        url = f"{self.host}/watch.php?id={vod_id}"
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": []}
        html = resp.text
        return self._parse_detail(html, vod_id, url)

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        page = pg or "1"
        url = f"{self.host}/?q={quote(key)}&page={page}"
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": [], "page": int(page)}
        html = resp.text
        result = self._parse_video_list(html, url)
        return {"list": result.get("list", []), "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        play_id = str(id).strip()
        # 直接返回播放页让WebView嗅探（带完整header）
        url = f"{self.host}/play.php?id={play_id}"
        return {
            "parse": 1,
            "url": url,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/"
            }
        }

    def recommendContent(self, ids, pg):
        """相关推荐：返回空列表"""
        return {"list": []}

    def destroy(self):
        pass

    # ---------- 内部辅助方法 ----------

    def _parse_video_list(self, html, base_url):
        """解析视频列表（首页/分类/搜索共用）"""
        items = []
        # 匹配卡片 <a class="card" href="/888/watch.php?id=xxx">
        pattern = r'<a\s+class="card"\s+href="([^"]+)"[^>]*>.*?<h3>([^<]+)</h3>.*?<div\s+class="meta">\s*<span>([^<]+)</span>\s*<span>([^<]+)</span>'
        matches = re.findall(pattern, html, re.DOTALL)
        for href, title, category, views in matches:
            if not href or not title:
                continue
            # 提取vod_id
            vid_match = re.search(r'id=(\d+)', href)
            if not vid_match:
                continue
            vod_id = vid_match.group(1)
            # 提取封面图
            thumb_match = re.search(r'<img[^>]+src="([^"]+)"[^>]*>', html[html.find(href):html.find(href)+500] if html.find(href) != -1 else "")
            pic = ""
            if thumb_match:
                pic = thumb_match.group(1)
            items.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": category.strip() + " · " + views.strip()
            })
        return {"list": items}

    def _parse_detail(self, html, vod_id, base_url):
        """解析详情页"""
        title = ""
        category = ""
        remark = ""
        cover = ""
        content = ""
        play_from = "播放"
        play_url = ""

        # 标题
        title_match = re.search(r'<h1>([^<]+)</h1>', html)
        if title_match:
            title = title_match.group(1).strip()

        # 分类/备注
        eyebrow_match = re.search(r'<p\s+class="eyebrow">([^<]+)</p>', html)
        if eyebrow_match:
            category = eyebrow_match.group(1).strip()

        # 时间/播放量
        muted_match = re.search(r'<p\s+class="muted">([^<]+)</p>', html)
        if muted_match:
            remark = muted_match.group(1).strip()

        # 封面图
        cover_match = re.search(r'<img[^>]+src="([^"]+)"[^>]*>', html)
        if cover_match:
            cover = cover_match.group(1)

        # 简介
        content_match = re.search(r'<div\s+class="panel">\s*<h2>简介</h2>\s*<p>([^<]+)</p>', html, re.DOTALL)
        if content_match:
            content = content_match.group(1).strip()

        # 播放链接：从"立即播放"按钮获取play.php?id=xxx
        play_btn_match = re.search(r'<a\s+class="btn\s+big"\s+href="([^"]+)"[^>]*>立即播放</a>', html)
        if play_btn_match:
            play_href = play_btn_match.group(1)
            vid_match = re.search(r'id=(\d+)', play_href)
            if vid_match:
                play_url = "播放$" + vid_match.group(1)

        if not play_url:
            play_url = "播放$" + vod_id

        return {
            "list": [{
                "vod_id": vod_id,
                "vod_name": title or "视频",
                "vod_pic": cover,
                "vod_remarks": remark or category,
                "vod_content": content,
                "vod_actor": "",
                "vod_director": "",
                "vod_play_from": play_from,
                "vod_play_url": play_url
            }]
        }

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址"""
        if not url:
            return ""
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url), safe="")

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def localProxy(self, param):
        """m3u8本地代理 - 五层管线实现"""
        try:
            # 参数解析
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

            if b"#EXTM3U" not in content[:512]:
                return [200, "application/octet-stream", content]

            cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log("localProxy error: " + str(e))
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]

    def _is_fake_image_stream(self, text, source_url):
        """检测是否为图片流伪装"""
        low_url = (source_url or "").lower()
        # 已知图片流特征
        for sig in ("doyinapi", "svip", "imgcdn", "photo"):
            if sig in low_url:
                return True
        # 检查分片扩展名
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower().split("?")[0]
            if low.endswith((".png", ".jpg", ".jpeg", ".webp")):
                return True
        return False

    def _resolve_main_dir(self, lines, source_url):
        """解析正片目录锚点：KEY URI 目录优先"""
        import posixpath
        parsed = urlparse(source_url)
        main_dir = posixpath.dirname(parsed.path)
        if not main_dir.endswith("/"):
            main_dir += "/"

        # 优先从 KEY 获取
        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            if not key_uri.startswith("http"):
                key_uri = urljoin(source_url, key_uri)
            key_path = urlparse(key_uri).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return main_dir

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI"""
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(m):
                uri = m.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)
        return line

    def _filter_segments(self, lines, source_url, main_dir):
        """第4层：分片过滤"""
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
        return segments, removed, kept

    def _dedup_tags(self, segments, source_url):
        """第5层：冗余标签清理"""
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

    def _clean_m3u8_multi(self, lines, source_url):
        """第2层：多码率主表透传"""
        out = []
        for line in lines:
            if line.startswith("#"):
                out.append(line)
                continue
            child = urljoin(source_url, line)
            if ".m3u8" in child.lower():
                out.append(self._m3u8_proxy_url(child))
            else:
                out.append(child)
        return "\n".join(out) + "\n"

    def _clean_m3u8(self, text, source_url):
        """五层管线主入口"""
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 第1层：图片流伪装检测
        if self._is_fake_image_stream(text, source_url):
            restored = text
            for ext in (".png", ".jpeg", ".jpg", ".webp"):
                restored = restored.replace(ext, ".ts")
            self.log("检测到图片流伪装，已还原扩展名 -> .ts，跳过广告过滤")
            return restored

        # 第2层：多码率主表
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            return self._clean_m3u8_multi(lines, source_url)

        # 第3层：正片目录锚点
        main_dir = self._resolve_main_dir(lines, source_url)

        # 第4层：分片过滤
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        # 第5层：全滤兜底
        if kept == 0 and removed > 0:
            self.log("广告过滤命中全部分片，判定锚点失效，回退为不过滤模式")
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")

        # 第5层：冗余标签清理
        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"