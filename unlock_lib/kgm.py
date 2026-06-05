"""
KGM format handler — Kugou Music encrypted formats.

Handles: .kgm .kgma .vpr

Decryption is performed via a Node.js WASM bridge that uses the
standard @xhacker/kgmwasm module installed in ~/.music-tool/.
"""

import subprocess
import json
import os

_WASM_BRIDGE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'wasm_bridge.js')

# All known KGM file extensions
_KGM_EXTS = {'kgm', 'kgma', 'vpr'}


def detect(ext: str) -> bool:
    """Check if this extension is a known KGM format."""
    return ext.lower() in _KGM_EXTS


def decrypt(data: bytearray, ext: str) -> bytearray:
    """Decrypt KGM-encrypted audio data via WASM bridge.

    Args:
        data: Complete file contents
        ext: File extension

    Returns:
        Decrypted audio data
    """
    tool_dir = os.path.dirname(os.path.dirname(__file__))
    tmp_dir = os.path.join(tool_dir, 'tmp')
    os.makedirs(tmp_dir, exist_ok=True)

    in_path = os.path.join(tmp_dir, f'kgm_in.{ext}')
    out_path = os.path.join(tmp_dir, f'kgm_out.bin')

    with open(in_path, 'wb') as f:
        f.write(bytes(data))

    result = subprocess.run(
        ['node', _WASM_BRIDGE, 'kgm', in_path, out_path],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=tool_dir,
    )

    if result.returncode != 0:
        err = result.stderr.strip()
        raise RuntimeError(f'KGM decryption failed: {err}')

    with open(out_path, 'rb') as f:
        decrypted = bytearray(f.read())

    for p in (in_path, out_path):
        try:
            os.unlink(p)
        except OSError:
            pass

    return decrypted
