# coding: utf-8
# 站点：咪咪爱视频
# 域名：https://www.mimiaiav.cc
# 类型：MacCMS 影视站 (成人)
# 路径前缀：/aa

import json
import re
import posixpath
from urllib.parse import quote, urljoin, unquote, urlparse

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.mimiaiav.cc"
        self.base_path = "/aa"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + self.base_path + "/"
        }
        self.classes = [
            {"type_id": "2", "type_name": "精品推荐"},
            {"type_id": "3", "type_name": "国产精品"},
            {"type_id": "4", "type_name": "主播秀色"},
            {"type_id": "5", "type_name": "自拍偷拍"},
            {"type_id": "6", "type_name": "网曝系列"},
            {"type_id": "7", "type_name": "国产丝袜"},
            {"type_id": "8", "type_name": "国产乱伦"},
            {"type_id": "9", "type_name": "国产人妻"},
            {"type_id": "11", "type_name": "国产视频"},
            {"type_id": "12", "type_name": "国产传媒"},
            {"type_id": "13", "type_name": "国产主播"},
            {"type_id": "14", "type_name": "抖阴视频"},
            {"type_id": "15", "type_name": "网曝黑料"},
            {"type_id": "16", "type_name": "极品媚黑"},
            {"type_id": "17", "type_name": "网红头条"},
            {"type_id": "18", "type_name": "韩国主播"},
            {"type_id": "20", "type_name": "国产制作"},
            {"type_id": "21", "type_name": "乱伦大全"},
            {"type_id": "22", "type_name": "主播网红"},
            {"type_id": "23", "type_name": "黑料网曝"},
            {"type_id": "24", "type_name": "淫乱合集"},
            {"type_id": "25", "type_name": "会所技师"},
            {"type_id": "26", "type_name": "偷拍自拍"},
            {"type_id": "27", "type_name": "淫妻绿帽"},
            {"type_id": "29", "type_name": "精品推荐2"},
            {"type_id": "30", "type_name": "国产色情"},
            {"type_id": "31", "type_name": "主播直播"},
            {"type_id": "32", "type_name": "自拍偷拍2"},
            {"type_id": "33", "type_name": "剧情介绍"},
            {"type_id": "34", "type_name": "多人多P"},
            {"type_id": "35", "type_name": "网红流出"},
            {"type_id": "36", "type_name": "黑料网曝2"},
            {"type_id": "38", "type_name": "国产自拍"},
            {"type_id": "39", "type_name": "国产裸聊"},
            {"type_id": "40", "type_name": "偷拍自拍3"},
            {"type_id": "41", "type_name": "制服丝袜"},
            {"type_id": "42", "type_name": "群交淫乱"},
            {"type_id": "43", "type_name": "巨乳美乳"},
            {"type_id": "44", "type_name": "少女萝莉"},
            {"type_id": "45", "type_name": "女同性恋"},
            {"type_id": "47", "type_name": "国产自拍2"},
            {"type_id": "48", "type_name": "抖音视频"},
            {"type_id": "49", "type_name": "网红头条2"},
            {"type_id": "50", "type_name": "网爆黑料"},
            {"type_id": "51", "type_name": "美女主播"},
            {"type_id": "52", "type_name": "麻豆传媒"},
            {"type_id": "53", "type_name": "SM调教"},
            {"type_id": "54", "type_name": "韩国主播2"},
            {"type_id": "56", "type_name": "中文字幕"},
            {"type_id": "57", "type_name": "日韩有码"},
            {"type_id": "58", "type_name": "日韩无码"},
            {"type_id": "59", "type_name": "欧美无码"},
            {"type_id": "60", "type_name": "制服诱惑"},
            {"type_id": "61", "type_name": "萝莉少女"},
            {"type_id": "62", "type_name": "女优明星"},
            {"type_id": "63", "type_name": "AV解说"},
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}

    def getName(self):
        return "咪咪爱视频"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            url = self.host + self.base_path + "/"
            res = self.fetch(url, headers=self.headers, timeout=15)
            html = res.text if hasattr(res, "text") else ""
            if not html:
                return {"list": []}
            return self._parse_video_list(html, is_home=True)
        except Exception as e:
            self.log({"action": "homeVideoContent", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = str(pg or "1")
            tid = str(tid)

            url = f"{self.host}{self.base_path}/index.php/vod/type/id/{tid}.html"
            if page != "1":
                url = url.replace('.html', f'/page/{page}.html')

            res = self.fetch(url, headers=self.headers, timeout=15)
            html = res.text if hasattr(res, "text") else ""
            if not html:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

            result = self._parse_video_list(html, is_home=False, page=page)

            pagecount = 1
            page_matches = re.findall(r'<a[^>]*class="[^"]*page-[^"]*"[^>]*>(\d+)</a>', html)
            if page_matches:
                pagecount = max([int(p) for p in page_matches if p.isdigit()] + [1])
            page_info = re.search(r'共\s*(\d+)\s*页', html) or re.search(r'第\s*\d+\s*/\s*(\d+)\s*页', html)
            if page_info:
                pagecount = int(page_info.group(1))
            last_match = re.search(r'<a[^>]*href="[^"]*/page/(\d+)\.html[^"]*"[^>]*>尾页</a>', html)
            if last_match:
                pagecount = int(last_match.group(1))

            result["pagecount"] = pagecount if pagecount > 1 else 99
            result["total"] = pagecount * 20

            return result
        except Exception as e:
            self.log({"action": "categoryContent", "tid": tid, "pg": pg, "error": str(e)})
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            if isinstance(ids, list) and len(ids) > 0:
                vid = str(ids[0])
            else:
                vid = str(ids)

            if "/play/id/" in vid:
                match = re.search(r'/id/(\d+)', vid)
                if match:
                    vid = match.group(1)

            url = f"{self.host}{self.base_path}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"

            vod = {
                "vod_id": vid,
                "vod_name": f"视频_{vid}",
                "vod_pic": "",
                "vod_remarks": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": ""
            }

            try:
                res = self.fetch(url, headers=self.headers, timeout=15)
                html = res.text if hasattr(res, "text") else ""

                if html:
                    title_match = re.search(r'<title>([^<]+)</title>', html)
                    if title_match:
                        title = title_match.group(1).replace("在线播放", "").strip()
                        title = title.replace("-咪咪爱视频-最新地址入口资源丰富最新热门", "").strip()
                        if title:
                            vod["vod_name"] = title

                    m3u8_url, source = self._extract_m3u8(html)
                    if m3u8_url:
                        # 直接返回 m3u8 原始地址，不经过代理（解决超时）
                        vod["vod_play_url"] = f"播放${m3u8_url}"
                    else:
                        # 没有 m3u8，传播放页让 playerContent 解析
                        vod["vod_play_url"] = f"播放$play@@{quote(url)}"

                    pic_match = re.search(r'<img[^>]*class="[^"]*vod_img[^"]*"[^>]*src="([^"]+)"', html, re.DOTALL)
                    if not pic_match:
                        pic_match = re.search(r'<img[^>]*data-original="([^"]+)"', html, re.DOTALL)
                    if pic_match:
                        pic = pic_match.group(1)
                        vod["vod_pic"] = pic if pic.startswith("http") else self.host + pic

                    desc_match = re.search(r'<span[^>]*class="[^"]*vod_content[^"]*"[^>]*>([^<]*)</span>', html)
                    if desc_match:
                        vod["vod_content"] = desc_match.group(1).strip()

            except Exception as e:
                self.log({"action": "detailContent_fetch_error", "error": str(e)})
                vod["vod_play_url"] = f"播放$play@@{quote(url)}"

            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent_error", "ids": ids, "error": str(e)})
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            if not key:
                return {"list": [], "page": 1}

            page = str(pg or "1")
            url = f"{self.host}{self.base_path}/index.php/vod/search.html?wd={quote(key)}"
            if page != "1":
                url += f"&page={page}"

            res = self.fetch(url, headers=self.headers, timeout=15)
            html = res.text if hasattr(res, "text") else ""
            if not html:
                return {"list": [], "page": int(page)}

            return self._parse_video_list(html, is_home=False, page=page, is_search=True)
        except Exception as e:
            self.log({"action": "searchContent", "key": key, "error": str(e)})
            return {"list": [], "page": int(pg or 1)}

    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "")

        # 处理 play@@ 前缀（播放页 URL）
        if raw.startswith("play@@"):
            url = unquote(raw.replace("play@@", "", 1))
            url = url.replace("\\/", "/")
            try:
                res = self.fetch(url, headers=self.headers, timeout=10)
                html = res.text if hasattr(res, "text") else ""
                if html:
                    m3u8_url, source = self._extract_m3u8(html)
                    if m3u8_url:
                        return {"parse": 0, "url": m3u8_url, "header": self.headers}
            except:
                pass
            return {"parse": 1, "url": url, "header": self.headers}

        # 直接 m3u8/mp4 链接 - 直接返回，不经过代理
        if raw.endswith((".m3u8", ".mp4")) or ".m3u8" in raw:
            url = raw.replace("\\/", "/")
            return {"parse": 0, "url": url, "header": self.headers}

        # HTTP URL 尝试解析
        if raw.startswith("http"):
            url = raw.replace("\\/", "/")
            try:
                res = self.fetch(url, headers=self.headers, timeout=10)
                html = res.text if hasattr(res, "text") else ""
                if html:
                    m3u8_url, source = self._extract_m3u8(html)
                    if m3u8_url:
                        return {"parse": 0, "url": m3u8_url, "header": self.headers}
            except:
                pass
            return {"parse": 1, "url": url, "header": self.headers}

        return {"parse": 1, "url": raw, "header": self.headers}

    def _extract_m3u8(self, html):
        if not html:
            return None, None

        # 模式1: player_aaaa 对象
        player_match = re.search(r'var\s+player_aaaa\s*=\s*({[^;]+});', html, re.DOTALL)
        if player_match:
            try:
                player_data = json.loads(player_match.group(1))
                url = player_data.get("url")
                if url and (url.endswith((".m3u8", ".mp4")) or ".m3u8" in url):
                    url = url.replace("\\/", "/")
                    return url, "player_aaaa"
            except:
                pass

        # 模式2: 直接匹配 .m3u8 URL
        m3u8_matches = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html)
        if m3u8_matches:
            url = m3u8_matches[0].replace("\\/", "/")
            return url, "direct"

        # 模式3: 松散匹配 "url":"xxx.m3u8"
        loose_match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
        if loose_match:
            url = loose_match.group(1).replace("\\/", "/")
            return url, "loose"

        return None, None

    def _parse_video_list(self, html, is_home=False, page="1", is_search=False):
        result = {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

        list_match = re.search(r'<ul class="video-list">(.*?)</ul>', html, re.DOTALL)
        if not list_match:
            return result

        list_html = list_match.group(1)

        items = re.findall(
            r'<li>.*?<a[^>]*data-original-href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h3[^>]*>.*?<text>(.*?)</text>',
            list_html,
            re.DOTALL
        )

        if not items:
            items2 = re.findall(
                r'<li>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h3[^>]*>.*?<text>(.*?)</text>',
                list_html,
                re.DOTALL
            )
            for href, pic, title in items2:
                if "/aa/index.php/vod/play/" in href or "/vod/play/" in href:
                    items.append((href, pic, title))

        for href, pic, title in items:
            title = title.strip()
            if not href or not title:
                continue

            vid_match = re.search(r'/id/(\d+)', href)
            vid = vid_match.group(1) if vid_match else href

            detail_url = href if href.startswith("http") else self.host + href

            result["list"].append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic if pic.startswith("http") else self.host + pic,
                "vod_remarks": "",
                "vod_url": detail_url
            })

            if is_home and len(result["list"]) >= 12:
                break

        if len(result["list"]) >= 20:
            result["pagecount"] = 99
            result["total"] = 999
        else:
            result["pagecount"] = 1
            result["total"] = len(result["list"])

        return result

    def isVideoFormat(self, url):
        return re.search(r'\.(m3u8|mp4)(\?|$)', url) is not None

    def destroy(self):
        pass