# coding: utf-8
# 乱伦天堂 (luanluntt) T3 爬虫 —— 成人站，Nuxt.js(Vue) SPA + AES 加密 JSON API
# 站点信息（换站只改 HOST / API_KEY / API_IV 与 self.classes）
import json
import base64
import re
from urllib.parse import quote, unquote, urljoin

from base.spider import Spider as BaseSpider

try:
    from Crypto.Cipher import AES  # pycryptodome
    from Crypto.Util.Padding import unpad
    _CRYPTO_OK = True
except Exception:
    _CRYPTO_OK = False


class Spider(BaseSpider):

    # ================= 站点信息 =================
    HOST = "https://asxosd.luanlun.cyou"
    # API 响应 AES-128-CBC 解密参数（entry.js: vu/mu 常量）
    API_KEY = b"a9yX32LpQvUt7wBc"
    API_IV = b"N7cPk2Bv38hWqFzM"

    def __init__(self):
        # 法则16/17：__init__ 零网络，分类静态硬编码
        self.host = self.HOST
        self.api = self.HOST + "/api"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Accept": "application/json",
            "Referer": self.HOST + "/",
            "Origin": self.HOST,
        }
        # 静态分类（只取 module=video 的分类，type_id = category_id）
        self.classes = [
            {"type_id": "664", "type_name": "国产乱伦"},
            {"type_id": "662", "type_name": "精品推荐"},
            {"type_id": "667", "type_name": "网曝事件"},
            {"type_id": "686", "type_name": "强奸乱伦"},
            {"type_id": "663", "type_name": "国产主播"},
            {"type_id": "665", "type_name": "自拍偷拍"},
            {"type_id": "668", "type_name": "传媒探花"},
            {"type_id": "671", "type_name": "淫妻作乐"},
            {"type_id": "670", "type_name": "AV解说"},
            {"type_id": "681", "type_name": "人妻熟女"},
            {"type_id": "680", "type_name": "中文字幕"},
            {"type_id": "682", "type_name": "无码流出"},
            {"type_id": "687", "type_name": "韩国三级"},
            {"type_id": "688", "type_name": "欧美激情"},
            {"type_id": "669", "type_name": "清纯学生"},
            {"type_id": "672", "type_name": "港台辣妹"},
            {"type_id": "673", "type_name": "足浴撩妹"},
            {"type_id": "674", "type_name": "反差母狗"},
            {"type_id": "675", "type_name": "AI换脸"},
            {"type_id": "676", "type_name": "VR视角"},
            {"type_id": "677", "type_name": "重口性癖"},
            {"type_id": "678", "type_name": "制服诱惑"},
            {"type_id": "679", "type_name": "丝袜美腿"},
            {"type_id": "666", "type_name": "制服丝袜"},
            {"type_id": "683", "type_name": "多人群交"},
            {"type_id": "684", "type_name": "凌辱快感"},
            {"type_id": "685", "type_name": "角色剧情"},
            {"type_id": "689", "type_name": "主奴调教"},
            {"type_id": "690", "type_name": "动漫卡通"},
            {"type_id": "691", "type_name": "变性伪娘"},
            {"type_id": "692", "type_name": "女同性恋"},
            {"type_id": "693", "type_name": "野外露出"},
        ]
        self.filters = {}

    # ================= 基础 =================
    def getName(self):
        return "乱伦天堂"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 法则17：init 零网络
        self.extend = extend or ""

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return (".m3u8" in u) or u.endswith(".mp4")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ================= API 工具 =================
    def _dec(self, cipher):
        """AES-128-CBC + PKCS7 解密 -> JSON 对象。"""
        if not _CRYPTO_OK:
            self.log("Crypto 不可用，无法解密 API 响应")
            return None
        try:
            raw = AES.new(self.API_KEY, AES.MODE_CBC, self.API_IV).decrypt(
                base64.b64decode(cipher))
            txt = unpad(raw, 16).decode("utf-8", errors="ignore")
            return json.loads(txt)
        except Exception as e:
            self.log("decrypt fail: " + str(e))
            return None

    def _api(self, path):
        """GET {api}{path}，解密后返回内层 data（对齐 entry.js: a.data ?? a）。"""
        try:
            full = self.api + path
            res = self.fetch(full, headers=self.headers)
            if not res:
                return None
            txt = getattr(res, "text", None)
            if txt is None and getattr(res, "content", None):
                txt = res.content.decode("utf-8", errors="ignore")
            txt = (txt or "").strip()
            if not txt:
                return None
            obj = json.loads(txt)
            if isinstance(obj, dict) and obj.get("cipher"):
                obj = self._dec(obj["cipher"])
                if obj is None:
                    return None
            if isinstance(obj, dict) and "data" in obj:
                return obj["data"]
            return obj
        except Exception as e:
            self.log("api fail: " + str(e))
            return None

    # ================= m3u8 去广告管线（法则26：仅代理 m3u8 文本，分片改绝对交播放器直连） =========
    def _get(self, url):
        """统一 GET 文本（供 localProxy 抓 m3u8）。"""
        try:
            full = url if url.startswith("http") else urljoin(self.host + "/", url.lstrip("/"))
            res = self.fetch(full, headers={"User-Agent": self.headers["User-Agent"]})
            if not res:
                return ""
            txt = getattr(res, "text", None)
            if txt is None and getattr(res, "content", None):
                txt = res.content.decode("utf-8", errors="ignore")
            return txt or ""
        except Exception as e:
            self.log("fetch fail: " + str(e))
            return ""

    def _proxy_url(self, target):
        """把真实 m3u8 地址包装成本地代理地址；取不到 getProxyUrl 时回退直链。"""
        if not target:
            return target
        base = ""
        try:
            base = self.getProxyUrl() or ""
        except Exception:
            base = ""
        if not base:
            return target
        if base.endswith("?") or base.endswith("&"):
            sep = ""
        elif "?" in base:
            sep = "&"
        else:
            sep = "?"
        return base + sep + "url=" + quote(target, safe="") + "&type=m3u8"

    @staticmethod
    def _resolve_url(uri, base_url):
        if not uri:
            return ""
        if uri.startswith("http"):
            return uri
        if uri.startswith("//"):
            return "https:" + uri
        try:
            return urljoin(base_url, uri)
        except Exception:
            return uri

    def _abs_tag_uri(self, line, base_url):
        """把 #EXT-X-KEY / #EXT-X-MAP 里的 URI="..." 改成绝对 CDN 地址。
        相对 key URI 不绝对化时播放器会按代理 base(127.0.0.1) 解析 → 取金钥 404 黑屏。"""
        m = re.search(r'URI="([^"]*)"', line)
        if not m or not m.group(1):
            return line
        absu = self._resolve_url(m.group(1), base_url)
        return line[:m.start(1)] + absu + line[m.end(1):]

    def _filter_m3u8(self, text, base_url, depth=0):
        if "#EXT-X-STREAM-INF" in text:
            return self._flatten_master(text, base_url, depth)
        return self._filter_media(text, base_url)

    def _flatten_master(self, text, base_url, depth=0):
        """主表拉平（single hop）：取首个子流绝对地址，抓该 media 清单过滤后回传。"""
        if depth >= 2:
            return text if text.endswith("\n") else text + "\n"
        sub = ""
        for raw in text.split("\n"):
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            sub = self._resolve_url(s, base_url)
            break
        if not sub:
            return text if text.endswith("\n") else text + "\n"
        media = self._get(sub)
        if not media or "#EXTM3U" not in media:
            return text if text.endswith("\n") else text + "\n"
        return self._filter_m3u8(media, sub, depth + 1)

    def _filter_media(self, text, base_url):
        """媒体清单去广告：
        锚点 = KEY URI 目录优先（正片 AES-128），无 KEY 回退 m3u8 URL 目录；
        只留锚点目录前缀分片（正片在 /videos/.../{code}/），广告前贴片(/stream/...)剔除；
        EXTINF/DISCONTINUITY/BYTERANGE 与分片成对丢弃，分片改绝对，KEY/MAP URI 绝对化；
        仅当 kept==0（正片一段不剩）才整体回退，避免误伤。"""
        lines = text.split("\n")
        base_dir = base_url.rsplit("/", 1)[0]
        anchor = ""
        for ln in lines:
            m = re.search(r'#EXT-X-KEY:[^\n]*URI="([^"]+)"', ln)
            if m:
                anchor = self._resolve_url(m.group(1), base_url).rsplit("/", 1)[0]
                break
        if not anchor:
            anchor = base_dir

        out = []
        buf = []
        removed = 0
        kept = 0
        kept_any = False
        for raw in lines:
            s = raw.strip()
            if not s:
                continue
            if s.startswith("#EXTINF") or s.startswith("#EXT-X-DISCONTINUITY") \
                    or s.startswith("#EXT-X-BYTERANGE") or s.startswith("#EXT-X-PROGRAM-DATE-TIME"):
                buf.append(s)
                continue
            if s.startswith("#"):
                if s.startswith("#EXT-X-KEY") or s.startswith("#EXT-X-MAP"):
                    s = self._abs_tag_uri(s, base_url)
                out.append(s)
                continue
            seg_abs = self._resolve_url(s, base_url)
            if seg_abs.startswith(anchor):
                for t in buf:
                    if (not kept_any) and t.startswith("#EXT-X-DISCONTINUITY"):
                        continue
                    out.append(t)
                out.append(seg_abs)
                kept += 1
                kept_any = True
            else:
                removed += 1
            buf = []

        if kept == 0 and removed > 0:
            return text if text.endswith("\n") else text + "\n"
        return "\n".join(out) + "\n"

    # ================= 卡片打包/解析 =================
    def _pack(self, vid, name, pic, remark):
        """列表阶段把字段打包进 vod_id，详情零网络直出（分隔符 |$|）。"""
        return "%s|$|%s|$|%s|$|%s" % (vid, name or "", pic or "", remark or "")

    def _cards(self, items):
        """API list -> vod list。"""
        out = []
        seen = set()
        for it in (items or []):
            if not isinstance(it, dict):
                continue
            vid = str(it.get("id") or "").strip()
            if not vid or vid in seen:
                continue
            seen.add(vid)
            title = re.sub(r"\s+", " ", str(it.get("title") or "").strip())
            pic = it.get("cover_url") or ""
            remark = it.get("category") or ""
            out.append({
                "vod_id": self._pack(vid, title, pic, remark),
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return out

    @staticmethod
    def _norm_ids(ids):
        # 法则35：ids 归一化，禁止裸 ids[0]
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    # ================= 首页/分类 =================
    def homeContent(self, filter):
        # 法则16：首页零网络
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 首页推荐用最新视频列表
        data = self._api("/videos?page=1")
        items = (data or {}).get("list") if isinstance(data, dict) else None
        return {"list": self._cards(items)}

    def categoryContent(self, tid, pg, filter, extend):
        page = 1
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        data = self._api("/videos?category_id=%s&page=%d" % (quote(str(tid)), page)) or {}
        items = data.get("list") if isinstance(data, dict) else None
        cards = self._cards(items)
        limit = 0
        pagecount = page
        total = 0
        if isinstance(data, dict):
            try:
                limit = int(data.get("ps") or 0)
            except Exception:
                limit = 0
            try:
                pagecount = int(data.get("pages") or page)
            except Exception:
                pagecount = page
            try:
                total = int(data.get("total") or 0)
            except Exception:
                total = 0
        if limit <= 0:
            limit = 20
        if pagecount < 1:
            pagecount = page if cards else page
        if total <= 0:
            total = pagecount * limit
        return {
            "list": cards,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": total,
        }

    # ================= 详情 =================
    def _skeleton(self, vid, title="", pic="", remark="解析中"):
        pid = str(vid).split("|$|")[0]
        return {"list": [{
            "vod_id": vid, "vod_name": title or "未知标题", "vod_pic": pic or "",
            "vod_remarks": remark, "vod_content": "",
            "vod_play_from": "正片", "vod_play_url": "正片$" + pid,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        try:
            ps = raw.split("|$|")
            vid = ps[0]
            name = ps[1] if len(ps) > 1 else ""
            pic = ps[2] if len(ps) > 2 else ""
            remark = ps[3] if len(ps) > 3 else ""
            content = ""
            # 缺标题/封面时补抓 /movie?id
            if (not name or not pic) and vid:
                data = self._api("/movie?id=%s" % quote(str(vid)))
                info = (data or {}).get("info") if isinstance(data, dict) else None
                if isinstance(info, dict):
                    if not name:
                        name = re.sub(r"\s+", " ", str(info.get("title") or "").strip())
                    if not pic:
                        pic = info.get("cover_url") or ""
                    if not remark:
                        remark = info.get("category") or ""
                    content = name
            if not vid:
                return self._skeleton(raw, name, pic)
            vod = {
                "vod_id": raw,
                "vod_name": name or "视频",
                "vod_pic": pic,
                "vod_remarks": remark,
                "vod_content": content or name or "",
                "vod_play_from": "正片",
                # 单集格式：名称$播放ID（纯数字视频 id）
                "vod_play_url": "正片$" + vid,
            }
            return {"list": [vod]}
        except Exception as e:
            self.log("detail exception: " + str(e))
            return self._skeleton(raw)

    # ================= 搜索 =================
    def searchContent(self, key, quick, pg="1"):
        page = 1
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        data = self._api("/videos?kw=%s&page=%d" % (quote(key), page)) or {}
        items = data.get("list") if isinstance(data, dict) else None
        return {"list": self._cards(items), "page": page}

    # ================= 播放 =================
    def playerContent(self, flag, id, vipFlags):
        pid = self._norm_ids(id)
        # 处理「名称$地址/ID」历史格式：取 $ 后段
        if "$" in pid:
            pid = pid.split("$")[-1]

        # 已是直链
        if pid.startswith("http") and (".m3u8" in pid.lower() or pid.lower().endswith(".mp4")):
            if ".m3u8" in pid.lower():
                return {"parse": 0, "url": self._proxy_url(pid),
                        "header": {"User-Agent": self.headers["User-Agent"]}}
            return {"parse": 0, "url": pid, "header": {"User-Agent": self.headers["User-Agent"]}}

        url = ""
        pfrom = ""
        # pid 为纯数字 -> /movie?id 取 play_url
        if re.fullmatch(r"\d+", pid or ""):
            data = self._api("/movie?id=%s" % pid)
            info = (data or {}).get("info") if isinstance(data, dict) else None
            if isinstance(info, dict):
                url = info.get("play_url") or ""
                pfrom = (info.get("play_from") or "").lower()

        if url:
            if url.startswith("//"):
                url = "https:" + url
            ua = self.headers["User-Agent"]
            # m3u8 走 localProxy 去广告（前贴片 /stream/ + 中插）；mp4 直链透传
            if ".m3u8" in url.lower() or pfrom == "m3u8":
                return {"parse": 0, "url": self._proxy_url(url),
                        "header": {"User-Agent": ua}}
            return {"parse": 0, "url": url, "header": {"User-Agent": ua}}

        # 兜底：交盒子解析
        return {"parse": 1, "url": pid, "header": self.headers}

    def localProxy(self, param):
        """代理并清洗 m3u8：过滤广告分片、KEY/分片改绝对地址，交播放器直连 CDN（法则26）。"""
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url") or param.get("u") or ""
            else:
                url = str(param or "")
            if not url:
                return [404, "text/plain", b""]
            if "%" in url:
                try:
                    url = unquote(url)
                except Exception:
                    pass
            text = self._get(url)
            if not text or "#EXTM3U" not in text:
                return [404, "text/plain", b""]
            cleaned = self._filter_m3u8(text, url)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception:
            return [404, "text/plain", b""]
