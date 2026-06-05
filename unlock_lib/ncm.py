"""
NCM format handler (.ncm files).

NetEase Cloud Music encrypted format.

File structure:
  [0x00] 8 bytes   magic "CTENFDAM"
  [0x08] 2 bytes   gap (skip)
  [0x0A] 4 bytes   key_length (uint32 LE)
  [0x0E] N bytes   encrypted RC4 key data (XOR 0x64, then AES-128-ECB decrypt)
  [    ] 4 bytes   metadata_length (uint32 LE)
  [    ] N bytes   encrypted metadata (XOR 0x63, base64 decode, AES-128-ECB decrypt)
  [    ] 5 bytes   gap (skip)
  [    ] 4 bytes   image_data_length
  [    ] N bytes   album cover image
  [    ] N bytes   encrypted audio (XOR with derived 256-byte keybox)

Key derivation:
  1. Read encrypted key block, XOR each byte with 0x64
  2. AES-128-ECB decrypt with CORE_KEY (16 bytes)
  3. Drop first 17 bytes → raw RC4 key
  4. Use RC4-KSA to derive 256-byte keybox
  5. Audio data XOR'd with keybox[pos % 256]
"""

import struct
import base64
import json
from unlock_lib.crypto_utils import aes128_ecb_decrypt, rc4_keybox_256
from unlock_lib import audio_utils

# Magic header: "CTENFDAM"
_MAGIC = bytes([0x43, 0x54, 0x45, 0x4E, 0x46, 0x44, 0x41, 0x4D])

# AES-128 keys (hex-encoded)
_CORE_KEY = bytes.fromhex('687a4852416d736f356b496e62617857')  # 16 bytes
_META_KEY = bytes.fromhex('2331346C6A6B5F215C5D2630553C2728')  # 16 bytes


def detect(ext: str) -> bool:
    """Check if this is an NCM format."""
    return ext.lower() == 'ncm'


def _read_key_data(data: bytes, offset: int) -> tuple:
    """Read and decrypt the RC4 key block.

    Returns (key_data, new_offset)
    """
    key_len = struct.unpack_from('<I', data, offset)[0]
    offset += 4

    # Read encrypted key bytes, XOR with 0x64
    cipher_key = bytearray(data[offset:offset + key_len])
    for i in range(len(cipher_key)):
        cipher_key[i] ^= 0x64
    offset += key_len

    # AES-128-ECB decrypt
    plain_key = aes128_ecb_decrypt(bytes(cipher_key), _CORE_KEY)

    # Drop first 17 bytes (AES padding/header)
    return plain_key[17:], offset


def _read_metadata(data: bytes, offset: int) -> dict:
    """Read and decrypt the metadata JSON block.

    Returns (metadata_dict, new_offset)
    """
    meta_len = struct.unpack_from('<I', data, offset)[0]
    offset += 4

    if meta_len == 0:
        return {}, offset

    # Read encrypted metadata, XOR with 0x63
    cipher_meta = bytearray(data[offset:offset + meta_len])
    for i in range(len(cipher_meta)):
        cipher_meta[i] ^= 0x63
    offset += meta_len

    # Drop first 22 bytes, then base64 decode
    b64_data = bytes(cipher_meta[22:]).decode('ascii', errors='ignore')
    encrypted = base64.b64decode(b64_data)

    # AES-128-ECB decrypt
    plain = aes128_ecb_decrypt(encrypted, _META_KEY).decode('utf-8', errors='ignore')

    # Parse JSON (format: "music:{...}" or "dj:{...}")
    colon_idx = plain.find(':')
    if colon_idx > 0:
        json_str = plain[colon_idx + 1:]
        obj = json.loads(json_str)
        if plain[:colon_idx] == 'dj':
            return obj.get('mainMusic', {}), offset
        return obj, offset

    return {}, offset


def _read_audio(data: bytes, offset: int, keybox: bytes) -> bytearray:
    """Decrypt the audio data."""
    # Skip 4 bytes + 13 bytes (internal counters/offsets)
    offset += struct.unpack_from('<I', data, offset + 5)[0] + 13

    audio = bytearray(data[offset:])
    for i in range(len(audio)):
        audio[i] ^= keybox[i & 0xFF]
    return audio


def decrypt(data: bytearray, ext: str) -> bytearray:
    """Decrypt NCM file.

    Returns:
        Decrypted audio data (no header stripping needed).
    """
    if len(data) < 8 or bytes(data[:8]) != _MAGIC:
        raise ValueError("Invalid NCM file: missing CTENFDAM magic")

    offset = 10  # skip magic (8) + gap (2)

    # Step 1: Read RC4 key
    raw_key, offset = _read_key_data(bytes(data), offset)

    # Step 2: Derive 256-byte XOR keybox
    keybox = rc4_keybox_256(raw_key)

    # Step 3: Read metadata
    metadata, offset = _read_metadata(bytes(data), offset)

    # Step 4: Skip album cover (5 + image_size bytes)
    # offset is now at gap_5 + image_size position
    # The gap and image reading is implicit in _read_audio

    # Step 5: Decrypt audio
    try:
        audio = _read_audio(bytes(data), offset, keybox)
    except (struct.error, IndexError):
        # Fallback: try from current offset
        audio = bytearray(data[offset:])
        for i in range(len(audio)):
            audio[i] ^= keybox[i & 0xFF]

    return audio


def get_metadata(data: bytearray) -> dict:
    """Extract metadata from NCM file (for reporting)."""
    if len(data) < 8 or bytes(data[:8]) != _MAGIC:
        return {}

    offset = 10
    try:
        _, offset = _read_key_data(bytes(data), offset)
        meta, _ = _read_metadata(bytes(data), offset)
        return meta
    except Exception:
        return {}
