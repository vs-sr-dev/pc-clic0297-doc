#!/usr/bin/env python3
"""assoc.py -- the ISO 9660 records Windows does not show you, and why.

Walking the primary descriptor of CLIC 11 yields 875 file records. Walking the
mounted volume from Windows yields 857. The difference is not a bug in either
walker: ECMA-119 9.1.6 defines a File Flags byte in every directory record, and
bit 2 means **Associated File** -- "the record describes a file associated with
the file described by the next record with the same name". Toast uses it for
the Macintosh resource fork, so that a hybrid disc can carry both forks in one
ISO namespace and a PC filesystem driver can hide the half it cannot use.

This tool reads the flag rather than assuming it. For every directory record in
a namespace it prints the flags byte, decoded, and it groups the records by
name so that a pair (data fork, resource fork) is visible as a pair.

    python tools/assoc.py _work/clic11.img
    python tools/assoc.py _work/clic11.img --joliet
    python tools/assoc.py _work/clic11.img --all

File Flags, ECMA-119 9.1.6, bit numbering from 0:
    0  Existence      hidden
    1  Directory
    2  Associated File
    3  Record         the record format is specified in the XA/EA
    4  Protection     permissions are specified in the EA
    5,6 reserved
    7  Multi-Extent   this is not the final record for the file
"""
import argparse
import struct
import sys
from collections import Counter, defaultdict

SECTOR = 2048
FLAGBITS = ["hidden", "directory", "ASSOCIATED", "record",
            "protection", "res5", "res6", "multi-extent"]


class Img:
    def __init__(self, path):
        self.f = open(path, "rb")

    def sector(self, lba):
        self.f.seek(lba * SECTOR)
        d = self.f.read(SECTOR)
        return d if len(d) == SECTOR else None

    def read(self, lba, n):
        self.f.seek(lba * SECTOR)
        return self.f.read(n * SECTOR)


def decode_flags(v):
    return "+".join(FLAGBITS[i] for i in range(8) if v & (1 << i)) or "-"


def walk(img, root_lba, root_len, joliet):
    out = []
    todo = [(root_lba, root_len, "")]
    seen = set()
    while todo:
        lba, ln, prefix = todo.pop(0)
        if (lba, ln) in seen:
            continue
        seen.add((lba, ln))
        nsec = (ln + SECTOR - 1) // SECTOR
        data = img.read(lba, nsec)
        off = 0
        while off < ln:
            rl = data[off]
            if rl == 0:
                off = (off // SECTOR + 1) * SECTOR
                continue
            rec = data[off:off + rl]
            ext = struct.unpack("<I", rec[2:6])[0]
            dlen = struct.unpack("<I", rec[10:14])[0]
            flags = rec[25]
            nlen = rec[32]
            raw = rec[33:33 + nlen]
            if nlen == 1 and raw in (b"\x00", b"\x01"):
                name = "." if raw == b"\x00" else ".."
            elif joliet:
                name = raw.decode("utf-16-be", "replace")
            else:
                name = raw.decode("latin-1")
            dt = rec[18:25]
            when = None
            if dt[0]:
                try:
                    when = "%04d-%02d-%02d %02d:%02d:%02d tz%+d" % (
                        1900 + dt[0], dt[1], dt[2], dt[3], dt[4], dt[5],
                        dt[6] - 256 if dt[6] > 127 else dt[6])
                except Exception:
                    when = None
            if name not in (".", ".."):
                path = prefix + "/" + name if prefix else name
                if flags & 2:
                    todo.append((ext, dlen, path))
                out.append((path, ext, dlen, flags, when))
            off += rl
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--joliet", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()

    img = Img(a.image)
    want = 2 if a.joliet else 1
    vd = None
    for n in range(16, 32):
        s = img.sector(n)
        if s is None or s[1:6] != b"CD001":
            continue
        if s[0] == want:
            vd = s
            break
        if s[0] == 255:
            break
    if vd is None:
        raise SystemExit("no descriptor of type %d" % want)
    root = vd[156:190]
    root_lba = struct.unpack("<I", root[2:6])[0]
    root_len = struct.unpack("<I", root[10:14])[0]
    print("namespace     : %s" % ("Joliet" if a.joliet else "ISO 9660 primary"))
    print("root extent   : LBA %d, %d bytes" % (root_lba, root_len))

    recs = walk(img, root_lba, root_len, a.joliet)
    files = [r for r in recs if not (r[3] & 2)]
    dirs = [r for r in recs if r[3] & 2]
    assoc = [r for r in files if r[3] & 4]
    plain = [r for r in files if not (r[3] & 4)]
    print("records       : %d  (%d files, %d directories)"
          % (len(recs), len(files), len(dirs)))
    print()
    print("flags byte histogram over file records:")
    fc = Counter(r[3] for r in files)
    for v, n in sorted(fc.items()):
        print("  0x%02x  %-40s %6d" % (v, decode_flags(v), n))
    print()
    print("file records WITHOUT the Associated bit : %d   %d bytes"
          % (len(plain), sum(r[2] for r in plain)))
    print("file records WITH    the Associated bit : %d   %d bytes"
          % (len(assoc), sum(r[2] for r in assoc)))
    print("sum                                     : %d   %d bytes"
          % (len(files), sum(r[2] for r in files)))
    print()

    if assoc:
        print("every associated record, with the plain record of the same name:")
        byname = defaultdict(list)
        for r in files:
            byname[r[0]].append(r)
        print("  %-40s %10s %10s %10s %10s"
              % ("path", "data LBA", "data len", "rsrc LBA", "rsrc len"))
        for r in sorted(assoc):
            pair = byname[r[0]]
            d = [x for x in pair if not (x[3] & 4)]
            dl = d[0] if d else None
            print("  %-40s %10s %10s %10d %10d"
                  % (r[0][-40:], dl[1] if dl else "-", dl[2] if dl else "-",
                     r[1], r[2]))
        print()
        orphan = [r for r in assoc if not [x for x in byname[r[0]]
                                           if not (x[3] & 4)]]
        print("associated records with no plain record of the same name : %d"
              % len(orphan))
        print()
        print("in every pair, does the associated record come FIRST in the "
              "directory?")
        order = Counter()
        seenpath = []
        for r in recs:
            if not (r[3] & 2):
                seenpath.append(r)
        for i, r in enumerate(seenpath):
            if r[3] & 4:
                nxt = seenpath[i + 1] if i + 1 < len(seenpath) else None
                order["associated then plain" if nxt and nxt[0] == r[0]
                      else "not immediately followed by its pair"] += 1
        for k, v in order.items():
            print("  %-44s %d" % (k, v))

    if a.all:
        print()
        print("%-52s %9s %11s %-28s %s"
              % ("path", "LBA", "bytes", "flags", "recorded"))
        for r in sorted(recs):
            print("%-52s %9d %11d %-28s %s"
                  % (r[0][:52], r[1], r[2], decode_flags(r[3]), r[4]))


if __name__ == "__main__":
    main()
