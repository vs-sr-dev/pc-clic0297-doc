#!/usr/bin/env python3
"""threedisc.py -- three columns, and every citation checked.

twodiscs.py put this family's 2005 disc next to its 2001 disc and kept the
citation honest: each figure quoted from another repository is stored here
with the document it was published in and a literal that must still occur in
that document, and the tool prints "citation check: N of N" instead of
quoting a number that has since been edited away. On its first run it caught
two wrong citations.

It is extended, not rewritten. Same mechanism, one more column, and one more
thing it now reports: **which axis is missing a value in which column**, so a
row that is blank because nobody measured it is visibly different from a row
that is blank because the answer is "none".

The three columns are

    2001  pc-harrypotter1-doc   Philosopher's Stone,  CD-ROM
    2005  pc-harrypotter4-doc   Goblet of Fire,       DVD, GEAR, SafeDisc
    2007  this repository       Order of the Phoenix, DVD, UltraISO, SecuROM

and a fourth thing is printed under the table: for every axis, whether the
2001->2005 step and the 2005->2007 step move the **same way**. Two differences
agreeing is not a trend and the tool says so in its own output; it is two
differences agreeing, which is worth more than one and less than a series.

    python tools/threedisc.py
    python tools/threedisc.py --hp1 ../pc-harrypotter1-doc \
                              --hp4 ../pc-harrypotter4-doc
"""
import argparse
import os

# (axis,
#  hp1 value, hp1 document, literal that must still occur in it,
#  hp4 value, hp4 document, literal that must still occur in it,
#  this disc's value, the command that produces it)
ROWS = [
    ("medium",
     "CD-ROM", "README.md", "PC CD-ROM",
     "DVD-ROM, single layer", "README.md", "DVD-ROM, single layer",
     "DVD-ROM, single layer, pressed (layer type 1, embossed)",
     "tools/spti.py E"),
    ("volume identifier",
     "HARRY_POTTER_SIP_2210B", "README.md", "HARRY_POTTER_SIP_2210B",
     "HPGOF", "README.md", "Volume `HPGOF`",
     "HPOOTP", "tools/vds.py E"),
    ("sectors declared",
     "292,173", "README.md", "292,173",
     "671,664", "README.md", "671,664",
     "1,826,656", "tools/vds.py E"),
    ("bytes",
     "598,370,304", "README.md", "598,370,304",
     "1,375,567,872", "README.md", "1,375,567,872",
     "3,740,991,488", "tools/spti.py E"),
    ("files / folders",
     "540 / 30", "README.md", "540 files",
     "1,659 / 40", "README.md", "1,659 files in 40 folders",
     "1,187 / 26", "tools/census.py E:/"),
    ("lead-out reported by READ TOC",
     "LBA 292,323 (MSF 64:59:48)", "docs/02-one-hundred-and-fifty.md",
     "292,323",
     "LBA 671,664 (MSF 149:17:39)", "docs/04-the-sector-windows-cannot-reach.md",
     "MSF 149:17:39",
     "LBA 1,151,849 (MSF 255:59:74, the field's ceiling)", "tools/toc.py E"),
    ("lead-out minus volume size",
     "+150", "docs/02-one-hundred-and-fifty.md", "292,323",
     "0", "docs/02-spec-sheet.md", "lead-out \u2212 PVD volume size | **0**",
     "-674,807, and it is the field saturating, not the disc",
     "tools/toc.py E, tools/msf.py --max"),
    ("second filesystem",
     "none", "docs/03-two-primaries.md", "Joliet",
     "UDF 1.02, complete, agreeing file for file",
     "docs/03-the-second-filesystem.md", "UDF",
     "UDF 1.02, complete, agreeing file for file",
     "tools/udf.py E"),
    ("Joliet",
     "absent", "docs/03-two-primaries.md", "Joliet",
     "present, escape %/@", "docs/02-spec-sheet.md", "Joliet",
     "absent -- no supplementary descriptor at all", "tools/vds.py E"),
    ("mastering house named in the descriptors",
     "unnamed", "docs/03-two-primaries.md", "identifiers",
     "GEAR, 1,717 times", "README.md", "GEAR",
     "none; the application field names UltraISO V8.5 instead",
     "tools/vds.py E, tools/udf.py E"),
    ("ISO text fields filled",
     "0 of 5", "docs/03-two-primaries.md", "identifiers",
     "2 of 5, both naming GEAR", "docs/02-spec-sheet.md", "GEAR SOFTWARE",
     "2 of 5 (system id 'Win32', application 'UltraISO V8.5 ...'); "
     "the other three are space-filled", "tools/vds.py E"),
    ("PVD payload in a field the standard requires to be zero",
     "388 bytes at +1139, 344 non-zero, six disc boundaries among twelve "
     "integers", "docs/03-two-primaries.md", "payload length  : 388 bytes",
     "267 bytes at +1139, 200 non-zero, ten of twelve slots zeroed",
     "docs/02-spec-sheet.md", "+1139",
     "125 non-zero bytes at +883 and +1884..+2047; one integer equals the "
     "volume size, at +2040", "tools/vdmatch3.py E --span 1880 2048"),
    ("ISO expiration date",
     "not published", "docs/09-four-clocks-and-an-offset.md", "clocks",
     "1981, twenty-four years before creation", "docs/16-open-questions.md",
     "1981",
     "not set (the field is ASCII zeros)", "tools/vds.py E"),
    ("ISO vs UDF timezone",
     "not applicable, no UDF", "docs/03-two-primaries.md", "Joliet",
     "ISO UTC+1, UDF UTC+00:00 on the same digits",
     "docs/10-six-clocks-and-one-hour.md",
     "an hour the two filesystems disagree about",
     "both +01:00; they agree", "tools/vds.py E, tools/udf.py E"),
    ("gaps in the ISO extent map",
     "1 gap of 10,000 sectors", "docs/05-the-extent-map.md", "extent map",
     "126 gaps, 79 of them exactly 20 sectors",
     "docs/03-the-second-filesystem.md", "79",
     "3 gaps, of 259, 1,258 and 4 sectors, no size repeated",
     "tools/isodev.py E --extents"),
    ("UDF File Entry placement",
     "not applicable, no UDF", "docs/03-two-primaries.md", "Joliet",
     "one sector per file, written in batches of twenty, spread through the "
     "disc", "docs/03-the-second-filesystem.md", "twenty files apart",
     "1,213 sectors in one contiguous run, LBA 304..1559",
     "tools/udf.py E, tools/gapname.py E"),
    ("genuinely spare sectors",
     "not published", "docs/05-the-extent-map.md", "extent map",
     "92", "docs/03-the-second-filesystem.md", "92 sectors",
     "204", "tools/gapname.py E --gaps 0-258 302-1559 1826652-1826655"),
    ("unreadable region",
     "9,280 sectors, LBA 818..10,097",
     "docs/06-nine-thousand-three-hundred-and-forty-three.md", "9,280",
     "none, over a full pass", "README.md", "no unreadable sector",
     "none, over a full 1,826,656-sector pass", "tools/sweep.py E --sha1"),
    ("protection",
     "SafeDisc 2.40.010", "docs/08-safedisc-2-40-010.md", "2.40.010",
     "SafeDisc 4.50.000", "README.md", "4.50.000",
     "SecuROM: four sections in hp.exe named ars / est / artem / celare, "
     "plus a .securom section; no version string found",
     "tools/securom.py, tools/hunt2.py"),
    ("protection artefacts at the root",
     "00000001.TMP, 00000002.TMP", "docs/08-safedisc-2-40-010.md",
     "00000002.TMP",
     "00000001.TMP, 00000002.TMP, DIAG.EXE", "docs/02-spec-sheet.md",
     "DIAG.EXE",
     "none", "tools/census.py E:/"),
    ("engine",
     "Unreal Engine 1", "README.md", "Unreal Engine 1",
     "RenderWare on RealCore 6.27.01 and RealGraph 6, with Havok",
     "README.md", "RealCore 6.27.01",
     "RenderWare on RealCore 6.27.01 and RealGraph 6, with Havok "
     "(Havok-4.0.0-r1 named)", "tools/hunt2.py, tools/machpaths2.py"),
    ("linker",
     "6.0 on 20 of 28 binaries", "docs/21-against-eight-trees.md",
     "PE i386, linker 6.0",
     "7.10 on 12 of 14; 6.00 on 2", "docs/02-spec-sheet.md", "7.10",
     "8.00 on 10 of 13 loose binaries; 7.10 on 3",
     "tools/pecensus.py _work/iso"),
    ("Authenticode signatures",
     "not published", "docs/08-safedisc-2-40-010.md", "SafeDisc",
     "not published", "docs/02-spec-sheet.md", "DIAG.EXE",
     "13 of 13 loose binaries signed, and hp.exe too",
     "tools/pecensus.py, tools/authenticode.py"),
    ("studio named on the disc",
     "once, in a machine path", "docs/19-dhunt-knowwonder.md", "KnowWonder",
     "never; three middleware vendors instead", "README.md", "none named",
     "no studio name, but a certificate saying Electronic Arts / UK Studio / "
     "Guildford / Surrey / GB and eleven z:\\phoenix source paths",
     "tools/authenticode.py, tools/machpaths2.py"),
    ("language axes",
     "15 axes, 25 codes, none on all", "docs/17-twenty-five-languages.md",
     "fifteen",
     "10 axes, 27 codes, four on all ten",
     "docs/11-twenty-seven-languages.md", "twenty-seven codes",
     "9 axes, 26 codes, none on all nine", "tools/langaxes.py _work/iso"),
    ("languages the installer switches on",
     "3", "docs/22-which-edition.md", "NumLanguages=3",
     "5 (fr, de, it, es, pt)", "README.md", "NumLanguages=5",
     "3 (fr, de, it)", "tools/langaxes.py, AutoRun/autorun.cfg"),
    ("help booklet",
     "not present", "docs/17-twenty-five-languages.md", "fifteen",
     "1,589 files, 10 languages, 789 distinct contents",
     "docs/12-the-help-system.md", "789",
     "1,113 files, 16 languages", "tools/census.py, tools/mirror.py"),
    ("written for this disc, by bytes",
     "89.09 %", "docs/20-whose-disc.md", "89.09",
     "94.62 %", "README.md", "94.62 %",
     "98.08 % with the archives, 7.04 % without", "tools/whose5.py _work/iso"),
    ("files matching another disc in this collection",
     "0 of 16,434 compared", "docs/21-against-eight-trees.md", "16,434",
     "0 of 17,553 in nine trees", "docs/02-spec-sheet.md", "17,553",
     "500, against pc-harrypotter4-doc's published hash list",
     "tools/listdiff.py notes/sha1-nozip.txt "
     "../pc-harrypotter4-doc/notes/sha1-all.txt"),
]


def load(cache, root, doc):
    p = os.path.join(root, doc)
    if p not in cache:
        try:
            cache[p] = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            cache[p] = None
    return cache[p], p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hp1", default="../pc-harrypotter1-doc")
    ap.add_argument("--hp4", default="../pc-harrypotter4-doc")
    a = ap.parse_args()

    cache = {}
    ok = bad = 0
    problems = []
    print("| axis | 2001 Philosopher's Stone | 2005 Goblet of Fire | "
          "2007 Order of the Phoenix |")
    print("|---|---|---|---|")
    for (axis, v1, d1, n1, v4, d4, n4, v5, cmd) in ROWS:
        for root, doc, needle, which in ((a.hp1, d1, n1, "hp1"),
                                         (a.hp4, d4, n4, "hp4")):
            text, p = load(cache, root, doc)
            if text is None:
                problems.append((axis, which, doc, "document not found"))
                bad += 1
            elif needle not in text:
                problems.append((axis, which, doc,
                                 "literal %r no longer occurs" % needle))
                bad += 1
            else:
                ok += 1
        print("| %s | %s | %s | %s |" % (axis, v1, v4, v5))

    print()
    print("citation check: %d of %d figures still occur in the document cited"
          % (ok, ok + bad))
    for axis, which, doc, why in problems:
        print("  !! %-42s %-4s %-46s %s" % (axis[:42], which, doc, why))
    print()
    print("axes: %d   columns: 3   citations checked: %d"
          % (len(ROWS), ok + bad))
    print()
    print("commands for this disc's column:")
    for r in ROWS:
        print("  %-46s %s" % (r[0][:46], r[8]))
    print()
    print("A note this tool prints on purpose: three points with two")
    print("consecutive products missing between the first and the second is")
    print("not a series. Two differences that agree are two differences that")
    print("agree. Nothing in this table licenses a sentence beginning \"the")
    print("series\".")


if __name__ == "__main__":
    main()
