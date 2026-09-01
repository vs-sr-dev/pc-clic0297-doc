#!/usr/bin/env python3
"""signcount.py -- how many times does the volume's metadata sign itself?

gearcount.py answers this for one word on one disc: the word `GEAR` is written
into its source, and the sector list it scans is that disc's. Run here it
prints zero, which is true and useless, because the question is not "how much
GEAR" but "how much of whoever made this".

So: the token is an argument, the sector ranges are arguments, and both are
echoed before the count. Three encodings are tried, as gearcount.py does,
because UDF writes some identifiers as bytes and some as UCS-2.

    python tools/signcount.py E --token "*EZB UltraISO" --range 0-70 256-1560 1826655
    python tools/signcount.py E --token GEAR --range 0-70
"""
import argparse

BS = chr(92)
SECTOR = 2048


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("--token", required=True)
    ap.add_argument("--range", dest="ranges", nargs="+", required=True,
                    help="LBA ranges like 0-70 (end exclusive) or a single LBA")
    ap.add_argument("--quiet", action="store_true",
                    help="counts only, no per-hit lines")
    a = ap.parse_args()

    lbas = []
    for spec in a.ranges:
        if "-" in spec:
            lo, hi = spec.split("-")
            lbas.extend(range(int(lo), int(hi)))
        else:
            lbas.append(int(spec))

    print("drive        : %s" % a.drive.upper())
    print("token        : %r" % a.token)
    print("sectors read : %d  (%s)" % (len(lbas), " ".join(a.ranges)))
    print()

    f = open(BS * 2 + "." + BS + a.drive.rstrip(":").upper() + ":", "rb",
             buffering=0)
    pats = ((a.token.encode("latin1"), "ascii"),
            (a.token.encode("utf-16-be"), "utf-16be"),
            (a.token.encode("utf-16-le"), "utf-16le"))
    hits = []
    for lba in lbas:
        f.seek(lba * SECTOR)
        d = f.read(SECTOR)
        if len(d) < SECTOR:
            continue
        for pat, kind in pats:
            p = d.find(pat)
            while p >= 0:
                ctx = d[max(0, p - 8):p + 40]
                txt = "".join(chr(x) if 32 <= x < 127 else "."
                              for x in ctx)
                hits.append((lba, p, kind, txt))
                p = d.find(pat, p + 1)

    if not a.quiet:
        print("%8s %6s %-9s %s" % ("sector", "offset", "encoding", "context"))
        for lba, off, kind, txt in hits[:80]:
            print("%8d %6d %-9s %s" % (lba, off, kind, txt))
        if len(hits) > 80:
            print("   ... and %d more" % (len(hits) - 80))
        print()

    print("total occurrences : %d" % len(hits))
    print("distinct sectors  : %d" % len({h[0] for h in hits}))
    by_kind = {}
    for _l, _o, k, _t in hits:
        by_kind[k] = by_kind.get(k, 0) + 1
    print("by encoding       : %s" % (by_kind or "{}"))
    if hits:
        s = sorted({h[0] for h in hits})
        print("sector range      : %d .. %d" % (s[0], s[-1]))


if __name__ == "__main__":
    main()
