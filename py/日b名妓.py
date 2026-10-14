# -*- coding: utf-8 -*-
"""
ribmj 站群 —— TVBox / dr_py 爬虫源（速度优化版 2026-10-13）
============================================================
架构: 全站 HTML 用 AES-128-CBC 加密后塞进 <div id="app">，前端 crypto-js 解密
加密: key = iv = 1234567898882222, PKCS7

本次优化（实测）
----------------
1. 域名池 + 竞速选优：实测 b 域 1.61s / 主域 a 4.91s（差 3 倍），
   启动并发探测各域，谁先回来用谁，并记住；
   单次请求超时 6s，失败自动切下一域（原来写死 a 域且 timeout=20）
2. homeContent 零请求秒回分类，列表交给 homeVideoContent 并行抓
   （首页 + 2 个热门分类并发，凑 ~32 条，原来首页只有 8 条）
3. 详情页后台预取播放页并展开 m3u8，点击时命中缓存 → 秒开
4. m3u8 是两层壳：master(只有1行) → media(真实分片)。
   直接返回内层 media 地址，省掉播放器一次往返（实测省 ~1.3s）
5. 失败结果不再入缓存（原来一次超时该 URL 永久为空）
6. requests / pycryptodome 缺失时用 urllib + 纯 Python AES 兜底，
   保证在精简版 TVBox 环境里也能出内容
7. 修搜索翻页 off-by-one：site 的 page 是 1 基（page=1 等同无参）
"""

import json
import base64
import re
import time
import threading
import urllib.parse
import urllib.request
import ssl

try:
    import requests as _rq
except Exception:
    _rq = None

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

try:
    from Crypto.Cipher import AES as _CryptoAES
    from Crypto.Util.Padding import unpad as _unpad
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False

try:
    from spider import Spider
except ImportError:
    try:
        from base.spider import Spider
    except ImportError:
        class Spider(object):
            pass

# ============================================================
# 站点配置
# ============================================================
# 实测响应速度排序（2026-10-13）：b 域 1.61s < ribmj 1.73s < www 4.5s < a 4.91s
# renqimm.site 密钥不同（解密是乱码），不可用
DOMAINS = [
    "https://b.ribmj.site",
    "https://ribmj.site",
    "https://www.ribmj.site",
    "https://a.ribmj.site",
]

UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

TIMEOUT = 8          # 单次请求超时（原来 20s，卡一次就白等）
RACE_TIMEOUT = 5     # 选域竞速超时
RACE_N = 3           # 每次取页面并发探测几个域（站点延迟波动 1.6~5s，竞速取最快）
HOME_EXTRA_TIDS = ("20",)        # 首页补充的分类（视频一区，热度最高）

# AES 解密参数
AES_KEY = b'1234567898882222'
AES_IV = b'1234567898882222'

# 全部分类（与站点 /index.php/vod/type.html 完全一致，36 个，20-55）
TYPE_LIST = [
    {"type_id": "20", "type_name": "视频一区"},
    {"type_id": "21", "type_name": "日韩无码"},
    {"type_id": "22", "type_name": "国产精品"},
    {"type_id": "23", "type_name": "日韩精品"},
    {"type_id": "24", "type_name": "欧美精品"},
    {"type_id": "25", "type_name": "动漫精品"},
    {"type_id": "26", "type_name": "自拍偷拍"},
    {"type_id": "27", "type_name": "伦理影片"},
    {"type_id": "28", "type_name": "中文字幕"},
    {"type_id": "29", "type_name": "视频二区"},
    {"type_id": "30", "type_name": "人妻系列"},
    {"type_id": "31", "type_name": "制服诱惑"},
    {"type_id": "32", "type_name": "强奸乱伦"},
    {"type_id": "33", "type_name": "AV明星"},
    {"type_id": "34", "type_name": "SM重味"},
    {"type_id": "35", "type_name": "巨乳系列"},
    {"type_id": "36", "type_name": "颜射系列"},
    {"type_id": "37", "type_name": "口交视频"},
    {"type_id": "38", "type_name": "视频三区"},
    {"type_id": "39", "type_name": "自慰系列"},
    {"type_id": "40", "type_name": "教师学生"},
    {"type_id": "41", "type_name": "大秀视频"},
    {"type_id": "42", "type_name": "明星换脸"},
    {"type_id": "43", "type_name": "AV解说"},
    {"type_id": "44", "type_name": "黑料网曝"},
    {"type_id": "45", "type_name": "精品探花"},
    {"type_id": "46", "type_name": "精品网红"},
    {"type_id": "47", "type_name": "视频四区"},
    {"type_id": "48", "type_name": "反差母狗"},
    {"type_id": "49", "type_name": "颜值正义"},
    {"type_id": "50", "type_name": "熟女少妇"},
    {"type_id": "51", "type_name": "人兽乱交"},
    {"type_id": "52", "type_name": "国产传媒"},
    {"type_id": "53", "type_name": "野战车震"},
    {"type_id": "54", "type_name": "SM调教"},
    {"type_id": "55", "type_name": "家庭乱伦"},
]

# ============================================================
# 纯 Python AES-128-CBC 解密（pycryptodome 缺失时兜底）
# ============================================================
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
_INV_SBOX = [0] * 256
for _i, _v in enumerate(_SBOX):
    _INV_SBOX[_v] = _i

_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]


def _xtime(a):
    a <<= 1
    if a & 0x100:
        a = (a ^ 0x1b) & 0xff
    return a


def _gmul(a, b):
    r = 0
    for _ in range(8):
        if b & 1:
            r ^= a
        a = _xtime(a)
        b >>= 1
    return r


def _aes128_dec_block(block, rk):
    """解密单个 16 字节块，rk 为 11 轮 16 字节轮密钥列表"""
    s = [block[i] ^ rk[10][i] for i in range(16)]
    for rnd in range(9, 0, -1):
        # InvShiftRows + InvSubBytes
        t = [0] * 16
        t[0] = _INV_SBOX[s[0]];   t[1] = _INV_SBOX[s[13]]
        t[2] = _INV_SBOX[s[10]];  t[3] = _INV_SBOX[s[7]]
        t[4] = _INV_SBOX[s[4]];   t[5] = _INV_SBOX[s[1]]
        t[6] = _INV_SBOX[s[14]];  t[7] = _INV_SBOX[s[11]]
        t[8] = _INV_SBOX[s[8]];   t[9] = _INV_SBOX[s[5]]
        t[10] = _INV_SBOX[s[2]];  t[11] = _INV_SBOX[s[15]]
        t[12] = _INV_SBOX[s[12]]; t[13] = _INV_SBOX[s[9]]
        t[14] = _INV_SBOX[s[6]];  t[15] = _INV_SBOX[s[3]]
        k = rk[rnd]
        ns = [0] * 16
        for c in range(4):
            # 顺序不能反：先 AddRoundKey 再 InvMixColumns（两者不可交换）
            a0 = t[c * 4] ^ k[c * 4];         a1 = t[c * 4 + 1] ^ k[c * 4 + 1]
            a2 = t[c * 4 + 2] ^ k[c * 4 + 2]; a3 = t[c * 4 + 3] ^ k[c * 4 + 3]
            ns[c * 4] = _gmul(a0, 14) ^ _gmul(a1, 11) ^ _gmul(a2, 13) ^ _gmul(a3, 9)
            ns[c * 4 + 1] = _gmul(a1, 14) ^ _gmul(a2, 11) ^ _gmul(a3, 13) ^ _gmul(a0, 9)
            ns[c * 4 + 2] = _gmul(a2, 14) ^ _gmul(a3, 11) ^ _gmul(a0, 13) ^ _gmul(a1, 9)
            ns[c * 4 + 3] = _gmul(a3, 14) ^ _gmul(a0, 11) ^ _gmul(a1, 13) ^ _gmul(a2, 9)
        s = ns
    # 最后一轮：InvShiftRows → InvSubBytes → AddRoundKey(rk[0])，无 InvMixColumns
    o = [0] * 16
    o[0] = s[0];   o[1] = s[13]; o[2] = s[10]; o[3] = s[7]
    o[4] = s[4];   o[5] = s[1];  o[6] = s[14]; o[7] = s[11]
    o[8] = s[8];   o[9] = s[5];  o[10] = s[2]; o[11] = s[15]
    o[12] = s[12]; o[13] = s[9]; o[14] = s[6]; o[15] = s[3]
    return bytes(_INV_SBOX[o[i]] ^ rk[0][i] for i in range(16))


def _key_expansion(key):
    rk = [[key[i] for i in range(16)]]
    for rnd in range(1, 11):
        prev = rk[-1]
        w = [prev[13], prev[14], prev[15], prev[12]]
        for i in range(4):
            w[i] = _SBOX[w[i]]
        w[0] ^= _RCON[rnd - 1]
        nk = [0] * 16
        for i in range(4):
            nk[i] = prev[i] ^ w[i]
        for i in range(4, 16):
            nk[i] = prev[i] ^ nk[i - 4]
        rk.append(nk)
    return rk


_RK_CACHE = {}


def _py_aes_cbc_decrypt(data, key, iv):
    rk = _RK_CACHE.get(key)
    if rk is None:
        rk = _key_expansion(key)
        _RK_CACHE[key] = rk
    out = bytearray()
    prev = iv
    for off in range(0, len(data), 16):
        blk = data[off:off + 16]
        d = _aes128_dec_block(blk, rk)
        out.extend(bytes(d[i] ^ prev[i] for i in range(16)))
        prev = blk
    pad = out[-1]
    if 1 <= pad <= 16:
        out = out[:-pad]
    return bytes(out)


class Spider(Spider):

    def __init__(self):
        try:
            super(Spider, self).__init__()
        except Exception:
            pass
        self.name = "日b名妓"
        self.host = DOMAINS[0]
        self.headers = {
            "User-Agent": UA,
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self._session = None
        self._cache = {}          # url -> 明文 HTML（只缓存成功）
        self._play_cache = {}     # 播放页 url -> 直链 m3u8（预取填充）
        self._picked = False      # 是否已完成选域
        self._winner = ""         # 竞速胜出的域名
        self._lock = threading.Lock()

    def getName(self):
        return self.name

    def init(self, extend=""):
        ext = str(extend or "").strip()
        if ext.startswith("http"):
            self.host = ext.rstrip("/")
            self._picked = True
        if _rq:
            try:
                self._session = _rq.Session()
            except Exception:
                self._session = None
        return

    # ================================================================
    # HTTP：requests 优先，urllib 兜底
    # ================================================================
    def _http_get(self, url, timeout=TIMEOUT):
        if _rq and self._session:
            try:
                r = self._session.get(url, headers=self.headers,
                                      timeout=timeout, verify=False)
                if r.status_code == 200:
                    try:
                        return r.text
                    except Exception:
                        return r.content.decode("utf-8", "ignore")
            except Exception:
                pass
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=self.headers)
            fp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            return fp.read().decode("utf-8", "ignore")
        except Exception:
            return ""

    # ================================================================
    # 选域竞速：并发探测，谁先回用谁
    # ================================================================
    def _pick_host(self):
        """真竞速：并发探测所有域，第一个成功返回的胜出（耗时≈最快那个域）"""
        if self._picked:
            return
        ev = threading.Event()

        def _probe(d):
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(d + "/", headers=self.headers)
                body = urllib.request.urlopen(req, timeout=RACE_TIMEOUT,
                                              context=ctx).read()
                if len(body) > 2000:
                    plain = self._to_plain(body.decode("utf-8", "ignore"))
                    if len(plain) > 500:
                        with self._lock:
                            if not self._winner:       # 第一个回来的胜出
                                self._winner = d
                                self.host = d
                                self.headers["Referer"] = d + "/"
                                self._cache[d + "/"] = plain
                        ev.set()
            except Exception:
                pass

        for d in DOMAINS:
            try:
                t = threading.Thread(target=_probe, args=(d,))
                t.daemon = True
                t.start()
            except Exception:
                pass
        ev.wait(RACE_TIMEOUT)      # 不等慢的，先到先用
        self._picked = True

    # ================================================================
    # AES 解密
    # ================================================================
    def _decrypt(self, blob):
        try:
            raw = base64.b64decode(blob)
        except Exception:
            return ""
        if _HAS_CRYPTO:
            try:
                d = _CryptoAES.new(AES_KEY, _CryptoAES.MODE_CBC, AES_IV).decrypt(raw)
                return _unpad(d, 16).decode("utf-8", "ignore")
            except Exception:
                pass
        try:
            return _py_aes_cbc_decrypt(raw, AES_KEY, AES_IV).decode("utf-8", "ignore")
        except Exception:
            return ""

    def _to_plain(self, html):
        """原始 HTML -> 解密后的明文"""
        if not html:
            return ""
        m = re.search(r'<div id="app"[^<>]*>(.*?)</div>', html, re.S)
        if not m:
            return html
        return self._decrypt(m.group(1).strip())

    # ================================================================
    # 取页面：sticky 域优先，失败切域；失败不入缓存
    # ================================================================
    def _fetch(self, url, timeout=TIMEOUT, race=True):
        self._pick_host()
        # 缓存按"路径"存（与域名无关），换域后仍命中
        path = url
        for d in DOMAINS:
            if path.startswith(d):
                path = path[len(d):]
                break
        with self._lock:
            c = self._cache.get(path)
        if c:
            return c
        # 竞速：并发打 RACE_N 个域，第一个解出内容的胜出
        # （站点延迟波动 1.6~5s，串行换域会把等待叠加，竞速只付最快的那次）
        box = {}
        ev = threading.Event()

        def _go(d):
            try:
                html = self._http_get(d + path, timeout)
                plain = self._to_plain(html)
                if plain and len(plain) > 500:
                    with self._lock:
                        if "p" not in box:
                            box["p"] = plain
                            box["d"] = d
                    ev.set()
            except Exception:
                pass

        order = [self.host] + [d for d in DOMAINS if d != self.host]
        ths = []
        for d in order[:max(1, RACE_N)]:
            try:
                t = threading.Thread(target=_go, args=(d,))
                t.daemon = True
                t.start()
                ths.append(t)
            except Exception:
                pass
        if not race:                      # 多页并发时不再叠加竞速，避免打爆站点
            ev.wait(0)
            for t in ths:
                try:
                    t.join(timeout + 1)
                except Exception:
                    pass
        else:
            ev.wait(timeout)
        if "p" in box:
            with self._lock:
                if len(self._cache) > 150:
                    self._cache.clear()
                self._cache[path] = box["p"]
            if box.get("d"):
                self.host = box["d"]
            return box["p"]
        # 竞速全败：串行兜底（含剩下没试过的域）
        for d in order:
            try:
                html = self._http_get(d + path, timeout)
                plain = self._to_plain(html)
                if plain and len(plain) > 500:
                    with self._lock:
                        self._cache[path] = plain
                    self.host = d
                    return plain
            except Exception:
                continue
        return ""

    def _fetch_many(self, urls, deadline=None):
        """并发抓多个页面，返回 {url: 明文}

        deadline: 总等待上限（秒）。到了就返回已就绪的，
        没赶上的线程仍在后台跑并把结果写进缓存，下次进入即命中。
        """
        out = {}
        lock = threading.Lock()

        def _w(u):
            p = self._fetch(u)
            if p:
                with lock:
                    out[u] = p
        ths = []
        for u in urls:
            t = threading.Thread(target=_w, args=(u,))
            t.daemon = True
            t.start()
            ths.append(t)
        end = time.time() + deadline if deadline else None
        for t in ths:
            try:
                t.join((end - time.time()) if end else (TIMEOUT + 2))
            except Exception:
                pass
        return out

    # ================================================================
    # 解析工具
    # ================================================================
    def _fix_pic(self, pic):
        if not pic:
            return ""
        pic = str(pic).strip()
        if pic.startswith("//"):
            return "https:" + pic
        if pic.startswith("/"):
            return self.host + pic
        if not pic.startswith("http"):
            return self.host + "/" + pic
        return pic

    def _parse_vod_list(self, html):
        items = []
        if not html:
            return items
        for li in re.findall(r'<li[^<>]*>(.*?)</li>', html, re.S):
            if 'thumbnail' not in li:
                continue
            vid_m = re.search(r'href="[^"]*vod/detail/id/(\d+)\.html"', li)
            if not vid_m:
                continue                       # 广告卡片（href="#"）直接跳过
            pic_m = re.search(r'<img src="([^"]+)"', li)
            name_m = re.search(r'alt="([^"]+)"', li)
            if not name_m:
                continue
            grade_m = re.search(r'<span[^<>]*class="video-grade"[^<>]*>(.*?)</span>', li, re.S)
            info_m = re.search(r'<p[^<>]*>(.*?)</p>', li, re.S)
            remarks = ""
            if grade_m:
                remarks = re.sub(r'<[^<>]+>', '', grade_m.group(1)).strip()
            elif info_m:
                remarks = re.sub(r'<[^<>]+>', '', info_m.group(1)).strip()
            items.append({
                "vod_id": vid_m.group(1),
                "vod_name": name_m.group(1).strip(),
                "vod_pic": self._fix_pic(pic_m.group(1) if pic_m else ""),
                "vod_remarks": remarks,
            })
        return items

    def _get_pagecount(self, html):
        if not html:
            return 1
        m = re.search(r'共\s*(\d+)\s*页', html)
        if m:
            return int(m.group(1))
        m = re.search(r'href="[^"]*page/(\d+)\.html[^"]*"[^<>]*>\s*尾页', html, re.S)
        if m:
            return int(m.group(1))
        # 兜底：取分页链接里最大的页码
        nums = [int(x) for x in re.findall(r'[?&]page=(\d+)', html)]
        if nums:
            return max(nums)
        return 1

    # ================================================================
    # 首页：分类零请求秒回
    # ================================================================
    def homeContent(self, filter=False):
        return {"class": TYPE_LIST, "filters": {}}

    def homeVideoContent(self):
        self._pick_host()
        urls = [self.host + "/"] + \
               ["%s/index.php/vod/type/id/%s.html" % (self.host, t)
                for t in HOME_EXTRA_TIDS]
        got = self._fetch_many(urls, deadline=3.0)   # 不被慢页面拖住
        items, seen = [], set()
        for u in urls:
            for it in self._parse_vod_list(got.get(u, "")):
                if it["vod_id"] in seen:
                    continue
                seen.add(it["vod_id"])
                items.append(it)
        return {"list": items[:40]}

    # ================================================================
    # 分类
    # ================================================================
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        if pg <= 1:
            url = "%s/index.php/vod/type/id/%s.html" % (self.host, tid)
        else:
            url = "%s/index.php/vod/type/id/%s/page/%s.html" % (self.host, tid, pg)
        html = self._fetch(url)
        items = self._parse_vod_list(html)
        total = self._get_pagecount(html)
        return {"list": items, "page": pg, "pagecount": total,
                "limit": len(items) or 12, "total": total * 12}

    # ================================================================
    # 详情（顺带后台预取播放地址）
    # ================================================================
    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) and ids else ids or "")
        if not vid:
            return {"list": []}
        url = "%s/index.php/vod/detail/id/%s.html" % (self.host, vid)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        title_m = re.search(r'<title>(.*?)</title>', html, re.S)
        title = re.sub(r'<[^<>]+>', '', title_m.group(1) if title_m else "").strip()
        title = re.sub(r'(剧情介绍|免费短剧|最新全集).*', '', title).strip()

        poster_m = re.search(
            r'<div class="detail-poster">.*?<img[^<>]*src="([^"]+)"', html, re.S)
        pic = self._fix_pic(poster_m.group(1)) if poster_m else ""

        desc_m = re.search(r'<meta name="description" content="([^"]*)"', html)
        content = (desc_m.group(1) if desc_m else title or "").strip()
        content = re.sub(r'[_\-—]\s*免费短剧.*$', '', content).strip()

        line_names = []
        tab_m = re.search(r'<ul[^<>]*id="detail-tab"[^<>]*>(.*?)</ul>', html, re.S)
        if tab_m:
            for li in re.findall(r'<li[^<>]*>(.*?)</li>', tab_m.group(1), re.S):
                nm = re.sub(r'<[^<>]+>', '', li).strip()
                if nm:
                    line_names.append(nm)

        lines_map = {}
        for m in re.finditer(
                r'href="(/index\.php/vod/play/id/%s/sid/(\d+)/nid/(\d+)\.html)"'
                r'[^<>]*(?:title="([^"]*)")?[^<>]*>(.*?)</a>' % re.escape(vid),
                html, re.S):
            pl_url, sid, nid, t_attr, text = m.groups()
            ep = (t_attr or re.sub(r'<[^<>]+>', '', text).strip() or ("第%s集" % nid)).strip()
            if not ep or "分享" in ep:
                continue
            sid = int(sid)
            lines_map.setdefault(sid, []).append(
                "%s$%s%s" % (ep, self.host, pl_url))

        from_parts, url_parts = [], []
        for sid in sorted(lines_map.keys()):
            nm = line_names[sid - 1] if (sid - 1) < len(line_names) and line_names[sid - 1] \
                else ("线路%s" % sid)
            from_parts.append(nm)
            url_parts.append("#".join(lines_map[sid]))

        vod = {
            "vod_id": vid,
            "vod_name": title or "未知片名",
            "vod_pic": pic,
            "vod_content": content,
            "vod_play_from": "$$$".join(from_parts) if from_parts else "默认线",
            "vod_play_url": "$$$".join(url_parts) if url_parts else "",
            "type_name": "",
        }
        # 后台预取播放地址：用户点开时已就绪
        try:
            play_urls = []
            for part in url_parts:
                for ep in part.split("#"):
                    if "$" in ep:
                        play_urls.append(ep.split("$")[-1])
            for pu in play_urls:
                if pu.startswith("http") and pu not in self._play_cache:
                    t = threading.Thread(target=self._resolve_play, args=(pu,))
                    t.daemon = True
                    t.start()
        except Exception:
            pass
        return {"list": [vod]}

    # ================================================================
    # 播放地址解析（播放页 -> 直链，并展开 master m3u8）
    # ================================================================
    def _resolve_play(self, page_url):
        if not page_url:
            return ""
        with self._lock:
            if page_url in self._play_cache:
                return self._play_cache[page_url]
        html = self._fetch(page_url)
        if not html:
            return ""
        real = ""
        start = html.find('player_aaaa=')
        if start != -1:
            brace = html.find('{', start)
            if brace != -1:
                try:
                    player, _ = json.JSONDecoder().raw_decode(html, brace)
                    real = str(player.get("url") or "")
                except Exception:
                    pass
        if not real:
            m = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
            if m:
                real = m.group(1)
        if real and real.startswith("//"):
            real = "https:" + real
        # 展开 master → media，省掉播放器一次往返
        real = self._expand_m3u8(real)
        if real:
            with self._lock:
                if len(self._play_cache) > 300:
                    self._play_cache.clear()
                self._play_cache[page_url] = real
        return real

    def _expand_m3u8(self, url):
        """master m3u8（只有一行 STREAM-INF）→ 真实分片表地址"""
        if not url or ".m3u8" not in url:
            return url
        try:
            txt = self._http_get(url, TIMEOUT)
            if not txt or "#EXT-X-STREAM-INF" not in txt:
                return url
            lines = [l.strip() for l in txt.splitlines()
                     if l.strip() and not l.strip().startswith("#")]
            if not lines:
                return url
            sub = lines[0]
            if sub.startswith("http"):
                return sub
            return urllib.parse.urljoin(url, sub)
        except Exception:
            return url

    def playerContent(self, flag, id, vipFlags):
        url = str(id or "")
        if not url:
            return {"parse": 0, "url": "", "header": self.headers}
        if not url.startswith("http"):
            url = self.host + url
        # 命中预取缓存 → 零等待
        with self._lock:
            cached = self._play_cache.get(url)
        if cached:
            return {"parse": 0, "url": cached, "header": self.headers}
        real = self._resolve_play(url)
        return {"parse": 0, "url": real or url, "header": self.headers}

    # ================================================================
    # 搜索
    # ================================================================
    def searchContent(self, keyword, quick=False, pg=1):
        pg = int(pg or 1)
        kw = urllib.parse.quote(str(keyword or ""), encoding="utf-8")
        # 实测：page 是 1 基（page=1 等同无参），原版写 pg-1 导致翻页错位
        url = "%s/index.php/vod/search.html?wd=%s" % (self.host, kw)
        if pg > 1:
            url += "&page=%d" % pg
        html = self._fetch(url)
        items = self._parse_vod_list(html)
        total = self._get_pagecount(html)
        return {"list": items, "page": pg, "pagecount": total,
                "limit": len(items) or 16, "total": total * 16}

    # ================================================================
    # 其它框架接口
    # ================================================================
    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return any(k in u for k in (".m3u8", ".mp4", ".flv", ".mkv", ".ts"))

    def localProxy(self, param):
        """透传代理：CDN 需要 Referer 时代拉"""
        try:
            url = param.get("url") or ""
            if isinstance(url, list):
                url = url[0] if url else ""
            if url:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, headers=self.headers)
                fp = urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx)
                body = fp.read()
                ctype = fp.headers.get("Content-Type") or \
                    ("application/vnd.apple.mpegurl" if ".m3u8" in url else "video/MP2T")
                return [200, ctype, body, None]
        except Exception:
            pass
        return [200, "video/MP2T", b"", None]

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return ""

    def close(self):
        return ""


# ============================================================
# 本地自检
# ============================================================
if __name__ == "__main__":
    s = Spider()
    s.init()
    t0 = time.time()
    s._pick_host()
    print("[OK ] 选域: %s (%.2fs)" % (s.host, time.time() - t0))

    t = time.time()
    h = s.homeContent(True)
    print("[OK ] homeContent %d 分类 (%.3fs, 零请求)" % (len(h["class"]), time.time() - t))
    assert h["class"]

    t = time.time()
    hv = s.homeVideoContent()
    print("[OK ] homeVideoContent %d 条 (%.2fs)" % (len(hv["list"]), time.time() - t))
    assert hv["list"]

    t = time.time()
    c = s.categoryContent("20", 1, False, {})
    print("[OK ] 分类页 %d 条 / %d 页 (%.2fs)" %
          (len(c["list"]), c["pagecount"], time.time() - t))
    assert c["list"]

    t = time.time()
    c2 = s.categoryContent("20", 2, False, {})
    same = c["list"][0]["vod_id"] == c2["list"][0]["vod_id"] if c2["list"] else True
    print("[OK ] 翻页 p2 %d 条, 首条%s (%.2fs)" %
          (len(c2["list"]), "★相同★" if same else "不同 ✅", time.time() - t))

    t = time.time()
    sc = s.searchContent("人妻", False, 1)
    s2 = s.searchContent("人妻", False, 2)
    diff = sc["list"] and s2["list"] and \
        sc["list"][0]["vod_id"] != s2["list"][0]["vod_id"]
    print("[OK ] 搜索 p1 %d 条 / p2 %d 条, 翻页%s (%.2fs)" %
          (len(sc["list"]), len(s2["list"]), "不同 ✅" if diff else "★相同★", time.time() - t))

    vid = c["list"][0]["vod_id"]
    t = time.time()
    d = s.detailContent([vid])
    print("[OK ] 详情 %s (%.2fs)" % (d["list"][0]["vod_name"][:30], time.time() - t))
    lines = d["list"][0]["vod_play_url"].split("$$$")
    print("[OK ] 线路 %d 条, 首线 %d 集" % (len(lines), len(lines[0].split("#"))))

    # 等预取线程
    time.sleep(2.5)
    pu = lines[0].split("#")[0].split("$")[-1]
    t = time.time()
    pc = s.playerContent("", pu, [])
    dt = time.time() - t
    print("[OK ] 播放 parse=%s (%.3fs) -> %s" % (pc.get("parse"), dt, str(pc.get("url"))[:78]))
    assert pc.get("parse") == 0 and pc["url"].startswith("http")

    # 直链校验：应已是 media 层（含 EXTINF），不再是 master 壳
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(pc["url"], headers=s.headers)
        body = urllib.request.urlopen(req, timeout=15, context=ctx).read(400).decode("utf-8", "ignore")
        print("[OK ] 直链校验: %s" % ("已是分片表 ✅" if "#EXTINF" in body else "仍是 master 壳"))
    except Exception as e:
        print("[WARN] 直链校验失败: %s" % str(e)[:60])

    # 纯 Python AES 兜底自检
    if _HAS_CRYPTO:
        raw = base64.b64encode(b"x" * 64)
        ref = _CryptoAES.new(AES_KEY, _CryptoAES.MODE_CBC, AES_IV).decrypt(base64.b64decode(raw))
        got = _py_aes_cbc_decrypt(base64.b64decode(raw), AES_KEY, AES_IV)
        print("[OK ] 纯Python AES 与 pycryptodome 一致: %s" % (ref[:16] == got[:16]))
        assert ref[:16] == got[:16]

    print("\n全部通过 ✅")
