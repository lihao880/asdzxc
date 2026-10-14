# coding: utf-8
# 站点信息沉淀（法则24）
# 主域名: https://mfeih.cc
# 备用域名: https://xxvv1.tw (国内)
# 发布页: https://mfeih.cc
# 内容类型: 成人短视频聚合站
# 特殊说明: 按网黄/创作者分区；m3u8 AES-128加密；无广告分片
# 最后验证时间: 2026-08-31
# 来源: 用户提供

import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://mfeih.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类硬编码（法则16/17）- 从导航菜单提取主要分类
        self.classes = [
            {"type_id": "cate9", "type_name": "粉色情人"},
            {"type_id": "cate10", "type_name": "Nicolove"},
            {"type_id": "cate11", "type_name": "玩偶姐姐"},
            {"type_id": "cate12", "type_name": "loliiiiipop99"},
            {"type_id": "cate13", "type_name": "柚子猫"},
            {"type_id": "cate14", "type_name": "辛尤里"},
            {"type_id": "cate15", "type_name": "YourPorn国外网黄"},
            {"type_id": "cate18", "type_name": "妲己精选"},
            {"type_id": "cate19", "type_name": "绿帽淫妻"},
            {"type_id": "cate20", "type_name": "纯爱乱伦"},
            {"type_id": "cate21", "type_name": "母狗调教"},
            {"type_id": "cate22", "type_name": "探花大神"},
            {"type_id": "cate23", "type_name": "极品主播"},
            {"type_id": "cate25", "type_name": "强奸/迷奸"},
            {"type_id": "cate26", "type_name": "明星淫梦"},
            {"type_id": "cate27", "type_name": "ASMR"},
            {"type_id": "cate28", "type_name": "美腿丝足"},
            {"type_id": "cate29", "type_name": "经典三级"},
            {"type_id": "cate31", "type_name": "校花女神"},
            {"type_id": "cate32", "type_name": "制服少女"},
            {"type_id": "cate33", "type_name": "尤物萝莉"},
            {"type_id": "cate34", "type_name": "粉红鲍鱼"},
            {"type_id": "cate35", "type_name": "清纯嫩妹"},
            {"type_id": "cate36", "type_name": "少女精选"},
            {"type_id": "cate37", "type_name": "母狗调教"},
            {"type_id": "cate38", "type_name": "处女开苞"},
            {"type_id": "cate39", "type_name": "福利姬"},
            {"type_id": "cate41", "type_name": "Xfree影视"},
            {"type_id": "cate42", "type_name": "麻豆传媒"},
            {"type_id": "cate43", "type_name": "糖心vlog"},
            {"type_id": "cate44", "type_name": "爆款收藏-JVID"},
            {"type_id": "cate45", "type_name": "果冻传媒"},
            {"type_id": "cate46", "type_name": "蜜桃传媒"},
            {"type_id": "cate47", "type_name": "91制片厂"},
            {"type_id": "cate48", "type_name": "星空无限"},
            {"type_id": "cate49", "type_name": "皇家华人"},
            {"type_id": "cate51", "type_name": "天美传媒"},
            {"type_id": "cate52", "type_name": "爱豆传媒"},
            {"type_id": "cate53", "type_name": "扣扣传媒"},
            {"type_id": "cate55", "type_name": "三上悠亞"},
            {"type_id": "cate56", "type_name": "河北彩花"},
            {"type_id": "cate57", "type_name": "渚光希"},
            {"type_id": "cate80", "type_name": "深田咏美"},
            {"type_id": "cate84", "type_name": "桃乃木香奈"},
            {"type_id": "cate87", "type_name": "桥本有菜"},
            {"type_id": "cate95", "type_name": "波多野结衣"},
            {"type_id": "cate126", "type_name": "Team Skeet"},
            {"type_id": "cate127", "type_name": "欧美精选"},
            {"type_id": "cate128", "type_name": "VIXEN"},
            {"type_id": "cate141", "type_name": "近亲乱伦"},
            {"type_id": "cate142", "type_name": "校园师生"},
            {"type_id": "cate147", "type_name": "人妻斩"},
            {"type_id": "cate148", "type_name": "PONDO"},
            {"type_id": "cate149", "type_name": "HEYZO"},
            {"type_id": "cate150", "type_name": "FC2"},
        ]
        # filters 空（站点无分类筛选）
        self.filters = {}
        for cls in self.classes:
            self.filters[cls["type_id"]] = []

    def getName(self):
        return "免费韩主播"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 抓取各分区视频"""
        try:
            resp = self.fetch(self.host + "/", headers=self.headers, timeout=10)
            if not resp:
                return {"list": []}
            html = resp.text or ""
            videos = self._parse_home_videos(html)
            return {"list": videos[:30]}
        except Exception as e:
            self.log({"action": "homeVideoContent", "error": str(e)})
            return {"list": []}

    def _parse_home_videos(self, html):
        """解析首页视频列表"""
        results = []
        # 匹配视频卡片: <a href="/video/数字ID/" ...> 内包含 data-plink 和 img
        pattern = r'<a\s+href="(/video/(\d+)/)"[^>]*>.*?<img[^>]*data-src="([^"]+)"[^>]*>.*?<h3[^>]*>(.*?)</h3>'
        matches = re.findall(pattern, html, re.DOTALL)
        seen = set()
        for match in matches:
            href, vid, pic, title = match
            if vid in seen:
                continue
            seen.add(vid)
            # 清洗标题
            title = re.sub(r'<[^>]+>', '', title).strip()
            results.append({
                "vod_id": vid,
                "vod_name": title[:50] if title else "视频",
                "vod_pic": pic if pic.startswith("http") else (self.host + pic if pic.startswith("/") else pic),
                "vod_remarks": ""
            })
            if len(results) >= 30:
                break
        return results

    def categoryContent(self, tid, pg, filter, extend):
        """分类列表"""
        page = pg or "1"
        try:
            url = f"{self.host}/category/{tid}/{page}/"
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = resp.text or ""
            videos = self._parse_category_videos(html)
            # 获取总页数
            pagecount = self._parse_pagecount(html)
            return {
                "list": videos,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception as e:
            self.log({"action": "categoryContent", "tid": tid, "pg": page, "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def _parse_category_videos(self, html):
        """解析分类页视频列表"""
        results = []
        pattern = r'<a\s+href="(/video/(\d+)/)"[^>]*>.*?<img[^>]*data-src="([^"]+)"[^>]*>.*?<h3[^>]*>(.*?)</h3>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            href, vid, pic, title = match
            title = re.sub(r'<[^>]+>', '', title).strip()
            results.append({
                "vod_id": vid,
                "vod_name": title[:50] if title else "视频",
                "vod_pic": pic if pic.startswith("http") else (self.host + pic if pic.startswith("/") else pic),
                "vod_remarks": ""
            })
        return results

    def _parse_pagecount(self, html):
        """解析总页数"""
        # 方法1: 从分页链接中提取所有页码
        pattern = r'<a[^>]*href="[^"]*/category/\w+/(\d+)/"[^>]*>.*?</a>'
        pages = re.findall(pattern, html)
        if pages:
            return max(int(p) for p in pages)
        # 方法2: 匹配当前页码后面的数字
        pattern2 = r'<li[^>]*class="[^"]*tp5-current[^"]*"[^>]*>.*?(\d+).*?</li>'
        match = re.search(pattern2, html, re.DOTALL)
        if match:
            current = int(match.group(1))
            # 尝试找下一项
            next_match = re.search(r'<li[^>]*>.*?<a[^>]*href="[^"]*/category/\w+/(\d+)/"', html)
            if next_match:
                next_page = int(next_match.group(1))
                # 如果有下一页，说明总页数至少是下一页
                return max(current, next_page)
            return current
        # 方法3: 从底部翻页按钮找最后一个数字
        match = re.search(r'<a[^>]*href="[^"]*/category/\w+/(\d+)/"[^>]*>.*?</a>\s*$', html)
        if match:
            return int(match.group(1))
        return 1

    def detailContent(self, ids):
        """详情页"""
        try:
            vid = ids[0] if ids else ""
            if not vid:
                return {"list": []}
            url = f"{self.host}/video/{vid}/"
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp:
                return {"list": []}
            html = resp.text or ""

            # 提取标题
            title = self._extract_title(html)
            pic = self._extract_poster(html)

            # 提取播放数据 window.__ARCHIVE_PLAYER__
            play_url, duration = self._extract_play_data(html)

            vod = {
                "vod_id": vid,
                "vod_name": title or "视频",
                "vod_pic": pic or "",
                "vod_remarks": duration or "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}" if play_url else ""
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent", "ids": ids, "error": str(e)})
            return {"list": []}

    def _extract_title(self, html):
        """提取标题"""
        match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        if match:
            return re.sub(r'<[^>]+>', '', match.group(1)).strip()
        match = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
        if match:
            title = match.group(1)
            # 移除站点后缀
            title = re.sub(r'\s*-\s*免费韩主播\s*$', '', title)
            return title.strip()
        return ""

    def _extract_poster(self, html):
        """提取封面图"""
        match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        if match:
            return match.group(1)
        match = re.search(r'data-src="([^"]+)"[^>]*>\s*</img>\s*<div[^>]*>.*?<span[^>]*>\d+</span>', html, re.DOTALL)
        if match:
            return match.group(1)
        return ""

    def _extract_play_data(self, html):
        """提取播放数据 - window.__ARCHIVE_PLAYER__"""
        pattern = r'window\.__ARCHIVE_PLAYER__\s*=\s*({[^;]+});'
        match = re.search(pattern, html)
        if not match:
            return "", ""
        try:
            data = json.loads(match.group(1))
            raw_path = data.get("rawPath", "")
            cdn_line = data.get("cdnLine", "https://d32bg2g0w9aqg4.cloudfront.net")
            if raw_path:
                play_url = cdn_line.rstrip("/") + raw_path
                return play_url, ""
        except:
            pass
        return "", ""

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        try:
            keyword = urllib.parse.quote(key)
            url = f"{self.host}/search/{keyword}/"
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp:
                return {"list": [], "page": 1}
            html = resp.text or ""
            results = self._parse_category_videos(html)
            return {"list": results[:50], "page": int(pg)}
        except Exception as e:
            self.log({"action": "searchContent", "key": key, "error": str(e)})
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        """播放"""
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        play_url = str(id).strip()

        # 如果是m3u8地址，走代理
        if play_url.startswith("http") and ".m3u8" in play_url:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(play_url),
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }

        # 如果是m3u8相对路径，补全
        if ".m3u8" in play_url and not play_url.startswith("http"):
            # 用默认CDN补全
            cdn = "https://d32bg2g0w9aqg4.cloudfront.net"
            full_url = cdn + play_url if play_url.startswith("/") else cdn + "/" + play_url
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(full_url),
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }

        # 降级嗅探
        return {"parse": 1, "url": play_url, "header": self.headers}

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址"""
        if not url:
            return ""
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url), safe="")

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def localProxy(self, param):
        """m3u8本地代理 - 五层管线"""
        try:
            # 解析参数（三重兜底）
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

            # 发起请求
            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")

            if not content:
                return [502, "text/plain", b"empty content"]

            # 检测是否为m3u8
            if b"#EXTM3U" not in content[:512]:
                return [200, "application/octet-stream", content]

            # 清洗m3u8（五层管线）
            text = content.decode("utf-8", errors="ignore")
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            self.log({"action": "localProxy", "error": str(e)})
            return [500, "text/plain", f"proxy error: {e}".encode("utf-8", errors="ignore")]

    def _clean_m3u8(self, text, source_url):
        """五层m3u8清洗管线"""
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

        # 第2层：多码率主表透传
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            return self._clean_m3u8_multi(lines, source_url)

        # 第3层：正片目录锚点（KEY URI优先）
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

        # 第5层续：冗余标签清理
        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def _is_fake_image_stream(self, text, source_url):
        """图片流伪装检测"""
        low_url = (source_url or "").lower()
        # 已知图片流服务商特征
        for sig in ("doyinapi", "svip", "imgcdn", "photo"):
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
            else:
                child = urllib.parse.urljoin(source_url, line)
                if ".m3u8" in child.lower():
                    out.append(self._m3u8_proxy_url(child))
                else:
                    out.append(child)
        return "\n".join(out) + "\n"

    def _resolve_main_dir(self, lines, source_url):
        """确定正片目录锚点（KEY URI优先）"""
        import posixpath
        parsed = urllib.parse.urlparse(source_url)
        main_dir = posixpath.dirname(parsed.path)
        if not main_dir.endswith("/"):
            main_dir += "/"

        # 优先以KEY URI目录为锚点
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
        """重写m3u8标签URI"""
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

    def destroy(self):
        pass