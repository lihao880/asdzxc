# coding: utf-8
# 站点: 番号吧 (fanhaob.cc)
# 类型: 成人聚合站
# 主域名: https://fanhaob.cc
# 备用域名: 待补充
# 内容类型: 视频
# 特殊说明: 播放地址需动态获取，使用 parse:1 降级
# 最后验证时间: 2026-08-31
# 来源: 用户提供

import json
import re
import html
import urllib.parse
import concurrent.futures
from base.spider import Spider


class Spider(Spider):
    def __init__(self):
        self.host = "https://fanhaob.cc"
        self.ua = "Mozilla/5.0 (Linux; Android 14; 22127RK46C Build/UKQ1.230804.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.0.0 Mobile Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/"
        }

        # 分类硬编码
        self.classes = [
            {"type_id": "cate8", "type_name": "🚨 下药迷奸×爆操强奸"},
            {"type_id": "cate9", "type_name": "🔥 NTR绿帽狂欢"},
            {"type_id": "cate10", "type_name": "🚨 重磅黑料"},
            {"type_id": "cate11", "type_name": "🏳️‍🌈 顶级GAY片"},
            {"type_id": "cate12", "type_name": "♠️ 媚黑贱犬"},
            {"type_id": "cate13", "type_name": "🤰 孕妇发情日记"},
            {"type_id": "cate14", "type_name": "🐻 兽交重口味"},
            {"type_id": "cate22", "type_name": "👗 制服"},
            {"type_id": "cate23", "type_name": "👅 白虎"},
            {"type_id": "cate24", "type_name": "🌸 校花"},
            {"type_id": "cate25", "type_name": "🍌 学妹"},
            {"type_id": "cate26", "type_name": "👠 御姐"},
            {"type_id": "cate27", "type_name": "🐶 反差婊"},
            {"type_id": "cate28", "type_name": "🎀 萝莉"},
            {"type_id": "cate29", "type_name": "👙 巨乳"},
            {"type_id": "cate30", "type_name": "🫦 女同"},
            {"type_id": "cate32", "type_name": "糖心Vlog"},
            {"type_id": "cate33", "type_name": "SWAG"},
            {"type_id": "cate34", "type_name": "大象传媒"},
            {"type_id": "cate35", "type_name": "麻豆传媒"},
            {"type_id": "cate36", "type_name": "天美传媒"},
            {"type_id": "cate37", "type_name": "星空传媒"},
            {"type_id": "cate38", "type_name": "QQ传媒×91制片厂"},
            {"type_id": "cate39", "type_name": "蜜桃传媒"},
            {"type_id": "cate40", "type_name": "皇家华人"},
            {"type_id": "cate46", "type_name": "【Top】直播"},
            {"type_id": "cate47", "type_name": "【Stripchat】直播"},
            {"type_id": "cate53", "type_name": "【投稿区】探花"},
            {"type_id": "cate54", "type_name": "【招嫖会所】探花"},
            {"type_id": "cate55", "type_name": "【外围女郎】探花"},
            {"type_id": "cate68", "type_name": "母子乱伦"},
            {"type_id": "cate69", "type_name": "淫乱兄妹"},
            {"type_id": "cate70", "type_name": "公公儿媳"},
            {"type_id": "cate76", "type_name": "精选动漫"},
            {"type_id": "cate77", "type_name": "泡面番"},
            {"type_id": "cate80", "type_name": "经典里番"},
            {"type_id": "cate86", "type_name": "推荐爆款热播"},
            {"type_id": "cate87", "type_name": "综合推荐-字幕区"},
            {"type_id": "cate88", "type_name": "精品无码Fc2"},
            {"type_id": "cate90", "type_name": "高清无码-人妻斩"},
            {"type_id": "cate91", "type_name": "巨乳&肥臀"},
            {"type_id": "cate92", "type_name": "JK制服"},
            {"type_id": "cate106", "type_name": "Kink欧美"},
            {"type_id": "cate107", "type_name": "Blacked欧美"},
            {"type_id": "cate108", "type_name": "Vixen欧美"},
            {"type_id": "cate109", "type_name": "Tushy欧美"},
            {"type_id": "cate124", "type_name": "国风3D"},
            {"type_id": "cate125", "type_name": "中文字幕3D"},
            {"type_id": "cate128", "type_name": "守望先锋3D"},
            {"type_id": "cate133", "type_name": "斗罗大陆3D"},
            {"type_id": "cate136", "type_name": "原神系列3D"},
        ]

        self.filters = {}

    def getName(self):
        return "番号吧"

    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html_text = self._req_html("/")
        if not html_text:
            return {"list": []}
        return {"list": self._parse_list(html_text, "video")}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        # 添加随机参数绕过缓存
        import time
        cache_buster = int(time.time() * 1000)
        url = f"/category/{tid}/{page}/?t={cache_buster}"
        html_text = self._req_html(url)
        if not html_text:
            return {"list": [], "page": int(page), "pagecount": int(page), "limit": 20, "total": 0}

        items = self._parse_list(html_text, "video")
        pagecount = self._parse_pagecount(html_text, page)

        return {
            "list": items,
            "page": int(page),
            "pagecount": max(pagecount, int(page)),
            "limit": 20,
            "total": 9999
        }
    def detailContent(self, ids):
        raw = ids[0]
        if "|" in raw:
            vid = raw.split("|")[0]
        else:
            vid = raw

        if "/video/" in vid:
            url = vid
        else:
            url = f"{self.host}/video/{vid}/"

        html_text = self._req_html(url)
        if not html_text:
            return {"list": []}

        soup = self._get_soup(html_text)

        title_node = soup.select_one("h1") or soup.select_one("title")
        vod_name = self._clean_text(title_node.get_text()) if title_node else "未知"

        pic_node = soup.select_one("meta[property='og:image']")
        vod_pic = pic_node.get("content", "") if pic_node else ""

        desc_node = soup.select_one("meta[name='description']")
        vod_content = desc_node.get("content", "") if desc_node else ""

        tags = []
        for tag in soup.select(".tp5-tag-item span"):
            t = self._clean_text(tag.get_text())
            if t:
                tags.append(t)
        vod_remarks = ", ".join(tags) if tags else ""

        # 从 __ARCHIVE_PLAYER__ 提取播放地址
        play_url = ""
        match = re.search(r'window\.__ARCHIVE_PLAYER__\s*=\s*({[^;]+});', html_text)
        if match:
            try:
                player_data = json.loads(match.group(1))
                raw_path = player_data.get("rawPath", "")
                cdn_line = player_data.get("cdnLine", "")
                if raw_path:
                    # 优先使用 cdnLine + rawPath
                    if cdn_line and raw_path.startswith("/"):
                        play_url = cdn_line + raw_path
                    elif raw_path.startswith("/"):
                        play_url = self.host + raw_path
                    else:
                        play_url = raw_path
            except:
                pass

        if not play_url:
            # 降级：使用详情页 URL 让播放器嗅探
            play_url = url

        return {
            "list": [{
                "vod_id": raw,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
                "vod_content": vod_content,
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}"
            }]
        }
    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": [], "page": int(pg)}

        q = urllib.parse.quote(key)
        html_text = self._req_html(f"/search/{q}/{pg}")
        if not html_text:
            return {"list": [], "page": int(pg)}

        items = self._parse_list(html_text, "video")
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        # m3u8 直链，返回 parse:0
        if id.startswith("http") and ".m3u8" in id:
            return {
                "parse": 0,
                "url": id,
                "header": {
                    "User-Agent": self.ua,
                    "Referer": self.host + "/",
                    "Accept": "application/vnd.apple.mpegurl, */*"
                }
            }

        # 如果是播放页 URL，降级给 WebView 嗅探
        if id.startswith("http"):
            return {
                "parse": 1,
                "url": id,
                "header": {
                    "User-Agent": self.ua,
                    "Referer": self.host + "/",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
            }

        return {"parse": 0, "url": id, "header": {}}
    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass

    def _req_html(self, path):
        url = path if path.startswith("http") else self.host + path
        try:
            res = self.fetch(url, headers=self.headers, timeout=10)
            if res and res.status_code == 200:
                return res.text
        except Exception as e:
            self.log({"action": "fetch_error", "url": url, "error": str(e)})
        return ""

    def _get_soup(self, html_text):
        try:
            from bs4 import BeautifulSoup
            return BeautifulSoup(html_text, "html.parser")
        except:
            return None

    def _clean_text(self, text):
        if not text:
            return ""
        return re.sub(r"\s+", " ", html.unescape(str(text))).strip()

    def _parse_pagecount(self, html_text, pg):
        soup = self._get_soup(html_text)
        if not soup:
            return int(pg)
        pagecount = int(pg)
        # 从分页链接中提取最大页码
        for a in soup.select("a.tp5-page-link"):
            href = a.get("href", "")
            # 匹配 /category/cate8/79/ 格式
            match = re.search(r"/category/[^/]+/(\d+)/", href)
            if match:
                num = int(match.group(1))
                if num > pagecount:
                    pagecount = num
        return pagecount
    def _parse_list(self, html_text, default_kind):
        soup = self._get_soup(html_text)
        if not soup:
            return []

        result = []
        for item in soup.select(".tp5-section-content__item a, .video-item a, .post a, .vod-item a"):
            href = item.get("href", "")
            if not href or "/video/" not in href:
                continue

            vid_match = re.search(r"/video/(\d+)/", href)
            if not vid_match:
                continue
            vod_id = vid_match.group(1)

            title_node = item.select_one("h3") or item
            title = self._clean_text(title_node.get_text()) if title_node else ""

            img = item.select_one("img")
            pic = img.get("data-src") or img.get("src", "") if img else ""
            if pic and not pic.startswith("http"):
                pic = self.host + pic

            duration_node = item.select_one(".tp5-duration")
            remark = self._clean_text(duration_node.get_text()) if duration_node else ""

            result.append({
                "vod_id": str(vod_id),
                "vod_name": title or f"视频{vod_id}",
                "vod_pic": pic,
                "vod_remarks": remark
            })

        return result