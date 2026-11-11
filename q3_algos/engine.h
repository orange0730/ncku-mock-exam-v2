// ============================================================================
//  搬運引擎 + 校驗（sniffer）── 大題三提供，不要修改。
//
//  搬運的部分與 demo/section2-3 相同：claim -> configure -> start -> wait -> release。
//  新增的 sniffer 對應 RP2350 DMA 的「資料搬運／校驗周邊」：
//  被 sniff 的通道在搬資料的同時，順便把「讀到的每個 byte」餵進一個 32-bit 累加器算 CRC。
//
//  對照 Pico SDK（hardware_dma）：
//    engine_sniff_enable(ch, mode)        <-> dma_sniffer_enable(ch, mode, true)
//    engine_sniff_set_accumulator(seed)   <-> dma_sniffer_set_data_accumulator(seed)
//    engine_sniff_set_output(rev, inv)    <-> dma_sniffer_set_output_reverse_enabled / _invert_enabled
//    engine_sniff_get_accumulator()       <-> dma_sniffer_get_data_accumulator()
//    engine_sniff_disable()               <-> dma_sniffer_disable()
//  （本模擬一律依記憶體位址順序、逐 byte 計算；真實硬體對 16/32-bit 傳輸的位元組順序請查 datasheet。）
// ============================================================================
#ifndef ENGINE_H
#define ENGINE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define ENGINE_CHANNELS 4

typedef enum { XFER_8 = 1, XFER_16 = 2, XFER_32 = 4 } xfer_size_t;

typedef struct {
  const void *src;
  void       *dst;
  size_t      count;          ///< number of TRANSFERS -- not a number of bytes
  xfer_size_t size;           ///< bytes per transfer
  bool        src_increment;
  bool        dst_increment;
} engine_job_t;

int  engine_claim(void);                    ///< 全部被占用時回傳 -1
void engine_configure(int ch, const engine_job_t *job);
void engine_start(int ch);
bool engine_busy(int ch);
void engine_wait(int ch);
void engine_release(int ch);

// ---- sniffer（全引擎只有一個，同一時間只能 sniff 一個通道）-----------------------
typedef enum {
  SNIFF_CRC32     = 0x0,   ///< CRC-32，多項式 0x04C11DB7，MSB-first（不反射）
  SNIFF_CRC32_REV = 0x1,   ///< 同上，但每個 byte 先做位元反轉再餵進去
  SNIFF_SUM       = 0xF,   ///< 單純把每個 byte 加總
} sniff_mode_t;

void     engine_sniff_enable(int ch, sniff_mode_t mode);  ///< ch 必須已 claim；sniffer 已在用時中止
void     engine_sniff_disable(void);
void     engine_sniff_set_accumulator(uint32_t seed);     ///< 設定累加器初值
void     engine_sniff_set_output(bool reverse, bool invert); ///< 「讀取時」先位元反轉、再反相
uint32_t engine_sniff_get_accumulator(void);

// ---- 以下只給評分用 -----------------------------------------------------------
unsigned long long engine_stat_transfers(void);
unsigned long long engine_stat_sniffed_bytes(void);
int  engine_stat_claimed_now(void);
bool engine_stat_sniff_enabled(void);
void engine_stat_reset(void);

#endif
