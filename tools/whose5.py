#!/usr/bin/env python3
"""whose5.py -- how much of this disc was written for this disc.

whose.py (from pc-harrypotter1-doc) names Epic's Unreal modules; whose4.py
(from pc-harrypotter4-doc) names DIAG.EXE, the two SafeDisc .TMP files and a
Visual C++ 7.1 runtime shipped twice. None of those objects exists here, so
both would print a number that is right for the wrong reasons. The rule is
restated for this object, and, as on the previous disc, the answer is reported
twice -- by bytes and by file count -- because the two disagree and the
disagreement is the finding.

THE RULE, stated so it can be argued with:

  tier 1  REDISTRIBUTED     a third party's product shipped whole: Microsoft's
                            DirectX 9.0c installer (DirectX\\), the Visual C++
                            2005 runtime and the Windows Installer update
                            (VCRedist\\), and the two Microsoft Games Explorer
                            DLLs at the root, one of which is literally named
                            GDFExampleBinary.
  tier 2  PROTECTION        nothing on this disc, outside the archive, belongs
                            to a protection vendor. The SecuROM wrapper is
                            four sections inside hp.exe, which is inside a zip
                            member, and is not counted here -- which
                            understates this tier exactly as the previous
                            disc's accounting understated its own.
  tier 3  HELP RUNTIME      the RoboHelp WebHelp furniture: its skin GIFs and
                            JPEGs, its two stylesheets, its build logs. The
                            .htm topic files are NOT in this tier: their text
                            is this publisher's, even where the generator laid
                            it out.
  tier 4  PUBLISHER COMMON  Electronic Arts components that are the same on
                            every EA title of the period: the AutoRun shell
                            and its GUI DLL, the installer and uninstaller
                            DLLs, the electronic-registration dictionary, and
                            Localization.ini -- which is demonstrably a
                            template, since its commented-out section still
                            carries another franchise's patch URLs.
  tier 5  THIS PRODUCT      everything left.

Two things this tool refuses to do:

  * it does not guess. A file it cannot place by path or name lands in tier 5
    and is listed, so an over-generous tier 5 is visible rather than assumed;
  * it does not count the two ZIP archives as one file each and stop there.
    They are reported both ways -- in, and out -- because 97.94 % of this disc
    is inside them and any single number that includes them is a number about
    a container.

    python tools/whose5.py _work/iso
    python tools/whose5.py _work/iso --zip-bytes 3659430452
    python tools/whose5.py _work/iso --list
"""
import argparse
import os

TIERS = ["", "REDISTRIBUTED", "PROTECTION", "HELP RUNTIME",
         "PUBLISHER COMMON", "THIS PRODUCT"]

HELP_FURNITURE_EXT = (".gif", ".jpg", ".jpeg", ".css", ".log", ".db")

EA_COMMON = {
    "autorun.exe", "autorungui.dll", "eainstall.dll", "eauninstall.exe",
    "ereg-dict.bin", "localization.ini",
}


def tier_of(rel):
    low = rel.lower().replace(chr(92), "/")
    base = low.rsplit("/", 1)[-1]
    top = low.split("/", 1)[0]

    if top in ("directx", "vcredist"):
        return 1, "third-party installer tree"
    if base in ("gdfexamplebinary.dll", "gameuxinstallhelper.dll"):
        return 1, "Microsoft Games Explorer helper"

    if low.startswith("support/european help files/"):
        if base.endswith(HELP_FURNITURE_EXT):
            return 3, "help generator furniture (%s)" % base.rsplit(".")[-1]
        return 5, "help topic text"

    if base in EA_COMMON:
        return 4, "EA installer component"
    if base.endswith("_code.exe") or base.endswith("_uninst.exe"):
        return 4, "EA electronic-registration component"

    return 5, "written for this product"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--zip-bytes", type=int, default=0,
                    help="bytes of the archives, counted as tier 5 when given")
    ap.add_argument("--zip-files", type=int, default=0)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    rows = []
    for r, dirs, names in os.walk(a.root):
        dirs.sort()
        for name in sorted(names):
            p = os.path.join(r, name)
            rel = os.path.relpath(p, a.root).replace(chr(92), "/")
            t, why = tier_of(rel)
            rows.append((t, why, os.path.getsize(p), rel))

    tot_b = sum(r[2] for r in rows)
    tot_n = len(rows)
    print("tree                : %s" % a.root)
    print("files               : %d" % tot_n)
    print("bytes               : %d" % tot_b)
    print()
    print("  %-4s %-18s %7s %8s %14s %8s" %
          ("tier", "name", "files", "% files", "bytes", "% bytes"))
    for t in range(1, 6):
        sel = [r for r in rows if r[0] == t]
        b = sum(r[2] for r in sel)
        print("  %-4d %-18s %7d %7.2f%% %14d %7.2f%%"
              % (t, TIERS[t], len(sel), 100.0 * len(sel) / tot_n, b,
                 100.0 * b / tot_b if tot_b else 0))
    five = [r for r in rows if r[0] == 5]
    print()
    print("WITHOUT the archives (the %d files that are loose on the disc):"
          % tot_n)
    print("  written for this disc, by bytes      : %.2f %%"
          % (100.0 * sum(r[2] for r in five) / tot_b))
    print("  written for this disc, by file count : %.2f %%"
          % (100.0 * len(five) / tot_n))

    if a.zip_bytes:
        b2 = tot_b + a.zip_bytes
        n2 = tot_n + (a.zip_files or 2)
        b5 = sum(r[2] for r in five) + a.zip_bytes
        n5 = len(five) + (a.zip_files or 2)
        print()
        print("WITH the archives counted as tier 5 (%d bytes in %d files):"
              % (a.zip_bytes, a.zip_files or 2))
        print("  written for this disc, by bytes      : %.2f %%"
              % (100.0 * b5 / b2))
        print("  written for this disc, by file count : %.2f %%"
              % (100.0 * n5 / n2))
        print()
        print("  The two numbers are %.2f points apart. Which one is 'the"
              % abs(100.0 * b5 / b2 - 100.0 * n5 / n2))
        print("  disc' is a question about what a file is, not a measurement.")

    if a.list:
        print()
        for t in range(1, 6):
            sel = [r for r in rows if r[0] == t]
            print("--- tier %d %s (%d files) ---" % (t, TIERS[t], len(sel)))
            shown = sel if t != 5 else sel[:40]
            for _t, why, sz, rel in shown:
                print("  %10d  %-58s %s" % (sz, rel[:58], why))
            if len(sel) > len(shown):
                print("  ... and %d more" % (len(sel) - len(shown)))
            print()


if __name__ == "__main__":
    main()
