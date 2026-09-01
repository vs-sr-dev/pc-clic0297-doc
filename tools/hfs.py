#!/usr/bin/env python3
"""hfs.py -- the other filesystem: Apple partition map, HFS MDB, HFS catalog.

Windows mounts the ISO 9660 side of this disc and shows 2,374 files in four
folders. The Master Directory Block of the HFS volume that shares the same
sectors says 2,401 files in ten folders. Nothing inherited into this collection
reads HFS, so this is written from the structures up.

Everything here is addressed, never scanned. The partition map at block 0 gives
the HFS partition's start; logical block 2 of that partition is the Master
Directory Block; the MDB gives the extents of the catalog B-tree; the catalog's
header node gives the first leaf; the leaves chain forward. A scanner that hunts
for 'BD' or for record shapes would find them inside JPEG data and invent files.

    python tools/hfs.py E --map
    python tools/hfs.py E --mdb
    python tools/hfs.py E --catalog
    python tools/hfs.py E --catalog --paths
    python tools/hfs.py E --extents-file

READING THE DISC, AND WHY THIS TOOL CACHES
------------------------------------------
The drive in this machine is tired: the tenth session killed it with 60
consecutive failed reads and needed the tray to recover. This tool therefore
reads the smallest regions that answer the question -- the partition map, the
MDB, and the catalog file, which together are well under a megabyte -- and it
writes every region it reads into a cache directory. A second run costs zero
reads. Delete the cache to force a re-read.

    --cache DIR   default _work/raw
    --image FILE  read from a file instead of the drive (no drive touched)

BYTE ORDER
----------
HFS is Motorola. Every multi-byte field in the partition map, the MDB, the
B-tree nodes and the catalog records is big-endian, without exception. There is
no XFIR-style swapped variant of HFS the way there is of Director's RIFX -- the
volume was written by a Macintosh and it stayed that way.

DATES
-----
HFS timestamps count seconds from 1904-01-01 00:00:00 **local time**. There is
no time zone in an HFS volume: the number means what the clock on the Mac that
wrote it said. That is a different semantics from the ISO 9660 descriptor, which
carries an explicit GMT offset field, and the difference is the point of the
clocks chapter -- so this tool prints HFS dates without a zone suffix and never
converts them.
"""
import argparse
import os
import struct
import sys

SECTOR = 2048
BLK = 512
BS = chr(92)

# 1904-01-01 to 1970-01-01 in seconds, including 17 leap days.
HFS_EPOCH_DELTA = 2082844800


def devpath(letter):
    return BS + BS + "." + BS + letter.upper().rstrip(":") + ":"


class Source(object):
    """Byte-addressable view of the disc, with an on-disk cache.

    Reads are issued to the device in whole 2048-byte sectors, because that is
    the unit the device hands over; the caller asks in bytes. Every sector read
    is cached under DIR/<lba>.bin so that a re-run never touches the drive.
    """

    def __init__(self, drive=None, image=None, cache="_work/raw", chunk=64):
        self.image = image
        self.drive = drive
        self.cache = cache
        self.chunk = chunk
        self.reads = 0
        self.cached = 0
        self.fh = None
        if image:
            self.fh = open(image, "rb")
        else:
            if cache:
                try:
                    os.makedirs(cache)
                except OSError:
                    pass

    def _sector(self, lba):
        if self.image:
            self.fh.seek(lba * SECTOR)
            d = self.fh.read(SECTOR)
            self.reads += 1
            return d
        path = os.path.join(self.cache, "%08d.bin" % lba) if self.cache else None
        if path and os.path.exists(path):
            self.cached += 1
            with open(path, "rb") as f:
                return f.read()
        # Read a run of `chunk` sectors starting on a multiple of chunk, so that
        # a walk over a contiguous structure costs one command per chunk rather
        # than one per sector.
        base = (lba // self.chunk) * self.chunk
        # The device handle is opened once and kept. Opening and closing
        # \\.\E: for every cache miss works for a handful of reads and then
        # fails with a sharing violation, which arrives as PermissionError and
        # looks exactly like a disc problem. It is not one.
        if self.fh is None:
            self.fh = open(devpath(self.drive), "rb", buffering=0)
        # The chunked read is an optimisation, not a requirement, and it has one
        # failure mode: near the end of the volume a 64-sector run that starts
        # on a multiple of 64 asks for sectors past the last one, and the volume
        # path answers with a Windows error rather than a short buffer. That
        # arrives as PermissionError and looks exactly like a bad sector. It is
        # not one: the same sectors read fine one at a time. So a chunk that
        # fails is retried smaller, down to a single sector, before anything is
        # called unreadable.
        buf = b""
        for n in (self.chunk, 16, 4, 1):
            if n > self.chunk:
                continue
            if n == 1:
                base = lba
            try:
                self.fh.seek(base * SECTOR)
                buf = self.fh.read(n * SECTOR)
            except OSError:
                buf = b""
            self.reads += 1
            if len(buf) > (lba - base) * SECTOR:
                break
        if len(buf) <= (lba - base) * SECTOR:
            raise IOError("sector %d did not read through %s"
                          % (lba, devpath(self.drive)))
        got = len(buf) // SECTOR
        for i in range(got):
            s = buf[i * SECTOR:(i + 1) * SECTOR]
            if self.cache:
                with open(os.path.join(self.cache, "%08d.bin" % (base + i)), "wb") as f:
                    f.write(s)
            if base + i == lba:
                out = s
        return out

    def read(self, offset, length):
        """Read `length` bytes from byte `offset` of the disc."""
        out = bytearray()
        first = offset // SECTOR
        last = (offset + length - 1) // SECTOR
        for lba in range(first, last + 1):
            out += self._sector(lba)
        start = offset - first * SECTOR
        return bytes(out[start:start + length])


def hfsdate(v):
    if v == 0:
        return "(not set)"
    import datetime
    try:
        d = datetime.datetime(1904, 1, 1) + datetime.timedelta(seconds=v)
    except OverflowError:
        return "(out of range: %d)" % v
    return d.strftime("%Y-%m-%d %H:%M:%S")


def macstr(b):
    """Decode a MacRoman byte string. HFS names are MacRoman, not Latin-1."""
    return b.decode("mac_roman", "replace")


def escname(s):
    """Escape the control characters an HFS name is allowed to contain.

    An HFS file name may hold any byte but ':' -- and four names on this volume
    end in 0x0D, which on a Macintosh is a line ending. Written raw into a TSV
    they split the row in half, and a reader that skips short rows silently
    loses exactly those four files. They are escaped here, not dropped, because
    the whole point of this repository is that they exist.
    """
    out = []
    for ch in s:
        o = ord(ch)
        if o < 0x20 or o == 0x7f:
            out.append("\\x%02x" % o)
        else:
            out.append(ch)
    return "".join(out)


def pstr(b, off, cap):
    n = b[off]
    if n > cap:
        n = cap
    return macstr(b[off + 1:off + 1 + n])


# ---------------------------------------------------------------- partition map

def partition_map(src):
    """Read block 0 (the driver descriptor, 'ER') and the 'PM' entries.

    The partition map lives in 512-byte blocks, which is not the unit the device
    hands over. Block N is at byte N*512, and this reads it through Source, so
    four partition-map blocks cost one sector.
    """
    b0 = src.read(0, BLK)
    out = {"er": None, "parts": []}
    if b0[:2] == b"ER":
        bsize, bcount = struct.unpack(">HI", b0[2:8])
        out["er"] = {"block_size": bsize, "block_count": bcount,
                     "devtype": struct.unpack(">H", b0[8:10])[0],
                     "devid": struct.unpack(">H", b0[10:12])[0]}
    n = 1
    total = None
    while n < 64:
        b = src.read(n * BLK, BLK)
        if b[:2] != b"PM":
            break
        (sig, res, mapblks, pystart, pyblks) = struct.unpack(">HHIII", b[0:16])
        name = macstr(b[16:48].split(b"\0")[0])
        ptype = macstr(b[48:80].split(b"\0")[0])
        dstart, dcount = struct.unpack(">II", b[80:88])
        status = struct.unpack(">I", b[88:92])[0]
        out["parts"].append({"index": n, "map_blocks": mapblks,
                             "start": pystart, "size": pyblks,
                             "name": name, "type": ptype,
                             "data_start": dstart, "data_count": dcount,
                             "status": status})
        if total is None:
            total = mapblks
        n += 1
        if n > total:
            break
    return out


def find_hfs(src):
    pm = partition_map(src)
    for p in pm["parts"]:
        if p["type"] == "Apple_HFS":
            return p, pm
    return None, pm


# ------------------------------------------------------------------------- MDB

MDB_FIELDS = [
    ("drSigWord", ">H", 0), ("drCrDate", ">I", 2), ("drLsMod", ">I", 6),
    ("drAtrb", ">H", 10), ("drNmFls", ">H", 12), ("drVBMSt", ">H", 14),
    ("drAllocPtr", ">H", 16), ("drNmAlBlks", ">H", 18), ("drAlBlkSiz", ">I", 20),
    ("drClpSiz", ">I", 24), ("drAlBlSt", ">H", 28), ("drNxtCNID", ">I", 30),
    ("drFreeBks", ">H", 34), ("drVolBkUp", ">I", 64), ("drVSeqNum", ">H", 68),
    ("drWrCnt", ">I", 70), ("drXTClpSiz", ">I", 74), ("drCTClpSiz", ">I", 78),
    ("drNmRtDirs", ">H", 82), ("drFilCnt", ">I", 84), ("drDirCnt", ">I", 88),
    ("drVCSize", ">H", 124), ("drVBMCSize", ">H", 126), ("drCtlCSize", ">H", 128),
    ("drXTFlSize", ">I", 130), ("drCTFlSize", ">I", 146),
]


def read_mdb(src, part_start_blk):
    """MDB is logical block 2 of the partition: offset 1024 from its start."""
    base = part_start_blk * BLK + 2 * BLK
    b = src.read(base, BLK)
    m = {"_base": base}
    for name, fmt, off in MDB_FIELDS:
        m[name] = struct.unpack(fmt, b[off:off + struct.calcsize(fmt)])[0]
    m["drVN"] = pstr(b, 36, 27)
    m["drXTExtRec"] = [struct.unpack(">HH", b[134 + i * 4:138 + i * 4]) for i in range(3)]
    m["drCTExtRec"] = [struct.unpack(">HH", b[150 + i * 4:154 + i * 4]) for i in range(3)]
    m["drFndrInfo"] = b[92:124]
    return m


class Volume(object):
    def __init__(self, src, part):
        self.src = src
        self.part = part
        self.vol_byte = part["start"] * BLK
        self.mdb = read_mdb(src, part["start"])
        self.ablk = self.mdb["drAlBlkSiz"]
        self.albst = self.mdb["drAlBlSt"]

    def alloc_byte(self, ab):
        """Byte offset on the DISC of allocation block `ab` of this volume."""
        return self.vol_byte + self.albst * BLK + ab * self.ablk

    def read_extents(self, extrec, size):
        """Concatenate the extents of a fork until `size` bytes are collected."""
        out = bytearray()
        for start, count in extrec:
            if count == 0:
                continue
            need = size - len(out)
            if need <= 0:
                break
            take = min(need, count * self.ablk)
            out += self.src.read(self.alloc_byte(start), take)
        return bytes(out)

    def catalog(self):
        return self.read_extents(self.mdb["drCTExtRec"], self.mdb["drCTFlSize"])

    def extents_file(self):
        return self.read_extents(self.mdb["drXTExtRec"], self.mdb["drXTFlSize"])


# ------------------------------------------------------------------- the B-tree

def node_recs(node):
    """Return the list of record byte-strings in one B-tree node."""
    n = struct.unpack(">H", node[10:12])[0]
    size = len(node)
    offs = []
    for i in range(n + 1):
        o = struct.unpack(">H", node[size - 2 * (i + 1):size - 2 * i])[0]
        offs.append(o)
    out = []
    for i in range(n):
        a, b = offs[i], offs[i + 1]
        if a > b or b > size:
            break
        out.append(node[a:b])
    return out


def btree_header(tree, nodesize=512):
    node = tree[0:nodesize]
    r = node_recs(node)[0]
    (depth, root, nrecs, fnode, lnode, nsize, keylen, nnodes, free) = \
        struct.unpack(">HIIIIHHII", r[0:30])
    return {"depth": depth, "root": root, "nrecs": nrecs, "first_leaf": fnode,
            "last_leaf": lnode, "node_size": nsize, "key_len": keylen,
            "nodes": nnodes, "free": free}


CDR = {1: "dir", 2: "file", 3: "dirthread", 4: "filethread"}


def parse_catalog(tree, nodesize=512):
    """Walk the leaf chain and return every catalog record.

    The walk starts at the header's first-leaf pointer and follows ndFLink. It
    does NOT iterate over every node index in the file: a B-tree file contains
    index nodes, map nodes and free nodes as well, and treating them as leaves
    would double-count.
    """
    hdr = btree_header(tree, nodesize)
    ns = hdr["node_size"] or nodesize
    recs = []
    seen = set()
    node_no = hdr["first_leaf"]
    leaves = 0
    while node_no:
        if node_no in seen:
            break
        seen.add(node_no)
        node = tree[node_no * ns:(node_no + 1) * ns]
        if len(node) < 14:
            break
        flink, blink, ntype, height, nrecs = struct.unpack(">IIbBH", node[0:12])
        if ntype != -1:  # 0xFF as signed byte: leaf
            break
        leaves += 1
        for r in node_recs(node):
            if len(r) < 2:
                continue
            klen = r[0]
            parid = struct.unpack(">I", r[2:6])[0] if klen >= 5 else None
            name = pstr(r, 6, 31) if klen >= 6 else ""
            doff = 1 + klen
            if doff % 2:
                doff += 1
            d = r[doff:]
            if not d:
                continue
            t = CDR.get(d[0])
            recs.append({"type": t, "raw_type": d[0], "parent": parid,
                         "name": name, "data": d})
        node_no = flink
    hdr["leaves_walked"] = leaves
    return hdr, recs


def dirrec(d):
    (flags, val, did, cr, md, bk) = struct.unpack(">HHIIII", d[2:22])
    return {"flags": flags, "valence": val, "id": did,
            "created": cr, "modified": md, "backup": bk}


def filrec(d):
    flags = d[2]
    ftyp = macstr(d[4:8])
    creator = macstr(d[8:12])
    fndflags = struct.unpack(">H", d[12:14])[0]
    (fnum,) = struct.unpack(">I", d[20:24])
    (stblk, dlen, dphy) = struct.unpack(">HII", d[24:34])
    (rstblk, rlen, rphy) = struct.unpack(">HII", d[34:44])
    (cr, md, bk) = struct.unpack(">III", d[44:56])
    ext = [struct.unpack(">HH", d[74 + i * 4:78 + i * 4]) for i in range(3)]
    rext = [struct.unpack(">HH", d[86 + i * 4:90 + i * 4]) for i in range(3)]
    return {"flags": flags, "type": ftyp, "creator": creator,
            "finder_flags": fndflags, "id": fnum,
            "data_start": stblk, "data_len": dlen, "data_phys": dphy,
            "rsrc_start": rstblk, "rsrc_len": rlen, "rsrc_phys": rphy,
            "created": cr, "modified": md, "backup": bk,
            "data_extents": ext, "rsrc_extents": rext}


def build_paths(recs):
    """Map CNID -> full path, from the directory records."""
    dirs = {}
    for r in recs:
        if r["type"] == "dir":
            info = dirrec(r["data"])
            dirs[info["id"]] = (r["parent"], r["name"])
    dirs[1] = (0, "")  # CNID 1 is the root's parent id; 2 is the root itself

    def path_of(cnid):
        parts = []
        seen = set()
        while cnid in dirs and cnid not in seen and cnid > 1:
            seen.add(cnid)
            par, nm = dirs[cnid]
            parts.append(nm)
            cnid = par
        return "/".join(reversed(parts))
    return dirs, path_of


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive", nargs="?", default="E")
    ap.add_argument("--image")
    ap.add_argument("--cache", default="_work/raw")
    ap.add_argument("--map", action="store_true")
    ap.add_argument("--mdb", action="store_true")
    ap.add_argument("--catalog", action="store_true")
    ap.add_argument("--paths", action="store_true")
    ap.add_argument("--extents-file", action="store_true")
    ap.add_argument("--dump-catalog", help="write the raw catalog file here")
    ap.add_argument("--tsv", help="write every file record as TSV here")
    a = ap.parse_args()

    src = Source(drive=a.drive, image=a.image, cache=a.cache)
    part, pm = find_hfs(src)

    if a.map or not (a.mdb or a.catalog or a.extents_file or a.tsv or a.dump_catalog):
        er = pm["er"]
        print("block 0  driver descriptor")
        if er:
            print("  signature    ER")
            print("  block size   %d" % er["block_size"])
            print("  block count  %d  = %d bytes = %.1f sectors of 2048"
                  % (er["block_count"], er["block_count"] * BLK,
                     er["block_count"] * BLK / float(SECTOR)))
        else:
            print("  no ER signature at block 0")
        print()
        for p in pm["parts"]:
            print("block %d  partition map entry" % p["index"])
            print("  name         %r" % p["name"])
            print("  type         %r" % p["type"])
            print("  start block  %d  = byte %d = LBA %.1f"
                  % (p["start"], p["start"] * BLK, p["start"] * BLK / float(SECTOR)))
            print("  size blocks  %d  = %d bytes = %.1f sectors"
                  % (p["size"], p["size"] * BLK, p["size"] * BLK / float(SECTOR)))
            print("  status       0x%08x" % p["status"])
            print()

    if part is None:
        print("no Apple_HFS partition found")
        return

    vol = Volume(src, part)
    m = vol.mdb

    if a.mdb:
        print("Master Directory Block at byte %d (LBA %d offset %d)"
              % (m["_base"], m["_base"] // SECTOR, m["_base"] % SECTOR))
        print("  signature      %s" % ("BD" if m["drSigWord"] == 0x4244
                                       else "0x%04x" % m["drSigWord"]))
        print("  volume name    %r" % m["drVN"])
        print("  created        %s" % hfsdate(m["drCrDate"]))
        print("  modified       %s" % hfsdate(m["drLsMod"]))
        print("  backup         %s" % hfsdate(m["drVolBkUp"]))
        print("  attributes     0x%04x" % m["drAtrb"])
        print("  files total    %d" % m["drFilCnt"])
        print("  dirs total     %d" % m["drDirCnt"])
        print("  files in root  %d" % m["drNmFls"])
        print("  dirs in root   %d" % m["drNmRtDirs"])
        print("  alloc blk size %d  = %.4f sectors of 2048"
              % (m["drAlBlkSiz"], m["drAlBlkSiz"] / float(SECTOR)))
        print("  alloc blocks   %d   free %d" % (m["drNmAlBlks"], m["drFreeBks"]))
        print("  first alloc blk %d (512-byte blocks from volume start)"
              % m["drAlBlSt"])
        print("  bitmap at blk  %d" % m["drVBMSt"])
        print("  next CNID      %d" % m["drNxtCNID"])
        print("  write count    %d" % m["drWrCnt"])
        print("  catalog size   %d bytes   extents %s"
              % (m["drCTFlSize"], m["drCTExtRec"]))
        print("  extents size   %d bytes   extents %s"
              % (m["drXTFlSize"], m["drXTExtRec"]))
        fi = m["drFndrInfo"]
        print("  finder info    %s" % (" ".join("%02x" % c for c in fi)))
        bl = struct.unpack(">I", fi[0:4])[0]
        print("                 blessed system folder CNID: %d" % bl)
        print()
        print("  volume starts at byte %d (LBA %.1f)"
              % (vol.vol_byte, vol.vol_byte / float(SECTOR)))
        print("  first alloc block at byte %d (LBA %.4f)"
              % (vol.alloc_byte(0), vol.alloc_byte(0) / float(SECTOR)))
        print("  catalog at byte %d (LBA %.4f)"
              % (vol.alloc_byte(m["drCTExtRec"][0][0]),
                 vol.alloc_byte(m["drCTExtRec"][0][0]) / float(SECTOR)))

    if a.catalog or a.tsv or a.dump_catalog:
        cat = vol.catalog()
        if a.dump_catalog:
            with open(a.dump_catalog, "wb") as f:
                f.write(cat)
            print("catalog written: %s  %d bytes" % (a.dump_catalog, len(cat)))
        hdr, recs = parse_catalog(cat)
        dirs, path_of = build_paths(recs)
        nf = sum(1 for r in recs if r["type"] == "file")
        nd = sum(1 for r in recs if r["type"] == "dir")
        nt = sum(1 for r in recs if r["type"] in ("dirthread", "filethread"))
        if a.catalog:
            print()
            print("catalog B-tree")
            print("  file size      %d bytes = %d nodes of %d"
                  % (len(cat), len(cat) // hdr["node_size"], hdr["node_size"]))
            print("  depth          %d" % hdr["depth"])
            print("  root node      %d" % hdr["root"])
            print("  first leaf     %d   last leaf %d"
                  % (hdr["first_leaf"], hdr["last_leaf"]))
            print("  leaf records   %d (declared)" % hdr["nrecs"])
            print("  nodes total    %d   free %d" % (hdr["nodes"], hdr["free"]))
            print("  key length     %d" % hdr["key_len"])
            print()
            print("  leaves walked  %d" % hdr["leaves_walked"])
            print("  records read   %d" % len(recs))
            print("    directories  %d" % nd)
            print("    files        %d" % nf)
            print("    threads      %d" % nt)
            print()
            print("  MDB says       %d files, %d directories"
                  % (m["drFilCnt"], m["drDirCnt"]))
            print("  catalog says   %d files, %d directories" % (nf, nd))
            print("  difference     files %+d, directories %+d"
                  % (nf - m["drFilCnt"], nd - m["drDirCnt"]))
        if a.paths:
            print()
            print("%-8s %-6s %-6s %10s %10s  %s"
                  % ("cnid", "type", "creat", "data", "rsrc", "path"))
            rows = []
            for r in recs:
                if r["type"] != "file":
                    continue
                f = filrec(r["data"])
                p = path_of(r["parent"])
                rows.append((escname(p + "/" + r["name"]), f))
            for p, f in sorted(rows):
                print("%-8d %-6s %-6s %10d %10d  %s"
                      % (f["id"], f["type"], f["creator"], f["data_len"],
                         f["rsrc_len"], p))
        if a.tsv:
            # filStBlk is a HINT field, and on this volume Toast left it zero on
            # all 2,401 records. An address taken from it puts every file at the
            # first allocation block, which makes an alignment test come out
            # perfect for a reason that has nothing to do with the disc. The
            # authoritative address is the first extent of filExtRec; nblocks
            # counts how many of the three extent slots are used, so a fork that
            # needed the extents overflow file is visible rather than silently
            # truncated.
            with open(a.tsv, "w", encoding="utf-8") as fo:
                fo.write("cnid\tpath\ttype\tcreator\tdata_len\tdata_ab\t"
                         "rsrc_len\trsrc_ab\tcreated\tmodified\tdata_lba\t"
                         "data_extents\trsrc_extents\n")
                for r in recs:
                    if r["type"] != "file":
                        continue
                    f = filrec(r["data"])
                    p = escname(path_of(r["parent"]) + "/" + r["name"])
                    dext = [e for e in f["data_extents"] if e[1]]
                    rext = [e for e in f["rsrc_extents"] if e[1]]
                    ab = dext[0][0] if dext else -1
                    rab = rext[0][0] if rext else -1
                    lba = vol.alloc_byte(ab) / float(SECTOR) if dext else -1
                    fo.write("%d\t%s\t%s\t%s\t%d\t%d\t%d\t%d\t%s\t%s\t%s\t%s\t%s\n"
                             % (f["id"], p, f["type"], f["creator"],
                                f["data_len"], ab,
                                f["rsrc_len"], rab,
                                hfsdate(f["created"]), hfsdate(f["modified"]),
                                ("%.4f" % lba) if lba >= 0 else "",
                                ";".join("%d+%d" % e for e in dext),
                                ";".join("%d+%d" % e for e in rext)))
            print("wrote %s" % a.tsv)
            fo2 = a.tsv.replace(".tsv", "-dirs.tsv")
            with open(fo2, "w", encoding="utf-8") as f2:
                f2.write("cnid\tpath\tvalence\tcreated\tmodified\n")
                for r in recs:
                    if r["type"] != "dir":
                        continue
                    d = dirrec(r["data"])
                    f2.write("%d\t%s\t%d\t%s\t%s\n"
                             % (d["id"], escname(path_of(d["id"])), d["valence"],
                                hfsdate(d["created"]), hfsdate(d["modified"])))
            print("wrote %s" % fo2)

    if a.extents_file:
        xt = vol.extents_file()
        hdr, _ = parse_catalog(xt) if False else (btree_header(xt), None)
        print()
        print("extents overflow B-tree")
        print("  file size      %d bytes" % len(xt))
        print("  depth          %d" % hdr["depth"])
        print("  leaf records   %d" % hdr["nrecs"])
        print("  nodes total    %d   free %d" % (hdr["nodes"], hdr["free"]))
        print()
        print("  A non-zero record count here means at least one fork on this")
        print("  volume needed more than three extents, i.e. it is fragmented.")

    print()
    print("[source: %s   sector reads issued %d, served from cache %d]"
          % (a.image or devpath(a.drive), src.reads, src.cached))


if __name__ == "__main__":
    main()
