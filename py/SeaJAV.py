# coding: utf-8
import re
import json
from urllib.parse import urljoin, quote

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://seajav.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "1", "type_name": "国产自拍"},
            {"type_id": "2", "type_name": "日本AV"},
            {"type_id": "3", "type_name": "91porn"},
            {"type_id": "4", "type_name": "国产AV"},
            {"type_id": "6", "type_name": "高清AV"},
            {"type_id": "7", "type_name": "无码AV"},
            {"type_id": "8", "type_name": "中文字幕AV"},
            {"type_id": "9", "type_name": "无码流出"},
            {"type_id": "10", "type_name": "三上悠亚AV"},
            {"type_id": "11", "type_name": "FC2PPV"},
            {"type_id": "13", "type_name": "自拍流出"},
            {"type_id": "14", "type_name": "福利姬"},
            {"type_id": "20", "type_name": "91视频"},
            {"type_id": "21", "type_name": "麻豆视频"},
            {"type_id": "22", "type_name": "91制片厂"},
            {"type_id": "23", "type_name": "天美传媒"},
            {"type_id": "24", "type_name": "蜜桃传媒"},
            {"type_id": "26", "type_name": "星空传媒"},
            {"type_id": "27", "type_name": "精东影业"},
            {"type_id": "37", "type_name": "糖心Vlog"},
            {"type_id": "38", "type_name": "91探花"},
            {"type_id": "39", "type_name": "杏吧视频"},
            {"type_id": "40", "type_name": "素人AV"},
            {"type_id": "41", "type_name": "AI明星"},
            {"type_id": "99", "type_name": "最新影片"},
        ]
        self.filters = {}

    def getName(self):
        return "seajav"

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            html = self._fetch_html(self.host + "/")
            videos = self._parse_video_list(html)
            return {"list": videos[:20]}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        if pg is None or pg == "":
            pg = 1
        pg = int(pg)
        if pg == 1:
            url = f"{self.host}/categories/{tid}.html"
        else:
            url = f"{self.host}/categories/{tid}-{pg}.html"
        result = self._fetch_video_list(url)
        result["page"] = pg
        result["pagecount"] = 99
        result["limit"] = 20
        return result

    def _fetch_video_list(self, url):
        try:
            html = self._fetch_html(url)
            videos = self._parse_video_list(html)
            return {"list": videos, "total": len(videos)}
        except Exception as e:
            self.log({"action": "fetch_list_fail", "url": url, "error": str(e)})
            return {"list": []}

    def _fetch_html(self, url):
        resp = self.fetch(url, headers=self.headers)
        return resp.text if resp else ""

    def _parse_video_list(self, html):
        videos = []
        patterns = [
            # 标准卡片（分类页/首页）
            r'<div class="thumbnail group">.*?<a href="(/video/(\d+)-1-1\.html)".*?<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"[^>]*>.*?<div class="my-2[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>',
            # 搜索页备用
            r'<a href="(/video/(\d+)-1-1\.html)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"[^>]*>.*?<div[^>]*>.*?<a[^>]*>(.*?)</a>',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            if matches:
                for match in matches:
                    href = match[0]
                    vid = match[1]
                    pic = match[2]
                    alt = match[3]
                    title = match[4]
                    if not vid:
                        continue
                    title = re.sub(r'&nbsp;', ' ', title).strip()
                    if not title and alt:
                        title = alt.strip()
                    if not title:
                        continue
                    # 补全封面图 URL（相对路径转绝对路径）
                    if pic and not pic.startswith("http"):
                        pic = urljoin(self.host, pic)
                    videos.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": "",
                        "vod_url": urljoin(self.host, href)
                    })
                if videos:
                    break
        return videos

    def detailContent(self, ids):
        if not ids or not ids[0]:
            return {"list": []}
        vid = str(ids[0]).strip()
        vid_clean = re.sub(r'[^0-9]', '', vid)
        if not vid_clean:
            return {"list": []}
        url = f"{self.host}/video/{vid_clean}-1-1.html"
        try:
            html = self._fetch_html(url)
            return self._parse_detail(html, vid_clean)
        except Exception as e:
            self.log({"action": "detail_fail", "url": url, "error": str(e)})
            return {"list": []}

    def _parse_detail(self, html, vid):
        vod = {
            "vod_id": vid,
            "vod_name": "",
            "vod_pic": "",
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "",
            "vod_play_url": ""
        }
        # 标题
        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        if title_match:
            vod["vod_name"] = re.sub(r'&nbsp;', ' ', title_match.group(1).strip())

        # 封面图 - 只匹配图片扩展名
        pic_match = re.search(r'<img[^>]*src="([^"]+\.(jpg|jpeg|png|gif|webp)[^"]*)"[^>]*alt="[^"]*"[^>]*>', html, re.IGNORECASE)
        if not pic_match:
            pic_match = re.search(r'<img[^>]*src="([^"]+)"[^>]*>', html)
        if pic_match:
            pic_url = pic_match.group(1)
            if not pic_url.endswith('.js'):
                vod["vod_pic"] = pic_url

        # 提取播放地址 - 多种方法
        play_url = None

        # 方法1: 直接搜索 "url":"https://...m3u8"
        m3u8_match = re.search(r'"url"\s*:\s*"(https?://[^"]+\.m3u8[^"]*)"', html)
        if m3u8_match:
            play_url = m3u8_match.group(1)

        # 方法2: 栈匹配提取 player_aaaa 完整 JSON
        if not play_url:
            start = html.find('player_aaaa=')
            if start != -1:
                json_start = html.find('{', start)
                if json_start != -1:
                    brace_count = 0
                    json_end = json_start
                    for i in range(json_start, len(html)):
                        ch = html[i]
                        if ch == '{':
                            brace_count += 1
                        elif ch == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break
                    if json_end > json_start:
                        json_str = html[json_start:json_end]
                        try:
                            data = json.loads(json_str)
                            if 'url' in data:
                                play_url = data['url']
                        except:
                            url_in_obj = re.search(r'"url"\s*:\s*"([^"]+)"', json_str)
                            if url_in_obj:
                                play_url = url_in_obj.group(1)

        # 方法3: iframe src
        if not play_url:
            iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"', html)
            if iframe_match:
                play_url = iframe_match.group(1)

        if play_url:
            vod["vod_play_url"] = f"播放${play_url}"
            vod["vod_play_from"] = "直链"
        else:
            vod["vod_play_url"] = f"播放$"
            vod["vod_play_from"] = ""

        # 描述
        desc_match = re.search(r'<div[^>]*class="[^"]*text-nord4[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        if desc_match:
            vod["vod_content"] = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()

        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        if not key or not key.strip():
            return {"list": [], "page": 1}
        keyword = key.strip()
        videos = []
        # 方法1: POST 搜索
        try:
            post_url = f"{self.host}/search.html"
            post_data = {"wd": keyword}
            resp = self.post(post_url, data=post_data, headers=self.headers)
            if resp:
                videos = self._parse_video_list(resp.text)
                if videos:
                    return {"list": videos, "page": int(pg or 1)}
        except Exception as e:
            self.log({"action": "search_post_fail", "key": keyword, "error": str(e)})

        # 方法2: GET 搜索
        if not videos:
            try:
                search_url = f"{self.host}/search/{quote(keyword)}/"
                html = self._fetch_html(search_url)
                videos = self._parse_video_list(html)
            except Exception as e:
                self.log({"action": "search_get_fail", "key": keyword, "error": str(e)})

        return {"list": videos, "page": int(pg or 1)}

    def playerContent(self, flag, id, vipFlags):
        if id:
            if id.startswith("http://") or id.startswith("https://"):
                if id.endswith((".m3u8", ".mp4", ".ts")):
                    return {"parse": 0, "url": id, "header": self.headers}
            if not id.startswith("http"):
                if id.startswith("/"):
                    id = urljoin(self.host, id)
                else:
                    id = self.host + "/" + id
                return {"parse": 0, "url": id, "header": self.headers}
        return {"parse": 1, "url": "", "header": self.headers}

    def localProxy(self, param):
        return [200, "application/octet-stream", "", {"Cache-Control": "no-store"}]

    def isVideoFormat(self, url):
        return url and url.endswith((".m3u8", ".mp4", ".mkv", ".avi", ".ts"))