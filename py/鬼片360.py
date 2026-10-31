# -*- coding: utf-8 -*-
"""
=================================================
  修复版：鬼片360（文件名"鬼片刁民"）TVBox 源
=================================================

修复点（相较原版）：
1. 【致命】原版 import requests / from bs4 import BeautifulSoup ——
   TVBox(FongMi T3) 的 Python 环境**没有** requests 和 bs4，
   一 import 整个源直接崩溃，进不了 TVBox。
   ⇒ 全部改用标准库 + TVBox 提供的 self.fetch / self.post。
2. detailContent 里用 BeautifulSoup.select 的少量代码改为正则解析（保留原正则部分不动）。
3. 新增 _to_text() 兼容 self.fetch 返回 str/bytes/Response。
4. 新增 base.spider 兜底（避免无 base.spider 时报错）。
5. homeContent 只返回 class（首页推荐交给 homeVideoContent，符合 TVBox 规范）。

注意：本站在沙箱探测返回 403（数据中心 IP 被拦），无法在此验证页面真实结构。
      选集正则基于通用 VC 模板推断，部署到本机 TVBox 后若选集为空，
      请按实际 /nv/ 详情页 HTML 微调 `class="list"` 与 `/play/` 正则。
"""
import re
import sys
import json
from urllib.parse import quote

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            import urllib.request
            req = urllib.request.Request(url, headers=headers or {})
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    return r.read().decode('utf-8', 'replace')
            except Exception:
                return ''

        def post(self, url, data=None, headers=None, **kw):
            import urllib.request
            if isinstance(data, str):
                body = data.encode('utf-8')
            else:
                body = json.dumps(data or {}).encode('utf-8')
            req = urllib.request.Request(url, data=body, headers=headers or {})
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    return r.read().decode('utf-8', 'replace')
            except Exception:
                return ''


class Spider(Spider):

    host = 'https://www.guipian360.org'

    # header 放类属性：即使 TVBox 未先调 init() 也可用
    header = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": host + "/",
        "Connection": "keep-alive",
    }

    def init(self, extend=""):
        self.extend = extend or ''

    def getName(self):
        return "鬼片360"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        return None

    # ---------- 兼容 fetch 返回 str/bytes/Response ----------
    @staticmethod
    def _to_text(resp):
        if resp is None:
            return ''
        if isinstance(resp, str):
            return resp
        if isinstance(resp, (bytes, bytearray)):
            if resp[:2] == b'\x1f\x8b':
                try:
                    import gzip
                    resp = gzip.decompress(resp)
                except Exception:
                    pass
            try:
                return resp.decode('utf-8', 'replace')
            except Exception:
                return str(resp)
        if hasattr(resp, 'text') and resp.text:
            return resp.text
        if hasattr(resp, 'content'):
            try:
                return resp.content.decode('utf-8', 'replace')
            except Exception:
                return ''
        return ''

    def _get(self, url):
        return self._to_text(self.fetch(url, headers=self.header))

    # ---------- 列表卡片解析 ----------
    def extract_videos(self, html):
        vod_list = []
        seen = set()
        # 【防重复】只解析主列表区 m-movies：
        # 该站页面还带 widget-top-list「热门侧栏」，会重复挂主列表里的影片；
        # 截取 m-movies 区块之后、第一个 widget 区块之前的内容再解析。
        m = re.search(r'class="m-movies[^"]*"', html)
        if m:
            rest = html[m.end():]
            end = re.search(r'class="widget', rest)
            html = rest[:end.start()] if end else rest
        # 用块级匹配，避免跨卡片污染
        blocks = re.findall(r'<[^>]+class="[^"]*u-movie[^"]*"[\s\S]*?</(?:article|div|li)>', html)
        for block in blocks:
            href_m = re.search(r'href="([^"]+)"', block)
            title_m = re.search(r'title="([^"]+)"', block)
            if not title_m:
                title_m = re.search(r'alt="([^"]+)"', block)
            if not title_m:
                title_m = re.search(r'<h2>([^<]+)</h2>', block)
            pic_m = re.search(r'data-original="([^"]+)"', block)
            if not pic_m:
                pic_m = re.search(r'src="([^"]+)"', block)
            remark_m = re.search(r'class="zhuangtai"[^>]*>(?:<span>)?([^<]+)', block)

            if href_m and title_m:
                href = href_m.group(1)
                id_m = re.search(r'/(\d+)\.html', href)
                if not id_m:
                    continue
                vod_id = id_m.group(1)
                if vod_id in seen:
                    continue
                seen.add(vod_id)
                vod_name = title_m.group(1).split('/')[0].strip().replace('《', '').replace('》', '')
                pic = pic_m.group(1) if pic_m else ""
                if pic.startswith('/'):
                    pic = self.host + pic
                elif pic and not pic.startswith(('http://', 'https://')):
                    pic = self.host + '/' + pic
                remarks = remark_m.group(1).strip() if remark_m else ""
                vod_list.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
        return vod_list

    def homeContent(self, filter):
        # 标准 TVBox homeContent 只返回分类；首页推荐由 homeVideoContent 提供
        return {"class": self.classes_config}

    def homeVideoContent(self):
        html = self._get(self.host)
        return {"list": self.extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page_num = int(pg) if str(pg).isdigit() else 1
        # 【防重复】实测该站 /list/{tid}_{n}.html 的所有翻页变体都返回与第 1 页
        # 相同的内容（翻页参数被服务端忽略），且页面无分页导航——
        # 每个分类只有最新 10 部。若放行 pg>1，TVBox 滚动加载第 2 页会得到
        # 完全重复的影片。因此锁定 pagecount=1：第 1 页正常返回，pg>1 返回空。
        if page_num > 1:
            return {"list": [], "page": page_num, "pagecount": 1, "limit": 10, "total": 10}
        url = f"{self.host}/list/{tid}.html"
        html = self._get(url)
        vlist = self.extract_videos(html)
        return {"list": vlist, "page": 1, "pagecount": 1, "limit": len(vlist), "total": len(vlist)}

    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/search.php?searchword={quote(key)}"
        if int(pg or 1) > 1:
            url += f"&page={pg}"
        html = self._get(url)
        return {"list": self.extract_videos(html), "page": pg}

    # ---------- 详情页（去 bs4，改正则） ----------
    def detailContent(self, ids):
        vod_id = ids[0]
        html = self._get(f"{self.host}/nv/{vod_id}.html")

        # 播放源 tabs（原 soup.select('#tv_tab li a')）
        tabs_block = re.search(r'id=["\']tv_tab["\'][^>]*>.*?</ul>', html, re.S)
        tabs = []
        if tabs_block:
            tabs = [re.sub(r'<[^>]+>', '', t).strip()
                    for t in re.findall(r'<a[^>]*>(.*?)</a>', tabs_block.group(0))]
        if not tabs:
            tabs = ["默认播放线路"]

        # 每个源的剧集（原 soup.select('#tv_tab .list') + ul.abc li a）
        lists = re.findall(r'class=["\']list["\'][^>]*>(.*?)</(?:div|ul)>', html, re.S)
        play_urls = []
        for lst in lists:
            sub_urls = []
            for m in re.finditer(r'<a[^>]*href=["\']/play/(.*?)\.html["\'][^>]*>(.*?)</a>', lst, re.S):
                name = re.sub(r'<[^>]+>', '', m.group(2)).strip()
                sub_urls.append(f"{name}${m.group(1)}")
            play_urls.append("#".join(sub_urls))
        if not play_urls:
            play_urls = [""]
        if len(play_urls) < len(tabs):
            play_urls += [""] * (len(tabs) - len(play_urls))

        name_m = re.search(r'<h1>(.*?)</h1>', html)
        vod_name = name_m.group(1).split('/')[0].strip().replace('《', '').replace('》', '') if name_m else "未知影片"

        def get_meta(pattern, default=""):
            m = re.search(pattern, html)
            return m.group(1).strip() if m else default

        pic_m = re.search(r'<img[^>]+data-original="([^"]+)"', html)
        if not pic_m:
            pic_m = re.search(r'<img[^>]+src="([^"]+)"[^>]*class="lazy"', html)
        vod_pic = pic_m.group(1) if pic_m else ""
        if vod_pic.startswith('/'):
            vod_pic = self.host + vod_pic
        elif vod_pic and not vod_pic.startswith(('http://', 'https://')):
            vod_pic = self.host + '/' + vod_pic

        vod_content_m = re.search(r'<p class="jianjie-p"[^>]*>([\s\S]*?)</p>', html)
        vod_content = re.sub(r'<.*?>', '', vod_content_m.group(1)).strip() if vod_content_m else "暂无该影片的相关简介。"

        return {"list": [{
            "vod_id": vod_id, "vod_name": vod_name, "vod_pic": vod_pic, "vod_content": vod_content,
            "vod_director": get_meta(r'<span>导演：</span>(.*?)</li>', "未知"),
            "vod_actor": get_meta(r'<span>主演：</span>(.*?)</li>', "未知"),
            "vod_year": get_meta(r'<strong>(\d{4})年</strong>', "近期"),
            "vod_area": get_meta(r'地区：</span><a[^>]*>(.*?)</a>', "未知"),
            "vod_play_from": "$$$".join(tabs),
            "vod_play_url": "$$$".join(play_urls)
        }]}

    # ---------- 播放解析 ----------
    def playerContent(self, flag, id, vipFlags):
        play_url = f"{self.host}/play/{id}.html"
        html = self._get(play_url)
        if 'var now="' not in html:
            play_url = f"{self.host}/play/{id}-0-0.html"
            html = self._get(play_url)
        m3u8_m = re.search(r'var now="([^"]+)"', html)
        if m3u8_m:
            return {"parse": 0, "url": m3u8_m.group(1), "header": {"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13)", "Referer": self.host + "/"}}
        return {"parse": 1, "url": play_url, "header": {"User-Agent": "Dalvik/2.1.0 (Linux; U: Android 13)", "Referer": self.host + "/"}}

    classes_config = [
        {"type_id": "1", "type_name": "鬼片大全"},
        {"type_id": "6", "type_name": "大陆鬼片"},
        {"type_id": "9", "type_name": "港台鬼片"},
        {"type_id": "8", "type_name": "林正英鬼片"},
        {"type_id": "7", "type_name": "日韩鬼片"},
        {"type_id": "11", "type_name": "欧美鬼片"},
        {"type_id": "10", "type_name": "泰国鬼片"},
        {"type_id": "3", "type_name": "恐怖片"},
        {"type_id": "2", "type_name": "电视剧"}
    ]
