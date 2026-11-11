"""替身 std_msgs/msg（評分與本機試跑用）。

欄位型別檢查比照真實 rclpy 產生的訊息類別：
  Int32 / UInt32 / UInt64 .data   必須是 int 且在該型別範圍內
  Float32 .data                   必須是 float（int 也會被拒絕）
  Bool .data                      必須是 bool
  String .data                    必須是 str
  *MultiArray .data               必須是 list / tuple / array.array 等序列，每個元素都是範圍內的 int
                                  （ctypes 陣列、numpy 陣列以外的奇怪物件會被拒絕）
  UInt8MultiArray .data 另外接受 bytes / bytearray
"""
import array


class _Layout:
    def __init__(self):
        self.dim = []
        self.data_offset = 0

    def __eq__(self, other):
        return isinstance(other, _Layout)


class _Msg:
    _ros_type = ''
    _fields = ('data',)

    def __init__(self, **kwargs):
        for name in self._fields:
            object.__setattr__(self, name, self._default(name))
        for name, value in kwargs.items():
            setattr(self, name, value)

    def __setattr__(self, name, value):
        if name not in self._fields:
            raise AttributeError(f'{self._ros_type} has no field {name!r}')
        if name == 'data':
            value = self._check(value)
        object.__setattr__(self, name, value)

    def _default(self, name):
        return _Layout() if name == 'layout' else self._zero

    def __eq__(self, other):
        return type(self) is type(other) and self.data == other.data

    def __repr__(self):
        return f"{self._ros_type.replace('/', '.')}(data={self.data!r})"


def _int_checker(lo, hi, label):
    def check(value):
        assert isinstance(value, int), "The 'data' field must be of type 'int'"
        assert lo <= value <= hi, f"The 'data' field must be an {label} in [{lo}, {hi}]"
        return value
    return staticmethod(check)


class Int32(_Msg):
    _ros_type = 'std_msgs/msg/Int32'
    _zero = 0
    _check = _int_checker(-2**31, 2**31 - 1, 'integer')


class UInt32(_Msg):
    _ros_type = 'std_msgs/msg/UInt32'
    _zero = 0
    _check = _int_checker(0, 2**32 - 1, 'unsigned integer')


class UInt64(_Msg):
    _ros_type = 'std_msgs/msg/UInt64'
    _zero = 0
    _check = _int_checker(0, 2**64 - 1, 'unsigned integer')


class Float32(_Msg):
    _ros_type = 'std_msgs/msg/Float32'
    _zero = 0.0

    @staticmethod
    def _check(value):
        assert isinstance(value, float), "The 'data' field must be of type 'float'"
        return value


class Bool(_Msg):
    _ros_type = 'std_msgs/msg/Bool'
    _zero = False

    @staticmethod
    def _check(value):
        assert isinstance(value, bool), "The 'data' field must be of type 'bool'"
        return value


class String(_Msg):
    _ros_type = 'std_msgs/msg/String'
    _zero = ''

    @staticmethod
    def _check(value):
        assert isinstance(value, str), "The 'data' field must be of type 'str'"
        return value


def _array_checker(lo, hi, typecode, allow_bytes=False):
    def check(value):
        if allow_bytes and isinstance(value, (bytes, bytearray)):
            return array.array(typecode, value)
        ok_container = isinstance(value, (list, tuple, array.array))
        assert ok_container, ("The 'data' field must be a set or sequence and each value of type 'int' "
                              f"(got {type(value).__name__})")
        for v in value:
            assert isinstance(v, int) and not isinstance(v, bool), \
                "The 'data' field must be a set or sequence and each value of type 'int'"
            assert lo <= v <= hi, f"The 'data' field values must be in [{lo}, {hi}]"
        return array.array(typecode, value)
    return staticmethod(check)


class _MultiArray(_Msg):
    _fields = ('layout', 'data')
    _zero = None

    def _default(self, name):
        return _Layout() if name == 'layout' else array.array(self._typecode)

    def __eq__(self, other):
        return type(self) is type(other) and list(self.data) == list(other.data)


class Int32MultiArray(_MultiArray):
    _ros_type = 'std_msgs/msg/Int32MultiArray'
    _typecode = 'i'
    _check = _array_checker(-2**31, 2**31 - 1, 'i')


class UInt32MultiArray(_MultiArray):
    _ros_type = 'std_msgs/msg/UInt32MultiArray'
    _typecode = 'I'
    _check = _array_checker(0, 2**32 - 1, 'I')


class UInt8MultiArray(_MultiArray):
    _ros_type = 'std_msgs/msg/UInt8MultiArray'
    _typecode = 'B'
    _check = _array_checker(0, 255, 'B', allow_bytes=True)
