"""
KWM format handler (.kwm files).

Kuwo Music encrypted format. File structure:
  - 16 bytes: magic header "yeelion-kuwo-tme" or variant
  - 8 bytes:  reserved
  - 8 bytes:  file key (used to derive XOR mask)
  - padding to offset 0x400 (1024)
  - then:     audio data XOR'd with 32-byte repeating mask

Key derivation:
  1. Read 8 bytes at offset 0x18 as little-endian uint64
  2. Convert to decimal string
  3. Pad/trim to exactly 32 characters by repeating
  4. XOR each char with corresponding char of fixed 32-char string
"""

import struct

# Fixed 32-character mask base string
_MASK_BASE = 'MoOtOiTvINGwd2E6n0E1i7L5t2IoOoNk'

# Magic headers for KWM detection
_MAGIC_1 = b'yeelion-kuwo-tme'
_MAGIC_2 = b'yeelion-kuwo\x00\x00\x00\x00'


def detect(ext: str) -> bool:
    """Check if this is a KWM format."""
    return ext.lower() == 'kwm'


def _derive_mask(file_key_bytes: bytes) -> bytes:
    """Derive 32-byte XOR mask from 8-byte file key.

    Algorithm:
      1. Interpret 8 bytes as little-endian uint64
      2. Convert to decimal string
      3. Repeat/pad to exactly 32 characters
      4. XOR each character with _MASK_BASE
    """
    key_int = struct.unpack('<Q', file_key_bytes)[0]
    key_str = str(key_int)

    # Pad or trim to exactly 32 chars
    if len(key_str) < 32:
        key_str = (key_str * (32 // len(key_str) + 1))[:32]
    else:
        key_str = key_str[:32]

    mask = bytearray(32)
    for i in range(32):
        mask[i] = ord(_MASK_BASE[i]) ^ ord(key_str[i])

    return bytes(mask)


def decrypt(data: bytearray, ext: str) -> bytearray:
    """Decrypt KWM encrypted data.

    Returns:
        Decrypted audio data (header stripped).
    """
    if len(data) < 0x400:
        raise ValueError("KWM file too small (min 1024 bytes)")

    # Verify magic header
    header = bytes(data[:16])
    if header != _MAGIC_1 and header != _MAGIC_2:
        raise ValueError(f"Invalid KWM magic: {header!r}")

    # Extract file key (8 bytes at offset 0x18)
    file_key = bytes(data[0x18:0x20])

    # Derive XOR mask
    mask = _derive_mask(file_key)

    # Decrypt audio data (from offset 0x400)
    audio = data[0x400:]
    for i in range(len(audio)):
        audio[i] ^= mask[i % 32]

    return audio
