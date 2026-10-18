# -*- coding: utf-8 -*-
# TVBox / 影视仓 Python 爬虫 —— 大师兄影视 (dashifu.dashifu888.com)
# 站点: 苹果CMS V10 + stui default2 模板, 纯 HTML 解析, 无需 pyquery/lxml
# 适配: Python 2.7 / 3.x 双兼容, 只用标准库
"""
【这个站的 8 个坑 —— 全是实测踩出来的, 别再回头试】

1. 桌面 UA 一律 404 —— 站方按 UA 拦。必须用手机 UA,
   否则拿到的就是 nginx 的 404 页面(548 字节), 看起来像站挂了。

2. 反爬垃圾标签 —— 页面里每两个真标签之间塞了一堆
   <style>/<address>/<bdo>/<kbd>/<sup>/<tt>/<var> 之类的空壳,
   class 名还被随机化 (stui-vodlist__thumb 前面挂个随机前缀)。
   所以不能按 class 精确匹配, 只能按「子串 in class」来认。

3. 详情页路径不只一种 —— /post/123.html 和 /peixun/123.html 都出现过,
   同一部片两个地址都能打开(内容一致)。硬编码 /post/ 会大面积 404,
   所以 vod_id 直接存完整链接, 不自己拼。

4. 分集地址不只一种 —— 见过
       /play/4872946-1-1.html          (老格式, id-源-集)
       /play/20261018/qrpmy.html       (新格式, 日期/随机串)
   必须从详情页的 <a href> 里原样扒出来。

5. 播放地址靠 player_aaaa 这个 JS 对象给 ——
   形如 player_aaaa={"flag":"play",...,"url":"https://...index.m3u8",...}
   注意页面里还有不止一个 "url" 字段(link 也叫 url), 且是第一个出现的,
   所以必须把 player_aaaa = {...} 整块抠出来再 json 解析, 不能全局搜 "url"。

6. ★ 分类页 URL 是个大坑 —— 我一开始判断错了, 这里是最新结论(2026-10-18):
   ① 裸地址 /list/1.html 是「类型聚合页」: 顶部 10 条推荐 + 各子类最新 12 条,
      拼出 106 条, 看起来像"全部", 其实没有第 2 页。
   ② 真列表在二级分类: /vodtype/7.html(动作片) /vodtype/8.html(喜剧片)...
      二级分类 ID 就写在类型页的 <h3> 里(/show/N-----------.html), 直接扒。
   ③ 分页是 /vodtype/7-2.html, 每页 36 条正文, 页底有 "2/131" 这样的页码。
      页码 1 也写成 -1.html, 跟页底「首页」链接一致。
   ④ 旧结论「加参数就丢分类」只对 /list/N-1-1.html 成立(那是筛选参数),
      跟 /vodtype/N-P.html 不是一回事。别再把它们混为一谈。
   ⚠ 另外: 每页开头还有 10 张侧栏「猜你喜欢」卡片, 它们的 block 长 6000+
     ~16000 字(垃圾标签撑的), 必须切掉, 否则每页头 10 条永远是同一批推荐,
     翻 131 页看起来都像"没有分页"。

7. ★ 网络层: urllib 抓 /list/N.html 会报 IncompleteRead(0 bytes read),
   同一地址 curl 却正常返回 43764 字节。原因是该站返回 chunked 空包,
   http.client 的分块解码直接抛异常, 把已收到的数据也丢了。
   解决: 自己用 socket 发 HTTP/1.1 并手工解 chunked(见 _raw_http),
   断线时保留半截 —— 反正是 HTML, 少个页脚无所谓。

8. ★ 站内搜索被管理员关了(三重确认):
   /search/-------------.html?wd=x  -> 「系统提示...搜索功能关闭中」
   /search.php?wd=x                -> 静默回落成首页
   /index.php/vod/search.html?wd=x -> HTTP 500
   解决: 抓 6 个主分类下的全部二级分类第 1 页建内存索引(约 700 条),
   15 分钟有效, 本地模糊匹配。
   注意必须串行抓 + sleep, 并发会被 IP 限流, 一半请求返回空包。

广告方面: 本站(v1/v3/v12.ppqrrs.com、adfg8.vip)实测 adjump=0、图片假分片=0,
但代理和过滤逻辑仍然保留 —— 它的源站会换, 哪天接上 fengbao 系就派上用场了。
"""
import os
import re
import sys
import json
import time
import base64
import socket
import urllib.parse
import urllib.request

try:
    import html as _html
except ImportError:  # Python 2
    import HTMLParser as _html_mod
    _html = _html_mod.HTMLParser()


# ======================================================================
# 全局配置
# ======================================================================
HOST = "http://dashifu.dashifu888.com"

# ★ 坑 1: 必须手机 UA。桌面 UA 直接吃 404
UA = ("Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

HEADER = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": HOST + "/",
}

TIMEOUT = 15
RETRY = 3

# ---- 过滤配置 ----
AD_FILTER = True                      # 是否走代理过滤广告
MIN_KEEP_SEC = 600                    # 过滤后剩余时长低于此值就放弃过滤(避免误删成残片)

# 插播广告段特征(小写子串) —— fengbao 系 CDN 会在正片第 5/40 分钟插 /video/adjump/
AD_PAT = ("adjump", "/ad/", "/ads/", "advert", "/gg/", "/guanggao")

# 假分片: 图片伪装成 .ts
IMG_EXT = ("png", "jpg", "jpeg", "gif", "webp", "bmp", "ico", "svg", "avif")


def _clean(s):
    """去标签 + 反转义 + 压空白"""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _doh(host):
    """
    ★ 这个站的播放域名(v3.ppqrrs.com / a.ak-kk.com / v4.cdtlas.com …)
      在不少网络环境下 IPv4 解析不到, 但公共 DNS 是有记录的。
      有 DNS-over-HTTPS 就自己解, 解不到再交给系统。
    ★ 注意: 这里必须用 urllib 直连, 不能回头调 _raw_http ——
      否则 _raw_http -> _doh -> _raw_http 无限递归, 每请求一次就卡 40 秒。
    """
    try:
        u = "https://dns.alidns.com/resolve?name=%s&type=A" % host
        req = urllib.request.Request(u, headers={"User-Agent": "curl/8.5.0"})
        raw = urllib.request.urlopen(req, timeout=5).read().decode("utf-8", "ignore")
        d = json.loads(raw)
        return [a["data"] for a in d.get("Answer", []) if a.get("type") == 1]
    except Exception:
        return []


def _raw_http(url, timeout=TIMEOUT, referer=None, bufsize=65536, maxsize=16 * 1024 * 1024):
    """
    裸 socket 发 HTTP/1.1 —— 为什么不用 urllib?
    ★ 这个站对 /list/N.html 这类裸分类页会返回 chunked 空包:
        python: IncompleteRead(0 bytes read)   —— 一个字节都拿不到
        curl  : 200 / 43764 字节               —— 同一个地址没事
      同一个地址、同样 UA, 唯一区别是 urllib 走 http.client 的分块解码。
      它遇到「发了 Content-Type 和 Set-Cookie 之后直接断流」的响应会抛异常,
      连已经收到的半截都丢掉。裸 socket 自己拼接就没事, 而且能顺便处理
      「chunked 发到一半断线」这种国情常见情况 —— 断在哪算哪。
    返回 str(已解码), 失败返回 ""。
    """
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or ""
    port = parsed.port or (443 if scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    hdr = ["GET %s HTTP/1.1" % path,
           "Host: %s" % host,
           "User-Agent: %s" % UA,
           "Accept: */*",
           "Accept-Language: zh-CN,zh;q=0.9",
           "Referer: %s" % (referer or (scheme + "://" + host + "/")),
           "Connection: close",
           "", ""]
    req = "\r\n".join(hdr).encode("utf-8")

    # --- 建连(带 DoH 兜底) ---
    last = ""
    socks = []
    for ip in ([None] + _doh(host)):
        try:
            if ip:
                s = socket.create_connection((ip, port), timeout=timeout)
            else:
                s = socket.create_connection((host, port), timeout=timeout)
            if scheme == "https":
                import ssl
                ctx = ssl.SSLContext(getattr(ssl, "PROTOCOL_TLS_CLIENT", ssl.PROTOCOL_TLS))
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                s = ctx.wrap_socket(s, server_hostname=host)
            socks.append(s)
            break
        except Exception as e:
            last = "%s@%s %s" % (host, ip or "sys", type(e).__name__)
            continue
    if not socks:
        print("[net] conn fail %s -> %s" % (url, last))
        return ""

    s = socks[0]
    try:
        s.sendall(req)
        buf = []
        total = 0
        while True:
            try:
                c = s.recv(bufsize)
            except socket.timeout:
                break
            except Exception:
                break
            if not c:
                break
            buf.append(c)
            total += len(c)
            if total > maxsize:
                break
        raw = b"".join(buf)
    finally:
        try:
            s.close()
        except Exception:
            pass

    if not raw:
        return ""
    # --- 剥响应头 ---
    i = raw.find(b"\r\n\r\n")
    if i < 0:
        return ""
    head = raw[:i].decode("latin-1", "ignore")
    body = raw[i + 4:]
    low = head.lower()
    # --- 解 chunked ---
    if "transfer-encoding: chunked" in low:
        out = []
        pos = 0
        while True:
            j = body.find(b"\r\n", pos)
            if j < 0:
                break
            try:
                ln = int(body[pos:j].split(b";")[0].strip() or b"0", 16)
            except Exception:
                break
            if ln == 0:
                break
            seg = body[j + 2:j + 2 + ln]
            out.append(seg)
            pos = j + 2 + ln + 2
            if len(seg) < ln:
                break          # 半截, 收下就走
        # ★ 断线的半截也要收: 有些响应最后一块没发完就断开,
        #   不认这半截, 页面尾部(分页、播放列表)就全丢了。
        if out:
            body = b"".join(out)
        elif body:
            body = b""         # 一个 chunk 都没解出来, 说明不是真 chunked, 交给下面按原文用
    # --- 解压 ---
    if "content-encoding: gzip" in low:
        try:
            import gzip
            body = gzip.decompress(body)
        except Exception:
            try:
                import io
                import gzip
                body = gzip.GzipFile(fileobj=io.BytesIO(body)).read()
            except Exception:
                pass
    # --- 解码 ---
    enc = "utf-8"
    m = re.search(r"charset=([\w-]+)", head, re.I)
    if m:
        enc = m.group(1)
    try:
        return body.decode(enc, "ignore")
    except Exception:
        return body.decode("utf-8", "ignore")


def _http(url, referer=None, timeout=TIMEOUT, retry=RETRY):
    """带重试的 GET。优先裸 socket(见 _raw_http 里的原因)。"""
    if not url.startswith("http"):
        return ""
    for i in range(retry):
        txt = _raw_http(url, timeout=timeout, referer=referer)
        if txt:
            return txt
        time.sleep(0.4)
    print("[net] fail %s" % url)
    return ""


def _http_bin(url, referer=None, timeout=TIMEOUT, retry=2):
    """
    取二进制(图片用)。返回 (bytes, content_type)。
    ★ 为什么单独写一个: _raw_http 最后会 decode 成 str,
      jpg 二进制过一遍 utf-8 ignore 就废了, 必须原始字节直接返回。
    """
    import re as _re
    import socket as _socket
    if not url.startswith("http"):
        return b"", ""
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or ""
    port = parsed.port or (443 if scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    for _ in range(retry):
        try:
            s = _socket.create_connection((host, port), timeout=timeout)
            if scheme == "https":
                import ssl as _ssl
                ctx = _ssl.SSLContext(getattr(_ssl, "PROTOCOL_TLS_CLIENT", _ssl.PROTOCOL_TLS))
                ctx.check_hostname = False
                ctx.verify_mode = _ssl.CERT_NONE
                s = ctx.wrap_socket(s, server_hostname=host)
            req = "\r\n".join([
                "GET %s HTTP/1.1" % path,
                "Host: %s" % host,
                "User-Agent: %s" % UA,
                "Accept: image/*,*/*;q=0.8",
                "Referer: %s" % (referer or (scheme + "://" + host + "/")),
                "Connection: close", "", ""])
            s.sendall(req.encode("utf-8"))
            buf = []
            while True:
                try:
                    c = s.recv(65536)
                except Exception:
                    break
                if not c:
                    break
                buf.append(c)
            try:
                s.close()
            except Exception:
                pass
            raw = b"".join(buf)
            i = raw.find(b"\r\n\r\n")
            if i < 0:
                continue
            head = raw[:i].decode("latin-1", "ignore")
            body = raw[i + 4:]
            if "transfer-encoding: chunked" in head.lower():
                out, pos = [], 0
                while True:
                    j = body.find(b"\r\n", pos)
                    if j < 0:
                        break
                    try:
                        ln = int(body[pos:j].split(b";")[0].strip() or b"0", 16)
                    except Exception:
                        break
                    if ln == 0:
                        break
                    seg = body[j + 2:j + 2 + ln]
                    out.append(seg)
                    pos = j + 2 + ln + 2
                    if len(seg) < ln:
                        break
                if out:
                    body = b"".join(out)
            ct = ""
            m = _re.search(r"content-type:\s*([^\r\n]+)", head, _re.I)
            if m:
                ct = m.group(1).strip()
            if body:
                return body, ct
        except Exception:
            time.sleep(0.3)
    return b"", ""


# ======================================================================
# 解析工具
# ======================================================================
# ★ 坑 2: class 被随机化, 只能用「子串」认
#   真实输出形如: class="5PRWU stui-vodlist__thumb lazyload"
# 所以不能用 lxml 的 class 精确选择, 统一用"找 a 标签 + 判断属性里含某子串"
A_TAG = re.compile(r"<a\s([^>]*?)>(.*?)</a>", re.S | re.I)


def _attr(attrs, name):
    """从属性串里取某个属性的值(单双引号都吃)"""
    m = re.search(name + r'\s*=\s*"([^"]*)"', attrs, re.I)
    if not m:
        m = re.search(name + r"\s*=\s*'([^']*)'", attrs, re.I)
    return m.group(1) if m else ""


def _find_blocks(html, cls_kw, span=1400):
    """
    找出所有 class 里含 cls_kw 的 div, 从匹配点向后截 span 字符。
    因为标签的 class 有随机前缀, 只能这么找。
    ★ span 不能太小: 一张卡片的真实内容被垃圾标签撑到 800~1200 字,
      给 2000 会串到下一张卡, 给 600 又会把 h4 名字切掉。1400 实测刚好。
    """
    out = []
    pat = re.compile(r'<div[^>]*class="[^"]*' + re.escape(cls_kw) + r'[^"]*"[^>]*>', re.I)
    for m in pat.finditer(html):
        out.append(html[m.start():m.start() + span])
    return out


# 侧栏/底部的排行榜、热播榜也用了同一套 a 标签, 要排除掉
# 它们挂在 stui-vodlist__text / rank / sidebar 里
_SIDE_KW = ("stui-vodlist__text", "stui-pannel__head", "sidebar",
            "stui-pannel-side", "col-lg-wide-25", "hidden-md hidden-sm")


def _parse_cards(html, strict=True):
    """
    从任意页面(首页/列表页)里抽影片卡片。
    卡片长这样(简化):
      <div class="XX stui-vodlist__box">
        <a class="XX stui-vodlist__thumb lazyload" href=".../post/123.html"
           title="杯雪·一战成名" data-original="/upload/vod/xxx.jpg">
          <span class="XX pic-text text-right">HD国语</span>
        </a>
        <h4 class="XX title text-overflow"><a href="..." title="...">名字</a></h4>
        <p class="XX text text-muted">主演1,主演2</p>
      </div>
    ★ 不能只认 stui-vodlist__box:
      首页(电影区)用的是另一套卡片模板, 里面没有 box, 只有 thumb。
      只按 box 抓, 首页 48 条会掉成 22 条。
    ★ 也不能全页乱抓:
      侧栏「周榜单/总榜单」也用 stui-vodlist__text, 抓进来会污染列表。
    """
    res = []
    seen = set()

    #   前面试过两种切法都踩坑:
    #     ① 从 box 往后截 1400 字 —— 垃圾标签把块撑到 800~1200 字,
    #        截短了丢 h4 名字, 截长了串到下一张卡;
    #     ② 按 <div class="... col-xs-3 ... list"> 切 —— 主内容区根本没这个 class
    #        (只有侧栏那 10 条推荐有), 结果每页只剩 10 条, 页页都一样。
    #     ③ 先按"最后一个 stui-vodlist ul"裁正文 —— 大错。侧栏某张卡后面挂着
    #        16000 字的垃圾标签, 把真正的正文 ul 挤到"最后一个"前面去了。
    #   ★ 末尾那张只截 1200 字: 最后一张卡后面的垃圾标签能拖出 3000 多字。
    #   ★ 侧栏 10 条推荐排在正文前面, 它们的块不是靠"长度"就能分辨的
    #     (实测 673 字 vs 正文 1067 字, 差不多)。可靠的分界是正文的 <ul>:
    #     侧栏推荐没有 stui-vodlist ul 包裹, 正文每张卡都挂在
    #     <ul class="... stui-vodlist clearfix"><li>... 下面。
    #     做法: 找第一个「后面紧跟 li+box」的 stui-vodlist ul, 从它开始算正文。
    starts = [m.start() for m in
              re.finditer(r'<div[^>]*class="[^"]*stui-vodlist__box[^"]*"[^>]*>', html, re.I)]
    body_from = 0
    for mu in re.finditer(r'<ul[^>]*class="[^"]*stui-vodlist[ "_]', html, re.I):
        if re.search(r'<li[^>]*>', html[mu.end():mu.end() + 400], re.I):
            body_from = mu.start()
            break
    if body_from:
        starts = [s for s in starts if s > body_from]

    blocks = []
    if starts:
        for k, s in enumerate(starts):
            e = starts[k + 1] if k + 1 < len(starts) else min(len(html), s + 1200)
            blocks.append(html[s:e])
    if not blocks:
        # 兜底: 有的模板没有 box, 直接用 thumb 的 a 切
        for m in re.finditer(r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*>', html, re.I):
            blocks.append(html[max(0, m.start() - 200):m.start() + 1200])

    for blk in blocks:
        # 第一个带 title 的 thumb 链接就是封面。
        # ★ 盒子开头常塞 100~300 字垃圾标签(里面的 <a> 没有 href),
        #   所以不能逐个 <a> 循环 + break 之前要先判 href 是否为空,
        #   直接在整块里找「带 thumb/lazyload 类的 a 标签」再解属性最稳。
        m = re.search(
            r'<a[^>]*class="[^"]*(?:stui-vodlist__thumb|lazyload)[^"]*"[^>]*>', blk, re.I)
        if not m:
            continue
        attrs = m.group(0)
        ahref = _attr(attrs, "href")
        atitle = _attr(attrs, "title")
        apic = _attr(attrs, "data-original") or _attr(attrs, "src")
        if not ahref:
            continue
        # 备注: thumb 里那个 span, 形如 <span class="X pic-text text-center">HD</span>
        anote = ""
        mm = re.search(r'<span[^>]*pic-text[^>]*>(.*?)</span>', blk, re.S)
        if mm:
            anote = _clean(mm.group(1))
        # 名字兜底: 从 h4.title 里再找一次
        if not atitle:
            m = re.search(r'<h4[^>]*>\s*<a[^>]*title="([^"]*)"', blk, re.I)
            if m:
                atitle = m.group(1)
        atitle = _clean(atitle)
        if not atitle or not re.search(r"/(post|peixun)/\d+\.html", ahref):
            continue
        # ★ 站里有的页会给 www.dashifu888.com 的跳转链, 统一拉回主域
        #   否则 detailContent 去 www 域抓会拿到 404 / 空页
        ahref = re.sub(r"^https?://(?:www\.)?dashifu888\.com", HOST, ahref)
        ahref = ahref.replace("http://www.dashifu.dashifu888.com", HOST)
        if not ahref.startswith(HOST):
            ahref = _abs(ahref)
        # 去重(同一页会重复出现)
        key = atitle
        if key in seen:
            continue
        seen.add(key)
        # 主演 / 备注
        m = re.search(r'<p[^>]*class="[^"]*stui-vodlist__text[^"]*text[^"]*"[^>]*>(.*?)</p>', blk, re.S)
        actor = _clean(m.group(1)) if m else ""
        # 备注形如 "HD国语"、"更新至06集"、"36集全"
        # ★ 列表页模板里 pic-text 放的是片名(不是 "HD国语"), 首页才放备注。
        #   所以: 跟片名一样就丢掉, 只留像备注的短词。
        note = ""
        an = _clean(anote)
        if an and an != atitle and len(an) <= 12 and not re.search(r"[,，、]", an):
            note = an
        res.append({
            "vod_id": "0$" + ahref,     # ★ 用完整链接当 id, 绕开 /post/ 与 /peixun/ 混用
            "vod_name": atitle,
            "vod_pic": _pic(_abs(apic)),
            "vod_remarks": note,
            "vod_content": actor,
        })
    return res


def _pic(u):
    """
    海报走本地代理。★ 见 localProxy 里 ptype=="pic" 的注释:
    本站的图片也做 UA 白名单, 盒子的 OkHttp UA 会吃 404, 海报全空白。
    """
    if not u:
        return ""
    if not AD_FILTER:
        return u
    return "proxy://do=py&type=pic&url=" + urllib.parse.quote(u, safe="")


def _abs(u):
    """补全相对地址"""
    if not u:
        return ""
    if u.startswith("//"):
        return "http:" + u
    if u.startswith("/"):
        return HOST + u
    if not u.startswith("http"):
        return HOST + "/" + u
    return u


def _take_id(vid):
    """从 vod_id 里剥出 http 链(兼容 源$链 / base64 / 纯数字)"""
    if not vid:
        return ""
    vid = str(vid).strip()
    if "$" in vid:
        vid = vid.split("$", 1)[1]
    if vid.startswith("http"):
        return vid
    # base64 兼容
    try:
        pad = vid + "=" * (-len(vid) % 4)
        dec = base64.b64decode(pad).decode("utf-8", "ignore")
        if dec.startswith("http"):
            return dec
    except Exception:
        pass
    # 纯数字 -> 拼 /post/
    if re.match(r"^\d+$", vid):
        return HOST + "/post/%s.html" % vid
    return vid


# ======================================================================
# 详情页解析
# ======================================================================
def _parse_detail(html):
    """返回 dict: name/pic/type/year/area/actor/director/desc/episodes"""
    d = {"name": "", "pic": "", "type": "", "year": "", "area": "",
         "actor": "", "director": "", "desc": "", "episodes": []}

    # --- 名字: <h1> 里常带评分 span, 先剔掉 ---
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if m:
        h1 = re.sub(r"<span[^>]*>.*?</span>", "", m.group(1), flags=re.S)  # 去掉 8.0 这种评分
        d["name"] = _clean(h1)
        if not d["name"]:
            d["name"] = _clean(m.group(1))
    if not d["name"]:
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        if m:
            d["name"] = _clean(m.group(1)).split("-")[0].split("_")[0]

    # --- 封面: 带 stui-content__thumb 的块里的 img ---
    m = re.search(r'class="[^"]*stui-content__thumb[^"]*"(.*?)(?:<ul|</div>\s*</div>)', html, re.S)
    scope = m.group(1) if m else html[:12000]
    mm = re.search(r'<img[^>]*(?:data-original|src)="([^"]+)"', scope, re.I)
    if mm:
        d["pic"] = _abs(mm.group(1))

    # --- 文本信息: 类型/地区/年份/主演/导演/更新 ---
    # 真实结构(简化):
    #   <p class="XX data">
    #     <span>类型：</span>日本 盛会  <span class="split-line"></span>
    #     <span>地区：</span>泰国&nbsp; <span class="split-line"></span>
    #     <span>年份：</span>2026&nbsp; </p>
    #   <p class="XX data"><span>主演：</span>하야시,陆锦顾,...</p>
    #   <p class="XX data"><span>导演：</span>玛利亚·迪亚兹</p>
    # ★ 按 <p> 分块解析比去标签再切行靠谱得多:
    #   去标签后「类型：」和「日本 盛会」会掉到两行,
    #   而一个 <p> 里塞了三个字段, 必须按 split-line 再切。
    for pm in re.finditer(r"<p[^>]*>(.*?)</p>", html, re.S):
        inner = pm.group(1)
        if "：" not in inner and ":" not in inner:
            continue
        # 每个 <span>标签：</span> 后面跟一段值, 用 split-line 或下一个 span 断开
        # 先按 split-line 切成若干段
        parts = re.split(r'<span[^>]*split-line[^>]*>\s*</span>', inner)
        if len(parts) == 1:
            parts = [inner]
        for part in parts:
            txt = _clean(part)
            if not txt:
                continue
            m = re.match(r"^\s*(类型|地区|年份|主演|导演|更新|语言|备注)\s*[:：]\s*(.*)$", txt)
            if not m:
                continue
            k, v = m.group(1), _clean(m.group(2))
            if k == "类型":
                d["type"] = v
            elif k == "地区":
                d["area"] = v
            elif k == "年份":
                d["year"] = v
            elif k == "主演":
                d["actor"] = v
            elif k == "导演":
                d["director"] = v

    # 兜底: 上面没抓到主演, 用 <p> 之外的整页文本再来一次
    if not d["actor"]:
        plain = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
        plain = re.sub(r"<[^>]+>", "\n", plain)
        plain = _html.unescape(plain)
        lines = [x.strip() for x in plain.split("\n") if x.strip()]
        for i, ln in enumerate(lines):
            if ln.rstrip(":：") == "主演":
                for j in range(i + 1, min(i + 4, len(lines))):
                    if lines[j] and not lines[j].endswith("："):
                        d["actor"] = lines[j]
                        break
                break

    # --- 简介 ---
    m = re.search(r'class="[^"]*detail-content[^"]*"[^>]*>(.*?)</p>', html, re.S)
    if m:
        d["desc"] = _clean(m.group(1))

    # --- 分集: 所有指向 /play/ 的 a ---
    # ★ 坑 4: 两种格式都要, 原样保存 href
    #   /play/4872946-1-1.html      (id-源-集)
    #   /play/20261018/qrpmy.html   (日期/随机串)
    # ★ 页里也混着 www.dashifu888.com 的跳转链, 统一拉回主域, 否则进播放页会 404
    eps = []
    for m in A_TAG.finditer(html):
        href = _attr(m.group(1), "href")
        if "/play/" not in href:
            continue
        txt = _clean(m.group(2)) or "正片"
        full = _abs(href)
        full = re.sub(r"^https?://(?:www\.)?dashifu888\.com", HOST, full)
        if not full.startswith(HOST):
            continue          # 外站播放页一律不要(去了也是死链)
        if not any(e[1] == full for e in eps):
            eps.append((txt, full))
    d["episodes"] = eps
    return d


# ======================================================================
# m3u8 广告过滤
# ======================================================================
def _seg_ext(u):
    """取分片扩展名(去掉 query)"""
    u = (u or "").split("?")[0].split("#")[0].lower()
    if "." not in u:
        return ""
    return u.rsplit(".", 1)[1]


def _is_ad_seg(u):
    lu = (u or "").lower()
    for w in AD_PAT:
        if w in lu:
            return True
    return False


def _is_img_seg(u):
    return _seg_ext(u) in IMG_EXT


def _filter_m3u8(text, base_url):
    """
    过滤 m3u8:
      - 删 /video/adjump/ 这类插播广告段
      - 删 png/webp 伪装的假分片
      - 顺手清掉因删除产生的孤立 #EXT-X-DISCONTINUITY
    保底: 剩余时长 < MIN_KEEP_SEC 就原样返回, 免得删成残片。
    """
    lines = text.split("\n")
    out = []
    pending = []
    keep_sec = 0.0
    total_sec = 0.0
    drop = 0
    just_dropped = False

    for ln in lines:
        t = ln.strip()
        if not t:
            continue
        if t.startswith("#EXT-X-ENDLIST"):
            out.extend(pending)
            pending = []
            out.append(ln)
            continue
        if t.startswith("#EXTINF"):
            # 记时长
            m = re.match(r"#EXTINF:\s*([\d.]+)", t)
            if m:
                total_sec += float(m.group(1))
            pending.append((ln, m.group(1) if m else 0))
            continue
        if t.startswith("#"):
            # 非 EXTINF 的标签: 直接进 pending 之前先挂上
            if not pending:
                # 没有 pending 说明是文件头/全局标签
                if just_dropped and t.startswith("#EXT-X-DISCONTINUITY"):
                    just_dropped = False
                    continue
                just_dropped = False
                out.append(ln)
            else:
                pending.append((ln, None))
            continue
        # 到这就是分片地址
        url = t
        bad = _is_ad_seg(url) or _is_img_seg(url)
        if bad:
            drop += 1
            just_dropped = True
            pending = []
            continue
        # 好分片: 先把 pending 刷出去
        sec = 0.0
        for item, dur in pending:
            out.append(item)
            if dur:
                sec = float(dur)
        pending = []
        keep_sec += sec
        out.append(url)
        just_dropped = False

    if pending:
        out.extend([x[0] if isinstance(x, tuple) else x for x in pending])

    if not out or "#EXTM3U" not in "\n".join(out[:3]):
        return text
    if keep_sec < MIN_KEEP_SEC:
        print("[ad] keep_sec=%.0f < %d, 放弃过滤" % (keep_sec, MIN_KEEP_SEC))
        return text
    if drop == 0:
        return text
    print("[ad] 剪掉 %d 段, 保留 %.0fs / 原 %.0fs" % (drop, keep_sec, total_sec))
    return "\n".join(out)


def _master_sub(text, base_url):
    """master 清单 -> 找第一条子清单地址"""
    if "#EXT-X-STREAM-INF" not in text:
        return ""
    for line in text.split("\n"):
        t = line.strip()
        if t and not t.startswith("#"):
            return urllib.parse.urljoin(base_url, t)
    return ""


def _fix_rel(text, base_url):
    """相对路径分片补全"""
    out = []
    for line in text.split("\n"):
        t = line.strip()
        if not t or t.startswith("#"):
            out.append(line)
            continue
        if t.startswith("http://") or t.startswith("https://"):
            out.append(line)
            continue
        out.append(urllib.parse.urljoin(base_url, t))
    return "\n".join(out)


# ======================================================================
# Spider 类
# ======================================================================
class Spider(object):
    # ---- 首页板块 ----
    CATS = [
        ("电影", "/list/1.html"),
        ("电视剧", "/list/2.html"),
        ("综艺", "/list/3.html"),
        ("动漫", "/list/4.html"),
        ("伦理片", "/list/30.html"),
        ("日韩", "/list/36.html"),
    ]

    def __init__(self):
        self.cache = {}

    # ---------- 基础 ----------
    def getName(self):
        return "大师兄影视"

    def isVideoFormat(self, url):
        u = (url or "").lower()
        for ext in (".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".mpd"):
            if ext in u:
                return True
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        self.cache = {}

    def getDependence(self):
        return []

    def init(self, extend=""):
        return True

    # ---------- 首页 ----------
    def _class_videos(self):
        out = []
        for name, path in self.CATS:
            out.append({"type_id": path, "type_name": name})
        return out
    def homeContent(self, filter=False):
        return {"class": self._class_videos(), "filters": self._filters()}

    def homeVideoContent(self):
        html = _http(HOST + "/")
        vids = _parse_cards(html)
        return {"list": vids}

    def _filters(self):
        # 本站分类页本身不支持筛选参数, 只给年份/地区做「排序线」意义不大,
        # 保持空 filters, 避免 TVBox 显示无效筛选项。
        return {}

    # ---------- 分类 ----------
    # ★★ 这个站的分类结构跟标准苹果CMS 不一样, 四组实测(2026-10):
    #
    #   ① 裸地址 /list/N.html 是个「类型聚合页」, 不是列表页:
    #        电影 /list/1.html -> 106 张卡 = 顶部 10 条推荐 + 8 个子类各 12 条
    #        这些是「子类最新 12 部」拼起来的, 不重复, 但没有第 2 页。
    #
    #   ② /vodtype/N.html 跟 /list/N.html 内容一模一样。真正的列表在二级分类:
    #        /vodtype/7.html  动作片   /vodtype/8.html  喜剧片 ...
    #      二级分类的 ID 从类型页的 <h3> 里直接扒(SUB_MAP)。
    #
    #   ③ 只有三种写法:
    #        /vodtype/7.html        第 1 页
    #        /vodtype/7-2.html      第 2 页   ← 参数是页码, 真的生效
    #        /vodtype/7-2-2.html    混页(不按分类, 别用)
    #      实测 /vodtype/7-2.html 与 7-3.html 首条不同, 每页 12 条;
    #      页数封顶(7-50 之后开始回落), 靠"本页 0 条"来判断到底。
    #
    #   ④ 老版本曾断言"分类页加参数会丢分类", 那只对 /list/N-1-1.html 成立。
    #      /vodtype/N-P.html 是正确的分页写法, 之前漏了这条路, 导致全站只有 106 部。
    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = int(pg or 1)
        tid = (tid or "1").strip()
        m = re.search(r"/?(\d+)", tid)
        cid = m.group(1) if m else "1"

        subs = self._sub_ids(cid)
        if not subs:
            # 没有二级分类的栏目(伦理片/日韩): 直接读类型页, 只有一页
            subs = [cid]

        per = len(subs)
        single = (len(subs) == 1 and subs[0] == cid)      # 30/36 这类没有子分类
        # 全局页码 -> (第几个子类, 子类内第几页)
        # ★ 越界要"钳住"而不是取模回绕: 取模会让第 65 页又变回第 1 页,
        #   翻到后面全是重复的老内容, 看起来像分页坏了。
        #   钳住之后超出的页自然返回空列表, TVBox 会停在这一页。
        idx = (page - 1) // per
        sub_pg = (page - 1) % per + 1
        if single:
            idx, sub_pg = 0, page
        if page < 1:
            return {"list": [], "page": page, "pagecount": 1, "limit": 0, "total": 0}
        sid = subs[idx]

        # ★ 页码 1 也写成 /vodtype/30-1.html: 页底「首页」就是这形式,
        #   裸地址在部分栏目会被站方当"无参数"回落成同一页。
        url = HOST + "/vodtype/%s-%d.html" % (sid, sub_pg)
        html = _http(url)
        vids = _parse_cards(html)
        if not vids and sub_pg == 1:
            # 少数栏目不吃 -1.html, 退回裸地址
            html = _http(HOST + "/vodtype/%s.html" % sid)
            vids = _parse_cards(html)

        # 页数: 页面底部有 "3/131" 这种当前页/总页数, 直接读, 不必靠猜
        pagecount = 999
        m = re.search(r'(\d+)\s*/\s*(\d+)\s*</span>', html)
        if m and m.group(2).isdigit():
            pagecount = max(1, int(m.group(2)))
        if not vids:
            pagecount = max(page, 1)
        return {"list": vids, "page": page, "pagecount": pagecount,
                "limit": len(vids), "total": 0}

    # ---------- 详情 ----------
    def detailContent(self, array):
        if not array:
            return {"list": []}
        vid = array[0] if isinstance(array, (list, tuple)) else array
        url = _take_id(vid)
        html = _http(url, referer=HOST + "/")
        if not html:
            return {"list": []}
        d = _parse_detail(html)

        # 集数分隔符
        names, urls = [], []
        for i, (txt, ep) in enumerate(d["episodes"]):
            names.append(txt or ("第%d集" % (i + 1)))
            urls.append(ep)
        if not urls:
            # 没分集(单片电影) —— 退回播放页本身
            names = ["正片"]
            urls = [url]

        vod = {
            "vod_id": "0$" + url,
            "vod_name": d["name"],
            "vod_pic": _pic(d["pic"]),
            "vod_year": d["year"],
            "vod_area": d["area"],
            "vod_remarks": "",
            "vod_actor": d["actor"],
            "vod_director": d["director"],
            "vod_content": d["desc"],
            "vod_play_from": "大师兄",
            "vod_play_url": "#".join(
                ["%s$%s" % (n, u) for n, u in zip(names, urls)]
            ),
        }
        return {"list": [vod]}

    # ---------- 播放 ----------
    def playerContent(self, flag, did, vip_flags=None):
        url = _take_id(did)
        if not url:
            return {"parse": 0, "playUrl": "", "url": "", "header": HEADER}

        # 详情页直接给的就是 /play/xxx.html, 这里要再进去抠 player_aaaa
        if "/play/" not in url:
            # 可能是详情页, 先找第一集
            html = _http(url)
            d = _parse_detail(html)
            if d["episodes"]:
                url = d["episodes"][0][1]

        html = _http(url, referer=HOST + "/")
        real = ""
        m = re.search(r"player_aaaa\s*=\s*(\{.*?\})\s*</script>", html, re.S)
        if m:
            try:
                obj = json.loads(m.group(1))
                real = obj.get("url", "") or ""
                real = real.replace("\\/", "/")
            except Exception as e:
                print("[player] json err %s" % e)
        if not real:
            # 兜底: 全局找 m3u8
            mm = re.search(r'(https?:\\?/\\?/[^"\'<>\s]+?\.m3u8[^"\'<>\s]*)', html)
            if mm:
                real = mm.group(1).replace("\\/", "/")
        if not real:
            print("[player] 没找到播放地址: %s" % url)
            return {"parse": 0, "playUrl": "", "url": "", "header": HEADER}

        header = dict(HEADER)
        header["Referer"] = HOST + "/"

        # 走代理过滤广告
        if AD_FILTER and ".m3u8" in real.lower():
            px = "proxy://do=py&type=m3u8&url=" + urllib.parse.quote(real, safe="")
            return {"parse": 0, "playUrl": "", "url": px, "header": header}

        return {"parse": 0, "playUrl": "", "url": real, "header": header}


    # ---------- 搜索 ----------
    # ★ 本站搜索被管理员关了, 三重确认:
    #   ① /search/-------------.html?wd=xxx  -> 「系统提示...搜索功能关闭中」
    #   ② /search.php?wd=xxx                -> 静默回落成首页(抓回来是 48 条首页片)
    #   ③ /index.php/vod/search.html?wd=xxx -> HTTP 500
    #   所以只能: 抓各分类列表 -> 建内存索引 -> 本地模糊匹配。
    #
    # ★ 索引规模 = 6 个分类各一页, 去重后 300 条上下。
    #   必须串行 + 0.3 秒间隔: 实测 6 个并发时源站按 IP 限流, 一半请求返回空包,
    #   索引只剩 46 条, 搜什么都搜不到。串行建一次 30~40 秒, 之后 15 分钟内毫秒级。
    _IDX = {"t": 0, "v": []}
    IDX_TTL = 900

    def _cats_with_id(self):
        out = []
        for name, path in self.CATS:
            mm = re.search(r"/list/(\d+)", path)
            if mm:
                out.append((name, path, mm.group(1)))
        return out

    def _sub_cats(self, html):
        """
        从类型页里抠二级分类: [("最新动作片","7"), ...]
        抓出来只用于调试核对, 正式逻辑走 SUB_MAP(不依赖页面结构)。
        """
        out = []
        seen = set()
        for m in re.finditer(r'<h3[^>]*>(.*?)</h3>', html, re.S):
            mm = re.search(r'href="[^"]*/show/(\d+)-+\.html"[^>]*>(.*?)</a>', m.group(1), re.S)
            if not mm:
                continue
            sid = mm.group(1)
            name = _clean(mm.group(2))
            if not name or sid in seen or len(name) > 8:
                continue
            seen.add(sid)
            out.append((name, sid))
        return out

    # ★ 主栏目 -> 二级分类。从各类型页 <h3> 里扒出来的现成 show 链接, 实测有效。
    #   电视剧比别处多两个: 15 港剧 / 31 泰剧(首页导航里没露出, 但链接确实通)。
    #   30(伦理片)/36(日韩) 没有二级分类, 它的类型页本身就 46 条, 没有更深的层。
    SUB_MAP = {
        "1": ["7", "8", "9", "10", "11", "12", "29", "13"],
        "2": ["14", "15", "31"],
        "3": ["21", "22", "23", "24"],
        "4": ["25", "26", "27", "28"],
    }

    def _sub_ids(self, cid):
        return list(self.SUB_MAP.get(str(cid), []))

    def _fetch_cat(self, cid):
        """
        抓一个主分类。走二级分类的第 1 页(每类 36 条正文), 不再用裸地址 ——
        裸地址的正文只有 36 条, 但那是聚合页; 二级分类能顺着页码继续往下翻,
        搜索索引里也就装得下更多片子。
        ★ 没有二级分类的栏目(30/36)退回自己的 -1.html。
        """
        subs = self._sub_ids(cid) or [cid]
        out = []
        seen = set()
        for sid in subs:
            html = _http(HOST + "/vodtype/%s-1.html" % sid, timeout=15)
            if not html:
                continue
            for v in _parse_cards(html):
                k = v["vod_name"]
                if k in seen:
                    continue
                seen.add(k)
                out.append(v)
            time.sleep(0.3)      # ★ 串行限速, 并发会被站方按 IP 限流
        return out

    def _build_index(self):
        now = time.time()
        if self._IDX["v"] and now - self._IDX["t"] < self.IDX_TTL:
            return self._IDX["v"]
        pool = []
        seen = set()
        for name, path, cid in self._cats_with_id():
            for v in self._fetch_cat(cid):
                k = v["vod_name"]
                if k in seen:
                    continue
                seen.add(k)
                pool.append(v)
            time.sleep(0.3)
        self._IDX = {"t": now, "v": pool}
        print("[idx] 建索引 %d 条" % len(pool))
        return pool

    def searchContent(self, key, quick=False, pg="1"):
        key = (key or "").strip()
        page = int(pg or 1)
        if not key:
            return {"list": [], "page": page, "total": 0}

        # 先试站内搜索(万一站方哪天又开了)
        html = _http(HOST + "/search/-------------.html?wd=" + urllib.parse.quote(key), timeout=10)
        if html and "搜索功能关闭" not in html:
            vids = _parse_cards(html)
            if vids:
                return {"list": vids, "page": page, "total": len(vids)}

        pool = self._build_index()
        kl = key.lower().replace(" ", "")
        hit = [v for v in pool if kl in v["vod_name"].lower().replace(" ", "")]
        if not hit:
            # 字面交集兜底: 「庆余年2」也能搜到「庆余年」
            kc = set(kl)
            scored = []
            for v in pool:
                name = v["vod_name"].lower()
                n = sum(1 for c in kc if c in name)
                if n >= max(2, len(kc) - 1):
                    scored.append((n, v))
            scored.sort(key=lambda x: -x[0])
            hit = [v for _, v in scored]

        per = 30
        start = (page - 1) * per
        return {"list": hit[start:start + per], "page": page, "total": len(hit)}

    # ---------- 代理 ----------
    def localProxy(self, param):
        """
        TVBox 传进来的 param 是 dict(新壳) 或 "do=py&type=m3u8&url=..."(老壳)。
        返回 (status, content_type, body)  —— 新壳还会多给一个 header dict。
        """
        if isinstance(param, str):
            data = urllib.parse.parse_qs(param)
            data = dict((k, v[0] if isinstance(v, list) and v else v) for k, v in data.items())
        else:
            data = param or {}

        ptype = data.get("type", "")
        raw = data.get("url", "")
        if isinstance(raw, list):
            raw = raw[0] if raw else ""
        raw = urllib.parse.unquote(raw)
        if not raw:
            return 400, "text/plain", "no url"

        # ★ 海报走代理。原因: 本站在 UA 里不含 "Mobile" 时, 连 /upload/ 下的图片
        #   都直接 404(实测 okhttp/3.12.0、Dalvik、python-requests 全是 404/146字节)。
        #   TVBox 加载海报用的是它自己的 OkHttp UA, 我们改不了 ——
        #   所以把 vod_pic 换成 proxy://, 由我们带手机 UA 去取, 再原样吐给盒子。
        if ptype in ("pic", "img", "image"):
            body, ct = _http_bin(raw, referer=HOST + "/")
            if not body:
                return 404, "text/plain", "pic fail"
            if not ct.startswith("image"):
                ct = "image/jpeg"
            return 200, ct, body

        if ptype != "m3u8":
            return 404, "text/plain", "not support"

        txt = _http(raw, referer=HOST + "/", timeout=20)
        if not txt or not txt.lstrip().startswith("#EXTM3U"):
            return 502, "text/plain", "upstream fail"

        # master 清单 -> 追一层子清单
        sub = _master_sub(txt, raw)
        if sub:
            txt2 = _http(sub, referer=HOST + "/", timeout=20)
            if txt2 and txt2.lstrip().startswith("#EXTM3U"):
                txt, raw = txt2, sub

        # 相对路径补全
        txt = _fix_rel(txt, raw)

        # 广告过滤
        if AD_FILTER:
            txt = _filter_m3u8(txt, raw)

        return 200, "application/vnd.apple.mpegurl", txt


# ======================================================================
# 13 个模块级接口 —— TVBox 只认这些, 类里的方法它看不见
# ★ 必须写。不写 = 整站空白(本地 python3 xxx.py 全绿也没用)
# ★ class Spider(Spider) 同名继承陷阱: 不能 Spider = Spider(),
#   要先存类引用 _M = Spider, 再延迟实例化。
# ======================================================================
_M = Spider
_sp = None


def _ins():
    global _sp
    if _sp is None:
        _sp = _M()
    return _sp


def init(extend=""):
    return _ins().init(extend)


def getName():
    return _ins().getName()


def homeContent(filter=False):
    return _ins().homeContent(filter)


def homeVideoContent():
    return _ins().homeVideoContent()


def categoryContent(tid, pg, filter=False, extend=None):
    return _ins().categoryContent(tid, pg, filter, extend)


def detailContent(array):
    return _ins().detailContent(array)


def playerContent(flag, did, vip_flags=None):
    return _ins().playerContent(flag, did, vip_flags)


def searchContent(key, quick=False, pg="1"):
    return _ins().searchContent(key, quick, pg)


def isVideoFormat(url):
    return _ins().isVideoFormat(url)


def manualVideoCheck():
    return _ins().manualVideoCheck()


def destroy():
    return _ins().destroy()


def localProxy(param):
    return _ins().localProxy(param)


def getDependence():
    return _ins().getDependence()


# ======================================================================
# 自检 —— python3 大师兄影视.py
# ======================================================================
if __name__ == "__main__":
    print("=== 1. 模块级接口 ===")
    NEED = ["init", "getName", "homeContent", "homeVideoContent",
            "categoryContent", "detailContent", "playerContent",
            "searchContent", "isVideoFormat", "manualVideoCheck",
            "destroy", "localProxy", "getDependence"]
    miss = [n for n in NEED if n not in globals()]
    print("    %d/13 齐" % (13 - len(miss)), ("缺: " + ",".join(miss)) if miss else "全齐")
    print("    注意: class 里的方法 TVBox 看不见, 必须靠上面这些模块级函数转发")

    print("=== 2. 首页 ===")
    hc = homeContent()
    print("    分类:", [c["type_name"] for c in hc.get("class", [])])
    hv = homeVideoContent().get("list", [])
    print("    首页条数:", len(hv))
    for v in hv[:3]:
        print("      -", v["vod_name"], "|", v["vod_remarks"], "|", v["vod_id"][:64])

    print("=== 3. 分类(走二级分类, 每页 36 条, 可翻页) ===")
    for tid in ["1", "2"]:
        c = categoryContent(tid, "1")
        lst = c.get("list", [])
        print("    栏目%s 第1页: %d 条, 首条=%s, 总页数=%s"
              % (tid, len(lst), lst[0]["vod_name"] if lst else "-", c.get("pagecount")))
    c2 = categoryContent("2", "2")
    l2 = c2.get("list", [])
    print("    栏目2 第2页: %d 条, 首条=%s" % (len(l2), l2[0]["vod_name"] if l2 else "-"))
    c3 = categoryContent("1", "3")
    l3 = c3.get("list", [])
    print("    栏目1 第3页: %d 条, 首条=%s" % (len(l3), l3[0]["vod_name"] if l3 else "-"))

    print("=== 4. 详情 ===")
    # 找一部有分集的剧来演示
    tv = categoryContent("2", "1").get("list", [])
    probe = tv[0] if tv else (hv[0] if hv else None)
    if probe:
        dd = detailContent([probe["vod_id"]]).get("list", [])
        if dd:
            d = dd[0]
            eps = d["vod_play_url"].split("#")
            print("    名字:", d["vod_name"], "| 年份:", d["vod_year"], "| 地区:", d["vod_area"])
            print("    主演:", d["vod_actor"][:60])
            print("    简介:", (d["vod_content"] or "")[:60])
            print("    分集:", len(eps), "| 首个:", eps[0][:96])

    print("=== 5. 搜索(本地索引, 首次要建) ===")
    t0 = time.time()
    idx = _ins()._build_index()
    print("    索引 %d 条, 耗时 %.1fs" % (len(idx), time.time() - t0))
    if idx:
        sample = idx[0]["vod_name"][:3]
        t0 = time.time()
        r = searchContent(sample).get("list", [])
        print("    拿索引首条的前 3 字「%s」搜: %d 条  (%.2fs)" % (sample, len(r), time.time() - t0))
        for v in r[:5]:
            print("      -", v["vod_name"])

    print("=== 6. 海报(必须走代理, 否则盒子全空白) ===")
    pic_ok = pic_bad = 0
    for v in (hv[:5] if hv else []):
        u = v.get("vod_pic") or ""
        if not u.startswith("proxy://"):
            pic_bad += 1
            print("    ! 未包代理:", v["vod_name"], u[:60])
            continue
        r = localProxy({"type": "pic", "url": u.split("url=", 1)[1]})
        if r[0] == 200 and isinstance(r[2], bytes) and r[2][:2] == b"\xff\xd8":
            pic_ok += 1
        else:
            pic_bad += 1
            print("    ! 取图失败:", v["vod_name"], "status=%s" % r[0])
    print("    抽测 5 张: 成功 %d, 失败 %d" % (pic_ok, pic_bad))

    print("=== 7. 播放 + 代理 ===")
    if probe:
        dd = detailContent([probe["vod_id"]]).get("list", [])
        if dd:
            first = dd[0]["vod_play_url"].split("#")[0]
            did = first.split("$", 1)[1] if "$" in first else first
            p = playerContent("", did)
            u = p.get("url", "")
            print("    playerContent ->", u[:110])
            if u.startswith("proxy://"):
                param = u.split("url=", 1)[1]
                r = localProxy({"type": "m3u8", "url": param})
                st, ct, body = r[0], r[1], r[2]
                print("    代理 status=%s ct=%s len=%d" % (st, ct, len(body)))
                if isinstance(body, str) and body.startswith("#EXTM3U"):
                    lines = [x for x in body.split("\n") if x and not x.startswith("#")]
                    ad = [x for x in lines if "adjump" in x.lower()]
                    img = [x for x in lines if re.search(r"\.(png|jpg|webp|gif)$", x.lower().split("?")[0])]
                    print("    分片数:", len(lines), "| adjump:", len(ad), "| 图片假分片:", len(img))
                    print("    首个分片:", lines[0] if lines else "-")
