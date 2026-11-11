"""一次評三個大題，印出總分（滿分 300）。

    python3 grade_all.py            # 評你的作答
    python3 grade_all.py --detail   # 連沒拿到分的項目一起列出
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUESTIONS = [
    ('大題一 eBNN 推論', HERE / 'q1_ebnn' / 'grade.py'),
    ('大題二 兩片板子平行推論', HERE / 'q2_parallel' / 'grade.py'),
    ('大題三 排序 / SHA-0 / CRC-32', HERE / 'q3_algos' / 'grade.py'),
]


def run(script, extra=()):
    proc = subprocess.run([sys.executable, str(script), '--json', *extra], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', cwd=str(script.parent))
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return dict(total=0, max=100, rows=[], error=(proc.stderr or proc.stdout).strip()[-800:])


def main():
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--detail', action='store_true')
    args = parser.parse_args()
    grand = 0
    for title, script in QUESTIONS:
        result = run(script)
        grand += result['total']
        print(f"{title:<24} {result['total']:3}/{result['max']}")
        if result.get('error'):
            print(f"    評分程式錯誤：{result['error']}")
        by_cat = {}
        for row in result['rows']:
            got, mx = by_cat.get(row['category'], (0, 0))
            by_cat[row['category']] = (got + row['points'], mx + row['max'])
        for cat, (got, mx) in by_cat.items():
            print(f'    {cat:<24} {got:3}/{mx}')
        if args.detail:
            for row in result['rows']:
                if not row['passed']:
                    print(f"      ✗ {row['name']}：{row['detail'].splitlines()[0] if row['detail'] else ''}")
    print(f'\n總分 TOTAL: {grand}/300')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
