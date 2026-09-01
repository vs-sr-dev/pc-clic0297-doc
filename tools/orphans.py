#!/usr/bin/env python3
"""orphans.py -- things shipped that nothing on this disc can use.

In Unreal 1 a module called Foo is a Foo.u (script package) or a Foo.dll
(native code), and its English strings live in Foo.int. The three are supposed
to travel together. This lists every module name that appears as one of the
three and asks which of the other two are present.

A Foo.int with no Foo.u and no Foo.dll is a localisation file for a module
that is not on the disc. That is the same class of object as the ten AMOS
banks on the Mystic Towers disc: shipped, complete, and unusable.

It also does the reverse for the localised sets: System/{0,1,2} hold .spa,
.ita and .por counterparts, and a counterpart with no .int is the other kind
of orphan.

    python tools/orphans.py E:/System
"""
import collections
import os
import sys

CODE = (".u", ".dll", ".unr")
LOCAL = (".int", ".spa", ".ita", ".por")


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "E:/System"
    have = collections.defaultdict(dict)

    def note(mod, kind, path):
        have[mod.lower()][kind] = (os.path.relpath(path, d)
                                   .replace(os.sep, "/"),
                                   os.path.getsize(path))

    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        if not os.path.isfile(p):
            continue
        stem, ext = os.path.splitext(f)
        e = ext.lower()
        if e in CODE or e in LOCAL:
            note(stem, e, p)
    maps = os.path.join(os.path.dirname(d.rstrip("/" + os.sep)), "Maps")
    if os.path.isdir(maps):
        for f in sorted(os.listdir(maps)):
            stem, ext = os.path.splitext(f)
            if ext.lower() == ".unr":
                note(stem, ".unr", os.path.join(maps, f))
    for sub in ("0", "1", "2"):
        p = os.path.join(d, sub)
        if not os.path.isdir(p):
            continue
        for f in sorted(os.listdir(p)):
            stem, ext = os.path.splitext(f)
            if ext.lower() in LOCAL:
                note(stem, ext.lower(), os.path.join(p, f))

    mods = sorted(have)
    print("%-14s %-9s %-9s %-9s %-7s %-7s %-7s %-7s"
          % ("module", ".u", ".dll", ".unr", ".int", ".spa", ".ita", ".por"))
    for m in mods:
        h = have[m]
        print("%-14s %-9s %-9s %-9s %-7s %-7s %-7s %-7s"
              % (m,
                 "%d" % h[".u"][1] if ".u" in h else "-",
                 "%d" % h[".dll"][1] if ".dll" in h else "-",
                 "%d" % h[".unr"][1] if ".unr" in h else "-",
                 "%d" % h[".int"][1] if ".int" in h else "-",
                 "%d" % h[".spa"][1] if ".spa" in h else "-",
                 "%d" % h[".ita"][1] if ".ita" in h else "-",
                 "%d" % h[".por"][1] if ".por" in h else "-"))
    print()

    noint = [m for m in mods if ".int" not in have[m]
             and (".u" in have[m] or ".dll" in have[m])]
    nocode = [m for m in mods if ".int" in have[m]
              and not any(k in have[m] for k in CODE)]
    print("modules with code but no English strings : %d" % len(noint))
    for m in noint:
        h = have[m]
        print("   %-14s %s" % (m, ", ".join(sorted(h))))
    print()
    print("STRINGS WITH NO MODULE -- a .int with no .u, no .dll and no .unr: %d"
          % len(nocode))
    tot = 0
    for m in nocode:
        h = have[m]
        sz = sum(v[1] for k, v in h.items())
        tot += sz
        print("   %-14s %s   %d bytes"
              % (m, ", ".join("%s %d" % (k, v[1]) for k, v in sorted(h.items())),
                 sz))
    print("   total %d bytes of localisation for absent modules" % tot)
    print()

    onlyloc = [m for m in mods
               if any(k in have[m] for k in (".spa", ".ita", ".por"))
               and ".int" not in have[m]]
    print("localised without an English original: %d %s" % (len(onlyloc),
                                                            onlyloc))
    intonly = [m for m in mods if ".int" in have[m]
               and not any(k in have[m] for k in (".spa", ".ita", ".por"))]
    print()
    print("English strings never translated: %d" % len(intonly))
    for m in intonly:
        print("   %-14s .int %d bytes%s"
              % (m, have[m][".int"][1],
                 "   (and no code either)" if m in nocode else ""))


if __name__ == "__main__":
    main()
