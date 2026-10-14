# -*- coding: utf-8 -*-
import requests
import json

class Spider:
    def init(self, extend=""):
        self.host = "https://5721004.xyz"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': f"{self.host}/player/pandalive0418.html"
        }
        print("PandaLive 专业版 - 基于list.json接口")

    def getName(self):
        return "PandaLive"

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        return None

    def _fetch_json_data(self):
        """从list.json抓取主播数据"""
        try:
            url = f"{self.host}/player/list.json"
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                return []
            
            data = resp.json()
            raw_list = data.get('list', [])
            
            processed = []
            for item in raw_list:
                user_id = item.get('userId', '')
                if not user_id:
                    continue
                
                title = item.get('title', '无标题')
                nick = item.get('userNick', '未知主播')
                is_adult = item.get('isAdult', False)
                is_pw = item.get('isPw', False)
                v_type = item.get('type', '')
                live_type = item.get('liveType', 'live')
                viewer_count = item.get('user', 0)
                
                processed.append({
                    'vod_id': f"live_{user_id}",
                    'vod_name': title if title else nick,
                    'vod_pic': item.get('thumbUrl', 'https://tupian.li/images/2024/03/30/660769b1ba623.png'),
                    'vod_remarks': f"💋 {viewer_count} {'🔞' if is_adult else '全年龄'}",
                    'vod_content': title,
                    'vod_actor': user_id,
                    '_isAdult': is_adult,
                    '_isPw': is_pw,
                    '_type': v_type,
                    '_isFan': v_type == 'fan',
                    '_isRecord': live_type == 'rec',
                    '_user_count': viewer_count,
                    '_status': '录像' if live_type == 'rec' else '直播'
                })
            
            # 按观众数量降序排序，观众多的排最前
            processed.sort(key=lambda x: x.get('_user_count', 0), reverse=True)
            print(f"共抓取到 {len(processed)} 个主播")
            return processed
        except Exception as e:
            print(f"JSON抓取失败: {e}")
            return []

    def _get_demo_data(self):
        """默认演示数据"""
        return [
            {
                'vod_id': 'live_demo1',
                'vod_name': '演示直播间',
                'vod_pic': 'https://tupian.li/images/2024/03/30/660769b1ba623.png',
                'vod_remarks': '👤 1234',
                'vod_content': '演示直播内容',
                'vod_actor': 'demo1',
                '_isAdult': True,
                '_isPw': False,
                '_type': 'free',
                '_isFan': False,
                '_isRecord': False,
                '_user_count': 1234,
                '_status': '直播'
            }
        ]

    def homeContent(self, filter):
        """首页"""
        try:
            classes = [
                {'type_id': 'pandalive', 'type_name': '🐼 PandaTV'}
            ]
            
            filters = {
                "pandalive": [
                    {
                        "key": "type",
                        "name": "类型",
                        "value": [
                            {"n": "全部", "v": "all"},
                            {"n": "🔞 19+", "v": "adult"},
                            {"n": "🔐 密码房", "v": "pw"},
                            {"n": "💎 粉丝房", "v": "fan"},
                            {"n": "📼 录像", "v": "record"}
                        ]
                    },
                    {
                        "key": "sort",
                        "name": "排序",
                        "value": [
                            {"n": "观众量 ↓", "v": "user-desc"},
                            {"n": "默认", "v": "default"}
                        ]
                    }
                ]
            }
            
            items = self._fetch_json_data()
            if not items:
                items = self._get_demo_data()
            
            print(f"首页返回 {len(items[:30])} 个主播")
            return {
                'class': classes,
                'list': items[:30],
                'filters': filters
            }
        except Exception as e:
            print(f"homeContent错误: {e}")
            return {
                'class': [{'type_id': 'pandalive', 'type_name': '🐼 PandaTV'}],
                'list': self._get_demo_data(),
                'filters': {}
            }

    def homeVideoContent(self):
        """首页视频推荐"""
        try:
            items = self._fetch_json_data()
            if not items:
                items = self._get_demo_data()
            return {'list': items[:20]}
        except:
            return {'list': self._get_demo_data()[:20]}

    def categoryContent(self, tid, pg, filter, extend):
        """分类页 - 支持分页"""
        try:
            all_list = self._fetch_json_data()
            if not all_list:
                all_list = self._get_demo_data()
            
            filtered = all_list.copy()
            
            # 筛选
            if extend:
                f_type = extend.get('type', 'all')
                if f_type == 'adult':
                    filtered = [v for v in filtered if v.get('_isAdult')]
                elif f_type == 'pw':
                    filtered = [v for v in filtered if v.get('_isPw')]
                elif f_type == 'fan':
                    filtered = [v for v in filtered if v.get('_isFan')]
                elif f_type == 'record':
                    filtered = [v for v in filtered if v.get('_isRecord')]
                
                # 排序
                sort_type = extend.get('sort', 'user-desc')
                if sort_type == 'user-desc':
                    filtered.sort(key=lambda x: x.get('_user_count', 0), reverse=True)
            
            # 分页 - 每页30条
            pg = int(pg) if pg else 1
            limit = 30
            start = (pg - 1) * limit
            end = start + limit
            page_list = filtered[start:end] if start < len(filtered) else []
            
            total = len(filtered)
            pagecount = (total + limit - 1) // limit if total > 0 else 1
            
            print(f"分类页调试: tid={tid}, pg={pg}, total={total}, pagecount={pagecount}, 本页={len(page_list)}")
            
            return {
                'list': page_list,
                'page': pg,
                'pagecount': pagecount,
                'limit': limit,
                'total': total
            }
        except Exception as e:
            print(f"categoryContent错误: {e}")
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}

    def _get_stream_url(self, user_id):
        """通过api.php获取真实的流地址"""
        try:
            api_url = f"{self.host}/player/api.php?id={user_id}&t=20240701"
            resp = requests.get(api_url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == 200:
                    return data.get('url', '')
            return ''
        except Exception as e:
            print(f"获取流地址失败: {e}")
            return ''

    def detailContent(self, ids):
        """详情页 - 获取真实流地址"""
        try:
            first_id = ids[0] if isinstance(ids, list) else ids
            user_id = first_id.replace("live_", "")
            
            # 获取真实流地址
            stream_url = self._get_stream_url(user_id)
            
            if not stream_url:
                # 如果获取失败，使用播放页面作为fallback
                stream_url = f"{self.host}/player/pandalive.html?url={user_id}"
            
            proxies = [
                "https://f00.515355.xyz/proxy/",
                "https://uae2.515355.xyz/proxy/",
                "https://hubu.515355.xyz/proxy/?",
                "https://pol.515355.xyz/proxy/",
                "https://flank.515355.xyz/proxy/",
                "https://ce2.515355.xyz/proxy/?",
            ]
            
            # 生成带代理的播放链接
            play_links = []
            for i, p in enumerate(proxies, 1):
                play_links.append(f"代理{i}${p}{stream_url}")
            play_links.append(f"直连${stream_url}")
            
            vod = {
                'vod_id': first_id,
                'vod_name': f"PandaTV - {user_id}",
                'vod_pic': 'https://tupian.li/images/2024/03/30/660769b1ba623.png',
                'vod_content': f'主播: {user_id}',
                'vod_play_from': 'PandaLive',
                'vod_play_url': '#'.join(play_links)
            }
            return {'list': [vod]}
        except Exception as e:
            print(f"detailContent错误: {e}")
            return {'list': []}
    def searchContent(self, key, quick, pg="1"):
        """搜索主播"""
        try:
            all_v = self._fetch_json_data()
            if not all_v:
                all_v = self._get_demo_data()
            key_l = key.lower()
            res = [v for v in all_v if key_l in v['vod_name'].lower() or key_l in v.get('vod_actor', '').lower()]
            
            # 搜索结果也支持分页
            pg_int = int(pg) if pg else 1
            limit = 50
            start = (pg_int - 1) * limit
            page_list = res[start:start+limit] if start < len(res) else []
            pagecount = (len(res) + limit - 1) // limit if len(res) > 0 else 1
            
            return {'list': page_list, 'page': pg_int, 'pagecount': pagecount}
        except:
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}

    def playerContent(self, flag, id, vipFlags):
        return {
            'parse': 0,
            'url': id,
            'header': self.headers
        }