#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import logging
import urllib.parse
import os
import sys
import time
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    BaseSpider = object

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Spider(BaseSpider):

    BASE_URL = "http://www.sangshipian.com"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "http://www.sangshipian.com/",
    }

    CATEGORY_MAP = {
        "1": {"name": "丧尸电影", "url": "/sangshidianying/", "cat_id": "1"},
        "2": {"name": "丧尸电视剧", "url": "/sangshidianshiju/", "cat_id": "2"},
        "3": {"name": "丧尸动漫", "url": "/sangshidongman/", "cat_id": "3"},
    }

    # 分类页 URL 是 /<分类>/<分类ID>-<类型>-<语言>-<年代>-<?>-<?>-<地区>-<?>-<排序>-page<n>.html
    # 一共 9 个空段，缺省留空。站点自己的筛选链接把路径写死成 sangshidianying，
    # 直接在电视剧/动漫页点会串到电影，所以只能按段位自己拼。
    # 下面这份是站点 2026-10 的筛选树快照，仅在动态解析失败时兜底。
    FILTER_TYPES = [
        ("全部", ""), ("喜剧", "1"), ("爱情", "2"), ("动作", "3"), ("科幻", "4"),
        ("恐怖", "5"), ("战争", "6"), ("惊悚", "7"), ("犯罪", "8"), ("悬疑", "9"),
        ("奇幻", "10"), ("冒险", "11"), ("古装", "12"), ("鬼怪", "13"),
    ]
    FILTER_AREAS = [
        ("全部", ""), ("大陆", "dalu"), ("美国", "meiguo"), ("香港", "xianggang"),
        ("台湾", "taiwan"), ("韩国", "hanguo"), ("日本", "riben"), ("泰国", "taiguo"),
        ("新加坡", "xinjiapo"), ("马来西亚", "malaixiya"), ("印度", "yindu"),
        ("英国", "yingguo"), ("法国", "faguo"), ("加拿大", "jianada"),
    ]
    FILTER_YEARS = [
        ("全部", ""),
        ("2023", "2023"), ("2022", "2022"), ("2021", "2021"), ("2020", "2020"),
        ("2019", "2019"), ("2018", "2018"), ("2017", "2017"), ("2016", "2016"),
        ("2015", "2015"), ("2014", "2014"),
        ("2000-2009", "1999,2009"), ("90年代", "1990,1999"),
        ("80年代", "1980,1989"), ("更早", "1900,1980"),
    ]

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(self.HEADERS)
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=Retry(total=1, backoff_factor=0.3))
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self._cache = {}
        self._cache_ttl = 300
        self._init_session()

    def _init_session(self):
        try:
            self.session.get(f"{self.BASE_URL}/", timeout=10)
        except Exception:
            pass

    def init(self, extend):
        pass

    def getName(self):
        return "丧尸片网"

    def _parse_ext(self, ext):
        if not ext:
            return {}
        if isinstance(ext, dict):
            return ext
        if isinstance(ext, str):
            try:
                return json.loads(ext)
            except Exception:
                return {}
        return {}

    def _get(self, url, use_cache=True):
        if use_cache:
            cached = self._cache.get(url)
            if cached and (time.time() - cached[0] < self._cache_ttl):
                return cached[1]
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = "utf-8"
            if use_cache and resp.status_code == 200:
                self._cache[url] = (time.time(), resp)
            return resp
        except Exception as e:
            logger.error(f"请求失败 {url}: {e}")
            return None

    def homeContent(self, filter=False):
        try:
            url = f"{self.BASE_URL}/"
            resp = self._get(url)
            if not resp:
                return {}

            classes = [{"type_id": cid, "type_name": info["name"]}
                       for cid, info in self.CATEGORY_MAP.items()]

            home_list = self._parse_video_list(resp.text)

            return {
                "class": classes,
                "filters": self._get_filters(),
                "list": home_list,
            }
        except Exception as e:
            logger.error(f"获取首页失败: {e}")
            return {}

    def homeVideoContent(self):
        home = self.homeContent()
        return {"list": home.get("list", [])}

    def _get_filters(self):
        """构建「类型 / 地区 / 年代」三项筛选。

        优先从站点筛选导航（div.fed-casc-list 下的 dl 列表）实时解析，
        这样站点增删类目时脚本不用跟着改；解析不到就用内置快照兜底。
        结果按进程缓存，避免每次进首页都多打一次请求。
        """
        cached = getattr(self, "_filters_cache", None)
        if cached is not None:
            return cached

        groups = {}  # 标题 -> [(文本, 值)]
        try:
            # 用「电影 + 空筛选」页取导航：这是站点自己的默认页，导航一定在
            url = f"{self.BASE_URL}/sangshidianying/1--------page1.html"
            resp = self._get(url)
            if resp:
                groups = self._parse_cascade(resp.text)
        except Exception as e:
            logger.error(f"解析筛选项失败: {e}")

        def build(parsed, fallback):
            items = parsed or fallback
            # 第一项统一成「全部」
            return [{"n": t, "v": v} for t, v in items]

        filters = {}
        for cate_id in self.CATEGORY_MAP:
            filters[cate_id] = [
                {"key": "area", "name": "地区",
                 "value": build(groups.get("地区"), self.FILTER_AREAS)},
                {"key": "year", "name": "年代",
                 "value": build(groups.get("年代"), self.FILTER_YEARS)},
            ]
        self._filters_cache = filters
        return filters

    def _parse_cascade(self, html):
        """从 div.fed-casc-list 里解析出 {「地区」: [(文本, 段值)], ...}。

        导航结构是 <dl><dt>地区</dt><dd><a href=...>大陆</a></dd>...</dl>，
        链接形如 /sangshidianying/1------meiguo--page1.html。
        这里不直接用 href（路径写死了分类），只取出「地区/年代」那一段的值，
        再由 _build_cat_url 按当前分类重新拼。
        """
        result = {}
        try:
            soup = BeautifulSoup(html, "html.parser")
            box = soup.find("div", class_="fed-casc-list")
            if not box:
                return result
            for dl in box.find_all("dl"):
                dt = dl.find("dt")
                if not dt:
                    continue
                title = dt.get_text(strip=True)
                if title not in ("地区", "年代"):
                    continue
                items = []
                seen = set()
                for a in dl.find_all("a"):
                    text = a.get_text(strip=True)
                    if not text or text in seen:
                        continue
                    value = self._filter_value_from_href(a.get("href", ""), title)
                    seen.add(text)
                    items.append((text, value))
                if items:
                    result[title] = items
        except Exception as e:
            logger.error(f"解析筛选导航异常: {e}")
        return result

    def _filter_value_from_href(self, href, title):
        """从筛选链接里抠出「地区」或「年代」对应的段值。"""
        try:
            path = urllib.parse.urlparse(href).path
            name = path.rsplit("/", 1)[-1]            # 1-5--2020-----page1.html
            name = re.sub(r"-page\d+\.html$", "", name)  # 1-5--2020-----
            parts = name.split("-")
            # 段位: [分类, 类型, 语言, 年代, ?, ?, 地区, ?, 排序]
            if title == "年代" and len(parts) > 3:
                return parts[3]
            if title == "地区" and len(parts) > 6:
                return parts[6]
        except Exception:
            pass
        return ""

    def _has_filter(self, ext):
        """判断是否带了地区/年代筛选（"全部"或空视为没筛）。"""
        ext = ext or {}
        if not isinstance(ext, dict):
            try:
                ext = json.loads(ext)
            except Exception:
                ext = {}
        for key in ("area", "year"):
            value = str(ext.get(key) or "").strip()
            if value and value not in ("全部", "all"):
                return True
        return False

    def _build_cat_url(self, cat_info, page, ext):
        """按 类型/地区/年代 拼分类页地址。

        URL 共 9 段：<分类ID>-<类型>-<语言>-<年代>-<?>-<?>-<地区>-<?>-<排序>
        空段保持为空，"全部" 也对应空段。
        """
        ext = ext or {}
        if not isinstance(ext, dict):
            try:
                ext = json.loads(ext)
            except Exception:
                ext = {}
        parts = [""] * 9
        parts[0] = str(cat_info["cat_id"])

        area = str(ext.get("area") or "").strip()
        year = str(ext.get("year") or "").strip()
        # 兼容「全部」被当成字面值传进来的情况
        if area in ("全部", "all", ""):
            area = ""
        if year in ("全部", "all", ""):
            year = ""
        parts[3] = year
        parts[6] = area

        has_filter = bool(area or year)
        if not has_filter:
            # 无筛选：站点只认 /<分类>/<分类ID>-page<n>.html 这种短格式才真能翻页。
            # 用 9 段格式写 page2 会永远返回第一页（实测 1--------page2.html 与
            # page1 内容完全一致），所以这里必须走短格式。
            return f"{self.BASE_URL}{cat_info['url']}{parts[0]}-page{page}.html"

        # 带筛选：只能用 9 段格式，而且站点对它的页码不生效（page2 仍返回第 1 页）。
        # 实测"筛选 + 翻页"这个组合在站点侧就是不支持的，因此固定取第 1 页，
        # 由调用方把 pagecount 报成 1，避免用户翻页翻出重复内容。
        seg = "-".join(parts)
        # 9 段 → 8 个连字符；末段为空时 join 已带出结尾的 "-"，直接接 page<n>.html
        # 例: 1------hanguo--page1.html / 1---2020-----page1.html
        return f"{self.BASE_URL}{cat_info['url']}{seg}page1.html"

    def categoryContent(self, tid, pg, filter, ext):
        try:
            page = int(pg) if pg else 1
            type_id = str(tid)

            if type_id not in self.CATEGORY_MAP:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

            cat_info = self.CATEGORY_MAP[type_id]
            url = self._build_cat_url(cat_info, page, ext)

            resp = self._get(url)
            if not resp:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

            videos = self._parse_video_list(resp.text)
            pagecount = self._parse_total_pages(resp.text)
            # 站点不支持"筛选 + 翻页"：带筛选时永远只有一页数据，如实报 1，
            # 否则用户会点进第 2 页拿到和第一页一模一样的列表。
            if self._has_filter(ext):
                pagecount = 1

            return {
                "list": videos,
                "page": page,
                "pagecount": pagecount if pagecount > 1 else 1,
                "limit": 48,
                "total": pagecount * 48 if pagecount > 1 else len(videos),
            }
        except Exception as e:
            logger.error(f"获取分类内容失败: {e}")
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def _parse_total_pages(self, html):
        """解析总页数。

        只从分页组件 div.fed-page-info 里取，不能全文扫：站点推荐位/排行榜里混着
        别的栏目的 -page63 链接，全文 findall 会把它当成当前列表的页数（实测筛选
        后只有 1 页却报 63 页，用户点第 2 页拿回来的还是同一批数据）。

        分页组件里第一个 <a> 就是权威的「当前页/总页数」，形如 0/12、0/1。
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            box = soup.find('div', class_=lambda x: x and 'fed-page-info' in str(x))
            if box:
                # 1) 权威字段 当前页/总页数
                m = re.search(r'(\d+)\s*/\s*(\d+)', box.get_text(' ', strip=True))
                if m:
                    return max(1, int(m.group(2)))
                # 2) 退而求其次：页码链接的最大值
                nums = re.findall(r'page(\d+)\.html', str(box))
                if nums:
                    return max(1, max(int(n) for n in nums))
        except Exception as e:
            logger.error(f"解析页数失败: {e}")

        # 站点明确写了「共 N 页」时以此为准
        page_m = re.search(r'共\s*(\d+)\s*页', html)
        if page_m:
            return max(1, int(page_m.group(1)))
        return 1

    def _parse_video_list(self, html):
        videos = []
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.find_all('li', class_='fed-list-item')

        for item in items:
            links = item.find_all('a', href=re.compile(r'/sangshi.*?/vod\d+\.html'))
            if not links:
                continue

            href = links[0].get('href', '')
            vid_match = re.search(r'/vod(\d+)\.html', href)
            if not vid_match:
                continue
            vid_id = vid_match.group(1)

            title = ''
            title_link = item.find('a', class_='fed-list-title')
            if title_link:
                title = title_link.get_text(strip=True)
            
            if not title and len(links) > 1:
                title = links[1].get_text(strip=True)

            poster = ''
            pics_link = item.find('a', class_='fed-list-pics')
            if pics_link:
                data_original = pics_link.get('data-original', '')
                if data_original:
                    poster = data_original
                    if not poster.startswith('http'):
                        poster = self.BASE_URL + poster

            remarks = ''
            score_span = item.find('span', class_='fed-list-score')
            if score_span:
                remarks = score_span.get_text(strip=True)
            
            if not remarks:
                remarks_span = item.find('span', class_='fed-list-remarks')
                if remarks_span:
                    remarks = remarks_span.get_text(strip=True)

            if title and len(title) > 1:
                videos.append({
                    "vod_id": vid_id,
                    "vod_name": title,
                    "vod_pic": poster,
                    "vod_remarks": remarks,
                })

        return videos

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else str(ids)

            cat_urls = [self.CATEGORY_MAP[cid]['url'] for cid in self.CATEGORY_MAP]
            detail_url = None
            for cat_url in cat_urls:
                url = f"{self.BASE_URL}{cat_url}vod{vod_id}.html"
                resp = self._get(url)
                if resp and resp.status_code == 200 and len(resp.text) > 1000:
                    detail_url = url
                    break

            if not detail_url:
                return {"list": []}

            html = resp.text
            soup = BeautifulSoup(html, 'html.parser')

            title = ''
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)

            if not title:
                meta_title = soup.find('meta', property='og:title')
                if meta_title:
                    title = meta_title.get('content', '')

            poster = ''
            og_image = soup.find('meta', property='og:image')
            if og_image:
                poster = og_image.get('content', '')

            if not poster:
                main_img = soup.find('div', class_=lambda x: x and 'main' in str(x).lower())
                if main_img:
                    img = main_img.find('img')
                    if img:
                        poster = img.get('src', '') or img.get('data-src', '')
                        if poster and not poster.startswith('http'):
                            poster = self.BASE_URL + poster

            year = area = type_name = lang = actor = director = remarks = content = ''

            # 详情字段在 <dd class="fed-deta-content"><ul><li>主演：... </li>
            # <li>导演：...</li><li>分类：...</li><li>地区：...</li><li>年份：...</li>
            # 都是一个个独立 li，按 li 解析比在整段文本上跑正则可靠：
            # 原来用 r'主演[：:]\s*([^\s]+)' 只能吃到第一个人名（人名之间是空格），
            # 而且站点写的是「分类」不是「类型」，所以 type_name 一直是空的。
            info_dd = soup.find('dd', class_=lambda x: x and 'fed-deta-content' in str(x))
            if info_dd:
                fields = {}
                for li in info_dd.find_all('li'):
                    txt = li.get_text(' ', strip=True)
                    m = re.match(r'^([^：:]{1,6})[：:]\s*(.*)$', txt)
                    if m:
                        fields[m.group(1).strip()] = m.group(2).strip()

                if fields.get('主演'):
                    actor = fields['主演'].replace(' ', ',')
                if fields.get('导演'):
                    director = fields['导演'].replace(' ', ',')
                # 站点用「分类」；兼容别的模板写「类型」
                type_name = fields.get('分类') or fields.get('类型') or type_name
                if fields.get('地区'):
                    area = fields['地区']
                if fields.get('年份'):
                    ym = re.search(r'(\d{4})', fields['年份'])
                    if ym:
                        year = ym.group(1)
                if fields.get('语言'):
                    lang = fields['语言']

            if not area or not year or not type_name:
                # 兜底：整体文本里再捞一次（模板改版时仍能出数据）
                info_div = soup.find('div', class_='fed-main-info')
                info_text = info_div.get_text(' ', strip=True) if info_div else ''
                if not area:
                    m = re.search(r'地区[：:]\s*([^\s]+)', info_text)
                    if m:
                        area = m.group(1).strip()
                if not type_name:
                    m = re.search(r'(?:分类|类型)[：:]\s*([^\s]+)', info_text)
                    if m:
                        type_name = m.group(1).strip()
                if not year:
                    year_m = re.search(r'(?:年份|年代)[：:]\s*(\d{4})', info_text) or \
                             re.search(r'(\d{4})', info_text)
                    if year_m:
                        year = year_m.group(1)

            content_divs = soup.find_all('div', class_='fed-tabs-boxs')
            for div in content_divs:
                content_text = div.get_text(' ', strip=True).strip()
                if content_text and content_text not in ['720P', '1080P', 'HD', 'BD', '高清'] and len(content_text) > 10:
                    content = content_text
                    break

            if not content:
                info_divs = soup.find_all('div', class_='fed-tabs-info')
                for div in info_divs:
                    content_text = div.get_text(' ', strip=True)
                    content_m = re.search(r'剧情介绍\s*(.*)', content_text)
                    if content_m:
                        content = content_m.group(1).strip()
                        break

            if not content:
                content_m = re.search(r'剧情[：:]\s*(.*?)[详细介绍|立即播放|你可能喜欢]', html)
                if content_m:
                    content = content_m.group(1).strip()

            if content:
                content = re.sub(r'<[^>]+>', '', content)
                content = re.sub(r'\s+', ' ', content).strip()

            play_from_list, play_url_list = self._parse_play_sources(html, vod_id, cat_url)

            vod_item = {
                "vod_id": vod_id,
                "vod_name": title+"",
                "vod_pic": poster,
                "type_name": type_name,
                "vod_year": year,
                "vod_area": area,
                "vod_remarks": remarks,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": content,
                "vod_play_from": '$$$'.join(play_from_list),
                "vod_play_url": '$$$'.join(play_url_list),
            }
            return {"list": [vod_item]}
        except Exception as e:
            logger.error(f"获取详情失败: {e}")
            return {"list": []}

    def _parse_play_sources(self, html, vod_id, cat_url):
        play_from_list = []
        play_url_list = []

        soup = BeautifulSoup(html, 'html.parser')

        source_tabs = soup.find_all('a', href=re.compile(r'/play\d+-\d+-\d+\.html'))

        sources = {}
        seen_hrefs = set()

        for tab in source_tabs:
            href = tab.get('href', '')
            
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)

            m = re.search(r'/play(\d+)-(\d+)-(\d+)\.html', href)
            if not m:
                continue

            sid = int(m.group(2))
            epid = int(m.group(3))
            ep_name = tab.get_text(strip=True)

            if ep_name in ['立即播放', '720P', '1080P', 'HD', 'BD', '高清']:
                if epid == 1:
                    ep_name = "正片"
                else:
                    ep_name = f"第{epid}集"

            if not ep_name:
                ep_name = f"第{epid}集"

            if sid not in sources:
                sources[sid] = {}

            if epid not in sources[sid]:
                sources[sid][epid] = (ep_name, href)

        for idx, sid in enumerate(sorted(sources.keys())):
            episodes_dict = sources[sid]
            episodes = sorted(episodes_dict.items(), key=lambda x: x[0])

            if not episodes:
                continue

            from_name = f"线路{sid}"
            play_from_list.append(from_name)

            urls = [f"{ep_name}${self.BASE_URL}{href}" for epid, (ep_name, href) in episodes]
            play_url_list.append('#'.join(urls))

        if not play_from_list:
            main_url = f"{self.BASE_URL}{cat_url}play{vod_id}-0-1.html"
            play_from_list.append("正片")
            play_url_list.append(f"正片${main_url}")

        return play_from_list, play_url_list

    def playerContent(self, flag, id, vipFlags):
        try:
            url = id
            if url.startswith('/'):
                url = self.BASE_URL + url
            elif not url.startswith('http'):
                for cat_url in [self.CATEGORY_MAP[cid]['url'] for cid in self.CATEGORY_MAP]:
                    test_url = f"{self.BASE_URL}{cat_url}play{url}.html"
                    resp = self._get(test_url)
                    if resp and resp.status_code == 200:
                        url = test_url
                        break

            resp = self._get(url, use_cache=False)
            if not resp:
                return {}

            html = resp.text

            m3u8_m = re.search(r'(https?://[^\s\"\'<>]+\.m3u8[^\"\']*)', html)
            if m3u8_m:
                play_url = m3u8_m.group(1)
                if '.m3u8' in play_url:
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": play_url,
                        "header": json.dumps({
                            "User-Agent": self.HEADERS["User-Agent"],
                            "Referer": self.BASE_URL + "/",
                        }),
                    }

            iframe_m = re.search(r'<iframe[^>]*src=[\"]([^\"]+)[\"]', html)
            if iframe_m:
                iframe_url = iframe_m.group(1)
                if not iframe_url.startswith('http'):
                    iframe_url = self.BASE_URL + iframe_url

                iframe_resp = self._get(iframe_url, use_cache=False)
                if iframe_resp:
                    iframe_html = iframe_resp.text
                    m3u8_m2 = re.search(r'(https?://[^\s\"\'<>]+\.m3u8[^\"\']*)', iframe_html)
                    if m3u8_m2:
                        return {
                            "parse": 0,
                            "playUrl": "",
                            "url": m3u8_m2.group(1),
                            "header": json.dumps({
                                "User-Agent": self.HEADERS["User-Agent"],
                                "Referer": self.BASE_URL + "/",
                            }),
                        }

            return {
                "parse": 1,
                "playUrl": "",
                "url": url,
                "header": json.dumps({
                    "User-Agent": self.HEADERS["User-Agent"],
                    "Referer": self.BASE_URL + "/",
                }),
            }
        except Exception as e:
            logger.error(f"解析播放失败: {e}")
            return {}

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
            encoded_key = urllib.parse.quote(key)

            url = f"{self.BASE_URL}/vod-search-wd-{encoded_key}-page{page}.html"

            resp = self._get(url, use_cache=False)
            if not resp:
                return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

            videos = self._parse_video_list(resp.text)
            pagecount = self._parse_total_pages(resp.text)

            return {
                "list": videos,
                "page": page,
                "pagecount": pagecount if pagecount > 1 else 1,
                "limit": 48,
                "total": pagecount * 48 if pagecount > 1 else len(videos),
            }
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}


if __name__ == "__main__":
    spider = Spider()
    print("=== 首页 ===")
    home = spider.homeContent()
    print("分类:", [c["type_name"] for c in home.get("class", [])])
    print("首页视频数:", len(home.get("list", [])))
    if home.get("list"):
        v = home["list"][0]
        print(f"示例: {v['vod_name']} | 海报: {bool(v['vod_pic'])}")

    print("\n=== 分类(丧尸电影) ===")
    cate = spider.categoryContent("1", 1, 0, {})
    print(f"视频数: {len(cate.get('list', []))}, 总页数: {cate.get('pagecount')}")
    if cate.get("list"):
        v = cate["list"][0]
        print(f"示例: {v['vod_name']} | 海报: {bool(v['vod_pic'])}")

    print("\n=== 分类(丧尸电视剧) ===")
    cate2 = spider.categoryContent("2", 1, 0, {})
    print(f"视频数: {len(cate2.get('list', []))}")
    if cate2.get("list"):
        for v in cate2["list"][:3]:
            print(f"  {v['vod_name']}")

    print("\n=== 分类(丧尸动漫) ===")
    cate3 = spider.categoryContent("3", 1, 0, {})
    print(f"视频数: {len(cate3.get('list', []))}")
    if cate3.get("list"):
        for v in cate3["list"][:3]:
            print(f"  {v['vod_name']}")

    if cate.get("list"):
        vid = cate["list"][0]["vod_id"]
        print(f"\n=== 详情({vid}) ===")
        detail = spider.detailContent([vid])
        if detail.get("list"):
            d = detail["list"][0]
            print(f"片名: {d['vod_name']}")
            print(f"海报: {'有' if d['vod_pic'] else '无'}")
            print(f"年份: {d['vod_year']}")
            print(f"导演: {d['vod_director']}")
            print(f"主演: {d['vod_actor']}")
            print(f"类型: {d['type_name']}")
            print(f"简介: {d['vod_content'][:100] if d['vod_content'] else '无'}")
            print(f"播放源: {d['vod_play_from']}")

    print("\n=== 搜索(僵尸) ===")
    res = spider.searchContent("僵尸", False, "1")
    print(f"搜索结果数: {len(res.get('list', []))}")
    if res.get("list"):
        v = res["list"][0]
        print(f"示例: {v['vod_name']} | 海报: {bool(v['vod_pic'])}")
