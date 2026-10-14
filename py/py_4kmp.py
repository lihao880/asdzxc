# coding=utf-8
"""
目标站: 4KMP  (4kmp.com -> www.4k-av.com)
说明:
  - 站点 /s 原生搜索被 Cloudflare WAF 永久封禁(真实浏览器亦 403)，故内置【自建搜索模式】
  - 自建搜索原理融合自 AppGet 模板 sechMode: 并发翻分类页 -> 本地片名/别名/标签匹配
  - 默认开启自建搜索(可用 ext={"sechMode":"0"} 强制关闭)
"""
import re
import time
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
import sys
sys.path.append('..')
from base.spider import Spider

try:
    from curl_cffi import requests as cffi_requests
    _HAS_CFFI = True
except Exception:
    _HAS_CFFI = False

_REAL_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

class Spider(Spider):
    def init(self, extend=""):
        # 站点真实域名: 4kmp.com 会 301 -> 4k-av.com，三个域名内容一致，可互为备份
        self.hosts = ["https://4kmp.com", "https://www.4k-av.com", "https://4k-av.com"]
        self.host = self.hosts[0]
        # 注意: 站点首页 GET / 会被 WAF 判定异常，故 Referer 不使用站点根
        self.headers = {
            "User-Agent": _REAL_UA,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        # ---- 自建搜索参数 (默认开启) ----
        self.sech_mode = "1"            # 1=启用自建搜索 0=关闭
        self.search_pg_max = 34         # 单分类最大翻页(movie 34/tv 18)
        self.search_batch = 5           # 每批并发页数
        self.search_workers = 5         # 并发线程数
        self.search_cats = ("movie", "tv")
        if isinstance(extend, dict):
            self.sech_mode = str(extend.get("sechMode", self.sech_mode))
            try:
                self.search_pg_max = int(extend.get("searchPages", self.search_pg_max))
                self.search_batch = int(extend.get("searchBatch", self.search_batch))
                self.search_workers = int(extend.get("searchWorkers", self.search_workers))
            except Exception:
                pass
        self._local = threading.local()

    # ---------------------------------------------------------------- 请求层
    def _session(self):
        """每线程独立会话(线程安全)。"""
        s = getattr(self._local, "s", None)
        if s is None:
            if _HAS_CFFI:
                s = cffi_requests.Session(impersonate="chrome124")
            else:
                import requests
                s = requests.Session()
            s.headers.update(self.headers)
            self._local.s = s
        return s

    def _get(self, url, tries=3):
        """
        GET 带重试。
        关键: 站点有 Cloudflare 风控(短时限流~30s恢复 + 首页黑名单)，
        这里用 chrome124 TLS 指纹 + 失败自动切换镜像域名重试。
        """
        # 若传入的是绝对URL，先按当前 host 归一，便于故障切换到镜像
        path = url
        for h in self.hosts:
            if path.startswith(h):
                path = path[len(h):]
                break
        if not path.startswith("/"):
            path = "/" + path.lstrip("/")
        s = self._session()
        for i in range(tries):
            host = self.hosts[i % len(self.hosts)]
            full = host + path
            try:
                r = s.get(full, timeout=25)
                if r.status_code == 200 and "Cloudflare" not in r.text[:400]:
                    return r.text
            except Exception as e:
                print(f"[_get] {full[:48]} err {e}")
            time.sleep(3 + i * 2)
        return ""

    # ------------------------------------------------------------ 解析工具
    @staticmethod
    def _extract_remark(name, tags):
        """
        生成副标题(vod_remarks)。
        站点列表页没有独立的'更新至X集'字段：
          - 剧集的状态直接写在标题里，如 '韩国制造 第2季全6集' / '挑情丑闻 全8集'
          - 电影无集数，用标签(类型)兜底
        优先从标题抽 '全N集/第N季/N集' 作为副标题，其次用标签。
        """
        t = name or ""
        # 全N集 / 共N集 / 更新至N集
        m = re.search(r'(全|共|更新至)\s*(\d+)\s*集', t)
        if m:
            return m.group(0).replace(' ', '')
        # 第N季
        m = re.search(r'第\s*[一二三四五六七八九十\d]+\s*季', t)
        if m:
            s = m.group(0).replace(' ', '')
            m2 = re.search(r'(\d+)\s*集', t)
            return f"{s}·{m2.group(0)}" if m2 else s
        # 单独的 N集
        m = re.search(r'(\d+)\s*集', t)
        if m:
            return m.group(0)
        # 兜底: 标签
        return "、".join(tags[:3]) if tags else ""

    def _parse_item(self, item):
        """从列表项提取完整信息：标题 / 别名 / 年份 / 标签 / 简介 / 封面"""
        try:
            a = item.select_one('.title a')
            if not a:
                return None
            href = a.get('href', '')
            if not href:
                return None
            h2 = a.select_one('h2')
            name = h2.text.strip() if h2 else (a.get('title', '') or '').strip()
            if not name:
                return None
            alias_tag = item.select_one('.info h3')
            alias = alias_tag.text.strip() if alias_tag else ''
            year = ''
            for lb in item.select('.resyear label'):
                if lb.get('title') == '年份':
                    year = lb.text.strip()
                    break
            tags = [sp.text.strip() for sp in item.select('.tags span')]
            desc_tag = item.select_one('.videodesc p')
            desc = desc_tag.text.strip() if desc_tag else ''
            img = item.select_one('img')
            # 兼容懒加载: 优先 src，其次 data-src / data-original
            pic = ''
            if img:
                pic = img.get('src') or img.get('data-src') or img.get('data-original') or ''
            blob = " ".join([name, alias, year, " ".join(tags), desc]).lower()
            return {
                "vod_id": href,
                "vod_name": name,
                "vod_pic": urllib.parse.urljoin(self.host, pic) if pic else "",
                "vod_year": year,
                "vod_remarks": self._extract_remark(name, tags),
                "_blob": blob,
            }
        except Exception:
            return None

    def _parse_list(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('.NTMitem') or soup.select('.RTMitem')
        out = []
        for it in items:
            v = self._parse_item(it)
            if v:
                out.append(v)
        return out

    def _clean(self, videos):
        """去掉内部字段 _blob"""
        return [{k: v for k, v in x.items() if k != "_blob"} for x in videos]

    # ------------------------------------------------------------ 分类分页
    def _cat_page(self, cat, pg):
        url = f"{self.host}/{cat}/" if int(pg) == 1 else f"{self.host}/{cat}/page-{pg}.html"
        html = self._get(url)
        if not html:
            return []
        return self._parse_list(html)

    # ------------------------------------------------------------ 各接口
    def homeContent(self, filter):
        result = {"class": [], "filters": {}}
        try:
            result["class"] = [
                {"type_name": "电影", "type_id": "movie"},
                {"type_name": "电视剧", "type_id": "tv"},
            ]
            print(f"[homeContent] 分类 {len(result['class'])} 个")
        except Exception as e:
            print(f"[homeContent] 异常: {e}")
        return result

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg) if pg else 1
            cat = tid if tid in ("movie", "tv") else "movie"
            videos = self._cat_page(cat, pg)
            pagecount = 1
            html = self._get(f"{self.host}/{cat}/")
            m = re.search(r'页次\s*(\d+)\s*/\s*(\d+)', html) or \
                re.search(r'(\d+)\s*/\s*(\d+)', html)
            if m:
                pagecount = int(m.group(2)) or 1
            print(f"[categoryContent] {tid} p{pg} -> {len(videos)}条 / 共{pagecount}页")
            return {"list": self._clean(videos), "page": pg, "pagecount": pagecount,
                    "limit": len(videos), "total": len(videos) * pagecount}
        except Exception as e:
            print(f"[categoryContent] 异常: {e}")
            return {"list": [], "page": 1, "pagecount": 0, "limit": 0, "total": 0}

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else str(ids).split(",")[0]
            url = urllib.parse.urljoin(self.host, vod_id) if vod_id.startswith("/") else vod_id
            html = self._get(url)
            soup = BeautifulSoup(html, 'html.parser')

            title_el = soup.select_one('#MainContent_titleh12 .MainTitle') or \
                       soup.select_one('#MainContent_titleh12 div div') or soup.select_one('h1')
            vod_name = title_el.text.strip() if title_el else ""

            poster = soup.select_one('.poster img')
            vod_pic = urllib.parse.urljoin(self.host, poster.get('src', '')) if poster else ""

            # 当前页直接可播放的 m3u8
            src_tag = soup.select_one('video source')
            play_from, play_url = "", ""
            if src_tag and src_tag.get('src'):
                src = src_tag['src']
                play_url = urllib.parse.urljoin(self.host, src) if src.startswith("/") else src
                play_from = "4KMP"

            # ----------------------------------------------------------
            # 线路构建
            # 站点【只有一条线路】(4KMP)，不存在多条源。
            #   结构要点(踩坑记录):
            #   1) #rtlist 首个 <li> 是【当前集】，只有 <img>+<span class=stitle>，
            #      【无 <a>】，若只用 '#rtlist a[href]' 会漏掉当前集。
            #   2) 页面散落 /zh/ /en/ /ja/ 等多语言链接，必须限定在 #rtlist 内。
            #   3) 电影(/movie/)页的 #rtlist 是"相关推荐"，非分集，需按类型排除。
            #   4) 【多季合并】: 如"韩国制造"含 S01E01~E06 + S02E01~E06，
            #      站点把两季放在同一个 #rtlist 里(且两个季词条指向同一份列表)。
            #      -> 按 SxxExx 前缀自动分季拆成独立线路「第1季」「第2季」，
            #         集名保留完整编号，避免客户端显示成"第1集/第2集"看起来重复。
            # ----------------------------------------------------------
            ep_list = []
            is_tv = "/tv/" in url or "/tv/" in vod_id
            if is_tv:
                for li in soup.select('#rtlist li'):
                    a = li.select_one('a[href]')
                    span = li.select_one('.stitle') or li.select_one('span')
                    ep_name = span.get_text(strip=True) if span else ""
                    if not ep_name:
                        img = li.select_one('img')
                        ep_name = (img.get('title') or img.get('alt') or '').strip() if img else ''
                    if not ep_name:
                        continue
                    if a and a.get('href'):
                        href = a['href']
                        if re.match(r'^/(zh|en|ja|ko|es|pt|th|vi|ar|ru|hi|id|bn|fr|de|it)/', href):
                            href = re.sub(r'^/[a-z]{2}/', '/', href)
                        ep_url = urllib.parse.urljoin(self.host, href)
                    else:
                        ep_url = url          # 当前集无 <a>，回退当前页
                    ep_list.append((ep_name, ep_url))

            if ep_list:
                # 按季(Sxx)分组；无季号则归入默认组
                seasons = {}
                for nm, eu in ep_list:
                    m = re.match(r'^[Ss](\d{1,2})[Ee]', nm)
                    skey = int(m.group(1)) if m else 0
                    seasons.setdefault(skey, []).append((nm, eu))

                if len(seasons) > 1 and 0 not in seasons:
                    # 多季: 每季一条线路，线路名"第N季"
                    tabs, urls = [], []
                    for skey in sorted(seasons.keys()):
                        tabs.append(f"第{skey}季")
                        urls.append("#".join(f"{nm}${eu}" for nm, eu in seasons[skey]))
                    play_from = "$$$".join(tabs)
                    play_url = "$$$".join(urls)
                else:
                    # 单季/无季号: 维持一条 4KMP 线路
                    play_from = "4KMP"
                    play_url = "#".join(f"{nm}${eu}" for nm, eu in ep_list)
            elif play_from:
                # 电影: 单一线路，直接播当前 m3u8
                play_url = f"正片${play_url}"
            else:
                play_from, play_url = "4KMP", ""

            vod = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_play_from": play_from,
                "vod_play_url": play_url,
            }
            print(f"[detailContent] {vod_name} | 源:{play_from[:30]} | 集:{len(ep_list)}")
            return {"list": [vod]}
        except Exception as e:
            print(f"[detailContent] 异常: {e}")
            return {"list": []}

    @staticmethod
    def _fix_lang(href):
        """去掉 /en/ 语言前缀，统一走简体中文路径(可用中文UA更稳)。"""
        if href.startswith("/en/"):
            return href[3:]
        return href

    # ============================================================ 自建搜索
    def _bsearch(self, wd, pg_max=None):
        """
        自建搜索(融合 AppGet 模板 sechMode 思路):
          并发分批翻【电影/电视剧】分类页，本地按 片名+别名+年份+标签+简介 匹配。
          首批命中即停，未命中继续翻页直到 pg_max。
        """
        kw = (wd or "").strip().lower()
        if not kw:
            return []
        pg_max = pg_max or self.search_pg_max
        kvods, cpage = [], 1
        while cpage <= pg_max:
            bend = min(cpage + self.search_batch - 1, pg_max)
            tasks = [(c, p) for p in range(cpage, bend + 1) for c in self.search_cats]
            try:
                with ThreadPoolExecutor(max_workers=self.search_workers) as ex:
                    results = list(ex.map(lambda x: self._cat_page(*x), tasks))
            except Exception as e:
                print(f"[_bsearch] 并发异常: {e}")
                results = []
            for r in results:
                kvods.extend([v for v in r if kw in v.get("_blob", "")])
            if kvods:
                break
            cpage = bend + 1
        # 去重
        seen, uniq = set(), []
        for v in kvods:
            if v["vod_id"] in seen:
                continue
            seen.add(v["vod_id"])
            uniq.append(v)
        return uniq

    def searchContent(self, key, quick, pg="1"):
        try:
            print(f"[searchContent] '{key}' 自建搜索模式={self.sech_mode}")
            videos = self._bsearch(key)
            print(f"[searchContent] 命中 {len(videos)} 条")
            return {"list": self._clean(videos), "page": int(pg or 1), "pagecount": 1,
                    "limit": len(videos), "total": len(videos)}
        except Exception as e:
            print(f"[searchContent] 异常: {e}")
            return {"list": [], "page": 1, "pagecount": 0, "limit": 0, "total": 0}

    def playerContent(self, flag, id, vipFlags):
        try:
            if ".m3u8" in id or ".mp4" in id:
                return {"parse": 0, "playUrl": "", "url": id, "header": self.headers}
            url = urllib.parse.urljoin(self.host, id) if id.startswith("/") else id
            html = self._get(url)
            soup = BeautifulSoup(html, 'html.parser')
            src_tag = soup.select_one('video source')
            if src_tag and src_tag.get('src'):
                src = src_tag['src']
                play_url = urllib.parse.urljoin(self.host, src) if src.startswith("/") else src
                print(f"[playerContent] {flag} -> {play_url[:60]}...")
                return {"parse": 0, "playUrl": "", "url": play_url, "header": self.headers}
            print(f"[playerContent] {flag} 未解析到链接")
            return {"parse": 0, "playUrl": "", "url": "", "header": ""}
        except Exception as e:
            print(f"[playerContent] 异常: {e}")
            return {"parse": 0, "playUrl": "", "url": "", "header": ""}
