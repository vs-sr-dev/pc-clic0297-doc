#!/usr/bin/env python3
"""pathdiff.py -- read the same sector both ways and compare the answers.

Every tool inherited by this repository reads sectors by opening the volume
device `\\\\.\\E:` and calling read() at a sector-aligned offset. A handful --
spti.py, toc.py, window2.py -- instead send a SCSI READ(10) through
IOCTL_SCSI_PASS_THROUGH_DIRECT. Nobody had ever compared the two on the same
sector, because on every previous disc there was no reason to think they could
disagree.

On this disc they disagree, and the disagreement is not subtle: sectors that
READ(10) answers with `key 3 MEDIUM ERROR, asc 11 ascq 00` -- unrecovered read
error -- are returned by the volume path as 2,048 bytes of plausible data in
five milliseconds.

This tool takes a list of LBAs, or a range, and prints for each:

    volume : ok / failed, the first eight bytes, the time
    spti   : ok / failed, the SCSI status and sense, the first eight bytes
    verdict: agree-ok / agree-fail / DISAGREE

and, when both return data, whether the 2,048 bytes are identical.

    python tools/pathdiff.py E 278 300 500 818 1000 1024 2048
    python tools/pathdiff.py E --range 1024 1087
    python tools/pathdiff.py E --range 780 900 --stride 4

Order matters and the tool controls it: for each LBA the SCSI read is issued
first and the volume read second, so that a cached answer on the volume side
cannot be blamed on this tool having warmed the cache in the same pass. Use
--volume-first to reverse it and see whether the verdict changes.
"""
import argparse
import os
import struct
import sys
import time

SECTOR = 2048
BS = chr(92)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def read_volume(f, lba):
    t = time.time()
    try:
        f.seek(lba * SECTOR)
        d = f.read(SECTOR)
    except OSError as e:
        return None, "%s/%s" % (e.__class__.__name__,
                                getattr(e, "winerror", e.errno)), time.time() - t
    if len(d) != SECTOR:
        return None, "short %d" % len(d), time.time() - t
    return d, "ok", time.time() - t


def read_spti(dr, spti, lba):
    cdb = [0x28, 0] + list(struct.pack(">I", lba)) + [0, 0, 1, 0]
    t = time.time()
    r = dr.cmd(cdb, SECTOR, timeout=30)
    dt = time.time() - t
    if not r["ok"] or r["status"] != 0:
        return None, "st%d %s" % (r["status"], spti.sense_str(r["sense"])), dt
    return r["data"], "ok", dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("lbas", nargs="*", type=int)
    ap.add_argument("--range", nargs=2, type=int, default=None)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--volume-first", action="store_true")
    a = ap.parse_args()

    lbas = list(a.lbas)
    if a.range:
        lbas += list(range(a.range[0], a.range[1] + 1, a.stride))
    if not lbas:
        raise SystemExit("give some LBAs or --range FIRST LAST")

    import spti
    dr = spti.Drive(a.drive)
    f = open(BS + BS + "." + BS + a.drive.upper().rstrip(":") + ":", "rb",
             buffering=0)

    print("order: %s first" % ("volume" if a.volume_first else "spti"))
    print()
    print("%9s | %-22s %8s | %-34s %8s | %s"
          % ("lba", "volume", "s", "spti READ(10)", "s", "verdict"))
    tally = {"agree-ok": 0, "agree-fail": 0, "DISAGREE": 0, "same bytes": 0,
             "different bytes": 0}
    for lba in lbas:
        if a.volume_first:
            dv, sv, tv = read_volume(f, lba)
            ds, ss, ts = read_spti(dr, spti, lba)
        else:
            ds, ss, ts = read_spti(dr, spti, lba)
            dv, sv, tv = read_volume(f, lba)
        okv, oks = dv is not None, ds is not None
        if okv and oks:
            v = "agree-ok"
            tally["same bytes" if dv == ds else "different bytes"] += 1
        elif not okv and not oks:
            v = "agree-fail"
        else:
            v = "DISAGREE"
        tally[v] += 1
        print("%9d | %-22s %8.3f | %-34s %8.3f | %s%s"
              % (lba,
                 (dv[:8].hex() if okv else sv), tv,
                 (ds[:8].hex() if oks else ss), ts,
                 v,
                 "" if not (okv and oks) else
                 ("  same" if dv == ds else "  DIFFERENT BYTES")))
    print()
    print("sectors compared : %d" % len(lbas))
    for k in ("agree-ok", "agree-fail", "DISAGREE", "same bytes",
              "different bytes"):
        print("  %-16s %d" % (k, tally[k]))


if __name__ == "__main__":
    main()
