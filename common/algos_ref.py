"""大題三的 Python 參考實作：SHA-0、CRC-32、DMA sniffer 的 CRC 模型。"""
import struct

MASK = 0xFFFFFFFF


def rotl(x, k):
    return ((x << k) | (x >> (32 - k))) & MASK


def _sha(msg, sha1):
    h = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0]
    ml = len(msg) * 8
    msg = bytes(msg) + b'\x80'
    msg += b'\x00' * ((56 - len(msg) % 64) % 64)
    msg += struct.pack('>Q', ml)
    for off in range(0, len(msg), 64):
        w = list(struct.unpack('>16I', msg[off:off + 64]))
        for t in range(16, 80):
            x = w[t - 3] ^ w[t - 8] ^ w[t - 14] ^ w[t - 16]
            w.append(rotl(x, 1) if sha1 else x)        # SHA-0 與 SHA-1 唯一的差別
        a, b, c, d, e = h
        for t in range(80):
            if t < 20:
                f, k = (b & c) | (~b & d), 0x5A827999
            elif t < 40:
                f, k = b ^ c ^ d, 0x6ED9EBA1
            elif t < 60:
                f, k = (b & c) | (b & d) | (c & d), 0x8F1BBCDC
            else:
                f, k = b ^ c ^ d, 0xCA62C1D6
            tmp = (rotl(a, 5) + (f & MASK) + e + k + w[t]) & MASK
            a, b, c, d, e = tmp, a, rotl(b, 30), c, d
        h = [(x + y) & MASK for x, y in zip(h, (a, b, c, d, e))]
    return b''.join(struct.pack('>I', x) for x in h)


def sha0(msg):
    return _sha(msg, sha1=False)


def sha1(msg):
    return _sha(msg, sha1=True)


def bitrev8(b):
    return int(f'{b:08b}'[::-1], 2)


def bitrev32(x):
    return int(f'{x & MASK:032b}'[::-1], 2)


def crc32_msb_update(acc, byte):
    """非反射（MSB-first）CRC-32，多項式 0x04C11DB7：sniffer 的 CRC32 模式。"""
    acc ^= byte << 24
    for _ in range(8):
        acc = ((acc << 1) ^ 0x04C11DB7) & MASK if acc & 0x80000000 else (acc << 1) & MASK
    return acc


def sniff_crc(data, seed, reverse_data, out_reverse, out_invert):
    acc = seed & MASK
    for byte in data:
        acc = crc32_msb_update(acc, bitrev8(byte) if reverse_data else byte)
    if out_reverse:
        acc = bitrev32(acc)
    if out_invert:
        acc ^= MASK
    return acc


if __name__ == '__main__':
    import hashlib
    import os
    import zlib
    assert sha0(b'abc').hex() == '0164b8a914cd2a5e74c4f7ff082c4d97f1edf880', sha0(b'abc').hex()
    for n in (0, 1, 55, 56, 63, 64, 65, 119, 120, 1000):
        m = os.urandom(n)
        assert sha1(m) == hashlib.sha1(m).digest(), n
        assert sniff_crc(m, MASK, True, True, True) == zlib.crc32(m), n
    print('SHA-0("abc") =', sha0(b'abc').hex())
    print('CRC-32("123456789") =', hex(zlib.crc32(b'123456789')),
          '| sniffer 模型 =', hex(sniff_crc(b'123456789', MASK, True, True, True)))
    print('all reference checks passed')
