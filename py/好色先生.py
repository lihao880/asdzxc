# coding=utf-8
import base64
import hashlib
import json
import random
import string
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, unquote, urljoin

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.extend = ''
        self.bootstrap = 'https://d2wexzpo1hxhi0.cloudfront.net'
        self.api_host = self.bootstrap
        self.image_host = 'https://simages.lkkwip.cn'
        self.video_hosts = ['http://rs2sts.az1vu.cn', 'https://rs2sts.az1vu.cn', 'https://vwq83.com']
        self.parameter_key = b'BxJand%xf5h3sycH'
        self.interface_key = b'c3d110af466a058d7bac6070b952cc5e'
        self.live_interface_key = b'0a958fb9ac062420af6ba5f4caad779f'
        self.xor_key = b'2019ysapp7527'
        self.uid = self._make_uid()
        self.token = ''
        self.login_time = 0
        self.classes = [
            {'type_name': '🎬 视频大区', 'type_id': 'video_all'},
            {'type_name': '💬 社区大区', 'type_id': 'community_all'},
            {'type_name': '📚 漫画大区', 'type_id': 'comic_all'},
            {'type_name': '⛩️ 动漫大区', 'type_id': 'anime_all'},
            {'type_name': '🎞️ 剧场大区', 'type_id': 'movie_all'},
            {'type_name': '📖 小说大区', 'type_id': 'novel_all'},
            {'type_name': '🖼️ 图集大区', 'type_id': 'pic_all'},
            {'type_name': '📱 短视频区', 'type_id': 'short_all'},
            {'type_name': '🔞 裸聊专区', 'type_id': 'naked_all'},
            {'type_name': '📺 直播专区', 'type_id': 'live_all'}
        ]
        self.routes = {
            'community_all': [('好色大厅', '65e0a031bc9767ecfd90a7a0'), ('约炮交友', '64f83937e0ff761e3dcdebee'), ('原创专区', '69b15f73143073bffac0b95f'), ('免费专区', '64f83943e0ff761e3dcdebf1'), ('发现精彩', '64f8395ae0ff761e3dcdebf4')],
            'comic_all': [('推荐', '65387ebaa1da3cd92f3bac6a'), ('本子', '68fa6420a7e2544d338d32c4'), ('主题', '66b2261f839c2f8e7fb48a7b'), ('C漫', '68fa6440a7e2544d338d32c9'), ('韩漫', '66b2266f839c2f8e7fb48a7f'), ('3D', '68fa64aea7e2544d338d32d0'), ('无修正', '68fa64bca7e2544d338d32d2'), ('单行本', '68fa64c7a7e2544d338d32d4'), ('连载中', '68fa64d1a7e2544d338d32d6'), ('AI绘画', '68fa64e5a7e2544d338d32d8'), ('CG图集', '68fa64eea7e2544d338d32da'), ('女性向', '68fa6500a7e2544d338d32dc'), ('yaoi', '68fa652fa7e2544d338d32de'), ('短篇', '68fa653da7e2544d338d32e0'), ('非H', '68fa6548a7e2544d338d32e2')],
            'anime_all': [('推荐', '65388e83a1da3cd92f3bad58'), ('主题', '66b229d3839c2f8e7fb48ab9'), ('同人', '66b229ec839c2f8e7fb48abb'), ('3D', '67a3581b433abe12fb309002'), ('中字', '66b22a59839c2f8e7fb48ac8'), ('无码', '66b22a45839c2f8e7fb48ac5'), ('泡面番', '68fbcfdb98d9f0d84ed151d6'), ('动画版', '66b22a19839c2f8e7fb48ac2'), ('MMD', '68fbd00998d9f0d84ed151da'), ('VAM', '68fbd02698d9f0d84ed151dd')],
            'movie_all': [('精选日漫', '66b4d0ef1e524c0278bc094b'), ('经典国漫', '66b4d2801e524c0278bc0966'), ('剧场版', '66b4d09b1e524c0278bc0948'), ('人气剧集', '66288d92acb0c84070573fac'), ('热门影视', '66b4d2031e524c0278bc095d')],
            'short_all': [('短视频', '68fa0dfba7e2544d338d3057')],
            'naked_all': [('性感魅魔', '68f8897837dd3a67da92c4be'), ('甜美少女', '68f889e537dd3a67da92c4c2'), ('熟女少妇', '68f88a7937dd3a67da92c4c5'), ('模特女神', '68f88b3937dd3a67da92c4c7')]
        }
        self.live_categories = [('推荐', 'tj'), ('中国', '6763e704daf2ddeb39b0ec83'),
                                ('日韩', '6763e717daf2ddeb39b0ec84'), ('越南', '6763e750daf2ddeb39b0ec87'),
                                ('乌克兰', '6763e72bdaf2ddeb39b0ec85'), ('俄罗斯', '6763e73bdaf2ddeb39b0ec86'),
                                ('欧美', '6763e768daf2ddeb39b0ec88'), ('男主播', '6763e7b6daf2ddeb39b0ec8a')]
        self.module_tags = {
            '65e0a031bc9767ecfd90a7a0': [('伦理之爱', '6277dfec1fb5df24ad64dfb3'), ('反差母狗', '65d70d5ed44f6893b7ab4cd6'), ('淫妻分享', '65d70d91d44f6893b7ab4cdf'), ('黑料吃瓜', '635e9b36d4dd9c00f6040043'), ('女优福利姬', '68079096f3532555983a2d13'), ('色友原创', '65d70d47d44f6893b7ab4cd2')],
            '64f83937e0ff761e3dcdebee': [('自拍分享', '5e2473375e3512a0cfbbd054'), ('同城交友', '65d70e27d44f6893b7ab4ce8'), ('绿奴淫妻', '65d70e46d44f6893b7ab4cee'), ('单男交友', '65d70e3bd44f6893b7ab4cec'), ('巨乳美乳', '66df0659a9f5e119ef18041d'), ('同性交友', '65d70e32d44f6893b7ab4cea')],
            '69b15f73143073bffac0b95f': [('好色乱伦', '69b15dd4143073bffac0b953'), ('好色原创', '69b15e50143073bffac0b958'), ('好色换妻', '69b15eac143073bffac0b95b')],
            '64f83943e0ff761e3dcdebf1': [('极品学妹', '66df0516a9f5e119ef180418'), ('颜值至上', '66dfcd81a9f5e119ef180ce3'), ('孕妇母乳', '66df02caa9f5e119ef180415'), ('霸凌捉奸', '66273cdff1c28e9c0b148028'), ('街射抄底', '66273d0df1c28e9c0b14802a'), ('厕拍达人', '66273d3ef1c28e9c0b14802c'), ('色情次元', '69be70f4b9a12ec70883e080')],
            '64f8395ae0ff761e3dcdebf4': [('奇趣百科', '66df018ca9f5e119ef18040e'), ('黄游资源', '66273b1bf1c28e9c0b148016'), ('调教分享', '66df0224a9f5e119ef180413')]
        }
        self.module_sections = {'65387ebaa1da3cd92f3bac6a': [('新本更新·好逼请主人品尝', '685fb968ee1b2870405f4d9b'),
                              ('吸晴韩漫·连载持续更新中', '6808e745f3532555983a3e9a'),
                              ('精选同人·你的性次元CP', '65e53b37f4340887446f7452'),
                              ('毁童年·你的童年我的童年好像不一样', '65f44a662b58f3d29bc2eb0c'),
                              ('近亲相奸·淫水不留外人田', '664352d01d2783ba5f290ba0'),
                              ('全彩涩漫·谁看了不爱', '65e53b4bf4340887446f7456'),
                              ('雌小鬼·总之就是非常可爱且耐操', '65f44b092b58f3d29bc2eb1a'),
                              ('小马大车·短小精悍', '68fa6759a7e2544d338d32f1'),
                              ('NTR绿帽专属·离离原上草', '65f44b932b58f3d29bc2eb21'),
                              ('肉便器·站起来蹬冒烟', '65f44ae02b58f3d29bc2eb16'),
                              ('熟女人妻·阿姨我鸡鸡痒', '66b73b6c1e524c0278bc2593'),
                              ('强暴轮奸·你叫啊 叫也不会有人救你', '68fa6808a7e2544d338d32fa'),
                              ('师生禁忌·爆草祖国小花朵', '68fa683fa7e2544d338d32fc'),
                              ('兽娘·福瑞控看过来', '68fa68dfa7e2544d338d3302'),
                              ('多人群P·嗨翻全场', '68fa68ffa7e2544d338d3304'),
                              ('阿嘿颜·喜欢看你淫荡的表情', '68fa693da7e2544d338d3306')],
 '68fa6420a7e2544d338d32c4': [('官方推荐', '68fa6c81a7e2544d338d3321'),
                              ('CG图集·尽情打飞机吧', '66aaf15d5205b5f23ba7af4b'),
                              ('巨乳诱惑·一秒入坑', '65f44aa22b58f3d29bc2eb11'),
                              ('双马尾·都要操冒烟啦', '68fa6d3da7e2544d338d3327'),
                              ('兔女郎·你是在诱惑我吗', '68fa6d51a7e2544d338d3329'),
                              ('无修正·接下来请多指教', '68fa6da8a7e2544d338d332b'),
                              ('情趣制服·心动不已 你总会喜欢', '65f44b232b58f3d29bc2eb1c'),
                              ('催眠·小母狗快来给主人操', '68fa6e2aa7e2544d338d332f'),
                              ('透视·你今天没穿胖次', '68fa6e55a7e2544d338d3331'),
                              ('角色扮演·你喜欢的样子我都有', '68fa6e93a7e2544d338d3335'),
                              ('纯爱H漫·余生请多指教', '68fa6ef5a7e2544d338d3337'),
                              ('耽美伪娘·干了这碗狗粮', '65e53b40f4340887446f7454'),
                              ('扶他·大屌美女', '68fa708aa7e2544d338d333b'),
                              ('百合·一起磨豆腐吗？', '68fa72afa7e2544d338d3349'),
                              ('后宫·我的美女老婆们', '66b739ec1e524c0278bc24c2'),
                              ('肛交·菊花一紧', '68fa711ba7e2544d338d333f'),
                              ('异种来袭·糟糕被包围了', '66b73aac1e524c0278bc2513'),
                              ('异世界·超能现实 幻想世界', '68fa718ea7e2544d338d3342')],
 '66b2261f839c2f8e7fb48a7b': [('原神色漫', '65e53b24f4340887446f744e'),
                              ('火影全员等你调教～', '665fded5d6c255005a869556'),
                              ('鬼灭之刃同人主题妖娆来袭', '664dcddc8e2b75c3b8b683b5'),
                              ('为美好的性爱献上祝福！', '667405b2dc4e92410ced1868'),
                              ('初音未来✨', '66b4d8d61e524c0278bc0a88'),
                              ('艦隊Collection', '66b61f651e524c0278bc1944'),
                              ('电锯人', '66b620121e524c0278bc1948'),
                              ('蔚蓝档案', '66b620911e524c0278bc194b')],
 '68fa6440a7e2544d338d32c9': [('C106', '68fa73c2a7e2544d338d3350'),
                              ('C105', '68fa73dfa7e2544d338d3352'),
                              ('C104', '68fa73f1a7e2544d338d3354'),
                              ('C103', '68fa7403a7e2544d338d3356'),
                              ('C102', '68fa7412a7e2544d338d3358'),
                              ('C101', '68fa7426a7e2544d338d335a'),
                              ('C100', '68fa7434a7e2544d338d335c'),
                              ('C99', '68fa744aa7e2544d338d335e'),
                              ('C98', '68fa7467a7e2544d338d3360'),
                              ('C97', '68fa7476a7e2544d338d3362'),
                              ('C96', '68fa7485a7e2544d338d3364'),
                              ('C95', '68fa749ca7e2544d338d3366')],
 '65388e83a1da3cd92f3bad58': [('精选里番～必看H漫', '65e5dd61f991137fab5f1a4b'),
                              ('本周推荐～最新动漫', '65a11ba8eea1d17a2de24773'),
                              ('萝莉少女～非常耐操', '65f3d0e42b58f3d29bc2e0b5'),
                              ('巨乳贫乳大对抗！✨', '66b4945335062bb1dd6c24ba'),
                              ('异种族～怪物入侵', '68fbca6e98d9f0d84ed151ab'),
                              ('3D～妖娆身姿卖弄风骚', '68fbc8c798d9f0d84ed1514f'),
                              ('18禁漫～无码解放', '68fbcaf798d9f0d84ed151af'),
                              ('熟女人妻～大奶少妇', '68fbc9e098d9f0d84ed151a5'),
                              ('BDSM～调教骚货', '68fbca2d98d9f0d84ed151a9'),
                              ('情趣诱惑～制服母狗', '68fbc93198d9f0d84ed15151'),
                              ('NTR～牛头人', '68fbc9ff98d9f0d84ed151a7'),
                              ('耽美百合～最爱同性', '68fbcac198d9f0d84ed151ad'),
                              ('禁忌乱伦～全家乱操', '68fbc9a698d9f0d84ed151a3')],
 '66b229d3839c2f8e7fb48ab9': [('后宫✨佳丽三千～', '66bdaa334028bb27ec17e6d5'),
                              ('NTR✨我要出轨啦～', '66bdb0354028bb27ec17e77e'),
                              ('BDSM✨调教控制～', '66bdb07f4028bb27ec17e784'),
                              ('师生✨禁忌之恋～', '66bdb0ad4028bb27ec17e786'),
                              ('公主✨傲娇就草你～', '66bdb0d64028bb27ec17e78c'),
                              ('熟女✨大雷少妇好喜欢～', '66bdb1144028bb27ec17e78e'),
                              ('异族✨跨种族做爱～', '66bdb1404028bb27ec17e794'),
                              ('耽美✨异性繁殖后代～', '66bdb1794028bb27ec17e79a'),
                              ('百合✨同性才是真爱～', '66bdb1884028bb27ec17e79c')],
 '66b229ec839c2f8e7fb48abb': [('原神同人', '65a12c63eea1d17a2de2477e'),
                              ('同人合集', '65e5dd59f991137fab5f1a49'),
                              ('崩坏-星穹铁道', '66b4d66b1e524c0278bc0997'),
                              ('碧蓝航线', '66b4d5b11e524c0278bc097a'),
                              ('蔚蓝档案', '66b4d6061e524c0278bc0980'),
                              ('鸣潮', '69aec2b3143073bffac0a846'),
                              ('绝区零', '69aec2a6143073bffac0a844'),
                              ('斗破苍穹', '69aec3dd143073bffac0a86d')]}
        tag_ids = {
            '调教':'696f2fba297419c81f0a3049','催眠':'696f2fba297419c81f0a3051','萝莉':'696f2fba297419c81f0a3019',
            'NTR':'696f2fbb297419c81f0a306e','国漫':'696f2fbb297419c81f0a309e','3D':'696f2fbb297419c81f0a3073',
            '剧情向':'696f2fba297419c81f0a3038','原神':'696f2fbb297419c81f0a308c','痴女':'696f2fba297419c81f0a300e',
            '同人':'696f2fba297419c81f0a3010','双马尾':'696f2fba297419c81f0a3017','阿嘿颜':'696f2fba297419c81f0a3018',
            '师生':'696f2fba297419c81f0a301f','百合':'696f2fba297419c81f0a3027','校园':'696f2fbb297419c81f0a307c',
            '耽美':'696f2fba297419c81f0a300f','巨乳':'696f2fba297419c81f0a302e','人妻':'696f2fba297419c81f0a3037',
            '都市':'696f2fbb297419c81f0a30d4','影视':'696f2fbb297419c81f0a30da','剧集':'696f2fbb297419c81f0a30db',
            '电影':'696f2fbb297419c81f0a30f2'}
        make_tags = lambda names: [('全部标签', '')] + [(name, tag_ids[name]) for name in names]
        self.media_tags = {
            'comic_all': make_tags(('调教','催眠','萝莉','NTR','国漫','3D','剧情向','原神','痴女','同人','双马尾','阿嘿颜')),
            'anime_all': make_tags(('调教','催眠','萝莉','NTR','国漫','3D','原神','痴女','同人','双马尾','阿嘿颜','师生')),
            'movie_all': make_tags(('影视','剧集','电影')),
            'novel_all': make_tags(('调教','NTR','剧情向','痴女','同人','百合','校园','耽美','巨乳','人妻','都市'))}
        self.pic_groups = [
            ('图集厂牌', '65c2e9aa3499fc57e0f1dafd', [('cosplay', '6630a191764291722f35152a'), ('秀人网', '65f17f8142aba5e51f28a5ce'), ('尤蜜荟', '65f17fb442aba5e51f28a5d4'), ('花漾', '65f17fc342aba5e51f28a5d7'), ('美媛馆', '65f17fe242aba5e51f28a5dd'), ('模范学院', '65f17ff442aba5e51f28a5df'), ('爱蜜社', '65f1800142aba5e51f28a5e2'), ('语画界', '65f1801842aba5e51f28a5e6'), ('嗲囡囡', '65f1802642aba5e51f28a5ea'), ('魅妍社', '65f181e242aba5e51f28a60d'), ('影私荟', '6688ced3d5e76291ad15a5ef'), ('花の颜', '668b9c7fd5e76291ad15b332'), ('猎女神', '668cb898d5e76291ad15c792'), ('星颜社', '668e12dcd5e76291ad15d9f6'), ('糖果画报', '668f64ced5e76291ad15ebb8'), ('喵糖映画', '6690a858d5e76291ad15f9c5'), ('AI性奴', '66bdb38b4028bb27ec17e7dc')]),
            ('百变服装', '67208bb78269cf267b6cb237', [('校服', '6721f1939c343f5290b11e1c'), ('丝袜', '67208cad8269cf267b6cb243'), ('内衣', '6721f11e9c343f5290b11e17'), ('制服', '6721f0d69c343f5290b11e15'), ('情趣', '672343a09c343f5290b132ed'), ('牛仔', '672343c99c343f5290b132f7'), ('JK', '672343d99c343f5290b132fa'), ('死库水', '672343eb9c343f5290b132fc'), ('和服', '672343f79c343f5290b132fe'), ('女仆', '672344049c343f5290b13300'), ('兔女郎', '672344109c343f5290b13302'), ('网袜', '6723441a9c343f5290b13304'), ('薄纱', '672344269c343f5290b13306'), ('旗袍', '672344319c343f5290b13308'), ('皮衣', '672344469c343f5290b1330c'), ('水手', '6723445d9c343f5290b1330f'), ('圣诞服', '672344679c343f5290b13311'), ('OL', '6721f14f9c343f5290b11e19')]),
            ('骚货任选', '6721f6e09c343f5290b11ea1', [('性感御姐', '6721f70a9c343f5290b11ea6'), ('甜美萝莉', '6721f7149c343f5290b11ea8'), ('青春少女', '6721f7369c343f5290b11eb0'), ('韵味美妇', '6721f7539c343f5290b11ebb'), ('长腿姐姐', '6721f8759c343f5290b11ec6'), ('人间胸器', '6721f88c9c343f5290b11ec8'), ('颜值母狗', '6721f89b9c343f5290b11eca')])
        ]
        self.video_groups = [
            ('最新', '659d434bda854a0b46bf912b', []),
            ('伦理之爱', '64f837e9e0ff761e3dcdebc8', [('禁忌母子', '65d73847d44f6893b7ab4d2f'), ('兄妹情深', '64f83eaae0ff761e3dcdec5d'), ('淫乱父女', '64f83ea2e0ff761e3dcdec5a'), ('姐弟相爱', '6964b0acc35b95eda6d3c53d'), ('爱上嫂子', '64f83ecfe0ff761e3dcdec6a'), ('师生乱伦', '6964b05ec35b95eda6d3c53b'), ('换夫换妻', '65d73865d44f6893b7ab4d31'), ('狂操小姨', '64f83eb3e0ff761e3dcdec60'), ('淫荡儿媳', '64f83ec4e0ff761e3dcdec67'), ('最爱岳母', '6964b048c35b95eda6d3c539'), ('家庭乱伦', '6964b0cbc35b95eda6d3c540'), ('舅侄畸恋', '64f83f05e0ff761e3dcdec6f')]),
            ('暗网', '65fadb520fc99765e04ac3ce', [('性虐SM', '65d7528ad44f6893b7ab4e23'), ('缅北禁地', '65d7529bd44f6893b7ab4e27'), ('喝尿吃屎', '65d75291d44f6893b7ab4e25'), ('巨物阳具', '65d752b9d44f6893b7ab4e2d')]),
            ('福利姬', '65e04ebcd44f6893b7ab9460', [('台北娜娜', 'actor:65e1d215f4340887446f5cf8'), ('玩偶姐姐', 'actor:65f50ed62b58f3d29bc2ef4a'), ('柚子猫', 'actor:65e19cb9bc9767ecfd90bbec'), ('饼干姐姐', 'actor:68970c0cbf7e6a64e9107f76'), ('小欣奈', 'actor:68970c48bf7e6a64e9107f78'), ('情深叉喔', 'actor:68970c68bf7e6a64e9107f7a'), ('刘玥', 'actor:65e18e1bbc9767ecfd90b9fb'), ('谭晓彤', 'actor:65e1aef8bc9767ecfd90bd89'), ('吴梦梦', 'actor:65e1b07abc9767ecfd90be6a'), ('奶咪', 'actor:65e1c503bc9767ecfd90c36e'), ('唐伯虎', 'actor:65e1d52af4340887446f5d51'), ('妮可 nicolove', 'actor:65e1d842f4340887446f5e17'), ('sunwall95', 'actor:65e1d8a1f4340887446f5e50'), ('欲梦', 'actor:65e1dd5af4340887446f5fad'), ('小水水', 'actor:65e1e0cef4340887446f5fff')]),
            ('黑料曝光', '65d74fdfd44f6893b7ab4dd1', [('网曝门泄密', '65d95b7ad44f6893b7ab4e88'), ('网红流出', '65d75095d44f6893b7ab4de5'), ('明星黑料', '65d7508bd44f6893b7ab4de3'), ('抓奸现场', '65f271d33fa82cca98a0545b')]),
            ('色图', '659e535f4a8f55efec47a9a7', []),
            ('探花大神', '65d96851d44f6893b7ab4f22', [('精选探花', '65d968cfd44f6893b7ab4f26'), ('最新探花', '65d96912d44f6893b7ab4f34'), ('小宝探花', '65d968c5d44f6893b7ab4f24'), ('锤子探花', '65d96900d44f6893b7ab4f30'), ('利哥探花', '65d968efd44f6893b7ab4f2c'), ('文轩探花', '65d968f7d44f6893b7ab4f2e'), ('七天探花', '65d96908d44f6893b7ab4f32'), ('李寻欢探花', '65d968d9d44f6893b7ab4f28')]),
            ('制服诱惑', '65d962e9d44f6893b7ab4ecf', [('JK少女', '65d964e1d44f6893b7ab4eda'), ('黑丝白丝', '6639d6c7764291722f355f8a'), ('乖巧女仆', '65d964d7d44f6893b7ab4ed8'), ('性感旗袍', '65d96508d44f6893b7ab4ee2'), ('OL制服', '65d964add44f6893b7ab4ed2'), ('cosplay', '667b7ea1c746cb70e60ea1a0'), ('空姐制服', '65d964bdd44f6893b7ab4ed4'), ('护士医生', '65d964cdd44f6893b7ab4ed6')]),
            ('韩国', '65d965c2d44f6893b7ab4eeb', [('韩国演艺圈卖淫事件', '65d96634d44f6893b7ab4ef5'), ('韩国女主播', '65d96622d44f6893b7ab4ef3'), ('韩国小情侣', '65d9664fd44f6893b7ab4ef8'), ('金先生 - 韩国探花，都是良家', '65d965edd44f6893b7ab4eed'), ('韩国情色 - 亚洲情色片天花板', '65d9660dd44f6893b7ab4ef1'), ('韩国棒子的网红', '65d9665bd44f6893b7ab4efa'), ('猜你喜欢', '66b62bb81e524c0278bc1a36')]),
            ('华语原创', '6617934e20ecd3576eab34d5', [('麻豆传媒', '661793ba20ecd3576eab34ea'), ('精东影业', '6617945120ecd3576eab34f7'), ('蜜桃传媒', '661793ab20ecd3576eab34e8'), ('爱神传媒', '661793e220ecd3576eab34ed'), ('糖心传媒', '661793f320ecd3576eab34f0'), ('黑料社', '6617940320ecd3576eab34f2'), ('台湾swag', '6617946420ecd3576eab34f9'), ('大象传媒', '6657f80211c77d08a50be3a5'), ('皇家华人', '6657f94f11c77d08a50be3ad'), ('兔子先生', '6657f99611c77d08a50be3b2'), ('性世界传媒', '6657fb7111c77d08a50be3f2'), ('91制片厂', '662c66e5bbb4178f5ce0cd2e'), ('天美传媒', '661fcc69601bcc6e1b764f4a'), ('星空无限传媒', '662c6543bbb4178f5ce0ccbb'), ('猜你喜欢', '66b62bc11e524c0278bc1a38')]),
            ('彩虹天堂', '65df0de2d44f6893b7ab5d11', [('蕾丝边 - 女女磨豆腐', '65e28b38f4340887446f63f7'), ('强人锁男--男上加男', '65f274c03fa82cca98a05483'), ('外国巨根爆插同性的菊花', '65f274d63fa82cca98a05486'), ('猜你喜欢', '66b62b9f1e524c0278bc1a34')]),
            ('成人节目', '65d96745d44f6893b7ab4efc', [('突袭女优家', '65d96779d44f6893b7ab4f00'), ('鲍鱼的胜利', '65d967bcd44f6893b7ab4f0e'), ('狼人插', '65d96806d44f6893b7ab4f1e'), ('抖阴学院', '667b7e34c746cb70e60ea188'), ('女优擂台摔角狂人', '65d967fed44f6893b7ab4f1c'), ('女优淫娃培训营', '65d967c6d44f6893b7ab4f10'), ('台湾街头性爱综艺', '667b80e0c746cb70e60ea259'), ('你好同学', '65d967d8d44f6893b7ab4f14'), ('情人劫密室逃脱', '65d967ebd44f6893b7ab4f18'), ('猜你喜欢', '66b62bcb1e524c0278bc1a3a')])
        ]
        self.filters = {}
        for tid in [x['type_id'] for x in self.classes]:
            fs = []
            if tid == 'live_all':
                self.filters[tid] = [{'key': 'cate_id', 'name': '地区',
                                      'value': [{'n': name, 'v': live_id}
                                                for name, live_id in self.live_categories]}]
                continue
            if tid == 'video_all':
                for name, mid, children in self.video_groups:
                    vals = [{'n': '全部', 'v': 'mod:' + mid}]
                    for child_name, child_id in children:
                        vals.append({'n': child_name, 'v': child_id if child_id.startswith('actor:') else 'msec:' + child_id})
                    fs.append({'key': 'cate_id', 'name': name, 'value': vals})
            elif tid == 'pic_all':
                for name, mid, children in self.pic_groups:
                    vals = [{'n': '全部', 'v': 'mod:' + mid}]
                    vals.extend({'n': child_name, 'v': 'msec:' + child_id} for child_name, child_id in children)
                    fs.append({'key': 'cate_id', 'name': name, 'value': vals})
            elif tid in self.routes:
                for name, mid in self.routes[tid]:
                    tags = self.module_tags.get(mid, [])
                    if tid == 'community_all' and tags:
                        vals = [{'n': '全部', 'v': 'mod:' + mid}]
                        vals.extend({'n': tag_name, 'v': 'mtag:' + mid + ':' + tag_id}
                                    for tag_name, tag_id in tags)
                        fs.append({'key': 'cate_id', 'name': name, 'value': vals})
                        continue
                    children = self.module_sections.get(mid, [])
                    if children:
                        vals = [{'n': '全部', 'v': 'mod:' + mid}]
                        vals.extend({'n': child_name, 'v': 'msec:' + child_id} for child_name, child_id in children)
                        fs.append({'key': 'cate_id', 'name': name, 'value': vals})
                    else:
                        fs.append({'key': 'cate_id', 'name': name, 'value': [{'n': name, 'v': 'mod:' + mid}]})
            if tid in self.media_tags:
                fs.append({'key': 'tag_id', 'name': '标签', 'value': [{'n': n, 'v': i} for n, i in self.media_tags[tid]]})
                fs.append({'key': 'payment_type', 'name': '付费', 'value': [{'n': '全部', 'v': ''}, {'n': 'VIP', 'v': 'vip'}, {'n': '金币', 'v': 'point'}]})
                fs.append({'key': 'time_type', 'name': '时间', 'value': [{'n': '全部', 'v': ''}, {'n': '本月', 'v': '1'}, {'n': '三个月内', 'v': '2'}, {'n': '半年内', 'v': '3'}, {'n': '更久', 'v': '4'}]})
            sort_values = ([{'n': '推荐', 'v': 'playNum'}, {'n': '最新', 'v': 'new'}, {'n': '人气', 'v': 'collect'}]
                           if tid in self.media_tags else
                           [{'n': '推荐', 'v': '1'}, {'n': '最新', 'v': 'new'}, {'n': '人气', 'v': 'hot'}])
            fs.append({'key': 'sort', 'name': '排序', 'value': sort_values})
            self.filters[tid] = fs

    def getName(self):
        return '好色先生'

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        self.extend = extend or ''
        try:
            cfg = json.loads(extend) if isinstance(extend, str) and extend.strip().startswith('{') else {}
            if cfg.get('api'):
                self.api_host = str(cfg['api']).rstrip('/')
        except Exception:
            pass

    def init(self, extend=''):
        self.setExtendInfo(extend)

    def _make_uid(self):
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(16)) + str(int(time.time() * 1000))

    def _headers(self, auth=True):
        h = {
            'temp': 'test',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36',
            'X-User-Agent': 'BuildID=com.abc.Butterfly;SysType=ios;DevID=%s;Ver=1.0.0;DevType=iPhone;Terminal=2;IsH5=1' % self.uid
        }
        if auth and self.token:
            h['Authorization'] = self.token
        return h

    def _encrypt_params(self, obj):
        raw = json.dumps(obj or {}, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        cipher = AES.new(self.parameter_key, AES.MODE_CBC, self.parameter_key)
        return base64.b64encode(cipher.encrypt(pad(raw, 16))).decode('ascii')

    def _decrypt_response(self, text, interface_key=None):
        try:
            raw = base64.b64decode(str(text).strip())
            seed = (interface_key or self.interface_key) + raw[:12]
            half = len(seed) // 2
            middle = hashlib.sha256(seed).digest()[8:24]
            left = hashlib.sha256(middle + seed[:half]).digest()
            right = hashlib.sha256(seed[half:] + middle).digest()
            key = left[:8] + right[8:24] + left[24:]
            iv = right[:4] + left[12:20] + right[28:]
            dec = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(raw[12:]), 16)
            return json.loads(dec.decode('utf-8', errors='ignore'))
        except Exception as e:
            self.log({'action': '响应解密失败', 'error': str(e)})
            return {}

    def _decode_result(self, obj):
        if not isinstance(obj, dict):
            return {}
        data = obj.get('data')
        if obj.get('hash') and isinstance(data, str):
            return self._decrypt_response(data)
        return data if data is not None else obj

    def _login(self, force=False):
        if self.token and not force and time.time() - self.login_time < 7200:
            return True
        payload = {'devID': self.uid, 'sysType': 'ios', 'cutInfos': '', 'isAppStore': False}
        for host in [self.api_host, self.bootstrap]:
            try:
                url = host.rstrip('/') + '/api/app/mine/login/h5'
                r = self.post(url, json={'data': self._encrypt_params(payload)}, headers=self._headers(False), timeout=12)
                data = self._decode_result(r.json())
                if isinstance(data, dict) and data.get('token'):
                    self.token = data['token']
                    self.login_time = time.time()
                    self.api_host = host.rstrip('/')
                    return True
            except Exception as e:
                self.log({'action': '游客登录失败', 'host': host, 'error': str(e)})
        return False

    def _request(self, path, params=None, method='get', retry=True):
        self._login()
        url = self.api_host.rstrip('/') + '/api/app/' + path.lstrip('/')
        clean = {k: str(v) for k, v in (params or {}).items() if v is not None and v != ''}
        try:
            if method == 'post':
                r = self.post(url, json={'data': self._encrypt_params(params or {})}, headers=self._headers(), timeout=15)
            else:
                qp = {'data': self._encrypt_params(clean)} if clean else None
                r = self.fetch(url, params=qp, headers=self._headers(), timeout=15)
            obj = r.json()
            if obj.get('code') in (5005, 5009) and retry:
                self._login(True)
                return self._request(path, params, method, False)
            if obj.get('code') != 200:
                self.log({'action': '接口异常', 'path': path, 'code': obj.get('code'), 'msg': obj.get('msg')})
                return {}
            return self._decode_result(obj)
        except Exception as e:
            self.log({'action': '请求失败', 'path': path, 'error': str(e)})
            return {}

    def _live_request(self, path, params, retry=True):
        self._login()
        url = self.api_host.rstrip('/') + '/api/app/' + path.lstrip('/')
        try:
            payload = dict(params or {})
            if 'time' in payload:
                payload['time'] = int(time.time() + 0.999)
            r = self.post(url, json={'data': self._encrypt_params(payload)}, headers=self._headers(), timeout=20)
            obj = r.json()
            if obj.get('code') != 200:
                if retry:
                    time.sleep(1)
                    return self._live_request(path, params, False)
                self.log({'action': '直播接口异常', 'path': path, 'code': obj.get('code'), 'msg': obj.get('msg')})
                return {}
            return self._decrypt_response(obj.get('data'), self.live_interface_key) if obj.get('hash') else (obj.get('data') or {})
        except Exception as e:
            if retry:
                time.sleep(1)
                return self._live_request(path, params, False)
            self.log({'action': '直播请求失败', 'path': path, 'error': str(e)})
            return {}

    def _extract_list(self, data):
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        for key in ('allVideoInfo', 'chosenVideoInfo', 'allMediaInfo', 'list', 'data', 'records', 'videos', 'searchMedia'):
            val = data.get(key)
            if isinstance(val, list):
                return val
        sections = data.get('allSection') or []
        out = []
        for section in sections if isinstance(sections, list) else []:
            if not isinstance(section, dict):
                continue
            out.extend(section.get('allVideoInfo') or [])
            out.extend(section.get('allMediaInfo') or [])
        return out

    def _abs(self, url, hosts):
        url = str(url or '').strip()
        if not url:
            return ''
        if url.startswith(('http://', 'https://')):
            return url
        return hosts[0].rstrip('/') + '/' + url.lstrip('/')

    def _pic(self, url):
        raw = self._abs(url, [self.image_host])
        return self.getProxyUrl() + '&url=' + quote(raw) if raw else ''

    def _play(self, url):
        return self._abs(url, self.video_hosts)

    def _duration(self, seconds):
        try:
            sec = int(seconds or 0)
            return '%02d:%02d' % (sec // 60, sec % 60)
        except Exception:
            return ''

    def _pack(self, item):
        return quote(json.dumps(item, ensure_ascii=False, separators=(',', ':')))

    def _unpack(self, text):
        try:
            return json.loads(unquote(text))
        except Exception:
            return {}

    def _format_video(self, v, prefix='video'):
        try:
            vid = str(v.get('id') or '')
            name = str(v.get('title') or v.get('name') or '').strip()
            if not vid or not name:
                return None
            cover = v.get('cover') or v.get('verticalCover') or v.get('horizontalCover') or ''
            source = v.get('sourceURL') or v.get('playURL') or v.get('url') or ''
            # vod_id 只封装详情/播放必需字段；禁止把整条 API 对象塞进列表响应，避免壳端日志和内存被放大。
            mini = {
                'id': vid, 'newsType': v.get('newsType') or '', 'title': name,
                'cover': cover, 'sourceURL': source, 'playTime': v.get('playTime') or 0
            }
            if prefix in ('community', 'pic', 'actorwork') or str(v.get('newsType') or '').upper() in ('COVER', 'GIFS'):
                mini['seriesCover'] = list(v.get('seriesCover') or [])

            if prefix == 'media':
                mini.update({'mediaType': v.get('mediaType') or '',
                             'currentEpisode': v.get('currentEpisode') or 0,
                             'totalEpisode': v.get('totalEpisode') or 0})
            remark = self._duration(v.get('playTime'))
            if prefix == 'media':
                mt = str(v.get('mediaType') or '')
                label = {'image': '📚 漫画', 'video': '⛩️ 动漫', 'text': '📖 小说', 'theatre': '🎞️ 剧场'}.get(mt, '📦 媒体')
                remark = '%s · %s话' % (label, v.get('currentEpisode') or v.get('totalEpisode') or 0)
            elif prefix in ('community', 'pic', 'actorwork'):
                pics = v.get('seriesCover') or []
                news_type = str(v.get('newsType') or '').upper()
                if prefix == 'actorwork':
                    remark = {'SP': '🎬 视频', 'COVER': '🖼️ 图片', 'GIFS': '✨ 动图'}.get(news_type, remark)
                else:
                    remark = ('🖼️ %s张' % len(pics)) if pics and not source else (remark or '社区内容')
            return {'vod_id': prefix + '@@' + self._pack(mini), 'vod_name': name,
                    'vod_pic': self._pic(cover), 'vod_remarks': remark}
        except Exception as e:
            self.log({'action': '单条转换失败', 'error': str(e)})
            return None

    def _format_media(self, v):
        return self._format_video(v, 'media')

    def _format_live(self, v):
        try:
            live_id = str(v.get('id') or '')
            name = str(v.get('name') or '').strip()
            url = str(v.get('url') or '').strip()
            if not live_id or not name or not url:
                return None
            mini = {'id': live_id, 'title': name, 'cover': v.get('coverImg') or '', 'sourceURL': url,
                    'isOnline': v.get('isOnline') is not False, 'viewCount': v.get('viewCount') or 0,
                    'country': v.get('country') or ''}
            status = '直播中' if mini['isOnline'] else '离线'
            viewers = int(mini['viewCount'] or 0)
            remark = '%s · %s人' % (status, viewers) if viewers else status
            return {'vod_id': 'live@@' + self._pack(mini), 'vod_name': name,
                    'vod_pic': str(mini['cover']), 'vod_remarks': remark}
        except Exception as e:
            self.log({'action': '直播单条转换失败', 'error': str(e)})
            return None

    def _format_naked(self, v):
        try:
            nid = str(v.get('id') or '')
            name = str(v.get('title') or '').strip()
            if not nid or not name:
                return None
            mini = {'id': nid, 'title': name, 'cover': v.get('cover') or '', 'price': v.get('price') or 0,
                    'age': v.get('age') or '', 'height': v.get('height') or '', 'cup': v.get('cup') or ''}
            return {'vod_id': 'naked@@' + self._pack(mini), 'vod_name': name, 'vod_pic': self._pic(mini['cover']),
                    'vod_remarks': '%s岁 · %scm · %s杯' % (mini['age'] or '-', mini['height'] or '-', mini['cup'] or '-')}
        except Exception as e:
            self.log({'action': '裸聊单条转换失败', 'error': str(e)})
            return None

    def _proxy_play(self, url):
        return self.getProxyUrl() + '&mode=play&url=' + quote(str(url or ''))

    def homeContent(self, filter=False):
        return {'class': self.classes, 'filters': self.filters}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        data = self._request('vid/module/659d434bda854a0b46bf912b', {'pageNumber': 1, 'pageSize': 20})
        return {'list': [x for x in (self._format_video(v) for v in self._extract_list(data)) if x]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}
        tid = str(tid or '')
        params = {'pageNumber': page, 'pageSize': 20}
        if extend.get('sort'):
            params['sort'] = extend.get('sort')
        cate = str(extend.get('cate_id') or '')
        module_id = cate.split(':', 1)[1] if cate.startswith('mod:') else ''
        section_id = cate.split(':', 1)[1] if cate.startswith('msec:') else ''
        actor_id = (cate.split(':', 1)[1] if cate.startswith('actor:') else
                    tid.split(':', 1)[1] if tid.startswith('actor:') else '')
        module_tag = cate.split(':', 2)[1:] if cate.startswith('mtag:') and cate.count(':') >= 2 else []
        prefix = 'video'
        data = {}
        if module_tag:
            module_id, tag_id = module_tag
            prefix = 'community' if tid == 'community_all' else 'video'
            sort_map = {'1': 3, 'new': 1, 'hot': 2}
            params.pop('sort', None)
            params.update({'moduleSort': sort_map.get(str(extend.get('sort') or '1'), 3), 'tagId': tag_id})
            data = self._request('vid/module/' + module_id, params)
        elif section_id:
            params['sortType'] = extend.get('sort') or 'new'
            data = self._request('vid/section/' + section_id, params)
            if not self._extract_list(data):
                parent_id = next((mid for _, mid, cs in self.video_groups + self.pic_groups
                                  if any(cid == section_id for _, cid in cs)), '')
                if not parent_id:
                    parent_id = next((mid for mid, cs in self.module_sections.items()
                                      if any(cid == section_id for _, cid in cs)), '')
                parent = self._request('vid/module/' + parent_id, {'pageNumber': page, 'pageSize': 100}) if parent_id else {}
                section = next((x for x in (parent.get('allSection') or [])
                                if str(x.get('sectionID') or '') == section_id), {})
                rows = (section.get('allVideoInfo') or []) + (section.get('allMediaInfo') or [])
                data = {'list': rows, 'hasNext': parent.get('hasNext', False)} if rows else parent
        elif actor_id:
            # 人物筛选直接返回其作品列表，不再把人物本身伪装成一集播放详情。
            media_type = str(extend.get('actor_type') or 'ALL').upper()
            types = [media_type] if media_type in ('SP', 'COVER', 'GIFS') else ['SP', 'COVER', 'GIFS']
            rows, total, has_next = [], 0, False
            for current_type in types:
                result = self._request('actress/vid/list', {
                    'actressID': actor_id, 'pageNumber': page, 'pageSize': 20,
                    'type': current_type, 'sortType': extend.get('sort') or 'new'})
                total += int(result.get('total') or 0) if isinstance(result, dict) else 0
                has_next = has_next or bool(result.get('hasNext')) if isinstance(result, dict) else has_next
                rows.extend(self._extract_list(result))
            items, seen = [], set()
            for row in rows:
                item = self._format_video(row, 'actorwork')
                if item and item['vod_id'] not in seen:
                    seen.add(item['vod_id']); items.append(item)
            return {'list': items, 'page': page, 'pagecount': page + (1 if has_next else 0),
                    'limit': 20, 'total': total or len(items)}
        elif tid.startswith('tag:'):
            params['tagID'] = tid.split(':', 1)[1]
            data = self._request('tag/vid/list', params)
        elif tid in ('comic_all', 'anime_all', 'movie_all'):
            prefix = 'media'
            tag_id = str(extend.get('tag_id') or '')
            use_library = bool(tag_id or extend.get('payment_type') or extend.get('time_type'))
            if use_library:
                media_params = {'pageNumber': page, 'pageSize': 20,
                                'canvas': {'comic_all': 'image', 'anime_all': 'video', 'movie_all': 'movie'}[tid],
                                'orderBy': extend.get('sort') or 'playNum'}
                if tag_id:
                    media_params['tagID'] = tag_id
                if extend.get('payment_type'):
                    media_params['paymentType'] = extend.get('payment_type')
                if extend.get('time_type'):
                    media_params['timeType'] = extend.get('time_type')
                data = self._request('media/library/search/v2', media_params, 'post')
                if not self._extract_list(data) and tid == 'movie_all':
                    if not module_id:
                        module_id = self.routes.get(tid, [('', '')])[0][1]
                    data = self._request('vid/module/' + module_id, params) if module_id else {}
            else:
                if not module_id:
                    module_id = self.routes.get(tid, [('', '')])[0][1]
                data = self._request('vid/module/' + module_id, params) if module_id else {}
        elif tid == 'novel_all':
            prefix = 'media'
            # library/search/v2 使用 canvas=text；仅旧版 media/random 兜底使用 type=3。
            params = {'pageNumber': page, 'pageSize': 20, 'canvas': 'text',
                      'orderBy': extend.get('sort') or 'playNum'}
            tag_id = str(extend.get('tag_id') or '')
            if tag_id:
                params['tagID'] = tag_id
            if extend.get('payment_type'):
                params['paymentType'] = extend.get('payment_type')
            if extend.get('time_type'):
                params['timeType'] = extend.get('time_type')
            data = self._request('media/library/search/v2', params, 'post')
            if not self._extract_list(data):
                fallback = dict(params)
                fallback.pop('canvas', None)
                fallback['type'] = 3
                data = self._request('media/random', fallback)
        elif tid == 'naked_all':
            if not module_id:
                module_id = self.routes['naked_all'][0][1]
            data = self._request('nakedchat/list', {'mid': module_id, 'pageNumber': page, 'pageSize': 20})
            items = [x for x in (self._format_naked(row) for row in self._extract_list(data)) if x]
            has_next = bool(data.get('hasNext')) if isinstance(data, dict) else False
            return {'list': items, 'page': page, 'pagecount': page + (1 if has_next else 0),
                    'limit': 20, 'total': int(data.get('total') or len(items)) if isinstance(data, dict) else len(items)}
        elif tid == 'live_all':
            live_id = str(extend.get('cate_id') or 'tj')
            now = int(time.time())
            if live_id == 'tj':
                live_data = self._live_request('live/module/list/lld', {'time': now})
                rows, seen = [], set()
                for block in live_data.get('recom') or []:
                    for row in block.get('anchors') or []:
                        rid = str(row.get('id') or '')
                        if rid and rid not in seen:
                            seen.add(rid); rows.append(row)
                start = (page - 1) * 20
                page_rows = rows[start:start + 20]
                has_next, total = start + 20 < len(rows), len(rows)
            else:
                live_data = self._live_request('live/anchor/list/lld', {
                    'id': live_id, 'pageNumber': page, 'pageSize': 20, 'time': now})
                page_rows = live_data.get('list') or []
                has_next = bool(live_data.get('hasNext'))
                total = int(live_data.get('total') or len(page_rows))
            items = [x for x in (self._format_live(row) for row in page_rows) if x]
            return {'list': items, 'page': page, 'pagecount': page + (1 if has_next else 0),
                    'limit': 20, 'total': total}
        else:
            if tid == 'community_all':
                prefix = 'community'
            elif tid == 'pic_all':
                prefix = 'pic'
            if not module_id:
                if tid == 'video_all':
                    module_id = self.video_groups[0][1]
                elif tid == 'pic_all':
                    module_id = self.pic_groups[0][1]
                else:
                    module_id = self.routes.get(tid, [('', '')])[0][1]
            data = self._request('vid/module/' + module_id, params) if module_id else self._request('vid/list', params)
        formatter = self._format_media if prefix == 'media' else (lambda x: self._format_video(x, prefix))
        items, seen = [], set()
        for row in self._extract_list(data):
            item = formatter(row)
            if item and item['vod_id'] not in seen:
                seen.add(item['vod_id']); items.append(item)
        has_next = data.get('hasNext') if isinstance(data, dict) else None
        pagecount = page + 1 if has_next is True or (has_next is None and len(items) >= 20) else page
        return {'list': items, 'page': page, 'pagecount': pagecount, 'limit': 20, 'total': pagecount * 20}

    def _rich(self, name, route):
        name = str(name or '').strip()
        if not name:
            return ''
        payload = json.dumps({'id': route, 'name': name}, ensure_ascii=False, separators=(',', ':'))
        return '[a=cr:%s/]%s[/a]' % (payload, name)

    def detailContent(self, ids):
        raw_id = str(ids[0]) if ids else ''
        if '@@' not in raw_id:
            return {'list': []}
        prefix, payload = raw_id.split('@@', 1)
        v = self._unpack(payload)
        if not v:
            return {'list': []}
        if prefix == 'live':
            source = str(v.get('sourceURL') or '')
            status = '直播中' if v.get('isOnline') is not False else '离线'
            viewers = int(v.get('viewCount') or 0)
            vod = {'vod_id': raw_id, 'vod_name': v.get('title') or '直播间',
                   'vod_pic': str(v.get('cover') or ''), 'vod_remarks': status,
                   'vod_content': '地区：%s\n当前观众：%s\n直播流实时更新' % (v.get('country') or '未知', viewers),
                   'vod_play_from': '直播专线' if source else '',
                   'vod_play_url': ('立即播放$live_play@@' + quote(source)) if source else ''}
            return {'list': [vod]}
        if prefix == 'naked':
            info = self._request('nakedchat/info', {'id': v.get('id')}) or v
            images = [self._pic(x) for x in (info.get('images') or []) if x]
            if not images and info.get('cover'):
                images = [self._pic(info.get('cover'))]
            meta = '年龄：%s  身高：%s  体重：%s  罩杯：%s  价格：%s' % (
                info.get('age') or '-', info.get('height') or '-', info.get('weight') or '-',
                info.get('cup') or '-', info.get('price') or '-')
            contact = str(info.get('contact') or '').strip()
            content = meta + ('\n营业时间：' + str(info.get('businessHours')) if info.get('businessHours') else '')
            content += ('\n联系方式：' + contact if contact else '')
            content += ('\n' + str(info.get('summary')) if info.get('summary') else '')
            vod = {'vod_id': raw_id, 'vod_name': info.get('title') or v.get('title') or '裸聊详情',
                   'vod_pic': self._pic(info.get('cover') or v.get('cover')), 'vod_remarks': '销量%s' % (info.get('saleNum') or 0),
                   'vod_content': content, 'vod_play_from': '图片资料' if images else '',
                   'vod_play_url': ('点击浏览$pic_play@@' + '&&'.join(images)) if images else ''}
            return {'list': [vod]}
        if prefix == 'actress':
            actress_id = str(v.get('id') or '')
            data = self._request('actress/info', {'id': actress_id})
            info = data.get('info') if isinstance(data, dict) else {}
            if not isinstance(info, dict) or not info:
                info = v
            groups = []
            for label, media_type in (('视频作品', 'SP'), ('图片作品', 'COVER'), ('动图作品', 'GIFS')):
                rows = self._extract_list(self._request('actress/vid/list', {
                    'actressID': actress_id, 'pageNumber': 1, 'pageSize': 50,
                    'type': media_type, 'sortType': 'new'}))
                entries = []
                for row in rows:
                    name = str(row.get('title') or row.get('name') or label).replace('#', ' ')
                    if media_type == 'SP':
                        target = self._play(row.get('sourceURL') or row.get('playURL') or '')
                    else:
                        pics = [self._pic(x) for x in (row.get('seriesCover') or []) if x]
                        target = 'pic_play@@' + '&&'.join(pics) if pics else ''
                    if target:
                        entries.append('%s$%s' % (name, target))
                if entries:
                    groups.append((label, '#'.join(entries)))
            cover = info.get('portrait') or ((info.get('seriesCover') or [''])[0])
            summary = str(info.get('summary') or '')
            meta = '地区：%s  身高：%s  三围：%s' % (info.get('region') or '未知', info.get('height') or '未知', info.get('threeDimensions') or '未知')
            vod = {'vod_id': raw_id, 'vod_name': info.get('name') or info.get('chineseName') or '女优详情',
                   'vod_pic': self._pic(cover), 'vod_remarks': '视频%s · 图片%s · 动图%s' % (
                       info.get('videoCount') or 0, info.get('picsCount') or 0, info.get('gifsCount') or 0),
                   'vod_content': meta + ('\n' + summary if summary else ''),
                   'vod_play_from': '$$$'.join(x[0] for x in groups),
                   'vod_play_url': '$$$'.join(x[1] for x in groups)}
            return {'list': [vod]}
        if prefix == 'media':
            info = self._request('media/v2/info', {'id': v.get('id')}) or v
            chapters = self._extract_list(self._request('media_content/v2/list', {
                'mediaId': v.get('id'), 'pageNumber': 1, 'pageSize': 50}))
            mt = str(info.get('mediaType') or v.get('mediaType') or '')
            entries = []
            for c in chapters:
                cid = c.get('id')
                if cid:
                    entries.append('%s$media_chapter@@%s@@%s' % (c.get('name') or ('第%s话' % c.get('episodeNumber')), mt, cid))
            vod = {'vod_id': raw_id, 'vod_name': info.get('title') or v.get('title'),
                   'vod_pic': self._pic(info.get('verticalCover') or info.get('horizontalCover') or v.get('cover')),
                   'vod_remarks': '共%s话' % len(entries), 'vod_content': info.get('summary') or '',
                   'vod_play_from': {'image': '漫画阅读', 'text': '小说阅读', 'video': '动漫播放', 'theatre': '剧场播放'}.get(mt, '媒体内容'),
                   'vod_play_url': '#'.join(entries)}
            return {'list': [vod]}
        source = self._play(v.get('sourceURL'))
        news_type = str(v.get('newsType') or '').upper()
        # SP 的 seriesCover 是封面/详情配图，不是图集；仅 COVER/GIFS 或无视频内容生成图片线路。
        raw_pics = (v.get('seriesCover') or []) if news_type in ('COVER', 'GIFS') or not source else []
        pics = [self._pic(x) for x in raw_pics if x]
        actor_links, tag_links = [], []
        pub = v.get('publisher') if isinstance(v.get('publisher'), dict) else {}
        if pub.get('name') and pub.get('uid'):
            actor_links.append(self._rich(pub.get('name'), 'actor:' + str(pub.get('uid'))))
        for a in v.get('actresses') or []:
            if isinstance(a, dict) and a.get('name') and a.get('id'):
                actor_links.append(self._rich(a['name'], 'actor:' + str(a['id'])))
        for t in v.get('tags') or []:
            if isinstance(t, dict) and t.get('name') and t.get('id'):
                tag_links.append(self._rich(t['name'], 'tag:' + str(t['id'])))
        play_from, play_url = [], []
        if pics:
            play_from.append('图片浏览'); play_url.append('点击浏览$pic_play@@' + '&&'.join(pics))
        if source:
            play_from.append('视频专线'); play_url.append('点击播放$' + source)
        desc = str(v.get('content') or v.get('richText') or '').strip()
        if tag_links:
            desc = '🏷️ ' + ' '.join(tag_links) + ('\n' + desc if desc else '')
        vod = {'vod_id': raw_id, 'vod_name': v.get('title') or '内容', 'vod_pic': self._pic(v.get('cover')),
               'vod_remarks': self._duration(v.get('playTime')), 'vod_actor': ' '.join(actor_links),
               'vod_content': desc, 'vod_play_from': '$$$'.join(play_from), 'vod_play_url': '$$$'.join(play_url)}
        return {'list': [vod]}

    def searchContent(self, key, quick=False, pg='1'):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        word = str(key or '').strip()
        if not word:
            return {'list': [], 'page': page, 'pagecount': page}

        # 视频、社区图片、动漫、漫画、小说走站点真实搜索接口并发请求。
        jobs = [
            ('video', 'search/list', {'pageNumber': page, 'pageSize': 20,
                                      'keyWords': [word], 'realm': 'SP', 'sortType': 1}, 'post'),
            ('pic', 'search/list', {'pageNumber': page, 'pageSize': 20,
                                    'keyWords': [word], 'realm': 'COVER', 'sortType': 1}, 'post'),
            ('anime', 'media/search', {'pageNumber': page, 'pageSize': 20, 'keyword': word, 'kind': 1}, 'get'),
            ('comic', 'media/search', {'pageNumber': page, 'pageSize': 20, 'keyword': word, 'kind': 2}, 'get'),
            ('novel', 'media/search', {'pageNumber': page, 'pageSize': 20, 'keyword': word, 'kind': 3}, 'get')
        ]
        chunks = [[] for _ in jobs]
        has_next = False
        self._login()  # 并发前只登录一次，避免多个线程重复刷新游客 Token。
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = {pool.submit(self._request, path, params, method): i
                       for i, (_, path, params, method) in enumerate(jobs)}
            for future in as_completed(futures):
                i = futures[future]
                try:
                    data = future.result() or {}
                    chunks[i] = self._extract_list(data)
                    has_next = has_next or bool(data.get('hasNext'))
                except Exception as e:
                    self.log({'action': '并发搜索单路失败', 'type': jobs[i][0], 'error': str(e)})

        result, seen = [], set()
        zone_marks = {'video': '🎬 视频区', 'pic': '🖼️ 图片区', 'anime': '⛩️ 动漫区',
                      'comic': '📚 漫画区', 'novel': '📖 小说区'}
        for (kind, _, _, _), rows in zip(jobs, chunks):
            for v in rows:
                try:
                    if kind in ('anime', 'comic', 'novel'):
                        item = self._format_media(v)
                    elif kind == 'pic':
                        item = self._format_video(v, 'community')
                    else:
                        item = self._format_video(v)
                    if not item or item['vod_id'] in seen:
                        continue
                    item['vod_remarks'] = '%s · %s' % (zone_marks[kind], item.get('vod_remarks') or '搜索结果')
                    seen.add(item['vod_id']); result.append(item)
                except Exception as e:
                    self.log({'action': '搜索单条转换失败', 'error': str(e)})
        return {'list': result, 'page': page, 'pagecount': page + (1 if has_next else 0)}

    def playerContent(self, flag, id, vipFlags):
        play_id = unquote(str(id or ''))
        if play_id.startswith('live_play@@'):
            source = play_id.split('@@', 1)[1]
            return {'parse': 0, 'playUrl': '', 'url': source,
                    'header': {'User-Agent': 'Mozilla/5.0'}}
        if play_id.startswith('pic_play@@'):
            return {'parse': 0, 'playUrl': '', 'url': 'pics://' + play_id[10:], 'header': {}}
        if play_id.startswith('media_chapter@@'):
            parts = play_id.split('@@', 2)
            mt, cid = parts[1], parts[2]
            data = self._request('media_content/v2/info', {'id': cid})
            if mt == 'image':
                pics = [self._pic(x) for x in (data.get('urlSet') or []) if x]
                return {'parse': 0, 'playUrl': '', 'url': 'pics://' + '&&'.join(pics), 'header': {}}
            if mt == 'text':
                text = str(data.get('text') or '')
                return {'parse': 0, 'url': 'novel://' + json.dumps({'title': data.get('name') or '正文', 'content': text}, ensure_ascii=False), 'header': {}}
            play_id = data.get('videoUrl') or data.get('audioUrl') or ''
        if not play_id:
            return {'parse': 0, 'url': '', 'header': {}}
        final_url = str(play_id).strip()
        if not final_url.startswith(('http://', 'https://')):
            final_url = self._play(final_url)
        # 直连 CDN 在壳端 EXO 会报 2001；通过本地代理重写 m3u8、分片和密钥地址。
        if '.m3u8' in final_url.lower():
            final_url = self._proxy_play(final_url)
        return {'parse': 0, 'playUrl': '', 'url': final_url,
                'header': {'User-Agent': 'Mozilla/5.0'}}

    def localProxy(self, param):
        param = param or {}
        url = unquote(str(param.get('url', '')))
        mode = str(param.get('mode', ''))
        if not url:
            return [404, 'text/plain', b'']
        if mode == 'play':
            candidates = [url] if url.startswith(('http://', 'https://')) else [h.rstrip('/') + '/' + url.lstrip('/') for h in self.video_hosts]
            last = b''
            for target in candidates:
                try:
                    r = self.fetch(target, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
                    content = r.content or b''; last = content
                    if not content or getattr(r, 'status_code', 500) >= 400:
                        continue
                    if b'#EXTM3U' in content[:200]:
                        text = content.decode('utf-8', errors='ignore')
                        base = target.rsplit('/', 1)[0] + '/'
                        out = []
                        for line in text.splitlines():
                            line = line.strip()
                            if line and not line.startswith('#'):
                                line = self._proxy_play(urljoin(base, line))
                            elif 'URI="' in line:
                                old = line.split('URI="', 1)[1].split('"', 1)[0]
                                key_url = urljoin(base, old)
                                # 源清单把真实根目录密钥伪写成 http://domain/enc.key。
                                if old.startswith(('http://domain/', 'https://domain/')):
                                    root = target.split('://', 1)
                                    key_url = root[0] + '://' + root[1].split('/', 1)[0] + '/' + old.split('domain/', 1)[1]
                                line = line.replace(old, self._proxy_play(key_url))
                            out.append(line)
                        return [200, 'application/vnd.apple.mpegurl', ('\n'.join(out)).encode('utf-8')]
                    if target.split('?', 1)[0].endswith('/enc.key'):
                        stripped = content.rstrip(b'\r\n')
                        content = stripped if len(stripped) in (16, 24, 32) else content
                    mime = 'video/mp2t' if target.split('?', 1)[0].endswith('.ts') else 'application/octet-stream'
                    return [200, mime, content]
                except Exception as e:
                    self.log({'action': '播放代理切换CDN', 'url': target, 'error': str(e)})
            return [502, 'text/plain', last or b'play proxy failed']
        try:
            r = self.fetch(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': self.api_host + '/'}, timeout=15)
            content = r.content
            if not content:
                return [404, 'text/plain', b'']
            magic = content[:20]
            if not (content.startswith((bytes.fromhex('ffd8ff'), bytes.fromhex('89504e47'), b'GIF8', b'BM')) or b'WEBP' in magic):
                out = bytearray(content)
                for i in range(min(100, len(out))):
                    out[i] ^= self.xor_key[i % len(self.xor_key)]
                content = bytes(out)
            mime = 'image/png' if content.startswith(bytes.fromhex('89504e47')) else 'image/gif' if content.startswith(b'GIF8') else 'image/webp' if b'WEBP' in content[:20] else 'image/jpeg'
            return [200, mime, content]
        except Exception as e:
            return [500, 'text/plain', str(e).encode('utf-8')]

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return None

    def action(self, action):
        return None

    def destroy(self):
        return None