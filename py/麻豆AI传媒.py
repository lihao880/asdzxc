# coding: utf-8
# 麻豆AI传媒 - https://www.madouai.xyz/
# 站点类型: React SPA, API驱动
# 最后验证: 2026-08-30

import json
import re
import time
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def getName(self):
        return "麻豆AI传媒"

    def __init__(self):
        self.host = "https://www.madouai.xyz"
        self.api = self.host + "/api/v1"
        self.ua = "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36"
        self._cache = {}
        self._cache_time = 0

        # 分类列表 - 第一个是"短剧"（使用short-dramas接口），其他使用videos接口
        self.classes = [
            {"type_id": "short_dramas", "type_name": "AI短剧"},
            {"type_id": "27", "type_name": "每日更新"},
            {"type_id": "6", "type_name": "麻豆原创AI"},
            {"type_id": "10", "type_name": "麻豆x性吧联合原创"},
            {"type_id": "9", "type_name": "麻豆传媒"},
            {"type_id": "13", "type_name": "清纯少女"},
            {"type_id": "14", "type_name": "重口调教"},
            {"type_id": "15", "type_name": "直播大秀"},
            {"type_id": "16", "type_name": "网红主播"},
            {"type_id": "17", "type_name": "媚黑母狗"},
            {"type_id": "18", "type_name": "白虎少女"},
            {"type_id": "19", "type_name": "黑料吃瓜"},
            {"type_id": "1", "type_name": "国产自拍（最新更新）"},
            {"type_id": "2", "type_name": "AV - 中文字幕"},
            {"type_id": "8", "type_name": "AV - 无码流出"},
            {"type_id": "4", "type_name": "探花大神"},
            {"type_id": "7", "type_name": "91大神"},
            {"type_id": "20", "type_name": "破解偷拍"},
            {"type_id": "28", "type_name": "世界杯专栏"},
            {"type_id": "21", "type_name": "反差母狗"},
            {"type_id": "22", "type_name": "白虎嫩妹"},
            {"type_id": "23", "type_name": "家庭乱伦"},
            {"type_id": "24", "type_name": "熟女偷情"},
            {"type_id": "25", "type_name": "网黄原创"},
        ]

        # 筛选器
        self.filters = {}
        for c in self.classes:
            self.filters[c["type_id"]] = []

    def init(self, extend=""):
        self.extend = extend or ""

    def getDependence(self):
        return []

    def destroy(self):
        self._cache = {}
        self._cache_time = 0

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            # 使用 videos API 获取最新视频作为首页推荐
            data = self._api_get("/videos", {"page": 1, "size": 24})
            items = data.get("items", []) if data else []
            return {"list": self._parse_video_list(items)}
        except Exception as e:
            self.log("首页推荐失败: %s" % str(e))
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        page = self._int(pg, 1)
        ext = self._parse_extend(extend)

        try:
            tid = str(tid or "27")
            params = {"page": page, "size": 24}

            # 判断使用哪个接口
            if tid == "short_dramas":
                # 短剧接口 - 使用 /api/v1/short-dramas
                short_params = {"productId": 1, "sortBy": "heat", "page": page, "size": 24}
                data = self._api_get("/short-dramas", short_params)
                if not data:
                    return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}
                items = data.get("items", [])
                total = self._int(data.get("total", 0))
                total_pages = self._int(data.get("totalPages", 1))
                return {
                    "list": self._parse_list(items),
                    "page": page,
                    "pagecount": total_pages or 1,
                    "limit": 24,
                    "total": total
                }

            # 普通视频接口 - 使用 /api/v1/videos（支持分类过滤）
            if tid != "all":
                params["categoryId"] = tid

            data = self._api_get("/videos", params)
            if not data:
                return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

            items = data.get("items", [])
            total = self._int(data.get("total", 0))
            total_pages = self._int(data.get("totalPages", 1))

            return {
                "list": self._parse_video_list(items),
                "page": page,
                "pagecount": total_pages or 1,
                "limit": 24,
                "total": total
            }
        except Exception as e:
            self.log("分类失败 tid=%s pg=%s err=%s" % (tid, page, str(e)))
            return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            vid = str(vid).strip()
            if not vid:
                return {"list": []}

            # 先尝试作为短剧获取（多集）
            data = self._api_get("/short-dramas/%s" % vid, {"productId": 1})
            if data and data.get("episodes"):
                # 短剧 - 多集
                vod = {
                    "vod_id": str(data.get("id", vid)),
                    "vod_name": data.get("title", ""),
                    "vod_pic": self._pic_url(data.get("coverUrl", "")),
                    "vod_remarks": "%s集" % data.get("episodeCount", 0) if data.get("episodeCount") else "",
                    "vod_content": data.get("description", ""),
                    "vod_actor": "",
                    "vod_director": "",
                    "vod_play_from": "麻豆",
                    "vod_play_url": ""
                }
                # 解析剧集
                episodes = data.get("episodes", [])
                if episodes:
                    play_urls = []
                    for ep in episodes:
                        ep_no = ep.get("episodeNo", 1)
                        title = ep.get("title", "第%s集" % ep_no)
                        video_url = ep.get("videoUrl", "")
                        if video_url:
                            play_urls.append("%s$%s" % (title, video_url))
                    if play_urls:
                        vod["vod_play_url"] = "#".join(play_urls)
                return {"list": [vod]}

            # 再尝试作为普通视频获取（单集）
            data = self._api_get("/videos/%s" % vid)
            if data:
                vod = {
                    "vod_id": str(data.get("id", vid)),
                    "vod_name": data.get("title", ""),
                    "vod_pic": self._pic_url(data.get("coverUrl", "")),
                    "vod_remarks": data.get("categoryName", ""),
                    "vod_content": data.get("description", "") or data.get("title", ""),
                    "vod_actor": data.get("authorName", "") or "",
                    "vod_director": "",
                    "vod_play_from": "麻豆",
                    "vod_play_url": ""
                }
                video_url = data.get("videoUrl", "")
                if video_url:
                    vod["vod_play_url"] = "播放$" + video_url
                return {"list": [vod]}

            return {"list": []}
        except Exception as e:
            self.log("详情失败: %s" % str(e))
            return {"list": []}

    def searchContent(self, key, quick=False, pg="1"):
        page = self._int(pg, 1)
        try:
            # 使用 videos API 的 keyword 参数进行搜索
            params = {"keyword": key, "page": page, "size": 24}
            data = self._api_get("/videos", params)
            if data:
                items = data.get("items", [])
                if items:
                    return {"list": self._parse_video_list(items), "page": page}
            return {"list": [], "page": page}
        except Exception as e:
            self.log("搜索失败: %s" % str(e))
            return {"list": [], "page": page}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            if not id:
                return {"parse": 0, "url": "", "header": {}}

            # 如果已经包含完整URL，直接返回
            if id.startswith("http"):
                if ".m3u8" in id:
                    return {
                        "parse": 0,
                        "url": self._m3u8_proxy_url(id),
                        "header": {"User-Agent": self.ua}
                    }
                return {"parse": 0, "url": id, "header": {"User-Agent": self.ua}}

            # 否则拼接代理URL
            encoded_path = urllib.parse.quote(id, safe="")
            m3u8_url = "%s/api/v1/m3u8/proxy?path=%s" % (self.host, encoded_path)
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(m3u8_url),
                "header": {"User-Agent": self.ua, "Referer": self.host + "/"}
            }
        except Exception as e:
            self.log("播放失败: %s" % str(e))
            return {"parse": 1, "url": id, "header": {"User-Agent": self.ua, "Referer": self.host + "/"}}

    def recommendContent(self, ids, pg):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            vid = str(vid).strip()
            if not vid:
                return {"list": []}

            # 使用同分类推荐
            data = self._api_get("/short-dramas", {"productId": 1, "sortBy": "heat", "page": 1, "size": 12})
            items = data.get("items", []) if data else []
            # 过滤掉当前视频
            filtered = [it for it in items if str(it.get("id", "")) != vid]
            return {"list": self._parse_list(filtered[:10])}
        except Exception as e:
            self.log("推荐失败: %s" % str(e))
            return {"list": []}

    def localProxy(self, param):
        """m3u8 代理 - 透传并补全分片地址"""
        try:
            target = ""
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

            resp = self.fetch(target, headers={"User-Agent": self.ua, "Referer": self.host + "/"}, timeout=20)
            if not resp:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")

            if not content:
                return [502, "text/plain", b"empty content"]

            # 如果是 m3u8，进行清洗
            if b"#EXTM3U" in content[:512]:
                cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

            # 非 m3u8 直接透传
            return [200, "application/octet-stream", content]
        except Exception as e:
            self.log("localProxy error: %s" % str(e))
            return [500, "text/plain", str(e).encode("utf-8", errors="ignore")]

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：重写相对路径为绝对路径"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 检测是否多码率
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    # 子流地址改为代理
                    child = urllib.parse.urljoin(source_url, line)
                    if ".m3u8" in child.lower():
                        out.append(self._m3u8_proxy_url(child))
                    else:
                        out.append(child)
            return "\n".join(out) + "\n"

        # 单码率：重写所有分片为绝对路径
        out = []
        for line in lines:
            if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
                # 重写 KEY URI
                def repl(match):
                    uri = match.group(1)
                    if uri.startswith(("http://", "https://")):
                        return 'URI="' + uri + '"'
                    return 'URI="' + urllib.parse.urljoin(source_url, uri) + '"'
                out.append(re.sub(r'URI="([^"]+)"', repl, line))
            elif line and not line.startswith("#"):
                # 分片地址补全
                if line.startswith(("http://", "https://")):
                    out.append(line)
                else:
                    out.append(urllib.parse.urljoin(source_url, line))
            else:
                out.append(line)

        return "\n".join(out) + "\n"

    def _m3u8_proxy_url(self, url):
        """生成代理地址"""
        if not url:
            return ""
        # getProxyUrl() 已经包含了 ?do=py，直接拼接 url 参数
        proxy_base = self.getProxyUrl()
        if "?" in proxy_base:
            return proxy_base + "&url=" + urllib.parse.quote(str(url), safe="")
        else:
            return proxy_base + "?url=" + urllib.parse.quote(str(url), safe="")

    def _api_get(self, path, params=None):
        """通用 API GET 请求"""
        try:
            url = self.api + path
            headers = {
                "User-Agent": self.ua,
                "Accept": "application/json, text/plain, */*",
                "Referer": self.host + "/",
                "Origin": self.host
            }
            resp = self.fetch(url, params=params, headers=headers, timeout=15)
            if not resp:
                return None
            data = resp.json()
            if isinstance(data, dict) and data.get("code") == 200:
                return data.get("data")
            return data
        except Exception as e:
            self.log("API请求失败 %s: %s" % (path, str(e)))
            return None

    def _parse_list(self, items):
        """解析短剧列表项 (short-dramas)"""
        result = []
        seen = set()
        for it in items or []:
            try:
                vid = str(it.get("id", ""))
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                result.append({
                    "vod_id": vid,
                    "vod_name": it.get("title", ""),
                    "vod_pic": self._pic_url(it.get("coverUrl", "")),
                    "vod_remarks": "%s集" % it.get("episodeCount", 0) if it.get("episodeCount") else "",
                    "vod_rating": str(it.get("rating", "")),
                })
            except Exception:
                continue
        return result

    def _parse_video_list(self, items):
        """解析视频列表项 (videos)"""
        result = []
        seen = set()
        for it in items or []:
            try:
                vid = str(it.get("id", ""))
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                # 时长格式化
                dur = it.get("durationSec", 0)
                if dur > 0:
                    mins = dur // 60
                    secs = dur % 60
                    remark = "%d分%d秒" % (mins, secs) if mins > 0 else "%d秒" % secs
                else:
                    remark = ""

                # 封面URL可能是相对路径
                cover = it.get("coverUrl", "")
                if cover and not cover.startswith("http"):
                    cover = self.host + "/" + cover.lstrip("/")

                result.append({
                    "vod_id": vid,
                    "vod_name": it.get("title", ""),
                    "vod_pic": cover,
                    "vod_remarks": remark,
                    "vod_rating": str(it.get("viewCount", 0)),
                    "categoryName": it.get("categoryName", ""),
                })
            except Exception:
                continue
        return result

    def _pic_url(self, url):
        """补全图片URL"""
        if not url:
            return ""
        if url.startswith("http"):
            return url
        return self.host + url

    def _parse_extend(self, extend):
        """解析 extend 参数"""
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except Exception:
                pass
            result = {}
            for part in extend.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    result[k.strip()] = v.strip()
            return result
        return {}

    def _int(self, v, default=0):
        try:
            return int(v)
        except Exception:
            return default