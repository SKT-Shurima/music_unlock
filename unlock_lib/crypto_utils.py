"""
Cryptographic utilities for music decryption.

Provides AES-128-ECB decryption and RC4 stream cipher.
Uses openssl CLI (available on macOS/Linux by default) for AES,
falling back to pycryptodome or pure Python as needed.
"""

import subprocess
import os
import tempfile

# ============================================================
# AES-128-ECB (via openssl CLI — zero Python dependencies)
# ============================================================

def aes128_ecb_decrypt(ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt data with AES-128-ECB (PKCS7 padding removed).

    Uses the system openssl command, which is available by default
    on macOS and most Linux distributions.
    """
    if len(key) != 16:
        raise ValueError(f"AES-128 requires 16-byte key, got {len(key)}")

    # Write input to temp file
    tmpdir = tempfile.mkdtemp(prefix='mt-aes-')
    try:
        in_path = os.path.join(tmpdir, 'in.bin')
        out_path = os.path.join(tmpdir, 'out.bin')

        with open(in_path, 'wb') as f:
            f.write(ciphertext)

        key_hex = key.hex()
        result = subprocess.run(
            ['openssl', 'enc', '-aes-128-ecb', '-d', '-K', key_hex,
             '-nopad', '-in', in_path, '-out', out_path],
            capture_output=True, text=True, timeout=10
        )

        if result.returncode != 0:
            raise RuntimeError(f"openssl AES decrypt failed: {result.stderr}")

        with open(out_path, 'rb') as f:
            plaintext = f.read()

        # Remove PKCS7 padding
        pad_len = plaintext[-1]
        if pad_len < 1 or pad_len > 16:
            raise ValueError(f"Invalid PKCS7 padding: {pad_len}")
        return plaintext[:-pad_len]

    finally:
        for p in (os.path.join(tmpdir, 'in.bin'), os.path.join(tmpdir, 'out.bin')):
            try:
                os.unlink(p)
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass


# ============================================================
# RC4 stream cipher (pure Python)
# ============================================================

def rc4_init(key: bytes) -> bytearray:
    """Initialize RC4 state (S-box) from key."""
    sbox = bytearray(range(256))
    j = 0
    key_len = len(key)
    for i in range(256):
        j = (j + sbox[i] + key[i % key_len]) & 0xFF
        sbox[i], sbox[j] = sbox[j], sbox[i]
    return sbox


def rc4_crypt(data: bytes, key: bytes) -> bytes:
    """Encrypt/decrypt data with RC4 (symmetric)."""
    sbox = rc4_init(key)
    result = bytearray(len(data))
    i = j = 0
    for idx, byte in enumerate(data):
        i = (i + 1) & 0xFF
        si = sbox[i]
        j = (j + si) & 0xFF
        sj = sbox[j]
        sbox[i], sbox[j] = sj, si
        k = sbox[(si + sj) & 0xFF]
        result[idx] = byte ^ k
    return bytes(result)


def rc4_keybox_256(key_data: bytes) -> bytes:
    """NCM-style: derive a fixed 256-byte XOR keybox from key_data.

    This is NOT standard RC4 PRGA. The NCM algorithm:
    1. Standard RC4-KSA: shuffle a 256-byte identity box using the key
    2. Static mapping: transform the shuffled box into a 256-byte output

    The result is a fixed 256-byte lookup table that repeats cyclically
    over the audio data (audio[cur] ^= keybox[cur & 0xFF]).
    """
    # Step 1: Standard RC4 KSA (key scheduling)
    sbox = bytearray(range(256))
    j = 0
    key_len = len(key_data)
    for i in range(256):
        j = (sbox[i] + j + key_data[i % key_len]) & 0xFF
        sbox[i], sbox[j] = sbox[j], sbox[i]

    # Step 2: Static transformation (NOT standard RC4 PRGA!)
    # For each output position idx: use (idx+1) as the lookup index,
    # compute two table lookups, and derive the output byte.
    keybox = bytearray(256)
    for idx in range(256):
        i = (idx + 1) & 0xFF
        si = sbox[i]
        sj = sbox[(i + si) & 0xFF]
        keybox[idx] = sbox[(si + sj) & 0xFF]

    return bytes(keybox)


# ============================================================
# Simple XOR helpers
# ============================================================

def xor_bytes(data: bytearray, key: bytes) -> bytearray:
    """In-place XOR of data with repeating key."""
    key_len = len(key)
    for i in range(len(data)):
        data[i] ^= key[i % key_len]
    return data


def xor_byte(data: bytearray, key: int) -> bytearray:
    """In-place XOR of data with a single byte value."""
    for i in range(len(data)):
        data[i] ^= key
    return data
