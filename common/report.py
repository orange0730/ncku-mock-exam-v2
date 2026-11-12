"""評分程式共用的小工具：逐項紀錄、印出報告、跑隔離的測試。"""
import json
import multiprocessing as mp
import sys


class Rows:
    def __init__(self, question):
        self.question = question
        self.rows = []

    def add(self, category, name, points, maximum, detail=''):
        points = max(0, min(points, maximum))
        self.rows.append(dict(category=category, name=name, points=points, max=maximum,
                              passed=points == maximum, detail='' if points == maximum else detail))

    def fail_all(self, items, detail):
        for category, name, maximum in items:
            self.add(category, name, 0, maximum, detail)

    def result(self, **extra):
        return dict(question=self.question, rows=self.rows, total=sum(r['points'] for r in self.rows),
                    max=sum(r['max'] for r in self.rows), **extra)


def print_report(result, label):
    current = None
    for row in result['rows']:
        if row['category'] != current:
            current = row['category']
            print(f'\n[{current}]')
        print(f"  {row['points']:2}/{row['max']:<2} {'PASS' if row['passed'] else 'FAIL'}  {row['name']}")
        if row['detail']:
            print(f"           -> {row['detail']}")
    for note in result.get('notes', []):
        print(f'\n（{note}）')
    print(f"\n{label} TOTAL: {result['total']}/{result['max']}")


def emit(result, label, as_json):
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding='utf-8')
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_report(result, label)


def _child(conn, fn, args):
    try:
        conn.send(('ok', fn(*args)))
    except BaseException as error:  # noqa: BLE001
        conn.send(('err', f'{type(error).__name__}: {error}'))
    finally:
        conn.close()


def isolated(fn, *args, timeout=60):
    """在子 process 裡執行 fn(*args)。C 程式當掉（segfault）或卡死都不會拖垮評分程式。

    回傳 (status, value)：status 是 'ok'、'err'、'crash' 或 'timeout'。
    fn 必須是模組層級的函式（可被 pickle）。
    """
    ctx = mp.get_context('spawn')
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(child, fn, args))
    proc.start()
    child.close()
    if parent.poll(timeout):
        try:
            status, value = parent.recv()
        except EOFError:
            status, value = 'crash', None
    else:
        status, value = 'timeout', None
    proc.join(1)
    if proc.is_alive():
        proc.kill()
        proc.join()
    if status == 'crash' or (status != 'timeout' and proc.exitcode not in (0, None) and status != 'ok'):
        hint = ('SIGSEGV：讀寫了不該碰的記憶體，最常見是陣列越界，例如迴圈多跑一次、n = 0 時 n - 1 變成極大值'
                if proc.exitcode == -11 else
                'SIGABRT：程式自己中止（例如搬運引擎拒絕了不合法的工作）' if proc.exitcode == -6 else
                '可能是存取錯誤記憶體或無窮遞迴')
        return 'crash', f'程式當掉了（exit code {proc.exitcode}，{hint}）'
    if status == 'timeout':
        return 'timeout', f'超過 {timeout} 秒沒有結束（無窮迴圈？演算法太慢？）'
    return status, value
