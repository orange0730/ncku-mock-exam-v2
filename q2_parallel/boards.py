"""（提供，不要修改）大題二的兩片模擬開發板。

    python3 boards.py 0        # 在真的 ROS 2 上啟動 board0（用你的 firmware.c）
    python3 boards.py 1        # 另一個終端機啟動 board1

板子規格（寫協調者時要用到）：
    board0：每個神經元 1.0 ms
    board1：每個神經元 2.0 ms（比較舊的板子，慢一倍）
    每筆 request 固定額外 2.0 ms（解析封包、喚醒），連線單程延遲 1.0 ms
    每片板子一次只處理一筆 request，其餘照到達順序排隊（FIFO）
"""
import ctypes
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COMMON = ROOT / 'common'
for p in (COMMON, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import model  # noqa: E402
from clib import build_and_load  # noqa: E402

PER_NEURON = (0.001, 0.002)       # 秒 / 神經元：board0、board1
OVERHEAD = 0.002                  # 秒 / request
LINK_LATENCY = 0.001              # 秒，單程


def decode_header(h):
    return (h >> 16) & 0xFFFF, (h >> 8) & 0xFF, h & 0xFF


def ref_firmware(req):
    """firmware.h 規格的 Python 參考實作。回傳 [header, bits] 或 None（不合法）。"""
    if len(req) != 3:
        return None
    _, first, count = decode_header(req[0])
    if count == 0 or count > 32 or first + count > 32:
        return None
    img = (req[2] << 32) | req[1]
    return [req[0], model._hidden_range_impl(img, first, count)]


class CFirmware:
    def __init__(self, firmware_c, bnn_c):
        q1 = ROOT / 'q1_ebnn'
        self.lib, self.warnings = build_and_load('firmware', [firmware_c, bnn_c],
                                                 include_dirs=[HERE, q1, COMMON])
        self.lib.fw_handle.restype = ctypes.c_int
        self.lib.fw_handle.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_int, ctypes.POINTER(ctypes.c_uint32)]

    def __call__(self, req):
        req = list(req)
        arr = (ctypes.c_uint32 * max(len(req), 1))(*req)
        resp = (ctypes.c_uint32 * 8)(*([0xDEADBEEF] * 8))
        rc = self.lib.fw_handle(arr, len(req), resp)
        return None if rc < 0 else list(resp[:rc])


def cost(board_index):
    def fn(msg):
        data = list(msg.data)
        count = data[0] & 0xFF if data else 0
        return OVERHEAD + count * PER_NEURON[board_index]
    return fn


def make_board(index, firmware=None):
    """建立 board{index} node。firmware 為 None 時用 Python 參考韌體。"""
    from std_msgs.msg import UInt32MultiArray
    from boardsim import SimBoard
    fw = firmware or ref_firmware

    def handler(msg):
        out = fw(list(msg.data))
        if out is None:
            return None
        reply = UInt32MultiArray()
        reply.data = [int(v) for v in out]
        return reply

    return SimBoard(f'board{index}', UInt32MultiArray, UInt32MultiArray, handler, cost(index), LINK_LATENCY)


def main():
    import rclpy
    index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    rclpy.init()
    fw = None if os.environ.get('FIRMWARE') == 'ref' else CFirmware(HERE / 'firmware.c', ROOT / 'q1_ebnn' / 'bnn.c')
    node = make_board(index, fw)
    print(f'board{index} 已啟動（{"參考" if fw is None else "你的"}韌體），按 Ctrl-C 停止', flush=True)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
