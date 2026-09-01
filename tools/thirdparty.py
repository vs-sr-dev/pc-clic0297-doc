#!/usr/bin/env python3
"""thirdparty.py -- how much of this disc is somebody else's software.

Grande Fratello (2003) shipped DirectX 8.1 four times over and it was 15.57 %
of the disc. Lucignolo (2007) shipped DirectX 9.0c and it was 3.15 %. This disc
is 1999 and the same question has a much bigger answer, so it is worth asking
carefully rather than quoting one directory's share and calling it done.

THE DENOMINATOR IS THE WHOLE POINT.

This material is the DATA SESSION of a CD Extra, copied to a filesystem. It is
not the disc. The disc also carries a first session with ten audio tracks, and
that session is not here. So every percentage this tool prints is over
222,271,591 bytes of data track, and it says so on every line, because the same
numerator over a whole-disc denominator would be roughly half as large and
would still look like a real number.

WHAT COUNTS AS SOMEBODY ELSE'S.

Three tiers, printed separately, because they are three different claims:

  tier 1  REDISTRIBUTED INSTALLERS -- Microsoft's Internet Explorer 5 package,
          Apple's QuickTime 3 installers for both platforms. Nobody involved in
          making this CD-ROM wrote a byte of it. Unambiguous.
  tier 2  ENGINE RUNTIME shipped inside the product -- the Macromedia Director
          player embedded in the two projectors, and the Xtras beside them. A
          projector is 93 % runtime by bytes; that runtime is Macromedia's
          code, but it is not a redistributable the user installs, it is the
          product's own skin. Counted separately for that reason.
  tier 3  AUTHORED CONTENT -- everything left. Movies, bitmaps, sounds,
          scripts, panoramas, the Blue Book directories.

The projector split needs a number, not an assumption: for a Director
projector the runtime is the PE sections plus whatever precedes the embedded
movie, and the authored part is the embedded Director container. `director.py`
reports the container's offset, so the split is measured per file rather than
guessed at.

    python tools/thirdparty.py DIR
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import director as dirmod     # noqa: E402

# Tier 1: paths (prefix match, forward slashes, case-insensitive) that are
# wholly redistributed third-party installers.
TIER1 = [
    ("dati/install/win32/", "Microsoft Internet Explorer 5 (Italian, Tiscali-branded)"),
    ("dati/install/ie45.sea", "Microsoft Internet Explorer 4.5 for Macintosh"),
    ("dati/install/qtime30.exe", "Apple QuickTime 3 installer, Windows"),
    ("dati/install/macintosh/", "Apple QuickTime 3 installer, Macintosh"),
    ("dati/install/cdsetup.exe", "Microsoft IE setup stub"),
    ("dati/install/autorun.inf", "Microsoft IE setup stub"),
]

# Tier 2: engine runtime that ships as part of the product.
TIER2_WHOLE = [
    ("dati/xtras/rvrplay.x32", "Live Picture / RealVR Xtra"),
    ("xtras/cdpro.x32", "Penworks CD Pro Xtra"),
    ("xtras/fileio.x32", "Macromedia FileIO Xtra"),
]
TIER2_PROJECTORS = ["883.exe", "dati/vr.exe"]

# Tier 2 partial: 883d.exe is a VISE installer wrapping the Activeworlds client.
# The client is third-party; the installer stub and the Italian dialog text are
# not. The payload is compressed and this tool does not decompress it, so the
# whole file is reported on its own line rather than split on a guess.
TIER2_NOTE = [("dati/install/883d.exe",
               "MindVision VISE stub + Activeworlds client payload (not split)")]


def walk(root):
    out = []
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for f in sorted(fn):
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            out.append((rel, rel.lower(), os.path.getsize(full)))
    return out


def projector_split(path):
    """(runtime bytes, authored bytes) for a Director projector."""
    data = open(path, "rb").read()
    hits = dirmod.find_overlays(data)
    if not hits:
        return len(data), 0
    off = hits[0][0]
    return off, len(data) - off


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

    rows = walk(args.dir)
    total = sum(r[2] for r in rows)

    print("DENOMINATOR")
    print("  data track, as copied : %d bytes in %d files" % (total, len(rows)))
    print("  audio session         : NOT PRESENT in this material")
    print("  whole disc            : unknown; every share below is over the")
    print("                          data track only, and is therefore an")
    print("                          upper bound on the whole-disc share.")
    print()

    claimed = set()

    print("TIER 1 -- redistributed third-party installers")
    print("%-46s %11s %8s" % ("path prefix", "bytes", "share"))
    print("-" * 46 + " " + "-" * 11 + " " + "-" * 8)
    t1 = 0
    for prefix, label in TIER1:
        b = n = 0
        for rel, low, size in rows:
            if low.startswith(prefix) and rel not in claimed:
                claimed.add(rel)
                b += size
                n += 1
        t1 += b
        print("%-46s %11d %7.3f%%   %s"
              % (prefix + "  (%d files)" % n, b, 100.0 * b / total, label))
    print("-" * 46 + " " + "-" * 11 + " " + "-" * 8)
    print("%-46s %11d %7.3f%%" % ("TIER 1 TOTAL", t1, 100.0 * t1 / total))
    print()

    print("TIER 2 -- engine runtime shipped inside the product")
    print("%-46s %11s %8s" % ("file", "bytes", "share"))
    print("-" * 46 + " " + "-" * 11 + " " + "-" * 8)
    t2 = 0
    for prefix, label in TIER2_WHOLE:
        for rel, low, size in rows:
            if low == prefix and rel not in claimed:
                claimed.add(rel)
                t2 += size
                print("%-46s %11d %7.3f%%   %s"
                      % (rel, size, 100.0 * size / total, label))
    authored_in_projectors = 0
    for prefix in TIER2_PROJECTORS:
        for rel, low, size in rows:
            if low == prefix and rel not in claimed:
                claimed.add(rel)
                rt, au = projector_split(os.path.join(args.dir, rel))
                t2 += rt
                authored_in_projectors += au
                print("%-46s %11d %7.3f%%   Director runtime (of %d total; "
                      "%d bytes are the embedded movie)"
                      % (rel + " [runtime part]", rt, 100.0 * rt / total,
                         size, au))
    print("-" * 46 + " " + "-" * 11 + " " + "-" * 8)
    print("%-46s %11d %7.3f%%" % ("TIER 2 TOTAL", t2, 100.0 * t2 / total))
    print()

    print("REPORTED SEPARATELY -- mixed, not split")
    t_mix = 0
    for prefix, label in TIER2_NOTE:
        for rel, low, size in rows:
            if low == prefix and rel not in claimed:
                claimed.add(rel)
                t_mix += size
                print("%-46s %11d %7.3f%%   %s"
                      % (rel, size, 100.0 * size / total, label))
    print()

    rest = [(rel, size) for rel, low, size in rows if rel not in claimed]
    t3 = sum(s for _, s in rest) + authored_in_projectors
    print("TIER 3 -- authored content")
    print("  files                 : %d" % len(rest))
    print("  bytes                 : %d  (includes %d bytes of embedded"
          % (t3, authored_in_projectors))
    print("                          Director movie recovered from the projectors)")
    print("  share of data track   : %.3f %%" % (100.0 * t3 / total))
    print()

    print("SUMMARY (denominator: %d bytes of data track)" % total)
    print("  tier 1 redistributed  : %11d   %7.3f %%" % (t1, 100.0 * t1 / total))
    print("  tier 2 engine runtime : %11d   %7.3f %%" % (t2, 100.0 * t2 / total))
    print("  883d.exe (mixed)      : %11d   %7.3f %%"
          % (t_mix, 100.0 * t_mix / total))
    print("  tier 3 authored       : %11d   %7.3f %%" % (t3, 100.0 * t3 / total))
    print("  ------------------------------------------------------")
    print("  checksum              : %11d   %7.3f %%"
          % (t1 + t2 + t_mix + t3, 100.0 * (t1 + t2 + t_mix + t3) / total))
    print()
    print("  'somebody else's software', tiers 1+2  : %.3f %% of the data track"
          % (100.0 * (t1 + t2) / total))
    print("  the same, counting 883d.exe as well    : %.3f %%"
          % (100.0 * (t1 + t2 + t_mix) / total))
    print()
    print("  For comparison with the briefing's starting figure: the whole of")
    print("  dati/install is %d bytes = %.3f %% of the data track."
          % (sum(s for rel, low, s in rows if low.startswith("dati/install/")),
             100.0 * sum(s for rel, low, s in rows
                         if low.startswith("dati/install/")) / total))


if __name__ == "__main__":
    main()
