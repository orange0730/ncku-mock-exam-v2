"""極簡 rclpy 替身（只供本模擬考評分與本機試跑用）。

真正的 ROS 2 請在官方 Docker container 裡跑。這個替身只模擬：
  * rclpy.init / ok / spin / spin_once / shutdown / try_shutdown
  * Node.create_publisher / create_subscription / create_timer / get_logger
  * 同一個 process 內的 topic 傳遞（同步呼叫 callback）
並且刻意保留真實 rclpy 會擋下的錯誤：
  * 訊息欄位型別錯誤（例如把 float 塞進 Int32.data）
  * publish 的訊息型別與 publisher 宣告的型別不同
  * 不合法的 topic 名稱
"""
import time

from . import _graph

_initialized = False


def init(args=None, context=None):
    global _initialized
    _initialized = True


def ok(context=None):
    return _initialized


def shutdown(context=None):
    global _initialized
    if not _initialized:
        raise RuntimeError('rclpy.shutdown() called without init')
    _initialized = False


def try_shutdown(context=None):
    global _initialized
    _initialized = False


def spin_once(node, executor=None, timeout_sec=None):
    _graph.GRAPH.advance(timeout_sec if timeout_sec is not None else 0.1, real_time=True)


def spin(node, executor=None):
    """以真實時間觸發 timer，直到 Ctrl-C。"""
    while _initialized:
        _graph.GRAPH.advance(0.01, real_time=True)
