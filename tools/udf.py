#!/usr/bin/env python3
"""udf.py -- read the UDF filesystem that shares this disc with ISO 9660.

`isodev.py` sees ISO 9660 and reports 2,096 sectors that no file claims. Most
of those sectors are not unclaimed: they belong to a second, complete
filesystem that ISO 9660 cannot see. This reads it.

    python tools/udf.py E                  # volume structures, summary
    python tools/udf.py E --tree           # walk the whole directory hierarchy
    python tools/udf.py E --entries        # every File Entry, by LBA
    python tools/udf.py E --iso notes/isodev-extents.txt   # reconcile the two

Structures per ECMA-167 (3rd ed.) and OSTA UDF. Only the parts this disc uses
are implemented; anything unexpected is printed rather than silently skipped.

Descriptor tag identifiers seen here:
    1 Primary Volume Descriptor      2 Anchor Volume Descriptor Pointer
    4 Implementation Use VD          5 Partition Descriptor
    6 Logical Volume Descriptor      7 Unallocated Space Descriptor
    8 Terminating Descriptor         9 Logical Volume Integrity Descriptor
  256 File Set Descriptor          257 File Identifier Descriptor
  261 File Entry
"""
import argparse
import collections
import re
import struct
import sys

SECTOR = 2048
BS = chr(92)

TAGS = {
    1: "PrimaryVolumeDescriptor", 2: "AnchorVolumeDescriptorPointer",
    3: "VolumeDescriptorPointer", 4: "ImplementationUseVolumeDescriptor",
    5: "PartitionDescriptor", 6: "LogicalVolumeDescriptor",
    7: "UnallocatedSpaceDescriptor", 8: "TerminatingDescriptor",
    9: "LogicalVolumeIntegrityDescriptor",
    256: "FileSetDescriptor", 257: "FileIdentifierDescriptor",
    258: "AllocationExtentDescriptor", 259: "IndirectEntry",
    260: "TerminalEntry", 261: "FileEntry", 262: "ExtendedAttributeHeader",
    263: "UnallocatedSpaceEntry", 264: "SpaceBitmapDescriptor",
    265: "PartitionIntegrityEntry", 266: "ExtendedFileEntry",
}
FILETYPE = {0: "?", 1: "unalloc-space-entry", 2: "partition-integrity",
            3: "indirect", 4: "directory", 5: "file", 6: "block-dev",
            7: "char-dev", 8: "ext-attrs", 9: "fifo", 10: "socket",
            11: "terminal", 12: "symlink", 13: "stream-dir"}


class Dev:
    def __init__(self, letter):
        self.f = open(BS + BS + "." + BS + letter.rstrip(":") + ":", "rb", buffering=0)
        self.reads = 0

    def sector(self, lba, n=1):
        self.f.seek(lba * SECTOR)
        d = self.f.read(SECTOR * n)
        self.reads += 1
        return d


def tag(b, off=0):
    if len(b) < off + 16:
        return None
    tid, ver, cks, res, ser, crc, crclen, loc = struct.unpack_from("<HHBBHHHI", b, off)
    s = sum(b[off:off + 4]) + sum(b[off + 5:off + 16])
    return {"id": tid, "ver": ver, "cks": cks, "cks_ok": (s & 0xFF) == cks,
            "serial": ser, "crc": crc, "crclen": crclen, "loc": loc,
            "name": TAGS.get(tid, "tag%d" % tid)}


def dstring(b):
    """OSTA compressed unicode d-string: length byte is the LAST byte."""
    if not b:
        return ""
    n = b[-1]
    return decode_dchars(b[:n])


def decode_dchars(b):
    if not b:
        return ""
    if b[0] == 8:
        return b[1:].decode("latin-1")
    if b[0] == 16:
        return b[1:].decode("utf-16-be", "replace")
    return b.decode("latin-1", "replace")


def regid(b):
    return "flags=%02x id=%r suffix=%r" % (b[0], b[1:24].rstrip(b"\x00 ").decode("latin-1"),
                                           b[24:32].rstrip(b"\x00").hex())


def timestamp(b):
    tz, year, mo, da, ho, mi, se, cs, hu, mu = struct.unpack_from("<hhBBBBBBBB", b, 0)
    ttype = (tz >> 12) & 0xF
    off = tz & 0xFFF
    if off & 0x800:
        off -= 0x1000
    if off == -2047:
        offs = "none"
    else:
        offs = "%+03d:%02d" % (off // 60, abs(off) % 60)
    return "%04d-%02d-%02d %02d:%02d:%02d.%02d%02d%02d %s (type %d)" % (
        year, mo, da, ho, mi, se, cs, hu, mu, offs, ttype)


def long_ad(b, off=0):
    length, blk, part = struct.unpack_from("<IIH", b, off)
    return {"len": length & 0x3FFFFFFF, "type": length >> 30, "blk": blk, "part": part}


def short_ad(b, off=0):
    length, pos = struct.unpack_from("<II", b, off)
    return {"len": length & 0x3FFFFFFF, "type": length >> 30, "blk": pos}


class UDF:
    def __init__(self, dev):
        self.dev = dev
        self.part_start = None
        self.part_len = None
        self.block = SECTOR
        self.fsd = None
        self.lvid = None
        self.descs = []
        self.anchors = []

    def p2l(self, blk):
        return self.part_start + blk

    def read_vrs(self):
        out = []
        for lba in range(16, 32):
            d = self.dev.sector(lba)
            if len(d) < 7:
                break
            ident = d[1:6]
            if ident in (b"BEA01", b"NSR02", b"NSR03", b"TEA01", b"CD001", b"CDW02"):
                out.append((lba, d[0], ident.decode(), d[6]))
            elif d[:8] == bytes(8):
                pass
        return out

    def read_anchor(self, lba):
        d = self.dev.sector(lba)
        if len(d) < SECTOR:
            return None
        t = tag(d)
        if not t or t["id"] != 2:
            return None
        mlen, mloc, rlen, rloc = struct.unpack_from("<IIII", d, 16)
        return {"lba": lba, "tag": t, "main": (mloc, mlen // SECTOR),
                "reserve": (rloc, rlen // SECTOR)}

    def read_vds(self, loc, n):
        out = []
        for i in range(n):
            d = self.dev.sector(loc + i)
            if len(d) < SECTOR:
                break
            t = tag(d)
            if not t or t["id"] == 0:
                break
            out.append((loc + i, t, d))
            if t["id"] == 8:
                break
        return out

    def parse_vds(self, seq, label):
        print("  %s at LBA %d:" % (label, seq[0][0] if seq else -1))
        for lba, t, d in seq:
            line = "    LBA %6d  tag %3d %-34s crc-ok=%s" % (
                lba, t["id"], t["name"], t["cks_ok"])
            print(line)
            if t["id"] == 1:
                print("        volume identifier   : %r" % dstring(d[24:56]))
                print("        volume set id       : %r" % dstring(d[72:200]))
                print("        recording time      : %s" % timestamp(d[376:388]))
                print("        implementation id   : %s" % regid(d[388:420]))
            elif t["id"] == 4:
                print("        impl id             : %s" % regid(d[16:48]))
                print("        LVID                : %r" % dstring(d[52:180]))
                print("        LV info 1/2/3       : %r %r %r"
                      % (dstring(d[180:216]), dstring(d[216:252]), dstring(d[252:288])))
                print("        impl id (inner)     : %s" % regid(d[288:320]))
            elif t["id"] == 5:
                flags, num = struct.unpack_from("<HH", d, 20)
                acc, start, plen = struct.unpack_from("<III", d, 184)
                print("        partition number    : %d  flags %d" % (num, flags))
                print("        contents            : %s" % regid(d[24:56]))
                print("        access type         : %d" % acc)
                print("        starting location   : LBA %d" % start)
                print("        length              : %d sectors" % plen)
                print("        implementation id   : %s" % regid(d[196:228]))
                self.part_start, self.part_len = start, plen
            elif t["id"] == 6:
                bs, = struct.unpack_from("<I", d, 212)
                nmaps, = struct.unpack_from("<I", d, 268)
                fsd = long_ad(d, 248)
                iseq = struct.unpack_from("<II", d, 432)
                print("        logical volume id   : %r" % dstring(d[84:212]))
                print("        logical block size  : %d" % bs)
                print("        domain id           : %s" % regid(d[216:248]))
                print("        file set descriptor : partition %d block %d, %d bytes"
                      % (fsd["part"], fsd["blk"], fsd["len"]))
                print("        partition maps      : %d" % nmaps)
                print("        integrity sequence  : LBA %d, %d bytes" % (iseq[1], iseq[0]))
                print("        implementation id   : %s" % regid(d[272:304]))
                self.block = bs
                self.fsd = fsd
                self.lvid = (iseq[1], iseq[0] // SECTOR)
            elif t["id"] == 7:
                n, = struct.unpack_from("<I", d, 20)
                print("        allocation descriptors: %d" % n)
                for i in range(n):
                    ln, pos = struct.unpack_from("<II", d, 24 + 8 * i)
                    print("          extent %d sectors at LBA %d" % (ln // SECTOR, pos))

    def read_lvid(self):
        if not self.lvid:
            return
        loc, n = self.lvid
        for i in range(max(n, 1)):
            d = self.dev.sector(loc + i)
            t = tag(d)
            if not t or t["id"] != 9:
                break
            npart, = struct.unpack_from("<I", d, 72)
            lenIU, = struct.unpack_from("<I", d, 76)
            free = struct.unpack_from("<I", d, 80)[0]
            size = struct.unpack_from("<I", d, 80 + 4 * npart)[0]
            iu = 80 + 8 * npart
            print("  LVID at LBA %d:" % (loc + i))
            print("        recording time      : %s" % timestamp(d[16:28]))
            print("        integrity type      : %d (%s)"
                  % (struct.unpack_from("<I", d, 28)[0],
                     "closed" if struct.unpack_from("<I", d, 28)[0] == 1 else "open"))
            print("        next unique id      : %d" % struct.unpack_from("<Q", d, 32)[0])
            print("        partitions          : %d" % npart)
            print("        free space          : %d sectors" % free)
            print("        partition size      : %d sectors" % size)
            if lenIU >= 46:
                print("        implementation id   : %s" % regid(d[iu:iu + 32]))
                nf, nd, rev_min, rev_max = struct.unpack_from("<IIHH", d, iu + 32)
                print("        files / directories : %d / %d" % (nf, nd))
                print("        min/max UDF read rev: %04x / %04x" % (rev_min, rev_max))
            break

    def read_fe(self, lba):
        d = self.dev.sector(lba)
        t = tag(d)
        if not t or t["id"] not in (261, 266):
            return None
        ext = t["id"] == 266
        icb_ft = d[16 + 11]
        icb_flags, = struct.unpack_from("<H", d, 16 + 18)
        ad_type = icb_flags & 7
        base = 176 if not ext else 216
        info_len, = struct.unpack_from("<Q", d, 56)
        blocks, = struct.unpack_from("<Q", d, 64)
        mtime = timestamp(d[84:96]) if not ext else timestamp(d[92:104])
        l_ea, l_ad = struct.unpack_from("<II", d, base - 8)
        ads = []
        p = base + l_ea
        if ad_type == 0:
            for i in range(l_ad // 8):
                ads.append(short_ad(d, p + 8 * i))
        elif ad_type == 1:
            for i in range(l_ad // 16):
                a = long_ad(d, p + 16 * i)
                ads.append({"len": a["len"], "type": a["type"], "blk": a["blk"]})
        elif ad_type == 3:
            ads.append({"embedded": True, "len": l_ad, "off": p})
        return {"lba": lba, "type": FILETYPE.get(icb_ft, str(icb_ft)),
                "ad_type": ad_type, "len": info_len, "blocks": blocks,
                "mtime": mtime, "ads": ads, "l_ea": l_ea, "l_ad": l_ad,
                "impl": regid(d[128:160]) if not ext else regid(d[168:200]),
                "uniq": struct.unpack_from("<Q", d, 160 if not ext else 200)[0],
                "raw": d, "ext": ext, "links": struct.unpack_from("<H", d, 48)[0]}

    def read_dir(self, fe):
        """Yield (name, characteristics, icb_long_ad) from a directory File Entry."""
        data = b""
        for ad in fe["ads"]:
            if ad.get("embedded"):
                data += fe["raw"][ad["off"]:ad["off"] + ad["len"]]
            else:
                n = (ad["len"] + SECTOR - 1) // SECTOR
                data += self.dev.sector(self.p2l(ad["blk"]), n)[:ad["len"]]
        p = 0
        while p + 38 <= len(data):
            t = tag(data, p)
            if not t or t["id"] != 257:
                break
            ver, chars, l_fi = struct.unpack_from("<HBB", data, p + 16)
            icb = long_ad(data, p + 20)
            l_iu, = struct.unpack_from("<H", data, p + 36)
            name_off = p + 38 + l_iu
            name = decode_dchars(data[name_off:name_off + l_fi])
            total = 38 + l_iu + l_fi
            total += (4 - (total % 4)) % 4
            yield name, chars, icb
            p += total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("--tree", action="store_true")
    ap.add_argument("--entries", action="store_true")
    ap.add_argument("--iso")
    a = ap.parse_args()

    dev = Dev(a.drive)
    u = UDF(dev)

    print("=== volume recognition sequence (LBA 16..31) ===")
    for lba, stype, ident, ver in u.read_vrs():
        print("  LBA %2d  type=%d  %s  version=%d" % (lba, stype, ident, ver))

    print()
    print("=== anchors ===")
    # last readable sector, found by probing
    lo, hi = 0, 1 << 22
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if len(dev.sector(mid)) == SECTOR:
            lo = mid
        else:
            hi = mid - 1
    last = lo
    print("  last sector that returns 2048 bytes: LBA %d" % last)
    for lba in (256, last - 256, last, last + 1):
        an = u.read_anchor(lba)
        if an:
            u.anchors.append(an)
            print("  anchor at LBA %d: main VDS %d sectors at LBA %d, reserve %d at LBA %d"
                  % (lba, an["main"][1], an["main"][0], an["reserve"][1], an["reserve"][0]))
        else:
            print("  no anchor at LBA %d" % lba)

    if not u.anchors:
        print("no UDF anchor found")
        return

    print()
    print("=== volume descriptor sequences ===")
    an = u.anchors[0]
    u.parse_vds(u.read_vds(*an["main"]), "main VDS")
    print()
    u.parse_vds(u.read_vds(*an["reserve"]), "reserve VDS")

    print()
    print("=== logical volume integrity ===")
    u.read_lvid()

    print()
    print("=== file set descriptor ===")
    fsd_lba = u.p2l(u.fsd["blk"])
    d = dev.sector(fsd_lba)
    t = tag(d)
    print("  LBA %d  tag %d %s" % (fsd_lba, t["id"], t["name"]))
    print("        recording time      : %s" % timestamp(d[16:28]))
    print("        logical volume id   : %r" % dstring(d[112:240]))
    print("        file set identifier : %r" % dstring(d[304:336]))
    print("        copyright file id   : %r" % dstring(d[336:368]))
    print("        abstract file id    : %r" % dstring(d[368:400]))
    root = long_ad(d, 400)
    print("        root directory ICB  : partition %d block %d (LBA %d)"
          % (root["part"], root["blk"], u.p2l(root["blk"])))
    print("        domain identifier   : %s" % regid(d[416:448]))

    # walk
    files = []
    dirs = []
    stack = [(u.p2l(root["blk"]), "")]
    seen = set()
    while stack:
        lba, path = stack.pop()
        if lba in seen:
            continue
        seen.add(lba)
        fe = u.read_fe(lba)
        if not fe:
            print("  !! no File Entry at LBA %d (%s)" % (lba, path))
            continue
        dirs.append((lba, path or "/", fe))
        for name, chars, icb in u.read_dir(fe):
            if chars & 8:      # parent
                continue
            child = u.p2l(icb["blk"])
            full = path + "/" + name
            if chars & 2:      # directory
                stack.append((child, full))
            else:
                cfe = u.read_fe(child)
                if cfe:
                    files.append((child, full, cfe))
                else:
                    print("  !! no File Entry at LBA %d (%s)" % (child, full))

    print()
    print("=== the tree, as UDF describes it ===")
    print("  directories : %d" % len(dirs))
    print("  files       : %d" % len(files))
    print("  file bytes  : %d" % sum(f[2]["len"] for f in files))
    print("  File Entry sectors: %d (one per file + one per directory)"
          % (len(files) + len(dirs)))
    embedded = sum(1 for f in files if f[2]["ad_type"] == 3)
    print("  files with data embedded in the File Entry: %d" % embedded)

    ent_lbas = sorted([f[0] for f in files] + [d0[0] for d0 in dirs])
    print("  File Entry LBA range: %d .. %d" % (ent_lbas[0], ent_lbas[-1]))

    if a.entries:
        print()
        print("=== every File Entry, by LBA ===")
        rows = sorted([(f[0], f[1], f[2]) for f in files] +
                      [(d0[0], d0[1] + "  [dir]", d0[2]) for d0 in dirs])
        for lba, name, fe in rows:
            ex = " ".join("%d@%d" % (ad["len"], u.p2l(ad["blk"]))
                          for ad in fe["ads"] if not ad.get("embedded"))
            print("  %7d  %-11s %12d  %s   %s" % (lba, fe["type"], fe["len"], name, ex))

    if a.tree:
        print()
        print("=== directory tree ===")
        for lba, path, fe in sorted(dirs, key=lambda r: r[1]):
            print("  %7d  %s" % (lba, path))

    if a.iso:
        print()
        print("=== reconciliation with the ISO 9660 extent map ===")
        gaps = []
        for line in open(a.iso, encoding="utf-8", errors="replace"):
            m = re.search(r"GAP of (\d+) sectors .LBA (\d+)\.\.(\d+).", line)
            if m:
                gaps.append((int(m.group(2)), int(m.group(1)), int(m.group(3))))
        gap_sectors = set()
        for s, n, e in gaps:
            gap_sectors.update(range(s, e + 1))
        udf_sectors = set(ent_lbas)
        for lba, path, fe in dirs:
            for ad in fe["ads"]:
                if not ad.get("embedded"):
                    n = (ad["len"] + SECTOR - 1) // SECTOR
                    udf_sectors.update(range(u.p2l(ad["blk"]), u.p2l(ad["blk"]) + n))
        print("  ISO calls %d sectors unclaimed" % len(gap_sectors))
        print("  UDF metadata occupies %d sectors" % len(udf_sectors))
        print("  of those, %d are inside ISO's gaps" % len(udf_sectors & gap_sectors))
        print("  ISO gap sectors NOT explained by UDF metadata: %d"
              % len(gap_sectors - udf_sectors))
        rest = sorted(gap_sectors - udf_sectors)
        if rest:
            runs = []
            s = p = rest[0]
            for x in rest[1:]:
                if x == p + 1:
                    p = x
                else:
                    runs.append((s, p - s + 1))
                    s = p = x
            runs.append((s, p - s + 1))
            print("  those remaining sectors, as runs:")
            for s, n in runs:
                print("    LBA %d..%d  (%d sectors)" % (s, s + n - 1, n))

    print()
    print("  device reads: %d" % dev.reads)


if __name__ == "__main__":
    main()
