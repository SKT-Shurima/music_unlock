"""
QMCv2 (musicex) 解密核心 —— QQ 音乐 PC 版 ≥19.5 新格式。

与旧版 QMC1(内嵌 key,走 wasm_bridge)不同,QMCv2 文件本身不含可用密钥,
需要从 QQ 音乐服务器获取的 ekey(见 qq_api.py),本模块负责:
  decrypt_ekey(ekey_b64)  -> rc4key       (TC-TEA 解出真实 RC4 密钥)
  decrypt_audio(audio, rc4key) -> bytes    (MAP / RC4 流式解密)

算法与 unlock-music / parakeet 一致。MAP cipher 的 rotate 公式采用
unlock-music-go 的实现 `(v<<r)|(v>>r)`(JS 版的 `(8-r)` 是错误的)。

numpy 仅作 MAP 模式的可选加速,缺失时自动回退到纯 Python。
"""
import base64
import struct

try:
    import numpy as _np
    _HAS_NUMPY = True
except ImportError:  # 无 numpy 也能跑,只是 MAP 模式慢一些
    _HAS_NUMPY = False


# ============================================================
# TC-TEA (腾讯魔改 TEA,CBC 模式) —— 用于 ekey -> rc4key
# ============================================================
def _tea_decrypt_block(v0, v1, k0, k1, k2, k3):
    delta = 0x9E3779B9
    s = 0xE3779B90  # delta * 16 mod 2^32
    for _ in range(16):
        v1 = (v1 - ((((v0 << 4) & 0xFFFFFFFF) + k2) ^ ((v0 + s) & 0xFFFFFFFF) ^ (((v0 >> 5) + k3) & 0xFFFFFFFF))) & 0xFFFFFFFF
        v0 = (v0 - ((((v1 << 4) & 0xFFFFFFFF) + k0) ^ ((v1 + s) & 0xFFFFFFFF) ^ (((v1 >> 5) + k1) & 0xFFFFFFFF))) & 0xFFFFFFFF
        s = (s - delta) & 0xFFFFFFFF
    return v0, v1


def _u32be(b, o):
    return struct.unpack('>I', b[o:o + 4])[0]


def _tea_cbc_decrypt(cipher, key16):
    n = len(cipher)
    if n < 10 or n % 8 != 0:
        return None
    k0, k1, k2, k3 = _u32be(key16, 0), _u32be(key16, 4), _u32be(key16, 8), _u32be(key16, 12)
    res = bytearray(cipher)
    iv1 = bytearray(8)
    iv2 = bytearray(8)
    nxt = bytearray(8)
    for i in range(0, n, 8):
        blk = res[i:i + 8]
        nxt[:] = blk
        for j in range(8):
            blk[j] ^= iv2[j]
        v0, v1 = _u32be(blk, 0), _u32be(blk, 4)
        d0, d1 = _tea_decrypt_block(v0, v1, k0, k1, k2, k3)
        blk[0:4] = struct.pack('>I', d0)
        blk[4:8] = struct.pack('>I', d1)
        iv2[:] = blk
        for j in range(8):
            blk[j] ^= iv1[j]
        iv1[:] = nxt
        res[i:i + 8] = blk
    pad = (res[0] & 0x07) + 2
    start = 1 + pad
    end = n - 7
    if end <= start:
        return None
    for i in range(end, n):
        if res[i] != 0:
            return None
    return bytes(res[start:end])


_SIMPLE_KEY = bytes([0x69, 0x56, 0x46, 0x38, 0x2B, 0x20, 0x15, 0x0B])


def decrypt_ekey(ekey_b64: str) -> bytes:
    """把服务器返回的 base64 ekey 解成真实 RC4 密钥。"""
    decoded = base64.b64decode(ekey_b64)
    if len(decoded) < 8:
        raise ValueError("ekey too short after base64 decode")
    tea_key = bytearray(16)
    for i in range(8):
        tea_key[i * 2] = _SIMPLE_KEY[i]
        tea_key[i * 2 + 1] = decoded[i]
    body = _tea_cbc_decrypt(decoded[8:], bytes(tea_key))
    if body is None:
        raise ValueError("TC-TEA decryption of ekey failed")
    return decoded[:8] + body


# ============================================================
# MAP cipher (rc4key 长度 <= 300)
# ============================================================
def _map_table(key):
    """预计算 offset 0..0x7ffe 的 mask(numpy 加速用)。"""
    N = len(key)
    karr = _np.frombuffer(key, dtype=_np.uint8)
    offs = _np.arange(0x7fff, dtype=_np.int64)
    idx = (offs * offs + 71214) % N
    vals = karr[idx].astype(_np.uint16)
    r = (((idx & 7) + 4) % 8)
    return (((vals << r) | (vals >> r)) & 0xFF).astype(_np.uint8)


def _map_decrypt_np(audio, key):
    n = len(audio)
    N = len(key)
    karr = _np.frombuffer(key, dtype=_np.uint8)
    a = _np.frombuffer(bytes(audio), dtype=_np.uint8).copy()
    CH = 1 << 20
    for s in range(0, n, CH):
        e = min(s + CH, n)
        offs = _np.arange(s, e, dtype=_np.int64)
        o = _np.where(offs > 0x7fff, offs % 0x7fff, offs)
        idx = (o * o + 71214) % N
        vals = karr[idx].astype(_np.uint16)
        r = ((idx & 7) + 4) % 8
        mask = (((vals << r) | (vals >> r)) & 0xFF).astype(_np.uint8)
        a[s:e] ^= mask
    return a.tobytes()


def _map_decrypt_py(audio, key):
    N = len(key)
    a = bytearray(audio)
    for i in range(len(a)):
        off = i % 0x7fff if i > 0x7fff else i
        idx = (off * off + 71214) % N
        v = key[idx]
        r = ((idx & 7) + 4) % 8
        a[i] ^= ((v << r) | (v >> r)) & 0xFF
    return bytes(a)


# ============================================================
# RC4 cipher (rc4key 长度 > 300,分段)
# ============================================================
_FIRST_SEG = 0x80
_SEG = 0x1400


class _RC4:
    def __init__(self, key):
        self.key = key
        self.N = N = len(key)
        S = bytearray(i & 0xFF for i in range(N))
        j = 0
        for i in range(N):
            j = (S[i] + j + key[i % N]) % N
            S[i], S[j] = S[j], S[i]
        self.S = S
        self.hash = 1
        for i in range(N):
            v = key[i]
            if v == 0:
                continue
            nx = (self.hash * v) & 0xFFFFFFFF
            if nx == 0 or nx <= self.hash:
                break
            self.hash = nx

    def _seg_key(self, idd):
        seed = self.key[idd % self.N]
        if seed == 0:
            return 0
        return int((self.hash / ((idd + 1) * seed)) * 100.0) % self.N

    def decrypt(self, buf, offset):
        n = len(buf)
        proc = 0
        tot = n
        if offset < _FIRST_SEG:
            L = min(tot, _FIRST_SEG - offset)
            for i in range(L):
                buf[i] ^= self.key[self._seg_key(offset + i)]
            tot -= L; proc += L; offset += L
        if tot > 0 and offset % _SEG:
            L = min(_SEG - (offset % _SEG), tot)
            self._seg(buf, proc, L, offset)
            tot -= L; proc += L; offset += L
        while tot > _SEG:
            self._seg(buf, proc, _SEG, offset)
            proc += _SEG; tot -= _SEG; offset += _SEG
        if tot > 0:
            self._seg(buf, proc, tot, offset)

    def _seg(self, buf, start, length, offset):
        S = bytearray(self.S)
        N = self.N
        skip = (offset % _SEG) + self._seg_key(offset // _SEG)
        j = 0
        k = 0
        i = -skip
        while i < length:
            j = (j + 1) % N
            k = (S[j] + k) % N
            S[j], S[k] = S[k], S[j]
            if i >= 0:
                buf[start + i] ^= S[(S[j] + S[k]) % N]
            i += 1


# ============================================================
# 统一入口
# ============================================================
def decrypt_audio(audio: bytes, rc4key: bytes) -> bytes:
    """用 rc4key 解密音频流。自动按 key 长度选 MAP / RC4。"""
    if len(rc4key) > 300:
        a = bytearray(audio)
        _RC4(rc4key).decrypt(a, 0)
        return bytes(a)
    if _HAS_NUMPY:
        return _map_decrypt_np(audio, rc4key)
    return _map_decrypt_py(audio, rc4key)
