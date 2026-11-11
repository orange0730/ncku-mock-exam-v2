"""大題一 Part C 參考解答。修正點以 [FIX n] 標示。"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, Int32MultiArray, UInt64          # [FIX 1] 影像是 UInt64

import bnn_lib


class EbnnNode(Node):
    def __init__(self):
        super().__init__('ebnn')
        self.bnn = bnn_lib.load()
        self.sub = self.create_subscription(UInt64, '/camera/image', self.on_image, 10)
        self.score_pub = self.create_publisher(Int32MultiArray, '/ebnn/scores', 10)   # [FIX 2] 名稱
        self.pred_pub = self.create_publisher(Int32, '/ebnn/prediction', 10)

    def on_image(self, msg):
        img = msg.data
        lo = img & 0xFFFFFFFF                    # [FIX 3] 低 32 位 = 像素 0..31 = img[0]
        hi = (img >> 32) & 0xFFFFFFFF
        pred, scores = self.bnn.infer_words(lo, hi)

        s = Int32MultiArray()                    # [FIX 4] 先發 scores
        s.data = [int(v) for v in scores]        # [FIX 5] ctypes 陣列不是序列，要轉成 list
        self.score_pub.publish(s)

        p = Int32()
        p.data = int(pred)
        self.pred_pub.publish(p)


def main():
    rclpy.init()
    node = EbnnNode()
    print('ebnn 已啟動，按 Ctrl-C 停止', flush=True)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
