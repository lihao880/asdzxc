# coding: utf-8
# 色猫视频 - TVBox爬虫
# 站点: https://semao212.xyz/

import re
import json
import urllib.parse
from urllib.parse import quote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://semao212.xyz"
        self.site_name = "色猫视频"
        
        self.classes = [
            {"type_id": "96", "type_name": "国产视频"},
            {"type_id": "97", "type_name": "网曝黑料"},
            {"type_id": "103", "type_name": "真实乱伦"},
            {"type_id": "135", "type_name": "直播裸聊"},
            {"type_id": "106", "type_name": "国产传媒"},
            {"type_id": "132", "type_name": "糖心vlog"},
            {"type_id": "142", "type_name": "少女萝莉"},
            {"type_id": "143", "type_name": "熟女少妇"},
            {"type_id": "123", "type_name": "国产自拍"},
            {"type_id": "139", "type_name": "群P换妻"},
            {"type_id": "144", "type_name": "酒店探花"},
            {"type_id": "141", "type_name": "偷拍盗摄"},
            {"type_id": "136", "type_name": "综合强片"},
            {"type_id": "140", "type_name": "醉酒强奸"},
            {"type_id": "138", "type_name": "户外野战"},
            {"type_id": "137", "type_name": "巨乳诱惑"},
            {"type_id": "131", "type_name": "明星换脸"},
            {"type_id": "114", "type_name": "日韩中字"},
            {"type_id": "113", "type_name": "日韩无码"},
            {"type_id": "133", "type_name": "无码素人"},
            {"type_id": "130", "type_name": "无码破解"},
            {"type_id": "121", "type_name": "欧美视频"},
        ]
        
        self.filters = {str(c["type_id"]): [] for c in self.classes}
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def getName(self):
        return "色猫视频"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/")
        items = self._parse_video_list(html)
        return {"list": items[:15]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg) if pg else "1"
        if pg == "1":
            url = f"{self.host}/index.php/vod/type/id/{tid}.html"
        else:
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"
        
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        page_count = self._parse_page_count(html)
        
        return {
            "list": items,
            "page": int(pg),
            "pagecount": page_count if page_count > 0 else 999,
            "limit": 20,
            "total": page_count * 20 if page_count > 0 else 9999,
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        
        if isinstance(ids, list):
            vid = str(ids[0])
        else:
            vid = str(ids)
        
        # 先访问详情页提取标题和图片
        detail_url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        detail_html = self._fetch_html(detail_url)
        
        vod_name = f"视频{vid}"
        vod_pic = ""
        vod_content = ""
        vod_actor = ""
        vod_director = ""
        vod_remarks = ""
        
        if detail_html:
            # 方法1: 从 <title> 提取标题
            title_pattern = r'<title>([^<]+)</title>'
            title_match = re.search(title_pattern, detail_html)
            if title_match:
                title = title_match.group(1).strip()
                # 去掉后缀 " - 色猫视频"
                title = title.replace(' - 色猫视频', '').strip()
                if title:
                    vod_name = title
            
            # 方法2: 从页面中的 h3 提取标题（详情页标题在 h3 中）
            if vod_name == f"视频{vid}":
                title_pattern2 = r'<h3[^>]*>([^<]+)</h3>'
                title_match2 = re.search(title_pattern2, detail_html)
                if title_match2:
                    vod_name = title_match2.group(1).strip()
            
            # 提取图片 - 查找 detail-cover 中的 img
            pic_pattern = r'<div[^>]*class="[^"]*detail-cover[^"]*"[^>]*>.*?<img[^>]*src="([^"]+)"'
            pic_match = re.search(pic_pattern, detail_html, re.DOTALL)
            if not pic_match:
                # 直接查找 img 标签
                pic_pattern2 = r'<img[^>]*src="([^"]+)"[^>]*>'
                pic_match = re.search(pic_pattern2, detail_html)
            if pic_match:
                vod_pic = pic_match.group(1)
                vod_pic = vod_pic.replace('&quot;', '').strip('"\'')
                if vod_pic.startswith('//'):
                    vod_pic = 'https:' + vod_pic
                elif vod_pic.startswith('/'):
                    vod_pic = self.host + vod_pic
        
        # 获取播放链接
        play_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        html = self._fetch_html(play_url)
        m3u8_url = self._extract_m3u8_from_html(html)
        
        if m3u8_url:
            vod = {
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
                "vod_actor": vod_actor,
                "vod_director": vod_director,
                "vod_content": vod_content,
                "vod_play_from": "播放",
                "vod_play_url": f"播放${m3u8_url}",
            }
        else:
            vod = {
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
                "vod_actor": vod_actor,
                "vod_director": vod_director,
                "vod_content": vod_content,
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}",
            }
        
        return {"list": [vod]}
    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        
        pg = str(pg) if pg else "1"
        encoded_key = quote(key)
        url = f"{self.host}/index.php/vod/search/wd/{encoded_key}.html"
        if pg != "1":
            url = f"{self.host}/index.php/vod/search/page/{pg}/wd/{encoded_key}.html"
        
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 1, "url": "", "header": self.headers}
        
        # 如果已经是 m3u8 链接，直接返回
        if id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0,
                "url": id,
                "header": {
                    "User-Agent": self.headers.get("User-Agent", ""),
                    "Referer": self.host + "/",
                }
            }
        
        # 如果是播放页URL，抓取页面提取m3u8
        if id.startswith("http"):
            html = self._fetch_html(id)
            m3u8_url = self._extract_m3u8_from_html(html)
            if m3u8_url:
                return {
                    "parse": 0,
                    "url": m3u8_url,
                    "header": {
                        "User-Agent": self.headers.get("User-Agent", ""),
                        "Referer": self.host + "/",
                    }
                }
            return {"parse": 1, "url": id, "header": self.headers}
        
        # 如果是 vod_id，构造播放页URL
        play_url = f"{self.host}/index.php/vod/play/id/{id}/sid/1/nid/1.html"
        html = self._fetch_html(play_url)
        m3u8_url = self._extract_m3u8_from_html(html)
        if m3u8_url:
            return {
                "parse": 0,
                "url": m3u8_url,
                "header": {
                    "User-Agent": self.headers.get("User-Agent", ""),
                    "Referer": self.host + "/",
                }
            }
        
        return {"parse": 1, "url": play_url, "header": self.headers}

    def recommendContent(self, ids, pg):
        """
        相关推荐接口 - 根据当前视频ID获取同类推荐
        """
        try:
            if not ids:
                return {"list": []}
            vid = str(ids[0]) if isinstance(ids, list) else str(ids)
            
            # 获取当前视频详情
            detail_result = self.detailContent([vid])
            detail_list = detail_result.get("list", [])
            if not detail_list:
                return {"list": []}
            
            vod_name = detail_list[0].get("vod_name", "")
            
            page = max(1, int(pg or 1))
            limit = 18
            seen = set()
            videos = []
            
            # 直接用视频标题搜索（取前6个字符）
            keyword = vod_name[:6].strip()
            if keyword and len(keyword) > 2:
                search_result = self.searchContent(keyword, 0, str(page))
                search_list = search_result.get("list", [])
                for item in search_list:
                    item_id = item.get("vod_id", "")
                    if item_id and item_id != vid and item_id not in seen:
                        seen.add(item_id)
                        videos.append(item)
                        if len(videos) >= limit:
                            break
            
            # 如果搜索结果不足，用分类推荐
            if len(videos) < 6:
                # 尝试获取分类ID
                tid = "96"  # 默认国产视频
                category_result = self.categoryContent(tid, str(page), {}, {})
                category_list = category_result.get("list", [])
                for item in category_list:
                    item_id = item.get("vod_id", "")
                    if item_id and item_id != vid and item_id not in seen:
                        seen.add(item_id)
                        videos.append(item)
                        if len(videos) >= limit:
                            break
            
            # 兜底：首页推荐
            if len(videos) < 4:
                home_result = self.homeVideoContent()
                home_list = home_result.get("list", [])
                for item in home_list:
                    item_id = item.get("vod_id", "")
                    if item_id and item_id != vid and item_id not in seen:
                        seen.add(item_id)
                        videos.append(item)
                        if len(videos) >= limit:
                            break
            
            return {"list": videos[:limit]}
            
        except Exception as e:
            if hasattr(self, 'log'):
                self.log('[recommendContent] 异常: %s' % e)
            return {"list": []}
    def destroy(self):
        pass

    def _fetch_html(self, url):
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if resp and hasattr(resp, "status_code") and resp.status_code == 200:
                return resp.text
            if resp and hasattr(resp, "text"):
                return resp.text
        except Exception as e:
            self.log(f"fetch error: {e}")
        return ""

    def _parse_video_list(self, html):
        items = []
        if not html:
            return items
        
        # 匹配视频卡片结构
        pattern = r'<li[^>]*class="[^"]*content-item[^"]*"[^>]*>.*?<a[^>]*href="[^"]*detail/id/(\d+)\.html[^"]*"[^>]*style="background-image:\s*url\([\'"]?([^\'"]+)[\'"]?\)"[^>]*>.*?<span[^>]*class="note[^"]*"[^>]*>(.*?)</span>.*?<h5[^>]*class="[^"]*video-title[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        seen = set()
        for vid, pic, date, title in matches:
            if vid in seen:
                continue
            title = title.strip()
            if re.match(r'^\d{4}-\d{2}-\d{2}$', title):
                continue
            if not title or len(title) < 2:
                continue
            seen.add(vid)
            # 清理图片URL
            pic = pic.replace('&quot;', '').strip('"\'')
            if pic.startswith('//'):
                pic = 'https:' + pic
            elif pic.startswith('/'):
                pic = self.host + pic
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": date,
            })
        
        # 回退方法：直接提取图片和标题
        if not items:
            # 提取视频项
            li_pattern = r'<li[^>]*class="[^"]*content-item[^"]*"[^>]*>(.*?)</li>'
            li_matches = re.findall(li_pattern, html, re.DOTALL)
            for li_html in li_matches:
                # 提取ID
                id_match = re.search(r'detail/id/(\d+)\.html', li_html)
                if not id_match:
                    continue
                vid = id_match.group(1)
                if vid in seen:
                    continue
                # 提取图片
                pic_match = re.search(r'background-image:\s*url\([\'"]?([^\'"]+)[\'"]?\)', li_html)
                pic = ""
                if pic_match:
                    pic = pic_match.group(1).replace('&quot;', '').strip('"\'')
                if pic.startswith('//'):
                    pic = 'https:' + pic
                elif pic.startswith('/'):
                    pic = self.host + pic
                # 提取标题
                title_match = re.search(r'<h5[^>]*>.*?<a[^>]*>([^<]+)</a>', li_html, re.DOTALL)
                title = title_match.group(1).strip() if title_match else f"视频{vid}"
                # 提取日期
                date_match = re.search(r'<span[^>]*class="note[^"]*"[^>]*>(.*?)</span>', li_html)
                date = date_match.group(1).strip() if date_match else ""
                seen.add(vid)
                items.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": date,
                })
        
        return items
    def _parse_page_count(self, html):
        if not html:
            return 1
        
        # 从页面中提取总页数
        pattern = r'<a[^>]*>(\d+)</a>[^<]*<a[^>]*>.*?下一页'
        matches = re.findall(pattern, html)
        if matches:
            try:
                return int(matches[-1])
            except:
                pass
        
        # 从"尾页"链接提取
        pattern2 = r'<a[^>]*href="[^"]*/page/(\d+)\.html"[^>]*>尾页</a>'
        match = re.search(pattern2, html)
        if match:
            try:
                return int(match.group(1))
            except:
                pass
        
        return 999

    def _extract_m3u8_from_html(self, html):
        if not html:
            return None
        
        # 方法1: 从 player_aaaa 对象中提取 (参考王室日报)
        pattern = r'var\s+player_aaaa\s*=\s*(\{[^;]+\});'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                url = data.get("url", "")
                if url and url.startswith("http") and (".m3u8" in url or ".mp4" in url):
                    return url
            except:
                pass
        
        # 方法2: 直接提取url字段
        pattern2 = r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"'
        match2 = re.search(pattern2, html)
        if match2:
            url = match2.group(1)
            if url and url.startswith("http"):
                return url
        
        # 方法3: 查找任何m3u8链接
        pattern3 = r'https?://[^"\']+\.m3u8[^"\']*'
        match3 = re.search(pattern3, html)
        if match3:
            return match3.group(0)
        
        return None