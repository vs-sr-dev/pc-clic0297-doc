#!/usr/bin/env python3
"""sectormap.py -- who owns every one of this disc's 322,926 sectors.

Two filesystems describe the same medium and neither of them describes all of
it. The ISO 9660 side accounts for 310,112 sectors and calls the remaining
12,814 "unallocated"; the HFS side accounts for its own partition and knows
nothing about the first half of the disc. Neither statement is wrong and
neither is the answer.

This builds one array of 322,926 entries and lets every claimant write its name
into it, in a fixed order, refusing to overwrite an entry that is already
claimed. What is left at the end is genuinely unclaimed, and the count of
double-claims is printed rather than hidden, because on a hybrid disc a sector
claimed twice is the normal case and a sector claimed twice *by two different
files* is a bug in the mastering.

Claimants, in the order they are allowed to write:

  1  ISO system area, descriptors, path tables, directory extents
  2  ISO file extents, including the Associated-File records (resource forks)
  3  Apple driver descriptor and partition map
  4  HFS volume structures: MDB, bitmap, catalogue, extents overflow
  5  HFS forks, by allocation-block extent out of the catalogue

    python tools/sectormap.py
    python tools/sectormap.py --runs
    python tools/sectormap.py --unclaimed
"""
import argparse
import os
import struct
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assoc

SECTOR = 2048


def sectors_for(nbytes):
    return (nbytes + SECTOR - 1) // SECTOR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="_work/clic11.img")
    ap.add_argument("--hfs", default="notes/hfs-files.tsv")
    ap.add_argument("--runs", action="store_true")
    ap.add_argument("--unclaimed", action="store_true")
    a = ap.parse_args()

    img = assoc.Img(a.image)
    pvd = img.sector(16)
    total = struct.unpack("<I", pvd[80:84])[0]
    own = [None] * total          # first claimant, in the order below
    also = [None] * total         # every other claimant, as a set
    detail = [None] * total       # the name of the ISO file or HFS fork

    def claim(lba, n, who, name=None):
        for i in range(lba, min(lba + n, total)):
            if own[i] is None:
                own[i] = who
                detail[i] = name
            elif own[i] != who:
                if also[i] is None:
                    also[i] = set()
                also[i].add(who)

    # 1 -- ISO metadata
    claim(0, 16, "ISO system area")
    n = 16
    while True:
        s = img.sector(n)
        if s is None or s[1:6] != b"CD001":
            break
        claim(n, 1, "ISO volume descriptor")
        if s[0] == 255:
            break
        n += 1
    for want, label in ((1, "ISO"), (2, "Joliet")):
        vd = None
        for k in range(16, 32):
            s = img.sector(k)
            if s is None or s[1:6] != b"CD001":
                continue
            if s[0] == want:
                vd = s
                break
            if s[0] == 255:
                break
        if vd is None:
            continue
        ptlen = struct.unpack("<I", vd[132:136], )[0]
        for off in (140, 144):
            lba = struct.unpack("<I", vd[off:off + 4])[0]
            if lba:
                claim(lba, sectors_for(ptlen), "%s path table" % label)
        for off in (148, 152):
            lba = struct.unpack(">I", vd[off:off + 4])[0]
            if lba:
                claim(lba, sectors_for(ptlen), "%s path table" % label)
        root = vd[156:190]
        root_lba = struct.unpack("<I", root[2:6])[0]
        root_len = struct.unpack("<I", root[10:14])[0]
        # the root's own extent: assoc.walk yields a directory's children, not
        # the directory itself, so the root would otherwise stay unclaimed and
        # show up as a one-sector hole in each namespace.
        claim(root_lba, sectors_for(root_len), "%s directory extent" % label)
        recs = assoc.walk(img, root_lba, root_len, want == 2)
        for path, lba, ln, flags, when in recs:
            if flags & 2:
                claim(lba, sectors_for(ln), "%s directory extent" % label)
        # 2 -- files, primary namespace only (Joliet points at the same bytes)
        if want == 1:
            for path, lba, ln, flags, when in recs:
                if flags & 2 or ln == 0:
                    continue
                claim(lba, sectors_for(ln),
                      "ISO resource fork (associated)" if flags & 4
                      else "ISO file")

    # 3 -- Apple partition map
    b0 = img.sector(0)
    if b0[:2] == b"ER":
        bsz = struct.unpack(">H", b0[2:4])[0]
        claim(0, 1, "ISO system area")
        nblocks = 1
        b1 = b0[bsz:bsz * 2] if bsz * 2 <= SECTOR else None
        hfs_start = hfs_size = None
        if b1 and b1[:2] == b"PM":
            nblocks = struct.unpack(">I", b1[4:8])[0]
        for i in range(1, (nblocks or 1) + 1):
            off = i * bsz
            blk = img.sector(off // SECTOR)[off % SECTOR: off % SECTOR + bsz]
            if blk[:2] != b"PM":
                break
            start, size = struct.unpack(">II", blk[8:16])
            typ = blk[48:80].split(b"\x00")[0].decode("latin-1")
            if typ == "Apple_HFS":
                hfs_start, hfs_size = start, size
    else:
        hfs_start = hfs_size = None

    # 4 and 5 -- HFS
    hfs_claims = 0
    if hfs_start is not None:
        vstart = hfs_start * 512
        mdb = img.sector((vstart + 1024) // SECTOR)
        moff = (vstart + 1024) % SECTOR
        mdb = mdb[moff:moff + 512]
        assert mdb[:2] == b"BD", "no MDB signature"
        alblksiz = struct.unpack(">I", mdb[20:24])[0]
        albst = struct.unpack(">H", mdb[28:30])[0]
        firstab_byte = vstart + albst * 512
        ab_sectors = alblksiz // SECTOR
        print("HFS partition   : start block %d, %d blocks of 512"
              % (hfs_start, hfs_size))
        print("HFS volume byte : %d   = LBA %.4f" % (vstart, vstart / SECTOR))
        print("alloc block size: %d bytes = %d sectors" % (alblksiz, ab_sectors))
        print("first alloc blk : byte %d = LBA %.4f"
              % (firstab_byte, firstab_byte / SECTOR))
        print("closed form     : LBA(ab n) = %d + %d n"
              % (firstab_byte // SECTOR, ab_sectors))
        print()
        # MDB layout, Inside Macintosh IV: drVBMSt at +14, drXTFlSize at +130
        # with its three-extent record at +134, drCTFlSize at +146 with its
        # record at +150. Getting the extents-overflow record off by four
        # bytes claims several thousand sectors of nothing, which is what the
        # first run of this tool did.
        claim(vstart // SECTOR, 2, "HFS volume structures")
        # the Alternate MDB: HFS keeps a copy in the second-to-last 512-byte
        # block of its partition. On this disc that is the very last sector of
        # the volume, which is why a first run of this tool reported the last
        # sector as belonging to nobody while it plainly says 'BD'.
        alt = (hfs_start + hfs_size - 2) * 512
        claim(alt // SECTOR, 1, "HFS volume structures", "alternate MDB")
        vbmst = struct.unpack(">H", mdb[14:16])[0]
        nab = struct.unpack(">H", mdb[18:20])[0]
        bmbytes = (nab + 7) // 8
        claim((vstart + vbmst * 512) // SECTOR,
              sectors_for(bmbytes), "HFS volume structures")
        for label, off in (("catalogue", 150), ("extents overflow", 134)):
            for k in range(3):
                st, cnt = struct.unpack(">HH", mdb[off + k * 4: off + k * 4 + 4])
                if cnt:
                    claim((firstab_byte + st * alblksiz) // SECTOR,
                          cnt * ab_sectors, "HFS volume structures", label)
        with open(a.hfs, encoding="utf-8", newline="") as fh:
            hdr = fh.readline().strip().split("\t")
            ix = {k: i for i, k in enumerate(hdr)}
            for line in fh:
                c = line.rstrip("\r\n").split("\t")
                if len(c) < len(hdr):
                    continue
                for col in ("data_extents", "rsrc_extents"):
                    v = c[ix[col]]
                    if not v:
                        continue
                    for piece in v.split(","):
                        piece = piece.strip()
                        if "+" not in piece:
                            continue
                        st, cnt = piece.split("+")
                        st, cnt = int(st), int(cnt)
                        if cnt == 0:
                            continue
                        hfs_claims += 1
                        claim((firstab_byte + st * alblksiz) // SECTOR,
                              cnt * ab_sectors, "HFS fork",
                              c[ix["path"]])

    c = Counter(o if o else "(unclaimed)" for o in own)
    print("sector ownership over %d sectors (%d bytes)" % (total, total * SECTOR))
    print("  %-34s %10s %14s %8s" % ("claimant", "sectors", "bytes", "pct"))
    for k, v in sorted(c.items(), key=lambda kv: -kv[1]):
        print("  %-34s %10d %14d %7.3f%%"
              % (k, v, v * SECTOR, 100.0 * v / total))
    print("  %-34s %10d %14d %7.3f%%"
          % ("TOTAL", sum(c.values()), sum(c.values()) * SECTOR, 100.0))
    print()
    print("HFS fork extents claimed : %d" % hfs_claims)
    print()
    print("sectors claimed by more than one of the five claimants: %d"
          % sum(1 for x in also if x))
    print("(on a hybrid this is the normal case and not an error: the same")
    print(" bytes are described by two catalogues. It is only an error when")
    print(" two records of the SAME catalogue claim one sector.)")
    seen = Counter()
    for i, x in enumerate(also):
        if x:
            for w in x:
                seen[(own[i], w)] += 1
    for (a1, b1), n in seen.most_common(12):
        print("   %-32s also %-30s %7d" % (a1, b1, n))
    print()

    runs = []
    i = 0
    while i < total:
        j = i
        while j < total and own[j] == own[i]:
            j += 1
        runs.append((i, j - i, own[i]))
        i = j
    unc = [r for r in runs if r[2] is None]
    print("unclaimed runs : %d, holding %d sectors (%d bytes)"
          % (len(unc), sum(r[1] for r in unc),
             sum(r[1] for r in unc) * SECTOR))
    hist = Counter(r[1] for r in unc)
    for sz, n in sorted(hist.items()):
        print("   runs of %6d sectors : %5d   (%d sectors)" % (sz, n, sz * n))
    print()
    if a.unclaimed or True:
        print("the unclaimed runs longer than 4 sectors:")
        for st, ln, _ in unc:
            if ln > 4:
                print("   LBA %7d .. %7d  %7d sectors  %12d bytes"
                      % (st, st + ln - 1, ln, ln * SECTOR))
    if a.runs:
        print()
        print("every run:")
        for st, ln, o in runs:
            print("   LBA %7d + %7d  %s" % (st, ln, o or "(unclaimed)"))


if __name__ == "__main__":
    main()
