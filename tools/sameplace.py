#!/usr/bin/env python3
"""sameplace.py -- do the two catalogues point at the same sectors?

The ISO 9660 volume and the HFS volume on this disc describe overlapping sets of
files. 2,373 paths exist on both sides. The question this tool answers is not
whether the *names* match -- twofs.py does that -- but whether the two
filesystems hand out the same **address** for the same file.

The stakes are arithmetic. 603,250,688 bytes of volume hold 583,368,848 bytes of
ISO payload. If the HFS side were a second copy of the same content rather than a
second view of it, the disc would need about 1.17 GB and it does not have it. So
"one copy, two catalogues" is the expected answer, and this tool exists to state
it as a measurement over all 2,373 shared files rather than as an inference from
a capacity argument.

    python tools/sameplace.py
    python tools/sameplace.py --show-mismatch

HOW THE TWO ADDRESSES ARE COMPUTED
----------------------------------
ISO: the directory record's extent field, already an LBA of 2,048-byte sectors,
     read by isodev.py.

HFS: the first extent of the file's filExtRec, an index into the volume's
     allocation blocks. Converted with

         byte = partition_start*512 + drAlBlSt*512 + allocblock*drAlBlkSiz
         LBA  = byte / 2048

     Note that filStBlk, the record's own "first allocation block" field, is
     zero on all 2,401 records of this volume and must not be used: an address
     taken from it puts every file at the first allocation block and makes any
     alignment test come out perfect for the wrong reason.

The comparison is exact. A file whose two addresses differ by even one sector is
reported, because on a disc where one filesystem was built inside the other,
a single exception is more interesting than the 2,372 agreements.
"""
import argparse
import re
import sys

SECTOR = 2048

EXT_RE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(.*?)\s*$")


def load_iso_extents(path):
    """Parse isodev.py --extents output into path -> (lba, sectors, bytes)."""
    out = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        if "GAP of" in line or "[dir extent]" in line:
            continue
        m = EXT_RE.match(line.rstrip("\n"))
        if not m:
            continue
        lba, sects, byts, slack, name = m.groups()
        if not name or name.startswith("---"):
            continue
        out[name.lower()] = (int(lba), int(sects), int(byts))
    return out


def load_hfs(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        head = f.readline().rstrip("\n").split("\t")
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < len(head):
                continue
            d = dict(zip(head, p))
            # strip the volume name that heads every HFS path
            i = d["path"].find("/")
            rel = d["path"][i + 1:] if i >= 0 else ""
            d["rel"] = rel
            out[rel.lower()] = d
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iso-extents", default="notes/isodev-extents.txt")
    ap.add_argument("--hfs", default="notes/hfs-files.tsv")
    ap.add_argument("--show-mismatch", action="store_true")
    a = ap.parse_args()

    iso = load_iso_extents(a.iso_extents)
    hfs = load_hfs(a.hfs)

    shared = sorted(set(iso) & set(hfs))
    agree = []
    differ = []
    for k in shared:
        ilba = iso[k][0]
        h = hfs[k]
        if not h["data_lba"]:
            differ.append((k, ilba, None, iso[k][2], int(h["data_len"])))
            continue
        hlba = float(h["data_lba"])
        if abs(hlba - ilba) < 1e-9:
            agree.append(k)
        else:
            differ.append((k, ilba, hlba, iso[k][2], int(h["data_len"])))

    print("ISO extent records parsed  : %d" % len(iso))
    print("HFS file records parsed    : %d" % len(hfs))
    print("paths present in both      : %d" % len(shared))
    print()
    print("same starting sector       : %d" % len(agree))
    print("different starting sector  : %d" % len(differ))
    print()
    pct = 100.0 * len(agree) / len(shared) if shared else 0.0
    print("%.4f %% of the shared files begin on the same sector under both"
          % pct)
    print("filesystems. Where that holds, the file exists once and is addressed")
    print("twice.")

    if differ:
        print()
        print("--- the exceptions ---")
        print("%10s %12s %12s %10s  %s"
              % ("ISO LBA", "HFS LBA", "delta", "ISO bytes", "path"))
        for k, ilba, hlba, ib, hb in differ:
            print("%10d %12s %12s %10d  %s"
                  % (ilba,
                     ("%.1f" % hlba) if hlba is not None else "(no fork)",
                     ("%+.1f" % (hlba - ilba)) if hlba is not None else "-",
                     ib, k))
            if hb != ib:
                print("%10s %12s %12s %10d  ^ and the two catalogues also"
                      " disagree about the length" % ("", "", "", hb))

    # the alignment consequence, stated as a measurement over the ISO side
    print()
    print("--- the 5-sector grid, from the ISO side ---")
    res = {}
    for k, (lba, s, b) in iso.items():
        res[lba % 5] = res.get(lba % 5, 0) + 1
    print("ISO file start LBA mod 5 : %s" % dict(sorted(res.items())))
    off = [(lba, k) for k, (lba, s, b) in iso.items() if lba % 5]
    for lba, k in sorted(off):
        inh = k in hfs
        print("  LBA %6d  mod5=%d  %-24s  in the HFS catalog: %s"
              % (lba, lba % 5, k, "yes" if inh else "NO"))
    print()
    print("The first allocation block of the HFS volume begins at an exact")
    print("sector boundary, and an allocation block is five sectors, so every")
    print("HFS-addressed file starts on a multiple of five. A file at an LBA")
    print("that is not a multiple of five is therefore a file the HFS volume")
    print("does not place -- which is a prediction about the catalogue, and")
    print("the column above is the test of it.")


if __name__ == "__main__":
    main()
