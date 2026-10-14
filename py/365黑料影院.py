# coding: utf-8
# 站点: 365黑料影院 (mh365.cc)
# 类型: 成人影视聚合站 (HTML解析)
# 域名: https://www.mh365.cc

import json
import re
import base64
from urllib.parse import urljoin, urlparse, quote, unquote

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.mh365.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "oumeiag", "type_name": "欧美劲爆"},
            {"type_id": "guochanv", "type_name": "国产传媒"},
            {"type_id": "huanlian", "type_name": "AI换脸"},
            {"type_id": "rihank", "type_name": "日韩无码"},
            {"type_id": "lunliv", "type_name": "伦理影片"},
            {"type_id": "qiangjian", "type_name": "强奸乱伦"},
            {"type_id": "yezhan", "type_name": "野战车震"},
            {"type_id": "chengren", "type_name": "成人动漫"},
            {"type_id": "jiatingk", "type_name": "家庭乱伦"},
            {"type_id": "diaojiao", "type_name": "SM调教"},
            {"type_id": "baihe", "type_name": "百合女同"},
            {"type_id": "guochanx", "type_name": "国产主播"},
            {"type_id": "jiudian", "type_name": "酒店探花"},
            {"type_id": "xuesheng", "type_name": "学生空姐"},
            {"type_id": "touqing", "type_name": "偷情少妇"},
            {"type_id": "chigua", "type_name": "吃瓜黑料"},
            {"type_id": "luguan", "type_name": "撸管必看"},
            {"type_id": "fancha", "type_name": "反差母狗"},
            {"type_id": "zipai", "type_name": "自拍偷拍"},
            {"type_id": "zhibo", "type_name": "直播裸聊"}
        ]
        years = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2010, -1)]
        self.filters = {}
        for c in self.classes:
            self.filters[c["type_id"]] = [{"key": "year", "name": "年代", "value": years}]

    def getName(self):
        return "365黑料影院"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""
        pass

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        url = self.host + "/"
        res = self.fetch(url, headers=self.headers)
        if not res or res.status_code != 200:
            return {"list": []}
        html = res.text
        items = []
        # 匹配首页所有卡片 - 更宽松的模式
        patterns = [
            # 标准卡片
            r'<article\s+class="[^"]*wu-poster-card[^"]*"[^>]*>.*?<a\s+class="[^"]*wu-poster-card__cover[^"]*"\s+href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h3>.*?<a\s+href="[^"]+"[^>]*>([^<]+)</a>.*?</h3>',
            # 备用模式
            r'<article\s+class="[^"]*wu-poster-card[^"]*"[^>]*>.*?<a\s+href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h3>([^<]+)</h3>',
            # 首页magazine焦点
            r'<article\s+class="[^"]*wt05-magazine__item[^"]*"[^>]*>.*?<a\s+class="[^"]*wt05-magazine__media[^"]*"\s+href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h2>.*?<a\s+href="[^"]+"[^>]*>([^<]+)</a>.*?</h2>',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                if len(match) >= 3:
                    vod_id = match[0]
                    vod_pic = match[1]
                    vod_name = match[2].strip()
                    if vod_id and vod_name and not vod_id.startswith("#") and not vod_id.startswith("javascript"):
                        items.append({
                            "vod_id": vod_id,
                            "vod_name": vod_name,
                            "vod_pic": urljoin(self.host, vod_pic),
                            "vod_remarks": ""
                        })
                if len(items) >= 30:
                    break
            if len(items) >= 30:
                break
        # 如果上面的都没匹配到，尝试直接搜索所有a标签中的视频链接
        if not items:
            video_links = re.findall(r'<a\s+href="(/video/[^"]+\.html)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h3[^>]*>([^<]+)</h3>', html, re.DOTALL)
            for match in video_links[:30]:
                vod_id = match[0]
                vod_pic = match[1]
                vod_name = match[2].strip()
                if vod_id and vod_name and not vod_id.startswith("#"):
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": vod_name,
                        "vod_pic": urljoin(self.host, vod_pic),
                        "vod_remarks": ""
                    })
        return {"list": items[:30]}
    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        base_url = f"{self.host}/video/{tid}"
        params = {}
        if page and page != "1":
            params["page"] = page
        ext = self._parse_extend(extend)
        if ext and ext.get("year"):
            params["year"] = ext["year"]
        url = base_url + ("?" + "&".join([f"{k}={v}" for k, v in params.items()]) if params else "")
        res = self.fetch(url, headers=self.headers)
        if not res or res.status_code != 200:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        html = res.text
        items = []
        pattern = r'<article class="wu-poster-card"[^>]*>.*?<a class="wu-poster-card__cover" href="([^"]+)">.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h3><a href="[^"]+">([^<]+)</a></h3>.*?<p>([^<]*)</p>.*?<small>([^<]*)</small>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            vod_id = match[0]
            vod_pic = match[1]
            vod_name = match[2].strip()
            vod_type = match[3].strip() if match[3] else ""
            vod_year = match[4].strip() if match[4] else ""
            remark = f"{vod_type} {vod_year}".strip()
            items.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": urljoin(self.host, vod_pic),
                "vod_remarks": remark
            })
        pagecount = 1
        page_links = re.findall(r'<a[^>]*href="[^"]*[?&]page=(\d+)"[^>]*>', html)
        if page_links:
            max_page = max([int(x) for x in page_links if x.isdigit()] + [1])
            pagecount = max_page
        next_match = re.search(r'<a[^>]*href="[^"]*[?&]page=(\d+)"[^>]*>[^<]*下一页[^<]*</a>', html)
        if next_match and int(next_match.group(1)) > int(page):
            pagecount = max(pagecount, int(next_match.group(1)))
        if not page_links and not next_match:
            pagecount = 1
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": len(items) + (int(page) - 1) * 20
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        url = self.host + vod_id if vod_id.startswith("/") else self.host + "/" + vod_id
        res = self.fetch(url, headers=self.headers)
        if not res or res.status_code != 200:
            return {"list": []}
        html = res.text
        title_match = re.search(r'<h1[^>]*itemprop="name"[^>]*>([^<]+)</h1>', html)
        vod_name = title_match.group(1).strip() if title_match else ""
        pic_match = re.search(r'<a class="wu-detail-poster"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>', html, re.DOTALL)
        vod_pic = urljoin(self.host, pic_match.group(1)) if pic_match else ""
        meta_match = re.search(r'<p class="wu-detail-meta">([^<]+)</p>', html)
        vod_remarks = meta_match.group(1).strip() if meta_match else ""
        desc_match = re.search(r'<p class="wu-detail-summary"[^>]*itemprop="description"[^>]*>([^<]+)</p>', html)
        vod_content = desc_match.group(1).strip() if desc_match else ""
        episode_links = []
        ep_pattern = r'<div class="wu-episode-list">.*?<a[^>]*href="([^"]+)"[^>]*>.*?<b>([^<]*)</b>.*?<small>([^<]*)</small>'
        ep_matches = re.findall(ep_pattern, html, re.DOTALL)
        if not ep_matches:
            ep_pattern2 = r'<div class="wu-episode-list">.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
            ep_matches2 = re.findall(ep_pattern2, html, re.DOTALL)
            for match in ep_matches2:
                ep_link = match[0]
                ep_name = match[1].strip()
                if ep_link and ep_name:
                    episode_links.append((ep_name, ep_link))
        else:
            for match in ep_matches:
                ep_link = match[0]
                ep_name = match[1].strip() or match[2].strip()
                if ep_link and ep_name:
                    episode_links.append((ep_name, ep_link))
        if not episode_links:
            play_btn = re.search(r'<a[^>]*href="([^"]+)"[^>]*>[^<]*立即播放[^<]*</a>', html)
            if play_btn:
                play_link = play_btn.group(1)
                if play_link and not play_link.startswith("#"):
                    episode_links.append(("播放", play_link))
        if episode_links:
            play_url = "$$$".join([f"{name}${link}" for name, link in episode_links])
            play_from = "$$$".join(["线路1"] * len(episode_links))
        else:
            play_url = ""
            play_from = ""
        vod = {
            "vod_id": vod_id,
            "vod_name": vod_name or "未知影片",
            "vod_pic": vod_pic,
            "vod_remarks": vod_remarks,
            "vod_content": vod_content or vod_name,
            "vod_play_from": play_from,
            "vod_play_url": play_url
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        url = f"{self.host}/video/search={key}"
        if pg and pg != "1":
            url += f"&page={pg}"
        res = self.fetch(url, headers=self.headers)
        if not res or res.status_code != 200:
            return {"list": [], "page": 1}
        html = res.text
        items = []
        pattern = r'<article class="wu-poster-card"[^>]*>.*?<a class="wu-poster-card__cover" href="([^"]+)">.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h3><a href="[^"]+">([^<]+)</a></h3>.*?<p>([^<]*)</p>.*?<small>([^<]*)</small>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            vod_id = match[0]
            vod_pic = match[1]
            vod_name = match[2].strip()
            vod_type = match[3].strip() if match[3] else ""
            vod_year = match[4].strip() if match[4] else ""
            remark = f"{vod_type} {vod_year}".strip()
            items.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": urljoin(self.host, vod_pic),
                "vod_remarks": remark
            })
        return {"list": items, "page": int(pg) if pg else 1}

    def playerContent(self, flag, id, vipFlags):
        # 如果已经是m3u8链接，通过代理返回（过滤广告）
        if id.startswith("http") and ".m3u8" in id.lower():
            return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": self.headers}
        if id.startswith("http") and ".mp4" in id.lower():
            return {"parse": 0, "url": id, "header": self.headers}
        # 播放页解析
        url = self.host + id if id.startswith("/") else self.host + "/" + id
        res = self.fetch(url, headers=self.headers)
        if not res or res.status_code != 200:
            return {"parse": 1, "url": url, "header": self.headers}
        html = res.text
        m3u8_url = None
        # 优先从 data-player-token 提取
        token_match = re.search(r'data-player-token="([^"]+)"', html)
        if token_match:
            try:
                token = token_match.group(1)
                decoded = base64.b64decode(token).decode('utf-8')
                if decoded.startswith("http"):
                    if "url=" in decoded:
                        url_param = re.search(r'[?&]url=([^&]+)', decoded)
                        if url_param:
                            m3u8_url = unquote(url_param.group(1))
                    elif ".m3u8" in decoded.lower():
                        m3u8_url = decoded
            except:
                pass
        # 从 iframe 提取
        if not m3u8_url:
            iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"[^>]*>', html)
            if iframe_match:
                src = iframe_match.group(1)
                if "url=" in src:
                    url_param = re.search(r'[?&]url=([^&]+)', src)
                    if url_param:
                        m3u8_url = unquote(url_param.group(1))
                elif ".m3u8" in src.lower():
                    m3u8_url = src
        # 从 data-video-token 提取
        if not m3u8_url:
            video_token_match = re.search(r'data-video-token="([^"]+)"', html)
            if video_token_match:
                try:
                    token = video_token_match.group(1)
                    decoded = base64.b64decode(token).decode('utf-8')
                    if ".m3u8" in decoded.lower():
                        m3u8_url = decoded
                except:
                    pass
        # 如果找到m3u8，走代理过滤广告
        if m3u8_url and m3u8_url.endswith(".m3u8"):
            return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": self.headers}
        # 直接播放链接
        direct_match = re.search(r'<video[^>]*src="([^"]+)"', html)
        if direct_match:
            video_url = direct_match.group(1)
            if video_url.startswith("http"):
                if ".m3u8" in video_url.lower():
                    return {"parse": 0, "url": self._m3u8_proxy_url(video_url), "header": self.headers}
                return {"parse": 0, "url": video_url, "header": self.headers}
        # 降级到嗅探
        return {"parse": 1, "url": url, "header": self.headers}
    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤"""
        target = unquote(str((param or {}).get("url", "") or ""))
        if not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]
        try:
            res = self.fetch(target, headers=self.headers, timeout=15, verify=False)
            if not res or getattr(res, "status_code", 0) != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            raw = getattr(res, "content", b"") or b""
            text = raw.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log("m3u8代理失败: " + str(e))
            return [500, "text/plain", b"m3u8 proxy error"]

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片，保留正片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"
        # 处理多码率 m3u8
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    if ".m3u8" in child.lower():
                        out.append(self._m3u8_proxy_url(child))
                    else:
                        out.append(child)
            return "\n".join(out) + "\n"
        # 单码率 m3u8 - 过滤广告分片
        source_path = urlparse(source_url).path
        source_parts = [p for p in source_path.split("/") if p]
        content_root = "/" + "/".join(source_parts[:2]) + "/" if len(source_parts) >= 2 else ""
        segments = []
        pending = []
        removed = 0
        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media = urljoin(source_url, line)
                # 广告过滤：包含 ad、banner、advert 等关键词的分片
                if self._is_ad_segment(media) or (content_root and content_root not in urlparse(media).path):
                    removed += 1
                else:
                    segments.extend(pending)
                    segments.append(media)
                pending = []
                continue
            segments.append(self._rewrite_m3u8_tag(line, source_url))
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line == "#EXT-X-KEY:METHOD=NONE" or line == "#EXT-X-DISCONTINUITY":
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)
        while len(out) > 1 and out[-2] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop(-2)
        if removed:
            self.log("m3u8已过滤广告分片: %d" % removed)
        return "\n".join(out) + "\n"

    def _is_ad_segment(self, url):
        """判断是否为广告分片"""
        ad_keywords = [
            "ad", "banner", "advert", "advertisement", "promo", 
            "sponsor", "campaign", "marketing", "promotion",
            "ads", "ad_", "-ad-", "_ad_", ".ad.", "-promo-",
            "guanggao", "gg_", "_gg"
        ]
        url_lower = url.lower()
        for kw in ad_keywords:
            if kw in url_lower:
                return True
        return False

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写 m3u8 标签中的 URI（补全绝对地址）"""
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                return 'URI="' + urljoin(source_url, match.group(1)) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            return urljoin(source_url, line)
        return line

    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址"""
        return self.getProxyUrl() + "&url=" + quote(str(url or ""), safe="")

    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except:
                pass
            result = {}
            clean = extend.strip()
            if clean.startswith("{") and clean.endswith("}"):
                clean = clean[1:-1]
            for part in clean.split(','):
                if '=' in part:
                    k, v = part.split('=', 1)
                    result[k.strip()] = v.strip()
            return result
        return {}