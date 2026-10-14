import re
import json
import urllib.request
import urllib.parse
from urllib.parse import urljoin

class Spider:
    def __init__(self):
        self.site_url = "https://hqwo.pgdvd.live"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.site_url
        }
        
        self.categories = {
            "20": {"name": "国产大制作"},
            "21": {"name": "偷拍自拍"},
            "22": {"name": "乱伦毁三观"},
            "23": {"name": "主播女网红"},
            "24": {"name": "黑料网曝"},
            "25": {"name": "高清无码"},
            "26": {"name": "中文字幕"},
            "27": {"name": "欧美精品"},
            "28": {"name": "淫乱学生妹"},
            "29": {"name": "动漫精选"},
            "30": {"name": "高清有码"},
            "31": {"name": "日本素人"},
            "32": {"name": "无码流出"},
            "33": {"name": "FC2"},
            "34": {"name": "会所技师"},
            "35": {"name": "国产推荐"},
            "36": {"name": "探花约炮"},
            "37": {"name": "韩国直播"},
            "38": {"name": "国产直播"},
            "39": {"name": "淫妻绿帽"},
            "40": {"name": "制服诱惑"},
            "41": {"name": "重口猎奇"},
            "42": {"name": "东京热"},
            "43": {"name": "一本道"},
            "44": {"name": "欧美精品"}
        }

    def init(self, cfg=None):
        pass

    def getDependence(self):
        return []

    def fetch(self, url):
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
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
        pattern = r'<a\s+class="vtz9"\s+href="([^"]+)"[^>]*>.*?<img[^>]*data-src="([^"]+)"[^>]*>.*?<cite>([^<]+)</cite>'
        matches = re.findall(pattern, html, re.DOTALL)
        for href, img_url, title in matches[:20]:
            try:
                full_url = self.fix_url(href)
                vid_match = re.search(r'id/(\d+)', full_url)
                vod_id = vid_match.group(1) if vid_match else ""
                result.append({
                    "vod_id": vod_id,
                    "vod_name": title.strip(),
                    "vod_pic": self.fix_url(img_url)
                })
            except:
                continue
        return result

    def homeContent(self, filter=False):
        result = {"class": [], "list": []}
        for tid, info in self.categories.items():
            result["class"].append({"type_id": tid, "type_name": info["name"]})
        html = self.fetch(self.site_url + "/")
        if html:
            result["list"] = self.extract_vod_list(html)
        return result

    def homeVideoContent(self):
        return self.homeContent(filter=False)

    def categoryContent(self, tid, pg=1, filter=False, extend={}):
        p = int(pg)
        if tid not in self.categories:
            return {"list": []}
        url = self.site_url + "/index.php/vod/type/id/" + tid + "/page/" + str(p) + ".html"
        html = self.fetch(url)
        if not html:
            return {"list": []}
        vod_list = self.extract_vod_list(html)
        pagecount = p
        page_match = re.search(r'<a[^>]*href="[^"]*page/(\d+)\.html"[^>]*>尾页</a>', html)
        if page_match:
            pagecount = int(page_match.group(1))
        return {"list": vod_list, "page": p, "pagecount": pagecount}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        play_url = self.site_url + "/index.php/vod/play/id/" + str(vod_id) + "/sid/1/nid/1.html"
        html = self.fetch(play_url)
        if not html:
            return {"list": []}
        
        # 提取标题
        title = ""
        title_match = re.search(r'<title>(.*?)</title>', html)
        if title_match:
            title = re.sub(r'[-–—|].*$', '', title_match.group(1)).strip()
        
        # 提取封面
        pic = ""
        img_match = re.search(r'<img[^>]*data-src="([^"]+)"', html)
        if img_match:
            pic = self.fix_url(img_match.group(1))
        
        # 提取简介
        desc = ""
        desc_match = re.search(r'<div[^>]*class="[^"]*desc[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        if desc_match:
            desc = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
        
        # 提取所有集数 (nid)
        eps = []
        # 方法1: 从播放页提取选集
        ep_pattern = r'<a[^>]*href="[^"]*nid/(\d+)[^"]*"[^>]*>([^<]+)</a>'
        ep_matches = re.findall(ep_pattern, html)
        if ep_matches:
            seen = set()
            for nid, name in ep_matches:
                if nid in seen:
                    continue
                seen.add(nid)
                name = re.sub(r'<[^>]+>', '', name).strip()
                if not name or name == 'undefined':
                    name = "第" + nid + "集"
                eps.append({"nid": nid, "name": name})
        
        # 方法2: 从li标签提取
        if not eps:
            li_pattern = r'<li[^>]*>.*?<a[^>]*href="[^"]*nid/(\d+)[^"]*"[^>]*>([^<]+)</a>'
            li_matches = re.findall(li_pattern, html, re.DOTALL)
            seen = set()
            for nid, name in li_matches:
                if nid in seen:
                    continue
                seen.add(nid)
                name = re.sub(r'<[^>]+>', '', name).strip()
                if not name or name == 'undefined':
                    name = "第" + nid + "集"
                eps.append({"nid": nid, "name": name})
        
        # 如果没有集数，默认1集
        if not eps:
            eps = [{"nid": "1", "name": "正片"}]
        
        # 构建线路和播放URL
        # 使用 $$$ 分隔多个线路，使用 # 分隔剧集，使用 $ 分隔剧集名和URL
        play_from = ["苹果DVD"]
        play_url_parts = []
        
        for ep in eps:
            ep_url = self.site_url + "/index.php/vod/play/id/" + str(vod_id) + "/sid/1/nid/" + ep["nid"] + ".html"
            play_url_parts.append(ep["name"] + "$" + ep_url)
        
        vod_play_url = "#".join(play_url_parts)
        vod_play_from = "$$$".join(play_from)
        
        return {"list": [{
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }]}

    def searchContent(self, key, quick=False, pg=1):
        search_url = self.site_url + "/index.php/vod/search.html"
        data = urllib.parse.urlencode({'wd': key}).encode('utf-8')
        req = urllib.request.Request(search_url, data=data, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
        except:
            return {"list": []}
        return {"list": self.extract_vod_list(html)}

    def playerContent(self, flag, id, vipFlags=[]):
        html = self.fetch(id)
        if not html:
            return {"parse": 0, "playUrl": ""}
        
        # 从 player_aaaa 提取播放直链
        player_match = re.search(r'var\s+player_aaaa\s*=\s*({[^;]+})', html)
        if player_match:
            try:
                data = json.loads(player_match.group(1))
                if data.get('url'):
                    return {"parse": 0, "playUrl": data['url']}
            except:
                pass
        
        # 备用: 从video标签提取
        video_match = re.search(r'<video[^>]*src="([^"]+)"', html)
        if video_match:
            return {"parse": 0, "Url": self.fix_url(video_match.group(1))}
        
        return {"parse": 0, "Url": ""}