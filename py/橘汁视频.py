# -*- coding: utf-8 -*-
# 橘汁视频 TVBox 爬虫源
# 逆向自 xiaosa/spider.jar 的 com.github.catvod.spider.AppDrama
#
# 协议要点(反编译确证):
#   1) init 时先 /api/v5/find/app/zone 握手, RSARequest(protobuf) 换回动态 RSA 公钥(this.d)
#   2) 此后所有请求头的 sig 用【动态公钥】做 RSA/ECB/PKCS1 加密(timestamp+random_str+vApp)
#      sig2/sig3 用 AES-ECB(dataIv) 加密同一串后拆前后两段; paramsData 用 AES-CBC(KN,KN) 加密设备JSON
#   3) proto/v5 接口: 请求体 = SecureRequest(protobuf), 内层把 query+ts 用 AES-ECB(dataKey) 加密后拼 random_str
#      响应 = ApiResult(protobuf) -> 业务对象(protobuf)
#   4) tag/list 与 getCategory 走 JSON(GET, 仅 paramsData 不含 sig):
#      tag/list 的 data 字段需双层 AES-ECB(dataKey -> dataIv) 解密
#   KN = jar 硬编码 "ed5fdsgucxumegqa" (KEY_NATIVE), 用作 paramsData / e() 的 AES-CBC 密钥(同时作 IV)
#
#
# ---- 2026-11-17 修复记录 ----
# 1) 站点换域名: juziapp.hzhcbkj.cn 已 502 -> juziappcc.hzhcbkj.cn
#    旧配置分发 app.txt 所在 COS 桶欠费(UnavailableForLegalReasons), 新分发在 123clouddisk CDN
# 2) init 原来只在 host 为空时才读 site, 域名一换就死锁在写死的旧域名; 改为"先读分发文件,
#    再用候选域名逐个 zone 探活", 并且 ext 里的旧 site 拉不到时自动回落到内置新地址
# 3) 分类/搜索分页原来写死 pagecount=9999 / total=99999, 改为解析响应 field 16 的真实总数
#    (实测 剧集 43642 / 搜索 24360), 壳不再无限翻页
# 4) 播放直链缓存原来永久生效, token 过期后必 403; 改为 600s TTL
# 5) 请求超时 25s -> 14s、重试 2 -> 1, 避免壳端长时间转圈
# 依赖: 仅标准库 + pycryptodome(Crypto), 无需 protobuf 运行库(自带纯 Python protobuf 编解码)
import sys, json, base64, ssl, time, random, re, string, uuid, html
import urllib.request, urllib.error, urllib.parse
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.Util.Padding import pad
from Crypto.PublicKey import RSA

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider:
        pass

try:
    import requests as _requests
except Exception:
    _requests = None

KN = b'ed5fdsgucxumegqa'          # KEY_NATIVE (jar 硬编码)
# 配置分发地址（内含 {"domain": "..."}）。旧地址 123-1319...cos.../app.txt 的桶已欠费 403，
# 这是本次"整源空白"的根因之一；ext 里若仍传旧 site，_resolve_domain 会自动回落到这里。
SITE_FALLBACK = 'https://1848463092.cdn.123clouddisk.com/1848463092/cct/az.txt'
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
HN = string.ascii_letters + string.digits
VIDEO_RE = re.compile(r'(?i).*\.(mp4|m3u8|flv|mkv|avi|ts|mov|mpd|m4a|wmv)(\?.*)?$')

# 图片是否附加 @Referer/@User-Agent 后缀(TVBox 壳侧拆分转请求头)。
# 本站图床无防盗链, 默认关闭; 如某图床需带 Referer 才能取图, 置 True。
PIC_HEADER_SUFFIX = False


# ---------------- 纯 Python protobuf 编解码 ----------------
def _enc_varint(n):
    out = bytearray()
    while True:
        b = n & 0x7f
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _enc_tag(field, wt):
    return _enc_varint((field << 3) | wt)


def enc_str(field, s):
    b = s.encode('utf-8') if isinstance(s, str) else s
    return _enc_tag(field, 2) + _enc_varint(len(b)) + b


def enc_var(field, n):
    return _enc_tag(field, 0) + _enc_varint(n)


def _dec_fields(buf):
    out = []
    i, n = 0, len(buf)
    while i < n:
        tag = 0
        shift = 0
        while True:
            b = buf[i]
            i += 1
            tag |= (b & 0x7f) << shift
            if not (b & 0x80):
                break
            shift += 7
        field = tag >> 3
        wt = tag & 7
        if wt == 0:
            val = 0
            shift = 0
            while True:
                b = buf[i]
                i += 1
                val |= (b & 0x7f) << shift
                if not (b & 0x80):
                    break
                shift += 7
            out.append((field, wt, val))
        elif wt == 2:
            ln = 0
            shift = 0
            while True:
                b = buf[i]
                i += 1
                ln |= (b & 0x7f) << shift
                if not (b & 0x80):
                    break
                shift += 7
            val = buf[i:i + ln]
            i += ln
            out.append((field, wt, val))
        elif wt == 1:
            val = buf[i:i + 8]
            i += 8
            out.append((field, wt, val))
        elif wt == 5:
            val = buf[i:i + 4]
            i += 4
            out.append((field, wt, val))
        else:
            break
    return out


def dec_msg(buf):
    """buf -> {field: [(wiretype, value), ...]}"""
    d = {}
    for f, wt, v in _dec_fields(buf):
        d.setdefault(f, []).append((wt, v))
    return d


def fld(m, fn):
    v = m.get(fn)
    if not v:
        return ''
    val = v[0][1]
    if isinstance(val, bytes):
        return val.decode('utf-8', 'replace')
    return val


def _unpad(b):
    return b[:-b[-1]] if b and 0 < b[-1] <= 16 else b


# ---------------- 爬虫主体 ----------------
class Spider(_BaseSpider):
    def __init__(self):
        # 以下为验证过的橘汁真实默认值, 即使 ext 不传也能全链路跑通
        self.host = 'http://juziappcc.hzhcbkj.cn'
        self.dkey = ''          # 动态 RSA 公钥(this.d), init 时由 zone 握手获得
        self.publicKey = 'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCr8SzZhjYy+rsya1K09t8d2K50pWFoBkgUqMpKOiW+3IEVKd4eTdvg9RSOjQ82kypL6R9BnsmrS1V8s4PVDwjQbUtYhTPPC9Hz16qY7rpD6m0d2vr09/UpWQ5uOy9PR0QTrsioveZ+DIe9jc3C+zBCu/kZSY/R8stwJoiitki3gwIDAQAB'
        self.dataKey = 'ZU1DSFFWNENKMDYXVUQRN0ZJDUC4PQ=='
        self.dataIv = 'OC1A06E197EF10CF3F6058CA7A803B5E'
        self.pkg = 'com.asjdhjhd.mgd.p3'
        self.appName = '橘汁'
        self.version = '3.0.7.0'
        self.decrypt = '1'
        self.site = 'https://1848463092.cdn.123clouddisk.com/1848463092/cct/az.txt'
        self._cache = {}
        # ---- 壳工程底座(移植自虫虫电影网.py) ----
        # 三级传输兜底: requests.Session 优先, 缺失则 urllib 降级; 三别名兼容不同壳调用习惯
        self.s = self.session = self.sess = _requests.Session() if _requests else None
        if self.s is not None:
            self.s.verify = False
        self._pcache = {}      # 播放直链缓存: 壳起播/切线路/重试重复请求时省一次站点往返
        self._siteKey = ''
        self._vflags = {}

    # ---------- 工具 ----------
    def _f(self, n):
        return ''.join(random.choice(HN) for _ in range(n - 1)) + '='

    def _device(self):
        u = uuid.uuid4().hex.upper()
        return {
            'country': 'CN', 'vName': self.version, 'cpuId': 'MT6893Z%2FCZA', 'young': 0,
            'facturer': 'OnePlus', 'pkg': self.pkg, 'uuid': u, 'resolution': '1080x2272',
            'mac': '02%3A00%3A00%3A00%3A00%3A00', 'abid': '397', 'model': 'PJZ110',
            'plat': 'android', 'udid': u, 'dpi': '440', 'net': '1', 'lang': 'zh',
            'brand': 'OnePlus', 'density': '2.75', 'appName': self.appName,
            'cpu': 'arm64-v8a', 'chid': '10000', 'carrier': '%E8%81%94%E9%80%9A',
            '_vOsCode': 33, 'vOs': '13', 'v': 1, 'tenantId': '',
            'vApp': self.version.replace('.', ''), 'device': 0, 'androidID': u[:16],
        }

    def _rsa(self, msg, key):
        pem = '-----BEGIN PUBLIC KEY-----\n' + key + '\n-----END PUBLIC KEY-----'
        return base64.b64encode(PKCS1_v1_5.new(RSA.import_key(pem)).encrypt(msg.encode())).decode()

    def _ecb_b64(self, pt, key):
        return base64.b64encode(AES.new(key.encode(), AES.MODE_ECB).encrypt(pad(pt.encode(), 16))).decode()

    def _cbc_hex(self, pt):
        return AES.new(KN, AES.MODE_CBC, KN).encrypt(pad(pt, 16)).hex()

    def _e_headers(self):
        pt = json.dumps(self._device(), separators=(',', ':')).encode()
        pd = self._cbc_hex(pt)
        return {'User-Agent': 'okhttp/3.12.1', 'Accept': 'application/json',
                'Content-Type': 'application/json; charset=utf-8',
                'publicParams': json.dumps({'paramsData': pd}, separators=(',', ':'))}

    def _c_headers(self, key=None):
        rsa_key = key or self.dkey or self.publicKey
        dev = self._device()
        ts = int(time.time() * 1000)
        rnd = self._f(16)
        vApp = dev.get('vApp', '3019')
        dev['sig'] = self._rsa(str(ts) + rnd + vApp, rsa_key)
        e2 = self._ecb_b64(str(ts) + rnd, self.dataIv)
        dev['random_str'] = rnd
        dev['timestamp'] = ts
        dev['sig2'] = e2[:8]
        dev['sig3'] = e2[8:]
        pt = json.dumps(dev, separators=(',', ':')).encode()
        pd = self._cbc_hex(pt)
        return {'User-Agent': 'okhttp/3.12.1', 'Accept': 'application/x-protobuf',
                'Content-Type': 'application/x-protobuf',
                'publicParams': json.dumps({'paramsData': pd}, separators=(',', ':'))}

    def _secure_body(self, params):
        qs = '&'.join('%s=%s' % (k, params[k]) for k in params if params.get(k))
        ts = int(time.time() * 1000)
        rs = self._f(8)
        af = self._f(20)
        body = qs + str(ts)
        aes_enc = self._ecb_b64(body, self.dataKey)
        combined = rs + aes_enc
        b = bytearray()
        b += enc_str(1, combined[:20])
        b += enc_str(2, combined[20:])
        b += enc_str(3, af)
        b += enc_var(4, ts)
        b += enc_str(5, rs)
        return bytes(b)

    def _request(self, url, data=None, headers=None, timeout=20, raw=False):
        """统一传输入口: requests 优先, 缺失则 urllib 兜底(三级传输兜底)。"""
        h = headers or {'User-Agent': 'okhttp/3.12.1'}
        if self.s is not None:
            try:
                if data is not None:
                    r = self.s.post(url, data=data, headers=h, timeout=timeout)
                else:
                    r = self.s.get(url, headers=h, timeout=timeout)
                if r.status_code < 400:
                    return r.content if raw else r.content.decode('utf-8', 'replace')
            except Exception:
                pass
        req = urllib.request.Request(url, data=data, headers=h)
        resp = urllib.request.urlopen(req, timeout=timeout, context=CTX).read()
        return resp if raw else resp.decode('utf-8', 'replace')

    def _get(self, url, headers=None, raw=False, timeout=20):
        return self._request(url, data=None, headers=headers, timeout=timeout, raw=raw)

    def _proto_post(self, path, params, retry=1):
        last = None
        for _ in range(retry + 1):
            try:
                data = self._secure_body(params)
                return self._request(self.host + path, data=data,
                                     headers=self._c_headers(), timeout=14, raw=True)
            except Exception as e:
                last = e
                time.sleep(0.4)
        raise last

    def _json_get(self, path, retry=1):
        last = None
        for _ in range(retry + 1):
            try:
                return json.loads(self._request(self.host + path,
                                                headers=self._e_headers(), timeout=14))
            except Exception as e:
                last = e
                time.sleep(0.4)
        raise last

    def _api(self, raw):
        m = dec_msg(raw)
        code = m.get(1, [(0, 0)])[0][1]
        msg = m.get(2, [(b'', 0)])[0][1]
        data = m.get(3, [(b'', 0)])[0][1]
        msg = msg.decode() if isinstance(msg, bytes) else msg
        data = data if isinstance(data, bytes) else b''
        return code, msg, data

    def _decrypt(self, b64str):
        s1 = _unpad(AES.new(self.dataKey.encode(), AES.MODE_ECB)
                    .decrypt(base64.b64decode(b64str))).decode()
        s2 = _unpad(AES.new(self.dataIv.encode(), AES.MODE_ECB)
                    .decrypt(base64.b64decode(s1)))
        return s2.decode('utf-8', 'replace')

    # ---------- 握手 ----------
    def _zone(self, timeout=12):
        ts = int(time.time() * 1000)
        rnd = self._f(16)
        sign = self._rsa(str(ts) + rnd, self.publicKey)
        b = bytearray()
        b += enc_var(1, ts)
        b += enc_str(2, sign)
        b += enc_str(3, self._f(16))
        b += enc_str(4, rnd)
        b += enc_str(5, self._f(16))
        raw = self._request(self.host + '/api/v5/find/app/zone', data=bytes(b),
                            headers=self._c_headers(self.publicKey), timeout=timeout, raw=True)
        _, _, data = self._api(raw)
        m = dec_msg(data)
        s2 = fld(m, 2)
        s3 = fld(m, 3)
        s4 = fld(m, 4)
        s5 = fld(m, 5)
        return (s2 + s3 + s4 + s5)

    def _resolve_domain(self):
        """从配置分发文件取当前 API 域名。

        站点会不定期换域名（juziapp → juziappcc），分发文件是唯一稳定入口；
        读不到就退回内置候选，保证离线也能起。
        """
        sites = []
        for u in (self.site, SITE_FALLBACK):
            if u and u not in sites:
                sites.append(u)
        for site in sites:
            for _ in range(2):
                try:
                    txt = self._get(site, headers={'User-Agent': 'okhttp/3.12.1'},
                                    timeout=8).strip()
                except Exception:
                    continue
                if not txt:
                    continue
                if txt.startswith('{'):
                    try:
                        j = json.loads(txt)
                    except Exception:
                        continue
                    u = str(j.get('domain') or j.get('host') or j.get('api') or '').strip()
                else:
                    u = txt.split()[0]
                if u.startswith('http'):
                    return u.rstrip('/')
        return ''


    # ---------- 解析 ----------
    def _beans(self, raw):
        out = []
        for wt, v in dec_msg(raw).get(1, []):
            b = dec_msg(v)
            cid = str(fld(b, 3))
            name = fld(b, 5)
            ci = b.get(2, [(b'', 0)])[0][1]
            pic = ''
            if ci:
                ci2 = dec_msg(ci)
                if ci2.get(2):
                    pic = fld(ci2, 2)
                elif ci2.get(1):
                    pic = fld(ci2, 1)
            rem = fld(b, 13)
            if cid and name:
                out.append({'vod_id': cid, 'vod_name': name, 'vod_pic': self._pic(pic), 'vod_remarks': rem})
        return out

    def _paged(self, path, params, pg, size=21):
        """发分页请求并解析真实总数（响应 field 16 就是 total，实测 43642/24360）。"""
        raw = self._proto_post(path, params)
        code, _, data = self._api(raw)
        items = self._beans(data)
        total = 0
        v = dec_msg(data).get(16)
        if v and v[0][0] == 0:
            try:
                total = int(v[0][1])
            except Exception:
                total = 0
        if total > 0:
            pages = max(1, (total + size - 1) // size)
        else:
            # 拿不到总数时按"本页有无数据"推断，避免固定 9999 让壳无限翻页
            pages = pg + 1 if items else pg
        return items, total, pages

    def _video_flag(self, path, source):
        if VIDEO_RE.match(path or ''):
            return path
        return base64.b64encode(
            json.dumps({'vodPlayFrom': source, 'playUrl': path}).encode()).decode()

    def _pic(self, src):
        """图片地址归一(移植自虫虫电影网.py)。

        ★幂等: 重复解析不得叠加后缀; 已带 proxy 前缀的旧版遗留先剥离
          (必须在归一前剥, 否则 proxy?url= 会被当相对路径拼到域名后)。
        ★图片 UA 墙正解: TVBox 生态图片请求头走 URL 后缀约定, 壳侧拆分后自动转成
          请求头 <URL>@Referer=<ref>@User-Agent=<ua>; 本站图床无防盗链, 默认不挂后缀。
        """
        u = (src or '').strip()
        if not u:
            return u
        if u.startswith('proxy?url='):
            u = u[len('proxy?url='):]
            if '%' in u:
                u = urllib.parse.unquote(u)
        elif u.startswith('proxy://'):
            u = u[len('proxy://'):]
        if u.startswith('//'):
            u = 'https:' + u
        if not u.startswith('http'):
            return u
        if not PIC_HEADER_SUFFIX:
            return u
        if ('@User-Agent=' in u or '@Referer=' in u
                or '@Cookie=' in u or '@Headers=' in u):
            return u
        return u + '@Referer=' + self.host + '/@User-Agent=okhttp/3.12.1'

    # ---------------- TVBox 接口 ----------------
    def init(self, extend=''):
        cfg = {}
        if extend:
            try:
                cfg = json.loads(extend) if isinstance(extend, str) else extend
            except Exception:
                cfg = {}
        if isinstance(cfg, dict):
            self.appName = cfg.get('appName', self.appName)
            self.publicKey = cfg.get('publicKey', self.publicKey)
            self.dataKey = cfg.get('dataKey', self.dataKey)
            self.dataIv = cfg.get('dataIv', self.dataIv)
            self.pkg = cfg.get('pkg', self.pkg)
            self.version = cfg.get('version', self.version)
            self.decrypt = cfg.get('decrypt', self.decrypt)
            self.site = cfg.get('site', self.site)
            self.host = cfg.get('host', self.host) or self.host
        self.dkey = ''

        # 候选顺序：配置分发域名 → 传入/内置域名 → 历史域名。
        # 必须"先探活再定 host"：旧版只在 host 为空时才读分发文件，
        # 于是域名一换就死锁在写死的旧域名上（正是本次故障的成因）。
        cands = []
        dist = self._resolve_domain()
        for h in (dist, self.host, 'http://juziappcc.hzhcbkj.cn',
                  'https://juziapp.hzhcbkj.cn'):
            if h and h.rstrip('/') not in cands:
                cands.append(h.rstrip('/'))
        for h in cands:
            self.host = h
            try:
                k = self._zone(timeout=10)
            except Exception:
                k = ''
            if k and len(k) >= 64:
                self.dkey = k
                return self.host
        # 全部不可用：保留最可信的域名，让上层拿到明确失败而不是空 host
        self.host = dist or self.host or 'http://juziappcc.hzhcbkj.cn'
        self.dkey = self.publicKey
        return self.host

    def getName(self):
        return '橘汁视频'

    def isVideoFormat(self, url):
        return bool(VIDEO_RE.match(url or ''))

    def manualVideoCheck(self):
        return False

    # ---------- 壳工程底座回调(移植自虫虫电影网.py, 提升跨壳兼容性) ----------
    def getDependence(self):
        return []

    def destroy(self):
        try:
            if self.s is not None:
                self.s.close()
        except Exception:
            pass

    def progressVideo(self, speed=0, time=0, end=0):
        # 壳播放进度回调; 无弹幕/进度联动需求直接 False
        return False

    def setVideoFlags(self, siteKey='', flags=None):
        # 壳视频标记回调(海阔/影视仓等扩展壳会调); 记录即可
        try:
            self._siteKey = siteKey or self._siteKey
            self._vflags = flags if isinstance(flags, dict) else dict()
        except Exception:
            pass
        return None

    def action(self, action):
        return {}

    def homeVideoContent(self):
        # 部分壳的"首页视频"快捷入口; 复用推荐墙
        try:
            return {'list': self.homeContent(0).get('list', [])}
        except Exception:
            return {'list': []}

    def localProxy(self, param):
        """本地代理兜底(m3u8 分片/KEY、图片代取)。

        ★返回必须是 dict 契约 {'code','content','headers'}(71模板/FongMi 实证);
          list 格式 [status,ctype,body,None] 壳不认, 是资源空白的经典原因。
        ★参数兼容 dict(url/u/key 键) 与裸串; 统一剥离 proxy?url=/proxy:// 前缀并 unquote。
        """
        u = ''
        if isinstance(param, dict):
            u = str(param.get('url') or param.get('u') or param.get('key') or '')
        else:
            u = str(param or '')
        if u.startswith('proxy?url='):
            u = u[len('proxy?url='):]
        elif 'proxy?url=' in u:
            u = u.split('proxy?url=', 1)[-1]
        if u.startswith('proxy://'):
            u = u[len('proxy://'):]
        if '%' in u:
            u = urllib.parse.unquote(u)
        if not u or not u.startswith('http'):
            return {'code': 403, 'content': b'', 'headers': {}}
        h = {'User-Agent': 'okhttp/3.12.1', 'Referer': self.host + '/'}
        try:
            if self.s is not None:
                r = self.s.get(u, headers=h, timeout=15)
                if r.status_code == 200 and r.content:
                    return {'code': 200, 'content': r.content,
                            'headers': {'Content-Type': r.headers.get('Content-Type', 'application/octet-stream')}}
                return {'code': r.status_code, 'content': b'', 'headers': {}}
        except Exception:
            pass
        try:
            req = urllib.request.Request(u, headers=h)
            with urllib.request.urlopen(req, timeout=15, context=CTX) as resp:
                body = resp.read()
                if body:
                    return {'code': 200, 'content': body,
                            'headers': {'Content-Type': resp.headers.get('Content-Type', 'application/octet-stream')}}
        except Exception:
            pass
        return {'code': 404, 'content': b'', 'headers': {}}

    def homeContent(self, filter_):
        # 一次取 tag/list(解密后含: 分类标签块 typeId/typeName + 推荐墙块 sections.vodList)
        arr = []
        try:
            j = self._json_get('/api/ex/v3/security/tag/list')
            data = j.get('data', '')
            if data:
                try:
                    arr = json.loads(self._decrypt(data)) if self.decrypt != '0' else json.loads(data)
                except Exception:
                    try:
                        arr = json.loads(data)
                    except Exception:
                        arr = []
        except Exception:
            arr = []

        # 1) 分类标签: 取带 typeId/typeName 的块(旧 getCategory 接口已废, 改从 tag/list 抽)
        classes = []
        for obj in arr:
            tid = obj.get('typeId')
            nm = obj.get('typeName')
            if tid and nm and str(nm) != '公告':
                classes.append({'type_name': str(nm), 'type_id': str(tid)})

        # 2) 静态兜底分类: 即便 tag/list 全挂, 首页也保证有分类标签可点
        if not classes:
            for tid, nm in [('21', '剧集'), ('20', '电影'), ('22', '综艺'), ('23', '动漫'),
                            ('24', '短剧'), ('26', '漫剧'), ('25', '直播')]:
                classes.append({'type_name': nm, 'type_id': tid})

        # 3) 推荐墙: 遍历各块的 sections.vodList
        wall = []
        for obj in arr:
            for sec in obj.get('sections', []) or []:
                for v in sec.get('vodList', []) or []:
                    cid = str(v.get('id', ''))
                    name = v.get('name', '')
                    pic = (v.get('coverImage') or {}).get('path', '')
                    if cid and name:
                        wall.append({'vod_id': cid, 'vod_name': name,
                                     'vod_pic': self._pic(pic), 'vod_remarks': v.get('remark', '')})

        # 4) 降级: 推荐墙为空时, 用第一个分类的 proto 列表填充, 保证首页有内容
        if not wall:
            try:
                tid = classes[0]['type_id']
                raw = self._proto_post('/api/proto/v5/drama/category',
                                      {'typeId1': tid, 'page': '1', 'pagesize': '21',
                                       'vodOrderBy': '最新'})
                _, _, data = self._api(raw)
                wall = self._beans(data)
            except Exception:
                pass
        return {'class': classes, 'filters': {}, 'list': wall,
                'page': 1, 'pagecount': 1, 'total': len(wall), 'limit': len(wall)}

    def categoryContent(self, tid, pg, filter_, ext):
        try:
            tid = int(tid)
        except Exception:
            tid = 20
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        params = {'typeId1': str(tid), 'page': str(pg), 'pagesize': '21',
                  'vodOrderBy': '最新'}
        if ext and isinstance(ext, dict):
            for k, src in (('vodArea', 'area'), ('vodLang', 'lang'),
                           ('vodClass', 'class'), ('vodYear', 'year'),
                           ('vodOrderBy', 'extend_sort')):
                if ext.get(src):
                    params[k] = ext[src]
        items, total, pages = [], 0, pg
        try:
            items, total, pages = self._paged('/api/proto/v5/drama/category', params, pg)
        except Exception:
            pass
        return {'list': items, 'page': pg, 'pagecount': pages,
                'total': total or len(items), 'limit': len(items)}

    def detailContent(self, ids):
        vid = ids[0] if ids else ''
        dm = {}
        try:
            raw = self._proto_post('/api/proto/v5/drama/getDetail', {'id': str(vid)})
            _, _, data = self._api(raw)
            dm = dec_msg(data)
        except Exception:
            pass
        name = fld(dm, 9)
        actor = fld(dm, 25)
        area = fld(dm, 1)
        year = fld(dm, 18)
        remark = fld(dm, 26)
        intro = fld(dm, 6)
        ci = dm.get(2, [(b'', 0)])[0][1]
        pic = ''
        if ci:
            ci2 = dec_msg(ci)
            if ci2.get(1):
                pic = fld(ci2, 1)
            elif ci2.get(2):
                pic = fld(ci2, 2)
        groups = {}
        for wt, v in dm.get(29, []):
            vm = dec_msg(v)
            title = fld(vm, 2) or '1'
            path = fld(vm, 4)
            source = fld(vm, 9)
            source_cn = fld(vm, 10) or '橘子'
            flag = self._video_flag(path, source)
            groups.setdefault(source_cn, []).append('%s$%s' % (title, flag))
        froms = list(groups.keys())
        urls = ['#'.join(groups[s]) for s in froms]
        if not froms:
            print('[橘汁] 详情无线路 id=%s name=%s' % (vid, name))
        return {'list': [{
            'vod_id': vid, 'vod_name': name or str(vid), 'vod_pic': self._pic(pic),
            'vod_actor': actor, 'vod_area': area, 'vod_year': year,
            'vod_remarks': remark, 'vod_content': (intro or '')[:500],
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }]}

    def playerContent(self, flag, id, vipFlags):
        fid = id or ''
        if VIDEO_RE.match(fid):
            return {'parse': 0, 'url': fid, 'header': {'User-Agent': 'okhttp/3.12.1'}}
        try:
            obj = json.loads(base64.b64decode(fid).decode())
        except Exception:
            return {'parse': 0, 'url': fid, 'header': {}}
        # 播放直链缓存：壳起播/切线路/重试常重复请求同一集，命中则省一次站点往返。
        # ★必须带 TTL：这些直链多数带 token/时间戳，15 分钟前的结果复用会直接 403。
        hit = self._pcache.get(fid)
        if hit and time.time() - hit[1] < 600:
            return {'parse': 0, 'url': hit[0], 'header': {'User-Agent': 'okhttp/3.12.1'}}
        url, header = '', {}
        try:
            raw = self._proto_post('/api/proto/v5/videoUsableUrl',
                                   {'vodPlayFrom': obj.get('vodPlayFrom', ''),
                                    'playUrl': obj.get('playUrl', '')})
            code, msg, data = self._api(raw)
            pm = dec_msg(data)
            url = fld(pm, 1)
            if not url:
                print('[橘汁] videoUsableUrl 空结果 code=%s msg=%s' % (code, msg))
            for wt, hv in pm.get(6, []):
                hm = dec_msg(hv)
                k = fld(hm, 1)
                if k:
                    header[k] = fld(hm, 2)
        except Exception:
            pass
        if url:
            if len(self._pcache) > 300:
                self._pcache.pop(next(iter(self._pcache)), None)
            self._pcache[fid] = (url, time.time())
        if not header:
            header = {'User-Agent': 'okhttp/3.12.1'}
        return {'parse': 0, 'url': url, 'header': header}

    def searchContent(self, key, quick, pg=1):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        items, total, pages = [], 0, pg
        try:
            items, total, pages = self._paged('/api/proto/v5/drama/search',
                                              {'searchKeys': key, 'page': str(pg),
                                               'pagesize': '21'}, pg)
        except Exception:
            pass
        return {'list': items, 'page': pg, 'pagecount': pages,
                'total': total or len(items), 'limit': len(items)}


# ---------------- 离线自检 ----------------
if __name__ == '__main__':
    EXT = {
        "appName": "橘汁",
        "publicKey": "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCr8SzZhjYy+rsya1K09t8d2K50pWFoBkgUqMpKOiW+3IEVKd4eTdvg9RSOjQ82kypL6R9BnsmrS1V8s4PVDwjQbUtYhTPPC9Hz16qY7rpD6m0d2vr09/UpWQ5uOy9PR0QTrsioveZ+DIe9jc3C+zBCu/kZSY/R8stwJoiitki3gwIDAQAB",
        "dataKey": "ZU1DSFFWNENKMDYXVUQRN0ZJDUC4PQ==",
        "dataIv": "OC1A06E197EF10CF3F6058CA7A803B5E",
        "pkg": "com.asjdhjhd.mgd.p3",
        "site": "https://1848463092.cdn.123clouddisk.com/1848463092/cct/az.txt",
        "version": "3.0.7.0",
        "decrypt": "1",
    }
    # ---- 无配置兜底验证: 即便 ext 完全不传, 也应拿到真实密钥并跑通 ----
    sp0 = Spider()
    sp0.init('')
    assert sp0.publicKey.startswith('MIGf'), '默认公钥未生效'
    h0 = sp0.homeContent(0)
    print('[无ext兜底] host:', sp0.host, '| 动态公钥前20:', sp0.dkey[:20])
    print('[无ext兜底] 分类:', len(h0['class']), '| 推荐墙:', len(h0['list']))
    if h0['class']:
        print('            分类样例:', h0['class'][0])
    if h0['list']:
        print('            墙样例:', h0['list'][0]['vod_name'], '| 海报:', h0['list'][0]['vod_pic'][:50])

    sp = Spider()
    print('\n=== init (zone 握手获取动态公钥, 带完整 ext) ===')
    host = sp.init(json.dumps(EXT))
    print('host:', host, '| 动态公钥前20:', sp.dkey[:20])

    print('\n=== 首页 ===')
    h = sp.homeContent(0)
    print('分类数:', len(h['class']), '| 推荐墙:', len(h['list']))
    if h['class']:
        print('  分类样例:', h['class'][0], h['class'][1] if len(h['class']) > 1 else '')
    if h['list']:
        print('  墙样例:', h['list'][0]['vod_name'], '| 海报:', h['list'][0]['vod_pic'][:50])

    print('\n=== 分类 (取第一个分类) ===')
    if h['class']:
        tid = h['class'][0]['type_id']
        c = sp.categoryContent(tid, 1, '', '')
        print('tid=%s 卡片数:%d' % (tid, len(c['list'])))
        if c['list']:
            print('  样例:', c['list'][0]['vod_name'], '| 海报:', c['list'][0]['vod_pic'][:50])

    print('\n=== 详情 (取墙首条) ===')
    if h['list']:
        vid = h['list'][0]['vod_id']
        d = sp.detailContent([vid])['list'][0]
        print('片名:', d['vod_name'], '| 年份:', d.get('vod_year'))
        print('线路:', d['vod_play_from'])
        print('播放:', d['vod_play_url'][:80])

    print('\n=== 播放解析 (首条首集) ===')
    if h['list']:
        vid = h['list'][0]['vod_id']
        d = sp.detailContent([vid])['list'][0]
        first_flag = d['vod_play_url'].split('$$$')[0].split('#')[0].split('$', 1)[1]
        p = sp.playerContent('', first_flag, [])
        print('解析URL:', (p.get('url') or '')[:90])
        if p.get('header'):
            print('响应头:', list(p['header'].keys()))

    print('\n=== 搜索 爱情 ===')
    s = sp.searchContent('爱情', False, 1)
    print('卡片数:', len(s['list']))
    if s['list']:
        print('  样例:', s['list'][0]['vod_name'])

    print('\n=== 壳工程底座回调 ===')
    print('getDependence:', sp.getDependence())
    print('homeVideoContent 卡片数:', len(sp.homeVideoContent().get('list', [])))
    print('setVideoFlags:', sp.setVideoFlags('juzi', {'hd': 1}))
    print('localProxy(空参):', sp.localProxy({'url': ''}).get('code'))
    lp = sp.localProxy('https://example.com/x.m3u8')
    print('localProxy(裸串) code:', lp.get('code'), '| content类型:', type(lp.get('content')).__name__)
    print('传输层 requests 可用:', sp.s is not None)

    assert len(h['class']) >= 5, '分类不足'
    assert len(h['list']) > 0, '推荐墙为空'
    assert h['class'] and sp.categoryContent(h['class'][0]['type_id'], 1, '', '')['list'], '分类列表为空'
    assert s['list'], '搜索为空'
    print('\n✅ 橘汁视频.py 全接口自检通过')
