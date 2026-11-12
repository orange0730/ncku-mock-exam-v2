"""分級提示：卡住時不用問 AI，跟評分程式要提示。

    python3 q1_ebnn/grade.py --hint              # 每個沒拿到分的項目給第 1 級提示（是哪一類錯）
    python3 q1_ebnn/grade.py --hint 2            # 第 2 級（指到哪裡）
    python3 q1_ebnn/grade.py --hint 3 --item bnn_hidden   # 第 3 級（接近答案），只看某一項

建議：先只要第 1 級，自己想 10 分鐘；還是卡住再要第 2 級。第 3 級留到真的想不出來。
每次使用都會記在 ci/results/hints.csv，CI 的輸出會顯示你用了幾次，方便你追蹤「不靠提示」的進度。

提示內容以編碼形式存在 common/hints.dat，避免隨手翻到答案；原文在 solutions/hints_src.py。
"""
import base64
import csv
import datetime as dt
import json
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'hints.dat'
LOG = ROOT / 'ci' / 'results' / 'hints.csv'
LEVEL_NAME = {1: '方向', 2: '位置', 3: '解法'}


def encode(table):
    return base64.b64encode(zlib.compress(json.dumps(table, ensure_ascii=False).encode('utf-8'), 9)).decode('ascii')


def load(question):
    if not DATA.exists():
        return []
    table = json.loads(zlib.decompress(base64.b64decode(DATA.read_text(encoding='ascii'))).decode('utf-8'))
    return table.get(question, [])


def match(entries, name):
    for entry in entries:
        if all(k in name for k in entry['keywords']):
            return entry
    return None


def add_args(parser):
    parser.add_argument('--hint', nargs='?', const=1, type=int, choices=(1, 2, 3), metavar='LEVEL',
                        help='對沒拿到分的項目顯示提示：1 = 方向、2 = 位置、3 = 解法（預設 1）')
    parser.add_argument('--item', default='', help='只看名稱包含這段文字的項目（搭配 --hint）')


def log_usage(question, item, level):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        new = not LOG.exists()
        with LOG.open('a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if new:
                w.writerow(['time', 'question', 'item', 'level'])
            w.writerow([dt.datetime.now().isoformat(timespec='seconds'), question, item, level])
    except OSError:
        pass


def usage_summary():
    """回傳 (總次數, 第 3 級次數)。"""
    if not LOG.exists():
        return 0, 0
    with LOG.open(encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    return len(rows), sum(1 for r in rows if r.get('level') == '3')


def maybe_show(result, question, args):
    if not getattr(args, 'hint', None) or getattr(args, 'json', False):
        return
    level = args.hint
    entries = load(question)
    failed = [r for r in result['rows'] if not r['passed'] and args.item in r['name']]
    print(f'\n========== 提示（第 {level} 級：{LEVEL_NAME[level]}）==========')
    if not failed:
        print('沒有符合的未通過項目。' if args.item else '全部項目都通過了，不需要提示。')
        return
    for row in failed:
        entry = match(entries, row['name'])
        print(f"\n▶ {row['name']}（{row['points']}/{row['max']}）")
        if '通過後才計算' in row['detail'] or row['detail'].startswith('先通過'):
            print('   （這一項要等前面的正確性項目通過才會計分，先處理那些）')
            continue
        if entry is None:
            print('   （這一項沒有準備提示）')
            continue
        for lv in range(1, level + 1):
            print(f'   [{lv}] {entry["levels"][lv - 1]}')
        log_usage(question, entry['keywords'][0], level)
    if level < 3:
        print(f'\n還是卡住？試試 --hint {level + 1}（可以加 --item 只看某一項）。')
    total, l3 = usage_summary()
    print(f'（這個 repo 累計看了 {total} 項提示，其中第 3 級 {l3} 項）')
