"""
Decryption orchestration engine.

Automatically detects file format, dispatches to the correct handler,
and writes decrypted output with proper file extension.
"""

import os
import sys
from unlock_lib import audio_utils

# Format handlers — each has detect(ext) and decrypt(data, ext)
_HANDLERS = {}

def _load_handlers():
    """Lazy-load format handlers."""
    global _HANDLERS
    if _HANDLERS:
        return

    from unlock_lib import cache, tm, xm, kwm, mg3d, ximalaya, ncm, kgm, qmc

    _HANDLERS = {
        'cache':     (cache.detect, cache.decrypt),
        'tm':        (tm.detect, tm.decrypt),
        'xm':        (xm.detect, xm.decrypt),
        'kwm':       (kwm.detect, kwm.decrypt),
        'mg3d':      (mg3d.detect, mg3d.decrypt),
        'ximalaya':  (ximalaya.detect, ximalaya.decrypt),
        'ncm':       (ncm.detect, ncm.decrypt),
        'kgm':       (kgm.detect, kgm.decrypt),
        'qmc':       (qmc.detect, qmc.decrypt),
    }


def decrypt_file(input_path: str, output_dir: str, failed_dir: str = None,
                 cookie: str = None, localdb=None) -> dict:
    """Decrypt a single encrypted music file.

    Args:
        input_path: Path to encrypted file
        output_dir: Directory for decrypted output
        failed_dir: Optional directory to copy failed files
        cookie:     QQ 音乐登录 cookie(QMCv2/musicex 新格式必需)
        localdb:    qq_api.LocalDB 实例(O 前缀文件反查 songmid,可选)

    Returns:
        dict with keys: success, input_path, output_path, format, error, size
    """
    _load_handlers()

    result = {
        'success': False,
        'input_path': input_path,
        'output_path': '',
        'format': '',
        'error': '',
        'size': 0,
    }

    # Determine file extension
    fname = os.path.basename(input_path)
    ext = os.path.splitext(fname)[1].lstrip('.').lower()
    if not ext:
        # Try hex-encoded extension (QQ Music cache naming)
        ext = fname.split('.')[-1].lower() if '.' in fname else fname.lower()

    result['format'] = ext

    if not audio_utils.is_encrypted_ext(ext):
        result['error'] = f'Not an encrypted format: .{ext}'
        return result

    # Read file
    try:
        with open(input_path, 'rb') as f:
            data = bytearray(f.read())
    except Exception as e:
        result['error'] = f'Read error: {e}'
        return result

    if len(data) == 0:
        result['error'] = 'Empty file'
        return result

    # Find and run handler
    try:
        decrypted = None

        from unlock_lib import qmc
        if qmc.detect(ext):
            # QQ 音乐:智能路由(内嵌 key→WASM;musicex/无 footer→API 取 ekey)
            decrypted = qmc.decrypt_qq(data, fname, cookie=cookie, localdb=localdb)
        else:
            for name, (detector, handler) in _HANDLERS.items():
                if detector(ext):
                    decrypted = handler(data, ext)
                    break

        if decrypted is None:
            result['error'] = f'No handler for format: .{ext}'
            return result

        # Determine output extension
        out_ext = audio_utils.sniff_extension(bytes(decrypted[:64]),
                                               audio_utils.expected_output_ext(ext))
        if out_ext == 'wav':
            # Verify WAV header
            if len(decrypted) >= 12 and bytes(decrypted[8:12]) != b'WAVE':
                out_ext = 'mp3'

        # Write output
        base_name = os.path.splitext(fname)[0]
        out_name = f'{base_name}.{out_ext}'
        out_path = os.path.join(output_dir, out_name)

        # Handle name collisions
        counter = 1
        while os.path.exists(out_path):
            out_name = f'{base_name}_{counter}.{out_ext}'
            out_path = os.path.join(output_dir, out_name)
            counter += 1

        os.makedirs(output_dir, exist_ok=True)
        with open(out_path, 'wb') as f:
            f.write(bytes(decrypted))

        result['success'] = True
        result['output_path'] = out_path
        result['size'] = len(decrypted)

    except Exception as e:
        result['error'] = str(e)
        # Copy failed file
        if failed_dir:
            try:
                os.makedirs(failed_dir, exist_ok=True)
                import shutil
                shutil.copy2(input_path, os.path.join(failed_dir, fname))
            except Exception:
                pass

    return result


def decrypt_directory(input_dir: str, output_dir: str,
                      failed_dir: str = None,
                      progress_callback=None,
                      cookie: str = None, localdb=None) -> dict:
    """Decrypt all encrypted files in a directory recursively.

    Args:
        input_dir: Source directory to scan
        output_dir: Output directory for decrypted files
        failed_dir: Directory for files that couldn't be decrypted
        progress_callback: Optional callback(current, total, filename)

    Returns:
        dict with keys: total, success, failed, results[]
    """
    os.makedirs(output_dir, exist_ok=True)
    if failed_dir:
        os.makedirs(failed_dir, exist_ok=True)

    # Collect encrypted files
    encrypted_files = []
    for root, dirs, files in os.walk(input_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lstrip('.').lower()
            if audio_utils.is_encrypted_ext(ext):
                encrypted_files.append(os.path.join(root, f))

    total = len(encrypted_files)
    results = []
    success_count = 0
    fail_count = 0

    for idx, filepath in enumerate(encrypted_files):
        if progress_callback:
            progress_callback(idx, total, os.path.basename(filepath))

        r = decrypt_file(filepath, output_dir, failed_dir, cookie=cookie, localdb=localdb)
        results.append(r)

        if r['success']:
            success_count += 1
            print(f"  OK  {os.path.basename(filepath)} → {os.path.basename(r['output_path'])}")
        else:
            fail_count += 1
            print(f"  FAIL  {os.path.basename(filepath)}: {r['error']}")

    if progress_callback:
        progress_callback(total, total, 'DONE')

    return {
        'total': total,
        'success': success_count,
        'failed': fail_count,
        'results': results,
    }
