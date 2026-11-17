# -*- coding: utf-8 -*-
# =============================================================================
# 新云帧享（js.trgfd.cn）· TVBox / OK影视(FongMi) Python 站源
#
# 由《新云帧享dr3.js》原样迁移而来，接口、参数、加密、设备链全部一一对应：
#   首页   GET  /cache/channel/首页.json
#   分类   GET  /cache/zhaopian/{频道}/{类型}/{地区}/{年份}/{排序}/{页码}.json
#          少儿频道多两段：{频道}/{类型}/{地区}/{年份}/全部/全部/{排序}/{页码}.json
#   搜索   GET  /vc/api/search/{关键词}/{页码}.json        明文，单页 18 条
#   详情   GET  /cache/videos/{id//1000}/{id}.json?version=&baoming=&channel=fenxiang
#   播放   GET  /vc/api/video/playurl?sid=&ji=&jiIndex=&t=&y=&isjiid=&androidId=
#              &modelName=&newDeviceCode=&b=&version=&baoming=&channel=
#          header vuk = md5(sid + '8' + VUK_KEY)
#
# 加密：响应体是 AES-256-GCM 密文（Base64 → 前 12 字节 IV、末 16 字节 tag，
#       中间是密文）。GCM 的数据段就是 AES-CTR：计数块 = IV||0x00000002 起逐块 +1，
#       只解密不校验 tag。三条密钥逐条试解，解出首字符是 { 或 [ 即命中。
#       壳里若没有 pycryptodome/cryptography，自动回落到内置纯 Python AES-256。
#
# 设备链：不注册拿不到直链。
#   1. POST /vc/api/device/isnew  → data.b / uid / newDeviceCode（必须 POST）
#   2. POST /vc/api/getadjson + addadian×3 + tongjiguanggao×2 = 广告解锁
#   实测注册即可取直链，广告 5 个请求只在站点真拒播时才补跑一轮。
# =============================================================================
import base64
import hashlib
import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass

try:
    from Crypto.Cipher import AES as _CryptoAES
except Exception:
    _CryptoAES = None

try:
    from cryptography.hazmat.primitives.ciphers import Cipher as _CfCipher
except Exception:
    _CfCipher = None

HOST = "https://js.trgfd.cn"
BRAND = "新云帧享"
PKG = "com.baiyunvideo.app"
VER = "3.4.0"
CHANNEL = "fenxiang"
MODEL = "Redmi Note 12"
VUK_KEY = "uiju6talkolp98lll7VH7yuDxih7ujh"
VUK_MIDDLE = "8"

DATA_KEYS = [
    "JPT5fjptd0qi1TZZxu53cA7XI2TvQkol",
    "qvn1u7FCfu8uao9oi80i8uVHVS8Dxih7",
    "8uiju6talkolp98lll7VH7yuDxih7ujh",
]

UA = "okhttp/4.12.0"
BASE_HEADERS = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
JSON_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json; charset=utf-8",
}
PLAY_HEADERS = {"User-Agent": UA}   # 修复：去掉 Referer。站点大量片源分片托管在 B 站图床(i0.hdslb.com)，
# B 站按 Referer 白名单防盗链，带上 Referer: https://js.trgfd.cn/ 会让所有分片返回 403 → 无法播放。
# 去掉 Referer 后：m3u8/密钥/分片均 200，AES-128 解密得到合法 TS 流。

TIMEOUT = 9
PAGE_SIZE = 21

HOME_TTL = 90
LIST_TTL = 120
DETAIL_TTL = 300
PL_TTL = 1500

# 一级分类（顶栏 6 个，顺序即站点频道顺序）
CLASSES = [("剧集", "剧集"), ("电影", "电影"), ("综艺", "综艺"),
           ("动漫", "动漫"), ("少儿", "少儿"), ("纪录片", "纪录片")]

FILTER_RAW = {
    "剧集": {
        "cls": "全部,爱情,古装,战争,喜剧,家庭,犯罪,武侠,冒险,动作,恐怖,悬疑,奇幻,剧情,历史,同性,短片,其他",
        "region": "全部,大陆,香港,台湾,日本,韩国,美国,泰国,其他",
        "year": "全部,2026,2025,2024,2023,2022,2021,2020,2019,2018,2017,2016,2015-2011,2010-2000,更早",
    },
    "电影": {
        "cls": "全部,喜剧,动作,科幻,爱情,家庭,悬疑,奇幻,剧情,恐怖,犯罪,动画,惊悚,战争,同性,冒险,灾难,其他",
        "region": "全部,大陆,香港,台湾,美国,日本,韩国,印度,泰国,英国,法国,其他",
        "year": "全部,2026,2025,2024,2023,2022,2021,2020,2019,2018,2017,2016,2015-2011,2010-2000,90年代,80年代,更早",
    },
    "综艺": {
        "cls": "全部,真人秀,音乐,脱口秀",
        "region": "全部,大陆,香港,台湾,日本,韩国,美国,其他",
        "year": "全部,2026,2025,2024,2023,2022,2021,2020,2019,2018,2017,2016,2015,2014,2013,2012,2011,更早",
    },
    "动漫": {
        "cls": "全部,爱情,武侠,喜剧,科幻,奇幻,家庭,热血,冒险,动作,剧情,同性,悬疑,惊悚,运动,历史,战争,动画",
        "region": "全部,大陆,日本,美国,其他",
        "year": "全部,2026,2025,2024,2023,2022,2021,2020,2019,2018,2017,2016,2015,2014,2013,2012,2011,更早",
    },
    "少儿": {
        "cls": "全部,看动画,玩玩具,听儿歌,看绘本,涨知识,学英语,识字拼音,好习惯,国学,做手工,冒险救援,生活日常,搞笑,动物,公主",
        "region": "全部,大陆,日本,美国,其他",
        "year": "全部,2026,2025,2024,2023,2022,2021,2020,10年代,00年代",
    },
    "纪录片": {
        "cls": "全部,自然,美食,社会,人文,历史,军事,科技,财经,探险,罪案,竞技,旅游",
        "region": "全部,大陆,海外",
        "year": "全部,2026,2025,2024,2023,2022,2021,2020,更早",
    },
}

SORTS = [("最新", "最新"), ("最热", "最热"), ("评分", "评分")]


def _options(text):
    return [{"n": x, "v": x} for x in str(text or "").split(",") if x]


def _filters():
    out = {}
    for tid, _ in CLASSES:
        raw = FILTER_RAW.get(tid) or {}
        out[tid] = [
            {"key": "cls", "name": "类型", "value": _options(raw.get("cls"))},
            {"key": "region", "name": "地区", "value": _options(raw.get("region"))},
            {"key": "year", "name": "年份", "value": _options(raw.get("year"))},
            {"key": "sort", "name": "排序", "value": [{"n": a, "v": b} for a, b in SORTS]},
        ]
    return out


_FILTER = _filters()


# ============================ 纯 Python AES-256（兜底） ============================
def _sbox_gen():
    p = [0] * 256
    l = [0] * 256
    x = 1
    for i in range(255):
        p[i] = x
        l[x] = i
        x ^= (x << 1) ^ (0x11B if x & 0x80 else 0)
        x &= 0xFF
    box = [0] * 256
    for i in range(256):
        inv = p[(255 - l[i]) % 255] if i else 0

        def rot(v, n):
            return ((v << n) | (v >> (8 - n))) & 0xFF

        box[i] = (inv ^ rot(inv, 1) ^ rot(inv, 2) ^ rot(inv, 3) ^ rot(inv, 4) ^ 0x63) & 0xFF
    return box


_SBOX = _sbox_gen()


def _gmul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a = ((a << 1) ^ (0x1B if a & 0x80 else 0)) & 0xFF
        b >>= 1
    return r


def _expand_key(key):
    nk, nr = 8, 14
    w = [0] * (16 * (nr + 1))
    for i in range(32):
        w[i] = key[i] & 0xFF
    rcon = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36, 0x6C, 0xD8, 0xAB, 0x4D]
    for i in range(nk, 4 * (nr + 1)):
        t = [w[(i - 1) * 4 + j] for j in range(4)]
        if i % nk == 0:
            t = [_SBOX[t[1]] ^ rcon[i // nk - 1], _SBOX[t[2]], _SBOX[t[3]], _SBOX[t[0]]]
        elif i % nk == 4:
            t = [_SBOX[t[0]], _SBOX[t[1]], _SBOX[t[2]], _SBOX[t[3]]]
        for j in range(4):
            w[i * 4 + j] = w[(i - nk) * 4 + j] ^ t[j]
    return w


def _encrypt_block(w, block):
    s = list(block)
    for i in range(16):
        s[i] ^= w[i]
    for rnd in range(1, 15):
        s = [_SBOX[x] for x in s]
        t = list(s)
        s[1], s[5], s[9], s[13] = t[5], t[9], t[13], t[1]
        s[2], s[6], s[10], s[14] = t[10], t[14], t[2], t[6]
        s[3], s[7], s[11], s[15] = t[15], t[3], t[7], t[11]
        if rnd != 14:
            for c in range(4):
                a0, a1, a2, a3 = s[c * 4:c * 4 + 4]
                s[c * 4] = _gmul(a0, 2) ^ _gmul(a1, 3) ^ a2 ^ a3
                s[c * 4 + 1] = a0 ^ _gmul(a1, 2) ^ _gmul(a2, 3) ^ a3
                s[c * 4 + 2] = a0 ^ a1 ^ _gmul(a2, 2) ^ _gmul(a3, 3)
                s[c * 4 + 3] = _gmul(a0, 3) ^ a1 ^ a2 ^ _gmul(a3, 2)
        base = rnd * 16
        for i in range(16):
            s[i] ^= w[base + i]
    return s


def _pure_ctr(key, iv12, data):
    w = _expand_key(key[:32])
    out = bytearray(len(data))
    ctr = 2
    for off in range(0, len(data), 16):
        cb = bytearray(iv12[:12]) + bytes([0, 0, 0, 0])
        cb[12] = (ctr >> 24) & 0xFF
        cb[13] = (ctr >> 16) & 0xFF
        cb[14] = (ctr >> 8) & 0xFF
        cb[15] = ctr & 0xFF
        ctr = (ctr + 1) & 0xFFFFFFFF
        stream = _encrypt_block(w, cb)
        n = min(16, len(data) - off)
        for i in range(n):
            out[off + i] = data[off + i] ^ stream[i]
    return bytes(out)


def _gcm_open(key_str, payload):
    """GCM 数据段解密（只做 CTR，不校验 tag），与 JS 版逐字节一致。"""
    iv = payload[:12]
    body = payload[12:]
    data = body[:-16] if len(body) > 16 else body
    key = key_str.encode("utf-8")[:32]
    if _CryptoAES is not None:
        return _CryptoAES.new(key, _CryptoAES.MODE_CTR, nonce=iv, initial_value=2).encrypt(data)
    if _CfCipher is not None:
        from cryptography.hazmat.primitives.ciphers import algorithms, modes
        cipher = _CfCipher(algorithms.AES(key), modes.CTR(iv + b"\x00\x00\x00\x02"))
        enc = cipher.encryptor()
        return enc.update(data) + enc.finalize()
    return _pure_ctr(key, iv, data)


def _b64_bytes(text):
    s = re.sub(r"[^A-Za-z0-9+/]", "", str(text or ""))
    s += "=" * ((4 - len(s) % 4) % 4)
    try:
        return base64.b64decode(s)
    except Exception:
        return b""


def decrypt_text(raw, keys=None):
    """明文 JSON 原样返回；密文按密钥池逐条试解。"""
    text = str(raw if raw is not None else "").strip()
    if not text:
        return ""
    if text[0] in "[{":
        return text
    data = _b64_bytes(text)
    if len(data) < 40:
        return ""
    for key in (keys or DATA_KEYS):
        try:
            plain = _gcm_open(key, data).decode("utf-8", "ignore")
            head = plain.lstrip()[:1]
            if head in ("[", "{"):
                return plain
        except Exception:
            continue
    return ""


def _jparse(text):
    text = str(text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    end = max(text.rfind("]"), text.rfind("}"))
    if end > 0:
        try:
            return json.loads(text[:end + 1])
        except Exception:
            pass
    return None


# ============================ 网络层（无依赖，直连） ============================
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE
_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=_SSL_CTX),
)


def _http(url, headers=None, body=None, timeout=TIMEOUT):
    """返回 (状态码, 文本)。断网/超时不抛异常，状态码给 0。"""
    data = body.encode("utf-8") if isinstance(body, (bytes, bytearray)) is False and body else body
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    hdr = dict(BASE_HEADERS)
    if data:
        hdr.update(JSON_HEADERS)
    if headers:
        hdr.update({str(k): str(v) for k, v in headers.items()})
    for k, v in hdr.items():
        req.add_header(k, v)
    try:
        resp = _OPENER.open(req, timeout=timeout)
        try:
            return resp.getcode(), resp.read().decode("utf-8", "ignore")
        finally:
            resp.close()
    except urllib.error.HTTPError as err:
        try:
            return err.code, err.read().decode("utf-8", "ignore")
        except Exception:
            return err.code, ""
    except Exception:
        return 0, ""


def _enc(seg):
    return urllib.parse.quote(str(seg), safe="")


def cat_path(type_, cls, region, year, sort, page):
    segs = ([type_, cls, region, year, "全部", "全部", sort, page] if type_ == "少儿"
            else [type_, cls, region, year, sort, page])
    return "/cache/zhaopian/" + "/".join(_enc(s) for s in segs) + ".json"


def home_path():
    return "/cache/channel/" + _enc("首页") + ".json"


def search_path(kw, page):
    return "/vc/api/search/" + _enc(kw) + "/%d.json" % page


def detail_path(vid):
    return "/cache/videos/%d/%s.json?version=%s&baoming=%s&channel=%s" % (
        int(vid) // 1000, vid, _enc(VER), _enc(PKG), CHANNEL)


# ============================ 设备链 ============================
def _md5(text):
    return hashlib.md5(str(text).encode("utf-8")).hexdigest()


DEV = {"inited": False, "unlocked": False, "b": "", "uid": 0, "dc": "", "ndev": "", "t": 0.0}
DEV_LOCK = threading.RLock()
DEV_INFLIGHT = [None]


def device_code(seed=""):
    # 站点按「设备」发放免费额度：固定指纹一旦被站点记成老设备就恒返回
    # 10306「请下载正版或观看广告」，永远拿不到直链；因此这里按安装随机生成，
    # 只在被站点拒播时才换一个（见 play_url），不会无节制刷设备。
    raw = "%s|%s|%s|%s" % (seed or "install", PKG, time.time(), os.urandom(8).hex())
    return _md5(raw)[:16]


def dev_base():
    return {
        "baoming": PKG, "packageName": PKG, "version": VER, "channel": CHANNEL,
        "uid": DEV["uid"], "deviceCode": DEV["dc"], "newDeviceCode": DEV["ndev"],
        "b": DEV["b"], "androidId": DEV["dc"], "modelName": MODEL,
    }


def register(force=False):
    with DEV_LOCK:
        if not force and DEV["b"] and time.time() - DEV["t"] < 3600:
            return True
        if not DEV["dc"]:
            DEV["dc"] = device_code()
        body = json.dumps({
            "packageName": PKG, "baoming": PKG, "version": VER, "channel": CHANNEL,
            "uid": 0, "modelName": MODEL, "isOld000": 0,
            "deviceCode": DEV["dc"], "newDeviceCode": "",
        }, ensure_ascii=False, separators=(",", ":"))
    code, text = _http(HOST + "/vc/api/device/isnew", body=body, timeout=TIMEOUT)
    obj = _jparse(decrypt_text(text))
    data = (obj or {}).get("data") or {}
    if not data.get("b"):
        return False
    with DEV_LOCK:
        DEV["b"] = str(data.get("b"))
        DEV["uid"] = data.get("uid") or 0
        DEV["ndev"] = str(data.get("newDeviceCode") or "")
        DEV["t"] = time.time()
        DEV["inited"] = True
    return True


def unlock_ad():
    """广告解锁：5 个请求，只在站点拒播时补跑。"""
    if not DEV["b"]:
        return False
    if DEV["unlocked"] and time.time() - DEV["t"] < 3600:
        return True
    try:
        _http(HOST + "/vc/api/getadjson", body=json.dumps(dev_base(), separators=(",", ":")),
              timeout=TIMEOUT)
        for act in ("show", "clicked", "closed"):
            body = dev_base()
            body["dongzhuo"] = act
            _http(HOST + "/vc/api/addadian", body=json.dumps(body, separators=(",", ":")),
                  timeout=TIMEOUT)
        for s in (0, 1):
            body = {"uid": DEV["uid"], "androidId": DEV["dc"], "newDeviceCode": DEV["ndev"],
                    "b": DEV["b"], "leixing": 1, "baoming": PKG, "channel": CHANNEL,
                    "version": VER, "shiji": s}
            _http(HOST + "/vc/api/tongjiguanggao", body=json.dumps(body, separators=(",", ":")),
                  timeout=TIMEOUT)
        DEV["unlocked"] = True
        return True
    except Exception:
        return False


def ensure_device(unlock=True, force=False):
    with DEV_LOCK:
        if not force and DEV["inited"] and DEV["b"] and time.time() - DEV["t"] < 3600:
            ok = True
        else:
            ok = register(force=force)
        if ok and unlock and not DEV["unlocked"]:
            threading.Thread(target=unlock_ad, daemon=True).start()
        return ok


# ============================ 解析 ============================
def fix_url(url):
    s = str(url or "").strip()
    if not s:
        return ""
    if s.startswith("http://"):
        return "https://" + s[7:]
    if s.startswith("https://"):
        return s
    if s.startswith("/"):
        return HOST + s
    return s


def clean_text(value):
    text = re.sub(r"<[^>]+>", "", str(value if value is not None else ""))
    text = text.replace("&nbsp;", " ")
    return " ".join(text.split()).strip()


def parse_item(item, def_type=""):
    if not isinstance(item, dict):
        return None
    vid = str(item.get("videoId") or item.get("id") or "").strip()
    name = clean_text(item.get("videoName") or item.get("name") or "")
    if not vid or not name:
        return None
    return {
        "vod_id": vid,
        "vod_name": name,
        "vod_pic": fix_url(item.get("fengmiantu") or item.get("dahengtu") or ""),
        "vod_remarks": clean_text(item.get("newchapter") or item.get("serialDesc") or item.get("remarks") or ""),
        "type_name": clean_text(item.get("typeName") or item.get("class") or def_type),
        "vod_year": str(item.get("year") or ""),
        "vod_area": str(item.get("region") or ""),
        "vod_actor": str(item.get("actor") or item.get("yanyuan") or ""),
        "vod_score": str(item.get("score") or ""),
        "_blurb": clean_text(item.get("shortBlurb") or item.get("blurb") or ""),
    }


def parse_list(arr, def_type=""):
    out, seen = [], set()
    if not isinstance(arr, list):
        return out
    for item in arr:
        vod = parse_item(item, def_type)
        if not vod or vod["vod_id"] in seen:
            continue
        seen.add(vod["vod_id"])
        out.append(vod)
    return out


def build_vod(detail, vid, fb=None):
    fb = fb or {}
    name = clean_text(detail.get("videoName") or detail.get("name") or fb.get("vod_name") or ("影片" + vid))
    play = detail.get("playUrlList") if isinstance(detail.get("playUrlList"), list) else []
    eps, total = [], 0
    for i, ep in enumerate(play):
        ep = ep if isinstance(ep, dict) else {}
        nm = clean_text(ep.get("name") or "").replace("$", " ").replace("#", " ")
        if not nm:
            nm = str(i + 1)
        if nm.isdigit():
            nm = "第%s集" % nm
        eps.append("%s$%s|%d|%s" % (nm, vid, i, "" if ep.get("ji") is None else ep.get("ji")))
        total += 1
    year = str(detail.get("year") or fb.get("vod_year") or "")
    area = str(detail.get("region") or fb.get("vod_area") or "")
    typ = clean_text(detail.get("class") or detail.get("subTypeName") or detail.get("typeName") or fb.get("type_name") or "")
    actor = clean_text(detail.get("actor") or fb.get("vod_actor") or "")
    remarks = clean_text(detail.get("remarks") or detail.get("serialDesc") or fb.get("vod_remarks") or "")
    blurb = clean_text(detail.get("blurb") or detail.get("shortBlurb") or fb.get("_blurb") or "")
    content = blurb + ("\n" + clean_text(detail.get("duo")) if detail.get("duo") else "")
    vod = {
        "vod_id": str(vid),
        "vod_name": name,
        "vod_pic": fix_url(detail.get("fengmiantu") or detail.get("dahengtu") or fb.get("vod_pic") or ""),
        "type_name": typ,
        "vod_year": year,
        "vod_area": area,
        "vod_lang": "",
        "vod_actor": actor,
        "vod_director": "",
        "vod_score": str(detail.get("score") or fb.get("vod_score") or ""),
        "vod_content": content,
        "vod_remarks": remarks or ("%d 集" % total if total else "暂无集数"),
        "vod_play_from": BRAND,
        "vod_play_url": "#".join(eps),
    }
    return vod, play, total


def pick_urls(obj):
    """playurl 返回里挑直链：实测多数片子的 urlarr 是 null，真链在 data.url。"""
    if (obj or {}).get("code") not in (0, None):
        return []
    data = (obj or {}).get("data") or (obj or {}).get("result") or {}
    out = []

    def push(value):
        s = str(value or "").strip()
        # 站点拒播时会给占位值 "http://" / 广告片 66.m3u8，必须挡掉
        if not re.match(r"^https?://[A-Za-z0-9]", s, re.I):
            return
        if s.lower().startswith("https://") and "v.trgfd.cn/66.m3u8" in s:
            return
        if s.lower().startswith("http://") and "v.trgfd.cn/66.m3u8" in s:
            return
        if s not in out:
            out.append(s)

    arr = data.get("urlarr")
    if isinstance(arr, list):
        for u in arr:
            push(u)
    elif isinstance(arr, str):
        for u in re.split(r"[,\s]+", arr):
            push(u)
    for key in ("url", "m3u8", "playUrl"):
        push(data.get(key))
    # https 优先，壳播放器兼容性更好；站点分片源多数只有 http，保留兜底
    return [u for u in out if u.lower().startswith("https://")] + \
           [u for u in out if not u.lower().startswith("https://")]


# ============================ 缓存 ============================
_CACHE = {}
_CACHE_LOCK = threading.Lock()


def _cget(key, ttl):
    with _CACHE_LOCK:
        item = _CACHE.get(key)
        if not item:
            return None
        if time.time() - item[0] > ttl:
            _CACHE.pop(key, None)
            return None
        return item[1]


def _cset(key, value, keep=False):
    with _CACHE_LOCK:
        _CACHE[key] = (time.time(), value)
        if not keep and len(_CACHE) > 400:
            for k in sorted(_CACHE, key=lambda x: _CACHE[x][0])[:len(_CACHE) // 2]:
                _CACHE.pop(k, None)
    return value


class Spider(BaseSpider):
    def getName(self):
        return BRAND

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4)(\?|$)", str(url or ""), re.I))

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""
        self._first_ep_warmed = set()

    # ---------------------------- 取流 -------------------------
    def _play_once(self, vid, idx, ji, vuk):
        """一轮四组参数（站点只认其中某一组，命中即返回）。返回 (urls, 拒绝原因, 是否广告拦截)。"""
        combos = [(0, 0, 1), (2, 0, 1), (0, 1, 1), (0, 0, 0)]
        msg, ad_block = "", False
        for t, y, isjiid in combos:
            qs = ("/vc/api/video/playurl?sid=%s&ji=%s&jiIndex=%d&t=%d&y=%d&isjiid=%d"
                  "&androidId=%s&modelName=%s&newDeviceCode=%s&b=%s&version=%s"
                  "&baoming=%s&channel=%s") % (
                vid, _enc(ji if ji != "" else idx), idx, t, y, isjiid,
                _enc(DEV["dc"]), _enc(MODEL), _enc(DEV["ndev"]), _enc(DEV["b"]),
                _enc(VER), _enc(PKG), CHANNEL)
            code, text = _http(HOST + qs, headers={"vuk": vuk}, timeout=TIMEOUT)
            obj = _jparse(decrypt_text(text))
            if not obj:
                continue
            urls = pick_urls(obj)
            if urls:
                return urls, "", False
            data = obj.get("data") or {}
            hint = str(obj.get("msg") or data.get("tishi") or "").strip()
            if int(obj.get("code") or 0) == 10306 or "广告" in hint:
                # 站点把本设备算成「老设备」，必须看广告才给直链（我们拿不到 SDK 回调）
                # 四组参数都会是这个结果，直接跳出，省掉 3 次无效请求
                return [], hint or "站点要求观看广告（10306）", True
            if hint and hint not in ("success", "ok", "获取成功"):
                msg = msg or hint
        return [], msg, ad_block

    def play_url(self, vid, idx, ji):
        key = "pl:%s|%s|%s" % (vid, idx, ji)
        hit = _cget(key, PL_TTL)
        if hit:
            return hit, ""
        vuk = _md5(str(vid) + VUK_MIDDLE + VUK_KEY)
        msg = ""
        for attempt in (0, 1):
            if attempt:
                # 本设备被站点记成老设备（10306）→ 换一个新设备号重登记再试
                with DEV_LOCK:
                    DEV["dc"] = device_code("rotate")
                    DEV["b"] = ""
                    DEV["uid"] = 0
                    DEV["ndev"] = ""
                    DEV["inited"] = False
                    DEV["unlocked"] = False
            if not ensure_device(True):
                msg = msg or "设备注册失败，无法取直链"
                continue
            urls, why, ad_block = self._play_once(vid, idx, ji, vuk)
            if urls:
                _cset(key, urls[0], True)
                if len(urls) > 1:
                    _cset(key + ":alt", urls[1:4], True)
                return urls[0], ""
            msg = why or msg
            # 10306：补跑一次 5 个广告回调（万一站点按回调放行），不行下一轮换设备
            if ad_block and attempt == 0:
                unlock_ad()
                urls, why2, still_block = self._play_once(vid, idx, ji, vuk)
                if urls:
                    _cset(key, urls[0], True)
                    if len(urls) > 1:
                        _cset(key + ":alt", urls[1:4], True)
                    return urls[0], ""
                msg = why2 or msg
            if "片源" in msg:
                break
        return "", msg or "直链获取失败"

    def _warm_first(self, vid, idx, ji):
        def run():
            try:
                self.play_url(vid, idx, ji)
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    # ---------------------------- 入口 -------------------------
    def homeContent(self, filter):
        result = {"class": [{"type_id": tid, "type_name": name} for tid, name in CLASSES]}
        if filter:
            result["filters"] = _FILTER
        return result

    def homeVideoContent(self):
        hit = _cget("home", HOME_TTL)
        if hit:
            return hit
        code, text = _http(HOST + home_path(), timeout=TIMEOUT)
        blocks = _jparse(decrypt_text(text))
        out, seen = [], set()

        def push(arr, def_type):
            for vod in parse_list(arr, def_type):
                if vod["vod_id"] in seen:
                    continue
                seen.add(vod["vod_id"])
                out.append(vod)

        if isinstance(blocks, list):
            for b in blocks:
                b = b if isinstance(b, dict) else {}
                title = str(b.get("title") or b.get("mokuaiming") or "")
                def_type = ""
                for tid, _ in CLASSES:
                    if tid in title:
                        def_type = tid
                data = b.get("data") if isinstance(b.get("data"), list) else []
                push(data[:6] if title == "轮播图" else data, def_type)
        result = {"list": out[:60]}
        if result["list"]:
            _cset("home", result)
        ensure_device(True)
        return result

    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, int(str(pg or "1").split(".")[0]) if str(pg or "").strip("0") else 1)
        type_ = str(tid or "").strip()
        if type_ not in [c[0] for c in CLASSES]:
            type_ = "剧集"
        ext = extend or {}
        cls = str(ext.get("cls") or "全部").strip() or "全部"
        region = str(ext.get("region") or "全部").strip() or "全部"
        year = str(ext.get("year") or "全部").strip() or "全部"
        sort = str(ext.get("sort") or "最新").strip()
        if sort not in ("最热", "评分"):
            sort = "最新"
        key = "list:%s|%s|%s|%s|%s:%d" % (type_, cls, region, year, sort, page)
        hit = _cget(key, LIST_TTL)
        if hit:
            return hit
        code, text = _http(HOST + cat_path(type_, cls, region, year, sort, page), timeout=TIMEOUT)
        arr = _jparse(decrypt_text(text))
        lst = parse_list(arr, type_)
        empty = not isinstance(arr, list) or not arr
        full = len(lst) >= PAGE_SIZE
        pagecount = page if empty else (page + 1 if full else page)
        result = {"page": page, "pagecount": pagecount, "limit": len(lst),
                  "total": 0 if empty else page * PAGE_SIZE, "list": lst}
        if lst:
            _cset(key, result)
        return result

    def searchContent(self, key, quick=False, pg="1"):
        kw = str(key or "").strip()
        page = max(1, int(str(pg or "1")[:3]) if str(pg or "1")[:3].isdigit() else 1)
        if not kw:
            return {"page": 1, "pagecount": 1, "limit": 0, "total": 0, "list": []}
        ckey = "search:%s:%d" % (kw, page)
        hit = _cget(ckey, 90)
        if hit:
            return hit
        code, text = _http(HOST + search_path(kw, page), timeout=TIMEOUT)
        arr = _jparse(decrypt_text(text))
        lst = parse_list(arr)
        result = {"page": page, "pagecount": page, "limit": len(lst),
                  "total": len(lst), "list": lst}
        if lst:
            _cset(ckey, result)
        return result

    def detailContent(self, ids):
        vid = re.sub(r"\D", "", str((ids[0] if isinstance(ids, (list, tuple)) and ids else ids) or ""))
        if not vid:
            return {"list": []}
        key = "detail:" + vid
        hit = _cget(key, DETAIL_TTL)
        if hit:
            return {"list": [hit[0]]}
        code, text = _http(HOST + detail_path(vid), timeout=TIMEOUT)
        detail = _jparse(decrypt_text(text))
        if not isinstance(detail, dict) or not (detail.get("videoName") or detail.get("name")):
            if code == 404:
                return {"list": []}
            return {"list": []}
        vod, play, _total = build_vod(detail, vid)
        _cset(key, (vod, play), True)
        ensure_device(True)
        if play:
            first = play[0] if isinstance(play[0], dict) else {}
            self._warm_first(vid, 0, "" if first.get("ji") is None else first.get("ji"))
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags=None):
        raw = str(id or "").strip()
        m = re.match(r"^(\d+)\|(\d+)\|(\d*)$", raw)
        if m:
            vid, idx, ji = m.group(1), int(m.group(2)), m.group(3)
            url, msg = self.play_url(vid, idx, ji)
            if url:
                nxt = "" if ji == "" else str(int(ji) + 1)
                self._warm_first(vid, idx + 1, nxt)
                return {"parse": 0, "jx": 0, "playUrl": "", "url": url, "header": dict(PLAY_HEADERS)}
            alt = _cget("pl:%s|%s|%s:alt" % (vid, idx, ji), PL_TTL)
            if alt:
                return {"parse": 0, "jx": 0, "playUrl": "", "url": alt[0], "header": dict(PLAY_HEADERS)}
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "", "header": dict(PLAY_HEADERS),
                    "msg": msg}
        if re.match(r"^https?://", raw, re.I):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": raw, "header": dict(PLAY_HEADERS)}
        return {"parse": 0, "jx": 0, "playUrl": "", "url": "", "header": dict(PLAY_HEADERS),
                "msg": "无效播放标识"}
