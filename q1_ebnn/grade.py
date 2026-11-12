"""大題一評分程式：eBNN 推論（C 核心 45 + PIO 加速器 25 + ROS node 30 = 100）。

    python3 grade.py
    python3 grade.py --bnn path/bnn.c --pio path/xnorpop.pio --node path/ebnn_node.py
    python3 grade.py --json
"""
import argparse
import ctypes
import importlib.util
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMON = HERE.parent / 'common'
sys.path.insert(0, str(COMMON))
sys.path.insert(0, str(HERE))

import model  # noqa: E402
from clib import BuildError, build_and_load  # noqa: E402
from guard import guarded  # noqa: E402
from fakeros import fresh_graph, use_fake_ros  # noqa: E402
from pio_sim import PioError, assemble, run  # noqa: E402
import hints  # noqa: E402
from report import Rows, emit, isolated  # noqa: E402

MASK32 = 0xFFFFFFFF


# ====================================================================== Part A：C 核心
def _load(source):
    lib, _ = build_and_load('bnn', [source], include_dirs=[HERE, COMMON])
    lib.popcount32.restype = ctypes.c_int
    lib.popcount32.argtypes = [ctypes.c_uint32]
    lib.bnn_hidden.restype = ctypes.c_uint32
    lib.bnn_hidden.argtypes = [ctypes.POINTER(ctypes.c_uint32)]
    lib.bnn_scores.restype = None
    lib.bnn_scores.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_int32)]
    lib.bnn_infer.restype = ctypes.c_int
    lib.bnn_infer.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_int32)]
    return lib


class Buffers:
    """影像（2 個 word）與分數（10 個 int32）都緊貼守護頁：多讀或多寫一格就會當掉。"""

    def __init__(self):
        self.img = guarded(ctypes.c_uint32, 2)
        self.scores = guarded(ctypes.c_int32, 10)

    def image(self, v):
        self.img[0], self.img[1] = v & MASK32, v >> 32
        return self.img

    def fresh_scores(self):
        self.scores[:] = [0x5A5A5A5A] * 10
        return self.scores


def c_part(test, source):
    """在子 process 裡跑一組 C 測試，回傳 None（通過）或第一個錯誤的說明。"""
    lib = _load(source)
    buf = Buffers()
    rng = random.Random(116)
    if test == 'popcount':
        values = [0, MASK32, 1, 0x80000000, 0x7FFFFFFF, 0xAAAAAAAA] + [rng.getrandbits(32) for _ in range(3000)]
        for v in values:
            got, want = lib.popcount32(v), bin(v).count('1')
            if got != want:
                return f'popcount32(0x{v:08X})：期望 {want}，實際 {got}'
    elif test == 'hidden':
        images = [img for img, _ in model.dataset(300)] + [rng.getrandbits(64) for _ in range(300)] + [0, (1 << 64) - 1]
        for v in images:
            got, want = lib.bnn_hidden(buf.image(v)), model.hidden(v)
            if got != want:
                return f'影像 0x{v:016X}：期望 hidden=0x{want:08X}，實際 0x{got:08X}'
    elif test == 'scores':
        for h in [0, MASK32, 0b111, 0x80000000] + [rng.getrandbits(32) for _ in range(1000)]:
            out = buf.fresh_scores()
            lib.bnn_scores(h, out)
            if list(out) != model.scores_from_hidden(h):
                return f'hidden=0x{h:08X}：期望 {model.scores_from_hidden(h)}，實際 {list(out)}'
    elif test == 'infer':
        data = model.dataset(1000)
        ties = 0
        for v, _ in data:
            out = buf.fresh_scores()
            got = lib.bnn_infer(buf.image(v), out)
            want, scores = model.infer(v)
            ties += scores.count(max(scores)) > 1
            if got != want or list(out) != scores:
                return f'影像 0x{v:016X}：期望 預測 {want} 分數 {scores}，實際 預測 {got} 分數 {list(out)}'
    elif test == 'accuracy':
        data = model.dataset(1000, seed=7)
        correct = 0
        for v, label in data:
            correct += lib.bnn_infer(buf.image(v), buf.fresh_scores()) == label
        want = sum(model.infer(v)[0] == label for v, label in data)
        if correct != want:
            return f'1000 張含雜訊的數字答對 {correct} 張，參考模型答對 {want} 張'
    return None


C_ITEMS = [  # (test, 名稱, 分數)
    ('popcount', 'popcount32（含第 31 位、全 1）', 8),
    ('hidden', 'bnn_hidden：XNOR、門檻、位元位置', 15),
    ('scores', 'bnn_scores：2p - 32', 8),
    ('infer', 'bnn_infer：預測與分數（含同分取最小 index）', 8),
    ('accuracy', '整體：1000 張含雜訊數字與參考模型逐張一致', 4),
]


def grade_c(rows, source):
    cat = 'A eBNN 核心 (C)'
    try:
        _, warnings = build_and_load('bnn', [source], include_dirs=[HERE, COMMON])
    except BuildError as error:
        rows.fail_all([(cat, n, p) for _, n, p in C_ITEMS] + [(cat, '-Wall -Wextra 零警告', 2)], str(error))
        return
    for test, name, pts in C_ITEMS:
        status, value = isolated(c_part, test, str(source), timeout=60)
        if status != 'ok':
            rows.add(cat, name, 0, pts, value)
        else:
            rows.add(cat, name, pts if value is None else 0, pts, value or '')
    rows.add(cat, '-Wall -Wextra 零警告', 2 if not warnings else 0, 2,
             f'{len(warnings)} 個警告，例如：{warnings[0][:200]}' if warnings else '')


# ====================================================================== Part B：PIO
CYCLE_TIERS = [(106, 6), (125, 4), (170, 2)]
INSTR_TIERS = [(9, 4), (16, 2), (32, 1)]


def pio_expected(words):
    return [32 - bin(w).count('1') for w in words]


def grade_pio(rows, path):
    cat = 'B XNOR-popcount PIO'
    rng = random.Random(2350)
    suites = [
        ('edge_values（fast）', [0, MASK32, 1, 0x80000000, 0x55555555, 0xF0F0F0F0, 0x7FFFFFFF, 0xFFFFFFFE], 'fast'),
        ('random_256（slow_rx）', [rng.getrandbits(32) for _ in range(256)], 'slow_rx'),
        ('random_512（bursty）', [rng.getrandbits(32) for _ in range(512)], 'bursty'),
    ]
    try:
        image = assemble(Path(path).read_text(encoding='utf-8'))
        error = None
    except (PioError, OSError) as e:
        image, error = None, str(e)
    all_ok = image is not None
    for name, words, schedule in suites:
        if image is None:
            rows.add(cat, name, 0, 5, f'組譯失敗：{error}')
            continue
        try:
            got, _, _ = run(image, words, schedule, expected_outputs=len(words))
            want = pio_expected(words)
            if got == want:
                rows.add(cat, name, 5, 5)
                continue
            if len(got) != len(want):
                detail = f'輸出 {len(got)} 個 word，應該是 {len(want)} 個'
            else:
                i = next(i for i, (a, b) in enumerate(zip(got, want)) if a != b)
                detail = f'輸入 0x{words[i]:08X}：期望 {want[i]}，實際 {got[i]}'
        except PioError as e:
            detail = str(e)
        all_ok = False
        rows.add(cat, name, 0, 5, detail)
    cycles = None
    if all_ok:
        perf_rng = random.Random(22099)
        words = [perf_rng.getrandbits(32) for _ in range(4096)]
        try:
            got, total, _ = run(image, words, 'fast', expected_outputs=len(words))
            cycles = total / len(words) if got == pio_expected(words) else None
        except PioError:
            cycles = None
    if cycles is None:
        rows.add(cat, '效率：週期數', 0, 6, '正確性全部通過後才計算')
        rows.add(cat, '效率：指令數', 0, 4, '正確性全部通過後才計算')
    else:
        n = len(image['program'])
        rows.add(cat, f'效率：{cycles:.2f} 週期 / word', next((p for t, p in CYCLE_TIERS if cycles <= t), 0), 6,
                 '分級：<=106 → 6、<=125 → 4、<=170 → 2')
        rows.add(cat, f'效率：{n} 條指令', next((p for t, p in INSTR_TIERS if n <= t), 0), 4,
                 '分級：<=9 → 4、<=16 → 2、<=32 → 1')


# ====================================================================== Part C：ROS node
NODE_ITEMS = [
    ('node 名稱 ebnn', 2), ('訂閱 /camera/image（UInt64）', 3), ('發布 /ebnn/scores 與 /ebnn/prediction（型別正確）', 3),
    ('30 張影像的分數與預測都正確', 12), ('每張影像：先 scores 後 prediction，各一次', 5), ('邊界影像：全 0、全 1', 5),
]


def grade_node(rows, path):
    import os
    cat = 'C ROS 2 node'
    os.environ['BNN_BACKEND'] = 'ref'          # node 的分數不受 C 核心影響
    rclpy, graph, Node, msgs = use_fake_ros()
    try:
        spec = importlib.util.spec_from_file_location('student_ebnn_node', str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as error:  # noqa: BLE001
        rows.fail_all([(cat, n, p) for n, p in NODE_ITEMS], f'無法載入：{type(error).__name__}: {error}')
        return

    def rig():
        fresh_graph(rclpy, graph)
        node = module.EbnnNode()
        cam = Node('camera').create_publisher(msgs.UInt64, '/camera/image', 10)
        return node, cam

    def send(cam, v):
        start, errs = len(graph.log), len(graph.errors)
        cam.publish(msgs.UInt64(data=v))
        if len(graph.errors) > errs:
            e = graph.errors[-1]
            raise RuntimeError(f'callback 拋出 {type(e).__name__}: {e}')
        return [(t, m) for t, m in graph.log[start + 1:]]

    def check(fn):
        try:
            return fn()
        except Exception as error:  # noqa: BLE001
            return False, f'{type(error).__name__}: {error}'

    def t_name():
        node, _ = rig()
        return node.get_name() == 'ebnn', f'node 名稱是 {node.get_name()!r}'

    def t_sub():
        rig()
        subs = [(s.topic, s.msg_type.__name__) for s in graph.subscriptions if s.node.get_name() == 'ebnn']
        return ('/camera/image', 'UInt64') in subs, f'目前訂閱：{subs}'

    def t_pubs():
        rig()
        pubs = {(p.topic, p.msg_type.__name__) for p in graph.publishers if p.node.get_name() == 'ebnn'}
        need = {('/ebnn/scores', 'Int32MultiArray'), ('/ebnn/prediction', 'Int32')}
        return need <= pubs, f'目前發布：{sorted(pubs)}'

    def outputs_for(images):
        _, cam = rig()
        result = []
        for v in images:
            out = send(cam, v)
            result.append(out)
        return result

    def t_values():
        images = [img for img, _ in model.dataset(30, seed=99)]
        for v, out in zip(images, outputs_for(images)):
            want_pred, want_scores = model.infer(v)
            scores = [list(m.data) for t, m in out if t == '/ebnn/scores']
            preds = [m.data for t, m in out if t == '/ebnn/prediction']
            if scores[:1] != [want_scores] or preds[:1] != [want_pred]:
                return False, f'影像 0x{v:016X}：期望 scores={want_scores} pred={want_pred}，實際 scores={scores} pred={preds}'
        return True, ''

    def t_order():
        images = [img for img, _ in model.dataset(5, seed=5)]
        for v, out in zip(images, outputs_for(images)):
            topics = [t for t, _ in out]
            if topics != ['/ebnn/scores', '/ebnn/prediction']:
                return False, f'影像 0x{v:016X} 的輸出順序：{topics}'
        return True, ''

    def t_edges():
        images = [0, (1 << 64) - 1, 1 << 63, 1]
        for v, out in zip(images, outputs_for(images)):
            want_pred, want_scores = model.infer(v)
            got = [(t, list(m.data) if t == '/ebnn/scores' else m.data) for t, m in out]
            if got != [('/ebnn/scores', want_scores), ('/ebnn/prediction', want_pred)]:
                return False, f'影像 0x{v:016X}：期望 scores={want_scores} pred={want_pred}，實際 {got}'
        return True, ''

    for (name, pts), fn in zip(NODE_ITEMS, [t_name, t_sub, t_pubs, t_values, t_order, t_edges]):
        ok, detail = check(fn)
        rows.add(cat, name, pts if ok else 0, pts, detail)


def grade(bnn, pio, node):
    rows = Rows('大題一 eBNN 推論')
    grade_c(rows, Path(bnn).resolve())
    grade_pio(rows, Path(pio).resolve())
    grade_node(rows, Path(node).resolve())
    return rows.result()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bnn', default=str(HERE / 'bnn.c'))
    parser.add_argument('--pio', default=str(HERE / 'xnorpop.pio'))
    parser.add_argument('--node', default=str(HERE / 'ebnn_node.py'))
    parser.add_argument('--json', action='store_true')
    hints.add_args(parser)
    args = parser.parse_args()
    result = grade(args.bnn, args.pio, args.node)
    emit(result, 'Q1', args.json)
    hints.maybe_show(result, 'Q1', args)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
