"""大題二 Part B：協調者 node —— 要修改的檔案。

把影像的推論工作分給兩片板子，收回結果、組合、依影像順序發布預測。完整規格見 README.md。

這份是「先求有」的版本：固定對半切、一次只處理一張影像，而且有 bug，連最基本的都跑不完。
"""
from collections import deque
import sys
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, UInt32MultiArray, UInt64

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'common'))
from model import argmax, scores_from_hidden  # noqa: E402  第二層（很便宜，協調者自己算）


class Coordinator(Node):
    def __init__(self):
        super().__init__('coordinator')
        self.sub = self.create_subscription(UInt64, '/camera/image', self.on_image, 100)
        self.req_pub = [self.create_publisher(UInt32MultiArray, f'/board{i}/request', 100) for i in (0, 1)]
        self.resp_sub = [self.create_subscription(UInt32MultiArray, f'/board{i}/response', self.on_response, 100)
                         for i in (0, 1)]
        self.pred_pub = self.create_publisher(Int32, '/ebnn/prediction', 100)
        self.queue = deque()
        self.busy = False
        self.seq = 0
        self.parts = {}

    def on_image(self, msg):
        self.queue.append(msg.data)
        self.try_send()

    def try_send(self):
        if self.busy or not self.queue:
            return
        img = self.queue.popleft()
        seq = self.seq
        self.seq += 1
        for board, (first, count) in enumerate([(0, 16), (16, 16)]):
            header = (first << 16) | (seq << 8) | count
            m = UInt32MultiArray()
            m.data = [header, img & 0xFFFFFFFF, img >> 32]
            self.req_pub[board].publish(m)
        self.busy = True

    def on_response(self, msg):
        header, bits = msg.data
        seq = header >> 16
        self.parts.setdefault(seq, []).append(bits)
        if len(self.parts[seq]) == 2:
            hidden = sum(self.parts.pop(seq))
            out = Int32()
            out.data = argmax(scores_from_hidden(hidden))
            self.pred_pub.publish(out)
            self.busy = False
            self.try_send()


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
