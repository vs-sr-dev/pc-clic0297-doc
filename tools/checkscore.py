#!/usr/bin/env python3
"""checkscore.py -- count the verdicts in docs/24 out of the tables.

The header of the scoring document has been wrong twice: 46/16/29/9 and then
42/18/31/8, both tallied by hand while the sections were still being edited.
This counts them out of the tables instead, so the header can be checked
against the body with a command rather than by adding up again.

Two things the counter has to know:

  * the row "| P04-P08 | unresolved | ... |" stands for five clauses, not one;
  * the analogy table in P96 has the same leading "| Pnn |" shape but its
    second column is "content" or "method", not a verdict, so those rows are
    excluded and reported separately.

  * P93 is scored in the tools chapter, not here, and is counted as deferred.

    python tools/checkscore.py
    python tools/checkscore.py docs/17-prediction-scoring.md
"""
import collections
import os
import re
import sys

# This repository numbers its prediction clauses C01..C62 rather than Pnn.
# Both are accepted so the tool stays usable by the repositories that
# inherited it. Declared in docs/16-tools.md rather than changed quietly.
ROW = re.compile(r"^\| ([PC]\d+)(?:[^|]*?) \| ([^|]+) \|", re.M)
VERDICTS = ("hit", "half", "miss", "unresolved")


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # The filename was hard-coded to pc-harrypotter1-doc's docs/24. This
    # repository numbers its chapters differently, so the path is now an
    # optional argument and, failing that, is found by pattern. Declared in
    # docs/18-tools.md rather than changed quietly.
    if len(sys.argv) > 1:
        p = sys.argv[1]
    else:
        docs = os.path.join(root, "docs")
        cand = sorted(f for f in os.listdir(docs)
                      if f.endswith("prediction-scoring.md"))
        if not cand:
            raise SystemExit("no docs/*prediction-scoring.md found in %s" % docs)
        p = os.path.join(docs, cand[0])
    print("scoring document: %s" % os.path.relpath(p, root))
    s = open(p, encoding="utf-8").read()

    counts = collections.Counter()
    analogy = collections.Counter()
    seen = []
    for m in ROW.finditer(s):
        tag = m.group(1)
        v = m.group(2).strip().replace("**", "").split()[0].rstrip(",;")
        if v in ("content", "method"):
            analogy[v] += 1
            continue
        if v not in VERDICTS:
            counts["UNRECOGNISED: %r on %s" % (v, tag)] += 1
            continue
        # the P04-P08 row stands for five clauses
        n = 5 if "P04" in m.group(0) and "P08" in m.group(0) else 1
        counts[v] += n
        seen.append((tag, v, n))

    print("verdict rows parsed : %d" % len(seen))
    print("analogy-table rows  : %d (%s)" % (sum(analogy.values()),
                                             dict(analogy)))
    print()
    for v in VERDICTS:
        print("  %-12s %3d" % (v, counts[v]))
    odd = {k: v for k, v in counts.items() if k not in VERDICTS}
    if odd:
        print()
        print("  unrecognised verdicts:")
        for k, v in odd.items():
            print("    %s x%d" % (k, v))
    total = sum(counts[v] for v in VERDICTS)
    print()
    print("  total scored here            : %d" % total)
    # P93 was scored in the tools chapter on the previous disc and is scored in
    # this document on this one, so the deferral is only added when P93 is not
    # actually in the tables. Declared in docs/18-tools.md.
    deferred = 0 if any(t == "P93" for t, v, n in seen) else 1
    print("  P93, scored elsewhere         : %d" % deferred)
    print("  grand total                   : %d" % (total + deferred))
    resolved = total - counts["unresolved"]
    pts = counts["hit"] + 0.5 * counts["half"]
    print()
    print("  resolved                      : %d" % resolved)
    print("  halves at 0.5                 : %.1f of %d = %.1f %%"
          % (pts, resolved, 100.0 * pts / resolved if resolved else 0))
    print()

    want = re.search(r"hit\s+(\d+)\s*\n\s*half\s+(\d+)\s*\n\s*miss\s+(\d+)"
                     r"\s*\n\s*unresolved\s+(\d+)", s)
    if not want:
        print("could not find the header block to check against")
        return 1
    hdr = tuple(int(x) for x in want.groups())
    got = (counts["hit"], counts["half"], counts["miss"], counts["unresolved"])
    print("  header says   hit %d  half %d  miss %d  unresolved %d" % hdr)
    print("  tables say    hit %d  half %d  miss %d  unresolved %d" % got)
    if hdr == got:
        print("  => they agree")
        return 0
    print("  => THEY DO NOT AGREE")
    return 1


if __name__ == "__main__":
    sys.exit(main())
