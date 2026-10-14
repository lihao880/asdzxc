# -*- coding: utf-8 -*-
# 榴莲视频 - TVBox/FongMi 爬虫
# 站点: https://www.llsp.me/
# 类型: 自研PHP模板（MacCMS风格播放器）
# 开发日期: 2026-07-29

import re
import json
import urllib.parse
from base.spider import Spider


class Spider(Spider):
    """榴莲视频爬虫 - TVBox/FongMi"""
    
    def __init__(self):
        self.base_url = 'https://www.llsp.me'
        self.site_name = '榴莲视频'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.base_url,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.timeout = 15
        # 分类列表（从导航栏提取，tid 3-40，不含19）
        self.classes = [
            {'type_id': '3', 'type_name': '国产精品'},
            {'type_id': '4', 'type_name': '国产自拍'},
            {'type_id': '5', 'type_name': '国产偷拍'},
            {'type_id': '6', 'type_name': '探花视频'},
            {'type_id': '7', 'type_name': '主播福利'},
            {'type_id': '8', 'type_name': '丝袜恋足'},
            {'type_id': '9', 'type_name': '网红爆料'},
            {'type_id': '10', 'type_name': '明星换脸'},
            {'type_id': '11', 'type_name': '母狗调教'},
            {'type_id': '12', 'type_name': '国产乱伦'},
            {'type_id': '13', 'type_name': '学生嫩妹'},
            {'type_id': '14', 'type_name': '人妻少妇'},
            {'type_id': '15', 'type_name': '港台美女'},
            {'type_id': '16', 'type_name': '抖阴视频'},
            {'type_id': '17', 'type_name': '麻豆传媒'},
            {'type_id': '18', 'type_name': '日韩情色'},
            {'type_id': '20', 'type_name': '日本无码'},
            {'type_id': '21', 'type_name': '韩国无码'},
            {'type_id': '22', 'type_name': '欧美无码'},
            {'type_id': '23', 'type_name': '中文字幕'},
            {'type_id': '24', 'type_name': '黄色动漫'},
            {'type_id': '25', 'type_name': '三级伦理'},
            {'type_id': '26', 'type_name': '香港三级'},
            {'type_id': '27', 'type_name': '韩国三级'},
            {'type_id': '28', 'type_name': '丝袜制服'},
            {'type_id': '29', 'type_name': '童颜巨乳'},
            {'type_id': '30', 'type_name': '熟女人妻'},
            {'type_id': '31', 'type_name': '少女萝莉'},
            {'type_id': '32', 'type_name': '强奸乱伦'},
            {'type_id': '33', 'type_name': '变态调教'},
            {'type_id': '34', 'type_name': '女优高清'},
            {'type_id': '35', 'type_name': '淫乱群交'},
            {'type_id': '36', 'type_name': '口交颜射'},
            {'type_id': '37', 'type_name': '男同女同'},
            {'type_id': '38', 'type_name': '淫语解说'},
            {'type_id': '39', 'type_name': '第一视角'},
            {'type_id': '40', 'type_name': '女优大全'},
        ]
        # 该站点无筛选功能
        self.filters = {}

    def getName(self):
        return self.site_name

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 从国产精品分类取第一页"""
        return self.categoryContent('3', '1', False, {})

    def categoryContent(self, tid, pg, filter=False, extend=None):
        """分类列表 - 支持翻页"""
        if extend is None:
            extend = {}
        pg = str(pg) if pg else '1'
        
        # 构建URL: 第一页不带页码，后续带 -{pg}
        if pg == '1':
            url = f"{self.base_url}/vodtype/{tid}.html"
        else:
            url = f"{self.base_url}/vodtype/{tid}-{pg}.html"
        
        try:
            resp = self.fetch(url, headers=self.headers, timeout=self.timeout)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}
            
            html = resp.text
            items = self._parse_video_list(html)
            
            # 提取总页数
            pagecount = 1
            total = len(items)
            # 从分页控件提取总页数
            page_match = re.search(r'当前(\d+)/(\d+)页', html)
            if page_match:
                total = int(page_match.group(2)) * 20
                pagecount = int(page_match.group(2))
            
            return {
                "list": items,
                "page": int(pg),
                "pagecount": pagecount,
                "limit": 20,
                "total": total
            }
        except Exception as e:
            self.log(f"categoryContent error: {str(e)}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}

    def _parse_video_list(self, html):
        """解析视频列表"""
        items = []
        # 匹配视频卡片
        pattern = r'<div class="col-style[^"]*"[^>]*>.*?<a href="([^"]+)" class="videoBox"[^>]*title="([^"]*)">.*?<img[^>]*src="([^"]*)"[^>]*>.*?<span class="title"[^>]*>([^<]*)</span>.*?<span class="number">([^<]*)</span>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for match in matches:
            href, title1, img, title2, date = match
            vid = href.split('/')[-1].replace('.html', '') if href else ''
            # 从href提取vod_id: /vodplay/968702-1-1.html -> 968702
            vid_match = re.search(r'/vodplay/(\d+)', href)
            if vid_match:
                vid = vid_match.group(1)
            # 优先使用img中的url，可能是懒加载
            pic = img if img else ''
            title = title1 or title2 or '未知'
            remark = date if date else ''
            # 构建详情页URL
            vod_url = self.base_url + href if href.startswith('/') else href
            
            items.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": remark,
                "vod_url": vod_url
            })
        
        return items

    def detailContent(self, ids):
        """获取视频详情 - 从详情页提取播放地址"""
        result = []
        for vid in ids:
            try:
                # 构建详情页URL
                url = f"{self.base_url}/vodplay/{vid}-1-1.html"
                resp = self.fetch(url, headers=self.headers, timeout=self.timeout)
                if not resp or resp.status_code != 200:
                    continue
                html = resp.text
                
                # 提取标题
                title_match = re.search(r'<h1[^>]*class="video-title"[^>]*>([^<]*)</h1>', html)
                title = title_match.group(1).strip() if title_match else ''
                
                # 提取分类
                class_match = re.search(r'视频分类[：:]\s*<a[^>]*>([^<]*)</a>', html)
                class_name = class_match.group(1).strip() if class_match else ''
                
                # 提取播放地址 - 从 player_aaaa 中提取 url
                play_url = self._extract_player_url(html)
                
                if play_url and play_url != self.base_url and play_url != self.base_url + '/':
                    # 构建播放数据
                    play_from = "线路1"
                    play_url_str = f"播放${play_url}"
                    vod = {
                        "vod_id": vid,
                        "vod_name": title or f"视频{vid}",
                        "vod_pic": "",
                        "vod_remarks": "",
                        "vod_content": f"分类: {class_name}" if class_name else "",
                        "vod_play_from": play_from,
                        "vod_play_url": play_url_str
                    }
                else:
                    # 无播放地址时返回空
                    vod = {
                        "vod_id": vid,
                        "vod_name": title or f"视频{vid}",
                        "vod_pic": "",
                        "vod_remarks": "",
                        "vod_content": "无播放地址",
                        "vod_play_from": "",
                        "vod_play_url": ""
                    }
                result.append(vod)
            except Exception as e:
                self.log(f"detailContent error for {vid}: {str(e)}")
                result.append({
                    "vod_id": vid,
                    "vod_name": f"视频{vid}",
                    "vod_pic": "",
                    "vod_remarks": "",
                    "vod_content": f"获取失败: {str(e)}",
                    "vod_play_from": "",
                    "vod_play_url": ""
                })
        
        return {"list": result}

    def _extract_player_url(self, html):
        """从详情页提取播放地址 - 从 player_aaaa 中提取 url 字段"""
        # 定位 player_aaaa 对象，然后提取其中的 url
        player_match = re.search(r'var\s+player_aaaa\s*=\s*({[^}]*"url"\s*:\s*"([^"]+)"[^}]*})', html)
        if player_match:
            url = player_match.group(2)
            if url and url.startswith('http') and '.m3u8' in url:
                return url
            if url and url.startswith('http') and 'lbsl2026.com' in url:
                return url
        
        # 备选：直接用正则提取 url 字段，但要求包含 m3u8 特征
        url_match = re.search(r'"url"\s*:\s*"([^"]*\.m3u8[^"]*)"', html)
        if url_match:
            return url_match.group(1)
        
        # 从 iframe src 提取
        iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"[^>]*>', html)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            if iframe_url.startswith('http'):
                return iframe_url
        
        # 从 video 标签提取
        video_match = re.search(r'<video[^>]*src="([^"]+)"', html)
        if video_match:
            return video_match.group(1)
        
        return None

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址"""
        from urllib.parse import quote
        # 清理URL中的反斜杠转义
        url = str(url or "").replace('\\/', '/')
        return self.getProxyUrl() + "&url=" + quote(url, safe=":/")

    def playerContent(self, flag, id, vipFlags=None):
        """播放器 - 返回直链，m3u8走代理过滤广告"""
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        
        # 如果已经是完整URL
        if id.startswith('http'):
            # m3u8地址走代理过滤广告
            if '.m3u8' in id.lower():
                return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": self.headers}
            return {"parse": 0, "url": id, "header": self.headers}
        
        # 如果是相对路径，补全
        if id.startswith('/'):
            full_url = self.base_url + id
            if '.m3u8' in full_url.lower():
                return {"parse": 0, "url": self._m3u8_proxy_url(full_url), "header": self.headers}
            return {"parse": 0, "url": full_url, "header": self.headers}
        
        # 作为播放ID处理
        return {"parse": 1, "url": id, "header": self.headers}

    def localProxy(self, param):
        """m3u8本地代理 + 广告分片过滤"""
        from urllib.parse import unquote
        import re
        
        target = unquote(str((param or {}).get("url", "") or ""))
        if not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]
        try:
            res = self.fetch(target, headers={"User-Agent": self.headers["User-Agent"]}, timeout=15, verify=False)
            if not res or getattr(res, "status_code", 0) != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            raw = getattr(res, "content", b"") or b""
            text = raw.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log("m3u8广告过滤失败: " + str(e))
            return [500, "text/plain", b"m3u8 proxy error"]

    def _clean_m3u8(self, text, source_url):
        """清洗m3u8：过滤广告分片"""
        from urllib.parse import urlparse, urljoin
        import re
        
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"
        
        # 主清单：子清单补成绝对地址并代理
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"
        
        # 分片清单：提取正片资源目录
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
        
        # 清理无效标记
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
            self.log("m3u8已过滤广告分片: %d" % removed)
        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI（补全绝对地址）"""
        from urllib.parse import urljoin
        import re
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                return 'URI="' + urljoin(source_url, match.group(1)) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            return urljoin(source_url, line)
        return line

    def searchContent(self, key, quick, pg="1"):
        """搜索 - 通过搜索接口"""
        pg = str(pg) if pg else '1'
        encoded_key = urllib.parse.quote(key)
        url = f"{self.base_url}/vodsearch/{encoded_key}-.html"
        
        try:
            resp = self.fetch(url, headers=self.headers, timeout=self.timeout)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": int(pg)}
            
            html = resp.text
            items = self._parse_video_list(html)
            
            return {"list": items, "page": int(pg)}
        except Exception as e:
            self.log(f"searchContent error: {str(e)}")
            return {"list": [], "page": int(pg)}

    def isVideoFormat(self, url):
        """判断是否为视频直链"""
        if not url:
            return False
        video_exts = ('.m3u8', '.mp4', '.flv', '.ts', '.m4s')
        return url.lower().endswith(video_exts)

    def destroy(self):
        pass