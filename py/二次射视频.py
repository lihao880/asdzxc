# coding: utf-8
import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xn--cl0a.ercisheshipin.click"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "avmingxing", "type_name": "AV明星"},
            {"type_id": "zhongweism", "type_name": "SM重味"},
            {"type_id": "zhongwenzimu", "type_name": "中文字幕"},
            {"type_id": "fuzhuang", "type_name": "制服诱惑"},
            {"type_id": "zuiqu", "type_name": "口交口爆"},
            {"type_id": "guochan", "type_name": "国产视频"},
            {"type_id": "duorenyundong", "type_name": "多人运动"},
            {"type_id": "juruyouwu", "type_name": "巨乳尤物"},
            {"type_id": "qiangluan", "type_name": "强奸乱伦"},
            {"type_id": "renhanwuma", "type_name": "日韩无码"},
            {"type_id": "oumeijingpin", "type_name": "欧美精品"},
            {"type_id": "zhiye", "type_name": "特殊职业"},
            {"type_id": "weixi", "type_name": "自慰系列"},
            {"type_id": "zipai", "type_name": "自拍偷拍"},
            {"type_id": "lingjiarenqi", "type_name": "邻家人妻"},
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}
        self.ad_patterns = ["/20260731/UTxI1Mxv/9567kb/hls/"]

    def getName(self):
        return "二次射视频"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        url = f"{self.host}/welcome/"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": []}
        html = r.text
        items = self._parse_list(html, url)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/videos/categories/{tid}/{page}/"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        html = r.text
        items = self._parse_list(html, url)
        pagecount = 1
        last_match = re.search(r'<li class="last"><a[^>]*href="[^"]*/' + re.escape(tid) + r'/(\d+)/"[^>]*>最后</a></li>', html, re.S)
        if last_match:
            pagecount = int(last_match.group(1))
        else:
            nums = re.findall(r'<li class="page"><a[^>]*>(\d+)</a></li>', html)
            if nums:
                pagecount = max(int(n) for n in nums)
        self.log({"category": tid, "page": page, "pagecount": pagecount, "count": len(items)})
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": 0
        }

    def _parse_list(self, html, base_url):
        items = []
        for m in re.finditer(r'<div class="item">.*?<a href="([^"]+)".*?title="([^"]+)".*?data-original="([^"]+)".*?<div class="duration">([^<]+)</div>.*?<div class="added"><em>([^<]+)</em></div>', html, re.S):
            link = m.group(1).strip()
            title = m.group(2).strip()
            pic = m.group(3).strip()
            duration = m.group(4).strip()
            added = m.group(5).strip()
            if not link or not title:
                continue
            if not link.startswith("http"):
                link = urllib.parse.urljoin(base_url, link)
            items.append({
                "vod_id": link,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": f"{duration} {added}",
            })
        return items

    def _norm_ids(self, ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            try:
                ids = ids.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        return str(ids).strip()

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}
        title = "加载中"
        pic = ""
        r = self.fetch(vid, headers=self.headers, timeout=15)
        if r and r.status_code == 200:
            html = r.text
            m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if not title or title == "加载中":
                m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html, re.S)
                if m:
                    title = m.group(1).strip()
            m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html, re.S)
            if m:
                pic = m.group(1).strip()
        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${vid}"
        }]}

    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/search/?q={urllib.parse.quote(key)}"
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": []}
        html = r.text
        items = self._parse_list(html, url)
        return {"list": items}

    def playerContent(self, flag, id, vipFlags):
        ua = self.headers.get("User-Agent", "")
        play_url = str(id or "").strip()
        if not play_url:
            return {"parse": 1, "url": "", "header": {"User-Agent": ua}}
        if "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]
        if not play_url.startswith("http"):
            if not play_url.startswith("//"):
                play_url = "https://" + play_url
        if play_url.endswith(".m3u8") or ".m3u8" in play_url.lower():
            proxy_base = self.getProxyUrl()
            if "?" in proxy_base:
                proxy_url = proxy_base + "&url=" + urllib.parse.quote(play_url, safe="")
            else:
                proxy_url = proxy_base + "?url=" + urllib.parse.quote(play_url, safe="")
            return {"parse": 0, "url": proxy_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}
        if not play_url.startswith("http"):
            play_url = urllib.parse.urljoin(self.host, play_url)
        r = self.fetch(play_url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"parse": 1, "url": play_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}
        html = r.text
        m = re.search(r'video_url:\s*["\']([^"\']+)["\']', html)
        if m:
            direct_url = m.group(1).strip()
            if direct_url:
                proxy_base = self.getProxyUrl()
                if "?" in proxy_base:
                    proxy_url = proxy_base + "&url=" + urllib.parse.quote(direct_url, safe="")
                else:
                    proxy_url = proxy_base + "?url=" + urllib.parse.quote(direct_url, safe="")
                return {"parse": 0, "url": proxy_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}
        return {"parse": 1, "url": play_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}

    def localProxy(self, params):
        if isinstance(params, str):
            target = params
        else:
            target = (params or {}).get("url", "")
        target = urllib.parse.unquote(str(target or "").strip())
        if not target or not target.startswith("http"):
            return [400, "text/plain", b"invalid url"]
        try:
            r = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=15)
            if not r or r.status_code != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            raw = r.content if hasattr(r, "content") else b""
            if not raw:
                return [502, "text/plain", b"empty response"]
            text = raw.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegURL", cleaned.encode("utf-8")]
        except Exception as e:
            self.log({"localProxy": "error", "error": str(e)})
            return [500, "text/plain", b"proxy error"]

    def _clean_m3u8(self, text, source_url):
        """递归清洗多码率m3u8中的广告分片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 检测是否为多码率主表（包含 #EXT-X-STREAM-INF）
        has_stream_inf = any(line.startswith("#EXT-X-STREAM-INF") for line in lines)

        if has_stream_inf:
            # 多码率模式：遍历每个子流，递归清洗
            out = []
            i = 0
            while i < len(lines):
                line = lines[i]
                if line.startswith("#EXT-X-STREAM-INF"):
                    # 保留 #EXT-X-STREAM-INF 行
                    out.append(line)
                    i += 1
                    # 下一行是子流URL
                    if i < len(lines):
                        sub_url = lines[i]
                        if not sub_url.startswith("http"):
                            sub_url = urllib.parse.urljoin(source_url, sub_url)
                        # 递归清洗子流
                        cleaned_sub = self._clean_sub_m3u8(sub_url)
                        out.append(cleaned_sub)
                        i += 1
                else:
                    out.append(line)
                    i += 1
            return "\n".join(out) + "\n"

        # 单码率模式：直接过滤分片
        return self._filter_segments(lines, source_url)

    def _clean_sub_m3u8(self, sub_url):
        """获取并清洗子流m3u8，返回清洗后的内容（作为分片URL嵌入主表）"""
        try:
            r = self.fetch(sub_url, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=15)
            if not r or r.status_code != 200:
                return sub_url  # 获取失败则返回原URL，避免播放中断
            raw = r.content if hasattr(r, "content") else b""
            if not raw:
                return sub_url
            text = raw.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return sub_url
            lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
            filtered = self._filter_segments(lines, sub_url)
            # 将清洗后的内容作为数据URL返回（或者返回清洗后的URL）
            # 由于子流清洗后是完整m3u8内容，需要返回数据URL或代理地址
            # 这里返回原URL，在播放器端会重新请求，但localProxy会再次清洗
            # 更简单的方式：直接返回清洗后的内容作为数据URL
            import base64
            encoded = base64.b64encode(filtered.encode("utf-8")).decode("ascii")
            return "data:application/vnd.apple.mpegURL;base64," + encoded
        except Exception as e:
            self.log({"clean_sub": "error", "url": sub_url, "error": str(e)})
            return sub_url

    def _filter_segments(self, lines, source_url):
        """过滤单个m3u8中的广告分片"""
        out = []
        removed = 0
        pending = []
        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                is_ad = False
                for ad_pat in self.ad_patterns:
                    if ad_pat in line:
                        is_ad = True
                        break
                if is_ad:
                    removed += 1
                    pending = []
                else:
                    out.extend(pending)
                    if not line.startswith("http"):
                        line = urllib.parse.urljoin(source_url, line)
                    out.append(line)
                    pending = []
                continue
            if line.startswith("#"):
                out.append(line)
            else:
                if not line.startswith("http"):
                    line = urllib.parse.urljoin(source_url, line)
                out.append(line)
        if removed:
            self.log({"m3u8": "ad_filtered", "removed": removed})
        # 清理重复标签
        result = []
        for line in out:
            if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-DISCONTINUITY"):
                if result and result[-1] == line:
                    continue
            result.append(line)
        return "\n".join(result) + "\n"

    def destroy(self):
        pass