# coding: utf-8
# ============================================================
# 站点: 极品鲍AV（名站导航）
# 主域名: https://yobigj.jinpinbaoz.top/
# 内容类型: 视频（m3u8 直链，图片流伪装分片 + 开头广告段）
# 架构: Nuxt3 SPA + 全 API 响应 AES-128-CBC 加密
# 解密: AES-128-CBC / Pkcs7 / Key=a9yX32LpQvUt7wBc / IV=N7cPk2Bv38hWqFzM
# 接口: /api/categories/video, /api/videos, /api/movie
# m3u8: 图片流伪装(.jpg) + 开头广告段(/mov/AD/ 独立目录)，走 localProxy 过滤
# 最后验证: 2026-09-12
# ============================================================
import json
import base64
import re
from urllib.parse import quote, urljoin, unquote, urlparse

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except ImportError:
    pass

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://yobigj.jinpinbaoz.top"
        self.aes_key = b"a9yX32LpQvUt7wBc"
        self.aes_iv = b"N7cPk2Bv38hWqFzM"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "application/json, text/plain, */*",
        }
        self.classes = [
            {"type_id": "2701", "type_name": "日韩精品"},
            {"type_id": "2700", "type_name": "日韩无码"},
            {"type_id": "2699", "type_name": "自拍偷拍"},
            {"type_id": "2698", "type_name": "探花约炮"},
            {"type_id": "2697", "type_name": "丝袜制服"},
            {"type_id": "2696", "type_name": "国内换脸"},
            {"type_id": "2695", "type_name": "反差母狗"},
            {"type_id": "2694", "type_name": "野战车震"},
            {"type_id": "2693", "type_name": "会所技师"},
            {"type_id": "2692", "type_name": "学生嫩穴"},
            {"type_id": "2691", "type_name": "淫妻绿帽"},
            {"type_id": "2690", "type_name": "原创乱伦"},
            {"type_id": "2689", "type_name": "网曝黑料"},
            {"type_id": "2688", "type_name": "主播网红"},
            {"type_id": "2687", "type_name": "传媒精品"},
            {"type_id": "2686", "type_name": "麻豆视频"},
            {"type_id": "2685", "type_name": "91制片厂"},
            {"type_id": "2684", "type_name": "天美传媒"},
            {"type_id": "2683", "type_name": "蜜桃传媒"},
            {"type_id": "2682", "type_name": "皇家华人"},
            {"type_id": "2681", "type_name": "星空传媒"},
            {"type_id": "2680", "type_name": "焦点影业"},
            {"type_id": "2679", "type_name": "海角社区"},
            {"type_id": "2678", "type_name": "成人头条"},
            {"type_id": "2677", "type_name": "乌鸦传媒"},
            {"type_id": "2676", "type_name": "兔子先生"},
            {"type_id": "2675", "type_name": "杏吧原创"},
            {"type_id": "2673", "type_name": "MINI传媒"},
            {"type_id": "2672", "type_name": "香蕉传媒"},
            {"type_id": "2671", "type_name": "开心鬼传媒"},
            {"type_id": "2670", "type_name": "糖心vlog"},
            {"type_id": "2669", "type_name": "萝莉社"},
            {"type_id": "2668", "type_name": "性视界"},
        ]
        self.filters = {}

    def getName(self):
        return "极品鲍AV"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def _decrypt(self, b64):
        try:
            ct = base64.b64decode(b64)
            pt = unpad(AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv).decrypt(ct), 16)
            return json.loads(pt.decode("utf-8", errors="ignore"))
        except Exception as e:
            self.log({"action": "decrypt_fail", "error": type(e).__name__})
            return {}

    def _get(self, path):
        url = self.host + path
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            self.log({"fetch_fail": url, "status": r.status_code if r else None})
            return {}
        try:
            j = json.loads(r.text)
        except Exception:
            return {}
        if "cipher" in j:
            return self._decrypt(j["cipher"])
        return j

    def _parse_list(self, items):
        out = []
        for it in items or []:
            vid = it.get("id")
            title = it.get("title")
            if not vid or not title:
                continue
            out.append({
                "vod_id": str(vid),
                "vod_name": title,
                "vod_pic": it.get("cover_url") or it.get("pic") or "",
                "vod_remarks": it.get("category") or "",
            })
        return out

    def homeVideoContent(self):
        res = self._get("/api/videos?page=1&ps=20&order=created_at")
        data = res.get("data", {}) or {}
        return {"list": self._parse_list(data.get("list", []))}

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
            d = {}
            for part in extend.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    d[k.strip()] = v.strip()
            return d
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        res = self._get(f"/api/videos?category_id={tid}&page={page}&ps=22")
        data = res.get("data", {}) or {}
        return {
            "list": self._parse_list(data.get("list", [])),
            "page": int(data.get("page", page)),
            "pagecount": int(data.get("pages", 1)),
            "limit": int(data.get("ps", 22)),
            "total": int(data.get("total", 0)),
        }

    def searchContent(self, key, quick, pg="1"):
        page = str(pg or "1")
        kw = quote(str(key or ""), safe="")
        res = self._get(f"/api/videos?kw={kw}&page={page}&ps=22")
        data = res.get("data", {}) or {}
        return {
            "list": self._parse_list(data.get("list", [])),
            "page": int(data.get("page", page)),
        }

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
        pid = str(vid).split("|$|")[0].replace("$", "|")
        return {"list": [{
            "vod_id": vid, "vod_name": title or "未知标题", "vod_pic": pic or "",
            "vod_remarks": remarks, "vod_content": "",
            "vod_play_from": "播放", "vod_play_url": "播放$" + pid,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        try:
            res = self._get(f"/api/movie?id={raw}")
            info = (res.get("data", {}) or {}).get("info", {}) or {}
            if not info:
                return self._skeleton(raw)
            play_url = str(info.get("play_url") or "").strip()
            if not play_url:
                return self._skeleton(raw, info.get("title"), info.get("cover_url"), info.get("category"))
            vod = {
                "vod_id": raw,
                "vod_name": info.get("title") or "视频",
                "vod_pic": info.get("cover_url") or "",
                "vod_remarks": info.get("category") or "",
                "vod_content": info.get("title") or "",
                "vod_play_from": "播放",
                "vod_play_url": "播放$" + play_url,
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"detail": "exception", "error": type(e).__name__})
            return self._skeleton(raw)

    def _proxy_url(self, url):
        base = self.getProxyUrl()
        sep = "&" if "?" in base else "?"
        return base + sep + "url=" + quote(str(url or ""), safe="")

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id or "")
        if "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]
        if play_url and not play_url.startswith("http"):
            play_url = "https://" + play_url.lstrip("/")
        if not play_url:
            return {"parse": 1, "url": self.host + "/", "header": self.headers}
        if play_url.endswith(".m3u8"):
            # m3u8 有开头广告段 + 图片流伪装，走 localProxy 过滤
            return {"parse": 0, "url": self._proxy_url(play_url), "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
            }}
        return {"parse": 0, "url": play_url, "header": {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.host + "/",
        }}

    def localProxy(self, param):
        """m3u8 本地代理：图片流后缀原样透传 + 开头广告段按锚点过滤"""
        target = unquote(str((param or {}).get("url", "") or ""))
        if not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", "invalid url"]
        try:
            r = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", ""),
                                            "Referer": self.host + "/"}, timeout=15)
            if not r or r.status_code != 200:
                return [502, "text/plain", "m3u8 fetch failed"]
            text = r.text
            if "#EXTM3U" not in text:
                return [502, "text/plain", "invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log({"localProxy": "error", "error": type(e).__name__})
            return [500, "text/plain", "proxy error"]

    def _clean_m3u8(self, text, source_url):
        """图片流伪装 + 开头广告段过滤。
        锚点：分片路径众数目录（法则33 图片流锚点策略），最稳。
        图片流分片后缀原样透传，只补绝对地址，禁止 replace。
        """
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 多码率主表：子流走代理
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for l in lines:
                if l.startswith("#"):
                    out.append(l)
                else:
                    child = urljoin(source_url, l)
                    out.append(self._proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        # 收集所有分片的目录，取众数作为正片锚点
        seg_dirs = {}
        for l in lines:
            if l and not l.startswith("#"):
                d = urlparse(urljoin(source_url, l)).path.rsplit("/", 1)[0] + "/"
                seg_dirs[d] = seg_dirs.get(d, 0) + 1
        if seg_dirs:
            anchor = max(seg_dirs.items(), key=lambda kv: kv[1])[0]
        else:
            anchor = source_url.rsplit("/", 1)[0] + "/"

        # 第一遍：按锚点丢弃跨目录广告分片
        out = []
        pending = []
        removed = 0
        kept = 0
        for l in lines:
            if l.startswith("#EXTINF"):
                pending = [l]; continue
            if pending and l.startswith("#"):
                pending.append(l); continue
            if pending:
                media = urljoin(source_url, l)
                if anchor not in urlparse(media).path:
                    removed += 1
                else:
                    out.extend(pending); out.append(media); kept += 1
                pending = []
                continue
            out.append(self._rewrite_tag(l, source_url))

        # 全滤兜底：误杀过半则整体回退（只补绝对地址，不过滤）
        if removed > 0 and (kept == 0 or removed > kept):
            self.log({"m3u8": "fallback_all", "kept": kept, "removed": removed, "anchor": anchor})
            out2 = []
            for l in lines:
                out2.append(self._rewrite_tag(l, source_url))
            return "\n".join(out2) + "\n"

        # 第二遍：清理孤儿 KEY（后面不紧跟 EXTINF）与重复 DISCONTINUITY
        final = []
        for i, l in enumerate(out):
            if l.startswith("#EXT-X-KEY"):
                nxt = out[i+1] if i+1 < len(out) else ""
                if not nxt.startswith("#EXTINF"):
                    continue
                final.append(l)
            elif l == "#EXT-X-DISCONTINUITY":
                if final and final[-1] == "#EXT-X-DISCONTINUITY":
                    continue
                final.append(l)
            else:
                final.append(l)

        while final and (final[-1].startswith("#EXT-X-KEY") or final[-1] == "#EXT-X-DISCONTINUITY"):
            final.pop()

        self.log({"m3u8": "cleaned", "kept": kept, "removed": removed, "anchor": anchor})
        return "\n".join(final) + "\n"

    def _rewrite_tag(self, line, source_url):
        """补全 KEY/MAP URI 与分片绝对地址；图片流后缀原样透传"""
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(m):
                return 'URI="' + urljoin(source_url, m.group(1)) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            return urljoin(source_url, line)
        return line

    def recommendContent(self, ids, pg):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        try:
            res = self._get(f"/api/movie?id={raw}")
            data = res.get("data", {}) or {}
            rel = data.get("related") or []
            lst = self._parse_list(rel)
            if not lst:
                for k in ("prev", "next"):
                    it = data.get(k) or {}
                    if it.get("id") and it.get("title"):
                        lst.append({
                            "vod_id": str(it.get("id")),
                            "vod_name": it.get("title"),
                            "vod_pic": it.get("cover_url") or "",
                            "vod_remarks": it.get("category") or "",
                        })
            return {"list": lst}
        except Exception:
            return {"list": []}

    def destroy(self):
        pass