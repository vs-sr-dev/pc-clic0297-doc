#!/usr/bin/env python3
"""renderers.py -- which 3D renderers this build can actually use.

readme_ita.txt names three families of graphics card as not fully supported.
That is a claim in prose. This is the same question asked of the bytes: which
render devices does the shipped configuration know about, which of those have
code on the disc, and which have only a name.

Sources, all on the disc:
  System/{0,1,2}/Default.ini    section headers of the form [XxxDrv.XxxRenderDevice]
                                and the RenderDevice / GameRenderDevice keys
  System/*.dll                  the native modules that actually exist
  System/*.int                  the localisation files, which survive their modules

    python tools/renderers.py E:/
"""
import os
import re
import sys

SEC = re.compile(r"^\[([A-Za-z0-9]+Drv)\.([A-Za-z0-9]+RenderDevice)\]\s*$")
KEY = re.compile(r"^(\w*RenderDevice)\s*=\s*(\S+)\s*$")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "E:/"
    sysdir = os.path.join(root, "System")
    have = {f.lower(): f for f in os.listdir(sysdir)}

    inis = []
    for sub in ("0", "1", "2"):
        p = os.path.join(sysdir, sub, "Default.ini")
        if os.path.exists(p):
            inis.append(p)
    if not inis:
        raise SystemExit("no Default.ini found")

    print("Default.ini copies found: %d" % len(inis))
    sizes = {os.path.getsize(p) for p in inis}
    print("all the same size: %s (%s)"
          % (len(sizes) == 1, sorted(sizes)))
    import hashlib
    digs = {hashlib.sha1(open(p, "rb").read()).hexdigest() for p in inis}
    print("all byte-identical: %s" % (len(digs) == 1))
    print()

    d = open(inis[0], "rb").read().decode("cp1252", "replace")
    devs = []
    keys = []
    for line in d.splitlines():
        m = SEC.match(line.strip())
        if m:
            devs.append((m.group(1), m.group(2)))
        m = KEY.match(line.strip())
        if m:
            keys.append((m.group(1), m.group(2)))

    print("render-device keys in [Engine.Engine]:")
    for k, v in keys:
        mod = v.split(".")[0]
        dll = (mod + ".dll").lower()
        print("   %-22s = %-34s  module %s: %s"
              % (k, v, mod,
                 "PRESENT as " + have[dll] if dll in have else "*** ABSENT ***"))
    print()

    print("render devices with a configuration section:")
    print()
    print("  %-12s %-28s %-10s %-10s" % ("module", "class", ".dll", ".int"))
    for mod, cls in devs:
        dll = (mod + ".dll").lower()
        it = (mod + ".int").lower()
        print("  %-12s %-28s %-10s %-10s"
              % (mod, cls,
                 have[dll] if dll in have else "-",
                 have[it] if it in have else "-"))
    print()

    shipped = [m for m, c in devs if (m + ".dll").lower() in have]
    named = [m for m, c in devs if (m + ".dll").lower() not in have]
    print("renderers with code on this disc : %d  %s" % (len(shipped), shipped))
    print("renderers named but not shipped  : %d  %s" % (len(named), named))
    print()

    print("and the .int files for render devices, with and without a module:")
    for f in sorted(os.listdir(sysdir)):
        if not f.lower().endswith(".int"):
            continue
        stem = f[:-4]
        if not stem.lower().endswith("drv"):
            continue
        dll = (stem + ".dll").lower()
        u = (stem + ".u").lower()
        print("   %-14s %6d bytes   .dll %s   .u %s"
              % (f, os.path.getsize(os.path.join(sysdir, f)),
                 "yes" if dll in have else "NO ",
                 "yes" if u in have else "NO "))
    print()
    print("note the spelling: the ini section is written one way and the .int")
    print("file another. Both are on this disc and they are different strings:")
    for mod, cls in devs:
        it = (mod + ".int").lower()
        if it not in have:
            alt = [have[k] for k in have
                   if k.endswith(".int") and k[:-4].lower() == mod.lower()]
            if alt:
                print("   ini says [%s.%s]   file is %s" % (mod, cls, alt[0]))


if __name__ == "__main__":
    main()
