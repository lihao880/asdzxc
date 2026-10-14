# -*- coding: utf-8 -*-
import re
import json
import base64
import urllib.parse
import posixpath
from urllib.parse import urlparse, quote, unquote
from base.spider import Spider as BaseSpider

try:
    import requests
except ImportError:
    requests = None


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://kkfuli2119.lol"
        self.site_name = "KK福利视频"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
            "Cookie": "PHPSESSID=6v64t1jih4viq4ka5aifvfio2s"
        }
        # 分类：国产自拍=1, 国产传媒=2, 探花系列=3, 网红主播=4, 中文字幕=5, 日本有码=6, 日本无码=7, 黑丝诱惑=8
        self.classes = [
            {"type_id": "1", "type_name": "国产自拍"},
            {"type_id": "2", "type_name": "国产传媒"},
            {"type_id": "3", "type_name": "探花系列"},
            {"type_id": "4", "type_name": "网红主播"},
            {"type_id": "5", "type_name": "中文字幕"},
            {"type_id": "6", "type_name": "日本有码"},
            {"type_id": "7", "type_name": "日本无码"},
            {"type_id": "8", "type_name": "黑丝诱惑"},
        ]
        self.filters = {}

    def getName(self):
        return self.site_name

    def getDependence(self):
        return ["requests"]

    def init(self, extend=""):
        """初始化，零网络依赖"""
        self.extend = extend or ""

    def fetch(self, url, headers=None, timeout=15):
        """封装请求，支持重试"""
        if requests is None:
            return None
        headers = headers or self.headers.copy()
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, verify=False)
            if resp.status_code == 200:
                resp.encoding = 'utf-8'
                _ = resp.content
            return resp
        except Exception as e:
            print(f"fetch error: {e}")
            return None

    def post(self, url, data=None, headers=None, timeout=15):
        """封装 POST 请求"""
        if requests is None:
            return None
        headers = headers or self.headers.copy()
        try:
            resp = requests.post(url, data=data, headers=headers, timeout=timeout, verify=False)
            return resp
        except Exception as e:
            print(f"post error: {e}")
            return None

    def fix_url(self, url):
        """补全 URL"""
        if not url:
            return ""
        url = url.strip()
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host.rstrip("/") + url
        return self.host.rstrip("/") + "/" + url.lstrip("/")

    def getProxyUrl(self):
        """获取本地代理地址"""
        return "http://127.0.0.1:9978/proxy"

    def make_proxy_url(self, pic_url):
        """生成图片代理地址"""
        if not pic_url:
            return ""
        encoded = base64.b64encode(pic_url.encode()).decode()
        return self.getProxyUrl() + "?do=py&type=img&url=" + encoded

    def extract_vod_id(self, url):
        """从详情链接提取视频ID"""
        if not url:
            return ""
        m = re.search(r"/id/(\d+)/", url)
        if m:
            return m.group(1)
        return url

    def parse_video_items(self, html, limit=999):
        """解析列表页视频项"""
        videos = []
        if not html:
            return videos

        pattern = r'<div class="vod-txt">\s*<a href="([^"]+)"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.DOTALL)

        img_pattern = r'<img[^>]+data-original="([^"]+)"'
        img_matches = re.findall(img_pattern, html, re.DOTALL)

        for idx, (link, title) in enumerate(matches):
            if not title or not link:
                continue

            vod_id = self.extract_vod_id(link)
            if not vod_id:
                continue

            pic = ""
            if idx < len(img_matches):
                pic = img_matches[idx]
                if "loading.gif" not in pic:
                    pic = self.fix_url(pic)
                    # 图片直接返回URL，不走代理（避免代理干扰）
                else:
                    pic = ""

            videos.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": ""
            })

            if len(videos) >= limit:
                break

        return videos
    def parse_play_data(self, html):
        """从详情页提取播放数据"""
        if not html:
            return None

        # 方法1: 查找 var player_aaaa= 后面的JSON对象
        start = html.find('var player_aaaa=')
        if start != -1:
            start += len('var player_aaaa=')
            brace_count = 0
            end = start
            in_string = False
            escape = False
            for i, ch in enumerate(html[start:], start):
                if escape:
                    escape = False
                    continue
                if ch == '\\':
                    escape = True
                    continue
                if ch == '"' and not escape:
                    in_string = not in_string
                    continue
                if not in_string:
                    if ch == '{':
                        brace_count += 1
                    elif ch == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break
            if end > start:
                json_str = html[start:end].rstrip(';')
                try:
                    data = json.loads(json_str)
                    if data and data.get("url"):
                        return data
                except:
                    pass

        # 方法2: 正则匹配 var player_aaaa = {...};
        pattern = r'var player_aaaa\s*=\s*({[^;]+});'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if data and data.get("url"):
                    return data
            except:
                pass

        # 方法3: 直接查找 m3u8 URL
        m3u8_pattern = r'url\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']'
        match = re.search(m3u8_pattern, html, re.IGNORECASE)
        if match:
            return {"url": match.group(1), "encrypt": 0}

        # 方法4: iframe 中的播放地址
        iframe_pattern = r'<iframe[^>]+src="[^"]*\?url=([^"]+)"'
        match = re.search(iframe_pattern, html)
        if match:
            return {"url": match.group(1), "encrypt": 0}

        return None
    def homeContent(self, filter=False):
        """首页返回分类和筛选"""
        result = {"class": self.classes}
        result["filters"] = self.filters if filter else {}

        try:
            html = self.fetch(self.host + "/").text if self.fetch(self.host + "/") else ""
            result["list"] = self.parse_video_items(html, 15) if html else []
        except:
            result["list"] = []

        return result

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐"""
        try:
            result = self.categoryContent("1", "1", False, None)
            return {"list": result.get("list", [])[:15]}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        """分类列表"""
        pg = int(pg) if pg else 1
        if pg <= 1:
            url = f"{self.host}/index.php/vod/type/id/{tid}.html"
        else:
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"

        resp = self.fetch(url)
        if not resp or resp.status_code != 200:
            return {"list": [], "page": pg, "pagecount": 1, "total": 0}

        html = resp.text

        if 'vods' not in html:
            return {"list": [], "page": pg, "pagecount": 1, "total": 0}

        videos = self.parse_video_items(html)

        total = 9999
        pagecount = 999
        total_match = re.search(r'共(\d+)条数据', html)
        if total_match:
            total = int(total_match.group(1))

        page_pattern = r'<a href="[^"]*/page/(\d+)\.html"'
        pages = re.findall(page_pattern, html)
        if pages:
            pagecount = max([int(p) for p in pages]) + 1

        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": 20,
            "total": total
        }

    def detailContent(self, ids):
        """详情页"""
        if not ids:
            return {"list": []}

        if isinstance(ids, list):
            vid = str(ids[0])
        else:
            vid = str(ids)

        url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        resp = self.fetch(url)
        if not resp or resp.status_code != 200:
            return {"list": []}

        html = resp.text

        title = ""
        title_match = re.search(r'<div class="title"><h3>([^<]+)</h3>', html)
        if title_match:
            title = title_match.group(1).strip()

        pic = ""
        pic_match = re.search(r'<img[^>]+data-original="([^"]+)"', html)
        if pic_match:
            pic = pic_match.group(1)
            if pic and "loading.gif" not in pic:
                pic = self.fix_url(pic)
                # 图片直接返回URL，不走代理
            else:
                pic = ""

        play_data = self.parse_play_data(html)

        if play_data and play_data.get("url"):
            play_url = play_data.get("url")
            if not play_url.startswith("http"):
                play_url = self.fix_url(play_url)
            play_from = "默认线路"
            play_url_str = f"播放${play_url}"
        else:
            play_from = "暂无线路"
            play_url_str = ""

        data = {
            "vod_id": vid,
            "vod_name": title or f"视频_{vid}",
            "vod_pic": pic,
            "vod_content": "",
            "vod_play_from": play_from,
            "vod_play_url": play_url_str,
        }

        return {"list": [data]}
    def searchContent(self, key, quick=False, pg="1"):
        """搜索"""
        if not key:
            return {"list": [], "page": 1}

        pg = int(pg) if pg else 1

        if pg <= 1:
            search_url = f"{self.host}/index.php/vod/search/wd/{urllib.parse.quote(key)}.html"
        else:
            search_url = f"{self.host}/index.php/vod/search/wd/{urllib.parse.quote(key)}/page/{pg}.html"

        resp = self.fetch(search_url)
        if not resp or resp.status_code != 200:
            return {"list": [], "page": pg}

        html = resp.text
        videos = self.parse_video_items(html)

        total = 0
        total_match = re.search(r'共(\d+)条数据', html)
        if total_match:
            total = int(total_match.group(1))

        return {
            "list": videos,
            "page": pg,
            "pagecount": 999,
            "total": total
        }

    def playerContent(self, flag, id, vipFlags=None):
        """播放器 - m3u8走代理过滤广告"""
        # 确保 id 是字符串
        id = str(id) if id is not None else ""
        if not id:
            return {"parse": 1, "url": ""}

        if id.startswith("pics://"):
            return {"parse": 1, "url": id}

        if id.startswith("http"):
            if ".m3u8" in id.lower():
                proxy_url = self._m3u8_proxy_url(id)
                headers = {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/",
                }
                return {"parse": 0, "url": proxy_url, "header": headers}
            if ".mp4" in id.lower():
                headers = {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/",
                }
                return {"parse": 0, "url": id, "header": headers}

            resp = self.fetch(id)
            if resp and resp.status_code == 200:
                html = resp.text
                play_data = self.parse_play_data(html)
                if play_data and play_data.get("url"):
                    play_url = play_data.get("url")
                    if not play_url.startswith("http"):
                        play_url = self.fix_url(play_url)
                    if ".m3u8" in play_url.lower():
                        proxy_url = self._m3u8_proxy_url(play_url)
                        headers = {
                            "User-Agent": self.headers["User-Agent"],
                            "Referer": self.host + "/",
                        }
                        return {"parse": 0, "url": proxy_url, "header": headers}
                    if ".mp4" in play_url.lower():
                        headers = {
                            "User-Agent": self.headers["User-Agent"],
                            "Referer": self.host + "/",
                        }
                        return {"parse": 0, "url": play_url, "header": headers}

        if id.isdigit():
            detail_url = f"{self.host}/index.php/vod/play/id/{id}/sid/1/nid/1.html"
            resp = self.fetch(detail_url)
            if resp and resp.status_code == 200:
                html = resp.text
                play_data = self.parse_play_data(html)
                if play_data and play_data.get("url"):
                    play_url = play_data.get("url")
                    if not play_url.startswith("http"):
                        play_url = self.fix_url(play_url)
                    if ".m3u8" in play_url.lower():
                        proxy_url = self._m3u8_proxy_url(play_url)
                        headers = {
                            "User-Agent": self.headers["User-Agent"],
                            "Referer": self.host + "/",
                        }
                        return {"parse": 0, "url": proxy_url, "header": headers}
                    if ".mp4" in play_url.lower():
                        headers = {
                            "User-Agent": self.headers["User-Agent"],
                            "Referer": self.host + "/",
                        }
                        return {"parse": 0, "url": play_url, "header": headers}

        return {"parse": 1, "url": id, "header": self.headers}
    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址 - 使用标准 http 代理格式"""
        if not url:
            return ""
        url = url.replace("\\/", "/")
        # 使用标准代理格式
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")
    def localProxy(self, param):
        """m3u8 本地代理 - 拦截并过滤广告分片"""
        try:
            # 兼容 url 和 source 两种参数名
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            # 剥离前缀 url= 并解码
            if target.startswith("url="):
                target = target[4:]
            target = unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            # 非m3u8直接透传
            if not target.endswith(".m3u8") and "m3u8" not in target.lower():
                resp = self.fetch(target, headers=self.headers, timeout=10)
                if resp and hasattr(resp, "status_code") and resp.status_code == 200:
                    content_type = resp.headers.get("Content-Type", "application/octet-stream")
                    return [200, content_type, resp.content]
                return [404, "text/plain", b"not found"]

            # 获取m3u8
            headers = {
                "User-Agent": self.headers.get("User-Agent", ""),
                "Referer": self.host + "/"
            }
            resp = self.fetch(target, headers=headers, timeout=20)
            if not resp or not hasattr(resp, "status_code") or resp.status_code != 200:
                return [502, "text/plain", b"fetch failed"]

            content = resp.text if hasattr(resp, "text") else resp.content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in content:
                return [502, "text/plain", b"invalid m3u8"]

            cleaned = self._clean_m3u8(content, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]
    def _proxy_image(self, param):
        """处理图片代理"""
        try:
            # 兼容多种参数格式
            url = ""
            if isinstance(param, dict):
                # 尝试从不同字段获取URL
                url = param.get("url", "") or param.get("source", "")
                # 如果 url 是 base64 编码的，解码
                if url and not url.startswith("http"):
                    try:
                        decoded = base64.b64decode(url).decode()
                        if decoded.startswith("http"):
                            url = decoded
                    except:
                        pass
                # 如果 url 以 http 开头但包含 type=img，提取真实URL
                if url.startswith("http") and "type=img" in url:
                    import urllib.parse as up
                    parsed = up.urlparse(url)
                    query = up.parse_qs(parsed.query)
                    if "url" in query:
                        try:
                            url = base64.b64decode(query["url"][0]).decode()
                        except:
                            url = query["url"][0]
            else:
                url = str(param or "")

            if not url or not url.startswith("http"):
                return [400, "text/plain", b"invalid image url"]

            resp = self.fetch(url, timeout=30)
            if not resp or resp.status_code != 200:
                return [404, "text/plain", b"image not found"]

            content = resp.content
            # 检测图片类型
            if content.startswith(b'\xff\xd8\xff'):
                return [200, "image/jpeg", content]
            elif content.startswith(b'\x89PNG'):
                return [200, "image/png", content]
            elif content.startswith(b'GIF8'):
                return [200, "image/gif", content]
            else:
                content_type = resp.headers.get("Content-Type", "image/jpeg")
                return [200, content_type, content]
        except Exception as e:
            return [500, "text/plain", f"image proxy error: {str(e)}".encode()]

    def _clean_m3u8(self, text, source_url):
        """清洗m3u8 - 过滤广告分片 (基于DISCONTINUITY分割)"""
        import posixpath
        try:
            lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
            if not lines:
                return "#EXTM3U\n"

            # 处理多码率 Master Playlist
            if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
                out = []
                # 保留 #EXTM3U
                out.append("#EXTM3U")
                for line in lines:
                    if line == "#EXTM3U":
                        continue
                    if line.startswith("#"):
                        out.append(line)
                    else:
                        child = urllib.parse.urljoin(source_url, line)
                        if ".m3u8" in child.lower():
                            out.append(self._m3u8_proxy_url(child))
                        else:
                            out.append(child)
                return "\n".join(out) + "\n"

            parsed = urllib.parse.urlparse(source_url)
            source_dir = posixpath.dirname(parsed.path)
            if not source_dir.endswith("/"):
                source_dir += "/"

            # 正片目录：从 #EXT-X-KEY 提取
            main_dir = source_dir
            for line in lines:
                if line.startswith("#EXT-X-KEY") and "URI=" in line:
                    uri_match = re.search(r'URI="([^"]+)"', line)
                    if uri_match:
                        key_path = uri_match.group(1)
                        if not key_path.startswith("http"):
                            key_dir = posixpath.dirname(key_path)
                            if key_dir and key_dir != "/":
                                if not key_dir.endswith("/"):
                                    key_dir += "/"
                                main_dir = key_dir
                                break

            # 找到第一个 #EXT-X-DISCONTINUITY 的位置
            discontinuity_idx = -1
            for i, line in enumerate(lines):
                if line == "#EXT-X-DISCONTINUITY":
                    discontinuity_idx = i
                    break

            segments = []
            pending = []

            if discontinuity_idx == -1:
                # 没有 DISCONTINUITY：只保留主目录下的分片
                for line in lines:
                    if line == "#EXTM3U":
                        continue
                    if line.startswith("#EXTINF"):
                        pending = [line]
                        continue
                    if pending and line.startswith("#"):
                        pending.append(line)
                        continue
                    if pending:
                        media_url = urllib.parse.urljoin(source_url, line)
                        media_parsed = urllib.parse.urlparse(media_url)
                        if media_parsed.path.startswith(main_dir):
                            segments.extend(pending)
                            segments.append(media_url)
                        pending = []
                        continue
                    if not line.startswith("#"):
                        segments.append(urllib.parse.urljoin(source_url, line))
                    else:
                        segments.append(line)
            else:
                # 有 DISCONTINUITY：保留 DISCONTINUITY 之后的所有分片
                in_main = False
                # 先保留必要的头部标签
                for line in lines:
                    if line == "#EXTM3U":
                        continue
                    if line == "#EXT-X-DISCONTINUITY":
                        in_main = True
                        # 保留 DISCONTINUITY 标记
                        segments.append(line)
                        continue

                    if not in_main:
                        # 在 DISCONTINUITY 之前，只保留 #EXT-X-KEY（用于正片解密）
                        if line.startswith("#EXT-X-KEY"):
                            segments.append(line)
                        continue

                    if line.startswith("#EXTINF"):
                        pending = [line]
                        continue
                    if pending and line.startswith("#"):
                        pending.append(line)
                        continue
                    if pending:
                        media_url = urllib.parse.urljoin(source_url, line)
                        segments.extend(pending)
                        segments.append(media_url)
                        pending = []
                        continue
                    if not line.startswith("#"):
                        segments.append(urllib.parse.urljoin(source_url, line))
                    else:
                        segments.append(line)

            # 重写 KEY 的 URI 为绝对路径
            out = ["#EXTM3U"]  # 始终保留 #EXTM3U 头
            for line in segments:
                line = self._rewrite_m3u8_tag(line, source_url)
                # 清理孤立的标记
                if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                    if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                        continue
                out.append(line)

            # 清理尾部多余的标记
            while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                out.pop()

            return "\n".join(out) + "\n"
        except Exception as e:
            # 如果清洗失败，返回原始内容
            return text
    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI"""
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