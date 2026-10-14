import requests
from bs4 import BeautifulSoup
import urllib3
import urllib.parse
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Spider:
    def __init__(self):
        self.host = "https://avtoday.io"
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': self.host
        }

    def getName(self): return "AVToday"
    def getDependence(self): return ['requests', 'beautifulsoup4']
    def init(self, extend=""): pass
    def isVideoCanPlay(self, url): return True
    def homeVideoContent(self): return self.categoryContent("new", 1, False, {})
    
    def homeContent(self, filter):
        return {"class": [
            {"type_id": "new", "type_name": "🎥 新片上架"},
            {"type_id": "hot", "type_name": "🔥 人氣影片"},
            {"type_id": "catalog/FC2#0", "type_name": "FC2"},
            {"type_id": "catalog/%E7%84%A1%E7%A2%BC#0", "type_name": "無碼影片"},
            {"type_id": "catalog/%E4%B8%AD%E6%96%87%E5%AD%97%E5%B9%95", "type_name": "🔠 中文字幕"}
        ]}

    def parse_list(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        vod_list = []
        items = soup.find_all('div', class_=lambda x: x and 'thumbnail' in x)
        
        for item in items:
            a_tag = item.find('a', href=lambda x: x and '/video/' in x)
            if not a_tag: continue
            vod_id = a_tag['href'].split('/')[-1]
            
            title_div = item.find('div', class_='video-title')
            name = title_div.get_text(strip=True) if title_div else a_tag.get_text(strip=True)
            
            if "廣告" in name or "直播" in name: continue

            pic = ""
            video_tag = item.find('video', class_='preview-video')
            if video_tag and video_tag.get('style'):
                style = video_tag.get('style')
                img_match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style)
                if img_match: pic = img_match.group(1)
            
            if not pic:
                img = item.find('img')
                if img: pic = img.get('data-src') or img.get('src') or ""
            
            if pic.startswith('//'): pic = "https:" + pic
            elif pic.startswith('/') and not pic.startswith('//'): pic = self.host + pic

            remark = ""
            duration = item.find('span', class_='video-duration')
            if duration: remark = duration.get_text(strip=True)

            vod_list.append({
                "vod_id": vod_id,
                "vod_name": name[:80],
                "vod_pic": pic,
                "vod_remarks": remark if remark else "HD"
            })
        return vod_list

    def categoryContent(self, tid, pg, filter, extend):
        # 確保 pg 是數字型態
        p = int(pg)
        
        # 建立基礎 URL
        if tid == "new":
            # 針對首頁新片：https://avtoday.io/?page=2
            base_url = f"{self.host}/"
        else:
            # 針對分類：確保路徑結尾有 / 避免 301 重定向問題
            # 變成 https://avtoday.io/catalog/FC2/?page=2
            clean_tid = tid.strip('/')
            base_url = f"{self.host}/{clean_tid}/"

        # 構造帶參數的請求 URL
        params = {'page': p}
        
        try:
            # 使用 requests 的 params 參數會自動處理 ? 與 & 的拼接，最安全
            r = requests.get(base_url, params=params, headers=self.header, timeout=10, verify=False)
            r.encoding = 'utf-8'
            
            vod_list = self.parse_list(r.text)
            
            # 必須回傳這四個數值，TVBox 的翻頁按鈕才會解鎖
            return {
                "page": p,
                "pagecount": p + 1, # 強制讓 TVBox 覺得還有下一頁
                "limit": len(vod_list),
                "total": 999,
                "list": vod_list
            }
        except Exception as e:
            print(f"Error: {e}")
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        # 放棄搜索，返回空列表避免報錯
        return {"list": []}

    def detailContent(self, ids):
        url = f"{self.host}/video/{ids[0]}"
        try:
            r = requests.get(url, headers=self.header, timeout=10, verify=False)
            soup = BeautifulSoup(r.text, 'html.parser')
            img = soup.find('meta', property='og:image')
            return {"list": [{
                "vod_id": ids[0],
                "vod_name": soup.find('h1').text.strip(),
                "vod_pic": img['content'] if img else "",
                "vod_play_from": "AVToday",
                "vod_play_url": f"播放$ {ids[0]}"
            }]}
        except: return {"list": []}

    def playerContent(self, jflag, ids, vip):
        return {"parse": 1, "url": f"{self.host}/video/{ids}", "header": self.header}

    def localProxy(self, path):
        return [200, "video/MP2T", "", ""]