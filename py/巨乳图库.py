# coding: utf-8
"""
站点名称: 巨乳图库 (JR TuKu)
主域名: https://jrtk2.cc/go/
备用域名: 无
发布页: 无
内容类型: 写真图集（图片）
特殊说明: WordPress站点，图片以wp-block-image内嵌，使用pics://协议
最后验证时间: 2026-09-04
来源: 用户提供
"""
import re
import json
from urllib.parse import urljoin, quote
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://jrtk2.cc/go/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        # 分类：最新放在推荐后面（第二位），然后是各模特标签
        self.classes = [
            {"type_id": "zuixin", "type_name": "最新"},
            {"type_id": "chunmomo", "type_name": "蠢沫沫"},
            {"type_id": "tuniang", "type_name": "兔娘"},
            {"type_id": "naixijiang", "type_name": "奈汐酱"},
            {"type_id": "naitaotao", "type_name": "奶桃桃"},
            {"type_id": "baiyin", "type_name": "白银"},
            {"type_id": "budingdafa", "type_name": "布丁大法"},
            {"type_id": "rinaijiao", "type_name": "日奈娇"},
            {"type_id": "shuimiao", "type_name": "水淼"},
            {"type_id": "yubo", "type_name": "雨波"},
            {"type_id": "senluo", "type_name": "森萝"},
            {"type_id": "yingdaomayi", "type_name": "樱岛麻衣"},
            {"type_id": "xingzhichichi", "type_name": "星之迟迟"},
            {"type_id": "ashat", "type_name": "AT鲨"},
        ]
        # filters 空
        self.filters = {}
        self.publish = None
        self.nav = None
        self.email = "xiaonv@proton.me"

    def getName(self):
        return "巨乳图库"

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        return None

    def init(self, extend=""):
        self.setExtendInfo(extend)
        return None

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐：获取最新图集"""
        url = self.host
        html = self._fetch_html(url)
        if not html:
            return {"list": []}
        items = self._parse_home_list(html)
        return {"list": items}

    def _fetch_html(self, url):
        """封装网络请求"""
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if resp and hasattr(resp, 'text'):
                return resp.text
            return ""
        except Exception:
            return ""

    def _parse_home_list(self, html):
        """解析首页列表卡片"""
        items = []
        # 匹配文章卡片
        pattern = r'<article[^>]*class="[^"]*lens-card[^"]*"[^>]*>[\s\S]*?<a[^>]*href="([^"]+)"[^>]*>[\s\S]*?<img[^>]*src="([^"]+)"[^>]*>[\s\S]*?<h2[^>]*class="[^"]*lens-card__title[^"]*"[^>]*><a[^>]*href="[^"]*"[^>]*>([^<]+)</a>[\s\S]*?<a[^>]*class="[^"]*lens-date[^"]*"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.S)
        for m in matches:
            url_detail, pic, name, date = m
            pic = urljoin(self.host, pic)
            vid = url_detail.split("?p=")[-1] if "?p=" in url_detail else url_detail
            items.append({
                "vod_id": f"{vid}||{name}||{pic}||{date}",
                "vod_name": name.strip(),
                "vod_pic": pic + "@Referer=" + self.host,
                "vod_remarks": date.strip(),
            })
        # 兜底匹配
        if not items:
            pattern2 = r'<a[^>]*href="([^"]*\?p=\d+)"[^>]*>[\s\S]*?<img[^>]*src="([^"]+)"[^>]*>[\s\S]*?<h2[^>]*class="[^"]*lens-card__title[^"]*"[^>]*><a[^>]*href="[^"]*"[^>]*>([^<]+)</a>'
            matches2 = re.findall(pattern2, html, re.S)
            for m in matches2:
                url_detail, pic, name = m
                pic = urljoin(self.host, pic)
                vid = url_detail.split("?p=")[-1]
                items.append({
                    "vod_id": f"{vid}||{name}||{pic}||",
                    "vod_name": name.strip(),
                    "vod_pic": pic + "@Referer=" + self.host,
                    "vod_remarks": "",
                })
        return items[:30]

    def categoryContent(self, tid, pg, filter, extend):
        """分类列表：按模特标签或最新"""
        try:
            page = int(pg) if pg and str(pg).isdigit() else 1
        except (ValueError, TypeError):
            page = 1
        
        if tid == "zuixin":
            # 最新：分页参数为 paged
            if page <= 1:
                url = self.host
            else:
                url = f"{self.host}?paged={page}"
        else:
            # 标签名映射
            tag_map = {
                "chunmomo": "蠢沫沫",
                "tuniang": "兔娘",
                "naixijiang": "奈汐酱",
                "naitaotao": "奶桃桃",
                "baiyin": "白银",
                "budingdafa": "布丁大法",
                "rinaijiao": "日奈娇",
                "shuimiao": "水淼",
                "yubo": "雨波",
                "senluo": "森萝",
                "yingdaomayi": "樱岛麻衣",
                "xingzhichichi": "星之迟迟",
                "ashat": "AT鲨",
            }
            tag_name = tag_map.get(tid, tid)
            if page <= 1:
                url = f"{self.host}?tag={tag_name}"
            else:
                url = f"{self.host}?tag={tag_name}&paged={page}"
        
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
        
        items = self._parse_home_list(html)
        
        # 提取总页数
        pagecount = 1
        pager_match = re.search(r'<a[^>]*class="page-numbers"[^>]*>(\d+)</a>', html)
        if pager_match:
            pagecount = int(pager_match.group(1))
        # 如果有 next 链接，说明还有下一页
        if re.search(r'class="next page-numbers"', html):
            next_match = re.search(r'<a[^>]*class="next page-numbers"[^>]*href="[^"]*paged=(\d+)"', html)
            if next_match:
                pagecount = max(pagecount, int(next_match.group(1)))
        
        return {
            "list": items,
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": len(items) if page == pagecount else page * 20
        }

    def detailContent(self, ids):
        """详情页：提取图集所有图片"""
        if not ids:
            return {"list": []}
        vid = ids[0]
        # 从vod_id中解析
        parts = vid.split("||")
        if len(parts) >= 3:
            post_id, name, pic, date = parts[0], parts[1], parts[2], parts[3] if len(parts) > 3 else ""
        else:
            post_id = vid
            name = ""
            pic = ""
            date = ""
        
        # 提取post_id
        if "?p=" in post_id:
            post_id = post_id.split("?p=")[-1]
        elif "/go/?p=" in post_id:
            post_id = post_id.split("/go/?p=")[-1]
        
        url = f"{self.host}?p={post_id}"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}
        
        # 提取标题
        if not name:
            title_match = re.search(r'<h1[^>]*class="[^"]*lens-single-title[^"]*"[^>]*>([^<]+)</h1>', html, re.S)
            if title_match:
                name = title_match.group(1).strip()
        
        # 提取图片
        imgs = self._extract_images(html)
        if not imgs:
            return {"list": []}
        
        # 构建单张图片列表，用于pics://协议
        # 格式: pics://图片1@Referer=xxx&&图片2@Referer=xxx&&图片3@Referer=xxx
        pic_urls = []
        for img in imgs:
            pic_urls.append(img + "@Referer=" + self.host)
        pics_protocol = "pics://" + "&&".join(pic_urls)
        
        vod = {
            "vod_id": post_id,
            "vod_name": name or "图集",
            "vod_pic": pic if pic else (imgs[0] + "@Referer=" + self.host),
            "vod_remarks": f"{len(imgs)}P",
            "vod_content": f"共 {len(imgs)} 张图片",
            "vod_play_from": "图片浏览",
            "vod_play_url": f"浏览图片${pics_protocol}",
        }
        return {"list": [vod]}

    def _extract_images(self, html):
        """从详情页提取图集图片，限定正文容器"""
        imgs = []
        # 先限定正文容器
        scope_match = re.search(r'<div[^>]*class="[^"]*entry-content[^"]*lens-gallery-content[^"]*"[^>]*>([\s\S]*?)(?:<div[^>]*class="[^"]*category-and-tags|</main>|<div[^>]*id="comments")', html, re.S)
        if not scope_match:
            scope_match = re.search(r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>([\s\S]*?)(?:<div[^>]*class="[^"]*category-and-tags|</main>|<div[^>]*id="comments")', html, re.S)
        if not scope_match:
            scope_match = re.search(r'<div[^>]*class="[^"]*lens-single-main[^"]*"[^>]*>([\s\S]*?)(?:<nav[^>]*class="[^"]*lens-post-nav|</main>)', html, re.S)
        scope = scope_match.group(1) if scope_match else html
        
        # 提取所有图片src
        img_pattern = r'<img[^>]+(?:src|data-src|data-original)="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"'
        matches = re.findall(img_pattern, scope, re.S)
        for m in matches:
            low = m.lower()
            bad = ['avatar', 'icon', 'logo', 'loading', 'smilies', 'qrcode', 'none.gif', 'thumb', 'favicon', 'wp-smiley']
            if any(k in low for k in bad):
                continue
            img_url = urljoin(self.host, m)
            if img_url not in imgs:
                imgs.append(img_url)
        
        # 兜底匹配
        if not imgs:
            img_pattern2 = r'<img[^>]+src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"'
            matches2 = re.findall(img_pattern2, html, re.S)
            for m in matches2:
                low = m.lower()
                bad = ['avatar', 'icon', 'logo', 'loading', 'smilies', 'qrcode', 'none.gif', 'thumb', 'favicon', 'wp-smiley']
                if any(k in low for k in bad):
                    continue
                img_url = urljoin(self.host, m)
                if img_url not in imgs:
                    imgs.append(img_url)
        
        # 去重
        seen = set()
        unique = []
        for img in imgs:
            if img not in seen:
                seen.add(img)
                unique.append(img)
        return unique

    def searchContent(self, key, quick, pg="1"):
        """搜索：WordPress搜索"""
        try:
            page = int(pg) if pg and str(pg).isdigit() else 1
        except (ValueError, TypeError):
            page = 1
        url = f"{self.host}?s={key}&paged={page}"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": page}
        items = self._parse_home_list(html)
        return {"list": items, "page": page}

    def playerContent(self, flag, id, vipFlags):
        """
        图片播放：使用pics://协议
        如果id是pics://协议，直接返回
        如果是单张图片URL，返回单张pics://
        """
        # 如果已经是pics://协议，直接返回
        if id and id.startswith("pics://"):
            return {"parse": 0, "url": id, "header": {}}
        
        # 如果id是浏览图片$pics://格式，提取pics://部分
        if id and "$" in id:
            parts = id.split("$", 1)
            if len(parts) == 2:
                url_part = parts[1]
                if url_part.startswith("pics://"):
                    return {"parse": 0, "url": url_part, "header": {}}
                if url_part.startswith("http"):
                    return {"parse": 0, "url": f"pics://{url_part}", "header": {}}
        
        # 如果id本身就是图片URL
        if id and id.startswith("http"):
            return {"parse": 0, "url": f"pics://{id}", "header": {}}
        
        return {"parse": 0, "url": "", "header": {}}

    def recommendContent(self, ids, pg="1"):
        """相关推荐"""
        return {"list": []}

    def destroy(self):
        """释放资源"""
        pass

    def siteInfo(self):
        """站点信息"""
        return {
            "current": self.host,
            "publish": self.publish,
            "nav": self.nav,
            "backups": [],
            "email": self.email,
            "type": "写真图集",
            "protocol": "pics://"
        }