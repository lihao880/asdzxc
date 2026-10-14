# coding=utf-8
import json
import re
import html
import base64
import urllib.parse
from bs4 import BeautifulSoup
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def getName(self):
        return "杏娱会所"

    def __init__(self):
        self.host = "https://p1szq.xyyhs22.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C Build/UKQ1.230804.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.0.0 Mobile Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/"
        }
        
        # 分类硬编码 - 从首页导航提取
        self.classes = [
            {"type_id": "7048666", "type_name": "精品推荐"},
            {"type_id": "7058666", "type_name": "国产传媒"},
            {"type_id": "7068666", "type_name": "探花系列"},
            {"type_id": "7078666", "type_name": "偷拍自拍"},
            {"type_id": "7088666", "type_name": "熟女少妇"},
            {"type_id": "7098666", "type_name": "无码专区"},
            {"type_id": "7108666", "type_name": "欧美性爱"},
            {"type_id": "7118666", "type_name": "颜值正义"},
            {"type_id": "7348696", "type_name": "精品网红"},
            {"type_id": "7358696", "type_name": "多人群交"},
            {"type_id": "7148676", "type_name": "美乳巨乳"},
            {"type_id": "7158676", "type_name": "网曝事件"},
            {"type_id": "7168676", "type_name": "国产主播"},
            {"type_id": "7178676", "type_name": "中文字幕"},
            {"type_id": "7188676", "type_name": "制服丝袜"},
            {"type_id": "7198676", "type_name": "口交自慰"},
            {"type_id": "7208676", "type_name": "国产精品"},
            {"type_id": "7218676", "type_name": "大秀视频"},
            {"type_id": "7368696", "type_name": "S M 调教"},
            {"type_id": "7388696", "type_name": "变性伪娘"},
        ]
        
        self.filters = {}

    def init(self, extend=""):
        self.extend = extend or ""

    def _d(self, input_str):
        """解码混淆字符串：atob + escape + decodeURIComponent，并清理HTML标签"""
        try:
            # 1. Base64 解码
            decoded_bytes = base64.b64decode(input_str)
            rv = decoded_bytes.decode('utf-8', errors='ignore')
            # 2. 如果结果中包含 %XX 或 %uXXXX，继续解码
            if '%' in rv:
                rv = re.sub(r'%u([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), rv)
                rv = re.sub(r'%([0-9A-Fa-f]{2})', lambda m: chr(int(m.group(1), 16)), rv)
            # 3. 移除 display:none 的 span 标签及其内容
            rv = re.sub(r'<span[^>]*display\s*:\s*none[^>]*>.*?</span>', '', rv, flags=re.DOTALL)
            # 4. 清理剩余的 HTML 标签
            rv = re.sub(r'<[^>]+>', '', rv)
            # 5. 解码 HTML 实体
            rv = html.unescape(rv)
            # 6. 清理多余空白
            rv = re.sub(r'\s+', ' ', rv).strip()
            return rv
        except Exception as e:
            return input_str
    def _fix_url(self, url):
        if not url:
            return ""
        url = str(url).strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        if not url.startswith("http"):
            return urllib.parse.urljoin(self.host + "/", url)
        return url

    def _clean_text(self, text):
        if not text:
            return ""
        return re.sub(r"\s+", " ", html.unescape(str(text))).strip()

    def _fetch_html(self, url):
        """获取页面HTML"""
        full_url = self._fix_url(url)
        try:
            res = self.fetch(full_url, headers=self.headers)
            if res and res.status_code == 200:
                res.encoding = 'utf-8'
                return res.text
        except Exception as e:
            pass
        return ""

    def _decode_title(self, text):
        """解码标题中的混淆内容"""
        if not text:
            return ""
        
        # 如果文本中包含 document.write(d('...'))，提取并解码
        # 匹配 d('...') 并解码
        pattern = r"d\(['\"]([^'\"]+)['\"]\)"
        
        # 先尝试提取纯文本内容（从 script 标签中）
        # 查找所有 script 标签内的内容
        script_pattern = r"<script[^>]*>(.*?)</script>"
        script_matches = re.findall(script_pattern, text, re.DOTALL)
        
        if script_matches:
            # 处理每个 script 内容
            result = text
            for script_content in script_matches:
                # 查找 d('xxx') 调用
                match = re.search(pattern, script_content)
                if match:
                    encoded = match.group(1)
                    decoded = self._d(encoded)
                    # 用解码后的文本替换整个 script 标签
                    result = re.sub(r"<script[^>]*>.*?</script>", decoded, result, count=1, flags=re.DOTALL)
                else:
                    # 如果没有 d() 调用，移除 script 标签
                    result = re.sub(r"<script[^>]*>.*?</script>", "", result, count=1, flags=re.DOTALL)
            # 清理残留的 HTML 标签
            result = re.sub(r"<[^>]+>", "", result)
            return self._clean_text(result)
        
        # 如果没有 script 标签，直接清理 HTML 标签
        return self._clean_text(re.sub(r"<[^>]+>", "", text))
    def _parse_list_items(self, html_text):
        """解析列表页中的视频条目"""
        soup = BeautifulSoup(html_text, "html.parser")
        items = []
        
        for a in soup.select('a.list_item.van-col--12'):
            href = a.get("href", "")
            if not href or "javascript:" in href or "link/jump" in href:
                continue
                
            # 提取封面图
            img = a.select_one(".list_img img")
            pic = self._fix_url(img.get("src") or img.get("data-src", "")) if img else ""
            
            # 提取标题 - 从 a 标签的 innerHTML 中用正则提取 d('...') 
            a_html = str(a)
            # 查找 d('xxx') 或 d("xxx")
            match = re.search(r"d\(['\"]([^'\"]+)['\"]\)", a_html)
            if match:
                encoded = match.group(1)
                title = self._d(encoded)
            else:
                # 如果没有 d()，尝试提取纯文本
                title_el = a.select_one(".list_title")
                title = self._clean_text(title_el.get_text()) if title_el else ""
            
            # 如果标题为空，尝试直接从 text 获取
            if not title:
                title_el = a.select_one(".list_title")
                if title_el:
                    title = self._clean_text(title_el.get_text())
            
            # 提取视频ID
            vid_match = re.search(r'/video\.php\?id=(\d+)', href)
            vod_id = vid_match.group(1) if vid_match else href
            
            if title and vod_id:
                items.append({
                    "vod_id": str(vod_id),
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        
        return items
    def _parse_page_count(self, html_text):
        """解析总页数"""
        soup = BeautifulSoup(html_text, "html.parser")
        max_page = 1
        
        # 从分页器获取
        for li in soup.select(".el-pager .number"):
            text = self._clean_text(li.get_text())
            if text.isdigit():
                max_page = max(max_page, int(text))
        
        # 从总条数计算
        title_text = soup.select_one(".list-title p")
        if title_text:
            total_match = re.search(r'共\s*\[?\s*(\d+)\s*\]?\s*部', self._clean_text(title_text.get_text()))
            if total_match:
                total = int(total_match.group(1))
                max_page = max(max_page, (total + 19) // 20)
        
        return max_page

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 直接取精品推荐分类第一页"""
        return self.categoryContent("7048666", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/list.php?id={tid}&page={page}"
        html_text = self._fetch_html(url)
        
        if not html_text:
            return {"list": [], "page": int(page), "pagecount": int(page), "limit": 20, "total": 0}
        
        items = self._parse_list_items(html_text)
        pagecount = self._parse_page_count(html_text)
        
        return {
            "list": items,
            "page": int(page),
            "pagecount": max(pagecount, int(page)),
            "limit": 20,
            "total": len(items) if int(page) >= pagecount else pagecount * 20
        }

    def detailContent(self, ids):
        """获取视频详情和播放地址"""
        # 兼容处理：ids 可能是列表、字符串或整数
        if isinstance(ids, list):
            vid = str(ids[0]) if ids else ""
        elif isinstance(ids, (str, int)):
            vid = str(ids)
        else:
            vid = ""
        
        if not vid:
            return {"list": []}
        
        # 如果包含@@分隔符，取第一部分
        if "@@" in vid:
            vid = vid.split("@@")[0]
        
        url = f"{self.host}/video.php?id={vid}"
        html_text = self._fetch_html(url)
        
        if not html_text:
            return {"list": []}
        
        soup = BeautifulSoup(html_text, "html.parser")
        
        # 提取标题 - 从整个页面 HTML 中用正则提取
        vod_name = "未知视频"
        title_el = soup.select_one(".play_title")
        if title_el:
            title_html = str(title_el)
            # 查找 d('xxx') 或 d("xxx")
            match = re.search(r"d\(['\"]([^'\"]+)['\"]\)", title_html)
            if match:
                vod_name = self._d(match.group(1))
            else:
                vod_name = self._clean_text(title_el.get_text())
        else:
            title_el = soup.select_one("title")
            if title_el:
                vod_name = self._clean_text(title_el.get_text())
        
        # 提取封面图
        pic = ""
        # 从页面中找封面图
        img = soup.select_one(".list_img img")
        if img:
            pic = self._fix_url(img.get("src") or img.get("data-src", ""))
        if not pic:
            # 尝试从其他地方找
            img = soup.select_one("video[poster]")
            if img:
                pic = self._fix_url(img.get("poster", ""))
        
        # 提取简介
        vod_content = vod_name
        desc_el = soup.select_one(".play_list_title")
        if desc_el:
            vod_content = self._clean_text(desc_el.get_text())
        
        # 提取播放地址 - 从script中提取 m3u8 URL
        play_url = ""
        # 查找 hls.loadSource('...') 
        match = re.search(r"hls\.loadSource\(['\"]([^'\"]+\.m3u8[^'\"]*)['\"]\)", html_text)
        if match:
            play_url = self._fix_url(match.group(1))
        else:
            # 查找其他模式
            match = re.search(r"(https?://[^\"'\s<>]+\.m3u8[^\"'\s<>]*)", html_text)
            if match:
                play_url = self._fix_url(match.group(1))
        
        # 构建播放数据
        if play_url:
            vod_play_from = "高清"
            vod_play_url = f"播放${play_url}"
        else:
            # 如果没有找到m3u8，返回嗅探模式
            vod_play_from = "网页嗅探"
            vod_play_url = f"播放$sniff@@{url}"
        
        vod = {
            "vod_id": vid,
            "vod_name": vod_name,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": vod_content or vod_name,
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }
        
        return {"list": [vod]}
    def searchContent(self, key, quick, pg="1"):
        """搜索功能"""
        if not key or not key.strip():
            return {"list": [], "page": 1}
        
        keyword = urllib.parse.quote(key.strip())
        url = f"{self.host}/search.php?content={keyword}"
        html_text = self._fetch_html(url)
        
        if not html_text:
            return {"list": [], "page": int(pg)}
        
        items = self._parse_list_items(html_text)
        pagecount = self._parse_page_count(html_text)
        
        return {
            "list": items,
            "page": int(pg),
            "pagecount": max(pagecount, int(pg))
        }

    def playerContent(self, flag, id, vipFlags):
        """播放器接口"""
        # 如果是嗅探模式
        if id.startswith("sniff@@"):
            return {"parse": 1, "url": id.replace("sniff@@", "", 1), "header": self.headers}
        
        # 如果是 m3u8 直链，走代理过滤广告
        if ".m3u8" in id:
            proxy_url = self._m3u8_proxy_url(id)
            return {"parse": 0, "url": proxy_url, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/"}}
        
        # 如果 id 本身就是 URL
        if id.startswith("http"):
            return {"parse": 0, "url": id, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/"}}
        
        # 降级嗅探
        return {"parse": 1, "url": id, "header": self.headers}
    def localProxy(self, param):
        """m3u8 本地代理 - 广告过滤"""
        try:
            # 兼容多种参数格式
            if isinstance(param, dict):
                target = param.get("url", "")
            elif isinstance(param, str):
                target = param
            else:
                return [400, "text/plain", b"invalid param"]
            
            if not target:
                return [400, "text/plain", b"missing url"]
            
            # 解码 URL
            target = urllib.parse.unquote(target)
            
            if not target.startswith("http"):
                return [400, "text/plain", b"invalid url"]
            
            # 请求 m3u8
            res = self.fetch(target, headers={"User-Agent": self.headers["User-Agent"]}, timeout=15)
            
            if not res:
                return [502, "text/plain", b"fetch failed"]
            
            raw = res.content or b""
            if not raw:
                return [502, "text/plain", b"empty response"]
            
            try:
                text = raw.decode("utf-8", errors="ignore")
                if "#EXTM3U" in text:
                    # 调用 _clean_m3u8 过滤广告分片
                    cleaned = self._clean_m3u8(text, target)
                    return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            except Exception as e:
                pass
            
            return [200, "video/mp4", raw]
            
        except Exception as e:
            return [500, "text/plain", str(e).encode("utf-8")]
    def _fix_m3u8_paths(self, text, source_url):
        """补全 m3u8 中的相对路径"""
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                # 处理 #EXT-X-KEY 中的 URI
                if line.startswith("#EXT-X-KEY") and 'URI="' in line:
                    def repl(m):
                        return 'URI="' + urllib.parse.urljoin(source_url, m.group(1)) + '"'
                    line = re.sub(r'URI="([^"]+)"', repl, line)
                lines.append(line)
            else:
                # 分片路径补全
                if not line.startswith("http"):
                    line = urllib.parse.urljoin(source_url, line)
                lines.append(line)
        return "\n".join(lines)
    def _clean_m3u8(self, text, source_url):
        """清洗 m3u8：过滤广告分片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"
        
        # 检测正片路径特征：m3u8 URL 中包含的视频ID路径
        # 从 source_url 中提取正片路径前缀
        # 例如：https://voddadaizi1.com:52866/videos/202511/11/69132f5f72c0032a43008b35/d240b2/index.m3u8
        # 正片分片在 /videos/202511/11/69132f5f72c0032a43008b35/d240b2/ 下
        parsed = urllib.parse.urlparse(source_url)
        path = parsed.path
        # 提取正片目录：去掉最后的 /index.m3u8
        if path.endswith("/index.m3u8"):
            base_path = path[:-11]  # 去掉 /index.m3u8
        elif path.endswith(".m3u8"):
            base_path = path[:path.rfind("/")]
        else:
            base_path = path
        
        # 确保 base_path 以 / 开头和结尾
        if not base_path.startswith("/"):
            base_path = "/" + base_path
        if not base_path.endswith("/"):
            base_path = base_path + "/"
        
        # 构建完整的基础 URL
        base_url = parsed.scheme + "://" + parsed.netloc + base_path
        
        # 过滤逻辑
        result = []
        skip = False
        skipped_count = 0
        
        for line in lines:
            if line.startswith("#"):
                # 保留所有标签
                result.append(line)
            else:
                # 分片URL
                if not line.startswith("http"):
                    # 补全为完整URL
                    full_url = urllib.parse.urljoin(source_url, line)
                else:
                    full_url = line
                
                # 判断是否为正片分片
                # 正片分片应该在 base_path 目录下
                if full_url.startswith(base_url):
                    result.append(full_url)
                else:
                    # 广告分片，跳过
                    skipped_count += 1
        
        if skipped_count > 0:
            print(f"过滤广告分片: {skipped_count} 个")
        
        return "\n".join(result) + "\n"
    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址 - TVBox 标准格式"""
        # getProxyUrl() 返回的是 http://127.0.0.1:9978/proxy?do=py
        # 所以只需要追加 &url= 参数
        return self.getProxyUrl() + "&url=" + urllib.parse.quote(str(url or ""), safe="")
    def isVideoFormat(self, url):
        return False

    def destroy(self):
        pass