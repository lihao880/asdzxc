SRC_NAME = "真果鉴v3.1"
SRC_KEY = "zhenguojian_all_v3.1"
LOCAL_PROXY_KEY = "真果鉴v3.1"
import base64
import gzip
import hashlib
import hmac
import http.client
import os
import socket
import ssl
import json
import random
import re
import struct
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
import lzma
import binascii
from collections.abc import Mapping
from typing import Any
try:
    from concurrent.futures import ThreadPoolExecutor, wait
except Exception:
    ThreadPoolExecutor = None
    wait = None
def parallel_run(tasks, max_workers):
    if ThreadPoolExecutor is None:
        return [(name, fn()) for name, fn in tasks]
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks}
        for future in futures:
            try:
                results.append((futures[future], future.result()))
            except Exception:
                continue
    return results
def parallel_run_to(tasks, max_workers, timeout=None):
    if ThreadPoolExecutor is None or wait is None:
        return [(name, fn()) for name, fn in tasks]
    pool = ThreadPoolExecutor(max_workers=max_workers)
    futures = {pool.submit(fn): name for name, fn in tasks}
    if timeout:
        done, _ = wait(futures, timeout=timeout)
    else:
        done = futures
    results = []
    for future in done:
        try:
            results.append((futures[future], future.result()))
        except Exception:
            continue
    pool.shutdown(wait=False)
    return results
LOCK = threading.RLock()
def log(*args):
    try:
        print("[真果鉴]", *args)
    except Exception:
        pass
def now():
    return int(time.time())
def uuid4():
    return "%08x-%04x-4%03x-%04x-%012x" % (
        random.getrandbits(32), random.getrandbits(16),
        random.getrandbits(12), random.getrandbits(16), random.getrandbits(48))
def first_non_empty(*values):
    for value in values:
        if value is not None:
            value = str(value).strip()
            if value:
                return value
    return ""
def js_unescape(text):
    return urllib.parse.unquote_plus(text)
def html_unescape(text):
    import html
    return html.unescape(text)
def clean_text(text):
    if text is None:
        return ""
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", str(text))
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
def attr(block, name):
    m = re.search(name + r'\s*=\s*(["\'])(.*?)\1', block, re.I | re.S)
    return html_unescape(m.group(2)) if m else ""
def attrs(block, *names):
    for name in names:
        value = attr(block, name)
        if value:
            return value
    return ""
def resolve_url(base, ref):
    if not ref:
        return ""
    if ref.startswith("//"):
        parsed = urllib.parse.urlparse(base)
        return parsed.scheme + ":" + ref
    return urllib.parse.urljoin(base, ref)
def parse_qs_keep(value):
    return urllib.parse.parse_qs(value, keep_blank_values=True)
def url_query_encode(values):
    return urllib.parse.urlencode(values)
def episode_number(text, fallback=0):
    m = re.search(r"(\d{1,6})", str(text or ""))
    if m:
        return int(m.group(1))
    return fallback
DEFAULT_TIMEOUT = 12
MAX_BODY = 16 << 20
def http_request(url, method="GET", headers=None, data=None, timeout=DEFAULT_TIMEOUT,
                 max_redirect=4, raw_bytes=True, verify=True):
    current = url
    method = method.upper()
    for _ in range(max_redirect + 1):
        parsed = urllib.parse.urlparse(current)
        host = parsed.hostname
        port = parsed.port
        if parsed.scheme == "https":
            if verify:
                conn = http.client.HTTPSConnection(host, port, timeout=timeout)
            else:
                _ctx = ssl._create_unverified_context()
                conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=_ctx)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        request_headers = dict(headers or {})
        if data is not None and "Content-Length" not in request_headers:
            request_headers["Content-Length"] = str(len(data))
        try:
            conn.request(method, path, body=data, headers=request_headers)
            resp = conn.getresponse()
            if resp.status in (301, 302, 303, 307, 308):
                location = resp.getheader("Location")
                conn.close()
                if not location:
                    return resp.status, dict(resp.getheaders()), b""
                current = urllib.parse.urljoin(current, location)
                if resp.status == 303:
                    method = "GET"
                    data = None
                continue
            body = resp.read(MAX_BODY + 1)
            headers_map = {}
            for key, value in resp.getheaders():
                lkey = key.lower()
                if lkey == "set-cookie" and lkey in headers_map:
                    headers_map[lkey] += "\n" + value
                else:
                    headers_map[lkey] = value
            conn.close()
            return resp.status, headers_map, body
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            raise
    raise RuntimeError("redirect too many: " + url)
def http_text(url, method="GET", headers=None, data=None, encoding=None, timeout=DEFAULT_TIMEOUT):
    _, resp_headers, body = http_request(url, method=method, headers=headers, data=data, timeout=timeout)
    if not encoding:
        content_type = resp_headers.get("content-type", "")
        m = re.search(r"charset=([\w-]+)", content_type, re.I)
        encoding = m.group(1) if m else None
    for candidate in (encoding, "utf-8", "gbk", "gb2312"):
        if candidate:
            try:
                return body.decode(candidate)
            except Exception:
                continue
    return body.decode("utf-8", "ignore")
def http_json(url, method="GET", headers=None, data=None, timeout=DEFAULT_TIMEOUT):
    status, _, body = http_request(url, method=method, headers=headers, data=data, timeout=timeout)
    if status >= 400:
        raise RuntimeError("HTTP %d: %s" % (status, url))
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        raise RuntimeError("invalid json: %s" % url)
CACHE = {}
CACHE_LOCK = threading.RLock()
def cache_get(key):
    with CACHE_LOCK:
        item = CACHE.get(key)
    if item and item[0] > time.time():
        return item[1]
    return None
def cache_set(key, value, ttl=600):
    with CACHE_LOCK:
        CACHE[key] = (time.time() + ttl, value)
def cache_pop(key):
    with CACHE_LOCK:
        CACHE.pop(key, None)
HONG_BASE = "https://api5-normal-sinfonlineb.fqnovel.com"
HONG_WEB = "https://hongguoduanju.com"
HONG_WEB_MIRRORS = ["https://hongguoduanju.com", "https://novelquickapp.com"]
def hong_web_base():
    cached = cache_get("hong:web")
    if cached:
        return cached
    for mirror in HONG_WEB_MIRRORS:
        try:
            status, _, _ = http_request(mirror + "/", timeout=6)
            if status < 400:
                cache_set("hong:web", mirror, 3600)
                return mirror
        except Exception:
            continue
    return HONG_WEB_MIRRORS[0]
HONG_UA = ("com.phoenix.read/73532 (Linux; U; Android 16; zh_CN; 25053RT47C; "
           "Build/BP2A.250605.031.A3; Cronet/TTNetVersion:04657795 2026-01-23 "
           "QuicVersion:c67e9834 2025-09-08)")
HONG_KEY = bytes([0x44, 0xb9, 0xb9, 0xd9, 0xa4, 0xae, 0xf9, 0xfc, 0xa4, 0x93,
                  0xaa, 0x75, 0x7c, 0xa3, 0xc2, 0xc4, 0xa4, 0x96, 0x93, 0x8f])
HONG_GENRES = [("short_play", "真人剧", "default"), ("comic_series", "漫剧", "comic_series"),
               ("ai_series", "AI剧", "ai_series")]
def hong_device_id():
    return str(1_000_000_000_000_000_000 + random.getrandbits(63) % 8_000_000_000_000_000_000)
def _rotl8(value, n):
    return ((value << n) | (value >> (8 - n))) & 0xFF
def _rev8(value):
    value = ((value & 0xF0) >> 4) | ((value & 0x0F) << 4)
    value = ((value & 0xCC) >> 2) | ((value & 0x33) << 2)
    value = ((value & 0xAA) >> 1) | ((value & 0x55) << 1)
    return value & 0xFF
def hong_sign(query_raw, body_bytes):
    timestamp = now()
    query_hash = hashlib.md5(query_raw.encode("utf-8")).digest()
    payload = bytearray(20)
    payload[0:4] = query_hash[0:4]
    stub = ""
    if body_bytes is not None:
        body_hash = hashlib.md5(body_bytes).digest()
        payload[4:8] = body_hash[0:4]
        stub = body_hash.hex().upper()
    payload[12:16] = bytes([0, 6, 11, 28])
    struct.pack_into(">I", payload, 16, timestamp)
    for index in range(20):
        payload[index] ^= HONG_KEY[index]
    for index in range(20):
        mixed = _rotl8(payload[index], 4) ^ payload[(index + 1) % 20]
        payload[index] = _rev8(mixed) ^ 0xFF ^ 20
    signature = bytes([0x84, 0x04, 0x40, 0x1c, 0, 0]) + bytes(payload)
    return signature.hex(), str(timestamp), stub
def hong_app_request(path, payload=None, timeout=15):
    state = cache_get("hong:state")
    if not state:
        state = {"device_id": hong_device_id(), "install_id": hong_device_id()}
        cache_set("hong:state", state, 86400)
    query = {
        "aid": "8662", "app_name": "novelread", "version_code": "73532", "version_name": "7.3.5.32",
        "manifest_version_code": "73532", "update_version_code": "73532", "channel": "update_64",
        "device_platform": "android", "os": "android", "ssmix": "a", "device_type": "25053RT47C",
        "device_brand": "Redmi", "language": "zh", "os_api": "36", "os_version": "16",
        "resolution": "1280*2772", "dpi": "520", "ac": "wifi",
        "device_id": state["device_id"], "iid": state["install_id"],
    }
    query["_rticket"] = str(int(time.time() * 1000))
    query_raw = urllib.parse.urlencode(query)
    body_bytes = None
    if payload is not None:
        body_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    signature, timestamp, stub = hong_sign(query_raw, body_bytes)
    headers = {
        "User-Agent": HONG_UA,
        "Accept": "application/json",
        "X-XS-From-Web": "0",
        "Sdk-Version": "2",
        "X-Gorgon": signature,
        "X-Khronos": timestamp,
        "X-SS-Req-Ticket": str(int(time.time() * 1000)),
    }
    if body_bytes is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        headers["X-SS-STUB"] = stub
    url = HONG_BASE + path + "?" + query_raw
    status, _, body = http_request(url, method="POST" if body_bytes is not None else "GET",
                                   headers=headers, data=body_bytes, timeout=timeout, verify=False)
    if status >= 400:
        raise RuntimeError("红果接口 HTTP %d" % status)
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        raise RuntimeError("红果接口返回非 JSON")
HOST = "https://api5-normal-sinfonlineb.fqnovel.com"
UA = "com.kylin.read/73532 (Linux; U; Android 16; zh_CN; PLK110; Build/; Cronet/TTNetVersion)"
MEDIA_UA = UA
EP = "mc-episode-v1:"
PROXY_TYPE = "mc_cenc"
APP_VERSION_CODE = "73532"
APP_VERSION_NAME = "7.3.5.32"
APP_UA = UA
EPISODE_PREFIX = EP
VIDEO_URL = HOST + "/novel/player/multi_video_model/v1/"
try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except Exception:
    hashes = None
    Cipher = algorithms = modes = None
try:
    from Crypto.Cipher import AES as CryptoAES
except Exception:
    CryptoAES = None
_VIDEO_ID = re.compile(r"\d{1,32}")
def _aes(key: bytes, iv: bytes, data: bytes, mode: str) -> bytes:
    if Cipher is not None:
        m = modes.CTR(iv) if mode == "ctr" else modes.CBC(iv)
        d = Cipher(algorithms.AES(key), m).decryptor()
        return d.update(data) + d.finalize()
    if CryptoAES is not None:
        if mode == "ctr":
            return CryptoAES.new(key, CryptoAES.MODE_CTR, nonce=b"", initial_value=iv).decrypt(data)
        return CryptoAES.new(key, CryptoAES.MODE_CBC, iv).decrypt(data)
    if mode == "ctr":
        return _aes_ctr_pure(key, iv, data)
    return aes_cbc_decrypt(data, key, iv)
class HongguoPluginError(RuntimeError):
    pass
def _text(value: Any) -> str:
    return str(value or "").strip()
def _first(*values: Any) -> str:
    for value in values:
        if isinstance(value, (list, tuple)):
            result = _first(*value)
        elif isinstance(value, Mapping):
            result = _first(
                value.get("url"),
                value.get("uri"),
                value.get("src"),
                value.get("download_url"),
                value.get("main_url"),
                value.get("backup_url"),
                value.get("backup_url_1"),
                value.get("play_addr"),
                value.get("url_list"),
            )
        else:
            result = _text(value)
        if result:
            return result
    return ""
def _json_response(status, headers, body) -> Any:
    if status >= 400:
        raise HongguoPluginError("上游响应 HTTP %d" % status)
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise HongguoPluginError("上游响应不是 JSON") from exc
def _media_url(item: Mapping[str, Any]) -> str:
    return _first(
        item.get("main_url"),
        item.get("backup_url"),
        item.get("backup_url_1"),
        item.get("play_addr"),
        item.get("url"),
    )
def _spade_value(item: Mapping[str, Any]) -> str:
    encrypt_info = item.get("encrypt_info")
    if not isinstance(encrypt_info, Mapping):
        encrypt_info = {}
    return _first(item.get("spade_a"), encrypt_info.get("spade_a"))
def derive_content_key(spade_b64: str) -> bytes:
    raw = _b64(spade_b64)
    if len(raw) < 3:
        raise HongguoPluginError("spade_a 太短")
    v8 = len(raw) - (raw[0] ^ raw[1] ^ raw[2]) + 47
    if v8 <= 0 or 1 + v8 > len(raw):
        v8 = len(raw) - 1
    if v8 < 33:
        raise HongguoPluginError("spade_a 长度异常")
    value = bytearray(raw[1 : 1 + v8])
    va, vb = 85, 246
    for index in range(v8):
        previous = va if index & 1 else vb
        if index & 1:
            va = value[index]
        else:
            vb = value[index]
        value[index] = (-21 - bin(index).count("1") + (previous ^ value[index])) & 0xFF
    try:
        return binascii.unhexlify(bytes(value[1:33]).decode("ascii"))
    except (ValueError, binascii.Error) as exc:
        raise HongguoPluginError("spade_a 密钥材料无效") from exc
def _find_box(data: memoryview, fourcc: bytes, start: int) -> tuple[int, int]:
    for index in range(max(4, start), len(data) - 4):
        if data[index : index + 4] != fourcc:
            continue
        size = struct.unpack(">I", data[index - 4 : index])[0]
        if size == 1 and index + 12 <= len(data):
            size = struct.unpack(">Q", data[index + 4 : index + 12])[0]
        if 8 <= size <= 5_000_000 and index - 4 + size <= len(data):
            return index - 4, size
    return -1, 0
def _box_body(data: memoryview, fourcc: bytes, start: int) -> memoryview | None:
    offset, size = _find_box(data, fourcc, start)
    return data[offset + 8 : offset + size] if offset >= 0 else None
def _parse_track(
    moov: memoryview,
    track_offset: int,
) -> tuple[list[int], list[int], list[int], list[int], int, int] | None:
    if track_offset < 0:
        return None
    stbl_offset, _ = _find_box(moov, b"stbl", track_offset + 8)
    if stbl_offset < 0:
        return None
    stsz = _box_body(moov, b"stsz", stbl_offset)
    stco = _box_body(moov, b"stco", stbl_offset)
    co64 = _box_body(moov, b"co64", stbl_offset)
    stsc = _box_body(moov, b"stsc", stbl_offset)
    saiz = _box_body(moov, b"saiz", stbl_offset)
    saio = _box_body(moov, b"saio", stbl_offset)
    if any(value is None for value in (stsz, stsc, saiz, saio)) or (
        stco is None and co64 is None
    ):
        return None
    assert stsz is not None and stsc is not None
    assert saiz is not None and saio is not None
    default_size = struct.unpack(">I", stsz[4:8])[0]
    sample_count = struct.unpack(">I", stsz[8:12])[0]
    sizes = (
        [default_size] * sample_count
        if default_size
        else [
            struct.unpack(">I", stsz[12 + index * 4 : 16 + index * 4])[0]
            for index in range(sample_count)
        ]
    )
    chunk_table = stco if stco is not None else co64
    assert chunk_table is not None
    chunk_count = struct.unpack(">I", chunk_table[4:8])[0]
    chunk_width = 4 if stco is not None else 8
    offsets = [
        int.from_bytes(
            chunk_table[
                8 + index * chunk_width : 8 + (index + 1) * chunk_width
            ],
            "big",
        )
        for index in range(chunk_count)
    ]
    entry_count = struct.unpack(">I", stsc[4:8])[0]
    entries = [
        (
            struct.unpack(">I", stsc[8 + index * 12 : 12 + index * 12])[0],
            struct.unpack(">I", stsc[12 + index * 12 : 16 + index * 12])[0],
        )
        for index in range(entry_count)
    ]
    chunk_samples = [0] * chunk_count
    for index, (first_chunk, samples_per_chunk) in enumerate(entries):
        end = entries[index + 1][0] - 1 if index + 1 < len(entries) else chunk_count
        for chunk in range(first_chunk - 1, min(end, chunk_count)):
            chunk_samples[chunk] = samples_per_chunk
    saiz_flags = int.from_bytes(saiz[1:4], "big")
    saiz_cursor = 12 if saiz_flags & 1 else 4
    if len(saiz) < saiz_cursor + 5:
        return None
    default_aux_size = saiz[saiz_cursor]
    aux_count = struct.unpack(">I", saiz[saiz_cursor + 1 : saiz_cursor + 5])[0]
    aux_sizes = (
        [default_aux_size] * aux_count
        if default_aux_size
        else [
            int(saiz[saiz_cursor + 5 + index])
            for index in range(aux_count)
            if saiz_cursor + 5 + index < len(saiz)
        ]
    )
    if len(aux_sizes) != aux_count:
        return None
    saio_flags = int.from_bytes(saio[1:4], "big")
    saio_cursor = 12 if saio_flags & 1 else 4
    offset_width = 8 if saio[0] == 1 else 4
    if len(saio) < saio_cursor + 4 + offset_width:
        return None
    entry_count = int.from_bytes(saio[saio_cursor : saio_cursor + 4], "big")
    if entry_count < 1:
        return None
    aux_offset = int.from_bytes(
        saio[saio_cursor + 4 : saio_cursor + 4 + offset_width],
        "big",
    )
    return sizes, offsets, chunk_samples, aux_sizes, aux_offset, sample_count
def _replace_fourcc(data: bytearray, old: bytes, new: bytes) -> None:
    position = 0
    while True:
        position = data.find(old, position)
        if position < 0:
            return
        data[position : position + len(old)] = new
        position += len(new)
def _replace_sinf(data: bytearray) -> None:
    position = 0
    while True:
        position = data.find(b"sinf", position)
        if position < 0:
            return
        if position >= 4:
            size = struct.unpack(">I", data[position - 4 : position])[0]
            end = position - 4 + size
            if 8 <= size < 50_000 and end <= len(data):
                data[position : position + 4] = b"free"
                data[position + 4 : end] = b"\x00" * max(0, end - position - 4)
                position = end
                continue
        position += 4
def decrypt_mp4_cenc(data: bytes, content_key: bytes) -> bytes:
    if len(content_key) != 16:
        raise HongguoPluginError("CENC 密钥长度错误")
    result = bytearray(data)
    if len(result) < 16:
        raise HongguoPluginError("MP4 数据过短")
    moov_start, moov_size = _find_box(memoryview(result), b"moov", 0)
    if moov_start < 0 or moov_size < 8:
        raise HongguoPluginError("MP4 moov 越界")
    moov = memoryview(result)[moov_start : moov_start + moov_size]
    tracks: list[int] = []
    track_search = 0
    while True:
        track, track_size = _find_box(moov, b"trak", track_search)
        if track < 0:
            break
        tracks.append(track)
        track_search = track + max(track_size, 8)
    decrypted_samples = 0
    for track in tracks:
        parsed = _parse_track(moov, track)
        if parsed is None:
            continue
        sizes, offsets, chunk_counts, aux_sizes, aux_offset, sample_count = parsed
        aux_size = sum(max(size, 8) for size in aux_sizes)
        if not sample_count or aux_offset < 0 or aux_offset + aux_size > len(result):
            continue
        aux = result[aux_offset : aux_offset + aux_size]
        sample_index = 0
        aux_index = 0
        for chunk_index, chunk_offset in enumerate(offsets):
            current = chunk_offset
            for _ in range(chunk_counts[chunk_index]):
                if sample_index >= sample_count or sample_index >= len(sizes):
                    break
                size = sizes[sample_index]
                if current + size > len(result):
                    raise HongguoPluginError("MP4 样本越界")
                if sample_index >= len(aux_sizes):
                    raise HongguoPluginError("MP4 辅助信息数量不足")
                entry_size = max(aux_sizes[sample_index], 8)
                iv = bytes(aux[aux_index : aux_index + min(entry_size, 8)]).ljust(
                    8, b"\0"
                ) + b"\0" * 8
                result[current : current + size] = _aes(
                    content_key, iv, bytes(result[current : current + size]), "ctr"
                )
                current += size
                sample_index += 1
                aux_index += entry_size
                decrypted_samples += 1
    if not decrypted_samples:
        raise HongguoPluginError("MP4 没有可解密的 CENC 样本")
    _replace_fourcc(result, b"encv", b"hvc1")
    _replace_fourcc(result, b"enca", b"mp4a")
    _replace_sinf(result)
    return bytes(result)
def _b64(value: str) -> bytes:
    text = _text(value)
    text += "=" * (-len(text) % 4)
    try:
        return base64.b64decode(text)
    except (ValueError, binascii.Error):
        return base64.urlsafe_b64decode(text)
def _branch_one_bytes() -> bytes:
    if not hasattr(_branch_one_bytes, "value"):
        _branch_one_bytes.value = lzma.decompress(base64.b85decode(_BRANCH_ONE_B85))
    return _branch_one_bytes.value
_BRANCH_ONE_B85 = (
    '{Wp48S^xk9=GL@E0stWa761SMbT8$j;R-wN{#^houf7QIIVU7<Ew*6C3?&vQR7`VixMIZH9HyzSRN)dgt5HsOFl)*@6hSxGmq5aA'
    'QqcTJ>uEXt3ca?@+^++8<`vdWaS1a!^(@3piHN^UDea^utz&m68PwK)la*43U*mNYT~Az3vWRR9M@u9%`>|`oTuVAm{6Xbi7<B{L'
    '+9%}E{{R4tW;N$iTuuPgJ`u;tZ?qE#6f{J&gM{zloCXZoG-hquoMj#I1srY?B&~p9xgbUzb@!5*4S7ma&y#>iUoW)6rJ_BOyLIpL'
    'xODyDEOHDUy)Hr^$hEEodD$hbGrZQIEu8`Tb_H;~Z>VMWKW5~p-hONtZJoi*u&tO=m69!Z>V7E`+W`F%rB6Z`>9J*SJ%Azqgna;j'
    'pyLxZi;ycJaM~j<o%H|7!w`?YyEm7i6pMnWxuw4z`~B6UKR|wY@2gl<iXrJDd{_1*$qp;ibMN}xIL<*Gi$aI_ToO8niDZ|W6uz1!'
    '%)Ofu3qfRq1h1p__0g|vqG(?;aP76#`-*@WsTbSc98!AL83wt_4q^NHqSkY?D&ko53i_{F9n~l_{x^5C{H|fMAIX4f`wb7ERjZ3y'
    '+#;VMHu5P=Jv3&yp^-ASDTXYC%$TxN7n?j-=xsY0676yMQ)eWeYkG3JD<>_>t{HhAIxC^4(?8&VcUx=ux(qrgcIAXU5Yosc?z1$('
    'FqfP|)2$ve(&}uw;(uxdO>E6dMMn^`79eTmC_B=qkOB^y=1A8sQi<MgW~fDdW0t4{^<IjM^J?x<&Z1M)pYO&uEA!yRw?Np_Eoi{o'
    'V9dD%VA6x*g>j#h5;4}+#ILn~##Qh5V8-%l`Cgcy0u7DR!N$07Q0#BWZ9icP<a5UiL*HS#iW;QiR{)ut8&c9ibCtR^s-hvxT<B5I'
    'pZF*<3Mz685I{5Bn03e7@&D%xea0+oBiI=#Ay^38D377%<QuMZ-O*%Tv;8|=X7k@BR9~m7iE|@?x%zlQ3NE968S;+Y@OKTIO1nRQ'
    '%$PlmG26EWG&hsL(A8Kvzr*S5Ay&gwR^Qs5EP|lmJc;6eX{5+3>-W3P^XQYY)|Xa<5v$^`p|naVLW^*4x>oTf$}?2%{6bD};l{wp'
    'UXx&>{O<J~x}|>(!V18p93xBW_5+H#yeu03vRjESLXD$A9{yVQwj)I(NohO>ORrTjPEA{?DAU0dxSX!K7471{McHXwNi-H;o*fS{'
    'A^u%?y|GH!Rj#yLuLt`!o<Kf)Y(ZpN4Tz3<fO`#$DE7bF-%oqDst*3_DWg8nZiEfL0Og$<i9XRgsx?2^G>t{jYLYX|a)tAG>|ahQ'
    '(CvT4r8nG+e1c=US5#<;4qieQKmF}v#Lir5E|do?DhNZDSa32d|8J@+jja&PG#}{s>QAtW@PV$U?q=(1XE9c#V$_wg+bp&V&B)eE'
    'w|E7%&@=fW46%KQT|hx-6(^7@;GSAuQiVAKWj{$=N<Dko+Tu^~&_g4k&tWyT+RiABes%c{2GlZizn~-ml%l&HeCQ7Y89{*{FhFJ$'
    '%A0T5Ok9YTqU!Y`FOD0Vll<93GAUvEw{f##S5Na@_<&-g^C8;XNP;Jns4P4`9G&OuVy9F{ye}9pZXFBGaV{9GqWseFXXDkv-Jtr#'
    'X`v5*<V}u7WzA@LlIItpV&L%Dnu!B`Tlz^fO$|&4Ecr^f5@l|Pk*?l`Q0k`=`(J9}mTP!oxXK|5+g>iFaV|-^t;>U+e*p}pUxsGg'
    'R<;C@A<@#B?1bIdg$yI+yA6AxY23cPa12A79#Fv)!=h0N+GRs0Kg078`}Jx76kkmF2?7`fU$Lt8m3@5>LUp7)McaOF3%leJQMA(V'
    'z#j;PC$N!2YwiDp$FdZE3B6)aNBYUa(TNaoy8X~=byBHab^*nv9%*}Rf54ca_b0AXoR_G3a@6Q#ZFpU^6?~3S9&n|oyDT=y+-aSh'
    'n_@mxq0;KkI{N4=aOj0w-G;T1{5|jUk~rpYu}~n&xeXONR{x@w=wxoIjOh3^cwp6#*_zNzKwGmt%gS9r?F8cMjKT$lB|br+51yB2'
    '=wZV7fy7D{`(29#`6Q#QIa%hm)is>KD_ry#_H*-F*|Z?%Qv8Wrj@X=do{p=*x3Fz@7wS7@0b~~-n@Ufde^yLqtQCm?0O`Da6nn-j'
    'r9Pog2fjAFwY<gel`&!+$DANDLZf`IKhg4BZGPdEYX1n!8rS+gQ7lP{?{KO45vsUu2dS7*+lGbck?L*-g91mpEav%V%JY1;m@7bb'
    '!~8*@(PmIx$hM4)kQD#-N9l_sU8UpQyq;#!2cR64Gr9}3BImqV(P!p6uw?K%E^%~`2F*P-WIQ3uw-kIk4m<8@RYF5W+XhoQx`p6k'
    '+9I#{E}8>IJkyQ%q6436nF9t#Lsz;}b$hp5{_)$_DwZec8D&xJpU4!-(s}b112NIK72XtvrrGX22}y~3_iro{&MnhETA+DaK?Xi('
    'Q0J_&dFeJ5#7fK#kt7e^e@c1D7iOsd7Y$~wsRTJ#qi|^(h#yWd2}FIU8B9IG^z<X74^tO-6ur(^CZ13AW`UFbC{Pe%@)oIN45MqI'
    'PHdq9D!Kbze*P?h!OC)3qiB!l?49WS?)rHvoGtFxap`)w1=tf8AMQ5IfrG3!9*(uQp>&-907)*(j!(qXjiLbP^#}@|w33k4F~`7m'
    'K~fLbR%d?z%hl(M*M#B6)+ez&D3$JDYg5AF2vDMPEE2G;dt-P!gtE!qaJ41%TjxghS@IBUwUEIbBB|AJ4?hq}BLavJ+^|F^sE80o'
    'uLA?B96n!Yic+9jWQ6baLx|+P0BjCKJP6CmKDt5GssWs1oekHG4ifxLAKG`*ebaE=-5kobMB}Pz;R0REqN-x}q3%W$B*jB?E{A%B'
    '2MhzK1%uoumz1tpa`{9cjKqgYo(@1|z(N)PeGvIibln>rkSAlt;@TjZ46mVE-PxOR1;;0DloppysYZl<liKBRKRt?9$YPa;+3T}O'
    'tk(2rC{(dZQ`ym+rqP^|wr0OI>e6G|A!P|?bB1T7wCbzf01t(nEUGrFWjeMlraZ}~O%Xn~3S`Ij?3XhZJj44r^n=^V1+N&4lbxGo'
    '0!x)@u1Oh2G558Kzoz_xRv^@R+Sg`Cz7G*Hrru<u)3M&MHearUo8*q=Tm|q>F#dZW2&@Gr5H7wXs&LAz?4wE7`UwBTRkeMY-w&~x'
    'xYPt=bzf(89ffpeR@daZBH>+i&9AQXz8Ag>QY~)CA!cmHgH<ADaviZ)5dYJuj+}hxlHaonh`lzE$v|TZ2F?t}1iK6w3;xx3i`k5E'
    '3fT8$h)$9gl59pjn9!Wyy(CiSm)fITqjj_HC6bB*xqNUV@F%^;AJG{&N#upHz)q{2eGtJ{3Vt*~?n6mbI5?3tt&&kjlS^Jk`5AKk'
    'stC&F!}ev&(y?w&Bj#pL<xuFqZlgCPdA=?Pv0St5C9@`p^%+}>PV`CM4&WXiAA=p%;HSE^I8hyHb@HbJlKm9(B<&rvxIdWJ!Ra`W'
    'hBT1d#{e#>cz9y9sU9Z>FD5Whu?djyd$z^Ls@m~rs_#3A*V$?hFlmO6p0uz~8wP--L+&#T9-XiXKJ4AQ%8r0jK1b6h*9Wi$-*5_l'
    'O#gg!K%y%um(KnRmO)=2JlcF+X}hP7Gn{v@AW+9!+?D4&s3dzwJ?<}0CzFsHw)I`q@f#x}7%g)SCviR=d%M!Rmu0E64)p8)od~J;'
    '`uAVx3hx(ZmT&ZB5FN_#N-S9Eo!g%GuzQb%boa1Ar5RHkT*|?FDT530rxbxdzA|UYb0wSBm%7Qn@nee@gz=>xU=<{_-qSfw5uiL;'
    'Mw2t@X*I@v5gyeO;Azw^vnq!jZL<eeC#YGoyR%FFGgKx7>CTY%Y{$jEnTUhmlE>vWa&xR^daeIgtPS9t@UxM+5D(jQtQ_K#m>{iU'
    'O?L(Lsk3<&K&Ums!V4(!0{&6z@!u^0I%2ikvMuCv?M%o^RU4iL9Ul=Tq`Qq@Y|gl{oFV~Pg{3!t#0?>Pb^@f|3o+DkcL3`=U&&99'
    'n1ipU;k(6$Nz26d3+X9kD2Xa;);f=qm`iT8!@&Qu*cJ5i_@Hd;W4ON2#^@~rt|oiREpd1zc0fLvL#d((Kta6BI3vAn-V@xZV6?gw'
    'BF+>*#3Zvm$iZ0&*L4xFf>P65Fs@w&+C#wM^s41lRJlT>3OUK+H|^M(l{gmrAm#*VIo*I{)6)`Nzr6!nmw#7l;a=;Tn6ly2vS7=!'
    '4~fE_r9)9&$7RnSmaUHleEM)gsGR)UePI2Z;ewO0?U{4Hj^NSpP?ZKTS1ny~#up6i*JvMIBxfjm6!LI8GWXS)_4~GP0Tc`k@RHlb'
    '?H*yz0Ro+%R`J|{HtsE%xxbx|k*{5o_xZfD-4bteruCah1ep@1vlv6^uCy1}`{fpW42@`+Mu;V?l$yPujd?<|dg(yXnEsC)#1?($'
    'zKI!)WJ{_o-+z`%>g@GCWa}v981h|wyGx=%oNo$4GCZGs6t-$my{R~~VT)-|t0xOmFH*mG*~zgs#tB&P;ZmopQC~^2%k>{0d<p}3'
    'yiuQU#kl%qM@J@o1s$0?AI$+a`tuRJtV4h2xCDaOMA266*nM}E2{;$JcVMOTdlEtNJv@?I-2L%@2q=VCUrysWM}fF%iaD0e+pt)O'
    '8cDVSi$j093_3X&BFLbb<ehj->IwfZ|8hkc56tni&2PBSpf)>hw3C=z-?+kQb#d26(o17askq>W4Pr};0!JE#@sxOF9my2)h<;cb'
    'qT6pG$%k6+f=FhWam9}cQRXZN5wlU$%U1vcZ{jIriu^h(0M*xQrm~b4xv+A)2*h{|*OUZHRs|f|)GEKa&*g~)W2TtT@sp!Yi~Jp6'
    'wj$ze7Qh-nn-d7f*<Tva>4;;Fh?D`p1icS86F*iA9ztj-WD$>79%gsB#1FbG{_>5LsYa?X69@8s3xd{bEr<N~$Y>`6YU0#ux0)++'
    '_%@p1W~Su8mIu&SDyjn!G5Qr|8K|Nb9}JFJojQ+6p^;w+uT6lnyKtZS=3elR)`hl>nFV_s<6^h;+(3*4)YFb;uPh2sE(;xkw=o({'
    'rYtN4S@zdyB7&z_aWQZ;0%0E*48M`@aATEdR@V13+j;5YhV?niH+U<3IVS)kl|v>n;TU6E(jG84m^*Zt2HF%yZ60921r25wAoevU'
    'fmk@6FhGsIlMK1CsV8Jm4?>-}sW4nU_xov}%a{Q;0GBl>+%-!r4`9mrOw6!D_zy3Kwa6^~rCkp^A1C1|-Jv*l9M=p(toY6>j|X}F'
    '&J*W-E$Lo`K*Nd<EoHO-T}2;3saoc$h$~Cga?D2<*&5Hg46wV3^&u}eJhkX|agkeS8;CBK7iTXMl!@!z3#Xf2x*z*nF)B7N^U=Vx'
    'B1}XSW_z$tJhrx*(Dmrr(Zpe6?bMoEU}Hd$5nq02d;8BUsG-9!=<GO0R|^ib3p+0%`}yu_v~J#U1ypv5yk<wJ>O**eB~TiY`XMSO'
    'jw!2tgE@FcbNS9HRi#}gs*>CRWVgjZ+WHLslM%L{zLlX8<O*U*kHTO10bKQ!rz((U%!zunm{*;U4v`f=tki_GYSn_(WA2Q8P=Uk7'
    'YSNM`v$C{T^NR!Hx9ak32Of6EQM^virk&Mt_!gSCwpt|c<Bx7L(PQoVzQ$tp*1$Qn_;wc}g~yzw-duDWuhv`_SQ;@;W)swM@m4Vb'
    'W8AezVn#N9$eYHZ>k>UAErfG>z6II2{1c-NL1G~)I^m>#6?6%=NdcxVnD#ni3uWui)jx9C4=W~kLY|Oe*bewS|N8*!A|#x($!+mR'
    '&gaDU{A&eA&TJ~XwQ`Fl%NrdX4IS10ui2`WfEQ~bHe>|0ky9r;QeKb->WHB`kP<Z+-rb-v6%0~3m7?si`($DP(UgVNbXscA-z7T&'
    'BXqY|qYp+5s?p-tV9KAT`%Lp&5FG+vd$KsO$q>(B+bZ<Ei~zr+3)btP8>-ZV!rzOtPOZt8Tzpn97eQ+wLh9Tl!))xz{-b2}kkE)X'
    'EJG1G<A2Xjg)~Ie>3IPJPD;I6su@*;N(}z!o7+h>cAl{jEcZ2<pFrdhcbK-&I%8!iASA~9B`vDzLN3vW`c883<BT$M^gS3-#&^WI'
    'LaPGGG|E;t&g46)d;@BlL&Y*3TS~FomoxyY%V}Pk=!S-=MV^{`_4HbM-h9Yp8TC*Z1}*{l<!U)PYL@jc@=-i0{QK6{pE8y3AC#bp'
    'l9ydw1bx^a*@@o{E{{lozQxm*zb2_;&9t(7?XIcrpX$(_zxvcvGE?2(4pMG#-_Z%)u7M(X#=t?VqDUmnx$qkPx5p43&eK|G@e;E*'
    'bjQLK!U%%6Tou#CZjwn|W-T|PT}A8LCPa(L@7n%1m>lfCJ3Ne0NKDBGgit}LYoOSmsl1ef0PEllmj*@Js#r6w08Lh9+bSeom$_*!'
    '5|r6Y4Dx}JPapC_RA{VAT|+ZpKEEoA@4)`4S6pmCKGSZTTrRNRB@V7-ucDbG4nM^oJlA)h97s`h>~c&iC{2ig!d1#Ms|2EpI4<pg'
    '5{k+uapUbX&0|$96o+LU(VI+VYjGtVqIV$Uh3`7JiA?nYTAi`>VS+bD+GS(^tdl5+xK6nJ(&b5xU~owi2wxtJwuQfZM9MOwx0S&Y'
    '0M|tBN1P+_SY#BSCCwPqU4kW7U(8c0F&W4nF1xcA91f)B#zz{gL3*#w7izhnq>*o-vc{mLA5QT^YFI*ri12A+GoT(*4sD|;Di3L;'
    'ddvAmG-l-X;ZAVo5xfgM2m#Lip2TfW%kJ?d*tAJDuo;B0EcW}mr$d+~fQI<{!iGQe0|xatE}eU4w=svBpHR<fP(6WoFy&FT8NGV8'
    '(&Q+7Y;%mbwDXyAtMj{#^RRn?x;8cRw3_SKOUhQYa!+q1OWqIlj)JZrOT^1u$Bu;$Y{3nEyc7#(9Oelrup)4yx6w}}2nJRD4O|)s'
    '%rB{_+nfdK5eNdcBW`Z9BIod+IMwsclUxn(!bp2P0C7SD8_EA1q+IBikyuTHEyw!3xuIJaTvfb8c7EPcg_1Q!C~I+Tu`$dQ^{tD8'
    'gUR^F@;|pVI(>9nV9L4ct5-EG*Q2vOh7|QvY@fsu-mx4=)2$W&H%Bv*6Pkqo!X)sGUjZ*w?($clu1BKNR!cvm&l_A4!QaMjH<)|8'
    'n~62K-9(7nUGvuX);0QFvfsj__uhI8O;kdf<L3V*IPRzzDHf|ly5R+Y${!EQG?PpmLmZcy7n{u5$Ua0QuI(2yZsq;qPVdC}peq^0'
    'z<@pjzs`{sAq=EiGu9Zu+w$ZG0ss(;51f8bw)di87Zb5v+Ng67DfaSH=IO^;AYi6tkt^qUHR;7g(k?Vefu`^xoQN4#U)%-JB;8EM'
    'fQT`aG&H`LFoR8qO}2be^6`gmM;n?H_TU9O4M)BE6(zNvxy&tDQKK}R@Gy?a8rvU7vhZ$)+ei#!QQJ+GjyN1|T=)K-%FGHQA}M(+'
    '{CK+xt4R$YYgYPkZ+(JWiO4IwTumqD+v@f?=)w_CvftQMa>TFkgOHe@qOnFRSEJtXUJpu+LXnR*N4v`Q83l2{m1<!7cv4+eKzRpV'
    '2($w<QJ-5OPeQ6Sbs3`oUsgo-SIo}`aMI5R709Et|3kbwyohKtqkky8-SiNU-g&<Xqi5x&!-HhOoNw8lf3gR}HgICxVvi_#kSC9)'
    'wB!Ay+V?oB77Gr3qCQPEpF`s{=+%{~77M(Qz%mS?J$rj8RIJhq*k~4KsnvBFZi)F2=<j9bv;N`cK71xsd^U=)`imfOGvOI6yCL9t'
    'u&`eXa1#S>pvspU*&UREpagCvg(lKkm+jlKin}pFVycXE6L%w(vH&1}baI9hBwpzi>I<c3v>O466<?IPbZQ=$JR~w7xp*k*VFacd'
    'Ev$B@D+QyksU7=6>7L%@%{_50Sj9%@XzeAAOqip=#fq?ykn4q)2(|F|?HnUV5;G%>lG*m}Au;xPFQ4(+j;)-1SD^9BtFjE^O?z}w'
    'uU|!m6Hy#z2M>UblgTLeaF%`8f16wkT><Ui+TSp}e70Y3l6@Zywj0Dv=uQd*K9?KRag-yLHji0#P!`p}>fnKbEb?e@em~s>XttyK'
    ')TceKHQ-~Tnz{k+grpi-x2T;K=yM_^%S`iDEe!1{lj%g!G~tdPIc}F1V7n8}8Nk*~w27SR70RK(##!BZ^@G6-XQEb<XjCmyJeW|2'
    'XX0>9t|3(uBG74aC&5gMh<}|_L8@RrOvt1qn^KyK5@*eAErDMMa|H4mlpeX~;P@EIw^#%8$Fs3W*5yK!O*hzqcb-^@pHmxbYO?i7'
    '&%4x!c>e_}-F<nWRhBR%3=2)xzCHs^{<K7x*m|<326#w9!z`yerW1}xe5UXui?A2ej9YGoX%gTbL03dT!(E(sf>%GGS6Z3v%bqA9'
    '4&dC6(7GuQAaO7{=>r%0nX@Q*tc%Q^bME5x!^o=9e2DXGmRdV?tK*Ze`U*vd^Cc)i6G=%2lu6SA329j44pM323>Q}aW6O}TIN}PJ'
    '(Y^EKmiAHwt}ZeXj;B$)P;W3qGjf*z6K>R6{s4ufaa%$47e&d32a{7%7`^=alj<NPhZ@hrzhw;a#18X!#z3;X>ldOIo_7_`9PMfV'
    '<86~9RK11O2Dr2@VfeqJ)icEr(oVh{jrh*<GEoJ|tt|5^L>o6W7ZNCf8jo-ka?*2<v*ArvW?28ls)^>>c9zWz4|pJ^$coH__5~}='
    'Mj)2(s#paw69f{;*cw2J!qurM{7Qwa!$noN5)<Y#1iWs;q8UC~2obh<a3<t9LyEgExq<yEfT4Mm(C+LE$m6s3$VS9bKkfQ)EW0|@'
    '!lyspCdGd}*}LySa=mo}lm^U7;%hc6_b*`k*A>PTcp)EoZhP@)Myju?zy}cv6x0d0J+gd~7-ByisLI|O>X~<X^2b7+uyX?^w|Qy#'
    'cod8xtTucA9uQ#BEVOLX@^ZZJDym^TA&G^UOd-BN3&jFO%zpa1qAQBQ$2$KwYFL7gnc?1|NCtBU)c5g*+y+O?9GPn%0BPvtEY&Zk'
    'Y906LZ{vwED1*AK5pGUF)e!*f0FPgD(Ecs+F0R<)qqRk)^WcrAhga_e#QaKU7;tDMj0Qi0)yCV!K&A&}V+zYx9w#aTHoOz6Ws^NO'
    'e}@L5x^ldz@k_mQM9=dhSxYFr*K1pdF&=LR3FTQz=m0rD>HCtJRO%=b97P3M=iYoR9501E+f|zhkdjB-ml5ulYLJmy$;X})JU$+3'
    'zyNT=s|&ZPb^&RRoPE7Wytzt^5i^-iyOFQO{2n1MjAr68i#lYjQNZ>4=eooL+zpM&E4Jkv6N6AKqDj9<zDA8vb>hEF2H3f)Ehqph'
    'I$`&19~xp|KthQK>8t|DOAF0Fq&AUnTMuf6Q`n`VsVE(_4L~E!cl}FQDg=W+@HIkucI9Q2%PY>X`q)7P!lf>fPm4&yX5&a%bZKEy'
    'm}FRrxHg!l1$y9y<eVyWWULXlDoC2j#@XxmXGO+0F>Ss$ukj&~twB;p_?hAab<M?AcX8KE2>Q`}9Mgt9Y23OF3A&X_>oGi<n#;$j'
    'BEXenz0@hx%7?+1$S)@(_&&O+g8x<~E>GXT>tUe>LAG~6d7{>2=VA?$j2svmjI9LncaGVXPfjK{J9fDKJ}7Z+(7%Sy;<ZL>Z?g;K'
    '7rYq|cO>Ma^A(!fsLpc`Ov($85(=_aJTcHz>vfvj)8LIb_vkeqBjdiddaQl$Cgs@;xAk@-%pjZ7;VnIFoD7wecc47Pj<RPokEU=w'
    'k{h%I+G>S4z<AO|;h%k8`JLh<>81ELs8~#u1ku8y@4?1EzR}~D^1Xc-^Z2{`=hMlANbzs{o6#@S2T!_-b^~V`zxQ4kKB^mHF*;r*'
    '6Y@H<<CsJa#Oq9;Y*T66-+(OWBOb*~$-hGY(K7#g?h&LUPT{hU3VT6*2i0(+uiRoUs&{rWb7?y8c*ao7<8qnl%F@!3zh{8F`$Gg&'
    'b6*)k5j6>d&y(Wf(Y&q8zyyKBlvy}_Y&I{%!f#$Dgrs}F>QGh*hn2}#WNst6!Q?wz%p0W6njR>>cz6a+No<0vS!G=N!4Y^o+q-*U'
    'yD$@p!i|$I@`{X;v1fX|k5z*J{TaL8RKb)T!vpi_gd$?mOSdG)%3qc4ix46SfP;eZM#Ii((=+We!%sKq3UCXmEEi`{eY;(`rmdqV'
    '9;(y1{6niqWj$+zPeg4?MY__EReO|KGj2}I%NObBmiEKx{CB!o=SIv4ZU2KJOMhs^ZQqbs7obl9^|8){XqaNp+(039&^000Sa^h&'
    '24%u1SGd{X;_&jh|1^|z3t%L-=xP*V!u%w_`$IegUxv>39@ku+aJiCq1DyW6ayl{SLUVR268{cZ7$oh(Yh~pAabC9C3`>B^8i3jw'
    'cgyaT1*d%;V&x2?QGZSpJyN+@7O?W_)zWXN34Eoez%c<|^4mu<_KPoCRvjokm69iJ4ACJ``8J)wK6{|9dL=2{C6~&fSHc!~4x&mH'
    '_m^imaD|EzFcow!V^y|CI~T6}1`sCH{ZqL`LG|rvl7UeLtOOY@id@bc${0dnFCBGw(}}p5kA*qB*?g^Av553SNeW~CO`9#pr~P~q'
    '%2(z1>q&+-X%*JJebW#_MD4<r^+IaE>N8WZk!u)-rsr(5H2#)1>;iC;@*8I^B<*_|q=T2tOtpm+K=Fe3%P2`ymsz;GR59Gb&>srW'
    'k#lwi!x3Q1M?^Q_<cIisHUzTJY$N3z)A9V)KS%uUyAm9`?zuUXoQ8vEg0n7WrlI?l*AF8zz>enuOH=X*9c}(leKhA-qQ;462_!#*'
    'Pe?r;M_4Nwfd6-`X_Fb!6PT-;zt-+O=^Jz`-JR1V@B4I>eR+ho00s6eD;9FgSLqH1wV%@F^$gs>b_zxfvulv|;zIweZ5Vbbca$B6'
    's@#B6JERzQvsUQ5FOrX6>Ta#RVTbm@km0(utG&Ke1hcv4<CvH{mGy&ILfBTA0o8ZZ1yM{x%H^Or5jf6J?=L-8d`Ya2m=(uTGO(Da'
    '+OM)bRzW@xBd(3xkWyM7Sk5&>&zdr8=7AX+Cb8!iUv`?$Cq*}DTOxb>yY`v7Cd1^lBF*GQTHc<l`m>8cuX*^|dmbpr#7tt6J$t`2'
    'h)c&z03gs}>eWqo9~BsDzYw8VZ6t&9<r_cb_PL<iu1K~&p<x4ObUO@n)&_pV((HP8j(!4Ww}-b-@l3#jzoJ^zW)Jo46N+raSUzhe'
    'o4wrTSZg;LJ1h4I{|#Q%(7-J<6D|@$s3p&ODUo<=7_k%O=0@CARS{8;_fY&6rPJsyQsdN=7DTusc*zmfTSW#9-e%EgiE9KQAk5kw'
    'P#)s%h|B`?%7FRrlADbY5i^sEZ?Mf2zcdq{@_fYD`^h=Lb+Tf><b*ta)$~*?$wYK3e83b!e%;JNFx@0zqOzKQZvWwq$BWy6$9API'
    'VZFw%dKnNS5G{^7$afAKLlLTtPwQCM61v<iaU7i84HGLfXsmQlak5RJ43|%i0sgQ!s?GS>oB-kd;m}c>Izd7vAu#xnYZ<?hz~f&_'
    'MO+7}p@|VlWy(`;rl}eCv@HpK9@mUp=M^5uaE0Z4`=_CWa2@hJV<v*B=N%VWl=bFii>TO{a)*YzAsX^Qw(@XZj})i?G07nV$&I;u'
    '%-}gIAIQPL7P;M2&tpL#^K}aqG%oNFJ061=`7vO4x-ZAbJcX|RkE@67);I>}p(7-Ot61m>5`pjRH#8yI+EnmtUM@g1|3oI-8o7kQ'
    'XFxJ3X{~ep;*5O>;?GCGNf3Ik+hbD|lDo}<_L0>GCo1cOkABa4L!<<fmJ!BQ?Hf-8V!dr8IOEP$F}zZBcRVol^D#-;-~Eq0?l>eU'
    'DiRZy@DdfK8_H;A2RBmyBu5ZmFRm|Kh^9CX2Dc?c6B)~b(4p0LX-x-@DseT}jD`^fcOOR9jVk-wZE`NTC<l2ZQJWS7TvShg%Z(*E'
    'r{T;Db4-Z)Wjw`1c%U1gbN9^OAQQkl>?z!~Skzxz2-410{ur4^P<f)v|DZ}t_132kScw^ni-t%9k9XMrWAC*RoMY0gP2|l7wl?CI'
    'fX=R%qA=dXXCFt;2%Z3h9<+nW(5GWU%O+DyU5xND_xM+(3p4ggSuW|atHu^~y)H0&E|IuYsXqh3h}*P;fn&8WyoXi?V)la^6zOKu'
    '0vPp6HamL%z_>17CZsM5cApJR_U{*36Rh0h1qlg3`kuxmj1&4b_-W|F?OQDMg~ISMnec^>kZuYed)n)eYCT;B;t?v6o&>CS{dIJm'
    'h+srIc=rKUx*PB&ReQB1P*m=|g>X^-8n@c_m4^3iHpF~BR2j1EI74nv+CT=J`mNSK0i?*esv~zHAWK1x+Z%Yz5%)Oas!b@;O^G+P'
    'Scz$&p&^ff`xXeMo?%gXzQkm3#=HuMGK?FzmL!C?%B#M|2k{G&_vC)4OZVM28#w-UaR0hi;XXd01qr7u-w6jPmXxv^G669<bmU^g'
    'k+MH?ay-OD9|W;<mF$7y>9cdq_xA7mS@3B-o8AmW1LfQ1--jU<l8po8B(RMIo!<!Fb{Lh&1{Sgq+Uh1dOGN;4W@+k{BojfHpr&UA'
    'oO%t3YNigNl<aCMd9FH7xz7`w_R8vdsng;ID{aN*OoF$jqkTB3IEb2X4@4`kt`e3B+FVzcN>}%nDEQnRap1LS{?U~c4DpUHhY0S6'
    'A25$sj&A}-vlo!^Aj7uuHfJo4AF9&@aQcBJGxwBs1gSWVx_uERU~L*5S%AWc0x{~y*^HAe`tvS8B{lhL!;4_w)`h|Gd}2C3lNnXv'
    'D%j)-sc+g0Yqn=4?L9(NP}4E9ad&rw1)lI%AV*+j7sEtnt4A5pN*{C(Jf&<7xN1};$2>_POQ;>Il&(22NkLQ`Bou-_`OI(4!JWTL'
    'RXZircVC}Jyq>2M4z=*F(Jj?T{Zv>@X{h!2aAq<jyp7FRb2c9oI^0V46t%WfhFk;cd#qtsl+541VDLDia;TeZg(OgpD#k_6MMBC9'
    'VKMoyj--blBNw>I`O+zniuZIe{-amNawhrOslk5blTTIXyeg)+>r|=?Qr<-t!EHSMqlhJI4%Nkm3hZ_Y-<|;Im_2<>Q?cf3YCTp}'
    'xD9UFPR6GR*P6ZhzS25DiP4&TSD<oQpT!6Gs>7Ce$--6qbV_n?RF?+>$8I2x5+}Wy!@D3%z@X%J!!nS-qms$q)YOrjaNG@3F2JeI'
    'B11G89c#!QRdEil3SS2Dcnx1iDNx4pwR7xdP$NK)7b!FPocY>_k@q|ua8R;6)J3Qk0h+YL_iRENH_!Lu9RP3h3_ksx^LPNmXlY!{'
    '7y`-skrRe=0^nqUEM%ZKm{T+YFg+{ama`H$UfOu|Wo}{~Q`BSA6bB`&x3baJSvimiBd(B5ZRC?ntIf;FDi^~|FS~vN;b7}SAjEQE'
    'NTqu30xy1@Wo%8r|4vgb{Yrd0;iN5E6jIh5Rqv4W^h#gT-7@MKFZ93v`_3A;JN=uCYZaY$MbH~=2QSWKOa(W-8el4Rrqrw}0UqvW'
    'P{g<?Bt(*K@H)3PwgsJ2FAd%whMYD`#D{0sxpx!Y>0e+C5|+DNKFUJcasKKjYAptG%7uRTSR<4>lHQWJAhTvl%mRf9J|F2jA1VCT'
    'gN{3cA?R97Pqm#W3xbIEg_2nC;2x1T=Vnp5tTwP{Ju9N9BufCnfhrWLxnbVa>Nbg9{u4TMXk;+<XO)1>SDrjnN^zdI7K@#L(GW}r'
    '1$=l=ni>jyarNmc<82Z4`)X3yy%w^5i0Y*JfayxJ_Qa-04?vh6Fk8s&`+ej56KkW=49@=^@F07CsUMw7*jhgv%4+P~bl*CSz{!U>'
    '0tv<kS^Y)vpjZ06U*eTPN8;lIA4NNo?DdCQvS8?5w3-@;=+Ev%Ll7Ej!x$LO$sz?n@I4~$|0`L`SQ_;kZ5CSY<Kxa0^i9u|s|~Nw'
    '1~5HbpuddQ^Ls>0M2!hDjcBkR`HCnm|M4_Zd35d!3Jl}iy}c@|KWWRIr=Ay^i6q}#uB|s`G+6{D7!;GO>PnRIcm8C2<lYzvT>lJ%'
    'g-Qxx`=^<B{^573Eqcl#pWtT(pe$O5MQlBxkJGtydEiQN5yXoyI~4#ukHZgC6_hqaouEeiEDV^SV}&gd_|Kg2iBR}rqVapm%xvks'
    '+_d?6R;8{Ne?lt&9&8h|bep_%wskas-S03-<Dd#?cRAcX=fQi)-~%&vdi_wzuc=b0-Cn15PCxDt`9i|kR}P(Ix=cz`W-phCNH*|C'
    '$~;?wMTXi1Wr%iOGm&&`tjV30f-9zi!?Rg$!A5>w8HU%ynm-43nYiihePYn9HOx^R;5HPrpPdt^;t*iC0Of7gK}Chl1FPoEOA`_^'
    'm17c>k;23<nRV#)K<e9zZ=+#20%d|kP6k?-Sme<)C;_s546EzYujIh88D_MVwUz6H?>UIcHHbN9-H*(*c5_<;4{9T#v6(WzF3$t;'
    'EYj9-3GTeJBGZiFNKfZ5l*&M>sm0<WfGpwL!Q2|l$&f=h<<)TL9cRRh%(r#<`*CAPYAhKG_Du3T9W0QY!RxRsj@S+GJ=_sC>VdpN'
    'ME!|1EI0i7DC!}j!F=O0{r#|e;TmN9x9#V+$?D?@8kBrC7+}JyX^5r$l(6F_olq+fQsDS`-zif_4dt3f)<beuhGeLPfZo&KLAPMw'
    'M=(g;79BJhMQwx#5*JRT^S8QQv+p)GzL&Q~$>C5IDd)a9lO|(VGa#SQD6ufB>rh;QXVk#)HCD>Bs=K#9oL`T(odYss>huj7K4c1I'
    'y*S~@u!&`zXR-(oQ+u7y{IB+?57IlVH^Qpk*l7x1?*jwq2@A{)T~eLshb|zTAx>`{)%2h~vcMAj&+PCLt~!4zq7UDMO3ZwxhfGB@'
    'uWYsiL7L8yuzEOYXQt?ICri|!tliMAM+#h@$cAQ#foiQnkY?e-cVsf$aJ>5{r4R(9-Fko?JK&q6ghJ{5f+M(2<vkq0iL(e8$KZw('
    '+d%060x0%>f<piGCLK^r?LNFFyU{k&0k7}RgHx^U4*(d^kWnD*SbySY0(izxtv95wcJ)ipKUj<$3$nTvw%y7=hV%U*$>QefYLGM^'
    'T~Umh53Lk870J46*~Ox!KPnxp`iD#S33?+Kd|fdDS8d4&TD4gepnv>~(u@UL>;eZG!iMVaUqBy@YFr+BNO<I7ZmokXvvew4`hH5G'
    '`oZzpURSOpTv_ICs1AbgE`Wf1DO@q?h+k-gy5v-O_BP%pQCb^qb^$_b+afLiAy%tz@i9@W&!~hx(-SSF%@*d|Gvgc~y>a3HhMq)E'
    '-18&ss>uppRbGFzP^<W{&wIK_2*T;BI?3o7odv~EUP_#eg{Kc>Mpiu=4+^?@;m+KYjDRFo{za}^k{a<U9fkam3lZo%1v(+(w_NXp'
    '?{(sHuPZH_hRsv+fNFL*FW9~I9}$tucVNTGvgamlc2R7|Y{ol52_NKx2%v*FVMH;5OYhA?6*bUhj~*-gkG^4-A@b~K8aja1j&rg`'
    'm#+0wCifK|as_}Wj@L>Q>YyGPAK9M43FD((nusW0IT*+ly}1$@8pI+c%49aac^b+PHy0vf4s;zYuri`)+HO7=O($SHgGK3dRS!R_'
    '%tVlLnUq<~?=(hz;QUB1uYz-PLxKWg2M7b(%hVJ7$NV8KhCqc;KFuEdcZcHS^%5v6TF~?Mu6IMhHgd9(KjXk=NecW=DOiM3<tQ5o'
    'w@B<(`RDmcQ(~Lc&twS%Wznhn@XT#+xB|?X{cSx0QGj>LX6^#%xSC?oJM;`w-lm-8DNY)2jd*QOv;_C3oxj2VQYx$4u9HyCMt*02'
    '>TbVw^KT>+txMSW?gE38;peu{7aJ_#Q%Yp$rngee1j#KQm|po#ODOzV7`HwTx>NJ;z5hg_zSvdevUyE20npPlTB&@&hk^WNw;Qe5'
    '9?rlvL%>R=UeauPL_M2r!3r`F6|@5&=Gu>tPE$PPeJ=-ClQm6vYTe<!0exa-Ou%Xn?eCH==^DbO!7Cy!Ph0f^iQF&cYdj8!hEPe;'
    'lY*1z!QTsLiCu4Z@GGL+`=d>RpRm)aX`JLg+H#}d@`Dq(U|J-fo5Lme&^`s)t=@V`o_maG&Zq|AJW@T;h~R>*pEQJ&!{#3HRzo#v'
    'Q85b|&tv;Rj`J#XLXktDIwu`Fvu(>LYz|eSD(*r9X>q{0Qmny<`$-B&K!owrcmk&`P`DTd()hw;9KPkXSn}lU@+72T*+c9X!p!D='
    '$K*OP!Tq}sEX&>);@WJW3uLVyn^jj0GUq(q>++wMq7wGo1gSc5Nk6TpVG<9)^HcKJ@j)q`BCx3XqFFHGj>TThkZd0*!EYiPI?K+n'
    '^rE;EHs}@#vcp7^SOvg(YD93MwOC3jSB;(x*NRlv{hZ{5&_bsiBgNkFK8i=E-gf+Z(K$POGN<eHgH=$yFkJ|zaN5k_MRt%46gO4S'
    '<F<N#^;cT~IKdf@zcFK;G~a~25u#lX81ig1ux>5XS;%%&fAZA4J}r6bGEb6JF8OBL<11D=ql-*c0LTwkH(ZLaU%+KkthH!!Lp`96'
    '#in#0g;9i?%;TtAR9#r0I{8rj)(5EMizbJN)7~u~uMZ^-L2i?IVB3E|jp1F;)aS#nvGCry<vf3Rch`0)faSg+lp^$s4mD!59s<0#'
    '@|e)#yWSAG#hJm;EX4u*aP>svlwdad9&#wZoPW;99cjSie{SuwaOJ_XgZw`6ze^wDH(y^9itJ)CtrOIjX9L{yN2H2kV%ip^uyh22'
    'vu;BwHd$IZ-rBx^yj=t{?jXCwe-??jLwBgB*b%db9Y@}*SBj7EkRQDLR@!#mD-6sY@7^iVIW;@dl8?vS3FM@%O??6{27M%m@@L{q'
    'bJ|-yyxxY5>y{ETUoKIG34YGX_w7}E=tAk&XI<`T(DJ=vEX8SbX@r<6q4+Dw+%H)v9w+lj-{MzzKZ4fu|J%>^wo;3@KKBlmYN=!n'
    'R^G$2EPlIA2wlQU!5)NYp&hm;-pM}VJ$pj^nzg5fYnWxSxD*%zgZ~iHfX*{}-7U&o46emBoDj$b@*7`qi9q%WV3*+6qalokfCVdX'
    '#+;==oWs6^e)Nv2atQuTi#@>N%pL%GJL<PtLx$5_vX+;X#+5Kz;dCVHX4=;*71k^mLXZ6@MuH~Axo2K@u+98{e@h}w6PA1Z{A>Qc'
    '`JevS0ax!p1P9{~B|h?cLL`=GZ@)OUaL<(V^|Xfnx_>uUv<%F0#rBCV`93{2r-o&h>3i8GUjqH;I+>(+U3_5R{^}+60Na*X`#OfQ'
    '?<l<FAZ0uS9XPEt>=|&|Q}~MxI3z@Y228_}eSbC>I{fnsfzaK@q<sk}EO%#7q)l&+O+_rG0cFqN*eroM4D?lU(e9jJc&T^a1OWyT'
    '$~vt^{@-J!e3g<f(3#ZRhO3yj%*>nZHBa|<G$-e*5AtIQ`#+#w$mxl96E<3p@{e<TmNb1sw_HZenAoH%T0{RtOM0t>xD-3Ms26qF'
    ')qD=~o2rYW7^%FwH(Aw`GMUFqMAIQ78>4ITjp=^q?Y7-DZ!vd<lHt1-7}S7yE3EnT(NlWg0;<Qw)r`|ejP{bFpL`+gl?;{`Q`<is'
    '73)<5iwYB806>2UHeW4twMP2!x7EP{`i*Gb=VtdncHYhU(S%x4vA)gWO9cJ>ev_@q^s$@HuelOqzx^%2oc|<7ftbi&#?l#L`H3*1'
    'AmSV3(ov@c+bG@TE8J$gKTUdKMIyL7A!Z{&w;xBRH9YsAdm7<{z_--GVD+Hh7+GvUj!U<KVqhhEImTMKX8F8DpwD<*-_>Y3A!<%b'
    'pW?3UV(64!EP%Yls1FjvudIFch8XVZgLtr0%q~rTvP4kPv)fdAz(dq3OHLuYPmip({U$-D4y|(d{UbKzbc(jT+2Q&jO%3(}l`u|f'
    'f_-c-`b&Fnnwxo~`jTetvI)s6Onu|bxIp?N>o~S^5`aL3%Mf`Y<r^RZ15xwuRk2j&FDkt+sU7YO`H99o6H7Exc-f}-)Y-aefpr|{'
    '8g22E+sOnDBx(vL^x6EqS0lnd@oFEU-*S6HvL1~yaRaL3_V?Mh8JYev0cy3j-6a2rRBBFLEA8jAzDwrYDz!x9gH@nx5aB9o@)D}s'
    'RX^!ov~^^bi)f?21<h4Dkwth)9OvVs=jH&UupwJ59L&VYjM<66)!!>Af%KTD9;V1{EO0)x!;D-Q1kT>!s1W)P=n@Nz?`iU@pYozO'
    'VpN_br9K_$!Pp?$9&_+l_B;n@rJ(S-%-obrSw{1Fwz_!ujwm(4Rpi9rDwUlz{~cy0-v`_X0il0rImnuoBj0lCNeTFXt%s^&#i|HB'
    '!@6v7N+G|~#1riQr0u<b28$fFD+Lv%dke<?R&I+eds`3<H>!@_W%#i7J1IjkRb03f5w%O*!G%0yD9lR$>Y+7;Y7Us~<NL@TZ9;Bd'
    'Y9*16x?#^=Lr@UAO3dE;{(pJK+AT<JbZe=QVio?1)uS6Y_v%FKD@lq0#lik1hBVrkjr#Vk|7%d@8m3yeY0~M6rj|{e<DPY!kVJ`E'
    'IycP3Etdxbm+u-?f2(yOF@->8p;i#>=rQMMb;z_+*MT8HU{V_A)Qi~18YC1+>}OW6c3x+>6+7_YpazZ-K$NxsJjxeLZ~`&$zxE{!'
    'A^Ie=5~$Rt<s7tV(J!Pjuh8K>O6G;P6l5Yc<n3HnCIZoeTT@TcfVV(iWi0OsTdMPZyk}BPR~DtEl&mL_Rg=9OiF*14c5+xZuv`n-'
    'cdwgFEYPX$xM?e`yJaEpflryM_&R38Imep~7lt9@_T0#Uue42e*QXAK@@GY#?(o{pED@(G&w<lXonJ?7xR;)=1d_catqe^_1V7u7'
    'ob8zzlT0#^@FlhDHC&du84=FEp9WOI+_)*S>3%Unf7~3%0%yU<fBj9PZm}O@%<e>xJ2xEL_^JX!pN|<0|C!gh{HMijCoCr-$W@kc'
    'B+Tt<XX^vmPCnK#A9B#!MOv!CBLh}u=1NM@;*wmTHfBjg&py@arKmVd-jKxI6)gk;n7b44qwwGwMB8ZkwaHlnQ>bV5PST0NmdLIS'
    '2JmUE?0V{l1k{**-iJG2gsj~g@+y2+0PvLpYAlHD);P94gSDuV(hIYC8IxhGI)%1Qe{mjP)4mHGC7U)F$nxy>)39taxgoD&DXz$q'
    'Pb;76%2-ufniA5KYZX2rR&U|X_aRC&SR#fF-+k}c(rH0e;5W0}cPIref*yb}$9yP81_jHWq4A7&tOg@A4}66o>2B?BcyD44JgQNY'
    '+#<@RF=sHtBm!&&8y0b}Qj4LNY?k*`-?Pp$8g39{S$-{i{mp~h6A0lRYq1HkvZ-gaDA;M^GVuHGuu<($c*&}I3hok&01*7;tq6mp'
    'EOVB<fC<(kNj-2i*QtnpJPy#dtSC2{a9TqTNk}L1Ijd0I!ys341)T<e;Cx(~XO9z#f+VbYL=5MNCmtHG=fgM8?pU{YfsBAc04QF1'
    'paQNJvA<12N*iknmAAVOrd7|isR@p`vv)c$Grq7%?BLkHPM@xq-I~zd4ZHjy0_dB$q_>#Crf*BK^DQj^AV7bQHHLYNN+vc_f)w!d'
    'CioL*WE~eU+5%7LAH0a2;*sz|Y1DshF{sqDneAZI9CX?=nEwXQe>yHBD2Qp0Ghb*<dHPXF+=8TQMXK*VMJM7N%}4jzGYF-y@~{WQ'
    'z|wEQgEZLr;g`Ta`)h;UG&9mIa`r*wI$-V4&zq5`TZpV5lnAoAMn(JMTiyO6${`%o3leyFVmpu1EAJd$4tG(a<OQ>@0?#B0%&tCE'
    'UErk2-Jt|*$f}k8l-W(kD4eyQnV|-0s(oDmBz2UIi?%V6Au)ROf!?F4Pu7?6qfyDvslVqiDUF}(Q>u|;Z6h6{7e<LIalS<H1xjH0'
    'l)<%Sx8C%<kOc1WJ&qMGty68S6O!>jTh#$-XLg}5!IIiDP>)6pD6fruQPWy?R2>lvnK<3!;d)o_z?;`A3defn5W0?QT!^Eg#3o*?'
    'h*7bB2!FXn#e^51^xzfCr}EbgIo*+qT`#AWEmm<h_d1idl0n>1VvQ(^8{?qyLaZL53e)-wl_#fGC0e=>L3aot4lP7u@C>Z<ZR^p{'
    'F-!YS9+LWQIvt=K3EZiLn5F^0XWpLf54M0rP^dU;#DnwZaaM7v+z_M_sf8#y10Q9Kze!|yoNv*NNVWti-^eOml#L|=r1n=WFlPN}'
    'c;rwi^RSpkx+_!Ohd;<*Yhu_-P#bVU77h+<jeWUF4n;`LI3&YlSut?>Q2dPT#Bb=B*!*{29i!*_hm=(i>UILY)3m(Y=n*lw8-LJW'
    '@EP8kQKnNMBXo`OJkan>WAzT?kQf}r2N6H%CxiwA5khi$S)r(Uq7m@#WtEYf9^dFj78!-=nw6uw!Yl619#A@CPUb#q00d(*FkhXb'
    'N3dAvhvhl6%^QdFe>M*cpi_h9Jr>BGI&R&06Py?HUbm@X4(SHRN6At!XK@m0+k_8;(Uifw$uZ|Ew%k_i`_Q~07o3D+C4v={T)W(I'
    '-TFS++nEkJ!dzrI%_<ynq1Q!^nOdJuVb~6Nm5u2xE)gLHdtm||EaGfJbkPm*t@*lG4`a%rN+RPyk4oe9<5Kky2}ka~E;!KxC>$K='
    'j!48gUC6<5#6NCF4gM`3;Zl#(BuL)dUb6{@SnpXEqYXwJI0qs_lcP$2=%hfln%P4SU=no%QTpM`EivFGgHiYAD?70xS#(q%Jv%!0'
    'xVg;%7Ot_bq5P4IDq-12K@rql$TJ7Y{jctn5+N$^<@%vs^!rn9U<fmh+=8BhXI?`YmalNkId&f<Yy`=dPBUW|asE*Bz5LH`sN3kJ'
    'cX7E5?x$NfHxufSw>kb$^v}I8w>n<(Y+X#khf$dx<`D+(=yeAg|Jg_EOkf4nXuC{#3{+aVY4m#UY0rH*aXkE)Bxpo?jPCni=p@3?'
    'Y=Z1g%Gh5#FLMe`f9a*b`9dG&2MTf6lwdXS(P4`1sT+Gf^v2k4tGFL2Fwsu;+N<fAR=ku05>wy~Z~ugtt^Q<Bz9I)MLGl!buRJqh'
    ';Fg#9d4$4gKv<8Bw#!H;S-q`JqTV}>8Hv)4^nSpLa02aqKmx7FQh`Ilkl2aQ9QD~t`!oQGL7B4RCM)7)FCwiu-F(~3Wk5>K?v#?i'
    'PhG3`5Pq>9lz-Q!R$|2UA-8Osr@y(^0gld*bGa1e)-#GTO=sC_FxYWrb!CrdgTxAfId36?$wkqB*nNChJRIc_$P8*!edLw?NB#m_'
    'IOj9vccR(-q4#lD@gFhW*N_e44jL1z>4U>}#_0epu=tbIme!p><0%H{W3zh=3_JO-NYLtM|Kg^hL+kZ5A(O!9!&3)s{z}mWCj0w*'
    'X*6EJB1##K_3BZ(qJMV*t_?ies?qcaVQCN4grm!KxpP0Mz~9Ja=RnHwWp83l%^&>epGNRVKl&EGhQ5T%;W9#h@Td@Irmx4xYg4cb'
    'o3<)AgQVV-NerpM1ITi4BkcP13}xrm)vHFXmfh!!0*qto`#oH7kmrjI(48{SeW9@&9NUYf+rRf{@8+BvKvjXYl)7m9E}1qz^DB`%'
    '<$awn^^-bvNx$kieD3hj1b$FJUnhUK0iLk}I0?T2FMhFDB5nsH3g98?Q{`u|Rw=1Hlgqz`f6<|Hg<Caj=VkI|ccbunAPjQzj4s~J'
    'TK_Ff$BsiUD>o@#8KUw>+cJv_YsM;tz1nPIZ)`M}`F=)G+i*p7#5L&0Mne$APjX9$2!dTdJMCxN7c?@^Ry;3Pv9r~Ag1*gV8*Y4j'
    'x!(qmMI-N`y%WS)G8G@xGpy-Z;7{r{iQ`fqy}sm1z2gMy^4j+GI>IN}clTxp?BNc)N77w#@z2lK+U(O}_A*75Zpq80tV`id2wW{}'
    ';nT{5_HMwb=|3sNQ_-ZvW0^kh`lM6Mv%I8zm=M3oJ)(*NxN+9tSb9xnGh!kbSf5TybGnlsQ$VCrm+$KjSE{+OBM9@EmjqrMUx}>+'
    '-8c=@sZ{F%0eSJHn_lX-0w)wWnIOkYYo5(~+?dWQ$Xa<XC*s?WtS;g%9<&z!c2y&Li&dV9T=FnuM#6u*&;7Z~pHT_YRe#G=l3BWJ'
    'QZYFAHODnG1cud&BE}tij6O|dB?HGUYs}>MFe15G4CSPj4}nDKlN1^672=LN@o@;5HM?gD05x|XM*f7`CzG)-E>Ap|&MzLZ8-fli'
    'K`y-TgLip(HQlv7meBuimanXZlcp{K+hUsTOqJA_w;<;SRGZ}*TTR3N=rGV9TR2^ds<+61jUk#A%GJ8dg5KVR3J><2f1x2>%hM8J'
    'K2z$a^u8<D5CVCAlCfq-kIergmml>I0M(nQU-$MzFzMymW=c8pPB|2EaDbE87Xh>R5Ry@toauWkT9d`49kxd-mR<&gkO^Gtj}R!Q'
    'FEK|U3xFlqoSEjcGO8>^;;YqZqr-#PVo9*%gC3a?C51Rm-aCVe;shaTv8`=%RHysx2B%2>c_}FubRjAA+4HuNIzw<N<#n~=rD|Tt'
    '&p1X;iUji#jBUr%Dmq`J<X%~VwDYxhV_m3PX75=nl8NuYjWX5QH>N;+36@+DxQ&7y^ID|tP|ECKnIb)(**9cac`EpQvpm}wvg5?~'
    'G^O_Da@}gO8Iz2C?{Q}02C3COVAmlm+6cdN8I2sw_*xc}K{ZBc)DYlCi6Bm??QPvsOT(=@VX0|r1cF}>Up-eboNAe#G0%%<tWzwW'
    'W6dU-2(`PO)1rC;0~N~j?N&HG{Wmx1qZ_)-?iuD7ST!Lm!X0#GVw-eK{GA0%8x(K|adzWMWhLlWKq&oWQw|<?hgAa(flcdKT>UNN'
    '{j=FI9~I+j7;EBBXCN}KKOSqH(V$ZjG-c=n4g&5I9GS3~?!3d_$qd<`<?_Nw#OOgE6UXHx?7j|Rt-l;Czd|DAP+pu<0kPvfKltQ?'
    'YwK-Z$iA4a86@P5{h~4X@#G)l=cf#8`_oo<S=C|kg$*Eu^>W`T>RpC>0M$zsDDo$ajL9KV;$e)%>1Fqn1LCRKqPtS>`n{sn`3PhX'
    'mQCme6?r{%<}O?y%+v?Fmg$=aQr&iNZQ^IV^rdr{nYEAxJBJlh&=syagaFqR$ws<6<f<I(9JVFA2v+e=x$(LXCyqPMZY^S0SDMlN'
    ')xf6n$=yYpus=i)X~h~<{1C5%wp{}2?|SO51~=nD-K^Njlakp#bJrirmz2#Idb-9gNq&`Xx}jd(z5?6LrG(6*>!@D$bD@-0F?f%<'
    '!+~4!ZvIeAH%!b{@;~>!%KOF=z2~T4{AL)iQ|@z%;G+buZ=+Va^kZ?-s?~8PxxaS!?Rah{dvpI<gvNjif%;;&4j`QlTvgK>2T8UM'
    'Mxnlxx(xdoo{+kF{MiSl9ltA|JOJ_N-ocb?lsI-MuM$@+vGN-jP01CY?!dUaTL8B007-GbYvbG@v8?w7e1YSlD5DUw#V+g_Yt|5{'
    '(hTyL)S$|)N^W{=pu*lVI=$OgQFs0|EGWqpaHP&LhdgM#1n$Q_vR)4GPog05BIh?^Cl9HcQu6PyX^EGvd0|USKQGugpaW7f@r3Uc'
    '?$%(6x9G+8F*8$8E5vaR1<>#f3G^n|0W?nfq<ea1X|9(vSl_wsSFBfQe_)cV5pJG_(V;7RUS?Eqc2L#9Faa!blrV7(Q_}}QE3cN+'
    'gdHw|2)RB>UxK9sq%z~0bG>*EJ5jNB!yz}_c3_&6a6FD{D4P(c;50agU;tT7S`z9^oM)Fps(3-oL;6mu8?kTkyQH!;8|ZG?d}1Cy'
    '*&_rjdHQ6&aF2v=S<6@SZ8+;MJq~C>AHD1n)opmIyR`040!+!g^HVx;s&GV(O86#EI^u&5=j7dZ>+2aET@E!vDiCv;LXM)EuKq2#'
    'Ilf`1!FD{%uYv$QRE)Z&M`?K8_4vCeL2$8~DEgm8!Gkl~-d@BXn<0cg`Y*Jw!E&+Mg^1Q3fTUNV;43~s_|2d*y{9B!{sK$Ic7t8b'
    'ErEKcWG{%fFmmH;6OJlxe8^VhMwt|kwD3)H)O-G`PLI=b4firw*@|fy2@x8;1A&Bdx9aa8C|~FS-s)IGou*x+izxC>LRZwsR6M1='
    '^RqN5+j}|T6Any!0P{>~lTFiH(r1Y9AM<C(*(D2PXP~(usR*=^+qM*}*H%qu48FZN1Seri(nVDC8ZIwHf$uYmT*KP%WZFN(2SoDP'
    ';;``l0bA2-EY^kzd7kR<^4yt~&x)-y9(&Zr3-vEW+}h%c5ZYgJ<Es*eR_<n7WQi-9TL((jlOx!6NtBVQ#k_F6ZZ;1f>AaJaIEoMo'
    'Br{?Ht&8m3DxEwk_t2Kq;ADR;tvqEn8{*aG`qm#wwp{&=$|o%e?PSlP8>yz~J2GoU>-uUAfJbUKk%zIfgHFR^J9ld*aER6poV<j!'
    '81gH=<cdVRz_@n#<F5uEssnNV@z5@85N@r?AX64JouwW}pvs|4%*ppou?*k{OW9dAo}M%c(r|q9e4XEt<d8@6=?EnV+)?%AP|Z7u'
    '0l>O9XSjmJc3Hk2ZZUH$)ujeo@O~L5KA+|lv>7Ioa`EHzWEQd}?PkBpcqJ;}2ikhvxDfHzS>uT^6UFxuPaEFh)vMGhl_C&LngPoy'
    'S&J~2e<HmHpa)jdpBaO#efxfj7$8O&5a;EQH1UHRguZ2o{AH#N1IhBaEf&^g7N;EFth(g~NE%y};D5XnX)-IF;F`tw6n*tN_&&?L'
    'SOFsSVi{>FT$>j}A-g5g#z|mJ?sv(z_(KXMH>9SX?|YQMNjAGa3?7s<cX1XD%!m<0B)nRmcX7&F;sZa-_YaSTFhMMt*i%v#M|_Ae'
    'Av@+CWxTA8h{U-+a@YfPo1hO+`SS`MMlAxLPC3>tnPIj1+GoAf^H<VsWb*56slz53VVmp`&Wg?Fg{>5$h|3R2ZJ4v`mcy0~<IY(&'
    '?U>mzC|3$*z9OLqU@${V@*_c0o(j8Qb#AV`fShD^rc1CjyBTiKM#nIlS2ERo1~Xv7HJ6%+=B#<&Md{X&sjJ=5lAXUd@_juCQW_OB'
    'a4nZNS<vtPqQVbzf2|!DON<IQ7F+>bO*AL?R8YCVUI<%ZNQ*g)Lt6vH?DM_+M+u;qN3<K<gkEq>$Og*ftsicv4Z_AI#qI?!Mc=gd'
    '_=s8)7`jE)&`(9yeN6dOuw~nmD1Z2NcrXlFAn6nFT(5ED)Ym!)1}yg5kR;~ZOC8k4feN1CxbkK$2ROd}=_ag`O0Q4--c37|3g8VX'
    'n32v$?z9RxYtz`pqa@ar4GdFz!HUnD>vw+Fwi)&+a;C?2R#Ox}ozdO@GQ+G^L|r>MsAjNozsGbAu0w)#nUa;i%&1q7WV5sihap58'
    '=lHwZt2p^gVacaFos1w?7O<@HP_-F?6B*@eOz2~{q*X&vRUn;-ss?4w1%lMQ?!bqRin7^U6v=Mpv`fFYm1;68a*Q4G6oqn+`LC~C'
    'ETaJazDD1OwjNE0NfM&Qf2c;Q(^<nL=^!0p$HNiUgn~lucf9rsif?<DS;kc<B9Iq>1}wBwx()L&4lS?YvZav5cQ&?GyRZh7N+lEL'
    '`;-qr-m3Na=AbpNRwBKE_y_E(UhnqP-t>H!ql6cz?kGpXo^f_1l*@rG7wK>l-N6FfY1v237Qv5-Iu{#|Ew1VaGi+YIn&N+yqPb=3'
    '86}=3#P2lxdJ9lJ3HPNDm!AVwOB-gzjPT{mA)82d--w*9m^wxyVGxq70tF8cX2bhe9`_Qzh9g~pOcgUh>4|8TdpAg=Tr7x8PbD0F'
    'hF61<WId4oi7Ii2NFbq#LIlifO9<)*TN<8pRg{j2*=S!i=jET%RrhTqFx8sXp;TGee~CZy&#-NB9ptoIIkY_f`ciXBob{fu-2fas'
    'o`a)#48&}l0!z9vIe(*O#RDT68(@iTWD6%EzAQR8t^`5otmt*-V<~$%3r2kD+h@u+t(C<1+1Bqo)!kh~rRQP8R<1>ZdYK@F>5(R1'
    'QB1Q0ssk-ZMh%bK*GJ}QhFTY3C;!JEMR6*P-W0=D!5?XGROPSWk*DZGti*dfFCj%%MVVBTD}E^$1Z9s@q&FUJJ(|75?P@t6-5hda'
    '2a4Vbbj4o+WCHbnaiD)D^fj%UHjh9YwEZPrp|W$?4$X|w(ew)iD~HwhNFqSv$L6W^nM`KUL>YRvIJVpHPfoSey$a5uh0RNqktmkQ'
    'QvTV+?fGU?dG0Z}S>$bH@VIpanZ?@ojRc~-7f~*5g3!#P*G`I$yu8-Rdh=E8TZ+4`IpNrJ@1xc1ktX8_t7bj5e4U=SjL@{&Zm^_W'
    '#6-R#=#eWqAPuDMS;1u>Ed{nI+66w|R3dh()~Pbv$Ux;Z)GRIN=_>kaRf5c;(m-z-V;5F{l1Jdio>qsLC#;B}t~guxIW3DbtuhU?'
    'T+jR3S(UdT!rM!VLgBH~9$vKdX^3lz@&OC>m<wQniQ9fG{LJnM;m7{~vTfcpdu`F*k?HmKIS8^U|4Xv?5D(ft^}nOd7^P0~xQ0SW'
    '>uxa`KS`heFrEBe+&Cch!B(wSi`bcA08q0-RjC6p`TuM)eiU=2%dTDo{s?lXFK?hjl1sF|sp}hiK`A)f^aBl+?il>sJ8`KwyxHJE'
    'Vx!T>V)Y!em{NWlB)nfQ4C^&dbjGD&FEBJa*XYH$WQXH(1u<%*vDO&Wr{6{Pv0wbk8Bwzbn)JP~nk7Nyir@z~lMX%cX<(Wc*v9i('
    'k(=K>SZZ>QbEK7Oj^;}vD3RG$MKiQ8qV2^=3o?RBvGVw^g+^6P1^HZtWGVR)=LTGbu?UU#v;3y_hV|M6pH?%ZUn5tXpb^UXxz4Fs'
    '5vE`_?xX#ln^B5l;)KS>Q%Z{Sh-VzRBPLyj%rtCbu<;F=->IzMwx)!DW5eG4$+ckhNsTD&0|e1*1-*awdyMwIt1J32j<@Xq@h~)P'
    ';P2MqabP3pw^R(hOL3@-*EI=3*VUo}w((}b3a*=g@u!P*i<F}knzWIaKqBue9!6)yy(;%-*g@yfmxCW22Mtq22on2_)_)q|7}s^m'
    '1L;h9mpJ&LXGdL@%!6p#3{3nC$cx)Ffk34o5IhO*3_$^3*Ku4dB5v0@SzQO~ArvFYU1V@Wm#?(_Lk5t5()?>WI_P!6hc5=x2O@VQ'
    'zG}m^S})!w*|%O7Bd;KNYyTow9US?L!M>7rq3O{D&uE|PD01XtQ{r}0yYc>7P;{UC4_ychk$Y_OD>=Xr)iuZ#AyBqH`}Yu|3|Z3r'
    'j$xJiR-RNV^xXKXHz&X5ED1k|K>aZEqPrl<070gqyr@6V(ll9cIfsSI-|uRqeNAL;dPc{fg&1lT=B>|FJvW=|`bJfitY)_80D`BH'
    '3ghX@fAXXtV{x<QZshq&NYDNTKB5PVD9wQK-Km~IVzH@RF9%h7E~m+JrPyJw9fLlOMB?7oCnIkq94?IA=I63<yFIM#glui*`Gvx2'
    'Hy^#vFAkYM)Y3_A3={JgI&CCWE?J&X_{lu?B20eXm*lkbHjV5jRf|O(;iJF>4hUW&N(uPq%oazy=7Ays{f#&@zq5%=f>K5Jhj_|!'
    ';+&ay!%z}d*A~u`JnMi8&&}$bf`BG)5r(<7#d}j|uF8pFqgA$p%1m@uVG|y#^I2k`${3{(Wj%;Ou<rpOcvxn6Bm18JEa60_w7Z?6'
    '7U`a3zv9eg;$WAbT_r&&n&6}+?R;x)nb6G>3WCO;Vo-435GXi;J}O?;7BMNI>XdSoLCp=5_`;iayadJ@<4EE8HDGq0j4&cbe1UXo'
    'ft&a^1iuClwDeg_n;3`W`Q@BWWS)y@%O`Bixdb6{IUo&UK)hv41-M>sqv7k5=x@4BJc^)KHTDXj0BX8ok2W`mh8ut4`Jc7)H%QjV'
    'pF?1qBW3tP#bYI=J^vzqB@)Svf#-clnw#K_2TQ>(C1uXBYZ#T3BXUy-lDL~^&-n_WaKY+QghVsS$Wg+GlfS(h236bpZR{CtwPijw'
    'abx?UN?T%Ysnj{*bUsdri;q?{jX*Dgx5QPOA$4ow|Dt}7ig;bqjIGSvJL1Sje7BLK$$4n`(~H+UL*-ih#3um+uWem21|I#a3XdJ2'
    '8CM;SD>YRn2RZYtzDW<WdYwZ($U-l;zC_9V({DHcn`r2|s1CR0k@&m<D1NO)GHX0b_yP_7KGoB>+`yP;{i;(64xQ2{3K32DB}l=A'
    'm6>iRj;)rAt~ptjtB;K0%w!Ynq%MFP6YJVPeL|z#1e8ayRhVs$ACE)I)@6qa*?u?B=KD+j7wl!v`Ww-r9Eq%4@4d=Jf5y!*-jYWS'
    '(;rH7>DZXoQf6EH7=8j<9Tb=1JpxKrI7nqPlpN2lDnvasHZ@YIYVn!`<H+H-32qdrYq83USbY6NQP&OD<O$2aW-xLU^r?A~&Sssh'
    'hkYbDZ;np15nRg2R_At?3DS%m)b6H=wt|;|C8zsy^ZuhBP9o{IcmsM<NCD=;yXphr;M9*nMR`X~l2-DwSOT_{wutnurbEve(m;8_'
    '=H9%SbH2#nwLhq;N5zrc(gMeJn&`P@ZD8>YCW{A2HC!Sci01+kJ$M$6=XAPW+nZqaha<3>^%>lT$kekUHrmrxd#O`cD?JgNBKtrl'
    'of!0SvlPOAfMUEsCEx5d4sMx-oQDOfKIP2!A#sL?C?11iB)3R^9d47M`_P*p5<2tw)qB%0co(Ny_ZwatA!9W~23uVsM~qIIY&6~A'
    'QtMR1-GYs)&hmb=@_#~YY}~Lk$%MHLU3b_MLoIpAEI$*WEh4TIacq;e=6J>Cm`HiEd;fz~&-{>O?lg!)u#SuTobm{7U_Lu86Hcc1'
    'Nfs17ZJPeWzSp4h5R$z*<%3p%IaYpV5$=lL0FX_fXdm6lUzPl`8f}9dz`JaCEC~*Q%wF_0U8=u|8R6)F!vk|YRE3buzXxXqI{5YF'
    'h)K@gSWL=bR=-{p3*Q1o=*wv@FggYo1_}B-e(yB;GfnpwWKFEN5H65t2CiKyrL5ViNd((~rn0Be+9*LtYhq5eyEADG3mItMPVN;^'
    'kCfja9ub6};jVo_2DRw@06jd|2jT73m(OU^R%Xut+FYObec`vUZaxP8{nv>&l#o^vI@)Wog&P*xPo_D#cD{hU|5kLbnbCH}O-<Wu'
    'Xi^M*I<@`o+l-N5INbbjfYIN>=NdEKQMBcX%ULmyL~gTgPP3`D9FbA_;>8&xhYj-XFcQ8iZ6%OP>!vHMa0z-$`70cmU<^6o92+M9'
    '+!HzUZ%`O^Pp&nG>qn0pKL1eW>XdN#4vlktqSc|+a0VAn;FpJn?0kqt`<((4w4-|92ArB==_Mf_$`%ubD>o@|0<Rx|Fld@*tO&HJ'
    '3r5+NEL+7sjodcWL=ptlF8b#hVl_rcAAEb6k@JIaJL0z@HBAn2E;Ai{OvJ+@Dov_CrPr7{pg@xt-kP{62omewlCRao_?Eu5nGuuk'
    '3zd6K8tE%(>?~pesO50|Mk2s`h*<G5bf?l(=knk+Vmb|5EnwO<V47|A;4<sW6h-Pdh(NR0srFO4tSVM$=yOlXHaJoQe%8jNW#}iX'
    '^-opejxae<<ICh9q3Nhj){qiY=uXbg*KzM2A!#JC^s!-z5s6%(RuW;;?Erz@7SoKtZ`aQ$JG-Ca%mGsCxM;mlU;$RFjkBho$fP2C'
    '_N6T_z`kAesA2t@X+fxHw%_bW*d^vw;7TX-U;ao3C)Ie8#U_4mKrKMMAOAsz5(C&mfjn@U_(!~%-l&ZN{oa7J^0%Xjne2R7omLmf'
    'x^{=Yv1W0E7R0L&aS8U%XpLOn;c@DCqt1pdZlhQe`Vhl=x+dxqB{C<PU?43_gt%6{1{}BYc;jBTtg*j}c0yW8Dbo1jB#q%y&N(wU'
    'zklzIE72Q-&c@*OMTpD3_*H^eJu(#P4VvtR8sKe9<*p(8kA2%DuMF!g;^Qtr&oxN5TrVa5QV<0KBUGCu1@FcVrogFQiv3a~%Tj(Q'
    'S^XQbwp=Kgn0{b+VULnvt5DW0wvuHjhe!+SNqLF9YW3z)G{X|{oy(ANvP&ubNz7#CanDp@w4bzN7H)_SaHU83K@~gI1Y|bIiGzU{'
    '6(ZbHJe}SFU~WEN65YLiDpF3OqO@(XzE2TO1>ivWoxD^JE33&4^~YSuIF&(%HqeDC=(>Y^HhnI<?Oe*x!G1F5W&k<4<;Twt+gx`2'
    '0&A$r>w^Gh>D{r^6^mA|e(?)!30Gc<l?xT<%+_Oq>Il2Q|Dk^v2SGGr>GH<CKQX(IX>O!I!4Me)fa(@2*>+^zitS$ec6$?`>@`+B'
    's+q*v*h`(MblCnuHB9Eo6$r~WSs=0WWyEu4RJVu7U)s)-2b3cQ@v4;R9$=qIktvF59A~3Zt^cWtgPJJ?Eg(%>dlTfZLka(rhej$;'
    'i>fu&giuj^BbMVGBLJ!fHkmm{N9M>sM(JBw*!`F#Lv$K+A{Jam)9t1D5_E_d4B~1?ZwrE=e@}FtT7M<-vmRh4eyv5)ypXY!dyTSs'
    'HQ611@xcT9H5#bX6>vIep=BrEiSRcqVsrW86raE(bLPu?P{-xRl11U?XjmoKQJM|@aNs8G{5K`MhD6V(BeoHA)b`K78n@p9#xjR8'
    'LuEM`tnn>SEjCK^$xwG+-0Vx#8e)KZ@OHEZVe=m`4~Y4~m3t{~r@n)2%ofUi`dm5lF=w(Ws8MnmX-pDcmuUXl4l)8PX@AXb50QK>'
    '7h?8fEzEd{;cUMgjI9jA`H|i4j&#kk{9DRzf&iMAZvs(r5$}D!vN#$>XLIJw(y4t8{92bm28N6fa$R=u3xZq;P4pf;;Ibqgik%6e'
    'HC-QaLrCO@aL8XoUqMmGjQI#GUUwwe?;_!vh6N|05Oci8U9g(pp?<mZdo~dQtaUjzz{ylCp>IS#o_x{h^#ZdA%!aap&jTSbG`XkY'
    'vy+6i$;PgDl2kvSWBeyzsw6jBKME&A)oF@QoitSwHHeH+EJd$?JgxxNU~r}Fdcqe&uKAJhHdl2``;bz<vX@iMF5S`fkPk10XDj+l'
    'dM*PvN1xSVGyTp<-19JT%|2gq*>$;6HGMR$LyEvd+Vy#xU}7zD+te;Pe@ro-cWvoHER0Fl;njlH+bCWGs4g4Pe|omtz3CUhd^UzL'
    'K=HKrsf$`55nc-i%%Kf1w0ww{HhVPWi#<!2_X$1S48EJK7=N5Y4Jz*(A1&iA1~VXR(|-4sx;G4ZP;vb&=>CG*!0LSX(Dq$uB?D_~'
    'B#M4i0ftxcNJDv4ZWJVo@z^Q>T|Oof*ZT%6!Dm~#lDm^i8iU1tAhK0h^~A9u^DI+gXBv_-#Z;M0qMx0hO4=d{9c#rPJvO%#jM4gM'
    'mHsN*d8$bK`S6T%OqZT_!Rzu~{RTm_iNaSzZ*Vx3K@xk$X}o+4zZc_zR`b7A(`=$_EhVG5@;@)%aH@dGpzmM(5K+MMN>U{Hn^50a'
    '>Y_7?Za<HvMWPK_a(Qa%J?v%(o<~H@!+rnAIzj3QoLG4VhkJ13jxt>=s%N{n0|CuFEZz45#LK_>=dj%<S6J9V+Q<f`@Fe(cW0u>0'
    '#(8lEh?i+AVfPIVu20p;#>q)Gc(sj=$TwX5zUQIGl<BactZ@g5Br->Jci6~uewzgx3je0xXvSCw5~1#mctoUZ`3N>&m9?8Ty0&+$'
    'UL&ei4F>zI%ceT+7eO|wl|uqYaF6PCo1E*xswYpCsH(k2=CCMOGQ4~<4dFV6W!{XDirnh$n(M1P-X)p{@i^Rw;OFQ_yHJkUQkGH-'
    'yGjhD&HojK^ZW@WlnrfZt-pp;6<nzBZs(p;p!Lg7*y->w+JF)#R}rHu<TqpBP20lBe?b;;ylygGC~-ts*!r78Lg~htuP^8W?NuSu'
    'C=R;0i2sY^tO&NK#Y8=4em5)co2eWw*r9*p`H1eRR;mfG`n7cbuN(ey30DcN)?H>W^tZ@yZX@1`;C$JJyfkQ9T>2?>g_#aJzxj4T'
    'H8UhjK2`W~SIh=rrQJ#1iBmzB07@O)^H=hCx}<Z3;&_TT9nsJl!tt1<67O4UGxWu_r7g7iVVPj}e28<1-BAkA4n#^ddOcxe(G#+E'
    'L9+K4XXYb5H}}1j$O0HjiY6Za(ddE)s41r_?d|iPW>+O`yMvi0fEULpuxye?Yuf=ZM&9Sd0epP)qKQ(IF&oiq{RE0I;xaYprAuJa'
    'wp=a;zWE$I(CEjHmiyZcL&`K)CWeQfQ>%ZTsAR(cflBe$1qf=>Q^pVdBo@BOKRG-TlQznN9Jh8#yR|H%I`=mj{_{-gn9$os^bNwC'
    'Q->5_^XzwW8p>i|jbV)_352F6{S2ADY$MZ@myhs_*L@t6Y11@S;B2kAPs<W}7welq9~1)Ok8KeeL2~8;t0&y_JT?G?X$3C#w*qhs'
    'D48t|QM*-kte{^9la;23ED2uqT1z`kWMn)~hBHF)tFq!oSi%ZkgDw4Z^}EkXyIc)=wXUB_>0k`zy?PTqu|X2!61zc?z~%kd-yb;g'
    'e5~hUmB1VF&+wO4Zef?PMWSA5F#({`CSLY*?ZsoHDpf91-Y$~c4?wWemU*GLg$|qfrsw?U7sXU!3GZ2V8&BgH+OcR^F(ec-`#aD5'
    'p%&Uft4}I=_D3R)g<p@u{dtB|KDeRp44Dtei$>V<QSC%K9vt>Im?W!^{*FS_J{Xw~jF$c1&2B;v7PQ<#5JJ4hr(iJ})ww&tUI|P6'
    '7v)^v6^ipk53T_wcX6pdhyfpk?ROmxuX>$f<uA9b2enB9dG(TDU-H%zqV)Bfq4+b)b}wn#SV2qypgh#fNsoqXr?sQR`l|1<pB|mN'
    'kGwMLN;c9Jfy>ceX47E?Mff9D)5x^s&N7w-1UOOBDH}DiZ-^$+R;ra%FLa-n_x&Tl$Rne&aRge`L8t}l2f6XCy1{a!YYcS`ad-KQ'
    'ZL$$Yv32a&2^^lUufA3Jw02heA<iN*EVOMiI|L2y3?=31$YPME$&qzRi)JT?*s>i}U-9f8U{B+nb`Bx{{P@{$G6I-(P9I54njWf*'
    '5NCDW)B7AAu=W?_&UTW6Hq;LwSI;v))PYSqTD7$cC1q*vlse((i6j9S-DUJe(gD9PW&($0em*uj0;Y#l|D`gyoVlStFv*Bugw||C'
    '9K)6<zWt!NlcfcuqJdbXx5_{|@<fzwO@#MDC28=}c&E)>Y#sEPwy@;OOFz<FaVJl<Na^+$e$eW5CnEz_1wRZ$5O$}Fj{qFX{%nNz'
    'Jv}kIuo8QHm=%L-Bo7@BwH_|p_ddwbtTc?B)&8|j2l$f6!?Q^D&?dXO4%qsyes$TF%Cb?#<j0o}!0pdqZ_Wtj*W^PmOFt)&U#R%R'
    'X}A)`&xC3IneG6|dJX=Fg~e4R6E;T*V&(G4(gOl~DH5;K%($zr|5cQin4Ml(pGewSjcc4Pbfm#Ww&10~oxchlBkaGqP$if9JVBsb'
    't&1ZC5Y(LJzcnjn&LG{4I}`F%s|l-V5``WOy#-)%4(VM9Vyc>yUDTSzC8p9^9=f_o9ncgO$kV>?M`E&#rtA_tfMVO+HhW*&$Syig'
    'yn6GU-pQKFF0YH%l!m1*FAc6ypqu+`iGX$4a936uw6#GgHd);=-XkP`W`{$oFQ9>}2pYQWdH-I-N9i~W_WV{%4vEFl-UvdH94mBO'
    'KYGVk2}8pFxmWE6T7E+l04E?Bf2lsb<NCXdPZYuZ7@J$`hhQP=!g7zP<P}87EJ^Dq<Y9K{C;F`nS2$D`-P`r3&v*lWCg@rx?MMtc'
    '<Tq#))3T+63T=k{>lxCf$Z*-5(F9VnNh+T{b<+E<rt1v`weCuli@;H=7{5%alLGmE;>VnY)X8P+-6nkmT=^g-15?3k{2R;?q}yv3'
    'MwOr0G{vHV_dG6E{*NY@%_@oPB~s}0cYv#WZLWPGz#JT6*r;tWtv5kwh-*tWB;x6EA~uM{AOTbsZ2oCqm!N&}8(D@j?2w)nQQ)BP'
    'rX7$nEk}SL<b_&ioPqKUotKMhn8V4;_0V@pC9;!QRj@kGVFzLQpvCkH9H+wf3Wvkyw-nM1+kX<4f!>wWd;W4cok=DRb{BM@lqbr`'
    'EXq}%Cv#S$3b?p2H$u6<4D4wg5RWHNQ50?rl5e`y`91w=cZ7BU48+mZ;@M&K*A*{rZnb~`{N9sWs0D;|tf#6@`~|d7Y=?{I-d0ln'
    '0a&%o7j>MbNj)I4G8P$(i7F4mA95OS+T3<(!Dr5{yv8Y0=W(`$eo}J!RVHaAzpIBhzSpZ8zEcBJsZP(@_zX895S2(UH6AK)MtI7j'
    'uFLqthkTz|B&eA{txq@qP)~_tH6b(a$t2_y@WWn#MsCD$3iTBc>fVYQj<PeHNDlPc!pfq-x3st=8)-{3Z<rFsZ+o4Ew}yqb$6PTH'
    'D$#X$KLI|j)=b<(fIZank3q;YjWn_FyUtl5x*3oDjO+3B8UW*4x%Ce_8}_40OW8%Kx#pUtVofMPB>b=jwJ<-qR|woz9LUYjV<Q60'
    'BLb^b+z%E6g5ur~L=#Y$L|U&Cb!*fszvm8avUi5$wVZGW?yAELRS=k`N`tvxlZ@&r_tP>xfusP07rZPKXZdg2KWFzft)Dp#vZpW2'
    'j*3aM{Hyz3kN~uDO$MG+QJL*`COyRr7E(}`2!9-JOceu&tg-FrniY2{9C~{P|6Nn%Z}DW^ylBN#8zsGo-8x^-3aMTL5l)l)**HL('
    'FLS$Yll_eH(?I?w6y(h7sqo&@dRln2yz-Ci6D{7cFVNESd-<8^-PY=b;Ve@2P<Kyml7SKZ)JnWVuFCu|A@dWUc8&Wh0@@viEN%oI'
    '1nE1+?KSot0=;0?^vzp?`8HAFgf#F5l6ZGgzje@#UX{6wcI!t^z{o)`H|~&Z%3^frDJzp{QNVz&>j%DPn*(PjKx_IsD!x^9Yz*?J'
    'goAs;w?3petUc^yTb_!oO~{5)ND(1iIm#UJTOJwQZBJBy+aEZ(dwT?$PKZ-*0C8cT>W9F@M-V%j{|u}kU|%!-+IXkUI#xzJuElZ7'
    '`hEE@KQNU+yh|b61@k9my>4JgtG;Kv)CdKHcig{Co`j}wV&1>mt<MY;c#4PiboBOuFOF(_xxx!Rgsp6Pk`q+cRNq=@0?og|J)>3J'
    'M?}Ka2cruN8%@oJwKZocb{r)*JFO0i4+$_Fq-&)Ty#vfG36Yk#2bCg9n*y6CJbu_<)g3-0Ild11ZK^+1O*(uOKjTmDg=J_@l`Ah6'
    '9x@1>(`&D&@S100&f~zig01{miL}bfDCeu_!x5mQQHY7hhV<xH{ty#p6Z64CP1{XC`Z5r&RbgX!U+D*Xs8O*f+Jxaf@!?+RxmQ1i'
    'mc)EL2E{_{Poc~lh1>f(VhW?$Fus6>vtpX;cx1mKTx}H@hDP{RVar06SF-+;UC+@%Z-tafHU&o5=1=2*jB2{446UMqAQsr_^)-Qx'
    ')y|9mFu<7xiQgB(*Mm6B0*>yVFFAry7}Yy|LN4+)=qiiVSt;BVJ@Hm1g}7+a`d=h?<_@fQo~{dXfjGqy7~@#JYE?fWgmvs+1UAu6'
    'u=B($WsPctS2Spw<i>uc*S{LL#T7ZIMk)1KS}>^_%I?j4OpK!ihBmVxFOLGKi}j;|XkrHY$c!wO1$BpZMvRnj4+6C3^shUyk?N*8'
    '=z}ur!sKCQE22r@risB^?9h!c7duwKIpo$kmuc}NO)J8hne7aV3RGaqUAJJKjvMLJpaQm@rGsw@McI^7s@Pw+9gD`9C>N?e`_s+e'
    'kM4+dE)gDABx?vssHLSXj2O-5$iGG1NDmsVe-c6EA_POwm3!gKe<G?zENnn&z?&aEPmGYVJD5dymo)lp{Bs%6g^%?~`8+xbc&Px>'
    '+xa<{E8SlR-f299*8?(nMun2oIjzOC<rFE*Eaw6QSV+yYB}pI%uM3aOT_M6VH4Q)EwsTF4!&!LY9Z@St+1fwu$%b1e|Le}Fj%$U%'
    'tkOY-vTR*;h?b>F0d-#i2xo812Oy)5-`YZq>#QutTTbUF>jwEcw59Ab=rpm*-DL_H`Xrshi3ARY7r_>=X@tL3mJB{Mub`_6)Lw6l'
    'jp~gu2^9rlE!y=Z0aK3f3{Ha_`SmXT2|eEwd72Rz<`Hr9^fBd~_JJp}CobTZYxbajESga-#!E$J7#N5cNqgt~D#V~iR5VqR6Purx'
    'GKBrOO=%{$8$?LZ#1H7RMoU&Vq)_pv9M+0;V<<R@Sr&b+M_)xjLr7Zst{VT1lrB5uZLTwl%cg1-J-uOqnyjH`sVwT{;Dfv!%txj%'
    'ez%7QrK>elbC_}hrhxEzUO&ivz4Wr?f+5uVH;r<unC`ul`-Y2keF!|UIaOU}R63d;niCQx@wFq8#c>&DdePhp06i!qn1A6%R5KrI'
    'eJf{C6geGsY+kQPrVG;4?>o)fH!N${Pw|}v09KmATQO_wD;Vpv3WDSa#A1~p0}~!dU;*jBVg$feDv;;UH@42#7=7FTY$b!Exs!i+'
    'PdOt;k%EU|TrE_kizVj=fZ-G)KJ3BWg=T5$EtWkIY~QBJJ;0xDwDEx5I6>poyxVg@Hk6$Tx(5Rh%x+sTnyO`fFT?89+((M!9xjWm'
    '1o(MLAYm{d!W<wm%+@_PgQ_Z4CU(fpC&uW`5<!F5|3SW^pjYZZ%s$1KZ7#*4%)wg_f2bKd;opW<(<_XZIL_o)+@7QayTaH=z|X6b'
    '!1wx$XA-_R+(vi>%p{p+t3g?gFg;0o>+a(XjQ3;Dz}1edl!o9hu)2436tmPzzf2*%^3a7ujr8=bHBX_@-DcpZS_BYDaWG_YAGWXP'
    'HDTE{8FMCz1p}MHj$b+wkUvztnyM7Mwsx7(H9Cy5_vZ)}m|E?>S%#t(S*~ZW#nIV<TSZicn_el4ojso&{61h=C`*#f1!q9P)z~7?'
    'j^ybL+rO>C!F>ONMZHFw?)+C?h>_DMX`hPsOi2!{Qr0?Gl8d^_j$Xs(L9~&nN(zD>^NZz`>d0*ChU|l5JHHGxRtu=PNgt^pO>-%I'
    '^(+_0^LXaS!cnJ=(M3>~yiIFa=Y8Ci2x{dljWG|^sdNsn&qH*A?p}0CAFahmC2>nDj~$`cys~a8H0O0EIcqII@>QLjw40C4CU(6g'
    'ieILwM(9RyANj?&X8w!nW(FRNus89N_|r!@)W@D=6CW~K3usE8*+t^fVUHgId2{%UuEM_?1=-WS9!iEPXan)2Qp35{V(J;^#SfbK'
    '7iJFc&ponTpggf7fj!3Yj2OxCT=4rq5)<4rn1x+-1fZ^&gu4B1pzWjUvEF4+xH6MO_$o@EJ?DVlPJ-;uOw_Z=RQBjjwg`ey;%71u'
    'YX+hII(c7T?ADu(qz!T>5ED%HUu4GhJ_Wl>`C&3vg75^YEZaS}5rYu=MSAIFiw*9`lc_%&1~ut1El$P+gnprc0~llsmGbAF6rF^m'
    'e{H+Kp~R!XAxGwxc`BWFg+ew77SN&~U=!`im3Dv&M^371)GAv5v*r{IX=JezaS!*mEL&WL2u2LxYA?dG6*}z(qQh@XNaPnep0j%#'
    'ItF_{he{Qp1oED*zID}X&l&10X*;mLP%5H4J~P3ay484Q54!~z7V8sFy(m|f_p$%jO^!Hh32Wt2*~fNzKTyNw5yII^j7{O63w4nJ'
    'm$LT6kL5)VvjCaM<;e`x<OyK}Os7m(!GhZ4sIjHt;`vyR`fVwsF)%p@quUu{-v(xt0<xK(K{OoNfPa-!gAIdLfogOMn#|6!W410A'
    'Nn|t-hr<I(VS+OOUF|@Bouu2CSEDLK%K=`%s}4JL(Bi<c)KlfRWZJiX%?ZTsHpsyYaOtm2qdtm6V#b_~H)!9h3C#pam}gMFHaA2G'
    'TxF%b`#^<2dUd?O_o!DuB|hB*j$V8c0upBWmE`*f9gKGLe~y*@2=+tXJ-&|=U4jov>@7J3;*c5t1kIoYuB_dBBRg8%#pF}~&M<bZ'
    'j>6hxEHs?Bo4h~xs>pBnhYP)GZmrE~(CHdCAjx@YD2ZLYy3R?6V`nyrPGwxZ@S|$tOm-zuMFs55MJWYwFuENwV(%^v*){)3r$1TC'
    'w^w4q5VEp>OnaM}d{sw1>rer8EVGk@$Ke!@GgL{G-ao1yrKpu^Z<z#e1^0FZPGZ^l$Rr1U=IAeS5md{_B;DHScyJ!?frD;Bwlw@i'
    'wd;yfUQ{r(wnQwe0w3k<4mQs<z+Ia8irJSR&#fD!lGOQzV-~p7B6zRhR+#mvIcmYf^@}%Z&XU5txhuM@@FM^Z+s_r6==*KYq)1m2'
    'j&@&ObNeRW(teN&r^kAR)6mBWvqmOMIH!ePr(SBPU!yiPgYtyiy!7!Vr4E6_5ksbjB>@QL&n-!ae&??YQbk>5>W4Q|k{XDlDoU3u'
    'Y~VP~zoZv4>Km{@FPqr}AsqgL$cg}PtXe$oy8@K2S>{K}k^aTIW&<U15W=6_F?xsOSa@FYtQbJBBBfN(Sld6io0@^A2Z3rCkxk&e'
    'E_vxrd8#G(-{ZaNDyPY?Hvzb35B%EwwP_I8UGj_)ptS0knbY^#Hvgs=<GV7S1>Gyze@Jn=%3QQmpsp~CGKAf#;x4!`NT<~eRkpke'
    'c>;qOw5L{#qD{fOcj*x*&$KRSw;2dIjR?T(l2Pk^s2x&YR2QQ_LR#wMPai!kOio=aeY3I^Y$LB(NqHB`<NnjuZ!&EJj!Gl_m~V1<'
    '*qbu&*Zk{kyomXXNWWr!-}-zjIpjW_h8ewV4HVOn=Q{~+sZ(iewRpIYbnM0Z_IJKLSE}^ro{^MxmgK(r=t5$DgNeoanQ6aqXvn$@'
    'qmsuVGoLJZQ*1655P&hA7wjEsqQ-Xl72Wj)GnWH2!BnbI#3smYag0S6!PU<N1bi*sLA12&YrMt&2`z(BTt%UB=@!lUKk6mfJ-`Qo'
    '6wE(6JMZU;enUK^1_V308UIfoB|8&^CO&gpBJT4K2Cw+>BVvq?f04a^g->+e^1YOk2nm_II6JQ7Z9q@+<4+^w*ee_iuvC2iS2hQO'
    'ahAw_!RenH;#fRTI35Z({y7#ofa$j=J`Awnx&xD$+j3DXR^lja<9f<9zJ!TOyXim%2!ChiyhDp6ALzIrig8d%bXP6~@K+0n5*EpT'
    'mL*F?ZlM(O$}d#M#g$K|6Q`n+mUuPfPDg4*=`t#)tnuI+O(m3NB@SQjhWUl1af|y^Gsp+0q|Qt9dFtyb41T%(u?_%afWqD2vY%ea'
    't;IFlJ5in3C5$=*OFMMjz{9RZ4>lQ=<U|8I9Lu7+E};kNoEiv;J^xOsR?KxAZEHzfNV{P($!P+#TsmL}oT82Ehj(_*SjK)kp-ej?'
    'obZsa*GTG}Jm;ZOh&=}bItBM{GZ*fD?PCNjKnFIEJ~c7#BTN~Ms9Ds9pe@_W$X0=iPXp*C(fl5Pwl0Y&591darbgO#3`tVfGk-8d'
    '+ZPx0G7x)A7sZ>H1CgIX3DTC$c8gGRHqvy+dZnrqNfE#2;ut978$!}uatmU68YEG(+MdEN3-?LF2&=iV-!##jZITzt4GQ_MvLh~f'
    'h&`Vf_U=A|r{O%gA{^3SzP&DpA3y4URBq_9@c8|z004A?z_^snHnG1Yp@dHp#^gNiC-aKa)i*uGe#cML?D)p$<NSZr$?fj~zG<Qq'
    '=cvyqb31lGQi;>I;%O=UP!@P(uUvr@n#WMvZCJDbFw77bq_<&bU1+>sEpz!Jk?!Giq9;2Jsr1vi_pgDSbg%kKOOYy51OiJNpJ1&I'
    'qpO>8r}ZfWhnKZwEsXW@c`#={^du9eCh0stM~I?v0eOKtD@q7ITUE=SeRtM3yAK}}!p?Zb>Wdsl$Nht_8n9SqhGtn=B(ev=Jc$9W'
    'S-6&OgVGlEaSHuF?!Qv^deT&HlH-UScqFC;^1`V%424I_znjcT$nDijrCX2NoMNiN9!#nYzg%#aCl}43<+74-`ilow@au&JuWZGF'
    '0h<`=7>1QH({_@CbojC&=>rd1@NO4WKrEXO>zxCzj1J9I>Fxl?L-k(wE%rk*=PZY5oac%_OX}XWu9C!U>14wFHy}})ka0L8w?`>7'
    'Qn-({As;$yWK1hlgL9t&o3cr7s+EHA-C_Xi<Lp6*@rp02j)rPexYIQ@mrcw(BrkxMDcbPP3s0V3rVGK2GqbI_`mMyRqi1ZcKz_oY'
    '+zcH(^-)?XQOGz@`V>Z+={PO33xQ|Npw1g18aQNXlN43*9EI^Eq5Bx{&o%ebQ?t!8WndF~S3D@>en=5tp2C5ffB2VZcTuZc==4Ss'
    'dvLs!8W-)WJgZaG^YoI#aootxsHQb5lj4Q~gaVy#j2*E|IYz6Nee~kkt?I?Gk(7=3`QXz&QH^6KnAb6A7A<5HH17*p$lqM2jjrHP'
    '5)Af#<ExXbNH#zS=z}d>>`XpWfj4uY<;H-^b9h($#}Re3N@Xb6?}*P5&10V!inykP*`q=CW{GO@E>Bj@B)cn1`M@lPOb3Vu<Kqbn'
    'vmOepyEt=<r6hZ9S3>s*Xi9!1Th5eVj4b5ham7(rk|?cL4WB?49)s+6?}m2Sb?PIp3tNBc6W)t7xlAu2jO;a(BvFC(QB^jLgMB)s'
    '@1L3A(-6df34C9RiC5~%nDf&X{dVd{-ix#CPuED!u4CRX(P$~?DaY_H9sG{WMiBTwY2XrS*NO%$Y68EaEk}_?4=1GCS7pR%P(JZ~'
    '@^>KiZI$gOZovC}wjeNRB@)U_F(%C7&W7yxYH*br20aIwYe)K%KeidLCTXoW<+%9AX`lD|$kVItp~J*BMtrW#sBra*DKw9<=2!Jk'
    '?cN+D*v2p}+F;a-SmU&;DIBZ9`6A7WH9#wlH3%y8jG%I*CCw1U5c)(x(BrN?)*pjX*~h_Jgd>+1t%rI7aF5K$8Um`NeSw@X-<;D%'
    '6$18E0jPTK(kChh6lilRfb(v&2vkw(=+EY*BcC7rr(zIL=nQ0n*tw<217>ZohUu@i??a^sE$_*`!plg_<6_v$HwFxnxdK$DAz0{m'
    '6A&oKq0a_4{6HoUlG*F2?HR^U2M|<OMID%20WGWRr?%(_I<yLWpfLDm1t-rY&S_~GC-4S&xvqegWax~i9x5WzJs5s6%#K??9MH$C'
    'zIc9Y=dbBmksekqVfDRW#UP{#_~5CriY2Um{S@K2Z&fmOugN77j}y+EFqVH^cU;9UXs5#|RKp5N?`-C;^I^=XO#7<5f{(sdFQw6j'
    '*X6M^-sUYeK-?QT9*3U*Keribaf`dJFTq+YPp4nXLn(I)j;>V0ZIPElpxQj5Sa|7v4?)l_#k4srj^6u8_yS#~<`GWi!rPaB(dzYh'
    '9pVV4Ls7C46Ety6=b<)f%;20?pNwqX7Xee5#m^-W(RZW<uE_O2MevO?Pl1kE;Es%knV7&p_{%LTax_R|6~vjQ%d8uUk@)WRn%o_S'
    '(@Q4-rLAuso25RX+20Rj9$R5&{8mWx7KWnZuF;zwejdt<%dgo6_Xo#k4#54V{e+V~b%Wmhxw+|ElpSI5-8g-zv7`Gpf~ST@=0E(!'
    'Vt?HhNJ6`^z=U*qzQPvn(geFxe$Y*YRXLot0RU75lQQFbLp^=4U$~iT7$({VPGvOfQwH!&V#Je(Qeu>}$#WM+a8u&<!2J4+1zw#?'
    'KUZs?&Or33?8&Eu9>ZF>)aS#5SDlQ7dcs}<6hTlffv+6<HC2>Pd3VUAAsP!bsh9T@ka`Ti*P~vg4<u9SHsZ5YmYqSTkAJomRyaky'
    'dplYd1uw4@m#Ak4apIuBepa7-yqBwA8HB8Ib0@5Z<a-2VU1L`5@|N3c6eH#%^c7Ontt1dLeJVm@blH!sqx{f9rLVHxEi4NpIX`1B'
    'LN1GK6*Cco%K`hcfu=QT274`O(Kmk|Vnu{rGw=nEFH&`FD+1T7LX6r^dO_uA_O^qR6*&S)d@4zb24*r-Ad(|G1OzO?)?s+W+e&@e'
    '6xTFwTU`u7Kqp?S8DGKAm{1}W>j!*C+1?u1-OQany&?`|5{?g%R$fUJ(Cm#7aZ8j6hH2Ed@Eq%M^AwF5l0>y9W5&Z|@H_)3+#Mju'
    '@j<E{oZoc(ae4N9jq%yW40UIQX%ljeEdj^=wq>?!cMo)Bv|zD!3j&Ya_)5hl8c>kO+~?quFyq%2?wg3&AStiuR~&%<J`3DfFwW}?'
    '-zyUSeMi1w5m!AoI>^6<<IJoM@`wG#bbKpi+ngHqghEo#WW?wMsoJSqVn4NcdQfb0u>?ybM0iSp0wYWf;f8+cNy^oq+Byfj1!Wo6'
    '_;lpdruG#XD9}PICcTLtU=4^ZmmS|V<8i}Rki<yO65f%N<b}>di-BJmIfxqCl505D!`up6eRas1LQojgrb6^ZP6<&o(hq~O7q-}$'
    'VVp={Iyf)uAk?b&@Uz3_nxYV}maC_F8hwR`Pb?DH=0am^KBeH%R<AZj0GLU)`pkah`JRCx$v~RAz7NxKWkOTYFVmXYdB4o@K(p{='
    'L><?_sP#bje~=m54;BNz8V1QB*FLgjvq$Eb)p4J;*}4}z2LoIEGy(LW+FKSc^nToU`C(PmY#R&>6Rg=FNC|p$2hc$+&{`m&5U__s'
    'ioIovC5m!NBc0mTFH-zMc57`RJ?5wFwk=myhMi&jS*QP<;%~!_R{O?3`3DP1I9UO&pBlwdKBFv8x*-qncoz3?3g@tU;%MdyMZgO8'
    'q|loP>m(`)Vzj=FHuKA%c1s0w-;GcaR)E|p=C`Zu=+(v|VEbS$98~}2rrKOrub&+uHwF3-O1m6yDF@or5MO*xe(^pVI!rhHV=vN9'
    'C0HMM5hKNE4gS(G(+`GT8Rfg~v+)t|KM0)pYy-C>^@t_?POjHxf*Fw-=9{-OpsHm!rg#kat}8Om%Z{FAyJcV7{z|Ah_B#@!Vj7tF'
    'GiWq}e8r9K{sg-NZ;Rn`<-O3PcP4)_-$@R+$T!Sqge=4jypT(=O&yFTusgNij+w)3QrJZmVlbitH1;V_8p299e0w!4z~?6*i}IHU'
    'iS{s|uAJ0~Ek_6sJpqU=vZ@<r?}hwk)~VKj2Qgv}L{cNj5G7m}WAyt^-wYG<p@}5&F-S>vvL<+|g`PNaaPYFnv}B>Yj!5B>x{PJ~'
    'l{9w&*M9S1gVHxHuZu)Nej#STfCt1jUN>x0-_IY{fFR}RG}wPMz7%1(rJp6nD?#XIuN$fy@su`MW#2GsVE%Ju+Q_%(9mRDi?lpb}'
    '<#hD1o=x|r3lnnqIxiK*WDf>uZE+AkhphtHktKZq%jj)<u6gWqR`8Rzx2G*R!#f=5d$-xY1y6xU@BKd$b{YaIKRZFosudmsoczu('
    'VZSO&;z);l@9*jddhj!aysP&=&U@gi4UF3In&bLF^}R>DAzMp64=Lq^?UKU(<eL4e#NY#iB3}M2W&{M8>F}O=9C!|FPp1v3yUt98'
    '2J0hS)P1_vqAu=E9`pw;AG4J>1TI+&;f%sK9Ft_|Lx`<mqdR4WBn(wrM|`X#LfuWr>L!x7d7503GQYt-cWgan=)89tMRISnWQhJ7'
    'zQvhA?NMBib(+>1H>ZSWd_vLY?^NplJnefHxLfLd3J6}%E}%GhAR>D1FGujsEx`Zx6<BfP=1cE3pw5A<L&BV7kZx%AL0gtN3<WU5'
    'U{!E$15AOEtU{vW;;KRlySHil?=(fDNt=(%by#uEQ=r)IQSGB}?vv7=I1^}j+>bX9%Lq_>fxgF5Y}iErW<Vz@+`wmyVKFc7^oRZZ'
    'i>pY&QVhMxcKFvVlY`!damiV-I+@(KYq*h7Tc#=~VXP`J3ctvL>g6RR0J{l(Zt{p^jq7XCq%&>(8RofIWCDX&H4B0Kj);yP>^##1'
    '*h8(M0dXkTGH8gn`K|U@Fh3$Bxa2&aiu5XOU-G1_;Ng>XQdte!ZVh^9UtvWc>7#aG1W9X1_QiYCdRurSY$Rj)^9E~_#Q!D;amg&y'
    ';$gmk)^9twmr%DNTXI7}7sbvzCtt8zAyBdi!^?KEEB;Ri>5(R%8)<LQTF9g@7HIVHCWzlSw*-5W`*h9cK`M}nY5Ra?G%zIT_omf%'
    '2D@}v<gT<;A=M(}!U5pReuX!tALVI~8-@IsGZt1us`M=wg93Vk&q^kPrVQE(>(^@?;WbU3>Y3E+Z&7|^s7E1a$P8Dv*HA*Q?$h*D'
    'a?a<Bv%Uk=Gn2*3@wkDgF-X#D(?_A9BC4mJV#_yx!-tu#N)94-O`yNj@eP_vlFwcIAUc^+hxFegXNbO?ykSamZb|5~rz<i7>qh>G'
    '_K^jtIj%&I>V3T2nhV`jp?fdd4E$J!yM2aVP_D#8$=+IdSpmIjO!0m#f`p=O0-h{AQ+=?~-ahFMk`6m*GECn4`?*rJwj3BhjM++r'
    '_R{zugKqtB?M-;UDp8l(q}M+qR)Xy?Dc-rN8L~!g?C?sB<957uNfUf>I~->R>R0NR&AR;xilk#%Vk=StIaCNGt6YTULKA2o=nJiO'
    '(dn8%wc@S(EDWPMk5Zj<q{jy+js`dgMcEMab%2Jx%b+CPI_vcvksDWZ=?EMzpKmr)P9U$mtKBW$%$954x+2z3eJ4M`-izHBVbaez'
    '#XEQ$(a|PFw)R+CG<b{~kbl00!-8H<hG%CnjZc&2_dGEuH&2s+4Zl1!#8Vstf)+<5RdfP%jH8Id|Hv8%K#!D8Pr0&@VfuN~N0;ik'
    'H2j$E5#Z+NWL|D>@(~9$mv&~M<T`EXHVAF)q5Q5drw3@NDmxBT6Woa9*p(xE>6=AF&Be@i#2!|^0u>XUyy**@laEUNc0%BKxKbx<'
    'r2Ss1Kt`HWn&jQV?Renut`{1_Lq|f&Y9Zhy4*D@B&M@SBNo+tH{C`xV>00{%&{N9kFf);Ev7I4>uK(<$JOn7$5flZmQq&2Pt?X<q'
    'u6d(Wi1uuC$T&dTL;Df%SgF&-8fF?wwWR$*&y>7}+frf>F0Wu=lmyXqkJ-oB6=NgS-aw?Pg?4$)h36-)=APT9(|+MeaD_j-I17^$'
    'X~u$g)7uv$Zw|{`zq9@vY;1Xgdc@=Lq~4xVZzbFk@YlsLL5Y9>vfoO-4ULXbJHJ4OwnNi_+(pX2=ATLET+JL@XEv92Wc){5_2-wC'
    '498E#0t!sarZ`v<HAR{L+MUW`K~AI4hfzUrM#GPHE%Np+U0Uag?{tV^K&OK5I*XU7u;j=DDmK~~Dm$c*F;DIgk?L#@%Gc(}v%933'
    'cPRU`>-J@(OUKf#JGdo|{8$^Y7TTUIDFbofiwly+y+O1VUAEWn>IObe-(0_ZR3pKb?Iny`g4cLZ`}O6<!im&~q$sE!F6cmE*BRYl'
    'mvVfMc&zy8^ew3YzV=z|*~B=PX;iJ3aEdhwQU0@=7@3c1r};ji1OxZoST2nw!^!+~{0?+&n*hG+<qpV*Q`~z${i3eEbN{EJb20|u'
    'm_Z;6oN5tr-1xC;i%6TNUEI=<#}TE!J~K|u{87iJa?>j#you!c1fvB@5Q@jkTr8dxf#E5;vh)ssuW7AO>sOsOo@BPyrB!W0EAs!C'
    'c}&?h*L3;29bf{`w2GnUy-6`+@ItU#ml=6_&uK8H{^F7=Rg<$i)npFT^)#4-aOhUmdL?rXO!>a%OR*MqED~5-t4^Qvy5MIE0u*Ko'
    'd!0V(kniN5W3n14^NlM6_Smt>XD`LB1Nd+dZ_}JpR(y%&>ssrs+VT$C{(hyx3>o_4Mf@hpf#v~)k;0jQM9w38wHxdap!-J`-P4N9'
    '{(G1{;c;pLT00DbK^mX}^HnT^)^IZdy(q$sM?^~BlbFHmwJY<tFTPNw7$?k-vA-14F}&8+nRqq$4fxnGjc9C!VhS(Is`O=Kqdn~('
    '%`8D7j?;)vA@(ToTycsllQoO6PFIJ+#A5*$^GLKsp9jCQrI{K&qF>3P2g%q|0+~4DfKDmZDu9yS;}Ggy4cpDX{g|Y(Bg$NEt&`O`'
    'C~1Fx3Z;3<Iox1w&&6GryH7#hyliC+f9;&g4F-^J3X5HCN&|^``f(c;2k}IsUL)T`;C6OGo=g90@}`ulrmk%`bY`*gIa_$g7s5}X'
    'OC@kfp->besZv-HL`CFNze^OJvxcm<2}sS?#yGA<wcfwdIad8vijn4h*xg2Be#v!|o?yo0dPg(w)=C=SB};)!Cof3=<>XOlQiw~-'
    '*R(nynCmP#Q&1=?Sm|9J^PrSENvT9Qb~J}*em?0%=W`F(@*oSy76!$5S=7tK_oVG?^Upy`lT!*af3Lm_N!1?MFDn%<QJz{s!V|!7'
    'aG`v-NKy+n;j*Vbffs^}f3aN>M+f)KM~fmI$1*rVWhK1?b6c-;kK!VTo!sUuM-T$(+wvsBJ4`iBK@#Ye_L5m0qkwH)7U{9r*jf<k'
    'iAs~T+-pjsE?FF!mz-PkV24?LcRO=Syrd--`p_{YE~w6;mmv~|#PCmz3H9(fCwJs@{lRwB*LigW55&FIeOR-67T*Nu=00R4jpOw<'
    'Zt$-#`3(`qqO~}Wqs~G!Qs6z*U#80KG*bb=N@wvW_tfiz5W2T8D-dLjzDjsr9(bA#bx(R<|80O;!eHX%ECVv*NPq#@OVN3O*J`P9'
    '>ewj{C_4&{zlw?g+2)RtO5zX~GBI7&JjSfcJRyGG-H3^I$-(1iZ#IG9M{F7<MdMB>8B3XDAskKqL>+93qhCAU!p>9Gnb5qXP~?~n'
    'l_Z4nR%u}0(1LYTGbH$>6ts?is^15dR%8Q+N=l0gl85PN5Lwp;G!WkVt9g8o<uKN&AzBC(nIc(;=;bqKNRC#|kKQhlW-8d4!!668'
    'ZJ|dsA&je@OGq&c(!*LfTZ7ok-(nsp0)X~;he9A#$Dhb$*KOL64Q~&T@OR?V6V`<9iB|(t^1)ER?j`vTSa<~Z^4)vj+^Tlk|J)>R'
    ';#SCj{nwu9TetmJ<e&8i5ONy?zi7P@zvlR8zXe}yW;vU)ZWM&1^nR(x9GZ5;?|f1RD#2$`%qd?2XC_)7>7vXl5|J&qFn$F1g8#kx'
    '?P?e1!otbn&Xg&mJT{Vj>_dM(@i@x>uKGN|y2f%3kPWe?sW7z@2#0xRtaJ<CsU{0ekRm8Htalu{Sd)FlOEd0a;N3{f?MPA-4o8ZL'
    '*{LeAF-{#7|8}5|(7ow#&}j0EWc;b&EZ4Z>jYXy8#Vt~@w<g}vMs5-82HfDftmcvSkYkf|`4$E1S^6FnOF@GH%G_t93$$#gzakTa'
    'KU#4X(`w08uPyi3*QP?B-{J(k8(q);l1Wd&c4}98=1asvH|H+gV~2b@^bV!%rnJ?xk=ZjTG&g^v?&q8oTwuQJ0(hx(m~LTZX(yJ@'
    'WEzBW^Q*(><KO+KxeNsHlltE=NnXs+(RcYH#b%78%muhMPpYdVl3Qte;D;7C_}?YVgXEoV)UGt{02~fv$=|Zq&tBy^ZkIbNZV#l9'
    '3tuEHvn`{>L-?U+SGn={jooxT3odQ*^rf>}OSeK@t%?V|FJ{4&HdvyWW&Ft!gH(>~m%=+EA_RPIyfe)-48mG`=!YX>I_++t7QG~?'
    'e7Ad))?=%~KSpp5Q>YwSHkoWGDN)I-uB*DWiw6p1HMs*CUw*D!3?sS@rRWzGzYp;0mUHL+9~6syI4+q@M@HM}5t~wqSE)cBHE{he'
    '$4>$#`R}LzpOj&<+V&AQJBXk$T@8+{YifM!jDCD7X2lEVz@DY<xcLwbc?Dx2^vF~;-R84Q$4a5~zW-2YagcV4zS7PHTht&Qs4QL+'
    '>&<n0WR?IpZ#_SP9mJi#x8W?*QdN-S%53#UtcCj!V#k3}b-ULI5OHOHBfOmDuHm-kxK~~v;WQ0-QQX*&B-9<ZnAdv4v6kIu-Sp%`'
    '&}i86ef7a;ezb{<B{xi?-H=R<Fr$xWxtTeZ90GJXLAH(%jN-2Z^^)U@*W}frL&_RvPB5)KaT$jutmPW)x*Xop*PD*`Tm{R>mqNIl'
    '8l_p~H4T&H6(?5IcAKTstD&O(?W64h`8h<;j~vc$lEX`-q`2?=wpa)WIX{iSE3v48DXRp`q!tpXzT%CRDYr-5!t<N0b7^qShXn?n'
    '`Q|bdF=hZ@e#ZXgTpgHr^gEl^W%aRYyA{JJU?J4C{+bgvLx78y(KiCnL_%TY9Pfb5TtbSzbjsVnaln}Bl<hj`1=g{s-zAb2p#fy)'
    '?gIY%o}|sTbGJb+{EaOKG}KFmNJgOFZH1-~rE!ucP1;`B@kf!|l~tM7etM4B{Gt}mmv)xc59+tS+`=%@qy@<HxpdRd@!H`4_7jbx'
    'N9Cpc>+!M8)fDfsTj-zje5lK<5z#d_j<&&FXG(wJ-fM@ZiTquoyD5`AL3a4#XWZ3tB6Gbi+EfkulW%g;KQGo3x7h~iE3T1x<k>0H'
    'Ht=HSq139tHpvP(mGTzMLf-Bn%63~tyw0+2@3|X;Y^u9(T^Y1>?^}V+?dI@G8AhtZ<qL+BxGVfQKF=B>6?z6i0p_UTFMKuPo`Thn'
    'f?f>K)@d+`_bbwy`YMlT#4iaqURDMNmqxn^kUAB{51-)B#{}&wseZ|_YAB5JTwZAcl&w486(H&CArd_Rkmc8|!9k_}WuwOa6QA`$'
    'sfr_fG2)3EF9udB>N+b|-j^!eN{4&?mKd05dTva<a1}<M;atf8)iRFSipEZ*2k+#u(b>Inhc?`X8Zut?cb{PPi9+y<#l?qI`=5JY'
    'V<p2j3nF#5ZR7U0byYDRR3<)ICq3XN(Q$2yh==jebO7aw+T%ZJ_}I6~uu3d%9+X$ah~q5?>3H+PB<2KYXsOBm?;B_0x;>@g2Z{Vo'
    '^1J4$3a5W*ZUy-tJ&#Ck5#sZLKM>sh4HqdFD*n@&6yw~xAgQTN=qLz7wOYpM0Dyi}$k-vxXZ~hKFZ1PevZ}-zAIvW=<YqIQv~7p9'
    '^?+k*c~6?VL6}NhUdtzed*d0=I@lkn5?-6x9a_sq^KLJ1nRnIan$JAiH0qCbA-f+y4j&m2ntNax|HZ2?Zc4|yn%7#@eZ)i9%{G#9'
    'uTFtgA~wVxK<359p`&J^5^OO37O--MTIe$1%5U-HW3NY7L1WZ<Q5s-VCh053!buANOinQS3;$C6DxDI1>R8Th+(LLBaxh}djk$=x'
    'M{4PLi;}tH_F4<~BaA#fkR(4cHvGKRhGlAToKga&S4ZX36Rr8f5F4VCZrS*=5DI*ftxW5nWAU%>0iU!_Lcw-&V#Kjs`EmTplKL$>'
    'tO}Jeu==wk=dvhi6>0Np2MwG*=_k%p2S$)w2%W~wzCR3Tttp-%@Z?0pZFKYNAv(&)x5I~Ho^tZ+@5HRNvB<rv-g3fZP3Iz@XLZ~m'
    '!vc-Kz#&IDYcX(Hq5tN^?{5fBIQvPCrsDV3#-t-Mz4LILXaV&y8e=Wa>^tDr7?v2ehFc>_J^YU^8qO*26C-@P4$Tz8#c!8v+A*;s'
    '*VGI;{E`X9i9L_7rE*$e=cg@c)UQ)a6MN~`C&8%wzh4fts8XWgKK{xJw*wpuXivcsMXiH2$O>%ve>xj%qEfd!YoEOx@)T;qXhPuS'
    'm*SYjU|;XtGI_t0MgLC>r*e$?L*Kw`C}~-8t|NRrYFsW-jt_CCJKKs+A`n1X4!W&+YukWK?4%*e{`2(goAX%@GELDo`5TOpoH$<c'
    'wVwaiVxE_JR5uiC%0^e0Ej8^iT)^hN0B2i>+8K5!8@Qtp6E`MjTrAz7?v4Z|&rBa^GiJ=+fU2G!m!|z&DfP!u0x$N{;sO(jrKbZo'
    'dFAfPZ)65i?hVhw>gv!7|H{4zmX!&4c{LSK4U>(}#2aVMx;+Mw#bWj4zi6EQFFrF14f4u1KV4X+f;ns|)L@}sP`ZMr6V47CJW>Y5'
    '2Z{iLbu?S0l35hkUu6VTrG5xfTWRB1EM9|)e!Sn~I1Sv*+igmJ8?OV&5>y7fIX~NEs%nWrqJkMV=$QuAZp8oTWvb(-^C#L<;THLa'
    '8*K9qTyd=|Bm&gK4z6oQ-(=LlP*!fuQ6g$=+6jXM(ePulm8DV#9O<<k^F<$}Ftj=vOjZ4jM*=l~=$U<2g}w}whp!DNLU9jItLE{o'
    'y-Hw5+_VT#uYO-Tpn+=zXo-z6nIAYM8A$Fvta#5ye9l!hoJ5Q@2Z*4#f6wB1(f9g4M2y;NHa$ZDkh~|uzeuOS>qg<_KTPmZKue*f'
    'hAbj~wSz)szh>xkydILXnHl3u_ICk|N2T7N8KJ@uHtQcGCFpmtu`MO(3{#)@l8*3XG^@qmz7h<wG9E!t3Hl5~a#lohhAvUP1_=5e'
    'z*kc1hrGitVeFqn8kV0trKcsmGSJFd?G6DT%Ai^4Qc8jlAY&w$!fH(*k;-dZHXXqg^P3f{)j4(qy@WFGxbp-hF!kc)bh+rcNK)Zv'
    'ddo2xaO1?EIta3ZF29i?Ix=~3ReZ1lHrWHUvKL|WDO+!BuC3tLxV==jvng|o9&Y*BNKhd;F~yZq`+4-DBN5@8hvtqU<N8PNf6)t%'
    '<PL*h-k&j%p2JslPOT=boSF;US@W@vUr(OY4pb+)+P5PU?C_zYBozvhd%d*j+vALUfY@&o(miM!V^;hfiP6|mspBMJ8qa1*RHvX?'
    'xXbTeFt_l#u10Mr+yZ8kUIR9UGVC#C#wx57@oN|5^RzIdc*cs@8w|>;X%VI`U|LmnyG-Of`A-<)?U0{%K%6Bx0$eSJQ~~Zs4WOl;'
    '20K3Ol5cPiq5UqC9_q(VyqTa1H9#Dw)!a?t71?%6?hMkZu(c7;N6=oQ$NH<s(rg>2_~Z2jW+cQ(HOyX(Y2`sZS`x~Qi2nb{c+*v2'
    'zJuFOuPPO7Ib<~-yqr#1ZQfMC?!PyzL3YnA2ca~<xyj2C?q?t5*rwPR6aCl=)y=8@4`Q)bd%3nMQv(5oKl-{}NJJEMM?3#n>=m?a'
    '7!rw4qwk+SU@$WG>M{BR-O<%_`g}J@s?6na1c(6zL1Ywd<`DaJ!EBuT2}@1L;-f`JP`z@z@GO4in#=!zvPk?ZrTbidPj-2bAT`Mq'
    'FoFjjUIj&po%;q;<Kl!`*Y{_@6fW%_ufau5{}5&+dCZZkOEH-PrDJZhGA3$jmk4Bzmb{j6FLOOFjcB0epxTX6(PX?hi>A}PjV)5~'
    '_l|$B=d;PAJVFfGB#7`f{-%`_K2&N7%7&u+QizqoCMlPDkonIvg}rB>smccZbdv{Iqdt6rrV;}MljJM<pEhfw*Aq~)y|A1z;T&(J'
    '+B(CNL1Zrfg^GoE-1s3D`anJjETGa4Ae%p0+_9zYTsOS|y)Z}^Tl)uEOV!GL(nTX6_85C5VDy9Iz#hEzbM`2+$(rfFW?(j5<&O0Z'
    '4>~7OEko2xPkl&?*|%%4<%p=x`9)YeiN}<B4dKY&We_QB%dG~SM%jK^uvu$QEX^>VtW8VlZajMm^AO=06^aLsI%8d4!}$YFV#Eq5'
    '#NgA}3B?j_va;C?|D{zcCwdt~7JuTI2+OfX#M-B?Igv7Y^r*()1Qwm;Xw~Dn?9F4-4~Fu^_t8tNY{tRx&UKCROa7T1Bv?83F%o`Z'
    'A7wfGCHSmSJQkwjRs?2cC)J38U&|&BsECL|AWc>9hwt*gFXlA{w8qEv+&tPyqNhIWc@~kc4r<eQ&$a?3Ye0qWt$&7N17zTMhk|Ox'
    '^4kjHfmS#Om?Fna;U#9`Q(Wp79QOBC`96lacvo#4JRcGBG7{(QuQE(AF%rF?oOT5%J-s}*MdbQ5wj21GChHVr{NnpV+EWEa&V3>z'
    'C7F+jZbT%h^37M-ht&>yJFecFpj@(>sseTGjo~O_A&wz`aV=I8?Q!JN8|4I4h+r(C$!1rB$@y0koTiNcDOA2PRn-%@`NHNGO2&)t'
    'Mg{Ei!87_v+r$so>#gPsuHW<%ANTL@OH_{Aa(?+@LSXbq6hg6mb2&VX;A11~{z)vZtu#A~jY7}T-9WtHEO=kHrM4MSmGz@F$YEq*'
    'o_WRFOgOe}WBuM0D4{QLvFvD*171w7ibWz(%cc~KS^A9+P0lGMV2klaz7nuU$v~v0D12gaa~CNFV~2r5>>gJ(*RFfz(p=6C#BgzJ'
    '9$iu7RP#Ly>$c&mK2zh-J<EQ=NF3w%jGz+*A=h2sFCS6@d$K=LX-ejsgGCf`<tgH7iG9M!`X6vPZf*$53)zRaVjVyS7raTE0le#1'
    'UOxLv&r%%ED(^$N{YY0imu6$RIX_`(^{dy_KYOviTP7!JDjXQ=KiBBlasE^D2~I!;EYEskqi)7~DrYlE^^V57FVrUjp5p(ot#)`?'
    'e<CGz{Mv7JjYz<dRM)3=jlOL?X1;iueA6*~a72L@&|dt^YxXS-36+>#D{iYv4cPgB93<h2UN_-zaJH+|-owH*yYo3ZXv~!%uX_oA'
    'f^^tB-W~jIj6RLWs8mJi5%Xe-DFbM5*t+re@Wy@KxK;;!9%3l+p@DOBy?Oavh`Ux5igL|r{lzfcG*q_pnj~TPpDEPG%2#}f=Tfa)'
    'I*PeY6yvNwUyP7@+#y7JPty2vqtXuMS4R_+QzD~U%xivO2e8O;lt$fCl4Z$WdC*@UN^0vnTzI=Ox>Uoz+gZG9l_qbNW7fJhU*lN='
    'F#QJqtdt{w<^P@f>2Rr82FO}=H*eiTt7`=V!yqQexJGXHbuOfi%)HZyaJ?heCh{Rke2Bp!5HU(P(K%>&$dw@NMc_n)wvzQ@0M5zt'
    '9&+zZMkvdqpE$`O-dLkX%cOvQn+Le<zExi`<8@`Ui$9ZPX~A09y9qBvRF=!XM(0fN9BmliQ+?LfXQ#^FN|pVCO7bep{N^o1iWeuO'
    '-w=ZIHR9*da+3~*oSm?rJcTE-)8A5jm=D^7;4rSWmYrb|UZ<gZV5MieSQ9+GTC+N<(vqKo$ARB0bjeL57~Z%4r&oH#Ldel1a_Rjm'
    '&T4GF-UXXFm$C$r8Z0qoGo4*SHRbN_IjYa<EiGQ3i=cD7Q|Bl6{pLs&d#f_MQz^#W)(cJHWVC9g8sfXEw{W2Vse@*ARm11d#^CI6'
    '>-&{9rkBpL-h2~!I$NzzN6lLOmwK!>QHzzNl=9o@_}rhsbs@tRc_g$%Ar&YLy@s8*$H@Ytamz_#K(ES2Tow3nklFEb5P1<La|b%A'
    '3~zG-i0|B+xzAR~3&YXN7Fj!$s2)c+hWu=`rVy;<_67w*mK#~iNM`CA(x7@iU!w*vQHw_i_L>;$+AYxf;-*Tsr#A`;OP2(zMWhP^'
    'Iy?UE8dY*NvE$`y25pR!F|B|3!DT5e76thELu3r-BideiczfZJ>;o*e-Wj=iXSz#8#*A7?y~1g=N<|4JC{5-TE*1y(iThlQHw62h'
    'AR}RIZ&#AmCD_5M&}>C0mJ|*9Ws{et5{`~&rMjP|gg$47;QR}%Y;W<A<LpmRwfc+0%8AFzs_YC7rb0a}JMIXAsAB}S*(HME#D}qD'
    '5d5W6Kd6j~PgEUaF=`$4<ufFp>Bn<57H~D-IkQwyf5shZaJyj{bk&^r6VP6gtKRgYr0m|{YtTz&eT(R~r}Qv{C<a5OROlri26&J|'
    'Zm1phiHyR@eAYjd<A<QF=6#*e_#n)Hq7+lnKtRDMui>H+J;M)wt(UmrK(GgZIM8&&jSmI49poK$_>*MZp`TEk6MC$^QJuQI1OjLr'
    'tmMXNN-T-W5o1BkTRPM*OAUx2I>|Q+MN#O45;CDYF+;nr@#tEPyH;F(4%7(U`tgkrmpwama>^O**gGm0!~e=BIcpMZ5}bnU?F4`8'
    'n?$!dX)=GMo=C^EJ&;Lyhd!hRl}cJj00h%y{-HWM&A|>vyHu*|*eE0dt685d&g>7BpxUj(=kT#|1y!l9gi=}tRrGZyG?)xzQK<T!'
    'O>gMMhB$Q2Z%4S3s6}nP4)be7JONAKjf3m%Bnpg&9b7@tAk)r;@-D=ISTdrJ!MOoK*B0EEA7<=p$Wxz(d6)CT<l?rG+)4c6&S9Tf'
    'ZW~n+bmrYKhr^m8nyar!?z0OKBT-;%V>ANh0Z6?GY1vPzH@Od|By#o3=cDiL<df>dSi&Titmrd|36BR7L2rWPT`F$@$1=+TJBe?s'
    '$0*5O>DXu9fQsWQULca~4g8r!&_xswRT(8%{Rs8!$2mo)t<tf+8uAbj83sPaRlD|&t|DNq#{)PRr>9Q5OI5?a%3)9?DMbJ`=sgh3'
    '+tqP(0-YaHSxecDpXIsLNLtPB=bBAV0r^DhU}mH;Mj&hK<yBSYbxuWxbM89?7W&Yol7{nDa-VlWf##FNu(TZNZzcFh!bA4k)5>JT'
    'axAHazD-0J3;WDWQ&ibO;#7XWW-%{rVGf*y652d53tK=sgKfSMdZ&%48rDQ#H8M3wBm4{O`Ki{oY+;qh7gH_cq@St0bz5k4KicRT'
    'd}f(q0SA7bmQ@rLIp)%_`&L1I5KYGgzcztLC0$+__0v#tCm>J%E6FFO|G=V7g?@t*{HnAN?&>s=shIbLqg_lqUk47ZNa#ChH7r&k'
    's{*5m)v$+HT?e(8UBla@UvNugS65PT>!4eNHlGJOrThurCMRJCZ(^fWa|fx7R6Fv8!iXhJ3oNX$dKe2*mdw+tq-OyN5DZj-Bfop~'
    ')<D%buGHVsuK(VkNxAvj=Sr(DF8JS?wEhlh!;zw%P-riDkhXvD536mWzP!=X^r3uUwvR5++@8YjBMtOHiF*7uc1j%_-T7xGC*S)s'
    'Zl@p({N}2vTS{%sx}__qV3gq5CnqER14rS;<JOD$NXb+tDMU?49vv$SY5|)NA)-TFI1lR$iI+e@%L3KQ6R8^}w6B(7s0E01yAh4w'
    '^C2<)rh-dCj|K8G)h1?dZF|T7WXLpT9Qj2Q7Z?Y}qM%0^WN5Octy2XDeAzpWoG_bZ7uY_rrcVIi3XZED+n)OO)mq=QOSAKxoLpTk'
    'aTDS`Wu5L!(BUUv)4wH7K1#-Z1q4v>2rP^7&pjqX`XjKQuvNIxdz}}L8QdN8rvG}e9Xei>8k*kr6E$Lst3K0)qHaMyh*uk29b9RE'
    '0MO-H07S^tC$cskj|}8H+}=gEMHn<N>VZDt)l<pG!Wb=^PsmqIpw@>Z*2#*x8A`(XJymeKqCqjjTkfdU=OiYGcvvwYqxNIHG`h<T'
    'IC>}0T;7L!oM%=`bC-6~xz-vN+4lk?SfLl?cT!ZuN_-qOlkFuQqKjU~_623qx1w{ywy}(+^Yp0UAc60}53ygxySN&jGbb3c&A|$1'
    '4aGjFp?UKP0cqQu;$<^fJ^7+SYSTp0;C2sLGG$n8bnWul-#8-yMWv}w!Xamw!Vn&A)jL*}eeMB8wI#gIe#`BXiD@ZLZ;kn?w|=s+'
    'YVA=`gnW3U*H1-+0NVoGn=~G$#I)SmLt&{0>)wPw%dY~z&kQk98}o&M%TeD^fNG6x5?i0q+15rQreNw#>`i1+LoL6Y+J9+cs1<et'
    'y~<LzHs0KarLg-Lj@>kK{06S`*F#-ZZ*q56NE9^i-p+%_=2q6FdEgs9YcNXOd-WItHE0}|4mLRzgX0QyJ1@$F)R=nF?gAKr=4=*|'
    'FR+BrbO^gP!hK<&&wyd#Cem|5Bw}4*Se!Evmv%Oq43qSQlD;l{^$Rn7Ls3+ujG3=KFhB2pK|nndlU6O5)a;z*nf#+?Jc|))ivsnE'
    'Q==xe89L`ovs~&+N;7N=dxV?mUboc`Udt*=z-3X>2#gPv^(p6V0F>agElp3d3y2eKrnzWcDH*DSQ-umS@*wolwZ<tLKs$JK!O)CH'
    'EQlhZ-_(U5h!Arr_L#{I7II`$CFki&y*aQkn8Ua!SjDSEn!P$}{_-Q4t*f_=+1s1I3>B|amIzxCowrQhq8;Bvq`V1-kLA3cr|1<Z'
    '9JmV%dX!3$G)ewVwxXDAjoXPYG8zd=@ROE$=?+BXGTA&DO0|pXjH!_jz(QKUa)zsbO0{R|ZpTr>@>G23l{O9Mo3>P9hA=nIGpb7@'
    '!maG&osw-*3^!(l=iq4|Mj=sIf?s)_F|R2GUIgLLFrmVPdShb*i}Udbr4|RjI#3se%%93)wcz>-#d;6zZ+-pc*m0wvnd=mNaFsC}'
    'k*XXqSYcEm>V$Ey+O{_bwO5kP@ZrN^A{M7EdW0!W|8C`AiK&URQKBtMX8zZv)<Ca}>J*0$c`Ym~14ZXml9TJUa^+OU&<Q+B-t5qa'
    '%ns&;bLEOxgxz9$_ODNRkkE{*CjQg+)1d+}UIi!(Yp3>*H!lJKaBu3f1SV`xS%G%y14e^Nxlg96(qRhjY*;I>%n0hhc41Ebs?`IU'
    'U>g`o8MeG@Fl?;wS*m_$`Bua|V=$5%%bl=qh(nl03Fet3lQu}pC@J+;=9>DT1^4moum&N2%kQ9amDD+fW{!scKzhi+X9j$f89`ec'
    'kyFX?AS`-YoDC)+3tZ}?GoAm7F%R$x%I}<_YZNnjXpa%O5Z8l-xS6oi?+3cQRV9sE<D>uMlAp$0)aE;(4(2k#DQjd6Cn_6mQrs<i'
    'szxsA6JmC}(XYNct7_`~CeFsdYY_DQlb`HL3Qj#0h3H5)dH-*;r@AP3JsLE;6i2d|n(m@&)PEzGqdz+#8Pj@${I_huBP9DPAC~x>'
    'XFsQ`LMufBmNW1JmUY(kWQS6qf&En%++fJE5@3)+w=&Ik6<n0$WHdzvmrDsrNE+I1et&e0s3lM4G^NAIzmJ~?@wh^n#M10aw~feE'
    'BsF$^kKEY!viRe1V?)YZMpQ4q9b<I?#rk?}>fbidlo^IdWab-N|1;ZjdYNFs@(Bk2mZgMJm=DJTG<-CLDo5x#{9%0j&c$0*;`0c2'
    'eXt{nnt}c{U_}5T4u&1BlpnsXW9J+zlu^^jVVn5iDL-%ykFDWiLo=1jGk4*iqk!jT6NX*C)vCfX<!$y^r+l5@CNa~Yhng~PDCg{g'
    'zk`iB5Hn<a{3D%<&N)j-M77YH{=JQ@pIjN$vl)&J<qN?FuxD22Yj8}*Y5(aMkY(k%`ig6E^%(!Cj(}OzK$s5O9!d!&jX4qe0B%31'
    '=+VR67l9vynmG_6sd9(+8T*sN?C%{*WdfIPmreV@lf$Qa?|Ag(WvYs~%y=>=e7oQH0)4geb&uX<uf%NG7tJM^Tf{-+jWDwElLzO5'
    'rh@9DD6NWFW$Rvw!vgem??G6U!RWPnKr2`*skS=?W1ElHujO=Zm9duYsO<xT-<J<@it(Bk%**ChyOsh>l~^TQECz3k%gd00z_O<Y'
    'b$nasu64JG49`=TYDAVnVlQLViDtm(P+=`A3h?o~m=@%`|CKQpK5FnRD#?(1Ua{gidco}9?}z5N=@pO=kbQWK^5<$0L_E5rJ&YjA'
    '!vE(0rCL*Ktwqx`s2<BuiXmkX4*(3prPR`w8&HaOCP-{p`NL9w_uaD*nNzQ<7!7bEi@-D<E<dzz7a#96j1FA+ULPYNM80t-R(ba-'
    '#e5Pq)krvg*s|33uw1dUO4SV%6FRZ!f*ryT*DMFq8AvJzEyrEzQeE975=W708s<eWoJbz5HqcZtB+OvT{&(HmCy4>)3T>*p8^DzB'
    'buIk;4Vzl1B<mg_9Vut5@9`rQdoDfx{<DpW{oILNvwFwpZeKwA-t)D%25LYk)je>U8j>$HmP>~w;`)3%xfgwScC_M>a+WtFf(PO#'
    'VJB!~T4-Jf6l~OncLq+X@z(7yy_wVi1N&%n-GRRJOfLCeVI4_Af1+X^?Va0Hndxq)b+4U+u9US3KVo(8AhB$(c6me`?_$w1gI&NL'
    'yP1qn<w~YY4NWC35Yi1;RnpTOalv}+hVQ-iHvkye_w&u<$f!I_yv1dMyamW_;nl~Dn!!mj{gFnp8#z_p#n!ud^9lu3h|*F_M>}^V'
    'F@XgUX5%UH#+rM$fufz{`(xkCE@ySBl73CrtuUXwsWL5C1{1WEX101I5OA6qH0IE3JK`eppH&+LHK;aEhx7smk0X7t@vlb=`;V(T'
    '(J}Z~ngTP^r|LrSF#tU=tgRY_nB4oo<|x9@oxs==5DPKNz|S_2H*L92m-K&qnG=RFnJEg}QF+1a@?7pc{vE=9xwxne{?0fc_0sW7'
    ';my^6-rnW-oO5Y(QY-kdH3mDipDK~|bso5bJLniskNLYjP2W9|$)Q*JrB-Dr_x~TzTMRKc4@e7*kjgzhuQr<VQXUG@hR!{Mn(jf7'
    '<n<9U0?-6Nrm)oqQDw(@(%fdfenF?9+$Y9_pp&*QR@H{4V#(l<nQ7XxN2=(u_i+7iGEUG#r$4=7!l#6n5%a2zqtHU`!U7W$c<^m$'
    'U~U^<M!#dOY3H%r4U8hm(grT)H)B{54TBvjlnEi4RSpMHqOLgkmCbVW6?424P~S99K4+Sj#Joy%V2%QmH(|mK{;<wx^lBdMo}6Ql'
    '9wzN6l4nfDKnpBws7FUN{2^ibw<rsJB80y=B0USi%A?=I9~F<K`|mbTb0H|NaLF-+3ncUyF$YiNC_u$#V*MUu(UE}54z{MLPPR~>'
    'Cm5{(8rdhZN6hIb(Mr{c!u%-)4n=wrYaaIl3l6=#0o^5l%t7ds)S~9ENNoM`iX+@iw$i&Sd4K9Jm0-zq90Gf|!ywZL>BzK~<*s(>'
    'fl*2PGmbB*$C&+ncoWF4ZUlrJbgj>clOeym$S)(*ne}-j<s4n3Y1N7nRss)FS5bK5O^8x$teTwMnO$7iJ@TLDz-}6nX5k(pH!VCE'
    'tItdWI*_}(NV^$}@GVAI_}nU+HAH{@mb7-$=!PSM8m$;L^V?pm!f!X(DV(L1U?r?uT5GWQp7rzKoWhMx(!i}wtD;=c^?hT2{VZ_a'
    'lOp(jnE7X&Ovk_whV?U%$v_Y3CmMAqWP^^&wK3jgRwVZ2u2-aU+bqc67cn-?SGHQ%-(y!me2{Zj1%*8Owd$d8(xl={e5hxMRc1i='
    'BUaOUZgMd7#DW0F!KY1!L18t09yew}M$*xs4wRsihwZAqsp@15;R?MJLReZ_#|8FDS)^*)oGJSw81LpK%P;g28#6r{(iCT7)lghp'
    'acF=2ymTq5u});r&*uyt*7;^tyM!Jg@^u`?_qssob7of;Vi1j}*Q7=`qJCpOmWFZV&elrUYN~KD$(}BUyWjqd&I~nZ1@D)>UmN6a'
    'rR%g!2Wiu&K8*#-@TFtL+k}v$f})K!mi+-#1oS7`VKPsQuhxS%12rC!l-$sSWkWq#K@F@NLL&aAwM#y`t5LBU@FQ`tIs&5zAoZi<'
    'Jycd^03bF)a5A!a`~?YE@Lz)7wsj+JOGuA#>|J+6L3H6N0O4@pMUG~Fl|tnH?^+<%V&Q00!0B$S9>ded9c-iE-wXIzI*#~OZy1C~'
    'jBjHjC>be_MA)<D1s@TH!LkvT6oYZGIdZ#!!n5dwz|ftNv^N2*Mr~*mkJ(&X1OH@%cb!>A4^*>S6N|Mg%4(eXc#3*f<&>Qn{2=m<'
    'xiG-fa~MZp556^Uyj+m>M1Iots+g3#U1Fh^x!WPZ0}E)kv_-KNMM=4ZBLQ1%K53JCJgF*XK9@9_)fmLndzkt7p^$kTr@sL+4XjD<'
    'TgVg~So-e_jaJgZ^}_sd&YQ^z3iBAi%AtV9s4-VM2`UP_m^?nGHKQ}VF}_Eyu$_swiwQ4a&YnoL1cY^nr<!8jAHlQwxUiy}IQLHh'
    'ZFree@Yc}GU~qsXcy$$v93Bw>G@!06zTuvQ5GtXZ$35n60Zq!ZJ=%m~+%N@uMQ%;RV!r(qFL+kt7vnadMA-u#Pwqx@^=5Sq{h6*I'
    'K669J0kZpvQfG@mPE=YS-%@mlL&__X*y&lk2Fsw?b{A9w-kSf+2MMv0yOU-H+c%vDQ(O~$46j&rpMNx$(7199OdAcK4_q<k002vl'
    '*rc|u?<JuCc2P6He3;vRap3o7efNKY75$P@0|VoU9ezWo3c1b)9{(we@P!Tdir{EA0Zyzx={+Id6IVcSKzgq$LyP!o(G>3Kdb1Ji'
    'O07ex-at)iq#_4oVL$6+5FNvTQ?{TDW{}yFfSD}D`1H|o_j6?(F0n6cE6krXh3uRqs~gw**k+WTZ=UHI@m+edH)0XF{|2WK>U(W3'
    'HYdMo?i;o=z1A$M<K`FJ<l^4k+7qcVJdlw%55dT1{AtNh`D(E+3$b~HGaOTBWGMJ%jpx9MJ!d(I6T(KL{;rW|xJF#o^T`Ey+$sv?'
    'Fclhstd$;rl=!T~Gp!DHOQXGSZieK^qynH83X5~6Ym)EaSk1WZH%c2^=oFbLJi-tJY#8J&be^K+C&I(7?)$)m$L|ff=^ix?@L+F$'
    'QWrcpyr77$(oRs_C{%Jr%cb+)KGrOJQq9>AI|e}<BIcJ6%+kU+N!qozcU6=TbZEu}j~G5WjIQNMGYGgS7l%QIxX72Tx2+BHulX;g'
    'UG2=kA>1_Qf!}Iu_-gS@TBIR?sTLtTo=>8t%WY)|+@+4@p3H>DA)wH>8uWlme|vm#y050?#z%1vVH6xXRl*{|A+a^pvH2mSny==8'
    ';{8@z;kn}o={`}7wPfyAWOP$u3z~fq5!VCd_JDE=3V9yzh6s}TG{ztdUK*Z$eBC*x97ufac2!s@SNQSHVnG27D91a&!c7Z_MUwA;'
    'Pjs5DGLO4>-GTIB$LD#c9*J?T_ne7Uu&HD8Pq`syO^5v4m?N_wgMy&t;Y7k>7<OxR@DXf1E7m`fSO?#mWQ96W%oD6WA05>Fy5fG1'
    '^a&cOQgUK)_js@~0bJ4leS>CM_q-df&nvmIy)qgy)jga8H6dq3!DuDu^;W%_u$LPhv0x%teww&jXv9!Xhx~<N-T*f_Jt)Bn23lJA'
    'p}cR774eYekDA|OjfA1B{KBYX6u~Unlf6sg=yu*aNuFYhe<%B<+tJ3ht?BX6bg^=V@{4&#%IgOl)GKM<UP3j7_ONtQ1nJ&l`~P4m'
    'x44lmO1}Hvkk=66tt4c4Jy?KQde`~WlwirI-&q^21#%sakVQpj(81=?m{;`_0s-j8T81HaZV4+#oH!dd!6-dlDt6TA&EZO2^Vcv5'
    'ki5$BC^f=9C1vd0o$_VHmAJs|)oP5T*qF_a;|D7!R2lcn`1Sq&3fSA&VxU>dG<!|A2x8!2gS?Dya=>g~B^!06u&RFHDtSskRd=rH'
    '6exw)cLv(!a&hmbbD67sQ;&R0?hX(l2%ZUvi$sLZaN2w9Os|<5i<!DXHLdAS7A+9W${P=0V3`2AHmzRhI&NH-j}-85Um-aGDs+%T'
    'kxtsCv5B}Ba^*>o_eJb*AUffoF79^^`qDynhiJTv<9JdOg}BP2w^|mL&hPG_{>UhDaq1EQEV2OP8~uQ$v_h(whCZz_h!H+ws>;PG'
    '!@de=q-w_$t2Z<>%BuoL=u2`kZ5|B-h{_JNbu5V@f5jDe0Q%aAQ1o}X2qe6Ttz#lB)TYF*bX2d;$v$PE%k%;V+FL(8QROi5<XNbo'
    'ZSC}jGT%L_7Q3PYup$+~T9&T<99GO48It@YZN*1Hpc>SWKurNU#y&uEXrzzay~3gjbTiZMZc1=U<os0T@#cZk&LCWwgQ^3dFb3))'
    '^m1#ZYGZJxAtQV!PePcLmmpC7+(SNbG-2l5nc$x>-Nn#O`2;~mL~j2lYq(KlctABS%X*#??AAKZeKHfL5FNhz^v2o|wW`YDpAz55'
    'w$t1Z@VC2RoXxR|IVxSLBjMA=`b2pXXB&cEynbkaZ`a+tR4^ivQlCD)2V3Vy55=dk#ZsA>T}={QG^jJ%#SRMK<fR0R2mZ)eXK~8T'
    'C^2vph)%Xz7ux{0CM?0>ZZ6-KET__Mj|h=liLe&OWg6T;I#tz3$TsR<B9liT<Y*{i&_uKwWNd$5VF@7%=gv0A?f?#CM~zFVa~2Uy'
    '<t~#YcOY7ek0+bf#bR3ZZQjvC)M)*I!>7=^iyxzZc+}}x6L^2GFq&H>%xnmRZ~qK)PEj{L**6zBcsbGanWpiACA-`K7aU`qY|QuV'
    '&pT!45Jd*TC_A~sBLy^`&gnIg_+QDs?H&~OFeU~VV4Xyodb?elq*zHosqs3ZA-Gs77H{^3gf(;Bx&U~C4%z_N0s?J-H8FZ=GI@G6'
    's4N6>xh9x2?nCsNNYM(PHG%t*ajhagjk{<+1*2#U^!jQ~Ue@;>FgAk>-bW)aQE`4a9fO9$V0I^^_)-4X$|8IBEYk@icvZriJ0P_d'
    'B<*c;n0DlG=o*6Qo-#Fog~PSN^(fM!j0}781+)iD;hMUAtA;gE1N1WZY8V9i4CN%{$9=dfFq&qL2jjv2b>HH94MFIjXuk^IOWCfE'
    '=ww@Qmblmej^=2l2P@=q0cAgj`Y4s={st9)YGhY@7i_o$>YiVZ$=%gs?@REn)9t+}aO#XzEP<<>OJtmEG!5+{AvIg?=2E8C+SE7a'
    '-#>gg9ZZrLhC`H_J>U8OoU>1CSlIfSH3!(7IifpL>=d?&b}!gb#?Ry0D7j+J`D8n)F4v9r%RQ5RE)%jgCOnb!13*#xm~R0JCmV>#'
    'YUa#NJAy*bnkQMKx!aV6z@^KnTZ0q@k>A5E^)m7nu>A#R%)0p^^8go=65?Hwr?ctV@UAIiX@N%PdHbk#Tj`3AL9@<lMN7PV<WtR3'
    'J!=mg_(H;x;u1*+-bNNCz5Uf*^D4i~@rNd({@e@`Y0zE6EiS9W$&v|aX_#DRSrC5xS??`1S^PZClBH73NET%2_;PR)3=6=?qIyc<'
    '%LMLK*1gqPdA})>@}6QTZh1H%K|#pV<UZ>xikUj@v|yt&lS)ckyc4-p%`7{wu*6qjNSlgVV=)0QZPwn@W-@#P=p(=@eTEV+6ySxL'
    ';Z55vt8ot#@LW}qKd1zLj)kv-iyk=-*HkM!n@Gh4ene77=vgVKjY#<_g<e{b9*1HL&otM+;Nv&MRMhTsWHDy7J&+HeXAkC&mEF{4'
    'LKU;T3P6J#jX1-q^cO$8DTa{6d%RHmPjg%ynk*TUn^CYc_gls#DdiesZ+22F8O2dk?L>+7>OF<4XqqJW@l^*&Bs@^~#|7!ZYWjjF'
    'E1S6dtyq%EG{V0_IYT9m!dwaRe2O+>+(-_w<|{w5pV+NB<916^jZU{UqVJs`)q)F)q}po!4h^?))2mXs-{ATrS$ayy$>5_>5t|5x'
    '6e~%jY_9p93GLG8ahQ}fjj1!Y`4W5%aPiPobz115w{Ph9WbZO5WDlB|A}_HVdIkaSJeNvMMt5}~ZJoE(J%*y#H<H{iU|i`$C<yYL'
    ';0Y4Ab=k8aKKP(Nst#C7Sf^JGuK<mr<Abubp7DNV6O0=}BJ4qD`^E<Jqp=Jdn*&pEztGp2`wqledj5_l-cBOl3NJ;&46~A;K<4KN'
    '>t_#XE1G)6MA7;UH|aViEHSddDDtD+&ZH`>MTF}`3Y1Nn-AK3IzSL|wKIwUAm)AN4gqfpBA2=X7RtIg37znQUvJSH6*Rj3-#?1qR'
    '7MwFMtbQh~h3L*=cIUNlUnfajY^sjvA+l6!W0dC*oktN(p%OqMY~i5*FGvtHxo<K{2CdZAM=UVS&Qx0diGH;7$VaLVZeqtlKzv&G'
    'F+!KcCBo^9_qk8tX$wUx>OGM6oPUmLlI0;e)e4Nz={b`lzjb-_GnT>b&-CYn%(^89>E;r4bNo6x+c=G$o-JU-eYD6bo{mU~P53V~'
    'Zd4EDKWwCx=uV`dvOGYx27p2GHZQx(H!4I<uc7=RPr5uflcIY!8EN2%8dKn}Jtt?ivfI~g)Mo;EHr?-8A-2N5lyP?!`TS^dFx$<T'
    '!J;UMh616JXAJAFWHef!fUR|O*wdqu5ueoPPbo4|=ywD7G$k@0!2u}4K<!#$;vM$OCl*F-Qt<G#Xcs<mBW1pi!$rf&;PoI$sR(xH'
    'POB3N*6w_9#%MlTyK{(GlW(4F*aN3kPRUAWSuk$sNo%rhD=={0bfv($HXdGro`ZXlHuBHYhv&>~$lN>$ZxlIM2Z=CXV8W+Q-7RfX'
    '$t2y0d?!)LmIT+C#uLa9-g$C}s+rkMUK9!SXSQZ8LQ5&bRQ=RWMzo-qX@)gxFUksii8v$>C`6X77N@V<f@Hn>d#Eif%}~0pnQ}AS'
    '<8arMNR_4i8LE$!8NVsPRykF8;BvWmM@zSyX{;E&NtGCoq7wI?f2hb2>2|(K5o80*SdZoZ<jwG+VQZ<}G)tdl9k5^E?&o*EZe-Cp'
    '(H>w#p_Xb0eP4MWxI;&rH8BC>Aq%10KKHFMBu{#*xS`o&=Ixu*c69K2manElI5+yLaXgA0@tLNS)2dhAq4jQ<#^}NX_u2n1q}%H)'
    'ux*JyMRwdW5R!bv1?G}GXl2~pzK)juV`thdUUwcuf?RxAMm}_FZNg$xQ4J>}1rUd4d1hkY<O55o9sI8hA2Zl!towip+-y;7Wqnv8'
    'T&?FiqbEtk1Ujq0<^a<?FvY}=(upO}@)4i&qqOWd*xfnqpH-wK@jWGnctieD3W4@QA8dhYh3^}@_(dQ6(It_V5lJ>`>vWK)6P6g~'
    '>odgR^w?^JG}Wi>N2A)z*kU*rO)OdT2LufStDL-{=lwg@nY@8y3Y*j0oi8@PV5eg0W>eOIMz@lf=otSdYbbcDcez2p_qzVbmgui_'
    '%4b#E`lm{b(sJ_I)u=8uW`SraQak<U_GQxb+Udmg>S!J<!$Q<Df1W+HvIlOr`H3KZTru4s5nu_v7gqH{-Jz*C{EqN~gV=I=EQ1RN'
    '8rqOq$Jd*rS~H>$o(hSFcWuB4yYb#%ps^>s6Zl#BT{=r1{k*z`t`wb~+0l@Uvb=IG@(J~)IHzT$CAUN5DiM|pv{H&Fe$XME9TYPk'
    'E0QnYhyg$K=;4S*!%jL(NHQ9I4^j?9QiIla(WGUOL2s<y_D>E6`XX95vLF1tz$B7cHTd_duK-3;ig1dmr?l%03`mHic(b9AC8jIf'
    'dusWl46$5IeWa%n*A>bc5lQDT`~3pzZAgQE=O1se7uP*X?iQr39`^b}QcgXUiXJvTD_5!XJR|Fm|C;)D6SYrADwp(?!J)z=5Zd^H'
    'zzsL5R<i5P&=76#S?f&w*-U02Wco%x>bWb$Qg6PA`+n!?%t+jKPrDn_PLz8ZyR*r4hl9fJO4XpqXOiw1;iEPN?N}wYx?Ve7fmUnk'
    'HuxA;=&a$+6tU}L)|zd`4Y{3M)E2pQ2v?5Lj`bMoRBN}B|D<lHeSzAdj94G9&VG>%$QD&o-_(EUeClxX@w(+)mawC&s_z<5$GVR{'
    '9LGNFFh+DF>UgW-Fn<h!{31*KkkF?pS2AbqLd(XA!V8cuz()gO{!b`7C!}>url=`x;u5Ty9hiB*^@y5t`JS?mSq@TDa~O;qyh^C`'
    'kcxj-iJHzro{bBN+jm0nTAl#u({NBOar(6M8oOh1gKJxJGzxA8h-yIv8S^2~nchX;2g_&K>c&BusTI7OfhRg+A;X?*iQ8U`>uM%i'
    '+jO4h>thN#N02g$)n!c=j*|(~`Jm^?&C;eK$7RVyakBK+Abx15P($*9O(Tu+hB8P7ak`7K!2uz<k`d#{r0v?;TYr6x;X_@)b8LrF'
    ')2aFBPpDtrQS`<@l;EjlsbqoACiqR=C@8whmrqqs!KKx_*Nj{VD7QvT?37(Z-0DUv!5P>m91FMb@<$cb&Gd-M6z3RYr}G2Umg`I<'
    'GmnGT%ZSiKRd=lmzv){P>s=3poVlu_AxU%f7kn($J-PoC6Vw=9;QQRm@&*`MbUk(`$~bN3oWzWvLkTrroJ(|9K~YLq`71`~@JqA6'
    '1NqR)HMurdt(Dps`xQ+-Ob1xfBA#PWWR#dSW(rs`Eb*pIv0@eph^OlR=AXd4jBgrF%x1aP%PB5hOgSAGQwv!ICQ(vkKS7FQHz6K&'
    '#k6)wkx?3Z-A~IRmnn5GViS-ilX~~prxfXq!<8ijGy&jF{+~NiqS0AuldE5S7|w{WPJdk%W;T*7=l-{i2{?dIv9_XFb%u_P#~~z}'
    '2qn>=Mkd52M$a$FP3)2*q^2kY*L?RvxeY&r&&Xw7^7}f$Vv=?KoIo53V)VpHWC93j>UuyyUQVzd8Qq7B#uXexLO@*1{f9o7&6xWG'
    'SZ&2^ECp)GjQI*-FRS%7M+>f8m<u5p5e;p5D>-7$gpL8K@eURj_5|FW2mk5+mOUir2(1hFWbW+$!c)5`*__LN^pv;lk>|;m{-RO4'
    'g(d+2ZO?M6Nyq-Jp-dQQ24CbKEb?}udPf?pR(<mp&qGtwglZceB-QOX+Of_iS{EXL#TP>P1xn47F6}Njzr!ndz?9xuEgi4{$FmDR'
    'G{V%59izC1kF>U6&}HPdjIBE{sH6n|R--HGzA&KUhU~A^hXpg?1t`78%q&qo{D3K^sk?cG+qMNL8hqS>?5-P(>FRTtG~zk}G3OLP'
    '{YbcTb|grc0S1e`w}m~tP4*1*KvvD)s%GlFpk_Kl%MWz=sAG(ZOJ_MPLOLgN7+Ax=J2Rq+2f$=b{z+<kkV)53@ZA&NndGW2qKmdJ'
    'S$Cm;VY~NHbY4FQz<8%2DM4g9ZzwG@=SJ)2s_#V?vv&-=PHSm(8Hu*KsQqcFEw5qSM-8lM0%(v6vRbac>*m|SMV7^8XJ>YN2bU%('
    'Z^WQUAUsGE6TfIW&Eo~oLP%S8Z*m`ts?)|PF6?jD^ohyCe-XdpsmSWB<bqW6Hj+I$g30Db&<H5P)ZJ|c%*3&NL1v7%MvxpTS~h#F'
    'lKVIaDI{iAM;+}L?Aj1$hBv{K(xZwUY}=Y@>58PayM|-}4&8fsJT;siTBv;RH!otwz5{Vs%CA62e;a=fE~1dt3m_V#$J$*&m@%L3'
    '_}C=81bCehH8hu3QDj$S=>)jQC{er?f=SxU=}ML(x=yPz*4_~^j1Oic@PXhGuJr?UW)2fe+~?+z0K^-VzYZbE%^?daC-d{_$?8N_'
    'vqGknH61UXEYjeR-|i%f^IL2Tm%B=e0fS?#y0{r$FxApN>KN*uiBZnLE%XIRin)@eDaR=(8HPI31y;y^W;7J$F&)>OOrz_0wx<gF'
    '8XUzJgmH@6x@=&T;>tsV#>3TRg!J*E;O+%1JNpv+HdMh`6mY%oo;U4FKQ0yRJGZaY63{H!34Yr(-@9niS)IdZAUTR_NG7W?h)I3&'
    'J5bdU*b_(gO%WJ1KPqYnmz9;gj_Agjjgm@?Sh$oo{v1~XW+54SDY?V63j2`2M4&a!C+s8cJ`d#MrE*L7c5(YXXVzbe1b^k6>jyNC'
    'HqktEK->Vc0_VZ|f$MR7)Kue`Z8)prgur<Y%xcIAEh)9OX9H<fE;KBe*`#qaZ`{h+(u2PuLCYs~=}5o-#A+)t#_~KXnue(5h3ElW'
    'k$vE1E27hJ;HTzmZq46=PeB2C9X63IRuOs{16|Z<_2CA)dDTye^k%qq%>9<Z_^<Fr-Qc+!lWv74gY*Qw4U|wZ)ZYT0$LBJyc#GW<'
    '`HccbaENJINeYG%+_m91-1+D;BjOUkXcq{0AVi8q`6u6#Yo0Y=se$+uuZW{;<K+lDi`X<4w4l!Qz$WfWZRzI61oEnjxkhW2k2}#{'
    '+N`m?4SruiB-Ab{1wwk^;Byk^rCjxX8%PJN_<hW}i;i*x4As;#g;%%Jh9D@_Y-xr3DAF)7XK6VVRLxz=U#HkRQB6X1-$mm_|BsnU'
    'PX7bE{+eBk`p#;2*3E-MH0vIiTHQ~nVj)aUlb6b5x_2g4;ZFR%0Mzp#6iJGsWO{Uu>6*jOL+W+~mP`ThS?k6#>|8QH!mix4u*H66'
    'B4f#_Ja6qdl}>i-PPB$ip$&cvq{(S~P1zEJZ+Mp$PDkp5O>*+>!Ox$-y<hFCpb%wr`2%82`x?KALSpk_6Uh}TG!t6IaoZb_Sx}7#'
    '+zuoOUhB_*OiqW0eQMg~`HcUUWTR5ekpXR1`cn}(W5E+Ltpp=4WJlafIxjM$Xiz9ywz!f=cYyX^6)Q74<udAXHARiF;@@m!k;i0$'
    'gj#iL)DnjX%Nzb+?q0J|`w`Y}YL9^tb5=)fHEa%7J(qiIVOi=Mv{o(Ivg{qOZ%W1a=Uy`4ZJXi>KkNZpL3HblCz?02Zb;5p?34L7'
    'pXINHOwA5JTEJ=F;97PUt2eX;!S8>8bple;)$OQ;^>+yo61nC??!3y&j7R$?<sC#LGm&?aRqNS(pKP3xr{$S{v-0a{N7O#lBn^%e'
    's>d!F&ciK!ny+5=Tin;~eVf-7P|-S&l2+3^mTzrxzk^jHa_(@=G@BfnJdUZF_%enchK#?qLdaWVxa6#CG88=<Siqq+a-f%tGK*|t'
    '-<AYx2q+GbvmMSD9vp?*tEid|`@@%oxEswySVdLQ^I|d~jXP8T6k%E%glO+dq1CXxVsus{XFMDJy`CkagaXvmJ}@h#XkpEIID;@!'
    'ccFZ1{N>9ly($psgO<h8Ih?HmvzT~0E*#bGQaOXuA&k#eCk^&!kGfn;9=sD}Ac4CoFh}NU?7=Snq5~`PNwpNVftVSyR9A1_vY$br'
    '+iDzw2tn`3`iCMFKb#@?C&deTi}S6hud+dLlP1%-bV*Na5;#8BT}kO&`=`AzFvLBj46VHGB&@GA>TZ<-Cc{y4_hYPE)KW#s9~VoF'
    '4TA~6Rp@niVCP{GU5%)}!(2(lP_tBt@}buLwKetaVy1Zzx9raT5bg-rSpbE4z`lb`R?nT*bvvJS9J$P<z@D`y(=d*`*x<||T~Ct&'
    '`AmPpcPpPFA|V;ZcsK16NUEg%Cj2zQrsQVHteQ-<5y-*v>mSD)egN?L>XaiUY<nrJwJcW2q;kbQpxpjRPXxIB**u-U?C=7w?(@iA'
    't{IOE|5}iMNh7xi!b39m7T$8P*Nf`26fc38P{9*}$CB*@1}vtbtuf{PrIK-&`;6Mo@(<tE)V*f@lI<)%ti%_yO!<o}Co;Ku3GcRa'
    'A;VPcvd(B)_6s*xbR|d%0P@l=P#Aj*<0)|*_G1uDnGH*QSKPSX9EGYTpy7KO7(M6Vj(-<S-F7x=olvrq638e7n?FVvGA|u>QFAQ~'
    'X)&eEg-Wz<&P_}<O{i5@hm=vDms`R;HEc%1IWNi)&zr!zZfA>L_6Sk0MUYGZ0x~9%lJC4(vCW9-0JH9-mfRK3M(dt8i|3q=ZbS?7'
    'r_$KdD??39LW?*dTQ>gTn$ZSJ03cD=PolV$Ha<`!Ygq+e9r)TdThniC*Zvz!aN61v=Q5v&0OraO7^T-TGP}a1AStn$SY&fcfSC{&'
    'pQ<!ngg@BF1hTgssftTToX+H3f?l;~q<e*!Xf=5@)arHdYI*MusKq>NkT8QlCgVc5sbivxEh&hExNI@EsYOCCRGf%a>8|x}0#liR'
    'LTQ|#X!PD7i8^d9XE2%S;nsZ9ujqO!w5(`PFSs<h>E{i@yk$bu?pG1w&FvNNnt|}Zq{QF0V{5U6L>#E-zbiRV$w9^jK1k$;HIG8C'
    '%BU%ofy@*@YA%K(4DPS`MAyEe43Qw;Z!wa1n+wAVuhM{EL~Ky;{>ZX2p{S4`TK7x!3rpkT7ne``z0?>jOB68VuCj6W`v`As(Je?|'
    'Ja@F3Om*&RFN{RjKW98?yl<(|XSa~$+DH(=1rTO>+Rb#%o=wW8gUQ&GT(f#cdO0oF-`7%Fzd$P}|Hyq+NvF4y{JH2$F*(p<rzKKf'
    'Z_Rsc)%&I6KqO*Kt}T8SV-At~n&jeObFVW*XzI7|2w-Skzwp1Yt!Ya<1r{FIEU0>21lGP+zx*N<S%^#}Jh>kezY0bnsKu|mO9M;1'
    'W^Kmn4L-2@r0TDw<hFz`JwXlsbb00hhJZSq&u3oZx9w$3T|A%<J$9zAl$L^7$TtQ$uUn8FkiI#me?ZHv`1RPRERuK76(tNF7@AQZ'
    '3R@t94_^H_CTi%dqc9GwFDr)IG)tzn=3Mrq(G%h!{1dbGxO-oQt5rcW=@hYp>^OmGsrZrxF?RFpuK;|lWm{;%xT7_Rc&b&&%!I2S'
    'zJLoNxf&`}N|9B)jPk7kaI?qLd#XXUB``R&G)R#QNr(TVMlsg({B0M74Lb+$+<TZMN+y{kMy%>OslA}gLCz^3&4Uk64hJyo6^y}G'
    '26edpM4Q3hR9d8So~zY-T%kD8L@hDm2_Bv^x0gI3LE;@!{nlLIMy=*FjBI{Tbq}qaT85YU<Hxz^8a1Qv2a~&d2y|c1<C}tHf)Gaf'
    'Y7CzYk@B$XCQ9eyh-JT1L3w}@jlf<C&fg7ADZBy4Uu(G{dsLCubGufZlnN5_M~y=Rv#CH2Zf;Rg$nT&jZI#vCa#&GK$%yzga$ZR|'
    'NQe{rM1Ec}JK>rw6u`UkG>ExX)IFvP`JN1ZT%IHhKt)wdEL3bG7VM<3Na{0pg(DOW@e4(`$*d^uvKKM`%ZAcjLr6o+BNw&Sd)x<w'
    'A+hEjB|iurU;r20kY8XpWLcfywK=3oBxCSYhTpNVz7WLXiNVG0Vhq1p#dA$5+cZz4N+S_$u{6lzln;I9)wV;O^~2M#Twi*wiTj_9'
    'n;7Lc6B$2&l8XS>X|CAUd9Z@GK8f}4-dGP8$L~#`f+pyu+OJEDiA5NkYB)}IQ~)Cca?GE*@R-4O#~}bd@sv9Q$$O!QQ(T#hOc5+D'
    'l+?J?5hq@?u@e6bSfZ5@Tz|NV&Zd9gyk;5``};>H5y8sCiL3aXOkzId^RyH$@_Q{6m)7MOy0ec=HgY=vUf=X8tYONTM1AbZKRsMV'
    'j<-zYue>1*ZeF2P<bFO58_Enn&58$Hdg9NgI~K4AiI*0xp)(w4Um$KfU$rV)Bb^)ixuFPOmiQeS{hx6M=HL9=@)=uBJt+@f4&9-*'
    'C`_HyB%As^7mEfEDH%EhvlyBNrjNbnqyKYtyj82XwZ-EeISjghmPvO+uwbdJY2e#x?S&3|kqb+JQn$Jlq8_bmF7~#=DNig7KC$wa'
    'c;MFKAQ!?DJmx@vzya~K+_rsl7K{8{Mw%ZIpg3W<3}$awJ4qZ6n+6^nm40Rqmkk~zj!|_ChBt%C*&TWnI=UFoCPPw5CE|eQ7s$U0'
    'y6`fS6VJq1hprC~SzFi7|K21xWegWdURFWdW0;e0h;t0ZbWVa}UgF(gp}70%mrb&B$D8M$c(jND8zWf8ddexh?5d#3<BlWwS|M7N'
    'l|-R`1Oe6Qqcd@V$r!Wn5ptqW<szy<xrtHWw?wT&Yzb&cz<j^U3Zba;HH(+uIQowSC{Fp=gv?gL*9x!FHVHc-C2nhuElHceb9HA`'
    'u=%fcEfuoZJRE2oI!>A}ce$qNK@--%Q-Qtdh$5=49ASI;jRCO*A9yjHu<nB7ht7s8wQ)a;>!xGV>&$zt0;MbCY&OUxnljzLwmJ&x'
    '5f&$)_Qq`EL>Y(LPT3(<$6NOe!B43#N=$zb#wf_X`f6mCuuD&ln^-PZ7_mTFVkRb6_E0-b%qWj~-uC-|h5bR-TD%lezJDjFES(&W'
    '4R1aVe)s29UZ1%Tr%%##i9BA0Y=J!|d!{fsuad!T&QK!OEM0yZLAe-buNmS+l$w>u`i2oX0Ne>qTYlENw3rNUI|%xmV}harPhCPb'
    '?-OE3N6ypK@+Lde=?ky2&Dj5mtpj$_8^$rbf?<|#cSM`Xqi-UPsDu44KdFL+ORM?1u#fWUFsQ`2Snci2<Ku?MYIR~LGfrA>HkZ!1'
    '+cDna+8m&|<NZsbrUMRS<S#yfg>0Gb<K)}#oe=dszOpx4cWy16izQR1p||OKdQgr>P-)$c4|0*l<Ve46BjoDGPnu+;y@@qvj99lR'
    'WPWa#{kXxt`NaBg5Cw(^@BLRW!~p}w>XCEyiy|P-v6OG+W;(9(gxpTy>Xx|J4N{<Ztow2O?r}Et(r5(BPPS-^Eh=v_03Kv@y4@-I'
    'EpEpQJEsB(b?ODh5fP9#iHSz^7f_##2ucDPV`Xes@#r7i=(l>S{-erHkhM7&<4TH~tkMd&gR?xkoc^~rwurjjvlqTp85@0VTo0;C'
    'S*OKHqsV!;u{Wn*LfYsdPI!iQEFCrN`&0ud=Zp{P{+`8Y)!Ih#i8)GZBXAqjV3pH^Q)9K86i9RSAsXuyZ{il5r3Y9n^^HWGhVO0F'
    'yw$M%pWk<;MH_o4LOx5sJdMWa=m}|D)lwI|f(kaU6B(=kx(L}N65MYQNA---eNZVl1w~y<cW%TN!m!U2*vu2xE-S310ST7qgASUe'
    'mrnT_O9N$I%T<`cN+ZlQRfhL>$+8=2sG$!9+xUdK_qh7c6_pThh`(Yz$V_NgAA^)VB$Xa5YIp;lG*W&zfz79=zzd*5lWdP<R*m9k'
    'XjD*VXS-6RLs2m~F5Gm`SieNPlW7gZMxH`XZay|S`}i8G8dSSc;ee(?$Bga$lr5bVM<crFw^-5^(|RZ<6Exr8Upl>nZ?<PUz)exg'
    'P%sH7_M^P5x0yez3=SCv2YyR?sL-r;%xB2kTMYab_jKP|dZ=D5l`P~J$|h33*>KwNCk*nZpw>zK#Z>?ptnhRU6GWfvASD#g9PyDv'
    '+rcH9*CEg~=<u>6cAuUmF3p$Vpb}6?xQ!dlhG&`|t2?HPeDS*PffVVqy($1=XN-=xtjZ>f>bQ>t4^!?nJzcVO0lw~a3t~<bz^G91'
    'TF%XT0qs3NywIxa;)iJnmMX9n9EHpGuXO4?+G;5Sn5ybC!|vu{<vj_20r(8BLmxGjH*Rwo#t#BlgJe!{T^Z>oL;Oayd{b|0XE|-W'
    '1;lOWMv-hn7_{m9%rv}<>dg_x+QAo6!44+4jR7)X45YwqXpCqAx>=#M9sz(Jqe%S)ffBi8n+5y`_VX%R$Iv}aH*iZ!vS24#qgQVF'
    '<X^6+F-Nj~qRW$cZ_+j{1C=7tm`^`fP56VNPZuTVDT~al+r%M7^GDeWU~O!s=Xl=V5MK8qSU|^MDfzMSK~cFYU>UA3vpaYP5r!6-'
    'UKkdYri<<2KaWtP4!orl%ZXXcNbNppr>MPsX)Y_KBZB(;vA{8|Air&rZD||I4N7S#j}2vSklaAIU#fcpCdzg+RJ7({tcqba$l{-}'
    '>o7qBYXC}2!hB~Sh_53Y_ST(WJ8GR*<~k?}U$^<dI@P+8>@2P2yhWKvC9L=ag*KWt=^dkteMAwFVpJy-?k0={D6+z+JDZr$BbepR'
    'DXs6Df}o{0mxnFXupctdE<4<OFQ|_S@a~r@Gp{FbsXoVpm8EcbjlJbG3m$#fWG1;WBjofVRq+`glWV>#=l&45H{zqxGa2^h?|ziF'
    'bY1@_cK-g6{)9MmFPJEC&N(c?H)*Y^G6U(8MvI{pA=(h}e#{??c!Lot?Y8~amk^KlEVD>1lOw|TMe6J=6|eWAWJQ4*5ye}Hc$<VU'
    'A40kRh@v##-QhyikGH{1SE3CVtZgC3XHq|Eb*U;oB0(>IzSR7If`Qf*l9e<s&1GF3npKXPbbf(={wdhMfZ^ci{`fxDnT`@cgW^)#'
    'cqp@8HALKNc($<G1<k^nB>aaT6{8^jC4^lsS(+ujL8@uI=;-Qfse^GOvJr(K0At3gXbQ!iL96ZR>1)usf;+QwhucnLwd8!#Y!fhm'
    '$qErR@r=Oq`RjU}P<di)pmKNu1WKE^;v^FPOFcTPYv%d5k+C28$$y@D84vPnjIL-@g?y*D-w&Nv{Gcl*6hr|5=vQNz6N4v~X%gmh'
    'skgDX47&rmLx^JLR=|giBS@&X7#^DSUV`Qk&gA~AFJMAISK893C790}t+cvRW$8cNp+%g=1PkJHxOIOQK`}<v--C}<=@0Wl;Yt)N'
    '!fEp}UfVg0hDs`(-as)kh@r0o<nXXHNujsKQ$v6E?-5-93ZEJf4Nsc6G(-D|$?e3`tlMnFYZpWB$0=i3yE*dWLZc|-|Ev;ZSZ^mz'
    'bsrycv4e$2frcDWItKbEL`s02{C*|m?dKs}77uxs!?1umsn5*pk0Z}61SGlCTUP%wKhq`5WkPp;&Ez0zD_md}s<Vom-QnMGCGw7s'
    'phYNhok(UWf7tAP6Xa^bw~NWTo6A+KBvUnYc*Aa^LTMLodAK<Qva65@vH#jy>#yAYxi;ddC*%l7NRAAf(TFPN8G*~9vDY6o1LVJi'
    '<bp(giu8w3N9Nv4i5vxI5=@*~b`pfh%Ey6B>Ywpy(##8UV-fb9b7{Ymp8(gkGBzp1&uG1K>2hBzx5*`izudETI5_^PM1~V|9+RtE'
    '2nA=F(BY(_WHZ%Z%Vx=Q!kM}iIk&wDGCq>tQ$24%-*><t6#Eku-7p)9Wz0ZAI$)h<rmK*SPnBHJ6^lwCSr1Dk=W;--VupV>8wNNe'
    '8=@7j<%(1bX0{Ez?=Ov0TYnCpv5pOhh+ar}tokE^x`v3c-9c@b{B;r0MG<$#UjD+wiBYBcrz_P5Rv8(G6y1Yp#F!!gaJ{lp@?&D1'
    'ZePlBvZKqaSJ8-&tFg9R-l{#Wfex9Dmzqk?p_vTa!?3lhC;lp^x;5iL_01!!$UoOXj-(YBzM9&;OoI6p)TQDDT!%NBBG(z(J@-3P'
    '3i2H7s|F|Y(WScb(@KrWp1Bv{r!D@lET#P(NDOKau!pS=12FE!B{Vkb>?v3Cr&bYH^T&bS%>Wz6cu12R2kP@x7;_3II`~Z+=VPh6'
    'PvB81GBAOkZ)XnTiuu}jmij%6u2`QV>hAXC-5vC%#cq{n=q|q{{(L$?C3e4JUZ*J2Bnm$WZ#F)ob;^0OE1toRv<OVL;HC#d&>Y%s'
    'QX#ev%wT%&V+7%?j*$-DUBRXJZk?>(0WU?x4)dU#n1Q#?RoiDekq`4ssU~2J+B}_f;s(IgnLy(i%nL(yWh^P<!k+&QmeHCsh?J#y'
    '^tLd`tjY8J7QqB0g8><iV=V7dI|Bc<dVLw&*z70>gC*Ey&W}ru&f77gjm`U+*am~7pFAlBxftkw{&`KDMLc)YgMXDjJ9k5SoLOs@'
    'mJQY!HEK<w!`q_2*TXh^-)5Zq?=FS#+Z<TUjZvT5WH%fLO!^fs<{R2<!djt3joSk87Ar1;68i+E*EmASny19xgfX5S0!Z(7_+LlE'
    'pL^xELCz9;U~C=UvyoZ1kf9!&F6A93{MX~X8Rz}six1-_kt(fNIQkRxg?#I3ts5yJrvImSAe6xO7GhJjTqw-hS=m<tkH2K$cGI0`'
    'n(%0hEHDL}m`Ec67MnvoBO=Bqi(EpSHNY6mXMF9a!YONMNw{BcF}?=K?PENuyh3CIdrsl%dDv8^%!`F0>@kghkc|aFiEsSguj&<L'
    'E{^-Mj?w-rLNwPvTTnPiePpaH$SrvLLc}Ml>g`#+FMx4Ft7b&Qk+EDfh3B|LTSNab?Q|TvW`4UU5%+x(hw~rLRAsa378hz{{uNw@'
    ')w@*>;ax`dHEau@F!$)J;EP9TYx%8ADCKS`MB(iw4=85u>vz%t4e~9Y0cw>dNXX-obBnfB^DKEM8!1;N*({3o(c~6{77}L$1bO_y'
    'fAcgoXDlW{O~@t1h!jS{Z)g|%?Gl@6Ox(|_a4S;c{02;;cP4YgYs|IQed4l_G#xYGv#-i1j1lX>l^epmpK`~oBV`Cnc^c1fh_l>L'
    'r+#5QSWSK}ua;;E7gKg;@ZV;yk0;UUUl6{@VX3t%{ca3%Q*f$$0v~1EV!YDY<R=j<9FT?bWKA*tY;@acaQTK14p`jEjwll=8dB>2'
    '$?qAhM1F?39aUsBgbb;{><2}OD%i;_uOIep+c|W{OQMH$)h(8J^(5`b3KN+(vFy?`r7LPQedhZ?|6>3-TIhm$RvZSI%7M#Gua#1S'
    '4#An&HsOoebyaC>i}LpTUSYAp2M#*a$5L1tZLRUjo@rRFpC$g_>#0EYTK|qQwXg!tAgcdzJ;s32WGQoI^s#&Mu1zkPGu{KQ04P%V'
    'nq#{|K8uRwNa_tY{mi{2<kVW}0+n~vSxXX?wJ2WSgcKr}_c}++dT;|T=6$=irMTZ7N6k*f;Z{k>8hB!x|Bf(|p>av>(<`=L5E3IQ'
    '66S8^(wP7s`|UiSX&;Lz=0M*GGLQzkg4UBdMIOKUSVp~0clhGN*l8Vll+ifW(IU~lzR><VyRi{hv}~3yb1mNnXdUNu0pPqMj;(*`'
    'TG?ZJ26`(ytNRBQ<fc;L6RGfGHMlMyBAFvKcTzU8%hedL^Kr~wyt<}%!b9eE-{xQ1rYsz9VRfhyHav6G(m=p-hcUw$;{mxY2tYu#'
    'IS1a|Kj)w)b3H(0<m$uXlt&ELZ|vdt=1>Z$xc)G?xYz*EOY+-rU!G{FqYb_Dq~=Fub-o3ag`|jh+&kuU>gLU-nFTybAqcs5y{^Ab'
    'J%yRsq5`Unn~cz+`Rpp|;O2(hOLQ3ACj<Wki%MYbz#b^tI0yVir-DWOY2QGUYKFB#U{(eJ!MCA<M6DKy#i{<KNW?0pz)&kCP)NJj'
    '$81n*8!?*7gJ&4HrgW)GPoghk>N6K2wOUvr_+Hlef+Yy)K{Z-vxei3Y$t-$Fq5v5Iw1H`!1=qZ29ci^Gn!eV{K?!m-yPc$iB{xoN'
    'kZY#Udv9Fpw%4XRAJl#xeQnE04*BX!@UNXCIJhd^;(?^~3UeU|rs>$O$vzGTTO=exCeJGN?F^?C1ltBJC5g+;70WeTvvN2Z@FLpW'
    '69w<E{zXQZk(2=xCc!&fuWWC>NmYr7sr-~^Oit!vWF-rj@8LFLK9B^{UxjBRsAFi+Y08y-5={24MU!kzem6T?qvl*xy=`VvL@_=?'
    '$rsQQb~32y-;f5;qmqv}64vIs2nFgDUeuF+h}V%L)1o+vAc>dBN5eQXMyVb7&1l)a0B8rDq5e6Dx)hN#hW0XVQ9I-7Lf)eSncESg'
    'WP5YS28TXtO%$LF_b)!~g*3M`<rHe}&LKf(rCr(c`M^$6=9Fn|S^3^0bQN^jK8TMUZ>(pKSj7#)RZ?OxF8uQx8UE-#=wt35C}ppl'
    'cnj!Pc5=@+!50%=_AHMnZF!fD46YY2E!j_u8Wy=-G&(Y9N`%SsY$qK%;b_N%&U8GNJY6c+L%@@y^&R|yPXuVy(3Rjf2xh3=(|=~2'
    'iv@%yxuY5{n>98iie7=0@U1T^w(CEz_oC0lKMN7OQaX)t(k|e1!9<#OsZ&VF48dx90B0^Tex^$cpOl_|P{iCybMQR4^eCeM!TKx8'
    'K<_yHv6GiYnf};1Z6S_I<QmL!gLY@IwU1Nexp&06dyWzc-R*yLr}#)CM2f<b-7&)UHVYTov#3gYFySyS`aba=u`In&mmL&zDhJ<)'
    'Xyd5Lfe<oDuUw4GQB;G;JTawwZ13XKUWC+PMMInnos^uZ18hL2$1Enae+WX3TLr{~Dgl;n&P5t1Xvgei=pl=#Y@dAUb_9Jwi9GIe'
    ';MkE1Q&ttewenmR%bW7t4_uP1Qh@tdk|?_(SQXQgQ&zC1x%4bejNO`|6pNJQ2cVNcFQ0@Dox&)~YwXs2rHQLE+Q#xBtEocaXj07*'
    'q+(wjz%Pi4Ni3&}=q~P!oopkTejTR^ZwLh)GU)J~!xVlYs?M*Vjs{;zxh6#&c4C!;`bO9@xw%|#--LNqwy;HxMpnIru$4H4kX+gg'
    'jEGQ#|BT4;bT^_K6^BDHk@p-`yBs=W(dT_qI2x9$!t5ASVo=ksUZl#iM6g#Mk`|^tiUgzN2+B%s=gUqx$*aVhb_Vj6A6VHkybZ4n'
    '#6#QJx?hoVoYi={$m~HwYc|mD4Hy;)_GF(^PZR3B9$>pNAbeFor$g|e9~q+)Qd?gRdV#VbnSFQxdla#yK9Gb>#yb9p7H2kw<&^_?'
    'PZlk>)}EFnJ1JZo+VerzgnDN5txm|zKWyXI<?73wJZPVmo8dxYbF-DsD}&x_<TxWtNzn+q%4-K|I{^+bW}0j*)Wxngd|Z!MBc_#3'
    '7}+F*u)Xe;Q|fic&y89kRG>s>8iN+M#n-L*T#!xzqeX$aE}KZED#`se@o5}HpxjUo&Wm3*5JxAr&&~|oy_NKM!f088eaM#Jx_~eV'
    ')=2X89<KDQEg6hQr1KhM&=U9X3~11%UY?2f;6f)9iQXqzL-aO3cok)OgO(u1t^U4swhP~`Veo2|K=l917mS7ez<*;;_K+tawT`uN'
    '%by}W=2z#m&C?VOr6cBi83)d+ihhZwv&e!~|4rB*TBmy0AoWrm0Z4DQz(b0)EzevHdmqnq2L;XnM2wla8Il~ouw1V?C`=*Ms(N1G'
    'FNE@EiR^=SOyQKH(@xiUGBZbz-fip~nSGQDU-~mCvB+7JZhm>XR1?!w(WbOT0ki$fZ`zD*F>Ma}LGhPh@GCh=-yhx*K<x4?WUoza'
    'sbg$_icI*akqfu-&n`$vvDpI0cY}Itt~)9r{xTL#1Sv@<?QU?4i9;<+LHQe!61_0Y?H-LF`(d(dXKIZexUd2xJlGQ~cnI-jZh4fE'
    'Wz+ve)bWN>GeAG01lmu;!_V|UY~9FZ<-wGXnKr{ZoGq{|*Lb)4N^>n3&8K8U?IkR-8Eg^;xu}bfKJ~kKJT_EKscT{B|6<J?gpo8I'
    'Nn?T#p{^l}(a5w86UMZn;10up$UXxZS^l6hnA(^f6OdfS(nZ07nzSxwR6wAm!^S>;^{Fpa0T82Lje1Q;=jsk9$DH7JlAt%YNh7+#'
    'YQY#@g$U=K5*aYl@>P5!DmRT)d~!0v-4#;JP+H=Mq*4kYhmELAdL<~KOMG-hIhZ=8Zj7p)0uX&b>uCuUR3_OyW{EF?P&YKezuyIW'
    '6U+uY)47Ns&zzuaQ$Y?a^^}`6XF@?tt6#VIM1k^TWsZxG=oaQ*<~;s}CCGc2$(zDij~XP1ZFZ^_-(M9jHyFv#{SJmhc1$yW1+>v}'
    'cz;EWK0$diV<fn3^OqN~j<8OXCC#z_`iIg&AuwvwDzltZL+)rUfVQEgegy5e{D>OcQtw7EFMlOSrJKG;vlD#8Ha1VRf&<S#BJ+#7'
    '@7SPxwHQ8x)WMA{nUiWg%d@zGm2Crz(wc8}I}LrpPz6Ub;Ly<snhyKN74_aSq{PYvZMDa<(8-}jyzIRkuPLkT$D9=T>{x;ad!eDm'
    'wts1jQ<%d^<TEZCYOAT(c9H%C&ln{7g+W5t3!>D(@0QYs@t76A>$K;)o9yd97vF@(E9%;nBrM1{y)<NLo4|FY1+>u&S)co<@)^E8'
    '5Y|Oub@})JLK0;jeDFRP=L6Rs1k^a4OVDfrCYAwilk^rHwmHOgM!uiIpqkjruwEjh9EM6s5e{EvMTrQ!d~^9F7AAH2+m{K`z>Y}T'
    ';l5~f-3o+MbI<Trey}6X@q4mzs$uVzLUJ7IYdSd!Swb{~5~d&Q&~|WUXAI3RzZaJ5a0X40oS0|4MmKr8(rMGQwqB^){!Nz~LP`tB'
    'ZS7DK9mx%yD$%xCEE3O-2oXL;G8+icJ9A&$66V9CJhdA5%my5SCuBlj@5yHRY^e^ig4KY9eSbkl;VC^3bm~;9i-E@{fc!DZqednL'
    '^Jj6MMa~rj55Fy8bGg3M$1+3~t=lrR*F`g!8RQ+&2s#aVzD;0Wq;Gf~Cnl^-b(p@atV)p<{vvedcI#7Ac!BN=#}9A@TT;#2@k81J'
    '@#`pBs!u7M4<^Ej>NJn4Y&f;by6zCO^4D@>zeRDRltBOZ90Ft1*mXv6eo1s2M^u}$v6hWXh-PC^8Xh=Fqv%LJB_vyWQx4ek`XGMk'
    'Smx-eZTkg9kPn@Rj=e0T@;%$GY?3ZOC1L)2NXn_Zl9;*mf?0QoJzcFUhheax;E0HPE5E|d$(!zg)hYbrK?%Pk`<bQ--{P6+Z8jAf'
    'l0)b~rn9~2F*LC4PlJQNT$TsNHTec0@64mWxV@j?6p38#*Gm8bMSy~!agh9h@v<Zxbd!OE2t<LpVIo%J!E~c#TigalO&ffT<+M)f'
    '++gj$VTVIh2aA_JY@Wi;b6!a52t{bL6r1@8<lE=J*d{mUt*a3Z&z5_v)02R#%rv&SE=1$b`I<}9*-|xClnXkA9PIQKzO`a!K=*yY'
    'gNT8=Td1WY%Wc=C6qL8n(l{Av<oRTZg)oW?%-Hd!ONUj1gOB#WW6gg82S?j+?}US!v}p1mS~(iQ-_Nki^FfwkB-P77w$f-~dpzUF'
    'qdL5OC?29ze~7A^9}foi-<VU$b6!DQiY)qwMbkes!7GoRcrggS!7c1ZgAb7}gFCE67(oqW7h!u!mrtl##_%4sGf+wXhCw#kCLzSM'
    'H3K%i8nFCWXhY%?)gA}I-}aTp`><`cX3fLz8FL?)(HlV@thIrmwc<o(I26pI-0k4^KG00p0Wbq^o@E7wYAhyd)l0=1nOvq!0>tS*'
    'aZI8WfUbv=tQzn@w2-zcK)|K5FdS1GA&>pn4i|ysF7-)vV-V6Qu-}~Vd0=Yv4!yTx$yxAoGp9E;ojZcRO^mzi!<lHiUZ^f`6OUWw'
    'q_I5~r!_9Xy)nW0QJn+V29nLU;f-`UM#JRZd2DOqZy^h<Y1C)y`?Y0$q2Bq!2(OBq@oZ%O=qgJTG6cS|IEH#j+!qKy31~ia<NHTc'
    '8G0`*K1~`jy9x#p(u}OUp4de2;5=$^`?u~PzW6u_Vlly9PcA{svGfwOMO=a<G)Fc|4YG)6hl2XehBt|};u|GQu7mCEk&uu`bT42l'
    'EUAW)|6S$Uo=YjI>cx6}meAzW?J@`^V0jBnB7im15eoqR`;88`pGO^)<nNIu+FB1sBcLn`NjZcDyvUljf~s8zsaRZegy6qep~d(6'
    'YR<!+$gKKrtaxXfW&e?y%rI%Mez@ObdpQig0J(brZYpQ?HpG>2-lTsc+$gjU8S8>GIuEg-Nn{oAHuNHY@!vBf`kM<3*ER<u`KFX5'
    'Ee^fwyWO*2yn%?G`<3Ll$rn?D{1#EECe9km1d+6q$39wU_*P~*o0G2Fd1c^T{B54pdUX#T0%n6}g0uq?;{-6H7S(+O$xSXaP*(B)'
    '8>M%-^||>p%GDRJD+LT-L6@anXqg16?7559UH|IXk!JfE*eWR#W3N1h=;+7X*QRcA0a#iVkPp0=&PDF$!Q$#10|oRdQyI38s)PwU'
    '48p0f5ufgx-r6bL_a_xUD{Peor-CZ`-iT|g4m2lW-9-DZwXl5%rZ`XPBjNzoGnjLNhWYB&r}eh#Q6d8Xj@WaEeDY(+h4pJlnO*iF'
    'qdPQFNf$WZuKwetSQ3+jlYOHOt^d^aF+Wh$4J1*Xo3@JPe>f{X*e7iK-DHh^zM(QU)ijA!Dg+!XVJesS0>i^k4@T16r(5k>Wj#vh'
    'i?7;9Z&}vzsAvc_#w1Q>3Vj_k4+F^hFKO8C-Gxw&@q0Ncb%K=?aKdv~bXGZH?|R6^IZHP2dIo*rcT9FT4~A0boVqKNC$Llcjjo4O'
    '+W`%K+j^f_6gvB3_$kh&)|%v84w(b1(8et%p0M+o8@qTDX97%5jF;4Ap+m0sc@?Itq}0`saQP!QL81o&cyX<?yi{MMZqL$|&lcK7'
    'n75af2o@)GZwI%ijJJ0joubz==A3RttL_8R><>j{Y9X674=Le(14n?2ui)<jcC2C^M@;F|F|dIlZ|=2_el{38Bw6cp-{wAq0+EEZ'
    '8Nvx!>J|pcDdhR>^7vmv4Di6Jem_9^%F+?yznIXf5YRA*T$W*;X4WHbS~Do8Zn{eySGsm>9HIfvOdACPB@B!36I}ci(s8IX9=0#_'
    ')Ek8RgsRv#!M|Lqp+6W+<=EeD`kuD^@>XD^bJP4yFDRt!#=`^sZ`B}pV^?Sg0>*|^k593;n1!^)QZ%%>s3twTY?Np8q64*8qA?Wq'
    'q7-TZ0s4TO%d53NGoXAIhS`qXsbXvY3FSzB?B$1I#BFZj!`hNz1ch-@%dx|xtJcwCFnNx=P20!!1V-E|VFy$Sjtw;K?mejyKQ=WB'
    '^j`HDm+Y~rp`N;hSW^qdt1lI5F~+56pN4w~^o4CILAATrf}R^dg4na?|FpmhGt0gQD!_Sv-hTmYc*s+BFTYUYxBu#O1DF38borD*'
    'xLD;NgRDq<zG};|l`PU%D}1}Om-%eS$oHNm##bm<OI`zd!)Xshu?8L{-;MzUAG|<WnzYWOT>Cw%;C0)t80YHA;OA!mF<c1N%1F53'
    'R#g_+eXtZ(4IcS>DhH*e^S6-QPu@7S*7%c+gsgjur_igqa1qo_b?3B)&?qc9cnEcy*BGtD-a+XE_tvVbZh7WaJyfsJ!KEY4=lJ?-'
    'F)R?wV9uo3zh3)Gcn={X-Vn_GzckfQ;W`Wrf!8$gz6i}8?evrdy^+{#IW6+;Hxt07>jyfCDV@t|pripErY?8+bNxW>qbU#GFUD17'
    'oo!3CgV5;@0He~5caEgHj%7$yJGcCSDy$lqHE=^+h$Oqu)oLcM(!kA0Sr6idxIGhs2MKj3kU&CKyx*;B5pK#d=WW8yWYl{e@9b~S'
    'FA{vzWaZspM<aot?NMop+M9{f#cDhf0>0_Ye3jIN0%2yzw4gQeTnr0>;CGV$L209mOo;kFLd<8tS>vv(XX3p9^+~l_(D?@$r_U2s'
    'CN8pZ%RxCMP_|xw$xdhH-bt^D$6nxM%UE5R4mN0@O57217;p|q0=u615biAytKiJDcLAp;;}*fUuXeO3eTDVFe4H{$N#NaN$p(lL'
    'G;K^HfuGa|nfDcG*gHC|X&-sr*d~GNh^N%Ru7)<2pn=Kt-&=qAl1*KbXBrgr&zn)+_~mE^f)yAebk+<ovI50_WGy8PRzf|{|EyNH'
    'Uqi|4?;+2!<1{aQlw>btRk8)@#h*HsdLmOu0?ar{Jj?oNIIK}KrQ$SrF88OYKh@!A_+Bx*L8W4aw&Z;l*B0a%0oX^xCqrcL@FoP('
    'y>@6>oLjQ#B4NbfhFNNhNzlFc7Y8MRks#^+SQ>NU`2OW%o&b~<&d;K$<Xj8gc~f56LUFv$(~PO*7%bsKn`MN&lwEW>gb8WtO^Ae%'
    'aV`({3~P^m?q|?Tt>&OO{u?CHFI~e$)2Dq=9YO<cD&RPVi0;h~p1Q?>>g2<=0?_>mn_mGqfguS3Ww1RD+`kF6C9Ayz`|W0c-7!Tf'
    'a3$!RU4ev=U^r66Ujop{27CZ63sP0q+<CFDBSrtWeYa?UzwahoTjP#|PgJcUiEO8Or&LyH0#gtVMI=j$)tDufH3ik^_2})?s>_(U'
    'pSf}Ja(9@9_2yxCyBZ@bI`IOBR=Dir^fPHSO_{JX8jThkSDyxz`{38~M^$O^P>`BYS4E%K@wl!{;r^>%#P|>6cyy6}=K2Sm0PFFe'
    'm9L+|2cdipP(?f^sw+!ESQ)4XCkw%*bC=b;)o-r~!GoB`;W0`;tHJakds0TJeP4=gYp0#E8qmfBu(dc(IlNRCGl=}z)qRQLrjMCn'
    '(+(1w%m56XXnv9E=W~|<$q@WupBy^w7ZHg=Kq*$DbowA3mCF8tb?rN#>GDA((4x-C(JWeXixnT1Zn3?H_uTP2%9EJprJ5(m)W<bH'
    'pHg;$PH6{9sEkKYc0VclNU@=Z*xj&X6`I)JyX29xUr_#cP1O&u3mbCv#A!FPhta3Xryz9L74JMAZ3Fpaf*aevxZOZR8<_YcHgg#z'
    'JWX06oubjk##{7MRFKl0R9&j&uV-#+3|A^&bW9w(V5QSl8u2Idxj4X8H}G)ww{hUaiZ8|;J00S;Vs2=(v+^0@GJ#=G6cr%Zo!17O'
    'qLPknK@pxmX0e;@Fuz{Hlhl2!iPhENqY+w^){d=_1E+7M1!z=b<61}Wvdr&xk07uwDfe5OiLlhYSxKl;>??l>7gtz7w%41h^q}ze'
    'X{q@g^VKaaO^QYoR$<1#cXtOqRF54QpDisVS{$J=<DV(+o1=Pd(1N_BZsBNacL66f%x=6huj*N;?wpBF|IOKl<&_SJWRs9AP7!lm'
    ')xKD|7&R^)enhecPb8yXz5Q|`RX!k|N?8M+$m;)@TM4f4I?;F~L?01;Sedhf5GZp15Dx(Z$*3oU#wR-mHEbE&&KSG$*wx6a^$Ig?'
    'LFCFB+6l}Sc+?tU`a6&q99v9P44iF<g-*&drJI*;>(Z>ztL1aZzV6=u&Yrh@LL@)W3LA|EYl2sht&CQl?Txp@*5JJhjui&O&@sv+'
    '?nj+K0JC~Q%IXP|H{#yDjEdD_OTQy%PW`SW>1Qb(^-=#NzqEM#u)~0?+Ct1l*5V2FdPum!p1`@lAG+7#{~kX;zupd8`6SUmQJGIu'
    'TvGglaZc>E<vop;c@ae~1ep<PU_b1v0xRUTjNof3q9=A6k=gnx__b+ek)eA+3XaBNaR?s;&u<gOicmYAl&AFfn8CfxzIs306hs%)'
    '>EV>MOwqBC=PaE#4y~KGF0l6-xyZY2qyl|4H3$X$#L0?8hIKSo0XM+&H^NvAHCH|61jPert6L`bScpN-7mR<YsY!2iFEEZQ8oO%@'
    'AmgSNI3l?eY>&W2a&GDV*<QFXM#q(QocGKV{PV~=;lw1UX@aT;MKgG6GD$3?syFaIf`7TrNL{(9F%Wt`tQQo@?4*6L1r7^kYbO$f'
    'PmHCf1kE!Bls5@sL#Mn*(oF7SvXNBgL92j`f~qC(asnBbbTn{qMA}?%{+^{q@i5RCBW4==95|}!0rGTGZrSUGixOoMF(2&DqX#Pi'
    'xhlwHw#~&k=j^-25j5J`P{jYX)XSu<C$Qu=lVnB!)y0wf?^|^Fa<59kbhllQ#c0ZMX>>CPQyOH+6??L@58nb>k)i9YJy5wKI|#lS'
    'zxNZ<JqMmo2YPq#kA2|#!5zq4_}^go#?Q&3-Ir*5ILMxyBTQ8Xz8<wm0Z5m!W5ylM(Z%zGMQ^_5O<x$VWME2xZSKq|?BMc+K&w1u'
    '_VFYt$oWOdYau!%ifqN_Hkf9`9|Z~RjSjZJ1GA!D9Z)eDSy|Y58ddswujnPwil-7udW&7cJpR&2efTh8;)|esHIF&myHfr9{j<Fh'
    '8>avmxdOqTpF|p2nSkmtc|}0Nk46Uh52l+smE7chTSUvKcM4!O^?W_*y$SkGKrSiT9kjVrooHgS9o=dnZ7?YdMC}~Qo~%IrqUs9>'
    'r9BL2qF!+McN*WLKrM#o1YDjUc;+FPLhPFHpe|D`SLF{M(w4L7M5chrY=pY5AvOBxdG2qxwRqHjy5bu<o63dEyyXLyZIm?MKg4GW'
    '%<CMSN;9vJ*Py-86CH4@Y-ca;qvh?F5n3JF@yxwUv+wLUOTM%60vt~UIS^CeE6v<k?Gf9e=OM)OzT0-Vl!^kPOh$xv&n~i4a}rY{'
    'Wm<6;5VmmN^P49w+E*2VZclJIRH!=I#25&>@Hgh5xYrxBUmLfKA;6$F#5ivS<DNIk(KqW7#q_D@#w@NBELN94qfGdd;H`JbGol%Q'
    'JHS2CqIcqN%sb=a$<nQ0nARB$-39t=Rx?(MZvxL8k^tgi;hP>v0DX9`5L~m7(W6fPN!Xc@<sA3{94@nm!FV0}W~Bp)3Q2tf8goJ<'
    'VV>@-sj<3q#-9yH6Ai3xB6LY|SJ&PEj8D%f<imE*)xS)1>iT~g9t+0&tQKz3Kkc3ip({!+;n}cDRORSRP=^Wv6fg++%Sh4Im5J?@'
    '(wjA<4ww&Qvlyo^x;@~S4ac~JpGw>kCwZ$f%Tw8<#=IGB#3g-Cjn8J)eb}THlI?H-7z2KIM9k}Q7@_h~&)$r*bgYBUQLu)C?_o@s'
    '?@hLOg??iWcUG+Enkwaks4{FmS85-=(}FivKOTqt_ZUTOE}P~7*84uI-)rY4W}^=#`$eaaK8|G=pqf%gJ8Wd*u*vdo4hXn^f6Ww_'
    'l2oM&OO!(iChuI!fKH+br*Je>aO^t^O_FQwz^A5<jiR-1W?f=Yu-Knjh7%mvZghQMX5Y(#+Jgrj8d%U-CbTae#>lKXAv#SE9HRnB'
    'M^ckrWl8*Z-hO)tP4tA&jP%`81PDws$WXkaoUnj%Lw;CL{l?`=%5cz2gLXJsF{nZq4U7efkFc|doQ7NY<X+2)9l9J2C^j?Xq}Goi'
    '{gaB~<`Y(=Y%LSN#YFtd12ikPTUynJLZ~d!{k{CWOwBFLyqz{$5{nXP{>ZHYy85!{;dwayE|3p~cRb0xEtubuNsukY_b%P6|Nd#Q'
    '06IwEki9HP@B?(AzT4z&UDjs&o{12$+AfB$6bQtzhC<F-Dg2~L$W8<f4(CM6$IG^NL1H%fiFTPXRml9BHQh3e>Utt<HCnJ8P);})'
    '-62iJZDxHJkx<Jd1f_TpGP0y?r|C>BGb&PuBz3t5Fov*%$HxdZ!pu`+>%KM+B!s;`2GRB8Odd`+12JNKPT1wsnHJAB%>uD>QkHQ5'
    'm%wk;abUhChCRa|>?*Jih_y7nbAHXu`bYSwbudSWd_(prR7Of}AX)h<!RBEey_f8yb?U=z)pogKZD=J~nPeDblT+tNWawVMk^lez'
    '_lN0;xhM^(00FCl1dxCQVU;jKvBYQl0ssI200dcD'
)
class SM3:
    def __init__(self, data=b""):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self._data = bytearray(data)
    def update(self, data):
        self._data.extend(data)
    def digest(self):
        if hashes is not None and hasattr(hashes, "SM3"):
            digest = hashes.Hash(hashes.SM3())
            digest.update(bytes(self._data))
            return digest.finalize()
        data = bytes(self._data)
        bit_len = len(data) * 8
        data += b"\x80"
        data += b"\x00" * ((56 - len(data) % 64) % 64)
        data += bit_len.to_bytes(8, "big")
        iv = [0x7380166F, 0x4914B2B9, 0x172442D7, 0xDA8A0600,
              0xA96F30BC, 0x163138AA, 0xE38DEE4D, 0xB0FB0E4E]
        def rol32(v, n):
            return ((v << n) | (v >> (32 - n))) & 0xFFFFFFFF
        for off in range(0, len(data), 64):
            block = data[off:off + 64]
            w = [int.from_bytes(block[i:i + 4], "big") for i in range(0, 64, 4)]
            for j in range(16, 68):
                x = w[j - 16] ^ w[j - 9] ^ rol32(w[j - 3], 15)
                w.append((x ^ rol32(x, 15) ^ rol32(x, 23) ^ rol32(w[j - 13], 7) ^ w[j - 6]) & 0xFFFFFFFF)
            w1 = [w[j] ^ w[j + 4] for j in range(64)]
            a, b, c, d, e, f, g, h = iv
            for j in range(64):
                tj = 0x79CC4519 if j < 16 else 0x7A879D8A
                ss1 = rol32((rol32(a, 12) + e + rol32(tj, j % 32)) & 0xFFFFFFFF, 7)
                ss2 = ss1 ^ rol32(a, 12)
                ff = a ^ b ^ c if j < 16 else (a & b) | (a & c) | (b & c)
                gg = e ^ f ^ g if j < 16 else (e & f) | ((~e) & g)
                tt1 = (ff + d + ss2 + w1[j]) & 0xFFFFFFFF
                tt2 = (gg + h + ss1 + w[j]) & 0xFFFFFFFF
                d, c, b, a = c, rol32(b, 9), a, tt1
                h, g, f, e = g, rol32(f, 19), e, (tt2 ^ rol32(tt2, 9) ^ rol32(tt2, 17)) & 0xFFFFFFFF
            iv = [(x ^ y) & 0xFFFFFFFF for x, y in zip(iv, (a, b, c, d, e, f, g, h))]
        return b"".join(x.to_bytes(4, "big") for x in iv)
xtime = lambda a: (((a << 1) ^ 0x1B) & 0xFF) if (a & 0x80) else (a << 1)
def rol(num, shift):
    shift %= 32
    return ((num << shift) | (num >> (32 - shift))) & 0xFFFFFFFF
def rl8(x: int, k: int) -> int:
    n = 8
    s = k & (n - 1)
    return ((x << s) | (x >> (n - s))) & 0xff
def ror32(value, count):
    count %= 32
    low = value << (32 - count)
    value >>= count
    value |= low
    value &= 0xFFFFFFFF
    return value
def ror(value, count):
    count %= 64
    low = value << (64 - count)
    value >>= count
    value |= low
    value &= 0xFFFFFFFFFFFFFFFF
    return value
def get_key_hash(key, rand):
    to_hash = bytearray(68)
    to_hash[:32] = key
    to_hash[32:36] = rand.to_bytes(4, byteorder='little')
    to_hash[36:] = key
    d1 = (rand >> 16) & 0x000000ff
    d2 = (d1 << 11) | (rand >> 24)
    d2 ^= (d1 >> 5) ^ d1
    d2 = ~d2 & 0xffffffff
    return SM3(to_hash).digest(), d2.to_bytes(4, "little")
def split_blocks(message, block_size=16, require_padding=True):
    assert len(message) % block_size == 0 or not require_padding
    return [message[i:i + 16] for i in range(0, len(message), block_size)]
def add_round_key(s, k):
    for i in range(4):
        for j in range(4):
            s[i][j] ^= k[i][j]
def add_round_key_con(s, k, con):
    for i in range(4):
        for j in range(4):
            s[i][j] ^= k[i][con[j]]
def bytes2matrix(text):
    return [list(text[i:i + 4]) for i in range(0, len(text), 4)]
def xor_bytes(a, b):
    return bytearray(i ^ j for i, j in zip(a, b))
def matrix2bytes(matrix):
    return bytearray(sum(matrix, []))
def mix_single_column(a, i):
    t = a[0][i] ^ a[1][i] ^ a[2][i] ^ a[3][i]
    u = a[0][i]
    a[0][i] ^= t ^ xtime(a[0][i] ^ a[1][i])
    a[1][i] ^= t ^ xtime(a[1][i] ^ a[2][i])
    a[2][i] ^= t ^ xtime(a[2][i] ^ a[3][i])
    a[3][i] ^= t ^ xtime(a[3][i] ^ u)
def mix_columns(s):
    for i in range(4):
        mix_single_column(s, i)
def inv_mix_columns(s):
    for i in range(0, 4):
        inv_mix_single_column(s, i)
def inv_mix_single_column(a, i):
    u = xtime(xtime(a[0][i] ^ a[2][i]))
    v = xtime(xtime(a[1][i] ^ a[3][i]))
    a[0][i] ^= u
    a[1][i] ^= v
    a[2][i] ^= u
    a[3][i] ^= v
    mix_single_column(a, i)
s_box = b''.join([
    b'\xFA\x7D\x08\x6B\x9C\x59\xB3\x4B\x04\x5F\x39\xD0\x38\x4A\x91\x99',
    b'\x00\x67\xA6\x20\x9F\xF5\x4D\x82\x73\x26\xEE\xDF\x18\x66\x83\x33',
    b'\x80\x03\x19\xFB\xD9\xFE\xAE\xAA\xA9\xB0\x52\xC6\x0B\xF3\x79\x25',
    b'\x4E\x78\xB4\x36\xAC\x5D\x1A\x27\x9E\x88\xDB\xBD\x3C\x63\xEC\x49',
    b'\x15\xC1\x30\x1F\xDC\xB8\x56\xD4\x6C\xCD\xCA\x09\x43\xC8\x35\xA3',
    b'\xEF\x1E\xF4\x96\xD2\xFC\x0E\x72\x7B\x94\x84\xD1\xEA\x45\x5A\x62',
    b'\x02\x3F\xD3\x12\x81\x34\x2B\xDD\x7E\xE6\x28\xF2\xA5\x46\x13\x01',
    b'\x3B\x21\xF6\x61\x37\x29\x2A\x0D\xED\x8C\xAF\xBF\x9D\x5C\xBB\x24',
    b'\x76\x0F\x75\xE4\x53\x89\xE1\x98\x8D\xB1\x9A\x65\x70\x4F\x54\x4C',
    b'\x58\xAB\x6E\x6F\x8B\x23\xC4\x07\x11\x0C\xBA\xCF\xA0\xA4\x8E\xD8',
    b'\x05\x3D\x14\xB2\xDA\x74\xC3\xD7\xE7\xBE\xD6\x7F\xDE\x48\x16\x3E',
    b'\x85\x90\xA1\x55\xB7\x77\x42\x22\xC9\x86\x50\x2E\x17\xF9\x64\x31',
    b'\x2C\x9B\xF1\x6D\x1C\x44\x68\xE3\xE9\xA8\x93\x97\xCB\x32\x57\xEB',
    b'\xE5\x71\x6A\xAD\xC0\xCC\xC7\xC5\xFD\x60\x1D\xA2\x2D\x47\xA7\xE2',
    b'\x51\x69\x5E\x7A\xCE\x0A\x41\xB6\x95\x8F\xF7\xB9\x87\xE0\x3A\x06',
    b'\x10\x8A\xB5\xF8\x5B\xD5\xF0\xBC\x92\xFF\x7C\x2F\xC2\xE8\x1B\x40',
    b'\xEC\x1B\xDA\xBD\xBA\x98\x91\x0C\xB2\x2B\x83\x41\x34\x67\xFB\x0A',
    b'\xD8\x76\xB5\x46\x05\x59\x61\x23\x75\x90\x87\x2A\xE3\x50\x15\x4C',
    b'\xAC\xB1\x79\xEB\xAE\xE5\x95\x47\x04\x68\xF0\x86\x3D\x51\x8B\x0F',
    b'\xCA\x8E\xE4\xB9\x4E\xF2\x12\x82\xBC\x0E\xD5\xF7\xEF\x28\x25\xCF',
    b'\x5B\x5D\xE9\x6A\x55\x02\xE1\x33\xBE\x93\xE7\xF5\xAD\x9D\x3E\x39',
    b'\x24\xA8\xE2\xFA\x17\x57\xD0\x7A\x0D\x08\x30\xD6\xB8\xA3\x8D\xFD',
    b'\x07\x9A\xC4\x1E\x6E\x22\x64\x97\xD2\x1D\xB0\xBF\x45\x66\x3F\x6C',
    b'\xDD\xDB\x27\x80\xA7\x11\xDC\xA6\xC5\x52\xF8\xC0\xB6\xC8\x5C\x00',
    b'\x73\x60\x7B\xA0\x19\x13\xAA\xC9\x35\x48\x4B\xD3\xA4\xCD\x9F\x99',
    b'\xF3\x10\x44\x40\x54\x7E\x29\xF4\x06\x1F\xA2\xAB\xA1\x2F\x3C\xF6',
    b'\xAF\x85\x62\x36\x21\x7F\x5E\xDF\x20\x1A\xB3\xB4\xE6\xFF\x72\x84',
    b'\x8F\x65\x26\x94\x5A\x77\xEA\x43\x78\xC7\x4A\xCC\x2C\x14\x6B\xC6',
    b'\xE8\x74\x53\xFC\xD4\x1C\xCE\x31\x70\x03\x18\x8C\x96\x38\x32\x89',
    b'\xF1\x3A\x5F\xD7\xF9\xA9\x69\xB7\x63\x37\x58\xC2\x3B\xC3\x71\xCB',
    b'\x9E\x92\x01\x8A\x0B\x4D\x88\x9B\xBB\x4F\x6D\x6F\xE0\xFE\xA5\x49',
    b'\xDE\x56\x16\x09\xED\x9C\xC1\x2D\xEE\x81\x7D\xD9\x7C\xD1\x2E\x42',
    b'\x5B\x4D\xC1\xA6\x5D\xEA\x44\xFD\x45\x4E\x1B\xA1\x3F\xD1\x89\xE1',
    b'\x7D\x2F\xAA\xDB\xAB\xAD\x59\xCB\xB1\xCE\x9A\x28\xC9\xE0\xF6\x70',
    b'\x39\x4A\xD7\xFF\x30\xF5\xDD\xBC\x57\x3B\x11\x8D\xB2\xEE\x00\xB6',
    b'\xE6\x1A\x5A\x7C\xF9\xDE\xC4\xCD\x2E\x80\xBB\xB9\x4C\xA5\x9F\x84',
    b'\x08\xC6\x6F\x42\x6C\xF0\x27\xE7\x8B\x3A\x9C\x51\xFB\x67\x21\x75',
    b'\x41\x31\xA7\xCA\x20\x43\x2A\xB7\xBF\xD9\x7A\xF2\xB5\xF8\x8C\x2C',
    b'\x23\x83\x4F\x8F\x60\xA0\x04\x13\x37\x14\xE3\x01\xC5\x63\x66\x5C',
    b'\x74\x81\xDF\x58\xBD\x68\x90\x3D\xD2\xB3\x34\xF4\x19\x93\x32\x29',
    b'\xD6\x49\xAE\x0D\x4B\xD8\x07\x9E\xAC\x1E\x2D\x0B\x40\xB8\x72\xBA',
    b'\x76\x10\x71\xA8\xE4\x56\x1D\x48\xFE\xE5\xC2\x47\x91\xDA\x87\x26',
    b'\x9D\x1F\x88\x6B\xC0\x98\xBE\x25\x09\x97\x33\xA3\x85\x16\x5E\x7F',
    b'\xDC\x6E\x54\xE9\xF7\xA9\xC8\xE8\xC3\x77\xD0\x82\x2B\xEC\x02\x62',
    b'\x8A\x92\x0E\x3E\xB0\x0F\x05\xF3\xF1\x96\x78\x38\x86\x36\x18\x3C',
    b'\x24\xCF\x0A\xB4\x53\xCC\x61\x65\xA4\xC7\x94\xD5\x15\x7E\x6D\xEF',
    b'\x79\x22\x35\x12\x6A\x8E\x52\x06\x55\x7B\x46\x64\x50\x95\xE2\x0C',
    b'\xED\xD3\x17\x03\xA2\x9B\x99\xEB\x1C\xFC\xAF\xD4\x73\x69\xFA\x5F',
    b'\xF7\x2C\x1E\xBF\xC8\xE1\xF3\x9F\x76\x80\x71\x48\xAA\x94\xAD\x64',
    b'\xFB\x89\xC6\x60\xC3\x32\xB3\x4D\xD2\xE0\x44\xDD\x5F\xA8\xB1\xC7',
    b'\x68\x23\x34\xC9\x6D\x12\x7F\xB7\xEB\x15\xBE\xA9\xD1\x78\x93\xA0',
    b'\x0C\x92\xA4\xD7\x47\xE3\x8A\xC2\x70\xAB\x26\x41\x9A\x79\xA7\xD8',
    b'\x14\x85\x8F\xC0\x6F\x56\xD0\x8C\x11\xB9\x2E\x3C\xE2\x9D\xCF\x0E',
    b'\xDE\x03\x5D\x46\x3E\xCD\x38\x43\x0F\x33\x5A\xD9\x1A\x65\x6C\x22',
    b'\x3B\xFC\x30\xA6\x88\xEA\x37\xA2\xB4\x8D\x8E\x51\x9C\xD6\x40\xEE',
    b'\xF9\xF8\x84\xF4\xAE\x97\xE9\xCA\x0A\x45\x67\x57\x04\x2F\x83\x5C',
    b'\xD5\xC5\xC4\x82\xB6\xA3\x91\x98\x1F\x4A\xAC\x96\x81\x6E\xCB\x1B',
    b'\x09\x08\xAF\x18\x95\x49\x7D\x54\xED\xFA\x16\x31\x3A\xDA\xB8\x66',
    b'\xF5\xA5\xF1\xFE\x10\x01\x06\x74\xCC\x63\xDF\x7C\x28\x25\xF6\xCE',
    b'\xB2\x4F\x8B\xE5\xBC\x87\x69\xBB\x86\x21\x07\x00\x36\xE7\x0B\x50',
    b'\x59\x9B\x1C\xE8\x62\x58\x19\x61\xF2\xBD\x27\x5E\xBA\x1D\xE6\x99',
    b'\x42\x3D\x0D\x2A\xB5\xDC\x5B\x29\xF0\x2D\x4C\x53\x7B\x6A\x73\x4E',
    b'\x3F\x75\xFF\x4B\xA1\x35\x17\x55\x72\x39\x20\xD3\xB0\xFD\xEF\x02',
    b'\xEC\x77\x7E\xE4\x2B\xDB\x90\xC1\x05\x9E\x7A\xD4\x52\x6B\x24\x13'])
inv_s_box = bytearray(1024)
class AES_V3():
    r_con = [[1, 0, 2, 3], [1, 3, 0, 2], [0, 1, 3, 2], [1, 0, 2, 3]]
    r_con2 = [[1, 0, 2, 3], [2, 0, 3, 1], [0, 1, 3, 2], [1, 0, 2, 3]]
    r_orders = [[0, 9, 14, 11, 4, 13, 2, 7, 8, 1, 6, 15, 12, 5, 10, 3],
                [0, 9, 14, 15, 4, 13, 2, 7, 8, 1, 6, 3, 12, 5, 10, 11],
                [0, 9, 14, 7, 4, 13, 2, 11, 8, 1, 6, 3, 12, 5, 10, 15],
                [0, 9, 14, 11, 4, 13, 2, 7, 8, 1, 6, 15, 12, 5, 10, 3]]
    def __init__(self, aes_key, khronos):
        self.word_size = khronos & 3
        self.aes_key = aes_key
        self.s_box = s_box[self.word_size << 8:]
        self.inv_s_box = inv_s_box[self.word_size << 8:]
        self.master_key = self._expand_key()
        self._key_matrices = bytes2matrix(self.master_key)
        self.con = self.r_con[self.word_size]
        self.con2 = self.r_con2[self.word_size]
        self.order = self.r_orders[self.word_size]
    def _expand_key(self):
        init_values = [0xca025ddc, 0x823dc546, 0xc9420583, 0xc298225f]
        init_value = init_values[self.word_size]
        mk = bytearray(init_value.to_bytes(4, "little"))
        mk = mk * 4
        mk = xor_bytes(mk, self.aes_key)
        mk += bytearray(32)
        rounds = 8
        for i in range(4, 12):
            idx = 4 * (i - 1)
            k0, k1, k2, k3 = mk[idx], mk[idx + 1], mk[idx + 2], mk[idx + 3]
            if i & 3 == 0:
                k00 = (init_value >> (rounds & 24)) ^ self.s_box[k1]
                k1 = self.s_box[k2]
                k2 = self.s_box[k3]
                k3 = self.s_box[k0]
                k0 = k00 & 0xff
            rounds += 2
            mk[idx + 4] = k0 ^ mk[idx - 12]
            mk[idx + 5] = k1 ^ mk[idx - 11]
            mk[idx + 6] = k2 ^ mk[idx - 10]
            mk[idx + 7] = k3 ^ mk[idx - 9]
        return mk
    @staticmethod
    def sum_data(data):
        key = bytearray(32)
        for i in range(31):
            idx = i * 8
            n0 = (data[idx] >> 4) & 2
            n1 = n0 | data[idx + 1] & 64
            n2 = n1 | (data[idx + 2] >> 2) & 1
            n3 = n2 | (data[idx + 3] << 3) & -128
            n4 = n3 | (data[idx + 4] >> 1) & 4
            n5 = n4 | (data[idx + 5] << 3) & 16
            n6 = n5 | (data[idx + 6] << 5) & 32
            n7 = n6 | (data[idx + 7] >> 4) & 8
            key[i] = (n7 & 0xff)
        key[31] = 1
        return key
    @staticmethod
    def mix_columns(data, key):
        data = bytearray(data)
        for i in range(31):
            kk = key[i]
            idx = i * 8
            data[idx + 0] = (data[idx + 0] & -33) | ((kk << 4) & 0xff & 32)
            data[idx + 1] = (data[idx + 1] & -65) | (kk & 64)
            data[idx + 2] = (data[idx + 2] & -5) | ((kk * 4) & 4)
            data[idx + 3] = (data[idx + 3] & -17) | ((kk >> 3) & 16)
            data[idx + 4] = (data[idx + 4] & -9) | ((kk + kk) & 8)
            data[idx + 5] = (data[idx + 5] & -3) | ((kk >> 3) & 2)
            data[idx + 6] = (data[idx + 6] & -2) | ((kk >> 5) & 1)
            data[idx + 7] = (data[idx + 7] & 127) | ((kk << 4) & 0xff & -128)
        return data
    def encrypt(self, data, iv):
        plaintext = self.sum_data(data)
        blocks = []
        previous = iv
        for plaintext_block in split_blocks(plaintext):
            x = xor_bytes(plaintext_block, previous)
            block = self.encrypt_block(x)
            blocks.append(block)
            previous = block
        key = b''.join(blocks)
        data = self.mix_columns(data, key)
        return key[-1:] + data
    def encrypt_block(self, plaintext):
        plain_state = bytes2matrix(plaintext)
        add_round_key_con(plain_state, self._key_matrices[0:4], self.con2)
        for i in range(1, 3):
            self.sub_bytes(plain_state)
            self.shift_rows(plain_state)
            if i == 1:
                self.shift_rows_con(plain_state, self.con2)
                mix_columns(plain_state)
            add_round_key_con(plain_state, self._key_matrices[i * 4:], self.con2)
        add_round_key(plain_state, self._key_matrices[4:])
        return matrix2bytes(plain_state)
    def decrypt(self, ciphertext, iv, data):
        assert len(iv) == 16
        blocks = []
        previous = iv
        for ciphertext_block in split_blocks(ciphertext):
            dc = xor_bytes(previous, self.decrypt_block(ciphertext_block))
            blocks.append(dc)
            previous = ciphertext_block
        key = b''.join(blocks)
        data = self.mix_columns(data, key)
        return data
    def decrypt_block(self, ciphertext):
        assert len(ciphertext) == 16
        cipher_state = bytes2matrix(ciphertext)
        add_round_key(cipher_state, self._key_matrices[4:])
        for i in range(2, 0, -1):
            add_round_key_con(cipher_state, self._key_matrices[i * 4:], self.con2)
            if i == 1:
                inv_mix_columns(cipher_state)
                self.shift_rows_con(cipher_state, self.con)
            self.inv_shift_rows(cipher_state)
            self.inv_sub_bytes(cipher_state)
        add_round_key_con(cipher_state, self._key_matrices[0:4], self.con2)
        return matrix2bytes(cipher_state)
    def shift_rows_con(self, s, c):
        for i in range(4):
            s[i][0], s[i][1], s[i][2], s[i][3] = s[i][c[0]], s[i][c[1]], s[i][c[2]], s[i][c[3]]
    def shift_rows(self, s):
        bs = matrix2bytes(s)
        for i in range(4):
            for j in range(4):
                s[i][j] = bs[self.order[i * 4 + j]]
    def inv_shift_rows(self, s):
        order = bytearray(16)
        for i in range(16):
            order[self.order[i]] = i
        bs = matrix2bytes(s)
        for i in range(4):
            for j in range(4):
                s[i][j] = bs[order[i * 4 + j]]
    def sub_bytes(self, s):
        for i in range(4):
            for j in range(4):
                s[i][j] = self.s_box[s[i][j]]
        s[0], s[1], s[2], s[3] = s[self.con2[0]], s[self.con2[1]], s[self.con2[2]], s[self.con2[3]]
    def inv_sub_bytes(self, s):
        for i in range(4):
            for j in range(4):
                s[i][j] = self.inv_s_box[s[i][j]]
        s[0], s[1], s[2], s[3] = s[self.con[0]], s[self.con[1]], s[self.con[2]], s[self.con[3]]
def leftCircularShift(k, bits):
    bits = bits % 32
    k = k % (2 ** 32)
    upper = (k << bits) % (2 ** 32)
    result = upper | (k >> (32 - (bits)))
    return (result)
def blockDivide(block, chunks):
    result = []
    size = len(block) // chunks
    for i in range(0, chunks):
        result.append(int.from_bytes(block[i * size:(i + 1) * size], byteorder="little"))
    return (result)
def F(X, Y, Z):
    return ((X & Y) | ((~X) & Z))
def G(X, Y, Z):
    return ((X & Z) | (Y & (~Z)))
def H(X, Y, Z):
    return (X ^ Y ^ Z)
def I(X, Y, Z):
    return (Y ^ (X | (~Z))) & 0xffffffff
def FF(a, b, c, d, M, s, t):
    result = b + leftCircularShift((a + F(b, c, d) + M + t), s)
    return (result)
def GG(a, b, c, d, M, s, t):
    result = b + leftCircularShift((a + G(b, c, d) + M + t), s)
    return (result)
def HH(a, b, c, d, M, s, t):
    result = b + leftCircularShift((a + H(b, c, d) + M + t), s)
    return (result)
def II(a, b, c, d, M, s, t):
    result = b + leftCircularShift((a + I(b, c, d) + M + t), s)
    return (result)
def sum_md5(data):
    check_sum = 0x20220420
    for i in range(12):
        if i % 2 == 0:
            temp = (check_sum >> 3) ^ check_sum
            check_sum = data[i] ^ (check_sum << 7)
        else:
            temp = (check_sum >> 5) ^ check_sum
            check_sum = data[i] | (check_sum << 11)
            check_sum ^= 0xffffffff
        check_sum ^= temp
        check_sum &= 0xffffffff
    check_sum |= 4
    check_sum ^= 0x1000000
    return check_sum
SV2 = [0xa7aefe20, 0x7149f1d6, 0x47e4ca07, 0xe9b58f67, 0x93b924de, 0xc614d0f5, 0x38afe0ef, 0xb2bbad73,
       0xe24444c3, 0x9d3aec9b, 0xdf7b37e4, 0xd8b16d40, 0xf8ac31b8, 0x76b9a90b, 0x31d833ee, 0x953fce64,
       0x353595a4, 0x4609c13b, 0x36925008, 0x8c6d0925, 0x5df5c177, 0x1cfbf52b, 0x8a4fa7f0, 0x114ca35e,
       0x8193f984, 0x7a7a8733, 0x316ab4d5, 0x3c20cfc9, 0xa6d84453, 0x3a18500c, 0x798ec47a, 0x97a76b28,
       0x66c4ff96, 0x51716443, 0xdd2fc3b, 0xb5696da7, 0xbbeb3ac5, 0x5c53d204, 0xd32608ce, 0x7279b9ec,
       0xf4188ecf, 0xf7d793db, 0x332cc491, 0xab76ae15, 0x9bebe727, 0x18a01384, 0x5be9f8a7, 0x5f90a754,
       0x39b663c0, 0x36673c83, 0x7c92f514, 0x9d7d94d7, 0xe2e8d9aa, 0x5f7e9ea9, 0x7abd4551, 0x569e05da,
       0x40a25632, 0x3df5a9a5, 0xbab37d80, 0x454286dc, 0x3f5d4e78, 0x3d7b75d, 0xb1fe4af7, 0xa5ab26a3]
def md5sum_v3(msg, count_v2, orders, count_v1, n=0):
    count = count_v2 & 0xff
    sv = [0] * 64
    for i in range(64):
        sv[i] = ror32(SV2[i], count_v1)
    start = [
        ror32(0x79e0f2fb, count),
        ror32(0xc8b52570, count),
        ror32(0xebc2f8cd, count),
        ror32(0x7c104d93, count)
    ]
    count = (count_v2 + 6) & 0xff
    end = [
        ror32(0x19be4866, count),
        ror32(0xe85986b4, count),
        ror32(0xe19b326e, count),
        ror32(0x71d1d7d4, count)
    ]
    A = start[0]
    B = start[1]
    C = start[2]
    D = start[3]
    a = A
    b = B
    c = C
    d = D
    block = msg[:64]
    M = blockDivide(block, 16)
    order1 = orders[:16]
    order2 = orders[16:32]
    order3 = orders[32:48]
    order4 = orders[48:]
    a = FF(a, b, c, d, M[order1[0]], 7, sv[0])
    d = FF(d, a, b, c, M[order1[1]], 12, sv[1])
    c = FF(c, d, a, b, M[order1[2]], 17, sv[2])
    b = FF(b, c, d, a, M[order1[3]], 22, sv[3])
    a = FF(a, b, c, d, M[order1[4]], 7, sv[4])
    d = FF(d, a, b, c, M[order1[5]], 12, sv[5])
    c = FF(c, d, a, b, M[order1[6]], 17, sv[6])
    b = FF(b, c, d, a, M[order1[7]], 22, sv[7])
    a = FF(a, b, c, d, M[order1[8]], 7, sv[8])
    d = FF(d, a, b, c, M[order1[9]], 12, sv[9])
    c = FF(c, d, a, b, M[order1[10]], 17, sv[10])
    b = FF(b, c, d, a, M[order1[11]], 22, sv[11])
    a = FF(a, b, c, d, M[order1[12]], 7, sv[12])
    d = FF(d, a, b, c, M[order1[13]], 12, sv[13])
    c = FF(c, d, a, b, M[order1[14]], 17, sv[14])
    b = FF(b, c, d, a, M[order1[15]], 22, sv[15])
    a = GG(a, b, c, d, M[order2[0]], 5, sv[16])
    d = GG(d, a, b, c, M[order2[1]], 9, sv[17])
    c = GG(c, d, a, b, M[order2[2]], 14, sv[18])
    b = GG(b, c, d, a, M[order2[3]], 20, sv[19])
    a = GG(a, b, c, d, M[order2[4]], 5, sv[20])
    d = GG(d, a, b, c, M[order2[5]], 9, sv[21])
    c = GG(c, d, a, b, M[order2[6]], 14, sv[22])
    b = GG(b, c, d, a, M[order2[7]], 20, sv[23])
    a = GG(a, b, c, d, M[order2[8]], 5, sv[24])
    d = GG(d, a, b, c, M[order2[9]], 9, sv[25])
    c = GG(c, d, a, b, M[order2[10]], 14, sv[26])
    b = GG(b, c, d, a, M[order2[11]], 20, sv[27])
    a = GG(a, b, c, d, M[order2[12]], 5, sv[28])
    d = GG(d, a, b, c, M[order2[13]], 9, sv[29])
    c = GG(c, d, a, b, M[order2[14]], 14, sv[30])
    b = GG(b, c, d, a, M[order2[15]], 20, sv[31])
    a = HH(a, b, c, d, M[order3[0]], 4, sv[32])
    d = HH(d, a, b, c, M[order3[1]], 11, sv[33])
    c = HH(c, d, a, b, M[order3[2]], 16, sv[34])
    b = HH(b, c, d, a, M[order3[3]], 23, sv[35])
    a = HH(a, b, c, d, M[order3[4]], 4, sv[36])
    d = HH(d, a, b, c, M[order3[5]], 11, sv[37])
    c = HH(c, d, a, b, M[order3[6]], 16, sv[38])
    b = HH(b, c, d, a, M[order3[7]], 23, sv[39])
    a = HH(a, b, c, d, M[order3[8]], 4, sv[40])
    d = HH(d, a, b, c, M[order3[9]], 11, sv[41])
    c = HH(c, d, a, b, M[order3[10]], 16, sv[42])
    b = HH(b, c, d, a, M[order3[11]], 23, sv[43])
    a = HH(a, b, c, d, M[order3[12]], 4, sv[44])
    d = HH(d, a, b, c, M[order3[13]], 11, sv[45])
    c = HH(c, d, a, b, M[order3[14]], 16, sv[46])
    b = HH(b, c, d, a, M[order3[15]], 23, sv[47])
    a = II(a, b, c, d, M[order4[0]], 6, sv[48])
    d = II(d, a, b, c, M[order4[1]], 10, sv[49])
    c = II(c, d, a, b, M[order4[2]], 15, sv[50])
    b = II(b, c, d, a, M[order4[3]], 21, sv[51])
    a = II(a, b, c, d, M[order4[4]], 6, sv[52])
    d = II(d, a, b, c, M[order4[5]], 10, sv[53])
    c = II(c, d, a, b, M[order4[6]], 15, sv[54])
    b = II(b, c, d, a, M[order4[7]], 21, sv[55])
    a = II(a, b, c, d, M[order4[8]], 6, sv[56])
    d = II(d, a, b, c, M[order4[9]], 10, sv[57])
    c = II(c, d, a, b, M[order4[10]], 15, sv[58])
    b = II(b, c, d, a, M[order4[11]], 21, sv[59])
    a = II(a, b, c, d, M[order4[12]], 6, sv[60])
    d = II(d, a, b, c, M[order4[13]], 10, sv[61])
    c = II(c, d, a, b, M[order4[14]], 15, sv[62])
    b = II(b, c, d, a, M[order4[15]], 21, sv[63])
    A = (A + a) % (2 ** 32) ^ end[0]
    B = (B + b) % (2 ** 32) ^ end[1]
    C = (C + c) % (2 ** 32) ^ end[2]
    D = (D + d) % (2 ** 32) ^ end[3]
    result = bytearray(
        A.to_bytes(4, "little") + B.to_bytes(4, "little") + C.to_bytes(4, "little") + D.to_bytes(4, "little"))
    result += sum_md5(result).to_bytes(4, "little")
    return result
def bxor(b1, b2):
    b3 = bytearray(len(b1))
    for i in range(len(b1)):
        b3[i] = b1[i] ^ b2[i]
    return b3
def get_iv(iv, data):
    for i in range(len(data)):
        if i & 1 == 0:
            iv = (iv >> 4) ^ iv ^ (iv << 6) ^ data[i]
        else:
            iv = ~((iv >> 7) ^ iv ^ (data[i] | iv << 12))
        iv = iv & 0xffffffff
    return iv
def hash_f13(query_sm3, body_md5_bytes, ts_bytes, khronos):
    iv = get_iv(0x20230928, query_sm3)
    iv = get_iv(iv, body_md5_bytes)
    iv = get_iv(iv, ts_bytes)
    iv_v0 = ((iv & 15) * 171) >> 9
    branch = (iv & 15) - ((iv_v0 * 3) & 0xff)
    if branch == 0:
        return branch_0(iv_v0, khronos, query_sm3, body_md5_bytes, ts_bytes)
    elif branch == 1:
        return branch_1(iv_v0, khronos, query_sm3, body_md5_bytes, ts_bytes)
    elif branch == 2:
        return branch_2(iv, khronos, query_sm3, body_md5_bytes, ts_bytes)
    else:
        raise Exception("no branch: " + str(branch))
def branch_0(iv_v0, khronos, query_sm3, body_md5_bytes, ts_bytes):
    tt01 = [0xc4a78580, 0xb3c0fd39, 0xc58c5686, 0xc9aa3ba7, 0xf5a7adf2, 0x963c2ed1]
    iv_v1 = tt01[iv_v0]
    count_v1 = (iv_v1 + khronos + 1) & 0xff
    count_v2 = (iv_v1 + khronos) & 0xffffffff
    tt02 = [0xebb64faf, 0x7aadcc2, 0xcf3187bf, 0xe01138ff, 0x6d0bfcff, 0x5a30a3be, 0xb41ad638, 0x34180eb8, 0xf233eb6f,
            0xb1a584cc, 0xccc30dc7, 0x47d1db51, 0xd55653de, 0x70a84fa1, 0x57473c12, 0xf76f0288, 0x2c077f0a, 0xda0dcad0,
            0xfbb86f6c, 0xfdc4cf00, 0x688a020d, 0xe676c6a6, 0x8cd6338b, 0x1a3c8d0e, 0xcce8b06b, 0x6ad0ed0b, 0xa0522717,
            0xdc71ac83, 0x2285db71, 0xd5b4dda6, 0x736f8650, 0x6560306c, 0x617ce2a6, 0xe423417e, 0xa40e143, 0x544e4032,
            0x88dffb2a, 0x716c1ae0, 0x4c467a88, 0x5b23bb3, 0xe1d0b866, 0xbaa3dcb8, 0xae3374d3, 0xc3381a50, 0x1702f75b,
            0xfe6da368, 0xf0b4cf48, 0x4e0ffbb8, 0x72aad10d, 0x26c53a3d, 0xf2bce0f6, 0xb4557581, 0x4a257fdd, 0x8c3182a2,
            0xab0b3b86, 0x3d5dfb14, 0x4f103634, 0xd37b52d7, 0x444eff16, 0xeb0a33d1, 0x6ca86f6e, 0x284ba7, 0x8387cfa,
            0x5fb37586]
    tt03 = [0] * 64
    for i in range(0, 64):
        tt03[i] = ror32(tt02[i], count_v1) & 0xffffffff
    n0 = (count_v2 + 2) & 7
    pad = bytearray(4)
    seed = bytes([0xfa, 0x45, 0x61, 0xd7])
    for i in range(4):
        v = int.from_bytes(bytes([seed[i], seed[i]]), 'little')
        v = v >> n0
        pad[i] = v & 0xff
    count_v2 = count_v2 & 0xff
    init_value = [
        ror32(0x7aba4fc8, count_v2), ror32(0x67166507, count_v2),
        ror32(0x6403fa00, count_v2), ror32(0x340f512f, count_v2),
        ror32(984304912, count_v2), ror32(3005047866, count_v2),
        ror32(2874125293, count_v2), ror32(2152413264, count_v2)
    ]
    data = query_sm3 + body_md5_bytes + ts_bytes + pad + bytes.fromhex(' 00 00 00 00 00 00 01 a0')
    di = [0] * (len(data) // 4)
    for i in range(len(data) // 4):
        di[i] = int.from_bytes(data[i * 4:i * 4 + 4], "big")
    di0 = di[0]
    for i in range(112):
        di1, di14 = di[i + 1], di[i + 14]
        r_di1 = rol(di1, 14) ^ rol(di1, 25) ^ (di1 >> 3)
        r_di2 = rol(di14, 13) ^ rol(di14, 15) ^ (di14 >> 10)
        di0 = di0 + di[i + 9] + r_di1 + r_di2
        di.append(di0 & 0xffffffff)
        di0 = di1
    if iv_v0 == 5:
        v_j = branch0_xor(init_value, iv_v1, di, tt03, 100, 2, 0, 3, 5, 4, 6, 7, 2, 1, 5)
    elif iv_v0 == 4:
        v_j = branch0_xor(init_value, iv_v1, di, tt03, 96, 0, 5, 6, 7, 3, 1, 2, 5, 4, 4)
    elif iv_v0 == 3:
        v_j = branch0_xor(init_value, iv_v1, di, tt03, 99, 3, 6, 2, 4, 5, 1, 0, 0, 7, 6)
    elif iv_v0 == 2:
        v_j = branch0_xor(init_value, iv_v1, di, tt03, 96, 7, 6, 2, 1, 4, 0, 5, 4, 3, 5)
    elif iv_v0 == 1:
        v_j = branch0_xor(init_value, iv_v1, di, tt03, 96, 0, 6, 7, 5, 3, 2, 1, 5, 4, 4)
    elif iv_v0 == 0:
        v_j = branch0_xor(init_value, iv_v1, di, tt03, 101, 5, 7, 6, 3, 2, 1, 0, 5, 4, 3)
    ret = bytearray(32)
    for i in range(8):
        ret[i * 4:i * 4 + 4] = ((v_j[i] + init_value[i]) & 0xffffffff).to_bytes(4, 'big')
    ret = bxor(ret[:16], ret[16:])
    sum = sum_md5(ret)
    ret += sum.to_bytes(4, "little")
    return ret
def swap_v0(src, src_xor, tt2, table_f, order1, typ=None):
    da0 = [0] * 8
    ha0 = src_xor[:]
    for i in range(8):
        da0[i] = src[order1[i]] ^ src_xor[i]
    for round in range(10):
        rr_0 = r00(ha0[0], ha0[1], ha0[2], ha0[3], ha0[4], ha0[5], ha0[6], ha0[7], 0, table_f)
        rr_1 = r00(ha0[1], ha0[2], ha0[3], ha0[4], ha0[5], ha0[6], ha0[7], ha0[0], 0, table_f)
        rr_2 = r00(ha0[2], ha0[3], ha0[4], ha0[5], ha0[6], ha0[7], ha0[0], ha0[1], 0, table_f)
        rr_3 = r00(ha0[3], ha0[4], ha0[5], ha0[6], ha0[7], ha0[0], ha0[1], ha0[2], 0, table_f)
        rr_4 = r00(ha0[4], ha0[5], ha0[6], ha0[7], ha0[0], ha0[1], ha0[2], ha0[3], 0, table_f)
        rr_5 = r00(ha0[5], ha0[6], ha0[7], ha0[0], ha0[1], ha0[2], ha0[3], ha0[4], 0, table_f)
        rr_6 = r00(ha0[6], ha0[7], ha0[0], ha0[1], ha0[2], ha0[3], ha0[4], ha0[5], 0, table_f)
        rr_7 = r00(ha0[7], ha0[0], ha0[1], ha0[2], ha0[3], ha0[4], ha0[5], ha0[6], 0, table_f)
        rr_7 = rr_7 ^ tt2[round + 1]
        d0, d1, d2, d3, d4, d5, d6, d7 = da0[0], da0[1], da0[2], da0[3], da0[4], da0[5], da0[6], da0[7]
        da0[0] = r00(d0, d1, d2, d3, d4, d5, d6, d7, rr_0, table_f)
        da0[1] = r00(d1, d2, d3, d4, d5, d6, d7, d0, rr_1, table_f)
        da0[2] = r00(d2, d3, d4, d5, d6, d7, d0, d1, rr_2, table_f)
        da0[3] = r00(d3, d4, d5, d6, d7, d0, d1, d2, rr_3, table_f)
        da0[4] = r00(d4, d5, d6, d7, d0, d1, d2, d3, rr_4, table_f)
        da0[5] = r00(d5, d6, d7, d0, d1, d2, d3, d4, rr_5, table_f)
        da0[6] = r00(d6, d7, d0, d1, d2, d3, d4, d5, rr_6, table_f)
        da0[7] = r00(d7, d0, d1, d2, d3, d4, d5, d6, rr_7, table_f)
        ha0[0], ha0[1], ha0[2], ha0[3], ha0[4], ha0[5], ha0[6], ha0[7] = rr_0, rr_1, rr_2, rr_3, rr_4, rr_5, rr_6, rr_7
    if typ is None:
        src[0] = da0[0] ^ src_xor[0] ^ src[0]
        src[1] = da0[7] ^ src_xor[1] ^ src[1]
        src[2] = da0[6] ^ src_xor[2] ^ src[2]
        src[3] = da0[5] ^ src_xor[3] ^ src[3]
        src[4] = da0[4] ^ src_xor[4] ^ src[4]
        src[5] = da0[3] ^ src_xor[5] ^ src[5]
        src[6] = da0[2] ^ src_xor[6] ^ src[6]
        src[7] = da0[1] ^ src_xor[7] ^ src[7]
    else:
        src[0] = da0[7] ^ typ[1]
        src[1] = da0[6] ^ typ[2]
        src[2] = da0[5] ^ typ[3]
        src[3] = da0[4] ^ typ[4]
        src[4] = da0[3] ^ typ[5]
        src[5] = da0[2] ^ typ[6]
        src[6] = da0[1] ^ typ[7] ^ src[7]
        src[7] = da0[0] ^ typ[0]
    return src
def branch_1(iv_v0, khronos, query_sm3, body_md5_bytes, ts_bytes):
    tt1 = [0x808a9c79, 0xf079807e, 0xbadf79c5, 0xa785d3ff, 0x82d8438c]
    iv_v1 = tt1[iv_v0]
    c_v1 = (iv_v1 + khronos) & 0xff
    c_v1 = ror(khronos, c_v1)
    orders = bytes.fromhex('''05 07 01 02 04 00 06 03 00 05 02 04 01 03 07 06
    05 07 02 04 01 06 03 00 03 00 02 04 06 07 01 05
    04 05 00 03 06 02 01 07 00 00 00 00 00 00 00 00''')
    order1 = orders[iv_v0 * 8:iv_v0 * 8 + 8]
    iv_v1 = (iv_v1 + khronos + 1) & 63
    tt1 = [0x87aeea5dab37cd6b, 0x7ff48becb4f54087, 0xb0724c06706bbd5d, 0x1fe5dfb1143e328d,
           0x1a2331d00af4f1f2, 0xcaff7131bb1e71ba, 0x33385e1042752218, 0xff01ed65d4a441fb,
           0xadb1ec8828c80e8, 0x62475d12f4e06fe7, 0xbd0b238da4fe72]
    tt2 = [0] * 11
    for i in range(0, 11):
        tt2[i] = ror(tt1[i], iv_v1)
    to_sign = bytearray(query_sm3 + body_md5_bytes + ts_bytes + bytes([0x80, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
    src = [0] * (len(to_sign) // 8)
    for i in range(len(to_sign) // 8):
        src[i] = int.from_bytes(to_sign[i * 8:i * 8 + 8], 'big')
    src_xor = [c_v1, c_v1, c_v1, c_v1, c_v1, c_v1, c_v1, c_v1]
    table_f = get_branch_1_table_f(iv_v0)
    swap = swap_v0(src, src_xor, tt2, table_f, order1)
    data = [0] * 8
    data[7] = 416
    src_xor = [swap[4], swap[3], swap[2], swap[1], swap[0], swap[7], swap[6], swap[5]]
    swap = swap_v0(data, src_xor, tt2, table_f, order1, swap)
    ret = bytearray(32)
    n = 0
    for i in range(7, -1, -1):
        pp = swap[i].to_bytes(8, "little")
        ret[n + 0], ret[n + 1], ret[n + 2], ret[n + 3] = pp[1], pp[3], pp[5], pp[6]
        n += 4
    for i in range(16):
        ret[i] ^= ret[i + 16]
    ret = ret[:16]
    sum = sum_md5(ret)
    ret += sum.to_bytes(4, "little")
    return ret
def r00(r0, r1, r2, r3, r4, r5, r6, r7, tt, table_f, v=0):
    x = table_f(8 * (r0 >> 56))
    r1 = (r1 >> 45) & 2040
    if tt > 0:
        x = x ^ tt
    x = x ^ table_f(r1 + 2048)
    r2 = (r2 >> 37) & 2040
    x = x ^ table_f(r2 + 4096)
    r3 = (r3 >> 29) & 2040
    x = x ^ table_f(r3 + 6144)
    r4 = (r4 >> 21) & 2040
    x = x ^ table_f(r4 + 8192)
    r5 = (r5 >> 13) & 2040
    x = x ^ table_f(r5 + 10240)
    r6 = (r6 >> 8) & 255
    x = x ^ table_f(8 * r6 + 12288)
    r7 = r7 & 255
    x = x ^ table_f(8 * r7 + 14336)
    return x
branch_2_orders = bytes.fromhex('''
    0f 07 04 00 09 08 03 0a 06 0b 05 0d 0e 01 0c 02 0f 05 08 0c 00 09 02 01 03 07 0e 06 0b 0a 0d 04 06 05 00 07 0c 00 0a 04 08 0f 01 0b 0d 09 02 0e 06 0b 02 05 04 03 08 01 01 07 0a 00 0d 0c 09 0e
    0d 07 0e 0f 0b 02 08 03 0c 05 09 01 00 04 06 0a 0d 09 02 06 0f 0b 0a 04 08 07 00 0c 05 03 01 0e 0c 09 0f 07 06 0f 03 0e 02 0d 04 05 01 0b 0a 00 0c 05 0a 09 0e 08 02 04 04 07 03 0f 01 06 0b 00
    0b 0f 04 08 02 0a 07 00 09 0d 06 01 0e 03 05 0c 0b 06 0a 05 08 02 0c 03 07 0f 0e 09 0d 00 01 04 09 06 08 0f 05 08 00 04 0a 0b 03 0d 01 02 0c 0e 09 0d 0c 06 04 07 0a 03 03 0f 00 08 01 05 02 0e
    01 00 0d 0f 09 0a 0b 0e 04 02 08 07 03 06 0c 05 01 08 0a 0c 0f 09 05 06 0b 00 03 04 02 0e 07 0d 04 08 0f 00 0c 0f 0e 0d 0a 01 06 02 07 09 05 03 04 02 05 08 0d 0b 0a 06 06 00 0e 0f 07 0c 09 03
    0a 08 04 0f 00 0b 01 06 0d 0c 07 09 03 0e 05 02 0a 07 0b 05 0f 00 02 0e 01 08 03 0d 0c 06 09 04 0d 07 0f 08 05 0f 06 04 0b 0a 0e 0c 09 00 02 03 0d 0c 02 07 04 01 0b 0e 0e 08 06 0f 09 05 00 03
    ''')
def branch_2(iv, khronos, query_sm3, body_md5_bytes, ts_bytes):
    n0 = (iv & 15 - 2) * 86
    iv_v0 = (n0 >> 15 & 0xff) + (n0 >> 8 & 0xff)
    t001 = [0x8980f29b, 0xeb549c7f, 0xb08726db, 0xd40cb5e6, 0xe8f559e4]
    n1 = t001[iv_v0]
    count_v1 = (n1 + khronos + 1) & 0xff
    count_v2 = (n1 + khronos) & 0xffffffff
    n0 = (count_v2 + 5) & 7
    pad = bytearray(8)
    seed = bytes([0x84, 0x96, 0x77, 0x9d, 0xd4, 0x15, 0x0b, 0xf8])
    for i in range(8):
        v = int.from_bytes(bytes([seed[i], seed[i]]), 'little')
        v = v >> n0
        pad[i] = v & 0xff
    data = query_sm3 + body_md5_bytes + ts_bytes + pad + bytes.fromhex('a0 01 00 00')
    idx = iv_v0 << 6
    ret = md5sum_v3(data, count_v2, branch_2_orders[idx:idx + 64], count_v1)
    return ret
def branch0_xor(data, base, di, tt03, round, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10):
    d = data[:]
    for i in range(round):
        offset = base + i
        n0 = di[offset & 127]
        n1 = ((d[x3] ^ d[x4]) & d[x1]) ^ d[x3]
        n2 = rol(d[x1], 26) ^ rol(d[x1], 21) ^ rol(d[x1], 7)
        offset = offset & 63
        n3 = tt03[offset]
        n4 = (n0 + n1 + n2 + n3 + d[x5]) & 0xffffffff
        n5 = rol(d[x2], 30) ^ rol(d[x2], 19) ^ rol(d[x2], 10)
        n6 = (d[x2] & d[x6]) | ((d[x2] | d[x6]) & d[x7])
        n7 = n5 + n6
        o = d[x9]
        d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7] = d[7], d[0], d[1], d[2], d[3], d[4], d[5], d[6]
        d[x10] = (n7 + n4) & 0xffffffff
        d[x8] = (o + n4) & 0xffffffff
    return d
branch_1_table = None
def get_branch_1_table_f(iv_v0):
    global branch_1_table
    if branch_1_table is None:
        branch_1_table = _branch_one_bytes()
    table = branch_1_table[iv_v0 << 14:]
    def table_f(x):
        return int.from_bytes(table[x:x + 8], 'little')
    return table_f
def _varint(value: int) -> bytes:
    value = int(value)
    if value < 0:
        value &= (1 << 64) - 1
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)
def _sint(value: int, bits: int) -> int:
    value = int(value)
    return (value << 1) if value >= 0 else (value << 1) ^ (~0)
def _proto_field(field: int, value: Any, kind: str) -> bytes:
    if value in (None, "", b"", 0, 0.0, False):
        return b""
    if kind == "sint32":
        return _varint((field << 3) | 0) + _varint(_sint(int(value), 32))
    if kind == "sint64":
        return _varint((field << 3) | 0) + _varint(_sint(int(value), 64))
    if kind == "float":
        return _varint((field << 3) | 5) + struct.pack("<f", float(value))
    if kind == "bytes":
        raw = bytes(value)
    elif kind == "string":
        raw = str(value).encode("utf-8")
    elif kind == "message":
        raw = bytes(value)
    else:
        raise ValueError(f"unknown protobuf field kind: {kind}")
    return _varint((field << 3) | 2) + _varint(len(raw)) + raw
def _proto(fields: list[tuple[int, Any, str]]) -> bytes:
    return b"".join(_proto_field(field, value, kind) for field, value, kind in fields)
def _encode_request() -> bytes:
    return _proto([
        (1, 111, "sint32"),
        (2, 10, "sint32"),
        (3, 694367, "sint32"),
        (5, 586952199, "sint32"),
    ])
def _encode_device(device: Mapping[str, Any]) -> bytes:
    fields = [
        (1, device.get("d1"), "sint32"), (2, device.get("collect_stat"), "sint32"),
        (3, device.get("aid"), "string"), (4, device.get("device_id"), "string"),
        (5, device.get("sec_device_token"), "string"), (6, device.get("app_version"), "string"),
        (7, device.get("battery"), "sint32"), (8, device.get("battery2"), "sint32"),
        (9, device.get("battery_health"), "sint32"), (10, device.get("battery_changed"), "sint32"),
        (11, device.get("network"), "string"), (12, device.get("tz"), "string"),
        (13, device.get("lan"), "string"), (14, device.get("cpu"), "sint32"),
        (15, device.get("resolution"), "string"), (16, device.get("sdcard"), "float"),
        (17, device.get("sdcard_used"), "float"), (18, device.get("memory"), "float"),
        (19, device.get("memory2"), "float"), (20, device.get("data"), "float"),
        (21, device.get("data_used"), "float"), (22, device.get("os_version"), "string"),
        (23, device.get("brightness"), "sint32"), (24, device.get("volume"), "sint32"),
        (25, device.get("ts"), "sint64"), (26, device.get("ts2"), "sint64"),
        (27, device.get("ts3"), "sint64"), (28, device.get("ts4"), "sint64"),
        (29, device.get("usb"), "sint32"), (30, device.get("hw_version"), "string"),
        (31, device.get("brand"), "string"), (32, device.get("board"), "string"),
        (33, device.get("product_name"), "string"), (34, device.get("product_device"), "string"),
        (35, device.get("product_manufacturer"), "string"), (36, device.get("hardware"), "string"),
        (38, device.get("unknown38"), "sint32"), (40, device.get("unknown40"), "sint32"),
    ]
    return _proto(fields)
def _encode_env(env: Mapping[str, Any]) -> bytes:
    fields = [
        (1, env.get("launch_time"), "sint32"), (2, env.get("unknown2"), "sint32"),
        (3, env.get("unknown3"), "sint32"), (5, env.get("unknown5"), "sint32"),
        (6, env.get("version"), "string"), (7, env.get("pid"), "sint32"),
        (12, _encode_device(env.get("device") or {}), "message"),
        (13, _proto([
            (1, (env.get("report") or {}).get("time"), "sint64"),
            (2, (env.get("report") or {}).get("state"), "sint32"),
            (4, (env.get("report") or {}).get("code"), "sint32"),
            (5, (env.get("report") or {}).get("times"), "sint32"),
            (6, (env.get("report") or {}).get("unknown6"), "sint32"),
        ]), "message"),
        (14, env.get("app_version"), "string"),
        (15, env.get("unknown15"), "sint32"), (16, env.get("unknown16"), "sint32"),
        (18, env.get("unknown18"), "sint32"), (19, env.get("unknown19"), "sint32"),
        (20, env.get("unknown20"), "sint32"), (21, env.get("unknown21"), "sint32"),
    ]
    return _proto(fields)
def _encode_medusa(values: Mapping[str, Any]) -> bytes:
    return _proto([
        (1, values.get("magic"), "bytes"), (2, values.get("version"), "sint32"),
        (3, values.get("rand"), "sint32"), (4, values.get("ms_app_id"), "string"),
        (5, values.get("device_id"), "string"), (6, values.get("license_id"), "string"),
        (7, values.get("app_version"), "string"), (8, values.get("sdk_version_str"), "string"),
        (9, values.get("sdk_version"), "sint32"), (10, values.get("xg_seed_bytes"), "bytes"),
        (12, values.get("time"), "sint32"), (13, values.get("query_body_ts_hash"), "bytes"),
        (14, values.get("query_sm3"), "bytes"), (15, _encode_request(), "message"),
        (16, values.get("sec_device_token"), "string"), (17, values.get("time2"), "sint32"),
        (18, values.get("lanusk_hash"), "bytes"), (19, values.get("query_body_hash_sm3"), "bytes"),
        (20, values.get("psk_version"), "string"), (21, values.get("call_type"), "sint32"),
        (23, _encode_env(values.get("env") or {}), "message"),
        (24, values.get("unknown24"), "string"), (26, values.get("original"), "string"),
    ])
def _json_body_md5(data: Any, data_type: str | None = None) -> str:
    if not data:
        return ""
    if isinstance(data, str):
        raw = data.encode("utf-8")
    elif isinstance(data, bytes):
        raw = data
    elif data_type == "application/json; charset=UTF-8":
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    else:
        raw = urlencode(data).encode("utf-8")
    return hashlib.md5(raw).hexdigest().upper()
def _url_encode(value: Mapping[str, Any]) -> str:
    return urlencode(value).replace("+", "%20").replace("%2A", "*")
def _get_params_encrypturl(url: str, params: Mapping[str, Any], devices: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    result = dict(params)
    for key, value in devices.items():
        if key in result:
            result[key] = value
        elif key == "device_id" and "did" in result:
            result["did"] = value
    result["ts"] = int(time.time())
    result["_rticket"] = int(time.time() * 1000)
    return url.split("?", 1)[0] + "?" + _url_encode(result), result
def _xg_rc4(data: bytes, key: bytes) -> bytearray:
    table = list(range(256))
    j = 0
    for i in range(256):
        j = (j + table[i] + key[i % len(key)]) % 256
        table[i] = table[j]
    i = j = 0
    result = bytearray(len(data))
    for index, value in enumerate(data):
        i = (i + 1) & 0xFF
        x = table[i]
        j = (j + x) & 0xFF
        y = table[j]
        table[i] = y
        result[index] = value ^ table[(y + y) & 0xFF]
    return result
def _reverse_bits(value: int) -> int:
    return int(f"{value:08b}"[::-1], 2)
def _encrypt_gorgon(body: Any, query: str, khronos: int, xg_rand: int, data_type: str) -> str:
    body_md5 = _json_body_md5(body, data_type).lower() if body else ""
    data = bytearray(hashlib.md5(query.encode()).digest()[:4])
    data += bytes.fromhex(body_md5)[:4] if body_md5 else b"\0\0\0\0"
    data += b"\0\0\0\0" + (67503104).to_bytes(4, "little") + khronos.to_bytes(4, "big")
    key = bytes((0x4A, 320 & 0xFF, 0x16, (xg_rand >> 8) & 0xFF, 0x47, 0x6C, 1, xg_rand & 0xFF))
    result = _xg_rc4(data, key)
    for index, value in enumerate(result):
        value = ((value >> 4) | (value << 4)) & 0xFF
        following = result[index + 1] if index + 1 < len(result) else result[0]
        result[index] = (~(_reverse_bits(following ^ value) ^ 20)) & 0xFF
    return (b"\x84\x04" + xg_rand.to_bytes(2, "little") + (320).to_bytes(2, "little") + result).hex()
def _ror64(value: int, count: int) -> int:
    count %= 64
    return ((value >> count) | (value << (64 - count))) & 0xFFFFFFFFFFFFFFFF
def _encrypt_helios(khronos: int, rand_value: int = 0) -> str:
    value = rand_value or random.randint(0, 0xFFFFFFFF)
    seed = value.to_bytes(4, "little") + b"8662"
    digest = hashlib.md5(seed).digest()
    keys = b"".join(f"{item:02x}".encode() for item in digest)
    table = [int.from_bytes(keys[:8], "little")]
    words = [int.from_bytes(keys[i:i + 8], "little") for i in range(0, 32, 8)]
    first, second = words[0], words[1]
    words = words[2:]
    for index in range(0x22):
        value2 = _ror64(second, 8)
        value2 = (value2 + first) & 0xFFFFFFFFFFFFFFFF
        value2 = (value2 ^ index) & 0xFFFFFFFFFFFFFFFF
        words.append(value2)
        value2 ^= _ror64(first, 61)
        value2 &= 0xFFFFFFFFFFFFFFFF
        table.append(value2)
        first, second = value2, words.pop(0)
    raw = (f"{khronos}-1588093228-8662").encode()
    pad = 16 - len(raw) % 16
    raw += bytes([pad]) * pad
    output = bytearray()
    for offset in range(0, len(raw), 16):
        left = int.from_bytes(raw[offset:offset + 8], "little")
        right = int.from_bytes(raw[offset + 8:offset + 16], "little")
        for index in range(0x22):
            right = (table[index] ^ (left + _ror64(right, 8))) & 0xFFFFFFFFFFFFFFFF
            left = (right ^ _ror64(left, 61)) & 0xFFFFFFFFFFFFFFFF
        output += left.to_bytes(8, "little") + right.to_bytes(8, "little")
    return base64.b64encode(value.to_bytes(4, "little") + output).decode()
def _gen_medusa_proto(url: str, url_params: Mapping[str, Any], devices: Mapping[str, Any], data: Any, khronos: int, data_type: str) -> tuple[bytes, bytes, bytes]:
    body_md5 = _json_body_md5(data, data_type).lower() if data else ""
    body_md5_bytes = bytes.fromhex(body_md5) if body_md5 else bytes(16)
    ts_bytes = khronos.to_bytes(4, "little")
    query = url.split("?", 1)[1] if "?" in url else ""
    query_sm3 = SM3(query).digest()
    query_body_hash = SM3(query.encode() + body_md5_bytes + b"none").digest()
    device_id = str(devices.get("device_id", url_params.get("device_id", url_params.get("did", ""))))
    version_name = str(devices.get("version_name", url_params.get("version_name", APP_VERSION_NAME)))
    device_model = str(devices.get("device_model", url_params.get("device_type", "")))
    brand = str(devices.get("device_brand", url_params.get("device_brand", "")))
    sec_device_token = str(devices.get("sec_device_token") or "")
    device_sec_device_token = str(devices.get("device_sec_device_token") or "")
    proto_rand = random.randint(0, 0xFFFFFFFF)
    launch_time = random.randint(100, 120)
    process_id = random.randint(10001, 12000)
    report_ts = 1728388016635
    report_time = int(time.time())
    device = {
        "d1": 1, "collect_stat": 2, "aid": "8662", "device_id": device_id,
        "sec_device_token": device_sec_device_token,
        "app_version": "!noperm!", "battery": -888888, "battery2": -888888,
        "battery_health": 3, "battery_changed": -888888, "network": "!notset!",
        "tz": "Asia/Shanghai,8", "lan": "zh_CN", "cpu": 4,
        "sdcard": 255.24993896484375, "sdcard_used": 35.58599090576172,
        "memory": 3.467449188232422, "memory2": 3.467449188232422,
        "data": 255.1754913330078, "data_used": 42.17544174194336,
        "os_version": str(devices.get("os_version", url_params.get("os_version", ""))),
        "brightness": 41, "volume": 36, "ts": report_ts, "ts2": report_ts,
        "ts3": report_ts, "ts4": report_ts + 2, "usb": -1, "hw_version": device_model,
        "brand": brand, "board": device_model, "product_name": device_model,
        "product_device": str(devices.get("device_manufacturer", brand)),
        "product_manufacturer": brand, "hardware": brand, "unknown38": 31,
    }
    env = {
        "launch_time": launch_time, "unknown2": 146331399,
        "unknown3": 146331396, "unknown5": 7, "version": "v04.06.04.03-bugfix",
        "pid": process_id, "device": device,
        "report": {"time": report_time, "state": -2, "code": 200, "times": 0, "unknown6": 0},
        "app_version": version_name,
    }
    values = {
        "magic": b"\xf7\xe8_\xfa\xd7\xd7\xdc;\xd6*\xc8pW\xcfa\x18",
        "version": 3, "rand": proto_rand, "ms_app_id": "8662",
        "device_id": device_id, "license_id": "1588093228", "app_version": version_name,
        "sdk_version_str": "v04.06.04-ml-android", "sdk_version": 67503104,
        "xg_seed_bytes": (320).to_bytes(8, "little"), "time": khronos,
        "query_body_ts_hash": hash_f13(query_sm3, body_md5_bytes, ts_bytes, khronos),
        "query_sm3": query_sm3[:6], "sec_device_token": sec_device_token, "time2": khronos,
        "lanusk_hash": b"", "query_body_hash_sm3": query_body_hash, "psk_version": "none",
        "call_type": 312, "env": env,
        "unknown24": '{"cmr":16777216,"cmr2":16777216,"un_h":1879194040,"vpn":0,"kd":0,"fkd":3672518972,"pd":-1872573247,"dyn":"","do":0,"tk":true}',
    }
    return _encode_medusa(values), query_sm3, hash_f13(query_sm3, body_md5_bytes, ts_bytes, khronos)
def _xmxor_two(data: bytes, key: bytes) -> bytearray:
    encoded = bytearray(len(data))
    for index, value in enumerate(data):
        position = (index * 4) & 28
        d0, d1 = key[position], key[position + 1]
        d2 = (rl8(value, 4) + d0) ^ d1
        d2 = rl8((~d2) & 0xFF, 3)
        d2 = ((d2 + d1) & 0xFF) ^ d0
        encoded[-index - 1] = (~d2) & 0xFF
    return encoded
def _xmxor(data: bytes, key: bytes) -> bytearray:
    value = _xmxor_two(data, key)
    last_flag = value[-1] ^ value[-2]
    data0 = value[0]
    value[0] = (~last_flag + value[0]) & 0xFF
    value[1] = ((value[0] ^ value[-1] ^ 254) + value[1]) & 0xFF
    value[2] = (value[2] + ((last_flag - data0) ^ rl8(value[1], 3) ^ 2)) & 0xFF
    for index in range(len(value) - 4):
        temp = rl8(value[index + 2], 3) ^ value[index + 1] ^ (index + 3)
        value[index + 3] = (~temp + value[index + 3]) & 0xFF
    value[-1] ^= value[-2]
    value[0] = ((value[0] ^ value[1]) + sum(value[1:])) & 0xFF
    return value
def _gen_medusa(url: str, url_params: Mapping[str, Any], devices: Mapping[str, Any], data: Any, khronos: int, data_type: str) -> str:
    config_key = b"\xf1Y3vvn\xa9\x8d4\xf3\x1b\x05z\x9d[\xe4"
    config_iv = b"\x1f\xe1\t\xa4\x12R\x83\xf4\x18\xde\x9e\x05\x1a\x96\x9e\x12"
    sign_key = b"\x8e\xbd\xfa8\x06\xec\xc5\xce\xe7\x94#\xe6\x02\x9e\xd8%@\xbc\"\x18\xbb~\xae\xf7\x1c\xb6\x91\xf7\xaa\x8a\xa2\xf5"
    proto, query_sm3, body_sm3 = _gen_medusa_proto(url, url_params, devices, data, khronos, data_type)
    hash_rand = random.randint(0, 0xFFFFFFFF)
    xm_rand = random.randint(0, 0xFFFFFFFF)
    key, seed = get_key_hash(sign_key, hash_rand)
    mixed = _xmxor(proto, key)
    mixed = (320).to_bytes(8, "little") + mixed
    mixed = bytearray(mixed[::-1])
    for index in range(len(mixed)):
        mixed[index] ^= seed[~index & 3]
    hash_bytes = hash_rand.to_bytes(4, "little")
    check_bit = ((query_sm3[0] & 63) << 14) | 0x18000001 | ((body_sm3[0] & 63) << 8)
    mixed = b"\x35" + xm_rand.to_bytes(4, "little") + check_bit.to_bytes(4, "little") + mixed + hash_bytes[2:]
    mixed = AES_V3(config_key, khronos).encrypt(mixed, config_iv)
    version = bytes.fromhex("03 00 00 00 f7 e8 5f fa d7 d7 dc 3b d6 2a c8 70 57 cf 61 18")
    version_or = b"".join((int.from_bytes(version[i:i + 4], "little") ^ khronos).to_bytes(4, "little") for i in range(0, 20, 4))
    return base64.b64encode(version_or + hash_bytes[:2] + (256).to_bytes(2, "little") + mixed).decode()
def _core_sixgod(url: str, params: Mapping[str, Any], devices: Mapping[str, Any], data: Any, header: Mapping[str, Any]) -> tuple[dict[str, str], str]:
    data_type = str(header.get("content-type", header.get("Content-Type", "")))
    xg_rand = random.randint(0, 0xFFFF)
    encrypted_url, url_params = _get_params_encrypturl(url, params, devices)
    khronos = int(time.time())
    encoded_query = _url_encode(url_params)
    values = {
        "khronos": str(khronos),
        "ladon": base64.b64encode(khronos.to_bytes(4, "big")).decode(),
        "argus": base64.b64encode(khronos.to_bytes(4, "little")).decode(),
        "gorgon": _encrypt_gorgon(data, encoded_query, khronos, xg_rand, data_type),
        "helios": _encrypt_helios(khronos, 0),
        "medusa": _gen_medusa(encrypted_url, url_params, devices, data, khronos, data_type),
    }
    signs = {
        "x-ladon": values["ladon"], "x-khronos": values["khronos"],
        "x-argus": values["argus"], "x-gorgon": values["gorgon"],
        "x-helios": values["helios"], "x-medusa": values["medusa"],
    }
    if data:
        signs["x-ss-stub"] = _json_body_md5(data, data_type)
    result_headers = {str(key).lower(): str(value) for key, value in header.items()}
    result_headers.update(signs)
    if devices.get("ua"):
        result_headers["user-agent"] = str(devices["ua"])
    result_headers["x-tt-dt"] = str(devices.get("x_tt_dt", ""))
    return result_headers, encrypted_url
def _device_config(config: Mapping[str, Any]) -> dict[str, str]:
    device_id = _text(config.get("device_id"))
    install_id = _text(config.get("install_id"))
    if not device_id or not install_id:
        raise HongguoPluginError("缺少红果 device_id/install_id 配置")
    return {
        "device_id": device_id, "iid": install_id, "install_id": install_id,
        "device_brand": "Redmi", "device_model": "25053RT47C", "device_type": "25053RT47C",
        "device_manufacturer": "Xiaomi", "os_version": "16", "version_name": APP_VERSION_NAME,
        "x_tt_dt": _text(config.get("x_tt_dt")),
        "sec_device_token": _text(config.get("sec_device_token")),
        "device_sec_device_token": _text(config.get("device_sec_device_token")),
        "ua": APP_UA,
    }
def _video_model(video_id: str, config: Mapping[str, Any]) -> dict[str, Any]:
    devices = _device_config(config)
    params = {
        "iid": devices["install_id"],
        "device_id": devices["device_id"],
        "ac": "wifi",
        "channel": "update_64",
        "aid": "8662",
        "app_name": "novelread",
        "version_code": APP_VERSION_CODE,
        "version_name": APP_VERSION_NAME,
        "device_platform": "android",
        "os": "android",
        "ssmix": "a",
        "device_type": "25053RT47C",
        "device_brand": "Redmi",
        "language": "zh",
        "os_api": "36",
        "os_version": "16",
        "manifest_version_code": APP_VERSION_CODE,
        "resolution": "1280*2772",
        "dpi": "520",
        "update_version_code": APP_VERSION_CODE,
        "host_abi": "arm64-v8a",
        "dragon_device_type": "phone",
        "pv_player": APP_VERSION_CODE,
        "compliance_status": "0",
        "need_personal_recommend": "1",
        "player_so_load": "1",
        "is_android_pad_screen": "0",
    }
    payload = {
        "biz_param": {
            "detail_page_version": 0,
            "device_level": 3,
            "disable_digg_stat": False,
            "need_all_video_definition": True,
            "need_mp4_align": False,
            "use_os_player": False,
            "use_server_dns": False,
            "video_platform": 1024,
        },
        "mixed_video_id_map": {"1004": [video_id]},
    }
    request_headers = {
        "User-Agent": APP_UA,
        "Accept": "application/json; charset=utf-8,application/x-protobuf",
        "Content-Type": "application/json; charset=UTF-8",
        "x-xs-from-web": "0",
        "x-ss-req-ticket": str(int(time.time() * 1000)),
        "x-tt-request-tag": "t=0;n=0",
        "sdk-version": "2",
        "passport-sdk-version": "50561",
        "x-vc-bdturing-sdk-version": "3.7.2.cn",
    }
    if devices.get("cookie"):
        request_headers["Cookie"] = devices["cookie"]
    signed_headers, signed_url = _core_sixgod(
        VIDEO_URL,
        params,
        devices,
        payload,
        request_headers,
    )
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    status, _, resp_body = http_request(signed_url, method="POST", headers=signed_headers,
                                        data=body, timeout=30, verify=False)
    response_data = _json_response(status, None, resp_body)
    data = response_data.get("data") or {}
    if not isinstance(data, Mapping):
        raise HongguoPluginError("video_model 数据为空")
    entry: Any = data.get(video_id)
    if entry is None:
        for value in data.values():
            if isinstance(value, Mapping):
                entry = value
                break
            if isinstance(value, list) and value and isinstance(value[0], Mapping):
                entry = value[0]
                break
    if not isinstance(entry, Mapping):
        entry = data
    raw_model = entry.get("video_model") if isinstance(entry, Mapping) else None
    if raw_model is None:
        raw_model = data.get("video_model")
    if isinstance(raw_model, str):
        try:
            raw_model = json.loads(raw_model)
        except ValueError as exc:
            raise HongguoPluginError("video_model JSON 无效") from exc
    if not isinstance(raw_model, Mapping):
        raise HongguoPluginError("video_model 为空")
    return dict(raw_model)
def _video_list_from_model(model: Mapping[str, Any]) -> Any:
    for key in ("video_list", "dynamic_video_list"):
        if model.get(key) is not None:
            return model[key]
    dynamic = model.get("dynamic_video")
    if isinstance(dynamic, Mapping):
        for key in ("dynamic_video_list", "video_list", "list"):
            if dynamic.get(key) is not None:
                return dynamic[key]
    video_info = model.get("video_info")
    if isinstance(video_info, Mapping):
        data = video_info.get("data")
        if isinstance(data, Mapping):
            return _video_list_from_model(data)
    data = model.get("data")
    if isinstance(data, Mapping):
        return _video_list_from_model(data)
    return None
_QUALITY_ORDER = ("2160", "1440", "1080", "720", "576", "540", "480", "360")
def _int(value: Any) -> int:
    match = re.search(r"\d+", _text(value))
    return int(match.group()) if match else 0
def _quality(value: Any) -> str:
    text = _text(value).lower()
    match = re.search(r"(2160|1440|1080|720|576|540|480|360)", text)
    return match.group(1) if match else "1080"
def _select_quality(video_list: Any, wanted: str = "1080") -> tuple[str, dict[str, Any]]:
    def rows_from(value: Any, hinted_quality: str = "") -> list[tuple[str, dict[str, Any]]]:
        if isinstance(value, list):
            result: list[tuple[str, dict[str, Any]]] = []
            for item in value:
                result.extend(rows_from(item, hinted_quality))
            return result
        if not isinstance(value, Mapping):
            return []
        if any(
            key in value
            for key in (
                "main_url",
                "backup_url",
                "backup_url_1",
                "play_addr",
                "spade_a",
                "encrypt_info",
            )
        ):
            return [(hinted_quality, dict(value))]
        result = []
        for key, item in value.items():
            if key in {"dynamic_video", "video_info", "data"} and isinstance(item, Mapping):
                result.extend(rows_from(item, hinted_quality))
                continue
            if key in {"video_list", "dynamic_video_list", "list"}:
                result.extend(rows_from(item, _quality(key)))
                continue
            if isinstance(item, (Mapping, list)):
                result.extend(rows_from(item, _quality(key)))
        return result
    candidates = rows_from(video_list)
    rows: dict[str, dict[str, Any]] = {}
    for hinted_quality, item in candidates:
        definition = _quality(
            item.get("definition")
            or item.get("vheight")
            or (item.get("video_meta") or {}).get("definition")
            or hinted_quality
        )
        rows[definition] = item
    if not rows:
        raise HongguoPluginError("播放模型没有清晰度")
    requested = _quality(wanted)
    order = [requested] + [item for item in _QUALITY_ORDER if item != requested]
    for definition in order:
        if definition in rows:
            return definition, rows[definition]
    definition = max(rows, key=lambda item: _int(item))
    return definition, rows[definition]
def _select_all_qualities(value: Any, hinted: str = "") -> list[tuple[str, dict[str, Any]]]:
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(_select_all_qualities(item, hinted))
        return out
    if not isinstance(value, Mapping):
        return []
    if any(k in value for k in ("main_url", "backup_url", "spade_a", "encrypt_info")):
        return [(hinted, dict(value))]
    out = []
    for key, item in value.items():
        hint = _quality(key) if key not in ("dynamic_video", "video_info", "data") else hinted
        if isinstance(item, (Mapping, list)):
            out.extend(_select_all_qualities(item, hint))
    return out
def _select_relay_quality(video_list: Any) -> tuple[str, dict[str, Any]]:
    candidates = []
    for quality, item in _select_all_qualities(video_list):
        meta = item.get("video_meta") if isinstance(item.get("video_meta"), Mapping) else item
        codec = _text(meta.get("codec_type") or meta.get("codec") or "").lower()
        size = int(meta.get("size") or 0) if str(meta.get("size") or "0").isdigit() else 0
        height = _int(quality or meta.get("vheight") or meta.get("definition"))
        codec_score = 2 if codec in ("h264", "avc1", "bytevc1") else (1 if codec == "bytevc2" else 0)
        candidates.append((codec_score, size <= 24 * 1024 * 1024, height, -size, quality, item))
    if not candidates:
        raise HongguoPluginError("播放模型没有清晰度")
    safe = [x for x in candidates if x[1]]
    pool = safe or candidates
    pool.sort(reverse=True, key=lambda x: (x[0], x[1], x[2], x[3]))
    return pool[0][4], pool[0][5]
def _decrypt_spade_url(value: str, key_seed: bytes) -> str:
    raw = _b64(value)
    if len(raw) < 20 or raw[0] != 0xA8 or raw[2:4] != b"\x01\x00":
        raise HongguoPluginError("spade URL 头无效")
    cipher_data = raw[4 : len(raw) - (len(raw) - 4) % 16]
    if not cipher_data:
        raise HongguoPluginError("spade URL 密文为空")
    constants = bytes.fromhex(
        "4dd4c2e6b83162090e52b3c7a6733ba4"
        "1cb2462b829ab58a196b39db57177524"
        "f49baf7f08e8d68d26a72e37c1a95a2f"
        "1f05a51892aef2949732b62a38aadd58"
    )
    first = hashlib.sha512(key_seed).digest()
    second = hashlib.sha512(first + constants).digest()
    plaintext = _aes(second[:16], second[16:32], cipher_data, "cbc")
    if plaintext:
        padding = plaintext[-1]
        if 1 <= padding <= 16 and padding <= len(plaintext):
            plaintext = plaintext[:-padding]
    return plaintext.rstrip(b"\0").decode("utf-8", errors="replace")
def _parse_ref(value: str, prefix: str) -> str:
    if not value.startswith(prefix):
        raise HongguoPluginError("播放引用无效")
    raw = value[len(prefix) :]
    if not raw or not _VIDEO_ID.fullmatch(raw):
        raise HongguoPluginError("播放引用格式无效")
    return raw
def _key_seed_from_model(model: Mapping[str, Any]) -> bytes:
    value = _text(model.get("key_seed"))
    if value:
        return _b64(value)
    for key in ("dynamic_video", "video_info", "data"):
        nested = model.get(key)
        if isinstance(nested, Mapping):
            result = _key_seed_from_model(nested)
            if result:
                return result
    return b""
def hong_drama_from_map(item, category=""):
    if not isinstance(item, dict):
        return None
    vd = item.get("video_data")
    if not isinstance(vd, dict):
        vd = item
    source_id = first_non_empty(vd.get("series_id_str"), vd.get("series_id"),
                                item.get("series_id_str"), item.get("series_id"),
                                vd.get("keyword"), item.get("keyword"))
    if not source_id or not re.fullmatch(r"\d{1,32}", str(source_id)):
        return None
    title = first_non_empty(vd.get("series_title"), vd.get("series_name"), vd.get("title"),
                            item.get("series_name"), item.get("name"), str(source_id))
    cover = first_non_empty(vd.get("series_cover"), vd.get("cover"), item.get("series_cover"))
    if cover:
        cover = resolve_url(hong_web_base() + "/", cover)
    intro = first_non_empty(vd.get("series_intro"), vd.get("video_desc"), item.get("series_intro"))
    count = first_non_empty(vd.get("episode_cnt"), item.get("episode_cnt"))
    remark = first_non_empty(vd.get("episode_right_text"), item.get("episode_right_text"))
    if not remark and count:
        remark = "共%s集" % count
    tags = []
    raw_tags = vd.get("tags")
    if isinstance(raw_tags, list):
        tags = [str(t) for t in raw_tags if t]
    category_list = vd.get("category_list")
    if isinstance(category_list, list):
        for entry in category_list:
            if isinstance(entry, dict) and entry.get("name"):
                name = str(entry["name"])
                if name not in tags:
                    tags.append(name)
    genre = first_non_empty(vd.get("category_name"), vd.get("categoryName"), vd.get("category"))
    if not genre and tags:
        genre = tags[0]
    return {"vod_id": "hongguo:" + str(source_id), "vod_name": str(title)[:200],
            "vod_pic": cover, "vod_content": intro, "vod_remarks": remark,
            "type_name": first_non_empty(genre, category), "vod_tag": ",".join(tags),
            "vod_year": "", "vod_area": ""}
def hong_catalog(category, page):
    genre = None
    for key, name, scene in HONG_GENRES:
        if category == key:
            genre = (key, name, scene)
            break
    if not genre:
        return []
    key, name, scene = genre
    offset = (page - 1) * 18
    payload = {
        "req_scene": scene, "offset": offset, "limit": 18,
        "req_type": "only_content", "need_selector_panel": False, "client_req_type": 3,
        "session_id": "", "filter_ids": "",
        "select_items": {"genre": [key], "sort": ["online_time"], "gender": [],
                         "category_dim_theme": [], "category_dim_role": [], "category_dim_epoch": [],
                         "online_time": [], "creation_status": []},
    }
    result = hong_app_request("/reading/distribution/category/landpage/v/", payload)
    rows = []
    data = result.get("data") if isinstance(result, dict) else None
    if isinstance(data, dict):
        for field in ("video_data", "data", "card_list", "video_list", "list"):
            value = data.get(field)
            if isinstance(value, list):
                rows = value
                break
        if not rows:
            items = data.get("items")
            if isinstance(items, list):
                rows = items
    out = []
    for item in rows:
        drama = hong_drama_from_map(item, name)
        if drama:
            out.append(drama)
    return out
def hong_detail(source_id):
    try:
        result = hong_app_request("/novel/player/video_detail/v1/", {"series_id": source_id})
        data = result.get("data") if isinstance(result, dict) else None
        detail = data.get("video_data") if isinstance(data, dict) else None
        if not isinstance(detail, dict):
            raise RuntimeError("红果 App 详情为空")
        if str(detail.get("series_id_str") or detail.get("series_id") or "") != str(source_id):
            raise RuntimeError("红果返回了其他剧集")
        drama = hong_drama_from_map(detail, "短剧") or {}
        episodes = []
        video_list = detail.get("video_list")
        if isinstance(video_list, list):
            for row in video_list:
                if not isinstance(row, dict):
                    continue
                video_id = str(row.get("vid") or "")
                index = episode_number(row.get("vid_index"))
                if not re.fullmatch(r"\d{1,32}", video_id) or index < 1:
                    continue
                episodes.append({"key": video_id, "title": "第%d集" % index})
        episodes.sort(key=lambda e: episode_number(e["title"]))
        if episodes:
            return drama, episodes
    except Exception:
        pass
    return hong_web_detail(source_id)
def hong_web_detail(source_id):
    url = hong_web_base() + "/detail?series_id=" + urllib.parse.quote(source_id)
    body = http_text(url, headers={"User-Agent": UA_CHROME, "Referer": hong_web_base() + "/"}, timeout=15)
    data = hong_parse_router_data(body)
    page = hong_router_loader(data, "detail_page", "detail_")
    detail = page.get("seriesDetail") if isinstance(page, dict) else None
    if not isinstance(detail, dict) or not detail:
        raise RuntimeError("红果网页详情为空")
    series = detail
    source_id = str(first_non_empty(series.get("series_id"), series.get("series_id_str"), source_id))
    title = first_non_empty(series.get("series_name"), series.get("series_title"), series.get("name"), source_id)
    cover = first_non_empty(series.get("series_cover"), series.get("cover"))
    cover = resolve_url(hong_web_base() + "/", cover) if cover else ""
    intro = first_non_empty(series.get("series_intro"), series.get("video_desc"))
    count = first_non_empty(series.get("episode_cnt"))
    remark = first_non_empty(series.get("episode_right_text"))
    if not remark and count:
        remark = "共%s集" % count
    drama = {"vod_id": "hongguo:" + source_id, "vod_name": str(title)[:200], "vod_pic": cover,
             "vod_content": intro, "vod_remarks": remark, "type_name": "短剧", "vod_year": "", "vod_area": ""}
    episodes = []
    vids = series.get("vid_list")
    if isinstance(vids, list):
        seen = set()
        for row in vids:
            vid = str(row or "").strip()
            if not re.fullmatch(r"\d{1,32}", vid) or vid in seen:
                continue
            seen.add(vid)
            episodes.append({"key": vid, "title": "第%d集" % (len(episodes) + 1)})
    if not episodes:
        raise RuntimeError("红果网页详情没有剧集 ID")
    return drama, episodes
def hong_parse_router_data(body):
    for pattern in (r'<script>window\._ROUTER_DATA\s*=\s*(\{.*?\})</script>',
                    r'window\._ROUTER_DATA\s*=\s*(\{.*?\});',
                    r'_ROUTER_DATA\s*=\s*(\{.*?\});'):
        match = re.search(pattern, body, re.S)
        if not match:
            continue
        try:
            return json.loads(html_unescape(match.group(1)))
        except Exception:
            continue
    return None
def hong_router_loader(data, *names):
    if not isinstance(data, dict):
        return {}
    loader = data.get("loaderData")
    if not isinstance(loader, dict):
        return {}
    for name in names:
        page = loader.get(name)
        if isinstance(page, dict) and page:
            return page
    for key, value in loader.items():
        for name in names:
            if name.endswith("$"):
                name = name[:-1]
            if name and key.startswith(name):
                if isinstance(value, dict) and value:
                    return value
    return {}
HONG_MEDIA_CACHE_TTL = 3600
HONG_MEDIA_WINDOW = 900
HONG_MEDIA_QUOTA = 3
def _hong_app_devices():
    return {
        "device_id": str(random.randint(10 ** 17, 10 ** 18 - 1)),
        "install_id": str(random.randint(10 ** 17, 10 ** 18 - 1)),
    }
def hong_app_media(source_id, key):
    vid = str(key or "").strip()
    if not vid:
        return ""
    try:
        base = _stream_ensure()
        return base + "/play?vid=" + urllib.parse.quote(vid, safe="")
    except Exception as exc:
        log("红果App流式服务启动失败", vid, exc)
        try:
            model = _video_model(vid, _hong_app_devices())
            video_list = _video_list_from_model(model)
            if not video_list:
                return ""
            _, item = _select_relay_quality(video_list)
            url = _media_url(item)
            if not url:
                return ""
            spade = _spade_value(item)
            key_seed = _key_seed_from_model(model)
            if key_seed:
                try:
                    url = _decrypt_spade_url(url, key_seed)
                except Exception:
                    pass
            if not spade:
                return "http://127.0.0.1:UndCover/proxy?do=%s&api=python&site=hongguo&type=hong_media&url=%s" % (
                    urllib.parse.quote(LOCAL_PROXY_KEY, safe=""),
                    urllib.parse.quote(url, safe=""))
            return "http://127.0.0.1:UndCover/proxy?do=%s&api=python&site=hongguo&type=mc_cenc&url=%s" % (
                urllib.parse.quote(LOCAL_PROXY_KEY, safe=""),
                urllib.parse.quote(vid, safe=""))
        except Exception as exc2:
            log("红果App取流失败", vid, exc2)
            return ""
def hong_app_cenc_proxy(vid):
    vid = str(vid or "").strip()
    if not vid:
        return [400, "text/plain", b"bad vid", {"Content-Type": "text/plain"}]
    try:
        model = _video_model(vid, _hong_app_devices())
        video_list = _video_list_from_model(model)
        if not video_list:
            raise Exception("播放模型无轨道")
        _, item = _select_relay_quality(video_list)
        url = _media_url(item)
        spade = _spade_value(item)
        if not url or not spade:
            raise Exception("轨道无 URL/spade_a")
        key_seed = _key_seed_from_model(model)
        if key_seed:
            try:
                url = _decrypt_spade_url(url, key_seed)
            except Exception:
                pass
        key = derive_content_key(spade)
        status, _, body = http_request(url, headers={
            "User-Agent": MEDIA_UA,
            "Referer": "https://novel.snssdk.com/",
        }, timeout=120, verify=False)
        if status >= 400 or not body:
            raise Exception("密文下载失败 HTTP %s" % status)
        plain = decrypt_mp4_cenc(body, key)
        return [200, "video/mp4", plain, {"Content-Type": "video/mp4"}]
    except Exception as exc:
        log("红果App解密失败", vid, exc)
        return [502, "text/plain", b"cenc resolve failed", {"Content-Type": "text/plain"}]
def _http_stream_get(url, headers=None, timeout=120):
    current = url
    for _ in range(5):
        parsed = urllib.parse.urlparse(current)
        host = parsed.hostname
        port = parsed.port
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        if parsed.scheme == "http":
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
        else:
            _ctx = ssl._create_unverified_context()
            conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=_ctx)
        try:
            conn.request("GET", path, headers=dict(headers or {}))
            resp = conn.getresponse()
            if resp.status in (301, 302, 303, 307, 308):
                location = resp.getheader("Location")
                conn.close()
                if not location:
                    raise RuntimeError("redirect without location: " + current)
                current = urllib.parse.urljoin(current, location)
                continue
            headers_map = {}
            for key, value in resp.getheaders():
                headers_map[key.lower()] = value
            def _iter(resp=resp, conn=conn):
                try:
                    while True:
                        chunk = resp.read(262144)
                        if not chunk:
                            break
                        yield chunk
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
            return resp.status, headers_map, _iter()
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            raise
    raise RuntimeError("redirect too many: " + url)
_STREAM_STATE = {"ready": False, "server": None, "port": 0, "base": "", "lock": threading.Lock()}
def _find_free_port(preferred):
    for port in range(preferred, preferred + 50):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
    return 0
def _stream_resolve(vid):
    model = _video_model(vid, _hong_app_devices())
    video_list = _video_list_from_model(model)
    if not video_list:
        raise RuntimeError("video model unavailable")
    _, item = _select_relay_quality(video_list)
    spade = _spade_value(item)
    key_seed = _key_seed_from_model(model)
    def _fix(value):
        value = str(value or "").strip()
        if value and key_seed:
            try:
                value = _decrypt_spade_url(value, key_seed)
            except Exception:
                pass
        return value
    main = _fix(_media_url(item))
    if not main:
        raise RuntimeError("video model unavailable")
    backups = []
    for name in ("backup_url_1", "backup_url_2", "play_addr", "url"):
        value = _fix(item.get(name))
        if value and value != main and value not in backups:
            backups.append(value)
    key = derive_content_key(spade) if spade else None
    return main, backups, key
def _stream_ensure():
    state = _STREAM_STATE
    with state["lock"]:
        if state["ready"] and state.get("server") is not None:
            return state["base"]
        if state.get("server") is not None:
            try:
                state["server"].server_close()
            except Exception:
                pass
            state["server"] = None
        port = _find_free_port(9878)
        if not port:
            raise RuntimeError("no free port for stream server")
        src_dir = os.path.join(tempfile.gettempdir(), "zhenguojian_v22_cache")
        try:
            os.makedirs(src_dir, exist_ok=True)
        except OSError:
            pass
        _StreamHandler.src_dir = src_dir
        server = ThreadingHTTPServer(("127.0.0.1", port), _StreamHandler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        state.update({"ready": True, "server": server, "port": port,
                      "base": "http://127.0.0.1:%d" % port})
        return state["base"]
class _StreamHandler(BaseHTTPRequestHandler):
    src_dir = None
    _resolve_cache = {}
    _vid_locks = {}
    _guard = threading.Lock()
    _download_locks = {}
    _download_guard = threading.Lock()
    _RESOLVE_TTL = 300
    _FILE_TTL = 1800
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        if path == "/play":
            self._handle_play(params)
        elif path == "/stream":
            self._handle_stream(params)
        elif path == "/jugu_m3u8":
            self._handle_jugu_m3u8(params)
        elif path == "/pic":
            self._handle_pic(params)
        elif path == "/fav_ok":
            body = _fav_placeholder_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                self.wfile.write(body)
            except Exception:
                pass
        elif path == "/health":
            self._json(200, {"ok": True, "service": "zhenguojian-stream"})
        else:
            self.send_error(404)
    def do_HEAD(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/stream":
            self._handle_stream(parse_qs(parsed.query), head_only=True)
        elif parsed.path == "/jugu_m3u8":
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.apple.mpegurl")
            self.send_header("Content-Length", "0")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
        else:
            self.send_error(404)
    def _handle_pic(self, params):
        u = pget(params, "u")
        if not u:
            self._json(400, {"error": "missing u"})
            return
        site = pget(params, "site") or "yeguo"
        try:
            if site == "hguo":
                code, mime, body, hdrs = hguo_proxy_image(u)
            else:
                code, mime, body, hdrs = yeguo_proxy_image(u)
        except Exception:
            code, mime, body, hdrs = 500, "text/plain", b"proxy error", {"Content-Type": "text/plain"}
        self.send_response(code)
        for k, v in hdrs.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass
    def log_message(self, *args):
        pass
    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass
    def _handle_jugu_m3u8(self, params):
        url = pget(params, "url")
        ep = pget(params, "ep")
        if not url:
            self._json(400, {"error": "missing url"})
            return
        try:
            cached = jugu_m3u8_cached(url)
            if cached is not None:
                payload = cached
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                try:
                    self.wfile.write(payload)
                except Exception:
                    pass
                return
            ck = {}
            try:
                ck = jugu_cookies()
            except Exception:
                ck = {}
            if not ck and ep:
                try:
                    jugu_play_with_cookies(str(ep))
                    ck = jugu_cookies()
                except Exception:
                    ck = {}
            headers = {"User-Agent": UA_ANDROID}
            if ck:
                headers["Cookie"] = "; ".join("%s=%s" % (k, v) for k, v in ck.items())
            status, resp_headers, body = http_request(url, headers=headers, timeout=25)
            if status >= 400:
                self._json(502, {"error": "jugu upstream %d" % status})
                return
            content_type = resp_headers.get("content-type", "")
            if "m3u8" in content_type or body[:7] == b"#EXTM3U":
                try:
                    jugu_self = _stream_ensure() + "/jugu_m3u8"
                except Exception:
                    jugu_self = ""
                payload = rewrite_m3u8(body, "jugu", {"url": url, "ep": ep, "jugu_self": jugu_self})
                JUGU_M3U8_CACHE[url] = (time.time(), payload)
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                try:
                    self.wfile.write(payload)
                except Exception:
                    pass
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                self.wfile.write(body)
            except Exception:
                pass
        except Exception as exc:
            log("剧果流式代理失败", url, exc)
            try:
                self._json(502, {"error": "jugu proxy error"})
            except Exception:
                pass
    def _resolve_vid(self, vid):
        with self._guard:
            if vid not in self._vid_locks:
                self._vid_locks[vid] = threading.Lock()
            if len(self._resolve_cache) > 1000:
                now = time.time()
                for key in [k for k, v in self._resolve_cache.items() if now - v[0] > self._RESOLVE_TTL]:
                    self._resolve_cache.pop(key, None)
        with self._vid_locks[vid]:
            hit = self._resolve_cache.get(vid)
            if hit and time.time() - hit[0] < self._RESOLVE_TTL:
                return hit[1]
            result = _stream_resolve(vid)
            self._resolve_cache[vid] = (time.time(), result)
            return result
    def _handle_play(self, params):
        vid = (params.get("vid") or [""])[0].strip()
        if not vid.isdigit():
            self._json(400, {"error": "vid invalid"})
            return
        try:
            main, backups, key = self._resolve_vid(vid)
            query = [("url", main)]
            if key:
                query.append(("key", base64.b64encode(key).decode("ascii")))
            for value in backups or []:
                query.append(("bk", value))
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:%d/stream?%s" % (
                self.server.server_port, urlencode(query)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
        except Exception as exc:
            self._json(502, {"error": str(exc)})
    def _handle_stream(self, params, head_only=False):
        raw_url = (params.get("url") or [""])[0].strip()
        key_b64 = (params.get("key") or [""])[0].strip()
        if not raw_url:
            self.send_error(400, "missing url")
            return
        backups = [value for value in params.get("bk", []) if value]
        candidates = [raw_url] + backups
        try:
            content_key = base64.b64decode(key_b64) if key_b64 else None
        except Exception:
            content_key = None
        if content_key is None:
            self._proxy_plain(candidates, head_only)
            return
        filename = "video_%s.mp4" % hashlib.md5(raw_url.encode()).hexdigest()[:16]
        filepath = os.path.join(self.src_dir or tempfile.gettempdir(), filename)
        if os.path.exists(filepath):
            self._serve_file(filepath, head_only)
            return
        range_header = self.headers.get("Range", "")
        # 解析 Range 起始字节：无 Range / bytes=0- / bytes=0-N 均视为"从头播放"，
        # 一律走增量流式 _stream_direct（边下边解密边下发），
        # 避免旧逻辑把 bytes=0-N 判定为非全量而走"整片下载+整片解密"造成的卡顿与超时。
        _range_start = 0
        _range_m = re.match(r"bytes\s*=\s*(\d+)\s*-", range_header or "")
        if _range_m:
            try:
                _range_start = int(_range_m.group(1))
            except Exception:
                _range_start = 0
        is_full = _range_start <= 0
        with self._download_guard:
            if filename not in self._download_locks:
                self._download_locks[filename] = threading.Lock()
            lock = self._download_locks[filename]
        if is_full and not head_only and lock.acquire(blocking=False):
            try:
                if os.path.exists(filepath):
                    self._serve_file(filepath, head_only)
                    return
                self._stream_direct(raw_url, backups, content_key, filepath)
                return
            except Exception:
                pass
            finally:
                lock.release()
        try:
            with lock:
                if os.path.exists(filepath):
                    self._serve_file(filepath, head_only)
                    return
                data = _download_bytes(candidates)
                if content_key is not None:
                    data = decrypt_mp4_cenc(data, content_key)
                try:
                    with open(filepath, "wb") as f:
                        f.write(data)
                except OSError:
                    pass
                self._schedule_cleanup(filepath)
                self._serve_file(filepath, head_only)
        except Exception:
            try:
                self.send_error(502, "stream failed")
            except Exception:
                pass
    def _proxy_plain(self, candidates, head_only):
        headers = {"User-Agent": MEDIA_UA, "Referer": "https://novel.snssdk.com/"}
        response = None
        for url in candidates:
            try:
                status, resp_headers, response = _http_stream_get(url, headers=headers, timeout=90)
                if status >= 400:
                    response = None
                    continue
                break
            except Exception:
                response = None
        if response is None:
            try:
                self.send_error(502, "cdn failed")
            except Exception:
                pass
            return
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        length = resp_headers.get("content-length")
        if length:
            self.send_header("Content-Length", length)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if head_only:
            try:
                response.close()
            except Exception:
                pass
            return
        try:
            for chunk in response:
                self.wfile.write(chunk)
        except Exception:
            pass
    def _serve_file(self, filepath, head_only=False):
        try:
            file_size = os.path.getsize(filepath)
        except OSError:
            self.send_error(404)
            return
        if file_size <= 16:
            self.send_error(404)
            return
        range_header = self.headers.get("Range", "")
        start, end, is_partial = 0, file_size - 1, False
        if range_header:
            match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if match:
                start = int(match.group(1))
                if match.group(2):
                    end = min(int(match.group(2)), file_size - 1)
                is_partial = True
        if start >= file_size or start > end:
            self.send_error(416)
            return
        length = end - start + 1
        if is_partial:
            self.send_response(206)
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, file_size))
        else:
            self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Expose-Headers", "Content-Length, Content-Range, Accept-Ranges")
        self.end_headers()
        if head_only:
            return
        try:
            with open(filepath, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except Exception:
            pass
    def _schedule_cleanup(self, filepath):
        def _delete():
            try:
                os.unlink(filepath)
            except OSError:
                pass
        timer = threading.Timer(self._FILE_TTL, _delete)
        timer.daemon = True
        timer.start()
    def _send_plain(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Expose-Headers", "Content-Length, Content-Range, Accept-Ranges")
        self.end_headers()
        try:
            self.wfile.write(data)
            self.wfile.flush()
        except Exception:
            pass
    def _stream_direct(self, raw_url, backups, content_key, filepath):
        headers = {"User-Agent": MEDIA_UA, "Referer": "https://novel.snssdk.com/"}
        candidates = [raw_url] + list(backups or [])
        response = None
        for url in candidates:
            try:
                status, resp_headers, response = _http_stream_get(url, headers=headers, timeout=120)
                if status >= 400:
                    response = None
                    continue
                break
            except Exception:
                response = None
        if response is None:
            raise RuntimeError("cdn failed")
        total_size = int(resp_headers.get("content-length") or 0)
        iterator = iter(response)
        buffer = bytearray()
        # ---- 修复: 不再假设 ftyp 之后的第二个 box 就是 moov ----
        # 旧逻辑若第二个 box 是 mdat，会把 moov_end 算成整个文件大小，
        # 导致必须先把整片下载完才开始服务（严重卡顿/超时）。
        # 现在遍历顶层 box 精确定位 moov；moov 在文件尾部时用 Range 单独取回。
        ftyp_size = 0
        moov_box_start = -1
        moov_size = 0
        mdat_start = -1
        mdat_size = 0
        moov_tail = b""
        head_need = 1024 * 1024
        while len(buffer) < head_need:
            try:
                chunk = next(iterator)
            except StopIteration:
                break
            if not chunk:
                break
            buffer.extend(chunk)
        if len(buffer) >= 8:
            ftyp_size = struct.unpack(">I", bytes(buffer[0:4]))[0]
            if ftyp_size < 8 or ftyp_size > len(buffer):
                ftyp_size = 0
        if ftyp_size > 0:
            off = 0
            while off + 8 <= len(buffer):
                bsize = struct.unpack(">I", bytes(buffer[off:off + 4]))[0]
                btype = bytes(buffer[off + 4:off + 8])
                if bsize == 1:
                    if off + 16 > len(buffer):
                        break
                    bsize = struct.unpack(">Q", bytes(buffer[off + 8:off + 16]))[0]
                    if bsize < 16:
                        break
                elif bsize == 0:
                    bsize = max(len(buffer) - off, 8)
                    if btype == b"moov":
                        moov_box_start, moov_size = off, bsize
                    elif btype == b"mdat":
                        mdat_start, mdat_size = off, bsize
                    break
                if bsize < 8:
                    break
                if btype == b"moov":
                    moov_box_start, moov_size = off, bsize
                    break
                if btype == b"mdat":
                    mdat_start, mdat_size = off, bsize
                off += bsize
        # moov 不在头部(非 faststart): 从 mdat 之后用 Range 取回 moov
        if moov_box_start < 0 and mdat_start >= 0 and mdat_size > 0:
            moov_off = mdat_start + mdat_size
            try:
                status_m, _, moov_iter = _http_stream_get(
                    candidates[0],
                    headers=dict(headers, Range="bytes=%d-%d" % (moov_off, moov_off + 8 * 1024 * 1024 - 1)),
                    timeout=30)
                if status_m < 400:
                    tail = b"".join(moov_iter)
                    if len(tail) >= 8:
                        msz = struct.unpack(">I", tail[0:4])[0]
                        if 8 <= msz <= len(tail):
                            moov_box_start, moov_size = moov_off, msz
                            # 注意: 不能用零字节把 buffer 填充到 moov_off，
                            # 否则 buffer[media_start:] 会混入大量零字节而破坏媒体流。
                            moov_tail = tail[:msz]
            except Exception:
                pass
        moov_end = (moov_box_start + moov_size) if moov_box_start >= 0 else 0
        # 媒体数据起点: faststart 时紧接 moov; moov 在尾部时从 mdat 开始(含 mdat box 头)
        if mdat_start >= 0:
            media_start = mdat_start
        else:
            media_start = moov_end
        have_moov = bool(moov_tail) or (moov_box_start >= 0 and moov_size > 8 and len(buffer) >= moov_end)
        if not have_moov:
            try:
                response.close()
            except Exception:
                pass
            data = bytearray(buffer)
            for chunk in iterator:
                data.extend(chunk)
            plain = decrypt_mp4_cenc(bytes(data), content_key)
            self._send_plain(plain)
            try:
                with open(filepath, "wb") as f:
                    f.write(plain)
                self._schedule_cleanup(filepath)
            except OSError:
                pass
            return
        if moov_tail:
            moov = bytearray(moov_tail[8:moov_size])
        else:
            moov = bytearray(buffer[moov_box_start + 8:moov_end])
        _replace_fourcc(moov, b"encv", b"hvc1")
        _replace_fourcc(moov, b"enca", b"mp4a")
        _replace_sinf(moov)
        view = memoryview(moov)
        decrypt_map = {}
        track_search = 0
        while True:
            track, track_size = _find_box(view, b"trak", track_search)
            if track < 0:
                break
            parsed = _parse_track(view, track)
            if parsed is not None:
                sizes, offsets, chunk_counts, aux_sizes, aux_offset, sample_count = parsed
                if sample_count and len(aux_sizes) >= sample_count and aux_offset >= 0:
                    aux_total = sum(max(size, 8) for size in aux_sizes)
                    if aux_offset + aux_total <= len(buffer):
                        aux_data = bytes(buffer[aux_offset:aux_offset + aux_total])
                    else:
                        try:
                            status, _, aux_iter = _http_stream_get(candidates[0], headers=dict(
                                headers, Range="bytes=%d-%d" % (aux_offset, aux_offset + aux_total - 1)),
                                timeout=15)
                            aux_data = b"".join(aux_iter)
                        except Exception:
                            aux_data = b""
                    if len(aux_data) >= aux_total:
                        sample_index, aux_index = 0, 0
                        for chunk_index, chunk_offset in enumerate(offsets):
                            offset = chunk_offset
                            count = chunk_counts[chunk_index] if chunk_index < len(chunk_counts) else 0
                            for _ in range(count):
                                if sample_index >= sample_count:
                                    break
                                size = sizes[sample_index]
                                entry_size = max(aux_sizes[sample_index], 8)
                                iv = bytes(aux_data[aux_index:aux_index + min(entry_size, 8)]).ljust(8, b"\x00")
                                decrypt_map[offset] = (size, iv)
                                offset += size
                                sample_index += 1
                                aux_index += entry_size
            track_search = track + max(track_size, 8)
        if not decrypt_map:
            try:
                response.close()
            except Exception:
                pass
            data = bytearray(buffer)
            for chunk in iterator:
                data.extend(chunk)
            plain = decrypt_mp4_cenc(bytes(data), content_key)
            self._send_plain(plain)
            try:
                with open(filepath, "wb") as f:
                    f.write(plain)
                self._schedule_cleanup(filepath)
            except OSError:
                pass
            return
        self.send_response(200)
        # 输出是重排后的 MP4(ftyp + moov + 媒体数据)，长度需按实际输出计算，
        # 不能直接沿用源文件长度（moov 在尾部时两者不等，会导致播放器中途断流）
        out_len = ftyp_size + moov_size + max(total_size - media_start, 0)
        if out_len > 0:
            self.send_header("Content-Length", str(out_len))
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Expose-Headers", "Content-Length, Content-Range, Accept-Ranges")
        self.end_headers()
        # moov 盒子头(8字节 size+type) + 已打补丁的 moov 体
        header_bytes = (bytes(buffer[0:ftyp_size])
                        + struct.pack(">I", moov_size) + b"moov"
                        + bytes(moov))
        part_path = filepath + ".part"
        try:
            file_handle = open(part_path, "wb")
        except OSError:
            file_handle = None
        try:
            self.wfile.write(header_bytes)
            self.wfile.flush()
            if file_handle:
                file_handle.write(header_bytes)
            current_pos = media_start
            if len(buffer) > media_start:
                segment = bytearray(buffer[media_start:])
                plain = _cenc_chunk(segment, current_pos, decrypt_map, content_key)
                self.wfile.write(plain)
                self.wfile.flush()
                if file_handle:
                    file_handle.write(plain)
                current_pos += len(segment)
            buffer = None
            for chunk in iterator:
                chunk = bytearray(chunk)
                plain = _cenc_chunk(chunk, current_pos, decrypt_map, content_key)
                self.wfile.write(plain)
                self.wfile.flush()
                if file_handle:
                    file_handle.write(plain)
                current_pos += len(chunk)
            if file_handle:
                file_handle.close()
                file_handle = None
            if os.path.exists(part_path):
                os.replace(part_path, filepath)
                self._schedule_cleanup(filepath)
        except Exception:
            pass
        finally:
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
            try:
                if os.path.exists(part_path):
                    os.unlink(part_path)
            except Exception:
                pass
            try:
                response.close()
            except Exception:
                pass
def _download_bytes(candidates):
    headers = {"User-Agent": MEDIA_UA, "Referer": "https://novel.snssdk.com/"}
    last = None
    for url in candidates:
        try:
            status, _, body = http_request(url, headers=headers, timeout=120, verify=False)
            if status >= 400:
                raise RuntimeError("HTTP %s" % status)
            return body
        except Exception as exc:
            last = exc
    raise RuntimeError("cdn failed: %s" % last)
def _cenc_chunk(chunk, chunk_start, decrypt_map, content_key):
    chunk_end = chunk_start + len(chunk)
    for sample_off, (size, iv) in decrypt_map.items():
        sample_end = sample_off + size
        if sample_off >= chunk_end or sample_end <= chunk_start:
            continue
        overlap_start = max(sample_off, chunk_start)
        overlap_end = min(sample_end, chunk_end)
        overlap_size = overlap_end - overlap_start
        offset_in_sample = overlap_start - sample_off
        start_block = offset_in_sample // 16
        counter = int.from_bytes(iv + b"\x00" * 8, "big") + start_block
        counter_bytes = counter.to_bytes(16, "big")
        block_offset = offset_in_sample % 16
        start_in_chunk = overlap_start - chunk_start
        segment = bytes(chunk[start_in_chunk:start_in_chunk + overlap_size])
        if block_offset:
            decoded = _aes(content_key, counter_bytes, b"\x00" * block_offset + segment, "ctr")
            decoded = decoded[block_offset:]
        else:
            decoded = _aes(content_key, counter_bytes, segment, "ctr")
        chunk[start_in_chunk:start_in_chunk + overlap_size] = decoded
    return bytes(chunk)
def hong_media_throttled(source_id, video_id):
    cache_key = "hong:media:%s:%s" % (source_id, video_id)
    cached = cache_get(cache_key)
    if cached:
        return cached
    state_key = "hong:rate:%s" % source_id
    state = cache_get(state_key)
    now = time.time()
    if not state or now - state[0] >= HONG_MEDIA_WINDOW:
        state = (now, [])
    if video_id not in state[1]:
        if len(state[1]) >= HONG_MEDIA_QUOTA:
            log("红果限流: 剧%s窗口内已请求%d个不同集, 拒绝新集%s(等窗口重置再点)" % (
                source_id, HONG_MEDIA_QUOTA, video_id))
            raise RuntimeError("红果播放页限流(每10分钟最多3个不同集, 请稍后再点)")
        state[1].append(video_id)
        cache_set(state_key, state, HONG_MEDIA_WINDOW + 120)
    return hong_web_media(source_id, video_id)
def hong_web_media(source_id, video_id):
    cache_key = "hong:media:%s:%s" % (source_id, video_id)
    cached = cache_get(cache_key)
    if cached:
        return cached
    url = hong_web_base() + "/player/" + urllib.parse.quote(source_id) + "/" + urllib.parse.quote(video_id)
    body = http_text(url, headers={"User-Agent": UA_CHROME, "Referer": hong_web_base() + "/"}, timeout=15)
    data = hong_parse_router_data(body)
    page = hong_router_loader(data, "player_page", "player_")
    if not isinstance(page, dict):
        raise RuntimeError("红果播放页解析失败")
    if str(page.get("vid") or "") != str(video_id) or str(page.get("series_id") or "") != str(source_id):
        raise RuntimeError("红果未返回所请求的剧集")
    info = page.get("video_player_info")
    if not isinstance(info, dict):
        info = page
    addresses = []
    seen = set()
    for field in ("main_url", "backup_url", "backup_url_1", "backup_url_2", "backup_urls", "url_list"):
        value = info.get(field)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    hong_media_add_address(addresses, seen, item)
        elif isinstance(value, str):
            hong_media_add_address(addresses, seen, value)
    if not addresses:
        raise RuntimeError("红果该集未提供公开播放地址")
    media = addresses[0]
    cache_set(cache_key, media, HONG_MEDIA_CACHE_TTL)
    return media
def hong_media_add_address(addresses, seen, raw):
    raw = str(raw).strip()
    if len(raw) > 8192:
        return
    if not re.match(r"^https?://", raw, re.I):
        try:
            decoded = base64.b64decode(raw + "=" * (-len(raw) % 4), validate=True).decode("utf-8")
        except Exception:
            try:
                decoded = base64.b64decode(raw, validate=True).decode("utf-8")
            except Exception:
                return
        raw = decoded.strip()
    if re.match(r"^https?://", raw, re.I) and raw not in seen:
        seen.add(raw)
        addresses.append(raw)
def hong_search(keyword):
    url = hong_web_base() + "/search/" + urllib.parse.quote(keyword)
    try:
        body = http_text(url, headers={"User-Agent": UA_CHROME, "Referer": hong_web_base() + "/"})
    except Exception:
        return []
    search_list = None
    def walk(value):
        nonlocal search_list
        if search_list is not None:
            return
        if isinstance(value, dict):
            for k, v in value.items():
                if k == "searchList" and isinstance(v, list):
                    search_list = v
                    return
                walk(v)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    marker = body.find("_ROUTER_DATA = ")
    if marker < 0:
        marker = body.find("_ROUTER_DATA=")
    if marker >= 0:
        seg = body[marker:]
        eq = seg.find("=")
        seg = seg[eq + 1:]
        end = seg.find("</script>")
        if end < 0:
            end = seg.find("</SCRIPT>")
        if end > 0:
            seg = seg[:end].strip()
            if seg.endswith(";"):
                seg = seg[:-1].strip()
            if seg.startswith("{"):
                try:
                    data, _ = json.JSONDecoder().raw_decode(seg)
                    walk(data)
                except Exception:
                    pass
    if search_list is None:
        for pattern in (r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                        r'<script id="__NUXT_DATA__" type="application/json">(.*?)</script>',
                        r'<script>window\._ROUTER_DATA\s*=\s*(\{.*?\})</script>'):
            m = re.search(pattern, body, re.S)
            if not m:
                continue
            try:
                data = json.loads(html_unescape(m.group(1)))
                walk(data)
                if search_list is not None:
                    break
            except Exception:
                continue
    out = []
    if isinstance(search_list, list):
        for row in search_list:
            drama = hong_drama_from_map(row, "短剧")
            if drama:
                out.append(drama)
    return out
HGUO_MIRRORS = ["https://huangguoai.com", "https://ttvoij.ediayikma.cc", "https://thu.ediayikma.cc",
                "https://pku.ediayikma.cc", "https://fdu.ediayikma.cc", "https://thu.agdkczeyx.cc"]
def hguo_mirror():
    ok = cache_get("hguo:mirror_ok")
    if ok:
        return ok
    mirrors = cache_get("hguo:mirrors")
    if not mirrors:
        mirrors = HGUO_MIRRORS + hguo_generated_mirrors()
        cache_set("hguo:mirrors", mirrors, 3600)
    found = [""]
    lock = threading.Lock()
    def probe(m):
        try:
            status, _, _ = http_request(m + "/", timeout=3)
            if status < 400:
                with lock:
                    if not found[0]:
                        found[0] = m
        except Exception:
            pass
    threads = [threading.Thread(target=probe, args=(m,)) for m in mirrors]
    for t in threads:
        t.start()
    for t in threads:
        t.join(4)
    mirror = found[0] or mirrors[0]
    if found[0]:
        cache_set("hguo:mirror_ok", mirror, 1800)
    return mirror
def hguo_generated_mirrors():
    out = []
    seen = set()
    for index in range(8):
        digest = hashlib.sha256(("huangguoai:%d" % index).encode()).hexdigest()
        prefix = digest[:6]
        prefix = re.sub(r"^[0-9]+", "", prefix)
        if len(prefix) < 4:
            prefix = digest[6:12].lstrip("0123456789")
        if len(prefix) > 6:
            prefix = prefix[:6]
        if prefix and not prefix.isdigit() and prefix not in seen:
            seen.add(prefix)
            out.append("https://" + prefix + ".ediayikma.cc")
    return out
def hguo_category(cat, page):
    mirror = hguo_mirror()
    cats = [cat] if cat else ["ai-duanju", "ai-manju", "ai-huanlian", "ai-mogai"]
    out = []
    def fetch(entry):
        try:
            url = "%s/api/videos/category/%s?sort=hot&page=%d&size=24" % (mirror, urllib.parse.quote(entry), page)
            data = http_json(url, headers={"User-Agent": UA_ANDROID, "Referer": mirror + "/"})
        except Exception:
            return []
        return hguo_walk_cards(data, entry)
    for _name, cards in parallel_run([("c%d" % i, lambda e=entry: fetch(e)) for i, entry in enumerate(cats)], 4):
        out.extend(cards)
        if len(out) >= 40:
            break
    return out
def hguo_walk_cards(value, category):
    out = []
    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            drama = hguo_card(node, category)
            if drama:
                out.append(drama)
                return
            for child in node.values():
                walk(child)
    walk(value)
    return out
def hguo_card(m, category):
    source_id = first_non_empty(m.get("id"), m.get("videoId"), m.get("video_id"), m.get("vid"), m.get("slug"))
    if not source_id:
        for value in m.values():
            if isinstance(value, str):
                match = re.search(r"/detail/([0-9a-zA-Z_-]+)/?", value)
                if match:
                    source_id = match.group(1)
                    break
    source_id = re.sub(r"[^0-9a-zA-Z_-]", "", str(source_id or ""))
    if not source_id:
        return None
    title = first_non_empty(m.get("title"), m.get("name"), m.get("videoTitle"), m.get("video_title"),
                            m.get("videoName"), m.get("video_name"))
    if not title or re.fullmatch(r"[\d\s]+", title):
        return None
    cover = first_non_empty(m.get("cover"), m.get("coverUrl"), m.get("cover_url"), m.get("coverImage"),
                            m.get("cover_image"), m.get("image"), m.get("imageUrl"), m.get("thumbnail"),
                            m.get("poster"), m.get("posterUrl"))
    cover = resolve_url("https://huangguoai.com/", cover) if cover else ""
    if "?" in cover and re.search(r"(auth_key|authkey|sign|token)=", cover, re.I):
        cover = cover.split("?", 1)[0]
    if cover:
        cover = hguo_pic_proxy(cover)
    else:
        cover = ""
    desc = first_non_empty(m.get("desc"), m.get("description"), m.get("intro"), m.get("summary"))
    remark = first_non_empty(m.get("vod_remarks"), m.get("remark"), m.get("remarks"))
    eps = first_non_empty(m.get("episodes"), m.get("episode_count"), m.get("total_episodes"))
    if not remark and eps:
        finished = str(m.get("is_finished", "")).lower()
        remark = ("全%s集" % eps) if finished in ("true", "1") else ("更新至%s集" % eps)
    return {"vod_id": "huangguoai:" + source_id, "vod_name": str(title)[:200], "vod_pic": cover,
            "vod_content": desc, "vod_remarks": remark, "type_name": category, "vod_year": "", "vod_area": ""}
def hguo_detail(source_id):
    mirror = hguo_mirror()
    url = mirror + "/detail/" + urllib.parse.quote(source_id) + "/"
    body = ""
    for attempt in range(4):
        try:
            body = http_text(url, headers={"User-Agent": UA_ANDROID, "Referer": mirror + "/"}, timeout=15)
        except Exception:
            body = ""
        if body and len(body) > 800:
            break
        time.sleep(1.0 * (attempt + 1))
    title = ""
    m = re.search(r"<title>(.*?)</title>", body, re.S)
    if m:
        title = clean_text(m.group(1)).replace(" - huangguoai.com", "")
    cover = ""
    for tag in re.findall(r'<meta[^>]+>', body, re.I):
        if attrs(tag, "property", "name").lower() == "og:image":
            cover = attrs(tag, "content")
            break
    pic_urls = set(re.findall(r'https?://pic\.[a-z0-9.-]+/[^\s"\'\\<>]+\.(?:jpe?g|png|webp)[^\s"\'\\<>]*', body, re.I))
    pic_urls = {html_unescape(u).rstrip('",\'') for u in pic_urls}
    if pic_urls:
        cover_name = re.search(r"/([^/]+)\.(?:jpe?g|png|webp)(?:[?#]|$)", cover, re.I)
        pick = ""
        if cover_name:
            for u in pic_urls:
                if "/" + cover_name.group(1) + "." in u:
                    pick = u
                    break
        cover = pick or sorted(pic_urls)[0]
    if "?" in cover and re.search(r"(auth_key|authkey|sign|token)=", cover, re.I):
        cover = cover.split("?", 1)[0]
    cover = resolve_url(mirror + "/", cover) if cover else ""
    if cover:
        cover = hguo_pic_proxy(cover)
    else:
        cover = ""
    desc = ""
    for tag in re.findall(r'<meta[^>]+>', body, re.I):
        if attrs(tag, "property", "name").lower() in ("description", "og:description"):
            desc = attrs(tag, "content")
            break
    episodes = hguo_episodes(body, url, source_id)
    if not episodes:
        media = hguo_media_from_page(body, url)
        if media:
            episodes = [{"key": "1", "title": "正片", "url": url, "media": media}]
    drama = {"vod_id": "huangguoai:" + source_id, "vod_name": (title or "短剧")[:200],
             "vod_pic": cover, "vod_content": desc, "vod_remarks": "共%d集" % len(episodes) if episodes else "",
             "type_name": "黄果AI", "vod_year": "", "vod_area": ""}
    return drama, episodes
def hguo_episodes(body, page_url, source_id):
    out = []
    seen = set()
    for match in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.S | re.I):
        href = html_unescape(match.group(1))
        title = clean_text(match.group(2))
        if re.fullmatch(r"(立即|马上|开始|在线|正片)?(播放|观看|观看正片|播放正片)", title):
            title = ""
        if not re.search(r"/(video|detail)/", href):
            continue
        full = resolve_url(page_url, href)
        path = urllib.parse.urlparse(full).path
        key = None
        m = re.search(r"/video/([^/]+)/([^/]+)/?$", path)
        if m and m.group(1) == source_id:
            key = m.group(2)
        elif re.search(r"/video/" + re.escape(source_id) + r"/?$", path):
            key = "1"
        if not key:
            m = re.search(r"/detail/" + re.escape(source_id) + r"/([^/]+)/?$", path)
            if m:
                key = m.group(1)
        if not key or full in seen:
            continue
        seen.add(full)
        index = episode_number(title, len(out) + 1)
        out.append({"key": str(key), "title": title or ("第%d集" % index), "url": full,
                    "index": index})
    out.sort(key=lambda e: episode_number(e["title"], e.get("index", 1)))
    return out
def hguo_media_from_page(body, page_url):
    m = re.search(r'<script\b[^>]*id=["\']videoInitialData["\'][^>]*>(.*?)</script>', body, re.S | re.I)
    if m:
        try:
            data = json.loads(html_unescape(m.group(1)))
        except Exception:
            data = None
        if isinstance(data, dict):
            for field in ("videoSrc", "videoUrl", "playUrl"):
                media = data.get(field)
                if isinstance(media, str) and re.search(r"\.(m3u8|mp4)", media, re.I):
                    return resolve_url(page_url, media)
            eps = data.get("epPlaySrcs")
            if isinstance(eps, dict):
                ep = re.search(r"/ep-(\d+)(?:/|$)", page_url)
                preferred = ep.group(1) if ep else first_non_empty(data.get("ep"), data.get("episode"))
                keys = sorted(eps.keys(), key=lambda k: episode_number(k, 1))
                if preferred and preferred in eps:
                    keys = [preferred] + [k for k in keys if k != preferred]
                for key in keys:
                    media = eps[key]
                    if isinstance(media, str) and re.search(r"\.(m3u8|mp4)", media, re.I):
                        return resolve_url(page_url, media)
    for pattern in (r'data-hls=["\']([^"\']+)["\']', r'data-play-src=["\']([^"\']+)["\']',
                    r'["\']?(?:videoSrc|videoUrl|playUrl|src|url)["\']?\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4)(?:[^"\']*)?)["\']'):
        m = re.search(pattern, body, re.I)
        if m and re.search(r"\.(m3u8|mp4)", m.group(1), re.I):
            return resolve_url(page_url, m.group(1))
    return ""
HGUOV_BASE = "https://huangguo.video"
def hguov_text(url, referer=None, timeout=12):
    last = ""
    for attempt in range(4):
        last = http_text(url, headers={"User-Agent": UA_ANDROID}, timeout=timeout)
        if last and len(last) > 500:
            return last
        time.sleep(1.2 * (attempt + 1))
    return last
def hguov_categories():
    cached = cache_get("hguov:cats")
    if cached:
        return cached
    out = []
    seen = set()
    try:
        body = hguov_text(HGUOV_BASE + "/videos", referer=HGUOV_BASE + "/")
        for m in re.finditer(r'href="(/videos\?category=(\d+))"[^>]*>\s*([^<]{1,40})\s*<', body):
            cid, name = m.group(2), clean_text(m.group(3)).strip()
            if cid in seen or not name or "查看全部" in name or "全部" == name:
                continue
            seen.add(cid)
            out.append({"type_id": "hguov:" + cid, "type_name": "黄果视频·" + name[:20]})
    except Exception as exc:
        log("黄果视频分类失败", exc)
    cache_set("hguov:cats", out, 1800)
    return out
def hguov_catalog(cat, page):
    url = HGUOV_BASE + "/videos?page=%d" % max(1, int(page or 1))
    if cat and str(cat) != "0":
        url += "&category=" + urllib.parse.quote(str(cat))
    body = hguov_text(url, referer=HGUOV_BASE + "/")
    out = []
    seen = set()
    for block in re.finditer(r'class="video-card[^"]*"[^>]*>(.*?)</a>', body, re.S | re.I):
        card = block.group(0)
        href = re.search(r'href="(/(?:series|video)/[^"/]+)"', card)
        if not href:
            continue
        code = href.group(1).rsplit("/", 1)[-1]
        if code in seen:
            continue
        seen.add(code)
        img = re.search(r'<img[^>]+(?:data-src|data-original|src)="([^"]+)"', card, re.I)
        cover = resolve_url(HGUOV_BASE + "/", html_unescape(img.group(1))) if img else ""
        title = ""
        tm = re.search(r'\balt="([^"]+)"', card)
        if tm:
            title = clean_text(tm.group(1))
        if not title:
            pm = re.search(r'<p[^>]*>([^<]+)</p>', card)
            if pm:
                title = clean_text(pm.group(1))
        if not title:
            inner = re.sub(r"<[^>]+>", " ", card)
            title = clean_text(inner)[:80]
        if title:
            out.append({
                "vod_id": "hguov:" + code,
                "vod_name": title[:120],
                "vod_pic": cover,
                "vod_remarks": "黄果视频",
            })
    return out
def hguov_detail(source_id):
    body = hguov_text(HGUOV_BASE + "/series/" + urllib.parse.quote(source_id) + "/",
                      referer=HGUOV_BASE + "/")
    title = ""
    tm = re.search(r"<title>(.*?)</title>", body, re.S)
    if tm:
        title = clean_text(tm.group(1)).replace("· 黄果剧场", "").strip()
    cover = ""
    cm = re.search(r'<img[^>]+src="(/uploads/content/series/[^"]+\.(?:webp|jpg|jpeg|png))"', body, re.I)
    if cm:
        cover = resolve_url(HGUOV_BASE + "/", html_unescape(cm.group(1)))
    if not cover:
        cm2 = re.search(r'<img[^>]+src="([^"]*uploads/content[^"]+)"', body, re.I)
        if cm2:
            cover = resolve_url(HGUOV_BASE + "/", html_unescape(cm2.group(1)))
    episodes = []
    seen = set()
    for m in re.finditer(r'href="(/video/([^"/]+))"', body):
        ep_url, code = m.group(1), m.group(2)
        if code in seen:
            continue
        seen.add(code)
        episodes.append({"key": code, "title": "第%d集" % (len(episodes) + 1), "index": len(episodes) + 1})
    if not episodes:
        vbody = hguov_text(HGUOV_BASE + "/video/" + urllib.parse.quote(source_id) + "/",
                           referer=HGUOV_BASE + "/series/" + source_id + "/")
        if not title:
            vtm = re.search(r"<title>(.*?)</title>", vbody, re.S)
            if vtm:
                title = clean_text(vtm.group(1)).replace("· 黄果剧场", "").strip()
        hls = re.search(r'data-hls="([^"]+)"', vbody)
        if hls:
            media = urllib.parse.urljoin(HGUOV_BASE + "/video/" + source_id + "/", html_unescape(hls.group(1)))
            episodes.append({"key": source_id, "title": "正片", "index": 1,
                             "media": media, "media_only": True})
    if not title:
        title = "黄果视频"
    drama = {
        "vod_id": "hguov:" + source_id,
        "vod_name": title[:120],
        "vod_pic": cover,
        "vod_remarks": "共%d集" % len(episodes) if episodes else "黄果视频",
    }
    episodes.sort(key=lambda e: e.get("index", 0))
    return drama, episodes
def hguov_play(source_id, key):
    code = str(key or "") or str(source_id or "")
    body = hguov_text(HGUOV_BASE + "/video/" + urllib.parse.quote(code) + "/")
    hls = re.search(r'data-hls="([^"]+)"', body)
    if hls:
        return urllib.parse.urljoin(HGUOV_BASE + "/video/" + code + "/", html_unescape(hls.group(1)))
    return ""
JUGU_API = "https://api.huangju.net"
JUGU_WEB = "https://huangju.net"
def jugu_token():
    token = cache_get("jugu:token")
    if token:
        return token
    device_id = uuid4()
    data = http_json(JUGU_API + "/auth/guest", method="POST",
                     headers={"User-Agent": UA_ANDROID, "Content-Type": "application/json"},
                     data=json.dumps({"deviceId": device_id}).encode("utf-8"))
    token = ""
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, dict):
            token = str(inner.get("token") or "")
        elif isinstance(inner, str):
            token = inner
        if not token:
            token = str(data.get("token") or "")
    if token:
        cache_set("jugu:token", token, 3300)
        return token
    raise RuntimeError("剧果 guest 登录失败")
def jugu_request(path, params=None):
    token = jugu_token()
    headers = {"User-Agent": UA_ANDROID, "Authorization": "Bearer " + token}
    if params:
        path += "?" + urllib.parse.urlencode(params)
    return http_json(JUGU_API + path, headers=headers)
def jugu_categories():
    cached = cache_get("jugu:categories")
    if cached:
        return cached
    data = jugu_request("/categories")
    cats = [{"type_id": "jugu:new", "type_name": "剧果·最新"}, {"type_id": "jugu:hot", "type_name": "剧果·热门"}]
    rows = None
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, list):
            rows = inner
        else:
            rows = data.get("categories")
    if isinstance(rows, list):
        seen = {"@new", "hot"}
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = first_non_empty(row.get("name"), row.get("title"))
            key = first_non_empty(row.get("slug"), row.get("id"), name)
            if not name or not key or str(key) in seen:
                continue
            seen.add(str(key))
            cats.append({"type_id": "jugu:cat:" + str(key), "type_name": str(name)})
    cache_set("jugu:categories", cats, 1800)
    return cats
def jugu_drama_from(row):
    if not isinstance(row, dict):
        return None
    id_value = row.get("id")
    slug = row.get("slug")
    if id_value is None and not slug:
        return None
    source_id = first_non_empty(slug, "")
    if id_value is not None:
        source_id = (source_id + "-" if source_id else "") + str(id_value)
    if not source_id:
        return None
    title = first_non_empty(row.get("title"), row.get("name"))
    if not title:
        return None
    cover = first_non_empty(row.get("coverUrl"), row.get("cover"))
    cover = resolve_url(JUGU_WEB + "/", cover) if cover else ""
    desc = first_non_empty(row.get("description"), row.get("synopsis"))
    remark = ""
    total = row.get("totalEpisodes")
    if total:
        remark = "全%s集" % total
    status = row.get("status")
    if status in ("ongoing", "updating"):
        remark = "更新中"
    elif status == "completed":
        remark = "已完结"
    return {"vod_id": "jugu:" + str(source_id), "vod_name": str(title)[:200], "vod_pic": cover,
            "vod_content": desc, "vod_remarks": remark, "type_name": "剧果",
            "vod_year": str(row.get("year") or ""), "vod_area": ""}
def jugu_catalog(cat, page):
    if cat.startswith("cat:"):
        params = {"page": page, "category": cat[4:]}
    elif cat == "hot":
        params = {"page": page, "sort": "hot"}
    else:
        params = {"page": page, "sort": "new"}
    try:
        data = jugu_request("/dramas", params)
    except Exception:
        return []
    rows = None
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, list):
            rows = inner
        elif isinstance(inner, dict):
            rows = inner.get("items") or inner.get("list")
        if rows is None:
            rows = data.get("items") or data.get("dramas")
    out = []
    if isinstance(rows, list):
        for row in rows:
            drama = jugu_drama_from(row)
            if drama:
                out.append(drama)
    return out
def jugu_detail(source_id):
    data = jugu_request("/dramas/" + urllib.parse.quote(str(source_id)))
    row = None
    if isinstance(data, dict):
        row = data.get("data")
        if not isinstance(row, dict):
            row = data
    if not isinstance(row, dict):
        raise RuntimeError("剧果未返回有效详情")
    drama = jugu_drama_from(row) or {}
    episodes = []
    rows = row.get("episodes")
    if isinstance(rows, list):
        for ep in rows:
            if not isinstance(ep, dict):
                continue
            ep_id = first_non_empty(ep.get("id"), ep.get("episodeId"))
            playable = ep.get("playable", True)
            if not ep_id or playable is False:
                continue
            number = episode_number(ep.get("epNo"), len(episodes) + 1)
            title = first_non_empty(ep.get("title"), "第%d集" % number)
            episodes.append({"key": str(ep_id), "title": str(title), "index": number})
    episodes.sort(key=lambda e: e.get("index", 0))
    return drama, episodes
def jugu_play(ep_id):
    data = http_json(JUGU_API + "/play/" + urllib.parse.quote(str(ep_id)),
                     headers={"User-Agent": UA_ANDROID, "Authorization": "Bearer " + jugu_token()})
    row = None
    if isinstance(data, dict):
        row = data.get("data")
        if not isinstance(row, dict):
            row = data
    if not isinstance(row, dict):
        raise RuntimeError("剧果未返回播放地址")
    media = first_non_empty(row.get("url"), row.get("playUrl"), row.get("m3u8"))
    if not media:
        raise RuntimeError("剧果播放地址为空")
    return resolve_url(JUGU_WEB + "/", media)
def jugu_search(keyword):
    try:
        data = jugu_request("/dramas", {"q": keyword, "page": 1})
    except Exception:
        return []
    rows = None
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, list):
            rows = inner
        elif isinstance(inner, dict):
            rows = inner.get("items") or inner.get("list")
        if rows is None:
            rows = data.get("items") or data.get("dramas")
    out = []
    if isinstance(rows, list):
        for row in rows:
            drama = jugu_drama_from(row)
            if drama:
                out.append(drama)
    return out
JUGU_PLAY_CACHE = {}
JUGU_M3U8_CACHE = {}
def jugu_play_cached(ep_id):
    now = time.time()
    hit = JUGU_PLAY_CACHE.get(str(ep_id))
    if hit and now - hit[0] < 60:
        return hit[1]
    media = jugu_play(str(ep_id))
    JUGU_PLAY_CACHE[str(ep_id)] = (now, media)
    return media
def jugu_prefetch_m3u8(media, ep):
    try:
        ck = jugu_cookies()
        if not ck:
            return
        headers = {"User-Agent": UA_ANDROID, "Cookie": "; ".join("%s=%s" % (k, v) for k, v in ck.items())}
        status, resp_headers, body = http_request(media, headers=headers, timeout=15)
        if status >= 400 or body[:7] != b"#EXTM3U":
            return
        try:
            jugu_self = _stream_ensure() + "/jugu_m3u8"
        except Exception:
            jugu_self = ""
        payload = rewrite_m3u8(body, "jugu", {"url": media, "ep": ep, "jugu_self": jugu_self})
        JUGU_M3U8_CACHE[media] = (time.time(), payload)
    except Exception:
        pass
def jugu_m3u8_cached(media):
    hit = JUGU_M3U8_CACHE.get(media)
    if hit and time.time() - hit[0] < 90:
        return hit[1]
    return None
DSD_WEB = "https://www.dsd.com.se"
DSD_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
DSD_COOKIES = {}
def dsd_headers(referer=None):
    headers = {"User-Agent": DSD_UA}
    if referer:
        headers["Referer"] = referer
    if DSD_COOKIES:
        headers["Cookie"] = "; ".join("%s=%s" % (k, v) for k, v in DSD_COOKIES.items())
    return headers
def dsd_session_request(url, referer=None, timeout=12):
    try:
        status, hdrs, body = http_request(url, headers=dsd_headers(referer), timeout=timeout)
    except Exception:
        raise
    raw = hdrs.get("set-cookie", "")
    for part in raw.split(","):
        seg = part.strip()
        if not seg:
            continue
        pair = seg.split(";", 1)[0]
        if "=" in pair:
            key, value = pair.split("=", 1)
            key = key.strip()
            if key:
                DSD_COOKIES[key] = value.strip()
    return status, hdrs, body
def dsd_session_text(url, referer=None, timeout=12, encoding="utf-8"):
    _, _, body = dsd_session_request(url, referer=referer, timeout=timeout)
    return body.decode(encoding, "ignore")
def dsd_categories():
    cached = cache_get("dsd:categories")
    if cached:
        return cached
    cats = []
    try:
        body = http_text(DSD_WEB + "/", headers=dsd_headers(DSD_WEB + "/"), timeout=10)
    except Exception:
        body = ""
    for match in re.finditer(r'<a\b[^>]*href="([^"]*index\.php/vod/type/id/(\d+)\.html)"[^>]*>(.*?)</a>',
                             body, re.S | re.I):
        name = clean_text(match.group(3))
        if name and not re.fullmatch(r"\d+", name):
            cats.append({"type_id": "dsd:" + match.group(2), "type_name": "帝果·" + name[:24]})
    if not cats:
        cats = [{"type_id": "dsd:all", "type_name": "帝果·全部"}]
    cache_set("dsd:categories", cats, 1800)
    return cats
def dsd_catalog(cat, page):
    url = "%s/index.php/vod/type/id/%s/page/%d.html" % (DSD_WEB, cat, page)
    try:
        body = http_text(url, headers=dsd_headers(DSD_WEB + "/"), timeout=10)
    except Exception:
        return []
    out = []
    seen = set()
    for match in re.finditer(r'<a\b[^>]*href="([^"]*vod/play/id/(\d+)/[^"]*\.html)"[^>]*>(.*?)</a>',
                             body, re.S | re.I):
        source_id = match.group(2)
        if source_id in seen:
            continue
        seen.add(source_id)
        block = match.group(0)
        title = ""
        m_desc = re.search(r'video-desc[^>]*>\s*([^<]{1,300})', block, re.I)
        if m_desc:
            title = clean_text(m_desc.group(1))
        if not title:
            title = clean_text(match.group(3))
        if not title:
            title = attrs(block, "title")
        if not title:
            continue
        cover = ""
        m_img = re.search(r'<img\b[^>]*>', block, re.I)
        if m_img:
            cover = attrs(m_img.group(0), "data-src", "data-original", "src")
        if not cover:
            m_bg = re.search(r'background(?:-image)?\s*:\s*url\(["\']?([^"\')]+)', block, re.I)
            if m_bg:
                cover = m_bg.group(1)
        cover = resolve_url(url, cover) if cover else ""
        remark = ""
        m_ep = re.search(r'共(\d+)集|(\d+)集', block, re.I)
        if m_ep:
            remark = "共%s集" % (m_ep.group(1) or m_ep.group(2))
        out.append({"vod_id": "dsd:" + source_id, "vod_name": str(title)[:200], "vod_pic": cover,
                    "vod_content": "", "vod_remarks": remark, "type_name": "帝果", "vod_year": "", "vod_area": ""})
        if len(out) >= 60:
            break
    return out
def dsd_parse_player(body):
    for match in re.finditer(r'\bplayer_[a-zA-Z0-9_]+\s*=\s*', body):
        decoder = json.JSONDecoder()
        try:
            player, _ = decoder.raw_decode(body[match.end():])
        except Exception:
            continue
        if isinstance(player, dict) and player.get("id") is not None and player.get("url") is not None:
            return player
    return None
def dsd_route(action, reference, page_url, source_id):
    full = urllib.parse.urljoin(page_url, html_unescape(reference))
    parsed = urllib.parse.urlparse(full)
    if parsed.hostname and parsed.hostname.lower() != urllib.parse.urlparse(DSD_WEB).hostname:
        return None
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2 or parts[0] != "index.php" or parts[1] != "vod" or len(parts) < 5:
        if parsed.path.startswith("/index.php"):
            parts = [p for p in parsed.path.lstrip("/").split("/") if p]
            if len(parts) < 4 or parts[1] != "vod":
                return None
        else:
            return None
    index = 1
    if parts[0] != "index.php":
        return None
    while index + 1 < len(parts):
        if parts[index] == "id" and index + 1 < len(parts):
            if parts[index + 1] != source_id:
                return None
        index += 2
    values = {}
    for idx in range(2, len(parts) - 1, 2):
        values[parts[idx]] = parts[idx + 1]
    return values
def dsd_detail(source_id):
    url = "%s/index.php/vod/play/id/%s/sid/1/nid/1.html" % (DSD_WEB, source_id)
    body = http_text(url, headers=dsd_headers(DSD_WEB + "/"), timeout=12)
    player = dsd_parse_player(body)
    title = ""
    cover = ""
    for heading in re.findall(r"<h[123]\b[^>]*>(.*?)</h[123]>", body, re.S | re.I):
        title = clean_text(heading)
        if title:
            break
    if player and isinstance(player, dict):
        data = player.get("vod_data")
        if isinstance(data, dict):
            title = first_non_empty(data.get("vod_name"), title)
        poster = player.get("poster")
        if isinstance(poster, str) and poster:
            cover = resolve_url(url, poster)
    if not cover:
        m = re.search(r'class="[^"]*thumb[^"]*"[^>]*>\s*<img[^>]+src="([^"]+)"', body, re.I)
        if m:
            cover = resolve_url(url, html_unescape(m.group(1)))
    if not title:
        raise RuntimeError("帝果详情缺少视频名称")
    episodes = []
    seen = set()
    for match in re.finditer(r'<a\b[^>]*href="([^"]*index\.php/vod/play/id/%s/sid/(\d+)/nid/(\d+)\.html)"[^>]*>(.*?)</a>'
                             % re.escape(source_id), body, re.S | re.I):
        sid, nid = match.group(2), match.group(3)
        key = "%s-%s" % (sid, nid)
        if key in seen:
            continue
        seen.add(key)
        ep_title = clean_text(match.group(4))
        if not ep_title:
            ep_title = "第%s集" % nid
        episodes.append({"key": key, "title": ep_title[:100], "line": int(sid), "ep": int(nid)})
    if player and isinstance(player, dict):
        if not episodes:
            episodes.append({"key": "1-1", "title": "正片", "line": 1, "ep": 1})
        for field in ("link_pre", "link_next"):
            link = player.get(field)
            if isinstance(link, str) and link:
                values = dsd_route("play", link, url, source_id)
                if values and values.get("id") == source_id:
                    key = "%s-%s" % (values.get("sid", "1"), values.get("nid", "1"))
                    if key not in seen:
                        seen.add(key)
                        episodes.append({"key": key, "title": "第%s集" % values.get("nid"),
                                         "line": int(values.get("sid", 1)), "ep": int(values.get("nid", 1))})
    episodes.sort(key=lambda e: e["ep"])
    drama = {"vod_id": "dsd:" + source_id, "vod_name": title[:200], "vod_pic": cover,
             "vod_content": "", "vod_remarks": "共%d集" % len(episodes) if episodes else "",
             "type_name": "帝果", "vod_year": "", "vod_area": ""}
    return drama, episodes
_DSD_AA_MAP = [("(c^_^o)", "0"), ("(ﾟΘﾟ)", "1"), ("(o^_^o)", "3"), ("(ﾟｰﾟ)", "4")]
def _dsd_split_top(value):
    parts = []
    depth = 0
    start = 0
    for index, char in enumerate(value):
        if char == "(":
            depth += 1
        elif char == ")":
            if depth > 0:
                depth -= 1
        elif char == "+" and depth == 0:
            part = value[start:index].strip()
            if part:
                parts.append(part)
            start = index + 1
    part = value[start:].strip()
    if part:
        parts.append(part)
    return parts
def _dsd_eval_expr(text):
    pos = 0
    def skip():
        nonlocal pos
        while pos < len(text) and text[pos] in " \t\r\n":
            pos += 1
    def parse_expr():
        nonlocal pos
        value, ok = parse_term()
        if not ok:
            return 0, False
        while True:
            skip()
            if pos < len(text) and text[pos] in "+-":
                op = text[pos]
                pos += 1
                right, ok2 = parse_term()
                if not ok2:
                    return 0, False
                value = value + right if op == "+" else value - right
            else:
                return value, True
    def parse_term():
        nonlocal pos
        value, ok = parse_factor()
        if not ok:
            return 0, False
        while True:
            skip()
            if pos < len(text) and text[pos] in "*/%":
                op = text[pos]
                pos += 1
                right, ok2 = parse_factor()
                if not ok2:
                    return 0, False
                if op == "*":
                    value = value * right
                elif op == "/":
                    if right == 0:
                        return 0, False
                    value = value // right
                else:
                    if right == 0:
                        return 0, False
                    value = value % right
            else:
                return value, True
    def parse_factor():
        nonlocal pos
        skip()
        sign = 1
        if pos < len(text) and text[pos] in "+-":
            sign = -1 if text[pos] == "-" else 1
            pos += 1
            skip()
        if pos < len(text) and text[pos] == "(":
            pos += 1
            value, ok = parse_expr()
            if not ok:
                return 0, False
            skip()
            if pos < len(text) and text[pos] == ")":
                pos += 1
                return sign * value, True
            return 0, False
        start = pos
        while pos < len(text) and text[pos].isdigit():
            pos += 1
        if start == pos:
            return 0, False
        return sign * int(text[start:pos]), True
    value, ok = parse_expr()
    skip()
    return (value, True) if ok and pos == len(text) else (0, False)
def _dsd_aa_digit(part):
    part = part.strip()
    if not part:
        return "", False
    if "(oﾟｰﾟo)" in part:
        return "u", True
    if "(ﾟДﾟ).ﾟΘﾟﾉ" in part:
        return "b", True
    for old, new in _DSD_AA_MAP:
        part = part.replace(old, new)
    if len(part) > 4096 or re.sub(r"[0-9()+\-*/% \t\r\n]", "", part):
        return "", False
    value, ok = _dsd_eval_expr(part)
    return (str(value), True) if ok else ("", False)
def decode_dsd_aaencode(raw):
    marker = "(ﾟДﾟ) ['_'] ( (ﾟДﾟ) ['_']"
    tail = "+ (ﾟДﾟ)[ﾟoﾟ]"
    start = raw.find(marker)
    if start < 0:
        return ""
    body = raw[start:]
    end = body.rfind(tail)
    if end < 0:
        return ""
    tokens = body[:end].split("(ﾟДﾟ)[ﾟεﾟ]+")
    decoded = []
    for token in tokens[1:]:
        digits = ""
        for part in _dsd_split_top(token):
            digit, ok = _dsd_aa_digit(part)
            if not ok:
                return ""
            digits += digit
        try:
            if digits.startswith("u") and len(digits) == 5:
                decoded.append(chr(int(digits[1:], 16)))
            elif digits and not re.sub(r"[0-7]", "", digits):
                decoded.append(chr(int(digits, 8)))
        except Exception:
            continue
    return "".join(decoded)
def dsd_signed_path(body):
    for match in re.finditer(r"<script\b[^>]*>(.*?)</script>", body, re.S | re.I):
        script = match.group(1)
        if "(ﾟДﾟ)" not in script:
            continue
        decoded = decode_dsd_aaencode(script)
        m = re.search(r'\bvar\s+vPath\s*=\s*["\']([^"\']+)["\']', decoded)
        if m:
            return m.group(1).strip()
    return ""
def dsd_issued_media(player, page_url):
    raw = str(player.get("url") or "")
    if not raw:
        return ""
    encrypt = str(player.get("encrypt") or "0")
    if encrypt == "1":
        raw = urllib.parse.unquote(raw)
    elif encrypt == "2":
        try:
            raw = urllib.parse.unquote(base64.b64decode(raw).decode("utf-8", "ignore"))
        except Exception:
            pass
    if not re.search(r"\.(m3u8|mp4)(\?|$)", raw, re.I):
        return ""
    return resolve_url(page_url, raw)
def dsd_play(line, ep):
    source_id = None
    raise NotImplementedError
HDOU_HOSTS = ["https://tideember.cc", "https://xqjurgek.top"]
HDOU_PLATFORM_KEY = "7961beb44246e3012ce228d6b5ced05a"
_AES_SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16]
_AES_INV_SBOX = [0] * 256
for _i in range(256):
    _AES_INV_SBOX[_AES_SBOX[_i]] = _i
_AES_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]
def _aes_mul(a, b):
    result = 0
    for _ in range(8):
        if b & 1:
            result ^= a
        high = a & 0x80
        a = (a << 1) & 0xFF
        if high:
            a ^= 0x1b
        b >>= 1
    return result
def _aes_xtime(a):
    a <<= 1
    if a & 0x100:
        a ^= 0x11b
    return a & 0xFF
_AES_T0 = [0] * 256
_AES_T1 = [0] * 256
_AES_T2 = [0] * 256
_AES_T3 = [0] * 256
for _i in range(256):
    _s = _AES_SBOX[_i]
    _s2 = _aes_xtime(_s)
    _s3 = _s ^ _s2
    _AES_T0[_i] = (_s2 << 24) | (_s << 16) | (_s << 8) | _s3
    _AES_T1[_i] = (_s3 << 24) | (_s2 << 16) | (_s << 8) | _s
    _AES_T2[_i] = (_s << 24) | (_s3 << 16) | (_s2 << 8) | _s
    _AES_T3[_i] = (_s << 24) | (_s << 16) | (_s3 << 8) | _s2
def _aes_expand_key_words(key):
    nk = len(key) // 4
    nr = nk + 6
    words = [int.from_bytes(key[4 * i:4 * i + 4], "big") for i in range(nk)]
    for index in range(nk, 4 * (nr + 1)):
        temp = words[index - 1]
        if index % nk == 0:
            temp = ((temp << 8) | (temp >> 24)) & 0xFFFFFFFF
            temp = ((_AES_SBOX[(temp >> 24) & 0xFF] << 24) |
                    (_AES_SBOX[(temp >> 16) & 0xFF] << 16) |
                    (_AES_SBOX[(temp >> 8) & 0xFF] << 8) |
                    _AES_SBOX[temp & 0xFF]) ^ (_AES_RCON[index // nk - 1] << 24)
        elif nk > 6 and index % nk == 4:
            temp = ((_AES_SBOX[(temp >> 24) & 0xFF] << 24) |
                    (_AES_SBOX[(temp >> 16) & 0xFF] << 16) |
                    (_AES_SBOX[(temp >> 8) & 0xFF] << 8) |
                    _AES_SBOX[temp & 0xFF])
        words.append(words[index - nk] ^ temp)
    return nr, words
def _aes_encrypt_block_words(block, rk, nr):
    s0 = int.from_bytes(block[0:4], "big") ^ rk[0]
    s1 = int.from_bytes(block[4:8], "big") ^ rk[1]
    s2 = int.from_bytes(block[8:12], "big") ^ rk[2]
    s3 = int.from_bytes(block[12:16], "big") ^ rk[3]
    for rnd in range(1, nr):
        t0 = _AES_T0[(s0 >> 24) & 0xFF] ^ _AES_T1[(s1 >> 16) & 0xFF] ^ \
             _AES_T2[(s2 >> 8) & 0xFF] ^ _AES_T3[s3 & 0xFF] ^ rk[4 * rnd]
        t1 = _AES_T0[(s1 >> 24) & 0xFF] ^ _AES_T1[(s2 >> 16) & 0xFF] ^ \
             _AES_T2[(s3 >> 8) & 0xFF] ^ _AES_T3[s0 & 0xFF] ^ rk[4 * rnd + 1]
        t2 = _AES_T0[(s2 >> 24) & 0xFF] ^ _AES_T1[(s3 >> 16) & 0xFF] ^ \
             _AES_T2[(s0 >> 8) & 0xFF] ^ _AES_T3[s1 & 0xFF] ^ rk[4 * rnd + 2]
        t3 = _AES_T0[(s3 >> 24) & 0xFF] ^ _AES_T1[(s0 >> 16) & 0xFF] ^ \
             _AES_T2[(s1 >> 8) & 0xFF] ^ _AES_T3[s2 & 0xFF] ^ rk[4 * rnd + 3]
        s0, s1, s2, s3 = t0, t1, t2, t3
    out = bytearray(16)
    out[0] = _AES_SBOX[(s0 >> 24) & 0xFF] ^ ((rk[4 * nr] >> 24) & 0xFF)
    out[1] = _AES_SBOX[(s1 >> 16) & 0xFF] ^ ((rk[4 * nr] >> 16) & 0xFF)
    out[2] = _AES_SBOX[(s2 >> 8) & 0xFF] ^ ((rk[4 * nr] >> 8) & 0xFF)
    out[3] = _AES_SBOX[s3 & 0xFF] ^ (rk[4 * nr] & 0xFF)
    out[4] = _AES_SBOX[(s1 >> 24) & 0xFF] ^ ((rk[4 * nr + 1] >> 24) & 0xFF)
    out[5] = _AES_SBOX[(s2 >> 16) & 0xFF] ^ ((rk[4 * nr + 1] >> 16) & 0xFF)
    out[6] = _AES_SBOX[(s3 >> 8) & 0xFF] ^ ((rk[4 * nr + 1] >> 8) & 0xFF)
    out[7] = _AES_SBOX[s0 & 0xFF] ^ (rk[4 * nr + 1] & 0xFF)
    out[8] = _AES_SBOX[(s2 >> 24) & 0xFF] ^ ((rk[4 * nr + 2] >> 24) & 0xFF)
    out[9] = _AES_SBOX[(s3 >> 16) & 0xFF] ^ ((rk[4 * nr + 2] >> 16) & 0xFF)
    out[10] = _AES_SBOX[(s0 >> 8) & 0xFF] ^ ((rk[4 * nr + 2] >> 8) & 0xFF)
    out[11] = _AES_SBOX[s1 & 0xFF] ^ (rk[4 * nr + 2] & 0xFF)
    out[12] = _AES_SBOX[(s3 >> 24) & 0xFF] ^ ((rk[4 * nr + 3] >> 24) & 0xFF)
    out[13] = _AES_SBOX[(s0 >> 16) & 0xFF] ^ ((rk[4 * nr + 3] >> 16) & 0xFF)
    out[14] = _AES_SBOX[(s1 >> 8) & 0xFF] ^ ((rk[4 * nr + 3] >> 8) & 0xFF)
    out[15] = _AES_SBOX[s2 & 0xFF] ^ (rk[4 * nr + 3] & 0xFF)
    return bytes(out)
def _aes_encrypt_block_int(ctr_int, rk, nr):
    s0 = (ctr_int >> 96) ^ rk[0]
    s1 = ((ctr_int >> 64) & 0xFFFFFFFF) ^ rk[1]
    s2 = ((ctr_int >> 32) & 0xFFFFFFFF) ^ rk[2]
    s3 = (ctr_int & 0xFFFFFFFF) ^ rk[3]
    for rnd in range(1, nr):
        t0 = _AES_T0[(s0 >> 24) & 0xFF] ^ _AES_T1[(s1 >> 16) & 0xFF] ^ \
             _AES_T2[(s2 >> 8) & 0xFF] ^ _AES_T3[s3 & 0xFF] ^ rk[4 * rnd]
        t1 = _AES_T0[(s1 >> 24) & 0xFF] ^ _AES_T1[(s2 >> 16) & 0xFF] ^ \
             _AES_T2[(s3 >> 8) & 0xFF] ^ _AES_T3[s0 & 0xFF] ^ rk[4 * rnd + 1]
        t2 = _AES_T0[(s2 >> 24) & 0xFF] ^ _AES_T1[(s3 >> 16) & 0xFF] ^ \
             _AES_T2[(s0 >> 8) & 0xFF] ^ _AES_T3[s1 & 0xFF] ^ rk[4 * rnd + 2]
        t3 = _AES_T0[(s3 >> 24) & 0xFF] ^ _AES_T1[(s0 >> 16) & 0xFF] ^ \
             _AES_T2[(s1 >> 8) & 0xFF] ^ _AES_T3[s2 & 0xFF] ^ rk[4 * rnd + 3]
        s0, s1, s2, s3 = t0, t1, t2, t3
    o0 = ((_AES_SBOX[(s0 >> 24) & 0xFF] ^ ((rk[4 * nr] >> 24) & 0xFF)) << 24) | \
         ((_AES_SBOX[(s1 >> 16) & 0xFF] ^ ((rk[4 * nr] >> 16) & 0xFF)) << 16) | \
         ((_AES_SBOX[(s2 >> 8) & 0xFF] ^ ((rk[4 * nr] >> 8) & 0xFF)) << 8) | \
         (_AES_SBOX[s3 & 0xFF] ^ (rk[4 * nr] & 0xFF))
    o1 = ((_AES_SBOX[(s1 >> 24) & 0xFF] ^ ((rk[4 * nr + 1] >> 24) & 0xFF)) << 24) | \
         ((_AES_SBOX[(s2 >> 16) & 0xFF] ^ ((rk[4 * nr + 1] >> 16) & 0xFF)) << 16) | \
         ((_AES_SBOX[(s3 >> 8) & 0xFF] ^ ((rk[4 * nr + 1] >> 8) & 0xFF)) << 8) | \
         (_AES_SBOX[s0 & 0xFF] ^ (rk[4 * nr + 1] & 0xFF))
    o2 = ((_AES_SBOX[(s2 >> 24) & 0xFF] ^ ((rk[4 * nr + 2] >> 24) & 0xFF)) << 24) | \
         ((_AES_SBOX[(s3 >> 16) & 0xFF] ^ ((rk[4 * nr + 2] >> 16) & 0xFF)) << 16) | \
         ((_AES_SBOX[(s0 >> 8) & 0xFF] ^ ((rk[4 * nr + 2] >> 8) & 0xFF)) << 8) | \
         (_AES_SBOX[s1 & 0xFF] ^ (rk[4 * nr + 2] & 0xFF))
    o3 = ((_AES_SBOX[(s3 >> 24) & 0xFF] ^ ((rk[4 * nr + 3] >> 24) & 0xFF)) << 24) | \
         ((_AES_SBOX[(s0 >> 16) & 0xFF] ^ ((rk[4 * nr + 3] >> 16) & 0xFF)) << 16) | \
         ((_AES_SBOX[(s1 >> 8) & 0xFF] ^ ((rk[4 * nr + 3] >> 8) & 0xFF)) << 8) | \
         (_AES_SBOX[s2 & 0xFF] ^ (rk[4 * nr + 3] & 0xFF))
    return (o0 << 96) | (o1 << 64) | (o2 << 32) | o3
def _aes_ctr_pure(key, iv, data):
    nr, rk = _aes_expand_key_words(key)
    ctr = int.from_bytes(iv[:16], "big")
    mask = (1 << 128) - 1
    out = bytearray(len(data))
    offset = 0
    size = len(data)
    while offset < size:
        keystream = _aes_encrypt_block_int(ctr, rk, nr)
        take = min(16, size - offset)
        chunk = data[offset:offset + take]
        if take == 16:
            block = (int.from_bytes(chunk, "big") ^ keystream).to_bytes(16, "big")
        else:
            block = (int.from_bytes(chunk, "big") << (8 * (16 - take)) ^ keystream).to_bytes(16, "big")[:take]
        out[offset:offset + take] = block
        ctr = (ctr + 1) & mask
        offset += take
    return bytes(out)
def _aes_expand_key(key):
    nk = len(key) // 4
    nr = nk + 6
    words = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
    for index in range(nk, 4 * (nr + 1)):
        temp = list(words[index - 1])
        if index % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [_AES_SBOX[b] for b in temp]
            temp[0] ^= _AES_RCON[index // nk - 1]
        elif nk > 6 and index % nk == 4:
            temp = [_AES_SBOX[b] for b in temp]
        words.append([words[index - nk][i] ^ temp[i] for i in range(4)])
    return nr, [words[i * 4:(i + 1) * 4] for i in range(nr + 1)]
def _aes_encrypt_block(block, round_keys, nr):
    state = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
    for r in range(4):
        for c in range(4):
            state[r][c] ^= round_keys[0][c][r]
    for rnd in range(1, nr):
        for r in range(4):
            for c in range(4):
                state[r][c] = _AES_SBOX[state[r][c]]
        state = [[state[r][(c + r) % 4] for c in range(4)] for r in range(4)]
        for c in range(4):
            a = [state[r][c] for r in range(4)]
            state[0][c] = _aes_mul(a[0], 2) ^ _aes_mul(a[1], 3) ^ a[2] ^ a[3]
            state[1][c] = a[0] ^ _aes_mul(a[1], 2) ^ _aes_mul(a[2], 3) ^ a[3]
            state[2][c] = a[0] ^ a[1] ^ _aes_mul(a[2], 2) ^ _aes_mul(a[3], 3)
            state[3][c] = _aes_mul(a[0], 3) ^ a[1] ^ a[2] ^ _aes_mul(a[3], 2)
        for r in range(4):
            for c in range(4):
                state[r][c] ^= round_keys[rnd][c][r]
    for r in range(4):
        for c in range(4):
            state[r][c] = _AES_SBOX[state[r][c]]
    state = [[state[r][(c + r) % 4] for c in range(4)] for r in range(4)]
    for r in range(4):
        for c in range(4):
            state[r][c] ^= round_keys[nr][c][r]
    out = bytearray(16)
    for r in range(4):
        for c in range(4):
            out[r + 4 * c] = state[r][c]
    return bytes(out)
def _aes_decrypt_block(block, round_keys, nr):
    state = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
    for r in range(4):
        for c in range(4):
            state[r][c] ^= round_keys[nr][c][r]
    for rnd in range(nr - 1, 0, -1):
        state = [[state[r][(c + 4 - r) % 4] for c in range(4)] for r in range(4)]
        for r in range(4):
            for c in range(4):
                state[r][c] = _AES_INV_SBOX[state[r][c]]
        for r in range(4):
            for c in range(4):
                state[r][c] ^= round_keys[rnd][c][r]
        for c in range(4):
            a = [state[r][c] for r in range(4)]
            state[0][c] = _aes_mul(a[0], 14) ^ _aes_mul(a[1], 11) ^ _aes_mul(a[2], 13) ^ _aes_mul(a[3], 9)
            state[1][c] = _aes_mul(a[0], 9) ^ _aes_mul(a[1], 14) ^ _aes_mul(a[2], 11) ^ _aes_mul(a[3], 13)
            state[2][c] = _aes_mul(a[0], 13) ^ _aes_mul(a[1], 9) ^ _aes_mul(a[2], 14) ^ _aes_mul(a[3], 11)
            state[3][c] = _aes_mul(a[0], 11) ^ _aes_mul(a[1], 13) ^ _aes_mul(a[2], 9) ^ _aes_mul(a[3], 14)
    state = [[state[r][(c + 4 - r) % 4] for c in range(4)] for r in range(4)]
    for r in range(4):
        for c in range(4):
            state[r][c] = _AES_INV_SBOX[state[r][c]]
    for r in range(4):
        for c in range(4):
            state[r][c] ^= round_keys[0][c][r]
    out = bytearray(16)
    for r in range(4):
        for c in range(4):
            out[r + 4 * c] = state[r][c]
    return bytes(out)
def aes_cbc_encrypt(plain, key, iv):
    nr, round_keys = _aes_expand_key(key)
    iv = bytes(iv[:16])
    previous = iv
    out = bytearray()
    for offset in range(0, len(plain), 16):
        block = bytes(a ^ b for a, b in zip(plain[offset:offset + 16], previous))
        encrypted = _aes_encrypt_block(block, round_keys, nr)
        out += encrypted
        previous = encrypted
    return bytes(out)
try:
    from Crypto.Cipher import AES as _CryptoAES
except Exception:
    _CryptoAES = None
def aes_cbc_decrypt(data, key, iv):
    if _CryptoAES is not None:
        try:
            cipher = _CryptoAES.new(bytes(key), _CryptoAES.MODE_CBC, bytes(iv[:16]))
            return cipher.decrypt(bytes(data))
        except Exception:
            pass
    nr, round_keys = _aes_expand_key(key)
    iv = bytes(iv[:16])
    previous = iv
    out = bytearray()
    for offset in range(0, len(data), 16):
        block = data[offset:offset + 16]
        decrypted = _aes_decrypt_block(block, round_keys, nr)
        out += bytes(a ^ b for a, b in zip(decrypted, previous))
        previous = block
    return bytes(out)
def hdou_pad(data):
    pad = 16 - len(data) % 16
    return data + bytes([pad]) * pad
def hdou_unpad(data):
    if not data:
        return data
    pad = data[-1]
    if pad < 1 or pad > 16:
        return data
    return data[:-pad]
def hdou_aes_encrypt(plain, key):
    iv = random.randbytes(16)
    return iv + aes_cbc_encrypt(hdou_pad(plain), key, iv)
def hdou_aes_decrypt(data, key):
    if len(data) < 32:
        raise RuntimeError("黄豆密文过短")
    iv, body = data[:16], data[16:]
    plain = aes_cbc_decrypt(body, key, iv)
    return hdou_unpad(plain)
def hdou_host():
    host = cache_get("hdou:host")
    if host:
        return host
    for candidate in HDOU_HOSTS:
        try:
            status, _, _ = http_request(candidate + "/", timeout=6)
            if status < 400:
                cache_set("hdou:host", candidate, 3600)
                return candidate
        except Exception:
            continue
    return HDOU_HOSTS[0]
def hdou_random_hex(length):
    return "".join("%02x" % random.randrange(256) for _ in range(length))
def hdou_call(path, payload):
    path = "/" + path.strip("/")
    host = hdou_host()
    rid = hdou_random_hex(16)
    key = hmac.new(HDOU_PLATFORM_KEY.encode(), bytes.fromhex(rid), hashlib.sha256).digest()
    plain = {"token": "", "deviceId": rid, "data": payload}
    raw = json.dumps(plain, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    gz = gzip.compress(raw)
    body = hdou_aes_encrypt(gz, key)
    timestamp = str(now())
    sign_raw = "Dart|%s|%s|%s|%s" % (rid, rid, timestamp, path)
    sign = hashlib.sha256(sign_raw.encode()).hexdigest()
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120 Safari/537.36"),
        "Accept": "*/*",
        "Origin": host,
        "Referer": host + "/home",
        "Content-Type": "application/octet-stream",
        "version": "2.0.0",
        "deviceType": "web",
        "requestId": rid,
        "sessionId": rid,
        "time": timestamp,
        "sign": sign + "-" + timestamp,
    }
    status, _, resp = http_request(host + "/api" + path, method="POST", headers=headers, data=body, timeout=15)
    if status >= 400:
        raise RuntimeError("黄豆接口 HTTP %d" % status)
    result = hdou_decode_response(resp, key)
    if isinstance(result, dict):
        result_status = result.get("status")
        if result_status not in (None, "y", "Y", "1", 1, "0"):
            raise RuntimeError("黄豆接口拒绝: %s" % first_non_empty(result.get("msg"), result.get("message"), result.get("error"), result_status))
    return result
def hdou_decode_response(resp, key):
    try:
        return json.loads(resp.decode("utf-8"))
    except Exception:
        pass
    plain = hdou_aes_decrypt(resp, key)
    if len(plain) >= 2 and plain[0] == 0x1f and plain[1] == 0x8b:
        plain = gzip.decompress(plain)
    return json.loads(plain.decode("utf-8"))
def hdou_extract_data(result):
    if not isinstance(result, dict):
        return None
    inner = result.get("data")
    if isinstance(inner, dict):
        return inner
    return result
def hdou_list(result):
    data = hdou_extract_data(result)
    if isinstance(data, dict):
        for field in ("list", "items", "rows"):
            value = data.get(field)
            if isinstance(value, list):
                return value
    if isinstance(data, list):
        return data
    return []
def hdou_drama_from(row):
    if not isinstance(row, dict):
        return None
    source_id = first_non_empty(row.get("id"), row.get("drama_id"))
    if not source_id:
        return None
    title = first_non_empty(row.get("name"), row.get("title"), row.get("t"))
    if not title:
        return None
    cover = first_non_empty(row.get("img"), row.get("img_y"), row.get("cover"), row.get("poster"))
    cover = resolve_url(hdou_host() + "/", cover) if cover else ""
    desc = first_non_empty(row.get("intro"), row.get("desc"), row.get("description"))
    remark = first_non_empty(row.get("remark"), row.get("remarks"))
    return {"vod_id": "huangdou:" + str(source_id), "vod_name": str(title)[:200], "vod_pic": cover,
            "vod_content": desc, "vod_remarks": remark, "type_name": "黄豆", "vod_year": "", "vod_area": ""}
def hdou_catalog(page):
    result = hdou_call("/drama/list", {"page": str(page), "page_size": "30"})
    out = []
    for row in hdou_list(result):
        drama = hdou_drama_from(row)
        if drama:
            out.append(drama)
    return out
HDOU_RANK_TABS = {
    "all": "总榜",
    "mogai": "魔改榜",
    "search": "搜索榜",
    "favorite": "收藏榜",
    "finish": "完结榜",
}
def hdou_rank(tab, page):
    tab = str(tab or "all")
    if tab not in HDOU_RANK_TABS:
        tab = "all"
    result = hdou_call("/drama/rank", {"tab": tab, "page": str(page)})
    out = []
    for row in hdou_list(result):
        drama = hdou_drama_from(row)
        if drama:
            out.append(drama)
    return out
def hdou_detail(source_id):
    result = hdou_call("/drama/detail", {"id": source_id})
    row = hdou_extract_data(result)
    if not isinstance(row, dict):
        raise RuntimeError("黄豆未返回有效详情")
    drama = hdou_drama_from(row) or {}
    episodes = []
    raw_eps = row.get("episodes")
    if isinstance(raw_eps, list):
        for ep in raw_eps:
            if not isinstance(ep, dict):
                continue
            seq = episode_number(first_non_empty(ep.get("seq"), ep.get("episode"), ep.get("ep")),
                                 len(episodes) + 1)
            title = first_non_empty(ep.get("name"), ep.get("title"), "第%d集" % seq)
            episodes.append({"key": str(seq), "title": str(title)[:100], "index": seq})
    count = first_non_empty(row.get("episode_count"), row.get("free_episodes"))
    if count and not episodes:
        for index in range(1, min(int(count), 10000) + 1):
            episodes.append({"key": str(index), "title": "第%d集" % index, "index": index})
    if not drama.get("vod_remarks") and episodes:
        drama["vod_remarks"] = "共%d集" % len(episodes)
    episodes.sort(key=lambda e: e.get("index", 0))
    return drama, episodes
def hdou_play(source_id, seq):
    result = hdou_call("/drama/play", {"id": source_id, "seq": str(seq)})
    row = hdou_extract_data(result)
    media = ""
    hls_key = ""
    if isinstance(row, dict):
        media = first_non_empty(row.get("m3u8"), row.get("play_url"), row.get("url"))
        hls_key = first_non_empty(row.get("hls_key"), row.get("key"))
    if not media:
        media = "%s/api/drama/hls/%s/%d/play.m3u8?line=free" % (hdou_host(), urllib.parse.quote(source_id), seq)
    return media, hls_key
def hdou_search(keyword):
    result = hdou_call("/drama/list", {"keywords": keyword, "page": "1", "page_size": "50"})
    out = []
    for row in hdou_list(result):
        drama = hdou_drama_from(row)
        if drama and (keyword.lower() in drama["vod_name"].lower()):
            out.append(drama)
    return out
YEGUO_BASE = "https://analyze.buxefaex.cc"
YEGUO_APIS = [
    "https://www.yeguodj.com/api.php",
    "https://ygdj7.com/api.php",
    "https://yoeolhoa.cc/api.php",
]
YEGUO_FILTERS = ["theme", "setting", "background", "time", "recommend"]
YEGUO_SL = {
    "bundleId": "com.pwa.mater",
    "version": "1.3.2",
    "oauth_type": "web",
    "language": "zh",
    "via": "pwa",
    "oauth_id": "7d05538c4b8a5e74e82f93c0dab0163c",
    "token": "",
    "trace_id": "7d05538c4b8a5e74e82f93c0dab0163c",
}
YEGUO_KEY_ENC = "50_97_99_102_55_101_57_49_101_57_56_54_52_54_55_51"
YEGUO_IV_ENC = "49_99_50_57_56_56_50_100_51_100_100_102_99_102_100_54"
YEGUO_IMG_KEY_ENC = "102_53_100_57_54_53_100_102_55_53_51_51_54_50_55_48"
YEGUO_IMG_IV_ENC = "57_55_98_54_48_51_57_52_97_98_99_50_102_98_101_49"
def yeguo_unlock(value):
    if re.fullmatch(r"\d+(?:_\d+)+", str(value)):
        try:
            return "".join(chr(int(x)) for x in str(value).split("_"))
        except Exception:
            return value
    return value
def yeguo_discover():
    config = {"key": yeguo_unlock(YEGUO_KEY_ENC), "iv": yeguo_unlock(YEGUO_IV_ENC)}
    return YEGUO_APIS[0], config
def yeguo_call(route, params=None, tries=2):
    site, config = yeguo_discover()
    headers = {
        "User-Agent": UA_ANDROID,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://www.yeguodj.com",
        "Referer": "https://www.yeguodj.com/",
        "X-Requested-With": "XMLHttpRequest",
    }
    payload = dict(YEGUO_SL)
    if params:
        payload.update(params)
    body = urllib.parse.urlencode(payload).encode("utf-8")
    last_error = None
    for api in YEGUO_APIS:
        for attempt in range(tries):
            try:
                status, _, resp = http_request(api + route, method="POST", headers=headers,
                                               data=body, timeout=8)
                text = resp.decode("utf-8", "ignore").strip()
                if not text.startswith("{"):
                    continue
                result = json.loads(text)
                if result.get("errcode") not in (0, None):
                    last_error = RuntimeError("野果接口错误: %s" % result.get("msg"))
                    continue
                if isinstance(result.get("data"), str):
                    decrypted = yeguo_decrypt_data(result["data"], config)
                    if isinstance(decrypted, dict) and isinstance(decrypted.get("data"), (dict, list)):
                        return decrypted["data"]
                    return decrypted
                return result
            except Exception as exc:
                last_error = exc
    raise last_error or RuntimeError("野果网关不可用")
def yeguo_decrypt_data(data_b64, config):
    encrypted = base64.b64decode(data_b64)
    key = config["key"].encode("utf-8")[:16]
    iv = config["iv"].encode("utf-8")[:16]
    if len(key) < 16:
        key = (key + b"\x00" * 16)[:16]
    if len(iv) < 16:
        iv = (iv + b"\x00" * 16)[:16]
    plain = aes_cbc_decrypt(encrypted, key, iv)
    plain = hdou_unpad(plain)
    return json.loads(plain.decode("utf-8"))
def yeguo_categories():
    cached = cache_get("yeguo:categories")
    if cached:
        return cached
    cats = [{"type_id": "yeguo:0", "type_name": "野果·全部"}]
    try:
        data = yeguo_call("/api/theater/exploreList", {"page": "1", "limit": "1"})
        filters = data.get("filters") if isinstance(data, dict) else None
        items = filters if isinstance(filters, list) else ([filters] if isinstance(filters, dict) else [])
        for filter_item in items:
            if not isinstance(filter_item, dict):
                continue
            field = str(filter_item.get("key") or "")
            if field not in YEGUO_FILTERS:
                continue
            options = filter_item.get("options") or filter_item.get("list")
            if isinstance(options, list):
                for option in options:
                    if not isinstance(option, dict):
                        continue
                    value, name = str(option.get("value") or option.get("id") or ""), str(option.get("name") or option.get("label") or "")
                    if value in ("", "0") or not name:
                        continue
                    cats.append({"type_id": "yeguo:%s:%s" % (field, value), "type_name": "野果·" + name[:24]})
    except Exception:
        pass
    cache_set("yeguo:categories", cats, 1800)
    return cats
YEGUO_PIC_CACHE = {}
YEGUO_PIC_CACHE_LOCK = threading.RLock()
YEGUO_PIC_CACHE_MAX = 400
YEGUO_PIC_SEM = threading.Semaphore(2)
def yeguo_pic_inline(raw):
    if not raw or raw.startswith("data:"):
        return ""
    with YEGUO_PIC_CACHE_LOCK:
        hit = YEGUO_PIC_CACHE.get(raw)
    if hit:
        return hit
    headers = {"User-Agent": UA_ANDROID, "Referer": "https://www.yeguodj.com/"}
    acquired = YEGUO_PIC_SEM.acquire(timeout=2)
    try:
        if not acquired:
            return ""
        status, _, body = http_request(raw, headers=headers, timeout=6)
    except Exception:
        return ""
    finally:
        if acquired:
            YEGUO_PIC_SEM.release()
    if status >= 400 or not body:
        return ""
    key = yeguo_unlock(YEGUO_IMG_KEY_ENC).encode("utf-8")[:16]
    iv = yeguo_unlock(YEGUO_IMG_IV_ENC).encode("utf-8")[:16]
    try:
        img = aes_cbc_decrypt(body, key, iv)
        img = hdou_unpad(img)
    except Exception:
        return ""
    if img[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    elif img[:4] == b"RIFF" and img[8:12] == b"WEBP":
        mime = "image/webp"
    elif img[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    else:
        return ""
    data_url = "data:%s;base64,%s" % (mime, base64.b64encode(img).decode("ascii"))
    with YEGUO_PIC_CACHE_LOCK:
        if len(YEGUO_PIC_CACHE) >= YEGUO_PIC_CACHE_MAX:
            YEGUO_PIC_CACHE.clear()
        YEGUO_PIC_CACHE[raw] = data_url
    return data_url
def hguo_proxy_image(raw):
    if not raw:
        return [404, "text/plain", b"not found", {"Content-Type": "text/plain"}]
    url = raw
    try:
        url = base64.urlsafe_b64decode(url + "=" * ((-len(url)) % 4)).decode("utf-8")
    except Exception:
        try:
            url = base64.b64decode(url + "=" * ((-len(url)) % 4)).decode("utf-8")
        except Exception:
            pass
    if not url.startswith("http"):
        return [404, "text/plain", b"not found", {"Content-Type": "text/plain"}]
    headers = {"User-Agent": UA_ANDROID, "Referer": "https://huangguoai.com/"}
    try:
        status, _, body = http_request(url, headers=headers, timeout=15)
    except Exception:
        return [500, "text/plain", b"upstream error", {"Content-Type": "text/plain"}]
    if status >= 400 or not body:
        return [status, "text/plain", b"upstream error", {"Content-Type": "text/plain"}]
    key = yeguo_unlock(YEGUO_IMG_KEY_ENC).encode("utf-8")[:16]
    iv = yeguo_unlock(YEGUO_IMG_IV_ENC).encode("utf-8")[:16]
    try:
        img = aes_cbc_decrypt(body, key, iv)
        img = hdou_unpad(img)
    except Exception:
        return [500, "text/plain", b"decrypt error", {"Content-Type": "text/plain"}]
    if img[:8] == b"\x89PNG\r\n\x1a\n":
        ctype = "image/png"
    elif img[:4] == b"RIFF" and img[8:12] == b"WEBP":
        ctype = "image/webp"
    elif img[:3] == b"\xff\xd8\xff":
        ctype = "image/jpeg"
    else:
        return [404, "text/plain", b"bad image", {"Content-Type": "text/plain"}]
    return [200, ctype, img, {"Content-Type": ctype}]
def hguo_pic_proxy(raw):
    if not raw or raw.startswith("data:"):
        return ""
    try:
        base = _yeguo_pic_base()
    except Exception:
        return ""
    enc = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    return "%s/pic?u=%s&site=hguo" % (base, enc)
def yeguo_proxy_image(raw):
    if not raw:
        return [404, "text/plain", b"not found", {"Content-Type": "text/plain"}]
    url = raw
    try:
        url = base64.urlsafe_b64decode(url + "=" * ((-len(url)) % 4)).decode("utf-8")
    except Exception:
        try:
            url = base64.b64decode(url + "=" * ((-len(url)) % 4)).decode("utf-8")
        except Exception:
            pass
    if not url.startswith("http"):
        return [404, "text/plain", b"not found", {"Content-Type": "text/plain"}]
    headers = {"User-Agent": UA_ANDROID, "Referer": "https://www.yeguodj.com/"}
    try:
        status, _, body = http_request(url, headers=headers, timeout=15)
    except Exception:
        return [500, "text/plain", b"upstream error", {"Content-Type": "text/plain"}]
    if status >= 400 or not body:
        return [status, "text/plain", b"upstream error", {"Content-Type": "text/plain"}]
    key = yeguo_unlock(YEGUO_IMG_KEY_ENC).encode("utf-8")[:16]
    iv = yeguo_unlock(YEGUO_IMG_IV_ENC).encode("utf-8")[:16]
    try:
        img = aes_cbc_decrypt(body, key, iv)
        img = hdou_unpad(img)
    except Exception:
        return [500, "text/plain", b"decrypt error", {"Content-Type": "text/plain"}]
    if img[:8] == b"\x89PNG\r\n\x1a\n":
        ctype = "image/png"
    elif img[:4] == b"RIFF" and img[8:12] == b"WEBP":
        ctype = "image/webp"
    elif img[:3] == b"\xff\xd8\xff":
        ctype = "image/jpeg"
    else:
        return [404, "text/plain", b"bad image", {"Content-Type": "text/plain"}]
    return [200, ctype, img, {"Content-Type": ctype}]
def yeguo_pic_proxy(raw):
    if not raw or raw.startswith("data:"):
        return ""
    try:
        base = _yeguo_pic_base()
    except Exception:
        return ""
    enc = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    return "%s/pic?u=%s" % (base, enc)
_YEGUO_PIC_BASE = {"base": ""}
_YEGUO_PIC_BASE_LOCK = threading.Lock()
def _yeguo_pic_base():
    if _YEGUO_PIC_BASE["base"]:
        return _YEGUO_PIC_BASE["base"]
    with _YEGUO_PIC_BASE_LOCK:
        if not _YEGUO_PIC_BASE["base"]:
            _YEGUO_PIC_BASE["base"] = _stream_ensure()
        return _YEGUO_PIC_BASE["base"]
def yeguo_drama_from(row, inline=True):
    if not isinstance(row, dict):
        return None
    source_id = first_non_empty(row.get("video_id"), row.get("id"))
    title = first_non_empty(row.get("title"), row.get("name"))
    if not source_id or not title:
        return None
    cover = first_non_empty(row.get("cover"), row.get("img"), row.get("poster"))
    cover = resolve_url(YEGUO_BASE + "/", cover) if cover else ""
    if cover:
        cover = yeguo_pic_proxy(cover)
    else:
        cover = ""
    desc = first_non_empty(row.get("description"), row.get("intro"))
    episodes = 0
    for field in ("episode_count", "total_serial"):
        try:
            episodes = max(episodes, int(row.get(field) or 0))
        except Exception:
            pass
    remark = ("全%d集" % episodes) if episodes else ""
    return {"vod_id": "yeguo:" + str(source_id), "vod_name": str(title)[:200], "vod_pic": cover,
            "vod_content": desc, "vod_remarks": remark, "type_name": "野果", "vod_year": "", "vod_area": ""}
def yeguo_catalog(cat, page):
    params = {"page": str(page), "page_size": "20"}
    if cat and cat != "0":
        if ":" in cat:
            field, value = cat.split(":", 1)
            if field in YEGUO_FILTERS:
                params[field] = value
    try:
        data = yeguo_call("/api/theater/exploreList", params)
    except Exception:
        return []
    rows = data.get("list") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        return []
    results = parallel_run_to([("d%d" % i, lambda r=row: yeguo_drama_from(r)) for i, row in enumerate(rows)], 4, 2.0)
    by_name = dict(results)
    out = []
    for i, row in enumerate(rows):
        drama = by_name.get("d%d" % i)
        if not drama:
            drama = yeguo_drama_from(row, inline=False)
        if drama:
            out.append(drama)
    return out
def yeguo_detail(source_id):
    data = yeguo_call("/api/playlet/detail", {"video_id": source_id, "id": source_id,
                                              "episode_id": "0", "related_limit": "0"})
    if not isinstance(data, dict):
        raise RuntimeError("野果未返回有效详情")
    drama = yeguo_drama_from(data) or {}
    episodes = []
    rows = data.get("episodes") or data.get("episode_list") or data.get("video_list")
    if isinstance(rows, list):
        for ep in rows:
            if not isinstance(ep, dict):
                continue
            ep_id = str(ep.get("id") or ep.get("episode_id") or "")
            number = episode_number(ep.get("sort") or ep.get("index") or ep.get("episode_no"), len(episodes) + 1)
            if not ep_id or number < 1:
                continue
            title = first_non_empty(ep.get("title"), "第%d集" % number)
            episodes.append({"key": ep_id, "title": str(title)[:100], "index": number})
    episodes.sort(key=lambda e: e.get("index", 0))
    return drama, episodes
def yeguo_play(source_id, ep_id):
    data = yeguo_call("/api/playlet/play", {"playlet_id": source_id, "video_id": source_id,
                                            "episode_id": ep_id})
    if not isinstance(data, dict):
        raise RuntimeError("野果未返回播放地址")
    if str(data.get("is_adv", "")).lower() in ("1", "true"):
        raise RuntimeError("野果返回的是广告")
    media = first_non_empty(data.get("video_url"), data.get("video_url_h265"),
                            data.get("play_url"), data.get("media_url"))
    if not media:
        raise RuntimeError("野果播放地址为空")
    return resolve_url(YEGUO_BASE + "/", media)
def yeguo_search(keyword):
    try:
        data = yeguo_call("/api/search/result", {"keyword": keyword, "tab": "video", "page": "1", "limit": "20"})
        if not isinstance(data, dict) or not data.get("list"):
            data = yeguo_call("/api/search/home", {"keyword": keyword, "page": "1", "limit": "20"})
    except Exception:
        try:
            data = yeguo_call("/api/search/home", {"keyword": keyword, "page": "1", "limit": "20"})
        except Exception:
            return []
    rows = (data.get("list") or data.get("videos")) if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        return []
    results = parallel_run_to([("d%d" % i, lambda r=row: yeguo_drama_from(r)) for i, row in enumerate(rows)], 4, 2.0)
    by_name = dict(results)
    out = []
    for i, row in enumerate(rows):
        drama = by_name.get("d%d" % i)
        if not drama:
            drama = yeguo_drama_from(row, inline=False)
        if drama:
            out.append(drama)
    return out
_FAV_LOCK = threading.RLock()
_FAV_FILE = None
_FAV_MEM = []
_FOLLOW_VID_MAP = {}
_FOLLOW_NEXT = {}
_FAV_PLACEHOLDER_B64 = (
    "AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAANMbW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAA+"
    "gAAQAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAgAAApt0cmFrAAAAXHRraGQAAAADAAAAAAAAAAAAAAABAAAAAAAAA+gAAAAAAAAAAAAAAAAAAA"
    "AAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAABAAAAAQAAAAAAAkZWR0cwAAABxlbHN0AAAAAAAA"
    "AAEAAAPoAAAAAAABAAAAAAITbWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAAAyAAAAMgBVxAAAAAAALWhkbHIAAAAAAA"
    "AAAHZpZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAABvm1pbmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAAACRkaW5m"
    "AAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAAX5zdGJsAAAAtnN0c2QAAAAAAAAAAQAAAKZhdmMxAAAAAAAAAA"
    "EAAAAAAAAAAAAAAAAAAAAAABAAEABIAAAASAAAAAAAAAABDExhdmMgbGlieDI2NAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "GP//AAAALGF2Y0MBQsAK/+EAFGdCwArd7ARAAAADAEAAAAyDxIngAQAFaM4BlyAAAAAQcGFzcAAAAAEAAAABAAAAFG"
    "J0cnQAAAAAAAAd8AAAHfAAAAAYc3R0cwAAAAAAAAABAAAAGQAAAgAAAAAcc3RzYwAAAAAAAAABAAAAAQAAABkAAAAB"
    "AAAAeHN0c3oAAAAAAAAAAAAAABkAAAJiAAAADwAAAA4AAAAPAAAADgAAAA8AAAAOAAAADwAAAA4AAAAPAAAADgAAAA"
    "8AAAAOAAAADwAAAA4AAAAPAAAADgAAAA8AAAAOAAAADwAAAA4AAAAPAAAADgAAAA8AAAAOAAAAFHN0Y28AAAAAAAAA"
    "AQAAA3wAAAA9dWR0YQAAADVtZXRhAAAAAAAAACFoZGxyAAAAAAAAAABtZGlyYXBwbAAAAAAAAAAAAAAAAAhpbHN0AA"
    "AACGZyZWUAAAPGbWRhdAAAAlEGBf//TdxF6b3m2Ui3lizYINkj7u94MjY0IC0gY29yZSAxNjQgcjMxOTEgNDYxM2Fj"
    "MyAtIEguMjY0L01QRUctNCBBVkMgY29kZWMgLSBDb3B5bGVmdCAyMDAzLTIwMjQgLSBodHRwOi8vd3d3LnZpZGVvbG"
    "FuLm9yZy94MjY0Lmh0bWwgLSBvcHRpb25zOiBjYWJhYz0wIHJlZj0xIGRlYmxvY2s9MDowOjAgYW5hbHlzZT0wOjAg"
    "bWU9ZGlhIHN1Ym1lPTAgcHN5PTEgcHN5X3JkPTEuMDA6MC4wMCBtaXhlZF9yZWY9MCBtZV9yYW5nZT0xNiBjaHJvbW"
    "FfbWU9MSB0cmVsbGlzPTAgOHg4ZGN0PTAgY3FtPTAgZGVhZHpvbmU9MjEsMTEgZmFzdF9wc2tpcD0xIGNocm9tYV9x"
    "cF9vZmZzZXQ9MCB0aHJlYWRzPTEgbG9va2FoZWFkX3RocmVhZHM9MSBzbGljZWRfdGhyZWFkcz0wIG5yPTAgZGVjaW"
    "1hdGU9MSBpbnRlcmxhY2VkPTAgYmx1cmF5X2NvbXBhdD0wIGNvbnN0cmFpbmVkX2ludHJhPTAgYmZyYW1lcz0wIHdl"
    "aWdodHA9MCBrZXlpbnQ9MSBrZXlpbnRfbWluPTEgc2NlbmVjdXQ9MCBpbnRyYV9yZWZyZXNoPTAgcmM9Y3JmIG1idH"
    "JlZT0wIGNyZj01MS4wIHFjb21wPTAuNjAgcXBtaW49MCBxcG1heD02OSBxcHN0ZXA9NCBpcF9yYXRpbz0xLjQwIGFx"
    "PTAAgAAAAAlliIQ6JigAFcAAAAALZYiCAiiYoAAgD4AAAAAKZYiECKJigACAPgAAAAtliIICKJigACAPgAAAAApliI"
    "QIomKAAIA+AAAAC2WIggIomKAAIA+AAAAACmWIhAiiYoAAgD4AAAALZYiCAiiYoAAgD4AAAAAKZYiECKJigACAPgAA"
    "AAtliIICKJigACAPgAAAAApliIQIomKAAIA+AAAAC2WIggIomKAAIA+AAAAACmWIhAiiYoAAgD4AAAALZYiCAiiYoA"
    "AgD4AAAAAKZYiECKJigACAPgAAAAtliIICKJigACAPgAAAAApliIQIomKAAIA+AAAAC2WIggIomKAAIA+AAAAACmWI"
    "hAiiYoAAgD4AAAALZYiCAiiYoAAgD4AAAAAKZYiECKJigACAPgAAAAtliIICKJigACAPgAAAAApliIQIomKAAIA+AA"
    "AAC2WIggIomKAAIA+AAAAACmWIhAiiYoAAgD4="
)
_FAV_MP4_CACHE = None
def _fav_placeholder_bytes():
    global _FAV_MP4_CACHE
    if _FAV_MP4_CACHE is None:
        _FAV_MP4_CACHE = base64.b64decode(_FAV_PLACEHOLDER_B64)
    return _FAV_MP4_CACHE
def _fav_placeholder_url():
    try:
        base = _stream_ensure()
        return base + "/fav_ok"
    except Exception:
        return "http://127.0.0.1:UndCover/proxy?do=%s&api=python&site=favorite&type=fav_ok" % (
            urllib.parse.quote(LOCAL_PROXY_KEY, safe=""))
_FAV_CANDIDATES = None
def _fav_candidates():
    global _FAV_CANDIDATES
    if _FAV_CANDIDATES is not None:
        return _FAV_CANDIDATES
    cands = []
    for cand in ("/sdcard/zhenguojian", "/storage/emulated/0/zhenguojian"):
        if cand not in cands:
            cands.append(cand)
    for key in ("PYTHON_SAVE_PATH", "PYTHON_CACHE_PATH"):
        value = os.environ.get(key)
        if value and value not in cands:
            cands.append(value)
    for key in ("HOME", "TMPDIR"):
        value = os.environ.get(key)
        if value and value not in cands:
            cands.append(os.path.join(value, "zhenguojian"))
    try:
        cwd = os.getcwd()
        if cwd and cwd not in cands:
            cands.append(os.path.join(cwd, "zhenguojian"))
    except Exception:
        pass
    base = os.path.join(tempfile.gettempdir(), "zhenguojian")
    if base not in cands:
        cands.append(base)
    _FAV_CANDIDATES = cands
    return cands
def _fav_dir():
    global _FAV_FILE
    if _FAV_FILE:
        return _FAV_FILE
    for cand in _fav_candidates():
        try:
            os.makedirs(cand, exist_ok=True)
            probe = os.path.join(cand, ".fav_probe")
            with open(probe, "w") as handle:
                handle.write("ok")
            os.remove(probe)
            _FAV_FILE = cand
            log("追剧收藏目录", cand)
            return cand
        except OSError:
            continue
    base = tempfile.gettempdir()
    _FAV_FILE = base
    log("追剧收藏目录(回退tempdir)", base)
    return base
def _fav_path():
    return os.path.join(_fav_dir(), "favorites.json")
def favorite_load():
    merged = {}
    for cand in _fav_candidates():
        path = os.path.join(cand, "favorites.json")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.loads(handle.read() or "[]")
            if not isinstance(data, list):
                data = []
            for item in data:
                if not (isinstance(item, dict) and item.get("vod_id")):
                    continue
                vid = str(item.get("vod_id") or "")
                if vid == "fav:toggle" or not vid:
                    continue
                merged[vid] = item
        except Exception:
            continue
    with _FAV_LOCK:
        for item in _FAV_MEM:
            if isinstance(item, dict) and item.get("vod_id"):
                merged[str(item.get("vod_id"))] = item
    if not merged:
        return []
    items = list(merged.values())
    items, changed = _fav_normalize(items)
    if changed:
        favorite_save(items)
    items.sort(key=lambda item: float(item.get("fav_at") or 0), reverse=True)
    return items
def _fav_normalize(items):
    changed = False
    out = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        vid = str(item.get("vod_id") or "")
        name = str(item.get("vod_name") or "")
        for prefix in ("__follow__", "__unfollow__"):
            if vid.startswith(prefix):
                vid = vid[len(prefix):].replace("~", ":")
                item["vod_id"] = vid
                if name.startswith(prefix):
                    item["vod_name"] = name[len(prefix):].replace("~", ":")
                changed = True
                break
        if vid == "fav:toggle" or not vid:
            changed = True
            continue
        if vid in seen:
            changed = True
            continue
        seen.add(vid)
        out.append(item)
    return out, changed
def favorite_save(items):
    text = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    ok = False
    for cand in _fav_candidates():
        try:
            os.makedirs(cand, exist_ok=True)
            path = os.path.join(cand, "favorites.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            with open(path, "r", encoding="utf-8") as handle:
                if handle.read() == text:
                    ok = True
        except Exception:
            continue
    with _FAV_LOCK:
        _FAV_MEM[:] = items
    return ok
def favorite_is_fav(vod_id):
    if not vod_id:
        return False
    with _FAV_LOCK:
        items = favorite_load()
    return any(item.get("vod_id") == vod_id for item in items)
def favorite_toggle(drama):
    vod_id = (drama or {}).get("vod_id") or ""
    if not vod_id:
        return False, 0
    with _FAV_LOCK:
        items = favorite_load()
        for item in items:
            if item.get("vod_id") == vod_id:
                items.remove(item)
                favorite_save(items)
                return False, len(items)
        fav = {
            "vod_id": vod_id,
            "vod_name": str((drama or {}).get("vod_name") or "")[:200],
            "vod_pic": str((drama or {}).get("vod_pic") or ""),
            "vod_remarks": str((drama or {}).get("vod_remarks") or "")[:80],
            "site": str((drama or {}).get("vod_play_from") or ""),
            "fav_at": time.time(),
        }
        items.append(fav)
        favorite_save(items)
        return True, len(items)
def favorite_list():
    items = []
    for fav in favorite_load():
        items.append({
            "vod_id": fav.get("vod_id"),
            "vod_name": fav.get("vod_name") or "",
            "vod_pic": fav.get("vod_pic") or "",
            "vod_remarks": fav.get("vod_remarks") or "",
            "type_name": fav.get("site") or "",
            "vod_content": "",
        })
    return items
def build_vod(drama, extra=None):
    item = dict(drama or {})
    if extra:
        item.update(extra)
    return item
def detail_vod(drama, episodes, site_name):
    vod = dict(drama or {})
    vod["vod_play_from"] = site_name
    vid = (drama or {}).get("vod_id") or ""
    lines = []
    for index, ep in enumerate(episodes, 1):
        key = str(ep.get("key") or "")
        lines.append("%s$%s/%s" % (ep.get("title") or ("第%d集" % index), vid, key))
    main_url = "#".join(lines)
    first_key = ""
    for ep in episodes:
        k = str(ep.get("key") or "")
        if k:
            first_key = k
            break
    if first_key:
        try:
            with _FAV_LOCK:
                _FOLLOW_NEXT[vid] = first_key
        except Exception:
            pass
    if favorite_is_fav(vid):
        fav_label = "取消追剧"
        follow_addr = "__unfollow__" + vid.replace(":", "~")
    else:
        fav_label = "点击追剧"
        follow_addr = "__follow__" + vid.replace(":", "~")
    try:
        with _FAV_LOCK:
            _FOLLOW_VID_MAP[follow_addr] = vid
            _FOLLOW_VID_MAP[str(fav_label) + "$" + follow_addr] = vid
    except Exception:
        pass
    vod["vod_play_url"] = main_url
    if not lines:
        vod["vod_play_from"] = site_name
        return vod
    vod["vod_play_url"] = main_url + "$$$" + fav_label + "$" + follow_addr
    vod["vod_play_from"] = "%s$$$追剧" % site_name
    return vod
def home_content():
    try:
        return hong_catalog("short_play", 1)[:50]
    except Exception as exc:
        log("首页推荐(红果)失败", exc)
        return []
def dsd_first_catalog():
    cats = dsd_categories()
    if not cats:
        return []
    tid = cats[0]["type_id"]
    if tid == "dsd:all":
        return []
    return dsd_catalog(tid.split(":", 1)[1], 1)
def _fav_diag_list():
    out = []
    items = favorite_load()
    with _FAV_LOCK:
        mem_n = len(_FAV_MEM)
    for cand in _fav_candidates():
        path = os.path.join(cand, "favorites.json")
        state = "只读"
        detail = "无文件"
        try:
            os.makedirs(cand, exist_ok=True)
            probe = os.path.join(cand, ".fav_probe")
            with open(probe, "w") as handle:
                handle.write("ok")
            os.remove(probe)
            state = "可写"
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as handle:
                        detail = "条数=%d" % len(json.loads(handle.read() or "[]"))
                except Exception:
                    detail = "文件解析失败"
            else:
                detail = "无文件"
        except Exception as exc:
            detail = str(exc)[:40]
        out.append({
            "vod_id": "favdiag:path%d" % len(out),
            "vod_name": "[%s] %s" % (state, cand),
            "vod_pic": "",
            "vod_remarks": "文件: %s\n%s" % (path, detail),
            "type_name": "路径自检",
        })
    out.append({
        "vod_id": "favdiag:mem",
        "vod_name": "内存缓存 %d 条 · 追剧清单合计 %d 条" % (mem_n, len(items)),
        "vod_pic": "",
        "vod_remarks": "可写且有条数=持久化成功; 仅内存=重启会丢\n提示: 私有目录无root不可见, 可给DsPlayer开存储权限让/sdcard/zhenguojian可写, 即可在文件管理器看到favorites.json",
        "type_name": "路径自检",
    })
    return out
def build_class():
    return [
        {"type_id": "zhuiju:", "type_name": "追剧"},
        {"type_id": "favdiag:", "type_name": "路径自检"},
        {"type_id": "hongguo:", "type_name": "红果·短剧"},
        {"type_id": "huangguoai:", "type_name": "黄果AI"},
        {"type_id": "hguov:", "type_name": "黄果视频"},
        {"type_id": "jugu:", "type_name": "剧果"},
        {"type_id": "dsd:", "type_name": "帝果"},
        {"type_id": "huangdou:", "type_name": "黄豆"},
        {"type_id": "yeguo:", "type_name": "野果"},
        {"type_id": "香果:", "type_name": "香果"},
        {"type_id": "橙果:", "type_name": "橙果"},
        {"type_id": "九果:", "type_name": "九果"},
        {"type_id": "五果:", "type_name": "五果"},
        {"type_id": "河果:", "type_name": "河果"},
        {"type_id": "猫果:", "type_name": "猫果"},
        {"type_id": "芽果:", "type_name": "芽果"},
        {"type_id": "观果:", "type_name": "观果"},
        {"type_id": "百果:", "type_name": "百果"},
        {"type_id": "薏果:", "type_name": "薏果"},
        {"type_id": "牛果:", "type_name": "牛果"},
        {"type_id": "山果:", "type_name": "山果"},
        {"type_id": "好果:", "type_name": "好果"},
        {"type_id": "饭果:", "type_name": "饭果"},
        {"type_id": "星果:", "type_name": "星果"},
    ]
def build_filters():
    filters = {}
    def add_filter(type_id, key, name, options):
        value = [{"n": opt[0], "v": opt[1]} for opt in options]
        filters.setdefault(type_id, []).append({"key": key, "name": name, "value": value})
    add_filter("hongguo:", "cat", "剧种", [
        ("真人剧", "short_play"), ("漫剧", "comic_series"), ("AI剧", "ai_series"),
    ])
    add_filter("huangguoai:", "cat", "分类", [
        ("全部", ""), ("AI短剧", "ai-duanju"), ("AI漫剧", "ai-manju"),
        ("AI换脸", "ai-huanlian"), ("AI魔改", "ai-mogai"),
    ])
    def fetch_hguov():
        try:
            return hguov_categories()
        except Exception:
            return []
    def fetch_dsd():
        try:
            return dsd_categories()
        except Exception:
            return []
    def fetch_yeguo():
        try:
            return yeguo_categories()
        except Exception:
            return []
    def fetch_agg_xj():
        try:
            return xjHomeClasses()
        except Exception:
            return []
    # 4 个任务给 4 个线程，避免第 4 个排队等待（原为 3，帝果最慢会拖长首屏）
    # 4 个任务给 4 个线程，并设 5s 总超时：
    # 避免单个失效站点(如帝果)拖慢首屏；超时未返回的分类降级为空，不阻塞出首页。
    _cats = dict(parallel_run_to([("hguov", fetch_hguov), ("dsd", fetch_dsd),
                                  ("yeguo", fetch_yeguo), ("agg_xj", fetch_agg_xj)], 4, 5))
    add_filter("hguov:", "cat", "分类", [("全部", "0")] + [
        (cat["type_name"].replace("黄果视频·", "")[:20], cat["type_id"].split(":", 1)[1])
        for cat in (_cats.get("hguov") or [])
        if str(cat.get("type_id") or "").startswith("hguov:")
    ])
    add_filter("jugu:", "cat", "排序", [("最新", "new"), ("热门", "hot")])
    add_filter("huangdou:", "cat", "榜单", [
        (HDOU_RANK_TABS.get(tab, tab), tab) for tab in ("all", "mogai", "search", "favorite", "finish")
    ])
    dsd_opts = [("全部", "all")]
    yeguo_opts = [("全部", "0")]
    for _name, cats in [("dsd", _cats.get("dsd")), ("yeguo", _cats.get("yeguo"))]:
        prefix = "dsd:" if _name == "dsd" else "yeguo:"
        title_prefix = "帝果·" if _name == "dsd" else "野果·"
        opts = dsd_opts if _name == "dsd" else yeguo_opts
        for cat in cats or []:
            tid = str(cat.get("type_id") or "")
            name = str(cat.get("type_name") or "").replace(title_prefix, "")
            if tid.startswith(prefix) and name and name not in [o[0] for o in opts]:
                opts.append((name[:20], tid.split(":", 1)[1]))
    add_filter("dsd:", "cat", "分类", dsd_opts)
    add_filter("yeguo:", "cat", "分类", yeguo_opts)
    add_filter("香果:", "cat", "分类", [(o["n"], o["v"]) for o in (_cats.get("agg_xj") or [{"n": "最新推荐", "v": "recommend"}])])
    for _agg_site, _agg_fs in CFG["filters"].items():
        if _agg_site == "香果":
            continue
        for _f in _agg_fs:
            add_filter(_agg_site + ":", _f["key"], _f["name"], [(o["n"], o["v"]) for o in _f["value"]])
    return filters
def category_content(tid, page, extend=None):
    cat = ""
    if isinstance(extend, dict):
        val = extend.get("cat")
        if val not in (None, ""):
            cat = str(val)
    if not cat and ":" in tid:
        cand = tid.split(":", 1)[1]
        if cand:
            cat = cand
    site = tid.split(":", 1)[0] if ":" in tid else tid
    if site in ("favorite", "zhuiju"):
        return favorite_list()
    if site == "favdiag":
        return _fav_diag_list()
    if site == "hongguo":
        items = hong_catalog(cat or "short_play", page)
    elif site == "huangguoai":
        items = hguo_category(cat, page)
    elif site == "hguov":
        items = hguov_catalog(cat, page)
    elif site == "jugu":
        items = jugu_catalog(cat or "hot", page)
    elif site == "dsd":
        items = dsd_first_catalog() if (not cat or cat == "all") else dsd_catalog(cat, page)
    elif site == "huangdou":
        items = hdou_rank(cat, page)
    elif site == "yeguo":
        items = yeguo_catalog(cat or "0", page)
    elif site in AGG_PLATFORM_NAMES:
        try:
            items = agg_category_content(site, page, extend).get("list", [])
        except Exception as exc:
            log("聚合分类失败", site, exc)
            items = []
    else:
        items = []
    return items
def search_all(keyword):
    tasks = [
        ("红果", lambda: hong_search(keyword)),
        ("黄果AI", lambda: []),
        ("剧果", lambda: jugu_search(keyword)),
        ("黄豆", lambda: hdou_search(keyword)),
        ("野果", lambda: yeguo_search(keyword)),
        ("聚合短剧", lambda: (agg_search_content(keyword) or {}).get("list", [])),
    ]
    merged = []
    seen = set()
    for name, result in parallel_run_to(tasks, 4, 5.0):
        try:
            for drama in result[:20]:
                if drama.get("vod_id") in seen:
                    continue
                seen.add(drama.get("vod_id"))
                merged.append(drama)
        except Exception:
            continue
    return merged
def detail_for(vod_id):
    if not vod_id:
        return None
    if str(vod_id).split("@", 1)[0] in AGG_PLATFORM_NAMES:
        try:
            _agg_detail = agg_detail_content(str(vod_id)) or {}
            return (_agg_detail.get("list") or [{}])[0] or None
        except Exception as exc:
            log("聚合详情失败", vod_id, exc)
            return None
    parts = vod_id.split(":", 1)
    site, source_id = parts[0], parts[1] if len(parts) > 1 else ""
    if site == "hongguo":
        drama, episodes = hong_detail(source_id)
        return detail_vod(drama, episodes, "红果")
    if site == "huangguoai":
        drama, episodes = hguo_detail(source_id)
        return detail_vod(drama, episodes, "黄果AI")
    if site == "hguov":
        drama, episodes = hguov_detail(source_id)
        return detail_vod(drama, episodes, "黄果视频")
    if site == "jugu":
        drama, episodes = jugu_detail(source_id)
        return detail_vod(drama, episodes, "剧果")
    if site == "dsd":
        drama, episodes = dsd_detail(source_id)
        return detail_vod(drama, episodes, "帝果")
    if site == "huangdou":
        drama, episodes = hdou_detail(source_id)
        return detail_vod(drama, episodes, "黄豆")
    if site == "yeguo":
        drama, episodes = yeguo_detail(source_id)
        return detail_vod(drama, episodes, "野果")
    return None
YEGUO_PLAY_HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Referer": "https://www.yeguodj.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
YEGUO_PLAY_HEADER_JSON = json.dumps(YEGUO_PLAY_HEADER, ensure_ascii=False)
def _fav_extract_vid(vod_id, key):
    try:
        with _FAV_LOCK:
            for probe in (key, vod_id):
                vid = _FOLLOW_VID_MAP.get(str(probe))
                if vid:
                    return str(vid)
    except Exception:
        pass
    raw = str(key or "") or str(vod_id or "")
    for part in raw.split("/"):
        for prefix in ("__follow__", "__unfollow__"):
            if part.startswith(prefix):
                vid = part[len(prefix):].replace("~", ":")
                if vid and vid != "fav:toggle":
                    return vid
    for cand in (str(vod_id or ""), str(key or "")):
        if (cand and cand != "fav:toggle" and ":" in cand
                and "__follow__" not in cand and "__unfollow__" not in cand):
            return cand
    return ""
def play_for(flag, vod_id, key):
    parts = vod_id.split(":", 1)
    site, source_id = parts[0], parts[1] if len(parts) > 1 else ""
    key_str = str(key or "")
    if (key_str.startswith("__follow__") or key_str.startswith("__unfollow__")
            or "fav:toggle" in key_str
            or str(vod_id).startswith("__follow__")
            or str(vod_id).startswith("__unfollow__")
            or str(vod_id) == "fav:toggle"):
        try:
            real_vid = _fav_extract_vid(vod_id, key_str)
            if not real_vid:
                real_vid = str(vod_id or "")
            parts2 = real_vid.split(":", 1)
            site2, source2 = parts2[0], parts2[1] if len(parts2) > 1 else ""
            drama = None
            try:
                drama = detail_for(real_vid)
            except Exception:
                drama = None
            drama = drama or {"vod_id": real_vid, "vod_name": real_vid}
            fav, total = favorite_toggle(drama)
            log("追剧", real_vid, "已收藏" if fav else "已取消", "共%d部" % total,
                "json=%s" % _fav_path())
            first_key = ""
            try:
                with _FAV_LOCK:
                    first_key = _FOLLOW_NEXT.get(real_vid, "")
            except Exception:
                first_key = ""
            if not first_key:
                try:
                    for ep in _detail_episodes(site2, source2):
                        k = str(ep.get("key") or "")
                        if k:
                            first_key = k
                            break
                except Exception:
                    first_key = ""
            if first_key:
                media = _resolve_media(site2, source2, first_key)
                if media:
                    if site2 == "yeguo":
                        return {"parse": 0, "url": media, "header": YEGUO_PLAY_HEADER_JSON}
                    return {"parse": 0, "url": media}
        except Exception as exc:
            log("追剧失败", vod_id, exc)
        return {"parse": 0, "url": _fav_placeholder_url()}
    for _agg_n in AGG_PLATFORM_NAMES:
        if str(flag).startswith(_agg_n):
            try:
                return agg_player_content(str(flag), str(key or vod_id))
            except Exception as exc:
                log("聚合播放失败", flag, key, exc)
                return {"parse": 0, "url": ""}
    prefix = vod_id + "/"
    if key.startswith(prefix):
        key = key[len(prefix):]
    try:
        media = _resolve_media(site, source_id, key)
        if not media:
            return {"parse": 0, "url": ""}
        if site == "yeguo":
            return {"parse": 0, "url": media, "header": YEGUO_PLAY_HEADER_JSON}
        return {"parse": 0, "url": media}
    except Exception as exc:
        log("播放失败", flag, vod_id, key, exc)
        return {"parse": 0, "url": ""}
def _detail_episodes(site, source_id):
    if not source_id:
        return []
    try:
        if site == "hongguo":
            _, episodes = hong_detail(source_id)
            return episodes or []
        if site == "huangguoai":
            _, episodes = hguo_detail(source_id)
            return episodes or []
        if site == "hguov":
            _, episodes = hguov_detail(source_id)
            return episodes or []
        if site == "jugu":
            _, episodes = jugu_detail(source_id)
            return episodes or []
        if site == "dsd":
            _, episodes = dsd_detail(source_id)
            return episodes or []
        if site == "huangdou":
            _, episodes = hdou_detail(source_id)
            return episodes or []
        if site == "yeguo":
            _, episodes = yeguo_detail(source_id)
            return episodes or []
    except Exception:
        pass
    return []
def _resolve_media(site, source_id, key):
    try:
        if site == "huangguoai":
            return hguo_ep_media(source_id, key) or ""
        if site == "hguov":
            return hguov_play(source_id, key) or ""
        if site == "jugu":
            media = jugu_play_cached(key)
            if not media:
                return ""
            try:
                base = _stream_ensure()
                try:
                    threading.Thread(target=jugu_prefetch_m3u8,
                                     args=(media, str(key)), daemon=True).start()
                except Exception:
                    pass
                return base + "/jugu_m3u8?url=%s&ep=%s" % (
                    urllib.parse.quote(media, safe=""),
                    urllib.parse.quote(str(key), safe=""))
            except Exception as exc:
                log("剧果流式服务启动失败", key, exc)
            return "http://127.0.0.1:UndCover/proxy?do=%s&api=python&site=jugu&url=%s&ep=%s" % (
                urllib.parse.quote(LOCAL_PROXY_KEY, safe=""),
                urllib.parse.quote(media, safe=""),
                urllib.parse.quote(str(key), safe=""))
        if site == "dsd":
            parts_key = str(key).split("-")
            line, ep = int(parts_key[0]), int(parts_key[1])
            return dsd_play_line(source_id, line, ep).get("url", "") or ""
        if site == "huangdou":
            media, _hls_key = hdou_play(source_id, key)
            return media or ""
        if site == "yeguo":
            return yeguo_play(source_id, key) or ""
        if site == "hongguo":
            media = hong_app_media(source_id, key)
            if not media:
                media = hong_media_throttled(source_id, key)
            return media or ""
    except Exception:
        pass
    return ""
def hguo_ep_media(source_id, key):
    mirror = hguo_mirror()
    m = re.fullmatch(r"(?:ep-)?(\d+)", str(key or ""), re.I)
    ep_part = ("ep-%s" % m.group(1)) if m else str(key or "")
    url = mirror + "/video/" + urllib.parse.quote(source_id) + "/" + urllib.parse.quote(ep_part) + "/"
    body = ""
    media = ""
    for attempt in range(4):
        try:
            body = http_text(url, headers={"User-Agent": UA_ANDROID, "Referer": mirror + "/"}, timeout=12)
        except Exception:
            body = ""
        media = hguo_media_from_page(body, url) if body else ""
        if media:
            break
        time.sleep(1.0 * (attempt + 1))
    if not media:
        body2 = http_text(mirror + "/detail/" + urllib.parse.quote(source_id) + "/",
                          headers={"User-Agent": UA_ANDROID, "Referer": mirror + "/"}, timeout=12)
        media = hguo_media_from_page(body2, mirror + "/detail/" + source_id + "/")
    return media
def dsd_play_line(source_id, line, ep):
    url = "%s/index.php/vod/play/id/%s/sid/%d/nid/%d.html" % (DSD_WEB, source_id, line, ep)
    body = dsd_session_text(url, referer=DSD_WEB + "/", timeout=12)
    player = dsd_parse_player(body)
    address = ""
    if player:
        try:
            address = dsd_issued_media(player, url)
        except Exception:
            address = ""
    if not address:
        if line != 1 or ep != 1:
            return {"parse": 0, "url": ""}
        cover = ""
        poster = player.get("poster") if player else None
        if isinstance(poster, str):
            cover = resolve_url(url, poster)
        if not cover:
            m = re.search(r'background-image:\s*url\(\s*["\']?([^"\')]+\.(?:jpg|jpeg|png|webp))["\']?\s*\)', body, re.I)
            if m:
                cover = resolve_url(url, m.group(1))
        if not cover:
            m = re.search(r'<img\b[^>]*class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]+)"', body, re.I)
            if m:
                cover = resolve_url(url, m.group(1))
        if cover and re.search(r"/1\.(?:jpg|jpeg|png|webp)$", cover, re.I):
            parsed = urllib.parse.urlparse(cover)
            if parsed.hostname and parsed.hostname.lower() == urllib.parse.urlparse(DSD_WEB).hostname:
                address = re.sub(r"/1\.(?:jpg|jpeg|png|webp)$", "/1000k/index.m3u8", parsed.path, flags=re.I)
                address = DSD_WEB + address
    if not address:
        return {"parse": 0, "url": ""}
    signed = ""
    via_vplayer = False
    if "sign=" not in address:
        media_path = urllib.parse.quote(urllib.parse.urlparse(address).path, safe="/")
        try:
            vp_url = "%s/addons/vplayer/?url=%s&jump=" % (DSD_WEB, media_path)
            vp_body = dsd_session_text(vp_url, referer=DSD_WEB + "/", timeout=12)
            signed = dsd_signed_path(vp_body)
            if signed:
                signed = urllib.parse.urljoin(DSD_WEB + "/addons/vplayer/", signed)
                if re.search(r"\.(m3u8|mp4)(\?|$)", signed, re.I):
                    address = signed
                    via_vplayer = True
        except Exception:
            pass
    return {"parse": 0, "url": address}
PROXY_HEADERS = {}
def proxy_headers(site, extra=None):
    headers = {}
    if site == "dsd":
        headers = {"User-Agent": DSD_UA}
        if DSD_COOKIES:
            headers["Cookie"] = "; ".join("%s=%s" % (k, v) for k, v in DSD_COOKIES.items())
    elif site == "jugu":
        headers = {"User-Agent": UA_ANDROID}
    elif site == "huangdou":
        headers = {"User-Agent": UA_ANDROID}
    elif site == "hongguo":
        headers = {"User-Agent": HONG_UA}
    elif site == "yeguo":
        headers = {"User-Agent": UA_ANDROID}
    elif site == "huangguoai":
        headers = {"User-Agent": UA_ANDROID}
    if extra:
        headers.update(extra)
    return headers
def pget(params, key, default=""):
    v = params.get(key, default)
    if isinstance(v, (list, tuple)):
        return v[0] if v else default
    return v or default
def local_proxy(param):
    if isinstance(param, str):
        s = param.strip()
        if s.startswith("{"):
            try:
                params = json.loads(s)
            except Exception:
                params = {}
        else:
            params = parse_qs_keep(s)
    elif isinstance(param, dict):
        params = param
    else:
        params = {}
    do = first_non_empty(pget(params, "do"), "media")
    url = pget(params, "url")
    site = pget(params, "site")
    try:
        if pget(params, "type") == "fav_ok" and pget(params, "site") == "favorite":
            body = _fav_placeholder_bytes()
            return [200, "video/mp4", body, {"Content-Type": "video/mp4", "Content-Length": str(len(body))}]
        if do == "key":
            hls_key = pget(params, "hls_key")
            try:
                key_bytes = bytes.fromhex(hls_key)
            except Exception:
                key_bytes = hls_key.encode()
            return [200, "application/octet-stream", key_bytes, {"Content-Type": "application/octet-stream"}]
        if pget(params, "type") in ("img", "pic"):
            raw = pget(params, "u") or pget(params, "url")
            return yeguo_proxy_image(raw)
        if site == "hongguo" and pget(params, "type") == "mc_cenc":
            return hong_app_cenc_proxy(url)
        if site == "hongguo" and pget(params, "type") == "hong_media":
            try:
                status, resp_headers, body = http_request(url, headers={
                    "User-Agent": MEDIA_UA,
                    "Referer": "https://novel.snssdk.com/",
                }, timeout=120, verify=False)
                if status >= 400:
                    return [status, "text/plain", b"upstream error", {"Content-Type": "text/plain"}]
                content_type = resp_headers.get("content-type", "")
                if "m3u8" in content_type or body[:7] == b"#EXTM3U":
                    return [200, "application/vnd.apple.mpegurl",
                            rewrite_m3u8(body, site, params),
                            {"Content-Type": "application/vnd.apple.mpegurl"}]
                return [200, content_type or "video/mp4", body,
                        {"Content-Type": content_type or "video/mp4", "Content-Length": str(len(body))}]
            except Exception as exc:
                log("红果媒体代理失败", url, exc)
                return [502, "text/plain", b"media proxy failed", {"Content-Type": "text/plain"}]
        if not url:
            return [400, "text/plain", b"bad request", {"Content-Type": "text/plain"}]
        headers = proxy_headers(site)
        referer = pget(params, "referer")
        if referer:
            headers["Referer"] = referer
        if site == "jugu":
            ck = {}
            try:
                ck = jugu_cookies()
            except Exception:
                ck = {}
            if not ck:
                ep = pget(params, "ep")
                if ep:
                    try:
                        jugu_play_with_cookies(str(ep))
                        ck = jugu_cookies()
                    except Exception:
                        ck = {}
            if ck:
                headers["Cookie"] = "".join("%s=%s; " % (k, v) for k, v in ck.items())
        if site == "huangdou":
            headers["Referer"] = hdou_host() + "/"
        if site == "dsd" and not referer:
            headers["Referer"] = DSD_WEB + "/"
        if site == "yeguo":
            headers["Referer"] = "https://www.yeguodj.com/"
        if site == "huangguoai":
            headers["Referer"] = hguo_mirror() + "/"
        status, resp_headers, body = http_request(url, headers=headers, timeout=25)
        if site == "dsd" and (status >= 400 or b"Access Denied" in body[:80]):
            for _ in range(3):
                time.sleep(0.5)
                status, resp_headers, body = http_request(url, headers=headers, timeout=25)
                if status < 400 and b"Access Denied" not in body[:80]:
                    break
        if status >= 400:
            return [status, "text/plain", b"upstream error", {"Content-Type": "text/plain"}]
        content_type = resp_headers.get("content-type", "")
        if ("m3u8" in content_type or body[:7] == b"#EXTM3U"):
            return [200, "application/vnd.apple.mpegurl",
                    rewrite_m3u8(body, site, params),
                    {"Content-Type": "application/vnd.apple.mpegurl"}]
        return [200, content_type or "application/octet-stream", body,
                {"Content-Type": content_type or "application/octet-stream"}]
    except Exception as exc:
        log("代理失败", do, site, exc)
        return [502, "text/plain", b"proxy error", {"Content-Type": "text/plain"}]
def _signed_suffix(site):
    if site != "jugu":
        return ""
    try:
        ck = jugu_cookies()
        if not ck:
            return ""
        suffix = urllib.parse.urlencode({
            "Policy": ck.get("CloudFront-Policy", ""),
            "Signature": ck.get("CloudFront-Signature", ""),
            "Key-Pair-Id": ck.get("CloudFront-Key-Pair-Id", ""),
        })
        return suffix
    except Exception:
        return ""
def _append_query(url, suffix):
    if not suffix:
        return url
    return url + ("&" if "?" in url else "?") + suffix
def rewrite_m3u8(body, site, params):
    base_url = pget(params, "url")
    suffix = _signed_suffix(site)
    jugu_self = pget(params, "jugu_self") or ""
    ep = pget(params, "ep") or ""
    lines = []
    stream_inf = False
    for raw in body.decode("utf-8", "ignore").splitlines():
        line = raw.strip()
        if line.startswith("#EXT-X-STREAM-INF"):
            stream_inf = True
            lines.append(raw)
            continue
        if line and not line.startswith("#"):
            if stream_inf:
                stream_inf = False
                sub_url = resolve_url(base_url, line)
                if site == "jugu" and jugu_self:
                    lines.append("%s?url=%s&ep=%s" % (
                        jugu_self,
                        urllib.parse.quote(sub_url, safe=""),
                        urllib.parse.quote(str(ep), safe="")))
                    continue
                seg = _append_query(sub_url, suffix)
                lines.append(seg)
                continue
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                m = re.search(r'URI="([^"]+)"', line)
                if m:
                    key_url = resolve_url(base_url, m.group(1))
                    if site == "huangdou" and pget(params, "hls_key"):
                        proxy = "http://127.0.0.1:UndCover/proxy?do=key&site=huangdou&hls_key=%s" % pget(params, "hls_key")
                        line = re.sub(r'URI="[^"]*"', 'URI="%s"' % proxy, line)
                    elif site == "jugu" and not suffix:
                        proxy = "http://127.0.0.1:UndCover/proxy?do=ts&site=%s&url=%s" % (
                            site, urllib.parse.quote(key_url, safe=""))
                        line = re.sub(r'URI="[^"]*"', 'URI="%s"' % proxy, line)
                    else:
                        line = re.sub(r'URI="[^"]*"', 'URI="%s"' % _append_query(key_url, suffix), line)
            else:
                seg = _append_query(resolve_url(base_url, line), suffix)
                lines.append(seg)
                continue
        lines.append(raw)
    return "\n".join(lines).encode("utf-8")
JUGU_COOKIE_CACHE = {"data": None, "ts": 0}
def jugu_cookies():
    if JUGU_COOKIE_CACHE["data"] and JUGU_COOKIE_CACHE["ts"] > time.time() - 600:
        return JUGU_COOKIE_CACHE["data"]
    return {}
def jugu_play_with_cookies(ep_id):
    token = jugu_token()
    url = JUGU_API + "/play/" + urllib.parse.quote(str(ep_id))
    status, resp_headers, _ = http_request(url, headers={"User-Agent": UA_ANDROID, "Authorization": "Bearer " + token}, timeout=15)
    if status >= 400:
        raise RuntimeError("剧果播放 HTTP %d" % status)
    cookies = {}
    set_cookies = (resp_headers.get("set-cookie") or "").split("\n")
    for item in set_cookies:
        pair = item.split(";")[0].strip()
        if "=" in pair:
            name, value = pair.split("=", 1)
            if name.strip() in ("CloudFront-Policy", "CloudFront-Signature", "CloudFront-Key-Pair-Id"):
                cookies[name.strip()] = value.strip()
    JUGU_COOKIE_CACHE["data"] = cookies
    JUGU_COOKIE_CACHE["ts"] = time.time()
    return cookies
_original_jugu_play = jugu_play
def jugu_play(ep_id):
    media = _original_jugu_play(ep_id)
    jugu_play_with_cookies(ep_id)
    return media
UA_CHROME = DSD_UA
UA_ANDROID = ("Mozilla/5.0 (Linux; Android 14; 25053RT47C Build/BP2A.250605.031.A3; wv) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.0.0 Mobile Safari/537.36")
def init():
    return {"key": SRC_KEY, "name": SRC_NAME, "logo": "", "api": "py"}
def homeContent(filter=False):
    cached = cache_get("home:content:" + SRC_KEY)
    if cached:
        return cached
    # 修复卡顿: 原先 build_filters() 与 home_content() 串行执行，
    # 总耗时 = 筛选拉取 + 推荐拉取。改为并发，总耗时取两者较慢者。
    def _filters_job():
        # 分类筛选项基本是静态数据，缓存 1 小时，避免每次进首页都重拉
        got = cache_get("home:filters:" + SRC_KEY)
        if got:
            return got
        got = build_filters()
        if got:
            cache_set("home:filters:" + SRC_KEY, got, 3600)
        return got or {}
    _bundle = dict(parallel_run_to([("filters", _filters_job),
                                    ("home", lambda: (home_content() or []))], 2, 8))
    _filters = _bundle.get("filters") or {}
    result = {"class": build_class(), "filters": _filters, "filter": _filters,
              "list": _bundle.get("home") or []}
    cache_set("home:content:" + SRC_KEY, result, 600)
    return result
def homeVideoContent():
    # 修复: 原先硬编码返回空列表，导致首页推荐栏永远空白。
    # 改为优先复用 homeContent 的 600s 缓存，命中即秒开；未命中再实时拉取。
    items = []
    try:
        cached = cache_get("home:content:" + SRC_KEY)
        if isinstance(cached, dict):
            items = cached.get("list") or []
    except Exception:
        items = []
    if not items:
        try:
            items = home_content() or []
        except Exception as exc:
            log("首页推荐(homeVideoContent)失败", exc)
            items = []
    return {"list": items}
def categoryContent(tid, pg, filter=False, extend=None):
    page = int(pg or 1)
    if page < 1:
        page = 1
    items = category_content(tid, page, extend)
    return {"list": items, "page": page, "pagecount": page + 1 if len(items) >= 15 else page}
def detailContent(ids):
    if isinstance(ids, (list, tuple)):
        ids = ids[0] if ids else ""
    elif isinstance(ids, str) and ids.strip().startswith("["):
        try:
            arr = json.loads(ids)
            if arr:
                ids = arr[0]
        except Exception:
            pass
    vod_id = str(ids).split(",")[0].strip()
    vod = detail_for(vod_id)
    if not vod:
        return {"list": []}
    return {"list": [vod]}
def searchContent(key, quick=False):
    if not key or not key.strip():
        return {"list": []}
    keyword = str(key).strip()
    cached = cache_get("search:" + SRC_KEY + ":" + keyword)
    if cached:
        return {"list": cached}
    items = search_all(keyword)
    cache_set("search:" + SRC_KEY + ":" + keyword, items, 300)
    return {"list": items}
def searchContentPage(key, quick=False, pg=1):
    return searchContent(key, quick)
def playerContent(flag, ids, vipFlags=None):
    if not ids:
        return {"parse": 0, "url": ""}
    ids_s = str(ids)
    if ("__follow__" in ids_s or "__unfollow__" in ids_s or "fav:toggle" in ids_s):
        return play_for(flag, ids_s, ids_s)
    if "/" in ids:
        vod_id, key = ids.rsplit("/", 1)
    else:
        vod_id, key = ids, ""
    for _agg_n in AGG_PLATFORM_NAMES:
        if str(flag).startswith(_agg_n):
            try:
                return agg_player_content(str(flag), str(ids))
            except Exception as exc:
                log("聚合播放失败", flag, ids, exc)
                return {"parse": 0, "url": ""}
    if ":" not in vod_id:
        return {"parse": 0, "url": ""}
    if not key:
        key = ids.rsplit("/", 1)[1] if "/" in ids else ids
    return play_for(flag, vod_id, key)
def localProxy(param):
    return local_proxy(param)
class Spider:
    def __init__(self):
        self.extend = ""
    def init(self, extend=""):
        self.extend = extend or ""
        return init()
    def getName(self):
        return SRC_NAME
    def getDependence(self):
        return []
    def homeContent(self, filter=False):
        return homeContent(filter)
    def homeVideoContent(self):
        return homeVideoContent()
    def categoryContent(self, tid, pg, filter=False, extend=None):
        return categoryContent(tid, pg, filter, extend)
    def detailContent(self, ids):
        return detailContent(ids)
    def searchContent(self, key, quick=False, pg="1"):
        return searchContent(key, quick)
    def searchContentPage(self, key, quick=False, pg=1):
        return searchContentPage(key, quick, pg)
    def playerContent(self, flag, ids, vipFlags=None):
        return playerContent(flag, ids, vipFlags)
    def localProxy(self, param):
        return localProxy(param)
    def destroy(self):
        pass
def main():
    print(json.dumps(homeContent(True), ensure_ascii=False)[:500])
if __name__ == "__main__":
    main()
import concurrent.futures
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    from Crypto.Hash import HMAC, SHA256
    from Crypto.PublicKey import RSA
    from Crypto.Signature import pkcs1_15
    from Crypto.Hash import SHA256 as RSA_SHA256
    HAS_CRYPTO = True
except ImportError:
    try:
        from Cryptodome.Cipher import AES
        from Cryptodome.Util.Padding import pad, unpad
        from Cryptodome.Hash import HMAC, SHA256
        from Cryptodome.PublicKey import RSA
        from Cryptodome.Signature import pkcs1_15
        from Cryptodome.Hash import SHA256 as RSA_SHA256
        HAS_CRYPTO = True
    except ImportError:
        HAS_CRYPTO = False
AGG_PLATFORM_NAMES = ["香果", "橙果", "九果", "五果", "河果", "猫果", "芽果", "观果", "百果", "薏果", "牛果", "山果", "好果", "饭果", "星果"]
CFG = {
    "keys": "d3dGiJc651gSQ8w1",
    "charMap": {
        '+': 'P', '/': 'X', '0': 'M', '1': 'U', '2': 'l', '3': 'E', '4': 'r', '5': 'Y', '6': 'W', '7': 'b', '8': 'd', '9': 'J',
        'A': '9', 'B': 's', 'C': 'a', 'D': 'I', 'E': '0', 'F': 'o', 'G': 'y', 'H': '_', 'I': 'H', 'J': 'G', 'K': 'i', 'L': 't',
        'M': 'g', 'N': 'N', 'O': 'A', 'P': '8', 'Q': 'F', 'R': 'k', 'S': '3', 'T': 'h', 'U': 'f', 'V': 'R', 'W': 'q', 'X': 'C',
        'Y': '4', 'Z': 'p', 'a': 'm', 'b': 'B', 'c': 'O', 'd': 'u', 'e': 'c', 'f': '6', 'g': 'K', 'h': 'x', 'i': '5', 'j': 'T',
        'k': '-', 'l': '2', 'm': 'z', 'n': 'S', 'o': 'Z', 'p': '1', 'q': 'V', 'r': 'v', 's': 'j', 't': 'Q', 'u': '7', 'v': 'D',
        'w': 'w', 'x': 'n', 'y': 'L', 'z': 'e'
    },
    "headers": {
        "default": {'User-Agent': 'okhttp/4.10.0', 'Content-Type': 'application/json'},
        "form": {'User-Agent': 'okhttp/3.12.11', 'Content-Type': 'application/x-www-form-urlencoded'},
        "browser": {'User-Agent': 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36', 'Content-Type': 'application/x-www-form-urlencoded'},
        "qimao": {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.87 Safari/537.36'},
        "baidu_app": {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; 22081212C Build/PQ3B.190801.002) Talos/1.8.13 SP-engine/3.47.0 bd_dvt/1 baiduboxapp/15.21.0.10 (Baidu; P1 9)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": "BAIDUCUID=0Ovgu0uAvu0_828wj8Hma_8i28joaSuIlOvOigiAH88ikS8f0k35aD6mA"
        },
        "xingxing": {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.87 Safari/537.36'}
    },
    "platform": {
        "星果": {"host": "http://read.api.duodutek.com", "list": "/novel-api/app/pageModel/getResourceById", "detail": "/novel-api/basedata/book/getChapterList"},
        "河果": {"host": "https://freevideo.zqqds.cn", "url1": "/free-video-portal/portal"},
        "猫果": {"host": "https://api-store.qmplaylet.com", "url1": "/api/v1/playlet/index", "url2": "https://api-read.qmplaylet.com/player/api/v1/playlet/info", "search": "/api/v1/playlet/search"},
        "芽果": {"host": "https://app.whjzjx.cn", "url1": "/cloud/v2/theater/home_page?theater_class_id", "url2": "/v2/theater_parent/detail", "search": "/v3/search", "loginUrl": "https://u.shytkjgs.com/user/v1/account/login"},
        "观果": {"host": "https://api.drama.9ddm.com", "url1": "/drama/home/shortVideoTags?version_code=1500&os_type=1", "url2": "/drama/home/shortVideoDetail?version_code=1000&os_type=1", "search": "/drama/home/search?version_code=1500&os_type=1"},
        "百果": {"host": "https://mbd.baidu.com"},
        "牛果": {"host": "https://new.tianjinzhitongdaohe.com", "url1": "https://csj-sp.csjdeveloper.com"},
        "山果": {"host": "https://api.app.gxshxy.com", "url1": "https://u.app.gxshxy.com/user/v3/account/login"},
        "好果": {"host": "https://sv.baidu.com"},
        "饭果": {"host": "https://xifan-api-cn.youlishipin.com", "url1": "/xifan/drama/portalPage", "url2": "/xifan/drama/getDuanjuInfo", "search": "/xifan/search/getSearchList"},
        "薏果": {"host": "https://yimi-api.zhangyue.com", "list": "/bookstore/local/visual/channel/list", "detail": "/video/client/short_play/episode_list", "search": "/bookstore/search/recommend_data"},
        "香果": {"host": "https://xiangjiaoai.ai"},
        "橙果": {"host": "https://chengguodj.com"},
        "九果": {"host": "https://91dj1.com"},
        "五果": {"host": "https://51dj20.com"}
    },
    "platformList": [
        {"name": "香果", "id": "香果"}, {"name": "橙果", "id": "橙果"}, {"name": "九果", "id": "九果"}, {"name": "五果", "id": "五果"},
        {"name": "河果", "id": "河果"}, {"name": "猫果", "id": "猫果"}, {"name": "芽果", "id": "芽果"},
        {"name": "观果", "id": "观果"}, {"name": "百果", "id": "百果"}, {"name": "薏果", "id": "薏果"},
        {"name": "牛果", "id": "牛果"}, {"name": "山果", "id": "山果"}, {"name": "好果", "id": "好果"},
        {"name": "饭果", "id": "饭果"}, {"name": "星果", "id": "星果"}
    ],
    "filters": {
        "星果": [{"key": "area", "name": "分类", "value": [{"n": "精选", "v": "1287"}, {"n": "热门", "v": "1288"}, {"n": "新剧", "v": "1289"}]}],
        "河果": [{"key": "area", "name": "分类", "value": [{"n": "精选", "v": "53@精选"}, {"n": "古装", "v": "54@古装"}, {"n": "重生", "v": "55@重生"}, {"n": "家庭", "v": "56@家庭"}, {"n": "恋爱", "v": "57@恋爱"}]}],
        "百果": [
            {"key": "class", "name": "综合", "value": [{"n": "新剧", "v": "新剧"}, {"n": "限时免费", "v": "限时免费"}, {"n": "精选", "v": "精选"}, {"n": "独播", "v": "独播"}]},
            {"key": "area", "name": "题材", "value": [{"n": "全部", "v": "全部"}, {"n": "神医", "v": "神医"}, {"n": "都市", "v": "都市"}, {"n": "现代言情", "v": "现代言情"}, {"n": "异能", "v": "异能"}, {"n": "逆袭", "v": "逆袭"}, {"n": "甜宠", "v": "甜宠"}, {"n": "总裁", "v": "总裁"}, {"n": "萌宝", "v": "萌宝"}, {"n": "战神", "v": "战神"}, {"n": "宫斗宅斗", "v": "宫斗宅斗"}, {"n": "神豪", "v": "神豪"}, {"n": "虐恋", "v": "虐恋"}, {"n": "闪婚", "v": "闪婚"}, {"n": "玄幻", "v": "玄幻"}, {"n": "穿越重生", "v": "穿越重生"}, {"n": "年代", "v": "年代"}, {"n": "家庭伦理", "v": "家庭伦理"}, {"n": "古代言情", "v": "古代言情"}, {"n": "武侠武打", "v": "武侠武打"}, {"n": "赘婿", "v": "赘婿"}, {"n": "青春校园", "v": "青春校园"}]}
        ],
        "芽果": [{"key": "area", "name": "分类", "value": [{"n": "剧场", "v": "1"}, {"n": "热播剧", "v": "2"}, {"n": "会员专享", "v": "8"}, {"n": "星选好剧", "v": "7"}, {"n": "新剧", "v": "3"}, {"n": "阳光剧场", "v": "5"}]}],
        "饭果": [{"key": "area", "name": "分类", "value": [{"n": "全部", "v": ""}, {"n": "都市", "v": "68@都市"}, {"n": "青春", "v": "68@青春"}, {"n": "现代言情", "v": "81@现代言情"}, {"n": "豪门", "v": "81@豪门"}, {"n": "大女主", "v": "80@大女主"}, {"n": "逆袭", "v": "79@逆袭"}, {"n": "打脸虐渣", "v": "79@打脸虐渣"}, {"n": "穿越", "v": "81@穿越"}]}],
        "猫果": [{"key": "area", "name": "分类", "value": [{"n": "全部", "v": ""}, {"n": "推荐", "v": "0"}, {"n": "新剧", "v": "-1"}, {"n": "都市情感", "v": "1273"}, {"n": "古装", "v": "1272"}, {"n": "都市", "v": "571"}, {"n": "玄幻仙侠", "v": "1286"}, {"n": "奇幻", "v": "570"}, {"n": "乡村", "v": "590"}, {"n": "民国", "v": "573"}, {"n": "年代", "v": "572"}, {"n": "青春校园", "v": "1288"}, {"n": "武侠", "v": "371"}, {"n": "科幻", "v": "594"}, {"n": "末世", "v": "556"}, {"n": "二次元", "v": "1289"}, {"n": "逆袭", "v": "400"}, {"n": "穿越", "v": "373"}, {"n": "复仇", "v": "795"}, {"n": "系统", "v": "787"}, {"n": "权谋", "v": "790"}, {"n": "重生", "v": "784"}, {"n": "女性成长", "v": "1294"}, {"n": "打脸虐渣", "v": "716"}, {"n": "闪婚", "v": "480"}, {"n": "强者回归", "v": "402"}, {"n": "追妻火葬场", "v": "715"}, {"n": "家庭", "v": "670"}, {"n": "马甲", "v": "558"}, {"n": "职场", "v": "724"}, {"n": "宫斗", "v": "343"}, {"n": "高手下山", "v": "1299"}, {"n": "娱乐明星", "v": "1295"}, {"n": "异能", "v": "727"}, {"n": "宅斗", "v": "342"}, {"n": "替身", "v": "712"}, {"n": "穿书", "v": "338"}, {"n": "商战", "v": "723"}, {"n": "种田经商", "v": "1291"}, {"n": "伦理", "v": "1293"}, {"n": "社会话题", "v": "1290"}, {"n": "致富", "v": "492"}, {"n": "偷听心声", "v": "1258"}, {"n": "脑洞", "v": "526"}, {"n": "豪门总裁", "v": "624"}, {"n": "萌宝", "v": "356"}, {"n": "战神", "v": "527"}, {"n": "真假千金", "v": "812"}, {"n": "赘婿", "v": "36"}, {"n": "神医", "v": "1269"}, {"n": "神豪", "v": "37"}, {"n": "小人物", "v": "1296"}, {"n": "团宠", "v": "545"}, {"n": "欢喜冤家", "v": "464"}, {"n": "女帝", "v": "617"}, {"n": "银发", "v": "1297"}, {"n": "兵王", "v": "28"}, {"n": "虐恋", "v": "16"}, {"n": "甜宠", "v": "21"}, {"n": "悬疑", "v": "27"}, {"n": "搞笑", "v": "793"}, {"n": "灵异", "v": "1287"}]}],
        "牛果": [{"key": "area", "name": "分类", "value": [{"n": "全部", "v": ""}, {"n": "现言", "v": "现言"}, {"n": "古言", "v": "古言"}, {"n": "历史", "v": "历史"}, {"n": "都市", "v": "都市"}, {"n": "亲情", "v": "亲情"}, {"n": "玄幻", "v": "玄幻"}, {"n": "热血", "v": "热血"}, {"n": "喜剧", "v": "喜剧"}, {"n": "悬疑", "v": "悬疑"}, {"n": "军事", "v": "军事"}, {"n": "其他剧情", "v": "其他剧情"}]}],
        "山果": [{"key": "area", "name": "分类", "value": [{"n": "精选", "v": "0"}, {"n": "人气", "v": "1"}, {"n": "新剧", "v": "51"}, {"n": "甜宠", "v": "46"}, {"n": "逆袭", "v": "6"}, {"n": "强者回归", "v": "50"}, {"n": "奇幻", "v": "44"}, {"n": "复仇", "v": "49"}, {"n": "中国梦", "v": "41"}, {"n": "家庭", "v": "9"}]}],
        "好果": [{"key": "area", "name": "分类", "value": [{"n": "热播剧", "v": "1"}, {"n": "新剧", "v": "2"}, {"n": "战神", "v": "1001"}, {"n": "神豪", "v": "2001"}, {"n": "神医", "v": "1002"}, {"n": "甜宠", "v": "1007"}, {"n": "赘婿", "v": "1003"}, {"n": "穿越重生", "v": "2004"}, {"n": "异能", "v": "2005"}, {"n": "虐恋", "v": "1006"}, {"n": "宫斗宅斗", "v": "2006"}, {"n": "玄幻", "v": "2009"}]}],
        "观果": [{"key": "area", "name": "分类", "value": [{"n": "全部", "v": ""}]}],
        "薏果": [{"key": "area", "name": "分类", "value": [{"n": "精选", "v": "channel_c6f50cd9"}, {"n": "逆袭", "v": "channel_a8e10abc"}, {"n": "复仇", "v": "channel_d26dd434"}, {"n": "恋爱", "v": "channel_75afe84a"}, {"n": "重生", "v": "channel_2272aac5"}, {"n": "古风", "v": "channel_73190d4f"}, {"n": "神医", "v": "channel_2d7eae6b"}, {"n": "言情", "v": "channel_614820bd"}, {"n": "都市", "v": "channel_13dfce8b"}, {"n": "悬疑", "v": "channel_861b9642"}, {"n": "历史", "v": "channel_18157927"}]}],
        "橙果": [
            {"key": "line", "name": "频道", "value": [
                {"n": "全部", "v": "browse"}, {"n": "原创", "v": "yuanchuang"}, {"n": "魔改", "v": "mogai"},
                {"n": "AI漫剧", "v": "manju"}, {"n": "真人短剧", "v": "zhenren"}, {"n": "AI短剧", "v": "aiduanju"}, {"n": "题材分类", "v": "tags"}]},
            {"key": "type", "name": "类型", "value": [
                {"n": "全部", "v": ""}, {"n": "都市邻里", "v": "dushi"}, {"n": "甜宠恋爱", "v": "tianchong"},
                {"n": "逆袭", "v": "nixi"}, {"n": "古装玄幻", "v": "xuanhuan"}, {"n": "复仇逆袭", "v": "fuchou"},
                {"n": "霸总激情", "v": "tianchong2"}, {"n": "虐恋情深", "v": "tag-06118f"}, {"n": "惊悚悬疑", "v": "xuanyi"},
                {"n": "穿越重生", "v": "chuanyue"}, {"n": "战神归来", "v": "tag-88650e"}, {"n": "末世生存", "v": "zhanshen"}]},
            {"key": "sort", "name": "排序", "value": [
                {"n": "最热", "v": "hot"}, {"n": "最新", "v": "new"}, {"n": "追剧最多", "v": "fav"}]}
        ],
        "九果": [{"key": "theme", "name": "主题", "value": [
            {"n": "全部", "v": "0"}, {"n": "现言情欲", "v": "10"}, {"n": "禁忌伦理", "v": "11"},
            {"n": "多人情热", "v": "12"}, {"n": "调教养成", "v": "13"}, {"n": "强制爱欲", "v": "14"},
            {"n": "权色博弈", "v": "15"}, {"n": "青春校园", "v": "16"}, {"n": "双修玄奇", "v": "17"}, {"n": "田园野情", "v": "18"}]},
            {"key": "setting", "name": "设定", "value": [
                {"n": "全部", "v": "0"}, {"n": "人妻熟女", "v": "56"}, {"n": "职场潜规则", "v": "57"},
                {"n": "金主包养", "v": "58"}, {"n": "出轨报复", "v": "59"}, {"n": "豪门专宠", "v": "60"},
                {"n": "契约肉偿", "v": "61"}, {"n": "欲擒故纵", "v": "62"}, {"n": "反差占有", "v": "63"},
                {"n": "金屋囚禁", "v": "64"}, {"n": "车内户外", "v": "65"}, {"n": "圈内禁忌", "v": "88"}]},
            {"key": "background", "name": "背景", "value": [
                {"n": "全部", "v": "0"}, {"n": "都市夜色", "v": "39"}, {"n": "深宫权欲", "v": "40"},
                {"n": "异界双修", "v": "41"}, {"n": "年代旧情", "v": "42"}, {"n": "乡野荒情", "v": "43"}]},
            {"key": "time", "name": "时间", "value": [
                {"n": "全部", "v": "0"}, {"n": "7天内", "v": "1"}, {"n": "14天内", "v": "2"}, {"n": "30天内", "v": "3"}, {"n": "90天内", "v": "4"}]},
            {"key": "recommend", "name": "排序", "value": [
                {"n": "默认", "v": "0"}, {"n": "最新", "v": "1"}, {"n": "最热", "v": "2"}]}],
        "五果": [
            {"key": "cid", "name": "频道", "value": [
                {"n": "剧集", "v": "drama"}, {"n": "演员", "v": "actor"}, {"n": "剧集周榜", "v": "drama_week"},
                {"n": "剧集月榜", "v": "drama_month"}, {"n": "AI成人短剧", "v": "aisd"}]},
            {"key": "sort", "name": "演员排序", "value": [
                {"n": "热门", "v": "hot"}, {"n": "男演员", "v": "2"}, {"n": "女演员", "v": "1"},
                {"n": "新人榜", "v": "new"}, {"n": "推荐榜", "v": "recommend"}]},
            {"key": "theme", "name": "主题", "value": [
                {"n": "全部", "v": "0"}, {"n": "成人", "v": "1"}, {"n": "AI漫剧", "v": "46"}, {"n": "51原创", "v": "47"},
                {"n": "AI魔改短剧", "v": "51"}, {"n": "致富", "v": "63"}, {"n": "修仙", "v": "59"}, {"n": "厨神", "v": "60"},
                {"n": "读心", "v": "61"}, {"n": "今古联通", "v": "62"}, {"n": "女性成长", "v": "4"}, {"n": "鉴宝", "v": "64"},
                {"n": "亲情", "v": "65"}, {"n": "末世", "v": "66"}, {"n": "武侠", "v": "67"}, {"n": "萌宠", "v": "68"},
                {"n": "萌宝", "v": "69"}, {"n": "真假千金", "v": "70"}, {"n": "青春", "v": "18"}, {"n": "现言", "v": "3"},
                {"n": "奇幻", "v": "5"}, {"n": "战神", "v": "6"}, {"n": "宫斗", "v": "7"}, {"n": "古言", "v": "8"},
                {"n": "玄幻", "v": "9"}, {"n": "脑洞", "v": "10"}, {"n": "权谋", "v": "11"}, {"n": "年代爱情", "v": "12"},
                {"n": "种田", "v": "15"}, {"n": "悬疑", "v": "13"}, {"n": "民国爱情", "v": "16"}, {"n": "轻松喜剧", "v": "17"},
                {"n": "志怪", "v": "19"}, {"n": "超能", "v": "58"}, {"n": "强制", "v": "57"}, {"n": "异世界", "v": "56"},
                {"n": "NTR", "v": "55"}, {"n": "纯爱", "v": "71"}, {"n": "群像", "v": "78"}]},
            {"key": "setting", "name": "设定", "value": [
                {"n": "全部", "v": "0"}, {"n": "后宫", "v": "20"}, {"n": "NTR", "v": "55"}, {"n": "反差", "v": "38"},
                {"n": "淫妻", "v": "74"}, {"n": "少妇", "v": "73"}, {"n": "大女主", "v": "7"}, {"n": "系统", "v": "29"},
                {"n": "重生", "v": "27"}, {"n": "穿越", "v": "28"}, {"n": "神豪", "v": "23"}, {"n": "打脸虐渣", "v": "25"},
                {"n": "马甲", "v": "26"}, {"n": "追妻/夫火葬场", "v": "72"}, {"n": "互相救赎", "v": "22"}, {"n": "甜宠", "v": "88"},
                {"n": "双向奔赴", "v": "48"}, {"n": "传承觉醒", "v": "38"}, {"n": "家长里短", "v": "37"}, {"n": "破镜重圆", "v": "36"},
                {"n": "虐恋", "v": "35"}, {"n": "霸总", "v": "34"}, {"n": "强者回归", "v": "33"}, {"n": "先婚后爱", "v": "32"},
                {"n": "小人物", "v": "31"}, {"n": "逆袭", "v": "39"}, {"n": "伦理", "v": "92"}, {"n": "出轨", "v": "98"},
                {"n": "偷情", "v": "97"}, {"n": "御姐", "v": "89"}, {"n": "萝莉", "v": "88"}, {"n": "替嫁", "v": "82"},
                {"n": "团宠", "v": "81"}, {"n": "无CP", "v": "80"}]},
            {"key": "background", "name": "背景", "value": [
                {"n": "全部", "v": "0"}, {"n": "校园", "v": "54"}, {"n": "架空", "v": "53"}, {"n": "民国", "v": "52"},
                {"n": "职场", "v": "45"}, {"n": "年代", "v": "44"}, {"n": "现代", "v": "40"}, {"n": "都市", "v": "41"},
                {"n": "古代", "v": "42"}, {"n": "乡村", "v": "43"}]},
            {"key": "audience", "name": "受众", "value": [
                {"n": "全部", "v": "0"}, {"n": "男", "v": "1"}, {"n": "女", "v": "2"}]},
            {"key": "time", "name": "时间", "value": [
                {"n": "全部", "v": "0"}, {"n": "7天内", "v": "7"}, {"n": "14天内", "v": "14"}, {"n": "30天内", "v": "30"}, {"n": "90天内", "v": "90"}]},
            {"key": "recommend", "name": "推荐", "value": [
                {"n": "默认", "v": "0"}, {"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "原创", "v": "original"}]}
        ]
    },
    "filter_def": {
"星果": {"area": "1287"}, "河果": {"area": "53@精选"},
        "芽果": {"area": "1"}, "饭果": {"area": "68@都市"}, "猫果": {"area": "0"},
        "观果": {"area": ""}, "牛果": {"area": "全部"}, "山果": {"area": "1"}, "好果": {"area": "1"},
        "百果": {"class": "新剧", "area": "全部"}, "薏果": {"area": "channel_c6f50cd9"},
        "香果": {"cat": "recommend"}, "橙果": {"line": "browse", "sort": "hot"},
        "九果": {}, "五果": {"cid": "drama"}
    }
}
def md5_sign(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()
def hmac_sha256(msg, key):
    if HAS_CRYPTO:
        h = HMAC.new(key.encode('utf-8'), msg.encode('utf-8'), digestmod=SHA256)
        return h.hexdigest()
    return ""
def agg_aes_cbc_encrypt(data, key, iv):
    if not HAS_CRYPTO: return ""
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ct = cipher.encrypt(pad(data.encode('utf-8'), AES.block_size))
    return ct.hex().upper()
def agg_aes_cbc_decrypt(hex_data, key, iv):
    if not HAS_CRYPTO: return ""
    try:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        pt = unpad(cipher.decrypt(bytes.fromhex(hex_data)), AES.block_size)
        return pt.decode('utf-8')
    except Exception: return ""
def aes_ecb_encrypt(data, key):
    if not HAS_CRYPTO: return ""
    cipher = AES.new(key.encode('utf-8'), AES.MODE_ECB)
    ct = cipher.encrypt(pad(data.encode('utf-8'), AES.block_size))
    return base64.b64encode(ct).decode('utf-8')
def aes_ecb_decrypt(b64_data, key):
    if not HAS_CRYPTO: return ""
    try:
        cipher = AES.new(key.encode('utf-8'), AES.MODE_ECB)
        pt = unpad(cipher.decrypt(base64.b64decode(b64_data)), AES.block_size)
        return pt.decode('utf-8')
    except Exception: return ""
def aes_gcm_decrypt(cipher_hex, iv_hex, key):
    if not HAS_CRYPTO: return "{}"
    try:
        enc_bytes = bytes.fromhex(cipher_hex)
        tag = enc_bytes[-16:]
        ciphertext = enc_bytes[:-16]
        cipher = AES.new(key.encode('utf-8'), AES.MODE_GCM, bytes.fromhex(iv_hex))
        pt = cipher.decrypt_and_verify(ciphertext, tag)
        return pt.decode('utf-8')
    except Exception: return "{}"
def rsa_sign_yimi(data, priv_key_pem):
    if not HAS_CRYPTO: return ""
    try:
        key = RSA.import_key(priv_key_pem)
        h = RSA_SHA256.new(data.encode('utf-8'))
        signature = pkcs1_15.new(key).sign(h)
        return base64.b64encode(signature).decode('utf-8')
    except Exception:
        return ""
YIMI_PRIV_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDwCPsMptVn80Im4VVfJ2uAkjs7NpJzzsyGxleK1uN9ux/KTiY2o8kiXcRIcAYVChfdX4ywUs0jrjh8iTcC91r6qgeBaDS8wWsL5bZrn7O/8sqq2hbizV4AvvsqhxVJzRUJZjbNOcMZOPJoeL5K4U4YsiOyV8a9lt5C6zEC4Qy0xjscvOTGyVTqtWeJedEedXtiKLQxAiy6OKJxyHQqdwMHUfAgAbLzAHcVpg1RSXwud+5vtTJNXOXT98FHoFDcRIEcHiiqfU9dskzAhG2nPbFujO+YFq9tZBrWmrhPaXcHfXZqtEYePM4vuvMYjhmANdG4Ehl6pN9nuEaLZ+L35/3nAgMBAAECggEBAOe+M+s2E2ll8WMqQEs6+s5J4Ee9201Vxh8E1TYlW8Ni60FdjAVKwgCc+Mla5nRfp0TCYElH1+hv5vdNXsBNYhgKGm701Z27O4dkA2gK6vcSCFtFbb0Qu4YK3OFlQ8dZ6cqGVbhz4Qmz8k2s7UPMHKM5Mb+YgTc/tlxzR4FZF/RaY8MDpv6iMcXPY27xJzZAV1jROCXjZTZNYbgjsKDAbthRDkjMyuKCIdq7rAHrEyFSx3n7/uxnZYh42bXzWyyWudbkAJoq1ZYx+NyYj5TsN/WNoYbCPcX0Ko+CNnpkC/6qtQbHrBiMprnld67qdLCVhWpmOBYukXVPwFMJjOFlYKkCgYEA+WDh3LpitYSO6hn7mhnbqEQba13cutbJW9RQa0BjGf1OGXdqXpimcWK7viZYAKhLlyGWQmoWduDq4bjSRx7ZxY8pMtpIUWoVkKItD7D2yvmYN1guHNRpHlUIAsSH3HGwQIeXy36hJcB5gC+3XgRVPz/juTMWJDC0usECNFz17bsCgYEA9miWi6JPnZ1ffQzAyE+P6vGC/Vrl7Uyr9gqxI/OkZa8bUqfZtGo5UDGSaGRUsoTsYiEJ8m5blPY0X4xr5x1kO6rfk0gHxn1OXlCP42yT2+CqQvjNO2DHOnWNryKjmAqaAITbmC2lgj0PiiPO32ZT3aXTOgwxTKbFP3LBDmwA18UCgYAQuEgsbmqz1OFoHLnbySQLEhXsiuyDsmbpu0BxEG4UjgEwf+sn0IBIVeBUjWmVEbOPvHbAmTBMZCQbYjLnBdCACGswt6Xln4E2o0j2Jl1Fmpp0C3t7/1nU6MqStO6O/yhcCztIL4NKbq82wvw+V3gHt5bjEePIJWPYqZwmOp1ahQKBgCqfHKs6gBr7RbETq6T6XiJ9c/Lu7iaFxJjicJGPazhLeaZqcjXKye8dI/36nMvkQh8XJ+lPPXgeviBo4aEwbE4F2HZZVz72HcAin0DvXwQBcHH1J0rGCrAJ9V/91d5OtySv1mwUOTS16yIx3260/HyyWj8ILN7dWfEHoG0mMV8hAoGBAI0KBzR9WfzxNKI4ZqRD9/sN+SH4oxymo2oJ+FnOW7hk1E0EyrsGzIDCrS/f7MPzLJI7F4DULsrU5RIQyouIybZra29Vqe4L8kdIae5O0R4Y2r7gt/yWo4cWnW53Q0f5o7mzV10Dc8ewuT1DyJrt25dMWsGsP8rQ/0pVUBLEf93b
-----END PRIVATE KEY-----"""
def fetch_json(url, method='GET', headers=None, data=None):
    try:
        if method == 'GET':
            r = requests.get(url, headers=headers, timeout=10, verify=False)
        else:
            if isinstance(data, dict):
                data = json.dumps(data, separators=(',', ':')).encode('utf-8')
            r = requests.post(url, headers=headers, data=data, timeout=10, verify=False)
        res = r.json()
        if res: return res
    except Exception:
        pass
    try:
        import urllib.request
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=headers or {}, method=method)
        if data and method != 'GET':
            if isinstance(data, dict):
                data = json.dumps(data, separators=(',', ':')).encode('utf-8')
            elif isinstance(data, str):
                data = data.encode('utf-8')
            resp = urllib.request.urlopen(req, data=data, timeout=10, context=ctx)
        else:
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        return json.loads(resp.read().decode('utf-8'))
    except Exception:
        return {}
def fetch_text(url, method='GET', headers=None, data=None):
    try:
        if method == 'GET':
            r = requests.get(url, headers=headers, timeout=10, verify=False)
        else:
            if isinstance(data, dict):
                data = json.dumps(data, separators=(',', ':')).encode('utf-8')
            r = requests.post(url, headers=headers, data=data, timeout=10, verify=False)
        r.encoding = 'utf-8'
        if r.text: return r.text
    except Exception:
        pass
    try:
        import urllib.request
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=headers or {}, method=method)
        if data and method != 'GET':
            if isinstance(data, dict):
                data = json.dumps(data, separators=(',', ':')).encode('utf-8')
            elif isinstance(data, str):
                data = data.encode('utf-8')
            resp = urllib.request.urlopen(req, data=data, timeout=10, context=ctx)
        else:
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        return resp.read().decode('utf-8')
    except Exception:
        return ""
def build_query(params):
    return "&".join(f"{urllib.parse.quote(str(k))}={urllib.parse.quote(str(v))}" for k, v in params.items())
class HMService:
    key_hex = "647a6b6a67667978677368796c677a6d"
    iv_hex = "6170697570646f776e65646372797074"
    datas = "e5f22c6e2c82fe001738cb9ce4696eab0556d064a55aef402e0fbe6b29a083f6538e4567de38e67de2071a49d9751526bfba45314e1fd4702b11c76ab9a3b5f873262854ba66e6715ed51364dbc6ee62c7180e047fcbcdbfd49874fc8f28674b16d90ca71a02de76c70598e0b75e647c37c2c19287e49be5f2a259d727dfc4df3d28802388bf3c356576b342e17e30a2ab74859263dba4d1c8eba79990d22d60d60927fdacb2addf2f0eaadd8887585ca2eb87f603faf0c207dda18cf67dc25b2199d303baff9e6605b3314a7d2631f62864f48619daceb9452f2b7b0667773553741856df030cca68af3c57810f983d452bb428ef5fc32206aef4865ae06c629bee7f5135547304acc7ef4e7c6df887308f2e79c493fd2ee03488722861b5bb51b09cb8911dfc92c288d94e601c066d2f9d612ad2c8d4eeb4920b1d44aff3e13fd75229b857f64925df1cf12f75a00d438c422ec1726462b915903f1dd1f4bb7cdf82cc15a6d507f80c789903e710f39a62aef073f3f93a6c681e75d295428aa290d7e98f82e7e9ad6e2b23d9086dfe8c63c5d8550b13fd61a77291473a8bdd43c7c2639f264be69d9d07f0585de4342a399275a64e7d1d4400b8ed4421a2f289f622e40cdd1cfc916a0b9ce747c924ac33e32d24b91ed5d64772d6ad6896412f52724006eabf12aaecfd6e81dad432c7b3800bbf793a1c375e3e7b4fb3b097724b5fc88a8c9bcf3dbc10cbdb252965"
    @classmethod
    def api(cls, code, bodyData):
        if not HAS_CRYPTO: return {}
        url = CFG["platform"]["河果"]["host"] + CFG["platform"]["河果"]["url1"] + "/" + code
        key_b = bytes.fromhex(cls.key_hex)
        iv_b = bytes.fromhex(cls.iv_hex)
        cipher = AES.new(key_b, AES.MODE_CBC, iv_b)
        enc_body = cipher.encrypt(pad(json.dumps(bodyData).encode('utf-8'), AES.block_size)).hex().upper()
        headers = {'datas': cls.datas, 'content-type': 'text/plain', 'user-agent': 'okhttp/4.10.0', 'Referer': 'https://freevideo.zqqds.cn'}
        raw_res = fetch_text(url, method='POST', headers=headers, data=enc_body)
        try:
            res = json.loads(raw_res)
            if res and res.get("data"):
                enc_bytes = bytes.fromhex(res["data"])
                cipher_dec = AES.new(key_b, AES.MODE_CBC, iv_b)
                dec = unpad(cipher_dec.decrypt(enc_bytes), AES.block_size).decode('utf-8')
                return json.loads(dec)
        except Exception:
            pass
        return {}
class NNService:
    token = ""
    csj_token = ""
    device_id = "aa11fc54-ba9c-3980-add5-447d3fa5b939"
    @classmethod
    def ensureAuth(cls):
        if cls.token: return
        headers = {"deviceid": cls.device_id, "User-Agent": "okhttp/4.12.0", "client": "app"}
        r = fetch_json("https://new.tianjinzhitongdaohe.com/api/v1/app/user/visitorInfo", headers=headers)
        cls.token = r.get("data", {}).get("token", "")
        if cls.token: return
        h2 = headers.copy()
        h2["Content-Type"] = "application/json;charset=UTF-8"
        r = fetch_json("https://new.tianjinzhitongdaohe.com/api/v1/app/user/visitorInfo", method='POST', headers=h2, data={})
        cls.token = r.get("data", {}).get("token", "")
    @classmethod
    def ensureCsjAuth(cls):
        if cls.csj_token: return
        try:
            t = str(int(time.time()))
            body = f"ac=wifi&os=Android&vod_version=1.10.21.6-tob&os_version=9&type=1&clientVersion=v5.2.5&uuid=Y4WNZ3SAWK7MAJMH7CXCDHJ4VMPVFRZQTBSIA4XTYO4AWEUHIK6Q01&resolution=1280*2618&openudid=889edced38f1069b&dt=Pixel%204&sha1=46121F77CE2FCAD3DBC3B9EC8A24908C1A8AD6D9&os_api=28&install_id=1549688030634536&device_brand=google&sdk_version=1.1.3.0&package_name=com.niuniu.ztdh.app&siteid=5627189&dev_log_aid=667431&oaid=&timestamp={t}"
            nonce = "VX1KKGtoBDCi1fB1"
            sig = hmac_sha256(t + nonce + body, 'aceaa47f96b4875d446b2e1d97e03bbb')
            enc_body = aes_ecb_encrypt(body, 'dafdb3d2a5c343d6')
            h = {'X-Salt': '786774955F', 'X-Nonce': nonce, 'X-Timestamp': t, 'X-Signature': sig, 'Content-Type': 'application/x-www-form-urlencoded'}
            r = fetch_text(f"{CFG['platform']['牛果']['url1']}/csj_sp/api/v1/user/login?siteid=5627189", method="POST", headers=h, data=enc_body)
            dec = aes_ecb_decrypt(r, 'dafdb3d2a5c343d6')
            cls.csj_token = json.loads(dec).get("data", {}).get("access_token", "")
        except Exception: pass
    @classmethod
    def api(cls, url, body):
        cls.ensureAuth()
        if not cls.token: raise Exception("牛果获取Token失败")
        h = {"token": cls.token, "deviceid": cls.device_id, "content-type": "application/json;charset=UTF-8", "User-Agent": "okhttp/4.12.0", "client": "app"}
        return fetch_json(url, method='POST', headers=h, data=body)
    @classmethod
    def post1(cls, url1, data1, index="1"):
        cls.ensureCsjAuth()
        t10 = str(int(time.time()))
        nonce = "X9UknYKtLa3DmtjC"
        body1 = re.sub(r'&lock_free=\d+', "&lock_free=1", data1)
        body1 = re.sub(r'&timestamp=\d+', f"&timestamp={t10}", body1)
        body1 = re.sub(r'&count=\d+', "&count=1", body1)
        body1 = re.sub(r'&index=\d+', f"&index={index}", body1)
        body1 = re.sub(r'&lock_ad=\d+', "&lock_ad=1", body1)
        body1 = re.sub(r'&lock_index=\d+', f"&lock_index={index}", body1)
        enc_body = aes_ecb_encrypt(body1, 'ce49b18dd4e0a4d8')
        sig = hmac_sha256(t10 + nonce + body1, 'aceaa47f96b4875d446b2e1d97e03bbb')
        h = {'X-Salt': 'FD8188A8D5', 'X-Nonce': nonce, 'X-Timestamp': t10, 'X-Access-Token': cls.csj_token, 'X-Signature': sig, 'User-Agent': 'okhttp/3.12.11', 'Content-Type': 'application/x-www-form-urlencoded'}
        r = fetch_text(url1, method='POST', headers=h, data=enc_body)
        dec = aes_ecb_decrypt(r, 'ce49b18dd4e0a4d8')
        try: return json.loads(dec)
        except Exception: return {}
class SHService:
    token = ""
    key = "xxxxxxwhwqedqder"
    @classmethod
    def ensureAuth(cls):
        if cls.token: return
        try:
            body = json.dumps({"device": "22ebfeec0a5ad3c0397bae448b8658cc3", "install_first_open": True, "first_install_time": 1751687627754, "last_update_time": 1751687627754, "report_link_url": "", "android_id": "8f7db6f23d745890", "package_name": "com.shanhai.duanju", "authorization": "", "timestamp": int(time.time()*1000)})
            enc_body = aes_ecb_encrypt(body, "B@ecf920Od8A4df7")
            r = fetch_json(CFG['platform']['山果']['url1'], method='POST', headers={"content-type": "application/json; charset=utf-8"}, data=enc_body)
            cls.token = r.get("data", {}).get("token", "")
        except Exception: pass
    @classmethod
    def request(cls, url):
        cls.ensureAuth()
        r = fetch_json(url, headers={"authorization": cls.token})
        if r and "data" in r and "data" in r["data"]:
            dec = aes_gcm_decrypt(r["data"]["data"], r["data"]["nonce"], cls.key)
            return json.loads(dec)
        return {}
def getQmParamsAndSign():
    session_id = str(int(time.time() * 1000))
    data = {"static_score": "0.8", "uuid": "00000000-7fc7-08dc-0000-000000000000", "device-id": "20250220125449b9b8cac84c2dd3d035c9052a2572f7dd0122edde3cc42a70", "mac": "", "sourceuid": "aa7de295aad621a6", "refresh-type": "0", "model": "22021211RC", "wlb-imei": "", "client-id": "aa7de295aad621a6", "brand": "Redmi", "oaid": "", "oaid-no-cache": "", "sys-ver": "12", "trusted-id": "", "phone-level": "H", "imei": "", "wlb-uid": "aa7de295aad621a6", "session-id": session_id}
    json_str = json.dumps(data, separators=(',', ':'))
    b64_str = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
    qm_params = "".join(CFG["charMap"].get(c, c) for c in b64_str)
    sign_str = f"AUTHORIZATION=app-version=10001application-id=com.duoduo.readchannel=unknownis-white=net-env=5platform=androidqm-params={qm_params}reg={CFG['keys']}"
    sign = md5_sign(sign_str)
    return qm_params, sign
def getHeaderX():
    qm_params, sign = getQmParamsAndSign()
    return {'net-env': '5', 'reg': '', 'channel': 'unknown', 'is-white': '', 'platform': 'android', 'application-id': 'com.duoduo.read', 'authorization': '', 'app-version': '10001', 'user-agent': 'webviewversion/0', 'qm-params': qm_params, 'sign': sign}
def yimiGetHeaders(path, params, sec):
    ts = str(int(time.time() * 1000))
    str3 = f"&{params}&{path}&{ts}&{sec}"
    sign = rsa_sign_yimi(str3, YIMI_PRIV_KEY)
    return {"x-appid": "zy9351ae", "x-sig-timestamp": ts, "x-sig-alg": "RSA-SHA256", "x-sig-sign": sign, "x-sig-ver": "v1.1", "x-sig-sec": sec, "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 15; 22081212C Build/AQ3A.241006.001)"}
def imgDecode(data):
    for key, iv in ((b"f5d965df75336270", b"97b60394abc2fbe1"),):
        try:
            dec = AES.new(key, AES.MODE_CBC, iv).decrypt(data)
        except Exception:
            continue
        if dec[:3] == b"\xff\xd8\xff":
            end = dec.find(b"\xff\xd9")
            return dec[:end + 2] if end != -1 else dec
        if dec[:8] == b"\x89PNG\r\n\x1a\n":
            return dec
        if dec[:4] == b"RIFF" and dec[8:12] == b"WEBP":
            return dec
    return None
def imgInline(raw):
    if not raw or raw.startswith("data:") or "cover-placeholder" in raw:
        return ""
    try:
        r = requests.get(raw, headers={"User-Agent": "Mozilla/5.0"}, timeout=12, verify=False)
        data = r.content or b""
        if not data:
            return ""
        img = imgDecode(data)
        if not img:
            return ""
        if img[:8] == b"\x89PNG\r\n\x1a\n":
            mime = "image/png"
        elif img[:4] == b"RIFF" and img[8:12] == b"WEBP":
            mime = "image/webp"
        else:
            mime = "image/jpeg"
        return "data:" + mime + ";base64," + base64.b64encode(img).decode("utf-8")
    except Exception:
        return ""
def imgProxy(raw):
    if not raw or raw.startswith("data:") or "cover-placeholder" in raw:
        return ""
    try:
        proxy = getProxyUrl()
    except Exception:
        proxy = ""
    if proxy:
        sep = "&" if "?" in proxy else "?"
        b64 = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8").rstrip("=")
        return proxy + sep + "type=img&u=" + b64
    return imgInline(raw)
XJ_SITE = "https://xiangjiaoai.ai"
XJ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Referer": XJ_SITE + "/",
    "Origin": XJ_SITE,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}
XJ_API_HEADERS = {
    "User-Agent": XJ_HEADERS["User-Agent"],
    "Referer": XJ_SITE + "/",
    "Origin": XJ_SITE,
    "Accept": "application/json, text/plain, */*",
}
XJ_CURSOR = {}
def xjHomeClasses():
    out = [{"n": "最新推荐", "v": "recommend"}]
    try:
        j = json.loads(fetch_text(XJ_SITE + "/api/categories", headers=XJ_API_HEADERS))
        for c in (j.get("data") or []):
            if c:
                out.append({"n": str(c.get("name", "")), "v": str(c.get("id", ""))})
    except Exception:
        pass
    return out
def xjVideos(tid, pg):
    pg = int(pg or 1)
    if str(tid) == "recommend":
        url = XJ_SITE + "/api/theater?sort=latest&limit=20"
    else:
        url = XJ_SITE + "/api/theater?category_id=" + str(tid) + "&limit=20"
    if pg > 1 and XJ_CURSOR.get(str(tid) + "_" + str(pg - 1)):
        url += "&cursor=" + urllib.parse.quote(XJ_CURSOR[str(tid) + "_" + str(pg - 1)])
    out = []
    try:
        j = json.loads(fetch_text(url, headers=XJ_API_HEADERS))
        data = j.get("data") or {}
        items = data.get("items") if isinstance(data, dict) else (data if isinstance(data, list) else [])
        nc = data.get("next_cursor") if isinstance(data, dict) else ""
        if nc:
            XJ_CURSOR[str(tid) + "_" + str(pg)] = nc
        for it in items:
            ec = it.get("episode_count") or 0
            out.append({"vod_name": str(it.get("title", "")), "vod_pic": str(it.get("cover_url", "")),
                        "vod_remarks": ("香果 | 全%s集" % ec) if ec else "香果 | 更新中",
                        "vod_id": "香果@" + str(it.get("id", ""))})
    except Exception:
        pass
    return out
def xjSearch(key):
    out = []
    try:
        j = json.loads(fetch_text(XJ_SITE + "/api/search?q=" + urllib.parse.quote(str(key)) + "&limit=30", headers=XJ_API_HEADERS))
        for it in ((j.get("data") or {}).get("items") or []):
            out.append({"vod_name": str(it.get("title", "")), "vod_pic": str(it.get("cover_url", "")),
                        "vod_remarks": "香果 | 短劇", "vod_id": "香果@" + str(it.get("id", ""))})
    except Exception:
        pass
    return out
def xjDetail(vid):
    vid = str(vid or "")
    html = fetch_text(XJ_SITE + "/dramas/" + vid, headers=XJ_HEADERS)
    name = vid
    pic = ""
    desc = ""
    ep_count = 30
    m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html) or re.search(r'<title>([^<]+)</title>', html)
    if m:
        name = m.group(1).split("|")[0].split("-")[0].strip()
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
    if m:
        pic = m.group(1)
    m = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', html)
    if m:
        desc = m.group(1)
    m = re.search(r'(\d+)\s*集', html)
    if m:
        ep_count = int(m.group(1))
    play_urls = ["第%s集$%s" % (i, XJ_SITE + "/dramas/" + vid + "?ep=" + str(i)) for i in range(1, ep_count + 1)]
    return {"vod_id": "香果@" + vid, "vod_name": name, "vod_pic": pic, "type_name": "短劇",
            "vod_remarks": "共%s集" % ep_count, "vod_content": desc,
            "vod_play_from": "香果", "vod_play_url": "#".join(play_urls)}
def xjPlayer(id):
    ph = {"User-Agent": XJ_HEADERS["User-Agent"], "Referer": XJ_SITE + "/", "Origin": XJ_SITE}
    id = str(id or "")
    if id.startswith("http"):
        if ".m3u8" in id or ".mp4" in id:
            return {"parse": 0, "playUrl": "", "url": id, "header": ph}
        html = fetch_text(id, headers=XJ_HEADERS)
        mm = re.search(r'https?://[^\s"\'<>]+?\.(?:m3u8|mp4)[^\s"\'<>]*', html)
        if mm:
            return {"parse": 0, "playUrl": "", "url": mm.group(0), "header": ph}
    return {"parse": 1, "url": id, "header": ph}
CG_HOST = "https://chengguodj.com"
CG_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Mobile Safari/537.36",
    "Referer": CG_HOST + "/",
}
def cgGet(url, retries=2):
    for i in range(retries + 1):
        h = fetch_text(url, headers=CG_HEADERS)
        if h:
            return h
        if i < retries:
            time.sleep(2)
    return ""
def cgParseList(h):
    videos = []
    seen = set()
    for card_m in re.finditer(r'<a class="card-main" href="(/play/([^"]+))"[^>]*>(.*?)</a>', h, re.S):
        vid = card_m.group(2)
        if vid in seen:
            continue
        seen.add(vid)
        card_html = card_m.group(3)
        title_m = re.search(r'<b class="card-title">([^<]+)</b>', card_html)
        title = title_m.group(1).strip() if title_m else ""
        fb_m = re.search(r'data-cover-fb="([^"]+)"', card_html)
        img_m = re.search(r'(?:z-image-loader-url|src)="([^"]+)"', card_html)
        cover = fb_m.group(1) if fb_m else (img_m.group(1) if img_m else "")
        if cover and cover.startswith("/"):
            cover = CG_HOST + cover
        videos.append({"vod_id": "橙果@" + vid, "vod_name": title, "vod_pic": cover, "vod_remarks": "橙果"})
    return videos
def cgExtractEps(h):
    idx = h.find('"episodes":')
    if idx < 0:
        return []
    i = idx + len('"episodes":')
    depth = 0
    while i < len(h):
        if h[i] == "[":
            depth += 1
        elif h[i] == "]":
            depth -= 1
            if depth == 0:
                break
        i += 1
    try:
        return json.loads(h[idx + len('"episodes":'):i + 1])
    except Exception:
        return []
def cgFindM3u8(h):
    m = re.search(r'https?://[^\s"\'<>{}|^~`\[\]]+\.m3u8[^\s"\'<>{}|^~`\[\]]*', h)
    return m.group(0) if m else ""
def cgDetail(vid):
    vid = str(vid or "")
    h = cgGet(CG_HOST + "/play/" + vid)
    if not h:
        return {}
    title_m = re.search(r'"title":"([^"]+)"', h)
    pic_m = re.search(r'"poster":"([^"]+)"', h)
    total_ep_m = re.search(r'"totalEp":(\d+)', h)
    desc_m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)', h, re.I)
    title = title_m.group(1) if title_m else vid
    pic = pic_m.group(1) if pic_m else ""
    total_ep = int(total_ep_m.group(1)) if total_ep_m else 1
    desc = desc_m.group(1).strip() if desc_m else ""
    if pic and pic.startswith("/"):
        pic = CG_HOST + pic
    eps = cgExtractEps(h)
    play_urls = []
    has_hls = set()
    for ep in eps:
        n = ep.get("n", 1)
        hls_url = ep.get("hls", "")
        if hls_url:
            play_urls.append("第%s集$%s" % (n, hls_url))
            try:
                has_hls.add(int(n))
            except Exception:
                pass
    for ep in eps:
        n = ep.get("n", 1)
        if n not in has_hls:
            play_urls.append("第%s集$%s" % (n, CG_HOST + "/play/" + vid + "/" + str(n)))
    play_urls.sort(key=lambda x: int(re.sub(r"\D", "", x.split("$")[0]) or 1))
    return {"vod_id": "橙果@" + vid, "vod_name": title, "vod_pic": pic,
            "vod_content": desc or "共%s集" % total_ep,
            "vod_play_from": "橙果", "vod_play_url": "#".join(play_urls)}
def cgPlayer(id):
    id = str(id or "")
    if id.startswith("http"):
        if ".m3u8" in id:
            return {"parse": 0, "playUrl": "", "url": id}
        return {"parse": 1, "playUrl": "", "url": id}
    url = CG_HOST + "/" + id.lstrip("/")
    h = cgGet(url)
    if not h:
        return {"parse": 1, "playUrl": "", "url": url}
    m3u8 = cgFindM3u8(h)
    if m3u8:
        return {"parse": 0, "playUrl": "", "url": m3u8}
    esc = re.search(r'https:\\?/\\?/[^\s"\'<>{}|^~`\[\]]+\.m3u8[^\s"\'<>{}|^~`\[\]]*', h)
    if esc:
        return {"parse": 0, "playUrl": "", "url": esc.group(0).replace("\\/", "/")}
    return {"parse": 1, "playUrl": "", "url": url}
JG_ENC_KEY = b"2acf7e91e9864673"
JG_ENC_IV = b"1c29882d3ddfcfd6"
JG_IMG_KEY = b"f5d965df75336270"
JG_IMG_IV = b"97b60394abc2fbe1"
JG_SL = {"bundleId": "com.pwa.mater", "version": "1.3.2", "oauth_type": "web", "language": "zh",
         "via": "pwa", "oauth_id": "7d05538c4b8a5e74e82f93c0dab0163c", "token": "", "trace_id": "7d05538c4b8a5e74e82f93c0dab0163c"}
JG_TAGS = {"ShallowReactive", "Reactive", "Ref", "Computed", "ShallowRef", "Raw"}
def jgDecrypt(data_b64):
    if not HAS_CRYPTO:
        return ""
    s = str(data_b64).replace(" ", "+")
    s += "=" * (-len(s) % 4)
    raw = base64.b64decode(s)
    cipher = AES.new(JG_ENC_KEY, AES.MODE_CBC, JG_ENC_IV)
    pt = cipher.decrypt(raw)
    pad = pt[-1]
    if 1 <= pad <= 16:
        pt = pt[:-pad]
    return pt.decode("utf-8", errors="replace")
def jgApi(path, params):
    body = dict(JG_SL)
    body.update(params or {})
    try:
        obj = json.loads(fetch_text("https://91dj1.com/api.php" + path, method="POST", headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Referer": "https://91dj1.com/", "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9", "Content-Type": "application/x-www-form-urlencoded"},
            data=urllib.parse.urlencode(body)))
    except Exception:
        return {}
    enc = obj.get("data") if isinstance(obj, dict) else None
    if isinstance(enc, dict):
        return enc
    if not isinstance(enc, str) or not enc:
        return {}
    try:
        dec = json.loads(jgDecrypt(enc))
        return dec.get("data") if isinstance(dec, dict) else {}
    except Exception:
        return {}
def jgPayload(html):
    m = re.search(r'<script[^>]+id=["\']__NUXT_DATA__["\'][^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        raw = json.loads(m.group(1).strip())
    except Exception:
        return None
    if not isinstance(raw, list):
        return raw
    memo = {}
    def get(i):
        if not isinstance(i, int) or i < 0 or i >= len(raw):
            return i
        if i in memo:
            return memo[i]
        x = raw[i]
        if isinstance(x, list):
            if x and isinstance(x[0], str) and x[0] in JG_TAGS and len(x) == 2 and isinstance(x[1], int) and 0 <= x[1] < len(raw):
                memo[i] = get(x[1])
                return memo[i]
            out = []
            memo[i] = out
            for v in x:
                out.append(get(v))
            return out
        if isinstance(x, dict):
            out = {}
            memo[i] = out
            for k, v in x.items():
                out[k] = get(v)
            return out
        memo[i] = x
        return x
    try:
        return get(0)
    except Exception:
        return None
def jgPageData(url, key_prefix):
    html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
                                    "Referer": "https://91dj1.com/"})
    root = jgPayload(html)
    if not isinstance(root, dict):
        return None
    data = root.get("data")
    if not isinstance(data, dict):
        return None
    for k, v in data.items():
        if k.startswith(key_prefix) and isinstance(v, dict):
            inner = v.get("data")
            if isinstance(inner, dict):
                return inner
    return None
def jgSafe(s):
    if not s:
        return ""
    t = str(s)
    try:
        t = t.encode("utf-8", errors="replace").decode("utf-8")
    except Exception:
        pass
    return "".join(ch for ch in t if ord(ch) >= 32 or ch in "\t\n\r")
def jgVod(item):
    vid = str(item.get("video_id") or item.get("id") or "")
    name = jgSafe(item.get("title") or item.get("video_title") or "").strip()
    pic = imgProxy(str(item.get("cover") or item.get("cover_img") or ""))
    rem = " ".join(x for x in (item.get("play_count_text") or "", item.get("serialize_status_text") or "") if x).strip()
    return {"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": rem}
def jgEncodePlayId(video_id, episode_id, sort):
    payload = json.dumps({"video_id": str(video_id or ""), "episode_id": str(episode_id or ""), "sort": int(sort or 1)},
                         ensure_ascii=False, separators=(",", ":"))
    token = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    return "ep_" + token
def jgDecodePlayId(value):
    text = str(value or "").strip()
    if text.startswith("ep_"):
        try:
            token = text[3:]
            token += "=" * (-len(token) % 4)
            data = json.loads(base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8"))
            return {"video_id": str(data.get("video_id") or ""), "episode_id": str(data.get("episode_id") or ""),
                    "sort": int(data.get("sort") or 1)}
        except Exception:
            pass
    m = re.match(r"^(\d+):(\d+)$", text)
    if m:
        return {"video_id": m.group(1), "episode_id": "", "sort": int(m.group(2))}
    return {"video_id": text if text.isdigit() else "", "episode_id": "", "sort": 1}
def jgProbe(url):
    if not re.search(r"\.m3u8(?:$|[?#])", url, re.I):
        return bool(re.search(r"\.mp4(?:$|[?#])", url, re.I))
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, stream=True, verify=False)
        return "#EXTM3U" in r.raw.read(4096).decode("utf-8", errors="replace")
    except Exception:
        return False
def jgDetail(vid):
    m = re.search(r"(\d+)", str(vid or ""))
    if not m:
        return {}
    vid = m.group(1)
    data = jgPageData("https://91dj1.com/drama/detail/" + vid + "/", "drama-detail")
    if not data:
        return {}
    name = jgSafe(data.get("title") or "").strip() or ("短剧" + vid)
    pic = imgProxy(str(data.get("cover") or ""))
    desc = jgSafe(data.get("description") or "").strip()
    rem = " ".join(x for x in (data.get("play_count_text") or "", data.get("serialize_status_text") or "") if x).strip()
    eps = sorted(data.get("episodes") or [], key=lambda e: int(e.get("sort") or 0))
    parts = []
    for i, e in enumerate(eps):
        eid = e.get("id")
        if eid is None:
            continue
        sort = int(e.get("sort") or i + 1)
        title = jgSafe(e.get("title")) or ("第%s集" % sort)
        title = str(title).replace("#", " ").replace("$", " ").strip()
        parts.append("%s$%s" % (title, jgEncodePlayId(vid, eid, sort)))
    return {"vod_id": "九果@" + vid, "vod_name": name, "vod_pic": pic, "vod_content": desc, "vod_remarks": rem,
            "vod_play_from": "九果", "vod_play_url": "#".join(parts)}
def jgPlay(id):
    play = jgDecodePlayId(id)
    vid = play.get("video_id") or ""
    eid = play.get("episode_id") or ""
    sort = int(play.get("sort") or 1)
    if not vid or not re.fullmatch(r"\d+", vid):
        return {"parse": 1, "url": "", "header": json.dumps({})}
    media = ""
    media_h265 = ""
    if eid and re.fullmatch(r"\d+", eid):
        data = jgApi("/api/playlet/play", {"playlet_id": int(vid), "video_id": int(vid), "episode_id": int(eid)})
        if data:
            media = str(data.get("video_url") or "")
            media_h265 = str(data.get("video_url_h265") or "")
            if not media and not media_h265:
                for e in data.get("episodeAll") or []:
                    if str(e.get("id") or e.get("episode_id") or "") == eid:
                        media = str(e.get("video_url") or "")
                        media_h265 = str(e.get("video_url_h265") or "")
                        break
    if not media and not media_h265:
        data = jgApi("/api/playlet/play", {"playlet_id": int(vid), "video_id": int(vid), "episode_id": 0})
        if data:
            for e in data.get("episodeAll") or []:
                if int(e.get("sort") or 0) == sort:
                    media = str(e.get("video_url") or "")
                    media_h265 = str(e.get("video_url_h265") or "")
                    break
    candidates = []
    for value in (media, media_h265):
        value = str(value or "").strip()
        if value.startswith("//"):
            value = "https:" + value
        if value and value not in candidates:
            candidates.append(value)
    for value in candidates:
        if jgProbe(value):
            return {"parse": 0, "url": value, "header": json.dumps({})}
    return {"parse": 1, "url": "", "header": json.dumps({})}
class WGService:
    host = ""
    headers = {}
    image_map = {}
    image_id_map = {}
    @classmethod
    def init(cls):
        if cls.host:
            return
        cls.publish = "https://51dj20.com/"
        cls.ua = "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/143.0 Mobile Safari/537.36"
        cls.headers = {"User-Agent": cls.ua,
                       "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                       "Accept-Language": "zh-CN,zh;q=0.9", "Referer": cls.publish}
        try:
            import ssl as _ssl
            _ssl._create_default_https_context = _ssl._create_unverified_context
        except Exception:
            pass
        cls.host = "https://ceiling.sysrycady.com/"
        cls._resolve_domain()
        cls.image_map = {}
        cls.image_id_map = {}
        try:
            with open("/storage/emulated/0/影视/AI/51短剧/51短剧图片映射.json", "r", encoding="utf-8") as f:
                raw = f.read()
            for x in cls._walk(cls._payload(raw), ["video_id", "title"]):
                title = str(x.get("title") or "")
                cover = cls._pic(x.get("cover") or x.get("cover_img") or x.get("cover_image"))
                if title and cover:
                    cls.image_map[title] = cover
                    cls.image_id_map[str(x.get("video_id"))] = cover
            for title, cover in re.findall(r'\"title\"\s*:\s*\"([^\"]+)\"[\s\S]{0,300}?\"cover\"\s*:\s*\"([^\"]+)\"', raw):
                cls.image_map.setdefault(title, cls._pic(cover))
        except Exception:
            pass
    @classmethod
    def _resolve_domain(cls):
        try:
            h = fetch_text(cls.publish, headers=cls.headers)
            m = re.search(r'<a[^>]+href=["\'](https?://[^"\']+)', h, re.I)
            if not m:
                return
            h = fetch_text(m.group(1), headers=cls.headers)
            m = re.search(r'Base64\.decode\(["\']([^"\']+)["\']\)', h, re.I)
            if not m:
                return
            decoded = base64.b64decode(m.group(1)).decode("utf-8", "ignore")
            m = re.search(r"words\.random\(\)\s*\+\s*[\"']([^\"']+)[\"']", decoded, re.I)
            if not m:
                return
            suffix = m.group(1).strip()
            prefix = "".join(random.choice("abcdefghjkmnpqrstuvwxy23456789") for _ in range(5))
            cls.host = "https://" + prefix + suffix.lstrip("/")
            if not cls.host.endswith("/"):
                cls.host += "/"
            cls.headers["Referer"] = cls.host
        except Exception:
            pass
    @classmethod
    def _req(cls, url):
        try:
            r = fetch_text(url, headers=cls.headers)
            return r
        except Exception:
            return ""
    @classmethod
    def _payload(cls, html):
        m = re.search(r'<script[^>]+id=["\']__NUXT_DATA__["\'][^>]*>(.*?)</script>', html, re.S | re.I)
        if not m:
            return None
        try:
            raw = json.loads(m.group(1).strip())
            memo = {}
            def get(i):
                if not isinstance(i, int) or i < 0 or i >= len(raw):
                    return i
                if i in memo:
                    return memo[i]
                x = raw[i]
                if isinstance(x, list):
                    out = []
                    memo[i] = out
                    for v in x:
                        out.append(get(v))
                    return out
                if isinstance(x, dict):
                    out = {}
                    memo[i] = out
                    for k, v in x.items():
                        out[k] = get(v)
                    return out
                memo[i] = x
                return x
            return get(0)
        except Exception:
            return None
    @classmethod
    def _walk(cls, obj, keys):
        out, seen = [], set()
        def go(x):
            if isinstance(x, dict):
                if all(k in x for k in keys):
                    mark = str(x.get(keys[0])) + str(x.get(keys[1]))
                    if mark not in seen:
                        seen.add(mark)
                        out.append(x)
                for v in x.values():
                    go(v)
            elif isinstance(x, list):
                for v in x:
                    go(v)
        go(obj)
        return out
    @classmethod
    def _pic(cls, x):
        if not isinstance(x, str):
            return ""
        url = x.replace("\\u002F", "/").replace("\\/", "/").replace("&amp;", "&").strip()
        if not url:
            return ""
        if url.startswith("//"):
            url = "https:" + url
        elif not url.startswith("http"):
            url = cls._fix(url)
        try:
            return getProxyUrl() + "&url=" + urllib.parse.quote(cls.e64(url), safe="") + "&type=img"
        except Exception:
            return imgInline(url) or url
    @classmethod
    def _media(cls, x):
        if not isinstance(x, str):
            return ""
        url = x.replace("\\u002F", "/").replace("\\/", "/").replace("&amp;", "&").strip()
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        return cls._fix(url)
    @classmethod
    def _num(cls, n):
        try:
            n = int(float(str(n).replace(",", "")))
            return (str(round(n / 10000, 1)).rstrip(".0") + "W") if n >= 10000 else str(n)
        except Exception:
            return ""
    @classmethod
    def _vod(cls, x, actor=False):
        title = str(x.get("title") or x.get("name") or x.get("video_title") or x.get("drama_name") or "")
        vid = x.get("actor_id") if actor else (x.get("video_id") or x.get("playlet_id") or x.get("id") or x.get("actor_id"))
        if not title or vid is None:
            return None
        if actor and x.get("actor_id") is not None:
            aid = str(x.get("actor_id"))
            pic = cls._pic(x.get("avatar"))
            works = cls._num(x.get("works"))
            fans = cls._num(x.get("fans_count"))
            plays = cls._num(x.get("play_count"))
            remark = ("作品" + works if works else "演员作品") + ((" · 粉丝" + fans) if fans else "") + ((" · 播放" + plays) if plays else "")
            return {"vod_id": "actor_detail_" + aid, "vod_name": title, "vod_pic": pic, "vod_remarks": remark,
                    "vod_tag": "folder", "vod_play_from": "", "vod_play_url": ""}
        eid = x.get("episode_id") or ""
        play_id = "五果@" + cls.host + "drama-play?id=" + str(vid) + ("&episode_id=" + str(eid) if eid else "")
        pic = cls.image_id_map.get(str(vid)) or cls.image_map.get(title) or cls._pic(
            x.get("cover") or x.get("cover_img") or x.get("cover_image") or x.get("image") or x.get("poster") or x.get("thumb"))
        plays = str(x.get("play_count_text") or "") or cls._num(x.get("play_count"))
        chase = cls._num(x.get("chase_count"))
        status = str(x.get("serialize_status_text") or ("播放" if eid else ""))
        remark = (("播放" + plays) if plays else "") + ((" · 追剧" + chase) if chase else "")
        return {"vod_id": play_id, "vod_name": title, "vod_pic": pic, "vod_remarks": remark or status,
                "vod_tag": "video", "vod_play_id": str(eid)}
    @classmethod
    def _meta(cls, html):
        data = cls._payload(html)
        for x in cls._walk(data, ["total", "page", "limit"]):
            total = int(x.get("total") or 0)
            limit = int(x.get("limit") or 20)
            return total, limit, max(1, (total + limit - 1) // limit)
        for x in cls._walk(data, ["total", "page"]):
            total = int(x.get("total") or 0)
            return total, 30, max(1, (total + 29) // 30)
        return 0, 20, 1
    @classmethod
    def _page(cls, html, actor=False):
        data = cls._payload(html)
        keys = ["actor_id", "name"] if actor else ["video_id", "title"]
        if not actor:
            html_pics = re.findall(r'(?:data-original|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)', html, re.I)
        else:
            html_pics = []
        arr = cls._walk(data, keys) if data else []
        result = []
        seen = set()
        if actor:
            links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>[\s\S]{0,300}?</a>', html, re.I)
            actor_links = [u for u in links if ("/actor" in u or "actor_id" in u) and "explore-actor" not in u and "rank-actor" not in u]
        else:
            actor_links = []
        for i, x in enumerate(arr):
            if actor:
                v = cls._vod(x, True)
                if v and not v.get("vod_id"):
                    v["vod_id"] = cls._fix(actor_links[i]) if i < len(actor_links) else v.get("vod_id", "")
            else:
                v = cls._vod(x, False)
                if v and not v.get("vod_pic") and i < len(html_pics):
                    v["vod_pic"] = cls._pic(html_pics[i])
            if v and v["vod_id"] not in seen:
                seen.add(v["vod_id"])
                result.append(v)
        return result
    @classmethod
    def _fix(cls, url):
        url = str(url or "").replace("\\u002F", "/").replace("\\/", "/")
        if url.startswith("http"):
            return url
        return cls.host.rstrip("/") + "/" + url.lstrip("/")
    @classmethod
    def _url(cls, cid, pg, ext=None):
        pg = max(1, int(pg))
        e = ext if isinstance(ext, dict) else {}
        if cid == "actor":
            sort = str(e.get("sort") or "hot")
            if sort == "1":
                base = cls.host + "explore-actor/1/"
            elif sort == "2":
                base = cls.host + "explore-actor/2/"
            elif sort in ("new", "hot", "recommend"):
                base = cls.host + "rank-actor/" + sort + "/"
            else:
                base = cls.host + "rank-actor/"
            return base if pg == 1 else base + "page/" + str(pg) + "/"
        if cid == "drama":
            vals = [str(e.get(k, 0) or 0) for k in ("theme", "setting", "background", "audience", "time", "recommend")]
            base = cls.host + "explore-drama/" + "-".join(vals) + "/"
            return base if pg == 1 else base + "page/" + str(pg) + "/"
        if cid == "drama_week":
            base = cls.host + "rank-drama/week/"
            return base if pg == 1 else base + "page/" + str(pg) + "/"
        if cid == "drama_month":
            base = cls.host + "rank-drama/month/"
            return base if pg == 1 else base + "page/" + str(pg) + "/"
        if cid == "aisd":
            base = cls.host + "drama/AISD/"
            return base if pg == 1 else base + "page/" + str(pg) + "/"
        if cid.startswith("actor$"):
            return cls.host + "actor/" + cid.split("$", 1)[1] + "/"
        return cls.host
    @classmethod
    def e64(cls, text):
        try:
            return base64.b64encode(str(text).encode("utf-8")).decode("utf-8")
        except Exception:
            return ""
    @classmethod
    def d64(cls, text):
        try:
            return base64.b64decode(str(text).encode("utf-8")).decode("utf-8")
        except Exception:
            return ""
_AGG_XINGYA_HEADERS = None
def agg_ensure_xingya():
    global _AGG_XINGYA_HEADERS
    if _AGG_XINGYA_HEADERS:
        return
    if _AGG_XINGYA_HEADERS: return
    try:
        h = {'User-Agent': 'okhttp/4.10.0', 'Accept-Encoding': 'gzip', 'Content-Type': 'application/x-www-form-urlencoded', 'x-app-id': '7', 'platform': '1', 'manufacturer': 'realme', 'version_name': '3.3.1', 'user_agent': 'Mozilla/5.0 (Linux; Android 9; RMX1931 Build/PQ3A.190605.05081124; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.114 Mobile Safari/537.36', 'app_version': '3.3.1', 'device_platform': 'android', 'personalized_recommend_status': '1', 'device_type': 'RMX1931', 'device_brand': 'realme', 'os_version': '9', 'channel': 'default', 'raw_channel': 'default', 'oaid': '', 'msa_oaid': '', 'uuid': 'randomUUID_914e7a9b-deac-4f80-9247-db56669187df', 'device_id': '24250683a3bdb3f118dff25ba4b1cba1a', 'ab_id': '', 'support_h265': '1'}
        b = 'device=24250683a3bdb3f118dff25ba4b1cba1a&install_first_open=false&first_install_time=1723214205125&last_update_time=1723214205125&report_link_url='
        r = fetch_json(CFG['platform']['芽果']['loginUrl'], method='POST', headers=h, data=b)
        token = r.get("data", {}).get("token")
        if token:
            _AGG_XINGYA_HEADERS = {**CFG["headers"]["default"], "authorization": token, 'dev_token': 'Bnf9uRPIcKTIOZasAUgUJAUDXhIOlB4lpDKsyLD4yvKm708G4J8PN1Z-gMaFgPwkRvqJrEje81VRxh41IaSj0lNWuoRLUg1r08Z1f0IqSv2q1lvfxrYckKavmnAPYLdkT9P1fPFNRt0RuN3DLLFZqApRDdPD3mM2jB6d79CF2LtM*', 'User-Agent': 'okhttp/4.10.0', 'user_agent': 'Mozilla/5.0 (Linux; Android 9; RMX1931 Build/PQ3A.190605.05081124; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.114 Mobile Safari/537.36', 'app_version': '3.0.0.1', 'version_name': '3.0.0.1', 'support_h265': '1'}
    except Exception: pass
def agg_category_content(tid, pg, extend=None):
    extend = extend or {}
    area = extend.get("area") or CFG["filter_def"].get(tid, {}).get("area", "")
    plat = CFG["platform"].get(tid)
    d = []
    try:
        if tid == '香果':
            cat = extend.get("cat") or "recommend"
            for v in xjVideos(cat, pg):
                d.append(v)
        elif tid == '橙果':
            h = cgGet(CG_HOST + "/browse?line=&status=&sort=hot&page=" + str(pg))
            for v in cgParseList(h):
                d.append(v)
        elif tid == '九果':
            data = jgPageData("https://91dj1.com/explore/drama/", "explore-drama")
            items = []
            if isinstance(data, dict):
                items = data.get("list") or data.get("dramas") or []
                if not items:
                    for k, v in data.items():
                        if isinstance(v, list) and v and isinstance(v[0], dict) and ("video_id" in v[0] or "title" in v[0]):
                            items = v
                            break
            for it in items:
                if isinstance(it, dict):
                    v = jgVod(it)
                    if v.get("vod_id") and v.get("vod_name"):
                        v["vod_id"] = "九果@" + str(v["vod_id"])
                        v["vod_remarks"] = ("九果 | " + str(v["vod_remarks"])) if v.get("vod_remarks") else "九果"
                        d.append(v)
        elif tid == '五果':
            WGService.init()
            cid = extend.get("cid") or "drama"
            url = WGService._url(cid, pg, extend)
            for v in WGService._page(WGService._req(url)):
                d.append(v)
        if tid == '河果':
            cid, cname = area.split('@') if '@' in area else ("53", "精选")
            body = {"recSwitch": True, "storePageId": 10002, "channelGroupId": "10", "channelId": int(cid), "channelName": cname, "lastColumnStyle": 3, "fromColumnId": "1", "pageFlag": str(pg), "theaterSubscriptSwitch": True}
            res = HMService.api("1125", body)
            if res and res.get("columnData") and res["columnData"][0]:
                for vod in res["columnData"][0].get("videoData", []):
                    d.append({"vod_name": vod["bookName"], "vod_pic": vod["coverWap"], "vod_remarks": f"河果 | 更新{vod['updateNum']}集", "vod_id": f"河果@{vod['bookId']}"})
        elif tid == '百果':
            t = int(time.time())
            version = md5_sign(f"{t}v2")
            body = {"data": {"refreshIndex": int(pg), "timestamp": t, "version": version, "themes": [{"kind": "综合", "names": [extend.get("class", "新剧")]}, {"kind": "题材", "names": ["" if area == '全部' else area]}], "extRequest": {"flow_tabid": "13"}, "from": "feed", "page": "channel_video_landing", "pd": "feed", "theme": ""}}
            res = fetch_json("https://mbd.baidu.com/feedapi/v1/videoserver/playlets/list?service=bdbox", method='POST', headers=CFG["headers"]["baidu_app"], data="data="+urllib.parse.quote(json.dumps(body)))
            for it in res.get("data", {}).get("items", []):
                d.append({"vod_name": it["title"], "vod_pic": it["img"], "vod_remarks": f"百果 | {it.get('updateStatus', '全集')}", "vod_id": f"百果@{it['collId']}"})
        elif tid == '牛果':
            NNService.ensureAuth()
            if not NNService.token: raise Exception("牛果获取Token失败")
            res = NNService.api(f"{plat['host']}/api/v1/app/screen/screenMovie", {"condition": {"classify": "" if area == '全部' else area, "typeId": "S1"}, "pageNum": int(pg), "pageSize": 40})
            for item in res.get("data", {}).get("records", []):
                d.append({"vod_name": item["name"], "vod_id": f"{tid}@{item['id']}", "vod_remarks": f"牛果 | 共{item['totalEpisode']}集", "vod_pic": item["cover"]})
        elif tid == '山果':
            SHService.ensureAuth()
            url = f"{plat['host']}/shanhai-theater/v2/theater_parent/cloud/v2/theater/home_page?theater_class_id=1&type=1&class2_ids={area}&page_num={pg}&page_size=24"
            res = SHService.request(url)
            for item in res.get("items", []):
                t = item.get("theater", {})
                d.append({"vod_name": t.get("title"), "vod_remarks": f"山果 | 共{t.get('total')}集", "vod_pic": t.get("cover_url"), "vod_id": f"山果@{t.get('id')}"})
        elif tid == '好果':
            bodyStr = f"tag_id={area}&pn={pg}&rn=12"
            h = {"User-Agent": CFG["headers"]["browser"]["User-Agent"], "Content-Type": "application/x-www-form-urlencoded"}
            res = fetch_json(f"{plat['host']}/haokan/ui-feed/playletTagsFeed?log=vhk&tn=1020970b&ctn=1008350n&blur=1", method='POST', headers=h, data=bodyStr)
            for item in res.get("data", {}).get("list", []):
                d.append({"vod_name": item["playlet_title"], "vod_remarks": f"好果 | 更新{item['episodes_num']}集", "vod_pic": item["playlet_poster"], "vod_id": f"好果@{item['playlet_id']}@{item['progress_vid']}"})
        elif tid == '芽果':
            agg_ensure_xingya()
            h = _AGG_XINGYA_HEADERS or CFG["headers"]["default"]
            url = f"{plat['host']}{plat['url1'].replace('theater_class_id', 'theater_class_id='+area)}&type=1&class2_ids=0&page_num={pg}&page_size=24"
            r = fetch_json(url, headers=h)
            for it in r.get("data", {}).get("list", []):
                t = it.get("theater", {})
                d.append({"vod_name": t.get("title"), "vod_pic": t.get("cover_url"), "vod_remarks": f"芽果 | {t.get('total')}集", "vod_id": f"芽果@{plat['host']}{plat['url2']}?theater_parent_id={t.get('id')}"})
        elif tid == '饭果':
            parts = area.split('@') if area else ['68', '都市']
            url = f"{plat['host']}{plat['url1']}?reqType=aggregationPage&offset={(int(pg)-1)*30}&categoryId={parts[0]}&categoryNames={urllib.parse.quote(parts[1])}&pageID=page_theater&appId=drama"
            r = fetch_json(url)
            for soup in r.get("result", {}).get("elements", []):
                for vod in soup.get("contents", []):
                    dj = vod.get("duanjuVo", {})
                    d.append({"vod_name": dj.get("title"), "vod_pic": dj.get("coverImageUrl"), "vod_remarks": f"饭果 | {dj.get('total')}集", "vod_id": f"饭果@{dj.get('duanjuId')}#{dj.get('source')}"})
        elif tid == '猫果':
            sign = md5_sign(f"operation=1playlet_privacy=1tag_id={area}{CFG['keys']}")
            url = f"{plat['host']}{plat['url1']}?tag_id={area}&playlet_privacy=1&operation=1&sign={sign}"
            hx = getHeaderX()
            h = {**hx, **CFG["headers"]["qimao"]}
            res = fetch_json(url, headers=h)
            for item in res.get("data", {}).get("list", []):
                d.append({"vod_name": item["title"], "vod_pic": item["image_link"], "vod_remarks": f"猫果 | {item['total_episode_num']}集", "vod_id": f"猫果@{urllib.parse.quote(item['playlet_id'])}"})
        elif tid == '星果':
            url = f"{plat['host']}{plat['list']}"
            params = {"productId": "2a8c14d1-72e7-498b-af23-381028eb47c0", "vestId": "2be070e0-c824-4d0e-a67a-8f688890cadb", "channel": "oppo19", "osType": "android", "version": "20", "token": "202509271001001446030204698626", "resourceId": area, "pageNum": str(pg), "pageSize": "20"}
            r = fetch_json(f"{url}?{build_query(params)}", headers=CFG["headers"]["xingxing"])
            for vod in r.get("data", {}).get("datalist", []):
                d.append({"vod_name": vod.get("name", ""), "vod_pic": vod.get("icon", ""), "vod_remarks": f"星果 | {vod.get('heat', 0)}万播放", "vod_id": f"星果@{vod['id']}@{urllib.parse.quote(vod.get('name',''))}@{urllib.parse.quote(vod.get('introduction',''))}"})
        elif tid == '观果':
            r = fetch_json(f"{plat['host']}{plat['search']}", method='POST', headers={'content-type': 'application/json; charset=utf-8'}, data={"audience": "全部受众", "page": int(pg), "pageSize": 30, "searchWord": "", "subject": "全部主题"})
            for it in r.get("data", []):
                d.append({"vod_name": it["title"], "vod_pic": it["vertPoster"], "vod_remarks": f"观果 | {it['episodeCount']}集", "vod_id": f"观果@{it['oneId']}"})
        elif tid == '薏果':
            path = "/bookstore/local/visual/channel/list"
            bp = f"key={area}&p1=1750574688516674369&p16=22081212C&p2=341201&p21=10&p22=15&p24=0&p25=21200&p28=cca83346da195d11&p29=zy9351ae&p3=102120009&p31=29d1af74b128f29f&p33=com.zhangyue.app.shortplay&p34=force_fsg_nav_bar&p35=BUZGFVakskazFWG2XwZ/LNs4fOnQczc4iivy1qLFvZqmerp2Abe2hv5Tu1jOHQJO5PGANizg3JbzgaTOon0qkmQ==&p4=501609&p5=16&p7=cca83346da195d11&p9=3&page={pg}&pc=10&usr=tj1290623468&zyeid=4fc4c6737a87b603e1b8ce9210032bae"
            h = yimiGetHeaders(path, bp, "AAF4IWZnITkqeX4hJCB5eio4IWc4IH4=")
            r = fetch_json(f"{plat['host']}{path}?{bp}", headers=h)
            for item in r.get("body", {}).get("list", [{}])[0].get("short_plays", []):
                d.append({"vod_name": item["short_play_name"], "vod_pic": item["cover_url"], "vod_remarks": f"薏果 | 热度值:{item.get('favor_count_format', 0)}", "vod_id": f"薏果@{item['id']}"})
    except Exception as e: 
        return {"list": [{"vod_id": "err", "vod_name": f"加载异常: {e}", "vod_pic": ""}]}
    return {"list": d, "page": pg, "pagecount": 99, "limit": 30, "total": 999}
def agg_detail_content(vod_id):
    ids = [vod_id]
    orId = ids[0]
    parts = orId.split('@')
    platform = parts[0]
    id = "@".join(parts[1:])
    plat = CFG["platform"].get(platform)
    vod = {}
    try:
        if platform == '香果':
            vod = xjDetail(id)
        elif platform == '橙果':
            vod = cgDetail(id)
        elif platform == '九果':
            vod = jgDetail(id)
        elif platform == '五果':
            WGService.init()
            vod = {}
            vid = ""
            eid = ""
            m = re.search(r"[?&]id=([^&]+)", id)
            if m: vid = m.group(1)
            m = re.search(r"[?&]episode_id=([^&]+)", id)
            if m: eid = m.group(1)
            if vid:
                arr = []
                h = WGService._req(WGService.host + "drama-play?id=" + vid)
                data = WGService._payload(h) if h else None
                if data:
                    arr = WGService._walk(data, ["video_id", "title"]) or WGService._walk(data, ["video_title", "cover_img"])
                if arr:
                    x = arr[0]
                    title = str(x.get("title") or x.get("video_title") or x.get("drama_name") or "短剧")
                    cover = WGService.image_id_map.get(str(vid)) or WGService._pic(x.get("cover") or x.get("cover_img") or x.get("poster") or x.get("thumb") or "")
                    desc = str(x.get("description") or x.get("video_desc") or x.get("content") or "")
                    eps = []
                    seen_ep = set()
                    for xx in WGService._walk(data, ["episode_title", "video_url"]):
                        n = xx.get("episode_title") or xx.get("sort") or xx.get("episode_id")
                        u = WGService._media(xx.get("video_url") or xx.get("url") or "")
                        if n and u and str(n) not in seen_ep:
                            seen_ep.add(str(n))
                            if re.search(r"集$", str(n)):
                                eps.append("%s$%s" % (n, u))
                            else:
                                eps.append("第%s集$%s" % (n, u))
                    if not eps:
                        for ep in (x.get("episodes") or x.get("episodeAll") or []):
                            n = ep.get("episode_title") or ep.get("sort") or ep.get("episode_id")
                            u = WGService._media(ep.get("video_url") or ep.get("url") or "")
                            if n and u and str(n) not in seen_ep:
                                seen_ep.add(str(n))
                                if re.search(r"集$", str(n)):
                                    eps.append("%s$%s" % (n, u))
                                else:
                                    eps.append("第%s集$%s" % (n, u))
                    vod = {"vod_id": "五果@" + vid, "vod_name": title, "vod_pic": cover, "vod_content": desc,
                           "vod_play_from": "五果", "vod_play_url": "#".join(eps) or "暂无播放地址$0"}
        if platform == '河果':
            res = HMService.api("1131", {"bookId": id})
            if res.get("videoInfo"):
                v = res["videoInfo"]
                listRes = HMService.api("1132", {"bookId": id, "chapterMin": 1, "chapterMax": 10000})
                eps = [f"{c['chapterName']}${c['chapterId']}++{c['chapterIndex']}++{id}" for c in listRes.get("chapterList", [])]
                vod = {"vod_name": v["bookName"], "vod_pic": v["coverWap"], "vod_id": orId, "vod_remarks": v["finishStatusCn"], "vod_content": v.get("introduction", ""), "vod_play_from": "河果", "vod_play_url": "#".join(eps)}
        elif platform == '百果':
            res = fetch_json("https://sv.baidu.com/haokan/ui-video/playlet/rec/detail?log=vhk&tn=1020970b&ctn=1008350n&blur=1", method='POST', headers=CFG["headers"]["browser"], data=f"playlet_id={id}&vid=undefined").get("data", {})
            eps = [f"第{i+1}集${v}" for i, v in enumerate(res.get("vid_list", []))]
            vod = {"vod_name": res.get("playlet_title"), "vod_pic": res.get("playlet_poster"), "vod_remarks": f"热度:{res.get('hot_value')}", "vod_content": res.get("description"), "vod_play_from": "百果", "vod_play_url": "#".join(eps)}
        elif platform == '牛果':
            NNService.ensureAuth()
            descRes = NNService.api(f"{plat['host']}/api/v1/app/play/movieDesc", {"id": id, "typeId": "S1"}).get("data", {})
            listRes = NNService.api(f"{plat['host']}/api/v1/app/play/movieDetails", {"id": id, "source": 0, "typeId": "S1", "userId": "546932"}).get("data", {})
            eps = [f"{i['episode']}${i['id']}+{id}+free" for i in listRes.get("episodeList", [])]
            if not eps and listRes.get("thirdPlayId"):
                d1 = f"not_include=0&lock_free=1&type=1&clientVersion=v5.2.5&uuid=6IDYUSASPQY5BBVACWQW3LLTPV4V7DE26UOCX5TZTVUGX4VUJNXQ01&resolution=1080*2320&openudid=82f4175d577a2939&dt=22021211RC&os_api=31&install_id=1496879012031075&sdk_version=1.1.3.0&siteid=5627189&dev_log_aid=667431&oaid=&timestamp={int(time.time())}&direction=0&ac=mobile&os=Android&vod_version=1.10.21.6-tob&os_version=12&count=1&index=1&shortplay_id={listRes['thirdPlayId']}&sha1=46121F77CE2FCAD3DBC3B9EC8A24908C1A8AD6D9&device_brand=Redmi&package_name=com.niuniu.ztdh.app"
                h1 = NNService.post1(f"{plat['url1']}/csj_sp/api/v1/shortplay/detail?siteid=5627189", d1)
                if h1 and h1.get("data", {}).get("episode_right_list"):
                    eps = [f"第{it['index']}集${it['index']}+{it['lock_type']}+{listRes['thirdPlayId']}" for it in h1["data"]["episode_right_list"]]
            vod = {"vod_name": descRes.get("name"), "vod_pic": descRes.get("cover"), "vod_remarks": f"评分:{descRes.get('score')}", "vod_content": descRes.get("introduce"), "vod_play_from": "牛果", "vod_play_url": "#".join(eps)}
        elif platform == '山果':
            res = SHService.request(f"{plat['host']}/shanhai-theater/v2/theater_parent/detail?theater_parent_id={id}")
            eps = [f"{i['son_title']}${i['son_video_url']}" for i in res.get("theaters", [])]
            vod = {"vod_name": res.get("title"), "vod_pic": res.get("cover_url"), "vod_remarks": " ".join(res.get("desc_tags", [])), "vod_content": res.get("introduction"), "vod_play_from": "山果", "vod_play_url": "#".join(eps)}
        elif platform == '好果':
            pid, vid = id.split('@')
            res = fetch_json(f"{plat['host']}/haokan/ui-video/playlet/rec/detail?log=vhk&tn=1020970b&ctn=1008350n&blur=1", method='POST', headers={"Content-Type": "application/x-www-form-urlencoded"}, data=f"playlet_id={pid}&vid={vid}").get("data", {})
            eps = [f"第{i+1}集${v}" for i, v in enumerate(res.get("vid_list", []))]
            vod = {"vod_name": res.get("playlet_title"), "vod_pic": res.get("playlet_poster"), "vod_remarks": f"更新:{res.get('episodes_num')}", "vod_content": res.get("description"), "vod_play_from": "好果", "vod_play_url": "#".join(eps)}
        elif platform == '芽果':
            agg_ensure_xingya()
            h = _AGG_XINGYA_HEADERS or CFG["headers"]["default"]
            d = fetch_json(id, headers=h).get("data", {})
            if d: vod = {"vod_name": d.get("title"), "vod_pic": d.get("cover_url"), "vod_content": d.get("introduction"), "vod_play_from": "芽果", "vod_play_url": "#".join([f"第{i['num']}集${i['son_video_url']}" for i in d.get("theaters", [])])}
        elif platform == '饭果':
            did, src = id.split('#')
            r = fetch_json(f"{plat['host']}{plat['url2']}?duanjuId={did}&source={src}&appId=drama").get("result", {})
            vod = {"vod_name": r.get("title"), "vod_pic": r.get("coverImageUrl"), "vod_content": r.get("desc"), "vod_play_from": "饭果", "vod_play_url": "#".join([f"{i['index']}${i['playUrl']}" for i in r.get("episodeList", [])])}
        elif platform == '猫果':
            d_id = urllib.parse.unquote(id)
            sign = md5_sign(f"playlet_id={d_id}{CFG['keys']}")
            hx = getHeaderX()
            h = {**hx, **CFG["headers"]["qimao"], "Content-Type": ""}
            r = fetch_json(f"{plat['url2']}?playlet_id={d_id}&sign={sign}", headers=h).get("data", {})
            vod = {"vod_name": r.get("title"), "vod_pic": r.get("image_link"), "vod_content": r.get("intro"), "vod_play_from": "猫果", "vod_play_url": "#".join([f"{i['sort']}${i['video_url']}" for i in r.get("play_list", [])])}
        elif platform == '观果':
            r = fetch_json(f"{plat['host']}{plat['url2']}&oneId={id}&page=1&pageSize=1000", headers=CFG["headers"]["default"])
            data = r.get("data", [])
            eps = []
            for idx, ep in enumerate(data):
                ps = ep.get("playSetting") or ep.get("videoClarityList") or []
                if isinstance(ps, str):
                    try: ps = json.loads(ps)
                    except Exception: ps = {}
                u = ''
                if isinstance(ps, dict): u = ps.get('super') or ps.get('high') or ps.get('normal') or ps.get('url') or ps.get('playUrl') or ''
                elif isinstance(ps, list) and ps:
                    best = next((x for x in ps if x.get('clarity') in ('1080P', '1080p', 'super', '超清')), ps[0])
                    u = best.get('url') or best.get('playUrl') or ''
                title = f"第{ep.get('playOrder') or ep.get('episode') or idx+1}集"
                eps.append(f"{title}${u or ep.get('playUrl', '')}")
            fst = data[0] if data else {}
            vod = {"vod_name": fst.get("title", ""), "vod_pic": fst.get("vertPoster") or fst.get("horizonPoster", ""), "vod_remarks": f"共{len(data)}集", "vod_content": f"播放量:{fst.get('viewCount',0)} 收藏:{fst.get('collectionCount',0)}", "vod_play_from": "观果", "vod_play_url": "#".join(eps)}
        elif platform == '星果':
            bid, name, desc = id.split('@')
            name, desc = urllib.parse.unquote(name), urllib.parse.unquote(desc)
            params = {"bookId": bid, "productId": "2a8c14d1-72e7-498b-af23-381028eb47c0", "vestId": "2be070e0-c824-4d0e-a67a-8f688890cadb", "channel": "oppo19", "osType": "android", "version": "20", "token": "202509271001001446030204698626"}
            r = fetch_json(f"{plat['host']}{plat['detail']}?{build_query(params)}", headers=CFG["headers"]["xingxing"])
            eps = []
            for i, v in enumerate(r.get("data", [])):
                try: u = v["shortPlayList"][0]["chapterShortPlayVoList"][0]["shortPlayUrl"]
                except Exception: u = ''
                if u: eps.append(f"第{i+1}集${u}")
            vod = {"vod_id": orId, "vod_name": name, "vod_content": desc, "vod_play_from": "星果", "vod_play_url": "#".join(eps) or "暂无播放地址$0"}
        elif platform == '薏果':
            path = "/video/client/short_play/episode_list"
            start_id = 1
            total = 999999
            eps = []
            body = {}
            while start_id <= total and start_id < 200: 
                end_id = start_id + 29
                bp = f"end_id={end_id}&p1=1750574688516674369&p16=22081212C&p2=341201&p21=10&p22=15&p24=0&p25=21200&p28=cca83346da195d11&p29=zy9351ae&p3=102120009&p31=29d1af74b128f29f&p33=com.zhangyue.app.shortplay&p34=force_fsg_nav_bar&p35=BUZGFVakskazFWG2XwZ/LNs4fOnQczc4iivy1qLFvZqmerp2Abe2hv5Tu1jOHQJO5PGANizg3JbzgaTOon0qkmQ==&p4=501609&p5=16&p7=cca83346da195d11&p9=3&pc=10&play_id={id}&start_id={start_id}&usr=tj1290623468&zyeid=4fc4c6737a87b603e1b8ce9210032bae"
                h = yimiGetHeaders(path, bp, "AAFzKmZkKjIqenUqJCNycSo7Kmw4I3U=")
                r = fetch_json(f"{plat['host']}{path}?{bp}", headers=h)
                body = r.get("body", {})
                l = body.get("episode_list", [])
                if not l: break
                if start_id == 1: total = body.get("target_count", total)
                for ep in l:
                    u = ep.get("play_url", "")
                    if "zhangyuecdn" in u: u = "https://mother-t.d.ireader.com" + u.split("com")[1]
                    eps.append(f"第{ep.get('order')}集${u}")
                start_id += 30
            vod = {"vod_name": body.get("name", "未知剧名"), "vod_content": body.get("introduce", ""), "vod_play_from": "薏果", "vod_play_url": "#".join(eps)}
    except Exception as e:
        return {"list": [{"vod_id": "err", "vod_name": f"详情加载失败:{e}", "vod_play_from": "错误"}]}
    try:
        fav_vid = vod.get("vod_id") or orId
        main_url = vod.get("vod_play_url") or ""
        if main_url:
            if favorite_is_fav(fav_vid):
                fav_label = "取消追剧"
                follow_addr = "__unfollow__" + str(fav_vid).replace(":", "~")
            else:
                fav_label = "点击追剧"
                follow_addr = "__follow__" + str(fav_vid).replace(":", "~")
            vod["vod_play_url"] = main_url + "$$$" + fav_label + "$" + follow_addr
            vod["vod_play_from"] = "%s$$$追剧" % (vod.get("vod_play_from") or platform)
    except Exception:
        pass
    return {"list": [vod]}
def agg_search_content(key, pg="1"):
    def _fetch_search(p):
        plat = CFG["platform"].get(p["id"])
        try:
            if p["id"] == '香果':
                return xjSearch(key)
            if p["id"] == '橙果':
                h = cgGet(CG_HOST + "/search?q=" + urllib.parse.quote(key))
                return cgParseList(h)
            if p["id"] == '九果':
                data = jgApi("/api/search/result", {"keyword": key, "tab": "video", "page": 1, "limit": 30})
                items = []
                if isinstance(data, dict):
                    for k in ("playlet", "videos", "list"):
                        v = data.get(k)
                        if isinstance(v, list):
                            items = v
                            break
                    if not items:
                        for k, v in data.items():
                            if isinstance(v, list) and v and isinstance(v[0], dict) and ("video_id" in v[0] or "title" in v[0]):
                                items = v
                                break
                out = []
                for it in items:
                    if isinstance(it, dict):
                        v = jgVod(it)
                        if v.get("vod_id") and v.get("vod_name"):
                            v["vod_id"] = "九果@" + str(v["vod_id"])
                            v["vod_remarks"] = ("九果 | " + str(v["vod_remarks"])) if v.get("vod_remarks") else "九果"
                            out.append(v)
                return out
            if p["id"] == '五果':
                WGService.init()
                out = []
                for u in (WGService.host + "search/" + urllib.parse.quote(key) + "/", WGService.host + "search?q=" + urllib.parse.quote(key)):
                    html = WGService._req(u)
                    if html:
                        vs = WGService._page(html)
                        if vs:
                            out = vs
                            break
                return out
            if p["id"] == '猫果':
                tid = 'ec1280db127955061754851657967'
                ewd = urllib.parse.quote(key)
                sign = md5_sign(f"extend=page={pg}read_preference=0track_id={tid}wd={ewd}{CFG['keys']}")
                url = f"{plat['host']}{plat['search']}?extend=&page={pg}&wd={ewd}&read_preference=0&track_id={tid}&sign={sign}"
                hx = getHeaderX()
                h = {**hx, **CFG["headers"]["qimao"]}
                h.pop("Content-Type", None); h.pop("content-type", None)
                h.pop("User-Agent", None); h.pop("user-agent", None)
                r = fetch_json(url, headers=h)
                return [{"vod_name": re.sub(r'<[^>]+>', '', i.get("title", "")).strip(), "vod_pic": i.get("image_link"), "vod_remarks": f"猫果 | {str(i.get('total_num','0')).replace('集','')}集", "vod_id": f"猫果@{urllib.parse.quote(str(i.get('id')))}"} for i in r.get("data", {}).get("list", [])]
            if p["id"] == '牛果':
                NNService.ensureAuth()
                if not NNService.token: return []
                r = NNService.api(f"{plat['host']}/api/v1/app/search/searchMovie", {"condition": {"typeId": "S1", "value": key}, "pageNum": int(pg), "pageSize": 40})
                return [{"vod_name": i["name"], "vod_id": f"{p['id']}@{i['id']}", "vod_remarks": f"{p['name']} | {i.get('type','')}", "vod_pic": i.get("cover")} for i in r.get("data", {}).get("records", [])]
            if p["id"] == '河果':
                r = HMService.api("1803", {"keyword": key, "page": int(pg), "size": 15, "searchSource": "搜索按钮", "hotWordType": 2, "tagIds": "", "reservationSwitch": True})
                return [{"vod_name": vod["bookName"], "vod_pic": vod["coverWap"], "vod_remarks": f"河果 | 更新{vod['updateNum']}集", "vod_id": f"河果@{vod['bookId']}"} for vod in r.get("searchVos", [])]
            if p["id"] == '百果':
                t = int(time.time())
                ver = md5_sign(f"{t}v2")
                body = {"data": {"query": key, "page": int(pg), "attribute": ["title"], "fe_page_type": "search", "extra": {"tab_id": "216", "flow_tabid": "13", "shortplay_source": "feed", "from": "feed", "tab_type": "搜索", "sub_template": "playlet_search_result"}}}
                r = fetch_json("https://mbd.baidu.com/feedapi/v1/videoserver/playlets/search?service=bdbox", method='POST', headers=CFG["headers"]["baidu_app"], data="data="+urllib.parse.quote(json.dumps(body)))
                return [{"vod_name": it["title"], "vod_pic": it["img"], "vod_id": f"百果@{it['nid'].split('_')[1]}", "vod_remarks": f"百果 | {it.get('collNum', '')}集"} for it in r.get("data", {}).get("itemList", [])]
            if p["id"] == '山果':
                SHService.ensureAuth()
                r = fetch_json(f"{plat['host']}/v3/search", method='POST', headers={"authorization": SHService.token, "Content-Type": "application/json"}, data={"text": key})
                return [{"vod_name": i["title"], "vod_id": f"山果@{i['id']}", "vod_remarks": f"山果 | {i['total']}集", "vod_pic": i["cover_url"]} for i in r.get("data", {}).get("theater", {}).get("search_data", [])]
            if p["id"] == '好果':
                bstr = f"method=get&pn=1&rn=10&v=2&word={urllib.parse.quote(key)}"
                h = {"User-Agent": CFG["headers"]["browser"]["User-Agent"], "Content-Type": "application/x-www-form-urlencoded"}
                r = fetch_json(f"{plat['host']}/haokan/api?cmd=search/sug&log=vhk&tn=1020970b&ctn=1008350n&blur=1&word={urllib.parse.quote(key)}", method='POST', headers=h, data=bstr)
                return [{"vod_name": i["title"], "vod_pic": i["cover_url"], "vod_remarks": f"好果 | 热度:{i['hot_value']}", "vod_id": f"好果@{i['id']}@"} for i in r.get("search/sug", {}).get("data", {}).get("list", []) if i.get("tplName") == "sug_playlet"]
            if p["id"] == '芽果':
                agg_ensure_xingya()
                h = _AGG_XINGYA_HEADERS or CFG["headers"]["default"]
                r = fetch_json(plat['host']+plat['search'], method='POST', headers={**h, "Content-Type": "application/json"}, data={"text": key})
                return [{"vod_name": it["title"], "vod_remarks": f"芽果 | {it.get('total', 0)}集", "vod_pic": it["cover_url"], "vod_id": f"芽果@{plat['host']}{plat['url2']}?theater_parent_id={it['id']}"} for it in r.get("data", {}).get("theater", {}).get("search_data", [])]
            if p["id"] == '饭果':
                url = f"{plat['host']}{plat['search']}?reqType=search&offset={(int(pg)-1)*30}&keyword={urllib.parse.quote(key)}&requestId={int(time.time())}aa498144140ef297&appId=drama"
                r = fetch_json(url)
                return [{"vod_name": vod["duanjuVo"]["title"], "vod_pic": vod["duanjuVo"]["coverImageUrl"], "vod_remarks": f"饭果 | {vod['duanjuVo']['total']}集", "vod_id": f"饭果@{vod['duanjuVo']['duanjuId']}#{vod['duanjuVo']['source']}"} for vod in r.get("result", {}).get("elements", [])]
            if p["id"] == '观果':
                r = fetch_json(f"{plat['host']}{plat['search']}", method='POST', headers={'content-type': 'application/json; charset=utf-8'}, data={"audience": "全部受众", "page": int(pg), "pageSize": 30, "searchWord": key, "subject": "全部主题"})
                return [{"vod_name": it["title"], "vod_pic": it["vertPoster"], "vod_remarks": f"观果 | {it['episodeCount']}集", "vod_id": f"观果@{it['oneId']}"} for it in r.get("data", [])]
            if p["id"] == '薏果':
                path = "/bookstore/search/recommend_data"
                params = f"keyword={urllib.parse.quote(key)}&p1=1750574688516674369&p16=22081212C&p2=341201&p21=3&p22=15&p24=0&p25=21200&p28=cca83346da195d11&p29=zy9351ae&p3=102120009&p31=29d1af74b128f29f&p33=com.zhangyue.app.shortplay&p34=force_fsg_nav_bar&p35=BUZGFVakskazFWG2XwZ/LNs4fOnQczc4iivy1qLFvZqmerp2Abe2hv5Tu1jOHQJO5PGANizg3JbzgaTOon0qkmQ==&p4=501609&p5=16&p7=cca83346da195d11&p9=3&page={pg}&pc=10&resource_type=short_play&size=10&sort=1&source_type=0,1&type=0&usr=tj1290623468&zyeid=4fc4c6737a87b603e1b8ce9210032bae"
                h = yimiGetHeaders(path, params, "AAF4IWZnITkqeX4hJCB5eio4IWc4IH4=")
                r = fetch_json(f"{plat['host']}{path}?{params}", headers=h)
                res = [{"vod_name": d["name"], "vod_pic": d["pic"], "vod_remarks": f"薏果 | 播放量:{d.get('popularity',0)}", "vod_id": f"薏果@{d['id']}"} for d in r.get("body", {}).get("short_play", {}).get("list", [])]
                return [i for i in res if key in i["vod_name"]]
        except Exception: return []
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_fetch_search, p) for p in CFG["platformList"]]
        for f in concurrent.futures.as_completed(futures):
            part = f.result()
            if part:
                results.extend(part)
    return {"list": results, "page": pg, "pagecount": 99, "limit": 30, "total": 999}
def agg_player_content(flag, id):
    try:
        if '香果' in flag:
            return xjPlayer(id)
        if '橙果' in flag:
            return cgPlayer(id)
        if '九果' in flag:
            return jgPlay(id)
        if '五果' in flag:
            WGService.init()
            url = id
            if url.startswith("五果@"):
                url = url[3:]
            if ".kbtjenysn.cc" in url:
                url = re.sub(r"https?://[^/]+", WGService.host.rstrip("/"), url)
            return {"parse": 0, "url": url}
        if '河果' in flag:
            arr = id.split("++")
            cid, cindex, bid = arr[0], arr[1], arr[2]
            body = {"bookId": bid, "chapterId": cid, "unClockType": "pay", "confirmPay": 2, "autoPayFlag": True, "omap": {"channelName": "精选", "logId": "17a6500357709bb2547e1e122b438cfc", "originName": "书城", "recId": "bigdata_rec", "scene": "nsc_727", "sceneId": "dzmf_video_sc_reco", "strategyId": "g6y6b5sq"}}
            res = HMService.api("1133", body)
            if res.get("chaptersPayType") == '免费':
                if res.get("chapterInfo") and res["chapterInfo"][0].get("content"):
                    c = res["chapterInfo"][0]["content"]
                    pu = c.get("m3u8720p") or (c.get("mp4SwitchUrl")[0] if c.get("mp4SwitchUrl") else "")
                    return {"parse": 0, "url": pu, "header": {"User-Agent": "okhttp/4.10.0"}}
            elif res.get("chaptersPayType") == '按章付费':
                return {"parse": 0, "url": f"https://api.cenguigui.cn/api/duanju/hema.php?book_id={bid}&video_id={cindex}&type=mp4"}
            return {"parse": 0, "url": "toast://解析失败"}
        if '百果' in flag:
            html = fetch_json("https://sv.baidu.com/appui/api?cmd=video/relate&log=vhk&tn=1020970b&ctn=1008350n&blur=1", method='POST', headers=CFG["headers"]["baidu_app"], data=f"method=post&vid={id}")
            j = html.get("video/relate", {}).get("data", {}).get("cur_video", {})
            if j and j.get("clarityUrl"):
                urls = sorted([i for i in j["clarityUrl"] if i.get("url")], key=lambda x: x.get("video_quality", 0), reverse=True)
                return {"parse": 0, "url": urls[0]["url"]}
            return {"parse": 0, "url": id}
        if '牛果' in flag:
            p = id.split('+')
            if len(p) == 3 and p[2] == 'free':
                r = NNService.api("https://new.tianjinzhitongdaohe.com/api/v1/app/play/movieDetails", {"id": p[1], "source": 0, "typeId": "S1", "userId": "546932", "episodeId": p[0]})
                return {"parse": 0, "url": r.get("data", {}).get("url") or "toast://无法播放"}
            elif len(p) == 3:
                if p[1] != 'free':
                    d1 = f"ac=mobile&os=Android&vod_version=1.10.21.6-tob&os_version=12&lock_ad=3&lock_free=3&type=1&clientVersion=v5.2.5&uuid=6IDYUSASPQY5BBVACWQW3LLTPV4V7DE26UOCX5TZTVUGX4VUJNXQ01&resolution=1080*2320&openudid=82f4175d577a2939&dt=22021211RC&os_api=31&install_id=1496879012031075&device_brand=Redmi&sdk_version=1.1.3.0&package_name=com.niuniu.ztdh.app&siteid=5627189&dev_log_aid=667431&oaid=abec0dfff623201b&timestamp={int(time.time())}"
                    NNService.post1("https://csj-sp.csjdeveloper.com/csj_sp/api/v1/pay/ad_unlock?siteid=5627189", d1, p[0])
                d2 = f"not_include=0&lock_free=1&type=1&clientVersion=v5.2.5&uuid=6IDYUSASPQY5BBVACWQW3LLTPV4V7DE26UOCX5TZTVUGX4VUJNXQ01&resolution=1080*2320&openudid=82f4175d577a2939&dt=22021211RC&os_api=31&install_id=1496879012031075&sdk_version=1.1.3.0&siteid=5627189&dev_log_aid=667431&oaid=abec0dfff623201b&timestamp={int(time.time())}&direction=0&ac=mobile&os=Android&vod_version=1.10.21.6-tob&os_version=12&count=1&index=1&shortplay_id={p[2]}&sha1=46121F77CE2FCAD3DBC3B9EC8A24908C1A8AD6D9&device_brand=Redmi&package_name=com.niuniu.ztdh.app"
                r = NNService.post1("https://csj-sp.csjdeveloper.com/csj_sp/api/v1/shortplay/detail?siteid=5627189", d2, p[0])
                try: u = r["data"]["list"][0]["video_model"]["video_list"]["video_1"]["main_url"]
                except Exception: u = ""
                return {"parse": 0, "url": base64.b64decode(u).decode('utf-8') if u else "toast://解析失败"}
        if '好果' in flag:
            res = fetch_json("https://sv.baidu.com/appui/api?cmd=video/relate&log=vhk&tn=1020970b&ctn=1008350n&blur=1", method='POST', headers=CFG["headers"]["browser"], data=f"method=post&vid={id}")
            l = res.get("video/relate", {}).get("data", {}).get("cur_video", {}).get("clarityUrl", [])
            urls = []
            for i in l:
                urls.extend([i.get("title", ""), i.get("url", "")])
            return {"parse": 0, "url": urls}
        if '观果' in flag:
            try:
                s = json.loads(id)
                u = []
                if s.get("super"): u.extend(["超清", s["super"]])
                if s.get("high"): u.extend(["高清", s["high"]])
                if s.get("normal"): u.extend(["流畅", s["normal"]])
                return {"parse": 0, "url": u if u else id}
            except Exception: return {"parse": 0, "url": id}
    except Exception: pass
    return {"parse": 0, "url": id}
