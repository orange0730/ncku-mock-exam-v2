"""RP2350 PIO 子集模擬器（教學用，Python 3.9+，只用標準函式庫）。

與第一份作業 (homework_pio) 的「自創 ISA」不同，這裡盡量貼近「真正的」PIO 指令語意，
讓你練習的是考場開發板上會用到的那一套思考方式。支援的子集：

  jmp  [cond] label     cond: (無) !x  x--  !y  y--  x!=y  !osre
  out  dest, n          dest: x y null isr        n: 1..32
  in   src, n           src : x y null isr osr    n: 1..32
  push [iffull] [block]
  pull [ifempty] [block|noblock]
  mov  dest, [op]src    dest: x y isr osr   src: x y null isr osr   op: ! 或 ~（反相）、::（位元反轉）
  set  dest, v          dest: x y           v: 0..31
  nop
  任何指令後可加 [n] 延遲（0..31 個額外週期）

組譯器指示（directive）：
  .program name   .wrap_target   .wrap
  .out_shift right|left [auto] [threshold]   ← 代替 C 端的 sm_config_set_out_shift()
  .in_shift  left|right [auto] [threshold]   ← 代替 C 端的 sm_config_set_in_shift()
  預設：.out_shift right 32（不 autopull）、.in_shift left 32（不 autopush）
  註解用 ; 或 //

時間模型：每個 tick 依序 (1) host 可能放一個 word 進 TX FIFO (2) host 可能從 RX FIFO 取一個
(3) state machine 嘗試執行一條指令。成功執行花 1 + delay 個週期；stall 不算執行週期。
FIFO 深度各 4。指令記憶體上限 32 條。

不支援：pins / side-set / irq / wait / exec / status / FIFO join ── 本題用不到。
"""
import re
from collections import deque

MASK = 0xFFFFFFFF
MAX_INSTR = 32

JMP_CONDS = {'': 'always', '!x': '!x', 'x--': 'x--', '!y': '!y', 'y--': 'y--',
             'x!=y': 'x!=y', '!osre': '!osre'}


class PioError(Exception):
    pass


def bitrev32(v):
    return int(f'{v & MASK:032b}'[::-1], 2)


def parse_number(text, line_no):
    try:
        return int(text, 0)
    except ValueError:
        raise PioError(f'line {line_no}: 不是數字：{text!r}') from None


def assemble(source):
    """回傳 dict(program=[(op, args, delay, line_no)], wrap_target, wrap, config)。"""
    labels, raw = {}, []
    config = dict(out_right=True, autopull=False, pull_thresh=32,
                  in_left=True, autopush=False, push_thresh=32)
    wrap_target = wrap = None
    for line_no, line in enumerate(source.splitlines(), 1):
        line = line.split(';', 1)[0].split('//', 1)[0].strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith('.'):
            parts = lower.replace(',', ' ').split()
            name = parts[0]
            if name == '.program':
                continue
            if name == '.wrap_target':
                wrap_target = len(raw)
            elif name == '.wrap':
                if not raw:
                    raise PioError(f'line {line_no}: .wrap 之前沒有指令')
                wrap = len(raw) - 1
            elif name in ('.out_shift', '.in_shift'):
                rest = parts[1:]
                if not rest or rest[0] not in ('left', 'right'):
                    raise PioError(f'line {line_no}: {name} 要指定 left 或 right')
                auto = 'auto' in rest
                nums = [parse_number(p, line_no) for p in rest[1:] if p != 'auto']
                thresh = nums[0] if nums else 32
                if not 1 <= thresh <= 32:
                    raise PioError(f'line {line_no}: threshold 必須是 1..32')
                if name == '.out_shift':
                    config.update(out_right=rest[0] == 'right', autopull=auto, pull_thresh=thresh)
                else:
                    config.update(in_left=rest[0] == 'left', autopush=auto, push_thresh=thresh)
            else:
                raise PioError(f'line {line_no}: 不支援的 directive {parts[0]}')
            continue
        m = re.match(r'^(?:public\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*:(.*)$', line)
        if m:
            label = m.group(1)
            if label in labels:
                raise PioError(f'line {line_no}: label {label} 重複')
            labels[label] = len(raw)
            line = m.group(2).strip()
            if not line:
                continue
        delay = 0
        dm = re.search(r'\[\s*(\w+)\s*\]\s*$', line)
        if dm:
            delay = parse_number(dm.group(1), line_no)
            if not 0 <= delay <= 31:
                raise PioError(f'line {line_no}: delay 必須是 0..31')
            line = line[:dm.start()].strip()
        raw.append((line_no, line, delay))

    if not raw:
        raise PioError('程式沒有任何指令')
    if len(raw) > MAX_INSTR:
        raise PioError(f'指令數 {len(raw)} 超過 PIO 指令記憶體上限 {MAX_INSTR}')

    program = []
    for line_no, text, delay in raw:
        tokens = text.replace(',', ' ').split()
        op, args = tokens[0].lower(), [t.lower() if t not in labels else t for t in tokens[1:]]
        if op == 'nop':
            op, args = 'mov', ['y', 'y']
        if op == 'jmp':
            if len(args) == 1:
                cond, target = '', args[0]
            elif len(args) == 2:
                cond, target = args
            else:
                raise PioError(f'line {line_no}: jmp 語法為 jmp [cond] label')
            if cond not in JMP_CONDS:
                raise PioError(f'line {line_no}: 不支援的 jmp 條件 {cond}')
            if target not in labels:
                raise PioError(f'line {line_no}: 找不到 label {target}')
            parsed = (cond, labels[target])
        elif op in ('out', 'in'):
            if len(args) != 2:
                raise PioError(f'line {line_no}: {op} 語法為 {op} dest/src, bits')
            where, n = args[0], parse_number(args[1], line_no)
            allowed = ('x', 'y', 'null', 'isr') if op == 'out' else ('x', 'y', 'null', 'isr', 'osr')
            if where not in allowed:
                raise PioError(f'line {line_no}: {op} 不支援 {where}（本模擬器支援 {allowed}）')
            if not 1 <= n <= 32:
                raise PioError(f'line {line_no}: bit 數必須是 1..32')
            parsed = (where, n)
        elif op in ('push', 'pull'):
            flags = set(args)
            ok = {'push': {'iffull', 'block'}, 'pull': {'ifempty', 'block', 'noblock'}}[op]
            if not flags <= ok:
                raise PioError(f'line {line_no}: {op} 不支援 {sorted(flags - ok)}')
            if op == 'push' and 'noblock' in flags:
                raise PioError(f'line {line_no}: 本模擬器不支援 push noblock')
            parsed = (('iffull' in flags) or ('ifempty' in flags), 'noblock' not in flags)
        elif op == 'mov':
            if len(args) == 2 and args[1] in ('!', '~', '::'):
                raise PioError(f'line {line_no}: 運算子要緊貼來源，例如 mov x, ~y')
            if len(args) == 3 and args[1] in ('!', '~', '::'):
                args = [args[0], args[1] + args[2]]
            if len(args) != 2:
                raise PioError(f'line {line_no}: mov 語法為 mov dest, [op]src')
            dest, src = args
            mod = ''
            for prefix in ('::', '!', '~'):
                if src.startswith(prefix):
                    mod, src = ('rev' if prefix == '::' else 'inv'), src[len(prefix):]
                    break
            if dest not in ('x', 'y', 'isr', 'osr'):
                raise PioError(f'line {line_no}: mov 目的地不支援 {dest}')
            if src not in ('x', 'y', 'null', 'isr', 'osr'):
                raise PioError(f'line {line_no}: mov 來源不支援 {src}')
            parsed = (dest, mod, src)
        elif op == 'set':
            if len(args) != 2 or args[0] not in ('x', 'y'):
                raise PioError(f'line {line_no}: set 語法為 set x|y, 0..31')
            v = parse_number(args[1], line_no)
            if not 0 <= v <= 31:
                raise PioError(f'line {line_no}: set 的值必須是 0..31（只有 5 bits）')
            parsed = (args[0], v)
        else:
            raise PioError(f'line {line_no}: 不認得的指令 {op}')
        program.append((op, parsed, delay, line_no))

    return dict(program=program,
                wrap_target=0 if wrap_target is None else wrap_target,
                wrap=len(program) - 1 if wrap is None else wrap,
                config=config)


SCHEDULES = {
    'fast': lambda t: (True, True),
    'slow_tx': lambda t: (t % 97 == 0, True),
    'slow_rx': lambda t: (True, t % 61 == 0),
    'bursty': lambda t: (t % 211 < 6, t % 149 in (0, 1, 2, 3)),
}


class StateMachine:
    def __init__(self, image):
        self.prog = image['program']
        self.wrap_target, self.wrap = image['wrap_target'], image['wrap']
        c = image['config']
        self.out_right, self.autopull, self.pull_thresh = c['out_right'], c['autopull'], c['pull_thresh']
        self.in_left, self.autopush, self.push_thresh = c['in_left'], c['autopush'], c['push_thresh']
        self.x = self.y = self.isr = self.osr = 0
        self.in_count = 0
        self.out_count = 32        # 開機時 OSR 是空的
        self.pc = 0
        self.delay_left = 0
        self.cycles = 0
        self.tx, self.rx = deque(), deque()

    # ----------------------------------------------------------- 小工具
    def _shift_out(self, n):
        if self.out_right:
            data = self.osr & ((1 << n) - 1) if n < 32 else self.osr
            self.osr = (self.osr >> n) if n < 32 else 0
        else:
            data = self.osr >> (32 - n)
            self.osr = (self.osr << n) & MASK if n < 32 else 0
        self.out_count = min(32, self.out_count + n)
        return data

    def _shift_in(self, value, n):
        value &= (1 << n) - 1 if n < 32 else MASK
        if n == 32:
            self.isr = value
        elif self.in_left:
            self.isr = ((self.isr << n) | value) & MASK
        else:
            self.isr = (self.isr >> n) | (value << (32 - n))
        self.in_count = min(32, self.in_count + n)

    def _read(self, src):
        return {'x': self.x, 'y': self.y, 'null': 0, 'isr': self.isr, 'osr': self.osr}[src]

    def _write(self, dest, value):
        value &= MASK
        if dest == 'x':
            self.x = value
        elif dest == 'y':
            self.y = value
        elif dest == 'isr':
            self.isr, self.in_count = value, 0
        elif dest == 'osr':
            self.osr, self.out_count = value, 0

    # ----------------------------------------------------------- 執行一個 tick
    def step(self):
        """回傳 'run'、'delay' 或 'stall:<原因>'。"""
        if self.delay_left:
            self.delay_left -= 1
            self.cycles += 1
            return 'delay'
        op, a, delay, _ = self.prog[self.pc]
        nxt = self.pc + 1 if self.pc != self.wrap else self.wrap_target

        if op == 'jmp':
            cond, target = a
            take = {'': True, '!x': self.x == 0, '!y': self.y == 0, 'x!=y': self.x != self.y,
                    '!osre': self.out_count < self.pull_thresh,
                    'x--': self.x != 0, 'y--': self.y != 0}[cond]
            if cond == 'x--':
                self.x = (self.x - 1) & MASK
            elif cond == 'y--':
                self.y = (self.y - 1) & MASK
            if take:
                nxt = target
        elif op == 'out':
            dest, n = a
            if self.autopull and self.out_count >= self.pull_thresh:
                if not self.tx:
                    return 'stall:out-autopull'
                self.osr, self.out_count = self.tx.popleft(), 0
            data = self._shift_out(n)
            if dest == 'isr':
                self.isr, self.in_count = data, n
            elif dest != 'null':
                self._write(dest, data)
            if self.autopull and self.out_count >= self.pull_thresh and self.tx:
                self.osr, self.out_count = self.tx.popleft(), 0
        elif op == 'in':
            src, n = a
            if self.autopush and self.in_count + n >= self.push_thresh and len(self.rx) >= 4:
                return 'stall:in-autopush'
            self._shift_in(self._read(src), n)
            if self.autopush and self.in_count >= self.push_thresh:
                self.rx.append(self.isr)
                self.isr = self.in_count = 0
        elif op == 'push':
            if_full, _block = a
            if not (if_full and self.in_count < self.push_thresh):
                if len(self.rx) >= 4:
                    return 'stall:push'
                self.rx.append(self.isr)
                self.isr = self.in_count = 0
        elif op == 'pull':
            if_empty, block = a
            skip = (if_empty or self.autopull) and self.out_count < self.pull_thresh
            if not skip:
                if self.tx:
                    self.osr, self.out_count = self.tx.popleft(), 0
                elif block:
                    return 'stall:pull'
                else:
                    self.osr, self.out_count = self.x, 0
        elif op == 'mov':
            dest, mod, src = a
            v = self._read(src)
            if mod == 'inv':
                v = ~v & MASK
            elif mod == 'rev':
                v = bitrev32(v)
            self._write(dest, v)
        elif op == 'set':
            self._write(a[0], a[1])
        if nxt >= len(self.prog):
            raise PioError('PC 跑出程式尾端：最後一條指令後面要有 .wrap 或 jmp')
        self.pc = nxt
        self.cycles += 1
        self.delay_left = delay
        return 'run'


def run(image, words, schedule='fast', expected_outputs=None, quiet_ticks=64, max_ticks=None):
    """把 words 依 schedule 餵進去，回傳 (outputs, cycles, ticks)。

    結束條件：所有輸入都已送入、TX/RX 都空、且 state machine 連續 quiet_ticks 個 tick
    卡在等待 TX（pull 或 autopull）。超過 max_ticks 視為逾時。
    """
    sm = StateMachine(image)
    feed_drain = SCHEDULES[schedule]
    outputs, sent, quiet = [], 0, 0
    limit = max_ticks or max(20000, 3000 * len(words))
    max_out = None if expected_outputs is None else expected_outputs
    for tick in range(limit):
        feed, drain = feed_drain(tick)
        if feed and sent < len(words) and len(sm.tx) < 4:
            sm.tx.append(words[sent] & MASK)
            sent += 1
        if drain and sm.rx:
            outputs.append(sm.rx.popleft())
        status = sm.step()
        if status in ('stall:pull', 'stall:out-autopull') and sent == len(words) and not sm.tx and not sm.rx:
            quiet += 1
            if quiet >= quiet_ticks:
                return outputs, sm.cycles, tick + 1
        else:
            quiet = 0
        if max_out is not None and len(outputs) > max_out:
            raise PioError(f'輸出比預期多（已超過 {max_out} 個 word）')
    raise PioError(f'逾時：{limit} ticks 內沒有處理完並停在等待輸入（可能卡在 push、無窮迴圈或輸出太少）')


def main():
    import argparse
    import sys
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='把幾個 word 餵給 PIO 程式並印出輸出與週期數')
    parser.add_argument('program')
    parser.add_argument('words', nargs='*', default=['0x12345678'])
    parser.add_argument('--schedule', default='fast', choices=sorted(SCHEDULES))
    parser.add_argument('--trace', action='store_true', help='逐 tick 印出狀態（只建議少量輸入時用）')
    args = parser.parse_args()
    with open(args.program, encoding='utf-8') as f:
        image = assemble(f.read())
    words = [int(w, 0) & MASK for w in args.words]
    if args.trace:
        sm = StateMachine(image)
        pending = list(words)
        for tick in range(400):
            if pending and len(sm.tx) < 4:
                sm.tx.append(pending.pop(0))
            if sm.rx:
                print(f'          host 讀到 RX: 0x{sm.rx.popleft():08x}')
            pc = sm.pc
            status = sm.step()
            print(f'tick {tick:3} pc={pc:2} {status:18} x={sm.x:08x} y={sm.y:08x} '
                  f'osr={sm.osr:08x}({sm.out_count:2}) isr={sm.isr:08x}({sm.in_count:2}) rx={[hex(v) for v in sm.rx]}')
            if status == 'stall:pull' and not pending and not sm.tx:
                break
        return 0
    outputs, cycles, ticks = run(image, words, args.schedule)
    print(f'{len(image["program"])} instructions; {cycles} executed cycles; {ticks} ticks')
    for v in outputs:
        print(f'0x{v:08x}  ({v})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
