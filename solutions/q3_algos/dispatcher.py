"""大題三 Part B 參考解答。

起始檔的錯：
  1. job id 是 little-endian（'<I'），不是 big-endian。
  2. CRC-32 在 dispatcher 自己用 zlib 算 —— 規定每個演算法要在「自己的那片板子」上跑。
  3. 排序做完才送 SHA-0，而且一次只處理一個工作：三片板子大部分時間都在閒置。
     → 三個 request 同時送出（平行），也不等上一個工作做完就送下一個（pipeline）。
  4. median 是排序後 index n // 2 的元素（不是 n // 2 - 1）。
  5. crc32 要 8 位小寫十六進位、補零（'{:08x}'）。
  6. pipeline 之後，結果要依「工作到達的順序」發布，先收齊的要先等著。
"""
import struct

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, UInt8MultiArray

KINDS = ('sort', 'sha0', 'crc')


class Dispatcher(Node):
    def __init__(self):
        super().__init__('dispatcher')
        self.sub = self.create_subscription(UInt8MultiArray, '/jobs/request', self.on_job, 100)
        self.req = {k: self.create_publisher(UInt8MultiArray, f'/board_{k}/request', 100) for k in KINDS}
        for k in KINDS:
            self.create_subscription(UInt8MultiArray, f'/board_{k}/response',
                                     lambda msg, k=k: self.on_response(k, msg), 100)
        self.result_pub = self.create_publisher(String, '/jobs/result', 100)
        self.order = []          # 工作到達的順序（job id）
        self.partial = {}        # job id -> {kind: 結果 bytes}

    def on_job(self, msg):
        data = bytes(msg.data)
        job_id = struct.unpack('<I', data[:4])[0]
        self.order.append(job_id)
        self.partial[job_id] = {}
        for k in KINDS:                              # 三片板子同時開工
            req = UInt8MultiArray()
            req.data = list(data)
            self.req[k].publish(req)

    def on_response(self, kind, msg):
        data = bytes(msg.data)
        job_id = struct.unpack('<I', data[:4])[0]
        if job_id in self.partial:
            self.partial[job_id][kind] = data[4:]
        self.flush()

    def flush(self):
        while self.order and len(self.partial[self.order[0]]) == len(KINDS):
            job_id = self.order.pop(0)
            r = self.partial.pop(job_id)
            n = len(r['sort']) // 4
            values = struct.unpack(f'<{n}I', r['sort'])
            crc = struct.unpack('<I', r['crc'])[0]
            out = String()
            out.data = (f'id={job_id} min={values[0]} median={values[n // 2]} max={values[-1]} '
                        f'crc32={crc:08x} sha0={r["sha0"].hex()}')
            self.result_pub.publish(out)


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
