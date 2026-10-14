# coding: utf-8
import re
import json
import base64
import urllib.parse
import posixpath
from bs4 import BeautifulSoup
try:
    import requests
except ImportError:
    pass

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://nxav2.xyz"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/'
        }
        self.classes = []
        self.filters = {}

    def getName(self):
        return "nxav2"

    def getDependence(self):
        return ['bs4', 'requests']

    def init(self, extend=""):
        pass

    def destroy(self):
        pass

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def fetch(self, url, headers=None, timeout=15):
        try:
            headers = headers or self.headers
            resp = requests.get(url, headers=headers, timeout=timeout)
            return resp
        except Exception as e:
            print('fetch error:', e)
            return None

    def post_fetch(self, url, data=None, headers=None, timeout=15):
        try:
            headers = headers or self.headers
            resp = requests.post(url, data=data, headers=headers, timeout=timeout)
            return resp
        except Exception as e:
            print('post error:', e)
            return None

    def get_html(self, url, headers=None):
        resp = self.fetch(url, headers)
        if resp and hasattr(resp, 'status_code') and resp.status_code == 200:
            return resp.text
        return None

    def fix_url(self, url):
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

    def _parse_list_items(self, html, limit=20):
        doc = BeautifulSoup(html, 'html.parser')
        videos = []
        items = doc.select('.movie1_list ul li')
        if not items:
            items = doc.find_all('li')
        
        for li in items:
            a = li.find('a', href=True)
            if not a:
                continue
            href = a.get('href', '')
            if 'vod-detail-id' not in href:
                continue
            vid_match = re.search(r'vod-detail-id-(\d+)\.html', href)
            if not vid_match:
                continue
            vod_id = vid_match.group(1)
            
            h3 = li.find('h3')
            title = ''
            if h3:
                title = h3.text.strip()
            if not title:
                title = a.get('title', '').strip()
            if not title:
                title = a.text.strip()
            
            img = li.find('img')
            pic = img.get('src') or img.get('data-src', '') if img else ''
            pic = self.fix_url(pic)
            
            remark = ''
            span = li.find('span', class_='movie_date')
            if span:
                remark = span.text.strip()
            if not remark:
                if '[' in title and ']' in title:
                    m = re.search(r'\[([^\]]+)\]', title)
                    if m:
                        remark = m.group(1)
            
            if vod_id and title:
                videos.append({
                    'vod_id': vod_id,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })
                if len(videos) >= limit:
                    break
        return videos

    def homeContent(self, filter=False):
        self.classes = [
            {"type_id": "zone1", "type_name": "在线一区"},
            {"type_id": "zone2", "type_name": "在线二区"},
            {"type_id": "zone3", "type_name": "在线三区"},
        ]
        self.filters = {
            "zone1": [
                {
                    "key": "cate",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "国产精品", "v": "16"},
                        {"n": "中文字幕", "v": "17"},
                        {"n": "国产传媒", "v": "18"},
                        {"n": "日韩无码", "v": "19"},
                        {"n": "日韩精品", "v": "20"},
                        {"n": "欧美情色", "v": "21"},
                        {"n": "强奸乱伦", "v": "22"},
                        {"n": "三级伦理", "v": "23"},
                    ]
                }
            ],
            "zone2": [
                {
                    "key": "cate",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "卡通动漫", "v": "24"},
                        {"n": "自拍偷拍", "v": "25"},
                        {"n": "明星换脸", "v": "26"},
                        {"n": "人妻系列", "v": "27"},
                        {"n": "制服诱惑", "v": "28"},
                        {"n": "巨乳系列", "v": "29"},
                        {"n": "颜射系列", "v": "30"},
                        {"n": "口交视频", "v": "31"},
                    ]
                }
            ],
            "zone3": [
                {
                    "key": "cate",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "教师学生", "v": "32"},
                        {"n": "精品探花", "v": "33"},
                        {"n": "精品网红", "v": "34"},
                        {"n": "熟女少妇", "v": "35"},
                        {"n": "SM重味", "v": "36"},
                        {"n": "黑料网曝", "v": "37"},
                        {"n": "颜值正义", "v": "38"},
                        {"n": "大秀视频", "v": "39"},
                    ]
                }
            ]
        }
        return {'class': self.classes, 'filters': self.filters}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self.get_html(self.host + '/')
        if not html:
            return {'list': []}
        videos = self._parse_list_items(html, 20)
        return {'list': videos}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = int(pg) if pg else 1
        
        cate_id = None
        if extend:
            if isinstance(extend, dict):
                cate_id = extend.get('cate', '')
            elif isinstance(extend, str):
                try:
                    ext = json.loads(extend)
                    cate_id = ext.get('cate', '')
                except:
                    if '=' in extend:
                        parts = extend.split('=')
                        if len(parts) == 2 and parts[0] == 'cate':
                            cate_id = parts[1]
        
        zone_map = {
            'zone1': ['16','17','18','19','20','21','22','23'],
            'zone2': ['24','25','26','27','28','29','30','31'],
            'zone3': ['32','33','34','35','36','37','38','39'],
        }
        
        if tid in zone_map:
            if cate_id and cate_id in zone_map.get(tid, []):
                actual_tid = cate_id
            else:
                actual_tid = zone_map[tid][0]
        else:
            actual_tid = tid
        
        url = f"{self.host}/?m=vod-type-id-{actual_tid}.html"
        if page > 1:
            url = f"{self.host}/?m=vod-type-id-{actual_tid}-pg-{page}.html"
        
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': 20, 'total': 0}
        
        videos = self._parse_list_items(html, 20)
        
        pagecount = 1
        total = 0
        doc = BeautifulSoup(html, 'html.parser')
        page_info = doc.find(string=re.compile(r'共\d+条数据'))
        if page_info:
            m = re.search(r'共(\d+)条数据\s*当前:(\d+)/(\d+)页', page_info)
            if m:
                total = int(m.group(1))
                pagecount = int(m.group(3))
        
        return {
            'list': videos,
            'page': page,
            'pagecount': pagecount,
            'limit': 20,
            'total': total
        }

    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        if isinstance(ids, list):
            vod_id = str(ids[0])
        else:
            vod_id = str(ids)
        url = f"{self.host}/?m=vod-detail-id-{vod_id}.html"
        html = self.get_html(url)
        if not html:
            return {'list': []}
        
        doc = BeautifulSoup(html, 'html.parser')
        
        title = ''
        title_dd = doc.find('dd', class_='film_title')
        if title_dd:
            title = title_dd.text.strip()
        
        pic = ''
        img = doc.select_one('.film_info dl dt img')
        if img:
            pic = img.get('src', '')
            pic = self.fix_url(pic)
        
        category = ''
        for dd in doc.find_all('dd'):
            if '類型：' in dd.text:
                category = dd.text.replace('類型：', '').strip()
                break
        
        content = ''
        content_div = doc.find('div', class_='film_info_r')
        if content_div:
            content = content_div.text.strip()
        
        play_links = []
        play_bar = doc.find('div', class_='film_bar')
        if play_bar:
            for a in play_bar.find_all('a', href=True):
                href = a.get('href', '')
                if 'vod-play-id' in href:
                    src_match = re.search(r'src-(\d+)', href)
                    num_match = re.search(r'num-(\d+)', href)
                    src = src_match.group(1) if src_match else '1'
                    num = num_match.group(1) if num_match else '1'
                    name = a.text.strip() or '正片'
                    play_links.append({
                        'name': name,
                        'src': src,
                        'num': num,
                        'href': href
                    })
        
        play_url_parts = []
        play_from_parts = []
        
        if play_links:
            lines = {}
            for pl in play_links:
                src = pl['src']
                if src not in lines:
                    lines[src] = []
                lines[src].append(pl)
            
            for src, items in lines.items():
                if items:
                    urls = []
                    for item in items:
                        play_href = item['href']
                        full_play_url = self.host + play_href if play_href.startswith('/') else play_href
                        urls.append(f"{item['name']}${full_play_url}")
                    play_url_parts.append('#'.join(urls))
                    from_name = f"线路{src}"
                    if len(items) == 1:
                        from_name = items[0]['name']
                    play_from_parts.append(from_name)
        
        if not play_url_parts:
            play_from_parts = ['默认线路']
            play_url_parts = [f'正片$/{vod_id}']
        
        data = {
            'vod_id': vod_id,
            'vod_name': title or '未知视频',
            'vod_pic': pic,
            'vod_content': content,
            'vod_actor': '',
            'vod_director': '',
            'vod_play_from': '$$$'.join(play_from_parts),
            'vod_play_url': '$$$'.join(play_url_parts),
        }
        return {'list': [data]}

    def searchContent(self, key, quick=False, pg='1'):
        if not key:
            return {'list': [], 'page': 1, 'pagecount': 1, 'total': 0}
        
        page = int(pg) if pg else 1
        search_url = f"{self.host}/index.php?m=vod-search"
        data = {'wd': key}
        resp = self.post_fetch(search_url, data=data, headers=self.headers)
        if not resp or not hasattr(resp, 'text'):
            return {'list': [], 'page': page, 'pagecount': 1, 'total': 0}
        
        html = resp.text
        videos = self._parse_list_items(html, 20)
        return {'list': videos, 'page': page, 'pagecount': 1, 'total': 0}

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址"""
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {'parse': 1, 'url': ''}
        
        if id.startswith('http') and (id.endswith('.m3u8') or id.endswith('.mp4')):
            if id.endswith('.m3u8'):
                return {
                    'parse': 0,
                    'url': self._m3u8_proxy_url(id),
                    'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}
                }
            return {
                'parse': 0,
                'url': id,
                'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}
            }
        
        if 'vod-play-id' in id or id.startswith('/?m=vod-play'):
            if not id.startswith('http'):
                id = self.host + id if id.startswith('/') else self.host + '/' + id
            html = self.get_html(id)
            if html:
                patterns = [
                    r"mac_url=unescape\('([^']+)'\)",
                    r'mac_url=unescape\("([^"]+)"\)',
                    r"var\s+mac_url\s*=\s*unescape\('([^']+)'\)",
                    r'mac_url\s*=\s*["\']([^"\']+)["\']'
                ]
                for pattern in patterns:
                    m = re.search(pattern, html)
                    if m:
                        mac_url = m.group(1)
                        try:
                            decoded = re.sub(r'%u([0-9A-Fa-f]{4})', lambda x: chr(int(x.group(1), 16)), mac_url)
                            decoded = re.sub(r'%([0-9A-Fa-f]{2})', lambda x: chr(int(x.group(1), 16)), decoded)
                            decoded = re.sub(r'\\u([0-9A-Fa-f]{4})', lambda x: chr(int(x.group(1), 16)), decoded)
                        except Exception as e:
                            decoded = mac_url
                        url_match = re.search(r'([^$]+)\$(https?://[^\s]+)', decoded)
                        if url_match:
                            play_url = url_match.group(2)
                            if play_url.endswith('.m3u8'):
                                return {
                                    'parse': 0,
                                    'url': self._m3u8_proxy_url(play_url),
                                    'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}
                                }
                            return {
                                'parse': 0,
                                'url': play_url,
                                'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}
                            }
                        if decoded.startswith('http'):
                            if decoded.endswith('.m3u8'):
                                return {
                                    'parse': 0,
                                    'url': self._m3u8_proxy_url(decoded),
                                    'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}
                                }
                            return {
                                'parse': 0,
                                'url': decoded,
                                'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}
                            }
        
        if id.startswith('http'):
            html = self.get_html(id)
            if html:
                patterns = [
                    r"mac_url=unescape\('([^']+)'\)",
                    r'mac_url=unescape\("([^"]+)"\)',
                    r"var\s+mac_url\s*=\s*unescape\('([^']+)'\)",
                ]
                for pattern in patterns:
                    m = re.search(pattern, html)
                    if m:
                        mac_url = m.group(1)
                        try:
                            decoded = re.sub(r'%u([0-9A-Fa-f]{4})', lambda x: chr(int(x.group(1), 16)), mac_url)
                            decoded = re.sub(r'%([0-9A-Fa-f]{2})', lambda x: chr(int(x.group(1), 16)), decoded)
                            decoded = re.sub(r'\\u([0-9A-Fa-f]{4})', lambda x: chr(int(x.group(1), 16)), decoded)
                        except:
                            decoded = mac_url
                        url_match = re.search(r'([^$]+)\$(https?://[^\s]+)', decoded)
                        if url_match:
                            play_url = url_match.group(2)
                            if play_url.endswith('.m3u8'):
                                return {
                                    'parse': 0,
                                    'url': self._m3u8_proxy_url(play_url),
                                    'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}
                                }
                            return {
                                'parse': 0,
                                'url': play_url,
                                'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}
                            }
        
        return {
            'parse': 1,
            'url': id if id.startswith('http') else self.host + '/?m=vod-detail-id-' + id + '.html',
            'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}
        }

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI（补全绝对地址）"""
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
        """清洗m3u8 - 过滤广告分片（参照王室日报实现）"""
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

                # 过滤逻辑：判断分片路径是否以正片目录开头
                is_ad = not media_parsed.path.startswith(main_dir)

                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                else:
                    removed += 1
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urllib.parse.urljoin(source_url, line))
            else:
                segments.append(line)

        # 二次清洗：去除孤立的 #EXT-X-DISCONTINUITY 和 KEY:METHOD=NONE
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

        if removed:
            print('m3u8 已过滤广告分片: %d 个' % removed)

        return "\n".join(out) + "\n"

    def localProxy(self, param):
        """
        m3u8本地代理 - 广告分片过滤
        """
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

            resp = self.fetch(target, headers=self.headers, timeout=20)
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
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]