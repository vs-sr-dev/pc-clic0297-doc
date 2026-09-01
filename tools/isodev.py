#!/usr/bin/env python3
"""isodev.py -- ISO 9660 / Joliet reader that walks a *device*, not an image.

This is the adaptation of pc-1000miglia-doc/tools/iso9660.py demanded by this
session's material. That tool mmap's an image file. Here there is no image:
there is `\\.\E:`, a volume device that

  * cannot be mmap'd usefully,
  * must be read in whole 2048-byte sectors at sector-aligned offsets,
  * has about ten thousand sectors in the middle that do not read at all.

So the sector accessor is a caching reader that returns None on failure rather
than raising, and every walk records which sectors it touched. All ISO
metadata (descriptors, path tables, directory extents) turns out to be below
the unreadable region, so the walk itself never trips over it -- but the code
does not assume that, it measures it.

Record layout being asserted, per ECMA-119 9.1, offsets within a record:

    0   1   length of directory record
    1   1   extended attribute record length
    2   8   extent, both-endian LBA
   10   8   data length, both-endian
   18   7   recording date: y-1900, month, day, hour, minute, second, tz
   25   1   file flags
   26   1   file unit size
   27   1   interleave gap size
   28   4   volume sequence number, both-endian
   32   1   length of file identifier
   33   n   file identifier

Usage:
    python tools/isodev.py E --vd
    python tools/isodev.py E --pathtable [--joliet]
    python tools/isodev.py E --tree [--joliet]
    python tools/isodev.py E --extents [--joliet]     LBA-ordered extent map
    python tools/isodev.py E --gaps                   what is not in a file
    python tools/isodev.py E --tz                     timezone offset census
    python tools/isodev.py E --compare                ISO tree vs Joliet tree
    python tools/isodev.py E --verify-record NAME
"""
import os
import sys

BS = chr(92)
NUL = bytes([0x00])
SECTOR = 2048


class Device:
    # 2026-08-31, pc-clic11-doc: this tool was written when there was no image
    # to read, only a device. On CLIC 11 there is an image -- one linear pass
    # over the whole disc, taken once -- and reading the image instead of the
    # drive is both faster and kinder. If the first argument names a file that
    # exists, it is opened as an image; otherwise it is a drive letter, and the
    # original behaviour is unchanged.
    def __init__(self, letter):
        if os.path.exists(letter) and os.path.isfile(letter):
            self.path = letter
        else:
            self.path = BS + BS + "." + BS + letter.upper() + ":"
        self.f = open(self.path, "rb")
        self.cache = {}
        self.reads = 0
        self.fails = 0

    def sector(self, lba):
        if lba in self.cache:
            return self.cache[lba]
        try:
            self.f.seek(lba * SECTOR)
            b = self.f.read(SECTOR)
            self.reads += 1
            if len(b) != SECTOR:
                b = None
        except OSError:
            self.fails += 1
            b = None
        self.cache[lba] = b
        return b

    def read(self, lba, nbytes):
        out = bytearray()
        n = (nbytes + SECTOR - 1) // SECTOR
        for i in range(n):
            s = self.sector(lba + i)
            if s is None:
                return None
            out += s
        return bytes(out[:nbytes])

    def close(self):
        self.f.close()


def both32(b):
    """Both-endian 32-bit; returns (le, be, agree)."""
    le = int.from_bytes(b[0:4], "little")
    be = int.from_bytes(b[4:8], "big")
    return le, be, le == be


class Rec:
    __slots__ = ("length", "ealen", "lba", "size", "dt", "raw_dt", "flags",
                 "unit", "gap", "volseq", "idlen", "ident", "name", "path",
                 "is_dir", "off")

    def __repr__(self):
        return "<Rec %s lba=%d size=%d>" % (self.path, self.lba, self.size)


def parse_record(b, off, joliet):
    ln = b[off]
    if ln == 0:
        return None
    r = Rec()
    r.off = off
    r.length = ln
    r.ealen = b[off + 1]
    r.lba = both32(b[off + 2:off + 10])[0]
    r.size = both32(b[off + 10:off + 18])[0]
    r.raw_dt = bytes(b[off + 18:off + 25])
    tz = r.raw_dt[6]
    r.dt = (1900 + r.raw_dt[0], r.raw_dt[1], r.raw_dt[2], r.raw_dt[3],
            r.raw_dt[4], r.raw_dt[5], tz if tz < 128 else tz - 256)
    r.flags = b[off + 25]
    r.unit = b[off + 26]
    r.gap = b[off + 27]
    r.volseq = both32(b[off + 28:off + 36])[0]
    r.idlen = b[off + 32]
    r.ident = bytes(b[off + 33:off + 33 + r.idlen])
    r.is_dir = bool(r.flags & 0x02)
    if r.idlen == 1 and r.ident in (NUL, b"\x01"):
        r.name = "." if r.ident == NUL else ".."
    elif joliet:
        try:
            r.name = r.ident.decode("utf-16-be")
        except UnicodeDecodeError:
            r.name = repr(r.ident)
    else:
        r.name = r.ident.decode("latin-1")
        if ";" in r.name:
            r.name = r.name.split(";")[0]
    return r


def find_vds(dev):
    out = {}
    lba = 16
    while lba < 64:
        b = dev.sector(lba)
        if b is None or b[1:6] != b"CD001":
            break
        out.setdefault(b[0], []).append((lba, b))
        if b[0] == 255:
            break
        lba += 1
    return out


def root_of(dev, joliet):
    vds = find_vds(dev)
    want = 2 if joliet else 1
    if want not in vds:
        raise SystemExit("no descriptor of type %d" % want)
    lba, b = vds[want][0]
    rd = b[156:190]
    r = parse_record(b, 156, joliet)
    r.name = ""
    r.path = ""
    return r, lba, b


def walk(dev, joliet=False):
    """Depth-first walk. Returns (files, dirs, dirsectors)."""
    root, vdlba, vd = root_of(dev, joliet)
    files, dirs, dirsectors = [], [], []
    stack = [root]
    dirs.append(root)
    seen = set()
    while stack:
        d = stack.pop(0)
        if d.lba in seen:
            continue
        seen.add(d.lba)
        nsec = (d.size + SECTOR - 1) // SECTOR
        for i in range(nsec):
            dirsectors.append(d.lba + i)
        data = dev.read(d.lba, d.size)
        if data is None:
            print("  !! directory extent at LBA %d is UNREADABLE" % d.lba,
                  file=sys.stderr)
            continue
        off = 0
        while off < len(data):
            if off % SECTOR == 0 and data[off] == 0:
                off += SECTOR - (off % SECTOR) if off % SECTOR else SECTOR
                continue
            if data[off] == 0:
                off += SECTOR - (off % SECTOR)
                continue
            r = parse_record(data, off, joliet)
            if r is None:
                break
            if r.name not in (".", ".."):
                r.path = (d.path + "/" + r.name) if d.path else r.name
                if r.is_dir:
                    dirs.append(r)
                    stack.append(r)
                else:
                    files.append(r)
            off += r.length
    return files, dirs, dirsectors, vdlba, vd


def cmd_vd(dev, args):
    vds = find_vds(dev)
    for t in sorted(vds):
        for lba, b in vds[t]:
            print("sector %-3d type %-3d  %r  version %d" % (lba, t, b[1:6], b[6]))
    print()
    tot = sum(len(v) for v in vds.values())
    print("%d descriptors, types %s" % (tot, sorted(vds)))
    if 1 in vds and len(vds[1]) > 1:
        a = vds[1][0][1]
        c = vds[1][1][1]
        n = sum(1 for i in range(SECTOR) if a[i] != c[i])
        print("two type-1 descriptors: %d of %d bytes differ" % (n, SECTOR))


def cmd_pathtable(dev, args):
    joliet = "--joliet" in args
    vds = find_vds(dev)
    b = vds[2 if joliet else 1][0][1]
    size = int.from_bytes(b[132:136], "little")
    lloc = int.from_bytes(b[140:144], "little")
    mloc = int.from_bytes(b[148:152], "big")
    print("path table size %d bytes, L at LBA %d, M at LBA %d"
          % (size, lloc, mloc))
    data = dev.read(lloc, size)
    off = 0
    n = 0
    while off < size:
        ln = data[off]
        if ln == 0:
            break
        ea = data[off + 1]
        lba = int.from_bytes(data[off + 2:off + 6], "little")
        parent = int.from_bytes(data[off + 6:off + 8], "little")
        ident = data[off + 8:off + 8 + ln]
        if joliet:
            try:
                nm = ident.decode("utf-16-be")
            except UnicodeDecodeError:
                nm = repr(ident)
        else:
            nm = ident.decode("latin-1")
        n += 1
        print("  %3d  lba %7d  parent %3d  %r" % (n, lba, parent, nm))
        off += 8 + ln + (ln & 1)
    print()
    print("%d path table records, %d bytes consumed of %d" % (n, off, size))


def cmd_tree(dev, args):
    joliet = "--joliet" in args
    files, dirs, ds, _, _ = walk(dev, joliet)
    for d in sorted(dirs, key=lambda r: r.path):
        print("D %-60s lba %7d size %8d" % (d.path or "/", d.lba, d.size))
    for f in sorted(files, key=lambda r: r.path):
        print("  %-60s lba %7d size %10d" % (f.path, f.lba, f.size))
    print()
    print("%d files, %d directories (root counted)" % (len(files), len(dirs)))
    print("total file bytes %d" % sum(f.size for f in files))


def cmd_extents(dev, args):
    joliet = "--joliet" in args
    files, dirs, dirsectors, vdlba, vd = walk(dev, joliet)
    volsize = int.from_bytes(vd[80:84], "little")
    items = []
    for f in files:
        nsec = (f.size + SECTOR - 1) // SECTOR
        items.append((f.lba, nsec, f.size, f.path, "F"))
    for d in dirs:
        nsec = (d.size + SECTOR - 1) // SECTOR
        items.append((d.lba, nsec, d.size, (d.path or "/") + "  [dir extent]", "D"))
    items.sort()
    print("LBA-ordered extent map, %d entries (%d files + %d directory extents)"
          % (len(items), len(files), len(dirs)))
    print()
    print("%9s %7s %11s %11s  %s" % ("LBA", "sectors", "bytes", "slack", "name"))
    prev_end = 0
    gaps = []
    for lba, nsec, size, path, kind in items:
        if lba > prev_end:
            gaps.append((prev_end, lba - 1, lba - prev_end))
            print("%9s %7s %11s %11s  ---- GAP of %d sectors (LBA %d..%d) ----"
                  % ("", "", "", "", lba - prev_end, prev_end, lba - 1))
        slack = nsec * SECTOR - size
        print("%9d %7d %11d %11d  %s" % (lba, nsec, size, slack, path))
        prev_end = max(prev_end, lba + nsec)
    if volsize > prev_end:
        gaps.append((prev_end, volsize - 1, volsize - prev_end))
        print("%9s %7s %11s %11s  ---- TAIL GAP of %d sectors (LBA %d..%d) ----"
              % ("", "", "", "", volsize - prev_end, prev_end, volsize - 1))
    print()
    print("gaps larger than 1 sector, biggest first:")
    for a, b, n in sorted(gaps, key=lambda g: -g[2]):
        if n > 1:
            print("   LBA %7d .. %7d   %7d sectors   %12d bytes"
                  % (a, b, n, n * SECTOR))
    print()
    fs = sum((f.size + SECTOR - 1) // SECTOR for f in files)
    ds_ = sum((d.size + SECTOR - 1) // SECTOR for d in dirs)
    fb = sum(f.size for f in files)
    print("volume                        %9d sectors  %12d bytes"
          % (volsize, volsize * SECTOR))
    print("file payload                  %9d sectors  %12d bytes"
          % (fs, fb))
    print("file slack (allocated - used) %9s           %12d bytes"
          % ("", fs * SECTOR - fb))
    print("directory extents             %9d sectors  %12d bytes"
          % (ds_, ds_ * SECTOR))
    print("system area (LBA 0..15)       %9d sectors  %12d bytes" % (16, 16 * SECTOR))
    print("volume descriptors            %9d sectors  %12d bytes" % (4, 4 * SECTOR))
    tot_gap = sum(n for _, _, n in gaps)
    print("unclaimed (gaps)              %9d sectors  %12d bytes"
          % (tot_gap, tot_gap * SECTOR))
    print()
    print("check: %d + %d + %d = %d, volume is %d, difference %d"
          % (fs, ds_, tot_gap, fs + ds_ + tot_gap, volsize,
             volsize - (fs + ds_ + tot_gap)))
    print()
    print("bytes outside any file: %d - %d = %d"
          % (volsize * SECTOR, fb, volsize * SECTOR - fb))


def cmd_gaps(dev, args):
    cmd_extents(dev, args)


def cmd_tz(dev, args):
    import collections
    out = collections.Counter()
    detail = collections.defaultdict(list)
    for joliet in (False, True):
        files, dirs, _, vdlba, vd = walk(dev, joliet)
        tag = "joliet" if joliet else "iso"
        for r in files + dirs:
            out[(tag, r.dt[6])] += 1
            if len(detail[(tag, r.dt[6])]) < 6:
                detail[(tag, r.dt[6])].append(r.path or "/")
        # descriptor date offsets
        for off, name in ((813, "creation"), (830, "modification")):
            o = vd[off + 16]
            print("%s descriptor (sector %d) %s: %r offset byte %d"
                  % (tag, vdlba, name, vd[off:off + 16].decode("latin-1"), o))
    print()
    print("directory-record GMT offset census (offset is in 15-minute units):")
    for (tag, tz), n in sorted(out.items()):
        print("  %-7s offset %3d (UTC%+g)  %5d records   e.g. %s"
              % (tag, tz, tz * 0.25, n, ", ".join(detail[(tag, tz)][:3])))
    print()
    tot = sum(n for (t, _), n in out.items() if t == "iso")
    print("ISO namespace: %d records total" % tot)
    kinds = set(tz for (t, tz) in out if t == "iso")
    print("distinct offsets in the ISO namespace: %s" % sorted(kinds))
    if len(kinds) == 1:
        print("=> the offset is universal across every directory record.")


def cmd_compare(dev, args):
    fi, di, _, _, _ = walk(dev, False)
    fj, dj, _, _, _ = walk(dev, True)
    print("ISO    : %d files, %d dirs, %d bytes"
          % (len(fi), len(di), sum(f.size for f in fi)))
    print("Joliet : %d files, %d dirs, %d bytes"
          % (len(fj), len(dj), sum(f.size for f in fj)))
    ei = {(f.lba, f.size) for f in fi}
    ej = {(f.lba, f.size) for f in fj}
    print()
    print("extents only in ISO   : %d" % len(ei - ej))
    for x in sorted(ei - ej)[:10]:
        print("   ", x)
    print("extents only in Joliet: %d" % len(ej - ei))
    for x in sorted(ej - ei)[:10]:
        print("   ", x)
    ni = {f.path.upper() for f in fi}
    nj = {f.path.upper() for f in fj}
    print()
    print("names differing case-insensitively, ISO only  : %d" % len(ni - nj))
    for x in sorted(ni - nj)[:20]:
        print("   ", x)
    print("names differing case-insensitively, Joliet only: %d" % len(nj - ni))
    for x in sorted(nj - ni)[:20]:
        print("   ", x)
    print()
    print("longest Joliet name: %d chars"
          % max(len(f.name) for f in fj))
    print("names longer than 8.3 in Joliet: %d"
          % sum(1 for f in fj if len(f.name.rsplit(".", 1)[0]) > 8))


def cmd_verify_record(dev, args):
    want = args[args.index("--verify-record") + 1].lower()
    files, dirs, _, _, _ = walk(dev, False)
    for r in files + dirs:
        if r.name.lower() == want or (r.path or "").lower().endswith(want):
            break
    else:
        raise SystemExit("no record named %r" % want)
    print("record for %r, %d bytes, at offset %d in its directory extent"
          % (r.path, r.length, r.off))
    print()
    fields = [
        (0, 1, "length of directory record", r.length),
        (1, 1, "extended attribute length", r.ealen),
        (2, 8, "extent, both-endian LBA", r.lba),
        (10, 8, "data length, both-endian", r.size),
        (18, 7, "recording date", r.dt),
        (25, 1, "file flags", "0x%02x" % r.flags),
        (26, 1, "file unit size", r.unit),
        (27, 1, "interleave gap", r.gap),
        (28, 8, "volume sequence, both-endian", r.volseq),
        (32, 1, "length of file identifier", r.idlen),
        (33, r.idlen, "file identifier", r.ident),
    ]
    used = 0
    for off, ln, name, val in fields:
        print("  +%-3d %2d  %-30s %s" % (off, ln, name, val))
        used = max(used, off + ln)
    print()
    print("  fields consume %d bytes, record declares %d, %d byte(s) of padding"
          % (used, r.length, r.length - used))
    print("  raw date bytes: %s" % r.raw_dt.hex(" "))


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    letter = args[0]
    dev = Device(letter)
    try:
        if "--vd" in args:
            cmd_vd(dev, args)
        elif "--pathtable" in args:
            cmd_pathtable(dev, args)
        elif "--tree" in args:
            cmd_tree(dev, args)
        elif "--extents" in args or "--gaps" in args:
            cmd_extents(dev, args)
        elif "--tz" in args:
            cmd_tz(dev, args)
        elif "--compare" in args:
            cmd_compare(dev, args)
        elif "--verify-record" in args:
            cmd_verify_record(dev, args)
        else:
            raise SystemExit(__doc__)
    finally:
        sys.stderr.write("[device: %d sector reads, %d failures, %d cached]\n"
                         % (dev.reads, dev.fails, len(dev.cache)))
        dev.close()


if __name__ == "__main__":
    main()
