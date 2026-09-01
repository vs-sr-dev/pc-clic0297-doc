#!/usr/bin/env python3
"""abslack.py -- what is in the bytes an ISO extent does not cover and HFS does.

NOT to be confused with the inherited `slack.py`, which measures the tail of the
last 2,048-byte SECTOR of each file. This measures whole sectors between the end
of a file's ISO extent and the end of its HFS ALLOCATION BLOCK, which only
exists on a hybrid. The two are complementary and this session ran both.


`twocat.py` shows that 6,818 sectors of this volume are owned by the HFS
catalogue and by nothing on the ISO side. The structural explanation is that
an HFS allocation block here is 10,240 bytes and an ISO extent is a whole
number of 2,048-byte sectors, so a file of length L occupies

    ceil(L / 2048)  sectors on the ISO side
    ceil(L / 10240) * 5  sectors on the HFS side

and the difference belongs to HFS alone. This tool proves that arithmetic file
by file rather than asserting it, and then looks at what the padding actually
contains -- zero, the tail of the file it follows repeated, or something else.

    python tools/abslack.py IMAGE                 the arithmetic, summed
    python tools/abslack.py IMAGE --content       classify every slack sector
    python tools/abslack.py IMAGE --sample N      hexdump N slack regions
"""
import argparse
import collections
import hashlib
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import iso9660
import hfs

SECTOR = 2048


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--content", action="store_true")
    ap.add_argument("--sample", type=int, default=0)
    a = ap.parse_args()

    fh, mm = iso9660.open_image(a.image)
    vds = iso9660.read_vds(mm)
    entries = iso9660.tree_of(mm, vds, False)

    src = hfs.Source(image=a.image)
    part, pm = hfs.find_hfs(src)
    vol = hfs.Volume(src, part)
    ablk = vol.mdb["drAlBlkSiz"]
    per_ab = ablk // SECTOR

    iso_sect = hfs_sect = 0
    slack_regions = []
    nfiles = 0
    for e in entries:
        if e["isdir"]:
            continue
        nfiles += 1
        L = e["size"]
        i = (L + SECTOR - 1) // SECTOR
        h = ((L + ablk - 1) // ablk) * per_ab
        iso_sect += i
        hfs_sect += h
        if h > i:
            slack_regions.append((e["extent"] + i, h - i, e["path"] + e["name"], L))

    print("file records            %d" % nfiles)
    print("ISO extent sectors      %d" % iso_sect)
    print("HFS allocation sectors  %d" % hfs_sect)
    print("difference              %d sectors = %d bytes"
          % (hfs_sect - iso_sect, (hfs_sect - iso_sect) * SECTOR))
    print("files with slack        %d of %d = %.4f %%"
          % (len(slack_regions), nfiles, 100.0 * len(slack_regions) / nfiles))
    hist = collections.Counter(n for _, n, _, _ in slack_regions)
    print()
    print("slack length, in sectors:")
    for k in sorted(hist):
        print("  %d sector(s)  x %5d  = %6d sectors"
              % (k, hist[k], k * hist[k]))

    if a.content:
        cls = collections.Counter()
        repeat_hits = 0
        checked = 0
        for lba, n, path, L in slack_regions:
            blob = mm[lba * SECTOR:(lba + n) * SECTOR]
            if blob.count(0) == len(blob):
                cls["all zero"] += n
                continue
            cls["not zero"] += n
            checked += 1
            # is it a repeat of the tail of the file that owns it?
            fstart = lba - ((L + SECTOR - 1) // SECTOR)
            tail = mm[fstart * SECTOR:lba * SECTOR]
            if len(tail) >= len(blob) and tail[-len(blob):] == blob:
                repeat_hits += 1
        print()
        print("slack sectors by content:")
        for k, v in sorted(cls.items(), key=lambda kv: -kv[1]):
            print("  %-10s %7d sectors = %d bytes  %.4f %% of slack"
                  % (k, v, v * SECTOR,
                     100.0 * v / max(1, sum(cls.values()))))
        print()
        print("non-zero slack regions that repeat their own file's tail: %d of %d"
              % (repeat_hits, checked))

    if a.sample:
        print()
        print("sample of %d slack regions:" % a.sample)
        step = max(1, len(slack_regions) // a.sample)
        for lba, n, path, L in slack_regions[::step][:a.sample]:
            blob = mm[lba * SECTOR:(lba + n) * SECTOR]
            print()
            print("  after %s (%d bytes), slack LBA %d +%d, sha1 %s"
                  % (path, L, lba, n, hashlib.sha1(blob).hexdigest()[:16]))
            print("    zero bytes %d of %d (%.2f %%)"
                  % (blob.count(0), len(blob),
                     100.0 * blob.count(0) / len(blob)))
            print("    first 48 : %s"
                  % " ".join("%02X" % c for c in blob[:48]))


if __name__ == "__main__":
    main()
