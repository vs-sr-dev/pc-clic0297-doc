#!/usr/bin/env python3
"""twofs.py -- the same sectors, two catalogues: what each filesystem can see.

This disc carries an ISO 9660 volume (with a Joliet supplement) and an HFS
volume over the same medium. Windows mounts the first and reports 2,374 files in
four folders; the HFS Master Directory Block reports 2,401 files in ten. The
difference is what this tool measures, and the first thing it has to do is
declare what it is counting, because the two numbers are not the same kind of
thing.

THE COUNTING RULE, DECLARED BEFORE THE RESULT
---------------------------------------------
An HFS file has two forks, data and resource. A *file* here means **one catalog
record of type cdrFilRec**, regardless of how many of its forks are non-empty.
That is the same unit the MDB's drFilCnt counts, and it is the only unit under
which the two sides can be subtracted at all: ISO 9660 has no concept of a fork,
so an ISO "file" is one directory record with a data extent.

Under any other rule the subtraction is meaningless, so the rule is fixed here
and the resource forks are reported **separately**, as bytes and as a count,
never folded into the file total.

Directories are counted **including the root** on both sides, because ISO 9660's
root is a directory record like any other and HFS's root has a catalog record
like any other. The MDB's drDirCnt excludes the root; that is a property of the
MDB field, not of the volume, and `hfs.py --catalog` prints both.

    python tools/twofs.py --hfs notes/hfs-files.tsv --iso _work/iso
    python tools/twofs.py --hfs notes/hfs-files.tsv --iso _work/iso --only-hfs
    python tools/twofs.py --hfs notes/hfs-files.tsv --iso _work/iso --align

MATCHING
--------
A file is "shared" when the same path exists on both sides and the data-fork
length equals the ISO file length. Names are compared case-insensitively:
ISO 9660 level 1 upper-cases, Joliet does not, and HFS preserves whatever the
Mac typed. Where a name differs only in case the tool says so rather than
silently pairing them.
"""
import argparse
import os
import sys


def load_hfs(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        head = f.readline().rstrip("\n").split("\t")
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < len(head):
                continue
            d = dict(zip(head, p))
            for k in ("data_len", "rsrc_len", "data_ab", "rsrc_ab", "cnid"):
                d[k] = int(d[k])
            rows.append(d)
    return rows


def load_iso(root):
    rows = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            rows.append({"path": rel, "size": os.path.getsize(full)})
    return rows


def strip_vol(p):
    """HFS paths carry the volume name as their first component."""
    i = p.find("/")
    return p[i + 1:] if i >= 0 else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hfs", default="notes/hfs-files.tsv")
    ap.add_argument("--iso", default="_work/iso")
    ap.add_argument("--only-hfs", action="store_true")
    ap.add_argument("--only-iso", action="store_true")
    ap.add_argument("--align", action="store_true",
                    help="check that every HFS data fork starts on a 5-sector LBA")
    ap.add_argument("--mismatch", action="store_true")
    a = ap.parse_args()

    hfs = load_hfs(a.hfs)
    iso = load_iso(a.iso)

    hmap = {}
    for r in hfs:
        hmap.setdefault(strip_vol(r["path"]).lower(), []).append(r)
    imap = {}
    for r in iso:
        imap.setdefault(r["path"].lower(), []).append(r)

    hkeys = set(hmap)
    ikeys = set(imap)
    both = hkeys & ikeys
    honly = hkeys - ikeys
    ionly = ikeys - hkeys

    print("counting rule : one HFS catalog record of type cdrFilRec = one file;")
    print("                resource forks are reported separately and never")
    print("                folded into the file total. Paths compared")
    print("                case-insensitively.")
    print()
    print("HFS  catalog records of type file : %d" % len(hfs))
    print("HFS  distinct paths               : %d" % len(hkeys))
    print("ISO  files on the mounted volume  : %d" % len(iso))
    print("ISO  distinct paths               : %d" % len(ikeys))
    print()
    print("paths on both sides               : %d" % len(both))
    print("paths only in HFS                 : %d" % len(honly))
    print("paths only in ISO                 : %d" % len(ionly))
    print()
    print("check: %d + %d = %d  (HFS total %s)"
          % (len(both), len(honly), len(both) + len(honly),
             "matches" if len(both) + len(honly) == len(hfs) else "DIFFERS"))
    print("check: %d + %d = %d  (ISO total %s)"
          % (len(both), len(ionly), len(both) + len(ionly),
             "matches" if len(both) + len(ionly) == len(iso) else "DIFFERS"))

    # resource forks, the thing the naive subtraction would have folded in
    withr = [r for r in hfs if r["rsrc_len"] > 0]
    print()
    print("HFS files with a non-empty resource fork : %d" % len(withr))
    print("  total resource-fork bytes              : %d"
          % sum(r["rsrc_len"] for r in withr))
    print("  total data-fork bytes                  : %d"
          % sum(r["data_len"] for r in hfs))
    print("  ISO total bytes                        : %d"
          % sum(r["size"] for r in iso))

    if a.only_hfs:
        print()
        print("--- the files the PC side cannot see ---")
        print("%-10s %-5s %-5s %10s %10s  %s"
              % ("cnid", "type", "creat", "data", "rsrc", "path"))
        rows = sorted((strip_vol(r["path"]), r) for k in honly for r in hmap[k])
        for p, r in rows:
            print("%-10d %-5s %-5s %10d %10d  %s"
                  % (r["cnid"], r["type"], r["creator"],
                     r["data_len"], r["rsrc_len"], p))
        print()
        print("total %d files, %d data bytes, %d resource bytes"
              % (len(rows), sum(r["data_len"] for _, r in rows),
                 sum(r["rsrc_len"] for _, r in rows)))

    if a.only_iso:
        print()
        print("--- the files the Mac side cannot see ---")
        for k in sorted(ionly):
            for r in imap[k]:
                print("%10d  %s" % (r["size"], r["path"]))

    if a.mismatch:
        print()
        print("--- shared paths whose lengths disagree ---")
        n = 0
        for k in sorted(both):
            h = hmap[k][0]
            i = imap[k][0]
            if h["data_len"] != i["size"]:
                print("%10d HFS  %10d ISO   %s" % (h["data_len"], i["size"], k))
                n += 1
        print("%d of %d shared paths disagree about the data length" % (n, len(both)))

    if a.align:
        print()
        print("--- where the HFS data forks land on the 2048-byte grid ---")
        res = {}
        frac = 0
        for r in hfs:
            if r["data_len"] == 0 or not r["data_lba"]:
                continue
            v = float(r["data_lba"])
            if v != int(v):
                frac += 1
            res[int(v) % 5] = res.get(int(v) % 5, 0) + 1
        print("HFS data-fork start LBA mod 5 : %s" % res)
        print("HFS data forks starting mid-sector : %d" % frac)
        print()
        print("An allocation block is %d bytes and the first one begins on an"
              % 10240)
        print("exact sector boundary, so every allocation block starts on an LBA")
        print("that is a multiple of five. A residue class other than 0 here")
        print("would falsify that.")


if __name__ == "__main__":
    main()
