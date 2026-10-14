# coding: utf-8
# 站点信息：水仙视频
# 主域名：https://etcsdp.sxsp3.top
# 备用域名：无
# 发布页：https://ejj.dpgc6.com/z/
# 内容类型：成人视频
# 特殊说明：图片流伪装（分片扩展名为.jpg），仅还原扩展名，不过滤广告
# 验证时间：2026-09-01
# 来源：etcsdp.sxsp3.top

import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://etcsdp.sxsp3.top"
        self.extend = ""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类列表（从首页导航栏提取）
        self.classes = [
            {"type_id": "20", "type_name": "日韩"},
            {"type_id": "21", "type_name": "偷拍"},
            {"type_id": "22", "type_name": "无码"},
            {"type_id": "23", "type_name": "自拍"},
            {"type_id": "24", "type_name": "巨乳"},
            {"type_id": "25", "type_name": "华人"},
            {"type_id": "26", "type_name": "嫩模"},
            {"type_id": "27", "type_name": "剧情"},
            {"type_id": "28", "type_name": "动漫"},
            {"type_id": "29", "type_name": "熟女"},
            {"type_id": "30", "type_name": "丝袜"},
            {"type_id": "32", "type_name": "欧美"},
            {"type_id": "33", "type_name": "有码"},
            {"type_id": "34", "type_name": "制服"},
            {"type_id": "35", "type_name": "口交"},
            {"type_id": "31", "type_name": "三级"}
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}
        # 图片缓存：{片名: 图片URL}
        self._pic_cache = {}

    def getName(self):
        return "水仙视频"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 从首页获取推荐列表（包括Banner图片），同时建立图片缓存
        try:
            resp = self.fetch(self.host + "/cn/home/web/", headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            items = []
            # 1. 从 Banner 区域提取带图片的视频，并建立缓存
            banner_pattern = r'<div style="width:50%;">\s*<a href="([^"]+)" title="([^"]*)">\s*<img[^>]+src="([^"]+)"'
            banner_matches = re.findall(banner_pattern, html, re.DOTALL)
            for link, title, pic in banner_matches:
                if not title:
                    continue
                vod_id_match = re.search(r'/(\d+)\.html', link)
                if not vod_id_match:
                    continue
                if not pic.startswith("http"):
                    pic = urllib.parse.urljoin(self.host, pic)
                # 存入缓存（用标题作为key）
                if title.strip():
                    self._pic_cache[title.strip()] = pic
                items.append({
                    "vod_id": vod_id_match.group(1),
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": "推荐"
                })
            # 2. 从列表区域提取（无图片，但可以通过标题匹配缓存）
            list_items = self._parse_list(html, self.host)
            # 为列表项匹配图片（通过标题匹配缓存）
            for item in list_items:
                if item["vod_name"] and item["vod_name"] in self._pic_cache:
                    item["vod_pic"] = self._pic_cache[item["vod_name"]]
            # 合并，去重（按vod_id）
            seen = set()
            merged = []
            for item in items + list_items:
                if item["vod_id"] not in seen:
                    seen.add(item["vod_id"])
                    merged.append(item)
            return {"list": merged[:30] if merged else []}
        except Exception as e:
            self.log({"action": "homeVideoContent", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        # 确保图片缓存已加载
        if not self._pic_cache:
            self._load_pic_cache()
        url = f"{self.host}/vodtype/{tid}-{page}.html"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = resp.text
            items = self._parse_list(html, self.host)
            pagecount = self._parse_pagecount(html)
            if pagecount < 1:
                pagecount = 14
            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception as e:
            self.log({"action": "categoryContent", "tid": tid, "pg": page, "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        # ids 是列表，取第一个作为视频ID
        if not ids:
            return {"list": []}
        vod_id = str(ids[0]).strip()
        url = f"{self.host}/{vod_id}.html"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            # 提取标题
            title_match = re.search(r'<h1 class="title">([^<]+)</h1>', html)
            title = title_match.group(1).strip() if title_match else "未知标题"
            # 提取分类
            type_match = re.search(r'<p class="data">.*?类型：([^<]+)</p>', html)
            category = type_match.group(1).strip() if type_match else ""
            # 提取封面图：优先从页面提取，如果没有则从缓存匹配
            pic = ""
            # 尝试从 stui-content__thumb 区域提取
            pic_match = re.search(r'<div class="stui-content__thumb">.*?<img[^>]+src="([^"]+)"', html, re.DOTALL)
            if pic_match:
                pic = pic_match.group(1)
                if not pic.startswith("http"):
                    pic = urllib.parse.urljoin(self.host, pic)
            # 如果页面没有图片，从缓存匹配（通过标题）
            if not pic and title and title in self._pic_cache:
                pic = self._pic_cache[title]
            # 提取播放地址
            play_url = self._extract_play_url(html)
            if not play_url:
                return {"list": []}
            # 构建播放树
            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": category,
                "vod_content": "",
                "vod_play_from": "直链",
                "vod_play_url": f"播放${play_url}"
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent", "vod_id": vod_id, "error": str(e)})
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        # 确保图片缓存已加载
        if not self._pic_cache:
            self._load_pic_cache()
        page = pg or "1"
        encoded_key = urllib.parse.quote(key)
        url = f"{self.host}/s/index.html?wd={encoded_key}"
        if page != "1":
            url = f"{self.host}/s/{encoded_key}/page/{page}.html"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": int(page)}
            html = resp.text
            items = self._parse_list(html, self.host)
            return {"list": items, "page": int(page)}
        except Exception as e:
            self.log({"action": "searchContent", "key": key, "error": str(e)})
            return {"list": [], "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        # id 就是播放地址
        play_url = str(id).strip()
        if not play_url:
            return {"parse": 0, "url": "", "header": {}}
        # 如果是m3u8地址，走代理清洗（图片流伪装，只还原扩展名）
        if ".m3u8" in play_url.lower():
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(play_url),
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        # 其他直接返回
        return {"parse": 0, "url": play_url, "header": {"User-Agent": self.headers.get("User-Agent", "")}}

    def recommendContent(self, ids, pg):
        # 从详情页提取相关推荐
        if not ids:
            return {"list": []}
        vod_id = str(ids[0]).strip()
        url = f"{self.host}/{vod_id}.html"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            items = []
            # 相关推荐在 <ul class="stui-content__playlist clearfix"> 中
            pattern = r'<ul\s+class="stui-content__playlist[^"]*clearfix">(.*?)</ul>'
            ul_match = re.search(pattern, html, re.DOTALL)
            if ul_match:
                ul_html = ul_match.group(1)
                li_pattern = r'<li>.*?<a\s+href="([^"]+)"\s+title="([^"]*)"'
                matches = re.findall(li_pattern, ul_html, re.DOTALL)
                for link, title in matches:
                    if not title:
                        continue
                    vod_id_match = re.search(r'/(\d+)\.html', link)
                    if not vod_id_match:
                        continue
                    items.append({
                        "vod_id": vod_id_match.group(1),
                        "vod_name": title.strip(),
                        "vod_pic": "",
                        "vod_remarks": ""
                    })
            return {"list": items[:20] if items else []}
        except Exception as e:
            self.log({"action": "recommendContent", "error": str(e)})
            return {"list": []}

    def destroy(self):
        pass

    # ========== 内部方法 ==========

    def _load_pic_cache(self):
        """加载图片缓存（从首页Banner提取）"""
        if self._pic_cache:
            return
        try:
            resp = self.fetch(self.host + "/cn/home/web/", headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return
            html = resp.text
            banner_pattern = r'<div style="width:50%;">\s*<a href="[^"]+" title="([^"]*)">\s*<img[^>]+src="([^"]+)"'
            matches = re.findall(banner_pattern, html, re.DOTALL)
            for title, pic in matches:
                if title and title.strip():
                    if not pic.startswith("http"):
                        pic = urllib.parse.urljoin(self.host, pic)
                    self._pic_cache[title.strip()] = pic
            self.log(f"图片缓存已加载: {len(self._pic_cache)} 条")
        except Exception as e:
            self.log(f"加载图片缓存失败: {e}")
    def _parse_list(self, html, base_url):
        """解析列表页（分类页/首页/搜索页共用），自动从缓存匹配图片"""
        items = []
        pattern = r'<li\s+class="clearfix">(.*?)</li>'
        li_matches = re.findall(pattern, html, re.DOTALL)
        for li_html in li_matches:
            if '影片名称' in li_html:
                continue
            title_match = re.search(r'<h3\s+class="title[^"]*">.*?<a\s+href="([^"]+)"\s+title="([^"]*)"', li_html, re.DOTALL)
            if not title_match:
                continue
            link = title_match.group(1)
            title = title_match.group(2).strip()
            if not title:
                text_match = re.search(r'<a[^>]*>([^<]+)</a>', li_html)
                if text_match:
                    title = text_match.group(1).strip()
            if not title or not link:
                continue
            type_match = re.search(r'<span\s+class="type">.*?<a[^>]*>([^<]+)</a>', li_html)
            type_name = type_match.group(1).strip() if type_match else ""
            time_match = re.search(r'<span\s+class="time">([^<]+)</span>', li_html)
            remark = time_match.group(1).strip() if time_match else ""
            if not link.startswith("http"):
                if link.startswith("/"):
                    link = base_url + link
                else:
                    link = urllib.parse.urljoin(base_url, link)
            vod_id_match = re.search(r'/(\d+)\.html', link)
            if not vod_id_match:
                continue
            vod_id = vod_id_match.group(1)
            # 尝试从li中提取图片
            pic = ""
            img_match = re.search(r'<img[^>]+src="([^"]+)"', li_html)
            if img_match:
                pic = img_match.group(1)
                if not pic.startswith("http"):
                    pic = urllib.parse.urljoin(base_url, pic)
            # 如果li中没有图片，从缓存匹配（通过标题）
            if not pic and title and title in self._pic_cache:
                pic = self._pic_cache[title]
            items.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark or type_name
            })
        return items

    def _parse_pagecount(self, html):
        """从页面脚本中提取总页数"""
        # 查找 select 循环中的 i<X
        pattern = r'for\s*\(\s*var\s+i\s*=\s*0\s*;\s*i\s*<\s*(\d+)\s*;\s*i\+\+'
        match = re.search(pattern, html)
        if match:
            return int(match.group(1))
        # 查找尾页链接中的数字
        pattern2 = r'/vodtype/\d+-(\d+)\.html".*?尾页'
        match2 = re.search(pattern2, html)
        if match2:
            return int(match2.group(1))
        return 14

    def _extract_play_url(self, html):
        """从详情页提取播放地址"""
        # 提取 rawUrl
        pattern = r"const\s+rawUrl\s*=\s*'([^']+)'"
        match = re.search(pattern, html)
        if match:
            raw = match.group(1)
            # 进一步提取 m3u8 URL
            m3u8_match = re.search(r'(https?://[^\s$#]+\.m3u8(?:\?[^\s#]*)?)', raw)
            if m3u8_match:
                return m3u8_match.group(1)
            return raw
        # 如果没找到 rawUrl，尝试其他模式
        pattern2 = r'url:\s*["\']([^"\']+\.m3u8[^"\']*)["\']'
        match2 = re.search(pattern2, html)
        if match2:
            return match2.group(1)
        return ""

    def _parse_recommend(self, html):
        """解析相关推荐"""
        items = []
        # 相关推荐在 <ul class="stui-content__playlist clearfix"> 中
        pattern = r'<ul\s+class="stui-content__playlist[^"]*clearfix">(.*?)</ul>'
        ul_match = re.search(pattern, html, re.DOTALL)
        if not ul_match:
            return []
        ul_html = ul_match.group(1)
        # 提取每个 a 标签
        a_pattern = r'<a\s+href="([^"]+)"\s+title="([^"]*)"'
        matches = re.findall(a_pattern, ul_html)
        for link, title in matches[:20]:
            if not title:
                continue
            vod_id_match = re.search(r'/(\d+)\.html', link)
            if not vod_id_match:
                continue
            items.append({
                "vod_id": vod_id_match.group(1),
                "vod_name": title.strip(),
                "vod_pic": "",
                "vod_remarks": ""
            })
        return items

    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址"""
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def localProxy(self, param):
        """m3u8 本地代理：图片流伪装站点，先还原扩展名，再过滤广告分片"""
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

            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp or resp.status_code != 200:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]

            # 检查是否为 m3u8
            if b"#EXTM3U" not in content[:256]:
                return [200, "application/octet-stream", content]

            text = content.decode("utf-8", errors="ignore")

            # 第1层：图片流伪装检测 - 先还原扩展名
            is_fake = self._is_fake_image_stream(text, target)
            if is_fake:
                self.log("检测到图片流伪装，还原扩展名 .jpg/.png -> .ts")
                # 还原扩展名（.jpeg 必须先于 .jpg）
                for ext in (".png", ".jpeg", ".jpg", ".webp"):
                    text = text.replace(ext, ".ts")
                # 重新分割行
                lines = [l.strip() for l in text.replace("\r", "").split("\n") if l.strip()]
                if not lines:
                    return [200, "application/vnd.apple.mpegurl", b"#EXTM3U\n"]
            else:
                lines = [l.strip() for l in text.replace("\r", "").split("\n") if l.strip()]

            # 第2层：多码率判断
            if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
                out = []
                for line in lines:
                    if line.startswith("#"):
                        out.append(line)
                    else:
                        child = urllib.parse.urljoin(target, line)
                        if ".m3u8" in child.lower():
                            out.append(self._m3u8_proxy_url(child))
                        else:
                            out.append(child)
                return [200, "application/vnd.apple.mpegurl", "\n".join(out).encode("utf-8")]

            # 第3层：正片目录锚点（KEY URI 目录优先）
            main_dir = self._resolve_main_dir(lines, target)

            # 第4层：分片过滤（图片流已还原扩展名，现在按目录过滤）
            segments, removed, kept = self._filter_segments(lines, target, main_dir)

            # 第5层：全滤兜底
            if removed > 0 and (kept == 0 or removed > kept):
                self.log(f"广告过滤命中过多分片(滤{removed}/留{kept})，判定锚点失效，回退为不过滤模式")
                out = [self._rewrite_m3u8_tag(l, target) for l in lines]
                return [200, "application/vnd.apple.mpegurl", "\n".join(out).encode("utf-8")]

            if removed:
                self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")
            else:
                self.log(f"m3u8无广告分片，保留正片: {kept}个")

            # 第5层：冗余标签清理
            out = self._dedup_tags(segments, target)
            return [200, "application/vnd.apple.mpegurl", "\n".join(out).encode("utf-8")]

        except Exception as e:
            self.log(f"localProxy error: {e}")
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]

    def _is_fake_image_stream(self, text, source_url):
        """检测图片流伪装"""
        low_url = (source_url or "").lower()
        # 已知图片流服务商特征
        for sig in ("doyinapi", "svip", "imgcdn", "photo", "thm3u8", "jpg"):
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

    def _resolve_main_dir(self, lines, source_url):
        """解析正片目录锚点：KEY URI 目录优先"""
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
        """冗余标签清理"""
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