# coding: utf-8
import json
import re
from urllib.parse import urljoin, unquote
from html import unescape

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://18xx.69xx.cfd"
        self.api_url = f"{self.host}/api/api.php/provide/vod/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36",
            "Referer": self.host + "/"
        }
        self.classes = []
        self.filters = {}
        self._load_classes()

    def _load_classes(self):
        """从 class.json 加载所有分类"""
        try:
            res = self.fetch(f"{self.host}/class.json", headers=self.headers)
            if res and res.status_code == 200:
                data = json.loads(res.text)
                self.classes = [{"type_id": str(c["type_id"]), "type_name": c["type_name"]} for c in data]
                for c in self.classes:
                    self.filters[c["type_id"]] = []
        except Exception as e:
            self.log({"action": "load_classes_fail", "error": str(e)})
            # 降级：硬编码主要分类
            self.classes = [
                {"type_id": "6", "type_name": "传媒-麻豆传媒"},
                {"type_id": "7", "type_name": "传媒-精东影业"},
                {"type_id": "8", "type_name": "传媒-蜜桃传媒"},
                {"type_id": "78", "type_name": "传媒-糖心传媒"},
            ]
            for c in self.classes:
                self.filters[c["type_id"]] = []

    def getName(self):
        return "18XX"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        """首页分类与筛选 - 只保留一个虚拟分类"""
        self.classes = [{"type_id": "0", "type_name": "全部"}]
        self.filters = {"0": []}
        return {"class": self.classes, "filters": self.filters if filter else {}}
    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 使用API"""
        return self._fetch_list(ac="detail", pg=1)

    def categoryContent(self, tid, pg, filter, extend):
        """分类列表 - 使用API并客户端过滤"""
        page = pg or "1"
        return self._fetch_list(ac="detail", tid=tid, pg=page)

    def _fetch_list(self, ac="detail", tid=None, pg=1):
        """通用列表获取方法 - 移除客户端过滤，返回全站数据"""
        params = {"ac": ac, "pg": pg}
        try:
            url = f"{self.api_url}?{self._build_query(params)}"
            res = self.fetch(url, headers=self.headers, timeout=10)
            if res and res.status_code == 200:
                data = json.loads(res.text)
                if data.get("code") == 1:
                    items = data.get("list", [])
                    parsed_list = []
                    for item in items:
                        vod = {
                            "vod_id": str(item["vod_id"]),
                            "vod_name": item["vod_name"],
                            "vod_pic": item.get("vod_pic", ""),
                            "vod_remarks": item.get("vod_remarks", ""),
                            "vod_play_from": item.get("vod_play_from", ""),
                            "vod_play_url": item.get("vod_play_url", ""),
                            "vod_actor": item.get("vod_actor", ""),
                            "vod_director": item.get("vod_director", ""),
                            "vod_content": item.get("vod_content", ""),
                            "vod_year": item.get("vod_year", ""),
                            "vod_area": item.get("vod_area", ""),
                            "type_name": item.get("type_name", ""),
                        }
                        parsed_list.append(vod)
                    return {
                        "list": parsed_list,
                        "page": int(data.get("page", 1)),
                        "pagecount": int(data.get("pagecount", 1)),
                        "limit": int(data.get("limit", 20)),
                        "total": int(data.get("total", 0))
                    }
        except Exception as e:
            self.log({"action": "fetch_list_fail", "error": str(e)})
        return {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}
    def detailContent(self, ids):
        """详情页 - 使用API"""
        if not ids:
            return {"list": []}
        # 兼容 ids 为整数或列表
        if isinstance(ids, (int, str)):
            vod_id = str(ids)
        elif isinstance(ids, list) and len(ids) > 0:
            raw = ids[0]
            if isinstance(raw, (int, str)):
                vod_id = str(raw)
            else:
                vod_id = str(raw)
        else:
            return {"list": []}
        
        # 尝试从传入的ID解析JSON数据（兼容旧格式）
        if isinstance(vod_id, str) and vod_id.startswith("{"):
            try:
                vod = json.loads(vod_id)
                if vod:
                    vod["vod_id"] = vod.get("vod_id", vod_id)
                    vod["vod_play_from"] = vod.get("vod_play_from", "")
                    vod["vod_play_url"] = vod.get("vod_play_url", "")
                    return {"list": [vod]}
            except:
                pass

        # 调用详情API
        params = {"ac": "detail", "ids": vod_id}
        try:
            url = f"{self.api_url}?{self._build_query(params)}"
            res = self.fetch(url, headers=self.headers)
            if res and res.status_code == 200:
                data = json.loads(res.text)
                if data.get("code") == 1:
                    items = data.get("list", [])
                    if items:
                        return {"list": items}
        except Exception as e:
            self.log({"action": "detail_fail", "error": str(e)})
        return {"list": []}
    def searchContent(self, key, quick, pg="1"):
        """搜索 - 使用API，快速返回"""
        if not key:
            return {"list": [], "page": 1}
        params = {"ac": "search", "wd": key, "pg": pg}
        try:
            url = f"{self.api_url}?{self._build_query(params)}"
            res = self.fetch(url, headers=self.headers, timeout=10)
            if res and res.status_code == 200:
                data = json.loads(res.text)
                if data.get("code") == 1:
                    items = data.get("list", [])
                    parsed_list = []
                    for item in items:
                        vod = {
                            "vod_id": str(item.get("vod_id", "")),
                            "vod_name": item.get("vod_name", ""),
                            "vod_pic": "",  # 搜索API不返回图片
                            "vod_remarks": item.get("vod_remarks", ""),
                            "vod_play_from": item.get("vod_play_from", ""),
                            "vod_play_url": item.get("vod_play_url", ""),
                        }
                        if vod["vod_id"]:
                            parsed_list.append(vod)
                    return {"list": parsed_list, "page": int(pg)}
        except Exception as e:
            self.log({"action": "search_fail", "error": str(e)})
        return {"list": [], "page": int(pg)}
    def playerContent(self, flag, id, vipFlags):
        """播放地址"""
        if id.startswith("http") and (id.endswith(".m3u8") or id.endswith(".mp4")):
            return {"parse": 0, "url": id, "header": self.headers}
        return {"parse": 1, "url": id, "header": self.headers}

    def _build_query(self, params):
        """构建URL查询字符串"""
        return "&".join([f"{k}={v}" for k, v in params.items() if v is not None])