# coding: utf-8
# 探花群 影视爬虫 - 标准HTML站
# 站点: https://132608.tanhq.top/

import re
import json
import urllib.parse
import posixpath
from urllib.parse import quote, urlencode

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://132608.tanhq.top"
        self.site_name = "探花群"
        self.classes = [
            {"type_id": "1", "type_name": "日韩"},
            {"type_id": "2", "type_name": "国产"},
            {"type_id": "3", "type_name": "欧美"},
            {"type_id": "4", "type_name": "动漫"},
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }
        self._title_cache = {}

    def getName(self):
        return "探花群"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/index.html")
        items = self._parse_video_list(html)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg) if pg else "1"
        url = f"{self.host}/list.php?cid={tid}&page={pg}"
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
        if isinstance(ids, list):
            vid = str(ids[0])
        else:
            vid = str(ids)
        
        detail_url = vid
        if not detail_url.startswith("http"):
            if detail_url.startswith("/"):
                detail_url = self.host + detail_url
            else:
                detail_url = self.host + "/" + detail_url
        
        html = self._fetch_html(detail_url)
        play_url = self._extract_m3u8_from_html(html)
        vod_name = self._extract_title_from_html(html)
        
        if play_url:
            vod = {
                "vod_id": vid,
                "vod_name": vod_name or "视频",
                "vod_pic": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}",
            }
        else:
            vod = {
                "vod_id": vid,
                "vod_name": vod_name or "视频",
                "vod_pic": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${detail_url}",
            }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = str(pg) if pg else "1"
        url = f"{self.host}/search.php?keyword={quote(key)}&page={pg}"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        return {"list": items, "page": int(pg)}

    def recommendContent(self, ids, pg="1"):
        """
        相关推荐接口 - 多级降级策略
        策略1: 用提取的关键词搜索
        策略2: 用短关键词搜索
        策略3: 用分类ID获取热门推荐
        策略4: 首页推荐兜底
        """
        try:
            if not ids:
                return {"list": []}
            
            vid = ids[0] if isinstance(ids, list) else ids
            result_list = []
            
            # ===== 策略1: 使用完整关键词 =====
            keyword = self._extract_keyword_from_id(vid)
            if keyword and len(keyword) >= 2:
                search_result = self.searchContent(keyword, quick=False, pg=pg)
                items = search_result.get("list", [])
                filtered = [item for item in items if item.get("vod_id") != vid]
                result_list.extend(filtered)
            
            # ===== 策略2: 如果结果少于3条，使用短关键词 =====
            if len(result_list) < 3 and keyword:
                words = keyword.split()
                if len(words) >= 3:
                    short_keyword = " ".join(words[:3])
                elif len(words) >= 2:
                    short_keyword = " ".join(words[:2])
                else:
                    short_keyword = keyword[:8] if len(keyword) > 8 else keyword
                
                if short_keyword != keyword:
                    search_result2 = self.searchContent(short_keyword, quick=False, pg=pg)
                    items2 = search_result2.get("list", [])
                    existing_ids = {item.get("vod_id") for item in result_list}
                    for item in items2:
                        if item.get("vod_id") != vid and item.get("vod_id") not in existing_ids:
                            result_list.append(item)
            
            # ===== 策略3: 如果结果少于3条，使用分类热门 =====
            if len(result_list) < 3:
                tid = self._extract_tid_from_vid(vid)
                if tid:
                    try:
                        category_result = self.categoryContent(tid, pg="1", filter=False, extend={})
                        items3 = category_result.get("list", [])
                        existing_ids = {item.get("vod_id") for item in result_list}
                        for item in items3[:20]:
                            if item.get("vod_id") != vid and item.get("vod_id") not in existing_ids:
                                result_list.append(item)
                                if len(result_list) >= 12:
                                    break
                    except:
                        pass
            
            # ===== 策略4: 如果结果少于3条，使用首页推荐兜底 =====
            if len(result_list) < 3:
                try:
                    home_result = self.homeVideoContent()
                    items4 = home_result.get("list", [])
                    existing_ids = {item.get("vod_id") for item in result_list}
                    for item in items4[:20]:
                        if item.get("vod_id") != vid and item.get("vod_id") not in existing_ids:
                            result_list.append(item)
                            if len(result_list) >= 12:
                                break
                except:
                    pass
            
            return {"list": result_list[:12]}
            
        except Exception as e:
            self.log({"action": "recommendContent_fail", "error": str(e)})
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        if id and id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0, 
                "url": self._m3u8_proxy_url(id), 
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        if id and id.startswith("http"):
            html = self._fetch_html(id)
            play_url = self._extract_m3u8_from_html(html)
            if play_url:
                return {
                    "parse": 0, 
                    "url": self._m3u8_proxy_url(play_url), 
                    "header": {"User-Agent": self.headers.get("User-Agent", "")}
                }
            return {"parse": 1, "url": id, "header": self.headers}
        if id and id.startswith("/"):
            detail_url = self.host + id
            html = self._fetch_html(detail_url)
            play_url = self._extract_m3u8_from_html(html)
            if play_url:
                return {
                    "parse": 0, 
                    "url": self._m3u8_proxy_url(play_url), 
                    "header": {"User-Agent": self.headers.get("User-Agent", "")}
                }
            return {"parse": 1, "url": detail_url, "header": self.headers}
        return {"parse": 1, "url": id, "header": self.headers}

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            resp = self.fetch(target, headers=self.headers, timeout=15)
            if not resp:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")

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
            resp = self.fetch(full_url, headers=self.headers, timeout=15)
            if resp:
                content = getattr(resp, "content", b"") or b""
                if not content and hasattr(resp, "text") and resp.text:
                    content = resp.text.encode("utf-8", errors="ignore")
                
                if content:
                    for encoding in ["utf-8", "gbk", "gb2312", "gb18030", "latin-1"]:
                        try:
                            text = content.decode(encoding)
                            if re.search(r'[\u4e00-\u9fa5]', text) or "html" in text.lower():
                                return text
                        except:
                            continue
                    return content.decode("utf-8", errors="ignore")
            return ""
        except Exception as e:
            self.log({"action": "fetch_fail", "url": full_url, "error": str(e)})
            return ""

    def _parse_video_list(self, html):
        items = []
        if not html:
            return items
        pattern = r'<a\s+href="([^"]+)"[^>]*>.*?<div[^>]*class="[^"]*hot-item[^"]*"[^>]*>.*?<img[^>]*data-original="([^"]+)"[^>]*>.*?<div[^>]*class="[^"]*hot-title[^"]*"[^>]*>([^<]+)</div>'
        matches = re.findall(pattern, html, re.DOTALL)
        for link, pic, title in matches:
            if "player" in link:
                items.append({
                    "vod_id": link,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return items

    def _parse_page_count(self, html):
        if not html:
            return 1
        pattern = r'<a[^>]*href="[^"]*page=(\d+)"[^>]*>(\d+)</a>'
        matches = re.findall(pattern, html)
        if matches:
            max_page = 1
            for page_num, _ in matches:
                try:
                    p = int(page_num)
                    if p > max_page:
                        max_page = p
                except:
                    pass
            return max_page
        return 1

    def _extract_m3u8_from_html(self, html):
        if not html:
            return None
        pattern = r"hls\.loadSource\('([^']+\.m3u8[^']*)'\)"
        match = re.search(pattern, html)
        if match:
            url = match.group(1)
            if url and url.startswith("http"):
                return url
        pattern2 = r'var\s+player_aaaa\s*=\s*(\{[^;]+\});'
        match2 = re.search(pattern2, html, re.DOTALL)
        if match2:
            try:
                data = json.loads(match2.group(1))
                url = data.get("url", "")
                if url and url.startswith("http"):
                    return url
            except:
                pass
        pattern3 = r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"'
        match3 = re.search(pattern3, html)
        if match3:
            url = match3.group(1)
            if url and url.startswith("http"):
                return url
        pattern4 = r'https?://[^"\']+\.m3u8[^"\']*'
        match4 = re.search(pattern4, html)
        if match4:
            return match4.group(0)
        return None

    def _extract_title_from_html(self, html):
        if not html:
            return None
        pattern = r'<title>([^<]+)</title>'
        match = re.search(pattern, html)
        if match:
            title = match.group(1)
            title = title.replace(" - 探花群", "").strip()
            return title
        return None

    def _extract_keyword_from_id(self, vid):
        if not vid:
            return None
        
        if vid in self._title_cache:
            cached_title = self._title_cache[vid]
            if cached_title:
                return self._clean_keyword(cached_title)
        
        try:
            detail_url = vid
            if not detail_url.startswith("http"):
                if detail_url.startswith("/"):
                    detail_url = self.host + detail_url
                else:
                    detail_url = self.host + "/" + detail_url
            
            html = self._fetch_html(detail_url)
            if not html:
                return None
            
            title = self._extract_title_from_html(html)
            if title:
                self._title_cache[vid] = title
                return self._clean_keyword(title)
                
            id_match = re.search(r'/(\d+)\.html', vid)
            if id_match:
                return id_match.group(1)
                
        except Exception as e:
            self.log({"action": "extract_keyword_fail", "error": str(e)})
        
        return None

    def _clean_keyword(self, title):
        if not title:
            return None
        title = re.sub(r'【[^】]*】', '', title)
        title = re.sub(r'\[[^\]]*\]', '', title)
        title = re.sub(r'[【】\[\]（）()]', '', title)
        title = re.sub(r'[、，。！？\s]+$', '', title)
        
        parts = re.split(r'[，,、。.！!？?\\s]+', title)
        words = [w.strip() for w in parts if w.strip() and len(w.strip()) > 1]
        
        chinese_words = [w for w in words if re.search(r'[\u4e00-\u9fa5]', w)]
        if chinese_words:
            clean = chinese_words[:3]
            return " ".join(clean)
        
        if words:
            clean = words[:2]
            return " ".join(clean)
        
        return None

    def _extract_tid_from_vid(self, vid):
        """从视频ID中提取分类ID"""
        if not vid:
            return None
        # 视频路径中包含日期，无法直接提取分类
        # 默认返回日韩分类（cid=1）作为兜底
        return "1"
