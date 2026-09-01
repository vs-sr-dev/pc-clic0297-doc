#!/usr/bin/env python3
"""padform.py -- check a closed form against every byte of a sector range.

holepat.py classifies each sector and finds that the padding region of this
disc is, sector by sector, an arithmetic progression modulo 256 whose common
difference is a function of the sector address. That is a statement about
2,048 differences per sector; it is not yet a statement about the bytes.

This tool takes a formula for the byte itself, as a Python expression in
`lba` and `i` (the byte offset inside the sector), builds the 2,048-byte
sector it predicts, and compares it with the sector the drive returns. It
reports how many sectors match **in all 2,048 bytes**, how many differ, and
for the first few that differ, the offset of the first differing byte and both
values.

    python tools/padform.py E 265135 335259 --formula "((lba+82)*(i+77))%256"
    python tools/padform.py E 265135 265390 --formula "((lba+82)*(i+77))%256" --verbose

The formula is an argument, not a constant. A different disc, or a different
guess, is a different command line and the tool has no opinion about which is
right -- it only counts.

Reads go out as SCSI READ(10) through spti.py, in --block sectors per command,
because the volume device on this machine returns cached bytes for sectors the
drive cannot read and its transfer limit varies with the address. See
tools/discpass.py for the measurement behind that sentence.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SECTOR = 2048


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("first", type=int)
    ap.add_argument("last", type=int)
    ap.add_argument("--formula", required=True,
                    help="expression in lba and i giving the byte value")
    ap.add_argument("--block", type=int, default=32)
    ap.add_argument("--examples", type=int, default=8)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--cache-mod", type=int, default=0,
                    help="if the formula depends on lba only through "
                         "lba %% N, give N and each of the N distinct "
                         "predicted sectors is built once instead of once "
                         "per sector. Declared, not assumed: with N wrong "
                         "the comparison fails loudly rather than quietly.")
    a = ap.parse_args()

    import spti
    dev = spti.Drive(a.drive)

    code = compile(a.formula, "<formula>", "eval")
    env = {"__builtins__": {}}

    def build(lba):
        return bytes(eval(code, env, {"lba": lba, "i": i}) & 0xFF
                     for i in range(SECTOR))

    cache = {}

    def predict(lba):
        if not a.cache_mod:
            return build(lba)
        k = lba % a.cache_mod
        v = cache.get(k)
        if v is None:
            v = cache[k] = build(lba)
        return v

    n = a.last - a.first + 1
    match = differ = unread = 0
    examples = []
    first_diff_hist = {}

    lba = a.first
    while lba <= a.last:
        want = min(a.block, a.last - lba + 1)
        cdb = ([0x28, 0] + list(struct.pack(">I", lba)) + [0]
               + list(struct.pack(">H", want)) + [0])
        r = dev.cmd(cdb, SECTOR * want, timeout=30)
        if not r["ok"] or r["status"] != 0:
            unread += want
            lba += want
            continue
        d = r["data"]
        for k in range(want):
            s = d[k * SECTOR:(k + 1) * SECTOR]
            p = predict(lba + k)
            if s == p:
                match += 1
                if a.verbose:
                    print("  %8d match" % (lba + k))
            else:
                differ += 1
                j = next(x for x in range(SECTOR) if s[x] != p[x])
                first_diff_hist[j] = first_diff_hist.get(j, 0) + 1
                if len(examples) < a.examples:
                    examples.append((lba + k, j, s[j], p[j],
                                     s[:8].hex(), p[:8].hex()))
        lba += want

    print("range        : LBA %d .. %d   (%d sectors, %d bytes)"
          % (a.first, a.last, n, n * SECTOR))
    print("formula      : byte[i] = %s" % a.formula)
    if a.cache_mod:
        print("prediction cache : one sector built per lba %% %d, %d distinct"
              % (a.cache_mod, len(cache)))
    print()
    print("sectors matching in all 2048 bytes : %d  (%.4f %%)"
          % (match, 100.0 * match / n if n else 0))
    print("sectors differing                  : %d" % differ)
    print("sectors the drive would not return : %d" % unread)
    print("bytes covered by the formula       : %d" % (match * SECTOR))
    if examples:
        print()
        print("first %d differing sectors:" % len(examples))
        for lba_, j, got, want_, gh, wh in examples:
            print("  LBA %8d  first difference at byte %4d: disc %02x, formula %02x"
                  % (lba_, j, got, want_))
            print("      disc    %s ..." % gh)
            print("      formula %s ..." % wh)
    if first_diff_hist:
        print()
        print("where the first difference falls, by offset:")
        for j in sorted(first_diff_hist)[:20]:
            print("  byte %4d : %d sectors" % (j, first_diff_hist[j]))


if __name__ == "__main__":
    main()
