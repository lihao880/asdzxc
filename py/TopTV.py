# coding=utf-8
import sys
import re
import requests
import json
import base64
from bs4 import BeautifulSoup

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    host = "https://toptv15.cyou"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': "https://toptv15.cyou/",
    }

    def getName(self):
        return "TopTV"

    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        result = {}
        result['class'] = [
            {"type_name": "国产自拍", "type_id": "1"},
            {"type_name": "国产传媒", "type_id": "2"},
            {"type_name": "探花系列", "type_id": "3"},
            {"type_name": "人妻熟女", "type_id": "4"},
            {"type_name": "日本无码", "type_id": "5"},
            {"type_name": "美乳巨乳", "type_id": "6"},
            {"type_name": "强制侵犯", "type_id": "7"},
            {"type_name": "制服诱惑", "type_id": "8"},
            {"type_name": "绝色佳人", "type_id": "9"},
            {"type_name": "家庭乱伦", "type_id": "10"},
            {"type_name": "绝顶潮吹", "type_id": "11"},
            {"type_name": "网红主播", "type_id": "12"},
            {"type_name": "剧情三级", "type_id": "13"},
            {"type_name": "欧美精品", "type_id": "14"},
            {"type_name": "成人动漫", "type_id": "15"}
        ]
        try:
            res = requests.get(self.host, headers=self.headers, timeout=10)
            res.encoding = 'utf-8'
            result['list'] = self.parseList(res.text)
        except:
            result['list'] = []
        return result

    def categoryContent(self, tid, pg, filter, extend):
        url = "{0}/index.php/vod/type/id/{1}/page/{2}.html".format(self.host, tid, pg)
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            res.encoding = 'utf-8'
            return {'list': self.parseList(res.text), 'page': int(pg), 'pagecount': 99}
        except:
            return {'list': [], 'page': int(pg)}

    def detailContent(self, ids):
        id = ids[0]
        url = self.host + id if id.startswith("/") else "{0}/index.php/vod/detail/id/{1}.html".format(self.host, id)
        res = requests.get(url, headers=self.headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        title_node = soup.select_one('p.is-size-4') or soup.select_one('h1')
        pic_node = soup.select_one('img.lazyload')
        vod = {
            "vod_id": id,
            "vod_name": self.cleanName(title_node.text) if title_node else "未知",
            "vod_pic": self.fixUrl(pic_node.get('data-src') or pic_node.get('src')) if pic_node else "",
            "vod_play_from": "TopPlayer", 
            "vod_play_url": ""
        }
        url_list = []
        play_links = soup.select('a[href*="/vod/play/id/"]')
        seen = set()
        for i, link in enumerate(play_links):
            href = link['href']
            if href not in seen:
                url_list.append("播放{0}${1}".format(i+1, href))
                seen.add(href)
        vod['vod_play_url'] = "#".join(url_list)
        return {"list": [vod]}

    def searchContent(self, key, quick, pg=1):
        url = "{0}/index.php/vod/search.html?wd={1}&page={2}".format(self.host, key, pg)
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            res.encoding = 'utf-8'
            return {"list": self.parseList(res.text)}
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        url = self.host + id if id.startswith("/") else id
        res = requests.get(url, headers=self.headers, timeout=10)
        match = re.search(r'player_aaaa=(.*?)</script>', res.text)
        if match:
            try:
                config = json.loads(match.group(1))
                p_url = config.get('url', '')
                if not p_url.startswith('http') and len(p_url) > 10:
                    p_url = base64.b64decode(p_url).decode('utf-8')
                return {"parse": 0, "url": p_url, "header": self.headers}
            except: pass
        return {"parse": 1, "url": url, "header": ""}

    def parseList(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        items = []
        for box in soup.select('div.column.is-half-mobile'):
            a = box.find('a', href=re.compile(r'/vod/detail/'))
            if not a: continue
            img = box.find('img')
            pic = self.fixUrl(img.get('data-src') or img.get('src')) if img else ""
            name = self.cleanName(a.get('title') or a.text)
            tag = box.find('span', class_='is-video-tag')
            items.append({"vod_id": a['href'], "vod_name": name, "vod_pic": pic, "vod_remarks": tag.text.strip() if tag else ""})
        return items

    def cleanName(self, name):
        if not name: return ""
        # 使用字符编码避开换行转义陷阱
        n = name.replace('\x0a', ' ').replace('\x0d', ' ')
        return re.sub(r'\d{4}-\d{2}-\d{2}.*', '', n).strip()

    def fixUrl(self, url):
        if not url: return ""
        if url.startswith('//'): return "https:" + url
        if url.startswith('/'): return self.host + url
        return url