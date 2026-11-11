"""大題二 Part B 參考解答：自適應排程的協調者。

起始檔的錯：
  1. header 欄位放錯位置：seq 要在 bits 31..16、first 在 15..8、count 在 7..0。
  2. 一次只送一張影像（等兩片都回來才送下一張），板子在等網路的時候是閒著的 → 沒有 pipeline。
  3. 固定對半切：board1 慢一倍，對半切時整體速度被 board1 拖住，跟只用 board0 一樣慢。
  4. 用回應到達的順序發布；改成 pipeline 之後順序可能亂掉，要依 seq 排好再發布。

排程策略（自己記帳：知道每片板子「預計什麼時候有空」）：
  * 兩片板子都閒著時，把一張影像的 32 個神經元依速度比例切開（找讓兩邊同時做完的切點）
    → 單張影像的「延遲」最低（約 26 ms，只用 board0 要 36 ms）。
  * 板子都還在忙（有積壓）時，整張影像丟給「最早能做完它」的那片板子
    → 每張只付一次 request 固定成本，「吞吐量」最高（比每張都切開快約 7%）。
這是分散式系統裡常見的取捨：資料平行（data parallel）重吞吐量，模型平行（model parallel）重延遲。
"""
import sys
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, UInt32MultiArray, UInt64

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'common'))
from model import argmax, scores_from_hidden  # noqa: E402

PER_NEURON = (0.001, 0.002)
OVERHEAD = 0.002
LINK = 0.001
FULL = 0xFFFFFFFF


def field_mask(first, count):
    return (((1 << count) - 1) << first) & FULL


class Coordinator(Node):
    def __init__(self):
        super().__init__('coordinator')
        self.sub = self.create_subscription(UInt64, '/camera/image', self.on_image, 100)
        self.req_pub = [self.create_publisher(UInt32MultiArray, f'/board{i}/request', 100) for i in (0, 1)]
        self.resp_sub = [self.create_subscription(UInt32MultiArray, f'/board{i}/response', self.on_response, 100)
                         for i in (0, 1)]
        self.pred_pub = self.create_publisher(Int32, '/ebnn/prediction', 100)
        self.free_at = [0.0, 0.0]      # 預估每片板子什麼時候做完手上的工作
        self.next_seq = 0
        self.next_out = 0
        self.missing = {}              # seq -> 還沒收到的神經元 mask
        self.hidden = {}               # seq -> 已收到的位元
        self.ready = {}                # seq -> 預測結果（等前面的 seq 發布完）

    def now(self):
        return self.get_clock().now().nanoseconds / 1e9

    def finish_time(self, board, count, now):
        return max(now + LINK, self.free_at[board]) + OVERHEAD + count * PER_NEURON[board]

    def plan(self, now):
        """回傳 [(board, first, count), ...]，並更新 free_at。"""
        both_idle = all(f <= now + LINK for f in self.free_at)
        if both_idle:
            best = None
            for a in range(1, 32):
                f0, f1 = self.finish_time(0, a, now), self.finish_time(1, 32 - a, now)
                if best is None or max(f0, f1) < best[0]:
                    best = (max(f0, f1), a, f0, f1)
            _, a, f0, f1 = best
            self.free_at = [f0, f1]
            return [(0, 0, a), (1, a, 32 - a)]
        board = min((0, 1), key=lambda b: self.finish_time(b, 32, now))
        self.free_at[board] = self.finish_time(board, 32, now)
        return [(board, 0, 32)]

    def on_image(self, msg):
        img = msg.data
        seq = self.next_seq
        self.next_seq = (seq + 1) & 0xFFFF
        self.missing[seq] = FULL
        self.hidden[seq] = 0
        for board, first, count in self.plan(self.now()):
            req = UInt32MultiArray()
            req.data = [(seq << 16) | (first << 8) | count, img & FULL, (img >> 32) & FULL]
            self.req_pub[board].publish(req)

    def on_response(self, msg):
        header, bits = msg.data[0], msg.data[1]
        seq, first, count = header >> 16, (header >> 8) & 0xFF, header & 0xFF
        if seq not in self.missing:
            return
        self.hidden[seq] |= bits
        self.missing[seq] &= ~field_mask(first, count) & FULL
        if self.missing[seq]:
            return
        del self.missing[seq]
        self.ready[seq] = argmax(scores_from_hidden(self.hidden.pop(seq)))
        while self.next_out in self.ready:            # 依影像順序發布
            out = Int32()
            out.data = self.ready.pop(self.next_out)
            self.pred_pub.publish(out)
            self.next_out = (self.next_out + 1) & 0xFFFF


def main():
    rclpy.init()
    node = Coordinator()
    print('coordinator 已啟動，按 Ctrl-C 停止', flush=True)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
