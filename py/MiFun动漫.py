# -*- coding: utf-8 -*-
"""
MiFun 动漫源 —— NewBox / 影视仓 等 catvod 系 App 的 Python 源（type=3）

适配说明（与原始 TVBox Java 版脚本的区别）：
  1. 运行环境是 App 内置的 Chaquopy(Python 3.11)，脚本被 app.py 以模块方式加载，
     必须提供 Spider 类，并实现 init / getName / getDependence / setExtendInfo 等
     宿主会直接调用的方法；返回值必须是可 json 序列化的 dict。
  2. 只依赖标准库（纯 Python 实现 P-256 ECDH + AES-256-GCM），无需额外 pip 包。
  3. 字段按接口真实 protobuf 结构重新映射（原脚本把“别名”当成年份、把分类 ID 当成
     分类名，列表里 vod_id 还是 int），播放地址改用 TVBox 标准 "标题$id" 格式。
  4. AES 改为 T 表实现，解密 100KB+ 的 boot 包从 ~2.8s 降到 ~0.5s（PC 实测）。

站点配置示例（App 内“添加站点/导入配置”里使用，api 必须以 .py 结尾或包含 .py?）：
  {
    "key": "mifun",
    "name": "MiFun",
    "type": 3,
    "api": "https://你的地址/MiFun.py",
    "ext": "{\"user\":\"tvpy623699\",\"pwd\":\"Tvpy@12345\"}"
  }

ext 支持三种写法：
  {"user":"账号","pwd":"密码","token":"可选","base":"可选","device":"可选","login":true,"boot":true}
  user=账号&pwd=密码
  留空（使用内置默认账号，仅匿名接口）

说明：该站频道的首页/分类/搜索/详情/解析均可匿名访问，默认不登录、不 boot；
如需登录态（部分账号资源），在 ext 里加 "login":true。
"""

import os
import json
import time
import gzip
import zlib
import hmac
import hashlib
import struct
import threading

# App 内置了 pycryptodome（requirements-common），有就用 C 实现，速度更快；
# 没有（比如本地调试/其它宿主）则自动退回下面的纯 Python 实现。
try:
    from Crypto.Cipher import AES as _RefAES
except Exception:
    _RefAES = None

# ============================ 常量 ============================
BASE = "http://cn.mymifun.com/api"
VER = "6.0.6"
PKG = "com.szzd.xcjm.funplus"

# 内置默认账号（可被 ext 覆盖；默认不登录）
DEFAULT_USER = "tvpy623699"
DEFAULT_PWD = "Tvpy@12345"

# 分类频道 ID -> 名称
CATEGORIES = [
    ("56", "番剧"),
    ("57", "国创"),
    ("58", "剧场"),
    ("59", "美漫"),
    ("60", "特摄"),
]

# 内容类型字段(4) -> 名称
TYPE_NAMES = {1: "番剧", 2: "国创", 3: "剧场", 4: "美漫", 5: "特摄"}

# 线路代码 -> 显示名
SOURCE_NAMES = {
    "toutiao": "快看云", "tkyun": "特快云", "jisuyun": "极速云",
    "oid": "天翼云", "file": "无限云", "cxyun": "畅想云",
    "1080zyk": "1080资源", "ffm3u8": "非凡资源", "m3u8": "m3u8",
}

UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"


def _log(msg):
    """Chaquopy 会把 stdout 转到 logcat，方便排查。"""
    try:
        print("[MiFun] %s" % msg)
    except Exception:
        pass


# ============================ HTTP ============================
def http_post(url, data, headers=None, timeout=12, retries=3):
    """POST，返回 (status, headers, body)，带 gzip 解压与重试。"""
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    last = None
    for i in range(max(1, retries)):
        try:
            req = Request(url, data=data, method="POST")
            for k, v in (headers or {}).items():
                req.add_header(k, v)
            resp = urlopen(req, timeout=timeout)
            try:
                body = resp.read()
                enc = (resp.headers.get("Content-Encoding") or "").lower()
                if "gzip" in enc:
                    body = gzip.decompress(body)
                return resp.getcode(), dict(resp.headers), body
            finally:
                try:
                    resp.close()
                except Exception:
                    pass
        except HTTPError as e:
            body = b""
            try:
                body = e.read() or b""
                if "gzip" in (e.headers.get("Content-Encoding") or "").lower():
                    body = gzip.decompress(body)
            except Exception:
                pass
            if e.code in (429, 502, 503, 504) and i + 1 < retries:
                time.sleep(0.8 * (i + 1))
                continue
            return e.code, dict(e.headers or {}), body
        except Exception as e:
            last = e
            if i + 1 < retries:
                time.sleep(0.6 * (i + 1))
    if last:
        raise last
    raise RuntimeError("http post failed: %s" % url)


# ============================ protobuf ============================
def pv(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def tag(f, wt):
    return pv((f << 3) | wt)


def pb_s(f, s):
    b = s.encode("utf-8") if isinstance(s, str) else s
    return tag(f, 2) + pv(len(b)) + b


def pb_i(f, v):
    return tag(f, 0) + pv(v)


def pb_b(f, v):
    return tag(f, 2) + pv(len(v)) + v


def pb_len(b):
    """极简 protobuf 解析：返回 {field: [value, ...]}，bytes 字段保持原样。"""
    i = 0
    n = len(b)

    def rv():
        nonlocal i
        v = 0
        s = 0
        while True:
            if i >= n:
                raise ValueError("eof")
            x = b[i]
            i += 1
            v |= (x & 0x7F) << s
            s += 7
            if not x & 0x80:
                return v

    out = {}
    while i < n:
        try:
            t = rv()
        except Exception:
            break
        f, wt = t >> 3, t & 7
        try:
            if wt == 0:
                out.setdefault(f, []).append(rv())
            elif wt == 2:
                l = rv()
                out.setdefault(f, []).append(b[i:i + l])
                i += l
            elif wt == 1:
                out.setdefault(f, []).append(b[i:i + 8])
                i += 8
            elif wt == 5:
                out.setdefault(f, []).append(b[i:i + 4])
                i += 4
            else:
                break
        except Exception:
            break
    return out


# ============================ P-256 ============================
P_P = 2 ** 256 - 2 ** 224 + 2 ** 192 + 2 ** 96 - 1
P_A = P_P - 3
P_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
P_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
GX = 0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296
GY = 0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5


def _inv(x, m=P_P):
    return pow(x, -1, m)


def _ec_add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2 and (y1 + y2) % P_P == 0:
        return None
    if p1 == p2:
        l = (3 * x1 * x1 + P_A) * _inv(2 * y1) % P_P
    else:
        l = (y2 - y1) * _inv(x2 - x1) % P_P
    x3 = (l * l - x1 - x2) % P_P
    y3 = (l * (x1 - x3) - y1) % P_P
    return (x3, y3)


def _ec_mul(k, pt):
    r = None
    add = pt
    while k:
        if k & 1:
            r = _ec_add(r, add)
        add = _ec_add(add, add)
        k >>= 1
    return r


def ec_keygen():
    d = int.from_bytes(os.urandom(32), "big") % (P_N - 2) + 1
    q = _ec_mul(d, (GX, GY))
    pub = b"\x04" + q[0].to_bytes(32, "big") + q[1].to_bytes(32, "big")
    return d, pub


def ec_shared(d, pub_bytes):
    x = int.from_bytes(pub_bytes[1:33], "big")
    y = int.from_bytes(pub_bytes[33:65], "big")
    s = _ec_mul(d, (x, y))
    return s[0].to_bytes(32, "big")


# ============================ AES-256（T 表加速） ============================
SBOX = bytes.fromhex(
    "637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0"
    "b7fd9326363ff7cc34a5e5f171d8311504c723c31896059a071280e2eb27b275"
    "09832c1a1b6e5aa0523bd6b329e32f8453d100ed20fcb15b6acbbe394a4c58cf"
    "d0efaafb434d338545f9027f503c9fa851a3408f929d38f5bcb6da2110fff3d2"
    "cd0c13ec5f974417c4a77e3d645d197360814fdc222a908846eeb814de5e0bdb"
    "e0323a0a4906245cc2d3ac629195e479e7c8376d8dd54ea96c56f4ea657aae08"
    "ba78252e1ca6b4c6e8dd741f4bbd8b8a703eb5664803f60e613557b986c11d9e"
    "e1f8981169d98e949b1e87e9ce5528df8ca1890dbfe6426841992d0fb054bb16"
)


def _xtime(a):
    a <<= 1
    if a & 0x100:
        a ^= 0x11B
    return a & 0xFF


def _build_te_tables():
    te0 = []
    for x in range(256):
        s = SBOX[x]
        s2 = _xtime(s)
        s3 = s2 ^ s
        te0.append((s2 << 24) | (s << 16) | (s << 8) | s3)

    def rotr(v, n):
        return ((v >> n) | (v << (32 - n))) & 0xFFFFFFFF

    return (te0,
            [rotr(v, 8) for v in te0],
            [rotr(v, 16) for v in te0],
            [rotr(v, 24) for v in te0])


TE0, TE1, TE2, TE3 = _build_te_tables()


def _sub_word(w):
    return ((SBOX[(w >> 24) & 0xFF] << 24) | (SBOX[(w >> 16) & 0xFF] << 16)
            | (SBOX[(w >> 8) & 0xFF] << 8) | SBOX[w & 0xFF])


class AES(object):
    """仅实现加密（GCM 只需要 encrypt_block）。key 长度 16/24/32 均可。"""
    __slots__ = ("nr", "rk")

    def __init__(self, key):
        nk = len(key) // 4
        nr = nk + 6
        self.nr = nr
        w = [int.from_bytes(key[4 * i:4 * i + 4], "big") for i in range(nk)]
        rcon = 1
        for i in range(nk, 4 * (nr + 1)):
            t = w[i - 1]
            if i % nk == 0:
                t = ((t << 8) & 0xFFFFFFFF) | (t >> 24)   # RotWord
                t = _sub_word(t) ^ (rcon << 24)
                rcon = _xtime(rcon)
            elif nk > 6 and i % nk == 4:
                t = _sub_word(t)
            w.append(w[i - nk] ^ t)
        self.rk = w

    def encrypt_block(self, block):
        rk = self.rk
        s0 = int.from_bytes(block[0:4], "big") ^ rk[0]
        s1 = int.from_bytes(block[4:8], "big") ^ rk[1]
        s2 = int.from_bytes(block[8:12], "big") ^ rk[2]
        s3 = int.from_bytes(block[12:16], "big") ^ rk[3]
        nr = self.nr
        for r in range(1, nr):
            n = r * 4
            t0 = (TE0[s0 >> 24] ^ TE1[(s1 >> 16) & 0xFF]
                  ^ TE2[(s2 >> 8) & 0xFF] ^ TE3[s3 & 0xFF] ^ rk[n])
            t1 = (TE0[s1 >> 24] ^ TE1[(s2 >> 16) & 0xFF]
                  ^ TE2[(s3 >> 8) & 0xFF] ^ TE3[s0 & 0xFF] ^ rk[n + 1])
            t2 = (TE0[s2 >> 24] ^ TE1[(s3 >> 16) & 0xFF]
                  ^ TE2[(s0 >> 8) & 0xFF] ^ TE3[s1 & 0xFF] ^ rk[n + 2])
            t3 = (TE0[s3 >> 24] ^ TE1[(s0 >> 16) & 0xFF]
                  ^ TE2[(s1 >> 8) & 0xFF] ^ TE3[s2 & 0xFF] ^ rk[n + 3])
            s0, s1, s2, s3 = t0, t1, t2, t3
        n = nr * 4
        o0 = ((SBOX[s0 >> 24] << 24) | (SBOX[(s1 >> 16) & 0xFF] << 16)
              | (SBOX[(s2 >> 8) & 0xFF] << 8) | SBOX[s3 & 0xFF]) ^ rk[n]
        o1 = ((SBOX[s1 >> 24] << 24) | (SBOX[(s2 >> 16) & 0xFF] << 16)
              | (SBOX[(s3 >> 8) & 0xFF] << 8) | SBOX[s0 & 0xFF]) ^ rk[n + 1]
        o2 = ((SBOX[s2 >> 24] << 24) | (SBOX[(s3 >> 16) & 0xFF] << 16)
              | (SBOX[(s0 >> 8) & 0xFF] << 8) | SBOX[s1 & 0xFF]) ^ rk[n + 2]
        o3 = ((SBOX[s3 >> 24] << 24) | (SBOX[(s0 >> 16) & 0xFF] << 16)
              | (SBOX[(s1 >> 8) & 0xFF] << 8) | SBOX[s2 & 0xFF]) ^ rk[n + 3]
        return b"".join(x.to_bytes(4, "big") for x in (o0, o1, o2, o3))


def _ghash_mul(x, y):
    r = 0xE1 << 120
    z = 0
    v = y
    for i in range(127, -1, -1):
        if (x >> i) & 1:
            z ^= v
        if v & 1:
            v = (v >> 1) ^ r
        else:
            v >>= 1
    return z


def _ghash(h, aad, ct):
    y = 0

    def blk(d):
        nonlocal y
        y = _ghash_mul(y ^ int.from_bytes(d, "big"), h)

    for i in range(0, len(aad), 16):
        blk(aad[i:i + 16].ljust(16, b"\x00"))
    for i in range(0, len(ct), 16):
        blk(ct[i:i + 16].ljust(16, b"\x00"))
    blk(struct.pack(">QQ", len(aad) * 8, len(ct) * 8))
    return y


def _gcm_ctr(aes, j0, data):
    out = bytearray()
    ctr = int.from_bytes(j0, "big") + 1   # GCM 计数器从 inc32(J0) 开始
    for i in range(0, len(data), 16):
        ks = aes.encrypt_block((ctr & ((1 << 128) - 1)).to_bytes(16, "big"))
        chunk = data[i:i + 16]
        out.extend(bytes(a ^ b for a, b in zip(chunk, ks)))
        ctr += 1
    return bytes(out)


def aes_gcm_encrypt(key, nonce, plain, aad=b""):
    if _RefAES is not None:
        try:
            c = _RefAES.new(key, _RefAES.MODE_GCM, nonce=nonce)
            c.update(aad)
            ct, tag = c.encrypt_and_digest(plain)
            return ct + tag
        except Exception:
            pass
    aes = AES(key)
    h = int.from_bytes(aes.encrypt_block(b"\x00" * 16), "big")
    j0 = nonce + b"\x00\x00\x00\x01"
    ct = _gcm_ctr(aes, j0, plain)
    s = _ghash(h, aad, ct)
    tag = (s ^ int.from_bytes(aes.encrypt_block(j0), "big")).to_bytes(16, "big")
    return ct + tag


def aes_gcm_decrypt(key, nonce, data, aad=b""):
    if _RefAES is not None:
        try:
            c = _RefAES.new(key, _RefAES.MODE_GCM, nonce=nonce)
            c.update(aad)
            return c.decrypt_and_verify(data[:-16], data[-16:])
        except Exception:
            pass
    aes = AES(key)
    h = int.from_bytes(aes.encrypt_block(b"\x00" * 16), "big")
    j0 = nonce + b"\x00\x00\x00\x01"
    ct, tag = data[:-16], data[-16:]
    s = _ghash(h, aad, ct)
    exp = (s ^ int.from_bytes(aes.encrypt_block(j0), "big")).to_bytes(16, "big")
    if exp != tag:
        raise ValueError("gcm tag mismatch")
    return _gcm_ctr(aes, j0, ct)


# ============================ 客户端 ============================
class MiFunClient(object):
    def __init__(self, base=BASE, device=None, username="", password="", token=""):
        self.base = (base or BASE).rstrip("/")
        self.device = device or ("tvpy" + hashlib.sha256(b"tvboxpy").hexdigest()[:10])
        self.user = username or ""
        self.pwd = password or ""
        self.token = token or ""
        self.sid = None
        self.key = None
        self.rid = int(time.time() * 1000) & 0x3FFFFFFF
        self._d = None
        self.boot_raw = b""

    def _headers(self):
        return {
            "Content-Type": "application/x-protobuf",
            "User-Agent": "okhttp/4.12.0",
            "X-Transport-Device": hashlib.sha256(self.device.encode()).hexdigest(),
            "X-Transport-Key-Ids": "",
            "Accept-Encoding": "gzip",
        }

    def handshake(self):
        d, pub = ec_keygen()
        self._d = d
        caps = pb_i(1, 1) + pb_i(2, 1) + pb_i(3, 1)
        body = pb_b(1, pub) + pb_s(2, VER) + pb_b(3, caps)
        st, hd, rb = http_post(self.base + "/v3/handshake", body, self._headers())
        if st != 200:
            raise RuntimeError("handshake %s %s" % (st, rb[:80]))
        f = pb_len(rb)
        self.sid = f[1][0].decode()
        shared = ec_shared(d, f[2][0])
        prk = hmac.new(self.sid.encode(), shared, hashlib.sha256).digest()
        self.key = hmac.new(prk, b"v3-session" + b"\x01", hashlib.sha256).digest()
        return self

    def call(self, module, action, payload=b""):
        self.rid = (self.rid + 1) & 0x7FFFFFFF
        rid = self.rid
        req = (pb_i(1, rid) + pb_i(2, module) + pb_i(3, action)
               + pb_s(4, self.device) + pb_b(6, payload)
               + pb_i(7, int(time.time() * 1000)))
        if self.token:
            req += pb_s(5, self.token)
        c = zlib.compressobj(6, zlib.DEFLATED, -15)
        comp = c.compress(req) + c.flush()
        nonce = os.urandom(12)
        frame = pb_i(1, rid) + pb_b(2, nonce + aes_gcm_encrypt(self.key, nonce, comp, b"v3-request"))
        h = self._headers()
        h["X-Session-Id"] = self.sid or ""
        st, hd, rb = http_post(self.base + "/v3", frame, h)
        if hd.get("X-Transport-Error") == "1" or st >= 400:
            raise RuntimeError("api %s/%s http %s %s" % (module, action, st, rb[:100]))
        f = pb_len(rb)
        blob = f[2][0]
        plain = aes_gcm_decrypt(self.key, blob[:12], blob[12:], b"v3-response")
        dec = zlib.decompress(plain, -15)
        r = pb_len(dec)
        return {
            "code": r.get(2, [0])[0],
            "msg": (r.get(3, [b""])[0] or b"").decode("utf-8", "ignore")
            if isinstance(r.get(3, [b""])[0], (bytes, bytearray)) else "",
            "data": r.get(4, [b""])[0],
        }

    def boot(self):
        app = pb_s(1, "MiFun") + pb_s(2, VER) + pb_s(3, PKG)
        dev = pb_s(1, self.device) + pb_i(2, 7) + pb_s(3, "14")
        body = pb_i(1, 1) + pb_s(3, "default") + pb_b(4, app) + pb_b(5, dev) + pb_i(7, 1)
        r = self.call(1, 0, body)
        if r["code"] != 0:
            raise RuntimeError("boot " + r["msg"])
        self.boot_raw = r["data"] or b""
        return self.boot_raw

    def login(self):
        if self.token:
            return self.token
        if not (self.user and self.pwd):
            raise RuntimeError("未配置账号")
        r = self.call(2, 30, pb_s(1, self.user) + pb_s(2, self.pwd))
        if r["code"] != 0:
            raise RuntimeError("登录失败: " + r["msg"])
        self.token = pb_len(r["data"])[2][0].decode()
        return self.token

    def search(self, kw, page=1, limit=20):
        body = pb_s(1, kw) + pb_i(2, page) + pb_i(3, limit) + pb_b(5, b"")
        return self.call(3, 61, body)

    def detail(self, vod_id):
        return self.call(3, 62, pb_i(1, int(vod_id)) + pb_s(3, VER) + pb_i(4, 7))

    def parse(self, api_id, url, ep=0):
        return self.call(3, 69, pb_i(1, api_id) + pb_s(2, url) + pb_i(3, ep))

    def channel(self, cid=1):
        return self.call(3, 60, pb_i(1, cid))

    def category(self, cid, page=1, limit=20):
        return self.call(3, 75, pb_i(1, int(cid)) + pb_i(2, int(page)) + pb_i(3, int(limit)))


# ============================ 工具 ============================
def _txt(d, field, default=""):
    """取 protobuf 字段并转字符串。"""
    v = d.get(field)
    if not v:
        return default
    x = v[0]
    if isinstance(x, (bytes, bytearray)):
        try:
            return x.decode("utf-8", "ignore")
        except Exception:
            return default
    return str(x)


def _int(d, field, default=0):
    v = d.get(field)
    if not v:
        return default
    x = v[0]
    if isinstance(x, (bytes, bytearray)):
        try:
            return int.from_bytes(x, "big")
        except Exception:
            return default
    try:
        return int(x)
    except Exception:
        return default


def _clean(s, limit=0):
    s = (s or "").replace("$", " ").replace("#", " ").replace("||", " ")
    s = " ".join(s.split())
    return s[:limit] if limit else s


# ============================ 宿主接口 ============================
class Spider(object):
    """
    NewBox / catvod Python 源入口类。
    宿主通过 app.spider(...) -> module.Spider() 实例化，再依次调用：
      setExtendInfo(ext) -> init(...) -> homeContent/homeVideoContent/...
    """

    def __init__(self):
        self.extend = ""
        self.cfg = {}
        self.siteKey = ""
        self._c = None
        self._lock = threading.RLock()

    # ---- 兼容宿主可能用到的属性写入 ----
    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    # ---- 元信息 ----
    def getName(self):
        return "MiFun"

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        self.extend = extend if extend is not None else ""
        self._parse_cfg(self.extend)
        return None

    def init(self, extend=""):
        # 宿主在无依赖时传 ext 字符串；有依赖时传依赖实例列表，这里忽略
        if isinstance(extend, (str, dict)):
            self.extend = extend
            self._parse_cfg(extend)
        else:
            self._parse_cfg(self.extend)
        return None

    def _parse_cfg(self, extend):
        cfg = {}
        try:
            if isinstance(extend, dict):
                cfg = dict(extend)
            else:
                s = (extend or "").strip()
                if s.startswith("{"):
                    cfg = json.loads(s)
                elif s.startswith("["):
                    # 依赖列表形式（宿主传列表时会转成字符串），忽略
                    cfg = {}
                elif s and "=" in s:
                    for kv in s.replace("\n", "&").split("&"):
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            cfg[k.strip()] = v.strip()
        except Exception as e:
            _log("配置解析失败: %s" % e)
        if cfg != getattr(self, "cfg", None) and getattr(self, "_c", None) is not None:
            # 配置变了，旧会话作废
            self._c = None
        self.cfg = cfg

    # ---- 客户端 ----
    def _client(self):
        with self._lock:
            if self._c is not None:
                return self._c
            c = MiFunClient(
                base=self.cfg.get("base") or BASE,
                device=self.cfg.get("device") or None,
                username=self.cfg.get("user") or DEFAULT_USER,
                password=self.cfg.get("pwd") or DEFAULT_PWD,
                token=self.cfg.get("token") or "",
            )
            c.handshake()
            # 实测首页/分类/搜索/详情/解析都不需要 boot（省 ~1.5s 和 127KB 流量）；
            # 个别账号需要客户端信息时，在 ext 里加 "boot": true 即可。
            if str(self.cfg.get("boot", "")).lower() in ("1", "true", "yes"):
                c.boot()
            # 该站匿名即可访问全部接口，默认不登录，避免首屏多等 1s
            want_login = str(self.cfg.get("login", "")).lower() in ("1", "true", "yes")
            if want_login and not c.token:
                try:
                    c.login()
                except Exception as e:
                    _log("登录失败，继续匿名访问: %s" % e)
            self._c = c
            return c

    def _api(self, fn, *args):
        last = None
        for _ in range(2):
            try:
                return fn(self._client(), *args)
            except Exception as e:
                last = e
                self._c = None
                time.sleep(0.5)
        if last:
            _log("接口失败: %s" % last)
        raise last if last else RuntimeError("unknown error")

    # ---- 列表项 -> TVBox 结构 ----
    @staticmethod
    def _vod(item):
        d = pb_len(item)
        tid = _int(d, 4)
        return {
            "vod_id": str(_int(d, 1)),
            "vod_name": _txt(d, 3),
            "vod_pic": _txt(d, 6),
            "vod_remarks": _txt(d, 11),
            "vod_year": str(_int(d, 2)) if 2 in d else "",
            "type_name": TYPE_NAMES.get(tid, _txt(d, 12)),
        }

    # ---- 首页分类 ----
    def homeContent(self, filter=False):
        try:
            data = {"class": [{"type_id": t, "type_name": n} for t, n in CATEGORIES]}
            if filter:
                data["filters"] = {}
            return data
        except Exception as e:
            _log("homeContent 异常: %s" % e)
            return {"class": []}

    # ---- 首页推荐 ----
    def homeVideoContent(self):
        try:
            r = self._api(MiFunClient.channel, 1)
            f = pb_len(r["data"])
            vids, seen = [], set()
            items = list(f.get(5, []))
            for mod in f.get(6, [])[:2]:
                md = pb_len(mod)
                if 2 in md:
                    items.extend(pb_len(md[2][0]).get(3, [])[:6])
            for it in items:
                v = self._vod(it)
                if v["vod_id"] in ("0", "") or v["vod_name"] == "":
                    continue
                if v["vod_id"] in seen:
                    continue
                seen.add(v["vod_id"])
                vids.append(v)
                if len(vids) >= 30:
                    break
            return {"list": vids}
        except Exception as e:
            _log("homeVideoContent 异常: %s" % e)
            return {"list": []}

    # ---- 分类列表 ----
    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            pg = int(pg or 1)
            tid = str(tid or "56")
            r = self._api(MiFunClient.category, tid, pg, 20)
            lst = []
            if r.get("data"):
                f = pb_len(r["data"])
                page = pb_len(f[2][0]) if 2 in f else {}
                lst = [self._vod(x) for x in page.get(3, [])]
            return {
                "list": lst,
                "page": pg,
                "pagecount": pg + 1 if lst else pg,
                "limit": 20,
                "total": len(lst),
            }
        except Exception as e:
            _log("categoryContent 异常: %s" % e)
            return {"list": [], "page": int(pg or 1), "pagecount": int(pg or 1), "limit": 20, "total": 0}

    # ---- 详情 ----
    def detailContent(self, ids):
        try:
            if isinstance(ids, (list, tuple)):
                vid = ids[0] if ids else ""
            else:
                vid = ids
            vid = str(vid).strip().strip('"')
            if not vid:
                return {"list": []}
            r = self._api(MiFunClient.detail, vid)
            if r.get("code") != 0 or not r.get("data"):
                return {"list": []}
            d = pb_len(r["data"])
            vod = {
                "vod_id": vid,
                "vod_name": _txt(d, 5),
                "vod_pic": _txt(d, 13),
                "vod_remarks": _txt(d, 22),
                "vod_year": _txt(d, 30),
                "vod_area": _txt(d, 28),
                "vod_lang": _txt(d, 29),
                "vod_actor": _txt(d, 17),
                "vod_director": _txt(d, 18),
                "vod_content": _txt(d, 71),
                "type_name": _txt(d, 12),
            }
            flags, urls = [], []
            for src in d.get(75, []):
                sd = pb_len(src)
                code = _txt(sd, 1)
                name = SOURCE_NAMES.get(code, code or "线路")
                eps = []
                for i, ep in enumerate(sd.get(2, [])):
                    ed = pb_len(ep)
                    ep_url = _txt(ed, 3)
                    ep_title = _clean(_txt(ed, 4)) or ("第%02d集" % (i + 1))
                    if not ep_url:
                        continue
                    direct = ep_url.startswith("http")
                    # TVBox 播放格式：标题$id，id = 模式||地址||集数||1
                    eps.append("%s$%s||%s||%d||1" % (ep_title, "0" if direct else "1", ep_url, i))
                if eps:
                    flags.append(name)
                    urls.append("#".join(eps))
            if flags:
                vod["vod_play_from"] = "$$$".join(flags)
                vod["vod_play_url"] = "$$$".join(urls)
            else:
                vod["vod_play_from"] = ""
                vod["vod_play_url"] = ""
            return {"list": [vod]}
        except Exception as e:
            _log("detailContent 异常: %s" % e)
            return {"list": []}

    # ---- 搜索 ----
    def searchContent(self, key, quick=False, pg="1"):
        try:
            r = self._api(MiFunClient.search, key, int(pg or 1), 20)
            lst = []
            if r.get("code") == 0 and r.get("data"):
                lst = [self._vod(x) for x in pb_len(r["data"]).get(1, [])]
            return {"list": lst}
        except Exception as e:
            _log("searchContent 异常: %s" % e)
            return {"list": []}

    # ---- 播放 ----
    def playerContent(self, flag, id, vipFlags=None):
        header = {"User-Agent": UA}
        try:
            raw = str(id or "")
            if raw.startswith("http"):
                return {"parse": 0, "playUrl": "", "url": raw, "header": header}
            parts = raw.split("||")
            mode = parts[0]
            target = parts[1] if len(parts) > 1 else raw
            ep = 0
            if len(parts) > 2:
                try:
                    ep = int(parts[2])
                except Exception:
                    ep = 0
            if target.startswith("http") or mode == "0":
                return {"parse": 0, "playUrl": "", "url": target, "header": header}
            r = self._api(MiFunClient.parse, 1, target, ep)
            if r.get("code") == 0 and r.get("data"):
                purl = _txt(pb_len(r["data"]), 2)
                if purl:
                    return {"parse": 0, "playUrl": "", "url": purl, "header": header}
            return {"parse": 0, "playUrl": "", "url": "", "header": header}
        except Exception as e:
            _log("playerContent 异常: %s" % e)
            return {"parse": 0, "playUrl": "", "url": "", "header": header}

    # ---- 其它宿主接口 ----
    def liveContent(self, url=""):
        return ""

    def localProxy(self, param=None):
        return None

    def isVideoFormat(self, url):
        return any(x in (url or "").lower() for x in (".mp4", ".m3u8", "douyinvod", "akamaized", ".flv"))

    def manualVideoCheck(self):
        return False

    def action(self, action=""):
        return {}

    def destroy(self):
        with self._lock:
            self._c = None
        return None
