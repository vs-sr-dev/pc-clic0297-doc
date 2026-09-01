#!/usr/bin/env python3
"""gapname.py -- name every sector ISO 9660 calls unclaimed, or say it is spare.

isodev.py --extents reports three gaps on this disc totalling 1,521 sectors,
and udf.py reduces them to 265 unexplained. 265 is not zero, and "unclaimed"
means "not claimed by the filesystem I can read", so this walks the gaps
sector by sector, reads each one, and gives it a name from what is actually in
it. Anything it cannot name is reported as genuinely spare, with its LBA.

It knows no LBA in advance. The structure positions come from:

  * ISO 9660: the system area is LBA 0..15 by definition, and the path table
    locations are read out of the PVD at +140 and +148;
  * UDF: the anchor at LBA 256 names the main and reserve volume descriptor
    sequences and their lengths; the Logical Volume Descriptor names the
    integrity sequence and the file set descriptor; the partition descriptor
    names the partition start.

    python tools/gapname.py E --gaps 0-258 302-1559 1826652-1826655
    python tools/gapname.py E --gaps 0-258 --verbose
"""
import argparse
import struct

BS = chr(92)
SECTOR = 2048

TAGS = {1: "PrimaryVolumeDescriptor", 2: "AnchorVolumeDescriptorPointer",
        3: "VolumeDescriptorPointer", 4: "ImplementationUseVolumeDescriptor",
        5: "PartitionDescriptor", 6: "LogicalVolumeDescriptor",
        7: "UnallocatedSpaceDescriptor", 8: "TerminatingDescriptor",
        9: "LogicalVolumeIntegrityDesc", 256: "FileSetDescriptor",
        257: "FileIdentifierDescriptor", 258: "AllocationExtentDescriptor",
        259: "IndirectEntry", 260: "TerminalEntry", 261: "FileEntry",
        262: "ExtendedAttributeHeaderDescriptor", 263: "UnallocatedSpaceEntry",
        264: "SpaceBitmapDescriptor", 265: "PartitionIntegrityEntry",
        266: "ExtendedFileEntry"}


class Dev(object):
    def __init__(self, letter):
        self.f = open(BS + BS + "." + BS + letter.upper() + ":", "rb",
                      buffering=0)
        self.n = 0

    def read(self, lba):
        self.f.seek(lba * SECTOR)
        self.n += 1
        return self.f.read(SECTOR)


def classify(b, lba, known, pstart=None, prev=None):
    """Name one sector. pstart is the UDF partition start, because a UDF
    descriptor's TagLocation is partition-relative inside the partition and
    absolute outside it, and a reader that only tries the absolute reading
    calls every directory data sector 'unidentified'."""
    if lba in known:
        return known[lba]
    if not b:
        return "unreadable"
    if b[1:6] == b"CD001":
        t = b[0]
        return ("ISO 9660 primary volume descriptor" if t == 1 else
                "ISO 9660 supplementary volume descriptor" if t == 2 else
                "ISO 9660 volume descriptor set terminator" if t == 255 else
                "ISO 9660 volume descriptor type %d" % t)
    if b[1:6] in (b"BEA01", b"NSR02", b"NSR03", b"TEA01", b"BOOT2", b"CDW02"):
        return "UDF volume recognition: %s" % b[1:6].decode("ascii")
    tag = struct.unpack_from("<H", b, 0)[0]
    if tag in TAGS:
        loc = struct.unpack_from("<I", b, 12)[0]
        rel = (lba - pstart) if pstart is not None else None
        if loc == lba or loc == rel:
            if TAGS[tag] == "FileIdentifierDescriptor":
                return "UDF directory data (FileIdentifierDescriptors)"
            return "UDF %s" % TAGS[tag]
    if prev and prev.startswith("UDF directory data"):
        return "UDF directory data (continuation of the previous extent)"
    if not any(b):
        return None          # all zero: spare unless named
    return "non-zero, unidentified"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("--gaps", nargs="+", required=True,
                    help="ranges like 0-258, inclusive")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    dev = Dev(a.drive)
    known = {}
    part_start = [None]

    # ISO: system area by definition, path tables from the PVD
    for i in range(16):
        known[i] = "ISO 9660 system area (LBA 0..15 by definition)"
    pvd = dev.read(16)
    lpt = struct.unpack_from("<I", pvd, 140)[0]
    mpt = struct.unpack_from(">I", pvd, 148)[0]
    ptsz = struct.unpack_from("<I", pvd, 132)[0]
    nsec = (ptsz + SECTOR - 1) // SECTOR
    for k in range(nsec):
        known[lpt + k] = "ISO 9660 L path table (PVD +140, %d bytes)" % ptsz
        known[mpt + k] = "ISO 9660 M path table (PVD +148, %d bytes)" % ptsz

    # UDF: everything from the anchor outwards
    anchors = []
    last = struct.unpack_from("<I", pvd, 80)[0] - 1
    for cand in (256, last, last - 256):
        b = dev.read(cand)
        if struct.unpack_from("<H", b, 0)[0] == 2 and \
                struct.unpack_from("<I", b, 12)[0] == cand:
            anchors.append(cand)
            known[cand] = "UDF AnchorVolumeDescriptorPointer"
            mlen, mloc, rlen, rloc = struct.unpack_from("<IIII", b, 16)
            for tag, ln, lo in (("main", mlen, mloc), ("reserve", rlen, rloc)):
                for k in range(ln // SECTOR):
                    known.setdefault(lo + k,
                                     "UDF %s volume descriptor sequence "
                                     "extent (%d sectors from the anchor at "
                                     "LBA %d)" % (tag, ln // SECTOR, cand))

    # walk the main VDS for the LVID and the partition start
    if anchors:
        b = dev.read(anchors[0])
        mlen, mloc = struct.unpack_from("<II", b, 16)
        for k in range(mlen // SECTOR):
            s = dev.read(mloc + k)
            tag = struct.unpack_from("<H", s, 0)[0]
            if tag in TAGS:
                known[mloc + k] = "UDF %s (main sequence)" % TAGS[tag]
            if tag == 6:      # LogicalVolumeDescriptor
                fsd_block = struct.unpack_from("<I", s, 248)[0]
                fsd_part = struct.unpack_from("<H", s, 252)[0]
                ilen, iloc = struct.unpack_from("<II", s, 432)
                for j in range((ilen + SECTOR - 1) // SECTOR):
                    known[iloc + j] = ("UDF logical volume integrity "
                                       "sequence (%d bytes at LBA %d)"
                                       % (ilen, iloc))
            if tag == 5:      # PartitionDescriptor
                pstart = struct.unpack_from("<I", s, 188)[0]
                known.setdefault(pstart, "UDF FileSetDescriptor "
                                 "(partition block 0, partition starts %d)"
                                 % pstart)
                part_start[0] = pstart

    rows = []
    for spec in a.gaps:
        lo, _, hi = spec.partition("-")
        lo, hi = int(lo), int(hi or lo)
        rows.append((lo, hi))

    total = spare = 0
    counts = {}
    print("every sector inside the gaps, named or declared spare")
    print()
    for lo, hi in rows:
        print("gap LBA %d..%d  (%d sectors)" % (lo, hi, hi - lo + 1))
        run_name, run_start = None, None
        for lba in range(lo, hi + 1):
            total += 1
            b = dev.read(lba)
            name = classify(b, lba, known, part_start[0], run_name)
            if name is None:
                name = "SPARE (all zero, claimed by nothing)"
                spare += 1
            counts[name.split(" (")[0]] = \
                counts.get(name.split(" (")[0], 0) + 1
            if name != run_name:
                if run_name is not None:
                    print("   %8d ..%8d  %6d  %s"
                          % (run_start, lba - 1, lba - run_start, run_name))
                run_name, run_start = name, lba
        print("   %8d ..%8d  %6d  %s"
              % (run_start, hi, hi - run_start + 1, run_name))
        print()

    print("summary, by what the sector is:")
    for k in sorted(counts, key=lambda k: -counts[k]):
        print("  %6d  %s" % (counts[k], k))
    print()
    print("sectors examined            : %d" % total)
    print("named                       : %d" % (total - spare))
    print("genuinely spare (all zero)  : %d" % spare)
    print("device reads                : %d" % dev.n)


if __name__ == "__main__":
    main()
