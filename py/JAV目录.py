# -*- coding: utf-8 -*-
# JAV目录大全 - 原始版本 + 广告过滤 v3.0
# 站点: https://javmenu.com

import re
import sys
import posixpath
import urllib.parse
from pyquery import PyQuery as pq
from base64 import b64decode, b64encode
from requests import Session

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        self.headers['referer'] = f'{self.host}/'
        self.session = Session()
        self.session.headers.update(self.headers)

    def getName(self):
        return "JAV目录大全"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        if hasattr(self, 'session'):
            self.session.close()

    host = "https://javmenu.com"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-full-version': '"133.0.6943.98"',
        'sec-ch-ua-arch': '"x86"',
        'sec-ch-ua-platform': '"Windows"',
        'sec-ch-ua-platform-version': '"19.0.0"',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-full-version-list': '"Not(A:Brand";v="99.0.0.0", "Google Chrome";v="133.0.6943.98", "Chromium";v="133.0.6943.98"',
        'dnt': '1',
        'upgrade-insecure-requests': '1',
        'sec-fetch-site': 'none',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'priority': 'u=0, i'
    }

    # ==================== 广告过滤 ====================

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        """m3u8 本地代理 + 广告分片过滤 (v3.0)"""
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            res = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=15)
            if not res:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(res, "content", b"") or b""
            if not content and hasattr(res, "text") and res.text:
                content = res.text.encode("utf-8", errors="ignore")

            if not content:
                return [502, "text/plain", b"empty content"]

            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]

    def _clean_m3u8(self, text, source_url):
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        parsed = urllib.parse.urlparse(source_url)
        source_dir = posixpath.dirname(parsed.path)
        if not source_dir.endswith("/"):
            source_dir += "/"

        main_dir = source_dir
        for line in lines:
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                uri_match = re.search(r'URI="([^"]+)"', line)
                if uri_match:
                    key_path = uri_match.group(1)
                    if not key_path.startswith("http"):
                        key_dir = posixpath.dirname(key_path)
                        if key_dir and key_dir != "/":
                            main_dir = key_dir + "/"
                            break

        segments = []
        pending = []

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urllib.parse.urljoin(source_url, line)
                media_parsed = urllib.parse.urlparse(media_url)
                is_ad = not media_parsed.path.startswith(main_dir)
                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urllib.parse.urljoin(source_url, line))
            else:
                segments.append(line)

        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urllib.parse.urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)

        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urllib.parse.urljoin(source_url, line)

        return line

    # ==================== 原始业务接口 ====================

    def homeContent(self, filter):
        cateManual = {
            "有码在线": "/zh/censored/online",
            "无码在线": "/zh/uncensored/online",
            "欧美在线": "/zh/western/online",
            "FC2在线": "/zh/fc2/online",
            "成人动画": "/zh/hanime/online",
            "国产在线": "/zh/chinese/online",
            "有码作品": "/zh/censored",
            "无码作品": "/zh/uncensored",
            "欧美作品": "/zh/western",
            "FC2作品": "/zh/fc2"
        }
        classes = [{'type_name': k, 'type_id': v} for k, v in cateManual.items()]
        return {'class': classes}

    def homeVideoContent(self):
        data = self.getpq("/zh")
        return {'list': self.getlist(data(".video-list-item"))}

    def categoryContent(self, tid, pg, filter, extend):
        url = f"{self.host}{tid}" if pg == '1' else f"{self.host}{tid}?page={pg}"
        data = self.getpq(url)
        return {
            'list': self.getlist(data(".video-list-item")),
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999
        }

    def detailContent(self, ids):
        vod_id = ids[0]
        if not vod_id.startswith('http'):
            url = f"{self.host}{vod_id}"
        else:
            url = vod_id
            vod_id = vod_id.replace(self.host, '')
        data = self.getpq(url)
        vod = {
            'vod_id': vod_id,
            'vod_name': data('h1').text() or data('title').text().split(' - ')[0],
            'vod_pic': self.getCover(data),
            'vod_content': data('.card-text').text() or '',
            'vod_director': '',
            'vod_actor': self.getActors(data),
            'vod_area': '日本',
            'vod_year': self.getYear(data('.text-muted').text()),
            'vod_remarks': self.getRemarks(data),
            'vod_play_from': 'JAV在线',
            'vod_play_url': self.getPlaylist(data, url)
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/zh/search?wd={key}&page={pg}"
        data = self.getpq(url)
        return {'list': self.getlist(data(".video-list-item"))}

    def playerContent(self, flag, id, vipFlags):
        try:
            real_url = self.d64(id)
            if real_url:
                return {
                    'parse': 0,
                    'url': self._m3u8_proxy_url(real_url),
                    'header': self.headers
                }
        except Exception as e:
            pass
        return {'parse': 0, 'url': self.d64(id), 'header': self.headers}

    # ==================== 原始私有工具 ====================

    def getlist(self, data):
        vlist = []
        for item in data.items():
            link = item('a').attr('href')
            if not link or '/zh/' not in link:
                continue
            link = link.replace(self.host, '') if link.startswith(self.host) else link
            name = item('.card-title').text() or item('img').attr('alt') or ''
            if not name:
                continue
            vlist.append({
                'vod_id': link,
                'vod_name': name.split(' - ')[0].strip(),
                'vod_pic': self.getListPicture(item),
                'vod_remarks': (item('.text-muted').text() or '').strip(),
                'style': {'ratio': 1.5, 'type': 'rect'}
            })
        return vlist

    def getListPicture(self, item):
        imgs = item('img')
        for img in imgs.items():
            pic = img.attr('data-src') or img.attr('src')
            if pic and not any(keyword in pic for keyword in ['button_logo', 'no_preview', 'loading.gif', 'loading.png']):
                return pic
        return ''

    def getCover(self, data):
        imgs = data('img')
        for img in imgs.items():
            pic = img.attr('data-src') or img.attr('src')
            if pic and not any(keyword in pic for keyword in ['button_logo', 'no_preview', 'loading.gif', 'loading.png', 'website_building']):
                return pic
        return ''

    def getActors(self, data):
        actors = []
        h1_text = data('h1').text()
        if h1_text:
            actors.extend(h1_text.strip().split()[1:])
        actor_links = data('a[href*="/actor/"]')
        for actor_link in actor_links.items():
            actor_text = actor_link.text()
            if actor_text and actor_text not in actors:
                actors.append(actor_text)
        return ','.join(actors) if actors else '未知'

    def getYear(self, date_str):
        m = re.search(r'(\d{4})-\d{2}-\d{2}', date_str or '')
        return m.group(1) if m else ''

    def getRemarks(self, data):
        tags = [tag.text() for tag in data('.badge').items() if tag.text()]
        return ' '.join(set(tags)) if tags else ''

    def getPlaylist(self, data, url):
        play_urls, seen = [], set()

        for src in data('source').items():
            u = src.attr('src')
            if u and u not in seen:
                play_urls.append(f"源{len(play_urls)+1}${self.e64(u)}")
                seen.add(u)

        for u in data('video').items():
            u = u.attr('src')
            if u and u not in seen:
                play_urls.append(f"线路{len(play_urls)+1}${self.e64(u)}")
                seen.add(u)

        for m in re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', data('script').text()):
            if m not in seen:
                play_urls.append(f"线路{len(play_urls)+1}${self.e64(m)}")
                seen.add(m)

        if not play_urls:
            play_urls.append(f"在线播放${self.e64(url)}")

        return '#'.join(play_urls)

    def getpq(self, path=''):
        url = path if path.startswith('http') else f'{self.host}{path}'
        try:
            rsp = self.session.get(url, timeout=20)
            rsp.encoding = 'utf-8'
            return pq(rsp.text)
        except Exception as e:
            print(f"getpq error: {e}")
            return pq('')

    def e64(self, text):
        try:
            return b64encode(text.encode('utf-8')).decode('utf-8')
        except Exception:
            return ''

    def d64(self, encoded_text):
        try:
            return b64decode(encoded_text.encode('utf-8')).decode('utf-8')
        except Exception:
            return ''