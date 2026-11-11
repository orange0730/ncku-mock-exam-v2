"""大題一 Part C：eBNN 推論 node —— 要修改的檔案。

規格（完整版見 README.md）：
  node 名稱 ebnn，類別 EbnnNode（建構子不帶參數）
  訂閱 /camera/image     std_msgs/msg/UInt64          一張 8x8 影像（bit r*8+c = 像素 (r, c)）
  發布 /ebnn/scores      std_msgs/msg/Int32MultiArray 10 個分數
  發布 /ebnn/prediction  std_msgs/msg/Int32           辨識結果 0..9
  每張影像：先發 scores，再發 prediction，各一次。
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, Int32MultiArray, UInt32

import bnn_lib


class EbnnNode(Node):
    def __init__(self):
        super().__init__('ebnn')
        self.bnn = bnn_lib.load()
        self.sub = self.create_subscription(UInt32, '/camera/image', self.on_image, 10)
        self.pred_pub = self.create_publisher(Int32, '/ebnn/prediction', 10)
        self.score_pub = self.create_publisher(Int32MultiArray, '/ebnn/score', 10)

    def on_image(self, msg):
        img = msg.data
        hi = img & 0xFFFFFFFF
        lo = img >> 32
        pred, scores = self.bnn.infer_words(lo, hi)

        p = Int32()
        p.data = pred
        self.pred_pub.publish(p)

        s = Int32MultiArray()
        s.data = scores
        self.score_pub.publish(s)


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
