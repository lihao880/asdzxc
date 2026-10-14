# coding: utf-8
# 站点: 汁乎AV片库 (https://new.zhtv8.xyz/)
# 类型: 成人影视聚合站
# 特性: 分类列表 / DPlayer 播放器 / 多线路
# 最后验证: 2026-09-06

import json
import re
import base64
from urllib.parse import urljoin, quote, unquote

from base.spider import Spider as BaseSpider

# coding: utf-8
# 站点: 汁乎AV片库 (https://new.zhtv8.xyz/)
# 类型: 成人影视聚合站
# 特性: 分类列表 / DPlayer 播放器 / 多线路
# 最后验证: 2026-09-06

import json
import re
from urllib.parse import urljoin, quote, unquote

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://new.zhtv8.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "jav", "type_name": "日本"},
            {"type_id": "asian", "type_name": "亚洲人"},
            {"type_id": "国产", "type_name": "国产", "is_search": True},
            {"type_id": "Cosplay", "type_name": "Cosplay"},
            {"type_id": "hentai", "type_name": "色情日漫"},
            {"type_id": "creampie", "type_name": "内射中出"},
            {"type_id": "teen", "type_name": "年轻"},
            {"type_id": "russian", "type_name": "俄罗斯美女"},
            {"type_id": "blowjob", "type_name": "口交"},
            {"type_id": "school-uniform", "type_name": "大学生"},
            {"type_id": "lesbian", "type_name": "女同"},
            {"type_id": "big-natural-tits", "type_name": "巨乳"},
            {"type_id": "petite", "type_name": "娇小"},
            {"type_id": "cartoon", "type_name": "卡通"},
            {"type_id": "foot-fetish", "type_name": "足控恋足"},
            {"type_id": "college", "type_name": "校园"},
            {"type_id": "cosplay", "type_name": "角色扮演"},
            {"type_id": "female-masturbation", "type_name": "女性自慰"},
            {"type_id": "titty-fucking", "type_name": "乳交"},
            {"type_id": "18-year-old", "type_name": "青少年"},
        ]
        self.filters = {}

    def getName(self):
        return "汁乎"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self.categoryContent("jav", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        if tid == "国产":
            return self.searchContent(tid, False, page)
        url = f"{self.host}/categories/{tid}/{page}"
        try:
            r = self.fetch(url, headers=self.headers, timeout=15)
            if not r or r.status_code != 200:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = r.text
            items = self._parse_list(html)
            pagecount = self._parse_pagecount(html)
            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception as e:
            self.log({"category": "error", "tid": tid, "pg": pg, "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def _parse_list(self, html):
        items = []
        # 方法1: 从 window.initials 中提取视频列表
        initials_m = re.search(r'window\.initials\s*=\s*({.*?});', html, re.S)
        if initials_m:
            try:
                raw_json = initials_m.group(1)
                data = json.loads(raw_json)
                
                # 正确的数据路径: pagesCategoryComponent.trendingVideoListProps.videoThumbProps
                video_thumbs = data.get("pagesCategoryComponent", {}).get("trendingVideoListProps", {}).get("videoThumbProps", [])
                
                # 如果上面的路径没有，尝试其他路径
                if not video_thumbs:
                    video_thumbs = data.get("xhlMlSource", {}).get("payload", {}).get("pageVideos", [])
                
                # 如果还是没有，尝试直接取 pageVideos
                if not video_thumbs:
                    video_thumbs = data.get("pageVideos", [])
                
                for v in video_thumbs:
                    if isinstance(v, dict):
                        # 从 videoThumbProps 中直接取数据
                        vid = v.get("pageURL", "") or v.get("url", "")
                        if not vid:
                            continue
                        
                        title = v.get("title", "") or v.get("name", "")
                        pic = v.get("thumbURL", "") or v.get("imageURL", "") or v.get("thumb", "")
                        
                        # 补全图片URL
                        if pic and not pic.startswith("http"):
                            pic = "https:" + pic if pic.startswith("//") else self.host + pic
                        
                        # 时长
                        duration = v.get("duration", 0)
                        if duration:
                            minutes = duration // 60
                            seconds = duration % 60
                            remark = f"{minutes:02d}:{seconds:02d}"
                        else:
                            remark = ""
                        
                        if vid and title:
                            items.append({
                                "vod_id": vid,
                                "vod_name": title,
                                "vod_pic": pic,
                                "vod_remarks": remark
                            })
                
                if items:
                    return items
            except Exception as e:
                self.log({"parse_list": "initials_parse_error", "error": str(e)})

        # 方法2: 从 HTML DOM 中提取（兜底）
        block_pattern = r'<div[^>]*class="[^"]*thumb-block[^"]*"[^>]*id="[^"]*"[^>]*>(.*?)</div>\s*</a>\s*</div>'
        blocks = re.findall(block_pattern, html, re.S)
        if not blocks:
            link_pattern = r'<a[^>]*href="(/videos/[^"]+)"[^>]*>.*?<div[^>]*class="[^"]*text-ellipsis[^"]*"[^>]*>(.*?)</span>'
            for m in re.finditer(link_pattern, html, re.S):
                link = m.group(1).strip()
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                pic = ""
                img_m = re.search(r'<img[^>]*src="([^"]+)"', html[m.start():m.end()+200])
                if img_m:
                    pic = img_m.group(1).strip()
                if link and title:
                    items.append({
                        "vod_id": link,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": ""
                    })
            return items

        for block in blocks:
            link_m = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', block)
            if not link_m:
                continue
            link = link_m.group(1).strip()
            if not link.startswith("http"):
                link = urljoin(self.host, link)

            title = ""
            title_m = re.search(r'<span[^>]*class="[^"]*text-ellipsis[^"]*"[^>]*>(.*?)</span>', block, re.S)
            if title_m:
                title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()

            pic = ""
            pic_m = re.search(r'<img[^>]*data-(?:original|src)="([^"]+)"[^>]*>', block)
            if not pic_m:
                pic_m = re.search(r'<img[^>]*src="([^"]+)"[^>]*>', block)
            if pic_m:
                pic = pic_m.group(1).strip()
                if pic == "" or "loading" in pic.lower():
                    pic_m2 = re.search(r'<img[^>]*data-src="([^"]+)"[^>]*>', block)
                    if pic_m2:
                        pic = pic_m2.group(1).strip()

            remark = ""
            dur_m = re.search(r'<small[^>]*class="[^"]*dur[^"]*"[^>]*>(.*?)</small>', block, re.S)
            if dur_m:
                remark = dur_m.group(1).strip()

            if link and title:
                items.append({
                    "vod_id": link,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
        return items
    def _parse_pagecount(self, html):
        max_page = 1
        patterns = [
            r'<a[^>]*href="[^"]*/categories/[^/]+/(\d+)"[^>]*>(\d+)</a>',
            r'page-list.*?<a[^>]*href="[^"]*/categories/[^/]+/(\d+)"[^>]*>(\d+)</a>',
            r'/(\d+)"[^>]*>(\d+)</a>\s*</li>\s*<li[^>]*class="[^"]*page-button-separator',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html)
            if matches:
                for m in matches:
                    try:
                        p = int(m[1] if len(m) > 1 else m[0])
                        if p > max_page:
                            max_page = p
                    except:
                        pass
        if max_page > 1:
            return max_page
        total_m = re.search(r'共\s*(\d+)\s*页', html)
        if total_m:
            try:
                return int(total_m.group(1))
            except:
                pass
        page_links = re.findall(r'/categories/[^/]+/(\d+)"', html)
        if page_links:
            try:
                return max(int(p) for p in page_links if p.isdigit())
            except:
                pass
        return 1

    def detailContent(self, ids):
        if isinstance(ids, list):
            ids = ids[0] if ids else ""
        if not ids:
            return {"list": []}
        if not ids.startswith("http"):
            ids = urljoin(self.host, ids)

        try:
            r = self.fetch(ids, headers=self.headers, timeout=15)
            if not r or r.status_code != 200:
                return {"list": []}
            html = r.text

            if '加载失败' in html or 'id="divmsg"' in html:
                return {"list": []}

            title = ""
            title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            if title_m:
                title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
            if not title:
                title_m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
                if title_m:
                    title = title_m.group(1).strip()

            pic = ""
            pic_m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
            if pic_m:
                pic = pic_m.group(1).strip()
            if not pic:
                pic_m = re.search(r'"thumbUrl":"([^"]+)"', html)
                if pic_m:
                    pic = pic_m.group(1).strip()

            play_urls = self._extract_play_urls(html)

            froms = []
            urls = []
            if play_urls:
                for label, url in play_urls:
                    if url and url.startswith("http"):
                        # 使用 urlquote 编码，避免 base64 在沙盒中不可用
                        encoded = quote(url, safe="")
                        froms.append(label or "播放")
                        urls.append(f"第1集${encoded}")
            else:
                froms = ["播放"]
                urls = [f"播放${ids}"]

            if not froms:
                return {"list": []}

            vod = {
                "vod_id": ids,
                "vod_name": title or "未知标题",
                "vod_pic": pic or "",
                "vod_remarks": "",
                "vod_content": "",
                "vod_play_from": "$$$".join(froms),
                "vod_play_url": "$$$".join(urls)
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"detail": "error", "ids": ids, "error": str(e)})
            return {"list": []}

    def _extract_play_urls(self, html):
        urls = []
        seen = set()

        initials_m = re.search(r'window\.initials\s*=\s*({.*?});', html, re.S)
        if initials_m:
            try:
                data = json.loads(initials_m.group(1))

                sources = data.get("downloadDropdownComponent", {}).get("sources", {})
                mp4 = sources.get("mp4", {})
                if mp4:
                    for quality in ["1080p", "720p", "480p", "240p", "144p"]:
                        url = mp4.get(quality, "")
                        if url and url.startswith("http") and url not in seen:
                            seen.add(url)
                            urls.append((quality, url))

                xplayer = data.get("xplayerSettings", {})
                sources2 = xplayer.get("sources", {})
                standard = sources2.get("standard", {})
                h264 = standard.get("h264", [])
                for item in h264:
                    if isinstance(item, dict):
                        quality = item.get("label", "未知")
                        url = item.get("url", "")
                        if url and url.startswith("http") and url not in seen and len(url) < 200:
                            seen.add(url)
                            urls.append((quality, url))

                vs = data.get("videoSources", {})
                for k, v in vs.items():
                    if isinstance(v, str) and v.startswith("http") and v not in seen:
                        seen.add(v)
                        urls.append((k, v))

            except Exception as e:
                self.log({"extract": "initials_parse_error", "error": str(e)})

        patterns = [
            r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)',
            r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)',
            r'(https?://video\d+\.xhcdn\.com/[^\s"\'<>]+)',
        ]
        for p in patterns:
            for m in re.finditer(p, html):
                url = m.group(1)
                if url and url.startswith("http") and url not in seen:
                    seen.add(url)
                    label = "m3u8" if ".m3u8" in url else "mp4"
                    urls.append((label, url))

        quality_order = {"1080p": 0, "720p": 1, "480p": 2, "240p": 3, "144p": 4}
        urls.sort(key=lambda x: quality_order.get(x[0], 99) if x[0] in quality_order else 99)

        result = []
        for label, url in urls:
            if url in seen:
                if ".m3u8" in url.lower() or ".mp4" in url.lower() or "video" in url.lower():
                    result.append((label, url))
                elif url.startswith("http"):
                    result.append((label, url))
                if len(result) >= 5:
                    break
        return result

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        page = pg or "1"
        url = f"{self.host}/search/{quote(key)}"
        if page != "1":
            url = f"{url}/{page}"
        try:
            r = self.fetch(url, headers=self.headers, timeout=15)
            if not r or r.status_code != 200:
                return {"list": [], "page": 1}
            html = r.text
            items = self._parse_list(html)
            pagecount = self._parse_pagecount(html)
            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception as e:
            self.log({"search": "error", "key": key, "error": str(e)})
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        # 尝试 URL 解码（使用 quote 编码的播放地址）
        try:
            decoded = unquote(id)
            if decoded.startswith("http") and (".mp4" in decoded.lower() or ".m3u8" in decoded.lower()):
                return {"parse": 0, "url": decoded, "header": self.headers}
        except Exception:
            pass

        if id.startswith("http") and (".mp4" in id.lower() or ".m3u8" in id.lower()):
            return {"parse": 0, "url": id, "header": self.headers}

        if id.startswith("http") and "/videos/" in id:
            try:
                r = self.fetch(id, headers=self.headers, timeout=15)
                if r and r.status_code == 200:
                    html = r.text
                    if '加载失败' in html or 'id="divmsg"' in html:
                        return {"parse": 1, "url": id, "header": self.headers}
                    play_urls = self._extract_play_urls(html)
                    if play_urls:
                        if flag:
                            for label, url in play_urls:
                                if flag.lower() in label.lower():
                                    return {"parse": 0, "url": url, "header": self.headers}
                        return {"parse": 0, "url": play_urls[0][1], "header": self.headers}
            except Exception as e:
                self.log({"player": "fetch_error", "id": id, "error": str(e)})
            return {"parse": 1, "url": id, "header": self.headers}

        if id.startswith("http"):
            return {"parse": 1, "url": id, "header": self.headers}
        return {"parse": 0, "url": "", "header": {}}

    def recommendContent(self, ids, pg):
        return self.homeVideoContent()

    def destroy(self):
        pass
