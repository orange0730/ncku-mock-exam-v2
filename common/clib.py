"""把 C 原始檔編譯成共享函式庫（.so / .dll）並用 ctypes 載入。

    lib, warnings = build_and_load('bnn', ['q1_ebnn/bnn.c'], include_dirs=[...])

以原始碼內容與編譯參數的雜湊值當快取鍵，內容沒變就不重新編譯。
編譯器：環境變數 CC，否則依序找 gcc / cc / clang。
"""
import ctypes
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / 'build'
BASE_FLAGS = ['-std=gnu11', '-O2', '-Wall', '-Wextra', '-fPIC', '-shared', '-pthread']

BLOCKED_HELP = ('作業系統拒絕載入剛編譯出來的函式庫（Windows 的 Smart App Control 常見）。'
                '請在 Linux（例如樹莓派）、WSL 或 Docker 裡評分。')


class BuildError(Exception):
    pass


def find_cc():
    for cand in (os.environ.get('CC'), 'gcc', 'cc', 'clang'):
        if cand and shutil.which(cand):
            return cand
    return None


def build_and_load(name, sources, include_dirs=(), extra_flags=()):
    """回傳 (ctypes.CDLL, warnings)。失敗時丟 BuildError（訊息可直接給學生看）。"""
    cc = find_cc()
    if cc is None:
        raise BuildError('找不到 C 編譯器（gcc / cc / clang），請設定 CC 環境變數')
    sources = [Path(s).resolve() for s in sources]
    for s in sources:
        if not s.exists():
            raise BuildError(f'找不到原始檔：{s}')
    flags = BASE_FLAGS + [f'-I{Path(d).resolve()}' for d in include_dirs] + list(extra_flags)
    digest = hashlib.sha256()
    for s in sources:
        digest.update(s.read_bytes())
    for d in include_dirs:
        for h in sorted(Path(d).glob('*.h')):
            digest.update(h.read_bytes())
    digest.update(' '.join(flags).encode())
    suffix = '.dll' if os.name == 'nt' else '.so'
    BUILD.mkdir(exist_ok=True)
    out = BUILD / f'{name}-{digest.hexdigest()[:12]}{suffix}'
    log = out.with_suffix('.log')
    if not out.exists():
        cmd = [cc, *flags, '-o', str(out), *map(str, sources)]
        if sys.platform != 'win32':
            cmd.append('-lm')
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if proc.returncode != 0:
            raise BuildError('編譯失敗：\n' + proc.stderr.strip()[:1500])
        log.write_text(proc.stderr, encoding='utf-8')
    warnings = [ln.strip() for ln in log.read_text(encoding='utf-8').splitlines() if 'warning' in ln] \
        if log.exists() else []
    try:
        lib = ctypes.CDLL(str(out))
    except OSError as error:
        if getattr(error, 'winerror', None) == 4551:
            raise BuildError(BLOCKED_HELP) from error
        raise BuildError(f'載入函式庫失敗：{error}') from error
    return lib, warnings
