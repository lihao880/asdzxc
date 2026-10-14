# coding=utf-8
"""
BOSSTV 爬虫源
站点: https://bosstv901.xyz
"""

import re
import json
import urllib.request
import urllib.parse
from urllib.parse import urljoin

class Spider:
    def __init__(self):
        self.site_url = "https://bosstv901.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.site_url
        }
        self.timeout = 15
        self.categories = {
            "1": {"name": "日韩无码", "url": "/index.php/vod/type/id/1.html"},
            "2": {"name": "国产精品", "url": "/index.php/vod/type/id/2.html"},
            "3": {"name": "日韩精品", "url": "/index.php/vod/type/id/3.html"},
            "4": {"name": "欧美精品", "url": "/index.php/vod/type/id/4.html"},
            "5": {"name": "自拍偷拍", "url": "/index.php/vod/type/id/5.html"},
            "6": {"name": "中文字幕", "url": "/index.php/vod/type/id/6.html"},
            "7": {"name": "人妻系列", "url": "/index.php/vod/type/id/7.html"},
            "8": {"name": "制服诱惑", "url": "/index.php/vod/type/id/8.html"},
            "9": {"name": "强奸乱伦", "url": "/index.php/vod/type/id/9.html"},
            "10": {"name": "AV明星", "url": "/index.php/vod/type/id/10.html"},
            "11": {"name": "国产传媒", "url": "/index.php/vod/type/id/11.html"},
            "12": {"name": "巨乳系列", "url": "/index.php/vod/type/id/12.html"},
            "13": {"name": "颜射系列", "url": "/index.php/vod/type/id/13.html"},
            "14": {"name": "自慰系列", "url": "/index.php/vod/type/id/14.html"},
        }

    def init(self, cfg=None):
        pass

    def getDependence(self):
        return []

    def fetch(self, url):
        if not url.startswith("http"):
            url = self.site_url + url
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception:
            return ""

    def fix_url(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        return urljoin(self.site_url, url)

    def extract_vod_list(self, html):
        result = []
        pattern = r'<a[^>]*href="(/index\.php/vod/detail/id/\d+\.html)"[^>]*>'
        links = re.findall(pattern, html)
        for href in links:
            try:
                pos = html.find(href)
                if pos == -1:
                    continue
                context = html[max(0, pos-300):min(len(html), pos+600)]
                id_match = re.search(r'/detail/id/(\d+)\.html', href)
                if not id_match:
                    continue
                vod_id = id_match.group(1)
                title = ""
                alt_match = re.search(r'alt="([^"]*)"', context)
                if alt_match and alt_match.group(1):
                    title = alt_match.group(1).strip()
                if not title:
                    name_match = re.search(r'vod-name[^>]*>([^<]+)', context)
                    if name_match:
                        title = name_match.group(1).strip()
                if not title:
                    continue
                pic = ""
                img_match = re.search(r'<img[^>]*src="([^"]+)"', context)
                if img_match:
                    pic = self.fix_url(img_match.group(1))
                if not pic:
                    data_match = re.search(r'data-original="([^"]+)"', context)
                    if data_match:
                        pic = self.fix_url(data_match.group(1))
                remark = ""
                time_match = re.search(r'vod-class[^>]*>([^<]+)', context)
                if time_match:
                    remark = time_match.group(1).strip()
                result.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
            except:
                continue
        return result

    def homeContent(self, filter=False):
        result = {"class": [], "list": []}
        for tid, info in self.categories.items():
            result["class"].append({"type_id": tid, "type_name": info["name"]})
        html = self.fetch("/")
        if html:
            result["list"] = self.extract_vod_list(html)
        return result

    def homeVideoContent(self):
        return self.homeContent(filter=False)

    def categoryContent(self, tid, pg=1, filter=False, extend={}):
        p = int(pg)
        info = self.categories.get(str(tid))
        if not info:
            return {"list": []}
        url = info["url"] + "?page=" + str(p)
        html = self.fetch(url)
        if not html:
            return {"list": []}
        vod_list = self.extract_vod_list(html)
        pagecount = 1
        total_match = re.search(r'<a[^>]*href="[^"]*/page/(\d+)\.html"[^>]*>尾頁</a>', html)
        if total_match:
            pagecount = int(total_match.group(1))
        else:
            page_links = re.findall(r'<a[^>]*href="[^"]*/page/(\d+)\.html"[^>]*>(\d+)</a>', html)
            for match in page_links:
                if int(match[1]) > pagecount:
                    pagecount = int(match[1])
        return {"list": vod_list, "page": p, "pagecount": pagecount, "total": len(vod_list) * pagecount}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        url = self.site_url + "/index.php/vod/detail/id/" + vod_id + ".html"
        html = self.fetch(url)
        if not html:
            return {"list": []}
        title = ""
        h1_match = re.search(r'<h1>资源名称：\s*([^<]+)</h1>', html)
        if h1_match:
            title = h1_match.group(1).strip()
        pic = ""
        img_match = re.search(r'<img[^>]*src="([^"]+)"[^>]*title="[^"]*"', html)
        if img_match:
            pic = self.fix_url(img_match.group(1))
        play_matches = re.findall(r'<a class="button22"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', html)
        play_from = []
        play_urls = []
        for href, name in play_matches:
            play_from.append(name.strip())
            play_urls.append(href)
        if not play_from:
            play_from = ["BOSSTV"]
            play_urls = ["/index.php/vod/play/id/" + vod_id + "/sid/1/nid/1.html"]
        return {"list": [{
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": "",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_urls)
        }]}

    def searchContent(self, key, quick=False, pg=1):
        p = int(pg)
        url = self.site_url + "/index.php/vod/search.html?wd=" + urllib.parse.quote(key) + "&page=" + str(p)
        html = self.fetch(url)
        if not html:
            return {"list": []}
        return {"list": self.extract_vod_list(html)}

    def playerContent(self, flag, id, vipFlags=[]):
        if not id:
            return {"parse": 0, "playUrl": ""}
        if id.startswith("http"):
            play_url = id
        else:
            play_url = self.site_url + id
        html = self.fetch(play_url)
        if not html:
            return {"parse": 0, "playUrl": play_url}
        
        # 方法1: 从 player_aaaa 对象中提取 url
        start = html.find('var player_aaaa')
        if start != -1:
            sub = html[start:start+2000]
            # 匹配 "url":"https:\/\/xxx"
            match = re.search(r'"url"\s*:\s*"((?:[^"\\]|\\.)*)"', sub)
            if match:
                video_url = match.group(1).replace('\\/', '/')
                if video_url.startswith('http'):
                    return {"parse": 0, "playUrl": video_url}
        
        # 方法2: 从 iframe 中提取
        iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"', html)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            m3u8_param = re.search(r'url=([^&\"]+)', iframe_url)
            if m3u8_param:
                return {"parse": 0, "playUrl": urllib.parse.unquote(m3u8_param.group(1))}
            return {"parse": 0, "playUrl": iframe_url}
        
        # 方法3: 直接找 m3u8
        m3u8_match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
        if m3u8_match:
            return {"parse": 0, "playUrl": m3u8_match.group(0)}
        
        return {"parse": 0, "playUrl": play_url}


if __name__ == '__main__':
    s = Spider()
    print('=' * 50)
    print('测试 homeContent')
    result = s.homeContent(False)
    print(f'分类: {len(result.get("class", []))} 个')
    print(f'视频: {len(result.get("list", []))} 条')
    print('=' * 50)
    print('测试 playerContent')
    result = s.playerContent('1', '/index.php/vod/play/id/26728/sid/1/nid/1.html')
    print(f'播放地址: {result.get("playUrl", "")}')