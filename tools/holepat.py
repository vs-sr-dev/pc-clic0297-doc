#!/usr/bin/env python3
"""holepat.py -- classify the contents of a sector range by *shape*, not by name.

gapname.py answers "is there a filesystem structure here"; when the answer is
no it prints "unidentified", which on this disc would be 80,163 sectors of
"unidentified" and no measurement at all.

This tool asks a different question: **is this sector the output of a
generator, and if so which one?** Every sector is put in exactly one class:

    zero        all 2048 bytes are 0x00
    fill        all 2048 bytes are the same non-zero byte
    arith       b[i] = (b[0] + i*d) mod 256 for a single constant d, for all i
    arith-run   the sector is arith except for a prefix or suffix
    text        >= 95 % of bytes are printable ASCII or whitespace
    other       none of the above; entropy and the first 16 bytes are reported

For every `arith` sector the pair (b[0], d) is recorded, so the caller can ask
whether d is a function of the LBA. That is the whole point: a classifier that
says "arithmetic progression, step 0x42" turns 143 MB of "unidentified" into a
closed form that can be checked against every sector rather than sampled.

    python tools/holepat.py E 265135 335259
    python tools/holepat.py E 278 10277 --hex
    python tools/holepat.py E 265135 335259 --model "(lba+82)%256"
    python tools/holepat.py E 265135 335259 --csv notes/holepat-big.csv

--model takes a Python expression in `lba` and, for every `arith` sector,
compares its measured step against the model's prediction, printing the count
of agreements and the first ten disagreements. No constant of any disc is
compiled into this file; every boundary comes from the command line.
"""
import argparse
import collections
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SECTOR = 2048
BS = chr(92)
PRINTABLE = set(range(32, 127)) | {9, 10, 13}


def devpath(letter):
    return BS + BS + "." + BS + letter.upper() + ":"


def entropy(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    n = float(len(b))
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def classify(b):
    """Return (class, detail). detail is (start, step) for arith.

    Linear in the sector length: the difference sequence d[i] = b[i+1]-b[i]
    mod 256 is computed once, and a progression is exactly a run of equal
    differences. The first version of this function searched for the longest
    progression by restarting at every offset, which is quadratic -- 4.2
    million operations per sector of random data, and it made a 1,024-sector
    range take longer than reading the whole disc.
    """
    n = len(b)
    if not n:
        return "short", None
    s = set(b)
    if s == {0}:
        return "zero", None
    if len(s) == 1:
        return "fill", (b[0], 0)
    diff = bytes((b[i + 1] - b[i]) & 0xFF for i in range(n - 1))
    d0 = diff[0]
    if diff.count(d0) == n - 1:
        return "arith", (b[0], d0)
    # longest run of a constant difference, found in one pass
    best_len = best_i = 0
    i = 0
    m = len(diff)
    while i < m:
        j = i
        while j < m and diff[j] == diff[i]:
            j += 1
        if j - i > best_len:
            best_len, best_i = j - i, i
        i = j
    if best_len + 1 >= n * 0.75:
        return "arith-run", (b[best_i], diff[best_i], best_i, best_len + 1)
    if sum(1 for x in b if x in PRINTABLE) >= 0.95 * n:
        return "text", None
    return "other", None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("first", type=int)
    ap.add_argument("last", type=int)
    ap.add_argument("--hex", action="store_true",
                    help="print the first 16 bytes of every non-arith sector")
    ap.add_argument("--model", default=None,
                    help="expression in lba giving the expected step")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--limit-examples", type=int, default=10)
    ap.add_argument("--max-failures", type=int, default=0,
                    help="stop after this many failed reads and say so; 0 = "
                         "no limit. A failed read on this drive costs about "
                         "seven seconds and enough of them put the drive in a "
                         "state where good sectors fail too, so a budget is "
                         "part of the measurement and is printed with it.")
    ap.add_argument("--block", type=int, default=32,
                    help="sectors per SCSI READ(10); SPTD refuses more than 32")
    a = ap.parse_args()

    n = a.last - a.first + 1
    counts = collections.Counter()
    steps = collections.Counter()
    starts = collections.Counter()
    model_ok = model_bad = 0
    bad_examples = []
    other_examples = []
    ent_sum = 0.0
    ent_n = 0
    runs = []                     # (class, first lba, last lba)
    csv = open(a.csv, "w", encoding="utf-8") if a.csv else None
    if csv:
        csv.write("lba,class,start,step,entropy\n")

    BLOCK = a.block
    import spti
    dev = spti.Drive(a.drive)

    failures = [0]
    aborted = [None]

    def block_read(first, want):
        if aborted[0]:
            return b""
        cdb = ([0x28, 0] + list(struct.pack(">I", first)) + [0]
               + list(struct.pack(">H", want)) + [0])
        r = dev.cmd(cdb, SECTOR * want, timeout=30)
        if not r["ok"] or r["status"] != 0:
            failures[0] += 1
            if a.max_failures and failures[0] >= a.max_failures:
                aborted[0] = ("stopped after %d failed reads at LBA %d "
                              "(--max-failures)" % (failures[0], first))
            return b""
        return r["data"]

    if True:
        buf = b""
        pos = 0
        bad_left = 0
        for k in range(n):
            lba = a.first + k
            if bad_left > 0:
                # this sector is inside a block the drive refused; consume it
                # without asking again. A second failed read of the same block
                # costs another seven seconds and answers nothing new.
                bad_left -= 1
                b = b""
            else:
                if pos >= len(buf):
                    want = min(BLOCK, n - k)
                    buf = block_read(lba, want)
                    pos = 0
                    if not buf:
                        bad_left = want - 1
                        b = b""
                        counts["unreadable"] += 1
                        if runs and runs[-1][0] == "unreadable" and runs[-1][2] == lba - 1:
                            runs[-1][2] = lba
                        else:
                            runs.append(["unreadable", lba, lba])
                        if csv:
                            csv.write(str(lba) + ",unreadable,,," + chr(10))
                        continue
                b = buf[pos:pos + SECTOR]
                pos += SECTOR
            if len(b) != SECTOR:
                cls, det = "unreadable", None
            else:
                cls, det = classify(b)
            counts[cls] += 1
            e = ""
            if cls in ("other", "text"):
                ev = entropy(b)
                ent_sum += ev
                ent_n += 1
                e = "%.4f" % ev
                if len(other_examples) < a.limit_examples:
                    other_examples.append((lba, cls, b[:16].hex(), ev))
            if cls == "arith":
                steps[det[1]] += 1
                starts[det[0]] += 1
                if a.model:
                    want = eval(a.model, {"__builtins__": {}}, {"lba": lba}) % 256
                    if want == det[1]:
                        model_ok += 1
                    else:
                        model_bad += 1
                        if len(bad_examples) < a.limit_examples:
                            bad_examples.append((lba, det[1], want))
            if a.hex and cls not in ("arith", "zero"):
                print("  %8d %-9s %s" % (lba, cls, b[:16].hex()))
            if csv:
                csv.write("%d,%s,%s,%s,%s\n" %
                          (lba, cls,
                           det[0] if det else "",
                           det[1] if det else "",
                           e))
            if runs and runs[-1][0] == cls and runs[-1][2] == lba - 1:
                runs[-1][2] = lba
            else:
                runs.append([cls, lba, lba])
    if csv:
        csv.close()

    print("range      : LBA %d .. %d   (%d sectors, %d bytes)"
          % (a.first, a.last, n, n * SECTOR))
    print("read        : SCSI READ(10), %d sectors per command" % a.block)
    print("failed reads: %d%s" % (failures[0],
                                  "   " + aborted[0] if aborted[0] else ""))
    print()
    print("class      count        share")
    for cls, c in counts.most_common():
        print("  %-9s %8d   %6.2f %%" % (cls, c, 100.0 * c / n))
    print()
    print("runs of one class, in LBA order: %d" % len(runs))
    for cls, lo, hi in runs[:40]:
        print("  %-9s %8d .. %8d   %8d" % (cls, lo, hi, hi - lo + 1))
    if len(runs) > 40:
        print("  ... %d more runs" % (len(runs) - 40))
    if steps:
        print()
        print("distinct arithmetic steps : %d" % len(steps))
        print("distinct first bytes      : %d" % len(starts))
        print("most common steps         : %s"
              % ", ".join("0x%02x x%d" % (k, v) for k, v in steps.most_common(6)))
    if a.model:
        tot = model_ok + model_bad
        print()
        print("model     : step == %s" % a.model)
        print("agrees    : %d of %d arithmetic sectors (%.4f %%)"
              % (model_ok, tot, 100.0 * model_ok / tot if tot else 0.0))
        for lba, got, want in bad_examples:
            print("  !! LBA %8d  measured 0x%02x  model 0x%02x" % (lba, got, want))
    if ent_n:
        print()
        print("mean Shannon entropy over %d non-generated sectors : %.4f bits/byte"
              % (ent_n, ent_sum / ent_n))
        for lba, cls, head, ev in other_examples:
            print("  %8d %-6s %s  H=%.3f" % (lba, cls, head, ev))


if __name__ == "__main__":
    main()
