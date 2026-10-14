#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# TVBox Python 爬虫 · 咕噜咕噜 (glgl.tv)
# ------------------------------------------------------------
# 接口协议（已逆向还原）:
#   传输: ECDH secp256r1 握手 + HKDF("v2-session") + AES-256-GCM
#         protobuf 裸编解码 + raw-deflate 压缩
#   1. 握手     POST /app/bn/v2  (AES-128-CBC 预握手, X-Handshake-Key)
#   2. Boot    svc=1 m=0   三层嵌套设备信息(含版本号, 解锁播放必需)
#   3. 榜单翻页 svc=3 m=65  {f1:rank_id, f2:page}
#   4. 搜索     svc=3 m=61  {f1:关键词, f2:页码, f5:{排序}}
#   5. 详情     svc=3 m=62  {f1:vod_id, f4:"APP_PLATFORM_ANDROID_TV", f5:0}
#   播放: 详情 f75 线路中 dyttm3u8/bfzym3u8/lzm3u8/ffm3u8 为明文 m3u8 直链
#
# 用法: TVBox 配置 "spider": "glgl_spider.py"
# 依赖: 无 (优先 pycryptodome/cryptography, 缺失时纯 Python 实现)
# ============================================================
import sys
import json, os, re, time, zlib, base64, hashlib, hmac, secrets
import urllib.request, urllib.parse
import ssl

try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    _BaseSpider = object

BASE = "http://103.45.132.22:19987/app/bn"
UA = "Dalvik/2.1.0 (Linux; U; Android 11; Pixel 4)"

# ============ 加密后端 (三级降级) ============
_BACKEND = None
try:
    from Crypto.Cipher import AES as _PAES
    _BACKEND = "pycryptodome"
except ImportError:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        _BACKEND = "cryptography"
    except ImportError:
        _BACKEND = "pure"

# ---------- 纯 Python AES + GCM (仅当无库时) ----------
if _BACKEND == "pure":
    _SBOX = None
    def _init_sbox():
        global _SBOX, _INV_SBOX, _MUL2, _MUL3, _MUL9, _MUL11, _MUL13, _MUL14
        if _SBOX is not None: return
        p = q = 1
        sb = [0]*256
        while True:
            p = (p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0))
            q ^= q << 1; q ^= q << 2; q ^= q << 4
            q &= 0xFF
            if q & 0x80: q ^= 0x09
            x = q ^ ((q << 1) | (q >> 7)) ^ ((q << 2) | (q >> 6)) ^ ((q << 3) | (q >> 5)) ^ ((q << 4) | (q >> 4))
            sb[p] = x & 0xFF ^ 0x63
            if p == 1: break
        sb[0] = 0x63
        _SBOX = sb
        _INV_SBOX = [0]*256
        for i in range(256): _INV_SBOX[sb[i]] = i
        def xt(a):
            a <<= 1
            return (a ^ 0x1B) & 0xFF if a & 0x100 else a
        _MUL2 = [xt(i) for i in range(256)]
        _MUL3 = [_MUL2[i] ^ i for i in range(256)]
        _MUL9 = [0]*256; _MUL11 = [0]*256; _MUL13 = [0]*256; _MUL14 = [0]*256
        for i in range(256):
            m2 = _MUL2[i]; m4 = _MUL2[m2]; m8 = _MUL2[m4]
            _MUL9[i] = m8 ^ i; _MUL11[i] = m8 ^ m2 ^ i
            _MUL13[i] = m8 ^ m4 ^ i; _MUL14[i] = m8 ^ m4 ^ m2

    def _xtime(a):
        a <<= 1
        return (a ^ 0x1B) & 0xFF if a & 0x100 else a

    _RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1B,0x36,0x6C,0xD8,0xAB,0x4D]

    def _aes128_key_expand(key):
        _init_sbox()
        w = [list(key[i*4:i*4+4]) for i in range(4)]
        for i in range(4, 44):
            t = list(w[i-1])
            if i % 4 == 0:
                t = t[1:] + t[:1]
                t = [_SBOX[b] for b in t]
                t[0] ^= _RCON[i//4-1]
            w.append([w[i-4][j] ^ t[j] for j in range(4)])
        return w

    def _aes256_key_expand(key):
        _init_sbox()
        w = [list(key[i*4:i*4+4]) for i in range(8)]
        for i in range(8, 60):
            t = list(w[i-1])
            if i % 8 == 0:
                t = t[1:] + t[:1]
                t = [_SBOX[b] for b in t]
                t[0] ^= _RCON[i//8-1]
            elif i % 8 == 4:
                t = [_SBOX[b] for b in t]
            w.append([w[i-8][j] ^ t[j] for j in range(4)])
        return w

    def _aes_encrypt_block(w, block):
        s = [[block[r + 4*c] for c in range(4)] for r in range(4)]
        def add_round_key(rnd):
            for c in range(4):
                for r in range(4):
                    s[r][c] ^= w[rnd*4 + c][r]
        def sub_shift():
            for r in range(4):
                row = [_SBOX[s[r][(c + r) % 4]] for c in range(4)]
                for c in range(4): s[r][c] = row[c]
        def mix():
            for c in range(4):
                a = [s[r][c] for r in range(4)]
                s[0][c] = _MUL2[a[0]] ^ _MUL3[a[1]] ^ a[2] ^ a[3]
                s[1][c] = a[0] ^ _MUL2[a[1]] ^ _MUL3[a[2]] ^ a[3]
                s[2][c] = a[0] ^ a[1] ^ _MUL2[a[2]] ^ _MUL3[a[3]]
                s[3][c] = _MUL3[a[0]] ^ a[1] ^ a[2] ^ _MUL2[a[3]]
        nr = len(w)//4 - 1
        add_round_key(0)
        for rnd in range(1, nr):
            sub_shift(); mix(); add_round_key(rnd)
        sub_shift(); add_round_key(nr)
        out = bytearray(16)
        for c in range(4):
            for r in range(4): out[r + 4*c] = s[r][c]
        return bytes(out)

    def _aes_ecb_encrypt(w, data):
        return b"".join(_aes_encrypt_block(w, data[i:i+16]) for i in range(0, len(data), 16))

    def _pkcs7_pad(d):
        n = 16 - len(d) % 16
        return d + bytes([n])*n

    def _pkcs7_unpad(d):
        return d[:-d[-1]] if d and 1 <= d[-1] <= 16 else d

    def _cbc_encrypt(key, iv, data):
        w = _aes128_key_expand(key) if len(key) == 16 else _aes256_key_expand(key)
        data = _pkcs7_pad(data)
        out = bytearray(); prev = iv
        for i in range(0, len(data), 16):
            blk = bytes(a ^ b for a, b in zip(data[i:i+16], prev))
            prev = _aes_ecb_encrypt(w, blk)
            out += prev
        return bytes(out)

    def _cbc_decrypt(key, iv, data):
        _init_sbox()
        # ECB decrypt 需要逆向… 为性能考虑, 纯Python 握手解密仅此一处, 用逐块实现
        w = _aes128_key_expand(key) if len(key) == 16 else _aes256_key_expand(key)
        nr = len(w)//4 - 1
        inv_sbox = _INV_SBOX
        def dec_block(blk):
            # state 列主序
            s = [[blk[r + 4*c] for c in range(4)] for r in range(4)]
            def inv_shift():
                for r in range(4):
                    row = [s[r][(c - r) % 4] for c in range(4)]
                    for c in range(4): s[r][c] = row[c]
            def add_rk(rnd):
                for c in range(4):
                    for r in range(4): s[r][c] ^= w[rnd*4 + c][r]
            def inv_sub():
                for r in range(4):
                    for c in range(4): s[r][c] = inv_sbox[s[r][c]]
            def inv_mix():
                for c in range(4):
                    a = [s[r][c] for r in range(4)]
                    s[0][c] = _MUL14[a[0]] ^ _MUL11[a[1]] ^ _MUL13[a[2]] ^ _MUL9[a[3]]
                    s[1][c] = _MUL9[a[0]] ^ _MUL14[a[1]] ^ _MUL11[a[2]] ^ _MUL13[a[3]]
                    s[2][c] = _MUL13[a[0]] ^ _MUL9[a[1]] ^ _MUL14[a[2]] ^ _MUL11[a[3]]
                    s[3][c] = _MUL11[a[0]] ^ _MUL13[a[1]] ^ _MUL9[a[2]] ^ _MUL14[a[3]]
            add_rk(nr)
            for rnd in range(nr-1, 0, -1):
                inv_shift(); inv_sub(); add_rk(rnd); inv_mix()
            inv_shift(); inv_sub(); add_rk(0)
            out = bytearray(16)
            for c in range(4):
                for r in range(4): out[r + 4*c] = s[r][c]
            return bytes(out)
        out = bytearray(); prev = iv
        for i in range(0, len(data), 16):
            blk = data[i:i+16]
            out += bytes(a ^ b for a, b in zip(dec_block(blk), prev))
            prev = blk
        return bytes(out)

    # ---- GCM ----
    def _ghash(h, data):
        # h: 16B hash 子密钥; 纯Python 位运算 GF(2^128)
        def gmul(a, b):
            # GCM 位串约定: MSB=x^0, 倍乘=右移, 溢出(bit0)约减 R=0xE1<<120
            r = 0; v = b
            for i in range(127, -1, -1):
                if (a >> i) & 1: r ^= v
                v = (v >> 1) ^ (0xE1 << 120 if v & 1 else 0)
            return r
        # 将字节串转 int (大端)
        def b2i(b): return int.from_bytes(b, "big")
        def i2b(i): return i.to_bytes(16, "big")
        y = 0
        for i in range(0, len(data), 16):
            blk = data[i:i+16]
            if len(blk) < 16: blk = blk + b"\x00" * (16 - len(blk))
            y = gmul(y ^ b2i(blk), b2i(h))
        return i2b(y)

    def _gcm_encrypt(key, nonce, plain):
        w = _aes256_key_expand(key)
        h = _aes_ecb_encrypt(w, b"\x00"*16)
        j0 = nonce + b"\x00\x00\x00\x01"  # 96-bit nonce
        # 计数器加密 (CTR)
        ct = bytearray(); counter = 2
        for i in range(0, len(plain), 16):
            ctr_blk = nonce + counter.to_bytes(4, "big")
            ks = _aes_ecb_encrypt(w, ctr_blk)
            blk = plain[i:i+16]
            ct += bytes(a ^ b for a, b in zip(blk, ks[:len(blk)]))
            counter += 1
        # GHASH: AAD(empty) || ct || len block
        pad_ct = ct + b"\x00" * ((16 - len(ct) % 16) % 16)
        lenblk = (0).to_bytes(8, "big") + (len(plain) * 8).to_bytes(8, "big")
        s = _ghash(h, pad_ct + lenblk)
        ekj0 = _aes_ecb_encrypt(w, j0)
        tag = bytes(a ^ b for a, b in zip(s, ekj0))
        return bytes(ct), tag

    def _gcm_decrypt(key, nonce, ct_tag):
        # ct_tag = ciphertext + tag(16B) — 无校验解密 (tag 忽略)
        nonce = ct_tag[:12] if nonce is None else nonce
        w = _aes256_key_expand(key)
        ct = ct_tag[:-16] if len(ct_tag) > 16 else ct_tag
        pt = bytearray(); counter = 2
        for i in range(0, len(ct), 16):
            ctr_blk = nonce + counter.to_bytes(4, "big")
            ks = _aes_ecb_encrypt(w, ctr_blk)
            blk = ct[i:i+16]
            pt += bytes(a ^ b for a, b in zip(blk, ks[:len(blk)]))
            counter += 1
        return bytes(pt)

# ---------- 统一加密接口 ----------
def aes_cbc_encrypt(key, iv, data):
    if _BACKEND == "pycryptodome":
        return _PAES.new(key, _PAES.MODE_CBC, iv).encrypt(
            data + bytes([16 - len(data) % 16]) * (16 - len(data) % 16))
    if _BACKEND == "cryptography":
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        pad = 16 - len(data) % 16
        return enc.update(data + bytes([pad])*pad) + enc.finalize()
    return _cbc_encrypt(key, iv, data)

def aes_cbc_decrypt(key, iv, data):
    if _BACKEND == "pycryptodome":
        return _PAES.new(key, _PAES.MODE_CBC, iv).decrypt(data)
    if _BACKEND == "cryptography":
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        return dec.update(data) + dec.finalize()
    return _cbc_decrypt(key, iv, data)

def pkcs7_unpad(d):
    return d[:-d[-1]] if d and 1 <= d[-1] <= 16 else d

def aes_gcm_encrypt(key, nonce, data):
    """返回 nonce+ct+tag"""
    if _BACKEND == "pycryptodome":
        ci = _PAES.new(key, _PAES.MODE_GCM, nonce, mac_len=16)
        ct = ci.encrypt(data)
        return nonce + ct + ci.digest()
    if _BACKEND == "cryptography":
        ct = AESGCM(key).encrypt(nonce, data, None)
        return nonce + ct
    ct, tag = _gcm_encrypt(key, nonce, data)
    return nonce + ct + tag

def aes_gcm_decrypt(key, nonce, ct):
    """ct 含尾部 16B tag (忽略校验)"""
    if _BACKEND == "pycryptodome":
        return _PAES.new(key, _PAES.MODE_GCM, nonce, mac_len=16).decrypt(ct)
    if _BACKEND == "cryptography":
        return AESGCM(key).decrypt(nonce, ct, None)
    return _gcm_decrypt(key, nonce, ct)

# ---------- 纯 Python secp256r1 ECDH ----------
_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
_A = P_A = _P - 3
_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
_GX = 0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296
_GY = 0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5
_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551

def _pt_add(p1, p2):
    if p1 is None: return p2
    if p2 is None: return p1
    x1, y1 = p1; x2, y2 = p2
    if x1 == x2:
        if (y1 + y2) % _P == 0: return None
        lam = (3 * x1 * x1 + _A) * pow(2 * y1, _P - 2, _P) % _P
    else:
        lam = (y2 - y1) * pow((x2 - x1) % _P, _P - 2, _P) % _P
    x3 = (lam * lam - x1 - x2) % _P
    y3 = (lam * (x1 - x3) - y1) % _P
    return (x3, y3)

def _pt_mul(k, pt):
    r = None
    while k:
        if k & 1: r = _pt_add(r, pt)
        pt = _pt_add(pt, pt)
        k >>= 1
    return r

def ecdh_keypair():
    priv = secrets.randbelow(_N - 1) + 1
    pub = _pt_mul(priv, (_GX, _GY))
    pub65 = b"\x04" + pub[0].to_bytes(32, "big") + pub[1].to_bytes(32, "big")
    return priv, pub65

def ecdh_shared(priv, server_pub65):
    sx = int.from_bytes(server_pub65[1:33], "big")
    sy = int.from_bytes(server_pub65[33:65], "big")
    shared = _pt_mul(priv, (sx, sy))
    return shared[0].to_bytes(32, "big")

# ============ protobuf 裸编解码 ============
def pb_varint(n):
    out = b""
    while True:
        b = n & 0x7F; n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n: return out

def pb_read_varint(data, i):
    r, s = 0, 0
    while True:
        b = data[i]; i += 1
        r |= (b & 0x7F) << s
        if not (b & 0x80): return r, i
        s += 7

def pb_field(fnum, wire, payload):
    tag = pb_varint((fnum << 3) | wire)
    if wire == 0: return tag + pb_varint(payload)
    if wire == 2: return tag + pb_varint(len(payload)) + payload
    raise ValueError("wire")

def pb_var(fnum, val):  return pb_field(fnum, 0, val)
def pb_bytes(fnum, b):  return pb_field(fnum, 2, b)
def pb_str(fnum, s):    return pb_field(fnum, 2, s.encode("utf-8") if isinstance(s, str) else s)

def pb_decode(data):
    out, i, n = [], 0, len(data)
    while i < n:
        try:
            tag, i = pb_read_varint(data, i)
            fnum, wire = tag >> 3, tag & 7
            if wire == 0:
                val, i = pb_read_varint(data, i)
                out.append((fnum, 0, val))
            elif wire == 2:
                ln, i = pb_read_varint(data, i)
                out.append((fnum, 2, data[i:i+ln])); i += ln
            elif wire == 1:
                out.append((fnum, 1, data[i:i+8])); i += 8
            elif wire == 5:
                out.append((fnum, 5, data[i:i+4])); i += 4
            else:
                break
        except (IndexError, ValueError):
            break
    return out

def deflate_raw(data, level=6):
    c = zlib.compressobj(level, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()

def inflate_raw(data):
    return zlib.decompressobj(-15).decompress(data)

# ============ 协议客户端 ============
class GuluClient:
    def __init__(self):
        self.session_id = None
        self.key = None
        self.android_id = secrets.token_hex(8).encode()   # 16 hex 字符
        self._booted = False
        self._last_search = 0
        self._last_m61 = 0        # m=61 (搜索/分类浏览) 全局节流时间戳
        self.parse_apis = {}       # boot f7 解析接口配置 {名称: URL模板}

    def _post(self, body, session_id="", handshake_key=""):
        req = urllib.request.Request(BASE + "/v2", data=body, method="POST")
        req.add_header("Content-Type", "application/x-protobuf")
        req.add_header("User-Agent", UA)
        req.add_header("X-Player-Page-Protection", "1")
        if session_id: req.add_header("X-Session-Id", session_id)
        if handshake_key: req.add_header("X-Handshake-Key", handshake_key)
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read()

    def ensure(self):
        """握手 + boot (含设备指纹, 是解锁播放的关键)"""
        if self.key is not None and self._booted:
            return True
        if not self.handshake():
            return False
        return self.boot()

    def handshake(self):
        priv, pub65 = ecdh_keypair()
        inner = pb_var(1, 1) + pb_var(2, 1) + pb_var(3, 1)
        outer = pb_bytes(1, pub65) + pb_str(2, "1.0.0") + pb_bytes(3, inner)
        hex_key = secrets.token_hex(16)          # 32 字符 AES-128 key
        iv = os.urandom(16)
        ct = aes_cbc_encrypt(hex_key.encode(), iv, zlib.compress(outer, 5))
        body = base64.b64encode(iv + ct)
        try:
            resp = self._post(body, handshake_key=hex_key)
        except Exception:
            return False
        raw = base64.b64decode(resp)
        plain = pkcs7_unpad(aes_cbc_decrypt(hex_key.encode(), raw[:16], raw[16:]))
        data = zlib.decompress(plain)
        fields = {}
        for f, w, v in pb_decode(data):
            fields.setdefault(f, v)
        if 1 not in fields or 2 not in fields: return False
        self.session_id = fields[1].decode()
        spub = fields[2]
        shared = ecdh_shared(priv, spub)
        # HKDF: PRK = HMAC(sessionId, shared); OKM = Expand(prk, "v2-session", 32)
        prk = hmac.new(self.session_id.encode(), shared, hashlib.sha256).digest()
        okm = b""; t = b""; i = 1
        while len(okm) < 32:
            t = hmac.new(prk, t + b"v2-session" + bytes([i]), hashlib.sha256).digest()
            okm += t; i += 1
        self.key = okm[:32]
        return True

    def boot(self):
        """AppBoot — 三层嵌套设备信息; 不带版本号服务器返回 500 getAppVersion() on null"""
        aid = self.android_id.decode()
        device_info = pb_str(1, "咕噜咕噜") + pb_str(2, "2.1.2") \
                    + pb_str(3, "com.jymqfh.xee") + pb_str(4, aid) + pb_str(5, "212")
        device_state = pb_str(1, aid) + pb_var(2, 0) + pb_str(3, "11") \
                     + pb_str(4, "Pixel 4") + pb_str(5, "google/redfin/redfin:11/RQ3A.211001.001") \
                     + pb_str(6, "google") + pb_str(7, "redfin") + pb_var(8, 0) \
                     + pb_str(9, "unknown") + pb_str(10, "unknown") + pb_var(11, 0) \
                     + pb_var(12, 30)
        boot_body = pb_str(1, "v1") + pb_str(2, "Android 11") + pb_str(3, "gulu") \
                  + pb_bytes(4, device_info) + pb_bytes(5, device_state)
        r = self.api(1, 0, boot_body)
        self._booted = r is not None
        # 提取解析接口配置 (f7: {f2:名称, f3:URL模板})
        if r and r.get("payload"):
            try:
                self.parse_apis = {}
                for f, w, v in pb_decode(r["payload"]):
                    if f == 7 and w == 2:
                        name = url = None
                        for sf, sw, sv in pb_decode(v):
                            if sf == 2 and sw == 2: name = _safe_str(sv)
                            elif sf == 3 and sw == 2: url = _safe_str(sv)
                        if name and url:
                            self.parse_apis[name] = url
            except Exception:
                pass
        return self._booted

    def api(self, service, method, body=b""):
        if self.key is None: return None
        # m=61 (VodSearch) 搜索与分类浏览共享服务器令牌桶:
        # 全局节流 2.8s, 防分类翻页吃空桶导致后续搜索被拒
        if method == 61:
            wait = 2.8 - (time.time() - self._last_m61)
            if wait > 0 and self._last_m61 > 0:
                time.sleep(wait)
            self._last_m61 = time.time()
        req_id = int(time.time() * 1000)
        ts = req_id
        inner = pb_var(1, req_id) + pb_var(2, service) + pb_var(3, method) \
              + pb_bytes(4, self.android_id) + pb_bytes(5, b"") \
              + pb_bytes(6, body) + pb_var(7, ts)
        compressed = deflate_raw(inner, 6)
        blob = aes_gcm_encrypt(self.key, os.urandom(12), compressed)
        outer = pb_var(1, ts) + pb_bytes(2, blob)
        try:
            resp = self._post(outer, session_id=self.session_id)
        except Exception:
            return None
        fields = pb_decode(resp)
        enc = next((v for f, w, v in fields if f == 2 and w == 2), None)
        if enc is None or len(enc) < 28: return None
        plain = aes_gcm_decrypt(self.key, enc[:12], enc[12:])
        try:
            data = inflate_raw(plain)
        except Exception:
            return None
        out = pb_decode(data)
        code = next((v for f, w, v in out if f == 2 and w == 0), None)
        # payload: f3 = 消息/错误, f4 = 数据体
        msg = next((v for f, w, v in out if f == 3 and w == 2), None)
        payload = next((v for f, w, v in out if f == 4 and w == 2), None)
        return {"code": code, "msg": msg, "payload": payload}

# ============ 业务解析 ============
# 分类体系 (m=66 VodChannelPage, 2026-08-25 对齐可搜索版)
# 请求体: f1=分类ID f2=页码 f3=年份(str) f5=排序对象{f1=1,f2=0,f3=sort}
# 分类走 m=66 不占 m=61 搜索令牌桶 —— 搜索稳定性的关键
CATEGORIES = [
    {"type_id": "movie",   "type_name": "电影"},
    {"type_id": "tv",      "type_name": "电视剧"},
    {"type_id": "variety", "type_name": "综艺"},
    {"type_id": "anime",   "type_name": "动漫"},
    {"type_id": "short",   "type_name": "短剧"},
    {"type_id": "doc",     "type_name": "纪录片"},
    {"type_id": "cn",      "type_name": "大陆剧"},
    {"type_id": "hk",      "type_name": "港剧"},
    {"type_id": "tw",      "type_name": "台剧"},
    {"type_id": "us",      "type_name": "美剧"},
    {"type_id": "kr",      "type_name": "韩剧"},
    {"type_id": "jp",      "type_name": "日剧"},
    {"type_id": "th",      "type_name": "泰剧"},
    {"type_id": "uk",      "type_name": "英剧"},
    {"type_id": "ru",      "type_name": "俄剧"},
]
TYPE_MAP = {
    "movie": 8, "tv": 9, "variety": 10, "anime": 11,
    "short": 12, "doc": 6, "cn": 34, "hk": 41,
    "tw": 42, "us": 35, "kr": 36, "jp": 38,
    "th": 39, "uk": 37, "ru": 45,
    # 兼容旧版 type_id (TVBox 可能缓存 v3 分类入口)
    "c1": 8, "c2": 9, "c3": 10, "c4": 11, "c5": 12,
    "46": 6, "40": 42,
}
SORTS = [("vod_hits_week", "最热"), ("vod_time", "最新"), ("vod_score", "评分")]
# m=66 翻页阈值: 达到该条数视为还有下一页 (频道类多, 榜单类少)
_PAGE_MORE = {8: 10, 9: 10, 10: 10, 11: 10, 12: 10, 6: 3}  # 其余默认 2

def _m66_body(cat_id, page, year="", sort=""):
    """m=66 VodChannelPage 请求体 (字段构造对齐已验证可用版)
    f1=varint分类ID; f2=length-delimited包varint页码; f3=年份; f5=排序对象"""
    body = pb_var(1, cat_id)
    # f2: 页码 (bytes 字段包 varint, 与 proto 定义 field2:message 一致)
    pv = b""
    n = page if page > 0 else 1
    while n:
        b7 = n & 0x7F
        n >>= 7
        pv += bytes([b7 | (0x80 if n else 0)])
    body += b"\x12" + bytes([len(pv)]) + pv
    if year:
        body += pb_str(3, str(year))
    if sort:
        # 排序对象 {f1:1, f2:0(length-delim包varint), f3:sort} — 字节级对齐可用版
        body += pb_bytes(5, pb_var(1, 1) + b"\x12\x01\x00" + pb_str(3, str(sort)))
    return body

# 线路显示名 (详情响应 f75 线路名 → TVBox 线路名)
LINE_NAMES = {"dyttm3u8": "电影天堂", "bfzym3u8": "暴风资源",
              "lzm3u8": "量子资源", "ffm3u8": "非凡资源",
              "qq": "腾讯视频", "qiyi": "爱奇艺", "youku": "优酷",
              "newxfyun": "咕噜4K", "xfyun": "咕噜4K二线",
              "CO4K": "咖啡4K超清", "jplink": "金牌极速",
              "rose": "玫瑰4K", "NBY": "蚂蚁资源",
              "qsvip": "旋风VIP", "qingshan": "青山资源"}

# 密文前缀 → 解析接口名 (boot f7 配置里的 f2 名称)
# 验证日期 2026-08-25: 7 种前缀全部真解析+可播
CIPHER_API = {
    "CO4K_":     "咖啡4K",
    "rose_":     "咖啡4K",
    "NBY-":      "蚂蚁",
    "qsvip-":    "熊出没",
    "qingshan-": "熊出没",
    "JP-":       "旋风金牌",
    "xfy-":      "新咕噜4K",
}
# 线路名 → 解析接口 (优先于前缀: xfyun/newxfyun 密文同为 xfy- 但接口不同)
# xfyun二线 → 咕噜4K总接口(p.php, 域名慢~9s); newxfyun → 新咕噜4K(dsxt)
# 2026-08-25 实测: dsxt 不认 xfyun 的密文, p.php 都认
FLAG_API = {
    "咕噜4K":     "新咕噜4K",
    "咕噜4K二线": "咕噜4K总接口",
    "玫瑰4K":     "咖啡4K",
    "咖啡4K":     "咖啡4K",
    "金牌极速":   "旋风金牌",
    "蚂蚁资源":   "蚂蚁",
    "旋风VIP":    "熊出没",
    "青山资源":   "熊出没",
}
# 解析接口兜底 URL 模板 (boot 配置缺失时用; 2026-08-25 抓取)
API_FALLBACK = {
    "咖啡4K":   "https://co4k.1ljx.com:32010/api/?key=6db7285d-c228-4cee-918e-67a01ef7c3f8&url=",
    "蚂蚁":     "https://api.nbyjson.top:7788/api/?key=8LJohkjTZHC2F9ct48&url=",
    "熊出没":   "https://jf.hxx2023.cc/api?key=Uw5rZokFSAywqcLN&url=",
    "旋风金牌": "http://111.170.58.215:4470/api.php?id=",
    "咕噜金牌": "http://111.170.58.215:4470/api.php?id=",
    "咕噜4K总接口": "https://xfyvideochandi.online/p.php?id=",
    "新咕噜4K": "http://172.247.189.48:7788/dsxt/api.php?user=xt&key=969632c8da19b3ef8c56e5b51011d5e0&j=19227eae77225a30&url=",
    "咕噜4K":   "http://172.247.189.48:7788/dsxt/api.php?user=xt&key=e1234a9df0358c6d78f20721a1b7b055&j=b8582063bca37121&url=",
}

def _cipher_prefix(url):
    """密文前缀识别: xfy-xxx / CO4K_xxx / NBY-xxx ..."""
    for p in CIPHER_API:
        if url.startswith(p):
            return p
    return None

def _get(client):
    """获取(或重建)客户端单例"""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = GuluClient()
    if not _CLIENT.ensure():
        _CLIENT = GuluClient()
        if not _CLIENT.ensure():
            return None
    return _CLIENT

_CLIENT = None
_search_cache = {}   # {关键词: (时间戳, 结果)} 10 分钟搜索缓存

def _safe_str(b):
    try:
        return b.decode("utf-8")
    except Exception:
        return ""

def _parse_vod_item(item_bytes):
    """搜索/榜单 里的视频条目 -> dict"""
    fields = pb_decode(item_bytes)
    d = {}
    for f, w, v in fields:
        if w == 0:
            if f == 1: d["id"] = v
            elif f == 2: d["year"] = v
            elif f == 4: d["type"] = v
        elif w == 2:
            if f == 3: d["name"] = _safe_str(v)
            elif f == 6: d["pic"] = _safe_str(v)
            elif f == 9: d["remark_alt"] = _safe_str(v)
            elif f == 11: d["remark"] = _safe_str(v)
    return d

def _rank_modules(payload):
    """解析 VodRankPage 响应为模块列表 [(模块名, 分类名, [video,...]), ...]"""
    mods = []
    if not payload: return mods
    for f, w, v in pb_decode(payload):
        if w != 2 or len(v) < 100: continue
        try:
            sub = pb_decode(v)
        except Exception:
            continue
        f66s = [vv for ff, ww, vv in sub if ff == 66 and ww == 2]
        if not f66s: continue
        name = ""
        cat = ""
        for ff, ww, vv in sub:
            if ff == 3 and ww == 2: name = _safe_str(vv)
            elif ff == 7 and ww == 2: cat = _safe_str(vv)
        vids = []
        for vv in f66s:
            d = _parse_vod_item(vv)
            if d.get("id") and d.get("name"):
                vids.append(d)
        if vids:
            mods.append((name, cat, vids))
    return mods

def _vod_list_from_payload(payload):
    """从 API payload 提取视频列表 (兼容三种结构)
    1. VodRankPage: payload {f1: 模块{f66: [video]}} → 展开所有模块
    2. 包装器: {f1: id, f2: name(str), f3: video}
    3. 直接视频: {f1: vod_id(int), f2: year(int), f3: title}
    """
    if not payload: return []
    items = []
    for f, w, v in pb_decode(payload):
        if w != 2 or len(v) < 30: continue
        try:
            sub = pb_decode(v)
        except Exception:
            continue
        # 1) 模块结构: 有 f66 视频列表
        f66s = [vv for ff, ww, vv in sub if ff == 66 and ww == 2]
        if f66s:
            for vv in f66s:
                d = _parse_vod_item(vv)
                if d.get("id") and d.get("name"):
                    items.append(d)
            continue
        # 2/3) f2 是 varint → 视频条目; 否则 → 包装器提取 f3
        f2_is_int = any(ff == 2 and ww == 0 for ff, ww, _ in sub)
        if f2_is_int:
            d = _parse_vod_item(v)
            if d.get("id") and d.get("name"):
                items.append(d)
        else:
            for ff, ww, vv in sub:
                if ff == 3 and ww == 2 and len(vv) > 30:
                    d = _parse_vod_item(vv)
                    if d.get("id") and d.get("name"):
                        items.append(d)
    return items

class Spider(_BaseSpider):
    HOST = "http://103.45.132.22:22670"

    def getName(self):
        return "咕噜咕噜"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    # ---------- 首页 ----------
    def _build_filters(self):
        """分类筛选器 (TVBox 标准key: year/by, 非标准key会致部分内核分类页空白)"""
        years = [str(y) for y in range(2026, 2014, -1)]
        filters = {}
        for cat in CATEGORIES:
            filters[cat["type_id"]] = [
                {"key": "year", "name": "年份",
                 "value": [{"n": "全部", "v": ""}] + [{"n": y, "v": y} for y in years]},
                {"key": "by", "name": "排序",
                 "value": [{"n": n, "v": v} for v, n in SORTS]},
            ]
        return filters

    def homeContent(self, filter=1):
        c = _get(None)
        result = {"class": [], "list": []}
        # m=66 分类体系: 15 分类 (对齐 APP 频道页)
        for cat in CATEGORIES:
            result["class"].append({"type_id": cat["type_id"],
                                    "type_name": cat["type_name"]})
        if filter:
            result["filters"] = self._build_filters()
        # 首页推荐: 电视剧频道第一页 (m=66, 不占搜索配额)
        try:
            r = c.api(3, 66, _m66_body(9, 1))
            if r and r.get("payload"):
                for d in _vod_list_from_payload(r["payload"])[:24]:
                    result["list"].append(self._item_to_home(d))
        except Exception:
            pass
        return result

    def homeVideoContent(self):
        c = _get(None)
        try:
            r = c.api(3, 66, _m66_body(9, 1))
            if r and r.get("payload"):
                lst = [self._item_to_home(d) for d in _vod_list_from_payload(r["payload"])[:24]]
                return {"list": lst}
        except Exception:
            pass
        return {}

    def _item_to_home(self, d):
        return {
            "vod_id": str(d["id"]),
            "vod_name": d.get("name", ""),
            "vod_pic": d.get("pic", ""),
            "vod_remark": d.get("remark") or d.get("remark_alt") or "",
        }

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg=1, filter=1, extend=None):
        c = _get(None)
        try:
            page = int(pg) if pg else 1
        except (ValueError, TypeError):
            page = 1
        # extend 兼容 string JSON / dict 两种传法
        ext = extend or {}
        if isinstance(ext, str):
            try:
                ext = json.loads(ext)
            except Exception:
                ext = {}
        if not isinstance(ext, dict):
            ext = {}
        cat_id = TYPE_MAP.get(str(tid))
        if cat_id is None:
            # 未知 type_id: 数字型直接当频道 ID 试 (m=66 f1 体系宽泛)
            try:
                cat_id = int(tid)
            except (ValueError, TypeError):
                return {"list": []}
        year = ext.get("year") or ""
        sort = ext.get("sort") or ext.get("by") or ""
        body = _m66_body(cat_id, page, year, sort)
        # m=66 偶发空响应, 退避重试一次
        items = []
        for attempt in range(2):
            r = c.api(3, 66, body)
            payload = (r or {}).get("payload") or b""
            if payload and len(payload) > 100:
                items = [self._item_to_home(d)
                         for d in _vod_list_from_payload(payload)]
                break
            if attempt == 0:
                time.sleep(1.5)
        threshold = _PAGE_MORE.get(cat_id, 2)
        hasmore = 1 if len(items) >= threshold else 0
        return {"list": items, "page": page,
                "pagecount": page + 1 if hasmore else page,
                "limit": max(len(items), threshold), "total": len(items)}

    # ---------- 详情 ----------
    def detailContent(self, ids=None):
        c = _get(None)
        if not ids:
            return {}
        try:
            vid = int(str(ids[0]).strip())
        except (ValueError, TypeError, IndexError):
            return {}
        body = pb_var(1, vid) + pb_str(4, "APP_PLATFORM_ANDROID_TV") + pb_var(5, 0)
        r = c.api(3, 62, body)
        if not r or not r.get("payload"):
            return {}
        detail = pb_decode(r["payload"])
        vod = {
            "vod_id": str(vid),
            "vod_name": "", "vod_pic": "", "vod_actor": "",
            "vod_director": "", "vod_area": "", "vod_year": "",
            "vod_content": "", "vod_remarks": "", "type_name": "",
        }
        genres, actors, directors = [], [], []
        sources = []          # [(线路名, [(集名, 链接), ...]), ...]
        for f, w, v in detail:
            if w == 0: continue
            if f == 5: vod["vod_name"] = _safe_str(v)
            elif f == 13: vod["vod_pic"] = _safe_str(v)
            elif f == 17: actors.append(_safe_str(v))
            elif f == 18: directors.append(_safe_str(v))
            elif f == 12: genres.append(_safe_str(v))
            elif f == 21: vod["vod_content"] = _safe_str(v)
            elif f == 22: vod["vod_remarks"] = _safe_str(v)
            elif f == 28: vod["vod_area"] = _safe_str(v)
            elif f == 30: vod["vod_year"] = _safe_str(v)
            elif f == 75 and w == 2:
                src = pb_decode(v)
                src_name = ""
                eps = []
                for sf, sw, sv in src:
                    if sf == 1 and sw == 2:
                        src_name = _safe_str(sv)
                    elif sf == 2 and sw == 2 and len(sv) > 10:
                        ep = pb_decode(sv)
                        ep_idx = next((x for ef, ew, x in ep if ef == 1 and ew == 0), None)
                        ep_url = next((x for ef, ew, x in ep if ef == 3 and ew == 2), b"")
                        ep_name = next((x for ef, ew, x in ep if ef == 4 and ew == 2), None)
                        if ep_url:
                            url = _safe_str(ep_url)
                            nm = _safe_str(ep_name) if ep_name else (f"第{ep_idx}集" if ep_idx is not None else "")
                            eps.append((nm, url))
                if eps:
                    sources.append((src_name, eps))
        vod["vod_actor"] = "、".join(actors[:12])
        vod["vod_director"] = "、".join(directors)
        vod["type_name"] = "/".join([g for g in genres if g][:4])
        # 剧集线路选择:
        #   明文 http 直链 (m3u8/官网) → 直接可播
        #   密文 (xfy-/CO4K_/NBY-/qsvip-/qingshan-/JP-/rose_) → playerContent 调解析接口换直链
        flags = []
        seen = set()
        for src_name, eps in sources:
            keep = []
            for nm, url in eps:
                if url.startswith("http"):
                    keep.append((nm, url))          # 直链/网页
                elif _cipher_prefix(url):
                    keep.append((nm, url))          # 密文, 播放时解析
            if not keep:
                continue
            fname = LINE_NAMES.get(src_name, src_name)
            if fname in seen: fname += "2"
            seen.add(fname)
            pairs = [f"{nm}${u}" for nm, u in keep]
            flags.append((fname, "#".join(pairs)))
        if not flags:
            return {"list": [vod]}
        vod["vod_play_from"] = "$$$".join(f for f, _ in flags)
        vod["vod_play_url"] = "$$$".join(u for _, u in flags)
        return {"list": [vod]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=None, pg=None):
        """TVBox 兼容签名: 1参/2参/3参调用全支持 (部分内核传 pg 翻页参数)"""
        c = _get(None)
        if not key or not str(key).strip():
            return {}
        key = str(key).strip()
        try:
            page = int(pg) if pg else 1
        except (ValueError, TypeError):
            page = 1
        # 结果缓存 10 分钟 (逐字连搜/重复搜索直接命中)
        ckey = f"{key}|{page}"
        cached = _search_cache.get(ckey)
        if cached and time.time() - cached[0] < 600:
            return cached[1]
        # 服务器令牌桶限流由 GuluClient.api 内 m=61 全局节流兜底 (2.8s/次);
        # 撞桶 (如APP端同IP也搜过) 时单次长退避 5.5s 补足令牌, 不再多试以免前端超时
        sort = pb_var(1, 1) + pb_var(2, 0) + pb_str(3, "vod_hits_week")
        body = pb_str(1, key) + pb_var(2, page) + pb_bytes(5, sort)
        r = c.api(3, 61, body)
        payload = (r or {}).get("payload") or b""
        if len(payload) < 200:
            time.sleep(5.5)
            r = c.api(3, 61, body)
            payload = (r or {}).get("payload") or b""
        if len(payload) < 200:
            return {}
        lst = _vod_list_from_payload(payload)
        items = [self._item_to_home(d) for d in lst if d.get("name")]
        result = {"list": items, "page": page, "pagecount": page + 1 if len(items) >= 20 else page,
                  "limit": max(len(items), 20), "total": len(items)}
        if items:
            if len(_search_cache) > 50:
                _search_cache.clear()
            _search_cache[ckey] = (time.time(), result)
        return result

    def searchContentPage(self, key, quick=None, pg=None):
        """部分 TVBox 内核用 searchContentPage 做分页搜索"""
        return self.searchContent(key, quick, pg)

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        """id 三种形态:
        1. http://...m3u8 / m.php — 明文直链, 直接播
        2. http://v.qq.com 等 — 官网页, 交给 TVBox 网页嗅探
        3. 密文 (xfy-/CO4K_/NBY-/qsvip-/qingshan-/JP-/rose_) — 调解析接口换直链
        """
        if not id:
            return {"parse": 0, "url": "", "header": {"User-Agent": UA}}
        if id.startswith("http"):
            is_stream = (".m3u8" in id) or ("m.php" in id)
            return {"parse": 0 if is_stream else 1,
                    "url": id, "header": {"User-Agent": UA}}
        # ---- 密文解析 ----
        cid = id
        # TVBox 可能对 %2B 解码成 + : CO4K/rose 密文服务器原始形态含 %2B, 需还原
        if cid.startswith(("CO4K_", "rose_")) and "+" in cid and "%2B" not in cid:
            cid = cid.replace(" ", "+")
            cid = urllib.parse.quote(cid, safe=":,_-")
        # 线路名优先路由 (xfyun/newxfyun 密文同为 xfy- 前缀但接口不同)
        api_name = (FLAG_API.get(flag)
                    or CIPHER_API.get(_cipher_prefix(cid)))
        c = _get(None)
        tmpl = (c.parse_apis.get(api_name) if c else None) or API_FALLBACK.get(api_name)
        if not tmpl:
            return {"parse": 0, "url": "", "header": {"User-Agent": UA}}
        for _attempt in range(2):
            try:
                api_url = tmpl + urllib.parse.quote(cid, safe="")
                req = urllib.request.Request(api_url)
                req.add_header("User-Agent", UA)
                with urllib.request.urlopen(req, timeout=20) as r:
                    txt = r.read(4096).decode("utf-8", errors="replace")
                got = ""
                try:
                    j = json.loads(txt)
                    got = (j.get("url") or "").strip()
                except Exception:
                    m = re.search(r'"url"\s*:\s*"([^"]+)"', txt)
                    got = m.group(1) if m else ""
                if got:
                    got = got.replace("\\/", "/")
                    # 新咕噜4K 返回的 m.php 本身就是 m3u8 播放列表
                    return {"parse": 0, "url": got,
                            "header": {"User-Agent": UA}}
            except Exception:
                pass
            time.sleep(0.6)
        return {"parse": 0, "url": "", "header": {"User-Agent": UA}}

    def localProxy(self, param):
        return {"list": [], "parse": 0, "url": ""}

    def liveContent(self, url):
        return {"list": []}


# ============ 自测 ============
if __name__ == "__main__":
    print("加密后端:", _BACKEND)
    sp = Spider()
    print("[1] homeContent:")
    home = sp.homeContent(True)
    print("    分类:", [c["type_name"] for c in home["class"]])
    print("    推荐数:", len(home["list"]))
    flt = home.get("filters", {})
    print(f"    筛选器: {len(flt)} 类, 电影维度:",
          [(d["name"], len(d["value"])) for d in flt.get("movie", [])])

    print("[2] 分类浏览 (m=66):")
    for tid, nm in (("movie", "电影"), ("tv", "电视剧"), ("us", "美剧"), ("short", "短剧")):
        cat = sp.categoryContent(tid, "1", False, {})
        first = cat["list"][0]["vod_name"] if cat["list"] else "-"
        print(f"    {nm}: {len(cat['list'])} 条, 首条 {first}")
        time.sleep(1.5)

    print("[3] 筛选:")
    for ext, lbl in (({"year": "2026"}, "电视剧+2026"),
                     ({"sort": "vod_score"}, "电影+评分排序")):
        cat = sp.categoryContent("tv" if "电视剧" in lbl else "movie", "1", False, ext)
        first = cat["list"][0]["vod_name"] if cat["list"] else "-"
        print(f"    {lbl}: {len(cat['list'])} 条, 首条 {first}")
        time.sleep(1.5)

    print("[4] 翻页:")
    cat = sp.categoryContent("movie", "2", False, {})
    print(f"    电影第2页: {len(cat['list'])} 条")

    _ctx = ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = ssl.CERT_NONE

    def _playable(url):
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", UA)
            with urllib.request.urlopen(req, timeout=12, context=_ctx) as rr:
                return rr.read(16).startswith(b"#EXTM3U")
        except Exception:
            return False

    if cat["list"]:
        vid = cat["list"][0]["vod_id"]
        print(f"[5] detailContent({vid}):")
        det = sp.detailContent([vid])
        v = det["list"][0]
        print("    片名:", v["vod_name"])
        routes = v.get("vod_play_from", "").split("$$$")
        print(f"    线路({len(routes)}):", " ".join(routes))

        print("[6] playerContent 全线路解析:")
        eps_groups = v.get("vod_play_url", "").split("$$$")
        n_ok = n_total = 0
        for ri, (rname, grp) in enumerate(zip(routes, eps_groups)):
            first = grp.split("#")[0]
            ep_name, _, ep_url = first.partition("$")
            if not ep_url:
                continue
            pc = sp.playerContent(rname, ep_url, [])
            got = pc.get("url", "")
            n_total += 1
            tag = ""
            if got:
                if _playable(got):
                    tag = "✅可播"; n_ok += 1
                elif pc.get("parse") == 1:
                    tag = "🌐网页"; n_ok += 1
                else:
                    tag = "⚠️直链未验证"; n_ok += 1
            else:
                tag = "❌解析失败"
            print(f"    {rname:<12} [{ep_name}] {got[:58]} {tag}")
            time.sleep(0.4)
        print(f"    => {n_ok}/{n_total} 线路可用")

    print("[7] 搜索三态调用 (TVBox 兼容核心):")
    se1 = sp.searchContent("凡人修仙传")                       # 1 参
    print(f"    1参: {len(se1.get('list', []))} 条")
    time.sleep(3)
    se2 = sp.searchContent("庆余年", False)                    # 2 参
    print(f"    2参: {len(se2.get('list', []))} 条")
    time.sleep(3)
    se3 = sp.searchContent("流浪地球", False, "1")             # 3 参 (电视实际形态)
    print(f"    3参: {len(se3.get('list', []))} 条")
    se4 = sp.searchContentPage("三体", False, "1")             # searchContentPage
    print(f"    Page别名: {len(se4.get('list', []))} 条")
    print("\n自测完成")
