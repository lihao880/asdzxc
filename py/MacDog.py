# coding: utf-8
"""
MacDog 影视聚合站 - TVBox/FongMi 爬虫源
站点: https://game.fanjugou12.top/
API: https://macapi2.com (备用: https://macapi1.com)
类型: 聚合影视 + 小说
版本: 1.0
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.api = "https://macapi2.com"
        self.fallback_api = "https://macapi1.com"
        self.host = "https://game.fanjugou12.top"
        self.current_api = self.api
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/',
            'Origin': self.host,
        }
        
        self.databases = []
        self.classes = []
        self.novel_sources = ['sis', 'pixiv']
        self.type_icons = {
            'av': '🔞',
            'movies': '🎬',
            'art': '🎨'
        }
        self.type_order = ['av', 'movies', 'art']
        self._init_classes()
        self.filters = {}
        self._init_filters()
    
    def _init_classes(self):
        self.video_classes = []
    
    def _init_filters(self):
        for cls in self.classes:
            tid = cls['type_id']
            if tid.startswith('novel_'):
                self.filters[tid] = [
                    {'key': 'category', 'name': '分类', 'value': [
                        {'n': '全部', 'v': ''},
                        {'n': '绿意盎然', 'v': '绿意盎然'},
                        {'n': '都市情缘', 'v': '都市情缘'},
                        {'n': '禁忌之恋', 'v': '禁忌之恋'},
                        {'n': '修真仙侠', 'v': '修真仙侠'},
                        {'n': '侠骨柔情', 'v': '侠骨柔情'},
                    ]}
                ]
            else:
                self.filters[tid] = [
                    {'key': 'sort', 'name': '排序', 'value': [
                        {'n': '最新', 'v': 'new'},
                        {'n': '人气', 'v': 'hot'},
                        {'n': '推荐', 'v': 'playNum'},
                    ]}
                ]
    
    def getName(self):
        return "MacDog 聚合站"
    
    def getDependence(self):
        return []
    
    def init(self, extend=''):
        try:
            self._get_databases()
        except:
            pass
        return {}
    
    def _get_databases(self):
        if self.databases:
            return self.databases
        data = self._api_request('/maccms/databases')
        if data and 'databases' in data:
            self.databases = data['databases']
            
            groups = {}
            for db in self.databases:
                if db.get('data_count', 0) <= 0:
                    continue
                db_type = db.get('type', 'other')
                if db_type not in groups:
                    groups[db_type] = []
                groups[db_type].append(db)
            
            self.classes = []
            for db_type in self.type_order:
                if db_type in groups:
                    icon = self.type_icons.get(db_type, '📦')
                    for db in groups[db_type]:
                        dbname = db.get('dbname')
                        name = db.get('name', dbname)
                        self.classes.append({
                            'type_id': dbname,
                            'type_name': f'{icon} {name}'
                        })
            
            if 'other' in groups:
                for db in groups['other']:
                    dbname = db.get('dbname')
                    name = db.get('name', dbname)
                    self.classes.append({
                        'type_id': dbname,
                        'type_name': f'📦 {name}'
                    })
            
            for src in self.novel_sources:
                self.classes.append({
                    'type_id': f'novel_{src}',
                    'type_name': f'📖 小说-{src.upper()}'
                })
            
            self._init_filters()
        return self.databases
    
    def _api_request(self, path, params=None, method='GET', data=None):
        url = f"{self.current_api}{path}"
        try:
            if method.upper() == 'POST':
                resp = self.fetch(url, headers=self.headers, data=data, method='POST')
            else:
                resp = self.fetch(url, headers=self.headers, params=params)
            
            if resp:
                if hasattr(resp, 'status_code') and resp.status_code == 200:
                    if hasattr(resp, 'json'):
                        return resp.json()
                elif isinstance(resp, dict):
                    return resp
                elif hasattr(resp, 'json'):
                    return resp.json()
            
            if self.current_api == self.api:
                self.current_api = self.fallback_api
                url = f"{self.current_api}{path}"
                if method.upper() == 'POST':
                    resp = self.fetch(url, headers=self.headers, data=data, method='POST')
                else:
                    resp = self.fetch(url, headers=self.headers, params=params)
                if resp:
                    if hasattr(resp, 'status_code') and resp.status_code == 200:
                        if hasattr(resp, 'json'):
                            return resp.json()
                    elif isinstance(resp, dict):
                        return resp
                    elif hasattr(resp, 'json'):
                        return resp.json()
        except Exception as e:
            print(f"_api_request error: {e}")
        return None
    
    def _parse_extend(self, extend):
        if extend is None:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except:
                pass
            try:
                if extend.startswith('{') and extend.endswith('}'):
                    extend = extend[1:-1]
                parts = extend.split('&')
                result = {}
                for p in parts:
                    if '=' in p:
                        k, v = p.split('=', 1)
                        result[k.strip()] = v.strip()
                return result
            except:
                return {}
        return {}
    
    def _fix_url(self, url):
        if not url:
            return ''
        if url.startswith('http://') or url.startswith('https://'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host.rstrip('/') + url
        return self.host.rstrip('/') + '/' + url.lstrip('/')
    
    def _duration(self, seconds):
        try:
            s = int(seconds or 0)
            h, rem = divmod(s, 3600)
            m, sec = divmod(rem, 60)
            return ('%d:%02d:%02d' % (h, m, sec)) if h else ('%d:%02d' % (m, sec))
        except:
            return ''
    
    def homeContent(self, filter=False):
        self._get_databases()
        return {'class': self.classes, 'filters': self.filters}
    
    def getHomeContent(self, filter=False):
        return self.homeContent(filter)
    
    def homeVideoContent(self):
        result = {'list': []}
        try:
            self._get_databases()
            if self.classes:
                for cls in self.classes:
                    if not cls['type_id'].startswith('novel_'):
                        first_db = cls['type_id']
                        break
                else:
                    return result
                data = self._api_request(f'/maccms/json/{first_db}/', {'page': 1})
                if data and data.get('code') == 1:
                    for item in data.get('list', [])[:20]:
                        result['list'].append({
                            'vod_id': f"{first_db}@@{item.get('vod_id', '')}",
                            'vod_name': item.get('vod_name', ''),
                            'vod_pic': item.get('vod_pic', ''),
                            'vod_remarks': self._duration(item.get('vod_duration')),
                            'vod_year': item.get('vod_year', ''),
                            'type_name': item.get('type_name', ''),
                        })
        except Exception as e:
            print(f"homeVideoContent error: {e}")
        return result
    
    def categoryContent(self, tid, pg=None, filter=False, extend=None):
        result = {'list': [], 'page': 1, 'pagecount': 1, 'total': 0}
        try:
            pg = int(pg or 1)
            ext = self._parse_extend(extend)
            tid = str(tid or '')
            
            if tid.startswith('novel_'):
                source = tid.replace('novel_', '')
                return self._novel_category(source, pg, ext)
            
            params = {'page': pg}
            sort = ext.get('sort', '')
            if sort:
                params['sort'] = sort
            
            data = self._api_request(f'/maccms/json/{tid}/', params)
            if data and data.get('code') == 1:
                result['page'] = data.get('page', 1)
                result['pagecount'] = data.get('pagecount', 1)
                result['total'] = data.get('total', 0)
                for item in data.get('list', []):
                    result['list'].append({
                        'vod_id': f"{tid}@@{item.get('vod_id', '')}",
                        'vod_name': item.get('vod_name', ''),
                        'vod_pic': item.get('vod_pic', ''),
                        'vod_remarks': self._duration(item.get('vod_duration')),
                        'vod_year': item.get('vod_year', ''),
                        'type_name': item.get('type_name', ''),
                        'vod_score': item.get('vod_score', ''),
                        'vod_hits': item.get('vod_hits', 0),
                    })
        except Exception as e:
            print(f"categoryContent error: {e}")
        return result
    
    def _novel_category(self, source, pg, extend):
        result = {'list': [], 'page': 1, 'pagecount': 1, 'total': 0}
        try:
            params = {'page': pg}
            category = extend.get('category')
            if category:
                params['category'] = category
            
            data = self._api_request(f'/book/{source}/novels', params)
            if data and data.get('code') == 0:
                result['page'] = pg
                items = data.get('data', [])
                total_pages = data.get('total_pages', 0)
                if total_pages > 0:
                    result['pagecount'] = total_pages
                else:
                    total = data.get('total', len(items))
                    result['pagecount'] = max(1, (total + 19) // 20)
                result['total'] = data.get('total', len(items))
                
                for item in items:
                    result['list'].append({
                        'vod_id': f"novel_{source}_{item.get('novel_id')}",
                        'vod_name': item.get('title', ''),
                        'vod_pic': item.get('cover_url', ''),
                        'vod_remarks': f"{item.get('category', '')} · {item.get('total_chapters', 0)}章",
                        'vod_author': item.get('author', ''),
                    })
        except Exception as e:
            print(f"_novel_category error: {e}")
        return result
    
    def detailContent(self, ids, **kwargs):
        result = {'list': []}
        try:
            if isinstance(ids, str):
                ids = [ids]
            
            for vod_id in ids:
                vod_id = str(vod_id)
                
                if vod_id.startswith('novel_'):
                    return self._novel_detail(vod_id)
                
                if '@@' in vod_id:
                    dbname, real_vod_id = vod_id.split('@@', 1)
                else:
                    dbname = None
                    real_vod_id = vod_id
                
                if not dbname:
                    for cls in self.classes:
                        if not cls['type_id'].startswith('novel_'):
                            dbname = cls['type_id']
                            break
                
                if not dbname:
                    continue
                
                data = self._api_request(f'/maccms/json/{dbname}/', {'vod_id': real_vod_id})
                if data and data.get('code') == 1:
                    matched_item = None
                    for item in data.get('list', []):
                        if str(item.get('vod_id', '')) == str(real_vod_id):
                            matched_item = item
                            break
                    
                    if not matched_item:
                        matched_item = data.get('list', [{}])[0]
                    
                    vod_play_from = matched_item.get('vod_play_from', '')
                    vod_play_url = matched_item.get('vod_play_url', '')
                    
                    # 如果 vod_play_url 为空，从封面图中提取标识符构造播放地址
                    if not vod_play_url:
                        pic_url = matched_item.get('vod_pic', '')
                        if pic_url:
                            # 从封面图 URL 中提取标识符
                            # http://15260503.top/20260725/uZttvpFx/1.jpg
                            # 提取 uZttvpFx
                            match = re.search(r'/([a-zA-Z0-9]+)/\d+\.jpg$', pic_url)
                            if match:
                                video_key = match.group(1)
                                # 使用示例 URL 模板构造播放地址
                                db_info = self._get_db_info(dbname)
                                if db_info and db_info.get('sample_vod_play_urls'):
                                    samples = db_info['sample_vod_play_urls']
                                    if samples:
                                        sample = samples[0]
                                        if '$' in sample:
                                            sample = sample.split('$', 1)[1]
                                        # 替换示例中的标识符
                                        # https://2607.v155p.com/20260725/uZttvpFx/index.m3u8
                                        # 替换 uZttvpFx 为 video_key
                                        import re as regex
                                        base_url = regex.sub(r'/[a-zA-Z0-9]+/index\.m3u8$', f'/{video_key}/index.m3u8', sample)
                                        vod_play_url = base_url
                                        if not vod_play_from:
                                            vod_play_from = db_info.get('name', '默认线路')
                    
                    # 如果还是没有播放地址，使用示例地址（最终降级）
                    if not vod_play_url:
                        db_info = self._get_db_info(dbname)
                        if db_info and db_info.get('sample_vod_play_urls'):
                            samples = db_info['sample_vod_play_urls']
                            if samples:
                                sample = samples[0]
                                if '$' in sample:
                                    sample = sample.split('$', 1)[1]
                                vod_play_url = sample
                                if not vod_play_from:
                                    vod_play_from = db_info.get('name', '默认线路')
                    
                    detail = {
                        'vod_id': vod_id,
                        'vod_name': matched_item.get('vod_name', ''),
                        'vod_pic': matched_item.get('vod_pic', ''),
                        'vod_content': matched_item.get('vod_blurb', ''),
                        'vod_actor': matched_item.get('vod_actor', ''),
                        'vod_director': matched_item.get('vod_director', ''),
                        'vod_year': matched_item.get('vod_year', ''),
                        'vod_area': matched_item.get('vod_area', ''),
                        'vod_lang': matched_item.get('vod_lang', ''),
                        'vod_score': matched_item.get('vod_score', ''),
                        'vod_hits': matched_item.get('vod_hits', 0),
                        'vod_duration': self._duration(matched_item.get('vod_duration')),
                        'vod_play_from': vod_play_from,
                        'vod_play_url': f"第1集${vod_play_url}" if vod_play_url else '',
                        'type_name': matched_item.get('type_name', ''),
                    }
                    result['list'].append(detail)
        except Exception as e:
            print(f"detailContent error: {e}")
        return result
    
    def _novel_detail(self, vod_id):
        result = {'list': []}
        try:
            parts = vod_id.split('_')
            if len(parts) < 3:
                return result
            source = parts[1]
            novel_id = parts[2]
            
            data = self._api_request(f'/book/{source}/novels/{novel_id}')
            if data and data.get('code') == 0:
                item = data.get('data', {})
                
                chapters_data = self._api_request(f'/book/{source}/novels/{novel_id}/chapters')
                chapters = chapters_data.get('data', []) if chapters_data else []
                
                play_urls = []
                for ch in chapters:
                    ch_idx = ch.get('chapter_index', 0)
                    ch_title = ch.get('chapter_info') or ch.get('title', f'第{ch_idx+1}章')
                    safe_title = ch_title.replace('$', '＄')
                    play_urls.append(f"{safe_title}$novel://{source}/{novel_id}/{ch_idx}")
                
                detail = {
                    'vod_id': vod_id,
                    'vod_name': item.get('title', ''),
                    'vod_pic': item.get('cover_url', ''),
                    'vod_content': item.get('description', ''),
                    'vod_actor': item.get('author', ''),
                    'vod_play_from': source.upper(),
                    'vod_play_url': '#'.join(play_urls),
                    'type_name': '小说',
                }
                result['list'].append(detail)
        except Exception as e:
            print(f"_novel_detail error: {e}")
        return result
    
    def _get_dbname_by_vod_id(self, vod_id):
        for db in self._get_databases():
            dbname = db.get('dbname')
            if not dbname:
                continue
            data = self._api_request(f'/maccms/json/{dbname}/', {'vod_id': vod_id})
            if data and data.get('code') == 1 and data.get('list'):
                return dbname
        return None
    
    def _get_db_info(self, dbname):
        for db in self._get_databases():
            if db.get('dbname') == dbname:
                return db
        return None
    
    def searchContent(self, key, quick=False, pg='1'):
        result = {'list': []}
        try:
            key = str(key or '').strip()
            if not key:
                return result
            
            page = int(pg or 1)
            databases = self._get_databases()
            all_results = []
            
            def search_db(dbname):
                items = []
                try:
                    data = self._api_request(f'/maccms/meili/search/{dbname}/', {'wd': key, 'page': page})
                    if data and data.get('code') == 1:
                        for item in data.get('list', []):
                            items.append({
                                'vod_id': f"{dbname}@@{item.get('vod_id', '')}",
                                'vod_name': item.get('vod_name', ''),
                                'vod_pic': item.get('vod_pic', ''),
                                'vod_remarks': self._duration(item.get('vod_duration')),
                                'type_name': item.get('type_name', ''),
                            })
                        return items
                    
                    data = self._api_request(f'/maccms/json/{dbname}/', {'page': 1, 'limit': 50})
                    if data and data.get('code') == 1:
                        for item in data.get('list', []):
                            name = item.get('vod_name', '')
                            if key.lower() in name.lower():
                                items.append({
                                    'vod_id': f"{dbname}@@{item.get('vod_id', '')}",
                                    'vod_name': name,
                                    'vod_pic': item.get('vod_pic', ''),
                                    'vod_remarks': self._duration(item.get('vod_duration')),
                                    'type_name': item.get('type_name', ''),
                                })
                except Exception as e:
                    print(f"search_db error: {e}")
                return items
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {}
                for db in databases[:10]:
                    dbname = db.get('dbname')
                    if dbname:
                        future = executor.submit(search_db, dbname)
                        futures[future] = dbname
                
                for future in as_completed(futures):
                    try:
                        items = future.result(timeout=10)
                        if items:
                            all_results.extend(items)
                    except Exception as e:
                        print(f"search future error: {e}")
            
            seen = set()
            for item in all_results:
                vid = item.get('vod_id')
                if vid and vid not in seen:
                    seen.add(vid)
                    result['list'].append(item)
                    if len(result['list']) >= 50:
                        break
            
            if len(result['list']) < 5:
                novel_items = self._novel_search(key)
                result['list'].extend(novel_items)
                
        except Exception as e:
            print(f"searchContent error: {e}")
        return result
    
    def _novel_search(self, keyword):
        result = []
        try:
            for source in self.novel_sources:
                data = self._api_request(f'/book/{source}/novels/search', {'keyword': keyword})
                if data and data.get('code') == 0:
                    for item in data.get('data', []):
                        result.append({
                            'vod_id': f"novel_{source}_{item.get('novel_id')}",
                            'vod_name': item.get('title', ''),
                            'vod_pic': item.get('cover_url', ''),
                            'vod_remarks': f"{item.get('category', '')} · {item.get('total_chapters', 0)}章",
                            'type_name': '小说',
                        })
        except Exception as e:
            print(f"_novel_search error: {e}")
        return result
    
    def playerContent(self, flag, id, vipFlags=None):
        """播放接口"""
        # 小说阅读 - novel:// 协议
        if id and id.startswith('novel://'):
            try:
                parts = id.replace('novel://', '').split('/')
                if len(parts) >= 3:
                    source = parts[0]
                    novel_id = parts[1]
                    chapter_idx = parts[2]
                    
                    data = self._api_request(f'/book/{source}/novels/{novel_id}/chapters/{chapter_idx}')
                    if data and data.get('code') == 0:
                        content = data.get('data', {}).get('content', '')
                        encoded_content = json.dumps({
                            'title': f'第{int(chapter_idx)+1}章',
                            'content': content
                        }, ensure_ascii=False)
                        return {
                            'parse': 0,
                            'url': 'novel://' + encoded_content,
                            'header': {}
                        }
            except Exception as e:
                print(f"novel player error: {e}")
            return {'parse': 1, 'url': id, 'header': {}}
        
        # 直链播放
        if id and (id.startswith('http://') or id.startswith('https://')):
            if any(id.endswith(ext) for ext in ['.m3u8', '.mp4', '.flv', '.m3u']):
                return {
                    'parse': 0,
                    'url': id,
                    'header': {
                        'User-Agent': self.headers['User-Agent'],
                        'Referer': self.host,
                    }
                }
        
        # 尝试从播放页提取
        if id:
            try:
                play_url = self._fix_url(id)
                if play_url.startswith('http'):
                    resp = self.fetch(play_url, headers=self.headers)
                    if resp and hasattr(resp, 'text'):
                        html = resp.text
                        iframe = re.search(r'<iframe[^>]+src="([^"]+)"', html)
                        if iframe:
                            return self.playerContent(flag, iframe.group(1), vipFlags)
                        m3u8 = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html)
                        if m3u8:
                            return {
                                'parse': 0,
                                'url': m3u8.group(1),
                                'header': {
                                    'User-Agent': self.headers['User-Agent'],
                                    'Referer': play_url,
                                }
                            }
            except Exception as e:
                print(f"playerContent parse error: {e}")
        
        return {
            'parse': 1,
            'url': id or flag,
            'header': self.headers
        }
    
    def isVideoFormat(self, url):
        return True
    
    def manualVideoCheck(self):
        return None
    
    def action(self, action):
        return None
    
    def destroy(self):
        return None