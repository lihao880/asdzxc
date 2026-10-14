// 夜社 - yeshex.com 影视+ 源插件
import cheerio from 'assets://js/lib/cheerio.min.js';

const HOST = 'https://yeshex.com';
const UA = 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36';

function mylog() {
    console.log('夜社', ...arguments);
}

// 自实现 base64
function _b64(str) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
    let output = '';
    str = String(str).replace(/[^A-Za-z0-9+/=]/g, '');
    for (let i = 0; i < str.length; i += 4) {
        const c1 = chars.indexOf(str.charAt(i));
        const c2 = chars.indexOf(str.charAt(i + 1));
        const c3 = chars.indexOf(str.charAt(i + 2));
        const c4 = chars.indexOf(str.charAt(i + 3));
        output += String.fromCharCode((c1 << 2) | (c2 >> 4));
        if (c3 !== 64) output += String.fromCharCode(((c2 & 15) << 4) | (c3 >> 2));
        if (c4 !== 64) output += String.fromCharCode(((c3 & 3) << 6) | c4);
    }
    return output;
}

// latin1 字节串 → UTF-8 字符串
function _utf8(str) {
    try {
        var out = '';
        for (var i = 0; i < str.length; i++) {
            var c = str.charCodeAt(i);
            if (c < 0x80) {
                out += String.fromCharCode(c);
            } else if (c >= 0xC0 && c < 0xE0) {
                out += String.fromCharCode(((c & 0x1F) << 6) | (str.charCodeAt(++i) & 0x3F));
            } else if (c >= 0xE0 && c < 0xF0) {
                out += String.fromCharCode(((c & 0x0F) << 12) | ((str.charCodeAt(++i) & 0x3F) << 6) | (str.charCodeAt(++i) & 0x3F));
            } else if (c >= 0xF0) {
                var cp = ((c & 0x07) << 18) | ((str.charCodeAt(++i) & 0x3F) << 12) | ((str.charCodeAt(++i) & 0x3F) << 6) | (str.charCodeAt(++i) & 0x3F);
                cp -= 0x10000;
                out += String.fromCharCode(0xD800 + (cp >> 10), 0xDC00 + (cp & 0x3FF));
            } else {
                out += String.fromCharCode(c);
            }
        }
        return out;
    } catch (e) {
        return str;
    }
}

// 全站响应体 Base64 + document.write 混淆，统一解码
function dec(raw) {
    if (!raw) return '';
    const m = (raw + '').match(/var\s+a\s*=\s*"([^"]+)"/);
    if (!m) return raw;
    try {
        let src = m[1];
        let b;
        if (typeof base64Decode === 'function') {
            b = base64Decode(src);
        } else if (typeof atob === 'function') {
            b = atob(src);
        } else {
            b = _b64(src);
        }
        b = _utf8(b);
        b = b.replace(/\\\//g, '/').replace(/\\"/g, '"').replace(/\\\\/g, '\\');
        b = b.replace(/\\u([0-9a-fA-F]{4})/g, (x, c) => String.fromCharCode(parseInt(c, 16)));
        return b;
    } catch (e) {
        return raw;
    }
}

function full(u) {
    if (!u) return u;
    if (u.indexOf('http') === 0) return u;
    if (u.charAt(0) === '/') return HOST + u;
    return HOST + '/' + u;
}

async function get(url) {
    const resp = await req(url, {
        method: 'get',
        headers: {
            'User-Agent': UA,
            'Referer': HOST + '/'
        }
    });
    const raw = (resp && typeof resp === 'object') ? resp.content : resp;
    return dec(raw);
}

// 列表解析
function parseList(html) {
    const $ = cheerio.load(html);
    const list = [];
    $('a.module-poster-item').each((i, el) => {
        const $el = $(el);
        const href = $el.attr('href') || '';
        if (!href) return;
        if (href.indexOf('/play/') === -1 && href.indexOf('/detail/') === -1 && href.indexOf('/novel/') === -1) return;
        const name = $el.attr('title') || $el.find('.module-poster-item-title').text().trim();
        const pic = $el.find('img').attr('src') || $el.find('img').attr('data-src') || '';
        const remark = $el.find('.module-item-pic .time').text().trim();
        if (name) {
            list.push({ vod_id: href, vod_name: name, vod_pic: pic, vod_remarks: remark });
        }
    });
    return list;
}

const CLASS_NAMES = '国产视频&日本AV&欧美无码&AI短剧&擦边短剧&韩国BJ&同人作品&动画卡通&3D动漫&中文动漫&里番&泡面番&有声小说&淫词艳曲&激情骚麦&韩国H漫&日本H漫&3D漫画&秀人系列&网红COS&机构套图&内购私拍&AI绘图&各国套图&视频&动漫&有声&漫画&写真&小说'.split('&');
const CLASS_URLS = '11&12&14&13&36&35&7&8&10&9&32&33&15&16&17&18&19&31&20&22&21&23&34&24&2&1&3&4&5&novel'.split('&');

// 小说走 /ntype/N.html（子类 6/25-30），其余走 /type/N.html
const NTYPE_IDS = { '6': 1, '25': 1, '26': 1, '27': 1, '28': 1, '29': 1, '30': 1 };

// 把配置项归一化成带前缀的路径段：type/11 或 ntype/6
function toSeg(seg) {
    seg = String(seg);
    if (seg === 'novel') return 'ntype/6';
    if (seg.indexOf('/') > -1) return seg;
    if (/^\d+$/.test(seg)) return (NTYPE_IDS[seg] ? 'ntype/' : 'type/') + seg;
    return seg;
}

function buildClasses() {
    const out = [];
    for (let i = 0; i < CLASS_NAMES.length; i++) {
        out.push({ type_id: toSeg(CLASS_URLS[i]), type_pid: 0, type_name: CLASS_NAMES[i] });
    }
    return out;
}

// ========== 接口 ==========

async function init(ext) {}

async function home(filter) {
    try {
        return JSON.stringify({ class: buildClasses(), filters: {} });
    } catch (err) {
        mylog('home err', err.message);
        return JSON.stringify({ class: [], filters: {} });
    }
}

async function homeContent(filter) {
    try {
        const html = await get(HOST + '/');
        const list = parseList(html);
        return JSON.stringify({ class: buildClasses(), filters: {}, list });
    } catch (err) {
        mylog('homeContent err', err.message);
        return JSON.stringify({ class: buildClasses(), filters: {}, list: [] });
    }
}

async function homeVod() {
    try {
        const html = await get(HOST + '/');
        const list = parseList(html);
        return JSON.stringify({ list });
    } catch (err) {
        mylog('homeVod err', err.message);
        return JSON.stringify({ list: [] });
    }
}

async function category(tid, pg, ext, filters) {
    try {
        // 归一化为带前缀的路径段（兼容纯数字 / novel / type-ntype 已带前缀）
        let seg = toSeg(tid);
        const url = HOST + '/' + seg + '.html';
        // 该站分类为一次性全量加载，/type/N-2.html 会回同一页，故只取第一页
        const html = await get(url);
        const list = parseList(html);
        return JSON.stringify({ list, page: Number(pg) || 1, pagecount: 1, limit: list.length, total: list.length });
    } catch (err) {
        mylog('category err', err.message);
        return JSON.stringify({ list: [], page: 1, pagecount: 1, limit: 0, total: 0 });
    }
}

async function detail(ids) {
    try {
        const input = ids;
        const html = await get(full(input));
        const $ = cheerio.load(html);
        let vod = { vod_id: input };

        let title = $('title').text().split('-')[0].trim();
        if (title) vod.vod_name = title;

        let pm = html.match(/"vod_pic"\s*:\s*"([^"]+)"/);
        if (pm) vod.vod_pic = pm[1].replace(/\\\//g, '/');
        if (!vod.vod_pic) {
            const img = $('img').first().attr('src');
            if (img) vod.vod_pic = img;
        }

        // 小说
        if (input.indexOf('/novel/') > -1) {
            const eps = [];
            $('.chpterlist .list a.link').each((i, el) => {
                const $a = $(el);
                const href = $a.attr('href');
                const name = $a.text().replace(/\(\d+字\)/g, '').trim();
                if (href) eps.push(name + '$' + href);
            });
            vod.vod_play_from = '夜社小说';
            vod.vod_play_url = eps.join('#');
            return JSON.stringify({ list: [vod] });
        }

        // 漫画
        if (input.indexOf('/detail/') > -1) {
            const eps = [];
            $('.chpterlist .list a.link').each((i, el) => {
                const $a = $(el);
                const href = $a.attr('href');
                const name = $a.text().trim();
                if (href) eps.push(name + '$' + href);
            });
            vod.vod_play_from = '夜社漫画';
            vod.vod_play_url = eps.join('#');
            return JSON.stringify({ list: [vod] });
        }

        // 视频/写真/图集
        const pics = [];
        $('.module-player-pics-list img, .module-player-cartoon-list img').each((i, el) => {
            const u = $(el).attr('src') || $(el).attr('data-src');
            if (u && pics.indexOf(u) === -1) pics.push(u);
        });

        let cur = '';
        const um = html.match(/"url"\s*:\s*"(https?:\/\/[^"]+\.(?:m3u8|mp4)[^"]*)"/);
        if (um) cur = um[1].replace(/\\\//g, '/');

        const eps = [];
        if (pics.length && !cur) {
            // 写真/漫画图集
            eps.push('图集$pics://' + pics.join('&&'));
        } else {
            // 视频：优先用集数列表（/play/ID/1/N.html），交由 play 逐集解析直链
            $('.chpterlist .list a.link').each((i, el) => {
                const $a = $(el);
                const href = $a.attr('href');
                const nm = $a.text().trim();
                if (href && href.indexOf('/play/') > -1) eps.push(nm + '$' + href);
            });
            if (!eps.length) {
                if (cur) eps.push('正片$' + cur);
                else eps.push('正片$' + full(input));
            }
        }
        vod.vod_play_from = '夜社';
        vod.vod_play_url = eps.join('#');
        return JSON.stringify({ list: [vod] });
    } catch (err) {
        mylog('detail err', err.message);
        return JSON.stringify({ list: [] });
    }
}

async function search(wd, quick, pg) {
    try {
        // 搜索翻页无效（-2 返回空），仅取第一页
        const url = HOST + '/vod/search/wd/' + encodeURIComponent(wd) + '.html';
        const html = await get(url);
        const list = parseList(html);
        return JSON.stringify({ list, page: 1, pagecount: 1, limit: list.length, total: list.length });
    } catch (err) {
        mylog('search err', err.message);
        return JSON.stringify({ list: [], page: 1, pagecount: 1, limit: 0, total: 0 });
    }
}

async function play(flag, id, flags) {
    try {
        if (id.indexOf('pics://') > -1) {
            return JSON.stringify({ parse: 0, url: id });
        }
        if (id.indexOf('novel://') > -1) {
            return JSON.stringify({ parse: 0, url: id });
        }
        if (id.indexOf('.m3u8') > -1 || id.indexOf('.mp4') > -1) {
            return JSON.stringify({ parse: 0, url: id, header: { 'User-Agent': UA, 'Referer': HOST + '/' } });
        }
        if (/\.(jpg|jpeg|png|webp)$/i.test(id)) {
            return JSON.stringify({ parse: 0, url: 'pics://' + id });
        }

        if (id.indexOf('/nchpter/') > -1 || id.indexOf('/play/') > -1 || id.indexOf('/detail/') > -1) {
            const html = await get(full(id));
            const $ = cheerio.load(html);

            // 小说正文
            if (id.indexOf('/nchpter/') > -1) {
                let title = $('.module-novel-detail .title').text().trim() || '正文';
                const paras = [];
                $('.module-novel-detail .content p').each((i, el) => {
                    const t = $(el).text().trim();
                    if (t) paras.push(t);
                });
                if (!paras.length) {
                    const txt = $('.module-novel-detail .content').text().trim();
                    if (txt) paras.push(txt);
                }
                const content = paras.join('\n');
                const ret = JSON.stringify({ title: title, content: content });
                return JSON.stringify({ parse: 0, url: 'novel://' + ret });
            }

            // 视频直链（player_aaaa.url）
            const um = html.match(/"url"\s*:\s*"(https?:\/\/[^"]+\.(?:m3u8|mp4)[^"]*)"/);
            if (um) {
                return JSON.stringify({ parse: 0, url: um[1].replace(/\\\//g, '/'), header: { 'User-Agent': UA, 'Referer': HOST + '/' } });
            }

            // 图片流
            const pics = [];
            $('.module-player-pics-list img, .module-player-cartoon-list img').each((i, el) => {
                const u = $(el).attr('src') || $(el).attr('data-src');
                if (u && pics.indexOf(u) === -1) pics.push(u);
            });
            if (pics.length) {
                return JSON.stringify({ parse: 0, url: 'pics://' + pics.join('&&') });
            }
        }

        return JSON.stringify({ parse: 1, url: id });
    } catch (err) {
        mylog('play err', err.message);
        return JSON.stringify({ parse: 1, url: id });
    }
}

export default {
    init,
    home,
    homeVod,
    homeContent,
    category,
    detail,
    play,
    search
};