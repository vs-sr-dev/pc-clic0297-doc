#!/usr/bin/env python3
"""filelist.py -- expand common_filelist.txt's three globs against the tree.

The root of this disc carries a 78-byte installer manifest, in the clear:

    1,1,Support{BS}European Help Files{BS}*.* /s
    1,1,Support{BS}*.*
    1,1,eauninstall.exe

Three lines that say what gets copied outside the zip. This expands them
against the actual tree and reports what they cover and what they miss, because
"the manifest describes the whole set" is a claim and not an observation.

    python tools/filelist.py
    python tools/filelist.py _work/nozip
"""
import fnmatch
import os
import sys

BS = chr(92)
root = sys.argv[1] if len(sys.argv) > 1 else "_work/nozip"

allf = set()
for dp, dn, fn in os.walk(root):
    for f in fn:
        allf.add(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, BS))


def match(pat, recursive):
    out = set()
    pd = os.path.dirname(pat)
    pb = os.path.basename(pat)
    for f in allf:
        d = os.path.dirname(f)
        base = os.path.basename(f)
        if recursive:
            if (d == pd or d.startswith(pd + BS)) and fnmatch.fnmatch(base, pb):
                out.add(f)
        elif d == pd and fnmatch.fnmatch(base, pb):
            out.add(f)
    return out


a = match("Support" + BS + "European Help Files" + BS + "*.*", True)
b = match("Support" + BS + "*.*", False)
c = {"eauninstall.exe"} & allf
cov = a | b | c

print("tree                                          : %s" % root)
print("files outside the zip                         : %d" % len(allf))
print("line 1  Support%sEuropean Help Files%s*.*  /s   : %d" % (BS, BS, len(a)))
print("line 2  Support%s*.*                           : %d" % (BS, len(b)))
print("line 3  eauninstall.exe                        : %d" % len(c))
print("covered in total                              : %d" % len(cov))
print()

sup = [f for f in allf if f.startswith("Support" + BS)]
miss = sorted(set(sup) - cov)
print("files under Support%s on the disc              : %d" % (BS, len(sup)))
print("of those, NOT covered by the manifest          : %d" % len(miss))
for f in miss:
    print("     %s" % f)
print()
print("outside Support%s and not covered (%d) -- these are the files the" % (BS, len(allf - cov - set(sup))))
print("autorun shell reads from the disc rather than installing:")
for f in sorted(allf - cov - set(sup)):
    print("     %s" % f)
