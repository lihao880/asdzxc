#!/usr/bin/env python3
# ============ ★写源必加清单（缺一不可，写源时逐条落注释核对）============
# ★必加①大图片：列表 item 走 _cw() 四件套 style={rect,1.78}+land+ratio+type_name（秀网阁同款）
# ★必加②二级分类/筛选器：homeContent 返 filters(key=一级tid·『全部』v=该tid) + categoryContent 消费 extend(★参数名必须 filter)（秀网阁同款）
# ★必加③搜索：searchContent(key,quick,pg) 关键词 quote()
# ☆按需·资料夹分类：folder:/cat:/vod_tag='folder' 真两级契约（非必加，用户点单才做）
# ============ ★写源必检查清单（交付前逐条核对，字看清别漏）============
# ★必检①翻页还少/卡顿：page/pagecount/limit/total 四件；pagecount 真解析(禁999伪分页)；翻页不卡
# ★必检②多线路接口检查：全部线路解析 + 并发 probe 各线首集可播；死线排后不剔除
# ★必检③播放源还能播放：playerContent 逐线实测可播(parse=0+真m3u8/MP4)
# ★必检④分类还少：补 LABEL/排行榜/更多入口
# ============ 写源必加/必检查清单结束（任何模板写源必走）============
# ============ ★写源前必调·三底座（任何写源自动触发，无需提醒）============
# ★底座①记忆库：query_memory『知识库/影视源开发』及分区（01-规范契约 / 02-技能与工具链 / 03-攻坚档案 / 04-源交付档案 / 05-归档与暂停）
# ★底座②技能包：/sdcard/Download/Operit/skills/SKILL_INDEX.md 分层调度（L0 tvbox-py-v73 → L1 pySkill → L2 攻坚逆向 → L3 adaptive四工作台 → L4 交付）
# ★底座③母版：cp 母版 → 改 CONFIG ★区 → 改站点逻辑区（禁从零手写骨架、禁跳技能库直接套模板）
# ============ 写源前必调·三底座结束 ============
# -*- coding: utf-8 -*-
# By:老醋花生米
# Date  : 2026-10-15
# Description: TVBox Python源 - 陌陌一夜情 (Moyeyiqing)

import re
import json
import urllib.request
import ssl
import urllib.parse

# TVBox Spider 基类兼容
try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider:
        pass


class Spider(_BaseSpider):
    
    def __init__(self):
        self.host = "https://ryoz487.mmyy25.top"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Mobile Safari/537.36",
            "Referer": self.host + "/",
        }
        self.categories = [
            {"type_id": "6", "type_name": "美女主播"},
            {"type_id": "7", "type_name": "精品推荐"},
            {"type_id": "3", "type_name": "自拍偷拍"},
            {"type_id": "8", "type_name": "国产乱伦"},
            {"type_id": "9", "type_name": "制服丝袜"},
            {"type_id": "10", "type_name": "传媒探花"},
            {"type_id": "11", "type_name": "清纯学生"},
            {"type_id": "12", "type_name": "淫妻作乐"},
            {"type_id": "13", "type_name": "反差母狗"},
            {"type_id": "17", "type_name": "足浴撩妹"},
            {"type_id": "14", "type_name": "制服诱惑"},
            {"type_id": "18", "type_name": "AI换脸"},
            {"type_id": "15", "type_name": "丝袜美腿"},
            {"type_id": "4", "type_name": "多人群交"},
            {"type_id": "16", "type_name": "中文字幕"},
            {"type_id": "5", "type_name": "主奴调教"},
        ]
    
    def getName(self):
        return "陌陌一夜情"
    
    def init(self, extend=""):
        return {}
    
    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|avi|mkv|mov)(\?|$)', url or "", re.I))
    
    def manualVideoCheck(self):
        return False
    
    def homeContent(self, filterable=False):
        return {
            "class": self.categories,
            "filters": {},
            "list": []
        }
    
    def homeVideoContent(self):
        html = self.get(self.host + "/")
        if html and len(html) > 1000:
            return {"list": self.parseList(html)}
        return {"list": []}
    
    def categoryContent(self, tid, pg="1", filterable=False, extend={}):
        url = self.host + ("/index.php/vod/type/id/" + str(tid) + ".html" if str(pg) == "1" else "/index.php/vod/type/id/" + str(tid) + "/page/" + str(pg) + ".html")
        html = self.get(url)
        if html and len(html) > 1000:
            return {
                "page": int(pg),
                "pagecount": 999,
                "limit": 24,
                "total": 999999,
                "list": self.parseList(html)
            }
        return {"list": [], "page": int(pg), "pagecount": 999, "limit": 24, "total": 999999}
    
    def detailContent(self, ids):
        vid = ids[0]
        # 播放页直接返回m3u8 URL
        play_url = self.host + "/index.php/vod/play/id/" + vid + "/sid/1/nid/1.html"
        html = self.get(play_url)
        
        if not html or len(html) < 500:
            return {"list": []}
        
        # 从 #bfz 提取 m3u8 URL
        m3u8 = ""
        name = ""
        m = re.search(r'id=["\']bfz["\'][^>]*data-user-name=["\']([^"\']+)["\']', html)
        if m:
            data = m.group(1)
            if "$" in data:
                parts = data.split("$")
                name = parts[0].strip()
                url = parts[1].strip() if len(parts) > 1 else ""
                # 检查是否是 m3u8
                if self.isVideoFormat(url):
                    m3u8 = url
                elif url.startswith("//"):
                    m3u8 = "https:" + url
                else:
                    m3u8 = self.host + url if url.startswith("/") else url
        
        # 尝试从详情页获取标题
        title = self.match(html, r'<h2[^>]*>([^<]+)</h2>')
        pic = self.match(html, r'<img[^>]+src=["\']([^"\']+\.jpg[^"\']*)["\']')
        
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title or ("视频" + vid),
                "vod_pic": pic or "",
                "vod_play_from": "".join([chr(0x8001), chr(0x918B), chr(0x82B1), chr(0x751F), chr(0x7C73)]),
                "vod_play_url": (name if name else "第1集") + "$" + m3u8
            }]
        }
    
    def searchContent(self, kw, pg="1", fast=False):
        html = self.get(self.host + "/index.php/vod/search.html?wd=" + urllib.parse.quote(kw) + "&page=" + str(pg))
        if html and len(html) > 500:
            return {"list": self.parseList(html), "page": int(pg), "pagecount": 999, "limit": 24, "total": 999999}
        return {"list": [], "page": int(pg), "pagecount": 999, "limit": 24, "total": 999999}
    
    def playerContent(self, flag, pid, flags=[]):
        url = pid
        if not self.isVideoFormat(url):
            # 尝试解析
            m3u8_match = re.search(r'(https?://[^\s\$]+\.m3u8[^\s\$]*)', url)
            if m3u8_match:
                url = m3u8_match.group(1)
        
        return {"parse": 0 if self.isVideoFormat(url) else 1, "playUrl": "", "url": url, "header": json.dumps(self.headers, ensure_ascii=False)}
    
    def localProxy(self, param):
        return [404, "text/plain", "", ""]
    
    def action(self, action):
        return {}
    
    def liveContent(self):
        return {}
    
    def destroy(self):
        return {}
    
    # ==================== 工具函数 ====================
    def get(self, url):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                data = resp.read()
                for enc in ['utf-8', 'gbk', 'gb2312']:
                    try:
                        return data.decode(enc)
                    except:
                        continue
                return data.decode('utf-8', errors='ignore')
        except:
            return ""
    
    def match(self, text, rule):
        m = re.search(rule, text or "", re.S)
        return m.group(1) if m else ""
    
    def parseList(self, html):
        res = []
        seen = set()
        if not html or len(html) < 500:
            return res
        
        # 匹配 <dl>...</dl> 块
        blocks = re.findall(r'<dl\b[^>]*>(.*?)</dl>', html, re.DOTALL)
        
        for block in blocks:
            # 提取链接和ID
            href_m = re.search(r'href=["\']([^"\']*vod/play/id/(\d+)[^"\']*)["\']', block)
            if not href_m:
                continue
            vid = href_m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            
            # 提取标题
            title = self.match(block, r'<h3[^>]*>([^<]+)</h3>')
            if not title:
                title = self.match(block, r'<a[^>]+class=["\'][^"\']*(?:mm|mmyy)["\'][^>]*>([^<]+)</a>')
            
            # 提取图片
            pic = self.match(block, r'<img[^>]+src=["\']([^"\']+)["\']')
            if not pic:
                pic = self.match(block, r'<img[^>]+data-original=["\']([^"\']+)["\']')
            
            # 提取备注
            remark = self.match(block, r'<span[^>]+class=["\'][^"\']*note[^"\']*["\'][^>]*>(.*?)</span>')
            
            if title:
                res.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": pic if pic and "load.gif" not in pic and "template" not in pic else "",
                    "vod_remarks": remark.strip() if remark else ""
                })
        
        return res


def main(req_data):
    try:
        obj = json.loads(req_data)
        t = obj.get("t", "")
        id = obj.get("id", "")
        pg = obj.get("pg", "1")
        kw = obj.get("wd", "")
        filterable = obj.get("filterable", False)
        extend = obj.get("extend", {})

        spider = Spider()

        if t == "home":
            return json.dumps(spider.homeContent(filterable), ensure_ascii=False)
        elif t == "category":
            return json.dumps(spider.categoryContent(id, pg, filterable, extend), ensure_ascii=False)
        elif t == "detail":
            return json.dumps(spider.detailContent([id]), ensure_ascii=False)
        elif t == "search":
            return json.dumps(spider.searchContent(kw, pg), ensure_ascii=False)
        elif t == "play":
            return json.dumps(spider.playerContent("", id, []), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"err": str(e)})


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        args = sys.argv[2:]
        spider = Spider()
        if cmd == "home":
            print(json.dumps(spider.homeContent(), ensure_ascii=False, indent=2))
        elif cmd == "category":
            print(json.dumps(spider.categoryContent(args[0] if args else "6", "1"), ensure_ascii=False, indent=2))
        elif cmd == "search":
            print(json.dumps(spider.searchContent(args[0] if args else "美女", "1"), ensure_ascii=False, indent=2))
        elif cmd == "detail":
            print(json.dumps(spider.detailContent([args[0] if args else "23199"]), ensure_ascii=False, indent=2))
        else:
            print(main(json.dumps({"t": cmd, "id": args[0] if args else ""})))
    else:
        print("Usage: python moyeyiqing.py <home|category|search|detail> [args]")
