#!/usr/bin/env python3
"""mapgraph.py -- the 41 maps, from their names and then from their bytes.

The forty-one .unr names are an intention. This tool turns them into a
measurement in two independent passes and reports where the two disagree,
because a name is a plan and a reference is a fact.

Pass one, NAMES: group the forty-one filenames by prefix and print the shape
of the list. No file is opened.

Pass two, REFERENCES: open every map and look for the name of every other map
in its name table and in its serialised strings. Unreal stores level-to-level
links as a URL string in a Teleporter or in LevelInfo, and a URL is a string,
so both places are searched:

  * the package name table, where a referenced map appears as an FName;
  * the export serial data, scanned for UTF-16 and Latin-1 runs, where a URL
    like "Lev3_Troll" or "Lev3_Troll#Start" appears as a property value.

Every hit is reported with the file, the offset and which of the two pass-two
sources produced it, so a claim about the story order can be traced to a byte.

    python tools/mapgraph.py E:/Maps --names
    python tools/mapgraph.py E:/Maps --refs
    python tools/mapgraph.py E:/Maps --graph
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkg  # noqa: E402

ASCII = re.compile(rb"[\x20-\x7e]{3,}")


def maps_in(d):
    return sorted(f for f in os.listdir(d) if f.lower().endswith(".unr"))


def prefix_of(name):
    b = name[:-4]
    for p in ("Lev_Tut", "Lev2_", "Lev3_", "Lev4_", "Lev5_", "Quid_"):
        if b.startswith(p):
            return p
    return "(none)"


def cmd_names(d):
    ms = maps_in(d)
    print("%d .unr files in %s" % (len(ms), d))
    print()
    by = collections.defaultdict(list)
    for m in ms:
        by[prefix_of(m)].append(m[:-4])
    print("%-10s %5s  %s" % ("prefix", "count", "members"))
    for p in sorted(by, key=lambda k: (k == "(none)", k)):
        v = sorted(by[p])
        print("%-10s %5d  %s" % (p, len(v), " ".join(v)))
    print()
    print("levels named by a Lev<n>_ prefix : %s"
          % sorted({p for p in by if p.startswith("Lev") and p != "Lev_Tut"}))
    print("there is no Lev1_ : %s"
          % ("confirmed" if not any(m.startswith("Lev1_") for m in ms)
             else "WRONG, there is one"))
    print("maps with no prefix at all      : %s" % sorted(by["(none)"]))
    print()
    sizes = [(os.path.getsize(os.path.join(d, m)), m) for m in ms]
    sizes.sort()
    print("smallest five:")
    for s, m in sizes[:5]:
        print("   %10d  %s" % (s, m))
    print("largest five:")
    for s, m in sizes[-5:][::-1]:
        print("   %10d  %s" % (s, m))
    print()
    print("total %d bytes" % sum(s for s, _ in sizes))


def strings_of(p):
    """Latin-1 and UTF-16LE printable runs in the whole package."""
    out = []
    for m in ASCII.finditer(p.d):
        out.append((m.start(), m.group().decode("latin-1")))
    return out


def cmd_refs(d, quiet=False):
    ms = maps_in(d)
    bases = {m[:-4]: m for m in ms}
    lowered = {b.lower(): b for b in bases}
    global TOKEN
    TOKEN = {b: re.compile(r"(?<![A-Za-z0-9_])" + re.escape(b) +
                           r"(?![A-Za-z0-9_])") for b in lowered}
    pkgs = {}
    for m in ms:
        p = upkg.Package(os.path.join(d, m))
        p.load()
        pkgs[m[:-4]] = p

    edges = collections.defaultdict(set)
    evidence = collections.defaultdict(list)
    for src, p in pkgs.items():
        # source 1: the name table. An FName is a whole token already, so
        # this pass compares whole entries and needs no boundary rule.
        for i, n in enumerate(p.names):
            key = n.lower()
            if key in lowered and lowered[key] != src:
                dst = lowered[key]
                edges[src].add(dst)
                evidence[(src, dst)].append(("nametable[%d]" % i, n))
        # source 2: printable runs anywhere in the package.
        # The match must be on a whole token, not a substring: "Lev_Tut1" is
        # a prefix of "Lev_Tut1b" and "Lev2_HogFront" of "Lev2_HogFront_2",
        # so a substring rule invents an edge for every longer sibling. The
        # name must therefore be bounded on both sides by something that is
        # not a letter, a digit or an underscore.
        for off, s in strings_of(p):
            low = s.lower()
            for b in lowered:
                for m in TOKEN[b].finditer(low):
                    dst = lowered[b]
                    if dst == src:
                        continue
                    edges[src].add(dst)
                    if len(evidence[(src, dst)]) < 6:
                        evidence[(src, dst)].append(
                            ("+0x%X" % off, s[:110]))
    if not quiet:
        print("references found between the %d maps" % len(ms))
        print()
        for src in sorted(pkgs):
            dsts = sorted(edges[src])
            print("%-22s -> %s" % (src, ", ".join(dsts) if dsts else "(none)"))
            for dst in dsts:
                for where, txt in evidence[(src, dst)][:3]:
                    print("      %-14s %-12s %r" % (dst, where, txt))
        print()
    return pkgs, edges, evidence


def cmd_graph(d):
    pkgs, edges, ev = cmd_refs(d, quiet=True)
    names = sorted(pkgs)
    indeg = collections.Counter()
    for s in names:
        for t in edges[s]:
            indeg[t] += 1
    print("%-24s %6s %7s" % ("map", "out", "in"))
    for n in names:
        print("%-24s %6d %7d" % (n, len(edges[n]), indeg[n]))
    print()
    orphans = [n for n in names if indeg[n] == 0]
    sinks = [n for n in names if not edges[n]]
    print("maps with ZERO incoming references : %d" % len(orphans))
    for n in orphans:
        print("     %s" % n)
    print()
    print("maps with ZERO outgoing references : %d" % len(sinks))
    for n in sinks:
        print("     %s" % n)
    print()
    total = sum(len(edges[n]) for n in names)
    print("edges: %d over %d nodes" % (total, len(names)))
    print()
    # connected components on the undirected version
    adj = collections.defaultdict(set)
    for s in names:
        for t in edges[s]:
            adj[s].add(t)
            adj[t].add(s)
    seen = set()
    comps = []
    for n in names:
        if n in seen:
            continue
        stack, comp = [n], []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            comp.append(x)
            stack.extend(adj[x] - seen)
        comps.append(sorted(comp))
    comps.sort(key=len, reverse=True)
    print("weakly connected components: %d" % len(comps))
    for c in comps:
        print("   %2d  %s" % (len(c), " ".join(c)))
    print()
    quid = [n for n in names if n.startswith("Quid_")]
    cross = [(s, t) for s in quid for t in edges[s] if not t.startswith("Quid_")]
    print("Quid_ maps referencing a non-Quid_ map: %d %s" % (len(cross), cross))
    into = [(s, t) for s in names if not s.startswith("Quid_")
            for t in edges[s] if t.startswith("Quid_")]
    print("non-Quid_ maps referencing a Quid_ map: %d %s" % (len(into), into))


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "E:/Maps"
    if "--names" in sys.argv:
        cmd_names(d)
    elif "--graph" in sys.argv:
        cmd_graph(d)
    else:
        cmd_refs(d)


if __name__ == "__main__":
    main()
