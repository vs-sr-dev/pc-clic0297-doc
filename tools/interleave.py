#!/usr/bin/env python3
"""interleave.py -- probe suspect sectors with known-good controls in the same pass.

This closes, or at least measures, the open question four sessions of this
collection have carried: on a drive whose behaviour degrades as it accumulates
failures, how do you tell a bad sector from a tired drive?

The tenth session concluded -- reproducibly, with three different SCSI commands
-- that 143 MB of perfectly healthy filler was unreadable. It was not. The drive
had stopped answering after about sixty consecutive errors, and only a tray
cycle cleared it. It found out by re-reading its controls afterwards.

Afterwards is too late. This reads a control sector **between every two suspect
sectors, in the same pass**, so the state of the drive is sampled at the moment
each verdict is taken rather than reconstructed at the end. A suspect that fails
while the controls on either side of it succeed is a property of the disc. A
suspect that fails while its neighbouring controls also fail says nothing about
the disc at all, and the tool refuses to call it bad.

    python tools/interleave.py E --control 16 --suspect 294550 294551 294552
    python tools/interleave.py E --control 16 --range 294540 294560
    python tools/interleave.py E --control 16 --range 294540 294560 --budget 40

BUDGET
------
`--budget` is the number of failed reads after which the tool stops and says so,
because a failed read on this drive costs about seven seconds and sixty of them
in a row cost the tray. The budget spent is printed next to the result whether
or not it was reached, so a run that stopped early can never be mistaken for a
run that found nothing.
"""
import argparse
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spti

SECTOR = 2048


class Probe(object):
    """One SCSI READ(10) per call, through the inherited spti.Drive.

    The first version of this file reimplemented IOCTL_SCSI_PASS_THROUGH_DIRECT
    and got the structure length wrong, so every read returned in 0.000 s with
    an all-zero sense buffer. The tool then correctly refused to give a verdict
    on twenty-one sectors, because its own controls were failing -- which is the
    behaviour it was written to have, arrived at for the wrong reason. spti.py
    already had a working Drive class. It is used here rather than rewritten.
    """

    def __init__(self, letter):
        self.d = spti.Drive(letter)

    def read(self, lba, n=1):
        cdb = ([0x28, 0] + list(struct.pack(">I", lba)) + [0]
               + list(struct.pack(">H", n)) + [0])
        t = time.time()
        r = self.d.cmd(cdb, SECTOR * n, timeout=30)
        dt = time.time() - t
        if r["ok"] and r["status"] == 0:
            return True, r["data"], dt, ""
        return False, None, dt, ("status %d %s winerr %d"
                                 % (r["status"], spti.sense_str(r["sense"]),
                                    r["winerr"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("--control", type=int, action="append", default=[],
                    help="an LBA known to be readable; may be given twice")
    ap.add_argument("--suspect", type=int, nargs="*", default=[])
    ap.add_argument("--range", type=int, nargs=2)
    ap.add_argument("--budget", type=int, default=40)
    a = ap.parse_args()

    controls = a.control or [16]
    suspects = list(a.suspect)
    if a.range:
        suspects += list(range(a.range[0], a.range[1] + 1))
    if not suspects:
        raise SystemExit("nothing to probe: give --suspect or --range")

    d = Probe(a.drive)
    print("drive        : %s:" % a.drive.upper().rstrip(":"))
    print("controls     : %s" % controls)
    print("suspects     : %d sectors, LBA %d..%d"
          % (len(suspects), min(suspects), max(suspects)))
    print("budget       : %d failed reads" % a.budget)
    print()
    print("%10s %-8s %7s  %s" % ("LBA", "verdict", "seconds", "sense"))

    fails = 0
    results = []
    ci = 0
    stopped = None
    for s in suspects:
        c = controls[ci % len(controls)]
        ci += 1
        okc, _, dtc, snc = d.read(c)
        if not okc:
            fails += 1
        print("%10d %-8s %7.3f  %s" % (c, "CONTROL ok" if okc else "CONTROL FAIL",
                                       dtc, snc))
        oks, _, dts, sns = d.read(s)
        if not oks:
            fails += 1
        print("%10d %-8s %7.3f  %s" % (s, "ok" if oks else "FAIL", dts, sns))
        okc2, _, dtc2, snc2 = d.read(c)
        if not okc2:
            fails += 1
        results.append({"lba": s, "ok": oks, "sense": sns,
                        "before": okc, "after": okc2, "t": dts})
        if fails >= a.budget:
            stopped = s
            break

    print()
    print("--- verdicts ---")
    good = [r for r in results if r["ok"]]
    bad = [r for r in results if not r["ok"] and r["before"] and r["after"]]
    void = [r for r in results if not r["ok"] and not (r["before"] and r["after"])]
    print("readable                                  : %d" % len(good))
    print("unreadable, both controls around it good  : %d" % len(bad))
    print("unreadable while a control also failed    : %d  (NO VERDICT)" % len(void))
    print()
    if bad:
        runs = []
        for r in bad:
            if runs and r["lba"] == runs[-1][1] + 1:
                runs[-1][1] = r["lba"]
            else:
                runs.append([r["lba"], r["lba"]])
        print("unreadable runs, each one flanked by a successful control:")
        for lo, hi in runs:
            print("    LBA %d .. %d   %d sectors" % (lo, hi, hi - lo + 1))
    if void:
        print()
        print("sectors on which this run refuses to give a verdict, because the")
        print("drive was not answering its own control at the time:")
        print("    %s" % ", ".join(str(r["lba"]) for r in void))
    slow = [r for r in good if r["t"] > 1.0]
    if slow:
        print()
        print("readable but slow (a recovered read, not a clean one):")
        for r in slow:
            print("    LBA %d   %.2f s" % (r["lba"], r["t"]))
    print()
    print("failed reads spent : %d of a budget of %d" % (fails, a.budget))
    if stopped is not None:
        print("STOPPED EARLY at LBA %d: the budget ran out. Everything above"
              % stopped)
        print("LBA %d is unmeasured, not measured-good." % stopped)


if __name__ == "__main__":
    main()
