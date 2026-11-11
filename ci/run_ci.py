"""模擬考場的 GitLab CI：看最新一個 commit 的訊息開頭寫哪一題，就跑那一題的評分。

    git commit -m "Q2: 修好 header 解析"      -> 跑大題二
    git commit -m "[Q1] popcount 改 SWAR"     -> 跑大題一
    git commit -m "Q1 Q3 一起交"              -> 跑大題一與大題三
    git commit -m "ALL: 全部評一次"           -> 三題都跑
    git commit -m "整理註解"                  -> 沒有題號，不評分

安裝成 git hook 後每次 commit 都會自動執行（見 ci/install_hook.py）；
也可以手動執行：python3 ci/run_ci.py [--message "Q2: ..."]
結果存在 ci/results/（不進版本控制）。
"""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / 'ci' / 'results'
JOBS = {
    'Q1': ('大題一 eBNN 推論', ROOT / 'q1_ebnn' / 'grade.py'),
    'Q2': ('大題二 兩片板子平行推論', ROOT / 'q2_parallel' / 'grade.py'),
    'Q3': ('大題三 排序 / SHA-0 / CRC-32', ROOT / 'q3_algos' / 'grade.py'),
}
PREFIX = re.compile(r'^\s*(?:\[?\s*(?:Q[1-3]|ALL)(?![0-9A-Za-z_])\s*\]?[\s:,，、]*)+', re.IGNORECASE)


def parse_questions(message):
    """只看訊息「開頭」的題號，跟考場一樣：題號寫在中間不算。"""
    first_line = message.strip().splitlines()[0] if message.strip() else ''
    m = PREFIX.match(first_line)
    if not m:
        return []
    found = re.findall(r'Q[1-3]|ALL', m.group(0), re.IGNORECASE)
    if any(f.upper() == 'ALL' for f in found):
        return list(JOBS)
    return sorted({f.upper() for f in found})


def git(*args):
    proc = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return proc.stdout.strip() if proc.returncode == 0 else ''


def main():
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--message', help='不讀 git，直接用這段 commit 訊息')
    args = parser.parse_args()

    message = args.message if args.message is not None else git('log', '-1', '--format=%B')
    sha = git('rev-parse', '--short', 'HEAD') or 'nocommit'
    questions = parse_questions(message)
    first = message.strip().splitlines()[0] if message.strip() else '(空訊息)'
    print(f'\n┌─ CI pipeline  commit {sha}：{first}')
    if not questions:
        print('└─ commit 訊息開頭沒有題號（Q1 / Q2 / Q3 / ALL），這次不評分。')
        return 0

    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    summary = []
    for q in questions:
        title, script = JOBS[q]
        print(f'│\n├─ job grade_{q.lower()}：{title}')
        proc = subprocess.run([sys.executable, str(script), '--json'], cwd=script.parent,
                              capture_output=True, text=True, encoding='utf-8', errors='replace')
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            print('│  評分程式本身出錯：')
            for line in (proc.stderr or proc.stdout).strip().splitlines()[-15:]:
                print(f'│    {line}')
            summary.append((q, None))
            continue
        (RESULTS / f'{stamp}-{sha}-{q}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                                         encoding='utf-8')
        for row in result['rows']:
            mark = '✔' if row['passed'] else '✘'
            print(f"│  {mark} {row['points']:2}/{row['max']:<2} {row['name']}")
            if row['detail']:
                print(f"│        {row['detail'].splitlines()[0][:150]}")
        print(f"│  ── {q} 得分 {result['total']}/{result['max']}")
        summary.append((q, result['total']))
    line = '  '.join(f'{q}={"ERR" if s is None else s}' for q, s in summary)
    print(f'└─ pipeline 完成：{line}（詳細結果：ci/results/{stamp}-{sha}-*.json）\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
