"""
Metadata extraction and filename renaming for decrypted audio files.

Uses ffprobe (from ffmpeg) to extract song title and artist from audio
metadata, then renames the file to "Artist - Title.ext" format.

Pure enhancement — if ffprobe is unavailable or metadata is missing,
falls back gracefully by keeping the original filename.
"""

import os
import subprocess


def get_metadata(filepath: str) -> dict:
    """Extract TITLE and ARTIST from an audio file using ffprobe.

    Tries stream_tags first (used by OGG/Opus/Vorbis), then format_tags
    (used by FLAC). Both contain VorbisComment-style TAG:KEY=VALUE pairs.

    Args:
        filepath: Path to the audio file

    Returns:
        dict with keys 'title' and 'artist' (empty string if not found)
    """
    tags = {}

    for entry_type in ("stream_tags", "format_tags"):
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", entry_type,
                 "-of", "default=noprint_wrappers=1", filepath],
                capture_output=True, text=True, timeout=15,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # ffprobe not installed or hung
            return tags
        except Exception:
            continue

        for line in result.stdout.strip().split("\n"):
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key_short = key.replace("TAG:", "")
            if key_short in ("TITLE", "ARTIST"):
                tags[key_short.lower()] = value.strip()

    return tags


def sanitize_filename(name: str) -> str:
    """Replace characters that are invalid in filenames.

    Args:
        name: Raw filename string

    Returns:
        Safe filename string
    """
    replacements = {
        "/": "／",
        ":": "：",
        "*": "＊",
        "?": "？",
        '"': "＂",
        "<": "＜",
        ">": "＞",
        "|": "｜",
        "\\": "＼",
        "\x00": "",
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name.strip(" .")


def rename_by_metadata(filepath: str) -> str:
    """Rename an audio file to "Artist - Title.ext" using embedded metadata.

    If metadata is missing or ffprobe unavailable, the file is left as-is.

    Args:
        filepath: Absolute path to the audio file

    Returns:
        The final file path (new path if renamed, original if not)
    """
    dirname = os.path.dirname(filepath)
    basename = os.path.basename(filepath)
    name, ext = os.path.splitext(basename)

    meta = get_metadata(filepath)
    title = meta.get("title", "")
    artist = meta.get("artist", "")

    if not title:
        return filepath

    # Build new filename
    if artist and artist != title:
        new_name = f"{artist}-{title}"
    else:
        new_name = title

    new_name = sanitize_filename(new_name)
    new_path = os.path.join(dirname, f"{new_name}{ext}")

    # If name unchanged or target already exists, skip
    if new_path == filepath:
        return filepath
    if os.path.exists(new_path):
        return filepath

    try:
        os.rename(filepath, new_path)
        return new_path
    except OSError:
        return filepath


def rename_directory(directory: str, dry_run: bool = False) -> dict:
    """Batch-rename all audio files in a directory by their embedded metadata.

    Scans for common audio formats (.flac, .ogg, .mp3, .m4a, .wav, .ape, .wma),
    extracts TITLE and ARTIST from each file, and renames to "Title - Artist.ext".

    Handles duplicate names by appending a counter (e.g. "Song - Artist (2).flac").

    Args:
        directory: Path to the directory containing audio files
        dry_run: If True, only preview changes without renaming

    Returns:
        dict with keys: total (files scanned), renamed (count), skipped (count),
              duplicates (count of name collisions handled)
    """
    AUDIO_EXTS = {'.flac', '.ogg', '.mp3', '.m4a', '.wav', '.ape', '.wma', '.aac', '.wv'}

    files = []
    for f in sorted(os.listdir(directory)):
        fpath = os.path.join(directory, f)
        if not os.path.isfile(fpath):
            continue
        _, ext = os.path.splitext(f)
        if ext.lower() in AUDIO_EXTS:
            files.append(fpath)

    total = len(files)
    renamed = 0
    skipped = 0
    duplicates = 0
    seen = {}  # base_name → count

    for fpath in files:
        dirname = os.path.dirname(fpath)
        basename = os.path.basename(fpath)
        _, ext = os.path.splitext(basename)

        meta = get_metadata(fpath)
        title = meta.get("title", "")
        artist = meta.get("artist", "")

        if not title:
            if not dry_run:
                print(f"  SKIP  {basename}: 缺少歌曲元数据")
            skipped += 1
            continue

        if artist and artist != title:
            new_name = f"{title} - {artist}"
        else:
            new_name = title

        new_name = sanitize_filename(new_name)
        new_path_base = os.path.join(dirname, f"{new_name}{ext}")

        # Handle name collisions
        base_key = f"{new_name}{ext}"
        if base_key in seen:
            seen[base_key] += 1
            new_path = os.path.join(dirname, f"{new_name} ({seen[base_key]}){ext}")
            duplicates += 1
        else:
            seen[base_key] = 1
            new_path = new_path_base

        if new_path == fpath:
            skipped += 1
            continue

        if dry_run:
            print(f"  PREVIEW  {basename} → {os.path.basename(new_path)}")
            renamed += 1
        else:
            try:
                os.rename(fpath, new_path)
                print(f"  OK  {basename} → {os.path.basename(new_path)}")
                renamed += 1
            except OSError as e:
                print(f"  FAIL  {basename}: {e}")
                skipped += 1

    return {
        'total': total,
        'renamed': renamed,
        'skipped': skipped,
        'duplicates': duplicates,
    }
