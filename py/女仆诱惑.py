# coding: utf-8
# 女仆诱惑 影视爬虫 - MacCMS 标准站
# 站点: https://heping616.npyh1.lol/nv/

import re
import json
import urllib.parse
import posixpath
from urllib.parse import quote, urlencode

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://heping616.npyh1.lol/nv"
        self.site_name = "女仆诱惑"
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
            {"type_id": "54", "type_name": "少女萝莉"},
            {"type_id": "55", "type_name": "SM调教"},
            {"type_id": "56", "type_name": "绝顶潮吹"},
            {"type_id": "58", "type_name": "时间停止"},
            {"type_id": "59", "type_name": "漫改系列"},
            {"type_id": "60", "type_name": "电车痴汉"},
            {"type_id": "61", "type_name": "淫欲痴女"},
            {"type_id": "62", "type_name": "AI换脸"},
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
            {"type_id": "90", "type_name": "网红头条"},
            {"type_id": "91", "type_name": "网爆黑料"},
            {"type_id": "92", "type_name": "欧美无码"},
            {"type_id": "93", "type_name": "女优明星"},
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }

    def getName(self):
        return "女仆诱惑"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/")
        items = self._parse_video_list(html)
        return {"list": items[:12]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg) if pg else "1"
        url = f"{self.host}/vodtype/{tid}.html?page={pg}"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        page_count = self._parse_page_count(html)
        return {
            "list": items,
            "page": int(pg),
            "pagecount": page_count,
            "limit": 20,
            "total": page_count * 20,
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        # ids[0] 可能是纯ID，也可能是打包字符串
        raw = str(ids[0])
        # 尝试解包：格式为 "id|$|name|$|pic|$|remark"
        if '|$|' in raw:
            parts = raw.split('|$|')
            vid = parts[0]
            name = parts[1] if len(parts) > 1 else f"视频{vid}"
            pic = parts[2] if len(parts) > 2 else ""
            remark = parts[3] if len(parts) > 3 else ""
        else:
            vid = raw
            name = f"视频{vid}"
            pic = ""
            remark = ""
        
        play_url = f"{self.host}/vodplay/{vid}-1-1.html"
        
        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}",
        }
        return {"list": [vod]}
    def searchContent(self, key, quick, pg="1"):
        pg = str(pg) if pg else "1"
        url = f"{self.host}/vodsearch/-------------.html?wd={quote(key)}&page={pg}"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags=[]):
        # 确保 id 是字符串
        if not isinstance(id, str):
            id = str(id)
        # 处理转义字符
        id = id.replace("\\/", "/")
        # 直接返回原始 m3u8，不经过代理（沙盒限制，无法过滤广告）
        if id and id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0, 
                "url": id, 
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        # 如果id是vodplay URL，请求页面提取m3u8
        if id and id.startswith("http"):
            html = self._fetch_html(id)
            play_url = self._extract_m3u8_from_html(html)
            if play_url:
                play_url = play_url.replace("\\/", "/")
                return {
                    "parse": 0, 
                    "url": play_url, 
                    "header": {"User-Agent": self.headers.get("User-Agent", "")}
                }
            return {"parse": 1, "url": id, "header": self.headers}
        # 如果id是vod_id，尝试获取m3u8
        detail_url = f"{self.host}/vodplay/{id}-1-1.html"
        html = self._fetch_html(detail_url)
        play_url = self._extract_m3u8_from_html(html)
        if play_url:
            play_url = play_url.replace("\\/", "/")
            return {
                "parse": 0, 
                "url": play_url, 
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        return {"parse": 1, "url": detail_url, "header": self.headers}
    def recommendContent(self, ids, pg=1):
        """推荐内容 - 从详情页提取相关推荐"""
        if not ids:
            return {"list": []}
        vid = str(ids[0]) if isinstance(ids, list) else str(ids)
        detail_url = f"{self.host}/voddetail/{vid}.html"
        html = self._fetch_html(detail_url)
        items = self._parse_recommend_list(html)
        return {"list": items}

    def destroy(self):
        """释放资源"""
        pass

    def getProxyUrl(self):
        """获取本地代理地址"""
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址"""
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        """
        m3u8本地代理 - 广告分片过滤
        使用 requests 替代 self.fetch（解决沙盒超时问题）
        """
        import requests
        try:
            # 兼容 url 和 source 两种参数名
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            # 使用 requests 获取 m3u8（绕过沙盒限制）
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": self.host + "/",
                "Accept": "*/*",
                "Accept-Encoding": "identity",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
                "Origin": self.host,
            }
            
            resp = requests.get(target, headers=headers, timeout=30, verify=False)
            if resp.status_code != 200:
                return [502, "text/plain", f"fetch failed: {resp.status_code}".encode()]

            content = resp.content
            if not content:
                return [502, "text/plain", b"empty content"]

            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]
    def _clean_m3u8(self, text, source_url):
        """清洗m3u8 - 过滤广告分片"""
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
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

        main_dir = source_dir
        for line in lines:
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                uri_match = re.search(r'URI="([^"]+)"', line)
                if uri_match:
                    key_path = uri_match.group(1)
                    if not key_path.startswith("http"):
                        key_dir = posixpath.dirname(key_path)
                        if key_dir and key_dir != "/":
                            main_dir = key_dir + "/"
                            break

        segments = []
        pending = []

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urllib.parse.urljoin(source_url, line)
                media_parsed = urllib.parse.urlparse(media_url)
                is_ad = not media_parsed.path.startswith(main_dir)
                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urllib.parse.urljoin(source_url, line))
            else:
                segments.append(line)

        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI（补全绝对地址）"""
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

    def _fetch_html(self, url, params=None):
        full_url = url
        if params:
            if "?" in url:
                full_url = url + "&" + urlencode(params)
            else:
                full_url = url + "?" + urlencode(params)
        try:
            # 不强制压缩，让服务器返回默认格式
            headers = self.headers.copy()
            resp = self.fetch(full_url, headers=headers, timeout=15)
            if resp:
                # 尝试多种方式获取内容
                text = None
                if hasattr(resp, "text") and resp.text:
                    text = resp.text
                elif hasattr(resp, "content") and resp.content:
                    try:
                        text = resp.content.decode("utf-8", errors="ignore")
                    except:
                        pass
                if text:
                    return text
                # 如果都为空，尝试从 raw 读取
                if hasattr(resp, "raw") and resp.raw:
                    try:
                        raw_data = resp.raw.read()
                        return raw_data.decode("utf-8", errors="ignore")
                    except:
                        pass
        except Exception as e:
            pass
        return ""
    def _parse_video_list(self, html):
        items = []
        if not html:
            return items
        # 匹配视频列表项
        pattern = r'<a[^>]*href="[^"]*voddetail/(\d+)\.html[^"]*"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"'
        matches = re.findall(pattern, html, re.DOTALL)
        for vid, pic, title in matches:
            if vid:
                # 打包 vod_id，包含标题和图片信息
                # 格式: id|$|name|$|pic|$|remark
                remark = ""
                packed_id = f"{vid}|$|{title.strip()}|$|{pic if pic.startswith('http') else self.host + pic}|$|{remark}"
                items.append({
                    "vod_id": packed_id,
                    "vod_name": title.strip(),
                    "vod_pic": pic if pic.startswith("http") else self.host + pic,
                    "vod_remarks": remark
                })
        # 备用匹配模式
        if not items:
            pattern2 = r'<a[^>]*href="/nv/voddetail/(\d+)\.html"[^>]*>([^<]+)</a>'
            matches2 = re.findall(pattern2, html)
            for vid, title in matches2:
                packed_id = f"{vid}|$|{title.strip()}|$||$|"
                items.append({
                    "vod_id": packed_id,
                    "vod_name": title.strip(),
                    "vod_pic": "",
                    "vod_remarks": ""
                })
        return items
    def _parse_page_count(self, html):
        if not html:
            return 1
        pattern = r'<a[^>]*data-num="[^"]*"[^>]*>(\d+)</a>'
        matches = re.findall(pattern, html)
        if matches:
            return int(matches[-1])
        return 1

    def _extract_m3u8_from_html(self, html):
        if not html:
            return None
        # 方法1: 从 player_aaaa 中提取
        pattern = r'var\s+player_aaaa\s*=\s*(\{[^;]+\});'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                url = data.get("url", "")
                if url and url.startswith("http"):
                    return url
            except Exception:
                pass
        # 方法2: 从 playurl 变量中提取
        pattern2 = r'var\s+playurl\s*=\s*["\']([^"\']+)["\']'
        match2 = re.search(pattern2, html)
        if match2:
            url = match2.group(1)
            if url and url.startswith("http"):
                return url
        # 方法3: 直接提取url字段
        pattern3 = r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"'
        match3 = re.search(pattern3, html)
        if match3:
            url = match3.group(1)
            if url and url.startswith("http"):
                return url
        # 方法4: 查找任何m3u8链接
        pattern4 = r'https?://[^"\']+\.m3u8[^"\']*'
        match4 = re.search(pattern4, html)
        if match4:
            return match4.group(0)
        return None
    def _extract_title_from_html(self, html):
        if not html:
            return ""
        pattern = r'<title>([^<]+)</title>'
        match = re.search(pattern, html)
        if match:
            title = match.group(1)
            # 去除站点后缀
            title = re.sub(r'\s*--\s*女仆诱惑$', '', title)
            return title.strip()
        return ""

    def _extract_pic_from_html(self, html):
        if not html:
            return ""
        pattern = r'<img[^>]*class="[^"]*pic[^"]*"[^>]*src="([^"]+)"'
        match = re.search(pattern, html)
        if match:
            pic = match.group(1)
            if pic.startswith("http"):
                return pic
            return self.host + pic
        return ""

    def _extract_remark_from_html(self, html):
        if not html:
            return ""
        pattern = r'<span[^>]*class="[^"]*remarks[^"]*"[^>]*>([^<]+)</span>'
        match = re.search(pattern, html)
        if match:
            return match.group(1).strip()
        return ""

    def _parse_recommend_list(self, html):
        items = []
        if not html:
            return items
        # 匹配相关推荐列表
        pattern = r'<li>.*?<a[^>]*href="/nv/voddetail/(\d+)\.html"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"'
        matches = re.findall(pattern, html, re.DOTALL)
        for vid, pic, title in matches:
            # 从 title 中提取纯标题（去除额外信息）
            clean_title = title.strip()
            if not clean_title:
                # 如果 alt 为空，从后面的 h5 中提取
                h5_pattern = r'<h5><a[^>]*title="([^"]*)"'
                h5_match = re.search(h5_pattern, html)
                if h5_match:
                    clean_title = h5_match.group(1).strip()
            items.append({
                "vod_id": vid,
                "vod_name": clean_title or f"视频{vid}",
                "vod_pic": pic if pic.startswith("http") else self.host + pic,
                "vod_remarks": ""
            })
        return items
