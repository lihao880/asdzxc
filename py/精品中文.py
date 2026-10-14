# coding: utf-8
"""
精品中文 TVBox 爬虫
站点类型: MacCMS 标准站
主域名: https://dxddcdjic.cfd
分类: 视频一区(id=1), 视频二区(id=2), 视频三区(id=3)
子分类:
  视频一区: 日本无码(6), 日韩视频(7), 中文字幕(8), 人妻熟女(9), 强奸伦乱(10), 欧美极品(11)
  视频二区: 偷拍自拍(13), 三级伦理(14), 人妖视频(15), 国产高清(12)
  视频三区: 网红黑料(17), 另类变态(18), AV解说(4), 动漫精品(16)
播放: m3u8 直链，无加密
"""
import re
import json
import urllib.request
import urllib.parse
from urllib.parse import urljoin, quote, unquote


class Spider:
    """TVBox/FongMi 爬虫"""

    def __init__(self):
        self.host = "https://dxddcdjic.cfd"
        self.site_url = self.host
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "1", "type_name": "视频一区"},
            {"type_id": "2", "type_name": "视频二区"},
            {"type_id": "3", "type_name": "视频三区"},
        ]
        # 筛选条件 - 每个大区包含对应的子分类
        self.filters = {
            "1": [
                {"key": "cate_id", "name": "子分类", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "日本无码", "v": "6"},
                    {"n": "日韩视频", "v": "7"},
                    {"n": "中文字幕", "v": "8"},
                    {"n": "人妻熟女", "v": "9"},
                    {"n": "强奸伦乱", "v": "10"},
                    {"n": "欧美极品", "v": "11"}
                ]},
                {"key": "by", "name": "排序", "value": [
                    {"n": "默认", "v": ""},
                    {"n": "最新", "v": "time"}
                ]}
            ],
            "2": [
                {"key": "cate_id", "name": "子分类", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "偷拍自拍", "v": "13"},
                    {"n": "三级伦理", "v": "14"},
                    {"n": "人妖视频", "v": "15"},
                    {"n": "国产高清", "v": "12"}
                ]},
                {"key": "by", "name": "排序", "value": [
                    {"n": "默认", "v": ""},
                    {"n": "最新", "v": "time"}
                ]}
            ],
            "3": [
                {"key": "cate_id", "name": "子分类", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "网红黑料", "v": "17"},
                    {"n": "另类变态", "v": "18"},
                    {"n": "AV解说", "v": "4"},
                    {"n": "动漫精品", "v": "16"}
                ]},
                {"key": "by", "name": "排序", "value": [
                    {"n": "默认", "v": ""},
                    {"n": "最新", "v": "time"}
                ]}
            ]
        }

    def _fetch(self, url, data=None, headers=None, timeout=15):
        try:
            if data:
                data = urllib.parse.urlencode(data).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers or self.headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                return type("Response", (), {"status_code": resp.getcode(), "text": html, "content": html.encode("utf-8")})()
        except Exception as e:
            self.log(f"请求失败: {str(e)}")
            return None

    def getName(self):
        return "精品中文"

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self._get_category_content("1", "1", {})

    def _get_category_content(self, tid, pg, extend):
        try:
            page = int(pg) if pg else 1
            # 处理子分类筛选：从extend中提取cate_id
            sub_cate = ""
            if extend:
                if isinstance(extend, dict):
                    sub_cate = extend.get("cate_id", "")
                elif isinstance(extend, str):
                    match = re.search(r'cate_id[=:"]+(\d+)', extend)
                    if match:
                        sub_cate = match.group(1)
            # 如果有子分类筛选，使用子分类ID作为tid
            target_tid = sub_cate if sub_cate else tid
            url = f"{self.host}/index.php/vod/type/id/{target_tid}/page/{page}.html"
            resp = self._fetch(url, headers=self.headers)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

            html = resp.text
            items = []
            pattern = r'<li class="stui-vodlist__item">.*?<a[^>]*href="([^"]*)"[^>]*title="([^"]*)"[^>]*data-original="([^"]*)"[^>]*>.*?<span[^>]*>([^<]*)</span>'
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                href, title, pic, remark = match
                if href:
                    vod_id = href.replace("/index.php", "").strip("/")
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": title.strip(),
                        "vod_pic": pic.strip(),
                        "vod_remarks": remark.strip() or "HD",
                    })

            if not items:
                blocks = re.findall(r'<li class="stui-vodlist__item">(.*?)</li>', html, re.DOTALL)
                for block in blocks:
                    href_match = re.search(r'href="([^"]*)"', block)
                    title_match = re.search(r'title="([^"]*)"', block)
                    pic_match = re.search(r'data-original="([^"]*)"', block)
                    remark_match = re.search(r'<span[^>]*>([^<]*)</span>', block)
                    if href_match and title_match:
                        href = href_match.group(1)
                        vod_id = href.replace("/index.php", "").strip("/")
                        items.append({
                            "vod_id": vod_id,
                            "vod_name": title_match.group(1).strip(),
                            "vod_pic": pic_match.group(1) if pic_match else "",
                            "vod_remarks": remark_match.group(1) if remark_match else "HD",
                        })

            # 分页信息 - 从分页按钮提取总页数
            pagecount = 1
            page_links = re.findall(r'<li[^>]*><a[^>]*href="[^"]*page/(\d+)\.html"[^>]*>(\d+)</a></li>', html)
            if page_links:
                pages = [int(p[1]) for p in page_links if p[1].isdigit()]
                if pages:
                    pagecount = max(pages)
            if pagecount <= 1:
                last_match = re.search(r'尾页[^>]*href="[^"]*page/(\d+)\.html', html)
                if last_match:
                    pagecount = int(last_match.group(1)) or 1
            if pagecount <= 1:
                total_match = re.search(r'共(\d+)页', html)
                if total_match:
                    pagecount = int(total_match.group(1)) or 1

            return {
                "list": items,
                "page": page,
                "pagecount": pagecount,
                "limit": 20,
                "total": len(items) * pagecount
            }
        except Exception as e:
            self.log(f"分类获取失败: {str(e)}")
            return {"list": [], "page": int(pg) if pg else 1, "pagecount": 1, "limit": 20, "total": 0}

    def categoryContent(self, tid, pg, filter, extend):
        return self._get_category_content(tid, pg, extend)

    def detailContent(self, ids):
        try:
            if not ids or not ids[0]:
                return {"list": []}
            vod_id = ids[0]
            if "vod/detail/id/" in vod_id:
                vid = re.search(r"id/(\d+)", vod_id)
                if vid:
                    vid = vid.group(1)
                else:
                    vid = vod_id
            else:
                vid = vod_id

            url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
            resp = self._fetch(url, headers=self.headers)
            if not resp or resp.status_code != 200:
                return {"list": []}

            html = resp.text
            title = ""
            title_match = re.search(r'<h3 class="title">([^<]*)</h3>', html)
            if title_match:
                title = title_match.group(1).strip()

            pic = ""
            pic_match = re.search(r'data-original="([^"]*)"', html)
            if pic_match:
                pic = pic_match.group(1).strip()

            desc = ""
            desc_match = re.search(r'<div class="stui-content__desc[^>]*>(.*?)</div>', html, re.DOTALL)
            if desc_match:
                desc = desc_match.group(1).strip()

            play_from = "辣椒资源"
            play_url = ""

            playlist_section = re.search(r'<ul class="stui-content__playlist clearfix">(.*?)</ul>', html, re.DOTALL)
            if playlist_section:
                play_items = re.findall(r'<li[^>]*><a[^>]*href="([^"]*)"[^>]*>([^<]*)</a></li>', playlist_section.group(1))
                if play_items:
                    play_parts = []
                    from_parts = []
                    for href, name in play_items:
                        play_parts.append(f"{name.strip()}${href.strip()}")
                        from_parts.append("辣椒资源")
                    play_url = "$$$".join(play_parts)
                    play_from = "$$$".join(from_parts)

            if not play_url:
                player_match = re.search(r'var player_aaaa=({[^}]+})', html)
                if player_match:
                    try:
                        player_data = json.loads(player_match.group(1))
                        if player_data.get("url"):
                            play_url = f"直链${player_data['url']}"
                        elif player_data.get("link"):
                            play_url = f"在线播放${player_data['link']}"
                    except:
                        pass

            vod = {
                "vod_id": vod_id,
                "vod_name": title or "未知",
                "vod_pic": pic,
                "vod_content": desc or title,
                "vod_remarks": "HD",
                "vod_play_from": play_from,
                "vod_play_url": play_url or f"在线播放$ /index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            }
            return {"list": [vod]}
        except Exception as e:
            self.log(f"详情获取失败: {str(e)}")
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        """站点无搜索功能，直接返回空"""
        return {"list": [], "page": 1, "pagecount": 0}

    def playerContent(self, flag, id, vipFlags):
        try:
            if id.startswith("http") and (".m3u8" in id or ".mp4" in id):
                return {"parse": 0, "url": id, "header": {"User-Agent": self.headers["User-Agent"]}}

            if "/vod/play/" in id:
                url = self.host + (id if id.startswith("/") else "/" + id)
                resp = self._fetch(url, headers=self.headers)
                if resp and resp.status_code == 200:
                    html = resp.text
                    player_match = re.search(r'var player_aaaa=({[^}]+})', html)
                    if player_match:
                        try:
                            player_data = json.loads(player_match.group(1))
                            real_url = player_data.get("url", "")
                            if real_url:
                                if real_url.endswith(".m3u8"):
                                    return {"parse": 0, "url": self._m3u8_proxy_url(real_url), "header": {}}
                                return {"parse": 0, "url": real_url, "header": {"User-Agent": self.headers["User-Agent"]}}
                        except:
                            pass

                    iframe_match = re.search(r'<iframe[^>]*src="([^"]*)"', html)
                    if iframe_match:
                        iframe_url = iframe_match.group(1)
                        if not iframe_url.startswith("http"):
                            iframe_url = urljoin(self.host, iframe_url)
                        return {"parse": 1, "url": iframe_url, "header": self.headers}

            if id.startswith("/"):
                id = self.host + id

            return {"parse": 1, "url": id, "header": self.headers}
        except Exception as e:
            self.log(f"播放解析失败: {str(e)}")
            return {"parse": 1, "url": id, "header": self.headers}

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?url=" + quote(str(url), safe="")

    def localProxy(self, param):
        try:
            target = unquote(str(param.get("url", "") or ""))
            if not target.startswith("http"):
                return [400, "text/plain", b"invalid url"]

            resp = self._fetch(target, headers={"User-Agent": self.headers["User-Agent"]}, timeout=15)
            if not resp or resp.status_code != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]

            content = resp.content
            if not content:
                return [502, "text/plain", b"empty response"]

            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log(f"m3u8代理失败: {str(e)}")
            return [500, "text/plain", b"m3u8 proxy error"]

    def _clean_m3u8(self, text, source_url):
        lines = [line.strip() for line in text.replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        source_parts = [p for p in source_url.split("/") if p]
        content_root = "/" + "/".join(source_parts[:2]) + "/" if len(source_parts) >= 2 else ""

        out = []
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
                if content_root and content_root not in media:
                    removed += 1
                else:
                    out.extend(pending)
                    out.append(media)
                pending = []
                continue
            out.append(self._rewrite_m3u8_tag(line, source_url))

        final_out = []
        for line in out:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if final_out and final_out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            final_out.append(line)

        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个")

        return "\n".join(final_out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                return 'URI="' + urljoin(source_url, match.group(1)) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            return urljoin(source_url, line)
        return line

    def siteInfo(self):
        return {
            "name": "精品中文",
            "host": self.host,
            "type": "影视",
            "description": "MacCMS标准站，3大区+14子分类，m3u8直链播放"
        }

    def log(self, msg):
        print(f"[精品中文] {msg}")