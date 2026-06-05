"""
QMC/QTag format handler — QQ Music encrypted formats.

Handles: .mflac .mgg .mggl .qmc0 .qmc2 .qmc3 .qmc4 .qmc6 .qmc8
         .qmcflac .qmcogg .mflac0 .mgg0 .mgg1 .mflach .mmp4
         .bkcmp3 .bkcflac .bkcwav .bkcogg .bkcwma .bkcape .bkcm4a .tkm

Decryption is performed via a Node.js WASM bridge that uses the
standard @xhacker/qmcwasm module installed in ~/.music-tool/.
"""

import subprocess
import json
import os
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
