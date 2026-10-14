# -*- coding: utf-8 -*-
"""
站点名称: 抖阴小视频
域名: dyxsp1.sbs
CMS类型: MacCMS v8/v10
数据来源: HTML解析
播放来源: player_aaaa.url 直出 m3u8
"""
import re
import json
import urllib.parse
import posixpath


class Spider:
    def __init__(self):
        self.host = "https://dyxsp1.sbs"
        self.classes = [
            {"type_id": "117", "type_name": "视频一区"},
            {"type_id": "118", "type_name": "视频二区"},
            {"type_id": "119", "type_name": "视频三区"},
            {"type_id": "120", "type_name": "视频四区"}
        ]
        self.filters = {
            "117": [
                {
                    "key": "tid",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": "117"},
                        {"n": "女优系列", "v": "121"},
                        {"n": "清纯学妹", "v": "122"},
                        {"n": "人兽乱交", "v": "123"},
                        {"n": "瑜伽裤", "v": "124"},
                        {"n": "闷骚护士", "v": "125"},
                        {"n": "网曝门", "v": "126"},
                        {"n": "传媒出品", "v": "127"},
                        {"n": "清纯辣妹", "v": "128"}
                    ]
                }
            ],
            "118": [
                {
                    "key": "tid",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": "118"},
                        {"n": "御姐系列", "v": "129"},
                        {"n": "唯美港姐", "v": "131"},
                        {"n": "东南亚乱交", "v": "132"},
                        {"n": "剧情介绍", "v": "133"},
                        {"n": "多人多P", "v": "134"},
                        {"n": "91探花", "v": "135"},
                        {"n": "网红流出", "v": "136"},
                        {"n": "户外流出", "v": "137"}
                    ]
                }
            ],
            "119": [
                {
                    "key": "tid",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": "119"},
                        {"n": "欧美大片", "v": "138"},
                        {"n": "萝莉少女", "v": "139"},
                        {"n": "伦理影片", "v": "140"},
                        {"n": "成人动漫", "v": "141"},
                        {"n": "自拍偷拍", "v": "142"},
                        {"n": "丝袜制服", "v": "143"},
                        {"n": "口交颜射", "v": "144"},
                        {"n": "日本精品", "v": "145"}
                    ]
                }
            ],
            "120": [
                {
                    "key": "tid",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": "120"},
                        {"n": "Cosplay", "v": "146"},
                        {"n": "国产色情", "v": "147"},
                        {"n": "美女主播", "v": "148"},
                        {"n": "亚洲无码", "v": "149"},
                        {"n": "中文字幕", "v": "150"},
                        {"n": "强奸乱伦", "v": "151"},
                        {"n": "男同性恋", "v": "152"},
                        {"n": "女同性恋", "v": "153"}
                    ]
                }
            ]
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://dyxsp1.sbs/"
        }

    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def _fetch_html(self, url):
        """获取页面HTML"""
        try:
            if hasattr(self, 'get'):
                resp = self.get(url, headers=self.headers)
                if resp:
                    if isinstance(resp, str):
                        return resp
                    if hasattr(resp, 'text'):
                        return resp.text
                    if hasattr(resp, 'content'):
                        return resp.content.decode('utf-8', errors='ignore')
            if hasattr(self, 'fetch'):
                resp = self.fetch(url, headers=self.headers)
                if resp:
                    if isinstance(resp, str):
                        return resp
                    if hasattr(resp, 'text'):
                        return resp.text
                    if hasattr(resp, 'content'):
                        return resp.content.decode('utf-8', errors='ignore')
        except:
            pass

        try:
            import requests
            resp = requests.get(url, headers=self.headers, timeout=30)
            resp.encoding = "utf-8"
            return resp.text
        except:
            return ""

    def _parse_player_data(self, html):
        """从HTML中解析 player_aaaa 数据"""
        if not html:
            return None
        patterns = [
            r'var player_aaaa\s*=\s*({[^;]+});',
            r'player_aaaa\s*=\s*({[^;]+});',
            r'player_aaaa=({[^;]+})',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except:
                    continue
        return None

    def _extend_to_tid(self, extend, default_tid):
        """从 extend 中提取 tid（用于子分类筛选）"""
        if not extend:
            return default_tid
        if isinstance(extend, dict):
            return extend.get("tid", default_tid)
        if isinstance(extend, str):
            try:
                data = json.loads(extend)
                return data.get("tid", default_tid)
            except:
                for part in extend.split(','):
                    if '=' in part:
                        k, v = part.split('=', 1)
                        if k.strip() == 'tid':
                            return v.strip()
        return default_tid

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8，过滤广告分片"""
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
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urllib.parse.urlparse(source_url)
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
                media_url = urllib.parse.urljoin(source_url, line)
                media_parsed = urllib.parse.urlparse(media_url)

                is_ad = not media_parsed.path.startswith(main_dir)

                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urllib.parse.urljoin(source_url, line))
            else:
                segments.append(line)

        # 二次清洗
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
        """重写相对路径标签"""
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urllib.parse.urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)

        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urllib.parse.urljoin(source_url, line)

        return line

    def homeVideoContent(self):
        result = []
        try:
            html = self._fetch_html(self.host + "/")
            if not html:
                return {"list": []}

            pattern = r'<div class="appel clearfix">\s*<div class="appel-main">\s*<div class="appel-heading clearfix">\s*<h3 class="appel-title">最近更新</h3>'
            match = re.search(pattern, html)
            if match:
                start = match.start()
                end = html.find('<div class="appel clearfix">', start + 1)
                if end == -1:
                    end = len(html)
                section = html[start:end]
            else:
                section = html

            li_pattern = r'<li>\s*<a class="thumbnail" href="([^"]+)"[^>]*><img src="([^"]+)"[^>]*></a>\s*<div class="video-info">\s*<h5><a href="([^"]+)"[^>]*>([^<]+)</a></h5>\s*<p>([^<]*)</p>'
            for match in re.finditer(li_pattern, section):
                img_url = match.group(2)
                detail_url = match.group(3)
                title = match.group(4).strip()
                remark = match.group(5).strip()
                vod_id = detail_url.replace("/voddetail/", "").replace(".html", "")
                result.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": img_url,
                    "vod_remarks": remark
                })
                if len(result) >= 20:
                    break
        except Exception as e:
            pass

        return {"list": result}

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        try:
            actual_tid = self._extend_to_tid(extend, tid)
            pg = pg or "1"
            url = self.host + f"/vodtype/{actual_tid}-{pg}.html"
            if pg == "1":
                url = self.host + f"/vodtype/{actual_tid}.html"
            html = self._fetch_html(url)
            if not html:
                return result

            total_match = re.search(r'共(\d+)条数据,当前(\d+)/(\d+)页', html)
            if total_match:
                total = int(total_match.group(1))
                result["total"] = total
                result["pagecount"] = int(total_match.group(3))
                result["page"] = int(total_match.group(2))

            li_pattern = r'<li>\s*<a class="thumbnail" href="([^"]+)"[^>]*><img src="([^"]+)"[^>]*></a>\s*<div class="video-info">\s*<h5><a href="([^"]+)"[^>]*>([^<]+)</a></h5>\s*<p>([^<]*)</p>'
            for match in re.finditer(li_pattern, html):
                img_url = match.group(2)
                detail_url = match.group(3)
                title = match.group(4).strip()
                remark = match.group(5).strip()
                vod_id = detail_url.replace("/voddetail/", "").replace(".html", "")
                result["list"].append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": img_url,
                    "vod_remarks": remark
                })
        except Exception as e:
            pass

        return result

    def detailContent(self, ids):
        result = {"list": []}
        try:
            if isinstance(ids, list):
                vod_id = str(ids[0])
            else:
                vod_id = str(ids)

            url = self.host + f"/vodplay/{vod_id}-1-1.html"
            html = self._fetch_html(url)
            if not html:
                return result

            player_data = self._parse_player_data(html)
            if player_data:
                vod_data = player_data.get("vod_data", {})
                vod_name = vod_data.get("vod_name", "")
                vod_class = vod_data.get("vod_class", "")
                from_source = player_data.get("from", "slm3u8")
                play_id = player_data.get("id", vod_id)

                img_match = re.search(r'<img[^>]+src="([^"]+)"[^>]+class="[^"]*thumbnail[^"]*"', html)
                vod_pic = img_match.group(1) if img_match else ""

                vod = {
                    "vod_id": str(play_id),
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_class": vod_class,
                    "vod_play_from": from_source,
                    "vod_play_url": f"正片${vod_id}"
                }
                result["list"].append(vod)
        except Exception as e:
            pass

        return result

    def searchContent(self, key, quick, pg="1"):
        result = {"list": [], "page": 1}
        try:
            import urllib.parse
            key_encoded = urllib.parse.quote(key)
            url = self.host + f"/vodsearch/{key_encoded}-------------.html"
            html = self._fetch_html(url)
            if not html:
                return result

            li_pattern = r'<li>\s*<a class="thumbnail" href="([^"]+)"[^>]*><img src="([^"]+)"[^>]*></a>\s*<div class="video-info">\s*<h5><a href="([^"]+)"[^>]*>([^<]+)</a></h5>\s*<p>([^<]*)</p>'
            for match in re.finditer(li_pattern, html):
                img_url = match.group(2)
                detail_url = match.group(3)
                title = match.group(4).strip()
                remark = match.group(5).strip()
                vod_id = detail_url.replace("/voddetail/", "").replace(".html", "")
                result["list"].append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": img_url,
                    "vod_remarks": remark
                })
                if len(result["list"]) >= 30:
                    break
        except Exception as e:
            pass

        return result

    def playerContent(self, flag, id, vipFlags):
        try:
            video_id = id
            if isinstance(id, str) and id.startswith("http"):
                return {"parse": 1, "url": id, "header": self.headers}

            url = self.host + f"/vodplay/{video_id}-1-1.html"
            html = self._fetch_html(url)
            if html:
                player_data = self._parse_player_data(html)
                if player_data:
                    play_url = player_data.get("url", "")
                    if play_url:
                        # 通过本地代理过滤广告
                        proxy_url = self._m3u8_proxy_url(play_url)
                        return {
                            "parse": 0,
                            "url": proxy_url,
                            "header": self.headers
                        }
        except Exception as e:
            pass

        return {"parse": 1, "url": self.host + f"/vodplay/{video_id}-1-1.html", "header": self.headers}

    def getName(self):
        return "抖阴小视频"

    def getDependence(self):
        return []

    def localProxy(self, param):
        """本地代理：过滤 m3u8 广告分片"""
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            # 获取 m3u8 内容
            if hasattr(self, 'fetch'):
                res = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=15)
            else:
                import requests
                res = requests.get(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=15)

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