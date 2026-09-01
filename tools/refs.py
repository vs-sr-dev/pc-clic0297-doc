#!/usr/bin/env python3
"""refs.py -- every filename the program names, and whether it is here.

This folder is not a product: it is one installed copy of a March 1992 BBS
distribution. So the question "is anything missing" is not rhetorical, and it
has a cheap answer: the executables and the overlay name the files they open,
in Turbo Pascal string literals, and every name they use can be checked against
the directory listing.

A name that resolves is evidence the distribution is complete for that file.
A name that does not resolve is either a file that was never shipped in this
form, or one that this copy lost.

The scan is deliberately conservative. It takes printable runs, then keeps only
those that look like DOS 8.3 names -- one to eight characters from the DOS name
set, optionally a dot and one to three more -- and rejects the ones whose
extension is not one this folder or the era uses. It then reports:

  * names that exist in the folder (case-insensitively),
  * names that do not,
  * and, separately, the *stems* used without an extension, because the game
    builds `IntroVga` + `.FL` at run time and the string in the binary is the
    stem alone.

  usage: refs.py <dir>
"""
import os
import re
import sys

RUN = re.compile(rb"[\x20-\x7e]{3,}")
NAME = re.compile(r"^[A-Za-z0-9_\-]{1,8}\.[A-Za-z0-9]{1,3}$")

# extensions worth believing in: the ones this folder uses, plus the DOS
# staples a 1992 program might open.
KNOWN = set("""FL POS PTS CT4 EXE OVR LLL CT4 IMV ICV CHV PAL POL CEL PIL COR
AUT MM NFO CNF BAT COM SYS DAT CFG TXT DOC BIN MID SND VOC DRV DIC IDX SAV
HLP INI LST""".split())


def runs(path):
    d = open(path, "rb").read()
    for m in RUN.finditer(d):
        yield m.start(), m.group().decode("cp437", "replace")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = sys.argv[1]
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    present = {n.upper() for n in os.listdir(root)}
    stems = {os.path.splitext(n)[0].upper() for n in os.listdir(root)}

    found = {}
    for n in sorted(os.listdir(root)):
        p = os.path.join(root, n)
        if os.path.getsize(p) > 4 * 1024 * 1024:
            continue
        for off, s in runs(p):
            # a Pascal literal may be embedded inside a longer printable run,
            # so scan the run for 8.3-shaped substrings too
            for cand in re.findall(r"[A-Za-z0-9_\-]{1,8}\.[A-Za-z0-9]{1,3}", s):
                if not NAME.match(cand):
                    continue
                ext = cand.rsplit(".", 1)[1].upper()
                if ext not in KNOWN:
                    continue
                found.setdefault(cand.upper(), []).append((n, off))

    hit = sorted(k for k in found if k in present)
    miss = sorted(k for k in found if k not in present)

    print("=== filenames named inside the material ===")
    print("resolved to a file in the folder : %d" % len(hit))
    for k in hit:
        where = ", ".join("%s+0x%X" % (a, b) for a, b in found[k][:3])
        print("  %-16s %s" % (k, where))
    print("")
    print("NOT present in the folder        : %d" % len(miss))
    for k in miss:
        where = ", ".join("%s+0x%X" % (a, b) for a, b in found[k][:3])
        print("  %-16s %s" % (k, where))
    print("")

    print("=== container stems named without an extension ===")
    print("(the game concatenates the stem with '.FL' at run time)")
    for stem in ("IntroVga", "MenuVga", "ArcadVga", "FinalVga", "AutoVga",
                 "BmapVga", "Musiche", "MUSICHE"):
        hits = []
        for n in sorted(os.listdir(root)):
            d = open(os.path.join(root, n), "rb").read()
            if stem.encode() in d:
                hits.append("%s+0x%X" % (n, d.find(stem.encode())))
        print("  %-10s in folder: %-3s   named in: %s"
              % (stem, "yes" if stem.upper() in stems else "no",
                 ", ".join(hits) or "nowhere"))
    print("")

    print("=== words that name a program this folder does not contain ===")
    for tok in (b"INSTALL", b"Install", b"install"):
        for n in sorted(os.listdir(root)):
            d = open(os.path.join(root, n), "rb").read()
            i = d.find(tok)
            while i >= 0:
                ctx = d[max(0, i - 60):i + 70]
                print("  %-14s +0x%-6X %r" % (n, i, ctx.decode("cp437", "replace")))
                i = d.find(tok, i + 1)


if __name__ == "__main__":
    main()
