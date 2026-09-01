#!/usr/bin/env python3
"""fourdisc.py -- four columns, and every citation checked.

threedisc.py put this collection's 2007 disc beside its 2005 and 2001 ones and
kept the citations honest: each figure quoted from another repository is stored
with the document it was published in and a literal that must still occur in
that document, and the tool prints "citation check: N of N" rather than quoting
a number that has since been edited away. It caught five wrong citations on its
first run of the previous session.

It is extended, not rewritten. Same mechanism, one more column, and two things
it now reports that the three-column version could not:

  * three of the four cited columns now have a **published hash list**
    (`notes/sha1-all.txt` in pc-harrypotter4-doc and pc-harrypotter5-doc, and
    `notes/hp1-sha1-all.txt` in pc-harrypotter5-doc for the 2001 disc), so a
    row about shared files is *verifiable* rather than *citable*, and the rows
    that are say so;
  * the fourth column is a **different publisher**, so an axis where all four
    agree is no longer an axis where one company did the same thing four
    times.

    python tools/fourdisc.py
    python tools/fourdisc.py --hp1 ../pc-harrypotter1-doc \
                             --hp4 ../pc-harrypotter4-doc \
                             --hp5 ../pc-harrypotter5-doc

Nothing in this table licenses a sentence beginning "the series", "SafeDisc
always" or "CDs of that period". Four discs are four discs, and the tool says
so in its own output.
"""
import argparse
import os

# (axis,
#  (2001 value, doc, literal), (2005 value, doc, literal),
#  (2007 value, doc, literal), this disc's value, the command that produces it)
#
# The 2001 and 2005 cells of the axes that also exist in threedisc.py are
# carried over from it verbatim, literals included.
ROWS = [
    ("publisher on the disc",
     ("Electronic Arts", "README.md", "Electronic Arts"),
     ("Electronic Arts", "README.md", "Electronic Arts"),
     ("Electronic Arts", "README.md", "Electronic Arts"),
     "Take Two / Triumph Studios (no publisher field; names in the credits)",
     "tools/hunt2.py _work/iso/AoW2.~ex --tokens-file notes/tokens.txt"),
    ("medium",
     ("CD-ROM", "README.md", "PC CD-ROM"),
     ("DVD-ROM, single layer", "README.md", "DVD-ROM, single layer"),
     ("DVD-ROM, single layer, pressed", "README.md", "DVD-ROM, single layer"),
     "CD-ROM, one track, profile 0x0008",
     "tools/spti.py E"),
    ("volume identifier",
     ("HARRY_POTTER_SIP_2210B", "README.md", "HARRY_POTTER_SIP_2210B"),
     ("HPGOF", "README.md", "Volume `HPGOF`"),
     ("HPOOTP", "README.md", "HPOOTP"),
     "AOW2", "tools/vds.py E"),
    ("sectors declared",
     ("292,173", "README.md", "292,173"),
     ("671,664", "README.md", "671,664"),
     ("1,826,656", "README.md", "1,826,656"),
     "335,261", "tools/vds.py E"),
    ("bytes",
     ("598,370,304", "README.md", "598,370,304"),
     ("1,375,567,872", "README.md", "1,375,567,872"),
     ("3,740,991,488", "README.md", "3,740,991,488"),
     "686,614,528", "tools/vds.py E"),
    ("files / folders",
     ("540 / 30", "README.md", "540 files"),
     ("1,659 / 40", "README.md", "1,659 files in 40 folders"),
     ("1,187 / 26", "README.md", "1,187 files in 26"),
     "36 / 13", "tools/isodev.py E --tree"),
    ("lead-out minus declared volume",
     ("+150", "README.md", "150"),
     ("not measured this way", "README.md", "671,664"),
     ("-674,807, a saturated field", "README.md", "674,807"),
     "+150", "tools/toc.py E"),
    ("filesystems",
     ("ISO 9660 + Joliet", "docs/03-two-primaries.md", "Joliet"),
     ("ISO 9660 + Joliet + UDF", "README.md", "UDF"),
     ("ISO 9660 + UDF, no Joliet", "README.md", "No Joliet"),
     "ISO 9660 + Joliet (escape %/@), no UDF",
     "tools/vds.py E"),
    ("primary volume descriptors",
     ("2", "docs/03-two-primaries.md", "Two primaries"),
     ("1", "README.md", "SafeDisc 4.50.000"),
     ("1", "README.md", "UltraISO"),
     "2", "tools/vds.py E"),
    ("payload in a descriptor field the standard requires to be zero",
     ("388 bytes at +1139", "docs/03-two-primaries.md", "1139"),
     ("267 bytes at +1139", "README.md", "requires to be zero"),
     ("121 bytes at +1884", "README.md", "requires to be zero"),
     "351 bytes at +1139..1489, one span crossing the field boundary",
     "tools/vdpayload.py E"),
    ("boundaries of this disc found inside that payload",
     ("6 of 12 aligned dwords", "docs/03-two-primaries.md", "Six of the twelve"),
     ("the protection version, as 4 and 50", "README.md",
      "the integers `4` and `50`"),
     ("the volume size", "README.md", "requires to be zero"),
     "4: first and last unreadable sector, 00000001.TMP LBA, gap end",
     "tools/vdmatch3.py E --span 1139 1490 ..."),
    ("root directory extent",
     ("early in the volume", "docs/03-two-primaries.md",
      "root directory record"),
     ("early in the volume", "README.md", "1,659"),
     ("LBA 259", "docs/02-spec-sheet.md", "259"),
     "LBA 335,260 -- the last sector of the volume",
     "tools/vds.py E"),
    ("unallocated sectors",
     ("10,000 + smaller", "README.md", "21,281,745"),
     ("2,096 in 126 gaps", "README.md", "126 unallocated gaps"),
     ("1,521 in 3 gaps", "docs/02-spec-sheet.md", "1,521"),
     "80,163 in 4 gaps, 23.91 % of the volume",
     "tools/isodev.py E --extents"),
    ("what is in the biggest gap",
     ("9,280 unreadable sectors", "README.md", "9,280"),
     ("a second filesystem (UDF)", "README.md", "second filesystem"),
     ("UDF metadata", "docs/02-spec-sheet.md", "1,258"),
     "143,595,520 bytes of a generated pattern with a closed form",
     "tools/padform.py E 265135 335259 --formula ..."),
    ("physically unreadable sectors",
     ("9,280, contiguous, LBA 818..10,097", "README.md", "9,280"),
     ("none over a full pass", "README.md", "no unreadable sector"),
     ("none over a full pass", "README.md", "no unreadable sector"),
     "scattered singles, first 807, last 10,265, ~6.2 % of LBA 790..10,265 sampled",
     "tools/holepat.py E 780 960 --block 1"),
    ("protection",
     ("SafeDisc 2.40.010", "README.md", "SafeDisc 2.40.010"),
     ("SafeDisc 4.50.000", "README.md", "SafeDisc 4.50.000"),
     ("SecuROM, no version string", "README.md", "no version string"),
     "SafeDisc 2.60.052", "tools/bog.py _work/iso/AoW2.~ex"),
    ("BoG_ marker offset",
     ("0xFD4", "docs/08-safedisc-2-40-010.md", "0xFD4"),
     ("0xFD4", "README.md", "0xFD4"),
     ("no marker", "README.md", "no version string"),
     "0x3D4", "tools/bog.py _work/iso/AoW2.~ex"),
    ("engine / toolchain of the game binary",
     ("Unreal Engine 1", "README.md", "Unreal Engine 1"),
     ("RenderWare on RealCore 6.27.01", "README.md", "RealCore 6.27.01"),
     ("RenderWare on RealCore 6.27.01", "README.md", "RealCore 6.27.01"),
     "Borland Delphi 5 (CODE/DATA/BSS sections, Vcl50.bpl, .pas paths)",
     "tools/pe.py _work/iso/AoW2.~ex"),
    ("mastering application named in the descriptor",
     ("none", "README.md", "292,173"),
     ("GEAR", "README.md", "GEAR"),
     ("UltraISO V8.5", "README.md", "UltraISO"),
     "none -- all five text fields empty",
     "tools/vds.py E"),
    ("Authenticode signatures",
     ("0", "README.md", "SafeDisc 2.40.010"),
     ("0 of 14", "README.md", "SafeDisc 4.50.000"),
     ("13 of 13", "README.md", "13 of 13 signed"),
     "0 of 9", "tools/pecensus.py _work/iso"),
    ("studio named inside the software",
     ("KnowWonder, once, in a path", "README.md", "KnowWonder"),
     ("none", "README.md", "no development studio appears at all"),
     ("none as a company name", "README.md", "no studio company name"),
     "Triumph Studios, in the version resource and four times in the credits",
     "tools/pe.py _work/iso/AoW2.~ex"),
    ("build path surviving in a binary",
     ("a developer's Windows domain", "README.md", "KnowWonder"),
     ("d:\\P4\\Eauk\\HPGoF\\", "docs/09-who-made-this.md", "Eauk"),
     ("z:\\phoenix\\code", "README.md", "phoenix"),
     "d:\\aow2\\engine\\ek\\HashTab.pas and d:\\aow2\\engine\\gfxe\\GFXE.pas",
     "tools/machpaths2.py _work/iso"),
    ("files byte-identical to another disc in this collection",
     ("0 of 16,434 compared", "docs/21-against-eight-trees.md", "16,434"),
     ("0 of 17,553 in nine trees", "docs/02-spec-sheet.md", "17,553"),
     ("500, against the 2005 disc", "README.md", "500 files"),
     "2 of 36, against the 2001 disc, and 0 against the other two",
     "tools/listdiff.py notes/sha1-all.txt "
     "../pc-harrypotter5-doc/notes/hp1-sha1-all.txt"),
    ("published hash list",
     ("yes, in pc-harrypotter5-doc/notes/hp1-sha1-all.txt",
      "README.md", "540 files"),
     ("yes, notes/sha1-all.txt, 1,659 lines", "README.md", "1,659 files"),
     ("yes, notes/sha1-all.txt, 1,187 lines", "README.md", "1,187 files"),
     "yes, notes/sha1-all.txt, 36 lines",
     "tools/hashall.py E:/"),
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
    ap.add_argument("--hp5", default="../pc-harrypotter5-doc")
    a = ap.parse_args()

    cache = {}
    ok = bad = 0
    problems = []
    print("| axis | 2001 Philosopher's Stone | 2005 Goblet of Fire | "
          "2007 Order of the Phoenix | 2002 Age of Wonders II |")
    print("|---|---|---|---|---|")
    for (axis, c1, c4, c5, mine, cmd) in ROWS:
        for root, (val, doc, needle), which in ((a.hp1, c1, "hp1"),
                                                (a.hp4, c4, "hp4"),
                                                (a.hp5, c5, "hp5")):
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
        print("| %s | %s | %s | %s | %s |"
              % (axis, c1[0], c4[0], c5[0], mine))

    print()
    print("citation check: %d of %d figures still occur in the document cited"
          % (ok, ok + bad))
    for axis, which, doc, why in problems:
        print("  !! %-46s %-4s %-30s %s" % (axis[:46], which, doc, why))
    print()
    print("axes: %d   cited columns: 3   measured column: 1   citations: %d"
          % (len(ROWS), ok + bad))
    print()
    print("commands for this disc's column:")
    for r in ROWS:
        print("  %-50s %s" % (r[0][:50], r[5]))
    print()
    print("A note this tool prints on purpose: four discs are four discs.")
    print("Three of them are the same publisher and the same series, and the")
    print("fourth is neither, which is what makes an agreement between all")
    print("four worth more than an agreement between the first three -- and")
    print("still not a law. Nothing here licenses a sentence beginning \"the")
    print("series\", \"SafeDisc always\" or \"CDs of that period\".")


if __name__ == "__main__":
    main()
