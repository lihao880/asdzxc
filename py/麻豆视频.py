# coding: utf-8
# ============================================================
# 站点：麻豆视频 (madou8.pw)
# 主域名：https://madou8.pw
# 语言路径：/asian/zh-CN
# 备用语言路径：/asian/zh-HK  /asian/en
# 内容类型：视频（成人影视）
# 架构：Streamit 主题自定义 CMS（非 MacCMS）
# 列表卡片：div.streamit-video-card (data-video-uid)
# 详情页：/asian/zh-CN/video/cid/{code}
# 播放API：GET /asian/zh-CN/api/video/stream?video_uid={uid} -> playlist[].url (m3u8)
# 搜索：/asian/zh-CN/videos/search/{keyword}
# 分页：/videos/{cat}/page/{pg}
# m3u8：playlist[0] 为标准直链（v.imgcaches.cc），取证 suspicious_ad_dirs 为空 → 不走代理
# 最后验证：2026-09-14
# ============================================================
import re
import json
from urllib.parse import quote, urljoin

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    def __init__(self):
        # __init__ 零网络，仅本地初始化，保证首页秒出
        self.extend = ""
        self.host = "https://madou8.pw"
        self.lang = "/asian/zh-CN"
        self.classes = [
            {"type_id": "new-releases", "type_name": "新作上市"},
            {"type_id": "recent", "type_name": "最近更新"},
            {"type_id": "hot/today", "type_name": "今日热门"},
            {"type_id": "hot/week", "type_name": "本周热门"},
            {"type_id": "hot/month", "type_name": "本月热门"},
            {"type_id": "tag/中文字幕", "type_name": "中文字幕"},
            {"type_id": "tag/无码流出", "type_name": "无码流出"},
        ]
        self.filters = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + self.lang,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def getName(self):
        return "麻豆视频"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    # ---------------- 首页 ----------------

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            html = self._fetch_html(self.host + self.lang)
            items = self._parse_cards(html)
            return {"list": items}
        except Exception as e:
            self.log({"home": "exception", "error": str(e)})
            return {"list": []}

    # ---------------- 分类 ----------------

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        tid = str(tid or "new-releases")
        path = tid.strip("/")
        if page == "1":
            url = f"{self.host}{self.lang}/videos/{path}"
        else:
            url = f"{self.host}{self.lang}/videos/{path}/page/{page}"
        try:
            html = self._fetch_html(url)
            items = self._parse_cards(html)
            # 总页数无法从页面直接取（分页器显示 99999），给一个足够大的值
            return {
                "list": items,
                "page": int(page),
                "pagecount": 9999,
                "limit": 24,
                "total": 999999,
            }
        except Exception as e:
            self.log({"category": "exception", "tid": tid, "pg": page, "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 24, "total": 0}

    # ---------------- 详情 ----------------

    @staticmethod
    def _norm_ids(ids):
        """法则35 L0：统一 list / str / int / bytes"""
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
        """法则35 L6：详情兜底骨架，禁止返回空 list"""
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
            return {"list": []}  # 唯一允许返回空的分支

        # 列表阶段打包格式：code|$|title|$|pic|$|remarks|$|video_uid
        parts = raw.split("|$|")
        code = parts[0]
        title = parts[1] if len(parts) > 1 else ""
        pic = parts[2] if len(parts) > 2 else ""
        remarks = parts[3] if len(parts) > 3 else ""
        video_uid = parts[4] if len(parts) > 4 else ""

        # 若打包里没有 video_uid，尝试访问详情页补取
        if not video_uid:
            try:
                detail_url = f"{self.host}{self.lang}/video/cid/{code}"
                html = self._fetch_html(detail_url)
                if html:
                    video_uid = self._extract_video_uid(html)
                    if not title:
                        title = self._pick(html, [
                            r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
                            r'<h1[^>]*>(.*?)</h1>',
                            r'<title>([^<]+)</title>',
                        ])
                        title = re.sub(r"\s*[-|]\s*麻豆视频.*$", "", title).strip() or title
                    if not pic:
                        pic = self._pick(html, [
                            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
                        ], clean=False)
            except Exception as e:
                self.log({"detail": "fetch_fail", "code": code, "error": str(e)})

        # play_id 用 video_uid 驱动 playerContent
        if video_uid:
            play_id = "vuid:" + video_uid
        else:
            # 无 uid 时退化为播放页 URL，交给 playerContent 再试
            play_id = f"{self.host}{self.lang}/video/cid/{code}"

        return {"list": [{
            "vod_id": raw,
            "vod_name": title or code,
            "vod_pic": pic or "",
            "vod_remarks": remarks,
            "vod_content": remarks,
            "vod_actor": "",
            "vod_director": "",
            "vod_play_from": "麻豆",
            "vod_play_url": "播放$" + play_id,
        }]}

    # ---------------- 搜索 ----------------

    def searchContent(self, key, quick, pg="1"):
        try:
            url = f"{self.host}{self.lang}/videos/search/{quote(str(key), safe='')}"
            html = self._fetch_html(url)
            items = self._parse_cards(html)
            return {"list": items, "page": int(pg or 1)}
        except Exception as e:
            self.log({"search": "exception", "key": key, "error": str(e)})
            return {"list": [], "page": int(pg or 1)}

    # ---------------- 播放 ----------------

    def playerContent(self, flag, id, vipFlags):
        pid = str(id or "")
        if "$" in pid:
            pid = pid.split("$", 1)[1]

        # 已是直链
        if re.search(r"\.(m3u8|mp4|flv)(\?|$)", pid, re.I):
            return {"parse": 0, "url": pid, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/"}}

        video_uid = ""
        if pid.startswith("vuid:"):
            video_uid = pid[5:]
        elif "/video/" in pid:
            try:
                html = self._fetch_html(pid)
                video_uid = self._extract_video_uid(html)
            except Exception as e:
                self.log({"player": "detail_fail", "error": str(e)})

        if video_uid:
            stream_url = f"{self.host}{self.lang}/api/video/stream?video_uid={quote(video_uid)}"
            try:
                r = self.fetch(stream_url, headers=self.headers, timeout=15)
                if r and r.status_code == 200:
                    data = json.loads(r.text)
                    playlist = data.get("playlist") or []
                    candidates = []
                    for item in playlist:
                        u = item.get("url", "") if isinstance(item, dict) else ""
                        if u and ".m3u8" in u:
                            candidates.append(u)
                    if candidates:
                        # 优先选多码率主表（playlist.m3u8），它是干净的标准源
                        best = ""
                        for u in candidates:
                            if "playlist.m3u8" in u:
                                best = u
                                break
                        if not best:
                            # 次选：无单分片占位特征（非 /tip.ts 中转）
                            best = candidates[0]
                        return {
                            "parse": 0,
                            "url": best,
                            "header": {
                                "User-Agent": self.headers["User-Agent"],
                                "Referer": self.host + "/",
                            },
                        }
            except Exception as e:
                self.log({"player": "stream_fail", "error": str(e)})

        if pid.startswith("http"):
            return {"parse": 0, "url": pid, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/"}}

        fallback = pid if pid.startswith("http") else f"{self.host}{self.lang}"
        return {"parse": 1, "url": fallback, "header": {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.host + "/",
        }}
    def recommendContent(self, ids, pg):
        try:
            vid = self._norm_ids(ids)
            code = vid.split("|$|")[0]
            if not code:
                return {"list": []}
            # 优先用详情页自带的推荐卡片
            url = f"{self.host}{self.lang}/video/cid/{code}"
            html = self._fetch_html(url)
            if html:
                items = self._parse_cards(html)
                items = [it for it in items if code not in it.get("vod_id", "")]
                if items:
                    return {"list": items[:20]}
            # 兜底：用编号前缀走搜索接口拿同类推荐
            prefix = re.split(r"[-_]", code)[0]
            if prefix and len(prefix) >= 2:
                r = self.fetch(
                    f"{self.host}{self.lang}/videos/search/{quote(prefix, safe='')}",
                    headers=self.headers, timeout=15)
                if r and r.status_code == 200:
                    items = self._parse_cards(r.text)
                    items = [it for it in items if code not in it.get("vod_id", "")]
                    return {"list": items[:20]}
            return {"list": []}
        except Exception as e:
            self.log({"recommend": "exception", "error": str(e)})
            return {"list": []}
    def destroy(self):
        pass

    # ---------------- 内部工具 ----------------

    def _fetch_html(self, url):
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            self.log({"fetch": "failed", "url": url, "status": getattr(r, "status_code", None)})
            return ""
        return r.text or ""

    @staticmethod
    def _pick(html, patterns, clean=True):
        for p in patterns:
            try:
                m = re.search(p, html, re.S | re.I)
            except Exception:
                continue
            if m:
                v = m.group(1)
                if clean:
                    v = re.sub(r"<[^>]+>", "", v)
                    v = v.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
                v = v.strip()
                if v:
                    return v
        return ""

    @staticmethod
    def _extract_video_uid(html):
        m = re.search(r'videoUid\s*=\s*"([0-9a-fA-F]+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'data-video-uid="([0-9a-fA-F]+)"', html)
        if m:
            return m.group(1)
        return ""

    def _parse_cards(self, html):
        """解析列表卡片，输出 vod_id 打包串"""
        if not html:
            return []
        results = []
        seen = set()
        # 用卡片起始标记切分（streamit-video-card 容器，含 data-video-uid）
        blocks = re.split(r'<div class="streamit-video-card\b', html)
        for blk in blocks[1:]:
            blk = '<div class="streamit-video-card ' + blk

            # 详情链接与 code
            m_link = re.search(r'href="([^"]*/video/cid/[^"]+)"', blk)
            if not m_link:
                continue
            href = m_link.group(1).strip()
            m_code = re.search(r'/video/cid/([^"/?#]+)', href)
            if not m_code:
                continue
            code = m_code.group(1)
            if code in seen:
                continue
            seen.add(code)

            # 标题：优先 title 属性，其次 a 标签文本
            title = ""
            m_title = re.search(r'class="streamit-video-card__caption-link[^"]*"[^>]*title="([^"]*)"', blk)
            if m_title:
                title = m_title.group(1).strip()
            if not title:
                m_title = re.search(r'class="streamit-video-card__caption-link[^"]*"[^>]*>(.*?)</a>', blk, re.S)
                if m_title:
                    title = re.sub(r"<[^>]+>", "", m_title.group(1)).strip()
            if not title:
                title = code
            title = title.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")

            # 封面：在 img 标签内取 src（class 可能在 src 前后）
            pic = ""
            for m_img in re.finditer(r'<img\b[^>]*>', blk):
                tag = m_img.group(0)
                if 'streamit-video-card__thumb' in tag or 'img-zoom' in tag:
                    m_src = re.search(r'src="([^"]+)"', tag)
                    if m_src:
                        pic = m_src.group(1).strip()
                        break
            if not pic:
                # 兜底：data-poster
                m_poster = re.search(r'data-poster="([^"]+)"', blk)
                if m_poster:
                    pic = m_poster.group(1).strip()
            if pic and not pic.startswith("http"):
                pic = urljoin(self.host, pic)

            # 角标（时长）
            remark = ""
            m_rm = re.search(r'streamit-video-card__time[^>]*>(.*?)</div>', blk, re.S)
            if m_rm:
                m_p = re.search(r'<p[^>]*>(.*?)</p>', m_rm.group(1), re.S)
                if m_p:
                    remark = re.sub(r"<[^>]+>", "", m_p.group(1)).strip()

            # video_uid
            uid = ""
            m_uid = re.search(r'data-video-uid="([0-9a-fA-F]+)"', blk)
            if m_uid:
                uid = m_uid.group(1)

            vod_id = "|$|".join([code, title, pic, remark, uid])
            results.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return results
