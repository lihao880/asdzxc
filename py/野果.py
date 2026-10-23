# -*- coding: utf-8 -*-
import json
import re
import math
from urllib.parse import urljoin, quote, urlparse, urlunparse

import requests


class Spider:
    def __init__(self, extend=""):
        self.extend = extend
        self.host = "https://analyze.buxefaex.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def init(self, extend=""):
        self.extend = extend

    # ---------- 请求 ----------
    def _get(self, url, referer=None):
        h = dict(self.headers)
        if referer:
            h["Referer"] = referer
        r = self.session.get(url, headers=h, timeout=20)
        r.encoding = "utf-8"
        return r

    def _page_and_payload(self, page_url):
        if not page_url.startswith("http"):
            page_url = urljoin(self.host, page_url)
        r = self._get(page_url)
        html = r.text
        data = None

        m = re.search(r'(/_payload\.json[^"\'\s<>]*)', html)
        pu = None
        if m:
            pu = urljoin(page_url, m.group(1))
        else:
            parsed = urlparse(page_url)
            pu = urlunparse((parsed.scheme, parsed.netloc,
                             parsed.path.rstrip("/") + "/_payload.json", "", "", ""))

        if pu:
            try:
                data = self._get(pu, page_url).json()
            except Exception:
                data = None
        return data, html, page_url

    # ---------- 递归工具 ----------
    def _walk(self, obj):
        yield obj
        if isinstance(obj, dict):
            for v in obj.values():
                yield from self._walk(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from self._walk(v)

    def _find_list(self, data, keys):
        best = None
        for node in self._walk(data):
            if not isinstance(node, list) or not node:
                continue
            dicts = [x for x in node if isinstance(x, dict)]
            if not dicts:
                continue
            if not any(any(k in d for k in keys) for d in dicts):
                continue
            score = len(dicts)
            if any(any(k in d for k in ("title", "name")) for d in dicts):
                score += 100
            if best is None or score > best[0]:
                best = (score, node)
        return best[1] if best else []

    def _first_str(self, item, keys):
        for k in keys:
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    def _extract_id(self, item):
        for k in ("id", "dramaId", "drama_id", "videoId", "episodeId", "slug"):
            v = item.get(k)
            if v not in (None, ""):
                return str(v)
        for k in ("path", "url", "link", "href"):
            v = item.get(k)
            if isinstance(v, str):
                m = re.search(r'/drama/detail/(\d+)', v)
                if m:
                    return m.group(1)
        return None

    def _pic(self, item):
        for k in ("cover", "pic", "poster", "image", "thumbnail", "coverUrl", "img"):
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                v = v.strip()
                if v.startswith("//"):
                    return "https:" + v
                if v.startswith("/"):
                    return urljoin(self.host, v)
                if v.startswith("http"):
                    return v
        return ""

    def _remark(self, item):
        tags = item.get("tags") or item.get("tag") or item.get("categories")
        if isinstance(tags, list):
            tags = " ".join([str(x) for x in tags if x])
        if isinstance(tags, str) and tags.strip():
            return tags.strip()[:30]
        for k in ("playCount", "views", "remark"):
            v = item.get(k)
            if isinstance(v, (str, int)) and str(v).strip():
                return str(v)[:30]
        return ""

    def _parse_items(self, items):
        out, seen = [], set()
        for it in items:
            if not isinstance(it, dict):
                continue
            vid = self._extract_id(it)
            title = self._first_str(it, ("title", "name", "vod_name", "dramaName"))
            if not vid or not title or vid in seen:
                continue
            seen.add(vid)
            out.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._pic(it),
                "vod_remarks": self._remark(it),
            })
        return out

    def _total(self, data, html):
        for node in self._walk(data):
            if isinstance(node, dict):
                for k in ("total", "totalCount", "count"):
                    v = node.get(k)
                    if isinstance(v, int) and v > 0:
                        return v
                    if isinstance(v, str) and v.isdigit():
                        return int(v)
        m = re.search(r'共\s*(\d+)\s*条', html or "")
        return int(m.group(1)) if m else 0

    # ---------- 媒体链接收集 ----------
    def _collect_media(self, data, html):
        """从 payload 和 HTML 里收集所有 m3u8/mp4，去重保序。"""
        urls = []
        seen = set()

        def add(u):
            if not u:
                return
            u = u.replace("\\/", "/").strip()
            if u.startswith("//"):
                u = "https:" + u
            if not u.startswith("http"):
                return
            if ".m3u8" not in u and ".mp4" not in u:
                return
            if u in seen:
                return
            seen.add(u)
            urls.append(u)

        # payload 递归
        for node in self._walk(data):
            if isinstance(node, str):
                for m in re.finditer(r'https?://[^\s"\'<>\\]+?\.(?:m3u8|mp4)(?:\?[^\s"\'<>\\]*)?', node):
                    add(m.group(0))
        # HTML 正则
        for m in re.finditer(r'https?://[^\s"\'<>\\]+?\.(?:m3u8|mp4)(?:\?[^\s"\'<>\\]*)?', html or ""):
            add(m.group(0))
        return urls

    def _ep_titles(self, data, html, n):
        """尝试从 payload 或 HTML 提取剧集标题，不够就用 第N集。"""
        titles = []

        # payload 里找剧集对象
        for node in self._walk(data):
            if isinstance(node, list) and node and all(isinstance(x, dict) for x in node):
                names = []
                for x in node:
                    t = self._first_str(x, ("title", "name", "episodeName", "epName", "episode"))
                    if t and re.search(r'第\s*\d+\s*[集话]|EP?\s*\d+', t, re.I):
                        names.append(t)
                if len(names) >= min(n, 2):
                    titles = names
                    break

        # HTML 里找 第N集
        if not titles:
            found = re.findall(r'(第\s*\d+\s*[集话])', html or "")
            if found:
                titles = [re.sub(r'\s+', '', x) for x in found]

        # 补齐
        while len(titles) < n:
            titles.append(f"第{len(titles)+1}集")
        return titles[:n]

    def _play_header(self):
        return json.dumps({
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.host + "/",
        }, ensure_ascii=False)

    # ---------- TVBox 接口 ----------
    def homeContent(self, filter):
        return {
            "class": [{"type_id": "drama", "type_name": "短剧"}],
            "filters": {},
        }

    def categoryContent(self, tid, pg, filter, extend):
        tid = (tid or "drama").split("|")[0]
        pg = int(pg or 1)
        page_url = f"{self.host}/explore/{tid}/" if pg <= 1 \
            else f"{self.host}/explore/{tid}/page/{pg}/"

        data, html, _ = self._page_and_payload(page_url)
        items = self._find_list(data, ("title", "name", "cover", "pic", "id", "slug", "path", "url"))
        vod_list = self._parse_items(items)
        total = self._total(data, html)
        limit = 20
        pagecount = math.ceil(total / limit) if total else 1

        return {
            "list": vod_list,
            "page": pg,
            "pagecount": pagecount,
            "limit": limit,
            "total": total or len(vod_list),
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        page_url = f"{self.host}/drama/detail/{vid}/"
        data, html, _ = self._page_and_payload(page_url)

        # 详情对象
        detail = {}
        for node in self._walk(data):
            if isinstance(node, dict) and any(str(node.get(k)) == vid for k in ("id", "dramaId", "drama_id")):
                detail = node
                break
        if not detail:
            for node in self._walk(data):
                if isinstance(node, dict) and any(k in node for k in ("title", "name")):
                    if any(k in node for k in ("cover", "pic", "poster", "description", "desc")):
                        detail = node
                        break

        # HTML 兜底标题
        title = self._first_str(detail, ("title", "name", "vod_name", "dramaName"))
        if not title:
            m = re.search(r'<title>(.*?)</title>', html or "", re.S)
            if m:
                title = re.sub(r'\s*[-|].*$', '', m.group(1)).strip()

        pic = self._pic(detail)
        if not pic:
            m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html or "")
            if m:
                pic = urljoin(self.host, m.group(1))

        desc = self._first_str(detail, ("description", "desc", "content", "summary"))
        if not desc:
            m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html or "")
            if m:
                desc = m.group(1)

        # 收集媒体 + 标题
        medias = self._collect_media(data, html)
        titles = self._ep_titles(data, html, len(medias)) if medias else []

        play_urls = []
        for i, u in enumerate(medias):
            play_urls.append(f"{titles[i]}${u}")

        if not play_urls:
            play_urls = [f"正片${page_url}"]

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title or f"短剧{vid}",
                "vod_pic": pic,
                "vod_content": desc,
                "vod_play_from": "野果",
                "vod_play_url": "#".join(play_urls),
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        q = quote(key)
        candidates = [
            f"{self.host}/search?q={q}",
            f"{self.host}/search?keyword={q}",
            f"{self.host}/search/{q}/",
            f"{self.host}/explore/drama/search?q={q}",
            f"{self.host}/explore/drama/?q={q}",
            f"{self.host}/explore/drama/search/{q}/",
        ]
        if pg > 1:
            candidates += [
                f"{self.host}/search?q={q}&page={pg}",
                f"{self.host}/search/{q}/page/{pg}/",
                f"{self.host}/explore/drama/search/{q}/page/{pg}/",
            ]

        for url in candidates:
            try:
                data, html, _ = self._page_and_payload(url)
                items = self._find_list(data, ("title", "name", "cover", "pic", "id", "slug", "path", "url"))
                vod_list = self._parse_items(items)
                if vod_list:
                    return {"list": vod_list, "page": pg}
            except Exception:
                continue
        return {"list": [], "page": pg}

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "url": "", "header": self._play_header()}
        if not id:
            return result

        if id.startswith("http") and (".m3u8" in id or ".mp4" in id):
            result["url"] = id
            return result

        # 兜底：尝试按播放页取
        urls = [id]
        if re.fullmatch(r"\d+", str(id)):
            urls += [
                f"{self.host}/drama/play/{id}/",
                f"{self.host}/drama/detail/{id}/",
            ]
        for u in urls:
            try:
                data, html, _ = self._page_and_payload(u)
                medias = self._collect_media(data, html)
                if medias:
                    result["url"] = medias[0]
                    return result
            except Exception:
                continue

        # 交给内置解析
        result["parse"] = 1
        result["url"] = id
        return result


if __name__ == "__main__":
    s = Spider()
    print("HOME:", json.dumps(s.homeContent(False), ensure_ascii=False))
    cat = s.categoryContent("drama", 1, False, {})
    print("CAT count:", len(cat["list"]), "pagecount:", cat["pagecount"], "total:", cat["total"])
    if cat["list"]:
        print("FIRST:", json.dumps(cat["list"][0], ensure_ascii=False))
        vid = cat["list"][0]["vod_id"]
        d = s.detailContent([vid])
        print("DETAIL name:", d["list"][0]["vod_name"])
        print("PLAY_FROM:", d["list"][0]["vod_play_from"])
        print("PLAY_URL:", d["list"][0]["vod_play_url"][:500])