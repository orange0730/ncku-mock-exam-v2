"""（提供，不要修改）大題三的三片模擬開發板，各自只會跑一種演算法。

    python3 boards.py sort      # 在真的 ROS 2 上啟動 board_sort（用你的 algos.c）
    python3 boards.py sha0
    python3 boards.py crc

訊息格式（三片板子都一樣，std_msgs/msg/UInt8MultiArray）：
    request ：[job id 4 bytes little-endian] + payload
    response：[job id 4 bytes little-endian] + 結果
        board_sort：payload 視為 little-endian uint32 陣列，回傳排序後的陣列（同樣格式）
        board_sha0：20 bytes 的 SHA-0 摘要
        board_crc ：4 bytes 的 CRC-32（little-endian），用 crc32_dma 算

板子速度（寫 dispatcher 時用來估算）：
    board_sort：每筆 request 1 ms + n·log2(n) × 1 µs（n = uint32 個數）
    board_sha0：每筆 request 1 ms + 每個 64-byte 區塊 0.15 ms
    board_crc ：每筆 request 1 ms + 每個 byte 2 µs
    連線單程延遲 1 ms；每片板子一次處理一筆，其餘 FIFO 排隊
"""
import ctypes
import math
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COMMON = ROOT / 'common'
for p in (COMMON, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import algos_ref  # noqa: E402
from clib import build_and_load  # noqa: E402

OVERHEAD = 0.001
LINK_LATENCY = 0.001
KINDS = ('sort', 'sha0', 'crc')


def service_time(kind, payload_len):
    if kind == 'sort':
        n = payload_len // 4
        return OVERHEAD + n * math.log2(max(n, 2)) * 1e-6
    if kind == 'sha0':
        return OVERHEAD + ((payload_len + 8) // 64 + 1) * 0.15e-3
    return OVERHEAD + payload_len * 2e-6


def ref_compute(kind, payload):
    if kind == 'sort':
        n = len(payload) // 4
        return struct.pack(f'<{n}I', *sorted(struct.unpack(f'<{n}I', payload[:4 * n])))
    if kind == 'sha0':
        return algos_ref.sha0(payload)
    return struct.pack('<I', zlib.crc32(payload))


class CAlgos:
    def __init__(self, algos_c=None):
        self.lib, self.warnings = build_and_load(
            'algos', [algos_c or HERE / 'algos.c', HERE / 'engine.c', HERE / 'bench.c'], include_dirs=[HERE])
        L = self.lib
        L.sort_u32.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t]
        L.sha0.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_uint8)]
        L.crc32_sw.restype = ctypes.c_uint32
        L.crc32_sw.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        L.crc32_dma.restype = ctypes.c_uint32
        L.crc32_dma.argtypes = [ctypes.c_char_p, ctypes.c_size_t]

    def __call__(self, kind, payload):
        if kind == 'sort':
            n = len(payload) // 4
            arr = (ctypes.c_uint32 * max(n, 1)).from_buffer_copy(payload[:4 * n] or b'\0\0\0\0')
            self.lib.sort_u32(arr, n)
            return bytes(arr)[:4 * n]
        if kind == 'sha0':
            out = (ctypes.c_uint8 * 20)()
            self.lib.sha0(bytes(payload), len(payload), out)
            return bytes(out)
        return struct.pack('<I', self.lib.crc32_dma(bytes(payload), len(payload)))


def make_board(kind, compute=None):
    from std_msgs.msg import UInt8MultiArray
    from boardsim import SimBoard
    compute = compute or ref_compute

    def handler(msg):
        data = bytes(msg.data)
        if len(data) < 4:
            return None
        reply = UInt8MultiArray()
        reply.data = list(data[:4] + compute(kind, data[4:]))
        return reply

    def cost(msg):
        return service_time(kind, max(0, len(msg.data) - 4))

    return SimBoard(f'board_{kind}', UInt8MultiArray, UInt8MultiArray, handler, cost, LINK_LATENCY)


def main():
    import os
    import rclpy
    kind = sys.argv[1] if len(sys.argv) > 1 else 'sort'
    if kind not in KINDS:
        raise SystemExit(f'用法：python3 boards.py {"|".join(KINDS)}')
    rclpy.init()
    compute = None if os.environ.get('FIRMWARE') == 'ref' else CAlgos()
    node = make_board(kind, compute)
    print(f'board_{kind} 已啟動，按 Ctrl-C 停止', flush=True)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
