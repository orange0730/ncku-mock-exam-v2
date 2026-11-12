"""大題三評分程式：三片板子跑排序 / SHA-0 / CRC-32（C 演算法 55 + dispatcher 30 + 效能 15 = 100）。

    python3 grade.py
    python3 grade.py --algos path/algos.c --dispatcher path/dispatcher.py
    python3 grade.py --json

dispatcher 的測試使用「參考韌體」的模擬板子，所以 Part B / C 不受你 C 實作對錯的影響。
"""
import argparse
import ctypes
import importlib.util
import os
import random
import struct
import sys
import tempfile
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COMMON = ROOT / 'common'
for p in (COMMON, HERE):
    sys.path.insert(0, str(p))

import algos_ref  # noqa: E402
from clib import BuildError, build_and_load  # noqa: E402
from fakeros import fresh_graph, use_fake_ros  # noqa: E402
from guard import guarded, guarded_bytes  # noqa: E402
from report import Rows, emit, isolated  # noqa: E402

ERROR_FILE = Path(tempfile.gettempdir()) / f'ncku_engine_error_{os.getpid()}.txt'


# ====================================================================== Part A：C
def _lib(source):
    lib, _ = build_and_load('algos', [source, HERE / 'engine.c', HERE / 'bench.c'], include_dirs=[HERE])
    lib.sort_u32.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t]
    lib.bench_qsort_u32.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t]
    lib.sha0.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_uint8)]
    for name in ('crc32_sw', 'crc32_dma', 'bench_crc32_bitwise'):
        getattr(lib, name).restype = ctypes.c_uint32
        getattr(lib, name).argtypes = [ctypes.c_char_p, ctypes.c_size_t]
    lib.engine_stat_claimed_now.restype = ctypes.c_int
    lib.engine_stat_sniff_enabled.restype = ctypes.c_bool
    lib.engine_stat_sniffed_bytes.restype = ctypes.c_ulonglong
    return lib


def c_part(test, source):
    lib = _lib(source)
    rng = random.Random(3)
    if test == 'sort':
        cases = [[], [5], [2, 1], [0xFFFFFFFF, 0, 0x80000000, 1], list(range(50)), list(range(50, 0, -1)), [7] * 30]
        cases += [[rng.choice((0, 1, 0xFFFFFFFF, rng.getrandbits(32), rng.randrange(10))) for _ in range(rng.randint(0, 600))]
                  for _ in range(60)]
        for case in cases:
            arr = guarded(ctypes.c_uint32, len(case), case)     # 陣列後面緊貼守護頁
            lib.sort_u32(arr, len(case))
            if list(arr) != sorted(case):
                head = case[:8]
                return f'n={len(case)}（開頭 {head}…）排序結果不正確'
        return None
    if test == 'sort_perf':
        n = 1_000_000
        data = [rng.getrandbits(32) for _ in range(n)]
        a = (ctypes.c_uint32 * n)(*data)
        b = (ctypes.c_uint32 * n)(*data)
        t0 = time.perf_counter()
        lib.sort_u32(a, n)
        t1 = time.perf_counter()
        lib.bench_qsort_u32(b, n)
        t2 = time.perf_counter()
        if list(a) != list(b):
            return ('wrong', '100 萬筆排序結果不正確')
        return ('ratio', (t1 - t0) / (t2 - t1), t1 - t0, t2 - t1)
    if test == 'sha0':
        lengths = [0, 1, 3, 55, 56, 57, 63, 64, 65, 119, 120, 127, 128, 1000] + [rng.randint(0, 300) for _ in range(150)]
        for n in lengths:
            msg = bytes(rng.getrandbits(8) for _ in range(n)) if n != 3 else b'abc'
            ptr, _keep = guarded_bytes(msg)
            out = guarded(ctypes.c_uint8, 20)
            lib.sha0(ptr, n, out)
            got, want = bytes(out), algos_ref.sha0(msg)
            if got != want:
                hint = '（這是 SHA-1 的結果！）' if got == algos_ref.sha1(msg) else ''
                return f'長度 {n} 的訊息：期望 {want.hex()}，實際 {got.hex()}{hint}'
        return None
    if test == 'crc_sw':
        if lib.crc32_sw(b'123456789', 9) != 0xCBF43926:
            return f'"123456789" 的 CRC-32 應是 cbf43926，實際 {lib.crc32_sw(b"123456789", 9):08x}'
        for n in [0, 1, 2, 3, 100] + [rng.randint(0, 5000) for _ in range(100)]:
            msg = bytes(rng.getrandbits(8) for _ in range(n))
            ptr, _keep = guarded_bytes(msg)
            got, want = lib.crc32_sw(ptr, n), zlib.crc32(msg)
            if got != want:
                return f'長度 {n}：期望 {want:08x}，實際 {got:08x}'
        return None
    if test == 'crc_perf':
        buf = bytes(rng.getrandbits(8) for _ in range(1 << 16)) * 64   # 4 MB
        mine, ref = [], []
        for _ in range(3):                       # 各跑 3 次取最快，降低計時雜訊
            t0 = time.perf_counter()
            got = lib.crc32_sw(buf, len(buf))
            t1 = time.perf_counter()
            lib.bench_crc32_bitwise(buf, len(buf))
            t2 = time.perf_counter()
            mine.append(t1 - t0)
            ref.append(t2 - t1)
            if got != zlib.crc32(buf):
                return ('wrong', '4 MB 資料的 CRC-32 不正確')
        return ('ratio', min(ref) / max(min(mine), 1e-9), min(mine), min(ref))
    if test == 'crc_dma':
        total = 0
        for n in [1, 2, 3, 4, 5, 7, 8, 100, 1001, 4096] + [rng.randint(1, 3000) for _ in range(20)] + [0]:
            view = bytes(rng.getrandbits(8) for _ in range(n))
            ptr, arr = guarded_bytes(view)      # 資料結尾緊貼守護頁；起始位址隨 n 而不對齊
            off = ctypes.addressof(arr) % 4
            got, want = lib.crc32_dma(ptr, n), zlib.crc32(view)
            total += n
            if got != want:
                return ('wrong', f'長度 {n}（位址 +{off}）：期望 {want:08x}，實際 {got:08x}')
        return ('ok', lib.engine_stat_sniffed_bytes(), total, lib.engine_stat_claimed_now(),
                bool(lib.engine_stat_sniff_enabled()))
    raise ValueError(test)


def run_c(test, source, timeout=60):
    if ERROR_FILE.exists():
        ERROR_FILE.unlink()
    status, value = isolated(c_part, test, str(source), timeout=timeout)
    if status == 'crash' and ERROR_FILE.exists():
        value = f'引擎中止：{ERROR_FILE.read_text(encoding="utf-8", errors="replace")}'
    return status, value


def grade_c(rows, source):
    cat = 'A 演算法 (C)'
    items = [(cat, '排序正確（含 n = 0、1、重複值、極值）', 8), (cat, '排序效率（100 萬筆，對照 qsort）', 7),
             (cat, 'SHA-0 正確（含 55 / 56 / 64 bytes 等填充邊界）', 12), (cat, 'CRC-32 軟體版正確', 6),
             (cat, 'CRC-32 軟體版效率（4 MB，對照逐位元版）', 6), (cat, 'CRC-32 DMA sniffer 版正確（含未對齊、0 bytes）', 8),
             (cat, 'DMA 版真的用 sniffer、用完歸還通道並關閉 sniffer', 4), (cat, '-Wall -Wextra 零警告', 4)]
    os.environ['ENGINE_ERROR_FILE'] = str(ERROR_FILE)
    try:
        _, warnings = build_and_load('algos', [source, HERE / 'engine.c', HERE / 'bench.c'], include_dirs=[HERE])
    except BuildError as error:
        rows.fail_all(items, str(error))
        return []
    notes = []

    st, v = run_c('sort', source)
    sort_ok = st == 'ok' and v is None
    rows.add(cat, items[0][1], 8 if sort_ok else 0, 8, v if st != 'ok' else (v or ''))
    if not sort_ok:
        rows.add(cat, items[1][1], 0, 7, '正確性通過後才計算')
    else:
        st, v = run_c('sort_perf', source, timeout=40)
        if st != 'ok':
            rows.add(cat, items[1][1], 0, 7, f'{v}（O(n²) 的排序跑不完 100 萬筆）')
        elif v[0] == 'wrong':
            rows.add(cat, items[1][1], 0, 7, v[1])
        else:
            ratio = v[1]
            pts = 7 if ratio <= 0.8 else 5 if ratio <= 1.5 else 2 if ratio <= 4 else 0
            rows.add(cat, f'排序效率：你的 {v[2] * 1000:.0f} ms / qsort {v[3] * 1000:.0f} ms = {ratio:.2f} 倍時間', pts, 7,
                     '分級：<=0.8 倍 → 7、<=1.5 → 5、<=4 → 2')

    st, v = run_c('sha0', source)
    rows.add(cat, items[2][1], 12 if st == 'ok' and v is None else 0, 12, v or '')

    st, v = run_c('crc_sw', source)
    crc_ok = st == 'ok' and v is None
    rows.add(cat, items[3][1], 6 if crc_ok else 0, 6, v or '')
    if not crc_ok:
        rows.add(cat, items[4][1], 0, 6, '正確性通過後才計算')
    else:
        st, v = run_c('crc_perf', source)
        if st != 'ok' or v[0] == 'wrong':
            rows.add(cat, items[4][1], 0, 6, v if st != 'ok' else v[1])
        else:
            speed = v[1]
            pts = 6 if speed >= 3 else 3 if speed >= 1.8 else 0
            rows.add(cat, f'CRC-32 效率：比逐位元版快 {speed:.1f} 倍（{v[2] * 1000:.0f} ms vs {v[3] * 1000:.0f} ms）', pts, 6,
                     '分級：>=3 倍 → 6、>=1.8 倍 → 3。提示：查表')

    st, v = run_c('crc_dma', source)
    if st != 'ok':
        rows.add(cat, items[5][1], 0, 8, v)
        rows.add(cat, items[6][1], 0, 4, '正確性通過後才計算')
    elif v[0] == 'wrong':
        rows.add(cat, items[5][1], 0, 8, v[1])
        rows.add(cat, items[6][1], 0, 4, '正確性通過後才計算')
    else:
        _, sniffed, total, claimed, sniffing = v
        rows.add(cat, items[5][1], 8, 8)
        problem = (f'sniffer 只處理了 {sniffed} / {total} bytes（是不是自己用軟體算了？）' if sniffed < total else
                   f'結束後還有 {claimed} 個通道沒歸還' if claimed else
                   '結束後 sniffer 還開著' if sniffing else '')
        rows.add(cat, items[6][1], 0 if problem else 4, 4, problem)
    rows.add(cat, items[7][1], 0 if warnings else 4, 4, f'{len(warnings)} 個警告，例如：{warnings[0][:200]}' if warnings else '')
    return notes


# ====================================================================== Part B / C：dispatcher
def make_job(job_id, payload):
    return struct.pack('<I', job_id) + payload


def expected_line(job_id, payload):
    n = len(payload) // 4
    values = sorted(struct.unpack(f'<{n}I', payload))
    return (f'id={job_id} min={values[0]} median={values[n // 2]} max={values[-1]} '
            f'crc32={zlib.crc32(payload):08x} sha0={algos_ref.sha0(payload).hex()}')


def simulate(module, schedule, rclpy, graph, Node, msgs):
    import boards
    fresh_graph(rclpy, graph)
    board_nodes = {k: boards.make_board(k) for k in boards.KINDS}
    module.Dispatcher()
    pub = Node('jobsource').create_publisher(msgs.UInt8MultiArray, '/jobs/request', 100)
    for t, job_id, payload in schedule:
        graph.advance(max(0.0, t - graph.now))
        pub.publish(msgs.UInt8MultiArray(data=list(make_job(job_id, payload))))
        if graph.errors:
            break
    if not graph.errors:
        graph.advance(30.0)
    if graph.errors:
        e = graph.errors[0]
        raise RuntimeError(f'callback 拋出 {type(e).__name__}: {e}')
    results = [(graph.log_time[i], m.data) for i, (t, m) in enumerate(graph.log) if t == '/jobs/result']
    responses = {}
    for i, (t, m) in enumerate(graph.log):
        if t.startswith('/board_') and t.endswith('/response'):
            job_id = struct.unpack('<I', bytes(m.data[:4]))[0]
            responses.setdefault(job_id, {})[t.split('/')[1]] = graph.log_time[i]
    got = {k: [struct.unpack('<I', bytes(m.data[:4]))[0] for _, m in b.requests] for k, b in board_nodes.items()}
    return results, responses, got


def grade_dispatcher(rows, path):
    rclpy, graph, Node, msgs = use_fake_ros()
    cat_b, cat_c = 'B dispatcher', 'C 效能'
    items = [(cat_b, '稀疏到達：10 個不同大小的工作，摘要字串完全正確且依序', 12),
             (cat_b, '一次湧入：20 個工作，摘要正確且依序', 10),
             (cat_b, '分工：每個工作都送到三片板子，且等三片都回覆後才發布', 8),
             (cat_c, '吞吐量', 15)]
    try:
        spec = importlib.util.spec_from_file_location('student_dispatcher', str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as error:  # noqa: BLE001
        rows.fail_all(items, f'無法載入：{type(error).__name__}: {error}')
        return
    rng = random.Random(77)
    sparse = [(0.1 * i, 1000 + 37 * i, bytes(rng.getrandbits(8) for _ in range(4 * rng.randint(1, 1024))))
              for i in range(10)]
    sparse[3] = (0.3, 0x12345678, bytes([0xFF, 0xFF, 0xFF, 0xFF]))         # 只有一個元素
    burst = [(0.0, i * 3 + 1, bytes(rng.getrandbits(8) for _ in range(4096))) for i in range(20)]

    outcome = {}
    for label, schedule in (('sparse', sparse), ('burst', burst)):
        try:
            outcome[label] = simulate(module, schedule, rclpy, graph, Node, msgs)
        except Exception as error:  # noqa: BLE001
            outcome[label] = f'{type(error).__name__}: {error}'

    def check(label, schedule, item):
        r = outcome[label]
        if isinstance(r, str):
            rows.add(*item[:2], 0, item[2], r)
            return False
        want = [expected_line(job_id, payload) for _, job_id, payload in schedule]
        got = [text for _, text in r[0]]
        if got == want:
            rows.add(*item[:2], item[2], item[2])
            return True
        if len(got) != len(want):
            detail = f'發布了 {len(got)} 筆結果，應該是 {len(want)} 筆'
        else:
            i = next(i for i, (a, b) in enumerate(zip(got, want)) if a != b)
            detail = f'第 {i + 1} 筆：\n              期望 {want[i][:120]}\n              實際 {got[i][:120]}'
        rows.add(*item[:2], 0, item[2], detail)
        return False

    ok1 = check('sparse', sparse, items[0])
    ok2 = check('burst', burst, items[1])
    problem = '先通過上面兩項' if not (ok1 and ok2) else None
    if problem is None:
        for label, schedule in (('sparse', sparse), ('burst', burst)):
            results, responses, got = outcome[label]
            for idx, (_, job_id, _) in enumerate(schedule):
                missing = [k for k in ('sort', 'sha0', 'crc') if job_id not in got[k]]
                if missing:
                    problem = f'工作 id={job_id} 沒有送到 board_{missing[0]}（每個演算法都要在自己的板子上跑）'
                    break
                last = max(responses.get(job_id, {}).values(), default=float('inf'))
                if results[idx][0] < last:
                    problem = f'工作 id={job_id} 在三片板子都回覆之前就發布了結果'
                    break
            if problem:
                break
    rows.add(*items[2][:2], 0 if problem else 8, 8, problem or '')
    if problem:
        rows.add(*items[3][:2], 0, 15, '正確性全部通過後才計算')
        return
    import boards
    results = outcome['burst'][0]
    makespan = results[-1][0]
    baseline = 20 * sum(boards.service_time(k, 4096) for k in boards.KINDS)
    speedup = baseline / makespan
    pts = 15 if speedup >= 2.7 else 10 if speedup >= 2.2 else 5 if speedup >= 1.5 else 0
    rows.add(cat_c, f'吞吐量：20 個工作共 {makespan * 1000:.0f} ms，加速比 {speedup:.2f}（對照：三個演算法輪流做 = {baseline * 1000:.0f} ms）',
             pts, 15, '分級：>=2.7 → 15、>=2.2 → 10、>=1.5 → 5')


def grade(algos, dispatcher):
    rows = Rows('大題三 三片板子：排序 / SHA-0 / CRC-32')
    notes = grade_c(rows, Path(algos).resolve())
    grade_dispatcher(rows, Path(dispatcher).resolve())
    if ERROR_FILE.exists():
        ERROR_FILE.unlink()
    return rows.result(notes=notes)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--algos', default=str(HERE / 'algos.c'))
    parser.add_argument('--dispatcher', default=str(HERE / 'dispatcher.py'))
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    emit(grade(args.algos, args.dispatcher), 'Q3', args.json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
