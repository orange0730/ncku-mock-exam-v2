# 02 位元運算、RISC-V 與 RP2350 PIO

對應：官方練習 `demo/section2-2`（`demo_asm.c`、`demo_pio.pio`）、參考文獻 [1] [4] [7]、RISC-V 規格書、v1 第二題、v2 大題一（XNOR-popcount 與 PIO）。
`homework_pio/reading/tutorial.txt` 已有很完整的入門（二進位、六個運算子、mask 配方、echo 逐步追蹤），這裡不重複，重點放在**考場上會出錯的地方**與**三種層次的對照**。

---

## 1. C 位元運算：會讓你「看起來對」的陷阱

### 1.1 優先順序（[1] cppreference）

由高到低，只列跟位元有關的：

```text
~  !  (一元)
*  /  %
+  -
<<  >>
<  <=  >  >=
==  !=
&
^
|
&&
||
?:
=  &=  |=  ^=  <<=  >>=
```

| 你寫的 | 編譯器看到的 | 要寫成 |
|---|---|---|
| `x & (x - 1) == 0` | `x & ((x - 1) == 0)` | `(x & (x - 1)) == 0` |
| `x & mask != 0` | `x & (mask != 0)` | `(x & mask) != 0` |
| `1 << n + 1` | `1 << (n + 1)` | 想清楚要哪個，加括號 |
| `a << 8 + b` | `a << (8 + b)` | `(a << 8) + b` 或 `(a << 8) \| b` |
| `flags \| FLAG_A && ok` | `(flags \| FLAG_A) && ok` | 位元 OR 與邏輯 AND 不要混用 |

> `gcc -Wall` 會對前兩個發出 `-Wparentheses` 警告。**看到警告就去看**，這就是第二題 Part A 有 2 分「零警告」的原因。

### 1.2 未定義行為（UB）與實作定義

| 寫法 | 問題 | 安全寫法 |
|---|---|---|
| `1 << 31` | `1` 是 signed int，移到符號位是 UB | `1u << 31` |
| `x << 32`、`x >> 32`（32-bit x） | 移位量 >= 寬度是 UB。x86 與 RISC-V 的硬體都只取移位量的低 5 位，所以 `x >> 32` 常常「剛好」等於 `x` | 寬度 32 特別處理；`rotl` 用 `& 31` |
| `(1u << width) - 1` 當 mask，width 可能是 32 | 同上 | `width >= 32 ? 0xFFFFFFFFu : (1u << width) - 1u` |
| 對負的 signed 右移 | 實作定義（多半是算術右移） | 用 `uint32_t` |
| `char c = 0x80; (uint32_t)c` | `char` 有沒有號是**實作定義**：x86 上是 signed，得到 `0xFFFFFF80`；ARM 與 RISC-V 上通常是 unsigned | 位元組一律用 `uint8_t` |

> 最後一條特別值得記：同一段讀 big-endian 的程式，在你的 x86 筆電上錯，在 RP2350（Cortex-M33 或 Hazard3）上卻可能「剛好對」。反過來也一樣。**不要依賴平台的巧合。**

### 1.3 整數提升（integer promotion）

比 `int` 窄的型別（`uint8_t`、`uint16_t`、`char`）參與運算前會先變成 `int`：

```c
uint8_t b = 0xA5;
~b            // 0xFFFFFF5A（int），不是 0x5A
(uint8_t)~b   // 0x5A
b << 24       // int；b >= 0x80 時這是 signed 溢位
(uint32_t)b << 24   // 安全
```

### 1.4 常用配方（背起來）

| 目的 | 寫法 |
|---|---|
| 第 n 位設 1 / 清 0 / 反轉 | `x \| (1u<<n)`、`x & ~(1u<<n)`、`x ^ (1u<<n)` |
| 取第 n 位 | `(x >> n) & 1u` |
| 取 hi..lo 欄位 | `(x >> lo) & mask(hi-lo+1)` |
| 換掉 hi..lo 欄位 | `m = mask(w) << lo; (x & ~m) \| ((v << lo) & m)` |
| 打包 | `(a << 24) \| (b << 16) \| (c << 8) \| d`（每個先轉 `uint32_t`、先 mask） |
| 是否 2 的冪次 | `x && !(x & (x - 1))` |
| 清掉最低位的 1 | `x & (x - 1)` |
| 只留最低位的 1 | `x & -x`（unsigned） |
| 循環左移 | `(x << (k & 31)) \| (x >> ((32 - k) & 31))` |
| 同位（parity） | 折疊：`x ^= x>>16; x ^= x>>8; x ^= x>>4; x &= 0xF; return (0x6996 >> x) & 1;` |

### 1.5 popcount 與位元反轉：同一件事的多種寫法

**popcount（數 1 的個數）**

```c
// 1) 逐位：固定 32 圈
for (c = 0; x; x >>= 1) c += x & 1;
// 2) Kernighan：圈數 = 1 的個數
for (c = 0; x; x &= x - 1) c++;
// 3) SWAR（一次處理所有位元，無分支）
x = x - ((x >> 1) & 0x55555555u);
x = (x & 0x33333333u) + ((x >> 2) & 0x33333333u);
x = (x + (x >> 4)) & 0x0F0F0F0Fu;
c = (x * 0x01010101u) >> 24;
// 4) 編譯器內建：__builtin_popcount(x)；RISC-V Zbb 有 cpop 指令
```

**位元反轉（32 bit）**

```c
x = ((x >> 1) & 0x55555555u) | ((x & 0x55555555u) << 1);   // 相鄰 1 位交換
x = ((x >> 2) & 0x33333333u) | ((x & 0x33333333u) << 2);   // 2 位一組交換
x = ((x >> 4) & 0x0F0F0F0Fu) | ((x & 0x0F0F0F0Fu) << 4);   // nibble 交換
x = ((x >> 8) & 0x00FF00FFu) | ((x & 0x00FF00FFu) << 8);   // byte 交換
x = (x >> 16) | (x << 16);                                 // 半字交換
```

這種「每層用 mask 把位元分組、一次搬一半」的思路叫做**分治 / SWAR**。CPU 上很好用，但 PIO 上沒有 AND，只能換別的方法（見第 3 節）。

---

## 2. RISC-V（RV32I）重點：參考資料「RISC-V Unprivileged ISA」

RP2350 有兩種核心可選：ARM Cortex-M33 與 RISC-V Hazard3。題目若涉及「特定指令集架構」，最可能是 RISC-V。

### 2.1 暫存器與基本指令

- 32 個 32-bit 暫存器 `x0..x31`；**`x0` 永遠讀到 0，寫入無效**。ABI 名稱：`zero ra sp gp tp t0-t6 s0-s11 a0-a7`（參數 / 回傳值用 `a0..a7`）。
- 指令固定 32 bit（加上 C 擴充後可以有 16 bit 的壓縮指令）。Load / store 架構：運算只在暫存器之間做。

| C | RV32I | 備註 |
|---|---|---|
| `a & b`、`a \| b`、`a ^ b` | `and` `or` `xor` | |
| `a & 0xFF` | `andi rd, rs, 0xFF` | 立即值是 **12 bit 有號**（-2048..2047），而且會**符號延伸** |
| `~a` | `xori rd, rs, -1` | 沒有 NOT 指令（`not` 是虛擬指令） |
| `a << 3`、`a >> 3`（unsigned） | `slli`、`srli` | 移位量只取低 5 位 |
| `(int32_t)a >> 3` | `srai` | 算術右移：補符號位 |
| `x = 0x12345678` | `lui` + `addi`（虛擬指令 `li`） | 見下方陷阱 |
| `if (a == b)` | `beq` / `bne` | 另有 `blt bge bltu bgeu`（有號 / 無號） |

**`li` 的陷阱：** `addi` 的 12 bit 立即值會符號延伸，所以載入 `0x12345FFF` 不能寫 `lui 0x12345` + `addi 0xFFF`（`0xFFF` 會被當成 -1），要寫成 `lui 0x12346` + `addi -1`。組譯器的 `li` 會自動幫你處理，但讀反組譯時要看得懂。

**`andi` 的陷阱：** `andi rd, rs, 0xFF00` 不合法（超出 12 bit）。要先 `li t0, 0xFF00`，再 `and`。

### 2.2 Bit-manipulation 擴充（Zb*）

RV32I 本身沒有 rotate、popcount。擴充 **Zbb** 提供 `rol/ror/rori`、`cpop`（popcount）、`clz/ctz`、`rev8`（byte 反轉）、`orc.b`、`andn/orn/xnor`、`min/max`、`sext.b/h`、`zext.h`。**Zbkb** 另有 `brev8`（每個 byte 內位元反轉）、`pack` 等。

> RP2350 的 Hazard3 核心實作了多個位元操作擴充；確切清單請查 datasheet [7] 的 Hazard3 章節。考場上若能用 `cpop`、`rev8`，就不用自己寫迴圈。

### 2.3 從 C 對照到指令（`demo_asm.c` 的延伸）

```text
C:      (x >> 4) & 0xF                      // 取 bits 7..4
RV32I:  srli a1, a0, 4
        andi a1, a1, 15

C:      x | (1u << n)                       // n 在暫存器 a1
RV32I:  li   t0, 1
        sll  t0, t0, a1
        or   a0, a0, t0
```

---

## 3. RP2350 PIO：參考資料「RP2350 datasheet, PIO chapter」

### 3.1 硬體長相

- RP2350 有 **3 個 PIO 區塊**，每個區塊有 **4 個 state machine (SM)**，四個 SM **共用**該區塊的 **32 條**指令記憶體。
- 每個 SM 只有：暫存器 **X、Y**（32 bit）、輸出移位暫存器 **OSR**、輸入移位暫存器 **ISR**、各自的移位計數器、**TX FIFO** 與 **RX FIFO**（各 4 個 word，可合併成單向 8 個）、時脈除頻器、腳位對應設定。
- **沒有 RAM、沒有加法器、沒有 AND/OR。** 能做的事全靠移位、搬移、反相 / 反轉、條件跳躍與遞減。
- 每條指令 1 個時脈週期（可加 delay），所以時序是可精確計算的。這正是 PIO 拿來做自訂通訊協定的原因。

```text
CPU ──put──> TX FIFO ──pull──> OSR ──out──> X / Y / pins / ISR ...
                                                │
CPU <──get── RX FIFO <──push── ISR <──in─── X / Y / pins / OSR / null
```

### 3.2 九條指令

| 指令 | 作用 | 重點 |
|---|---|---|
| `jmp [cond] label` | 跳躍 | cond：`!x`、`x--`、`!y`、`y--`、`x!=y`、`pin`、`!osre` |
| `wait pol src idx` | 等某個 GPIO / 腳位 / IRQ 變成 0 或 1 | 跟外部訊號同步 |
| `in src, n` | 從 src 移 n bit 進 ISR | src：`pins x y null isr osr` |
| `out dest, n` | 從 OSR 移 n bit 出去 | dest：`pins x y null pindirs pc isr exec` |
| `push [iffull] [block\|noblock]` | ISR → RX FIFO，ISR 清 0 | 預設 block：RX 滿就停住等 |
| `pull [ifempty] [block\|noblock]` | TX FIFO → OSR | 預設 block：TX 空就停住等；noblock 時 TX 空會把 X 複製進 OSR |
| `mov dest, [op]src` | 複製 | op：`!` 或 `~` 反相、`::` **位元反轉** |
| `irq` | 設定 / 清除 / 等待 IRQ 旗標 | SM 之間或對 CPU 發訊號 |
| `set dest, v` | 寫入 5 bit 立即值（0..31） | dest：`pins x y pindirs` |

另外每條指令都有一個 5 bit 欄位，**分給 delay `[n]` 與 side-set 共用**。

### 3.3 一定要懂的語意

1. **`jmp x-- label`：先看 X 是否非 0 決定跳不跳，然後無論如何 X 減 1。** 所以 `set x, 3` 配 `jmp x--` 的迴圈會跑 **4** 次（3、2、1、0 各進迴圈本體一次）。
2. **沒有加法，那怎麼「數數」？** 從 `0xFFFFFFFF`（`mov x, ~null`）開始，每遇到一次就 `jmp x--` 減 1，最後 `mov isr, ~x` 就是次數：`~(0xFFFFFFFF - k) = k`。這是 PIO 的經典技巧。
3. **大常數怎麼來？** `set` 只有 5 bit。方法：`mov x, ~null` 拿全 1；或初始化時讓 CPU 先送一個常數，`pull` + `mov x, osr`（或 `out x, 32`）存進 X / Y。
4. **移位方向是設定，不是指令。** `sm_config_set_out_shift(&c, shift_right, autopull, threshold)`：shift_right = true 時 `out` 從 OSR 的 LSB 開始取；false 時從 MSB 開始取。`in` 同理。
5. **autopull / autopush：** 開啟後，OSR 被取到 threshold 個 bit 時自動從 TX 補（不用寫 `pull`），ISR 累積到 threshold 時自動送到 RX（不用寫 `push`）。省指令、省週期，但**不要再手動 push / pull**（官方 homework 的 tutorial 也提醒過這會衝突）。
6. **`!osre`**：OSR 已取出的 bit 數小於 pull threshold 時為真。沒開 autopull 時，OSR 取完後再 `out` 會得到 0，不會卡住。
7. **`.wrap_target` / `.wrap`**：執行完 `.wrap` 那一條後，免費跳回 `.wrap_target`（0 週期、0 指令）。能省一條 `jmp`。
8. **`mov` 讀 OSR 不會消耗它；`out` 會。** `mov isr, ::osr` 拿到反轉後的整個 word，OSR 還在，之後照樣可以一個一個 `out`。
9. **stall 是正常的。** `pull` 遇到空 TX、`push` 遇到滿 RX 就停在原地，所有狀態不變，等 FIFO 有空間 / 有資料再繼續。正確的程式在任何 host 速度下輸出都一樣，只有時間不同。

### 3.4 C SDK 端怎麼把 PIO 程式跑起來（[4]）

```c
PIO pio = pio0;
uint offset = pio_add_program(pio, &popcount_program);       // 載入指令記憶體
uint sm = pio_claim_unused_sm(pio, true);                    // 拿一個 SM（也是有限資源！）
pio_sm_config c = popcount_program_get_default_config(offset);
sm_config_set_out_shift(&c, true,  false, 32);               // 右移、不 autopull、threshold 32
sm_config_set_in_shift (&c, false, false, 32);               // 左移、不 autopush
pio_sm_init(pio, sm, offset, &c);
pio_sm_set_enabled(pio, sm, true);

pio_sm_put_blocking(pio, sm, 0x12345678);                    // CPU → TX FIFO
uint32_t rev = pio_sm_get_blocking(pio, sm);                 // RX FIFO → CPU
uint32_t cnt = pio_sm_get_blocking(pio, sm);
```

`*_program_get_default_config()` 與 `*_program` 是 `pioasm` 從 `.pio` 檔產生的。本模擬器的 `.out_shift` / `.in_shift` directive 就是在代替上面兩行 `sm_config_set_*_shift`。

### 3.5 同一件事的三種層次

| 任務 | C（CPU） | RISC-V | PIO |
|---|---|---|---|
| 取 bits 15..8 | `(x >> 8) & 0xFF` | `srli` + `andi` | `out null, 8` 丟掉低 8 位，再 `out x, 8` |
| 位元反轉 | 分治 mask / 迴圈 | Zbkb `brev8` + `rev8` 組合 | **一條** `mov x, ::osr` |
| 數 1 的個數 | `__builtin_popcount` / SWAR | Zbb `cpop` | `out y, 1` + `jmp !y` + `jmp x--` 迴圈 |
| 每 word 送回 | `return` | `ret` | `in x, 32` + `push`，或開 autopush |

> 心得：PIO 在「搬位元、反轉、精準時序」上極強，在「算數」上極弱。寫 PIO 前先問：這件事能不能用**移位與計數**表達？

### 3.6 PIO 程式的效率怎麼想

- **週期數** = 每個輸入要執行幾條指令。迴圈裡每一條都乘以圈數，所以優化先看**迴圈本體**。
- 常見技巧：讓一個跳躍同時做兩件事（`jmp x-- loop` 既計數又回圈）、用 `.wrap` 省掉回圈的 `jmp`、把結束條件併到已經存在的分支裡。
- **展開（unroll）** 能減少每圈的檢查，但 32 條指令記憶體很快就用完，而且四個 SM 共用。官方 homework 與本模擬考都同時計週期與指令數，就是要你權衡這件事。

---

## 4. 自我檢查

<details><summary>1. <code>set x, 2</code> 之後 <code>loop: jmp x-- loop</code>，這條 jmp 共執行幾次？最後 X 是多少？</summary>
3 次（X=2 跳、X=1 跳、X=0 不跳），最後 X = 0xFFFFFFFF。
</details>

<details><summary>2. <code>out_shift</code> 設為向右，OSR = 0x12345678，<code>out x, 8</code> 之後 X 與 OSR 各是多少？</summary>
X = 0x78，OSR = 0x00123456（右移 8 位、補 0）。
</details>

<details><summary>3. 為什麼 <code>rotl32</code> 寫成 <code>(x &lt;&lt; k) | (x &gt;&gt; (32 - k))</code>，在 x86 上 k=0 也會「對」？為什麼還是錯？</summary>
x86 的移位指令只看移位量的低 5 位，<code>x &gt;&gt; 32</code> 實際上是 <code>x &gt;&gt; 0</code>，<code>x | x = x</code> 剛好正確。但 C 標準說移位量 >= 寬度是 UB，編譯器可以假設它不會發生並做出意料外的最佳化，換平台或換最佳化等級都可能出錯。
</details>

<details><summary>4. RISC-V 上要讓 <code>a0 = a0 &amp; 0xFFFF</code>，為什麼不能 <code>andi a0, a0, 0xFFFF</code>？有什麼替代？</summary>
<code>andi</code> 的立即值只有 12 bit 有號。替代：<code>slli a0, a0, 16</code> 再 <code>srli a0, a0, 16</code>；或 <code>li t0, 0xFFFF</code> + <code>and</code>；有 Zbb 時用 <code>zext.h</code>。
</details>

<details><summary>5. PIO 沒有 autopush，程式用了 <code>in x, 32</code> 卻忘了 <code>push</code>，會發生什麼？</summary>
資料停在 ISR，CPU 收不到；下一次 <code>in</code> 會把舊資料擠掉（或與新資料混在一起）。輸出筆數會少於預期，host 等不到資料。
</details>
