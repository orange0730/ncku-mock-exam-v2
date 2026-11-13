# 2-3 臨界區、鎖、搬運引擎（DMA）（考場速查）

> 來源：`demo/section2-3/2-3.README.md`、`Makefile`、`critical-section/main.c`、`transfer-engine/engine.h`、`engine.c`、`main.c`（考前練習 2-3.pdf 內容相同）、演練試題 PDF 第三節；
> 外部連結 [2] Pico SDK `hardware_dma` API（取自 SDK 原始碼 `hardware/dma.h`）、[3] OSTEP 第 28 章 *Locks*、[5] `pthread_spin_lock(3p)`；並引用 RP2350 datasheet §12.6 DMA 與 §3.1.4 硬體 spinlock。
> 標 `// file:` 的完整程式已在樹莓派（4 核心）上編譯執行驗證；Pico SDK 範例（⚠）未實機驗證，API 名稱已對照 SDK 標頭。

## 目錄

- [1. demo 怎麼跑](#1-demo-怎麼跑)
- [2. Critical section demo 逐段解析](#2-critical-section-demo-逐段解析)
- [3. pthread 與鎖的 API](#3-pthread-與鎖的-api)
- [4. 平行程式範例（race / mutex / 本地累計 / atomic）](#4-平行程式範例race--mutex--本地累計--atomic)
- [5. OSTEP 第 28 章 Locks 全章整理](#5-ostep-第-28-章-locks-全章整理)
- [6. RP2350 上的鎖與核心間通訊](#6-rp2350-上的鎖與核心間通訊)
- [7. Transfer engine demo 逐段解析](#7-transfer-engine-demo-逐段解析)
- [8. RP2350 DMA（datasheet 重點）](#8-rp2350-dmadatasheet-重點)
- [9. Pico SDK DMA API](#9-pico-sdk-dma-api)
- [10. DMA 範例程式](#10-dma-範例程式)
- [11. 「想一想」參考答案](#11-想一想參考答案)

---

## 1. demo 怎麼跑

需要 `gcc`（或 `clang`）與 `make`；Linux 直接跑、Windows 用 WSL、macOS 可。不需要開發板。

| 指令 | 作用 |
|---|---|
| `make` | 編譯（`cc -O2 -Wall -Wextra -pthread`），執行檔放 `bin/` |
| `make run` | 依序執行兩個 demo |
| `make run-critical-section` | 只跑 critical section |
| `make run-transfer-engine` | 只跑 transfer engine |
| `make mistake` | transfer engine 的「最常見錯誤」示範（`--mistake`） |
| `make clean` | 清掉 `bin/` |
| `make help` | 列出所有指令 |

---

## 2. Critical section demo 逐段解析

兩個工作者（執行緒）各把同一個 `counter` 加 1 共 20000 次，理應得 40000。

```text
expected counter = 40000   (12 CPUs available)

1. no lock            counter = 39734    LOST UPDATES     70.3 ms
2. lock, short hold   counter = 40000    ok               67.2 ms
3. lock, long hold    counter = 40000    ok              155.6 ms
```

```c
static volatile long counter;            // volatile：每次都真的讀寫記憶體（但不保證不可分割！）
static pthread_spinlock_t lock;

static uint32_t work(uint32_t x) {       // 模擬「每個工作者要做的真正工作」，故意不便宜
  for (int i = 0; i < 2000; i++) x = x * 1664525u + 1013904223u;
  return x;
}

// 1. 不上鎖：讀、加、寫三步之間可能被插隊 → 遺失更新
for (...) { sink += work(i); long v = counter; counter = v + 1; }

// 2. 短鎖：work 在鎖外，鎖只包 counter++ → 正確又快
for (...) { sink += work(i); pthread_spin_lock(&lock); counter++; pthread_spin_unlock(&lock); }

// 3. 長鎖：work 也在鎖內 → 正確但兩個工作者輪流排隊，等於單執行緒，慢一倍以上
for (...) { pthread_spin_lock(&lock); sink += work(i); counter++; pthread_spin_unlock(&lock); }
```

**三個重點**

1. 第 1 行每次結果不同而且總是少：`counter++` 是「讀出、加一、寫回」三步，另一個工作者插進空檔，一次更新就消失了。
2. 第 2 行用鎖保護三步，結果精準；被鎖保護的那段叫**臨界區（critical section）**。多核心系統常見的硬體鎖（如本例的 spinlock）保護的就是這種共用資料的讀改寫。
3. 第 3 行也對但慢一倍以上：耗時計算也在鎖內，兩個工作者輪流等對方。**鎖要抓得越短越好，只鎖真正存取共享資料的那幾行。**

> 只有一顆 CPU 的環境（某些 VM / container）第 1 行可能顯示 ok，程式開頭會提醒。那不代表沒鎖是安全的，只是兩個工作者沒有真的同時跑。程式用 `sched_getaffinity` 數「這個 process 實際能用的 CPU」，而不是整台機器有幾顆。

---

## 3. pthread 與鎖的 API

```c
#include <pthread.h>        // 編譯加 -pthread

// 執行緒
int pthread_create(pthread_t *th, const pthread_attr_t *attr, void *(*fn)(void *), void *arg);
int pthread_join(pthread_t th, void **ret);          // 等它結束；之後它寫的資料都看得到

// mutex（拿不到就睡）
pthread_mutex_t m = PTHREAD_MUTEX_INITIALIZER;       // 或 pthread_mutex_init(&m, NULL)
pthread_mutex_lock(&m);  /* 臨界區 */  pthread_mutex_unlock(&m);
pthread_mutex_trylock(&m);                           // 拿不到回 EBUSY
pthread_mutex_destroy(&m);

// spinlock（拿不到就原地打轉）
pthread_spinlock_t s;
pthread_spin_init(&s, PTHREAD_PROCESS_PRIVATE);      // 只在同一 process 內用
pthread_spin_lock(&s);   /* 臨界區 */  pthread_spin_unlock(&s);
pthread_spin_trylock(&s);                            // 拿不到回 EBUSY
pthread_spin_destroy(&s);
```

**`pthread_spin_lock(3p)` 重點（POSIX）**

| 項目 | 規定 |
|---|---|
| `pthread_spin_lock` | 鎖空著就取得；被別人拿著就**不返回**，一直 spin 到拿到 |
| `pthread_spin_trylock` | 沒人拿著才取得；否則立刻失敗 |
| 回傳值 | 成功 0；否則錯誤碼 |
| `EBUSY` | trylock 在鎖被占用時**必定**回傳 |
| `EDEADLK` | spin_lock 偵測到死結時**可能**回傳（例如自己已經拿著又鎖一次） |
| `EINVAL` | 偵測到未初始化的鎖時建議回傳 |
| `EINTR` | 兩者都不會回傳 |
| 已持有又上鎖 | **未定義行為** |
| 未初始化就用 | 未定義行為 |
| 應用注意 | 可能造成 **priority inversion** |
| 相關 | `pthread_spin_destroy`、`pthread_spin_init`、`pthread_spin_unlock` |

**mutex 與 spinlock 怎麼選**

| | mutex | spinlock |
|---|---|---|
| 拿不到時 | 睡眠，讓出 CPU | 原地打轉，燒 CPU |
| 適合 | 臨界區可能很長、執行緒比核心多 | 臨界區**極短**、每條執行緒各有核心 |
| 單核心 | 好 | 差（持有者被排程走時，等待者白白轉一整個時間片） |

**原子操作（C11，`<stdatomic.h>`）**：單一變數的計數不一定要鎖：

```c
#include <stdatomic.h>
atomic_long counter = 0;
atomic_fetch_add(&counter, 1);          // 原子地 +1（硬體：x86 lock xadd、ARM ldrex/strex、RISC-V amoadd）
long v = atomic_load(&counter);
```

---

## 4. 平行程式範例（race / mutex / 本地累計 / atomic）

```c
// file: parlab.c
// 編譯：gcc -std=gnu11 -O2 -Wall -Wextra -pthread parlab.c -o parlab && ./parlab
// 四種寫法比較：不上鎖（錯）、每次上鎖、本地累計後合併、原子操作；以及把 n 筆資料平均切給 T 條執行緒。
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>

#define THREADS 4
#define N 4000000

static uint32_t data[N];
static long shared_count;                 /* 數「低 4 位是 0」的資料筆數 */
static atomic_long atomic_count;
static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;

typedef struct { size_t begin, end; int mode; } task_t;

static void *worker(void *arg) {
    task_t *t = (task_t *)arg;
    long local = 0;
    for (size_t i = t->begin; i < t->end; i++) {
        int hit = (data[i] & 15u) == 0;   /* 「計算」 */
        if (!hit) continue;
        if (t->mode == 0) shared_count++;                                   /* 錯：race */
        else if (t->mode == 1) { pthread_mutex_lock(&mu); shared_count++; pthread_mutex_unlock(&mu); }
        else if (t->mode == 2) local++;                                     /* 本地累計 */
        else atomic_fetch_add(&atomic_count, 1);                            /* 原子 */
    }
    if (t->mode == 2) {                    /* 臨界區只有一次加法 */
        pthread_mutex_lock(&mu);
        shared_count += local;
        pthread_mutex_unlock(&mu);
    }
    return NULL;
}

static double run(int mode, long *result) {
    pthread_t th[THREADS];
    task_t tasks[THREADS];
    struct timespec a, b;
    shared_count = 0;
    atomic_store(&atomic_count, 0);
    clock_gettime(CLOCK_MONOTONIC, &a);
    for (int t = 0; t < THREADS; t++) {
        /* 切法：[n*t/T, n*(t+1)/T)，餘數平均分散、最後一段剛好到 n */
        tasks[t] = (task_t){ (size_t)N * t / THREADS, (size_t)N * (t + 1) / THREADS, mode };
        pthread_create(&th[t], NULL, worker, &tasks[t]);
    }
    for (int t = 0; t < THREADS; t++) pthread_join(th[t], NULL);
    clock_gettime(CLOCK_MONOTONIC, &b);
    *result = mode == 3 ? atomic_load(&atomic_count) : shared_count;
    return (b.tv_sec - a.tv_sec) * 1e3 + (b.tv_nsec - a.tv_nsec) / 1e6;
}

int main(void) {
    uint32_t x = 1;
    long expect = 0;
    for (size_t i = 0; i < N; i++) {
        x ^= x << 13; x ^= x >> 17; x ^= x << 5;          /* xorshift 亂數 */
        data[i] = x;
        expect += (x & 15u) == 0;
    }
    const char *names[] = {"no lock (race)", "mutex every time", "local + merge", "atomic"};
    for (int mode = 0; mode < 4; mode++) {
        long got;
        double ms = run(mode, &got);
        printf("%-18s count=%-8ld %-12s %7.1f ms\n", names[mode], got, got == expect ? "ok" : "LOST UPDATES", ms);
    }
    printf("expected %ld\n", expect);
    return 0;
}
```

典型結果（4 核心）：no lock 少算、mutex 每次上鎖正確但最慢、本地累計最快、atomic 介於中間。

**平行程式的規則**

- 能不共享就不共享：每條執行緒寫自己的區域變數，最後合併一次。
- `pthread_join` 之後讀執行緒寫的資料不用鎖（join 保證可見性）。
- 傳給每條執行緒的參數要各自一份（`tasks[t]`），不要都傳同一個區域變數的位址。
- 切工作用 `[n*t/T, n*(t+1)/T)`；`T > n` 時有些執行緒分到空區間，最好直接少開幾條。
- 死結四條件：互斥、持有並等待、不可搶奪、循環等待。預防：**所有人用同一順序拿多把鎖**；持有鎖時不要去等別的事。

---

## 5. OSTEP 第 28 章 Locks 全章整理

**28.1 基本概念**：在臨界區前後 `lock(&mutex)` / `unlock(&mutex)`，讓它像一條原子指令。鎖是一個變數，狀態只有「可用（free）」或「已取得（held）」，持有者叫 owner。`lock()` 在鎖被持有時不會返回；`unlock()` 後若有人在等，其中一個會取得鎖。鎖讓程式設計師拿回一點排程的控制權。

**28.2 Pthread 鎖**：POSIX 的鎖叫 **mutex**（mutual exclusion）。`pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER; pthread_mutex_lock(&lock); ...; pthread_mutex_unlock(&lock);`。可以用不同的鎖保護不同的資料：**粗粒度**（一把大鎖）vs **細粒度**（多把小鎖，並行度較高）。

**28.3 怎麼做出一把鎖**：需要硬體支援（更強的指令）與作業系統支援。

**28.4 評估一把鎖的三個標準**

1. **正確性 / 互斥**：能不能擋住多個執行緒同時進入臨界區？
2. **公平性**：每個等待者都有機會拿到嗎？會不會有人**餓死（starve）**？
3. **效能**：沒有競爭時的成本；單一 CPU 多執行緒競爭時；多 CPU 競爭時。

**28.5 關中斷**：`lock()` = 關中斷、`unlock()` = 開中斷。優點是簡單。缺點：要讓任意程式執行特權操作（可能被濫用，例如 lock 後無窮迴圈，只能重開機）；**多處理器無效**（其他 CPU 照樣進臨界區）；長時間關中斷會遺失中斷。只適合作業系統內部的有限情況。

**28.6 失敗的嘗試：只用 load / store**

```c
void lock(lock_t *m)   { while (m->flag == 1) ; m->flag = 1; }   // 檢查與設定之間可能被插隊
void unlock(lock_t *m) { m->flag = 0; }
```

兩個問題：**正確性**（兩個執行緒都看到 flag = 0，都設成 1，都進去）；**效能**（spin-waiting 浪費 CPU，單處理器上特別糟）。
旁註：**Dekker / Peterson 演算法**只用 load / store 也能做到兩個執行緒的互斥（`flag[2]` 表示意願、`turn` 表示輪到誰），但在現代硬體上因為寬鬆的記憶體一致性模型而不成立。

**28.7 Test-and-Set（atomic exchange）自旋鎖**

```c
int TestAndSet(int *old_ptr, int new) { int old = *old_ptr; *old_ptr = new; return old; }  // 硬體保證原子
void lock(lock_t *l)   { while (TestAndSet(&l->flag, 1) == 1) ; }
void unlock(lock_t *l) { l->flag = 0; }
```

SPARC 叫 `ldstub`、x86 是加了 lock 的 `xchg`、RISC-V 是 `amoswap`。單處理器上要能正確運作，需要**搶佔式排程器**（timer 中斷），否則 spin 的執行緒永遠不讓出 CPU。
秘訣：**把自己想成惡意的排程器**，在最糟的時機中斷執行緒，看看鎖會不會壞。

**28.8 評估自旋鎖**：正確 ✓；**不公平**（可能永遠 spin，會餓死）；效能：單 CPU 很差（持有者被搶佔時，N−1 個執行緒各浪費一個時間片），多 CPU 且執行緒數 ≈ CPU 數、臨界區短時還不錯。

**28.9 Compare-and-Swap（CAS，x86 叫 compare-and-exchange）**

```c
int CompareAndSwap(int *ptr, int expected, int new) {
    int original = *ptr;
    if (original == expected) *ptr = new;
    return original;
}
void lock(lock_t *l) { while (CompareAndSwap(&l->flag, 0, 1) == 1) ; }
```

比 test-and-set 強（可做 lock-free 資料結構），但當自旋鎖用時行為相同。

**28.10 Load-Linked / Store-Conditional（MIPS、Alpha、PowerPC、ARM；RISC-V 的 `lr.w` / `sc.w`）**

```c
int LoadLinked(int *ptr) { return *ptr; }
int StoreConditional(int *ptr, int value) {
    if (/* 自從 LL 之後沒有人寫過 *ptr */) { *ptr = value; return 1; }   // 成功
    return 0;                                                              // 失敗
}
void lock(lock_t *l) {
    while (1) {
        while (LoadLinked(&l->flag) == 1) ;            // 等到 0
        if (StoreConditional(&l->flag, 1) == 1) return; // 搶到了
    }                                                   // 被別人搶先：重來
}
// 精簡版：while (LoadLinked(&l->flag) || !StoreConditional(&l->flag, 1)) ;
```

**28.11 Fetch-and-Add 與 ticket lock（公平）**

```c
int FetchAndAdd(int *ptr) { int old = *ptr; *ptr = old + 1; return old; }
typedef struct { int ticket; int turn; } lock_t;
void lock(lock_t *l)   { int myturn = FetchAndAdd(&l->ticket); while (l->turn != myturn) ; }
void unlock(lock_t *l) { l->turn = l->turn + 1; }
```

拿號碼牌，輪到才進去：**保證每個執行緒都會前進**（不會餓死）。秘訣：**Lauer's Law：程式碼越少越好**。

**28.12 太多 spin 怎麼辦**：持有者在臨界區被中斷時，其他人白轉。純硬體解決不了，需要作業系統支援。

**28.13 改用 yield**

```c
void lock() { while (TestAndSet(&flag, 1) == 1) yield(); }   // 拿不到就讓出 CPU
```

兩個執行緒時不錯；100 個執行緒時每個都要經過一次 run-and-yield，context switch 成本高；**仍可能餓死**。

**28.14 用佇列睡覺（Solaris 的 park / unpark）**

```c
typedef struct { int flag; int guard; queue_t *q; } lock_t;
void lock(lock_t *m) {
    while (TestAndSet(&m->guard, 1) == 1) ;        // 用短暫 spin 保護鎖本身的資料
    if (m->flag == 0) { m->flag = 1; m->guard = 0; }
    else { queue_add(m->q, gettid()); m->guard = 0; park(); }      // 排隊、睡覺
}
void unlock(lock_t *m) {
    while (TestAndSet(&m->guard, 1) == 1) ;
    if (queue_empty(m->q)) m->flag = 0;            // 沒人要
    else unpark(queue_remove(m->q));               // 直接把鎖交給下一個（flag 保持 1）
    m->guard = 0;
}
```

- guard 只在鎖程式碼內 spin 幾條指令，時間很短。
- 被喚醒的執行緒等於直接接手，所以 `flag` 不歸零。
- 若 `guard = 0` 放在 `park()` 之後 → 睡著還抱著 guard，死結。
- **wakeup / waiting race**：在 `park()` 之前被切走、鎖剛好被釋放 → 可能永遠睡。Solaris 用 `setpark()`：先宣告要睡，若期間已被 unpark，`park()` 立刻返回。
- 旁註 **priority inversion**：低優先權 T1 拿著自旋鎖，高優先權 T2 一直 spin，T1 永遠跑不到 → 系統卡死。三執行緒版本：T3（高）等 T1（低）的鎖，T2（中）一直跑，T3 被 T2 間接卡住。解法：避免自旋鎖、**priority inheritance**（暫時提高持有者優先權）、所有執行緒同優先權。（真實案例：火星探路者號）

**28.15 Linux futex**

- `futex_wait(address, expected)`：若 `*address == expected` 就睡，否則立刻返回。
- `futex_wake(address)`：喚醒一個等待者。
- glibc 的實作用一個整數：最高位（bit 31）表示鎖是否被持有（所以被持有時整數為負），其餘位元記等待者數量。沒競爭時只有一次原子 bit test-and-set 加鎖、一次原子加法解鎖（fast path）。

**28.16 Two-phase lock**：第一階段先 spin 一下（鎖可能馬上被釋放），拿不到再進第二階段睡覺。Linux 的 futex 鎖就是一種（只 spin 一次）。

**28.17 結論**：真實的鎖 = 硬體支援（更強的原子指令）+ 作業系統支援（park / unpark、futex）。

**作業（x86.py 模擬器）**：`flag.s`（單一旗標鎖會不會壞）、`-M -R -c` 追變數與暫存器、`-a bx=…` 設迴圈次數、`-i` 改中斷頻率找出壞掉的時機、`test-and-set.s`（xchg 自旋鎖）、`-P` 指定排程、`peterson.s`、`ticket.s`、`yield.s`（比較省了多少指令）、`test-and-test-and-set.s`（先讀到 0 再嘗試 xchg，減少寫入）。

---

## 6. RP2350 上的鎖與核心間通訊

| 機制 | 說明 |
|---|---|
| **SIO 硬體 spinlock ×32** | 每個是 1 位元旗標，對應 `SPINLOCK0`..`SPINLOCK31`。**讀取 = 嘗試取得**（非 0 表示成功，0 表示已被拿走）；**寫入任意值 = 釋放**。兩個核心同一週期搶同一把，core 0 勝。只適合保護**很短**的臨界區（或用來實作 mutex、semaphore、queue 等更高階的同步）。`SPINLOCK_ST` 可看全部狀態 |
| 原子指令 | 兩種核心都支援 exclusive / atomic 指令（Arm `ldrex/strex`、RISC-V `lr/sc`、`amo*`），配合全域 exclusive monitor 可安全共享 SRAM 變數。RP2350 A2 有 erratum RP2350-E2，SDK 預設用原子指令實作 `hardware_sync` 的 spin lock |
| 核心間 FIFO（mailbox） | 兩個方向各一個，32 位寬、4 個 entry。寫 `FIFO_WR`、讀 `FIFO_RD`，`FIFO_ST` 有 VLD（有資料）、RDY（有空位）、ROE（空時讀）、WOF（滿時寫）。滿時寫 / 空時讀不改變 FIFO，但會設黏著錯誤旗標 |
| Doorbell | 每方向 8 個旗標，觸發對方核心的中斷 |

**Pico SDK**⚠

```c
#include "pico/multicore.h"
multicore_launch_core1(core1_entry);          // 啟動 core 1
multicore_fifo_push_blocking(uint32_t v);     // 送給另一顆核心
uint32_t v = multicore_fifo_pop_blocking();   // 從另一顆核心收
bool multicore_fifo_push_timeout_us(uint32_t v, uint64_t us);
bool multicore_fifo_pop_timeout_us(uint64_t us, uint32_t *out);
multicore_fifo_rvalid(); multicore_fifo_wready(); multicore_fifo_drain();

#include "pico/sync.h"
mutex_t m;              mutex_init(&m);       mutex_enter_blocking(&m);  ...  mutex_exit(&m);
critical_section_t cs;  critical_section_init(&cs);
critical_section_enter_blocking(&cs);  ...  critical_section_exit(&cs);    // 也會關本核心的中斷
spin_lock_t *lk = spin_lock_init(spin_lock_claim_unused(true));
uint32_t save = spin_lock_blocking(lk);  ...  spin_unlock(lk, save);       // 關中斷並取得
```

雙核心平行推論的範例見 [3_去年題型與今年預測.md §4.5](3_去年題型與今年預測.md#45-今年可能rp2350-雙核心平行一片板子內-)。

---

## 7. Transfer engine demo 逐段解析

假想的「搬運引擎」是 CPU 之外的獨立單元。你不寫複製迴圈，而是**描述**工作：從哪讀、寫到哪、幾筆、每筆多大、哪一邊的位址要前進。描述完就啟動，然後去做別的事，之後回來收結果。

```text
描述 (configure) → 啟動 (start) → 等待 (wait / busy) → 取用結果
```

**API（engine.h）**

```c
#define ENGINE_CHANNELS 4
typedef enum { XFER_8 = 1, XFER_16 = 2, XFER_32 = 4 } xfer_size_t;   // 每筆只能 1、2、4 bytes

typedef struct {
  const void *src;
  void       *dst;
  size_t      count;          // 幾「筆」傳輸，不是幾個 bytes
  xfer_size_t size;           // 每筆幾 bytes
  bool        src_increment;  // 來源位址要不要前進
  bool        dst_increment;  // 目的位址要不要前進
} engine_job_t;

int  engine_claim(void);                              // 取得一個空通道；全部被占用回傳 -1
void engine_configure(int ch, const engine_job_t *job);
void engine_start(int ch);                            // 立刻返回，搬運在背景進行
bool engine_busy(int ch);
void engine_wait(int ch);                             // 等到這個通道搬完
void engine_release(int ch);                          // 歸還通道
```

**引擎會拒絕（印出原因並結束程式）的情況**：通道編號不存在（例如拿 −1 來用）、沒 claim、執行中 configure、size 不是 1/2/4、**count 為 0**、src 或 dst 沒有對齊 size、還沒 configure 就 start、執行中 start、執行中 release。

**main.c 的三段**

```c
// 1. 複製 4096 個 word：兩邊都前進
engine_job_t copy = { .src = src, .dst = dst, .count = N, .size = XFER_32,
                      .src_increment = true, .dst_increment = true };
engine_configure(ch, &copy);
engine_start(ch);
while (engine_busy(ch)) { spins++; ... }     // 證明「啟動後程式還能繼續跑」
engine_wait(ch);

// 2. 填值：來源不前進（一直讀同一個 pattern）
uint32_t pattern = 0xA5A5A5A5u;
engine_job_t fill = { .src = &pattern, .dst = dst, .count = N, .size = XFER_32,
                      .src_increment = false, .dst_increment = true };

// 3. make mistake：count 填成 bytes
wrong.count = N * sizeof(uint32_t);           // 4 倍的量！引擎不會抱怨，照做了，寫出界 3*N 個 word
```

輸出：

```text
claimed channel 0 (there are 4)
1. copy 4096 words          dst matches src
   while it ran, this program went round its own loop 98705538 times
2. fill 4096 words          every word is 0xA5A5A5A5
   same engine, same count -- only the increment flags changed
```

**四個要記的點**

1. **`count` 是「幾筆傳輸」，不是「幾個 bytes」**（最常見的錯）。`bytes = count × size`。
2. **位址要不要遞增是描述的一部分**：複製與填值是同一個引擎、同樣的筆數，差別只在來源位址走不走。
3. **每筆只能 1、2、4 bytes，位址要對齊**，否則引擎停下來告訴你違反哪條規則。
4. **通道是有限資源**：用前取得、用完歸還。這個引擎只有 4 個。

**這個程式沒辦法示範的事**：demo 的引擎是一條執行緒，還是占了你電腦一顆核心；真正的 DMA 消耗的是**記憶體匯流排頻寬**，不是 CPU 指令，搬運期間 CPU 真的空出來。所以「主程式跑了幾圈」只能說明啟動後程式能繼續跑，**不能說明這件事沒有成本**。

**選大小的公式**：`m = (uintptr_t)src | (uintptr_t)dst | nbytes; size = (m & 3) == 0 ? 4 : (m & 1) == 0 ? 2 : 1; count = nbytes / size;`

---

## 8. RP2350 DMA（datasheet 重點）

| 項目 | 內容 |
|---|---|
| 通道數 | **16**（RP2040 是 12）；共用 IRQ 輸出 4 個（RP2040 是 2） |
| 每個通道的 4 個暫存器 | `READ_ADDR`（下一個讀的位址）、`WRITE_ADDR`、`TRANS_COUNT`（剩幾筆 / 下一次要幾筆）、`CTRL`（其他所有設定、啟用、狀態） |
| 位址遞增 | 依 `DATA_SIZE`（1/2/4 bytes）與 `INCR_READ`/`INCR_WRITE`、`INCR_READ_REV`/`INCR_WRITE_REV`：每次加 size × (−1、0、1 或 2) |
| 位址對齊 | **必須對齊 size；DMA 不會檢查**（由軟體負責），未對齊的結果未指定 |
| `TRANS_COUNT` | **筆數**；總 bytes = TRANS_COUNT × DATA_SIZE。RP2350 低 28 位是筆數（最多 2²⁸−1），高 4 位是 MODE |
| MODE | `0x0` 一般（數到 0 停）；`0x1` TRIGGER_SELF（做完自動重新觸發，適合環形緩衝區定期中斷）；`0xF` ENDLESS（不遞減，永遠跑；count 0 會立刻停） |
| 重新觸發 | 沒重寫 `TRANS_COUNT` 時每次觸發做一樣的筆數；位址沒重寫時從目前位址接著做 |
| 觸發方式 | 寫入 trigger 暫存器（各種 alias）、另一個通道完成時 `CHAIN_TO` 指向它、寫 `MULTI_CHAN_TRIGGER`（同時觸發多個）。觸發後 `CTRL.BUSY = 1`；**BUSY 時忽略新的觸發**；`CTRL.EN` 為 0 也忽略 |
| chaining | `CHAIN_TO` 4 位；指向自己 = 不串接。用途：控制區塊（通道 A 寫通道 B 的設定）、ping-pong（兩通道互相觸發，設定與傳輸 pipeline） |
| null trigger | 寫全 0 到 trigger 暫存器不會啟動；用來結束控制區塊串列。`IRQ_QUIET = 1` 時只有收到 null trigger 才發中斷 |
| DREQ | 讓周邊控制 DMA 速度（`CTRL.TREQ_SEL`）。表：0 = `DREQ_PIO0_TX0`、1 = `PIO0_TX1`、2 = `PIO0_TX2`、3 = `PIO0_TX3`…（程式裡用 `pio_get_dreq()` 或 `DREQ_xxx` 常數，不要自己算編號）。也可選 4 個 pacing timer 或不限速（記憶體對記憶體） |
| Pacing timer | 4 個，分數（X/Y）除頻，每 n 個時脈送一個請求 |
| **CRC 計算（sniffer）** | 被選定的通道搬資料時旁觀資料並計算，不改資料。支援：**CRC-32（MSB-first 與 LSB-first）**、CRC-16-CCITT（兩種）、加總（32 位累加）、偶同位。結果暫存器可讀可寫（寫入 = 設定初值 seed）。讀出時可做位元反相、位元反轉、byte swap（只影響呈現，不影響計算）。必須跟得上每時脈 32 位 |
| Abort | `CHAN_ABORT` 每通道一位。RP2350 正確順序：① 清掉要中止通道的 EN 並關閉 CHAIN_TO ② 寫 `CHAN_ABORT` ③ 輪詢直到 ABORT 位元清除。BUSY 清除前不要重新啟動（erratum RP2350-E5） |
| 安全 | 通道、IRQ、timer、sniffer 都可指定安全等級；DMA 有內建 MPU |

---

## 9. Pico SDK DMA API

```c
#include "hardware/dma.h"
```

| 類別 | 函式 |
|---|---|
| 取得 / 歸還通道 | `int dma_claim_unused_channel(bool required)`（required=false 時沒有就回 −1；true 時沒有會 panic）、`dma_channel_claim(ch)`、`dma_channel_unclaim(ch)`、`dma_claim_mask`、`dma_unclaim_mask`、`dma_channel_is_claimed` |
| 設定 | `dma_channel_config c = dma_channel_get_default_config(ch);` |
| | `channel_config_set_transfer_data_size(&c, DMA_SIZE_8 / DMA_SIZE_16 / DMA_SIZE_32)` |
| | `channel_config_set_read_increment(&c, bool)`、`channel_config_set_write_increment(&c, bool)` |
| | `channel_config_set_dreq(&c, dreq)`（`DREQ_FORCE` = 不限速） |
| | `channel_config_set_chain_to(&c, other_ch)`、`channel_config_set_ring(&c, write, size_bits)`、`channel_config_set_bswap(&c, bool)`、`channel_config_set_irq_quiet`、`channel_config_set_high_priority`、`channel_config_set_enable`、`channel_config_set_sniff_enable(&c, bool)` |
| | RP2350：`channel_config_set_read_address_update_type` / `_write_address_update_type`（NONE / INCREMENT / INCREMENT_BY_TWO / DECREMENT） |
| 預設值 | **讀遞增、寫不遞增**、不限速（`DREQ_FORCE`）、chain 到自己、**32 位**、無 ring、無 bswap、啟用、不 sniff、低優先 |
| 設定 + 啟動 | `dma_channel_configure(ch, &c, write_addr, read_addr, transfer_count, bool trigger)` ← **寫入位址在前、讀取位址在後**（同 `memcpy(dst, src, n)`）；`transfer_count` 是**筆數** |
| | `dma_channel_set_config`、`dma_channel_set_read_addr`、`dma_channel_set_write_addr`、`dma_channel_set_trans_count`（每個都有 `trigger` 參數） |
| | `dma_channel_start(ch)`、`dma_start_channel_mask(mask)`、`dma_channel_transfer_from_buffer_now`、`dma_channel_transfer_to_buffer_now` |
| 筆數編碼 | `dma_encode_transfer_count(n)`；RP2350：`dma_encode_transfer_count_with_self_trigger(n)`、`dma_encode_endless_transfer_count()` |
| 狀態 | `bool dma_channel_is_busy(ch)`、`dma_channel_wait_for_finish_blocking(ch)`（等完並加記憶體屏障）、`dma_channel_abort(ch)`、`dma_channel_cleanup(ch)` |
| 中斷 | `dma_channel_set_irq0_enabled(ch, bool)`、`dma_irqn_set_channel_enabled(irq, ch, bool)`、`dma_channel_get_irq0_status`、`dma_channel_acknowledge_irq0(ch)`、`dma_irqn_acknowledge_channel` |
| **sniffer** | `dma_sniffer_enable(ch, mode, force_channel_enable)`；mode：`0x0` CRC-32、`0x1` CRC-32 bit-reversed data、`0x2` CRC-16-CCITT、`0x3` CRC-16 reversed、`0xe` XOR（popcount 奇偶）、`0xf` 32 位加總 |
| | `dma_sniffer_set_data_accumulator(seed)`、`uint32_t dma_sniffer_get_data_accumulator()`、`dma_sniffer_set_output_invert_enabled(bool)`、`dma_sniffer_set_output_reverse_enabled(bool)`、`dma_sniffer_set_byte_swap_enabled(bool)`、`dma_sniffer_disable()` |
| timer | `dma_claim_unused_timer`、`dma_timer_set_fraction(timer, num, den)`、`dma_get_timer_dreq(timer)` |

**demo engine ↔ Pico SDK 對照**

| demo | Pico SDK |
|---|---|
| `engine_claim()` | `dma_claim_unused_channel(false)` |
| `.size = XFER_32` | `channel_config_set_transfer_data_size(&c, DMA_SIZE_32)` |
| `.src_increment` / `.dst_increment` | `channel_config_set_read_increment` / `_write_increment` |
| `.count` | `dma_channel_configure(..., transfer_count, ...)` |
| `engine_start()` | `trigger = true` 或 `dma_channel_start()` |
| `engine_busy()` | `dma_channel_is_busy()` |
| `engine_wait()` | `dma_channel_wait_for_finish_blocking()` |
| `engine_release()` | `dma_channel_unclaim()` |

---

## 10. DMA 範例程式

**1. 用 DMA 複製記憶體（memcpy）**⚠

```c
#include "hardware/dma.h"

void dma_memcpy32(uint32_t *dst, const uint32_t *src, size_t words) {
    if (words == 0) return;
    int ch = dma_claim_unused_channel(true);
    dma_channel_config c = dma_channel_get_default_config(ch);
    channel_config_set_transfer_data_size(&c, DMA_SIZE_32);
    channel_config_set_read_increment(&c, true);
    channel_config_set_write_increment(&c, true);          // 預設是 false，複製要開
    dma_channel_configure(ch, &c, dst, src, words, true);  // 寫在前、讀在後；筆數；立刻啟動
    // ... CPU 可以做別的事 ...
    dma_channel_wait_for_finish_blocking(ch);
    dma_channel_unclaim(ch);
}
```

**2. 填值（memset）**：讀位址不遞增：`channel_config_set_read_increment(&c, false); channel_config_set_write_increment(&c, true);`，`read_addr = &pattern`。

**3. 用 sniffer 算 CRC-32**⚠

```c
uint32_t dma_crc32(const uint8_t *buf, size_t len) {
    if (len == 0) return 0;                          // 引擎 / DMA 不要給 0 筆
    static uint8_t sink;
    int ch = dma_claim_unused_channel(true);
    dma_channel_config c = dma_channel_get_default_config(ch);
    channel_config_set_transfer_data_size(&c, DMA_SIZE_8);    // 逐 byte，位址不用對齊
    channel_config_set_read_increment(&c, true);
    channel_config_set_write_increment(&c, false);            // 資料只是「流過」sniffer
    channel_config_set_sniff_enable(&c, true);
    dma_sniffer_enable(ch, 0x1, true);                        // 0x1：CRC-32、資料位元反轉（反射輸入）
    dma_sniffer_set_data_accumulator(0xFFFFFFFFu);            // init
    dma_sniffer_set_output_reverse_enabled(true);             // refout
    dma_sniffer_set_output_invert_enabled(true);              // xorout
    dma_channel_configure(ch, &c, &sink, buf, len, true);
    dma_channel_wait_for_finish_blocking(ch);
    uint32_t crc = dma_sniffer_get_data_accumulator();
    dma_sniffer_disable();
    dma_channel_unclaim(ch);
    return crc;                                               // 應等於標準 CRC-32（"123456789" → 0xCBF43926）
}
```

> 這組設定（mode 0x1 + seed 0xFFFFFFFF + 輸出反轉 + 輸出反相）在模擬考的引擎模型與 Python 中驗證過等於標準 CRC-32。真實硬體在 16 / 32 位傳輸時的位元組順序請用 SDK 範例 `dma/sniff_crc` 或已知向量驗證；必要時開 `dma_sniffer_set_byte_swap_enabled`。用 8 位傳輸最單純。

**4. DMA 把資料餵給 PIO（DREQ 控速）**⚠

```c
int ch = dma_claim_unused_channel(true);
dma_channel_config c = dma_channel_get_default_config(ch);
channel_config_set_transfer_data_size(&c, DMA_SIZE_32);
channel_config_set_read_increment(&c, true);              // 從陣列讀
channel_config_set_write_increment(&c, false);            // 一直寫同一個位址：PIO 的 TX FIFO
channel_config_set_dreq(&c, pio_get_dreq(pio, sm, true)); // TX FIFO 有空位才送下一筆
dma_channel_configure(ch, &c, &pio->txf[sm], words, n_words, true);
// PIO → 記憶體：讀 &pio->rxf[sm]、讀不遞增、寫遞增、dreq = pio_get_dreq(pio, sm, false)
```

**5. 多個工作比通道多時的排程**（對應 demo「通道是有限資源」）

```text
while 還有工作:
    ch = claim()
    while ch == -1:                 # 通道滿了
        等「最早開始」的那個完成、release 它
        ch = claim()
    configure + start               # 不要在這裡 wait（否則並行度永遠是 1）
    記下 ch
最後把剩下的全部 wait + release
```

---

## 11. 「想一想」參考答案

1. **把 critical section 範例「鎖的範圍」改成只鎖讀取、不鎖寫回？**
   一樣會遺失更新。A 在鎖內讀到 5、解鎖，B 也在鎖內讀到 5、解鎖，兩人都寫回 6。鎖必須涵蓋整個「讀 → 改 → 寫」。
2. **transfer engine 的四個通道都被占用時，第五個搬運請求怎麼處理？與一般的有限資源有何相似？**
   策略：等某個通道完成並歸還後再派（阻塞等待）；立刻回報失敗（`engine_claim()` 回傳 −1、SDK 的 `required = false`），讓呼叫者決定；排進佇列，有通道歸還時再派；或退回由 CPU 自己搬。這和執行緒池、資料庫連線池、檔案描述子、記憶體一樣：**使用前取得、用完一定要歸還**、取得失敗要處理、等待時不要抱著別的資源（避免死結）。
