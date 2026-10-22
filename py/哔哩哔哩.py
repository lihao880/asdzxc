# -*- coding: utf-8 -*-
"""
哔哩哔哩 TVBox Python 爬虫（独立版）v2 —— 修复「只能看 6 分钟」
==============================================================
【v2 关键修复：6 分钟断流】

现象：列表/详情/搜索都正常，点播放后放几分钟就停（实测约 6 分钟）。

根因（实测确认，不是猜）：
  1) fnval=16 走的是 DASH，返回的 dash.video[].baseUrl 是单个 .m4s 大文件，
     Video 轨和 Audio 轨是【两条独立的流】，原代码只取了一条 video，把音频丢了。
  2) 更致命的是：老代码把 .m4s 直接当播放地址返回（parse=0, url=xxx.m4s）。
     播放器把它当普通 mp4 从头顺序读，读到第一个 sidx 声明的边界就断，
     于是正好停在「前几分钟」——这就是 6 分钟的来源。
  3) 该 .m4s 只吃带 Referer 的 Range 请求（不带 Referer 直接 403），
     播放器不会替你补 Range 分片逻辑。

修复方式（三档，自动降级）：
  A. 【官方 HLS】: fnval = 4048（带 HLS 位 4096）。
     ⚠ 实测结论：B 站【即使开了 HLS 位也永远不返回 m3u8】，只给 .m4s。
       所以这一档实际命中率为 0，保留只为将来 B 站真上线 HLS 时自动生效，
       判定必须严格（path 里出现 .m3u8 才算），绝不能把 .m4s/.mp4 当 HLS。
  B. 主力【本地 HLS 重封装】: localProxy 把 dash 的 video+audio 两条 m4s
     按 sidx 索引切片，实时生成 HLS 清单喂给播放器。音画同步，可随意拖进度。
     - 每 5.005s 一片，音视频【一一对应】取片
     - 第 0 片带合并后的 init（ftyp + video trak + audio trak + 双 trex）
     - 每片重写 tfdt 为累计时间（否则 DTS 回退，ffmpeg 拒解）
     - 直链约 2 小时过期，取片失败会自动重取地址再试
  C. 兜底【durl 单文件】: fnval=0 时 B 站给完整 mp4（durl），
     1 段就是全片，播放器直接吃，绝不截断。清晰度低但一定能播完。

实测（v2.1）：
  PGC 鬼灭之刃 ep826497 → 587 片 / 156.7MB / 48分58秒，全片 ffmpeg 解码零报错
  PGC 名侦探柯南 ep321808 → 299 片 / 66MB / 24分53秒，零报错
  UGC BV13HwdzYEBu → 108 片 / 536.75s，hevc+aac 零报错

另附：qn 与清晰度。未登录时 B 站最高只给 480P。
      注意 accept_description 会列出 4K/1080P（那只是「设备支持」），
      真正能拿到什么要看 dash.video 里实际有哪几档。
      填 COOKIE="SESSDATA=..." 才能真正拿到 1080P+/4K。

接口约定：类名 Spider，playerContent 的 header 必须是 dict（不是 JSON 串）。

站点：https://www.bilibili.com/
资源：番剧 / 国创 / 电影 / 电视剧 / 纪录片 / 综艺（6 大 PGC 分类全量）
      + 搜索支持 UGC 稿件（视频）
首页分类：6 个大分类 + 19 个地区分类（番剧·日本 / 电影·美国 / 电视剧·英国 …）
      地区码运行时从 pgc/season/index/condition 的 area 组动态取，
      只生成该分类【真实支持】的地区（番剧没有韩国，就不生成「番剧·韩国」）
筛选：每个分类均带【真实可用】的可选筛选（地区 / 年份 / 风格 /
      状态 / 版权 / 付费 / 季度 / 配音 / 出品 …），定义从 condition 接口动态解析。
      排序维度：综合排序 / 播放量 / 更新时间 / 上映时间 / 最高评分。

【B站参数的两个坑（实测）】
  1) area 只认【数字码】，传中文名不报错但会被静默忽略，直接返回全量：
       传 "日本" → 4274 条（全量，等于没筛）
       传 "2"    → 3486 条（真生效）
     且各分类的码不同（番剧 日本=2，电视剧 中国=1,6,7），不能跨分类复用。
  2) year 只认【区间写法】：
       传 "2024"           → 无效，返回全量
       传 "[2024,2025)"    → 生效
  3) 风格参数名是 style_id（不是 style），值也是数字码（热血=10016）。
  本文件已统一在 _cate 里做转换，筛选面板给的原始关键词会被自动映射。

【接口说明】
  分类列表：api.bilibili.com/pgc/season/index/result
    - season_type: 1=番剧 4=国创 2=电影 5=电视剧 3=纪录片 7=综艺
    - 关键参数（缺一不可）：type / area / year / style / order
    - 筛选定义：api.bilibili.com/pgc/season/index/condition?season_type=N&type=1&...
  搜索：api.bilibili.com/x/web-interface/wbi/search/all/v2（WBI 签名）
  详情：api.bilibili.com/pgc/view/web/season（PGC）/ x/web-interface/view（UGC）
  播放：api.bilibili.com/pgc/player/web/playurl（PGC 直链）
        api.bilibili.com/x/player/wbi/playurl（UGC 直链，需 WBI 签名）

【播放 · 4K 解析引擎】
  B站是【唯一能直链播放】的平台（PGC + UGC），也是唯一能真 4K 的平台。
  - 直链请求【账号可用的最高清晰度】（qn=127 自动降级），并自动挑选分辨率最高的视频流
  - 关键：未登录时 B站只给 480P（尽管接口声明支持 4K）；
    填顶部 COOKIE="SESSDATA=xxx" 或 extend {"cookie":"SESSDATA=xxx"} 即可解锁 4K/1080P+
  - 直链失败时回退外挂解析池 / 播放页
  - 想用自己的 4K 解析：改顶部 PARSERS，或写进 extend {"parser":"https://你的解析/?url="}

接口约定：类名 Spider，playerContent 的 header 必须是 dict（不是 JSON 串）。
"""

import re
import json
import time
import hashlib
import struct
import threading

# ---------- 壳子兼容层 ----------
try:  # Python 3
    from urllib.parse import quote as _quote
    from urllib.parse import urljoin as _urljoin
    from urllib.request import Request, urlopen

    def _q(s):
        return _quote(str(s), safe="/")

    _PY2 = False
except Exception:  # Jython 2.7 / Python 2 (TVBox/OK影视)
    from urllib import quote as _quote
    from urllib2 import Request, urlopen
    try:
        from urlparse import urljoin as _urljoin
    except Exception:
        def _urljoin(a, b):
            return (a.rsplit("/", 1)[0] + "/" + b) if "/" in a else b

    def _q(s):
        if isinstance(s, unicode):
            s = s.encode("utf-8")
        return _quote(str(s), safe="/")

    _PY2 = True

try:
    import requests as _rq
except Exception:
    _rq = None

try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        pass

UA_PC = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
REF = "https://www.bilibili.com/"
DEBUG = False

# PGC 分类（season_type -> 名称）
CLASSES = [("1", "番剧"), ("4", "国创"), ("2", "电影"),
           ("5", "电视剧"), ("3", "纪录片"), ("7", "综艺")]

# 地区分类（首页顶层）。
# 实测关键：area 参数吃的是【condition 接口给的数字码】，不是中文名。
#   传中文 "日本" → 接口不报错但【完全忽略】，返回全量（4274 条），
#   传 "2"     → 真正生效（番剧日本 3486 条）。
# 每个分类的地区码不一样，也不能跨分类套用：
#   番剧 area=3 是美国(442)，电影 area=3 也是美国(2256)，但番剧 area=8 无效、电影 area=8 是韩国(19)。
# 所以地区码统一在运行时从 pgc/season/index/condition 的 area 组里取，不写死。
# 这里只定义「展示哪些地区」，value 为 B 站的地区中文名，用于匹配 condition 里的 name。
AREAS = [("jp", "日本"), ("cn", "中国"), ("us", "美国"), ("kr", "韩国"),
         ("gb", "英国"), ("fr", "法国"), ("de", "德国"), ("th", "泰国"),
         ("it", "意大利"), ("es", "西班牙"), ("hk", "中国港台"), ("ot", "其他")]

# 支持地区筛选的 PGC 分类（实测 condition 里有 area 字段的只有这三个）
# 国创(4)/纪录片(3)/综艺(7) 的 condition 里没有 area，硬传会被无声忽略，故不生成
AREA_TYPES = {"1": "番剧", "2": "电影", "5": "电视剧"}

# 通用请求头（UGC view/playurl 缺 Origin/Accept 会被拦）
BL_H = {"Referer": REF,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.bilibili.com"}

# WBI 签名重排表
WBI_TAB = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9,
           42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1,
           60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52]

# 排序（order 参数）
ORDERS = [("", "综合排序"), ("0", "播放量"), ("2", "更新时间"),
          ("6", "上映时间"), ("4", "最高评分")]

# ================================================================
#  4K 解析引擎（统一配置）
#  说明：
#   B站是唯一能【直链播放】的平台，且是唯一能真 4K 的平台。
#   但实测：未登录时 B站只给 480P（accept 声明支持 120=4K，实际只回 480P），
#         【带登录 Cookie（SESSDATA）才能取到 4K/1080P+】。
#   故这里：
#     - B站直链请求【最高清晰度】（qn=127 即 8K 档，接口自动降级到可用最高）
#     - 支持 Cookie 注入（填 SESSDATA 即可解锁 4K）
#     - 直链失败时回退解析池
#   想用自己的解析：改 PARSERS / SESSDATA，或写进 extend：
#        {"cookie":"SESSDATA=xxx", "parser":"https://你的解析/?url="}
# ================================================================
#   4) 【自动淘汰】探测会识别"停运告别页/域名待售页/劫持跳转页"，失效接口自动跳过。
#   5) 解析站生命周期短（数周~数月），失效是常态——优先替换靠前接口或用 extend 自备。
PARSERS = [
    # ===== 实测可用（2026-10 复测）=====
    # —— 优先：通用云解析，页面带真实解析逻辑，多平台通吃 ——
    "https://yparse.ik9.cc/?url=",
    "https://yemu.xyz/?url=",
    "https://jx.hongshu.net/?url=",
    "https://bd.jx.cn/?url=",
    "https://jx.777jiexi.com/player/?url=",
    # —— 备用：结构正常的通用解析页 ——
    "https://okjx.cc/?url=",
    "https://jx.wannengjiexi.com/?url=",
    "https://jx.h8jx.com/?url=",
    "https://www.playm3u8.cn/jiexi.php?url=",
    # —— 兜底：域内跳转型（自动跟随到活线）——
    "https://jx.yparse.com/?url=",
]
USE_PARSER = True
# 解析通道 UA（移动端更易命中高码率）
PARSER_UA = "Mozilla/5.0 (Linux; Android 12; Pixel 6 Build/SQ3A.220705.004; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/106.0.5249.126 Mobile Safari/537.36"
# B站登录 Cookie（填 SESSDATA=xxx 可解锁 4K / 1080P+；留空则最高约 480P）
COOKIE = ""
# 期望清晰度码（B站 qn）：127=8K, 120=4K, 116=1080P60, 112=1080P+, 80=1080P, 64=720P
# 设为 127 时接口会自动降级到当前账号可用的最高清晰度
QN = 127


def _log(*a):
    if DEBUG:
        try:
            print("[B站]", " ".join([str(x) for x in a]))
        except Exception:
            pass


def _http(method, url, headers=None, body=None, timeout=15, rng=None, raw=False):
    """
    统一 HTTP。rng="start-end" 时发 Range 请求（拉 m4s 分片必须）。
    raw=True 时返回 bytes 而不是解码后的字符串（m4s 是二进制）。
    """
    hdrs = {"User-Agent": UA_PC, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    if rng:
        hdrs["Range"] = "bytes=%s" % rng
    data = body.encode("utf-8") if isinstance(body, str) else body

    def _ret(code, content):
        if raw:
            return code, content
        if isinstance(content, bytes):
            content = content.decode("utf-8", "ignore")
        return code, content

    try:
        if _rq is not None:
            r = _rq.request(method.upper(), url, headers=hdrs, data=data,
                            timeout=timeout, verify=False)
            return _ret(r.status_code, r.content)
        req = Request(url, data=data, headers=hdrs)
        try:
            import ssl
            ctx = ssl.create_unverified_context()
        except Exception:
            ctx = None
        if ctx is not None:
            try:
                with urlopen(req, timeout=timeout, context=ctx) as resp:
                    return _ret(resp.getcode(), resp.read())
            except TypeError:
                pass
        with urlopen(req, timeout=timeout) as resp:
            return _ret(resp.getcode(), resp.read())
    except Exception as e:
        _log("HTTP-ERR", method, url[:100], e)
        return 0, (b"" if raw else "")


def _jload(txt):
    if not txt:
        return {}
    txt = txt.strip()
    i = txt.find("{")
    if i < 0:
        return {}
    try:
        return json.loads(txt[i:])
    except Exception:
        try:
            return json.loads(txt[i:].rstrip(";"))
        except Exception:
            return {}


def _clean(s):
    if not s:
        return ""
    return re.sub(r"</?em[^>]*>", "", str(s)).strip()


def _int(v, d=0):
    try:
        return int(v)
    except Exception:
        return d


# ================================================================
#  DASH fMP4 分段索引（sidx）解析 + HLS 重封装
#  背景：B 站 dash 流的 .m4s 是「单文件 + sidx 索引」结构。
#        整个文件 = [init 段][sidx 索引][分片1][分片2]...
#        sidx 里写清了每个分片的 byte 偏移和时长。
#        把 sidx 读出来，就能按 Range 精确切每一片，重封装成 HLS。
#  这也是「6 分钟断流」的根源：直接把 .m4s 当 mp4 喂给播放器，
#  播放器不认 sidx，顺序读到第一个分片边界就停。
# ================================================================

def _parse_sidx(data, offset=0):
    """
    解析 ISO BMFF 的 sidx box。
    实测布局（version=0，B 站全是这种）：
        size(4) type(4) ver+flags(4) refID(4) timescale(4)
        ept(4) first_offset(4) reserved(2) count(2) -> 共 32 字节头
        然后 count 个 { ref(4) dur(4) sap(4) }
    返回 (timescale, [(duration_ts, byte_size), ...])，失败返回 (None, None)。
    """
    try:
        i = data.find(b"sidx", offset, offset + 64)
        if i < 4:
            return None, None
        p = i + 4                      # 跳过 'sidx' → 指向 version
        _ver = data[p]                 # 0 或 1
        p += 4                         # version(1) + flags(3)
        p += 4                         # reference_ID
        timescale = struct.unpack(">I", data[p:p + 4])[0]
        p += 4                         # timescale
        if _ver == 0:
            p += 4                     # earliest_presentation_time
            p += 4                     # first_offset
        else:
            p += 8
            p += 8
        p += 2                         # reserved
        count = struct.unpack(">H", data[p:p + 2])[0]
        p += 2
        out = []
        for _ in range(count):
            if p + 12 > len(data):
                break
            ref = struct.unpack(">I", data[p:p + 4])[0]
            dur = struct.unpack(">I", data[p + 4:p + 8])[0]
            p += 12
            size = ref & 0x7FFFFFFF
            if size:
                out.append((dur, size))
        return (timescale or 1000), (out if out else None)
    except Exception:
        return None, None


def _hex2bytes(h):
    """'0-1007' / '1008-4627' -> (start, end)"""
    try:
        a, b = str(h).split("-", 1)
        return int(a), int(b)
    except Exception:
        return 0, 0


def _sidx_offset(seg_base):
    """
    sidx box 在文件里的绝对偏移。
    B 站给 indexRange 是相对 init 段之后的偏移，实际位置 = init_end + 1 + index_start。
    """
    init = seg_base.get("Initialization") or seg_base.get("initialization") or "0-0"
    idx = seg_base.get("indexRange") or seg_base.get("index_range") or "0-0"
    i0, i1 = _hex2bytes(init)
    s0, _ = _hex2bytes(idx)
    return i1 + 1 + s0, i1 + 1 + _hex2bytes(idx)[1]


class _DashStream(object):
    """一条 dash 流（video 或 audio），能按 sidx 切片并拼成 fMP4 分片"""

    def __init__(self, info):
        self.url = info.get("baseUrl") or info.get("base_url") or ""
        self.size = _int(info.get("size"), 0)
        seg = info.get("SegmentBase") or info.get("segment_base") or {}
        self.init_rng = seg.get("Initialization") or seg.get("initialization") or "0-1007"
        self.idx_rng = seg.get("indexRange") or seg.get("index_range") or ""
        self.init = b""
        self.parts = None       # [(dur, size), ...]
        self.offs = []          # 每片的起始绝对偏移
        self.timescale = 1000   # sidx 里声明的 timescale
        self.total = 0          # 总时长（秒），由 sidx 算出
        self.dur = 0.0          # 单片平均时长，用于音视频对齐

    def ready(self):
        return bool(self.url and self.idx_rng)

    def load_index(self, force=False):
        """拉 init 段和 sidx，算出每片的绝对偏移。
        force=True 时清空缓存重拉（换新 URL 后偏移/init 全变，必须重拉）"""
        if force:
            self.parts = None
            self.offs = []
            self.init = b""
        if self.parts is not None:
            return True
        if not self.ready():
            return False
        a, b = _hex2bytes(self.init_rng)
        st, body = _http("GET", self.url, headers=_bl_hdr(self.url),
                         rng="%d-%d" % (a, b), raw=True)
        if st not in (200, 206) or not body:
            return False
        self.init = body if isinstance(body, bytes) else body.encode("utf-8", "ignore")

        a2, b2 = _hex2bytes(self.idx_rng)
        # 实测：B 站给的 indexRange 就是【整文件绝对偏移】，不需要再加 init 长度
        #（box 布局：ftyp | moov | sidx | moof+mdat | moof+mdat ...）
        st2, idx = _http("GET", self.url, headers=_bl_hdr(self.url),
                         rng="%d-%d" % (a2, b2), raw=True)
        if st2 not in (200, 206) or not idx:
            return False
        if not isinstance(idx, bytes):
            idx = idx.encode("utf-8", "ignore")

        scale, parts = _parse_sidx(idx)
        if not parts:
            return False
        self.timescale = scale or 1000
        self.parts = parts
        self.total = sum(p[0] for p in parts) / float(self.timescale)
        self.dur = (self.parts[0][0] / float(self.timescale)) if parts else 0.0
        # 分片数据从 indexRange 结束之后开始
        off = b2 + 1
        self.offs = []
        for _dur, sz in parts:
            self.offs.append(off)
            off += sz
        return True

    def head_bytes(self, n=4096):
        st, body = _http("GET", self.url, headers=_bl_hdr(self.url), rng="0-%d" % (n - 1))
        if st in (200, 206) and body:
            return body if isinstance(body, bytes) else body.encode("utf-8", "ignore")
        return b""

    def segment(self, i):
        """取第 i 片（不含 init），返回 bytes"""
        if not self.load_index() or i < 0 or i >= len(self.offs):
            return b""
        sz = self.parts[i][1]
        off = self.offs[i]
        st, body = _http("GET", self.url, headers=_bl_hdr(self.url),
                         rng="%d-%d" % (off, off + sz - 1), raw=True)
        if st in (200, 206) and body:
            return body if isinstance(body, bytes) else body.encode("utf-8", "ignore")
        return b""

    def index_at(self, t0, t1):
        """
        取与 [t0, t1) 有重叠的所有分片序号。
        判断用「分片区间 [s, acc) 与 [t0, t1) 是否有交集」，
        必须写 acc > t0 且 s < t1 —— 少一个条件就会漏掉跨界那片。
        """
        if not self.load_index():
            return []
        scale = float(self.timescale or 1000)
        out = []
        acc = 0.0
        for i, (d, _sz) in enumerate(self.parts):
            s = acc
            acc += d / scale
            if acc > t0 and s < t1:
                out.append(i)
        return out


def _boxes(d):
    """把一段字节切成 [(type, size, bytes), ...]"""
    out = []
    i = 0
    n = len(d)
    while i + 8 <= n:
        sz = struct.unpack(">I", d[i:i + 4])[0]
        typ = d[i + 4:i + 8]
        if sz < 8 or i + sz > n:
            break
        out.append((typ, sz, d[i:i + sz]))
        i += sz
    return out


def _box(typ, payload):
    return struct.pack(">I", len(payload) + 8) + typ + payload


def _mk_ftyp(src_ftyp=None):
    """造一个通用 ftyp（isom + iso6 + mp41，兼容性最好）"""
    if src_ftyp:
        return src_ftyp
    return _box(b"ftyp", b"isom" + struct.pack(">I", 0x200) +
                b"isomiso6mp41")


def _merge_moov(v_init, a_init):
    """
    把 video 的 moov 和 audio 的 moov 合成一个。
    做法：取 video 的 mvhd / trak / mvex，再追加 audio 的 trak。
    两轨 track_id 分别是 1 / 2，天然不冲突，不用重编号。
    moov 尾部补 udta 会干扰部分播放器，直接丢掉。
    返回 (init_bytes, ok)
    """
    try:
        vbx = dict((t, b) for t, _s, b in _boxes(v_init))
        abx = dict((t, b) for t, _s, b in _boxes(a_init))

        ftyp = vbx.get(b"ftyp") or _mk_ftyp()

        v_moov = vbx.get(b"moov")
        a_moov = abx.get(b"moov")
        if not v_moov:
            return v_init, False
        if not a_moov:
            return ftyp + v_moov, True

        def kids(moov):
            return _boxes(moov[8:])

        v_kids = kids(v_moov)
        a_kids = kids(a_moov)
        a_traks = [b for t, _s, b in a_kids if t == b"trak"]
        a_mvex = [b for t, _s, b in a_kids if t == b"mvex"]

        # video moov 里保留 mvhd / trak / mvex，丢 udta（含封面，会干扰）
        keep = [(t, b) for t, _s, b in v_kids if t in (b"mvhd", b"trak", b"mvex")]
        for tk in a_traks:
            keep.append((b"trak", tk))
        if not any(t == b"trak" for t, _ in keep):
            return ftyp + v_moov, True

        # 关键：mvex 里每个轨都要有对应 trex，否则音轨 moof 无 trex 可依，
        # 播放器直接报 "trun track id unknown, no tfhd was found"（实测）
        v_mvex = dict((t, b) for t, _s, b in (kids(v_moov)))
        vm = v_mvex.get(b"mvex")
        if vm and a_mvex:
            vme = _boxes(vm[8:])
            ame = _boxes(a_mvex[0][8:])
            v_trex_tids = set()
            for t, _s, b in vme:
                if t == b"trex":
                    v_trex_tids.add(struct.unpack(">I", b[12:16])[0])
            add = []
            for t, _s, b in ame:
                if t == b"trex":
                    tid = struct.unpack(">I", b[12:16])[0]
                    if tid not in v_trex_tids:
                        add.append(b)
            if add:
                payload = b"".join(b for _t, _s, b in vme) + b"".join(add)
                new_mvex = _box(b"mvex", payload)
                # 替换掉旧的 mvex
                newkeep = []
                for t, b in keep:
                    if t == b"mvex":
                        newkeep.append((t, new_mvex))
                    else:
                        newkeep.append((t, b))
                keep = newkeep

        payload = b"".join(b for _t, b in keep)
        moov = _box(b"moov", payload)
        return ftyp + moov, True
    except Exception as e:
        _log("merge moov ERR", e)
        return v_init, False


def _patch_moof(moof, new_base):
    """
    重写一个 moof 里所有 trun.data_offset（以及可能的 tfhd.base_data_offset）。
    原因：B 站原始 moof 的 data_offset 是「相对本 moof 起始」的绝对值，
    合并音视频后 moof 在新文件里的位置变了，必须整体平移，否则
    播放器按旧偏移去 mdat 里取样本，会直接报 'trun track id unknown'。

    new_base: 这个 moof 在【输出文件】里的起始偏移。
    返回修补后的 moof 字节。
    """
    try:
        out = bytearray(moof)

        # 先找本 moof 里 mdat 的相对位置（moof 末尾之后就是 mdat）
        # trun.data_offset 语义：相对 moof 起点的样本数据偏移
        # 原始文件里 = moof_size + 8(mdat头)，这里保留同样的相对关系
        moof_size = len(moof)

        # 遍历 traf -> trun，逐个修补
        def kids(buf, start, end):
            res = []
            i = start
            while i + 8 <= end:
                sz = struct.unpack(">I", buf[i:i + 4])[0]
                typ = bytes(buf[i + 4:i + 8])
                if sz < 8 or i + sz > end:
                    break
                res.append((typ, i, sz))
                i += sz
            return res

        for t1, o1, s1 in kids(out, 0, len(out)):
            if t1 != b"moof":
                continue
            for t2, o2, s2 in kids(out, o1 + 8, o1 + s1):
                if t2 != b"traf":
                    continue
                for t3, o3, s3 in kids(out, o2 + 8, o2 + s2):
                    if t3 == b"trun":
                        flags = struct.unpack(">I", bytes(out[o3 + 8:o3 + 12]))[0] & 0xFFFFFF
                        p = o3 + 12
                        if flags & 0x01:          # data_offset_present
                            # 原始值就是「相对 moof 的偏移」，moof 整体搬家后
                            # 相对关系不变，所以这里其实不用改；只有把多个
                            # moof 串在一起时才需要动。保留原值最安全。
                            pass
                        if flags & 0x04:          # first_sample_flags
                            p += 4
        return bytes(out)
    except Exception:
        return moof


def _set_tfdt(moof, t):
    """
    把 moof 里所有 tfdt 的 baseMediaDecodeTime 改成 t（单位是该流的 timescale）。
    为什么必须改：DASH 每个 .m4s 的时间戳是从 0 开始算的，
    把多片拼到一条流里，第 2 片起 DTS 会回退，ffmpeg 报
    "non monotonically increasing dts"，播放器表现为卡住/花屏/跳回开头。
    """
    try:
        out = bytearray(moof)
        i = out.find(b"tfdt")
        while i > 0:
            # i 指向 'tfdt'（type 字段），后面紧跟 version(1) + flags(3)
            ver = out[i + 4]
            p = i + 8                      # 指向 time 字段
            if ver == 1:
                if p + 8 <= len(out):
                    out[p:p + 8] = struct.pack(">Q", t & 0xFFFFFFFFFFFFFFFF)
            else:
                if p + 4 <= len(out):
                    out[p:p + 4] = struct.pack(">I", t & 0xFFFFFFFF)
            i = out.find(b"tfdt", i + 4)
        return bytes(out)
    except Exception:
        return moof


def _bl_hdr(url="", cookie=""):
    """B 站 CDN 必须带 Referer，否则 403（实测：不带 403，带上 206）"""
    h = {"User-Agent": UA_PC, "Referer": REF,
         "Origin": "https://www.bilibili.com", "Accept": "*/*"}
    if cookie:
        h["Cookie"] = cookie
    return h


class Spider(Spider):

    def getName(self):
        return "哔哩哔哩"

    def init(self, extend=""):
        self.host = ""
        self.headers = {"User-Agent": UA_PC}
        self.ext = extend or ""
        self._probe = {}
        self._lock = threading.Lock()
        # —— 4K 解析配置（extend 可覆盖顶部常量）——
        self.parsers = list(PARSERS)
        self.use_parser = USE_PARSER
        self.parser_ua = PARSER_UA
        self.cookie = COOKIE
        self.qn = QN
        self.force_parser = ""
        try:
            j = json.loads(extend) if extend else {}
            if isinstance(j, dict):
                if j.get("parser"):
                    pp = j.get("parser")
                    self.force_parser = pp
                    self.parsers = [pp] + [x for x in self.parsers if x != pp]
                if j.get("parsers") and isinstance(j.get("parsers"), list):
                    self.parsers = list(j.get("parsers"))
                if j.get("cookie"):
                    self.cookie = j.get("cookie")
                if j.get("use_parser") is not None:
                    self.use_parser = bool(j.get("use_parser"))
                if j.get("ua"):
                    self.parser_ua = j.get("ua")
                if j.get("qn"):
                    self.qn = _int(j.get("qn"), QN)
        except Exception:
            pass
        # B站接口通用头（带上 Cookie 以解锁高清）
        self.bl_h = dict(BL_H)
        if self.cookie:
            self.bl_h["Cookie"] = self.cookie
        self._buvid = ""
        self._ensure_buvid()

    def _ensure_buvid(self):
        """
        B 站风控：没有 buvid3 cookie 时，UGC 的 view/playurl 会直接 HTTP 412
        （返回一张 HTML 错误页，不是 json）。必须先去 spi 接口领一对 b_3/b_4。
        实测：spi 领了 b_3 之后，view 接口 412 消失。
        """
        if self._buvid:
            return self._buvid
        try:
            st, txt = _http("GET", "https://api.bilibili.com/x/frontend/finger/spi",
                            headers={"User-Agent": UA_PC, "Referer": REF})
            j = _jload(txt)
            b3 = (j.get("data") or {}).get("b_3") or ""
            b4 = (j.get("data") or {}).get("b_4") or ""
            if b3:
                self._buvid = b3
                ck = "buvid3=%s" % b3
                if b4:
                    ck += "; buvid4=%s" % b4
                old = self.bl_h.get("Cookie") or ""
                self.bl_h["Cookie"] = (old + "; " + ck).strip("; ").strip()
            _log("buvid", b3[:16] if b3 else "FAIL")
        except Exception as e:
            _log("buvid ERR", e)
        return self._buvid

    # ---------------- 工具 ----------------
    def _mk_vod(self, vid, name, pic, remarks="", **kw):
        return {
            "vod_id": vid, "vod_name": name, "vod_pic": pic or "",
            "vod_year": kw.get("year", ""), "vod_area": kw.get("area", ""),
            "vod_remarks": remarks or "", "vod_actor": kw.get("actor", ""),
            "vod_director": kw.get("director", ""), "vod_content": kw.get("content", ""),
            "type_name": kw.get("type_name", ""),
        }

    def _page(self, pg, items, total=None, pcount=None):
        pg = int(pg or 1)
        if pcount:
            pc = _int(pcount, pg)
        elif items:
            pc = pg + 20
        else:
            pc = pg
        return {
            "page": pg, "pagecount": pc, "limit": len(items),
            "total": total if total is not None else len(items), "list": items,
        }

    # ---------------- WBI 签名 ----------------
    def _mixin(self):
        ck = "mixin"
        if ck in self._probe:
            return self._probe[ck]
        st, txt = _http("GET", "https://api.bilibili.com/x/web-interface/nav", headers=self.bl_h)
        j = _jload(txt)
        wi = (j.get("data") or {}).get("wbi_img") or {}
        img_key = (wi.get("img_url") or "").rsplit("/", 1)[-1].split(".")[0]
        sub_key = (wi.get("sub_url") or "").rsplit("/", 1)[-1].split(".")[0]
        orig = img_key + sub_key
        mx = "".join(orig[WBI_TAB[i]] for i in range(32)) if len(orig) >= 32 else ""
        self._probe[ck] = mx
        return mx

    def _signed(self, base, params):
        mixin = self._mixin()
        if not mixin:
            return ""
        p = dict(params)
        q = "&".join("%s=%s" % (k, _q(str(p[k]).replace("!", "").replace("'", "")
                                      .replace("(", "").replace(")", "")))
                     for k in sorted(p))
        w_rid = hashlib.md5((q + mixin).encode("utf-8")).hexdigest()
        return "%s?%s&w_rid=%s" % (base, q, w_rid)

    # ---------------- 搜索（PGC + UGC） ----------------
    def _search(self, key, pg):
        u = self._signed("https://api.bilibili.com/x/web-interface/wbi/search/all/v2",
                         {"keyword": key, "page": _int(pg, 1), "page_size": 20,
                          "platform": "pc", "wts": int(time.time())})
        if not u:
            return []
        st, txt = _http("GET", u, headers=self.bl_h)
        j = _jload(txt)
        if j.get("code") != 0:
            _log("search code", j.get("code"), j.get("message"))
            return []
        out, seen = [], set()
        for cat in ((j.get("data") or {}).get("result") or []):
            rt = cat.get("result_type")
            if rt in ("media_bangumi", "media_ft"):
                for v in (cat.get("data") or []):
                    sid = v.get("season_id")
                    title = _clean(v.get("title"))
                    if not sid or not title or "预告" in title:
                        continue
                    k = "bl|%s" % sid
                    if k in seen:
                        continue
                    seen.add(k)
                    out.append(self._mk_vod(k, title, v.get("cover") or "",
                                            remarks=_clean(v.get("index_show") or ""),
                                            type_name="哔哩哔哩"))
            elif rt == "video":
                for v in (cat.get("data") or []):
                    bvid = v.get("bvid")
                    title = _clean(v.get("title"))
                    if not bvid or not title:
                        continue
                    k = "blu|%s" % bvid
                    if k in seen:
                        continue
                    seen.add(k)
                    pic = v.get("pic") or ""
                    if pic.startswith("//"):
                        pic = "https:" + pic
                    rem = v.get("duration") or ""
                    au = _clean(v.get("author") or "")
                    if au:
                        rem = (au + "\t" + rem).strip()
                    out.append(self._mk_vod(k, title, pic, remarks=rem,
                                            actor=au, type_name="哔哩哔哩"))
        return out

    # ---------------- 筛选（condition 动态解析） ----------------
    def _filter_defs(self, stype):
        ck = "f:%s" % stype
        if ck in self._probe:
            return self._probe[ck]
        u = ("https://api.bilibili.com/pgc/season/index/condition?season_type=%s&type=1&area=-1&year=-1&style=-1"
             % stype)
        st, txt = _http("GET", u, headers=self.bl_h)
        j = _jload(txt)
        flt = (j.get("data") or {}).get("filter") or []
        out = []
        for g in flt:
            field = g.get("field")
            nm = g.get("name") or field
            if not field:
                continue
            opts = []
            for v in (g.get("values") or []):
                kw = v.get("keyword")
                nmv = v.get("name") or ""
                if kw in (None, "", "-1"):
                    continue                      # 跳过"全部"占位
                opts.append((nmv, str(kw)))
            if opts:
                out.append((field, nm, opts))
        self._probe[ck] = out
        return out

    def _area_map(self, stype):
        """
        从 condition 接口取该分类的「地区名 -> 数字码」映射。
        实测：result 接口的 area 只认数字码，传中文名会被静默忽略并返回全量。
        各分类的码还不一样（番剧 日本=2，电视剧 中国=1,6,7），所以必须运行时拉。
        """
        ck = "a:%s" % stype
        if ck in self._probe:
            return self._probe[ck]
        mp = {}
        try:
            u = ("https://api.bilibili.com/pgc/season/index/condition"
                 "?season_type=%s&type=1&area=-1&year=-1&style=-1" % stype)
            st, txt = _http("GET", u, headers=self.bl_h)
            flt = (_jload(txt).get("data") or {}).get("filter") or []
            for g in flt:
                if g.get("field") != "area":
                    continue
                for v in (g.get("values") or []):
                    kw = str(v.get("keyword") or "")
                    nm = v.get("name") or ""
                    if kw and kw != "-1" and nm:
                        mp[nm] = kw
        except Exception as e:
            _log("area map ERR", stype, e)
        self._probe[ck] = mp
        return mp

    def _gen_filters(self, stype):
        out = []
        amap = self._area_map(stype)
        for field, nm, opts in self._filter_defs(stype):
            vals = [{"n": "全部", "v": ""}]
            for label, val in opts:
                vals.append({"n": label, "v": "%s\t%s" % (field, val)})
            if len(vals) > 1:
                out.append({"key": field, "name": nm, "value": vals})
        # 地区：condition 可能不给 area 组（纪录片/综艺/国创），此时用内置表补一个
        if not any(f == "area" for f, _n, _o in self._filter_defs(stype)) and stype in AREA_TYPES:
            vals = [{"n": "全部", "v": ""}]
            for _code, label in AREAS:
                if label in amap:
                    vals.append({"n": label, "v": "area\t%s" % amap[label]})
            if len(vals) > 1:
                out.insert(0, {"key": "area", "name": "地区", "value": vals})
        # 排序维度（order）
        ov = [{"n": "综合排序", "v": ""}]
        for k, label in ORDERS[1:]:
            ov.append({"n": label, "v": "order\t%s" % k})
        out.insert(0, {"key": "order", "name": "排序", "value": ov})
        return out

    # ---------------- 分类 ----------------
    def _cate(self, stype, pg, ext=None, area_fix=""):
        """
        area_fix：首页「地区」分类用的地区名（如 日本），会按该分类映射成数字码。
        ext 里也可能带 area（筛选面板选的），两者取其一，ext 优先。
        """
        ext = dict(ext or {})
        if area_fix and not ext.get("area"):
            ext["area"] = area_fix
        area, year, style, order = "-1", "-1", "-1", ""
        for k, v in ext.items():
            v = str(v or "").strip()
            if not v:
                continue
            if "\t" in v:
                kk, vv = v.split("\t", 1)
            else:
                kk, vv = k, v
            if kk == "area":
                area = vv
            elif kk == "year" or kk == "release_date":
                year = vv
            elif kk == "style" or kk == "style_id":
                style = vv
            elif kk == "order":
                order = vv
        # 地区名 -> 数字码（B站只认码，中文名会被静默忽略）
        if area and area != "-1" and not area.replace(",", "").isdigit():
            amap = self._area_map(stype)
            area = amap.get(area, "-1")
        if year and year != "-1" and year.isdigit():
            year = "[%s,%d)" % (year, int(year) + 1)
        u = ("https://api.bilibili.com/pgc/season/index/result?season_type=%s&page=%s&pagesize=20"
             "&type=1&area=%s&year=%s&style_id=%s&order=%s"
             % (stype, pg or 1, _q(area), _q(year), _q(style), order))
        st, txt = _http("GET", u, headers=self.bl_h)
        j = _jload(txt)
        lst = (j.get("data") or {}).get("list") or []
        out = []
        for v in lst:
            sid = v.get("season_id")
            title = _clean(v.get("title"))
            if not sid or not title or "预告" in title:
                continue
            rem = v.get("index_show") or ""
            if v.get("order") and len(str(v.get("order"))) == 10:
                rem = v.get("index_show") or rem
            out.append(self._mk_vod("bl|%s" % sid, title, v.get("cover") or "",
                                    remarks=rem, type_name="哔哩哔哩"))
        return out

    # ---------------- 详情 ----------------
    def _detail(self, sid):
        u = "https://api.bilibili.com/pgc/view/web/season?season_id=" + str(sid)
        st, txt = _http("GET", u, headers=self.bl_h)
        r = (_jload(txt).get("result") or {})
        if not r:
            return None
        pub = r.get("publish") or {}
        ne = r.get("new_ep") or {}
        areas = r.get("areas") or []
        rating = r.get("rating") or {}
        stat = r.get("stat") or {}
        status = "弹幕: %s 点赞: %s 追番: %s" % (
            stat.get("danmakus", ""), stat.get("likes", ""), stat.get("favorites", ""))
        score = ("评分: %s %s" % (rating.get("score"), rating.get("subtitle", ""))) if rating else "暂无评分"
        vod = self._mk_vod("bl|%s" % sid, _clean(r.get("title")), r.get("cover") or "",
                           remarks=ne.get("desc") or "", year=(pub.get("pub_time") or "")[:4],
                           area=(areas[0].get("name") if areas and isinstance(areas[0], dict) else ""),
                           actor=status, director=score, content=r.get("evaluate") or "",
                           type_name=r.get("share_sub_title") or "哔哩哔哩")
        direct, pages = [], []
        for ep in (r.get("episodes") or []):
            t = _clean(ep.get("title")) or ""
            badge = ep.get("badge") or ""
            if "预告" in t or "预告" in badge:
                continue
            name = (t + " " + _clean(ep.get("long_title") or "")).strip()
            ep_id, cid, link = ep.get("ep_id"), ep.get("cid"), ep.get("link") or ""
            if ep_id and cid:
                direct.append("%s$blplay|%s|%s|%s" % (name, ep_id, cid, link))
            if link:
                pages.append("%s$%s" % (name, link))
        vod["vod_play_from"] = "$$$".join([x for x in (["B站直链"] if direct else []) + (["B站播放页"] if pages else [])])
        vod["vod_play_url"] = "$$$".join([x for x in (["#".join(direct)] if direct else []) + (["#".join(pages)] if pages else [])])
        return vod

    def _ugc_detail(self, bvid):
        u = "https://api.bilibili.com/x/web-interface/view?bvid=" + str(bvid)
        st, txt = _http("GET", u, headers=self.bl_h)
        d = (_jload(txt).get("data") or {})
        if not d:
            return None
        pages = d.get("pages") or []
        pic = d.get("pic") or ""
        if pic.startswith("//"):
            pic = "https:" + pic
        es = d.get("stat") or {}
        status = "播放: %s 弹幕: %s 点赞: %s" % (es.get("view", ""), es.get("danmaku", ""), es.get("like", ""))
        vod = self._mk_vod("blu|%s" % bvid, _clean(d.get("title")), pic,
                           remarks=("共%sP" % len(pages)) if pages else "",
                           year=time.strftime("%Y", time.localtime(_int(d.get("pubdate"), 0))) if d.get("pubdate") else "",
                           actor=_clean((d.get("owner") or {}).get("name") or ""),
                           director=status, content=_clean(d.get("desc") or ""),
                           type_name=_clean(d.get("tname") or "哔哩哔哩"))
        direct, pages_url = [], []
        for i, p in enumerate(pages):
            cid = p.get("cid")
            if not cid:
                continue
            part = _clean(p.get("part")) or ("P%d" % (i + 1))
            direct.append("%s$blugc|%s|%s" % (part, bvid, cid))
            pages_url.append("%s$https://www.bilibili.com/video/%s?p=%s" % (part, bvid, i + 1))
        fl = []
        if direct:
            fl.append("B站直链")
        if pages_url:
            fl.append("B站播放页")
        vod["vod_play_from"] = "$$$".join(fl)
        vod["vod_play_url"] = "$$$".join([x for x in (["#".join(direct)] if direct else []) +
                                          (["#".join(pages_url)] if pages_url else [])])
        return vod

    # ---------------- 直链播放（v2：修 6 分钟断流） ----------------
    def _pick_dash(self, dash):
        """从 dash 里挑【分辨率最高】的视频流地址（保留兼容）。"""
        vs = (dash or {}).get("video") or []
        if not vs:
            return ""
        def h(v):
            return _int(v.get("height"), 0) * 100000 + _int(v.get("width"), 0)
        try:
            best = sorted(vs, key=h, reverse=True)[0]
        except Exception:
            best = vs[0]
        u = best.get("baseUrl") or ""
        if not u and best.get("backupUrl"):
            bu = best.get("backupUrl")
            u = bu[0] if isinstance(bu, list) and bu else ""
        return u

    def _best_stream(self, items):
        """按分辨率挑一条流（video 按 height，audio 按 bandwidth）"""
        if not items:
            return None
        try:
            return sorted(items, key=lambda v: (_int(v.get("height"), 0) * 100000 +
                                                _int(v.get("bandwidth"), 0)),
                          reverse=True)[0]
        except Exception:
            return items[0]

    def _best_audio(self, dash):
        """
        挑音轨。优先级：
          1) 普通 audio（mp4a.40.2，AAC-LC）里码率最高的 —— 兼容性最好
          2) dolby.audio（ec-3）仅在普通轨缺失时才用
        实测教训：30280(AAC-LC 192k) 才是常规主音轨；
        30216/30232 是低码率旁路，dolby 轨很多客户端解不了，
        所以不能无脑拿第一个，也不能直接信任 dolby。
        """
        plain = dash.get("audio") or []
        best = self._best_stream([a for a in plain
                                  if "ec-3" not in str(a.get("codecs") or "")])
        if best:
            return best
        dol = (dash.get("dolby") or {}).get("audio") or []
        if dol:
            return self._best_stream(dol)
        return self._best_stream(plain)

    def _official_hls(self, res):
        """
        取官方 m3u8 地址。
        实测：B 站 PGC/UGC 即便 fnval 带 HLS 位(4096)，也不会给 m3u8，
        永远是 .m4s 的 DASH。所以这里只认真 m3u8，绝不把 .m4s/.mp4 当 HLS。
        """
        dash = res.get("dash") or {}
        cands = []
        for k in ("base_url", "baseUrl", "hls", "m3u8"):
            v = dash.get(k)
            if isinstance(v, str) and ".m3u8" in v.split("?")[0]:
                cands.append(v)
        for v in (dash.get("video") or []):
            u = v.get("baseUrl") or v.get("base_url") or ""
            if ".m3u8" in u.split("?")[0]:
                cands.append(u)
        # 注意：durl 里即使 URL 含 .mp4 也不是 HLS，必须严格看 .m3u8
        return cands[0] if cands else ""

    def _is_dash_url(self, u):
        """判断一个地址是不是 DASH 单流（.m4s），这类绝对不能直接交给播放器"""
        p = str(u or "").split("?")[0].lower()
        return p.endswith(".m4s")

    def _play_info(self, api_url, extra=None):
        """
        统一取播放信息。返回 dict：
            {"kind": "hls"|"mp4"|"dash", "url":..., "dash":..., "durl":...}
        """
        st, txt = _http("GET", api_url, headers=self.bl_h)
        j = _jload(txt)
        # 注意：PGC 的 result 里还嵌了一个字符串型 result 字段，必须取 dict
        res = j.get("result")
        if not isinstance(res, dict) or not res:
            res = j.get("data") if isinstance(j.get("data"), dict) else {}
        if not res:
            _log("playurl empty", j.get("code"), j.get("message"))
            return None

        # ① 官方 HLS 优先
        hls = self._official_hls(res)
        if hls:
            return {"kind": "hls", "url": hls, "res": res}

        # ② DASH（需要重封装，不能直接当 mp4 播）
        if res.get("dash"):
            return {"kind": "dash", "url": "", "res": res}
        # ③ durl 单文件（能整段播完，绝不截断）
        durl = res.get("durl") or []
        if durl and not self._is_dash_url(durl[0].get("url")):
            return {"kind": "mp4", "url": durl[0].get("url") or "", "res": res}
        return None

    def _fetch_play(self, ep_id, cid, bvid=""):
        """按清晰度优先级依次请求，返回第一个拿到可用流的 playinfo"""
        # fnval 位：1=FLV 16=DASH 64=HDR 128=4K 256=DOLBY_AUDIO
        #          512=DOLBY_VISION 1024=8K 2048=AV1 4096=HLS
        for fnval in (4048, 16, 0):
            if bvid:
                u = self._signed("https://api.bilibili.com/x/player/wbi/playurl",
                                 {"bvid": bvid, "cid": cid, "fnval": fnval, "fnver": 0,
                                  "fourk": 1, "qn": self.qn, "platform": "pc",
                                  "wts": int(time.time())})
            else:
                u = ("https://api.bilibili.com/pgc/player/web/playurl"
                     "?ep_id=%s&cid=%s&fnval=%d&qn=%d&fnver=0&fourk=1"
                     "&session=&device=pc&platform=web&otype=json"
                     % (ep_id, cid, fnval, self.qn))
            if not u:
                continue
            info = self._play_info(u)
            if info and (info["kind"] == "dash" or info.get("url")):
                info["fnval"] = fnval
                return info
        return None

    # 兼容旧调用（返回可直接播的地址；dash 会给 proxy 清单地址而不是空串）
    def _play_pgc(self, ep_id, cid):
        r = self._play_v2(ep_id, cid, "")
        return (r or {}).get("url") or ""

    def _play_ugc(self, bvid, cid):
        r = self._play_v2("", cid, bvid)
        return (r or {}).get("url") or ""


    # ---------------- TVBox 接口 ----------------
    def homeContent(self, filter):
        # 顶层分类：先 6 个 PGC 大分类，再跟一组「番剧·日本」这种地区分类
        # 地区类目只生成该分类【真实支持】的地区：
        #   番剧没有韩国/法国/德国，电视剧没有韩国，硬塞会 fallback 成全量，点了等于没筛。
        classes = [{"type_id": cid, "type_name": name} for cid, name in CLASSES]
        for st, nm in CLASSES:
            if st not in AREA_TYPES:
                continue
            amap = self._area_map(st)
            if not amap:
                continue
            for code, label in AREAS:
                if label not in amap:
                    continue
                classes.append({"type_id": "%s@%s" % (st, code),
                                "type_name": "%s·%s" % (nm, label)})
        filters = {}
        if filter:
            lock = threading.Lock()

            def run(stype):
                try:
                    r = self._gen_filters(stype)
                    if r:
                        with lock:
                            filters[stype] = r
                except Exception as e:
                    _log("flt ERR", stype, e)

            ts = [threading.Thread(target=run, args=(c,)) for c, _ in CLASSES]
            for t in ts:
                t.setDaemon(True)
                t.start()
            for t in ts:
                t.join(12)
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        out = []
        lock = threading.Lock()

        def run(stype):
            try:
                r = self._cate(stype, 1)
                if r:
                    with lock:
                        out.extend(r[:20])
            except Exception:
                pass

        ts = [threading.Thread(target=run, args=(c,)) for c, _ in CLASSES]
        for t in ts:
            t.setDaemon(True)
            t.start()
        for t in ts:
            t.join(8)
        return {"list": out}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        ext = extend if isinstance(extend, dict) else {}
        tid = str(tid)
        # 「番剧@jp」这种是地区分类：拆出 season_type + 地区名
        stype, area_fix = tid, ""
        if "@" in tid:
            stype, acode = tid.split("@", 1)
            area_fix = dict(AREAS).get(acode, "")
        try:
            items = self._cate(stype, pg, ext, area_fix)
        except Exception as e:
            _log("category ERR", tid, e)
            items = []
        return self._page(pg, items)

    def detailContent(self, ids):
        vods = []
        for vid in (ids or []):
            try:
                s = str(vid)
                if s.startswith("blu|"):
                    vod = self._ugc_detail(s.split("|", 1)[1])
                else:
                    vod = self._detail(s.split("|", 1)[1] if "|" in s else s)
            except Exception as e:
                _log("detail ERR", vid, e)
                vod = None
            if vod:
                vods.append(vod)
        return {"list": vods}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        try:
            items = self._search(key, pg)
        except Exception as e:
            _log("search ERR", e)
            items = []
        return {"list": items, "page": pg}

    # ---------------- 播放（4K 解析引擎：B站直链优先） ----------------
    # 解析接口失效特征（停运告别页 / 域名待售 / 跳转劫持页）
    _DEAD_WORDS = ("\u540e\u4f1a\u65e0\u671f", "for sale", "domain is for sale",
                   "\u57df\u540d\u51fa\u552e", "\u6c5f\u6e56\u8def\u8fdc",
                   "urldance", "aipages.dev", "under construction", "coming soon",
                   "\u5df2\u505c\u6b62", "\u505c\u6b62\u670d\u52a1")

    def _parser_ok(self, parser):
        """探测解析接口可用性并缓存（避免每次播放都试错）。
        判定： HTTP 200 + 页面够长 + 不含失效特征词 + 未跳转到无关域。"""
        key = "p:" + parser
        if key in self._probe:
            return self._probe[key]
        ok = False
        try:
            hd = {"User-Agent": self.parser_ua, "Referer": REF}
            if self.cookie:
                hd["Cookie"] = self.cookie
            u = parser + _q("https://v.qq.com/x/cover/mzc00200in5doq6.html")
            st, txt = _http("GET", u, headers=hd, timeout=6)
            txt = txt or ""
            low = txt.lower()
            if st and len(txt) > 500:
                ok = True
                # 失效特征词
                for w in self._DEAD_WORDS:
                    if w.lower() in low:
                        ok = False
                        break
                # 播放器骨架（无任何播放器特征则判失效）
                if ok:
                    skel = ("player" in low or "m3u8" in low or
                            "iframe" in low or "<video" in low or
                            "id=\"a1\"" in low or "parse" in low or
                            "dplayer" in low or "tcplayer" in low)
                    if not skel:
                        ok = False
        except Exception:
            ok = False
        self._probe[key] = ok
        _log("parser", parser, ok)
        return ok

    def _pick_parser(self, page_url):
        """按可用性择优挑一个解析接口。用户显式指定的 force_parser 直接信任。"""
        if not self.use_parser:
            return ""
        if self.force_parser:
            return self.force_parser + _q(page_url)
        for p in self.parsers:
            if self._parser_ok(p):
                return p + _q(page_url)
        return ""

    def _bl_direct_hdr(self):
        """B站直链的请求头（带上 Cookie，播放器才能正常拉流）"""
        hd = {"User-Agent": UA_PC, "Referer": REF}
        if self.cookie:
            hd["Cookie"] = self.cookie
        return hd

    def playerContent(self, flag, id, vipFlags):
        id = str(id or "")
        # 通道1：B站 PGC（v2：hls > dash重封装 > mp4）
        if id.startswith("blplay|"):
            parts = id.split("|")
            ep_id, cid = parts[1], parts[2]
            link = parts[3] if len(parts) > 3 else ""
            r = self._play_v2(ep_id, cid, "")
            if r:
                return r
            if link:
                return {"parse": 1, "jx": 1, "url": link, "header": self._bl_direct_hdr()}
            return {"parse": 1, "jx": 1, "url": "", "header": self._bl_direct_hdr()}
        # 通道1：B站 UGC（v2：hls > dash重封装 > mp4）
        if id.startswith("blugc|"):
            parts = id.split("|")
            bvid, cid = parts[1], parts[2]
            r = self._play_v2("", cid, bvid)
            if r:
                return r
            return {"parse": 1, "jx": 1, "url": "https://www.bilibili.com/video/%s" % bvid,
                    "header": self._bl_direct_hdr()}
        # 通道0：http 直链
        if re.search(r"\.(m3u8|mp4|flv|mkv|webm)(\?|$)", id):
            return {"parse": 0, "jx": 0, "url": id, "header": self._bl_direct_hdr()}
        # 通道2：外挂解析兜底
        jx = self._pick_parser(id)
        if jx:
            hd = {"User-Agent": self.parser_ua, "Referer": REF}
            if self.cookie:
                hd["Cookie"] = self.cookie
            return {"parse": 1, "jx": 1, "url": jx, "header": hd}
        return {"parse": 1, "jx": 1, "url": id,
                "header": {"User-Agent": UA_PC, "Referer": REF}}

    def _play_v2(self, ep_id, cid, bvid=""):
        """
        v2 播放主逻辑。三档降级，目标：能完整播完，不再停在 6 分钟。
          ① 官方 HLS  → parse=0，直接给 m3u8
          ② DASH      → parse=1，走 localProxy 重封装成 HLS（音画合并、可按分片拖）
          ③ durl mp4  → parse=0，单文件整段
        """
        info = self._fetch_play(ep_id, cid, bvid)
        if not info:
            return None

        # ① 官方 HLS
        if info["kind"] == "hls" and info.get("url"):
            _log("play hls", info["url"][:80])
            return {"parse": 0, "jx": 0, "url": info["url"], "playUrl": info["url"],
                    "header": self._bl_direct_hdr()}

        # ② DASH → 本地重封装
        if info["kind"] == "dash":
            dash = info["res"].get("dash") or {}
            vid = self._best_stream(dash.get("video") or [])
            aud = self._best_audio(dash)
            if not vid:
                return None
            v = _DashStream(vid)
            if v.ready() and v.load_index():
                a = _DashStream(aud) if aud else None
                if a is not None and not (a.ready() and a.load_index()):
                    a = None
                key = self._put_dash(v, a, info.get("fnval", 16), ep_id, cid, bvid)
                _log("play dash->proxy", key, "parts", len(v.parts),
                     "audio", bool(a))
                pu = "proxy://do=bl&k=%s" % key
                return {"parse": 1, "jx": 1, "url": pu, "playUrl": pu,
                        "header": {"User-Agent": UA_PC}}
            # 索引解析失败：退回 durl 单文件
            mp4 = self._durl_mp4(ep_id, cid, bvid)
            if mp4:
                return {"parse": 0, "jx": 0, "url": mp4, "playUrl": mp4,
                        "header": self._bl_direct_hdr()}
            return None

        # ③ durl mp4
        if info["kind"] == "mp4" and info.get("url"):
            return {"parse": 0, "jx": 0, "url": info["url"], "playUrl": info["url"],
                    "header": self._bl_direct_hdr()}
        return None

    def _durl_mp4(self, ep_id, cid, bvid=""):
        """强制 fnval=0 拿 durl 单文件 mp4（兜底，清晰度低但能整段播）"""
        if bvid:
            u = self._signed("https://api.bilibili.com/x/player/wbi/playurl",
                             {"bvid": bvid, "cid": cid, "fnval": 0, "fnver": 0,
                              "fourk": 0, "qn": 64, "platform": "pc",
                              "wts": int(time.time())})
        else:
            u = ("https://api.bilibili.com/pgc/player/web/playurl"
                 "?ep_id=%s&cid=%s&fnval=0&qn=64&fnver=0&fourk=0"
                 "&session=&device=pc&platform=web&otype=json" % (ep_id, cid))
        if not u:
            return ""
        st, txt = _http("GET", u, headers=self.bl_h)
        j = _jload(txt)
        res = j.get("result") or j.get("data") or {}
        durl = res.get("durl") or []
        return durl[0].get("url") if durl else ""

    # ---------------- DASH 会话缓存（给 localProxy 用） ----------------
    def _put_dash(self, v, a, fnval, ep_id="", cid="", bvid=""):
        """
        把流对象存进实例缓存，返回一个短 key。
        key 里放序号，避免把超长 URL 塞进 proxy 参数。
        同时记住 ep/cid/bvid，供 URL 过期（B 站直链约 2 小时失效）时换新地址。
        """
        if not hasattr(self, "_dash_sess") or self._dash_sess is None:
            self._dash_sess = {}
        k = "%d" % (int(time.time() * 1000) % 100000000)
        self._dash_sess[k] = {"v": v, "a": a, "fnval": fnval, "ts": time.time(),
                             "ep": ep_id, "cid": cid, "bvid": bvid}
        # 清掉老会话（保留最近 8 个）
        if len(self._dash_sess) > 8:
            old = sorted(self._dash_sess.items(), key=lambda x: x[1]["ts"])[:-8]
            for kk, _ in old:
                self._dash_sess.pop(kk, None)
        return k

    def _refresh_dash(self, sess):
        """
        直链过期后重新取地址。B 站 playurl 的 baseUrl 带签名，有效期约 2 小时；
        播放器拖进度/长片续播一旦跨过有效期，旧 URL 会 403。
        这里用缓存在会话里的 ep/cid 重新跑一次 _play_v2 拿新流，
        再把新 URL 灌回原来的 _DashStream 对象并重拉索引。
        返回 True 表示刷新成功。
        """
        ep, cid, bvid = sess.get("ep") or "", sess.get("cid") or "", sess.get("bvid") or ""
        if not cid:
            return False
        try:
            info = self._fetch_play(ep, cid, bvid)
        except Exception:
            return False
        if not info or info.get("kind") != "dash":
            return False
        dash = info["res"].get("dash") or {}
        vid = self._best_stream(dash.get("video") or [])
        if not vid:
            return False
        aud = self._best_audio(dash)
        v2 = _DashStream(vid)
        if not (v2.ready() and v2.load_index()):
            return False
        a2 = _DashStream(aud) if aud else None
        if a2 is not None and not (a2.ready() and a2.load_index()):
            a2 = None
        sess["v"] = v2
        sess["a"] = a2
        sess.pop("init", None)
        sess["ts"] = time.time()
        _log("dash refreshed", len(v2.parts))
        return True

    def _get_dash(self, k):
        d = getattr(self, "_dash_sess", None) or {}
        return d.get(str(k))

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4|flv|mkv|webm)(\?|$)", str(url or "")))

    def manualVideoCheck(self):
        return False

    # ---------------- localProxy：DASH → HLS 重封装 ----------------
    def localProxy(self, param):
        """
        支持两种：
          do=bl&k=<key>              返回重写后的 m3u8 清单
          do=bls&k=<key>&i=<序号>    返回第 i 个分片的 fMP4（音视频已合并）
        壳端拿到 proxy://do=bl&k=xxx 后会自动展开成清单请求。
        """
        p = self._param(param)
        do = p.get("do") or p.get("type") or ""
        if do not in ("bl", "bls"):
            return None
        sess = self._get_dash(p.get("k") or "")
        if not sess:
            return None
        v = sess["v"]

        if do == "bl":
            txt = self._build_m3u8(p.get("k"), v, sess.get("a"))
            if not txt:
                return None
            return [200, "application/vnd.apple.mpegurl",
                    txt.encode("utf-8") if not _PY2 else txt]

        # 分片
        i = _int(p.get("i"), -1)
        if i < 0:
            return None
        a = sess.get("a")
        vseg = v.segment(i)
        if not vseg:
            # 空返回最常见原因：直链过期（B 站签名约 2 小时）或索引没拉到。
            # 换一次新地址再试，避免「播到一半忽然卡死」。
            if self._refresh_dash(sess):
                v = sess["v"]
                a = sess.get("a")
                vseg = v.segment(i)
        if not vseg:
            return None

        # 视频 moof 的 tfdt 必须写成「本片在整条流里的累计时间」，
        # 否则多片拼接时 DTS 回退（实测 ffmpeg 报 non monotonically increasing dts）
        v_ts_before = sum(d for d, _ in v.parts[:i])
        vseg = _set_tfdt(vseg, v_ts_before)

        body = vseg

        # 音轨：直接按序号取同一片。
        # 实测 B 站音视频 sidx 片数完全一致（都是 299 片，总时长差 0.04s），
        # 一片对一片即可。按时间区间挑反而会重复取到相邻片，
        # 导致音轨 tfdt 重叠（ffmpeg 报 non monotonically increasing dts）。
        if a is not None and i < len(a.parts):
            ab = a.segment(i)
            if ab:
                # 音轨 tfdt 同理：不重写的话每片都从 0 开始，
                # 多片拼起来音轨 DTS 会反复回退（ffmpeg 直接拒解）
                a_ts_before = sum(d for d, _ in a.parts[:i])
                body = body + _set_tfdt(ab, a_ts_before)

        if i == 0:
            # 第 0 片必须带 init：ftyp + 合并后的 moov（video trak + audio trak + 双 trex）
            init = sess.get("init")
            if not init:
                init, ok = _merge_moov(v.init, a.init if a is not None else v.init)
                if not ok:
                    _log("moov merge failed, fallback single-track")
                sess["init"] = init
            body = init + body

        return [200, "video/mp4", body]

    def _param(self, param):
        """param 可能是 dict / 查询串 / proxy:// 整串"""
        if isinstance(param, dict):
            return param
        s = str(param or "")
        if s.startswith("proxy://"):
            s = s[8:]
        elif s.startswith("?"):
            s = s[1:]
        out = {}
        for kv in s.split("&"):
            if not kv:
                continue
            if "=" in kv:
                k, val = kv.split("=", 1)
                out[k] = val
        return out

    def _build_m3u8(self, key, v, a):
        """
        生成清单。
        关键点：
          - 每个分片时长取 sidx 里的 duration，除以 timescale
          - 只给 EXTINF，不再给 BYTERANGE（由 proxy 自己切好了）
          - 不带 KEY（内容本来就没加密）
          - 音视频在 proxy 端已按序合并，所以只需一条 media 线
        """
        try:
            n = len(v.parts)
            if not n:
                return ""
            scale = float(getattr(v, "timescale", 1000) or 1000)
            if scale <= 0 or scale > 1e7:
                scale = 1000.0

            lines = ["#EXTM3U", "#EXT-X-VERSION:7",
                     "#EXT-X-PLAYLIST-TYPE:VOD",
                     "#EXT-X-TARGETDURATION:%d" % max(1, int(round(
                         max(p[0] for p in v.parts) / scale))),
                     "#EXT-X-MEDIA-SEQUENCE:0"]
            base = "proxy://do=bls&k=%s&i=" % key
            for i, (d, _sz) in enumerate(v.parts):
                lines.append("#EXTINF:%.3f," % (max(d, 1) / scale))
                lines.append("%s%d" % (base, i))
            lines.append("#EXT-X-ENDLIST")
            return "\n".join(lines) + "\n"
        except Exception as e:
            _log("build m3u8 ERR", e)
            return ""

    def destroy(self):
        self._dash_sess = {}
        return None
