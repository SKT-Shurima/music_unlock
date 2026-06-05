"""
TM format handler (.tm0 / .tm2 / .tm3 / .tm6 files).

QQ Music iOS legacy format. The "encryption" is just corrupted first 8 bytes
of an M4A file. Restore the standard M4A ftyp box header.
"""

# Standard M4A ftyp box header (8 bytes)
_M4A_HEADER = bytes([0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70])


def detect(ext: str) -> bool:
    """Check if this is a TM format."""
    return ext.lower() in ('tm0', 'tm2', 'tm3', 'tm6')


def decrypt(data: bytearray, ext: str) -> bytearray:
    """Fix the first 8 bytes to restore valid M4A header."""
    if len(data) >= 8:
        data[:8] = _M4A_HEADER
    return data
