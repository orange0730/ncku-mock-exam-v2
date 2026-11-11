"""評分程式用：切換成替身 rclpy（common/fake_ros），並提供一個乾淨的 ROS graph。"""
import sys
from pathlib import Path

FAKE = Path(__file__).resolve().parent / 'fake_ros'


def use_fake_ros():
    for name in list(sys.modules):
        if name == 'rclpy' or name.startswith(('rclpy.', 'std_msgs')):
            del sys.modules[name]
    if str(FAKE) in sys.path:
        sys.path.remove(str(FAKE))
    sys.path.insert(0, str(FAKE))
    import rclpy
    from rclpy import _graph
    from rclpy.node import Node
    from std_msgs import msg
    return rclpy, _graph.GRAPH, Node, msg


def fresh_graph(rclpy, graph):
    graph.reset()
    graph.raise_errors = False
    rclpy.try_shutdown()
    rclpy.init()
