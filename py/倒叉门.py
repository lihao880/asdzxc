# -*- coding: utf-8 -*-
# ============================================================
# 站点名称：倒叉门
# 主域名：https://pd.daocamen03.xyz
# 内容类型：成人视频（聚合/多分区站）
# 分类入口：category.php?name=<分类名>&page=N
# 详情/播放ID：detail.php?id=<m3u8完整地址>（ID 即 m3u8 地址）
# 搜索入口：search.php?q=<关键词>
# 图片：data-original，标准 JPEG（data-aes 为装饰标记，实测未加密）
# m3u8：多码率主表；广告目录 /20260830/i2vAQKIt/1000kb/hls/，需 localProxy 清洗
# 最后验证：2026-09-13
# ============================================================
import re
import json
from urllib.parse import quote, urljoin

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    def __init__(self):
        self.host = "https://pd.daocamen03.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }
        # 分类：静态硬编码（法则16/17）
        self.categories = [
            {"type_id": "有码中字", "type_name": "有码中字"},
            {"type_id": "无码中字", "type_name": "无码中字"},
            {"type_id": "国产视频", "type_name": "国产视频"},
            {"type_id": "成人动漫", "type_name": "成人动漫"},
            {"type_id": "日本无码", "type_name": "日本无码"},
            {"type_id": "日本有码", "type_name": "日本有码"},
            {"type_id": "欧美视频", "type_name": "欧美视频"},
            {"type_id": "网曝吃瓜", "type_name": "网曝吃瓜"},
        ]
        self.filters = {c["type_id"]: [] for c in self.categories}

    # ---------------- 基础 ----------------

    def getName(self):
        return "倒叉门"

    def init(self, extend=""):
        # 零网络依赖（法则16）
        pass

    def isVideoFormat(self, url):
        return bool(url) and any(url.split("?")[0].endswith(e)
                                 for e in (".m3u8", ".mp4", ".flv", ".m4s"))

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        return {"class": self.categories, "filters": self.filters}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except Exception:
                pass
            result = {}
            for part in extend.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    result[k.strip()] = v.strip()
            return result
        return {}

    # ---------------- 解析 ----------------

    def _abs(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        return urljoin(self.host + "/", url.lstrip("./"))

    def _pic(self, img):
        if not img:
            return ""
        for attr in ("data-original", "data-src", "src"):
            v = img.get(attr)
            if v:
                return self._abs(v)
        return ""

    def _parse_list(self, html, doc=None):
        """列表解析（纯正则，不依赖 self.html）：容器 .vod，
        链接 .vod-img a[href*=detail.php?id=]，标题 .vod-txt a，封面 .content-img"""
        items = []
        seen = set()
        if not html:
            return items
        # 按 <div class="vod"> 切块
        blocks = re.split(r'<div\s+class="vod">', html)
        for blk in blocks[1:]:
            try:
                m = re.search(r'detail\.php\?id=(https?://[^"&\']+)', blk)
                if not m:
                    continue
                vid = m.group(1).strip()
                if vid in seen:
                    continue
                seen.add(vid)
                # 标题：vod-txt 内 a 文本，去内联标签
                name = ""
                tm = re.search(r'<div\s+class="vod-txt">\s*<a[^>]*>(.*?)</a>', blk, re.S)
                if tm:
                    name = re.sub(r"<[^>]+>", "", tm.group(1)).strip()
                if not name:
                    tm = re.search(r'<img[^>]+alt="([^"]*)"', blk)
                    name = (tm.group(1).strip() if tm else "")
                # 封面：data-original 优先
                pic = ""
                pm = re.search(r'data-original="([^"]+)"', blk)
                if not pm:
                    pm = re.search(r'<img[^>]+src="([^"]+)"', blk)
                if pm:
                    pic = self._abs(pm.group(1))
                items.append({
                    "vod_id": vid,
                    "vod_name": name or "未知标题",
                    "vod_pic": pic,
                    "vod_remarks": "",
                })
            except Exception:
                continue
        return items
    def homeVideoContent(self):
        r = self.fetch(self.host + "/", headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            self.log({"homeVideoContent": "fetch_failed"})
            return {"list": []}
        return {"list": self._parse_list(r.text)}

    # ---------------- 分类列表 ----------------

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        url = "{}/category.php?name={}&page={}".format(
            self.host, quote(str(tid)), page)
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            self.log({"categoryContent": "fetch_failed", "pg": page})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        lst = self._parse_list(r.text)
        # 分页实测：pagination_parser → 8 页
        total_pages = 8
        m = re.search(r"尾页.*?page=(\d+)", r.text, re.S)
        if m:
            try:
                total_pages = int(m.group(1))
            except Exception:
                pass
        return {
            "list": lst,
            "page": int(page),
            "pagecount": total_pages,
            "limit": 20,
            "total": total_pages * 20,
        }

    # ---------------- 详情 ----------------

    def detailContent(self, ids):
        # ids 归一化（法则35）
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ""
        else:
            vid = str(ids) if ids else ""
        if not vid:
            return {"list": []}
        if "$" in vid:
            vid = vid.split("$", 1)[1]

        candidates = [
            "{}/detail.php?id={}".format(self.host, vid),
            "{}/play.php?id={}".format(self.host, vid),
        ]
        html = ""
        for u in candidates:
            r = self.fetch(u, headers=self.headers, timeout=15)
            if r and r.status_code == 200 and r.text and len(r.text) > 500:
                html = r.text
                break
        if not html:
            return {"list": [{
                "vod_id": vid, "vod_name": "未知标题", "vod_pic": "",
                "vod_content": "", "vod_play_from": "播放",
                "vod_play_url": "播放${}".format(vid),
            }]}

        # 关键：站点对旧视频的 detail 页会把「详情区块」显示成其它视频，
        # 目标视频只出现在「相关推荐」里。
        # 因此用 vid 在整页里做精确锚定：找到 href/id 与 vid 相同的那条记录，
        # 其对应标题才是正确标题；详情区块仅作兜底。
        title = ""
        pic = ""
        content = ""

        # 1) 优先：从详情页所有卡片里，找 href 含本 vid 的那条，取其标题
        #    卡片结构：<a href="...detail.php?id=<vid>">封面</a> ... <div class="vod-txt"><a href="...id=<vid>">标题</a>
        esc = re.escape(vid)
        # 同卡片内的标题：以 vid 出现位置为锚，向后找最近的 vod-txt 标题
        for m in re.finditer(r'detail\.php\?id=' + esc + r'[^"]*"[^>]*>', html):
            seg = html[m.start(): m.start() + 3000]
            tm = re.search(r'<div\s+class="vod-txt">\s*<a[^>]*>(.*?)</a>', seg, re.S)
            if tm:
                cand = re.sub(r"<[^>]+>", "", tm.group(1)).strip()
                cand = cand.replace("&amp;", "&")
                if cand and cand not in ("视频详情", "倒叉门", "返回首页"):
                    title = cand
                    pm = re.search(r'data-original="([^"]+)"', seg) or \
                         re.search(r'<img[^>]+src="([^"]+)"', seg)
                    if pm:
                        pic = self._abs(pm.group(1))
                    break

        # 2) 兜底：详情区块标题（跳过固定栏目名）
        if not title:
            SKIP = {"视频详情", "倒叉门", "返回首页", ""}
            for tm in re.findall(r"<h3[^>]*>(.*?)</h3>", html, re.S):
                cand = re.sub(r"<[^>]+>", "", tm).strip()
                if cand and cand not in SKIP and len(cand) >= 4:
                    title = cand
                    break

        if not pic:
            mm = re.search(r'<img\s+src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', html, re.I)
            if mm:
                pic = self._abs(mm.group(1))

        tags = re.findall(r'search\.php\?q=[^"]+"[^>]*>([^<]+)</a>', html)
        if tags:
            content = "标签：" + "、".join(dict.fromkeys(tags))

        return {"list": [{
            "vod_id": vid,
            "vod_name": title or "未知标题",
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": content,
            "vod_play_from": "播放",
            "vod_play_url": "播放${}".format(vid),
        }]}
    def searchContent(self, key, quick, pg="1"):
        url = "{}/search.php?q={}".format(self.host, quote(str(key)))
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            self.log({"searchContent": "fetch_failed"})
            return {"list": [], "page": 1}
        return {"list": self._parse_list(r.text), "page": 1}

    # ---------------- 推荐 ----------------

    def recommendContent(self, ids, pg):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        if not vid:
            return {"list": []}
        r = self.fetch("{}/detail.php?id={}".format(self.host, vid),
                       headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return {"list": []}
        lst = self._parse_list(r.text)
        # 去掉自身
        return {"list": [x for x in lst if x.get("vod_id") != vid][:20]}

    # ---------------- 播放 ----------------

    def playerContent(self, flag, id, vipFlags):
        # id 可能是 "名称$地址"
        play_url = str(id or "")
        if "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]
        if play_url and not play_url.startswith("http"):
            play_url = ("https:" + play_url) if play_url.startswith("//") \
                else ("https://" + play_url)
        if not play_url:
            return {"parse": 0, "url": "", "header": self.headers}

        # 按域名分流（法则30）：仅确认有广告目录的源走代理
        host = play_url.split("/")[2] if "://" in play_url else ""
        if "kjbwhcnao.com" in host:
            # getProxyUrl() 形态不定：
            #   部分壳端返回 http://127.0.0.1:9978/proxy
            #   部分返回 http://127.0.0.1:9978/proxy?do=py
            # 统一规整为 基址 + /proxy?do=py&url=<编码后地址>
            base = self.getProxyUrl() or ""
            base = base.split("?")[0].rstrip("/")          # 去掉已有 query 和尾部斜杠
            if base.endswith("/proxy"):
                proxy_url = "{}?do=py&url={}".format(base, quote(play_url, safe=""))
            else:
                proxy_url = "{}/proxy?do=py&url={}".format(base, quote(play_url, safe=""))
            self.log({"player": "proxy", "host": host, "proxy": proxy_url.split("&url=")[0]})
            return {"parse": 0, "url": proxy_url, "header": self.headers}

        self.log({"player": "direct", "host": host})
        return {"parse": 0, "url": play_url, "header": self.headers}
    def _clean_m3u8(self, text, base_url):
        # 广告目录（m3u8_analyzer 取证结论：18 个广告分片来自此目录）
        AD_DIRS = ["/20260830/i2vAQKIt/1000kb/hls/"]

        base_dir = base_url.rsplit("/", 1)[0] + "/"
        origin = "/".join(base_url.split("/")[:3])

        # 第2层：多码率主表 —— 子流必须改写为【代理地址】，
        # 否则播放器直连子流，子流未经清洗，广告照播（实测踩坑）
        if "#EXT-X-STREAM-INF" in text:
            proxy_base = self.getProxyUrl() or ""
            proxy_base = proxy_base.split("?")[0].rstrip("/")
            out = []
            for ln in text.split("\n"):
                if ln and not ln.startswith("#") and not ln.startswith("http"):
                    if ln.startswith("/"):
                        sub_abs = origin + ln
                    else:
                        sub_abs = base_dir + ln
                    # 子流改走代理，保证二次清洗
                    if proxy_base.endswith("/proxy"):
                        ln = "{}?do=py&url={}".format(proxy_base, quote(sub_abs, safe=""))
                    else:
                        ln = "{}/proxy?do=py&url={}".format(proxy_base, quote(sub_abs, safe=""))
                out.append(ln)
            return "\n".join(out)

        lines = text.split("\n")
        out = []
        removed = 0
        kept = 0
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("#EXTINF"):
                seg = lines[i + 1] if i + 1 < len(lines) else ""
                if seg.startswith("http"):
                    seg_full = seg
                elif seg.startswith("/"):
                    seg_full = origin + seg
                else:
                    seg_full = urljoin(base_dir, seg)
                if any(d in seg_full for d in AD_DIRS):
                    removed += 1
                    i += 2
                    continue
                out.append(line)
                out.append(seg_full)
                kept += 1
                i += 2
                continue
            out.append(line)
            i += 1

        # 第5层：全滤兜底
        if removed > 0 and (kept == 0 or removed > kept):
            self.log({"m3u8": "fallback_original", "removed": removed, "kept": kept})
            return text

        cleaned = []
        prev = None
        for ln in out:
            if ln.startswith("#EXT-X-DISCONTINUITY") and prev and \
               prev.startswith("#EXT-X-DISCONTINUITY"):
                continue
            cleaned.append(ln)
            prev = ln
        self.log({"m3u8": "filtered", "removed": removed, "kept": kept})
        return "\n".join(cleaned)
    def localProxy(self, param):
        url = param.get("url") if isinstance(param, dict) else None
        if not url:
            return [404, "text/plain; charset=utf-8", "no url"]
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return [502, "text/plain; charset=utf-8", "fetch failed"]
        text = self._clean_m3u8(r.text, url)
        return [200, "application/vnd.apple.mpegurl; charset=utf-8", text]

    # ---------------- 清理 ----------------

    def destroy(self):
        pass