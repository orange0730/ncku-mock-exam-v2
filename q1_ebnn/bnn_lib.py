"""（提供，不要修改）把 bnn.c 編譯成共享函式庫並包成 Python 物件，給 ROS node 呼叫。

    bnn = bnn_lib.load()            # 編譯並載入 q1_ebnn/bnn.c
    pred, scores = bnn.infer_words(lo, hi)

注意：scores 回傳的是 ctypes 陣列（c_int32 * 10），不是 Python list。

環境變數 BNN_BACKEND=ref 時改用 common/model.py 的 Python 參考實作，
評分 ROS node 時會這樣做，讓 node 的分數不受你 C 核心對錯的影響。
"""
import ctypes
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMON = HERE.parent / 'common'
if str(COMMON) not in sys.path:
    sys.path.insert(0, str(COMMON))

import model  # noqa: E402
from clib import build_and_load  # noqa: E402

Scores = ctypes.c_int32 * 10
Image = ctypes.c_uint32 * 2


class CBnn:
    def __init__(self, source):
        self.lib, self.warnings = build_and_load('bnn', [source], include_dirs=[HERE, COMMON])
        self.lib.bnn_infer.restype = ctypes.c_int
        self.lib.bnn_infer.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_int32)]

    def infer_words(self, lo, hi):
        scores = Scores()
        pred = self.lib.bnn_infer(Image(lo, hi), scores)
        return pred, scores


class RefBnn:
    warnings = []

    def infer_words(self, lo, hi):
        pred, scores = model.infer(((hi & 0xFFFFFFFF) << 32) | (lo & 0xFFFFFFFF))
        return pred, Scores(*scores)


def load(backend=None, source=None):
    backend = backend or os.environ.get('BNN_BACKEND', 'c')
    if backend == 'ref':
        return RefBnn()
    return CBnn(source or HERE / 'bnn.c')
