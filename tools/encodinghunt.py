#!/usr/bin/env python3
"""encodinghunt.py -- look for a word in every byte spelling it could have.

`hunt2.py` finds a token by scanning for printable ASCII runs and for UTF-16LE
runs. That is the right default and it has one blind spot, which this disc walks
straight into: **an accented letter is not printable ASCII**, so a run
containing one is cut in two and a token containing one is never found.

The town in this title is spelled *Vigata* with a grave accent on the second a,
and the word Camilleri's novels use for it is written on a Macintosh in 2000, so
the accented letter is MacRoman 0x88 -- not Latin-1 0xE0, not UTF-8 0xC3 0xA0,
not UTF-16. `hunt2.py --tokens Vigata` returns zero hits and the honest reading
of that zero is "not in this encoding", not "not on this disc".

So this takes a word written with real accents and searches for **every byte
sequence that could spell it**: MacRoman, Latin-1, CP437, CP850, UTF-8,
UTF-16LE, UTF-16BE, and the unaccented ASCII fallback. It reports which spelling
was found, because which one it is says which machine typed it.

    python tools/encodinghunt.py _work --word "Vigata" --word "Camilleri"
    python tools/encodinghunt.py _work --word "perche" --context 40

The count of files scanned is printed next to the result, and a word found zero
times is reported as zero times **in the encodings tried**, which are listed.
"""
import argparse
import os
import sys

ENCODINGS = [("mac_roman", "MacRoman -- what a Macintosh of 2000 would write"),
             ("latin-1", "Latin-1 / CP1252 -- what a Windows PC would write"),
             ("cp437", "CP437 -- the original PC console codepage"),
             ("cp850", "CP850 -- the Western European DOS codepage"),
             ("utf-8", "UTF-8"),
             ("utf-16-le", "UTF-16LE"),
             ("utf-16-be", "UTF-16BE"),
             ("ascii-fold", "the same word with the accents removed")]

FOLD = {"a": "aàáâä", "e": "eèéêë", "i": "iìíîï", "o": "oòóôö", "u": "uùúûü",
        "c": "cç", "n": "nñ"}


def fold(w):
    out = []
    for ch in w:
        low = ch.lower()
        hit = None
        for base, group in FOLD.items():
            if low in group:
                hit = base if ch.islower() else base.upper()
        out.append(hit if hit else ch)
    return "".join(out)


def spellings(word):
    """Every byte sequence that could spell `word`, labelled."""
    out = []
    for enc, why in ENCODINGS:
        if enc == "ascii-fold":
            b = fold(word).encode("ascii", "ignore")
        else:
            try:
                b = word.encode(enc)
            except (UnicodeEncodeError, LookupError):
                continue
        if b and all(b != o[1] for o in out):
            out.append((enc, b, why))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--word", action="append", required=True)
    ap.add_argument("--context", type=int, default=0)
    ap.add_argument("--max-hits", type=int, default=6)
    ap.add_argument("--ignore-case", action="store_true")
    a = ap.parse_args()

    files = []
    for r in a.roots:
        if os.path.isfile(r):
            files.append(r)
            continue
        for dp, dn, fn in os.walk(r):
            for n in fn:
                files.append(os.path.join(dp, n))
    files.sort()

    plans = []
    for w in a.word:
        plans.append((w, spellings(w)))

    print("files scanned : %d" % len(files))
    print("words         : %s" % ", ".join(a.word))
    print()
    for w, sp in plans:
        print("--- %r ---" % w)
        for enc, b, why in sp:
            print("    %-12s %-40s %s" % (enc, repr(b), why))
    print()

    counts = {}
    where = {}
    for p in files:
        try:
            data = open(p, "rb").read()
        except OSError:
            continue
        low = data.lower() if a.ignore_case else data
        for w, sp in plans:
            for enc, b, why in sp:
                needle = b.lower() if a.ignore_case else b
                start = 0
                while True:
                    i = low.find(needle, start)
                    if i < 0:
                        break
                    k = (w, enc)
                    counts[k] = counts.get(k, 0) + 1
                    if len(where.setdefault(k, [])) < a.max_hits:
                        ctx = ""
                        if a.context:
                            lo = max(0, i - a.context)
                            hi = min(len(data), i + len(b) + a.context)
                            ctx = repr(data[lo:hi])
                        where[k].append((p, i, ctx))
                    start = i + 1

    print("%-16s %-12s %8s  %s" % ("word", "encoding", "hits", "example"))
    print("-" * 78)
    for w, sp in plans:
        total = 0
        for enc, b, why in sp:
            n = counts.get((w, enc), 0)
            total += n
            if n == 0:
                continue
            ex = where[(w, enc)][0]
            print("%-16s %-12s %8d  %s +0x%X"
                  % (w, enc, n, os.path.relpath(ex[0]), ex[1]))
        if total == 0:
            print("%-16s %-12s %8d  in none of the %d encodings listed above"
                  % (w, "(all)", 0, len(sp)))
    print()

    if a.context:
        for w, sp in plans:
            for enc, b, why in sp:
                k = (w, enc)
                if k not in where:
                    continue
                print("--- %r as %s ---" % (w, enc))
                for p, i, ctx in where[k]:
                    print("    %s +0x%X" % (os.path.relpath(p), i))
                    print("        %s" % ctx)


if __name__ == "__main__":
    main()
