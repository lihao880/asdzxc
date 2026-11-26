# coding: utf-8
# 片库4K（4k01.pianku.online）· Newbox / TVBox / FongMi Python 站源
# 站点类型：MACCMS 静态化 HTML 站（Cloudflare 后面，纯标准库即可抓取）。
# 路由：
#   分类 /vodtype/{tid}.html ，分页 /vodtype/{tid}-{pg}.html
#   详情 /voddetail/{id}.html
#   搜索 /vodsearch/-------------.html?wd={关键词}
#   播放 /vodplay/{id}-{sid}-{nid}.html  → 页内 var player_aaaa={...url:官方链接...}
# 播放方案（用网站自己的解析后端，不依赖任何第三方解析器/小白）：
#   站点播放页 var player_aaaa.url 是官方平台链接（youku/qq/bili...）。
#   同系（lyyytv）站点的自解析后端：
#       http://4kzj.lyyytv.cn/api/index?parsesId=1&appid=10001&videoUrl={官方链接}
#   返回 {"code":200,"url":"https://baidu.con/<16位key><base64密文>"}，
#   用前16字符当 key/iv 做 AES-CBC 解密，得到真实 m3u8/mpd 直链（api.69mzf.cn 等）。
#   全流程纯标准库实现，无第三方依赖。
import re
import json
import time
import base64
import urllib.parse
import urllib.request

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass

HOST = "https://4k01.pianku.online"
UA = "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"

# 网站自解析后端（lyyytv 同系，parsesId=1 实测可解 youku/qq/bili）
SITE_PARSE_API = "http://4kzj.lyyytv.cn/api/index?parsesId=1&appid=10001&videoUrl="
DEC_PREFIX = "https://baidu.con/"
# 网站自带的 LX 解析器入口（兜底用）
SITE_PARSE = "jx.lxyy.club"

# 分类导航（来自站点实际导航；tid 用站点真实 id）
CATEGORIES = [
    ("20", "电影"), ("21", "华语电影"), ("22", "欧美电影"), ("23", "日韩电影"),
    ("24", "动作片"), ("25", "喜剧片"), ("26", "爱情片"), ("27", "科幻片"),
    ("28", "恐怖片"), ("29", "悬疑片"), ("30", "犯罪片"), ("31", "战争片"),
    ("32", "纪录片"), ("33", "武侠片"), ("34", "奇幻片"), ("35", "动画片"),
    ("36", "其他片"), ("37", "剧集"), ("38", "国产剧"), ("39", "欧美剧"),
    ("40", "日韩剧"), ("41", "港台剧"), ("42", "泰国剧"), ("43", "动漫"),
    ("44", "国漫"), ("45", "综艺"), ("46", "综艺节目"), ("47", "短剧"),
]

FILTER_NAMES = {"class": "类型", "area": "地区", "lang": "语言", "year": "年份"}


# ---------------------------------------------------------------- AES（解密网站解析结果，纯标准库）
def _gmul(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return p


def _build_sbox():
    inv = [0] * 256
    for i in range(1, 256):
        r, base, e = 1, i, 254
        while e:
            if e & 1:
                r = _gmul(r, base)
            base = _gmul(base, base)
            e >>= 1
        inv[i] = r

    def rotl(x, n):
        return ((x << n) | (x >> (8 - n))) & 0xFF

    return [inv[i] ^ rotl(inv[i], 1) ^ rotl(inv[i], 2) ^ rotl(inv[i], 3) ^ rotl(inv[i], 4) ^ 0x63
            for i in range(256)]


SBOX = _build_sbox()
INV_SBOX = [0] * 256
for _i, _v in enumerate(SBOX):
    INV_SBOX[_v] = _i
RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36, 0x6C, 0xD8, 0xAB, 0x4D]


class _AES(object):
    def __init__(self, key):
        if len(key) not in (16, 24, 32):
            raise ValueError("bad key")
        self.nk = len(key) // 4
        self.nr = self.nk + 6
        self.rk = self._expand(key)

    def _expand(self, key):
        w = [list(key[i:i + 4]) for i in range(0, len(key), 4)]
        for i in range(self.nk, 4 * (self.nr + 1)):
            t = list(w[i - 1])
            if i % self.nk == 0:
                t = t[1:] + t[:1]
                t = [SBOX[b] for b in t]
                t[0] ^= RCON[i // self.nk - 1]
            elif self.nk > 6 and i % self.nk == 4:
                t = [SBOX[b] for b in t]
            w.append([w[i - self.nk][j] ^ t[j] for j in range(4)])
        return w

    def _add(self, s, rnd):
        for c in range(4):
            for r in range(4):
                s[r][c] ^= self.rk[rnd * 4 + c][r]

    def dec(self, block):
        s = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
        self._add(s, self.nr)
        for rnd in range(self.nr - 1, -1, -1):
            for r in range(1, 4):
                s[r] = s[r][-r:] + s[r][:-r]
            for r in range(4):
                for c in range(4):
                    s[r][c] = INV_SBOX[s[r][c]]
            self._add(s, rnd)
            if rnd != 0:
                for c in range(4):
                    a0, a1, a2, a3 = s[0][c], s[1][c], s[2][c], s[3][c]
                    s[0][c] = _gmul(a0, 14) ^ _gmul(a1, 11) ^ _gmul(a2, 13) ^ _gmul(a3, 9)
                    s[1][c] = _gmul(a0, 9) ^ _gmul(a1, 14) ^ _gmul(a2, 11) ^ _gmul(a3, 13)
                    s[2][c] = _gmul(a0, 13) ^ _gmul(a1, 9) ^ _gmul(a2, 14) ^ _gmul(a3, 11)
                    s[3][c] = _gmul(a0, 11) ^ _gmul(a1, 13) ^ _gmul(a2, 9) ^ _gmul(a3, 14)
        return bytes(s[r][c] for c in range(4) for r in range(4))


def _aes_cbc_dec(data, key, iv):
    aes = _AES(key)
    out, prev = bytearray(), iv
    for i in range(0, len(data), 16):
        blk = data[i:i + 16]
        dec = aes.dec(blk)
        out += bytes(dec[j] ^ prev[j] for j in range(16))
        prev = blk
    n = out[-1]
    return bytes(out[:-n])


def _decrypt_baidu(url):
    """https://baidu.con/<16位key><base64密文> → AES-CBC(key,key) 明文直链"""
    if not url or not url.startswith(DEC_PREFIX):
        return ""
    body = url[len(DEC_PREFIX):]
    if len(body) <= 16:
        return ""
    key = body[:16].encode()
    ct = body[16:]
    try:
        raw = base64.b64decode(ct + "=" * (-len(ct) % 4))
    except Exception:
        return ""
    if not raw or len(raw) % 16:
        return ""
    try:
        text = _aes_cbc_dec(raw, key, key).decode("utf-8", "ignore")
    except Exception:
        return ""
    return text if text.startswith("http") else ""


# ---------------------------------------------------------------- HTTP
def _http(url, timeout=20, headers=None):
    h = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
    if headers:
        h.update(headers)
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers=h)
            r = urllib.request.urlopen(req, timeout=timeout)
            data = r.read()
            return data.decode("utf-8", "ignore")
        except Exception:
            time.sleep(0.3)
    return ""


def _abs(u):
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return HOST + u
    return u


def _clean(s):
    s = re.sub(r"<[^>]+>", "", str(s or ""))
    return s.replace("&nbsp;", " ").replace("&amp;", "&").strip()


def _unescape(s):
    return str(s or "").replace("\\/", "/")


# ---------------------------------------------------------------- 解析工具
_CARD_RE = re.compile(
    r'<div class="vod-item">\s*<a href="(/voddetail/\d+\.html)"[^>]*title="([^"]*)"[^>]*>.*?'
    r'<img[^>]*src="([^"]*)"[^>]*>.*?(?:<span class="remarks">([^<]*)</span>)?.*?'
    r'<h4 class="title">([^<]*)</h4>.*?<p class="subtitle">([^<]*)</p>',
    re.S)


def _parse_cards(html):
    out = []
    for m in _CARD_RE.finditer(html):
        href, title_attr, pic, remarks, title, subtitle = m.groups()
        vid = re.search(r"(\d+)", href)
        if not vid:
            continue
        name = _clean(title or title_attr)
        if not name:
            continue
        rm = _clean(remarks)
        sub = _clean(subtitle)
        if rm:
            vrem = rm
        elif sub:
            vrem = sub
        else:
            vrem = ""
        out.append({
            "vod_id": vid.group(1),
            "vod_name": name,
            "vod_pic": _abs(_clean(pic)),
            "vod_remarks": vrem,
            "subtitle": sub,
        })
    return out


def _parse_player_url(html):
    """从播放页提取 player_aaaa={...} 里的 url / from（站点直链常为 m3u8）。"""
    m = re.search(r"player_aaaa\s*=\s*(\{.*?\})\s*</script>", html, re.S)
    if not m:
        m = re.search(r"player_aaaa\s*=\s*(\{.*?\})", html, re.S)
    if not m:
        return "", ""
    try:
        j = json.loads(m.group(1))
    except Exception:
        return "", ""
    return str(j.get("url") or "").strip(), str(j.get("from") or "").strip()


def _site_parse_url(play_url):
    """用网站自己的解析：请求 /lxart/entry.php 拿到带签名的 jx.lxyy.club 解析地址。
    play_url 形如 /vodplay/{id}-{sid}-{nid}.html 或完整 URL。返回签名解析地址，失败返回 ""。
    """
    m = re.search(r"/vodplay/(\d+)-(\d+)-(\d+)\.html", play_url)
    if not m:
        return ""
    vid, sid, nid = m.groups()
    entry = "%s/lxart/entry.php?id=%s&sid=%s&nid=%s" % (HOST, vid, sid, nid)
    html = _http(entry, timeout=20, headers={"Referer": play_url if play_url.startswith("http") else HOST + "/" + play_url.lstrip("/")})
    if not html:
        return ""
    mb = re.search(r'<script id="lx-binding-data"[^>]*>(.*?)</script>', html, re.S)
    if not mb:
        return ""
    try:
        data = json.loads(mb.group(1))
    except Exception:
        return ""
    target = str(data.get("target") or "").strip()
    # 确认是本站解析域名，避免异常数据
    if SITE_PARSE in target and target.startswith("http"):
        return target.replace("\\u0026", "&").replace("\\/", "/")
    return ""


def site_parse_real(official_url):
    """用网站自己的解析后端把官方平台链接解析成真实可播直链。
    official_url: 官方平台页面链接（youku/qq/bili...）
    返回: (真实直链, 是否需要客户端解析)；成功返回 (url, False)。
    """
    official_url = str(official_url or "").strip()
    if not official_url.startswith("http"):
        return "", True
    try:
        api = SITE_PARSE_API + urllib.parse.quote(official_url, safe="")
        txt = _http(api, timeout=25, headers={"Referer": HOST + "/", "Accept": "application/json"})
        j = json.loads(txt)
    except Exception:
        return "", True
    if not isinstance(j, dict) or int(j.get("code") or 0) != 200:
        return "", True
    enc = str(j.get("url") or "").strip()
    # 直链（有些线路直接返回 m3u8）
    if enc.startswith("http") and not enc.startswith(DEC_PREFIX):
        return enc, False
    # baidu.con 加密串 → AES 解密
    real = _decrypt_baidu(enc)
    if real:
        return real, False
    return "", True


class Spider(BaseSpider):
    def getName(self):
        return "片库4K"

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        pass

    def init(self, extend=""):
        self.host = HOST

    # ---------------------------------------------------------------- 首页
    def homeContent(self, filter):
        classes = [{"type_id": tid, "type_name": name} for tid, name in CATEGORIES]
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        html = _http(HOST + "/")
        lst = _parse_cards(html)
        return {"list": [{k: v for k, v in x.items() if k != "subtitle"} for x in lst]}

    # ---------------------------------------------------------------- 分类
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(str(pg).strip() or 1))
        except Exception:
            page = 1
        url = "%s/vodtype/%s-%d.html" % (HOST, tid, page)
        html = _http(url)
        lst = _parse_cards(html)
        # 尾页
        pagecount = page
        m = re.search(r'href="/vodtype/[^"]*?(\d+)\.html"[^>]*title="尾页"', html)
        if m:
            pagecount = int(m.group(1))
        elif len(lst) < 6 and page > 1:
            pagecount = page
        else:
            pagecount = max(page + 1, page)
        return {
            "page": page,
            "pagecount": pagecount,
            "limit": len(lst) or 18,
            "total": pagecount * len(lst) if lst else 0,
            "list": [{k: v for k, v in x.items() if k != "subtitle"} for x in lst],
        }

    # ---------------------------------------------------------------- 详情
    def detailContent(self, ids):
        vid = str(ids[0] or "").strip()
        if not vid:
            return {"list": []}
        html = _http("%s/voddetail/%s.html" % (HOST, vid))
        if not html:
            return {"list": []}

        # 标题 / 备注
        name, remarks = "", ""
        m = re.search(r'<h1 class="detail-title">(.*?)</h1>', html, re.S)
        if m:
            raw = m.group(1)
            rm = re.search(r'<span class="detail-remarks">(.*?)</span>', raw, re.S)
            if rm:
                remarks = _clean(rm.group(1))
            name = _clean(re.sub(r"<span.*?</span>", "", raw, flags=re.S))

        # 图片
        pic = ""
        m = re.search(r'<img[^>]*src="([^"]*)"[^>]*alt="[^"]*"', html)
        if m:
            pic = _abs(_clean(m.group(1)))

        # 元信息：分类/地区/年份/导演/主演
        def meta(label):
            mm = re.search(label + r"：\s*<a?[^>]*>?\s*([^<\n]+)", html)
            if not mm:
                mm = re.search(label + r"[^：:]*[:：]\s*([^<\n]+)", html)
            return _clean(mm.group(1)) if mm else ""

        type_name = meta("分类")
        area = meta("地区")
        year = meta("年份")
        director = meta("导演")
        actor = meta("主演")

        # 简介
        content = ""
        m = re.search(r'<div class="detail-desc">.*?</h3>\s*(.*?)</div>', html, re.S)
        if m:
            content = _clean(m.group(1))

        # 线路 + 剧集
        # <span class="source-tab-item" data-target="playlist-{sid}">{名称}</span>
        tabs = re.findall(
            r'<span class="source-tab-item"[^>]*data-target="playlist-(\d+)"[^>]*>(.*?)</span>',
            html, re.S)
        froms = []
        urls = []
        for sid, tname in tabs:
            tname = _clean(tname) or ("线路" + sid)
            # <div class="source-pane" id="playlist-{sid}"> ... <a href="/vodplay/{id}-{sid}-{nid}.html" title="..">
            pm = re.search(r'<div class="source-pane" id="playlist-%s">(.*?)</div>\s*</div>' % sid,
                           html, re.S)
            block = pm.group(1) if pm else ""
            eps = re.findall(
                r'<a href="(/vodplay/\d+-%s-\d+\.html)"[^>]*title="([^"]*)"' % sid,
                block)
            if not eps:
                eps = re.findall(
                    r'<a href="(/vodplay/\d+-%s-\d+\.html)"[^>]*>([^<]*)</a>' % sid,
                    block)
            if not eps:
                continue
            items = []
            for href, title in eps:
                label = _clean(title) or "正片"
                items.append("%s$%s" % (label, _abs(href)))
            froms.append(tname)
            urls.append("#".join(items))

        # 兼容：无 source-pane 时，取页面首个播放链接
        if not froms:
            m = re.search(r'href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*class="btn-play"', html)
            if m:
                froms = ["默认"]
                urls = ["正片$" + _abs(m.group(1))]

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "type_name": type_name,
            "vod_year": year,
            "vod_area": area,
            "vod_lang": "",
            "vod_remarks": remarks,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": content,
            "vod_play_from": "$$$".join(froms),
            "vod_play_url": "$$$".join(urls),
        }
        return {"list": [vod]}

    # ---------------------------------------------------------------- 搜索
    def searchContent(self, key, quick, pg="1"):
        try:
            page = max(1, int(str(pg).strip() or 1))
        except Exception:
            page = 1
        url = "%s/vodsearch/-------------.html?wd=%s" % (HOST, urllib.parse.quote(str(key or "")))
        html = _http(url)
        lst = _parse_cards(html)
        return {
            "list": [{k: v for k, v in x.items() if k != "subtitle"} for x in lst],
            "page": page,
        }

    # ---------------------------------------------------------------- 播放
    def playerContent(self, flag, id, vipFlags):
        play_url = str(id or "").strip()
        if not play_url.startswith("http"):
            play_url = _abs(play_url)
        header = '{"User-Agent":"%s"}' % UA

        # 已经是媒体直链
        if re.search(r"\.(m3u8|mp4|m3u|flv|mkv|ts|mov|webm)(?:[?#]|$)", play_url, re.I):
            return {"parse": 0, "playUrl": "", "url": play_url, "header": header}

        official = play_url
        # 站内播放页 → 抓 player_aaaa.url（本站点直链 m3u8，或官方平台链接）
        if "/vodplay/" in play_url:
            html = _http(play_url, timeout=20, headers={"Referer": HOST + "/"})
            official, _from = _parse_player_url(html)
            if not official:
                # 播放页拿不到地址，兜底给网站 LX 解析签名地址
                target = _site_parse_url(play_url)
                if target:
                    return {"parse": 0, "playUrl": "", "url": target, "header": header}
                return {"parse": 0, "playUrl": "", "url": "",
                        "header": "", "msg": "未能获取播放地址，请切换线路"}
            # 站点自带直链（m3u8/mpd/mp4）→ 直接用
            if re.search(r"\.(m3u8|mp4|m3u|flv|mkv|ts|mov|webm|mpd)(?:[?#]|$)", official, re.I):
                return {"parse": 0, "playUrl": "", "url": official, "header": header}

        # 官方平台链接 → 用网站自己的解析后端（4kzj.lyyytv.cn）解出真实直链
        if official.startswith("http"):
            real, need_client = site_parse_real(official)
            if real:
                return {"parse": 0, "playUrl": "", "url": real, "header": header}
            # 解析失败：交给客户端解析器兜底
            return {"parse": 1, "playUrl": "", "url": official, "header": ""}

        return {"parse": 0, "playUrl": "", "url": play_url, "header": header}
