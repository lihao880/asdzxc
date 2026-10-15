#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
蓝光影视 TVBox 手机版爬虫源
站点: https://www.zhongyuanxinhua.com/
CMS: 苹果CMS v10 (Ewave 模板)

特性:
1. 基于真实站点结构编写（分类 /vodtype/、详情 /voddetail/、播放 /vodplay/、搜索 /vodsearch/）
2. 纯正则解析，不依赖 lxml（兼容 TVBox 内置 Python 环境）
3. requests 不可用时自动降级 urllib.request
4. 播放地址提取链（m3u8 / mp4 / player_data / iframe / eval / videoSources ...）
5. 全接口 try-except 兜底，任何异常都返回空结构不抛错

接入方式: TVBox / 影视仓 配置接口填入本 py 文件路径或 http 地址即可。
"""

import re
import json
import base64
import html as html_mod
from urllib.parse import quote, unquote, urljoin

try:
    import requests
except Exception:
    requests = None

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""):
            pass

        def homeContent(self, filter=False):
            pass

        def homeVideoContent(self):
            pass

        def categoryContent(self, tid, pg, filter=False, extend=None):
            pass

        def detailContent(self, ids):
            pass

        def playerContent(self, flag, id, vipFlags=None):
            pass

        def searchContent(self, key, quick, pg="1"):
            pass

        def localProxy(self, param):
            pass


# ═══════════════════════════════════════════════════════════════
# CONFIG 区
# ═══════════════════════════════════════════════════════════════
HOST = "https://www.zhongyuanxinhua.com"
SITE_NAME = "蓝光影视"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")

# 默认分类（首页动态解析失败时使用）—— 与站点导航一一对应
DEFAULT_CLASSES = [
    {"type_name": "电影", "type_id": "1"},
    {"type_name": "电视剧", "type_id": "2"},
    {"type_name": "综艺", "type_id": "3"},
    {"type_name": "动漫", "type_id": "4"},
    {"type_name": "短剧", "type_id": "20"},
    {"type_name": "动画片", "type_id": "35"},
    {"type_name": "4K电影", "type_id": "36"},
    {"type_name": "Netflix作品", "type_id": "37"},
]
# 筛选（仅在 homeContent(filter=True) 时下发）
# 说明：本站点筛选走 /vodshow/ 路径，实测有效维度为 地区 / 年份 / 语言 / 排序 / 字母；
#       "类型"维度站点下发的多为通用标签池，多数分类下会返回空列表，故此处不提供。
#       v 值即站点 URL 中对应槽位的原始文本（中文需 URL 编码，由 addressable 层处理）。
DEFAULT_FILTERS = {
    "1": [
        {"key": "地区", "name": "地区", "value": [
            {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
            {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"},
            {"n": "韩国", "v": "韩国"}, {"n": "英国", "v": "英国"}, {"n": "法国", "v": "法国"}]},
        {"key": "年份", "name": "年份", "value": [
            {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"},
            {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"},
            {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}]},
        {"key": "排序", "name": "排序", "value": [
            {"n": "全部", "v": ""}, {"n": "时间", "v": "time"},
            {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]},
        {"key": "语言", "name": "语言", "value": [
            {"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"},
            {"n": "粤语", "v": "粤语"}, {"n": "日语", "v": "日语"}, {"n": "韩语", "v": "韩语"}]},
    ]
}


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════
def fix_url(url, host=HOST):
    """URL 补全"""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    if url.startswith("/"):
        return urljoin(host, url)
    return urljoin(host, "/" + url)


def clean_text(text):
    """去掉 HTML 标签与实体，清洗文本。"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", str(text))
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _scrub(url):
    """清洗 URL 尾部杂质。"""
    if not url:
        return ""
    for ch in ["'", '"', ")", "]", ",", " ", "\\"]:
        if url.endswith(ch):
            url = url[:-1]
    return url.strip()


def _unescape_url(u):
    """把 JSON 转义形式的 URL（https:\\/\\/x\\/y）还原为正常 URL。"""
    if not u:
        return ""
    return u.replace("\\/", "/").replace("\\u0026", "&").replace("\\", "")


def _extract_play(html_text, host=HOST):
    """播放地址提取链"""
    if not html_text:
        return ""
    # 0. player_aaaa —— 本站点真实播放页的权威来源，优先处理并反转义
    m = re.search(r"var\s*player_aaaa\s*=\s*(\{.*?\})\s*</script>", html_text, re.S)
    if not m:
        m = re.search(r"player_aaaa\s*=\s*(\{.*?\})", html_text, re.S)
    if m:
        try:
            d = json.loads(m.group(1))
            u = d.get("url") or d.get("url_next") or ""
            if u:
                return _unescape_url(u)
        except Exception:
            mm = re.search(r'"url"\s*:\s*"([^"]+)"', m.group(1))
            if mm:
                return _unescape_url(mm.group(1))
    # 1. m3u8（含转义形式）
    m = re.search(r"(https?:\\?/\\?/[^\s\"'<>]+\.m3u8[^\s\"'<>]*)", html_text, re.I)
    if m:
        return _scrub(_unescape_url(m.group(1)))
    # 2. mp4 / flv
    m = re.search(r"(https?:\\?/\\?/[^\s\"'<>]+\.(?:mp4|flv)[^\s\"'<>]*)", html_text, re.I)
    if m:
        return _scrub(_unescape_url(m.group(1)))
    # 3. var now
    m = re.search(r"var\s*now\s*=\s*['\"]([^'\"]+)['\"]", html_text)
    if m:
        return fix_url(_unescape_url(m.group(1)), host)
    # 4. player_data
    m = re.search(r"player_data\s*=\s*(\{.*?\})", html_text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            u = d.get("url") or d.get("play_url") or ""
            if u:
                return fix_url(_unescape_url(u), host)
        except Exception:
            pass
    # 5. iframe
    m = re.search(r"<iframe[^>]+src=[\"']([^\"']+)[\"']", html_text, re.I)
    if m:
        try:
            sub = _http_get(fix_url(m.group(1), host))
            return _extract_play(sub, host)
        except Exception:
            pass
    # 6. eval
    if re.search(r"eval\s*\(", html_text):
        return ""
    # 7. videoSources
    m = re.search(r"videoSources\s*:\s*(\[.*?\])", html_text, re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group(1))
            if arr:
                return fix_url(_unescape_url(arr[0].get("file", "")), host)
        except Exception:
            pass
    # 8. wvPlayer.play
    m = re.search(r"wvPlayer\.play\s*\(\s*['\"]([^\"]+)['\"]", html_text)
    if m:
        return fix_url(_unescape_url(m.group(1)), host)
    # 9. location.href
    m = re.search(r"location\.href\s*=\s*['\"]([^\"]+)['\"]", html_text)
    if m:
        return fix_url(_unescape_url(m.group(1)), host)
    # 10. url: 'xxx.m3u8'
    m = re.search(r"url\s*:\s*['\"]([^\"]+\.m3u8[^\"]*)['\"]", html_text, re.I)
    if m:
        return fix_url(_unescape_url(m.group(1)), host)
    # 11. var playurl
    m = re.search(r"var\s*playurl\s*=\s*['\"]([^\"]+)['\"]", html_text)
    if m:
        return fix_url(_unescape_url(m.group(1)), host)
    # 13. 通用视频直链
    m = re.search(r"(https?:\\?/\\?/[^\s\"'<>]+\.(?:m3u8|mp4|flv|ts)[^\s\"'<>]*)", html_text, re.I)
    if m:
        return _scrub(_unescape_url(m.group(1)))
    return ""


def _http_get(url, headers=None, timeout=15):
    try:
        if requests:
            r = requests.get(url, headers=headers or {}, timeout=timeout, verify=False)
            if r.status_code == 200:
                return r.text
            return ""
        import urllib.request
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "ignore")
    except Exception:
        return ""


def _http_post(url, data, headers=None, timeout=15):
    try:
        if requests:
            r = requests.post(url, data=data, headers=headers or {}, timeout=timeout, verify=False)
            if r.status_code == 200:
                return r.text
            return ""
        import urllib.request
        from urllib.parse import urlencode
        body = urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "ignore")
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════
# Spider 主类
# ═══════════════════════════════════════════════════════════════
class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = HOST
        self.name = SITE_NAME
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
            "Connection": "keep-alive",
        }
        self.session = requests.Session() if requests else None
        if self.session:
            self.session.headers.update(self.headers)
        self.seen_ids = set()
        self._timeout = 20

    # ---------- 基础 ----------
    def init(self, extend=""):
        """支持通过 extend 覆盖站点域名，例如：
        {"host": "https://www.zhongyuanxinhua.com"}
        """
        if extend:
            try:
                cfg = json.loads(extend)
                if cfg.get("host"):
                    self.host = cfg["host"].rstrip("/")
                    self.headers["Referer"] = self.host + "/"
                    if self.session:
                        self.session.headers.update({"Referer": self.host + "/"})
            except Exception:
                pass

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return any(x in url for x in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            if self.session:
                self.session.close()
        except Exception:
            pass

    def _fetch(self, url):
        if not url:
            return ""
        for _ in range(2):
            txt = self._http_get(url)
            if txt:
                return txt
        return ""

    def _http_get(self, url, timeout=None):
        """实例级 GET：优先复用 session（保持连接与 Cookie），否则降级 requests/urllib。"""
        timeout = timeout or self._timeout
        # 1) requests.Session
        if self.session:
            try:
                r = self.session.get(url, timeout=timeout, verify=False)
                if r.status_code == 200:
                    return r.text
                return ""
            except Exception:
                pass
        # 2) 裸 requests
        if requests:
            try:
                r = requests.get(url, headers=self.headers, timeout=timeout, verify=False)
                if r.status_code == 200:
                    return r.text
                return ""
            except Exception:
                pass
        # 3) urllib 兜底
        return _http_get(url, headers=self.headers, timeout=timeout)

    # ---------- 解析：分类导航 ----------
    def _parse_nav(self, html_text):
        """从首页导航解析分类：[{type_name, type_id}, ...]"""
        if not html_text:
            return []
        classes, seen = [], set()
        # 匹配顶部导航 /vodtype/1.html 形态
        pat = re.compile(
            r'<a[^>]+href=["\']([^"\']*/vodtype/(\d+)\.html)["\'][^>]*>([^<]{1,12})</a>',
            re.I)
        for href, tid, name in pat.findall(html_text):
            name = clean_text(name)
            if not name or name in ("首页", "Home", "搜索", "登录", "注册", "更多", "友情链接"):
                continue
            if tid in seen:
                continue
            seen.add(tid)
            classes.append({"type_name": name, "type_id": tid})
        return classes[:30]

    # ---------- 解析：列表项 ----------
    def _parse_list(self, html_text):
        """从分类/搜索页提取视频条目：[{vod_id, vod_name, vod_pic, vod_remarks}, ...]"""
        if not html_text:
            return []
        result = []
        seen = set()
        # ── 关键修复 ──────────────────────────────────────────────
        # Ewave 模板的卡片边界是 <div class="video-content-item">…</div></div>，
        # 而不是 <article class="post-list">。因为
        #   <article class="post-list video-list feaimg"> 只包住封面图 <a.video-img>，
        #   </article> 之后的兄弟节点 <p class="video-name"> 才是片名。
        # 旧写法按 article 切分 → 每个 block 里都没有片名 → 触发的兜底又误用整页
        # html_text 去搜第一个 video-name，导致所有条目片名都变成同一条（"多浪迪总统"）。
        # 这里改为按 video-content-item 切分，一次拿到「封面 + 片名 + 演员」完整卡片。
        # ──────────────────────────────────────────────────────────
        cards = re.findall(
            r'<div[^>]*class=["\'][^"\']*video-content-item[^"\']*["\'][^>]*>(.*?)</div>\s*</div>',
            html_text, re.I | re.S)
        if not cards:
            # 降级：搜索结果页用 <article class="post-list contt blockimg"> 卡片
            cards = re.findall(
                r'<article[^>]*class=["\'][^"\']*post-list[^"\']*contt[^"\']*["\'][^>]*>(.*?)</article>',
                html_text, re.I | re.S)
        if not cards:
            # 二次降级：按 col-xs-4 卡片切分（兼容个别模板变体）
            parts = re.split(r'(?=<div[^>]*class=["\'][^"\']*col-xs-\d)', html_text)
            cards = [p for p in parts if '/voddetail/' in p]
        for block in cards:
            try:
                # 提取详情链接和 ID
                m = re.search(r'href=["\']([^"\']*/voddetail/(\d+)\.html)["\']', block, re.I)
                if not m:
                    m = re.search(r'href=["\']([^"\']*/voddetail/(\d+))["\']', block, re.I)
                if not m:
                    continue
                vid = m.group(2)
                if vid in seen:
                    continue
                seen.add(vid)
                # 标题：优先 video-name 内 <a title="…">
                title = ""
                tm = re.search(
                    r'<p[^>]*class=["\'][^"\']*video-name[^"\']*["\'][^>]*>.*?title=["\']([^"\']+)["\']',
                    block, re.I | re.S)
                if tm:
                    title = clean_text(tm.group(1))
                if not title:
                    # 搜索结果页：<span class="entry-title"><a …>标题</a>
                    tm = re.search(
                        r'<span[^>]*class=["\'][^"\']*entry-title[^"\']*["\'][^>]*>\s*<a[^>]*title=["\']([^"\']+)["\']',
                        block, re.I | re.S)
                    if tm:
                        title = clean_text(tm.group(1))
                if not title:
                    # 兜底：卡片内第一个带 title 的详情链接
                    tm = re.search(
                        r'/voddetail/\d+\.html["\'][^>]*title=["\']([^"\']+)["\']', block, re.I)
                    if tm:
                        title = clean_text(tm.group(1))
                if not title:
                    tm = re.search(
                        r'<p[^>]*class=["\'][^"\']*video-name[^"\']*["\'][^>]*>\s*<a[^>]*>([^<]+)</a>',
                        block, re.I | re.S)
                    if tm:
                        title = clean_text(tm.group(1))
                if not title:
                    continue
                # 图片
                m = re.search(r'data-original=["\']([^"\']+)["\']', block, re.I)
                if not m:
                    m = re.search(r'src=["\']([^"\']+)["\']', block, re.I)
                pic = fix_url(m.group(1), self.host) if m else ""
                # 备注：更新状态（如"更新HD"）
                remarks = ""
                m = re.search(r'<span[^>]*class=["\'][^"\']*video-title[^"\']*["\'][^>]*>([^<]+)</span>', block, re.I)
                if m:
                    remarks = clean_text(m.group(1))[:20]
                if not remarks:
                    m = re.search(r'<em[^>]*class=["\'][^"\']*voddate[^"\']*["\'][^>]*>([^<]+)</em>', block, re.I)
                    if m:
                        remarks = clean_text(m.group(1))[:20]
                result.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": remarks})
                if len(result) >= 60:
                    break
            except Exception:
                continue
        return result

    def _pagecount(self, html_text, pg):
        """提取总页数"""
        try:
            # 站点真实分页器形如：<li class="current"><a href="#">1<span …>/1214</span></a></li>
            m = re.search(
                r'<li[^>]*class=["\'][^"\']*current["\'][^>]*>.*?/\s*(\d+)',
                html_text, re.S | re.I)
            if m:
                return max(int(m.group(1)), 1)
            # 标题里的 "第N页" 不含总数，故再兜底找 "最后一页/尾页" 链接
            m = re.search(
                r'href=["\'][^"\']*?(\d+)---\.html["\'][^>]*title=["\']第\d+页["\']',
                html_text, re.I)
            if m:
                return max(int(m.group(1)), 1)
            m = re.search(r"共\s*(\d+)\s*页", html_text)
            if m:
                return max(int(m.group(1)), 1)
        except Exception:
            pass
        return max(int(pg or 1), 1)

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        try:
            html_text = self._fetch(self.host + "/")
            classes = self._parse_nav(html_text)
            if not classes:
                classes = [dict(c) for c in DEFAULT_CLASSES]
            result = {"class": classes}
            # 仅在客户端请求筛选时才下发 filters，避免无谓开销/无效维度
            if filter:
                result["filters"] = DEFAULT_FILTERS
            return result
        except Exception:
            return {"class": [dict(c) for c in DEFAULT_CLASSES]}

    def homeVideoContent(self):
        try:
            html_text = self._fetch(self.host + "/")
            videos = self._parse_list(html_text)
            return {"list": videos}
        except Exception:
            return {"list": []}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            result = {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 24, "total": 0}
            pg = int(pg or 1)
            ext = self._parse_extend(extend)
            if ext:
                # 带筛选时走 /vodshow/ 路径（12 槽位），分页同样内嵌在槽位 8
                url = self._build_show_url(tid, ext, pg)
            elif pg <= 1:
                url = "{}/vodtype/{}.html".format(self.host, tid)
            else:
                url = "{}/vodtype/{}-{}.html".format(self.host, tid, pg)
            html_text = self._fetch(url)
            if html_text:
                items = self._parse_list(html_text)
                result["list"] = items
                result["pagecount"] = self._pagecount(html_text, pg)
                result["total"] = len(items)
            return result
        except Exception:
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 24, "total": 0}

    @staticmethod
    def _parse_extend(extend):
        """把 TVBox 传来的筛选参数统一转成 dict。"""
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        try:
            return json.loads(extend)
        except Exception:
            return {}

    def _build_show_url(self, tid, ext, pg):
        """
        构造 /vodshow/ 筛选地址。站点槽位（索引 0..11，'-' 连接，末尾 '.html'）：
          0=分类id  1=地区  2=排序(by)  3=类型  4=语言  5=字母
          6=空      7=空    8=页码      9=资源  10=空   11=年份
        实例：/vodshow/1-大陆-hits--喜剧-国语--2---2025.html
        """
        by_map = {"时间": "time", "人气": "hits", "评分": "score"}
        slots = [""] * 12
        slots[0] = str(tid)
        slots[1] = ext.get("地区", "")
        slots[2] = by_map.get(ext.get("排序", ""), ext.get("排序", ""))
        slots[3] = ext.get("类型", "")
        slots[4] = ext.get("语言", "")
        slots[5] = ext.get("字母", "")
        slots[8] = str(pg) if pg > 1 else ""
        slots[9] = ext.get("资源", "")
        slots[11] = ext.get("年份", "")
        path = "/vodshow/" + "-".join(slots) + ".html"
        return self.host + quote(path, safe="/-")

    # ---------- 详情 ----------
    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            result = {"list": []}
            url = "{}/voddetail/{}.html".format(self.host, vid)
            html_text = self._fetch(url)
            if not html_text:
                return result
            # 标题
            title = vid
            m = re.search(
                r'<h1[^>]*class=["\'][^"\']*detail-info-title[^"\']*["\'][^>]*>(.*?)</h1>',
                html_text, re.I | re.S)
            if m:
                mm = re.search(r'>([^<]+)<', m.group(1))
                if mm:
                    title = clean_text(mm.group(1))
            if not title or title == vid:
                m = re.search(r'<title>([^<]+)</title>', html_text, re.I)
                if m:
                    title = clean_text(m.group(1)).split("_")[0].split("-")[0].strip()
            # 图片
            pic = ""
            m = re.search(r'<div[^>]*class=["\'][^"\']*block-fea[^"\']*["\'][^>]*data-original=["\']([^"\']+)["\']', html_text, re.I)
            if not m:
                m = re.search(r'<img[^>]+(?:data-original|src)=["\']([^"\']+)["\']', html_text, re.I)
            if m:
                pic = fix_url(m.group(1), self.host)

            # 详情字段：演员 / 导演 / 类型 / 状态 / 地区 / 年份 / 语言 / 简介
            def _field(label):
                mm = re.search(
                    r'<span>%s[：:]</span>(.*?)(?:</p>|</li>)' % re.escape(label),
                    html_text, re.S)
                return clean_text(mm.group(1)) if mm else ""

            actor = _field("演员")
            director = _field("导演")
            area = _field("地区")
            year = _field("年份")
            lang = _field("语言")
            state = _field("状态")
            # 类型保留为多个标签拼接
            tm = re.search(r'<span>类型[：:]</span>(.*?)(?:</p>|</li>)', html_text, re.S)
            type_name = ""
            if tm:
                type_name = ",".join(
                    x.strip() for x in re.findall(r'>([^<>]+)</a>', tm.group(1)) if x.strip())
            # 剧情简介
            content = ""
            cm = re.search(
                r'<div[^>]*class=["\'][^"\']*entry-content[^"\']*["\'][^>]*>(.*?)</div>',
                html_text, re.S)
            if not cm:
                cm = re.search(r'<div[^>]*class=["\'][^"\']*show_text[^"\']*["\'][^>]*>(.*?)</div>',
                               html_text, re.S)
            if cm:
                content = clean_text(cm.group(1))

            # 播放源分组解析
            groups = self._parse_play_groups(html_text)
            sources, play_urls = [], []
            for sname, eps in groups:
                if not eps:
                    continue
                sources.append(sname)
                play_urls.append("#".join("{}${}".format(clean_text(t)[:40], fix_url(u, self.host)) for u, t in eps))
            if not sources:
                # 兜底：直接找所有 vodplay 链接
                eps = re.findall(
                    r'<a[^>]+href=["\']([^"\']*/vodplay/[^"\']*)["\'][^>]*>([^<]+)</a>',
                    html_text, re.I)
                if eps:
                    sources.append("默认")
                    play_urls.append("#".join(
                        "{}${}".format(clean_text(t)[:40], fix_url(u, self.host)) for u, t in eps))
            if not sources:
                sources.append("默认")
                play_urls.append("播放${}".format(vid))
            result["list"].append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "type_name": type_name,
                "vod_year": year,
                "vod_area": area,
                "vod_lang": lang,
                "vod_remarks": state,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": content,
                "vod_play_from": "$$$".join(sources),
                "vod_play_url": "$$$".join(play_urls),
            })
            return result
        except Exception:
            return {"list": []}

    def _parse_play_groups(self, html_text):
        """解析详情页播放源分组。

        真实结构：
          <li class="swiper-slide ewave-tab" data-target="#ewave-playlist-1"><a>云播资源</a></li>
          …
          <ul class="row … ewave-playlist-content …" id="ewave-playlist-1">
              <li><a href="/vodplay/8660-1-1.html">第01集</a></li>
          </ul>
        旧实现把「线路名列表」与「面板列表」按下标 zip 配对，一旦某个面板
        没解析到剧集被 continue，后续线路名就会整体错位（线路名与剧集不匹配）。
        这里改为通过 data-target 的 id 精确定位每个面板，彻底消除错位。
        """
        groups = []
        if not html_text:
            return groups
        # 线路：id -> 名称
        tab_pairs = re.findall(
            r'data-target=["\']#(ewave-playlist-\d+)["\'][^>]*>\s*<a[^>]*>([^<]+)</a>',
            html_text, re.I)
        if not tab_pairs:
            tab_pairs = re.findall(
                r'<li[^>]*class=["\'][^"\']*ewave-tab[^"\']*["\'][^>]*>\s*<a[^>]*>([^<]+)</a>',
                html_text, re.I)
            tab_pairs = [("ewave-playlist-1", n) for n in tab_pairs]
        for pid, sname in tab_pairs:
            sname = clean_text(sname)
            if not sname or sname in ("全部", "选集"):
                continue
            # 精确定位该线路对应的 <ul id="ewave-playlist-N">
            um = re.search(
                r'<ul[^>]*id=["\']%s["\'][^>]*>(.*?)</ul>' % re.escape(pid),
                html_text, re.I | re.S)
            if not um:
                continue
            eps = re.findall(
                r'<a[^>]+href=["\']([^"\']*/vodplay/[^"\']*)["\'][^>]*>([^<]+)</a>',
                um.group(1), re.I)
            if not eps:
                eps = re.findall(
                    r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{1,20})\s*</a>',
                    um.group(1), re.I)
            if eps:
                groups.append((sname, eps))
        return groups

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        header = {"Referer": self.host + "/", "User-Agent": UA}
        try:
            if self.isVideoFormat(id):
                return {"parse": 0, "url": id, "header": header}
            play_url = ""
            if id.startswith("http"):
                html_text = self._fetch(id)
                play_url = _extract_play(html_text, self.host)
            if play_url:
                return {"parse": 0, "url": play_url, "header": header}
            return {"parse": 0, "url": id, "header": header}
        except Exception:
            return {"parse": 0, "url": id, "header": header}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        try:
            result = {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 24, "total": 0}
            if not key:
                return result
            pg = int(pg or 1)
            # 站点原生搜索分页路径：/vodsearch/{kw}----------{pg}---.html
            # （关键词占据"地区"槽位；不传 pg 即第 1 页）
            page_seg = str(pg) if pg > 1 else ""
            url = "{}/vodsearch/{}----------{}---.html".format(
                self.host, quote(key, safe=""), page_seg)
            html_text = self._fetch(url)
            if html_text:
                items = self._parse_list(html_text)
                result["list"] = items
                result["pagecount"] = self._pagecount(html_text, pg)
                result["total"] = len(items)
            return result
        except Exception:
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 24, "total": 0}

    # ---------- 本地代理 ----------
    def localProxy(self, param):
        try:
            s = param if isinstance(param, str) else ""
            if not s:
                return [200, "video/MP2T", b"", {}]
            if "," in s:
                s = s.split(",", 1)[1]
            if s.startswith("http"):
                url = s
            else:
                b = s.encode()
                b += b"=" * (-len(b) % 4)
                url = base64.urlsafe_b64decode(b).decode("utf-8", "ignore")
                if not url.startswith("http"):
                    url = base64.b64decode(b).decode("utf-8", "ignore")
            headers = dict(self.headers)
            headers["Referer"] = self.host + "/"
            if requests:
                r = requests.get(url, headers=headers, timeout=self._timeout, verify=False)
                content_type = r.headers.get("Content-Type", "video/MP2T")
                return [r.status_code, content_type, r.content, {}]
            import urllib.request
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                ct = resp.headers.get("Content-Type", "video/MP2T")
                return [200, ct, resp.read(), {}]
        except Exception:
            return [200, "video/MP2T", b"", {}]
