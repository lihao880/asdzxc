# coding=utf-8
"""
爱的色放 - TVBox 爬虫
只返回 url，不返回 playUrl
"""
import re
import json
import gzip
import zlib
import urllib.parse
import urllib.request
import urllib.error
import ssl
import sys
import html as html_lib

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
    HAS_BASE = True
except:
    HAS_BASE = False


class Spider:
    """爱的色放 - 苹果CMS影视爬虫"""
    
    def __init__(self):
        self.host = "https://abc615.adsf2.ink/adse"
        self.base_url = self.host
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
        }
        self._classes = None
        self.cookies = {}

    def getName(self):
        return "爱的色放"

    def init(self, extend=""):
        pass

    def _get_classes(self):
        if self._classes is not None:
            return self._classes
        self._classes = [
            {"id": "6", "name": "精品推荐"},
            {"id": "7", "name": "国产精品"},
            {"id": "8", "name": "主播秀色"},
            {"id": "9", "name": "日本有码"},
            {"id": "10", "name": "日本无码"},
            {"id": "11", "name": "中文字幕"},
            {"id": "21", "name": "童颜巨乳"},
            {"id": "22", "name": "性感人妻"},
            {"id": "23", "name": "强奸乱伦"},
            {"id": "24", "name": "欧美情色"},
            {"id": "25", "name": "三级伦理"},
            {"id": "26", "name": "卡通动漫"},
            {"id": "27", "name": "丝袜OL"},
            {"id": "28", "name": "自拍偷拍"},
            {"id": "29", "name": "日本片商"},
            {"id": "31", "name": "网曝系列"},
            {"id": "32", "name": "麻豆传媒"},
            {"id": "34", "name": "国产乱伦"},
            {"id": "36", "name": "国产SM"},
            {"id": "37", "name": "国产人妻"},
            {"id": "41", "name": "网红主播"},
            {"id": "42", "name": "国产传媒"},
            {"id": "43", "name": "探花系列"},
            {"id": "44", "name": "人妻熟女"},
            {"id": "45", "name": "日本无码"},
            {"id": "46", "name": "美乳巨乳"},
            {"id": "47", "name": "强制侵犯"},
            {"id": "48", "name": "制服诱惑"},
            {"id": "49", "name": "绝色佳人"},
            {"id": "50", "name": "风俗泡泡浴"},
            {"id": "51", "name": "家庭乱伦"},
            {"id": "52", "name": "AV解说"},
            {"id": "53", "name": "三级电影"},
            {"id": "54", "name": "少女萝莉"},
            {"id": "55", "name": "SM调教"},
            {"id": "56", "name": "绝顶潮吹"},
            {"id": "57", "name": "魔镜系列"},
            {"id": "58", "name": "时间停止"},
            {"id": "59", "name": "漫改系列"},
            {"id": "60", "name": "电车痴汉"},
            {"id": "73", "name": "无码专区"},
            {"id": "74", "name": "麻豆传媒"},
            {"id": "75", "name": "制服诱惑"},
            {"id": "76", "name": "三级伦理"},
            {"id": "77", "name": "AI换脸"},
            {"id": "78", "name": "中文字幕"},
            {"id": "79", "name": "卡通动漫"},
            {"id": "80", "name": "欧美系列"},
            {"id": "81", "name": "美女主播"},
            {"id": "82", "name": "国产自拍"},
            {"id": "83", "name": "熟女人妻"},
            {"id": "84", "name": "萝莉少女"},
            {"id": "85", "name": "多人群交"},
            {"id": "86", "name": "美乳巨乳"},
            {"id": "87", "name": "强奸乱伦"},
            {"id": "88", "name": "抖音视频"},
            {"id": "89", "name": "韩国主播"},
            {"id": "90", "name": "网红头条"},
            {"id": "91", "name": "网爆黑料"},
            {"id": "92", "name": "欧美无码"},
        ]
        return self._classes

    def _fix_url(self, url):
        if not url:
            return ""
        url = str(url).strip()
        url = url.replace('\\/', '/')
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        if not url.startswith("http"):
            return self.host + "/" + url
        return url

    def _clean_text(self, text):
        if not text:
            return ""
        return re.sub(r"\s+", " ", html_lib.unescape(str(text))).strip()

    def _fetch(self, url, headers=None):
        if headers is None:
            headers = self.headers.copy()
        
        if not url.startswith("http"):
            url = self.host + url if url.startswith("/") else self.host + "/" + url
        
        try:
            req = urllib.request.Request(url, headers=headers)
            if self.cookies:
                cookie_str = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
                req.add_header('Cookie', cookie_str)
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read()
                encoding = resp.info().get('Content-Encoding', '').lower()
                if encoding == 'gzip':
                    try:
                        content = gzip.decompress(content)
                    except:
                        pass
                elif encoding == 'deflate':
                    try:
                        content = zlib.decompress(content, -zlib.MAX_WBITS)
                    except:
                        pass
                cookie_header = resp.info().get('Set-Cookie', '')
                if cookie_header:
                    for cookie in cookie_header.split(','):
                        if '=' in cookie:
                            parts = cookie.strip().split(';')[0].split('=', 1)
                            if len(parts) == 2:
                                self.cookies[parts[0]] = parts[1]
                return content.decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"[爱的色放] fetch error: {e}")
            return ""

    def _parse_video_list(self, html):
        videos = []
        if not html:
            return videos
        
        dl_pattern = r'<dl>(.*?)</dl>'
        dl_blocks = re.findall(dl_pattern, html, re.DOTALL)
        
        for block in dl_blocks:
            try:
                link_match = re.search(r'href="([^"]+)"', block)
                if not link_match:
                    continue
                link = link_match.group(1)
                id_match = re.search(r'/vodplay/(\d+)', link)
                if not id_match:
                    continue
                vod_id = id_match.group(1)
                pic_match = re.search(r'data-src="([^"]+)"', block)
                if not pic_match:
                    pic_match = re.search(r'src="([^"]+)"', block)
                pic = pic_match.group(1) if pic_match else ""
                title_match = re.search(r'<h3>(.*?)</h3>', block)
                if not title_match:
                    title_match = re.search(r'alt="([^"]+)"', block)
                title = title_match.group(1) if title_match else ""
                title = self._clean_text(title)
                remark_match = re.search(r'<i>(.*?)</i>', block)
                remark = remark_match.group(1) if remark_match else ""
                if vod_id and title:
                    videos.append({
                        "vod_id": vod_id,
                        "vod_name": title,
                        "vod_pic": self._fix_url(pic),
                        "vod_remarks": remark
                    })
            except:
                continue
        
        if not videos:
            link_pattern = r'href="(/adse/vodplay/(\d+)-1-1\.html)"[^>]*>'
            for match in re.finditer(link_pattern, html):
                try:
                    link = match.group(1)
                    vod_id = match.group(2)
                    pos = match.end()
                    h3_match = re.search(r'<h3>(.*?)</h3>', html[pos:pos+300])
                    title = self._clean_text(h3_match.group(1)) if h3_match else ""
                    if vod_id and title:
                        pic = ""
                        pic_match = re.search(r'data-src="([^"]+)"', html[max(0, pos-300):pos+300])
                        if pic_match:
                            pic = pic_match.group(1)
                        videos.append({
                            "vod_id": vod_id,
                            "vod_name": title,
                            "vod_pic": self._fix_url(pic),
                            "vod_remarks": ""
                        })
                except:
                    continue
        
        return videos

    def _extract_play_url(self, html):
        """提取播放地址"""
        player_match = re.search(r'player_aaaa\s*=\s*({[^;]+?});', html)
        if player_match:
            try:
                player_data = json.loads(player_match.group(1))
                play_url = player_data.get("url", "")
                if play_url and '.m3u8' in play_url:
                    return self._fix_url(play_url)
            except:
                pass
        
        player_idx = html.find('player_aaaa')
        if player_idx > 0:
            region = html[player_idx:player_idx+800]
            url_match = re.search(r'"url":\s*"([^"]+)"', region)
            if url_match:
                play_url = url_match.group(1)
                play_url = play_url.replace('\\/', '/')
                if '.m3u8' in play_url:
                    return play_url
        
        iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"[^>]*>', html)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            if 'yutujx.com' in iframe_url:
                real_match = re.search(r'\?url=([^&]+)', iframe_url)
                if real_match:
                    real_url = urllib.parse.unquote(real_match.group(1))
                    if '.m3u8' in real_url:
                        return self._fix_url(real_url)
        
        m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
        if m3u8_match:
            return self._fix_url(m3u8_match.group(1))
        
        return None

    def homeContent(self, filter):
        result = {"class": [], "list": []}
        for cls in self._get_classes():
            result["class"].append({
                "type_id": cls["id"],
                "type_name": cls["name"]
            })
        html = self._fetch("/")
        if html:
            videos = self._parse_video_list(html)
            result["list"] = videos[:20] if len(videos) > 20 else videos
        return result

    def homeVideoContent(self):
        html = self._fetch("/")
        if html:
            videos = self._parse_video_list(html)
            return {"list": videos[:20] if len(videos) > 20 else videos}
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
        except:
            page = 1
        
        result = {
            "list": [],
            "page": page,
            "pagecount": 1,
            "limit": 20,
            "total": 0
        }
        
        if page == 1:
            url = f"/vodtype/{tid}.html"
        else:
            url = f"/vodtype/{tid}-{page}.html"
        
        html = self._fetch(url)
        if html:
            videos = self._parse_video_list(html)
            result["list"] = videos
            
            total_match = re.search(r'共有(\d+)个视频', html)
            if total_match:
                result["total"] = int(total_match.group(1))
            
            page_links = re.findall(r'href="[^"]*[?&]page[=_](\d+)"', html)
            page_links += re.findall(r'href="[^"]*[-](\d+)\.html"', html)
            if page_links:
                page_nums = [int(p) for p in page_links if p.isdigit()]
                if page_nums:
                    result["pagecount"] = max(page_nums) + 1 if page_nums else 1
            
            if result["pagecount"] <= page and re.search(r'下一页|next', html, re.I):
                result["pagecount"] = page + 1
        
        return result

    def searchContent(self, key, quick, pg=1):
        result = {"list": []}
        if not key or not key.strip():
            return result
        
        try:
            page = int(pg) if pg else 1
        except:
            page = 1
        
        encoded_key = urllib.parse.quote(key.strip())
        url = f"/vodsearch/-------------.html?wd={encoded_key}&page={page}"
        
        html = self._fetch(url)
        if html:
            videos = self._parse_video_list(html)
            result["list"] = videos
        
        return result

    def detailContent(self, ids):
        result = {"list": []}
        if not ids or len(ids) == 0:
            return result
        
        vid = ids[0]
        url = f"/vodplay/{vid}-1-1.html"
        html = self._fetch(url)
        if not html:
            return result
        
        video_data = {
            "vod_id": vid,
            "vod_name": "",
            "vod_pic": "",
            "vod_content": "",
            "vod_remarks": "",
            "vod_play_from": "",
            "vod_play_url": ""
        }
        
        title_match = re.search(r'<h1>(.*?)</h1>', html)
        if title_match:
            video_data["vod_name"] = self._clean_text(title_match.group(1))
        else:
            title_match = re.search(r'<title>(.*?)</title>', html)
            if title_match:
                title = title_match.group(1)
                title = re.sub(r'\s*[-|]\s*(视频在线播放|成人色情|爱的色放).*$', '', title)
                video_data["vod_name"] = self._clean_text(title)
        
        play_url = self._extract_play_url(html)
        if play_url:
            video_data["vod_play_from"] = "直链"
            video_data["vod_play_url"] = play_url
        else:
            video_data["vod_play_from"] = "网页嗅探"
            video_data["vod_play_url"] = url
        
        result["list"].append(video_data)
        return result

    def playerContent(self, flag, id, vipFlags):
        """播放解析 - 只返回 url，不返回 playUrl"""
        result = {"parse": 1, "url": ""}
        
        if id:
            if ".m3u8" in id:
                result["parse"] = 0
                result["url"] = id
                result["header"] = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": self.host + "/"
                }
                return result
            
            if "vodplay" in id or "/adse/" in id:
                if not id.startswith("http"):
                    full_url = self.host + id if id.startswith("/") else self.host + "/" + id
                else:
                    full_url = id
                
                html = self._fetch(full_url)
                if html:
                    play_url = self._extract_play_url(html)
                    if play_url:
                        result["parse"] = 0
                        result["url"] = play_url
                        result["header"] = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Referer": full_url
                        }
                        return result
        
        result["parse"] = 1
        result["url"] = id if id else self.host + "/"
        return result

    def localProxy(self, params):
        return None

    def destroy(self):
        pass

    def getDependence(self):
        return []

    def videoContent(self, ids):
        return self.detailContent(ids)