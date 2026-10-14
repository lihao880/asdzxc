# coding: utf-8
# ============================================================
# TVBox/FongMi 爬虫源 - 网红的私密
# 站点: https://www.whdsm2.pics/cn/home/web/
# 架构: MacCMS (datll.10.2 模板) 标准 HTML 站
# 内容: 视频 (m3u8)
# 特征: 图片流伪装站(分片 .jpg), AES-128 加密, 播放直链内联 player_data
# 分类: 20-27 (国产精品/主播大秀/唯美视频/口交视频/日本有碼/日本無碼/动漫视频/欧美视频)
# 分页: /index.php/vod/show/id/{tid}/page/{pg}.html (实测 971 页)
# 详情: /index.php/vod/play/id/{id}/sid/1/nid/1.html
# 搜索: /index.php/vod/search.html?wd={kw}  (POST)
# 播放: player_data.url 直接是 m3u8 直链, 无广告特征 -> 直连不代理
# 最后验证: 2026-09-21
# ============================================================
import json
import re
from urllib.parse import quote, urljoin, unquote, urlparse

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    def __init__(self):
        # __init__ 零网络，只做本地初始化，保证首页秒出
        self.extend = ""
        self.host = "https://www.whdsm2.pics"
        self.base = "/cn/home/web"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        # 分类静态硬编码（法则16/17）
        self.classes = [
            {"type_id": "20", "type_name": "国产精品"},
            {"type_id": "21", "type_name": "主播大秀"},
            {"type_id": "22", "type_name": "唯美视频"},
            {"type_id": "23", "type_name": "口交视频"},
            {"type_id": "24", "type_name": "日本有碼"},
            {"type_id": "25", "type_name": "日本無碼"},
            {"type_id": "26", "type_name": "动漫视频"},
            {"type_id": "27", "type_name": "欧美视频"},
        ]
        # 站点无真实筛选 DOM，返回空 filters（禁止伪造）
        self.filters = {}

    def getName(self):
        return "网红的私密"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # init 零网络
        self.extend = extend or ""

    def homeContent(self, filter):
        # 零网络，快速返回
        return {"class": self.classes, "filters": self.filters}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    # ---------------- 工具方法 ----------------

    @staticmethod
    def _norm_ids(ids):
        """法则35：ids 归一化，兼容 list/str/int/bytes"""
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def _fetch_html(self, url, method="GET", data=None):
        """统一请求，判空（runtime 8.2）"""
        try:
            if method == "POST":
                r = self.post(url, data=data, headers=self.headers, timeout=15)
            else:
                r = self.fetch(url, headers=self.headers, timeout=15)
            if not r or r.status_code != 200:
                self.log({"fetch": "failed", "url": url,
                          "status": r.status_code if r else None})
                return ""
            return r.text or ""
        except Exception as e:
            self.log({"fetch": "exception", "url": url, "error": type(e).__name__})
            return ""

    # ---------------- 列表解析（分类页 / 搜索页 / 首页通用） ----------------

    def _parse_list(self, html):
        """解析卡片；兼容分类/搜索页(li.i_list)与首页(li.layui-col-sm3)两种结构"""
        result = []
        if not html:
            return result
        # 统一按 <li 卡片切分，兼容 i_list 与纯 layui-col-sm3
        blocks = re.split(r'<li[^>]*class="[^"]*(?:i_list|layui-col-sm3)[^"]*"', html)
        seen = set()
        for blk in blocks[1:]:
            blk = blk.split("</li>", 1)[0]
            m = re.search(r'<a[^>]*href="([^"]+)"[^>]*title="([^"]*)"', blk)
            if not m:
                continue
            href = m.group(1).strip()
            title = m.group(2).strip()
            vid_m = re.search(r'/vod/play/id/(\d+)', href)
            if not vid_m:
                continue
            vid = vid_m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            # 图片：lay-src 优先，兜底 src
            pic = ""
            pm = re.search(r'<img[^>]*lay-src="([^"]+)"', blk)
            if not pm:
                pm = re.search(r'<img[^>]*src="([^"]+)"', blk)
            if pm:
                pic = pm.group(1).strip()
            # 角标
            remark = ""
            rm = re.search(r'<span[^>]*class="[^"]*layui-remarks[^"]*"[^>]*>([^<]*)</span>', blk)
            if rm:
                remark = rm.group(1).strip()
            if not title:
                nm = re.search(r'<div[^>]*class="[^"]*vodname[^"]*"[^>]*>([^<]+)</div>', blk)
                if nm:
                    title = nm.group(1).strip()
            packed = "|$|".join([vid, title, pic, remark, href])
            result.append({
                "vod_id": packed,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return result
    def homeVideoContent(self):
        html = self._fetch_html(self.host + self.base + "/")
        return {"list": self._parse_list(html)}

    # ---------------- 分类 ----------------

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        url = "%s%s/index.php/vod/show/id/%s/page/%s.html" % (
            self.host, self.base, tid, page)
        html = self._fetch_html(url)
        items = self._parse_list(html)
        # 总页数：尝试从分页容器取；取不到给保守值
        pagecount = 999
        try:
            m = re.search(r'共\s*(\d+)\s*页', html)
            if m:
                pagecount = int(m.group(1))
        except Exception:
            pass
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20,
        }

    # ---------------- 详情（零网络拆包） ----------------

    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
        """法则35：骨架兜底，禁止返回空 list"""
        pid = str(vid).split("|$|")[0].replace("$", "|")
        return {"list": [{
            "vod_id": vid,
            "vod_name": title or "未知标题",
            "vod_pic": pic or "",
            "vod_remarks": remarks,
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": "播放$" + pid,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}   # 唯一允许返回空的分支
        try:
            ps = raw.split("|$|")
            vod_id = ps[0]
            old_name = ps[1] if len(ps) > 1 else ""
            old_pic = ps[2] if len(ps) > 2 else ""
            old_remark = ps[3] if len(ps) > 3 else ""
            play_page = ps[4] if len(ps) > 4 else ""
            if not play_page:
                play_page = "%s%s/index.php/vod/play/id/%s/sid/1/nid/1.html" % (
                    self.host, self.base, vod_id)
            # 播放ID 安全：直接存完整播放页 URL（不含裸 $）
            vod = {
                "vod_id": raw,
                "vod_name": old_name or "视频",
                "vod_pic": old_pic,
                "vod_remarks": old_remark,
                "vod_actor": "",
                "vod_director": "",
                "vod_content": old_remark,
                "vod_play_from": "播放",
                "vod_play_url": "播放$" + play_page,
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"detail": "exception", "ids": raw, "error": type(e).__name__})
            return self._skeleton(raw)

    # ---------------- 搜索 ----------------

    def searchContent(self, key, quick, pg="1"):
        page = str(pg or "1")
        url = "%s%s/index.php/vod/search.html" % (self.host, self.base)
        data = {"wd": key}
        if page and page != "1":
            url = "%s%s/index.php/vod/search/page/%s/wd/%s.html" % (
                self.host, self.base, page, quote(key))
            data = None
        if data is not None:
            html = self._fetch_html(url, method="POST", data=data)
        else:
            html = self._fetch_html(url)
        items = self._parse_list(html)
        return {"list": items, "page": int(page)}

    # ---------------- 播放（懒加载解析直链） ----------------

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id) if id else ""
        # 剥离 "名称$地址"
        if play_url and "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]
        play_url = play_url.strip()
        # 补全协议 / 相对地址
        if play_url and not play_url.startswith("http"):
            if play_url.startswith("//"):
                play_url = "https:" + play_url
            elif play_url.startswith("/"):
                play_url = self.host + play_url
            else:
                play_url = self.host + self.base + "/" + play_url.lstrip("/")

        # 已是直链
        if re.search(r'\.(m3u8|mp4|flv)(\?|$)', play_url, re.I):
            return self._play_result(play_url)

        # 播放页：提取 player_data 内联 JSON
        html = self._fetch_html(play_url)
        if not html:
            return {"parse": 1, "url": play_url, "header": self.headers}

        # L1: player_data JSON
        direct = self._extract_player_data(html)
        if direct:
            return self._play_result(direct)

        # L5: 全文正则兜底（m3u8/mp4）
        m = re.search(r'https?://[^\s"\'<>\\]+?\.(?:m3u8|mp4)(?:\?[^\s"\'<>\\]*)?', html)
        if m:
            return self._play_result(m.group(0).replace("\\/", "/"))

        # 降级嗅探
        return {"parse": 1, "url": play_url, "header": self.headers}

    def _play_result(self, url):
        """m3u8 走 localProxy 做多码率子流广告过滤；mp4/flv 直连"""
        url = str(url or "").strip().replace("\\/", "/")
        if url.endswith(".m3u8") or ".m3u8?" in url:
            proxy = self.getProxyUrl() + "&url=" + quote(url, safe="")
            return {"parse": 0, "url": proxy, "header": self.headers}
        return {"parse": 0, "url": url, "header": self.headers}

    def localProxy(self, param):
        """m3u8 代理：多码率主表透传，子流按自身目录动态锚点过滤广告分片"""
        try:
            target = ""
            if isinstance(param, dict):
                target = param.get("url", "") or ""
                if not target:
                    target = param.get("target", "") or ""
            target = unquote(str(target))
            if not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]
            r = self.fetch(target, headers={"User-Agent": self.headers["User-Agent"]},
                           timeout=15)
            if not r or r.status_code != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            text = (r.text or "")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log({"localProxy": "error", "error": type(e).__name__})
            return [500, "text/plain", b"proxy error"]

    def _clean_m3u8(self, text, source_url):
        """多码率主表透传（子流改代理）；子流按目录众数/自身目录锚点过滤"""
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 多码率主表：子流改代理地址
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    if ".m3u8" in child.lower():
                        out.append(self.getProxyUrl() + "&url=" + quote(child, safe=""))
                    else:
                        out.append(child)
            return "\n".join(out) + "\n"

        # 子流：锚点 = m3u8 自身目录（正片目录）
        import posixpath
        base_dir = posixpath.dirname(urlparse(source_url).path)
        if not base_dir.endswith("/"):
            base_dir += "/"

        out = []
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
                media = urljoin(source_url, line)
                mpath = urlparse(media).path
                if base_dir and base_dir not in mpath:
                    removed += 1          # 跨目录 → 广告分片
                else:
                    out.extend(pending)
                    out.append(media)
                    kept += 1
                pending = []
                continue
            out.append(self._rewrite_tag(line, source_url))

        # 全滤兜底：过滤过头则整体回退
        if removed > 0 and (kept == 0 or removed > kept):
            self.log({"clean": "fallback", "removed": removed, "kept": kept})
            out = [self._rewrite_tag(l, source_url) for l in lines]
        elif removed:
            self.log({"clean": "filtered", "removed": removed, "kept": kept,
                      "anchor": base_dir})

        return "\n".join(out) + "\n"

    def _rewrite_tag(self, line, source_url):
        """补全绝对地址；KEY/MAP 只补 URI 不改后缀"""
        if line.startswith(("#EXT-X-KEY", "#EXT-X-MAP", "#EXT-X-SESSION-KEY")):
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
    def _extract_player_data(self, html):
        """平衡括号提取 player_data 对象并取 url"""
        try:
            idx = html.find("player_data")
            if idx < 0:
                return ""
            brace = html.find("{", idx)
            if brace < 0:
                return ""
            depth = 0
            end = -1
            for i in range(brace, len(html)):
                c = html[i]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end < 0:
                return ""
            raw = html[brace:end + 1]
            try:
                obj = json.loads(raw)
            except Exception:
                # loose 重试
                raw2 = raw.replace("\\/", "/").replace("'", '"')
                raw2 = re.sub(r',\s*}', '}', raw2)
                obj = json.loads(raw2)
            url = obj.get("url", "") or ""
            url = str(url).replace("\\/", "/").strip()
            if url and re.search(r'\.(m3u8|mp4|flv)', url, re.I):
                return url
        except Exception as e:
            self.log({"player_data": "parse_fail", "error": type(e).__name__})
        return ""

    # ---------------- 推荐 ----------------

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass