"""替身 rclpy 的「ROS graph」：記錄 node、publisher、subscription、timer。"""
import copy
import re
import time

_NAME_RE = re.compile(r'^/?[A-Za-z_~][A-Za-z0-9_~/]*$')


class InvalidTopicNameException(Exception):
    pass


def type_name(msg_type):
    return getattr(msg_type, '_ros_type', msg_type.__name__)


def normalize_topic(name):
    if not isinstance(name, str) or not _NAME_RE.match(name) or '//' in name \
            or (len(name) > 1 and name.endswith('/')):
        raise InvalidTopicNameException(f'Invalid topic name: {name!r}')
    return name if name.startswith('/') else '/' + name


class Graph:
    def __init__(self):
        self.reset()

    def reset(self):
        self.nodes = []
        self.publishers = []
        self.subscriptions = []
        self.timers = []
        self.log = []          # (topic, msg) in publish order
        self.log_time = []     # 每筆 log 對應的模擬時間（秒）
        self.errors = []       # 例外：callback 內拋出的錯誤等
        self.now = 0.0
        self.raise_errors = True

    # ---------------------------------------------------------- CLI 風格查詢
    def node_names(self):
        return sorted('/' + n.get_name() for n in self.nodes)

    def topic_info(self, topic):
        pubs = [p for p in self.publishers if p.topic == topic]
        subs = [s for s in self.subscriptions if s.topic == topic]
        types = sorted({type_name(x.msg_type) for x in pubs + subs})
        return dict(types=types, publisher_count=len(pubs), subscription_count=len(subs))

    def topics(self):
        return sorted({x.topic for x in self.publishers + self.subscriptions})

    def node_info(self, node_name):
        name = node_name.lstrip('/')
        subs = [(s.topic, type_name(s.msg_type)) for s in self.subscriptions if s.node.get_name() == name]
        pubs = [(p.topic, type_name(p.msg_type)) for p in self.publishers if p.node.get_name() == name]
        return dict(subscribers=sorted(subs), publishers=sorted(pubs))

    # ---------------------------------------------------------- 傳遞
    def deliver(self, publisher, msg):
        self.log.append((publisher.topic, copy.deepcopy(msg)))
        self.log_time.append(self.now)
        for sub in list(self.subscriptions):
            if sub.topic != publisher.topic:
                continue
            if sub.msg_type is not publisher.msg_type:
                # 真實 ROS 2：型別不同的兩端根本不會連上，訊息就這樣不見了。
                continue
            try:
                sub.callback(copy.deepcopy(msg))
            except Exception as error:  # noqa: BLE001 - 模擬 node 崩潰
                self.errors.append(error)
                if self.raise_errors:
                    raise

    def advance(self, seconds, real_time=False):
        end = self.now + seconds
        while True:
            due = [t for t in self.timers if not t.cancelled and t.next_fire <= end]
            if not due:
                break
            timer = min(due, key=lambda t: t.next_fire)
            if real_time and timer.next_fire > self.now:
                time.sleep(timer.next_fire - self.now)
            self.now = timer.next_fire
            timer.next_fire += timer.period
            timer.callback()
        if real_time and end > self.now:
            time.sleep(end - self.now)
        self.now = end


GRAPH = Graph()
