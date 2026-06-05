#!/usr/bin/env python3
"""
music-tool — Encrypted music decryption engine.

Usage:
  python3 unlock.py decrypt <input_dir> <output_dir> [--failed-dir <dir>]
  python3 unlock.py classify <audio_dir> <music_lib>
  python3 unlock.py check <music_dir> [--anomaly-dir <dir>]
  python3 unlock.py all <input_dir> [--music-lib <dir>]
  python3 unlock.py --help
"""

import sys
import os

# Add parent to path for package imports
sys.path.insert(0, os.path.dirname(__file__))

from unlock_lib import engine


def cmd_decrypt(args):
    """Decrypt encrypted music files."""
    if len(args) < 2:
        print("Usage: unlock.py decrypt <input_dir> <output_dir> [--failed-dir <dir>]")
        sys.exit(1)

    input_dir = args[0]
    output_dir = args[1]
    failed_dir = None

    i = 2
    while i < len(args):
        if args[i] == '--failed-dir' and i + 1 < len(args):
            failed_dir = args[i + 1]
            i += 2
        else:
            i += 1

    print(f"Decrypting: {input_dir} -> {output_dir}")
    result = engine.decrypt_directory(input_dir, output_dir, failed_dir)
    print(f"\nDone: {result['success']} succeeded, {result['failed']} failed (out of {result['total']})")


def cmd_help():
    print(__doc__)


def main():
    if len(sys.argv) < 2:
        cmd_help()
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == 'decrypt':
        cmd_decrypt(args)
    elif cmd in ('--help', '-h', 'help'):
        cmd_help()
    else:
        print(f"Unknown command: {cmd}")
        cmd_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
