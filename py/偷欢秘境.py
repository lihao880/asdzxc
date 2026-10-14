# coding: utf-8
# 站点: 偷欢秘境 (thmj)
# 域名: https://03val.thmj1.cyou (备用: 03val.thmj.pics)
# CMS: MacCMS
# 类型: 成人影视
import json
import re
import base64
from urllib.parse import quote, unquote, urljoin, urlparse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://03val.thmj1.cyou"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类列表 (从首页提取)
        self.classes = [
            {"type_id": "20", "type_name": "学生少女"},
            {"type_id": "21", "type_name": "技师风采"},
            {"type_id": "22", "type_name": "熟女少妇"},
            {"type_id": "23", "type_name": "国产热播"},
            {"type_id": "24", "type_name": "反差母狗"},
            {"type_id": "25", "type_name": "美脚丝足"},
            {"type_id": "26", "type_name": "情侣自拍"},
            {"type_id": "27", "type_name": "私房俱乐部"},
            {"type_id": "28", "type_name": "偷情约炮"},
            {"type_id": "29", "type_name": "真实偷拍"},
            {"type_id": "30", "type_name": "高潮喷水"},
            {"type_id": "31", "type_name": "强奸迷奸"},
            {"type_id": "32", "type_name": "户外露出"},
            {"type_id": "33", "type_name": "SM调教"},
            {"type_id": "34", "type_name": "情趣内衣"},
            {"type_id": "35", "type_name": "精选探花"},
            {"type_id": "36", "type_name": "网曝门事件"},
            {"type_id": "37", "type_name": "校园猛料"},
            {"type_id": "38", "type_name": "网红流出"},
            {"type_id": "39", "type_name": "明星黑料"},
            {"type_id": "40", "type_name": "裸贷肉偿"},
            {"type_id": "41", "type_name": "婚闹恶俗"},
            {"type_id": "42", "type_name": "抓奸名场面"},
            {"type_id": "43", "type_name": "男同女同"},
            {"type_id": "44", "type_name": "JK少女"},
            {"type_id": "45", "type_name": "黑丝白丝"},
            {"type_id": "46", "type_name": "女仆"},
            {"type_id": "47", "type_name": "cosplay"},
            {"type_id": "48", "type_name": "OL制服"},
            {"type_id": "49", "type_name": "旗袍"},
            {"type_id": "50", "type_name": "空姐制服"},
            {"type_id": "51", "type_name": "护士医生"},
            {"type_id": "52", "type_name": "伦理之爱"},
            {"type_id": "53", "type_name": "禁忌母子"},
            {"type_id": "54", "type_name": "兄弟姐妹"},
            {"type_id": "55", "type_name": "爱上嫂子"},
            {"type_id": "56", "type_name": "狂操小姨"},
            {"type_id": "57", "type_name": "换夫换妻"},
            {"type_id": "58", "type_name": "淫荡儿媳"},
            {"type_id": "59", "type_name": "爷爷奶奶"},
            {"type_id": "60", "type_name": "伦理精选"},
            {"type_id": "61", "type_name": "啪啪直播"},
            {"type_id": "62", "type_name": "学生直播"},
            {"type_id": "63", "type_name": "自慰诱惑"},
            {"type_id": "64", "type_name": "乱伦直播"},
            {"type_id": "65", "type_name": "户外勾搭"},
            {"type_id": "66", "type_name": "车震直播"},
            {"type_id": "67", "type_name": "国产AV"},
            {"type_id": "68", "type_name": "网红主播"},
            {"type_id": "69", "type_name": "欧美精选"},
            {"type_id": "70", "type_name": "户外搭讪"},
            {"type_id": "71", "type_name": "美女自慰"},
            {"type_id": "72", "type_name": "乱伦直播"},
            {"type_id": "73", "type_name": "黑人大屌"},
            {"type_id": "74", "type_name": "群P大作战"},
            {"type_id": "75", "type_name": "欧美重口"},
            {"type_id": "76", "type_name": "人兽性交"},
            {"type_id": "77", "type_name": "SM性虐"},
            {"type_id": "78", "type_name": "人妖伪娘"},
            {"type_id": "79", "type_name": "孕妇内射"},
            {"type_id": "80", "type_name": "吃屎喝尿"},
            {"type_id": "81", "type_name": "扩阴拳交"},
            {"type_id": "82", "type_name": "阳具巨物"},
            {"type_id": "83", "type_name": "3D动漫"},
            {"type_id": "84", "type_name": "同人动漫"},
            {"type_id": "85", "type_name": "剧情故事"},
            {"type_id": "86", "type_name": "国产动漫"},
            {"type_id": "87", "type_name": "日韩动漫"},
            {"type_id": "88", "type_name": "欧美动漫"},
            {"type_id": "89", "type_name": "港台动漫"},
            {"type_id": "90", "type_name": "海外动漫"},
            {"type_id": "91", "type_name": "日本中文"},
            {"type_id": "92", "type_name": "无码流出"},
            {"type_id": "93", "type_name": "FC2"},
            {"type_id": "94", "type_name": "HEYZO"},
            {"type_id": "95", "type_name": "东京热"},
            {"type_id": "96", "type_name": "一本道"},
            {"type_id": "97", "type_name": "人妻斩"},
            {"type_id": "98", "type_name": "主播网黄"},
            {"type_id": "99", "type_name": "色情综艺"},
            {"type_id": "100", "type_name": "情色AV"},
        ]
        self.filters = {}

    def getName(self):
        return "偷欢秘境"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 推荐列表 = 首页最新列表
        return self._fetch_list("/", 1)

    def _fetch_list(self, path, pg=1):
        """通用列表抓取"""
        if pg < 1:
            pg = 1
        url = self.host + path
        if "?" in path:
            url += "&page=" + str(pg)
        else:
            url += "/page/" + str(pg) + ".html" if "/type/" in path else "?page=" + str(pg)
        try:
            html = self.fetch(url, headers=self.headers).text
            return self._parse_video_list(html)
        except Exception as e:
            self.log("fetch list error: " + str(e))
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

    def _parse_video_list(self, html):
        """从HTML解析视频列表"""
        items = []
        # 匹配 video-img-box 结构
        pattern = r'<div class="video-img-box[^"]*">.*?<a href="([^"]+)".*?<img[^>]*src="([^"]+)"[^>]*>.*?<span class="label">([^<]*)</span>.*?<h6 class="title"><a[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        for m in matches:
            link, pic, remark, title = m
            if not link.startswith("http"):
                link = self.host + link
            # 提取视频ID
            vid_match = re.search(r'/id/(\d+)/', link)
            vod_id = vid_match.group(1) if vid_match else ""
            if not vod_id:
                continue
            items.append({
                "vod_id": str(vod_id),
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": remark.strip()
            })
        return {"list": items}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        page = pg or 1
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
        try:
            html = self.fetch(url, headers=self.headers).text
            result = self._parse_video_list(html)
            # 从分类标签中提取总数
            total = 0
            # 方式1: 从当前页面的分类链接中提取
            for cls in self.classes:
                if cls["type_id"] == str(tid):
                    # 在HTML中查找对应的分类标签
                    pattern = f'type/id/{tid}\\.html"[^>]*>([^<]+)'
                    match = re.search(pattern, html)
                    if match:
                        label = match.group(1)
                        num_match = re.search(r'丨(\d+)', label)
                        if num_match:
                            total = int(num_match.group(1))
                            break
            # 方式2: 如果上面没找到，尝试从之前保存的class信息中获取
            if total == 0:
                for cls in self.classes:
                    if cls["type_id"] == str(tid):
                        # 从type_name中提取数字
                        num_match = re.search(r'(\d+)$', cls["type_name"])
                        if num_match:
                            total = int(num_match.group(1))
                        break
            # 方式3: 从页面的mac_total中提取
            if total == 0:
                total_match = re.search(r'<span class="mac_total">(\d+)</span>', html)
                if total_match:
                    total = int(total_match.group(1))
            pagecount = (total + 19) // 20 if total > 0 else 1
            result["page"] = int(page)
            result["pagecount"] = pagecount
            result["limit"] = 20
            result["total"] = total
            return result
        except Exception as e:
            self.log("categoryContent error: " + str(e))
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        try:
            html = self.fetch(url, headers=self.headers).text
            # 提取标题
            title_match = re.search(r'<h4>([^<]+)</h4>', html)
            title = title_match.group(1).strip() if title_match else "视频"
            # 提取封面
            pic_match = re.search(r'<img[^>]*src="([^"]+)"[^>]*data-preview', html)
            pic = pic_match.group(1) if pic_match else ""
            # 提取播放地址
            player_match = re.search(r'var player_aaaa=({[^}]+})', html)
            play_url = ""
            if player_match:
                try:
                    data = json.loads(player_match.group(1))
                    play_url = data.get("url", "")
                except:
                    pass
            # 如果没有直接提取到，尝试从iframe提取
            if not play_url:
                iframe_match = re.search(r'<iframe[^>]*src="[^"]*video\.php\?url=([^"]+)"', html)
                if iframe_match:
                    play_url = unquote(iframe_match.group(1))
            if not play_url:
                # 尝试从player.js提取
                js_match = re.search(r'src="/static/player/[^"]+\.js\?[^"]*"', html)
                if js_match:
                    pass  # 继续尝试其他方式
            # 提取分类
            cat_match = re.search(r'<a href="/index.php/vod/type/id/\d+\.html"[^>]*>([^<]+)</a>', html)
            category = cat_match.group(1) if cat_match else ""
            # 构建详情
            vod = {
                "vod_id": str(vid),
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": category,
                "vod_content": category,
                "vod_play_from": "播放",
                "vod_play_url": "播放$" + play_url if play_url else ""
            }
            return {"list": [vod]}
        except Exception as e:
            self.log("detailContent error: " + str(e))
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        page = pg or "1"
        url = f"{self.host}/index.php/vod/search.html?wd={quote(key)}&page={page}"
        try:
            html = self.fetch(url, headers=self.headers).text
            result = self._parse_video_list(html)
            result["page"] = int(page)
            return result
        except Exception as e:
            self.log("searchContent error: " + str(e))
            return {"list": [], "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 1, "url": "", "header": self.headers}
        # 如果是播放地址
        if id.startswith("http"):
            if ".m3u8" in id:
                return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": self.headers}
            return {"parse": 0, "url": id, "header": self.headers}
        # 尝试直接访问播放页提取
        try:
            url = f"{self.host}/index.php/vod/play/id/{id}/sid/1/nid/1.html" if not id.startswith("http") else id
            html = self.fetch(url, headers=self.headers).text
            player_match = re.search(r'var player_aaaa=({[^}]+})', html)
            if player_match:
                data = json.loads(player_match.group(1))
                play_url = data.get("url", "")
                if play_url and ".m3u8" in play_url:
                    return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": self.headers}
                if play_url:
                    return {"parse": 0, "url": play_url, "header": self.headers}
        except:
            pass
        return {"parse": 1, "url": id, "header": self.headers}

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "&url=" + quote(str(url or ""), safe="")

    def localProxy(self, param):
        target = unquote(str((param or {}).get("url", "") or ""))
        if not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]
        try:
            res = self.fetch(target, headers=self.headers, timeout=15)
            if not res or getattr(res, "status_code", 0) != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            raw = getattr(res, "content", b"") or b""
            text = raw.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log("m3u8 proxy error: " + str(e))
            return [500, "text/plain", b"m3u8 proxy error"]

    def _clean_m3u8(self, text, source_url):
        """清洗m3u8，过滤非正片分片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
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
                if content_root and content_root not in urlparse(media).path:
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
            self.log("m3u8 filtered ads: %d" % removed)
        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                return 'URI="' + urljoin(source_url, match.group(1)) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            return urljoin(source_url, line)
        return line