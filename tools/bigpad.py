#!/usr/bin/env python3
"""bigpad.py -- why a BIGF archive declares more than the sum of its entries.

big.py reports, for all six archives on this disc, a declared size larger than
its own table plus the sum of its entry sizes -- 990,806 bytes on movies.big,
6,282,163 on data3.big, and four more. That was open question 5.

The answer is alignment, and it is measurable: this walks the entry table,
sorts by offset, and prints the gap between the end of each entry and the start
of the next, plus the largest power of two that divides every entry offset.

Two header notes that cost a wrong number the first time:

  * the archive size at +4 is **little-endian**; the entry count at +8 and the
    first-data offset at +12 are **big-endian**. Reading the size big-endian
    gives 1,814,474,303 for a 1,068,377,708-byte archive, which is nonsense,
    and nonsense is the only reason the mistake was caught;
  * an entry is 4 bytes of big-endian offset, 4 of big-endian size, then a
    NUL-terminated name.

It decompresses only the head of one zip member -- one megabyte by default,
which holds a 348-entry table comfortably -- and never the archive.

    python tools/bigpad.py E:/0compressed.zip data.big
    python tools/bigpad.py E:/0compressed.zip movies.big --head 2097152
    python tools/bigpad.py E:/0compressed.zip data.big --dump fingerpr.int
"""
import argparse
import collections
import hashlib
import struct
import time
import zipfile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archive")
    ap.add_argument("member")
    ap.add_argument("--head", type=int, default=1 << 20)
    ap.add_argument("--dump", default=None,
                    help="hex-dump one entry by name, if it is inside --head")
    a = ap.parse_args()

    z = zipfile.ZipFile(a.archive)
    info = [i for i in z.infolist() if i.filename == a.member][0]
    t = time.time()
    with z.open(info) as fh:
        head = fh.read(a.head)
    print("zip member          : %s" % a.member)
    print("  compressed        : %d" % info.compress_size)
    print("  stored            : %d" % info.file_size)
    print("  decompressed here : %d bytes in %.1f s" % (len(head), time.time() - t))
    print()

    magic = head[:4]
    size_le = struct.unpack_from("<I", head, 4)[0]
    size_be = struct.unpack_from(">I", head, 4)[0]
    count = struct.unpack_from(">I", head, 8)[0]
    first = struct.unpack_from(">I", head, 12)[0]
    print("magic               : %r" % magic)
    print("size at +4, LE      : %d   %s" % (size_le,
          "== the member's own size" if size_le == info.file_size else ""))
    print("size at +4, BE      : %d   (the wrong reading, kept to show it)"
          % size_be)
    print("entry count at +8   : %d  (big-endian)" % count)
    print("first offset at +12 : %d  (big-endian)" % first)
    print()

    off = 16
    ents = []
    for _ in range(count):
        o, sz = struct.unpack_from(">II", head, off)
        off += 8
        end = head.index(b"\0", off)
        ents.append((o, sz, head[off:end].decode("latin1")))
        off = end + 1
    print("entry table         : %d entries parsed, ends at byte %d"
          % (len(ents), off))
    print("  +12 field minus that: %d" % (first - off))
    print("  first entry starts at %d, so the header region is %d bytes"
          % (min(e[0] for e in ents), min(e[0] for e in ents)))
    print()

    print("alignment of the %d entry offsets:" % len(ents))
    best = 0
    for shift in range(1, 22):
        k = 1 << shift
        n = sum(1 for o, sz, nm in ents if o % k == 0)
        if n == len(ents):
            best = k
        print("   divisible by %8d : %d of %d" % (k, n, len(ents)))
    print()
    print("  every entry offset is a multiple of %d bytes." % best)
    print()

    byoff = sorted(ents)
    gaps = [byoff[i + 1][0] - (byoff[i][0] + byoff[i][1])
            for i in range(len(byoff) - 1)]
    neg = [g for g in gaps if g < 0]
    print("gaps between the end of one entry and the start of the next:")
    print("  pairs          : %d" % len(gaps))
    print("  negative       : %d  (entries must not overlap)" % len(neg))
    print("  min / max      : %d / %d" % (min(gaps), max(gaps)))
    print("  total padding  : %d bytes" % sum(gaps))
    over = [g for g in gaps if g >= best]
    print("  gaps >= %d : %d" % (best, len(over)))
    print()
    print("  every gap is exactly what alignment demands: for each pair,")
    print("  (end of entry) rounded up to %d equals (start of the next)."
          % best)
    bad = 0
    for i in range(len(byoff) - 1):
        end = byoff[i][0] + byoff[i][1]
        want = ((end + best - 1) // best) * best
        if want != byoff[i + 1][0]:
            bad += 1
            if bad <= 5:
                print("    EXCEPTION after %s: ends %d, rounds to %d, next is %d"
                      % (byoff[i][2], end, want, byoff[i + 1][0]))
    print("  pairs where that does not hold: %d of %d" % (bad, len(gaps)))
    print()

    last = byoff[-1]
    print("last entry          : %s, @%d + %d = %d"
          % (last[2], last[0], last[1], last[0] + last[1]))
    print("declared size (LE)  : %d" % size_le)
    print("difference          : %d" % (size_le - (last[0] + last[1])))
    print()
    print("sum of entry sizes  : %d" % sum(e[1] for e in ents))
    print("+ table (%d) + padding (%d) + header gap (%d)"
          % (off, sum(gaps), min(e[0] for e in ents) - off))
    print("= %d, against a declared %d, difference %d"
          % (sum(e[1] for e in ents) + off + sum(gaps)
             + (min(e[0] for e in ents) - off), size_le,
             size_le - (sum(e[1] for e in ents) + sum(gaps)
                        + min(e[0] for e in ents))))

    if a.dump:
        hit = [e for e in ents if e[2].lower().endswith(a.dump.lower())]
        print()
        if not hit:
            print("no entry named %r" % a.dump)
            return
        o, sz, nm = hit[0]
        print("entry %s : @%d, %d bytes" % (nm, o, sz))
        if o + sz > len(head):
            print("  (outside the %d bytes decompressed; raise --head)"
                  % len(head))
            return
        blob = head[o:o + sz]
        print("  sha1 %s" % hashlib.sha1(blob).hexdigest())
        for i in range(0, len(blob), 16):
            row = blob[i:i + 16]
            print("  %04x  %-47s  %s"
                  % (i, " ".join("%02x" % b for b in row),
                     "".join(chr(b) if 32 <= b < 127 else "." for b in row)))


if __name__ == "__main__":
    main()
