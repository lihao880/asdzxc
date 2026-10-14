import json
import sys
from requests import Session
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=""):
        self.api_url = "https://www.xxxfollow.com/api/v1"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.xxxfollow.com/',
            'Origin': 'https://www.xxxfollow.com'
        }
        self.session = Session()
        self.session.headers.update(self.headers)
    
    def getName(self):
        return "XXXFollow"
    
    def homeContent(self, filter):
        t_map = {"全部": "all", "女生": "f", "男生": "m", "情侣": "c"}
        cls = [{'type_name': k, 'type_id': v} for k, v in t_map.items()]
        flt = [{"key": "sort", "name": "排序", "value": [{"n": "最新", "v": "new"}, {"n": "最热", "v": "hot"}]}]
        return {'class': cls, 'filters': {v: flt for v in t_map.values()}}
    
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg)
        p = {"page": pg, "limit": 20}
        try:
            if tid.startswith('user:'):
                un = tid.split(':', 1)[1].strip()
                url = f"{self.api_url}/user/{un}/post/public"
                p["sort_by"] = "recent"
            else:
                url = f"{self.api_url}/user/public"
                p["genders"] = "cfm" if tid == "all" else tid
                if extend and extend.get("sort") == "hot":
                    p["force_variant"] = "out-best-full-trend-combined-max-new-sort-new-append"
            
            d = self.session.get(url, params=p, timeout=10).json()
            items = d if isinstance(d, list) else d.get('list', [])
            vl = []
            
            for i in items:
                pt = i.get('post', {})
                usr = pt.get('user', {})
                md = pt.get('media', [])
                if not md: continue
                
                fm = md[0]
                t = fm.get('type', 'video')
                pu = fm.get('fhd_url') or fm.get('url') or fm.get('sd_url') or "" if t == 'video' else fm.get('url') or fm.get('thumb_url') or ""
                un = usr.get('username', usr.get('display_name', ''))
                nm = pt.get('text', '').strip() or usr.get('display_name', 'No Title')
                pic = fm.get('start_url') or fm.get('thumb_url') if t == 'video' else fm.get('url') or fm.get('thumb_url')
                
                vl.append({
                    'vod_id': f"{pt.get('id', '')}|{fm.get('id', '')}|{t}|{pu}|{un}",
                    'vod_name': nm[:30] + '...' if len(nm) > 30 else nm,
                    'vod_pic': pic,
                    'vod_remarks': f"❤{i.get('like_count', 0)} 👀{i.get('view_count', 0)}",
                    'vod_actor': un
                })
                
            return {'list': vl, 'page': pg, 'pagecount': pg + 1 if vl else pg, 'total': 999999}
        except Exception:
            return {'list': [], 'page': pg, 'pagecount': pg, 'total': 999999}
    
    def _get_user_videos(self, username, max_videos=100):
        """获取指定用户的所有视频链接（最多 max_videos 个）"""
        videos = []
        page = 1
        limit = 20  # 每页帖子数
        
        while len(videos) < max_videos:
            try:
                url = f"{self.api_url}/user/{username}/post/public"
                params = {"page": page, "limit": limit, "sort_by": "recent"}
                resp = self.session.get(url, params=params, timeout=10)
                data = resp.json()
                items = data if isinstance(data, list) else data.get('list', [])
                if not items:
                    break
                
                for item in items:
                    if len(videos) >= max_videos:
                        break
                    pt = item.get('post', {})
                    media_list = pt.get('media', [])
                    for media in media_list:
                        if media.get('type') == 'video':
                            # 优先取 fhd_url，其次 url，最后 sd_url
                            video_url = media.get('fhd_url') or media.get('url') or media.get('sd_url')
                            if video_url and video_url not in videos:
                                videos.append(video_url)
                                if len(videos) >= max_videos:
                                    break
                # 检查是否还有下一页（如果返回的总数小于 limit 则没有下一页）
                if len(items) < limit:
                    break
                page += 1
            except Exception:
                break
        return videos
    
    def detailContent(self, ids):
        # 解析传入的 vod_id 格式：post_id|media_id|type|url|username
        parts = ids[0].split('|')
        username = parts[4] if len(parts) > 4 else ""
        
        if not username:
            return {'list': [{'vod_id': ids[0], 'vod_play_from': 'XXXFollow', 'vod_play_url': '无有效用户$', 'vod_actor': ''}]}
        
        # 获取该用户的所有视频（最多100个）
        video_urls = self._get_user_videos(username, max_videos=100)
        
        if not video_urls:
            play_url = "暂无视频$http://0.0.0.0/off.mp4"
        else:
            # 构建播放列表：第1集$url1#第2集$url2...
            segments = []
            for idx, url in enumerate(video_urls, start=1):
                segments.append(f"第{idx}集${url}")
            play_url = "#".join(segments)
        
        # 用户链接（可点击跳转用户合集）
        user_link = f"[a=cr:{json.dumps({'id': f'user:{username}', 'name': username}, ensure_ascii=False)}/]{username}[/a]"
        
        return {
            'list': [{
                'vod_id': ids[0],
                'vod_name': f"{username} 的合集（共{len(video_urls)}视频）",
                'vod_play_from': 'XXXFollow',
                'vod_play_url': play_url,
                'vod_actor': user_link,
                'vod_remarks': f"共{len(video_urls)}个视频"
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        return self.categoryContent(f"user:{key}", pg, filter=False, extend={})

    def playerContent(self, flag, id, vipFlags):
        return {'parse': 0, 'url': id, 'header': self.headers}