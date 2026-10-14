# coding=utf-8
# 完整内置筛选版：不依赖外置 JSON；动态版保留为 91国产集合.py
import base64
import hashlib
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, unquote

import urllib3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from requests import Session

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append('..')
from base.spider import Spider as BaseSpider



# 完整内置分类筛选：由真实 /modules/list、section、tag 接口核验后固化。
# 运行时不读取外置 JSON；旧动态版仍可独立维护并导出筛选快照。
BUILTIN_CLASSES = [{'type_name': '🎬 视频大区', 'type_id': 'video_all'},
 {'type_name': '📸 图片大区', 'type_id': 'pic_all'},
 {'type_name': '📚 漫画大区', 'type_id': 'comic_all'},
 {'type_name': '📖 小说大区', 'type_id': 'novel_all'},
 {'type_name': '📱 短视频大区', 'type_id': 'tik_all'},
 {'type_name': '💬 社区大区', 'type_id': 'community_all'},
 {'type_name': '🕶 深网大区', 'type_id': 'deep_all'},
 {'type_name': '🔥 热搜视频', 'type_id': 'hot_all'}]

BUILTIN_FILTERS = {'video_all': [{'key': 'cate_id',
                'name': '推荐',
                'value': [{'n': '全部', 'v': 'mod:650c14aac8adc51465ea1b26'},
                          {'n': '精选乱伦', 'v': 'msec:666185ba27e094952c941d10'},
                          {'n': '蜜桃巨臀', 'v': 'msec:672f33a07bc3b471ac059eb2'},
                          {'n': '按摩会所', 'v': 'msec:650c6565171265a04a6783ab'},
                          {'n': '媚黑爆操', 'v': 'msec:650c5cf1171265a04a67835d'},
                          {'n': '勾引搭讪', 'v': 'msec:650c6557171265a04a6783a8'},
                          {'n': '黑料吃瓜', 'v': 'msec:650c5c52171265a04a678345'},
                          {'n': '颜值美女', 'v': 'msec:650c64e6171265a04a67838d'},
                          {'n': '极品学妹', 'v': 'msec:650c653c171265a04a6783a2'},
                          {'n': '暗网禁区', 'v': 'msec:650c5c33171265a04a67833f'},
                          {'n': '群P激战', 'v': 'msec:650c5c47171265a04a678342'},
                          {'n': '熟女少妇', 'v': 'msec:650c6571171265a04a6783ae'},
                          {'n': '成人综艺', 'v': 'msec:650c5c62171265a04a678348'},
                          {'n': '性奴母犬', 'v': 'msec:668d3fdcc04ac15dc6c9a71b'},
                          {'n': '绿帽淫妻', 'v': 'msec:672f337a7bc3b471ac059eaf'},
                          {'n': '迷奸强奸', 'v': 'msec:650c3b7ec8adc51465ea1b6c'},
                          {'n': '学生破处', 'v': 'msec:69212398ae19d959bfd54390'}]},
               {'key': 'cate_id',
                'name': '18岁',
                'value': [{'n': '全部', 'v': 'mod:672f31587bc3b471ac059d7a'},
                          {'n': '少女', 'v': 'msec:672f325e7bc3b471ac059d9f'},
                          {'n': '嫩萝', 'v': 'msec:68f06ee8c76b7d560aea9135'},
                          {'n': '精选', 'v': 'msec:69212d55ae19d959bfd5443c'},
                          {'n': '原创', 'v': 'msec:69429d0dae19d959bfd5b8ac'},
                          {'n': '国色', 'v': 'msec:6a2fd7aaa36ba0e6fa99461c'}]},
               {'key': 'cate_id',
                'name': '国产',
                'value': [{'n': '全部', 'v': 'mod:650c1527c8adc51465ea1b45'},
                          {'n': '国产自拍', 'v': 'msec:650c64fb171265a04a678393'},
                          {'n': '街射偷拍', 'v': 'msec:650c6532171265a04a67839f'},
                          {'n': '捉奸霸凌', 'v': 'msec:650c3b1ac8adc51465ea1b66'},
                          {'n': '偷情换妻', 'v': 'msec:650c5ce4171265a04a67835a'},
                          {'n': '自慰喷水', 'v': 'msec:650c6506171265a04a678396'},
                          {'n': '精品探花', 'v': 'msec:650c64f0171265a04a678390'},
                          {'n': '网红主播', 'v': 'msec:650c64d7171265a04a67838a'},
                          {'n': '野战车震', 'v': 'msec:650c5c74171265a04a67834b'},
                          {'n': '百合女同', 'v': 'msec:650c6513171265a04a678399'},
                          {'n': '直播大秀', 'v': 'msec:650c6546171265a04a6783a5'},
                          {'n': '摄像破解', 'v': 'msec:650c5c21171265a04a67833c'},
                          {'n': 'SM调教', 'v': 'msec:650c5cb1171265a04a678354'},
                          {'n': '明星淫梦', 'v': 'msec:650c5c81171265a04a67834e'},
                          {'n': '孕妇哺乳', 'v': 'msec:66d0650d2a51a6d65b56c005'},
                          {'n': '人妖男同', 'v': 'msec:650c5cd6171265a04a678357'},
                          {'n': '户外露出', 'v': 'msec:650c6589171265a04a6783b4'}]},
               {'key': 'cate_id',
                'name': '乱伦',
                'value': [{'n': '全部', 'v': 'mod:650c14bfc8adc51465ea1b2c'},
                          {'n': '母子', 'v': 'msec:650c641c171265a04a678365'},
                          {'n': '父女', 'v': 'msec:650c642d171265a04a678368'},
                          {'n': '姐弟', 'v': 'msec:650c644b171265a04a678371'},
                          {'n': '兄妹', 'v': 'msec:650c6438171265a04a67836b'},
                          {'n': '嫂子', 'v': 'msec:650c6461171265a04a678377'},
                          {'n': '岳母', 'v': 'msec:650c6478171265a04a67837d'},
                          {'n': '全家乱P', 'v': 'msec:650c649c171265a04a678386'},
                          {'n': '儿媳', 'v': 'msec:650c6455171265a04a678374'},
                          {'n': '师生', 'v': 'msec:650c648f171265a04a678383'},
                          {'n': '小姨子', 'v': 'msec:650c6442171265a04a67836e'},
                          {'n': '舅侄', 'v': 'msec:650c646e171265a04a67837a'}]},
               {'key': 'cate_id',
                'name': '日韩',
                'value': [{'n': '全部', 'v': 'mod:650c14e4c8adc51465ea1b36'},
                          {'n': '中文字幕', 'v': 'msec:650c67c5171265a04a6783fb'},
                          {'n': '精选无码', 'v': 'msec:650c675d171265a04a6783f1'},
                          {'n': '欧美剧情', 'v': 'msec:650c689b171265a04a678425'},
                          {'n': '家庭乱伦', 'v': 'msec:650c6807171265a04a67840a'},
                          {'n': '无码FC2', 'v': 'msec:650c674f171265a04a6783ee'},
                          {'n': '巨根黑人', 'v': 'msec:650c6859171265a04a678419'},
                          {'n': '上司侵犯', 'v': 'msec:650c6834171265a04a678413'},
                          {'n': '多P群交', 'v': 'msec:650c67d2171265a04a6783fe'},
                          {'n': '电车痴汉', 'v': 'msec:650c67ed171265a04a678404'},
                          {'n': '时间静止', 'v': 'msec:650c6827171265a04a678410'},
                          {'n': '日韩三级', 'v': 'msec:650c6869171265a04a67841c'},
                          {'n': '素人约拍', 'v': 'msec:650c673d171265a04a6783eb'},
                          {'n': '人妻NTR', 'v': 'msec:650c684a171265a04a678416'},
                          {'n': '紧缚捆绑', 'v': 'msec:68f9da57ae19d959bfd4b5c9'},
                          {'n': '性感美臀', 'v': 'msec:68f9da64ae19d959bfd4b5cc'},
                          {'n': '巨乳系列', 'v': 'msec:68f9da6aae19d959bfd4b5cf'},
                          {'n': '水果懂片', 'v': 'msec:68f9da78ae19d959bfd4b5d2'},
                          {'n': '欧美搭讪', 'v': 'msec:68f9db56ae19d959bfd4b5da'},
                          {'n': 'COS大作', 'v': 'msec:68f9dad1ae19d959bfd4b5d6'},
                          {'n': '有栖花绯', 'v': 'msec:68f9dbe5ae19d959bfd4b5dd'},
                          {'n': '深田咏美', 'v': 'msec:68f9dbf5ae19d959bfd4b5e0'},
                          {'n': '波多野结Y', 'v': 'msec:68f9dbffae19d959bfd4b5e3'},
                          {'n': '松本一香', 'v': 'msec:68f9dc20ae19d959bfd4b5e6'},
                          {'n': '桃乃木香N', 'v': 'msec:68f9dc52ae19d959bfd4b5e9'},
                          {'n': '小宵虎南', 'v': 'msec:68f9dc7bae19d959bfd4b5ec'},
                          {'n': '桥本有菜', 'v': 'msec:68f9dc83ae19d959bfd4b5ef'},
                          {'n': '枫可怜', 'v': 'msec:68f9e807ae19d959bfd4b5f8'},
                          {'n': '河北彩花', 'v': 'msec:68f9e811ae19d959bfd4b5fb'},
                          {'n': '明里紬', 'v': 'msec:68f9e83eae19d959bfd4b5fe'},
                          {'n': '樱空桃', 'v': 'msec:68f9e85dae19d959bfd4b601'},
                          {'n': '美乃雀', 'v': 'msec:68f9e875ae19d959bfd4b604'},
                          {'n': '森泽佳奈', 'v': 'msec:68f9e890ae19d959bfd4b607'},
                          {'n': '白桃花', 'v': 'msec:68f9e8a3ae19d959bfd4b60a'},
                          {'n': '森日向子', 'v': 'msec:68f9e8edae19d959bfd4b610'},
                          {'n': '星宫一花', 'v': 'msec:68f9e905ae19d959bfd4b613'},
                          {'n': '安斋拉拉', 'v': 'msec:68f9e92aae19d959bfd4b616'},
                          {'n': '吉高宁宁', 'v': 'msec:68f9e94aae19d959bfd4b619'},
                          {'n': '小花暖', 'v': 'msec:68f9e961ae19d959bfd4b61c'},
                          {'n': '天使萌', 'v': 'msec:68f9e974ae19d959bfd4b61f'},
                          {'n': '希岛爱理', 'v': 'msec:68f9e98dae19d959bfd4b622'},
                          {'n': '葵司', 'v': 'msec:68f9e9a6ae19d959bfd4b625'},
                          {'n': '相泽南', 'v': 'msec:68f9ea01ae19d959bfd4b628'},
                          {'n': '沙月惠奈', 'v': 'msec:68f9ea1bae19d959bfd4b62b'},
                          {'n': '鹫尾芽衣', 'v': 'msec:68f9ea52ae19d959bfd4b62e'},
                          {'n': '田中宁宁', 'v': 'msec:68f9ea6dae19d959bfd4b631'},
                          {'n': '沙月芽衣', 'v': 'msec:68f9ea8aae19d959bfd4b634'},
                          {'n': '七泽美亚', 'v': 'msec:68f9eaa7ae19d959bfd4b637'},
                          {'n': '山岸逢花', 'v': 'msec:68f9eab1ae19d959bfd4b63a'},
                          {'n': '美谷朱里', 'v': 'msec:68f9eac6ae19d959bfd4b63d'},
                          {'n': '北野未奈', 'v': 'msec:68fb9a2fae19d959bfd4d2b5'},
                          {'n': '美园和花', 'v': 'msec:68fc3988ae19d959bfd4d4a5'},
                          {'n': '木下日葵', 'v': 'msec:68fc3a8bae19d959bfd4d4b5'}]},
               {'key': 'cate_id',
                'name': '厂牌',
                'value': [{'n': '全部', 'v': 'mod:650c14d2c8adc51465ea1b31'},
                          {'n': '麻豆传媒', 'v': 'msec:650c65cf171265a04a6783bb'},
                          {'n': '蜜桃传媒', 'v': 'msec:650c6615171265a04a6783ca'},
                          {'n': '91制片厂', 'v': 'msec:650c65dc171265a04a6783be'},
                          {'n': '星空无限', 'v': 'msec:650c6692171265a04a6783e2'},
                          {'n': '糖心Vlog', 'v': 'msec:650c66a2171265a04a6783e5'},
                          {'n': '天美传媒', 'v': 'msec:650c660a171265a04a6783c7'},
                          {'n': '精东影业', 'v': 'msec:650c65fc171265a04a6783c4'},
                          {'n': '性世界', 'v': 'msec:650c6686171265a04a6783df'},
                          {'n': '兔子先生', 'v': 'msec:650c6663171265a04a6783d9'},
                          {'n': '扣扣传媒', 'v': 'msec:650c66af171265a04a6783e8'},
                          {'n': '果冻传媒', 'v': 'msec:650c65e8171265a04a6783c1'},
                          {'n': '台湾JVID', 'v': 'msec:650c663f171265a04a6783d3'},
                          {'n': 'SA国际传媒', 'v': 'msec:650c6674171265a04a6783dc'},
                          {'n': 'SWAG', 'v': 'msec:650c6651171265a04a6783d6'},
                          {'n': '爱豆传媒', 'v': 'msec:693949a6ae19d959bfd59a25'},
                          {'n': '色控', 'v': 'msec:693949adae19d959bfd59a28'},
                          {'n': '皇家华人', 'v': 'msec:650c6620171265a04a6783cd'},
                          {'n': '黑料社', 'v': 'msec:650c662b171265a04a6783d0'},
                          {'n': '大象传媒', 'v': 'msec:6657fa0027e094952c93ab8e'},
                          {'n': '同城约炮', 'v': 'msec:689c9b72ce00c2d11f94d9b7'}]},
               {'key': 'cate_id',
                'name': '萝莉',
                'value': [{'n': '全部', 'v': 'mod:672f318e7bc3b471ac059d81'},
                          {'n': 'JK', 'v': 'msec:672f33f87bc3b471ac059eb9'},
                          {'n': 'Cosplay', 'v': 'msec:672f340b7bc3b471ac059ebc'},
                          {'n': '女仆', 'v': 'msec:672f34177bc3b471ac059ebf'},
                          {'n': '丝袜', 'v': 'msec:672f34237bc3b471ac059ec2'},
                          {'n': '自慰', 'v': 'msec:672f343a7bc3b471ac059ec8'},
                          {'n': '学生', 'v': 'msec:672f342e7bc3b471ac059ec5'},
                          {'n': '潮喷', 'v': 'msec:672f344a7bc3b471ac059ecb'},
                          {'n': '巨乳', 'v': 'msec:672f346e7bc3b471ac059ed2'},
                          {'n': '白虎', 'v': 'msec:672f347b7bc3b471ac059ed5'},
                          {'n': '足交', 'v': 'msec:672f34897bc3b471ac059ed8'},
                          {'n': '内射', 'v': 'msec:672f34957bc3b471ac059edb'}]},
               {'key': 'cate_id',
                'name': '网黄',
                'value': [{'n': '全部', 'v': 'mod:650c1513c8adc51465ea1b40'},
                          {'n': '唐伯虎', 'v': 'msec:650e91c4cf6cf7ee4838a1cb'},
                          {'n': '饼干姐姐', 'v': 'msec:67dceaafe49a8e8519c61aaa'},
                          {'n': '玩偶姐姐', 'v': 'msec:650e6d06cf6cf7ee48389f6b'},
                          {'n': '台北娜娜', 'v': 'msec:650e91a8cf6cf7ee4838a1c8'},
                          {'n': '桥本香菜', 'v': 'msec:67dceae1e49a8e8519c61aaf'},
                          {'n': '辛尤里', 'v': 'msec:650e9192cf6cf7ee4838a1c5'},
                          {'n': '小欣奈', 'v': 'msec:67dceb01e49a8e8519c61ab2'},
                          {'n': 'Cola酱', 'v': 'msec:650e90bacf6cf7ee4838a185'},
                          {'n': '御梦子', 'v': 'msec:67dceb11e49a8e8519c61ab5'},
                          {'n': '柚子猫', 'v': 'msec:650e90ddcf6cf7ee4838a1a0'},
                          {'n': '捅主任', 'v': 'msec:67dceb24e49a8e8519c61ab8'},
                          {'n': '樱花小猫', 'v': 'msec:650e9121cf6cf7ee4838a1ae'},
                          {'n': '水冰月', 'v': 'msec:67dcebc9e49a8e8519c61ac7'},
                          {'n': '黑椒盖饭', 'v': 'msec:67dcebede49a8e8519c61aca'},
                          {'n': '刘玥', 'v': 'msec:650e9169cf6cf7ee4838a1ba'},
                          {'n': '冉冉学姐', 'v': 'msec:67dcec09e49a8e8519c61acd'},
                          {'n': '粉色情人', 'v': 'msec:67dd15cfe49a8e8519c61dac'},
                          {'n': '鸡教练', 'v': 'msec:67dd17c0e49a8e8519c61e24'},
                          {'n': '小二先生', 'v': 'msec:67dd2abfe49a8e8519c61ec0'},
                          {'n': '荔枝', 'v': 'msec:67dd2c98e49a8e8519c61f4b'},
                          {'n': '多乙', 'v': 'msec:67dd2d17e49a8e8519c61f7d'},
                          {'n': '小敏儿', 'v': 'msec:67dd2e21e49a8e8519c61fec'},
                          {'n': 'Make', 'v': 'msec:67dd3144e49a8e8519c62072'},
                          {'n': '麻豆苏畅', 'v': 'msec:67dd33ffe49a8e8519c620e1'},
                          {'n': '兔子米菲', 'v': 'msec:67dd36d2e49a8e8519c62131'},
                          {'n': 'Vivian姐', 'v': 'msec:650e931ecf6cf7ee4838a21e'},
                          {'n': '台湾粉红兔', 'v': 'msec:651190c4fb7502f9732f45ba'},
                          {'n': '推特欧尼', 'v': 'msec:651190d4fb7502f9732f45be'},
                          {'n': 'Naomiii', 'v': 'msec:67de8604e49a8e8519c62720'},
                          {'n': '地雷系', 'v': 'msec:650e92facf6cf7ee4838a212'},
                          {'n': '棒棒糖', 'v': 'msec:650e913bcf6cf7ee4838a1b4'},
                          {'n': '仙仙桃', 'v': 'msec:650e9153cf6cf7ee4838a1b7'}]},
               {'key': 'cate_id',
                'name': '福利姬',
                'value': [{'n': '全部', 'v': 'mod:67d03d5d3d2a955efcc8eb52'},
                          {'n': '情深叉喔', 'v': 'msec:67d03eff3d2a955efcc8eb6c'},
                          {'n': '桃桃酱', 'v': 'msec:67d03f173d2a955efcc8eb70'},
                          {'n': '私人玩物', 'v': 'msec:67d03f293d2a955efcc8eb73'},
                          {'n': '米娜学姐', 'v': 'msec:67d03f353d2a955efcc8eb76'},
                          {'n': '娜美', 'v': 'msec:67d03f423d2a955efcc8eb79'},
                          {'n': '香草少女', 'v': 'msec:67d03f4c3d2a955efcc8eb7c'},
                          {'n': '八月', 'v': 'msec:67d03f533d2a955efcc8eb7f'},
                          {'n': '白袜袜', 'v': 'msec:67d03f5f3d2a955efcc8eb82'},
                          {'n': '萌白酱', 'v': 'msec:67d03f6d3d2a955efcc8eb88'},
                          {'n': '酥酥', 'v': 'msec:67d03f753d2a955efcc8eb8b'},
                          {'n': '小鸟酱', 'v': 'msec:67d03f843d2a955efcc8eb8e'},
                          {'n': '不见星空', 'v': 'msec:67d03f8c3d2a955efcc8eb91'},
                          {'n': '优米酱', 'v': 'msec:67d03f953d2a955efcc8eb94'},
                          {'n': '鸡蛋饼', 'v': 'msec:67d03f9e3d2a955efcc8eb97'},
                          {'n': '米胡桃', 'v': 'msec:67d03fa63d2a955efcc8eb9a'},
                          {'n': '推特B神', 'v': 'msec:67d03fb23d2a955efcc8eb9d'},
                          {'n': 'OKIA（日）', 'v': 'msec:67d03fc63d2a955efcc8eba0'},
                          {'n': '芋喵喵', 'v': 'msec:67d03fd23d2a955efcc8eba3'},
                          {'n': '锅锅酱', 'v': 'msec:67d044833d2a955efcc8eba8'},
                          {'n': '唐可可', 'v': 'msec:67d044993d2a955efcc8ebae'},
                          {'n': '小晗wink', 'v': 'msec:67d044a73d2a955efcc8ebb1'},
                          {'n': '铃木君', 'v': 'msec:67d044af3d2a955efcc8ebb4'},
                          {'n': '猫宝宝', 'v': 'msec:67d044b73d2a955efcc8ebb7'},
                          {'n': '绯红小猫', 'v': 'msec:67d044bf3d2a955efcc8ebba'},
                          {'n': '司雨', 'v': 'msec:67d044c63d2a955efcc8ebbd'},
                          {'n': '菜头喵喵', 'v': 'msec:67d044cf3d2a955efcc8ebc0'},
                          {'n': '懒懒睡不醒', 'v': 'msec:67d044d93d2a955efcc8ebc3'},
                          {'n': '安安老师', 'v': 'msec:67d044e13d2a955efcc8ebc6'},
                          {'n': '喵小吉', 'v': 'msec:67d044e93d2a955efcc8ebc9'},
                          {'n': '小晚酱', 'v': 'msec:67d044f63d2a955efcc8ebcc'},
                          {'n': '白桃少女', 'v': 'msec:67d045003d2a955efcc8ebcf'}]},
               {'key': 'cate_id',
                'name': 'P站',
                'value': [{'n': '全部', 'v': 'mod:6745d862f8efcbeaf1f3d0da'},
                          {'n': 'Candy Love', 'v': 'msec:67dc2108ea6685cca4a68da8'},
                          {'n': 'SweetieFox', 'v': 'msec:67d048503d2a955efcc8ebe1'},
                          {'n': 'Eva Elfie', 'v': 'msec:67d0487b3d2a955efcc8ebeb'},
                          {'n': 'Riley Reid', 'v': 'msec:67d048853d2a955efcc8ebee'},
                          {'n': 'Reislin', 'v': 'msec:67d048943d2a955efcc8ebf1'},
                          {'n': 'Purple Bitch', 'v': 'msec:67d0489f3d2a955efcc8ebf4'},
                          {'n': 'Sia Siberia', 'v': 'msec:67d048ab3d2a955efcc8ebf7'},
                          {'n': 'NicoLove', 'v': 'msec:65119072fb7502f9732f45ab'},
                          {'n': 'Leah Meow', 'v': 'msec:67d048b53d2a955efcc8ebfa'},
                          {'n': 'Daisybaby', 'v': 'msec:651190a2fb7502f9732f45b0'},
                          {'n': 'Babeneso', 'v': 'msec:67d048bd3d2a955efcc8ebfd'},
                          {'n': 'Creamy Spot', 'v': 'msec:67d048cf3d2a955efcc8ec00'},
                          {'n': 'Zirael Rem', 'v': 'msec:67d049063d2a955efcc8ec0c'},
                          {'n': 'Pinkloving', 'v': 'msec:67d049103d2a955efcc8ec0f'},
                          {'n': 'Okirakuhuhu', 'v': 'msec:67d0491a3d2a955efcc8ec12'},
                          {'n': 'Yui Peachpie', 'v': 'msec:67d049233d2a955efcc8ec15'},
                          {'n': 'Featured', 'v': 'msec:67d0492d3d2a955efcc8ec18'},
                          {'n': 'Nuomibaby', 'v': 'msec:67d049353d2a955efcc8ec1b'},
                          {'n': 'MollyLittle', 'v': 'msec:67d0493e3d2a955efcc8ec1e'},
                          {'n': 'Lolilipop99', 'v': 'msec:67d049473d2a955efcc8ec21'},
                          {'n': 'solazola', 'v': 'msec:683584768330ab805e6b3186'},
                          {'n': 'StepSiblings', 'v': 'msec:683584bf8330ab805e6b3189'},
                          {'n': 'adriana', 'v': 'msec:6835852d8330ab805e6b318c'},
                          {'n': 'daintyWilder', 'v': 'msec:683585828330ab805e6b318f'}]},
               {'key': 'cate_id',
                'name': '动漫',
                'value': [{'n': '全部', 'v': 'mod:67b82a0b7cc676ac32d998e3'},
                          {'n': '3D动漫', 'v': 'msec:67b82a2d7cc676ac32d99902'},
                          {'n': 'H动漫', 'v': 'msec:67b82a3c7cc676ac32d99912'},
                          {'n': '原神', 'v': 'msec:67b82a457cc676ac32d99920'},
                          {'n': '同人动漫', 'v': 'msec:67b82a4e7cc676ac32d99924'},
                          {'n': '游戏国漫', 'v': 'msec:67b82a757cc676ac32d99942'},
                          {'n': '斗破苍穹', 'v': 'msec:68e9e43a53dec3babf063139'},
                          {'n': '完美世界', 'v': 'msec:68e9e44453dec3babf06313c'},
                          {'n': '新番速递', 'v': 'msec:68e9e45253dec3babf06313f'},
                          {'n': '星穹铁道', 'v': 'msec:68e9e51f53dec3babf063142'},
                          {'n': '守望先锋', 'v': 'msec:68e9e53753dec3babf063145'},
                          {'n': '王者荣耀', 'v': 'msec:67b82a817cc676ac32d99948'},
                          {'n': '崩坏', 'v': 'msec:68e9dd6953dec3babf063107'},
                          {'n': '乱伦精选', 'v': 'msec:68e9ddb653dec3babf06310f'},
                          {'n': '幼齿萝莉', 'v': 'msec:68e9de4253dec3babf063112'},
                          {'n': 'VAM', 'v': 'msec:68e9de4b53dec3babf063115'},
                          {'n': '白虎嫩鲍', 'v': 'msec:68e9de8853dec3babf063118'},
                          {'n': '最终幻想', 'v': 'msec:68e9ded753dec3babf06311b'},
                          {'n': '斗罗大陆', 'v': 'msec:68e9dd7953dec3babf06310a'},
                          {'n': '小马拉车', 'v': 'msec:68e9e2e553dec3babf063125'},
                          {'n': '碧蓝航线', 'v': 'msec:68e9e30653dec3babf063128'},
                          {'n': '无码涩漫', 'v': 'msec:68e9e3f453dec3babf063131'},
                          {'n': '中文剧情', 'v': 'msec:68e9e40153dec3babf063134'},
                          {'n': 'MMD', 'v': 'msec:67b82a947cc676ac32d99954'},
                          {'n': 'motion anime', 'v': 'msec:67b82eed7cc676ac32d99aa1'}]},
               {'key': 'cate_id',
                'name': '其它模块',
                'value': [{'n': '最新', 'v': 'mod:6997d46a84c6be0f8421d0b2'}]},
               {'key': 'cate_id',
                'name': '更多标签',
                'value': [{'n': '全部', 'v': 'tag:5e150e80b9210b10b2052ed7'},
                          {'n': '熟女少妇', 'v': 'tag:5e150e80b9210b10b2052ed7'},
                          {'n': '涩涩美图', 'v': 'tag:66d1c92aee1f33615dbb9bd2'},
                          {'n': '品茶约炮', 'v': 'tag:5dbeb2d6e76468ea20625f2a'},
                          {'n': '萝莉', 'v': 'tag:5dbeb269e76468ea20625ef2'},
                          {'n': '学生', 'v': 'tag:5de2f937cda257823b28453e'},
                          {'n': '国产', 'v': 'tag:5dbeb281e76468ea20625f00'},
                          {'n': '探花', 'v': 'tag:60f9310f797de222083987d5'},
                          {'n': '野战', 'v': 'tag:5dbeb234e76468ea20625ed1'},
                          {'n': '内射', 'v': 'tag:5dbeb248e76468ea20625ee1'},
                          {'n': '嫩模', 'v': 'tag:5dfc95a61bce93a79fdf98bf'},
                          {'n': '少妇', 'v': 'tag:5dbeb23be76468ea20625ed9'},
                          {'n': '制服', 'v': 'tag:5dbeb33ae76468ea20625f67'},
                          {'n': '巨乳', 'v': 'tag:5dbeb239e76468ea20625ed8'},
                          {'n': '自慰', 'v': 'tag:5dbeb22fe76468ea20625ebc'},
                          {'n': '约啪', 'v': 'tag:5dbeb3ace76468ea20625fa5'},
                          {'n': '换妻', 'v': 'tag:5dbec72864447bd682552ffe'},
                          {'n': '露出', 'v': 'tag:5dbeb230e76468ea20625eca'},
                          {'n': '丝袜', 'v': 'tag:5dbeb268e76468ea20625ef0'},
                          {'n': 'cos', 'v': 'tag:5dd7db87e2c6eeb6be6a8aab'},
                          {'n': '美臀', 'v': 'tag:5dbeb39fe76468ea20625f9f'},
                          {'n': '足交', 'v': 'tag:5dbeb231e76468ea20625ecf'},
                          {'n': '主播', 'v': 'tag:5dbeb2dce76468ea20625f2e'},
                          {'n': '虐恋', 'v': 'tag:5e046e657a3aac4e680fe478'},
                          {'n': '多人', 'v': 'tag:5e551cf7d759e5a42e717ebc'},
                          {'n': '猎奇', 'v': 'tag:5dbeb2c4e76468ea20625f20'},
                          {'n': '动漫', 'v': 'tag:5dbeb316e76468ea20625f53'},
                          {'n': '口交', 'v': 'tag:5dbeb42be76468ea20625fbd'},
                          {'n': '口爆', 'v': 'tag:5dbeb404e76468ea20625fb5'},
                          {'n': '欧美', 'v': 'tag:5dde205ca1fffd6b580f51c8'},
                          {'n': '深喉', 'v': 'tag:5dbeb32de76468ea20625f60'}]},
               {'key': 'sort',
                'name': '排序',
                'value': [{'n': '综合', 'v': '1'},
                          {'n': '最新', 'v': '2'},
                          {'n': '最热', 'v': '3'},
                          {'n': '播放', 'v': '4'},
                          {'n': '收藏', 'v': '5'},
                          {'n': '点赞', 'v': '6'},
                          {'n': '评论', 'v': '7'}]}],
 'pic_all': [{'key': 'cate_id',
              'name': '图集分类',
              'value': [{'n': 'Cosplay', 'v': 'mod:65c2e9aa3499fc57e0f1dafd'},
                        {'n': '秀人网', 'v': 'mod:6694ab9ac4f9a85dfc7aadca'},
                        {'n': '尤蜜荟', 'v': 'mod:66950059c4f9a85dfc7ab8d0'},
                        {'n': '花漾', 'v': 'mod:66950f2ac4f9a85dfc7ab920'},
                        {'n': '美媛馆', 'v': 'mod:669511b2c4f9a85dfc7ab978'},
                        {'n': '模范学院', 'v': 'mod:669513aac4f9a85dfc7ab9e6'},
                        {'n': '爱蜜社', 'v': 'mod:66a0c01b4d9cb2dcdfda8f4b'},
                        {'n': '语画界', 'v': 'mod:66a247be4d9cb2dcdfda9d95'},
                        {'n': '嗲囡囡', 'v': 'mod:66a248254d9cb2dcdfda9d9e'},
                        {'n': '魅妍社', 'v': 'mod:66a07fa94d9cb2dcdfda8d39'},
                        {'n': '喵糖映画', 'v': 'mod:6694d1eec4f9a85dfc7aafeb'}]},
             {'key': 'sort',
              'name': '排序',
              'value': [{'n': '综合', 'v': '1'},
                        {'n': '最新', 'v': '2'},
                        {'n': '最热', 'v': '3'},
                        {'n': '播放', 'v': '4'},
                        {'n': '收藏', 'v': '5'},
                        {'n': '点赞', 'v': '6'},
                        {'n': '评论', 'v': '7'}]}],
 'comic_all': [{'key': 'cate_id',
                'name': '漫画',
                'value': [{'n': '全部', 'v': 'mod:67b7f7e5ac310312c98dc12a'},
                          {'n': '全彩涩漫', 'v': 'msec:67b7f890ac310312c98dc153'},
                          {'n': '同人漫画', 'v': 'msec:67b7ff24ac310312c98dc318'},
                          {'n': '3D漫画', 'v': 'msec:67b7ff30ac310312c98dc31b'},
                          {'n': '吸晴韩漫', 'v': 'msec:67b7ff43ac310312c98dc31e'},
                          {'n': '爆射C106', 'v': 'msec:69303159ae19d959bfd574ff'},
                          {'n': '毁童年系列', 'v': 'msec:67b7ff53ac310312c98dc321'},
                          {'n': '童颜萝莉', 'v': 'msec:67b7ff5eac310312c98dc324'},
                          {'n': '丰满尤物', 'v': 'msec:6942a326ae19d959bfd5b95f'},
                          {'n': 'NTR', 'v': 'msec:67b7ff6aac310312c98dc327'},
                          {'n': '原神剧场', 'v': 'msec:69303594ae19d959bfd5772b'},
                          {'n': '七龙珠', 'v': 'msec:69303588ae19d959bfd57728'},
                          {'n': '禁忌乱伦', 'v': 'msec:67b7ff76ac310312c98dc32a'},
                          {'n': '肉便器', 'v': 'msec:69303a6bae19d959bfd577d7'},
                          {'n': 'AI绘图', 'v': 'msec:69313d37ae19d959bfd57bc6'},
                          {'n': '人妻阿姨', 'v': 'msec:69313d42ae19d959bfd57bc9'},
                          {'n': '恋上辣妹', 'v': 'msec:69313d59ae19d959bfd57bcc'},
                          {'n': '强暴轮奸', 'v': 'msec:69313d68ae19d959bfd57bcf'},
                          {'n': '荒淫校园', 'v': 'msec:69313d71ae19d959bfd57bd2'},
                          {'n': '紧致处女', 'v': 'msec:69313d95ae19d959bfd57bd9'},
                          {'n': '泳装特辑', 'v': 'msec:69313dafae19d959bfd57bdd'}]},
               {'key': 'sort',
                'name': '排序',
                'value': [{'n': '综合', 'v': '1'},
                          {'n': '最新', 'v': '2'},
                          {'n': '最热', 'v': '3'},
                          {'n': '播放', 'v': '4'},
                          {'n': '收藏', 'v': '5'},
                          {'n': '点赞', 'v': '6'},
                          {'n': '评论', 'v': '7'}]}],
 'novel_all': [{'key': 'cate_id',
                'name': '淫妻少妇',
                'value': [{'n': '全部', 'v': 'mod:6818bb4c09f06f3a92826386'},
                          {'n': '淫荡少妇', 'v': 'msec:6818bc4309f06f3a928263a8'}]},
               {'key': 'cate_id',
                'name': '其它分类',
                'value': [{'n': '有声小说', 'v': 'mod:680b7e3361ffc2e4224f7b7c'},
                          {'n': '剧情演绎', 'v': 'mod:6818bac609f06f3a9282637f'},
                          {'n': '家庭乱伦', 'v': 'mod:6818ba8e09f06f3a9282636f'},
                          {'n': '都市激情', 'v': 'mod:6818baa509f06f3a92826374'},
                          {'n': '校园春色', 'v': 'mod:6818bbdc09f06f3a92826391'},
                          {'n': '古典武侠', 'v': 'mod:68137637abf672f142d9b740'}]},
               {'key': 'sort',
                'name': '排序',
                'value': [{'n': '综合', 'v': '1'},
                          {'n': '最新', 'v': '2'},
                          {'n': '最热', 'v': '3'},
                          {'n': '播放', 'v': '4'},
                          {'n': '收藏', 'v': '5'},
                          {'n': '点赞', 'v': '6'},
                          {'n': '评论', 'v': '7'}]}],
 'tik_all': [{'key': 'cate_id',
              'name': '分区',
              'value': [{'n': '抖音', 'v': 'mod:68c02b57c23a546a4491056c'},
                        {'n': '直播推荐', 'v': 'live:tj'},
                        {'n': '中国', 'v': 'live:6763e704daf2ddeb39b0ec83'},
                        {'n': '日韩', 'v': 'live:6763e717daf2ddeb39b0ec84'},
                        {'n': '越南', 'v': 'live:6763e750daf2ddeb39b0ec87'},
                        {'n': '乌克兰', 'v': 'live:6763e72bdaf2ddeb39b0ec85'},
                        {'n': '俄罗斯', 'v': 'live:6763e73bdaf2ddeb39b0ec86'},
                        {'n': '欧美', 'v': 'live:6763e768daf2ddeb39b0ec88'},
                        {'n': '男主播', 'v': 'live:6763e7b6daf2ddeb39b0ec8a'}]}],
 'community_all': [{'key': 'cate_id',
                    'name': '热门推荐',
                    'value': [{'n': '全部', 'v': 'mod:650c153ec8adc51465ea1b4a'},
                              {'n': '原创大神', 'v': 'tag:5dbeb22fe76468ea20625ebf'},
                              {'n': '伦理之爱', 'v': 'tag:5dbeb23fe76468ea20625edc'},
                              {'n': '反差母狗', 'v': 'tag:65142906b27d2b6b52999db3'},
                              {'n': '自拍分享', 'v': 'tag:5dbeb22fe76468ea20625ec0'},
                              {'n': '吃瓜黑料', 'v': 'tag:635e9b36d4dd9c00f6040043'},
                              {'n': '萝莉少女', 'v': 'tag:62e39daadab5fbe7af6adb7c'}]},
                   {'key': 'cate_id',
                    'name': '分享交友',
                    'value': [{'n': '全部', 'v': 'mod:650c1555c8adc51465ea1b50'},
                              {'n': '换妻交友', 'v': 'tag:5dbec68964447bd682552fed'},
                              {'n': '同城交友', 'v': 'tag:653cd79255e6c8ab96b6a8ee'},
                              {'n': '绿奴淫妻', 'v': 'tag:5e0606fbcf4864a3bdd3b87d'},
                              {'n': '单男交友', 'v': 'tag:6556202069a93440ed26d5c0'},
                              {'n': '经验交流', 'v': 'tag:5dbeb2c8e76468ea20625f23'},
                              {'n': '同性交友', 'v': 'tag:6571495495ca90d781529627'}]},
                   {'key': 'cate_id',
                    'name': '暗黑探索',
                    'value': [{'n': '全部', 'v': 'mod:650c1579c8adc51465ea1b5a'},
                              {'n': '春药迷奸', 'v': 'tag:634a2a0bd4dd9c00f602ed33'},
                              {'n': '街射抄底', 'v': 'tag:5dbeb2c8e76468ea20625f25'},
                              {'n': '孕妇母乳', 'v': 'tag:5dbeb79be76468ea20626034'},
                              {'n': '捉奸霸凌', 'v': 'tag:6330e8a475e4ba97d39da8b5'},
                              {'n': '奇趣百科', 'v': 'tag:65324bf529a3f62c782d447a'},
                              {'n': '偷拍厕拍', 'v': 'tag:69256e88ae19d959bfd5517e'}]},
                   {'key': 'cate_id',
                    'name': '发现精彩',
                    'value': [{'n': '全部', 'v': 'mod:6617fb57a0a97ae2d34a75c8'},
                              {'n': '成人游戏', 'v': 'tag:6618dd30c94cd8dee90fc480'},
                              {'n': '情色阅读', 'v': 'tag:6551de07551bf56ec540ccd0'},
                              {'n': '裸聊直播', 'v': 'tag:5e3b62e1ee21bb6cec2649c6'}]},
                   {'key': 'sort',
                    'name': '帖子',
                    'value': [{'n': '推荐', 'v': '3'},
                              {'n': '最新', 'v': '1'},
                              {'n': '最热', 'v': '2'},
                              {'n': '精华', 'v': '5'},
                              {'n': '视频', 'v': '6'}]}],
 'deep_all': [{'key': 'cate_id',
               'name': '深网禁地',
               'value': [{'n': '全部', 'v': 'mod:6539cd4dec571cc72bdc0a4d'},
                         {'n': '暗网萝莉', 'v': 'msec:650c3c09c8adc51465ea1b72'},
                         {'n': '圣水滋养', 'v': 'msec:6539d116ec571cc72bdc0aa5'},
                         {'n': '黄金盛筵', 'v': 'msec:6539d0d2ec571cc72bdc0a9f'},
                         {'n': '恋物癖', 'v': 'msec:698ef36184c6be0f8421aa5b'},
                         {'n': '精选重口', 'v': 'msec:6539d176ec571cc72bdc0ab3'}]},
              {'key': 'cate_id',
               'name': '暗网禁地',
               'value': [{'n': '全部', 'v': 'mod:652e566529a3f62c782d2edc'},
                         {'n': 'N号房', 'v': 'msec:652e589529a3f62c782d2f1a'}]},
              {'key': 'sort',
               'name': '排序',
               'value': [{'n': '综合', 'v': '1'},
                         {'n': '最新', 'v': '2'},
                         {'n': '最热', 'v': '3'},
                         {'n': '播放', 'v': '4'},
                         {'n': '收藏', 'v': '5'},
                         {'n': '点赞', 'v': '6'},
                         {'n': '评论', 'v': '7'}]}],
 'hot_all': []}

class Spider(BaseSpider):
    # 发布页: https://da8ttmrfqqhqf.cloudfront.net
    api_hosts = [
        'https://d2m0k739byzwun.cloudfront.net',
        'https://d1w3p997s8acw6.cloudfront.net',
    ]
    interface_key = '0a958fb9ac062420af6ba5f4caad779f'
    param_key = b'BxJand%xf5h3sycH'
    param_iv = b'BxJand%xf5h3sycH'
    xor_key = b'2019ysapp7527'
    img_host = 'https://simages.lkkwip.cn'
    vid_host = 'https://zzzsts.lkkwip.cn'
    audio_host = 'https://mp4.pjrwfe.cn'
    site_referer = 'https://da8ttmrfqqhqf.cloudfront.net/'

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
        self.host = self.api_hosts[0]
        self.session = Session()
        self.token = ''
        self.uid = ''
        self.ready = False
        self.module_map = {}
        self.tag_map = {}
        self.community_tag_parent = {}
        self.route_parent = {}
        # 深拷贝，防止壳端或运行逻辑修改全局内置配置
        self.classes = json.loads(json.dumps(BUILTIN_CLASSES, ensure_ascii=False))
        self.filters = json.loads(json.dumps(BUILTIN_FILTERS, ensure_ascii=False))
        self._hydrate_builtin_maps()
        self._normalize_cate_filters()

    def _hydrate_builtin_maps(self):
        """从内置 filters 重建模块/标签映射，保证无动态分类请求也能正常取数。"""
        zones = {
            'video_all': 'video', 'pic_all': 'pic', 'comic_all': 'comic',
            'novel_all': 'novel', 'tik_all': 'tik', 'community_all': 'community',
            'deep_all': 'deep', 'hot_all': 'video',
        }
        for zid, rows in (self.filters or {}).items():
            zone = zones.get(zid, 'video')
            for row in rows or []:
                key = str(row.get('key') or '')
                parent_mid = key[len('cate_mod_'):] if key.startswith('cate_mod_') else ''
                if parent_mid:
                    self.module_map[parent_mid] = {
                        'zone': zone, 'name': str(row.get('name') or parent_mid), 'type': None
                    }
                for item in row.get('value') or []:
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
        return '91国产集合完整版'

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        return None

    def init(self, extend=''):
        self.setExtendInfo(extend)
        try:
            if isinstance(extend, str) and extend.strip().startswith('http'):
                e = extend.strip().rstrip('/')
                self.api_hosts = [e] + [h for h in self.api_hosts if h != e]
        except Exception:
            pass
        # 完整版分类零网络依赖；登录仅为后续列表/详情/播放准备 token。
        self._ensure_login()
        self._hydrate_builtin_maps()
        return None

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
        raw = json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        cipher = AES.new(self.param_key, AES.MODE_CBC, self.param_iv)
        return base64.b64encode(cipher.encrypt(pad(raw, 16))).decode('utf-8')

    def _dec_data(self, enc):
        if not enc:
            return {}
        try:
            I = base64.b64decode(str(enc).replace('\n', '').replace('\r', ''))
            e = list(self.interface_key.encode('utf-8')) + list(I[:12])
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
        return ''.join(random.choice(chars) for _ in range(16)) + str(int(time.time() * 1000))

    def _ua(self):
        return (
            f'BuildID=com.abc.Butterfly;SysType=pc;DevID={self.uid};Ver=1.0.0;'
            f'DevType=iPhone;DeviceBrand=Apple;DeviceModel=iPhone;SystemName=iOS;'
            f'SystemVersion=17.0;Terminal=1;IsH5=1;Sid='
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
            url = self.host + '/api/app/mine/login/h5'
            body = {'data': self._enc_param({'devID': self.uid, 'sysType': 'pc', 'isAppStore': False})}
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
            data = self._req('GET', '/ping/domain/h5')
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
                    # 站点多数接口要求 data 内字段为字符串
                    kw['params'] = {'data': self._enc_param({k: str(v) for k, v in params.items() if v is not None})}
                r = self.session.get(url, headers=self._headers(), timeout=15, verify=False, **kw)
            else:
                payload = None
                if data is not None:
                    if isinstance(data, dict):
                        # 保留 list/dict 原样，其余转 str（搜索 keyWords 必须是数组）
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
        # 土豆式：每个父分类单独一行 filters 项（key=cate_xxx）
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
        # 兼容旧调用：返回扁平 n/v（不再直接用于 filters）
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
        # 统一 post@@：详情按 /vid/info 同时挂视频+画廊
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

    def _live_list(self, live_id, page, page_size=20):
        now = int(time.time())
        if str(live_id) == 'tj':
            data = self._req('POST', '/live/module/list/lld', data={'time': now}) or {}
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
        return self._req('POST', '/live/anchor/list/lld', data={
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
            'novel_all': 'novel', 'tik_all': 'tik', 'community_all': 'community',
            'deep_all': 'deep', 'hot_all': 'video',
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

        # ---- 视频大区：仅真实子分类做父行；无子分类模块并入单行「模块」----
        video_rows = rows_from_modules(video_mods, 'video', with_section=True)
        have = set()
        for r in video_rows:
            k = str(r.get('key') or '')
            if k.startswith('cate_mod_'):
                have.add(k[len('cate_mod_'):])
        rest = [m for m in video_mods if str(m.get('id') or '') not in have]
        if rest:
            video_rows.extend(self._flat_modules_filter(rest, 'video', key='cate_video_more', title='其它模块'))

        # 标签分区：/vid/sections 每个 section 是父分类，allTags 是子分类
        try:
            sec = self._req('GET', '/vid/sections') or {}
            # 这四组属于社区 Section，不能重复挂到视频大区。
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
                # 全部 = 第一个标签，保证默认可选
                vals = [{'n': '全部', 'v': vals[0]['v']}] + vals
                video_rows.append({
                    'key': f'cate_sec_{sid or sname}',
                    'name': sname,
                    'value': vals,
                })
        except Exception:
            pass

        # 补充 tag/conf 里 sections 没有的标签，单独一行「更多标签」
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

        # ---- 其它大区 ----
        # 规则：有真实 allSection 子分类 -> 土豆式多行父分类
        #       无真实子分类 -> 单行「分类」平铺，不造假父行
        def zone_filters(arr, zone, with_sort=True, with_section=True, flat_title='分类'):
            arr = list(arr or [])
            rows = []
            if with_section and arr:
                rows = rows_from_modules(arr, zone, with_section=True)
            # 若没有任何真实子分类父行，改为单行平铺
            if not rows:
                rows = self._flat_modules_filter(arr, zone, key=f'cate_{zone}', title=flat_title)
            else:
                # 有的模块有子分类、有的没有：把无子分类模块补进单行「其它分类」
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
        # 裸聊接口无列表数据，不展示该大区
        fmap['hot_all'] = []
        self.filters = fmap
        self._normalize_cate_filters()
        # 同步去掉无数据大区 class
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

    def _m3u8_play_url(self, source):
        """官方 H5 播放：/api/app/vid/h5/m3u8/{sourceURL}?token=&c=CDN"""
        if not source:
            return ''
        self._ensure_login()
        src = unquote(str(source)).lstrip('/')
        if src.startswith('http') and '.m3u8' in src:
            # 已是完整 h5 代理地址
            if '/api/app/vid/h5/m3u8/' in src:
                return src
            # 完整 CDN 直链 -> 抽 path
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
        for k in ['allVideoInfo', 'allMediaInfo', 'chosenVideoInfo', 'videos', 'list', 'data', 'records']:
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
            # 只存相对 source path，播放时拼 h5 m3u8；详情可附带 seriesCover 画廊
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

        # 1) 视频 section（推荐/深网等）
        data = self._req('GET', f'/vid/section/{section_id}', params={
            'pageNumber': int(page),
            'pageSize': int(page_size),
            'sortType': vsort,
        }) or {}
        if self._extract_list(data):
            return data

        mid = str(module_id or '')
        # 2) 模块 tagId（少数模块可用）
        if mid:
            data = self._req('GET', f'/vid/module/{mid}', params={
                'pageNumber': int(page),
                'pageSize': int(page_size),
                'moduleSort': msort,
                'tagId': str(section_id),
            }) or {}
            # 仅当结果与“无 tagId 的模块列表”有明显差异时才采用；否则继续本地过滤
            base = self._module_list(mid, page, page_size, msort) or {}
            a = [str(x.get('id') or '') for x in self._extract_list(data)[:5]]
            b = [str(x.get('id') or '') for x in self._extract_list(base)[:5]]
            if a and a != b:
                return data

        # 3) 漫画等：接口不按 section 过滤时，按标签名本地筛选模块流
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
            # 多拉几页再切片，尽量让不同子分类有差异
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

        # 4) 兜底：父模块全部
        if mid:
            return self._module_list(mid, page, page_size, msort) or {}
        return {}


    def _default_cate(self, tid):
        # 取该大区第一个 cate_* 行的第一个有效 v
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
            # 首页推荐必须使用真实模块，不能把 msec:/tag: 当 moduleID。
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

            stid = str(tid or '')
            if stid.startswith('search:'):
                return self.searchContent(stid[7:], False, pg)

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

            # 土豆式：从所有 cate_* 里取当前选中的子分类
            selected = self._get_selected_id(extend, self._default_cate(stid))
            if not selected:
                return result

            kind, rid = selected, selected
            if ':' in selected:
                kind, rid = selected.split(':', 1)

            # 短视频页直播 Tab：推荐及地区主播列表
            if stid == 'tik_all' and kind == 'live':
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

            # 社区大区：分类(all/mod/tag)；帖内视频+图在详情
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
                # cate_id 统一后，通过内部映射反查真实父模块及大区
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
                # mod:xxx 或裸 id
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
                # post/video/pic 统一：/vid/info 可能同时有 sourceURL + seriesCover
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
                # prefix == pic: name/pic from p[2]/p[3]
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
                if not isinstance(sc, list):
                    sc = []
                if not sc and pic_raw and prefix == 'pic':
                    sc = [pic_raw]
                img_urls = [self._abs(u, 'img') for u in sc if u]
                play_from = []
                play_url = []
                nt = str(news or '').upper()
                # sourceURL 是唯一视频判断依据，不能用 newsType 排除混合帖
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
                return {'list': [{
                    'vod_id': vid,
                    'vod_name': name or ('图集' if prefix == 'pic' else '社区帖'),
                    'vod_pic': self._img(pic_raw),
                    'type_name': '社区' if prefix == 'post' else ('图片' if prefix == 'pic' else '视频'),
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
        page = int(pg or 1)
        result = {'list': [], 'page': page}
        word = str(key or '').strip()
        if not word:
            return result
        try:
            # 登录只做一次，避免多个线程同时触发登录和修改共享 token。
            if not self._ensure_login():
                return result

            tasks = [
                ('video', 'POST', '/search/list', None, {
                    'pageNumber': page, 'pageSize': 20,
                    'keyWords': [word], 'realm': 'video',
                }),
                ('media_5', 'GET', '/media/search', {
                    'pageNumber': page, 'pageSize': 15, 'keyword': word, 'kind': '5'
                }, None),
                ('media_6', 'GET', '/media/search', {
                    'pageNumber': page, 'pageSize': 15, 'keyword': word, 'kind': '6'
                }, None),
                ('media_4', 'GET', '/media/search', {
                    'pageNumber': page, 'pageSize': 15, 'keyword': word, 'kind': '4'
                }, None),
                ('media_1', 'GET', '/media/search', {
                    'pageNumber': page, 'pageSize': 15, 'keyword': word, 'kind': '1'
                }, None),
                ('hot', 'GET', '/search/hotVid/list', {
                    'pageNumber': page, 'pageSize': 20
                }, None),
            ]
            responses = {}
            with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
                future_map = {
                    pool.submit(self._req, method, path, params=params, data=data): name
                    for name, method, path, params, data in tasks
                }
                for fut in as_completed(future_map):
                    name = future_map[fut]
                    try:
                        responses[name] = fut.result() or {}
                    except Exception:
                        responses[name] = {}

            visited = set()

            def add_item(it):
                if not it:
                    return
                vod_id = str(it.get('vod_id') or '')
                if not vod_id or vod_id in visited:
                    return
                visited.add(vod_id)
                result['list'].append(it)

            # 请求并发、结果按固定优先级输出，避免 as_completed 导致列表顺序跳动。
            for task_name, _, _, _, _ in tasks:
                for v in self._extract_list(responses.get(task_name) or {}):
                    try:
                        title = str(v.get('title') or v.get('name') or '')
                        if task_name == 'hot' and word.lower() not in title.lower():
                            continue
                        if 'mediaType' in v:
                            add_item(self._item_media(v))
                        else:
                            add_item(self._item_video(v))
                    except Exception:
                        continue
            return result
        except Exception:
            return result

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
                header = self._play_header()
                if self.token:
                    header['Authorization'] = self.token
                return {'parse': 0, 'url': self._proxy(play), 'header': header}

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
                    return {'parse': 0, 'url': self._m3u8_play_url(video), 'header': self._play_header()}
                return {'parse': 0, 'url': 'novel://' + json.dumps({'title': title, 'content': '正文加载失败'}, ensure_ascii=False), 'header': ''}

            return {'parse': 0, 'url': unquote(sid), 'header': self._play_header()}
        except Exception as e:
            return {'parse': 0, 'url': '', 'header': '', 'message': str(e)}

    def localProxy(self, param):
        url = unquote(param.get('url') or '')
        if not url:
            return [404, 'text/plain', b'']
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
                'Referer': self.site_referer,
            }
            if self.token:
                headers['Authorization'] = self.token
            r = self.session.get(url, headers=headers, timeout=20, verify=False)
            content = r.content or b''
            if not content:
                return [404, 'text/plain', b'']
            # m3u8：补全 KEY 相对路径
            if b'#EXTM3U' in content[:64] or url.endswith('.m3u8') or '/h5/m3u8/' in url:
                text = content.decode('utf-8', errors='ignore')
                # KEY 必须是绝对 API 地址；相对 /api/... 会被 EXO 请求到 127.0.0.1 而失败
                for key_path in ('/api/app/vid/sec', '/api/app/vid/m3u8sec'):
                    text = text.replace(f'URI="{key_path}"', f'URI="{self.host}{key_path}"')
                    text = text.replace(f"URI='{key_path}'", f"URI='{self.host}{key_path}'")
                return [200, 'application/vnd.apple.mpegurl', text.encode('utf-8')]
            # 图片 XOR
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
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass