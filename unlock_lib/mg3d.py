"""
MG3D format handler (.mg3d files).

Migu 3D audio — custom WAV variant. The encryption is a subtraction cipher
with a 32-byte repeating key. The key is discovered by brute-forcing:
  1. Try possible keys (uppercase hex chars only, each byte 0-9 or A-F)
  2. Decrypt the first 0x100 bytes with candidate key
  3. Validate: decrypted data must look like a RIFF WAVE header
  4. Use the first valid key to decrypt the entire file

Key format: 32 bytes, each byte is an uppercase hex ASCII character
(0x30-0x39 = '0'-'9', 0x41-0x46 = 'A'-'F').
"""

import struct


def detect(ext: str) -> bool:
    """Check if this is an MG3D format."""
    return ext.lower() == 'mg3d'


def _generate_key_candidates() -> list:
    """Generate common MG3D keys as bytes.

    All known MG3D keys consist of uppercase hex characters (0-9, A-F).
    We try a few common prefix patterns first, then brute-force.
    """
    hex_chars = b'0123456789ABCDEF'
    # Generate keys that start with common patterns
    # Most keys start with '0' or 'A'-'F'
    candidates = []
    # Try keys starting with '00', '0A', 'A0', 'AA', etc.
    prefixes = [b'00', b'0A', b'A0', b'AA', b'0F', b'F0']
    for p in prefixes:
        key = p * 16  # Repeat prefix to get 32 bytes
        candidates.append(key)
    return candidates


def _is_valid_wav_header(data: bytes) -> bool:
    """Check if data starts with a valid RIFF WAVE header."""
    if len(data) < 0x2C:
        return False

    # Must start with "RIFF"
    if data[0:4] != b'RIFF':
        return False

    # Must contain "WAVEfmt " at offsets 8-15
    if data[8:16] != b'WAVEfmt ':
        return False

    # fmt chunk size at offset 16 (4 bytes LE) must be 16, 18, or 40
    fmt_size = struct.unpack_from('<I', data, 16)[0]
    if fmt_size not in (16, 18, 40):
        return False

    # First data chunk name should be printable ASCII
    data_offset = 20 + fmt_size
    if data_offset + 4 > len(data):
        return False
    chunk_name = data[data_offset:data_offset + 4]
    for b in chunk_name:
        if b < 0x20 or b > 0x7E:
            return False

    return True


def _try_decrypt_header(data: bytes, key: bytes) -> bool:
    """Try decrypting the header with a candidate key."""
    segment = bytearray(data[:0x100])
    for i in range(len(segment)):
        segment[i] = (segment[i] - key[i % 32]) & 0xFF
    return _is_valid_wav_header(bytes(segment))


def _brute_force_key(data: bytes) -> bytes:
    """Find the correct 32-byte MG3D key via brute force."""
    hex_chars = b'0123456789ABCDEF'

    # Phase 1: Try common patterns
    for first in hex_chars:
        key = bytes([first] * 32)
        if _try_decrypt_header(data, key):
            return key

    # Phase 2: Try all 2-byte patterns (more common)
    for c1 in hex_chars:
        for c2 in hex_chars:
            key = bytes([c1, c2] * 16)
            if _try_decrypt_header(data, key):
                return key

    # Phase 3: Try 4-byte repeating patterns
    for c1 in hex_chars[:4]:  # Limit to first 4 hex chars for speed
        for c2 in hex_chars:
            for c3 in hex_chars:
                for c4 in hex_chars:
                    key = bytes([c1, c2, c3, c4] * 8)
                    if _try_decrypt_header(data, key):
                        return key

    raise ValueError("Cannot find MG3D key — file may be corrupted or use unknown key format")


def decrypt(data: bytearray, ext: str) -> bytearray:
    """Decrypt MG3D encrypted data.

    The encryption is a subtraction cipher with 32-byte block size:
        plaintext[i] = (ciphertext[i] - key[i % 32]) mod 256
    """
    if len(data) < 0x100:
        raise ValueError("MG3D file too small (min 256 bytes)")

    # Find the key
    key = _brute_force_key(bytes(data))

    # Decrypt entire file
    for i in range(len(data)):
        data[i] = (data[i] - key[i % 32]) & 0xFF

    return data
