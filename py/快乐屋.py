# coding: utf-8
# ============================================================
# 站点信息
#   名称: 快乐屋
#   主域名: https://ztmczm.kuailewuo.cc
#   备用域名: 通过 /api/public/domains 动态获取
#   发布页: 无
#   内容类型: 成人视频（video）
#   架构: Nuxt SPA + REST API（响应 AES-128-CBC 加密）
#   加密: AES-128-CBC  key=a9yX32LpQvUt7wBc  iv=N7cPk2Bv38hWqFzM  Base64密文
#   接口:
#     GET /api/categories/video            分类列表
#     GET /api/videos?page=1&ps=24&order=created_at&category_id=X   分类列表
#     GET /api/videos?kw=关键词&page=1&ps=24                         搜索
#     GET /api/movie?id=X                  详情（含 play_url 直链）
#     GET /api/top/fetch?limit=N           置顶/推荐
#   m3u8: 详情接口直接返回直链；含跨目录广告分片（suspicious_ad_dirs），
#         锚点目录随视频变化 -> 采用动态锚点（m3u8 URL 目录）
#   最后验证: 2026-09-12
#   来源: 用户指定站点
# ============================================================
import json
import base64
import re
from urllib.parse import quote, urljoin, unquote, urlparse

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except ImportError:
    AES = None

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    # 取证结论：suspicious_ad_dirs 非空 -> 需要清洗
    NEED_CLEAN = True

    def __init__(self):
        self.host = "https://ztmczm.kuailewuo.cc"
        self.extend = ""
        self.aes_key = b"a9yX32LpQvUt7wBc"
        self.aes_iv = b"N7cPk2Bv38hWqFzM"
        self.api = self.host + "/api"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "application/json, text/plain, */*",
        }
        # 分类静态硬编码（零网络依赖）
        self.classes = [
            {"type_id": "2664", "type_name": "日本精品"},
            {"type_id": "2663", "type_name": "日韩无码"},
            {"type_id": "2662", "type_name": "日韩超清"},
            {"type_id": "2661", "type_name": "异族风情"},
            {"type_id": "2660", "type_name": "女优明星"},
            {"type_id": "2659", "type_name": "SM调教"},
            {"type_id": "2658", "type_name": "中文字幕"},
            {"type_id": "2657", "type_name": "成人动漫"},
            {"type_id": "2656", "type_name": "欧美性爱"},
            {"type_id": "2655", "type_name": "精品推荐"},
            {"type_id": "2654", "type_name": "国产色情"},
            {"type_id": "2653", "type_name": "国产超清"},
            {"type_id": "2652", "type_name": "国产自拍"},
            {"type_id": "2651", "type_name": "探花约炮"},
            {"type_id": "2650", "type_name": "丝袜制服"},
            {"type_id": "2649", "type_name": "强奸迷奸"},
            {"type_id": "2648", "type_name": "国内换脸"},
            {"type_id": "2647", "type_name": "多人群交"},
            {"type_id": "2646", "type_name": "反差母狗"},
            {"type_id": "2645", "type_name": "野战车震"},
            {"type_id": "2644", "type_name": "会所技师"},
            {"type_id": "2643", "type_name": "校园春色"},
            {"type_id": "2642", "type_name": "淫妻绿帽"},
            {"type_id": "2641", "type_name": "乱伦毁三观"},
            {"type_id": "2640", "type_name": "网曝黑料"},
            {"type_id": "2639", "type_name": "主播网红"},
            {"type_id": "2638", "type_name": "传媒精品"},
            {"type_id": "2637", "type_name": "麻豆视频"},
            {"type_id": "2636", "type_name": "91制片厂"},
            {"type_id": "2635", "type_name": "天美传媒"},
            {"type_id": "2634", "type_name": "蜜桃传媒"},
            {"type_id": "2633", "type_name": "皇家华人"},
            {"type_id": "2632", "type_name": "星空传媒"},
            {"type_id": "2631", "type_name": "焦点影业"},
            {"type_id": "2630", "type_name": "海角社区"},
            {"type_id": "2629", "type_name": "成人头条"},
            {"type_id": "2628", "type_name": "乌鸦传媒"},
            {"type_id": "2627", "type_name": "兔子先生"},
            {"type_id": "2626", "type_name": "杏吧原创"},
            {"type_id": "2625", "type_name": "玩偶姐姐"},
            {"type_id": "2624", "type_name": "MINI传媒"},
            {"type_id": "2623", "type_name": "大象传媒"},
            {"type_id": "2622", "type_name": "开心鬼传媒"},
            {"type_id": "2621", "type_name": "糖心vlog"},
            {"type_id": "2620", "type_name": "萝莉社"},
            {"type_id": "2619", "type_name": "性视界"},
        ]
        # 排序筛选
        order_opts = [
            {"n": "最新", "v": "created_at"},
            {"n": "最热", "v": "hits"},
        ]
        self.filters = {}
        for c in self.classes:
            self.filters[c["type_id"]] = [
                {"key": "order", "name": "排序", "value": order_opts}
            ]

    def getName(self):
        return "快乐屋"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ---------- 解密 ----------
    def _decrypt(self, b64_text):
        try:
            raw = base64.b64decode(b64_text)
            pt = unpad(AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv).decrypt(raw), 16)
            return json.loads(pt.decode("utf-8", errors="ignore"))
        except Exception as e:
            self.log({"action": "decrypt_fail", "error": str(e)})
            return {}

    def _api_get(self, path):
        """请求 API 并解密，返回 data（业务层统一处理）。"""
        url = self.api + path
        try:
            r = self.fetch(url, headers=self.headers, timeout=15)
        except Exception as e:
            self.log({"api": "exception", "path": path, "error": str(e)})
            return {}
        if not r or r.status_code != 200:
            self.log({"api": "bad_status", "path": path,
                      "status": r.status_code if r else None})
            return {}
        try:
            j = json.loads(r.text)
        except Exception:
            return {}
        if "cipher" in j:
            d = self._decrypt(j["cipher"])
        else:
            d = j
        # 统一剥离 code/data
        if isinstance(d, dict) and d.get("code", 0) == 0 and "data" in d:
            return d.get("data") or {}
        return d if isinstance(d, dict) else {}

    # ---------- 列表解析 ----------
    def _parse_list(self, items):
        out = []
        for it in items or []:
            vid = it.get("id")
            title = it.get("title")
            if not vid or not title:
                continue
            pic = it.get("cover_url") or ""
            hits = it.get("hits") or 0
            cat = it.get("category") or ""
            remark = f"{cat} · {hits}次" if cat else f"{hits}次"
            out.append({
                "vod_id": str(vid),
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return out

    # ---------- 首页 ----------
    def homeContent(self, filter):
        if filter:
            return {"class": self.classes, "filters": self.filters}
        return {"class": self.classes}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 首页推荐：最新视频
        d = self._api_get("/videos?page=1&ps=24&order=created_at")
        return {"list": self._parse_list(d.get("list", []))}

    # ---------- 分类 ----------
    @staticmethod
    def _parse_extend(extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except Exception:
                pass
            res = {}
            for part in extend.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    res[k.strip()] = v.strip()
            return res
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        ext = self._parse_extend(extend)
        order = ext.get("order") or "created_at"
        path = f"/videos?page={page}&ps=24&order={order}&category_id={tid}"
        d = self._api_get(path)
        lst = self._parse_list(d.get("list", []))
        total = int(d.get("total") or 0)
        pages = int(d.get("pages") or 1)
        return {
            "list": lst,
            "page": int(page),
            "pagecount": pages,
            "limit": 24,
            "total": total,
        }

    # ---------- 详情 ----------
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

    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
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
            return {"list": []}
        try:
            d = self._api_get("/movie?id=" + quote(raw))
            info = (d or {}).get("info") or {}
            if not info:
                return self._skeleton(raw)
            title = info.get("title") or ""
            pic = info.get("cover_url") or ""
            play_url = info.get("play_url") or ""
            cat = info.get("category") or ""
            hits = info.get("hits") or 0
            remark = f"{cat} · {hits}次" if cat else f"{hits}次"
            if not play_url:
                return self._skeleton(raw, title, pic, remark)
            vod = {
                "vod_id": raw,
                "vod_name": title,
                "vod_pic": pic,
                "vod_type": cat,
                "vod_remarks": remark,
                "vod_content": title,
                "vod_play_from": "快乐屋",
                "vod_play_url": "播放$" + play_url,
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"detail": "exception", "ids": raw, "error": str(e)})
            return self._skeleton(raw)

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        page = str(pg or "1")
        path = f"/videos?kw={quote(key)}&page={page}&ps=24"
        d = self._api_get(path)
        return {"list": self._parse_list(d.get("list", [])), "page": int(page)}

    # ---------- 推荐 ----------
    def recommendContent(self, ids=None, pg="1"):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        try:
            d = self._api_get("/movie?id=" + quote(raw))
            related = (d or {}).get("related") or []
            return {"list": self._parse_list(related)}
        except Exception:
            return {"list": []}
    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id) if id else ""
        # id 可能是 "名称$地址" 格式
        if "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]
        if play_url and not play_url.startswith("http"):
            play_url = "https://" + play_url.lstrip("/")
        if not play_url:
            return {"parse": 0, "url": "", "header": {}}

        ua = self.headers.get("User-Agent", "")
        if ".m3u8" in play_url:
            if self.NEED_CLEAN:
                return {"parse": 0, "url": self._m3u8_proxy_url(play_url),
                        "header": {"User-Agent": ua}}
            return {"parse": 0, "url": play_url, "header": {"User-Agent": ua}}
        return {"parse": 0, "url": play_url, "header": {"User-Agent": ua}}

    # ---------- m3u8 广告过滤（动态锚点） ----------
    @staticmethod
    def _is_fake_image_stream(text, source_url):
        IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
        VIDEO_EXT = (".ts", ".m4s", ".mp4", ".aac", ".m4a")
        has_video = False
        has_image = False
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            path = line.split("?")[0].split("#")[0].lower()
            if path.endswith(VIDEO_EXT):
                has_video = True
            elif path.endswith(IMAGE_EXT):
                has_image = True
        return has_image and not has_video

    @staticmethod
    def _rewrite_m3u8_tag(line, source_url):
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

    def _resolve_main_dir(self, lines, source_url, is_image_stream=False):
        """动态锚点：本站在 m3u8 同目录下挂正片分片，广告在另一目录。
        锚点目录随视频变化，因此必须从 source_url 动态推导（anchor_source=m3u8_url）。"""
        import posixpath
        base_dir = posixpath.dirname(urlparse(source_url).path)
        if not base_dir.endswith("/"):
            base_dir += "/"
        if is_image_stream:
            counter = {}
            for line in lines:
                if not line or line.startswith("#"):
                    continue
                p = urlparse(urljoin(source_url, line)).path
                d = posixpath.dirname(p)
                if d and d != "/":
                    counter[d + "/"] = counter.get(d + "/", 0) + 1
            if counter:
                return max(counter.items(), key=lambda kv: kv[1])[0]
            return base_dir
        # 普通流：KEY URI 目录优先
        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            key_path = urlparse(
                key_uri if key_uri.startswith("http")
                else urljoin(source_url, key_uri)
            ).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return base_dir

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 第1层：图片流检测 —— 只打标记，不 return
        is_img = self._is_fake_image_stream(text, source_url)
        if is_img:
            self.log({"stage": "clean", "fake_image_stream": True,
                      "action": "keep_suffix_as_is"})

        # 第2层：多码率主表
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                    continue
                child = urljoin(source_url, line)
                if ".m3u8" in child.lower():
                    out.append(self._m3u8_proxy_url(child))
                else:
                    out.append(child)
            return "\n".join(out) + "\n"

        # 第3层：正片目录锚点（动态）
        main_dir = self._resolve_main_dir(lines, source_url, is_image_stream=is_img)

        # 第4层：分片过滤
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
                media = urljoin(source_url, line)
                media_path = urlparse(media).path
                if media_path.startswith(main_dir):
                    segments.extend(pending)
                    segments.append(self._rewrite_m3u8_tag(media, source_url))
                    kept += 1
                else:
                    removed += 1
                pending = []
                continue
            segments.append(self._rewrite_m3u8_tag(line, source_url))

        # 第5层：全滤兜底
        if removed > 0 and (kept == 0 or removed > kept):
            self.log({"stage": "clean", "fallback": "no_filter",
                      "removed": removed, "kept": kept, "anchor": main_dir})
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log({"stage": "clean", "removed": removed,
                      "kept": kept, "anchor": main_dir})

        # 第5层：冗余标签清理
        NOISE = ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE")
        out = []
        for line in segments:
            if line in NOISE:
                if not out or out[-1] in NOISE:
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in NOISE:
            out.pop()
        return "\n".join(out) + "\n"

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                qs = urlparse(target).query
                from urllib.parse import parse_qs
                q = parse_qs(qs)
                if "url" in q:
                    target = q["url"][0]
            target = unquote(str(target or ""))
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp or resp.status_code != 200:
                return [502, "text/plain", b"fetch failed"]
            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]

            if b"#EXTM3U" in content[:512]:
                cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            return [200, "application/octet-stream", content]
        except Exception as e:
            return [500, "text/plain", ("localProxy error: " + str(e)).encode("utf-8", errors="ignore")]