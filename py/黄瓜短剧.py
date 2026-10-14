# coding: utf-8
# 站点信息沉淀（法则24）
# 主域名: https://hgdju.com
# 备用域名: hgdju1.com, hgdju2.com, hgdju3.com
# 发布页: https://hgdj.ai
# 内容类型: 短剧（原创/魔改/AI漫剧/真人短剧/AI短剧）
# 特殊说明: 播放页内嵌 HG_PLAY 数据，hls 字段带 auth_key 签名
# 最后验证时间: 2026-09-02
# 来源: 用户提供

import json
import re
from urllib.parse import urljoin, quote, unquote, urlparse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://hgdju.com"
        # 分类：内容线（与 /browse 页面一致）
        self.classes = [
            {"type_id": "all", "type_name": "全部"},
            {"type_id": "yuanchuang", "type_name": "原创"},
            {"type_id": "mogai", "type_name": "魔改"},
            {"type_id": "manju", "type_name": "AI 漫剧"},
            {"type_id": "zhenren", "type_name": "真人短剧"},
            {"type_id": "aiduanju", "type_name": "AI短剧"},
        ]
        # 筛选器：题材、状态、排序
        self.filters = {
            "all": [
                {
                    "key": "topic",
                    "name": "题材",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "都市邻里", "v": "dushi"},
                        {"n": "甜宠恋爱", "v": "tianchong"},
                        {"n": "逆袭", "v": "nixi"},
                        {"n": "复仇逆袭", "v": "fuchou"},
                        {"n": "古装玄幻", "v": "xuanhuan"},
                        {"n": "惊悚悬疑", "v": "jingsong"},
                        {"n": "霸总激情", "v": "bazong"},
                        {"n": "穿越重生", "v": "chuanyue"},
                        {"n": "虐恋情深", "v": "nuelian"},
                        {"n": "战神归来", "v": "zhanshen"},
                        {"n": "末世生存", "v": "moshi"},
                    ]
                },
                {
                    "key": "status",
                    "name": "状态",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "连载中", "v": "ongoing"},
                        {"n": "已完结", "v": "ended"},
                    ]
                },
                {
                    "key": "sort",
                    "name": "排序",
                    "value": [
                        {"n": "最热", "v": "hot"},
                        {"n": "最新", "v": "new"},
                        {"n": "追剧最多", "v": "follow"},
                    ]
                }
            ],
            "yuanchuang": [
                {
                    "key": "topic",
                    "name": "题材",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "都市邻里", "v": "dushi"},
                        {"n": "甜宠恋爱", "v": "tianchong"},
                        {"n": "逆袭", "v": "nixi"},
                        {"n": "复仇逆袭", "v": "fuchou"},
                        {"n": "古装玄幻", "v": "xuanhuan"},
                        {"n": "惊悚悬疑", "v": "jingsong"},
                        {"n": "霸总激情", "v": "bazong"},
                        {"n": "穿越重生", "v": "chuanyue"},
                        {"n": "虐恋情深", "v": "nuelian"},
                        {"n": "战神归来", "v": "zhanshen"},
                        {"n": "末世生存", "v": "moshi"},
                    ]
                },
                {
                    "key": "status",
                    "name": "状态",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "连载中", "v": "ongoing"},
                        {"n": "已完结", "v": "ended"},
                    ]
                },
                {
                    "key": "sort",
                    "name": "排序",
                    "value": [
                        {"n": "最热", "v": "hot"},
                        {"n": "最新", "v": "new"},
                        {"n": "追剧最多", "v": "follow"},
                    ]
                }
            ],
            "mogai": [
                {
                    "key": "topic",
                    "name": "题材",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "都市邻里", "v": "dushi"},
                        {"n": "甜宠恋爱", "v": "tianchong"},
                        {"n": "逆袭", "v": "nixi"},
                        {"n": "复仇逆袭", "v": "fuchou"},
                        {"n": "古装玄幻", "v": "xuanhuan"},
                        {"n": "惊悚悬疑", "v": "jingsong"},
                        {"n": "霸总激情", "v": "bazong"},
                        {"n": "穿越重生", "v": "chuanyue"},
                        {"n": "虐恋情深", "v": "nuelian"},
                        {"n": "战神归来", "v": "zhanshen"},
                        {"n": "末世生存", "v": "moshi"},
                    ]
                },
                {
                    "key": "status",
                    "name": "状态",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "连载中", "v": "ongoing"},
                        {"n": "已完结", "v": "ended"},
                    ]
                },
                {
                    "key": "sort",
                    "name": "排序",
                    "value": [
                        {"n": "最热", "v": "hot"},
                        {"n": "最新", "v": "new"},
                        {"n": "追剧最多", "v": "follow"},
                    ]
                }
            ],
            "manju": [
                {
                    "key": "topic",
                    "name": "题材",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "都市邻里", "v": "dushi"},
                        {"n": "甜宠恋爱", "v": "tianchong"},
                        {"n": "逆袭", "v": "nixi"},
                        {"n": "复仇逆袭", "v": "fuchou"},
                        {"n": "古装玄幻", "v": "xuanhuan"},
                        {"n": "惊悚悬疑", "v": "jingsong"},
                        {"n": "霸总激情", "v": "bazong"},
                        {"n": "穿越重生", "v": "chuanyue"},
                        {"n": "虐恋情深", "v": "nuelian"},
                        {"n": "战神归来", "v": "zhanshen"},
                        {"n": "末世生存", "v": "moshi"},
                    ]
                },
                {
                    "key": "status",
                    "name": "状态",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "连载中", "v": "ongoing"},
                        {"n": "已完结", "v": "ended"},
                    ]
                },
                {
                    "key": "sort",
                    "name": "排序",
                    "value": [
                        {"n": "最热", "v": "hot"},
                        {"n": "最新", "v": "new"},
                        {"n": "追剧最多", "v": "follow"},
                    ]
                }
            ],
            "zhenren": [
                {
                    "key": "topic",
                    "name": "题材",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "都市邻里", "v": "dushi"},
                        {"n": "甜宠恋爱", "v": "tianchong"},
                        {"n": "逆袭", "v": "nixi"},
                        {"n": "复仇逆袭", "v": "fuchou"},
                        {"n": "古装玄幻", "v": "xuanhuan"},
                        {"n": "惊悚悬疑", "v": "jingsong"},
                        {"n": "霸总激情", "v": "bazong"},
                        {"n": "穿越重生", "v": "chuanyue"},
                        {"n": "虐恋情深", "v": "nuelian"},
                        {"n": "战神归来", "v": "zhanshen"},
                        {"n": "末世生存", "v": "moshi"},
                    ]
                },
                {
                    "key": "status",
                    "name": "状态",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "连载中", "v": "ongoing"},
                        {"n": "已完结", "v": "ended"},
                    ]
                },
                {
                    "key": "sort",
                    "name": "排序",
                    "value": [
                        {"n": "最热", "v": "hot"},
                        {"n": "最新", "v": "new"},
                        {"n": "追剧最多", "v": "follow"},
                    ]
                }
            ],
            "aiduanju": [
                {
                    "key": "topic",
                    "name": "题材",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "都市邻里", "v": "dushi"},
                        {"n": "甜宠恋爱", "v": "tianchong"},
                        {"n": "逆袭", "v": "nixi"},
                        {"n": "复仇逆袭", "v": "fuchou"},
                        {"n": "古装玄幻", "v": "xuanhuan"},
                        {"n": "惊悚悬疑", "v": "jingsong"},
                        {"n": "霸总激情", "v": "bazong"},
                        {"n": "穿越重生", "v": "chuanyue"},
                        {"n": "虐恋情深", "v": "nuelian"},
                        {"n": "战神归来", "v": "zhanshen"},
                        {"n": "末世生存", "v": "moshi"},
                    ]
                },
                {
                    "key": "status",
                    "name": "状态",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "连载中", "v": "ongoing"},
                        {"n": "已完结", "v": "ended"},
                    ]
                },
                {
                    "key": "sort",
                    "name": "排序",
                    "value": [
                        {"n": "最热", "v": "hot"},
                        {"n": "最新", "v": "new"},
                        {"n": "追剧最多", "v": "follow"},
                    ]
                }
            ]
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36",
            "Referer": self.host + "/"
        }
        self._cached_host = self.host

    def getName(self):
        return "黄瓜短剧"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 首页推荐：从首页抓取热门剧集
        try:
            resp = self.fetch(self.host + "/", headers=self.headers, timeout=10)
            html = resp.text if resp else ""
            return {"list": self._parse_cards(html)}
        except Exception as e:
            self.log("homeVideoContent error: " + str(e))
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        # 分类页支持分页：/browse?page=N
        page = pg or "1"
        # 解析 extend
        extend_dict = self._parse_extend(extend)
        # 构建 URL 参数
        params = []
        # 内容线：tid 映射到 line 参数
        if tid and tid != "all":
            params.append(f"line={tid}")
        # 题材
        topic = extend_dict.get("topic", "")
        if topic:
            params.append(f"tag={topic}")
        # 状态
        status = extend_dict.get("status", "")
        if status:
            params.append(f"status={status}")
        # 排序
        sort = extend_dict.get("sort", "")
        if sort:
            params.append(f"sort={sort}")
        # 分页：只有 pg > 1 时才添加 page 参数
        if int(page) > 1:
            params.append(f"page={page}")

        url = f"{self.host}/browse"
        if params:
            url += "?" + "&".join(params)

        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            html = resp.text if resp else ""
            cards = self._parse_cards(html)
            # 提取总数量
            total_match = re.search(r'已显示.*?/ 共 (\d+) 部', html)
            total = int(total_match.group(1)) if total_match else len(cards)
            # 提取总页数：从"加载更多"链接或总数量估算
            page_match = re.search(r'<a[^>]*class="load-more"[^>]*href="[^"]*page=(\d+)"', html)
            if page_match:
                next_page = int(page_match.group(1))
                # 如果有 next 链接，说明还有下一页
                pagecount = next_page  # 粗略估计
            else:
                # 没有"加载更多"链接，说明是最后一页
                pagecount = int(page) if int(page) > 1 else 1
            # 更精确的总页数：从 total 和每页数量估算
            if total > 0 and len(cards) > 0:
                estimated_pages = (total + len(cards) - 1) // len(cards)
                pagecount = max(pagecount, estimated_pages)

            return {
                "list": cards,
                "page": int(page),
                "pagecount": pagecount,
                "limit": len(cards) if cards else 20,
                "total": total
            }
        except Exception as e:
            self.log("categoryContent error: " + str(e))
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def _parse_extend(self, extend):
        """解析 extend 参数，支持 dict / 字符串 / JSON 格式"""
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                # 尝试 JSON 解析
                return json.loads(extend)
            except:
                pass
            # 尝试 key=value,key2=value2 格式
            result = {}
            for part in extend.split(','):
                if '=' in part:
                    k, v = part.split('=', 1)
                    result[k.strip()] = v.strip()
            return result
        return {}

    def detailContent(self, ids):
        # 详情页：取标题、简介、选集
        vod_id = str(ids[0]) if ids else ""
        try:
            url = f"{self.host}/drama/{vod_id}"
            resp = self.fetch(url, headers=self.headers, timeout=15)
            html = resp.text if resp else ""

            # 提取标题
            title_match = re.search(r'<h1[^>]*class="page-h1"[^>]*>([^<]+)</h1>', html)
            title = title_match.group(1).strip() if title_match else vod_id

            # 提取简介
            intro_match = re.search(r'<p[^>]*class="detail-intro[^"]*"[^>]*>([^<]*(?:<[^>]+>[^<]*</[^>]+>)*[^<]*)</p>', html, re.DOTALL)
            intro = re.sub(r'<[^>]+>', '', intro_match.group(1).strip()) if intro_match else ""

            # 提取角标
            line_match = re.search(r'<span[^>]*class="pill pill-line"[^>]*>([^<]+)</span>', html)
            line = line_match.group(1).strip() if line_match else ""

            # 提取集数
            ep_links = re.findall(r'<a[^>]*class="ep-link[^"]*"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', html)
            play_urls = []
            for href, ep_num in ep_links:
                if href.startswith("/play/"):
                    play_urls.append(f"第{ep_num}集${self.host}{href}")

            vod_play_url = "#".join(play_urls) if play_urls else ""
            vod_play_from = "黄瓜短剧" if vod_play_url else ""

            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": "",
                "vod_remarks": line,
                "vod_content": intro,
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url
            }
            return {"list": [vod]}
        except Exception as e:
            self.log("detailContent error: " + str(e))
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        # 搜索功能
        try:
            encoded_key = quote(key, safe="")
            url = f"{self.host}/search?q={encoded_key}"
            resp = self.fetch(url, headers=self.headers, timeout=15)
            html = resp.text if resp else ""
            cards = self._parse_cards(html)
            return {"list": cards, "page": int(pg)}
        except Exception as e:
            self.log("searchContent error: " + str(e))
            return {"list": [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        # 播放页解析 HG_PLAY 数据
        try:
            # id 格式：https://hgdju.com/play/{slug}/{ep}
            resp = self.fetch(id, headers=self.headers, timeout=15)
            html = resp.text if resp else ""

            # 提取 HG_PLAY JSON
            match = re.search(r'window\.HG_PLAY\s*=\s*({[^;]+});', html)
            if not match:
                return {"parse": 1, "url": id, "header": self.headers}

            data = json.loads(match.group(1))
            episodes = data.get("episodes", [])
            # 从 URL 中提取集数
            ep_match = re.search(r'/(\d+)$', id)
            ep_idx = int(ep_match.group(1)) - 1 if ep_match else 0

            if ep_idx < len(episodes):
                hls_url = episodes[ep_idx].get("hls", "")
                if hls_url and ".m3u8" in hls_url:
                    # 走 localProxy 代理（法则30）
                    proxy_url = self._m3u8_proxy_url(hls_url)
                    return {"parse": 0, "url": proxy_url, "header": {}}
                mp4_url = episodes[ep_idx].get("mp4", "")
                if mp4_url:
                    return {"parse": 0, "url": mp4_url, "header": self.headers}

            return {"parse": 1, "url": id, "header": self.headers}
        except Exception as e:
            self.log("playerContent error: " + str(e))
            return {"parse": 1, "url": id, "header": self.headers}

    def recommendContent(self, ids, pg):
        # 相关推荐：从详情页抓取推荐列表
        vod_id = str(ids[0]) if ids else ""
        try:
            url = f"{self.host}/drama/{vod_id}"
            resp = self.fetch(url, headers=self.headers, timeout=15)
            html = resp.text if resp else ""

            # 提取相关推荐区域
            sec_match = re.search(r'<section[^>]*class="sec"[^>]*>.*?<h2[^>]*class="sec-title"[^>]*>.*?相关推荐.*?</h2>(.*?)</section>', html, re.DOTALL)
            if sec_match:
                cards = self._parse_cards(sec_match.group(1))
                return {"list": cards}
            return {"list": []}
        except Exception as e:
            self.log("recommendContent error: " + str(e))
            return {"list": []}

    def destroy(self):
        pass

    # ===== 辅助方法 =====

    def _parse_cards(self, html):
        """解析卡片列表（分类页/搜索页/首页/推荐）"""
        cards = []
        # 匹配 .card 结构，更精确的提取
        card_pattern = re.compile(
            r'<div[^>]*class="[^"]*card[^"]*"[^>]*>'
            r'.*?<a[^>]*class="card-main"[^>]*href="([^"]+)"[^>]*>'
            r'.*?<img[^>]*'
            r'(?:z-image-loader-url="([^"]+)"|src="([^"]+)"|data-cover-fb="([^"]+)")'
            r'[^>]*>'
            r'.*?<i[^>]*class="card-line"[^>]*>([^<]+)</i>'
            r'.*?<i[^>]*class="card-ep[^"]*"[^>]*>([^<]+)</i>'
            r'.*?<b[^>]*class="card-title"[^>]*>([^<]+)</b>'
            r'.*?</a>'
            r'.*?<a[^>]*href="([^"]+)"[^>]*>详情</a>'
            r'.*?</div>',
            re.DOTALL
        )
        for match in card_pattern.finditer(html):
            play_href = match.group(1).strip()
            # 图片地址：优先 z-image-loader-url，其次 src，最后 data-cover-fb
            img_url = match.group(2) or match.group(3) or match.group(4) or ""
            img_url = img_url.strip()
            line = match.group(5).strip() if match.group(5) else ""
            remark = match.group(6).strip() if match.group(6) else ""
            title = match.group(7).strip() if match.group(7) else ""
            detail_href = match.group(8).strip() if match.group(8) else ""

            # 提取 vod_id（从详情链接 /drama/xxx）
            vid_match = re.search(r'/drama/([^/?#]+)', detail_href)
            vod_id = vid_match.group(1) if vid_match else ""

            # 封面图补全
            if img_url and not img_url.startswith("http"):
                img_url = urljoin(self.host, img_url)

            if vod_id and title:
                cards.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": img_url,
                    "vod_remarks": remark,
                    "vod_play_from": "黄瓜短剧",
                    "vod_url": urljoin(self.host, play_href)
                })
        return cards

    def _m3u8_proxy_url(self, url):
        """生成 m3u8 代理地址"""
        if not url:
            return ""
        proxy_base = "http://127.0.0.1:9978/proxy?do=py&url="
        return proxy_base + quote(str(url), safe="")

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤（五层管线）"""
        # 解析 target
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

        try:
            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp:
                return [502, "text/plain", b"fetch failed"]
            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]

            if b"#EXTM3U" not in content[:256]:
                return [200, "application/octet-stream", content]

            text = content.decode("utf-8", errors="ignore")
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log("localProxy error: " + str(e))
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]

    def _clean_m3u8(self, text, source_url):
        """五层去广告管线"""
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # ---- 第1层：图片流伪装检测 ----
        if self._is_fake_image_stream(text, source_url):
            restored = text
            for ext in (".png", ".jpeg", ".jpg", ".webp"):
                restored = restored.replace(ext, ".ts")
            self.log("检测到图片流伪装，已还原扩展名 -> .ts，跳过广告过滤")
            # 补全绝对地址
            out = [self._rewrite_m3u8_tag(l, source_url) for l in restored.replace("\r", "").split("\n") if l.strip()]
            return "\n".join(out) + "\n"

        # ---- 第2层：多码率主表 ----
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
            return "\n".join(out) + "\n"

        # ---- 第3层：正片目录锚点 ----
        main_dir = self._resolve_main_dir(lines, source_url)

        # ---- 第4层：分片过滤 ----
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        # ---- 第5层：全滤兜底 ----
        if removed > 0 and (kept == 0 or removed > kept):
            self.log(f"广告过滤命中过多分片(滤{removed}/留{kept})，判定锚点失效，回退为不过滤模式")
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")

        # ---- 第5层续：冗余标签清理 ----
        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def _is_fake_image_stream(self, text, source_url):
        """检测图片流伪装"""
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
        """确定正片目录锚点（KEY URI 优先）"""
        import posixpath
        parsed = urlparse(source_url)
        main_dir = posixpath.dirname(parsed.path)
        if not main_dir.endswith("/"):
            main_dir += "/"

        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            if not key_uri.startswith(("http://", "https://")):
                key_uri = urljoin(source_url, key_uri)
            key_path = urlparse(key_uri).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return main_dir

    def _filter_segments(self, lines, source_url, main_dir):
        """分片过滤"""
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
        # 如果 pending 残留（文件末尾无换行），按广告丢弃
        if pending:
            removed += 1
        return segments, removed, kept

    def _dedup_tags(self, segments, source_url):
        """冗余标签清理"""
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
        return out

    def _rewrite_m3u8_tag(self, line, source_url):
        """补全 URI 绝对地址"""
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