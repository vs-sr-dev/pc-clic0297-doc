#!/usr/bin/env python3
"""census.py -- a whole-tree census for 2,862 files.

pc-mystictowers-doc's census.py printed a hex dump of every file, which is the
right thing to do when there are four of them. Here it would print 2,862 hex
dumps, so this is a different tool with the same name and the same purpose:
find out what is on the disc without opening anything by hand.

What it measures:
  * per extension: count, bytes, share of the tree, size range, and the
    distinct four-byte magics found at offset 0 with a count for each;
  * per top-level directory: the same;
  * SHA-1 of every file, hence byte-identical duplicates and the bytes they
    waste;
  * files whose size is a statistical outlier inside their own directory,
    which is the cheap way to find placeholders and leftovers;
  * entropy, on a sample, for anything that looks compressed.

Entropy is computed on at most --entropy-cap bytes (default 262144) taken from
the head of the file. On a 166 MB AVI the first 256 KB is enough to say
"compressed" and reading all of it is not free.

    python tools/census.py _work/iso
    python tools/census.py _work/iso --ext .tga
    python tools/census.py _work/iso --dups
    python tools/census.py _work/iso --outliers
    python tools/census.py _work/iso --magic
    python tools/census.py _work/iso --sha1
"""
import hashlib
import math
import os
import sys
from collections import Counter, defaultdict

ENTROPY_CAP = 262144


def entropy(b):
    if not b:
        return 0.0
    c = Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def scan(root, cap=ENTROPY_CAP, want_sha1=True):
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            size = os.path.getsize(p)
            with open(p, "rb") as fh:
                head = fh.read(min(size, cap))
            h = None
            if want_sha1:
                sh = hashlib.sha1()
                with open(p, "rb") as fh:
                    while True:
                        chunk = fh.read(1 << 20)
                        if not chunk:
                            break
                        sh.update(chunk)
                h = sh.hexdigest()
            ext = os.path.splitext(fn)[1].lower()
            top = rel.split("/")[0] if "/" in rel else "(root)"
            out.append(dict(rel=rel, name=fn, size=size, ext=ext, top=top,
                            dirn=os.path.dirname(rel) or "(root)",
                            magic=bytes(head[:4]), head=bytes(head[:16]),
                            ent=entropy(head), sha1=h))
    return out


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def show_magic(b):
    return "".join(chr(x) if 32 <= x < 127 else "." for x in b) + \
        "  " + " ".join("%02X" % x for x in b)


def by_extension(files, total):
    print("%-8s %6s %13s %8s %10s %10s %10s %7s" % (
        "ext", "count", "bytes", "share", "min", "max", "mean", "H(mean)"))
    groups = defaultdict(list)
    for f in files:
        groups[f["ext"] or "(none)"].append(f)
    for ext, g in sorted(groups.items(), key=lambda kv: -sum(
            f["size"] for f in kv[1])):
        s = [f["size"] for f in g]
        print("%-8s %6d %13d %7.2f%% %10d %10d %10d %7.3f" % (
            ext, len(g), sum(s), pct(sum(s), total), min(s), max(s),
            sum(s) // len(g),
            sum(f["ent"] for f in g) / len(g)))
    print()
    print("extensions: %d   files: %d   bytes: %d" % (
        len(groups), len(files), total))


def by_directory(files, total):
    groups = defaultdict(list)
    for f in files:
        groups[f["dirn"]].append(f)
    print("%-58s %6s %13s %8s" % ("directory", "count", "bytes", "share"))
    for d, g in sorted(groups.items()):
        s = sum(f["size"] for f in g)
        print("%-58s %6d %13d %7.2f%%" % (d, len(g), s, pct(s, total)))
    print()
    print("directories holding at least one file: %d" % len(groups))


def magics(files):
    groups = defaultdict(Counter)
    for f in files:
        groups[f["ext"] or "(none)"][f["magic"]] += 1
    for ext, c in sorted(groups.items(), key=lambda kv: -sum(kv[1].values())):
        print("%-8s %d files, %d distinct four-byte magics" % (
            ext, sum(c.values()), len(c)))
        for m, n in c.most_common(8):
            print("      %6d  %s" % (n, show_magic(m)))
        if len(c) > 8:
            print("      ... %d more" % (len(c) - 8))


def dups(files, total):
    by = defaultdict(list)
    for f in files:
        by[f["sha1"]].append(f)
    groups = [v for v in by.values() if len(v) > 1]
    groups.sort(key=lambda v: -(v[0]["size"] * (len(v) - 1)))
    wasted = sum(v[0]["size"] * (len(v) - 1) for v in groups)
    print("distinct SHA-1 values : %d" % len(by))
    print("files                 : %d" % len(files))
    print("duplicate groups      : %d" % len(groups))
    print("redundant copies      : %d" % sum(len(v) - 1 for v in groups))
    print("bytes in redundancy   : %d  (%.2f %% of the tree)" % (
        wasted, pct(wasted, total)))
    print()
    for v in groups:
        print("  %d copies x %d bytes  sha1 %s" % (
            len(v), v[0]["size"], v[0]["sha1"]))
        for f in sorted(v, key=lambda x: x["rel"]):
            print("      %s" % f["rel"])


def outliers(files):
    """Files whose size is far from the median of their own directory.

    A 43-byte TGA next to eight hundred 40 KB TGAs is not an outlier because
    43 is small; it is an outlier because everything around it is a thousand
    times bigger. Directory-relative is the only comparison that means
    anything on a disc with 1,433 files of one type."""
    groups = defaultdict(list)
    for f in files:
        groups[(f["dirn"], f["ext"])].append(f)
    rows = []
    for (d, ext), g in groups.items():
        if len(g) < 4:
            continue
        s = sorted(f["size"] for f in g)
        med = s[len(s) // 2]
        if med == 0:
            continue
        for f in g:
            ratio = f["size"] / med
            if ratio < 0.05 or ratio > 12.0:
                rows.append((ratio, med, len(g), f))
    rows.sort(key=lambda r: r[0])
    print("%-64s %9s %9s %6s %7s" % (
        "file", "bytes", "dir med", "n", "ratio"))
    for ratio, med, n, f in rows:
        print("%-64s %9d %9d %6d %7.3f" % (f["rel"], f["size"], med, n, ratio))
    print()
    print("outliers: %d  (ratio to directory median below 0.05 or above 12)"
          % len(rows))


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "_work/iso"
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
    need_sha1 = "--dups" in sys.argv or "--sha1" in sys.argv
    files = scan(root, want_sha1=need_sha1)
    total = sum(f["size"] for f in files)
    if "--ext" in sys.argv:
        want = sys.argv[sys.argv.index("--ext") + 1].lower()
        sel = [f for f in files if f["ext"] == want]
        sel.sort(key=lambda f: f["size"])
        print("%-64s %10s %8s  %s" % ("file", "bytes", "entropy", "first 16"))
        for f in sel:
            print("%-64s %10d %8.3f  %s" % (
                f["rel"], f["size"], f["ent"], show_magic(f["head"])))
        s = [f["size"] for f in sel]
        print()
        print("%s: %d files, %d bytes, min %d, max %d, median %d" % (
            want, len(sel), sum(s), min(s), max(s), sorted(s)[len(s) // 2]))
        return
    if "--magic" in sys.argv:
        magics(files)
        return
    if "--dups" in sys.argv:
        dups(files, total)
        return
    if "--outliers" in sys.argv:
        outliers(files)
        return
    if "--sha1" in sys.argv:
        for f in sorted(files, key=lambda x: x["rel"]):
            print("%s  %10d  %s" % (f["sha1"], f["size"], f["rel"]))
        return
    print("=== by extension ===")
    by_extension(files, total)
    print()
    print("=== by directory ===")
    by_directory(files, total)


if __name__ == "__main__":
    main()
