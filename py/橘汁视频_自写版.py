# -*- coding: utf-8 -*-
# 橘汁视频 TVBox py 源 —— 独立重写版
# 协议：AES(请求体加密) + RSA(签名) + protobuf(编码) + zone 动态换私钥
# 常量来源说明：host/密钥不在 APK 明文（加密配置+native），经逆向+实测验证确定。
# 代码结构为本实现独立设计，不复制既有脚本。

import json
import re
import time
import base64
import string
import random
import hashlib
import urllib.request
import urllib.parse

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass

# ---------- 常量（实测验证） ----------
HOST = 'https://juziapp.hzhcbkj.cn'
UA = 'okhttp/3.12.1'
PUB1 = 'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCr8SzZhjYy+rsya1K09t8d2K50pWFoBkgUqMpKOiW+3IEVKd4eTdvg9RSOjQ82kypL6R9BnsmrS1V8s4PVDwjQbUtYhTPPC9Hz16qY7rpD6m0d2vr09/UpWQ5uOy9PR0QTrsioveZ+DIe9jc3C+zBCu/kZSY/R8stwJoiitki3gwIDAQAB'
KEY_NATIVE = b'ed5fdsgucxumegqa'          # 请求头参数加密 key（CBC, iv=key）
KEY_SAFE = b'OC1A06E197EF10CF3F6058CA7A803B5E'   # 头里 sig2/sig3 来源 key
KEY_PW = b'11GK2we32144LO&hilUITB)FMd1khdaF'     # SAFECODE 派生 key
CERT_MD5 = '090DA8F91D3F60CC6CB250D86F06FE12'
CERT_SHA1 = '3DADB42485B7F864E766479ADA6B1176D81D8D73'
PKG = 'com.mxj.wylcjbxyx'
VER = '3024'

# SAFECODE = AES(PW) 加密 MD5+SHA1+PKG+VER -> base64x2 -> 头尾16


def _pad16(b):
    n = 16 - len(b) % 16
    return b + bytes([n]) * n


def _safe_code():
    from Crypto.Cipher import AES
    data = (CERT_MD5 + '######' + CERT_SHA1 + '~~~~~~' + PKG + '>>>+++' + VER).encode()
    ct = AES.new(KEY_PW, AES.MODE_ECB).encrypt(_pad16(data))
    b64 = base64.b64encode(ct).decode()
    b64b = base64.b64encode(b64.encode()).decode()
    return (b64b[:16] + b64b[-16:]).upper()


SAFECODE = _safe_code()


# ---------- protobuf 编解码 ----------
def _varint(n):
    out = b''
    while True:
        x = n & 0x7f
        n >>= 7
        if n:
            out += bytes([x | 0x80])
        else:
            return out + bytes([x])


def _field(num, wire, payload):
    head = _varint((num << 3) | wire)
    if wire == 2:
        return head + _varint(len(payload)) + payload
    return head + payload


def _pb(buf):
    """proto 解码：返回 [(field, wire, value)]，wire0=int, wire2=bytes"""
    out, i, n = [], 0, len(buf)
    while i < n:
        b = buf[i]
        fn, wt = b >> 3, b & 7
        i += 1
        if wt == 0:
            v, sh = 0, 0
            while i < n:
                x = buf[i]
                i += 1
                v |= (x & 0x7f) << sh
                sh += 7
                if not x & 0x80:
                    break
            out.append((fn, wt, v))
        elif wt == 2:
            ln, sh = 0, 0
            while i < n:
                x = buf[i]
                i += 1
                ln |= (x & 0x7f) << sh
                sh += 7
                if not x & 0x80:
                    break
            out.append((fn, wt, buf[i:i + ln]))
            i += ln
        elif wt == 5:
            out.append((fn, wt, buf[i:i + 4]))
            i += 4
        elif wt == 1:
            out.append((fn, wt, buf[i:i + 8]))
            i += 8
        else:
            i += 1
    return out


def _rand(n):
    pool = string.ascii_letters + string.digits
    return ''.join(random.sample(list(pool), n - 1)) + '='


# ---------- 主爬虫 ----------
class Spider(BaseSpider):
    def getName(self):
        return '橘汁视频'

    def init(self, extend=''):
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_v1_5
        self.udid = hashlib.md5(str(time.time()).encode()).hexdigest()[:16].upper()
        self.rsa1 = PKCS1_v1_5.new(RSA.import_key(base64.b64decode(PUB1)))
        self.rsa2 = None
        self.token = ''
        self._register_and_login()
        self._fetch_zone()

    def _post(self, path, body, ctype='application/json'):
        req = urllib.request.Request(HOST + path, data=body,
            headers={'User-Agent': UA, 'Content-Type': ctype}, method='POST')
        return urllib.request.urlopen(req, timeout=25).read()

    def _register_and_login(self):
        # 新 udid 需先注册再登录才能拿到 token
        uname = 'tv_%s' % self.udid[:10].lower()
        pwd = hashlib.md5(('tv' + self.udid).encode()).hexdigest()
        body = json.dumps({'username': uname, 'password': pwd,
                           'udid': self.udid}).encode()
        try:
            self._post('/api/ex/v3/user/register', body)
        except Exception:
            pass
        try:
            data = json.loads(self._post('/api/ex/v3/user/login', body))
            self.token = (data.get('data') or {}).get('token') or ''
        except Exception:
            self.token = ''

    def _fetch_zone(self):
        from Crypto.Cipher import PKCS1_v1_5
        ts = int(time.time() * 1000)
        rnd = _rand(16)
        sign = base64.b64encode(self.rsa1.encrypt((str(ts) + rnd).encode())).decode()
        body = (_field(1, 0, _varint(ts)) + _field(2, 2, sign.encode()) +
                _field(3, 2, rnd.encode()) + _field(4, 2, rnd.encode()) +
                _field(5, 2, rnd.encode()))
        params = {'plat': 'android', 'vOs': '16', '_vOsCode': '36', 'vApp': VER,
                  'vName': '3.0.2.4', 'pkg': PKG, 'appName': '%E6%A9%98%E6%B1%81',
                  'udid': self.udid, 'uuid': self.udid, 'chid': '10000',
                  'androidID': self.udid, 'net': '1', 'young': 0, 'tenantId': '*',
                  'v': 1, 'device': 0, 'lang': 'zh', 'country': 'CN', 'cpu': 'arm64-v8a'}
        req = urllib.request.Request(HOST + '/api/v5/find/app/zone', data=body,
            headers={'User-Agent': UA, 'Content-Type': 'application/x-protobuf',
                     'Accept': 'application/x-protobuf',
                     'publicParams': json.dumps(params, separators=(',', ':'))},
            method='POST')
        resp = urllib.request.urlopen(req, timeout=25).read()
        inner = [v for fn, wt, v in _pb(resp) if fn == 3 and wt == 2][0]
        strs = {fn: v for fn, wt, v in _pb(inner) if wt == 2}
        from Crypto.PublicKey import RSA
        self.rsa2 = PKCS1_v1_5.new(RSA.import_key(base64.b64decode(
            strs[2] + strs[3] + strs[4] + strs[5])))

    def _build_headers(self):
        from Crypto.Cipher import AES, PKCS1_v1_5
        ts = int(time.time() * 1000)
        rnd = _rand(16)
        sig = base64.b64encode(
            self.rsa2.encrypt((str(ts) + rnd + VER).encode())).decode()
        ao = base64.b64encode(AES.new(KEY_SAFE, AES.MODE_ECB).encrypt(
            _pad16((str(ts) + rnd).encode()))).decode()
        j = {'country': 'CN', 'vName': '3.0.2.4', 'cpuId': '', 'young': 0,
             'facturer': 'OnePlus', 'pkg': PKG, 'uuid': self.udid,
             'resolution': '1080x2256', 'mac': '02%3A00%3A00%3A00%3A00%3A00',
             'sig': sig, 'abid': '7470', 'model': 'PJX110', 'plat': 'android',
             'udid': self.udid, 'dpi': '480', 'net': '1', 'lang': 'zh',
             'random_str': rnd, 'brand': 'OnePlus', 'timestamp': ts,
             'density': '3.0', 'appName': '%E6%A9%98%E6%B1%81',
             'cpu': 'arm64-v8a', 'chid': '10000', 'carrier': '%E8%81%94%E9%80%9A',
             'sig2': ao[:8], 'v': 1, 'sig3': ao[8:], 'tenantId': '*',
             '_vOsCode': '36', 'vOs': '16', 'vApp': VER, 'device': 0,
             'androidID': self.udid}
        blob = json.dumps(j, separators=(',', ':'), ensure_ascii=False).encode()
        pd_hex = AES.new(KEY_NATIVE, AES.MODE_CBC, KEY_NATIVE).encrypt(
            _pad16(blob)).hex()
        h = {'User-Agent': UA, 'Accept': 'application/json',
             'Cache-Control': 'no-cache',
             'publicParams': json.dumps({'paramsData': pd_hex},
                                        separators=(',', ':'))}
        if self.token:
            h['token'] = self.token
        return h

    def _secure(self, query):
        """构造 SecureRequest 加密请求体(protobuf)"""
        from Crypto.Cipher import AES
        ts = int(time.time() * 1000)
        rnd = _rand(8)
        ct = AES.new(SAFECODE.encode(), AES.MODE_ECB).encrypt(
            _pad16((query + str(ts)).encode()))
        b64 = base64.b64encode(ct).decode()
        return (_field(1, 2, (rnd + b64[:12]).encode()) +
                _field(2, 2, b64[12:].encode()) +
                _field(3, 2, _rand(20).encode()) + _field(4, 0, _varint(ts)) +
                _field(5, 2, rnd.encode()))

    def _proto_request(self, path, query):
        hh = self._build_headers()
        hh['Content-Type'] = 'application/x-protobuf'
        hh['Accept'] = 'application/x-protobuf'
        req = urllib.request.Request(HOST + path, data=self._secure(query),
                                     headers=hh, method='POST')
        return urllib.request.urlopen(req, timeout=25).read()

    # ---------- 分类 ----------
    def homeContent(self, filter):
        cats = []
        filters = {}
        try:
            d = urllib.request.urlopen(
                urllib.request.Request(HOST + '/api/v3/drama/getCategory?orderBy=type_id',
                    headers={'User-Agent': UA, 'Accept': 'application/json'}),
                timeout=20).read()
            for c in json.loads(d).get('data') or []:
                if str(c.get('id')) != '29':
                    cats.append({'type_id': str(c['id']),
                                 'type_name': c.get('name', '')})
                # 解析筛选维度(class/area/lang/year...) 做成 TVBox filter
                try:
                    cv = json.loads(c.get('converUrl') or '{}')
                except Exception:
                    cv = {}
                opts = []
                if cv.get('class'):
                    opts.append({'key': 'class', 'name': '类型', 'value': [
                        {'n': x, 'v': x} for x in cv['class'].split(',') if x]})
                if cv.get('area'):
                    opts.append({'key': 'area', 'name': '地区', 'value': [
                        {'n': x, 'v': x} for x in cv['area'].split(',') if x]})
                if cv.get('year'):
                    opts.append({'key': 'year', 'name': '年份', 'value': [
                        {'n': x, 'v': x} for x in cv['year'].split(',') if x]})
                if opts:
                    filters[str(c['id'])] = opts
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
        result = {'class': cats}
        if filters:
            result['filters'] = filters
        return result

    def homeVideoContent(self):
        return {'list': self._category_list('page=1&pagesize=24')}

    def categoryContent(self, tid, pg, f, ext):
        pg = int(pg or 1)
        if tid == 'history':
            return {'list': self._history(), 'page': 1, 'pagecount': 1,
                    'limit': 40, 'total': 40}
        # 解析筛选参数（前端本地过滤）
        tag = area = year = ''
        if isinstance(ext, dict):
            tag = (ext.get('class') or ext.get('category') or '').strip()
            area = (ext.get('area') or '').strip()
            year = (ext.get('year') or '').strip()
        elif isinstance(ext, str) and ext:
            try:
                e = json.loads(ext)
                tag = (e.get('class') or e.get('category') or '').strip()
                area = (e.get('area') or '').strip()
                year = (e.get('year') or '').strip()
            except Exception:
                pass
        # 有筛选：多拉几页再本地过滤；无筛选：正常单页
        if tag or area or year:
            pages = 12
            all_ = []
            for p in range(1, pages + 1):
                qs = 'page=%d&pagesize=24&typeId1=%s' % (p, tid)
                all_.extend(self._category_list(qs))
            out = []
            for it in all_:
                cl = (it.get('_class') or '')
                ar = (it.get('_area') or '')
                yr = (it.get('_year') or '')
                if tag and tag not in cl:
                    continue
                if area and area not in ar:
                    continue
                if year and year != yr:
                    continue
                if it.get('vod_id') and it.get('vod_id') not in [x.get('vod_id') for x in out]:
                    out.append(it)
            return {'list': out, 'page': 1, 'pagecount': 1,
                    'limit': len(out), 'total': len(out)}
        qs = 'page=%d&pagesize=24&typeId1=%s' % (pg, tid)
        return {'list': self._category_list(qs), 'page': pg,
                'pagecount': 999, 'limit': 24, 'total': 99999}

    def _category_list(self, qs):
        out = []
        try:
            d = self._proto_request('/api/proto/v5/drama/category', qs)
            top = _pb(d)
            code = [v for fn, wt, v in top if fn == 1 and wt == 0]
            if (code[0] if code else 0) != 200:
                return out
            data = [v for fn, wt, v in top if fn == 3 and wt == 2][0]
            for fn, wt, v in _pb(data):
                if fn != 1 or wt != 2:
                    continue
                info = {'vod_id': '', 'vod_name': '', 'vod_pic': '',
                        'vod_remarks': '', '_class': '', '_area': '', '_year': ''}
                for f2, w2, v2 in _pb(v):
                    if f2 == 3 and w2 == 0:
                        info['vod_id'] = str(v2)
                    elif f2 == 5 and w2 == 2:
                        info['vod_name'] = v2.decode('utf-8', 'replace')
                    elif f2 == 2 and w2 == 2:
                        pics = [x.decode('utf-8', 'replace')
                                for f3, w3, x in _pb(v2)
                                if w3 == 2 and x.startswith(b'http')]
                        if pics:
                            info['vod_pic'] = next(
                                (u for u in pics if u.startswith('https')), pics[0])
                    elif f2 == 13 and w2 == 2:
                        info['vod_remarks'] = v2.decode('utf-8', 'replace')
                    elif f2 == 1 and w2 == 2:
                        info['_area'] = v2.decode('utf-8', 'replace')
                    elif f2 == 14 and w2 == 0:
                        info['_year'] = str(v2)
                    elif f2 == 15 and w2 == 2:
                        info['_class'] = v2.decode('utf-8', 'replace')
                if info['vod_id']:
                    out.append(info)
        except Exception:
            pass
        return out

    def _history(self):
        out = []
        try:
            d = urllib.request.urlopen(urllib.request.Request(
                HOST + '/api/ex/v3/user/history?username=fzcrym',
                headers={'User-Agent': UA, 'Accept': 'application/json'}),
                timeout=20).read()
            for it in json.loads(d).get('data') or []:
                vid = it.get('videoId', '')
                if '|' in vid:
                    frm, url = vid.split('|', 1)
                    out.append({'vod_id': 'h$%s$%s' % (frm, url),
                                'vod_name': it.get('videoName', ''),
                                'vod_pic': it.get('videoCover', ''),
                                'vod_remarks': '%s·第%s集' % (
                                    frm, it.get('videoPart', ''))})
        except Exception:
            pass
        return out

    # ---------- 详情 ----------
    def detailContent(self, ids):
        vid = ids[0]
        out = {'vod_id': vid}
        if vid.startswith('h$'):
            _, frm, url = vid.split('$', 2)
            return {'list': [dict(out, vod_name='继续观看',
                                  vod_play_from=frm,
                                  vod_play_url='正片$%s' % url,
                                  vod_pic='', vod_content='播放历史·线路:' + frm)]}
        try:
            d = self._proto_request('/api/proto/v5/drama/getDetail', 'id=' + vid)
            top = _pb(d)
            data = [v for fn, wt, v in top if fn == 3 and wt == 2][0]
            # 详情字段
            for fn, wt, v in _pb(data):
                if fn > 100:
                    break
                if fn == 9 and wt == 2 and 'vod_name' not in out:
                    out['vod_name'] = v.decode('utf-8', 'replace')
                elif fn == 2 and wt == 2 and 'vod_pic' not in out:
                    pics = [x.decode('utf-8', 'replace')
                            for f3, w3, x in _pb(v)
                            if w3 == 2 and x.startswith(b'http')]
                    if pics:
                        out['vod_pic'] = next(
                            (u for u in pics if u.startswith('https')), pics[0])
                elif fn == 6 and wt == 2 and 'vod_content' not in out:
                    out['vod_content'] = re.sub(
                        r'<[^>]+>', '', v.decode('utf-8', 'replace'))
            # 分集：扫描 0xEA01 tag
            lines, order = {}, []
            pos, n = 0, len(data)
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
                    if f3_ == 2 or f3_ == 3:
                        title = v3_.decode('utf-8', 'replace')
                    elif f3_ == 4:
                        pth = v3_.decode('utf-8', 'replace')
                    elif f3_ == 9:
                        src = v3_.decode('utf-8', 'replace')
                    elif f3_ == 10:
                        src_cn = v3_.decode('utf-8', 'replace')
                if not pth:
                    continue
                mm = re.match(r'^第?0*(\d{1,4})[集话期](?:完结)?$', title)
                if mm:
                    title = mm.group(1)
                line = src_cn or src or '正片'
                if line not in lines:
                    lines[line] = []
                    order.append(line)
                if re.search(r'(?i)\.(mp4|m3u8|flv|mkv|avi|ts|mov|mpd|m4a|wmv)(\?.*)?$', pth):
                    ep_url = pth
                else:
                    ep_url = base64.b64encode(json.dumps(
                        {'vodPlayFrom': src, 'playUrl': pth},
                        separators=(',', ':')).encode()).decode()
                if ep_url.startswith('http'):
                    ep_url = urllib.parse.quote(ep_url, safe=':/?&=%#@+~')
                lines[line].append('%s$%s' % (title or '正片', ep_url))
            def _rank(nm):
                if '超高清' in nm:
                    return 0
                if '蓝光' in nm:
                    return 1
                return 2
            order.sort(key=lambda x: (_rank(x), x))
            if order:
                out['vod_play_from'] = '$$$'.join(order)
                out['vod_play_url'] = '$$$'.join(
                    '#'.join(lines[l]) for l in order)
            else:
                out['vod_play_from'] = '橘汁'
                out['vod_play_url'] = '暂无片源$http://'
        except Exception:
            out['vod_name'] = vid
            out['vod_play_from'] = '橘汁'
            out['vod_play_url'] = '播放$http://'
        return {'list': [out]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg=1):
        try:
            qs = 'page=%s&pagesize=24&searchKeys=%s' % (pg or 1, key)
            d = self._proto_request('/api/proto/v5/drama/search', qs)
            top = _pb(d)
            code = [v for fn, wt, v in top if fn == 1 and wt == 0]
            if (code[0] if code else 0) != 200:
                return {'list': [], 'page': int(pg or 1)}
            datas = [v for fn, wt, v in top if fn == 3 and wt == 2]
            out = []
            if datas:
                for fn, wt, v in _pb(datas[0]):
                    if wt != 2 or fn == 0 or fn > 100:
                        continue
                    item = {'vod_id': '', 'vod_name': '', 'vod_pic': '',
                            'vod_remarks': ''}
                    for f3, w3, v3 in _pb(v):
                        if not (w3 == 2 or (f3 == 3 and w3 == 0)):
                            continue
                        if f3 == 3 and w3 == 0:
                            item['vod_id'] = str(v3)
                        elif f3 == 5:
                            item['vod_name'] = v3.decode('utf-8', 'replace')
                        elif f3 == 2:
                            pics = [x.decode('utf-8', 'replace')
                                    for _, w4, x in _pb(v3)
                                    if w4 == 2 and x.startswith(b'http')]
                            if pics:
                                item['vod_pic'] = next(
                                    (u for u in pics if u.startswith('https')), pics[0])
                        elif f3 == 13:
                            item['vod_remarks'] = v3.decode('utf-8', 'replace')
                    if item['vod_id'] and item['vod_name']:
                        out.append(item)
            return {'list': out, 'page': int(pg or 1)}
        except Exception:
            return {'list': [], 'page': 1}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        if id and not id.startswith('http') and '$' in id:
            id = id.split('$', 1)[1]
        url = id
        try:
            if id and not id.startswith('http') and not id.startswith('h$'):
                jm = json.loads(base64.b64decode(id))
                qs = 'vodPlayFrom=%s&playUrl=%s' % (
                    urllib.parse.quote(jm.get('vodPlayFrom', '')),
                    urllib.parse.quote(jm.get('playUrl', ''), safe=''))
                d = self._proto_request('/api/proto/v5/videoUsableUrl', qs)
                top = _pb(d)
                code = [v for fn, wt, v in top if fn == 1 and wt == 0]
                if (code[0] if code else 0) == 200:
                    data = [v for fn, wt, v in top if fn == 3 and wt == 2]
                    if data:
                        mm = re.search(rb'https?://[\x21-\x7e]+', data[0])
                        if mm:
                            url = mm.group(0).decode('utf-8', 'replace')
            elif not url.startswith('http'):
                url = 'http://'
        except Exception:
            pass
        return {'parse': 0, 'playUrl': '', 'url': url,
                'header': {'User-Agent': UA}}

    def isVideoFormat(self, url):
        return True

    def isTextFormat(self, url):
        return False

    def localProxy(self, param):
        return [404, 'text/plain', b'']

    def destroy(self):
        pass


# ---------- 模块级转发（TVBox 按模块函数名调用） ----------
_inst = None


def _sp():
    global _inst
    if _inst is None:
        _inst = Spider()
    return _inst


def getName():
    return _sp().getName()


def init(extend=''):
    return _sp().init(extend)


def homeContent(filter=None):
    return _sp().homeContent(filter)


def homeVideoContent():
    return _sp().homeVideoContent()


def categoryContent(tid, pg=1, filter=None, extend=None):
    return _sp().categoryContent(tid, pg, filter, extend)


def detailContent(ids):
    return _sp().detailContent(ids)


def searchContent(key, quick=False, pg=1):
    return _sp().searchContent(key, quick, pg)


def searchContentPage(key, quick=False, pg=1):
    return _sp().searchContent(key, quick, pg)


def playerContent(flag, id, vipFlags=None):
    return _sp().playerContent(flag, id, vipFlags)


def localProxy(param):
    return _sp().localProxy(param)


def isVideoFormat(url):
    return _sp().isVideoFormat(url)


def isTextFormat(url):
    return _sp().isTextFormat(url)


def manualVideoCheck():
    return False


def getDependence():
    return []


def destroy():
    return _sp().destroy()
