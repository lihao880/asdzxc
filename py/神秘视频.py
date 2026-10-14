# coding: utf-8
import json
import re
import posixpath
from urllib.parse import quote, unquote, urljoin, urlparse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    """
    站点: 717022.xyz (绿色导航)
    类型: 成人影视API站
    数据源: https://api.xjzyapi.xyz/provide/vod/
    特点: 纯API接口，播放地址为m3u8直链，支持广告分片过滤
    """
    
    def __init__(self):
        self.api_host = "https://api.xjzyapi.xyz"
        self.web_host = "https://717022.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.web_host + "/"
        }
        # 分类映射 (从首页JS提取)
        self.classes = [
            {"type_id": "49", "type_name": "国产"},
            {"type_id": "21", "type_name": "无码"},
            {"type_id": "50", "type_name": "欧美"},
            {"type_id": "15", "type_name": "网红"},
            {"type_id": "22", "type_name": "有码"},
            {"type_id": "20", "type_name": "素人"},
            {"type_id": "23", "type_name": "字幕"},
            {"type_id": "11", "type_name": "传媒"}
        ]
        # 筛选器（该站无筛选参数，留空）
        self.filters = {}
        for cls in self.classes:
            self.filters[cls["type_id"]] = []

    def getName(self):
        return "绿色导航"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 默认请求国产分类(id=49)第1页"""
        try:
            url = f"{self.api_host}/provide/vod/?ac=detail&t=49&pg=1"
            resp = self.fetch(url, headers=self.headers)
            data = json.loads(resp.text)
            items = data.get("list", [])
            return {"list": self._parse_vod_list(items)}
        except Exception as e:
            self.log({"action": "homeVideoContent", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        """分类列表"""
        try:
            page = pg or 1
            url = f"{self.api_host}/provide/vod/?ac=detail&t={tid}&pg={page}"
            resp = self.fetch(url, headers=self.headers)
            data = json.loads(resp.text)
            items = data.get("list", [])
            return {
                "list": self._parse_vod_list(items),
                "page": int(page),
                "pagecount": data.get("pagecount", 1),
                "limit": data.get("limit", 20),
                "total": data.get("total", 0)
            }
        except Exception as e:
            self.log({"action": "categoryContent", "error": str(e)})
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        """详情页"""
        try:
            vod_id = ids[0] if ids else ""
            if not vod_id:
                return {"list": []}
            url = f"{self.api_host}/provide/vod/?ac=detail&ids={vod_id}"
            resp = self.fetch(url, headers=self.headers)
            data = json.loads(resp.text)
            items = data.get("list", [])
            if not items:
                return {"list": []}
            item = items[0]
            # 构建播放数据
            play_from = item.get("vod_play_from", "播放")
            play_url = item.get("vod_play_url", "")
            vod = {
                "vod_id": str(item.get("vod_id", vod_id)),
                "vod_name": item.get("vod_name", ""),
                "vod_pic": item.get("vod_pic", ""),
                "vod_remarks": item.get("vod_remarks", ""),
                "vod_actor": item.get("vod_actor", ""),
                "vod_director": item.get("vod_director", ""),
                "vod_content": item.get("vod_content", ""),
                "vod_year": item.get("vod_year", ""),
                "vod_tag": item.get("vod_tag", ""),
                "vod_play_from": play_from,
                "vod_play_url": play_url
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent", "error": str(e)})
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        try:
            page = pg or "1"
            url = f"{self.api_host}/provide/vod/?ac=detail&wd={quote(key)}&pg={page}"
            resp = self.fetch(url, headers=self.headers)
            data = json.loads(resp.text)
            items = data.get("list", [])
            return {
                "list": self._parse_vod_list(items),
                "page": int(page)
            }
        except Exception as e:
            self.log({"action": "searchContent", "error": str(e)})
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        """播放器 - 返回 m3u8 直链，走本地代理过滤广告"""
        try:
            if not id:
                return {"parse": 0, "url": "", "header": {}}
            # 如果是m3u8直链，走代理过滤广告
            if id.endswith(".m3u8"):
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(id),
                    "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": self.web_host + "/"
                    }
                }
            if id.endswith(".mp4"):
                return {
                    "parse": 0,
                    "url": id,
                    "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": self.web_host + "/"
                    }
                }
            # 否则尝试解析
            url = f"{self.api_host}/provide/vod/?ac=detail&ids={id}"
            resp = self.fetch(url, headers=self.headers)
            data = json.loads(resp.text)
            items = data.get("list", [])
            if items and items[0].get("vod_play_url"):
                play_url = items[0].get("vod_play_url")
                if "$" in play_url:
                    parts = play_url.split("$", 1)
                    if len(parts) == 2:
                        real_url = parts[1]
                        if real_url.endswith(".m3u8"):
                            return {
                                "parse": 0,
                                "url": self._m3u8_proxy_url(real_url),
                                "header": {
                                    "User-Agent": self.headers["User-Agent"],
                                    "Referer": self.web_host + "/"
                                }
                            }
                        return {
                            "parse": 0,
                            "url": real_url,
                            "header": {
                                "User-Agent": self.headers["User-Agent"],
                                "Referer": self.web_host + "/"
                            }
                        }
                return {
                    "parse": 0,
                    "url": play_url,
                    "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": self.web_host + "/"
                    }
                }
            return {"parse": 1, "url": id, "header": self.headers}
        except Exception as e:
            self.log({"action": "playerContent", "error": str(e)})
            return {"parse": 1, "url": id, "header": self.headers}

    def recommendContent(self, ids, pg):
        """
        相关推荐接口 - 根据当前视频ID获取同类推荐
        ids: 视频ID列表，如 ['100368']
        pg: 页码（从1开始）
        返回: {'list': [vod1, vod2, ...]}
        实现策略：
        1. 从当前视频提取分类/标签
        2. 按分类关键词搜索同类视频
        3. 不足则用热门列表兜底
        """
        try:
            # 提取视频ID
            vid = str(ids[0] if isinstance(ids, (list, tuple)) and ids else "")
            if not vid:
                return {"list": []}
            
            page = max(1, int(pg or 1))
            limit = 18
            
            # 获取当前视频详情
            detail_url = f"{self.api_host}/provide/vod/?ac=detail&ids={vid}"
            resp = self.fetch(detail_url, headers=self.headers)
            detail_data = json.loads(resp.text)
            items = detail_data.get("list", [])
            if not items:
                return {"list": []}
            
            detail = items[0]
            category = detail.get("type_name", "") or detail.get("vod_class", "")
            tags = detail.get("vod_tag", "")
            
            videos = []
            seen = set()
            seen.add(vid)
            
            # 策略1: 按分类推荐
            if category:
                search_url = f"{self.api_host}/provide/vod/?ac=detail&wd={quote(category)}&pg={page}"
                search_resp = self.fetch(search_url, headers=self.headers)
                search_data = json.loads(search_resp.text)
                for item in search_data.get("list", []):
                    item_id = str(item.get("vod_id", ""))
                    if item_id and item_id not in seen:
                        seen.add(item_id)
                        videos.append({
                            "vod_id": item_id,
                            "vod_name": item.get("vod_name", ""),
                            "vod_pic": item.get("vod_pic", ""),
                            "vod_remarks": item.get("vod_remarks", "") or item.get("vod_duration", "")
                        })
                        if len(videos) >= limit:
                            break
            
            # 策略2: 按标签推荐
            if len(videos) < limit and tags:
                first_tag = tags.split(",")[0].strip()
                if first_tag and first_tag != category:
                    search_url = f"{self.api_host}/provide/vod/?ac=detail&wd={quote(first_tag)}&pg={page}"
                    search_resp = self.fetch(search_url, headers=self.headers)
                    search_data = json.loads(search_resp.text)
                    for item in search_data.get("list", []):
                        item_id = str(item.get("vod_id", ""))
                        if item_id and item_id not in seen:
                            seen.add(item_id)
                            videos.append({
                                "vod_id": item_id,
                                "vod_name": item.get("vod_name", ""),
                                "vod_pic": item.get("vod_pic", ""),
                                "vod_remarks": item.get("vod_remarks", "") or item.get("vod_duration", "")
                            })
                            if len(videos) >= limit:
                                break
            
            # 策略3: 热门兜底 (默认使用国产分类)
            if len(videos) < limit:
                hot_url = f"{self.api_host}/provide/vod/?ac=detail&t=49&pg={page}"
                hot_resp = self.fetch(hot_url, headers=self.headers)
                hot_data = json.loads(hot_resp.text)
                for item in hot_data.get("list", []):
                    item_id = str(item.get("vod_id", ""))
                    if item_id and item_id not in seen:
                        seen.add(item_id)
                        videos.append({
                            "vod_id": item_id,
                            "vod_name": item.get("vod_name", ""),
                            "vod_pic": item.get("vod_pic", ""),
                            "vod_remarks": item.get("vod_remarks", "") or item.get("vod_duration", "")
                        })
                        if len(videos) >= limit:
                            break
            
            return {"list": videos[:limit]}
            
        except Exception as e:
            self.log({"action": "recommendContent", "error": str(e)})
            return {"list": []}

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

            # 发起 HTTP 请求获取 m3u8 内容
            res = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=15)
            if not res:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(res, "content", b"") or b""
            if not content and hasattr(res, "text") and res.text:
                content = res.text.encode("utf-8", errors="ignore")

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
        """清洗 m3u8：过滤广告分片，保留正片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 处理多码率 Master Playlist
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

        # 从 #EXT-X-KEY 提取正片目录（更准确）
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
                media_url = urljoin(source_url, line)
                media_parsed = urlparse(media_url)

                # 过滤逻辑：判断分片路径是否以正片目录开头
                is_ad = not media_parsed.path.startswith(main_dir)

                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urljoin(source_url, line))
            else:
                segments.append(line)

        # 二次清洗：去除孤立/连续的 #EXT-X-DISCONTINUITY 和 KEY:METHOD=NONE
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        # 清理尾部多余的标记
        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写 m3u8 标签中的 URI（补全绝对地址）"""
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

    def destroy(self):
        """释放资源"""
        pass

    def _parse_vod_list(self, items):
        """解析视频列表"""
        result = []
        for item in items:
            vod_id = str(item.get("vod_id", ""))
            vod_name = item.get("vod_name", "")
            vod_pic = item.get("vod_pic", "")
            vod_remarks = item.get("vod_remarks", "") or item.get("vod_duration", "")
            if vod_id and vod_name:
                result.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks
                })
        return result