# coding=utf-8
import re
import json
import urllib.request
import urllib.parse
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base.spider import Spider

BASE = "https://ncfzuxrbko.cc/"
AES_KEY = b'f5d965df75336270'
AES_IV = b'97b60394abc2fbe1'

class Spider(Spider):
    def getName(self):
        return "MissAVt"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": BASE + "/"
        }

    def getDependence(self):
        return []

    def header(self):
        return self.headers

    def _get(self, url):
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode('utf-8', errors='ignore')
        except:
            return ""

    def _fix(self, u):
        if not u:
            return ""
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return BASE + u
        return u

    def _build_proxy_pic(self, pic_url):
        """将原始加密图片 URL 转换为 TVBox 本地代理 URL"""
        if not pic_url:
            return ""
        clean_url = pic_url.replace("pics://", "https://") if pic_url.startswith("pics://") else pic_url
        img_b64 = base64.b64encode(clean_url.encode()).decode('utf-8')
        return f"proxy://do=py&site={self.getName()}&type=img&url={img_b64}"

    def _parse_list(self, html):
        if not html:
            return []
        results, seen = [], set()
        
        blocks = re.split(r'(?=<a[^>]+href=["\'][^"\']*?/watch/)', html)
        
        for block in blocks:
            if "/watch/" not in block:
                continue
                
            href_match = re.search(r'href=["\'][^"\']*?/watch/([^"\'>/]+)/?["\']', block)
            if not href_match:
                continue
                
            vod_id = href_match.group(1).strip()
            if not vod_id or len(vod_id) < 2 or vod_id in seen:
                continue
            seen.add(vod_id)

            pic = ""
            mp = re.search(r'data-src=["\']([^"\']+)["\']', block)
            if mp:
                pic = self._fix(mp.group(1))
                
            title = vod_id
            ma = re.search(r'class=["\'][^"\']*?line-clamp-2[^"\']*?["\'][^>]*>([\s\S]*?)</a>', block)
            if ma:
                title = ma.group(1).strip()
                title = re.sub(r'<[^>]+>', '', title)
            else:
                malt = re.search(r'<img[^>]+alt=["\']([^"\']{2,})["\']', block)
                if malt:
                    title = malt.group(1).strip()

            duration = ""
            md = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', block)
            if md:
                duration = md.group(1)

            proxy_pic = self._build_proxy_pic(pic)
            results.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": proxy_pic,
                "vod_remarks": duration
            })
            
        return results

    def localProxy(self, params):
        """本地代理图片解密引擎"""
        if params.get('type') == 'img':
            try:
                img_url = base64.b64decode(params.get('url')).decode('utf-8')
                img_headers = self.headers.copy()
                img_headers.update({'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8'})
                req = urllib.request.Request(img_url, headers=img_headers)
                
                with urllib.request.urlopen(req, timeout=10) as r:
                    raw_data = r.read()

                if raw_data.startswith(b'\xff\xd8') or raw_data.startswith(b'\x89PNG') or raw_data.startswith(b'GIF8'):
                    mime = "image/jpeg" if raw_data.startswith(b'\xff\xd8') else ("image/png" if raw_data.startswith(b'\x89PNG') else "image/gif")
                    return [200, mime, raw_data]

                if raw_data.startswith(b'"') or b' ' in raw_data[:10]:
                    raw_data = base64.b64decode(raw_data.strip(b'"\' \n\r'))

                cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
                decrypted = cipher.decrypt(raw_data)
                try:
                    decrypted = unpad(decrypted, AES.block_size)
                except:
                    pass

                mime = "image/jpeg"
                if decrypted.startswith(b'\x89PNG'):
                    mime = "image/png"
                elif decrypted.startswith(b'GIF8'):
                    mime = "image/gif"
                elif decrypted.startswith(b'RIFF') and b'WEBP' in decrypted[8:12]:
                    mime = "image/webp"

                return [200, mime, decrypted]
            except Exception as e:
                print(f"本地代理图片解密异常: {e}")
        return [404, "text/plain", "Not Found"]

    def _m3u8(self, slug):
        html = self._get(f"{BASE}/embed/{slug}/")
        m = re.search(r'<source\s+src=["\']([^"\']+\.m3u8[^"\']*)["\']', html)
        return m.group(1) if m else ""

    def homeVideoContent(self):
        return self.homeContent(False)

    def homeContent(self, filter):
        html = self._get(BASE + "/")
        classes = [
            {"type_id": "1", "type_name": "📺 首页"},
            {"type_id": "sort_hot", "type_name": "🔥 当前最热"},
            {"type_id": "sort_renew", "type_name": "🆕 最新更新"},
            {"type_id": "sort_month_hot", "type_name": "📈 本月最热"},
            {"type_id": "category_censored", "type_name": "🔞 有码AV"},
            {"type_id": "category_chinese-subtitle", "type_name": "🇨🇳 中文字幕"},
            {"type_id": "category_renqishunv", "type_name": "👩 人妻熟女"},
            {"type_id": "category_zhifuyouhuo", "type_name": "👔 制服诱惑"},
            {"type_id": "category_tiaojiaoSM", "type_name": "⛓️ 调教SM"},
            {"type_id": "category_jiatingluanlun", "type_name": "🏠 家庭乱伦"},
            {"type_id": "category_madou", "type_name": "🎬 麻豆传媒"},
            {"type_id": "category_swag", "type_name": "🎬 SWAG"},
            {"type_id": "category_sweet-heart-vlog", "type_name": "🍬 糖心vlog"},
            {"type_id": "category_ed-mosaic", "type_name": "🎬 ED MOSAIC"},
            {"type_id": "category_douyin", "type_name": "📱 抖阴"},
            {"type_id": "category_91-studio", "type_name": "🎬 91制片厂"},
            {"type_id": "category_mr-rabbit", "type_name": "🐰 兔子先生"},
            {"type_id": "category_domestic-media", "type_name": "🎬 国产传媒"},
            {"type_id": "category_xingbatanhua", "type_name": "🌺 杏吧探花"},
            {"type_id": "category_uncensored-leak", "type_name": "💦 无码流出"},
            {"type_id": "category_fc2", "type_name": "🎥 FC2"},
            {"type_id": "category_tokyohot", "type_name": "🔥 东京热"},
            {"type_id": "category_marriedslash", "type_name": "🔪 人妻斩"},
            {"type_id": "category_heyzo", "type_name": "🎬 HEYZO"},
            {"type_id": "category_reducing-mosaic", "type_name": "🔓 无码破解"},
            {"type_id": "category_10musume", "type_name": "🎬 10musume"},
            {"type_id": "category_pacopacomama", "type_name": "👩 pacopacomama"},
            {"type_id": "category_xxx-av", "type_name": "🎬 xxx-av"},
            {"type_id": "category_caribbeancompr", "type_name": "🎬 Caribbeancompr"},
            {"type_id": "category_caribbeancom", "type_name": "🎬 Caribbeancom"},
            {"type_id": "category_1pondo", "type_name": "📖 一本道"},
            {"type_id": "category_siro", "type_name": "🎬 SIRO"},
            {"type_id": "category_luxu", "type_name": "🎬 lulu"},
            {"type_id": "category_gana", "type_name": "🎬 gana"},
            {"type_id": "category_prestige-premium", "type_name": "🎬 PRESTIGE PREMIUM"},
            {"type_id": "category_s-cute", "type_name": "🎬 S-CUTE"},
            {"type_id": "category_ara", "type_name": "🎬 ARA"},
            {"type_id": "actresses_hot", "type_name": "👩 AV女优"},
            {"type_id": "tags", "type_name": "🏷️ AV标签"},
            {"type_id": "articles", "type_name": "📝 AV影评"},
        ]
        return {"class": classes, "list": self._parse_list(html)[:24], "filters": {}}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        type_map = {
            "1": "",
            "sort_hot": "/sort/hot/",
            "sort_renew": "/sort/renew/",
            "sort_month_hot": "/sort/month_hot/",
            "category_censored": "/category/censored/",
            "category_chinese-subtitle": "/category/chinese-subtitle/",
            "category_renqishunv": "/category/renqishunv/",
            "category_zhifuyouhuo": "/category/zhifuyouhuo/",
            "category_tiaojiaoSM": "/category/tiaojiaoSM/",
            "category_jiatingluanlun": "/category/jiatingluanlun/",
            "category_madou": "/category/madou/",
            "category_swag": "/category/swag/",
            "category_sweet-heart-vlog": "/category/sweet-heart-vlog/",
            "category_ed-mosaic": "/category/ed-mosaic/",
            "category_douyin": "/category/douyin/",
            "category_91-studio": "/category/91-studio/",
            "category_mr-rabbit": "/category/mr-rabbit/",
            "category_domestic-media": "/category/domestic-media/",
            "category_xingbatanhua": "/category/xingbatanhua/",
            "category_uncensored-leak": "/category/uncensored-leak/",
            "category_fc2": "/category/fc2/",
            "category_tokyohot": "/category/tokyohot/",
            "category_marriedslash": "/category/marriedslash/",
            "category_heyzo": "/category/heyzo/",
            "category_reducing-mosaic": "/category/reducing-mosaic/",
            "category_10musume": "/category/10musume/",
            "category_pacopacomama": "/category/pacopacomama/",
            "category_xxx-av": "/category/xxx-av/",
            "category_caribbeancompr": "/category/caribbeancompr/",
            "category_caribbeancom": "/category/caribbeancom/",
            "category_1pondo": "/category/1pondo/",
            "category_siro": "/category/siro/",
            "category_luxu": "/category/luxu/",
            "category_gana": "/category/gana/",
            "category_prestige-premium": "/category/prestige-premium/",
            "category_s-cute": "/category/s-cute/",
            "category_ara": "/category/ara/",
            "actresses_hot": "/actresses/hot/",
            "tags": "/tags/",
            "articles": "/articles/",
        }
        base_path = type_map.get(tid, "")
        if base_path == "":
            url = BASE + "/" if page == 1 else f"{BASE}/?page={page}"
        else:
            url = f"{BASE}{base_path}" if page == 1 else f"{BASE}{base_path.rstrip('/')}/{page}/"
        html = self._get(url)
        video_list = self._parse_list(html)
        pagecount = 100
        if html:
            m = re.search(r'第\d+/(\d+)\s*页', html)
            if m:
                try:
                    pagecount = int(m.group(1))
                except:
                    pass
        return {
            "page": page,
            "pagecount": pagecount,
            "limit": len(video_list),
            "total": pagecount * 20,
            "list": video_list
        }

    def detailContent(self, ids):
        result = {"list": []}
        for vod_id in ids:
            html = self._get(f"{BASE}/watch/{vod_id}/")
            if not html:
                continue
                
            title = vod_id
            m = re.search(r'<h1[^>]*>\s*([^<]+)\s*</h1>', html)
            if m:
                title = m.group(1).strip()
            
            pic = ""
            m = re.search(r'"thumbnailUrl"\s*:\s*"([^"]+)"', html)
            if not m:
                m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
            if m:
                pic = self._fix(m.group(1))
            
            proxy_pic = self._build_proxy_pic(pic)
            
            desc = ""
            m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html)
            if m:
                desc = m.group(1).strip()
            
            duration = ""
            m = re.search(r'"times"\s*:\s*"([^"]+)"', html)
            if m:
                duration = m.group(1)
            
            m3u8 = self._m3u8(vod_id)
            play_url = f"默认${m3u8}" if m3u8 else f"默认${BASE}/watch/{vod_id}/"
            
            result["list"].append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": proxy_pic,
                "vod_content": desc,
                "vod_remarks": duration,
                "vod_play_from": "默认",
                "vod_play_url": play_url
            })
        return result

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        encoded_key = urllib.parse.quote(key)
        url = f"{BASE}/search/{encoded_key}/" if page <= 1 else f"{BASE}/search/{encoded_key}/?page={page}"
        return {"list": self._parse_list(self._get(url)), "page": page, "pagecount": 20}

    def playerContent(self, flag, id, vipFlags):
        play_url = id
        if ".m3u8" not in id:
            m = re.search(r'/watch/([^/]+)/?$', id)
            slug = m.group(1) if m else id.rstrip('/').split('/')[-1]
            m3u8 = self._m3u8(slug)
            if m3u8:
                play_url = m3u8
        return {
            "parse": 0,
            "url": play_url,
            "header": json.dumps(self.headers)
        }

    def destroy(self):
        pass