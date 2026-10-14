#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 橘汁4k (橘汁追剧 v3.0.6.0) TVBox/默影视 桥接 Spider
# 协议逆向自 com.dasjkjfd.mgd v3.0.6.0
#   加密链: zone 握手(RSA一级公钥→二级公钥) → publicParams={"paramsData":AES-128-CBC(设备JSON)}
#           → 业务 body=SecureRequest{ 8位随机 + AES-256-ECB(safeCode, query+ts) }
#           → 响应 protobuf (ApiResult{code,msg,data})
#   paramsData 原生算法 (libBaseNativeJNI.so method01): AES-128-CBC(key="ed5fdsgucxumegqa", iv=key) + PKCS7 + hex
#   4K 线路置顶: 线路权重(DramaVideo field18)降序, 过滤 App 内核专线
# 兼容性: 有 pycryptodome 用 Crypto; 无则自动降级为内置纯标准库实现(Android py/默影视可用)
# 仅用于学习研究, 请于 24 小时内删除
import base64
import json
import random
import re
import time
import ssl
import urllib.request
import urllib.error
from urllib.parse import quote

try:
    import requests
except Exception:
    requests = None

try:
    from concurrent.futures import ThreadPoolExecutor
except Exception:
    ThreadPoolExecutor = None

try:
    from base.spider import Spider as _BaseSpider
    _HAVE_BASESPIDER = True
except Exception:
    _HAVE_BASESPIDER = False

    class _BaseSpider(object):
        """无 base.spider 时的兜底基类(带 urllib fetch)"""

        @staticmethod
        def _ssl_ctx():
            try:
                return ssl._create_unverified_context()
            except Exception:
                return None

        def fetch(self, url, headers=None, timeout=None, **kw):
            req = urllib.request.Request(url, headers=headers or {})
            ctx = self._ssl_ctx() if url.startswith('https') else None
            try:
                resp = urllib.request.urlopen(req, timeout=timeout or 15, context=ctx)
                return type('Resp', (), {
                    'content': resp.read(), 'text': '', 'status_code': resp.status,
                    'headers': dict(resp.headers)})()
            except urllib.error.HTTPError as e:
                return type('Resp', (), {
                    'content': e.read(), 'text': '', 'status_code': e.code,
                    'headers': dict(e.headers or {})})()

try:
    from Crypto.Cipher import AES, PKCS1_v1_5
    from Crypto.PublicKey import RSA
    from Crypto.Util.Padding import pad, unpad
    _HAVE_CRYPTO = True
except Exception:
    _HAVE_CRYPTO = False

    # ================= 纯标准库降级实现 (AES/RSA/DER) =================
    _SBOX = [
        0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
        0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
        0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
        0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
        0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
        0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
        0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
        0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
        0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
        0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
        0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
        0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
        0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
        0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
        0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
        0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
    ]
    _RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36, 0x6c, 0xd8, 0xab, 0x4d]
    _INV_SBOX = [0] * 256
    for _i, _v in enumerate(_SBOX):
        _INV_SBOX[_v] = _i

    def _xtime(a):
        a <<= 1
        return (a ^ 0x1b) & 0xff if a & 0x100 else a

    def _mul(a, b):
        p = 0
        for _ in range(8):
            if b & 1:
                p ^= a
            b >>= 1
            a = _xtime(a)
        return p

    class _PureAES:
        def __init__(self, key):
            nk = len(key) // 4
            if nk not in (4, 6, 8):
                raise ValueError('key size')
            self._nr = nk + 6
            self._rk = self._expand(key, nk)

        def _expand(self, key, nk):
            nr = self._nr
            words = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
            for i in range(nk, 4 * (nr + 1)):
                t = list(words[i - 1])
                if i % nk == 0:
                    t = t[1:] + t[:1]
                    t = [_SBOX[b] for b in t]
                    t[0] ^= _RCON[i // nk - 1]
                elif nk > 6 and i % nk == 4:
                    t = [_SBOX[b] for b in t]
                words.append([words[i - nk][j] ^ t[j] for j in range(4)])
            return words

        def _add_round(self, state, rnd):
            for c in range(4):
                for r in range(4):
                    state[r][c] ^= self._rk[rnd * 4 + c][r]

        def _sub_shift(self, state):
            for r in range(4):
                row = [state[r][(c + r) % 4] for c in range(4)]
                state[r] = [_SBOX[b] for b in row]

        def _mix_col(self, state, c):
            a = [state[r][c] for r in range(4)]
            state[0][c] = _mul(a[0], 2) ^ _mul(a[1], 3) ^ a[2] ^ a[3]
            state[1][c] = a[0] ^ _mul(a[1], 2) ^ _mul(a[2], 3) ^ a[3]
            state[2][c] = a[0] ^ a[1] ^ _mul(a[2], 2) ^ _mul(a[3], 3)
            state[3][c] = _mul(a[0], 3) ^ a[1] ^ a[2] ^ _mul(a[3], 2)

        def encrypt_block(self, block):
            state = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
            self._add_round(state, 0)
            for rnd in range(1, self._nr):
                self._sub_shift(state)
                for c in range(4):
                    self._mix_col(state, c)
                self._add_round(state, rnd)
            self._sub_shift(state)
            self._add_round(state, self._nr)
            return bytes(state[r][c] for c in range(4) for r in range(4))

        def _inv_sub_shift(self, state):
            for r in range(4):
                row = [state[r][(c - r) % 4] for c in range(4)]
                state[r] = [_INV_SBOX[b] for b in row]

        def _inv_mix_col(self, state, c):
            a = [state[r][c] for r in range(4)]
            state[0][c] = _mul(a[0], 14) ^ _mul(a[1], 11) ^ _mul(a[2], 13) ^ _mul(a[3], 9)
            state[1][c] = _mul(a[0], 9) ^ _mul(a[1], 14) ^ _mul(a[2], 11) ^ _mul(a[3], 13)
            state[2][c] = _mul(a[0], 13) ^ _mul(a[1], 9) ^ _mul(a[2], 14) ^ _mul(a[3], 11)
            state[3][c] = _mul(a[0], 11) ^ _mul(a[1], 13) ^ _mul(a[2], 9) ^ _mul(a[3], 14)

        def decrypt_block(self, block):
            state = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
            self._add_round(state, self._nr)
            for rnd in range(self._nr - 1, 0, -1):
                self._inv_sub_shift(state)
                self._add_round(state, rnd)
                for c in range(4):
                    self._inv_mix_col(state, c)
            self._inv_sub_shift(state)
            self._add_round(state, 0)
            return bytes(state[r][c] for c in range(4) for r in range(4))

    def _pkcs7_pad(data):
        n = 16 - len(data) % 16
        return data + bytes([n]) * n

    def _pkcs7_unpad(data):
        n = data[-1]
        if not 1 <= n <= 16 or data[-n:] != bytes([n]) * n:
            raise ValueError('bad pad')
        return data[:-n]

    def _pure_ecb_enc(key, data):
        aes = _PureAES(key)
        data = _pkcs7_pad(data)
        return b''.join(aes.encrypt_block(data[i:i + 16])
                        for i in range(0, len(data), 16))

    def _pure_ecb_dec(key, ct):
        aes = _PureAES(key)
        out = b''.join(aes.decrypt_block(ct[i:i + 16])
                       for i in range(0, len(ct), 16))
        return _pkcs7_unpad(out)

    def _pure_cbc_enc(key, iv, data):
        aes = _PureAES(key)
        data = _pkcs7_pad(data)
        out, prev = b'', iv
        for i in range(0, len(data), 16):
            blk = bytes(a ^ b for a, b in zip(data[i:i + 16], prev))
            prev = aes.encrypt_block(blk)
            out += prev
        return out

    def _der_read(data, off):
        tag = data[off]
        off += 1
        ln = data[off]
        off += 1
        if ln & 0x80:
            nbytes = ln & 0x7f
            ln = int.from_bytes(data[off:off + nbytes], 'big')
            off += nbytes
        return tag, data[off:off + ln], off + ln

    def _parse_pub_der(der):
        """X509 SubjectPublicKeyInfo (DER) → (n, e)"""
        _, spki, _ = _der_read(der, 0)
        _, _, off = _der_read(spki, 0)
        tag, bits, _ = _der_read(spki, off)
        if tag != 0x03:
            raise ValueError('not bitstring')
        inner = bits[1:]
        _, rsakey, _ = _der_read(inner, 0)
        _, n_b, off = _der_read(rsakey, 0)
        _, e_b, _ = _der_read(rsakey, off)
        n = int.from_bytes(n_b[1:] if n_b[0] == 0 else n_b, 'big')
        e = int.from_bytes(e_b, 'big')
        return n, e

    def _pure_rsa_enc(n, e, msg):
        """PKCS#1 v1.5 加密"""
        import os
        k = (n.bit_length() + 7) // 8
        ps = b''
        while len(ps) < k - 3 - len(msg):
            b = os.urandom(1)
            if b != b'\x00':
                ps += b
        em = b'\x00\x02' + ps + b'\x00' + msg
        return pow(int.from_bytes(em, 'big'), e, n).to_bytes(k, 'big')

# ================= 加密封装 (双路径统一入口) =================
if _HAVE_CRYPTO:
    def _aes_ecb_enc(key, pt):
        return AES.new(key, AES.MODE_ECB).encrypt(pad(pt, 16))

    def _aes_ecb_dec(key, ct):
        return unpad(AES.new(key, AES.MODE_ECB).decrypt(ct), 16)

    def _aes_cbc_enc(key, iv, pt):
        return AES.new(key, AES.MODE_CBC, iv=iv).encrypt(pad(pt, 16))

    def _import_pub(der):
        return RSA.import_key(der)

    def _rsa_enc(pub, msg):
        return PKCS1_v1_5.new(pub).encrypt(msg)
else:
    def _aes_ecb_enc(key, pt):
        return _pure_ecb_enc(key, pt)

    def _aes_ecb_dec(key, ct):
        return _pure_ecb_dec(key, ct)

    def _aes_cbc_enc(key, iv, pt):
        return _pure_cbc_enc(key, iv, pt)

    def _import_pub(der):
        return _parse_pub_der(der)

    def _rsa_enc(pub, msg):
        n, e = pub
        return _pure_rsa_enc(n, e, msg)

# ================= 逆向配置常量 (全部实锤) =================
PASSWORD = 'AWSS@E' + 'AAA112' + 'U*Yjgt' + 'UITB)F' + 'Md1khdaF'  # 32B 主 AES 钥
SAFE_PW = '11GK2w' + 'e32144' + 'LO&hil' + 'UITB)F' + 'Md1khdaF'   # safeCode 钥
PDATA_KEY = b'ed5fdsgucxumegqa'                                    # native method01 key(=iv)
SAFE_SECRET_KEY = 'OC1A06E197EF10CF3F6058CA7A803B5E'               # sig2/sig3 钥
PKG = 'com.dasjkjfd.mgd'
V_APP, V_NAME = 3060, '3.0.6.0'
MD5_CERT = '3A4A23871C21D1F00D75C58AB5F688F8'
SHA1_CERT = '8F2E5859B53F5F488F7021A07B7EFA62EB8FEDBD'
FAKE_POS = 1
BASE = 'https://juziapp.hzhcbkj.cn'
_PUB_ENC = ('IZqqsqXdVNmR9N/QzBr3mYxNdgMF8R3xj5y9zlyRPDcUO5k9dxnY3OXSxX1vRvH6'
            'mMTeOA7JFlkPA1I+ZlfEzLA5xknBP4AvUs3R4hQ6axvJIUief0sx4TR/3cxHlZdGH'
            'UHKX/ISqzuRP97T271Eu10FL6cFzAvxt28Rw5DIZ0si5X3GlPjiI68JwMlSi5f7bs'
            '8htWQlzatRhhu7wnclQW5+gMiZmw/ydRaaw5eotXkQdIGiXUY6Y6g60Qapw8Rdq25'
            'fIIK4SS6kwJJYk20e83zTLafR9GOAK27EpY74G/Y=')

UA = ('Mozilla/5.0 (Linux; Android 13; M2012K11AC Build/TKQ1.220829.002; wv) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.0.0 Mobile Safari/537.36')
CH = '1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

CATS = [('电影', '20'), ('电视剧', '21'), ('综艺', '22'),
        ('动漫', '23'), ('短剧', '24'), ('直播', '25'), ('漫剧', '26')]


def _b64d(s):
    return base64.b64decode(s)


def _b64e(b):
    return base64.b64encode(b).decode()


def _rand_str(n):
    """App 内部算法: 从字符表取 n-1 个互不重复字符 + '='"""
    pool = list(CH)
    random.shuffle(pool)
    return ''.join(pool[:n - 1]) + '='


def _uri_encode(s):
    """Android Uri.encode 语义"""
    return quote(str(s), safe="-_.!~*'()")


# ================= protobuf =================
def _pb_varint(n):
    out = b''
    while True:
        b = n & 0x7f
        n >>= 7
        out += bytes([b | 0x80]) if n else bytes([b])
        if not n:
            return out


def _pb_enc(fields):
    """fields: [(num, wire, value)]"""
    out = b''
    for num, wire, val in sorted(fields):
        out += _pb_varint(num << 3 | wire)
        if wire == 0:
            out += _pb_varint(val)
        else:
            if isinstance(val, str):
                val = val.encode()
            out += _pb_varint(len(val)) + val
    return out


def _pb_parse(data):
    """→ [(num, wire, value)] 保留重复字段"""
    out, i = [], 0
    n = len(data)
    while i < n:
        key = 0
        shift = 0
        while True:
            b = data[i]
            i += 1
            key |= (b & 0x7f) << shift
            shift += 7
            if not b & 0x80:
                break
        num, wire = key >> 3, key & 7
        if wire == 0:
            v = 0
            shift = 0
            while True:
                b = data[i]
                i += 1
                v |= (b & 0x7f) << shift
                shift += 7
                if not b & 0x80:
                    break
            out.append((num, 0, v))
        elif wire == 2:
            ln = 0
            shift = 0
            while True:
                b = data[i]
                i += 1
                ln |= (b & 0x7f) << shift
                shift += 7
                if not b & 0x80:
                    break
            out.append((num, 2, data[i:i + ln]))
            i += ln
        else:
            raise ValueError('wire=%d' % wire)
    return out


def _f2s(v):
    return v.decode('utf-8', 'replace') if isinstance(v, bytes) else str(v)


def _sub_map(msg):
    """bytes 消息 → {num: 最后一个值}"""
    m = {}
    for num, wire, val in _pb_parse(msg):
        m[num] = val
    return m


# ================= HTTP 适配层 (requests 优先, urllib 每请求新连接兜底) =================
class _Resp:
    def __init__(self, content, status):
        self.content = content
        self.status_code = status


class _Http:
    """真机壳环境无 requests 时走 urllib; 有 requests 走 Session"""

    def __init__(self, ua):
        self._ua = ua
        self._cookies = {}
        if requests is not None:
            try:
                self._s = requests.Session()
                self._s.headers.update({'User-Agent': ua})
                return
            except Exception:
                pass
        self._s = None

    @staticmethod
    def _ctx():
        try:
            return ssl._create_unverified_context()
        except Exception:
            return None

    def post(self, url, data=None, headers=None, timeout=15):
        hdrs = {'User-Agent': self._ua}
        if headers:
            hdrs.update(headers)
        if self._s is not None:
            r = self._s.post(url, data=data, headers=hdrs, timeout=timeout)
            return r
        req = urllib.request.Request(url, data=data, headers=hdrs, method='POST')
        if self._cookies:
            req.add_header('Cookie', '; '.join('%s=%s' % kv for kv in self._cookies.items()))
        try:
            resp = urllib.request.urlopen(req, timeout=timeout, context=self._ctx())
        except urllib.error.HTTPError as e:
            return _Resp(e.read(), e.code)
        for sc in resp.headers.get_all('Set-Cookie') or []:
            try:
                kv = sc.split(';', 1)[0]
                if '=' in kv:
                    k, v = kv.split('=', 1)
                    self._cookies[k.strip()] = v.strip()
            except Exception:
                pass
        return _Resp(resp.read(), resp.status)


# ================= 客户端 =================
class _Client:
    def __init__(self):
        self.s = _Http(UA)
        self.second_pub = None
        self.safe_code = None
        self._udid = ''.join(random.choices('0123456789abcdef', k=32))
        self._aid = ''.join(random.choices('0123456789abcdef', k=16))
        self._first_pub = None
        self._ok = False
        self.last_err = ''

    # ---- safeCode: 双b64(AES(SAFE_PW, 证书串)) 取首尾16大写 ----
    def _build_safe_code(self):
        content = (MD5_CERT + '######' + SHA1_CERT + '~~~~~~' + PKG
                   + '>>>+++' + str(V_APP))
        inner = _b64e(_aes_ecb_enc(SAFE_PW.encode(), content.encode()))
        outer = _b64e(inner.encode())
        self.safe_code = outer[:16].upper() + outer[-16:].upper()

    # ---- publicParams: {"paramsData": hex(AES-CBC(设备JSON含sig))} ----
    def _public_params(self):
        m = {
            'plat': 'android', 'v': '1', 'vOs': '13', '_vOsCode': '33',
            'vApp': str(V_APP), 'vName': V_NAME, 'pkg': PKG, 'appName': '橘汁',
            'mac': '02:00:00:00:00:00', 'model': 'M2012K11AC', 'brand': 'Redmi',
            'facturer': 'Xiaomi', 'udid': self._udid, 'uuid': self._udid,
            'chid': '10000', 'androidID': self._aid,
            'resolution': '2400x1080', 'density': '2.75', 'dpi': '440',
            'net': 'wifi', 'carrier': 'CMCC', 'cpu': 'arm64-v8a',
            'abid': '', 'cpuId': '', 'device': '1',
            'lang': 'zh', 'country': 'CN', 'tenantId': '',
        }
        m = {k: _uri_encode(v) for k, v in m.items()}
        if self.second_pub is not None:
            ts = int(time.time() * 1000)
            rnd16 = _rand_str(16)
            sig = _b64e(_rsa_enc(
                self.second_pub, (str(ts) + rnd16 + str(V_APP)).encode()))
            aes_sign = _b64e(_aes_ecb_enc(
                SAFE_SECRET_KEY.encode(), (str(ts) + rnd16).encode()))
            m.update({'timestamp': ts, 'random_str': rnd16,
                      'sig': sig, 'sig2': aes_sign[:8], 'sig3': aes_sign[8:]})
        m['young'] = 0
        js = json.dumps(m, separators=(',', ':'), ensure_ascii=False)
        ct = _aes_cbc_enc(PDATA_KEY, PDATA_KEY, js.encode())
        return json.dumps({'paramsData': ct.hex()}, separators=(',', ':'))

    def _headers(self):
        return {'publicParams': self._public_params(),
                'Content-Type': 'application/x-protobuf',
                'Accept': 'application/x-protobuf',
                'Cache-Control': 'no-cache'}

    # ---- zone 握手 ----
    def _zone(self):
        ts = int(time.time() * 1000)
        r16 = _rand_str(16)
        body = _pb_enc([(1, 0, ts), (2, 2, _b64e(_rsa_enc(
            self._first_pub, (str(ts) + r16).encode()))),
            (3, 2, _rand_str(16)), (4, 2, r16), (5, 2, _rand_str(16))])
        r = self.s.post(BASE + '/api/v5/find/app/zone', data=body,
                        headers=self._headers(), timeout=15)
        api = _sub_map(r.content)
        if api.get(1, -1) != 200:
            raise RuntimeError('zone code=%s' % api.get(1))
        pub = _sub_map(api[3])
        # sFakePos=1 → 拼 str2+str3+str4+str5
        key_b64 = ''.join(_f2s(pub.get(i, b''))
                          for i in (2, 3, 4, 5) if pub.get(i))
        self.second_pub = _import_pub(_b64d(key_b64))

    def init(self):
        if self._ok:
            return True
        pub_b64 = _aes_ecb_dec(PASSWORD.encode(), _b64d(_PUB_ENC)).decode()
        self._first_pub = _import_pub(_b64d(pub_b64))
        self._build_safe_code()
        self._zone()
        self._ok = True
        return True

    def retry(self):
        self._ok = False
        return self.init()

    # ---- 业务请求: SecureRequest{ 8随机 + AES(safeCode, query+ts) } ----
    def call(self, path, params=None, retries=1):
        params = params or {}
        query = '&'.join('%s=%s' % (k, params[k]) for k in params)
        for attempt in range(retries + 1):
            try:
                self.init()
                ts = int(time.time() * 1000)
                r8 = _rand_str(8)
                full = r8 + _b64e(_aes_ecb_enc(
                    self.safe_code.encode(), (query + str(ts)).encode()))
                body = _pb_enc([(1, 2, full[:20]), (2, 2, full[20:]),
                                (3, 2, _rand_str(20)), (4, 0, ts), (5, 2, r8)])
                r = self.s.post(BASE + path, data=body,
                                headers=self._headers(), timeout=15)
                if r.status_code == 424:
                    raise RuntimeError('424')
                api = _sub_map(r.content)
                return api.get(1, -1), _f2s(api.get(2, b'')), api.get(3, b'')
            except Exception as e:
                self.last_err = repr(e)[:100]
                if attempt >= retries:
                    return -1, '请求失败:' + self.last_err, b''
                try:
                    self.retry()
                except Exception:
                    pass


# ================= Spider =================
_client = None
_detail_cache = {}
_probe_cache = {}  # vid → (过期ts, ok_names, play_groups) 二次进详情免探测
PROBE_TTL = 600


def _get_client():
    global _client
    if _client is None:
        _client = _Client()
    return _client


_IP_PIC_RE = re.compile(r'^http://(\d{1,3}\.){3}\d{1,3}')


def _fix_pic(u):
    """http:// 封面升级 https(Android 9+ 默认禁明文图); IP:端口型保留"""
    if not u:
        return ''
    u = u.strip()
    if u.startswith('http://') and not _IP_PIC_RE.match(u):
        return 'https://' + u[7:]
    return u


def _drama_list(data):
    """data proto → [drama dict] + total"""
    out, total = [], 0
    try:
        for num, wire, val in _pb_parse(data):
            if num == 1 and wire == 2:
                f = _sub_map(val)
                pics = []
                if f.get(2):
                    for pn, pw, pv in _pb_parse(f[2]):
                        if pw == 2:
                            pics.append(_f2s(pv))
                out.append({
                    'id': f.get(3, 0),
                    'title': _f2s(f.get(5, b'')),
                    'pic': _fix_pic(pics[0]) if pics else '',
                    'remark': _f2s(f.get(13, b'')),
                    'year': _f2s(f.get(14, b'')),
                    'area': _f2s(f.get(1, b'')),
                    'actors': _f2s(f.get(12, b'')),
                    'tag': _f2s(f.get(15, b'')),
                    'brief': _f2s(f.get(4, b'')),
                })
            elif num == 16 and wire == 0:
                total = val
    except Exception:
        pass
    return out, total


def _parse_detail(data):
    """getDetail data → (info dict, lines list)"""
    info = {'id': '', 'title': '', 'pic': '', 'year': '', 'area': '',
            'actors': '', 'brief': '', 'tag': '', 'remarks': ''}
    lines = {}
    order = []
    try:
        for num, wire, val in _pb_parse(data):
            if wire != 2:
                continue
            if num == 2:
                pics = [_f2s(pv) for pn, pw, pv in _pb_parse(val) if pw == 2]
                if pics:
                    info['pic'] = _fix_pic(pics[0])
            elif num == 29:
                e = _sub_map(val)
                frm = _f2s(e.get(9, b''))
                name = _f2s(e.get(10, b'')) or frm
                ep_name = _f2s(e.get(3, b''))
                token = _f2s(e.get(4, b''))
                weight = e.get(18, 0)
                if not frm or not token:
                    continue
                key = (frm, name)
                if key not in lines:
                    lines[key] = {'from': frm, 'name': name,
                                  'weight': weight, 'eps': []}
                    order.append(key)
                lines[key]['eps'].append((ep_name, token))
                lines[key]['weight'] = max(lines[key]['weight'], weight)
            else:
                if num == 4:
                    info['id'] = _f2s(val)
                elif num == 9:
                    info['title'] = _f2s(val)
                elif num == 6 and not info['brief']:
                    info['brief'] = _f2s(val)
                elif num == 7 and not info['brief']:
                    info['brief'] = _f2s(val)
                elif num == 18:
                    info['year'] = _f2s(val)
                elif num == 25:
                    info['actors'] = _f2s(val)
                elif num == 15:
                    info['tag'] = _f2s(val)
                elif num == 1 and not info['area']:
                    info['area'] = _f2s(val)
                elif num == 12 and not info['remarks']:
                    info['remarks'] = _f2s(val)
    except Exception:
        pass
    return info, [lines[k] for k in order]


_PROBE_RE = re.compile(r'^https?://', re.I)


def _url_ok(url):
    """直链可达性检测: Range 请求取 2 字节, 200/206 视为可播(踢掉死链)"""
    try:
        hdrs = {'Range': 'bytes=0-1', 'User-Agent': UA}
        if requests is not None:
            r = requests.get(url, headers=hdrs, timeout=(2, 4),
                             stream=True, verify=False)
            ok = r.status_code in (200, 206)
            try:
                r.close()
            except Exception:
                pass
            return ok
        req = urllib.request.Request(url, headers=hdrs)
        ctx = _BaseSpider._ssl_ctx() if url.startswith('https') else None
        resp = urllib.request.urlopen(req, timeout=4, context=ctx)
        try:
            resp.read(2)
        finally:
            resp.close()
        return True
    except Exception:
        return False


def _probe_line(cl, frm, token):
    """探测线路第1集: 返回真实且可达的 URL, 否则 None(App 专线/死链)"""
    try:
        code, msg, data = cl.call('/api/proto/v5/videoUsableUrl', {
            'vodPlayFrom': frm,
            'playUrl': quote(token, safe='-.*_'),
        })
        if code != 200 or not data:
            return None
        pu = _f2s(_sub_map(data).get(1, b''))
        if pu and pu != token and _PROBE_RE.match(pu) and _url_ok(pu):
            return pu
    except Exception:
        pass
    return None


def _ext_of(url):
    low = url.lower()
    for ext in ('.m3u8', '.mp4', '.flv', '.mkv'):
        if ext in low:
            return ext[1:]
    return ''


def _q_rank(name):
    """画质分级: 4K(2160) → 蓝光/臻彩/原盘 → 其他, 高画质线路置顶"""
    u = name.upper()
    if '4K' in u or '2160' in u:
        return 0
    if ('蓝光' in name or '臻彩' in name or '原盘' in name
            or 'BLURAY' in u or 'REMUX' in u or '1080' in u):
        return 1
    return 2


class Spider(_BaseSpider):
    def getName(self):
        return '橘汁4k'

    def init(self, extend=''):
        try:
            _get_client().init()
        except Exception:
            pass
        return ''

    def destroy(self):
        return ''

    def homeContent(self, filter):
        cats = [{'type_id': tid, 'type_name': name} for name, tid in CATS]
        return {'class': cats, 'filters': {}}

    def homeVideoContent(self):
        try:
            cl = _get_client()
            code, msg, data = cl.call('/api/proto/v5/drama/category',
                                      {'typeId1': '20', 'page': '1', 'pagesize': '8'})
            if code == 200:
                items, _ = _drama_list(data)
                if items:
                    it = items[0]
                    return {'vod_id': str(it['id']), 'vod_name': it['title'],
                            'vod_pic': it['pic'], 'vod_remarks': it['remark']}
        except Exception:
            pass
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        if str(tid) == 'diag':
            return self._diag()
        pg = int(pg) if str(pg).isdigit() else 1
        cl = _get_client()
        code, msg, data = cl.call('/api/proto/v5/drama/category', {
            'typeId1': str(tid), 'page': str(pg), 'pagesize': '20'})
        items, total = [], 0
        if code == 200:
            items, total = _drama_list(data)
        videos = [{'vod_id': str(it['id']), 'vod_name': it['title'],
                   'vod_pic': it['pic'], 'vod_remarks': it['remark']}
                  for it in items if it.get('id')]
        if not videos:
            # 失败原因直接显示在列表里, 不再静默空白
            err = (msg or ('code=%s' % code))[:80]
            videos = [{'vod_id': '0', 'vod_name': '⚠️加载失败:' + err,
                       'vod_pic': '', 'vod_remarks': '下拉刷新重试'}]
            total = 0
        pagecount = max(1, (total + 19) // 20) if total else pg + 1
        return {'list': videos, 'page': pg, 'pagecount': pagecount,
                'limit': 20, 'total': total}

    def _diag(self):
        """诊断页: 每一步执行状态直接显示在列表里, 手机端截图即可定位"""
        rows = []

        def add(k, v):
            rows.append({'vod_id': 'diag%d' % len(rows),
                         'vod_name': '%s = %s' % (k, v),
                         'vod_pic': '', 'vod_remarks': ''})

        import platform
        add('01.py版本', '20261003-diag')
        add('02.Python', platform.python_version())
        add('03.Crypto加密库', '有' if _HAVE_CRYPTO else '无→内置纯标准库')
        add('04.requests库', '有' if requests is not None else '无→urllib')
        add('05.base.spider', '有(壳桥接)' if _HAVE_BASESPIDER else '无(兜底)')
        add('06.线程池', '有' if ThreadPoolExecutor is not None else '无')

        cl = _Client()
        try:
            cl.init()
            add('07.zone握手', 'OK ' + (cl.safe_code or '')[:20])
        except Exception as e:
            add('07.zone握手', '失败: ' + repr(e)[:90])
        try:
            code, msg, data = cl.call('/api/proto/v5/drama/category',
                                      {'typeId1': '20', 'page': '1', 'pagesize': '5'})
            items, total = _drama_list(data) if code == 200 else ([], 0)
            if code == 200 and items:
                add('08.业务请求', 'OK 首条=%s 总数=%s' % (items[0]['title'], total))
            else:
                add('08.业务请求', '失败 code=%s msg=%s' % (code, (msg or '')[:60]))
        except Exception as e:
            add('08.业务请求', '异常: ' + repr(e)[:90])
        add('09.请求地址', BASE)
        if cl.last_err:
            add('10.最后错误', cl.last_err[:90])
        else:
            add('10.最后错误', '(无)')
        return {'list': rows, 'page': 1, 'pagecount': 1,
                'limit': 20, 'total': len(rows)}

    def detailContent(self, ids):
        cl = _get_client()
        vid = ids[0]
        cache = _detail_cache.get(vid)
        if not cache:
            code, msg, data = cl.call('/api/proto/v5/drama/getDetail', {'id': vid})
            if code != 200:
                return {'list': [{'vod_id': vid, 'vod_name': '获取失败:' + msg}]}
            info, lines = _parse_detail(data)
            _detail_cache.clear()
            _detail_cache[vid] = (info, lines)
            cache = (info, lines)
        info, lines = cache
        vod = {
            'vod_id': vid,
            'vod_name': info['title'],
            'vod_pic': info['pic'],
            'type_name': info['tag'].split(',')[0] if info['tag'] else '',
            'vod_year': info['year'],
            'vod_area': info['area'],
            'vod_actor': info['actors'],
            'vod_director': '',
            'vod_content': info['brief'],
            'vod_tag': info['tag'],
            'vod_remarks': info['remarks'],
        }

        # ---- 探测结果缓存命中则直接用(二次进详情秒开) ----
        pc = _probe_cache.get(vid)
        if pc and pc[0] > time.time():
            ok_names, play_groups = pc[1], pc[2]
        else:
            # ---- 线路: 画质分级(4K→蓝光→其他) → 权重降序 → 并发探测 ----
            ranked = sorted(lines, key=lambda ln: (_q_rank(ln['name']),
                                                   -ln['weight']))
            cand = [ln for ln in ranked if ln['eps']]
            if ThreadPoolExecutor is not None and len(cand) > 1:
                with ThreadPoolExecutor(max_workers=6) as pool:
                    probes = list(pool.map(
                        lambda ln: _probe_line(cl, ln['from'], ln['eps'][0][1]), cand))
            else:
                probes = [_probe_line(cl, ln['from'], ln['eps'][0][1])
                          for ln in cand]
            play_groups, ok_names = [], []
            for ln, real in zip(cand, probes):
                if not real:
                    continue
                ok_names.append('%s(%s)' % (ln['name'], ln['from']))
                parts = ['%s$%s' % (nm or '第1集', tok)
                         for nm, tok in ln['eps']]
                play_groups.append('#'.join(parts))
            _probe_cache[vid] = (time.time() + PROBE_TTL,
                                 ok_names, play_groups)
        if play_groups:
            vod['vod_play_from'] = '$$$'.join(ok_names)
            vod['vod_play_url'] = '$$$'.join(play_groups)
        else:
            vod['vod_play_from'] = '提示'
            vod['vod_play_url'] = '该内容仅限App内播放(专线)$'
        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags):
        cl = _get_client()
        frm = ''
        if flag:
            m = re.search(r'\(([^)]*)\)\s*$', flag)
            frm = m.group(1) if m else flag
        url = ''
        try:
            code, msg, data = cl.call('/api/proto/v5/videoUsableUrl', {
                'vodPlayFrom': frm,
                'playUrl': quote(id, safe='-.*_'),
            })
            if code == 200 and data:
                pu = _f2s(_sub_map(data).get(1, b''))
                if pu and pu != id and _PROBE_RE.match(pu):
                    url = pu
        except Exception:
            pass
        # videoUsableUrl 返回的均为可直接播放地址(m3u8/mp4直链, 可能无后缀)
        # 无后缀直链再走 parse=1 会被壳扔进网页解析池 → 必挂
        result = {'parse': '0' if url else '1', 'url': url, 'header': ''}
        return result

    def searchContent(self, key, quick, pg='1'):
        pg = str(pg or '1')
        cl = _get_client()
        code, msg, data = cl.call('/api/proto/v5/drama/search', {
            'searchKeys': key, 'page': pg, 'pagesize': '20'})
        items, total = [], 0
        if code == 200:
            items, total = _drama_list(data)
        videos = [{'vod_id': str(it['id']), 'vod_name': it['title'],
                   'vod_pic': it['pic'], 'vod_remarks': it['remark']}
                  for it in items if it.get('id')]
        if not videos and msg:
            videos = [{'vod_id': '0', 'vod_name': '⚠️搜索失败:' + msg[:80],
                       'vod_pic': '', 'vod_remarks': ''}]
        return {'list': videos, 'page': int(pg),
                'pagecount': max(1, (total + 19) // 20) if total else 1,
                'total': total}

    def playerAssistant(self, flag, id):
        return self.playerContent(flag, id, '')

    def localProxy(self, param):
        return ''


if __name__ == '__main__':
    sp = Spider()
    sp.init('')
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == 'search':
        print(json.dumps(sp.searchContent(sys.argv[2], False), ensure_ascii=False)[:600])
    elif len(sys.argv) > 2 and sys.argv[1] == 'detail':
        print(json.dumps(sp.detailContent([sys.argv[2]]), ensure_ascii=False)[:1500])
    else:
        home = sp.homeContent(False)
        print('分类:', [c['type_name'] for c in home['class']])
        cat = sp.categoryContent('21', 1, False, {})
        print('电视剧20条中的前3:', [v['vod_name'] for v in cat['list'][:3]])
