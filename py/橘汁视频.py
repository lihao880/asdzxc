# -*- coding: utf-8 -*-
# 橘汁视频 TVBox spider — 华谊同款协议栈移植
import json
import re
import sys
import time
import base64
import string
import random
import hashlib
import urllib.request
import urllib.parse
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5, AES
from Crypto.Util.Padding import pad, unpad

try:
    from base.spider import Spider as _Base
except Exception:
    class _Base:
        pass

PUB1_B64 = 'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCr8SzZhjYy+rsya1K09t8d2K50pWFoBkgUqMpKOiW+3IEVKd4eTdvg9RSOjQ82kypL6R9BnsmrS1V8s4PVDwjQbUtYhTPPC9Hz16qY7rpD6m0d2vr09/UpWQ5uOy9PR0QTrsioveZ+DIe9jc3C+zBCu/kZSY/R8stwJoiitki3gwIDAQAB'
NATIVE_K = b'ed5fdsgucxumegqa'
SAFE = b'OC1A06E197EF10CF3F6058CA7A803B5E'
PW_SAFE = b'11GK2we32144LO&hilUITB)FMd1khdaF'
CERT_MD5 = '090DA8F91D3F60CC6CB250D86F06FE12'
CERT_SHA1 = '3DADB42485B7F864E766479ADA6B1176D81D8D73'
PKG = 'com.mxj.wylcjbxyx'
VC = '3024'
HOST = 'https://juziapp.hzhcbkj.cn'
UA = 'okhttp/3.12.1'

_e = base64.b64encode(AES.new(PW_SAFE, AES.MODE_ECB).encrypt(pad(
    (CERT_MD5 + '######' + CERT_SHA1 + '~~~~~~' + PKG + '>>>+++' + VC).encode(), 16))).decode()
_e2 = base64.b64encode(_e.encode()).decode()
SAFECODE = (_e2[:16] + _e2[-16:]).upper()


def _varint(n):
    b = b''
    while True:
        x = n & 0x7f
        n >>= 7
        if n:
            b += bytes([x | 0x80])
        else:
            return b + bytes([x])


def _f(num, wire, payload):
    t = _varint((num << 3) | wire)
    if wire == 2:
        return t + _varint(len(payload)) + payload
    return t + payload


def _pb(buf):
    out = []
    i = 0
    n = len(buf)
    while i < n:
        b = buf[i]; fn, wt = b >> 3, b & 7; i += 1
        if wt == 0:
            v = 0; sh = 0
            while i < n:
                x = buf[i]; i += 1
                v |= (x & 0x7f) << sh; sh += 7
                if not x & 0x80:
                    break
            out.append((fn, wt, v))
        elif wt == 2:
            ln = 0; sh = 0
            while i < n:
                x = buf[i]; i += 1
                ln |= (x & 0x7f) << sh; sh += 7
                if not x & 0x80:
                    break
            out.append((fn, wt, buf[i:i + ln])); i += ln
        elif wt == 5:
            out.append((fn, wt, buf[i:i + 4])); i += 4
        elif wt == 1:
            out.append((fn, wt, buf[i:i + 8])); i += 8
        else:
            i += 1
    return out


def _rnd(k):
    CH = string.ascii_letters + string.digits
    return ''.join(random.sample(list(CH), k - 1)) + '='


class Spider(_Base):
    HOST_NAME = '橘汁视频'

    # 是否过滤 m3u8 里的图片伪装广告分片(默认开)
    # 关掉就直连, 省一层代理; 开了播放会多一次本地转发, 但没广告
    AD_FILTER = True
    # 过滤后至少保留这么多秒, 否则不采用过滤结果(防残片)
    # 实测: 正常一集 45 分钟左右(2813 秒); NS蓝光-1 过滤后只剩 20 秒;
    #       FY蓝光 过滤后只有 426 秒(7.1 分钟) —— 都是残片, 播到一半就断。
    # 阈值取 900 秒(15 分钟): 短剧/番剧单集一般也超过这个数,
    # 而残片全在 7 分钟以内, 能干净地挡住。
    MIN_KEEP_SEC = 900
    # 详情阶段预检线路: 首集 m3u8 里图片分片占比 >= 这个值就判坏线剔除
    # 实测坏线都是 85%~100%, 干净线路是 0%, 取 0.5 有足够安全边界
    AD_RATIO = 0.5
    # 是否开启这个预检(会多发 N 次请求, 但能直接避免用户点到广告线)
    PRECHECK_LINES = True
    # 只预检排序后的前几条线路, 不全查。
    # 全查 9~12 条要 4~11 秒, 详情页会明显卡; 前 4 条已覆盖
    # 用户最可能点的位置, 后面的坏线用户点到了再靠 AD_FILTER 兜底。
    PRECHECK_N = 4
    # 预检时只看清单前多少个分片(够判断比例就行, 看全清单很慢)
    SAMPLE_SEGS = 12

    # 插播广告段的地址特征(小写子串匹配)
    # ★ fengbao 系源站在正片第 5 分钟 / 第 40 分钟插广告, 地址长这样:
    #     /video/adjump/time/17873201989040000000.ts   (adjump = ad jump)
    #   广告是真的 TS 视频(1.1MB), 不是图片, 只能靠路径认。
    #   实测每条: B蓝光 18 个, 仙逆 9 个, 位置固定在第 5 / 40 分钟,
    #   两侧都夹着 #EXT-X-DISCONTINUITY。
    #   遇到新的广告路径就往后加, 不用改逻辑。
    _AD_PAT = ('adjump', '/ad/', '/ads/', 'advert', '/gg/', '/guanggao')
    # 插播广告是按"秒"算的(18 个 * 3 秒 = 54 秒), 不影响
    # MIN_KEEP_SEC 那道残片判断 —— 那道阈值只针对"整集全是图"的假片源。

    def getName(self):
        return '橘汁视频'

    _cur_id = ''

    def init(self, extend=''):
        self.udid = hashlib.md5(str(time.time()).encode()).hexdigest()[:16].upper()
        self._rsa1 = PKCS1_v1_5.new(RSA.import_key(base64.b64decode(PUB1_B64)))
        self._rsa2 = None
        self._token = ''
        self._login()
        self._zone()

    def _http(self, url, data=None, headers=None):
        req = urllib.request.Request(url, data=data, headers=headers or {})
        import ssl
        ctx = ssl._create_unverified_context()
        return urllib.request.urlopen(req, timeout=25, context=ctx).read()

    def _login(self):
        try:
            body = json.dumps({'username': 'tv_%s' % self.udid[:10].lower(),
                               'password': hashlib.md5(('tv' + self.udid).encode()).hexdigest(),
                               'udid': self.udid}).encode()
            try:
                self._http(HOST + '/api/ex/v3/user/register', body, {
                    'User-Agent': UA, 'Content-Type': 'application/json'})
            except Exception:
                pass
            d = self._http(HOST + '/api/ex/v3/user/login', body, {
                'User-Agent': UA, 'Content-Type': 'application/json'})
            data = json.loads(d).get('data') or {}
            self._token = (data.get('token') or (data.get('user') or {}).get('token') or '')
        except Exception:
            self._token = ''

    def _zone(self):
        ts = int(time.time() * 1000)
        rnd = _rnd(16)
        sign = base64.b64encode(self._rsa1.encrypt((str(ts) + rnd).encode())).decode()
        body = (_f(1, 0, _varint(ts)) + _f(2, 2, sign.encode()) +
                _f(3, 2, rnd.encode()) + _f(4, 2, rnd.encode()) + _f(5, 2, rnd.encode()))
        P = {'plat': 'android', 'vOs': '16', '_vOsCode': '36', 'vApp': VC,
             'vName': '3.0.2.4', 'pkg': PKG,
             'appName': '%E6%A9%98%E6%B1%81',
             'udid': self.udid, 'uuid': self.udid, 'chid': '10000',
             'androidID': self.udid, 'net': '1', 'young': 0, 'tenantId': '*',
             'v': 1, 'device': 0, 'lang': 'zh', 'country': 'CN', 'cpu': 'arm64-v8a'}
        d = self._http(HOST + '/api/v5/find/app/zone', body, {
            'User-Agent': UA, 'Content-Type': 'application/x-protobuf',
            'Accept': 'application/x-protobuf', 'Cache-Control': 'no-cache',
            'publicParams': json.dumps(P, separators=(',', ':'))})
        top = _pb(d)
        inner = [v for fn, wt, v in top if fn == 3 and wt == 2][0]
        strs = {fn: v for fn, wt, v in _pb(inner) if wt == 2}
        self._rsa2 = PKCS1_v1_5.new(RSA.import_key(base64.b64decode(
            strs[2] + strs[3] + strs[4] + strs[5])))

    def _hdr(self):
        ts = int(time.time() * 1000)
        rnd = _rnd(16)
        sig = base64.b64encode(self._rsa2.encrypt((str(ts) + rnd + VC).encode())).decode()
        ao = base64.b64encode(AES.new(SAFE, AES.MODE_ECB).encrypt(
            pad((str(ts) + rnd).encode(), 16))).decode()
        J = {'country': 'CN', 'vName': '3.0.2.4', 'cpuId': '', 'young': 0,
             'facturer': 'OnePlus', 'pkg': PKG, 'uuid': self.udid,
             'resolution': '1080x2256', 'mac': '02%3A00%3A00%3A00%3A00%3A00',
             'sig': sig, 'abid': '7470', 'model': 'PJX110', 'plat': 'android',
             'udid': self.udid, 'dpi': '480', 'net': '1', 'lang': 'zh',
             'random_str': rnd, 'brand': 'OnePlus', 'timestamp': ts,
             'density': '3.0', 'appName': '%E6%A9%98%E6%B1%81',
             'cpu': 'arm64-v8a', 'chid': '10000', 'carrier': '%E8%81%94%E9%80%9A',
             'sig2': ao[:8], 'v': 1, 'sig3': ao[8:], 'tenantId': '*',
             '_vOsCode': '36', 'vOs': '16', 'vApp': VC, 'device': 0,
             'androidID': self.udid}
        blob = json.dumps(J, separators=(',', ':'), ensure_ascii=False).encode()
        pd_hex = AES.new(NATIVE_K, AES.MODE_CBC, NATIVE_K).encrypt(pad(blob, 16)).hex()
        h = {'User-Agent': UA, 'Accept': 'application/json',
             'Cache-Control': 'no-cache',
             'publicParams': json.dumps({'paramsData': pd_hex}, separators=(',', ':'))}
        if self._token:
            h['token'] = self._token
        return h

    def _secure(self, mapkv):
        ts = int(time.time() * 1000)
        rnd8 = _rnd(8)
        plain = (mapkv + str(ts)).encode()
        ct = AES.new(SAFECODE.encode(), AES.MODE_ECB).encrypt(pad(plain, 16))
        b64 = base64.b64encode(ct).decode()
        return (_f(1, 2, (rnd8 + b64[:12]).encode()) +
                _f(2, 2, b64[12:].encode()) +
                _f(3, 2, _rnd(20).encode()) + _f(4, 0, _varint(ts)) +
                _f(5, 2, rnd8.encode()))

    def homeContent(self, f):
        cats = []
        try:
            d = self._http(HOST + '/api/v3/drama/getCategory?orderBy=type_id',
                           None, {'User-Agent': UA, 'Accept': 'application/json'})
            for c in (json.loads(d).get('data') or []):
                if str(c.get('id')) != '29':
                    cats.append({'type_id': str(c['id']),
                                 'type_name': c.get('name', '')})
        except Exception:
            pass
        if not cats:
            cats = [{'type_id': '21', 'type_name': '电影'},
                    {'type_id': '22', 'type_name': '剧集'},
                    {'type_id': '25', 'type_name': '动漫'},
                    {'type_id': '26', 'type_name': '综艺'},
                    {'type_id': '27', 'type_name': '短剧'},
                    {'type_id': '28', 'type_name': '漫剧'}]
        cats.append({'type_id': 'history', 'type_name': '最近在看'})
        return {'class': cats}

    def homeVideoContent(self):
        return {'list': self._list('page=1&pagesize=24')}

    def _vodids(self):
        try:
            d = self._http(HOST + '/api/ex/v3/security/tag/list', None, self._hdr())
            tags = json.loads(d).get('data') or []
            ids = []
            for t in tags:
                for sec in (t.get('sections') or []):
                    for v in (sec.get('vodList') or []):
                        ids.append(str(v.get('id')))
            return ','.join(ids[:6])
        except Exception:
            return ''

    def _list(self, qs):
        out = []
        try:
            hh = self._hdr()
            hh['Content-Type'] = 'application/x-protobuf'
            hh['Accept'] = 'application/x-protobuf'
            d = self._http(HOST + '/api/proto/v5/drama/category',
                           self._secure(qs), hh)
            top = _pb(d)
            code = [v for fn, wt, v in top if fn == 1 and wt == 0]
            if (code[0] if code else 0) != 200:
                return out
            data = [v for fn, wt, v in top if fn == 3 and wt == 2][0]
            for fn, wt, v in _pb(data):
                if fn != 1 or wt != 2:
                    continue
                info = {'vod_id': '', 'vod_name': '', 'vod_pic': '', 'vod_remarks': ''}
                for f2, w2, v2 in _pb(v):
                    if f2 == 3 and w2 == 0:
                        info['vod_id'] = str(v2)
                    elif f2 == 5 and w2 == 2:
                        info['vod_name'] = v2.decode('utf-8', 'replace')
                    elif f2 == 2 and w2 == 2:
                        cands = [v3.decode('utf-8', 'replace')
                                 for f3, w3, v3 in _pb(v2)
                                 if w3 == 2 and v3.startswith(b'http')]
                        if cands:
                            info['vod_pic'] = next(
                                (u for u in cands if u.startswith('https')),
                                cands[0])
                    elif f2 == 13 and w2 == 2:
                        info['vod_remarks'] = v2.decode('utf-8', 'replace')
                if info['vod_id']:
                    out.append(info)
        except Exception:
            pass
        return out

    def categoryContent(self, tid, pg, f, ext):
        pg = int(pg or 1)
        if tid == 'history':
            return {'list': self._history_list(), 'page': 1,
                    'pagecount': 1, 'limit': 40, 'total': 40}
        qs = 'page=%d&pagesize=24&typeId1=%s' % (pg, tid)
        return {'list': self._list(qs), 'page': pg,
                'pagecount': 999, 'limit': 24, 'total': 99999}

    def _history_list(self):
        out = []
        try:
            d = self._http(HOST + '/api/ex/v3/user/history?username=fzcrym',
                           None, {'User-Agent': UA, 'Accept': 'application/json'})
            for it in (json.loads(d).get('data') or []):
                vid = it.get('videoId', '')
                if '|' in vid:
                    frm, url = vid.split('|', 1)
                    out.append({
                        'vod_id': 'h$%s$%s' % (frm, url),
                        'vod_name': it.get('videoName', ''),
                        'vod_pic': it.get('videoCover', ''),
                        'vod_remarks': '%s·第%s集' % (frm, it.get('videoPart', '')),
                    })
        except Exception:
            pass
        return out

    def detailContent(self, ids):
        out = {'vod_id': ids[0]}
        self._cur_id = ids[0]
        if ids[0].startswith('h$'):
            _, frm, url = ids[0].split('$', 2)
            return {'list': [dict(out, vod_name='继续观看',
                                   vod_play_from=frm,
                                   vod_play_url='正片$%s' % url,
                                   vod_pic='',
                                   vod_content='播放历史·线路:' + frm)]}
        try:
            hh = self._hdr()
            hh['Content-Type'] = 'application/x-protobuf'
            hh['Accept'] = 'application/x-protobuf'
            d = self._http(HOST + '/api/proto/v5/drama/getDetail',
                           self._secure('id=' + ids[0]), hh)
            top = _pb(d)
            data = [v for fn, wt, v in top if fn == 3 and wt == 2][0]
            dd = _pb(data)
            for fn, wt, v in dd:
                if fn == 0 or fn > 100:
                    break  # protobuf 错位起点, 之后全是字符串碎片(乱码源)
                if fn == 9 and wt == 2 and 'vod_name' not in out:
                    out['vod_name'] = v.decode('utf-8', 'replace')
                elif fn == 1 and wt == 2 and 'vod_area' not in out:
                    out['vod_area'] = v.decode('utf-8', 'replace')
                elif fn == 12 and wt == 2 and 'vod_director' not in out:
                    out['vod_director'] = v.decode('utf-8', 'replace')
                elif fn == 16 and wt == 2 and 'vod_actor' not in out:
                    out['vod_actor'] = v.decode('utf-8', 'replace').lstrip(' ,')
                elif fn == 25 and wt == 2 and 'vod_actor' not in out:
                    out['vod_actor'] = v.decode('utf-8', 'replace')
                elif fn == 6 and wt == 2 and 'vod_content' not in out:
                    out['vod_content'] = re.sub(
                        r'<[^>]+>', '', v.decode('utf-8', 'replace'))
                elif fn == 2 and wt == 2 and 'vod_pic' not in out:
                    cands = [v3.decode('utf-8', 'replace')
                             for f3, w3, v3 in _pb(v)
                             if w3 == 2 and v3.startswith(b'http')]
                    if cands:
                        out['vod_pic'] = next(
                            (u for u in cands if u.startswith('https')),
                            cands[0])
            # 演员兜底: f16/f25 无值时从错位块的干净中文串提取
            if 'vod_actor' not in out:
                for fn, wt, v in dd:
                    if fn == 0 and wt == 2:
                        txt = v.decode('utf-8', 'replace')
                        names = re.findall(
                            r'[\u4e00-\u9fa5·]{2,12}(?::?,)'
                            r'?[一-龥·]{2,12}', txt)
                        cand = [x for x in names if len(x) >= 4]
                        if cand:
                            out['vod_actor'] = ','.join(cand[:6])
                            break
            # f29 分集: 详情响应 _pb 会错位, 用原始 0xEA01 tag 扫描
            eps = []
            pos = 0
            n = len(data)
            while True:
                j = data.find(b'\xea\x01', pos)
                if j < 0:
                    break
                k = j + 2
                ln = 0
                sh = 0
                while k < n and data[k] & 0x80:
                    ln |= (data[k] & 0x7f) << sh
                    sh += 7
                    k += 1
                if k >= n:
                    break
                ln |= (data[k] & 0x7f) << sh
                k += 1
                if ln <= 0 or k + ln > n:
                    pos = j + 1
                    continue
                entry = data[k:k + ln]
                pos = k + ln
                title = pth = src = src_cn = ''
                for f3_, w3_, v3_ in _pb(entry):
                    if w3_ != 2:
                        continue
                    if f3_ == 2:
                        title = v3_.decode('utf-8', 'replace')
                    elif f3_ == 3:
                        title = v3_.decode('utf-8', 'replace')
                    elif f3_ == 4:
                        pth = v3_.decode('utf-8', 'replace')
                    elif f3_ == 9:
                        src = v3_.decode('utf-8', 'replace')
                    elif f3_ == 10:
                        src_cn = v3_.decode('utf-8', 'replace')
                if not pth:
                    continue
                # 集名归一化: "第01集"/"第01集完结"→"1"
                mm = re.match(r'^第?0*(\d{1,4})[集话期](?:完结)?$', title)
                if mm:
                    title = mm.group(1)
                eps.append((title, pth, src, src_cn))
            lines = {}
            order = []
            for title, pth, src, src_cn in eps:
                line = src_cn or src or '正片'
                if line not in lines:
                    lines[line] = []
                    order.append(line)
                if re.match(r'(?i).*\.(mp4|m3u8|flv|mkv|avi|ts|mov|mpd|m4a|wmv)(\?.*)?$', pth):
                    ep_url = pth
                else:
                    ep_url = base64.b64encode(json.dumps(
                        {'vodPlayFrom': src, 'playUrl': pth},
                        separators=(',', ':')).encode()).decode()
                # ★ 地址里带中文(如 .../xianni/第01集/index.m3u8)必须百分号编码,
                #   否则 urllib 按 ascii 编码直接抛错, 播放器也拼不出请求(404)。
                #   保留 :/?&=%#@+~ 这些有语义的字符, 只编码中文和空格。
                if ep_url.startswith('http'):
                    ep_url = urllib.parse.quote(ep_url, safe=':/?&=%#@+~')
                lines[line].append('%s$%s' % (title or '正片', ep_url))
            # 集名归一化: "第01集"→"1", 纯数字保留, 其他保留原名
            for ln_name in lines:
                norm = []
                for it in lines[ln_name]:
                    t, u = it.split('$', 1)
                    mm = re.match(r'^第?0*(\d{1,4})[集话期]$', t)
                    norm.append('%s$%s' % (mm.group(1) if mm else t, u))
                lines[ln_name] = norm
            # 线路排序: 超高清最前, 蓝光按名, 其余殿后
            def _rank(nm):
                if '超高清' in nm:
                    return 0
                if '蓝光' in nm:
                    return 1
                return 2
            order.sort(key=lambda x: (_rank(x), x))
            # 用后台预检的结果剔除已知广告线(首次进来缓存是空的, 全给出去)
            if self.PRECHECK_LINES and len(order) > 1:
                order = self._drop_ad_lines(order, lines, ids[0])
            out['_lines'] = order
            out['_lines_map'] = lines
            lines = out.pop('_lines', [])
            lmap = out.pop('_lines_map', {})
            if lines:
                out['vod_play_from'] = '$$$'.join(lines)
                out['vod_play_url'] = '$$$'.join(
                    '#'.join(lmap[l]) for l in lines)
            else:
                out['vod_play_from'] = '橘汁'
                out['vod_play_url'] = '暂无片源$http://'
            # 后台异步预检(不阻塞本次返回)
            if self.PRECHECK_LINES and len(lines) > 1:
                self._precheck_async(ids[0], lines, lmap)
        except Exception:
            out['vod_name'] = ids[0]
            out['vod_play_from'] = '橘汁'
            out['vod_play_url'] = '播放$http://'
        return {'list': [out]}

    def searchContent(self, key, quick, pg=1):
        try:
            hh = self._hdr()
            hh['Content-Type'] = 'application/x-protobuf'
            hh['Accept'] = 'application/x-protobuf'
            qs = 'page=%s&pagesize=24&searchKeys=%s' % (pg or 1, key)
            d = self._http(HOST + '/api/proto/v5/drama/search',
                           self._secure(qs), hh)
            top = _pb(d)
            code = [v for fn, wt, v in top if fn == 1 and wt == 0]
            if (code[0] if code else 0) != 200:
                return {'list': [], 'page': int(pg or 1)}
            datas = [v for fn, wt, v in top if fn == 3 and wt == 2]
            if not datas:
                return {'list': [], 'page': int(pg or 1)}
            out = []
            for fn, wt, v in _pb(datas[0]):
                if wt != 2 or fn == 0 or fn > 100:
                    continue
                item = {'vod_id': '', 'vod_name': '', 'vod_pic': '',
                        'vod_remarks': ''}
                for f3, w3, v3 in _pb(v):
                    if w3 != 2 and not (f3 == 3 and w3 == 0):
                        continue
                    try:
                        if f3 == 3 and w3 == 0:
                            item['vod_id'] = str(v3)
                        elif f3 == 5:
                            item['vod_name'] = v3.decode('utf-8', 'replace')
                        elif f3 == 2:
                            # 海报 b64串: 取内部http
                            cands = [x.decode('utf-8', 'replace')
                                     for _, w4, x in _pb(v3)
                                     if w4 == 2 and x.startswith(b'http')]
                            if cands:
                                item['vod_pic'] = next(
                                    (u for u in cands if u.startswith('https')),
                                    cands[0])
                        elif f3 == 13:
                            item['vod_remarks'] = v3.decode('utf-8', 'replace')
                        elif f3 == 4:
                            item['vod_content'] = v3.decode(
                                'utf-8', 'replace')[:100]
                    except Exception:
                        pass
                if item['vod_id'] and item['vod_name']:
                    out.append(item)
            return {'list': out, 'page': int(pg or 1)}
        except Exception:
            return {'list': [], 'page': 1}

    def playerContent(self, flag, id, vipFlags):
        # 详情里给的是一整段 '集名$参数', 播放时必须把集名剥掉,
        # 否则 base64 解不开, 整条被当成 URL 原样吐出去(会 404)
        try:
            if id and not id.startswith('http') and '$' in id:
                id = id.split('$', 1)[1]
        except Exception:
            pass
        url = id
        try:
            if id and not id.startswith('http') and not id.startswith('h$'):
                jm = json.loads(base64.b64decode(id))
                pf, pu = jm.get('vodPlayFrom', ''), jm.get('playUrl', '')
                hh = self._hdr()
                hh['Content-Type'] = 'application/x-protobuf'
                hh['Accept'] = 'application/x-protobuf'
                qs = 'vodPlayFrom=%s&playUrl=%s' % (
                    urllib.parse.quote(pf), urllib.parse.quote(pu, safe=''))
                d = self._http(HOST + '/api/proto/v5/videoUsableUrl',
                               self._secure(qs), hh)
                top = _pb(d)
                code = [v for fn, wt, v in top if fn == 1 and wt == 0]
                if (code[0] if code else 0) == 200:
                    data = [v for fn, wt, v in top if fn == 3 and wt == 2]
                    if data:
                        mm = re.search(rb'https?://[\x21-\x7e]+',
                                       data[0])
                        if mm:
                            url = mm.group(0).decode(
                                'utf-8', 'replace')
            elif not url.startswith('http'):
                url = 'http://'
        except Exception:
            pass
        # ★ m3u8 里混着伪装成视频分片的图片广告 -> 挂本地代理过滤
        if self.AD_FILTER and url.lower().find('.m3u8') > 0:
            url = self._proxy_url(url)
        return {'parse': 0, 'playUrl': '', 'url': url,
                'header': {'User-Agent': UA}}

    # ------------------------------------------------------ 切片广告过滤
    #
    # 现象: 部分线路的 m3u8 里, 广告方把图片(png/webp)伪装成视频分片,
    # 夹在正常 ts 之间, 播放器当成帧照播 -> 就成了"片头广告/中途广告"。
    # 实测(兰香如故 第1集):
    #   FY蓝光      总分片 519, 其中 png 440 (85%)
    #   NN蓝光      总分片 520, 其中 png 510 (98%)
    #   NS蓝光-1    总分片 501, 其中 png 497 (99%)
    #   自建4K-3    总分片 520, 其中 png 520 (100%)
    #   JD4K-可下载 总分片 509, 其中 webp 509 (100%)
    #   自建4K-2    总分片 141, 全 ts, 干净
    #
    # ★ 但实测结论是: 这些图片不是"插播广告", 而是**顶替了正片时长**。
    #   把图片全删掉之后, 真正的 ts 只剩一丁点, 整集内容根本不在里面:
    #
    #     主角   FY蓝光      广告 427 真视频 60 片 -> 真时长 5.9 分钟
    #     主角   自营蓝光-1  广告 488 真视频  0 片 -> 真时长 0
    #     主角   自建4K-3    广告 579 真视频  0 片 -> 真时长 0
    #     兰香   FY蓝光      广告 439 真视频 80 片 -> 真时长 6.8 分钟
    #     兰香   NN蓝光      广告 510 真视频 10 片 -> 真时长 0.7 分钟
    #     兰香   NS蓝光-1    广告 497 真视频  4 片 -> 真时长 0.3 分钟
    #     兰香   JD4K-可下载 广告 509 真视频  0 片 -> 真时长 0
    #
    #   所以对这些线路"过滤广告"= 得到一个几分钟的残片, 比带着广告更糟。
    #   正确做法: 识别出来直接判这条线不可用, 让壳子换线。
    #
    #   过滤仍然保留(AD_FILTER), 只在"广告占比高但正片还完整"时才有意义 ——
    #   目前实测没遇到这种源, 逻辑留着以防源站整改。
    #
    # 做法: 原始地址包一层 localProxy, 代理拉 m3u8 -> 剔除图片分片和
    # 对应 #EXTINF -> 把相对分片地址补成绝对 -> 返回新的 m3u8。
    # 播放器只看到过滤后的清单, 感知不到代理存在。

    _ALLOWED_EXT = ('ts', 'm4s', 'mp4', 'm4v', 'aac', 'mp3', 'flv', 'cmfv', 'fmp4')
    _IMG_EXT = ('png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'ico', 'svg', 'avif')

    @staticmethod
    def _seg_ext(u):
        """取分片后缀; 无后缀返回空串"""
        p = u.split('?')[0].split('#')[0]
        tail = p.rsplit('/', 1)[-1]
        if '.' not in tail:
            return ''
        return tail.rsplit('.', 1)[-1].lower()

    def _split_ep(self, item):
        """'集名$播放参数' -> (集名, 播放参数)"""
        s = str(item or '')
        if '$' in s:
            return s.split('$', 1)
        return '', s

    # 坏线缓存: {(影片id, 线路名): 1/0}  1=广告线 0=正常
    _AD_CACHE = {}
    _AD_LOCK = None
    _AD_RUNNING = None

    def _precheck_async(self, vid, order, lmap):
        """后台线程预检前 PRECHECK_N 条线路, 结果写进 _AD_CACHE
        不阻塞详情返回: 实测单条线路要 0.2~9 秒(自建4K-2 的清单 api
        就要 5~9 秒), 同步做详情页会卡住, 用户直接退出了。
        """
        global _AD_RUNNING
        try:
            import threading
            from concurrent.futures import ThreadPoolExecutor
        except Exception:
            return
        if Spider._AD_LOCK is None:
            Spider._AD_LOCK = threading.Lock()
        if Spider._AD_RUNNING is None:
            Spider._AD_RUNNING = set()

        probe = [n for n in order[:max(1, int(self.PRECHECK_N))]
                 if (vid, n) not in Spider._AD_CACHE]
        if not probe:
            return
        with Spider._AD_LOCK:
            probe = [n for n in probe if n not in Spider._AD_RUNNING]
            Spider._AD_RUNNING.update(probe)
        if not probe:
            return

        def one(name):
            try:
                items = lmap.get(name) or []
                bad = bool(items) and self._line_is_ad_heavy(items[0])
            except Exception:
                bad = False
            Spider._AD_CACHE[(vid, name)] = 1 if bad else 0
            with Spider._AD_LOCK:
                Spider._AD_RUNNING.discard(name)

        def run():
            try:
                with ThreadPoolExecutor(max_workers=len(probe)) as ex:
                    list(ex.map(one, probe))
            except Exception:
                pass

        try:
            threading.Thread(target=run).start()
        except Exception:
            pass

    def _drop_ad_lines(self, order, lmap, vid=''):
        """按缓存剔除已确认的广告线
        只信缓存, 不再现场探测(现场探测会把详情页拖住); 首刷时缓存为空
        就原样返回, 后台算好后用户再进详情就干净了。
        全被剔除时也原样返回(总比没有线路强)。
        """
        if not self.PRECHECK_LINES or len(order) < 2:
            return order
        bad = set(n for n in order
                  if Spider._AD_CACHE.get((vid, n)) == 1)
        if not bad:
            return order
        kept = [n for n in order if n not in bad]
        return kept or order

    def _line_is_ad_heavy(self, first_item):
        """预检一条线路的首集: 图片分片占比过高就判它为坏线
        返回 True 表示"该剔除"
        """
        try:
            _, pid = self._split_ep(first_item)
            if not pid:
                return False
            # 取真实 m3u8 地址(不包代理, 直接解析)
            url = pid
            if not pid.startswith('http'):
                jm = json.loads(base64.b64decode(pid))
                pf, pu = jm.get('vodPlayFrom', ''), jm.get('playUrl', '')
                hh = self._hdr()
                hh['Content-Type'] = 'application/x-protobuf'
                hh['Accept'] = 'application/x-protobuf'
                qs = 'vodPlayFrom=%s&playUrl=%s' % (
                    urllib.parse.quote(pf, safe=''),
                    urllib.parse.quote(pu, safe=''))
                d = self._http(HOST + '/api/proto/v5/videoUsableUrl',
                               self._secure(qs), hh)
                top = _pb(d)
                code = [v for fn, wt, v in top if fn == 1 and wt == 0]
                if (code[0] if code else 0) != 200:
                    return False
                data = [v for fn, wt, v in top if fn == 3 and wt == 2]
                if not data:
                    return False
                mm = re.search(rb'https?://[\x21-\x7e]+', data[0])
                if not mm:
                    return False
                url = mm.group(0).decode('utf-8', 'replace')
            if '.m3u8' not in url.lower():
                return False
            # 只读前几十 KB 就够判断了: 坏线开头立刻就是图片分片,
            # 干净线开头是正常 ts。整份清单可能有上千行(自建4K-2 要 11 秒),
            # 而判断只需要开头这一小段。
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            resp = urllib.request.urlopen(req, timeout=6)
            raw = resp.read(4096 * 8)
            try:
                resp.close()
            except Exception:
                pass
            text = raw.decode('utf-8', 'replace')
            if '#EXTM3U' not in text:
                return False
            segs = [l.strip() for l in text.split('\n')
                    if l.strip() and not l.startswith('#')]
            if not segs:
                return False
            # 只探前 PREVIEW_SEGS 个分片就够判了:
            # 坏线是 85%~100% 图片, 干净线是 0%, 抽查十来个分片
            # 就能区分, 不必把整张清单下回来(自建4K-2 有 1400 多行, 要 8 秒)
            sample = segs[:self.SAMPLE_SEGS]
            img = sum(1 for s in sample if self._seg_ext(s) in self._IMG_EXT)
            return float(img) / len(sample) >= self.AD_RATIO
        except Exception:
            return False

    def _proxy_url(self, url):
        """把 m3u8 地址包成 localProxy 地址
        注意 url 必须编码, 否则里面的 & 会把参数切断
        """
        return 'proxy://do=py&type=m3u8&url=' + urllib.parse.quote(url, safe='')

    @staticmethod
    def _parse_proxy_param(param):
        """localProxy 的 param 可能是 dict / 查询串 / 整条代理 URL / 列表串"""
        if isinstance(param, dict):
            return dict(param)
        s = str(param or '').strip()
        out = {}
        if not s:
            return out
        if s.startswith('{'):
            try:
                d = json.loads(s)
                if isinstance(d, dict):
                    return d
            except Exception:
                pass
        if '?' in s and ('proxy' in s or 'do=py' in s):
            s = s.split('?', 1)[1]
        s = s.strip().strip('[]')
        for part in re.split(r'[,&]', s):
            part = part.strip().strip('"').strip("'")
            if '=' not in part:
                continue
            k, v = part.split('=', 1)
            k = k.strip()
            if k in ('url', 'u'):
                # url 的值里可能还有未编码的 &, 按位置取到串尾重组
                idx = s.find(part)
                if idx >= 0:
                    v = s[idx + len(k) + 1:]
                v = urllib.parse.unquote(v.strip().strip('"').strip("'"))
            out[k] = v
        return out

    def _is_ad_seg(self, url):
        """分片地址看起来像插播广告吗
        ★ 实测 fengbao 系源站(风爆/风豹 CDN)会在正片中间插入广告段,
          路径是 /video/adjump/time/<19位时间戳><序号>.ts:
              /video/adjump/time/17873201989040000000.ts
          这类地址以 / 开头(站点根路径), 正常分片是 0000299.ts 这种相对名。
          配合 #EXT-X-DISCONTINUITY 出现, 位置固定在第 5 分钟和第 40 分钟。
          注意: 广告段是真的 TS 视频(1.1MB), 不是图片, 只能靠路径/域名认。
        """
        u = (url or '').lower()
        for w in self._AD_PAT:
            if w in u:
                return True
        return False

    def _filter_m3u8(self, text, base_url):
        """干掉图片分片和插播广告段, 相对地址补绝对
        返回 (新内容, 删掉几个, 留下几个, 留下的总秒数)
        """
        lines = text.split('\n')
        out = []
        dropped = 0
        kept = 0
        kept_sec = 0.0
        # 待处理的 #EXTINF/#EXT-X-* 先攒着, 确认下一行是有效分片才一起吐出
        pending = []
        pending_sec = 0.0
        # 上一个分片是不是刚被当广告删掉 —— 用来顺手清掉后面的
        # #EXT-X-DISCONTINUITY(广告段和正片之间一定夹着它,
        # 广告删了它就成了孤立标记, 有些播放器会因此重置解码器闪一下)
        just_dropped = False
        for raw in lines:
            ln = raw.rstrip('\r')
            t = ln.strip()
            if not t:
                continue
            if t.startswith('#'):
                # ★ #EXTM3U/#EXT-X-VERSION/#EXT-X-TARGETDURATION 这些
                #   头部标签不属于任何分片, 必须无条件先输出。
                #   攒进 pending 的话, 一旦第一个分片就是广告, 它会被整批丢掉,
                #   剩下的清单没有 #EXTM3U 开头, 播放器直接不认。
                if not t.startswith('#EXTINF'):
                    # 紧跟在被删广告后面的 DISCONTINUITY 一起丢掉
                    if just_dropped and t.startswith('#EXT-X-DISCONTINUITY'):
                        just_dropped = False
                        continue
                    just_dropped = False
                    out.append(ln)
                    continue
                pending.append(ln)
                try:
                    pending_sec = float(t.split(':', 1)[1].split(',')[0])
                except Exception:
                    pending_sec = 0.0
                continue
            # 这行是分片地址
            ext = self._seg_ext(t)
            if self.AD_FILTER and (ext in self._IMG_EXT or self._is_ad_seg(t)):
                # 图片广告 / 插播广告段: 连同它上面的 #EXTINF 一起丢掉
                dropped += 1
                pending = []
                pending_sec = 0.0
                just_dropped = True
                continue
            just_dropped = False
            # 相对地址 -> 绝对
            if not (t.startswith('http://') or t.startswith('https://')):
                t = urllib.parse.urljoin(base_url, t)
            out.extend(pending)
            pending = []
            out.append(t)
            kept += 1
            kept_sec += pending_sec
            pending_sec = 0.0
        return '\n'.join(out) + '\n', dropped, kept, kept_sec

    def localProxy(self, param):
        p = self._parse_proxy_param(param)
        rtype = str(p.get('type') or '')
        url = str(p.get('url') or '')
        if not url:
            return [404, 'text/plain', b'']
        if rtype and rtype != 'm3u8':
            return [404, 'text/plain', b'']
        try:
            hh = {'User-Agent': UA, 'Accept': '*/*'}
            # ★ 部分源站(c1.rrcdnbf6.com 这种)对同一地址会间歇性甩 404:
            #   实测连续请求 6 次的结果是 200/200/404/404/200/200。
            #   代理这层必须重试, 否则播放器拿到 404 就直接报"播放失败",
            #   而用户重进一次可能又好了 —— 体验极差。
            body = b''
            last = None
            for _try in range(3):
                try:
                    req = urllib.request.Request(url, headers=hh)
                    resp = urllib.request.urlopen(req, timeout=15)
                    body = resp.read()
                    enc = ''
                    try:
                        enc = (resp.headers.get(
                            'Content-Encoding') or '').lower()
                    except Exception:
                        pass
                    if enc == 'gzip' or body[:2] == b'\x1f\x8b':
                        import gzip as _gz
                        import io as _io
                        body = _gz.GzipFile(fileobj=_io.BytesIO(body)).read()
                    if body:
                        break
                except Exception as e:
                    last = e
                    # 源站抖得很快, 隔 0.25 秒重试基本就能命中,
                    # 别退避太久, 否则一次播放要等两三秒才出画面
                    try:
                        import time as _t
                        _t.sleep(0.25)
                    except Exception:
                        pass
                    continue
            if not body:
                if last:
                    raise last
                return [404, 'text/plain', b'']
            text = body.decode('utf-8', 'replace')
        except Exception:
            return [404, 'text/plain', b'']

        if '#EXTM3U' not in text:
            # 不是 m3u8, 原样回(可能是 master 或错误页)
            return [200, 'application/vnd.apple.mpegurl', body]

        new_text, dropped, kept, kept_sec = self._filter_m3u8(text, url)
        if dropped == 0:
            # 没广告; 但如果分片是相对地址(B蓝光 就是 0000000.ts 这种),
            # 也得把补全后的清单吐出去, 否则播放器拼不出可播地址。
            if new_text and new_text != text:
                return [200, 'application/vnd.apple.mpegurl',
                        new_text.encode('utf-8')]
            return [200, 'application/vnd.apple.mpegurl', body]
        if kept == 0:
            # 全被过滤掉了(说明这条线路全是图片), 原样回, 免得变黑屏
            return [200, 'application/vnd.apple.mpegurl', body]
        # ★ 时长兜底: 有的线路图片广告占了"视频内容位", 真视频分片本来就只剩
        #   几十秒。实测兰香如故第1集: NS蓝光-1 过滤后仅 4 片 / 20 秒,
        #   FY蓝光 80 片 / 7.7 分钟, 而正常线路 自建4K-2 是 141 片 / 46.9 分钟。
        #   这种残片播出去还不如带着广告能看, 直接回原清单让用户自己换线路。
        if kept_sec < self.MIN_KEEP_SEC:
            return [200, 'application/vnd.apple.mpegurl', body]
        return [200, 'application/vnd.apple.mpegurl',
                new_text.encode('utf-8')]

    def isVideoFormat(self, url):
        return True

    def isTextFormat(self, url):
        return False

    def destroy(self):
        pass


# ------------------------------------------------------------------ 模块级转发
#
# hipy / CatVod(T4) 是按模块函数名调用的, 不是按类方法。原文件只有类,
# 缺这层转发在 TVBox 里会直接找不到接口。顺手补齐。

_sp = None


def _ins():
    global _sp
    if _sp is None:
        _sp = Spider()
    return _sp


def getName():
    return _ins().getName()


def init(extend=''):
    return _ins().init(extend)


def homeContent(filter=None):
    return _ins().homeContent(filter)


def homeVideoContent():
    return _ins().homeVideoContent()


def categoryContent(tid, pg=1, filter=None, extend=None):
    return _ins().categoryContent(tid, pg, filter, extend)


def detailContent(ids):
    return _ins().detailContent(ids)


def searchContent(key, quick=False, pg=1):
    return _ins().searchContent(key, quick, pg)


def searchContentPage(key, quick=False, pg=1):
    return _ins().searchContent(key, quick, pg)


def playerContent(flag, id, vipFlags=None):
    return _ins().playerContent(flag, id, vipFlags)


def localProxy(param):
    return _ins().localProxy(param)


def isVideoFormat(url):
    return _ins().isVideoFormat(url)


def manualVideoCheck():
    return False


def getDependence():
    return []


def destroy():
    return _ins().destroy()
