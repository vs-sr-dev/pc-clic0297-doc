#!/usr/bin/env python3
"""filemaker.py -- what `.clc` is, and how much of it is the Overlook Hotel.

The magazine gave its cover database the extension `.clc`, which is not a
format, and the briefing for this session listed it as "the magazine's format
and nobody knows it". Two facts from the bytes settle it:

  * the Macintosh twin of the same file, `PAGMAC/Pagella`, carries the HFS
    type `FMP3` and the creator `NFIN` -- FileMaker Pro 3, Claris;
  * `PAGWIN/` ships `FMENGINE.DLL`, `FMTOOLS.DLL`, `FMOLE.DLL`, `FM_CLC.DLL`
    and `PAGELLA.EXE`, all with the version-resource CompanyName
    "Claris Corporation".

So `.clc` is a FileMaker Pro 3 database with the magazine's extension on it.

The second thing this tool measures is the filler. FileMaker Pro pads the
unused part of its allocated blocks with a repeating sentence rather than with
zeros, and the sentence is the one Jack Torrance types in *The Shining*. Every
byte of it is unused space that was written to the master anyway, so it belongs
in the leftovers accounting, and this counts it exactly.

    python tools/filemaker.py _work/hfs/PAGMAC/Pagella _work/iso/PAGWIN/pagella.clc
"""
import argparse
import os

JACK = b"All work and no play makes Jack a dull boy. "


def runs_of(d, pat):
    """total bytes covered by maximal runs of pat, and how many runs."""
    total = 0
    nruns = 0
    i = d.find(pat)
    while i >= 0:
        j = i
        while d[j:j + len(pat)] == pat:
            j += len(pat)
        # count the partial repetition that a run usually ends on
        k = 0
        while k < len(pat) and d[j + k:j + k + 1] == pat[k:k + 1]:
            k += 1
        total += (j + k) - i
        nruns += 1
        i = d.find(pat, j + k + 1)
    return total, nruns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()

    grand = 0
    for p in a.files:
        with open(p, "rb") as fh:
            d = fh.read()
        n = len(d)
        tot, runs = runs_of(d, JACK)
        zero = d.count(b"\x00")
        print("=" * 70)
        print("%s" % p)
        print("  bytes                       : %d" % n)
        print("  header, first 15 bytes      : %s"
              % " ".join("%02x" % b for b in d[:15]))
        print("  'All work and no play...'   : %d bytes in %d runs   %.2f %% of the file"
              % (tot, runs, 100.0 * tot / n))
        print("  zero bytes                  : %d   %.2f %%"
              % (zero, 100.0 * zero / n))
        first = d.find(JACK)
        print("  first filler byte at offset : %s"
              % (first if first >= 0 else "not present"))
        grand += tot
    print("=" * 70)
    print("filler bytes across all files given : %d" % grand)


if __name__ == "__main__":
    main()
