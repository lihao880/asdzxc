# coding: utf-8
# 站点: 色污影视
# 域名: https://www.swys4.ink
# 系统: MacCMS
# 类型: 成人影视站
# 特点: 播放地址为直链m3u8，需广告过滤

import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.swys4.ink"
        self.base_path = "/cn/home/web"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.classes = [
            {"type_id": "20", "type_name": "国产自拍"},
            {"type_id": "21", "type_name": "制服丝袜"},
            {"type_id": "22", "type_name": "强奸乱伦"},
            {"type_id": "23", "type_name": "教师学生"},
            {"type_id": "24", "type_name": "素人系列"},
            {"type_id": "25", "type_name": "人妻熟女"},
            {"type_id": "26", "type_name": "日韩无码"},
            {"type_id": "27", "type_name": "日韩有码"},
            {"type_id": "28", "type_name": "中文字幕"},
            {"type_id": "29", "type_name": "欧美风情"},
            {"type_id": "30", "type_name": "经典伦理"},
            {"type_id": "31", "type_name": "卡通动漫"},
        ]
        self.filters = {
            "20": [], "21": [], "22": [], "23": [], "24": [], "25": [],
            "26": [], "27": [], "28": [], "29": [], "30": [], "31": [],
        }
        self.ad_dirs = ['cUUPOTlS']

    def getName(self):
        return "色污影视"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""
        pass

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        result = self.categoryContent("20", "1", False, {})
        return {"list": result.get("list", [])}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}{self.base_path}/index.php/vod/show/id/{tid}/page/{page}.html"
        resp = self.fetch(url, headers=self.headers)
        if not resp:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        html = getattr(resp, "content", b"").decode("utf-8", errors="ignore")
        return self._parse_category_list(html, page)

    def _parse_category_list(self, html, page):
        items = []
        # 方法1: 匹配 li.index
        li_pattern = r'<li[^>]*class="[^"]*index[^"]*"[^>]*>(.*?)</li>'
        li_matches = re.findall(li_pattern, html, re.DOTALL)
        for li_html in li_matches:
            link_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*stui-vodlist__thumb', li_html)
            if not link_match:
                link_match = re.search(r'<h4[^>]*class="[^"]*title[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"', li_html, re.DOTALL)
            if not link_match:
                continue
            link = link_match.group(1)
            title_match = re.search(r'<a[^>]*title="([^"]+)"', li_html)
            if not title_match:
                continue
            title = title_match.group(1).strip()
            pic_match = re.search(r'data-original="([^"]+)"', li_html)
            pic = pic_match.group(1) if pic_match else ""
            score_match = re.search(r'<span[^>]*class="score[^"]*"[^>]*>([^<]+)</span>', li_html)
            score = score_match.group(1).strip() if score_match else ""
            remark_match = re.search(r'<span[^>]*class="pic-text[^"]*"[^>]*>([^<]+)</span>', li_html)
            remark = remark_match.group(1).strip() if remark_match else ""
            vod_id = self._extract_vod_id(link)
            if vod_id and title:
                items.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": self._fix_url(pic),
                    "vod_remarks": remark or score,
                })
        # 方法2: 直接匹配视频卡片
        if not items:
            pattern = r'<a[^>]*href="(/cn/home/web/index.php/vod/play/id/\d+/sid/1/nid/1\.html)"[^>]*title="([^"]+)"[^>]*data-original="([^"]+)"'
            matches = re.findall(pattern, html, re.DOTALL)
            for link, title, pic in matches:
                vod_id = self._extract_vod_id(link)
                if vod_id and title:
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": title,
                        "vod_pic": self._fix_url(pic),
                        "vod_remarks": "",
                    })
        pagecount = 1
        total = 0
        page_match = re.search(r'class="active num"[^>]*><a[^>]*>([^/]+)/([^<]+)</a>', html)
        if page_match:
            pagecount = int(page_match.group(2))
            total = int(page_match.group(2)) * 20
        return {"list": items, "page": int(page), "pagecount": pagecount, "limit": 20, "total": total}
    def _extract_play_url(self, html):
        """从HTML中提取播放地址"""
        if not html:
            return None
        # 方法1: 从 player_data 中提取
        match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
        if match:
            url = match.group(1)
            url = url.replace("\\/", "/")
            if url.startswith("http"):
                return url
        # 方法2: 匹配 var player_data = {...}
        match = re.search(r'var\s+player_data\s*=\s*({[^;]+});', html, re.DOTALL)
        if match:
            try:
                js_obj = match.group(1)
                js_obj = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', js_obj)
                data = json.loads(js_obj)
                url = data.get("url", "")
                if url:
                    url = url.replace("\\/", "/")
                if url and url.startswith("http") and ".m3u8" in url:
                    return url
            except Exception:
                pass
        # 方法3: 直接从HTML中搜索m3u8链接
        match = re.search(r'https?://[^"\']+\.m3u8[^"\']*', html)
        if match:
            url = match.group(0)
            url = url.replace("\\/", "/")
            return url
        return None

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        real_id = self._extract_real_id(vod_id)
        if not real_id:
            real_id = vod_id
        # 改为请求播放页（play）而不是详情页（detail）
        url = f"{self.host}{self.base_path}/index.php/vod/play/id/{real_id}/sid/1/nid/1.html"
        resp = self.fetch(url, headers=self.headers)
        if not resp:
            return {"list": []}
        html = getattr(resp, "content", b"").decode("utf-8", errors="ignore")
        return self._parse_play_page(html, real_id)

    def _parse_detail(self, html, vod_id):
        title_match = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>', html)
        title = title_match.group(1).strip() if title_match else "未知视频"
        score_match = re.search(r'([\d.]+)\s*分', html)
        score = score_match.group(1) if score_match else ""
        pic_match = re.search(r'data-original="([^"]+)"', html)
        pic = pic_match.group(1) if pic_match else ""
        play_data_match = re.search(r'var\s+player_data\s*=\s*({[^;]+});', html)
        play_url = ""
        play_from = "播放"
        if play_data_match:
            try:
                data = json.loads(play_data_match.group(1))
                play_url = data.get("url", "")
                play_from = data.get("from", "播放")
            except:
                pass
        if not play_url:
            m3u8_match = re.search(r'https?://[^\s"\']+\.m3u8', html)
            if m3u8_match:
                play_url = m3u8_match.group(0)
        if play_url:
            vod_play_from = play_from
            vod_play_url = f"第1集${play_url}"
        else:
            vod_play_from = ""
            vod_play_url = ""
        content_match = re.search(r'<p[^>]*>简介：</p>\s*<p[^>]*>([^<]+)</p>', html)
        vod_content = content_match.group(1).strip() if content_match else ""
        vod = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": self._fix_url(pic),
            "vod_remarks": score,
            "vod_content": vod_content,
            "vod_actor": "",
            "vod_director": "",
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url,
        }
        return {"list": [vod]}
    def _parse_play_page(self, html, vod_id):
        """解析播放页（详情+播放地址）"""
        if not html:
            return {"list": []}
        # 提取标题
        title_match = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>', html)
        title = title_match.group(1).strip() if title_match else "未知视频"
        # 提取评分
        score_match = re.search(r'([\d.]+)\s*分', html)
        score = score_match.group(1) if score_match else ""
        # 提取封面
        pic_match = re.search(r'data-original="([^"]+)"', html)
        pic = pic_match.group(1) if pic_match else ""
        # 提取播放地址 - 使用与勃士相同的方式
        play_url = self._extract_play_url(html)
        if play_url:
            vod_play_from = "播放"
            vod_play_url = f"第1集${play_url}"
        else:
            vod_play_from = ""
            vod_play_url = ""
        vod = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": self._fix_url(pic),
            "vod_remarks": score,
            "vod_content": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url,
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        if not key:
            return {"list": [], "page": 1}
        page = pg or "1"
        # 编码关键词
        encoded_key = urllib.parse.quote(key.encode("utf-8"), safe="")
        # 构造搜索URL
        url = f"{self.host}{self.base_path}/index.php/vod/search/wd/{encoded_key}.html"
        if int(page) > 1:
            url = f"{self.host}{self.base_path}/index.php/vod/search/page/{page}.html?wd={encoded_key}"
        self.log(f"搜索URL: {url}")
        resp = self.fetch(url, headers=self.headers)
        if not resp:
            self.log("搜索请求失败")
            return {"list": [], "page": int(page)}
        html = getattr(resp, "content", b"").decode("utf-8", errors="ignore")
        # 使用与分类列表相同的解析方法
        result = self._parse_category_list(html, page)
        self.log(f"搜索结果数量: {len(result.get('list', []))}")
        return {"list": result.get("list", []), "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        """播放地址 - 所有m3u8走代理过滤广告"""
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        if id.startswith(("http://", "https://")):
            if ".m3u8" in id:
                # 走代理过滤广告分片
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(id),
                    "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": self.host + "/",
                    }
                }
            return {
                "parse": 0,
                "url": id,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/",
                }
            }
        if id.startswith("/"):
            url = self.host + id
        else:
            url = self.host + self.base_path + "/index.php/vod/play/id/" + id + "/sid/1/nid/1.html"
        resp = self.fetch(url, headers=self.headers)
        if resp:
            html = getattr(resp, "content", b"").decode("utf-8", errors="ignore")
            play_url = self._extract_play_url(html)
            if play_url and ".m3u8" in play_url:
                # 走代理过滤广告分片
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(play_url),
                    "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": self.host + "/",
                    }
                }
        return {
            "parse": 1,
            "url": url,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
            }
        }

    def _m3u8_proxy_url(self, url):
        """生成代理地址 - 避免重复拼接参数"""
        if not url:
            return ""
        proxy_base = self.getProxyUrl()
        # 检查 proxy_base 是否已包含 do=py
        if 'do=py' in proxy_base:
            # 已有 do=py，直接用 & 拼接 target
            if '?' in proxy_base:
                return proxy_base + "&target=" + urllib.parse.quote(str(url or ""), safe="")
            else:
                return proxy_base + "?target=" + urllib.parse.quote(str(url or ""), safe="")
        else:
            # 没有 do=py，添加 do=py 和 target
            if '?' in proxy_base:
                return proxy_base + "&do=py&target=" + urllib.parse.quote(str(url or ""), safe="")
            else:
                return proxy_base + "?do=py&target=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        """本地代理 - 支持 do=py&target= 格式"""
        self.log(f"localProxy 收到参数: {param}")
        target = ""
        # 处理各种参数格式
        if isinstance(param, dict):
            # 优先取 target，然后是 url，然后是 source，最后才是 do
            target = param.get("target", "") or param.get("url", "") or param.get("source", "") or param.get("do", "")
            self.log(f"从 dict 提取 target: {target}")
        elif isinstance(param, str):
            target = param
            self.log(f"从 str 提取 target: {target}")
        else:
            target = str(param or "")
            self.log(f"从其他类型提取 target: {target}")
        
        # 如果 target 是 "do=py&target=..." 格式，解析出真正的 target
        if target.startswith("do=py&target="):
            target = target[13:]
            self.log(f"去掉 do=py&target= 后: {target}")
        elif target.startswith("do=py"):
            import urllib.parse as urlparse
            parsed = urlparse.parse_qs(target)
            if "target" in parsed:
                target = parsed["target"][0]
                self.log(f"从查询字符串提取 target: {target}")
            elif "url" in parsed:
                target = parsed["url"][0]
                self.log(f"从查询字符串提取 url: {target}")
        elif target.startswith("target="):
            target = target[7:]
            self.log(f"去掉 target= 后: {target}")
        
        target = urllib.parse.unquote(str(target or ""))
        self.log(f"URL解码后 target: {target}")
        
        # 如果还是没有 target，尝试从原始 param 中提取
        if not target and isinstance(param, dict):
            for key in ["target", "url", "source", "u", "do"]:
                if key in param and param[key]:
                    val = str(param[key])
                    if "target=" in val:
                        target = val.split("target=")[-1].split("&")[0]
                        self.log(f"从 {key} 中提取 target: {target}")
                    elif "url=" in val:
                        target = val.split("url=")[-1].split("&")[0]
                        self.log(f"从 {key} 中提取 url: {target}")
                    else:
                        target = val
                        self.log(f"从 {key} 直接取值: {target}")
                    break
        
        target = urllib.parse.unquote(str(target or ""))
        self.log(f"最终 target: {target}")
        
        if not target or not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", f"invalid url: {target}".encode("utf-8")]
        
        try:
            fetch_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.swys4.ink/",
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Origin": "https://www.swys4.ink",
            }
            
            resp = self.fetch(target, headers=fetch_headers, timeout=30, verify=False)
            
            if not resp:
                self.log(f"fetch 返回空响应: target={target}")
                return [502, "text/plain", b"fetch failed - empty response"]
            
            status_code = getattr(resp, "status_code", 0)
            if status_code != 200:
                self.log(f"fetch 返回非200状态码: {status_code}, target={target}")
                return [502, "text/plain", f"fetch failed - status {status_code}".encode("utf-8")]
            
            content = getattr(resp, "content", b"") or b""
            if not content:
                self.log(f"fetch 返回空内容: target={target}")
                return [502, "text/plain", b"empty content"]
            
            self.log(f"fetch 成功，内容长度: {len(content)}, 是否m3u8: {b'#EXTM3U' in content[:256]}")
            
            if b"#EXTM3U" in content[:256]:
                text = content.decode("utf-8", errors="ignore")
                cleaned = self._clean_m3u8(text, target)
                self.log(f"m3u8 清洗完成，原始长度: {len(text)}, 清洗后长度: {len(cleaned)}")
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            
            content_type = "application/octet-stream"
            if target.endswith(".ts"):
                content_type = "video/mp2t"
            elif target.endswith(".m3u8"):
                content_type = "application/vnd.apple.mpegurl"
            elif target.endswith(".mp4"):
                content_type = "video/mp4"
            elif target.endswith(".key") or target.endswith(".bin"):
                content_type = "application/octet-stream"
            return [200, content_type, content]
            
        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            self.log(f"localProxy 异常: {str(e)}")
            return [500, "text/plain", error_msg]

    def _clean_m3u8(self, text, source_url):
        """清洗m3u8：过滤广告分片（基于目录特征）"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"
        
        # 检查是否为多码率 Master Playlist
        is_multi = any(line.startswith("#EXT-X-STREAM-INF") for line in lines)
        if is_multi:
            # 多码率：将子流URL替换为代理地址，让播放器通过代理请求子流
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    # 补全子流路径为绝对路径，然后转为代理地址
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child))
            self.log("多码率playlist，子流已转换为代理地址")
            return "\n".join(out) + "\n"
        
        # 单码率 - 过滤广告分片
        result = []
        pending_extinf = []
        removed = 0
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
                        is_ad = False
                        for ad_dir in self.ad_dirs:
                            if ad_dir in media_url:
                                is_ad = True
                                break
                        if not is_ad:
                            source_path = urllib.parse.urlparse(source_url).path
                            media_path = urllib.parse.urlparse(media_url).path
                            if source_path and media_path:
                                source_parts = [p for p in source_path.split("/") if p]
                                media_parts = [p for p in media_path.split("/") if p]
                                if len(source_parts) >= 2 and len(media_parts) >= 2:
                                    if source_parts[0] != media_parts[0]:
                                        is_ad = True
                        if is_ad:
                            removed += 1
                            self.log(f"过滤广告分片: {media_url}")
                        else:
                            if media_url.endswith('.jpg'):
                                media_url = media_url[:-4] + '.ts'
                            result.extend(pending_extinf)
                            result.append(media_url)
                        i += 1
                        break
                continue
            result.append(line)
            i += 1
        
        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个")
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
        if not link:
            return None
        match = re.search(r'/vod/play/id/(\d+)/', link)
        if match:
            return match.group(1)
        match = re.search(r'/vod/detail/id/(\d+)\.html', link)
        if match:
            return match.group(1)
        match = re.search(r'play/id/(\d+)', link)
        if match:
            return match.group(1)
        return link

    def _extract_real_id(self, vod_id):
        if not vod_id:
            return None
        if '|' in vod_id or '$' in vod_id:
            return vod_id.split('|')[0].split('$')[0]
        return vod_id

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith(("http://", "https://")):
            return url
        if url.startswith("/"):
            return self.host + url
        return urllib.parse.urljoin(self.host + "/", url)

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass