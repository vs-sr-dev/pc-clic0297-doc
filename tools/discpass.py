#!/usr/bin/env python3
"""discpass.py -- one full pass over the disc, through either access path.

There are two ways to read a sector on Windows and this repository needed both
before it could say anything about the medium at all:

  volume  open the volume device \\\\.\\E: and read() at a sector-aligned
          offset. This is what every inherited tool does. It goes through the
          CDFS driver and the system cache.
  spti    IOCTL_SCSI_PASS_THROUGH_DIRECT with a SCSI READ(10) command. This is
          what spti.py, toc.py and window2.py already use for their own
          purposes. It goes to the drive.

They do not agree. Measured on this disc, `\\\\.\\E:` refuses a 384-sector read
at LBA 512, a 64-sector read at LBA 1024 and a 512-sector read at LBA 2048,
reproducibly, with a Windows error and after a six-to-nine second wait --
while READ(10) returns all three in full with SCSI status 0 and no sense data.
A tool that reads through the volume path and reports the refusals as
unreadable sectors is describing the driver, not the disc.

So this tool takes the path as an argument and prints which one it used, and
the two runs over the same range are the measurement.

    python tools/discpass.py E --via spti --sha1
    python tools/discpass.py E --via volume --first 0 --last 12287
    python tools/discpass.py E --via spti --chunk 64 --last 335410

A chunk that fails is retried once at --group size, and a group that fails is
reported as a failing group. Nothing is retried sector by sector:
pc-harrypotter1-doc measured that this drive answers a failing read in units of
64 sectors, so below 64 there is no finer border to find.

Every size is a command-line argument. Nothing in this file is a constant of
any disc.
"""
import argparse
import hashlib
import os
import struct
import sys
import time

SECTOR = 2048
BS = chr(92)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class VolumeReader:
    name = "volume device, read() through the CDFS driver and system cache"

    def __init__(self, letter):
        self.f = open(BS + BS + "." + BS + letter.upper().rstrip(":") + ":",
                      "rb", buffering=0)

    def read(self, lba, n):
        try:
            self.f.seek(lba * SECTOR)
            d = self.f.read(n * SECTOR)
        except OSError as e:
            return None, "%s %s" % (e.__class__.__name__,
                                    getattr(e, "winerror", e.errno))
        if len(d) != n * SECTOR:
            return None, "short read, %d of %d bytes" % (len(d), n * SECTOR)
        return d, ""


class SptiReader:
    name = "SCSI READ(10) through IOCTL_SCSI_PASS_THROUGH_DIRECT"

    def __init__(self, letter):
        import spti
        self.spti = spti
        self.d = spti.Drive(letter)

    def read(self, lba, n):
        cdb = ([0x28, 0] + list(struct.pack(">I", lba)) + [0]
               + list(struct.pack(">H", n)) + [0])
        r = self.d.cmd(cdb, SECTOR * n, timeout=30)
        if not r["ok"] or r["status"] != 0:
            return None, ("status %d  %s  winerr %d"
                          % (r["status"], self.spti.sense_str(r["sense"]),
                             r["winerr"]))
        return r["data"], ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("--via", choices=("volume", "spti"), default="spti")
    ap.add_argument("--chunk", type=int, default=32,
                    help="sectors per read; SPTD refuses more than 32")
    ap.add_argument("--group", type=int, default=64,
                    help="re-read size when a chunk fails")
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--last", type=int, required=True, help="inclusive")
    ap.add_argument("--sha1", action="store_true")
    ap.add_argument("--report", type=float, default=30.0)
    ap.add_argument("--csv", default=None,
                    help="write one line per failing group")
    a = ap.parse_args()

    if a.via == "spti" and a.chunk > 32:
        raise SystemExit("IOCTL_SCSI_PASS_THROUGH_DIRECT refuses transfers over "
                         "64 KiB on this system: use --chunk 32 or less. "
                         "Measured by tools/xfermax.py --via spti.")
    rd = (VolumeReader if a.via == "volume" else SptiReader)(a.drive)
    h = hashlib.sha1() if a.sha1 else None

    lba = a.first
    ok_sectors = 0
    bad = []                # [first, last, reason]
    slow = []
    retried = 0
    t0 = time.time()
    last_report = t0

    def mark(first, n, why):
        if bad and bad[-1][1] == first - 1 and bad[-1][2] == why:
            bad[-1][1] = first + n - 1
        else:
            bad.append([first, first + n - 1, why])

    while lba <= a.last:
        n = min(a.chunk, a.last - lba + 1)
        t = time.time()
        d, why = rd.read(lba, n)
        dt = time.time() - t
        if d is not None:
            if h:
                h.update(d)
            ok_sectors += n
            if dt > 2.0:
                slow.append((lba, n, dt))
        elif a.group >= n:
            mark(lba, n, why)
        else:
            retried += 1
            for off in range(0, n, a.group):
                m = min(a.group, n - off)
                dd, why2 = rd.read(lba + off, m)
                if dd is not None:
                    if h:
                        h.update(dd)
                    ok_sectors += m
                else:
                    mark(lba + off, m, why2)
        lba += n
        now = time.time()
        if now - last_report >= a.report:
            sys.stderr.write("  ... LBA %d  %.1f MB ok  %d bad runs  %.0f s\n"
                             % (lba, ok_sectors * SECTOR / 1e6, len(bad),
                                now - t0))
            sys.stderr.flush()
            last_report = now

    el = time.time() - t0
    n_req = a.last - a.first + 1
    print("drive             : %s:" % a.drive.upper().rstrip(":"))
    print("access path       : %s" % rd.name)
    print("chunk / group     : %d / %d sectors" % (a.chunk, a.group))
    print("range             : LBA %d .. %d  (%d sectors, %d bytes)"
          % (a.first, a.last, n_req, n_req * SECTOR))
    print("elapsed           : %.1f s" % el)
    print("chunks re-read    : %d" % retried)
    print("readable          : %d sectors, %d bytes" % (ok_sectors, ok_sectors * SECTOR))
    print("unreadable        : %d sectors" % (n_req - ok_sectors))
    print("rate              : %.2f MB/s" % (ok_sectors * SECTOR / 1e6 / el if el else 0))
    if h:
        print("sha1(readable)    : %s" % h.hexdigest())
    print()
    if not bad:
        print("no unreadable sector in the whole range, through this path.")
    else:
        print("unreadable runs   : %d" % len(bad))
        for f, l, why in bad[:60]:
            print("    LBA %8d .. %8d  %8d sectors   %s" % (f, l, l - f + 1, why))
        if len(bad) > 60:
            print("    ... %d more runs" % (len(bad) - 60))
    if a.csv:
        with open(a.csv, "w", encoding="utf-8") as fh:
            fh.write("first,last,sectors,reason\n")
            for f, l, why in bad:
                fh.write("%d,%d,%d,%s\n" % (f, l, l - f + 1, why.replace(",", ";")))
    print()
    print("chunks slower than 2 s that nevertheless returned data: %d" % len(slow))
    for f, n, dt in slow[:20]:
        print("    LBA %8d  %4d sectors  %.2f s" % (f, n, dt))
    if len(slow) > 20:
        print("    ... %d more" % (len(slow) - 20))


if __name__ == "__main__":
    main()
