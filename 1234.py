"""
OK本地PY源扫描器推送
========================
- 扫描 PY 目录（识别 class Spider）
- 一键扫描并推送
- 点右侧单个 PY推送
- 扫到 0 个时拒绝推送
"""

import hashlib
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request

from base.spider import Spider as BaseSpider


def _detect_storage_root():
    candidates = []
    external = str(os.environ.get("EXTERNAL_STORAGE", "")).strip()
    if external:
        candidates.append(external)
    candidates.extend(("/sdcard", "/storage/emulated/0", os.path.expanduser("~/storage/shared")))
    seen = set()
    for candidate in candidates:
        path = os.path.abspath(os.path.expanduser(candidate))
        real = os.path.realpath(path)
        if real in seen:
            continue
        seen.add(real)
        if os.path.isdir(path):
            return real
    return os.path.abspath(external or "/sdcard")


def _detect_local_base(storage_root):
    for name in ("tvbox", "TVBox"):
        path = os.path.realpath(os.path.join(storage_root, name))
        if os.path.isdir(path):
            return path
    return os.path.realpath(os.path.join(storage_root, "tvbox"))


STORAGE_ROOT = _detect_storage_root()
LOCAL_BASE = _detect_local_base(STORAGE_ROOT)
DEFAULT_PY_DIR = os.path.join(LOCAL_BASE, "py")
TV_DIR = os.path.join(STORAGE_ROOT, "TV")
FENGLING_PATH = os.path.join(TV_DIR, "丰之玲.json")
SINGLE_PATH = os.path.join(TV_DIR, ".single_config.json")
SETTINGS_PATH = os.path.join(TV_DIR, "py_scan.settings.json")


class Spider(BaseSpider):

    VERSION = "v1.0"

    RESCAN_ID = "__py_scan_rescan__"
    EDIT_DIR_ID = "__py_scan_edit_dir__"

    ACTION_RESCAN = "py_scan_rescan"
    ACTION_EDIT_DIR = "py_scan_edit_dir"
    ACTION_PUSH_ONE_PREFIX = "py_push:"

    MAX_SCAN_DEPTH = 8
    MAX_SCAN_FILES = 3000
    MAX_SOURCE_SIZE = 5 * 1024 * 1024

    def __init__(self):
        super().__init__()
        self.lock = threading.RLock()
        self.inited = False
        self.scan_dir = DEFAULT_PY_DIR
        self.sources = []
        self.status = self._empty_status()
        self._dialog_refs = []

    def getName(self):
        return "本地PY源扫描器 {}".format(self.VERSION)

    def _empty_status(self):
        return {
            "scan_time": "-",
            "found": 0,
            "included": 0,
            "skipped": 0,
            "write_state": "尚未扫描",
            "error": "",
            "warnings": [],
        }

    # ==================================================================
    # 初始化
    # ==================================================================
    def init(self, extend=""):
        with self.lock:
            if self.inited:
                return
            self._load_settings()
            try:
                self._refresh()
            except Exception as exc:
                self.status["warnings"].append("启动扫描失败: {}".format(exc))
            self.inited = True

    def _load_settings(self):
        if not os.path.isfile(SETTINGS_PATH):
            return
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if isinstance(data, dict):
                value = str(data.get("scan_dir", "")).strip()
                if value:
                    self.scan_dir = value
        except Exception:
            pass

    def _save_settings(self):
        try:
            if not os.path.isdir(TV_DIR):
                os.makedirs(TV_DIR, exist_ok=True)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as fp:
                json.dump({"scan_dir": self.scan_dir}, fp, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ==================================================================
    # 扫描
    # ==================================================================
    def _is_spider_file(self, path):
        try:
            with open(path, "rb") as fp:
                data = fp.read(256 * 1024)
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            return False
        return bool(re.search(r"\bclass\s+Spider\s*(?:\(|:)", text))

    def _scan(self):
        self.sources = []
        self.status = self._empty_status()
        self.status["scan_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

        root = os.path.abspath(os.path.expanduser(self.scan_dir))
        if not os.path.isdir(root):
            self.status["write_state"] = "目录不存在"
            self.status["error"] = "扫描目录不存在: {}".format(root)
            return False

        self_path = os.path.realpath(__file__)
        found = 0
        included = 0
        skipped = 0

        for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
            rel = os.path.relpath(current, root)
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            dirs[:] = sorted(
                [d for d in dirs if not d.startswith(".") and d != "__pycache__"],
                key=lambda v: v.lower(),
            )
            if depth >= self.MAX_SCAN_DEPTH:
                dirs[:] = []

            for file_name in sorted(files, key=lambda v: v.lower()):
                if not file_name.lower().endswith(".py"):
                    continue
                if file_name == "__init__.py":
                    continue
                if found >= self.MAX_SCAN_FILES:
                    break
                full_path = os.path.join(current, file_name)
                if os.path.islink(full_path) or not os.path.isfile(full_path):
                    continue
                real_path = os.path.realpath(full_path)
                if real_path == self_path:
                    continue
                found += 1
                try:
                    stat = os.stat(real_path)
                    if stat.st_size <= 0 or stat.st_size > self.MAX_SOURCE_SIZE:
                        skipped += 1
                        continue
                except Exception:
                    skipped += 1
                    continue
                if not self._is_spider_file(real_path):
                    skipped += 1
                    continue
                relative = os.path.relpath(real_path, root).replace(os.sep, "/")
                self.sources.append({
                    "path": real_path,
                    "relative": relative,
                    "base_name": file_name[:-3],
                })
                included += 1

        self._apply_display_names()
        self.status["found"] = found
        self.status["included"] = included
        self.status["skipped"] = skipped
        self.status["write_state"] = "扫描完成"
        return True

    def _apply_display_names(self):
        counts = {}
        for source in self.sources:
            key = source["base_name"].lower()
            counts[key] = counts.get(key, 0) + 1
        for source in self.sources:
            base = source["base_name"]
            if counts.get(base.lower(), 0) > 1:
                folder = os.path.dirname(source["relative"])
                suffix = folder.replace("/", " · ") if folder else "根目录"
                source["name"] = "{} 【{}】┃[py]".format(base, suffix)
            else:
                source["name"] = base + "┃[py]"

    # ==================================================================
    # URL 工具
    # ==================================================================
    def _file_url(self, path):
        """相对 file:// 形式（用于 site.api 里的 PY 路径）"""
        absolute = os.path.realpath(os.path.abspath(path))
        storage_root = os.path.realpath(STORAGE_ROOT)
        try:
            relative = os.path.relpath(absolute, storage_root).replace(os.sep, "/")
        except Exception:
            relative = ""
        if relative and relative != ".." and not relative.startswith("../"):
            return "file://" + relative.lstrip("/")
        return "file://" + absolute

    def _abs_file_url(self, path):
        """绝对 file:// 形式（三斜杠，用于推送给 TVBox 的配置地址）"""
        absolute = os.path.realpath(os.path.abspath(path))
        return "file://" + absolute

    def _build_site(self, source):
        key = "local_py_" + self._source_hash(source)
        return {
            "key": key,
            "name": source["name"],
            "type": 3,
            "api": self._file_url(source["path"]),
            "searchable": 1,
            "quickSearch": 1,
        }

    def _source_hash(self, source):
        return hashlib.sha256(source["path"].encode("utf-8")).hexdigest()[:12]

    def _find_source_by_hash(self, h):
        for s in self.sources:
            if self._source_hash(s) == h:
                return s
        return None

    def _write_config_file(self, path, config):
        try:
            if not os.path.isdir(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path), exist_ok=True)
            content = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as fp:
                        if fp.read() == content:
                            return True
                except Exception:
                    pass
            temp_path = path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as fp:
                fp.write(content)
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(temp_path, path)
            return True
        except Exception as exc:
            self.status["error"] = "写入配置失败: {}".format(exc)
            return False

    def _write_fengzhiling(self):
        if not self.sources:
            self.status["error"] = "未扫到任何 PY 源"
            return False
        config = {"sites": [self._build_site(s) for s in self.sources]}
        return self._write_config_file(FENGLING_PATH, config)

    def _write_single_config(self, source):
        config = {"sites": [self._build_site(source)]}
        return self._write_config_file(SINGLE_PATH, config)

    # ==================================================================
    # 推送
    # ==================================================================
    def _push_config(self, url, name="推送接口"):
        try:
            from java import jclass
            port = int(jclass("com.github.catvod.Proxy").getPort())
            if port < 1:
                return False, "Proxy 端口未就绪"
            config = json.dumps(
                {"type": 0, "url": url, "name": name},
                ensure_ascii=False, separators=(",", ":"),
            )
            body = urllib.parse.urlencode(
                {"config": config, "targets": "[]", "force": "false"}
            ).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:{}/action?do=sync&mode=1&type=history".format(port),
                data=body,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                    "Connection": "close",
                },
            )
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=5) as r:
                code = r.getcode()
            return True, "已推送：{} (HTTP {})".format(url, code)
        except Exception as e:
            return False, "推送失败: {}".format(e)

    def _push_all(self):
        if not self.sources:
            return False, "没有扫描到py爬虫，请重新设置目录"
        if not os.path.isfile(FENGLING_PATH):
            return False, "爬虫不存在"
        url = self._abs_file_url(FENGLING_PATH)
        return self._push_config(url, name="全部PY源")

    def _push_one(self, h):
        source = self._find_source_by_hash(h)
        if source is None:
            return False, "未找到该PY源"
        if not self._write_single_config(source):
            return False, "临时配置失败: {}".format(self.status.get("error", ""))
        url = self._abs_file_url(SINGLE_PATH)
        return self._push_config(url, name=source["name"])

    def _refresh(self):
        ok = self._scan()
        if ok and self.sources:
            self._write_fengzhiling()
        return ok

    # ==================================================================
    # Android 反射
    # ==================================================================
    def _current_android_activity(self, jclass):
        app_class = jclass("com.fongmi.android.tv.App")
        activity_class = jclass("android.app.Activity")
        modifier_class = jclass("java.lang.reflect.Modifier")
        app_info = app_class.getClass()
        activity_info = activity_class.getClass()

        for method in app_info.getDeclaredMethods():
            try:
                if not modifier_class.isStatic(method.getModifiers()):
                    continue
                if len(method.getParameterTypes()) != 0:
                    continue
                if not activity_info.isAssignableFrom(method.getReturnType()):
                    continue
                method.setAccessible(True)
                try:
                    activity = method.invoke(None, [])
                except Exception:
                    activity = method.invoke(None)
                if activity is not None:
                    return activity
            except Exception:
                continue

        app = None
        for field in app_info.getDeclaredFields():
            try:
                if not modifier_class.isStatic(field.getModifiers()):
                    continue
                if not app_info.isAssignableFrom(field.getType()):
                    continue
                field.setAccessible(True)
                app = field.get(None)
                if app is not None:
                    break
            except Exception:
                continue
        if app is not None:
            for field in app.getClass().getDeclaredFields():
                try:
                    if modifier_class.isStatic(field.getModifiers()):
                        continue
                    if not activity_info.isAssignableFrom(field.getType()):
                        continue
                    field.setAccessible(True)
                    activity = field.get(app)
                    if activity is not None:
                        return activity
                except Exception:
                    continue
        raise ValueError("未找到当前 Android 页面")

    # ==================================================================
    # 目录浏览器
    # ==================================================================
    def _open_dir_browser(self):
        try:
            from java import dynamic_proxy, jclass, jarray
            from java.lang import String as JString

            toast_class = jclass("android.widget.Toast")
            click_listener = jclass("android.content.DialogInterface$OnClickListener")
            runnable_class = jclass("java.lang.Runnable")
            try:
                builder_class = jclass(
                    "com.google.android.material.dialog.MaterialAlertDialogBuilder"
                )
            except Exception:
                builder_class = jclass("android.app.AlertDialog$Builder")

            activity = self._current_android_activity(jclass)
            owner = self

            start = os.path.abspath(os.path.expanduser(owner.scan_dir or DEFAULT_PY_DIR))
            if not os.path.isdir(start):
                start = os.path.realpath(STORAGE_ROOT)
            state = {"path": start, "showing": False, "dialog": None}

            def list_dirs(path):
                try:
                    return sorted(
                        [
                            d
                            for d in os.listdir(path)
                            if os.path.isdir(os.path.join(path, d)) and not d.startswith(".")
                        ],
                        key=lambda v: v.lower(),
                    )
                except Exception:
                    return []

            def dismiss_current():
                d = state.get("dialog")
                if d is not None:
                    try:
                        d.dismiss()
                    except Exception:
                        pass
                state["dialog"] = None

            def schedule_show():
                if state["showing"]:
                    return
                state["showing"] = True
                runner = ShowRunner()
                owner._dialog_refs.append(runner)
                owner._dialog_refs = owner._dialog_refs[-8:]
                activity.runOnUiThread(runner)

            def navigate_to(new_path):
                state["path"] = new_path
                dismiss_current()
                schedule_show()

            def use_current():
                path = state["path"]
                with owner.lock:
                    owner.scan_dir = path
                    owner._save_settings()
                    try:
                        owner._refresh()
                    except Exception as exc:
                        toast_class.makeText(
                            activity, "扫描失败: " + str(exc), toast_class.LENGTH_LONG
                        ).show()
                        return
                dismiss_current()
                toast_class.makeText(
                    activity,
                    "已选择并扫描: {} ({} 个PY源)".format(path, len(owner.sources)),
                    toast_class.LENGTH_LONG,
                ).show()

            class ItemClick(dynamic_proxy(click_listener)):
                def onClick(self, dialog, which):
                    try:
                        idx = int(which)
                        path = state["path"]
                        dirs = list_dirs(path)
                        has_parent = os.path.dirname(path) != path
                        offset = 0
                        if has_parent:
                            if idx == 0:
                                navigate_to(os.path.dirname(path))
                                return
                            offset = 1
                        di = idx - offset
                        if 0 <= di < len(dirs):
                            navigate_to(os.path.join(path, dirs[di]))
                    except Exception as exc:
                        try:
                            toast_class.makeText(
                                activity, "错误: " + str(exc), toast_class.LENGTH_LONG
                            ).show()
                        except Exception:
                            pass

            class UseButton(dynamic_proxy(click_listener)):
                def onClick(self, dialog, which):
                    try:
                        use_current()
                    except Exception as exc:
                        try:
                            toast_class.makeText(
                                activity, "错误: " + str(exc), toast_class.LENGTH_LONG
                            ).show()
                        except Exception:
                            pass

            class ShowRunner(dynamic_proxy(runnable_class)):
                def run(self):
                    try:
                        path = state["path"]
                        dirs = list_dirs(path)
                        labels = []
                        if os.path.dirname(path) != path:
                            labels.append("⬆  返回上级目录")
                        if not dirs:
                            labels.append("（没有子文件夹）")
                        else:
                            for d in dirs:
                                labels.append("📁  " + d)
                        arr = jarray(JString)(labels)
                        b = builder_class(activity)
                        b.setTitle(path)
                        b.setItems(arr, ItemClick())
                        b.setPositiveButton("使用此目录", UseButton())
                        b.setNegativeButton("取消", None)
                        d = b.show()
                        state["dialog"] = d
                        owner._dialog_refs.append(d)
                        owner._dialog_refs = owner._dialog_refs[-8:]
                    except Exception as exc:
                        try:
                            toast_class.makeText(
                                activity,
                                "打开失败: " + str(exc),
                                toast_class.LENGTH_LONG,
                            ).show()
                        except Exception:
                            pass
                    finally:
                        state["showing"] = False

            schedule_show()
            return True, ""
        except Exception as exc:
            return False, "打开目录选择器失败: {}".format(exc)

    # ==================================================================
    # TVBox 接口
    # ==================================================================
    def homeContent(self, filter):
        with self.lock:
            if not self.inited:
                self.init("")
        return {
            "class": [
                {"type_id": "all", "type_name": "PY源 ({})".format(len(self.sources))},
            ],
            "list": self._home_items(),
        }

    def homeVideoContent(self):
        with self.lock:
            if not self.inited:
                self.init("")
        return {"list": self._home_items()}

    def _home_items(self):
        return [
            {
                "vod_id": self.RESCAN_ID,
                "vod_name": "扫描推送",
                "vod_pic": "https://files.seeusercontent.com/2026/10/13/g0dS/1791894305322_edit_2712206973539.png",
                "vod_remarks": "已扫 {} 个".format(
                     len(self.sources)
                ),
                "action": self.ACTION_RESCAN,
            },
            {
                "vod_id": self.EDIT_DIR_ID,
                "vod_name": "设置目录",
                "vod_pic": "https://files.seeusercontent.com/2026/10/13/g0dS/1791894305322_edit_2712206973539.png",
                "vod_remarks": "py目录",
                "action": self.ACTION_EDIT_DIR,
            },
        ]

    def categoryContent(self, tid, pg, filter, ext):
        with self.lock:
            if not self.inited:
                self.init("")
        try:
            page = max(1, int(pg))
        except Exception:
            page = 1
        items = list(self.sources) if tid == "all" else []
        return self._paged(items, page)

    def _paged(self, items, page):
        page_size = 60
        total = len(items)
        page_count = max(1, (total + page_size - 1) // page_size)
        if page > page_count:
            page_items = []
        else:
            start = (page - 1) * page_size
            page_items = items[start:start + page_size]
        return {
            "page": page,
            "pagecount": page_count,
            "limit": page_size,
            "total": total,
            "list": [self._to_vod(item) for item in page_items],
        }

    def _source_id(self, source):
        return "src_" + hashlib.sha256(source["path"].encode("utf-8")).hexdigest()[:16]

    def _to_vod(self, source):
        return {
            "vod_id": self._source_id(source),
            "vod_name": source["name"],
            "vod_pic": "",
            "vod_remarks": source["relative"] + " · 点击推送此源",
            "action": self.ACTION_PUSH_ONE_PREFIX + self._source_hash(source),
        }

    def detailContent(self, array):
        with self.lock:
            if not self.inited:
                self.init("")
        source_id = str(array[0]) if isinstance(array, (list, tuple)) and array else str(array or "")
        if source_id == self.RESCAN_ID:
            with self.lock:
                ok_scan = self._refresh()
                if ok_scan and self.sources:
                    ok_push, push_msg = self._push_all()
                elif ok_scan and not self.sources:
                    ok_push, push_msg = False, "扫到 0 个PY源，未推送"
                else:
                    ok_push, push_msg = False, "扫描失败，未推送"
            content = (
                "扫描: {scan}\n"
                "扫到: {n} 个PY源\n"
                "输出: {out}\n"
                "推送: {push}"
            ).format(
                scan="成功" if ok_scan else "失败",
                n=len(self.sources),
                out=FENGLING_PATH,
                push=push_msg,
            )
            return {"list": [{
                "vod_id": self.RESCAN_ID,
                "vod_name": "扫描并推送完成",
                "vod_pic": "",
                "vod_remarks": "成功" if ok_scan and ok_push else "未推送",
                "vod_content": content,
            }]}
        for source in self.sources:
            if self._source_id(source) == source_id:
                content = (
                    "名称: {name}\n"
                    "文件: {path}\n"
                    "相对路径: {relative}\n"
                    "api: {api}"
                ).format(
                    name=source["name"],
                    path=source["path"],
                    relative=source["relative"],
                    api=self._file_url(source["path"]),
                )
                return {"list": [{
                    "vod_id": source_id,
                    "vod_name": source["name"],
                    "vod_pic": "",
                    "vod_remarks": "PY",
                    "vod_content": content,
                }]}
        return {"list": [{"vod_name": "源不存在", "vod_content": "请重新扫描"}]}

    def searchContent(self, key, quick, pg="1"):
        with self.lock:
            if not self.inited:
                self.init("")
        keyword = str(key or "").strip().lower()
        try:
            page = max(1, int(pg))
        except Exception:
            page = 1
        if not keyword:
            items = []
        else:
            items = [
                s for s in self.sources
                if keyword in s["name"].lower() or keyword in s["relative"].lower()
            ]
        return self._paged(items, page)

    def action(self, action):
        with self.lock:
            if not self.inited:
                self.init("")
        action = str(action)
        if action == self.ACTION_EDIT_DIR:
            opened, message = self._open_dir_browser()
            return {"code": 0, "msg": "" if opened else message}
        if action == self.ACTION_RESCAN:
            with self.lock:
                ok_scan = self._refresh()
                if ok_scan and self.sources:
                    ok_push, push_msg = self._push_all()
                elif ok_scan and not self.sources:
                    ok_push, push_msg = False, "扫到 0 个PY源，已跳过推送"
                else:
                    ok_push, push_msg = False, "扫描失败，已跳过推送"
            if ok_scan and self.sources and ok_push:
                return {
                    "code": 0,
                    "msg": "扫描完成：{} 个PY源；{}".format(
                        len(self.sources), push_msg
                    ),
                }
            if ok_scan and not self.sources:
                return {
                    "code": 0,
                    "msg": "扫描完成：0 个PY源，未推送（避免推空白配置）",
                }
            if ok_scan and self.sources and not ok_push:
                return {
                    "code": 0,
                    "msg": "扫描完成：{} 个PY源，但推送失败：{}".format(
                        len(self.sources), push_msg
                    ),
                }
            return {
                "code": 0,
                "msg": "扫描失败：{}".format(
                    self.status["error"] or self.status["write_state"]
                ),
            }
        if action.startswith(self.ACTION_PUSH_ONE_PREFIX):
            h = action[len(self.ACTION_PUSH_ONE_PREFIX):]
            with self.lock:
                ok, msg = self._push_one(h)
            return {"code": 0, "msg": msg}
        return {"code": 0, "msg": "未知操作"}

    def playerContent(self, flag, id, vipFlags):
        return {"parse": 0, "url": "", "header": {}, "msg": "这是扫描管理条目"}

    def destroy(self):
        return "destroy"