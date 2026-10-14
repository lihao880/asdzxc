# coding: utf-8
# 人妻档案网 影视爬虫 - MacCMS 标准站
# 站点: https://3_4s_ht_u.rqdaw2.sbs/

import re
import json
import urllib.parse
import posixpath
from urllib.parse import quote, urlencode

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://3_4s_ht_u.rqdaw2.sbs"
        self.site_name = "人妻档案网"
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
                        {"n": "精品视频", "v": "121"},
                        {"n": "国产色情", "v": "122"},
                        {"n": "主播直播", "v": "123"},
                        {"n": "亚洲无码", "v": "124"},
                        {"n": "中文字幕", "v": "125"},
                        {"n": "巨乳美乳", "v": "126"},
                        {"n": "人妻少妇", "v": "127"},
                        {"n": "强奸乱伦", "v": "128"}
                    ]
                }
            ],
            "118": [
                {
                    "key": "tid",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": "118"},
                        {"n": "欧美大片", "v": "129"},
                        {"n": "粉嫩萝莉", "v": "130"},
                        {"n": "精品动漫", "v": "131"},
                        {"n": "自拍偷拍", "v": "132"},
                        {"n": "丝袜美腿", "v": "133"},
                        {"n": "口交颜射", "v": "134"},
                        {"n": "日本精品", "v": "135"},
                        {"n": "Cosplay", "v": "136"}
                    ]
                }
            ],
            "119": [
                {
                    "key": "tid",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": "119"},
                        {"n": "超级辣妹", "v": "137"},
                        {"n": "极品御姐", "v": "138"},
                        {"n": "唯美港姐", "v": "139"},
                        {"n": "东南亚AV", "v": "140"},
                        {"n": "剧情介绍", "v": "141"},
                        {"n": "多人乱交", "v": "142"},
                        {"n": "91探花", "v": "143"},
                        {"n": "网红流出", "v": "144"}
                    ]
                }
            ],
            "120": [
                {
                    "key": "tid",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": "120"},
                        {"n": "野外车震", "v": "145"},
                        {"n": "古装扮演", "v": "146"},
                        {"n": "女优系列", "v": "147"},
                        {"n": "可爱学生", "v": "148"},
                        {"n": "必射视频", "v": "149"},
                        {"n": "瑜伽裤", "v": "150"},
                        {"n": "闷骚护士", "v": "151"},
                        {"n": "女同性恋", "v": "152"}
                    ]
                }
            ]
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }
        self.log("人妻档案网 __init__ 完成")

    def getName(self):
        return "人妻档案网"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""
        self.log(f"init called, extend={extend}")

    def homeContent(self, filter):
        self.log(f"homeContent called, filter={filter}")
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        self.log("homeVideoContent start")
        html = self._fetch_html(self.host + "/")
        items = self._parse_video_list(html)
        self.log(f"homeVideoContent 返回 {len(items)} 条")
        return {"list": items[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg) if pg else "1"
        real_tid = tid
        if extend:
            if isinstance(extend, dict):
                real_tid = extend.get("tid", tid)
            elif isinstance(extend, str):
                try:
                    ext_dict = json.loads(extend)
                    real_tid = ext_dict.get("tid", tid)
                except:
                    for part in extend.split(','):
                        if '=' in part:
                            k, v = part.split('=', 1)
                            if k.strip() == 'tid':
                                real_tid = v.strip()
                                break
        self.log(f"categoryContent tid={tid}, real_tid={real_tid}, pg={page}, extend={extend}")
        url = f"{self.host}/vodtype/{real_tid}-{page}.html"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        page_count = self._parse_page_count(html)
        total = page_count * 20
        return {
            "list": items,
            "page": int(page),
            "pagecount": page_count,
            "limit": 20,
            "total": total,
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        if isinstance(ids, list):
            vid = str(ids[0])
        else:
            vid = str(ids)
        self.log(f"detailContent ids={ids}, vid={vid}")

        detail_url = f"{self.host}/vodplay/{vid}-1-1.html"
        html = self._fetch_html(detail_url)
        play_url = self._extract_m3u8_from_html(html)

        title = f"视频{vid}"
        if html:
            title_match = re.search(r'<p class="group-title[^"]*"[^>]*>([^<]+)</p>', html)
            if title_match:
                title = title_match.group(1).strip()

        if play_url:
            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}",
            }
        else:
            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${detail_url}",
            }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = str(pg) if pg else "1"
        self.log(f"searchContent key={key}, pg={page}")
        url = f"{self.host}/vodsearch/-------------.html?wd={quote(key)}"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        return {"list": items, "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        self.log(f"playerContent flag={flag}, id={id[:60] if id else 'none'}")
        if id and id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(id),
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        if id and id.startswith("http"):
            html = self._fetch_html(id)
            play_url = self._extract_m3u8_from_html(html)
            if play_url:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(play_url),
                    "header": {"User-Agent": self.headers.get("User-Agent", "")}
                }
            return {"parse": 1, "url": id, "header": self.headers}
        return {"parse": 1, "url": id, "header": self.headers}

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ""))

            self.log(f"localProxy target={target[:60] if target else 'none'}")

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            resp = self.fetch(target, headers=self.headers, timeout=15, verify=False)
            if not resp:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")

            if not content:
                return [502, "text/plain", b"empty content"]

            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            cleaned = self._clean_m3u8(text, target)
            self.log(f"localProxy 清理完成, 原始长度={len(text)}, 清理后={len(cleaned)}")
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            self.log(f"localProxy error: {str(e)}")
            return [500, "text/plain", error_msg]

    def _clean_m3u8(self, text, source_url):
        """清洗m3u8 - 过滤广告分片"""
        import posixpath
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
                    if ".m3u8" in child.lower():
                        out.append(self._m3u8_proxy_url(child))
                    else:
                        out.append(child)
            return "\n".join(out) + "\n"

        parsed = urllib.parse.urlparse(source_url)
        # 使用主 m3u8 的路径作为正片目录基准
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

        self.log(f"正片目录基准: {source_dir}")

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
                media_url = urllib.parse.urljoin(source_url, line)
                media_parsed = urllib.parse.urlparse(media_url)
                # 判断分片路径是否以 source_dir 开头（正片目录）
                is_ad = not media_parsed.path.startswith(source_dir)
                if is_ad:
                    removed += 1
                    self.log(f"过滤广告分片: {media_url}")
                    pending = []
                    continue
                segments.extend(pending)
                segments.append(media_url)
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urllib.parse.urljoin(source_url, line))
            else:
                segments.append(line)

        # 清理孤立标记
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        if removed:
            self.log(f"m3u8已过滤广告分片: {removed} 个")
        return "\n".join(out) + "\n"
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

    def _fetch_html(self, url, params=None):
        full_url = url
        if params:
            if "?" in url:
                full_url = url + "&" + urlencode(params)
            else:
                full_url = url + "?" + urlencode(params)
        try:
            resp = self.fetch(full_url, headers=self.headers, timeout=15, verify=False)
            if resp and hasattr(resp, "status_code") and resp.status_code == 200:
                return resp.text
            if resp and hasattr(resp, "text"):
                return resp.text
        except Exception as e:
            self.log(f"_fetch_html error: {str(e)}")
        return ""

    def _parse_video_list(self, html):
        items = []
        if not html:
            return items
        pattern = r'<a href="(/vodplay/(\d+)-1-1\.html)" class="group-item[^"]*">.*?<img[^>]*src="([^"]+)"[^>]*>.*?<p>([^<]+)</p>'
        matches = re.findall(pattern, html, re.DOTALL)
        for url, vid, pic, title in matches:
            if vid:
                items.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return items

    def _parse_page_count(self, html):
        if not html:
            return 1
        total_match = re.search(r'共(\d+)条', html)
        if total_match:
            total = int(total_match.group(1))
            return (total + 19) // 20 if total > 0 else 1
        return 1

    def _extract_m3u8_from_html(self, html):
        if not html:
            return None
        pattern = r'var\s+player_aaaa\s*=\s*(\{[^;]+\});'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                url = data.get("url", "")
                if url and url.startswith("http"):
                    return url.replace("\\/", "/")
            except:
                pass
        pattern2 = r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"'
        match2 = re.search(pattern2, html)
        if match2:
            url = match2.group(1)
            if url and url.startswith("http"):
                return url.replace("\\/", "/")
        pattern3 = r'https?://[^"\']+\.m3u8[^"\']*'
        match3 = re.search(pattern3, html)
        if match3:
            return match3.group(0)
        return None

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        self.log("destroy called")