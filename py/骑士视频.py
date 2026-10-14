# coding: utf-8
# 站点信息沉淀（法则24）
# 主域名: https://www.qssp3.homes
# 备用域名: 无
# 发布页: 无
# 内容类型: 成人影视（国产/日韩/欧美/动漫等）
# 特殊说明: MacCMS模板，播放数据内嵌player_data，m3u8直链
# 最后验证时间: 2026-08-31
# 来源: 用户提供 https://www.qssp3.homes/cn/home/web/

import posixpath
import json
import re
from urllib.parse import urljoin, quote, unquote, urlparse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.qssp3.homes"
        self.base_path = "/cn/home/web"
        self.site_name = "骑士视频"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host + self.base_path + "/"
        }
        
        # 分类列表（法则16：分类硬编码）
        self.classes = [
            {"type_id": "20", "type_name": "熟母少妇"},
            {"type_id": "21", "type_name": "网红直播"},
            {"type_id": "22", "type_name": "自拍偷拍"},
            {"type_id": "23", "type_name": "强奸乱伦"},
            {"type_id": "24", "type_name": "高清国产"},
            {"type_id": "25", "type_name": "韩国专区"},
            {"type_id": "26", "type_name": "日本有码"},
            {"type_id": "27", "type_name": "日本无码"},
            {"type_id": "28", "type_name": "欧美情色"},
            {"type_id": "29", "type_name": "动漫卡通"},
            {"type_id": "30", "type_name": "三级伦理"}
        ]
        
        # filters（站点无真实筛选，返回空）
        self.filters = {}

    def getName(self):
        return self.site_name

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        # 零网络依赖，快速返回分类
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 从首页获取推荐列表（最近热播）
        url = self.host + self.base_path + "/"
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": []}
        
        html = resp.text or ""
        # 提取最近热播区域的视频列表
        pattern = r'<a href="([^"]+)" title="([^"]*)"[^>]*>\s*<div class="video__inner[^"]*">\s*<div class="video__block">\s*<img[^>]*src="([^"]+)"[^>]*/>\s*</div>\s*<div class="video__text">\s*<div class="like__wrap">\s*<i></i>\s*<span>(\d+)</span>\s*</div>\s*<h3>([^<]*)</h3>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        result = []
        seen = set()
        for href, title, pic, views, h3_title in matches:
            if href in seen:
                continue
            seen.add(href)
            vod_id = self._extract_vod_id_from_url(href)
            if not vod_id:
                continue
            display_title = title or h3_title
            if not display_title:
                continue
            result.append({
                "vod_id": vod_id,
                "vod_name": display_title.strip(),
                "vod_pic": pic.strip() if pic else "",
                "vod_remarks": views + "次观看" if views else ""
            })
            if len(result) >= 30:
                break
        
        return {"list": result}

    def categoryContent(self, tid, pg, filter, extend):
        # 确保 pg 为整数
        try:
            page = int(pg) if pg is not None else 1
        except (ValueError, TypeError):
            page = 1
        
        # URL 构造：page=1 时不带 /page/1.html，直接访问分类首页
        if page <= 1:
            url = f"{self.host}{self.base_path}/index.php/vod/type/id/{tid}.html"
        else:
            url = f"{self.host}{self.base_path}/index.php/vod/type/id/{tid}/page/{page}.html"
        
        self.log({"action": "categoryContent", "tid": tid, "page": page, "url": url})
        
        resp = self.fetch(url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
        
        html = resp.text or ""
        video_items = self._parse_video_items(html)
        
        # 提取分页信息
        pagecount = 1
        # 从尾页链接提取最大页数
        tail_match = re.search(r'尾页</a>&nbsp;.*?href="[^"]*/page/(\d+)\.html"', html)
        if tail_match:
            pagecount = int(tail_match.group(1))
        else:
            # 尝试从分页链接中提取最大页码
            page_links = re.findall(r'href="[^"]*/page/(\d+)\.html"', html)
            if page_links:
                pagecount = max([int(p) for p in page_links])
        
        # 确保 pagecount 至少为1
        if pagecount < 1:
            pagecount = 1
        
        total = pagecount * 20
        
        return {
            "list": video_items,
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": total
        }
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        
        vid = str(ids[0])
        if vid.startswith("http"):
            vod_id = self._extract_vod_id_from_url(vid)
            if not vod_id:
                vod_id = vid
        else:
            vod_id = vid
        
        play_url = f"{self.host}{self.base_path}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
        
        resp = self.fetch(play_url, headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            return {"list": []}
        
        html = resp.text or ""
        
        title_match = re.search(r'<title>([^<]*)</title>', html)
        title = title_match.group(1).replace(" - 骑士视频", "").strip() if title_match else "视频"
        
        # 提取player_data - 使用更宽松的正则
        play_url_direct = ""
        player_match = re.search(r'var\s+player_data\s*=\s*(\{[^}]+\})', html, re.DOTALL)
        if player_match:
            try:
                data_str = player_match.group(1)
                # 清理可能的换行和注释
                data_str = re.sub(r'/\*.*?\*/', '', data_str, flags=re.DOTALL)
                data_str = re.sub(r'//.*?$', '', data_str, flags=re.MULTILINE)
                data = json.loads(data_str)
                play_url_direct = data.get("url", "")
            except Exception as e:
                self.log({"action": "detail_parse_error", "error": str(e)})
        
        if not play_url_direct:
            m3u8_match = re.search(r'https?://[^"\']+\.m3u8[^"\']*', html)
            if m3u8_match:
                play_url_direct = m3u8_match.group(0)
        
        vod_play_from = "直链"
        vod_play_url = f"第1集${play_url_direct}" if play_url_direct else ""
        
        result = [{
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }]
        
        return {"list": result}
    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": 1}
        
        search_url = f"{self.host}{self.base_path}/index.php/vod/search.html"
        # 尝试GET方式
        resp = self.fetch(f"{search_url}?wd={quote(key)}", headers=self.headers, timeout=10)
        if not resp or resp.status_code != 200:
            # 尝试POST方式
            resp = self.post(search_url, data={"wd": key}, headers=self.headers, timeout=10)
        
        if not resp or resp.status_code != 200:
            return {"list": [], "page": 1}
        
        html = resp.text or ""
        
        # 检查是否无结果
        if re.search(r'没有找到.*结果|暂无数据|搜索无结果', html):
            return {"list": [], "page": 1}
        
        video_items = self._parse_video_items(html)
        return {"list": video_items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        
        play_url = str(id).strip()
        
        # 如果已经是m3u8/mp4直链，返回代理地址（让播放器走localProxy过滤广告）
        if play_url.startswith("http") and ".m3u8" in play_url:
            proxy_url = self._m3u8_proxy_url(play_url)
            self.log({"action": "playerContent", "original": play_url, "proxy": proxy_url})
            return {
                "parse": 0,
                "url": proxy_url,
                "header": {"User-Agent": self.headers.get("User-Agent", "")}
            }
        
        # 如果是播放页URL，请求获取播放地址
        if play_url.startswith("http"):
            resp = self.fetch(play_url, headers=self.headers, timeout=15)
            if resp and resp.status_code == 200:
                html = resp.text or ""
                
                # 提取player_data
                player_match = re.search(r'var\s+player_data\s*=\s*(\{[^}]+\})', html, re.DOTALL)
                if player_match:
                    try:
                        data_str = player_match.group(1)
                        data_str = re.sub(r'/\*.*?\*/', '', data_str, flags=re.DOTALL)
                        data_str = re.sub(r'//.*?$', '', data_str, flags=re.MULTILINE)
                        data = json.loads(data_str)
                        direct_url = data.get("url", "")
                        if direct_url and direct_url.startswith("http") and ".m3u8" in direct_url:
                            proxy_url = self._m3u8_proxy_url(direct_url)
                            self.log({"action": "player_extract", "original": direct_url, "proxy": proxy_url})
                            return {
                                "parse": 0,
                                "url": proxy_url,
                                "header": {"User-Agent": self.headers.get("User-Agent", "")}
                            }
                    except Exception as e:
                        self.log({"action": "player_parse_error", "error": str(e)})
                
                # 尝试直接提取m3u8
                m3u8_match = re.search(r'https?://[^"\']+\.m3u8[^"\']*', html)
                if m3u8_match:
                    direct_url = m3u8_match.group(0)
                    proxy_url = self._m3u8_proxy_url(direct_url)
                    return {
                        "parse": 0,
                        "url": proxy_url,
                        "header": {"User-Agent": self.headers.get("User-Agent", "")}
                    }
        
        # 如果play_url本身就是播放页URL但提取失败，降级嗅探
        if play_url.startswith("http") and "/play/id/" in play_url:
            return {
                "parse": 1,
                "url": play_url,
                "header": {
                    "User-Agent": self.headers.get("User-Agent", ""),
                    "Referer": self.host + self.base_path + "/"
                }
            }
        
        # 其他情况返回空
        return {"parse": 0, "url": "", "header": {}}
    def recommendContent(self, ids, pg):
        # 返回空列表
        return {"list": []}

    def destroy(self):
        pass

    def _extract_vod_id_from_url(self, url):
        """从URL中提取视频ID"""
        if not url:
            return ""
        # 匹配 /id/数字/
        match = re.search(r'/id/(\d+)/', url)
        if match:
            return match.group(1)
        # 匹配 /id/数字.html
        match = re.search(r'/id/(\d+)\.html', url)
        if match:
            return match.group(1)
        return ""

    def _parse_video_items(self, html):
        """从HTML中解析视频列表"""
        pattern = r'<a href="([^"]+)" title="([^"]*)"[^>]*>\s*<div class="video__inner[^"]*">\s*<div class="video__block">\s*<img[^>]*src="([^"]+)"[^>]*/>\s*</div>\s*<div class="video__text">\s*<div class="like__wrap">\s*<i></i>\s*<span>(\d*)</span>\s*</div>\s*<h3>([^<]*)</h3>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        result = []
        seen = set()
        for href, title, pic, views, h3_title in matches:
            if href in seen:
                continue
            seen.add(href)
            vod_id = self._extract_vod_id_from_url(href)
            if not vod_id:
                continue
            display_title = title or h3_title
            if not display_title:
                continue
            result.append({
                "vod_id": vod_id,
                "vod_name": display_title.strip(),
                "vod_pic": pic.strip() if pic else "",
                "vod_remarks": views + "次观看" if views else ""
            })
        
        return result

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址"""
        if not url:
            return ""
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url), safe="")

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def localProxy(self, param):
        """m3u8本地代理 + 广告分片过滤（参照m3u8_ad_filter.md五层管线）"""
        try:
            # 解析目标URL
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                qs = urlparse(target).query
                parsed_qs = {}
                for part in qs.split("&"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        parsed_qs[k] = v
                if "url" in parsed_qs:
                    target = parsed_qs["url"]
            
            target = unquote(str(target or ""))
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]
            
            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp:
                return [502, "text/plain", b"fetch failed"]
            
            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]
            
            # 检查是否为m3u8
            if b"#EXTM3U" in content[:512]:
                cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            
            # 非m3u8直接透传
            return [200, "application/octet-stream", content]
            
        except Exception as e:
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]

    def _is_fake_image_stream(self, text, source_url):
        """检测是否为图片流伪装"""
        low_url = (source_url or "").lower()
        for sig in ("doyinapi", "svip", "imgcdn", "photo"):
            if sig in low_url:
                return True
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower().split("?")[0]
            if low.endswith((".png", ".jpg", ".jpeg", ".webp")):
                return True
        return False

    def _resolve_main_dir(self, lines, source_url):
        """确定正片目录锚点：KEY URI 优先 → DISCONTINUITY 之后 → 分片数量最多 → m3u8 URL 目录"""
        import posixpath
        from collections import Counter
        from urllib.parse import urlparse, urljoin
        
        parsed = urlparse(source_url)
        default_dir = posixpath.dirname(parsed.path)
        if not default_dir.endswith("/"):
            default_dir += "/"
        
        # 1. 优先从 #EXT-X-KEY 提取
        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            if key_uri.startswith("http"):
                key_path = urlparse(key_uri).path
            else:
                key_path = urlparse(urljoin(source_url, key_uri)).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        
        # 2. 从 #EXT-X-MAP 提取
        for line in lines:
            if not line.startswith("#EXT-X-MAP") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            map_uri = m.group(1)
            if map_uri.startswith("http"):
                map_path = urlparse(map_uri).path
            else:
                map_path = urlparse(urljoin(source_url, map_uri)).path
            map_dir = posixpath.dirname(map_path)
            if map_dir and map_dir != "/":
                return map_dir + "/"
        
        # 3. 检测 #EXT-X-DISCONTINUITY，取之后的第一个分片目录
        after_discontinuity = False
        for line in lines:
            if line == "#EXT-X-DISCONTINUITY":
                after_discontinuity = True
                continue
            if after_discontinuity and line and not line.startswith("#"):
                # 找到 DISCONTINUITY 后的第一个分片
                if line.startswith("http"):
                    seg_path = urlparse(line).path
                else:
                    seg_path = line
                seg_dir = posixpath.dirname(seg_path)
                if seg_dir and seg_dir != "/":
                    if seg_dir.startswith("/"):
                        seg_dir = seg_dir[1:]
                    return seg_dir + "/"
        
        # 4. 统计所有分片的目录，选出现次数最多的
        seg_dirs = []
        for line in lines:
            if line and not line.startswith("#"):
                if line.startswith("http"):
                    seg_path = urlparse(line).path
                else:
                    seg_path = line
                seg_dir = posixpath.dirname(seg_path)
                if seg_dir and seg_dir != "/":
                    if seg_dir.startswith("/"):
                        seg_dir = seg_dir[1:]
                    seg_dirs.append(seg_dir + "/")
        
        if seg_dirs:
            dir_counter = Counter(seg_dirs)
            max_count = 0
            best_dir = default_dir
            for d, count in dir_counter.items():
                if count > max_count:
                    max_count = count
                    best_dir = d
            return best_dir
        
        return default_dir
    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI"""
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(m):
                uri = m.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)
        return line

    def _clean_m3u8(self, text, source_url):
        """清洗m3u8：五层管线 - 修复版"""
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"
        
        # ===== 第1层：图片流伪装检测 =====
        is_fake_image = self._is_fake_image_stream(text, source_url)
        
        # ===== 第2层：多码率主表透传 =====
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    if ".m3u8" in child.lower():
                        out.append(self._m3u8_proxy_url(child))
                    else:
                        out.append(child)
            self.log({"action": "m3u8_multi_bitrate", "status": "proxy_children"})
            return "\n".join(out) + "\n"
        
        # ===== 第3层：正片目录锚点 =====
        main_dir = self._resolve_main_dir(lines, source_url)
        # 确保 main_dir 不以 / 开头（用于比较）
        if main_dir.startswith("/"):
            main_dir = main_dir[1:]
        if not main_dir.endswith("/"):
            main_dir += "/"
        self.log({"action": "m3u8_main_dir", "main_dir": main_dir})
        
        # ===== 第4层：分片过滤 =====
        segments = []
        pending = []
        removed = 0
        kept = 0
        
        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urljoin(source_url, line)
                media_path = urlparse(media_url).path
                # 去掉前导 / 后比较
                if media_path.startswith("/"):
                    media_path = media_path[1:]
                if media_path.startswith(main_dir):
                    segments.extend(pending)
                    segments.append(media_url)
                    kept += 1
                else:
                    removed += 1
                pending = []
                continue
            if line.startswith("#"):
                segments.append(line)
            else:
                segments.append(urljoin(source_url, line))
        
        if pending:
            removed += 1
        
        # ===== 第5层：全滤兜底 =====
        if kept == 0 and removed > 0:
            self.log({"action": "m3u8_filter", "status": "fallback_no_filter", "removed": removed, "kept": kept})
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"
        
        if removed > 0:
            self.log({"action": "m3u8_filter", "removed": removed, "kept": kept, "main_dir": main_dir})
        else:
            self.log({"action": "m3u8_filter", "removed": 0, "kept": kept, "main_dir": main_dir})
        
        # ===== 冗余标签清理 =====
        NOISE = ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE")
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in NOISE:
                if not out or out[-1] in NOISE:
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in NOISE:
            out.pop()
        
        return "\n".join(out) + "\n"
