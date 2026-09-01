#!/usr/bin/env python3
"""jbf.py -- JASC Paint Shop Pro browser cache (`PSPBRWSE.JBF`).

This is not a format of the object. It is a format of a program somebody ran
on a folder of this disc's source tree before the disc existed: Paint Shop Pro
writes `PSPBRWSE.JBF` into a directory the moment a user opens that directory
in its image browser, and the file caches one thumbnail per image so the second
visit is fast. Finding one pressed onto a CD-ROM means the folder was browsed
and then copied wholesale.

The format is JASC's, is not documented by JASC, and is not reverse-engineered
here beyond what the bytes state plainly. What this tool derives, and only
this:

  * the 16-byte ASCII signature `JASC BROWS FILE`;
  * the count of entries, if the header states one;
  * the file names, which are stored as plain 8.3 ASCII strings and can be
    recovered by scanning for them without decoding anything else.

Thumbnail pixel data is NOT decoded and no claim is made about its encoding.
The interesting question is not what the thumbnails look like: it is WHICH
files the cache names, because a cache can outlive the files it describes.

    python tools/jbf.py FILE
    python tools/jbf.py FILE --against DIR    which named files still exist
"""
import argparse
import os
import re
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--against", help="directory the cache should describe")
    a = ap.parse_args()

    d = open(a.path, "rb").read()
    print("file        : %s" % os.path.basename(a.path))
    print("size        : %d bytes" % len(d))
    print("first 32    : %s" % " ".join("%02X" % c for c in d[:32]))
    sig = d[:15]
    print("signature   : %r  (%s)"
          % (sig.decode("latin-1"),
             "JASC BROWS FILE" if sig == b"JASC BROWS FILE" else "UNEXPECTED"))
    print("bytes 16-40 : %s" % " ".join("%02X" % c for c in d[16:40]))

    # 8.3 names in the DOS character set, upper case, with a known image
    # extension. Deliberately narrow: a loose pattern finds strings inside
    # thumbnail data and invents files.
    # Names in this cache are mixed case, 8.3, and each is followed immediately
    # by a three-letter tag that is its own extension reversed: `Waitscr.lbm`
    # then `MBL`, `Mouseptr.bbm` then `MBB`. The tag is required by the pattern
    # and checked below, because without it the scan finds byte sequences
    # inside thumbnail data and invents files that were never there.
    pat = re.compile(
        rb"([A-Za-z0-9_~-]{1,8}\.(?:bmp|gif|jpg|tif|pcx|lbm|bbm|png|tga|iff|"
        rb"BMP|GIF|JPG|TIF|PCX|LBM|BBM|PNG|TGA|IFF))([A-Za-z]{3})")
    names = []
    seen = set()
    for m in pat.finditer(d):
        n = m.group(1).decode("latin-1")
        ext = n.rsplit(".", 1)[1]
        # group(2) is bytes and ext is str: comparing them directly is always
        # unequal and silently drops every record. This cost twenty minutes
        # and is exactly the failure the branch keeps warning about -- a
        # filter that rejects everything looks the same as a file with
        # nothing in it.
        if m.group(2).decode("latin-1").lower() != ext[::-1].lower():
            continue
        if n not in seen:
            seen.add(n)
            names.append((n, m.start()))
    print("names found : %d distinct" % len(names))
    if names:
        span = names[-1][1] - names[0][1]
        print("  first at offset %d, last at %d, span %d bytes"
              % (names[0][1], names[-1][1], span))
        if len(names) > 1:
            step = span / float(len(names) - 1)
            print("  mean spacing %.1f bytes -- %s"
                  % (step,
                     "regular, so this is a record array"
                     if abs(step - round(step)) < 2 else "irregular"))
    print()
    for n, off in names:
        print("  %6d  %s" % (off, n))

    if a.against:
        have = set()
        for r, ds, fs in os.walk(a.against):
            for f in fs:
                have.add(f.upper())
        miss = [n for n, _ in names if n.upper() not in have]
        print()
        print("checked against %s" % a.against)
        print("  named and present : %d" % (len(names) - len(miss)))
        print("  named and ABSENT  : %d" % len(miss))
        for n in miss:
            print("    %s" % n)


if __name__ == "__main__":
    main()
