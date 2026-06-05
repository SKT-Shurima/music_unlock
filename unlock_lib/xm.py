"""
XM format handler (.xm files).

Xiami Music encrypted format. File structure:
  - 4 bytes: magic "ifmt"
  - 4 bytes: type text (" WAV", "FLAC", " MP3", " A4M")
  - 4 bytes: unknown
  - 3 bytes: data offset (little-endian)
  - 1 byte:  XOR key
  - 1 byte:  unknown
  - then:    encrypted audio data

Decryption: for each byte after data_offset:
    plaintext = (ciphertext - key) XOR 0xFF
"""

import struct


def detect(ext: str) -> bool:
    """Check if this is an XM format."""
    return ext.lower() == 'xm'


def _get_output_extension(type_text: str) -> str:
    """Map XM type text to file extension."""
    mapping = {
        ' WAV': 'wav',
        'FLAC': 'flac',
        ' MP3': 'mp3',
        ' A4M': 'm4a',
    }
    return mapping.get(type_text, 'mp3')


def decrypt(data: bytearray, ext: str) -> bytearray:
    """Decrypt XM encrypted data.

    Returns:
        Decrypted audio data (header stripped, just raw audio).
    """
    if len(data) < 16:
        raise ValueError("XM file too small (min 16 bytes)")

    # Parse header
    magic = data[0:4]
    if magic != b'ifmt':
        raise ValueError(f"Invalid XM magic: {magic!r}")

    type_text = data[4:8].decode('ascii', errors='replace')
    key = data[0x0F]  # offset 15

    # Data offset (3 bytes little-endian at offset 12-14)
    data_offset = data[0x0C] | (data[0x0D] << 8) | (data[0x0E] << 16)

    # Decrypt: skip header, decrypt from data_offset
    audio = data[data_offset:]
    for i in range(len(audio)):
        audio[i] = (audio[i] - key) & 0xFF
        audio[i] ^= 0xFF

    # Return just the decrypted audio (caller handles output extension)
    return audio


def get_output_ext(data: bytearray) -> str:
    """Determine output file extension from XM header."""
    if len(data) >= 8:
        type_text = data[4:8].decode('ascii', errors='replace')
        return _get_output_extension(type_text)
    return 'mp3'
