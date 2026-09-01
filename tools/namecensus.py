#!/usr/bin/env python3
"""namecensus.py -- the union of 249 name tables, which is a dictionary.

Every Unreal package carries the name of everything it contains. Put the 249
name tables together and you have the vocabulary of the game: classes,
properties, textures, sounds, actors, spells, rooms.

This builds that union and then asks the questions the union makes possible:

  * how many distinct names, and how many are used by exactly one package;
  * which names are in every package (the engine's floor);
  * the names that no import and no export in ANY package refers to -- a name
    kept in a table and pointed at by nothing;
  * a grep, so a word can be looked up and answered with the packages that
    carry it.

    python tools/namecensus.py E:/ --summary
    python tools/namecensus.py E:/ --unused
    python tools/namecensus.py E:/ --find WORD [WORD ...]
    python tools/namecensus.py E:/ --dump OUT.txt
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkg  # noqa: E402


def load(root):
    pkgs = []
    for path in upkg.find_packages(root):
        try:
            p = upkg.Package(path)
            p.load()
            pkgs.append(p)
        except Exception as e:
            print("  !! %s: %s" % (path, e), file=sys.stderr)
    return pkgs


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "E:/"
    args = sys.argv[2:]
    pkgs = load(root)
    where = collections.defaultdict(set)
    total = 0
    for p in pkgs:
        for n in p.names:
            where[n].add(os.path.basename(p.path))
            total += 1

    if "--find" in args:
        words = args[args.index("--find") + 1:]
        for w in words:
            hits = sorted(n for n in where if w.lower() in n.lower())
            print("%r : %d distinct names" % (w, len(hits)))
            for n in hits[:60]:
                ws = sorted(where[n])
                print("   %-38s in %d package(s): %s%s"
                      % (n, len(ws), ", ".join(ws[:4]),
                         " ..." if len(ws) > 4 else ""))
            if len(hits) > 60:
                print("   ... and %d more" % (len(hits) - 60))
            print()
        return

    if "--dump" in args:
        out = args[args.index("--dump") + 1]
        with open(out, "w", encoding="utf-8") as f:
            for n in sorted(where, key=lambda s: s.lower()):
                f.write("%-46s %3d  %s\n"
                        % (n, len(where[n]), " ".join(sorted(where[n]))))
        print("wrote %d names to %s" % (len(where), out))
        return

    if "--unused" in args:
        # a name referenced by no import and no export in its own package
        orphan = collections.Counter()
        examples = collections.defaultdict(list)
        for p in pkgs:
            used = set()
            for cp, cn, pk, on in p.imports:
                used.update((cp, cn, on))
            for e in p.exports:
                used.add(e[3])
            for i, n in enumerate(p.names):
                if i not in used:
                    orphan[n] += 1
                    if len(examples[n]) < 4:
                        examples[n].append(os.path.basename(p.path))
        print("names in a table that no import or export in the same package")
        print("points at: %d distinct, %d occurrences"
              % (len(orphan), sum(orphan.values())))
        print()
        print("(these are not unused objects -- an Unreal name is also used by")
        print("property values, states and string literals, which this tool")
        print("does not resolve. It is an upper bound, and it is printed as")
        print("one.)")
        print()
        for n, c in orphan.most_common(60):
            print("   %-40s x%-5d e.g. %s" % (n, c, ", ".join(examples[n])))
        return

    print("packages            : %d" % len(pkgs))
    print("name-table entries  : %d (with repeats across packages)" % total)
    print("distinct names      : %d" % len(where))
    print()
    once = [n for n in where if len(where[n]) == 1]
    print("names in exactly one package : %d (%.1f %%)"
          % (len(once), 100.0 * len(once) / len(where)))
    everywhere = [n for n in where if len(where[n]) == len(pkgs)]
    print("names in every package       : %d  %s"
          % (len(everywhere), sorted(everywhere)))
    print()
    hi = sorted(where, key=lambda n: -len(where[n]))[:20]
    print("the twenty most widely shared names:")
    for n in hi:
        print("   %-30s in %d of %d packages" % (n, len(where[n]), len(pkgs)))
    print()
    sizes = sorted(((p.name_n, os.path.basename(p.path)) for p in pkgs),
                   reverse=True)
    print("the ten largest name tables:")
    for n, b in sizes[:10]:
        print("   %-40s %d names" % (b, n))
    print("the ten smallest:")
    for n, b in sizes[-10:]:
        print("   %-40s %d names" % (b, n))
    print()
    lens = collections.Counter(len(n) for n in where)
    print("name length distribution: shortest %d, longest %d"
          % (min(lens), max(lens)))
    longest = sorted(where, key=len)[-8:]
    print("the longest names: %s" % longest)
    print()
    nonascii = [n for n in where if any(ord(c) > 126 or ord(c) < 32
                                        for c in n)]
    print("names with a byte outside printable ASCII: %d %s"
          % (len(nonascii), nonascii[:10]))
    print()
    tot_names_bytes = sum(p.name_end - p.name_off for p in pkgs)
    print("bytes spent on name tables across all packages: %d (%.3f %% of the"
          " %d bytes those packages occupy)"
          % (tot_names_bytes, 100.0 * tot_names_bytes /
             sum(p.size for p in pkgs), sum(p.size for p in pkgs)))


if __name__ == "__main__":
    main()
