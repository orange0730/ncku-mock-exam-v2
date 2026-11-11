"""替身 rclpy.node.Node。介面與真實 rclpy 相同的子集。"""
from ._graph import GRAPH, normalize_topic, type_name


class _Logger:
    def __init__(self, name):
        self.name = name

    def _log(self, level, msg):
        if not GRAPH.raise_errors:   # 評分時保持安靜
            return
        print(f'[{level}] [{self.name}]: {msg}', flush=True)

    def debug(self, msg, **_):
        pass

    def info(self, msg, **_):
        self._log('INFO', msg)

    def warning(self, msg, **_):
        self._log('WARN', msg)

    warn = warning

    def error(self, msg, **_):
        self._log('ERROR', msg)


class Publisher:
    def __init__(self, node, msg_type, topic, qos):
        self.node, self.msg_type, self.topic, self.qos = node, msg_type, topic, qos

    def publish(self, msg):
        if not isinstance(msg, self.msg_type):
            # 與真實 rclpy 相同：型別不符直接丟 TypeError
            raise TypeError(f'Expected {type_name(self.msg_type)}, got {type(msg).__name__}')
        GRAPH.deliver(self, msg)

    def get_subscription_count(self):
        return GRAPH.topic_info(self.topic)['subscription_count']


class Subscription:
    def __init__(self, node, msg_type, topic, callback, qos):
        self.node, self.msg_type, self.topic, self.callback, self.qos = node, msg_type, topic, callback, qos


class Timer:
    def __init__(self, period, callback):
        if period <= 0:
            raise ValueError('timer period must be > 0')
        self.period = float(period)
        self.callback = callback
        self.next_fire = GRAPH.now + self.period
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    @property
    def timer_period_ns(self):
        return int(self.period * 1e9)


class Node:
    def __init__(self, node_name, **_):
        if not node_name or not node_name.replace('_', 'a').isalnum() or node_name[0].isdigit():
            raise ValueError(f'Invalid node name: {node_name!r}')
        self._name = node_name
        self._logger = _Logger(node_name)
        GRAPH.nodes.append(self)

    def get_name(self):
        return self._name

    def get_logger(self):
        return self._logger

    def get_clock(self):
        return _Clock()

    def create_publisher(self, msg_type, topic, qos_profile, **_):
        pub = Publisher(self, msg_type, normalize_topic(topic), qos_profile)
        GRAPH.publishers.append(pub)
        return pub

    def create_subscription(self, msg_type, topic, callback, qos_profile, **_):
        sub = Subscription(self, msg_type, normalize_topic(topic), callback, qos_profile)
        GRAPH.subscriptions.append(sub)
        return sub

    def create_timer(self, timer_period_sec, callback, **_):
        timer = Timer(timer_period_sec, callback)
        timer.node = self
        GRAPH.timers.append(timer)
        return timer

    def destroy_node(self):
        GRAPH.publishers = [p for p in GRAPH.publishers if p.node is not self]
        GRAPH.subscriptions = [s for s in GRAPH.subscriptions if s.node is not self]
        GRAPH.timers = [t for t in GRAPH.timers if getattr(t, 'node', None) is not self]
        if self in GRAPH.nodes:
            GRAPH.nodes.remove(self)


class _Clock:
    def now(self):
        return _Time(GRAPH.now)


class _Time:
    def __init__(self, seconds):
        self.nanoseconds = int(seconds * 1e9)
