# -*- coding: utf-8 -*-
import sys
sys.path.append('..')

import re
import json
import base64
import hashlib
import hmac
import time
import uuid
import gzip
import os
import random
import requests
from base.spider import Spider

img_cache = {}

class Spider(Spider):
    def __init__(self):
        self.host = "https://adjust.cbpjoocbe.com"
        self.api_host = "https://api.51dj1.com"
        self.platform_key = "7961beb44246e3012ce228d6b5ced05a"
        self.version = "2.0.0"
        self.device_type = "web"
        self.session_id = uuid.uuid4().hex
        self.device_id = self.session_id
        self.token = ""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept": "*/*",
            "Origin": self.host,
            "Referer": self.host + "/home",
            "Content-Type": "application/octet-stream"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._all_videos = {}
        self._categories = []
        self._category_videos = {}  # 按分类存储视频
        self._loaded = False
        self.class_cache = None
        self.filter_cache = {}

    def init(self, extend=""):
        if extend:
            try:
                cfg = json.loads(extend)
                self.host = (cfg.get("site") or cfg.get("base_url") or self.host).rstrip("/")
                self.api_host = self.host.replace("adjust", "api")
                self.token = cfg.get("token", self.token)
                self.headers["Origin"] = self.host
                self.headers["Referer"] = self.host + "/home"
                self.session.headers.update(self.headers)
            except Exception:
                pass
        self._ensure_token()

    def _ensure_token(self):
        if self.token:
            return True
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import pad
            import random
            
            uid = ''.join(random.choice('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz') for _ in range(16)) + str(int(time.time() * 1000))
            
            key = b"BxJand%xf5h3sycH"
            iv = b"BxJand%xf5h3sycH"
            raw = json.dumps({"devID": uid, "sysType": "pc", "isAppStore": False}, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
            encrypted = base64.b64encode(AES.new(key, AES.MODE_CBC, iv).encrypt(pad(raw, 16))).decode()
            
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Referer": self.host + "/",
                "Origin": self.host,
            }
            r = self.session.post(self.api_host + "/api/app/mine/login/h5", json={"data": encrypted}, headers=headers, timeout=15, verify=False)
            if r.status_code == 200:
                j = r.json()
                if j.get("code") == 200:
                    data = j.get("data", {})
                    if isinstance(data, dict):
                        self.token = data.get("token", "")
                    elif isinstance(data, str):
                        self.token = data
                    if self.token:
                        self.headers["Authorization"] = self.token
                        self.session.headers.update(self.headers)
                        return True
            return False
        except Exception as e:
            print("[51短剧] token获取失败:", e)
            return False

    def _sha_bytes(self, arr):
        return hashlib.sha256(bytes.fromhex(''.join(format((int(v) + 256) % 256, 'x') for v in arr))).digest()

    def _hex_bytes(self, arr):
        return ''.join(format((int(v) + 256) % 256, 'x') for v in arr)

    def _decrypt_91_data(self, enc_data):
        """91guochan 风格的解密方法"""
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            import hashlib
            
            interface_key = '0a958fb9ac062420af6ba5f4caad779f'
            
            I = base64.b64decode(str(enc_data).replace('\n', '').replace('\r', ''))
            if len(I) < 12:
                return None
            
            e = list(interface_key.encode('utf-8')) + list(I[:12])
            n = list(self._sha_bytes(e)[8:24])
            M = len(e) // 2
            m = list(self._sha_bytes(n + e[:M]))
            a = list(self._sha_bytes(e[M:] + n))
            
            key = bytes.fromhex(self._hex_bytes(m[:8] + a[8:24] + m[24:]))
            iv = bytes.fromhex(self._hex_bytes(a[:4] + m[12:20] + a[28:]))
            
            ch = self._hex_bytes(list(I[12:]))
            ct = b''
            for i in range(0, len(ch), 5000):
                part = ch[i:i + 5000]
                if len(part) % 2:
                    part = part[:-1]
                if part:
                    ct += bytes.fromhex(part)
            
            pt = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(ct), 16)
            return json.loads(pt.decode('utf-8'))
        except Exception as e:
            print("[51短剧] 解密失败:", e)
            return None

    def _call_encrypted_api(self, path, params=None):
        """调用加密 API"""
        params = params or {}
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import pad
            import gzip
            import uuid
            import os
            
            rid = str(uuid.uuid4())
            iv = os.urandom(16)
            raw = json.dumps({
                "token": self.token or "",
                "deviceId": self.device_id,
                "data": params
            }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            compressed = gzip.compress(raw)
            
            # 使用 91guochan 的密钥派生方式
            key = b"2acf7e91e9864673"
            iv_aes = b"1c29882d3ddfcfd6"
            cipher = AES.new(key, AES.MODE_CBC, iv_aes)
            encrypted = cipher.encrypt(pad(compressed, 16))
            encrypted_b64 = base64.b64encode(encrypted).decode()
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, text/plain, */*",
                "Origin": self.host,
                "Referer": self.host + "/",
            }
            if self.token:
                headers["Authorization"] = self.token
            
            url = self.api_host + path
            data = {"data": encrypted_b64, "crypt": "1"}
            r = self.session.post(url, data=data, headers=headers, timeout=15, verify=False)
            
            if r.status_code == 200:
                j = r.json()
                if j.get("crypt") and j.get("data"):
                    decrypted = self._decrypt_91_data(j.get("data"))
                    if decrypted:
                        return decrypted
                return j
            return {}
        except Exception as e:
            print("[51短剧] API调用失败:", e)
            return {}

    def _decrypt_91guochan(self, enc_data):
        """91guochan 风格的数据解密"""
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            import hashlib
            
            interface_key = '0a958fb9ac062420af6ba5f4caad779f'
            
            # 解码 base64
            I = base64.b64decode(str(enc_data).replace('\n', '').replace('\r', ''))
            if len(I) < 12:
                return None
            
            # 计算密钥和 IV（91guochan 的派生方式）
            e = list(interface_key.encode('utf-8')) + list(I[:12])
            n = list(hashlib.sha256(bytes.fromhex(''.join(format((int(v) + 256) % 256, 'x') for v in e))).digest()[8:24])
            M = len(e) // 2
            m = list(hashlib.sha256(bytes.fromhex(''.join(format((int(v) + 256) % 256, 'x') for v in (n + e[:M])))).digest())
            a = list(hashlib.sha256(bytes.fromhex(''.join(format((int(v) + 256) % 256, 'x') for v in (e[M:] + n)))).digest())
            
            key = bytes.fromhex(''.join(format((int(v) + 256) % 256, 'x') for v in (m[:8] + a[8:24] + m[24:])))
            iv = bytes.fromhex(''.join(format((int(v) + 256) % 256, 'x') for v in (a[:4] + m[12:20] + a[28:])))
            
            # 解密数据
            ch = ''.join(format((int(v) + 256) % 256, 'x') for v in list(I[12:]))
            ct = b''
            for i in range(0, len(ch), 5000):
                part = ch[i:i + 5000]
                if len(part) % 2:
                    part = part[:-1]
                if part:
                    ct += bytes.fromhex(part)
            
            pt = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(ct), 16)
            return json.loads(pt.decode('utf-8'))
        except Exception as e:
            print("[51短剧] 解密失败:", e)
            return None

    def getName(self):
        return "51短剧"

    def _fetch_html(self, url):
        try:
            r = self.session.get(url, timeout=30, verify=False)
            r.encoding = 'utf-8'
            return r.text
        except Exception:
            return ""

    def _proxy_image(self, url):
        if not url:
            return ""
        if url.startswith("data:"):
            return url
        proxy = self.getProxyUrl()
        if not proxy:
            proxy = "http://127.0.0.1:9978/proxy?do=py"
        elif "?" not in proxy:
            proxy = proxy + "?do=py"
        elif "do=py" not in proxy:
            proxy = proxy + "&do=py"
        encoded = base64.b64encode(url.encode()).decode()
        return f"{proxy}&type=img&url={encoded}"

    def _list(self, data):
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        if isinstance(data.get("list"), list):
            return data["list"]
        if isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data.get("data"), list):
            return data["data"]
        if isinstance(data.get("data"), dict):
            return self._list(data["data"])
        return []

    def _vod(self, item):
        item = item or {}
        vid = str(item.get("id") or item.get("video_id") or item.get("drama_id") or "")
        name = item.get("name") or item.get("title") or item.get("vod_name") or vid
        pic = item.get("cover") or item.get("img_y") or item.get("img_x") or item.get("img") or item.get("pic") or ""
        return {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": self._proxy_image(pic) if pic else "",
            "vod_remarks": item.get("update_label") or item.get("remarks") or "",
            "vod_content": item.get("description") or item.get("intro") or "",
            "latest_episode_id": str(item.get("latest_episode_id") or "")
        }

    def _load_data(self):
        if hasattr(self, '_loaded') and self._loaded:
            return
        if not hasattr(self, '_all_videos'):
            self._all_videos = {}
        if not hasattr(self, '_categories'):
            self._categories = []
        if not hasattr(self, '_category_videos'):
            self._category_videos = {}
        
        # 从探索页获取数据（包含全部分类和更多视频）
        explore_url = self.host + "/explore-drama?page=1"
        html = self._fetch_html(explore_url)
        if not html:
            html = self._fetch_html(self.host)
            if not html:
                return
        
        data = self._parse_nuxt_data(html)
        if not data or not isinstance(data, list):
            return
        
        # 查找包含 list 和 total 的数据
        video_list = []
        total = 0
        
        for item in data:
            if isinstance(item, dict):
                # 检查是否有 list 字段
                if "list" in item and isinstance(item["list"], list):
                    lst = item["list"]
                    if lst and len(lst) > 0:
                        # 检查第一个元素是否有 video_id
                        first = lst[0] if lst else None
                        if isinstance(first, dict) and "video_id" in first:
                            video_list = lst
                            total = item.get("total", len(lst))
                            break
                        # 检查是否是 data 包装
                        inner_data = item.get("data")
                        if isinstance(inner_data, dict) and "list" in inner_data:
                            video_list = inner_data["list"]
                            total = inner_data.get("total", len(video_list))
                            break
        
        # 如果找到了视频列表，解析它
        if video_list:
            # 提取分类（从页面中的筛选标签）
            categories = []
            # 从 HTML 中提取分类标签
            theme_pattern = r'<span[^>]*data-active="[^"]*"[^>]*>([^<]+)</span>'
            theme_matches = re.findall(theme_pattern, html)
            # 过滤出分类名称
            seen = set()
            for name in theme_matches:
                name = name.strip()
                if name and name not in seen and len(name) <= 10:
                    seen.add(name)
                    categories.append({"type_id": str(len(categories) + 1), "type_name": name})
            
            # 如果没有提取到分类，使用默认分类
            if not categories:
                categories = [
                    {"type_id": "1", "type_name": "全部短剧"},
                    {"type_id": "2", "type_name": "热门推荐"},
                    {"type_id": "3", "type_name": "最新上线"}
                ]
            
            self._categories = categories
            self._category_videos = {c["type_id"]: [] for c in categories}
            
            # 解析视频列表
            for v in video_list:
                if isinstance(v, dict):
                    vid = str(v.get("video_id", ""))
                    if vid and vid.isdigit():
                        cover = v.get("cover", "")
                        if cover and not cover.startswith("http"):
                            cover = self.host + cover
                        video_info = {
                            "vod_id": vid,
                            "vod_name": v.get("title", ""),
                            "vod_pic": self._proxy_image(cover) if cover else "",
                            "vod_remarks": "",
                            "vod_content": v.get("intro", "")[:200] if v.get("intro") else "",
                            "latest_episode_id": str(v.get("latest_episode_id", ""))
                        }
                        self._all_videos[vid] = video_info
                        # 添加到第一个分类
                        if self._categories:
                            first_tid = self._categories[0]["type_id"]
                            self._category_videos[first_tid].append(video_info)
            
            self._loaded = True
            return
        
        # 如果探索页没有提取到数据，回退到首页解析
        html = self._fetch_html(self.host)
        if not html:
            return
        
        data = self._parse_nuxt_data(html)
        if not data or not isinstance(data, list):
            return
        
        target_idx = None
        for item in data:
            if isinstance(item, dict) and "data" in item:
                idx = item["data"]
                if isinstance(idx, int) and idx < len(data):
                    target = data[idx]
                    if isinstance(target, dict) and ("top_list" in target or "modules" in target):
                        target_idx = idx
                        break
        
        if target_idx is None:
            return
        
        target = data[target_idx]
        
        # 提取分类列表（从 modules）
        modules_idx = target.get("modules")
        if modules_idx is not None and isinstance(modules_idx, int) and modules_idx < len(data):
            modules_container = data[modules_idx]
            if isinstance(modules_container, dict):
                list_idx = modules_container.get("list")
                if isinstance(list_idx, int):
                    modules = data[list_idx]
                elif isinstance(list_idx, list):
                    modules = list_idx
                else:
                    modules = []
            elif isinstance(modules_container, list):
                modules = modules_container
            else:
                modules = []
            
            if isinstance(modules, list):
                for mod_idx in modules:
                    if isinstance(mod_idx, int) and mod_idx < len(data):
                        mod = data[mod_idx]
                        if isinstance(mod, dict):
                            tid = str(self._get_value(data, mod.get("id", "")))
                            name = self._get_value(data, mod.get("title", ""))
                            if tid and name:
                                self._categories.append({"type_id": tid, "type_name": str(name)})
                                if tid not in self._category_videos:
                                    self._category_videos[tid] = []
                                
                                items_idx = mod.get("items", [])
                                if isinstance(items_idx, int) and items_idx < len(data):
                                    actual_items = data[items_idx]
                                elif isinstance(items_idx, list):
                                    actual_items = items_idx
                                else:
                                    actual_items = []
                                
                                if isinstance(actual_items, list):
                                    for item_idx in actual_items:
                                        if isinstance(item_idx, int) and item_idx < len(data):
                                            v = data[item_idx]
                                            if isinstance(v, dict):
                                                vid = str(self._get_value(data, v.get("video_id", "")))
                                                if vid and vid.isdigit() and vid not in self._all_videos:
                                                    pic_url = self._get_value(data, v.get("cover", ""))
                                                    video_info = {
                                                        "vod_id": vid,
                                                        "vod_name": self._get_value(data, v.get("title", "")),
                                                        "vod_pic": self._proxy_image(pic_url) if pic_url else "",
                                                        "vod_remarks": "",
                                                        "vod_content": self._get_value(data, v.get("intro", ""))[:200],
                                                        "latest_episode_id": str(self._get_value(data, v.get("latest_episode_id", "")))
                                                    }
                                                    self._all_videos[vid] = video_info
                                                    self._category_videos[tid].append(video_info)
        
        # 如果分类为空，添加默认分类
        if not self._categories:
            self._categories = [
                {"type_id": "1", "type_name": "AI成人短剧"},
                {"type_id": "2", "type_name": "原创短剧"},
                {"type_id": "3", "type_name": "热门精选短剧"}
            ]
            self._category_videos = {c["type_id"]: [] for c in self._categories}
        
        # 提取 top_list（首页推荐）
        top_list_idx = target.get("top_list")
        if top_list_idx is not None and isinstance(top_list_idx, int) and top_list_idx < len(data):
            top_list = data[top_list_idx]
            if isinstance(top_list, list):
                for idx in top_list:
                    if isinstance(idx, int) and idx < len(data):
                        v = data[idx]
                        if isinstance(v, dict):
                            vid = str(self._get_value(data, v.get("video_id", "")))
                            if vid and vid.isdigit() and vid not in self._all_videos:
                                pic_url = self._get_value(data, v.get("cover", ""))
                                video_info = {
                                    "vod_id": vid,
                                    "vod_name": self._get_value(data, v.get("title", "")),
                                    "vod_pic": self._proxy_image(pic_url) if pic_url else "",
                                    "vod_remarks": "",
                                    "vod_content": self._get_value(data, v.get("intro", ""))[:200],
                                    "latest_episode_id": str(self._get_value(data, v.get("latest_episode_id", "")))
                                }
                                self._all_videos[vid] = video_info
                                if self._categories and len(self._categories) > 0:
                                    first_tid = self._categories[0]["type_id"]
                                    if first_tid not in self._category_videos:
                                        self._category_videos[first_tid] = []
                                    self._category_videos[first_tid].append(video_info)
        
        self._loaded = True

    def _get_value(self, data, idx):
        if isinstance(idx, int) and idx < len(data):
            return data[idx]
        return idx

    def _parse_nuxt_data(self, html):
        pattern = r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>'
        m = re.search(pattern, html, re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except Exception:
            return None

    def homeContent(self, filter=False):
        self._load_data()
        return {"class": self._categories, "list": list(self._all_videos.values())[:20]}

    def homeVideoContent(self):
        # 尝试从加密 API 获取数据
        data = self._call_encrypted_api("/api.php/api/theater/exploreList", {})
        # 调试：如果 data 是 dict，检查是否有 list
        if data and isinstance(data, dict):
            print("[51短剧] API返回keys:", list(data.keys()))
            # 检查 data.data 或 data.list
            items = self._list(data.get("data", data) if isinstance(data, dict) else data)
            if items:
                print("[51短剧] API返回items数量:", len(items))
                return {"list": [self._vod(x) for x in items[:20]]}
        # 回退到静态 HTML 解析
        print("[51短剧] 回退到静态解析")
        self._load_data()
        return {"list": list(self._all_videos.values())[:20]}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        page = int(pg) if str(pg).isdigit() else 1
        page_size = 24
        
        # 动态请求探索页
        explore_url = self.host + "/explore-drama?page=" + str(page)
        html = self._fetch_html(explore_url)
        
        videos = []
        total = 0
        
        if html:
            data = self._parse_nuxt_data(html)
            if data and isinstance(data, list):
                # 查找 list 数据
                for item in data:
                    if isinstance(item, dict):
                        if "list" in item and isinstance(item["list"], list):
                            lst = item["list"]
                            if lst and len(lst) > 0:
                                first = lst[0] if lst else None
                                if isinstance(first, dict) and "video_id" in first:
                                    total = item.get("total", len(lst))
                                    for v in lst:
                                        if isinstance(v, dict):
                                            vid = str(v.get("video_id", ""))
                                            if vid and vid.isdigit():
                                                cover = v.get("cover", "")
                                                if cover and not cover.startswith("http"):
                                                    cover = self.host + cover
                                                videos.append({
                                                    "vod_id": vid,
                                                    "vod_name": v.get("title", ""),
                                                    "vod_pic": self._proxy_image(cover) if cover else "",
                                                    "vod_remarks": "",
                                                    "vod_content": v.get("intro", "")[:200] if v.get("intro") else "",
                                                    "latest_episode_id": str(v.get("latest_episode_id", ""))
                                                })
                                    break
                        # 检查 data 包装
                        inner_data = item.get("data")
                        if isinstance(inner_data, dict) and "list" in inner_data:
                            lst = inner_data["list"]
                            if lst and len(lst) > 0:
                                total = inner_data.get("total", len(lst))
                                for v in lst:
                                    if isinstance(v, dict):
                                        vid = str(v.get("video_id", ""))
                                        if vid and vid.isdigit():
                                            cover = v.get("cover", "")
                                            if cover and not cover.startswith("http"):
                                                cover = self.host + cover
                                            videos.append({
                                                "vod_id": vid,
                                                "vod_name": v.get("title", ""),
                                                "vod_pic": self._proxy_image(cover) if cover else "",
                                                "vod_remarks": "",
                                                "vod_content": v.get("intro", "")[:200] if v.get("intro") else "",
                                                "latest_episode_id": str(v.get("latest_episode_id", ""))
                                            })
                                break
        
        # 如果提取失败，回退到缓存
        if not videos:
            self._load_data()
            if tid and tid in self._category_videos:
                items = self._category_videos.get(tid, [])
            else:
                items = list(self._all_videos.values())
            
            total = len(items)
            pagecount = (total + page_size - 1) // page_size if total > 0 else 1
            start = (page - 1) * page_size
            end = start + page_size
            paginated = items[start:end] if items else []
            return {"page": page, "pagecount": pagecount, "limit": page_size, "total": total, "list": paginated}
        
        pagecount = (total + page_size - 1) // page_size if total > 0 else 1
        
        return {"page": page, "pagecount": pagecount, "limit": page_size, "total": total, "list": videos}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids and isinstance(ids, list) else str(ids)
        if not vid:
            return {"list": []}
        self._load_data()
        detail = self._all_videos.get(vid, {})
        if not detail:
            html = self._fetch_html(self.host + "/drama-detail/" + vid + "/")
            name = re.search(r'<title>(.*?)</title>', html)
            if name:
                detail["vod_name"] = name.group(1).split(" - ")[0].strip()
            pic = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            if pic:
                detail["vod_pic"] = pic.group(1)
        vod_name = detail.get("vod_name", "51短剧")
        vod_pic = detail.get("vod_pic", "")
        episodes = []
        html = self._fetch_html(self.host + "/drama-play?id=" + vid)
        if html:
            play_url = re.search(r'<source[^>]+src="([^"]+)"', html)
            if play_url:
                episodes.append("全集$%s" % play_url.group(1))
        if not episodes:
            m3u8 = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html) if html else None
            if m3u8:
                episodes.append("全集$%s" % m3u8.group(1))
        if not episodes:
            episodes.append("全集$%s" % vid)
        vod_play_url = "#".join(episodes) if episodes else ""
        vod = {
            "vod_id": vid,
            "vod_name": vod_name,
            "vod_pic": self._proxy_image(vod_pic) if vod_pic else "",
            "vod_play_from": "51短剧",
            "vod_play_url": vod_play_url,
            "vod_content": detail.get("vod_content", ""),
            "vod_remarks": ("共%d集" % len(episodes)) if episodes else ""
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg=1):
        self._load_data()
        results = []
        key_lower = key.lower()
        for vid, info in self._all_videos.items():
            if key_lower in info.get("vod_name", "").lower():
                results.append({"vod_id": vid, "vod_name": info.get("vod_name", ""), "vod_pic": info.get("vod_pic", ""), "vod_remarks": ""})
        return {"list": results[:20]}

    def playerContent(self, flag, id, vipFlags=None):
        if isinstance(id, str) and id.startswith("http"):
            return {"playUrl": "", "url": id, "parse": 0, "header": self.headers, "position": "0"}
        html = self._fetch_html(self.host + "/drama-play?id=" + str(id))
        if html:
            m3u8 = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
            if m3u8:
                return {"playUrl": "", "url": m3u8.group(1), "parse": 0, "header": self.headers, "position": "0"}
            mp4 = re.search(r'(https?://[^\s"\']+\.mp4[^\s"\']*)', html)
            if mp4:
                return {"playUrl": "", "url": mp4.group(1), "parse": 0, "header": self.headers, "position": "0"}
        return {"playUrl": "", "msg": "无法获取播放地址: %s" % id}

    def localProxy(self, param):
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            type_ = param.get('type')
            url = param.get('url')
            if type_ == 'img':
                try:
                    real_url = base64.b64decode(url).decode('utf-8')
                except Exception:
                    real_url = url
                if not real_url.startswith('http'):
                    return [404, 'text/plain', b'Invalid URL']
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": self.host + "/"}
                res = requests.get(real_url, headers=headers, timeout=20)
                if res.status_code != 200:
                    return [404, 'text/plain', b'Image not found']
                data = res.content
                key = b"f5d965df75336270"
                iv = b"97b60394abc2fbe1"
                cipher = AES.new(key, AES.MODE_CBC, iv)
                decrypted = unpad(cipher.decrypt(data), AES.block_size)
                if decrypted[:3] == b"\xff\xd8\xff":
                    return [200, 'image/jpeg', decrypted, {'Content-Length': str(len(decrypted))}]
                if decrypted[:4] == b"\x89PNG":
                    return [200, 'image/png', decrypted, {'Content-Length': str(len(decrypted))}]
                if decrypted[:4] == b"GIF8":
                    return [200, 'image/gif', decrypted, {'Content-Length': str(len(decrypted))}]
                return [200, 'image/jpeg', decrypted, {'Content-Length': str(len(decrypted))}]
            return [404, 'text/plain', b'Unknown type']
        except Exception as e:
            return [500, 'text/plain', str(e).encode()]

    def destroy(self):
        global img_cache
        img_cache.clear()
        if hasattr(self, 'session'):
            self.session.close()