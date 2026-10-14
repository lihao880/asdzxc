# AVXXX Spider (MacCMS v10) - 修复URL重复问题
import re
import json
import urllib.request
import urllib.parse
import gzip
from io import BytesIO
from urllib.parse import urljoin

class Spider:
    def __init__(self):
        self.site_url = "https://avxxx.avxxx23.xyz/avxxx"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.site_url
        }
        
        self.categories = {
            "1": {"name": "视频分类", "url": "/index.php/vod/type/id/1.html"},
            "3": {"name": "国产视频", "url": "/index.php/vod/type/id/3.html"},
            "2": {"name": "网曝吃瓜", "url": "/index.php/vod/type/id/2.html"},
            "4": {"name": "日本无码", "url": "/index.php/vod/type/id/4.html"},
            "5": {"name": "日本有码", "url": "/index.php/vod/type/id/5.html"},
            "6": {"name": "无码中字", "url": "/index.php/vod/type/id/6.html"},
            "7": {"name": "有码中字", "url": "/index.php/vod/type/id/7.html"},
            "8": {"name": "欧美视频", "url": "/index.php/vod/type/id/8.html"},
            "9": {"name": "成人动漫", "url": "/index.php/vod/type/id/9.html"}
        }

    def init(self, cfg=None):
        pass

    def getDependence(self):
        return []

    def fetch(self, url):
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
                if resp.headers.get('Content-Encoding') == 'gzip':
                    buf = BytesIO(raw)
                    with gzip.GzipFile(fileobj=buf) as gz:
                        return gz.read().decode('utf-8', errors='ignore')
                return raw.decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"[ERROR] fetch: {e}")
            return ""

    def fix_url(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            # 如果URL已经包含站点地址，直接返回
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            # 如果URL以/开头，检查是否已经包含/avxxx前缀
            if url.startswith("/avxxx/"):
                # 已经是完整路径，直接拼接域名
                return "https://avxxx.avxxx23.xyz" + url
            return self.site_url + url
        return self.site_url + "/" + url

    def extract_vod_list(self, html):
        result = []
        
        li_pattern = r'<li[^>]*>(.*?)</li>'
        li_matches = re.findall(li_pattern, html, re.DOTALL)
        
        for li_html in li_matches:
            a_match = re.search(r'<a[^>]*class="[^"]*thumbnail[^"]*"[^>]*href="([^"]+)"[^>]*>', li_html)
            if not a_match:
                continue
            href = a_match.group(1)
            
            pic = ""
            pic_match = re.search(r'<img[^>]*data-original="([^"]+)"', li_html)
            if pic_match:
                pic = pic_match.group(1)
            if not pic:
                pic_match = re.search(r'<img[^>]*src="([^"]+)"', li_html)
                if pic_match:
                    pic = pic_match.group(1)
            
            if 'loading.svg' in pic or 'ynzq' in pic:
                pic = ""
            
            pic = self.fix_url(pic)
            
            title = ""
            title_match = re.search(r'<h5[^>]*>.*?<a[^>]*title="([^"]*)"[^>]*>([^<]*)</a>', li_html, re.DOTALL)
            if title_match:
                title = title_match.group(1) if title_match.group(1) else title_match.group(2)
            if not title:
                title_match = re.search(r'<h5[^>]*>.*?<a[^>]*>([^<]+)</a>', li_html, re.DOTALL)
                if title_match:
                    title = title_match.group(1)
            
            title = re.sub(r'\s+', ' ', title).strip()
            if not title:
                continue
            
            vod_id = self._extract_id(href)
            
            result.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": ""
            })
            
            if len(result) >= 20:
                break
        
        return result

    def homeContent(self, filter=False):
        result = {"class": [], "list": []}
        
        for tid, info in self.categories.items():
            result["class"].append({
                "type_id": tid,
                "type_name": info["name"]
            })
        
        html = self.fetch(self.site_url + "/")
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
        
        if p == 1:
            url = self.site_url + info["url"]
        else:
            base_url = info["url"].replace('.html', '')
            url = self.site_url + base_url + f'/page/{p}.html'
        
        html = self.fetch(url)
        if not html:
            return {"list": []}
        
        vod_list = self.extract_vod_list(html)
        
        pagecount = p
        page_match = re.findall(r'<a[^>]*href="[^"]*/page/(\d+)\.html"[^>]*>', html)
        if page_match:
            max_page = max(int(x) for x in page_match)
            pagecount = max_page
        
        return {
            "list": vod_list,
            "page": p,
            "pagecount": pagecount if pagecount > p else p + 1,
            "total": len(vod_list) * pagecount
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        
        vid = ids[0]
        if vid.startswith("http"):
            url = vid
        else:
            url = self.site_url + f"/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        
        html = self.fetch(url)
        if not html:
            return {"list": []}
        
        # 提取标题
        title = ""
        title_match = re.search(r'<div[^>]*style="[^"]*text-align:center[^"]*"[^>]*>.*?<b>([^<]+)</b>', html, re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
        if not title:
            og_match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html)
            if og_match:
                title = og_match.group(1).strip()
        if not title:
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                title = title_match.group(1)
        title = re.sub(r'[-—]\s*(?:成人视频在线观看|AVXXX|在线播放|成人色情视频|免费AV视频).*$', '', title).strip()
        title = re.sub(r'\s*[-—]\s*$', '', title).strip()
        
        # 提取封面
        pic = ""
        player_match = re.search(r'player_aaaa\s*=\s*({[^;]+})', html)
        if player_match:
            json_str = player_match.group(1)
            pic_match = re.search(r'"vod_pic"\s*:\s*"([^"]+)"', json_str)
            if pic_match:
                pic = self.fix_url(pic_match.group(1))
        if not pic:
            pic_match = re.search(r'<img[^>]*data-original="([^"]+)"[^>]*class="[^"]*pic[^"]*"', html)
            if pic_match:
                pic_candidate = pic_match.group(1)
                if 'loading.svg' not in pic_candidate and 'gif' not in pic_candidate:
                    pic = self.fix_url(pic_candidate)
        if not pic:
            pic_match = re.search(r'<img[^>]*(?:data-original|src)="([^"]+)"[^>]*>', html)
            if pic_match:
                pic_candidate = pic_match.group(1)
                if 'loading.svg' not in pic_candidate and 'gif' not in pic_candidate and 'ad' not in pic_candidate.lower():
                    pic = self.fix_url(pic_candidate)
        
        # 提取简介
        desc = ""
        desc_match = re.search(r'<div[^>]*class="[^"]*content[^"]*"[^>]*>([^<]+)</div>', html)
        if desc_match:
            desc = desc_match.group(1).strip()
        
        # 提取剧集 - 修复URL重复问题
        eps = []
        ep_pattern = r'<li[^>]*>.*?<a[^>]*href="([^"]*vod/play[^"]*)"[^>]*>([^<]+)</a>.*?</li>'
        ep_matches = re.findall(ep_pattern, html, re.DOTALL)
        for ep_url, ep_name in ep_matches:
            ep_name = ep_name.strip()
            if ep_name:
                # 使用 fix_url 处理，但 fix_url 已修复重复问题
                full_url = self.fix_url(ep_url)
                eps.append({"name": ep_name, "href": full_url})
        
        if not eps and player_match:
            json_str = player_match.group(1)
            url_match = re.search(r'"url"\s*:\s*"([^"]+)"', json_str)
            if url_match:
                play_url = url_match.group(1).replace('\\/', '/')
                eps.append({"name": "播放", "href": play_url})
        
        # 构建播放数据
        origins = ["默认"]
        play_from = []
        play_url_parts = []
        
        for origin in origins:
            play_from.append(origin)
            ep_parts = []
            for ep in eps:
                ep_parts.append(ep["name"] + "$" + ep["href"])
            if ep_parts:
                play_url_parts.append("#".join(ep_parts))
            else:
                play_url_parts.append("")
        
        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url_parts)
        }]}

    def searchContent(self, key, quick=False, pg=1):
        p = int(pg)
        url = self.site_url + "/index.php/vod/search.html?wd=" + urllib.parse.quote(key)
        if p > 1:
            url += "&page=" + str(p)
        
        html = self.fetch(url)
        if not html:
            return {"list": []}
        
        return {"list": self.extract_vod_list(html)}

    def playerContent(self, flag, id, vipFlags=[]):
        """获取播放地址 - 返回url+header"""
        if id.startswith("http"):
            html = self.fetch(id)
        else:
            html = self.fetch(self.fix_url(id))
        
        if not html:
            return {"parse": 0, "url": id}
        
        play_url = None
        
        # 1. 从 player_aaaa 对象提取 url
        player_match = re.search(r'player_aaaa\s*=\s*({[^;]+})', html)
        if player_match:
            json_str = player_match.group(1)
            url_match = re.search(r'"url"\s*:\s*"([^"]+)"', json_str)
            if url_match:
                play_url = url_match.group(1).replace('\\/', '/')
        
        # 2. 检查 iframe
        if not play_url:
            iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"', html)
            if iframe_match:
                play_url = self.fix_url(iframe_match.group(1))
        
        # 3. 检查 url 变量
        if not play_url:
            video_match = re.search(r'url\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html, re.IGNORECASE)
            if video_match:
                play_url = self.fix_url(video_match.group(1))
        
        # 4. 直接链接
        if not play_url:
            direct_match = re.search(r'(https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*)', html)
            if direct_match:
                play_url = direct_match.group(1)
        
        if not play_url:
            return {"parse": 0, "url": id}
        
        # 返回播放地址和header
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.site_url + "/",
            "Origin": self.site_url
        }
        return {"parse": 0, "url": play_url, "header": headers}

    def _extract_id(self, url):
        match = re.search(r'/id/(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'[?&]id=(\d+)', url)
        if match:
            return match.group(1)
        return '0'