# coding: utf-8
# 不卡精品站 - TVBox/FongMi 爬虫
# 站点: https://0765.buka22.top/buka/
# 类型: MacCMS 成人视频站 (AES-CBC 加密)
# 特征: 标准 MacCMS 结构，页面内容 AES-CBC 加密，DPlayer m3u8 直链
# 支持: m3u8 广告过滤、本地代理

import re
import json
import base64
import posixpath
from urllib.parse import quote, urljoin, unquote, urlparse

from base.spider import Spider as BaseSpider

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except ImportError:
    pass


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://0765.buka22.top/buka"
        self.aes_key = b"1234567898882222"
        self.aes_iv = b"1234567898882222"
        self.classes = [
            {"type_id": "1", "type_name": "视频一区"},
            {"type_id": "10", "type_name": "视频二区"},
            {"type_id": "19", "type_name": "视频三区"},
            {"type_id": "28", "type_name": "视频四区"},
            {"type_id": "37", "type_name": "视频五区"},
            {"type_id": "2", "type_name": "精品推荐"},
            {"type_id": "3", "type_name": "国产精品"},
            {"type_id": "4", "type_name": "主播秀色"},
            {"type_id": "5", "type_name": "日本有码"},
            {"type_id": "6", "type_name": "日本无码"},
            {"type_id": "7", "type_name": "中文字幕"},
            {"type_id": "8", "type_name": "童颜巨乳"},
            {"type_id": "9", "type_name": "性感人妻"},
            {"type_id": "11", "type_name": "强奸乱伦"},
            {"type_id": "12", "type_name": "欧美情色"},
            {"type_id": "13", "type_name": "三级伦理"},
            {"type_id": "14", "type_name": "卡通动漫"},
            {"type_id": "15", "type_name": "丝袜OL"},
            {"type_id": "16", "type_name": "自拍偷拍"},
            {"type_id": "17", "type_name": "日本片商"},
            {"type_id": "18", "type_name": "剧情介绍"},
            {"type_id": "20", "type_name": "网曝系列"},
            {"type_id": "21", "type_name": "麻豆传媒"},
            {"type_id": "22", "type_name": "明星换脸"},
            {"type_id": "23", "type_name": "国产乱伦"},
            {"type_id": "24", "type_name": "国产丝袜"},
            {"type_id": "25", "type_name": "国产SM"},
            {"type_id": "26", "type_name": "国产人妻"},
            {"type_id": "27", "type_name": "探花嫖娼"},
            {"type_id": "29", "type_name": "同性恋"},
            {"type_id": "30", "type_name": "日韩无码"},
            {"type_id": "31", "type_name": "日韩精品"},
            {"type_id": "32", "type_name": "欧美精品"},
            {"type_id": "33", "type_name": "国产传媒"},
            {"type_id": "34", "type_name": "伦理影片"},
            {"type_id": "35", "type_name": "人妻系列"},
            {"type_id": "36", "type_name": "制服诱惑"},
            {"type_id": "38", "type_name": "AV明星"},
            {"type_id": "39", "type_name": "SM重味"},
            {"type_id": "40", "type_name": "巨乳系列"},
            {"type_id": "41", "type_name": "颜射系列"},
            {"type_id": "42", "type_name": "口交视频"},
            {"type_id": "43", "type_name": "自慰系列"},
            {"type_id": "44", "type_name": "教师学生"},
            {"type_id": "45", "type_name": "大秀视频"},
        ]
        self.filters = {str(c["type_id"]): [] for c in self.classes}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    def getName(self):
        return "不卡精品站"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址"""
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def _decrypt_html(self, encrypted_text):
        """解密页面内容 - AES-CBC"""
        try:
            encrypted_text = encrypted_text.strip()
            encrypted_bytes = base64.b64decode(encrypted_text)
            cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv)
            decrypted = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
            return decrypted.decode('utf-8', errors='ignore')
        except Exception as e:
            return encrypted_text

    def _fetch_decrypted_html(self, url):
        """获取并解密页面"""
        try:
            resp = self.fetch(url, headers=self.headers)
            if resp and hasattr(resp, "status_code") and resp.status_code == 200:
                html = resp.text
                if '<div id="app" style="display:none;">' in html:
                    match = re.search(r'<div id="app" style="display:none;">([\s\S]*?)</div>', html)
                    if match:
                        encrypted = match.group(1).strip()
                        return self._decrypt_html(encrypted)
                return html
            return ""
        except Exception as e:
            return ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self.categoryContent("1", "1", None, None)

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg) if pg else "1"
        tid = str(tid)
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"
        html = self._fetch_decrypted_html(url)
        items = self._parse_video_list(html)
        page_count = self._parse_page_count(html, tid)
        return {
            "list": items,
            "page": int(pg),
            "pagecount": page_count if page_count > 0 else 1,
            "limit": 20,
            "total": page_count * 20 if page_count > 0 else 20,
        }

    def detailContent(self, ids):
        if isinstance(ids, list):
            raw = str(ids[0])
        else:
            raw = str(ids)
        parts = raw.split("|$|")
        vid = parts[0]
        title = parts[1] if len(parts) > 1 else "视频"
        pic = parts[2] if len(parts) > 2 else ""
        remark = parts[3] if len(parts) > 3 else ""

        play_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"

        if len(parts) == 1:
            html = self._fetch_decrypted_html(play_url)
            title, pic, remark = self._parse_detail_meta(html)

        vod = {
            "vod_id": raw,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_content": remark,
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}",
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = str(pg) if pg else "1"
        url = f"{self.host}/index.php/vod/search/page/{pg}/wd/{quote(key)}.html"
        html = self._fetch_decrypted_html(url)
        items = self._parse_video_list(html)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        if id.startswith("http"):
            play_url = id
        else:
            play_url = f"{self.host}/index.php/vod/play/id/{id}/sid/1/nid/1.html"

        html = self._fetch_decrypted_html(play_url)

        player_match = re.search(r'var\s+player_aaaa\s*=\s*({[^;]+});?', html, re.DOTALL)
        if player_match:
            try:
                data = json.loads(player_match.group(1))
                if data.get("encrypt") == 0 and data.get("url"):
                    m3u8_url = data["url"]
                    if m3u8_url.startswith("//"):
                        m3u8_url = "https:" + m3u8_url
                    # 通过本地代理过滤广告
                    return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": self.headers}
            except:
                pass

        video_match = re.search(r'<video[^>]*src="([^"]+\.m3u8[^"]*)"', html, re.IGNORECASE)
        if video_match:
            m3u8_url = video_match.group(1)
            if m3u8_url.startswith("//"):
                m3u8_url = "https:" + m3u8_url
            elif m3u8_url.startswith("/"):
                m3u8_url = self.host + m3u8_url
            return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": self.headers}

        return {"parse": 1, "url": play_url, "header": self.headers}

    def localProxy(self, param):
        """m3u8 本地代理 - 广告过滤 + 路径重写"""
        try:
            # 兼容 url 和 source 两种参数名
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            # 剥离前缀并解码
            if target.startswith("url="):
                target = target[4:]
            target = unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            # 获取 m3u8 内容
            res = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=15)
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
        """清洗 m3u8：过滤广告分片，保留正片"""
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

        # 二次清洗：去除孤立/连续的标记
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        # 清理尾部多余的标记
        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写 m3u8 标签中的 URI（补全绝对地址）"""
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

    def _parse_video_list(self, html):
        items = []
        if not html:
            return items

        blocks = re.findall(r'<div\s+class="item\s+thumb\s+thumb--videos">(.*?)</div>\s*</div>', html, re.DOTALL)
        if not blocks:
            blocks = re.findall(r'<div\s+class="item\s+thumb[^"]*">(.*?)</div>\s*</div>', html, re.DOTALL)

        for block in blocks:
            link_match = re.search(r'<a\s+href="([^"]+)"', block)
            if not link_match:
                continue
            link = link_match.group(1)

            vid_match = re.search(r'/vod/play/id/(\d+)/', link)
            if not vid_match:
                continue
            vid = vid_match.group(1)

            title_match = re.search(r'<h5\s+class="thumb-spot__title">([^<]+)</h5>', block)
            if not title_match:
                title_match = re.search(r'<h5[^>]*>([^<]+)</h5>', block)
            if not title_match:
                continue
            title = title_match.group(1).strip()

            pic_match = re.search(r'<img\s+src="([^"]+)"', block)
            pic = pic_match.group(1) if pic_match else ""

            remark_match = re.search(r'<span\s+class="[^"]*duration[^"]*"[^>]*>([^<]+)</span>', block)
            remark = remark_match.group(1) if remark_match else ""

            if any(k in title for k in ["同城约炮", "金桃直播", "糖果直播", "顶级主播"]):
                continue

            items.append({
                "vod_id": f"{vid}|$|{title}|$|{pic}|$|{remark}",
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })

        return items

    def _parse_page_count(self, html, tid):
        if not html:
            return 1

        match = re.search(r'<a[^>]*href="[^"]*/page/(\d+)\.html"[^>]*>.*?尾页', html)
        if match:
            return int(match.group(1))

        matches = re.findall(r'<a[^>]*href="[^"]*/page/(\d+)\.html"[^>]*>', html)
        if matches:
            return max(int(x) for x in matches)

        return 1

    def _parse_detail_meta(self, html):
        title = "视频"
        pic = ""
        remark = ""

        if not html:
            return title, pic, remark

        title_match = re.search(r'<h1\s+class="title">([^<]+)</h1>', html)
        if title_match:
            title = title_match.group(1).strip()

        player_match = re.search(r'var\s+player_aaaa\s*=\s*({[^;]+});?', html, re.DOTALL)
        if player_match:
            try:
                data = json.loads(player_match.group(1))
                if "vod_data" in data:
                    vod_data = data["vod_data"]
                    if "vod_name" in vod_data:
                        title = vod_data["vod_name"]
                    if "vod_pic" in vod_data:
                        pic = vod_data["vod_pic"]
            except:
                pass

        if not pic:
            pic_match = re.search(r'<div\s+class="thumb__img">\s*<img\s+src="([^"]+)"', html)
            if pic_match:
                pic = pic_match.group(1)

        return title, pic, remark