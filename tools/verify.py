#!/usr/bin/env python3
"""verify.py -- settle the predictions that no other tool happened to answer.

Nine clauses in docs/00-predictions.md were about fields that none of the
session's other tools measured on the way past. Scoring them from impressions
would be worse than leaving them unresolved, so this measures each one
directly, prints the prediction next to the measurement, and says which way it
went.

    python tools/verify.py E:/
"""
import collections
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkg  # noqa: E402
import isodev  # noqa: E402

BS = chr(92)


def head(n, text):
    print()
    print("=" * 70)
    print("%s  %s" % (n, text))
    print("=" * 70)


def p13_p15(root, letter):
    head("P13/P15", "Joliet vs ISO, and the system area")
    dev = isodev.Device(letter)
    fi, di, _, _, _ = isodev.walk(dev, False)
    fj, dj, _, _, _ = isodev.walk(dev, True)
    print("  ISO    : %d files, %d dirs, %d bytes"
          % (len(fi), len(di), sum(f.size for f in fi)))
    print("  Joliet : %d files, %d dirs, %d bytes"
          % (len(fj), len(dj), sum(f.size for f in fj)))
    ei = {(f.lba, f.size) for f in fi}
    ej = {(f.lba, f.size) for f in fj}
    print("  extents only in ISO    : %d" % len(ei - ej))
    print("  extents only in Joliet : %d" % len(ej - ei))
    print("  P13 predicted: same 540 files and 30 dirs, zero one-sided.")
    print("  => %s" % ("HIT" if (len(fi) == len(fj) == 540
                                 and len(di) == len(dj)
                                 and not (ei - ej) and not (ej - ei))
                       else "MISS"))
    print()
    sysarea = b""
    for lba in range(16):
        s = dev.sector(lba)
        if s is None:
            print("  system area sector %d UNREADABLE" % lba)
            return
        sysarea += s
    nz = sum(1 for b in sysarea if b)
    print("  system area, LBA 0..15: %d bytes, %d non-zero" % (len(sysarea), nz))
    print("  P15 predicted: entirely zero, all 32768 bytes.")
    print("  => %s" % ("HIT" if nz == 0 else "MISS"))
    dev.close()


def p37_p38_p40(root):
    head("P37/P38/P40", "mtimes and date strings")
    times = []
    for dp, dn, fn in os.walk(root):
        for f in sorted(fn):
            p = os.path.join(dp, f)
            times.append((datetime.datetime.fromtimestamp(os.path.getmtime(p)),
                          os.path.relpath(p, root).replace(os.sep, "/")))
    vals = collections.Counter(t.replace(microsecond=0) for t, _ in times)
    print("  files                 : %d" % len(times))
    print("  distinct mtimes       : %d" % len(vals))
    print("  P37 predicted: fewer than 12 distinct values.")
    print("  => %s" % ("HIT" if len(vals) < 12 else "MISS"))
    print()
    print("  the ten commonest mtimes:")
    for t, n in vals.most_common(10):
        print("     %s  x%d" % (t, n))
    print()
    early = sorted(t for t, _ in times)[0]
    late = sorted(t for t, _ in times)[-1]
    pre = [(t, r) for t, r in times if t < datetime.datetime(2001, 10, 1)]
    print("  earliest mtime        : %s" % early)
    print("  latest mtime          : %s" % late)
    print("  files before 2001-10-01: %d" % len(pre))
    for t, r in sorted(pre)[:8]:
        print("     %s  %s" % (t, r))
    print("  P38 predicted: all 540 in October 2001, zero before 2001-10-01.")
    print("  => %s" % ("HIT" if not pre else "MISS"))
    print()
    YEAR = re.compile(rb"(?<![0-9])(19[89][0-9]|20[0-2][0-9])(?![0-9])")
    late_years = collections.Counter()
    where = collections.defaultdict(list)
    for dp, dn, fn in os.walk(root):
        for f in sorted(fn):
            p = os.path.join(dp, f)
            ext = os.path.splitext(f)[1].lower()
            if ext not in (".txt", ".int", ".ita", ".spa", ".por", ".ini",
                           ".csv", ".cfg", ".inf", ".lay"):
                continue
            d = open(p, "rb").read()
            for m in YEAR.finditer(d):
                y = int(m.group(1))
                if y >= 2002:
                    late_years[y] += 1
                    rel = os.path.relpath(p, root).replace(os.sep, "/")
                    if len(where[y]) < 4:
                        where[y].append("%s +0x%X" % (rel, m.start()))
    print("  years >= 2002 in the disc's text files: %s" % dict(late_years))
    for y in sorted(late_years):
        print("     %d: %s" % (y, ", ".join(where[y])))
    print("  P40 predicted: no date string later than 2001-11-30, no 2002s.")
    print("  => %s" % ("HIT" if not late_years else "MISS"))


def p53_p55(root):
    head("P53/P55", "zero-size exports, and how often Epic is named")
    zero = []
    tot = 0
    for path in upkg.find_packages(root):
        k = upkg.Package(path)
        k.load()
        for e in k.exports:
            tot += 1
            if e[5] == 0:
                zero.append((os.path.basename(path), k.name(e[3])))
    print("  exports across all 249 packages : %d" % tot)
    print("  exports with serial size 0      : %d" % len(zero))
    for b, n in zero[:12]:
        print("     %-34s %s" % (b, n))
    print("  P53 predicted: at least one export with zero serial size.")
    print("  => %s" % ("HIT" if zero else "MISS"))
    print()
    RUN = re.compile(rb"[\x20-\x7e]{4,}")
    counts = collections.Counter()
    files = collections.defaultdict(set)
    toks = (b"Epic", b"KnowWonder", b"Electronic Arts", b"Unreal")
    for dp, dn, fn in os.walk(root):
        for f in sorted(fn):
            p = os.path.join(dp, f)
            d = open(p, "rb").read()
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            for m in RUN.finditer(d):
                s = m.group()
                for t in toks:
                    n = s.lower().count(t.lower())
                    if n:
                        counts[t] += n
                        files[t].add(rel)
    for t in toks:
        print("  %-18s %6d occurrences in %d files"
              % (t.decode(), counts[t], len(files[t])))
    print("  P55 predicted: KnowWonder in fewer than 10 files,"
          " Epic in more than 40.")
    print("  => KnowWonder in %d files: %s"
          % (len(files[b"KnowWonder"]),
             "HIT" if len(files[b"KnowWonder"]) < 10 else "MISS"))
    print("  => Epic %d occurrences: %s"
          % (counts[b"Epic"], "HIT" if counts[b"Epic"] > 40 else "MISS"))
    print("     (files naming KnowWonder: %s)" % sorted(files[b"KnowWonder"]))


def p58(root):
    head("P58", "every .unr imports a name that Engine.u exports")
    eng = upkg.Package(os.path.join(root, "System", "Engine.u"))
    eng.load()
    exported = {eng.name(e[3]) for e in eng.exports}
    print("  Engine.u exports %d objects, %d distinct names"
          % (len(eng.exports), len(exported)))
    maps = sorted(f for f in os.listdir(os.path.join(root, "Maps"))
                  if f.lower().endswith(".unr"))
    bad = []
    for m in maps:
        k = upkg.Package(os.path.join(root, "Maps", m))
        k.load()
        imported = {k.name(i[3]) for i in k.imports}
        if not (imported & exported):
            bad.append(m)
    print("  maps whose imports share no name with Engine.u's exports: %d %s"
          % (len(bad), bad))
    print("  P58 predicted: zero.")
    print("  => %s" % ("HIT" if not bad else "MISS"))


def p83(root):
    head("P83", "the three HogFront maps share import names")
    names = ["Lev2_HogFront.unr", "Lev2_HogFront_2.unr", "Lev2_HogFront_3.unr"]
    sets = {}
    for n in names:
        k = upkg.Package(os.path.join(root, "Maps", n))
        k.load()
        sets[n] = {k.name(i[3]) for i in k.imports}
        print("  %-24s %6d imports, %5d distinct import names"
              % (n, k.imp_n, len(sets[n])))
    print()
    for i in range(3):
        for j in range(i + 1, 3):
            a, b = sets[names[i]], sets[names[j]]
            inter = len(a & b)
            print("  %-22s vs %-22s : %d shared, %.1f %% of the smaller"
                  % (names[i], names[j], inter,
                     100.0 * inter / min(len(a), len(b))))
    common = sets[names[0]] & sets[names[1]] & sets[names[2]]
    print()
    print("  shared by all three: %d names, %.1f %% of the smallest set"
          % (len(common), 100.0 * len(common) / min(len(s) for s in sets.values())))
    print("  P83 predicted: more than 60 %% of import names shared.")
    ok = all(100.0 * len(sets[names[i]] & sets[names[j]]) /
             min(len(sets[names[i]]), len(sets[names[j]])) > 60
             for i in range(3) for j in range(i + 1, 3))
    print("  => %s" % ("HIT" if ok else "MISS"))


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "E:/"
    letter = root[0]
    p13_p15(root, letter)
    p37_p38_p40(root)
    p53_p55(root)
    p58(root)
    p83(root)


if __name__ == "__main__":
    main()
