# coding: utf-8
# 站点信息：
#   主域名: https://www.tututuku.cc/
#   内容类型: 图片/写真
#   特殊说明: 图片集，使用 pics:// 协议播放
#   最后验证时间: 2026-09-04
#   来源: https://www.tututuku.cc/

import re
import json
import urllib.parse
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    """兔兔图库 - 图片/写真站爬虫"""

    def __init__(self):
        # 初始化本地配置，零网络依赖
        self.host = "https://www.tututuku.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类配置
        self.classes = [
            {"type_id": "b/1", "type_name": "最新"},
            {"type_id": "b/7", "type_name": "周榜"},
            {"type_id": "j/xiurenwang", "type_name": "秀人网"},
            {"type_id": "j/youmihui", "type_name": "尤蜜荟"},
            {"type_id": "j/yuhuajie", "type_name": "语画界"},
            {"type_id": "j/xingyanshe", "type_name": "星颜社"},
            {"type_id": "j/mofanxueyuan", "type_name": "模范学院"},
            {"type_id": "j/meiyuanguan", "type_name": "美媛馆"},
            {"type_id": "j/aimishe", "type_name": "爱蜜社"},
            {"type_id": "j/youwuguan", "type_name": "尤物馆"},
            {"type_id": "j/mitaoshe", "type_name": "蜜桃社"},
            {"type_id": "j/yunulang", "type_name": "御女郎"},
            {"type_id": "j/ruisiguan", "type_name": "瑞丝馆"},
            {"type_id": "j/miaotangyinghua", "type_name": "喵糖映画"},
            {"type_id": "j/senluocaituan", "type_name": "森萝财团"},
            {"type_id": "j/qinglanyinghua", "type_name": "轻兰映画"},
            {"type_id": "j/fengzhilingyu", "type_name": "风之领域"},
            {"type_id": "j/rosi", "type_name": "ROSI写真"},
            {"type_id": "j/youmi", "type_name": "尤蜜"},
            {"type_id": "j/aiyouwu", "type_name": "爱尤物"},
            {"type_id": "j/beautyleg", "type_name": "Beautyleg"},
            {"type_id": "j/ligui", "type_name": "丽柜"},
            {"type_id": "j/simu", "type_name": "丝慕"},
        ]
        # 筛选配置（此站无筛选功能）
        self.filters = {}
        # 是否清洗 m3u8（此站为图片站，不涉及）
        self.NEED_CLEAN = False

    def getName(self):
        return "兔兔图库"

    def getDependence(self):
        return []

    def init(self, extend=""):
        """初始化，零网络依赖"""
        self.extend = extend or ""

    def homeContent(self, filter):
        """首页分类和筛选配置，快速返回"""
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐：请求最新列表页 /b/1"""
        return self._fetch_list_page("b/1", 1)

    def categoryContent(self, tid, pg, filter, extend):
        """分类列表页"""
        page = pg or "1"
        # tid 即为 URL 路径，如 b/1, j/xiurenwang
        return self._fetch_list_page(tid, page)

    def _fetch_list_page(self, tid, pg):
        """获取列表页并解析"""
        base_url = f"{self.host}/{tid}"
        if str(pg) != "1":
            url = f"{base_url}/page/{pg}"
        else:
            url = base_url

        try:
            resp = self.fetch(url, headers=self.headers)
            html = resp.text if resp else ""
            list_data = self._parse_list(html)
            # 提取分页信息
            pagecount = self._get_pagecount(html)
            return {
                "list": list_data,
                "page": int(pg),
                "pagecount": pagecount,
                "limit": 20,
                "total": pagecount * 20
            }
        except Exception as e:
            self.log(f"_fetch_list_page error: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}

    def _parse_list(self, html):
        """解析列表页，复用逻辑"""
        items = []
        if not html:
            return items
        
        # 直接匹配每个列表项中的关键信息
        # 匹配模式：机构名、图集链接、缩略图、标题
        # 图集链接是 <a href="/xxxxx"> 这种短代码，不在 jigou 内部
        
        # 先按列表项分割
        item_pattern = r'<div class="acli lilp1">(.*?)</div>\s*</div>'
        item_blocks = re.findall(item_pattern, html, re.S)
        
        for block in item_blocks:
            try:
                # 提取机构名（从 jigou 中的 a class="a3" 提取）
                org_match = re.search(r'<div class="jigou">.*?<a class="a3"[^>]*>.*?<i[^>]*>.*?</i>\s*([^<]+)</a>', block, re.S)
                org_name = org_match.group(1).strip() if org_match else ""
                
                # 提取图集详情链接：匹配包含 em 标签的 a 标签
                # 注意：这个 a 标签不在 jigou 内部
                detail_match = re.search(r'<a href="([^"]+)"[^>]*>\s*<span>.*?</span>\s*<em>([^<]+)</em>', block, re.S)
                if not detail_match:
                    continue
                detail_url = detail_match.group(1)
                title = detail_match.group(2).strip()
                
                # 提取缩略图
                img_match = re.search(r'<img class="lazy" data-original="([^"]+)"', block, re.S)
                img_url = img_match.group(1) if img_match else ""
                
                if not detail_url:
                    continue
                
                vod_name = title
                vod_pic = img_url
                # 处理标题中的 [P] 数字
                vod_remarks = re.search(r'\[(\d+)P\]', vod_name)
                vod_remarks = f"{vod_remarks.group(1)}P" if vod_remarks else ""
                # 增加机构信息
                if org_name:
                    vod_name = f"{org_name} | {vod_name}"
                
                items.append({
                    "vod_id": detail_url,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks
                })
            except Exception as e:
                continue
                
        return items

    def _get_pagecount(self, html):
        """从HTML中提取总页数"""
        if not html:
            return 1
        # 查找分页容器中的链接，取最后一个数字
        pattern = r'<div class="page_navi">.*?<a[^>]*>(\d+)</a>\s*<a[^>]*>(\d+)</a>\s*<a[^>]*>(\d+)</a>'
        match = re.search(pattern, html, re.S)
        if match:
            # 最后一个数字通常是总页数
            return int(match.group(3))
        # 尝试匹配简单模式
        simple_pattern = r'<div class="page_navi">.*?<a[^>]*>(\d+)</a>.*?<a[^>]*>(\d+)</a>.*?<a[^>]*>(\d+)</a>'
        match = re.search(simple_pattern, html, re.S)
        if match:
            return int(match.group(3))
        # 尝试匹配 "共X页" 文本
        text_pattern = r'共(\d+)页'
        match = re.search(text_pattern, html)
        if match:
            return int(match.group(1))
        return 1

    def detailContent(self, ids):
        """获取详情页，只返回基本信息，不包含 pics:// 链接"""
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        url = f"{self.host}/{vod_id}"
        try:
            resp = self.fetch(url, headers=self.headers)
            html = resp.text if resp else ""
            return self._parse_detail(html, vod_id)
        except Exception as e:
            self.log(f"detailContent error: {e}")
            return {"list": []}

    def _parse_detail(self, html, vod_id):
        """解析详情页，返回基本信息（不包含 pics://）"""
        vod = {
            "vod_id": vod_id,
            "vod_name": "",
            "vod_pic": "",
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "图片",
            "vod_play_url": f"浏览图片${vod_id}"  # 播放时 playerContent 会解析
        }
        if not html:
            return {"list": [vod]}

        # 提取标题
        title_match = re.search(r'<h1>.*?<i class="fa-solid fa-right-from-bracket"></i>([^<]+)</h1>', html)
        if title_match:
            vod["vod_name"] = title_match.group(1).strip()

        # 提取封面图（第一张大图）
        img_match = re.search(r'<a href="(https?://timg[^"]+\.(?:jpg|png|jpeg|webp))"', html, re.I)
        if img_match:
            vod["vod_pic"] = img_match.group(1)

        # 提取图片数量
        count_match = re.search(r'共<span>(\d+)</span>张', html)
        if count_match:
            vod["vod_remarks"] = f"{count_match.group(1)}张"

        # 提取简介
        desc_match = re.search(r'<div class="p_info">([^<]+)</div>', html)
        if desc_match:
            vod["vod_content"] = desc_match.group(1).strip()

        return {"list": [vod]}

    def _parse_recommend(self, html):
        """解析相关推荐"""
        rec_items = []
        if not html:
            return rec_items
        # 相关推荐在 <div class="ac acrand"> 中
        pattern = r'<div class="ac acrand">.*?<div class="acli lilp1">.*?<a href="([^"]+)">.*?<em>([^<]+)</em>'
        matches = re.findall(pattern, html, re.S)
        for match in matches:
            detail_url, title = match
            rec_items.append({
                "vod_id": detail_url,
                "vod_name": title.strip(),
                "vod_pic": "",
                "vod_remarks": ""
            })
        return rec_items

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        # 处理中文关键词
        enc_key = urllib.parse.quote(key)
        url = f"{self.host}/sou?f={enc_key}"
        try:
            resp = self.fetch(url, headers=self.headers)
            html = resp.text if resp else ""
            items = self._parse_list(html)
            return {"list": items, "page": int(pg)}
        except Exception as e:
            self.log(f"searchContent error: {e}")
            return {"list": [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        """播放：提取图集中所有图片，返回 pics:// 链接"""
        if id and id.startswith("pics://"):
            return {"parse": 0, "url": id, "header": self.headers}

        try:
            if not id:
                return {"parse": 0, "url": "", "header": {}}

            if id.startswith("http"):
                base_url = id.rstrip("/")
            else:
                if not id.startswith("/"):
                    id = "/" + id
                base_url = f"{self.host}{id}"

            res = self.fetch(base_url, headers=self.headers, timeout=15)
            if not res:
                return {"parse": 0, "url": "", "header": {}}

            html = res.text
            if len(html) < 1000:
                return {"parse": 0, "url": "", "header": {}}

            # 直接从 div#image.postpic 中提取所有图片
            img_urls = []
            container_match = re.search(r'<div\s+id="image"\s+class="postpic">(.*?)</div>', html, re.S | re.I)
            if container_match:
                container = container_match.group(1)
                for m in re.finditer(r'<a\s+href="([^"]+\.(?:jpg|png|jpeg|webp))"', container, re.S | re.I):
                    img_urls.append(m.group(1))

            if not img_urls:
                return {"parse": 0, "url": "", "header": {}}

            # 去重
            seen = set()
            unique_urls = []
            for u in img_urls:
                if u not in seen:
                    seen.add(u)
                    unique_urls.append(u)

            pics = []
            for img in unique_urls:
                if not img.startswith("http"):
                    img = urljoin(self.host, img)
                pics.append(f"{img}@Referer={self.host}/")

            pics_url = "pics://" + "&&".join(pics)
            return {"parse": 0, "url": pics_url, "header": self.headers}

        except Exception as e:
            return {"parse": 0, "url": "", "header": {}}

    def recommendContent(self, ids, pg):
        """相关推荐"""
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        url = f"{self.host}/{vod_id}"
        try:
            resp = self.fetch(url, headers=self.headers)
            html = resp.text if resp else ""
            rec_items = self._parse_recommend(html)
            return {"list": rec_items}
        except Exception as e:
            self.log(f"recommendContent error: {e}")
            return {"list": []}

    def destroy(self):
        """清理资源"""
        pass