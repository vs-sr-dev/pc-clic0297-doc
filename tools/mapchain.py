#!/usr/bin/env python3
"""mapchain.py -- the story order of the 41 maps, from the strings that move
the player between them.

mapgraph.py finds every mention of one map's name inside another. That is the
loose net and it catches things that are not transitions.

This is the strict net, and it turned out there are TWO transition mechanisms
on this disc, not one. Both are literal strings inside a map's serialised
objects and both are accepted here, separately labelled, because which one a
transition uses is itself a measurement:

  CL   the console command  "ChangeLevel <map>"  (optionally "<map>.unr")
  URL  a bare travel URL    "<map>.unr"          with no ChangeLevel in front

Nothing else is accepted. A mention of a map's name that is neither of these
is discarded, and the count of what was discarded is printed.

The tool then walks the graph, prints the linear order, and compares that
order against what the FILENAMES claim. The filename comparison is
case-insensitive on the stem, because two of these maps differ from each other
only in the case of one letter and a case-sensitive rule silently skips the
most interesting pair on the disc.

    python tools/mapchain.py E:/Maps
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkg  # noqa: E402

ASCII = re.compile(rb"[\x20-\x7e]{4,}")


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "E:/Maps"
    ms = sorted(f for f in os.listdir(d) if f.lower().endswith(".unr"))
    bases = [m[:-4] for m in ms]
    low = {b.lower(): b for b in bases}

    CL = {b: re.compile(r"changelevel\s+" + re.escape(b) +
                        r"(?:\.unr)?(?![A-Za-z0-9_])", re.I) for b in low}
    URL = {b: re.compile(r"(?<![A-Za-z0-9_])" + re.escape(b) +
                         r"\.unr(?![A-Za-z0-9_])", re.I) for b in low}
    ANY = {b: re.compile(r"(?<![A-Za-z0-9_])" + re.escape(b) +
                         r"(?![A-Za-z0-9_])", re.I) for b in low}

    edges = collections.defaultdict(dict)   # src -> dst -> (kind, off, ctx)
    loose = collections.Counter()
    for m in ms:
        src = m[:-4]
        data = open(os.path.join(d, m), "rb").read()
        for mo in ASCII.finditer(data):
            s = mo.group().decode("latin-1")
            for b in low:
                dst = low[b]
                if dst == src:
                    continue
                hit = CL[b].search(s)
                kind = "CL"
                if not hit:
                    hit = URL[b].search(s)
                    kind = "URL"
                if not hit:
                    if ANY[b].search(s):
                        loose[(src, dst)] += 1
                    continue
                cur = edges[src].get(dst)
                if cur is None or (cur[0] == "URL" and kind == "CL"):
                    edges[src][dst] = (kind, mo.start() + hit.start(),
                                       s[max(0, hit.start() - 24):
                                         hit.start() + 64])

    print("transitions accepted, %d maps" % len(bases))
    print()
    kinds = collections.Counter()
    for src in bases:
        for dst, (k, off, ctx) in sorted(edges[src].items()):
            kinds[k] += 1
    print("edge kinds: %s" % dict(kinds))
    print("mentions rejected as neither ChangeLevel nor a .unr URL: %d pairs, "
          "%d occurrences" % (len(loose), sum(loose.values())))
    print()
    for src in bases:
        e = sorted(edges[src].items())
        if not e:
            print("%-22s -> (nothing)" % src)
            continue
        print("%-22s -> %s" % (src, ", ".join(x[0] for x in e)))
        for dst, (k, off, ctx) in e:
            print("      %-4s %-16s +0x%-8X %r" % (k, dst, off, ctx))
    print()

    # Entry is the main menu: every map can go back to it. It is not a
    # story successor, so the walk excludes it and says so.
    def succ(n):
        return [t for t in edges[n] if t != "Entry"]

    indeg = collections.Counter()
    for s in bases:
        for t in succ(s):
            indeg[t] += 1
    roots = [b for b in bases if indeg[b] == 0 and succ(b)]
    print("nodes with no incoming transition (Entry excluded as a successor):")
    for r in roots:
        print("     %-22s out-degree %d" % (r, len(succ(r))))
    print()

    print("the walk, following the single successor of each map:")
    walked = set()
    for r in sorted(roots):
        seen = []
        cur = r
        while cur and cur not in seen:
            seen.append(cur)
            n = succ(cur)
            cur = n[0] if len(n) == 1 else None
        walked.update(seen)
        print()
        print("  from %s: %d maps" % (r, len(seen)))
        for i, n in enumerate(seen, 1):
            k = ""
            if i < len(seen):
                k = edges[n][seen[i]][0]
            print("     %2d. %-22s %s" % (i, n, ("--%s-->" % k) if k else ""))
    print()
    print("maps not on any walk: %d  %s"
          % (len(bases) - len(walked), sorted(set(bases) - walked)))
    print()

    # order across the whole graph
    order = {}
    for r in sorted(roots):
        seen = []
        cur = r
        while cur and cur not in seen:
            seen.append(cur)
            n = succ(cur)
            cur = n[0] if len(n) == 1 else None
        base = len(order)
        for i, n in enumerate(seen):
            order.setdefault(n, base + i)

    print("where the shipped order disagrees with the filenames")
    print("(stem compared case-insensitively):")
    stem = re.compile(r"^(.*?)(\d+)$")
    found = 0
    for i, a in enumerate(bases):
        for b in bases[i + 1:]:
            if a not in order or b not in order:
                continue
            ma, mb = stem.match(a), stem.match(b)
            if not ma or not mb:
                continue
            if ma.group(1).lower() != mb.group(1).lower():
                continue
            na, nb = int(ma.group(2)), int(mb.group(2))
            if na == nb:
                continue
            names_first = a if na < nb else b
            chain_first = a if order[a] < order[b] else b
            if names_first != chain_first:
                found += 1
                print("   %-18s (position %2d)" % (a, order[a] + 1))
                print("   %-18s (position %2d)" % (b, order[b] + 1))
                print("      the numbers in the names say %s comes first;"
                      % names_first)
                print("      the ChangeLevel strings say %s comes first."
                      % chain_first)
                if a.lower() == b.lower().replace(str(nb), str(na)):
                    pass
                if ma.group(1) != mb.group(1):
                    print("      the two stems also differ in case: %r vs %r"
                          % (ma.group(1), mb.group(1)))
    if not found:
        print("   none")


if __name__ == "__main__":
    main()
