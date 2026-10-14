# coding: utf-8
"""
站点名称：爱妃视频
站点域名：https://sttjg.com（主站），备用域名见 /addr/show.js
站点类型：JS 注入型 SPA（所有数据在 loading() 函数中）
内容类型：成人视频
数据提取方式：从页面源码中提取 loading({...}) 中的 JSON 数据
解密方式：分段 Base32 解码（parseInt(part, 32) -> Unicode 码点）
验证时间：2026-09-02
"""
import json
import re
from urllib.parse import urljoin

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://sttjg.com"
        self.site_name = "爱妃视频"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类列表（从首页 category 中提取并解码）
        self.classes = [
            {"type_id": "1", "type_name": "国产视频"},
            {"type_id": "2", "type_name": "美女正妹"},
            {"type_id": "3", "type_name": "传媒映画"},
            {"type_id": "4", "type_name": "国产探花"},
            {"type_id": "5", "type_name": "无码精选"},
            {"type_id": "6", "type_name": "中文字幕"},
            {"type_id": "7", "type_name": "欧美专区"},
            {"type_id": "8", "type_name": "自拍偷拍"},
            {"type_id": "9", "type_name": "强制中出"},
            {"type_id": "10", "type_name": "吃瓜黑料"},
            {"type_id": "11", "type_name": "明星换脸"},
            {"type_id": "12", "type_name": "人气女优"},
            {"type_id": "13", "type_name": "剧情解说"},
            {"type_id": "14", "type_name": "美女直播"},
            {"type_id": "15", "type_name": "伦理电影"},
            {"type_id": "16", "type_name": "动漫番剧"},
        ]
        # filters（该站无筛选功能）
        self.filters = {str(i): [] for i in range(1, 17)}
        # 缓存域名
        self._cached_host = self.host

    def getName(self):
        return self.site_name

    def getDependence(self):
        return []

    def init(self, extend=""):
        # init 零网络依赖
        pass

    def _decode_name(self, encoded):
        """
        解码混淆名称
        格式：分段用 "-" 连接，每段是 base32 编码的数字
        例如 "LNT-JL7-12E6-164H" -> 每段用 parseInt(part, 32) 解码为 Unicode 码点
        """
        if not encoded:
            return ""
        result = []
        for part in encoded.split('-'):
            if part:
                try:
                    code_point = int(part, 32)
                    # 只保留有效的 Unicode 字符
                    if 0x4E00 <= code_point <= 0x9FFF or 0x3400 <= code_point <= 0x4DBF:
                        result.append(chr(code_point))
                    else:
                        # 非中文字符范围也尝试转换，但可能包含数字/字母
                        result.append(chr(code_point))
                except ValueError:
                    result.append(part)
        return ''.join(result)

    def _fetch_page_data(self, url):
        """获取页面并提取 loading() 中的 JSON 数据"""
        try:
            resp = self.fetch(url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                self.log({"error": f"fetch failed: {resp.status_code}"})
                return None
            html = resp.text
            # 提取 loading({...}) 中的 JSON
            match = re.search(r'loading\(({.*?})\);', html, re.DOTALL)
            if not match:
                self.log({"error": "loading() not found"})
                return None
            json_str = match.group(1)
            return json.loads(json_str)
        except Exception as e:
            self.log({"error": f"_fetch_page_data error: {str(e)}"})
            return None

    def _parse_video_list(self, data_list, image_base):
        """解析视频列表数据"""
        result = []
        for item in data_list:
            vid = str(item.get("id", ""))
            name_encoded = item.get("name", "")
            name = self._decode_name(name_encoded) or name_encoded
            src = item.get("src", "")
            pic = urljoin(image_base, src) if src else ""
            result.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": ""
            })
        return result

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐"""
        data = self._fetch_page_data(self.host + "/")
        if not data:
            return {"list": []}
        archives = data.get("archives", [])
        config = data.get("config", {})
        image_base = config.get("image", self.host)
        all_videos = []
        for section in archives:
            section_data = section.get("data", [])
            all_videos.extend(self._parse_video_list(section_data, image_base))
        return {"list": all_videos[:20]}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        """分类列表"""
        page = int(pg) if pg else 1
        # 分页 URL: /type/{tid}-{page}.html，第一页特殊
        if page == 1:
            url = f"{self.host}/type/{tid}.html"
        else:
            url = f"{self.host}/type/{tid}-{page}.html"
        data = self._fetch_page_data(url)
        if not data:
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
        archives = data.get("archives", {})
        config = data.get("config", {})
        image_base = config.get("image", self.host)
        # 获取视频列表
        video_data = archives.get("data", [])
        video_list = self._parse_video_list(video_data, image_base)
        # 分页信息
        paging = archives.get("paging", {})
        pagecount = paging.get("count", 1)
        return {
            "list": video_list,
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": paging.get("total", pagecount * 20)
        }

    def detailContent(self, ids):
        """
        详情页（播放页）
        该站播放页即详情页，直接返回播放地址
        """
        vid = ids[0] if ids else ""
        if not vid:
            return {"list": []}
        url = f"{self.host}/play/{vid}.html"
        data = self._fetch_page_data(url)
        if not data:
            return {"list": []}
        self_data = data.get("self", {})
        name_encoded = self_data.get("name", "")
        name = self._decode_name(name_encoded) or name_encoded
        play_url_base = self_data.get("url", "")
        play_info = self_data.get("info", "")
        if play_url_base and play_info:
            play_url = play_url_base.rstrip("/") + play_info
        else:
            play_url = ""
        # 推荐列表
        archives = data.get("archives", {})
        config = data.get("config", {})
        image_base = config.get("image", self.host)
        recommend_data = archives.get("data", [])
        recommend_list = self._parse_video_list(recommend_data, image_base)
        # 构造详情数据
        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": "",
            "vod_remarks": "",
            "vod_content": name,
            "vod_play_from": "直链",
            "vod_play_url": f"播放${play_url}" if play_url else "",
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        page = int(pg) if pg else 1
        # 搜索 URL: /search/{keyword}.html
        url = f"{self.host}/search/{key}.html"
        data = self._fetch_page_data(url)
        if not data:
            return {"list": [], "page": page}
        # 搜索页数据结构与分类页一致
        archives = data.get("archives", {})
        config = data.get("config", {})
        image_base = config.get("image", self.host)
        video_data = archives.get("data", [])
        video_list = self._parse_video_list(video_data, image_base)
        return {"list": video_list, "page": page}

    def playerContent(self, flag, id, vipFlags):
        """
        播放器
        id 是 detailContent 中返回的播放 ID（即 m3u8 地址）
        """
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        # id 就是 m3u8 地址，直接返回直链
        return {
            "parse": 0,
            "url": id,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/"
            }
        }

    def recommendContent(self, ids, pg):
        """相关推荐"""
        # 从 detailContent 中已解析推荐，但此方法需要独立实现
        # 简单返回空列表，实际可在 detailContent 中已包含推荐数据
        return {"list": []}

    def destroy(self):
        """释放资源"""
        pass