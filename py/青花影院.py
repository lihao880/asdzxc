# coding: utf-8
# 青花影院 TVBox 爬虫
# 站点: https://aasshhjj.cfd/
# CMS: 苹果CMS (MacCMS)
# 注意: 站点有反爬，搜索功能已禁用（返回500）

import re
import json
import urllib.parse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://aasshhjj.cfd/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host
        }
        self.classes = [
            {"type_id": "1", "type_name": "中文字幕"},
            {"type_id": "6", "type_name": "日韩视频"},
            {"type_id": "2", "type_name": "三级伦理"},
            {"type_id": "7", "type_name": "欧美专区"},
            {"type_id": "3", "type_name": "国产高清"},
            {"type_id": "8", "type_name": "熟女人妻"},
            {"type_id": "4", "type_name": "动漫精品"},
            {"type_id": "5", "type_name": "极度诱惑"},
        ]
        self.filters = {}
        self.site_name = "青花影院"

    def getName(self):
        return self.site_name

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def homeContent(self, filter=True):
        return {
            "class": self.classes,
            "filters": {str(cls["type_id"]): {} for cls in self.classes}
        }

    def getHomeContent(self, filter=True):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch(self.host)
        return self._parse_video_list(html, page="1", is_home=True)

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or 1)
        url = f"{self.host}index.php/vod/type/id/{tid}/page/{page}.html"
        html = self._fetch(url)
        return self._parse_video_list(html, page)

    def detailContent(self, ids):
        raw = str(ids[0])
        parts = raw.split("|$|")
        vod_id = parts[0]
        vod_name = parts[1] if len(parts) > 1 else ""
        vod_pic = parts[2] if len(parts) > 2 else ""
        vod_remark = parts[3] if len(parts) > 3 else ""
        play_url = parts[4] if len(parts) > 4 else f"{self.host}index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"

        vod = {
            "vod_id": raw,
            "vod_name": vod_name or "视频",
            "vod_pic": vod_pic,
            "vod_remarks": vod_remark,
            "vod_content": vod_remark,
            "vod_play_from": "直连",
            "vod_play_url": f"播放${play_url}"
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        try:
            html = self._fetch(id)
            pattern = r'var\s+player_aaaa\s*=\s*({[^}]+})'
            match = re.search(pattern, html)
            if match:
                data = json.loads(match.group(1))
                if data.get("encrypt") == 0 and data.get("url"):
                    return {"parse": 0, "url": data["url"], "header": self.headers}
            return {"parse": 1, "url": id}
        except:
            return {"parse": 1, "url": id}

    def searchContent(self, key, quick, pg="1"):
        # 站点搜索返回500错误，已禁用
        return {"list": []}

    def _fetch(self, url):
        try:
            res = self.fetch(url, headers=self.headers)
            if hasattr(res, 'text'):
                return res.text
            if isinstance(res, dict):
                return res.get('text', '')
            return ''
        except Exception as e:
            return ''

    def _post(self, url, data=None):
        try:
            res = self.post(url, data=data, headers=self.headers)
            if hasattr(res, 'text'):
                return res.text
            if isinstance(res, dict):
                return res.get('text', '')
            return ''
        except Exception as e:
            return ''

    def _parse_video_list(self, html, page="1", is_home=False):
        result = {"list": [], "page": int(page), "pagecount": 1}
        if not html:
            return result

        # 提取视频列表
        li_pattern = r'<li[^>]*class="[^"]*col-md-2[^"]*"[^>]*>(.*?)</li>'
        items = re.findall(li_pattern, html, re.DOTALL)
        for li_html in items:
            item = self._parse_item(li_html)
            if item:
                result["list"].append(item)

        # 如果是首页，不解析分页（首页无分页）
        if is_home:
            return result

        # 提取分页信息：从分页链接中提取最大页码
        # 匹配 "1 2 3 4 5" 或 "首页 上一页 1 2 3 4 5 下一页 尾页"
        page_links = re.findall(r'<a[^>]*>(\d+)</a>', html)
        if page_links:
            # 取最大的数字作为总页数
            max_page = max([int(x) for x in page_links if x.isdigit()])
            result["pagecount"] = max_page

        # 提取当前页码：从URL参数或seapage变量
        # 方式1: 从seapage变量提取
        seapage_match = re.search(r'seapage\s*=\s*["\']?(\d+)', html)
        if seapage_match:
            result["page"] = int(seapage_match.group(1))

        # 方式2: 从URL中的page参数提取
        page_match = re.search(r'[?&]page=(\d+)', html)
        if page_match:
            result["page"] = int(page_match.group(1))

        return result

    def _parse_item(self, li_html):
        try:
            # 封面图
            pic = ''
            m = re.search(r'background:\s*url\(([^)]+)\)', li_html)
            if m:
                pic = m.group(1).strip()
            if not pic:
                m = re.search(r'data-original=["\']([^"\']+)["\']', li_html)
                if m:
                    pic = m.group(1)

            # 标题 + 链接
            title = ''
            link = ''
            m = re.search(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']+)["\']', li_html)
            if not m:
                m = re.search(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', li_html)
            if m:
                link = m.group(1)
                title = m.group(2).strip()
                if not title:
                    title = re.sub(r'<[^>]+>', '', li_html)[:50]

            if not link or not title:
                return None

            if not link.startswith('http'):
                link = urllib.parse.urljoin(self.host, link)

            # 备注
            remark = ''
            m = re.search(r'<td><div[^>]*>([^<]+)</div></td>', li_html)
            if m:
                remark = m.group(1).strip()

            # 提取 vod_id
            vod_id = re.search(r'/vod/(?:play|detail)/id/(\d+)', link)
            vod_id = vod_id.group(1) if vod_id else link

            raw = f"{vod_id}|$|{title}|$|{pic}|$|{remark}|$|{link}"
            return {
                "vod_id": raw,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark
            }
        except:
            return None