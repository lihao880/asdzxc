# coding: utf-8
import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://zzd.xmbn5.homes"
        self.base_path = "/cn/home/web"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + self.base_path + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.classes = [
            {"type_id": "20", "type_name": "国产视频"},
            {"type_id": "21", "type_name": "日韩有码"},
            {"type_id": "22", "type_name": "日韩无码"},
            {"type_id": "23", "type_name": "制服学生"},
            {"type_id": "24", "type_name": "动漫卡通"},
            {"type_id": "25", "type_name": "欧美变态"},
            {"type_id": "26", "type_name": "三级伦理"},
        ]
        self.filters = {k: [] for k in ["20", "21", "22", "23", "24", "25", "26"]}

    def getName(self):
        return "小妹爆奶"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 从首页提取推荐视频
        url = self.host + self.base_path + "/"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            items = []
            # 匹配本周热播和本月热播中的视频列表
            pattern = r'<li class="stui-vodlist__item">.*?<a[^>]*href="([^"]+)"[^>]*title="([^"]+)"[^>]*data-original="([^"]+)"[^>]*>.*?<span class="pic-text[^>]*>([^<]*)</span>'
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches[:20]:
                link, title, pic, remark = match
                vod_id = self._extract_vod_id(link)
                if vod_id:
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": remark.strip() or "最新",
                    })
            return {"list": items}
        except Exception as e:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = self.host + self.base_path + f"/index.php/vod/show/id/{tid}/page/{page}.html"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = resp.text
            items = []
            pattern = r'<li class="stui-vodlist__item">.*?<a[^>]*href="([^"]+)"[^>]*title="([^"]+)"[^>]*data-original="([^"]+)"[^>]*>.*?<span class="pic-text[^>]*>([^<]*)</span>'
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                link, title, pic, remark = match
                vod_id = self._extract_vod_id(link)
                if vod_id:
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": remark.strip() or "最新",
                    })
            # 提取总页数 - 从"尾页"链接中提取
            pagecount = 100  # 默认值
            # 方法1: 匹配 "尾页" 链接中的页码
            last_match = re.search(r'尾页[^<]*<a[^>]*href="[^"]*page/(\d+)\.html"', html)
            if last_match:
                pagecount = int(last_match.group(1))
            else:
                # 方法2: 匹配 "尾页" 链接
                last_match2 = re.search(r'<a[^>]*href="[^"]*page/(\d+)\.html"[^>]*>尾页</a>', html)
                if last_match2:
                    pagecount = int(last_match2.group(1))
                else:
                    # 方法3: 匹配分页导航中最大的数字
                    page_nums = re.findall(r'<a[^>]*href="[^"]*page/(\d+)\.html"[^>]*>(\d+)</a>', html)
                    if page_nums:
                        max_page = max(int(num) for _, num in page_nums)
                        pagecount = max_page if max_page > pagecount else pagecount
            return {
                "list": items,
                "page": int(page),
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20,
            }
        except Exception as e:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = self.host + self.base_path + f"/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            # 提取标题
            title_match = re.search(r'<h4[^>]*class="title"[^>]*>([^<]+)</h4>', html)
            title = title_match.group(1).strip() if title_match else "未知"
            # 提取封面
            pic_match = re.search(r'<a[^>]*class="stui-vodlist__thumb[^"]*"[^>]*data-original="([^"]+)"', html)
            pic = pic_match.group(1) if pic_match else ""
            # 提取播放地址
            player_data_match = re.search(r'var player_data=({[^}]+})', html)
            play_url = ""
            if player_data_match:
                try:
                    data = json.loads(player_data_match.group(1))
                    play_url = data.get("url", "")
                except:
                    pass
            # 提取选集列表
            playlist = []
            playlist_pattern = r'<li[^>]*class="[^"]*active[^"]*"[^>]*>.*?<a[^>]*href="[^"]+"[^>]*>([^<]+)</a>'
            playlist_matches = re.findall(playlist_pattern, html, re.DOTALL)
            if not playlist_matches:
                # 尝试匹配所有li
                li_pattern = r'<li[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
                li_matches = re.findall(li_pattern, html, re.DOTALL)
                for href, name in li_matches:
                    if "sid" in href and "nid" in href:
                        playlist.append(name.strip())
            if not playlist_matches and not playlist:
                playlist = ["第1集"]
            # 构建vod_play_url
            if play_url:
                # 直接使用m3u8直链
                vod_play_url = "第1集$" + play_url
                vod_play_from = "直链"
            else:
                # 如果没有m3u8，使用播放页地址
                vod_play_url = "第1集$" + url
                vod_play_from = "播放页"
            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "最新",
                "vod_content": "",
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url,
            }
            return {"list": [vod]}
        except Exception as e:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        url = self.host + self.base_path + f"/index.php/vod/search.html?wd={urllib.parse.quote(key)}"
        if str(pg) != "1":
            url += f"&pg={pg}"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": int(pg)}
            html = resp.text
            items = []
            pattern = r'<li class="stui-vodlist__item">.*?<a[^>]*href="([^"]+)"[^>]*title="([^"]+)"[^>]*data-original="([^"]+)"[^>]*>.*?<span class="pic-text[^>]*>([^<]*)</span>'
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                link, title, pic, remark = match
                vod_id = self._extract_vod_id(link)
                if vod_id:
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": remark.strip() or "最新",
                    })
            return {"list": items, "page": int(pg)}
        except Exception as e:
            return {"list": [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        play_url = str(id).strip()
        # 如果是播放页URL，尝试提取m3u8
        if "vod/play/id/" in play_url:
            try:
                resp = self.fetch(play_url, headers=self.headers, timeout=15)
                if resp and resp.status_code == 200:
                    player_data_match = re.search(r'var player_data=({[^}]+})', resp.text)
                    if player_data_match:
                        try:
                            data = json.loads(player_data_match.group(1))
                            m3u8_url = data.get("url", "")
                            if m3u8_url and ".m3u8" in m3u8_url:
                                return {
                                    "parse": 0,
                                    "url": self._m3u8_proxy_url(m3u8_url),
                                    "header": self.headers,
                                }
                        except:
                            pass
            except:
                pass
            return {"parse": 1, "url": play_url, "header": self.headers}
        # 直接m3u8
        if ".m3u8" in play_url:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(play_url),
                "header": self.headers,
            }
        # 其他情况
        return {"parse": 0, "url": play_url, "header": self.headers}

    def _m3u8_proxy_url(self, url):
        proxy_url = self.getProxyUrl()
        if "?" in proxy_url:
            return proxy_url + "&url=" + urllib.parse.quote(str(url or ""), safe="")
        return proxy_url + "?url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        target = ""
        if isinstance(param, dict):
            target = param.get("url", "") or param.get("source", "")
        elif isinstance(param, str):
            target = param
        if target and target.startswith("url="):
            target = target[4:]
        if target and "url=" in target:
            parsed = urllib.parse.urlparse(target)
            qs = urllib.parse.parse_qs(parsed.query)
            if "url" in qs:
                target = qs["url"][0]
        target = urllib.parse.unquote(str(target or ""))
        if not target or not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]
        try:
            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp:
                return [502, "text/plain", b"fetch failed"]
            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]
            if b"#EXTM3U" in content[:256]:
                text = content.decode("utf-8", errors="ignore")
                cleaned = self._clean_m3u8(text, target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            content_type = "application/octet-stream"
            if target.endswith(".ts"):
                content_type = "video/mp2t"
            elif target.endswith(".m3u8"):
                content_type = "application/vnd.apple.mpegurl"
            elif target.endswith(".jpg") or target.endswith(".png"):
                content_type = "image/jpeg"
            elif target.endswith(".mp4"):
                content_type = "video/mp4"
            return [200, content_type, content]
        except Exception as e:
            return [500, "text/plain", str(e).encode("utf-8", errors="ignore")]

    def _clean_m3u8(self, text, source_url):
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"
        # 检查是否多码率
        is_multi = any(line.startswith("#EXT-X-STREAM-INF") for line in lines)
        if is_multi:
            return self._clean_m3u8_multi(lines, source_url)
        return self._clean_m3u8_single(lines, source_url)

    def _clean_m3u8_multi(self, lines, source_url):
        out = []
        for line in lines:
            if line.startswith("#"):
                out.append(line)
            else:
                child_url = urllib.parse.urljoin(source_url, line)
                out.append(self._m3u8_proxy_url(child_url))
        return "\n".join(out) + "\n"

    def _clean_m3u8_single(self, lines, source_url):
        parsed = urllib.parse.urlparse(source_url)
        dir_path = parsed.path[:parsed.path.rfind('/')+1] if '/' in parsed.path else "/"

        def is_valid_segment(url):
            parsed_url = urllib.parse.urlparse(url)
            return parsed_url.path.startswith(dir_path)

        result = []
        pending_extinf = []
        removed = 0
        kept = 0
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                line = self._rewrite_m3u8_tag(line, source_url)
                result.append(line)
                i += 1
                continue
            if line.startswith("#EXTINF"):
                pending_extinf = [line]
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.startswith("#"):
                        pending_extinf.append(next_line)
                        i += 1
                    else:
                        media_url = urllib.parse.urljoin(source_url, next_line)
                        if is_valid_segment(media_url):
                            if media_url.endswith('.jpg'):
                                media_url = media_url[:-4] + '.ts'
                            result.extend(pending_extinf)
                            result.append(media_url)
                            kept += 1
                        else:
                            removed += 1
                        i += 1
                        break
                continue
            result.append(line)
            i += 1
        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")
        return "\n".join(result) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
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

    def _extract_vod_id(self, link):
        match = re.search(r'/play/id/(\d+)/', link)
        return match.group(1) if match else None

    def destroy(self):
        pass