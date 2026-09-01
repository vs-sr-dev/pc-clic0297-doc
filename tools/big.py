#!/usr/bin/env python3
"""big.py -- read the table of contents of an EA BIG archive.

The game on this disc is nested two containers deep: the ISO holds
`0compressed.zip`, the zip holds four `.big` archives, and the `.big` archives
hold the game. A BIG archive puts its whole table of contents at the front, so
the contents can be listed by decompressing only the head of the zip member --
no 1.7 GB of extraction, no temporary files.

    python tools/big.py _work/iso/0compressed.zip data.big
    python tools/big.py _work/iso/0compressed.zip data.big --list
    python tools/big.py _work/iso/0compressed.zip --all
    python tools/big.py somefile.big --raw

Format (EA BIG, BIGF variant):
    0   4   magic 'BIGF'  (or 'BIG4' for >4 GB)
    4   4   total archive size, little-endian
    8   4   number of entries, big-endian
   12   4   offset of the first entry's data, big-endian
   16   ..  per entry: 4 offset (BE), 4 size (BE), NUL-terminated name

Anything that does not parse is printed rather than assumed.
"""
import argparse
import collections
import os
import struct
import sys
import zipfile
import zlib


def head_of_member(zpath, member, want):
    """Decompress the first `want` bytes of a zip member without writing it out."""
    with zipfile.ZipFile(zpath) as z:
        with z.open(member) as f:
            out = b""
            while len(out) < want:
                b = f.read(min(1 << 20, want - len(out)))
                if not b:
                    break
                out += b
            return out


def parse_big(head, name, verbose=False):
    if len(head) < 16:
        print("  %s: only %d bytes, cannot be a BIG archive" % (name, len(head)))
        return None
    magic = head[:4]
    if magic not in (b"BIGF", b"BIG4", b"C0FB"):
        print("  %s: magic %r is not BIGF/BIG4" % (name, magic))
        print("    first 32 bytes: %s" % " ".join("%02x" % x for x in head[:32]))
        return None
    total = struct.unpack_from("<I", head, 4)[0]
    n = struct.unpack_from(">I", head, 8)[0]
    first = struct.unpack_from(">I", head, 12)[0]
    entries = []
    p = 16
    for i in range(n):
        if p + 8 > len(head):
            print("  !! table truncated after %d of %d entries "
                  "(need more head bytes)" % (i, n))
            break
        off, size = struct.unpack_from(">II", head, p)
        p += 8
        e = head.find(b"\x00", p)
        if e < 0:
            print("  !! unterminated name at %d after %d entries" % (p, i))
            break
        entries.append((off, size, head[p:e].decode("latin-1")))
        p = e + 1
    return {"magic": magic.decode(), "total": total, "count": n,
            "first": first, "entries": entries, "tablelen": p}


def report(name, big, listing, top):
    print("=== %s ===" % name)
    print("  magic                 : %s" % big["magic"])
    print("  declared archive size : %d bytes" % big["total"])
    print("  entries declared      : %d" % big["count"])
    print("  entries parsed        : %d" % len(big["entries"]))
    print("  first data offset     : %d" % big["first"])
    print("  table ends at         : %d" % big["tablelen"])
    if big["entries"]:
        tot = sum(s for _, s, _ in big["entries"])
        print("  sum of entry sizes    : %d bytes" % tot)
        print("  table + data          : %d  (declared %d, difference %d)"
              % (big["first"] + tot, big["total"], big["total"] - big["first"] - tot))
        lo = min(o for o, _, _ in big["entries"])
        hi = max(o + s for o, s, _ in big["entries"])
        print("  data spans            : %d .. %d" % (lo, hi))
        zero = sum(1 for _, s, _ in big["entries"] if s == 0)
        print("  zero-length entries   : %d" % zero)

        ext = collections.defaultdict(lambda: [0, 0])
        for _, s, nm in big["entries"]:
            e = os.path.splitext(nm)[1].lower() or "(none)"
            ext[e][0] += 1
            ext[e][1] += s
        print("  extensions inside (%d):" % len(ext))
        for e, (c, s) in sorted(ext.items(), key=lambda kv: -kv[1][1])[:top]:
            print("    %-14s %6d  %14d  %6.2f %%" % (e, c, s, 100.0 * s / tot if tot else 0))

        seps = sum(1 for _, _, nm in big["entries"] if chr(92) in nm or "/" in nm)
        print("  names with a path separator: %d" % seps)
        topdir = collections.defaultdict(lambda: [0, 0])
        for _, s, nm in big["entries"]:
            t = nm.replace(chr(92), "/").split("/")[0] if ("/" in nm or chr(92) in nm) else "(root)"
            topdir[t][0] += 1
            topdir[t][1] += s
        print("  top-level names inside (%d):" % len(topdir))
        for t, (c, s) in sorted(topdir.items(), key=lambda kv: -kv[1][1])[:top]:
            print("    %-24s %6d  %14d" % (t[:24], c, s))

        dup = collections.Counter(nm.lower() for _, _, nm in big["entries"])
        d = {k: v for k, v in dup.items() if v > 1}
        print("  duplicate names       : %d" % len(d))
        print("  largest entries:")
        for o, s, nm in sorted(big["entries"], key=lambda e: -e[1])[:10]:
            print("    %12d  @%-12d %s" % (s, o, nm))
    if listing:
        print("  --- every entry ---")
        for o, s, nm in big["entries"]:
            print("    %12d %12d  %s" % (o, s, nm))
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="a .zip containing .big members, or a .big file")
    ap.add_argument("member", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--raw", action="store_true", help="path is a .big file itself")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--head", type=int, default=16 << 20,
                    help="bytes of each member to decompress (default 16 MB)")
    ap.add_argument("--top", type=int, default=20)
    a = ap.parse_args()

    if a.raw:
        with open(a.path, "rb") as f:
            head = f.read(a.head)
        big = parse_big(head, a.path)
        if big:
            report(a.path, big, a.list, a.top)
        return

    with zipfile.ZipFile(a.path) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".big")]
    targets = names if (a.all or not a.member) else [a.member]
    print("archive: %s" % a.path)
    print("BIG members: %s" % ", ".join(names))
    print()
    for m in targets:
        head = head_of_member(a.path, m, a.head)
        big = parse_big(head, m)
        if big:
            report(m, big, a.list, a.top)


if __name__ == "__main__":
    main()
