"""
Cache format handler (.uc / .uc! files).

These are QQ Music / NetEase streaming cache files encrypted with a simple
single-byte XOR cipher. The entire file is XOR'd with 0xA3 (163).
"""

from unlock_lib import audio_utils


def detect(ext: str) -> bool:
    """Check if this is a cache format."""
    return ext.lower() in ('uc', 'uc!')


def decrypt(data: bytearray, ext: str) -> bytearray:
    """Decrypt cache data by XORing every byte with 0xA3."""
    for i in range(len(data)):
        data[i] ^= 0xA3
    return data
