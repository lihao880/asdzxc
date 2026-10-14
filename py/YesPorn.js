// YesPorn - 客户端单文件源（纯正则解析，无 cheerio 依赖）
// 站点：https://cn.yesporn.ws/  入口：/enter
const HOST = 'https://cn.yesporn.ws';
const UA = 'Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36';

function mylog(...args) {
    console.log('[YesPorn]', ...args);
}

function full(u) {
    if (!u) return '';
    u = String(u);
    return u.indexOf('http') === 0 ? u : HOST + (u[0] === '/' ? '' : '/') + u;
}

async function myFetch(url, method, body) {
    try {
        var opt = { method: method || 'get', headers: { 'User-Agent': UA, 'Referer': HOST + '/', 'X-Requested-With': 'XMLHttpRequest' } };
        if (body) { opt.body = body; opt.headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'; }
        let res = await req(url, opt);
        return (res && typeof res === 'object') ? res.content : res;
    } catch (err) {
        mylog('myfetch err', err);
        return '';
    }
}

async function init(cfg) {
    mylog('Spider Init Done');
}

var CLASSES = [
    { type_id: 'latest-updates', type_name: '最新' },
    { type_id: 'most-popular', type_name: '最热' },
    { type_id: 'top-rated', type_name: '评分最高' },
    { type_id: 'longest', type_name: '最长' },
    { type_id: 'most-commented', type_name: '评论最多' },
    { type_id: 'most-favourited', type_name: '最受喜爱' },
    { type_id: 'brazzers', type_name: 'Brazzers' },
    { type_id: 'reality-kings', type_name: 'Reality Kings' },
    { type_id: 'bangbros', type_name: 'Bangbros' },
    { type_id: 'puretaboo', type_name: 'PureTaboo' }
];

async function home(filter) {
    try {
        return JSON.stringify({ class: CLASSES, filters: {} });
    } catch (e) {
        mylog('home err', e.message);
        return JSON.stringify({ class: [], filters: {} });
    }
}

async function homeVod() {
    try {
        var html = await myFetch(HOST + '/enter');
        return JSON.stringify({ list: parseList(html) });
    } catch (e) {
        mylog('homeVod err', e.message);
        return JSON.stringify({ list: [] });
    }
}

async function homeContent(filter) {
    try {
        var html = await myFetch(HOST + '/enter');
        return JSON.stringify({ class: CLASSES, filters: {}, list: parseList(html) });
    } catch (e) {
        mylog('homeContent err', e.message);
        return JSON.stringify({ class: CLASSES, filters: {}, list: [] });
    }
}

// 纯正则解析列表
function parseList(html) {
    if (!html) return [];
    var list = [];
    var seen = {};
    var blocks = html.split('<div class="thumb');
    for (var i = 1; i < blocks.length; i++) {
        var b = blocks[i];
        var mh = b.match(/href="(https?:\/\/[^"]*\/video\/[^"]+)"/);
        if (!mh) continue;
        var href = mh[1];

        var title = '';
        var mt = b.match(/title="([^"]*)"/);
        if (mt) title = mt[1].trim();
        if (!title) {
            var ma = b.match(/alt="([^"]*)"/);
            if (ma) title = ma[1].trim();
        }
        if (!title) continue;

        var pic = '';
        var mp = b.match(/data-original="([^"]+)"/);
        if (mp) pic = mp[1];

        var remark = '';
        var mr = b.match(/class="time">([^<]+)</);
        if (mr) remark = mr[1].trim();

        var vid = href;
        if (seen[vid]) continue;
        seen[vid] = 1;

        list.push({
            vod_id: vid,
            vod_name: title,
            vod_pic: pic,
            vod_remarks: remark
        });
    }
    return list;
}

async function category(tid, pg, filter, extend) {
    try {
        pg = parseInt(pg) || 1;
        tid = tid || 'post_date';
        // 站内排序 slug 映射到 sort_by 值
        var sortMap = {
            'latest-updates': 'post_date',
            'most-popular': 'video_viewed',
            'top-rated': 'rating',
            'longest': 'duration',
            'most-commented': 'most_commented',
            'most-favourited': 'most_favourited'
        };
        var sortBy = sortMap[tid] || 'post_date';
        var body = 'block_id=list_videos_most_recent_videos&sort_by=' + sortBy + '&from=' + pg;
        mylog('category POST from=' + pg);
        var html = await myFetch(HOST + '/enter', 'post', body);
        var list = parseList(html);
        if (!list || list.length === 0) {
            html = await myFetch(HOST + '/enter');
            list = parseList(html);
        }
        return JSON.stringify({ list: list, page: pg, pagecount: 673 });
    } catch (e) {
        mylog('category err', e.message);
        return JSON.stringify({ list: [], pagecount: 1 });
    }
}
async function detail(id) {
    try {
        var pageUrl = full(id);
        mylog('detail url', pageUrl);
        var html = await myFetch(pageUrl);
        if (!html) return JSON.stringify({ list: [] });

        var name = '';
        var mh = html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/);
        if (mh) name = mh[1].replace(/<[^>]+>/g, '').trim();
        if (!name) {
            var mo = html.match(/og:title"\s+content="([^"]*)"/);
            if (mo) name = mo[1];
        }
        if (!name) {
            var mt = html.match(/<title>([\s\S]*?)<\/title>/);
            if (mt) name = mt[1].trim();
        }

        var pic = '';
        var mp = html.match(/og:image"\s+content="([^"]*)"/);
        if (mp) pic = mp[1];

        var content = '';
        var mc = html.match(/id="resume"[^>]*>([\s\S]*?)<\/span>/);
        if (mc) content = mc[1].replace(/<[^>]+>/g, '').trim();

        var vod = {
            vod_id: pageUrl,
            vod_name: name,
            vod_pic: pic,
            vod_content: content,
            vod_remarks: '',
            vod_play_from: 'YesPorn',
            vod_play_url: '播放$' + pageUrl
        };
        return JSON.stringify({ list: [vod] });
    } catch (e) {
        mylog('detail err', e.message);
        return JSON.stringify({ list: [] });
    }
}

async function search(wd, quick, pg) {
    try {
        var url = HOST + '/search/?q=' + encodeURIComponent(wd);
        mylog('search url', url);
        var html = await myFetch(url);
        return JSON.stringify({ list: parseList(html), pagecount: 9999 });
    } catch (e) {
        mylog('search err', e.message);
        return JSON.stringify({ list: [], pagecount: 1 });
    }
}

function isDirectVideoUrl(url) {
    return ['m3u', 'mp4'].some(function (x) { return (url + '').includes(x); });
}

async function play(flag, id, flags) {
    mylog('play id:', id);
    try {
        var pageUrl = full(id);
        var m = pageUrl.match(/\/video\/(\d+)/);
        var vid = m ? m[1] : '';
        if (!vid) {
            return JSON.stringify({ parse: 1, url: pageUrl, header: { 'User-Agent': UA, 'Referer': HOST + '/' } });
        }
        // 走下载页拿带 download=true 的真直链（绕过 kt_player 校验）
        var dlPage = HOST + '/view_video_download.php?id=' + vid + '&format=720';
        var html = await myFetch(dlPage);
        var real = extractDownloadUrl(html);
        if (!real) {
            html = await myFetch(HOST + '/view_video_download.php?id=' + vid + '&format=480');
            real = extractDownloadUrl(html);
        }
        if (real) {
            mylog('命中下载直链', real);
            return JSON.stringify({ parse: 0, url: real, header: { 'User-Agent': UA, 'Referer': dlPage } });
        }
        // 兜底：转嗅探 embed
        return JSON.stringify({ parse: 1, url: HOST + '/embed/' + vid + '/', header: { 'User-Agent': UA, 'Referer': pageUrl } });
    } catch (e) {
        mylog('play失败:', e.message);
        return JSON.stringify({ parse: 1, url: full(id), header: { 'User-Agent': UA, 'Referer': HOST + '/' } });
    }
}

// 从下载页提取带 download=true 的真直链
function extractDownloadUrl(html) {
    if (!html) return '';
    var m = html.match(/(https?:\/\/[^"'\s<>]+\/get_file\/[^"'\s<>]+\.mp4[^"'\s<>]*)/);
    if (m && m[1]) return m[1].replace(/&amp;/g, '&');
    return '';
}function extractVideoUrl(html) {
    if (!html) return '';
    var m = html.match(/video_url\s*:\s*'([^']+)'/);
    if (!m) m = html.match(/video_url\s*:\s*"([^"]+)"/);
    if (m && m[1]) {
        var u = m[1].replace(/^function\/\d+\//, '');
        if (u.indexOf('http') === 0) return u;
    }
    m = html.match(/(https?:\/\/[^"'\s]+\/get_file\/[^"'\s]+\.mp4[^"'\s]*)/);
    if (m && m[1]) return m[1];
    return '';
}

export default {
    init,
    home,
    homeVod,
    category,
    detail,
    search,
    play
};
