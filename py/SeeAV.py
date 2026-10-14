# coding=utf-8
# !/usr/bin/python
"""
FongMi / TVBox T3 (type=3) 爬虫源
站点：SeeAV  https://seeav.com/
类型：日本/亚洲 AV 影片站（成人）—— Nuxt SPA + 全加密 JSON API + HLS(m3u8) 直链
说明（逆向要点，换站需重做全部加密）：
  - 全站数据走 /api/* POST，Body 为加密文本(text/plain)：
      Base64(iv(16) + AES-CBC/Pkcs7( gzip( JSON ) ))
      金钥 = HMAC-SHA256(message=hex(requestId 去横线), key="nq4f5vzbwse1k3ry") -> 32B
      明文结构 = {"data": params, "token": token, "deviceId": deviceId}
                 （login/device 另在顶层平铺 share_code / channel_code）
    响应同样是上述加密格式，用同一 requestId 的金钥解密后 JSON.parse。
  - 必带头：Content-Type=text/plain, deviceType=web, version=1.0.0,
            time=Date.now()前11位, requestId=uuidv4, language=zh
            + 设备头 Sid/Device/Device-Id/Device-Fingerprint/Fp-Version/Sdk-Version
  - 匿名登入：POST /api/login/device (顶层加 share_code/channel_code) -> token,user_id
             组合 token = f"{token}_{user_id}"，后续所有请求带此 token。
  - 列表/分类/搜索统一端点：POST /api/search/movie
       参数 {page, keyword?, tag_id?}；空参=最新全部；tag_id 过滤分类/片商/标签。
       回 {data:{data:[卡片...], current_page, last_page}}
  - 标签字典：POST /api/search/movieTags {tag_id:1} -> [{id,name}...]（内容标签全集）
  - 详情：POST /api/movie/detail {id:<hash>} -> {name,number,img,description,duration,
           actors,tags,publisher,play_links[{name,m3v_url,m3c_url,code}],recommend_items}
  - 播放：详情 play_links[].m3v_url（相对 m3v/xxx.m3u8?time&expired&rand&uid&sign，
           有效期约 3h）。m3u8 内 AES-128 KEY 与 .ts 分片均为「绝对且自带签名」的
           CDN 直链(cdn-yh.jymmehp.info / cdn-test2.irxjfs.cn)，仅需 UA 即可拉取，
           无 IP/Referer 绑定 -> 直接 parse:0 交播放器，无需本地代理。
  - 封面图 cdn.g3ejjm8m.com 为明文 JPEG，仅需 UA -> 直接用，无需解密/代理。
最后验证：2026-09-30
"""
import sys
import json
import time
import uuid
import gzip
import hmac
import hashlib
import base64
import os
import re
from urllib.parse import quote

sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        def init(self, extend=""):
            pass

try:
    from Crypto.Cipher import AES as _AES
except Exception:
    _AES = None


class Spider(Spider):
    # ============ 站点信息（换站只改这里 + 上方 crypto 说明）============
    siteName = "SeeAV"
    HOST = "https://seeav.com"
    CK = b"nq4f5vzbwse1k3ry"          # 客户端加密主金钥
    UA = ("Mozilla/5.0 (Linux; Android 14; 22127RK46C/Pixel5) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
    LIMIT = 30

    # ---------- 生命周期 ----------
    def init(self, extend=""):
        self.extend = extend or ""
        self._token = ""
        # 设备信息（每会话随机一次，缓存复用；零网络）
        self._dev = {
            "sid": self._hx(16),
            "device": "Android",
            "device_id": self._hx(16),
            "device_fingerprint": self._hx(32),
            "fp_version": "3.0.0",
            "sdk_version": "1.1.8",
        }
        return

    def getName(self):
        return self.siteName

    def isVideoFormat(self, url):
        u = url or ""
        return any(x in u for x in (".m3u8", ".mp4", ".ts", ".flv", ".mkv", "/m3v/", "/m3c/"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    def getDependence(self):
        return []

    # ================= 加密内核 =================
    @staticmethod
    def _hx(n):
        return os.urandom(n).hex()

    def _gen_key(self, rid):
        msg = bytes.fromhex(rid.replace("-", ""))
        return hmac.new(self.CK, msg, hashlib.sha256).digest()

    @staticmethod
    def _pad(b):
        p = 16 - (len(b) % 16)
        return b + bytes([p]) * p

    @staticmethod
    def _unpad(b):
        return b[:-b[-1]] if b else b

    def _encrypt(self, obj, rid):
        key = self._gen_key(rid)
        raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        raw = gzip.compress(raw)
        iv = os.urandom(16)
        ct = _AES.new(key, _AES.MODE_CBC, iv).encrypt(self._pad(raw))
        return base64.b64encode(iv + ct).decode()

    def _decrypt(self, b64, rid):
        key = self._gen_key(rid)
        blob = base64.b64decode(b64)
        pt = self._unpad(_AES.new(key, _AES.MODE_CBC, blob[:16]).decrypt(blob[16:]))
        try:
            pt = gzip.decompress(pt)
        except Exception:
            pass
        return json.loads(pt.decode("utf-8", "ignore"))

    def _api(self, endpoint, params, extra_top=None, need_login=True):
        """加密 POST 单一端点，回解密后的 dict；失败回 {}。"""
        if _AES is None:
            return {}
        if need_login and not self._token:
            self._login()
        rid = str(uuid.uuid4())
        t = str(int(time.time() * 1000))[:11]
        payload = {"data": params, "token": self._token, "deviceId": self._dev["device_id"]}
        if extra_top:
            payload.update(extra_top)
        try:
            body = self._encrypt(payload, rid)
        except Exception:
            return {}
        h = {
            "Content-Type": "text/plain", "deviceType": "web", "version": "1.0.0",
            "time": t, "requestId": rid, "language": "zh", "User-Agent": self.UA,
            "Origin": self.HOST, "Referer": self.HOST + "/", "Accept": "application/json",
            "Sid": self._dev["sid"], "Device": self._dev["device"],
            "Device-Id": self._dev["device_id"], "Device-Fingerprint": self._dev["device_fingerprint"],
            "Fp-Version": self._dev["fp_version"], "Sdk-Version": self._dev["sdk_version"],
        }
        try:
            r = self.post(self.HOST + endpoint, data=body, headers=h)
        except Exception:
            return {}
        if not r:
            return {}
        txt = getattr(r, "text", "") or ""
        if not txt:
            return {}
        try:
            return self._decrypt(txt, rid)
        except Exception:
            return {}

    def _login(self):
        d = self._api("/api/login/device", {},
                      extra_top={"share_code": "", "channel_code": ""}, need_login=False)
        data = d.get("data") if isinstance(d, dict) else None
        if isinstance(data, dict):
            tk = data.get("token") or ""
            uid = data.get("user_id") or data.get("userId") or ""
            if tk and uid:
                self._token = "%s_%s" % (tk, uid)
        return self._token

    # ================= 列表卡片 =================
    def _card(self, it):
        vid = it.get("id")
        if not vid:
            return None
        name = it.get("name") or it.get("number") or str(vid)
        remarks = []
        num = it.get("number")
        if num:
            remarks.append(str(num))
        dur = it.get("duration")
        if dur:
            remarks.append(str(dur))
        if it.get("pay_type") == "vip":
            remarks.append("VIP")
        return {
            "vod_id": str(vid),
            "vod_name": name,
            "vod_pic": it.get("img") or "",
            "vod_remarks": " | ".join(remarks),
        }

    def _cards(self, arr):
        out, seen = [], set()
        for it in (arr or []):
            c = self._card(it)
            if not c or c["vod_id"] in seen:
                continue
            seen.add(c["vod_id"])
            out.append(c)
        return out

    def _search_page(self, page, tag_id="", keyword=""):
        params = {"page": int(page)}
        if keyword:
            params["keyword"] = str(keyword)[:500]
        if tag_id:
            try:
                params["tag_id"] = int(tag_id)
            except Exception:
                params["tag_id"] = tag_id
        d = self._api("/api/search/movie", params)
        data = d.get("data") if isinstance(d, dict) else None
        if not isinstance(data, dict):
            return [], 1
        lst = self._cards(data.get("data"))
        try:
            pc = int(data.get("last_page") or 1)
        except Exception:
            pc = 1
        return lst, max(pc, 1)

    # ================= 首页分类（静态硬编码，零网络，法则16）=================
    # type_id 约定：""=最新全部；"tag@@<tag_id>"=按 tag_id 过滤。
    # tag_id 命名空间实测：小 id=片商/系列，大 id=内容标签（均可用于 search/movie）。
    _CLASSES = [
        ("最新", ""),
        ("无码", "tag@@625"),
        ("中出内射", "tag@@682"),
        ("素人", "tag@@691"),
        ("人妻", "tag@@554"),
        ("巨乳", "tag@@563"),
        ("熟女", "tag@@670"),
        ("学生", "tag@@517"),
        ("SM调教", "tag@@556"),
        ("JK制服", "tag@@532"),
        ("Cosplay", "tag@@535"),
        ("卡里比", "tag@@2"),
        ("一本道", "tag@@5"),
        ("Paco", "tag@@3"),
        ("SIRO", "tag@@4"),
        ("LUXU", "tag@@17"),
    ]
    # 类型筛选下拉（value=tag_id；选中则覆盖分类的 tag_id）
    _TAG_FILTER = [
        ("全部", ""), ("素人", "691"), ("无码", "625"), ("中出内射", "682"),
        ("巨乳", "563"), ("人妻", "554"), ("熟女", "670"), ("少女", "645"),
        ("学生", "517"), ("口交", "634"), ("自拍", "669"), ("颜射", "578"),
        ("SM调教", "556"), ("制服", "525"), ("JK", "532"), ("Cosplay", "535"),
        ("痴女", "676"), ("OL", "604"), ("辣妹", "693"), ("清纯", "637"),
        ("丝袜", "651"), ("足交", "529"), ("潮吹放尿", "582"), ("肛交", "580"),
        ("3P", "581"), ("寝取NTR", "679"),
    ]

    def homeContent(self, filter):
        classes = [{"type_name": n, "type_id": t} for (n, t) in self._CLASSES]
        values = [{"n": n, "v": v} for (n, v) in self._TAG_FILTER]
        flt = {c["type_id"]: [{"key": "tag", "name": "类型", "value": values}]
               for c in classes}
        return {"class": classes, "filters": flt}

    def homeVideoContent(self):
        lst, _ = self._search_page(1)
        return {"list": lst}

    # ================= 分类 =================
    def _parse_extend(self, extend):
        if isinstance(extend, dict):
            return extend
        if not extend:
            return {}
        s = str(extend).strip()
        if s.startswith("{"):
            try:
                return json.loads(s)
            except Exception:
                s = s.strip("{}")
        out = {}
        for pair in re.split(r'[&,;]', s):
            if "=" in pair:
                k, _, v = pair.partition("=")
                k = k.strip().strip('"').strip("'")
                v = v.strip().strip('"').strip("'")
                if k:
                    out[k] = v
        return out

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        tid = str(tid or "")
        ext = self._parse_extend(extend)

        # 类型筛选下拉优先覆盖
        tag_id = ext.get("tag") or ""
        if not tag_id and tid.startswith("tag@@"):
            tag_id = tid.split("@@", 1)[1]

        lst, pc = self._search_page(page, tag_id=tag_id)
        return {
            "list": lst,
            "page": page,
            "pagecount": pc,
            "limit": len(lst) or self.LIMIT,
            "total": pc * (len(lst) or self.LIMIT),
        }

    # ================= 详情 =================
    def _norm_ids(self, ids):
        if isinstance(ids, (list, tuple)):
            ids = ids[0] if ids else ""
        return str(ids or "").strip()

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}
        d = self._api("/api/movie/detail", {"id": vid})
        info = d.get("data") if isinstance(d, dict) else None
        if not isinstance(info, dict):
            # 兜底骨架，避免回空 list（法则35）
            return {"list": [{"vod_id": vid, "vod_name": vid,
                              "vod_play_from": "线路1", "vod_play_url": "线路1$" + vid}]}

        name = info.get("name") or info.get("number") or vid
        # 演员
        actors = info.get("actors") or []
        actor_names = []
        for a in actors:
            if isinstance(a, dict):
                nm = a.get("name") or a.get("nickname")
                if nm:
                    actor_names.append(str(nm))
            elif a:
                actor_names.append(str(a))
        # 标签
        tags = info.get("tags") or []
        tag_names = []
        for tg in tags:
            if isinstance(tg, dict):
                nm = tg.get("name")
                if nm:
                    tag_names.append(str(nm))
            elif tg:
                tag_names.append(str(tg))
        publisher = info.get("publisher")
        if isinstance(publisher, dict):
            publisher = publisher.get("name") or ""

        remarks = []
        if info.get("number"):
            remarks.append(str(info["number"]))
        if info.get("duration"):
            remarks.append(str(info["duration"]))
        if info.get("pay_type") == "vip":
            remarks.append("VIP")
        if info.get("score"):
            remarks.append("评分" + str(info["score"]))

        # 播放线路：play_links[].m3v_url（相对，含签名，有效期约 3h）
        froms, urls = [], []
        for i, pl in enumerate(info.get("play_links") or []):
            if not isinstance(pl, dict):
                continue
            m3v = pl.get("m3v_url") or pl.get("m3c_url") or ""
            if not m3v:
                continue
            line_name = (pl.get("name") or ("线路%d" % (i + 1))).strip() or ("线路%d" % (i + 1))
            token = base64.b64encode(m3v.encode()).decode()  # 避免裸 $（法则21）
            froms.append(line_name)
            urls.append("%s$%s" % (line_name, token))
        if not froms:
            # 无 play_links：交给 playerContent 用 id 现取（movie/play）
            froms = ["线路1"]
            urls = ["线路1$id::%s" % vid]

        vod = {
            "vod_id": str(info.get("id") or vid),
            "vod_name": name,
            "vod_pic": info.get("img") or "",
            "vod_remarks": " | ".join(remarks),
            "vod_year": str(info.get("issue_date") or "")[:10],
            "vod_area": "日本",
            "vod_actor": ", ".join(actor_names),
            "vod_director": publisher or "",
            "vod_content": (info.get("description") or "").strip(),
            "type_name": ", ".join(tag_names),
            "vod_play_from": "$$$".join(froms),
            "vod_play_url": "$$$".join(urls),
        }
        return {"list": [vod]}

    # ================= 搜索 =================
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg)
        except Exception:
            page = 1
        lst, _ = self._search_page(page, keyword=key)
        return {"list": lst, "page": page}

    # ================= 播放 =================
    def playerContent(self, flag, id, vipFlags):
        pid = self._norm_ids(id)
        url = ""
        if pid.startswith("id::"):
            # 用 movie 视频 hash 现取新鲜签名直链
            vid = pid[4:]
            d = self._api("/api/movie/play", {"id": vid})
            data = d.get("data") if isinstance(d, dict) else None
            rel = ""
            if isinstance(data, dict):
                rel = data.get("m3v_url") or data.get("m3c_url") or ""
            url = self._abs(rel)
        else:
            # base64(相对 m3v_url)
            try:
                rel = base64.b64decode(pid).decode("utf-8", "ignore")
            except Exception:
                rel = pid
            url = self._abs(rel)

        if not url:
            return {"parse": 0, "url": "", "header": {}}
        header = {"User-Agent": self.UA, "Referer": self.HOST + "/", "Origin": self.HOST}
        # HLS 内 KEY/分片均为绝对签名直链，仅需 UA -> 直接直链播放
        return {"parse": 0, "url": url, "header": header}

    def _abs(self, rel):
        if not rel:
            return ""
        if rel.startswith("http"):
            return rel
        return self.HOST + "/" + rel.lstrip("/")

    # ================= 推荐 =================
    def recommendContent(self, ids=None, pg="1"):
        lst, _ = self._search_page(1)
        return {"list": lst}

    # ================= 本地代理（不需要）=================
    def localProxy(self, param):
        return [404, "text/plain", {}]
