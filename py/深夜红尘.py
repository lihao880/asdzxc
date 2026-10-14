# coding: utf-8
"""
站点名称：深夜红尘
主域名：https://www.hongchensp.sbs
备用域名：shenyesp.vip
内容类型：成人影视
特殊说明：MacCMS风格HTML站，播放地址嵌入player_aaaa变量，m3u8无广告特征
验证时间：2026-09-06
来源：用户提供

m3u8结构摘要：
- 锚点来源：m3u8_url目录
- 广告目录：无
- 图片流伪装：否
- 处理方式：直接返回原始直链，不经过localProxy
"""
import json
import re
from urllib.parse import urljoin, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.hongchensp.sbs"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类列表 - 从首页导航提取
        self.classes = [
            {"type_id": "23", "type_name": "国产精品"},
            {"type_id": "1", "type_name": "国产传媒"},
            {"type_id": "2", "type_name": "网红直播"},
            {"type_id": "3", "type_name": "大秀视频"},
            {"type_id": "4", "type_name": "黑料网爆"},
            {"type_id": "5", "type_name": "精品探花"},
            {"type_id": "6", "type_name": "制服诱惑"},
            {"type_id": "7", "type_name": "反差母狗"},
            {"type_id": "8", "type_name": "自慰系列"},
            {"type_id": "9", "type_name": "中文字幕"},
            {"type_id": "10", "type_name": "熟女少妇"},
            {"type_id": "11", "type_name": "教师学生"},
            {"type_id": "13", "type_name": "明星换脸"},
            {"type_id": "16", "type_name": "精品欧美"},
            {"type_id": "20", "type_name": "动漫专区"},
            {"type_id": "22", "type_name": "精品日韩"},
        ]
        # 筛选器 - 站点无筛选功能
        self.filters = {str(c["type_id"]): [] for c in self.classes}
        # m3u8无广告特征，直接返回原始直链
        self.NEED_CLEAN = False

    def getName(self):
        return "深夜红尘"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 从首页抓取推荐列表
        try:
            resp = self.fetch(self.host + "/", headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            return self._parse_home_list(html)
        except Exception as e:
            self.log({"homeVideoContent": "error", "msg": str(e)})
            return {"list": []}

    def _parse_home_list(self, html):
        """解析首页推荐列表"""
        items = []
        # 使用正则提取 video-item
        pattern = r'<article[^>]*class="[^"]*video-item[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h3[^>]*class="[^"]*video-item__title[^"]*"[^>]*>([^<]+)</h3>'
        matches = re.findall(pattern, html, re.S)
        for href, pic, title in matches:
            if not href or not title:
                continue
            vod_id = href.split("/")[-1].split(".")[0] if "/play/" in href else href
            items.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": pic if pic.startswith("http") else urljoin(self.host, pic),
                "vod_remarks": ""
            })
        return {"list": items[:20]}  # 取前20个

    @staticmethod
    def _norm_ids(ids):
        """法则35：ids归一化"""
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            try:
                ids = ids.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        return str(ids).strip()

    @staticmethod
    def _parse_extend(extend):
        """extend参数多格式兼容"""
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except:
                pass
            result = {}
            for part in extend.split(','):
                if '=' in part:
                    k, v = part.split('=', 1)
                    result[k.strip()] = v.strip()
            return result
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = resp.text
            items, total_pages = self._parse_category_list(html, tid)
            return {
                "list": items,
                "page": int(page),
                "pagecount": total_pages or 1,
                "limit": 20,
                "total": len(items)
            }
        except Exception as e:
            self.log({"categoryContent": "error", "tid": tid, "pg": pg, "msg": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def _parse_category_list(self, html, tid):
        """解析分类列表页"""
        items = []
        # 提取视频项 - 修正vod_id提取
        pattern = r'<article[^>]*class="[^"]*video-item[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h3[^>]*class="[^"]*video-item__title[^"]*"[^>]*>([^<]+)</h3>'
        matches = re.findall(pattern, html, re.S)
        for href, pic, title in matches:
            if not href or not title:
                continue
            # 从href中提取真实的vod_id - 格式: /index.php/vod/play/id/6575/sid/1/nid/1.html
            id_match = re.search(r'/id/(\d+)', href)
            if id_match:
                vod_id = id_match.group(1)
            else:
                vod_id = href.split("/")[-1].split(".")[0] if "/play/" in href else href
            # 过滤广告
            if "qq.com" in href or "ads" in pic:
                continue
            items.append({
                "vod_id": vod_id,
                "vod_name": title.strip(),
                "vod_pic": pic if pic.startswith("http") else urljoin(self.host, pic),
                "vod_remarks": ""
            })
        # 提取总页数
        total_pages = 1
        page_pattern = r'<a[^>]*class="[^"]*a_page_info[^"]*"[^>]*href="[^"]*/page/(\d+)\.html[^"]*"[^>]*>\d+</a>'
        pages = re.findall(page_pattern, html)
        if pages:
            total_pages = max(int(p) for p in pages)
        return items, total_pages
    def detailContent(self, ids):
        """法则35：详情页提取管线"""
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}

        # 如果ids包含播放地址（从列表阶段打包）
        if "|$|" in vid:
            parts = vid.split("|$|")
            if len(parts) >= 5 and parts[4]:
                return {"list": [{
                    "vod_id": vid,
                    "vod_name": parts[1] if len(parts) > 1 else "未知标题",
                    "vod_pic": parts[2] if len(parts) > 2 else "",
                    "vod_remarks": parts[3] if len(parts) > 3 else "",
                    "vod_content": parts[3] if len(parts) > 3 else "",
                    "vod_play_from": "直链",
                    "vod_play_url": f"播放${parts[4]}"
                }]}

        # 构建详情页URL
        detail_url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        try:
            resp = self.fetch(detail_url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return self._skeleton(vid)
            html = resp.text
            return self._parse_detail(html, vid)
        except Exception as e:
            self.log({"detailContent": "error", "vid": vid, "msg": str(e)})
            return self._skeleton(vid)

    def _parse_detail(self, html, vid):
        """解析详情页"""
        title = "未知标题"
        pic = ""
        play_url = ""

        # 提取标题
        title_match = re.search(r'<h1[^>]*class="[^"]*video-detail__title[^"]*"[^>]*>(.*?)</h1>', html, re.S)
        if title_match:
            title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()

        # 提取player_aaaa中的播放地址（L2/L3层）
        var_pattern = r'var\s+player_aaaa\s*=\s*(\{.*?\});'
        var_match = re.search(var_pattern, html, re.S)
        if var_match:
            try:
                raw = var_match.group(1)
                # 尝试JSON解析
                data = json.loads(raw)
                play_url = data.get("url", "")
                if play_url:
                    play_url = play_url.replace("\\/", "/")
            except:
                # loose解析
                pass

        # 如果player_aaaa未取到，尝试全文正则
        if not play_url:
            url_match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
            if url_match:
                play_url = url_match.group(1).replace("\\/", "/")

        # 提取封面图
        pic_match = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
        if pic_match:
            pic = pic_match.group(1)

        if not play_url:
            return self._skeleton(vid, title, pic)

        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${play_url}"
        }]}

    def _skeleton(self, vid, title="", pic=""):
        """法则35：详情兜底骨架"""
        pid = str(vid).split("|$|")[0].replace("$", "|")
        return {"list": [{
            "vod_id": vid,
            "vod_name": title or "未知标题",
            "vod_pic": pic or "",
            "vod_remarks": "解析中",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${pid}"
        }]}

    def searchContent(self, key, quick, pg="1"):
        # 该站搜索功能未测试，返回空列表
        return {"list": [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        """播放地址提取：直链优先"""
        ua = self.headers.get("User-Agent", "")
        if not id:
            return {"parse": 1, "url": "", "header": {"User-Agent": ua}}

        play_url = str(id).strip()

        # L1：直链识别
        if play_url.startswith("http") and (".m3u8" in play_url or ".mp4" in play_url):
            # 无广告特征，直接返回原始直链
            return {"parse": 0, "url": play_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}

        # 如果id是相对路径，补全
        if play_url.startswith("/"):
            play_url = urljoin(self.host, play_url)

        # 请求播放页提取（L2-L5）
        try:
            resp = self.fetch(play_url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"parse": 1, "url": play_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}
            html = resp.text

            # L2：播放器变量
            var_pattern = r'var\s+player_aaaa\s*=\s*(\{.*?\});'
            var_match = re.search(var_pattern, html, re.S)
            if var_match:
                try:
                    raw = var_match.group(1)
                    data = json.loads(raw)
                    m3u8 = data.get("url", "")
                    if m3u8:
                        m3u8 = m3u8.replace("\\/", "/")
                        return {"parse": 0, "url": m3u8, "header": {"User-Agent": ua, "Referer": self.host + "/"}}
                except:
                    pass

            # L5：全文正则兜底
            url_match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
            if url_match:
                m3u8 = url_match.group(1).replace("\\/", "/")
                return {"parse": 0, "url": m3u8, "header": {"User-Agent": ua, "Referer": self.host + "/"}}

            # 降级
            self.log({"playerContent": "fallback", "id": id, "page": play_url})
            return {"parse": 1, "url": play_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}
        except Exception as e:
            self.log({"playerContent": "error", "id": id, "msg": str(e)})
            return {"parse": 1, "url": play_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass


# 本地测试入口
if __name__ == "__main__":
    s = Spider()
    s.init()
    print("=== homeContent ===")
    print(json.dumps(s.homeContent(False), ensure_ascii=False, indent=2))
    print("=== homeVideoContent ===")
    print(json.dumps(s.homeVideoContent(), ensure_ascii=False, indent=2))
    print("=== categoryContent tid=23 pg=1 ===")
    print(json.dumps(s.categoryContent("23", "1", False, {}), ensure_ascii=False, indent=2))
    print("=== detailContent id=6575 ===")
    print(json.dumps(s.detailContent(["6575"]), ensure_ascii=False, indent=2))
    print("=== playerContent id=m3u8 ===")
    print(json.dumps(s.playerContent("play", "https://jipinvipplay.com/20260528/t066KSRN/index.m3u8", None), ensure_ascii=False, indent=2))