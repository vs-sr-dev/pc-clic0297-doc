#!/usr/bin/env python3
"""twodiscs.py -- put this disc's numbers next to pc-harrypotter1-doc's.

That repository's disc is not in a drive and that session did not publish a
hash list, so a file-by-file comparison is impossible (see docs/15). What is
possible is a comparison of *published measurements*, and the honest way to do
it is to make the citation checkable: every figure quoted from the other
repository is stored here together with the document it was published in and a
pattern that must still occur in that document. If the pattern stops matching,
this tool says so instead of quoting a number that has been edited away.

    python tools/twodiscs.py
    python tools/twodiscs.py --hp1 ../pc-harrypotter1-doc

Nothing here reads the other disc. It reads the other repository's prose.
"""
import argparse
import os
import re
import sys

# (axis, HP1 value, HP1 source document, a literal that must occur in it,
#  this disc's value, the command that produces it)
ROWS = [
    ("medium", "CD-ROM", "README.md", "PC CD-ROM",
     "DVD-ROM, single layer", "tools/spti.py E"),
    ("volume identifier", "HARRY_POTTER_SIP_2210B", "README.md", "HARRY_POTTER_SIP_2210B",
     "HPGOF", "tools/vds.py E"),
    ("sectors declared", "292,173", "README.md", "292,173",
     "671,664", "tools/vds.py E"),
    ("bytes", "598,370,304", "README.md", "598,370,304",
     "1,375,567,872", "tools/vds.py E"),
    ("files", "540", "README.md", "540 files",
     "1,659", "tools/census.py _work/iso"),
    ("folders", "30", "README.md", "in 30 folders",
     "40", "tools/census.py _work/iso"),
    ("lead-out minus volume", "150", "docs/02-one-hundred-and-fifty.md", "292,323",
     "0", "tools/toc.py E"),
    ("volume descriptors", "4, two of them primary",
     "docs/03-two-primaries.md", "sector 17 : type 1",
     "3 CD001 + a UDF recognition sequence at 19-21", "tools/vds.py E, tools/udf.py E"),
    ("second filesystem", "none", "docs/03-two-primaries.md", "Joliet",
     "UDF 1.02, complete, agreeing file for file", "tools/udf.py E"),
    ("PVD hidden payload", "388 bytes at +1139, 344 non-zero",
     "docs/03-two-primaries.md", "payload length  : 388 bytes",
     "267 bytes at +1139, 200 non-zero", "tools/vdpayload.py E"),
    ("of which disc boundaries", "6 of 12 integers",
     "docs/03-two-primaries.md", "Six of the twelve",
     "0 of 12; ten slots are zero", "tools/vdmatch.py E notes/isodev-extents.txt"),
    ("ISO text fields filled", "0 of 5", "docs/03-two-primaries.md", "identifiers",
     "2 of 5 (system id, preparer), both naming GEAR", "tools/vds.py E"),
    ("GMT offset split", "descriptor 0, records 4",
     "docs/09-four-clocks-and-an-offset.md", "571 records",
     "descriptor 4, all 1,698 records 4", "tools/isodev.py E --tz"),
    ("clocks", "4", "docs/09-four-clocks-and-an-offset.md", "Four clocks",
     "6", "tools/clocks4.py E"),
    ("unreadable region", "9,280 sectors, LBA 818..10,097",
     "docs/06-nine-thousand-three-hundred-and-forty-three.md", "9,280",
     "none, over a full pass", "tools/sweep.py E"),
    ("read quantum", "64 sectors (failure granularity, on CD)",
     "docs/06-nine-thousand-three-hundred-and-forty-three.md", "64 sectors",
     "16 sectors (access granularity, on DVD)", "tools/window2.py E"),
    ("SafeDisc version", "2.40.010", "docs/08-safedisc-2-40-010.md", "2.40.010",
     "4.50.000", "tools/bog.py _work/iso/DIAG.EXE"),
    ("occurrences of 'Macrovision'", "0 in 540 files",
     "docs/08-safedisc-2-40-010.md", "Macrovision",
     "10 (7 outside the zip, 3 in it), all UTF-16", "tools/hunt2.py"),
    ("00000001.TMP", "2,048 bytes (1 sector)", "docs/08-safedisc-2-40-010.md",
     "00000001.TMP", "20,482,048 bytes (10,001 sectors)", "tools/sdtmp.py E"),
    ("00000002.TMP", "317,440 bytes, entropy -0.0000, 1 of 256 byte values",
     "docs/08-safedisc-2-40-010.md", "00000002.TMP   317440 bytes  entropy -0.0000",
     "317,440 bytes, 26.01 % zero, entropy 6.7263", "tools/tmp2.py E"),
    ("engine", "Unreal Engine 1, 249 packages", "README.md", "Unreal Engine 1",
     "RenderWare + RealCore 6.27.01 + RealGraph 6 + Havok, named in one exe",
     "tools/hunt2.py, tools/machpaths2.py"),
    ("game data layout", "540 loose files in 30 folders", "README.md", "540 files",
     "1 zip -> 4 BIG archives -> 715 files", "tools/zipdir.py, tools/big.py"),
    ("linker", "6.0 on 20 of 28 binaries", "docs/21-against-eight-trees.md",
     "PE i386, linker 6.0", "7.10 on 12 of 14; 6.00 on 2",
     "tools/pecensus.py _work/iso"),
    ("studio named on the disc", "once, in a machine path",
     "docs/19-dhunt-knowwonder.md", "KnowWonder",
     "never; three middleware vendors instead", "tools/hunt2.py"),
    ("language axes", "15, no language on all of them",
     "docs/17-twenty-five-languages.md", "fifteen",
     "10, four languages on all of them", "tools/langaxes.py _work/nozip"),
    ("written for this disc", "89.09 % by bytes", "docs/20-whose-disc.md", "89.09",
     "94.62 % by bytes, 51.60 % by file count", "tools/whose4.py _work/iso"),
    ("files matching another disc", "0 of 16,434 compared",
     "docs/21-against-eight-trees.md", "16,434",
     "0 of 17,553 files in nine trees", "tools/discdiff.py"),
    ("mastering house", "unnamed", "docs/03-two-primaries.md", "identifiers",
     "GEAR, 1,717 times", "tools/gearcount.py E"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hp1", default="../pc-harrypotter1-doc")
    a = ap.parse_args()

    cache = {}
    ok = bad = 0
    print("| axis | pc-harrypotter1-doc (2001) | this disc (2005) |")
    print("|---|---|---|")
    problems = []
    for axis, v1, doc, needle, v4, cmd in ROWS:
        p = os.path.join(a.hp1, doc)
        if p not in cache:
            try:
                cache[p] = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                cache[p] = None
        text = cache[p]
        if text is None:
            problems.append((axis, doc, "document not found"))
            bad += 1
        elif needle not in text:
            problems.append((axis, doc, "literal %r no longer occurs" % needle))
            bad += 1
        else:
            ok += 1
        print("| %s | %s | %s |" % (axis, v1, v4))

    print()
    print("citation check: %d of %d figures still occur in the document cited"
          % (ok, ok + bad))
    for axis, doc, why in problems:
        print("  !! %-28s %-46s %s" % (axis, doc, why))
    print()
    print("commands for this disc's column:")
    for axis, v1, doc, needle, v4, cmd in ROWS:
        print("  %-30s %s" % (axis, cmd))
    print()
    print("sources for the other column:")
    for d in sorted({r[2] for r in ROWS}):
        print("  %s" % os.path.join(a.hp1, d).replace(chr(92), "/"))


if __name__ == "__main__":
    main()
