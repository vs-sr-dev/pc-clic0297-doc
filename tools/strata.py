#!/usr/bin/env python3
"""strata.py -- the disc as a stratigraphic section: one row per body of work.

producers.py answers "whose code is in these bytes" and gets Macromedia at a
third of the disc, because a third of the disc is Director movies and every
Director movie carries Macromedia's copyright. That is a true answer to a
question nobody asked. **The engine's vendor is not the work's author**, and on
a compilation disc the useful unit is neither the file nor the vendor but the
*stratum*: a body of material that arrived together, from one place, at one
time.

The top-level folder is the assembly unit here, and this tool takes it as such
and then tests it. For each stratum it reports what can be measured without
deciding anything:

  * files and bytes, and the share of the disc;
  * the span of clock A (ISO recording dates) inside it, and its mode;
  * the span of clock B (internal format timestamps) inside it;
  * every container format present, with counts;
  * every vendor named in the bytes, with counts;
  * whether the Macintosh side sees it at all.

A stratum whose clock A span is a few hours arrived as a unit. One whose span
is years was assembled from parts. That distinction is the whole point, and it
is a measurement, not a judgement.

    python tools/strata.py
    python tools/strata.py --tsv notes/strata.tsv
"""
import argparse
import csv
import datetime
from collections import Counter, defaultdict


def load(path, delim="\t"):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=delim))


def parse(s):
    if not s:
        return None
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def top(p):
    return p.split("/")[0] if "/" in p else "(root)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clocks", default="notes/threeclocks.tsv")
    ap.add_argument("--producers", default="notes/producers.tsv")
    ap.add_argument("--hfs", default="notes/hfs-files.tsv")
    ap.add_argument("--tsv")
    a = ap.parse_args()

    clocks = load(a.clocks)
    prod = {r["path"]: r for r in load(a.producers)}
    hfs = set()
    for r in load(a.hfs):
        p = r["path"]
        hfs.add((p.split("/", 1)[1] if "/" in p else p).upper())

    st = defaultdict(list)
    for r in clocks:
        st[top(r["path"])].append(r)

    total = sum(int(r["size"]) for r in clocks)
    print("strata of CLIC 11, by bytes.  Unit: the top-level entry of the "
          "ISO volume.")
    print("Total %d files, %d bytes." % (len(clocks), total))
    print()

    rows = []
    for name, rs in sorted(st.items(),
                           key=lambda kv: -sum(int(r["size"]) for r in kv[1])):
        b = sum(int(r["size"]) for r in rs)
        A = sorted(x for x in (parse(r["clockA"]) for r in rs) if x)
        B = sorted(x for x in (parse(r["clockB"]) for r in rs) if x)
        kinds = Counter(r["kind"] for r in rs)
        vend = Counter()
        for r in rs:
            pr = prod.get(r["path"])
            if pr:
                for g in (pr["grade1"], pr["grade2"]):
                    if g:
                        for piece in g.split("+"):
                            vend[piece] += 1
        onmac = sum(1 for r in rs if r["path"].upper() in hfs)
        Aspan = (A[-1] - A[0]) if A else None
        rows.append((name, len(rs), b, A, B, kinds, vend, onmac, Aspan))

        print("=" * 74)
        print("%-14s %5d files  %12d bytes  %6.2f %% of the disc"
              % (name, len(rs), b, 100.0 * b / total))
        if A:
            print("  clock A (recorded) : %s .. %s   span %s"
                  % (A[0].strftime("%Y-%m-%d %H:%M"),
                     A[-1].strftime("%Y-%m-%d %H:%M"), Aspan))
            day = Counter(x.date() for x in A)
            top3 = ", ".join("%s x%d" % (d, n) for d, n in day.most_common(3))
            print("  busiest days       : %s" % top3)
        if B:
            print("  clock B (internal) : %s .. %s   over %d of %d files"
                  % (B[0].strftime("%Y-%m-%d"), B[-1].strftime("%Y-%m-%d"),
                     len(B), len(rs)))
        else:
            print("  clock B (internal) : none of these files carries one")
        print("  formats            : %s"
              % ", ".join("%s %d" % (k, v) for k, v in kinds.most_common(8)))
        print("  vendors in the bytes: %s"
              % (", ".join("%s %d" % (k, v) for k, v in vend.most_common(6))
                 or "none named"))
        print("  visible to the Mac : %d of %d files" % (onmac, len(rs)))

    print("=" * 74)
    print()
    print("%-14s %6s %13s %8s %-24s %s"
          % ("stratum", "files", "bytes", "share", "clock A span", "arrived"))
    for name, n, b, A, B, kinds, vend, onmac, Aspan in rows:
        verdict = ""
        if Aspan is not None:
            days = Aspan.total_seconds() / 86400.0
            verdict = ("as a unit" if days < 2 else
                       "over days" if days < 40 else
                       "assembled from parts")
        print("%-14s %6d %13d %7.2f%% %-24s %s"
              % (name, n, b, 100.0 * b / total,
                 str(Aspan) if Aspan is not None else "-", verdict))

    if a.tsv:
        with open(a.tsv, "w", encoding="utf-8", newline="") as fh:
            fh.write("stratum\tfiles\tbytes\tshare\tA_first\tA_last\tA_span_days"
                     "\tB_first\tB_last\tmac_visible\n")
            for name, n, b, A, B, kinds, vend, onmac, Aspan in rows:
                fh.write("%s\t%d\t%d\t%.4f\t%s\t%s\t%s\t%s\t%s\t%d\n"
                         % (name, n, b, 100.0 * b / total,
                            A[0] if A else "", A[-1] if A else "",
                            "%.4f" % (Aspan.total_seconds() / 86400.0)
                            if Aspan is not None else "",
                            B[0] if B else "", B[-1] if B else "", onmac))
        print()
        print("wrote %s" % a.tsv)


if __name__ == "__main__":
    main()
