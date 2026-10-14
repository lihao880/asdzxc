# coding: utf-8
# TVBox/FongMi 爬虫 - ero-video.net
# 站点: https://en.ero-video.net/

import re
import json
from urllib.parse import urljoin, quote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.host = "https://ero-video.net"
        # 使用移动端 UA，确保获取到的 HTML 包含 NMA.video.url
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1"
        }
        self.classes = [
            {"type_id": "15988", "type_name": "素人"},
            {"type_id": "38597", "type_name": "巨乳"},
            {"type_id": "38602", "type_name": "人妻"},
            {"type_id": "16024", "type_name": "中出し"},
            {"type_id": "38704", "type_name": "FC2-PPV"},
            {"type_id": "a3gZfDemj1i3QOCN433l", "type_name": "カリビアン"},
            {"type_id": "38665", "type_name": "美少女"},
            {"type_id": "15957", "type_name": "盗撮"},
            {"type_id": "38623", "type_name": "コスプレ"},
        ]
        # 存储上一次请求的 cookie
        self.cookie_jar = {}

    def getName(self):
        return "erovideo"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            html = self._fetch_html(self.host + "/?sort=latest")
            videos = self._parse_video_list(html)
            return {"list": videos[:20]} if videos else {"list": []}
        except Exception as e:
            self.log({"action": "homeVideoContent_fail", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        if tid.startswith("a3gZfDemj1i3QOCN433l"):
            url = f"{self.host}/?mmc={tid}&sort=latest&page={page}"
        else:
            url = f"{self.host}/?t[]={tid}&sort=latest&page={page}"
        
        try:
            html = self._fetch_html(url)
            videos = self._parse_video_list(html)
            total_pages = self._get_total_pages(html)
            return {
                "list": videos,
                "page": int(page),
                "pagecount": total_pages if total_pages > 0 else 99,
                "limit": 20,
                "total": 999
            }
        except Exception as e:
            self.log({"action": "categoryContent_fail", "tid": tid, "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 0, "limit": 20, "total": 0}

    def detailContent(self, ids):
        raw = str(ids[0])
        parts = raw.split('|$|')
        vod_id = parts[0]
        vod_name = parts[1] if len(parts) > 1 else ""
        vod_pic = parts[2] if len(parts) > 2 else ""
        vod_remark = parts[3] if len(parts) > 3 else ""
        play_url = parts[4] if len(parts) > 4 else f"/movie/?mcd={vod_id}"
        
        vod = {
            "vod_id": raw,
            "vod_name": vod_name or "视频",
            "vod_pic": vod_pic,
            "vod_remarks": vod_remark,
            "vod_content": vod_remark,
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}"
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        try:
            page = pg or "1"
            url = f"{self.host}/?q={quote(key)}&page={page}"
            html = self._fetch_html(url)
            videos = self._parse_video_list(html)
            total_pages = self._get_total_pages(html)
            return {
                "list": videos,
                "page": int(page),
                "pagecount": total_pages if total_pages > 0 else 1
            }
        except Exception as e:
            self.log({"action": "searchContent_fail", "key": key, "error": str(e)})
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        """
        播放 - 两步提取:
        1. 从详情页提取 window.NMA.video.url (hls端点)
        2. 请求hls端点获取真正的m3u8地址
        """
        if id.startswith("http") and (".m3u8" in id or ".mp4" in id):
            return {"parse": 0, "url": id, "header": self.headers}
        
        if not id.startswith("http"):
            play_url = urljoin(self.host, id)
        else:
            play_url = id
        
        try:
            self.log({"action": "playerContent_start", "play_url": play_url})
            
            # 先请求一次获取 cookie
            resp = self.fetch(play_url, headers=self.headers)
            html = resp.text
            
            self.log({"action": "playerContent_html_length", "length": len(html)})
            
            # 调试：检查是否包含关键特征
            has_nma = "NMA.video" in html
            self.log({"action": "playerContent_has_nma", "value": has_nma})
            
            # 尝试多种方式提取
            hls_endpoint = None
            
            # 方法1: window.NMA.video.url
            patterns = [
                r'window\.NMA\.video\.url\s*=\s*"([^"]+)"',
                r'NMA\.video\.url\s*=\s*"([^"]+)"',
                r'video\.url\s*=\s*"([^"]+)"',
                r'"sources"\s*:\s*\[\s*\{[^}]*"src"\s*:\s*"([^"]+)"',
                r'/movie/hls/\?mcd=[^&\s"\']+[^"\']*'
            ]
            
            for i, pattern in enumerate(patterns):
                m = re.search(pattern, html, re.DOTALL if i == 3 else 0)
                if m:
                    hls_endpoint = m.group(1) if i < 4 else m.group(0)
                    self.log({"action": f"playerContent_extract_method_{i+1}", "hls": hls_endpoint})
                    break
            
            if hls_endpoint:
                if hls_endpoint.startswith("/"):
                    hls_endpoint = self.host + hls_endpoint
                
                self.log({"action": "playerContent_fetch_hls", "hls_endpoint": hls_endpoint})
                
                hls_resp = self.fetch(hls_endpoint, headers=self.headers)
                m3u8_content = hls_resp.text
                
                self.log({"action": "playerContent_hls_response", "content": m3u8_content[:300]})
                
                # 解析m3u8中的媒体地址
                real_m3u8_match = re.search(r'https?://[^\s]+\.mp4', m3u8_content)
                if real_m3u8_match:
                    real_m3u8 = real_m3u8_match.group(0).strip()
                    self.log({"action": "playerContent_success", "m3u8": real_m3u8})
                    # 播放头只保留 UA，避免第三方 CDN 因 Referer 问题被拦截
                    play_headers = {
                        "User-Agent": self.headers.get("User-Agent", "Mozilla/5.0"),
                        "Referer": play_url,
                        "Cookie": self.cookie_jar.get("pref", "")
                    }
                    return {"parse": 0, "url": real_m3u8, "header": play_headers}
                
                url_match = re.search(r'https?://[^\s]+', m3u8_content)
                if url_match:
                    real_m3u8 = url_match.group(0).strip()
                    self.log({"action": "playerContent_success_fallback", "m3u8": real_m3u8})
                    return {"parse": 0, "url": real_m3u8, "header": self.headers}
            
            self.log({"action": "playerContent_fallback_parse1", "play_url": play_url})
            return {"parse": 1, "url": play_url, "header": self.headers}
            
        except Exception as e:
            self.log({"action": "playerContent_exception", "url": play_url, "error": str(e)})
            return {"parse": 1, "url": play_url, "header": self.headers}

    # ---------- 辅助方法 ----------

    def _fetch_html(self, url):
        resp = self.fetch(url, headers=self.headers)
        return resp.text

    def _parse_video_list(self, html):
        videos = []
        pattern = r'<article\s+class="c-movie"[^>]*>(.*?)</article>'
        blocks = re.findall(pattern, html, re.DOTALL)
        
        for block in blocks:
            try:
                link_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*>', block)
                if not link_match:
                    continue
                link = link_match.group(1)
                
                mcd_match = re.search(r'mcd=([^&\s"\']+)', link)
                if not mcd_match:
                    continue
                vod_id = mcd_match.group(1)
                
                title = ""
                title_match = re.search(r'<h2[^>]*class="c-movie--head"[^>]*>(.*?)</h2>', block, re.DOTALL)
                if title_match:
                    title = self._clean_text(title_match.group(1))
                if not title:
                    title_match2 = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.DOTALL)
                    if title_match2:
                        title = self._clean_text(title_match2.group(1))
                
                pic = ""
                pic_match = re.search(r'<source[^>]+srcset="([^"]+)"', block)
                if pic_match:
                    pic = pic_match.group(1).split()[0]
                if not pic:
                    pic_match2 = re.search(r'<img[^>]+src="([^"]+)"', block)
                    if pic_match2:
                        pic = pic_match2.group(1)
                if pic and not pic.startswith("http"):
                    pic = self.host + pic
                
                duration = ""
                duration_match = re.search(r'<time[^>]*class="c-movie--duration"[^>]*>(.*?)</time>', block)
                if duration_match:
                    duration = duration_match.group(1).strip()
                
                quality = ""
                quality_match = re.search(r'<strong[^>]*class="c-movie--quality"[^>]*>(.*?)</strong>', block)
                if quality_match:
                    quality = quality_match.group(1).strip()
                
                full_vod_id = f"{vod_id}|$|{title}|$|{pic}|$|{quality} {duration}|$|/movie/?mcd={vod_id}"
                
                videos.append({
                    "vod_id": full_vod_id,
                    "vod_name": title or "视频",
                    "vod_pic": pic,
                    "vod_remarks": f"{quality} {duration}".strip() or "HD"
                })
            except Exception as e:
                continue
        
        return videos

    def _get_total_pages(self, html):
        page_links = re.findall(r'<a[^>]+href="[^"]*page=(\d+)"[^>]*>', html)
        if page_links:
            pages = [int(p) for p in page_links]
            return max(pages)
        return 1

    def _clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()