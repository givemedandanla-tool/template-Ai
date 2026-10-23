"""Render a project GUI agent task for Codex; never dispatch or change model settings."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

from tooling_extensions import inside, verify_extensions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--role')
    parser.add_argument('--goal', default='Review the current GUI implementation against the approved contract.')
    parser.add_argument('--base')
    parser.add_argument('--head')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    manifest = verify_extensions(here)
    roles = manifest['agent_roles']
    if args.list:
        for role, path in roles.items():
            print(role + ': ' + path)
        return
    if args.role not in roles:
        parser.error('Select one of the roles shown by --list')
    for value in [args.base, args.head]:
        if value is not None and not re.fullmatch(r'[0-9a-f]{7,40}', value):
            parser.error('Commit references must be hexadecimal commit IDs')
    print(inside(here, roles[args.role]).read_text(encoding='utf-8'))
    print('\n本次任務：' + args.goal)
    if args.base or args.head:
        print('評估提交：base=' + (args.base or 'not provided') + ', head=' + (args.head or 'working tree'))
    print('\n僅在使用者已授權協作時由主代理透過實際 collaboration 工具指派。'
          '本腳本不啟動代理、不安裝模型、不改平台設定；回報須指明實際執行者與來源。')


if __name__ == '__main__':
    main()
