# -*- coding: utf-8 -*-
# ik4k.com (MacCMS dsn2 移动端) drpy 源
#
# 旋转盾 /_guard(旋转拼图): 纯 Python 自动求解 —— 取 /_guard/rotate.png 求正确旋转角,
#   按前端算法回填 cookie  guardret = base64(rc4(角度串, guard[:8]))  并探测放行。
#   该盾只校验最终角度(不校验拖动轨迹), 校验通过后服务端下发 _ok8_ 维持会话。
#
# 真机(TVBox/Android)要点(此前"过不了盾/首页转圈"的根因):
#   1) 角度求解用"极向 profile 循环互相关"(粗定位 + 0.25° 精定位), 各采样一次, ~0.2s;
#      旧实现对每个候选角重复旋转采样(~1s+), 盒子侧偏慢会跑不完 deadline。
#   2) rotate.png 一律二进制读取并校验 PNG 魔数, 防止被文本化后求解必然失败。
#   3) 请求显式 Accept-Encoding: identity, 避免响应被压缩而盒子侧未解压导致解析空。
#   4) 每轮过盾前清除陈旧 cookie(guardret/guard/_ok8_/server_session), 否则"旧验证态
#      与新 guard 签名"混用会被判冲突 —— 这是盒子侧过不了盾的直接原因。
#
# 结构要点(实测):
#   首页卡片: <a class="public-list-exp" href="/voddetail/{id}/" title="{名}"> + data-src
#   分类: 首屏无影片(纯 AJAX) -> POST /index.php/ds_api/vod(见 categoryContent 处注释)
#   详情: /voddetail/{id}/ 线路在 anthology-tab, 选集在 anthology-list-box(并行配对)
#   播放: /vodplay/{id}-{sid}-{nid}/  player_aaaa.{url,encrypt}
import sys, re, json, time, html as _html
from urllib.parse import quote
import requests

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = requests.get(url, headers=headers, timeout=15)
            r.encoding = 'utf-8'
            return r

HOST = 'https://www.ik4k.com'
UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 '
      '(KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1')
REFERER = HOST + '/'


# ========== /_guard 旋转盾: 纯 Python 自动求解(无 numpy/PIL/预训练模型) ==========
# 盾机制(实测): /_guard/rotate.png 为 680x250, 左半=挖了圆孔的底图, 右半=圆形拼图块;
#   拖动滑块令 rotation = percentage*360, 松手时提交 cookie:
#       guardret = base64(rc4(currentRotation.toString(), guard[:8]))
#   服务端只校验最终角度(不校验拖动轨迹), 通过后下发 _ok8_ 维持会话。
# 求解依据: 正确角 = 使"拼图块环形灰度 profile"与"孔外底图环形灰度 profile"的归一化
#   互相关(NCC)最大的旋转角(接缝连续性); 与"把照片转正"的图像语义无关, 故不需要任何
#   旋转角度预训练模型(RotNet/ConvNeXt 那类)。

def _rc4_bytes(data, key):
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + ord(key[i % len(key)])) % 256
        s[i], s[j] = s[j], s[i]
    out = bytearray()
    i = j = 0
    for b in data:
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        out.append(b ^ s[(s[i] + s[j]) % 256])
    return bytes(out)


def _sign(text, key):
    """等价前端 a(text,key)=btoa(rc4(text,key))。"""
    import base64
    return base64.b64encode(_rc4_bytes(text.encode('latin-1'), key)).decode('ascii')


def _png_rgba(data):
    """极简 PNG 解码(8bit/非隔行, 支持调色板/灰度/RGB/RGBA) -> (w, h, bytearray RGBA)。"""
    import struct, zlib
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not png')
    pos, meta, idat, plte, trns = 8, None, [], None, None
    while pos < len(data):
        ln = struct.unpack('>I', data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b'IHDR':
            w, h, bd, ct, _c, _f, inter = struct.unpack('>IIBBBBB', chunk)
            if inter or bd != 8:
                raise ValueError('png unsupported bd=%s inter=%s' % (bd, inter))
            meta = (w, h, bd, ct)
        elif typ == b'PLTE':
            plte = chunk
        elif typ == b'tRNS':
            trns = chunk
        elif typ == b'IDAT':
            idat.append(chunk)
        elif typ == b'IEND':
            break
    w, h, bd, ct = meta
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    raw = zlib.decompress(b''.join(idat))
    stride = w * ch
    out = bytearray(w * h * 4)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ft == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 255
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        base = y * w
        for x in range(w):
            if ct == 3:
                idx = line[x]
                o = idx * 3
                r, g, b = plte[o], plte[o + 1], plte[o + 2]
                a = trns[idx] if (trns is not None and idx < len(trns)) else 255
            elif ct == 2:
                o = x * 3
                r, g, b, a = line[o], line[o + 1], line[o + 2], 255
            elif ct == 6:
                o = x * 4
                r, g, b, a = line[o], line[o + 1], line[o + 2], line[o + 3]
            elif ct == 0:
                r = g = b = line[x]
                a = 255
            else:
                o = x * 2
                r = g = b = line[o]
                a = line[o + 1]
            k = (base + x) << 2
            out[k] = r
            out[k + 1] = g
            out[k + 2] = b
            out[k + 3] = a
        prev = line
    return w, h, out


def _solve_angle(data):
    """返回使拼图块与底图接缝最连续的旋转角(度); 图形态不符时抛异常。

    关键优化(真机可跑): 拼图块绕其圆心旋转 θ, 等价于其"极坐标角向 profile"整体循环
    平移 θ。因此只需各采样一次背景环与拼图块环 profile, 用循环互相关粗定位, 再在候选
    附近以 0.25° 步进做平移点积精定位; 不再对每个候选角重复旋转采样, 求解从 ~1s 降到
    ~0.2s, 避免盒子侧 Python 偏慢导致过盾超时。
    """
    import math
    w, h, px = _png_rgba(data)
    half = w // 2

    def region(x0, test):
        sx = sy = cnt = 0
        for y in range(h):
            row = (y * w) << 2
            for x in range(x0, x0 + half):
                if test(px[row + (x << 2) + 3]):
                    sx += x
                    sy += y
                    cnt += 1
        if not cnt:
            return None
        cx, cy = sx / cnt, sy / cnt
        rmax = 0.0
        for y in range(h):
            row = (y * w) << 2
            for x in range(x0, x0 + half):
                if test(px[row + (x << 2) + 3]):
                    d = (x - cx) ** 2 + (y - cy) ** 2
                    if d > rmax:
                        rmax = d
        return cx, cy, math.sqrt(rmax)

    hole = region(0, lambda a: a < 128)          # 底图孔洞(透明)
    piece = region(half, lambda a: a > 128)      # 拼图块(圆)
    if not hole or not piece:
        raise ValueError('guard image unrecognized')
    hcx, hcy, hr = hole
    pcx, pcy, pr = piece
    r0 = min(hr, pr)

    def gray_at(x, y):
        x = 0.0 if x < 0 else (w - 1.001 if x > w - 1.001 else x)
        y = 0.0 if y < 0 else (h - 1.001 if y > h - 1.001 else y)
        x0, y0 = int(x), int(y)
        fx, fy = x - x0, y - y0
        x1, y1 = x0 + 1, y0 + 1
        o00 = (y0 * w + x0) << 2
        o10 = (y0 * w + x1) << 2
        o01 = (y1 * w + x0) << 2
        o11 = (y1 * w + x1) << 2

        def g(o):
            return px[o] * .299 + px[o + 1] * .587 + px[o + 2] * .114
        return (g(o00) * (1 - fx) * (1 - fy) + g(o10) * fx * (1 - fy) +
                g(o01) * (1 - fx) * fy + g(o11) * fx * fy)

    def norm(vals):
        m = sum(vals) / len(vals)
        c = [v - m for v in vals]
        s = math.sqrt(sum(v * v for v in c)) or 1.0
        return c, s

    N, dec, radii = 1440, 4, (2, 6, 10)          # N=1440 -> 0.25°/索引
    cosf = [math.cos(2 * math.pi * i / N) for i in range(N)]
    sinf = [math.sin(2 * math.pi * i / N) for i in range(N)]
    bg_c, bg_n, pc_c, pc_n = {}, {}, {}, {}
    for d in radii:
        rb = r0 + d
        bg_c[d], bg_n[d] = norm([gray_at(hcx + rb * cosf[i], hcy + rb * sinf[i])
                                 for i in range(N)])
        rp = r0 - d
        pc_c[d], pc_n[d] = norm([gray_at(pcx + rp * cosf[i], pcy + rp * sinf[i])
                                 for i in range(N)])

    # 粗定位: 4:1 抽稀 profile 的循环互相关(整度)
    nb = N // dec
    total = [0.0] * nb
    for d in radii:
        B = [bg_c[d][i] for i in range(0, N, dec)]
        P = [pc_c[d][i] for i in range(0, N, dec)]
        bm = sum(B) / nb
        pm = sum(P) / nb
        B = [v - bm for v in B]
        P = [v - pm for v in P]
        bn = math.sqrt(sum(v * v for v in B)) or 1.0
        pn = math.sqrt(sum(v * v for v in P)) or 1.0
        corr = [0.0] * nb
        for i in range(nb):
            bi = B[i]
            if bi == 0.0:
                continue
            for k in range(nb):
                corr[k] += bi * P[(i - k) % nb]
        inv = 1.0 / (bn * pn)
        for k in range(nb):
            total[k] += corr[k] * inv
    k0 = max(range(nb), key=lambda k: total[k])

    def ncc(m):
        tot = 0.0
        for d in radii:
            B, P = bg_c[d], pc_c[d]
            dot = 0.0
            for i in range(N):
                dot += B[i] * P[(i - m) % N]
            tot += dot / (bg_n[d] * pc_n[d])
        return tot / len(radii)

    # 旋转方向二选一(取 NCC 更优), 再在其附近 0.25° 步进精定位
    base = max((k0 * dec, (N - k0 * dec) % N), key=ncc)
    best = None
    for off in range(-16, 17):
        m = (base + off) % N
        v = ncc(m)
        if best is None or v > best[0]:
            best = (v, m)
    return round(best[1] * 360.0 / N, 2)


# 一级分类(顶级 type): 电影 / 电视剧 / 综艺 / 动漫
TOP_TYPES = [
    {'type_id': 'dianying', 'type_name': '电影'},
    {'type_id': 'dianshiju', 'type_name': '电视剧'},
    {'type_id': 'zongyipian', 'type_name': '综艺'},
    {'type_id': 'dongman', 'type_name': '动漫'},
]

# 地区快捷 slug(原二级分类): 作为"电视剧 / 综艺"下的地区筛选值。
# 这些 slug 本身即站点有效分类(vodshow/{slug}-------- 可返回内容), 直接复用
# 作筛选值可保证二级筛选不会出空页(避免之前"二级筛选无内容"的坑)。
AREA_SLUGS = {
    'meiju': '美剧', 'hanju': '韩剧', 'riju': '日剧', 'taiju': '台剧',
    'gangju': '港剧', 'guochanju': '国产剧', 'haiwaiju': '海外剧',
    'daluzongyi': '大陆综艺', 'gangtaizongyi': '港台综艺',
    'rihanzongyi': '日韩综艺', 'oumeizongyi': '欧美综艺',
}
_DIANSHI_AREA = ('meiju', 'hanju', 'riju', 'taiju', 'gangju', 'guochanju', 'haiwaiju')
_ZONGYI_AREA = ('daluzongyi', 'gangtaizongyi', 'rihanzongyi', 'oumeizongyi')


def _area_filter(tids):
    """构造 drpy 地区筛选: 默认"全部", 其余为各地区的 slug(值) + 中文名(显示)。"""
    opts = [{'n': '全部', 'v': ''}]
    for s in tids:
        opts.append({'n': AREA_SLUGS[s], 'v': s})
    return [{'key': 'area', 'name': '地区', 'value': opts}]


def _enum_filter(key, name, vals):
    """构造 drpy 枚举筛选(地区/类型/年份...): 值即显示名, 与站点 vodshow 段值一致。"""
    opts = [{'n': '全部', 'v': ''}]
    for v in vals:
        opts.append({'n': v, 'v': v})
    return [{'key': key, 'name': name, 'value': opts}]


# 电影地区 / 类型(实测 data-val, 与 vodshow 第 2 / 3 段对应)
DIANYING_AREA = ['中国大陆', '其它', '加拿大', '印度', '台湾', '德国', '意大利', '新加坡',
                 '日本', '法国', '泰国', '美国', '英国', '西班牙', '韩国', '香港']
DIANYING_CLASS = ['其它', '冒险', '剧情', '动作', '动画', '古装', '商战', '喜剧', '奇幻',
                  '微电影', '恐怖', '悬疑', '惊悚', '战争', '枪战', '武侠', '灾难', '谍战',
                  '科幻', '网络电影', '警匪', '都市', '青春']
# 动漫类别(实测 vodshow/dongman--{类})
DONGMAN_CLASS = ['国产动漫', '日韩动漫', '欧美动漫']

# vodshow 12 段路径中, 各筛选维度对应的段索引(从 0 计; 第 0 段固定为 type slug)
SEG_IDX = {'area': 1, 'class': 2, 'year': 3, 'lang': 4, 'version': 5,
           'state': 6, 'letter': 7, 'time': 8, 'level': 9, 'weekday': 10}

# drpy 二级筛选(FILTERS)
#   电视剧 / 综艺: 按地区细分(复用已验证的地区 slug, 见 categoryContent 分支)
#   电影 / 动漫: 按地区 / 类型 / 类别细分(值取站点真实 data-val, 直填 vodshow 对应段)
FILTERS = {
    'dianshiju': _area_filter(_DIANSHI_AREA),
    'zongyipian': _area_filter(_ZONGYI_AREA),
    'dianying': _enum_filter('area', '地区', DIANYING_AREA) +
                _enum_filter('class', '类型', DIANYING_CLASS),
    'dongman': _enum_filter('class', '类别', DONGMAN_CLASS),
}

DL_HOME, DL_DETAIL, DL_PLAY = 12.0, 12.0, 16.0


def _log(m):
    try:
        print('[ik4k] %s' % m)
    except Exception:
        pass


def _vodshow_core(tid):
    """把 tid 规范化成 12 段的 vodshow 路径核心。

    站点分类页形如:
        一级: /vodshow/dianying-----------/
        二级: /vodshow/dianying-中国大陆----------/   (第2段是地区筛选)
    即 split('-') 后固定 12 段, 缺位补空。
    """
    segs = str(tid or '').strip('/').split('-')
    segs = (segs + [''] * 12)[:12]
    return '-'.join(segs)


class Spider(Spider):
    def __init__(self):
        self.base = HOST
        self.sess = requests.Session()
        self.sess.headers.update({
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
        })

    # ---------- 生命周期 ----------
    def init(self, extend=''):
        ext = {}
        if extend:
            try:
                ext = json.loads(extend) if extend.strip().startswith('{') else {}
            except Exception:
                ext = {}
        if ext.get('host'):
            self.base = str(ext['host']).rstrip('/')
        return ''


    # ---------- 请求 ----------
    def _get(self, url, timeout=7):
        """取文本页; 显式 Accept-Encoding: identity, 避免响应被压缩而盒子侧未解压。"""
        try:
            h = {'Referer': REFERER, 'Accept-Encoding': 'identity'}
            r = self.sess.get(url, headers=h, timeout=timeout, allow_redirects=True)
            try:
                r.encoding = 'utf-8'
            except Exception:
                pass
            return r
        except Exception:
            return None

    def _get_img(self, url, timeout=7):
        """取图片: 一律二进制读取(绝不按文本解码), 失败返回 b''。"""
        try:
            h = {'Referer': REFERER, 'Accept-Encoding': 'identity',
                 'Accept': 'image/avif,image/webp,image/png,image/*,*/*;q=0.8'}
            r = self.sess.get(url, headers=h, timeout=timeout)
            return r.content or b''
        except Exception:
            return b''

    @staticmethod
    def _is_guard(html):
        if not html:
            return False
        return ('/_guard/' in html) or ('rotate_html' in html) or ('Security Verification' in html)

    def _fetch(self, url, deadline):
        """取页; 命中盾则自动过盾后重取。全程尊重 deadline, 不空转。"""
        r = None
        for _ in range(3):
            if time.time() > deadline:
                break
            r = self._get(url, timeout=min(10, max(3, deadline - time.time())))
            if r is None:
                time.sleep(0.3)
                continue
            if not self._is_guard(r.text):
                return r
            if not self._try_pass_guard(deadline):
                return r          # 过盾失败: 原样返回, 上层出提示卡, 优雅降级
            # 过盾成功 -> 重取目标页
            if time.time() > deadline:
                break
            r = self._get(url, timeout=min(10, max(3, deadline - time.time())))
            if r is not None and not self._is_guard(r.text):
                return r
        return r

    def _purge_guard_cookies(self):
        """清空与过盾校验相关的陈旧凭证, 避免"旧 cookie 与新 guard 签名"混用导致服务端
        校验冲突(典型症状: 盒子侧始终"签名已提交但探测仍被盾")。

        清除目标: guardret(上一轮的旧签名)/ guard(上一轮的旧挑战值)/
                  _ok8_(旧验证通过态)/ server_session_*(旧会话)
        清除后, 取图会拿到全新 guard, 本轮 guardret 由新 guard 签名, 二者严格配对。
        """
        targets = ('guardret', 'guard', '_ok8_')
        prefixes = ('server_session',)
        try:
            for _ in range(4):
                victims = []
                for c in list(self.sess.cookies):
                    n = (getattr(c, 'name', '') or '').lower()
                    if n in targets or n.startswith(prefixes):
                        victims.append((getattr(c, 'domain', None),
                                        getattr(c, 'path', '/') or '/',
                                        getattr(c, 'name', '')))
                if not victims:
                    break
                for d, p, n in victims:
                    try:
                        if d:
                            self.sess.cookies.clear(d, p, n)
                        else:
                            self.sess.cookies.clear(n=n)
                    except Exception:
                        try:
                            self.sess.cookies.clear()
                        except Exception:
                            pass
        except Exception:
            pass

    def _try_pass_guard(self, deadline=None, attempts=3):
        """自动求解 /_guard 旋转盾: 取图 -> 求角 -> 回填 guardret -> 探测放行。

        真机加固: 图片二进制取回并校验 PNG 魔数; 求解走快速角度算法(~0.2s);
        每轮取新图新角, 允许数轮重试; 尊重 deadline, 不无限空转。
        诊断: 每个失败分支在 _guard_reason 记录环节, 供提示卡定位(不改动任何求解/签名逻辑)。
        """
        if deadline is None:
            deadline = time.time() + 12
        base = self.base
        self._guard_reason = ''
        for _ in range(attempts):
            if time.time() > deadline:
                self._guard_reason = self._guard_reason or '时间预算用尽(盒子侧求解偏慢)'
                break
            # 关键: 每轮先清掉陈旧验证态, 避免"旧 cookie 与新 guard 签名"混用
            #       导致服务端校验冲突(遗留 _ok8_/server_session/旧 guardret 时的典型症状)
            self._purge_guard_cookies()
            to = min(8, max(3, deadline - time.time()))
            img = self._get_img('%s/_guard/rotate.png?t=%d' % (base, int(time.time() * 1000)), timeout=to)
            if len(img) < 200 or img[:8] != b'\x89PNG\r\n\x1a\n':
                self._guard_reason = 'rotate.png 非 PNG(盒子侧取图异常/被拦)'
                time.sleep(0.2)      # 没拿到 PNG(可能仍是引导脚本): 稍后重试
                continue
            try:
                guard = self.sess.cookies.get('guard') or ''
            except Exception:
                guard = ''
            if not guard:
                self._guard_reason = '未拿到 guard cookie(Set-Cookie 未落进会话)'
                time.sleep(0.2)
                continue
            try:
                ang = _solve_angle(img)
                self.sess.cookies.set('guardret', _sign(str(ang), guard[:8]), path='/')
            except Exception:
                self._guard_reason = '角度求解异常'
                time.sleep(0.2)
                continue
            _log('自动过盾: angle=%s guard=%s' % (ang, guard))
            probe = self._get(base + '/', timeout=min(8, max(3, deadline - time.time())))
            if probe is not None and not self._is_guard(probe.text):
                return True
            self._guard_reason = 'sign_probe_guarded'
        return False

    # ---------- 解析: 列表(首页/分类/搜索) ----------
    def _items(self, html):
        out = []
        for m in re.finditer(
                r'<a[^>]*class="public-list-exp"[^>]*href="(/voddetail/(\d+)/)"[^>]*title="([^"]*)"[^>]*>(.*?)</a>',
                html, re.S):
            href, vid, title, body = m.groups()
            pic = re.search(r'data-src="([^"]+)"', body) or re.search(r'data-original="([^"]+)"', body)
            rem = re.search(r'public-list-prb[^>]*>([^<]*)<', body)
            out.append({
                'vod_id': vid,
                'vod_name': title.strip(),
                'vod_pic': pic.group(1) if pic else '',
                'vod_remarks': rem.group(1).strip() if rem else '',
            })
        return out

    def _search_items(self, h):
        """搜索结果卡片(与首页/分类不同): data-src 封面 + h3 标题 + slide-info-remarks 备注。"""
        out = []
        for blk in re.split(r'<div class="vod-detail style-detail cor4 search-list">', h)[1:]:
            blk = blk[:1600]
            mm = re.search(r'href="(/voddetail/(\d+)/)"', blk)
            if not mm:
                continue
            nm = re.search(r'<h3[^>]*>(.*?)</h3>', blk, re.S)
            name = re.sub(r'<[^>]+>', '', nm.group(1)).strip() if nm else ''
            pic = re.search(r'data-src="([^"]+)"', blk)
            rem = re.search(r'slide-info-remarks[^>]*>([^<]*)<', blk)
            out.append({
                'vod_id': mm.group(2),
                'vod_name': name,
                'vod_pic': pic.group(1) if pic else '',
                'vod_remarks': rem.group(1).strip() if rem else '',
            })
        return out

    def _guard_card(self):
        reason = getattr(self, '_guard_reason', '')
        name = 'ik4k: 旋转验证盾未自动通过'
        if reason == 'sign_probe_guarded':
            return {'vod_id': '0', 'vod_name': name, 'vod_pic': '',
                    'vod_remarks': '失败环节: 签名已提交但探测仍被盾(角度/签名不符, 或该出口IP被加严)'}
        if reason:
            return {'vod_id': '0', 'vod_name': name, 'vod_pic': '',
                    'vod_remarks': '失败环节: %s' % reason}
        return {'vod_id': '0', 'vod_name': name, 'vod_pic': '',
                'vod_remarks': '自动过盾失败'}

    def _net_fail_card(self):
        return {'vod_id': '0', 'vod_name': 'ik4k: 网络请求失败/超时',
                'vod_pic': '', 'vod_remarks': '站点请求失败或超时; 若持续出现请检查网络或稍后重试'}

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        out = {'class': [dict(c) for c in TOP_TYPES], 'list': []}
        if filter:
            out['filters'] = FILTERS
        try:
            r = self._fetch(self.base + '/', time.time() + DL_HOME)
            if r is None:
                out['list'] = [self._net_fail_card()]
            elif self._is_guard(r.text):
                out['list'] = [self._guard_card()]
            else:
                out['list'] = self._items(r.text)[:60]
        except Exception:
            pass
        return out

    def homeVideoContent(self):
        try:
            r = self._fetch(self.base + '/', time.time() + DL_HOME)
            if r is not None and not self._is_guard(r.text):
                return {'list': self._items(r.text)[:60]}
        except Exception:
            pass
        return {'list': []}

    # ---------- AJAX 分类与翻页 ----------
    # 站点分类页首屏没有任何影片(全页 /voddetail/ 数为 0), 列表由 JS 异步填充,
    # 对应网页的"下滑式加载"(ds_cms.ajax.list_bottom = 3)。真实接口(取自 script.js):
    #     POST {host}/index.php/ds_api/vod        (maccms.path 为空串, jQuery $.ajax 表单提交)
    #     参数 = 首屏空容器 <div id="dataList" ...> 上的 data-*
    #            (type 为数字 id/class/area/year/lang/version/state/letter/time/level/weekday)
    #            + by(排序: time/hits/score) + page(页码, 从 1 递增)
    #     返回 JSON: {code:1, list:[{url,vod_name,vod_pic,vod_remarks,vod_serial,...}],
    #                 pagecount, total};  code=2 表示"没有更多了"
    def _post(self, url, data, deadline):
        """POST 站点接口; 命中盾则自动过盾后重试一次(复用 _try_pass_guard)。"""
        for _ in range(2):
            try:
                to = min(8, max(3, deadline - time.time()))
                r = self.sess.post(url, data=data,
                                   headers={'Referer': REFERER, 'Accept-Encoding': 'identity'},
                                   timeout=to)
            except Exception:
                r = None
            if r is None:
                continue
            txt = ''
            try:
                r.encoding = 'utf-8'
                txt = r.text or ''
            except Exception:
                pass
            # 盾会返回 HTML 引导脚本(非 JSON)
            if self._is_guard(txt) or (txt.lstrip()[:1] not in ('{', '[')):
                if self._try_pass_guard(deadline):
                    continue
                return None
            try:
                return json.loads(txt)
            except Exception:
                return None
        return None

    def _datalist_params(self, tid, deadline):
        """从 /vodshow/ 首屏的 #dataList 空容器提取 AJAX 所需参数(含 type 数字 id)。

        这样做不需要硬编码 slug->type_id 映射(如 dianying=20), 换分类也能自动拿到正确的 id。
        """
        cache = getattr(self, '_dl_cache', None)
        if cache is None:
            cache = {}
            self._dl_cache = cache
        if tid in cache:
            return cache[tid]
        params = {}
        try:
            r = self._fetch('%s/vodshow/%s/' % (self.base, _vodshow_core(tid)), deadline)
            if r is not None:
                mm = re.search(r'<div id="dataList"[^>]*>', r.text)
                if mm:
                    for k, v in re.findall(r'data-([a-z]+)="([^"]*)"', mm.group(0)):
                        params[k] = v
        except Exception:
            pass
        if params:
            cache[tid] = params
        return params

    def _json_items(self, items):
        """接口返回 list -> drpy 卡片。"""
        out = []
        for v in items or []:
            if not isinstance(v, dict):
                continue
            href = str(v.get('url') or '')
            mid = (re.search(r'/(\d+)\.html', href) or re.search(r'/(\d+)/', href)
                   or re.search(r'(\d+)', href))
            vid = mid.group(1) if mid else ''
            if not vid:
                continue
            pic = str(v.get('vod_pic') or '')
            if pic.startswith('//'):
                pic = 'https:' + pic
            elif pic.startswith('/'):
                pic = '%s%s' % (HOST, pic)
            rem = str(v.get('vod_remarks') or '')
            ser = str(v.get('vod_serial') or '')
            if not rem and ser not in ('', '0'):
                rem = '第%s集' % ser
            out.append({'vod_id': vid, 'vod_name': str(v.get('vod_name') or ''),
                        'vod_pic': pic, 'vod_remarks': rem})
        return out

    # ---------- 分类 ----------
    @staticmethod
    def _parse_extend(extend):
        """筛选值: drpy 可能传 dict 或 JSON 字符串, 统一成字典。"""
        if isinstance(extend, dict):
            return extend
        if not extend:
            return {}
        try:
            return json.loads(extend)
        except Exception:
            return {}

    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        try:
            pg = max(int(str(pg)), 1)
        except Exception:
            pg = 1
        # 二级筛选: 在"电视剧 / 综艺"下选了地区(area)时, 直接复用该地区的独立 slug
        # 作为 vodshow 第一段。这样既是真正的"顶级分类 + 地区筛选"结构, 又复用已验证
        # 能返回内容的 slug, 避免地区中文值猜测错误导致二级筛选出空页。
        ext = self._parse_extend(extend)
        area = ext.get('area', '') if isinstance(ext, dict) else ''
        if area and area in AREA_SLUGS:
            real_tid = area          # 电视剧/综艺: 复用独立地区 slug(已验证出内容)
        else:
            # 电影/动漫: 将筛选维度(area/class/year...)填进 vodshow 对应段, 拼成 12 段路径
            segs = (str(tid).strip('/').split('-') + [''] * 12)[:12]
            for k, v in (ext.items() if isinstance(ext, dict) else []):
                if k in SEG_IDX and v:
                    segs[SEG_IDX[k]] = v
            real_tid = '-'.join(segs)
        deadline = time.time() + DL_HOME
        # 主路径: 站点 AJAX 接口(下滑式加载的数据源), 页码走 POST 的 page 参数
        try:
            p = dict(self._datalist_params(real_tid, deadline) or {})
            if p:
                p['page'] = pg
                p.setdefault('by', 'time')
                res = self._post('%s/index.php/ds_api/vod' % self.base, p, deadline)
                if isinstance(res, dict):
                    code = str(res.get('code', ''))
                    lst = self._json_items(res.get('list') or [])
                    # pagecount 缺失/无效时给 pg+1, 保证仍能继续往下翻(翻到空页自然停)。
                    # 否则接口不返回 pagecount 会让 pagecount==pg, 第 2 页就翻不动了。
                    try:
                        pc = int(res.get('pagecount') or 0)
                    except Exception:
                        pc = 0
                    pc = pc if pc > pg else pg + 1
                    try:
                        total = int(res.get('total') or len(lst))
                    except Exception:
                        total = len(lst)
                    if lst:
                        return {'list': lst, 'page': pg, 'pagecount': pc,
                                'limit': 60, 'total': total}
                    if code in ('1', '2'):      # 1=空结果, 2=没有更多(已到末页)
                        return {'list': [], 'page': pg, 'pagecount': pg,
                                'limit': 60, 'total': 0}
        except Exception:
            pass
        # 兜底: 原 GET 逻辑(接口变更或模板不同时, 至少第 1 页仍有机会出内容)
        t = real_tid
        url = '%s/vodtype/%s/' % (self.base, t) if pg <= 1 else '%s/vodtype/%s-%d.html' % (self.base, t, pg)
        lst = []
        try:
            r = self._fetch(url, deadline)
            if r is None:
                return {'list': [self._net_fail_card()], 'page': pg, 'pagecount': pg,
                        'limit': 60, 'total': 0}
            if self._is_guard(r.text):
                return {'list': [self._guard_card()], 'page': pg, 'pagecount': pg,
                        'limit': 60, 'total': 0}
            lst = self._items(r.text)
        except Exception:
            pass
        return {'list': lst, 'page': pg, 'pagecount': pg + 1, 'limit': 60, 'total': len(lst)}

    # ---------- 详情 ----------
    @staticmethod
    def _order_playlist(froms, urls):
        """线路排序: 主线/备用等直链(parse=0)在前, 4K/蓝光类官网线路(parse=1)排最后。
        用稳定排序, 仅把含 4K/蓝光 的线路后置, 同组内保持原相对顺序。"""
        def _k(n):
            return 1 if ('4K' in n or '蓝光' in n) else 0
        order = sorted(range(len(froms)), key=lambda i: _k(froms[i]))
        return [froms[i] for i in order], [urls[i] for i in order]

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        m = re.search(r'(\d+)', vid)
        vid = m.group(1) if m else ''
        if not vid:
            return {'list': []}
        h = ''
        try:
            r = self._fetch('%s/voddetail/%s/' % (self.base, vid), time.time() + DL_DETAIL)
            if r is not None:
                if self._is_guard(r.text):
                    return {'list': [self._guard_card()]}
                h = r.text
        except Exception:
            pass
        if not h:
            return {'list': []}
        title = ''
        mt = re.search(r'<title>([^_<\-]+)', h)
        if mt:
            title = mt.group(1).strip()
        pic = re.search(r'data-original="([^"]+)"', h) or re.search(r'data-src="([^"]+)"', h)
        # 线路名称(顺序即来源顺序)
        #   dsn2 移动端: <div class="anthology-tab..."><div class="swiper-wrapper">
        #                <a class="swiper-slide">…&nbsp;主线<span class="badge">10</span></a>…
        #   桌面端变体: data-form + class="vod-playerUrl swiper-slide"
        names = []
        _tab = re.search(r'anthology-tab(.*?)anthology-list', h, re.S)
        _segs = re.findall(r'<a[^>]*class="[^"]*swiper-slide[^"]*"[^>]*>(.*?)</a>',
                           _tab.group(1) if _tab else '', re.S)
        if not _segs:
            _segs = [b for _f, b in re.findall(
                r'data-form="([^"]+)"[^>]*class="vod-playerUrl swiper-slide[^"]*"[^>]*>(.*?)</a>', h)]
        for body in _segs:
            body = re.sub(r'<[^>]+>', '', body)               # 先去掉 HTML 标签
            body = _html.unescape(body)                       # 再解 &#xe679; &nbsp; 等实体
            nm = re.sub(r'[^\u4e00-\u9fffA-Za-z0-9\-]', '', body)  # 只留中英文/数字/连字符
            nm = re.sub(r'\d+$', '', nm)                      # 去掉末尾角标数字(如 21/6)
            names.append(nm)
        # 选集 boxes (与线路名按位置并行配对; 兼容单/双引号)
        boxes = re.findall(r'anthology-list-box[^>]*>(.*?)</ul>', h, re.S)
        froms, urls = [], []
        if names and len(boxes) >= len(names):
            for i, name in enumerate(names):
                blk = boxes[i] if i < len(boxes) else ''
                links = re.findall(r'href="(/vodplay/(\d+)-(\d+)-(\d+)/)"', blk)
                if not links:
                    continue
                links.sort(key=lambda x: int(x[3]) if x[3].isdigit() else 0)
                eps = ['%s$%s%s' % (n, self.base, href) for href, _, _, n in links]
                froms.append(name or ('线路%d' % (i + 1)))
                urls.append('#'.join(eps))
        # 兜底: 直接按 sid 分组(名称用 线路N, 不影响播放)
        if not froms:
            by_sid = {}
            for href, v, s, n in re.findall(r'href="(/vodplay/(\d+)-(\d+)-(\d+)/)"', h):
                by_sid.setdefault(s, []).append((int(n), href))
            for s in sorted(by_sid, key=lambda x: int(x)):
                eps = ['%s$%s%s' % (n, self.base, href) for n, href in sorted(by_sid[s])]
                froms.append('线路' + s)
                urls.append('#'.join(eps))
        froms, urls = self._order_playlist(froms, urls)
        return {'list': [{
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic.group(1) if pic else '',
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=False, pg='1'):
        try:
            pg = max(int(str(pg)), 1)
        except Exception:
            pg = 1
        kw = re.sub(r'[/?#&\s]+', '', str(key or ''))
        if not kw:
            return {'list': [], 'page': pg, 'pagecount': pg}
        lst = []
        try:
            r = self._fetch('%s/vodsearch/%s----------%d---.html' % (self.base, quote(kw), pg),
                            time.time() + DL_HOME)
            if r is not None:
                if self._is_guard(r.text):
                    return {'list': [self._guard_card()], 'page': pg, 'pagecount': pg}
                lst = self._search_items(r.text) or self._items(r.text)
        except Exception:
            pass
        if not lst:
            return {'list': [], 'page': pg, 'pagecount': pg}
        return {'list': lst, 'page': pg, 'pagecount': pg + 1}

    # ---------- 播放 ----------
    @staticmethod
    def _player_json(h):
        i = h.find('player_aaaa')
        if i < 0:
            return {}
        j = h.find('{', i)
        d, k = 0, j
        while k < len(h):
            if h[k] == '{':
                d += 1
            elif h[k] == '}':
                d -= 1
                if d == 0:
                    break
            k += 1
        try:
            return json.loads(h[j:k + 1])
        except Exception:
            return {}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id) if str(id).startswith('http') else self.base + str(id)
        try:
            r = self._fetch(url, time.time() + DL_PLAY)
        except Exception:
            r = None
        if r is None:
            return {'parse': 1, 'jx': 1, 'url': url, 'header': {'User-Agent': UA, 'Referer': REFERER}}
        if self._is_guard(r.text):
            # 命中盾: 交 WebView 兜底(真浏览器可能自动过/或需用户手动), 不直接判死
            return {'parse': 1, 'jx': 0, 'url': url, 'header': {'User-Agent': UA, 'Referer': REFERER}}
        h = r.text
        pa = self._player_json(h)
        u = (pa.get('url') or '').strip()
        enc = str(pa.get('encrypt', 0))
        if u and u.startswith('http'):
            # 直链(媒体文件)才 parse=0; 若 player_aaaa.url 实为第三方站点网页
            # (如 腾讯/优酷/v.qq.com、v.youku.com), 交解析器嗅探(parse=1)
            if enc in ('0', '') and self.isVideoFormat(u):
                return {'parse': 0, 'url': u, 'header': {'User-Agent': UA, 'Referer': REFERER}}
            return {'parse': 1, 'jx': 1, 'url': u, 'header': {'User-Agent': UA, 'Referer': REFERER}}
        # 没解析到 url: 兜底交 WebView(播放页自带 JS 解密/跳转)
        return {'parse': 1, 'jx': 1, 'url': url, 'header': {'User-Agent': UA, 'Referer': REFERER}}

    # ---------- 工具钩子 ----------
    def isVideoFormat(self, url):
        u = str(url or '').lower()
        return any(('.' + e) in u for e in ('m3u8', 'mp4', 'flv', 'mkv', 'avi', 'ts'))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None
