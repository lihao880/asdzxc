# -*- coding: utf-8 -*-
# 站点信息
# 主域名: https://chineseav.xyz
# API域名: https://chavapi.freeaav.xyz
# API Token: chineseav_2026_secret
# 内容类型: 国产AV视频聚合
# 来源: https://chineseav.xyz
# 最后验证: 2026-08-31
# m3u8结构摘要: 视频为mp4直链，无m3u8广告过滤需求

import json
import urllib.parse
import re
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.api_base = "https://chavapi.freeaav.xyz"
        self.api_token = "chineseav_2026_secret"
        self.site_name = "強國AV"
        self.host = "https://chineseav.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-API-Token": self.api_token,
            "Accept": "application/json"
        }
        # 硬编码分类（来自 /api/categories 接口）
        self.classes = [
            {"type_id": "91制片厂", "type_name": "91制片厂"},
            {"type_id": "Hong Kong Doll", "type_name": "Hong Kong Doll"},
            {"type_id": "Pussy Hunter", "type_name": "Pussy Hunter"},
            {"type_id": "SA国际传媒", "type_name": "SA国际传媒"},
            {"type_id": "SWAG Live", "type_name": "SWAG Live"},
            {"type_id": "Swag A片", "type_name": "Swag A片"},
            {"type_id": "亞裔素人網紅", "type_name": "亞裔素人網紅"},
            {"type_id": "印度婊子", "type_name": "印度婊子"},
            {"type_id": "吴梦梦频道", "type_name": "吴梦梦频道"},
            {"type_id": "國產AV", "type_name": "國產AV"},
            {"type_id": "大象传媒", "type_name": "大象传媒"},
            {"type_id": "天美传媒", "type_name": "天美传媒"},
            {"type_id": "微密圈传媒", "type_name": "微密圈传媒"},
            {"type_id": "星空无限传媒", "type_name": "星空无限传媒"},
            {"type_id": "杏吧原创", "type_name": "杏吧原创"},
            {"type_id": "果冻传媒", "type_name": "果冻传媒"},
            {"type_id": "泰国婊子", "type_name": "泰国婊子"},
            {"type_id": "皇家华人", "type_name": "皇家华人"},
            {"type_id": "精东传媒", "type_name": "精东传媒"},
            {"type_id": "色控工作室", "type_name": "色控工作室"},
            {"type_id": "菲律宾婊子", "type_name": "菲律宾婊子"},
            {"type_id": "蜜桃传媒", "type_name": "蜜桃传媒"},
            {"type_id": "韩国婊子", "type_name": "韩国婊子"},
            {"type_id": "香蕉视频", "type_name": "香蕉视频"},
            {"type_id": "麻豆传媒", "type_name": "麻豆传媒"},
        ]
        # filters - 简单站无筛选
        self.filters = {}

    def getName(self):
        return self.site_name

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 获取最新视频列表"""
        try:
            result = self._fetch_api("/api/videos", {"page": "1", "sort": "newest"})
            if result and "data" in result:
                items = result["data"][:20]
                return {"list": self._parse_videos(items)}
            return {"list": []}
        except Exception as e:
            self.log({"action": "homeVideoContent_error", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        """分类列表 - 按频道/分类获取视频"""
        try:
            page = str(pg) if pg else "1"
            # 分类名直接作为频道名请求
            url = "/api/videos/by-channels"
            params = {
                "channels": tid,
                "page": page,
                "sort": "newest"
            }
            result = self._fetch_api(url, params)
            if result and "data" in result:
                items = result["data"]
                # 如果返回为空，说明没有更多数据
                if not items:
                    return {"list": [], "page": int(page), "pagecount": int(page), "limit": 20, "total": 0}
                # 尝试从响应中获取总数，如果没有则估算
                total = result.get("total", 9999)
                # 计算总页数：如果每页20条，用total/20，但API可能返回全部数据
                # 实际上这个API返回的是所有数据，没有分页信息，我们用返回的数据量判断
                pagecount = int(page) + 1  # 至少给一个下一页，让用户能继续翻
                # 但如果数据不足20条，说明是最后一页
                if len(items) < 20:
                    pagecount = int(page)
                return {
                    "list": self._parse_videos(items),
                    "page": int(page),
                    "pagecount": pagecount,
                    "limit": 20,
                    "total": total if isinstance(total, int) else 9999
                }
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        except Exception as e:
            self.log({"action": "categoryContent_error", "error": str(e)})
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 20, "total": 0}
    def detailContent(self, ids):
        """视频详情"""
        try:
            if not ids:
                return {"list": []}
            vid = ids[0]
            result = self._fetch_api(f"/api/video/{vid}")
            if result:
                data = result
                # 构建播放地址
                video_url = data.get("video_url", "")
                title = data.get("title", "未知标题")
                thumbnail = data.get("thumbnail", "")
                duration = data.get("duration", "")
                views = data.get("views", 0)
                categories = data.get("categories", "")
                description = data.get("description", "")

                play_from = "播放"
                if video_url:
                    if video_url.endswith(".m3u8"):
                        play_url_str = f"播放${video_url}"
                    else:
                        play_url_str = f"播放${video_url}"
                else:
                    play_url_str = ""

                vod = {
                    "vod_id": str(vid),
                    "vod_name": title,
                    "vod_pic": thumbnail,
                    "vod_remarks": f"时长: {self._format_duration(duration)} | 播放: {views}",
                    "vod_content": description or categories,
                    "vod_play_from": play_from,
                    "vod_play_url": play_url_str,
                }
                return {"list": [vod]}
            return {"list": []}
        except Exception as e:
            self.log({"action": "detailContent_error", "error": str(e)})
            return {"list": []}

    def searchContent(self, key, quick=False, pg="1"):
        """搜索"""
        try:
            if not key:
                return {"list": [], "page": 1, "pagecount": 1, "total": 0}
            page = str(pg) if pg else "1"
            url = "/api/search"
            params = {"q": key}
            result = self._fetch_api(url, params)
            if result and "data" in result:
                items = result["data"]
                return {
                    "list": self._parse_videos(items),
                    "page": int(page),
                    "pagecount": 999,
                    "total": 9999
                }
            return {"list": [], "page": int(page), "pagecount": 1, "total": 0}
        except Exception as e:
            self.log({"action": "searchContent_error", "error": str(e)})
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "total": 0}

    def playerContent(self, flag, id, vipFlags=None):
        """播放"""
        if not id:
            return {"parse": 1, "url": ""}

        # 如果是m3u8或mp4直链
        if id.startswith("http"):
            if ".m3u8" in id or ".mp4" in id:
                headers = {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/"
                }
                return {"parse": 0, "url": id, "header": headers}

        # 如果id是数字，尝试通过detail获取真实地址
        if id.isdigit():
            try:
                result = self._fetch_api(f"/api/video/{id}")
                if result and result.get("video_url"):
                    video_url = result["video_url"]
                    headers = {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": self.host + "/"
                    }
                    return {"parse": 0, "url": video_url, "header": headers}
            except Exception:
                pass

        # 降级嗅探
        return {"parse": 1, "url": id, "header": {"User-Agent": self.headers["User-Agent"]}}

    def recommendContent(self, ids, pg=None):
        """相关推荐"""
        try:
            if not ids:
                return {"list": []}
            # 基于分类推荐同分类视频
            vid = ids[0]
            result = self._fetch_api(f"/api/video/{vid}")
            if result:
                categories = result.get("categories", "")
                if categories:
                    url = "/api/videos/by-category"
                    params = {"cat": categories, "page": "1", "sort": "views"}
                    rec_result = self._fetch_api(url, params)
                    if rec_result and "data" in rec_result:
                        items = rec_result["data"][:10]
                        return {"list": self._parse_videos(items)}
            return {"list": []}
        except Exception as e:
            self.log({"action": "recommendContent_error", "error": str(e)})
            return {"list": []}

    def localProxy(self, params):
        """本地代理 - 图片/视频透传"""
        # 此站视频为直链，不需要代理
        return [404, "text/plain", b"Not Found"]

    def destroy(self):
        """释放资源"""
        pass

    # ==================== 私有方法 ====================

    def _fetch_api(self, endpoint, params=None):
        """调用API"""
        url = self.api_base.rstrip("/") + endpoint
        if params:
            url += "?" + urllib.parse.urlencode(params)
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if resp and resp.status_code == 200:
                try:
                    return json.loads(resp.text)
                except:
                    return None
            return None
        except Exception as e:
            self.log({"action": "fetch_api_error", "url": url, "error": str(e)})
            return None

    def _parse_videos(self, items):
        """解析视频列表"""
        videos = []
        for item in items:
            vid = item.get("id") or item.get("rowid")
            title = item.get("title", "")
            thumbnail = item.get("thumbnail", "")
            duration = item.get("duration", "")
            views = item.get("views", 0)
            video_url = item.get("video_url", "")

            if not vid or not title:
                continue

            # 构建vod_id - 使用视频ID
            vod_id = str(vid)

            # 备注：时长和播放量
            remarks = []
            if duration:
                remarks.append(self._format_duration(duration))
            if views:
                remarks.append(f"播放:{views}")
            vod_remarks = " | ".join(remarks) if remarks else ""

            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": thumbnail,
                "vod_remarks": vod_remarks,
            })
        return videos

    def _format_duration(self, seconds):
        """格式化时长"""
        try:
            secs = int(seconds)
            if secs < 60:
                return f"{secs}s"
            elif secs < 3600:
                mins = secs // 60
                rem = secs % 60
                return f"{mins}m{rem}s" if rem > 0 else f"{mins}m"
            else:
                hours = secs // 3600
                mins = (secs % 3600) // 60
                return f"{hours}h{mins}m"
        except:
            return str(seconds)

    def _parse_extend(self, extend):
        """解析extend参数（多格式兼容）"""
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
            for part in extend.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    result[k.strip()] = v.strip()
            return result
        return {}