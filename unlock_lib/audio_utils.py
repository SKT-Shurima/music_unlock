"""
Audio format detection via magic bytes and header analysis.
Zero external dependencies.
"""

# Magic byte signatures for common audio formats
_SIGNATURES = [
    # (signature, offset, extension, mime_type)
    (b'fLaC',            0, 'flac', 'audio/flac'),
    (b'ID3',             0, 'mp3',  'audio/mpeg'),
    (b'\xff\xfb',        0, 'mp3',  'audio/mpeg'),   # MPEG frame header
    (b'\xff\xf3',        0, 'mp3',  'audio/mpeg'),
    (b'\xff\xf2',        0, 'mp3',  'audio/mpeg'),
    (b'OggS',            0, 'ogg',  'audio/ogg'),
    (b'RIFF',            0, 'wav',  'audio/wav'),    # Need to check for WAVE
    (b'ftyp',            4, 'm4a',  'audio/mp4'),     # ISO BMFF
    (b'\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c', 0, 'wma', 'audio/x-ms-wma'),
    (b'\xff\xf1',        0, 'aac',  'audio/aac'),
    (b'FRM8',            0, 'dff',  'audio/dff'),     # DSDIFF
    (b'MAC ',            0, 'ape',  'audio/ape'),     # Monkey's Audio
]

def sniff_extension(data: bytes, default_ext: str = 'mp3') -> str:
    """Detect audio format from magic bytes.

    Args:
        data: Beginning of audio file (at least 16 bytes)
        default_ext: Fallback extension if detection fails

    Returns:
        File extension without dot (e.g. 'flac', 'mp3')
    """
    for sig, offset, ext, _ in _SIGNATURES:
        if len(data) >= offset + len(sig):
            if data[offset:offset + len(sig)] == sig:
                # Special case: RIFF needs to verify it's WAVE not AVI
                if ext == 'wav':
                    if len(data) >= 12 and data[8:12] == b'WAVE':
                        return ext
                    continue
                return ext
    return default_ext


def get_mime_type(ext: str) -> str:
    """Get MIME type from file extension."""
    for _, _, e, mime in _SIGNATURES:
        if e == ext:
            return mime
    return 'application/octet-stream'


# Known encrypted format extensions and their output formats
ENCRYPTED_EXTENSIONS = {
    # QQ Music
    'mflac':   'flac',   'mgg':     'ogg',    'mggl':    'ogg',
    'mgg0':    'ogg',    'mgg1':    'ogg',    'mflac0':  'flac',
    'mflach':  'flac',   'mmp4':    'm4a',
    'qmcflac': 'flac',   'qmcogg':  'ogg',
    'qmc0':    'mp3',    'qmc2':    'ogg',    'qmc3':    'mp3',
    'qmc4':    'ogg',    'qmc6':    'ogg',    'qmc8':    'ogg',
    'bkcmp3':  'mp3',    'bkcflac': 'flac',   'bkcwav':  'wav',
    'bkcogg':  'ogg',    'bkcwma':  'wma',    'bkcape':  'ape',
    'bkcm4a':  'm4a',    'tkm':     'm4a',
    # QQ Music cache (hex-encoded extensions from cache naming)
    '666c6163': 'flac',  '6d7033':  'mp3',   '6f6767':  'ogg',
    '6d3461':  'm4a',    '776176':  'wav',
    'uc':      'mp3',    'uc!':     'mp3',
    # QQ Music old (TM)
    'tm0':     'm4a',    'tm2':     'm4a',    'tm3':     'm4a',
    'tm6':     'm4a',
    # NetEase Cloud Music
    'ncm':     'mp3',
    # Kugou
    'kgm':     'mp3',    'kgma':    'mp3',    'vpr':     'mp3',
    # Kuwo
    'kwm':     'mp3',
    # Xiami
    'xm':      'mp3',
    # Migu
    'mg3d':    'wav',
    # Ximalaya
    'x2m':     'm4a',    'x3m':     'm4a',
}

ENCRYPTED_EXT_SET = set(ENCRYPTED_EXTENSIONS.keys())


def is_encrypted_ext(ext: str) -> bool:
    """Check if a file extension is a known encrypted format."""
    return ext.lower().lstrip('.') in ENCRYPTED_EXT_SET


def expected_output_ext(enc_ext: str) -> str:
    """Get the expected output extension for an encrypted format."""
    return ENCRYPTED_EXTENSIONS.get(enc_ext.lower().lstrip('.'), 'mp3')
