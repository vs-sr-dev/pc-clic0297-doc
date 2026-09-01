#!/usr/bin/env python3
"""iso9660.py -- ISO 9660 / Joliet reader for this repository.

Descended from pc-mystictowers-doc/tools/iso9660.py, rewritten here for three
reasons that disc did not raise:

  1. this image is 506 MB, so it is mmap'd rather than read() into a bytes
     object;
  2. this image has a Joliet supplementary descriptor, so there are *two*
     namespaces and they can disagree -- `--compare` is the whole point;
  3. the directory-record dates on this disc look impossible, so every date
     is carried around with its seven raw bytes attached and `--dates`
     prints them. A date parser you cannot audit is not a measurement.

Layout being asserted, per ECMA-119 9.1, offsets within a directory record:

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

`--verify-record` re-derives that layout on one named record and prints the
byte-by-byte accounting, so the offset-18 claim is checkable and not asserted.

Usage:
    python tools/iso9660.py IMAGE --vd
    python tools/iso9660.py IMAGE --pathtable [--joliet]
    python tools/iso9660.py IMAGE --tree [--joliet]
    python tools/iso9660.py IMAGE --dates [--joliet]
    python tools/iso9660.py IMAGE --compare
    python tools/iso9660.py IMAGE --conform
    python tools/iso9660.py IMAGE --sha1 [--joliet]
    python tools/iso9660.py IMAGE --gaps

A 2,352-byte-per-sector image (CloneCD .img, MODE1/2352 or MODE2/2352
BIN) is detected by its sync pattern and read through RawSectorImage,
which presents the user data of each sector as a flat 2,048-byte-sector
volume. No cooking step is needed.
    python tools/iso9660.py IMAGE --verify-record NAME
    python tools/iso9660.py IMAGE --extract OUTDIR [--only PREFIX] [--joliet]
"""
import hashlib
import mmap
import os
import re
import struct
import sys

SECTOR = 2048


class RawDisc(object):
    """Read-only random access to a physical CD-ROM through the Windows
    device namespace, presented with the same slicing interface as an mmap so
    every mode of this tool works on a real disc as well as on an image file.

    Reads must be sector-aligned on a device handle, so this rounds every
    request out to whole 2,048-byte sectors and caches what it has read. A
    scratched disc will raise on the sectors it cannot read, and the caller
    finds out rather than silently receiving zeros."""

    SECTOR = 2048

    def __init__(self, path):
        import ctypes
        import ctypes.wintypes as wt
        self.ctypes = ctypes
        self.k = ctypes.windll.kernel32
        self.k.CreateFileW.restype = ctypes.c_void_p
        self.k.SetFilePointerEx.argtypes = [
            ctypes.c_void_p, ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong), ctypes.c_ulong]
        self.k.ReadFile.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
            ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
        self.h = self.k.CreateFileW(path, 0x80000000, 3, None, 3, 0, None)
        if self.h in (None, -1, 0xFFFFFFFFFFFFFFFF):
            raise OSError("CreateFileW(%r) failed, error %d" % (
                path, ctypes.GetLastError()))
        self.wt = wt
        self.cache = {}
        self.errors = set()
        self._len = None

    def __len__(self):
        if self._len is None:
            # IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C
            ctypes = self.ctypes
            out = ctypes.c_longlong(0)
            ret = self.wt.DWORD()
            ok = self.k.DeviceIoControl(
                ctypes.c_void_p(self.h), 0x0007405C, None, 0,
                ctypes.byref(out), 8, ctypes.byref(ret), None)
            self._len = int(out.value) if ok else 0
        return self._len

    def sector(self, n):
        if n in self.cache:
            return self.cache[n]
        ctypes = self.ctypes
        buf = ctypes.create_string_buffer(self.SECTOR)
        got = self.wt.DWORD()
        newpos = ctypes.c_longlong(0)
        self.k.SetFilePointerEx(ctypes.c_void_p(self.h),
                                n * self.SECTOR, ctypes.byref(newpos), 0)
        ok = self.k.ReadFile(ctypes.c_void_p(self.h), buf, self.SECTOR,
                             ctypes.byref(got), None)
        if not ok or got.value != self.SECTOR:
            self.errors.add(n)
            raise IOError("sector %d unreadable (error %d)" % (
                n, ctypes.GetLastError()))
        b = buf.raw
        if len(self.cache) < 40000:
            self.cache[n] = b
        return b

    def __getitem__(self, k):
        if isinstance(k, int):
            return self.sector(k // self.SECTOR)[k % self.SECTOR]
        start, stop = k.start or 0, k.stop
        if stop is None:
            stop = len(self)
        first, last = start // self.SECTOR, (stop - 1) // self.SECTOR
        out = bytearray()
        for n in range(first, last + 1):
            out += self.sector(n)
        off = start - first * self.SECTOR
        return bytes(out[off:off + (stop - start)])

    def close(self):
        self.k.CloseHandle(self.ctypes.c_void_p(self.h))


class RawSectorImage(object):
    """A 2,352-byte-per-sector CD image, presented as if it were a plain ISO.

    A CloneCD .img (or any BIN from a MODE2/2352 or MODE1/2352 cue) holds
    whole physical sectors: sync, header, mode byte, and for Mode 2 a
    subheader, all ahead of the user data, and EDC/ECC behind it. ISO 9660
    lives only in the user data, so this class maps a logical byte offset
    (what the filesystem thinks) onto a physical one (what the file holds),
    per sector, using each sector's own mode and form byte rather than one
    global assumption.

      mode 1        user data at offset 16, 2,048 bytes
      mode 2 form 1 user data at offset 24, 2,048 bytes
      mode 2 form 2 user data at offset 24, 2,324 bytes -- not addressable as
                    a 2,048-byte logical sector, so it reads back as zeros
                    and is counted in .form2

    Sectors are cached in blocks so that walking a directory tree does not
    re-read the same sector once per record.

    Written for pc-grandefratello-doc, whose disc arrived as a CloneCD set
    rather than as an image: the two earlier discs in this collection were
    cooked ISOs and this path did not exist. Cooking works too, but it throws
    away the mode byte, the subheader, the EDC and the ECC -- which is to say
    it throws away every question about the disc as a disc."""

    SECTOR = 2048
    RAW = 2352
    SYNC = b"\x00" + b"\xff" * 10 + b"\x00"

    def __init__(self, mm):
        self.mm = mm
        self.sectors = len(mm) // self.RAW
        self.block = 256
        self.cache = {}
        self.form2 = 0
        self.mode0 = 0

    def __len__(self):
        return self.sectors * self.SECTOR

    def _load(self, blk):
        if blk in self.cache:
            return self.cache[blk]
        first = blk * self.block
        n = min(self.block, self.sectors - first)
        raw = self.mm[first * self.RAW:(first + n) * self.RAW]
        out = []
        for i in range(n):
            sec = raw[i * self.RAW:(i + 1) * self.RAW]
            mode = sec[15]
            if mode == 1:
                out.append(sec[16:2064])
            elif mode == 2:
                if sec[18] & 0x20:
                    self.form2 += 1
                    out.append(b"\x00" * self.SECTOR)
                else:
                    out.append(sec[24:2072])
            else:
                self.mode0 += 1
                out.append(b"\x00" * self.SECTOR)
        buf = b"".join(out)
        if len(self.cache) > 512:
            self.cache.clear()
        self.cache[blk] = buf
        return buf

    def sector(self, n):
        blk, i = divmod(n, self.block)
        buf = self._load(blk)
        return buf[i * self.SECTOR:(i + 1) * self.SECTOR]

    def __getitem__(self, k):
        if isinstance(k, int):
            return self.sector(k // self.SECTOR)[k % self.SECTOR]
        start = k.start or 0
        stop = len(self) if k.stop is None else min(k.stop, len(self))
        if stop <= start:
            return b""
        first, last = start // self.SECTOR, (stop - 1) // self.SECTOR
        fb, lb = first // self.block, last // self.block
        out = bytearray()
        for blk in range(fb, lb + 1):
            out += self._load(blk)
        off = start - fb * self.block * self.SECTOR
        return bytes(out[off:off + (stop - start)])

    def close(self):
        pass


def looks_raw(fh):
    """A 2352-byte-per-sector image opens with the CD sync pattern and holds
    a whole number of raw sectors. Both tests, not either."""
    size = os.fstat(fh.fileno()).st_size
    if size % 2352:
        return False
    fh.seek(0)
    head = fh.read(16)
    fh.seek(0)
    return head[:12] == RawSectorImage.SYNC


def open_image(path):
    """An image file, or a raw drive.

    Pass a bare drive specification such as ``E:`` to read the physical disc
    in that drive instead of an image file. Writing the Windows device path
    on the command line is avoided deliberately: this shell rewrites anything
    that looks like a path, and the backslashes do not survive."""
    if re.match(r"^[A-Za-z]:$", path) or path.startswith(chr(92) * 2):
        if re.match(r"^[A-Za-z]:$", path):
            path = chr(92) * 2 + "." + chr(92) + path
        d = RawDisc(path)
        return d, d
    fh = open(path, "rb")
    mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
    if looks_raw(fh):
        return fh, RawSectorImage(mm)
    return fh, mm


def dec_datetime(b):
    """The 17-byte ASCII date used in volume descriptors."""
    raw = bytes(b[:16])
    off = struct.unpack_from("b", b, 16)[0]
    if raw == b"0" * 16 or raw == bytes(16):
        return None, off, raw
    try:
        t = raw.decode("ascii")
        s = "%s-%s-%s %s:%s:%s.%s" % (t[0:4], t[4:6], t[6:8], t[8:10],
                                      t[10:12], t[12:14], t[14:16])
    except Exception:
        s = repr(raw)
    return s, off, raw


def dir_datetime(b):
    """The 7-byte binary date on a directory record.

    Returns (text, tz, raw7). The text is NOT sanitised: if the month byte
    says 230 this prints 230. Silently clamping is how a disc's real
    contents become a tool's opinion.
    """
    y, mo, d, h, mi, s = b[0], b[1], b[2], b[3], b[4], b[5]
    off = struct.unpack_from("b", b, 6)[0]
    return ("%04d-%02d-%02d %02d:%02d:%02d" % (1900 + y, mo, d, h, mi, s),
            off, bytes(b[:7]))


def date_is_valid(raw7):
    """True if the seven bytes describe a date that exists."""
    y, mo, d, h, mi, s = raw7[0], raw7[1], raw7[2], raw7[3], raw7[4], raw7[5]
    tz = struct.unpack_from("b", raw7, 6)[0]
    if not (1 <= mo <= 12):
        return False
    if not (1 <= d <= 31):
        return False
    if h > 23 or mi > 59 or s > 59:
        return False
    if not (-48 <= tz <= 52):
        return False
    return True


def read_vds(mm):
    vds = []
    sec = 16
    while (sec + 1) * SECTOR <= len(mm):
        b = mm[sec * SECTOR:(sec + 1) * SECTOR]
        if b[1:6] != b"CD001":
            break
        vds.append((sec, b[0], b))
        if b[0] == 255:
            break
        sec += 1
    return vds


def pick(vds, joliet):
    """Return the descriptor to walk: type 2 if --joliet, else type 1."""
    want = 2 if joliet else 1
    for sec, t, b in vds:
        if t == want:
            return sec, b
    raise SystemExit("no volume descriptor of type %d" % want)


def decode_name(raw, joliet):
    if joliet:
        try:
            return raw.decode("utf-16-be")
        except Exception:
            return raw.decode("latin-1")
    return raw.decode("latin-1")


def walk(mm, sector, length, joliet, path="/", out=None, depth=0, seen=None):
    if out is None:
        out = []
    if seen is None:
        seen = set()
    if sector in seen:
        return out
    seen.add(sector)
    blob = mm[sector * SECTOR:sector * SECTOR + length]
    p = 0
    while p < len(blob):
        rlen = blob[p]
        if rlen == 0:
            p = ((p // SECTOR) + 1) * SECTOR
            if p >= len(blob):
                break
            continue
        if p + rlen > len(blob):
            break
        rec = blob[p:p + rlen]
        nlen = rec[32]
        raw = bytes(rec[33:33 + nlen])
        ts, tz, raw7 = dir_datetime(rec[18:25])
        flags = rec[25]
        isdir = bool(flags & 0x02)
        if raw == b"\x00":
            pretty = "."
        elif raw == b"\x01":
            pretty = ".."
        else:
            pretty = decode_name(raw, joliet)
        if pretty not in (".", ".."):
            e = dict(path=path, name=pretty, rawname=raw,
                     extent=struct.unpack_from("<I", rec, 2)[0],
                     size=struct.unpack_from("<I", rec, 10)[0],
                     time=ts, tz=tz, raw7=raw7, flags=flags, isdir=isdir,
                     depth=depth, xa=rec[1], reclen=rlen,
                     recoff=sector * SECTOR + p)
            out.append(e)
            if isdir:
                walk(mm, e["extent"], e["size"], joliet,
                     path + pretty + "/", out, depth + 1, seen)
        p += rlen
    return out


def tree_of(mm, vds, joliet):
    _sec, b = pick(vds, joliet)
    root_ext = struct.unpack_from("<I", b, 158)[0]
    root_len = struct.unpack_from("<I", b, 166)[0]
    return walk(mm, root_ext, root_len, joliet)


# ---------------------------------------------------------------- reports

def cmd_vd(mm, vds):
    print("image size       : %d bytes = %d sectors of %d  (whole: %s)" % (
        len(mm), len(mm) // SECTOR, SECTOR, len(mm) % SECTOR == 0))
    print("descriptors      : %d" % len(vds))
    names = {0: "boot record", 1: "primary", 2: "supplementary/enhanced",
             3: "partition", 255: "terminator"}
    for sec, t, b in vds:
        print("   sector %3d  type %3d  %s" % (sec, t, names.get(t, "?")))
    for sec, t, b in vds:
        if t not in (1, 2):
            continue
        print()
        print("=== descriptor at sector %d, type %d ===" % (sec, t))
        jol = (t == 2)
        esc = bytes(b[88:120]).rstrip(b"\x00 ")
        for label, lo, hi in (("system identifier", 8, 40),
                              ("volume identifier", 40, 72),
                              ("volume set identifier", 190, 318),
                              ("publisher identifier", 318, 446),
                              ("data preparer identifier", 446, 574),
                              ("application identifier", 574, 702),
                              ("copyright file identifier", 702, 739),
                              ("abstract file identifier", 739, 776),
                              ("bibliographic file identifier", 776, 813)):
            raw = bytes(b[lo:hi])
            if jol:
                try:
                    txt = raw.decode("utf-16-be")
                except Exception:
                    txt = raw.decode("latin-1")
            else:
                txt = raw.decode("latin-1")
            txt = txt.replace("\x00", "").strip()
            print("  %-30s: %r%s" % (label, txt, "" if txt else "   (blank)"))
        if jol:
            print("  %-30s: %r" % ("escape sequences", esc))
        print("  %-30s: %d sectors = %d bytes" % (
            "volume space size",
            struct.unpack_from("<I", b, 80)[0],
            struct.unpack_from("<I", b, 80)[0] * SECTOR))
        print("  %-30s: %d" % ("volume set size",
                               struct.unpack_from("<H", b, 120)[0]))
        print("  %-30s: %d" % ("volume sequence number",
                               struct.unpack_from("<H", b, 124)[0]))
        print("  %-30s: %d" % ("logical block size",
                               struct.unpack_from("<H", b, 128)[0]))
        print("  %-30s: %d bytes at sector %d (L) / %d (M)" % (
            "path table",
            struct.unpack_from("<I", b, 132)[0],
            struct.unpack_from("<I", b, 140)[0],
            struct.unpack_from(">I", b, 148)[0]))
        for i, lab in enumerate(("creation", "modification",
                                 "expiration", "effective")):
            s, off, raw = dec_datetime(b[813 + i * 17:813 + i * 17 + 17])
            print("  %-30s: %-26s GMT%+d  raw %r" % (
                lab + " date", s if s else "(unset)", off, raw))
        print("  %-30s: %d" % ("file structure version", b[881]))
        rd = b[156:190]
        ts, tz, raw7 = dir_datetime(rd[18:25])
        print("  %-30s: extent %d, %d bytes, %s GMT%+d" % (
            "root directory record", struct.unpack_from("<I", rd, 2)[0],
            struct.unpack_from("<I", rd, 10)[0], ts, tz))
        print("  %-30s: %s" % ("root date raw",
                               " ".join("%02X" % x for x in raw7)))
        tail = bytes(b[883:1395])
        print("  %-30s: %s" % ("application use (512 B)",
                               "all zero" if not any(tail)
                               else repr(tail[:64])))


def cmd_pathtable(mm, vds, joliet):
    _sec, b = pick(vds, joliet)
    size = struct.unpack_from("<I", b, 132)[0]
    sec = struct.unpack_from("<I", b, 140)[0]
    blob = mm[sec * SECTOR:sec * SECTOR + size]
    print("L path table at sector %d, %d bytes  (%s namespace)" % (
        sec, size, "Joliet" if joliet else "primary"))
    p = n = 0
    while p + 8 <= len(blob):
        nlen = blob[p]
        if nlen == 0:
            break
        extent = struct.unpack_from("<I", blob, p + 2)[0]
        parent = struct.unpack_from("<H", blob, p + 6)[0]
        raw = bytes(blob[p + 8:p + 8 + nlen])
        n += 1
        print("  %3d  parent %3d  extent %7d  xa %d  %r" % (
            n, parent, extent, blob[p + 1], decode_name(raw, joliet)))
        p += 8 + nlen + (nlen & 1)
    print("entries: %d" % n)


def cmd_tree(mm, entries, joliet, sha1=False):
    files = [e for e in entries if not e["isdir"]]
    dirs = [e for e in entries if e["isdir"]]
    print("namespace: %s" % ("Joliet" if joliet else "primary"))
    print("%-78s %11s %9s  %-21s %s" % ("path", "bytes", "extent",
                                        "recorded", "tz"))
    for e in sorted(entries, key=lambda x: (x["path"].upper(),
                                            x["name"].upper())):
        full = e["path"] + e["name"] + ("/" if e["isdir"] else "")
        line = "%-78s %11s %9d  %-21s %+d" % (
            full, "" if e["isdir"] else e["size"], e["extent"],
            e["time"], e["tz"])
        if sha1 and not e["isdir"]:
            h = hashlib.sha1()
            off = e["extent"] * SECTOR
            rem = e["size"]
            while rem > 0:
                n = min(rem, 1 << 20)
                h.update(mm[off:off + n])
                off += n
                rem -= n
            line += "  " + h.hexdigest()
        print(line)
    print()
    print("directories : %d" % len(dirs))
    print("files       : %d" % len(files))
    print("file bytes  : %d" % sum(e["size"] for e in files))
    print("file sectors: %d" % sum((e["size"] + SECTOR - 1) // SECTOR
                                   for e in files))
    print("image bytes : %d" % len(mm))


def cmd_dates(entries):
    from collections import Counter
    c = Counter()
    for e in entries:
        c[(e["time"], e["tz"], e["raw7"])] += 1
    print("distinct directory-record timestamps: %d over %d records" % (
        len(c), len(entries)))
    print()
    print("%-21s %5s %6s  %-23s %s" % ("as-printed", "tz", "count",
                                       "raw seven bytes", "valid?"))
    for (ts, tz, raw7), n in sorted(c.items(), key=lambda kv: -kv[1]):
        print("%-21s %+5d %6d  %-23s %s" % (
            ts, tz, n, " ".join("%02X" % x for x in raw7),
            "yes" if date_is_valid(raw7) else "NO"))
    print()
    bad = [e for e in entries if not date_is_valid(e["raw7"])]
    print("records with an impossible date: %d of %d (%.2f %%)" % (
        len(bad), len(entries), 100.0 * len(bad) / max(1, len(entries))))
    if bad:
        print()
        print("first ten, with the full directory record:")
        for e in bad[:10]:
            print("  %s%s" % (e["path"], e["name"]))
            print("    record at image offset %d, %d bytes" % (
                e["recoff"], e["reclen"]))
            print("    date bytes at rec+18 : %s" % " ".join(
                "%02X" % x for x in e["raw7"]))


def cmd_compare(mm, vds):
    pri = tree_of(mm, vds, False)
    jol = tree_of(mm, vds, True)
    print("primary namespace : %d entries (%d files, %d dirs)" % (
        len(pri), sum(1 for e in pri if not e["isdir"]),
        sum(1 for e in pri if e["isdir"])))
    print("Joliet  namespace : %d entries (%d files, %d dirs)" % (
        len(jol), sum(1 for e in jol if not e["isdir"]),
        sum(1 for e in jol if e["isdir"])))
    pb = sum(e["size"] for e in pri if not e["isdir"])
    jb = sum(e["size"] for e in jol if not e["isdir"])
    print("primary file bytes: %d" % pb)
    print("Joliet  file bytes: %d   (delta %d)" % (jb, jb - pb))
    pe = {}
    for e in pri:
        if not e["isdir"]:
            pe.setdefault(e["extent"], []).append(e["path"] + e["name"])
    je = {}
    for e in jol:
        if not e["isdir"]:
            je.setdefault(e["extent"], []).append(e["path"] + e["name"])
    print()
    print("extents in primary only : %d" % len(set(pe) - set(je)))
    print("extents in Joliet only  : %d" % len(set(je) - set(pe)))
    both = set(pe) & set(je)
    print("extents in both         : %d" % len(both))
    diff = []
    for x in sorted(both):
        a = pe[x][0]
        b = je[x][0]
        if a != b:
            diff.append((x, a, b))
    print("of which the two namespaces spell differently: %d" % len(diff))
    casefold = [t for t in diff if t[1].upper() == t[2].upper()]
    real = [t for t in diff if t[1].upper() != t[2].upper()]
    print("  ... differing only by letter case          : %d" % len(casefold))
    print("  ... differing by more than case            : %d" % len(real))
    print()
    print("date bytes identical in both namespaces for every shared extent: %s" % (
        all(next(e["raw7"] for e in pri if e["extent"] == x and not e["isdir"])
            == next(e["raw7"] for e in jol if e["extent"] == x and not e["isdir"])
            for x in sorted(both)[:400])))
    print()
    for x, a, b in (real or diff)[:60]:
        print("  extent %7d" % x)
        print("     primary: %s" % a)
        print("     joliet : %s" % b)
    if len(diff) > 60:
        print("  ... %d more" % (len(diff) - 60))
    print()
    dp = {}
    for e in pri:
        if e["raw7"] != next((f["raw7"] for f in jol
                              if f["extent"] == e["extent"]), e["raw7"]):
            dp[e["extent"]] = 1
    print("entries whose date differs between namespaces: %d" % len(dp))


def cmd_verify_record(mm, vds, want):
    """Re-derive the directory-record layout on one named record."""
    for joliet in (False, True):
        entries = tree_of(mm, vds, joliet)
        hits = [e for e in entries if e["name"].upper().startswith(want.upper())]
        if not hits:
            continue
        e = hits[0]
        rec = mm[e["recoff"]:e["recoff"] + e["reclen"]]
        print("=== %s namespace: %s%s ===" % (
            "Joliet" if joliet else "primary", e["path"], e["name"]))
        print("record at image offset %d (sector %d + %d), %d bytes" % (
            e["recoff"], e["recoff"] // SECTOR, e["recoff"] % SECTOR,
            e["reclen"]))
        print(" ".join("%02X" % x for x in rec))
        print()
        cursor = 0

        def field(n, label, shown):
            nonlocal cursor
            print("  +%-3d %-3d %-30s %s" % (cursor, n, label, shown))
            cursor += n

        field(1, "length of directory record", "%d" % rec[0])
        field(1, "extended attribute length", "%d" % rec[1])
        le = struct.unpack_from("<I", rec, 2)[0]
        be = struct.unpack_from(">I", rec, 6)[0]
        field(8, "extent, both-endian",
              "LE %d / BE %d  %s" % (le, be, "AGREE" if le == be else "DISAGREE"))
        le = struct.unpack_from("<I", rec, 10)[0]
        be = struct.unpack_from(">I", rec, 14)[0]
        field(8, "data length, both-endian",
              "LE %d / BE %d  %s" % (le, be, "AGREE" if le == be else "DISAGREE"))
        d = rec[18:25]
        field(7, "recording date (7 bytes)",
              "%s -> %s" % (" ".join("%02X" % x for x in d),
                            dir_datetime(d)[0]))
        field(1, "file flags", "0x%02X" % rec[25])
        field(1, "file unit size", "%d" % rec[26])
        field(1, "interleave gap size", "%d" % rec[27])
        le = struct.unpack_from("<H", rec, 28)[0]
        be = struct.unpack_from(">H", rec, 30)[0]
        field(4, "volume sequence, both-endian",
              "LE %d / BE %d  %s" % (le, be, "AGREE" if le == be else "DISAGREE"))
        field(1, "length of file identifier", "%d" % rec[32])
        field(rec[32], "file identifier", repr(bytes(rec[33:33 + rec[32]])))
        pad = rec[0] - cursor
        print("  +%-3d %-3d %-30s %s" % (
            cursor, pad, "padding / system use",
            repr(bytes(rec[cursor:])) if pad > 0 else "(none)"))
        print()
        print("  accounted: %d + %d padding = %d = declared record length %s" % (
            cursor, pad, cursor + pad,
            "OK" if cursor + pad == rec[0] else "MISMATCH"))
        print("  the two both-endian fields agreeing is the proof that the")
        print("  cursor is aligned; a shifted read would break both.")
        print()


def cmd_conform(mm, vds):
    """How far the primary namespace is from ISO 9660, and how far Joliet is
    from Joliet. WinISO's output is measured against the standards it claims."""
    pri = tree_of(mm, vds, False)
    jol = tree_of(mm, vds, True)
    dchar = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
    stats = dict(total=0, no_version=0, name_gt8=0, ext_gt3=0, dots=0,
                 space=0, bad_char=0, dir_name_gt8=0, dir_dot=0, level1=0)
    bad_examples = {}
    for e in pri:
        stats["total"] += 1
        n = e["name"]
        if e["isdir"]:
            if len(n) > 8:
                stats["dir_name_gt8"] += 1
                bad_examples.setdefault("dir_name_gt8", n)
            if "." in n:
                stats["dir_dot"] += 1
                bad_examples.setdefault("dir_dot", n)
        else:
            if ";" not in n:
                stats["no_version"] += 1
                bad_examples.setdefault("no_version", n)
            base = n.split(";")[0]
            if base.count(".") > 1:
                stats["dots"] += 1
                bad_examples.setdefault("dots", n)
            stem, _, ext = base.partition(".")
            if len(stem) > 8:
                stats["name_gt8"] += 1
                bad_examples.setdefault("name_gt8", n)
            if len(ext) > 3:
                stats["ext_gt3"] += 1
                bad_examples.setdefault("ext_gt3", n)
            if len(stem) <= 8 and len(ext) <= 3:
                stats["level1"] += 1
        if " " in n:
            stats["space"] += 1
            bad_examples.setdefault("space", n)
        if set(n) - dchar - set(".;"):
            stats["bad_char"] += 1
            bad_examples.setdefault("bad_char", n)
    print("=== primary namespace, measured against ISO 9660 ===")
    print("entries examined                       : %d" % stats["total"])
    print("files with no ';1' version suffix      : %d" % stats["no_version"])
    print("file stems longer than 8 characters    : %d" % stats["name_gt8"])
    print("extensions longer than 3 characters    : %d" % stats["ext_gt3"])
    print("names with more than one dot           : %d" % stats["dots"])
    print("names containing a space               : %d" % stats["space"])
    print("names with a non-d-character           : %d" % stats["bad_char"])
    print("directory names longer than 8 chars    : %d" % stats["dir_name_gt8"])
    print("directory names containing a dot       : %d" % stats["dir_dot"])
    print("files that would pass ISO 9660 level 1 : %d" % stats["level1"])
    for k, v in sorted(bad_examples.items()):
        print("   first %-24s: %r" % (k, v))
    print()
    print("=== is the primary namespace just Joliet uppercased? ===")
    pmap = {}
    for e in pri:
        pmap[e["extent"], e["size"], e["isdir"]] = e["path"] + e["name"]
    same = diff = miss = 0
    examples = []
    for e in jol:
        k = (e["extent"], e["size"], e["isdir"])
        if k not in pmap:
            miss += 1
            continue
        a = pmap[k]
        b = (e["path"] + e["name"]).upper()
        if a == b:
            same += 1
        else:
            diff += 1
            if len(examples) < 20:
                examples.append((a, b))
    print("primary path == upper(joliet path)     : %d" % same)
    print("differs                                : %d" % diff)
    print("no counterpart                         : %d" % miss)
    for a, b in examples:
        print("   primary        %s" % a)
        print("   upper(joliet)  %s" % b)
    print()
    print("=== Joliet, measured against Joliet ===")
    over64 = [e for e in jol if len(e["name"]) > 64]
    print("Joliet names longer than 64 characters : %d" % len(over64))
    depth = max(e["depth"] for e in jol)
    print("deepest directory level (root = 0)     : %d" % depth)
    print("  (ISO 9660 allows 8 levels; Joliet's own limit is also 8)")
    deep = sorted(jol, key=lambda e: -e["depth"])[:3]
    for e in deep:
        print("   level %d  %s%s" % (e["depth"], e["path"], e["name"]))
    print()
    zero = [e for e in pri if not e["isdir"] and e["size"] == 0]
    print("zero-length files                      : %d" % len(zero))
    for e in zero:
        print("   extent %d  %s%s" % (e["extent"], e["path"], e["name"]))


def cmd_gaps(mm, vds):
    entries = tree_of(mm, vds, False)
    jol = tree_of(mm, vds, True)
    total = len(mm) // SECTOR
    used = bytearray(total)
    for s in range(0, 16):
        used[s] = 1
    for sec, t, b in vds:
        used[sec] = 1
    for _sec, b in ((pick(vds, False)), (pick(vds, True))):
        for off in (140, 144):
            s = struct.unpack_from("<I", b, off)[0]
            n = (struct.unpack_from("<I", b, 132)[0] + SECTOR - 1) // SECTOR
            for i in range(s, min(s + n, total)):
                if i:
                    used[i] = 1
        for off in (148, 152):
            s = struct.unpack_from(">I", b, off)[0]
            n = (struct.unpack_from("<I", b, 132)[0] + SECTOR - 1) // SECTOR
            for i in range(s, min(s + n, total)):
                if i:
                    used[i] = 1
    for e in entries + jol:
        n = (e["size"] + SECTOR - 1) // SECTOR
        for s in range(e["extent"], min(e["extent"] + n, total)):
            used[s] = 1
    runs = []
    i = 0
    while i < total:
        if not used[i]:
            j = i
            while j < total and not used[j]:
                j += 1
            runs.append((i, j - i))
            i = j
        else:
            i += 1
    print("image sectors     : %d" % total)
    print("sectors claimed   : %d" % sum(used))
    print("sectors unclaimed : %d" % (total - sum(used)))
    print("unclaimed runs    : %d" % len(runs))
    for s, n in runs[:40]:
        blob = mm[s * SECTOR:(s + n) * SECTOR]
        nz = "all zero" if not any(blob) else "NON-ZERO"
        print("   sector %7d  x%-7d  %-8s  %s" % (
            s, n, nz, " ".join("%02X" % x for x in blob[:16])))
    if len(runs) > 40:
        print("   ... %d more runs" % (len(runs) - 40))


def cmd_extract(mm, entries, outdir, only):
    n = 0
    total = 0
    for e in entries:
        if e["isdir"]:
            continue
        full = (e["path"] + e["name"]).lstrip("/")
        if only and not full.upper().startswith(only.upper()):
            continue
        clean = full.split(";")[0]
        dest = os.path.join(outdir, clean.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        off = e["extent"] * SECTOR
        with open(dest, "wb") as fh:
            rem = e["size"]
            while rem > 0:
                k = min(rem, 1 << 22)
                fh.write(mm[off:off + k])
                off += k
                rem -= k
        n += 1
        total += e["size"]
    print("extracted %d files, %d bytes, to %s" % (n, total, outdir))


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
    if len(argv) < 3:
        raise SystemExit(__doc__)
    fh, mm = open_image(argv[1])
    joliet = "--joliet" in argv
    vds = read_vds(mm)
    try:
        if "--vd" in argv:
            cmd_vd(mm, vds)
        elif "--pathtable" in argv:
            cmd_pathtable(mm, vds, joliet)
        elif "--compare" in argv:
            cmd_compare(mm, vds)
        elif "--conform" in argv:
            cmd_conform(mm, vds)
        elif "--gaps" in argv:
            cmd_gaps(mm, vds)
        elif "--verify-record" in argv:
            cmd_verify_record(mm, vds, argv[argv.index("--verify-record") + 1])
        elif "--dates" in argv:
            cmd_dates(tree_of(mm, vds, joliet))
        elif "--extract" in argv:
            only = argv[argv.index("--only") + 1] if "--only" in argv else None
            cmd_extract(mm, tree_of(mm, vds, joliet),
                        argv[argv.index("--extract") + 1], only)
        elif "--tree" in argv or "--sha1" in argv:
            cmd_tree(mm, tree_of(mm, vds, joliet), joliet, "--sha1" in argv)
        else:
            raise SystemExit(__doc__)
    finally:
        mm.close()
        fh.close()


if __name__ == "__main__":
    main(sys.argv)
