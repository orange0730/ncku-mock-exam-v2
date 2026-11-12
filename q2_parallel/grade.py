"""大題二評分程式：兩片板子平行推論（韌體 C 35 + 協調者正確性 40 + 效能 25 = 100）。

    python3 grade.py
    python3 grade.py --firmware path/firmware.c --coordinator path/coordinator.py
    python3 grade.py --json

協調者的測試使用「參考韌體」的模擬板子，所以 Part B / C 的分數不受你韌體對錯的影響。
"""
import argparse
import ctypes
import importlib.util
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COMMON = ROOT / 'common'
for p in (COMMON, HERE):
    sys.path.insert(0, str(p))

import model  # noqa: E402
from clib import BuildError, build_and_load  # noqa: E402
from fakeros import fresh_graph, use_fake_ros  # noqa: E402
from guard import guarded  # noqa: E402
from report import Rows, emit, isolated  # noqa: E402

FULL = 0xFFFFFFFF
SENTINEL = 0xDEADBEEF


# ====================================================================== Part A：韌體
def pick_bnn_source():
    """優先用你大題一的 bnn.c；它的 bnn_hidden 還不正確時改用參考解答（若存在）。"""
    student = ROOT / 'q1_ebnn' / 'bnn.c'
    status, value = isolated(_check_bnn, str(student), timeout=60)
    if status == 'ok' and value:
        return student, None
    ref = ROOT / 'solutions' / 'q1_ebnn' / 'bnn.c'
    if ref.exists():
        return ref, '大題一的 bnn_hidden 還不正確，韌體測試改連結參考解答的 bnn.c'
    return student, '大題一的 bnn_hidden 還不正確，韌體測試可能因此失敗'


def _check_bnn(source):
    lib, _ = build_and_load('bnn', [source], include_dirs=[ROOT / 'q1_ebnn', COMMON])
    lib.bnn_hidden.restype = ctypes.c_uint32
    lib.bnn_hidden.argtypes = [ctypes.POINTER(ctypes.c_uint32)]
    rng = random.Random(1)
    for _ in range(200):
        v = rng.getrandbits(64)
        if lib.bnn_hidden((ctypes.c_uint32 * 2)(v & FULL, v >> 32)) != model.hidden(v):
            return False
    return True


def _fw(firmware, bnn):
    lib, _ = build_and_load('firmware', [firmware, bnn], include_dirs=[HERE, ROOT / 'q1_ebnn', COMMON])
    lib.fw_handle.restype = ctypes.c_int
    lib.fw_handle.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_int, ctypes.POINTER(ctypes.c_uint32)]

    def call(req):
        # req 剛好 n 個 word、resp 剛好 2 個 word，後面都緊貼守護頁：
        # 還沒檢查 n 就去讀 req[1]、或寫到 resp[2]，程式會立刻當掉。
        arr = guarded(ctypes.c_uint32, len(req), req)
        resp = guarded(ctypes.c_uint32, 2, [SENTINEL] * 2)
        return lib.fw_handle(arr, len(req), resp), list(resp)
    return call


def fw_part(test, firmware, bnn):
    call = _fw(firmware, bnn)
    rng = random.Random(42)
    if test in ('echo', 'bits'):
        for _ in range(600):
            first = rng.randrange(32)
            count = rng.randint(1, 32 - first)
            seq = rng.randrange(1 << 16)
            img = rng.getrandbits(64)
            header = (seq << 16) | (first << 8) | count
            rc, resp = call([header, img & FULL, img >> 32])
            if test == 'echo' and (rc != 2 or resp[0] != header):
                return f'header=0x{header:08X}（seq={seq} first={first} count={count}）：期望回傳 2、resp[0]=0x{header:08X}，實際 rc={rc} resp[0]=0x{resp[0]:08X}'
            want = model.hidden_range(img, first, count)
            if test == 'bits' and (rc != 2 or resp[1] != want):
                return f'first={first} count={count} 影像 0x{img:016X}：期望 resp[1]=0x{want:08X}，實際 0x{resp[1]:08X}（rc={rc}）'
    elif test == 'invalid':
        img = 0x0123456789ABCDEF
        cases = [([0x00000010, 1], 'n = 2'), ([0x00000010, 1, 2, 3], 'n = 4'),
                 ([0x00010500], 'n = 1'), ([0x00000000, 1, 2], 'count = 0'),
                 ([0x00000021, 1, 2], 'count = 33'), ([0x00001E05, 1, 2], 'first = 30, count = 5'),
                 ([0x0000FF01, img & FULL, img >> 32], 'first = 255')]
        for req, label in cases:
            rc, resp = call(req)
            if rc != -1 or resp != [SENTINEL] * 2:
                return f'不合法的請求（{label}）：期望回傳 -1 且不寫 resp，實際 rc={rc}、resp 被改成 {[hex(v) for v in resp[:2]]}'
    elif test == 'full':
        for _ in range(50):
            img = rng.getrandbits(64)
            rc, resp = call([0x00070020, img & FULL, img >> 32])
            if rc != 2 or resp[1] != model.hidden(img):
                return f'first=0 count=32：期望 resp[1]=0x{model.hidden(img):08X}，實際 0x{resp[1]:08X}（rc={rc}）'
    return None


FW_ITEMS = [('echo', 'header 原樣送回（含 first >= 16）', 10), ('bits', '部分神經元的輸出與位元位置', 15),
            ('invalid', '不合法請求回傳 -1 且不寫入', 5), ('full', 'count = 32 的完整範圍', 5)]


def grade_firmware(rows, firmware):
    cat = 'A 板子韌體 (C)'
    bnn, note = pick_bnn_source()
    try:
        build_and_load('firmware', [firmware, bnn], include_dirs=[HERE, ROOT / 'q1_ebnn', COMMON])
    except BuildError as error:
        rows.fail_all([(cat, n, p) for _, n, p in FW_ITEMS], str(error))
        return note
    for test, name, pts in FW_ITEMS:
        status, value = isolated(fw_part, test, str(firmware), str(bnn), timeout=60)
        if status != 'ok':
            rows.add(cat, name, 0, pts, value)
        else:
            rows.add(cat, name, pts if value is None else 0, pts, value or '')
    return note


# ====================================================================== Part B / C：協調者
def forbidden(*_args, **_kwargs):
    raise RuntimeError('協調者不能自己算第一層（model.hidden / hidden_range / infer），要交給板子算')


def simulate(module, schedule, rclpy, graph, Node, msgs):
    import boards
    fresh_graph(rclpy, graph)
    board_nodes = [boards.make_board(0), boards.make_board(1)]
    saved = model.hidden, model.hidden_range, model.infer
    model.hidden = model.hidden_range = model.infer = forbidden
    try:
        module.Coordinator()
        cam = Node('camera').create_publisher(msgs.UInt64, '/camera/image', 100)
        sent = []
        for t, img in schedule:
            graph.advance(max(0.0, t - graph.now))
            sent.append(graph.now)
            cam.publish(msgs.UInt64(data=img))
            if graph.errors:
                break
        if not graph.errors:
            graph.advance(10.0)
    finally:
        model.hidden, model.hidden_range, model.infer = saved
    if graph.errors:
        e = graph.errors[0]
        raise RuntimeError(f'callback 拋出 {type(e).__name__}: {e}')
    preds = [(graph.log_time[i], m.data) for i, (t, m) in enumerate(graph.log) if t == '/ebnn/prediction']
    reqs = [[list(m.data) for _, m in b.requests] for b in board_nodes]
    errors = [e for b in board_nodes for e in b.errors]
    return sent, preds, reqs, errors


def coverage_problem(reqs, n):
    covered = {}
    for board, lst in enumerate(reqs):
        for data in lst:
            if len(data) != 3:
                return f'board{board} 收到長度 {len(data)} 的請求'
            seq, first, count = data[0] >> 16, (data[0] >> 8) & 0xFF, data[0] & 0xFF
            mask = (((1 << count) - 1) << first) & FULL
            if covered.get(seq, 0) & mask:
                return f'seq {seq} 的神經元被重複計算（board{board} first={first} count={count}）'
            covered[seq] = covered.get(seq, 0) | mask
    for seq in range(n):
        if covered.get(seq, 0) != FULL:
            return f'seq {seq} 的 32 個神經元沒有全部送給板子算（已送出 mask 0x{covered.get(seq, 0):08X}）'
    return None


def images(n, seed):
    return [img for img, _ in model.dataset(n, seed=seed)]


def grade_coordinator(rows, path):
    rclpy, graph, Node, msgs = use_fake_ros()
    cat_b, cat_c = 'B 協調者正確性', 'C 效能'
    items_b = [(cat_b, '稀疏到達：20 張影像的預測正確且依序', 15),
               (cat_b, '一次湧入：40 張影像的預測正確且依序', 15),
               (cat_b, '工作分配：每張影像 32 個神經元剛好算一次、兩片板子都有用到', 10)]
    items_c = [(cat_c, '吞吐量', 15), (cat_c, '延遲', 10)]
    try:
        spec = importlib.util.spec_from_file_location('student_coordinator', str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as error:  # noqa: BLE001
        rows.fail_all(items_b + items_c, f'無法載入：{type(error).__name__}: {error}')
        return []

    sparse_imgs, burst_imgs = images(20, 31), images(40, 32)
    results = {}
    for label, schedule in (('sparse', [(0.1 * i, img) for i, img in enumerate(sparse_imgs)]),
                            ('burst', [(0.0, img) for img in burst_imgs])):
        try:
            results[label] = simulate(module, schedule, rclpy, graph, Node, msgs)
        except Exception as error:  # noqa: BLE001
            results[label] = f'{type(error).__name__}: {error}'

    def check_preds(label, imgs):
        r = results[label]
        if isinstance(r, str):
            return False, r
        _, preds, _, errors = r
        want = [model.argmax(model.scores_from_hidden(model._hidden_impl(v))) for v in imgs]
        got = [p for _, p in preds]
        if errors:
            return False, f'板子回報錯誤：{errors[0]}'
        if got != want:
            if len(got) != len(want):
                return False, f'發布了 {len(got)} 個預測，應該是 {len(want)} 個'
            i = next(i for i, (a, b) in enumerate(zip(got, want)) if a != b)
            return False, f'第 {i} 張（seq {i}）：期望 {want[i]}，實際 {got[i]}（順序錯了或組合錯了）'
        return True, ''

    ok_sparse, d = check_preds('sparse', sparse_imgs)
    rows.add(*items_b[0][:2], 15 if ok_sparse else 0, 15, d)
    ok_burst, d = check_preds('burst', burst_imgs)
    rows.add(*items_b[1][:2], 15 if ok_burst else 0, 15, d)

    ok_cov, d = False, '先通過上面兩項'
    if ok_sparse and ok_burst:
        problems = [coverage_problem(results[k][2], n) for k, n in (('sparse', 20), ('burst', 40))]
        used = all(results['burst'][2][b] for b in (0, 1))
        problem = next((p for p in problems if p), None) or (None if used else '一次湧入時只用到一片板子')
        ok_cov, d = problem is None, problem or ''
    rows.add(*items_b[2][:2], 10 if ok_cov else 0, 10, d)

    notes = []
    if not (ok_sparse and ok_burst and ok_cov):
        rows.add(cat_c, '吞吐量', 0, 15, '正確性全部通過後才計算')
        rows.add(cat_c, '延遲', 0, 10, '正確性全部通過後才計算')
        return notes
    sent, preds, _, _ = results['burst']
    makespan = preds[-1][0] - sent[0]
    baseline = 40 * (0.002 + 32 * 0.001)
    speedup = baseline / makespan
    tp = 15 if speedup >= 1.49 else 11 if speedup >= 1.44 else 7 if speedup >= 1.3 else 3 if speedup >= 1.1 else 0
    rows.add(cat_c, f'吞吐量：40 張共 {makespan * 1000:.0f} ms，加速比 {speedup:.3f}（對照：只用 board0 = {baseline * 1000:.0f} ms）',
             tp, 15, '分級：>=1.49 → 15、>=1.44 → 11、>=1.3 → 7、>=1.1 → 3')
    sent, preds, _, _ = results['sparse']
    latency = sum(p[0] - s for p, s in zip(preds, sent)) / len(sent) * 1000
    lp = 10 if latency <= 27 else 6 if latency <= 30 else 3 if latency <= 37 else 0
    rows.add(cat_c, f'延遲：每 100 ms 一張時，平均 {latency:.1f} ms', lp, 10,
             '分級：<=27 ms → 10、<=30 → 6、<=37 → 3（只用 board0 約 36 ms）')
    return notes


def grade(firmware, coordinator):
    rows = Rows('大題二 兩片板子平行推論')
    note = grade_firmware(rows, Path(firmware).resolve())
    notes = grade_coordinator(rows, Path(coordinator).resolve())
    return rows.result(notes=[n for n in [note, *notes] if n])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--firmware', default=str(HERE / 'firmware.c'))
    parser.add_argument('--coordinator', default=str(HERE / 'coordinator.py'))
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    emit(grade(args.firmware, args.coordinator), 'Q2', args.json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
