"""大題三 Part B：dispatcher node —— 要修改的檔案。

把每個工作同時交給三片板子（排序 / SHA-0 / CRC-32），收齊結果後依工作順序發布摘要。
完整規格見 README.md。這份是學長的版本：能跑，但格式、順序、分工、效率都有問題。
"""
from collections import deque
import struct
import zlib

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, UInt8MultiArray


class Dispatcher(Node):
    def __init__(self):
        super().__init__('dispatcher')
        self.sub = self.create_subscription(UInt8MultiArray, '/jobs/request', self.on_job, 100)
        self.sort_pub = self.create_publisher(UInt8MultiArray, '/board_sort/request', 100)
        self.sha_pub = self.create_publisher(UInt8MultiArray, '/board_sha0/request', 100)
        self.create_subscription(UInt8MultiArray, '/board_sort/response', self.on_sort, 100)
        self.create_subscription(UInt8MultiArray, '/board_sha0/response', self.on_sha, 100)
        self.result_pub = self.create_publisher(String, '/jobs/result', 100)
        self.queue = deque()
        self.current = None

    def on_job(self, msg):
        self.queue.append(bytes(msg.data))
        if self.current is None:
            self.next_job()

    def next_job(self):
        if not self.queue:
            self.current = None
            return
        data = self.queue.popleft()
        job_id = struct.unpack('>I', data[:4])[0]
        self.current = {'id': job_id, 'payload': data[4:]}
        req = UInt8MultiArray()
        req.data = list(data)
        self.sort_pub.publish(req)                  # 先排序，做完再算 SHA-0

    def on_sort(self, msg):
        data = bytes(msg.data)
        values = struct.unpack(f'<{(len(data) - 4) // 4}I', data[4:])
        self.current['sorted'] = values
        req = UInt8MultiArray()
        req.data = list(struct.pack('>I', self.current['id']) + self.current['payload'])
        self.sha_pub.publish(req)

    def on_sha(self, msg):
        job = self.current
        values = job['sorted']
        crc = zlib.crc32(job['payload'])
        text = (f"id={job['id']} min={values[0]} median={values[len(values) // 2 - 1]} max={values[-1]} "
                f"crc32={crc:X} sha0={bytes(msg.data[4:]).hex()}")
        out = String()
        out.data = text
        self.result_pub.publish(out)
        self.next_job()


def main():
    rclpy.init()
    node = Dispatcher()
    print('dispatcher 已啟動，按 Ctrl-C 停止', flush=True)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
