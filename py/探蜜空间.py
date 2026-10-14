# coding: utf-8
"""
站点：探蜜空间·花影社 (hlfuli.com)
类型：HTML 视频站（非 MacCMS，Cloudflare 后端）
主域名：https://hlfuli.com
内容类型：成人视频
特殊说明：
  - 分类路由 /category/{slug}/，分页 ?page={page}&c=1
  - 详情页 /video/{slug}-{id}/，播放直链内嵌在 #url-data 的 data-val 属性
  - m3u8 取证：无广告、无多码率、无 KEY、非图片流、分片可达 → 直接返回原始直链，不走代理
  - data-free="True" 为免费视频；data-vip="1" 为会员专属，播放直链仍可能内嵌
最后验证：2026-09-13
"""
import re
import json
from urllib.parse import quote, urljoin

from base.spider import Spider as BaseSpider

try:
    from lxml import etree
except ImportError:
    etree = None


class Spider(BaseSpider):

    def __init__(self):
        # 零网络：仅本地初始化
        self.host = "https://hlfuli.com"
        self.extend = ""
        # 顶级分类（静态硬编码，法则16/17）
        self.classes = [
            {"type_id": "all", "type_name": "全部"},
            {"type_id": "chinese-premium", "type_name": "精品国产"},
            {"type_id": "welfare-cosplay", "type_name": "福利姬"},
            {"type_id": "virgin-girl", "type_name": "处女&少女"},
            {"type_id": "incest", "type_name": "乱伦"},
            {"type_id": "SM", "type_name": "网暴"},
            {"type_id": "candid-selfie", "type_name": "偷拍自拍"},
            {"type_id": "seduce", "type_name": "偷情"},
            {"type_id": "alternative", "type_name": "另类视频"},
            {"type_id": "latest", "type_name": "最新资源"},
            {"type_id": "special", "type_name": "特色资源"},
            {"type_id": "loli-student", "type_name": "萝莉学生"},
            {"type_id": "today-expose", "type_name": "今日爆料"},
        ]
        # 站点无真实筛选 DOM，返回空 filters（避免伪造假筛选）
        self.filters = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept-Language": "zh-Hans-CN,zh;q=0.9",
        }

    def getName(self):
        return "探蜜空间"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 零网络
        self.extend = extend or ""

    def _full_url(self, path):
        if not path:
            return ""
        if path.startswith("http"):
            return path
        if path.startswith("//"):
            return "https:" + path
        return urljoin(self.host, path)

    # ---------- 首页 ----------

    def homeContent(self, filter):
        # 零网络
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 首页推荐 = 全部视频第一页
        return self.categoryContent("all", "1", False, {})

    # ---------- 分类列表 ----------

    def _parse_extend(self, extend):
        """支持 dict / '{a=b}' / 'a=b' 三种格式"""
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            s = extend.strip()
            try:
                return json.loads(s)
            except Exception:
                pass
            result = {}
            for part in s.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    result[k.strip()] = v.strip()
            return result
        return {}

    def _list_url(self, tid, pg):
        page = pg or "1"
        if tid in ("all", "", None):
            base = "%s/video" % self.host
        else:
            base = "%s/category/%s/" % (self.host, tid)
        if str(page) == "1":
            return base if tid in ("all", "", None) else base
        sep = "&" if "?" in base else "?"
        return "%s%spage=%s&c=1" % (base, sep, page)

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        url = self._list_url(tid, page)
        try:
            r = self.fetch(url, headers=self.headers, timeout=15)
        except Exception as e:
            self.log({"category": "fetch_exception", "error": type(e).__name__})
            r = None
        if not r or r.status_code != 200:
            self.log({"category": "fetch_failed", "status": getattr(r, "status_code", None)})
            return {"list": [], "page": int(page) if page.isdigit() else 1,
                    "pagecount": 1, "limit": 20, "total": 0}

        html = r.text or ""
        items = self._parse_list_html(html)
        # 分页总页数：从分页区最大页码推断，兜底 10
        pagecount = self._parse_pagecount(html) or 10
        return {
            "list": items,
            "page": int(page) if page.isdigit() else 1,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20,
        }

    def _parse_pagecount(self, html):
        try:
            nums = re.findall(r'page=(\d+)', html)
            nums = [int(n) for n in nums if n.isdigit()]
            nums = [n for n in nums if 1 <= n <= 5000]
            if nums:
                return max(nums)
        except Exception:
            pass
        return 0

    def _parse_list_html(self, html):
        """解析列表项：ul#data_list li"""
        items = []
        if not html:
            return items
        try:
            if etree is not None:
                doc = etree.HTML(html)
                lis = doc.xpath('//ul[@id="data_list"]/li')
                for li in lis:
                    a_list = li.xpath('.//span[@class="sTit"]/a')
                    if not a_list:
                        continue
                    a = a_list[0]
                    href = a.get("href", "")
                    name = (a.text or "").strip()
                    if not name:
                        name = (a.get("title") or "").strip()
                    pic_list = li.xpath('.//div[@class="pic"]//img')
                    pic = ""
                    if pic_list:
                        pic = pic_list[0].get("src", "") or pic_list[0].get("data-original", "")
                    des_list = li.xpath('.//span[@class="sDes"]')
                    remark = (des_list[0].text or "").strip() if des_list else ""
                    vid = self._href_to_id(href)
                    if not vid or not name:
                        continue
                    items.append({
                        "vod_id": vid,
                        "vod_name": name,
                        "vod_pic": self._full_url(pic),
                        "vod_remarks": remark,
                    })
        except Exception as e:
            self.log({"parse_list": "exception", "error": type(e).__name__})
        return items

    @staticmethod
    def _href_to_id(href):
        """/video/movie-4045/ -> https://hlfuli.com/video/movie-4045/"""
        if not href:
            return ""
        m = re.search(r'/video/([a-zA-Z0-9_\-]+)/?', href)
        if m:
            return "/video/%s/" % m.group(1)
        return ""

    # ---------- 详情 ----------

    @staticmethod
    def _norm_ids(ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
        pid = str(vid).replace("$", "|")
        return {"list": [{
            "vod_id": vid, "vod_name": title or "未知标题", "vod_pic": pic or "",
            "vod_remarks": remarks, "vod_content": "",
            "vod_play_from": "播放", "vod_play_url": "播放$" + pid,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}

        # raw 是 /video/xxx-123/ 形式
        detail_url = self._full_url(raw)
        if not detail_url.startswith("http"):
            detail_url = self.host + "/" + raw.lstrip("/")

        title = ""
        pic = ""
        content = ""
        m3u8 = ""
        try:
            r = self.fetch(detail_url, headers=self.headers, timeout=15)
            if r and r.status_code == 200:
                html = r.text or ""
                if len(html) > 500:
                    parsed = self._parse_detail_html(html)
                    title = parsed.get("title", "")
                    pic = parsed.get("pic", "")
                    content = parsed.get("content", "")
                    m3u8 = parsed.get("m3u8", "")
        except Exception as e:
            self.log({"detail": "exception", "error": type(e).__name__})

        if not m3u8:
            # 兜底骨架：交给 playerContent 再抓一次
            return self._skeleton(raw, title, pic)

        play_id = self._pack_play_id(m3u8, detail_url)
        vod = {
            "vod_id": raw,
            "vod_name": title or "视频",
            "vod_pic": pic,
            "vod_remarks": content or "",
            "vod_content": content or "",
            "vod_play_from": "播放",
            "vod_play_url": "播放$" + play_id,
        }
        return {"list": [vod]}

    def _parse_detail_html(self, html):
        result = {"title": "", "pic": "", "content": "", "m3u8": ""}
        try:
            # 标题：<h1> 或 og:title 或 <title>
            m = re.search(r'<title>(.*?)</title>', html, re.S)
            if m:
                t = m.group(1).strip()
                t = re.sub(r'\s*[-_|].*?探蜜空间.*$', '', t).strip()
                result["title"] = t
            # 播放直链：#url-data 的 data-val
            m2 = re.search(r'id="url-data"[^>]*data-val="([^"]+)"', html)
            if not m2:
                m2 = re.search(r'data-val="(https?://[^"]*\.m3u8[^"]*)"', html)
            if m2:
                result["m3u8"] = m2.group(1).strip()
            # 详情封面
            m3 = re.search(r'class="detailPic".*?<img[^>]+src="([^"]+)"', html, re.S)
            if not m3:
                m3 = re.search(r'class="aesImgTag"[^>]*src="([^"]+)"', html)
            if m3:
                result["pic"] = self._full_url(m3.group(1).strip())
            # 观看次数/评分作为 content
            m4 = re.search(r'观看次数：\s*(\d+)', html)
            if m4:
                result["content"] = "观看次数：" + m4.group(1)
        except Exception:
            pass
        return result

    def _pack_play_id(self, m3u8, page_url):
        """播放ID 内禁止裸 $，用 | 分隔：m3u8|页面URL"""
        safe = m3u8.replace("$", "%24")
        return safe + "|" + page_url

    # ---------- 搜索 ----------

    def searchContent(self, key, quick, pg="1"):
        page = str(pg or "1")
        kw = quote(str(key or ""), safe="")
        url = "%s/video/search/?q=%s" % (self.host, kw)
        if page != "1":
            url += "&page=" + page
        try:
            r = self.fetch(url, headers=self.headers, timeout=15)
        except Exception as e:
            self.log({"search": "exception", "error": type(e).__name__})
            r = None
        if not r or r.status_code != 200:
            return {"list": [], "page": int(page) if page.isdigit() else 1}
        html = r.text or ""
        # 无结果污染过滤
        if re.search(r'没有找到|暂无数据|搜索无结果', html):
            return {"list": [], "page": int(page) if page.isdigit() else 1}
        items = self._parse_list_html(html)
        return {"list": items, "page": int(page) if page.isdigit() else 1}

    # ---------- 播放 ----------

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id or "").strip()
        page_url = ""

        # 拆包：m3u8|页面URL
        if "|" in play_url:
            parts = play_url.split("|", 1)
            play_url = parts[0]
            page_url = parts[1] if len(parts) > 1 else ""
        # 兼容 名称$地址 形式
        if "$" in play_url:
            play_url = play_url.split("$", 1)[1]

        play_url = play_url.replace("%24", "$")

        # 已是 m3u8/mp4 直链 → 直接返回，不走代理（法则30：m3u8_analyzer 取证无广告）
        if play_url and re.search(r'\.(m3u8|mp4|flv)(\?|$)', play_url, re.I):
            if not play_url.startswith("http"):
                if play_url.startswith("//"):
                    play_url = "https:" + play_url
                else:
                    play_url = "https://" + play_url
            return {"parse": 0, "url": play_url, "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
            }}

        # 兜底：抓详情页提取 data-val
        if page_url:
            try:
                r = self.fetch(page_url, headers=self.headers, timeout=15)
                if r and r.status_code == 200:
                    m = re.search(r'data-val="(https?://[^"]*\.m3u8[^"]*)"', r.text or "")
                    if m:
                        return {"parse": 0, "url": m.group(1).strip(), "header": {
                            "User-Agent": self.headers["User-Agent"],
                            "Referer": self.host + "/",
                        }}
            except Exception as e:
                self.log({"player": "fallback_exception", "error": type(e).__name__})

        # 最后手段：嗅探
        if page_url:
            return {"parse": 1, "url": page_url, "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
            }}
        return {"parse": 1, "url": play_url, "header": {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.host + "/",
        }}

    # ---------- 推荐 ----------

    def recommendContent(self, ids, pg):
        """基于当前分类推荐：返回全部列表第一页"""
        try:
            return self.categoryContent("all", "1", False, {})
        except Exception:
            return {"list": []}

    # ---------- 其他 ----------

    def destroy(self):
        try:
            self.extend = ""
        except Exception:
            pass

    def isVideoFormat(self, url):
        return bool(url and re.search(r'\.(m3u8|mp4|flv)', url, re.I))

    def manualVideoCheck(self):
        return False

    def liveContent(self, url):
        return ""

    def action(self, action):
        return {}