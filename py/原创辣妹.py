# -*- coding: utf-8 -*-
# 作者：蜗牛大叔
import re
import sys
sys.path.append('..')
from base.spider import Spider
import json
import urllib.parse
import urllib.request
import ssl

def _fix_key_uri(ln, playlist_url):
    """KEY 标签的相对 URI 改绝对，绝对的不动。"""
    s = ln.strip()
    if s.startswith("#EXT-X-KEY:"):
        m = re.search(r'URI="([^"]+)"', ln)
        if m and not m.group(1).lower().startswith("http"):
            absu = urllib.parse.urljoin(playlist_url, m.group(1))
            ln = ln.replace('URI="%s"' % m.group(1), 'URI="%s"' % absu)
    return ln



def _strip_ad(text, playlist_url):
    """去掉全部广告块（片头 + 片中），返回可直接播放的 m3u8 文本。

    广告识别（ZakaTV p007 招式：按分片路径统计时长）：
    广告分片和正片分片走不同路径。统计每条分片目录路径的总时长，
    时长占比最大的路径就是正片；其它路径的分片，在广告总时长不足
    全部时长一半时全部删除（防多 CDN 正片被误杀）。
    删完重建 MEDIA-SEQUENCE；DISCONTINUITY 按保留下来的分片块重建
    （两块正片之间只留一个）；KEY/MAP 等标签保留；分片与 KEY 的
    相对 URI 一律改绝对（2026-10-07 站方部分视频改走 t36/t27.cdn2020.com，
    分片为相对路径，不改绝对播放器按代理地址解析会 404）。

    实测样本（2026-10-08）：4 个块 = 9 广告(25.8s) + 2151 正片(6453.2s)
    + 9 广告(25.8s) + 2666 正片(7998.6s)，清理后总时长 14451.8s = 4:00:52。
    """
    text = (text or "").replace("\r", "")
    lines = text.split("\n")
    # 头部：第一个分片/#EXTINF 之前的所有标签行（EXTM3U/VERSION/KEY 等）必须保留
    head_end = len(lines)
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("#EXTINF") or (s and not s.startswith("#")):
            head_end = i
            break
    head = [_fix_key_uri(ln, playlist_url) for ln in lines[:head_end]]
    body = lines[head_end:]

    # 解析出所有分片：extinf 行号 / uri 行号 / 时长 / 绝对地址
    segs = []
    pending = None  # (extinf_idx, dur)
    for idx, ln in enumerate(body):
        s = ln.strip()
        if s.startswith("#EXTINF"):
            try:
                dur = float(s.split(":", 1)[1].split(",", 1)[0])
            except Exception:
                dur = 0.0
            pending = (idx, dur)
        elif pending is not None and s and not s.startswith("#"):
            eidx, dur = pending
            pending = None
            segs.append({"dur": dur,
                         "abs": urllib.parse.urljoin(playlist_url, s),
                         "extinf_idx": eidx, "uri_idx": idx})

    def _path(sg):
        return sg["abs"].rsplit("/", 1)[0]

    drop_idx = set()
    dropped = 0
    if segs:
        stat = {}
        for sg in segs:
            k = _path(sg)
            stat[k] = stat.get(k, 0.0) + sg["dur"]
        total = sum(stat.values())
        main_key = max(stat.items(), key=lambda x: x[1])[0]
        ad_dur = total - stat[main_key]
        if ad_dur > 0 and ad_dur < total * 0.5:
            for sg in segs:
                if _path(sg) != main_key:
                    drop_idx.add(sg["extinf_idx"])
                    drop_idx.add(sg["uri_idx"])
                    dropped += 1
        # 兜底：没触发按路径删时，沿用老逻辑只删片头短广告块
        if not drop_idx:
            cut = None
            for i, ln in enumerate(body):
                if ln.strip() == "#EXT-X-DISCONTINUITY":
                    cut = i
                    break
            if cut is not None:
                first_dur = sum(sg["dur"] for sg in segs if sg["uri_idx"] < cut)
                if 0 < first_dur <= 180:
                    for sg in segs:
                        if sg["uri_idx"] < cut:
                            drop_idx.add(sg["extinf_idx"])
                            drop_idx.add(sg["uri_idx"])
                            dropped += 1

    # 重建 body：跳过被删分片；DISCONTINUITY 按保留块重建；
    # 断点间隙里的 KEY/MAP 等标签缓存，等下一个保留分片时跟在 DISC 后面下发
    orig_disc = sum(1 for ln in body if ln.strip() == "#EXT-X-DISCONTINUITY")
    out = []
    need_disc = False
    emitted_seg = False
    pending_tags = []
    for idx, ln in enumerate(body):
        if idx in drop_idx:
            continue
        s = ln.strip()
        if s == "#EXT-X-DISCONTINUITY":
            need_disc = True
            continue
        if s.startswith("#EXTINF"):
            if need_disc and emitted_seg:
                out.append("#EXT-X-DISCONTINUITY")
            # 断点间隙里缓存的标签跟在 DISC 后面下发，相邻重复的去重
            for t in pending_tags:
                if not out or out[-1] != t:
                    out.append(t)
            pending_tags = []
            need_disc = False
            out.append(ln)
            continue
        if s.startswith("#"):
            ln = _fix_key_uri(ln, playlist_url)
            if need_disc:
                pending_tags.append(ln)
            else:
                out.append(ln)
            continue
        if s:
            # 分片 URI：相对路径一律改绝对，否则播放器按代理地址解析会 404
            out.append(urllib.parse.urljoin(playlist_url, s))
            emitted_seg = True
            continue
        out.append(ln)
    out.extend(pending_tags)

    text = "\n".join(head + out)
    if dropped:
        text = re.sub(r"#EXT-X-MEDIA-SEQUENCE:\d+",
                      "#EXT-X-MEDIA-SEQUENCE:%d" % dropped, text, count=1)
        new_disc = out.count("#EXT-X-DISCONTINUITY")
        if orig_disc > new_disc:
            def _dec_seq(m):
                v = int(m.group(1)) - (orig_disc - new_disc)
                return "#EXT-X-DISCONTINUITY-SEQUENCE:%d" % max(v, 0)
            text = re.sub(r"#EXT-X-DISCONTINUITY-SEQUENCE:(\d+)", _dec_seq,
                          text, count=1)
    return text


class Spider(Spider):
    def init(self, extend=""):
        self.host = 'https://www.yclm01.sbs'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host + '/',
        }

    def getName(self):
        return '原创辣妹'

    def isVideoFormat(self, url):
        if not url:
            return False
        return bool(re.search(r'\.(m3u8|mp4|flv|ts|mkv|avi|mov)(\?|$)', str(url), re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def _get(self, url):
        try:
            r = self.fetch(url, headers=self.headers)
            if r and len(r.text) > 500:
                return r.text
        except Exception:
            pass
        return ''

    CATS = [
        ('20', '视频一区'), ('21', '视频二区'), ('22', '视频三区'), ('23', '视频四区'),
        ('24', '国产精品'), ('25', '国产乱伦'), ('26', '国产传媒'), ('27', '黑料不打烊'),
        ('28', '国产自拍'), ('29', '网红主播'), ('30', '探花系列'), ('31', '三级电影'),
        ('32', '人妻熟女'), ('33', '日本无码'), ('34', '美乳巨乳'), ('35', '强制侵犯'),
        ('36', '制服诱惑'), ('37', '绝色佳人'), ('38', '风俗泡泡浴'), ('39', '家庭乱伦'),
        ('40', 'AV解说'), ('41', '少女萝莉'), ('42', 'SM调教'), ('43', '绝顶潮吹'),
        ('44', '魔镜系列'), ('45', '时间停止'), ('46', '催眠洗脑'), ('47', '电车痴汉'),
        ('48', '淫欲痴女'), ('49', '韩国主播'), ('50', '泰国风情'), ('51', 'OnlyFans'),
        ('52', 'AI换脸'), ('53', '漫改系列'), ('54', '欧美精品'),
    ]

    def homeContent(self, filter=None):
        return {'class': [{'type_id': c[0], 'type_name': c[1]} for c in self.CATS]}

    def _parse_list(self, h):
        vids = []
        seen = set()
        for m in re.finditer(
            r'<article class="media-card">\s*<a class="thumb" href="/index\.php/vod/detail/id/(\d+)\.html">'
            r'<img src="([^"]+)" alt="([^"]*)"[^>]*>(?:<span>([^<]*)</span>)?',
            h
        ):
            vid, pic, title = m.group(1), m.group(2), m.group(3)
            if vid in seen:
                continue
            seen.add(vid)
            vids.append({
                'vod_id': vid,
                'vod_name': title.strip(),
                'vod_pic': pic,
                'vod_remarks': (m.group(4) or '').strip(),
            })
        return vids

    def homeVideoContent(self):
        h = self._get(self.host + '/')
        return {'list': self._parse_list(h)}

    def categoryContent(self, tid, pg, filter=None, extend=None):
        pg = int(pg)
        if pg == 1:
            url = f'{self.host}/index.php/vod/type/id/{tid}.html'
        else:
            url = f'{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html'
        h = self._get(url)
        return {'list': self._parse_list(h), 'page': pg, 'pagecount': 9999, 'limit': 30, 'total': 999999}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) else ids
        h = self._get(f'{self.host}/index.php/vod/detail/id/{vid}.html')
        name = ''
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', h)
        if m:
            name = m.group(1).strip()
        pic = ''
        pm = re.search(r'<a class="thumb" href="[^"]*"><img src="([^"]+)" alt="' + re.escape(name[:12]), h) if name else None
        if pm:
            pic = pm.group(1)

        froms, urls = [], []
        for blk in re.finditer(r'<div class="play-list">(.*?)</div>', h, re.S):
            b = blk.group(1)
            nm = re.search(r'<strong>([^<]+)</strong>', b)
            eps = []
            for m in re.finditer(
                r'href="(/index\.php/vod/play/id/\d+/sid/\d+/nid/(\d+)\.html)"[^>]*>(.*?)</a>',
                b, re.S
            ):
                url, nid, txt = m.group(1), m.group(2), m.group(3)
                ep = re.sub(r'<[^>]+>', '', txt).replace('▶', '').strip() or f'第{nid}集'
                eps.append(f'{ep}${url}')
            if eps:
                froms.append(nm.group(1).strip() if nm else '线路')
                urls.append('#'.join(eps))
        # 兜底：无 play-list 块时直接收集全部播放链接
        if not urls:
            links = sorted(set(re.findall(r'href="(/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"', h)))
            if links:
                froms.append('正片')
                urls.append('正片$' + links[0] if len(links) == 1 else
                            '#'.join(f'第{i+1}集${u}' for i, u in enumerate(links)))
        vod = {
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }
        return {'list': [vod]}

    def searchContent(self, key, quick=False, pg=1):
        pg = int(pg)
        from urllib.parse import quote
        url = f'{self.host}/index.php/vod/search/wd/{quote(key)}.html'
        if pg > 1:
            url = f'{self.host}/index.php/vod/search/wd/{quote(key)}/page/{pg}.html'
        h = self._get(url)
        return {'list': self._parse_list(h), 'page': pg}

    def playerContent(self, flag, id, vipFlags=None):
        url = ''
        play_page = ''
        if id:
            full = id if str(id).startswith('http') else self.host + str(id)
            if re.search(r'\.(m3u8|mp4)(\?|$)', full):
                url = full
            else:
                play_page = full
                h = self._get(full)
                m = re.search(r'<source[^>]+src="([^"]+)"', h, re.I) \
                    or re.search(r'<video[^>]+src="([^"]+)"', h, re.I)
                if m:
                    url = m.group(1)
                if not url:
                    mb = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', h)
                    if mb:
                        url = mb.group(0)
        header = dict(self.headers)
        if play_page:
            header['Referer'] = play_page
        # 去广告：走 localProxy（header 用 json.dumps）
        referer = play_page or self.host
        if url and '.m3u8' in url:
            base = self._proxy_base()
            sep = "&" if "?" in base else "?"
            proxy_url = "%s%stype=ak_adfree&url=%s&referer=%s" % (
                base, sep,
                urllib.parse.quote(url, safe=""),
                urllib.parse.quote(referer, safe=""))
            return {'parse': 0, 'playUrl': '', 'url': proxy_url,
                    'header': json.dumps({"User-Agent": self.headers["User-Agent"], "Referer": referer})}
        return {'parse': 0, 'url': url, 'header': header}

    def _proxy_base(self):
        try:
            if hasattr(self, "getProxyUrl"):
                base = self.getProxyUrl() or ""
                if base:
                    return base
        except Exception:
            pass
        return "http://127.0.0.1:9978/proxy?do=py"

    def localProxy(self, params):
        """下发去广告的 m3u8。"""
        try:
            if not isinstance(params, dict):
                params = {}
            def _first(d, *ks):
                for k in ks:
                    v = d.get(k)
                    if v:
                        return v[0] if isinstance(v, list) else v
                return ""
            action = _first(params, "type", "do", "action")
            if action != "ak_adfree":
                return [404, "text/plain", "not found"]
            m3u8_url = urllib.parse.unquote(_first(params, "url"))
            referer = urllib.parse.unquote(_first(params, "referer")) or self.host
            if not m3u8_url.startswith("http"):
                return [404, "text/plain", "bad url"]
            h = {"User-Agent": self.headers["User-Agent"], "Referer": referer}
            req = urllib.request.Request(m3u8_url, headers=h)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            r = urllib.request.urlopen(req, timeout=15, context=ctx)
            text = r.read().decode("utf-8", "ignore")
            if "#EXT-X-STREAM-INF" in text:
                mm = re.search(r"^(?!#)(.+\.m3u8.*)$", text, re.M)
                if mm:
                    sub = urllib.parse.urljoin(m3u8_url, mm.group(1).strip())
                    req2 = urllib.request.Request(sub, headers=h)
                    r2 = urllib.request.urlopen(req2, timeout=15, context=ctx)
                    text = r2.read().decode("utf-8", "ignore")
                    m3u8_url = sub
            return [200, "application/vnd.apple.mpegurl", _strip_ad(text, m3u8_url)]
        except Exception as e:
            return [500, "text/plain", "proxy error: %s" % e]
