# coding: utf-8
# 站点: 护士AV (https://5g.hushiav7.cc/a/)
# 类型: MacCMS HTML解析站
# 主域名: https://5g.hushiav7.cc/a/

import re
import json
import posixpath
import urllib.parse
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://5g.hushiav7.cc/a"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "244", "type_name": "55资源"},
            {"type_id": "358", "type_name": "番茄资源"},
            {"type_id": "119", "type_name": "不卡资源"},
            {"type_id": "286", "type_name": "兔儿资源"},
            {"type_id": "370", "type_name": "森林资源"},
            {"type_id": "329", "type_name": "库库资源"}
        ]
        self.filters = {
            "244": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": "244"},
                    {"n": "AV解说", "v": "266"},
                    {"n": "国产自拍", "v": "254"},
                    {"n": "熟女人妻", "v": "255"},
                    {"n": "萝莉少女", "v": "256"},
                    {"n": "百合剧情", "v": "257"},
                    {"n": "美乳巨乳", "v": "258"},
                    {"n": "强歼乱伦", "v": "259"},
                    {"n": "抖音视频", "v": "260"}
                ]}
            ],
            "358": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": "358"},
                    {"n": "高清有码", "v": "369"},
                    {"n": "动漫精选", "v": "368"},
                    {"n": "学生妹", "v": "367"},
                    {"n": "中文字幕", "v": "366"},
                    {"n": "高清无码", "v": "365"},
                    {"n": "黑料网曝", "v": "364"},
                    {"n": "主播网红", "v": "363"},
                    {"n": "乱伦系列", "v": "362"}
                ]}
            ],
            "119": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": "119"},
                    {"n": "国产视频", "v": "120"},
                    {"n": "中文字幕", "v": "121"},
                    {"n": "国产传媒", "v": "122"},
                    {"n": "日本有码", "v": "123"},
                    {"n": "日本无码", "v": "124"},
                    {"n": "欧美无码", "v": "125"},
                    {"n": "强干乱伦", "v": "126"},
                    {"n": "制服诱惑", "v": "127"}
                ]}
            ],
            "286": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": "286"},
                    {"n": "精品推荐", "v": "304"},
                    {"n": "主播秀色", "v": "305"},
                    {"n": "日本有码", "v": "306"},
                    {"n": "日本无码", "v": "307"},
                    {"n": "中文字幕", "v": "308"},
                    {"n": "童颜巨乳", "v": "309"},
                    {"n": "性感人妻", "v": "310"},
                    {"n": "强歼乱伦", "v": "311"}
                ]}
            ],
            "370": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": "370"},
                    {"n": "精品推荐", "v": "371"},
                    {"n": "国产情色", "v": "372"},
                    {"n": "亚洲无码", "v": "373"},
                    {"n": "亚洲有码", "v": "374"},
                    {"n": "中文字幕", "v": "375"},
                    {"n": "强*乱伦", "v": "376"},
                    {"n": "欧美精品", "v": "377"},
                    {"n": "萝莉少女", "v": "378"}
                ]}
            ],
            "329": [
                {"key": "sub", "name": "子分类", "value": [
                    {"n": "全部", "v": "329"},
                    {"n": "日本有码", "v": "330"},
                    {"n": "无码中文", "v": "331"},
                    {"n": "有码中文", "v": "332"},
                    {"n": "日本无码", "v": "333"},
                    {"n": "国产视频", "v": "334"},
                    {"n": "欧美高清", "v": "335"},
                    {"n": "动漫剧情", "v": "336"}
                ]}
            ]
        }

    def init(self, extend=""):
        self.extend = extend or ""

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        # 添加 ?do=py 参数，与新人专属.py 保持一致
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def _fetch_html(self, url):
        try:
            res = self.fetch(url, headers=self.headers, timeout=15)
            if res is None:
                return ""
            if hasattr(res, "text") and res.text:
                return res.text
            if hasattr(res, "content") and res.content:
                try:
                    return res.content.decode('utf-8', errors='ignore')
                except Exception:
                    pass
            if hasattr(res, "body") and res.body:
                if isinstance(res.body, bytes):
                    return res.body.decode('utf-8', errors='ignore')
                return str(res.body)
            if isinstance(res, str):
                return res
            return ""
        except Exception:
            return ""

    def _fix_url(self, url):
        if not url:
            return ''
        url = url.strip()
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host.rstrip('/') + url
        return self.host.rstrip('/') + '/' + url.lstrip('/')

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch_html(self.host + "/")
        items = self._parse_list(html)
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        actual_tid = tid
        if extend:
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except:
                    extend = {}
            if isinstance(extend, dict) and extend.get("sub"):
                actual_tid = extend["sub"]
        page = pg or "1"
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
        if isinstance(ids, list):
            vid = str(ids[0])
        else:
            vid = str(ids)
        url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        html = self._fetch_html(url)
        return self._parse_detail(html, vid)

    def searchContent(self, key, quick, pg="1"):
        if not key or key.strip() == "":
            return {"list": [], "page": 1}
        page = pg or "1"
        url = f"{self.host}/index.php/vod/search/wd/{urllib.parse.quote(key)}/page/{page}.html"
        html = self._fetch_html(url)
        items = self._parse_list(html)
        return {"list": items, "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        if id.startswith("http"):
            play_url = id
        else:
            parts = id.split("|")
            if len(parts) >= 3:
                vid, sid, nid = parts[0], parts[1], parts[2]
                play_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html"
            else:
                play_url = id

        html = self._fetch_html(play_url)
        if html:
            match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
            if match:
                m3u8_url = match.group(1).replace("\\/", "/")
                return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": self.headers}
            match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
            if match:
                m3u8_url = match.group(0).replace("\\/", "/")
                return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": self.headers}

        return {"parse": 1, "url": play_url, "header": self.headers}

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤"""
        target = urllib.parse.unquote(str((param or {}).get("url") or (param or {}).get("source") or ""))
        if not target:
            return [400, "text/plain", b"invalid url"]
        try:
            res = self.fetch(target, headers={"User-Agent": self.headers["User-Agent"]}, timeout=15)
            if not res:
                return [502, "text/plain", b"fetch failed"]
            content = getattr(res, "content", b"") or b""
            if not content:
                return [502, "text/plain", b"empty content"]
            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            return [500, "text/plain", str(e).encode()]

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urllib.parse.urlparse(source_url)
        source_path = parsed.path
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
                media = urllib.parse.urljoin(source_url, line)
                if content_root and content_root not in urllib.parse.urlparse(media).path:
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
        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                return 'URI="' + urllib.parse.urljoin(source_url, match.group(1)) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            return urllib.parse.urljoin(source_url, line)
        return line

    def _parse_list(self, html):
        items = []
        if not html:
            return items
        pattern = r'<li[^>]*class="[^"]*content-item[^"]*"[^>]*>(.*?)</li>'
        li_matches = re.findall(pattern, html, re.DOTALL)
        for li in li_matches:
            link_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', li)
            if not link_match:
                continue
            link = link_match.group(1)
            title_match = re.search(r'<a[^>]*title="([^"]*)"', li)
            title = title_match.group(1) if title_match else ""
            img_match = re.search(r'<img[^>]*data-original="([^"]+)"', li)
            if not img_match:
                img_match = re.search(r'<img[^>]*src="([^"]+)"', li)
            pic = img_match.group(1) if img_match else ""
            note_match = re.search(r'<span[^>]*class="[^"]*note[^"]*"[^>]*>([^<]*)</span>', li)
            remark = note_match.group(1) if note_match else ""
            vid_match = re.search(r'/vod/detail/id/(\d+)\.html', link)
            vid = vid_match.group(1) if vid_match else link
            if title:
                items.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": remark.strip()
                })
        return items

    def _parse_detail(self, html, vid):
        if not html:
            return {"list": []}

        title_match = re.search(r'<h5[^>]*class="[^"]*title[^"]*"[^>]*>名称：([^<]*)</h5>', html)
        title = title_match.group(1).strip() if title_match else ""

        img_match = re.search(r'<img[^>]*class="[^"]*img-responsive[^"]*"[^>]*src="([^"]+)"', html)
        pic = img_match.group(1) if img_match else ""

        class_match = re.search(r'<h5[^>]*class="[^"]*title[^"]*"[^>]*>类别：([^<]*)</h5>', html)
        remark = class_match.group(1).strip() if class_match else ""

        content_match = re.search(r'<div[^>]*class="[^"]*vod_content[^"]*"[^>]*>([^<]*)</div>', html)
        content = content_match.group(1).strip() if content_match else ""

        play_from = []
        play_url = []

        line_matches = re.findall(r'<div[^>]*class="[^"]*ap-player-heading[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        line_names = []
        for lm in line_matches:
            strong_match = re.search(r'<strong>(.*?)</strong>', lm)
            if strong_match:
                line_names.append(strong_match.group(1).strip())
            else:
                text = re.sub(r'<[^>]+>', '', lm).strip()
                if text:
                    line_names.append(text)

        list_matches = re.findall(r'<ul[^>]*class="[^"]*ap-player-list[^"]*"[^>]*>(.*?)</ul>', html, re.DOTALL)
        for idx, ul in enumerate(list_matches):
            line_name = line_names[idx] if idx < len(line_names) else f"线路{idx+1}"
            items = re.findall(r'<li[^>]*class="[^"]*ap-player-item[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', ul, re.DOTALL)
            if items:
                eps = []
                for href, name in items:
                    name_clean = re.sub(r'<[^>]+>', '', name).strip()
                    eps.append(f"{name_clean}${href}")
                if eps:
                    play_from.append(line_name)
                    play_url.append("#".join(eps))

        if not play_from:
            btn_match = re.search(r'<a[^>]*href="([^"]*vod/play[^"]*)"[^>]*>立即播放</a>', html)
            if btn_match:
                play_url_raw = self._fix_url(btn_match.group(1))
                sid_match = re.search(r'sid/(\d+)', play_url_raw)
                nid_match = re.search(r'nid/(\d+)', play_url_raw)
                sid = sid_match.group(1) if sid_match else "1"
                nid = nid_match.group(1) if nid_match else "1"
                play_from.append("默认线路")
                play_url.append(f"第1集${vid}|{sid}|{nid}")

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
                "vod_content": content,
                "vod_play_from": "$$$".join(play_from) if play_from else "",
                "vod_play_url": "$$$".join(play_url) if play_url else ""
            }]
        }

    def _get_pagecount(self, html):
        if not html:
            return 1
        last_match = re.search(r'<a[^>]*href="[^"]*page/(\d+)[^"]*"[^>]*>尾页</a>', html)
        if last_match:
            try:
                return int(last_match.group(1))
            except:
                pass
        matches = re.findall(r'<a[^>]*href="[^"]*page/(\d+)[^"]*"[^>]*>(\d+)</a>', html)
        max_page = 1
        for href, num in matches:
            try:
                p = int(num)
                if p > max_page:
                    max_page = p
            except:
                pass
        return max_page

    def destroy(self):
        pass