"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: 'SupJav',
  lang: 'hipy',
})
"""

import sys
import os
import copy
import requests
import json
import re
import base64
import threading
import urllib3
import urllib.parse
from urllib.parse import quote, unquote, urljoin, urlsplit
from bs4 import BeautifulSoup

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from base.spider import Spider as BaseSpider


class _CompatLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class Spider(BaseSpider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ext = ''
        self.t4_api = kwargs.get('t4_api', '')
        self.host = 'https://supjav.com'
        self.pic_proxy = ''
        self.m3u8_proxy = ''
        self.one_mark = 'Android原生WebView弹窗'
        self._handler = None
        self._cf_dialog = None
        self._cf_webview = None
        self._cf_listener = None
        self._cf_webview_client = None
        self._cf_ui_task = None
        self._cf_poll_task = None
        self._cf_wait = None
        self._cf_cookie = ''
        self._cf_ua = ''
        self._cf_final_url = ''
        self._cf_html = ''
        self._cf_value_callback = None
        try:
            self._cf_lock = threading.Lock()
        except Exception as e:
            self._cf_lock = _CompatLock()
            print('[SupJav] 当前壳不支持原生线程锁，已启用兼容模式: %s' % e)
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            base_dir = '/storage/emulated/0/tvbox/sites-py'
        self._cf_session_file = os.path.join(base_dir, '.supjav_webview_session.json')
        self.classes = [
            {"type_id": "zh", "type_name": "最新中文"},
            {"type_id": "zh/popular", "type_name": "热门"},
            {"type_id": "zh/category/censored-jav", "type_name": "有码"},
            {"type_id": "zh/category/uncensored-jav", "type_name": "无码"},
            {"type_id": "zh/category/amateur", "type_name": "素人"},
            {"type_id": "zh/category/chinese-subtitles", "type_name": "中文字幕"},
            {"type_id": "zh/category/reducing-mosaic", "type_name": "无码破解"},
            {"type_id": "zh/category/english-subtitles", "type_name": "英文字幕"}
        ]
        self.filters = {}
        self.headers = {
            'User-Agent': ('Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 '
                           '(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36'),
            'Referer': self.host + '/',
            'Origin': self.host
        }
        self.session = requests.Session()
        try:
            adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20)
            self.session.mount('http://', adapter)
            self.session.mount('https://', adapter)
        except Exception as e:
            print('[SupJav] 当前壳不支持自定义连接池，使用默认Session: %s' % e)
        self._load_cf_session()

    def _load_cf_session(self):
        try:
            if not os.path.isfile(self._cf_session_file):
                return
            with open(self._cf_session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            self._cf_cookie = str(data.get('cookie') or '')
            self._cf_ua = str(data.get('ua') or '')
            if self._cf_ua:
                self.headers['User-Agent'] = self._cf_ua
            print('[SupJav] 已载入WebView会话: cookie=%s' % bool(self._cf_cookie))
        except Exception as e:
            print('[SupJav] WebView会话读取失败: %s' % e)

    def _save_cf_session(self):
        if not self._cf_cookie:
            return
        try:
            data = {'cookie': self._cf_cookie, 'ua': self._cf_ua, 'host': self.host}
            tmp = self._cf_session_file + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
            os.replace(tmp, self._cf_session_file)
            print('[SupJav] WebView会话已持久化')
        except Exception as e:
            print('[SupJav] WebView会话保存失败: %s' % e)

    def init(self, extend=""):
        raw = getattr(self, 'ext', '') or extend or ''
        self.ext = raw
        if isinstance(raw, dict):
            config = raw
        else:
            try:
                config = json.loads(raw) if str(raw).strip() else {}
                if not isinstance(config, dict):
                    config = {}
            except Exception:
                config = {}
        self.host = str(config.get('site') or self.host).rstrip('/')
        self.headers['Referer'] = self.host + '/'
        self.headers['Origin'] = self.host
        try:
            from android.os import Handler, Looper
            self._handler = Handler(Looper.getMainLooper())
        except Exception:
            self._handler = None

    def getName(self):
        return "SupJav"

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        self.ext = extend or ''
        return None

    def homeLayout(self):
        return 0

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(?:m3u8|mp4|flv)(?:$|[?#])', str(url or ''), re.I))

    def manualVideoCheck(self):
        return False

    def action(self, action_name, action_param=None):
        return f"当前过盾方式: {self.one_mark}"

    def _cf_activity(self):
        try:
            from java.lang import Class
            cls = Class.forName('android.app.ActivityThread')
            thread = cls.getMethod('currentActivityThread', None).invoke(None, None)
            field = cls.getDeclaredField('mActivities')
            field.setAccessible(True)
            for record in field.get(thread).values().toArray():
                try:
                    rc = record.getClass()
                    paused = rc.getDeclaredField('paused')
                    paused.setAccessible(True)
                    if paused.getBoolean(record):
                        continue
                    activity = rc.getDeclaredField('activity')
                    activity.setAccessible(True)
                    return activity.get(record)
                except Exception:
                    continue
        except Exception as e:
            print(f'[SupJav] 获取 Activity 失败: {e}')
        return None

    def _cf_run_ui(self, func):
        try:
            if self._handler is None:
                from android.os import Handler, Looper
                self._handler = Handler(Looper.getMainLooper())
            from java import dynamic_proxy
            from java.lang import Runnable
            outer = self
            class Task(dynamic_proxy(Runnable)):
                def run(self):
                    try:
                        func()
                    except Exception as e:
                        print(f'[SupJav] 验证 UI 异常: {e}')
                        if outer._cf_wait:
                            outer._cf_wait.set()
            task = Task()
            self._cf_ui_task = task
            self._handler.post(task)
            return True
        except Exception as e:
            print(f'[SupJav] UI 调度失败: {e}')
            return False

    def _cf_show_dialog(self, target_url):
        wait = threading.Event()
        self._cf_wait = wait
        self._cf_html = ''
        self._cf_final_url = target_url

        def build():
            try:
                from java import jclass, dynamic_proxy
                from java.lang import Runnable
                activity = self._cf_activity()
                if activity is None or activity.isFinishing():
                    wait.set()
                    return

                WebView = jclass('android.webkit.WebView')
                WebViewClient = jclass('android.webkit.WebViewClient')
                CookieManager = jclass('android.webkit.CookieManager')
                AlertDialog = jclass('android.app.AlertDialog')
                OnClick = jclass('android.content.DialogInterface$OnClickListener')
                ViewGroup = jclass('android.view.ViewGroup')
                ValueCallback = jclass('android.webkit.ValueCallback')

                outer = self
                manager = CookieManager.getInstance()
                manager.setAcceptCookie(True)
                if outer._cf_cookie:
                    for cookie_part in outer._cf_cookie.split(';'):
                        cookie_part = cookie_part.strip()
                        if '=' in cookie_part:
                            manager.setCookie(outer.host, cookie_part)
                            manager.setCookie(target_url, cookie_part)
                    manager.flush()
                web = WebView(activity)
                manager.setAcceptThirdPartyCookies(web, True)
                settings = web.getSettings()
                settings.setJavaScriptEnabled(True)
                settings.setDomStorageEnabled(True)
                settings.setDatabaseEnabled(True)
                settings.setLoadWithOverviewMode(True)
                settings.setUseWideViewPort(True)

                outer._cf_ua = str(settings.getUserAgentString() or '')
                client = WebViewClient()
                outer._cf_webview_client = client
                web.setWebViewClient(client)

                density = activity.getResources().getDisplayMetrics().density
                # 只保留验证所需的小型网页区域，避免站点首页把弹窗撑成近全屏。
                web.setLayoutParams(ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    int(180 * density + 0.5)
                ))

                state = {'done': False, 'ticks': 0, 'extracting': False, 'shown': False}
                # 先给 Cloudflare 自动挑战约 4 秒静默执行时间；需要人工交互时再显示。
                silent_ticks = 6
                dialog_ref = {'value': None}

                def finish(success):
                    if state['done']:
                        return
                    state['done'] = True
                    if success:
                        manager.flush()
                        try:
                            current_url = str(web.getUrl() or target_url)
                        except Exception:
                            current_url = target_url
                        outer._cf_final_url = current_url
                        cookie = (manager.getCookie(current_url)
                                  or manager.getCookie(target_url)
                                  or manager.getCookie(outer.host)
                                  or '')
                        outer._cf_cookie = str(cookie).strip()
                        outer._save_cf_session()
                        print('[SupJav] 已取得WebView真实HTML，自动返回壳端: %s | html=%s | cookie=%s' %
                              (current_url[:100], len(outer._cf_html), bool(cookie)))
                    try:
                        web.stopLoading()
                        web.destroy()
                    except Exception:
                        pass
                    dialog = dialog_ref['value']
                    if dialog is not None:
                        try:
                            dialog.dismiss()
                        except Exception:
                            pass
                    outer._cf_webview = None
                    outer._cf_dialog = None
                    outer._cf_listener = None
                    outer._cf_poll_task = None
                    outer._cf_value_callback = None
                    wait.set()

                def extract_html(force=False):
                    if state['done'] or state['extracting']:
                        return
                    state['extracting'] = True

                    class HtmlCallback(dynamic_proxy(ValueCallback)):
                        def onReceiveValue(self, value):
                            state['extracting'] = False
                            try:
                                raw = str(value or '')
                                html = json.loads(raw) if raw else ''
                                if not isinstance(html, str):
                                    html = str(html or '')
                                valid = (len(html) > 500
                                         and '<html' in html.lower()
                                         and not outer._is_cf_challenge(html))
                                if valid:
                                    outer._cf_html = html
                                    finish(True)
                                    return
                                if state['ticks'] >= silent_ticks:
                                    show_dialog()
                                if force:
                                    print('[SupJav] 当前仍是验证页，暂不关闭')
                            except Exception as e:
                                print('[SupJav] WebView HTML提取失败: %s' % e)

                    callback = HtmlCallback()
                    outer._cf_value_callback = callback
                    try:
                        web.evaluateJavascript(
                            '(function(){return document.documentElement.outerHTML;})()',
                            callback
                        )
                    except Exception as e:
                        state['extracting'] = False
                        print('[SupJav] evaluateJavascript失败: %s' % e)

                class Listener(dynamic_proxy(OnClick)):
                    def __init__(self, positive):
                        super().__init__()
                        self.positive = positive

                    def onClick(self, dialog, which):
                        if self.positive:
                            extract_html(True)
                        else:
                            finish(False)

                class Poll(dynamic_proxy(Runnable)):
                    def run(self):
                        if state['done']:
                            return
                        state['ticks'] += 1
                        # WebView 先在后台持续执行 JS 并抽取 DOM；自动挑战成功则始终不显示。
                        if state['ticks'] >= 2:
                            extract_html(False)
                        if not state['done'] and outer._handler is not None:
                            outer._handler.postDelayed(self, 700)

                positive = Listener(True)
                negative = Listener(False)
                poll = Poll()
                outer._cf_listener = (positive, negative)
                outer._cf_poll_task = poll

                builder = AlertDialog.Builder(activity)
                builder.setTitle('SupJav 验证（完成后自动关闭）')
                builder.setView(web)
                builder.setPositiveButton('完成', positive)
                builder.setNegativeButton('取消', negative)
                dialog = builder.create()
                dialog_ref['value'] = dialog
                dialog.setCanceledOnTouchOutside(False)

                def show_dialog():
                    if state['done'] or state['shown']:
                        return
                    state['shown'] = True
                    dialog.show()
                    try:
                        window = dialog.getWindow()
                        metrics = activity.getResources().getDisplayMetrics()
                        width = min(int(metrics.widthPixels * 0.82), int(380 * density + 0.5))
                        window.setLayout(width, ViewGroup.LayoutParams.WRAP_CONTENT)
                    except Exception as e:
                        print('[SupJav] 弹窗尺寸设置失败: %s' % e)
                    print('[SupJav] 后台自动验证未完成，需要人工验证')

                outer._cf_webview = web
                outer._cf_dialog = dialog
                # 在同一 WebView 环境静默加载；自动挑战成功则直接取 HTML，全程不显示。
                web.loadUrl(target_url)
                outer._handler.postDelayed(poll, 500)
            except Exception as e:
                print(f'[SupJav] 验证弹窗创建失败: {e}')
                wait.set()

        if not self._cf_run_ui(build):
            return ''
        if not wait.wait(180):
            print('[SupJav] 验证等待超时')
            def close_timeout():
                try:
                    if self._cf_dialog is not None:
                        self._cf_dialog.dismiss()
                    if self._cf_webview is not None:
                        self._cf_webview.stopLoading()
                        self._cf_webview.destroy()
                except Exception:
                    pass
                self._cf_dialog = None
                self._cf_webview = None
                self._cf_poll_task = None
            self._cf_run_ui(close_timeout)
        cookie = self._cf_cookie
        self._cf_wait = None
        if cookie:
            self.headers['Cookie'] = cookie
            if self._cf_ua:
                self.headers['User-Agent'] = self._cf_ua
            domains = {urllib.parse.urlsplit(self.host).hostname,
                       urllib.parse.urlsplit(target_url).hostname,
                       urllib.parse.urlsplit(self._cf_final_url).hostname}
            for part in cookie.split(';'):
                name, sep, value = part.strip().partition('=')
                if sep and name:
                    for domain in domains:
                        if domain:
                            self.session.cookies.set(name, value, domain=domain)
            print('[SupJav] WebView会话保留，后续页面优先静默加载')
        return self._cf_html

    def _is_cf_challenge(self, text):
        body = str(text or '').lower()
        marks = ('cf_chl', 'challenge-platform', 'cf-turnstile', 'just a moment',
                 'enable javascript and cookies to continue', 'checking your browser')
        return ('cloudflare' in body and any(x in body for x in marks)) or 'challenge-platform' in body

    def _fetch_html(self, url, session=None, custom_referer=None):
        target_url = url
        req_headers = copy.deepcopy(self.headers)
        if custom_referer:
            req_headers['Referer'] = custom_referer

        try:
            getter = session.get if session else self.session.get
            resp = getter(target_url, headers=req_headers, timeout=15, verify=False)
            text = resp.text or ''
            if resp.status_code == 200 and not self._is_cf_challenge(text):
                return text
            if resp.status_code in (403, 429, 503) or self._is_cf_challenge(text):
                with self._cf_lock:
                    # Cloudflare 将浏览器状态绑定到 WebView 指纹，requests 回放不可靠。
                    # 直接返回 WebView 运行后提取的真实 DOM。
                    web_html = self._cf_show_dialog(url)
                    if web_html and not self._is_cf_challenge(web_html):
                        return web_html
                    print('[SupJav] 未取得WebView真实HTML')
        except Exception as e:
            print(f"[SupJav Error] 请求异常，转WebView会话兜底: {e}")
            try:
                with self._cf_lock:
                    web_html = self._cf_show_dialog(url)
                if web_html and not self._is_cf_challenge(web_html):
                    return web_html
            except Exception as web_error:
                print('[SupJav] WebView兜底失败: %s' % web_error)
        return ""

    @staticmethod
    def _js_unescape(value):
        value = str(value or '').replace('\\/', '/')
        value = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), value)
        value = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), value)
        return value.replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')

    @staticmethod
    def _base_n(value, radix):
        chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        value, radix = int(value), int(radix)
        if value == 0:
            return '0'
        out = ''
        while value:
            out = chars[value % radix] + out
            value //= radix
        return out

    def _resolve_fst(self, html):
        packed = re.search(
            r"}\(\s*'(.+?)'\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*'(.+?)'\.split\(\s*'\|'\s*\)",
            str(html or ''), re.S)
        if not packed:
            return ''
        payload = self._js_unescape(packed.group(1))
        radix, count = int(packed.group(2)), int(packed.group(3))
        words = self._js_unescape(packed.group(4)).split('|')
        for i in range(count - 1, -1, -1):
            if i < len(words) and words[i]:
                payload = re.sub(r'\b' + re.escape(self._base_n(i, radix)) + r'\b', words[i], payload)
        clean = payload.replace('\\/', '/')
        for key in ('hls2', 'hls3', 'file'):
            pattern = r'''["']''' + key + r'''["']\s*:\s*["'](https?://[^"']+)'''
            match = re.search(pattern, clean, re.I)
            if match and ('.m3u8' in match.group(1).lower() or key == 'hls2'):
                return match.group(1)
        match = re.search(r'''https?://[^\s"']+\.m3u8(?:\?[^\s"']*)?''', clean, re.I)
        return match.group(0) if match else ''

    def _resolve_streamtape(self, html):
        text = str(html or '').replace('\\/', '/')
        assignment = re.search(
            r'''getElementById\(\s*["']botlink["']\s*\)\.innerHTML\s*=\s*([^;]+)''',
            text, re.S)
        if not assignment:
            return ''
        expression = assignment.group(1)
        parts = re.search(
            r'''^[\s]*(["'])(.*?)\1\s*\+\s*\(\s*(["'])((?:\\.|(?!\3).)*)\3\s*\)((?:\.substring\(\d+\))+)''',
            expression, re.S)
        if not parts:
            return ''
        prefix = self._js_unescape(parts.group(2))
        tail = self._js_unescape(parts.group(4))
        for amount in re.findall(r'\.substring\((\d+)\)', parts.group(5)):
            tail = tail[int(amount):]
        url = prefix + tail
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            url = 'https://streamtape.com' + url
        return url + ('&' if '?' in url else '?') + 'stream=1'

    @staticmethod
    def _decode_voe_config(encoded):
        try:
            value = str(encoded or '')
            alpha = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
            rota = 'NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm'
            value = value.translate(str.maketrans(alpha, rota))
            for token in ('@$', '^^', '~@', '%?', '*~', '!!', '#&'):
                value = value.replace(token, '_')
            value = value.replace('_', '')
            value += '=' * (-len(value) % 4)
            stage = base64.b64decode(value).decode('latin1')
            stage = ''.join(chr((ord(ch) - 3) % 256) for ch in stage)[::-1]
            stage += '=' * (-len(stage) % 4)
            return json.loads(base64.b64decode(stage).decode('utf-8', 'ignore'))
        except Exception as e:
            print('[SupJav] VOE配置解码失败: %s' % e)
            return {}

    def _resolve_voe(self, html, final_page):
        text = str(html or '')
        jump = re.search(r'''https?://stevenfamilyedge\.com/e/[^\s"'<>]+''', text, re.I)
        target = jump.group(0) if jump else str(final_page or '')
        if not target.startswith('http'):
            return ''
        headers = {
            'User-Agent': self.headers.get('User-Agent', 'Mozilla/5.0'),
            'Referer': final_page
        }
        resp = self.session.get(target, headers=headers, timeout=20, verify=False)
        page = resp.text or ''
        script = re.search(
            r'''<script[^>]+type=["']application/json["'][^>]*>(.*?)</script>''',
            page, re.S | re.I)
        if not script:
            return ''
        raw = json.loads(script.group(1).strip())
        encoded = raw[0] if isinstance(raw, list) and raw else ''
        config = self._decode_voe_config(encoded)
        source = str(config.get('source') or '') if isinstance(config, dict) else ''
        return source if source.startswith('http') and '.m3u8' in source.lower() else ''

    def _resolve_real_play_url(self, intermediate_url, page_url='', line_name=''):
        line = str(line_name or '').strip().upper()
        try:
            ua = self.headers.get('User-Agent', 'Mozilla/5.0')
            l_headers = {'User-Agent': ua, 'Referer': page_url or self.host + '/'}
            l_resp = self.session.get(intermediate_url, headers=l_headers, timeout=15, verify=False)
            l_html = l_resp.text or ''
            olid_match = re.search(r'''OLID\s*=\s*["']([^"']+)["']''', l_html)
            if not olid_match:
                print('[SupJav] %s线路未找到OLID' % (line or '未知'))
                return '', 1

            c_url = 'https://lk1.supremejav.com/supjav.php?c=' + olid_match.group(1).strip()[::-1]
            c_headers = {'User-Agent': ua, 'Referer': intermediate_url}
            c_resp = self.session.get(c_url, headers=c_headers, timeout=18, verify=False)
            c_html = c_resp.text or ''
            final_page = str(c_resp.url or c_url)
            clean_html = c_html.replace('\\/', '/')
            print('[SupJav] 线路解析: %s | final=%s | html=%s' %
                  (line or '未知', final_page[:100], len(c_html)))

            media = ''
            if line == 'TV' or 'turboviplay' in final_page.lower() or 'turbovidhls' in final_page.lower():
                found = re.search(r'''https?://[^\s"'<>]+?\.m3u8(?:\?[^\s"'<>]*)?''', clean_html, re.I)
                media = found.group(0).strip() if found else ''
            elif line == 'FST' or 'fc2stream.' in final_page.lower():
                media = self._resolve_fst(c_html)
            elif line == 'ST' or 'streamtape.' in final_page.lower():
                media = self._resolve_streamtape(c_html)
                if media:
                    probe = self.session.get(
                        media,
                        headers={'User-Agent': ua, 'Referer': final_page},
                        timeout=18, verify=False, allow_redirects=True, stream=True)
                    if probe.status_code in (200, 206) and str(probe.url).startswith('http'):
                        media = str(probe.url)
                    probe.close()
            elif line == 'VOE' or 'voe.' in final_page.lower() or 'stevenfamilyedge.' in final_page.lower():
                media = self._resolve_voe(c_html, final_page)

            if media:
                print('[SupJav] %s直链已提取: %s' % (line or '未知', media[:120]))
                return media, 0
            print('[SupJav] %s线路未取得最终媒体，保留网页兜底' % (line or '未知'))
            return final_page, 1
        except Exception as e:
            print('[SupJav Error] %s线路解析异常: %s' % (line or '未知', e))
            return '', 1


    def homeContent(self, filter=False):
        return {"class": list(self.classes), "filters": dict(self.filters)}

    def homeVideoContent(self):
        return self.categoryContent("zh", 1, False, {})

    def categoryContent(self, tid, pg, filter, extend):
        pg = max(1, int(pg))
        if tid == "zh" or not tid:
            url = f"{self.host}/zh/page/{pg}" if pg > 1 else f"{self.host}/zh/"
        else:
            url = f"{self.host}/{tid}/page/{pg}" if pg > 1 else f"{self.host}/{tid}"

        html = self._fetch_html(url)
        video_list = []

        if html:
            soup = BeautifulSoup(html, "html.parser")
            posts = soup.select(".posts .post")

            for post in posts:
                a_tag = post.select_one("a.img") or post.select_one("h3 a")
                if not a_tag: continue
                
                href = a_tag.get("href", "")
                title = a_tag.get("title") or a_tag.text.strip()
                if not href: continue

                vod_id = href.replace(self.host + "/", "").replace(".html", "")
                img_tag = post.select_one("img")
                pic = ""
                if img_tag:
                    pic = img_tag.get("data-original") or img_tag.get("src") or ""

                if pic and self.pic_proxy:
                    pic = f"{self.pic_proxy}{base64.b64encode(pic.encode('utf-8')).decode('utf-8')}"

                meta_tag = post.select_one(".meta")
                remarks = meta_tag.text.strip() if meta_tag else "高清"

                video_list.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })

        return {
            "page": pg,
            "pagecount": pg + 1,
            "limit": len(video_list),
            "total": len(video_list) * 10,
            "list": video_list
        }

    def _normalize_vod_id(self, value):
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ''
        elif isinstance(value, dict):
            value = value.get('id') or value.get('vod_id') or value.get('url') or ''
        raw = unquote(str(value or '').strip())
        if raw.startswith('{'):
            try:
                data = json.loads(raw)
                raw = str(data.get('id') or data.get('vod_id') or data.get('url') or '')
            except Exception:
                pass
        if raw.startswith('http://') or raw.startswith('https://'):
            raw = urlsplit(raw).path
        raw = raw.split('?', 1)[0].split('#', 1)[0].strip('/')
        if raw.endswith('.html'):
            raw = raw[:-5]
        if raw.startswith('zh/'):
            return raw
        if re.fullmatch(r'\d+', raw):
            return 'zh/' + raw
        return raw

    def _parse_post_items(self, nodes, current_id=''):
        items, seen = [], set()
        current = self._normalize_vod_id(current_id)
        for post in nodes or []:
            try:
                a_tag = post.select_one('a.img[href]') or post.select_one('h3 a[href]') or post.select_one('a[rel="bookmark"][href]')
                img_tag = post.select_one('img')
                if a_tag is None:
                    continue
                href = urljoin(self.host + '/', str(a_tag.get('href') or '').strip())
                if urlsplit(href).hostname not in (urlsplit(self.host).hostname, 'www.' + str(urlsplit(self.host).hostname or '')):
                    continue
                vod_id = self._normalize_vod_id(href)
                title = str(a_tag.get('title') or (img_tag.get('alt') if img_tag else '') or a_tag.get_text(' ', strip=True) or '').strip()
                if not vod_id or not title or vod_id == current or vod_id in seen:
                    continue
                seen.add(vod_id)
                pic = str((img_tag.get('data-original') or img_tag.get('data-src') or img_tag.get('src') or '') if img_tag else '').strip()
                if pic.startswith('data:'):
                    pic = ''
                pic = urljoin(href, pic) if pic else ''
                if pic and self.pic_proxy:
                    pic = self.pic_proxy + base64.b64encode(pic.encode('utf-8')).decode('utf-8')
                meta = post.select_one('.meta')
                remarks = meta.get_text(' ', strip=True) if meta else '高清'
                items.append({'vod_id': vod_id, 'vod_name': title, 'vod_pic': pic, 'vod_remarks': remarks})
            except Exception as e:
                print('[SupJav] 单条卡片解析失败: %s' % e)
        return items

    def detailContent(self, array):
        vod_id = self._normalize_vod_id(array)
        if not vod_id:
            return {'list': []}
        target_url = f"{self.host}/{vod_id}.html"

        html = self._fetch_html(target_url)
        play_groups = []
        title = vod_id
        pic = ""

        if html:
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.select_one('.post-meta h2') or soup.select_one('h1')
            title = title_tag.get_text(' ', strip=True) if title_tag else vod_id

            img_tag = soup.select_one('.post-meta > img') or soup.select_one('.post-media img') or soup.select_one('a.img img')
            if img_tag:
                pic = img_tag.get('data-original') or img_tag.get('data-src') or img_tag.get('src') or ''
                pic = urljoin(target_url, pic) if pic else ''
            if pic and self.pic_proxy:
                pic = f"{self.pic_proxy}{base64.b64encode(pic.encode('utf-8')).decode('utf-8')}"

            dz_video = soup.select_one("#dz_video")
            bg = dz_video.get("bg", "") if dz_video else ""

            server_btns = list(soup.select('.btn-server'))
            server_btns.sort(key=lambda btn: 0 if btn.get_text(' ', strip=True).upper() == 'VOE' else 1)

            for btn in server_btns:
                server_name = btn.text.strip()
                vurl = btn.get("data-link", "")
                
                if vurl:
                    intermediate_url = f"https://lk1.supremejav.com/supjav.php?l={vurl}&bg={bg}"
                    combined_id = f"{server_name}|||{intermediate_url}@@@{target_url}"
                    play_groups.append((server_name, f"播放${combined_id}"))

        if not play_groups:
            play_groups.append(("备用源", f"播放${target_url}"))

        vod = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_play_from": "$$$".join(x[0] for x in play_groups),
            "vod_play_url": "$$$".join(x[1] for x in play_groups)
        }
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            categories = [x.get_text(' ', strip=True) for x in soup.select('.post-meta .cats a') if x.get_text(' ', strip=True)]
            tags = [x.get_text(' ', strip=True) for x in soup.select('.post-meta .tags a') if x.get_text(' ', strip=True)]
            content_tag = soup.select_one('.post-content')
            content = content_tag.get_text('\n', strip=True) if content_tag else ''
            if not content:
                parts = []
                if categories:
                    parts.append('分类：' + ' / '.join(dict.fromkeys(categories)))
                if tags:
                    parts.append('标签：' + ' / '.join(dict.fromkeys(tags)))
                content = '\n'.join(parts)
            views = soup.select_one('.dz_view .views')
            if categories:
                vod['vod_class'] = ','.join(dict.fromkeys(categories))
            if tags:
                vod['vod_tag'] = ','.join(dict.fromkeys(tags))
            if content:
                vod['vod_content'] = content
            if views:
                vod['vod_remarks'] = views.get_text(' ', strip=True)
        
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        word = str(key or '').strip()
        if not word:
            return {'list': [], 'page': page, 'pagecount': page, 'limit': 0, 'total': 0}
        url = f"{self.host}/zh/?s={quote(word)}" + (f"&paged={page}" if page > 1 else "")
        html = self._fetch_html(url)
        items = []
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            items = self._parse_post_items(soup.select('.posts .post'))
        return {
            'page': page,
            'pagecount': page + 1 if items else page,
            'limit': len(items),
            'total': len(items),
            'list': items
        }

    def searchContentPage(self, key, quick=False, pg='1'):
        return self.searchContent(key, quick, pg)

    def recommendContent(self, ids, pg):
        vod_id = self._normalize_vod_id(ids)
        if not vod_id:
            return {'list': []}
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        if page > 1:
            return {'list': []}
        try:
            target_url = f"{self.host}/{vod_id}.html"
            html = self._fetch_html(target_url)
            if not html:
                return {'list': []}
            soup = BeautifulSoup(html, 'html.parser')
            container = None
            for heading in soup.select('.archive-title'):
                name = heading.get_text(' ', strip=True).lower()
                if 'you may also like' in name or '猜你喜欢' in name or '相关推荐' in name:
                    sibling = heading.find_next_sibling()
                    if sibling is not None and 'posts' in (sibling.get('class') or []):
                        container = sibling
                    break
            if container is None:
                return {'list': []}
            return {'list': self._parse_post_items(container.select(':scope > .post'), vod_id)}
        except Exception as e:
            print('[SupJav] 相关推荐解析失败: %s' % e)
            return {'list': []}


    def _tv_proxy_url(self, url, mode='hls'):
        try:
            base = str(self.getProxyUrl() or '')
        except Exception:
            base = ''
        if not base:
            return str(url or '')
        return base + '&mode=' + quote(mode) + '&url=' + quote(str(url or ''), safe='')

    @staticmethod
    def _strip_png_ts(data):
        data = bytes(data or b'')
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):
            return data, False
        limit = min(len(data) - 188 * 5, 65536)
        for offset in range(8, max(8, limit)):
            if data[offset] == 0x47 and all(data[offset + 188 * i] == 0x47 for i in range(5)):
                return data[offset:], True
        return data, False

    def playerContent(self, flag, id, vipFlags):

        raw = str(id or '')
        page_url = ''
        if '@@@' in raw:
            raw, page_url = raw.split('@@@', 1)
        line_name = str(flag or '')
        if '|||' in raw:
            line_name, raw = raw.split('|||', 1)

        parse_mode = 1
        final_url = raw
        if 'supjav.php?l=' in raw or 'supremejav.com' in raw:
            resolved, parse_mode = self._resolve_real_play_url(raw, page_url, line_name)
            if resolved:
                final_url = resolved

        header_dict = {'User-Agent': self.headers.get('User-Agent', 'Mozilla/5.0')}
        if parse_mode == 0 and (self.isVideoFormat(final_url) or '/master' in final_url.lower()):
            play_url = self._tv_proxy_url(final_url, 'hls') if str(line_name).upper() == 'TV' else final_url
            return {'parse': 0, 'url': play_url, 'header': header_dict}
        return {'parse': 1, 'url': final_url, 'header': header_dict}

    def localProxy(self, param):
        try:
            mode = str((param or {}).get('mode') or '')
            target = unquote(str((param or {}).get('url') or ''))
            if not target:
                return [404, 'text/plain', b'']
            headers = {
                'User-Agent': self.headers.get('User-Agent', 'Mozilla/5.0'),
                'Accept': '*/*',
                'Accept-Encoding': 'identity'
            }
            resp = self.session.get(target, headers=headers, timeout=(8, 12), verify=False)
            if resp.status_code in (403, 429, 500, 502, 503, 504):
                try:
                    resp.close()
                except Exception:
                    pass
                retry_headers = dict(headers)
                retry_headers['Connection'] = 'close'
                resp = self.session.get(target, headers=retry_headers, timeout=(8, 12), verify=False)
            if resp.status_code not in (200, 206):
                print('[SupJav] TV上游资源失败: %s | %s' % (resp.status_code, target[:120]))
                return [resp.status_code, 'text/plain', b'']
            data = resp.content or b''

            if mode == 'hls':
                text = data.decode('utf-8', 'ignore')
                if '#EXTM3U' not in text:
                    return [502, 'text/plain', b'']
                base_url = str(resp.url or target)
                out = []
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped and not stripped.startswith('#'):
                        absolute = urljoin(base_url, stripped)
                        child_mode = 'hls' if '.m3u8' in absolute.lower() else 'seg'
                        line = self._tv_proxy_url(absolute, child_mode)
                    elif stripped.startswith('#EXT-X-KEY') or stripped.startswith('#EXT-X-MAP'):
                        uri = re.search(r'''URI=(["'])([^"']+)\1''', line, re.I)
                        if uri:
                            absolute = urljoin(base_url, uri.group(2))
                            line = line[:uri.start(2)] + self._tv_proxy_url(absolute, 'res') + line[uri.end(2):]
                    out.append(line)
                return [200, 'application/vnd.apple.mpegurl', ('\n'.join(out) + '\n').encode('utf-8')]

            if mode == 'seg':
                if data.startswith(b'\x47'):
                    return [200, 'video/mp2t', data]
                payload, stripped = self._strip_png_ts(data)
                if stripped:
                    return [200, 'video/mp2t', payload]
                return [200, resp.headers.get('Content-Type') or 'application/octet-stream', data]

            return [200, resp.headers.get('Content-Type') or 'application/octet-stream', data]
        except Exception as e:
            print('[SupJav] TV媒体代理失败: %s' % e)
            return [500, 'text/plain', b'']

    def destroy(self):
        try:
            if self._cf_dialog is not None:
                self._cf_dialog.dismiss()
            if self._cf_webview is not None:
                self._cf_webview.stopLoading()
                self._cf_webview.destroy()
            self.session.close()
        except Exception:
            pass
        self._cf_dialog = None
        self._cf_webview = None
        self._cf_listener = None
        self._cf_value_callback = None
        self._cf_poll_task = None
        if self._cf_wait is not None:
            self._cf_wait.set()