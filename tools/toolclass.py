#!/usr/bin/env python3
"""toolclass.py -- classify every tool exactly once, and prove it.

docs/…-tools.md has to say, for each tool in this directory, whether it applies
to this disc. The failure mode of writing that by hand is not getting a
classification wrong -- it is *forgetting one*, and then publishing a total that
does not add up to the number of files.

So the classification lives here, as data, and the tool asserts three things:

  * every .py file in tools/ appears in exactly one class;
  * no class names a file that is not there;
  * the class sizes sum to the file count.

It fails loudly rather than printing a plausible table.

    python tools/toolclass.py
    python tools/toolclass.py --markdown

The classification below is CLIC 11's, rewritten from the eleventh session's.
The biggest change is that the whole CAB and installer apparatus -- cab.py,
cabdates.py, cabsig.py, inno.py, msi.py, vise.py, zob.py -- was "does not
apply" for eleven discs in a row and applies here, because this disc is
121 cabinets and two installers.
"""
import argparse
import os
import sys

# ---------------------------------------------------------------------------
# The classes. A tool is in exactly one.
# ---------------------------------------------------------------------------

CLASSES = [

("written for this disc",
 "Written this session, because nothing inherited could answer the question. "
 "Four, which is the fewest any CD session has needed, and that is a statement "
 "about how complete the inherited apparatus has become rather than about how "
 "easy this disc was.",
 ["twocat.py", "abslack.py", "slackorigin.py", "jbf.py"]),

("inherited and used",
 "Ran on this disc and produced a figure that a document cites. Nothing is in "
 "this class that was not actually executed.",
 ["hfs.py", "iso9660.py", "pecensus.py", "census.py", "protscan.py",
  "buildpaths.py", "discdiff.py", "mov.py", "avi.py", "audio.py",
  "slack.py", "checkscore.py", "toolclass.py"]),

("inherited, superseded here",
 "Would have answered a question this repository asked, and something else "
 "answered it instead -- either a tool written this session that extends it, or "
 "a direct reading of the image. Named so that nobody thinks the question went "
 "unasked.",
 # The six that CLIC 11 listed here -- iso9660, census, discdiff, mov, avi,
 # audio -- were actually RUN this session and have moved to "inherited and
 # used". What is left, plus the fourteen CLIC 11 wrote whose question this
 # session answered another way.
 ["vds.py", "vdpayload.py", "vdmatch3.py", "gapmap.py", "sameplace.py",
  "listdiff.py", "filelist2.py", "namecensus.py", "imagecensus.py", "jpeg.py",
  "mtimes.py", "clocks.py", "twoclocks.py", "strdump.py", "hunt2.py",
  # written for CLIC 11; twocat.py subsumes the first five on a hybrid
  "assoc.py", "sectormap.py", "pcinvisible.py", "threewalks.py",
  "treecensus.py", "vdall.py", "threeclocks.py", "leftovers.py",
  "macrsrc.py", "rawimage.py", "media.py", "twofs.py", "hashall.py",
  "dircensus.py"]),

("inherited, applicable, not needed",
 "Would run here and would say something true, but nothing in this repository "
 "needed it. Listed so that the count is honest.",
 ["pe.py", "ne.py", "rsrc.py", "authenticode.py", "signcount.py", "cabsig.py",
  "inno.py", "msi.py", "vise.py", "zob.py", "dates.py", "timeline.py",
  "smallfiles.py", "accounting.py", "cdxa.py", "compare.py", "verify.py",
  "resolve.py", "refcheck.py", "refs.py", "collectrefs.py", "stock.py",
  "thirdparty.py", "bmp.py", "tga.py", "headers.py", "msf.py", "rawsect.py",
  "subch.py", "secmap.py", "padform.py", "padecho.py", "holepat.py",
  "pathdiff.py", "gamestats.py", "orphans.py", "mirror.py", "zipdir.py",
  "cast.py", "swa.py", "interleave.py", "discpass.py", "xfermax.py",
  "udf.py",
  # written for CLIC 11, would run here, nothing needed them
  "bog.py", "cab.py", "cabdates.py", "checklinks.py", "director.py",
  "encodinghunt.py", "filemaker.py", "fivelists.py", "producers.py",
  "requires.py", "strata.py", "szdd.py"]),

("inherited and misleading here",
 "Runs, prints something, and what it prints is about another disc. Each one "
 "is named in the tools chapter with what it says and why it is wrong.",
 ["sweep.py", "leadout.py", "window.py", "window2.py", "vdfields.py",
  "vdmatch.py", "safedisc.py", "sdnumbers.py", "sdtmp.py", "sdalign.py",
  "tmp2.py", "langaxes.py", "mzcensus.py", "filelist.py", "whose.py",
  "whose4.py", "whose5.py", "gearcount.py", "toolcheck.py", "encodings.py",
  "threedisc.py", "fourdisc.py", "hunt.py", "clocks4.py", "clockwork.py",
  "twodiscs.py", "machpaths.py", "machpaths2.py", "securom.py",
  # these four address a DRIVE. There is no drive this session: the object is
  # an image file. They run and they are about a machine, not about this disc.
  "spti.py", "toc.py", "isodev.py", "hfsx.py"]),

("does not apply: another engine or another publisher",
 "Written for a container, protection or toolchain that is not on this disc. "
 "Nothing here is Unreal, Electronic Arts, an Alias/Wavefront package or a "
 "Bink-style edge map.",
 ["big.py", "bigheads.py", "biglang.py", "bigpad.py", "umx.py", "upkg.py",
  "dobby.py", "langtable.py", "cmapcensus.py", "renderers.py", "mapchain.py",
  "mapgraph.py", "edges.py", "edgemode.py", "edgerun.py", "gap20.py",
  "gapdump.py", "gapname.py", "gapscan.py", "gapstruct.py", "pkgdiff2.py",
  "pkgsame.py", "mld.py"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="tools")
    ap.add_argument("--markdown", action="store_true")
    a = ap.parse_args()

    on_disk = sorted(f for f in os.listdir(a.dir) if f.endswith(".py"))
    named = []
    for _, _, files in CLASSES:
        named.extend(files)

    print("tools/*.py on disk        : %d" % len(on_disk))
    print("tools named in a class    : %d" % len(named))
    print("distinct tools classified : %d" % len(set(named)))
    print()
    for title, _, files in CLASSES:
        print("%-50s %5d" % (title, len(files)))
    print("%-50s %5d" % ("total", len(named)))
    print()

    ok = True
    dupes = sorted(f for f in set(named) if named.count(f) > 1)
    if dupes:
        ok = False
        print("!! classified more than once (%d): %s" % (len(dupes), ", ".join(dupes)))
    missing = sorted(set(on_disk) - set(named))
    if missing:
        ok = False
        print("!! on disk but in no class (%d): %s"
              % (len(missing), ", ".join(missing)))
    ghosts = sorted(set(named) - set(on_disk))
    if ghosts:
        ok = False
        print("!! named in a class but not on disk (%d): %s"
              % (len(ghosts), ", ".join(ghosts)))
    if len(named) != len(on_disk):
        ok = False
        print("!! totals disagree: %d classified, %d on disk"
              % (len(named), len(on_disk)))

    if not ok:
        print()
        print("refusing to print the table until every tool is classified "
              "exactly once.")
        return 1

    bad = sum(len(f) for t, _, f in CLASSES
              if t.startswith("inherited and misleading")
              or t.startswith("does not apply"))
    print("tools that do not apply or mislead on this disc : %d of %d  (%.1f %%)"
          % (bad, len(on_disk), 100.0 * bad / len(on_disk)))

    if a.markdown:
        print()
        for title, blurb, files in CLASSES:
            print("### %s — %d" % (title, len(files)))
            print()
            print(blurb)
            print()
            for f in sorted(files):
                print("  * `%s`" % f)
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
