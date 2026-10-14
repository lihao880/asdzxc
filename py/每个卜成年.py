# coding: utf-8
"""
站点名称: 每個蔔成年
主域名: https://mgwcn5.181802.xyz
内容类型: 影视站（HTML解析，视频播放）
"""
import re
import json
from urllib.parse import urljoin, quote
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://mgwcn5.181802.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.classes = [
            {"type_id": "95", "type_name": "中文传媒"},
            {"type_id": "96", "type_name": "麻豆传媒"},
            {"type_id": "97", "type_name": "精东影业"},
            {"type_id": "98", "type_name": "蜜桃传媒"},
            {"type_id": "99", "type_name": "果冻传媒"},
            {"type_id": "100", "type_name": "星空无限传媒"},
            {"type_id": "101", "type_name": "SA国际传媒"},
            {"type_id": "102", "type_name": "性视界传媒"},
            {"type_id": "103", "type_name": "天美传媒"},
            {"type_id": "104", "type_name": "皇家华人"},
            {"type_id": "105", "type_name": "扣扣传媒"},
            {"type_id": "106", "type_name": "91传媒"},
            {"type_id": "107", "type_name": "杏吧传媒"},
            {"type_id": "108", "type_name": "起点传媒"},
            {"type_id": "109", "type_name": "CCAV成人头条"},
            {"type_id": "110", "type_name": "渡边传媒"},
            {"type_id": "111", "type_name": "辣椒原创"},
            {"type_id": "112", "type_name": "红斯灯影像"},
            {"type_id": "113", "type_name": "情欲国潮"},
            {"type_id": "114", "type_name": "糖心传媒"},
            {"type_id": "115", "type_name": "乐播传媒"},
            {"type_id": "116", "type_name": "国产"},
            {"type_id": "117", "type_name": "国产自拍"},
            {"type_id": "118", "type_name": "国产偷拍"},
            {"type_id": "119", "type_name": "国产探花"},
            {"type_id": "120", "type_name": "国产主播"},
            {"type_id": "121", "type_name": "节目企划"},
            {"type_id": "122", "type_name": "国产网红"},
            {"type_id": "123", "type_name": "国产户外"},
            {"type_id": "124", "type_name": "国产吃瓜"},
            {"type_id": "125", "type_name": "台湾JVID"},
            {"type_id": "126", "type_name": "欧美视频"},
            {"type_id": "127", "type_name": "高清无码"},
            {"type_id": "128", "type_name": "高清有码"},
            {"type_id": "129", "type_name": "中文字幕"},
            {"type_id": "130", "type_name": "日本AV"},
            {"type_id": "131", "type_name": "日本中文字幕"},
            {"type_id": "132", "type_name": "日本无码流出"},
            {"type_id": "133", "type_name": "日本高清有码"},
            {"type_id": "134", "type_name": "日本东京热"},
            {"type_id": "135", "type_name": "日本一本道"},
            {"type_id": "136", "type_name": "日本素人"},
            {"type_id": "137", "type_name": "动漫"},
            {"type_id": "138", "type_name": "黄漫"},
            {"type_id": "139", "type_name": "里番中字"},
            {"type_id": "140", "type_name": "小重口味"},
            {"type_id": "141", "type_name": "男同"},
            {"type_id": "142", "type_name": "小众女同"},
            {"type_id": "143", "type_name": "TS人妖"},
            {"type_id": "144", "type_name": "白虎萌妹"},
            {"type_id": "145", "type_name": "SM虐待"},
            {"type_id": "146", "type_name": "NTR绿帽"},
            {"type_id": "147", "type_name": "明星网黄"},
            {"type_id": "148", "type_name": "葫芦影业"},
            {"type_id": "149", "type_name": "其他传媒"},
        ]
        self.filters = {}

    def getName(self):
        return "每個蔔成年"

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        return None

    def init(self, extend=""):
        self.setExtendInfo(extend)
        return None

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 取第一个分类的最新内容"""
        url = f"{self.host}/index.php/vod/type/id/95/page/1.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}
        return {"list": self._parse_list(html)}

    def _fetch_html(self, url):
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if resp and hasattr(resp, 'text'):
                return resp.text
            return ""
        except Exception:
            return ""

    def _parse_list(self, html):
        """解析视频列表"""
        items = []
        # 匹配卡片: layui-col-md3 ajax-item
        pattern = r'<div[^>]*class="[^"]*layui-col-md3[^"]*layui-col-xs12[^"]*ajax-item[^"]*"[^>]*>.*?<a[^>]*class="pic"[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*(?:lay-src|src)="([^"]+)"[^>]*>.*?<a[^>]*class="title"[^>]*href="[^"]*"[^>]*>([^<]+)</a>.*?</div>'
        matches = re.findall(pattern, html, re.S)
        for m in matches:
            url_detail, pic, name = m
            # 处理相对路径
            if not url_detail.startswith("http"):
                url_detail = urljoin(self.host, url_detail)
            pic = urljoin(self.host, pic)
            # 提取vod_id
            vid_match = re.search(r'/id/(\d+)', url_detail)
            vid = vid_match.group(1) if vid_match else url_detail
            items.append({
                "vod_id": vid,
                "vod_name": name.strip(),
                "vod_pic": pic + "@Referer=" + self.host + "/",
                "vod_remarks": "",
            })
        return items

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg and str(pg).isdigit() else 1
        except (ValueError, TypeError):
            page = 1
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

        items = self._parse_list(html)

        # 提取总页数
        pagecount = 1
        pager_match = re.search(r'<a[^>]*class="page-numbers"[^>]*href="[^"]*page/(\d+)"[^>]*>(\d+)</a>', html)
        if pager_match:
            pagecount = int(pager_match.group(2))
        # 找最大页码
        max_page_matches = re.findall(r'page/(\d+)\.html', html)
        if max_page_matches:
            max_p = max([int(p) for p in max_page_matches if p.isdigit()])
            if max_p > pagecount:
                pagecount = max_p

        return {
            "list": items,
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": len(items) if page == pagecount else page * 20
        }

    def detailContent(self, ids):
        # 兼容 ids 为 int、str 或 list
        if not ids:
            return {"list": []}
        if isinstance(ids, list):
            vid = str(ids[0])
        elif isinstance(ids, int):
            vid = str(ids)
        else:
            vid = str(ids)
        
        url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        # 提取标题 - 从 h1 中提取，去除 i 标签等HTML
        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if title_match:
            # 去除所有HTML标签，获取纯文本
            name = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
        else:
            name = ""

        # 提取播放地址 - 直接从 HTML 中匹配 "url":"..." 且包含 .m3u8 的地址
        play_url = ""
        url_match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
        if url_match:
            play_url = url_match.group(1).replace("\\/", "/")
        
        # 如果没找到，尝试匹配 video 或 iframe 的 src
        if not play_url:
            video_match = re.search(r'<video[^>]*src=["\']([^"\']+\.m3u8[^"\']*)["\']', html)
            if video_match:
                play_url = video_match.group(1)
        
        if not play_url:
            iframe_match = re.search(r'<iframe[^>]*src=["\']([^"\']+\.m3u8[^"\']*)["\']', html)
            if iframe_match:
                play_url = iframe_match.group(1)

        vod = {
            "vod_id": vid,
            "vod_name": name or "未知标题",
            "vod_pic": "",
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}" if play_url else "",
        }
        return {"list": [vod]}
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg and str(pg).isdigit() else 1
        except (ValueError, TypeError):
            page = 1
        url = f"{self.host}/index.php/vod/search/page/{page}/wd/{key}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": page}
        items = self._parse_list(html)
        return {"list": items, "page": page}

    def playerContent(self, flag, id, vipFlags):
        """
        flag: 线路标识
        id: 播放地址（直接从vod_play_url传入，可能是域名或完整URL）
        """
        play_url = str(id) if id else ""
        
        # 如果id是 "播放$url" 格式，提取URL部分
        if play_url and "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]
        
        # 如果提取到的URL不是http开头，补全为https
        if play_url and not play_url.startswith("http"):
            if not play_url.startswith("//"):
                play_url = "https://" + play_url
        
        if play_url:
            return {
                "parse": 0,
                "url": play_url,
                "header": {
                    "Referer": self.host + "/",
                    "User-Agent": self.headers["User-Agent"]
                }
            }
        
        return {"parse": 0, "url": "", "header": {}}
    def recommendContent(self, ids, pg="1"):
        return {"list": []}

    def destroy(self):
        pass

    def siteInfo(self):
        return {"current": self.host, "type": "影视站"}