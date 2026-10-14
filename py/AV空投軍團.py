# coding: utf-8
"""
站点: AV空投軍團2站
域名: https://ipornbase.xyz
类型: Drupal + Plyr播放器
特点: 分类列表 /{category}/new?page=N，详情页 window.m3u8List 直出
验证时间: 2026-09-04
m3u8结构: 无广告，直接返回直链，不套代理
"""
import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://ipornbase.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类硬编码
        self.classes = [
            {"type_id": "asian", "type_name": "亞洲國產"},
            {"type_id": "japanese", "type_name": "日本AV"},
            {"type_id": "uncensored-leak", "type_name": "JAV無碼流出"},
            {"type_id": "fc2", "type_name": "FC2素人"},
            {"type_id": "hentai", "type_name": "裏番"},
            {"type_id": "western", "type_name": "歐美"},
            {"type_id": "korean", "type_name": "韓國直播"},
        ]
        # 筛选器（站点无复杂筛选，留空）
        self.filters = {c["type_id"]: [] for c in self.classes}
        # m3u8 无广告，不走代理
        self.NEED_CLEAN = False

    def getName(self):
        return "AV空投軍團2站"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 首页推荐：抓取 asian/new 第一页作为首页推荐
        return self._fetch_list("asian", "1")

    def _fetch_list(self, category, pg):
        """通用列表提取函数"""
        url = f"{self.host}/{category}/new?page={pg}"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            items = []
            # 提取视频卡片：.cf 容器
            pattern = r'<div class="cf[^"]*">.*?<a href="([^"]+)".*?<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)".*?<span class="count-number">([^<]*)</span>.*?<div class="videotitle"><a href="[^"]*"[^>]*>([^<]*)</a></div>'
            for m in re.finditer(pattern, html, re.DOTALL):
                link = m.group(1).strip()
                pic = m.group(2).strip()
                alt = m.group(3).strip()
                remark = m.group(4).strip()
                title = m.group(5).strip()
                if link and title:
                    vod_id = link.strip("/").split("/")[-1] if "/" in link else link
                    items.append({
                        "vod_id": f"{category}|{vod_id}",
                        "vod_name": title,
                        "vod_pic": pic if pic.startswith("http") else urllib.parse.urljoin(self.host, pic),
                        "vod_remarks": remark
                    })
            return {"list": items}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg) if pg else "1"
        extend_dict = self._parse_extend(extend)
        # 兼容数字tid：映射到对应的分类路径
        tid_map = {
            "1": "asian",
            "2": "japanese",
            "3": "uncensored-leak",
            "4": "fc2",
            "5": "hentai",
            "6": "western",
            "7": "korean"
        }
        category = tid_map.get(str(tid), str(tid))
        result = self._fetch_list(category, page)
        return {
            "list": result.get("list", []),
            "page": int(page),
            "pagecount": 1449,
            "limit": 20,
            "total": 28980
        }
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
            for part in extend.split(','):
                if '=' in part:
                    k, v = part.split('=', 1)
                    result[k.strip()] = v.strip()
            return result
        return {}

    def detailContent(self, ids):
        raw = str(ids[0]) if ids else ""
        parts = raw.split("|")
        category = parts[0] if len(parts) > 0 else "asian"
        vod_id = parts[1] if len(parts) > 1 else raw
        url = f"{self.host}/video/{vod_id}"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            # 提取标题
            title_match = re.search(r'<h1 class="vdtitle">([^<]+)</h1>', html)
            title = title_match.group(1).strip() if title_match else ""
            # 提取番号
            sn_match = re.search(r'<div class="field field--name-field-video-sn[^"]*".*?<div class="field--item">([^<]+)</div>', html, re.DOTALL)
            sn = sn_match.group(1).strip() if sn_match else ""
            # 提取演员
            actress_match = re.search(r'<div class="field field--name-field-video-actress[^"]*".*?<div class="field--item">([^<]+)</div>', html, re.DOTALL)
            actress = actress_match.group(1).strip() if actress_match else ""
            # 提取描述
            desc_match = re.search(r'<div class="clearfix text-formatted field field--name-field-video-description[^"]*".*?<p>([^<]+)</p>', html, re.DOTALL)
            desc = desc_match.group(1).strip() if desc_match else ""
            # 提取 m3u8 地址（直接）
            m3u8_match = re.search(r'window\.m3u8List\s*=\s*\[([^\]]+)\]', html)
            play_url = ""
            if m3u8_match:
                m3u8_raw = m3u8_match.group(1).strip()
                # 提取引号内的URL
                url_match = re.search(r'["\']([^"\']+\.m3u8[^"\']*)["\']', m3u8_raw)
                if url_match:
                    play_url = url_match.group(1).strip()
                    if not play_url.startswith("http"):
                        play_url = urllib.parse.urljoin(self.host, play_url)
            if not play_url:
                # 兜底：正则全文搜
                fallback = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
                if fallback:
                    play_url = fallback.group(0).strip()
            # 构建详情
            vod = {
                "vod_id": raw,
                "vod_name": title or vod_id,
                "vod_pic": "",
                "vod_remarks": sn,
                "vod_actor": actress,
                "vod_director": "",
                "vod_content": desc,
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}" if play_url else ""
            }
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        page = str(pg) if pg else "1"
        url = f"{self.host}/search?fulltext={urllib.parse.quote(key)}&page={page}"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            items = []
            pattern = r'<div class="cf[^"]*">.*?<a href="([^"]+)".*?<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)".*?<span class="count-number">([^<]*)</span>.*?<div class="videotitle"><a href="[^"]*"[^>]*>([^<]*)</a></div>'
            for m in re.finditer(pattern, html, re.DOTALL):
                link = m.group(1).strip()
                pic = m.group(2).strip()
                alt = m.group(3).strip()
                remark = m.group(4).strip()
                title = m.group(5).strip()
                if link and title:
                    vid = link.strip("/").split("/")[-1] if "/" in link else link
                    items.append({
                        "vod_id": f"search|{vid}",
                        "vod_name": title,
                        "vod_pic": pic if pic.startswith("http") else urllib.parse.urljoin(self.host, pic),
                        "vod_remarks": remark
                    })
            return {"list": items, "page": int(page)}
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id or "").strip()
        ua = self.headers.get("User-Agent", "")
        if not play_url:
            return {"parse": 1, "url": "", "header": {"User-Agent": ua}}
        # 直链：直接返回
        if play_url.startswith("http") and ".m3u8" in play_url:
            # 无广告特征，返回原始直链（不套代理）
            return {"parse": 0, "url": play_url, "header": {"User-Agent": ua}}
        # 如果不是直链，尝试当作播放页抓取
        page_url = play_url if play_url.startswith("http") else urllib.parse.urljoin(self.host, play_url)
        try:
            resp = self.fetch(page_url, headers=self.headers, timeout=10)
            if not resp or resp.status_code != 200:
                return {"parse": 1, "url": page_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}
            html = resp.text
            # 提取 m3u8
            m3u8_match = re.search(r'window\.m3u8List\s*=\s*\[([^\]]+)\]', html)
            if m3u8_match:
                raw = m3u8_match.group(1).strip()
                url_match = re.search(r'["\']([^"\']+\.m3u8[^"\']*)["\']', raw)
                if url_match:
                    m3u8_url = url_match.group(1).strip()
                    if not m3u8_url.startswith("http"):
                        m3u8_url = urllib.parse.urljoin(self.host, m3u8_url)
                    return {"parse": 0, "url": m3u8_url, "header": {"User-Agent": ua}}
            # 全文兜底
            fallback = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
            if fallback:
                return {"parse": 0, "url": fallback.group(0).strip(), "header": {"User-Agent": ua}}
            return {"parse": 1, "url": page_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}
        except Exception:
            return {"parse": 1, "url": page_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}

    def recommendContent(self, ids, pg):
        # 无推荐接口，返回空
        return {"list": []}

    def destroy(self):
        pass

    # localProxy 保留但不使用（无广告特征）
    def localProxy(self, param):
        return [404, "text/plain", b"not used"]