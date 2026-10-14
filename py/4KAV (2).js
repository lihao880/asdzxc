import { load } from 'assets://js/lib/cat.js';

let HOST = 'https://4k-av.com';
let siteKey = '', siteType = '', sourceKey = '', ext = '';

/* ==================== 性能参数（按需微调） ==================== */
const CFG = {
    timeout: 3000,          // 单次请求超时(ms)，失败快速重试而不是干等
    retry: 1,               // 超时/空响应重试次数
    retryDelay: 120,        // 重试间隔(ms)
    homeTTL: 5 * 60 * 1000, // 首页缓存有效期
    listTTL: 5 * 60 * 1000, // 分类/搜索结果缓存有效期
    pageTTL: 30 * 60 * 1000,// 总页数缓存有效期
    playTTL: 30 * 60 * 1000,// 播放地址缓存有效期
    listMax: 80,            // 列表缓存条目上限(LRU)
    playMax: 300,           // 播放缓存条目上限(LRU)
    prefetchNext: true,     // 预取下一页（翻页几乎零等待）
    prefetchPlay: true,     // 详情页预解析播放地址（点播零请求）
    preferM3U8: true        // 同时存在 mp4/m3u8 时优先 m3u8（起播更快、不卡）
};

const COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
};
let BASE_HEADERS = { ...COMMON_HEADERS, Referer: HOST + '/' };

/* ==================== 缓存（带 TTL + LRU，防内存膨胀） ==================== */
const PLAY_CACHE = new Map();
const LIST_CACHE = new Map();
const PAGE_CACHE = new Map();
const HOME_CACHE = { t: 0, v: '' };
const INFLIGHT = new Map(); // 同 URL 并发去重

const now = () => Date.now();
const sleep = ms => new Promise(r => setTimeout(r, ms));

function clearCache() {
    PLAY_CACHE.clear(); LIST_CACHE.clear(); PAGE_CACHE.clear();
    HOME_CACHE.t = 0; HOME_CACHE.v = ''; INFLIGHT.clear();
}
function trim(map, max) {
    if (map.size <= max) return;
    const arr = [];
    map.forEach((v, k) => arr.push([k, v.t]));
    arr.sort((a, b) => a[1] - b[1]);
    for (let i = 0; i < map.size - max; i++) map.delete(arr[i][0]);
}
function getCache(map, key, ttl) {
    const it = map.get(key);
    if (!it) return null;
    if (ttl && now() - it.t > ttl) { map.delete(key); return null; }
    return it.v;
}
function setCache(map, key, val, max) {
    map.set(key, { t: now(), v: val });
    trim(map, max);
}

/* ==================== 网络层：超时重试 + 并发去重 ==================== */
async function doRequest(url, ref, retry) {
    const headers = ref ? { ...BASE_HEADERS, Referer: ref } : BASE_HEADERS;
    for (let i = 0; i <= retry; i++) {
        try {
            const res = await req(url, { method: 'get', headers, timeout: CFG.timeout });
            const content = (res && res.content) || '';
            if (content) return { content };
        } catch (e) { /* 超时/异常继续重试 */ }
        if (i < retry) await sleep(CFG.retryDelay);
    }
    return { content: '' };
}
async function request(url, ref, retry = CFG.retry) {
    if (!url) return { content: '' };
    const hit = INFLIGHT.get(url);
    if (hit) return hit;               // 同一 URL 并发只发一次请求
    const p = doRequest(url, ref, retry);
    INFLIGHT.set(url, p);
    try { return await p; } finally { INFLIGHT.delete(url); }
}

/* ==================== HTML 预处理：砍掉无用内容，加速解析 ==================== */
function shrink(html, keys) {
    let s = -1;
    for (let i = 0; i < keys.length; i++) {
        const p = html.indexOf(keys[i]);
        if (p >= 0 && (s < 0 || p < s)) s = p;
    }
    return s < 0 ? html : html.slice(Math.max(0, s - 500)); // 去掉冗长的 head/meta
}
function stripScripts(html) {
    return html
        .replace(/<script[\s\S]*?<\/script>/gi, '')
        .replace(/<style[\s\S]*?<\/style>/gi, '');
}
function prepareList(html) {
    return stripScripts(shrink(html, ['NTMitem']));
}
function prepareDetail(html) {
    return stripScripts(shrink(html, ['MainContent', 'MainTitle', 'tophead']));
}

function joinUrl(url) {
    if (!url) return '';
    if (url.startsWith('http')) return url;
    if (url.startsWith('//')) return 'https:' + url;
    if (url.startsWith('/')) return HOST + url;
    return HOST + '/' + url;
}
function cleanText(s) {
    return (s || '').replace(/[\r\n\t]+/g, ' ').replace(/\s+/g, ' ').trim();
}

/* ==================== 播放地址解析 ==================== */
const QUALITIES = ['4K', '2160P', '1440P', '1080P', '720P', '480P', '360P'];
function matchAll(re, str) {
    const out = [];
    const r = new RegExp(re.source, re.flags.indexOf('g') >= 0 ? re.flags : re.flags + 'g');
    let m;
    while ((m = r.exec(str))) { out.push(m); if (m.index === r.lastIndex) r.lastIndex++; }
    return out;
}
function extractPlayUrls(html) {
    if (!html) return [];
    const out = [];
    const push = u => {
        const s = (u || '').trim();
        if (!s) return;
        if (!/\.(m3u8|mp4)(\?|#|$)/i.test(s)) return;
        if (/ad|ads|advert|poster|preview|logo/i.test(s)) return; // 排除广告/预览
        if (out.indexOf(s) < 0) out.push(s);
    };
    // 1) <video><source src>（最可靠，优先）
    matchAll(/<source[^>]+src=["']([^"']+)["']/gi, html).forEach(m => push(m[1]));
    // 2) JS 变量/JSON 里的地址
    matchAll(/["'](?:url|file|src|playurl|videourl|m3u8|hls)["']\s*[:=]\s*["']([^"']+\.(?:m3u8|mp4)[^"']*)["']/gi, html).forEach(m => push(m[1]));
    // 3) 兜底：正文里的直链
    matchAll(/https?:\/\/[^"'\\\s<>]+\.(?:m3u8|mp4)(?:\?[^"'\\\s<>]*)?/gi, html).forEach(m => push(m[0]));
    matchAll(/["'](\/[^"'\\\s<>]+\.(?:m3u8|mp4)(?:\?[^"'\\\s<>]*)?)["']/gi, html).forEach(m => push(m[1]));
    return out;
}
function pickSource(list) {
    if (!list || !list.length) return '';
    if (CFG.preferM3U8) {
        const m = list.find(u => /\.m3u8(\?|#|$)/i.test(u));
        if (m) return m;
    }
    return list[0];
}
function extractPlayUrl(html) {
    return pickSource(extractPlayUrls(html));
}
function normalizeQuality(q) {
    if (!q) return '';
    const u = ('' + q).toUpperCase();
    if (/^(4K|2160P|1440P|1080P|720P|480P|360P)$/.test(u)) return u;
    return '';
}
function swapQuality(m3u8, target) {
    const t = normalizeQuality(target);
    if (!m3u8 || !t) return m3u8;
    // 形态一：/1080P/index.m3u8
    let out = m3u8.replace(/\/(4K|2160P|1440P|1080P|720P|480P|360P)\/([^\/?#]+\.m3u8)(?=$|[?#])/i, '/' + t + '/$2');
    // 形态二：文件名里带清晰度，xxx_1080P.mp4 / xxx.1080p.m3u8
    if (out === m3u8) {
        out = m3u8.replace(/(4K|2160P|1440P|1080P|720P|480P|360P)(?=[^\/]*\.(?:m3u8|mp4))/i, t);
    }
    return out;
}
function seedPlayCache(id, base) {
    if (!base) return;
    setCache(PLAY_CACHE, 'default|' + id, base, CFG.playMax);
    for (let i = 0; i < QUALITIES.length; i++) {   // 一次解析，预生成所有清晰度直链
        const u = swapQuality(base, QUALITIES[i]);
        if (u && u !== base) setCache(PLAY_CACHE, QUALITIES[i] + '|' + id, u, CFG.playMax);
    }
}
function findPlay(id, q) {
    const key = (q || 'default') + '|' + id;
    const direct = getCache(PLAY_CACHE, key, CFG.playTTL);
    if (direct) return direct;
    let base = getCache(PLAY_CACHE, 'default|' + id, CFG.playTTL);
    if (!base) {  // 用同 id 的任一清晰度反推，避免重复请求
        PLAY_CACHE.forEach((it, k) => {
            if (!base && k.endsWith('|' + id) && now() - it.t <= CFG.playTTL) base = it.v;
        });
    }
    if (!base) return '';
    const v = q ? swapQuality(base, q) : base;
    if (v) setCache(PLAY_CACHE, key, v, CFG.playMax);
    return v;
}
function prefetchPlayUrl(u) {   // 详情页后台预取首集，点播零等待
    if (!CFG.prefetchPlay || !u) return;
    if (PLAY_CACHE.has('default|' + u)) return;
    request(u, HOST + '/').then(res => {
        const pu = extractPlayUrl(res.content || '');
        if (pu) seedPlayCache(u, joinUrl(pu));
    }).catch(() => {});
}

/* ==================== 列表解析 ==================== */
function parseVodList(html) {
    const $ = load(html);
    const list = [];
    const seen = {};
    $('.NTMitem').each((_, el) => {
        const item = $(el);
        const titleA = item.find('.title a').first();
        let href = titleA.attr('href') || '';
        if (!href) href = item.find('.poster a').first().attr('href') || '';
        if (!href) return;
        let name = cleanText(titleA.find('h2').text() || titleA.attr('title') || '');
        if (!name) name = cleanText(item.find('.poster img').attr('alt') || '');
        if (!name) return;
        const img = item.find('.poster img').first();
        // 兼容懒加载，且不再因图片缺失丢整条数据
        const pic = img.attr('src') || img.attr('data-src') || img.attr('data-original') ||
            img.attr('data-lazy-src') || img.attr('data-echo') || '';
        if (seen[href]) return;
        seen[href] = 1;
        list.push({
            vod_id: href,
            vod_name: name,
            vod_pic: joinUrl(pic),
            vod_remarks: cleanText(item.find('.resyear label[title="分辨率"]').first().text()),
            vod_year: cleanText(item.find('.resyear label[title="年份"]').first().text())
        });
    });
    return list;
}
function getPageTotal(html) {
    let m = (html || '').match(/页次\s*\d+\s*\/\s*(\d+)/);
    if (m) return parseInt(m[1]);
    m = (html || '').match(/[^\d](\d+)\s*页/g);
    if (m && m.length) {
        let mx = 1;
        m.forEach(s => { const n = parseInt(s.replace(/\D/g, '')); if (n > mx) mx = n; });
        if (mx > 1) return mx;
    }
    let max = 1, x;
    const re = /page-(\d+)\.html/g;   // 兜底：从分页链接推断总页数
    while ((x = re.exec(html || ''))) { const n = parseInt(x[1]); if (n > max) max = n; }
    return max;
}
function getTotalCount(html) {
    let m = (html || '').match(/(\d+)\s*条搜索结果/);
    if (m) return parseInt(m[1]);
    m = (html || '').match(/(\d+)\s*个视频/);
    if (m) return parseInt(m[1]);
    return 0;
}
function parsePage(html) {
    const list = parseVodList(prepareList(html));
    return { list: list, pagecount: getPageTotal(html), totalCount: getTotalCount(html) };
}
function emptyResult(pg, pagecount) {
    return JSON.stringify({ page: pg, pagecount: pagecount || 0, limit: 0, total: 0, list: [] });
}
function pageUrl(base, pg, total, isSearch) {
    if (pg <= 1) return base;
    const p = total - pg + 1;
    if (p < 1 || p > total) return '';
    if (p === 1) return base;
    return isSearch ? base + '&page=' + p : base + 'page-' + p + '.html';
}
function prefetchPage(url) {   // 预取下一页
    if (!CFG.prefetchNext || !url || LIST_CACHE.has(url)) return;
    request(url, HOST + '/').then(res => {
        const html = res.content || '';
        if (html) setCache(LIST_CACHE, url, parsePage(html), CFG.listMax);
    }).catch(() => {});
}
function buildBase(tid, extend) {
    if (extend.year) return HOST + '/' + encodeURIComponent(extend.year) + '/';
    if (extend.tag) return HOST + '/tag/' + encodeURIComponent(extend.tag) + '/';
    return HOST + '/' + tid + '/';
}

/* ==================== 接口实现 ==================== */
function init(cfg) {
    siteKey = cfg.skey;
    siteType = cfg.stype;
    sourceKey = cfg.sourceKey;
    ext = cfg.ext || '';
    const old = HOST;
    if (ext && ext.startsWith('http')) HOST = ext.replace(/\/$/, '');
    if (HOST !== old) clearCache();          // 域名变更，旧缓存全部失效
    BASE_HEADERS = { ...COMMON_HEADERS, Referer: HOST + '/' };
}

async function home(filter) {
    const classes = [
        { type_id: 'tv', type_name: '电视剧' },
        { type_id: 'movie', type_name: '电影' }
    ];
    const yearValue = [{ n: '全部', v: '' }];
    ['2026', '2025', '2024', '2023', '2022', '2021', '2020', '2019'].forEach(y => yearValue.push({ n: y, v: y }));
    const tagValue = [{ n: '全部', v: '' }];
    ['动作', '剧情', '冒险', '喜剧', '国产剧', '恐怖', '战争', '科幻', '动画', '韩剧', '犯罪', '纪录片'].forEach(t => tagValue.push({ n: t, v: t }));
    const filterObj = [
        { key: 'year', name: '年份', value: yearValue },
        { key: 'tag', name: '类型', value: tagValue }
    ];
    return JSON.stringify({ class: classes, filters: { tv: filterObj, movie: filterObj, av: filterObj } });
}

async function homeVod() {
    try {
        if (HOME_CACHE.v && now() - HOME_CACHE.t < CFG.homeTTL) return HOME_CACHE.v;
        const res = await request(HOST + '/');
        const html = res.content || '';
        const result = JSON.stringify({ list: parseVodList(prepareList(html)) });
        if (html) { HOME_CACHE.t = now(); HOME_CACHE.v = result; }
        return result;
    } catch (e) {
        return JSON.stringify({ list: [] });
    }
}

async function category(tid, pg, filter, extend) {
    pg = parseInt(pg) || 1;
    extend = extend || {};
    const base = buildBase(tid, extend);
    try {
        let total = getCache(PAGE_CACHE, base, CFG.pageTTL) || 0;
        if (!total) {   // 顺带把第一页缓存下来
            const first = await request(base, HOST + '/');
            const fh = first.content || '';
            if (fh) {
                total = getPageTotal(fh);
                if (total) setCache(PAGE_CACHE, base, total, 200);
                setCache(LIST_CACHE, base, parsePage(fh), CFG.listMax);
            }
        }
        const url = pageUrl(base, pg, total, false);
        if (!url) return emptyResult(pg, total);
        let data = getCache(LIST_CACHE, url, CFG.listTTL);
        if (!data) {
            const res = await request(url, HOST + '/');
            const html = res.content || '';
            data = html ? parsePage(html) : { list: [], pagecount: total, totalCount: 0 };
            if (html) setCache(LIST_CACHE, url, data, CFG.listMax);
        }
        const pagecount = data.pagecount || total || 1;
        const totalCount = data.totalCount || pagecount * data.list.length;
        prefetchPage(pageUrl(base, pg + 1, pagecount, false));
        return JSON.stringify({ page: pg, pagecount: pagecount, limit: data.list.length, total: totalCount, list: data.list });
    } catch (e) {
        return emptyResult(pg, 0);
    }
}

async function detail(id) {
    try {
        const url = joinUrl(id);
        const res = await request(url, HOST + '/');
        const raw = res.content || '';
        const html = prepareDetail(raw);
        const $ = load(html);
        const name = cleanText($('.MainTitle').first().text()) || cleanText($('#tophead h1').first().text()) || '';
        let pic = $('#MainContent_poster img').first().attr('src') || $('.poster img').first().attr('src') || '';
        pic = joinUrl(pic);
        let content = '';
        $('#MainContent_videodesc .cnline').each((_, p) => { content += $(p).text().trim() + '\n'; });
        content = cleanText(content);
        if (!content) content = cleanText($('.videodesc').first().text());
        const typeArr = [];
        $('#MainContent_tags a').each((_, a) => { typeArr.push(cleanText($(a).text())); });
        let year = '', resolution = '', duration = '';
        $('#MainContent_videodetail span').each((_, s) => {
            const t = cleanText($(s).text());
            const ym = t.match(/年份[:：]?\s*(\d{4})/);
            if (ym) year = ym[1];
            const rm = t.match(/分辨率[:：]?\s*(.+)/);
            if (rm) resolution = rm[1].trim();
            const dm = t.match(/片长[:：]?\s*(.+)/);
            if (dm) duration = dm[1].trim();
        });
        const vod = {
            vod_id: id,
            vod_name: name,
            vod_pic: pic,
            vod_content: content,
            vod_type: typeArr.join('/'),
            vod_year: year,
            vod_remarks: resolution
        };
        const eps = [];
        $('#MainContent_reletv .screenshot, #rtlist .screenshot').each((_, el) => {
            const box = $(el);
            const a = box.find('a').first();
            let epName = '', epHref = '';
            if (a.length) {
                epHref = a.attr('href') || '';
                epName = a.find('span').first().text().trim() || a.attr('title') || '';
            } else {
                epHref = id;
                epName = box.find('span').first().text().trim();
            }
            epName = cleanText(epName);
            if (epHref && epName) eps.push({ name: epName, id: epHref });
        });
        const qualities = [];
        const s = (resolution || '').toUpperCase();
        ['4K', '1080P', '720P', '480P', '360P'].forEach(q => { if (s.includes(q)) qualities.push(q); });

        // 关键提速：复用详情页已下载的 HTML 解析播放地址，点播不再二次请求
        if (CFG.prefetchPlay) {
            const pu = extractPlayUrl(raw);
            if (pu) seedPlayCache(id, joinUrl(pu));
            else if (eps.length) prefetchPlayUrl(joinUrl(eps[0].id));
        }

        const playFrom = [];
        const playUrls = [];
        const singleLine = eps.length > 0 ? eps.map(e => e.name + '$' + e.id).join('#') : '正片$' + id;
        if (qualities.length > 0) {
            qualities.forEach(q => { playFrom.push(q); playUrls.push(singleLine); });
        } else {
            playFrom.push('高清');
            playUrls.push(singleLine);
        }
        vod.vod_play_from = playFrom.join('$$$');
        vod.vod_play_url = playUrls.join('$$$');
        return JSON.stringify({ list: [vod] });
    } catch (e) {
        return JSON.stringify({ list: [] });
    }
}

async function search(wd, quick, pg) {
    pg = parseInt(pg) || 1;
    if (!wd) return emptyResult(pg, 0);
    const base = HOST + '/s?y=' + encodeURIComponent(wd);
    try {
        let total = getCache(PAGE_CACHE, base, CFG.pageTTL) || 0;
        if (!total) {
            const first = await request(base, HOST + '/');
            const fh = first.content || '';
            if (fh) {
                total = getPageTotal(fh);
                if (total) setCache(PAGE_CACHE, base, total, 200);
                setCache(LIST_CACHE, base, parsePage(fh), CFG.listMax);
            }
        }
        const url = pageUrl(base, pg, total, true);
        if (!url) return emptyResult(pg, total);
        let data = getCache(LIST_CACHE, url, CFG.listTTL);
        if (!data) {
            const res = await request(url, HOST + '/');
            const html = res.content || '';
            data = html ? parsePage(html) : { list: [], pagecount: total, totalCount: 0 };
            if (html) setCache(LIST_CACHE, url, data, CFG.listMax);
        }
        const pagecount = data.pagecount || total || 1;
        const totalCount = data.totalCount || pagecount * data.list.length;
        prefetchPage(pageUrl(base, pg + 1, pagecount, true));
        return JSON.stringify({ page: pg, pagecount: pagecount, limit: data.list.length, total: totalCount, list: data.list });
    } catch (e) {
        return emptyResult(pg, 0);
    }
}

async function play(flag, id, flags) {
    try {
        const targetQ = normalizeQuality(flag);
        const url = joinUrl(id);
        const cached = findPlay(id, targetQ);   // 命中缓存：零请求直接出流
        if (cached) {
            return JSON.stringify({
                parse: 0,
                url: cached,
                header: { 'User-Agent': COMMON_HEADERS['User-Agent'], 'Referer': url }
            });
        }
        const res = await request(url, HOST + '/');
        const html = res.content || '';
        let playUrl = joinUrl(extractPlayUrl(html));
        if (playUrl) seedPlayCache(id, playUrl);
        if (targetQ) playUrl = findPlay(id, targetQ) || swapQuality(playUrl, targetQ);
        if (playUrl && /\.m3u8|\.mp4/i.test(playUrl)) {
            return JSON.stringify({
                parse: 0,
                url: playUrl,
                header: { 'User-Agent': COMMON_HEADERS['User-Agent'], 'Referer': url }
            });
        }
        return JSON.stringify({
            parse: 1,
            url: playUrl || url,
            header: { 'User-Agent': COMMON_HEADERS['User-Agent'] }
        });
    } catch (e) {
        return JSON.stringify({ parse: 1, url: joinUrl(id) });
    }
}

export function __jsEvalReturn() {
    return { init, home, homeVod, category, detail, search, play };
}
