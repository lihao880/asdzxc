# coding=utf-8
import base64
import hashlib
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, unquote

import urllib3

AES = None
pad = None
unpad = None
Session = None
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append('..')
from base.spider import Spider as BaseSpider



BUILTIN_CLASSES = [{'type_name': '视频', 'type_id': 'video_all'}, {'type_name': '动漫', 'type_id': 'anime_all'}, {'type_name': '漫画', 'type_id': 'comic_all'}, {'type_name': '社区', 'type_id': 'community_all'}, {'type_name': '暗网', 'type_id': 'deep_all'}, {'type_name': '小说', 'type_id': 'novel_all'}, {'type_name': '图片', 'type_id': 'pic_all'}]
BUILTIN_FILTERS = {'video_all': [{'key': 'cate_id', 'name': '热门', 'value': [{'n': '全部', 'v': 'mod:650c14aac8adc51465ea1b26'}, {'n': '极品学妹', 'v': 'msec:681c390b05828daa49ed5453'}, {'n': '最新推荐', 'v': 'msec:686bd6fabd54de359f64933b'}, {'n': '白虎嫩穴', 'v': 'msec:686bd797bd54de359f649344'}, {'n': '童颜巨乳', 'v': 'msec:686bd7a2bd54de359f649347'}, {'n': '探花精选', 'v': 'msec:686bd7acbd54de359f64934a'}, {'n': '制服诱惑', 'v': 'msec:686bd7b5bd54de359f64934d'}, {'n': '反差母狗', 'v': 'msec:686bd7bdbd54de359f649350'}, {'n': '猎奇百科', 'v': 'msec:6882fdad2c06c8077aabb599'}, {'n': '精选乱伦', 'v': 'msec:666185ba27e094952c941d10'}, {'n': '韩国视频', 'v': 'msec:681c609605828daa49ed5dce'}, {'n': '绿帽淫妻', 'v': 'msec:650c5ce4171265a04a67835a'}, {'n': '良家少妇', 'v': 'msec:650c6571171265a04a6783ae'}, {'n': '美腿丝足', 'v': 'msec:650c681a171265a04a67840d'}, {'n': '高颜值女神', 'v': 'msec:688339d952403fa2f64fb03c'}, {'n': '孕妇偷情', 'v': 'msec:66d0650d2a51a6d65b56c005'}, {'n': '强奸迷奸', 'v': 'msec:6883454852403fa2f64fb0f1'}]}, {'key': 'cate_id', 'name': '国产', 'value': [{'n': '全部', 'v': 'mod:650c1527c8adc51465ea1b45'}, {'n': '国产自拍', 'v': 'msec:650c64fb171265a04a678393'}, {'n': '勾引搭讪', 'v': 'msec:650c6557171265a04a6783a8'}, {'n': '黑料曝光', 'v': 'msec:6805fcb88a392e22f5e17c31'}, {'n': '户外露出', 'v': 'msec:650c6589171265a04a6783b4'}, {'n': '嫖娼约炮', 'v': 'msec:6805f8868a392e22f5e17bf9'}, {'n': '网红主播', 'v': 'msec:650c64d7171265a04a67838a'}, {'n': '监控偷拍', 'v': 'msec:650c5c21171265a04a67833c'}, {'n': '轻口调教', 'v': 'msec:668d3fdcc04ac15dc6c9a71b'}, {'n': '自慰喷水', 'v': 'msec:6887455952403fa2f64fc0aa'}, {'n': '网曝泄密', 'v': 'msec:6805fcdf8a392e22f5e17c3a'}, {'n': '大屌萌妹', 'v': 'msec:6964c3052e56c127454f2083'}, {'n': '明星换脸', 'v': 'msec:650c5c81171265a04a67834e'}, {'n': '野战车震', 'v': 'msec:650c5c74171265a04a67834b'}, {'n': '百合女同', 'v': 'msec:650c6513171265a04a678399'}, {'n': '会所按摩', 'v': 'msec:6a2f749e98474b862667b907'}, {'n': '多人群p', 'v': 'msec:6a2f74ba98474b862667b90a'}]}, {'key': 'cate_id', 'name': '精选', 'value': [{'n': '全部', 'v': 'mod:6a2bc4c6368c661198085922'}, {'n': '热播', 'v': 'msec:6a39fba237d2f2cb678b9c12'}, {'n': '原创', 'v': 'msec:6a2bc51c368c66119808592d'}, {'n': '18岁', 'v': 'msec:6a2bc550368c661198085930'}, {'n': '乱伦', 'v': 'msec:6a2bc55e368c661198085933'}, {'n': '传媒', 'v': 'msec:6a2bc59f368c661198085936'}]}, {'key': 'cate_id', 'name': '乱伦', 'value': [{'n': '全部', 'v': 'mod:650c14bfc8adc51465ea1b2c'}, {'n': '母子乱伦', 'v': 'msec:650c641c171265a04a678365'}, {'n': '父女乱伦', 'v': 'msec:650c642d171265a04a678368'}, {'n': '家庭乱伦', 'v': 'msec:66d04f712a51a6d65b56bae6'}, {'n': '兄妹姐妹', 'v': 'msec:650c6438171265a04a67836b'}]}, {'key': 'cate_id', 'name': '国产AV', 'value': [{'n': '全部', 'v': 'mod:650c14d2c8adc51465ea1b31'}, {'n': '麻豆传媒', 'v': 'msec:650c65cf171265a04a6783bb'}, {'n': '糖心Vlog', 'v': 'msec:650c66a2171265a04a6783e5'}, {'n': '星空无限', 'v': 'msec:650c6692171265a04a6783e2'}, {'n': '91制片厂', 'v': 'msec:650c65dc171265a04a6783be'}, {'n': '蜜桃传媒', 'v': 'msec:650c6615171265a04a6783ca'}, {'n': '天美传媒', 'v': 'msec:650c660a171265a04a6783c7'}, {'n': '精东影业', 'v': 'msec:650c65fc171265a04a6783c4'}, {'n': '性世界', 'v': 'msec:650c6686171265a04a6783df'}, {'n': '兔子先生', 'v': 'msec:650c6663171265a04a6783d9'}, {'n': '扣扣传媒', 'v': 'msec:650c66af171265a04a6783e8'}, {'n': '果冻传媒', 'v': 'msec:650c65e8171265a04a6783c1'}, {'n': '台湾JVID', 'v': 'msec:650c663f171265a04a6783d3'}, {'n': 'SA国际传媒', 'v': 'msec:650c6674171265a04a6783dc'}, {'n': 'SWAG', 'v': 'msec:650c6651171265a04a6783d6'}, {'n': '皇家华人', 'v': 'msec:650c6620171265a04a6783cd'}, {'n': '大象传媒', 'v': 'msec:6657fa0027e094952c93ab8e'}]}, {'key': 'cate_id', 'name': 'AV', 'value': [{'n': '全部', 'v': 'mod:6805b98b8a392e22f5e17b7d'}, {'n': '中文字幕', 'v': 'msec:650c67c5171265a04a6783fb'}, {'n': '精选无码', 'v': 'msec:650c675d171265a04a6783f1'}, {'n': '家庭乱伦', 'v': 'msec:650c6807171265a04a67840a'}, {'n': '无码FC2', 'v': 'msec:650c674f171265a04a6783ee'}, {'n': '巨根黑人', 'v': 'msec:650c6859171265a04a678419'}, {'n': '多P群交', 'v': 'msec:650c67d2171265a04a6783fe'}, {'n': '时间静止', 'v': 'msec:650c6827171265a04a678410'}, {'n': '人妻NTR', 'v': 'msec:6805bae78a392e22f5e17b98'}, {'n': '强奸系列', 'v': 'msec:6805baf88a392e22f5e17b9b'}, {'n': '人间胸器', 'v': 'msec:6805bb098a392e22f5e17b9e'}, {'n': 'AV解说', 'v': 'msec:6805bb1a8a392e22f5e17ba1'}, {'n': '奇葩AV', 'v': 'msec:6805bb328a392e22f5e17ba4'}]}, {'key': 'cate_id', 'name': '主播', 'value': [{'n': '全部', 'v': 'mod:6805fcfa8a392e22f5e17c3d'}, {'n': '户外直播', 'v': 'msec:6805fd398a392e22f5e17c42'}, {'n': '韩国主播', 'v': 'msec:681c60a305828daa49ed5dd3'}, {'n': '网红直播', 'v': 'msec:6805fd4b8a392e22f5e17c48'}, {'n': '啪啪直播', 'v': 'msec:6805fd558a392e22f5e17c4b'}]}, {'key': 'cate_id', 'name': 'Only Fans', 'value': [{'n': '全部', 'v': 'mod:6870951ffa78013f4a8bb250'}, {'n': '唐伯虎', 'v': 'msec:688492f952403fa2f64fba84'}, {'n': '桥本香菜', 'v': 'msec:68ac361fbf30a31ee7a2c435'}, {'n': '许木学长', 'v': 'msec:68c0315a171ba5db9f2b3488'}, {'n': '斯文禽兽', 'v': 'msec:68c2c787171ba5db9f2b3e08'}, {'n': '娜娜', 'v': 'msec:68c2c7ba171ba5db9f2b3e0e'}, {'n': '冉冉学姐', 'v': 'msec:68c2c7cb171ba5db9f2b3e11'}, {'n': '唐可可', 'v': 'msec:68c2c7f9171ba5db9f2b3e14'}, {'n': '锅锅酱', 'v': 'msec:68c95437a1b136fc271373b9'}, {'n': '鸡教练', 'v': 'msec:68c9567ca1b136fc2713742c'}, {'n': 'D先生', 'v': 'msec:68ee4a7601d81bdf516a9da3'}, {'n': '91xx君', 'v': 'msec:68ee4cd501d81bdf516a9de2'}, {'n': '91原创-老虎菜', 'v': 'msec:695d0a522e56c127454eff6a'}, {'n': '日本极品情侣博主 emma_and_ken', 'v': 'msec:69a82ae6058db0645b200dc0'}, {'n': '性感小野猫', 'v': 'msec:69bbf1811c94a51e6af14165'}, {'n': '91原创', 'v': 'msec:68f6360f6479be6e1a753703'}, {'n': '台北娜娜', 'v': 'msec:6884947e52403fa2f64fba90'}, {'n': '小桃酱', 'v': 'msec:68c2c7ac171ba5db9f2b3e0b'}, {'n': '甜心宝贝', 'v': 'msec:68c2c83f171ba5db9f2b3e17'}, {'n': '酥酥', 'v': 'msec:68b161c8171ba5db9f2b1e3b'}, {'n': '辛尤里', 'v': 'msec:6884953752403fa2f64fbaa5'}, {'n': '白桃少女', 'v': 'msec:6884951d52403fa2f64fbaa2'}, {'n': '柚子猫', 'v': 'msec:6884950752403fa2f64fba9f'}, {'n': '下面有根棒棒糖', 'v': 'msec:688494ce52403fa2f64fba99'}, {'n': '粉色情人', 'v': 'msec:6884935a52403fa2f64fba8d'}, {'n': '饼干姐姐', 'v': 'msec:68c02fc9171ba5db9f2b3441'}, {'n': 'Cola酱', 'v': 'msec:6884956852403fa2f64fbaab'}, {'n': '仙仙桃', 'v': 'msec:6884958052403fa2f64fbaae'}, {'n': '奶咪', 'v': 'msec:688494af52403fa2f64fba96'}, {'n': '粉红兔', 'v': 'msec:6884949852403fa2f64fba93'}, {'n': '米娜学姐', 'v': 'msec:6895c7ab0c199c26edc44a9b'}, {'n': '阿朱', 'v': 'msec:6884934a52403fa2f64fba8a'}, {'n': '玩偶姐姐', 'v': 'msec:687095d8fa78013f4a8bb25b'}, {'n': '樱花小猫', 'v': 'msec:688494e952403fa2f64fba9c'}, {'n': '地雷系', 'v': 'msec:650e92facf6cf7ee4838a212'}]}, {'key': 'cate_id', 'name': '欧美', 'value': [{'n': '全部', 'v': 'mod:6805bbed8a392e22f5e17bb1'}, {'n': '欧美中字', 'v': 'msec:681c3a2a05828daa49ed548f'}, {'n': '欧美剧情', 'v': 'msec:650c689b171265a04a678425'}, {'n': '欧美乱伦', 'v': 'msec:6805fb9c8a392e22f5e17c18'}, {'n': '东欧极品', 'v': 'msec:6805fbb68a392e22f5e17c1b'}, {'n': '黑白配', 'v': 'msec:681c3a4105828daa49ed5496'}, {'n': '群P大战', 'v': 'msec:681c3f1505828daa49ed5499'}, {'n': '欧美重口', 'v': 'msec:6539d176ec571cc72bdc0ab3'}, {'n': '街头搭讪', 'v': 'msec:6a2fbb8b98474b862667c0c4'}]}, {'key': 'cate_id', 'name': '综艺', 'value': [{'n': '全部', 'v': 'mod:6806004a8a392e22f5e17c7b'}, {'n': '日本整人综艺', 'v': 'msec:68d267ac095fdbb5063fe2a5'}, {'n': '酷炫老師', 'v': 'msec:68cd60517b6e9d0bfc8a985d'}, {'n': '薇傲性事', 'v': 'msec:69b9527b950b127f4e297519'}, {'n': '童酸酸讓你酸', 'v': 'msec:68ce6c3a7b6e9d0bfc8a9b0a'}, {'n': '小哥哥艾理', 'v': 'msec:68ce6c197b6e9d0bfc8a9b07'}, {'n': '抖阴学院', 'v': 'msec:6806006b8a392e22f5e17c81'}, {'n': '台湾综艺', 'v': 'msec:680600768a392e22f5e17c84'}, {'n': '鲍鱼游戏', 'v': 'msec:6806008b8a392e22f5e17c87'}, {'n': '突袭女优', 'v': 'msec:680600998a392e22f5e17c8a'}]}, {'key': 'cate_id', 'name': '三级片', 'value': [{'n': '全部', 'v': 'mod:6882311d2c06c8077aabb56f'}, {'n': '韩国三级片', 'v': 'msec:681c608a05828daa49ed5dbf'}, {'n': '国产三级', 'v': 'msec:650c5c8f171265a04a678351'}, {'n': '欧美三级', 'v': 'msec:6805fbe98a392e22f5e17c24'}]}, {'key': 'sort', 'name': '排序', 'value': [{'n': '综合', 'v': '1'}, {'n': '最新', 'v': '2'}, {'n': '最热', 'v': '3'}, {'n': '播放', 'v': '4'}, {'n': '收藏', 'v': '5'}, {'n': '点赞', 'v': '6'}, {'n': '评论', 'v': '7'}]}], 'anime_all': [{'key': 'cate_id', 'name': '动漫', 'value': [{'n': '全部', 'v': 'mod:67b82a0b7cc676ac32d998e3'}, {'n': '官方推荐', 'v': 'msec:6808f2c932f78b2ce0ade3a3'}, {'n': '精选里番', 'v': 'msec:67b82a3c7cc676ac32d99912'}, {'n': '原神剧场', 'v': 'msec:67b82a457cc676ac32d99920'}, {'n': '精选同人', 'v': 'msec:67b82a4e7cc676ac32d99924'}, {'n': '3D动漫', 'v': 'msec:67b82a2d7cc676ac32d99902'}, {'n': '王者荣耀', 'v': 'msec:67b82a817cc676ac32d99948'}, {'n': 'MMD', 'v': 'msec:67b82a947cc676ac32d99954'}, {'n': 'AI生成', 'v': 'msec:67b82eed7cc676ac32d99aa1'}, {'n': '幼齿小萝莉', 'v': 'msec:6808f2d632f78b2ce0ade3a6'}, {'n': '斗罗大陆', 'v': 'msec:6808f2ef32f78b2ce0ade3a9'}, {'n': '斗破苍穹', 'v': 'msec:6808f93732f78b2ce0ade3d3'}, {'n': 'VAM', 'v': 'msec:6808f9c332f78b2ce0ade3de'}]}, {'key': 'sort', 'name': '排序', 'value': [{'n': '综合', 'v': '1'}, {'n': '最新', 'v': '2'}, {'n': '最热', 'v': '3'}, {'n': '播放', 'v': '4'}, {'n': '收藏', 'v': '5'}, {'n': '点赞', 'v': '6'}, {'n': '评论', 'v': '7'}]}], 'comic_all': [{'key': 'cate_id', 'name': '漫画', 'value': [{'n': '全部', 'v': 'mod:67b7f7e5ac310312c98dc12a'}, {'n': '官方推荐', 'v': 'msec:67b7ff30ac310312c98dc31b'}, {'n': '全彩涩漫', 'v': 'msec:67b7f890ac310312c98dc153'}, {'n': '精选同人', 'v': 'msec:67b7ff24ac310312c98dc318'}, {'n': '吸晴韩漫', 'v': 'msec:67b7ff43ac310312c98dc31e'}, {'n': '毁童年系列', 'v': 'msec:67b7ff53ac310312c98dc321'}, {'n': '萝莉控', 'v': 'msec:67b7ff5eac310312c98dc324'}, {'n': 'NTR牛头人', 'v': 'msec:67b7ff6aac310312c98dc327'}, {'n': '背德禁忌', 'v': 'msec:67b7ff76ac310312c98dc32a'}]}, {'key': 'sort', 'name': '排序', 'value': [{'n': '综合', 'v': '1'}, {'n': '最新', 'v': '2'}, {'n': '最热', 'v': '3'}, {'n': '播放', 'v': '4'}, {'n': '收藏', 'v': '5'}, {'n': '点赞', 'v': '6'}, {'n': '评论', 'v': '7'}]}], 'community_all': [{'key': 'cate_id', 'name': '热门推荐', 'value': [{'n': '全部', 'v': 'mod:650c153ec8adc51465ea1b4a'}, {'n': '热门推荐', 'v': 'msec:650eadf9504f2005d3ab0d82'}, {'n': '自拍分享', 'v': 'mtag:650c153ec8adc51465ea1b4a:5dbeb22fe76468ea20625ec0'}, {'n': '反差骚货', 'v': 'mtag:650c153ec8adc51465ea1b4a:65142906b27d2b6b52999db3'}, {'n': '伦理之爱', 'v': 'mtag:650c153ec8adc51465ea1b4a:5dbeb23fe76468ea20625edc'}, {'n': '我爱我妻', 'v': 'mtag:650c153ec8adc51465ea1b4a:5e0606fbcf4864a3bdd3b87d'}, {'n': '黑料吃瓜', 'v': 'mtag:650c153ec8adc51465ea1b4a:635e9b36d4dd9c00f6040043'}, {'n': '兴趣杂谈', 'v': 'mtag:650c153ec8adc51465ea1b4a:5dbeb2c8e76468ea20625f23'}]}, {'key': 'cate_id', 'name': '社区交友', 'value': [{'n': '全部', 'v': 'mod:650c1555c8adc51465ea1b50'}, {'n': '分享交友', 'v': 'msec:650eb06e504f2005d3ab0fa9'}, {'n': '91原创', 'v': 'mtag:650c1555c8adc51465ea1b50:69a59efc058db0645b1ff0b6'}, {'n': '换妻交友', 'v': 'mtag:650c1555c8adc51465ea1b50:5dbec68964447bd682552fed'}, {'n': '同城交友', 'v': 'mtag:650c1555c8adc51465ea1b50:653cd79255e6c8ab96b6a8ee'}]}, {'key': 'sort', 'name': '排序', 'value': [{'n': '综合', 'v': '1'}, {'n': '最新', 'v': '2'}, {'n': '最热', 'v': '3'}, {'n': '播放', 'v': '4'}, {'n': '收藏', 'v': '5'}, {'n': '点赞', 'v': '6'}, {'n': '评论', 'v': '7'}]}], 'deep_all': [{'key': 'cate_id', 'name': '暗网', 'value': [{'n': '全部', 'v': 'mod:652e566529a3f62c782d2edc'}, {'n': '圣水滋养', 'v': 'msec:6539d116ec571cc72bdc0aa5'}, {'n': '恐怖电影院', 'v': 'msec:691fcb816479be6e1a760886'}, {'n': '黄金盛筵', 'v': 'msec:6539d0d2ec571cc72bdc0a9f'}, {'n': '全球禁片', 'v': 'msec:65549cc369a93440ed26ce54'}, {'n': '重口调教', 'v': 'msec:6539d0fcec571cc72bdc0aa2'}]}, {'key': 'sort', 'name': '排序', 'value': [{'n': '综合', 'v': '1'}, {'n': '最新', 'v': '2'}, {'n': '最热', 'v': '3'}, {'n': '播放', 'v': '4'}, {'n': '收藏', 'v': '5'}, {'n': '点赞', 'v': '6'}, {'n': '评论', 'v': '7'}]}], 'novel_all': [{'key': 'cate_id', 'name': '有声小说', 'value': [{'n': '全部', 'v': 'mod:680b7e3361ffc2e4224f7b7c'}]}, {'key': 'cate_id', 'name': '剧情演绎', 'value': [{'n': '全部', 'v': 'mod:6818bac609f06f3a9282637f'}]}, {'key': 'cate_id', 'name': '家庭乱伦', 'value': [{'n': '全部', 'v': 'mod:6818ba8e09f06f3a9282636f'}]}, {'key': 'cate_id', 'name': '都市激情', 'value': [{'n': '全部', 'v': 'mod:6818baa509f06f3a92826374'}]}, {'key': 'cate_id', 'name': '淫妻少妇', 'value': [{'n': '全部', 'v': 'mod:6818bb4c09f06f3a92826386'}]}, {'key': 'cate_id', 'name': '校园春色', 'value': [{'n': '全部', 'v': 'mod:6818bbdc09f06f3a92826391'}]}, {'key': 'sort', 'name': '排序', 'value': [{'n': '综合', 'v': '1'}, {'n': '最新', 'v': '2'}, {'n': '最热', 'v': '3'}, {'n': '播放', 'v': '4'}, {'n': '收藏', 'v': '5'}, {'n': '点赞', 'v': '6'}, {'n': '评论', 'v': '7'}]}], 'pic_all': [{'key': 'cate_id', 'name': '国产精选', 'value': [{'n': '全部', 'v': 'mod:65c2e9aa3499fc57e0f1dafd'}]}, {'key': 'cate_id', 'name': '魅妍社', 'value': [{'n': '全部', 'v': 'mod:66a07fa94d9cb2dcdfda8d39'}]}, {'key': 'cate_id', 'name': '秀人网', 'value': [{'n': '全部', 'v': 'mod:6694ab9ac4f9a85dfc7aadca'}]}, {'key': 'cate_id', 'name': '尤蜜荟', 'value': [{'n': '全部', 'v': 'mod:66950059c4f9a85dfc7ab8d0'}]}, {'key': 'cate_id', 'name': '花漾', 'value': [{'n': '全部', 'v': 'mod:66950f2ac4f9a85dfc7ab920'}]}, {'key': 'cate_id', 'name': '美媛馆', 'value': [{'n': '全部', 'v': 'mod:669511b2c4f9a85dfc7ab978'}]}, {'key': 'cate_id', 'name': '模范学院', 'value': [{'n': '全部', 'v': 'mod:669513aac4f9a85dfc7ab9e6'}]}, {'key': 'cate_id', 'name': '爱蜜社', 'value': [{'n': '全部', 'v': 'mod:66a0c01b4d9cb2dcdfda8f4b'}]}, {'key': 'cate_id', 'name': '语画界', 'value': [{'n': '全部', 'v': 'mod:66a247be4d9cb2dcdfda9d95'}]}, {'key': 'cate_id', 'name': '嗲囡囡', 'value': [{'n': '全部', 'v': 'mod:66a248254d9cb2dcdfda9d9e'}]}, {'key': 'cate_id', 'name': '喵糖映画', 'value': [{'n': '全部', 'v': 'mod:6694d1eec4f9a85dfc7aafeb'}]}, {'key': 'sort', 'name': '排序', 'value': [{'n': '综合', 'v': '1'}, {'n': '最新', 'v': '2'}, {'n': '最热', 'v': '3'}, {'n': '播放', 'v': '4'}, {'n': '收藏', 'v': '5'}, {'n': '点赞', 'v': '6'}, {'n': '评论', 'v': '7'}]}]}

class Spider(BaseSpider):
    api_hosts = [
        'https://dxulz50c2x0pp.cloudfront.net',
        'https://d2tw9uw5rogvdw.cloudfront.net',
    ]
    interface_key = '65dc07d1b7915c6b2937432b091837a7'
    live_interface_key = '0a958fb9ac062420af6ba5f4caad779f'
    param_key = b'BxJand%xf5h3sycH'
    param_iv = b'BxJand%xf5h3sycH'
    xor_key = b'2019ysapp7527'
    img_host = 'https://zzzznnn.lkkwip.cn'
    vid_host = 'https://zhsnust.lkkwip.cn'
    audio_host = 'https://mp4.pjrwfe.cn'
    site_referer = 'https://91porn01.cc/'
    device_file = '/storage/emulated/0/tvbox/sites-py/.91PORN_device.json'

    SORT_MAP = [
        {'n': '综合', 'v': '1'},
        {'n': '最新', 'v': '2'},
        {'n': '最热', 'v': '3'},
        {'n': '播放', 'v': '4'},
        {'n': '收藏', 'v': '5'},
        {'n': '点赞', 'v': '6'},
        {'n': '评论', 'v': '7'},
    ]

    COMMUNITY_SORT_MAP = [
        {'n': '推荐', 'v': '3'},
        {'n': '最新', 'v': '1'},
        {'n': '最热', 'v': '2'},
        {'n': '精华', 'v': '5'},
        {'n': '视频', 'v': '6'},
    ]

    def __init__(self):
        self.ext = ''
        self.host = self.api_hosts[0]
        self.session = None
        self.token = ''
        self.uid = self._load_or_create_uid()
        self.ready = False
        self.module_map = {}
        self.tag_map = {}
        self.community_tag_parent = {}
        self.route_parent = {}
        self.classes = json.loads(json.dumps(BUILTIN_CLASSES, ensure_ascii=False))
        self.filters = json.loads(json.dumps(BUILTIN_FILTERS, ensure_ascii=False))
        self._apply_ui_config()
        self._hydrate_builtin_maps()
        self._normalize_cate_filters()

    def _apply_ui_config(self):
        """补齐短视频/直播大区，并合并只有单入口的碎片筛选行。"""
        class_ids = {str(x.get('type_id') or '') for x in self.classes}
        if 'tik_all' not in class_ids:
            self.classes.append({'type_name': '抖音', 'type_id': 'tik_all'})
        if 'live_all' not in class_ids:
            self.classes.append({'type_name': '直播', 'type_id': 'live_all'})

        tik_values = [{'n': '推荐', 'v': 'tik:SHORT'}]
        self.filters['tik_all'] = [{'key': 'cate_id', 'name': '分类', 'value': tik_values}]
        self.filters['live_all'] = [{'key': 'cate_id', 'name': '地区', 'value': [
            {'n': '推荐', 'v': 'live:tj'},
            {'n': '中国', 'v': 'live:6763e704daf2ddeb39b0ec83'},
            {'n': '日韩', 'v': 'live:6763e717daf2ddeb39b0ec84'},
            {'n': '越南', 'v': 'live:6763e750daf2ddeb39b0ec87'},
            {'n': '乌克兰', 'v': 'live:6763e72bdaf2ddeb39b0ec85'},
            {'n': '俄罗斯', 'v': 'live:6763e73bdaf2ddeb39b0ec86'},
            {'n': '欧美', 'v': 'live:6763e768daf2ddeb39b0ec88'},
            {'n': '男主播', 'v': 'live:6763e7b6daf2ddeb39b0ec8a'},
        ]}]

        for zid in ('novel_all', 'pic_all'):
            rows = self.filters.get(zid) or []
            merged, keep = [], []
            for row in rows:
                values = row.get('value') or []
                if str(row.get('key') or '') != 'sort' and len(values) == 1 and values[0].get('v'):
                    merged.append({'n': str(row.get('name') or values[0].get('n') or '分类'),
                                   'v': str(values[0].get('v'))})
                else:
                    keep.append(row)
            if merged:
                self.filters[zid] = [{'key': 'cate_id', 'name': '分类', 'value': merged}] + keep

    def _hydrate_builtin_maps(self):
        """从内置 filters 重建模块/标签映射，保证无动态分类请求也能正常取数。"""
        zones = {
            'video_all': 'video', 'pic_all': 'pic', 'comic_all': 'comic',
            'novel_all': 'novel', 'tik_all': 'tik', 'live_all': 'live',
            'community_all': 'community', 'deep_all': 'deep', 'hot_all': 'video',
        }
        for zid, rows in (self.filters or {}).items():
            zone = zones.get(zid, 'video')
            for row in rows or []:
                key = str(row.get('key') or '')
                values = row.get('value') or []
                parent_mid = key[len('cate_mod_'):] if key.startswith('cate_mod_') else ''
                if not parent_mid:
                    for item in values:
                        value = str(item.get('v') or '')
                        if value.startswith('mod:'):
                            parent_mid = value[4:]
                            break
                if parent_mid:
                    self.module_map[parent_mid] = {
                        'zone': zone, 'name': str(row.get('name') or parent_mid), 'type': None
                    }
                for item in values:
                    value = str(item.get('v') or '')
                    name = str(item.get('n') or '')
                    if value.startswith('mod:'):
                        mid = value[4:]
                        if mid:
                            self.module_map[mid] = {'zone': zone, 'name': name or mid, 'type': None}
                    elif value.startswith('tag:'):
                        tag = value[4:]
                        if tag:
                            self.tag_map[tag] = name or tag
                            if zone == 'community' and parent_mid:
                                self.community_tag_parent[tag] = parent_mid

    def getName(self):
        return '91PORN App'

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        self.ext = extend or ''
        return None

    def homeLayout(self):
        return 0

    def init(self, extend=''):
        if extend not in (None, ''):
            self.setExtendInfo(extend)
        value = getattr(self, 'ext', '') or ''
        try:
            if isinstance(value, str) and value.strip().startswith('http'):
                e = value.strip().rstrip('/')
                self.api_hosts = [e] + [h for h in self.api_hosts if h != e]
                self.host = self.api_hosts[0]
        except Exception:
            pass
        self._hydrate_builtin_maps()
        return None

    def _runtime(self):
        global AES, pad, unpad, Session
        if AES is None or pad is None or unpad is None:
            from Crypto.Cipher import AES as _AES
            from Crypto.Util.Padding import pad as _pad, unpad as _unpad
            AES, pad, unpad = _AES, _pad, _unpad
        if Session is None:
            from requests import Session as _Session
            Session = _Session
        if self.session is None:
            self.session = Session()
        return True

    def _hex_bytes(self, arr):
        out = []
        for v in arr:
            e = format((int(v) + 256) % 256, 'x')
            if len(e) == 1:
                e = '0' + e
            out.append(e)
        return ''.join(out)

    def _sha_bytes(self, arr):
        return hashlib.sha256(bytes.fromhex(self._hex_bytes(arr))).digest()

    def _enc_param(self, obj):
        self._runtime()
        raw = json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        cipher = AES.new(self.param_key, AES.MODE_CBC, self.param_iv)
        return base64.b64encode(cipher.encrypt(pad(raw, 16))).decode('utf-8')

    def _dec_data(self, enc, interface_key=None):
        self._runtime()
        if not enc:
            return {}
        try:
            I = base64.b64decode(str(enc).replace('\n', '').replace('\r', ''))
            key_text = str(interface_key or self.interface_key)
            e = list(key_text.encode('utf-8')) + list(I[:12])
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
        except Exception:
            return {}

    def _gen_uid(self):
        chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        return ''.join(random.SystemRandom().choice(chars) for _ in range(16)) + str(int(time.time() * 1000))

    def _valid_uid(self, value):
        return bool(re.fullmatch(r'[0-9A-Za-z]{16}\d{13}', str(value or '')))

    def _load_or_create_uid(self):
        """首次随机、后续稳定；写入失败时本进程内仍保持同一 ID。"""
        try:
            with open(self.device_file, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            uid = saved.get('device_id') if isinstance(saved, dict) else ''
            if self._valid_uid(uid):
                return str(uid)
        except Exception:
            pass
        uid = self._gen_uid()
        try:
            parent = os.path.dirname(self.device_file)
            if parent:
                os.makedirs(parent, exist_ok=True)
            tmp = self.device_file + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump({'device_id': uid}, f, ensure_ascii=False, separators=(',', ':'))
            os.replace(tmp, self.device_file)
        except Exception:
            pass
        return uid

    def _ua(self):
        return (
            f'BuildID=app.p87433.p4d26a192d2f415764a00;SysType=android;DevID={self.uid};Ver=1.12.2;'
            f'DevType=22127RK46C;DeviceBrand=Redmi;DeviceModel=22127RK46C;SystemName=Android;'
            f'SystemVersion=14;Terminal=1;IsH5=0;Sid='
        )

    def _headers(self):
        h = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
            'X-User-Agent': self._ua(),
            'Content-Type': 'application/json',
            'temp': 'test',
            'Accept': 'application/json, text/plain, */*',
            'Referer': self.site_referer,
            'Origin': self.site_referer.rstrip('/'),
        }
        if self.token:
            h['Authorization'] = self.token
        return h

    def _pick_host(self):
        self._runtime()
        for h in self.api_hosts:
            try:
                r = self.session.get(h + '/api/app/ping/check', headers=self._headers(), timeout=8, verify=False)
                if r.json().get('code') == 200:
                    self.host = h
                    return h
            except Exception:
                continue
        self.host = self.api_hosts[0]
        return self.host

    def _ensure_login(self):
        if self.ready and self.token:
            return True
        try:
            if not self.uid:
                self.uid = self._gen_uid()
            self._pick_host()
            url = self.host + '/api/app/mine/login'
            body = {'data': self._enc_param({'devID': self.uid, 'sysType': 'android', 'isAppStore': False})}
            r = self.session.post(url, headers=self._headers(), json=body, timeout=12, verify=False)
            j = r.json()
            if j.get('code') != 200:
                return False
            data = self._dec_data(j.get('data')) if j.get('hash') else (j.get('data') or {})
            self.token = data.get('token') or ''
            self.ready = bool(self.token)
            self._load_source()
            return self.ready
        except Exception:
            self.ready = False
            return False

    def _load_source(self):
        try:
            data = self._req('GET', '/ping/domain')
            for s in data.get('sourceList') or []:
                t = s.get('type')
                doms = s.get('domain') or []
                if not doms:
                    continue
                u = ''
                d0 = doms[0]
                if isinstance(d0, dict):
                    u = d0.get('url') or ''
                else:
                    u = str(d0 or '')
                if not u:
                    continue
                if t == 'IMAGE':
                    self.img_host = u.rstrip('/')
                elif t == 'VID':
                    self.vid_host = u.rstrip('/')
                elif t == 'AUDIO':
                    self.audio_host = u.rstrip('/')
        except Exception:
            pass

    def _req(self, method, path, params=None, data=None):
        if not self._ensure_login():
            return {}
        url = self.host + '/api/app' + path
        try:
            if method == 'GET':
                kw = {}
                if params is not None:
                    kw['params'] = {'data': self._enc_param({k: str(v) for k, v in params.items() if v is not None})}
                r = self.session.get(url, headers=self._headers(), timeout=15, verify=False, **kw)
            else:
                payload = None
                if data is not None:
                    if isinstance(data, dict):
                        norm = {}
                        for k, v in data.items():
                            if v is None:
                                continue
                            if isinstance(v, (list, dict, bool, int, float)):
                                norm[k] = v
                            else:
                                norm[k] = str(v)
                        payload = {'data': self._enc_param(norm)}
                    else:
                        payload = {'data': self._enc_param(data)}
                r = self.session.post(url, headers=self._headers(), json=payload, timeout=15, verify=False)
            j = r.json()
            if j.get('code') != 200:
                return {}
            return self._dec_data(j.get('data')) if j.get('hash') else (j.get('data') or {})
        except Exception:
            return {}

    def _static_filters(self):
        sort = {'key': 'sort', 'name': '排序', 'value': self.SORT_MAP}
        video_rows = []
        for n, v in [
            ('推荐', 'mod:650c14aac8adc51465ea1b26'),
            ('最新', 'mod:6997d46a84c6be0f8421d0b2'),
            ('国产', 'mod:650c1527c8adc51465ea1b45'),
            ('乱伦', 'mod:650c14bfc8adc51465ea1b2c'),
            ('日韩', 'mod:650c14e4c8adc51465ea1b36'),
            ('萝莉', 'mod:672f318e7bc3b471ac059d81'),
        ]:
            video_rows.append({
                'key': f'cate_{v.split(":",1)[1][:8]}',
                'name': n,
                'value': [{'n': '全部', 'v': v}, {'n': n, 'v': v}],
            })
        video_rows.append(sort)
        return {
            'video_all': video_rows,
            'pic_all': [{
                'key': 'cate_pic_cos',
                'name': 'Cosplay',
                'value': [{'n': '全部', 'v': 'mod:65c2e9aa3499fc57e0f1dafd'}, {'n': 'Cosplay', 'v': 'mod:65c2e9aa3499fc57e0f1dafd'}],
            }, sort],
            'comic_all': [{
                'key': 'cate_comic',
                'name': '漫画',
                'value': [{'n': '全部', 'v': 'mod:67b7f7e5ac310312c98dc12a'}],
            }],
            'novel_all': [{
                'key': 'cate_novel_audio',
                'name': '有声小说',
                'value': [{'n': '全部', 'v': 'mod:680b7e3361ffc2e4224f7b7c'}],
            }, {
                'key': 'cate_novel_family',
                'name': '家庭乱伦',
                'value': [{'n': '全部', 'v': 'mod:6818ba8e09f06f3a9282636f'}],
            }, sort],
            'tik_all': [{
                'key': 'cate_tik',
                'name': '抖音',
                'value': [{'n': '全部', 'v': 'mod:68c02b57c23a546a4491056c'}],
            }],
            'community_all': [],
            'deep_all': [],
                        'hot_all': [],
        }

    def _pack_modules(self, arr, zone):
        vals = []
        for m0 in arr or []:
            mid = str(m0.get('id') or '')
            name = str(m0.get('moduleName') or m0.get('name') or mid)
            if not mid:
                continue
            vals.append({'n': name, 'v': f'mod:{mid}'})
            self.module_map[mid] = {'zone': zone, 'name': name, 'type': m0.get('type')}
        return vals

    def _real_sections(self, name, sections=None):
        """有效子分类：排除空、与父同名的假子项"""
        out = []
        pname = str(name or '').strip()
        for sct in sections or []:
            sid = str(sct.get('sectionID') or sct.get('id') or '')
            sname = str(sct.get('sectionName') or sct.get('name') or '').strip()
            if not sid or not sname:
                continue
            if sname == pname:
                continue
            out.append({'sid': sid, 'name': sname})
        return out

    def _row_from_module(self, m0, zone, sections=None):
        """仅当存在真实子分类时，才生成土豆式父分类行"""
        mid = str(m0.get('id') or '')
        name = str(m0.get('moduleName') or m0.get('name') or mid)
        if not mid:
            return None
        self.module_map[mid] = {'zone': zone, 'name': name, 'type': m0.get('type')}
        real = self._real_sections(name, sections)
        if not real:
            return None
        vals = [{'n': '全部', 'v': f'mod:{mid}'}]
        for s in real:
            vals.append({'n': s['name'], 'v': f"msec:{s['sid']}"})
        return {
            'key': f'cate_mod_{mid}',
            'name': name,
            'value': vals,
        }

    def _flat_modules_filter(self, arr, zone, key='cate_id', title='分类'):
        """无子分类：单行平铺，不造假多行父分类"""
        vals = []
        for m0 in arr or []:
            mid = str(m0.get('id') or '')
            name = str(m0.get('moduleName') or m0.get('name') or mid)
            if not mid:
                continue
            self.module_map[mid] = {'zone': zone, 'name': name, 'type': m0.get('type')}
            vals.append({'n': name, 'v': f'mod:{mid}'})
        if not vals:
            return []
        return [{'key': key, 'name': title, 'value': vals}]


    def _item_community(self, v):
        """社区帖：统一入口；详情内再拆视频+图集。"""
        if not isinstance(v, dict):
            return None
        vid = str(v.get('id') or '')
        if not vid:
            return None
        name = str(v.get('title') or v.get('name') or '未命名')
        pic_raw = str(v.get('cover') or v.get('verticalCover') or v.get('horizontalCover') or '')
        news = str(v.get('newsType') or '')
        source = str(v.get('sourceURL') or v.get('previewURL') or '')
        sc = v.get('seriesCover') or []
        n_img = len(sc) if isinstance(sc, list) else 0
        has_video = bool(source)
        has_pic = n_img > 0 or news in ('COVER', 'PIC')
        if has_video and has_pic:
            remark = f"🎬+🖼️ {n_img}张" if n_img else '🎬+🖼️'
        elif has_pic and not has_video:
            remark = f"🖼️ {n_img}张" if n_img else '🖼️ 图集'
        else:
            dur = int(v.get('playTime') or 0)
            if dur > 0:
                remark = f"{dur // 60:02d}:{dur % 60:02d}"
            elif news == 'SHORT':
                remark = '📱 短视频'
            elif news == 'SEED_LINK':
                remark = '🔗 资源'
            else:
                remark = '🎬 视频'
        return {
            'vod_id': f"post@@{vid}@@{quote(name)}@@{quote(pic_raw)}@@{quote(source)}@@{news or 'SP'}",
            'vod_name': name,
            'vod_pic': self._img(pic_raw),
            'vod_remarks': remark,
        }

    def _community_module_list(self, mid, page, page_size=15, module_sort='3', tag_id=''):
        if not mid:
            return {}
        params = {'pageNumber': int(page), 'pageSize': int(page_size), 'moduleSort': str(module_sort or '3')}
        if tag_id:
            params['tagId'] = str(tag_id)
        return self._req('GET', f'/vid/module/{mid}', params=params) or {}

    def _community_fetch_raw(self, rid, page, page_size=20, sort_type='3'):
        """社区网页真实参数：moduleSort=3/1/2/5/6，标签随父模块提交 tagId。"""
        rid = str(rid or 'all')
        if rid == 'all' or rid.startswith('all'):
            mods = sorted(mid for mid, info in (self.module_map or {}).items()
                          if (info or {}).get('zone') == 'community')
            if not mods:
                return {}
            out = []
            for mid in mods:
                d = self._community_module_list(mid, page, max(5, page_size // max(1, len(mods))), sort_type)
                out.extend(self._extract_list(d))
            return {'allVideoInfo': out, 'hasNext': True}
        if rid.startswith('mod:'):
            return self._community_module_list(rid[4:], page, page_size, sort_type)
        if rid.startswith('tag:'):
            tid = rid[4:]
            mid = str((self.community_tag_parent or {}).get(tid) or '')
            if mid:
                return self._community_module_list(mid, page, page_size, sort_type, tid)
            return self._tag_list(tid, page, page_size, sort_type) or {}
        if rid.startswith('mtag:'):
            parts = rid.split(':', 2)
            if len(parts) == 3:
                return self._community_module_list(parts[1], page, page_size, sort_type, parts[2])
            return {}
        if rid.startswith('msec:'):
            route = (self.route_parent or {}).get(rid) or {}
            mid = str(route.get('mid') or '')
            data = self._msec_list(rid[5:], page, page_size, sort_type, mid, 'community', route.get('name') or '')
            if self._extract_list(data):
                return data
            return self._community_module_list(mid, page, page_size, sort_type) if mid else {}
        return self._community_module_list(rid, page, page_size, sort_type)

    def _community_list(self, rid, page, page_size=15, sort_type='3'):
        """社区混排：视频帖/图片帖/混合帖同列表，详情再拆多线路。"""
        page = int(page or 1)
        page_size = int(page_size or 15)
        data = self._community_fetch_raw(rid, page, page_size, sort_type) or {}
        chunk = self._extract_list(data)
        return {'allVideoInfo': chunk, 'hasNext': bool(data.get('hasNext') is not False and chunk)}

    def _build_community_filters(self, arr):
        """社区宫格：每个模块一行父分类，行内为该宫格全部及真实 allTags。"""
        arr = list(arr or [])

        def fetch_row(m0):
            mid = str(m0.get('id') or '')
            name = str(m0.get('moduleName') or m0.get('name') or mid)
            if not mid:
                return None
            self.module_map[mid] = {'zone': 'community', 'name': name, 'type': m0.get('type')}
            try:
                data = self._module_list(mid, 1, 1) or {}
            except Exception:
                data = {}
            values = [{'n': '全部', 'v': f'mod:{mid}'}]
            seen = set()
            for section in data.get('allSection') or []:
                for tag in section.get('allTags') or []:
                    tid = str(tag.get('tagID') or tag.get('id') or '')
                    tname = str(tag.get('tagName') or tag.get('name') or tid)
                    if not tid or tid in seen:
                        continue
                    seen.add(tid)
                    self.tag_map[tid] = tname
                    values.append({'n': tname, 'v': f'tag:{tid}'})
            return {'key': f'cate_mod_{mid}', 'name': name, 'value': values}

        try:
            with ThreadPoolExecutor(max_workers=min(4, max(1, len(arr)))) as pool:
                rows = list(pool.map(fetch_row, arr))
        except Exception:
            rows = [fetch_row(item) for item in arr]
        rows = [row for row in rows if row]
        if rows:
            rows.append({'key': 'sort', 'name': '帖子', 'value': self.COMMUNITY_SORT_MAP})
        return rows



    def _build_tik_filters(self, arr):
        values = []
        for m0 in arr or []:
            mid = str(m0.get('id') or '')
            name = str(m0.get('moduleName') or m0.get('name') or '短视频')
            if mid:
                self.module_map[mid] = {'zone': 'tik', 'name': name, 'type': m0.get('type')}
                values.append({'n': name, 'v': f'mod:{mid}'})
        try:
            live = self._req('POST', '/live/module/list/lld', data={'time': int(time.time())}) or {}
            values.append({'n': '直播推荐', 'v': 'live:tj'})
            for item in live.get('module') or []:
                lid = str(item.get('id') or '')
                name = str(item.get('title') or item.get('name') or lid)
                if lid:
                    values.append({'n': name, 'v': f'live:{lid}'})
        except Exception:
            pass
        if not any(str(x.get('v') or '').startswith('live:') for x in values):
            values.extend([
                {'n': '直播推荐', 'v': 'live:tj'},
                {'n': '中国', 'v': 'live:6763e704daf2ddeb39b0ec83'},
                {'n': '日韩', 'v': 'live:6763e717daf2ddeb39b0ec84'},
                {'n': '越南', 'v': 'live:6763e750daf2ddeb39b0ec87'},
                {'n': '乌克兰', 'v': 'live:6763e72bdaf2ddeb39b0ec85'},
                {'n': '俄罗斯', 'v': 'live:6763e73bdaf2ddeb39b0ec86'},
                {'n': '欧美', 'v': 'live:6763e768daf2ddeb39b0ec88'},
                {'n': '男主播', 'v': 'live:6763e7b6daf2ddeb39b0ec8a'},
            ])
        return [{'key': 'cate_tik', 'name': '分区', 'value': values}] if values else []

    def _live_request(self, path, data):
        if not self._ensure_login():
            return {}
        try:
            payload = dict(data or {})
            if 'time' in payload:
                payload['time'] = int(time.time() + 0.999)
            r = self.session.post(
                self.host + '/api/app' + path,
                headers=self._headers(), json={'data': self._enc_param(payload)},
                timeout=20, verify=False)
            obj = r.json()
            if obj.get('code') != 200:
                return {}
            return (self._dec_data(obj.get('data'), self.live_interface_key)
                    if obj.get('hash') else (obj.get('data') or {}))
        except Exception:
            return {}

    def _live_list(self, live_id, page, page_size=20):
        now = int(time.time())
        if str(live_id) == 'tj':
            data = self._live_request('/live/module/list/lld', {'time': now}) or {}
            out, seen = [], set()
            for block in data.get('recom') or []:
                for item in block.get('anchors') or []:
                    aid = str(item.get('id') or '')
                    if aid and aid not in seen:
                        seen.add(aid)
                        out.append(item)
            start = (int(page) - 1) * int(page_size)
            chunk = out[start:start + int(page_size)]
            return {'list': chunk, 'hasNext': start + int(page_size) < len(out)}
        return self._live_request('/live/anchor/list/lld', {
            'id': str(live_id), 'pageNumber': int(page), 'pageSize': int(page_size), 'time': now
        }) or {}

    def _item_live(self, item):
        if not isinstance(item, dict):
            return None
        aid = str(item.get('id') or '')
        url = str(item.get('url') or '')
        if not aid or not url:
            return None
        name = str(item.get('name') or '直播间')
        pic = str(item.get('coverImg') or '')
        viewers = int(item.get('viewCount') or 0)
        status = '直播中' if item.get('isOnline') is not False else '离线'
        return {
            'vod_id': f'live@@{aid}@@{quote(name)}@@{quote(pic)}@@{quote(url)}',
            'vod_name': name, 'vod_pic': pic,
            'vod_remarks': f'{status} · {viewers}人' if viewers else status,
        }

    def _normalize_cate_filters(self):
        """新土豆模式：所有宫格行统一 cate_id；内部另存父模块关系。"""
        self.route_parent = {}
        zone_map = {
            'video_all': 'video', 'pic_all': 'pic', 'comic_all': 'comic',
            'novel_all': 'novel', 'tik_all': 'tik', 'live_all': 'live',
            'community_all': 'community', 'deep_all': 'deep', 'hot_all': 'video',
        }
        for zid, rows in (self.filters or {}).items():
            zone = zone_map.get(zid, 'video')
            for row in rows or []:
                key = str(row.get('key') or '')
                if key == 'sort':
                    continue
                values = row.get('value') or []
                parent_mid = key[len('cate_mod_'):] if key.startswith('cate_mod_') else ''
                if not parent_mid:
                    for item in values:
                        value = str(item.get('v') or '')
                        if value.startswith('mod:'):
                            parent_mid = value[4:]
                            break
                for item in values:
                    value = str(item.get('v') or '')
                    if value:
                        self.route_parent[value] = {
                            'mid': parent_mid, 'zone': zone,
                            'row': str(row.get('name') or ''),
                            'name': str(item.get('n') or ''),
                        }
                        if zone == 'community' and parent_mid and value.startswith('tag:'):
                            self.community_tag_parent[value[4:]] = parent_mid
                row['key'] = 'cate_id'

    def _rich(self, name, route):
        name = str(name or '').strip()
        route = str(route or '').strip()
        if not name or not route:
            return ''
        payload = json.dumps({'id': route, 'name': name}, ensure_ascii=False, separators=(',', ':'))
        return '[a=cr:%s/]%s[/a]' % (payload, name)

    def _route_id(self, tid):
        if isinstance(tid, dict):
            return str(tid.get('id') or '')
        value = unquote(str(tid or '').strip())
        if value.startswith('{'):
            try:
                obj = json.loads(value)
                if isinstance(obj, dict):
                    return str(obj.get('id') or '')
            except Exception:
                pass
        return value

    def _get_selected_id(self, extend, default_id=''):
        """新土豆同款：统一优先读取 cate_id，兼容旧缓存中的 cate_*。"""
        if not isinstance(extend, dict):
            return default_id
        value = extend.get('cate_id')
        if value not in (None, ''):
            return str(value)
        for k, v in extend.items():
            if str(k).startswith('cate_') and v not in (None, ''):
                return str(v)
        return default_id

    def _load_modules(self):
        data = self._req('GET', '/modules/list')
        if not isinstance(data, dict):
            return
        fmap = {}
        self.module_map = {}
        self.tag_map = {}

        home = data.get('homePage') or []
        video_mods, comic_mods = [], []
        for m0 in home:
            if int(m0.get('type') or 0) == 5:
                comic_mods.append(m0)
            else:
                video_mods.append(m0)

        def rows_from_modules(arr, zone, with_section=False):
            rows = []
            arr = list(arr or [])
            sec_map = {}
            if with_section and arr:
                def fetch_sec(m0):
                    mid = str(m0.get('id') or '')
                    if not mid:
                        return mid, []
                    try:
                        d = self._module_list(mid, 1, 1) or {}
                        return mid, d.get('allSection') or []
                    except Exception:
                        return mid, []
                try:
                    with ThreadPoolExecutor(max_workers=min(8, max(1, len(arr)))) as ex:
                        for mid, secs in ex.map(fetch_sec, arr):
                            if mid:
                                sec_map[mid] = secs
                except Exception:
                    for m0 in arr:
                        mid, secs = fetch_sec(m0)
                        if mid:
                            sec_map[mid] = secs
            for m0 in arr:
                mid = str(m0.get('id') or '')
                row = self._row_from_module(m0, zone, sec_map.get(mid) if with_section else None)
                if row:
                    rows.append(row)
            return rows

        video_rows = rows_from_modules(video_mods, 'video', with_section=True)
        have = set()
        for r in video_rows:
            k = str(r.get('key') or '')
            if k.startswith('cate_mod_'):
                have.add(k[len('cate_mod_'):])
        rest = [m for m in video_mods if str(m.get('id') or '') not in have]
        if rest:
            video_rows.extend(self._flat_modules_filter(rest, 'video', key='cate_video_more', title='其它模块'))

        try:
            sec = self._req('GET', '/vid/sections') or {}
            community_sections = {'热门推荐', '分享交友', '暗黑探索', '发现精彩'}
            community_tag_ids = set()
            for sct in sec.get('sections') or []:
                sid = str(sct.get('sectionID') or sct.get('id') or '')
                sname = str(sct.get('sectionName') or sct.get('name') or '标签')
                tags = sct.get('allTags') or []
                if sname in community_sections:
                    community_tag_ids.update(str(tg.get('id') or tg.get('tagID') or '') for tg in tags if isinstance(tg, dict))
                    continue
                vals = []
                for tg in tags:
                    tid = str(tg.get('id') or '')
                    tname = str(tg.get('tagName') or tid)
                    if not tid:
                        continue
                    self.tag_map[tid] = tname
                    vals.append({'n': tname, 'v': f'tag:{tid}'})
                if not vals:
                    continue
                vals = [{'n': '全部', 'v': vals[0]['v']}] + vals
                video_rows.append({
                    'key': f'cate_sec_{sid or sname}',
                    'name': sname,
                    'value': vals,
                })
        except Exception:
            pass

        try:
            conf = self._req('GET', '/tag/conf/list') or {}
            more = []
            for tg in conf.get('tags') or []:
                tid = str(tg.get('id') or '')
                tname = str(tg.get('tagName') or tid)
                if not tid or tid in self.tag_map or tid in community_tag_ids:
                    continue
                self.tag_map[tid] = tname
                more.append({'n': tname, 'v': f'tag:{tid}'})
            if more:
                more = [{'n': '全部', 'v': more[0]['v']}] + more
                video_rows.append({'key': 'cate_tag_more', 'name': '更多标签', 'value': more})
        except Exception:
            pass

        video_rows.append({'key': 'sort', 'name': '排序', 'value': self.SORT_MAP})
        fmap['video_all'] = video_rows

        def zone_filters(arr, zone, with_sort=True, with_section=True, flat_title='分类'):
            arr = list(arr or [])
            rows = []
            if with_section and arr:
                rows = rows_from_modules(arr, zone, with_section=True)
            if not rows:
                rows = self._flat_modules_filter(arr, zone, key=f'cate_{zone}', title=flat_title)
            else:
                have = set()
                for r in rows:
                    k = str(r.get('key') or '')
                    if k.startswith('cate_mod_'):
                        have.add(k[len('cate_mod_'):])
                rest = [m for m in arr if str(m.get('id') or '') not in have]
                if rest:
                    rows.extend(self._flat_modules_filter(rest, zone, key=f'cate_{zone}_more', title='其它分类'))
            if with_sort and rows:
                rows = rows + [{'key': 'sort', 'name': '排序', 'value': self.SORT_MAP}]
            return rows

        fmap['pic_all'] = zone_filters(data.get('pics') or [], 'pic', flat_title='图集分类')
        fmap['comic_all'] = zone_filters(comic_mods, 'comic', flat_title='漫画分类')
        fmap['novel_all'] = zone_filters(data.get('novel') or [], 'novel', flat_title='小说分类')
        fmap['tik_all'] = self._build_tik_filters(data.get('douYin') or [])
        fmap['community_all'] = self._build_community_filters(data.get('community') or [])
        fmap['deep_all'] = zone_filters(data.get('deepWeb') or [], 'deep', flat_title='深网分类')
        fmap['hot_all'] = []
        self.filters = fmap
        self._normalize_cate_filters()
        self.classes = [c for c in self.classes if c.get('type_id') != 'naked_all']

    def _abs(self, path, kind='img'):
        if not path:
            return ''
        p = str(path)
        if p.startswith('http'):
            return p
        base = self.img_host if kind == 'img' else (self.vid_host if kind == 'vid' else self.audio_host)
        return base.rstrip('/') + '/' + p.lstrip('/')

    def _proxy(self, url):
        if not url:
            return ''
        try:
            base = self.getProxyUrl()
        except Exception:
            base = ''
        if not base:
            return url
        return base + '&url=' + quote(url, safe='')

    def _img(self, path):
        return self._proxy(self._abs(path, 'img'))

    def _play_header(self):
        return {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
            'Referer': self.site_referer,
            'Origin': self.site_referer.rstrip('/'),
        }
    def _video_header(self):
        return {
            'User-Agent': 'Mozilla/5.0',
            'Referer': self.site_referer,
        }


    def _m3u8_play_url(self, source):
        """官方 H5 播放：/api/app/vid/h5/m3u8/{sourceURL}?token=&c=CDN"""
        if not source:
            return ''
        self._ensure_login()
        src = unquote(str(source)).lstrip('/')
        if src.startswith('http') and '.m3u8' in src:
            if '/api/app/vid/h5/m3u8/' in src:
                return src
            for prefix in (self.vid_host.rstrip('/') + '/', 'https://zzzsts.lkkwip.cn/'):
                if src.startswith(prefix):
                    src = src[len(prefix):]
                    break
        if src.startswith('http'):
            return src
        return f"{self.host}/api/app/vid/h5/m3u8/{src}?token={self.token}&c={self.vid_host}"
    def _extract_list(self, data):
        if not isinstance(data, dict):
            return data if isinstance(data, list) else []
        for k in ['allVideoInfo', 'allMediaInfo', 'chosenVideoInfo', 'videos', 'medias', 'list', 'data', 'records']:
            v = data.get(k)
            if isinstance(v, list) and v:
                return v
        return []


    def _item_video(self, v):
        vid = str(v.get('id') or '')
        if not vid:
            return None
        name = str(v.get('title') or v.get('name') or '未命名')
        pic_raw = str(v.get('cover') or v.get('verticalCover') or v.get('horizontalCover') or '')
        news = str(v.get('newsType') or 'SP')
        source = str(v.get('sourceURL') or v.get('previewURL') or '')
        sc = v.get('seriesCover') or []
        n_img = len(sc) if isinstance(sc, list) else 0
        if news in ('PIC', 'COVER') and (news == 'PIC' or sc):
            remark = f"🖼️ {n_img}张" if n_img else '🖼️ 图集'
            vod_id = f"pic@@{vid}@@{quote(name)}@@{quote(pic_raw)}"
        else:
            dur = int(v.get('playTime') or 0)
            if n_img and source:
                remark = f"🎬+🖼️ {n_img}张"
            elif dur > 0:
                remark = f"{dur // 60:02d}:{dur % 60:02d}"
            else:
                remark = '🎬 视频' if news != 'SHORT' else '📱 短视频'
            vod_id = f"video@@{vid}@@{quote(source)}@@{quote(name)}@@{quote(pic_raw)}@@{news}"
        return {
            'vod_id': vod_id,
            'vod_name': name,
            'vod_pic': self._img(pic_raw),
            'vod_remarks': remark,
        }

    def _media_kind(self, v, zone=''):
        """按接口真实 mediaType 判型，避免 video 动漫被兜底成小说。"""
        mt = str(v.get('mediaType') or '').strip().lower()
        sub = int(v.get('mediaSubType') or 0)
        if mt == 'image':
            return 'comic'
        if mt == 'video':
            return 'anime'
        if mt in ('audio', 'text') or sub == 1:
            return 'novel'
        return zone if zone in ('comic', 'novel', 'anime') else 'novel'

    def _item_media(self, v, zone=''):
        vid = str(v.get('id') or '')
        if not vid:
            return None
        name = str(v.get('title') or v.get('name') or '未命名')
        pic_raw = str(v.get('verticalCover') or v.get('horizontalCover') or v.get('cover') or '')
        sub = int(v.get('mediaSubType') or 0)
        total = int(v.get('totalEpisode') or 0)
        prefix = self._media_kind(v, zone)
        if prefix == 'comic':
            remark = f"📚 {total}话" if total else '📚 漫画'
        elif prefix == 'anime':
            remark = f"🎞️ {total}集" if total else '🎞️ 动漫'
        elif sub == 1 or '有声' in name:
            remark = f"🎧 {total}集" if total else '🎧 有声'
        else:
            remark = f"📖 {total}章" if total else '📖 小说'
        return {
            'vod_id': f"{prefix}@@{vid}@@{quote(name)}@@{quote(pic_raw)}",
            'vod_name': name,
            'vod_pic': self._img(pic_raw),
            'vod_remarks': remark,
        }

    def _module_list(self, mid, page, page_size=15, sort_type=''):
        if not mid:
            return {}
        params = {'pageNumber': int(page), 'pageSize': int(page_size)}
        if sort_type:
            params['sortType'] = str(sort_type)
        return self._req('GET', f'/vid/module/{mid}', params=params) or {}

    def _tag_list(self, tag_id, page, page_size=15, sort_type='1'):
        if not tag_id:
            return {}
        params = {
            'pageNumber': int(page),
            'pageSize': int(page_size),
            'tagID': str(tag_id),
            'sortType': str(sort_type or '1'),
        }
        return self._req('GET', '/tag/vid/list', params=params) or {}

    def _msec_list(self, section_id, page, page_size=15, sort_type='', module_id='', zone='', section_name=''):
        """allSection 子分类列表。"""
        if not section_id:
            return {}
        st = str(sort_type or '1')
        if st in ('new', 'hot'):
            vsort, msort = st, ('1' if st == 'new' else '2')
        elif st.isdigit():
            msort = '1' if st in ('1', '2') else '2'
            vsort = 'new' if st in ('1', '2') else 'hot'
        else:
            vsort, msort = 'new', '1'

        data = self._req('GET', f'/vid/section/{section_id}', params={
            'pageNumber': int(page),
            'pageSize': int(page_size),
            'sortType': vsort,
        }) or {}
        if self._extract_list(data):
            return data

        mid = str(module_id or '')
        if mid:
            data = self._req('GET', f'/vid/module/{mid}', params={
                'pageNumber': int(page),
                'pageSize': int(page_size),
                'moduleSort': msort,
                'tagId': str(section_id),
            }) or {}
            base = self._module_list(mid, page, page_size, msort) or {}
            a = [str(x.get('id') or '') for x in self._extract_list(data)[:5]]
            b = [str(x.get('id') or '') for x in self._extract_list(base)[:5]]
            if a and a != b:
                return data

        parent = {}
        if mid:
            parent = self._module_list(mid, page, page_size, msort) or {}
            for sec in parent.get('allSection') or []:
                if str(sec.get('sectionID') or sec.get('id') or '') != str(section_id):
                    continue
                embedded = self._extract_list(sec)
                if embedded:
                    key = 'allMediaInfo' if zone in ('comic', 'novel') else 'allVideoInfo'
                    return {key: embedded[:int(page_size)], 'hasNext': bool(parent.get('hasNext'))}
                break
            if zone == 'comic' and self._extract_list(parent):
                return parent

        kw = str(section_name or '').strip()
        if mid and zone in ('comic', 'novel') and kw and kw not in ('全部',):
            aliases = {
                '全彩涩漫': ['全彩'], '同人漫画': ['同人'], '3D漫画': ['3D'], '吸晴韩漫': ['韩漫', '韩漫'],
                '童颜萝莉': ['萝莉', '幼女', '双马尾'], '丰满尤物': ['巨乳', '爆乳'], '禁忌乱伦': ['乱伦'],
                'AI绘图': ['AI', 'AI繪圖', 'AI绘图'], '人妻阿姨': ['人妻', '熟女'], '恋上辣妹': ['辣妹', 'JK'],
                '强暴轮奸': ['轮奸', '强暴'], '荒淫校园': ['校园', '校服'], '泳装特辑': ['泳装', '水着'],
                '爆射C106': ['C106'], '原神剧场': ['原神'], '七龙珠': ['龙珠', '七龙珠'], 'NTR': ['NTR'],
                '毁童年系列': ['童年', '毁童年'], '肉便器': ['肉便器'], '紧致处女': ['处女'],
            }
            keys = aliases.get(kw, [kw])
            matched = []
            need = int(page) * int(page_size)
            for pg in range(1, 12):
                chunk = self._extract_list(self._module_list(mid, pg, 30, msort) or {})
                if not chunk:
                    break
                for x in chunk:
                    blob = ' '.join([
                        str(x.get('title') or ''),
                        str(x.get('summary') or ''),
                        ' '.join([str(t.get('tagName') if isinstance(t, dict) else t) for t in (x.get('tagDetails') or x.get('tags') or [])]),
                    ])
                    if any(k and k in blob for k in keys):
                        matched.append(x)
                if len(matched) >= need:
                    break
            start = (int(page) - 1) * int(page_size)
            part = matched[start:start + int(page_size)]
            if part:
                return {'allMediaInfo': part, 'hasNext': len(matched) > start + int(page_size)}

        if mid:
            return self._module_list(mid, page, page_size, msort) or {}
        return {}


    def _default_cate(self, tid):
        for block in (self.filters.get(tid) or []):
            if str(block.get('key') or '').startswith('cate_'):
                for x in block.get('value') or []:
                    if x.get('v'):
                        return x.get('v')
        return ''

    def _export_filters_json(self):
        try:
            path = '/storage/emulated/0/tvbox/sites-py/91国产集合完整版_内置筛选备份.json'
            obj = {'class': self.classes, 'filters': self.filters}
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def homeContent(self, filter):
        return {'class': self.classes, 'filters': self.filters}

    def getHomeContent(self, filter=True):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            selected = str(self._default_cate('video_all') or '')
            mid = selected[4:] if selected.startswith('mod:') else '650c14aac8adc51465ea1b26'
            data = self._module_list(mid, 1, 12)
            lst = []
            for v in self._extract_list(data):
                try:
                    if 'mediaType' in v:
                        it = self._item_media(v)
                    else:
                        it = self._item_video(v)
                    if it:
                        lst.append(it)
                except Exception:
                    continue
            return {'list': lst}
        except Exception:
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        result = {'list': [], 'page': int(pg or 1), 'pagecount': 99, 'limit': 15, 'total': 999999}
        try:
            if isinstance(extend, str) and extend:
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            if not isinstance(extend, dict):
                extend = {}

            stid = self._route_id(tid)
            if stid.startswith('search:'):
                return self.searchContent(stid[7:], False, pg)
            if stid.startswith('tag:'):
                return self._tag_route_list(stid[4:], pg)
            if stid.startswith('type:'):
                return self._module_route_list(stid[5:], pg)

            sort_type = str(extend.get('sort') or '1')

            if stid == 'hot_all':
                data = self._req('GET', '/search/hotVid/list', params={'pageNumber': int(pg), 'pageSize': 15}) or {}
                for v in self._extract_list(data) or data.get('data') or []:
                    try:
                        it = self._item_video(v)
                        if it:
                            result['list'].append(it)
                    except Exception:
                        continue
                return result

            selected = self._get_selected_id(extend, self._default_cate(stid))
            if not selected:
                return result

            kind, rid = selected, selected
            if ':' in selected:
                kind, rid = selected.split(':', 1)

            if stid == 'tik_all' and kind == 'tik':
                data = self._req('GET', '/vid/recommend/list', params={
                    'pageNumber': int(pg), 'pageSize': 20, 'newsType': rid or 'SHORT'
                }) or {}
                for raw in self._extract_list(data):
                    try:
                        item = self._item_video(raw)
                        if item:
                            result['list'].append(item)
                    except Exception:
                        continue
                result['limit'] = 20
                if data.get('hasNext') is False:
                    result['pagecount'] = int(pg)
                return result

            if stid in ('tik_all', 'live_all') and kind == 'live':
                data = self._live_list(rid, pg, 20)
                for item in data.get('list') or []:
                    try:
                        vod = self._item_live(item)
                        if vod:
                            result['list'].append(vod)
                    except Exception:
                        continue
                result['limit'] = 20
                if data.get('hasNext') is False:
                    result['pagecount'] = int(pg)
                return result

            if stid == 'community_all':
                crid = selected
                if kind in ('cvid', 'cpic', 'line'):
                    crid = rid if kind != 'line' else 'all'
                elif kind in ('mod', 'tag'):
                    crid = selected
                elif selected in ('', 'community_all', 'video', 'pic'):
                    crid = 'all'
                else:
                    crid = selected if selected != 'all' else 'all'
                    if kind == 'all' or selected == 'all':
                        crid = 'all'
                if crid.startswith('cvid:') or crid.startswith('cpic:'):
                    crid = crid.split(':', 1)[1]
                data = self._community_list(crid, pg, 15, sort_type)
                for v in self._extract_list(data):
                    try:
                        it = self._item_community(v)
                        if it:
                            result['list'].append(it)
                    except Exception:
                        continue
                if data.get('hasNext') is False:
                    result['pagecount'] = int(pg)
                return result

            if kind == 'tag':
                data = self._tag_list(rid, pg, 15, sort_type)
                zone = 'video'
            elif kind == 'msec':
                meta = (self.route_parent or {}).get(selected) or {}
                mid_guess = str(meta.get('mid') or '')
                zone = str(meta.get('zone') or '') or {
                    'pic_all': 'pic', 'comic_all': 'comic', 'novel_all': 'novel',
                    'tik_all': 'tik', 'community_all': 'community', 'deep_all': 'deep',
                }.get(stid, 'video')
                sec_name = str(meta.get('name') or '')
                data = self._msec_list(rid, pg, 15, sort_type,
                                       module_id=mid_guess, zone=zone, section_name=sec_name)
            else:
                mid = rid if kind == 'mod' else selected
                data = self._module_list(mid, pg, 15, sort_type)
                zone = (self.module_map.get(mid) or {}).get('zone') or ''
                if not zone:
                    zone = {
                        'pic_all': 'pic', 'comic_all': 'comic', 'novel_all': 'novel',
                        'tik_all': 'tik', 'community_all': 'community', 'deep_all': 'deep',
                        'naked_all': 'naked'
                    }.get(stid, 'video')

            for v in self._extract_list(data):
                try:
                    if zone in ('novel', 'comic') or 'mediaType' in v:
                        it = self._item_media(v, zone)
                    else:
                        it = self._item_video(v)
                    if it:
                        result['list'].append(it)
                except Exception:
                    continue
            if data.get('hasNext') is False and stid != 'tik_all':
                result['pagecount'] = int(pg)
            elif stid == 'tik_all' and not result['list']:
                result['pagecount'] = max(1, int(pg) - 1)
            return result
        except Exception:
            return result

    def _module_route_list(self, module_id, pg):
        page = max(1, int(pg or 1))
        result = {'list': [], 'page': page, 'pagecount': page, 'limit': 15, 'total': 0}
        data = self._module_list(str(module_id), page, 15, '1') or {}
        for raw in self._extract_list(data):
            try:
                item = self._item_video(raw)
                if item:
                    result['list'].append(item)
            except Exception:
                continue
        if data.get('hasNext'):
            result['pagecount'] = page + 1
        result['total'] = int(data.get('total') or len(result['list']))
        return result

    def _tag_route_list(self, tag_id, pg):
        page = max(1, int(pg or 1))
        result = {'list': [], 'page': page, 'pagecount': page, 'limit': 15, 'total': 0}
        data = self._tag_list(str(tag_id), page, 15, '1') or {}
        for raw in self._extract_list(data):
            try:
                item = self._item_video(raw)
                if item:
                    result['list'].append(item)
            except Exception:
                continue
        if data.get('hasNext'):
            result['pagecount'] = page + 1
        result['total'] = int(data.get('total') or len(result['list']))
        return result

    def detailContent(self, ids):
        try:
            vid = str(ids[0] if isinstance(ids, list) else ids)
            p = vid.split('@@')
            prefix = p[0]
            real = p[1] if len(p) > 1 else vid
            name = unquote(p[2]) if len(p) > 2 else ''
            pic_raw = unquote(p[3]) if len(p) > 3 else ''

            if prefix == 'live':
                url = unquote(p[4]) if len(p) > 4 else ''
                return {'list': [{
                    'vod_id': vid, 'vod_name': name or '直播间', 'vod_pic': pic_raw,
                    'type_name': '直播', 'vod_content': '直播流实时更新', 'vod_remarks': '直播中',
                    'vod_play_from': '直播', 'vod_play_url': f'立即播放$live_play@@{quote(url)}',
                }]}

            if prefix in ('video', 'post', 'pic'):
                source = ''
                news = 'SP'
                if prefix == 'video':
                    source = unquote(p[2]) if len(p) > 2 else ''
                    name = unquote(p[3]) if len(p) > 3 else name
                    pic_raw = unquote(p[4]) if len(p) > 4 else pic_raw
                    news = p[5] if len(p) > 5 else 'SP'
                elif prefix == 'post':
                    name = unquote(p[2]) if len(p) > 2 else name
                    pic_raw = unquote(p[3]) if len(p) > 3 else pic_raw
                    source = unquote(p[4]) if len(p) > 4 else ''
                    news = p[5] if len(p) > 5 else 'SP'
                info = self._req('GET', '/vid/info', params={'videoID': real}) or {}
                content = ''
                sc = []
                if isinstance(info, dict) and info:
                    name = info.get('title') or name
                    pic_raw = info.get('cover') or info.get('verticalCover') or pic_raw
                    source = info.get('sourceURL') or info.get('previewURL') or source
                    content = str(info.get('content') or info.get('summary') or '')
                    news = info.get('newsType') or news
                    sc = info.get('seriesCover') or []
                    publisher = info.get('publisher') if isinstance(info.get('publisher'), dict) else {}
                    tags = info.get('tags') if isinstance(info.get('tags'), list) else []
                    type_id = str(info.get('videoTypeId') or '')
                    type_name = str(info.get('videoTypeName') or '')
                else:
                    publisher, tags, type_id, type_name = {}, [], '', ''
                if not isinstance(sc, list):
                    sc = []
                if not sc and pic_raw and prefix == 'pic':
                    sc = [pic_raw]
                img_urls = [self._abs(u, 'img') for u in sc if u]
                play_from = []
                play_url = []
                nt = str(news or '').upper()
                if source:
                    play_from.append('直链播放')
                    play_url.append(f"播放$video_play@@{quote(source)}")
                if img_urls:
                    play_from.append('画廊模式')
                    play_url.append('点击浏览$pic_play@@' + '&&'.join(img_urls))
                if not play_from and source:
                    play_from.append('直链播放')
                    play_url.append(f"播放$video_play@@{quote(source)}")
                if not play_from and pic_raw:
                    play_from.append('画廊模式')
                    play_url.append('点击浏览$pic_play@@' + self._abs(pic_raw, 'img'))
                remark_bits = []
                if source and '直链播放' in play_from:
                    remark_bits.append('视频')
                if img_urls:
                    remark_bits.append(f"{len(img_urls)}图")
                vod_content = content.strip() if content else ''
                if not vod_content:
                    if img_urls and '直链播放' in play_from:
                        vod_content = f'本帖含视频与{len(img_urls)}张配图'
                    elif img_urls:
                        vod_content = f'共{len(img_urls)}张图片，点击浏览。'
                    else:
                        vod_content = '点击播放'
                tag_links = []
                for tag in tags:
                    if not isinstance(tag, dict):
                        continue
                    link = self._rich(tag.get('name'), 'tag:' + str(tag.get('id') or ''))
                    if link:
                        tag_links.append(link)
                type_link = self._rich(type_name, 'type:' + type_id) if type_id else ''
                extra = []
                if type_link:
                    extra.append('类型：' + type_link)
                if tag_links:
                    extra.append('标签：' + ' '.join(tag_links))
                if extra:
                    vod_content = (vod_content + '\n' + '\n'.join(extra)).strip()
                publisher_name = str(publisher.get('name') or '')
                return {'list': [{
                    'vod_id': vid,
                    'vod_name': name or ('图集' if prefix == 'pic' else '社区帖'),
                    'vod_pic': self._img(pic_raw),
                    'type_name': '社区' if prefix == 'post' else ('图片' if prefix == 'pic' else '视频'),
                    'vod_actor': publisher_name,
                    'vod_content': vod_content,
                    'vod_remarks': '+'.join(remark_bits) if remark_bits else str(news),
                    'vod_play_from': '$$$'.join(play_from),
                    'vod_play_url': '$$$'.join(play_url),
                }]}

            if prefix in ('comic', 'novel', 'anime'):
                info = self._req('GET', '/media/info', params={'id': real}) or {}
                if isinstance(info, dict):
                    name = info.get('title') or name
                    pic_raw = info.get('verticalCover') or info.get('horizontalCover') or pic_raw
                    content = info.get('summary') or ''
                    total = int(info.get('totalEpisode') or 0)
                    mt = str(info.get('mediaType') or ('image' if prefix == 'comic' else ('video' if prefix == 'anime' else 'text'))).lower()
                    sub = int(info.get('mediaSubType') or 0)
                else:
                    content, total, mt, sub = '', 0, ('video' if prefix == 'anime' else 'text'), 0

                chapters = []
                page = 1
                while page <= 30:
                    data = self._req('GET', '/media_content/list', params={
                        'mediaId': real, 'pageNumber': page, 'pageSize': 50
                    }) or {}
                    arr = data.get('list') or []
                    if not arr:
                        break
                    chapters.extend(arr)
                    if not data.get('hasNext'):
                        break
                    page += 1

                urls = []
                for c in chapters:
                    try:
                        cid = str(c.get('id') or '')
                        if not cid:
                            continue
                        ep = c.get('episodeNumber') or len(urls) + 1
                        cname = str(c.get('name') or f'第{ep}话')
                        video_url = str(c.get('videoUrl') or '')
                        if prefix == 'anime' or mt == 'video':
                            if video_url:
                                urls.append(f"{cname}$video_play@@{quote(video_url)}")
                        elif prefix == 'comic' or mt == 'image':
                            urls.append(f"{cname}$comic_chapter_{cid}")
                        else:
                            urls.append(f"{cname}$novel_chapter_{cid}")
                    except Exception:
                        continue
                if not urls and prefix == 'novel':
                    urls = [f"正文$novel_chapter_none_{real}"]

                if prefix == 'anime' or mt == 'video':
                    play_from, label, unit = '动漫播放', '动漫', '集'
                elif prefix == 'comic' or mt == 'image':
                    play_from, label, unit = '画册阅读', '漫画', '话'
                else:
                    play_from, label, unit = ('有声阅读' if sub == 1 else '小说阅读'), '小说', ('集' if sub == 1 else '章')
                return {'list': [{
                    'vod_id': vid,
                    'vod_name': name or label,
                    'vod_pic': self._img(pic_raw),
                    'type_name': label,
                    'vod_content': content or (f'共{total or len(urls)}{unit}' if total or urls else ''),
                    'vod_remarks': f"{len(urls)}{unit}",
                    'vod_play_from': play_from,
                    'vod_play_url': '#'.join(urls)
                }]}

            return {'list': []}
        except Exception:
            return {'list': []}
    def searchContent(self, key, quick, pg='1'):
        page = max(1, int(pg or 1))
        result = {'list': [], 'page': page}
        word = str(key or '').strip()
        if not word or not self._ensure_login():
            return result
        common = {'pageNumber': page, 'pageSize': 15}
        tasks = [
            ('视频', 'video', 'POST', '/search/list', None, dict(common, keyWords=[word], realm='SP', sortType=1)),
            ('抖音', 'video', 'POST', '/search/list', None, dict(common, keyWords=[word], realm='SHORT', sortType=1)),
            ('帖子', 'community', 'POST', '/search/list', None, dict(common, keyWords=[word], realm='COVER', sortType=1)),
            ('图集', 'community', 'POST', '/search/list', None, dict(common, keyWords=[word], realm='PIC', sortType=1)),
            ('动漫', 'media', 'GET', '/media/search', dict(common, keyword=word, kind='1'), None),
            ('图片', 'media', 'GET', '/media/search', dict(common, keyword=word, kind='2'), None),
            ('小说', 'media', 'GET', '/media/search', dict(common, keyword=word, kind='3'), None),
        ]
        def fetch_task(task):
            _, _, method, path, params, data = task
            try:
                return self._req(method, path, params=params, data=data) or {}
            except Exception:
                return {}

        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(fetch_task, tasks))
        seen = set()
        for task, response in zip(tasks, responses):
            mark, item_type = task[0], task[1]
            for raw in self._extract_list(response):
                try:
                    if item_type == 'community':
                        item = self._item_community(raw)
                    elif item_type == 'media':
                        item = self._item_media(raw)
                    else:
                        item = self._item_video(raw)
                    vod_id = str((item or {}).get('vod_id') or '')
                    if not vod_id or vod_id in seen:
                        continue
                    remark = str(item.get('vod_remarks') or '')
                    item['vod_remarks'] = mark + (' · ' + remark if remark else '')
                    seen.add(vod_id)
                    result['list'].append(item)
                except Exception:
                    continue
        return result


    def recommendContent(self, ids, pg):
        current = str(ids[0]) if ids else ''
        page = max(1, int(pg or 1))
        parts = current.split('@@')
        prefix = parts[0] if parts else ''
        real = parts[1] if len(parts) > 1 else current
        try:
            if prefix in ('comic', 'novel', 'anime'):
                data = self._req('GET', '/media/recommend', params={
                    'mediaId': real, 'pageNumber': page, 'pageSize': 15
                }) or {}
                formatter = self._item_media
            elif prefix in ('video', 'post', 'pic'):
                news_type = parts[5] if len(parts) > 5 else 'SP'
                data = self._req('GET', '/vid/recommend/list', params={
                    'videoID': real, 'pageNumber': page, 'pageSize': 15,
                    'newsType': news_type or 'SP'
                }) or {}
                formatter = self._item_video
            else:
                return {'list': []}
            out, seen = [], set()
            for raw in self._extract_list(data):
                try:
                    if prefix in ('comic', 'novel', 'anime'):
                        raw_name = str(raw.get('title') or raw.get('name') or '').strip()
                        raw_pic = str(raw.get('verticalCover') or raw.get('horizontalCover') or raw.get('cover') or '').strip()
                        raw_type = str(raw.get('mediaType') or '').strip().lower()
                        if not raw_name or not raw_pic or raw_name in ('i119', '未命名') or raw_type not in ('image', 'video', 'audio', 'text'):
                            continue
                    item = formatter(raw)
                    item_id = str((item or {}).get('vod_id') or '')
                    item_name = str((item or {}).get('vod_name') or '').strip()
                    if item and item_id and item_name and item_id != current and item_id not in seen:
                        seen.add(item_id)
                        out.append(item)
                except Exception:
                    continue
            return {'list': out}
        except Exception:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        try:
            sid = str(id or '')
            if sid.startswith('pic_play@@'):
                urls = sid.replace('pic_play@@', '', 1).split('&&')
                pics = [self._proxy(u) for u in urls if u]
                return {'parse': 0, 'url': 'pics://' + '&&'.join(pics), 'header': self._play_header()}

            if sid.startswith('live_play@@'):
                url = unquote(sid.split('@@', 1)[1])
                return {'parse': 0, 'url': url, 'header': {'User-Agent': 'Mozilla/5.0'}}

            if sid.startswith('video_play@@'):
                source = unquote(sid.split('@@', 1)[1])
                play = self._m3u8_play_url(source)
                return {'parse': 0, 'url': play, 'header': self._video_header()}

            if sid.startswith('comic_chapter_'):
                cid = sid.replace('comic_chapter_', '', 1)
                info = self._req('GET', '/media_content/info', params={'id': cid}) or {}
                urls = info.get('urlSet') or []
                if not urls and info.get('cover'):
                    urls = [info.get('cover')]
                pics = [self._proxy(self._abs(u, 'img')) for u in urls if u]
                return {'parse': 0, 'url': 'pics://' + '&&'.join(pics), 'header': self._play_header()}

            if sid.startswith('novel_chapter_'):
                cid = sid.replace('novel_chapter_', '', 1)
                if cid.startswith('none_'):
                    return {'parse': 0, 'url': 'novel://' + json.dumps({'title': '正文', 'content': '暂无章节'}, ensure_ascii=False), 'header': ''}
                info = self._req('GET', '/media_content/info', params={'id': cid}) or {}
                title = str(info.get('name') or '正文')
                text = str(info.get('text') or '').strip()
                audio = str(info.get('audioUrl') or '')
                video = str(info.get('videoUrl') or '')
                if text:
                    text = text.replace('<br>', '\n').replace('<br/>', '\n').replace('</br>', '\n')
                    return {'parse': 0, 'url': 'novel://' + json.dumps({'title': title, 'content': text}, ensure_ascii=False), 'header': ''}
                if audio:
                    return {'parse': 0, 'url': self._abs(audio, 'audio'), 'header': self._play_header()}
                if video:
                    return {'parse': 0, 'url': self._m3u8_play_url(video), 'header': self._video_header()}
                return {'parse': 0, 'url': 'novel://' + json.dumps({'title': title, 'content': '正文加载失败'}, ensure_ascii=False), 'header': ''}

            return {'parse': 0, 'url': unquote(sid), 'header': self._play_header()}
        except Exception as e:
            return {'parse': 0, 'url': '', 'header': '', 'message': str(e)}

    def localProxy(self, param):
        url = unquote(param.get('url') or '')
        if not url:
            return [404, 'text/plain', b'']
        try:
            self._runtime()
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
                'Referer': self.site_referer,
            }
            r = self.session.get(url, headers=headers, timeout=20, verify=False)
            content = r.content or b''
            if not content:
                return [404, 'text/plain', b'']
            if not content.startswith((b'\xff\xd8', b'\x89PNG', b'GIF8', b'BM', b'RIFF')):
                out = bytearray(content)
                for i in range(min(100, len(out))):
                    out[i] ^= self.xor_key[i % len(self.xor_key)]
                content = bytes(out)
            if content.startswith(b'\x89PNG'):
                mime = 'image/png'
            elif content.startswith(b'GIF8'):
                mime = 'image/gif'
            elif content[:4] == b'RIFF' and b'WEBP' in content[:16]:
                mime = 'image/webp'
            else:
                mime = 'image/jpeg'
            return [200, mime, content]
        except Exception:
            return [404, 'text/plain', b'']

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(?:m3u8|mp4|flv)(?:$|[?#])', str(url or ''), re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass