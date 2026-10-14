# coding: utf-8
"""
站点: HuoPorn福利视频
域名: https://www.huoporn.lol
类型: 成人影视站 (苹果CMS)
版本: 1.0
说明: 支持分类浏览、详情、搜索、播放
"""

import json
import re
from urllib.parse import urljoin, quote, unquote
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.huoporn.lol"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类硬编码 - 从首页导航提取
        self.classes = [
            {"type_id": "1", "type_name": "国产"},
            {"type_id": "2", "type_name": "传媒"},
            {"type_id": "3", "type_name": "网红"},
            {"type_id": "4", "type_name": "大秀"},
            {"type_id": "5", "type_name": "探花"},
            {"type_id": "6", "type_name": "反差"},
            {"type_id": "7", "type_name": "颜值"},
            {"type_id": "8", "type_name": "中文"},
            {"type_id": "9", "type_name": "无码"},
            {"type_id": "10", "type_name": "日韩"},
            {"type_id": "11", "type_name": "欧美"},
            {"type_id": "12", "type_name": "动漫"},
            {"type_id": "13", "type_name": "人妻"},
            {"type_id": "14", "type_name": "制服"},
            {"type_id": "15", "type_name": "乱伦"},
            {"type_id": "16", "type_name": "明星"},
            {"type_id": "17", "type_name": "自拍"},
            {"type_id": "18", "type_name": "三级"},
            {"type_id": "20", "type_name": "师生"}
        ]
        # 筛选 - 站点无筛选功能，返回空
        self.filters = {tid: [] for tid in [str(i) for i in range(1, 19)] + ["20"]}

    def getName(self):
        return "HuoPorn"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐数据"""
        try:
            res = self.fetch(self.host + "/", headers=self.headers)
            if not res or res.status_code != 200:
                return {"list": []}
            html = res.text
            items = self._parse_video_list(html)
            return {"list": items[:20] if len(items) > 20 else items}
        except Exception as e:
            self.log({"action": "homeVideoContent", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
        try:
            res = self.fetch(url, headers=self.headers)
            if not res or res.status_code != 200:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = res.text
            items = self._parse_video_list(html)
            # 提取分页信息
            pagecount = self._parse_page_count(html)
            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount or 1,
                "limit": 20,
                "total": 0
            }
        except Exception as e:
            self.log({"action": "categoryContent", "tid": tid, "pg": page, "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        """详情页 - 提取播放地址"""
        try:
            # 兼容多种 ids 格式
            if isinstance(ids, list) and len(ids) > 0:
                vod_id = str(ids[0])
            elif isinstance(ids, str):
                # 如果 ids 是逗号分隔的字符串
                if ',' in ids:
                    vod_id = ids.split(',')[0].strip()
                else:
                    vod_id = ids
            else:
                vod_id = str(ids)
            
            # 去除可能的前缀
            vod_id = re.sub(r'[^0-9]', '', vod_id)
            if not vod_id:
                return {"list": []}
            
            url = f"{self.host}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
            self.log({"action": "detailContent", "url": url})
            res = self.fetch(url, headers=self.headers)
            if not res or res.status_code != 200:
                return {"list": []}
            html = res.text
            # 提取播放地址
            play_url = self._extract_play_url(html)
            # 提取标题
            title = self._extract_title(html)
            if not title:
                title_match = re.search(r'<h1[^>]*class="video-detail__title"[^>]*>([^<]+)</h1>', html)
                if title_match:
                    title = title_match.group(1).strip()
            if not title:
                title = f"视频_{vod_id}"
            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}" if play_url else ""
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent", "error": str(e)})
            return {"list": []}
    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        try:
            url = f"{self.host}/index.php/vod/search.html"
            data = {"wd": key}
            res = self.post(url, data=data, headers=self.headers)
            if not res or res.status_code != 200:
                return {"list": [], "page": int(pg)}
            html = res.text
            items = self._parse_video_list(html)
            # 过滤非关键词结果（部分HTML可能混杂首页数据）
            filtered = []
            for item in items:
                if key.lower() in item.get("vod_name", "").lower():
                    filtered.append(item)
            return {"list": filtered[:30] if len(filtered) > 30 else filtered, "page": int(pg)}
        except Exception as e:
            self.log({"action": "searchContent", "key": key, "error": str(e)})
            return {"list": [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        """播放"""
        if not id:
            return {"parse": 1, "url": "", "header": self.headers}
        # 如果已经是完整URL，直接播放
        if id.startswith("http://") or id.startswith("https://"):
            if id.endswith((".m3u8", ".mp4")):
                return {"parse": 0, "url": id, "header": self.headers}
            # 非媒体URL，尝试通过详情页提取
            return self._fetch_play_from_url(id)
        # 如果是ID，构造详情页URL提取
        if re.match(r"^\d+$", id):
            detail_url = f"{self.host}/index.php/vod/play/id/{id}/sid/1/nid/1.html"
            return self._fetch_play_from_url(detail_url)
        # 可能是参数格式，尝试解析
        return {"parse": 1, "url": id, "header": self.headers}

    def _fetch_play_from_url(self, url):
        """从详情页提取播放地址"""
        try:
            res = self.fetch(url, headers=self.headers)
            if not res or res.status_code != 200:
                return {"parse": 1, "url": url, "header": self.headers}
            html = res.text
            play_url = self._extract_play_url(html)
            if play_url and play_url.startswith("http"):
                return {"parse": 0, "url": play_url, "header": self.headers}
            # 尝试从player_aaaa中提取
            player_match = re.search(r'var\s+player_aaaa\s*=\s*({[^}]+})', html)
            if player_match:
                try:
                    data = json.loads(player_match.group(1))
                    url_in = data.get("url", "")
                    if url_in and url_in.startswith("http"):
                        return {"parse": 0, "url": url_in, "header": self.headers}
                except:
                    pass
            return {"parse": 1, "url": url, "header": self.headers}
        except Exception as e:
            self.log({"action": "_fetch_play_from_url", "error": str(e)})
            return {"parse": 1, "url": url, "header": self.headers}

    def _parse_video_list(self, html):
        """解析视频列表 - 使用正则提取"""
        items = []
        # 匹配 article.video-item 结构
        pattern = r'<article[^>]*class="[^"]*video-item[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<span[^>]*class="[^"]*video-item__duration[^"]*"[^>]*>([^<]*)</span>.*?<h3[^>]*class="[^"]*video-item__title[^"]*"[^>]*>([^<]*)</h3>'
        matches = re.findall(pattern, html, re.DOTALL)
        for href, pic, remark, title in matches:
            # 过滤广告：href 以 // 开头或包含 qq.com 等广告域名
            if not href or href.startswith('//') or 'qq.com' in href:
                continue
            if not title or title == '视频框广告内容，这里是文字介绍内容':
                continue
            vod_id_match = re.search(r'/vod/play/id/(\d+)/', href)
            vod_id = vod_id_match.group(1) if vod_id_match else href
            items.append({
                "vod_id": str(vod_id),
                "vod_name": title.strip(),
                "vod_pic": pic if pic.startswith("http") else urljoin(self.host, pic),
                "vod_remarks": remark.strip()
            })
        # 如果正则匹配失败，尝试备用模式
        if not items:
            items = self._parse_video_list_fallback(html)
        return items
    def _parse_video_list_fallback(self, html):
        """备用解析 - 更宽松的匹配"""
        items = []
        # 匹配 a 标签中的链接
        a_pattern = r'<a[^>]*href="(/index\.php/vod/play/id/\d+[^"]*)"[^>]*>'
        hrefs = re.findall(a_pattern, html)
        # 匹配标题
        title_pattern = r'<h3[^>]*class="[^"]*video-item__title[^"]*"[^>]*>([^<]+)</h3>'
        titles = re.findall(title_pattern, html)
        # 匹配图片
        img_pattern = r'<img[^>]*class="[^"]*video-item__image[^"]*"[^>]*src="([^"]+)"'
        pics = re.findall(img_pattern, html)
        # 匹配标签
        remark_pattern = r'<span[^>]*class="[^"]*video-item__duration[^"]*"[^>]*>([^<]+)</span>'
        remarks = re.findall(remark_pattern, html)
        for i, href in enumerate(hrefs):
            if i >= len(titles):
                break
            # 过滤广告
            if not href or 'qq.com' in href:
                continue
            title = titles[i] if i < len(titles) else ""
            if not title or title == '视频框广告内容，这里是文字介绍内容':
                continue
            vod_id_match = re.search(r'/vod/play/id/(\d+)/', href)
            vod_id = vod_id_match.group(1) if vod_id_match else href
            pic = pics[i] if i < len(pics) else ""
            remark = remarks[i] if i < len(remarks) else ""
            items.append({
                "vod_id": str(vod_id),
                "vod_name": title.strip(),
                "vod_pic": pic if pic.startswith("http") else urljoin(self.host, pic) if pic else "",
                "vod_remarks": remark.strip()
            })
        return items
    def _parse_page_count(self, html):
        """解析总页数"""
        # 从分页中提取最大页数
        pattern = r'<a[^>]*href="[^"]*page/(\d+)\.html"[^>]*>[\s]*(\d+)[\s]*</a>'
        matches = re.findall(pattern, html)
        pages = [int(m[1]) for m in matches if m[1].isdigit()]
        if pages:
            return max(pages)
        # 尝试从"共XX页"提取
        page_match = re.search(r'共\s*(\d+)\s*页', html)
        if page_match:
            return int(page_match.group(1))
        return 1

    def _extract_play_url(self, html):
        """提取播放地址"""
        # 方法1: 从 player_aaaa 对象提取
        player_match = re.search(r'var\s+player_aaaa\s*=\s*({[^}]+})', html)
        if player_match:
            try:
                data = json.loads(player_match.group(1))
                url = data.get("url", "")
                if url and url.startswith("http"):
                    return url
            except:
                pass
        # 方法2: 从 iframe src 提取
        iframe_pattern = r'<iframe[^>]*src="([^"]+)"[^>]*>'
        iframes = re.findall(iframe_pattern, html)
        for src in iframes:
            if src.startswith("http") and (".m3u8" in src or "m3u8" in src):
                return src
        # 方法3: 从视频标签提取
        video_pattern = r'<video[^>]*src="([^"]+)"'
        video_match = re.search(video_pattern, html)
        if video_match:
            return video_match.group(1)
        # 方法4: 从 script 中的 m3u8 URL 提取
        m3u8_pattern = r'https?://[^\s"\']+\.m3u8[^\s"\']*'
        m3u8_match = re.search(m3u8_pattern, html)
        if m3u8_match:
            return m3u8_match.group(0)
        return ""

    def _extract_title(self, html):
        """提取标题"""
        title_match = re.search(r'<h1[^>]*class="video-detail__title"[^>]*>([^<]+)</h1>', html)
        if title_match:
            return title_match.group(1).strip()
        # 从title标签提取
        title_match = re.search(r'<title>([^<]+)</title>', html)
        if title_match:
            t = title_match.group(1)
            t = re.sub(r'\s*-\s*.*$', '', t)
            return t.strip()
        return ""

    def localProxy(self, param):
        """m3u8 本地代理 - 默认不处理"""
        return [400, "text/plain", b"not implemented"]

    def log(self, data):
        """日志记录"""
        try:
            print("[HuoPorn]", json.dumps(data, ensure_ascii=False))
        except:
            pass