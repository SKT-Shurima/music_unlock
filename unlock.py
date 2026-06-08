#!/usr/bin/env python3
"""
music-tool — 加密音乐解密引擎(纯解密,不扫描/不分类)。

用法:
  python3 unlock.py decrypt <输入目录> <输出目录> [选项]
  python3 unlock.py rename <目录> [--dry-run]

选项:
  --failed-dir <dir>     失败文件拷贝到此目录
  --cookie <str>         QQ 音乐登录 cookie(解密 musicex/QMCv2 新格式必需)
  --cookie-file <path>   从文件读取 cookie
  --qq-db <path>         指定本地 qqmusic.sqlite(O 前缀文件反查 songmid;默认自动检测)
  --help

如何获取 cookie:浏览器登录 https://y.qq.com → F12 → Application → Cookies,
复制 qqmusic_key 的值(或整行 cookie)。仅用于解密你自己账号可访问的音乐。
"""

import sys
import os

# Add parent to path for package imports
sys.path.insert(0, os.path.dirname(__file__))

from unlock_lib import engine


def cmd_decrypt(args):
    """Decrypt encrypted music files."""
    if len(args) < 2:
        print("用法: unlock.py decrypt <输入目录> <输出目录> "
              "[--failed-dir <dir>] [--cookie <str>] [--cookie-file <path>] [--qq-db <path>]")
        sys.exit(1)

    input_dir = args[0]
    output_dir = args[1]
    failed_dir = None
    cookie = None
    qq_db = None

    i = 2
    while i < len(args):
        if args[i] == '--failed-dir' and i + 1 < len(args):
            failed_dir = args[i + 1]; i += 2
        elif args[i] == '--cookie' and i + 1 < len(args):
            cookie = args[i + 1]; i += 2
        elif args[i] == '--cookie-file' and i + 1 < len(args):
            with open(args[i + 1]) as f:
                cookie = f.read().strip()
            i += 2
        elif args[i] == '--qq-db' and i + 1 < len(args):
            qq_db = args[i + 1]; i += 2
        else:
            i += 1

    # 环境变量回退
    if not cookie:
        cookie = os.environ.get('QQMUSIC_COOKIE') or None

    # 准备本地 QQ 数据库(O 前缀文件反查 songmid;缺失则降级)
    localdb = None
    if cookie:
        try:
            from unlock_lib import qq_api
            localdb = qq_api.LocalDB(qq_db)
            if localdb.available:
                print(f"  本地 QQ 音乐库: {len(localdb.by_media)} 首可反查 songmid")
        except Exception:
            localdb = None

    if cookie:
        print("  已提供 cookie:支持解密 QQ musicex/QMCv2 新格式")
    else:
        print("  未提供 cookie:仅能解密内嵌密钥格式(其他平台 + QQ 旧格式)")

    print(f"解密: {input_dir} -> {output_dir}")
    result = engine.decrypt_directory(input_dir, output_dir, failed_dir,
                                      cookie=cookie, localdb=localdb)
    print(f"\n完成: 成功 {result['success']}, 失败 {result['failed']} "
          f"(共 {result['total']})")


def cmd_rename(args):
    """Batch-rename audio files by embedded metadata (Title - Artist)."""
    if len(args) < 1:
        print("用法: unlock.py rename <目录> [--dry-run]")
        sys.exit(1)

    directory = args[0]
    dry_run = '--dry-run' in args

    if not os.path.isdir(directory):
        print(f"错误: 目录不存在: {directory}")
        sys.exit(1)

    from unlock_lib import metadata

    if dry_run:
        print(f"预览模式: {directory}\n")

    result = metadata.rename_directory(directory, dry_run=dry_run)

    print(f"\n完成: 扫描 {result['total']} 个文件, "
          f"重命名 {result['renamed']} 个, "
          f"跳过 {result['skipped']} 个"
          + (f", 重名处理 {result['duplicates']} 个" if result['duplicates'] else ""))


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
    elif cmd == 'rename':
        cmd_rename(args)
    elif cmd in ('--help', '-h', 'help'):
        cmd_help()
    else:
        print(f"未知命令: {cmd}")
        cmd_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
