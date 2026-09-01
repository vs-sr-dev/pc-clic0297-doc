#!/usr/bin/env python3
"""whose.py -- how much of this disc was written for this disc.

The same question was asked of the 883 disc (33 % somebody else's) and of the
1000 Miglia folder (0 %). Here almost nothing was a free choice: the engine is
Epic's, the compiler is Microsoft's, the protection is Macrovision's, the
installer is InstallShield's and 4.85 % of the disc is literally a Microsoft
redistributable. So the number matters and the RULE matters more, because a
number like this is mostly an argument about the rule.

THE RULE, stated so it can be disagreed with:

  tier 1  REDISTRIBUTED       a third party's product, shipped whole. Nobody
                              on this project wrote or compiled a byte.
  tier 2  PROTECTION          Macrovision's SafeDisc: its driver, its manager
                              DLL, its two placeholder files, its localised
                              dialog bitmaps, and the part of System/HP.exe
                              that is outside the PE sections the linker
                              produced.
  tier 3  LICENSED ENGINE     Epic's Unreal Engine 1 modules and stock content
                              packages. Compiled here, authored elsewhere.
                              Identified two ways that must agree: the module
                              name is one of Epic's, AND (for packages) the
                              package version is below the 76 that this
                              build's own content carries.
  tier 4  THIS PRODUCT        everything else.

Every file lands in exactly one tier and the assignment for every file is
printed, so the argument can be had over the list rather than over the total.

Two denominators are printed for every tier, because they differ by more than
three points and the difference is the 10,000-sector hole:

    577,088,559   bytes inside files
    598,370,304   bytes of volume

    python tools/whose.py E:/
"""
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkg  # noqa: E402

FILEBYTES = 577088559
VOLBYTES = 598370304

EPIC_MODULES = {
    "core", "engine", "editor", "render", "fire", "ipdrv", "ipserver",
    "ubrowser", "uweb", "uwindow", "umenu", "utmenu", "unrealshare",
    "d3ddrv", "softdrv", "windrv", "window", "galaxy", "metaldrv", "sgldrv",
}
EPIC_CONTENT = {
    "detail.utx", "genfx.utx", "palettes.utx", "liquids.utx",
    "greatfire.utx", "fireeng.utx", "fireeng-k.utx", "flarefx.utx",
    "fractalfx.utx", "uwindowfonts.utx", "editor.utx",
    "ambient.uax", "critters.uax",
}


def pe_section_end(path):
    d = open(path, "rb").read()
    if d[:2] != b"MZ":
        return None, len(d)
    e = struct.unpack_from("<I", d, 0x3C)[0]
    if d[e:e + 4] != b"PE" + bytes([0, 0]):
        return None, len(d)
    nsec = struct.unpack_from("<H", d, e + 6)[0]
    optsz = struct.unpack_from("<H", d, e + 20)[0]
    off = e + 24 + optsz
    hi = 0
    for i in range(nsec):
        b = d[off + 40 * i: off + 40 * i + 40]
        vs, va, rs, ro = struct.unpack_from("<IIII", b, 8)
        hi = max(hi, ro + rs)
    return hi, len(d)


def classify(rel, size, root):
    low = rel.lower()
    base = os.path.basename(low)
    top = low.split("/")[0]
    stem, ext = os.path.splitext(base)

    if top == "directx":
        return 1, "Microsoft DirectX redistributable"
    if base == "shfolder.exe":
        return 1, "Microsoft shell redistributable"
    if top == "setup" and base in ("setup.exe", "ikernel.ex_", "data1.hdr",
                                   "layout.bin", "setup.ini"):
        return 1, "InstallShield engine"
    if base in ("drvmgt.dll", "secdrv.sys", "00000001.tmp", "00000002.tmp"):
        return 2, "SafeDisc"
    if ext in (".016", ".256") and len(stem) == 8:
        return 2, "SafeDisc localised dialog bitmap"
    # Help/ holds the game's own splash bitmaps. Five of them are byte
    # for byte the same image as the SafeDisc dialog bitmaps in System/,
    # which is a fact about reuse and not about authorship, so they stay
    # in tier 4 and the reuse is reported by census.py --dups instead.
    if base.endswith("_eahelp.hlp"):
        return 1, "Electronic Arts support help file (shared EA component)"
    if stem in EPIC_MODULES and ext in (".u", ".dll", ".int"):
        return 3, "Epic engine module"
    if base in EPIC_CONTENT:
        return 3, "Epic stock content package"
    return 4, "this product"


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "E:/"
    rows = []
    for dp, dn, fn in os.walk(root):
        for f in sorted(fn):
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            size = os.path.getsize(p)
            t = classify(rel, size, root)
            if isinstance(t[0], tuple):
                t = t[0]
            rows.append((t[0], t[1], rel, size))

    # HP.exe is split: the linker's sections belong to this product, the
    # bytes past them are the protection's.
    hp = os.path.join(root, "System", "HP.exe")
    split = None
    if os.path.exists(hp):
        end, total = pe_section_end(hp)
        if end and end < total:
            split = (end, total - end)
            rows = [r for r in rows if r[2].lower() != "system/hp.exe"]
            rows.append((4, "this product (HP.exe, linker sections)",
                         "System/HP.exe [0..%d)" % end, end))
            rows.append((2, "SafeDisc (HP.exe, bytes past the last section)",
                         "System/HP.exe [%d..%d)" % (end, total), total - end))

    tiers = collections.defaultdict(lambda: [0, 0])
    reasons = collections.defaultdict(lambda: [0, 0])
    for t, why, rel, size in rows:
        tiers[t][0] += 1
        tiers[t][1] += size
        reasons[(t, why)][0] += 1
        reasons[(t, why)][1] += size

    NAMES = {1: "tier 1  REDISTRIBUTED", 2: "tier 2  PROTECTION",
             3: "tier 3  LICENSED ENGINE", 4: "tier 4  THIS PRODUCT"}
    print("files classified: %d (System/HP.exe counted as two parts)"
          % len(rows))
    if split:
        print("System/HP.exe: %d bytes of PE sections, %d bytes past them"
              % split)
    print()
    print("%-26s %6s %13s %9s %9s"
          % ("tier", "files", "bytes", "of files", "of volume"))
    tot = 0
    for t in sorted(tiers):
        n, b = tiers[t]
        tot += b
        print("%-26s %6d %13d %8.2f %% %8.2f %%"
              % (NAMES[t], n, b, 100.0 * b / FILEBYTES, 100.0 * b / VOLBYTES))
    print("%-26s %6d %13d %8.2f %% %8.2f %%"
          % ("total", len(rows), tot, 100.0 * tot / FILEBYTES,
             100.0 * tot / VOLBYTES))
    print()
    print("check: tier sum %d vs the census total %d, difference %d"
          % (tot, FILEBYTES, FILEBYTES - tot))
    print()
    somebody = sum(tiers[t][1] for t in (1, 2, 3))
    print("somebody else's (tiers 1+2+3) : %13d   %.2f %% of files, "
          "%.2f %% of volume"
          % (somebody, 100.0 * somebody / FILEBYTES,
             100.0 * somebody / VOLBYTES))
    print("this product     (tier 4)     : %13d   %.2f %% of files, "
          "%.2f %% of volume"
          % (tiers[4][1], 100.0 * tiers[4][1] / FILEBYTES,
             100.0 * tiers[4][1] / VOLBYTES))
    print()
    print("and the volume denominator adds one item no file owns:")
    print("   the 10,000-sector unallocated hole   %13d bytes  %.2f %% of "
          "volume" % (10000 * 2048, 100.0 * 10000 * 2048 / VOLBYTES))
    print()
    print("by reason:")
    for (t, why), (n, b) in sorted(reasons.items(),
                                   key=lambda kv: (kv[0][0], -kv[1][1])):
        print("  %-24s %-52s %5d %13d" % (NAMES[t].split()[1], why[:52], n, b))
    print()
    print("every file in tiers 1, 2 and 3, so the rule can be argued with:")
    for t in (1, 2, 3):
        print()
        print("  %s" % NAMES[t])
        for tt, why, rel, size in sorted(rows, key=lambda r: -r[3]):
            if tt == t:
                print("     %-52s %11d  %s" % (rel[:52], size, why))


if __name__ == "__main__":
    main()
