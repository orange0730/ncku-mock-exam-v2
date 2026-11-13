# 2-2 位元運算、RISC-V、RP2350 PIO（考場速查）

> 來源：`demo/section2-2/2-2.README.md`、`demo_asm.c`、`demo_pio.pio`（考前練習 2-2.pdf 內容相同）、演練試題 PDF 第二節；
> 外部連結 [1] cppreference *C Operator Precedence*、RISC-V 規格書（*The RISC-V Instruction Set Manual, Volume I: Unprivileged ISA*，取自 riscv-isa-manual 2026-11-12 版）、
> [7] *RP2350 Datasheet* 第 11 章 PIO（並引用 3.8 Hazard3）、[4] Pico SDK `hardware_pio` API（取自 SDK 原始碼 `hardware/pio.h`）。
> 本檔的完整範例程式（標有 `// file:`）都在樹莓派上用 `gcc -Wall -Wextra` 編譯並執行驗證過；PIO 範例用 `common/pio_sim.py` 驗證過。

## 目錄

- **A. C 位元運算**
  - [A1 demo_asm.c 全部輸出](#a1-demo_asmc-全部輸出)
  - [A2 運算子優先順序（完整表）](#a2-運算子優先順序完整表)
  - [A3 型別、整數提升、未定義行為](#a3-型別整數提升未定義行為)
  - [A4 位元配方大全](#a4-位元配方大全)
  - [A5 完整範例程式 bitlab.c](#a5-完整範例程式-bitlabc)
- **B. RISC-V（RV32I 與擴充）**
  - [B1 暫存器與 ABI](#b1-暫存器與-abi)
  - [B2 指令格式與立即值](#b2-指令格式與立即值)
  - [B3 RV32I 指令總表](#b3-rv32i-指令總表)
  - [B4 虛擬指令](#b4-虛擬指令)
  - [B5 M、A、Zbb、Zbs、Zba、Zbkb 擴充](#b5-mazbbzbszbazbkb-擴充)
  - [B6 組合語言範例](#b6-組合語言範例)
- **C. RP2350 PIO**
  - [C1 硬體概觀](#c1-硬體概觀)
  - [C2 程式設計模型：暫存器、計數器、FIFO、stall](#c2-程式設計模型暫存器計數器fifostall)
  - [C3 九條指令完整語意](#c3-九條指令完整語意)
  - [C4 pioasm 語法與 directive](#c4-pioasm-語法與-directive)
  - [C5 side-set、wrap、FIFO join、autopush/autopull、clock divider、腳位](#c5-side-setwrapfifo-joinautopushautopullclock-divider腳位)
  - [C6 Pico SDK PIO API](#c6-pico-sdk-pio-api)
  - [C7 PIO 範例程式](#c7-pio-範例程式)
  - [C8 PIO 技巧與陷阱](#c8-pio-技巧與陷阱)

---

# A. C 位元運算

## A1 demo_asm.c 全部輸出

```c
uint32_t x = 0xA5;   /* 1010 0101 */
```

| 運算式 | 結果 | 說明 |
|---|---|---|
| `x & 0x0F` | `0x05` | AND：只留低 4 位 |
| `x \| 0x0F` | `0xAF` | OR：低 4 位全設 1 |
| `x ^ 0xFF` | `0x5A` | XOR：每一位都反過來（低 8 位內） |
| `~x & 0xFF` | `0x5A` | NOT（`~x` 本身是 `0xFFFFFF5A`，所以要 `& 0xFF`） |
| `x << 4` | `0xA50` | 左移 4 位 |
| `x >> 4` | `0xA` | 右移 4 位 |
| `x \| (1u << 1)` | `0xA7` | 設定第 1 位 |
| `x & ~(1u << 0)` | `0xA4` | 清除第 0 位 |
| `(x >> 7) & 1` | `1` | 取出第 7 位 |
| `(x >> 4) & 0xF` | `0xA` | 取出 bits 7..4：先右移再 mask |
| `(0x12u << 8) \| 0x34` | `0x1234` | 把兩個較窄的值合併成較寬的值 |

編譯執行：`cc demo_asm.c -o demo_asm && ./demo_asm`。

二進位 / 十六進位對照：`0`=0000 `1`=0001 `2`=0010 `3`=0011 `4`=0100 `5`=0101 `6`=0110 `7`=0111 `8`=1000 `9`=1001 `A`=1010 `B`=1011 `C`=1100 `D`=1101 `E`=1110 `F`=1111。

## A2 運算子優先順序（完整表）

（cppreference，由高到低；同一列同優先順序）

| 級 | 運算子 | 說明 | 結合性 |
|---|---|---|---|
| 1 | `++` `--`（後置）`()` `[]` `.` `->` `(type){list}` | 後置遞增遞減、函式呼叫、陣列、成員、複合字面值 | 左→右 |
| 2 | `++` `--`（前置）`+` `-`（一元）`!` `~` `(type)` `*` `&` `sizeof` `_Alignof` | 一元運算 | **右→左** |
| 3 | `*` `/` `%` | 乘除餘 | 左→右 |
| 4 | `+` `-` | 加減 | 左→右 |
| 5 | `<<` `>>` | 移位 | 左→右 |
| 6 | `<` `<=` `>` `>=` | 關係 | 左→右 |
| 7 | `==` `!=` | 相等 | 左→右 |
| 8 | `&` | 位元 AND | 左→右 |
| 9 | `^` | 位元 XOR | 左→右 |
| 10 | `\|` | 位元 OR | 左→右 |
| 11 | `&&` | 邏輯 AND | 左→右 |
| 12 | `\|\|` | 邏輯 OR | 左→右 |
| 13 | `?:` | 條件 | **右→左** |
| 14 | `=` `+=` `-=` `*=` `/=` `%=` `<<=` `>>=` `&=` `^=` `\|=` | 指定 | **右→左** |
| 15 | `,` | 逗號 | 左→右 |

**一定要記的陷阱**

| 你寫的 | 實際意思 | 要寫成 |
|---|---|---|
| `x & mask == 0` | `x & (mask == 0)` | `(x & mask) == 0` |
| `x & (x - 1) == 0` | `x & ((x - 1) == 0)` | `(x & (x - 1)) == 0` |
| `1 << n + 1` | `1 << (n + 1)` | 加括號表達本意 |
| `a << 8 + b` | `a << (8 + b)` | `(a << 8) \| b` |
| `a < b < c` | `(a < b) < c` | `a < b && b < c` |
| `a < b == c` | `(a < b) == c` | — |
| `*p++` | `*(p++)` | 要 `(*p)++` 就加括號 |
| `sizeof (int) * p` | `(sizeof(int)) * p` | — |

其他：優先順序與「求值順序」無關；`?:` 中間那段當作有括號；`a = b = c` 是 `a = (b = c)`。`gcc -Wall` 的 `-Wparentheses` 會對前兩個陷阱發出警告。

## A3 型別、整數提升、未定義行為

| 項目 | 規則 / 陷阱 | 安全寫法 |
|---|---|---|
| 整數提升 | 比 `int` 窄的（`uint8_t`、`uint16_t`、`char`、`short`）運算前先變 `int` | 需要時先轉 `(uint32_t)` |
| `~` 寬度 | `uint8_t b = 0xA5; ~b` 是 `0xFFFFFF5A`（int） | `(uint8_t)~b` 或 `~b & 0xFF` |
| `char` 有沒有號 | 實作定義：x86 是 signed，ARM / RISC-V 通常 unsigned | 位元組一律 `uint8_t` |
| 符號延伸 | `(int8_t)0x80` 轉 32 位是 `0xFFFFFF80` | 先轉成無號 |
| `1 << 31` | `1` 是 signed int，移到符號位是 UB | `1u << 31` |
| 移位量 ≥ 寬度 | `x << 32`、`x >> 32` 是 UB（x86 / RISC-V 硬體只看低 5 位，常「剛好」得到 x） | 寬度 32 特判；`& 31` |
| 負數右移 | 實作定義（通常算術右移） | 用 `uint32_t` |
| 有號溢位 | UB | 用無號數運算 |
| `size_t` 減法 | `n - 1` 在 `n == 0` 時變極大值 | 先判 `n == 0` |
| 固定寬度型別 | `#include <stdint.h>`：`uint8_t`、`uint16_t`、`uint32_t`、`uint64_t`、`int32_t`…；印出用 `<inttypes.h>` 的 `PRIu32`、`PRIx32` | — |

## A4 位元配方大全

| 目的 | 寫法 |
|---|---|
| 設定第 n 位 | `x \| (1u << n)` |
| 清除第 n 位 | `x & ~(1u << n)` |
| 反轉第 n 位 | `x ^ (1u << n)` |
| 測試第 n 位 | `(x >> n) & 1u`、`(x & (1u << n)) != 0` |
| 低 w 位的 mask | `w >= 32 ? 0xFFFFFFFFu : (1u << w) - 1u` |
| 取 hi..lo 欄位 | `(x >> lo) & mask(hi - lo + 1)` |
| 換掉 hi..lo 欄位為 v | `m = mask(w) << lo; x = (x & ~m) \| ((v << lo) & m);` |
| 打包 4 個 byte | `((uint32_t)a << 24) \| ((uint32_t)b << 16) \| ((uint32_t)c << 8) \| d` |
| 讀 big-endian | `(p[0] << 24) \| (p[1] << 16) \| (p[2] << 8) \| p[3]`（p 為 `uint8_t*`，先轉 `uint32_t`） |
| 讀 little-endian | `p[0] \| (p[1] << 8) \| (p[2] << 16) \| (p[3] << 24)` |
| 2 的冪次 | `x && !(x & (x - 1))` |
| 清掉最低的 1 | `x & (x - 1)` |
| 只留最低的 1 | `x & (~x + 1)`（= `x & -x`，無號） |
| 循環左移 | `(x << (k & 31)) \| (x >> ((32 - k) & 31))` |
| 循環右移 | `(x >> (k & 31)) \| (x << ((32 - k) & 31))` |
| byte 反轉 | `__builtin_bswap32(x)`，或 `(x>>24) \| ((x>>8)&0xFF00) \| ((x<<8)&0xFF0000) \| (x<<24)` |
| popcount | Kernighan：`for (c = 0; x; x &= x - 1) c++;`；SWAR 見 A5；`__builtin_popcount(x)` |
| 同位 | `x ^= x>>16; x ^= x>>8; x ^= x>>4; x &= 0xF; (0x6996 >> x) & 1` |
| 位元反轉（32） | 分治：交換相鄰 1 位、2 位一組、4 位、8 位、16 位（見 A5） |
| 相同位數（XNOR） | `popcount(~(a ^ b))` |
| 二值內積（±1） | `2 * popcount(~(a ^ b)) - n` |
| 符號延伸 n 位欄位 | `(int32_t)(v << (32 - n)) >> (32 - n)`（算術右移，實作定義但普遍） |
| 前導零 / 尾端零 | `__builtin_clz(x)`、`__builtin_ctz(x)`（`x == 0` 時未定義） |

## A5 完整範例程式 bitlab.c

```c
// file: bitlab.c
// 編譯：gcc -std=c11 -O2 -Wall -Wextra bitlab.c -o bitlab && ./bitlab
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

static uint32_t low_mask(unsigned w) { return w >= 32 ? 0xFFFFFFFFu : ((1u << w) - 1u); }

static uint32_t get_field(uint32_t x, unsigned hi, unsigned lo) { return (x >> lo) & low_mask(hi - lo + 1); }

static uint32_t set_field(uint32_t x, unsigned hi, unsigned lo, uint32_t v) {
    uint32_t m = low_mask(hi - lo + 1) << lo;
    return (x & ~m) | ((v << lo) & m);
}

static uint32_t rotl32(uint32_t x, unsigned k) { k &= 31; return (x << k) | (x >> ((32 - k) & 31)); }

static int popcount_loop(uint32_t x) { int c = 0; for (int i = 0; i < 32; i++) c += (x >> i) & 1u; return c; }
static int popcount_kern(uint32_t x) { int c = 0; for (; x; x &= x - 1) c++; return c; }
static int popcount_swar(uint32_t x) {
    x = x - ((x >> 1) & 0x55555555u);
    x = (x & 0x33333333u) + ((x >> 2) & 0x33333333u);
    x = (x + (x >> 4)) & 0x0F0F0F0Fu;
    return (int)((x * 0x01010101u) >> 24);
}

static uint32_t bitrev32(uint32_t x) {
    x = ((x >> 1) & 0x55555555u) | ((x & 0x55555555u) << 1);
    x = ((x >> 2) & 0x33333333u) | ((x & 0x33333333u) << 2);
    x = ((x >> 4) & 0x0F0F0F0Fu) | ((x & 0x0F0F0F0Fu) << 4);
    x = ((x >> 8) & 0x00FF00FFu) | ((x & 0x00FF00FFu) << 8);
    return (x >> 16) | (x << 16);
}

static uint8_t reverse8(uint8_t b) {
    uint8_t r = 0;
    for (int i = 0; i < 8; i++) r = (uint8_t)((r << 1) | ((b >> i) & 1u));
    return r;
}

static int parity32(uint32_t x) { x ^= x >> 16; x ^= x >> 8; x ^= x >> 4; x &= 0xFu; return (0x6996u >> x) & 1u; }
static int is_pow2(uint32_t x) { return x != 0 && (x & (x - 1)) == 0; }

static uint32_t load_be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}
static uint32_t load_le32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static void store_be32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16); p[2] = (uint8_t)(v >> 8); p[3] = (uint8_t)v;
}

/* 二值神經元：相同位數 = popcount(XNOR)；二值內積 = 2 * 相同 - 位數 */
static int xnor_matches(uint32_t a, uint32_t w) { return popcount_swar(~(a ^ w)); }

int main(void) {
    uint32_t x = 0xA5;
    printf("demo: %02" PRIX32 " %02" PRIX32 " %02" PRIX32 " %02" PRIX32 " %" PRIX32 " %" PRIX32 "\n",
           x & 0x0F, x | 0x0F, x ^ 0xFF, ~x & 0xFF, x << 4, x >> 4);
    printf("get_field(0xABCD1234, 15, 8) = 0x%02" PRIX32 "\n", get_field(0xABCD1234u, 15, 8));       /* 12 */
    printf("get_field(x, 31, 0)          = 0x%08" PRIX32 "\n", get_field(0xDEADBEEFu, 31, 0));      /* DEADBEEF */
    printf("set_field(0xFFFFFFFF, 7, 4, 0x12) = 0x%08" PRIX32 "\n", set_field(0xFFFFFFFFu, 7, 4, 0x12)); /* FFFFFF2F */
    printf("rotl32(0x80000001, 1) = 0x%08" PRIX32 "  rotl32(x, 0) = 0x%08" PRIX32 "\n",
           rotl32(0x80000001u, 1), rotl32(0x12345678u, 0));                                     /* 00000003 12345678 */
    printf("popcount(0xF0F0F0F0) = %d %d %d\n", popcount_loop(0xF0F0F0F0u), popcount_kern(0xF0F0F0F0u),
           popcount_swar(0xF0F0F0F0u));                                                         /* 16 16 16 */
    printf("bitrev32(1) = 0x%08" PRIX32 "  reverse8(0x78) = 0x%02X\n", bitrev32(1u), reverse8(0x78)); /* 80000000 1E */
    printf("parity32(7) = %d  is_pow2(64) = %d  is_pow2(0) = %d\n", parity32(7u), is_pow2(64u), is_pow2(0u));
    uint8_t buf[4] = {0x12, 0x34, 0x56, 0x80};
    printf("load_be32 = 0x%08" PRIX32 "  load_le32 = 0x%08" PRIX32 "\n", load_be32(buf), load_le32(buf)); /* 12345680 80563412 */
    store_be32(buf, 0xCAFEBABEu);
    printf("store_be32 -> %02X %02X %02X %02X\n", buf[0], buf[1], buf[2], buf[3]);              /* CA FE BA BE */
    printf("xnor_matches(0xFFFF0000, 0xFF00FF00) = %d\n", xnor_matches(0xFFFF0000u, 0xFF00FF00u)); /* 16 */
    printf("signed char trap: (int8_t)0x80 -> 0x%08" PRIX32 "\n", (uint32_t)(int32_t)(int8_t)0x80); /* FFFFFF80 */
    return 0;
}
```

去年考題會用到的較大範例（CRC-32、SHA-0、radix sort、二值神經網路層）在 [A_演算法範例.md](A_演算法範例.md)。

---

# B. RISC-V（RV32I 與擴充）

> 2-2 README 給的連結 `riscv.org/specifications/ratified/` 是索引頁：列出歷史版的 UCB 技術報告（Volume I User-Level ISA 2011 / v2.0 2014 / v2.1 2016、Volume II Privileged v1.7 / v1.9、Compressed v1.7），並連到 **docs.riscv.org**（Ratified ISA Specifications、Ratified Specifications Library）與 Ratified Extensions 清單。目前的完整規格在 docs.riscv.org 或 GitHub `riscv/riscv-isa-manual` 的 release（本節即取自其 2026-11-12 版）。Hazard3 依據的版本：RV32I v2.1、M v2.0、A v2.1、C v2.0（Unprivileged ISA 20191213），Zba / Zbb / Zbs v1.0.0（20210628），Zbkb v1.0.1。
>
> RP2350 有兩種核心可選：Arm Cortex-M33 ×2 或 **Hazard3 RISC-V ×2**（150 MHz，520 kB SRAM）。
> Hazard3 在 RP2350 上實作：**RV32I、M、A、C（Zca）、Zba、Zbb、Zbs、Zbkb、Zcb、Zcmp、Zicsr**，以及 Machine / User 模式、Debug、PMP（8 區）；另有自訂擴充 Xh3power、Xh3bextm、Xh3irq、Xh3pmpm。

## B1 暫存器與 ABI

- 32 個暫存器 `x0`–`x31`，RV32 每個 32 位（XLEN = 32）；**`x0` 永遠是 0**，寫入無效。另有 `pc`。
- 基本 ISA 沒有專用的 stack pointer / link register，是呼叫慣例規定的：`x1` = 返回位址、`x2` = stack pointer、`x5` = 備用 link register。

| 暫存器 | ABI 名稱 | 用途 | 誰保存 |
|---|---|---|---|
| x0 | `zero` | 常數 0 | — |
| x1 | `ra` | 返回位址 | caller |
| x2 | `sp` | stack pointer | callee |
| x3 | `gp` | global pointer | — |
| x4 | `tp` | thread pointer | — |
| x5–x7 | `t0`–`t2` | 暫存 | caller |
| x8 | `s0` / `fp` | 保存 / frame pointer | callee |
| x9 | `s1` | 保存 | callee |
| x10–x11 | `a0`–`a1` | 參數 / **回傳值** | caller |
| x12–x17 | `a2`–`a7` | 參數 | caller |
| x18–x27 | `s2`–`s11` | 保存 | callee |
| x28–x31 | `t3`–`t6` | 暫存 | caller |

## B2 指令格式與立即值

- 基本指令固定 32 位（C 擴充有 16 位壓縮指令）。load-store 架構：只有 load / store 存取記憶體。
- 格式：**R**（rd, rs1, rs2）、**I**（12 位立即值：ALU 立即值、load、JALR）、**S**（store）、**B**（分支）、**U**（20 位高位立即值：LUI、AUIPC）、**J**（JAL）。
- **I 型立即值是 12 位有號，會符號延伸**：範圍 −2048 … 2047。`andi a0, a0, 0xFF` 可以；`andi a0, a0, 0xFFFF` 不行。
- `LUI rd, imm20`：把 imm20 放到 rd 的 bits 31..12，低 12 位補 0。
- 32 位常數 = `lui` + `addi`；但 `addi` 的立即值會符號延伸，所以 `0x12345FFF` 要寫成 `lui 0x12346` + `addi -1`。組譯器的 `li` 會自動處理。
- 分支 / JAL 的位移以 2 bytes 為單位：分支 ±4 KiB，JAL ±1 MiB。
- 記憶體是 byte 定址；RP2350 是 little-endian（最低位址放最低位元組）。

## B3 RV32I 指令總表

| 類別 | 指令 | 語意 |
|---|---|---|
| 立即值運算 | `addi rd, rs1, imm` | rd = rs1 + sext(imm)，溢位忽略 |
| | `slti` / `sltiu` | rd = (rs1 < sext(imm)) ? 1 : 0（有號 / 無號比較）；`sltiu rd, rs, 1` = `seqz` |
| | `andi` / `ori` / `xori` | 與符號延伸的立即值做 AND / OR / XOR；`xori rd, rs, -1` = `not` |
| | `slli` / `srli` / `srai` | 立即值移位，移位量 0..31；srli 補 0、srai 補符號位 |
| 高位立即值 | `lui rd, imm20` | rd = imm20 << 12 |
| | `auipc rd, imm20` | rd = pc + (imm20 << 12) |
| 暫存器運算 | `add` / `sub` | rd = rs1 ± rs2（溢位忽略） |
| | `slt` / `sltu` | 有號 / 無號小於；`sltu rd, x0, rs` = `snez` |
| | `and` / `or` / `xor` | 位元運算 |
| | `sll` / `srl` / `sra` | 移位，**移位量只取 rs2 的低 5 位** |
| 跳躍 | `jal rd, offset` | rd = pc + 4；pc += offset（±1 MiB）；`j` = `jal x0` |
| | `jalr rd, offset(rs1)` | rd = pc + 4；pc = (rs1 + sext(offset)) & ~1；`ret` = `jalr x0, 0(ra)` |
| 分支 | `beq` `bne` `blt` `bge` `bltu` `bgeu` | 比較 rs1、rs2，成立就 pc += offset（±4 KiB） |
| Load | `lb` `lh` `lw` `lbu` `lhu` | rd = mem[rs1 + sext(off)]；`lb`/`lh` 符號延伸，`lbu`/`lhu` 補 0 |
| Store | `sb` `sh` `sw` | mem[rs1 + sext(off)] = rs2 的低 8 / 16 / 32 位 |
| 記憶體順序 | `fence`、`fence.i` | 記憶體 / 指令存取的順序屏障 |
| 系統 | `ecall`、`ebreak` | 系統呼叫、除錯中斷點 |
| NOP | `nop` | 編碼為 `addi x0, x0, 0` |

- 沒有任何整數運算會產生例外（溢位不會 trap）。無號加法溢位檢查：`add t0, t1, t2; bltu t0, t1, overflow`。

## B4 虛擬指令

| 虛擬指令 | 實際 | | 虛擬指令 | 實際 |
|---|---|---|---|---|
| `li rd, imm` | `lui` + `addi`（或只用其一） | | `mv rd, rs` | `addi rd, rs, 0` |
| `la rd, sym` | `auipc` + `addi` | | `not rd, rs` | `xori rd, rs, -1` |
| `neg rd, rs` | `sub rd, x0, rs` | | `seqz rd, rs` | `sltiu rd, rs, 1` |
| `snez rd, rs` | `sltu rd, x0, rs` | | `sltz` / `sgtz` | `slt rd, rs, x0` / `slt rd, x0, rs` |
| `beqz rs, L` | `beq rs, x0, L` | | `bnez rs, L` | `bne rs, x0, L` |
| `bgt a, b, L` | `blt b, a, L` | | `ble a, b, L` | `bge b, a, L` |
| `bgtu` / `bleu` | 同上、無號 | | `j L` | `jal x0, L` |
| `jr rs` | `jalr x0, 0(rs)` | | `ret` | `jalr x0, 0(ra)` |
| `call f` | `auipc ra` + `jalr ra` | | `tail f` | `auipc t1` + `jalr x0` |

## B5 M、A、Zbb、Zbs、Zba、Zbkb 擴充

**M（乘除）**

| 指令 | 語意 |
|---|---|
| `mul` | 乘積的低 32 位 |
| `mulh` / `mulhu` / `mulhsu` | 乘積的高 32 位（有號×有號 / 無號×無號 / 有號×無號） |
| `div` / `divu` | 有號 / 無號除法（向 0 取整） |
| `rem` / `remu` | 有號 / 無號餘數 |

除以 0 不會 trap：商 = 全 1（`divu` 為 2³²−1、`div` 為 −1），餘數 = 被除數。有號溢位（−2³¹ ÷ −1）：商 = −2³¹，餘數 = 0。

**A（原子操作）** 位址必須自然對齊（word 要 4 的倍數），否則例外。

| 指令 | 語意 |
|---|---|
| `lr.w rd, (rs1)` | load-reserved：讀 word，並在該位址登記「保留」 |
| `sc.w rd, rs2, (rs1)` | store-conditional：保留仍有效才寫入；**成功 rd = 0，失敗 rd ≠ 0**；無論成敗都會清掉保留 |
| `amoswap.w rd, rs2, (rs1)` | 原子地：rd = mem；mem = rs2（= test-and-set / atomic exchange） |
| `amoadd.w` / `amoand.w` / `amoor.w` / `amoxor.w` | 原子地：rd = mem；mem = mem op rs2（`amoadd` = fetch-and-add） |
| `amomax[u].w` / `amomin[u].w` | 原子最大 / 最小 |
| `.aq` / `.rl` 後綴 | acquire / release 記憶體順序（上鎖用 `.aq`，解鎖用 `.rl`） |

LR/SC 比 CAS 好的原因（規格書說明）：避免 ABA 問題、不需要三個來源運算元。缺點是可能 livelock（規格對特定條件有前進保證）。

**Zbb（基本位元操作）**

| 指令 | 語意 |
|---|---|
| `andn` / `orn` / `xnor` | rs1 & ~rs2、rs1 \| ~rs2、~(rs1 ^ rs2) |
| `clz` / `ctz` | 前導零 / 尾端零個數 |
| `cpop` | **popcount** |
| `max` / `maxu` / `min` / `minu` | 有號 / 無號最大最小 |
| `sext.b` / `sext.h` / `zext.h` | 8 / 16 位符號延伸、16 位零延伸 |
| `rol` / `ror` / `rori` | 循環左移 / 右移 |
| `orc.b` | 每個 byte：非 0 就變 0xFF，0 維持 0 |
| `rev8` | 位元組順序反轉（大小端轉換） |

**Zbs（單一位元）**：`bset`、`bclr`、`binv`、`bext`（設定 / 清除 / 反轉 / 取出第 rs2 位），各有立即值版 `bseti`、`bclri`、`binvi`、`bexti`。
**Zba（位址計算）**：`sh1add`、`sh2add`、`sh3add`：rd = (rs1 << 1/2/3) + rs2（陣列索引）。
**Zbkb**：`pack`（兩個 16 位拼成 32 位）、`packh`（兩個 8 位拼成 16 位）、`brev8`（每個 byte 內位元反轉）、`zip` / `unzip`（RV32 位元交錯）。

## B6 組合語言範例

```asm
# a0 = popcount(a0)，只用 RV32I（迴圈）
popcount:
    li   t0, 0              # 計數
1:  beqz a0, 2f
    addi t1, a0, -1
    and  a0, a0, t1         # 清掉最低的 1（Kernighan）
    addi t0, t0, 1
    j    1b
2:  mv   a0, t0
    ret

# 有 Zbb：一條
    cpop a0, a0

# XNOR-popcount（二值神經元的相同位數）：a0 = popcount(~(a0 ^ a1))
    xnor a0, a0, a1         # Zbb
    cpop a0, a0

# 取出 bits 15..8：a0 = (a0 >> 8) & 0xFF
    srli a0, a0, 8
    andi a0, a0, 0xFF

# 取出 bits 23..8（16 位寬，超過 andi 範圍）
    slli a0, a0, 8          # 先把 bit 23 推到 bit 31
    srli a0, a0, 16         # 再右移，保留 16 位

# 設定第 a1 位：a0 |= 1 << a1
    li   t0, 1
    sll  t0, t0, a1
    or   a0, a0, t0         # Zbs：bset a0, a0, a1

# 循環左移 a1 位（RV32I 沒有 rotate）
    sll  t0, a0, a1
    neg  t1, a1
    srl  t1, a0, t1         # 移位量只取低 5 位，所以 -a1 等於 32 - a1
    or   a0, t0, t1         # Zbb：rol a0, a0, a1

# 自旋鎖：amoswap（test-and-set）
lock:                       # a0 = &lock
    li   t0, 1
1:  amoswap.w.aq t1, t0, (a0)
    bnez t1, 1b             # 舊值是 1 = 別人拿著，繼續等
    ret
unlock:
    amoswap.w.rl x0, x0, (a0)   # 或：fence；sw zero, 0(a0)
    ret

# 原子加一：用 LR/SC
inc:                        # a0 = &counter
1:  lr.w  t0, (a0)
    addi  t0, t0, 1
    sc.w  t1, t0, (a0)
    bnez  t1, 1b            # 失敗（非 0）就重試
    ret
```

---

# C. RP2350 PIO

## C1 硬體概觀

- RP2350 有 **3 個 PIO 區塊**，每個 **4 個 state machine（SM）**，共 12 個 SM（RP2040 是 2 個區塊、8 個 SM）。
- 每個區塊有 **32 條指令**的共用指令記憶體（1 寫 4 讀：4 個 SM 每個週期都能同時取指令，不會互卡）。系統只能寫入（載入程式）。
- 每個 SM 配備：
  - 兩個 32 位移位暫存器 **OSR**、**ISR**（任意方向、任意位數）
  - 兩個 32 位暫存器 **X**、**Y**
  - **TX、RX FIFO 各 4 個 word**，可合併成單向 8 個
  - 分數時脈除頻器（16 位整數 + 8 位小數）
  - 彈性的 GPIO 對應
  - DMA 介面（系統 DMA 可持續每個時脈 1 word）
  - IRQ 旗標的設定、清除、狀態
- 用途：8080 / 6800 並列匯流排、I2C、I2S、SDIO、SPI / DSPI / QSPI、UART、DPI / VGA 等。
- 每個 SM 最多看得到 32 個 GPIO（RP2350A 為 30 個）；所有 SM 都能同時存取任何 GPIO。
- RP2350 相對 RP2040 新增：`GPIOBASE`（選擇哪 32 個 GPIO）、跨 PIO 區塊同時啟停與 IRQ（`prev` / `next`）、`SHIFTCTRL.IN_COUNT`、RX FIFO 隨機存取（`FJOIN_RX_PUT` / `FJOIN_RX_GET`，`mov rxfifo[]`）、`WAIT JMPPIN`、`MOV PINDIRS`、`MOV x, STATUS` 可讀 SM IRQ、DREQ 延遲少 1 週期。PIO 版本：RP2040 = 0，RP2350 = 1。

## C2 程式設計模型：暫存器、計數器、FIFO、stall

```text
CPU / DMA ──寫入──> TX FIFO ──PULL──> OSR ──OUT──> PINS / X / Y / NULL / PINDIRS / PC / ISR / EXEC
CPU / DMA <──讀取── RX FIFO <──PUSH── ISR <──IN─── PINS / X / Y / NULL / ISR / OSR
```

**控制流程**

- 每個系統時脈，每個 SM 取指、解碼、執行一條指令。**每條指令剛好 1 週期**，除非它 stall。
- 每條指令可加最多 31 個延遲週期 `[n]`（與 side-set 共用 5 位元）。
- PC 執行完一條指令後的更新規則：
  1. 若是 JMP 且條件成立 → 跳到目標；
  2. 否則若 PC == `WRAP_TOP` → PC = `WRAP_BOTTOM`（`.wrap` / `.wrap_target`，**0 週期**）；
  3. 否則 PC + 1（到 31 後回到 0）。
- 指令也可來自：寫入 `SMx_INSTR` 暫存器（立即執行）、`MOV EXEC`、`OUT EXEC`（執行資料流裡的指令；MOV / OUT 本身 1 週期，被執行的指令在下一週期）。

**OSR**

- `PULL`：從 TX FIFO 取一個 word 放進 OSR。
- `OUT`：從 OSR 移出 1–32 位到目的地；**OSR 移出後補 0**。
- 開啟 autopull 時，達到門檻後 OUT 會自動補充 OSR。
- 移位方向（左 / 右）由處理器設定（`SHIFTCTRL`），程式裡改不了。

**ISR**

- `IN`：移入 1–32 位；`PUSH`：把 ISR 寫到 RX FIFO，**ISR 清為 0**。
- 開啟 autopush 時，達到門檻後 IN 會自動 push。
- 想讓「LSB 先收到」的資料靠右對齊：右移收資料，最後用 `IN NULL, n` 補 0（例如 UART 收 8 位後 `in null, 24`）。

**移位計數器（0..32，飽和）**

| 事件 | 輸入計數（ISR） | 輸出計數（OSR） |
|---|---|---|
| 重置 / `CTRL_SM_RESTART` | 0（空） | **32**（已用完，沒東西可移出） |
| `IN n` / `OUT n` | + n | + n |
| 成功的 `PUSH` / autopush | 0 | — |
| 成功的 `PULL` / autopull | — | 0 |
| `MOV ISR, …` | 0 | — |
| `MOV OSR, …` | — | 0 |
| `OUT ISR, n` | 設為 n | + n |

**X、Y**：IN / OUT / SET / MOV 的來源或目的地，以及 JMP 條件的來源。可用 MOV 備份 / 還原移位暫存器。

**FIFO**：每個 SM 一組 4-word 的 TX（系統 → SM）與 RX（SM → 系統）FIFO。FIFO 會產生 DREQ，讓 DMA 依「RX 有資料」或「TX 有空位」調整節奏。單向傳輸可用 `FJOIN` 合併成 8 個。

**stall（原地等待；PC 不前進，delay 等 stall 結束才開始）**

- `WAIT` 條件未成立
- 阻塞的 `PULL` 遇到 TX 空、阻塞的 `PUSH` 遇到 RX 滿
- `IRQ WAIT` 設了旗標、等它被清除
- 開了 autopull，`OUT` 時 OSR 已達門檻（而 TX 空）
- 開了 autopush，`IN` 達門檻而 RX 滿

side-set 不受 stall 影響：一定在該指令的第一個週期就生效。

**腳位對應**：每個 SM 有 OUT、SET、IN、side-set 四組連續腳位範圍（base + count，設定在 `PINCTRL`），可重疊。同一個 GPIO 在同一週期被多個 SM 寫入時，**編號最大的 SM 勝**；同一 SM 的 SET/OUT 與 side-set 同時寫同一腳，**side-set 勝**。沒人寫的 GPIO 維持原值。

**IRQ 旗標**：每個 PIO 區塊 8 個，所有 SM 都看得到，可經 `IRQ0_INTE` / `IRQ1_INTE` 送到系統中斷。用途：通知 CPU、同步 SM。SM 之間**不能直接傳資料**，只能用 IRQ 同步；同一週期同時設定與清除時，設定優先。

## C3 九條指令完整語意

指令 16 位：bits 15..13 = 種類，bits 12..8 = **Delay/side-set**（5 位：低位是 delay、高 `SIDESET_COUNT` 位是 side-set），其餘是參數。**所有指令 1 週期**。

| 指令 | 編碼 bits 15..13 | 參數 |
|---|---|---|
| JMP | 000 | Condition(3) Address(5) |
| WAIT | 001 | Pol Source(2) Index(5) |
| IN | 010 | Source(3) Bit count(5) |
| OUT | 011 | Destination(3) Bit count(5) |
| PUSH / PULL / MOV(RX) | 100 | 見下 |
| MOV | 101 | Destination(3) Op(2) Source(3) |
| IRQ | 110 | Clr Wait IdxMode(2) Index(3) |
| SET | 111 | Destination(3) Data(5) |

### JMP

`jmp (<cond>) <target>`：條件成立就把 PC 設為 Address（指令記憶體的**絕對位址**；SDK 載入時會自動加上載入偏移）。不論跳不跳，delay 都會發生（在評估條件、更新 PC 之後）。

| cond | 意思 |
|---|---|
| （無） | 一定跳 |
| `!x` | X 為 0 |
| `x--` | **X 非 0（遞減前）**；之後 X 一律減 1 |
| `!y` | Y 為 0 |
| `y--` | Y 非 0（遞減前）；之後 Y 一律減 1 |
| `x!=y` | X ≠ Y |
| `pin` | `EXECCTRL_JMP_PIN` 選的 GPIO 為高 |
| `!osre` | OSR 未空：自上次 PULL 移出的位數 < `PULL_THRESH`（與 autopull 同一門檻） |

> `x--` 的遞減**不是條件式的**；分支依據的是遞減**前**的值。`set x, 3` 配上迴圈尾的 `jmp x-- loop`，迴圈本體跑 4 次。

### WAIT

`wait <pol> gpio <n>` | `wait <pol> pin <n>` | `wait <pol> irq (prev|next) <n> (rel)` | `wait <pol> jmppin (+ <off>)`

- 等到條件成立（stall）；delay 在條件成立後才開始。
- pol：1 = 等 1、0 = 等 0。
- `gpio`：絕對 GPIO 編號，不受 IN 對應影響。`pin`：IN_BASE + index（mod 32）。`irq`：PIO IRQ 旗標。`jmppin`：JMP_PIN + 0..3。
- `wait 1 irq x`：條件成立時**會清除**該旗標。
- `rel`：IRQ 編號的低 2 位加上 SM 編號（mod 4），讓跑同一程式的多個 SM 各用各的旗標。`prev` / `next`：相鄰 PIO 區塊的旗標。
- 注意：不要對送往系統中斷的 IRQ 旗標用 `wait 1 irq`，會與中斷處理程式 race。

### IN

`in <source>, <bit_count>`（1–32，32 編碼為 0）

- 來源：`pins`、`x`、`y`、`null`（全 0）、`isr`、`osr`。
- 依 `IN_SHIFTDIR` 移動 ISR 騰出空間，再把來源的**最低** bit_count 位放進空位（來源位元的順序不受移位方向影響）。輸入計數 + bit_count（飽和 32）。
- autopush：達到 `PUSH_THRESH` 就自動 push、清 ISR 與計數；RX 滿則 stall。IN 本身仍是 1 週期。

### OUT

`out <destination>, <bit_count>`（1–32）

- 目的地：`pins`、`x`、`y`、`null`（丟棄）、`pindirs`、`pc`（無條件跳到移出的位址）、`isr`（並把 ISR 計數設為 bit_count）、`exec`（把移出的資料當指令執行）。
- 寫到目的地的是 32 位值：低 bit_count 位來自 OSR，其餘補 0。**右移時取 OSR 的最低位，左移時取最高位**。輸出計數 + bit_count。
- autopull：達到 `PULL_THRESH` 時自動從 TX 補 OSR、計數歸 0；TX 空則 stall。

### PUSH

`push`、`push iffull`、`push block`、`push noblock`、`push iffull noblock`…

- 把 ISR 整個（32 位）推進 RX FIFO，ISR 清 0。
- `iffull`：輸入計數未達 `PUSH_THRESH` 就什麼都不做。
- `block`（預設）：RX 滿就 stall。`noblock`：RX 滿也繼續；FIFO 不變、**ISR 照樣清 0**、設 `FDEBUG_RXSTALL`（資料遺失）。

### PULL

`pull`、`pull ifempty`、`pull block`、`pull noblock`…

- 從 TX FIFO 取一個 word 進 OSR，輸出計數歸 0。
- `ifempty`：輸出計數未達 `PULL_THRESH` 就什麼都不做。
- `block`（預設）：TX 空就 stall。`noblock`：TX 空時**把 X 複製到 OSR**（= `mov osr, x`）。可先在 X 放預設值，或每次 `pull noblock` 後 `mov x, osr`，讓最後的有效值一直重複。
- **開 autopull 時，OSR 滿的話 `PULL` 是 no-op**（當作屏障）。要丟掉 OSR 內容用 `out null, 32`。

### MOV

`mov <destination>, (op) <source>`

- 目的地：`pins`、`x`、`y`、`pindirs`（PIO v1）、`exec`、`pc`、`isr`（**輸入計數歸 0**）、`osr`（**輸出計數歸 0，即「滿」**）。
- op：`!` 或 `~` = 位元反相；`::` = **位元反轉**（bit n ← bit 31−n）。
- 來源：`pins`、`x`、`y`、`null`、`status`、`isr`、`osr`。
- `status`：全 1 或全 0，依 `EXECCTRL_STATUS_SEL`（例如 TX 少於 N 個、RX 少於 N 個，或某 IRQ 旗標）。
- `mov dst, pins`：依 IN 對應讀腳，超過 `IN_COUNT` 的位元為 0。
- `nop` = `mov y, y`。

**MOV 到 / 從 RX FIFO（PIO v1）**：`mov rxfifo[y], isr`、`mov rxfifo[<0-3>], isr`（需 `FJOIN_RX_PUT`）、`mov osr, rxfifo[y]`、`mov osr, rxfifo[<0-3>]`（需 `FJOIN_RX_GET`）。只開 PUT 時，系統可透過 `RXFx_PUTGETn` 隨機讀（當狀態暫存器）；只開 GET 時，系統可隨機寫（當設定暫存器）；兩者都開時系統不能存取，SM 拿來當額外暫存空間。此時 PUSH 未定義，也不能開 autopush。

### IRQ

`irq (prev|next) <n> (rel)`、`irq set`、`irq nowait`、`irq wait`、`irq clear`

- 設定或清除 IRQ 旗標 0–7。`wait`：設定後等它被清除才繼續（delay 等清除後才開始）。`clear` 時 wait 無效。
- 同時 set 與 clear 同一旗標 → set 勝。
- `rel`、`prev`、`next` 同 WAIT。跨 PIO 用時，兩邊的除頻器要相同並同步重啟。

### SET

`set <destination>, <value>`（0–31）

- 目的地：`pins`、`x`、`y`、`pindirs`。對 X、Y：**低 5 位設為 Data，其餘清 0**。
- SET 與 OUT 的腳位對應各自獨立，可重疊（例如 UART TX 用 SET 打起始 / 停止位、用 OUT 送資料到同一腳）。

## C4 pioasm 語法與 directive

```text
<instruction> (side <side_set_value>) ([<delay_value>])
```

- 指令名、關鍵字、directive **不分大小寫**；逗號可省略（`out pins, 3` = `out pins 3`，`jmp x-- label` = `jmp x--, label`）。
- 註解：`;` 或 `//` 單行，`/* */` 多行。
- label：`name:` 或 `PUBLIC name:`（label 其實是自動的 `.define`，值為指令偏移）。
- 數值：十進位、`0xf`、`0b1001`、`.define` 的符號、label、`(<expression>)`（必須加括號）。
- 運算式：`+ - * /`、一元 `-`、`<< >>`、`::`（位元反轉）。

| directive | 作用 |
|---|---|
| `.program <name>` | 開始一個程式（名稱用於產生的 C 程式碼） |
| `.define (PUBLIC) <sym> <value>` | 定義符號；PUBLIC 會輸出成 `#define` |
| `.origin <offset>` | 指定載入位址（常用於必須從 0 開始的程式） |
| `.wrap_target` / `.wrap` | 迴圈起點 / 終點（免費的無條件跳躍）；未指定時預設為程式開頭 / 結尾 |
| `.side_set <count> (opt) (pindirs)` | side-set 位數；`opt` 表示可省略（多佔 1 位）；`pindirs` 表示控制方向 |
| `.in <count> (left\|right) (auto) (<threshold>)` | IN 腳數、ISR 移位方向、autopush、門檻（v0 時 count 必須 32） |
| `.out <count> (left\|right) (auto) (<threshold>)` | OUT 腳數、OSR 移位方向、autopull、門檻 |
| `.set <count>` | SET 腳數 |
| `.fifo txrx\|tx\|rx\|txput\|txget\|putget` | FIFO 設定（預設 txrx；後三者需 v1） |
| `.mov_status rxfifo < n` / `txfifo < n` / `irq (prev\|next) set n` | `mov x, status` 的來源 |
| `.clock_div <divider>` | 預設時脈除頻 |
| `.pio_version 0\|1` | 目標版本（RP2350 = 1，預設） |
| `.lang_opt <lang> <name> <option>`、`.word <value>` | 語言選項、直接放 16 位原始指令 |

delay 值一般 0–31；開了 side-set 時可用位數減少。`.side_set` 沒宣告就不能寫 `side`；宣告為非 opt 時每條指令都**必須**寫 `side`。

pioasm 產生的標頭（每個程式）：`<name>_program_instructions[]`、`<name>_program`（`struct pio_program`）、`<name>_wrap_target`、`<name>_wrap`、`<name>_program_get_default_config(offset)`（內含 `sm_config_set_wrap`，以及依 directive 設好的 shift / side-set 等）。

## C5 side-set、wrap、FIFO join、autopush/autopull、clock divider、腳位

**side-set**：在執行主指令的同時改變最多 5 個腳（例如 SPI 的資料位與時脈邊緣同時發生）。設定項目：`SIDESET_COUNT`（佔用 delay 欄的位數；設 5 則沒有 delay）、`SIDE_EN`（最高位當致能，對應 `opt`）、`SIDESET_BASE`、`SIDE_PINDIR`。

```text
.program spi_tx_fast
.side_set 1
loop:
    out pins, 1   side 0
    jmp loop      side 1         ; 每 2 個週期送 1 位
```

**wrap**：`.wrap` 後面那條指令執行完（且沒跳躍）就回到 `.wrap_target`，不花週期、不佔指令。`WRAP_TOP` / `WRAP_BOTTOM` 是絕對位址，程式載入偏移後要調整（SDK 的 `_get_default_config(offset)` 已處理）。

```text
.program squarewave_fast
    set pindirs, 1
.wrap_target
    set pins, 1
    set pins, 0
.wrap
```

**FIFO join**：`FJOIN_TX` → TX 8 個、RX 沒有（PUSH 會 stall）；`FJOIN_RX` 反之。改變 FJOIN 會丟掉 FIFO 內的資料。8 個 entry 足以讓 DMA 每個時脈送 1 word。

**autopush / autopull**（門檻 1–32；暫存器值 0 代表 32）

```text
IN（autopush 開）：
  isr = shift_in(isr, input()); isr_count = sat(isr_count + n)
  if isr_count >= threshold:
      if rx fifo full: stall   else: push(isr); isr = 0; isr_count = 0

非 OUT 週期（autopull 開）：
  if MOV or PULL: osr_count = 0
  if osr_count >= threshold and tx fifo not empty: osr = pull(); osr_count = 0

OUT 週期（autopull 開）：
  if osr_count >= threshold:
      if tx fifo not empty: osr = pull(); osr_count = 0
      stall                                   ; 不能在同一週期補滿又移出
  else:
      output(osr); osr = shift(osr, n); osr_count = sat(osr_count + n)
      if osr_count >= threshold and tx fifo not empty: osr = pull(); osr_count = 0
```

- autopull 開時 OSR 是「非同步補充」的：**`MOV x, OSR` 的結果未定義**（可能是殘留資料或新 word）；需要讀 OSR 時改用明確的 PULL。
- autopull 開時 `PULL` 在 OSR 滿時是 no-op（屏障）。
- 例：`auto_push_pull` 回送程式 `out x, 32` / `in x, 32`（兩個都 auto，門檻 32）每 2 週期 1 word。

**clock divider**：16 位整數 + 8 位小數（1 ~ 65536，步進 1/256），一階 delta-sigma。整數 n：每 n 個系統週期跑 1 個 SM 週期。小數會讓部分週期長度為 n+1（有抖動；小 n 時明顯）。快速非同步序列建議用整數倍。

**GPIO 對應**：OUT（最多 32 位，LSB → OUT_BASE）、SET（最多 5 位 → SET_BASE）、side-set（最多 5 位 → SIDESET_BASE，有 SIDE_EN 時少 1）各自獨立；IN 資料依 IN_BASE 旋轉（LSB = IN_BASE 那一腳）。

## C6 Pico SDK PIO API

```c
#include "hardware/pio.h"
#include "myprog.pio.h"          // pioasm 由 myprog.pio 產生
```

| 類別 | 函式 |
|---|---|
| 實例 | `pio0`、`pio1`、`pio2`；`NUM_PIOS`、`NUM_PIO_STATE_MACHINES` |
| 載入程式 | `int pio_add_program(PIO, const pio_program_t *)` → 偏移；`pio_can_add_program`、`pio_add_program_at_offset`、`pio_remove_program`、`pio_clear_instruction_memory` |
| 取得 SM | `int pio_claim_unused_sm(PIO, bool required)`（required=false 時沒有就回 −1）、`pio_sm_claim`、`pio_sm_unclaim`、`pio_sm_is_claimed` |
| 一次搞定 | `bool pio_claim_free_sm_and_add_program(const pio_program_t *, PIO *pio, uint *sm, uint *offset)`；`pio_remove_program_and_unclaim_sm(...)` |
| 設定 | `pio_sm_config c = <name>_program_get_default_config(offset);` 或 `pio_get_default_sm_config()` |
| | `sm_config_set_out_shift(&c, bool shift_right, bool autopull, uint pull_threshold)` |
| | `sm_config_set_in_shift(&c, bool shift_right, bool autopush, uint push_threshold)` |
| | `sm_config_set_out_pins(&c, base, count)`、`sm_config_set_set_pins(&c, base, count)`、`sm_config_set_in_pins(&c, base)`、`sm_config_set_sideset_pins(&c, base)`、`sm_config_set_sideset(&c, bits, optional, pindirs)`、`sm_config_set_jmp_pin(&c, pin)` |
| | `sm_config_set_clkdiv(&c, float div)`、`sm_config_set_clkdiv_int_frac8(&c, int, frac8)`、`sm_config_set_wrap(&c, wrap_target, wrap)` |
| | `sm_config_set_fifo_join(&c, PIO_FIFO_JOIN_NONE / _TX / _RX / _TXGET / _TXPUT / _PUTGET)`、`sm_config_set_mov_status(&c, STATUS_TX_LESSTHAN / STATUS_RX_LESSTHAN / STATUS_IRQ_SET, n)`、`sm_config_set_out_special(...)` |
| 啟動 | `pio_sm_init(PIO, sm, initial_pc, &c)`（重置並套用設定，仍停用）→ `pio_sm_set_enabled(PIO, sm, true)`；`pio_set_sm_mask_enabled`、`pio_enable_sm_mask_in_sync`、`pio_sm_restart`、`pio_sm_clkdiv_restart` |
| FIFO | `pio_sm_put_blocking(PIO, sm, uint32_t)`、`uint32_t pio_sm_get_blocking(PIO, sm)`、`pio_sm_put`（滿則不做）、`pio_sm_get`（空則未定義）、`pio_sm_is_tx_fifo_full/empty`、`pio_sm_is_rx_fifo_full/empty`、`pio_sm_get_tx_fifo_level`、`pio_sm_get_rx_fifo_level`、`pio_sm_clear_fifos`、`pio_sm_drain_tx_fifo` |
| 即時執行 | `pio_sm_exec(PIO, sm, instr)`、`pio_sm_exec_wait_blocking`、`pio_sm_get_pc` |
| 腳位 | `pio_gpio_init(PIO, pin)`、`pio_sm_set_consecutive_pindirs(PIO, sm, base, count, is_out)`、`pio_sm_set_pins`、`pio_sm_set_pins_with_mask`、`pio_sm_set_pindirs_with_mask` |
| DMA | `uint pio_get_dreq(PIO, sm, bool is_tx)`；TX FIFO 位址 `&pio->txf[sm]`、RX `&pio->rxf[sm]` |
| 中斷 | `pio_set_irq0_source_enabled`、`pio_get_irq_num`、`pio_interrupt_get` / `pio_interrupt_clear`（旗標 0–7） |

**`pio_get_default_sm_config()` 的預設值**：除頻 1、wrap 0..31、**IN 與 OUT 都向右移**、不 autopush / autopull、門檻 32。

- `shift_right = true` 表示向右移：OUT 取 OSR 的最低位，IN 從最高位那端放進來。
- 門檻 0–32（32 代表整個 word）。

## C7 PIO 範例程式

以下程式（除了需要腳位的）都能用 `common/pio_sim.py` 驗證：`python3 common/pio_sim.py 檔名.pio 0x12345678`。

**1. echo（demo_pio.pio）**：假設已開 autopull（與 autopush 或手動 push）。

```text
.program echo
.wrap_target
    out x, 32       ; 從 OSR 取 32 位到 X（OSR 空時 autopull 自動補）
    in  x, 32       ; 放進 ISR
    push            ; 送回 CPU
.wrap
```

不開 autopull 的版本：

```text
.program echo_manual
.wrap_target
    pull            ; 等 CPU 送一個 word
    mov isr, osr    ; 直接複製（mov 到 ISR 會把輸入計數歸 0）
    push
.wrap
```

**2. popcount（數 1 的個數）**：從 0xFFFFFFFF 往下數，最後反相。

```text
.program popcount
.wrap_target
    pull
    mov x, ~null        ; x = 0xFFFFFFFF
loop:
    out y, 1            ; 右移：先取最低位
    jmp !y zero
    jmp x-- loop        ; 1-bit：x 減 1，直接回迴圈（x 不會是 0，一定跳）
zero:
    jmp !osre loop      ; 0-bit：還有位元就回迴圈
    mov isr, ~x         ; ~(0xFFFFFFFF - k) = k
    push
.wrap
```

每個 bit 3 週期。1-bit 可以跳過 `!osre` 檢查，是因為：最後一位若是 1，多跑一次 `out`，空的 OSR 移出 0（沒開 autopull 時），走 0 的路徑就會離開迴圈。

**3. 數 0 的個數（XNOR-popcount：CPU 送 a ^ w）**：先 `mov osr, ~osr` 反相，改成數 1。

```text
.program count_zeros
.wrap_target
    pull
    mov osr, ~osr
    mov x, ~null
loop:
    out y, 1
    jmp !y zero
    jmp x-- loop
zero:
    jmp !osre loop
    mov isr, ~x
    push
.wrap
```

**4. 位元反轉 + popcount（每個輸入輸出 2 個 word）**

```text
.wrap_target
    pull
    mov isr, ::osr      ; mov 讀 OSR 不會消耗它
    push
    mov x, ~null
loop:
    out y, 1
    jmp !y zero
    jmp x-- loop
zero:
    jmp !osre loop
    mov isr, ~x
    push
.wrap
```

**5. 把一個 word 拆成 4 個 byte 分別送出（autopull、OUT 右移）**

```text
; 設定：sm_config_set_out_shift(&c, true, true, 32); sm_config_set_in_shift(&c, false, false, 32);
.program unpack_bytes
.wrap_target
    out x, 8            ; 先取最低的 byte（OSR 右移）
    in  x, 8
    in  null, 24        ; 靠右對齊：ISR 左移時把 x 推到高位，再補 24 個 0… 錯！
.wrap
```

> ⚠ 上面是常見錯誤：ISR **左移**時，先 `in x, 8` 再 `in null, 24`，x 會被推到 bits 31..24。
> 正確做法：ISR 左移時先 `in null, 24` 再 `in x, 8`；或改用 `mov isr, x` 後 `push`（最直接）：

```text
.program unpack_bytes
.wrap_target
    pull
    set y, 3            ; 4 個 byte → 迴圈 4 次
byte:
    out x, 8
    mov isr, x          ; ISR = 這個 byte（靠右），計數歸 0
    push
    jmp y-- byte
.wrap
```

**6. 每 n 位分段送出（手動 pull、計數迴圈）**

```text
.program manual_pull            ; 來自 datasheet：每個 FIFO word 送 4 位，附時脈
.side_set 1 opt
.wrap_target
    set x, 2                    ; 位數 - 2
    pull side 1 [1]             ; TX 空時停在這裡（時脈為高）
bitloop:
    out pins, 1 side 0 [1]
    jmp x-- bitloop side 1 [1]  ; 跑 3 次
    out pins, 1 side 0
.wrap
```

**7. 方波**：`set pindirs, 1` 後 `.wrap_target / set pins, 1 / set pins, 0 / .wrap`（每 2 週期一個週期）。

**8. WS2812（datasheet 範例，X 當 24 位計數、Y 當暫存位元）**

```text
.program ws2812_led
public entry_point:
    pull
    set x, 23           ; 24 位
bitloop:
    set pins, 1
    out y, 1 [5]
    jmp !y skip         ; 0 不延長
    nop [5]
skip:
    set pins, 0 [5]
    jmp x-- bitloop
    jmp entry_point
```

**9. C 端：載入、設定、執行、收結果**

```c
#include "pico/stdlib.h"
#include "hardware/pio.h"
#include "popcount.pio.h"

int main(void) {
    stdio_init_all();
    PIO pio = pio0;
    uint offset = pio_add_program(pio, &popcount_program);
    int sm = pio_claim_unused_sm(pio, true);
    pio_sm_config c = popcount_program_get_default_config(offset);
    sm_config_set_out_shift(&c, true, false, 32);    // OSR 右移、不 autopull、門檻 32
    sm_config_set_in_shift(&c, false, false, 32);    // ISR 左移、不 autopush
    pio_sm_init(pio, sm, offset, &c);
    pio_sm_set_enabled(pio, sm, true);

    pio_sm_put_blocking(pio, sm, 0xF0F0F0F0u);
    uint32_t n = pio_sm_get_blocking(pio, sm);       // 16
    printf("popcount = %lu\n", (unsigned long)n);
}
```

（用到腳位時再加：`pio_gpio_init(pio, pin); pio_sm_set_consecutive_pindirs(pio, sm, pin, 1, true); sm_config_set_set_pins(&c, pin, 1);` 等。）

## C8 PIO 技巧與陷阱

| 技巧 / 陷阱 | 說明 |
|---|---|
| 沒有加法 | 只能用 `jmp x--` / `jmp y--` 遞減；數數從 `mov x, ~null`（0xFFFFFFFF）開始，最後 `mov isr, ~x` |
| `set` 只有 5 位 | 大常數：`mov x, ~null`；或初始化時 CPU 先送一個值，`pull` + `mov x, osr`（或 `out x, 32`） |
| 32 次迴圈 | `set x, 31` + `jmp x--`（跑 32 次）；或用 `jmp !osre` 判斷 OSR 用完 |
| 比較 | 只有 `x != y`、`!x`、`!y` |
| 反轉 / 反相 | `mov dst, ::src`（位元反轉）、`mov dst, ~src`（反相）一條搞定 |
| `.wrap` | 省掉迴圈尾的 `jmp`，0 週期 |
| autopull 與手動 pull | 開 autopull 後不要再依賴 `mov x, osr`（未定義）；PULL 在 OSR 滿時是 no-op |
| autopush 與手動 push | 不要同時讓兩者都在同一個 word 上生效 |
| 沒開 autopull 的 OUT | OSR 用完後再 `out` 會移出 0，不會停 |
| `mov isr, …` / `mov osr, …` | 會重設對應的移位計數 |
| 指令記憶體 | 一個 PIO 區塊 32 條，4 個 SM 共用 |
| 輸出順序 | 一個輸入要輸出幾個 word，就要剛好 push 幾次（或 autopush 幾次） |
| 速度 | 迴圈裡每條指令都乘以圈數；讓一個 jmp 同時計數與回圈，可以省週期 |
| FIFO 滿 / 空 | 正確的程式在任何主機速度下結果都一樣，只有時間不同（stall） |
