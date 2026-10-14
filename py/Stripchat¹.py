# coding: utf-8
# Stripchat 直播 T3 爬虫  —  成人直播平台（doppiocdn / Mouflon v2 加密）
# 换站/维护只改：HOST_API / REF / KEY_MAP / self.classes
import re
import json
import base64
import hashlib
from urllib.parse import quote, unquote, urljoin, parse_qs

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    # ================= 站点信息 =================
    HOST_API = "https://zh.stripchat.com/api/front/models"
    REF = "https://zh.stripchat.com/"
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    X_DEVICE_INFO = '{"t":"webMobile","v":"1.0","ui":24631221}'
    LIMIT = 40

    # Mouflon v2：pkey -> key_v2（已实机验证 11 组）
    KEY_MAP = {
        "1Dzcc6OjP73LKbtI": "Y64UVwX5RrIWnOLp", "7uUnbD0jMCB9GH32": "lzCQ6QBTnLpB0zMF",
        "Fq6m2TO2ZeBkRPm9": "xb6di1NF9EFXHUwb", "GrRncsoByZmsiT6L": "NigHYyOD9l4rvAEb",
        "N2oLovTIXb0o28Uj": "ABE7Sj8jh3oPM2ae", "NTK9aqcLmNFMWrpQ": "tOcYOap4Ty1l9Jzb",
        "OLzu7QlySkG2fVRn": "CsovScFH9VirSJ4Z", "Ohi7eTRBpkAuML0l": "kExe29N2sLFrHGqu",
        "Ook7quaiNgiyuhai": "EQueeGh2kaewa3ch", "Zokee2OhPh9kugh4": "Quean4cai9boJa5a",
        "Zeechoej4aleeshi": "ubahjae7goPoodi6",
    }

    # ================= init =================
    def __init__(self):
        self.host = self.HOST_API
        self.headers = {
            "User-Agent": self.UA,
            "x-device-info": self.X_DEVICE_INFO,
            "Referer": self.REF,
        }
        # 静态分类（法则16）：type_id = primaryTag
        self.classes = [
            {"type_id": "girls", "type_name": "女生"},
            {"type_id": "couples", "type_name": "情侣"},
            {"type_id": "trans", "type_name": "跨性别"},
            {"type_id": "men", "type_name": "男生"},
        ]
        # 每类共用 filters
        # ethnicity/age/hairColor/bodyType/autoTag：服务端 filterGroupTags 过滤，
        #   value 为「组名 + 首字母大写值」的驼峰 slug（如 ethnicityAsian），已实测有效。
        # country：服务端无过滤参数，改客户端过滤（model.country ISO 两码小写）。
        common = [
            {"key": "ethnicity", "name": "人种", "value": [
                {"n": "全部", "v": ""}, {"n": "亚洲", "v": "ethnicityAsian"},
                {"n": "黑人", "v": "ethnicityEbony"}, {"n": "拉丁", "v": "ethnicityLatino"},
                {"n": "白人", "v": "ethnicityWhite"}, {"n": "印度", "v": "ethnicityIndian"},
                {"n": "中东", "v": "ethnicityMiddleEastern"}]},
            {"key": "age", "name": "年龄", "value": [
                {"n": "全部", "v": ""}, {"n": "熟女", "v": "ageMilf"},
                {"n": "成熟", "v": "ageMature"}, {"n": "年长", "v": "ageOld"}]},
            {"key": "hairColor", "name": "发色", "value": [
                {"n": "全部", "v": ""}, {"n": "金发", "v": "hairColorBlonde"},
                {"n": "黑发", "v": "hairColorBlack"}, {"n": "彩色", "v": "hairColorColorful"}]},
            {"key": "bodyType", "name": "体型", "value": [
                {"n": "全部", "v": ""}, {"n": "娇小", "v": "bodyTypePetite"},
                {"n": "丰满", "v": "bodyTypeCurvy"}, {"n": "中等", "v": "bodyTypeMedium"},
                {"n": "运动", "v": "bodyTypeAthletic"}, {"n": "大码", "v": "bodyTypeBig"}]},
            {"key": "autoTag", "name": "特色", "value": [
                {"n": "全部", "v": ""}, {"n": "高清", "v": "autoTagHd"},
                {"n": "新人", "v": "autoTagNew"}, {"n": "Lovense", "v": "autoTagLovense"},
                {"n": "VR", "v": "autoTagVr"}]},
            {"key": "country", "name": "国别", "value": [
                {"n": "全部", "v": ""}, {"n": "中国", "v": "cn"},
                {"n": "台湾", "v": "tw"}, {"n": "香港", "v": "hk"},
                {"n": "日本", "v": "jp"}, {"n": "韩国", "v": "kr"},
                {"n": "越南", "v": "vn"}, {"n": "泰国", "v": "th"},
                {"n": "菲律宾", "v": "ph"}, {"n": "印度", "v": "in"},
                {"n": "美国", "v": "us"}, {"n": "英国", "v": "gb"},
                {"n": "加拿大", "v": "ca"}, {"n": "俄罗斯", "v": "ru"},
                {"n": "哥伦比亚", "v": "co"}, {"n": "委内瑞拉", "v": "ve"},
                {"n": "意大利", "v": "it"}, {"n": "西班牙", "v": "es"},
                {"n": "法国", "v": "fr"}, {"n": "德国", "v": "de"}]},
        ]
        self.filters = {c["type_id"]: common for c in self.classes}
        # 服务端 tag 过滤的 key（extend 消费时按此顺序取 tag，送 filterGroupTags）
        self._filter_keys = ["ethnicity", "age", "hairColor", "bodyType", "autoTag"]
        # 客户端过滤的 key（服务端无对应参数）
        self._client_key = "country"

    # ================= 基础 =================
    def getName(self):
        return "Stripchat"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return (".m3u8" in u) or u.endswith(".mp4") or "/proxy?" in u

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ================= 网络工具 =================
    def _get(self, url, referer=None):
        """统一 GET，返回文本；走 self.fetch（法则4）。"""
        try:
            h = dict(self.headers)
            if referer:
                h["Referer"] = referer
            res = self.fetch(url, headers=h)
            if not res:
                return ""
            txt = getattr(res, "text", None)
            if txt is None and getattr(res, "content", None):
                txt = res.content.decode("utf-8", errors="ignore")
            return txt or ""
        except Exception as e:
            self.log("fetch fail: " + str(e))
            return ""

    def _api(self, primary_tag, offset, tags=None, query=None, limit=None):
        """请求列表 API，返回解析后的 dict（失败回 {}）。"""
        lim = int(limit) if limit else self.LIMIT
        url = "%s?primaryTag=%s&limit=%d&offset=%d" % (
            self.HOST_API, quote(primary_tag), lim, int(offset))
        if tags:
            groups = [[t] for t in tags if t]
            if groups:
                url += "&filterGroupTags=" + quote(json.dumps(groups), safe="")
        if query:
            url += "&query=" + quote(query)
        txt = self._get(url)
        if not txt:
            return {}
        try:
            return json.loads(txt)
        except Exception:
            return {}

    # ================= 打包 / 归一化 =================
    @staticmethod
    def _b64u_enc(s):
        return base64.urlsafe_b64encode(s.encode("utf-8")).decode("ascii").rstrip("=")

    @staticmethod
    def _b64u_dec(s):
        s = s + "=" * ((4 - len(s) % 4) % 4)
        try:
            return base64.urlsafe_b64decode(s.encode("ascii")).decode("utf-8", "replace")
        except Exception:
            return ""

    def _auto_master(self, model):
        """由 model 卡片得到 _auto master URL。"""
        hls = model.get("hlsPlaylist") or ""
        if hls:
            return re.sub(r"_\d+p(_blurred)?\.m3u8", "_auto.m3u8", hls)
        mid = model.get("id")
        if mid:
            return "https://edge-hls.doppiocdn.media/hls/%s/master/%s_auto.m3u8" % (mid, mid)
        return ""

    def _pack(self, model):
        """把播放所需信息打包进 vod_id（分隔 |$|），详情零网络直出。
        末段为 base64url(auto master url)，避免裸 $。"""
        mid = str(model.get("id") or "")
        name = model.get("username") or model.get("streamName") or mid
        pic = (model.get("previewUrlThumbSmall") or model.get("avatarUrl") or "")
        country = model.get("country") or ""
        viewers = model.get("viewersCount")
        remark_bits = []
        if model.get("isLive"):
            remark_bits.append("● LIVE")
        if isinstance(viewers, int):
            remark_bits.append("%d 人观看" % viewers)
        if country:
            remark_bits.append(country)
        remark = " · ".join(remark_bits) if remark_bits else ""
        auto = self._auto_master(model)
        return "%s|$|%s|$|%s|$|%s|$|%s" % (mid, name, pic, remark, self._b64u_enc(auto))

    def _cards(self, models):
        out = []
        seen = set()
        for m in models or []:
            if not (m.get("isLive") and m.get("status") == "public"):
                continue
            mid = str(m.get("id") or "")
            if not mid or mid in seen:
                continue
            seen.add(mid)
            packed = self._pack(m)
            name = m.get("username") or m.get("streamName") or mid
            pic = (m.get("previewUrlThumbSmall") or m.get("avatarUrl") or "")
            viewers = m.get("viewersCount")
            remark = ("%d 人观看" % viewers) if isinstance(viewers, int) else "LIVE"
            out.append({
                "vod_id": packed,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return out

    @staticmethod
    def _norm_ids(ids):
        # 法则35：ids 归一化
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    # ================= 首页 / 分类 =================
    def homeContent(self, filter):
        return {
            "class": self.classes,
            "filters": self.filters if filter else {},
        }

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        d = self._api("girls", 0)
        return {"list": self._cards(d.get("models"))}

    def _extend_tags(self, extend):
        """从 extend 提取选中的服务端 tag slug 列表（不含 country）。"""
        tags = []
        if isinstance(extend, dict):
            for k in self._filter_keys:
                v = extend.get(k)
                if v:
                    tags.append(v)
        return tags

    def _extend_country(self, extend):
        """从 extend 提取国别 code（ISO 两码小写），无则空。"""
        if isinstance(extend, dict):
            v = extend.get(self._client_key)
            if v:
                return str(v).strip().lower()
        return ""

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        tags = self._extend_tags(extend)
        country = self._extend_country(extend)
        primary = tid or "girls"

        # 国别：服务端无过滤参数，改客户端过滤（扫描多批 + 本地分页）
        if country:
            return self._category_by_country(primary, page, tags, country)

        offset = (page - 1) * self.LIMIT
        d = self._api(primary, offset, tags=tags)
        cards = self._cards(d.get("models"))

        # total：有 tag 过滤取 filteredCount，否则 totalCount
        if tags:
            total = d.get("filteredCount") or d.get("totalCount") or 0
        else:
            total = d.get("totalCount") or d.get("filteredCount") or 0
        try:
            total = int(total)
        except Exception:
            total = 0
        if total > 0:
            pagecount = (total + self.LIMIT - 1) // self.LIMIT
        else:
            pagecount = page + (1 if cards else 0)
        if pagecount < page:
            pagecount = page
        if pagecount > 500:
            pagecount = 500
        return {
            "list": cards,
            "page": page,
            "pagecount": pagecount,
            "limit": self.LIMIT,
            "total": total or pagecount * self.LIMIT,
        }

    def _category_by_country(self, primary, page, tags, country):
        """国别客户端过滤：以 90/批扫描服务端列表，按 model.country 命中后本地分页。"""
        DISPLAY = self.LIMIT           # 展示每页数（40）
        BATCH = 90                     # 服务端单请求上限
        MAX_SCAN = 720                 # 最多扫描的 model 数（8 批）
        need = page * DISPLAY          # 填满到请求页所需命中数
        collected = []
        seen = set()
        off = 0
        exhausted = False
        while len(collected) < need + DISPLAY and off < MAX_SCAN:
            d = self._api(primary, off, tags=tags, limit=BATCH)
            models = d.get("models") or []
            if not models:
                exhausted = True
                break
            for m in models:
                if not (m.get("isLive") and m.get("status") == "public"):
                    continue
                if (m.get("country") or "").lower() != country:
                    continue
                mid = str(m.get("id") or "")
                if not mid or mid in seen:
                    continue
                seen.add(mid)
                collected.append(m)
            off += BATCH
            if len(models) < BATCH:
                exhausted = True
                break

        start = (page - 1) * DISPLAY
        end = start + DISPLAY
        page_models = collected[start:end]
        cards = self._cards(page_models)

        # 分页：本轮扫描已尽 → pagecount 依已收集数；否则可能还有更多 → page+1
        if exhausted:
            total = len(collected)
            pagecount = (total + DISPLAY - 1) // DISPLAY if total else page
        else:
            total = len(collected)
            pagecount = page + 1 if len(collected) > end else page
        if pagecount < page:
            pagecount = page
        return {
            "list": cards,
            "page": page,
            "pagecount": pagecount,
            "limit": DISPLAY,
            "total": total or pagecount * DISPLAY,
        }

    # ================= 详情 =================
    def _skeleton(self, raw, name="", pic=""):
        return {"list": [{
            "vod_id": raw, "vod_name": name or "直播间", "vod_pic": pic or "",
            "vod_remarks": "LIVE", "vod_content": "",
            "vod_play_from": "Stripchat直播", "vod_play_url": "直播$" + raw,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        try:
            ps = raw.split("|$|")
            mid = ps[0] if ps else ""
            name = ps[1] if len(ps) > 1 else ""
            pic = ps[2] if len(ps) > 2 else ""
            remark = ps[3] if len(ps) > 3 else ""
            auto_b64 = ps[4] if len(ps) > 4 else ""
            auto = self._b64u_dec(auto_b64) if auto_b64 else ""
            # 缺 master 时由 model id 兜底重建
            if not auto and mid:
                auto = "https://edge-hls.doppiocdn.media/hls/%s/master/%s_auto.m3u8" % (mid, mid)
            play_id = self._b64u_enc(auto) if auto else ""
            # 带上 username（无裸 $，用 | 分隔第二段），供 playerContent 探测失败时打开直播间
            if play_id and name:
                play_id += "|" + self._b64u_enc(name)
            if not play_id:
                return self._skeleton(raw, name, pic)
            vod = {
                "vod_id": raw,
                "vod_name": name or "直播间",
                "vod_pic": pic,
                "vod_remarks": remark or "LIVE",
                "vod_content": "Stripchat 直播 · " + (name or ""),
                "vod_play_from": "Stripchat直播",
                # 单集：名称$播放ID，ID 为 base64url(master url)（法则21，内无裸 $）
                "vod_play_url": "直播$" + play_id,
            }
            return {"list": [vod]}
        except Exception as e:
            self.log("detail exception: " + str(e))
            return self._skeleton(raw)

    # ================= 搜索（无搜索 API，客户端 username 过滤） =================
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page > 1:
            return {"list": [], "page": page}
        kw = (key or "").strip().lower()
        if not kw:
            return {"list": [], "page": page}
        out = []
        seen = set()
        for primary in ("girls", "trans", "couples", "men"):
            d = self._api(primary, 0)
            for m in d.get("models") or []:
                if not (m.get("isLive") and m.get("status") == "public"):
                    continue
                mid = str(m.get("id") or "")
                if not mid or mid in seen:
                    continue
                uname = (m.get("username") or m.get("streamName") or "").lower()
                if kw in uname:
                    seen.add(mid)
                    packed = self._pack(m)
                    name = m.get("username") or m.get("streamName") or mid
                    pic = (m.get("previewUrlThumbSmall") or m.get("avatarUrl") or "")
                    out.append({
                        "vod_id": packed, "vod_name": name,
                        "vod_pic": pic, "vod_remarks": "LIVE",
                    })
        return {"list": out, "page": page}

    # ================= Mouflon v2 解密 =================
    @staticmethod
    def _dec_v2(token, key_v2):
        """token[::-1] -> base64 -> XOR sha256(key_v2) -> utf-8"""
        rt = token[::-1]
        rt += "=" * ((4 - len(rt) % 4) % 4)
        raw = base64.b64decode(rt)
        kh = hashlib.sha256(key_v2.encode()).digest()
        return bytearray(b ^ kh[i % 32] for i, b in enumerate(raw)).decode("utf-8", "replace")

    def _decode_seg(self, enc_url, key_v2):
        """解密 MOUFLON:URI 里的中段 token，替换回原 URL。"""
        m = re.search(r'_([A-Za-z0-9+/=\-]{10,})', enc_url)
        if not m:
            return enc_url
        tok = m.group(1)
        try:
            dec = self._dec_v2(tok, key_v2)
        except Exception:
            return enc_url
        if not dec:
            return enc_url
        return enc_url.replace(tok, dec)

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
        m = re.search(r'URI="([^"]*)"', line)
        if not m or not m.group(1):
            return line
        absu = self._resolve_url(m.group(1), base_url)
        return line[:m.start(1)] + absu + line[m.end(1):]

    # ================= 代理地址 =================
    def _proxy(self, target, ptype, pkey=""):
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
        u = base + sep + "url=" + quote(target, safe="") + "&type=" + ptype
        if pkey:
            u += "&pkey=" + quote(pkey, safe="")
        return u

    # ================= 播放 =================
    def _room_url(self, user):
        if user:
            return self.REF.rstrip("/") + "/" + str(user).lstrip("/")
        return self.REF

    def _web_header(self):
        return {"User-Agent": self.UA, "Referer": self.REF}

    def _probe_stream(self, auto):
        """实时探测流状态：ok(可免费播) / paid(付费或私密秀) / off(未开播/离线)。
        - master 无 #EXTM3U（多为 404）→ off
        - master 有，但 variant 取不到内容（免费流被 403 锁）→ paid
        - variant 拿到 #EXTM3U → ok
        """
        mt = self._get(auto, referer=self.REF)
        if not mt or "#EXTM3U" not in mt:
            return "off"
        pkeys = re.findall(r"#EXT-X-MOUFLON:PSCH:v2:([^\s,]+)", mt)
        pkey = next((p for p in pkeys if p in self.KEY_MAP), None)
        vurl = ""
        for line in mt.split("\n"):
            s = line.strip()
            if s.startswith("http"):
                vurl = s
                break
        if not vurl:
            return "unknown"
        vabs = self._resolve_url(vurl, auto)
        if "psch=" not in vabs:
            sep = "&" if "?" in vabs else "?"
            vabs += sep + "psch=v2" + (("&pkey=" + pkey) if pkey else "")
        # 重试一次，规避 CDN 偶发空响应导致误判 paid
        for _ in range(2):
            vt = self._get(vabs, referer=self.REF)
            if vt and "#EXTM3U" in vt:
                return "ok"
        return "paid"

    def playerContent(self, flag, id, vipFlags):
        pid = self._norm_ids(id)
        if "$" in pid:
            pid = pid.split("$")[-1]

        # pid 形如 b64(auto)|b64(username)；兼容纯 http、纯数字 model id、单段 b64
        user = ""
        parts = pid.split("|")
        head = parts[0] if parts else pid
        if len(parts) > 1 and parts[1]:
            user = self._b64u_dec(parts[1])

        auto = ""
        if head.startswith("http"):
            auto = head
        elif re.fullmatch(r"\d+", head or ""):
            auto = "https://edge-hls.doppiocdn.media/hls/%s/master/%s_auto.m3u8" % (head, head)
        else:
            dec = self._b64u_dec(head)
            if dec.startswith("http"):
                auto = dec

        if not auto:
            return {"parse": 1, "url": self._room_url(user), "header": self._web_header(),
                    "jx": 0, "msg": "无法解析直播地址，已为你打开直播间"}

        # 实时探测：区分「可免费观看 / 付费秀 / 未开播」
        status = self._probe_stream(auto)
        if status == "ok":
            proxied = self._proxy(auto, "master")
            return {
                "parse": 0,
                "url": proxied,
                "header": {"User-Agent": self.UA, "Referer": self.REF},
            }

        if status == "paid":
            msg = "主播正在开付费/私密秀，无法免费观看，已为你打开直播间"
        else:  # off / unknown
            msg = "主播当前未开播或已离线，已为你打开直播间"
        return {"parse": 1, "url": self._room_url(user), "header": self._web_header(),
                "jx": 0, "msg": msg}

    # ================= 本地代理 =================
    def localProxy(self, param):
        try:
            url = ""
            ptype = "master"
            pkey = ""
            if isinstance(param, dict):
                url = param.get("url") or ""
                ptype = param.get("type") or "master"
                pkey = param.get("pkey") or ""
                # 部分实现把 value 包成 list
                if isinstance(url, (list, tuple)) and url:
                    url = url[0]
                if isinstance(ptype, (list, tuple)) and ptype:
                    ptype = ptype[0]
                if isinstance(pkey, (list, tuple)) and pkey:
                    pkey = pkey[0]
            else:
                url = str(param or "")
            if url and "%" in url:
                try:
                    url = unquote(url)
                except Exception:
                    pass
            if not url:
                return [404, "text/plain", b""]

            if ptype == "master":
                return self._proxy_master(url)
            return self._proxy_variant(url, pkey)
        except Exception as e:
            self.log("localProxy fail: " + str(e))
            return [404, "text/plain", b""]

    def _proxy_master(self, master_url):
        """抓 master：挑已知 pkey + 保留 preset variant，重写为代理 variant 地址。"""
        text = self._get(master_url, referer=self.REF)
        if not text or "#EXTM3U" not in text:
            return [404, "text/plain", b""]

        pkeys = re.findall(r"#EXT-X-MOUFLON:PSCH:v2:([^\s,]+)", text)
        pkey = next((p for p in pkeys if p in self.KEY_MAP), None)

        lines = text.split("\n")
        # 收集 (inf_line, variant_url)
        variants = []
        header_lines = []
        i = 0
        n = len(lines)
        while i < n:
            s = lines[i].rstrip()
            if s.startswith("#EXT-X-STREAM-INF"):
                vurl = ""
                j = i + 1
                while j < n:
                    t = lines[j].strip()
                    if t and not t.startswith("#"):
                        vurl = t
                        break
                    j += 1
                if vurl:
                    variants.append((s, vurl))
                i = j + 1
                continue
            if s.startswith("#EXT-X-MOUFLON"):
                i += 1
                continue
            if s.startswith("#"):
                header_lines.append(s)
            i += 1

        # 优先 preset（_480p 等，非 blurred）；无则退回全部
        presets = [(inf, u) for inf, u in variants
                   if re.search(r"_\d+p\.m3u8", u) and "blurred" not in u.lower()]
        pool = presets if presets else variants
        if not pool:
            return [404, "text/plain", b""]

        out = ["#EXTM3U"]
        for h in header_lines:
            if h.startswith("#EXTM3U"):
                continue
            out.append(h)
        for inf, vurl in pool:
            vabs = self._resolve_url(vurl, master_url)
            sep = "&" if "?" in vabs else "?"
            vq = vabs
            if "psch=" not in vabs:
                vq = vabs + sep + "psch=v2"
                if pkey:
                    vq += "&pkey=" + pkey
            proxied = self._proxy(vq, "variant", pkey or "")
            out.append(inf)
            out.append(proxied)
        return [200, "application/vnd.apple.mpegurl", ("\n".join(out) + "\n").encode("utf-8")]

    def _proxy_variant(self, variant_url, pkey):
        """抓 variant：逐段解密 MOUFLON:URI，替换占位分片行为解密后的绝对地址。"""
        text = self._get(variant_url, referer=self.REF)
        if not text or "#EXTM3U" not in text:
            return [404, "text/plain", b""]

        key_v2 = self.KEY_MAP.get(pkey or "")
        # variant 内也可能带 PSCH，pkey 缺失时自愈
        if not key_v2:
            mp = re.search(r"#EXT-X-MOUFLON:PSCH:v2:([^\s,]+)", text)
            if mp and mp.group(1) in self.KEY_MAP:
                key_v2 = self.KEY_MAP[mp.group(1)]

        out = []
        pending = None
        for raw in text.split("\n"):
            s = raw.rstrip()
            if s == "":
                continue
            if s.startswith("#EXT-X-MOUFLON:URI:"):
                enc = s.split(":", 2)[2] if s.count(":") >= 2 else ""
                if enc and key_v2:
                    pending = self._decode_seg(enc, key_v2)
                elif enc:
                    pending = self._resolve_url(enc, variant_url)
                continue
            if s.startswith("#EXT-X-MOUFLON"):
                # 其它 mouflon 标签（PSCH 等）丢弃，播放器不识别
                continue
            if s.startswith("#EXT-X-MAP") or s.startswith("#EXT-X-KEY"):
                out.append(self._abs_tag_uri(s, variant_url))
                continue
            if s.startswith("#"):
                out.append(s)
                continue
            # 非注释行 = 分片 URL（多为占位 media.mp4）
            if pending:
                out.append(pending)
                pending = None
            else:
                out.append(self._resolve_url(s, variant_url))
        return [200, "application/vnd.apple.mpegurl", ("\n".join(out) + "\n").encode("utf-8")]
