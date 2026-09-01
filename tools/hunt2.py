#!/usr/bin/env python3
"""hunt2.py -- hunt.py, plus UTF-16.

`hunt.py` extracts printable ASCII runs and searches those, which is the right
method and the reason it does not report noise. On this disc it reported zero
hits for `Macrovision` -- and `pecensus.py` had already read
`Macrovision Corporation` out of DIAG.EXE's version resource three minutes
earlier.

Both were right. Windows version resources are UTF-16LE, so the company name is
`M\0a\0c\0r\0...`, which contains no ASCII run longer than one character. A
tool that only sees ASCII cannot see the string that a tool reading the
resource directory reads without effort.

So this scans each file twice: once for ASCII runs and once for UTF-16LE runs,
and reports which encoding each hit came from. The counts are kept apart
because "the name appears in the file" and "the name appears in a form a human
would have typed" are different claims.

    python tools/hunt2.py _work/iso --tokens Macrovision KnowWonder
    python tools/hunt2.py _work/iso --tokens-file notes/tokens.txt --context
"""
import argparse
import collections
import os
import re
import sys

ASCII = re.compile(rb"[\x20-\x7e]{4,}")


def utf16_runs(b, minlen=4):
    """Yield (offset, text) for runs of printable UTF-16LE characters."""
    out = []
    i = 0
    n = len(b)
    start = None
    cur = []
    while i + 1 < n:
        lo, hi = b[i], b[i + 1]
        if hi == 0 and 0x20 <= lo <= 0x7E:
            if start is None:
                start = i
                cur = []
            cur.append(chr(lo))
            i += 2
        else:
            if start is not None and len(cur) >= minlen:
                out.append((start, "".join(cur)))
            start = None
            cur = []
            i += 1
    if start is not None and len(cur) >= minlen:
        out.append((start, "".join(cur)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--tokens", nargs="*", default=[])
    ap.add_argument("--tokens-file")
    ap.add_argument("--min", type=int, default=4)
    ap.add_argument("--context", action="store_true")
    ap.add_argument("--max-hits", type=int, default=6)
    a = ap.parse_args()

    tokens = list(a.tokens)
    if a.tokens_file:
        tokens += [l.strip() for l in open(a.tokens_file, encoding="utf-8")
                   if l.strip() and not l.startswith("#")]
    low = [t.lower() for t in tokens]

    files = []
    for d in a.dirs:
        if os.path.isfile(d):
            files.append(d)
            continue
        for dp, dn, fn in os.walk(d):
            for f in fn:
                files.append(os.path.join(dp, f))
    files.sort()

    hits = {t: {"ascii": [], "utf16": []} for t in tokens}
    nruns_a = nruns_u = 0
    for p in files:
        try:
            with open(p, "rb") as f:
                b = f.read()
        except OSError:
            continue
        aruns = [(m.start(), m.group().decode("latin-1")) for m in ASCII.finditer(b)]
        uruns = utf16_runs(b, a.min)
        nruns_a += len(aruns)
        nruns_u += len(uruns)
        for kind, runs in (("ascii", aruns), ("utf16", uruns)):
            for off, s in runs:
                sl = s.lower()
                for t, tl in zip(tokens, low):
                    j = sl.find(tl)
                    if j >= 0:
                        hits[t][kind].append((p, off + (j * (2 if kind == "utf16" else 1)), s))

    print("files scanned        %d" % len(files))
    print("ASCII runs >= 4      %d" % nruns_a)
    print("UTF-16LE runs >= %d   %d" % (a.min, nruns_u))
    print()
    print("%-22s %7s %7s   %s" % ("token", "ascii", "utf16", "where"))
    print("-" * 78)
    for t in tokens:
        na = len(hits[t]["ascii"])
        nu = len(hits[t]["utf16"])
        print("%-22s %7d %7d" % (t, na, nu))
        for kind in ("ascii", "utf16"):
            for p, off, s in hits[t][kind][:a.max_hits]:
                rel = os.path.relpath(p, a.dirs[0]) if os.path.isdir(a.dirs[0]) else p
                if a.context:
                    print("      %-6s %-46s +0x%X  %r" % (kind, rel[:46], off, s[:110]))
                else:
                    print("      %-6s %-46s +0x%X" % (kind, rel[:46], off))
            if len(hits[t][kind]) > a.max_hits:
                print("      %-6s ... %d more" % (kind, len(hits[t][kind]) - a.max_hits))


if __name__ == "__main__":
    main()
