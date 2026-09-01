#!/usr/bin/env python3
"""pcinvisible.py -- every byte of this disc a Windows machine cannot reach.

The published hash list of a disc has always meant "what another session could
reproduce by putting the disc in a Windows drive". On a hybrid that list is
incomplete by construction, and the incompleteness is measurable:

  * 18 resource forks live in the ISO namespace with the Associated-File flag
    set (ECMA-119 9.1.6 bit 2). They are real ISO directory records with real
    extents, and the Windows CDFS driver drops them on the floor;
  * 23 files exist only in the HFS catalogue, with 29 forks between them.

A fork is counted here as PC-invisible when it is a resource fork, or when it
is the data fork of a path that does not appear in the Windows walk of the
mounted volume. The rule is stated so the subtraction can be checked.

    python tools/pcinvisible.py --forks _work/hfs --tree _work/iso \\
        --out notes/sha1-hfs-only.txt
"""
import argparse
import hashlib
import os


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--forks", default="_work/hfs")
    ap.add_argument("--tree", default="_work/iso")
    ap.add_argument("--out", default="notes/sha1-hfs-only.txt")
    a = ap.parse_args()

    win = set()
    for dp, dn, fn in os.walk(a.tree):
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), a.tree)
            win.add(rel.replace(os.sep, "/").upper())

    rows = []
    skipped = []
    for dp, dn, fn in os.walk(a.forks):
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, a.forks).replace(os.sep, "/")
            is_rsrc = rel.endswith(".rsrc")
            base = rel[:-5] if is_rsrc else rel
            if not is_rsrc and base.upper() in win:
                skipped.append(rel)
                continue
            rows.append((sha1(p), os.path.getsize(p), rel, is_rsrc))

    rows.sort(key=lambda r: r[2])
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        for h, sz, rel, isr in rows:
            fh.write("%s  %12d  %s\n" % (h, sz, rel))
        fh.write("forks %d  bytes %d  distinct sha1 %d\n"
                 % (len(rows), sum(r[1] for r in rows),
                    len(set(r[0] for r in rows))))

    nr = [r for r in rows if r[3]]
    nd = [r for r in rows if not r[3]]
    print("rule: a fork is PC-invisible when it is a resource fork, or when it")
    print("      is the data fork of a path absent from the Windows walk.")
    print()
    print("data forks of paths Windows never sees : %4d   %12d bytes"
          % (len(nd), sum(r[1] for r in nd)))
    print("resource forks, all of them            : %4d   %12d bytes"
          % (len(nr), sum(r[1] for r in nr)))
    print("total PC-invisible forks               : %4d   %12d bytes"
          % (len(rows), sum(r[1] for r in rows)))
    print("distinct sha1 among them               : %4d"
          % len(set(r[0] for r in rows)))
    print()
    print("data forks skipped because Windows can read them : %d" % len(skipped))
    print("wrote %s" % a.out)


if __name__ == "__main__":
    main()
