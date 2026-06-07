"""
QMC/QTag format handler — QQ Music encrypted formats.

Handles: .mflac .mgg .mggl .qmc0 .qmc2 .qmc3 .qmc4 .qmc6 .qmc8
         .qmcflac .qmcogg .mflac0 .mgg0 .mgg1 .mflach .mmp4
         .bkcmp3 .bkcflac .bkcwav .bkcogg .bkcwma .bkcape .bkcm4a .tkm

两类密钥来源:
  - QMC1(内嵌 key:QTag / 短 key 尾):走 Node.js WASM 桥接(@xhacker/qmcwasm),无需 cookie
  - QMCv2(musicex / 无 footer,QQ 音乐 PC ≥19.5):文件不含密钥,需凭登录 cookie
    调 QQ 音乐 API 取 ekey 后用纯 Python 解密(见 qmc2.py / qq_api.py)
"""

import subprocess
import json
import os
import re
import shutil

_WASM_BRIDGE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'wasm_bridge.js')

# All known QMC file extensions
_QMC_EXTS = {
    'mflac', 'mgg', 'mggl', 'mgg0', 'mgg1', 'mflac0', 'mflach', 'mmp4',
    'qmcflac', 'qmcogg',
    'qmc0', 'qmc2', 'qmc3', 'qmc4', 'qmc6', 'qmc8',
    'bkcmp3', 'bkcflac', 'bkcwav', 'bkcogg', 'bkcwma', 'bkcape', 'bkcm4a',
    'tkm',
    '666c6163', '6d7033', '6f6767', '6d3461', '776176',
}


def detect(ext: str) -> bool:
    """Check if this extension is a known QMC format."""
    return ext.lower() in _QMC_EXTS


def decrypt(data: bytearray, ext: str) -> bytearray:
    """Decrypt QMC-encrypted audio data via WASM bridge.

    Writes input to a temp file, calls the Node.js WASM bridge,
    reads back the decrypted output.

    Args:
        data: Complete file contents
        ext: File extension

    Returns:
        Decrypted audio data
    """
    import tempfile

    tool_dir = os.path.dirname(os.path.dirname(__file__))
    tmp_dir = os.path.join(tool_dir, 'tmp')
    os.makedirs(tmp_dir, exist_ok=True)

    # Write encrypted data to temp file
    in_path = os.path.join(tmp_dir, f'qmc_in.{ext}')
    out_path = os.path.join(tmp_dir, f'qmc_out.bin')

    with open(in_path, 'wb') as f:
        f.write(bytes(data))

    # Call Node.js WASM bridge
    result = subprocess.run(
        ['node', _WASM_BRIDGE, 'qmc', in_path, out_path],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=tool_dir,
    )

    if result.returncode != 0:
        err = result.stderr.strip()
        raise RuntimeError(f'QMC decryption failed: {err}')

    # Read back decrypted data
    with open(out_path, 'rb') as f:
        decrypted = bytearray(f.read())

    # Cleanup
    for p in (in_path, out_path):
        try:
            os.unlink(p)
        except OSError:
            pass

    return decrypted


# ============================================================
# QMCv2 (musicex) 智能路由
# ============================================================
class NeedCookieError(Exception):
    """musicex / 无 footer 文件需要 QQ 音乐 cookie 才能取密钥。"""


def _is_audio(buf) -> bool:
    """判断解密结果是否为有效音频头(FLAC/OGG/MP3/WAV/M4A/APE)。"""
    if len(buf) < 4:
        return False
    b = bytes(buf[:12])
    if b[:4] in (b'fLaC', b'OggS', b'wma\x00'):
        return True
    if b[:3] == b'ID3' or (b[0] == 0xFF and (b[1] & 0xE0) == 0xE0):  # mp3
        return True
    if b[:4] == b'RIFF' and b[8:12] == b'WAVE':  # wav
        return True
    if b[4:8] == b'ftyp':  # m4a/mp4
        return True
    if b[:4] == b'MAC ':  # ape
        return True
    return False


def decrypt_qq(data: bytearray, fname: str, cookie: str = None, localdb=None) -> bytearray:
    """按文件尾部结构智能解密 QQ 音乐文件。

    Args:
        data:    完整文件内容
        fname:   文件名(用于 musicex/O 前缀/数字命名 的 songmid 解析)
        cookie:  QQ 音乐登录 cookie(含 qqmusic_key);musicex/无 footer 必需
        localdb: qq_api.LocalDB 实例,用于 O 前缀文件按 media_mid 反查 songmid(可选)

    Returns:
        解密后的音频数据(保证是有效音频,否则抛异常)
    """
    from unlock_lib import qq_api, qmc2

    raw = bytes(data)
    info = qq_api.parse_footer(raw)
    fmt = info['fmt']
    audio = raw[:info['audio_len']]

    # 1) 内嵌 key(QMC1):QTag / 短 key 尾
    #    先试 WASM(QMC1),再试把内嵌串当 QMCv2 ekey(qmc2);均校验音频头
    if fmt in ('qtag', 'keytail'):
        ext_for_wasm = os.path.splitext(fname)[1].lstrip('.').lower() or 'mflac'
        try:
            out = decrypt(data, ext_for_wasm)
            if _is_audio(out):
                return out
        except Exception:
            pass
        if info['embedded_ekey']:
            try:
                out = qmc2.decrypt_audio(audio, qmc2.decrypt_ekey(info['embedded_ekey']))
                if _is_audio(out):
                    return bytearray(out)
            except Exception:
                pass
        # 内嵌 key 解不出:可能是 QMCv2 伪装,继续尝试 API(需 cookie)

    # 2) QMCv2:musicex / 无 footer / 内嵌失败 —— 需要 ekey
    if not cookie:
        raise NeedCookieError(
            f"{fname} 是 QQ 音乐新格式(musicex/QMCv2),需提供 --cookie 才能解密")

    base, ext = os.path.splitext(os.path.basename(fname))

    # 解析 songmid + 候选请求文件名
    songmid = None
    req_filenames = []
    if fmt == 'musicex' and info['songmid'] and info['filename']:
        songmid = info['songmid']
        req_filenames = [info['filename']]
    else:
        # 无 footer:O 前缀(O4M0xxx)或数字命名(NNNN-NN)
        m_oprefix = re.match(r'^([A-Z]\d[A-Z]\d)(.+)$', base)
        m_numbered = re.match(r'^(\d+)-\d+$', base)
        if m_oprefix:
            media_mid = m_oprefix.group(2)
            rec = localdb.by_media_mid(media_mid) if localdb else None
            if rec:
                songmid = rec[0]
            req_filenames = [os.path.basename(fname)] + qq_api.candidate_filenames(ext, media_mid)
        elif m_numbered:
            rec = localdb.by_song_id(m_numbered.group(1)) if localdb else None
            if not rec or not rec[0]:
                rec = qq_api.song_detail_by_id(m_numbered.group(1), cookie)
            if rec and rec[0]:
                songmid, media_mid = rec
                if media_mid:
                    req_filenames = qq_api.candidate_filenames(ext, media_mid)

    if not songmid or not req_filenames:
        raise RuntimeError(f"无法定位 songmid({fmt}),该歌曲可能不在 QQ 音乐库中")

    # 逐个候选请求 ekey,解密后校验音频头,取第一个有效的
    last_err = "未取到 ekey"
    for rfn in req_filenames:
        try:
            ekey = qq_api.fetch_ekey(songmid, rfn, cookie)
        except Exception as e:
            last_err = f"API 错误: {e}"
            continue
        if not ekey:
            continue
        try:
            out = qmc2.decrypt_audio(audio, qmc2.decrypt_ekey(ekey))
        except Exception as e:
            last_err = f"解密失败: {e}"
            continue
        if _is_audio(out):
            return bytearray(out)
        last_err = "解密后非有效音频(可能是试听片段/版权受限)"
    raise RuntimeError(last_err)
