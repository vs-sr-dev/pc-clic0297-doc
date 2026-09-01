#!/usr/bin/env python3
"""cab.py - read a Microsoft cabinet (MSCF) and extract it, no dependencies.

The format is published and simple enough to read directly, which matters
here: on this disc the whole game is inside one 50 MB cabinet, and a session
that cannot open it has documented an installer rather than a game.

  CFHEADER   'MSCF', total size, offset of the file table, folder and file
             counts, flags, set id, and an optional reserved area whose three
             size fields change the size of every other structure in the file
  CFFOLDER   one per compressed stream: where its data blocks start, how many
             there are, and which compressor
  CFFILE     one per file: uncompressed size, offset within its folder's
             decompressed stream, folder index, MS-DOS date and time,
             attributes, and the name
  CFDATA     one per block: checksum, compressed size, uncompressed size

Compression 0 (store) and 1 (MSZIP) are implemented. MSZIP is raw deflate
per block behind a two-byte 'CK' signature, with the previous block's last
32 KB carried in as the dictionary, so blocks cannot be decoded out of order.
Quantum and LZX are recognised and refused rather than guessed at.

Usage:
    python tools/cab.py FILE --info
    python tools/cab.py FILE --list [--sort size|name|offset]
    python tools/cab.py FILE --census
    python tools/cab.py FILE --extract OUTDIR [--only PREFIX]
"""

import argparse
import datetime
import os
import struct
import sys
import zlib

COMPRESS = {0: "none (stored)", 1: "MSZIP", 2: "Quantum", 3: "LZX"}

ATTR = [(0x01, "RDONLY"), (0x02, "HIDDEN"), (0x04, "SYSTEM"),
        (0x20, "ARCH"), (0x40, "EXEC"), (0x80, "NAME_IS_UTF")]

HDR_FLAGS = [(0x0001, "PREV_CABINET"), (0x0002, "NEXT_CABINET"),
             (0x0004, "RESERVE_PRESENT")]


def dos_datetime(date, time):
    try:
        return datetime.datetime(
            ((date >> 9) & 0x7F) + 1980, (date >> 5) & 0x0F, date & 0x1F,
            (time >> 11) & 0x1F, (time >> 5) & 0x3F, (time & 0x1F) * 2)
    except ValueError:
        return None


def cstr(buf, off):
    end = buf.index(b"\x00", off)
    return buf[off:end], end + 1


class Cab(object):
    def __init__(self, path):
        self.path = path
        self.size = os.path.getsize(path)
        with open(path, "rb") as fh:
            self.raw = fh.read()
        self._parse()

    def _parse(self):
        b = self.raw
        if b[:4] != b"MSCF":
            raise ValueError("not a cabinet: magic is %r" % b[:4])
        (self.res1, self.cbCabinet, self.res2, self.coffFiles, self.res3,
         self.verMinor, self.verMajor, self.cFolders, self.cFiles,
         self.flags, self.setID, self.iCabinet) = struct.unpack_from(
            "<IIIIIBBHHHHH", b, 4)

        p = 36
        self.cbCFHeader = self.cbCFFolder = self.cbCFData = 0
        self.abReserve = b""
        if self.flags & 0x0004:
            self.cbCFHeader, self.cbCFFolder, self.cbCFData = \
                struct.unpack_from("<HBB", b, p)
            p += 4
            self.abReserve = b[p:p + self.cbCFHeader]
            p += self.cbCFHeader
        self.prev = self.next = None
        if self.flags & 0x0001:
            n1, p = cstr(b, p)
            d1, p = cstr(b, p)
            self.prev = (n1, d1)
        if self.flags & 0x0002:
            n2, p = cstr(b, p)
            d2, p = cstr(b, p)
            self.next = (n2, d2)

        self.folders = []
        for i in range(self.cFolders):
            coffCabStart, cCFData, typeCompress = struct.unpack_from(
                "<IHH", b, p)
            p += 8 + self.cbCFFolder
            self.folders.append({
                "index": i, "start": coffCabStart, "blocks": cCFData,
                "compress": typeCompress & 0x000F,
                "window": (typeCompress >> 8) & 0x1F,
            })

        self.files = []
        p = self.coffFiles
        for i in range(self.cFiles):
            cbFile, uoff, ifolder, date, time, attribs = struct.unpack_from(
                "<IIHHHH", b, p)
            p += 16
            name, p = cstr(b, p)
            self.files.append({
                "index": i, "size": cbFile, "uoff": uoff, "folder": ifolder,
                "date": date, "time": time, "attribs": attribs,
                "name": name.decode("utf-8" if attribs & 0x80 else "cp1252",
                                    "replace").replace("\\", "/"),
                "raw_name": name,
                "dt": dos_datetime(date, time),
            })
        self.file_table_end = p

    # ---------------------------------------------------------------- data
    def folder_blocks(self, fi):
        """Yield (compressed, cbData, cbUncomp, csum) for one folder."""
        f = self.folders[fi]
        p = f["start"]
        b = self.raw
        for _ in range(f["blocks"]):
            csum, cbData, cbUncomp = struct.unpack_from("<IHH", b, p)
            p += 8 + self.cbCFData
            yield b[p:p + cbData], cbData, cbUncomp, csum
            p += cbData

    def folder_data(self, fi):
        """Decompress one folder's whole stream."""
        f = self.folders[fi]
        c = f["compress"]
        if c == 0:
            return b"".join(blk for blk, _, _, _ in self.folder_blocks(fi))
        if c != 1:
            raise NotImplementedError(
                "folder %d uses %s; only store and MSZIP are implemented"
                % (fi, COMPRESS.get(c, c)))
        out = []
        history = b""
        for blk, cbData, cbUncomp, _ in self.folder_blocks(fi):
            if blk[:2] != b"CK":
                raise ValueError("MSZIP block without CK signature")
            d = zlib.decompressobj(-zlib.MAX_WBITS,
                                   zdict=history) if history else \
                zlib.decompressobj(-zlib.MAX_WBITS)
            chunk = d.decompress(blk[2:]) + d.flush()
            if len(chunk) != cbUncomp:
                raise ValueError("block decompressed to %d, header says %d"
                                 % (len(chunk), cbUncomp))
            out.append(chunk)
            history = (history + chunk)[-32768:]
        return b"".join(out)

    def file_bytes(self, entry, cache):
        fi = entry["folder"]
        if fi not in cache:
            cache.clear()
            cache[fi] = self.folder_data(fi)
        d = cache[fi]
        return d[entry["uoff"]:entry["uoff"] + entry["size"]]


# ------------------------------------------------------------------ output
def cmd_info(cab):
    print("=" * 72)
    print("CABINET  %s" % cab.path)
    print("=" * 72)
    print("  file size on disc          %d" % cab.size)
    print("  cbCabinet (header says)    %d   %s"
          % (cab.cbCabinet,
             "matches" if cab.cbCabinet == cab.size else "** DISAGREES **"))
    print("  version                    %d.%d" % (cab.verMajor, cab.verMinor))
    print("  folders                    %d" % cab.cFolders)
    print("  files                      %d" % cab.cFiles)
    print("  flags                      0x%04x  %s"
          % (cab.flags, ", ".join(n for m, n in HDR_FLAGS if cab.flags & m)
             or "none"))
    print("  set id                     %d" % cab.setID)
    print("  cabinet number in set      %d" % cab.iCabinet)
    print("  offset of file table       %d" % cab.coffFiles)
    print("  reserved sizes             header %d, folder %d, data %d"
          % (cab.cbCFHeader, cab.cbCFFolder, cab.cbCFData))
    if cab.abReserve:
        print("  header reserved bytes      %s" % cab.abReserve[:64].hex(" "))
    print("  reserved1/2/3              0x%08x 0x%08x 0x%08x"
          % (cab.res1, cab.res2, cab.res3))
    if cab.prev:
        print("  previous cabinet           %r" % (cab.prev,))
    if cab.next:
        print("  next cabinet               %r" % (cab.next,))
    print()
    print("-- folders")
    total_u = 0
    for f in cab.folders:
        blocks = list(cab.folder_blocks(f["index"]))
        comp = sum(b[1] for b in blocks)
        unc = sum(b[2] for b in blocks)
        total_u += unc
        print("   folder %-3d  %-14s  %6d blocks  %11d -> %11d  (%.3fx)"
              % (f["index"], COMPRESS.get(f["compress"], f["compress"]),
                 f["blocks"], comp, unc, (unc / comp) if comp else 0))
        if f["window"]:
            print("               window %d" % f["window"])
    print()
    print("  uncompressed total         %d bytes" % total_u)
    print("  compressed total           %d bytes" % cab.size)
    print("  ratio                      %.4f x" % (total_u / float(cab.size)))
    fsum = sum(f["size"] for f in cab.files)
    print("  sum of CFFILE sizes        %d bytes  %s"
          % (fsum, "matches" if fsum == total_u else
             "(%+d vs folder streams)" % (fsum - total_u)))


def cmd_list(cab, sort):
    files = list(cab.files)
    if sort == "size":
        files.sort(key=lambda e: -e["size"])
    elif sort == "name":
        files.sort(key=lambda e: e["name"].lower())
    elif sort == "offset":
        files.sort(key=lambda e: (e["folder"], e["uoff"]))
    print("%12s  %3s %12s  %-19s %-24s %s"
          % ("bytes", "fld", "offset", "date", "attribs", "name"))
    for e in files:
        at = ", ".join(n for m, n in ATTR if e["attribs"] & m)
        print("%12d  %3d %12d  %-19s %-24s %s"
              % (e["size"], e["folder"], e["uoff"],
                 e["dt"].strftime("%Y-%m-%d %H:%M:%S") if e["dt"] else "?",
                 at, e["name"]))
    print()
    print("files: %d, bytes: %d" % (len(files), sum(e["size"] for e in files)))


def cmd_census(cab):
    ext = {}
    dirs = {}
    dates = {}
    for e in cab.files:
        base = e["name"].rsplit("/", 1)[-1]
        x = ("." + base.rsplit(".", 1)[1].lower()) if "." in base else "(none)"
        n, b = ext.get(x, (0, 0))
        ext[x] = (n + 1, b + e["size"])
        d = e["name"].rsplit("/", 1)[0] if "/" in e["name"] else "(root)"
        n, b = dirs.get(d, (0, 0))
        dirs[d] = (n + 1, b + e["size"])
        k = e["dt"].strftime("%Y-%m-%d %H:%M:%S") if e["dt"] else "?"
        dates[k] = dates.get(k, 0) + 1

    total = sum(e["size"] for e in cab.files)
    print("-- by extension  (%d files, %d bytes)" % (len(cab.files), total))
    print("   %-10s %6s %14s %8s" % ("ext", "count", "bytes", "share"))
    for x, (n, b) in sorted(ext.items(), key=lambda kv: -kv[1][1]):
        print("   %-10s %6d %14d %7.2f %%" % (x, n, b, 100.0 * b / total))
    print()
    print("-- by directory")
    print("   %-46s %6s %14s %8s" % ("directory", "count", "bytes", "share"))
    for d, (n, b) in sorted(dirs.items(), key=lambda kv: -kv[1][1]):
        print("   %-46s %6d %14d %7.2f %%" % (d[:46], n, b, 100.0 * b / total))
    print()
    print("-- distinct MS-DOS timestamps: %d" % len(dates))
    for k, n in sorted(dates.items(), key=lambda kv: -kv[1])[:25]:
        print("   %-22s %d" % (k, n))
    if len(dates) > 25:
        print("   ... %d more" % (len(dates) - 25))


def cmd_extract(cab, outdir, only):
    cache = {}
    order = sorted(cab.files, key=lambda e: (e["folder"], e["uoff"]))
    n = 0
    total = 0
    for e in order:
        if only and not e["name"].lower().startswith(only.lower()):
            continue
        dest = os.path.join(outdir, e["name"].replace("/", os.sep))
        d = os.path.dirname(dest)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        data = cab.file_bytes(e, cache)
        if len(data) != e["size"]:
            print("  ** %s: got %d bytes, table says %d"
                  % (e["name"], len(data), e["size"]))
        with open(dest, "wb") as fh:
            fh.write(data)
        n += 1
        total += len(data)
    print("extracted %d files, %d bytes, to %s" % (n, total, outdir))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cab")
    ap.add_argument("--info", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--sort", default="offset",
                    choices=("size", "name", "offset"))
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--extract")
    ap.add_argument("--only")
    a = ap.parse_args()

    cab = Cab(a.cab)
    if a.info:
        cmd_info(cab)
    if a.list:
        cmd_list(cab, a.sort)
    if a.census:
        cmd_census(cab)
    if a.extract:
        cmd_extract(cab, a.extract, a.only)


if __name__ == "__main__":
    main()
