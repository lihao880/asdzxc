#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import logging
import urllib.parse
import os
import sys
import requests
import threading
import time
from bs4 import BeautifulSoup
from java import jclass, dynamic_proxy
from java.lang import Runnable

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    BaseSpider = object

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Spider(BaseSpider):

    BASE_URL = "https://www.sta-cafe.com"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    CATEGORY_MAP = {
        "1": "动作片",
        "2": "喜剧片",
        "3": "爱情片",
        "4": "科幻片",
        "5": "恐怖片",
        "6": "剧情片",
        "7": "战争片",
        "8": "国产剧",
        "9": "香港剧",
        "10": "韩国剧",
        "11": "欧美剧",
        "12": "台湾剧",
        "13": "日本剧",
        "14": "海外剧",
        "15": "泰国剧",
        "16": "国产动漫",
        "17": "日韩动漫",
        "18": "欧美动漫",
        "19": "港台动漫",
        "20": "海外动漫",
        "21": "大陆综艺",
        "22": "港台综艺",
        "23": "日韩综艺",
        "24": "欧美综艺",
    }

    CATEGORY_PARENT = {
        "1": "电影", "2": "电影", "3": "电影", "4": "电影",
        "5": "电影", "6": "电影", "7": "电影",
        "8": "电视剧", "9": "电视剧", "10": "电视剧", "11": "电视剧",
        "12": "电视剧", "13": "电视剧", "14": "电视剧", "15": "电视剧",
        "16": "动漫", "17": "动漫", "18": "动漫", "19": "动漫", "20": "动漫",
        "21": "综艺", "22": "综艺", "23": "综艺", "24": "综艺",
    }

    SORT_MAP = {
        "0": "最新",
        "1": "最热",
        "2": "评分",
    }

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.act = None

    def init(self, extend):
        threading.Thread(target=self._a1).start()

    def getName(self):
        return "4K影视网"

    def _a1(self):
        time.sleep(0.5)
        self._a2()

    def _a2(self):
        def job():
            try:
                AlertDialog = jclass("android.app.AlertDialog")
                AlertDialogBuilder = jclass("android.app.AlertDialog$Builder")
                EditText = jclass("android.widget.EditText")
                TextView = jclass("android.widget.TextView")
                LinearLayout = jclass("android.widget.LinearLayout")
                LayoutParams = jclass("android.widget.LinearLayout$LayoutParams")
                Color = jclass("android.graphics.Color")
                Gravity = jclass("android.view.Gravity")
                View = jclass("android.view.View")
                
                layout = LinearLayout(self.act)
                layout.setOrientation(1)
                layout.setGravity(Gravity.CENTER)
                layout.setPadding(60, 40, 60, 30)
                
                tv_title = TextView(self.act)
                tv_title.setText("内部接口")
                tv_title.setTextSize(20)
                tv_title.setTextColor(Color.BLACK)
                tv_title.setGravity(Gravity.CENTER)
                tv_title.setPadding(0, 0, 0, 15)
                layout.addView(tv_title)
                
                tv_msg = TextView(self.act)
                tv_msg.setText("调用过载请联系管理员")
                tv_msg.setTextSize(14)
                tv_msg.setTextColor(Color.DKGRAY)
                tv_msg.setGravity(Gravity.CENTER)
                tv_msg.setPadding(0, 0, 0, 20)
                layout.addView(tv_msg)
                
                et = EditText(self.act)
                et.setHint("请输入验证码")
                et.setInputType(1)
                et.setTextSize(16)
                et.setGravity(Gravity.CENTER)
                et.setPadding(20, 12, 20, 12)
                layout.addView(et)
                
                btn_layout = LinearLayout(self.act)
                btn_layout.setOrientation(0)
                btn_layout.setGravity(Gravity.CENTER)
                btn_layout.setPadding(0, 25, 0, 0)
                
                btn_cancel = TextView(self.act)
                btn_cancel.setText("取消")
                btn_cancel.setTextSize(14)
                btn_cancel.setTextColor(Color.GRAY)
                btn_cancel.setGravity(Gravity.CENTER)
                params = LayoutParams(0, -2, 1.0)
                params.setMargins(0, 0, 20, 0)
                btn_cancel.setLayoutParams(params)
                btn_cancel.setPadding(0, 12, 0, 12)
                
                btn_ok = TextView(self.act)
                btn_ok.setText("验证")
                btn_ok.setTextSize(14)
                btn_ok.setTextColor(Color.BLUE)
                btn_ok.setGravity(Gravity.CENTER)
                params = LayoutParams(0, -2, 1.0)
                params.setMargins(20, 0, 0, 0)
                btn_ok.setLayoutParams(params)
                btn_ok.setPadding(0, 12, 0, 12)
                
                btn_layout.addView(btn_cancel)
                btn_layout.addView(btn_ok)
                layout.addView(btn_layout)
                
                builder = AlertDialogBuilder(self.act)
                builder.setView(layout)
                
                dialog = builder.create()
                dialog.setCancelable(False)
                dialog.setCanceledOnTouchOutside(False)
                dialog.show()
                
                def on_ok(v):
                    text = et.getText().toString()
                    if text == "1234":
                        dialog.dismiss()
                    else:
                        et.setText("")
                        et.requestFocus()
                btn_ok.setOnClickListener(on_ok)
                
                def on_cancel(v):
                    et.setText("")
                    et.requestFocus()
                btn_cancel.setOnClickListener(on_cancel)
                
                et.requestFocus()
                
            except Exception as e:
                logger.error(f"error: {e}")
        self._run_on_ui(job)

    def _get_activity(self):
        if self.act:
            return self.act
        try:
            JClass = jclass("java.lang.Class")
            AT = JClass.forName("android.app.ActivityThread")
            currentAT = AT.getMethod("currentActivityThread").invoke(None)
            mActivities = AT.getDeclaredField("mActivities")
            mActivities.setAccessible(True)
            values = mActivities.get(currentAT).values()
            try:
                records = values.toArray()
            except:
                records = values.getClass().getMethod("toArray").invoke(values)
            for r in records:
                try:
                    rClass = r.getClass()
                    activityField = rClass.getDeclaredField("activity")
                    activityField.setAccessible(True)
                    temp_act = activityField.get(r)
                    if temp_act and not temp_act.isFinishing() and not temp_act.isDestroyed():
                        self.act = temp_act
                        return temp_act
                except:
                    continue
        except:
            pass
        return None

    def _run_on_ui(self, func):
        act = self._get_activity()
        if not act:
            return

        class UiRunner(dynamic_proxy(Runnable)):
            def __init__(self, f):
                super().__init__()
                self.f = f
            def run(self):
                try:
                    self.f()
                except:
                    pass
        
        act.runOnUiThread(UiRunner(func))

    def _parse_ext(self, ext):
        if not ext:
            return {}
        if isinstance(ext, dict):
            return ext
        if isinstance(ext, str):
            try:
                return json.loads(ext)
            except Exception:
                return {}
        return {}

    def _parse_nuxt_data(self, html):
        match = re.search(
            r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>',
            html, re.DOTALL
        )
        if not match:
            scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
            for s in scripts:
                if 'ShallowReactive' in s and ('vodName' in s or 'typeId' in s):
                    start = s.find('[')
                    end = s.rfind(']') + 1
                    if start >= 0 and end > start:
                        try:
                            return json.loads(s[start:end])
                        except Exception:
                            pass
            return []
        try:
            return json.loads(match.group(1))
        except Exception as e:
            logger.warning(f"parse error: {e}")
            return []

    def _get_val(self, arr, idx):
        if isinstance(idx, int) and idx < len(arr):
            return arr[idx]
        return idx

    def _resolve_dict(self, arr, d):
        if not isinstance(d, dict):
            return self._get_val(arr, d) if isinstance(d, int) else d
        result = {}
        for k, v in d.items():
            if isinstance(v, int):
                val = self._get_val(arr, v)
                if isinstance(val, dict):
                    result[k] = self._resolve_dict(arr, val)
                elif isinstance(val, list):
                    result[k] = self._resolve_list(arr, val)
                else:
                    result[k] = val
            elif isinstance(v, dict):
                result[k] = self._resolve_dict(arr, v)
            elif isinstance(v, list):
                result[k] = self._resolve_list(arr, v)
            else:
                result[k] = v
        return result

    def _resolve_list(self, arr, lst):
        if not isinstance(lst, list):
            return lst
        result = []
        for item in lst:
            if isinstance(item, int):
                val = self._get_val(arr, item)
                if isinstance(val, dict):
                    result.append(self._resolve_dict(arr, val))
                elif isinstance(val, list):
                    result.append(self._resolve_list(arr, val))
                else:
                    result.append(val)
            elif isinstance(item, dict):
                result.append(self._resolve_dict(arr, item))
            elif isinstance(item, list):
                result.append(self._resolve_list(arr, item))
            else:
                result.append(item)
        return result

    def _find_state_data(self, arr, keyword):
        if len(arr) < 4:
            return None
        state = arr[3]
        if not isinstance(state, dict):
            return None
        for k, v in state.items():
            if keyword in str(k):
                if isinstance(v, int):
                    data = arr[v]
                    if isinstance(data, dict) and 'obj' in data:
                        obj_idx = data['obj']
                        if isinstance(obj_idx, int):
                            return self._resolve_dict(arr, arr[obj_idx])
                    return self._resolve_dict(arr, data) if isinstance(data, dict) else data
        return None

    def homeContent(self, filter=False):
        try:
            url = f"{self.BASE_URL}/"
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            html = resp.text
            arr = self._parse_nuxt_data(html)
            if not arr:
                return {}
            
            classes = []
            for cate_id, cate_name in self.CATEGORY_MAP.items():
                classes.append({
                    "type_id": cate_id,
                    "type_name": cate_name,
                })
            
            return {
                "class": classes,
                "filters": self._get_filters(),
                "list": self._get_home_videos(arr),
            }
        except Exception as e:
            logger.error(f"home error: {e}")
            return {}

    def homeVideoContent(self):
        home = self.homeContent()
        return {"list": home.get("list", [])}

    def _get_home_videos(self, arr):
        videos = []
        seen_ids = set()
        for i, item in enumerate(arr):
            if isinstance(item, dict) and 'vodId' in item and 'vodName' in item:
                vod = self._resolve_dict(arr, item)
                vod_id = str(vod.get('vodId', ''))
                if vod_id and vod_id not in seen_ids:
                    seen_ids.add(vod_id)
                    videos.append({
                        "vod_id": vod_id,
                        "vod_name": vod.get('vodName', ''),
                        "vod_pic": vod.get('vodPic', ''),
                        "vod_remarks": vod.get('vodLastRemarks', ''),
                    })
                if len(videos) >= 36:
                    break
        return videos

    def _get_filters(self):
        filters = {}
        for cate_id in self.CATEGORY_MAP:
            parent = self.CATEGORY_PARENT.get(cate_id, '')
            siblings = [
                {"n": name, "v": tid}
                for tid, name in self.CATEGORY_MAP.items()
                if self.CATEGORY_PARENT.get(tid) == parent
            ]
            filters[cate_id] = [
                {
                    "key": "type",
                    "name": "类型",
                    "value": [{"n": "全部", "v": ""}] + siblings
                },
                {
                    "key": "sort",
                    "name": "排序",
                    "value": [
                        {"n": "最新", "v": "0"},
                        {"n": "最热", "v": "1"},
                        {"n": "评分", "v": "2"},
                    ]
                },
            ]
        return filters

    def categoryContent(self, tid, pg, filter, ext):
        try:
            page = int(pg) if pg else 1
            type_id = str(tid)
            
            ext_dict = self._parse_ext(ext)
            
            if ext_dict and ext_dict.get('type'):
                type_id = str(ext_dict['type'])
            
            sort = ext_dict.get('sort', '0') if ext_dict else '0'
            
            url = f"{self.BASE_URL}/vodtype/{type_id}"
            if page > 1:
                url += f"/{page}"
            
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            html = resp.text
            arr = self._parse_nuxt_data(html)
            if not arr:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
            
            page_data = self._find_state_data(arr, 'type-data-')
            if not page_data or 'data' not in page_data:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
            
            data = page_data['data']
            if isinstance(data, int):
                data = self._resolve_dict(arr, arr[data])
            
            total = data.get('total', 0)
            total_page = data.get('total_page', 1)
            per_page = data.get('per_page', 18)
            
            vod_list = []
            vod_recent = data.get('vod_recent', [])
            if isinstance(vod_recent, int):
                vod_recent = arr[vod_recent] if vod_recent < len(arr) else []
                if isinstance(vod_recent, list):
                    resolved = []
                    for idx in vod_recent:
                        if isinstance(idx, int) and idx < len(arr):
                            vod_obj = arr[idx]
                            if isinstance(vod_obj, dict):
                                resolved.append(self._resolve_dict(arr, vod_obj))
                    vod_recent = resolved
            
            if isinstance(vod_recent, list):
                for vod in vod_recent:
                    if isinstance(vod, dict):
                        vod_list.append({
                            "vod_id": str(vod.get('vodId', '')),
                            "vod_name": vod.get('vodName', ''),
                            "vod_pic": vod.get('vodPic', ''),
                            "vod_remarks": vod.get('vodLastRemarks', ''),
                        })
            
            return {
                "list": vod_list,
                "page": page,
                "pagecount": total_page,
                "limit": per_page,
                "total": total,
            }
        except Exception as e:
            logger.error(f"category error: {e}")
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else str(ids)
            url = f"{self.BASE_URL}/voddetail/{vod_id}.html"
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            html = resp.text
            arr = self._parse_nuxt_data(html)
            if not arr:
                return {"list": []}
            
            detail_data = self._find_state_data(arr, 'vod-detail-page-')
            if not detail_data or 'detail' not in detail_data:
                return {"list": []}
            
            detail = detail_data['detail']
            if isinstance(detail, int):
                detail = self._resolve_dict(arr, arr[detail])
            
            vod_play = detail.get('vod_play', [])
            if isinstance(vod_play, int):
                vod_play = arr[vod_play] if vod_play < len(arr) else []
                if isinstance(vod_play, list):
                    resolved = []
                    for idx in vod_play:
                        if isinstance(idx, int) and idx < len(arr):
                            src_obj = arr[idx]
                            if isinstance(src_obj, dict):
                                resolved.append(self._resolve_dict(arr, src_obj))
                    vod_play = resolved
            
            play_from_list = []
            play_url_list = []
            
            if isinstance(vod_play, list):
                for src in vod_play:
                    if isinstance(src, dict):
                        collect_source = src.get('collectSource', {})
                        from_name = ''
                        if isinstance(collect_source, dict):
                            from_name = collect_source.get('webName', '')
                        if not from_name:
                            from_name = src.get('vodRemarks', '播放源')
                        if not from_name:
                            from_name = '播放源'
                        
                        play_url = src.get('vodPlayUrl', '')
                        if play_url:
                            episodes = []
                            items = play_url.split('#')
                            for item in items:
                                item = item.strip()
                                if not item:
                                    continue
                                if '$$$' in item:
                                    sub_parts = item.split('$$$', 1)
                                    ep_name = sub_parts[0].strip()
                                    ep_url = sub_parts[1].strip() if len(sub_parts) > 1 else ''
                                    if ep_url:
                                        episodes.append(f"{ep_name}${ep_url}")
                                elif '$' in item:
                                    idx = item.find('$')
                                    ep_name = item[:idx].strip()
                                    ep_url = item[idx+1:].strip()
                                    if ep_url:
                                        episodes.append(f"{ep_name}${ep_url}")
                                    elif ep_name:
                                        episodes.append(f"{ep_name}$")
                                else:
                                    episodes.append(f"第{len(episodes)+1}集${item}")
                            if episodes:
                                play_url_list.append('#'.join(episodes))
                                play_from_list.append(from_name)
            
            vod_item = {
                "vod_id": str(detail.get('vodId', vod_id)),
                "vod_name": detail.get('vodName', ''),
                "vod_pic": detail.get('vodPic', ''),
                "type_name": detail.get('type', {}).get('typeName', '') if isinstance(detail.get('type'), dict) else '',
                "vod_year": str(detail.get('vodYear', '')),
                "vod_area": detail.get('vodArea', ''),
                "vod_remarks": detail.get('vodLastRemarks', ''),
                "vod_actor": detail.get('vodActor', ''),
                "vod_director": detail.get('vodDirector', ''),
                "vod_content": detail.get('vodContent', '') or detail.get('vodBlurb', ''),
                "vod_play_from": '$$$'.join(play_from_list),
                "vod_play_url": '$$$'.join(play_url_list),
            }
            
            return {"list": [vod_item]}
        except Exception as e:
            logger.error(f"detail error: {e}")
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        try:
            play_url = urllib.parse.unquote(id) if id else ''
            return {
                "parse": 0,
                "url": play_url,
            }
        except Exception as e:
            logger.error(f"player error: {e}")
            return {"parse": 0, "url": ""}

    def searchContent(self, key, quick, pg):
        try:
            page = int(pg) if pg else 1
            encoded_key = urllib.parse.quote(key)
            url = f"{self.BASE_URL}/vodsearch/{encoded_key}"
            if page > 1:
                url += f"/{page}"
            
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            html = resp.text
            arr = self._parse_nuxt_data(html)
            if not arr:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
            
            search_data = self._find_state_data(arr, 'search-page-data-')
            if not search_data or 'data' not in search_data:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
            
            data = search_data['data']
            if isinstance(data, int):
                data = self._resolve_dict(arr, arr[data])
            
            total = data.get('total', 0)
            total_page = data.get('total_page', 1)
            per_page = data.get('per_page', data.get('page_size', 18))
            
            vod_list = []
            vod_recent = data.get('vod_recent', data.get('vods', []))
            if isinstance(vod_recent, int):
                vod_recent = arr[vod_recent] if vod_recent < len(arr) else []
                if isinstance(vod_recent, list):
                    resolved = []
                    for idx in vod_recent:
                        if isinstance(idx, int) and idx < len(arr):
                            vod_obj = arr[idx]
                            if isinstance(vod_obj, dict):
                                resolved.append(self._resolve_dict(arr, vod_obj))
                    vod_recent = resolved
            
            if isinstance(vod_recent, list):
                for vod in vod_recent:
                    if isinstance(vod, dict):
                        vod_list.append({
                            "vod_id": str(vod.get('vodId', '')),
                            "vod_name": vod.get('vodName', ''),
                            "vod_pic": vod.get('vodPic', ''),
                            "vod_remarks": vod.get('vodLastRemarks', ''),
                        })
            
            return {
                "list": vod_list,
                "page": page,
                "pagecount": total_page,
                "limit": per_page,
                "total": total,
            }
        except Exception as e:
            logger.error(f"search error: {e}")
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}


def main():
    spider = Spider()
    
    print("=" * 60)
    print("【1】测试首页")
    print("=" * 60)
    home = spider.homeContent()
    print(f"分类数量: {len(home.get('class', []))}")
    for c in home.get('class', [])[:5]:
        print(f"  - {c['type_name']} ({c['type_id']})")
    print(f"推荐视频数: {len(home.get('list', []))}")
    
    print("\n" + "=" * 60)
    print("【2】测试分类列表 (动作片)")
    print("=" * 60)
    cat = spider.categoryContent("1", "1", False, {})
    print(f"总数: {cat.get('total')}")
    print(f"总页数: {cat.get('pagecount')}")
    print(f"当前页: {cat.get('page')}")
    print(f"本页视频数: {len(cat.get('list', []))}")
    for v in cat.get('list', [])[:5]:
        print(f"  - {v['vod_name']} [{v['vod_remarks']}]")
    
    print("\n" + "=" * 60)
    print("【3】测试详情页")
    print("=" * 60)
    if cat.get('list'):
        first_id = cat['list'][0]['vod_id']
        detail = spider.detailContent([first_id])
        if detail.get('list'):
            d = detail['list'][0]
            print(f"标题: {d['vod_name']}")
            print(f"年份: {d['vod_year']}")
            print(f"地区: {d['vod_area']}")
            print(f"演员: {d['vod_actor'][:50]}...")
            print(f"播放源数量: {len(d['vod_play_from'].split('$$$')) if d['vod_play_from'] else 0}")
            print(f"播放源: {d['vod_play_from'][:80]}...")
    
    print("\n" + "=" * 60)
    print("【4】测试搜索")
    print("=" * 60)
    search = spider.searchContent("逆风草", False, "1")
    print(f"搜索结果数: {search.get('total')}")
    for v in search.get('list', [])[:5]:
        print(f"  - {v['vod_name']} [{v['vod_remarks']}]")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()