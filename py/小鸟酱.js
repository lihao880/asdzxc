// 小鸟酱 - 客户端单文件源（影视+/海阔/TVBox/FongMi）
// 站点：https://xiaoniao3452575.buzz  （域名常换，永久入口 小鸟酱.xyz）
// 结构：静态 HTML，列表 article.card，详情 /video/info/{id}.html，播放 /video/play/{id}.html
// 播放：播放页 JSON-LD 里 contentUrl 直链 m3u8（可能 URL 编码）
//       ⚠ 直链 m3u8 有 Cloudflare 防盗链，裸请求 403，必须带 UA + Referer
// 分页：分类 /video/type/{tid}/{pg}.html ；搜索 /video/search/{kw}/n/{pg}.html
// 去重：列表按归一化标题去重（同片多 id 反复出现）

import cheerio from 'assets://js/lib/cheerio.min.js';

const HOST = 'https://xiaoniao3452575.buzz';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

function mylog(...args) {
    console.log('[小鸟酱]', ...args);
}

// 播放请求头（绕 CDN 防盗链）
function playHeaders() {
    return {
        'User-Agent': UA,
        'Referer': HOST + '/',
        'Origin': HOST
    };
}

async function getHtml(url) {
    try {
        const res = await req(url, {
            method: 'get',
            headers: {
                'User-Agent': UA,
                'Referer': HOST + '/'
            }
        });
        return (res && typeof res === 'object') ? (res.content || '') : (res || '');
    } catch (e) {
        mylog('getHtml err', url, e.message);
        return '';
    }
}

function full(u) {
    if (!u) return '';
    u = String(u).trim();
    if (u.indexOf('http') === 0) return u;
    if (u.charAt(0) !== '/') u = '/' + u;
    return HOST + u;
}

function isDirectVideoUrl(url) {
    return ['m3u', 'mp4'].some(item => (url + '').indexOf(item) > -1);
}

// 标题归一化：去空格/标点/常见后缀，用于判重
function normTitle(name) {
    if (!name) return '';
    let s = String(name);
    s = s.replace(/[\s\u3000]+/g, '');
    s = s.replace(/[.\-_,:：。，、·!！?？"'“”‘’()（）\[\]【】<>《》\/\\|~`@#$%^&*+=]/g, '');
    s = s.replace(/new$/i, '');
    s = s.replace(/[\s\u3000]+/g, '');
    return s;
}

function dedup(list) {
    const seen = {};
    const out = [];
    for (let i = 0; i < list.length; i++) {
        const it = list[i];
        const key = normTitle(it.vod_name) || ('id:' + String(it.vod_id || ''));
        if (!key || seen[key]) continue;
        seen[key] = 1;
        out.push(it);
    }
    return out;
}

function parseList(html) {
    const list = [];
    if (!html) return list;
    const $ = cheerio.load(html);
    $('article.card').each(function () {
        const a = $(this).find('a').first();
        if (!a || !a.attr('href')) return;
        const href = a.attr('href');
        if (href.indexOf('/video/info/') === -1) return;
        const title = a.attr('title') || a.text().trim();
        const img = $(this).find('img').first();
        let pic = img.attr('src') || img.attr('data-src') || img.attr('data-original') || '';
        let remarks = '';
        const txt = $(this).text().replace(/\s+/g, ' ').trim();
        const dateM = txt.match(/\d{4}-\d{2}-\d{2}/);
        if (dateM) remarks = dateM[0];
        const idM = href.match(/\/video\/info\/(\d+)\.html/);
        const vid = idM ? idM[1] : href;
        list.push({
            vod_id: String(vid),
            vod_name: title || '',
            vod_pic: full(pic),
            vod_remarks: remarks
        });
    });
    return list;
}

function parsePageCount(html) {
    if (!html) return 9999;
    const m = html.match(/当前\s*\d+\s*\/\s*(\d+)\s*页/);
    if (m) {
        const n = parseInt(m[1]);
        if (n > 0) return n;
    }
    return 9999;
}

async function init(cfg) {
    mylog('Spider Init Done');
}

async function home(filter) {
    try {
        const html = await getHtml(HOST + '/');
        const classList = [];
        const seen = {};
        if (html) {
            const $ = cheerio.load(html);
            $('nav.site-nav a.nav-item').each(function () {
                let href = $(this).attr('href') || '';
                const name = ($(this).attr('title') || $(this).text() || '').trim();
                if (!href || href.indexOf('/video/type/') === -1) return;
                const m = href.match(/\/video\/type\/(\d+)\.html/);
                if (!m) return;
                const tid = m[1];
                if (seen[tid] || !name) return;
                seen[tid] = 1;
                classList.push({ type_id: tid, type_pid: 0, type_name: name });
            });
        }
        if (classList.length === 0) {
            classList.push({ type_id: '913', type_pid: 0, type_name: '91精选' });
            classList.push({ type_id: '955', type_pid: 0, type_name: '热点专题' });
            classList.push({ type_id: '956', type_pid: 0, type_name: '国产传媒' });
            classList.push({ type_id: '441', type_pid: 0, type_name: '网曝黑料' });
            classList.push({ type_id: '822', type_pid: 0, type_name: '精品资源' });
        }
        mylog('home class count', classList.length);
        return JSON.stringify({ class: classList, filters: {} });
    } catch (e) {
        mylog('home err', e.message);
        return JSON.stringify({ class: [], filters: {} });
    }
}

async function homeVod() {
    try {
        const html = await getHtml(HOST + '/');
        let list = dedup(parseList(html));
        list = list.slice(0, 20);
        return JSON.stringify({ list: list });
    } catch (e) {
        mylog('homeVod err', e.message);
        return JSON.stringify({ list: [] });
    }
}

async function category(tid, pg, filter, extend) {
    try {
        pg = parseInt(pg) || 1;
        let url;
        if (pg <= 1) {
            url = HOST + '/video/type/' + tid + '.html';
        } else {
            url = HOST + '/video/type/' + tid + '/' + pg + '.html';
        }
        mylog('category url', url);
        const html = await getHtml(url);
        const list = dedup(parseList(html));
        return JSON.stringify({ list: list, pagecount: parsePageCount(html) });
    } catch (e) {
        mylog('category err', e.message);
        return JSON.stringify({ list: [], pagecount: 1 });
    }
}

async function detail(id) {
    try {
        const numMatch = String(id).match(/(\d+)/);
        const vid = numMatch ? numMatch[1] : String(id);
        const url = HOST + '/video/info/' + vid + '.html';
        mylog('detail url', url);
        const html = await getHtml(url);
        if (!html) return JSON.stringify({ list: [] });
        const $ = cheerio.load(html);

        let name = '';
        const h1 = $('h1').first();
        if (h1 && h1.text()) name = h1.text().trim();
        if (!name) {
            const t = $('title').text() || '';
            name = t.split(/[|｜]/)[0].trim();
        }

        let pic = '';
        const pimg = $('.detail-cover img, .detail img, img').first();
        if (pimg) pic = pimg.attr('src') || pimg.attr('data-src') || '';

        let actor = '', num = '', area = '', content = '', typeName = '';
        $('.meta-row').each(function () {
            const label = $(this).find('.meta-label').text().trim();
            const val = $(this).find('.meta-value').text().trim();
            if (label.indexOf('主演') > -1) actor = val;
            else if (label.indexOf('番号') > -1) num = val;
            else if (label.indexOf('片商') > -1) area = val;
            else if (label.indexOf('分类') > -1) typeName = val;
        });
        content = $('meta[name="description"]').attr('content') || '';

        const playUrl = '第1集$' + HOST + '/video/play/' + vid + '.html';
        const vod = {
            vod_id: String(vid),
            vod_name: name || '',
            vod_pic: full(pic),
            type_name: typeName || '',
            vod_year: num || '',
            vod_area: area || '',
            vod_lang: '',
            vod_director: '',
            vod_actor: actor || '',
            vod_content: content || '',
            vod_remarks: '',
            vod_play_from: '小鸟酱',
            vod_play_url: playUrl
        };
        return JSON.stringify({ list: [vod] });
    } catch (e) {
        mylog('detail err', e.message);
        return JSON.stringify({ list: [] });
    }
}

async function search(kw, quick, pg) {
    try {
        const page = parseInt(pg) || 1;
        const kwEnc = encodeURIComponent(kw);
        let url;
        if (page <= 1) {
            url = HOST + '/video/search/' + kwEnc + '.html';
        } else {
            url = HOST + '/video/search/' + kwEnc + '/n/' + page + '.html';
        }
        mylog('search url', url);
        const html = await getHtml(url);
        const raw = parseList(html);
        const list = dedup(raw);
        const pagecount = parsePageCount(html);
        mylog('search raw', raw.length, 'dedup', list.length, 'pagecount', pagecount);
        return JSON.stringify({ list: list, pagecount: pagecount });
    } catch (e) {
        mylog('search err', e.message);
        return JSON.stringify({ list: [], pagecount: 1 });
    }
}

function extractContentUrl(html) {
    if (!html) return '';
    let m = html.match(/"contentUrl"\s*:\s*"([^"]+)"/);
    if (!m) {
        m = html.match(/https?:\/\/[^"'\s\\]+\.m3u8[^"'\s\\]*/);
        if (m) return m[0].replace(/\\/g, '');
        return '';
    }
    let u = m[1];
    if (u.indexOf('%3A') > -1 || u.indexOf('%2F') > -1) {
        try { u = decodeURIComponent(u); } catch (e) { }
    }
    u = u.replace(/\\/g, '');
    return u;
}

async function play(flag, id, flags) {
    mylog('开始获取播放地址:', id);
    try {
        if (isDirectVideoUrl(id)) {
            // 直链也要带防盗链头
            return JSON.stringify({ parse: 0, url: id, header: playHeaders(), headers: playHeaders() });
        }
        let playUrl = String(id);
        if (playUrl.indexOf('http') !== 0) {
            const num = (playUrl.match(/(\d+)/) || [])[1] || playUrl;
            playUrl = HOST + '/video/play/' + num + '.html';
        } else if (playUrl.indexOf('/video/play/') === -1) {
            const num = (playUrl.match(/(\d+)/) || [])[1] || '';
            playUrl = HOST + '/video/play/' + num + '.html';
        }
        mylog('play page', playUrl);
        const html = await getHtml(playUrl);
        const realUrl = extractContentUrl(html);
        if (realUrl) {
            mylog('realUrl', realUrl);
            // 关键：带 header，否则 CDN 403
            return JSON.stringify({ parse: 0, url: realUrl, header: playHeaders(), headers: playHeaders() });
        }
        mylog('contentUrl 未取到，转交嗅探');
        return JSON.stringify({ parse: 1, url: playUrl, header: playHeaders(), headers: playHeaders() });
    } catch (e) {
        mylog('play失败:', e.message);
        return JSON.stringify({ parse: 1, url: id, header: playHeaders(), headers: playHeaders() });
    }
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