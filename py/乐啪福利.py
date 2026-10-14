# coding: utf-8
"""
乐啪福利 TVBox 爬虫
站点：https://lpfl12.cfd/
类型：MacCMS HTML 影视站
"""
import re
import json
import posixpath
from urllib.parse import urljoin, quote, unquote, urlparse

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://lpfl12.cfd"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类列表：tid 范围 28-48
        self.classes = [
            {"type_id": "28", "type_name": "国产自拍"},
            {"type_id": "29", "type_name": "主播诱惑"},
            {"type_id": "30", "type_name": "探花约炮"},
            {"type_id": "31", "type_name": "偷拍偷窥"},
            {"type_id": "32", "type_name": "网曝吃瓜"},
            {"type_id": "33", "type_name": "抖阴短片"},
            {"type_id": "34", "type_name": "传媒剧情"},
            {"type_id": "35", "type_name": "日韩主播"},
            {"type_id": "36", "type_name": "日韩无码"},
            {"type_id": "37", "type_name": "中文字幕"},
            {"type_id": "38", "type_name": "AV解说"},
            {"type_id": "39", "type_name": "换脸明星"},
            {"type_id": "40", "type_name": "强奸乱伦"},
            {"type_id": "41", "type_name": "女优明星"},
            {"type_id": "42", "type_name": "欧美激情"},
            {"type_id": "43", "type_name": "重口激情"},
            {"type_id": "44", "type_name": "三级伦理"},
            {"type_id": "45", "type_name": "剧情动漫"},
            {"type_id": "46", "type_name": "SM调教"},
            {"type_id": "47", "type_name": "女同性恋"},
            {"type_id": "48", "type_name": "VR视角"},
        ]
        self.filters = {str(i): [] for i in range(28, 49)}

    def getName(self):
        return "乐啪福利"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self.categoryContent("28", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg) if pg else "1"
        url = f"{self.host}/frim/index{tid}-{page}.html"
        if page == "1":
            url = f"{self.host}/frim/index{tid}.html"

        try:
            res = self.fetch(url, headers=self.headers)
            if not res:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

            html = res.text
            items = self._parse_vod_list(html)
            pagecount, total = self._parse_pagination(html)

            if pagecount <= 1:
                pagecount = self._parse_last_page(html)

            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount or 1,
                "limit": 20,
                "total": total or 0
            }
        except Exception as e:
            self.log(f"categoryContent error: {str(e)}")
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        vod_id = str(ids[0])
        url = f"{self.host}/movie/index{vod_id}.html"

        try:
            res = self.fetch(url, headers=self.headers)
            if not res:
                return {"list": []}

            html = res.text
            vod = self._parse_detail(html, vod_id)
            return {"list": [vod]} if vod else {"list": []}
        except Exception as e:
            self.log(f"detailContent error: {str(e)}")
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/search.php"
        data = {"searchword": key}
        try:
            res = self.post(url, data=data, headers=self.headers)
            if not res:
                return {"list": [], "page": 1}

            html = res.text
            items = self._parse_search_results(html)
            return {"list": items, "page": int(pg) if pg else 1}
        except Exception as e:
            self.log(f"searchContent error: {str(e)}")
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        if id and id.endswith((".m3u8", ".mp4")):
            if id.endswith(".m3u8"):
                return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": {}}
            return {"parse": 0, "url": id, "header": {"User-Agent": self.headers["User-Agent"]}}

        url = id if id.startswith("http") else f"{self.host}/play/{id}.html"
        try:
            res = self.fetch(url, headers=self.headers)
            if not res:
                return {"parse": 1, "url": id, "header": self.headers}

            html = res.text
            m3u8_url = self._extract_m3u8(html)

            if m3u8_url:
                return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": {}}
            else:
                return {"parse": 1, "url": id, "header": self.headers}
        except Exception as e:
            self.log(f"playerContent error: {str(e)}")
            return {"parse": 1, "url": id, "header": self.headers}

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def localProxy(self, param):
        """m3u8 代理 + 广告过滤"""
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            res = self.fetch(target, headers=self.headers, timeout=15)
            if not res:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(res, "content", b"") or b""
            if not content and hasattr(res, "text") and res.text:
                content = res.text.encode("utf-8", errors="ignore")

            if not content:
                return [502, "text/plain", b"empty content"]

            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 处理多码率 Master Playlist
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

        # 从 #EXT-X-KEY 提取正片目录（更准确）
        main_dir = source_dir
        for line in lines:
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                uri_match = re.search(r'URI="([^"]+)"', line)
                if uri_match:
                    key_path = uri_match.group(1)
                    if not key_path.startswith("http"):
                        key_dir = posixpath.dirname(key_path)
                        if key_dir and key_dir != "/":
                            main_dir = key_dir + "/"
                            break

        segments = []
        pending = []

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urljoin(source_url, line)
                media_parsed = urlparse(media_url)

                # 过滤逻辑：判断分片路径是否以正片目录开头
                is_ad = not media_parsed.path.startswith(main_dir)

                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urljoin(source_url, line))
            else:
                segments.append(line)

        # 二次清洗：去除孤立的 DISCONTINUITY 和 KEY:METHOD=NONE
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写 m3u8 标签中的 URI"""
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)

        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)

        return line

    def _parse_vod_list(self, html):
        items = []
        pattern = r'<li class="col-md-[56]\s+col-sm-4\s+col-xs-3">(.*?)</li>'
        matches = re.findall(pattern, html, re.DOTALL)

        for block in matches:
            link_match = re.search(r'href="(/movie/index(\d+)\.html)"', block)
            if not link_match:
                continue
            vod_id = link_match.group(2)

            title_match = re.search(r'title="([^"]+)"', block)
            title = title_match.group(1) if title_match else ""

            pic_match = re.search(r'data-original="([^"]+)"', block)
            pic = pic_match.group(1) if pic_match else ""

            remark_match = re.search(r'<span class="pic-text text-right">([^<]+)</span>', block)
            remark = remark_match.group(1) if remark_match else ""

            if vod_id and title:
                items.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })

        return items

    def _parse_search_results(self, html):
        items = []
        pattern = r'<li class="active top-line-dot clearfix">(.*?)</li>'
        matches = re.findall(pattern, html, re.DOTALL)

        for block in matches:
            link_match = re.search(r'href="(/movie/index(\d+)\.html)"', block)
            if not link_match:
                continue
            vod_id = link_match.group(2)

            title_match = re.search(r'<h3 class="title"><a href="[^"]*">([^<]+)</a></h3>', block)
            title = title_match.group(1) if title_match else ""

            pic_match = re.search(r'data-original="([^"]+)"', block)
            pic = pic_match.group(1) if pic_match else ""

            remark_match = re.search(r'<span class="pic-text text-right">([^<]+)</span>', block)
            remark = remark_match.group(1) if remark_match else ""

            if vod_id and title:
                items.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark or ""
                })

        return items

    def _parse_detail(self, html, vod_id):
        title_match = re.search(r'<h3 class="title">([^<]+)</h3>', html)
        title = title_match.group(1).strip() if title_match else ""

        pic_match = re.search(r'data-original="([^"]+)"', html)
        pic = pic_match.group(1) if pic_match else ""

        desc_match = re.search(r'<span class="detail-content" style="display: none;">(.*?)</span>', html, re.DOTALL)
        content = ""
        if desc_match:
            content = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
        if not content:
            desc_match2 = re.search(r'<span class="detail-sketch">([^<]+)</span>', html)
            content = desc_match2.group(1) if desc_match2 else ""

        vod = {
            "vod_id": str(vod_id),
            "vod_name": title or "未知标题",
            "vod_pic": pic,
            "vod_remarks": "更新至第1集",
            "vod_content": content,
            "vod_actor": "内详",
            "vod_director": "内详",
            "vod_play_from": "播放",
            "vod_play_url": f"第1集${vod_id}-0-0"
        }

        return vod

    def _parse_pagination(self, html):
        pagecount = 1
        total = 0

        num_match = re.search(r'(\d+)/(\d+)', html)
        if num_match:
            pagecount = int(num_match.group(2))

        total_match = re.search(r'共有(\d+)部影片', html)
        if total_match:
            total = int(total_match.group(1))

        return pagecount, total

    def _parse_last_page(self, html):
        match = re.search(r'<a[^>]*href="[^"]*/index\d+-(\d+)\.html"[^>]*>尾页</a>', html)
        if match:
            return int(match.group(1))
        matches = re.findall(r'<a[^>]*href="[^"]*/index\d+-(\d+)\.html"[^>]*>', html)
        if matches:
            pages = [int(x) for x in matches if x.isdigit()]
            if pages:
                return max(pages)
        return 1

    def _extract_m3u8(self, html):
        match = re.search(r'var now\s*=\s*"([^"]+\.m3u8)"', html)
        if match:
            return match.group(1).replace("\\/", "/")

        match = re.search(r'now\s*=\s*"([^"]+\.m3u8)"', html)
        if match:
            return match.group(1).replace("\\/", "/")

        match = re.search(r'url\s*:\s*"([^"]+\.m3u8)"', html)
        if match:
            return match.group(1).replace("\\/", "/")

        return None

    def destroy(self):
        pass