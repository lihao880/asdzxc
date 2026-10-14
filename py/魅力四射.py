# coding: utf-8
import re
import json
import urllib.parse
from bs4 import BeautifulSoup
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    BaseSpider = object


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xz123.cfd"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/'
        }
        self.classes = [
            {"type_id": "1", "type_name": "无码专区"},
            {"type_id": "6", "type_name": "中文字幕"},
            {"type_id": "2", "type_name": "麻豆传媒"},
            {"type_id": "3", "type_name": "制服诱惑"},
            {"type_id": "4", "type_name": "三级伦理"},
            {"type_id": "7", "type_name": "卡通动漫"},
            {"type_id": "5", "type_name": "AI换脸"},
            {"type_id": "8", "type_name": "欧美系列"},
            {"type_id": "13", "type_name": "女同性爱"},
            {"type_id": "14", "type_name": "多人群交"},
            {"type_id": "15", "type_name": "美乳巨乳"},
            {"type_id": "9", "type_name": "美女主播"},
            {"type_id": "16", "type_name": "强奸乱轮"},
            {"type_id": "11", "type_name": "熟女人妻"},
            {"type_id": "12", "type_name": "萝莉少女"},
            {"type_id": "10", "type_name": "国产自拍"},
            {"type_id": "17", "type_name": "抖音视频"},
            {"type_id": "18", "type_name": "韩国主播"},
            {"type_id": "19", "type_name": "网红头条"},
            {"type_id": "20", "type_name": "网爆黑料"},
            {"type_id": "21", "type_name": "欧美无码"},
            {"type_id": "22", "type_name": "女忧明星"},
            {"type_id": "23", "type_name": "SM调教"},
            {"type_id": "24", "type_name": "AV解说"},
        ]
        self.filters = {}

    def getName(self):
        return "魅力四射"

    def getDependence(self):
        return ["bs4"]

    def init(self, extend=""):
        self.extend = extend or ""

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _fetch(self, url, headers=None, timeout=15):
        try:
            if hasattr(self, 'fetch'):
                resp = self.fetch(url, headers=headers or self.headers, timeout=timeout)
                return resp
            import requests
            resp = requests.get(url, headers=headers or self.headers, timeout=timeout)
            return resp
        except Exception as e:
            print('fetch error:', e)
            return None

    def _get_html(self, url, headers=None):
        resp = self._fetch(url, headers)
        if resp and hasattr(resp, 'status_code') and resp.status_code == 200:
            return resp.text
        return None

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

    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except:
                pass
            result = {}
            for part in extend.split(','):
                if '=' in part:
                    k, v = part.split('=', 1)
                    result[k.strip()] = v.strip()
            return result
        return {}

    def _parse_video_list(self, html, limit=999):
        if not html:
            return []
        doc = BeautifulSoup(html, 'html.parser')
        videos = []
        seen_ids = set()

        for a in doc.select('a[href*="/detail/"]'):
            href = a.get('href', '')
            if not href or '/detail/' not in href:
                continue

            vid_match = re.search(r'/detail/id/(\d+)\.html', href)
            if not vid_match:
                continue
            vid = vid_match.group(1)

            if vid in seen_ids:
                continue
            seen_ids.add(vid)

            title = a.get('title', '')
            if not title:
                h3 = a.find('h3', class_='text-ellipsis')
                if h3:
                    title = h3.text.strip()
            if not title:
                title = a.text.strip()

            pic = ''
            img = a.find('img', class_='content-img')
            if img:
                pic = img.get('data-original') or img.get('src', '')
                pic = self._fix_url(pic)

            remark = ''
            parent = a.parent
            if parent:
                for sibling in parent.previous_siblings:
                    if sibling.name == 'a' and '/detail/' in sibling.get('href', ''):
                        time_text = sibling.text.strip()
                        if re.match(r'\d{2}-\d{2}', time_text):
                            remark = time_text
                            break

            if vid and title:
                videos.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })
                if len(videos) >= limit:
                    break

        return videos

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            result = self.categoryContent('1', '1', False, None)
            return {'list': result.get('list', [])[:20]}
        except Exception as e:
            print('homeVideoContent error:', e)
            return {'list': []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        url = f"{self.host}/index.php/vod/type/id/{tid}.html"
        if pg > 1:
            url += f"?page={pg}"

        html = self._get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}

        videos = self._parse_video_list(html)

        pagecount = 999
        doc = BeautifulSoup(html, 'html.parser')
        for a in doc.select('a[href*="page="]'):
            if a.text.strip().isdigit():
                num = int(a.text.strip())
                if num > pagecount:
                    pagecount = num

        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 20,
            'total': pagecount * 20
        }

    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        vid = ids[0]

        url = f"{self.host}/index.php/vod/detail/id/{vid}.html"
        html = self._get_html(url)
        if not html:
            return {'list': []}

        doc = BeautifulSoup(html, 'html.parser')

        title = ''
        h1 = doc.find('h1')
        if h1:
            title = h1.text.strip()
        if not title:
            title_tag = doc.find('div', class_='header_title')
            if title_tag:
                title = title_tag.text.strip()

        pic = ''
        img = doc.find('img', class_='content-img')
        if img:
            pic = img.get('data-original') or img.get('src', '')
            pic = self._fix_url(pic)

        remark = ''
        type_span = doc.find('span', string=re.compile(r'類型|类型'))
        if type_span:
            parent = type_span.parent
            if parent:
                remark = parent.text.replace('類型：', '').replace('类型：', '').strip()

        content = ''
        desc_div = doc.find('div', class_='content-text')
        if desc_div:
            content = desc_div.text.strip()

        play_from_list = []
        play_url_list = []

        for a in doc.select('a[href*="/play/"]'):
            href = a.get('href', '')
            if not href or '/play/' not in href:
                continue
            play_id_match = re.search(r'/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html', href)
            if not play_id_match:
                continue
            play_from = a.text.strip() or '线路'
            play_url = href
            if play_url not in play_url_list:
                play_from_list.append(play_from)
                play_url_list.append(play_url)

        if play_from_list:
            vod_play_from = '$$$'.join(play_from_list)
            vod_play_url = '$$$'.join([f'播放${url}' for url in play_url_list])
        else:
            vod_play_from = '默认线路'
            vod_play_url = f'播放${vid}'

        data = {
            'vod_id': vid,
            'vod_name': title or '未知视频',
            'vod_pic': pic,
            'vod_remarks': remark,
            'vod_content': content,
            'vod_play_from': vod_play_from,
            'vod_play_url': vod_play_url,
        }

        return {'list': [data]}

    def searchContent(self, key, quick=False, pg='1'):
        if not key:
            return {'list': [], 'page': 1, 'pagecount': 1, 'total': 0}

        pg = int(pg) if pg else 1
        url = f"{self.host}/index.php/vod/search.html?wd={urllib.parse.quote(key)}"
        if pg > 1:
            url += f"&page={pg}"

        html = self._get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}

        videos = self._parse_video_list(html)

        pagecount = 1
        doc = BeautifulSoup(html, 'html.parser')
        for a in doc.select('a[href*="page="]'):
            if a.text.strip().isdigit():
                num = int(a.text.strip())
                if num > pagecount:
                    pagecount = num

        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'total': pagecount * 20
        }

    def _m3u8_proxy_url(self, url):
        if not url:
            return ''
        url = str(url).replace('\\/', '/')
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(url, safe="")

    def _extract_m3u8_from_html(self, html):
        if not html:
            return None

        pattern = r'var\s+player_aaaa\s*=\s*(\{[^;]+\});'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                url = data.get("url", "")
                if url and url.startswith("http") and ".m3u8" in url:
                    url = url.replace('\\/', '/')
                    return url
            except:
                pass

        pattern2 = r'var\s+player\s*=\s*(\{[^;]+\});'
        match2 = re.search(pattern2, html, re.DOTALL)
        if match2:
            try:
                data = json.loads(match2.group(1))
                url = data.get("url", "")
                if url and url.startswith("http") and ".m3u8" in url:
                    url = url.replace('\\/', '/')
                    return url
            except:
                pass

        pattern3 = r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"'
        match3 = re.search(pattern3, html)
        if match3:
            url = match3.group(1)
            if url and url.startswith("http"):
                url = url.replace('\\/', '/')
                return url

        iframe_match = re.search(r'<iframe[^>]*src=["\']([^"\']+)["\'][^>]*>', html)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            if ".m3u8" in iframe_url:
                m3u8_match = re.search(r'[?&]url=([^&]+)', iframe_url)
                if m3u8_match:
                    m3u8_url = urllib.parse.unquote(m3u8_match.group(1))
                    if m3u8_url.startswith("http") and ".m3u8" in m3u8_url:
                        m3u8_url = m3u8_url.replace('\\/', '/')
                        return m3u8_url
                if iframe_url.startswith("http") and ".m3u8" in iframe_url:
                    iframe_url = iframe_url.replace('\\/', '/')
                    return iframe_url

        pattern5 = r'https?://[^\s"\']+\.m3u8[^\s"\']*'
        match5 = re.search(pattern5, html)
        if match5:
            url = match5.group(0)
            url = url.replace('\\/', '/')
            return url

        return None

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {'parse': 1, 'url': ''}

        if id.startswith('http') and (id.endswith('.m3u8') or '.m3u8?' in id):
            proxy_url = self._m3u8_proxy_url(id)
            return {
                'parse': 0,
                'url': proxy_url,
                'header': {
                    'User-Agent': self.headers['User-Agent'],
                    'Referer': self.host + '/'
                }
            }

        play_page_url = id
        if id.startswith('/'):
            play_page_url = self.host + id
        elif not id.startswith('http'):
            play_page_url = f"{self.host}/index.php/vod/play/id/{id}/sid/1/nid/1.html"

        html = self._get_html(play_page_url)
        if html:
            m3u8_url = self._extract_m3u8_from_html(html)
            if m3u8_url:
                proxy_url = self._m3u8_proxy_url(m3u8_url)
                return {
                    'parse': 0,
                    'url': proxy_url,
                    'header': {
                        'User-Agent': self.headers['User-Agent'],
                        'Referer': self.host + '/'
                    }
                }

        return {
            'parse': 1,
            'url': play_page_url,
            'header': {
                'User-Agent': self.headers['User-Agent'],
                'Referer': self.host + '/'
            }
        }

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写 m3u8 标签中的 URI（补全绝对地址）"""
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

    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片，保留正片（基于 m3u8_ad_filter.md v3.0）"""
        import posixpath
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 处理多码率 Master Playlist（主 m3u8 代理嵌套）
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

                # 过滤逻辑：判断分片路径是否以正片目录开头
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

        # 二次清洗：去除孤立/连续的 #EXT-X-DISCONTINUITY 和 KEY:METHOD=NONE
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

    def localProxy(self, param):
        """m3u8 本地代理 - 广告分片过滤（基于 m3u8_ad_filter.md v3.0）"""
        try:
            # 兼容 url 和 source 两种参数名
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            # 剥离前缀 url= 并解码
            if target.startswith("url="):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            # 发起 HTTP 请求获取 m3u8 内容
            resp = self._fetch(target, headers=self.headers, timeout=15)
            if not resp:
                return [502, "text/plain", b"fetch failed"]

            content = b""
            if hasattr(resp, "content"):
                content = resp.content or b""
            if not content and hasattr(resp, "text"):
                content = resp.text.encode("utf-8", errors="ignore")

            if not content:
                return [502, "text/plain", b"empty content"]

            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            # 执行广告过滤清洗
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]

    def destroy(self):
        pass
