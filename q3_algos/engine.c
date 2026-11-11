// 搬運引擎 + sniffer 的實作（大題三提供，不要修改）。
// 用 pthread 模擬硬體：忠實的是「介面與規則」，不是「不花 CPU」這件事。
#include "engine.h"

#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void die(const char *what) {
  fprintf(stderr, "ENGINE_ERROR %s\n", what);
  fflush(stderr);
  const char *path = getenv("ENGINE_ERROR_FILE");   // 評分程式用來取得中止原因
  if (path) {
    FILE *f = fopen(path, "w");
    if (f) { fputs(what, f); fclose(f); }
  }
  abort();
}

typedef struct {
  bool         claimed, configured, joinable;
  atomic_bool  busy;
  engine_job_t job;
  pthread_t    th;
} channel_t;

static channel_t chans[ENGINE_CHANNELS];
static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
static unsigned long long st_transfers, st_sniffed;

static int sniff_ch = -1;
static sniff_mode_t sniff_mode;
static uint32_t sniff_acc;
static bool out_rev, out_inv;

static void check_channel(int ch) {
  if (ch < 0 || ch >= ENGINE_CHANNELS) die("no such channel (did engine_claim() return -1?)");
  if (!chans[ch].claimed) die("that channel was never claimed");
}

int engine_claim(void) {
  pthread_mutex_lock(&mu);
  for (int i = 0; i < ENGINE_CHANNELS; i++) {
    if (!chans[i].claimed) {
      chans[i].claimed = true;
      pthread_mutex_unlock(&mu);
      return i;
    }
  }
  pthread_mutex_unlock(&mu);
  return -1;
}

void engine_configure(int ch, const engine_job_t *job) {
  check_channel(ch);
  if (atomic_load(&chans[ch].busy)) die("the channel is still running the previous job");
  if (job->size != XFER_8 && job->size != XFER_16 && job->size != XFER_32)
    die("transfer size must be 1, 2 or 4 bytes");
  if (job->count == 0) die("count is zero -- count is the number of transfers, not bytes");
  if (((uintptr_t)job->src % (uintptr_t)job->size) != 0) die("source address is not aligned to the transfer size");
  if (((uintptr_t)job->dst % (uintptr_t)job->size) != 0) die("destination address is not aligned to the transfer size");
  chans[ch].job = *job;
  chans[ch].configured = true;
}

static uint32_t crc_byte(uint32_t acc, uint8_t b) {
  acc ^= (uint32_t)b << 24;
  for (int i = 0; i < 8; i++) acc = (acc & 0x80000000u) ? (acc << 1) ^ 0x04C11DB7u : (acc << 1);
  return acc;
}

static uint8_t rev8(uint8_t b) {
  uint8_t r = 0;
  for (int i = 0; i < 8; i++) r = (uint8_t)((r << 1) | ((b >> i) & 1u));
  return r;
}

static void *run_job(void *arg) {
  channel_t *c = (channel_t *)arg;
  int ch = (int)(c - chans);
  const unsigned char *s = (const unsigned char *)c->job.src;
  unsigned char *d = (unsigned char *)c->job.dst;
  size_t step = (size_t)c->job.size;
  for (size_t i = 0; i < c->job.count; i++) {
    unsigned char tmp[4];
    memcpy(tmp, s, step);
    memcpy(d, tmp, step);
    pthread_mutex_lock(&mu);
    if (sniff_ch == ch) {
      for (size_t k = 0; k < step; k++) {
        if (sniff_mode == SNIFF_SUM) sniff_acc += tmp[k];
        else sniff_acc = crc_byte(sniff_acc, sniff_mode == SNIFF_CRC32_REV ? rev8(tmp[k]) : tmp[k]);
      }
      st_sniffed += step;
    }
    pthread_mutex_unlock(&mu);
    if (c->job.src_increment) s += step;
    if (c->job.dst_increment) d += step;
  }
  pthread_mutex_lock(&mu);
  st_transfers += c->job.count;
  pthread_mutex_unlock(&mu);
  atomic_store(&c->busy, false);
  return NULL;
}

void engine_start(int ch) {
  check_channel(ch);
  if (!chans[ch].configured) die("nothing was configured on that channel yet");
  if (atomic_load(&chans[ch].busy)) die("that channel is already running");
  if (chans[ch].joinable) { pthread_join(chans[ch].th, NULL); chans[ch].joinable = false; }
  atomic_store(&chans[ch].busy, true);
  if (pthread_create(&chans[ch].th, NULL, run_job, &chans[ch]) != 0) die("could not start worker thread");
  chans[ch].joinable = true;
}

bool engine_busy(int ch) { check_channel(ch); return atomic_load(&chans[ch].busy); }

void engine_wait(int ch) {
  check_channel(ch);
  if (chans[ch].joinable) { pthread_join(chans[ch].th, NULL); chans[ch].joinable = false; }
}

void engine_release(int ch) {
  check_channel(ch);
  if (atomic_load(&chans[ch].busy)) die("release while the channel is still running");
  if (chans[ch].joinable) { pthread_join(chans[ch].th, NULL); chans[ch].joinable = false; }
  pthread_mutex_lock(&mu);
  if (sniff_ch == ch) { pthread_mutex_unlock(&mu); die("release while the sniffer is still attached to this channel"); }
  chans[ch].claimed = chans[ch].configured = false;
  pthread_mutex_unlock(&mu);
}

void engine_sniff_enable(int ch, sniff_mode_t mode) {
  check_channel(ch);
  if (mode != SNIFF_CRC32 && mode != SNIFF_CRC32_REV && mode != SNIFF_SUM) die("unknown sniff mode");
  pthread_mutex_lock(&mu);
  if (sniff_ch >= 0 && sniff_ch != ch) { pthread_mutex_unlock(&mu); die("the sniffer is already attached to another channel"); }
  sniff_ch = ch;
  sniff_mode = mode;
  pthread_mutex_unlock(&mu);
}

void engine_sniff_disable(void) {
  pthread_mutex_lock(&mu);
  sniff_ch = -1;
  pthread_mutex_unlock(&mu);
}

void engine_sniff_set_accumulator(uint32_t seed) {
  pthread_mutex_lock(&mu);
  sniff_acc = seed;
  pthread_mutex_unlock(&mu);
}

void engine_sniff_set_output(bool reverse, bool invert) {
  pthread_mutex_lock(&mu);
  out_rev = reverse;
  out_inv = invert;
  pthread_mutex_unlock(&mu);
}

uint32_t engine_sniff_get_accumulator(void) {
  pthread_mutex_lock(&mu);
  uint32_t v = sniff_acc;
  pthread_mutex_unlock(&mu);
  if (out_rev) {
    uint32_t r = 0;
    for (int i = 0; i < 32; i++) r = (r << 1) | ((v >> i) & 1u);
    v = r;
  }
  if (out_inv) v = ~v;
  return v;
}

unsigned long long engine_stat_transfers(void) { return st_transfers; }
unsigned long long engine_stat_sniffed_bytes(void) { return st_sniffed; }
bool engine_stat_sniff_enabled(void) { return sniff_ch >= 0; }

int engine_stat_claimed_now(void) {
  int n = 0;
  pthread_mutex_lock(&mu);
  for (int i = 0; i < ENGINE_CHANNELS; i++) n += chans[i].claimed;
  pthread_mutex_unlock(&mu);
  return n;
}

void engine_stat_reset(void) {
  pthread_mutex_lock(&mu);
  st_transfers = st_sniffed = 0;
  pthread_mutex_unlock(&mu);
}
