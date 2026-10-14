# -*- coding: utf-8 -*-
"""
欧派视频 - TVBox/FongMi 爬虫
站点: https://rfuuzj.opsp8.best
类型: 成人影视站 (HTML)
版本: 1.0
"""
import re
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup


class Spider:
    def __init__(self):
        self.host = "https://rfuuzj.opsp8.best"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/cn/home/web/',
        }
        # 分类列表 - 从首页提取
        self.classes = [
            {"type_id": "20", "type_name": "亚洲情色"},
            {"type_id": "21", "type_name": "制服师生"},
            {"type_id": "22", "type_name": "卡通动漫"},
            {"type_id": "23", "type_name": "丝袜美腿"},
            {"type_id": "24", "type_name": "强奸乱伦"},
            {"type_id": "25", "type_name": "偷拍自拍"},
            {"type_id": "29", "type_name": "人妻熟女"},
            {"type_id": "30", "type_name": "无码专区"},
            {"type_id": "32", "type_name": "自淫系列"},
            {"type_id": "36", "type_name": "国产精品"},
            {"type_id": "33", "type_name": "拳交系列"},
            {"type_id": "28", "type_name": "欧美性爱"},
            {"type_id": "31", "type_name": "SM捆绑"},
            {"type_id": "35", "type_name": "男同女同"},
            {"type_id": "26", "type_name": "4K岛国"},
            {"type_id": "27", "type_name": "中文字幕"},
            {"type_id": "37", "type_name": "三级伦理"},
        ]
        self.filters = {}

    def fetch(self, url, headers=None, timeout=15):
        """发送HTTP请求"""
        try:
            headers = headers or self.headers
            resp = requests.get(url, headers=headers, timeout=timeout)
            return resp
        except Exception as e:
            print('fetch error:', e)
            return None

    def get_html(self, url, headers=None):
        """获取HTML内容"""
        resp = self.fetch(url, headers)
        if resp and resp.status_code == 200:
            return resp.text
        return None

    def fix_url(self, url):
        """补全URL"""
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

    def _parse_video_list(self, html, limit=50):
        """解析视频列表 (首页推荐/分类列表/搜索结果)"""
        videos = []
        doc = BeautifulSoup(html, 'html.parser')
        
        # 查找视频列表 - 使用 dl 标签
        dls = doc.find_all('dl')
        for dl in dls:
            dt = dl.find('dt')
            if not dt:
                continue
            a = dt.find('a', href=True)
            if not a:
                continue
            href = a.get('href', '')
            if not href or not href.endswith('.html') or '/vodtype/' in href:
                continue
            
            # 提取视频ID
            vid = href.strip('/').replace('.html', '')
            if not vid:
                continue
            
            # 标题
            dd = dl.find('dd')
            title = ''
            if dd:
                title_a = dd.find('a')
                if title_a:
                    title = title_a.text.strip()
            if not title:
                title = a.get('title', '') or a.text.strip()
            if not title:
                continue
            
            # 封面
            img = dt.find('img')
            pic = img.get('src') or img.get('data-src', '') if img else ''
            pic = self.fix_url(pic)
            
            # 角标/备注
            remark = ''
            # 查找角标 (可能在 span 中)
            span = dt.find('span')
            if span:
                remark = span.text.strip()
            if not remark:
                # 尝试从标题中提取
                m = re.search(r'[\[（(]([^\]）)]+)[\]）)]', title)
                if m:
                    remark = m.group(1)
            
            videos.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remark
            })
            
            if len(videos) >= limit:
                break
        
        return videos

    def _parse_extend(self, extend):
        """解析 extend 参数，支持多种格式"""
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

    def homeContent(self, filter=False):
        """返回首页分类和筛选"""
        return {
            'class': self.classes,
            'filters': self.filters if filter else {}
        }

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 从亚洲情色分类获取最新内容"""
        try:
            result = self.categoryContent('20', 1, False, None)
            return {'list': result.get('list', [])[:20]}
        except Exception as e:
            print('homeVideoContent error:', e)
            return {'list': []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        """分类列表"""
        pg = int(pg) if pg else 1
        tid = str(tid)
        
        # 分页格式: /vodtype/{tid}-{pg}.html
        if pg == 1:
            url = self.host + '/vodtype/' + tid + '.html'
        else:
            url = self.host + '/vodtype/' + tid + '-' + str(pg) + '.html'
        
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        
        videos = self._parse_video_list(html, 50)
        
        # 解析分页信息
        pagecount = 1
        total = 50
        doc = BeautifulSoup(html, 'html.parser')
        
        # 查找分页链接
        pagination = doc.find('div', class_=re.compile(r'pagination'))
        if pagination:
            for a in pagination.find_all('a'):
                text = a.text.strip()
                if text.isdigit():
                    num = int(text)
                    if num > pagecount:
                        pagecount = num
                # 检查末页
                if '末页' in text or '尾页' in text:
                    href = a.get('href', '')
                    m = re.search(r'-(\d+)\.html', href)
                    if m:
                        pagecount = int(m.group(1))
        
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount or 999,
            'limit': 50,
            'total': pagecount * 50 if pagecount else 9999
        }

    def detailContent(self, ids):
        """视频详情"""
        if not ids:
            return {'list': []}
        vid = ids[0]
        
        url = self.host + '/' + vid + '.html'
        html = self.get_html(url)
        if not html:
            return {'list': []}
        
        doc = BeautifulSoup(html, 'html.parser')
        
        # 标题
        title = ''
        t = doc.find('h1')
        if t:
            title = t.text.strip()
        if not title:
            t = doc.find('title')
            if t:
                title = t.text.strip().replace(' - 欧派视频', '')
        
        # 封面
        pic = ''
        img = doc.find('img', class_=re.compile(r'img|cover|poster'))
        if not img:
            img = doc.find('img', src=re.compile(r'\.jpg|\.png|\.jpeg'))
        if img:
            pic = img.get('src') or img.get('data-src', '')
            pic = self.fix_url(pic)
        
        # 简介
        content = ''
        desc = doc.find('div', class_=re.compile(r'desc|content|intro|summary'))
        if desc:
            content = desc.text.strip()
        
        # 播放地址 - 从HTML中提取
        play_url = ''
        
        # 方法1: 查找 videoSrc 变量
        m = re.search(r'videoSrc\s*=\s*["\']([^"\']+)["\']', html)
        if m:
            play_url = m.group(1)
        
        # 方法2: 查找 m3u8 链接
        if not play_url:
            m = re.search(r'["\'](https?://[^\s"\']+\.m3u8[^\s"\']*)["\']', html)
            if m:
                play_url = m.group(1)
        
        # 方法3: 查找 iframe 中的播放地址
        if not play_url:
            iframe = doc.find('iframe', src=True)
            if iframe:
                iframe_src = iframe.get('src', '')
                if iframe_src:
                    play_url = iframe_src
        
        # 补全URL
        if play_url and not play_url.startswith('http'):
            play_url = self.fix_url(play_url)
        
        # 构造播放数据
        if play_url:
            play_from = '默认线路'
            play_url_str = '播放$' + play_url
        else:
            # 如果没有找到播放地址，使用视频ID作为降级
            play_from = '默认线路'
            play_url_str = '播放$' + vid
        
        data = {
            'vod_id': vid,
            'vod_name': title or '未知标题',
            'vod_pic': pic,
            'vod_content': content,
            'vod_play_from': play_from,
            'vod_play_url': play_url_str,
        }
        
        return {'list': [data]}

    def searchContent(self, key, quick=False, pg='1'):
        """搜索"""
        if not key:
            return {'list': [], 'page': 1, 'pagecount': 1, 'total': 0}
        
        pg = int(pg) if pg else 1
        url = self.host + '/s/index.html?wd=' + urllib.parse.quote(key)
        if pg > 1:
            url += '&pg=' + str(pg)
        
        html = self.get_html(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'total': 0}
        
        videos = self._parse_video_list(html, 50)
        
        return {
            'list': videos,
            'page': pg,
            'pagecount': 999,
            'total': 9999
        }

    def playerContent(self, flag, id, vipFlags=None):
        """播放地址"""
        if not id:
            return {'parse': 1, 'url': ''}
        
        # 如果是代理图片协议
        if id.startswith('pics://') or id.startswith('proxy://'):
            return {'parse': 1, 'url': id}
        
        # 处理播放ID
        # 格式: 名称$播放ID
        if '$' in id:
            parts = id.split('$', 1)
            play_id = parts[1] if len(parts) > 1 else parts[0]
        else:
            play_id = id
        
        # 构建请求头
        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/',
        }
        
        # 如果是直链 m3u8/mp4，走 localProxy 过滤广告
        if play_id.startswith('http'):
            if '.m3u8' in play_id or '.mp4' in play_id:
                # 通过 localProxy 代理，过滤广告分片
                proxy_url = self._m3u8_proxy_url(play_id)
                return {
                    'parse': 0,
                    'url': proxy_url,
                    'header': headers
                }
            else:
                # 尝试从播放页解析
                html = self.get_html(play_id)
                if html:
                    m = re.search(r'videoSrc\s*=\s*["\']([^"\']+)["\']', html)
                    if m:
                        url = m.group(1)
                        if url.startswith('/'):
                            url = self.host + url
                        if '.m3u8' in url or '.mp4' in url:
                            proxy_url = self._m3u8_proxy_url(url)
                            return {
                                'parse': 0,
                                'url': proxy_url,
                                'header': headers
                            }
                    m = re.search(r'["\'](https?://[^\s"\']+\.m3u8[^\s"\']*)["\']', html)
                    if m:
                        proxy_url = self._m3u8_proxy_url(m.group(1))
                        return {
                            'parse': 0,
                            'url': proxy_url,
                            'header': headers
                        }
                # 降级到 WebView 嗅探
                return {
                    'parse': 1,
                    'url': play_id,
                    'header': headers
                }
        
        # 如果不是直链，尝试拼接
        if not play_id.startswith('http'):
            url = self.host + '/' + play_id + '.html'
            html = self.get_html(url)
            if html:
                m = re.search(r'videoSrc\s*=\s*["\']([^"\']+)["\']', html)
                if m:
                    play_url = m.group(1)
                    if play_url.startswith('/'):
                        play_url = self.host + play_url
                    if '.m3u8' in play_url or '.mp4' in play_url:
                        proxy_url = self._m3u8_proxy_url(play_url)
                        return {
                            'parse': 0,
                            'url': proxy_url,
                            'header': headers
                        }
        
        # 降级
        return {
            'parse': 1,
            'url': play_id if play_id.startswith('http') else self.host + '/' + play_id + '.html',
            'header': headers
        }

    def localProxy(self, params):
        """本地代理 - 用于m3u8广告过滤"""
        try:
            # 解析参数
            if isinstance(params, dict):
                target = params.get('url', '') or params.get('source', '')
            else:
                target = str(params or '')
            
            if target.startswith('url='):
                target = target[4:]
            elif 'url=' in target:
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(target).query)
                if 'url' in qs:
                    target = qs['url'][0]
            
            target = urllib.parse.unquote(str(target or ''))
            if not target or not re.match(r'^https?://', target, re.I):
                return [400, 'text/plain', b'invalid url']
            
            # 获取内容
            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp or resp.status_code != 200:
                return [502, 'text/plain', b'fetch failed']
            
            content = resp.content
            if not content:
                return [502, 'text/plain', b'empty content']
            
            # 检查是否为 m3u8
            if b'#EXTM3U' in content[:256]:
                # 调用 m3u8 清洗
                cleaned = self._clean_m3u8(content.decode('utf-8', errors='ignore'), target)
                return [200, 'application/vnd.apple.mpegurl', cleaned.encode('utf-8')]
            
            # 非 m3u8 直接透传
            content_type = resp.headers.get('Content-Type', 'application/octet-stream')
            return [200, content_type, content]
            
        except Exception as e:
            print('localProxy error:', e)
            return [500, 'text/plain', str(e).encode('utf-8', errors='ignore')]

    def _clean_m3u8(self, text, source_url):
        """m3u8 广告过滤 - 五层管线"""
        if not text:
            return '#EXTM3U\n'
        
        # 第1层: 图片流伪装检测
        if self._is_fake_image_stream(text, source_url):
            restored = text
            # 注意：.jpeg 必须先于 .jpg 替换
            for ext in ('.png', '.jpeg', '.jpg', '.webp'):
                restored = restored.replace(ext, '.ts')
            print('检测到图片流伪装，已还原扩展名 -> .ts，跳过广告过滤')
            return restored
        
        lines = [l.strip() for l in str(text or '').replace('\r', '').split('\n') if l.strip()]
        if not lines:
            return '#EXTM3U\n'
        
        # 第2层: 多码率主表处理
        if any(l.startswith('#EXT-X-STREAM-INF') for l in lines):
            return self._clean_m3u8_multi(lines, source_url)
        
        # 第3层: 正片目录锚点
        main_dir = self._resolve_main_dir(lines, source_url)
        
        # 第4层: 分片过滤
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)
        
        # 第5层: 全滤兜底
        if kept == 0 and removed > 0:
            print('广告过滤命中全部分片，判定锚点失效，回退为不过滤模式')
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return '\n'.join(out) + '\n'
        
        if removed > 0:
            print(f'm3u8已过滤广告分片: {removed}个，保留正片: {kept}个')
        
        # 冗余标签清理
        out = self._dedup_tags(segments, source_url)
        return '\n'.join(out) + '\n'

    def _is_fake_image_stream(self, text, source_url):
        """检测是否为图片流伪装"""
        if not text or not source_url:
            return False
        
        low_url = source_url.lower()
        # 图片流服务商特征
        for sig in ('doyinapi', 'svip', 'imgcdn', 'photo', 'pic.'):
            if sig in low_url:
                return True
        
        # 检查分片扩展名
        for line in str(text or '').split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            low = line.lower().split('?')[0]
            if low.endswith(('.png', '.jpg', '.jpeg', '.webp')):
                return True
        
        return False

    def _clean_m3u8_multi(self, lines, source_url):
        """处理多码率主表"""
        out = []
        for line in lines:
            if line.startswith('#'):
                out.append(line)
                continue
            child = urllib.parse.urljoin(source_url, line)
            if '.m3u8' in child.lower():
                # 子流走代理
                out.append(self._m3u8_proxy_url(child))
            else:
                out.append(child)
        return '\n'.join(out) + '\n'

    def _m3u8_proxy_url(self, url):
        """生成代理地址"""
        if url:
            url = url.replace('\\/', '/')
        return 'http://127.0.0.1:9978/proxy?do=py&url=' + urllib.parse.quote(str(url or ''), safe='')

    def _resolve_main_dir(self, lines, source_url):
        """确定正片目录锚点"""
        import posixpath
        parsed = urllib.parse.urlparse(source_url)
        main_dir = posixpath.dirname(parsed.path)
        if not main_dir.endswith('/'):
            main_dir += '/'
        
        # 优先以 KEY URI 目录为锚点
        for line in lines:
            if not line.startswith('#EXT-X-KEY') or 'URI=' not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            key_path = urllib.parse.urlparse(
                key_uri if key_uri.startswith('http')
                else urllib.parse.urljoin(source_url, key_uri)
            ).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != '/':
                return key_dir + '/'
        
        return main_dir

    def _filter_segments(self, lines, source_url, main_dir):
        """过滤分片"""
        segments = []
        pending = []
        removed = 0
        kept = 0
        
        for line in lines:
            if line.startswith('#EXTINF'):
                pending = [line]
                continue
            if pending and line.startswith('#'):
                pending.append(line)
                continue
            if pending:
                media_url = urllib.parse.urljoin(source_url, line)
                media_path = urllib.parse.urlparse(media_url).path
                if media_path.startswith(main_dir):
                    segments.extend(pending)
                    segments.append(media_url)
                    kept += 1
                else:
                    removed += 1
                pending = []
                continue
            if line.startswith('#'):
                segments.append(line)
            else:
                segments.append(urllib.parse.urljoin(source_url, line))
        
        return segments, removed, kept

    def _dedup_tags(self, segments, source_url):
        """清理冗余标签"""
        NOISE = ('#EXT-X-DISCONTINUITY', '#EXT-X-KEY:METHOD=NONE')
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in NOISE:
                if not out or out[-1] in NOISE:
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in NOISE:
            out.pop()
        return out

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写标签中的URI"""
        if line.startswith('#EXT-X-KEY') or line.startswith('#EXT-X-MAP'):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(('http://', 'https://')):
                    return 'URI="' + uri + '"'
                return 'URI="' + urllib.parse.urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith('#'):
            if line.startswith(('http://', 'https://')):
                return line
            return urllib.parse.urljoin(source_url, line)
        return line

    def init(self, extend=''):
        """初始化"""
        pass

    def destroy(self):
        """销毁"""
        pass

    def getDependence(self):
        """依赖"""
        return ['requests', 'bs4']

    def getName(self):
        """站点名称"""
        return '欧派视频'