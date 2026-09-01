#!/usr/bin/env python3
"""gearcount.py -- every place the mastering house signs this disc.

The ISO 9660 publisher, application and copyright fields are empty, so the
publisher of the game is nowhere in the volume metadata. The company that cut
the master is in it repeatedly, across two standards and two copies of the UDF
descriptor sequence. This counts the occurrences instead of estimating them:
it scans the volume-structure sectors for the ASCII and UTF-16 byte patterns
of the word, and prints the sector and offset of each.

    python tools/gearcount.py E
"""
import sys

BS = chr(92)
SECTOR = 2048
drive = (sys.argv[1] if len(sys.argv) > 1 else "E").rstrip(":")
f = open(BS * 2 + "." + BS + drive + ":", "rb", buffering=0)

hits = []
for lba in list(range(0, 70)) + [256, 257, 258, 259, 260, 261, 262, 264]:
    f.seek(lba * SECTOR)
    d = f.read(SECTOR)
    if len(d) < SECTOR:
        continue
    for pat, kind in ((b"GEAR", "ascii"), ("GEAR".encode("utf-16-be"), "utf-16be"),
                      ("GEAR".encode("utf-16-le"), "utf-16le")):
        p = d.find(pat)
        while p >= 0:
            ctx = d[p:p + 40]
            txt = "".join(chr(x) if 32 <= x < 127 else "." for x in ctx)
            hits.append((lba, p, kind, txt))
            p = d.find(pat, p + 1)

print("occurrences of 'GEAR' in the volume structures of %s:" % drive)
print()
print("%6s %6s %-9s %s" % ("sector", "offset", "encoding", "context"))
for lba, off, kind, txt in hits:
    print("%6d %6d %-9s %s" % (lba, off, kind, txt))
print()
print("total: %d" % len(hits))
print("sectors involved: %s" % sorted({h[0] for h in hits}))
