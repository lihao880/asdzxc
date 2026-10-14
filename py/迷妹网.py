# coding: utf-8
"""
站点: 迷妹网 (3bmm)
域名: https://pmrhniy.info/
备用域名: https://3bmm.com/
类型: 成人影视站 (HTML)
CMS: EmpireCMS 7.5
数据来源: HTML 解析
"""
import re
import json
import random
import requests
from urllib.parse import urljoin

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://pmrhniy.info/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host
        }
        self.classes = [
            {"type_id": "guochan", "type_name": "国产"},
            {"type_id": "zhibo", "type_name": "直播"},
            {"type_id": "rihan", "type_name": "日韩"},
            {"type_id": "oumei", "type_name": "欧美"},
            {"type_id": "sanji", "type_name": "三级"},
            {"type_id": "dongman", "type_name": "动漫"}
        ]
        self.filters = {}

    def getName(self):
        return "迷妹网"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host)
        items = self._parse_list(html, self.host)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        page = pg or "1"
        base_url = f"{self.host}suoyoushipin/{tid}/"
        if page == "1":
            url = base_url
        else:
            url = f"{base_url}index_{page}.html"
        
        html = self._fetch_html(url)
        items = self._parse_list(html, url)
        pagecount = self._get_pagecount(html)
        
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20
        }

    def detailContent(self, ids):
        vid = ids[0] if ids else ""
        if not vid:
            return {"list": []}
        
        if vid.startswith("http"):
            url = vid
        else:
            url = urljoin(self.host, vid)
        
        html = self._fetch_html(url)
        
        title_match = re.search(r'<title>(.+?)\s*-\s*迷妹网</title>', html)
        title = title_match.group(1).strip() if title_match else "未知视频"
        
        pic_match = re.search(r'<img[^>]+src="([^"]+)"[^>]+alt="[^"]*"', html)
        pic = pic_match.group(1) if pic_match else ""
        if pic and not pic.startswith("http"):
            pic = urljoin(self.host, pic)
        
        play_url = self._extract_play_url(html)
        
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": title,
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}" if play_url else ""
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg):
        if not key:
            return {"list": [], "page": 1}
        
        # 使用EmpireCMS搜索接口，需要包含 show=title
        data = {
            "keyboard": key,
            "show": "title"
        }
        url = f"{self.host}e/search/index.php"
        try:
            resp = self.post(url, data=data, headers=self.headers)
            html = resp.text
            items = self._parse_list(html, url)
            return {"list": items, "page": int(pg) if pg else 1}
        except Exception as e:
            return {"list": [], "page": int(pg) if pg else 1}

    def playerContent(self, flag, id, vipFlags=""):
        if not id:
            return {"parse": 1, "url": "", "header": {}}
        
        if id.endswith(".m3u8"):
            return {"parse": 0, "url": id, "header": self.headers}
        
        if id.startswith("http") or id.startswith("/"):
            html = self._fetch_html(id if id.startswith("http") else urljoin(self.host, id))
            play_url = self._extract_play_url(html)
            if play_url:
                return {"parse": 0, "url": play_url, "header": self.headers}
        
        return {"parse": 1, "url": id, "header": self.headers}

    def _fetch_html(self, url):
        """获取HTML，优先使用self.fetch，备选requests"""
        try:
            resp = self.fetch(url, headers=self.headers)
            if resp and hasattr(resp, 'text') and len(resp.text) > 1000:
                return resp.text
        except Exception as e:
            pass
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                return resp.text
        except Exception as e:
            pass
        return ""

    def _parse_list(self, html, base_url):
        items = []
        pattern = r'<li><a href="([^"]+)"[^>]*title="([^"]*)"[^>]*><img[^>]+src="([^"]+)"[^>]*>.*?<p>([^<]*)</p>.*?<span>([^<]*)</span>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for match in matches:
            href, title, img, p_text, span = match
            if not href.startswith("http") and not href.startswith("/suoyoushipin/"):
                continue
            if "/suoyoushipin/" not in href:
                continue
            vod_name = p_text.strip() or title.strip()
            vod_pic = img if img.startswith("http") else urljoin(base_url, img)
            vod_remarks = span.strip()
            items.append({
                "vod_id": href,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks
            })
        return items

    def _get_pagecount(self, html):
        page_nums = re.findall(r'<a[^>]+href="[^"]*index_(\d+)\.html"[^>]*>', html)
        if page_nums:
            return max(int(x) for x in page_nums)
        last_match = re.search(r'<a[^>]+href="[^"]*index_(\d+)\.html"[^>]*>尾页</a>', html)
        if last_match:
            return int(last_match.group(1))
        return 1

    def _extract_play_url(self, html):
        # 方法1: 从 fullVideoURL 变量提取
        match = re.search(r'fullVideoURL\s*=\s*["\']([^"\']+)["\']', html)
        if match:
            return match.group(1)
        
        # 方法2: 从 vservers 和 vHLSurl 拼接
        vservers_match = re.search(r'vservers\s*=\s*(\[[^\]]+\])', html)
        hlsurl_match = re.search(r'vHLSurl\s*=\s*["\']([^"\']+)["\']', html)
        if vservers_match and hlsurl_match:
            try:
                servers = json.loads(vservers_match.group(1).replace("'", '"'))
                if servers:
                    vsp = random.choice(servers)
                    return vsp + hlsurl_match.group(1)
            except:
                pass
        
        # 方法3: 从 vsp + hlsulr 拼接
        vsp_match = re.search(r'vsp\s*=\s*["\']([^"\']+)["\']', html)
        hls_match = re.search(r'hlsulr\s*=\s*["\']([^"\']+)["\']', html)
        if vsp_match and hls_match:
            return vsp_match.group(1) + hls_match.group(1)
        
        # 方法4: 从 video 标签 src 属性提取
        match = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', html)
        if match:
            return match.group(1)
        
        return ""