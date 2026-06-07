"""
QQ 音乐 ekey 获取 + songmid 解析 —— 用于 QMCv2(musicex)解密。

QMCv2 文件本身不含可用密钥,需要凭登录 cookie 调 QQ 音乐 API 获取 ekey:
  - 关键:API 的 songmid 参数必须是真正的 songmid,而文件名里的是 media_mid,两者不同。
  - songmid 来源:musicex footer 自带 / 数字命名(NNNN-NN)按 song_id 查 API /
                  O 前缀(O4M0xxx)按 media_mid 查本地 qqmusic.sqlite。

如何获取 cookie:浏览器登录 https://y.qq.com,F12 → Application → Cookies →
  复制 `qqmusic_key` 的值(完整 cookie 串更稳妥,含 qm_keyst/euin/wxuin 等)。
"""
import json
import os
import re
import ssl
import struct
import urllib.request

try:
    import certifi
    _CAFILE = certifi.where()
except ImportError:
    _CAFILE = None

_CTX = ssl.create_default_context(cafile=_CAFILE) if _CAFILE else ssl.create_default_context()
# 绕过系统代理直连,避免抓包代理的自签证书导致校验失败
_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=_CTX),
)

_GUID = "e1b475ed2a9f206084deaf3541d77343590a6454"
_API = "https://u.y.qq.com/cgi-bin/musicu.fcg"


# ============================================================
# footer 解析
# ============================================================
def parse_footer(data: bytes) -> dict:
    """识别 QQ 加密文件尾部结构。

    返回 dict:
      fmt: 'musicex' | 'qtag' | 'keytail' | 'nofooter'
      audio_len: 加密音频部分长度
      songmid: musicex 自带的 songmid(其余为 None)
      filename: musicex 自带的媒体文件名(其余为 None)
      embedded_ekey: qtag/keytail 内嵌的 ekey 字符串(其余为 None)
    """
    n = len(data)
    out = {'fmt': 'nofooter', 'audio_len': n, 'songmid': None, 'filename': None, 'embedded_ekey': None}
    if n < 16:
        return out
    if data[n - 8:n] == b'musicex\x00':
        tail = struct.unpack('<I', data[n - 16:n - 12])[0]
        out['fmt'] = 'musicex'
        out['audio_len'] = n - tail
        parts = [p for p in data[n - tail:n - 20].decode('utf-16-le', 'ignore').split('\x00') if p]
        out['filename'] = next((p for p in parts if p.endswith(('.mgg', '.mflac'))), None)
        out['songmid'] = next(
            (p for p in parts if re.fullmatch(r'[A-Za-z0-9]{10,}', p) and not p.endswith(('.mgg', '.mflac'))),
            None)
        return out
    if data[n - 4:n] == b'QTag':
        ps = struct.unpack('>I', data[n - 8:n - 4])[0]
        ts = n - 8 - ps
        if ts >= 0:
            pl = data[ts:n - 8]
            c = pl.find(b',')
            if c > 0:
                out['fmt'] = 'qtag'
                out['audio_len'] = ts
                out['embedded_ekey'] = pl[:c].decode('utf-8', 'ignore')
                return out
    kl = struct.unpack('<I', data[n - 4:n])[0]
    if 0 < kl < 0x300:
        ks = n - 4 - kl
        if ks >= 0:
            out['fmt'] = 'keytail'
            out['audio_len'] = ks
            out['embedded_ekey'] = data[ks:ks + kl].decode('utf-8', 'ignore')
    return out


# ============================================================
# API 调用
# ============================================================
def gtk(qqmusic_key: str) -> int:
    """计算 CSRF token g_tk(QQ 音乐 web API 必需)。"""
    h = 5381
    for c in qqmusic_key:
        h += (h << 5) + ord(c)
    return h & 0x7fffffff


def _extract_key(cookie: str) -> str:
    m = re.search(r'qqmusic_key=([^;]+)', cookie) or re.search(r'qm_keyst=([^;]+)', cookie)
    return m.group(1) if m else ""


def _extract_uin(cookie: str) -> str:
    for name in ('wxuin', 'uin'):
        m = re.search(rf'(?:^|[;\s]){name}=(\d+)', cookie)
        if m:
            return m.group(1)
    return "0"


def _comm(cookie: str) -> dict:
    g = gtk(_extract_key(cookie))
    uin = _extract_uin(cookie)
    return {
        "uin": uin, "format": "json", "ct": 24, "cv": 4747474,
        "platform": "yqq.json", "chid": "0",
        "g_tk": g, "g_tk_new_20200303": g, "tmeLoginType": "1",
        "inCharset": "utf-8", "outCharset": "utf-8", "notice": 0, "needNewCode": 1,
    }


def _post(body: dict, cookie: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        _API, data=json.dumps(body).encode(),
        headers={
            "Referer": "https://y.qq.com/", "Origin": "https://y.qq.com",
            "Cookie": cookie, "User-Agent": "Mozilla/5.0 Chrome/124",
        })
    with _OPENER.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def fetch_ekeys(pairs, cookie: str) -> dict:
    """批量取 ekey。pairs=[(songmid, filename), ...];返回 {filename: ekey}。"""
    if not pairs:
        return {}
    uin = _extract_uin(cookie)
    body = {
        "req_0": {
            "module": "music.vkey.GetVkey", "method": "UrlGetVkey",
            "param": {
                "guid": _GUID,
                "songmid": [p[0] for p in pairs],
                "filename": [p[1] for p in pairs],
                "songtype": [0] * len(pairs),
                "uin": uin, "ctx": 0,
            },
        },
        "comm": _comm(cookie),
    }
    j = _post(body, cookie)
    out = {}
    for info in j.get('req_0', {}).get('data', {}).get('midurlinfo', []):
        if info.get('ekey'):
            out[info.get('filename')] = info['ekey']
    return out


def fetch_ekey(songmid: str, filename: str, cookie: str):
    """取单个 ekey,失败返回 None。"""
    return fetch_ekeys([(songmid, filename)], cookie).get(filename)


_detail_cache = {}


def song_detail_by_id(song_id, cookie: str):
    """按数字 song_id 查 (songmid, media_mid)。用于 NNNN-NN 命名文件。"""
    song_id = str(song_id)
    if song_id in _detail_cache:
        return _detail_cache[song_id]
    res = (None, None)
    try:
        j = _post({
            "req_0": {"module": "music.pf_song_detail_svr", "method": "get_song_detail",
                      "param": {"song_id": int(song_id)}},
            "comm": _comm(cookie),
        }, cookie)
        t = j.get('req_0', {}).get('data', {}).get('track_info', {})
        res = (t.get('mid'), t.get('file', {}).get('media_mid'))
    except Exception:
        pass
    _detail_cache[song_id] = res
    return res


# ============================================================
# 候选文件名(无 footer 文件需按音质前缀试)
# ============================================================
def candidate_filenames(ext: str, media_mid: str):
    if ext == '.mgg' or ext == 'mgg':
        return [f"{p}{media_mid}.mgg" for p in ('O8M0', 'O6M0', 'O4M0', 'O2M0')]
    return [f"{p}{media_mid}.mflac" for p in ('F0M0', 'RS01', 'F000')]


# ============================================================
# 本地 QQ 音乐数据库(O 前缀文件按 media_mid 反查 songmid)
# ============================================================
_DEFAULT_DB = os.path.expanduser(
    "~/Library/Containers/com.tencent.QQMusicMac/Data/Library/"
    "Application Support/QQMusicMac/qqmusic.sqlite")


class LocalDB:
    """本地 qqmusic.sqlite 映射;不存在时降级为空(所有查询返回 None)。"""

    def __init__(self, path: str = None):
        self.by_media = {}
        self.by_id = {}
        self.available = False
        path = path or _DEFAULT_DB
        if not os.path.exists(path):
            return
        try:
            import sqlite3
            con = sqlite3.connect(path)
            cur = con.cursor()
            cur.execute("SELECT id, K_SONG_RESERVE1, K_SONG_RESERVE8 FROM SONGS")
            for sid, songmid, mediamid in cur.fetchall():
                if songmid:
                    if mediamid:
                        self.by_media[mediamid] = (songmid, mediamid)
                    self.by_id[str(sid)] = (songmid, mediamid)
            con.close()
            self.available = True
        except Exception:
            self.available = False

    def by_media_mid(self, media_mid):
        return self.by_media.get(media_mid)

    def by_song_id(self, song_id):
        return self.by_id.get(str(song_id))
