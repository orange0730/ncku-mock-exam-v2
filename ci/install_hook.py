"""把 ci/run_ci.py 裝成 git 的 post-commit hook：之後每次 commit 都會自動評分。

    python3 ci/install_hook.py            # 安裝
    python3 ci/install_hook.py --remove   # 移除

（hook 存在 .git/hooks/ 裡，不會跟著 git clone 走，所以換電腦要重新安裝一次。）
"""
import os
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK_BODY = """#!/bin/sh
# 由 ci/install_hook.py 安裝：模擬考場的 GitLab CI
python3 "$(git rev-parse --show-toplevel)/ci/run_ci.py" || python "$(git rev-parse --show-toplevel)/ci/run_ci.py"
"""


def main():
    git_dir = subprocess.run(['git', 'rev-parse', '--git-dir'], cwd=ROOT, capture_output=True, text=True)
    if git_dir.returncode != 0:
        print('這個資料夾還不是 git repository。先執行：git init')
        return 1
    hook = (ROOT / git_dir.stdout.strip() / 'hooks' / 'post-commit').resolve()
    if '--remove' in sys.argv:
        if hook.exists():
            hook.unlink()
        print('已移除 post-commit hook')
        return 0
    hook.parent.mkdir(parents=True, exist_ok=True)
    if hook.exists() and 'run_ci.py' not in hook.read_text(encoding='utf-8', errors='replace'):
        print(f'{hook} 已經有別的內容，為了安全不覆蓋。請手動處理。')
        return 1
    hook.write_text(HOOK_BODY, encoding='utf-8', newline='\n')
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f'已安裝：{hook}')
    print('之後 commit 訊息以 Q1 / Q2 / Q3 / ALL 開頭時，就會自動跑對應的評分。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
