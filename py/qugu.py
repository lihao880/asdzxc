# -*- coding: utf-8 -*-
# TVBox/影视仓 Python 爬虫 - 趣谷 qugu.py v2.0 (类式桥, 默影视真机约定)
# 2026-10-14 全链路 v2: b设备令牌链修复版
#
# 【v2 修复要点】(对照 v1 的三处致命伤)
#   1. b 设备令牌: POST /vc/api/device/isnew (无签名) 下发 b+newDeviceCode, 本地缓存,
#      playurl 遇 10401/10303 自动重注册一次
#   2. playurl 参数名纠错: version=2.8.0 (cl.n="version", v1 误发 cl=), ji=集真实id
#      (详情 playUrlList[].ji, v1 误用序号), isjiid=1&t=0&y=0
#   3. vuk 请求头: MD5(str(sid)+KEY) 必带 (r2/v.java)
#   新增详情接口: GET /cache/videos/{sid//100}/{sid}.json (AES-256-GCM, 已实测解密)
#   新增搜索格式: GET /vc/api/search/{关键词}/{页}.json?version=2.8.0 (明文)
#   KEY: qvn1u7polu8uaolplopoiuVH9oqDxih7 (libkeys.so getApiKey, 详情接口实测验证)
#   响应加密: Base64 → [12B IV][密文+16B tag], AES-256-GCM (r2/n.java), 纯标准库实现
#   基址: https://js.trgfd.cn (备用 ss.dcggffw.top); UA: QingmanLslandApp/1.0
# 学习用途
import os
import re
import sys
import json
import time
import gzip
import base64
import random
import hashlib
import urllib.parse
import urllib.request
import ssl

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider(object):
        pass

UA = 'QingmanLslandApp/1.0'
UA_LOGIN = 'MangaApp/1.0'
KEY = 'qvn1u7polu8uaolplopoiuVH9oqDxih7'
HOSTS = ['https://js.trgfd.cn', 'https://ss.dcggffw.top']
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
_REQ_CACHE = {}

RANKS = ['热播榜', '热搜榜', '飙升榜', '新片榜']
TYPES = ['大陆剧', '美剧', '韩剧', '英剧', '泰剧', '日剧', '台剧', '港剧',
         '电影', '国内综艺', '国外综艺', '国漫', '日漫', '少儿', '纪录片']

DECOY_MARK = '66.m3u8'


def _log(*args):
    try:
        sys.stderr.write('[趣谷] ' + ' '.join(str(a) for a in args) + '\n')
    except Exception:
        pass


# ---------- 纯标准库 AES-256-GCM 解密 ----------
_SBOX = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16]
_RCON = [0x01000000,0x02000000,0x04000000,0x08000000,0x10000000,0x20000000,0x40000000]


def _xtime(a):
    a <<= 1
    if a & 0x100:
        a ^= 0x11b
    return a & 0xff


def _aes256_expand(key):
    words = [int.from_bytes(key[i * 4:i * 4 + 4], 'big') for i in range(8)]
    for i in range(8, 60):
        t = words[i - 1]
        if i % 8 == 0:
            t = ((t << 8) | (t >> 24)) & 0xffffffff  # RotWord (先拼接后截断)
            t = (_SBOX[(t >> 24) & 0xff] << 24) | (_SBOX[(t >> 16) & 0xff] << 16) \
                | (_SBOX[(t >> 8) & 0xff] << 8) | _SBOX[t & 0xff]
            t ^= _RCON[i // 8 - 1]
        elif i % 8 == 4:
            t = (_SBOX[(t >> 24) & 0xff] << 24) | (_SBOX[(t >> 16) & 0xff] << 16) \
                | (_SBOX[(t >> 8) & 0xff] << 8) | _SBOX[t & 0xff]
        words.append(words[i - 8] ^ t)
    return words


def _aes256_encrypt_block(words, block):
    s = [block[i] for i in range(16)]
    # initial round key
    for i in range(16):
        s[i] ^= (words[i // 4] >> (24 - (i % 4) * 8)) & 0xff
    for rnd in range(13):
        s = [_SBOX[b] for b in s]
        # ShiftRows
        t = s[:]
        for r in range(1, 4):
            for c in range(4):
                s[r + 4 * c] = t[r + 4 * ((c + r) % 4)]
        # MixColumns
        for c in range(4):
            a = s[4 * c:4 * c + 4]
            x = a[0] ^ a[1] ^ a[2] ^ a[3]
            s[4 * c + 0] = a[0] ^ x ^ _xtime(a[0] ^ a[1])
            s[4 * c + 1] = a[1] ^ x ^ _xtime(a[1] ^ a[2])
            s[4 * c + 2] = a[2] ^ x ^ _xtime(a[2] ^ a[3])
            s[4 * c + 3] = a[3] ^ x ^ _xtime(a[3] ^ a[0])
        for i in range(16):
            s[i] ^= (words[4 * (rnd + 1) + i // 4] >> (24 - (i % 4) * 8)) & 0xff
    s = [_SBOX[b] for b in s]
    t = s[:]
    for r in range(1, 4):
        for c in range(4):
            s[r + 4 * c] = t[r + 4 * ((c + r) % 4)]
    for i in range(16):
        s[i] ^= (words[56 + i // 4] >> (24 - (i % 4) * 8)) & 0xff
    return bytes(s)


def _gf_mult(x, y):
    r = 0xe1000000000000000000000000000000
    z, v = 0, y
    for i in range(128):
        if (x >> (127 - i)) & 1:
            z ^= v
        if v & 1:
            v = (v >> 1) ^ r
        else:
            v >>= 1
    return z


def gcm_decrypt(key, b64):
    """Base64 → [12B IV][密文+16B tag] → 明文 str; 失败返回 None"""
    try:
        raw = base64.b64decode(b64.strip())
    except Exception:
        return None
    if len(raw) < 28:
        return None
    iv, ct, tag = raw[:12], raw[12:-16], raw[-16:]
    words = _aes256_expand(key)
    j0 = iv + b'\x00\x00\x00\x01'
    cb = int.from_bytes(j0, 'big')
    out = bytearray()
    for i in range(0, len(ct), 16):
        cb = (cb & ~0xffffffff) | ((cb + 1) & 0xffffffff)
        ks = _aes256_encrypt_block(words, cb.to_bytes(16, 'big'))
        blk = ct[i:i + 16]
        out.extend(bytes(a ^ b for a, b in zip(blk, ks)))
    # tag 校验 (失败仅告警, 不阻塞出数据)
    try:
        h = int.from_bytes(_aes256_encrypt_block(words, b'\x00' * 16), 'big')
        y = 0
        for i in range(0, len(ct), 16):
            blk = ct[i:i + 16]
            if len(blk) < 16:
                blk = blk + b'\x00' * (16 - len(blk))
            y = _gf_mult(y ^ int.from_bytes(blk, 'big'), h)
        lb = (0).to_bytes(8, 'big') + len(ct).to_bytes(8, 'big')
        y = _gf_mult(y ^ int.from_bytes(lb, 'big'), h)
        e = int.from_bytes(_aes256_encrypt_block(words, j0), 'big')
        if ((y ^ e).to_bytes(16, 'big')) != tag:
            _log('GCM tag 不匹配(仍输出明文)')
    except Exception as e:
        _log('tag计算异常', repr(e)[:60])
    return out.decode('utf-8', 'ignore')


# ---------- HTTP ----------
def _http(url, headers=None, data=None, method='GET', timeout=10, tries=2):
    h = {'User-Agent': UA, 'Accept': '*/*', 'Accept-Encoding': 'gzip'}
    if headers:
        h.update(headers)
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=h, method=method)
            resp = urllib.request.urlopen(req, timeout=timeout, context=_CTX)
            raw = resp.read()
            if raw[:2] == b'\x1f\x8b':
                raw = gzip.decompress(raw)
            return raw.decode('utf-8', 'ignore')
        except Exception as e:
            _log('%s失败(%d/%d)' % (method, attempt + 1, tries), url[:90], repr(e)[:70])
            time.sleep(0.3)
    return ''


def _cache_get(key):
    v = _REQ_CACHE.get(key)
    if v and v[0] > time.time():
        return v[1]
    if v:
        _REQ_CACHE.pop(key, None)
    return None


def _cache_set(key, val, ttl=300):
    if len(_REQ_CACHE) > 256:
        _REQ_CACHE.clear()
    _REQ_CACHE[key] = (time.time() + ttl, val)


def _get(url, ttl=300, headers=None):
    ck = 'G|' + url
    hit = _cache_get(ck)
    if hit is not None:
        return hit
    html = _http(url, headers=headers)
    _cache_set(ck, html, ttl if html else 60)
    return html


def _host():
    hit = _cache_get('HOST')
    if hit:
        return hit
    for hh in HOSTS:
        html = _http(hh + '/cache/filterOptions/filter.json', timeout=6, tries=1)
        if html:
            _cache_set('HOST', hh, 3600)
            return hh
    _cache_set('HOST', HOSTS[0], 600)
    return HOSTS[0]


# ---------- 设备令牌 (b) ----------
_DEV_FILE = None
def _dev_file():
    global _DEV_FILE
    if _DEV_FILE is None:
        try:
            _DEV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.qugu_dev.json')
        except Exception:
            _DEV_FILE = '.qugu_dev.json'
    return _DEV_FILE


def _isnew(force=False):
    """POST /vc/api/device/isnew → {b, newDeviceCode}; 429 等限流返回 None"""
    ck = 'DEV'
    if not force:
        hit = _cache_get(ck)
        if hit:
            return hit
        try:  # 本地持久化: 设备令牌跨进程复用, 免冷启动重注册
            with open(_dev_file(), 'r') as f:
                info = json.load(f)
            if info.get('b') and info.get('dev'):
                _cache_set(ck, info, 86400)
                return info
        except Exception:
            pass
    dev = ''.join(random.choices('0123456789abcdef', k=16))
    # 请求契约 = SplashActivity 原样 (jx_all/sources/SplashActivity.java:100-260)
    body = json.dumps({
        'packageName': 'com.quguvideo.app', 'baoming': 'com.quguvideo.app',
        'version': '2.8.0', 'channel': 'baidutuiguang',
        'uid': 0, 'userName': '', 'modelName': 'Xiaomi M2012K11AC',
        'isOld000': 0, 'deviceCode': dev, 'newDeviceCode': ''}).encode('utf-8')
    resp = _http(_host() + '/vc/api/device/isnew', data=body, method='POST', tries=1,
                 headers={'Content-Type': 'application/json'})
    if not resp:
        return None
    try:
        j = json.loads(resp)
    except Exception:
        pt = gcm_decrypt(KEY.encode(), resp)
        try:
            j = json.loads(pt) if pt else None
        except Exception:
            j = None
    if not isinstance(j, dict):
        _log('isnew 响应异常:', resp[:80])
        return None
    if j.get('code') not in (0, 200, None):
        _log('isnew code=', j.get('code'), str(j.get('message'))[:60])
        if j.get('code') == 429:
            _cache_set('DEV429', 1, 300)
        return None
    d = j.get('data') or {}
    b = str(d.get('b') or j.get('b') or '')
    ndc = str(d.get('newDeviceCode') or j.get('newDeviceCode') or dev)
    if not b:
        _log('isnew 无 b:', str(j)[:120])
        return None
    info = {'dev': dev, 'b': b, 'ndc': ndc}
    _cache_set(ck, info, 86400)
    try:  # 持久化设备令牌, 免冷启动重注册
        with open(_dev_file(), 'w') as f:
            json.dump(info, f)
    except Exception:
        pass
    return info


def _device():
    info = _isnew()
    if info:
        return info
    # 无 b 兜底: 空设备打一次(服务端可能直接拒, 但保持请求形态合法)
    return {'dev': 'b9a1f2c3d4e5f6a7', 'b': '', 'ndc': 'b9a1f2c3d4e5f6a7'}


# ---------- 数据装配 ----------
def _vod_from(it):
    vid = str(it.get('videoId') or '')
    name = it.get('videoName') or ''
    pic = it.get('fengmiantu') or ''
    total = it.get('total') or 0
    serial = it.get('serial') or 0
    nep = it.get('newchapter') or ''
    isend = it.get('isend')
    remarks = it.get('remarks') or ''
    if not remarks:
        if nep:
            remarks = nep
        elif isend == 1:
            remarks = '已完结'
        elif serial:
            remarks = '更新至%s' % serial
        elif total:
            remarks = '全%s集' % total
    score = it.get('score')
    if score:
        remarks = (remarks + ' ' if remarks else '') + ('%.1f' % score if isinstance(score, float) else str(score))
    return {
        "vod_id": vid, "vod_name": name, "vod_pic": pic,
        "vod_remarks": remarks,
        "vod_year": str(it.get('year') or ''),
        "vod_area": it.get('region') or '',
        "vod_actor": it.get('actor') or '',
        "vod_content": it.get('blurb') or it.get('shortBlurb') or '',
        "_total": total, "_serial": serial,
    }


def _parse_list(html):
    try:
        arr = json.loads(html)
    except Exception:
        return []
    if isinstance(arr, dict):
        arr = (arr.get('data') or {}).get('videos') or []
    vods, seen = [], set()
    for it in arr if isinstance(arr, list) else []:
        v = _vod_from(it)
        if not v['vod_id'] or v['vod_id'] in seen:
            continue
        seen.add(v['vod_id'])
        vods.append(v)
    return vods


def _list_url(rank, typ, pg):
    return '%s/cache/xinrank/%s/%s/%d.json' % (
        _host(), urllib.parse.quote(rank), urllib.parse.quote(typ), int(pg))


class Spider(_BaseSpider):

    def getName(self):
        return "趣谷"

    def init(self, extend=""):
        self.site = _host()
        self._total = {}

    def destroy(self):
        pass

    def homeContent(self, filter):
        classes = [{"type_id": t, "type_name": t} for t in TYPES]
        return {"class": classes,
                "filters": {t: [{"key": "rank", "name": "榜单",
                                 "value": [{"n": r, "v": r} for r in RANKS]}] for t in TYPES}}

    def homeVideoContent(self):
        vods = []
        for rank in RANKS[:2]:
            vods.extend(_parse_list(_get(_list_url(rank, '全部', 1), ttl=600)))
            if len(vods) >= 30:
                break
        return {"list": vods[:30]}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        rank = '热播榜'
        if isinstance(extend, dict):
            rank = extend.get('rank') or rank
        elif extend:
            rank = str(extend)
        if rank not in RANKS:
            rank = '热播榜'
        typ = tid if tid in TYPES else '全部'
        vods = _parse_list(_get(_list_url(rank, typ, pg)))
        for v in vods:
            self._total[v['vod_id']] = (v.get('_total'), v.get('_serial'))
        return {"list": vods, "page": pg,
                "pagecount": pg + 1 if len(vods) >= 10 else pg,
                "limit": 10, "total": 999999 if vods else 0}

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if not key:
            return {"list": [], "page": pg}
        url = '%s/vc/api/search/%s/%d.json?version=2.8.0' % (
            _host(), urllib.parse.quote(key), pg)
        vods = _parse_list(_get(url, ttl=180))
        for v in vods:
            self._total[v['vod_id']] = (v.get('_total'), v.get('_serial'))
        return {"list": vods, "page": pg}

    def detailContent(self, array):
        vid = str(array[0] if isinstance(array, list) else array)
        m = re.search(r'\d+', vid)
        if not m:
            return {"list": []}
        vid = m.group(0)
        url = '%s/cache/videos/%d/%s.json?baoming=com.quguvideo.app&version=2.8.0&channel=baidutuiguang' % (
            _host(), int(vid) // 100, vid)
        raw = _get(url, ttl=600)
        j = None
        if raw:
            try:
                j = json.loads(raw)
            except Exception:
                pt = gcm_decrypt(KEY.encode(), raw)
                if pt:
                    try:
                        j = json.loads(pt)
                    except Exception:
                        j = None
        eps = []
        vod = {"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_content": "",
               "vod_year": "", "vod_area": "", "vod_actor": "", "vod_remarks": ""}
        if isinstance(j, dict):
            pl = j.get('playUrlList') or []
            for i, e in enumerate(pl):
                nm = str(e.get('name') or (i + 1))
                eps.append(('第%s集' % nm.zfill(2), '%s-%s' % (vid, e.get('ji'))))
            vod.update({
                "vod_name": j.get('videoName') or '',
                "vod_pic": j.get('fengmiantu') or '',
                "vod_year": str(j.get('year') or ''),
                "vod_area": j.get('region') or '',
                "vod_actor": j.get('actor') or '',
                "vod_content": j.get('blurb') or j.get('shortBlurb') or '',
                "vod_remarks": j.get('remarks') or j.get('newchapter') or '',
            })
        if not eps:
            eps = [('第01集', '%s-1' % vid)]
        vod["vod_play_from"] = '趣谷'
        vod["vod_play_url"] = '#'.join('$'.join(x) for x in eps)
        return {"list": [vod]}

    def _playurl(self, sid, ji, info, ji_index=0):
        q = urllib.parse.urlencode({
            'sid': sid, 'ji': ji, 'jiIndex': ji_index, 't': '0', 'y': '0',
            'isjiid': '1', 'androidId': info['dev'], 'modelName': 'Xiaomi M2012K11AC',
            'newDeviceCode': info['ndc'], 'b': info['b'],
            'version': '2.8.0', 'baoming': 'com.quguvideo.app',
            'channel': 'baidutuiguang'})
        vuk = hashlib.md5((sid + KEY).encode()).hexdigest()
        raw = _http(_host() + '/vc/api/video/playurl?' + q,
                    headers={'vuk': vuk}, tries=1)
        if not raw:
            return None
        try:
            j = json.loads(raw)
        except Exception:
            pt = gcm_decrypt(KEY.encode(), raw)
            try:
                j = json.loads(pt) if pt else None
            except Exception:
                j = None
        return j if isinstance(j, dict) else None

    def playerContent(self, flag, id, vipFlags):
        pid = str(id or '')
        m = re.fullmatch(r'(\d+)-(\d+)', pid)
        header = {"User-Agent": UA}
        if not m:
            return {"parse": 0, "playUrl": "", "url": "", "header": header}
        sid, ji = m.group(1), m.group(2)
        info = _device()
        pj = self._playurl(sid, ji, info)
        code = (pj or {}).get('code')
        if code in (10401, 10303) or pj is None:
            # 设备记录失效/缺失 → 重注册一次再试
            info = _isnew(force=True) or info
            pj = self._playurl(sid, ji, info)
            code = (pj or {}).get('code')
        url = ((pj or {}).get('data') or {}).get('url') or ''
        if url and DECOY_MARK in url:
            _log('命中反爬诱饵(66.m3u8), code=', code)
        return {"parse": 0, "playUrl": "", "url": url, "header": header}


# 学习用途; 沙盒自检见 qugu2_chain.py / test_*.py
