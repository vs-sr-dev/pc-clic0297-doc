#!/usr/bin/env python3
"""spti.py -- talk to the drive in SCSI, through IOCTL_SCSI_PASS_THROUGH_DIRECT.

Five repositories have carried `subch.py` without ever getting a disc under it,
and every one of them left "raw access via SPTI" as an open question. This is
the attempt. It is deliberately not a subchannel reader: this disc is a DVD,
and the CD-only `READ CD` (0xBE) command is not the interesting one here.
What is interesting is that four sources disagree about how many sectors this
disc has, and exactly one of them can be asked directly.

    python tools/spti.py E                 # inquiry, capacity, DVD structure
    python tools/spti.py E --read 671663   # READ(10) one sector, raw
    python tools/spti.py E --read 671660 --count 8
    python tools/spti.py E --cache         # the drive's caching mode page

Commands issued:
    0x12 INQUIRY                     who the drive says it is
    0x46 GET CONFIGURATION           the current profile (CD-ROM? DVD-ROM?)
    0x25 READ CAPACITY(10)           the drive's own last-LBA
    0xAD READ DISC STRUCTURE fmt 0   the DVD physical format information,
                                     which carries the start and end physical
                                     sector numbers of the data area
    0x28 READ(10)                    a sector, bypassing the Win32 file length
    0x5A MODE SENSE(10) page 0x08    the caching page, including prefetch
"""
import argparse
import ctypes
import ctypes.wintypes as w
import struct
import sys

BS = chr(92)
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x0004D014

SCSI_IOCTL_DATA_OUT = 0
SCSI_IOCTL_DATA_IN = 1
SCSI_IOCTL_DATA_UNSPECIFIED = 2


class SPTD(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.c_ushort),
        ("ScsiStatus", ctypes.c_ubyte),
        ("PathId", ctypes.c_ubyte),
        ("TargetId", ctypes.c_ubyte),
        ("Lun", ctypes.c_ubyte),
        ("CdbLength", ctypes.c_ubyte),
        ("SenseInfoLength", ctypes.c_ubyte),
        ("DataIn", ctypes.c_ubyte),
        ("DataTransferLength", ctypes.c_ulong),
        ("TimeOutValue", ctypes.c_ulong),
        ("DataBuffer", ctypes.c_void_p),
        ("SenseInfoOffset", ctypes.c_ulong),
        ("Cdb", ctypes.c_ubyte * 16),
    ]


class SPTDWB(ctypes.Structure):
    _fields_ = [("sptd", SPTD), ("filler", ctypes.c_ulong),
                ("sense", ctypes.c_ubyte * 32)]


SENSE_KEYS = {
    0: "NO SENSE", 1: "RECOVERED ERROR", 2: "NOT READY", 3: "MEDIUM ERROR",
    4: "HARDWARE ERROR", 5: "ILLEGAL REQUEST", 6: "UNIT ATTENTION",
    7: "DATA PROTECT", 8: "BLANK CHECK", 11: "ABORTED COMMAND",
}
PROFILES = {
    0x0008: "CD-ROM", 0x0009: "CD-R", 0x000A: "CD-RW",
    0x0010: "DVD-ROM", 0x0011: "DVD-R sequential", 0x0012: "DVD-RAM",
    0x0013: "DVD-RW restricted", 0x0014: "DVD-RW sequential",
    0x001A: "DVD+RW", 0x001B: "DVD+R", 0x002A: "DVD+RW DL", 0x002B: "DVD+R DL",
    0x0040: "BD-ROM", 0x0041: "BD-R SRM", 0x0043: "BD-RE",
}
BOOK = {0: "DVD-ROM", 1: "DVD-RAM", 2: "DVD-R", 3: "DVD-RW",
        9: "DVD+RW", 10: "DVD+R"}


class Drive:
    def __init__(self, letter):
        k = ctypes.windll.kernel32
        path = BS + BS + "." + BS + letter.rstrip(":") + ":"
        self.h = None
        for access in (GENERIC_READ | GENERIC_WRITE, GENERIC_READ):
            h = k.CreateFileW(path, access, FILE_SHARE_READ | FILE_SHARE_WRITE,
                              None, OPEN_EXISTING, 0, None)
            if h != INVALID_HANDLE_VALUE:
                self.h = h
                self.access = "read+write" if access != GENERIC_READ else "read only"
                break
        if self.h is None:
            raise OSError("cannot open %s: error %d" % (path, k.GetLastError()))
        self.k = k

    def cmd(self, cdb, datalen=0, direction=SCSI_IOCTL_DATA_IN, timeout=20):
        p = SPTDWB()
        p.sptd.Length = ctypes.sizeof(SPTD)
        p.sptd.CdbLength = len(cdb)
        p.sptd.SenseInfoLength = 32
        p.sptd.DataIn = direction if datalen else SCSI_IOCTL_DATA_UNSPECIFIED
        p.sptd.DataTransferLength = datalen
        p.sptd.TimeOutValue = timeout
        buf = ctypes.create_string_buffer(datalen) if datalen else None
        p.sptd.DataBuffer = ctypes.cast(buf, ctypes.c_void_p) if buf else None
        p.sptd.SenseInfoOffset = SPTDWB.sense.offset
        for i, b in enumerate(cdb):
            p.sptd.Cdb[i] = b
        ret = w.DWORD()
        ok = self.k.DeviceIoControl(self.h, IOCTL_SCSI_PASS_THROUGH_DIRECT,
                                    ctypes.byref(p), ctypes.sizeof(p),
                                    ctypes.byref(p), ctypes.sizeof(p),
                                    ctypes.byref(ret), None)
        err = self.k.GetLastError()
        sense = bytes(p.sense)
        return {"ok": bool(ok), "winerr": err, "status": p.sptd.ScsiStatus,
                "data": buf.raw if buf else b"", "sense": sense}


def sense_str(s):
    if not s or s[0] == 0:
        return "(none)"
    key = s[2] & 0xF
    return "response %02x  key %d %s  asc %02x ascq %02x" % (
        s[0] & 0x7F, key, SENSE_KEYS.get(key, "?"), s[12], s[13])


def show(label, r):
    print("  %-26s status=%d win=%d  sense: %s"
          % (label, r["status"], r["winerr"], sense_str(r["sense"])))


def hexdump(d, n=64, base=0):
    for o in range(0, min(len(d), n), 16):
        row = d[o:o + 16]
        print("      %5d  %-47s  %s" % (base + o, " ".join("%02x" % x for x in row),
                                        "".join(chr(x) if 32 <= x < 127 else "." for x in row)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("--read", type=int)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--cache", action="store_true")
    ap.add_argument("--hex", action="store_true")
    a = ap.parse_args()

    d = Drive(a.drive)
    print("handle opened %s" % d.access)
    print()

    print("=== INQUIRY (0x12) ===")
    r = d.cmd([0x12, 0, 0, 0, 96, 0], 96)
    show("INQUIRY", r)
    if r["status"] == 0 and len(r["data"]) >= 36:
        b = r["data"]
        print("      peripheral type   : 0x%02x" % (b[0] & 0x1F))
        print("      vendor            : %r" % b[8:16].decode("latin-1").strip())
        print("      product           : %r" % b[16:32].decode("latin-1").strip())
        print("      revision          : %r" % b[32:36].decode("latin-1").strip())

    print()
    print("=== GET CONFIGURATION (0x46), current profile ===")
    r = d.cmd([0x46, 0, 0, 0, 0, 0, 0, 0, 32, 0], 32)
    show("GET CONFIGURATION", r)
    if r["status"] == 0 and len(r["data"]) >= 8:
        prof = struct.unpack_from(">H", r["data"], 6)[0]
        print("      current profile   : 0x%04x  %s" % (prof, PROFILES.get(prof, "?")))

    print()
    print("=== READ CAPACITY(10) (0x25) ===")
    r = d.cmd([0x25, 0, 0, 0, 0, 0, 0, 0, 0, 0], 8)
    show("READ CAPACITY", r)
    if r["status"] == 0 and len(r["data"]) == 8:
        last, blk = struct.unpack(">II", r["data"])
        print("      last LBA          : %d" % last)
        print("      block length      : %d" % blk)
        print("      sector count      : %d  (last LBA + 1)" % (last + 1))
        print("      bytes             : %d" % ((last + 1) * blk))

    print()
    print("=== READ DISC STRUCTURE (0xAD) format 00, physical format information ===")
    r = d.cmd([0xAD, 0, 0, 0, 0, 0, 0, 0, 0x08, 0x00, 0, 0], 2052)
    show("READ DISC STRUCTURE", r)
    if r["status"] == 0 and len(r["data"]) >= 20:
        b = r["data"][4:]
        book = b[0] >> 4
        print("      book type         : %d (%s)  part version %d"
              % (book, BOOK.get(book, "?"), b[0] & 0xF))
        print("      disc size         : %d   max rate code %d" % (b[1] >> 4, b[1] & 0xF))
        print("      layers            : %d   track path %d   layer type %d"
              % (((b[2] >> 5) & 3) + 1, (b[2] >> 4) & 1, b[2] & 0xF))
        start = struct.unpack(">I", b[4:8])[0] & 0xFFFFFF
        end = struct.unpack(">I", b[8:12])[0] & 0xFFFFFF
        endl0 = struct.unpack(">I", b[12:16])[0] & 0xFFFFFF
        print("      data area start PSN : 0x%06x = %d" % (start, start))
        print("      data area end   PSN : 0x%06x = %d" % (end, end))
        print("      layer 0 end     PSN : 0x%06x = %d" % (endl0, endl0))
        if end >= start:
            n = end - start + 1
            print("      physical sectors in data area: %d" % n)
            print("      that is LBA 0 .. %d" % (n - 1))
            print("      divisible by 16 (one DVD ECC block): %s  (%d blocks%s)"
                  % (n % 16 == 0, n // 16, "" if n % 16 == 0 else " + %d" % (n % 16)))
        if a.hex:
            hexdump(r["data"], 32)

    if a.cache:
        print()
        print("=== MODE SENSE(10) (0x5A) page 0x08, caching ===")
        r = d.cmd([0x5A, 0, 0x08, 0, 0, 0, 0, 0, 64, 0], 64)
        show("MODE SENSE caching", r)
        if r["status"] == 0:
            hexdump(r["data"], 40)

    if a.read is not None:
        print()
        print("=== READ(10) (0x28) LBA %d, %d sector(s) ===" % (a.read, a.count))
        for i in range(a.count):
            lba = a.read + i
            cdb = [0x28, 0] + list(struct.pack(">I", lba)) + [0] + \
                  list(struct.pack(">H", 1)) + [0]
            r = d.cmd(cdb, 2048)
            got = len(r["data"]) if r["status"] == 0 else 0
            nz = sum(1 for x in r["data"] if x) if r["status"] == 0 else -1
            print("  LBA %7d  status=%d  bytes=%d  non-zero=%s   sense: %s"
                  % (lba, r["status"], got, nz if nz >= 0 else "-",
                     sense_str(r["sense"])))
            if r["status"] == 0 and a.hex:
                hexdump(r["data"], 64)


if __name__ == "__main__":
    main()
