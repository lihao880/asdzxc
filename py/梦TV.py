# coding=utf-8
# 梦TV Spider - 优化直链提取与代理版本
# 站点: https://mengtv829.biz

import re
import json
import time
import urllib.parse
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://mengtv829.biz"
        self.backup_host = "https://www.mengtv22.click"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }
        self._cookies = {}

        # 分类硬编码 (零网络依赖)
        self.classes = [
            {"type_id": "1", "type_name": "视频一区"},
            {"type_id": "2", "type_name": "视频二区"},
            {"type_id": "3", "type_name": "视频三区"}
        ]

        # 筛选器 (子分类)
        self.filters = {
            "1": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "抖音视频", "v": "6"},
                    {"n": "韩国主播", "v": "7"},
                    {"n": "网红头条", "v": "8"},
                    {"n": "网爆黑料", "v": "9"},
                    {"n": "欧美无码", "v": "10"},
                    {"n": "女优明星", "v": "11"},
                    {"n": "SM调教", "v": "12"},
                    {"n": "AV解说", "v": "20"}
                ]}
            ],
            "2": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "无码专区", "v": "13"},
                    {"n": "麻豆传媒", "v": "14"},
                    {"n": "制服诱惑", "v": "15"},
                    {"n": "三级伦理", "v": "16"},
                    {"n": "AI换脸", "v": "21"},
                    {"n": "中文字幕", "v": "22"},
                    {"n": "卡通动漫", "v": "23"},
                    {"n": "欧美系列", "v": "24"}
                ]}
            ],
            "3": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "美女主播", "v": "25"},
                    {"n": "国产自拍", "v": "26"},
                    {"n": "熟女人妻", "v": "27"},
                    {"n": "萝莉少女", "v": "28"},
                    {"n": "女同性爱", "v": "29"},
                    {"n": "多人群交", "v": "30"},
                    {"n": "美乳巨乳", "v": "31"},
                    {"n": "强奸乱伦", "v": "32"}
                ]}
            ]
        }

    def init(self, cfg=None):
        """初始化 - 访问首页获取 Cookie"""
        try:
            resp = self.fetch(self.host, headers=self.headers, timeout=10)
            if resp and hasattr(resp, 'cookies') and resp.cookies:
                if isinstance(resp.cookies, dict):
                    self._cookies = resp.cookies
                elif hasattr(resp.cookies, 'get_dict'):
                    self._cookies = resp.cookies.get_dict()
                elif hasattr(resp.cookies, 'items'):
                    self._cookies = {k: v for k, v in resp.cookies.items()}
                if self._cookies:
                    cookie_str = "; ".join([f"{k}={v}" for k, v in self._cookies.items()])
                    self.headers["Cookie"] = cookie_str
        except Exception as e:
            self.log({"action": "init_fail", "error": str(e)})

    def getDependence(self):
        return []

    def getName(self):
        return "梦TV"

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def _fetch_html(self, url, retry=2):
        """获取页面 HTML - 支持重试与 Cookie 维持"""
        if hasattr(self, '_cookies') and self._cookies:
            cookie_str = "; ".join([f"{k}={v}" for k, v in self._cookies.items()])
            self.headers["Cookie"] = cookie_str

        for attempt in range(retry + 1):
            try:
                resp = self.fetch(url, headers=self.headers, timeout=15)
                if resp is None:
                    continue

                if hasattr(resp, 'cookies') and resp.cookies:
                    if isinstance(resp.cookies, dict):
                        self._cookies.update(resp.cookies)
                    elif hasattr(resp.cookies, 'get_dict'):
                        self._cookies.update(resp.cookies.get_dict())
                    elif hasattr(resp.cookies, 'items'):
                        self._cookies.update({k: v for k, v in resp.cookies.items()})

                if hasattr(resp, "text") and resp.text:
                    return resp.text
                if hasattr(resp, "content") and resp.content:
                    try:
                        return resp.content.decode('utf-8', errors='ignore')
                    except Exception:
                        pass
                return ""
            except Exception as e:
                if attempt < retry:
                    time.sleep(1)
                    continue
                self.log({"action": "fetch_fail", "url": url, "error": str(e)})
                return ""
        return ""

    def fix_url(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return urllib.parse.urljoin(self.host, url)

    def extract_id_from_url(self, url):
        match = re.search(r'/detail/id/(\d+)\.html', url)
        if match:
            return match.group(1)
        match = re.search(r'/play/id/(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'[?&]id=(\d+)', url)
        if match:
            return match.group(1)
        return url

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/")
        items = self._parse_list(html)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        actual_tid = tid
        if extend:
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            if isinstance(extend, dict) and extend.get("sub"):
                actual_tid = extend["sub"]
        url = f"{self.host}/index.php/vod/type/id/{actual_tid}/page/{page}.html"
        html = self._fetch_html(url)
        items = self._parse_list(html)
        pagecount = self._get_pagecount(html)
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        if isinstance(ids, int):
            vid = str(ids)
        elif isinstance(ids, list):
            vid = str(ids[0]) if ids else ""
        else:
            vid = str(ids)
        if not vid:
            return {"list": []}

        if "detail/id/" in vid or "play/id/" in vid:
            vid = self.extract_id_from_url(vid)

        url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        html = self._fetch_html(url)
        return self._parse_detail(html, vid)

    def searchContent(self, key, quick, pg="1"):
        if not key or key.strip() == "":
            return {"list": [], "page": 1}
        page = pg or "1"
        encoded_key = urllib.parse.quote(key)
        url = f"{self.host}/index.php/vod/search/wd/{encoded_key}/page/{page}.html"
        html = self._fetch_html(url)
        items = self._parse_list(html)
        return {"list": items, "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        """解析播放地址，精准提取 m3u8 直链"""
        if id.startswith("http") and (".m3u8" in id or ".mp4" in id):
            if ".m3u8" in id:
                return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": self.headers}
            return {"parse": 0, "url": id, "header": self.headers}

        if id.startswith("http"):
            play_url = id
        elif id.startswith("/"):
            play_url = self.host + id
        else:
            vid = self.extract_id_from_url(id)
            play_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"

        headers = self.headers.copy()
        headers["Referer"] = play_url
        html = self._fetch_html(play_url)

        if not html and self.backup_host:
            play_url = play_url.replace(self.host, self.backup_host)
            html = self._fetch_html(play_url)

        if not html:
            return {"parse": 1, "url": play_url, "header": headers}

        # 1. 解析 player_aaaa 对象
        player_match = re.search(r'var\s+player_aaaa\s*=\s*({[^;]+});', html)
        if player_match:
            try:
                player_data = json.loads(player_match.group(1))
                real_url = player_data.get("url", "")
                if real_url:
                    real_url = real_url.replace("\\/", "/")
                    if ".m3u8" in real_url or real_url.startswith("http"):
                        return {
                            "parse": 0,
                            "url": self._m3u8_proxy_url(real_url) if ".m3u8" in real_url else real_url,
                            "header": headers
                        }
            except Exception as e:
                self.log({"action": "player_aaaa_error", "error": str(e)})

        # 2. 全局匹配 m3u8 地址
        m3u8_match = re.search(r'(https?://[^\s"\':]+\.m3u8[^\s"\']*)', html)
        if m3u8_match:
            real_url = m3u8_match.group(1).replace("\\/", "/")
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(real_url),
                "header": headers
            }

        # 3. 解析 iframe 框架
        iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"', html, re.IGNORECASE)
        if iframe_match:
            iframe_url = self.fix_url(iframe_match.group(1))
            if ".m3u8" in iframe_url:
                return {"parse": 0, "url": self._m3u8_proxy_url(iframe_url), "header": headers}
            url_param = re.search(r'[?&]url=([^&]+)', iframe_url)
            if url_param:
                real_url = urllib.parse.unquote(url_param.group(1)).replace("\\/", "/")
                if ".m3u8" in real_url:
                    return {"parse": 0, "url": self._m3u8_proxy_url(real_url), "header": headers}

        # 兜底交由 WebView 嗅探
        return {"parse": 1, "url": play_url, "header": headers}

    def localProxy(self, param):
        """本地代理处理 m3u8 请求，解决防盗链与相对路径问题"""
        url = param.get("url", "")
        if not url:
            return [404, "text/plain", "Missing URL"]

        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or not hasattr(resp, "text"):
                return [500, "text/plain", "Fetch m3u8 failed"]

            content = resp.text
            # 修正相对路径 TS 分片为绝对路径
            lines = content.split("\n")
            new_lines = []
            base_url = url.rsplit('/', 1)[0] + '/'

            for line in lines:
                line_str = line.strip()
                if line_str and not line_str.startswith("#"):
                    if not line_str.startswith("http"):
                        line_str = urllib.parse.urljoin(base_url, line_str)
                new_lines.append(line_str)

            return [200, "application/vnd.apple.mpegurl", "\n".join(new_lines)]
        except Exception as e:
            return [500, "text/plain", str(e)]

    def _parse_list(self, html):
        items = []
        if not html:
            return items

        pattern = r'<li class="content-item">.*?<a class="video-pic loading" href="([^"]+)" title="([^"]+)".*?<img class="content-img lazy" data-original="([^"]+)"[^>]*>.*?<span class="note text-bg-r">([^<]+)</span>.*?</li>'
        matches = re.findall(pattern, html, re.DOTALL)

        for match in matches:
            link, title, pic, remark = match
            vid = self.extract_id_from_url(link)
            if vid and title.strip():
                items.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": self.fix_url(pic),
                    "vod_remarks": remark.strip()
                })

        if not items:
            pattern2 = r'<a[^>]+href="([^"]*detail[^"]+)"[^>]*>.*?<img[^>]+data-original="([^"]+)"[^>]*>.*?<span[^>]*>([^<]+)</span>.*?<h5[^>]*>.*?<a[^>]+title="([^"]+)"'
            matches2 = re.findall(pattern2, html, re.DOTALL)
            for match in matches2:
                link, pic, remark, title = match
                vid = self.extract_id_from_url(link)
                if vid and title.strip():
                    items.append({
                        "vod_id": vid,
                        "vod_name": title.strip(),
                        "vod_pic": self.fix_url(pic),
                        "vod_remarks": remark.strip()
                    })

        return items

    def _parse_detail(self, html, vid):
        if not html:
            return {"list": []}

        title = ""
        title_match = re.search(r'<h2 class="c_pink text-ellipsis">([^<]+)</h2>', html)
        if title_match:
            title = title_match.group(1).strip()
        if not title:
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                title = re.sub(r'\s*[-–].*$', '', title_match.group(1).strip())

        pic = ""
        pic_match = re.search(r'<img class="lazy" data-original="([^"]+)"', html)
        if pic_match:
            pic = self.fix_url(pic_match.group(1))

        vod_type = ""
        type_match = re.search(r'<p>视频类型：([^<]+)</p>', html)
        if type_match:
            vod_type = type_match.group(1).strip()

        update_time = ""
        time_match = re.search(r'<p>更新时间：([^<]+)</p>', html)
        if time_match:
            update_time = time_match.group(1).strip()

        play_links = re.findall(r'<a class="btn btn-m btn-default" title="[^"]*" href="([^"]+)"', html)

        play_urls = []
        if play_links:
            for idx, link in enumerate(play_links):
                play_urls.append(f"播放{(idx + 1)}${link}")
        else:
            play_urls.append(f"正片$/index.php/vod/play/id/{vid}/sid/1/nid/1.html")

        vod = {
            "vod_id": vid,
            "vod_name": title or "未知标题",
            "vod_pic": pic,
            "vod_remarks": update_time,
            "vod_content": f"类型: {vod_type}" if vod_type else "",
            "vod_play_from": "梦TV",
            "vod_play_url": "#".join(play_urls)
        }

        return {"list": [vod]}

    def _get_pagecount(self, html):
        if not html:
            return 1
        page_match = re.search(r'共(\d+)[頁页]', html)
        if page_match:
            return int(page_match.group(1))
        return 1

    def destroy(self):
        pass