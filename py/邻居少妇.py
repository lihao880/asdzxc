# coding: utf-8
"""
站点信息沉淀（法则24）
主域名：https://linjs.cc
备用域名：https://linjs.cc (暂未发现备用域名)
发布页：https://linjs.cc/
内容类型：成人影视聚合站
特殊说明：详情页直接内嵌m3u8地址，使用CDN托管，含AES-128加密KEY
最后验证时间：2026-08-31
来源：用户提供 https://linjs.cc/
m3u8结构摘要：单码率，无广告分片，KEY目录为/keyhome/
"""

import re
import json
from urllib.parse import urljoin, quote, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        # __init__ 零网络依赖（法则16）
        self.host = "https://linjs.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        
        # 分类硬编码（法则16/17）
        self.classes = [
            {"type_id": "3", "type_name": "顶级网黄"},
            {"type_id": "4", "type_name": "福利姬"},
            {"type_id": "5", "type_name": "主播勾引"},
            {"type_id": "6", "type_name": "传媒精选"},
            {"type_id": "7", "type_name": "JVID"},
            {"type_id": "8", "type_name": "锅锅酱"},
            {"type_id": "9", "type_name": "巨乳大奶"},
            {"type_id": "10", "type_name": "抖音风"},
            {"type_id": "11", "type_name": "制服诱惑"},
            {"type_id": "12", "type_name": "樱花小猫"},
            {"type_id": "13", "type_name": "反差女友"},
            {"type_id": "14", "type_name": "探花约炮"},
            {"type_id": "15", "type_name": "调教性奴"},
            {"type_id": "16", "type_name": "ASMR"},
            {"type_id": "17", "type_name": "颜值网红"},
            {"type_id": "18", "type_name": "高潮自慰"},
            {"type_id": "19", "type_name": "欧美洋马"},
            {"type_id": "20", "type_name": "露出野战"},
            {"type_id": "21", "type_name": "SWAG"},
            {"type_id": "22", "type_name": "热门吃瓜"},
            {"type_id": "23", "type_name": "绿帽淫妻"},
            {"type_id": "24", "type_name": "群交滥交"},
            {"type_id": "25", "type_name": "风骚少妇"},
            {"type_id": "26", "type_name": "逆天乱伦"},
            {"type_id": "27", "type_name": "AI女神"},
            {"type_id": "28", "type_name": "风骚母狗"},
            {"type_id": "29", "type_name": "断袖男同"},
            {"type_id": "30", "type_name": "原创短剧"},
            {"type_id": "31", "type_name": "足交口爆"},
            {"type_id": "32", "type_name": "炮桶小屋"},
            {"type_id": "33", "type_name": "无套内射"},
            {"type_id": "34", "type_name": "黑鬼长屌"},
            {"type_id": "35", "type_name": "女同百合"},
            {"type_id": "36", "type_name": "伪娘人妖"},
            {"type_id": "37", "type_name": "吴梦梦"},
        ]
        
        # 空 filters（站点无筛选入口，法则3.2）
        self.filters = {}
        for cls in self.classes:
            self.filters[cls["type_id"]] = []

    def getName(self):
        return "邻居少妇"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # init 零网络依赖（法则2）
        self.extend = extend or ""

    def destroy(self):
        # 释放资源（法则21）
        pass

    def homeContent(self, filter):
        # 首页零网络依赖（法则6/16）
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 首页推荐（法则7）
        url = self.host + "/"
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": []}
        
        html = resp.text
        items = self._parse_video_list(html, is_home=True)
        return {"list": items}

    def categoryContent(self, tid, pg, filter, extend):
        # 分类列表（法则6/19）
        page = pg or "1"
        url = f"{self.host}/category/cate{tid}/{page}/"
        
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        
        html = resp.text
        items = self._parse_video_list(html, is_home=False)
        
        # 提取分页信息
        pagecount = self._parse_pagecount(html)
        
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20
        }

    def detailContent(self, ids):
        # 详情页（法则9/19）
        if not ids:
            return {"list": []}
        
        vid = ids[0]
        url = f"{self.host}/video/{vid}/"
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": []}
        
        html = resp.text
        
        # 提取标题
        title = self._extract_title(html) or "未知视频"
        
        # 提取观看数
        views = self._extract_views(html) or "0"
        
        # 提取 m3u8 地址（核心）
        m3u8_url = self._extract_m3u8(html)
        
        # 构建播放数据
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": self._extract_cover(html),
            "vod_remarks": views + " 观看",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "CDN播放",
            "vod_play_url": f"播放${m3u8_url}" if m3u8_url else ""
        }
        
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        # 搜索（法则25）
        if not key:
            return {"list": [], "page": 1}
        
        page = pg or "1"
        url = f"{self.host}/search/{key}/{page}/"
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": [], "page": int(page)}
        
        html = resp.text
        items = self._parse_video_list(html, is_home=False)
        
        return {"list": items, "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        # 播放（法则5/7/27）
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        
        # 如果是相对路径，补全为绝对地址
        if not id.startswith(("http://", "https://")):
            # 尝试补全为 CDN 地址（从详情页的 data-url 格式推断）
            # 但这里无法从 id 反推完整 CDN 地址，因为缺少路径前缀
            # 实际上壳端传入的 id 可能是完整的 m3u8 相对路径，需要拼接 host
            # 但 host 是网站域名，不是 CDN 域名，所以需要从 id 本身判断
            # 如果 id 以 /video/ 开头，说明是站内相对路径，直接补全域名
            if id.startswith("/"):
                full_url = self.host + id
            else:
                full_url = urljoin(self.host, id)
            
            # 检查是否为 m3u8
            if ".m3u8" in full_url:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(full_url),
                    "header": {"User-Agent": self.headers["User-Agent"]}
                }
        
        # 如果已经是完整 m3u8 地址，直接走代理
        if id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id),
                "header": {"User-Agent": self.headers["User-Agent"]}
            }
        
        # 否则视为需要跳转的播放页ID，降级到 parse:1（法则27）
        return {
            "parse": 1,
            "url": id,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/"
            }
        }

    def recommendContent(self, ids, pg):
        # 相关推荐
        if not ids:
            return {"list": []}
        
        # 从详情页提取推荐列表
        vid = ids[0] if isinstance(ids, list) else ids
        url = f"{self.host}/video/{vid}/"
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": []}
        
        html = resp.text
        items = self._parse_video_list(html, is_home=False)
        return {"list": items}

    def localProxy(self, params):
        """m3u8 本地代理 + 五层去广告管线（法则30）"""
        target = self._parse_proxy_params(params)
        if not target or not target.startswith(("http://", "https://")):
            return [400, "text/plain", b"invalid url"]
        
        try:
            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp or resp.status_code != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            
            content = resp.content
            if not content:
                return [502, "text/plain", b"empty content"]
            
            # 检查是否为 m3u8
            if b"#EXTM3U" not in content[:256]:
                # 非 m3u8 直接透传
                return [200, "application/octet-stream", content]
            
            text = content.decode("utf-8", errors="ignore")
            cleaned = self._clean_m3u8(text, target)
            
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]

    # ==================== 辅助方法 ====================

    def _parse_proxy_params(self, params):
        """解析 localProxy 参数（兼容 dict/字符串/url= 前缀）"""
        if isinstance(params, dict):
            target = params.get("url", "") or params.get("source", "")
        else:
            target = str(params or "")
        
        if target.startswith("url="):
            target = target[4:]
        elif "url=" in target:
            qs = {}
            for part in target.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    qs[k] = v
            target = qs.get("url", target)
        
        return unquote(str(target or ""))

    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址"""
        return "http://127.0.0.1:9978/proxy?do=py&url=" + quote(str(url or ""), safe="")

    def _parse_video_list(self, html, is_home=False):
        """解析视频列表（过滤广告 item）"""
        items = []
        
        # 匹配视频项
        # 非广告项：li class="stui-vodlist__item" 不含 module-two
        # 广告项有 module-two 类，直接跳过
        pattern = r'<li\s+class="stui-vodlist__item[^"]*"(?![^>]*module-two[^>]*>).*?<a\s+class="stui-vodlist__thumb"[^>]*href="([^"]+)"[^>]*>\s*<img[^>]*data-original="([^"]+)"[^>]*>.*?<h4[^>]*><a[^>]*>([^<]+)</a></h4>.*?<strong>([^<]+)</strong>'
        
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            link, pic, title, remark = match
            # 只保留站内视频链接（过滤外链广告）
            if not link.startswith("/video/"):
                continue
            vod_id = link.replace("/video/", "").strip("/")
            items.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": remark.strip()
            })
        
        return items[:30]  # 限制数量

    def _parse_pagecount(self, html):
        """提取总页数"""
        # 查找分页中的最大页码
        pattern = r'<a[^>]*href="[^"]*/cate\d+/(\d+)/"[^>]*>\s*(\d+)\s*</a>'
        matches = re.findall(pattern, html)
        if matches:
            pages = [int(m[1]) for m in matches if m[1].isdigit()]
            if pages:
                return max(pages)
        
        # 查找 "共X页" 或 "尾页"
        pattern2 = r'尾页[^<]*</a>\s*</div>|共\s*(\d+)\s*页'
        m2 = re.search(pattern2, html)
        if m2 and m2.group(1):
            return int(m2.group(1))
        
        return 1

    def _extract_title(self, html):
        """提取标题"""
        pattern = r'<span\s+class="title">([^<]+)</span>'
        m = re.search(pattern, html)
        if m:
            return m.group(1).strip()
        return None

    def _extract_views(self, html):
        """提取观看数"""
        pattern = r'<span\s+class="people"><em>([^<]+)</em>\s*次观看</span>'
        m = re.search(pattern, html)
        if m:
            return m.group(1).strip()
        return None

    def _extract_cover(self, html):
        """提取封面图"""
        pattern = r'<meta\s+property="og:image"\s+content="([^"]+)"'
        m = re.search(pattern, html)
        if m:
            return m.group(1)
        return ""

    def _extract_m3u8(self, html):
        """提取 m3u8 地址（从 data-url 和 data-cdnline 拼接）"""
        # 提取 cdnline
        cdn_pattern = r'<div[^>]*id="article-videos"[^>]*data-cdnline="([^"]+)"'
        cdn_match = re.search(cdn_pattern, html)
        cdn_base = cdn_match.group(1) if cdn_match else "https://d32bg2g0w9aqg4.cloudfront.net"
        
        # 提取 m3u8 路径
        url_pattern = r'<div[^>]*id="article-videos"[^>]*data-url="([^"]+\.m3u8)"'
        url_match = re.search(url_pattern, html)
        if url_match:
            m3u8_path = url_match.group(1)
            if m3u8_path.startswith(("http://", "https://")):
                return m3u8_path
            return urljoin(cdn_base, m3u8_path)
        
        # 备用：从 player 配置中提取
        pattern2 = r'"video"\s*:\s*\{[^}]*"url"\s*:\s*"([^"]+\.m3u8)"'
        m2 = re.search(pattern2, html)
        if m2:
            url = m2.group(1)
            if url.startswith(("http://", "https://")):
                return url
            return urljoin(cdn_base, url)
        
        return None

    # ==================== m3u8 五层去广告管线（法则30）====================

    def _clean_m3u8(self, text, source_url):
        """五层去广告管线"""
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 第1层：图片流伪装检测
        if self._is_fake_image_stream(text, source_url):
            restored = text
            for ext in (".png", ".jpeg", ".jpg", ".webp"):
                restored = restored.replace(ext, ".ts")
            return restored

        # 第2层：多码率主表透传
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            return self._clean_m3u8_multi(lines, source_url)

        # 第3层：正片目录锚点（KEY URI 目录优先）
        main_dir = self._resolve_main_dir(lines, source_url)

        # 第4层：分片过滤
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        # 第5层：全滤兜底
        if kept == 0 and removed > 0:
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            pass  # 可在日志中记录

        # 第5层：冗余标签清理
        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def _is_fake_image_stream(self, text, source_url):
        """第1层：图片流伪装检测"""
        low_url = (source_url or "").lower()
        # 依据1：已知图片流服务商特征
        for sig in ("doyinapi", "svip", "imgcdn", "photo"):
            if sig in low_url:
                return True
        # 依据2：分片扩展名为图片格式
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower().split("?")[0]
            if low.endswith((".png", ".jpg", ".jpeg", ".webp")):
                return True
        return False

    def _clean_m3u8_multi(self, lines, source_url):
        """第2层：多码率主表处理"""
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

    def _resolve_main_dir(self, lines, source_url):
        """第3层：正片目录锚点（KEY URI 目录优先）"""
        import posixpath
        parsed = urlparse(source_url)
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
            key_path = urlparse(
                key_uri if key_uri.startswith("http") else urljoin(source_url, key_uri)
            ).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return main_dir

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

    def _rewrite_m3u8_tag(self, line, source_url):
        """补全标签中的 URI 为绝对地址"""
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)
        return line


# 兼容 urlparse
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse