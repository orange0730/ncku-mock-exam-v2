"""eBNN 模型、測試資料與 Python 參考實作（三個大題共用）。

影像：8x8 黑白，打包成一個 64-bit 整數，像素 (r, c) 在 bit r*8 + c。
      傳給 C 時拆成 img[0] = 低 32 位（第 0..3 列）、img[1] = 高 32 位（第 4..7 列）。

第一層（隱藏層）32 個二值神經元，神經元 j：
      matches_j = popcount(~(x XOR W1[j]))            # 64 位元裡「相同」的位數 = XNOR + popcount
      h_j       = 1 if matches_j >= T1[j] else 0      # BatchNorm + sign 摺疊成一個整數門檻
      隱藏層打包成 32-bit：bit j = h_j

第二層（輸出層）10 個分數：
      score_k = 2 * popcount(~(h XOR W2[k])) - 32     # 二值內積：相同 +1、不同 -1
      prediction = 分數最大的 k；同分取 index 最小者

這個 eBNN 是「手工設計」的：神經元 3d..3d+2 是數字 d 的模板（原位、左移、右移），
所以它真的能辨識加了雜訊的數字。
"""
import random

MASK32 = 0xFFFFFFFF
MASK64 = (1 << 64) - 1
N_HIDDEN = 32
N_OUT = 10

GLYPHS = {
    0: ['..####..', '.#....#.', '.#...##.', '.#..#.#.', '.#.#..#.', '.##...#.', '.#....#.', '..####..'],
    1: ['...##...', '..###...', '...##...', '...##...', '...##...', '...##...', '...##...', '..####..'],
    2: ['..####..', '.#....#.', '......#.', '.....#..', '....#...', '...#....', '..#.....', '.######.'],
    3: ['..####..', '.#....#.', '......#.', '...###..', '......#.', '......#.', '.#....#.', '..####..'],
    4: ['....##..', '...#.#..', '..#..#..', '.#...#..', '.######.', '.....#..', '.....#..', '.....#..'],
    5: ['.######.', '.#......', '.#......', '.#####..', '......#.', '......#.', '.#....#.', '..####..'],
    6: ['...###..', '..#.....', '.#......', '.#####..', '.#....#.', '.#....#.', '.#....#.', '..####..'],
    7: ['.######.', '......#.', '.....#..', '....#...', '...#....', '...#....', '...#....', '...#....'],
    8: ['..####..', '.#....#.', '.#....#.', '..####..', '.#....#.', '.#....#.', '.#....#.', '..####..'],
    9: ['..####..', '.#....#.', '.#....#.', '.#....#.', '..#####.', '......#.', '.....#..', '..###...'],
}


def glyph_bits(rows, shift=0):
    """把字元圖轉成 64-bit；shift = -1 / +1 代表整張圖往左 / 右移一欄。"""
    v = 0
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            cc = c + shift
            if ch == '#' and 0 <= cc < 8:
                v |= 1 << (r * 8 + cc)
    return v


def build_model():
    w1, t1 = [], []
    for d in range(10):
        for shift in (0, -1, 1):
            w1.append(glyph_bits(GLYPHS[d], shift))
            t1.append(60)
    rng = random.Random(116)
    w1.append(MASK64)          # 神經元 30：全 1 權重 = 「墨水很多」偵測器
    t1.append(44)
    w1.append(rng.getrandbits(64))
    t1.append(36)              # 神經元 31：隨機權重
    w2 = []
    for k in range(10):
        w2.append(0b111 << (3 * k))
    return w1, t1, w2


W1, T1, W2 = build_model()


def popcount(v):
    return bin(v).count('1')


def hidden(img64):
    h = 0
    for j in range(N_HIDDEN):
        matches = popcount(~(img64 ^ W1[j]) & MASK64)
        if matches >= T1[j]:
            h |= 1 << j
    return h


_hidden_impl = hidden   # 給模擬板子用的私有別名（評分時協調者不能自己算第一層）


def scores_from_hidden(h):
    return [2 * popcount(~(h ^ W2[k]) & MASK32) - 32 for k in range(N_OUT)]


def argmax(scores):
    best = 0
    for k in range(1, len(scores)):
        if scores[k] > scores[best]:
            best = k
    return best


def infer(img64):
    s = scores_from_hidden(hidden(img64))
    return argmax(s), s


def hidden_range(img64, first, count):
    """第一層裡 first .. first+count-1 這幾個神經元，放在原本的位元位置上。"""
    mask = ((1 << count) - 1) << first if count else 0
    return _hidden_impl(img64) & mask & MASK32


_hidden_range_impl = hidden_range


def noisy_digit(rng, digit, flips):
    shift = rng.choice((0, 0, -1, 1))
    v = glyph_bits(GLYPHS[digit], shift)
    for _ in range(flips):
        v ^= 1 << rng.randrange(64)
    return v


def dataset(n=200, seed=2025, max_flips=4):
    rng = random.Random(seed)
    data = []
    for i in range(n):
        d = i % 10
        data.append((noisy_digit(rng, d, rng.randint(0, max_flips)), d))
    return data


def split_words(img64):
    return img64 & MASK32, (img64 >> 32) & MASK32


def write_model_h(path):
    lines = ['/* 由 common/model.py 產生的 eBNN 權重（不要手改）。 */',
             '#ifndef MODEL_H', '#define MODEL_H', '', '#include <stdint.h>', '',
             '#define N_HIDDEN 32', '#define N_OUT 10', '',
             '/* W1[j][0] = 權重低 32 位（像素 0..31），W1[j][1] = 高 32 位（像素 32..63） */',
             'static const uint32_t W1[N_HIDDEN][2] = {']
    for j, w in enumerate(W1):
        lo, hi = split_words(w)
        lines.append(f'    {{0x{lo:08X}u, 0x{hi:08X}u}},  /* neuron {j:2} */')
    lines.append('};')
    lines.append('')
    lines.append('/* 第一層門檻：相同的位數 >= T1[j] 時輸出 1 */')
    lines.append('static const int T1[N_HIDDEN] = {' + ', '.join(map(str, T1)) + '};')
    lines.append('')
    lines.append('/* 第二層權重：每個輸出一個 32-bit 字 */')
    lines.append('static const uint32_t W2[N_OUT] = {' + ', '.join(f'0x{w:08X}u' for w in W2) + '};')
    lines += ['', '#endif', '']
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    import sys
    data = dataset(1000)
    correct = sum(infer(img)[0] == d for img, d in data)
    print(f'accuracy on 1000 noisy digits: {correct / 10:.1f}%')
    clean = sum(infer(glyph_bits(GLYPHS[d]))[0] == d for d in range(10))
    print(f'clean glyphs: {clean}/10')
    if len(sys.argv) > 1:
        write_model_h(sys.argv[1])
        print('wrote', sys.argv[1])
