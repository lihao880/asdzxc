# coding: utf-8
# 站点: 小淫虫
# 域名: https://xyca01.xiaoyc168.xyz/
# 类型: MacCMS 成人影视站
# 备注: 部分分类需会员(视频一区id=49)，其他分类正常

import re
import json
from urllib.parse import quote, urljoin, unquote, urlparse

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xyca01.xiaoyc168.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类硬编码
        self.classes = [
            {"type_id": "20", "type_name": "视频二区(经典三级)"},
            {"type_id": "24", "type_name": "视频三区"},
            {"type_id": "32", "type_name": "视频四区"},
            {"type_id": "40", "type_name": "视频五区"},
        ]
        # 注意: 视频一区 id=49 需会员，暂不加入
        self.filters = {}

    def getName(self):
        return "小淫虫"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐视频"""
        try:
            html = self.fetch(self.host + "/", headers=self.headers).text
            return {"list": self._parse_video_list(html)}
        except Exception as e:
            self.log({"action": "homeVideoContent", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        """分类列表"""
        page = pg or "1"
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
        try:
            html = self.fetch(url, headers=self.headers).text
            videos = self._parse_video_list(html)
            pagecount = self._parse_pagecount(html)
            return {
                "list": videos,
                "page": int(page),
                "pagecount": pagecount or 99,
                "limit": 20,
                "total": 0
            }
        except Exception as e:
            self.log({"action": "categoryContent", "tid": tid, "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        """详情页"""
        if isinstance(ids, list):
            vid = str(ids[0])
        else:
            vid = str(ids)
        url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        try:
            html = self.fetch(url, headers=self.headers).text
            return {"list": [self._parse_detail(html, vid)]}
        except Exception as e:
            self.log({"action": "detailContent", "vod_id": vid, "error": str(e)})
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        page = pg or "1"
        url = f"{self.host}/index.php/vod/search.html?wd={quote(key)}"
        if page and page != "1":
            url += f"&page={page}"
        try:
            html = self.fetch(url, headers=self.headers).text
            videos = self._parse_video_list(html)
            pagecount = self._parse_pagecount(html)
            return {
                "list": videos,
                "page": int(page),
                "pagecount": pagecount or 1,
                "limit": 20,
                "total": 0
            }
        except Exception as e:
            self.log({"action": "searchContent", "key": key, "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def playerContent(self, flag, id, vipFlags):
        """
        获取播放直链
        id 格式: id/{vid}/sid/{sid}/nid/{nid}.html
        优先返回 parse:0 直链，失败则降级为 parse:1 嗅探
        """
        play_url = f"{self.host}/index.php/vod/play/{id}"
        
        try:
            resp = self.fetch(play_url, headers=self.headers)
            if not resp or resp.status_code != 200:
                return {"parse": 1, "url": play_url, "header": self.headers}
            
            html = resp.text if hasattr(resp, 'text') else resp.content.decode('utf-8', errors='ignore')
            
            # 直接搜索 m3u8 链接
            m3u8_url = self._extract_m3u8(html)
            if m3u8_url:
                return {"parse": 0, "url": m3u8_url, "header": self.headers}
            
            # 提取 iframe 并递归
            iframe_url = self._extract_iframe(html)
            if iframe_url:
                m3u8_url = self._fetch_iframe_m3u8(iframe_url)
                if m3u8_url:
                    return {"parse": 0, "url": m3u8_url, "header": self.headers}
            
        except Exception as e:
            self.log({"action": "playerContent", "error": str(e)})
        
        # 降级: 交给 WebView 嗅探
        return {"parse": 1, "url": play_url, "header": self.headers}

    def _extract_m3u8(self, html):
        """从 HTML 中提取 m3u8 链接"""
        # 方法1: 直接搜索 "url":"https://...m3u8"
        match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html, re.IGNORECASE)
        if match:
            url = match.group(1)
            url = url.replace('\\/', '/')
            url = url.replace('\\\\/', '/')
            return url
        
        # 方法2: 搜索 player_aaaa 对象
        match = re.search(r'player_aaaa\s*=\s*({[^;]+});', html, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            json_str = json_str.replace('\\/', '/')
            json_str = json_str.replace('\\\\/', '/')
            try:
                data = json.loads(json_str)
                url = data.get('url', '')
                if url and (url.endswith('.m3u8') or 'm3u8' in url.lower()):
                    return url
            except:
                pass
        
        # 方法3: 直接搜索 .m3u8 链接
        match = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html, re.IGNORECASE)
        if match:
            url = match.group(0)
            url = url.replace('\\/', '/')
            url = url.replace('\\\\/', '/')
            return url
        
        return None

    def _extract_iframe(self, html):
        """提取 iframe src"""
        patterns = [
            r'<iframe[^>]+src=["\']([^"\']+)["\'][^>]*>',
            r'iframe\s*[:=]\s*["\']([^"\']+)["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                url = match.group(1)
                if url.startswith('//'):
                    url = 'https:' + url
                if not url.startswith('http'):
                    url = self.host + url if url.startswith('/') else self.host + '/' + url
                return url
        return None

    def _fetch_iframe_m3u8(self, iframe_url):
        """递归获取 iframe 中的 m3u8"""
        try:
            resp = self.fetch(iframe_url, headers=self.headers, timeout=10)
            if resp and resp.status_code == 200:
                html = resp.text if hasattr(resp, 'text') else resp.content.decode('utf-8', errors='ignore')
                return self._extract_m3u8(html)
        except Exception as e:
            self.log({"action": "_fetch_iframe_m3u8", "error": str(e)})
        return None

    def _parse_video_list(self, html):
        """解析视频列表"""
        videos = []
        pattern = r'<li\s+class="content-item">.*?<a\s+class="video-pic\s+loading"\s+href="([^"]+)"\s+title="([^"]*)"[^>]*>.*?<img[^>]+data-original="([^"]+)"[^>]*>.*?<span\s+class="note[^>]*>([^<]*)</span>.*?<h5[^>]*>.*?<a[^>]*>([^<]*)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            href, title_pic, pic, remark, title = match
            vod_id = href.replace("/index.php/vod/detail/id/", "").replace(".html", "") if "/detail/" in href else ""
            videos.append({
                "vod_id": vod_id or href,
                "vod_name": title or title_pic or "未知",
                "vod_pic": pic,
                "vod_remarks": remark
            })
        return videos

    def _parse_detail(self, html, vod_id):
        """解析详情页"""
        title = ""
        title_match = re.search(r'<h2\s+class="text-ellipsis"[^>]*>([^<]+)</h2>', html)
        if title_match:
            title = title_match.group(1).strip()

        type_text = ""
        remark = ""
        type_match = re.search(r'<p>\s*视频类型：([^<]+)\s*</p>', html)
        if type_match:
            type_text = type_match.group(1).strip()
        update_match = re.search(r'<p>\s*更新时间：([^<]+)\s*</p>', html)
        if update_match:
            remark = update_match.group(1).strip()

        pic = ""
        pic_match = re.search(r'<img[^>]+class="lazy"[^>]+data-original="([^"]+)"', html)
        if pic_match:
            pic = pic_match.group(1)

        play_from = []
        play_url = []

        line_pattern = r'<a[^>]+class="btn[^"]*"[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
        line_matches = re.findall(line_pattern, html)
        for href, name in line_matches:
            if "/vod/play/" in href:
                play_from.append(name.strip())
                play_id = href.replace("/index.php/vod/play/", "")
                play_url.append(play_id)

        if not play_from:
            play_from.append("默认线路")
            play_url.append(f"id/{vod_id}/sid/1/nid/1.html")

        vod = {
            "vod_id": vod_id,
            "vod_name": title or "未知视频",
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_content": type_text,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url)
        }
        return vod

    def _parse_pagecount(self, html):
        """解析总页数"""
        match = re.search(r'共(\d+)条数据', html)
        if match:
            total = int(match.group(1))
            return (total + 19) // 20
        match = re.search(r'<em[^>]*>(\d+)/(\d+)</em>', html)
        if match:
            return int(match.group(2))
        match = re.search(r'<a[^>]+href="[^"]*/page/(\d+).html"[^>]*>尾页</a>', html)
        if match:
            return int(match.group(1))
        return 1