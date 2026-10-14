# OK影视专用爬虫插件 | 4K影视网（www.sta-cafe.com）| 基于base.spider
# 数据链路：站点为 Nuxt3 前后端分离，全部数据来自 JSON 接口 /api/show/v3/
#   /index            首页分类树(含type子分类与最新数据)
#   /type/{tid}/{pg}  分类列表(按子分类typeId分页)
#   /vod/{id}         视频详情(含播放线路与剧集m3u8直链)
#   /search/{wd}/{pg} 搜索
# 播放地址均为 m3u8 直链，无需二次解析
import sys
import re
import json
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
requests.packages.urllib3.disable_warnings()

from base.spider import Spider

class Spider(Spider):
    # ========== 插件基础配置 ==========
    def getName(self):
        return "4K影视网"

    # ========== 初始化全局配置 ==========
    def init(self, extend=""):
        super().init(extend)
        # 站点基础地址与 JSON 接口根路径
        self.site_url = "https://www.sta-cafe.com"
        self.api_base = self.site_url + "/api/show/v3"
        # 请求头（移动端UA + 站点Referer）
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
            "Referer": self.site_url + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "application/json, text/plain, */*"
        }
        # 会话保持 + 请求重试
        self.sess = requests.Session()
        self.sess.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])))
        self.sess.mount("http://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])))
        # 全局参数
        self.page_size = 18   # 站点列表每页条数
        self.total = 9999     # 模拟总条数
        # 大分类 -> 子分类映射（typeId 全局唯一，1-24）
        self.sub_map = {
            "1": [("动作片", "1"), ("喜剧片", "2"), ("爱情片", "3"), ("科幻片", "4"),
                  ("恐怖片", "5"), ("剧情片", "6"), ("战争片", "7")],
            "2": [("国产剧", "8"), ("香港剧", "9"), ("韩国剧", "10"), ("欧美剧", "11"),
                  ("台湾剧", "12"), ("日本剧", "13"), ("海外剧", "14"), ("泰国剧", "15")],
            "3": [("国产动漫", "16"), ("日韩动漫", "17"), ("欧美动漫", "18"),
                  ("港台动漫", "19"), ("海外动漫", "20")],
            "4": [("大陆综艺", "21"), ("港台综艺", "22"), ("日韩综艺", "23"), ("欧美综艺", "24")],
        }

    # ========== 通用请求方法：GET JSON，返回data字段 ==========
    def fetch(self, url, timeout=10):
        try:
            res = self.sess.get(url, headers=self.headers, timeout=timeout, verify=False)
            if res and res.ok:
                data = res.json()
                if data.get("code") == 0:
                    return data.get("data")
            return None
        except Exception as e:
            return None

    # ========== 统一视频项解析（列表/搜索共用） ==========
    def _parse_vod(self, item):
        vod_pic = item.get("vodPic") or ""
        if vod_pic.startswith("//"):
            vod_pic = "https:" + vod_pic
        elif vod_pic and not vod_pic.startswith(("http://", "https://")):
            vod_pic = self.site_url + (vod_pic if vod_pic.startswith("/") else "/" + vod_pic)
        return {
            "vod_id": str(item.get("vodId", "")),
            "vod_name": (item.get("vodName") or "").strip(),
            "vod_pic": vod_pic,
            "vod_remarks": item.get("vodLastRemarks") or ""
        }

    # ========== 筛选解析辅助 ==========
    # ========== 首页分类接口 ==========
    def homeContent(self, filter):
        cate_list = [{"type_name": cate_name, "type_id": cate_id} for cate_id, cate_name in [("1", "电影"), ("2", "电视剧"), ("3", "动漫"), ("4", "综艺")]]
        return {"class": cate_list}

    # ========== 分类列表接口 ==========
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        video_list = []
        pagecount = pg
        total_page = None
        if tid == "recent":
            return {
                "list": [],
                "page": 1,
                "pagecount": 1,
                "limit": self.page_size,
                "total": 0
            }
        else:
            # 大分类直接映射到默认子分类（如电影->动作片），保证列表有数据
            sub_tid = self.sub_map[tid][0][1] if tid in self.sub_map else tid
            data = self.fetch(self.api_base + "/type/{0}/{1}".format(sub_tid, pg))
            if data:
                for item in data.get("vod_recent") or []:
                    video_list.append(self._parse_vod(item))
                tp = data.get("total_page")
                if isinstance(tp, int) and tp > 0:
                    total_page = tp
        # 总页数：优先真实total_page，否则沿用模板逻辑
        if total_page is not None:
            pagecount = total_page if total_page >= pg else pg
        else:
            pagecount = pg + 1 if len(video_list) else pg
        return {
            "list": video_list,
            "page": pg,
            "pagecount": pagecount,
            "limit": self.page_size,
            "total": self.total
        }

    # ========== 视频详情接口 ==========
    def detailContent(self, ids):
        vod_id = ids[0] if ids else ""
        if not vod_id:
            return {"list": [{"vod_name": "视频ID为空"}]}
        data = self.fetch(self.api_base + "/vod/{0}".format(vod_id))
        if not data:
            return {"list": [{"vod_id": vod_id, "vod_name": "视频详情解析失败"}]}
        # 播放线路与地址：vod_play 列表，每条含 collectSource.webName(线路名) 与 vodPlayUrl(集名$地址#...)
        play_from_list = []
        play_url_list = []
        for p in data.get("vod_play") or []:
            src = p.get("collectSource") or {}
            play_from_list.append(src.get("webName") or "线路")
            play_url_list.append(p.get("vodPlayUrl") or "")
        detail_info = {
            "vod_id": str(data.get("vodId", vod_id)),
            "vod_name": data.get("vodName") or "未知名称",
            "vod_pic": data.get("vodPic") or "",
            "vod_remarks": data.get("vodLastRemarks") or "",
            "type_name": (data.get("type") or {}).get("typeName") or "",
            "vod_year": data.get("vodYear") or "",
            "vod_area": data.get("vodArea") or "",
            "vod_actor": data.get("vodActor") or "",
            "vod_director": data.get("vodDirector") or "",
            "vod_content": (data.get("vodContent") or data.get("vodBlurb") or "").strip(),
            "vod_play_from": "$$$".join(play_from_list),
            "vod_play_url": "$$$".join(play_url_list)
        }
        return {"list": [detail_info]}

    # ========== 搜索接口 ==========
    def searchContent(self, key, quick, pg=1):
        pg = int(pg) if str(pg).isdigit() else 1
        video_list = []
        pagecount = pg
        total_page = None
        data = self.fetch(self.api_base + "/search/{0}/{1}".format(requests.utils.quote(key), pg))
        if data:
            for item in data.get("vods") or []:
                video_list.append(self._parse_vod(item))
            tp = data.get("total_page")
            if isinstance(tp, int) and tp > 0:
                total_page = tp
        if total_page is not None:
            pagecount = total_page if total_page >= pg else pg
        else:
            pagecount = pg + 1 if len(video_list) else pg
        return {
            "list": video_list,
            "page": pg,
            "pagecount": pagecount,
            "limit": self.page_size,
            "total": len(video_list) if len(video_list) < self.total else self.total
        }

    # ========== 播放解析接口 ==========
    def playerContent(self, flag, id, vipFlags):
        # 拆分「节点名$地址」
        play_url = id.split("$")[1] if "$" in id else id
        if not play_url:
            return {"parse": 0, "url": "", "header": self.headers}
        # 站点播放地址均为 m3u8 直链，无需二次解析
        return {
            "parse": 0,
            "url": play_url,
            "header": self.headers
        }

# ========== 无额外入口（OK影视自动识别Spider类） ==========