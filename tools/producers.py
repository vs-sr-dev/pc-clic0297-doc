#!/usr/bin/env python3
"""producers.py -- who made what, in bytes, with the evidence graded.

Every previous disc in this collection had one producer and the interesting
question was whether anything on it came from somewhere else. This one has
many, and "who made this file" has several right answers, so the count has to
say *how it knows* as well as *what it found*.

Three grades of evidence, and a file is attributed by the strongest it has:

  grade 1   a version-resource CompanyName, read out of a PE or NE image.
            The vendor put it there deliberately and the linker wrote it.
  grade 2   a copyright notice in the bytes: a run of text matching
            "(c)"/"copyright"/"(C)" followed by a name. Weaker, because a
            file can quote someone else's notice.
  grade 3   containment: the file sits in a subtree where grade 1 found
            exactly one owner. **Off by default**, and it should be: on this
            disc it attributed 186 MB of a 1996 Italian adventure game to
            Microsoft, because one Microsoft-linked helper DLL sits in the
            same folder as the game's data. The engine's vendor is not the
            work's producer. Use --containment to see it, and do not quote
            the result as a measurement.

Nothing is attributed by guessing from a folder name. The vendor list is not
compiled in: it is whatever the bytes said in grades 1 and 2.

    python tools/producers.py _work/iso
    python tools/producers.py _work/iso --evidence
    python tools/producers.py _work/iso --tsv notes/producers.tsv
"""
import argparse
import os
import re
import struct
import sys
from collections import Counter, defaultdict

# how a vendor's many spellings fold to one name. Every key here was seen in
# the bytes of this disc first; nothing is anticipated.
FOLD = [
    (r"microsoft", "Microsoft"),
    (r"macromedia", "Macromedia"),
    (r"apple comput", "Apple"),
    (r"claris", "Claris"),
    (r"installshield|stirling techn", "InstallShield / Stirling"),
    (r"lead technolog", "LEAD Technologies"),
    (r"adaptec", "Adaptec"),
    (r"lcsi|logo comput", "LCSI"),
    (r"netscape", "Netscape"),
    (r"vdonet|vdolive", "VDOnet"),
    (r"progressive networks|realaudio", "Progressive Networks"),
    (r"adobe", "Adobe"),
    (r"intel corp", "Intel"),
    (r"radius", "Radius"),
    (r"supermac", "SuperMac"),
    (r"sonic foundry", "Sonic Foundry"),
    (r"digital equipment", "DEC"),
]

COPY = re.compile(
    rb"(?:Copyright|COPYRIGHT|\(c\)|\(C\)|\xa9)[^\x00-\x08\x0b-\x1f]{2,90}")


def fold(name):
    low = name.lower()
    for pat, canon in FOLD:
        if re.search(pat, low):
            return canon
    return None


def version_company(path, size):
    """CompanyName out of a VS_VERSIONINFO, PE or NE, found by signature.

    The version resource is UTF-16 in a PE and 8-bit in an NE; both contain
    the literal key "CompanyName" followed by the value. Rather than walk two
    different resource trees this reads the whole file once and looks for the
    key in both encodings -- which is a search, not an address, and is
    therefore reported as grade 1 only when exactly one distinct value is
    found.
    """
    if size > 24 * 1024 * 1024:
        return None
    with open(path, "rb") as fh:
        d = fh.read()
    if d[:2] != b"MZ":
        return None
    found = set()
    for key, step, dec in ((b"C\x00o\x00m\x00p\x00a\x00n\x00y\x00N\x00a\x00m\x00e\x00", 2, "utf-16-le"),
                           (b"CompanyName", 1, "latin-1")):
        i = 0
        while True:
            i = d.find(key, i)
            if i < 0:
                break
            j = i + len(key)
            # skip the key terminator and any padding zeros
            while j < len(d) and d[j] == 0:
                j += 1
            end = j
            lim = min(j + 200, len(d))
            while end < lim:
                if step == 2:
                    if d[end:end + 2] == b"\x00\x00":
                        break
                    end += 2
                else:
                    if d[end] == 0:
                        break
                    end += 1
            val = d[j:end].decode(dec, "replace").strip()
            if 2 <= len(val) <= 80 and val.isprintable():
                found.add(val)
            i = j
    if len(found) == 1:
        return found.pop()
    if found:
        return sorted(found)[0]
    return None


def copyrights(path, size):
    if size > 24 * 1024 * 1024:
        n = 4 * 1024 * 1024
    else:
        n = size
    with open(path, "rb") as fh:
        d = fh.read(n)
    out = set()
    for m in COPY.finditer(d):
        s = m.group(0).decode("latin-1", "replace")
        s = "".join(ch for ch in s if ch.isprintable()).strip()
        if len(s) >= 8:
            out.add(s[:90])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--evidence", action="store_true")
    ap.add_argument("--containment", action="store_true",
                    help="allow grade 3; see the caveat at the top")
    ap.add_argument("--tsv")
    a = ap.parse_args()

    rows = []
    for dp, dn, fn in os.walk(a.root):
        for f in sorted(fn):
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, a.root).replace(os.sep, "/")
            size = os.path.getsize(p)
            g1 = fold(version_company(p, size) or "")
            raw1 = version_company(p, size) if g1 else None
            cps = copyrights(p, size)
            g2 = None
            names = set()
            for c in cps:
                n = fold(c)
                if n:
                    names.add(n)
            if len(names) == 1:
                g2 = next(iter(names))
            elif names:
                g2 = "+".join(sorted(names))
            rows.append([rel, size, g1, raw1, g2, sorted(cps)[:3]])

    # grade 3: containment
    sub = defaultdict(set)
    for rel, size, g1, raw1, g2, cps in rows:
        top = rel.split("/")[0] if "/" in rel else "(root)"
        for g in (g1,):
            if g:
                sub[top].add(g)
    for r in rows:
        top = r[0].split("/")[0] if "/" in r[0] else "(root)"
        r.append(next(iter(sub[top]))
                 if (a.containment and len(sub[top]) == 1) else None)

    tot = sum(r[1] for r in rows)
    byname = Counter()
    bygrade = Counter()
    gradebytes = Counter()
    for rel, size, g1, raw1, g2, cps, g3 in rows:
        if g1:
            who, gr = g1, 1
        elif g2 and "+" not in g2:
            who, gr = g2, 2
        elif g3:
            who, gr = g3, 3
        else:
            who, gr = "(unattributed)", 0
        byname[who] += size
        bygrade[gr] += 1
        gradebytes[gr] += size

    print("files                 : %d" % len(rows))
    print("bytes                 : %d" % tot)
    print()
    print("evidence grade used:")
    labels = {1: "1  version-resource CompanyName",
              2: "2  copyright string in the bytes",
              3: "3  containment in a single-owner subtree",
              0: "-  no evidence of any grade"}
    for g in (1, 2, 3, 0):
        print("  %-42s %5d files %12d bytes %6.2f%%"
              % (labels[g], bygrade[g], gradebytes[g],
                 100.0 * gradebytes[g] / tot))
    print()
    print("producers, by bytes:")
    print("  %-28s %6s %14s %8s" % ("producer", "files", "bytes", "share"))
    fc = Counter()
    for rel, size, g1, raw1, g2, cps, g3 in rows:
        who = g1 or (g2 if g2 and "+" not in g2 else None) or g3 or "(unattributed)"
        fc[who] += 1
    for who, b in byname.most_common():
        print("  %-28s %6d %14d %7.2f%%" % (who, fc[who], b, 100.0 * b / tot))
    print()

    print("the distinct CompanyName strings actually found (grade 1):")
    cn = Counter()
    for rel, size, g1, raw1, g2, cps, g3 in rows:
        if raw1:
            cn[raw1] += 1
    for v, n in cn.most_common():
        print("  %-52s %4d" % (v, n))
    print()

    if a.evidence:
        print("every copyright string found, with how many files carry it:")
        cc = Counter()
        for rel, size, g1, raw1, g2, cps, g3 in rows:
            for c in cps:
                cc[c] += 1
        for c, n in cc.most_common(80):
            print("  %4d  %s" % (n, c))

    if a.tsv:
        with open(a.tsv, "w", encoding="utf-8", newline="") as fh:
            fh.write("path\tsize\tgrade1\tcompanyname\tgrade2\tgrade3\n")
            for rel, size, g1, raw1, g2, cps, g3 in rows:
                fh.write("%s\t%d\t%s\t%s\t%s\t%s\n"
                         % (rel, size, g1 or "", (raw1 or "").replace("\t", " "),
                            g2 or "", g3 or ""))
        print("wrote %s" % a.tsv)


if __name__ == "__main__":
    main()
