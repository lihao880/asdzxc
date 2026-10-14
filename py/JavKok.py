# coding: utf-8
# ============================================================
# 站点: JavKok (javkok.com)
# 类型: Laravel + Alpine.js 服务端渲染 HTML 站
# 主域: https://javkok.com
# 内容: 日本 AV 影视
# 路由:
#   分类: /{slug}?page={n}   (new/release/uncensored-leak/chinese_subtitle/today/weekly/monthly ...)
#   列表卡片: div.video-card  a[href] -> /{slug}
#   详情: /{slug}   内嵌 data-video-id="148"
#   播放: POST /api/play/{video_id}  -> {status:ok, d:base64}
#         base64 解后 XOR(key=jk_v2_x9Qm4pL7) -> JSON [{url,vtt}]
#   搜索: GET /search?keyword={kw}
# 逆向: /js/video-player.js?v=3 内 fetchSources + _d() XOR
# 最后验证: 2026-09-21
# ============================================================
import json
import base64
import re
from urllib.parse import quote, urljoin, unquote, urlparse

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    XOR_KEY = [106, 107, 95, 118, 50, 95, 120, 57, 81, 109, 52, 112, 76, 55]  # "jk_v2_x9Qm4pL7"

    def __init__(self):
        self.host = "https://javkok.com"
        self.extend = ""
        self.session_cookie = ""
        self.csrf_token = ""
        self.warmed = False

        # 分类静态硬编码（法则16/17，零网络）
        self.classes = [
            {"type_id": "new", "type_name": "最近更新"},
            {"type_id": "release", "type_name": "新作上市"},
            {"type_id": "uncensored-leak", "type_name": "無碼流出"},
            {"type_id": "chinese_subtitle", "type_name": "中文字幕"},
            {"type_id": "today", "type_name": "今日熱門"},
            {"type_id": "weekly", "type_name": "本週熱門"},
            {"type_id": "monthly", "type_name": "本月熱門"},
            {"type_id": "actresses", "type_name": "女優一覽"},
            {"type_id": "genres", "type_name": "類型"},
            {"type_id": "makers", "type_name": "發行商"},
        ]
        self.filters = {}

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        }

    # ---------------- 基础 ----------------

    def getName(self):
        return "JavKok"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 零网络
        self.extend = extend or ""

    def destroy(self):
        pass

    def _hdrs(self, referer=None, extra=None):
        h = dict(self.headers)
        h["Referer"] = referer or (self.host + "/")
        if extra:
            h.update(extra)
        return h

    # ---------------- 首页/分类 ----------------

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return {"list": self._fetch_list(self.host + "/new")}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg or "1")
        base = "%s/%s" % (self.host, tid)
        if pg and pg != "1":
            url = "%s?page=%s" % (base, pg)
        else:
            url = base
        lst = self._fetch_list(url)
        # 总页数：从分页器提取（站点按页显示）
        pagecount = self._parse_pagecount(url, pg)
        return {
            "list": lst,
            "page": int(pg) if pg.isdigit() else 1,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20,
        }

    def _parse_pagecount(self, url, pg):
        try:
            r = self.fetch(url, headers=self._hdrs(), timeout=15)
            if not r or r.status_code != 200:
                return 9999
            html = r.text or ""
            idx = html.find("site-pagination")
            if idx == -1:
                return 1
            seg = html[idx:idx + 6000]
            nums = [int(n) for n in re.findall(r'[?&]page=(\d+)', seg)]
            has_next = bool(re.search(r'data-next-url="[^"]+"', seg))
            cur = int(pg) if str(pg).isdigit() else 1
            if nums:
                mx = max(nums)
                return mx + 1 if has_next else mx
            return 9999 if has_next else cur
        except Exception:
            return 9999
    def _fetch_list(self, url):
        try:
            r = self.fetch(url, headers=self._hdrs(), timeout=15)
            if not r or r.status_code != 200:
                self.log({"action": "list_fail", "url": url, "status": getattr(r, "status_code", None)})
                return []
            return self._parse_cards(r.text or "")
        except Exception as e:
            self.log({"action": "list_exc", "url": url, "error": type(e).__name__})
            return []

    def _parse_cards(self, html):
        items = []
        seen = set()
        # 定位卡片块
        blocks = re.split(r'class="thumbnail group video-card"', html)
        for blk in blocks[1:]:
            blk = blk[:2500]
            # 链接
            m = re.search(r'<a\s+href="(https?://[^"]+)"\s+title="([^"]*)"', blk)
            if not m:
                continue
            href = m.group(1)
            code = m.group(2).strip()
            # 只取详情 slug 链接（形如 host/slug，无多级路径）
            try:
                p = urlparse(href).path.strip("/")
            except Exception:
                continue
            if not p or "/" in p:
                continue
            slug = p
            if slug in seen:
                continue
            seen.add(slug)
            # 标题
            tm = re.search(r'title="[^"]*"\s*>\s*([^<]{2,})</a>', blk)
            name = ""
            if tm:
                name = self._clean(tm.group(1))
            if not name:
                im = re.search(r'alt="([^"]+)"', blk)
                if im:
                    name = self._clean(im.group(1))
            if not name:
                name = code
            # 封面
            pic = ""
            pm = re.search(r'<img[^>]+src="(https?://[^"]+)"', blk)
            if pm:
                pic = pm.group(1)
            # 时长角标
            rem = ""
            rm = re.search(r'>(\d{1,2}:\d{2}:\d{2})<', blk)
            if rm:
                rem = rm.group(1)
            items.append({
                "vod_id": slug,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": rem,
            })
        return items

    @staticmethod
    def _clean(s):
        return re.sub(r"\s+", " ", str(s or "")).strip()

    # ---------------- 搜索 ----------------

    def searchContent(self, key, quick, pg="1"):
        try:
            url = "%s/search?keyword=%s" % (self.host, quote(str(key or ""), safe=""))
            r = self.fetch(url, headers=self._hdrs(), timeout=15)
            if not r or r.status_code != 200:
                return {"list": [], "page": 1}
            return {"list": self._parse_cards(r.text or ""), "page": int(pg) if str(pg).isdigit() else 1}
        except Exception:
            return {"list": [], "page": 1}

    # ---------------- 详情 ----------------

    @staticmethod
    def _norm_ids(ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def _skeleton(self, vid, title="", pic="", remarks=""):
        return {"list": [{
            "vod_id": vid, "vod_name": title or "未知标题", "vod_pic": pic or "",
            "vod_remarks": remarks, "vod_content": "",
            "vod_play_from": "播放", "vod_play_url": "播放$" + str(vid),
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        slug = raw.split("|")[0]
        # 已封装 video_id
        vid = ""
        if "|" in raw:
            vid = raw.split("|", 1)[1]
        try:
            url = "%s/%s" % (self.host, slug)
            r = self.fetch(url, headers=self._hdrs(), timeout=15)
            if not r or r.status_code != 200 or len(r.text or "") < 500:
                return self._skeleton(raw)
            html = r.text or ""

            # 标题
            name = ""
            hm = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            if hm:
                inner = hm.group(1)
                spans = re.findall(r'<span[^>]*>([^<]*)</span>', inner)
                name = self._clean(" ".join(spans)) if spans else self._clean(re.sub(r"<[^>]+>", "", inner))
            if not name:
                tm = re.search(r"<title>([^<]+)</title>", html)
                if tm:
                    name = self._clean(tm.group(1).split("|")[0])
            if not name:
                name = slug

            # 封面
            pic = ""
            pm = re.search(r'poster="(https?://[^"]+)"', html)
            if pm:
                pic = pm.group(1)
            if not pic:
                pm2 = re.search(r'<img[^>]+src="(https?://images-cdn[^"]+)"', html)
                if pm2:
                    pic = pm2.group(1)

            # video_id
            if not vid:
                vm = re.search(r'data-video-id="(\d+)"', html)
                if vm:
                    vid = vm.group(1)

            # 简介 / 演员
            content = ""
            cm = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
            if cm:
                content = self._clean(cm.group(1))

            # 播放ID 封装 slug|video_id
            play_id = slug if not vid else "%s|%s" % (slug, vid)
            vod = {
                "vod_id": raw,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": content,
                "vod_play_from": "播放",
                "vod_play_url": "播放$" + play_id,
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detail_exc", "ids": raw, "error": type(e).__name__})
            return self._skeleton(raw)

    # ---------------- 播放 ----------------

    def _xor_decode(self, b64):
        raw = base64.b64decode(b64)
        k = self.XOR_KEY
        out = "".join(chr(raw[i] ^ k[i % len(k)]) for i in range(len(raw)))
        return json.loads(out)

    def _get_sources(self, video_id):
        """POST /api/play/{id} 拿 m3u8 直链"""
        try:
            url = "%s/api/play/%s" % (self.host, str(video_id).strip())
            # Laravel 防护：需同一 session + X-CSRF-TOKEN + XHR 头
            self._warmup()
            h = {
                "User-Agent": self.headers["User-Agent"],
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.host + "/",
                "Origin": self.host,
            }
            if self.csrf_token:
                h["X-CSRF-TOKEN"] = self.csrf_token
            if self.session_cookie:
                h["Cookie"] = self.session_cookie
            r = self.post(url, headers=h, timeout=15)
            if not r or r.status_code != 200:
                return []
            data = json.loads(r.text or "{}")
            if data.get("status") != "ok" or not data.get("d"):
                return []
            src = self._xor_decode(data["d"])
            return src if isinstance(src, list) else []
        except Exception as e:
            self.log({"action": "play_api_exc", "error": type(e).__name__})
            return []

    def _warmup(self):
        """获取 session cookie + csrf（一次即可）"""
        if self.warmed and self.session_cookie:
            return
        try:
            r = self.fetch(self.host + "/", headers=self._hdrs(), timeout=15)
            if r and r.status_code == 200:
                html = r.text or ""
                m = re.search(r'csrf-token"\s+content="([^"]+)"', html)
                if m:
                    self.csrf_token = m.group(1)
                # 从响应头拿 set-cookie
                try:
                    sc = r.headers.get("Set-Cookie") or r.headers.get("set-cookie") or ""
                    if sc:
                        self.session_cookie = sc.split(";")[0]
                except Exception:
                    pass
                self.warmed = True
        except Exception:
            pass

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id) if id else ""
        if "$" in play_url:
            play_url = play_url.split("$", 1)[1]
        video_id = play_url.split("|", 1)[1] if "|" in play_url else ""
        if not video_id:
            slug = play_url.split("|")[0]
            try:
                r = self.fetch("%s/%s" % (self.host, slug), headers=self._hdrs(), timeout=15)
                if r and r.status_code == 200:
                    vm = re.search(r'data-video-id="(\d+)"', r.text or "")
                    if vm:
                        video_id = vm.group(1)
            except Exception:
                pass
        if not video_id:
            slug = play_url.split("|")[0]
            return {"parse": 1, "url": "%s/%s" % (self.host, slug),
                    "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/"}}
        srcs = self._get_sources(video_id)
        if srcs:
            m3u8 = srcs[0].get("url", "")
            if m3u8:
                # 直连方案（MPV/IJK 兼容最佳，勿套代理）：
                # 返回子流绝对地址 + Referer，播放器透传 header 直连 CDN。
                sub = self._sub_stream_url(m3u8)
                hdr = {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/",
                    "Accept": "*/*",
                }
                return {"parse": 0, "url": sub, "header": hdr}
        slug = play_url.split("|")[0]
        return {"parse": 1, "url": "%s/%s" % (self.host, slug),
                "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/"}}
    def _sub_stream_url(self, master_url):
        """从主表取第一条子流，拼成绝对地址；失败则返回原地址。"""
        try:
            r = self.fetch(master_url, headers={"User-Agent": self.headers["User-Agent"],
                                                "Referer": self.host + "/"}, timeout=15)
            if r and r.status_code == 200 and "#EXTM3U" in (r.text or ""):
                base = master_url.rsplit("/", 1)[0] + "/"
                for line in (r.text or "").replace("\r", "").split("\n"):
                    s = line.strip()
                    if s and not s.startswith("#"):
                        return urljoin(base, s)
        except Exception:
            pass
        return master_url
    def localProxy(self, param):
        try:
            target = unquote(str((param or {}).get("url", "") or ""))
            if not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]
            media_headers = {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
                "Accept": "*/*",
            }
            low = target.lower()
            if ".m3u8" in low:
                r = self.fetch(target, headers=media_headers, timeout=15)
                if not r or r.status_code != 200:
                    self.log({"proxy": "m3u8_fail", "status": getattr(r, "status_code", None)})
                    return [502, "text/plain", b"m3u8 fetch failed"]
                text = r.text or ""
                if "#EXTM3U" not in text:
                    return [502, "text/plain", b"invalid m3u8"]
                base = target.rsplit("/", 1)[0] + "/"
                out = []
                for line in text.replace("\r", "").split("\n"):
                    s = line.strip()
                    if not s:
                        out.append(line)
                        continue
                    if s.startswith("#EXT-X-KEY") or s.startswith("#EXT-X-MAP"):
                        out.append(re.sub(r'URI="([^"]+)"',
                                          lambda m: 'URI="' + self._proxy_media(urljoin(base, m.group(1))) + '"',
                                          s))
                    elif s.startswith("#"):
                        out.append(s)
                    else:
                        out.append(self._proxy_media(urljoin(base, s)))
                body = "\n".join(out).encode("utf-8")
                self.log({"proxy": "m3u8_ok", "lines": len(out), "bytes": len(body)})
                return [200, "application/vnd.apple.mpegurl", body]
            else:
                r = self.fetch(target, headers=media_headers, timeout=20)
                if not r or getattr(r, "status_code", 0) != 200:
                    self.log({"proxy": "seg_fail", "status": getattr(r, "status_code", None)})
                    return [502, "text/plain", b"media fetch failed"]
                content = getattr(r, "content", None)
                if content is None:
                    try:
                        content = r.text.encode("utf-8", errors="ignore")
                    except Exception:
                        content = b""
                self.log({"proxy": "seg_ok", "bytes": len(content), "ct": "video/mp2t"})
                if low.endswith((".ts", ".m4s")):
                    ctype = "video/mp2t"
                elif low.endswith((".jpeg", ".jpg", ".webp", ".png")):
                    ctype = "video/mp2t"
                else:
                    ctype = "application/octet-stream"
                return [200, ctype, content]
        except Exception as e:
            self.log({"action": "proxy_exc", "error": type(e).__name__})
            return [500, "text/plain", b"proxy error"]
    def _proxy_media(self, url):
        base = self.getProxyUrl()
        sep = "&" if "?" in base else "?"
        return base + sep + "url=" + quote(str(url), safe="")
    def recommendContent(self, ids, pg):
        return {"list": []}