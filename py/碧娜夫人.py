# coding: utf-8
# 站点: 碧娜夫人 (oppo.missbina.site)
# 类型: 成人影视聚合站 (Alpine.js + 内嵌JSON)
# 更新日期: 2026-08-09
# 支持: m3u8 广告分片过滤 (proxy:// 协议)

import json
import base64
import re
import posixpath
from urllib.parse import urljoin, quote, unquote, urlparse

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://oppo.missbina.site"
        self.classes = [
            {"type_id": "53", "type_name": "国产传媒"},
            {"type_id": "29", "type_name": "变性情爱"},
            {"type_id": "23", "type_name": "百合拉拉"},
            {"type_id": "39", "type_name": "欧美映集"},
            {"type_id": "33", "type_name": "日影名库"},
            {"type_id": "31", "type_name": "捆绑调教"},
            {"type_id": "35", "type_name": "中字片场"},
            {"type_id": "43", "type_name": "国潮原创"}
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}
        self._vod_cache = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36",
            "Referer": self.host + "/"
        }

    def getName(self):
        return "碧娜夫人"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def _make_proxy_url(self, target, proxy_type="m3u8"):
        """生成 proxy:// 协议URL"""
        encoded = base64.b64encode(target.encode()).decode()
        return f"proxy://do=py&type={proxy_type}&url={encoded}"

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def _fetch_page_data(self, url):
        try:
            html = self.fetch(url, headers=self.headers).text
            pattern = r'const binaryStr = atob\([\'"]([^\'"]+)[\'"]\);'
            match = re.search(pattern, html)
            if not match:
                return None
            b64_data = match.group(1)
            json_str = base64.b64decode(b64_data).decode('utf-8')
            data = json.loads(json_str)
            return data
        except Exception as e:
            self.log({"action": "fetch_page_data_fail", "url": url, "error": str(e)})
            return None

    def _parse_vod_list(self, items):
        result = []
        for item in items:
            vod_id = str(item.get("vod_id", ""))
            vod_name = item.get("vod_name", "")
            if not vod_id or not vod_name:
                continue
            result.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": item.get("vod_pic", ""),
                "vod_remarks": item.get("vod_duration", "")
            })
        return result

    def _build_vod_item(self, item):
        vod_id = str(item.get('vod_id', ''))
        vod_name = item.get('vod_name', '')
        vod_pic = item.get('vod_pic', '')
        vod_duration = item.get('vod_duration', '')
        vod_play_url = item.get('vod_play_url', '')
        vod_tag = item.get('vod_tag', '')
        
        play_url = vod_play_url
        if vod_play_url and '$' in vod_play_url:
            parts = vod_play_url.split('$', 1)
            if len(parts) == 2:
                play_url = parts[1]
        
        return {
            "vod_id": vod_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_remarks": vod_duration,
            "vod_content": vod_tag,
            "vod_play_from": "播放",
            "vod_play_url": f"正片${play_url}"
        }

    def homeVideoContent(self):
        data = self._fetch_page_data(self.host + "/")
        if not data:
            return {"list": []}
        random_list = data.get("other_request_data", {}).get("random_list", [])
        return {"list": self._parse_vod_list(random_list)}

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or 1)
        url = f"{self.host}/vodlist/type/{tid}/keyword/all/orderby/default/page/{page}.html"
        data = self._fetch_page_data(url)
        if not data:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        
        request_data = data.get("request_data", {})
        vod_list = request_data.get("list", [])
        total = request_data.get("total", 0)
        
        for item in vod_list:
            vid = str(item.get('vod_id'))
            self._vod_cache[vid] = self._build_vod_item(item)
        
        result_list = self._parse_vod_list(vod_list)
        total_pages = (total + 19) // 20 if total > 0 else 1
        
        return {
            "list": result_list,
            "page": int(page),
            "pagecount": total_pages,
            "limit": 20,
            "total": total
        }

    def detailContent(self, ids):
        if isinstance(ids, int):
            vid = str(ids)
        elif isinstance(ids, list) and len(ids) > 0:
            vid = str(ids[0])
        else:
            vid = str(ids)
        
        vod = self._vod_cache.get(vid)
        if vod:
            return {"list": [vod]}
        
        url = f"{self.host}/voddetail/type/53/id/{vid}.html"
        data = self._fetch_page_data(url)
        if not data:
            return {"list": []}
        
        vod_info = data.get("vod_info", {})
        if not vod_info:
            return {"list": []}
        
        vod_item = self._build_vod_item(vod_info)
        return {"list": [vod_item]}

    def searchContent(self, key, quick, pg="1"):
        page = pg or "1"
        encoded_key = quote(str(key).encode('utf-8'))
        url = f"{self.host}/vodlist/type/all/keyword/{encoded_key}/orderby/default/page/{page}.html"
        data = self._fetch_page_data(url)
        if not data:
            return {"list": [], "page": int(page)}

        request_data = data.get("request_data", {})
        items = request_data.get("list", [])
        return {"list": self._parse_vod_list(items), "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 1, "url": "", "header": self.headers}
        
        # 如果 id 包含 $，提取后面的 URL
        if "$" in id:
            parts = id.split("$", 1)
            if len(parts) == 2 and parts[1].startswith("http"):
                id = parts[1]
        
        m3u8_url = None
        
        # 从 aojiexi.com 代理链接中提取真实 m3u8
        if "aojiexi.com" in id and "url=" in id:
            match = re.search(r'url=([^&]+)', id)
            if match:
                inner_url = unquote(match.group(1))
                if ".m3u8" in inner_url:
                    m3u8_url = inner_url
        else:
            match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', id)
            if match:
                m3u8_url = match.group(1).replace("\\/", "/")
        
        if m3u8_url:
            return {
                "parse": 0,
                "url": m3u8_url,
                "header": {
                    "User-Agent": self.headers.get("User-Agent", ""),
                    "Referer": self.host + "/"
                }
            }
        
        if id.startswith("http"):
            return {"parse": 0, "url": id, "header": self.headers}
        
        return {"parse": 1, "url": id, "header": self.headers}
    def localProxy(self, param):
        """本地代理 - 强制调用 _clean_m3u8"""
        try:
            target = ""
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "") or param.get("do", "")
            elif isinstance(param, str):
                target = param
            else:
                target = str(param or "")
            
            if target.startswith("url="):
                target = target[4:]
            if target.startswith("source="):
                target = target[7:]
            target = unquote(str(target or ""))
            target = target.replace("\\/", "/")
            
            if "proxy?do=py" in target or "proxy?do=py&url=" in target:
                url_match = re.search(r'[&?]url=([^&]+)', target)
                if url_match:
                    target = unquote(url_match.group(1))
                    target = target.replace("\\/", "/")
            
            if not target or not re.match(r"^https?://", target, re.I):
                if isinstance(param, dict):
                    for key in ["url", "source", "do", "u", "link", "play_url"]:
                        if param.get(key):
                            val = str(param[key]).replace("\\/", "/")
                            if val.startswith("http"):
                                target = val
                                break
                if not target or not re.match(r"^https?://", target, re.I):
                    return [400, "text/plain", b"invalid url"]
            
            # 获取 m3u8 内容
            res = self.fetch(target, headers=self.headers, timeout=15)
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
            
            # 强制调用 _clean_m3u8
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            
        except Exception as e:
            self.log({"action": "localProxy_error", "error": str(e)})
            return [500, "text/plain", f"proxy error: {str(e)}".encode("utf-8")]
    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片 (v3.13 - 字符串匹配)"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        # 提取正片目录
        main_dir = None
        for line in lines:
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                uri_match = re.search(r'URI="([^"]+)"', line)
                if uri_match:
                    key_path = uri_match.group(1)
                    if key_path.startswith("http"):
                        key_parsed = urlparse(key_path)
                        key_dir = posixpath.dirname(key_parsed.path)
                    else:
                        key_dir = posixpath.dirname(key_path)
                    if key_dir and key_dir != "/":
                        main_dir = key_dir + "/"
                        break

        if main_dir is None:
            parsed = urlparse(source_url)
            main_dir = posixpath.dirname(parsed.path)
            if not main_dir.endswith("/"):
                main_dir += "/"

        # 过滤分片
        segments = []
        pending = []
        removed = 0

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urljoin(source_url, line)
                # 直接使用字符串判断是否包含正片目录
                is_ad = main_dir not in media_url
                if is_ad:
                    removed += 1
                else:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue
            if not line.startswith("#"):
                segments.append(urljoin(source_url, line))
            else:
                segments.append(line)

        if removed > 0:
            self.log(f"m3u8 已过滤 {removed} 个广告分片")

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
    def isVideoFormat(self, url):
        return url and (url.endswith(".m3u8") or url.endswith(".mp4"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass