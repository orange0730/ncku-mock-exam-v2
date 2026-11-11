"""模擬「一片開發板」：板上的韌體 + 它和 ROS 2 之間的連線（類似 micro-ROS agent）。

    /<name>/request ──(連線延遲)──> [板子：FIFO 排隊、一次處理一個] ──(連線延遲)──> /<name>/response

* handler(request_msg) -> response_msg 或 None：韌體邏輯（呼叫 C 函式庫或 Python 參考實作）。
* cost(request_msg) -> 秒：這筆工作在這片板子上要花多久（模擬板子的運算速度）。
* 只用真實 rclpy 也有的 API（timer、clock），所以在真的 ROS 2 上一樣能跑；
  在替身 rclpy 裡，時間是「模擬時間」，不會真的等。
"""
from collections import deque

from rclpy.node import Node


class SimBoard(Node):
    def __init__(self, name, req_type, resp_type, handler, cost, link_latency=0.001):
        super().__init__(name)
        self.handler = handler
        self.cost = cost
        self.link_latency = link_latency
        self.resp_type = resp_type
        self.sub = self.create_subscription(req_type, f'/{name}/request', self.on_request, 100)
        self.pub = self.create_publisher(resp_type, f'/{name}/response', 100)
        self.busy_until = 0.0
        self.pending = deque()
        # 統計（評分用）
        self.requests = []          # (收到時間, 原始 request)
        self.busy_time = 0.0
        self.max_queue = 0
        self.errors = []

    def now(self):
        return self.get_clock().now().nanoseconds / 1e9

    def on_request(self, msg):
        now = self.now()
        self.requests.append((now, msg))
        arrival = now + self.link_latency
        start = max(arrival, self.busy_until)
        work = self.cost(msg)
        finish = start + work
        self.busy_until = finish
        self.busy_time += work
        self.pending.append(finish)
        while self.pending and self.pending[0] <= now:
            self.pending.popleft()
        self.max_queue = max(self.max_queue, len(self.pending))
        try:
            response = self.handler(msg)
        except Exception as error:  # noqa: BLE001 - 韌體當掉
            self.errors.append(f'{type(error).__name__}: {error}')
            response = None
        if response is None:
            self.errors.append('韌體拒絕了這筆 request（回傳錯誤）')
            return
        self._send_later(finish + self.link_latency - now, response)

    def _send_later(self, delay, response):
        holder = {}

        def fire():
            holder['timer'].cancel()
            self.pub.publish(response)

        holder['timer'] = self.create_timer(max(delay, 1e-9), fire)
