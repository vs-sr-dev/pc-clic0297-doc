#!/usr/bin/env python3
"""dircensus.py -- every Director container on the disc, and which way round.

The briefing for this session noticed that `Data/01.dxr` begins `RIFX` and
`Data/Varie.cst` begins `XFIR` -- the same format in the two byte orders, in the
same folder -- and asked how the 132 Director files divide.

The division turns out not to be a division. This walks every container on both
sides of the disc, reports the byte order, the `imap` file-version field and the
chunk census, and totals them by order and by extension. It calls director.py
for the parsing, so it inherits that reader's rule of addressing chunks through
`mmap` rather than scanning for tags.

    python tools/dircensus.py _work/iso _work/hfs
    python tools/dircensus.py _work/iso _work/hfs --chunks
    python tools/dircensus.py _work/iso _work/hfs --tsv notes/director.tsv

THE VERSION FIELD
-----------------
`imap` carries a file-version number. pc-883d-doc calibrated it against two
Macintosh projectors whose own version resources named the runtime that wrote
them: **1223 is Director 6.5 and 1406 is Director 7**. That calibration is
inherited, and it is a citation, not a measurement of this disc -- so the tool
prints the raw number first and the reading second.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import director as D

VERSION_NAMES = {1223: "Director 6.5", 1406: "Director 7"}
EXTS = (".dxr", ".cst", ".dir", ".cxt", ".cct", ".dcr")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--chunks", action="store_true")
    ap.add_argument("--tsv")
    a = ap.parse_args()

    files = []
    for root in a.roots:
        for dp, dn, fn in os.walk(root):
            for n in fn:
                p = os.path.join(dp, n)
                if n.lower().endswith(EXTS):
                    files.append(p)
    files.sort()

    rows = []
    bad = []
    for p in files:
        data = open(p, "rb").read()
        magic = data[0:4]
        if magic not in (b"RIFX", b"XFIR"):
            bad.append((p, magic))
            continue
        try:
            r = D.Reader(data, 0)
        except Exception as e:
            bad.append((p, "%s: %s" % (magic, e)))
            continue
        ents = r.chunks
        tags = {}
        for e in ents:
            t = e["tag"].decode("ascii", "replace")
            c, b = tags.get(t, (0, 0))
            tags[t] = (c + 1, b + e["len"])
        rows.append({"path": p, "magic": magic.decode(), "size": len(data),
                     "version": r.file_version, "codec": r.codec,
                     "entries": len(ents), "tags": tags})

    print("Director containers found : %d" % len(rows))
    if bad:
        print("files with a Director extension that are not containers : %d" % len(bad))
        for p, m in bad:
            print("    %-60s %r" % (p, m))
    print()

    # by byte order
    order = {}
    for r in rows:
        k = r["magic"]
        c, b = order.get(k, (0, 0))
        order[k] = (c + 1, b + r["size"])
    print("%-6s %-28s %7s %14s" % ("magic", "byte order", "files", "bytes"))
    for k in sorted(order):
        name = "big-endian (Motorola)" if k == "RIFX" else "little-endian (Intel)"
        print("%-6s %-28s %7d %14d" % (k, name, order[k][0], order[k][1]))
    print()

    # by extension and byte order
    grid = {}
    for r in rows:
        e = os.path.splitext(r["path"])[1].lower()
        grid[(e, r["magic"])] = grid.get((e, r["magic"]), 0) + 1
    exts = sorted(set(e for e, m in grid))
    print("%-8s %8s %8s" % ("ext", "RIFX", "XFIR"))
    for e in exts:
        print("%-8s %8d %8d" % (e, grid.get((e, "RIFX"), 0), grid.get((e, "XFIR"), 0)))
    print()

    # version field
    vers = {}
    for r in rows:
        vers[r["version"]] = vers.get(r["version"], 0) + 1
    print("%-10s %7s  %s" % ("imap ver", "files", "reading (cited from pc-883d-doc)"))
    for v in sorted(vers):
        print("%-10d %7d  %s" % (v, vers[v], VERSION_NAMES.get(v, "(not calibrated)")))
    print()

    # codec tag
    codecs = {}
    for r in rows:
        c = r["codec"]
        c = c.decode("ascii", "replace") if isinstance(c, bytes) else c
        codecs[c] = codecs.get(c, 0) + 1
    print("codec tag after the outer length : %s" % dict(sorted(codecs.items())))
    print()

    if a.chunks:
        # mmap entry 0 is the outer container itself, whose declared length is
        # the whole file. Counting it as a chunk makes every share come out at
        # half its real value and the total come out at twice the bytes on the
        # disc, so it is excluded here and reported on its own line.
        allt = {}
        outer = [0, 0]
        for r in rows:
            for t, (c, b) in r["tags"].items():
                if t in ("RIFX", "XFIR"):
                    outer[0] += c
                    outer[1] += b
                    continue
                cc, bb = allt.get(t, (0, 0))
                allt[t] = (cc + c, bb + b)
        tot = sum(b for c, b in allt.values())
        print("outer container entries excluded from the census below:"
              " %d entries, %d bytes" % (outer[0], outer[1]))
        print("(mmap entry 0 describes the file itself, not a chunk in it)")
        print()
        print("%-8s %8s %14s %8s" % ("tag", "count", "bytes", "share"))
        for t in sorted(allt, key=lambda x: -allt[x][1]):
            c, b = allt[t]
            print("%-8s %8d %14d %7.2f%%" % (t, c, b, 100.0 * b / tot if tot else 0))
        print("%-8s %8d %14d" % ("total", sum(c for c, b in allt.values()), tot))
        print()

    if a.tsv:
        with open(a.tsv, "w", encoding="utf-8") as f:
            f.write("path\tmagic\tsize\timap_version\tcodec\tchunks\n")
            for r in rows:
                c = r["codec"]
                c = c.decode("ascii", "replace") if isinstance(c, bytes) else c
                f.write("%s\t%s\t%d\t%d\t%s\t%d\n"
                        % (r["path"].replace(os.sep, "/"), r["magic"], r["size"],
                           r["version"], c, r["entries"]))
        print("wrote %s" % a.tsv)


if __name__ == "__main__":
    main()
