"""評分用：配置「緊貼著守護頁（guard page）」的 ctypes 陣列，用來抓陣列越界。

    arr = guarded(ctypes.c_int32, 10)          # 10 個元素，最後一個元素後面緊接著一個不可讀寫的分頁
    arr = guarded(ctypes.c_uint8, n, data)     # 也可以給初值

C 程式只要多讀或多寫一個元素（例如 for (k = 0; k <= 10; k++)），就會碰到守護頁，
作業系統立刻送出 SIGSEGV，程式當掉，評分程式就知道「這裡越界了」。
不靠運氣：不管越界的那格記憶體剛好是什麼值，一定抓得到。

需要 mmap + mprotect（Linux / macOS）。其他平台退回一般陣列，只能靠哨兵值檢查。
"""
import ctypes
import mmap
import sys

PAGE = mmap.PAGESIZE
_keep = []          # 讓 mmap 物件活著，直到 process 結束

try:
    _libc = ctypes.CDLL(None)
    _mprotect = _libc.mprotect
    _mprotect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    _mprotect.restype = ctypes.c_int
    AVAILABLE = sys.platform != 'win32'
except (OSError, AttributeError, TypeError):
    AVAILABLE = False


def guarded(ctype, n, values=None):
    """回傳長度 n 的 ctypes 陣列，陣列的「最後一個 byte 之後」就是守護頁。"""
    if not AVAILABLE:
        arr = (ctype * max(n, 1))()
        if values is not None:
            arr[:len(values)] = list(values)
        return arr
    size = ctypes.sizeof(ctype) * n
    pages = (size + PAGE - 1) // PAGE + 1
    mem = mmap.mmap(-1, pages * PAGE, prot=mmap.PROT_READ | mmap.PROT_WRITE)
    base = ctypes.addressof(ctypes.c_char.from_buffer(mem))
    guard_page = base + (pages - 1) * PAGE
    if _mprotect(guard_page, PAGE, 0) != 0:           # 0 = PROT_NONE
        raise OSError('mprotect failed')
    arr = (ctype * n).from_address(guard_page - size)
    _keep.append(mem)
    if values is not None:
        arr[:] = list(values)
    return arr


def guarded_bytes(data):
    """把 bytes 放進緊貼守護頁的緩衝區，回傳可直接傳給 C 的指標（c_char_p 相容）。"""
    arr = guarded(ctypes.c_uint8, len(data), data)
    return ctypes.cast(arr, ctypes.c_char_p), arr
