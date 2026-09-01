#!/usr/bin/env python3
"""zipdir.py -- read the central directory of a ZIP archive without extracting.

93.98 % of this disc is one 1,286,963,770-byte file. Listing what is inside it
is a measurement of the container; unpacking 1.29 GB and censusing it as though
it were the disc is not. This reads the central directory only: names, methods,
sizes, CRCs and the DOS timestamps, which are a clock the disc carries nowhere
else.

    python tools/zipdir.py E:/0compressed.zip
    python tools/zipdir.py E:/0compressed.zip --list > notes/zip-members.txt
    python tools/zipdir.py E:/0compressed.zip --grep KnowWonder

Reads at most a few megabytes off the end of the file plus the central
directory itself.
"""
import argparse
import collections
import datetime
import os
import re
import struct
import sys

EOCD = b"PK" + bytes([5, 6])
EOCD64 = b"PK" + bytes([6, 6])
EOCD64L = b"PK" + bytes([6, 7])
CEN = b"PK" + bytes([1, 2])
METHODS = {0: "stored", 1: "shrunk", 6: "imploded", 8: "deflate", 9: "deflate64",
           12: "bzip2", 14: "lzma", 95: "xz", 93: "zstd", 98: "ppmd"}
MADEBY = {0: "MS-DOS/FAT", 3: "Unix", 6: "OS/2 HPFS", 7: "Macintosh",
          10: "Windows NTFS", 11: "MVS", 14: "VFAT", 19: "OS X"}


def dosdt(dt, tm):
    try:
        return datetime.datetime(1980 + ((dt >> 9) & 0x7F), (dt >> 5) & 0xF,
                                 dt & 0x1F, (tm >> 11) & 0x1F, (tm >> 5) & 0x3F,
                                 (tm & 0x1F) * 2)
    except ValueError:
        return None


def find_eocd(f, size):
    n = min(size, 66000)
    f.seek(size - n)
    tail = f.read(n)
    i = tail.rfind(EOCD)
    if i < 0:
        raise SystemExit("no end-of-central-directory record found")
    return size - n + i, tail[i:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--grep")
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()

    size = os.path.getsize(a.path)
    f = open(a.path, "rb")
    eocd_off, tail = find_eocd(f, size)

    (_, dnum, dcd, ndisk, ntotal, cdsize, cdoff, clen) = struct.unpack_from(
        "<IHHHHIIH", tail, 0)
    comment = tail[22:22 + clen]
    print("archive          : %s" % a.path)
    print("file size        : %d bytes" % size)
    print("EOCD at offset   : %d  (%d bytes from the end)" % (eocd_off, size - eocd_off))
    print("disks            : this %d, cd starts on %d" % (dnum, dcd))
    print("entries          : %d on this disk, %d total" % (ndisk, ntotal))
    print("central directory: %d bytes at offset %d" % (cdsize, cdoff))
    print("archive comment  : %d bytes %s" % (clen, repr(comment[:80]) if clen else ""))

    zip64 = (ntotal == 0xFFFF or cdoff == 0xFFFFFFFF or cdsize == 0xFFFFFFFF)
    # look for the zip64 locator regardless, and say whether it is there
    f.seek(max(0, eocd_off - 20))
    loc = f.read(20)
    has64 = loc[:4] == EOCD64L
    print("ZIP64 locator    : %s" % ("present" if has64 else "absent"))
    if zip64 and not has64:
        print("  !! counts say ZIP64 but no locator found")

    f.seek(cdoff)
    cd = f.read(cdsize)
    print("central directory read: %d bytes" % len(cd))
    print()

    rows = []
    p = 0
    while p + 46 <= len(cd) and cd[p:p + 4] == CEN:
        (_, vmade, vneed, flags, method, mtime, mdate, crc, csize, usize,
         nlen, elen, klen, dstart, iattr, eattr, lho) = struct.unpack_from(
            "<IHHHHHHIIIHHHHHII", cd, p)
        name = cd[p + 46:p + 46 + nlen]
        extra = cd[p + 46 + nlen:p + 46 + nlen + elen]
        cmt = cd[p + 46 + nlen + elen:p + 46 + nlen + elen + klen]
        try:
            nm = name.decode("utf-8" if flags & 0x800 else "cp437")
        except UnicodeDecodeError:
            nm = name.decode("latin-1")
        rows.append({"name": nm, "vmade": vmade, "vneed": vneed, "flags": flags,
                     "method": method, "dt": dosdt(mdate, mtime), "crc": crc,
                     "csize": csize, "usize": usize, "eattr": eattr,
                     "lho": lho, "extra": extra, "cmt": cmt,
                     "raw_mdate": mdate, "raw_mtime": mtime})
        p += 46 + nlen + elen + klen
    print("members parsed   : %d  (header said %d)" % (len(rows), ntotal))
    if p != len(cd):
        print("  !! %d bytes of central directory left unparsed at offset %d"
              % (len(cd) - p, p))
    print()

    dirs = [r for r in rows if r["name"].endswith("/")]
    files = [r for r in rows if not r["name"].endswith("/")]
    tot_c = sum(r["csize"] for r in files)
    tot_u = sum(r["usize"] for r in files)
    print("directory entries: %d" % len(dirs))
    print("file entries     : %d" % len(files))
    print("compressed total : %d bytes" % tot_c)
    print("uncompressed tot : %d bytes" % tot_u)
    if tot_c:
        print("whole-archive ratio: %.4f : 1  (saves %.2f %%)"
              % (tot_u / tot_c, 100.0 * (1 - tot_c / tot_u) if tot_u else 0))
    print("central dir + eocd + local headers overhead: %d bytes"
          % (size - tot_c - 0))
    print()

    print("compression methods:")
    for m, c in collections.Counter(r["method"] for r in files).most_common():
        cc = sum(r["csize"] for r in files if r["method"] == m)
        uu = sum(r["usize"] for r in files if r["method"] == m)
        print("  %-10s (%2d)  %6d files  %14d -> %14d  %s"
              % (METHODS.get(m, "?"), m, c, uu, cc,
                 "%.3f:1" % (uu / cc) if cc else "-"))
    print()

    print("version made by (upper byte = host system):")
    for v, c in collections.Counter(r["vmade"] for r in files).most_common():
        print("  0x%04x  host %d %-12s  zip spec %d.%d   x%d"
              % (v, v >> 8, MADEBY.get(v >> 8, "?"), (v & 0xFF) // 10, (v & 0xFF) % 10, c))
    print("version needed:")
    for v, c in collections.Counter(r["vneed"] for r in files).most_common():
        print("  %d.%d  x%d" % (v // 10, v % 10, c))
    print("general purpose flags:")
    for v, c in collections.Counter(r["flags"] for r in files).most_common():
        print("  0x%04x  x%d" % (v, c))
    print("extra-field lengths:")
    for v, c in collections.Counter(len(r["extra"]) for r in files).most_common(6):
        print("  %d bytes  x%d" % (v, c))
    print()

    print("extensions inside the archive (by uncompressed bytes):")
    ext = collections.defaultdict(lambda: [0, 0, 0])
    for r in files:
        e = os.path.splitext(r["name"])[1].lower() or "(none)"
        ext[e][0] += 1
        ext[e][1] += r["usize"]
        ext[e][2] += r["csize"]
    for e, (c, u, cz) in sorted(ext.items(), key=lambda kv: -kv[1][1])[:a.top]:
        print("  %-10s %6d  %14d -> %14d  %6.2f %%  %s"
              % (e, c, u, cz, 100.0 * u / tot_u if tot_u else 0,
                 "%.2f:1" % (u / cz) if cz else "-"))
    print("  ... %d extensions total" % len(ext))
    print()

    print("top-level entries inside the archive:")
    top = collections.defaultdict(lambda: [0, 0])
    for r in files:
        t = r["name"].replace(chr(92), "/").split("/")[0]
        top[t][0] += 1
        top[t][1] += r["usize"]
    for t, (c, u) in sorted(top.items(), key=lambda kv: -kv[1][1]):
        print("  %-40s %6d files  %14d bytes" % (t[:40], c, u))
    print()

    print("second-level entries (first two path components):")
    two = collections.defaultdict(lambda: [0, 0])
    for r in files:
        parts = r["name"].replace(chr(92), "/").split("/")
        t = "/".join(parts[:2]) if len(parts) > 1 else parts[0]
        two[t][0] += 1
        two[t][1] += r["usize"]
    for t, (c, u) in sorted(two.items(), key=lambda kv: -kv[1][1])[:a.top]:
        print("  %-50s %6d  %14d" % (t[:50], c, u))
    print("  ... %d distinct" % len(two))
    print()

    print("DOS timestamps inside the archive:")
    dts = [r["dt"] for r in files if r["dt"]]
    print("  members with a parseable date: %d of %d" % (len(dts), len(files)))
    if dts:
        print("  oldest : %s" % min(dts))
        print("  newest : %s" % max(dts))
        print("  spread : %s" % (max(dts) - min(dts)))
        print("  distinct values: %d" % len(set(dts)))
        for d, c in collections.Counter(dts).most_common(10):
            print("    %s  x%d" % (d, c))
        print("  by month:")
        for m, c in sorted(collections.Counter(
                (d.year, d.month) for d in dts).items()):
            print("    %04d-%02d  x%d" % (m[0], m[1], c))
    print()

    print("duplicate content, by (CRC, uncompressed size):")
    key = collections.Counter((r["crc"], r["usize"]) for r in files)
    dup = {k: v for k, v in key.items() if v > 1}
    print("  distinct (crc,size) pairs: %d" % len(key))
    print("  pairs appearing more than once: %d" % len(dup))
    print("  members that share a pair with another: %d"
          % sum(v for v in dup.values()))
    print("  bytes those duplicates account for (uncompressed): %d"
          % sum(k[1] * (v - 1) for k, v in dup.items()))
    for k, v in sorted(dup.items(), key=lambda kv: -kv[1] * kv[0][1])[:10]:
        names = [r["name"] for r in files if (r["crc"], r["usize"]) == k][:3]
        print("    crc %08x size %10d  x%-4d  %s" % (k[0], k[1], v, names[0]))
    print()

    print("zero-length members: %d" % sum(1 for r in files if r["usize"] == 0))
    print("largest members:")
    for r in sorted(files, key=lambda r: -r["usize"])[:12]:
        print("  %14d -> %14d  %-8s %s"
              % (r["usize"], r["csize"], METHODS.get(r["method"], "?"), r["name"]))

    print()
    print("absolute-looking paths inside member names: %d"
          % sum(1 for r in files if re.match("^[A-Za-z]:[/" + chr(92)*2 + "]", r["name"])))
    print("member names containing a backslash: %d"
          % sum(1 for r in files if chr(92) in r["name"]))

    if a.grep:
        print()
        print("=== member names matching %r ===" % a.grep)
        rx = re.compile(a.grep, re.I)
        n = 0
        for r in rows:
            if rx.search(r["name"]):
                print("  %s" % r["name"])
                n += 1
        print("  %d matches" % n)

    if a.list:
        print()
        print("=== every member ===")
        print("%-10s %14s %14s %8s %-19s %s"
              % ("method", "uncompressed", "compressed", "crc32", "dos mtime", "name"))
        for r in rows:
            print("%-10s %14d %14d %08x %-19s %s"
                  % (METHODS.get(r["method"], str(r["method"])), r["usize"],
                     r["csize"], r["crc"], r["dt"] or "-", r["name"]))


if __name__ == "__main__":
    main()
