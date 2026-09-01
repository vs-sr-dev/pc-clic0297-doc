#!/usr/bin/env python3
"""vdfields.py -- read the sector-16 payload as numbers instead of as noise.

The short non-zero runs in the payload look like small integers with zero high
bytes. This prints the whole span 1139..1535 as bytes, as 16-bit LE and as
32-bit LE at every alignment, and flags any value that lands in the range of a
plausible sector address on this disc (0 .. 292,323).

    python tools/vdfields.py E
"""
import sys

BS = chr(92)
LEADOUT = 292323
VOLSIZE = 292173


def rd(letter, lba, n=1):
    with open(BS + BS + "." + BS + letter.upper() + ":", "rb") as f:
        f.seek(lba * 2048)
        return f.read(2048 * n)


def main():
    letter = sys.argv[1] if len(sys.argv) > 1 else "E"
    s = rd(letter, 16)
    lo, hi = 1139, 1535

    print("sector 16, bytes %d..%d, hex dump" % (lo, hi))
    print()
    for a in range(lo & ~0xF, hi + 1, 16):
        chunk = s[a:a + 16]
        txt = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        print("  %4d  %-47s  %s" % (a, chunk.hex(" "), txt))
    print()

    print("32-bit little-endian dwords, alignment sweep.")
    print("Flagged if 0 < v <= %d (a sector address could look like this)."
          % LEADOUT)
    print()
    for align in range(4):
        start = lo + align
        vals = []
        a = start
        while a + 4 <= hi + 1:
            v = int.from_bytes(s[a:a + 4], "little")
            vals.append((a, v))
            a += 4
        plaus = [(o, v) for o, v in vals if 0 < v <= LEADOUT]
        print("  alignment %d (offsets %d, %d, ...): %d dwords, %d plausible"
              % (align, start, start + 4, len(vals), len(plaus)))
        for o, v in plaus:
            note = ""
            if v > 9000 and v < 11000:
                note = "   <- inside the probe bracket for the region end"
            if v > VOLSIZE:
                note = "   <- beyond the declared volume"
            print("      +%-5d %10d  (0x%08x)%s" % (o, v, v, note))
    print()

    print("16-bit little-endian words at the short runs, for comparison:")
    for a in (1275, 1279, 1284, 1286, 1288, 1291, 1303, 1307, 1311, 1331):
        w = int.from_bytes(s[a:a + 2], "little")
        d = int.from_bytes(s[a:a + 4], "little")
        print("  +%-5d word %6d (0x%04x)   dword %12d (0x%08x)"
              % (a, w, w, d, d))


if __name__ == "__main__":
    main()
